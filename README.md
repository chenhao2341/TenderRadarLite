# TenderRadarLite

TenderRadarLite 是一个本地优先的招投标线索发现与字段质量审计 Alpha 工具。

它当前面向的是“本地抓取公开公告、做结构化去重、查看本地 HTML 报告、持续校准字段质量”的工程化使用场景，不是成熟 SaaS，不是全国招投标平台，也不是自动投标工具。

## 当前不是

- 不是成熟 SaaS
- 不是全国招投标平台
- 不是自动投标工具
- 不是中标预测系统
- 不绕过登录 / 验证码 / 反爬
- 不默认下载附件
- 不默认解析 PDF / DOC / DOCX
- 不默认触发 Feishu
- 不默认调用 AI

## 当前来源边界

默认 `supported` 来源：

- 衡阳公共资源交易平台 / 建设工程交易
- 衡阳公共资源交易平台 / 政府采购交易

默认关闭的 `alpha` 来源：

- 长沙公共资源交易平台 / 长沙政府采购交易
- 中国政府采购网 / 地方公告

说明：

- `supported` 代表当前已有本地 adapter，且在 `v0.1-alpha` 中可作为默认可用来源。
- `alpha` 不等于不可用，但当前不承诺稳定，默认保持关闭。
- 当前“双来源”成立于同一衡阳平台下的两个真实来源，不应包装成全国稳定跨站覆盖。

更完整的来源状态说明见 [docs/SOURCE_CATALOG.md](docs/SOURCE_CATALOG.md)。

## 当前核心能力

- 多来源 adapter 框架
- SQLite 去重与本地留存
- 本地 HTML 报告
- 地区 / 来源分组展示
- Source Catalog
- 字段完整性审计 workflow
- Windows 本地运行
- 可选 Feishu 集成
- 可选 AI 分析

## Quickstart

### 1. 安装依赖

```powershell
python -m pip install -r requirements.txt
```

### 2. 运行默认本地主路径

```powershell
python run_mvp.py --local-html --profile design_consulting
```

也可以直接运行：

```powershell
python run_mvp.py --local-html
```

### 3. 查看报告

默认输出到：

```text
reports/latest.html
```

可直接用浏览器打开，或双击 Windows 脚本打开。

更完整说明见 [docs/WINDOWS_QUICKSTART.md](docs/WINDOWS_QUICKSTART.md)。

### 4. 本地 Web 控制台 Alpha

可双击 `启动Web控制台.bat` 或运行 `python scripts/start_web_console.py` 打开 `http://127.0.0.1:8765`。当前控制台支持安全触发一次固定的本地扫描入口，默认不触发 Feishu，不调用 AI，仍然不是多用户系统或后台调度系统。

## 默认安全边界

- Feishu 默认关闭，不是主路径前置条件
- AI 默认关闭，不会随默认命令自动调用
- `alpha` 来源默认关闭
- 不提交 `.env`
- 不提交 `data/bids.db`
- 不提交 `reports/latest.html`
- 不提交 `logs/*`

更完整安全说明见 [docs/SECURITY.md](docs/SECURITY.md)。

## 已知限制摘要

- 衡阳建设工程最近 10 条 live 样本存在非严格倒序 / 旧公告混入风险
- 衡阳建设工程更正 / 澄清 / 暂停类字段边界仍可继续加强
- 长沙政府采购为 `alpha`，默认关闭，部分 `deadline` 缺失，`content_summary` 语义偏弱
- 中国政府采购网地方公告为 `alpha`，默认关闭，结果公告 `content_summary` 受原文限制
- 不下载附件，不解析 PDF / DOC / DOCX
- 不做自动投标，不承诺全国稳定覆盖
- 仍偏工程化 Alpha，不承诺普通非技术用户零门槛使用

完整列表见 [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md)。

## 文档入口

- [Windows 快速开始](docs/WINDOWS_QUICKSTART.md)
- [Source Catalog](docs/SOURCE_CATALOG.md)
- [Web 控制台边界](docs/WEB_CONSOLE.md)
- [项目架构](docs/ARCHITECTURE.md)
- [本地 HTML 报告](docs/LOCAL_HTML.md)
- [飞书可选配置](docs/FEISHU_SETUP.md)
- [Profiles 说明](docs/PROFILES.md)
- [安全说明](docs/SECURITY.md)
- [Known Limitations](docs/KNOWN_LIMITATIONS.md)
- [Release Notes v0.1-alpha](docs/RELEASE_NOTES_v0.1-alpha.md)
- [Roadmap](docs/ROADMAP.md)
- [FAQ](docs/FAQ.md)
- [Development](docs/DEVELOPMENT.md)
- [Release Checklist](docs/RELEASE_CHECKLIST.md)

## Roadmap 摘要

- `v0.1-alpha`：本地报告、双 supported 来源、默认关闭 alpha 来源、Source Catalog、字段质量审计、Windows 本地运行、安全边界说明
- `v0.2-alpha`：Web 控制台真实运行入口
- `v0.3-beta`：Source Probe / 更多异构来源 / 质量持续修复

## 开源发布边界

- 当前开源主路径是命令行 / Windows 脚本 / 本地 HTML 报告
- Web 控制台当前仍是 Alpha 骨架，不是完整运行入口
- 不承诺所有来源字段完美
- 不承诺全国稳定覆盖
- 不承诺附件深度解析
- 不承诺自动投标、SaaS 或登录 / 验证码绕过能力

## 示例材料

当前仓库未提交真实运行截图。

- 如需补展示材料，请参考 [docs/assets/README.md](docs/assets/README.md)
- 示例截图待补充

## 项目结构

```text
run_mvp.py
app/
  adapters/
  html_report.py
  main.py
  runner.py
  source_catalog.py
  storage.py
  web_console.py
config/
docs/
profiles/
reports/
scripts/
tests/
```

更详细的模块说明见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## License

仓库如需公开发布，建议由维护者确认后补充正式 License 文件。本轮不擅自新增许可证。
