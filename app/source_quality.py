from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from .config import load_sources
from .source_catalog import STATUS_ORDER, load_source_catalog


@dataclass
class SourceQualityRow:
    source_key: str
    display_name: str
    source_name: str
    source_subtype: str
    source_type: str
    source_type_hint: str
    technical_type: str
    status: str
    default_enabled: bool
    current_enabled: bool
    participated_in_latest_run: bool
    access_mode: str
    detail_mode: str
    original_url_policy: str
    raw_api_policy: str
    freshness_observability: str
    dedupe_observability: str
    field_completeness_observability: str
    field_completeness_level: str
    detail_observation: str
    original_url_readable: str
    raw_api_url_available: str
    fetched: int | None
    inserted: int | None
    duplicates: int | None
    errors: int | None
    latest_db_publish_time: str
    latest_site_publish_time: str
    latest_report_time: str
    freshness_level: str
    dedupe_stability_level: str
    dedupe_signal: str
    known_risks: str
    probe_reuse_value: str
    recommended_usage: str


def build_source_quality_matrix(
    *,
    catalog: dict[str, Any] | None = None,
    current_run_summaries: Iterable[Any] | None = None,
    report_generated_at: str = "",
) -> list[dict[str, Any]]:
    active_catalog = catalog or load_source_catalog()
    runtime_lookup = _build_runtime_lookup(load_sources())
    run_lookup = _build_run_lookup(current_run_summaries or [])

    rows: list[SourceQualityRow] = []
    for index, source in enumerate(active_catalog.get("sources") or []):
        runtime_key = _runtime_lookup_key(source)
        runtime_entry = runtime_lookup.get(runtime_key) or runtime_lookup.get(("", runtime_key[1], runtime_key[2]))
        runtime_name = str((runtime_entry or {}).get("name") or "").strip()
        run_entry = run_lookup.get(runtime_name or str(source.get("name") or "").strip())
        source_type_hint = str(source.get("source_type_hint") or _derive_source_type_hint(source)).strip()
        technical_type = str(source.get("technical_type") or _derive_technical_type(source, source_type_hint)).strip()
        default_enabled = bool(source.get("default_enabled", source.get("status") == "supported"))
        current_enabled = bool(runtime_entry.get("enabled")) if runtime_entry else default_enabled
        fetched = _int_or_none(run_entry.get("fetched_count")) if run_entry else None
        inserted = _int_or_none(run_entry.get("inserted_count")) if run_entry else None
        duplicates = _int_or_none(run_entry.get("duplicate_count")) if run_entry else None
        errors = _int_or_none(run_entry.get("error_count")) if run_entry else None
        latest_site_publish_time = str(run_entry.get("latest_site_publish_time") or "") if run_entry else ""
        latest_db_publish_time = str(run_entry.get("latest_db_publish_time") or "") if run_entry else ""
        latest_report_time = str(run_entry.get("finished_at") or "") if run_entry else report_generated_at
        dedupe_signal = _classify_dedupe_signal(
            inserted_count=inserted,
            duplicate_count=duplicates,
            error_count=errors,
            latest_site_publish_time=latest_site_publish_time,
            latest_db_publish_time=latest_db_publish_time,
        )
        rows.append(
            SourceQualityRow(
                source_key=str(source.get("id") or f"source-{index}"),
                display_name=str(source.get("name") or source.get("id") or ""),
                source_name=str(source.get("source") or ""),
                source_subtype=str(source.get("source_subtype") or ""),
                source_type=str(source.get("source_type") or "unknown"),
                source_type_hint=source_type_hint,
                technical_type=technical_type,
                status=str(source.get("status") or "unknown"),
                default_enabled=default_enabled,
                current_enabled=current_enabled,
                participated_in_latest_run=run_entry is not None,
                access_mode=str(source.get("access_mode") or _derive_access_mode(source, source_type_hint)),
                detail_mode=str(source.get("detail_mode") or _derive_detail_mode(source, source_type_hint)),
                original_url_policy=str(source.get("original_url_policy") or _derive_original_url_policy(source_type_hint)),
                raw_api_policy=str(source.get("raw_api_policy") or _derive_raw_api_policy(source_type_hint)),
                freshness_observability=str(source.get("freshness_observability") or _derive_observability(source)),
                dedupe_observability=str(source.get("dedupe_observability") or _derive_observability(source)),
                field_completeness_observability=str(
                    source.get("field_completeness_observability") or _derive_observability(source)
                ),
                field_completeness_level=str(source.get("field_completeness_level") or source.get("data_quality") or "unknown"),
                detail_observation=_detail_observation(fetched, run_entry),
                original_url_readable=_url_policy_label(str(source.get("original_url_policy") or _derive_original_url_policy(source_type_hint))),
                raw_api_url_available=_raw_api_label(str(source.get("raw_api_policy") or _derive_raw_api_policy(source_type_hint))),
                fetched=fetched,
                inserted=inserted,
                duplicates=duplicates,
                errors=errors,
                latest_db_publish_time=latest_db_publish_time,
                latest_site_publish_time=latest_site_publish_time,
                latest_report_time=latest_report_time,
                freshness_level=_freshness_level(latest_site_publish_time, latest_db_publish_time, source),
                dedupe_stability_level=_dedupe_stability_level(dedupe_signal, source),
                dedupe_signal=dedupe_signal,
                known_risks=str(source.get("known_risks") or source.get("notes") or ""),
                probe_reuse_value=str(source.get("probe_reuse_value") or _derive_probe_reuse_value(source)),
                recommended_usage=str(source.get("recommended_usage") or _derive_recommended_usage(source)),
            )
        )

    order = {status: idx for idx, status in enumerate(STATUS_ORDER)}
    rows.sort(key=lambda row: (order.get(row.status, 999), row.current_enabled is False, row.display_name))
    return [asdict(row) for row in rows]


def _build_runtime_lookup(runtime_sources: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    lookup: dict[tuple[str, str, str], dict[str, Any]] = {}
    for source in runtime_sources:
        name = str(source.get("name") or "").strip()
        source_name = str(source.get("source") or "").strip()
        source_subtype = str(source.get("source_subtype") or "").strip()
        lookup[(name, source_name, source_subtype)] = source
        lookup[("", source_name, source_subtype)] = source
    return lookup


def _runtime_lookup_key(source: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(source.get("name") or "").strip(),
        str(source.get("source") or "").strip(),
        str(source.get("source_subtype") or "").strip(),
    )


def _build_run_lookup(run_summaries: Iterable[Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for summary in run_summaries:
        source_name = str(_read_value(summary, "source_name") or "").strip()
        if not source_name:
            continue
        lookup[source_name] = {
            "source_name": source_name,
            "fetched_count": _read_value(summary, "fetched_count"),
            "inserted_count": _read_value(summary, "inserted_count"),
            "duplicate_count": _read_value(summary, "duplicate_count"),
            "error_count": _read_value(summary, "error_count"),
            "detail_success_count": _read_value(summary, "detail_success_count"),
            "latest_site_publish_time": _read_value(summary, "latest_site_publish_time"),
            "latest_db_publish_time": _read_value(summary, "latest_db_publish_time"),
            "finished_at": _read_value(summary, "finished_at"),
        }
    return lookup


def _read_value(item: Any, key: str) -> Any:
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def _int_or_none(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    return int(value)


def _derive_source_type_hint(source: dict[str, Any]) -> str:
    source_id = str(source.get("id") or "")
    source_from = str(source.get("source_from") or "")
    status = str(source.get("status") or "unknown")
    if source_id == "zhejiang-government-procurement":
        return "json_portal_flow"
    if source_id in {"hengyang-procurement", "changsha-procurement"}:
        return "json_api"
    if source_id in {"hengyang-construction", "china-government-procurement-local"}:
        return "html_list_detail"
    if source_id == "chongqing-government-procurement":
        return "spa_runtime_required"
    if source_id == "guangdong-government-procurement":
        return "spa_runtime_required"
    if source_id == "china-government-procurement":
        return "candidate_unknown"
    if source_id == "enterprise-procurement-portals":
        return "anti_bot"
    if status == "planned":
        return "planned"
    if status == "blocked" and source_from == "github_reference":
        return "blocked_captcha"
    return "unknown"


def _derive_technical_type(source: dict[str, Any], source_type_hint: str) -> str:
    mapping = {
        "json_api": "JSON/API",
        "html_list_detail": "HTML list + detail",
        "json_portal_flow": "JSON portal flow",
        "spa_runtime_required": "SPA/runtime required",
        "blocked_captcha": "Blocked/captcha",
        "anti_bot": "Anti-bot/login",
        "candidate_unknown": "Candidate/unknown",
        "planned": "Planned research",
        "unknown": "Unknown",
    }
    return mapping.get(source_type_hint, str(source.get("source_type") or "Unknown"))


def _derive_access_mode(source: dict[str, Any], source_type_hint: str) -> str:
    if source_type_hint in {"json_api", "json_portal_flow"}:
        return "requests_json"
    if source_type_hint == "html_list_detail":
        return "requests_html"
    if source_type_hint == "spa_runtime_required":
        return "browser_runtime_required"
    if source_type_hint in {"blocked_captcha", "anti_bot"}:
        return "blocked"
    return "unknown"


def _derive_detail_mode(source: dict[str, Any], source_type_hint: str) -> str:
    if source_type_hint == "json_api":
        return "json_detail"
    if source_type_hint == "json_portal_flow":
        return "portal_detail_html"
    if source_type_hint == "html_list_detail":
        return "html_detail"
    if str(source.get("has_detail_page") or "") == "no":
        return "list_only"
    return "unknown"


def _derive_original_url_policy(source_type_hint: str) -> str:
    if source_type_hint in {"json_api", "html_list_detail"}:
        return "readable"
    if source_type_hint == "json_portal_flow":
        return "mixed"
    if source_type_hint in {"blocked_captcha", "anti_bot"}:
        return "blocked"
    if source_type_hint == "spa_runtime_required":
        return "api_only"
    return "unknown"


def _derive_raw_api_policy(source_type_hint: str) -> str:
    if source_type_hint in {"json_api", "json_portal_flow"}:
        return "available"
    if source_type_hint == "html_list_detail":
        return "partial"
    if source_type_hint in {"blocked_captcha", "anti_bot"}:
        return "blocked"
    return "none"


def _derive_observability(source: dict[str, Any]) -> str:
    update_frequency = str(source.get("update_frequency") or "")
    if update_frequency == "frequent":
        return "medium"
    if update_frequency == "unknown":
        return "low"
    return "unknown"


def _derive_probe_reuse_value(source: dict[str, Any]) -> str:
    source_type_hint = _derive_source_type_hint(source)
    if source_type_hint in {"json_api", "html_list_detail", "json_portal_flow"}:
        return "high"
    if source_type_hint in {"spa_runtime_required", "candidate_unknown"}:
        return "medium"
    if source_type_hint == "planned":
        return "low"
    if source_type_hint in {"blocked_captcha", "anti_bot"}:
        return "blocked"
    return "low"


def _derive_recommended_usage(source: dict[str, Any]) -> str:
    status = str(source.get("status") or "unknown")
    if status == "supported":
        return "default_supported"
    if status == "alpha":
        return "manual_alpha_test"
    if status == "candidate":
        return "probe_reference"
    if status == "planned":
        return "planned"
    if status == "blocked":
        return "blocked"
    return "research_only"


def _detail_observation(fetched_count: int | None, run_entry: dict[str, Any] | None) -> str:
    if not run_entry:
        return "未参与最近一次运行"
    detail_success_count = _int_or_none(run_entry.get("detail_success_count"))
    if fetched_count in {None, 0} or detail_success_count is None:
        return "unknown"
    if detail_success_count == fetched_count:
        return "detail_success"
    if detail_success_count == 0:
        return "detail_failed"
    return "detail_partial"


def _classify_dedupe_signal(
    *,
    inserted_count: int | None,
    duplicate_count: int | None,
    error_count: int | None,
    latest_site_publish_time: str,
    latest_db_publish_time: str,
) -> str:
    if inserted_count is None or duplicate_count is None:
        return "unknown"
    if inserted_count > 0 and duplicate_count > 0:
        if error_count == 0 and (inserted_count <= 1 or (latest_site_publish_time and latest_db_publish_time and latest_site_publish_time >= latest_db_publish_time)):
            return "suspected_realtime_update"
        return "dedupe_anomaly"
    if inserted_count == 0 and duplicate_count > 0 and (error_count or 0) == 0:
        return "stable"
    return "unknown"


def _freshness_level(latest_site_publish_time: str, latest_db_publish_time: str, source: dict[str, Any]) -> str:
    if latest_site_publish_time:
        return "site_observed"
    if latest_db_publish_time:
        return "db_observed"
    if str(source.get("freshness_observability") or ""):
        return str(source.get("freshness_observability"))
    return "unknown"


def _dedupe_stability_level(dedupe_signal: str, source: dict[str, Any]) -> str:
    if dedupe_signal == "stable":
        return "stable"
    if dedupe_signal == "suspected_realtime_update":
        return "watch"
    if dedupe_signal == "dedupe_anomaly":
        return "risk"
    return str(source.get("dedupe_stability_level") or "unknown")


def _url_policy_label(policy: str) -> str:
    mapping = {
        "readable": "yes",
        "mixed": "partial",
        "api_only": "no",
        "blocked": "blocked",
        "unknown": "unknown",
    }
    return mapping.get(policy, "unknown")


def _raw_api_label(policy: str) -> str:
    mapping = {
        "available": "yes",
        "partial": "partial",
        "none": "no",
        "blocked": "blocked",
        "unknown": "unknown",
    }
    return mapping.get(policy, "unknown")
