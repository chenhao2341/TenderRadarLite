from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.ai_analysis import AIAnalysisConfig, analyze_notice, analyze_notices, build_notice_analysis_prompt
from app.models import Notice


class _FakeClient:
    def __init__(self, response: str = "", error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.prompts: list[str] = []

    def create_chat_completion(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        return self.response


class AIAnalysisTests(unittest.TestCase):
    def _notice(self, *, suffix: str, lead_tier: str = "DIRECT") -> Notice:
        return Notice(
            source="source",
            source_subtype="construction",
            dedupe_key=f"source|{suffix}",
            section_id=f"section-{suffix}",
            project_name=f"Project {suffix}",
            notice_id=f"notice-{suffix}",
            notice_title=f"Notice {suffix}",
            notice_type="ZHAOBIAO_NOTICE",
            purchaser_or_tenderer="Tenderer",
            agency="Agency",
            region="Hengyang",
            publish_time="2026-06-15 10:00:00",
            budget_amount="1000",
            ceiling_price="900",
            content_summary="Design consulting service for public project.",
            qualification_summary="Grade-A design qualification.",
            lead_tier=lead_tier,
            lead_reason=f"{lead_tier} reason",
            matched_positive_signals=["design consulting"],
            matched_negative_signals=["construction"] if lead_tier == "EXCLUDE" else [],
        )

    def test_default_disabled_ai_skips_without_calling_client(self) -> None:
        config = AIAnalysisConfig(enabled=False, api_key="key")
        client = _FakeClient(response='{"summary":"ignored"}')

        result = analyze_notice(self._notice(suffix="disabled"), config, profile_name="design_consulting", client=client)

        self.assertTrue(result.skipped)
        self.assertEqual(result.skip_reason, "AI analysis disabled")
        self.assertEqual(client.prompts, [])

    def test_missing_api_key_skips_without_crashing(self) -> None:
        config = AIAnalysisConfig(enabled=True, api_key="")

        result = analyze_notice(self._notice(suffix="missing-key"), config, profile_name="design_consulting")

        self.assertTrue(result.skipped)
        self.assertEqual(result.skip_reason, "未配置 DEEPSEEK_API_KEY")

    def test_prompt_does_not_include_secret_fields(self) -> None:
        prompt = build_notice_analysis_prompt(self._notice(suffix="prompt"), profile_name="design_consulting")

        self.assertIn("project_name", prompt)
        self.assertNotIn("DEEPSEEK_API_KEY", prompt)
        self.assertNotIn("tenant_access_token", prompt)
        self.assertNotIn("raw_payload", prompt)
        self.assertNotIn("FEISHU_APP_SECRET", prompt)

    def test_json_response_parses_into_structured_result(self) -> None:
        config = AIAnalysisConfig(enabled=True, api_key="key")
        client = _FakeClient(
            response=(
                '{"opportunity_score":82,"recommendation":"follow_up","summary":"Strong fit.",'
                '"reasons":["Matches profile"],"risks":["Tight deadline"],"follow_up_questions":["Who is PM?"]}'
            )
        )

        result = analyze_notice(self._notice(suffix="json"), config, profile_name="design_consulting", client=client)

        self.assertFalse(result.skipped)
        self.assertEqual(result.opportunity_score, 82)
        self.assertEqual(result.recommendation, "follow_up")
        self.assertEqual(result.reasons, ["Matches profile"])
        self.assertEqual(result.risks, ["Tight deadline"])
        self.assertEqual(result.follow_up_questions, ["Who is PM?"])

    def test_non_json_response_does_not_crash(self) -> None:
        config = AIAnalysisConfig(enabled=True, api_key="key")
        client = _FakeClient(response="Plain text summary only.")

        result = analyze_notice(self._notice(suffix="plain"), config, profile_name="design_consulting", client=client)

        self.assertFalse(result.skipped)
        self.assertEqual(result.summary, "Plain text summary only.")
        self.assertEqual(result.reasons, [])

    def test_network_error_does_not_break_flow(self) -> None:
        config = AIAnalysisConfig(enabled=True, api_key="key")
        client = _FakeClient(error=RuntimeError("network down"))

        result = analyze_notice(self._notice(suffix="error"), config, profile_name="design_consulting", client=client)

        self.assertTrue(result.skipped)
        self.assertEqual(result.skip_reason, "AI request failed")
        self.assertIn("network down", result.error)

    def test_analyze_notices_only_targets_direct_and_watchlist(self) -> None:
        config = AIAnalysisConfig(enabled=True, api_key="key", max_items=10)

        results = analyze_notices(
            [
                self._notice(suffix="direct", lead_tier="DIRECT"),
                self._notice(suffix="watch", lead_tier="WATCHLIST"),
                self._notice(suffix="exclude", lead_tier="EXCLUDE"),
            ],
            config,
            profile_name="design_consulting",
            client_factory=lambda _: _FakeClient(response='{"summary":"ok"}'),
        )

        self.assertEqual(len(results), 2)
        self.assertEqual({result.notice_key for result in results}, {"source|direct", "source|watch"})

    def test_analyze_notices_respects_limit(self) -> None:
        config = AIAnalysisConfig(enabled=True, api_key="key", max_items=1)

        results = analyze_notices(
            [self._notice(suffix="one"), self._notice(suffix="two")],
            config,
            profile_name="design_consulting",
            client_factory=lambda _: _FakeClient(response='{"summary":"ok"}'),
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].notice_key, "source|one")


class MainAndRunnerAIFlagTests(unittest.TestCase):
    def test_local_html_without_ai_flag_still_runs(self) -> None:
        from app.main import main
        from app.runner import RunSummary

        with mock.patch(
            "app.main.run_once",
            return_value=[RunSummary(source_name="construction", fetched_count=1, inserted_count=1, duplicate_count=0, pushed_count=1)],
        ) as run_once_mock:
            exit_code = main(["--local-html"])

        self.assertEqual(exit_code, 0)
        self.assertNotIn("enable_ai_analysis", run_once_mock.call_args.kwargs)

    def test_local_html_ai_flag_without_key_still_generates_html(self) -> None:
        from app.runner import run_once

        temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        notice = AIAnalysisTests()._notice(suffix="runner", lead_tier="DIRECT")
        source = {
            "name": "Source",
            "enabled": True,
            "module": "unused",
            "class": "unused",
            "url": "https://example.com",
            "region": "Hengyang",
            "source": "source",
            "source_subtype": "construction",
        }

        class _LocalAdapter:
            def __init__(self) -> None:
                self.last_crawl_stats = {"fetched_total": 1, "detail_success_count": 1}

            def crawl(self):
                return [notice]

        with (
            mock.patch("app.runner.DATA_DIR", temp_dir / "data"),
            mock.patch("app.runner.REPORT_DIR", temp_dir / "reports"),
            mock.patch("app.logging_utils.LOG_DIR", temp_dir / "logs"),
            mock.patch("app.runner.load_sources", return_value=[source]),
            mock.patch("app.runner._build_adapter", return_value=_LocalAdapter()),
            mock.patch(
                "app.runner.classify_notice",
                return_value={
                    "lead_tier": "DIRECT",
                    "lead_reason": "DIRECT reason",
                    "matched_positive_signals": ["design consulting"],
                    "matched_negative_signals": [],
                },
            ),
            mock.patch("app.runner.open_html_report", return_value=True),
            mock.patch.dict("os.environ", {"DEEPSEEK_API_KEY": ""}, clear=False),
        ):
            results = run_once(enable_feishu=False, html_report=True, enable_ai_analysis=True, ai_analysis_limit=5)

        self.assertEqual(len(results), 1)
        report_path = temp_dir / "reports" / "latest.html"
        self.assertTrue(report_path.exists())
        html = report_path.read_text(encoding="utf-8")
        self.assertIn("AI 分析已跳过：未配置 DEEPSEEK_API_KEY", html)


if __name__ == "__main__":
    unittest.main()
