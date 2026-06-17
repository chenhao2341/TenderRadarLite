from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.ai_analysis import (
    AIAnalysisConfig,
    AMOUNT_UNIT_RISK_TEXT,
    DEFAULT_AI_ANALYSIS_MAX_ITEMS,
    MAX_AI_ANALYSIS_ITEMS,
    MISSING_KEY_REASON,
    OpenAICompatibleClient,
    UNIT_UNCONFIRMED_TEXT,
    analyze_notice,
    analyze_notices,
    build_notice_analysis_prompt,
    has_explicit_amount_unit,
)
from app.amount_utils import RAW_TEXT_SOURCE, amount_unit_source_label, parse_amount_context
from app.html_report import build_html_report
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


class _FakeAdapter:
    def __init__(self, notices: list[Notice]) -> None:
        self._notices = notices
        self.last_crawl_stats = {"fetched_total": len(notices), "detail_success_count": len(notices)}

    def crawl(self) -> list[Notice]:
        return list(self._notices)


class AIAnalysisTests(unittest.TestCase):
    def _notice(
        self,
        *,
        suffix: str,
        lead_tier: str = "DIRECT",
        budget_amount: str = "5631.436489",
        ceiling_price: str = "6351.45",
        budget_amount_unit: str = "",
        budget_amount_unit_source: str = "",
        budget_amount_raw_text_snippet: str = "",
        ceiling_price_unit: str = "",
        ceiling_price_unit_source: str = "",
        ceiling_price_raw_text_snippet: str = "",
    ) -> Notice:
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
            bid_open_or_response_deadline="2026-06-20 09:00:00",
            budget_amount=budget_amount,
            ceiling_price=ceiling_price,
            budget_amount_unit=budget_amount_unit,
            budget_amount_unit_source=budget_amount_unit_source,
            budget_amount_raw_text_snippet=budget_amount_raw_text_snippet,
            ceiling_price_unit=ceiling_price_unit,
            ceiling_price_unit_source=ceiling_price_unit_source,
            ceiling_price_raw_text_snippet=ceiling_price_raw_text_snippet,
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
        self.assertEqual(result.skip_reason, MISSING_KEY_REASON)

    def test_from_env_defaults_to_deepseek_v4_flash_and_default_limit(self) -> None:
        with mock.patch.dict(
            "os.environ",
            {
                "DEEPSEEK_API_KEY": "",
                "DEEPSEEK_BASE_URL": "",
                "DEEPSEEK_MODEL": "",
                "AI_ANALYSIS_TIMEOUT_SECONDS": "",
                "AI_ANALYSIS_MAX_ITEMS": "",
            },
            clear=False,
        ):
            config = AIAnalysisConfig.from_env(enabled=True)

        self.assertEqual(config.base_url, "https://api.deepseek.com")
        self.assertEqual(config.model, "deepseek-v4-flash")
        self.assertEqual(config.timeout_seconds, 30)
        self.assertEqual(config.max_items, DEFAULT_AI_ANALYSIS_MAX_ITEMS)

    def test_from_env_clamps_overlarge_limit_to_hard_cap(self) -> None:
        with mock.patch.dict("os.environ", {"AI_ANALYSIS_MAX_ITEMS": "100"}, clear=False):
            config = AIAnalysisConfig.from_env(enabled=True)

        self.assertEqual(config.max_items, MAX_AI_ANALYSIS_ITEMS)

    def test_client_posts_to_openai_compatible_chat_completions_endpoint(self) -> None:
        config = AIAnalysisConfig(
            enabled=True,
            api_key="key",
            base_url="https://api.deepseek.com",
            model="deepseek-v4-flash",
        )
        session = mock.Mock()
        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"choices": [{"message": {"content": '{"summary":"ok"}'}}]}
        session.post.return_value = response

        client = OpenAICompatibleClient(config, session=session)
        client.create_chat_completion("prompt")

        session.post.assert_called_once()
        self.assertEqual(session.post.call_args.args[0], "https://api.deepseek.com/chat/completions")
        self.assertEqual(session.post.call_args.kwargs["json"]["model"], "deepseek-v4-flash")

    def test_prompt_sets_general_tender_identity_without_single_industry_binding(self) -> None:
        prompt = build_notice_analysis_prompt(self._notice(suffix="identity"), profile_name="design_consulting")

        self.assertIn("中国大陆招投标与政府采购线索研判助手", prompt)
        self.assertIn("不得默认按建设工程或设计咨询逻辑分析所有项目", prompt)
        self.assertIn("unknown_profile", prompt)
        self.assertNotIn("唯一场景", prompt)

    def test_prompt_includes_professional_boundaries(self) -> None:
        prompt = build_notice_analysis_prompt(self._notice(suffix="boundary"), profile_name="software_it")

        self.assertIn("不是评标委员会", prompt)
        self.assertIn("不是法律顾问", prompt)
        self.assertIn("不替代人工审核", prompt)
        self.assertIn("不输出中标概率", prompt)
        self.assertIn("线索跟进价值，不是中标概率", prompt)

    def test_prompt_requires_simplified_chinese_and_disallows_english_natural_language(self) -> None:
        prompt = build_notice_analysis_prompt(self._notice(suffix="language"), profile_name="medical_equipment")

        self.assertIn("所有自然语言字段必须使用简体中文", prompt)
        self.assertIn("不得使用英文自然语言", prompt)
        self.assertIn("recommendation", prompt)

    def test_prompt_forbids_inventing_amount_units_and_other_missing_fields(self) -> None:
        prompt = build_notice_analysis_prompt(self._notice(suffix="amount"), profile_name="construction")

        self.assertIn("不得推断为元、万元、亿元", prompt)
        self.assertIn("金额原始数值为 xxx，单位未确认", prompt)
        self.assertIn("不得把 5631.436489 写成 5631万元", prompt)
        self.assertIn("不得编造预算单位、资质要求、采购人、项目地点、报名时间、开标时间", prompt)

    def test_prompt_marks_numeric_only_amount_fields_as_unit_unconfirmed(self) -> None:
        prompt = build_notice_analysis_prompt(
            self._notice(suffix="numeric-only", budget_amount="5631.436489", ceiling_price="6351.45"),
            profile_name="design_consulting",
        )

        self.assertIn('"raw_value": "5631.436489"', prompt)
        self.assertIn(f'"unit": "{UNIT_UNCONFIRMED_TEXT}"', prompt)
        self.assertIn('"unit_source": "未确认"', prompt)
        self.assertIn('"budget_amount": {', prompt)
        self.assertNotIn('"raw_value": "5631万元"', prompt)

    def test_prompt_keeps_explicit_amount_units_when_present(self) -> None:
        prompt = build_notice_analysis_prompt(
            self._notice(suffix="explicit-unit", budget_amount="5631.436489万元", ceiling_price="6351.45元"),
            profile_name="design_consulting",
        )

        self.assertIn('"raw_value": "5631.436489"', prompt)
        self.assertIn('"unit": "万元"', prompt)
        self.assertIn('"unit_source": "源字段"', prompt)

    def test_prompt_includes_amount_source_and_snippet_when_context_is_available(self) -> None:
        prompt = build_notice_analysis_prompt(
            self._notice(
                suffix="amount-context",
                budget_amount="5631.436489",
                budget_amount_unit="万元",
                budget_amount_unit_source=RAW_TEXT_SOURCE,
                budget_amount_raw_text_snippet="本项目最高投标限价5631.436489万元",
            ),
            profile_name="design_consulting",
        )

        self.assertIn('"raw_value": "5631.436489"', prompt)
        self.assertIn('"unit": "万元"', prompt)
        self.assertIn(f'"unit_source": "{amount_unit_source_label(RAW_TEXT_SOURCE)}"', prompt)
        self.assertIn('"raw_text_snippet": "本项目最高投标限价5631.436489万元"', prompt)

    def test_prompt_states_unit_uncertainty_does_not_mean_no_value(self) -> None:
        prompt = build_notice_analysis_prompt(self._notice(suffix="uncertain-not-skip"), profile_name="design_consulting")

        self.assertIn("金额单位不能判断，不等于项目没有跟进价值", prompt)
        self.assertIn("不得仅因单位未确认就自动建议 skip", prompt)

    def test_prompt_includes_general_announcement_type_guidance(self) -> None:
        prompt = build_notice_analysis_prompt(self._notice(suffix="notice-type"), profile_name="unknown")

        self.assertIn("更正公告", prompt)
        self.assertIn("澄清公告", prompt)
        self.assertIn("流标公告", prompt)
        self.assertIn("中标公告", prompt)
        self.assertIn("暂停公告", prompt)

    def test_prompt_includes_dynamic_profile_guidance(self) -> None:
        prompt = build_notice_analysis_prompt(self._notice(suffix="profile"), profile_name="software_it")

        self.assertIn("software_it", prompt)
        self.assertIn("数字化平台", prompt)
        self.assertIn("medical_equipment", prompt)
        self.assertIn("不得强行套用某一行业逻辑", prompt)

    def test_prompt_does_not_include_secret_fields(self) -> None:
        prompt = build_notice_analysis_prompt(self._notice(suffix="secret"), profile_name="design_consulting")

        self.assertNotIn("DEEPSEEK_API_KEY", prompt)
        self.assertNotIn("tenant_access_token", prompt)
        self.assertNotIn("raw_payload", prompt)
        self.assertNotIn("FEISHU_APP_SECRET", prompt)

    def test_json_response_parses_into_structured_result(self) -> None:
        config = AIAnalysisConfig(enabled=True, api_key="key")
        client = _FakeClient(
            response=(
                '{"opportunity_score":82,"recommendation":"follow_up","summary":"该项目具备进一步跟进价值。",'
                '"reasons":["与画像匹配"],"risks":["需复核资质条件"],"follow_up_questions":["投标截止时间是否仍有效？"]}'
            )
        )

        result = analyze_notice(self._notice(suffix="json"), config, profile_name="design_consulting", client=client)

        self.assertFalse(result.skipped)
        self.assertEqual(result.opportunity_score, 82)
        self.assertEqual(result.recommendation, "follow_up")
        self.assertEqual(result.reasons, ["与画像匹配"])
        self.assertEqual(result.risks, ["需复核资质条件"])
        self.assertEqual(result.follow_up_questions, ["投标截止时间是否仍有效？"])

    def test_non_json_response_does_not_crash(self) -> None:
        config = AIAnalysisConfig(enabled=True, api_key="key")
        client = _FakeClient(response="仅返回一段中文摘要。")

        result = analyze_notice(self._notice(suffix="plain"), config, profile_name="design_consulting", client=client)

        self.assertFalse(result.skipped)
        self.assertEqual(result.summary, "仅返回一段中文摘要。")
        self.assertEqual(result.reasons, [])
        self.assertEqual(result.risks, [])

    def test_amount_unit_risk_is_appended_when_model_mentions_unconfirmed_units(self) -> None:
        config = AIAnalysisConfig(enabled=True, api_key="key")
        client = _FakeClient(
            response=(
                '{"opportunity_score":75,"recommendation":"watch","summary":"预算约为5631万元，建议继续观察。",'
                '"reasons":["金额较大"],"risks":[],"follow_up_questions":["金额单位是否在原公告中明确？"]}'
            )
        )

        result = analyze_notice(self._notice(suffix="unit-risk"), config, profile_name="design_consulting", client=client)

        self.assertIn(AMOUNT_UNIT_RISK_TEXT, result.risks)

    def test_unconfirmed_amount_units_are_sanitized_from_ai_text(self) -> None:
        config = AIAnalysisConfig(enabled=True, api_key="key")
        client = _FakeClient(
            response=(
                '{"opportunity_score":75,"recommendation":"watch",'
                '"summary":"最高投标限价为5631.436489万元，建议继续观察。",'
                '"reasons":["预算6351.45元需要关注"],'
                '"risks":[],"follow_up_questions":["5631.436489万元对应的单位是否在原公告中明确？"]}'
            )
        )

        result = analyze_notice(self._notice(suffix="sanitize"), config, profile_name="design_consulting", client=client)

        self.assertNotIn("5631.436489万元", result.summary)
        self.assertIn("金额原始数值为5631.436489，单位未确认", result.summary)
        self.assertIn("金额原始数值为6351.45，单位未确认", result.reasons[0])
        self.assertIn("金额原始数值为5631.436489，单位未确认", result.follow_up_questions[0])

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

    def test_has_explicit_amount_unit_detects_common_units(self) -> None:
        self.assertTrue(has_explicit_amount_unit("5631.43万元"))
        self.assertTrue(has_explicit_amount_unit("人民币 200 元"))
        self.assertFalse(has_explicit_amount_unit("5631.436489"))

    def test_parse_amount_context_extracts_wanyuan_from_text(self) -> None:
        context = parse_amount_context(
            "570.89",
            text_sources=[(RAW_TEXT_SOURCE, "预算金额为570.89万元，详见公告。")],
            field_hints=("预算",),
        )

        self.assertEqual(context.unit, "万元")
        self.assertEqual(context.unit_source, RAW_TEXT_SOURCE)
        self.assertIn("570.89万元", context.raw_text_snippet)

    def test_parse_amount_context_extracts_yuan_from_text(self) -> None:
        context = parse_amount_context(
            "1200000",
            text_sources=[(RAW_TEXT_SOURCE, "最高限价为1200000元，超过无效。")],
            field_hints=("最高", "限价"),
        )

        self.assertEqual(context.unit, "元")

    def test_parse_amount_context_extracts_yiyuan_from_text(self) -> None:
        context = parse_amount_context(
            "1.2",
            text_sources=[(RAW_TEXT_SOURCE, "投资估算约1.2亿元，建设期两年。")],
            field_hints=("投资", "估算"),
        )

        self.assertEqual(context.unit, "亿元")

    def test_parse_amount_context_returns_unknown_for_numeric_only_value(self) -> None:
        context = parse_amount_context("5631.436489")

        self.assertIsNone(context.unit)
        self.assertEqual(context.unit_source, "unknown")


class HTMLReportAIAnalysisTests(unittest.TestCase):
    def _notice(self, **kwargs) -> Notice:
        kwargs.setdefault("budget_amount", "5631.436489")
        kwargs.setdefault("ceiling_price", "6351.45")
        return AIAnalysisTests()._notice(suffix="html", **kwargs)

    def test_html_recommendation_follow_up_is_localized(self) -> None:
        notice = self._notice()
        html = build_html_report(
            [notice],
            ai_results={
                "section:section-html": mock.Mock(
                    skipped=False,
                    opportunity_score=88,
                    recommendation="follow_up",
                    summary="建议重点跟进。",
                    reasons=["画像匹配"],
                    risks=["需复核资质条件"],
                    follow_up_questions=["项目负责人是谁？"],
                )
            },
        )

        self.assertIn("建议跟进", html)
        self.assertNotIn(">follow_up<", html)

    def test_html_recommendation_watch_and_skip_are_localized(self) -> None:
        notice = self._notice()
        watch_html = build_html_report(
            [notice],
            ai_results={
                "section:section-html": mock.Mock(
                    skipped=False,
                    opportunity_score=70,
                    recommendation="watch",
                    summary="继续观察。",
                    reasons=[],
                    risks=[],
                    follow_up_questions=[],
                )
            },
        )
        skip_html = build_html_report(
            [notice],
            ai_results={
                "section:section-html": mock.Mock(
                    skipped=False,
                    opportunity_score=30,
                    recommendation="skip",
                    summary="建议跳过。",
                    reasons=[],
                    risks=[],
                    follow_up_questions=[],
                )
            },
        )

        self.assertIn("继续观察", watch_html)
        self.assertIn("建议跳过", skip_html)

    def test_html_marks_amounts_without_explicit_units_as_unconfirmed(self) -> None:
        html = build_html_report([self._notice()])

        self.assertIn("5631.436489（单位未确认）", html)
        self.assertIn("6351.45（单位未确认）", html)

    def test_html_keeps_amounts_with_explicit_units(self) -> None:
        html = build_html_report([self._notice(budget_amount="5631.436489万元", ceiling_price="6351.45元")])

        self.assertIn("5631.436489 万元", html)
        self.assertIn("6351.45 元", html)
        self.assertNotIn("5631.436489万元（单位未确认）", html)

    def test_html_uses_runtime_amount_context_when_unit_is_not_embedded_in_value(self) -> None:
        html = build_html_report(
            [
                self._notice(
                    budget_amount="5631.436489",
                    budget_amount_unit="万元",
                    budget_amount_unit_source=RAW_TEXT_SOURCE,
                    ceiling_price="1200000",
                    ceiling_price_unit="元",
                    ceiling_price_unit_source=RAW_TEXT_SOURCE,
                )
            ]
        )

        self.assertIn("5631.436489 万元", html)
        self.assertIn("1200000 元", html)


class MainAndRunnerAIFlagTests(unittest.TestCase):
    def _notice(self, suffix: str = "runner", lead_tier: str = "DIRECT") -> Notice:
        return AIAnalysisTests()._notice(suffix=suffix, lead_tier=lead_tier)

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
        notice = self._notice()
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

        with (
            mock.patch("app.runner.DATA_DIR", temp_dir / "data"),
            mock.patch("app.runner.REPORT_DIR", temp_dir / "reports"),
            mock.patch("app.logging_utils.LOG_DIR", temp_dir / "logs"),
            mock.patch("app.runner.load_sources", return_value=[source]),
            mock.patch("app.runner._build_adapter", return_value=_FakeAdapter([notice])),
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
        self.assertIn(MISSING_KEY_REASON, html)

    def test_overlarge_ai_limit_is_capped_and_reported(self) -> None:
        from app.runner import run_once

        temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        notices = [self._notice(suffix=f"n{i}") for i in range(12)]
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

        with (
            mock.patch("app.runner.DATA_DIR", temp_dir / "data"),
            mock.patch("app.runner.REPORT_DIR", temp_dir / "reports"),
            mock.patch("app.logging_utils.LOG_DIR", temp_dir / "logs"),
            mock.patch("app.runner.load_sources", return_value=[source]),
            mock.patch("app.runner._build_adapter", return_value=_FakeAdapter(notices)),
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
            mock.patch("app.runner.analyze_notices", return_value=[]) as analyze_notices_mock,
            mock.patch.dict("os.environ", {"DEEPSEEK_API_KEY": "fake-key"}, clear=False),
        ):
            run_once(enable_feishu=False, html_report=True, enable_ai_analysis=True, ai_analysis_limit=100)

        config = analyze_notices_mock.call_args.args[1]
        self.assertEqual(config.max_items, MAX_AI_ANALYSIS_ITEMS)
        html = (temp_dir / "reports" / "latest.html").read_text(encoding="utf-8")
        self.assertIn(f"AI 分析数量已限制为 {MAX_AI_ANALYSIS_ITEMS} 条", html)


if __name__ == "__main__":
    unittest.main()
