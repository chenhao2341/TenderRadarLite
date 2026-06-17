from __future__ import annotations

from dataclasses import dataclass
import re


UNIT_UNCONFIRMED_SOURCE = "unknown"
RAW_TEXT_SOURCE = "raw_text"
EXPLICIT_FIELD_SOURCE = "explicit_field"
EXPLICIT_AMOUNT_UNIT_TOKENS = ("万元", "亿元", "元", "人民币", "RMB", "CNY", "¥", "￥")
AMOUNT_UNIT_PATTERN = re.compile(
    r"(?P<prefix>人民币|RMB|CNY|¥|￥)?\s*(?P<number>\d+(?:\.\d+)?)\s*(?P<unit>亿元|万元|元)"
)


@dataclass(frozen=True)
class AmountContext:
    raw_value: str
    unit: str | None
    unit_source: str
    raw_text_snippet: str


def has_explicit_amount_unit(value: str) -> bool:
    normalized = (value or "").strip()
    if not normalized:
        return False
    return any(token in normalized for token in EXPLICIT_AMOUNT_UNIT_TOKENS)


def parse_amount_context(
    raw_value: str,
    *,
    field_text: str = "",
    text_sources: list[tuple[str, str]] | None = None,
    field_hints: tuple[str, ...] = (),
) -> AmountContext:
    normalized_raw = (raw_value or "").strip()
    explicit = _extract_explicit_amount(field_text or normalized_raw)
    if explicit is not None:
        return explicit

    if not normalized_raw:
        return AmountContext(raw_value="", unit=None, unit_source=UNIT_UNCONFIRMED_SOURCE, raw_text_snippet="")

    for source_name, text in text_sources or []:
        snippet = _find_amount_snippet(normalized_raw, text, field_hints=field_hints)
        if snippet is None:
            continue
        _, unit = snippet
        return AmountContext(
            raw_value=normalized_raw,
            unit=unit,
            unit_source=source_name or RAW_TEXT_SOURCE,
            raw_text_snippet=_extract_snippet(text, normalized_raw, unit),
        )

    return AmountContext(
        raw_value=normalized_raw,
        unit=None,
        unit_source=UNIT_UNCONFIRMED_SOURCE,
        raw_text_snippet="",
    )


def format_amount_with_context(raw_value: str, *, unit: str | None, missing_text: str, unit_unconfirmed_text: str) -> str:
    normalized = (raw_value or "").strip()
    if not normalized:
        return missing_text
    if unit:
        return f"{normalized} {unit}"
    return f"{normalized}（{unit_unconfirmed_text}）"


def amount_unit_source_label(unit_source: str) -> str:
    if unit_source == EXPLICIT_FIELD_SOURCE:
        return "源字段"
    if unit_source == RAW_TEXT_SOURCE:
        return "公告原文"
    return "未确认"


def build_amount_context_from_notice(
    raw_value: str,
    *,
    unit: str = "",
    unit_source: str = "",
    raw_text_snippet: str = "",
) -> AmountContext:
    normalized_unit = (unit or "").strip() or None
    normalized_source = (unit_source or "").strip() or UNIT_UNCONFIRMED_SOURCE
    explicit = _extract_explicit_amount(raw_value)
    if explicit is not None:
        return explicit
    return AmountContext(
        raw_value=(raw_value or "").strip(),
        unit=normalized_unit,
        unit_source=normalized_source,
        raw_text_snippet=(raw_text_snippet or "").strip(),
    )


def _extract_explicit_amount(value: str) -> AmountContext | None:
    normalized = (value or "").strip()
    if not normalized:
        return None
    match = AMOUNT_UNIT_PATTERN.search(normalized)
    if match is None:
        return None
    return AmountContext(
        raw_value=match.group("number"),
        unit=match.group("unit"),
        unit_source=EXPLICIT_FIELD_SOURCE,
        raw_text_snippet=normalized,
    )


def _find_amount_snippet(raw_value: str, text: str, *, field_hints: tuple[str, ...]) -> tuple[str, str] | None:
    normalized_text = _normalize_space(text)
    if not normalized_text:
        return None

    candidate_pattern = re.compile(
        rf"(?P<segment>.{{0,40}}{re.escape(raw_value)}\s*(?P<unit>亿元|万元|元).{{0,40}})"
    )
    candidates = list(candidate_pattern.finditer(normalized_text))
    if not candidates:
        return None

    if field_hints:
        for match in candidates:
            segment = match.group("segment")
            if any(hint in segment for hint in field_hints):
                return segment, match.group("unit")

    first = candidates[0]
    return first.group("segment"), first.group("unit")


def _extract_snippet(text: str, raw_value: str, unit: str) -> str:
    normalized_text = _normalize_space(text)
    if not normalized_text:
        return ""
    anchor = f"{raw_value}{unit}"
    index = normalized_text.find(anchor)
    if index < 0:
        return anchor
    start = max(index - 24, 0)
    end = min(index + len(anchor) + 24, len(normalized_text))
    return normalized_text[start:end].strip(" ，；;。")


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()
