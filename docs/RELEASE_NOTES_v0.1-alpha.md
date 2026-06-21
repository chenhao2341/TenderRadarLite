# TenderRadarLite v0.1-alpha Release Notes

## 版本定位

`v0.1-alpha` 是本地优先招投标线索发现与字段质量审计 Alpha 版本。

当前版本强调的是：

- 本地优先
- 安全默认值
- 双 `supported` 来源主路径
- 默认关闭的 `alpha` 异构来源扩展能力
- 本地 HTML 报告与字段质量审计 workflow

## 已完成能力

- 2 个默认 `supported` 来源
- 2 个默认关闭 `alpha` 来源
- JSON API 来源支持
- static HTML 来源支持
- SQLite 去重
- 本地 HTML 报告
- 地区 / 来源分组
- Source Catalog
- 字段完整性审计 workflow
- Windows 本地运行
- 可选 Feishu
- 可选 AI

## 当前来源边界

默认 `supported`：

- 衡阳公共资源交易平台 / 建设工程交易
- 衡阳公共资源交易平台 / 政府采购交易

默认关闭 `alpha`：

- 长沙公共资源交易平台 / 长沙政府采购交易
- 中国政府采购网 / 地方公告

## 关键 checkpoint 摘要

- `tenderradar-ccgp-local-html-adapter-alpha-v0.1`
- `tenderradar-hengyang-procurement-field-fix-v0.1`
- 更早的重要 checkpoint 可结合仓库 tag 历史继续查阅

## 已知限制

- 衡阳建设工程最近 10 条 live 样本存在非严格倒序 / 旧公告混入风险
- 衡阳建设工程更正 / 澄清 / 暂停类字段边界仍可继续加强
- 长沙政府采购为 `alpha`，默认关闭，部分 `deadline` 缺失，`content_summary` 语义偏弱
- 中国政府采购网地方公告为 `alpha`，默认关闭，结果公告 `content_summary` 受原文限制
- 当前不下载附件，不解析 PDF / DOC / DOCX
- 当前不承诺全国稳定覆盖
- 当前不承诺普通非技术用户零门槛使用

详见 [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md)。

## 安全边界

- Feishu 默认不触发
- AI 默认不调用
- `alpha` 来源默认关闭
- `.env` / `data/bids.db` / `reports/latest.html` / `logs/*` 不应提交
- 不提供登录 / 验证码绕过
- 不提供自动投标

## Web 控制台状态

当前 Web 控制台仍是 Alpha / 本地控制台骨架：

- 可查看状态、报告入口、日志摘要、来源目录
- 当前缺真实运行按钮或完整运行闭环

因此当前主路径仍是命令行 / Windows `.bat` / 本地 HTML 报告。

## 示例材料

- 示例截图待补充
- 可参考 [assets/README.md](assets/README.md) 规划后续安全截图占位

## 下一阶段

- `v0.2-alpha`：Web 控制台真实运行入口
- `v0.3-beta`：Source Probe / 更多异构来源
