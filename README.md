# TenderRadarLite

TenderRadarLite 是一个本地优先、可扩展的招投标线索监控工具，支持本地 HTML 报告、行业 profiles、Windows 双击运行和可选飞书同步。

## 项目定位

这个仓库当前更适合以下场景：

- 在本地定时或手动抓取公开招投标公告
- 生成结构化结果并做 SQLite 去重沉淀
- 用行业 profile 做轻量分类筛选
- 直接查看本地 HTML 报告
- 在需要时接入飞书多维表格或 App Bot

当前阶段是本地优先的开源工具，不是全国全行业成熟平台，也不是重后台 SaaS。

## 当前能力

- 本地抓取公开公告
- 结构化公告字段提取
- SQLite 去重与本地留存
- 行业 profiles 分类框架
- 本地 HTML 报告输出
- Windows 双击运行入口
- 可选飞书多维表格 / App Bot 同步
- 适配器框架与来源注册机制
- 自动化测试覆盖

## 快速开始

### 命令行

```powershell
python -m pip install -r requirements.txt
python run_mvp.py --local-html
python run_mvp.py --local-html --profile design_consulting
```

### Windows 双击运行

1. 双击 `scripts/检查运行环境.bat`
2. 双击 `scripts/启动本地招投标报告.bat`

## 关键说明

- 本地 HTML 模式不需要飞书。
- 飞书属于高级可选插件，不是本地报告的前置依赖。
- `design_consulting` 是当前最完整的 profile。
- `software_it`、`construction`、`medical_equipment` 目前处于 alpha/template 状态，需要按真实场景继续校准。
- 当前仓库重点是本地抓取、结构化和筛选能力，不承诺全国范围、多行业、生产级全覆盖。

## 常用运行方式

```powershell
python run_mvp.py --local-only
python run_mvp.py --local-html
python run_mvp.py --local-html --profile design_consulting
```

生成成功后，本地 HTML 报告默认输出到 `reports/latest.html`。

## 文档入口

- [Windows 快速开始](docs/WINDOWS_QUICKSTART.md)
- [本地 HTML 报告说明](docs/LOCAL_HTML.md)
- [Profiles 说明](docs/PROFILES.md)
- [飞书可选配置](docs/FEISHU_SETUP.md)
- [项目架构](docs/ARCHITECTURE.md)
- [安全说明](docs/SECURITY.md)
- [路线图](docs/ROADMAP.md)
- [发布前检查清单](docs/RELEASE_CHECKLIST.md)

## 安全说明

开源前请明确不要提交以下内容：

- `.env`
- `data/bids.db`
- `reports/latest.html`
- `logs/*`
- 飞书 `App Secret`
- 飞书 `Webhook`
- 飞书 `chat_id`
- 飞书 `tenant_access_token`

`.env.example` 只能保留占位符，不能放真实密钥。

## 项目结构

```text
run_mvp.py
app/
  main.py
  runner.py
  adapters/
  storage.py
  html_report.py
  feishu.py
profiles/
config/
docs/
scripts/
tests/
```

更详细的模块说明见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 开源边界

- 不内置真实密钥
- 不包含本地运行产生的数据库、日志和报告产物
- 不承诺所有来源长期稳定
- 不将飞书作为默认必选依赖
- 当前不包含 EXE、安装包和全国化平台能力

## License

仓库当前如需公开发布，建议在维护者确认后再补充正式 License。常见候选可考虑 `MIT` 或 `Apache-2.0`，但本轮不擅自新增许可证文件。
