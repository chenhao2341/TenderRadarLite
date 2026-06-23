from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.adapters.ccgp_local import (
    BROWSER_HEADERS,
    CcgpLocalAdapter,
    _build_dedupe_key,
    _normalize_detail_url,
    _normalize_detail_deadline,
)
from app.source_catalog import find_source_by_id, load_source_catalog
from app.storage import Storage


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "ccgp_local"


def _read_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


class CcgpLocalAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fetcher = mock.Mock()
        self.fetcher.timeout = 20
        self.adapter = CcgpLocalAdapter(
            source_name="China Government Procurement Local",
            url="https://www.ccgp.gov.cn/cggg/dfgg/",
            region="全国",
            fetcher=self.fetcher,
            source_config={
                "name": "China Government Procurement Local",
                "source": "中国政府采购网",
                "source_subtype": "地方公告",
                "region": "全国",
                "enabled": False,
                "page_size": 20,
            },
        )

    def test_browser_headers_include_required_browser_like_fields(self) -> None:
        self.assertIn("Mozilla/5.0", self.adapter.browser_headers["User-Agent"])
        self.assertIn("text/html", self.adapter.browser_headers["Accept"])
        self.assertEqual(self.adapter.browser_headers["Accept-Language"], BROWSER_HEADERS["Accept-Language"])

    def test_fetch_list_parses_fixture_and_preserves_descending_top_10(self) -> None:
        with mock.patch.object(
            self.adapter,
            "_request_text",
            return_value=(_read_fixture("list_page_1.html"), 200, None),
        ):
            items = self.adapter.fetch_list()

        self.assertEqual(len(items), 10)
        self.assertEqual(items[0]["notice_title"], "尖扎县某单位办公用品采购项目的更正公告")
        self.assertEqual(items[0]["notice_type"], "更正公告")
        self.assertEqual(items[0]["region"], "青海")
        self.assertEqual(items[0]["purchaser_or_tenderer"], "尖扎县公安局")
        self.assertEqual(
            items[0]["canonical_detail_url"],
            "https://www.ccgp.gov.cn/cggg/dfgg/gzgg/202606/t20260621_26784713.htm",
        )
        top_10_times = [item["publish_time"] for item in items[:10]]
        self.assertEqual(top_10_times, sorted(top_10_times, reverse=True))
        self.assertEqual(items[7]["article_id"], "26784706")
        self.assertEqual(items[7]["dedupe_key"], "中国政府采购网-地方公告|26784706")
        self.assertEqual(items[7]["raw_api_url"], "")
        self.assertEqual(items[7]["original_url"], items[7]["canonical_detail_url"])
        self.assertEqual(items[7]["employee_readable_url"], items[7]["canonical_detail_url"])

    def test_dedupe_key_falls_back_to_canonical_detail_url_when_article_id_missing(self) -> None:
        dedupe_key = _build_dedupe_key(
            source="中国政府采购网",
            source_subtype="地方公告",
            article_id="",
            canonical_url="https://www.ccgp.gov.cn/cggg/dfgg/custom/detail.htm",
        )
        self.assertEqual(
            dedupe_key,
            "中国政府采购网-地方公告|https://www.ccgp.gov.cn/cggg/dfgg/custom/detail.htm",
        )

    def test_open_bid_detail_extracts_project_code_budget_ceiling_deadline_and_qualification(self) -> None:
        item = {
            "notice_title": "黄陵县隆坊镇人民政府2026年果园更新改造苗木采购(二次)招标公告",
            "notice_type": "公开招标",
            "publish_time": "2026-06-21 22:12:00",
            "region": "陕西",
            "purchaser_or_tenderer": "黄陵县隆坊镇人民政府",
            "canonical_detail_url": "https://www.ccgp.gov.cn/cggg/dfgg/gkzb/202606/t20260621_26784706.htm",
            "article_id": "26784706",
        }
        with mock.patch.object(
            self.adapter,
            "_request_text",
            return_value=(_read_fixture("detail_open_bid.html"), 200, None),
        ):
            detail = self.adapter.fetch_detail(item)

        notice = self.adapter.normalize(item, detail)

        self.assertEqual(notice.project_code, "SXKRMZB2026-013.2B1")
        self.assertEqual(notice.budget_amount, "609.027250")
        self.assertEqual(notice.budget_amount_unit, "万元")
        self.assertEqual(notice.ceiling_price, "609.027250")
        self.assertEqual(notice.ceiling_price_unit, "万元")
        self.assertEqual(notice.bid_open_or_response_deadline, "2026-07-14 09:00:00")
        self.assertIn("第二十二条", notice.qualification_summary)
        self.assertIn("苗木一批", notice.content_summary)
        self.assertEqual(notice.source, "中国政府采购网")
        self.assertEqual(notice.source_subtype, "地方公告")
        self.assertEqual(notice.region, "陕西")
        self.assertEqual(notice.original_url, item["canonical_detail_url"])
        self.assertEqual(notice.employee_readable_url, item["canonical_detail_url"])
        self.assertEqual(notice.raw_api_url, "")
        self.assertTrue(notice.has_attachment)
        self.assertEqual(notice.attachment_count, 2)

    def test_consult_detail_extracts_project_code_budget_deadline_and_content_summary(self) -> None:
        item = {
            "notice_title": "枝江市综合防灾减灾指挥调度平台建设项目竞争性磋商公告",
            "notice_type": "竞争性磋商",
            "publish_time": "2026-06-21 22:28:00",
            "region": "湖北",
            "purchaser_or_tenderer": "枝江市水利和湖泊局",
            "canonical_detail_url": "https://www.ccgp.gov.cn/cggg/dfgg/jzxcs/202606/t20260621_26784710.htm",
            "article_id": "26784710",
        }
        with mock.patch.object(
            self.adapter,
            "_request_text",
            return_value=(_read_fixture("detail_consult.html"), 200, None),
        ):
            detail = self.adapter.fetch_detail(item)

        notice = self.adapter.normalize(item, detail)

        self.assertEqual(notice.project_code, "420583202606000511")
        self.assertEqual(notice.budget_amount, "105.500000")
        self.assertEqual(notice.budget_amount_unit, "万元")
        self.assertEqual(notice.bid_open_or_response_deadline, "2026-07-02 09:30:00")
        self.assertIn("综合防灾减灾指挥调度平台", notice.content_summary)
        self.assertIn("中小企业", notice.qualification_summary)

    def test_award_detail_keeps_missing_qualification_as_non_failure_and_filters_jiucuo(self) -> None:
        with mock.patch.object(
            self.adapter,
            "_request_text",
            return_value=(_read_fixture("detail_award.html"), 200, None),
        ):
            detail = self.adapter.fetch_detail(
                {
                    "canonical_detail_url": "https://www.ccgp.gov.cn/cggg/dfgg/zbgg/202606/t20260621_26784703.htm",
                }
            )
        notice = self.adapter.normalize(
            {
                "notice_title": "广州市信息技术职业学校2026年购置类项目（CZ2026-0445）结果公告",
                "notice_type": "中标公告",
                "publish_time": "2026-06-21 22:05:00",
                "region": "广东",
                "purchaser_or_tenderer": "广州市信息技术职业学校",
                "canonical_detail_url": "https://www.ccgp.gov.cn/cggg/dfgg/zbgg/202606/t20260621_26784703.htm",
                "article_id": "26784703",
            },
            detail,
        )

        self.assertTrue(detail["detail_available"])
        self.assertEqual(notice.project_code, "CZ2026-0445")
        self.assertEqual(notice.qualification_summary, "未提取到")
        self.assertEqual(notice.attachment_count, 2)
        self.assertTrue(all("jiucuo.html" not in attachment.url for attachment in notice.attachments))
        self.assertTrue(notice.attachments[0].url.startswith(notice.original_url + "#attachment-"))
        self.assertEqual(notice.raw_api_url, "")
        self.assertNotIn("资质要求未提取到", notice.detail_risk_note or "")

    def test_correction_notice_allows_missing_deadline_and_qualification(self) -> None:
        notice = self.adapter.normalize(
            {
                "notice_title": "测试更正公告",
                "notice_type": "更正公告",
                "publish_time": "2026-06-22 10:00:00",
                "region": "云南",
                "purchaser_or_tenderer": "测试采购人",
                "canonical_detail_url": "https://www.ccgp.gov.cn/cggg/dfgg/gzgg/test.htm",
                "article_id": "test-correction",
            },
            {
                "detail_checked": True,
                "detail_available": True,
                "detail_html": "<div>项目基本情况 原公告的采购项目编号： DHZC2026-G1-00447-DHSH-0014 更正内容：招标文件调整。</div>",
                "meta": {"采购项目编号": "DHZC2026-G1-00447-DHSH-0014"},
                "attachments": [],
                "raw_api_url": "",
                "employee_url": "https://www.ccgp.gov.cn/cggg/dfgg/gzgg/test.htm",
                "detail_risk_note": None,
                "status_code": 200,
            },
        )

        self.assertEqual(notice.project_code, "DHZC2026-G1-00447-DHSH-0014")
        self.assertNotIn("资质要求未提取到", notice.detail_risk_note or "")
        self.assertNotIn("截止时间未提取到", notice.detail_risk_note or "")

    def test_non_result_notice_marks_core_field_gaps_in_detail_risk_note(self) -> None:
        notice = self.adapter.normalize(
            {
                "notice_title": "测试竞争性磋商公告",
                "notice_type": "竞争性磋商",
                "publish_time": "2026-06-22 10:00:00",
                "region": "山西",
                "purchaser_or_tenderer": "测试采购人",
                "canonical_detail_url": "https://www.ccgp.gov.cn/cggg/dfgg/jzxcs/test.htm",
                "article_id": "test-core-gap",
            },
            {
                "detail_checked": True,
                "detail_available": True,
                "detail_html": "<div>详见采购文件</div>",
                "meta": {},
                "attachments": [{"title": "附件1.pdf", "url": "https://example.com/a.pdf", "file_type": "", "source_section": "附件"}],
                "raw_api_url": "",
                "employee_url": "https://www.ccgp.gov.cn/cggg/dfgg/jzxcs/test.htm",
                "detail_risk_note": None,
                "status_code": 200,
            },
        )

        self.assertIn("项目内容摘要未提取到", notice.detail_risk_note or "")
        self.assertIn("资质要求未提取到", notice.detail_risk_note or "")
        self.assertIn("项目编号未提取到", notice.detail_risk_note or "")
        self.assertIn("截止时间未提取到", notice.detail_risk_note or "")
        self.assertIn("预算金额/限价未提取到", notice.detail_risk_note or "")

    def test_nested_detail_html_keeps_following_sections_for_non_result_notice(self) -> None:
        item = {
            "notice_title": "横桥镇文侯村机械购置项目采购公告",
            "notice_type": "公开招标",
            "publish_time": "2026-06-22 00:00:00",
            "region": "山西",
            "purchaser_or_tenderer": "横桥镇人民政府",
            "canonical_detail_url": "https://www.ccgp.gov.cn/cggg/dfgg/gkzb/202606/t20260622_26784726.htm",
            "article_id": "26784726",
        }
        nested_html = """
        <div class="vF_detail_content_container">
          <div class="vF_detail_content">
            <div><div style="border:1px solid"><div style="font-family:FangSong;">
              <p>项目概况</p>
              <p>横桥镇文侯村机械购置项目招标项目的潜在投标人应在政采云平台线上获取招标文件，并于2026年07月13日 08:30前递交投标文件。</p>
            </div></div></div>
            <p><strong>一、项目基本情况</strong></p>
            <div>
              <p>项目编号：1408252026AGK00058</p>
              <p>采购需求：采购拖拉机、旋耕机及相关配套设备。</p>
              <p>申请人的资格要求：满足《中华人民共和国政府采购法》第二十二条规定；本项目的特定资格要求：具备相关供货能力。</p>
            </div>
          </div>
        </div>
        """
        with mock.patch.object(self.adapter, "_request_text", return_value=(nested_html, 200, None)):
            detail = self.adapter.fetch_detail(item)

        notice = self.adapter.normalize(item, detail)

        self.assertEqual(notice.project_code, "1408252026AGK00058")
        self.assertEqual(notice.bid_open_or_response_deadline, "2026-07-13 08:30:00")
        self.assertIn("第二十二条", notice.qualification_summary)
        self.assertIn("拖拉机", notice.content_summary)
        self.assertNotIn("项目编号未提取到", notice.detail_risk_note or "")

    def test_deadline_parser_supports_chinese_hour_minute_format(self) -> None:
        detail_text = "项目概况 某项目采购项目的潜在供应商应在某地获取采购文件，并于2026年06月25日 09时30分（北京时间）前提交响应文件。"
        deadline = _normalize_detail_deadline({}, detail_text, "竞争性谈判")
        self.assertEqual(deadline, "2026-06-25 09:30:00")

    def test_deadline_parser_does_not_treat_file_get_time_as_bid_deadline(self) -> None:
        deadline = _normalize_detail_deadline(
            {"获取采购文件时间": "2026年06月22日至2026年06月24日"},
            "仅包含获取采购文件时间：2026年06月22日至2026年06月24日。",
            "竞争性磋商",
        )
        self.assertEqual(deadline, "")

    def test_fetch_detail_marks_403_with_clear_note(self) -> None:
        with mock.patch.object(
            self.adapter,
            "_request_text",
            return_value=(None, 403, "请求被拒绝(403)，该来源需要浏览器型请求头"),
        ):
            detail = self.adapter.fetch_detail(
                {
                    "canonical_detail_url": "https://www.ccgp.gov.cn/cggg/dfgg/gkzb/202606/t20260621_26784706.htm",
                }
            )

        self.assertFalse(detail["detail_available"])
        self.assertEqual(detail["status_code"], 403)
        self.assertIn("403", detail["detail_risk_note"])

    def test_source_config_and_catalog_keep_ccgp_local_disabled_and_alpha(self) -> None:
        sources = json.loads(Path("D:/TenderRadarLite/config/sources.json").read_text(encoding="utf-8"))
        source = next(item for item in sources if item["name"] == "China Government Procurement Local")
        self.assertFalse(source["enabled"])
        self.assertEqual(source["source"], "中国政府采购网")
        self.assertEqual(source["source_subtype"], "地方公告")

        catalog = load_source_catalog()
        catalog_entry = find_source_by_id(catalog, "china-government-procurement-local")
        self.assertIsNotNone(catalog_entry)
        self.assertEqual(catalog_entry["status"], "alpha")


    def test_detail_url_normalization_trims_and_drops_fragment(self) -> None:
        normalized = _normalize_detail_url(
            " /cggg/dfgg/gkzb/202606/t20260621_26784706.htm?foo=1#section ",
            "https://www.ccgp.gov.cn/cggg/dfgg/",
        )
        self.assertEqual(
            normalized,
            "https://www.ccgp.gov.cn/cggg/dfgg/gkzb/202606/t20260621_26784706.htm?foo=1",
        )

    def test_same_fixture_batch_is_duplicate_on_second_save(self) -> None:
        with mock.patch.object(
            self.adapter,
            "_request_text",
            return_value=(_read_fixture("list_page_1.html"), 200, None),
        ):
            items = self.adapter.fetch_list()

        detail_html_map = {
            "26784706": _read_fixture("detail_open_bid.html"),
            "26784710": _read_fixture("detail_consult.html"),
            "26784703": _read_fixture("detail_award.html"),
        }

        def fake_request_text(url: str) -> tuple[str | None, int | None, str | None]:
            article_id = url.rsplit("_", 1)[-1].split(".", 1)[0]
            html = detail_html_map.get(article_id)
            if html is not None:
                return html, 200, None
            return "<div></div>", 200, None

        with mock.patch.object(self.adapter, "_request_text", side_effect=fake_request_text):
            notices = [self.adapter.normalize(item, self.adapter.fetch_detail(item)) for item in items]

        fd, raw_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.unlink(raw_path)
        storage = Storage(Path(raw_path))
        first_inserted = sum(1 for notice in notices if storage.save_notice(notice))
        second_inserted = sum(1 for notice in notices if storage.save_notice(notice))
        del storage

        self.assertEqual(first_inserted, len(notices))
        self.assertEqual(second_inserted, 0)


if __name__ == "__main__":
    unittest.main()
