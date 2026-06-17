from __future__ import annotations

import unittest

from app.models import Notice
from app.opportunity_stage import classify_opportunity_stage


class OpportunityStageTests(unittest.TestCase):
    def _notice(self, title: str, *, notice_type: str = "", summary: str = "") -> Notice:
        return Notice(
            source="source",
            source_subtype="construction",
            dedupe_key=title,
            section_id=title,
            project_name=title,
            notice_title=title,
            notice_type=notice_type,
            content_summary=summary,
            lead_tier="DIRECT",
        )

    def test_bid_and_procurement_notices_are_new_opportunities(self) -> None:
        self.assertEqual(classify_opportunity_stage(self._notice("片区规划设计服务招标公告")), "new_opportunity")
        self.assertEqual(classify_opportunity_stage(self._notice("设计咨询服务采购公告")), "new_opportunity")

    def test_corrections_clarifications_and_answers_are_not_new_opportunities(self) -> None:
        self.assertEqual(classify_opportunity_stage(self._notice("设计服务更正公告")), "correction_or_clarification")
        self.assertEqual(classify_opportunity_stage(self._notice("设计服务澄清答疑公告")), "correction_or_clarification")

    def test_failed_terminated_and_rebid_notices_are_rebid_signals(self) -> None:
        self.assertEqual(classify_opportunity_stage(self._notice("设计服务流标公告")), "rebid_signal")
        self.assertEqual(classify_opportunity_stage(self._notice("设计服务废标后重新招标公告")), "rebid_signal")

    def test_awards_and_contracts_are_results(self) -> None:
        self.assertEqual(classify_opportunity_stage(self._notice("设计服务中标候选人公示")), "award_result")
        self.assertEqual(classify_opportunity_stage(self._notice("设计服务成交结果公告")), "award_result")

    def test_material_equipment_and_pure_construction_are_procurement_mismatch(self) -> None:
        self.assertEqual(classify_opportunity_stage(self._notice("管材采购项目招标公告")), "mismatch_procurement")
        self.assertEqual(classify_opportunity_stage(self._notice("施工总承包招标公告")), "mismatch_procurement")


if __name__ == "__main__":
    unittest.main()
