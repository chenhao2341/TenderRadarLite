# 项目架构

## 入口与核心模块

- `run_mvp.py` / `app/main.py`
  - CLI 入口，负责解析命令参数并分发到不同运行模式。
- `app/runner.py`
  - 运行编排核心，负责加载来源、调用适配器、分类、存储和输出。
- `app/models.py`
  - 定义 `Notice`、`RawNotice`、`RawNoticeDetail` 等核心数据模型。
- `app/adapters/`
  - 各来源适配器实现目录。
- `app/adapters/registry.py`
  - 适配器 registry，负责按配置创建实际 adapter。
- `app/profiles.py`
  - 行业 profiles 的加载和校验入口。
- `app/storage.py`
  - SQLite 存储与去重。
- `app/html_report.py`
  - 本地 HTML 报告生成与打开逻辑。
- `app/feishu.py`
  - 可选飞书输出能力。
- `scripts/`
  - Windows 双击入口脚本。

## 数据流

```text
source adapter
-> Notice
-> storage / classification
-> HTML report / optional Feishu
```

更细一点的过程如下：

1. `config/sources.json` 提供启用的来源配置。
2. `app/runner.py` 通过 `app/adapters/registry.py` 创建对应 adapter。
3. adapter 抓取原始公告并组装成 `Notice`。
4. 系统加载关键字和 profile，对公告做轻量分类。
5. `app/storage.py` 负责写入 SQLite 并做去重。
6. 根据运行模式输出到本地 HTML，或在显式启用时写入飞书。

## 运行模式

- `--local-only`
  - 本地抓取与存储，不启用飞书。
- `--local-structured-preview`
  - 生成本地结构化预览。
- `--local-html`
  - 生成本地 HTML 报告，不启用飞书。
- 默认无参数
  - 允许走飞书能力，但是否真的输出取决于本地环境配置。

## 目录结构概览

```text
app/
config/
data/
docs/
examples/
logs/
profiles/
reports/
scripts/
tests/
```

## AI Analysis Alpha

- `app/ai_analysis.py` 提供默认关闭的 AI 辅助研判能力，只在 `--local-html --ai-analysis` 时启用。
- AI 只读取已结构化的 `Notice` 字段，不重新抓取、不改变 `lead_tier`，不写入 SQLite，也不进入飞书链路。
- 无密钥或请求失败时，本地 HTML 主流程保持可用，仅在控制台或 HTML 中提示 AI 已跳过。
- AI 自然语言字段必须输出简体中文；`recommendation` 内部仍保留 `follow_up / watch / skip` 枚举，展示层再映射为中文。
- AI 的定位是“通用招投标 / 政府采购线索初筛助手”，不是某一单独行业的专家系统，也不应默认所有项目都是建设工程或设计咨询项目。
- AI 会结合当前 profile、公告类型和命中信号动态调整分析重点；随着 profiles 增多，这一层应继续保持行业可扩展，而不是写死单一行业逻辑。
- AI 只帮助业务人员判断是否值得进一步查看原公告，不替代人工审查招标文件、附件、资格条件和评分办法，不作为法律意见，也不作为最终投标决策。
- AI 不输出中标概率，不对金额单位、资质条件、时间节点做无依据推断。
- 对预算金额、最高限价等字段，若结构化输入未明确单位，则 prompt 和 HTML 都按“原始值 / 单位未确认”处理，避免把数字误读为万元或亿元。
- AI 分析不是默认全量分析，而是用户按需启用的辅助研判；默认建议分析少量重点线索，默认 5 条，单次硬上限 10 条。
- 当前仅分析聚合后 `DIRECT / WATCHLIST` 项目的代表公告，避免对全部抓取结果做无差别批量分析。
- DeepSeek OpenAI-compatible 默认配置为：`DEEPSEEK_BASE_URL=https://api.deepseek.com`、`DEEPSEEK_MODEL=deepseek-v4-flash`。
- 实际请求 endpoint 为：`https://api.deepseek.com/chat/completions`，`base_url` 由环境变量提供，`app/ai_analysis.py` 内部拼接 `/chat/completions`。

## 设计边界

- adapter 负责来源差异，不负责全局存储策略。
- profile 负责轻量行业筛选，不替代人工判断。
- HTML 是默认本地输出路径。
- 飞书是可选插件，不应作为核心运行前提。
## Amount context

- Amount-unit handling for existing sources is a runtime parsing concern layered on top of current structured fields.
- Adapters keep the original numeric `budget_amount` / `ceiling_price` values and try to recover unit evidence from the current notice text.
- Recovered evidence is passed forward as runtime-only context such as unit, unit source, and raw text snippet; this avoids a SQLite schema change.
- HTML and AI share the same amount-context interpretation so the display layer and prompt layer do not diverge on unit handling.

## Task 4-D Attachment Discovery Alpha

- Task 4-D adds a lightweight `公告详情与附件发现 Alpha` layer between notice discovery and report rendering.
- The scope is limited to:
  - checking whether the current source detail page or detail API is available,
  - discovering explicit attachment links or structured attachment entries,
  - identifying attachment title, coarse file type, and coarse category,
  - surfacing the result in local HTML and AI prompt context.
- The runtime helper lives in `app/attachment_utils.py`.
- `Notice` now carries runtime-only attachment review fields such as `detail_checked`, `detail_available`, `attachments`, `attachments_found`, and `detail_risk_note`.
- These fields are not persisted to SQLite, so Task 4-D does not require any schema change.
- Current adapters only inspect already-enabled Hengyang sources and do not expand source coverage.
- The implementation does not download attachment bodies and does not parse PDF, Word, Excel, OCR, or RAG content.
- Attachment title and coarse type are treated only as manual-review clues; final judgement must still use the original notice and original attachments.

## Optional enterprise opportunity mode

TenderRadarLite has two coexisting open-source routes:

1. General public monitoring mode: the default mode for public tender monitoring, Source Catalog, unlisted-site onboarding guidance, industry profiles, local HTML, optional Feishu sync, AI notice triage, future Web console, and open-source documentation.
2. Enterprise custom opportunity mode: an optional mode enabled by `--company-profile`, adding company profile loading, enterprise match scoring, and the enterprise opportunity view on top of the same notice pipeline.

Shared foundation:

- adapters
- `Notice`
- HTML report generation
- attachment discovery
- amount-unit guardrails
- AI triage
- tests
- documentation

Default behavior remains the public monitoring mode. `python run_mvp.py --local-html --profile design_consulting` keeps the general report path and does not require a company profile. `python run_mvp.py --local-html --profile design_consulting --company-profile profiles/company_sample.yaml` enables enterprise scoring and the enterprise opportunity view.

The enterprise fields are runtime-only in this Alpha and are not persisted to SQLite. The enterprise view is not forced into the default report, and enterprise scoring does not replace `DIRECT / WATCHLIST / EXCLUDE`.
