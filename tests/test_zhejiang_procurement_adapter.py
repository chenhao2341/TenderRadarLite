from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

from app.adapters.zhejiang_procurement import (
    DETAIL_API,
    SEARCH_HOME_API,
    ZhejiangProcurementAdapter,
    _build_detail_api_url,
    _build_detail_page_url,
)
from app.models import Notice
from app.source_catalog import find_source_by_id, load_source_catalog


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "zhejiang_procurement"


def _read_json(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


class ZhejiangProcurementAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fetcher = mock.Mock()
        self.fetcher.timeout = 20
        self.source_config = {
            "name": "Zhejiang Government Procurement",
            "source": "浙江政府采购网",
            "source_subtype": "政府采购 / JSON门户流",
            "enabled": False,
            "category_code": "110-606633",
            "sub_codes": ["110-306476", "110-684034", "110-511933"],
            "exclude_district_prefix": ["90", "006011", "H0", "001111"],
            "page_size": 10,
            "parent_id": "600007",
        }
        self.adapter = ZhejiangProcurementAdapter(
            source_name="Zhejiang Government Procurement",
            url=SEARCH_HOME_API,
            region="浙江省",
            fetcher=self.fetcher,
            source_config=self.source_config,
        )
        self.list_payload = _read_json("search_home_page_1.json")
        self.detail_payload = _read_json("detail_sample.json")

    def test_fetch_list_parses_search_home_json(self) -> None:
        with mock.patch.object(self.adapter, "_post_json", return_value=self.list_payload):
            items = self.adapter.fetch_list()

        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]["title"], "浙江师范大学关于高精度信号测量与振动控制装备公开招标公告")
        self.assertEqual(items[0]["articleId"], "/1DDoavnYlo4kXCYBI7Pxw==")
        self.assertEqual(items[0]["publishDateString"], "2026-06-23")
        self.assertEqual(items[0]["districtName"], "浙江省本级")
        self.assertEqual(items[0]["purchaseMethod"], "公开招标")
        self.assertEqual(items[0]["purchaseName"], "浙江师范大学")
        self.assertEqual(items[0]["_first_id"], "600007")

    def test_fetch_detail_builds_readable_and_api_urls(self) -> None:
        item = dict(self.list_payload["result"]["data"]["children"][0])
        item["_first_id"] = "600007"
        with mock.patch.object(self.adapter, "_get_json", return_value=self.detail_payload):
            detail = self.adapter.fetch_detail(item)

        self.assertTrue(detail["detail_checked"])
        self.assertTrue(detail["detail_available"])
        self.assertEqual(
            detail["employee_url"],
            _build_detail_page_url("600007", "/1DDoavnYlo4kXCYBI7Pxw=="),
        )
        self.assertEqual(
            detail["raw_api_url"],
            _build_detail_api_url("/1DDoavnYlo4kXCYBI7Pxw=="),
        )

    def test_normalize_maps_core_fields_without_guessing_optional_fields(self) -> None:
        item = dict(self.list_payload["result"]["data"]["children"][0])
        item["_first_id"] = "600007"
        detail = {
            "detail_checked": True,
            "detail_available": True,
            "detail": self.detail_payload["result"]["data"],
            "raw_api_url": _build_detail_api_url(item["articleId"]),
            "employee_url": _build_detail_page_url("600007", item["articleId"]),
            "structured_attachments": [
                {
                    "name": "采购意向情况说明.doc",
                    "url": "https://zcy-gov-open-doc.oss-cn-north-2-gov-1.aliyuncs.com/1024FPA/330000/10007103194/20266/sample-procurement-file.doc",
                }
            ],
        }

        notice = self.adapter.normalize(item, detail)

        self.assertIsInstance(notice, Notice)
        self.assertEqual(notice.source, "浙江政府采购网")
        self.assertEqual(notice.source_subtype, "政府采购 / JSON门户流")
        self.assertEqual(notice.notice_title, item["title"])
        self.assertEqual(notice.notice_id, item["articleId"])
        self.assertEqual(notice.project_name, "高精度信号测量与振动控制装备")
        self.assertEqual(notice.project_code, "330000263030080000973-ZB2026039（第2次）")
        self.assertEqual(notice.purchaser_or_tenderer, "浙江师范大学")
        self.assertEqual(notice.region, "浙江省本级")
        self.assertEqual(notice.publish_time, "2026-06-23 09:23:09")
        self.assertEqual(notice.notice_type, "招标公告")
        self.assertEqual(notice.procurement_method, "公开招标")
        self.assertEqual(notice.bid_open_or_response_deadline, "2026-07-14 08:30:00")
        self.assertEqual(
            notice.original_url,
            "https://zfcg.czt.zj.gov.cn/site/detail?parentId=600007&articleId=%2F1DDoavnYlo4kXCYBI7Pxw%3D%3D",
        )
        self.assertEqual(notice.employee_readable_url, notice.original_url)
        self.assertEqual(
            notice.raw_api_url,
            "https://zfcg.czt.zj.gov.cn/portal/detail?articleId=%2F1DDoavnYlo4kXCYBI7Pxw%3D%3D",
        )
        self.assertIn("采购高精度信号测量与振动控制装备一批", notice.content_summary)
        self.assertIn("政府采购法", notice.qualification_summary)
        self.assertTrue(notice.detail_available)
        self.assertTrue(notice.has_attachment)
        self.assertIn("JSON 门户流字段有限", notice.detail_risk_note or "")
        self.assertIn("默认结果可能存在置顶旧文或非严格时序", notice.detail_risk_note or "")
        self.assertNotIn("project_code", (notice.detail_risk_note or "").lower())

    def test_normalize_keeps_missing_qualification_and_deadline_as_partial_not_guess(self) -> None:
        item = dict(self.list_payload["result"]["data"]["children"][1])
        item["_first_id"] = "600007"
        detail_data = dict(self.detail_payload["result"]["data"])
        detail_data["content"] = "<div><p>采购需求：仅展示最小正文。</p></div>"
        detail_data["projectCode"] = ""
        item["bidOpeningTime"] = None
        notice = self.adapter.normalize(
            item,
            {
                "detail_checked": True,
                "detail_available": True,
                "detail": detail_data,
                "raw_api_url": _build_detail_api_url(item["articleId"]),
                "employee_url": _build_detail_page_url("600007", item["articleId"]),
                "structured_attachments": [],
            },
        )

        self.assertEqual(notice.project_code, "")
        self.assertEqual(notice.qualification_summary, "未提取到")
        self.assertEqual(notice.bid_open_or_response_deadline, "")
        self.assertIn("deadline 缺失不能视为 parser 必然失败", notice.detail_risk_note or "")
        self.assertIn("qualification_summary 缺失不能视为 parser 必然失败", notice.detail_risk_note or "")

    def test_crawl_collects_partial_stats(self) -> None:
        with (
            mock.patch.object(self.adapter, "_post_json", return_value=self.list_payload),
            mock.patch.object(self.adapter, "_get_json", return_value=self.detail_payload),
        ):
            notices = self.adapter.crawl()

        self.assertEqual(len(notices), 3)
        self.assertEqual(self.adapter.last_crawl_stats["list_count"], 3)
        self.assertEqual(self.adapter.last_crawl_stats["detail_success_count"], 3)
        self.assertEqual(self.adapter.last_crawl_stats["detail_failed_count"], 0)

    def test_source_config_and_catalog_keep_zhejiang_disabled_and_alpha(self) -> None:
        sources = json.loads(Path("D:/TenderRadarLite/config/sources.json").read_text(encoding="utf-8"))
        source = next(item for item in sources if item["name"] == "Zhejiang Government Procurement")
        self.assertFalse(source["enabled"])
        self.assertEqual(source["source"], "浙江政府采购网")
        self.assertEqual(source["source_subtype"], "政府采购 / JSON门户流")

        catalog = load_source_catalog()
        catalog_entry = find_source_by_id(catalog, "zhejiang-government-procurement")
        self.assertIsNotNone(catalog_entry)
        self.assertEqual(catalog_entry["status"], "alpha")
        self.assertEqual(catalog_entry["adapter"], "app.adapters.zhejiang_procurement")


if __name__ == "__main__":
    unittest.main()
