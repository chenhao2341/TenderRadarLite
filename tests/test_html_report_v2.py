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

    def _source_group_slice(self, html: str, source_label: str) -> str:
        start = html.index(source_label)
        return html[start : start + 1800]

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
        self.assertGreaterEqual(html.count("Direct Project"), 2)
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
        self.assertNotIn("EXCLUDEEXCLUDE 排除项", html)
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

    def test_report_renders_source_label_when_available(self) -> None:
        notice = self._notice(
            project_name="Changsha Project",
            suffix="changsha-source",
            lead_tier="EXCLUDE",
            section_id="section-changsha-source",
            notice_type="ZHAOBIAO_NOTICE",
            publish_time="2026-06-16 10:00:00",
        )
        notice.source = "长沙公共资源交易平台"
        notice.source_subtype = "长沙政府采购交易"

        with tempfile.TemporaryDirectory() as raw_dir:
            report_path = Path(raw_dir) / "latest.html"
            write_html_report(report_path, [notice], source_count=1, generated_at="2026-06-15 12:00:00")
            html = report_path.read_text(encoding="utf-8")

        self.assertIn("来源", html)
        self.assertIn("长沙公共资源交易平台 / 长沙政府采购交易", html)

    def test_report_adds_region_source_section_with_catalog_status_and_counts(self) -> None:
        hengyang_construction = self._notice(
            project_name="Hengyang Construction Project",
            suffix="hy-construction",
            lead_tier="DIRECT",
            section_id="section-hy-construction",
            notice_type="ZHAOBIAO_NOTICE",
            publish_time="2026-06-16 10:00:00",
        )
        hengyang_construction.source = "衡阳分平台"
        hengyang_construction.source_subtype = "建设工程交易"
        hengyang_construction.region = "衡阳"

        hengyang_procurement = self._notice(
            project_name="Hengyang Procurement Project",
            suffix="hy-procurement",
            lead_tier="WATCHLIST",
            section_id="section-hy-procurement",
            notice_type="GENGZHENG_NOTICE",
            publish_time="2026-06-15 10:00:00",
        )
        hengyang_procurement.source = "衡阳分平台"
        hengyang_procurement.source_subtype = "政府采购交易"
        hengyang_procurement.region = "衡阳"

        changsha_direct = self._notice(
            project_name="Changsha Direct Project",
            suffix="cs-direct",
            lead_tier="DIRECT",
            section_id="section-cs-direct",
            notice_type="ZHAOBIAO_NOTICE",
            publish_time="2026-06-17 10:00:00",
        )
        changsha_direct.source = "长沙公共资源交易平台"
        changsha_direct.source_subtype = "长沙政府采购交易"
        changsha_direct.region = "长沙"

        changsha_exclude = self._notice(
            project_name="Changsha Exclude Project",
            suffix="cs-exclude",
            lead_tier="EXCLUDE",
            section_id="section-cs-exclude",
            notice_type="GENGZHENG_NOTICE",
            publish_time="2026-06-14 10:00:00",
        )
        changsha_exclude.source = "长沙公共资源交易平台"
        changsha_exclude.source_subtype = "长沙政府采购交易"
        changsha_exclude.region = "长沙"

        ccgp_local_notice = self._notice(
            project_name="CCGP Local Project",
            suffix="ccgp-local",
            lead_tier="WATCHLIST",
            section_id="section-ccgp-local",
            notice_type="ZHAOBIAO_NOTICE",
            publish_time="2026-06-16 09:00:00",
        )
        ccgp_local_notice.source = "\u4e2d\u56fd\u653f\u5e9c\u91c7\u8d2d\u7f51"
        ccgp_local_notice.source_subtype = "\u5730\u65b9\u516c\u544a"
        ccgp_local_notice.region = "\u5c71\u4e1c"

        with tempfile.TemporaryDirectory() as raw_dir:
            report_path = Path(raw_dir) / "latest.html"
            write_html_report(
                report_path,
                [hengyang_construction, hengyang_procurement, changsha_direct, changsha_exclude, ccgp_local_notice],
                source_count=4,
                generated_at="2026-06-17 12:00:00",
            )
            html = report_path.read_text(encoding="utf-8")

        self.assertIn("按地区与来源查看", html)
        self.assertIn("衡阳", html)
        self.assertIn("长沙", html)
        self.assertIn("DIRECT 直接商机", html)
        self.assertIn("WATCHLIST 待复核", html)
        self.assertIn("EXCLUDE 排除项", html)
        self.assertNotIn("supported \u6709", html)
        self.assertNotIn("alpha \u963f\u5c14\u6cd5", html)
        self.assertNotIn("DIRECT \u6570 \u76f4\u63a5\u6570", html)
        self.assertNotIn("WATCHLIST \u6570 \u5173\u6ce8\u5217\u8868\u6570\u91cf", html)
        self.assertNotIn("EXCLUDE \u6570 \u6392\u9664\u6570\u5b57", html)


        construction_slice = self._source_group_slice(html, "衡阳分平台 / 建设工程交易")
        self.assertIn(">supported<", construction_slice)
        self.assertIn("公告数量</strong><span>1</span>", construction_slice)
        self.assertIn("DIRECT 数</strong><span>1</span>", construction_slice)

        procurement_slice = self._source_group_slice(html, "衡阳分平台 / 政府采购交易")
        self.assertIn(">supported<", procurement_slice)
        self.assertIn("WATCHLIST 数</strong><span>1</span>", procurement_slice)

        changsha_slice = self._source_group_slice(html, "长沙公共资源交易平台 / 长沙政府采购交易")
        self.assertIn(">alpha<", changsha_slice)
        self.assertNotIn(">supported<", changsha_slice)
        self.assertIn("公告数量</strong><span>2</span>", changsha_slice)
        self.assertIn("DIRECT 数</strong><span>1</span>", changsha_slice)
        self.assertIn("EXCLUDE 数</strong><span>1</span>", changsha_slice)
        self.assertIn("最近发布时间</strong><span>2026-06-17 10:00:00</span>", changsha_slice)

        ccgp_local_slice = self._source_group_slice(
            html, "\u4e2d\u56fd\u653f\u5e9c\u91c7\u8d2d\u7f51 / \u5730\u65b9\u516c\u544a"
        )
        self.assertIn(">alpha<", ccgp_local_slice)
        self.assertIn("\u516c\u544a\u6570\u91cf</strong><span>1</span>", ccgp_local_slice)
        self.assertIn("WATCHLIST \u6570</strong><span>1</span>", ccgp_local_slice)

    def test_report_groups_unknown_region_and_missing_subtype_conservatively(self) -> None:
        unknown_region_notice = self._notice(
            project_name="Unknown Region Project",
            suffix="unknown-region",
            lead_tier="WATCHLIST",
            section_id="section-unknown-region",
            notice_type="ZHAOBIAO_NOTICE",
            publish_time="2026-06-16 10:00:00",
        )
        unknown_region_notice.region = ""
        unknown_region_notice.source = "长沙公共资源交易平台"
        unknown_region_notice.source_subtype = ""

        subtype_only_notice = self._notice(
            project_name="Subtype Only Project",
            suffix="subtype-only",
            lead_tier="DIRECT",
            section_id="section-subtype-only",
            notice_type="ZHAOBIAO_NOTICE",
            publish_time="2026-06-15 10:00:00",
        )
        subtype_only_notice.region = ""
        subtype_only_notice.source = ""
        subtype_only_notice.source_subtype = "政府采购交易"

        with tempfile.TemporaryDirectory() as raw_dir:
            report_path = Path(raw_dir) / "latest.html"
            write_html_report(
                report_path,
                [unknown_region_notice, subtype_only_notice],
                source_count=1,
                generated_at="2026-06-16 12:00:00",
            )
            html = report_path.read_text(encoding="utf-8")

        self.assertIn("地区未确认", html)
        self.assertIn("长沙公共资源交易平台", html)
        self.assertIn("政府采购交易", html)
        self.assertIn("按地区与来源查看", html)

    def test_report_uses_readable_link_label_when_employee_url_exists(self) -> None:
        notice = self._notice(
            project_name="Readable Link Project",
            suffix="readable-link",
            lead_tier="DIRECT",
            section_id="section-readable-link",
            notice_type="ZHAOBIAO_NOTICE",
            publish_time="2026-06-16 10:00:00",
        )

        with tempfile.TemporaryDirectory() as raw_dir:
            report_path = Path(raw_dir) / "latest.html"
            write_html_report(report_path, [notice], source_count=1, generated_at="2026-06-15 12:00:00")
            html = report_path.read_text(encoding="utf-8")

        self.assertIn("打开原文链接", html)
        self.assertNotIn("打开原始接口", html)

    def test_report_uses_raw_api_label_when_only_api_url_is_available(self) -> None:
        notice = self._notice(
            project_name="API Link Project",
            suffix="api-link",
            lead_tier="WATCHLIST",
            section_id="section-api-link",
            notice_type="ZHAOBIAO_NOTICE",
            publish_time="2026-06-16 10:00:00",
        )
        notice.employee_readable_url = ""
        notice.original_url = ""
        notice.raw_api_url = "https://example.com/raw-api"
        notice.detail_available = True

        with tempfile.TemporaryDirectory() as raw_dir:
            report_path = Path(raw_dir) / "latest.html"
            write_html_report(report_path, [notice], source_count=1, generated_at="2026-06-15 12:00:00")
            html = report_path.read_text(encoding="utf-8")

        self.assertIn("打开原始接口", html)
        self.assertNotIn("打开原文链接", html)

    def test_report_treats_trade_api_in_original_url_as_api_link(self) -> None:
        notice = self._notice(
            project_name="Original API Link Project",
            suffix="original-api-link",
            lead_tier="WATCHLIST",
            section_id="section-original-api-link",
            notice_type="ZHAOBIAO_NOTICE",
            publish_time="2026-06-16 10:00:00",
        )
        notice.employee_readable_url = ""
        notice.original_url = "https://example.com/tradeApi/project/detail?id=1"
        notice.raw_api_url = ""
        notice.detail_available = True

        with tempfile.TemporaryDirectory() as raw_dir:
            report_path = Path(raw_dir) / "latest.html"
            write_html_report(report_path, [notice], source_count=1, generated_at="2026-06-15 12:00:00")
            html = report_path.read_text(encoding="utf-8")

        self.assertIn("打开原始接口", html)
        self.assertNotIn("打开原文链接", html)

    def test_report_does_not_render_failed_api_as_primary_link(self) -> None:
        notice = self._notice(
            project_name="Failed API Project",
            suffix="failed-api",
            lead_tier="EXCLUDE",
            section_id="section-failed-api",
            notice_type="ZHAOBIAO_NOTICE",
            publish_time="2026-06-16 10:00:00",
        )
        notice.employee_readable_url = ""
        notice.original_url = ""
        notice.raw_api_url = "https://example.com/failed-api"
        notice.detail_available = False
        notice.detail_risk_note = "详情页不可访问或解析失败"

        with tempfile.TemporaryDirectory() as raw_dir:
            report_path = Path(raw_dir) / "latest.html"
            write_html_report(report_path, [notice], source_count=1, generated_at="2026-06-15 12:00:00")
            html = report_path.read_text(encoding="utf-8")

        self.assertNotIn('href="https://example.com/failed-api"', html)
        self.assertIn("详情页不可访问或解析失败，建议人工到原站复核", html)
        self.assertNotIn("打开原文链接", html)

    def test_report_renders_quality_risk_panel_when_notice_has_risk_note(self) -> None:
        notice = self._notice(
            project_name="Quality Risk Project",
            suffix="quality-risk",
            lead_tier="WATCHLIST",
            section_id="section-quality-risk",
            notice_type="ZHAOBIAO_NOTICE",
            publish_time="2026-06-16 10:00:00",
        )
        notice.detail_risk_note = "列表新鲜度未证明，可能混入旧公告"

        with tempfile.TemporaryDirectory() as raw_dir:
            report_path = Path(raw_dir) / "latest.html"
            write_html_report(report_path, [notice], source_count=1, generated_at="2026-06-15 12:00:00")
            html = report_path.read_text(encoding="utf-8")

        self.assertIn("数据质量提示", html)
        self.assertIn("列表新鲜度未证明，可能混入旧公告", html)


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
            bid_open_or_response_deadline="2099-06-20 09:00:00",
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
