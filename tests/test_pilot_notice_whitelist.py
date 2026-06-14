from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.models import Notice
from app.runner import backfill_feishu, reset_pilot_sync_state, run_pilot_notice_whitelist
from app.storage import NoticeMatchStatus, Storage


class _FakeAdapter:
    def __init__(self, notices):
        self._notices = notices

    def crawl(self):
        return list(self._notices)


class _FakeFeishuClient:
    instances = []

    def __init__(self, logger):
        self.logger = logger
        self.written = []
        self.summaries = []
        self.schema_inited = False
        type(self).instances.append(self)

    def init_schema(self):
        self.schema_inited = True

    def write_notice(self, notice, **kwargs):
        self.written.append((notice.notice_id, kwargs))
        return True

    def send_summary(self, notices, **kwargs):
        self.summaries.append([notice.notice_id for notice in notices])
        return True

    def can_write_bitable(self):
        return True

    def can_send_webhook(self):
        return False

    def can_send_app_bot(self):
        return True

    def has_any_output(self):
        return True


def _make_notice(
    *,
    notice_id: str,
    section_id: str,
    notice_type: str,
    project_name: str,
    lead_signal: str = "",
    negative_signal: str = "",
) -> Notice:
    notice = Notice(
        source="衡阳分平台",
        source_subtype="建设工程交易",
        dedupe_key="",
        section_id=section_id,
        project_name=project_name,
        notice_id=notice_id,
        notice_title=project_name,
        notice_publish_time="2026-06-12 10:00:00",
        section_name=project_name,
        notice_type=notice_type,
        publish_time="2026-06-12 10:00:00",
        content_summary=lead_signal,
        qualification_summary=negative_signal,
        employee_readable_url=f"https://example.com/detail?bidSectionId={section_id}",
        raw_api_url=f"https://example.com/api?sectionId={section_id}",
        fetched_at="2026-06-13 12:00:00",
    )
    return notice


class PilotNoticeWhitelistTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.root, ignore_errors=True))
        self.data_dir = self.root / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.notice_file = self.root / "pilot_notice_ids.json"
        self.notice_file.write_text(
            json.dumps(
                {
                    "notice_ids": [
                        "direct-1",
                        "direct-2",
                        "watch-1",
                        "exclude-1",
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.notices = [
            _make_notice(
                notice_id="direct-1",
                section_id="sec-1",
                notice_type="ZHAOBIAO_NOTICE",
                project_name="Direct Design Project",
                lead_signal="设计服务",
            ),
            _make_notice(
                notice_id="direct-2",
                section_id="sec-1",
                notice_type="ZANTING_NOTICE",
                project_name="Direct Design Project",
                lead_signal="设计服务",
            ),
            _make_notice(
                notice_id="watch-1",
                section_id="sec-2",
                notice_type="ZHAOBIAO_NOTICE",
                project_name="Watchlist Renovation Project",
                lead_signal="改造",
                negative_signal="施工总承包 安全生产许可证",
            ),
            _make_notice(
                notice_id="exclude-1",
                section_id="sec-3",
                notice_type="ZHAOBIAO_NOTICE",
                project_name="Elevator Purchase Project",
                lead_signal="电梯采购",
            ),
            _make_notice(
                notice_id="other-1",
                section_id="sec-9",
                notice_type="ZHAOBIAO_NOTICE",
                project_name="Other Project",
                lead_signal="设计服务",
            ),
        ]

    def _run(self, *, execute: bool):
        _FakeFeishuClient.instances.clear()
        source = {
            "name": "P0-1",
            "enabled": True,
            "module": "unused",
            "class": "unused",
            "url": "https://example.com",
            "region": "衡阳",
            "source": "衡阳分平台",
            "source_subtype": "建设工程交易",
        }
        with (
            mock.patch("app.runner.DATA_DIR", self.data_dir),
            mock.patch("app.runner.load_sources", return_value=[source]),
            mock.patch("app.runner._build_adapter", return_value=_FakeAdapter(self.notices)),
            mock.patch("app.runner.FeishuClient", _FakeFeishuClient),
        ):
            return run_pilot_notice_whitelist(self.notice_file, execute=execute)

    def test_dry_run_filters_to_whitelist_without_side_effects(self) -> None:
        result = self._run(execute=False)
        self.assertEqual(result.notice_ids_total, 4)
        self.assertEqual(result.matched_count, 4)
        self.assertEqual(result.non_whitelist_scanned_count, 1)
        self.assertEqual(result.non_whitelist_written_count, 0)
        self.assertEqual(result.sqlite_inserted_count, 0)
        self.assertEqual(result.feishu_written_count, 0)
        self.assertEqual(result.webhook_sent_count, 0)
        self.assertEqual([item.notice_id for item in result.records], ["direct-1", "direct-2", "watch-1", "exclude-1"])
        self.assertTrue(all(item.will_insert_sqlite for item in result.records))
        self.assertEqual(len(_FakeFeishuClient.instances), 0)

        db_path = self.data_dir / "bids.db"
        storage = Storage(db_path)
        self.assertEqual(storage.get_history_stats()[0], 0)

    def test_execute_writes_only_whitelist_and_is_idempotent(self) -> None:
        first = self._run(execute=True)
        self.assertEqual(first.sqlite_inserted_count, 4)
        self.assertEqual(first.feishu_written_count, 3)
        self.assertEqual(first.webhook_sent_count, 1)
        self.assertEqual(first.direct_count, 2)
        self.assertEqual(first.watchlist_count, 1)
        self.assertEqual(first.exclude_count, 1)
        self.assertEqual(first.bot_notice_ids, ["direct-1", "direct-2"])
        self.assertEqual(len(_FakeFeishuClient.instances), 1)
        self.assertEqual(len(_FakeFeishuClient.instances[0].written), 3)

        db_path = self.data_dir / "bids.db"
        conn = Storage(db_path)._connect()
        try:
            saved_notice_ids = [row[0] for row in conn.execute("SELECT notice_id FROM bids ORDER BY id").fetchall()]
            saved_dedupe_keys = [row[0] for row in conn.execute("SELECT dedupe_key FROM bids WHERE section_id = 'sec-1' ORDER BY id").fetchall()]
        finally:
            conn.close()
        self.assertEqual(saved_notice_ids, ["direct-1", "direct-2", "watch-1", "exclude-1"])
        self.assertEqual(len(saved_dedupe_keys), 2)
        self.assertNotEqual(saved_dedupe_keys[0], saved_dedupe_keys[1])
        self.assertTrue(all("other-1" not in key for key in saved_dedupe_keys))

        second = self._run(execute=True)
        self.assertEqual(second.existing_count, 4)
        self.assertEqual(second.sqlite_inserted_count, 0)
        self.assertEqual(second.feishu_written_count, 0)
        self.assertEqual(second.webhook_sent_count, 0)
        self.assertEqual(second.non_whitelist_written_count, 0)
        self.assertEqual(len(_FakeFeishuClient.instances), 1)
        self.assertEqual(len(_FakeFeishuClient.instances[0].written), 0)
        self.assertEqual(len(_FakeFeishuClient.instances[0].summaries), 0)

        storage = Storage(db_path)
        conn = storage._connect()
        try:
            sync_rows = conn.execute(
                """
                SELECT notice_id, pilot_feishu_written_at IS NOT NULL, pilot_webhook_sent_at IS NOT NULL
                FROM bids
                ORDER BY id
                """
            ).fetchall()
        finally:
            conn.close()
        self.assertEqual(
            sync_rows,
            [
                ("direct-1", 1, 1),
                ("direct-2", 1, 1),
                ("watch-1", 1, 0),
                ("exclude-1", 0, 0),
            ],
        )

    def test_execute_upgrades_legacy_row_in_place_without_side_effects(self) -> None:
        db_path = self.data_dir / "bids.db"
        storage = Storage(db_path)
        legacy_notice = _make_notice(
            notice_id="",
            section_id="sec-1",
            notice_type="ZANTING_NOTICE",
            project_name="Direct Design Project",
            lead_signal="设计服务",
        )
        legacy_notice.notice_publish_time = ""
        legacy_notice.notice_title = ""
        legacy_notice.publish_time = "2026-06-12 10:00:00"
        legacy_notice.dedupe_key = "衡阳分平台-建设工程交易|sec-1"
        self.assertTrue(storage.save_notice(legacy_notice))

        _FakeFeishuClient.instances.clear()
        source = {
            "name": "P0-1",
            "enabled": True,
            "module": "unused",
            "class": "unused",
            "url": "https://example.com",
            "region": "衡阳",
            "source": "衡阳分平台",
            "source_subtype": "建设工程交易",
        }
        with (
            mock.patch("app.runner.DATA_DIR", self.data_dir),
            mock.patch("app.runner.load_sources", return_value=[source]),
            mock.patch("app.runner._build_adapter", return_value=_FakeAdapter(self.notices)),
            mock.patch("app.runner.FeishuClient", _FakeFeishuClient),
        ):
            dry = run_pilot_notice_whitelist(self.notice_file, execute=False)
            legacy_record = next(item for item in dry.records if item.notice_id == "direct-2")
            self.assertEqual(legacy_record.match_status, NoticeMatchStatus.LEGACY)
            self.assertEqual(legacy_record.legacy_current_dedupe_key, "衡阳分平台-建设工程交易|sec-1")
            self.assertEqual(legacy_record.legacy_current_notice_id, "")
            self.assertTrue(legacy_record.will_upgrade_legacy)
            self.assertFalse(legacy_record.will_insert_sqlite)
            self.assertFalse(legacy_record.will_write_feishu)
            self.assertFalse(legacy_record.will_send_bot)

            execute = run_pilot_notice_whitelist(self.notice_file, execute=True)
            self.assertEqual(execute.sqlite_inserted_count, 3)
            self.assertEqual(execute.feishu_written_count, 2)
            self.assertEqual(execute.webhook_sent_count, 1)

        conn = storage._connect()
        try:
            rows = conn.execute(
                "SELECT notice_id, notice_title, notice_publish_time, dedupe_key FROM bids WHERE section_id='sec-1' ORDER BY id"
            ).fetchall()
        finally:
            conn.close()

        self.assertEqual(len(rows), 2)
        upgraded_row = next(row for row in rows if row[0] == "direct-2")
        self.assertEqual(upgraded_row[1], "Direct Design Project")
        self.assertEqual(upgraded_row[2], "2026-06-12 10:00:00")
        self.assertEqual(upgraded_row[3], "衡阳分平台-建设工程交易|sec-1|direct-2")


class PilotNoticeWhitelistMainTests(unittest.TestCase):
    def test_main_uses_dry_run_by_default_for_pilot_file(self) -> None:
        from app.main import main

        with mock.patch("app.main.run_pilot_notice_whitelist") as run_pilot:
            run_pilot.return_value = mock.Mock(
                execute=False,
                records=[],
                notice_ids_total=0,
                matched_count=0,
                missing_notice_ids=[],
                existing_count=0,
                sqlite_inserted_count=0,
                feishu_written_count=0,
                webhook_sent_count=0,
                direct_count=0,
                watchlist_count=0,
                exclude_count=0,
                non_whitelist_scanned_count=0,
                non_whitelist_written_count=0,
                bot_notice_ids=[],
            )
            exit_code = main(["--pilot-notice-ids-file", "examples\\pilot_notice_ids.local.json"])

        self.assertEqual(exit_code, 0)
        run_pilot.assert_called_once_with("examples\\pilot_notice_ids.local.json", execute=False)

    def test_main_requires_file_for_execute(self) -> None:
        from app.main import main

        with self.assertRaises(SystemExit):
            main(["--execute"])

    def test_main_allows_backfill_with_pilot_file(self) -> None:
        from app.main import main

        with mock.patch("app.main.backfill_feishu") as backfill:
            backfill.return_value = mock.Mock(
                total_history_count=2,
                hit_history_count=2,
                eligible_count=2,
                written_count=2,
                notified=True,
                duplicate_notice_sent=False,
                bot_sent_count=1,
            )
            exit_code = main(["--backfill-feishu", "--pilot-notice-ids-file", "examples\\pilot_notice_ids.local.json"])

        self.assertEqual(exit_code, 0)
        backfill.assert_called_once_with("examples\\pilot_notice_ids.local.json")

    def test_main_resets_pilot_sync_state_with_pilot_file(self) -> None:
        from app.main import main

        with mock.patch("app.main.reset_pilot_sync_state") as reset_sync:
            reset_sync.return_value = mock.Mock(targeted_count=2, reset_count=2)
            exit_code = main(["--reset-pilot-sync-state", "--pilot-notice-ids-file", "examples\\pilot_notice_ids.local.json"])

        self.assertEqual(exit_code, 0)
        reset_sync.assert_called_once_with("examples\\pilot_notice_ids.local.json")


class PilotNoticeWhitelistBackfillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.root, ignore_errors=True))
        self.data_dir = self.root / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.notice_file = self.root / "pilot_notice_ids.json"
        self.notice_file.write_text(
            json.dumps({"notice_ids": ["direct-1", "watch-1"]}, ensure_ascii=False),
            encoding="utf-8",
        )

        self.direct_notice = _make_notice(
            notice_id="direct-1",
            section_id="sec-1",
            notice_type="ZHAOBIAO_NOTICE",
            project_name="Direct Design Project",
            lead_signal="设计服务",
        )
        self.watch_notice = _make_notice(
            notice_id="watch-1",
            section_id="sec-2",
            notice_type="ZHAOBIAO_NOTICE",
            project_name="Watchlist Renovation Project",
            lead_signal="改造",
            negative_signal="施工总承包",
        )
        self.direct_notice.hit_keywords = ["设计服务"]
        self.direct_notice.lead_tier = "DIRECT"
        self.direct_notice.lead_reason = "direct"
        self.watch_notice.hit_keywords = ["改造"]
        self.watch_notice.lead_tier = "WATCHLIST"
        self.watch_notice.lead_reason = "watch"
        storage = Storage(self.data_dir / "bids.db")
        self.assertTrue(storage.save_notice(self.direct_notice))
        self.assertTrue(storage.save_notice(self.watch_notice))

    def _backfill(self):
        _FakeFeishuClient.instances.clear()
        with (
            mock.patch("app.runner.DATA_DIR", self.data_dir),
            mock.patch("app.runner.FeishuClient", _FakeFeishuClient),
        ):
            return backfill_feishu(self.notice_file)

    def test_backfill_whitelist_repairs_half_success_once(self) -> None:
        first = self._backfill()
        self.assertEqual(first.eligible_count, 2)
        self.assertEqual(first.written_count, 2)
        self.assertEqual(first.bot_sent_count, 1)
        self.assertTrue(first.notified)
        self.assertEqual(len(_FakeFeishuClient.instances), 1)
        self.assertEqual([item[0] for item in _FakeFeishuClient.instances[0].written], ["direct-1", "watch-1"])
        self.assertEqual(_FakeFeishuClient.instances[0].summaries, [["direct-1"]])

        conn = Storage(self.data_dir / "bids.db")._connect()
        try:
            rows = conn.execute(
                """
                SELECT notice_id, pilot_feishu_written_at IS NOT NULL, pilot_webhook_sent_at IS NOT NULL
                FROM bids
                ORDER BY id
                """
            ).fetchall()
        finally:
            conn.close()
        self.assertEqual(rows, [("direct-1", 1, 1), ("watch-1", 1, 0)])

        second = self._backfill()
        self.assertEqual(second.eligible_count, 0)
        self.assertEqual(second.written_count, 0)
        self.assertEqual(second.bot_sent_count, 0)
        self.assertFalse(second.notified)
        self.assertEqual(len(_FakeFeishuClient.instances), 1)
        self.assertEqual(_FakeFeishuClient.instances[0].written, [])
        self.assertEqual(_FakeFeishuClient.instances[0].summaries, [])

    def test_backfill_whitelist_does_not_require_hit_keywords(self) -> None:
        conn = Storage(self.data_dir / "bids.db")._connect()
        try:
            conn.execute("UPDATE bids SET hit_keywords = ''")
            conn.commit()
        finally:
            conn.close()

        result = self._backfill()
        self.assertEqual(result.eligible_count, 2)
        self.assertEqual(result.written_count, 2)
        self.assertEqual(result.bot_sent_count, 1)

    def test_reset_pilot_sync_state_only_affects_whitelist(self) -> None:
        other_notice = _make_notice(
            notice_id="other-2",
            section_id="sec-9",
            notice_type="ZHAOBIAO_NOTICE",
            project_name="Other Project",
            lead_signal="设计服务",
        )
        other_notice.lead_tier = "DIRECT"
        other_notice.lead_reason = "other"
        storage = Storage(self.data_dir / "bids.db")
        self.assertTrue(storage.save_notice(other_notice))

        conn = storage._connect()
        try:
            conn.execute(
                """
                UPDATE bids
                SET pilot_feishu_written_at = '2026-06-15T10:00:00',
                    pilot_webhook_sent_at = '2026-06-15T10:00:00'
                """
            )
            conn.commit()
        finally:
            conn.close()

        with mock.patch("app.runner.DATA_DIR", self.data_dir):
            result = reset_pilot_sync_state(self.notice_file)

        self.assertEqual(result.targeted_count, 2)
        self.assertEqual(result.reset_count, 2)

        conn = storage._connect()
        try:
            rows = conn.execute(
                """
                SELECT notice_id, pilot_feishu_written_at IS NULL, pilot_webhook_sent_at IS NULL
                FROM bids
                ORDER BY id
                """
            ).fetchall()
        finally:
            conn.close()

        self.assertEqual(
            rows,
            [
                ("direct-1", 1, 1),
                ("watch-1", 1, 1),
                ("other-2", 0, 0),
            ],
        )


if __name__ == "__main__":
    unittest.main()
