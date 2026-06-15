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

- `app/ai_analysis.py` 鎻愪緵榛樿鍏抽棴鐨?AI 杈呭姪鐮旀壒鑳藉姏锛屽彧鍦?`--local-html --ai-analysis` 鏃跺惎鐢ㄣ€?
- AI 鍙宸茬粨鏋勫寲鐨?`Notice` 瀛楁锛屼笉閲嶆柊鎶撳彇銆佷笉鏀瑰彉 `lead_tier`锛屼笉鍐欏叆 SQLite锛屼笉杩涢涔︺€?
- 鏃犲瘑閽ユ垨璇锋眰澶辫触鏃讹紝鏈湴 HTML 涓绘祦绋嬩繚鎸佸彲鐢紝浠呭湪鎺у埗鍙版垨 HTML 鎻愮ず AI 宸茶烦杩囥€?

## 设计边界

- adapter 负责来源差异，不负责全局存储策略。
- profile 负责轻量行业筛选，不替代人工判断。
- HTML 是默认本地输出路径。
- 飞书是可选插件，不应作为核心运行前提。
