# Profiles 说明

## profile 是什么

profile 是 TenderRadarLite 用来做行业筛选和线索分类的一组规则配置。

它通过关键字、排除词和公告类型权重，帮助系统把公告区分为更值得关注或更应排除的结果。

## 默认 profile

默认 profile 是：

```text
design_consulting
```

如果不显式传 `--profile`，系统会使用这个默认值。

## 当前内置 profiles

- `design_consulting`
- `software_it`
- `construction`
- `medical_equipment`

其中：

- `design_consulting` 适合规划、设计、可研、勘察、咨询等线索筛选，是当前最完整、最适合直接使用的 profile。
- `software_it`、`construction`、`medical_equipment` 目前是 alpha/template，更适合作为行业模板继续定制。

## 如何使用

```powershell
python run_mvp.py --local-html --profile design_consulting
```

也可以替换为其他 profile id：

```powershell
python run_mvp.py --local-html --profile software_it
```

## 每个字段的含义

### `profile_id`

profile 的唯一标识，通常与 JSON 文件名一致。

### `name`

用于展示的 profile 名称。

### `description`

说明这个 profile 的适用行业、成熟度和用途。

### `positive_keywords`

正向关键词。命中后会提升公告与目标行业相关的概率。

### `strong_positive_keywords`

强正向关键词。比普通正向词信号更强，通常代表更明确的行业相关性。

### `negative_keywords`

负向关键词。命中后会降低优先级，但不一定直接排除。

### `exclude_keywords`

排除关键词。用于明确屏蔽不希望纳入当前行业视角的公告。

### `notice_type_weights`

不同公告类型的权重配置，用于辅助判断优先级。

### `budget_keywords`

预算、限价、金额相关关键词，用于辅助提取和观察金额类信息。

### `qualification_keywords`

资质相关关键词，用于辅助识别资质要求类内容。

## 如何新增自己的 profile

1. 复制一个现有 JSON 文件作为模板。
2. 修改 `profile_id`、`name`、`description`。
3. 根据目标行业补充 `positive_keywords`、`strong_positive_keywords`、`negative_keywords`、`exclude_keywords`。
4. 调整 `notice_type_weights`。
5. 使用本地 HTML 反复验证效果。

建议先从 `design_consulting.json` 或某个 alpha/template 文件开始改，不要直接修改业务代码。

## 使用建议

- 如果你是第一次接触这个项目，优先从 `design_consulting` 开始。
- 如果你的行业不同，可把 alpha/template 文件作为起点继续细化。
- profile 规则是轻量筛选，不替代人工判断。
