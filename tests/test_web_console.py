from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from app.web_console import WebConsoleService


class WebConsoleServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))
        (self.temp_dir / "profiles").mkdir()
        (self.temp_dir / "reports").mkdir()
        (self.temp_dir / "logs").mkdir()
        (self.temp_dir / "data").mkdir()
        (self.temp_dir / ".env.example").write_text("DEEPSEEK_API_KEY=\n", encoding="utf-8")
        for profile_id in ("construction", "design_consulting", "medical_equipment", "software_it"):
            (self.temp_dir / "profiles" / f"{profile_id}.json").write_text("{}", encoding="utf-8")
        (self.temp_dir / "profiles" / "company_sample.yaml").write_text("company_name: Demo\n", encoding="utf-8")
        (self.temp_dir / "logs" / "run-20260618.log").write_text(
            "INFO startup\nWARNING nothing sensitive here\n",
            encoding="utf-8",
        )
        (self.temp_dir / ".env").write_text(
            "\n".join(
                [
                    "DEEPSEEK_API_KEY=sk-real-secret",
                    "DEEPSEEK_MODEL=deepseek-v4-flash",
                    "FEISHU_APP_ID=cli_demo",
                    "FEISHU_APP_SECRET=secret-demo",
                    "FEISHU_WEBHOOK_URL=https://example.invalid/hook",
                ]
            ),
            encoding="utf-8",
        )
        self.service = WebConsoleService(root_dir=self.temp_dir)

    def test_status_payload_masks_sensitive_values(self) -> None:
        payload = self.service.get_status_payload()
        serialized = json.dumps(payload, ensure_ascii=False)

        self.assertIn("local-html", serialized)
        self.assertNotIn("sk-real-secret", serialized)
        self.assertNotIn("secret-demo", serialized)
        self.assertNotIn("https://example.invalid/hook", serialized)

    def test_report_payload_when_latest_html_exists(self) -> None:
        report_path = self.temp_dir / "reports" / "latest.html"
        report_path.write_text("<html>report</html>", encoding="utf-8")

        payload = self.service.get_report_payload()

        self.assertTrue(payload["exists"])
        self.assertEqual(payload["path"], str(report_path))
        self.assertTrue(payload["updated_at"])

    def test_report_payload_when_latest_html_missing(self) -> None:
        payload = self.service.get_report_payload()

        self.assertFalse(payload["exists"])
        self.assertIn("--local-html", payload["message"])

    def test_logs_payload_only_reads_logs_directory(self) -> None:
        (self.temp_dir / ".env").write_text("DEEPSEEK_API_KEY=must-not-leak\n", encoding="utf-8")

        payload = self.service.get_logs_payload()
        serialized = json.dumps(payload, ensure_ascii=False)

        self.assertIn("run-20260618.log", serialized)
        self.assertNotIn(".env", serialized)
        self.assertNotIn("must-not-leak", serialized)

    def test_config_status_only_reports_presence_not_secret_values(self) -> None:
        payload = self.service.get_config_status_payload()
        serialized = json.dumps(payload, ensure_ascii=False)

        self.assertEqual(payload["feishu"]["app_secret"], "已配置")
        self.assertEqual(payload["ai"]["api_key"], "已配置")
        self.assertNotIn("configured", serialized)
        self.assertNotIn("missing", serialized)
        self.assertNotIn("sk-real-secret", serialized)
        self.assertNotIn("secret-demo", serialized)

    def test_default_recommended_commands_use_design_consulting(self) -> None:
        payload = self.service.get_run_payload()
        command = payload["recommended_command"]
        enterprise_command = payload["enterprise_command"]

        self.assertEqual(command, "python run_mvp.py --local-html --profile design_consulting")
        self.assertNotIn("--company-profile", command)
        self.assertNotIn("--ai-analysis", command)
        self.assertNotIn("feishu", command.lower())
        self.assertEqual(
            enterprise_command,
            "python run_mvp.py --local-html --profile design_consulting --company-profile profiles/company_sample.yaml",
        )
        self.assertIn("--company-profile profiles/company_sample.yaml", enterprise_command)
        self.assertNotIn("--ai-analysis", enterprise_command)
        self.assertNotIn("feishu", enterprise_command.lower())

    def test_default_run_payload_marks_feishu_and_ai_disabled(self) -> None:
        payload = self.service.get_run_payload()

        self.assertFalse(payload["defaults"]["ai_analysis"])
        self.assertFalse(payload["defaults"]["feishu_sync"])
        self.assertTrue(payload["defaults"]["local_html"])

    def test_report_page_renders_friendly_empty_state(self) -> None:
        rendered_html = self.service.render_page("report")

        self.assertIn("尚未生成本地报告", rendered_html)
        self.assertIn("TenderRadarLite", rendered_html)

    def test_run_page_and_nav_are_simplified_chinese(self) -> None:
        rendered_html = self.service.render_page("run")

        self.assertIn(">仪表盘<", rendered_html)
        self.assertIn(">运行入口<", rendered_html)
        self.assertIn(">报告入口<", rendered_html)
        self.assertIn(">日志<", rendered_html)
        self.assertIn(">配置状态<", rendered_html)
        self.assertIn("公开模式：", rendered_html)
        self.assertIn("企业模式：", rendered_html)
        self.assertIn("其他行业 profile 当前可用于测试或后续扩展。", rendered_html)
        self.assertNotIn(">Dashboard<", rendered_html)
        self.assertNotIn(">Run<", rendered_html)
        self.assertNotIn("跑步", rendered_html)
        self.assertNotIn("奔跑", rendered_html)

    def test_dashboard_uses_chinese_status_labels(self) -> None:
        rendered_html = self.service.render_page("dashboard")

        self.assertIn("当前 Git 版本", rendered_html)
        self.assertIn("工作区状态", rendered_html)
        self.assertIn("本地报告", rendered_html)
        self.assertIn("行业配置", rendered_html)
        self.assertIn("企业画像", rendered_html)
        self.assertIn("AI 分析", rendered_html)
        self.assertIn("飞书", rendered_html)
        self.assertNotIn("Git HEAD", rendered_html)
        self.assertNotIn("Industry Profiles", rendered_html)
        self.assertNotIn("Company Profile", rendered_html)
        self.assertNotIn("AI Analysis", rendered_html)

    def test_api_run_returns_recommended_command_not_real_execution(self) -> None:
        payload = self.service.handle_api_request("POST", "/api/run")

        self.assertEqual(payload["mode"], "command-only")
        self.assertEqual(payload["recommended_command"], "python run_mvp.py --local-html --profile design_consulting")
        self.assertEqual(
            payload["enterprise_command"],
            "python run_mvp.py --local-html --profile design_consulting --company-profile profiles/company_sample.yaml",
        )
        self.assertFalse(payload["will_trigger_feishu"])
        self.assertFalse(payload["will_trigger_ai"])


if __name__ == "__main__":
    unittest.main()
