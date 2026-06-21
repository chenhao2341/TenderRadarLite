# Development

## 项目结构

```text
app/
  adapters/
  html_report.py
  runner.py
  source_catalog.py
  storage.py
config/
docs/
profiles/
scripts/
tests/
run_mvp.py
```

## adapter 开发基本流程

1. 明确来源入口、公告类型和访问边界。
2. 在 `app/adapters/` 中实现新 adapter。
3. 在 registry 和配置中接入。
4. 为列表、详情、字段映射和异常情况补测试。
5. 在文档与 Source Catalog 中明确 `status` 和默认启停策略。

## 测试命令

```powershell
python -m pytest
```

## 不提交本地文件规则

不要提交：

- `.env`
- `data/bids.db`
- `reports/latest.html`
- `logs/*`
- 本地备份目录

## 新来源 workflow 入口

新来源接入前，先完成：

1. 入口可访问性确认
2. 原文链接可读性确认
3. 字段结构映射
4. 最小样本验证
5. Source Catalog 状态定义

当前主真相文件：

- `config/sources.json`
- `config/source_catalog.yaml`

## 字段完整性 workflow 入口

字段质量问题应优先进入：

- 测试用例
- `docs/KNOWN_LIMITATIONS.md`
- `config/source_catalog.yaml` 的 `notes`
- 运行时风险说明

不要把字段风险直接混同为来源 `status`。

## checkpoint 前检查

1. `git status --short`
2. `python -m pytest`
3. 核对变更范围是否符合本轮边界
4. 核对未误提交 `.env` / DB / report / logs
5. 核对 README / Quickstart / Source Catalog / Security 是否一致
