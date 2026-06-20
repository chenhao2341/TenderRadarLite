from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from app.models import Notice


class FakeFetcher:
    def __init__(self, json_map: dict[str, object]) -> None:
        self.json_map = json_map

    def get_json(self, url: str):
        return self.json_map[url]

    def get_text(self, url: str):
        raise AssertionError(f"unexpected text fetch: {url}")


def load_fixture(name: str) -> dict:
    path = Path(__file__).parent / "fixtures" / name
    return json.loads(path.read_text(encoding="utf-8"))


class ChangshaProcurementAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        from app.adapters.changsha_procurement import ChangshaProcurementAdapter

        self.adapter_class = ChangshaProcurementAdapter
        self.list_url = (
            "https://changsha.hnsggzy.com/tradeApi/governmentPurchase/"
            "projectInformation/selectAll?regionCode=430100&current=1&size=10"
            "&descs=noticeSendTime&notice=1&tenderMode=%E5%85%AC%E5%BC%80%E6%8B%9B%E6%A0%87"
        )
        self.page2_url = (
            "https://changsha.hnsggzy.com/tradeApi/governmentPurchase/"
            "projectInformation/selectAll?regionCode=430100&current=2&size=5"
            "&descs=noticeSendTime&notice=1&tenderMode=%E5%85%AC%E5%BC%80%E6%8B%9B%E6%A0%87"
        )
        self.page1_size5_url = (
            "https://changsha.hnsggzy.com/tradeApi/governmentPurchase/"
            "projectInformation/selectAll?regionCode=430100&current=1&size=5"
            "&descs=noticeSendTime&notice=1&tenderMode=%E5%85%AC%E5%BC%80%E6%8B%9B%E6%A0%87"
        )
        self.section_id = "011a2f03-78f2-4ea0-af0f-630182744105"
        self.project_url = (
            "https://changsha.hnsggzy.com/tradeApi/governmentPurchase/projectInformation/"
            f"getBySectionId?sectionId={self.section_id}"
        )
        self.announcement_url = (
            "https://changsha.hnsggzy.com/tradeApi/governmentPurchase/projectInformation/"
            f"getAnnouncementBySectionId?sectionId={self.section_id}"
        )
        self.list_payload = load_fixture("changsha_procurement_list_sample.json")
        self.project_payload = load_fixture("changsha_procurement_project_sample.json")
        self.announcement_payload = load_fixture("changsha_procurement_announcement_sample.json")

    def _build_adapter(
        self,
        *,
        announcement_payload: dict | None = None,
        source_config: dict | None = None,
        extra_json_map: dict[str, object] | None = None,
    ):
        fetcher_map = {
            self.list_url: self.list_payload,
            self.project_url: self.project_payload,
            self.announcement_url: announcement_payload or self.announcement_payload,
        }
        if extra_json_map:
            fetcher_map.update(extra_json_map)
        fetcher = FakeFetcher(fetcher_map)
        return self.adapter_class(
            source_name="Changsha Procurement",
            url=self.list_url,
            region="长沙",
            fetcher=fetcher,
            source_config=source_config
            or {
                "name": "Changsha Procurement",
                "source": "长沙公共资源交易平台",
                "source_subtype": "长沙政府采购交易",
            },
        )

    def test_fetch_list_returns_records_from_fixture(self) -> None:
        adapter = self._build_adapter()

        items = adapter.fetch_list()

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["bidSectionId"], self.section_id)
        self.assertEqual(items[0]["purchaseProjectName"], "（东塘校区）2026年家具类采购项目")

    def test_fetch_list_respects_pages_scanned_and_page_size(self) -> None:
        second_page_payload = {"code": 200, "data": {"records": [copy.deepcopy(self.list_payload["data"]["records"][0])]}}
        second_page_payload["data"]["records"][0]["bidSectionId"] = "page-2"
        second_page_payload["data"]["records"][0]["purchaseProjectName"] = "第二页项目"
        adapter = self._build_adapter(
            source_config={
                "name": "Changsha Procurement",
                "source": "长沙公共资源交易平台",
                "source_subtype": "长沙政府采购交易",
                "pages_scanned": 2,
                "page_size": 5,
            },
            extra_json_map={
                self.page1_size5_url: self.list_payload,
                self.page2_url: second_page_payload,
            },
        )
        adapter.url = self.page1_size5_url

        items = adapter.fetch_list()

        self.assertEqual(len(items), 2)
        self.assertEqual(adapter.last_crawl_stats if hasattr(adapter, "last_crawl_stats") else {}, {})
        self.assertEqual(adapter._list_stats["pages_scanned"], 2)
        self.assertEqual(adapter._list_stats["page_size"], 5)

    def test_fetch_detail_merges_project_and_announcement_payloads(self) -> None:
        adapter = self._build_adapter()
        item = self.list_payload["data"]["records"][0]

        detail = adapter.fetch_detail(item)

        self.assertTrue(detail["detail_checked"])
        self.assertTrue(detail["detail_available"])
        self.assertEqual(
            detail["detail"]["governmentProcurementProjectInformation"]["purchaserName"],
            "长沙市雅礼中学",
        )
        self.assertEqual(
            detail["announcement"]["id"],
            "fd2954cf-7b46-41bc-aace-cddb631aa360",
        )
        self.assertEqual(detail["raw_api_url"], self.announcement_url)

    def test_normalize_builds_notice_with_stable_dedupe_and_attachment_metadata(self) -> None:
        adapter = self._build_adapter()
        item = self.list_payload["data"]["records"][0]

        notice = adapter.normalize(item, adapter.fetch_detail(item))

        self.assertIsInstance(notice, Notice)
        self.assertEqual(notice.source, "长沙公共资源交易平台")
        self.assertEqual(notice.source_subtype, "长沙政府采购交易")
        self.assertEqual(
            notice.dedupe_key,
            "长沙公共资源交易平台-长沙政府采购交易|011a2f03-78f2-4ea0-af0f-630182744105|fd2954cf-7b46-41bc-aace-cddb631aa360",
        )
        self.assertEqual(notice.section_id, self.section_id)
        self.assertEqual(notice.notice_id, "fd2954cf-7b46-41bc-aace-cddb631aa360")
        self.assertEqual(notice.notice_title, "长沙市雅礼中学（东塘校区）2026年家具类采购项目招标公告")
        self.assertEqual(notice.project_name, "（东塘校区）2026年家具类采购项目")
        self.assertEqual(notice.purchaser_or_tenderer, "长沙市雅礼中学")
        self.assertEqual(notice.agency, "湖南中投项目管理有限公司")
        self.assertEqual(notice.region, "长沙")
        self.assertEqual(
            notice.original_url,
            "https://changsha.hnsggzy.com/#/resources/projectDetail/governmentPurchase?id=d6fe1726-8b47-4230-85e8-562dd090f4bb&regionCode=430100&bidSectionId=011a2f03-78f2-4ea0-af0f-630182744105&default=projectInfo",
        )
        self.assertEqual(notice.employee_readable_url, notice.original_url)
        self.assertEqual(notice.raw_api_url, self.announcement_url)
        self.assertTrue(notice.detail_checked)
        self.assertTrue(notice.detail_available)
        self.assertTrue(notice.has_attachment)
        self.assertEqual(notice.attachments_found, 2)
        self.assertEqual(notice.attachments[0].title, "CSCG20260467-01Z01")
        self.assertEqual(notice.attachments[1].title, "采购文件.pdf")
        self.assertEqual(notice.attachments[1].file_type, "PDF")
        self.assertEqual(notice.budget_amount, "1233095.0")
        self.assertEqual(notice.budget_amount_unit, "")
        self.assertEqual(notice.budget_amount_unit_source, "unknown")
        self.assertIn("附件仅做发现", notice.detail_risk_note or "")

    def test_normalize_extracts_clean_content_and_qualification_summary_from_notice_content(self) -> None:
        payload = copy.deepcopy(self.announcement_payload)
        payload["data"]["governmentProcureAnnouncementInformation"][0]["noticeContent"] = """
        <div>
          <p>项目概况：本项目采购智慧教室设备升级与安装服务。</p>
          <p>采购需求：完成多媒体终端、讲台和网络改造，服务期 30 天。</p>
          <p>申请人的资格要求：</p>
          <p>1. 满足《中华人民共和国政府采购法》第二十二条规定。</p>
          <p>2. 本项目专门面向中小企业采购。</p>
          <p><span>请勿保留 HTML 标签</span></p>
        </div>
        """
        adapter = self._build_adapter(announcement_payload=payload)
        item = self.list_payload["data"]["records"][0]

        notice = adapter.normalize(item, adapter.fetch_detail(item))

        self.assertIn("智慧教室设备升级与安装服务", notice.content_summary)
        self.assertIn("政府采购法", notice.qualification_summary)
        self.assertIn("专门面向中小企业采购", notice.qualification_summary)
        self.assertNotIn("<p>", notice.content_summary)
        self.assertNotIn("<span>", notice.qualification_summary)

    def test_normalize_returns_missing_summary_when_notice_content_has_no_relevant_section(self) -> None:
        payload = copy.deepcopy(self.announcement_payload)
        payload["data"]["governmentProcureAnnouncementInformation"][0]["noticeContent"] = """
        <div>
          <p>公告说明：本页面仅展示流程提醒。</p>
          <p>报名后请按系统提示办理。</p>
        </div>
        """
        project_payload = copy.deepcopy(self.project_payload)
        project_payload["data"]["GovernmentProcureSectionInformationList"][0]["purchaseSectionContent"] = "详见招标文件"
        project_payload["data"]["GovernmentProcureSectionInformationList"][0]["purchaseQualification"] = "详见招标文件"
        adapter = self._build_adapter(
            announcement_payload=payload,
            extra_json_map={self.project_url: project_payload},
        )
        item = self.list_payload["data"]["records"][0]

        notice = adapter.normalize(item, adapter.fetch_detail(item))

        self.assertEqual(notice.content_summary, "未提取到")
        self.assertEqual(notice.qualification_summary, "未提取到")

    def test_normalize_falls_back_when_announcement_id_is_missing(self) -> None:
        payload = copy.deepcopy(self.announcement_payload)
        announcement = payload["data"]["governmentProcureAnnouncementInformation"][0]
        announcement["id"] = ""
        adapter = self._build_adapter(announcement_payload=payload)
        item = self.list_payload["data"]["records"][0]

        notice = adapter.normalize(item, adapter.fetch_detail(item))

        self.assertEqual(
            notice.dedupe_key,
            "长沙公共资源交易平台-长沙政府采购交易|011a2f03-78f2-4ea0-af0f-630182744105|长沙市雅礼中学（东塘校区）2026年家具类采购项目招标公告|2026-06-16T15:08:24.000+08:00",
        )

    def test_crawl_keeps_notice_when_announcement_detail_is_unavailable(self) -> None:
        adapter = self._build_adapter(announcement_payload={"code": 500, "msg": "unavailable", "data": None})

        notices = adapter.crawl()

        self.assertEqual(len(notices), 1)
        self.assertFalse(notices[0].detail_available)
        self.assertIn("详情页不可访问或解析失败", notices[0].detail_risk_note or "")
        self.assertEqual(notices[0].attachments_found, 1)
        self.assertTrue(notices[0].dedupe_key.startswith("长沙公共资源交易平台-长沙政府采购交易|011a2f03"))

    def test_fetch_detail_prefers_matching_announcement_type_over_latest_non_matching_notice(self) -> None:
        payload = copy.deepcopy(self.announcement_payload)
        payload["data"]["governmentProcureAnnouncementInformation"] = [
            {
                "id": "newer-gengzheng",
                "bulletinType": "更正公告",
                "noticeName": "长沙市雅礼中学（东塘校区）2026年家具类采购项目更正公告",
                "noticeSendTime": "2026-06-18T10:00:00.000+08:00",
                "bulletinDuty": "湖南中投项目管理有限公司",
                "noticeContent": "<div><p>更正公告</p></div>",
            },
            copy.deepcopy(self.announcement_payload["data"]["governmentProcureAnnouncementInformation"][0]),
        ]
        adapter = self._build_adapter(announcement_payload=payload)
        item = self.list_payload["data"]["records"][0]

        detail = adapter.fetch_detail(item)
        notice = adapter.normalize(item, detail)

        self.assertEqual(detail["announcement"]["bulletinType"], "招标公告")
        self.assertEqual(detail["announcement"]["id"], "fd2954cf-7b46-41bc-aace-cddb631aa360")
        self.assertEqual(notice.notice_type, "招标公告")
        self.assertIn("公告类型与列表类型不一致", notice.detail_risk_note or "")


if __name__ == "__main__":
    unittest.main()
