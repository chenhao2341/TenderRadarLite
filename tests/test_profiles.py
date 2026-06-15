from __future__ import annotations

import unittest
from unittest import mock

from app.main import build_parser, main
from app.models import Notice
from app.preview_report import classify_notice


class ProfileLoaderTests(unittest.TestCase):
    def test_loads_design_consulting_profile(self) -> None:
        from app.profiles import load_profile

        profile = load_profile("design_consulting")

        self.assertEqual(profile["profile_id"], "design_consulting")
        self.assertIn("规划设计", profile["positive_keywords"])
        self.assertIn("施工图设计", profile["strong_positive_keywords"])
        self.assertIn("施工总承包", profile["negative_keywords"])
        self.assertIn("设备采购", profile["exclude_keywords"])

    def test_loads_alpha_template_profiles(self) -> None:
        from app.profiles import load_profile

        for profile_id in ("software_it", "construction", "medical_equipment"):
            profile = load_profile(profile_id)
            self.assertEqual(profile["profile_id"], profile_id)
            self.assertTrue(profile["description"])
            self.assertIsInstance(profile["positive_keywords"], list)

    def test_missing_profile_raises_clear_error(self) -> None:
        from app.profiles import ProfileNotFoundError, load_profile

        with self.assertRaises(ProfileNotFoundError) as ctx:
            load_profile("missing_profile")

        self.assertIn("missing_profile", str(ctx.exception))
        self.assertIn("Available profiles", str(ctx.exception))


class ProfileClassificationTests(unittest.TestCase):
    def _notice(self, *, project_name: str, content_summary: str = "", qualification_summary: str = "") -> Notice:
        return Notice(
            source="source",
            source_subtype="construction",
            dedupe_key="source|notice-1",
            section_id="section-1",
            project_name=project_name,
            notice_id="notice-1",
            notice_type="ZHAOBIAO_NOTICE",
            publish_time="2026-06-15 10:00:00",
            content_summary=content_summary,
            qualification_summary=qualification_summary,
            original_url="https://example.com/notice-1",
        )

    def test_design_consulting_positive_signals_cover_core_terms(self) -> None:
        from app.profiles import load_profile

        notice = self._notice(project_name="城市更新片区规划设计及方案设计服务", content_summary="含可研编制")
        classification = classify_notice(notice, profile=load_profile("design_consulting"))

        self.assertEqual(classification["lead_tier"], "DIRECT")
        self.assertIn("规划设计", classification["matched_positive_signals"])
        self.assertIn("城市更新", classification["matched_positive_signals"])
        self.assertIn("方案设计", classification["matched_positive_signals"])
        self.assertIn("可研", classification["matched_positive_signals"])

    def test_design_consulting_negative_and_exclude_signals_work(self) -> None:
        from app.profiles import load_profile

        notice = self._notice(project_name="食堂物业及设备采购项目", content_summary="施工总承包单位另行确定")
        classification = classify_notice(notice, profile=load_profile("design_consulting"))

        self.assertEqual(classification["lead_tier"], "EXCLUDE")
        self.assertIn("设备采购", classification["matched_negative_signals"])
        self.assertIn("物业", classification["matched_negative_signals"])
        self.assertIn("食堂", classification["matched_negative_signals"])
        self.assertIn("施工总承包", classification["matched_negative_signals"])

    def test_construction_general_contracting_does_not_block_working_drawing_design(self) -> None:
        from app.profiles import load_profile

        notice = self._notice(project_name="片区施工图设计服务", content_summary="含方案设计与初步设计")
        classification = classify_notice(notice, profile=load_profile("design_consulting"))

        self.assertEqual(classification["lead_tier"], "DIRECT")
        self.assertIn("施工图设计", classification["matched_positive_signals"])


class ProfileCliTests(unittest.TestCase):
    def test_parser_accepts_profile_argument(self) -> None:
        parser = build_parser()

        args = parser.parse_args(["--local-html", "--profile", "design_consulting"])

        self.assertEqual(args.profile, "design_consulting")

    def test_local_html_passes_explicit_profile(self) -> None:
        with mock.patch("app.main.run_once", return_value=[]) as run_once_mock:
            exit_code = main(["--local-html", "--profile", "design_consulting"])

        self.assertEqual(exit_code, 0)
        run_once_mock.assert_called_once_with(enable_feishu=False, html_report=True, profile_id="design_consulting")

    def test_local_html_default_profile_argument_is_forwarded(self) -> None:
        with mock.patch("app.main.run_once", return_value=[]) as run_once_mock:
            exit_code = main(["--local-html"])

        self.assertEqual(exit_code, 0)
        run_once_mock.assert_called_once_with(enable_feishu=False, html_report=True, profile_id="design_consulting")


if __name__ == "__main__":
    unittest.main()
