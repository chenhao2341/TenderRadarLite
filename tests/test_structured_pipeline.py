from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.feishu import OFFICIAL_PLATFORM_URL, SCHEMA_FIELDS, FeishuClient
from app.models import Notice
from app.storage import Storage


class FakeFetcher:
    def __init__(self, json_map: dict[str, object]) -> None:
        self.json_map = json_map

    def get_json(self, url: str):
        return self.json_map[url]

    def get_text(self, url: str):
        raise AssertionError(f"unexpected text fetch: {url}")


class StructuredStorageTests(unittest.TestCase):
    def test_storage_migrates_and_saves_structured_notice(self) -> None:
        fd, raw_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        db_path = Path(raw_path)
        try:
            storage = Storage(db_path)
            notice = Notice(
                source="source",
                source_subtype="construction",
                dedupe_key="source|section-1",
                section_id="section-1",
                project_name="Example Project",
                section_name="Section A",
                notice_type="Tender Notice",
                project_code="CODE-001",
                purchaser_or_tenderer="Tenderer A",
                agency="Agency A",
                region="Hengyang",
                publish_time="2026-06-11 10:00:00",
                file_get_deadline="2026-06-20 17:00:00",
                bid_open_or_response_deadline="2026-06-30 09:00:00",
                budget_amount="1000",
                ceiling_price="900",
                procurement_method="Open Tender",
                content_summary="content summary",
                qualification_summary="qualification summary",
                accepts_consortium="No",
                original_url="https://example.com/detail",
                employee_readable_url="https://example.com/detail",
                raw_api_url="https://example.com/api",
                has_attachment=True,
                attachment_count=2,
                fetched_at="2026-06-11 11:00:00",
                hit_keywords=["design"],
                lead_tier="WATCHLIST",
                lead_reason="has follow-up value but is still construction-led",
                matched_positive_signals=["renovation"],
                matched_negative_signals=["general construction"],
            )

            self.assertTrue(storage.save_notice(notice))

            conn = sqlite3.connect(db_path)
            try:
                columns = [row[1] for row in conn.execute("PRAGMA table_info(bids)")]
                self.assertIn("employee_readable_url", columns)
                self.assertIn("raw_api_url", columns)
                row = conn.execute(
                    """
                    SELECT employee_readable_url, raw_api_url, lead_tier, lead_reason
                    FROM bids
                    """
                ).fetchone()
            finally:
                conn.close()

            self.assertEqual(row[0], "https://example.com/detail")
            self.assertEqual(row[1], "https://example.com/api")
            self.assertEqual(row[2], "WATCHLIST")
            self.assertIn("construction-led", row[3])
        finally:
            try:
                os.remove(db_path)
            except PermissionError:
                pass


class AdapterBehaviorTests(unittest.TestCase):
    def test_procurement_adapter_skips_sections_without_real_notice(self) -> None:
        from app.adapters.hengyang_procurement import HengyangProcurementAdapter

        list_url = (
            "https://hengyang.hnsggzy.com/tradeApi/governmentPurchase/"
            "projectInformation/selectAll?regionCode=430400&current=1&size=10"
        )
        project_url_1 = (
            "https://hengyang.hnsggzy.com/tradeApi/governmentPurchase/projectInformation/"
            "getBySectionId?sectionId=sec-1"
        )
        project_url_2 = (
            "https://hengyang.hnsggzy.com/tradeApi/governmentPurchase/projectInformation/"
            "getBySectionId?sectionId=sec-2"
        )
        ann_url_1 = (
            "https://hengyang.hnsggzy.com/tradeApi/governmentPurchase/projectInformation/"
            "getAnnouncementBySectionId?sectionId=sec-1"
        )
        ann_url_2 = (
            "https://hengyang.hnsggzy.com/tradeApi/governmentPurchase/projectInformation/"
            "getAnnouncementBySectionId?sectionId=sec-2"
        )
        fetcher = FakeFetcher(
            {
                list_url: {
                    "data": {
                        "records": [
                            {
                                "bidSectionId": "sec-1",
                                "projectId": "proj-1",
                                "purchaseProjectName": "Project One",
                                "purchaseSectionName": "Package One",
                                "regionName": "Hengyang",
                                "noticeType": "ZHAOBIAO_NOTICE",
                            },
                            {
                                "bidSectionId": "sec-2",
                                "projectId": "proj-2",
                                "purchaseProjectName": "Project Two",
                                "purchaseSectionName": "Package Two",
                                "regionName": "Hengyang",
                                "noticeType": None,
                            },
                        ]
                    }
                },
                project_url_1: {
                    "data": {
                        "governmentProcurementProjectInformation": {
                            "purchaseProjectName": "Project One",
                            "purchaseProjectCode": "PC-1",
                            "purchaserName": "Purchaser One",
                            "purchaserAgencyName": "Agency One",
                            "programBudget": "100",
                            "regionCode": "430400",
                        },
                        "GovernmentProcureSectionInformationList": [
                            {
                                "id": "sec-1",
                                "purchaseSectionName": "Package One",
                                "tenderType": "Competitive Negotiation",
                                "sectionBudget": "100",
                            }
                        ],
                        "GovernmentPurchaseFile": [],
                    }
                },
                project_url_2: {
                    "data": {
                        "governmentProcurementProjectInformation": {
                            "purchaseProjectName": "Project Two",
                            "purchaseProjectCode": "PC-2",
                        },
                        "GovernmentProcureSectionInformationList": [{"id": "sec-2", "purchaseSectionName": "Package Two"}],
                        "GovernmentPurchaseFile": [],
                    }
                },
                ann_url_1: {
                    "code": 200,
                    "data": {
                        "governmentProcureAnnouncementInformation": [
                            {
                                "noticeName": "Project One competitive negotiation notice",
                                "bulletinType": "Tender Notice",
                                "noticeSendTime": "2026-06-11T10:00:00.000+08:00",
                                "noticeContent": (
                                    "<p>Procurement project: Project One</p>"
                                    "<p>Consortium supported: No</p>"
                                ),
                            }
                        ]
                    },
                },
                ann_url_2: {"code": 400, "msg": "no notice", "data": None},
            }
        )

        adapter = HengyangProcurementAdapter(
            source_name="procurement",
            url=list_url,
            region="Hengyang",
            fetcher=fetcher,
        )
        notices = adapter.crawl()
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0].section_id, "sec-1")
        self.assertEqual(notices[0].project_code, "PC-1")
        self.assertEqual(notices[0].procurement_method, "Competitive Negotiation")

    def test_construction_adapter_builds_hash_detail_url(self) -> None:
        from app.adapters.hengyang_construction import HengyangConstructionAdapter

        list_url = (
            "https://hengyang.hnsggzy.com/tradeApi/constructionTender/"
            "listByFile?regionCode=430400&current=1&size=10"
        )
        section_id = "sec-1"
        fetcher = FakeFetcher(
            {
                list_url: {
                    "data": {
                        "records": [
                            {
                                "bidSectionId": section_id,
                                "regionCode": "430400",
                                "tenderProjectType": "CONSTRUCTION",
                                "noticeType": "ZHAOBIAO_NOTICE",
                                "name": "Hengyang",
                                "tenderProjectName": "Example Construction",
                                "bidSectionName": "Section A",
                                "noticeSendTime": "2026-06-11 10:00:00",
                            }
                        ]
                    }
                },
                f"https://hengyang.hnsggzy.com/tradeApi/constructionTender/getBySectionId?sectionId={section_id}": {
                    "data": {
                        "constructionTender": {
                            "id": "tender-1",
                            "tenderProjectName": "Example Construction",
                            "tenderProjectCode": "P-1",
                            "ownerName": "Tenderer A",
                            "tenderAgencyName": "Agency A",
                            "tenderMode": "Open Tender",
                        },
                        "constructionProject": {"regionCode": "Hunan-Hengyang-Hengnan"},
                        "constructionSectionList": [
                            {
                                "bidSectionName": "Section A",
                                "contractReckonPrice": 100,
                                "tenderControlPrice": 90,
                            }
                        ],
                    }
                },
                f"https://hengyang.hnsggzy.com/tradeApi/constructionNotice/getBySectionId?sectionId={section_id}": {
                    "data": {
                        "noticeList": [
                            {
                                "bulletinType": "Tender Notice",
                                "noticeSendTime": "2026-06-11 10:00:00",
                                "noticeContent": (
                                    "<p>Project overview: example construction</p>"
                                    "<p>Qualification: required</p>"
                                ),
                                "docGetEndTime": "2026-06-20 17:00:00",
                                "bidOpeningTimeStart": "2026-06-30 09:00:00",
                            }
                        ]
                    }
                },
                f"https://hengyang.hnsggzy.com/tradeApi/attach/proxy/getFileListBySectionId?sectionId={section_id}": {
                    "data": []
                },
            }
        )

        adapter = HengyangConstructionAdapter(
            source_name="construction",
            url=list_url,
            region="Hengyang",
            fetcher=fetcher,
        )
        notices = adapter.crawl()
        self.assertEqual(len(notices), 1)
        self.assertEqual(
            notices[0].employee_readable_url,
            "https://hengyang.hnsggzy.com/#/resources/transactionDetail/construction?bidSectionId=sec-1&t=GC",
        )
        self.assertEqual(
            notices[0].raw_api_url,
            "https://hengyang.hnsggzy.com/tradeApi/constructionNotice/getBySectionId?sectionId=sec-1",
        )


class KeywordCoverageTests(unittest.TestCase):
    def test_keyword_matching_covers_four_structured_fields(self) -> None:
        from app.keywords import build_keyword_text, match_keywords

        notice = Notice(
            source="source",
            source_subtype="construction",
            dedupe_key="a|4",
            section_id="sec-keyword",
            project_name="Generic Project",
            section_name="Generic Section",
            content_summary="ordinary content",
            qualification_summary="this project belongs to design service procurement",
            original_url="https://example.com/ann2",
            fetched_at="2026-06-11 11:00:00",
        )

        text = build_keyword_text(notice)
        self.assertIn("Generic Project", text)
        self.assertIn("Generic Section", text)
        self.assertIn("ordinary content", text)
        self.assertIn("design service procurement", text)
        self.assertEqual(match_keywords(text, ["design service"]), ["design service"])


class FeishuSchemaTests(unittest.TestCase):
    def test_schema_fields_include_link_and_business_columns(self) -> None:
        for field in [
            "来源子类",
            "唯一键",
            "标段名称",
            "公告类型",
            "项目编号",
            "招标人或采购单位",
            "代理机构",
            "文件获取截止时间",
            "开标或响应截止时间",
            "预算金额",
            "最高限价",
            "采购或招标方式",
            "项目内容摘要",
            "资质要求摘要",
            "是否接受联合体",
            "是否有附件",
            "附件数量",
            "商机层级",
            "分类理由",
            "正向信号",
            "排除信号",
            "官方平台入口",
            "建议搜索关键词",
            "原始接口链接",
        ]:
            self.assertIn(field, SCHEMA_FIELDS)

    def test_notice_fields_use_direct_detail_url_when_available(self) -> None:
        client = FeishuClient(mock.Mock())
        notice = Notice(
            source="source",
            source_subtype="construction",
            dedupe_key="d1",
            section_id="s1",
            project_name="Project One",
            notice_type="Tender Notice",
            purchaser_or_tenderer="Purchaser",
            region="Hengyang",
            content_summary="content summary",
            qualification_summary="qualification summary",
            employee_readable_url="https://hengyang.hnsggzy.com/#/resources/transactionDetail/construction?bidSectionId=s1&t=GC",
            raw_api_url="https://example.com/api",
            lead_tier="WATCHLIST",
            lead_reason="reason",
        )
        fields = client._build_notice_fields(notice)
        self.assertEqual(fields["原文链接"], notice.employee_readable_url)
        self.assertEqual(fields["官方平台入口"], OFFICIAL_PLATFORM_URL)
        self.assertEqual(fields["建议搜索关键词"], "Project One")
        self.assertEqual(fields["原始接口链接"], "https://example.com/api")

    def test_notice_fields_keep_safe_fallback_without_direct_url(self) -> None:
        client = FeishuClient(mock.Mock())
        notice = Notice(
            source="source",
            source_subtype="construction",
            dedupe_key="d1",
            section_id="s1",
            project_name="Project One",
            raw_api_url="https://example.com/api",
        )
        fields = client._build_notice_fields(notice)
        self.assertEqual(fields["原文链接"], OFFICIAL_PLATFORM_URL)
        self.assertEqual(fields["建议搜索关键词"], "Project One")
        self.assertEqual(fields["原始接口链接"], "https://example.com/api")

    def test_summary_uses_direct_detail_url_when_available(self) -> None:
        client = FeishuClient(mock.Mock())
        notice = Notice(
            source="source",
            source_subtype="construction",
            dedupe_key="d1",
            section_id="s1",
            project_name="Project One",
            notice_type="Tender Notice",
            purchaser_or_tenderer="Purchaser",
            region="Hengyang",
            content_summary="content summary",
            qualification_summary="qualification summary",
            employee_readable_url="https://hengyang.hnsggzy.com/#/resources/transactionDetail/construction?bidSectionId=s1&t=GC",
            raw_api_url="https://example.com/api",
            lead_tier="WATCHLIST",
            lead_reason="reason",
        )
        lines = client._build_notice_message_lines(notice)
        self.assertTrue(any(line.startswith("原文详情页：") for line in lines))
        self.assertTrue(any("https://example.com/api" in line for line in lines))

    def test_summary_keeps_fallback_when_direct_url_missing(self) -> None:
        client = FeishuClient(mock.Mock())
        notice = Notice(
            source="source",
            source_subtype="construction",
            dedupe_key="d1",
            section_id="s1",
            project_name="Project One",
            raw_api_url="https://example.com/api",
            lead_tier="WATCHLIST",
        )
        lines = client._build_notice_message_lines(notice)
        self.assertTrue(any("官方平台入口" in line and OFFICIAL_PLATFORM_URL in line for line in lines))
        self.assertTrue(any(line == "建议搜索关键词：Project One" for line in lines))
        self.assertTrue(any("原始接口链接（仅供复核）" in line for line in lines))


class MainEntryTests(unittest.TestCase):
    def test_local_structured_preview_runs_without_feishu(self) -> None:
        from app.main import main

        with mock.patch("app.main.run_once") as run_once:
            run_once.return_value = []
            exit_code = main(["--local-structured-preview"])

        self.assertEqual(exit_code, 0)
        run_once.assert_called_once()
        kwargs = run_once.call_args.kwargs
        self.assertFalse(kwargs["enable_feishu"])
        self.assertTrue(kwargs["structured_preview"])


if __name__ == "__main__":
    unittest.main()
