# Known Limitations

TenderRadarLite 当前是本地优先的 `v0.1-alpha`。以下限制应被视为公开边界的一部分，而不是隐藏细节。

## 来源与字段质量

- Hengyang Construction 最近 10 条 live 样本存在非严格倒序 / 旧公告混入风险。
- Hengyang Construction 的更正 / 澄清 / 暂停类字段边界仍可继续加强。
- Changsha Procurement 当前为 `alpha`，默认关闭，部分 `deadline` 缺失，`content_summary` 语义偏弱。
- China Government Procurement Local 当前为 `alpha`，默认关闭，结果公告 `content_summary` 受原文限制。

## 集成与能力边界

- Feishu 是可选集成，不是默认主路径。
- AI 分析是可选 Alpha，不是成熟业务判断系统。
- 当前不下载附件。
- 当前不解析 PDF / DOC / DOCX。
- 当前不做自动投标。

## 产品与适用范围边界

- 当前不承诺全国稳定覆盖。
- 当前不承诺普通非技术用户零门槛使用。
- 当前不绕过登录 / 验证码 / 反爬。
- 当前 Web 控制台仍是 Alpha 骨架，不是完整运行入口。

## 如何理解这些限制

- `supported` 来源也可能仍有字段质量改进空间。
- `alpha` 来源不等于不可用，但不应作为当前主能力承诺。
- 这些限制不会阻止你本地验证主链路，但会影响对外发布时的能力表述。
