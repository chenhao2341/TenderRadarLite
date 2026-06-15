from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from .models import Notice
from .profiles import load_profile


KEY_FIELDS = [
    "project_name",
    "section_name",
    "notice_type",
    "project_code",
    "purchaser_or_tenderer",
    "agency",
    "region",
    "publish_time",
    "file_get_deadline",
    "bid_open_or_response_deadline",
    "budget_amount",
    "ceiling_price",
    "procurement_method",
    "content_summary",
    "qualification_summary",
    "accepts_consortium",
    "original_url",
]

REQUIRED_FIELDS = [
    "project_name",
    "notice_type",
    "purchaser_or_tenderer",
    "agency",
    "publish_time",
    "original_url",
    "content_summary",
]

MANUAL_WATCHLIST_PROJECTS = {
    "衡南县城乡供水扩容及管网漏损治理项目",
    "衡山县第四中学综合楼建设项目",
    "衡山县城市供水提质改造及智慧水务建设项目(供水管网改造一期)",
    "衡阳市直管公房危旧房改造项目（二期）",
}

DIRECT_SIGNALS = [
    "规划设计",
    "建筑设计",
    "装修设计",
    "景观设计",
    "方案设计",
    "城市更新策划",
    "规划编制",
    "工程咨询",
    "勘察设计",
    "设计服务",
    "文旅策划",
    "展陈设计",
    "设计",
    "规划",
    "咨询",
    "策划",
    "方案编制",
]

WATCHLIST_SIGNALS = [
    "危旧房改造",
    "老旧小区改造",
    "城市更新",
    "公共建筑",
    "城乡环境提升",
    "校园改造",
    "乡村振兴",
    "文旅空间",
    "风貌整治",
    "基础设施改造",
    "供水改造",
    "智慧水务",
    "漏损治理",
    "管网改造",
    "综合楼建设",
    "改造",
]

EXCLUDE_SIGNALS = [
    "电梯采购",
    "图书采购",
    "空调采购",
    "电器采购",
    "普通设备采购",
    "家具采购",
    "普通家具采购",
    "医疗设备",
    "经营权管理",
    "货物采购",
    "设备采购",
    "电梯",
    "图书",
    "空调",
    "电器",
    "家具",
]

DIRECT_BLOCKERS = [
    "施工总承包",
    "建筑工程三级",
    "市政公用工程三级",
    "安全生产许可证",
]


def write_structured_preview_report(path: Path, notices: Iterable[Notice], keywords: list[str] | None = None) -> None:
    grouped: dict[str, list[Notice]] = defaultdict(list)
    for notice in notices:
        grouped[notice.source_subtype].append(notice)

    p01 = grouped.get("建设工程交易", [])[:10]
    p02_all = grouped.get("政府采购交易", [])
    p02_recent = [notice for notice in p02_all if is_recent_notice(notice.publish_time)][:10]
    p01_counts = Counter(notice.lead_tier or "UNSET" for notice in p01)

    lines: list[str] = [
        "# 新来源结构化抓取预览",
        "",
        "## 1. 概览",
        "",
        f"- 建设工程交易样本数：{len(p01)}",
        f"- 建设工程交易 DIRECT：{p01_counts.get('DIRECT', 0)}",
        f"- 建设工程交易 WATCHLIST：{p01_counts.get('WATCHLIST', 0)}",
        f"- 建设工程交易 EXCLUDE：{p01_counts.get('EXCLUDE', 0)}",
        f"- 政府采购交易有正文样本数：{len(p02_all)}",
        f"- 政府采购交易近期有效样本数：{len(p02_recent)}",
        "- 当前关键词库：" + "、".join(keywords or []),
        "- 本报告仅用于本地结构化验收，不触发飞书或 Webhook。",
        "",
    ]

    lines.extend(_render_section("P0-1 建设工程交易前 10 条", p01))
    lines.extend(_render_section("P0-2 政府采购交易中近期有效公告前 10 条", p02_recent))
    if not p02_recent:
        lines.extend(
            [
                "## P0-2 近期性说明",
                "",
                f"- 本轮有正文样本共 {len(p02_all)} 条，但按公告发布时间筛选“近期”后为 0 条。",
                "- 原因：列表接口 `noticeSendTime` 长期为空，详情正文 `noticeSendTime` 实测落在 2018-2021 年，当前接口返回的是历史项目壳与旧公告映射，不是近期公告流。",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def evaluate_notice(notice: Notice, today: str | None = None) -> dict[str, str]:
    missing_required = [field for field in REQUIRED_FIELDS if not getattr(notice, field)]
    fields_ok = "是" if not missing_required else "否"
    fields_reason = "核心字段齐全" if not missing_required else f"缺少核心字段: {', '.join(missing_required)}"
    classification = classify_notice(notice, today=today)
    recommend = "是" if classification["lead_tier"] in {"DIRECT", "WATCHLIST"} and is_recent_notice(notice.publish_time, today=today) else "否"
    reason = str(classification["lead_reason"])
    if not is_recent_notice(notice.publish_time, today=today):
        reason = f"非近期公告；{reason}"
    if not notice.original_url or not notice.content_summary:
        reason = f"缺少真实正文支撑；{reason}"
    return {
        "fields_ok": fields_ok,
        "fields_reason": fields_reason,
        "recommend_feishu": recommend,
        "recommend_reason": reason,
    }


def classify_notice(
    notice: Notice,
    today: str | None = None,
    *,
    profile: dict | None = None,
) -> dict[str, str | list[str]]:
    active_profile = profile or load_profile()
    text = " ".join(
        part
        for part in [
            notice.project_name,
            notice.section_name,
            notice.content_summary,
            notice.qualification_summary,
            notice.procurement_method,
            notice.notice_type,
        ]
        if part
    )

    strong_positive_keywords = list(active_profile.get("strong_positive_keywords", []))
    positive_keywords = list(active_profile.get("positive_keywords", []))
    negative_keywords = list(active_profile.get("negative_keywords", []))
    exclude_keywords = list(active_profile.get("exclude_keywords", []))

    positive_signals = _unique_preserve_order(
        _collect_matches(text, strong_positive_keywords + DIRECT_SIGNALS + positive_keywords + WATCHLIST_SIGNALS)
    )
    negative_signals = _unique_preserve_order(
        _collect_matches(text, exclude_keywords + EXCLUDE_SIGNALS + negative_keywords + DIRECT_BLOCKERS)
    )
    if notice.hit_keywords:
        for keyword in notice.hit_keywords:
            if keyword not in positive_signals:
                positive_signals.append(keyword)

    if notice.project_name in MANUAL_WATCHLIST_PROJECTS:
        if "人工审计样本" not in positive_signals:
            positive_signals.insert(0, "人工审计样本")
        return {
            "lead_tier": "WATCHLIST",
            "lead_reason": "人工审计已确认：当前为施工资质或工程实施导向，不是直接设计/规划/咨询商机，但存在延伸观察价值。",
            "matched_positive_signals": positive_signals,
            "matched_negative_signals": negative_signals,
        }

    has_direct_signal = _contains_any(text, strong_positive_keywords + DIRECT_SIGNALS + positive_keywords) or bool(notice.hit_keywords)
    has_watchlist_signal = _contains_any(text, WATCHLIST_SIGNALS)
    has_direct_blocker = _contains_any(notice.qualification_summary, DIRECT_BLOCKERS)
    has_negative_signal = _contains_any(text, negative_keywords + DIRECT_BLOCKERS)
    has_exclude_signal = _contains_any(text, exclude_keywords + EXCLUDE_SIGNALS)

    if has_exclude_signal:
        return {
            "lead_tier": "EXCLUDE",
            "lead_reason": "标题或正文出现明显无关的货物/设备采购信号，排除。",
            "matched_positive_signals": positive_signals,
            "matched_negative_signals": negative_signals or ["明显无关类别"],
        }

    if has_direct_signal and not has_direct_blocker and not has_negative_signal and not has_exclude_signal:
        return {
            "lead_tier": "DIRECT",
            "lead_reason": "标题/摘要/资质要求明确属于设计/规划/咨询服务，可作为直接商机。",
            "matched_positive_signals": positive_signals,
            "matched_negative_signals": negative_signals,
        }

    if has_watchlist_signal or (has_direct_signal and has_negative_signal):
        blocker_text = "当前存在施工资质或工程实施导向，不应进入 DIRECT。"
        reason = "存在改造、城市更新或公共建设延伸信号，建议作为关联观察。" if not has_direct_blocker else blocker_text
        return {
            "lead_tier": "WATCHLIST",
            "lead_reason": reason,
            "matched_positive_signals": positive_signals,
            "matched_negative_signals": negative_signals,
        }

    if not is_recent_notice(notice.publish_time, today=today):
        negative_signals.append("非近期公告")
    return {
        "lead_tier": "EXCLUDE",
        "lead_reason": "未出现明确设计/规划/咨询方向，也缺少值得持续观察的改造延伸信号。",
        "matched_positive_signals": positive_signals,
        "matched_negative_signals": negative_signals,
    }


def is_recent_notice(publish_time: str, *, today: str | None = None, days: int = 180) -> bool:
    dt = parse_notice_date(publish_time)
    if not dt:
        return False
    today_date = datetime.strptime(today, "%Y-%m-%d").date() if today else date.today()
    return (today_date - dt).days <= days


def parse_notice_date(value: str) -> date | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f+08:00", "%Y-%m-%dT%H:%M:%S+08:00"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _collect_matches(text: str, keywords: list[str]) -> list[str]:
    return [keyword for keyword in keywords if keyword and keyword in text]


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _render_section(title: str, notices: list[Notice]) -> list[str]:
    lines = [f"## {title}", ""]
    if not notices:
        lines.extend(["- 无样本。", ""])
        return lines

    for idx, notice in enumerate(notices, start=1):
        empty_fields = [field for field in KEY_FIELDS if not getattr(notice, field)]
        evaluation = evaluate_notice(notice)
        classification = classify_notice(notice)
        lines.extend(
            [
                f"### {idx}. {notice.title}",
                "",
                f"- source: {notice.source}",
                f"- source_subtype: {notice.source_subtype}",
                f"- dedupe_key: {notice.dedupe_key}",
                f"- section_id: {notice.section_id or '空'}",
                f"- project_name: {notice.project_name or '空'}",
                f"- section_name: {notice.section_name or '空'}",
                f"- notice_type: {notice.notice_type or '空'}",
                f"- project_code: {notice.project_code or '空'}",
                f"- purchaser_or_tenderer: {notice.purchaser_or_tenderer or '空'}",
                f"- agency: {notice.agency or '空'}",
                f"- region: {notice.region or '空'}",
                f"- publish_time: {notice.publish_time or '空'}",
                f"- file_get_deadline: {notice.file_get_deadline or '空'}",
                f"- bid_open_or_response_deadline: {notice.bid_open_or_response_deadline or '空'}",
                f"- budget_amount: {notice.budget_amount or '空'}",
                f"- ceiling_price: {notice.ceiling_price or '空'}",
                f"- procurement_method: {notice.procurement_method or '空'}",
                f"- content_summary: {notice.content_summary or '空'}",
                f"- qualification_summary: {notice.qualification_summary or '空'}",
                f"- has_attachment: {'是' if notice.has_attachment else '否'}",
                f"- attachment_count: {notice.attachment_count}",
                f"- hit_keywords: {'、'.join(notice.hit_keywords) if notice.hit_keywords else '无'}",
                f"- 空字段: {', '.join(empty_fields) if empty_fields else '无'}",
                f"- 字段完整度是否合格: {evaluation['fields_ok']}",
                f"- 字段完整度原因: {evaluation['fields_reason']}",
                f"- lead_tier: {classification['lead_tier']}",
                f"- lead_reason: {classification['lead_reason']}",
                f"- matched_positive_signals: {'、'.join(classification['matched_positive_signals']) if classification['matched_positive_signals'] else '无'}",
                f"- matched_negative_signals: {'、'.join(classification['matched_negative_signals']) if classification['matched_negative_signals'] else '无'}",
                f"- 是否建议进入飞书试用: {evaluation['recommend_feishu']}",
                f"- 建议或排除原因: {evaluation['recommend_reason']}",
                "",
            ]
        )
    return lines
