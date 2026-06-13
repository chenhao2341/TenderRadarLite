from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.config import load_sources
from app.dedupe import build_dedupe_key
from app.fetcher import Fetcher
from app.models import Notice
from app.runner import RunSummary, run_once
from app.storage import Storage


class FakeFetcher:
    def __init__(self, json_map: dict[str, object]) -> None:
        self.json_map = json_map

    def get_json(self, url: str):
        return self.json_map.get(url)

    def get_text(self, url: str):
        raise AssertionError(f"unexpected text fetch: {url}")


class _LocalAdapter:
    def __init__(self, notices):
        self._notices = list(notices)
        self.last_crawl_stats = {"fetched_total": len(self._notices), "detail_success_count": len(self._notices)}

    def crawl(self):
        return list(self._notices)


class ConstructionReliabilityTests(unittest.TestCase):
    def test_construction_adapter_scans_configured_pages_and_emits_notice_per_notice_item(self) -> None:
        from app.adapters.hengyang_construction import HengyangConstructionAdapter

        list_url = (
            "https://hengyang.hnsggzy.com/tradeApi/constructionTender/"
            "listByFile?regionCode=430400&current=1&size=2"
        )
        page2_url = (
            "https://hengyang.hnsggzy.com/tradeApi/constructionTender/"
            "listByFile?regionCode=430400&current=2&size=2"
        )
        fetcher = FakeFetcher(
            {
                list_url: {
                    "data": {
                        "records": [
                            {
                                "bidSectionId": "sec-1",
                                "tenderProjectType": "CONSTRUCTION",
                                "tenderProjectName": "Project One",
                                "bidSectionName": "Section One",
                                "noticeSendTime": "2026-06-12 10:00:00",
                            },
                            {
                                "bidSectionId": "sec-2",
                                "tenderProjectType": "CONSTRUCTION",
                                "tenderProjectName": "Project Two",
                                "bidSectionName": "Section Two",
                                "noticeSendTime": "2026-06-11 10:00:00",
                            },
                        ],
                        "pages": 2,
                    }
                },
                page2_url: {
                    "data": {
                        "records": [
                            {
                                "bidSectionId": "sec-3",
                                "tenderProjectType": "CONSTRUCTION",
                                "tenderProjectName": "Project Three",
                                "bidSectionName": "Section Three",
                                "noticeSendTime": "2026-06-10 10:00:00",
                            }
                        ],
                        "pages": 2,
                    }
                },
                "https://hengyang.hnsggzy.com/tradeApi/constructionTender/getBySectionId?sectionId=sec-1": {
                    "data": {
                        "constructionTender": {
                            "tenderProjectName": "Project One",
                            "tenderProjectCode": "P-1",
                            "ownerName": "Tenderer One",
                        },
                        "constructionProject": {"regionCode": "Hunan-Hengyang"},
                        "constructionSectionList": [{"bidSectionName": "Section One"}],
                    }
                },
                "https://hengyang.hnsggzy.com/tradeApi/constructionTender/getBySectionId?sectionId=sec-2": {
                    "data": {
                        "constructionTender": {
                            "tenderProjectName": "Project Two",
                            "tenderProjectCode": "P-2",
                            "ownerName": "Tenderer Two",
                        },
                        "constructionProject": {"regionCode": "Hunan-Hengyang"},
                        "constructionSectionList": [{"bidSectionName": "Section Two"}],
                    }
                },
                "https://hengyang.hnsggzy.com/tradeApi/constructionTender/getBySectionId?sectionId=sec-3": {
                    "data": {
                        "constructionTender": {
                            "tenderProjectName": "Project Three",
                            "tenderProjectCode": "P-3",
                            "ownerName": "Tenderer Three",
                        },
                        "constructionProject": {"regionCode": "Hunan-Hengyang"},
                        "constructionSectionList": [{"bidSectionName": "Section Three"}],
                    }
                },
                "https://hengyang.hnsggzy.com/tradeApi/constructionNotice/getBySectionId?sectionId=sec-1": {
                    "data": {
                        "noticeList": [
                            {
                                "id": "notice-1",
                                "noticeName": "Project One Notice",
                                "bulletinType": "ZHAOBIAO_NOTICE",
                                "noticeSendTime": "2026-06-12 10:00:00",
                                "noticeContent": "<p>content one</p>",
                            }
                        ]
                    }
                },
                "https://hengyang.hnsggzy.com/tradeApi/constructionNotice/getBySectionId?sectionId=sec-2": {
                    "data": {
                        "noticeList": [
                            {
                                "id": "notice-2a",
                                "noticeName": "Project Two Clarification",
                                "bulletinType": "CHENGQING_NOTICE",
                                "noticeSendTime": "2026-06-11 10:00:00",
                                "noticeContent": "<p>clarification</p>",
                            },
                            {
                                "id": "notice-2b",
                                "noticeName": "Project Two Correction",
                                "bulletinType": "GENGZHENG_NOTICE",
                                "noticeSendTime": "2026-06-11 12:00:00",
                                "noticeContent": "<p>correction</p>",
                            },
                        ]
                    }
                },
                "https://hengyang.hnsggzy.com/tradeApi/constructionNotice/getBySectionId?sectionId=sec-3": {
                    "data": {
                        "noticeList": [
                            {
                                "noticeName": "Project Three Notice",
                                "bulletinType": "ZHAOBIAO_NOTICE",
                                "noticeSendTime": "2026-06-10 10:00:00",
                                "noticeContent": "<p>content three</p>",
                            }
                        ]
                    }
                },
                "https://hengyang.hnsggzy.com/tradeApi/attach/proxy/getFileListBySectionId?sectionId=sec-1": {"data": []},
                "https://hengyang.hnsggzy.com/tradeApi/attach/proxy/getFileListBySectionId?sectionId=sec-2": {"data": []},
                "https://hengyang.hnsggzy.com/tradeApi/attach/proxy/getFileListBySectionId?sectionId=sec-3": {"data": []},
            }
        )

        adapter = HengyangConstructionAdapter(
            source_name="construction",
            url=list_url,
            region="Hengyang",
            fetcher=fetcher,
            source_config={"pages_scanned": 2, "page_size": 2},
        )

        notices = adapter.crawl()

        self.assertEqual(len(notices), 4)
        self.assertEqual(adapter.last_crawl_stats["pages_scanned"], 2)
        self.assertEqual(adapter.last_crawl_stats["page_size"], 2)
        self.assertEqual(adapter.last_crawl_stats["list_count"], 3)
        self.assertEqual(adapter.last_crawl_stats["detail_success_count"], 4)
        self.assertEqual(adapter.last_crawl_stats["real_notice_count"], 4)
        self.assertEqual(notices[1].notice_id, "notice-2a")
        self.assertEqual(notices[2].notice_id, "notice-2b")
        self.assertNotIn("<bidSectionId>", notices[0].employee_readable_url)
        self.assertIn("bidSectionId=sec-2", notices[1].employee_readable_url)


class DedupeRuleTests(unittest.TestCase):
    def test_build_dedupe_key_prefers_notice_id_then_notice_type_and_time(self) -> None:
        with_notice_id = Notice(
            source="source",
            source_subtype="construction",
            dedupe_key="",
            section_id="section-1",
            project_name="Project",
            notice_id="notice-1",
            notice_type="ZHAOBIAO_NOTICE",
            notice_publish_time="2026-06-12 10:00:00",
        )
        without_notice_id = Notice(
            source="source",
            source_subtype="construction",
            dedupe_key="",
            section_id="section-1",
            project_name="Project",
            notice_type="GENGZHENG_NOTICE",
            notice_publish_time="2026-06-12 11:00:00",
        )

        self.assertEqual(
            build_dedupe_key(with_notice_id),
            "source-construction|section-1|notice-1",
        )
        self.assertEqual(
            build_dedupe_key(without_notice_id),
            "source-construction|section-1|GENGZHENG_NOTICE|2026-06-12 11:00:00",
        )


class StorageCompatibilityTests(unittest.TestCase):
    def test_storage_upgrades_legacy_section_level_record_without_duplicate_insert(self) -> None:
        fd, raw_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        db_path = Path(raw_path)
        try:
            storage = Storage(db_path)
            legacy_notice = Notice(
                source="source",
                source_subtype="construction",
                dedupe_key="source-construction|section-1",
                section_id="section-1",
                project_name="Project",
                notice_type="ZHAOBIAO_NOTICE",
                publish_time="2026-06-12 10:00:00",
                fetched_at="2026-06-12 10:05:00",
            )
            self.assertTrue(storage.save_notice(legacy_notice))

            same_notice = Notice(
                source="source",
                source_subtype="construction",
                dedupe_key="source-construction|section-1|notice-1",
                section_id="section-1",
                project_name="Project",
                notice_id="notice-1",
                notice_title="Project Notice",
                notice_type="ZHAOBIAO_NOTICE",
                notice_publish_time="2026-06-12 10:00:00",
                publish_time="2026-06-12 10:00:00",
                fetched_at="2026-06-13 10:05:00",
            )
            self.assertFalse(storage.save_notice(same_notice))

            different_notice = Notice(
                source="source",
                source_subtype="construction",
                dedupe_key="source-construction|section-1|notice-2",
                section_id="section-1",
                project_name="Project",
                notice_id="notice-2",
                notice_title="Project Correction",
                notice_type="GENGZHENG_NOTICE",
                notice_publish_time="2026-06-12 12:00:00",
                publish_time="2026-06-12 12:00:00",
                fetched_at="2026-06-13 10:10:00",
            )
            self.assertTrue(storage.save_notice(different_notice))

            conn = sqlite3.connect(db_path)
            try:
                rows = conn.execute(
                    "select dedupe_key, notice_id, notice_type, publish_time from bids order by id"
                ).fetchall()
            finally:
                conn.close()

            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0][0], "source-construction|section-1|notice-1")
            self.assertEqual(rows[0][1], "notice-1")
            self.assertEqual(rows[1][0], "source-construction|section-1|notice-2")
        finally:
            try:
                os.remove(db_path)
            except PermissionError:
                pass


class FetcherBehaviorTests(unittest.TestCase):
    def test_fetcher_bypasses_system_proxy_env(self) -> None:
        fetcher = Fetcher(mock.Mock())
        self.assertFalse(fetcher.session.trust_env)


class MainExitCodeTests(unittest.TestCase):
    def test_main_returns_non_zero_when_all_enabled_sources_fail(self) -> None:
        from app.main import main

        failed = [
            RunSummary(
                source_name="construction",
                fetched_count=0,
                inserted_count=0,
                duplicate_count=0,
                pushed_count=0,
                error_count=1,
                fetch_failed=True,
            )
        ]

        with mock.patch("app.main.run_once", return_value=failed):
            exit_code = main([])

        self.assertNotEqual(exit_code, 0)

    def test_main_returns_zero_when_any_enabled_source_succeeds(self) -> None:
        from app.main import main

        results = [
            RunSummary(
                source_name="construction",
                fetched_count=30,
                inserted_count=0,
                duplicate_count=30,
                pushed_count=0,
                error_count=0,
                fetch_failed=False,
            )
        ]

        with mock.patch("app.main.run_once", return_value=results):
            exit_code = main([])

        self.assertEqual(exit_code, 0)


class OptionalFeishuOutputTests(unittest.TestCase):
    def test_run_once_keeps_local_flow_when_feishu_env_is_missing(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        (temp_dir / "logs").mkdir(parents=True, exist_ok=True)
        source = {
            "name": "Hengyang Construction",
            "enabled": True,
            "module": "unused",
            "class": "unused",
            "url": "https://example.com",
            "region": "Hengyang",
            "source": "衡阳分平台",
            "source_subtype": "建设工程交易",
        }
        notice = Notice(
            source="衡阳分平台",
            source_subtype="建设工程交易",
            dedupe_key="",
            section_id="sec-1",
            project_name="Design Project",
            notice_id="notice-1",
            notice_title="Design Project Notice",
            notice_type="ZHAOBIAO_NOTICE",
            notice_publish_time="2026-06-12 10:00:00",
            publish_time="2026-06-12 10:00:00",
            content_summary="设计服务",
            original_url="https://example.com/detail",
            fetched_at="2026-06-13 12:00:00",
        )

        with (
            mock.patch("app.runner.DATA_DIR", temp_dir / "data"),
            mock.patch("app.runner.REPORT_DIR", temp_dir / "reports"),
            mock.patch("app.logging_utils.LOG_DIR", temp_dir / "logs"),
            mock.patch("app.runner.load_sources", return_value=[source]),
            mock.patch("app.runner._build_adapter", return_value=_LocalAdapter([notice])),
            mock.patch("app.runner.FeishuClient") as feishu_client,
            mock.patch.dict(
                os.environ,
                {
                    "FEISHU_APP_ID": "",
                    "FEISHU_APP_SECRET": "",
                    "FEISHU_BITABLE_URL": "",
                    "FEISHU_WEBHOOK_URL": "",
                    "FEISHU_BITABLE_APP_TOKEN": "",
                    "FEISHU_BITABLE_TABLE_ID": "",
                },
                clear=False,
            ),
        ):
            feishu_client.return_value.has_any_output.return_value = False
            results = run_once(enable_feishu=True)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].inserted_count, 1)
        self.assertEqual(results[0].feishu_written_count, 0)
        self.assertEqual(results[0].webhook_sent_count, 0)
        feishu_client.return_value.write_notice.assert_not_called()
        feishu_client.return_value.send_summary.assert_not_called()


class SourceConfigTests(unittest.TestCase):
    def test_procurement_source_is_disabled_in_formal_run(self) -> None:
        sources = load_sources()
        procurement = next(source for source in sources if source["class"] == "HengyangProcurementAdapter")
        construction = next(source for source in sources if source["class"] == "HengyangConstructionAdapter")

        self.assertFalse(procurement["enabled"])
        self.assertEqual(construction["pages_scanned"], 3)
        self.assertEqual(construction["page_size"], 10)


if __name__ == "__main__":
    unittest.main()
