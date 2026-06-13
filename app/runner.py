from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import DATA_DIR, REPORT_DIR, ensure_runtime_dirs, load_keywords, load_pilot_notice_ids, load_sources
from .dedupe import build_dedupe_key
from .feishu import FeishuClient
from .fetcher import Fetcher
from .keywords import build_keyword_text, match_keywords
from .logging_utils import setup_logging
from .models import Notice
from .preview_report import classify_notice, write_structured_preview_report
from .storage import NoticeMatchStatus, Storage


@dataclass
class RunSummary:
    source_name: str
    fetched_count: int
    inserted_count: int
    duplicate_count: int
    pushed_count: int
    pages_scanned: int = 0
    page_size: int = 0
    detail_success_count: int = 0
    real_notice_count: int = 0
    skipped_count: int = 0
    direct_count: int = 0
    watchlist_count: int = 0
    exclude_count: int = 0
    feishu_written_count: int = 0
    webhook_sent_count: int = 0
    error_count: int = 0
    latest_site_publish_time: str = ""
    latest_db_publish_time: str = ""
    fetch_failed: bool = False


@dataclass
class BackfillSummary:
    total_history_count: int
    hit_history_count: int
    eligible_count: int
    written_count: int
    notified: bool
    duplicate_notice_sent: bool


@dataclass
class PilotNoticeRecord:
    notice_id: str
    section_id: str
    project_name: str
    section_name: str
    notice_type: str
    display_status: str
    publish_time: str
    lead_tier: str
    lead_reason: str
    employee_readable_url: str
    dedupe_key: str
    exists_in_sqlite: bool
    match_status: str
    legacy_current_dedupe_key: str
    legacy_current_notice_id: str
    legacy_upgrade_dedupe_key: str
    will_insert_sqlite: bool
    will_upgrade_legacy: bool
    will_write_feishu: bool
    will_send_bot: bool


@dataclass
class PilotNoticeWhitelistSummary:
    notice_ids_total: int
    matched_count: int
    missing_notice_ids: list[str]
    existing_count: int
    sqlite_inserted_count: int
    feishu_written_count: int
    webhook_sent_count: int
    direct_count: int
    watchlist_count: int
    exclude_count: int
    non_whitelist_scanned_count: int
    non_whitelist_written_count: int
    records: list[PilotNoticeRecord]
    bot_notice_ids: list[str]
    execute: bool


def _build_adapter(source: dict, fetcher: Fetcher):
    module = importlib.import_module(source["module"])
    adapter_class = getattr(module, source["class"])
    return adapter_class(
        source_name=source["name"],
        url=source["url"],
        region=source["region"],
        fetcher=fetcher,
        source_config=source,
    )


def _feishu_has_any_output(client: Any) -> bool:
    method = getattr(client, "has_any_output", None)
    return method() if callable(method) else True


def _feishu_can_write_bitable(client: Any) -> bool:
    method = getattr(client, "can_write_bitable", None)
    return method() if callable(method) else True


def _feishu_can_send_webhook(client: Any) -> bool:
    method = getattr(client, "can_send_webhook", None)
    return method() if callable(method) else True


def run_once(enable_feishu: bool = True, structured_preview: bool = False) -> list[RunSummary]:
    ensure_runtime_dirs()
    logger = setup_logging()
    keywords = load_keywords()
    storage = Storage(DATA_DIR / "bids.db")
    feishu = None
    if enable_feishu:
        feishu_candidate = FeishuClient(logger)
        if _feishu_has_any_output(feishu_candidate):
            feishu = feishu_candidate
    fetcher = Fetcher(logger)
    results: list[RunSummary] = []
    preview_notices: list[Notice] = []

    for source in load_sources():
        if not source.get("enabled", True):
            continue

        adapter = _build_adapter(source, fetcher)
        run_id = storage.start_run(source["name"])
        inserted = 0
        duplicates = 0
        feishu_written = 0
        webhook_sent = 0
        error_count = 0
        direct_notices: list[Notice] = []
        direct_count = 0
        watchlist_count = 0
        exclude_count = 0

        try:
            notices = adapter.crawl()
            stats = adapter.last_crawl_stats or {}

            for notice in notices:
                keyword_text = build_keyword_text(notice)
                notice.hit_keywords = match_keywords(keyword_text, keywords)
                classification = classify_notice(notice)
                notice.lead_tier = str(classification["lead_tier"])
                notice.lead_reason = str(classification["lead_reason"])
                notice.matched_positive_signals = list(classification["matched_positive_signals"])
                notice.matched_negative_signals = list(classification["matched_negative_signals"])
                if notice.lead_tier == "DIRECT":
                    direct_count += 1
                elif notice.lead_tier == "WATCHLIST":
                    watchlist_count += 1
                elif notice.lead_tier == "EXCLUDE":
                    exclude_count += 1

                is_new = storage.save_notice(notice)
                notice.is_new = is_new
                if is_new:
                    inserted += 1
                else:
                    duplicates += 1

                if structured_preview:
                    preview_notices.append(notice)

                if not is_new:
                    continue

                bitable_written = False
                if feishu is not None and _feishu_can_write_bitable(feishu) and notice.lead_tier in {"DIRECT", "WATCHLIST"}:
                    try:
                        feishu.write_notice(notice)
                    except Exception as exc:
                        error_count += 1
                        logger.error("bitable write failed: %s", exc)
                    else:
                        bitable_written = True
                        feishu_written += 1
                if feishu is not None and _feishu_can_send_webhook(feishu) and notice.lead_tier == "DIRECT":
                    if bitable_written or not _feishu_can_write_bitable(feishu):
                        direct_notices.append(notice)

            if feishu is not None and _feishu_can_send_webhook(feishu) and direct_notices:
                try:
                    feishu.send_summary(direct_notices)
                except Exception as exc:
                    error_count += 1
                    logger.error("webhook notify failed: %s", exc)
                else:
                    webhook_sent = 1

            source_site_name = f"{source.get('source', '')}-{source.get('source_subtype', '')}".strip("-")
            latest_db_publish_time = storage.get_latest_publish_time(source_site_name)
            fetch_failed = bool(stats.get("fetch_failed", 0))
            logger.info(
                "source=%s pages_scanned=%s page_size=%s fetched=%s detail_success=%s inserted=%s "
                "duplicates=%s direct=%s watchlist=%s exclude=%s feishu_written=%s webhook_sent=%s "
                "error_count=%s latest_site_publish_time=%s latest_db_publish_time=%s",
                source["name"],
                stats.get("pages_scanned", 1),
                stats.get("page_size", 10),
                stats.get("fetched_total", stats.get("list_count", len(notices))),
                stats.get("detail_success_count", len(notices)),
                inserted,
                duplicates,
                direct_count,
                watchlist_count,
                exclude_count,
                feishu_written,
                webhook_sent,
                error_count + int(stats.get("error_count", 0)),
                stats.get("latest_site_publish_time", ""),
                latest_db_publish_time,
            )
            storage.finish_run(
                run_id=run_id,
                status="failed" if fetch_failed else "ok",
                fetched_count=stats.get("fetched_total", stats.get("list_count", len(notices))),
                inserted_count=inserted,
                duplicate_count=duplicates,
                error_count=error_count + int(stats.get("error_count", 0)),
                note="",
            )
            results.append(
                RunSummary(
                    source_name=source["name"],
                    fetched_count=stats.get("fetched_total", stats.get("list_count", len(notices))),
                    inserted_count=inserted,
                    duplicate_count=duplicates,
                    pushed_count=direct_count,
                    pages_scanned=stats.get("pages_scanned", 1),
                    page_size=stats.get("page_size", 10),
                    detail_success_count=stats.get("detail_success_count", len(notices)),
                    real_notice_count=stats.get("real_notice_count", len(notices)),
                    skipped_count=stats.get("skipped_count", 0),
                    direct_count=direct_count,
                    watchlist_count=watchlist_count,
                    exclude_count=exclude_count,
                    feishu_written_count=feishu_written,
                    webhook_sent_count=webhook_sent,
                    error_count=error_count + int(stats.get("error_count", 0)),
                    latest_site_publish_time=stats.get("latest_site_publish_time", ""),
                    latest_db_publish_time=latest_db_publish_time,
                    fetch_failed=fetch_failed,
                )
            )
        except Exception as exc:
            logger.exception("source=%s run failed", source["name"])
            storage.finish_run(
                run_id=run_id,
                status="failed",
                fetched_count=0,
                inserted_count=inserted,
                duplicate_count=duplicates,
                error_count=1,
                note=str(exc),
            )
            results.append(
                RunSummary(
                    source_name=source["name"],
                    fetched_count=0,
                    inserted_count=inserted,
                    duplicate_count=duplicates,
                    pushed_count=0,
                    direct_count=direct_count,
                    watchlist_count=watchlist_count,
                    exclude_count=exclude_count,
                    feishu_written_count=feishu_written,
                    webhook_sent_count=webhook_sent,
                    error_count=1,
                    fetch_failed=True,
                )
            )

    if structured_preview:
        write_structured_preview_report(REPORT_DIR / "新来源结构化抓取预览.md", preview_notices, keywords)

    return results


def backfill_feishu() -> BackfillSummary:
    ensure_runtime_dirs()
    logger = setup_logging()
    storage = Storage(DATA_DIR / "bids.db")
    total_history_count, hit_history_count = storage.get_history_stats()
    pending_notices = storage.get_pending_backfill_notices()

    if hit_history_count == 0:
        return BackfillSummary(total_history_count, hit_history_count, 0, 0, False, False)

    feishu = FeishuClient(logger)
    written_notices: list[Notice] = []
    for notice in pending_notices:
        try:
            feishu.write_notice(notice)
        except Exception as exc:
            logger.error("backfill bitable write failed: %s", exc)
            continue
        storage.mark_notice_backfilled(build_dedupe_key(notice))
        written_notices.append(notice)

    notified = False
    if written_notices:
        try:
            feishu.send_summary(written_notices, summary_title="TenderRadarLite backfill completed", max_examples=3)
        except Exception as exc:
            logger.error("backfill webhook notify failed: %s", exc)
        else:
            notified = True

    return BackfillSummary(total_history_count, hit_history_count, len(pending_notices), len(written_notices), notified, False)


def structured_preview_report_path() -> Path:
    return REPORT_DIR / "structured-preview.md"


def run_pilot_notice_whitelist(
    pilot_notice_ids_file: str | Path,
    *,
    execute: bool = False,
) -> PilotNoticeWhitelistSummary:
    ensure_runtime_dirs()
    logger = setup_logging()
    keywords = load_keywords()
    storage = Storage(DATA_DIR / "bids.db")
    feishu = None
    if execute:
        feishu_candidate = FeishuClient(logger)
        if _feishu_has_any_output(feishu_candidate):
            feishu = feishu_candidate
    fetcher = Fetcher(logger)
    allowed_notice_ids = set(load_pilot_notice_ids(pilot_notice_ids_file))
    records: list[PilotNoticeRecord] = []
    matched_notices: list[Notice] = []
    bot_notice_ids: list[str] = []
    scanned_notice_count = 0

    if execute and feishu is not None and _feishu_can_write_bitable(feishu):
        feishu.init_schema()

    for source in load_sources():
        if not source.get("enabled", True):
            continue
        adapter = _build_adapter(source, fetcher)
        notices = adapter.crawl()
        scanned_notice_count += len(notices)
        for notice in notices:
            if notice.notice_id not in allowed_notice_ids:
                continue
            keyword_text = build_keyword_text(notice)
            notice.hit_keywords = match_keywords(keyword_text, keywords)
            classification = classify_notice(notice)
            notice.lead_tier = str(classification["lead_tier"])
            notice.lead_reason = str(classification["lead_reason"])
            notice.matched_positive_signals = list(classification["matched_positive_signals"])
            notice.matched_negative_signals = list(classification["matched_negative_signals"])
            notice.dedupe_key = build_dedupe_key(notice)
            matched_notices.append(notice)

    matched_map = {notice.notice_id: notice for notice in matched_notices}
    missing_notice_ids = [notice_id for notice_id in allowed_notice_ids if notice_id not in matched_map]
    existing_count = 0
    sqlite_inserted_count = 0
    feishu_written_count = 0
    webhook_sent_count = 0
    direct_count = 0
    watchlist_count = 0
    exclude_count = 0
    direct_notices_to_notify: list[Notice] = []

    for notice_id in load_pilot_notice_ids(pilot_notice_ids_file):
        notice = matched_map.get(notice_id)
        if notice is None:
            continue
        if notice.lead_tier == "DIRECT":
            direct_count += 1
        elif notice.lead_tier == "WATCHLIST":
            watchlist_count += 1
        elif notice.lead_tier == "EXCLUDE":
            exclude_count += 1

        match_status = storage.get_notice_match_status(notice)
        legacy_snapshot = storage.get_legacy_upgrade_snapshot(notice) if match_status == NoticeMatchStatus.LEGACY else None
        exists_in_sqlite = match_status != NoticeMatchStatus.MISSING
        if exists_in_sqlite:
            existing_count += 1
        will_insert_sqlite = match_status == NoticeMatchStatus.MISSING
        will_upgrade_legacy = match_status == NoticeMatchStatus.LEGACY
        will_write_feishu = will_insert_sqlite and notice.lead_tier in {"DIRECT", "WATCHLIST"}
        will_send_bot = will_insert_sqlite and notice.lead_tier == "DIRECT"

        records.append(
            PilotNoticeRecord(
                notice_id=notice.notice_id,
                section_id=notice.section_id,
                project_name=notice.project_name,
                section_name=notice.section_name,
                notice_type=notice.notice_type,
                display_status=_display_status(notice.notice_type),
                publish_time=notice.publish_time,
                lead_tier=notice.lead_tier,
                lead_reason=notice.lead_reason,
                employee_readable_url=notice.employee_readable_url,
                dedupe_key=notice.dedupe_key,
                exists_in_sqlite=exists_in_sqlite,
                match_status=match_status,
                legacy_current_dedupe_key=(legacy_snapshot or {}).get("current_dedupe_key", ""),
                legacy_current_notice_id=(legacy_snapshot or {}).get("current_notice_id", ""),
                legacy_upgrade_dedupe_key=(legacy_snapshot or {}).get("upgraded_dedupe_key", ""),
                will_insert_sqlite=will_insert_sqlite,
                will_upgrade_legacy=will_upgrade_legacy,
                will_write_feishu=will_write_feishu,
                will_send_bot=will_send_bot,
            )
        )

        if not execute:
            continue

        if will_upgrade_legacy:
            storage.save_notice(notice)
            continue
        if not will_insert_sqlite:
            continue

        inserted = storage.save_notice(notice)
        notice.is_new = inserted
        if not inserted:
            continue
        sqlite_inserted_count += 1

        bitable_written = False
        if feishu is not None and _feishu_can_write_bitable(feishu) and notice.lead_tier in {"DIRECT", "WATCHLIST"}:
            feishu.write_notice(notice)
            feishu_written_count += 1
            bitable_written = True
        if feishu is not None and _feishu_can_send_webhook(feishu) and notice.lead_tier == "DIRECT":
            if bitable_written or not _feishu_can_write_bitable(feishu):
                direct_notices_to_notify.append(notice)

    if execute and feishu is not None and _feishu_can_send_webhook(feishu) and direct_notices_to_notify:
        feishu.send_summary(direct_notices_to_notify)
        webhook_sent_count = 1
        bot_notice_ids = [notice.notice_id for notice in direct_notices_to_notify]

    return PilotNoticeWhitelistSummary(
        notice_ids_total=len(allowed_notice_ids),
        matched_count=len(records),
        missing_notice_ids=missing_notice_ids,
        existing_count=existing_count,
        sqlite_inserted_count=sqlite_inserted_count,
        feishu_written_count=feishu_written_count,
        webhook_sent_count=webhook_sent_count,
        direct_count=direct_count,
        watchlist_count=watchlist_count,
        exclude_count=exclude_count,
        non_whitelist_scanned_count=max(scanned_notice_count - len(records), 0),
        non_whitelist_written_count=0,
        records=records,
        bot_notice_ids=bot_notice_ids,
        execute=execute,
    )
def _display_status(notice_type: str) -> str:
    mapping = {
        "ZHAOBIAO_NOTICE": "招标公告",
        "CHENGQING_NOTICE": "澄清公告",
        "GENGZHENG_NOTICE": "更正公告",
        "ZANTING_NOTICE": "暂停公告",
        "REVIEW_NOTICE": "复议公告",
        "CHONGXIN_ZHAOBIAO_NOTICE": "重新招标公告",
    }
    return mapping.get((notice_type or "").strip(), notice_type or "未提取到")
