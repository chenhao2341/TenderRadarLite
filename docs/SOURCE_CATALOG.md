# TenderRadarLite Source Catalog

## 1. 它是什么

`Source Catalog` 是 TenderRadarLite 的来源目录层，用来描述：

- 当前有哪些来源
- 每个来源的 `status`
- 哪些来源已有本地 adapter
- 哪些来源默认启用
- 哪些来源只是候选、规划或阻塞记录

运行启停真相在：

- `config/sources.json`

来源状态真相在：

- `config/source_catalog.yaml`

## 2. 它不是什么

Source Catalog 不是抓取器，不会：

- 自动新增来源
- 自动生成 adapter
- 自动触发抓取
- 自动触发 Feishu
- 自动调用 AI
- 自动把 `candidate` 或 `planned` 变成可运行来源

## 3. status 定义

### `supported`

- 当前已有本地 adapter
- 当前可作为默认可用来源
- 可用于 `v0.1-alpha` 的主展示路径

### `alpha`

- 当前已有本地 adapter
- 已具备一定可用性，但不承诺稳定
- 通常默认关闭
- `alpha` 不等于不可用，只是不应包装成 `supported`

### `candidate`

- 已进入来源目录
- 尚未完成本地验证
- 未接入当前运行主路径

### `planned`

- 仅表示后续计划研究
- 当前不代表已支持抓取

### `blocked`

- 表示当前不适合走现有本地 requests 路线
- 可能原因包括登录要求、反爬风险、稳定性问题、敏感边界或维护成本
- `blocked` 不等于永久不可做，只是当前不进入本地 Alpha 主线

## 4. 当前 v0.1-alpha 关键来源

当前 `supported`：

- 衡阳公共资源交易平台 / 建设工程交易
- 衡阳公共资源交易平台 / 政府采购交易

当前 `alpha`：

- 长沙公共资源交易平台 / 长沙政府采购交易，默认关闭
- 中国政府采购网 / 地方公告，默认关闭

说明：

- 衡阳建设工程为 `supported`
- 衡阳政府采购为 `supported`
- 长沙政府采购为 `alpha`
- 中国政府采购网地方公告为 `alpha`

## 5. status 与字段风险的关系

`source_status` 反映的是来源接入与运行边界，不应被单个字段风险直接污染。

也就是说：

- 某来源有字段缺失，不等于必须降成 `blocked`
- 某来源有摘要偏弱，不等于必须移出 `alpha`
- 某来源的字段边界风险，应该写入 `known limitations` 或 `detail_risk_note`

当前字段风险的正式归档位置应优先使用：

- [docs/KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md)
- `config/source_catalog.yaml` 中的 `notes`
- 运行时 `detail_risk_note`

## 6. 如何从 candidate 升级为 alpha

至少应满足：

1. 本地确认入口可访问
2. 明确公告类型和字段结构
3. 完成本地 adapter
4. 跑通最小抓取链路
5. 明确安全边界与默认启停策略

## 7. 如何从 alpha 升级为 supported

至少应满足：

1. adapter 已存在且可运行
2. 真实本地验证通过
3. 默认启停策略明确
4. 文档边界清楚
5. 已知字段风险可接受，不会误导成“稳定全国覆盖”

## 8. blocked 的理解

`blocked` 表示“当前不适合走本地 requests 路线”，常见原因包括：

- 登录 / 验证码要求
- 高强度反爬
- 访问稳定性过差
- 敏感范围
- 维护成本不适合当前 Alpha

它不等于永久放弃，只是当前版本不把它纳入主线。

## 9. 与运行主路径的关系

当前开源主路径仍是：

1. 命令行运行
2. Windows `.bat` 运行
3. 本地 HTML 报告查看

Source Catalog 的作用是帮助解释“当前为什么只默认开两个来源、为什么另两个来源默认关闭”，不是把所有目录项都变成可运行承诺。

## 10. Web 控制台中的 Source Catalog

本地控制台 `/sources` 页面当前只做只读展示：

- 展示来源总数和状态统计
- 展示 `supported / alpha / candidate / planned / blocked`
- 展示地区、类型、风险和备注

它不会：

- 一键抓取
- 一键接入新来源
- 修改 `config/sources.json`
- 修改 `config/source_catalog.yaml`

## 11. 当前对外表述边界

当前可以准确表述为：

- TenderRadarLite 已有 2 个默认可用 `supported` 来源
- 另有 2 个默认关闭的 `alpha` 来源
- 当前已覆盖 JSON API 与 static HTML 两类来源样式
- 当前已具备 Source Catalog、SQLite 去重和本地 HTML 报告主链路

当前不应表述为：

- 全国稳定多来源平台
- 所有来源都已支持
- 所有 `alpha` 来源都接近 `supported`
- 跨站大规模稳定采集已经完成
