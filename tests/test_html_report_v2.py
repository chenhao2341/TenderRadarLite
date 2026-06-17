from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.company_profile import CompanyProfile
from app.html_report import _company_zone_for_notice, write_html_report
from app.models import Notice


class HtmlReportV2Tests(unittest.TestCase):
    def _notice(
        self,
        *,
        project_name: str,
        suffix: str,
        lead_tier: str,
        section_id: str,
        notice_type: str,
        publish_time: str,
    ) -> Notice:
        return Notice(
            source="source",
            source_subtype="construction",
            dedupe_key=f"source|{suffix}",
            section_id=section_id,
            project_name=project_name,
            notice_id=f"notice-{suffix}",
            notice_type=notice_type,
            purchaser_or_tenderer="Tenderer",
            agency="Agency",
            region="Hengyang",
            publish_time=publish_time,
            bid_open_or_response_deadline="2026-06-20 09:00:00",
            budget_amount="1000",
            ceiling_price="900",
            content_summary="Content summary",
            qualification_summary="Qualification summary",
            employee_readable_url=f"https://example.com/{suffix}",
            hit_keywords=["design"],
            lead_tier=lead_tier,
            lead_reason=f"{lead_tier} reason",
            matched_positive_signals=["design service"],
            matched_negative_signals=["construction"] if lead_tier == "EXCLUDE" else [],
            fetched_at="2026-06-15 12:00:00",
        )

    def test_report_aggregates_related_notices_into_one_project_card(self) -> None:
        notices = [
            self._notice(
                project_name="Direct Project",
                suffix="direct-a",
                lead_tier="DIRECT",
                section_id="section-1",
                notice_type="ZHAOBIAO_NOTICE",
                publish_time="2026-06-15 10:00:00",
            ),
            self._notice(
                project_name="Direct Project",
                suffix="direct-b",
                lead_tier="WATCHLIST",
                section_id="section-1",
                notice_type="GENGZHENG_NOTICE",
                publish_time="2026-06-16 10:00:00",
            ),
            self._notice(
                project_name="Watch Project",
                suffix="watch-a",
                lead_tier="WATCHLIST",
                section_id="section-2",
                notice_type="CHENGQING_NOTICE",
                publish_time="2026-06-14 10:00:00",
            ),
            self._notice(
                project_name="Exclude Project",
                suffix="exclude-a",
                lead_tier="EXCLUDE",
                section_id="section-3",
                notice_type="ZANTING_NOTICE",
                publish_time="2026-06-13 10:00:00",
            ),
        ]

        with tempfile.TemporaryDirectory() as raw_dir:
            report_path = Path(raw_dir) / "latest.html"
            write_html_report(report_path, notices, source_count=1, generated_at="2026-06-15 12:00:00")
            html = report_path.read_text(encoding="utf-8")

        self.assertIn("TenderRadarLite 本地招投标线索报告", html)
        self.assertIn("本轮公告数", html)
        self.assertIn("聚合项目数", html)
        self.assertIn("4", html)
        self.assertIn("3", html)
        self.assertEqual(html.count("Direct Project"), 1)
        self.assertIn("关联公告 2 条", html)
        self.assertIn("招标公告", html)
        self.assertIn("更正公告", html)
        self.assertIn("DIRECT reason", html)
        self.assertIn("打开原文", html)

    def test_report_deemphasizes_exclude_section_with_collapsed_panel(self) -> None:
        notices = [
            self._notice(
                project_name="Exclude Project",
                suffix="exclude-a",
                lead_tier="EXCLUDE",
                section_id="section-3",
                notice_type="ZANTING_NOTICE",
                publish_time="2026-06-13 10:00:00",
            )
        ]

        with tempfile.TemporaryDirectory() as raw_dir:
            report_path = Path(raw_dir) / "latest.html"
            write_html_report(report_path, notices, source_count=1, generated_at="2026-06-15 12:00:00")
            html = report_path.read_text(encoding="utf-8")

        self.assertIn("<details class=\"exclude-panel\"", html)
        self.assertIn("EXCLUDE 排除项", html)
        self.assertIn("暂停公告", html)
        self.assertNotIn("https://cdn.", html)
        self.assertNotIn("node_modules", html.lower())
        self.assertNotIn("react", html.lower())
        self.assertNotIn("vite", html.lower())

    def test_report_renders_empty_state(self) -> None:
        with tempfile.TemporaryDirectory() as raw_dir:
            report_path = Path(raw_dir) / "latest.html"
            write_html_report(report_path, [], source_count=0, generated_at="2026-06-15 12:00:00")
            html = report_path.read_text(encoding="utf-8")

        self.assertIn("本轮未发现新线索", html)
        self.assertIn("检查来源配置或稍后再运行", html)

    def test_report_prefers_related_notice_qualification_summary_over_representative_gap(self) -> None:
        direct_notice = self._notice(
            project_name="Merged Project",
            suffix="merged-direct",
            lead_tier="DIRECT",
            section_id="section-merged",
            notice_type="ZANTING_NOTICE",
            publish_time="2026-06-16 10:00:00",
        )
        direct_notice.qualification_summary = ""
        direct_notice.content_summary = "Short summary"

        related_notice = self._notice(
            project_name="Merged Project",
            suffix="merged-bid",
            lead_tier="WATCHLIST",
            section_id="section-merged",
            notice_type="ZHAOBIAO_NOTICE",
            publish_time="2026-06-15 10:00:00",
        )
        related_notice.qualification_summary = "Bidder must have grade-A architecture qualification and recent similar project experience."
        related_notice.content_summary = "This notice contains the fuller content summary for the merged project."

        with tempfile.TemporaryDirectory() as raw_dir:
            report_path = Path(raw_dir) / "latest.html"
            write_html_report(report_path, [direct_notice, related_notice], source_count=1, generated_at="2026-06-15 12:00:00")
            html = report_path.read_text(encoding="utf-8")

        self.assertIn("grade-A architecture qualification", html)
        self.assertIn("fuller content summary", html)
        self.assertIn("资质要求摘要来源：招标公告", html)
        self.assertIn("项目内容摘要来源：招标公告", html)

    def test_report_prefers_longer_summary_when_multiple_related_notices_have_content(self) -> None:
        shorter_notice = self._notice(
            project_name="Long Summary Project",
            suffix="summary-short",
            lead_tier="WATCHLIST",
            section_id="section-summary",
            notice_type="CHENGQING_NOTICE",
            publish_time="2026-06-16 10:00:00",
        )
        shorter_notice.qualification_summary = "Short requirement."
        shorter_notice.content_summary = "Short content."

        longer_notice = self._notice(
            project_name="Long Summary Project",
            suffix="summary-long",
            lead_tier="EXCLUDE",
            section_id="section-summary",
            notice_type="ZHAOBIAO_NOTICE",
            publish_time="2026-06-15 10:00:00",
        )
        longer_notice.qualification_summary = (
            "Longer qualification summary with more detail about staffing, licensing, design leadership, and comparable public projects."
        )
        longer_notice.content_summary = (
            "Longer content summary describing renovation scope, public space upgrades, smart systems, and phased construction requirements."
        )

        with tempfile.TemporaryDirectory() as raw_dir:
            report_path = Path(raw_dir) / "latest.html"
            write_html_report(report_path, [shorter_notice, longer_notice], source_count=1, generated_at="2026-06-15 12:00:00")
            html = report_path.read_text(encoding="utf-8")

        self.assertIn("Longer qualification summary with more detail", html)
        self.assertIn("Longer content summary describing renovation scope", html)

    def test_report_falls_back_to_missing_summary_only_when_all_related_notices_are_empty(self) -> None:
        notice_a = self._notice(
            project_name="Missing Summary Project",
            suffix="missing-a",
            lead_tier="WATCHLIST",
            section_id="section-missing",
            notice_type="CHENGQING_NOTICE",
            publish_time="2026-06-16 10:00:00",
        )
        notice_b = self._notice(
            project_name="Missing Summary Project",
            suffix="missing-b",
            lead_tier="EXCLUDE",
            section_id="section-missing",
            notice_type="GENGZHENG_NOTICE",
            publish_time="2026-06-15 10:00:00",
        )
        notice_a.qualification_summary = ""
        notice_b.qualification_summary = "未提取到"
        notice_a.content_summary = ""
        notice_b.content_summary = "未提取到"

        with tempfile.TemporaryDirectory() as raw_dir:
            report_path = Path(raw_dir) / "latest.html"
            write_html_report(report_path, [notice_a, notice_b], source_count=1, generated_at="2026-06-15 12:00:00")
            html = report_path.read_text(encoding="utf-8")

        self.assertIn("未提取到", html)
        self.assertIn("可能原因：资质要求可能在招标文件 / PDF / 附件中，当前本地报告暂未解析附件。", html)

    def test_direct_and_watchlist_show_qualification_summary_without_extra_click(self) -> None:
        direct_notice = self._notice(
            project_name="Direct Qualification Project",
            suffix="direct-qualification",
            lead_tier="DIRECT",
            section_id="section-direct-qualification",
            notice_type="ZHAOBIAO_NOTICE",
            publish_time="2026-06-16 10:00:00",
        )
        direct_notice.qualification_summary = "Direct qualification summary shown by default."

        watch_notice = self._notice(
            project_name="Watch Qualification Project",
            suffix="watch-qualification",
            lead_tier="WATCHLIST",
            section_id="section-watch-qualification",
            notice_type="ZHAOBIAO_NOTICE",
            publish_time="2026-06-15 10:00:00",
        )
        watch_notice.qualification_summary = "Watch qualification summary shown by default."

        with tempfile.TemporaryDirectory() as raw_dir:
            report_path = Path(raw_dir) / "latest.html"
            write_html_report(report_path, [direct_notice, watch_notice], source_count=1, generated_at="2026-06-15 12:00:00")
            html = report_path.read_text(encoding="utf-8")

        self.assertIn("Direct qualification summary shown by default.", html)
        self.assertIn("Watch qualification summary shown by default.", html)
        self.assertNotIn("<summary>资质要求摘要</summary>", html)

    def test_long_qualification_summary_supports_expand_for_full_text(self) -> None:
        notice = self._notice(
            project_name="Long Qualification Project",
            suffix="long-qualification",
            lead_tier="DIRECT",
            section_id="section-long-qualification",
            notice_type="ZHAOBIAO_NOTICE",
            publish_time="2026-06-16 10:00:00",
        )
        notice.qualification_summary = " ".join(f"requirement-{index:02d}" for index in range(120))

        with tempfile.TemporaryDirectory() as raw_dir:
            report_path = Path(raw_dir) / "latest.html"
            write_html_report(report_path, [notice], source_count=1, generated_at="2026-06-15 12:00:00")
            html = report_path.read_text(encoding="utf-8")

        self.assertIn('<details class="qualification-details">', html)
        self.assertIn("展开完整资质要求", html)
        self.assertIn("requirement-119", html)
        self.assertIn("requirement-00 requirement-01", html)
        self.assertIn("...", html)

    def test_short_qualification_summary_does_not_force_expand_control(self) -> None:
        notice = self._notice(
            project_name="Short Qualification Project",
            suffix="short-qualification",
            lead_tier="WATCHLIST",
            section_id="section-short-qualification",
            notice_type="ZHAOBIAO_NOTICE",
            publish_time="2026-06-16 10:00:00",
        )
        notice.qualification_summary = "Short qualification summary without extra expansion."

        with tempfile.TemporaryDirectory() as raw_dir:
            report_path = Path(raw_dir) / "latest.html"
            write_html_report(report_path, [notice], source_count=1, generated_at="2026-06-15 12:00:00")
            html = report_path.read_text(encoding="utf-8")

        self.assertNotIn('<details class="qualification-details">', html)
        self.assertNotIn("展开完整资质要求", html)


    def test_company_profile_report_adds_four_zone_business_view(self) -> None:
        high = self._notice(
            project_name="Priority Design Project",
            suffix="priority",
            lead_tier="DIRECT",
            section_id="section-priority",
            notice_type="ZHAOBIAO_NOTICE",
            publish_time="2026-06-16 10:00:00",
        )
        high.opportunity_stage = "new_opportunity"
        high.company_match_score = 86
        high.company_match_level = "high"
        high.company_match_reasons = ["命中规划设计", "地区匹配"]

        review = self._notice(
            project_name="Review Clarification Project",
            suffix="review",
            lead_tier="WATCHLIST",
            section_id="section-review",
            notice_type="GENGZHENG_NOTICE",
            publish_time="2026-06-16 09:00:00",
        )
        review.opportunity_stage = "correction_or_clarification"
        review.company_match_score = 62
        review.company_match_level = "medium"
        review.company_match_reasons = ["命中咨询服务"]
        review.manual_review_items = ["更正/澄清公告不是全新机会"]

        low = self._notice(
            project_name="Pipe Procurement Project",
            suffix="low",
            lead_tier="EXCLUDE",
            section_id="section-low",
            notice_type="ZHAOBIAO_NOTICE",
            publish_time="2026-06-15 09:00:00",
        )
        low.opportunity_stage = "mismatch_procurement"
        low.company_match_score = 18
        low.company_match_level = "mismatch"
        low.company_mismatch_reasons = ["命中设备采购"]

        with tempfile.TemporaryDirectory() as raw_dir:
            report_path = Path(raw_dir) / "latest.html"
            write_html_report(
                report_path,
                [high, review, low],
                source_count=1,
                generated_at="2026-06-15 12:00:00",
                company_profile=CompanyProfile(company_name="测试设计咨询公司"),
            )
            html = report_path.read_text(encoding="utf-8")

        self.assertIn("企业商机视图", html)
        self.assertIn("今日优先跟进", html)
        self.assertIn("建议人工复核", html)
        self.assertIn("项目动态", html)
        self.assertIn("低优先级或不匹配", html)
        self.assertIn("新机会", html)
        self.assertIn("企业匹配分", html)
        self.assertIn("Priority Design Project", html)
        self.assertIn("Pipe Procurement Project", html)

    def test_default_report_does_not_force_company_business_view(self) -> None:
        notice = self._notice(
            project_name="Public Mode Project",
            suffix="public-mode",
            lead_tier="DIRECT",
            section_id="section-public-mode",
            notice_type="ZHAOBIAO_NOTICE",
            publish_time="2026-06-16 10:00:00",
        )
        notice.company_match_score = 90
        notice.company_match_level = "high"

        with tempfile.TemporaryDirectory() as raw_dir:
            report_path = Path(raw_dir) / "latest.html"
            write_html_report(report_path, [notice], source_count=1, generated_at="2026-06-15 12:00:00")
            html = report_path.read_text(encoding="utf-8")

        self.assertNotIn("企业商机视图", html)
        self.assertNotIn("今日优先跟进", html)
        self.assertIn("DIRECT", html)


class CompanyBusinessZoneTests(unittest.TestCase):
    def _notice(self) -> Notice:
        return Notice(
            source="source",
            source_subtype="construction",
            dedupe_key="source|zone",
            section_id="section-zone",
            project_name="Zone Project",
            notice_id="notice-zone",
            notice_title="Zone Project",
            notice_type="ZHAOBIAO_NOTICE",
            publish_time="2026-06-16 10:00:00",
            bid_open_or_response_deadline="2026-06-20 09:00:00",
            lead_tier="DIRECT",
        )

    def test_company_today_zone_requires_strong_match_signal(self) -> None:
        notice = self._notice()
        notice.opportunity_stage = "new_opportunity"
        notice.company_match_score = 82
        notice.company_match_level = "high"
        notice.company_match_reasons = [
            "\u547d\u4e2d\u8bbe\u8ba1\u54a8\u8be2\u76f8\u5173\u8bcd\uff1a\u8bbe\u8ba1\u3001\u54a8\u8be2\u3001\u89c4\u5212",
            "\u4ec5\u4e3a\u5f31\u5339\u914d\u8bcd\uff0c\u9700\u7ed3\u5408\u539f\u516c\u544a\u786e\u8ba4",
        ]

        self.assertEqual(_company_zone_for_notice(notice), "review")

    def test_company_today_zone_requires_no_obvious_exclusion_signal(self) -> None:
        notice = self._notice()
        notice.opportunity_stage = "new_opportunity"
        notice.company_match_score = 80
        notice.company_match_level = "high"
        notice.company_match_reasons = ["\u547d\u4e2d\u5f3a\u5339\u914d\u8bcd\uff1a\u5de5\u7a0b\u54a8\u8be2"]
        notice.company_mismatch_reasons = ["\u547d\u4e2d\u6392\u9664\u7c7b\u578b\uff1a\u8bbe\u5907\u91c7\u8d2d"]

        self.assertEqual(_company_zone_for_notice(notice), "review")

    def test_company_today_zone_accepts_new_high_strong_signal_without_exclusion(self) -> None:
        notice = self._notice()
        notice.opportunity_stage = "new_opportunity"
        notice.company_match_score = 86
        notice.company_match_level = "high"
        notice.company_match_reasons = ["\u547d\u4e2d\u5f3a\u5339\u914d\u8bcd\uff1a\u52d8\u5bdf\u8bbe\u8ba1\u3001\u5de5\u7a0b\u54a8\u8be2"]

        self.assertEqual(_company_zone_for_notice(notice), "today")


if __name__ == "__main__":
    unittest.main()
