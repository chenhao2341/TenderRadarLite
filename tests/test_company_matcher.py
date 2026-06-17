from __future__ import annotations

import unittest

from app.company_matcher import apply_company_match, match_company_profile
from app.company_profile import CompanyProfile
from app.models import AttachmentInfo, Notice


class CompanyMatcherTests(unittest.TestCase):
    def _profile(self) -> CompanyProfile:
        return CompanyProfile(
            company_name="\u6d4b\u8bd5\u8bbe\u8ba1\u54a8\u8be2\u516c\u53f8",
            regions=["\u6e56\u5357", "\u8861\u9633"],
            business_scope=[
                "\u89c4\u5212\u8bbe\u8ba1",
                "\u5de5\u7a0b\u54a8\u8be2",
                "\u53ef\u7814\u62a5\u544a",
                "\u52d8\u5bdf\u8bbe\u8ba1",
            ],
            target_project_types=[
                "\u8bbe\u8ba1\u670d\u52a1",
                "\u54a8\u8be2\u670d\u52a1",
                "\u53ef\u7814",
                "\u89c4\u5212\u7f16\u5236",
                "\u52d8\u5bdf",
            ],
            exclude_project_types=[
                "\u65bd\u5de5\u603b\u627f\u5305",
                "\u7eaf\u6750\u6599\u91c7\u8d2d",
                "\u8bbe\u5907\u91c7\u8d2d",
            ],
            qualifications=[
                "\u5de5\u7a0b\u54a8\u8be2\u5907\u6848",
                "\u5efa\u7b51\u884c\u4e1a\u8bbe\u8ba1\u4e59\u7ea7",
            ],
        )

    def _notice(self, title: str, *, summary: str = "", qualification: str = "", stage: str = "new_opportunity") -> Notice:
        return Notice(
            source="source",
            source_subtype="construction",
            dedupe_key=title,
            section_id=title,
            project_name=title,
            notice_title=title,
            region="\u8861\u9633",
            content_summary=summary,
            qualification_summary=qualification,
            bid_open_or_response_deadline="2026-07-01 09:00:00",
            lead_tier="DIRECT",
            opportunity_stage=stage,
        )

    def test_weak_design_terms_do_not_raise_notice_to_high_match(self) -> None:
        notice = self._notice(
            "\u67d0\u9879\u76ee\u8bbe\u8ba1\u54a8\u8be2\u610f\u5411\u5f81\u96c6",
            summary="\u516c\u544a\u4ec5\u63d0\u5230\u8bbe\u8ba1\u3001\u54a8\u8be2\u3001\u89c4\u5212\u7b49\u4e00\u822c\u63cf\u8ff0\uff0c\u672a\u660e\u786e\u5177\u4f53\u670d\u52a1\u7c7b\u578b",
        )

        result = match_company_profile(notice, self._profile(), today="2026-06-17")

        self.assertNotEqual(result.level, "high")
        self.assertLess(result.score, 70)
        self.assertTrue(any("\u5f31\u5339\u914d" in reason for reason in result.match_reasons))
        self.assertEqual(sum(1 for reason in result.match_reasons if reason.startswith("\u547d\u4e2d\u8bbe\u8ba1\u54a8\u8be2\u76f8\u5173\u8bcd")), 1)

    def test_strong_design_terms_allow_high_match(self) -> None:
        notice = self._notice(
            "\u7247\u533a\u52d8\u5bdf\u8bbe\u8ba1\u53ca\u5de5\u7a0b\u54a8\u8be2\u670d\u52a1\u62db\u6807\u516c\u544a",
            summary="\u5305\u542b\u52d8\u5bdf\u8bbe\u8ba1\u3001\u521d\u6b65\u8bbe\u8ba1\u3001\u65bd\u5de5\u56fe\u8bbe\u8ba1\u3001\u53ef\u884c\u6027\u7814\u7a76",
            qualification="\u9700\u5177\u5907\u5de5\u7a0b\u54a8\u8be2\u5907\u6848",
        )

        result = match_company_profile(notice, self._profile(), today="2026-06-17")

        self.assertEqual(result.level, "high")
        self.assertGreaterEqual(result.score, 70)
        self.assertTrue(any("\u5f3a\u5339\u914d" in reason for reason in result.match_reasons))

    def test_excluded_procurement_and_construction_signals_are_downgraded(self) -> None:
        notice = self._notice(
            "\u7ba1\u6750\u8bbe\u5907\u91c7\u8d2d\u53ca\u65bd\u5de5\u603b\u627f\u5305\u62db\u6807\u516c\u544a",
            summary="\u91c7\u8d2d\u7ba1\u6750\u3001\u8bbe\u5907\u5e76\u8981\u6c42\u5b89\u5168\u751f\u4ea7\u8bb8\u53ef\u8bc1",
        )

        result = match_company_profile(notice, self._profile(), today="2026-06-17")

        self.assertIn(result.level, {"low", "mismatch"})
        self.assertTrue(any("\u8bbe\u5907\u91c7\u8d2d" in reason or "\u65bd\u5de5\u603b\u627f\u5305" in reason for reason in result.mismatch_reasons))
        self.assertTrue(any("\u504f\u65bd\u5de5/\u91c7\u8d2d" in reason for reason in result.mismatch_reasons))

    def test_construction_license_signals_trigger_downgrade_or_review(self) -> None:
        notice = self._notice(
            "\u67d0\u7167\u660e\u5de5\u7a0b\u9879\u76ee\u516c\u544a",
            summary="\u516c\u544a\u63d0\u5230\u5b89\u5168\u751f\u4ea7\u8bb8\u53ef\u8bc1\u3001\u65bd\u5de5\u8d44\u8d28\uff0c\u5e76\u5305\u542b\u5b89\u88c5\u5de5\u7a0b\u5185\u5bb9",
        )

        result = match_company_profile(notice, self._profile(), today="2026-06-17")

        self.assertIn(result.level, {"medium", "low", "mismatch"})
        self.assertNotEqual(result.level, "high")
        self.assertTrue(any("\u5b89\u5168\u751f\u4ea7\u8bb8\u53ef\u8bc1" in reason or "\u65bd\u5de5\u8d44\u8d28" in reason for reason in result.mismatch_reasons))

    def test_unconfirmed_amount_unit_adds_manual_review_without_zeroing_match(self) -> None:
        notice = self._notice(
            "\u8bbe\u8ba1\u54a8\u8be2\u670d\u52a1\u91c7\u8d2d\u516c\u544a",
            summary="\u8bbe\u8ba1\u54a8\u8be2\u670d\u52a1",
        )
        notice.budget_amount = "5631.436489"
        notice.budget_amount_unit = ""

        result = match_company_profile(notice, self._profile(), today="2026-06-17")

        self.assertGreater(result.score, 0)
        self.assertTrue(any("\u91d1\u989d\u5355\u4f4d" in item for item in result.manual_review_items))
        self.assertFalse(any("\u4e0d\u5339\u914d" in reason for reason in result.mismatch_reasons))

    def test_correction_and_award_are_not_treated_as_priority_new_follow_up(self) -> None:
        correction = self._notice(
            "\u8bbe\u8ba1\u54a8\u8be2\u670d\u52a1\u6f84\u6e05\u516c\u544a",
            summary="\u8bbe\u8ba1\u54a8\u8be2\u670d\u52a1",
            stage="correction_or_clarification",
        )
        award = self._notice(
            "\u8bbe\u8ba1\u54a8\u8be2\u670d\u52a1\u6210\u4ea4\u7ed3\u679c\u516c\u544a",
            summary="\u8bbe\u8ba1\u54a8\u8be2\u670d\u52a1",
            stage="award_result",
        )

        correction_result = match_company_profile(correction, self._profile(), today="2026-06-17")
        award_result = match_company_profile(award, self._profile(), today="2026-06-17")

        self.assertLess(correction_result.score, 70)
        self.assertLess(award_result.score, 70)
        self.assertTrue(any("\u4e0d\u662f\u5168\u65b0\u673a\u4f1a" in item for item in correction_result.manual_review_items))
        self.assertTrue(any("\u7ed3\u679c\u516c\u544a" in reason for reason in award_result.mismatch_reasons))

    def test_apply_company_match_writes_notice_fields(self) -> None:
        notice = self._notice(
            "\u8bbe\u8ba1\u54a8\u8be2\u670d\u52a1\u91c7\u8d2d\u516c\u544a",
            summary="\u5305\u542b\u8bbe\u8ba1\u670d\u52a1\u3001\u5de5\u7a0b\u54a8\u8be2\u3001\u53ef\u7814",
        )
        notice.attachments = [AttachmentInfo(title="\u62db\u6807\u6587\u4ef6.pdf", url="https://example.com/file.pdf")]
        notice.attachments_found = 1
        notice.detail_checked = True
        notice.detail_available = True

        apply_company_match(notice, self._profile(), today="2026-06-17")

        self.assertEqual(notice.company_match_level, "high")
        self.assertGreaterEqual(notice.company_match_score, 70)
        self.assertTrue(notice.company_match_reasons)
        self.assertTrue(any("\u9644\u4ef6" in item for item in notice.manual_review_items))


if __name__ == "__main__":
    unittest.main()
