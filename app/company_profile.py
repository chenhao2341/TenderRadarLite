from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .config import ROOT_DIR


DEFAULT_COMPANY_PROFILE_PATH = ROOT_DIR / "profiles" / "company_sample.yaml"
DEFAULT_PREFERRED_UNIT = "元"
DEFAULT_BUDGET_NOTE = "金额单位不明确时不直接过滤"


@dataclass(frozen=True)
class BudgetPreference:
    min_amount: int | None = None
    preferred_unit: str = DEFAULT_PREFERRED_UNIT
    note: str = DEFAULT_BUDGET_NOTE


@dataclass(frozen=True)
class NoticeTypePreference:
    high: list[str] = field(default_factory=list)
    medium: list[str] = field(default_factory=list)
    low: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CompanyProfile:
    company_name: str = ""
    regions: list[str] = field(default_factory=list)
    business_scope: list[str] = field(default_factory=list)
    target_project_types: list[str] = field(default_factory=list)
    exclude_project_types: list[str] = field(default_factory=list)
    qualifications: list[str] = field(default_factory=list)
    budget_preference: BudgetPreference = field(default_factory=BudgetPreference)
    notice_type_preference: NoticeTypePreference = field(default_factory=NoticeTypePreference)


def load_company_profile(path: str | Path | None = None) -> CompanyProfile:
    resolved_path = Path(path) if path else DEFAULT_COMPANY_PROFILE_PATH
    if not resolved_path.is_absolute():
        resolved_path = ROOT_DIR / resolved_path
    if not resolved_path.exists():
        raise FileNotFoundError(f"Company profile not found: {resolved_path}")

    payload = yaml.safe_load(resolved_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Company profile must be a mapping: {resolved_path}")
    return _build_company_profile(payload)


def _build_company_profile(payload: dict[str, Any]) -> CompanyProfile:
    budget_payload = payload.get("budget_preference") or {}
    notice_type_payload = payload.get("notice_type_preference") or {}

    return CompanyProfile(
        company_name=_as_string(payload.get("company_name")),
        regions=_as_string_list(payload.get("regions")),
        business_scope=_as_string_list(payload.get("business_scope")),
        target_project_types=_as_string_list(payload.get("target_project_types")),
        exclude_project_types=_as_string_list(payload.get("exclude_project_types")),
        qualifications=_as_string_list(payload.get("qualifications")),
        budget_preference=BudgetPreference(
            min_amount=_as_int_or_none(budget_payload.get("min_amount")),
            preferred_unit=_as_string(budget_payload.get("preferred_unit")) or DEFAULT_PREFERRED_UNIT,
            note=_as_string(budget_payload.get("note")) or DEFAULT_BUDGET_NOTE,
        ),
        notice_type_preference=NoticeTypePreference(
            high=_as_string_list(notice_type_payload.get("high")),
            medium=_as_string_list(notice_type_payload.get("medium")),
            low=_as_string_list(notice_type_payload.get("low")),
        ),
    )


def _as_string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [_as_string(item) for item in value if _as_string(item)]
    normalized = _as_string(value)
    return [normalized] if normalized else []


def _as_int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise ValueError("budget_preference.min_amount must be an integer or null")
    return int(value)
