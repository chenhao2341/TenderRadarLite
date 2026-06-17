# AI Analysis Validation

- Validation date: 2026-06-16
- Model target: `deepseek-v4-flash`
- Base URL: `https://api.deepseek.com`
- Endpoint: `https://api.deepseek.com/chat/completions`
- Real-check command: `python run_mvp.py --local-html --profile design_consulting --ai-analysis --ai-analysis-limit 3`

## Task 6-D goals

- Keep AI analysis as an opt-in helper rather than a default full-batch flow.
- Force all AI natural-language output to Simplified Chinese.
- Keep internal `recommendation` enum as `follow_up / watch / skip`, but render it as Chinese in HTML.
- Position AI as a general tendering and government-procurement lead triage assistant, not a single-industry expert system.
- Bind analysis focus to the active profile and signals instead of assuming every project is engineering or design consulting.
- Prevent unsupported amount-unit inference in both prompt instructions and HTML presentation.

## Problem found in manual acceptance

- The model previously turned raw numeric values such as `5631.436489` or `6351.45` into expressions like `5631万元` without explicit unit support in the structured fields.
- This is a high-risk hallucination because the original HTML only showed raw values and did not confirm `元 / 万元 / 亿元`.

## Guardrail decisions

- AI analysis remains disabled by default.
- Without `--ai-analysis`, the program must not call DeepSeek.
- `--ai-analysis-limit` remains the user-facing quantity control.
- Default analysis count stays small at 5.
- Single-run hard cap is 10.
- If the user requests a larger value, the program clamps it to 10 and reports: `AI 分析数量已限制为 10 条，避免 API 额度消耗过大。`

## Prompt positioning and professional boundary

- AI is positioned as a general China-mainland tendering and government-procurement lead triage assistant.
- AI supports multiple industries and should adapt to the active profile, not hard-code engineering or design-consulting logic for all notices.
- AI only helps business users decide whether a notice deserves deeper manual review.
- AI does not replace reading the original notice, attachments, bidding documents, qualification conditions, or scoring rules.
- AI is not legal advice.
- AI is not a final bid/no-bid decision maker.
- AI does not output bid-winning probability.

## Amount-unit guardrails

- Amount fields are passed to the model as raw structured values plus explicit unit-status metadata.
- If the structured field does not explicitly contain a unit, the prompt tells the model that the unit is unconfirmed and must not be inferred.
- The model is explicitly forbidden from converting `5631.436489` into `5631万元` unless the input field itself clearly includes `万元`.
- HTML now displays numeric-only amount fields as `原始值（单位未确认）` to reduce user misreading.
- If AI output still mentions amount units while the structured input has no confirmed unit, the result is marked with a manual-review risk reminder.

## Product positioning

- AI analysis is an auxiliary judgement aid, not a default full-batch pipeline.
- The expected usage is user-selected, small-sample analysis of priority opportunities.
- Future Web controls should allow users to choose specific projects, sources, or industries for AI analysis.
- This keeps API cost, runtime risk, and HTML report size under control.

## Company profile boundary

Enterprise match context is optional. Without `--company-profile`, AI prompt construction remains in general public monitoring mode and does not receive company profile summaries or enterprise match scores.

With `--company-profile`, the prompt may receive company profile summary, `opportunity_stage`, `company_match_score`, `company_match_level`, match reasons, mismatch reasons, and manual-review items. These fields are rule-scoring context only: AI must not replace the rule score, must not output bid-winning probability, must not treat correction/clarification notices as new opportunities, and must not claim it has read attachment full text.

## Real API re-check

- Pending after code/test verification in this turn.
- Acceptance focus:
  - HTML is generated successfully.
  - AI analysis blocks render in the report.
  - All natural-language fields are Simplified Chinese.
  - Recommendation labels display in Chinese.
  - Output remains professional, objective, and neutral.
  - Unsupported amount-unit inference does not reappear.
  - Manual-review reminders remain visible where needed.
  - No Feishu side effects.
  - No SQLite persistence for AI output.
  - No API key leakage.

## Task 4-C-DQ amount-context update

- Amount-unit quality is treated as an upstream structured-data problem first, not a prompt-only problem.
- The runtime amount context now prefers `raw_value`, `unit`, `unit_source`, and `raw_text_snippet`.
- When the source field is numeric-only but the current notice text clearly contains `元 / 万元 / 亿元`, the runtime context recovers that unit from the notice text and passes it to both HTML and AI.
- When the current source data and notice text still do not confirm the unit, HTML shows `单位未确认` and AI is required to keep the value unconverted.
- `单位未确认` does not mean the project has no value; AI should still judge follow-up value from grounded non-amount signals and recommend manual re-check where appropriate.

## Task 4-D attachment-review guardrails

- AI prompt now receives detail-page status, attachment count, coarse attachment flags, and up to five attachment titles.
- AI may use attachment discovery as a reason to suggest manual follow-up.
- AI must not claim that it has read the full attachment text.
- AI must not invent attachment content from title alone.
- If the detail page is unavailable, AI should explicitly suggest opening the original link for manual review.
- If no attachment is found, AI must not conclude that the project has no value only from that absence.
