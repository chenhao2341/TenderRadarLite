from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .dedupe import build_dedupe_key
from .models import Notice


class NoticeMatchStatus:
    EXACT = "exact"
    LEGACY = "legacy"
    MISSING = "missing"


class Storage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bids (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_site TEXT NOT NULL,
                    title TEXT NOT NULL,
                    region TEXT,
                    published_at TEXT,
                    source_url TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    dedupe_key TEXT NOT NULL UNIQUE,
                    is_new INTEGER NOT NULL,
                    hit_keywords TEXT,
                    manual_judgement TEXT NOT NULL DEFAULT '待确认',
                    feishu_backfilled_at TEXT,
                    created_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    source_site TEXT,
                    fetched_count INTEGER DEFAULT 0,
                    inserted_count INTEGER DEFAULT 0,
                    duplicate_count INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0,
                    note TEXT
                )
                """
            )

            for column_name, column_sql in [
                ("feishu_backfilled_at", "TEXT"),
                ("source", "TEXT"),
                ("source_subtype", "TEXT"),
                ("section_id", "TEXT"),
                ("notice_id", "TEXT"),
                ("notice_title", "TEXT"),
                ("notice_publish_time", "TEXT"),
                ("project_name", "TEXT"),
                ("section_name", "TEXT"),
                ("notice_type", "TEXT"),
                ("project_code", "TEXT"),
                ("purchaser_or_tenderer", "TEXT"),
                ("agency", "TEXT"),
                ("publish_time", "TEXT"),
                ("file_get_deadline", "TEXT"),
                ("bid_open_or_response_deadline", "TEXT"),
                ("budget_amount", "TEXT"),
                ("ceiling_price", "TEXT"),
                ("procurement_method", "TEXT"),
                ("content_summary", "TEXT"),
                ("qualification_summary", "TEXT"),
                ("accepts_consortium", "TEXT"),
                ("original_url", "TEXT"),
                ("employee_readable_url", "TEXT"),
                ("raw_api_url", "TEXT"),
                ("has_attachment", "INTEGER NOT NULL DEFAULT 0"),
                ("attachment_count", "INTEGER NOT NULL DEFAULT 0"),
                ("lead_tier", "TEXT"),
                ("lead_reason", "TEXT"),
                ("matched_positive_signals", "TEXT"),
                ("matched_negative_signals", "TEXT"),
                ("pilot_feishu_written_at", "TEXT"),
                ("pilot_webhook_sent_at", "TEXT"),
            ]:
                self._ensure_column(conn, "bids", column_name, column_sql)
            conn.commit()

    def _ensure_column(self, conn: sqlite3.Connection, table_name: str, column_name: str, column_sql: str) -> None:
        columns = [row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")]
        if column_name not in columns:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")

    def start_run(self, source_site: str) -> int:
        started_at = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO runs (started_at, status, source_site)
                VALUES (?, ?, ?)
                """,
                (started_at, "running", source_site),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def finish_run(
        self,
        run_id: int,
        status: str,
        fetched_count: int,
        inserted_count: int,
        duplicate_count: int,
        error_count: int,
        note: str = "",
    ) -> None:
        finished_at = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE runs
                SET finished_at = ?, status = ?, fetched_count = ?, inserted_count = ?,
                    duplicate_count = ?, error_count = ?, note = ?
                WHERE id = ?
                """,
                (finished_at, status, fetched_count, inserted_count, duplicate_count, error_count, note, run_id),
            )
            conn.commit()

    def save_notice(self, notice: Notice) -> bool:
        dedupe_key = build_dedupe_key(notice)
        notice.dedupe_key = dedupe_key
        now = datetime.now().isoformat(timespec="seconds")
        hit_keywords = ",".join(notice.hit_keywords)
        matched_positive_signals = " | ".join(notice.matched_positive_signals)
        matched_negative_signals = " | ".join(notice.matched_negative_signals)
        update_values = (
            notice.fetched_at,
            now,
            hit_keywords,
            notice.source,
            notice.source_subtype,
            notice.section_id,
            notice.notice_id,
            notice.notice_title,
            notice.notice_publish_time,
            notice.project_name,
            notice.section_name,
            notice.notice_type,
            notice.project_code,
            notice.purchaser_or_tenderer,
            notice.agency,
            notice.region,
            notice.publish_time,
            notice.file_get_deadline,
            notice.bid_open_or_response_deadline,
            notice.budget_amount,
            notice.ceiling_price,
            notice.procurement_method,
            notice.content_summary,
            notice.qualification_summary,
            notice.accepts_consortium,
            notice.original_url,
            notice.employee_readable_url,
            notice.raw_api_url,
            1 if notice.has_attachment else 0,
            notice.attachment_count,
            notice.lead_tier,
            notice.lead_reason,
            matched_positive_signals,
            matched_negative_signals,
            notice.manual_judgement,
            notice.title,
            notice.source_site,
            notice.published_at,
            notice.source_url,
        )

        with self._connect() as conn:
            exact_row = conn.execute(
                "SELECT id FROM bids WHERE dedupe_key = ?",
                (dedupe_key,),
            ).fetchone()
            if exact_row:
                conn.execute(
                    """
                    UPDATE bids
                    SET fetched_at = ?, last_seen_at = ?, is_new = 0,
                        hit_keywords = ?, source = ?, source_subtype = ?, section_id = ?,
                        notice_id = ?, notice_title = ?, notice_publish_time = ?,
                        project_name = ?, section_name = ?, notice_type = ?, project_code = ?,
                        purchaser_or_tenderer = ?, agency = ?, region = ?, publish_time = ?,
                        file_get_deadline = ?, bid_open_or_response_deadline = ?,
                        budget_amount = ?, ceiling_price = ?, procurement_method = ?,
                        content_summary = ?, qualification_summary = ?, accepts_consortium = ?,
                        original_url = ?, employee_readable_url = ?, raw_api_url = ?,
                        has_attachment = ?, attachment_count = ?, lead_tier = ?, lead_reason = ?,
                        matched_positive_signals = ?, matched_negative_signals = ?, manual_judgement = ?,
                        title = ?, source_site = ?, published_at = ?, source_url = ?
                    WHERE dedupe_key = ?
                    """,
                    update_values + (dedupe_key,),
                )
                conn.commit()
                return False

            legacy_row = self._find_legacy_row(conn, notice)
            if legacy_row:
                conn.execute(
                    """
                    UPDATE bids
                    SET fetched_at = ?, last_seen_at = ?, is_new = 0,
                        hit_keywords = ?, source = ?, source_subtype = ?, section_id = ?,
                        notice_id = ?, notice_title = ?, notice_publish_time = ?,
                        project_name = ?, section_name = ?, notice_type = ?, project_code = ?,
                        purchaser_or_tenderer = ?, agency = ?, region = ?, publish_time = ?,
                        file_get_deadline = ?, bid_open_or_response_deadline = ?,
                        budget_amount = ?, ceiling_price = ?, procurement_method = ?,
                        content_summary = ?, qualification_summary = ?, accepts_consortium = ?,
                        original_url = ?, employee_readable_url = ?, raw_api_url = ?,
                        has_attachment = ?, attachment_count = ?, lead_tier = ?, lead_reason = ?,
                        matched_positive_signals = ?, matched_negative_signals = ?, manual_judgement = ?,
                        title = ?, source_site = ?, published_at = ?, source_url = ?, dedupe_key = ?
                    WHERE id = ?
                    """,
                    update_values + (dedupe_key, legacy_row[0]),
                )
                conn.commit()
                return False

            conn.execute(
                """
                INSERT INTO bids (
                    source_site, title, region, published_at, source_url, fetched_at,
                    dedupe_key, is_new, hit_keywords, manual_judgement, created_at, last_seen_at,
                    source, source_subtype, section_id, notice_id, notice_title, notice_publish_time,
                    project_name, section_name, notice_type, project_code, purchaser_or_tenderer,
                    agency, publish_time, file_get_deadline, bid_open_or_response_deadline,
                    budget_amount, ceiling_price, procurement_method, content_summary,
                    qualification_summary, accepts_consortium, original_url, employee_readable_url,
                    raw_api_url, has_attachment, attachment_count, lead_tier, lead_reason,
                    matched_positive_signals, matched_negative_signals
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    notice.source_site,
                    notice.title,
                    notice.region,
                    notice.published_at,
                    notice.source_url,
                    notice.fetched_at,
                    dedupe_key,
                    1,
                    hit_keywords,
                    notice.manual_judgement,
                    now,
                    now,
                    notice.source,
                    notice.source_subtype,
                    notice.section_id,
                    notice.notice_id,
                    notice.notice_title,
                    notice.notice_publish_time,
                    notice.project_name,
                    notice.section_name,
                    notice.notice_type,
                    notice.project_code,
                    notice.purchaser_or_tenderer,
                    notice.agency,
                    notice.publish_time,
                    notice.file_get_deadline,
                    notice.bid_open_or_response_deadline,
                    notice.budget_amount,
                    notice.ceiling_price,
                    notice.procurement_method,
                    notice.content_summary,
                    notice.qualification_summary,
                    notice.accepts_consortium,
                    notice.original_url,
                    notice.employee_readable_url,
                    notice.raw_api_url,
                    1 if notice.has_attachment else 0,
                    notice.attachment_count,
                    notice.lead_tier,
                    notice.lead_reason,
                    matched_positive_signals,
                    matched_negative_signals,
                ),
            )
            conn.commit()
            return True

    def notice_exists(self, notice: Notice) -> bool:
        return self.get_notice_match_status(notice) != NoticeMatchStatus.MISSING

    def get_notice_match_status(self, notice: Notice) -> str:
        dedupe_key = build_dedupe_key(notice)
        notice.dedupe_key = dedupe_key
        with self._connect() as conn:
            exact_row = conn.execute(
                "SELECT 1 FROM bids WHERE dedupe_key = ?",
                (dedupe_key,),
            ).fetchone()
            if exact_row:
                return NoticeMatchStatus.EXACT
            if self._find_legacy_row(conn, notice) is not None:
                return NoticeMatchStatus.LEGACY
            return NoticeMatchStatus.MISSING

    def get_legacy_upgrade_snapshot(self, notice: Notice) -> dict[str, str] | None:
        dedupe_key = build_dedupe_key(notice)
        notice.dedupe_key = dedupe_key
        with self._connect() as conn:
            legacy_row = self._find_legacy_row(conn, notice)
            if legacy_row is None:
                return None
            row = conn.execute(
                """
                SELECT dedupe_key, COALESCE(notice_id, ''), COALESCE(notice_title, ''), COALESCE(notice_publish_time, '')
                FROM bids
                WHERE id = ?
                """,
                (legacy_row[0],),
            ).fetchone()
        return {
            "current_dedupe_key": str(row[0] or ""),
            "current_notice_id": str(row[1] or ""),
            "current_notice_title": str(row[2] or ""),
            "current_notice_publish_time": str(row[3] or ""),
            "upgraded_dedupe_key": dedupe_key,
        }

    def _find_legacy_row(self, conn: sqlite3.Connection, notice: Notice) -> sqlite3.Row | None:
        if not notice.section_id:
            return None
        legacy_dedupe_key = f"{notice.source_site}|{notice.section_id}"
        if legacy_dedupe_key == notice.dedupe_key:
            return None
        return conn.execute(
            """
            SELECT id
            FROM bids
            WHERE dedupe_key = ?
              AND source_site = ?
              AND section_id = ?
              AND COALESCE(notice_id, '') = ''
              AND COALESCE(notice_type, '') = ?
              AND COALESCE(publish_time, '') = ?
            LIMIT 1
            """,
            (
                legacy_dedupe_key,
                notice.source_site,
                notice.section_id,
                notice.notice_type,
                notice.notice_publish_time or notice.publish_time,
            ),
        ).fetchone()

    def get_history_stats(self) -> tuple[int, int]:
        with self._connect() as conn:
            total_count = conn.execute("SELECT COUNT(*) FROM bids").fetchone()[0]
            hit_count = conn.execute(
                "SELECT COUNT(*) FROM bids WHERE COALESCE(TRIM(hit_keywords), '') <> ''"
            ).fetchone()[0]
            return int(total_count), int(hit_count)

    def get_latest_publish_time(self, source_site: str) -> str:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT MAX(COALESCE(notice_publish_time, publish_time, published_at, ''))
                FROM bids
                WHERE source_site = ?
                """,
                (source_site,),
            ).fetchone()
        return str(row[0] or "")

    def get_pending_backfill_notices(self) -> list[Notice]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT source, source_subtype, dedupe_key, section_id, notice_id, notice_title, notice_publish_time,
                       project_name, section_name, notice_type, project_code, purchaser_or_tenderer, agency, region,
                       publish_time, file_get_deadline, bid_open_or_response_deadline, budget_amount, ceiling_price,
                       procurement_method, content_summary, qualification_summary, accepts_consortium,
                       original_url, employee_readable_url, raw_api_url, has_attachment, attachment_count,
                       fetched_at, hit_keywords, manual_judgement, source_site, title, published_at, source_url,
                       lead_tier, lead_reason, matched_positive_signals, matched_negative_signals
                FROM bids
                WHERE COALESCE(TRIM(hit_keywords), '') <> ''
                  AND feishu_backfilled_at IS NULL
                ORDER BY id
                """
            ).fetchall()
        return [self._row_to_notice(row) for row in rows]

    def mark_notice_backfilled(self, dedupe_key: str) -> None:
        self._mark_timestamp_for_keys("feishu_backfilled_at", [dedupe_key])

    def get_pilot_watchlist_candidates(self, project_names: list[str], limit: int = 4) -> list[Notice]:
        if not project_names:
            return []
        placeholders = ",".join("?" for _ in project_names)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT source, source_subtype, dedupe_key, section_id, notice_id, notice_title, notice_publish_time,
                       project_name, section_name, notice_type, project_code, purchaser_or_tenderer, agency, region,
                       publish_time, file_get_deadline, bid_open_or_response_deadline, budget_amount, ceiling_price,
                       procurement_method, content_summary, qualification_summary, accepts_consortium,
                       original_url, employee_readable_url, raw_api_url, has_attachment, attachment_count,
                       fetched_at, hit_keywords, manual_judgement, source_site, title, published_at, source_url,
                       lead_tier, lead_reason, matched_positive_signals, matched_negative_signals
                FROM bids
                WHERE lead_tier = 'WATCHLIST'
                  AND pilot_feishu_written_at IS NULL
                  AND project_name IN ({placeholders})
                """,
                project_names,
            ).fetchall()
        notices = [self._row_to_notice(row) for row in rows]
        order_map = {name: idx for idx, name in enumerate(project_names)}
        notices.sort(key=lambda notice: (order_map.get(notice.project_name, 999), notice.dedupe_key))
        return notices[:limit]

    def mark_pilot_feishu_written(self, dedupe_keys: Iterable[str]) -> None:
        self._mark_timestamp_for_keys("pilot_feishu_written_at", dedupe_keys)

    def mark_pilot_webhook_sent(self, dedupe_keys: Iterable[str]) -> None:
        self._mark_timestamp_for_keys("pilot_webhook_sent_at", dedupe_keys)

    def get_latest_notices(self, source_subtype: str, limit: int) -> list[Notice]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT source, source_subtype, dedupe_key, section_id, notice_id, notice_title, notice_publish_time,
                       project_name, section_name, notice_type, project_code, purchaser_or_tenderer, agency, region,
                       publish_time, file_get_deadline, bid_open_or_response_deadline, budget_amount, ceiling_price,
                       procurement_method, content_summary, qualification_summary, accepts_consortium,
                       original_url, employee_readable_url, raw_api_url, has_attachment, attachment_count,
                       fetched_at, hit_keywords, manual_judgement, source_site, title, published_at, source_url,
                       lead_tier, lead_reason, matched_positive_signals, matched_negative_signals
                FROM bids
                WHERE source_subtype = ?
                ORDER BY last_seen_at DESC, id DESC
                LIMIT ?
                """,
                (source_subtype, limit),
            ).fetchall()
        return [self._row_to_notice(row) for row in rows]

    def _mark_timestamp_for_keys(self, column_name: str, dedupe_keys: Iterable[str]) -> None:
        keys = [key for key in dedupe_keys if key]
        if not keys:
            return
        placeholders = ",".join("?" for _ in keys)
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                f"UPDATE bids SET {column_name} = ? WHERE dedupe_key IN ({placeholders})",
                (now, *keys),
            )
            conn.commit()

    def _row_to_notice(self, row: tuple) -> Notice:
        hit_keywords = [item.strip() for item in (row[29] or "").split(",") if item.strip()]
        matched_positive = [item.strip() for item in (row[37] or "").split("|") if item.strip()]
        matched_negative = [item.strip() for item in (row[38] or "").split("|") if item.strip()]
        return Notice(
            source=row[0] or row[31] or "",
            source_subtype=row[1] or "",
            dedupe_key=row[2] or "",
            section_id=row[3] or "",
            notice_id=row[4] or "",
            notice_title=row[5] or row[32] or "",
            notice_publish_time=row[6] or row[33] or "",
            project_name=row[7] or row[32] or "",
            section_name=row[8] or "",
            notice_type=row[9] or "",
            project_code=row[10] or "",
            purchaser_or_tenderer=row[11] or "",
            agency=row[12] or "",
            region=row[13] or "",
            publish_time=row[14] or row[33] or "",
            file_get_deadline=row[15] or "",
            bid_open_or_response_deadline=row[16] or "",
            budget_amount=row[17] or "",
            ceiling_price=row[18] or "",
            procurement_method=row[19] or "",
            content_summary=row[20] or "",
            qualification_summary=row[21] or "",
            accepts_consortium=row[22] or "",
            original_url=row[23] or row[34] or "",
            employee_readable_url=row[24] or "",
            raw_api_url=row[25] or "",
            has_attachment=bool(row[26]),
            attachment_count=int(row[27] or 0),
            fetched_at=row[28] or now_string(),
            hit_keywords=hit_keywords,
            manual_judgement=row[30] or "待确认",
            lead_tier=row[35] or "",
            lead_reason=row[36] or "",
            matched_positive_signals=matched_positive,
            matched_negative_signals=matched_negative,
            is_new=False,
        )


def now_string() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
