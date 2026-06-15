from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable

import requests

from .models import Notice


MISSING_TEXT = "未提取到"
ALLOWED_TIERS = {"DIRECT", "WATCHLIST"}


@dataclass(frozen=True)
class AIAnalysisConfig:
    enabled: bool = False
    api_key: str = ""
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"
    timeout_seconds: int = 30
    max_items: int = 5

    @classmethod
    def from_env(cls, *, enabled: bool = False, max_items: int | None = None) -> "AIAnalysisConfig":
        timeout_raw = os.getenv("AI_ANALYSIS_TIMEOUT_SECONDS", "30").strip() or "30"
        max_items_raw = os.getenv("AI_ANALYSIS_MAX_ITEMS", "5").strip() or "5"
        try:
            timeout_seconds = max(int(timeout_raw), 1)
        except ValueError:
            timeout_seconds = 30
        try:
            env_max_items = max(int(max_items_raw), 1)
        except ValueError:
            env_max_items = 5
        return cls(
            enabled=enabled,
            api_key=os.getenv("DEEPSEEK_API_KEY", "").strip(),
            base_url=(os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").strip() or "https://api.deepseek.com/v1"),
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip() or "deepseek-chat",
            timeout_seconds=timeout_seconds,
            max_items=max_items if max_items is not None else env_max_items,
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

    def create_chat_completion(self, prompt: str) -> str:
        response = self.session.post(
            f"{self.config.base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.config.model,
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "你是招投标线索研判助手。请基于已结构化字段判断该项目是否值得人工跟进。"
                            "不要编造资质、预算或时间。缺失信息请标注“未提取到”。"
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        return str((((payload.get("choices") or [{}])[0].get("message") or {}).get("content")) or "")


def build_notice_analysis_prompt(notice: Notice, *, profile_name: str = "") -> str:
    fields = {
        "project_name": notice.project_name or MISSING_TEXT,
        "notice_title": notice.notice_title or notice.title or MISSING_TEXT,
        "notice_type": notice.notice_type or MISSING_TEXT,
        "region": notice.region or MISSING_TEXT,
        "purchaser_or_tenderer": notice.purchaser_or_tenderer or MISSING_TEXT,
        "agency": notice.agency or MISSING_TEXT,
        "budget_amount": notice.budget_amount or MISSING_TEXT,
        "ceiling_price": notice.ceiling_price or MISSING_TEXT,
        "content_summary": notice.content_summary or MISSING_TEXT,
        "qualification_summary": notice.qualification_summary or MISSING_TEXT,
        "lead_tier": notice.lead_tier or MISSING_TEXT,
        "lead_reason": notice.lead_reason or MISSING_TEXT,
        "matched_positive_signals": notice.matched_positive_signals or [],
        "matched_negative_signals": notice.matched_negative_signals or [],
        "profile_id": profile_name or MISSING_TEXT,
        "profile_name": profile_name or MISSING_TEXT,
    }
    instructions = {
        "task": "请判断该项目是否值得人工跟进，并给出简洁、可执行的辅助说明。",
        "output_schema": {
            "opportunity_score": "0-100 的整数",
            "recommendation": "follow_up | watch | skip",
            "summary": "一句话摘要",
            "reasons": ["跟进理由 1", "跟进理由 2"],
            "risks": ["风险点 1", "风险点 2"],
            "follow_up_questions": ["建议追问 1", "建议追问 2"],
        },
    }
    return json.dumps({"instructions": instructions, "notice": fields}, ensure_ascii=False, indent=2)


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
        result.skip_reason = "未配置 DEEPSEEK_API_KEY"
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

    return _parse_analysis_response(result, raw_content)


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
