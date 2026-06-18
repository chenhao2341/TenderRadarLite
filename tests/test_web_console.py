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
        (self.temp_dir / "config").mkdir()
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
        (self.temp_dir / "config" / "sources.json").write_text(
            "[]",
            encoding="utf-8",
        )
        (self.temp_dir / "config" / "source_catalog.yaml").write_text(
            "\n".join(
                [
                    "version: 1",
                    "sources:",
                    "  - id: hengyang-construction",
                    "    name: 衡阳分平台 / 建设工程交易",
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
                    "    name: 衡阳分平台 / 政府采购交易",
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
                    "  - id: national-public-resource-platform",
                    "    name: 全国公共资源交易平台",
                    "    homepage: unknown",
                    "    list_entry_url: unknown",
                    "    region: 全国",
                    "    source_type: public_resource_trading",
                    "    supported_notice_types: [招标公告]",
                    "    adapter: ''",
                    "    status: planned",
                    "    industry_profiles: [design_consulting]",
                    "    has_detail_page: unknown",
                    "    has_attachments: likely",
                    "    access_risk: medium",
                    "    anti_bot_risk: medium",
                    "    login_requirement: unknown",
                    "    data_quality: unknown",
                    "    update_frequency: unknown",
                    "    notes: 待后续人工确认入口。",
                    "    source_from: manual_research",
                    "    reference_project: backlog",
                    "    license_note: planning only",
                    "  - id: enterprise-procurement-portals",
                    "    name: 企业采购门户集合",
                    "    homepage: unknown",
                    "    list_entry_url: unknown",
                    "    region: 多地区",
                    "    source_type: enterprise_procurement",
                    "    supported_notice_types: [采购公告]",
                    "    adapter: ''",
                    "    status: blocked",
                    "    industry_profiles: [design_consulting]",
                    "    has_detail_page: unknown",
                    "    has_attachments: no",
                    "    access_risk: high",
                    "    anti_bot_risk: high",
                    "    login_requirement: yes",
                    "    data_quality: low",
                    "    update_frequency: unknown",
                    "    notes: 登录和反爬风险高。",
                    "    source_from: manual_research",
                    "    reference_project: backlog",
                    "    license_note: blocked",
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

    def test_sources_page_is_accessible_and_read_only(self) -> None:
        rendered_html = self.service.render_page("sources")

        self.assertIn("来源目录", rendered_html)
        self.assertIn("候选 / 计划研究 不代表已经支持抓取", rendered_html)
        self.assertIn("本页只是来源知识库，不会触发抓取", rendered_html)
        self.assertIn(">来源目录<", rendered_html)
        self.assertNotIn("立即抓取", rendered_html)
        self.assertNotIn("一键接入", rendered_html)

    def test_sources_page_shows_catalog_rows_and_chinese_labels(self) -> None:
        rendered_html = self.service.render_page("sources")

        self.assertIn("衡阳分平台 / 建设工程交易", rendered_html)
        self.assertIn("衡阳分平台 / 政府采购交易", rendered_html)
        self.assertIn("中国政府采购网", rendered_html)
        self.assertIn("已支持", rendered_html)
        self.assertIn("Alpha", rendered_html)
        self.assertIn("候选", rendered_html)
        self.assertIn("计划研究", rendered_html)
        self.assertIn("暂不建议", rendered_html)
        self.assertIn("政府采购", rendered_html)
        self.assertIn("公共资源交易", rendered_html)
        self.assertIn("企业采购", rendered_html)
        self.assertIn("中", rendered_html)
        self.assertIn("高", rendered_html)
        self.assertIn("可能有", rendered_html)
        self.assertIn("无", rendered_html)
        self.assertNotIn(">supported<", rendered_html)
        self.assertNotIn(">candidate<", rendered_html)
        self.assertNotIn(">planned<", rendered_html)
        self.assertNotIn(">blocked<", rendered_html)

    def test_dashboard_shows_source_catalog_summary_in_chinese(self) -> None:
        rendered_html = self.service.render_page("dashboard")

        self.assertIn("来源目录摘要", rendered_html)
        self.assertIn("来源总数", rendered_html)
        self.assertIn("已支持", rendered_html)
        self.assertIn("Alpha", rendered_html)
        self.assertIn("候选", rendered_html)
        self.assertIn("计划研究", rendered_html)
        self.assertIn("暂不建议", rendered_html)
        self.assertNotIn("supported", rendered_html)
        self.assertNotIn("candidate", rendered_html)

    def test_sources_page_uses_table_classes_for_spacing_and_wrapping(self) -> None:
        rendered_html = self.service.render_page("sources")

        self.assertIn('class="source-table"', rendered_html)
        self.assertIn('badge badge-status status-', rendered_html)
        self.assertIn('badge badge-risk risk-', rendered_html)
        self.assertIn('class="adapter-cell"', rendered_html)
        self.assertIn('class="notes-cell"', rendered_html)

    def test_sources_payload_does_not_leak_secret_and_does_not_trigger_integrations(self) -> None:
        payload = self.service.handle_api_request("GET", "/api/status")
        sources_page = self.service.render_page("sources")
        serialized = json.dumps(payload, ensure_ascii=False) + sources_page

        self.assertNotIn("sk-real-secret", serialized)
        self.assertNotIn("secret-demo", serialized)
        self.assertNotIn("https://example.invalid/hook", serialized)
        self.assertIn("不会触发抓取", serialized)
        self.assertIn("默认不触发飞书", serialized)


if __name__ == "__main__":
    unittest.main()
