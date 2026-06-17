from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


class CompanyProfileLoaderTests(unittest.TestCase):
    def test_loads_company_sample_yaml(self) -> None:
        from app.company_profile import load_company_profile

        profile = load_company_profile(Path("profiles/company_sample.yaml"))

        self.assertEqual(profile.company_name, "某某设计咨询有限公司")
        self.assertIn("湖南", profile.regions)
        self.assertIn("规划设计", profile.business_scope)
        self.assertIn("施工总承包", profile.exclude_project_types)
        self.assertEqual(profile.budget_preference.min_amount, 500000)
        self.assertEqual(profile.notice_type_preference.high, ["招标公告", "采购公告", "重新招标公告"])

    def test_missing_fields_use_defaults(self) -> None:
        from app.company_profile import load_company_profile

        with tempfile.TemporaryDirectory() as raw_dir:
            profile_path = Path(raw_dir) / "company_minimal.yaml"
            profile_path.write_text('company_name: "测试企业"\n', encoding="utf-8")

            profile = load_company_profile(profile_path)

        self.assertEqual(profile.company_name, "测试企业")
        self.assertEqual(profile.regions, [])
        self.assertEqual(profile.business_scope, [])
        self.assertEqual(profile.target_project_types, [])
        self.assertEqual(profile.exclude_project_types, [])
        self.assertEqual(profile.qualifications, [])
        self.assertIsNone(profile.budget_preference.min_amount)
        self.assertEqual(profile.budget_preference.preferred_unit, "元")
        self.assertEqual(profile.budget_preference.note, "金额单位不明确时不直接过滤")
        self.assertEqual(profile.notice_type_preference.high, [])
        self.assertEqual(profile.notice_type_preference.medium, [])
        self.assertEqual(profile.notice_type_preference.low, [])

    def test_existing_industry_profiles_still_load(self) -> None:
        from app.profiles import load_profile

        profile = load_profile("design_consulting")

        self.assertEqual(profile["profile_id"], "design_consulting")


if __name__ == "__main__":
    unittest.main()
