# TenderRadarLite Product Strategy

## 1. 产品定位

TenderRadarLite 不是全国招投标 SaaS，也不是单纯爬虫脚本，而是一个本地优先、可扩展的招投标线索发现与研判工具。

当前核心链路是：

内置来源抓取
→ 结构化
→ 去重
→ 行业 profiles 初筛
→ 本地 HTML 报告
→ 可选飞书同步
→ 可选 AI 辅助研判

这个定位强调两件事：一是本地优先，先把公开公告转成可读、可筛、可分享的线索；二是可扩展，后续可以围绕来源体系、行业能力和 AI 辅助逐步增强，而不是一开始就承诺做成全国全行业平台。

## 2. 目标用户

TenderRadarLite 当前更适合以下用户：

- 中小企业
- 设计咨询 / 规划设计 / 工程咨询公司
- 建筑工程 / 施工 / 改造类公司
- IT / 软件 / 数字化服务商
- 医疗设备 / 政府采购相关供应商
- AI 自动化实践者 / 开源使用者

这些用户有一些共通痛点：

- 每天手动刷招投标网站耗时
- 多地区多网站信息分散
- 公告重复、字段混乱
- 不知道哪些项目值得跟进
- 难以把线索同步给团队
- 非技术用户难以维护爬虫脚本

因此，产品的首要价值不是“抓更多网页”本身，而是把分散公告整理成可操作的线索流，并为后续判断和协作提供更低门槛的入口。

## 3. 当前已完成能力

从产品视角看，TenderRadarLite 已经具备一套可用的 Alpha / 工程化 MVP 基座：

- 已支持部分内置来源抓取
- 已支持本地 HTML 报告
- 已支持 `DIRECT / WATCHLIST / EXCLUDE` 分层
- 已支持 `design_consulting` profile
- 已支持可选飞书同步
- 已支持 Windows bat 双击入口
- 已具备 AI 分析插件工程骨架
- 已具备适配器扩展基础
- 已具备测试、文档、安全边界

这些能力说明项目已经不是零散脚本，但也必须明确：当前仍是 Alpha / 工程化 MVP，不是成熟全国平台，不承诺对所有地区、所有行业、所有网站稳定覆盖。

## 4. 双线开发模型

后续开发应明确分成两条线并行推进。

### 工程稳定线

负责：

- 测试
- Git checkpoint / tag
- 安全边界
- 配置隔离
- 错误兜底
- 兼容旧功能
- 本地运行稳定性
- Windows 入口 / 后续 EXE
- 不泄露密钥

工程稳定线的职责是把已有能力做稳，确保本地优先路线可持续维护，避免在产品扩展时破坏现有入口、配置和安全边界。

### 产品价值线

负责：

- 数据来源覆盖
- 来源知识库
- 未收录网站接入向导
- 行业 profile × 来源推荐
- 真实 AI 分析体验
- 业务价值案例
- 用户可操作入口
- GitHub / 作品集 / 演示传播

产品价值线的职责是让项目从“工程底座”走向“真正有用”。两条线必须并行，但不能互相污染。工程线保证稳定，产品线保证有用。

## 5. 产品能力分层：P0 / P1 / P2

### P0

- 真实 DeepSeek API 联调与 AI 输出验收
- 来源知识库 Source Catalog
- 未收录站点接入向导 Alpha
- 行业 profile 与推荐来源绑定
- 真实业务案例复盘
- 本地 Web 控制台原型

P0 的目标是把产品链路补完整，让用户能理解项目知道哪些来源、适合哪些行业、AI 能带来什么辅助价值，以及后续本地入口会长成什么样。

### P1

- 更多省市/行业来源适配
- 用户自定义来源配置
- 更好的 HTML 报告交互
- 飞书推送策略优化
- 定时任务
- Windows zip 发布包
- EXE alpha

P1 的目标是在 P0 产品定位稳定后，扩大覆盖范围并提升使用门槛与分发体验。

### P2

- RAG / 企业知识库
- Word 投标文档生成
- 附件 PDF / DOC 深度解析
- 云端部署
- 多用户账号
- 权限管理
- OnlyOffice 类在线编辑
- SaaS 化

P2 只作为远期方向，不应混入当前路线，不应反向挤占 P0 的产品验收和稳定性工作。

## 6. 来源体系设计

后续需要建立 Source Catalog，而不是继续停留在“只硬编码几个来源”的阶段。Source Catalog 的目标不是立刻接入所有网站，而是先把系统知道什么、支持到什么程度、接下来准备支持什么表达清楚。

建议字段：

- `source_id`
- `source_name`
- `url`
- `region`
- `level`：`national / province / city / county / industry`
- `source_type`：`government_procurement / public_resource / construction_exchange / industry_portal / other`
- `industry_tags`
- `supported_profiles`
- `adapter_status`：`supported / partial / planned / research / unsupported`
- `crawl_method`：`api_json / static_html / js_rendered / manual_review / unknown`
- `notes`
- `risks`

Source Catalog 的作用包括：

- 告诉用户系统知道哪些来源
- 告诉用户哪些已支持、哪些计划支持
- 给行业 profile 推荐来源
- 为后续站点接入向导提供归档目标
- 让项目看起来不是只靠几个固定网页

## 7. 未收录网站接入向导

这里的输入对象不是单条公告详情页，而是用户提供的、尚未被系统收录的官方/地方招投标网站或栏目页。

第一版目标能力是：用户输入一个招投标网站栏目 URL 后，系统做只读侦察，并输出接入建议。侦察项应包括：

- 能否访问
- 是否有公告列表
- 是否有详情链接
- 是否有分页
- 是否有发布时间
- 是否疑似 JSON 接口
- 是否疑似 JS 渲染
- 是否需要人工适配
- 推荐接入方式
- 生成候选 `source_id / source_name`
- 输出接入风险和下一步建议

第一版边界也要明确：

- 只做侦察和接入建议
- 不自动修改 config
- 不自动生成正式 adapter
- 不承诺适配所有网站

这个能力的意义在于，把“用户发现了一个官方栏目但项目还不认识它”这件事，从人工口头反馈，变成可归档、可评估、可排期的产品流程。

## 8. 行业 profile × 来源推荐

profiles 不应该只是关键词库，还应该逐步和推荐来源建立关联关系。用户不一定知道该刷哪些站，但系统可以先基于行业提供一个较高相关度的起点。

示例：

- `design_consulting`：规划设计、建筑设计、工程咨询、城市更新、可研、方案设计类来源
- `construction`：建设工程、施工、改造、EPC、监理、总承包类来源
- `software_it`：政府采购、信息化、系统集成、软件开发、数字化平台类来源
- `medical_equipment`：政府采购、医疗器械、设备采购类来源

未来理想体验应是：

用户选择行业
→ 系统推荐对应来源
→ 抓取相关公告
→ profile 初筛
→ AI 辅助研判
→ 本地报告 / 飞书同步

这样，profile 的价值会从“筛选规则”扩展为“行业线索发现入口”。

## 9. AI 分析定位

AI 不是主判断系统，它的位置应放在规则 profile 初筛之后，作为辅助研判层。

AI 分析不是默认全量分析，也不应该无差别覆盖全部抓取公告。更合理的产品定位是：由用户按需启用，对少量重点线索做辅助研判，用来帮助人工判断是否值得继续跟进。

AI 的行业定位也必须保持通用和可扩展。TenderRadarLite 面向的是中国大陆招投标、政府采购、公共资源交易线索发现与研判，不应把 AI 身份固定成建设工程或设计咨询单一领域助手。当前更合理的设计是：AI 根据所选 profile、公告类型、命中信号和结构化摘要动态调整分析重点；如果 profile 未知，则退回通用招投标初筛视角，而不是强行套用某一行业逻辑。

AI 不改变 `lead_tier`，不替代 `DIRECT / WATCHLIST / EXCLUDE`，不编造信息，只基于已结构化字段给出：

- 商机摘要
- 跟进理由
- 风险点
- 建议追问问题
- 简单评分
- 是否建议人工跟进

当前策略应继续保持：

- 默认关闭，只有用户显式传入 `--ai-analysis` 才调用模型
- 默认只建议分析少量重点线索，而不是批量全量分析
- 当前仅针对 `DIRECT / WATCHLIST` 做辅助研判
- 需要用 `--ai-analysis-limit` 控制数量，并设置单次硬上限，避免 API 成本失控、程序风险上升、HTML 报告过大
- 后续 Web 控制台应支持用户按项目、来源、行业手动选择分析对象，而不是强制自动分析全部结果
- AI 不替代人工审查招标文件、附件、资格条件和评分办法，不作为法律意见，也不作为最终投标决策
- AI 不输出中标概率，不对金额单位、资质条件、时间节点做无依据推断；金额单位未确认时应明确提示人工复核原公告及附件

当前必须明确：

- 任务 6-A 只是 AI 分析插件工程骨架
- 任务 6-B 才是 DeepSeek 真实 API 联调与产品验收

因此，现阶段不能把“已具备 AI 骨架”对外表述成“已经完成成熟 AI 研判能力”。

## 10. 任务 6-B 验收标准

任务 6-B 的验收应尽量贴近真实产品使用，而不是只看代码能否跑通。建议标准如下：

- 本地配置真实 `DEEPSEEK_API_KEY`
- 执行 `--ai-analysis`
- 只分析 `DIRECT / WATCHLIST` 前 3-5 条
- HTML 报告中能看到 AI 分析区
- AI 输出包含摘要、评分、跟进理由、风险点、建议追问
- 人工检查是否胡编
- 人工判断是否比规则筛选更有帮助
- 记录耗时和成本
- 无 Key 时仍可跳过
- API 失败不影响报告
- 不写飞书、不写 SQLite、不泄露 Key

验收重点不是“模型有响应”本身，而是输出是否对跟进判断有帮助、失败时是否足够安全、成本是否在可接受范围内。

## 11. 不做什么 / 不过度承诺

当前阶段不承诺以下事项：

- 全国所有招投标网站都能稳定抓取
- 所有 JS 网站都能自动解析
- 所有 PDF / DOC 附件都能解析
- 自动生成正式投标文件
- 替代人工判断
- 企业级 SaaS
- 多用户权限系统
- 成熟 RAG 知识库
- OnlyOffice 在线编辑

这些边界必须持续写进 README、演示说明和后续发布材料，避免把 Alpha / 工程化 MVP 错误包装成成熟商业平台。

## 12. 后续建议路线

推荐顺序如下：

1. 冻结任务 6-A AI 分析插件工程骨架
2. P-0 产品策略文档
3. 任务 6-B DeepSeek 真实 API 联调与产品验收
4. P-A Source Catalog 来源知识库
5. P-B 未收录网站接入向导 Alpha
6. P-C 行业 profile × 来源推荐
7. 任务 7-A 本地 Web 控制台
8. 任务 7-B Windows zip 发布包
9. 任务 7-C EXE alpha
10. 任务 8 GitHub 开源发布与作品集包装

这个顺序的原则是：先冻结已有工程骨架，再完成产品定位与验收，再进入面向用户价值的扩展，不跳步，不提前承诺云端化和 SaaS 化能力。

## 13. 一句话产品表达

TenderRadarLite 是一个本地优先的招投标线索发现工具，可以自动抓取公开公告、去重、按行业筛选高价值线索，并生成本地报告；后续将支持来源知识库、未收录网站接入向导和 AI 辅助研判。
## Amount-unit strategy update

- Amount-unit accuracy for existing sources is treated as an upstream data-quality problem, not a prompt-only problem.
- HTML should show the real confirmed unit when current source data or notice text confirms it, and `单位未确认` only when the unit still cannot be recovered.
- AI analysis should consume amount raw value, unit, unit source, and raw text snippet when available.
- AI must not guess amount units or force unsupported conversions.
- `单位未确认` does not automatically mean `skip`; users still need grounded follow-up suggestions based on non-amount signals.

## Task 4-D strategy update

- Task 4-D is positioned as `公告详情与附件发现 Alpha`, not as full bidding-document intelligence.
- The product value in this phase is to help users notice that key facts may live in detail pages or attachments, then prompt targeted manual review.
- Current scope:
  - detail-page availability check,
  - attachment link discovery,
  - attachment title recognition,
  - coarse file-type recognition,
  - coarse attachment-category recognition,
  - HTML presentation,
  - AI reminder to review original notice and attachments.
- Out of scope in this phase:
  - downloading attachment bodies,
  - parsing PDF / DOC / DOCX / XLS / XLSX,
  - OCR,
  - RAG or knowledge base,
  - automatic qualification-fit judgement,
  - automatic scoring-method analysis,
  - full bid/no-bid decision.
- AI remains a helper only. It may mention that a likely bidding file or bill file exists, but it must not claim to have read the full attachment text and must not invent attachment content from titles alone.
- Amount unit, qualification requirements, scoring method, procurement demand, and deadline interpretation still require human review against the original notice and attachments.
- This Alpha can serve later as a prerequisite layer for a second-phase `ai_bidding` style intelligent bidding-document analysis system, but that system is explicitly out of scope for Task 4-D.

## Optional enterprise opportunity mode

TenderRadarLite supports two open-source usage modes that share the same foundation.

1. 通用公开监控模式：
   面向通用多来源招投标公告监控、来源知识库、行业 profile 和公开报告。

2. 企业定制商机模式：
   在通用监控基础上，额外传入 company profile，对公告进行企业匹配评分和商机分层。

The enterprise opportunity workbench is an optional advanced mode in the open-source project, not a replacement for the public monitoring roadmap. The default route remains general public monitoring: multiple sources, Source Catalog, unlisted-site onboarding guidance, industry profile support, local HTML reports, optional Feishu sync, AI notice-level triage, future local Web console, open-source release, and documentation/showcase materials.

Enterprise mode is enabled only when a user passes `--company-profile`. In that mode the shared `Notice` pipeline additionally carries `opportunity_stage`, `company_match_score`, `company_match_level`, match reasons, mismatch reasons, and manual-review items for enterprise-level sorting and explanation.

This does not overturn Source Catalog, the unlisted-site onboarding guide, industry profile × source recommendation, the Web console roadmap, or open-source publication. Company profile, enterprise scoring, the enterprise workbench, up to three重点来源配置, high-match deep-analysis queues, and future `ai_bidding` fork/bridge integration are branch capabilities built on the same public foundation, not the only main line.
