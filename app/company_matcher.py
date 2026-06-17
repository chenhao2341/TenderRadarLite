from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from .amount_utils import build_amount_context_from_notice
from .company_profile import CompanyProfile
from .models import Notice


MATCH_LEVELS = {"high", "medium", "low", "mismatch", "unknown"}

WEAK_MATCH_TERMS = ["设计", "咨询", "规划", "改造", "工程"]
STRONG_MATCH_TERMS = [
    "设计服务",
    "勘察设计",
    "工程咨询",
    "可研",
    "可行性研究",
    "规划编制",
    "初步设计",
    "施工图设计",
    "全过程咨询",
    "方案设计",
    "造价咨询",
]
PROCUREMENT_EXCLUSION_TERMS = [
    "管材采购",
    "设备采购",
    "材料采购",
    "货物采购",
]
CONSTRUCTION_EXCLUSION_TERMS = [
    "纯施工",
    "施工总承包",
    "专业承包",
    "安全生产许可证",
    "施工资质",
    "安装工程",
]


@dataclass(frozen=True)
class CompanyMatchResult:
    score: int
    level: str
    match_reasons: list[str] = field(default_factory=list)
    mismatch_reasons: list[str] = field(default_factory=list)
    manual_review_items: list[str] = field(default_factory=list)


def apply_company_match(notice: Notice, profile: CompanyProfile, *, today: str | None = None) -> CompanyMatchResult:
    result = match_company_profile(notice, profile, today=today)
    notice.company_match_score = result.score
    notice.company_match_level = result.level
    notice.company_match_reasons = result.match_reasons
    notice.company_mismatch_reasons = result.mismatch_reasons
    notice.manual_review_items = result.manual_review_items
    return result


def match_company_profile(notice: Notice, profile: CompanyProfile, *, today: str | None = None) -> CompanyMatchResult:
    text = _notice_text(notice)
    score = 20
    match_reasons: list[str] = []
    mismatch_reasons: list[str] = []
    manual_review_items: list[str] = []

    region_hits = _hits(notice.region, profile.regions)
    if region_hits:
        score += 10
        match_reasons.append(f"地区匹配：{region_hits[0]}")

    target_hits = _hits(text, profile.target_project_types)
    if target_hits:
        score += min(20, 12 + 4 * (len(target_hits) - 1))
        match_reasons.append(f"命中明确目标项目类型：{_join_hits(target_hits, limit=3)}")

    business_hits = _hits(text, profile.business_scope)
    if business_hits:
        score += min(12, 6 + 3 * (len(business_hits) - 1))
        match_reasons.append(f"命中业务方向：{_join_hits(business_hits, limit=3)}")

    strong_hits = _hits(text, STRONG_MATCH_TERMS)
    if strong_hits:
        score += min(28, 16 + 4 * (len(strong_hits) - 1))
        match_reasons.append(f"命中强匹配词：{_join_hits(strong_hits, limit=4)}")

    weak_hits = _hits(text, WEAK_MATCH_TERMS)
    if weak_hits:
        score += min(6, 2 * len(weak_hits))
        match_reasons.append(f"命中设计咨询相关词：{_join_hits(weak_hits, limit=4)}")
        if not strong_hits and not target_hits:
            match_reasons.append("仅为弱匹配词，需结合原公告确认是否为设计咨询服务")

    qualification_hits = _hits(text, profile.qualifications)
    if qualification_hits:
        score += min(10, 5 * len(qualification_hits))
        match_reasons.append(f"命中资质关键词：{_join_hits(qualification_hits, limit=2)}")

    exclude_hits = _unique_preserve_order(
        _hits(text, profile.exclude_project_types)
        + _hits(text, PROCUREMENT_EXCLUSION_TERMS)
        + _hits(text, CONSTRUCTION_EXCLUSION_TERMS)
    )
    if _is_lighting_installation_project(text):
        exclude_hits.append("照明工程（施工/安装导向）")
    exclude_hits = _unique_preserve_order(exclude_hits)
    if exclude_hits:
        score -= min(48, 18 + 8 * (len(exclude_hits) - 1))
        mismatch_reasons.append(f"命中排除类型：{_join_hits(exclude_hits, limit=4)}")
        mismatch_reasons.append("项目主要内容偏施工/采购，不属于当前企业目标标的")

    stage = notice.opportunity_stage or "unknown"
    if stage == "new_opportunity":
        score += 8
        match_reasons.append("公告阶段为新机会")
    elif stage == "correction_or_clarification":
        score -= 12
        manual_review_items.append("更正/澄清/答疑公告不是全新机会，建议归入项目动态或人工复核")
    elif stage == "project_update":
        score -= 8
        manual_review_items.append("项目动态公告需结合原项目进展人工复核")
    elif stage == "rebid_signal":
        score -= 6
        manual_review_items.append("流标/废标/重招线索需关注后续重新采购")
    elif stage == "award_result":
        score -= 30
        mismatch_reasons.append("结果公告通常不是投标机会")
    elif stage == "mismatch_procurement":
        score -= 30
        mismatch_reasons.append("公告阶段显示明显不匹配采购")
    elif stage in {"needs_manual_review", "unknown"}:
        manual_review_items.append("商机阶段需人工确认")

    if _deadline_expired(notice, today=today):
        score -= 25
        mismatch_reasons.append("截止时间可能已过")

    if _has_unconfirmed_amount_unit(notice):
        manual_review_items.append("金额单位未确认，需以原公告或附件为准")

    if notice.needs_attachment_review or notice.attachments or notice.attachments_found:
        manual_review_items.append("附件状态需人工复核，当前未解析附件正文")

    if weak_hits and not strong_hits and not target_hits:
        manual_review_items.append("仅命中弱匹配词，建议人工确认是否属于设计咨询服务")

    score = max(0, min(100, score))
    has_high_confidence_signal = bool(strong_hits or target_hits)
    has_obvious_exclusion = bool(exclude_hits)
    level = _level_for_score(
        score,
        mismatch_reasons,
        has_high_confidence_signal=has_high_confidence_signal,
        has_obvious_exclusion=has_obvious_exclusion,
    )
    return CompanyMatchResult(
        score=score,
        level=level,
        match_reasons=_limited(match_reasons),
        mismatch_reasons=_limited(mismatch_reasons),
        manual_review_items=_limited(manual_review_items),
    )


def _level_for_score(
    score: int,
    mismatch_reasons: list[str],
    *,
    has_high_confidence_signal: bool,
    has_obvious_exclusion: bool,
) -> str:
    if score >= 70 and has_high_confidence_signal and not has_obvious_exclusion:
        return "high"
    if score >= 45:
        return "medium"
    if score >= 25:
        return "low"
    return "mismatch" if mismatch_reasons else "low"


def _notice_text(notice: Notice) -> str:
    return " ".join(
        value
        for value in [
            notice.notice_title,
            notice.project_name,
            notice.section_name,
            notice.procurement_method,
            notice.content_summary,
            notice.qualification_summary,
            notice.lead_reason,
            " ".join(notice.hit_keywords),
            " ".join(notice.matched_positive_signals),
            " ".join(notice.matched_negative_signals),
        ]
        if value
    )


def _hits(text: str, keywords: list[str]) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for keyword in keywords:
        normalized = (keyword or "").strip()
        if normalized and normalized in text and normalized not in seen:
            seen.add(normalized)
            results.append(normalized)
    return results


def _join_hits(values: list[str], *, limit: int) -> str:
    return "、".join(values[:limit])


def _is_lighting_installation_project(text: str) -> bool:
    return "照明工程" in text and any(keyword in text for keyword in ["施工", "安装"])


def _has_unconfirmed_amount_unit(notice: Notice) -> bool:
    contexts = [
        build_amount_context_from_notice(
            notice.budget_amount,
            unit=notice.budget_amount_unit,
            unit_source=notice.budget_amount_unit_source,
            raw_text_snippet=notice.budget_amount_raw_text_snippet,
        ),
        build_amount_context_from_notice(
            notice.ceiling_price,
            unit=notice.ceiling_price_unit,
            unit_source=notice.ceiling_price_unit_source,
            raw_text_snippet=notice.ceiling_price_raw_text_snippet,
        ),
    ]
    return any(context.raw_value and not context.unit for context in contexts)


def _deadline_expired(notice: Notice, *, today: str | None) -> bool:
    raw = (notice.bid_open_or_response_deadline or notice.file_get_deadline or "").strip()
    if not raw:
        return False
    parsed = _parse_date(raw)
    if parsed is None:
        return False
    baseline = _parse_date(today or date.today().isoformat())
    return baseline is not None and parsed.date() < baseline.date()


def _parse_date(value: str) -> datetime | None:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value[:19] if fmt.endswith("%S") else value[:10], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        results.append(normalized)
    return results


def _limited(values: list[str]) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        results.append(normalized)
        if len(results) >= 5:
            break
    return results
