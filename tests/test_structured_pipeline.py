from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.attachment_utils import detect_attachment_category, detect_file_type, extract_attachments_from_html
from app.feishu import OFFICIAL_PLATFORM_URL, PRIMARY_FIELD_NAME, SCHEMA_FIELDS, FeishuClient
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
    def test_attachment_helper_extracts_links_types_and_categories_from_html(self) -> None:
        html = """
        <div>
          <a href="/files/招标文件.pdf">招标文件.pdf</a>
          <a href="https://example.com/bill/工程量清单.xlsx">工程量清单.xlsx</a>
          <a href="/download/更正公告.docx">更正公告.docx</a>
          <a href="/archives/报价表.xls">报价表.xls</a>
          <a href="/bundle/附件.zip">附件.zip</a>
          <a href="/bundle/附件.rar">附件.rar</a>
        </div>
        """

        attachments = extract_attachments_from_html(html, base_url="https://example.com/detail")

        self.assertEqual([item.title for item in attachments[:3]], ["招标文件.pdf", "工程量清单.xlsx", "更正公告.docx"])
        self.assertEqual(detect_file_type("/files/a.pdf"), "PDF")
        self.assertEqual(detect_file_type("/files/a.doc"), "DOC")
        self.assertEqual(detect_file_type("/files/a.docx"), "DOCX")
        self.assertEqual(detect_file_type("/files/a.xls"), "XLS")
        self.assertEqual(detect_file_type("/files/a.xlsx"), "XLSX")
        self.assertEqual(detect_file_type("/files/a.zip"), "ZIP")
        self.assertEqual(detect_file_type("/files/a.rar"), "RAR")
        self.assertEqual(detect_attachment_category("招标文件.pdf"), "bidding_file")
        self.assertEqual(detect_attachment_category("采购文件.doc"), "procurement_file")
        self.assertEqual(detect_attachment_category("工程量清单.xlsx"), "bill_file")
        self.assertEqual(detect_attachment_category("报价表.xls"), "bill_file")
        self.assertEqual(detect_attachment_category("最高限价说明.doc"), "bill_file")
        self.assertEqual(detect_attachment_category("更正公告.docx"), "correction_file")
        self.assertEqual(detect_attachment_category("澄清说明.pdf"), "correction_file")
        self.assertEqual(detect_attachment_category("答疑文件.pdf"), "correction_file")
        self.assertEqual(detect_attachment_category("补遗通知.pdf"), "correction_file")

    def test_procurement_adapter_fetch_normalize_pipeline_preserves_key_fields(self) -> None:
        from app.adapters.hengyang_procurement import HengyangProcurementAdapter

        list_url = (
            "https://hengyang.hnsggzy.com/tradeApi/governmentPurchase/"
            "projectInformation/selectAll?regionCode=430400&current=1&size=10"
        )
        section_id = "sec-1"
        project_url = (
            "https://hengyang.hnsggzy.com/tradeApi/governmentPurchase/projectInformation/"
            f"getBySectionId?sectionId={section_id}"
        )
        ann_url = (
            "https://hengyang.hnsggzy.com/tradeApi/governmentPurchase/projectInformation/"
            f"getAnnouncementBySectionId?sectionId={section_id}"
        )
        fetcher = FakeFetcher(
            {
                list_url: {
                    "data": {
                        "records": [
                            {
                                "bidSectionId": section_id,
                                "projectId": "proj-1",
                                "purchaseProjectName": "Project One",
                                "purchaseSectionName": "Package One",
                                "regionName": "Hengyang",
                                "noticeType": "Tender Notice",
                                "noticeSendTime": "2026-06-11 10:00:00",
                            }
                        ]
                    }
                },
                project_url: {
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
                                "id": section_id,
                                "purchaseSectionName": "Package One",
                                "tenderType": "Competitive Negotiation",
                                "sectionBudget": "100",
                                "controlPrice": "90",
                            }
                        ],
                        "GovernmentPurchaseFile": [{"name": "file1.pdf"}],
                    }
                },
                ann_url: {
                    "code": 200,
                    "data": {
                        "governmentProcureAnnouncementInformation": [
                            {
                                "id": "ann-1",
                                "noticeName": "Project One competitive negotiation notice",
                                "bulletinType": "Tender Notice",
                                "noticeSendTime": "2026-06-11T10:00:00.000+08:00",
                                "noticeContent": (
                                    "<p>Procurement project: Project One</p>"
                                    "<p>采购预算：100万元</p>"
                                    "<p>最高限价：90元</p>"
                                    "<p>Qualification: supplier qualification required</p>"
                                    "<p>Deadline: 2026-06-20 09:00:00</p>"
                                    "<p>Consortium supported: No</p>"
                                ),
                            }
                        ]
                    },
                },
            }
        )

        adapter = HengyangProcurementAdapter(
            source_name="procurement",
            url=list_url,
            region="Hengyang",
            fetcher=fetcher,
            source_config={"source": "source", "source_subtype": "procurement"},
        )

        items = adapter.fetch_list()
        self.assertEqual(len(items), 1)

        detail = adapter.fetch_detail(items[0])
        notice = adapter.normalize(items[0], detail)

        self.assertIsInstance(notice, Notice)
        self.assertEqual(notice.source, "source")
        self.assertEqual(notice.source_subtype, "procurement")
        self.assertEqual(notice.project_name, "Project One")
        self.assertEqual(notice.section_name, "Package One")
        self.assertTrue(hasattr(notice, "qualification_summary"))
        self.assertIsInstance(notice.qualification_summary, str)
        self.assertTrue(notice.content_summary)
        self.assertEqual(notice.budget_amount, "100")
        self.assertEqual(notice.budget_amount_unit, "万元")
        self.assertEqual(notice.ceiling_price, "90")
        self.assertEqual(notice.ceiling_price_unit, "元")
        self.assertEqual(notice.original_url, ann_url)
        self.assertEqual(notice.raw_api_url, ann_url)
        self.assertTrue(notice.detail_checked)
        self.assertTrue(notice.detail_available)
        self.assertEqual(notice.attachments_found, 1)
        self.assertEqual(notice.attachments[0].title, "file1.pdf")
        self.assertEqual(notice.attachments[0].file_type, "PDF")
        self.assertTrue(notice.dedupe_key)

    def test_procurement_adapter_marks_sections_without_real_notice_as_detail_unavailable(self) -> None:
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
        self.assertEqual(len(notices), 2)
        self.assertEqual(notices[0].section_id, "sec-1")
        self.assertTrue(notices[0].detail_available)
        self.assertEqual(notices[0].project_code, "PC-1")
        self.assertEqual(notices[0].procurement_method, "Competitive Negotiation")
        self.assertEqual(notices[1].section_id, "sec-2")
        self.assertFalse(notices[1].detail_available)
        self.assertEqual(notices[1].detail_risk_note, "详情页不可访问或解析失败")

    def test_procurement_adapter_keeps_notice_when_detail_is_unavailable(self) -> None:
        from app.adapters.hengyang_procurement import HengyangProcurementAdapter

        list_url = (
            "https://hengyang.hnsggzy.com/tradeApi/governmentPurchase/"
            "projectInformation/selectAll?regionCode=430400&current=1&size=10"
        )
        section_id = "sec-unavailable"
        project_url = (
            "https://hengyang.hnsggzy.com/tradeApi/governmentPurchase/projectInformation/"
            f"getBySectionId?sectionId={section_id}"
        )
        ann_url = (
            "https://hengyang.hnsggzy.com/tradeApi/governmentPurchase/projectInformation/"
            f"getAnnouncementBySectionId?sectionId={section_id}"
        )
        fetcher = FakeFetcher(
            {
                list_url: {
                    "data": {
                        "records": [
                            {
                                "bidSectionId": section_id,
                                "projectId": "proj-1",
                                "purchaseProjectName": "Project Unavailable",
                                "purchaseSectionName": "Package One",
                                "regionName": "Hengyang",
                                "noticeType": "Tender Notice",
                                "noticeSendTime": "2026-06-11 10:00:00",
                            }
                        ]
                    }
                },
                project_url: {
                    "data": {
                        "governmentProcurementProjectInformation": {
                            "purchaseProjectName": "Project Unavailable",
                            "purchaseProjectCode": "PC-1",
                        },
                        "GovernmentProcureSectionInformationList": [{"id": section_id, "purchaseSectionName": "Package One"}],
                        "GovernmentPurchaseFile": [],
                    }
                },
                ann_url: {"code": 500, "msg": "unavailable", "data": None},
            }
        )

        adapter = HengyangProcurementAdapter(
            source_name="procurement",
            url=list_url,
            region="Hengyang",
            fetcher=fetcher,
            source_config={"source": "source", "source_subtype": "procurement"},
        )

        notices = adapter.crawl()

        self.assertEqual(len(notices), 1)
        self.assertTrue(notices[0].detail_checked)
        self.assertFalse(notices[0].detail_available)
        self.assertEqual(notices[0].detail_risk_note, "详情页不可访问或解析失败")
        self.assertEqual(notices[0].attachments_found, 0)

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

    def test_construction_adapter_fetch_normalize_pipeline_preserves_key_fields(self) -> None:
        from app.adapters.hengyang_construction import HengyangConstructionAdapter

        list_url = (
            "https://hengyang.hnsggzy.com/tradeApi/constructionTender/"
            "listByFile?regionCode=430400&current=1&size=10"
        )
        section_id = "sec-1"
        project_url = f"https://hengyang.hnsggzy.com/tradeApi/constructionTender/getBySectionId?sectionId={section_id}"
        notice_url = f"https://hengyang.hnsggzy.com/tradeApi/constructionNotice/getBySectionId?sectionId={section_id}"
        attachment_url = f"https://hengyang.hnsggzy.com/tradeApi/attach/proxy/getFileListBySectionId?sectionId={section_id}"
        fetcher = FakeFetcher(
            {
                list_url: {
                    "data": {
                        "records": [
                            {
                                "bidSectionId": section_id,
                                "regionCode": "430400",
                                "tenderProjectType": "CONSTRUCTION",
                                "noticeType": "Tender Notice",
                                "name": "Hengyang",
                                "tenderProjectName": "Example Construction",
                                "bidSectionName": "Section A",
                                "noticeSendTime": "2026-06-11 10:00:00",
                            }
                        ]
                    }
                },
                project_url: {
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
                notice_url: {
                    "data": {
                        "noticeList": [
                            {
                                "id": "notice-1",
                                "noticeName": "Example Construction notice",
                                "bulletinType": "Tender Notice",
                                "noticeSendTime": "2026-06-11 10:00:00",
                                "noticeContent": (
                                    "<p>Project overview: example construction</p>"
                                    "<p>合同估算价100万元</p>"
                                    "<p>最高投标限价90元</p>"
                                    "<p>Qualification: required</p>"
                                    "<p>Deadline: 2026-06-30 09:00:00</p>"
                                ),
                                "docGetEndTime": "2026-06-20 17:00:00",
                                "bidOpeningTimeStart": "2026-06-30 09:00:00",
                            }
                        ]
                    }
                },
                attachment_url: {"data": [{"name": "drawing.pdf"}]},
            }
        )

        adapter = HengyangConstructionAdapter(
            source_name="construction",
            url=list_url,
            region="Hengyang",
            fetcher=fetcher,
            source_config={"source": "source", "source_subtype": "construction"},
        )

        items = adapter.fetch_list()
        self.assertEqual(len(items), 1)

        detail = adapter.fetch_detail(items[0])
        notice = adapter.normalize(items[0], detail)

        self.assertIsInstance(notice, Notice)
        self.assertEqual(notice.source, "source")
        self.assertEqual(notice.source_subtype, "construction")
        self.assertEqual(notice.project_name, "Example Construction")
        self.assertEqual(notice.section_name, "Section A")
        self.assertTrue(hasattr(notice, "qualification_summary"))
        self.assertIsInstance(notice.qualification_summary, str)
        self.assertTrue(notice.content_summary)
        self.assertEqual(notice.budget_amount, "100")
        self.assertEqual(notice.budget_amount_unit, "万元")
        self.assertEqual(notice.ceiling_price, "90")
        self.assertEqual(notice.ceiling_price_unit, "元")
        self.assertEqual(
            notice.employee_readable_url,
            "https://hengyang.hnsggzy.com/#/resources/transactionDetail/construction?bidSectionId=sec-1&t=GC",
        )
        self.assertEqual(notice.original_url, notice.employee_readable_url)
        self.assertEqual(notice.raw_api_url, notice_url)
        self.assertTrue(notice.detail_checked)
        self.assertTrue(notice.detail_available)
        self.assertEqual(notice.attachments_found, 1)
        self.assertEqual(notice.attachments[0].file_type, "PDF")
        self.assertTrue(notice.dedupe_key)


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
    def test_schema_fields_match_clean_table_layout(self) -> None:
        self.assertEqual(
            SCHEMA_FIELDS,
            [
                "商机层级",
                "公告类型",
                "发布时间",
                "地区",
                "招标人或采购单位",
                "代理机构",
                "预算金额",
                "最高限价",
                "截止时间",
                "命中关键词",
                "分类理由",
                "原文链接",
                "抓取时间",
                "唯一键",
            ],
        )

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
            agency="Agency",
            region="Hengyang",
            budget_amount="100",
            ceiling_price="90",
            bid_open_or_response_deadline="2026-06-20 09:00:00",
            employee_readable_url="https://hengyang.hnsggzy.com/#/resources/transactionDetail/construction?bidSectionId=s1&t=GC",
            raw_api_url="https://example.com/api",
            lead_tier="WATCHLIST",
            lead_reason="reason",
            hit_keywords=["design"],
            fetched_at="2026-06-11 11:00:00",
        )
        fields = client._build_notice_fields(notice)
        self.assertEqual(
            set(fields.keys()),
            {
                "项目名称",
                "商机层级",
                "公告类型",
                "发布时间",
                "地区",
                "招标人或采购单位",
                "代理机构",
                "预算金额",
                "最高限价",
                "截止时间",
                "命中关键词",
                "分类理由",
                "原文链接",
                "抓取时间",
                "唯一键",
            },
        )
        self.assertEqual(fields["原文链接"], notice.employee_readable_url)
        self.assertEqual(fields["截止时间"], "2026-06-20 09:00:00")
        self.assertEqual(fields["命中关键词"], "design")
        self.assertEqual(fields["唯一键"], "d1")

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
        self.assertEqual(fields["项目名称"], "Project One")

    def test_summary_uses_detailed_format_with_raw_url(self) -> None:
        client = FeishuClient(mock.Mock())
        notice = Notice(
            source="source",
            source_subtype="construction",
            dedupe_key="d1",
            section_id="s1",
            project_name="Project One",
            notice_type="Tender Notice",
            purchaser_or_tenderer="Purchaser",
            agency="Agency",
            region="Hengyang",
            budget_amount="100",
            ceiling_price="90",
            procurement_method="公开招标",
            file_get_deadline="2026-06-18 09:00:00",
            bid_open_or_response_deadline="2026-06-20 09:00:00",
            content_summary="content summary",
            qualification_summary="qualification summary",
            accepts_consortium="未提取到",
            has_attachment=True,
            attachment_count=2,
            employee_readable_url="https://hengyang.hnsggzy.com/#/resources/transactionDetail/construction?bidSectionId=s1&t=GC",
            raw_api_url="https://example.com/api",
            lead_tier="WATCHLIST",
            lead_reason="reason",
            matched_positive_signals=["design"],
            matched_negative_signals=["construction"],
        )
        lines = client._build_notice_message_lines(notice)
        self.assertEqual(lines[0], "商机层级：WATCHLIST")
        self.assertTrue(any(line == "项目名称：Project One" for line in lines))
        self.assertTrue(any(line == "招标人或采购单位：Purchaser" for line in lines))
        self.assertTrue(any(line == "文件获取截止时间：2026-06-18 09:00:00" for line in lines))
        self.assertTrue(any(line == "开标或响应截止时间：2026-06-20 09:00:00" for line in lines))
        self.assertTrue(any(line == "附件数量：2" for line in lines))
        self.assertTrue(any(line.startswith("人工建议：") for line in lines))
        self.assertTrue(any(line.startswith("原文详情页：https://hengyang.hnsggzy.com/") for line in lines))
        self.assertTrue(any(line == "原始接口链接（仅供复核）：https://example.com/api" for line in lines))

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
        self.assertTrue(any(line == f"官方平台入口：{OFFICIAL_PLATFORM_URL}" for line in lines))
        self.assertTrue(any(line == "建议搜索关键词：Project One" for line in lines))
        self.assertTrue(any("原始接口链接（仅供复核）" in line for line in lines))

    def test_send_summary_uses_detailed_header(self) -> None:
        client = FeishuClient(mock.Mock())
        notices = [
            Notice(source="s", source_subtype="t", dedupe_key="1", section_id="a", project_name="One", lead_tier="DIRECT"),
            Notice(source="s", source_subtype="t", dedupe_key="2", section_id="b", project_name="Two", lead_tier="WATCHLIST"),
        ]
        with mock.patch.object(client, "send_bot_message", return_value=True) as send_bot_message:
            client.send_summary(notices)

        message = send_bot_message.call_args.args[0]
        self.assertTrue(message.startswith("【TenderRadarLite】"))
        self.assertIn("商机层级：DIRECT", message)

    def test_init_schema_is_idempotent_when_fields_exist(self) -> None:
        client = FeishuClient(mock.Mock())
        fields = [{"field_id": "fld1", "field_name": PRIMARY_FIELD_NAME, "is_primary": True}] + [
            {"field_id": f"fld{index}", "field_name": field_name, "is_primary": False}
            for index, field_name in enumerate(SCHEMA_FIELDS, start=2)
        ]

        with (
            mock.patch.object(client, "parse_bitable_target_from_env", return_value=("app_token", "tbl1")),
            mock.patch.object(client, "_get_tenant_access_token", return_value="token"),
            mock.patch.object(
                client,
                "_resolve_target_table",
                return_value=mock.Mock(app_token="app_token", table_id="tbl1", table_name="数据表"),
            ),
            mock.patch.object(client, "_list_fields", return_value=fields),
            mock.patch.object(client, "_create_field") as create_field,
        ):
            result = client.init_schema()

        create_field.assert_not_called()
        self.assertEqual(result["created_fields"], [])
        self.assertEqual(result["failed_fields"], [])

    def test_init_schema_stops_when_primary_rename_fails(self) -> None:
        client = FeishuClient(mock.Mock())
        fields = [{"field_id": "fld1", "field_name": "文本", "is_primary": True}]

        with (
            mock.patch.object(client, "parse_bitable_target_from_env", return_value=("app_token", "tbl1")),
            mock.patch.object(client, "_get_tenant_access_token", return_value="token"),
            mock.patch.object(
                client,
                "_resolve_target_table",
                return_value=mock.Mock(app_token="app_token", table_id="tbl1", table_name="数据表"),
            ),
            mock.patch.object(client, "_list_fields", return_value=fields),
            mock.patch.object(client, "_update_field", side_effect=RuntimeError("rename failed")),
            mock.patch.object(client, "_create_field") as create_field,
        ):
            with self.assertRaises(RuntimeError):
                client.init_schema()

        create_field.assert_not_called()


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

    def test_local_html_runs_without_feishu(self) -> None:
        from app.main import main

        with mock.patch("app.main.run_once") as run_once:
            run_once.return_value = []
            exit_code = main(["--local-html"])

        self.assertEqual(exit_code, 0)
        run_once.assert_called_once()
        kwargs = run_once.call_args.kwargs
        self.assertFalse(kwargs["enable_feishu"])
        self.assertTrue(kwargs["html_report"])

    def test_init_feishu_fields_alias_calls_init_schema(self) -> None:
        from app.main import main

        fake_client = mock.Mock()
        fake_client.init_schema.return_value = {
            "app_token_masked": "mask",
            "table_id": "tbl",
            "table_name": "数据表",
            "existing_fields": ["项目名称"],
            "created_fields": [],
            "renamed_fields": [],
            "failed_fields": [],
            "existing_field_count": 1,
        }

        with mock.patch("app.main.FeishuClient", return_value=fake_client):
            exit_code = main(["--init-feishu-fields"])

        self.assertEqual(exit_code, 0)
        fake_client.init_schema.assert_called_once()


class HtmlReportTests(unittest.TestCase):
    def _sample_notice(self, lead_tier: str, project_name: str, suffix: str) -> Notice:
        return Notice(
            source="source",
            source_subtype="construction",
            dedupe_key=f"source|{suffix}",
            section_id=f"section-{suffix}",
            project_name=project_name,
            notice_id=f"notice-{suffix}",
            notice_type="Tender Notice",
            purchaser_or_tenderer="Tenderer",
            agency="Agency",
            region="Hengyang",
            publish_time="2026-06-15 10:00:00",
            bid_open_or_response_deadline="2026-06-20 09:00:00",
            budget_amount="1000",
            ceiling_price="900",
            content_summary="Content summary",
            qualification_summary="Qualification summary",
            employee_readable_url=f"https://example.com/{suffix}",
            hit_keywords=["design"],
            lead_tier=lead_tier,
            lead_reason=f"{lead_tier} reason",
            fetched_at="2026-06-15 12:00:00",
        )

    def test_write_html_report_renders_sections_and_fields(self) -> None:
        from app.html_report import write_html_report

        notices = [
            self._sample_notice("DIRECT", "Direct Project", "direct"),
            self._sample_notice("WATCHLIST", "Watch Project", "watch"),
            self._sample_notice("EXCLUDE", "Exclude Project", "exclude"),
        ]

        with tempfile.TemporaryDirectory() as raw_dir:
            report_path = Path(raw_dir) / "latest.html"
            written_path = write_html_report(report_path, notices, source_count=1, generated_at="2026-06-15 12:00:00")

            self.assertEqual(written_path, report_path)
            self.assertTrue(report_path.exists())
            html = report_path.read_text(encoding="utf-8")

        self.assertIn("TenderRadarLite 本地招投标线索报告", html)
        self.assertIn(">DIRECT<", html)
        self.assertIn(">WATCHLIST<", html)
        self.assertIn(">EXCLUDE<", html)
        self.assertIn("Direct Project", html)
        self.assertIn("DIRECT reason", html)
        self.assertIn('href="https://example.com/direct"', html)

    def test_write_html_report_renders_attachment_panel(self) -> None:
        from app.models import AttachmentInfo
        from app.html_report import write_html_report

        notice = self._sample_notice("DIRECT", "Attachment Project", "attachment")
        notice.detail_checked = True
        notice.detail_available = True
        notice.attachments_found = 2
        notice.attachments = [
            AttachmentInfo(title="招标文件.pdf", url="https://example.com/files/a.pdf", file_type="PDF", category="bidding_file", source="detail_page"),
            AttachmentInfo(title="工程量清单.xlsx", url="https://example.com/files/b.xlsx", file_type="XLSX", category="bill_file", source="detail_page"),
        ]

        with tempfile.TemporaryDirectory() as raw_dir:
            report_path = Path(raw_dir) / "latest.html"
            write_html_report(report_path, [notice], source_count=1, generated_at="2026-06-15 12:00:00")
            html = report_path.read_text(encoding="utf-8")

        self.assertIn("详情/附件", html)
        self.assertIn("发现附件：2 个", html)
        self.assertIn("招标文件.pdf", html)
        self.assertIn("工程量清单.xlsx", html)

    def test_write_html_report_handles_missing_attachments_without_crashing(self) -> None:
        from app.html_report import write_html_report

        notice = self._sample_notice("WATCHLIST", "No Attachment Project", "no-attachment")
        notice.detail_checked = True
        notice.detail_available = True
        notice.attachments_found = 0

        with tempfile.TemporaryDirectory() as raw_dir:
            report_path = Path(raw_dir) / "latest.html"
            write_html_report(report_path, [notice], source_count=1, generated_at="2026-06-15 12:00:00")
            html = report_path.read_text(encoding="utf-8")

        self.assertIn("详情/附件", html)
        self.assertIn("发现附件：0 个", html)

    def test_write_html_report_marks_detail_unavailable(self) -> None:
        from app.html_report import write_html_report

        notice = self._sample_notice("WATCHLIST", "Unavailable Detail Project", "detail-unavailable")
        notice.detail_checked = True
        notice.detail_available = False
        notice.detail_risk_note = "详情页不可访问或解析失败"

        with tempfile.TemporaryDirectory() as raw_dir:
            report_path = Path(raw_dir) / "latest.html"
            write_html_report(report_path, [notice], source_count=1, generated_at="2026-06-15 12:00:00")
            html = report_path.read_text(encoding="utf-8")

        self.assertIn("详情页不可访问或解析失败", html)
        self.assertIn("请人工打开原文链接复核", html)

    def test_write_html_report_renders_empty_state(self) -> None:
        from app.html_report import write_html_report

        with tempfile.TemporaryDirectory() as raw_dir:
            report_path = Path(raw_dir) / "latest.html"
            write_html_report(report_path, [], source_count=0, generated_at="2026-06-15 12:00:00")
            html = report_path.read_text(encoding="utf-8")

        self.assertIn("本轮未发现新线索", html)
        self.assertIn("检查来源配置或稍后再运行", html)


if __name__ == "__main__":
    unittest.main()
