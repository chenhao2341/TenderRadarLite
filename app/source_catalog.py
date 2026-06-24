from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


ALLOWED_STATUS = {"supported", "alpha", "candidate", "planned", "blocked"}
ALLOWED_SOURCE_TYPE = {
    "government_procurement",
    "public_resource_trading",
    "industry_platform",
    "enterprise_procurement",
    "aggregator",
    "unknown",
}
ALLOWED_SOURCE_TYPE_HINT = {
    "json_api",
    "html_list_detail",
    "json_portal_flow",
    "spa_runtime_required",
    "blocked_captcha",
    "anti_bot",
    "candidate_unknown",
    "planned",
    "unknown",
}
ALLOWED_ACCESS_MODE = {"requests_json", "requests_html", "browser_runtime_required", "blocked", "unknown"}
ALLOWED_DETAIL_MODE = {"html_detail", "json_detail", "portal_detail_html", "list_only", "unknown"}
ALLOWED_ORIGINAL_URL_POLICY = {"readable", "mixed", "api_only", "blocked", "unknown"}
ALLOWED_RAW_API_POLICY = {"available", "partial", "none", "blocked", "unknown"}
ALLOWED_OBSERVABILITY = {"high", "medium", "low", "unknown"}
ALLOWED_RECOMMENDED_USAGE = {"default_supported", "manual_alpha_test", "probe_reference", "research_only", "blocked", "planned"}
ALLOWED_PROBE_REUSE_VALUE = {"high", "medium", "low", "blocked"}
ALLOWED_YES_NO_UNKNOWN = {"yes", "no", "unknown"}
ALLOWED_ATTACHMENT = {"yes", "no", "likely", "unknown"}
ALLOWED_RISK = {"low", "medium", "high", "unknown"}
ALLOWED_LOGIN = {"no", "likely", "yes", "unknown"}
ALLOWED_DATA_QUALITY = {"high", "medium", "low", "unknown"}
ALLOWED_SOURCE_FROM = {"native", "github_reference", "manual_research"}
STATUS_ORDER = ["supported", "alpha", "candidate", "planned", "blocked"]
BOOLEAN_ENUM_FIELDS = {"has_detail_page", "has_attachments", "login_requirement"}


def _default_catalog_path() -> Path:
    return Path(__file__).resolve().parent.parent / "config" / "source_catalog.yaml"


def load_source_catalog(path: str | Path | None = None) -> dict[str, Any]:
    catalog_path = Path(path) if path else _default_catalog_path()
    with catalog_path.open("r", encoding="utf-8") as fh:
        catalog = yaml.safe_load(fh) or {}
    if not isinstance(catalog, dict):
        raise ValueError("Source catalog root must be a mapping.")
    catalog.setdefault("version", 1)
    catalog.setdefault("sources", [])
    if not isinstance(catalog["sources"], list):
        raise ValueError("Source catalog sources must be a list.")
    for source in catalog["sources"]:
        if not isinstance(source, dict):
            continue
        for field in BOOLEAN_ENUM_FIELDS:
            value = source.get(field)
            if value is True:
                source[field] = "yes"
            elif value is False:
                source[field] = "no"
    return catalog


def validate_source_catalog(catalog: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    sources = catalog.get("sources") or []
    if not isinstance(sources, list):
        return ["Source catalog sources must be a list."]

    for index, source in enumerate(sources):
        label = f"source[{index}]"
        if not isinstance(source, dict):
            errors.append(f"{label}: source entry must be a mapping.")
            continue

        source_id = str(source.get("id") or "").strip()
        status = str(source.get("status") or "").strip()
        source_type = str(source.get("source_type") or "").strip()
        adapter = str(source.get("adapter") or "").strip()
        source_from = str(source.get("source_from") or "").strip()
        homepage = str(source.get("homepage") or "").strip()
        list_entry_url = str(source.get("list_entry_url") or "").strip()
        notes = str(source.get("notes") or "").strip()

        if not source_id:
            errors.append(f"{label}: id is required.")
        elif source_id in seen_ids:
            errors.append(f"{label}: duplicate id '{source_id}'.")
        else:
            seen_ids.add(source_id)

        if status not in ALLOWED_STATUS:
            errors.append(f"{source_id or label}: invalid status '{status}'.")
        if source_type not in ALLOWED_SOURCE_TYPE:
            errors.append(f"{source_id or label}: invalid source_type '{source_type}'.")
        source_type_hint = str(source.get("source_type_hint") or "").strip()
        if source_type_hint and source_type_hint not in ALLOWED_SOURCE_TYPE_HINT:
            errors.append(f"{source_id or label}: invalid source_type_hint '{source_type_hint}'.")
        access_mode = str(source.get("access_mode") or "").strip()
        if access_mode and access_mode not in ALLOWED_ACCESS_MODE:
            errors.append(f"{source_id or label}: invalid access_mode '{access_mode}'.")
        detail_mode = str(source.get("detail_mode") or "").strip()
        if detail_mode and detail_mode not in ALLOWED_DETAIL_MODE:
            errors.append(f"{source_id or label}: invalid detail_mode '{detail_mode}'.")
        original_url_policy = str(source.get("original_url_policy") or "").strip()
        if original_url_policy and original_url_policy not in ALLOWED_ORIGINAL_URL_POLICY:
            errors.append(f"{source_id or label}: invalid original_url_policy '{original_url_policy}'.")
        raw_api_policy = str(source.get("raw_api_policy") or "").strip()
        if raw_api_policy and raw_api_policy not in ALLOWED_RAW_API_POLICY:
            errors.append(f"{source_id or label}: invalid raw_api_policy '{raw_api_policy}'.")
        freshness_observability = str(source.get("freshness_observability") or "").strip()
        if freshness_observability and freshness_observability not in ALLOWED_OBSERVABILITY:
            errors.append(f"{source_id or label}: invalid freshness_observability '{freshness_observability}'.")
        dedupe_observability = str(source.get("dedupe_observability") or "").strip()
        if dedupe_observability and dedupe_observability not in ALLOWED_OBSERVABILITY:
            errors.append(f"{source_id or label}: invalid dedupe_observability '{dedupe_observability}'.")
        field_observability = str(source.get("field_completeness_observability") or "").strip()
        if field_observability and field_observability not in ALLOWED_OBSERVABILITY:
            errors.append(f"{source_id or label}: invalid field_completeness_observability '{field_observability}'.")
        recommended_usage = str(source.get("recommended_usage") or "").strip()
        if recommended_usage and recommended_usage not in ALLOWED_RECOMMENDED_USAGE:
            errors.append(f"{source_id or label}: invalid recommended_usage '{recommended_usage}'.")
        probe_reuse_value = str(source.get("probe_reuse_value") or "").strip()
        if probe_reuse_value and probe_reuse_value not in ALLOWED_PROBE_REUSE_VALUE:
            errors.append(f"{source_id or label}: invalid probe_reuse_value '{probe_reuse_value}'.")
        if str(source.get("has_detail_page") or "").strip() not in ALLOWED_YES_NO_UNKNOWN:
            errors.append(f"{source_id or label}: invalid has_detail_page value.")
        if str(source.get("has_attachments") or "").strip() not in ALLOWED_ATTACHMENT:
            errors.append(f"{source_id or label}: invalid has_attachments value.")
        if str(source.get("access_risk") or "").strip() not in ALLOWED_RISK:
            errors.append(f"{source_id or label}: invalid access_risk value.")
        if str(source.get("anti_bot_risk") or "").strip() not in ALLOWED_RISK:
            errors.append(f"{source_id or label}: invalid anti_bot_risk value.")
        if str(source.get("login_requirement") or "").strip() not in ALLOWED_LOGIN:
            errors.append(f"{source_id or label}: invalid login_requirement value.")
        if str(source.get("data_quality") or "").strip() not in ALLOWED_DATA_QUALITY:
            errors.append(f"{source_id or label}: invalid data_quality value.")
        if source_from not in ALLOWED_SOURCE_FROM:
            errors.append(f"{source_id or label}: invalid source_from '{source_from}'.")

        if status in {"supported", "alpha"} and not adapter:
            errors.append(f"{source_id or label}: supported/alpha source must declare adapter.")
        if status in {"candidate", "planned", "blocked"} and adapter:
            errors.append(f"{source_id or label}: candidate/planned/blocked source must not declare adapter.")
        if status == "supported" and source_from == "github_reference":
            errors.append(f"{source_id or label}: github_reference source cannot be supported.")
        if status == "candidate" and source_from == "native":
            errors.append(f"{source_id or label}: native source should not be marked candidate in this alpha.")
        if status in {"planned", "blocked"} and (homepage in {"", "unknown"} or list_entry_url in {"", "unknown"}) and not notes:
            errors.append(f"{source_id or label}: planned/blocked source with unknown URL must include notes.")

    return errors


def get_source_catalog_summary(catalog: dict[str, Any]) -> dict[str, Any]:
    grouped = group_sources_by_status(catalog)
    return {
        "total": len(catalog.get("sources") or []),
        "by_status": {status: len(grouped[status]) for status in STATUS_ORDER},
    }


def group_sources_by_status(catalog: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped = {status: [] for status in STATUS_ORDER}
    for source in catalog.get("sources") or []:
        status = str(source.get("status") or "").strip()
        if status in grouped:
            grouped[status].append(source)
    return grouped


def list_sources(
    catalog: dict[str, Any],
    status: str | None = None,
    source_type: str | None = None,
    region: str | None = None,
) -> list[dict[str, Any]]:
    status_filter = (status or "").strip()
    source_type_filter = (source_type or "").strip()
    region_filter = (region or "").strip()
    filtered: list[dict[str, Any]] = []
    for source in catalog.get("sources") or []:
        if status_filter and source.get("status") != status_filter:
            continue
        if source_type_filter and source.get("source_type") != source_type_filter:
            continue
        if region_filter and source.get("region") != region_filter:
            continue
        filtered.append(source)
    return filtered


def find_source_by_id(catalog: dict[str, Any], source_id: str) -> dict[str, Any] | None:
    expected_id = (source_id or "").strip()
    for source in catalog.get("sources") or []:
        if str(source.get("id") or "").strip() == expected_id:
            return source
    return None
