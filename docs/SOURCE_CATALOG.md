# TenderRadarLite Source Catalog

## 1. 它是什么

`Source Catalog` 是 TenderRadarLite 的“来源目录层”。

它用于记录：

- 当前支持哪些来源
- 哪些来源已有 adapter
- 哪些来源只是 candidate
- 哪些来源计划后续研究
- 哪些来源因风险暂不建议接入
- 每个来源的地区、来源类型、公告类型、附件可能性、访问风险、数据质量、备注和来源依据

当前配置文件：

- `config/source_catalog.yaml`

当前只读工具模块：

- `app/source_catalog.py`

## 2. 它不是什么

Source Catalog 不是抓取器。

它不会：

- 自动接入新站点
- 自动生成 adapter
- 自动抓取 candidate / planned 来源
- 自动触发 Feishu
- 自动调用 AI
- 自动执行全国全站爬取

## 3. status 含义

- `supported`
  - 当前已有本地 adapter，且当前 Alpha 视为已支持来源。
- `alpha`
  - 当前已有本地 adapter，但仍处于 Alpha 状态，或尚未默认启用。
- `candidate`
  - 只进入来源目录，未本地验证，未接入 adapter，不代表已经支持抓取。
- `planned`
  - 计划后续研究的来源，入口、字段或接入方式仍待人工确认。
- `blocked`
  - 因敏感范围、稳定性、登录要求、反爬或业务边界风险，当前不建议接入。

## 4. candidate / planned 与 supported 的区别

`supported / alpha` 才与当前本地 adapter 有关。

`candidate / planned / blocked` 只是知识库记录：

- 不是当前运行来源
- 不是当前默认抓取来源
- 不是“已经支持”
- 不是“下一步自动接入”

## 5. 第三方 GitHub 项目如何使用

第三方 GitHub 项目在本轮只作为来源参考：

- 用来补充来源入口清单
- 用来观察字段设计
- 用来记录常见风险模式

不会：

- 复制第三方代码
- 直接照抄第三方来源网页清单
- 在 LICENSE 不清晰时复用实现

## 6. LICENSE 不清时如何处理

如果参考项目 LICENSE 不清，处理原则是：

- 只记录来源线索
- 不复制代码
- 不复制整套来源列表
- 不把它当作可直接复用的 adapter 资产

## 7. candidate 升级为 alpha 的条件

至少满足：

- 本地人工确认来源入口
- 本地确认目标页面可访问
- 明确字段结构和公告类型
- 明确不涉及当前禁止范围
- 已新增并验证本地 adapter

## 8. alpha 升级为 supported 的条件

至少满足：

- adapter 已存在且可运行
- 本地验证通过
- 状态和边界说明清楚
- 不依赖登录、验证码绕过或高风险抓取
- 在当前 Alpha 范围内被确认可作为默认支持来源

## 9. 什么情况下应标为 blocked

典型情况包括：

- 敏感范围，不适合当前 Alpha
- 需要登录或高强度反爬绕过
- 稳定性或延迟风险过高
- 业务边界不适合本地优先公开模式
- 付费站点或企业门户集合，合规和维护成本过高

## 10. 如何在 Web 控制台查看

启动本地控制台后访问：

- `http://127.0.0.1:8765/sources`

左侧菜单会显示：

- `来源目录`

页面会明确说明：

- `candidate / planned` 不代表已经支持抓取
- `supported / alpha` 才与当前 adapter 有关
- 本页只是来源知识库，不会触发抓取
