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


if __name__ == "__main__":
    unittest.main()
