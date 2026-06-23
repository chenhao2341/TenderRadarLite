from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.web_console import RunConflictError, WebConsoleService


class ImmediateThread:
    def __init__(self, target, name=None, daemon=None):
        self.target = target

    def start(self) -> None:
        self.target()


class PendingThread:
    def __init__(self, target, name=None, daemon=None):
        self.target = target

    def start(self) -> None:
        return


class WebConsoleServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))
        for name in ("profiles", "reports", "logs", "data", "config"):
            (self.temp_dir / name).mkdir()
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
        (self.temp_dir / "config" / "sources.json").write_text("[]", encoding="utf-8")
        (self.temp_dir / "config" / "source_catalog.yaml").write_text(
            "\n".join(
                [
                    "version: 1",
                    "sources:",
                    "  - id: hengyang-construction",
                    "    name: 衡阳公共资源交易平台 / 建设工程交易",
                    "    homepage: https://example.invalid/construction",
                    "    list_entry_url: https://example.invalid/construction/list",
                    "    region: 衡阳",
                    "    source_type: public_resource_trading",
                    "    supported_notice_types: [招标公告]",
                    "    adapter: hengyang_construction",
                    "    status: supported",
                    "    industry_profiles: [design_consulting]",
                    "    has_detail_page: yes",
                    "    has_attachments: likely",
                    "    access_risk: low",
                    "    anti_bot_risk: low",
                    "    login_requirement: no",
                    "    data_quality: high",
                    "    update_frequency: frequent",
                    "    notes: 原生来源。",
                    "    source_from: native",
                    "    reference_project: ''",
                    "    license_note: native adapter only",
                    "  - id: hengyang-procurement",
                    "    name: 衡阳公共资源交易平台 / 政府采购交易",
                    "    homepage: https://example.invalid/procurement",
                    "    list_entry_url: https://example.invalid/procurement/list",
                    "    region: 衡阳",
                    "    source_type: government_procurement",
                    "    supported_notice_types: [采购公告]",
                    "    adapter: hengyang_procurement",
                    "    status: alpha",
                    "    industry_profiles: [design_consulting]",
                    "    has_detail_page: yes",
                    "    has_attachments: likely",
                    "    access_risk: medium",
                    "    anti_bot_risk: medium",
                    "    login_requirement: no",
                    "    data_quality: medium",
                    "    update_frequency: frequent",
                    "    notes: 原生来源，但当前未默认启用。",
                    "    source_from: native",
                    "    reference_project: ''",
                    "    license_note: native adapter only",
                    "  - id: china-government-procurement",
                    "    name: 中国政府采购网",
                    "    homepage: https://example.invalid/cgp",
                    "    list_entry_url: https://example.invalid/cgp/list",
                    "    region: 全国",
                    "    source_type: government_procurement",
                    "    supported_notice_types: [采购公告]",
                    "    adapter: ''",
                    "    status: candidate",
                    "    industry_profiles: [design_consulting]",
                    "    has_detail_page: unknown",
                    "    has_attachments: unknown",
                    "    access_risk: medium",
                    "    anti_bot_risk: medium",
                    "    login_requirement: unknown",
                    "    data_quality: unknown",
                    "    update_frequency: unknown",
                    "    notes: 仅来源目录记录，未本地验证。",
                    "    source_from: github_reference",
                    "    reference_project: scout-only",
                    "    license_note: reference only",
                ]
            ),
            encoding="utf-8",
        )
        self.service = WebConsoleService(root_dir=self.temp_dir)

    def test_dashboard_page_is_accessible(self) -> None:
        rendered_html = self.service.render_page("dashboard")

        self.assertIn("TenderRadarLite", rendered_html)
        self.assertIn("运行入口", rendered_html)
        self.assertIn("来源目录摘要", rendered_html)

    def test_initial_run_status_api_is_accessible(self) -> None:
        payload = self.service.handle_api_request("GET", "/api/run/status")

        self.assertEqual(payload["status"], "idle")
        self.assertEqual(payload["command"], subprocess.list2cmdline([sys.executable, "run_mvp.py", "--local-html", "--profile", "design_consulting"]))
        self.assertEqual(payload["report_path"], str(self.temp_dir / "reports" / "latest.html"))
        self.assertFalse(payload["report_exists"])

    def test_post_local_scan_triggers_fixed_safe_command(self) -> None:
        calls: list[tuple[list[str], dict[str, object]]] = []

        def fake_run(command, **kwargs):
            calls.append((command, kwargs))
            (self.temp_dir / "reports" / "latest.html").write_text("<html>ok</html>", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="INFO done\n", stderr="")

        with patch("app.web_console.threading.Thread", ImmediateThread), patch("app.web_console.subprocess.run", side_effect=fake_run):
            payload = self.service.handle_api_request("POST", "/api/run/local-scan")

        self.assertEqual(payload["status"], "success")
        self.assertEqual(len(calls), 1)
        command, kwargs = calls[0]
        self.assertEqual(command, [sys.executable, "run_mvp.py", "--local-html", "--profile", "design_consulting"])
        self.assertEqual(kwargs["cwd"], str(self.temp_dir))
        self.assertFalse(kwargs["shell"])
        self.assertTrue(kwargs["capture_output"])
        self.assertEqual(kwargs["timeout"], 300)

    def test_run_while_running_is_rejected(self) -> None:
        with patch("app.web_console.threading.Thread", PendingThread):
            first = self.service.handle_api_request("POST", "/api/run/local-scan")
            self.assertEqual(first["status"], "running")
            with self.assertRaises(RunConflictError):
                self.service.handle_api_request("POST", "/api/run/local-scan")

    def test_successful_run_updates_status_summary(self) -> None:
        def fake_run(command, **kwargs):
            (self.temp_dir / "reports" / "latest.html").write_text("<html>ok</html>", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="line1\nline2\n", stderr="")

        with patch("app.web_console.threading.Thread", ImmediateThread), patch("app.web_console.subprocess.run", side_effect=fake_run):
            self.service.handle_api_request("POST", "/api/run/local-scan")

        payload = self.service.handle_api_request("GET", "/api/run/status")
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["returncode"], 0)
        self.assertTrue(payload["success"])
        self.assertTrue(payload["report_exists"])
        self.assertTrue(payload["started_at"])
        self.assertTrue(payload["finished_at"])
        self.assertIsNotNone(payload["duration_seconds"])
        self.assertEqual(payload["stdout_tail"], ["line1", "line2"])

    def test_failed_run_updates_status_summary(self) -> None:
        def fake_run(command, **kwargs):
            return subprocess.CompletedProcess(command, 7, stdout="INFO before fail\n", stderr="ERROR failed\n")

        with patch("app.web_console.threading.Thread", ImmediateThread), patch("app.web_console.subprocess.run", side_effect=fake_run):
            self.service.handle_api_request("POST", "/api/run/local-scan")

        payload = self.service.handle_api_request("GET", "/api/run/status")
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["returncode"], 7)
        self.assertFalse(payload["success"])
        self.assertEqual(payload["stderr_tail"], ["ERROR failed"])

    def test_output_tail_is_truncated_and_masked(self) -> None:
        stdout = "\n".join(f"line-{index}" for index in range(25))
        stderr = "DEEPSEEK_API_KEY=sk-real-secret\nTOKEN=abc123\nAuthorization: Bearer super-token"

        def fake_run(command, **kwargs):
            return subprocess.CompletedProcess(command, 3, stdout=stdout, stderr=stderr)

        with patch("app.web_console.threading.Thread", ImmediateThread), patch("app.web_console.subprocess.run", side_effect=fake_run):
            self.service.handle_api_request("POST", "/api/run/local-scan")

        payload = self.service.handle_api_request("GET", "/api/run/status")
        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertEqual(len(payload["stdout_tail"]), 20)
        self.assertEqual(payload["stdout_tail"][0], "line-5")
        self.assertEqual(payload["stdout_tail"][-1], "line-24")
        self.assertNotIn("sk-real-secret", serialized)
        self.assertNotIn("abc123", serialized)
        self.assertNotIn("super-token", serialized)
        self.assertIn("DEEPSEEK_API_KEY=***", serialized)
        self.assertIn("TOKEN=***", serialized)

    def test_run_history_keeps_recent_items(self) -> None:
        returncodes = iter(range(7))

        def fake_run(command, **kwargs):
            code = next(returncodes)
            return subprocess.CompletedProcess(command, code, stdout=f"run-{code}\n", stderr="")

        with patch("app.web_console.threading.Thread", ImmediateThread), patch("app.web_console.subprocess.run", side_effect=fake_run):
            for _ in range(7):
                self.service.handle_api_request("POST", "/api/run/local-scan")

        history = self.service.handle_api_request("GET", "/api/run/history")
        self.assertEqual(len(history["items"]), 5)
        self.assertEqual(history["items"][0]["returncode"], 6)
        self.assertEqual(history["items"][-1]["returncode"], 2)

    def test_run_page_renders_real_button_and_summary_blocks(self) -> None:
        rendered_html = self.service.render_page("run")

        self.assertIn("运行一次本地扫描", rendered_html)
        self.assertIn("/api/run/local-scan", rendered_html)
        self.assertIn("/api/run/status", rendered_html)
        self.assertIn("stdout 摘要", rendered_html)
        self.assertIn("stderr 摘要", rendered_html)

    def test_legacy_api_run_remains_command_only(self) -> None:
        payload = self.service.handle_api_request("POST", "/api/run")

        self.assertEqual(payload["mode"], "command-only")
        self.assertIn("POST /api/run/local-scan", payload["message"])
        self.assertFalse(payload["will_trigger_feishu"])
        self.assertFalse(payload["will_trigger_ai"])

    def test_report_entrypoint_still_opens_latest_html(self) -> None:
        report_path = self.temp_dir / "reports" / "latest.html"
        report_path.write_text("<html>report</html>", encoding="utf-8")

        payload = self.service.get_report_payload()
        rendered_html = self.service.render_page("report")

        self.assertTrue(payload["exists"])
        self.assertEqual(payload["open_url"], "/artifacts/report/latest")
        self.assertIn("/artifacts/report/latest", rendered_html)

    def test_missing_report_payload_has_helpful_message(self) -> None:
        payload = self.service.get_report_payload()

        self.assertFalse(payload["exists"])
        self.assertIn("--local-html", payload["message"])

    def test_logs_config_and_source_catalog_interfaces_still_work(self) -> None:
        logs = self.service.handle_api_request("GET", "/api/logs")
        config = self.service.handle_api_request("GET", "/api/config-status")
        catalog = self.service.handle_api_request("GET", "/api/source-catalog")
        rendered_sources = self.service.render_page("sources")

        self.assertIn("run-20260618.log", logs["files"])
        self.assertEqual(config["ai"]["api_key"], "已配置")
        self.assertEqual(config["feishu"]["app_secret"], "已配置")
        self.assertEqual(catalog["summary"]["total"], 3)
        self.assertIn("来源目录", rendered_sources)
        self.assertIn("候选", rendered_sources)
        self.assertIn("不会触发抓取", rendered_sources)

    def test_config_status_only_reports_presence_not_secret_values(self) -> None:
        payload = self.service.get_config_status_payload()
        serialized = json.dumps(payload, ensure_ascii=False)

        self.assertEqual(payload["feishu"]["app_secret"], "已配置")
        self.assertEqual(payload["ai"]["api_key"], "已配置")
        self.assertNotIn("sk-real-secret", serialized)
        self.assertNotIn("secret-demo", serialized)
        self.assertNotIn("https://example.invalid/hook", serialized)

    def test_status_payload_masks_sensitive_values(self) -> None:
        payload = self.service.get_status_payload()
        serialized = json.dumps(payload, ensure_ascii=False)

        self.assertIn("local-html", serialized)
        self.assertNotIn("sk-real-secret", serialized)
        self.assertNotIn("secret-demo", serialized)
        self.assertNotIn("https://example.invalid/hook", serialized)

    def test_run_payload_exposes_safe_defaults(self) -> None:
        payload = self.service.get_run_payload()

        self.assertTrue(payload["defaults"]["local_html"])
        self.assertFalse(payload["defaults"]["ai_analysis"])
        self.assertFalse(payload["defaults"]["feishu_sync"])
        self.assertEqual(payload["run_mode"], "single-shot-local-scan")


if __name__ == "__main__":
    unittest.main()
