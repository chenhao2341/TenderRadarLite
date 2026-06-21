from __future__ import annotations

import unittest


class HengyangProcurementAdapterTests(unittest.TestCase):
    def test_build_hengyang_list_url_adds_verified_frontend_params(self) -> None:
        from app.adapters.hengyang_procurement import _build_hengyang_list_url

        url = _build_hengyang_list_url(
            "https://hengyang.hnsggzy.com/tradeApi/governmentPurchase/"
            "projectInformation/selectAll?regionCode=430400&current=9&size=99"
        )

        self.assertEqual(
            url,
            "https://hengyang.hnsggzy.com/tradeApi/governmentPurchase/"
            "projectInformation/selectAll?regionCode=430400&current=1&size=10"
            "&descs=noticeSendTime&notice=1&tenderMode=%E5%85%AC%E5%BC%80%E6%8B%9B%E6%A0%87",
        )

    def test_build_employee_readable_url_uses_frontend_hash_route(self) -> None:
        from app.adapters.hengyang_procurement import _build_employee_readable_url

        url = _build_employee_readable_url(
            origin="https://hengyang.hnsggzy.com",
            project_id="proj-1",
            region_code="430400",
            section_id="sec-1",
        )

        self.assertEqual(
            url,
            "https://hengyang.hnsggzy.com/#/resources/projectDetail/governmentPurchase"
            "?id=proj-1&regionCode=430400&bidSectionId=sec-1&default=projectInfo",
        )

    def test_normalize_region_code_uses_readable_city_name(self) -> None:
        from app.adapters.hengyang_procurement import HengyangProcurementAdapter

        adapter = HengyangProcurementAdapter(
            "Hengyang Procurement",
            "https://hengyang.hnsggzy.com/tradeApi/governmentPurchase/projectInformation/selectAll?regionCode=430400",
            "衡阳",
            _FakeFetcher(),
            {"source": "衡阳分平台", "source_subtype": "政府采购交易"},
        )

        notice = adapter.normalize(
            {
                "bidSectionId": "sec-1",
                "projectId": "proj-1",
                "purchaseProjectName": "项目A",
                "purchaseSectionName": "项目A包1",
                "noticeSendTime": "2026-06-22 10:00:00",
                "noticeType": "ZHAOBIAO_NOTICE",
                "regionCode": "430400",
            },
            {
                "detail_checked": True,
                "detail_available": True,
                "employee_url": "https://example.com/readable",
                "raw_api_url": "https://example.com/tradeApi/detail",
                "detail": {
                    "governmentProcurementProjectInformation": {
                        "purchaseProjectName": "项目A",
                        "purchaseProjectCode": "CODE-1",
                        "regionCode": "430400",
                        "purchaserName": "采购人A",
                        "purchaserAgencyName": "代理A",
                    },
                    "GovernmentProcureSectionInformationList": [
                        {
                            "purchaseSectionName": "项目A包1",
                            "tenderType": "公开招标",
                        }
                    ],
                    "GovernmentPurchaseFile": [],
                },
                "announcement": {
                    "bulletinType": "招标公告",
                    "noticeSendTime": "2026-06-22T10:00:00.000+08:00",
                    "noticeContent": "<p>提交投标文件的截止时间：2026年07月08日 10:00</p>",
                },
            },
        )

        self.assertEqual(notice.region, "衡阳市")

    def test_extract_deadline_supports_additional_label_and_chinese_hour_minute(self) -> None:
        from app.adapters.hengyang_procurement import _extract_deadline_from_text

        deadline = _extract_deadline_from_text(
            "供应商应在获取招标文件后，并于2026年06月25日 09时30分前提交响应文件。"
            "提交响应文件截止时间以系统为准。"
        )

        self.assertEqual(deadline, "2026年06月25日09:30")

    def test_normalize_missing_deadline_adds_risk_note_for_tender_notice(self) -> None:
        from app.adapters.hengyang_procurement import HengyangProcurementAdapter

        adapter = HengyangProcurementAdapter(
            "Hengyang Procurement",
            "https://hengyang.hnsggzy.com/tradeApi/governmentPurchase/projectInformation/selectAll?regionCode=430400",
            "衡阳",
            _FakeFetcher(),
            {"source": "衡阳分平台", "source_subtype": "政府采购交易"},
        )

        notice = adapter.normalize(
            {
                "bidSectionId": "sec-2",
                "projectId": "proj-2",
                "purchaseProjectName": "项目B",
                "purchaseSectionName": "项目B包1",
                "noticeSendTime": "2026-06-22 10:00:00",
                "noticeType": "ZHAOBIAO_NOTICE",
                "regionName": "衡阳市",
            },
            {
                "detail_checked": True,
                "detail_available": True,
                "employee_url": "https://example.com/readable",
                "raw_api_url": "https://example.com/tradeApi/detail",
                "detail": {
                    "governmentProcurementProjectInformation": {
                        "purchaseProjectName": "项目B",
                        "purchaseProjectCode": "CODE-2",
                        "purchaserName": "采购人B",
                        "purchaserAgencyName": "代理B",
                    },
                    "GovernmentProcureSectionInformationList": [
                        {
                            "purchaseSectionName": "项目B包1",
                            "tenderType": "公开招标",
                        }
                    ],
                    "GovernmentPurchaseFile": [{"fileId": "f-1"}],
                },
                "announcement": {
                    "bulletinType": "招标公告",
                    "noticeSendTime": "2026-06-22T10:00:00.000+08:00",
                    "noticeContent": "<p>项目概况：详见招标文件。</p>",
                },
                "structured_attachments": [{"fileId": "f-1"}],
            },
        )

        self.assertEqual(notice.bid_open_or_response_deadline, "")
        self.assertIn("招标/采购类公告未提取到截止时间", notice.detail_risk_note or "")
        self.assertIn("附件仅做发现，未下载或解析", notice.detail_risk_note or "")


class _FakeFetcher:
    timeout = 20


if __name__ == "__main__":
    unittest.main()
