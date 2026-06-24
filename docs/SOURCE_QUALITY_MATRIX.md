# Source Quality Matrix Alpha

## 定位

`Source Quality Matrix` 是 `Source Catalog` 的轻量补充层。

它解决的不是“有没有这个来源”，而是：

- 这个来源当前处于什么接入状态
- 为什么它是 `supported` / `alpha` / `candidate` / `blocked`
- 默认是否应该启用
- 最近一次运行看到了什么
- 新鲜度、去重、字段完整性目前能观测到多少
- 对后续 `Source Probe` 是否有复用价值

它不做以下事情：

- 不新增来源
- 不自动把 `alpha` 升级为 `supported`
- 不自动把 `candidate` 变成可运行来源
- 不替代现有公告列表
- 不改变默认运行逻辑

## 当前字段

每个来源至少包含以下质量字段：

- `source_key`
- `display_name`
- `status`
- `default_enabled`
- `source_type_hint`
- `access_mode`
- `detail_mode`
- `original_url_policy`
- `raw_api_policy`
- `freshness_observability`
- `dedupe_observability`
- `field_completeness_observability`
- `known_risks`
- `probe_reuse_value`
- `recommended_usage`

报告渲染阶段还会拼接最近一次运行的轻量观测：

- `participated_in_latest_run`
- `fetched`
- `inserted`
- `duplicates`
- `errors`
- `latest_db_publish_time`
- `latest_site_publish_time`
- `detail_observation`
- `dedupe_signal`

## source_type_hint 建议值

- `json_api`
- `html_list_detail`
- `json_portal_flow`
- `spa_runtime_required`
- `blocked_captcha`
- `anti_bot`
- `candidate_unknown`
- `planned`
- `unknown`

## recommended_usage 建议值

- `default_supported`
- `manual_alpha_test`
- `probe_reference`
- `research_only`
- `blocked`
- `planned`

## 当前 Alpha 解释边界

- `supported` 仍表示当前默认主路径可用来源
- `alpha` 仍表示已接入但默认关闭、需要保守验证的来源
- `candidate` / `planned` / `blocked` 仍不是当前可采集承诺
- `unknown` 只应用于未登记来源或矩阵无法识别的条目

## 可观测性解释

### latest_site_publish_time

如果 adapter 本轮没有提供 `latest_site_publish_time`，报告应直接说明：

- `当前 adapter 未提供 latest_site_publish_time`

这不是运行错误，而是后续可观测性增强项。

### dedupe_signal

当前报告只做轻量解释，不做重判定：

- `stable`
- `suspected_realtime_update`
- `dedupe_anomaly`
- `unknown`

其中：

- `suspected_realtime_update` 表示有少量新增，不直接判定为去重异常
- `dedupe_anomaly` 表示需要后续复核
- `unknown` 表示现有运行摘要不足以判断
