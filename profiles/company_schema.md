# Company Profile Schema Alpha

`profiles/company_sample.yaml` 用于企业级画像配置，先作为 P0-1 的本地加载与默认值基线。

## 顶层字段

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `company_name` | `string` | `""` | 企业名称 |
| `regions` | `list[string]` | `[]` | 地区偏好 |
| `business_scope` | `list[string]` | `[]` | 业务范围 |
| `target_project_types` | `list[string]` | `[]` | 重点关注项目类型 |
| `exclude_project_types` | `list[string]` | `[]` | 明确排除项目类型 |
| `qualifications` | `list[string]` | `[]` | 资质能力 |
| `budget_preference` | `mapping` | 见下文 | 金额偏好 |
| `notice_type_preference` | `mapping` | 见下文 | 公告类型偏好 |

## budget_preference

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `min_amount` | `int \| null` | `null` | 最低预算偏好，不应在单位不明时硬过滤 |
| `preferred_unit` | `string` | `"元"` | 展示与比较时的偏好单位 |
| `note` | `string` | `"金额单位不明确时不直接过滤"` | 给后续评分/展示逻辑的提示 |

## notice_type_preference

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `high` | `list[string]` | `[]` | 高优先级公告类型 |
| `medium` | `list[string]` | `[]` | 中优先级公告类型 |
| `low` | `list[string]` | `[]` | 低优先级公告类型 |

## 兼容边界

- 当前 `app/profiles.py` 的行业 profile JSON 体系保持不变。
- `company profile` 仅负责企业画像加载，不直接改写现有 `lead_tier`、HTML 报告或 Feishu 逻辑。
- 后续 P0-2 / P0-3 可以在此基础上继续接入 `opportunity_stage` 和企业匹配评分。
