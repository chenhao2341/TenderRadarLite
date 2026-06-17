from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable

import requests

from .attachment_utils import ATTACHMENT_REVIEW_HINT, attachment_titles_summary
from .amount_utils import (
    amount_unit_source_label,
    build_amount_context_from_notice,
    has_explicit_amount_unit,
)
from .models import Notice


MISSING_TEXT = "未提取到"
MISSING_KEY_REASON = "未配置 DEEPSEEK_API_KEY"
ALLOWED_TIERS = {"DIRECT", "WATCHLIST"}
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
CHAT_COMPLETIONS_PATH = "/chat/completions"
DEFAULT_AI_ANALYSIS_MAX_ITEMS = 5
MAX_AI_ANALYSIS_ITEMS = 10
UNIT_UNCONFIRMED_TEXT = "单位未确认"
AMOUNT_UNIT_WARNING = "金额原始数值仅按输入字段展示，单位未确认，需以原公告及附件为准。"
AMOUNT_UNIT_RISK_TEXT = "预算或限价字段的金额单位在结构化输入中未确认，相关金额表述需以原公告及附件为准。"
FORBIDDEN_PHRASES = [
    "稳赚",
    "机会巨大",
    "强烈推荐",
    "必投",
    "中标概率很高",
    "无风险",
    "确定符合",
    "肯定能投",
    "一定可以参与",
]
SYSTEM_PROMPT = (
    "你是中国大陆招投标与政府采购线索研判助手，熟悉公开招标、政府采购、公共资源交易公告的阅读、分类和初筛。"
    "你可以覆盖建设工程、设计咨询、软件 IT、医疗设备、物业服务、后勤服务、培训服务、第三方检测、评估咨询等多行业场景，"
    "但不能把任何单一行业当成唯一默认场景。"
    "你不是评标委员会，不是法律顾问，不是最终投标决策人，不替代人工审核招标文件、资格条件、评分办法、附件和原公告。"
    "你只能基于系统已提取的结构化字段，结合当前 profile、公告类型和命中信号做线索初筛与跟进建议。"
    "所有自然语言输出必须使用简体中文，包括 summary、reasons、risks、follow_up_questions。"
    "不得使用英文撰写自然语言内容。"
    "保持专业、客观、中立、克制，不夸大项目价值，不制造机会感，不做营销式判断。"
    "不得输出“合规”“违法”“必然中标”“一定能投”“一定不能投”“中标概率高”等法律结论、结果承诺或中标概率判断。"
    "recommendation 字段只能使用 follow_up、watch、skip 三个枚举值之一。"
    "金额字段必须严格按输入字段解释；若输入未明确单位，不得推断为元、万元或亿元，也不得换算、放大、缩小或四舍五入解释。"
    "若金额单位未明确，只能表述为“金额原始数值为 xxx，单位未确认”或“公告中未明确金额单位”。"
    "不要编造预算单位、资质要求、采购人、项目地点、报名时间、开标时间、评分办法、投标保证金、业绩要求、人员要求等公告中没有的信息。"
    "缺失信息请明确写“公告中未明确”或“系统未提取到”。"
    "只返回 JSON 对象，不要返回额外说明。"
)


@dataclass(frozen=True)
class AIAnalysisConfig:
    enabled: bool = False
    api_key: str = ""
    base_url: str = DEFAULT_DEEPSEEK_BASE_URL
    model: str = DEFAULT_DEEPSEEK_MODEL
    timeout_seconds: int = 30
    max_items: int = DEFAULT_AI_ANALYSIS_MAX_ITEMS

    @classmethod
    def from_env(cls, *, enabled: bool = False, max_items: int | None = None) -> "AIAnalysisConfig":
        timeout_raw = os.getenv("AI_ANALYSIS_TIMEOUT_SECONDS", "30").strip() or "30"
        max_items_raw = os.getenv("AI_ANALYSIS_MAX_ITEMS", str(DEFAULT_AI_ANALYSIS_MAX_ITEMS)).strip() or str(DEFAULT_AI_ANALYSIS_MAX_ITEMS)
        try:
            timeout_seconds = max(int(timeout_raw), 1)
        except ValueError:
            timeout_seconds = 30
        try:
            env_max_items = max(int(max_items_raw), 1)
        except ValueError:
            env_max_items = DEFAULT_AI_ANALYSIS_MAX_ITEMS
        return cls(
            enabled=enabled,
            api_key=os.getenv("DEEPSEEK_API_KEY", "").strip(),
            base_url=(os.getenv("DEEPSEEK_BASE_URL", DEFAULT_DEEPSEEK_BASE_URL).strip() or DEFAULT_DEEPSEEK_BASE_URL),
            model=(os.getenv("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL).strip() or DEFAULT_DEEPSEEK_MODEL),
            timeout_seconds=timeout_seconds,
            max_items=normalize_ai_analysis_limit(max_items if max_items is not None else env_max_items),
        )


@dataclass
class AIAnalysisResult:
    enabled: bool
    skipped: bool
    notice_key: str
    skip_reason: str = ""
    opportunity_score: int | None = None
    recommendation: str = ""
    summary: str = ""
    reasons: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    follow_up_questions: list[str] = field(default_factory=list)
    raw_response: str = ""
    error: str = ""


class OpenAICompatibleClient:
    def __init__(self, config: AIAnalysisConfig, session: requests.Session | None = None) -> None:
        self.config = config
        self.session = session or requests.Session()

    @property
    def chat_completions_url(self) -> str:
        return f"{self.config.base_url.rstrip('/')}{CHAT_COMPLETIONS_PATH}"

    def create_chat_completion(self, prompt: str) -> str:
        response = self.session.post(
            self.chat_completions_url,
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.config.model,
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
            },
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        return str((((payload.get("choices") or [{}])[0].get("message") or {}).get("content")) or "")


def build_notice_analysis_prompt(notice: Notice, *, profile_name: str = "") -> str:
    normalized_profile = (profile_name or "").strip() or "unknown"
    fields = {
        "project_name": notice.project_name or MISSING_TEXT,
        "notice_title": notice.notice_title or notice.title or MISSING_TEXT,
        "notice_type": notice.notice_type or MISSING_TEXT,
        "region": notice.region or MISSING_TEXT,
        "purchaser_or_tenderer": notice.purchaser_or_tenderer or MISSING_TEXT,
        "agency": notice.agency or MISSING_TEXT,
        "publish_time": notice.publish_time or notice.notice_publish_time or MISSING_TEXT,
        "deadline_or_bid_open_time": notice.bid_open_or_response_deadline or notice.file_get_deadline or MISSING_TEXT,
        "budget_amount": _build_amount_field(
            notice.budget_amount,
            unit=notice.budget_amount_unit,
            unit_source=notice.budget_amount_unit_source,
            raw_text_snippet=notice.budget_amount_raw_text_snippet,
        ),
        "ceiling_price": _build_amount_field(
            notice.ceiling_price,
            unit=notice.ceiling_price_unit,
            unit_source=notice.ceiling_price_unit_source,
            raw_text_snippet=notice.ceiling_price_raw_text_snippet,
        ),
        "content_summary": notice.content_summary or MISSING_TEXT,
        "qualification_summary": notice.qualification_summary or MISSING_TEXT,
        "detail_page_status": _detail_status_for_prompt(notice),
        "attachment_count": notice.attachments_found,
        "has_likely_bidding_file": _yes_no_unknown(notice.has_likely_bidding_file, notice.detail_checked),
        "has_likely_procurement_file": _yes_no_unknown(notice.has_likely_procurement_file, notice.detail_checked),
        "has_likely_bill_file": _yes_no_unknown(notice.has_likely_bill_file, notice.detail_checked),
        "has_likely_correction_file": _yes_no_unknown(notice.has_likely_correction_file, notice.detail_checked),
        "attachment_title_summary": attachment_titles_summary(notice, max_items=5) or [MISSING_TEXT],
        "attachment_review_hint": ATTACHMENT_REVIEW_HINT,
        "attachment_guardrail": "不得声称已阅读附件全文，不得根据附件标题编造附件内容",
        "detail_risk_note": notice.detail_risk_note or MISSING_TEXT,
        "lead_tier": notice.lead_tier or MISSING_TEXT,
        "lead_reason": notice.lead_reason or MISSING_TEXT,
        "matched_positive_signals": notice.matched_positive_signals or [],
        "matched_negative_signals": notice.matched_negative_signals or [],
        "profile_id": normalized_profile,
        "profile_name": normalized_profile,
    }
    instructions = {
        "role": "中国大陆招投标与政府采购线索研判助手",
        "task": "基于结构化公告字段、当前 profile 和命中信号，判断该线索是否具备进一步人工跟进价值。",
        "scope": [
            "你是招投标线索初筛助手，不是评标委员会，不是法律顾问，不是最终投标决策人。",
            "你不替代人工审核原公告、附件、招标文件、评分办法和资格条件。",
            "你只做辅助研判，不输出法律结论，不输出中标概率，不承诺投标结果。",
        ],
        "analysis_principles": [
            "保持专业、客观、中立、克制，不夸大项目价值，不制造机会感，不做营销式判断。",
            "所有判断必须基于输入字段；字段中明确出现的信息才能作为事实，其他只能作为推断或不确定事项。",
            "缺失信息必须写“公告中未明确”或“系统未提取到”。",
            "不得编造预算单位、资质要求、采购人、项目地点、报名时间、开标时间、评分办法、投标保证金、业绩要求、人员要求等信息。",
            "所有自然语言字段必须使用简体中文，不得使用英文自然语言。",
            "opportunity_score 表示线索跟进价值，不是中标概率，不得解释为中标概率。",
            "金额单位不能判断，不等于项目没有跟进价值；应结合画像匹配、公告阶段、采购主体、时间窗口等因素综合判断。",
        ],
        "industry_profile_guidance": {
            "general_rule": "必须结合当前 profile、公告类型、匹配信号和公告摘要动态分析，不得默认按建设工程或设计咨询逻辑分析所有项目。",
            "design_consulting": "重点关注设计、规划、咨询、可研、方案、勘察、工程咨询等匹配信号。",
            "construction": "重点关注施工、改造、EPC、总承包、监理、资质等级、安全许可证等。",
            "software_it": "重点关注软件开发、系统集成、数字化平台、信息化服务、运维、数据治理、信创等。",
            "medical_equipment": "重点关注设备采购、医疗器械、参数要求、品牌或型号限制、售后服务、资质证照等。",
            "unknown_profile": "如果 profile 未知或信号不足，不得强行套用某一行业逻辑，只做通用招投标线索研判。",
        },
        "announcement_type_guidance": {
            "招标公告/采购公告": "可作为正式跟进线索，但仍需核实资质、截止时间、附件和采购需求。",
            "更正公告": "必须提示查看原公告和更正内容，不得直接当成全新招标机会。",
            "澄清公告": "必须提示关注是否改变招标条件、技术参数、投标截止时间或评分办法。",
            "流标公告": "可提示后续可能存在重新采购或重新招标机会，但不得直接认定已经重招。",
            "中标公告": "一般不作为投标机会，但可作为市场情报或竞争对手信息。",
            "暂停公告": "不得建议直接投标，需等待后续恢复、变更或重新公告。",
        },
        "amount_guardrails": [
            "金额字段必须严格按输入字段解释。",
            "如果金额上下文中的 unit 为未确认，不得推断为元、万元、亿元，也不得换算、放大、缩小或四舍五入解释。",
            "不得把 5631.436489 写成 5631万元，除非输入中明确出现万元等单位。",
            "对于 budget_amount、ceiling_price，应以该字段提供的 raw_value、unit、unit_source、raw_text_snippet 为准，不得脱离这些上下文字段自行补写单位。",
            "如果输入中没有明确单位，只能写“金额原始数值为 xxx，单位未确认”或“公告中未明确金额单位”。",
            "涉及金额判断时必须提示需以原公告及附件为准。",
            "如果金额单位未确认，但其他信号显示项目仍值得跟进，不得仅因单位未确认就自动建议 skip。",
        ],
        "forbidden_phrases": FORBIDDEN_PHRASES,
        "recommended_style": [
            "具备进一步跟进价值",
            "建议人工复核原公告及附件",
            "需核实资质条件",
            "需确认报名或投标截止时间",
            "需关注更正或澄清公告对招标条件的影响",
            "当前信息不足以判断是否完全匹配",
            "建议结合企业资质、业绩、人员、供货能力或服务能力进一步判断",
        ],
        "output_schema": {
            "opportunity_score": "0 到 100 的整数，表示线索跟进价值，不是中标概率",
            "recommendation": "follow_up | watch | skip",
            "summary": "简体中文，简短说明项目性质、公告阶段、是否值得进一步查看",
            "reasons": ["简体中文理由1", "简体中文理由2"],
            "risks": ["简体中文风险1", "简体中文风险2"],
            "follow_up_questions": ["简体中文追问1", "简体中文追问2"],
        },
    }
    return json.dumps({"instructions": instructions, "notice": fields}, ensure_ascii=False, indent=2)


def normalize_ai_analysis_limit(value: int | None) -> int:
    if value is None:
        return DEFAULT_AI_ANALYSIS_MAX_ITEMS
    return max(1, min(int(value), MAX_AI_ANALYSIS_ITEMS))


def analyze_notice(
    notice: Notice,
    config: AIAnalysisConfig,
    *,
    profile_name: str = "",
    client: OpenAICompatibleClient | None = None,
) -> AIAnalysisResult:
    result = AIAnalysisResult(enabled=config.enabled, skipped=False, notice_key=notice.dedupe_key or notice.notice_id or notice.title)
    if not config.enabled:
        result.skipped = True
        result.skip_reason = "AI analysis disabled"
        return result
    if (notice.lead_tier or "").upper() not in ALLOWED_TIERS:
        result.skipped = True
        result.skip_reason = f"lead_tier {notice.lead_tier or MISSING_TEXT} not eligible for AI analysis"
        return result
    if not config.api_key:
        result.skipped = True
        result.skip_reason = MISSING_KEY_REASON
        return result

    active_client = client or OpenAICompatibleClient(config)
    prompt = build_notice_analysis_prompt(notice, profile_name=profile_name)
    try:
        raw_content = active_client.create_chat_completion(prompt)
    except Exception as exc:
        result.skipped = True
        result.skip_reason = "AI request failed"
        result.error = str(exc)
        return result

    return _apply_amount_unit_guardrails(_parse_analysis_response(result, raw_content), notice)


def analyze_notices(
    notices: list[Notice],
    config: AIAnalysisConfig,
    *,
    profile_name: str = "",
    client_factory: Callable[[AIAnalysisConfig], OpenAICompatibleClient] | None = None,
) -> list[AIAnalysisResult]:
    client = client_factory(config) if client_factory is not None and config.enabled and config.api_key else None
    eligible = [notice for notice in notices if (notice.lead_tier or "").upper() in ALLOWED_TIERS]
    limited = eligible[: max(config.max_items, 0)]
    return [analyze_notice(notice, config, profile_name=profile_name, client=client) for notice in limited]


def _parse_analysis_response(result: AIAnalysisResult, raw_content: str) -> AIAnalysisResult:
    result.raw_response = raw_content or ""
    parsed = _try_parse_json_object(raw_content)
    if parsed is None:
        result.summary = (raw_content or "").strip()
        return result

    result.opportunity_score = _coerce_score(parsed.get("opportunity_score"))
    result.recommendation = str(parsed.get("recommendation") or "").strip()
    result.summary = str(parsed.get("summary") or "").strip()
    result.reasons = _coerce_string_list(parsed.get("reasons"))
    result.risks = _coerce_string_list(parsed.get("risks"))
    result.follow_up_questions = _coerce_string_list(parsed.get("follow_up_questions"))
    return result


def _apply_amount_unit_guardrails(result: AIAnalysisResult, notice: Notice) -> AIAnalysisResult:
    if not _needs_amount_unit_warning(notice):
        return result

    mentioned_units_before = _mentions_amount_units(result) or _mentions_amount_units_safe(result)
    result.summary = _sanitize_unconfirmed_amount_units(result.summary, notice)
    result.reasons = [_sanitize_unconfirmed_amount_units(text, notice) for text in result.reasons]
    result.risks = [_sanitize_unconfirmed_amount_units(text, notice) for text in result.risks]
    result.follow_up_questions = [_sanitize_unconfirmed_amount_units(text, notice) for text in result.follow_up_questions]

    if mentioned_units_before or _mentions_amount_units_safe(result):
        if AMOUNT_UNIT_RISK_TEXT not in result.risks:
            result.risks.append(AMOUNT_UNIT_RISK_TEXT)
    return result


def _mentions_amount_units(result: AIAnalysisResult) -> bool:
    texts = [result.summary, *result.reasons, *result.risks, *result.follow_up_questions]
    combined = " ".join(text for text in texts if text)
    return bool(re.search(r"\d(?:[\d.,])*\s*(?:元|万元|亿元)", combined))


def _needs_amount_unit_warning(notice: Notice) -> bool:
    return any(context.raw_value and not context.unit for context in _notice_amount_contexts(notice))


def _sanitize_unconfirmed_amount_units(text: str, notice: Notice) -> str:
    normalized = (text or "").strip()
    if not normalized:
        return normalized

    sanitized = normalized
    confirmed_mentions = {
        f"{context.raw_value}{context.unit}"
        for context in _notice_amount_contexts(notice)
        if context.raw_value and context.unit
    }
    for context in _notice_amount_contexts(notice):
        raw = context.raw_value
        if not raw or context.unit:
            continue
        pattern = re.compile(rf"{re.escape(raw)}\s*(?:元|万元|亿元)")
        sanitized = pattern.sub(f"金额原始数值为{raw}，单位未确认", sanitized)
    generic_pattern = re.compile(r"(\d(?:[\d.,])*)\s*(鍏億涓囧厓|浜垮厓)")
    sanitized = generic_pattern.sub(
        lambda match: match.group(0)
        if match.group(0).replace(" ", "") in confirmed_mentions
        else f"閲戦鍘熷鏁板€间负{match.group(1)}锛屽崟浣嶆湭纭",
        sanitized,
    )
    sanitized = re.sub(
        r"(\d(?:[\d.,])*)\s*(元|万元|亿元|鍏億涓囧厓|浜垮厓)",
        lambda match: match.group(0)
        if match.group(0).replace(" ", "") in confirmed_mentions
        else f"金额原始数值为{match.group(1)}，单位未确认",
        sanitized,
    )
    return sanitized


def _build_amount_field(
    value: str,
    *,
    unit: str = "",
    unit_source: str = "",
    raw_text_snippet: str = "",
) -> dict[str, str]:
    context = build_amount_context_from_notice(
        value,
        unit=unit,
        unit_source=unit_source,
        raw_text_snippet=raw_text_snippet,
    )
    if not context.raw_value:
        return {
            "raw_value": MISSING_TEXT,
            "unit": "未确认",
            "unit_source": "未确认",
            "interpretation_rule": "金额字段缺失，不得自行补写单位。",
        }
    if context.unit:
        return {
            "raw_value": context.raw_value,
            "unit": context.unit,
            "unit_source": amount_unit_source_label(context.unit_source),
            "raw_text_snippet": context.raw_text_snippet or f"{context.raw_value}{context.unit}",
            "interpretation_rule": "不得改写、换算或推断为其他单位。",
        }
    return {
        "raw_value": context.raw_value,
        "unit": UNIT_UNCONFIRMED_TEXT,
        "unit_source": "未确认",
        "raw_text_snippet": context.raw_text_snippet,
        "interpretation_rule": AMOUNT_UNIT_WARNING,
    }


def _notice_amount_contexts(notice: Notice) -> list:
    return [
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


def _try_parse_json_object(raw_content: str) -> dict[str, Any] | None:
    if not raw_content:
        return None
    text = raw_content.strip()
    candidates = [text]
    if "```" in text:
        candidates.append(text.replace("```json", "").replace("```", "").strip())
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _coerce_score(value: Any) -> int | None:
    try:
        score = int(value)
    except (TypeError, ValueError):
        return None
    return max(0, min(score, 100))


def _coerce_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            items.append(text)
    return items


def _mentions_amount_units_safe(result: AIAnalysisResult) -> bool:
    texts = [result.summary, *result.reasons, *result.risks, *result.follow_up_questions]
    combined = " ".join(text for text in texts if text)
    return bool(re.search(r"\d(?:[\d.,])*\s*(?:元|万元|亿元|鍏億涓囧厓|浜垮厓)", combined))


def _detail_status_for_prompt(notice: Notice) -> str:
    if not notice.detail_checked:
        return "未检查"
    if not notice.detail_available:
        return "不可访问"
    return "已检查"


def _yes_no_unknown(value: bool, checked: bool) -> str:
    if not checked:
        return "未确认"
    return "有" if value else "无"
