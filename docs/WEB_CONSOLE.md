# TenderRadarLite Web 控制台

## 1. 这是什么

TenderRadarLite Web 控制台是本地优先的轻量浏览器入口。

它当前只提供：

- Dashboard 项目状态总览
- Run 推荐命令与安全默认项
- Report 本地 HTML 报告入口
- Logs 最近日志摘要
- Config 配置状态遮罩展示
- Sources 来源目录只读展示

它不是 SaaS，不是登录后台，不是投标文件生成工作台。

## 2. 如何启动

推荐两种方式：

```bash
python scripts/start_web_console.py
```

或直接双击仓库根目录中的：

`启动Web控制台.bat`

默认地址：

`http://127.0.0.1:8765`

## 3. 默认不会触发 Feishu

当前 Alpha 页面不提供真实运行按钮。

- 不会从页面触发 Feishu 同步
- 不会自动发送 webhook
- 不会自动写入飞书多维表
- 不会从 Sources 页面触发抓取

## 4. 默认不会调用 AI

当前 Alpha 页面只展示 AI 配置状态和安全推荐命令。

- 默认推荐命令只包含 `--local-html`
- 默认不包含 `--ai-analysis`
- 页面不会主动触发模型调用
- Sources 页面不会调用 AI 生成新来源

## 5. 如何打开 latest.html

有两种入口：

- Dashboard 页面中的报告状态卡片
- Report 页面中的“打开报告”按钮

如果 `reports/latest.html` 不存在，页面会提示先运行：

```bash
python run_mvp.py --local-html --profile design_consulting
```

## 6. 如何查看配置状态

打开 `Config` 页面可看到：

- `.env` 是否存在
- `.env.example` 是否存在
- Feishu 必填字段是否已配置
- AI provider / model / key 是否已配置
- `profiles/`、`reports/`、`logs/` 是否存在
- `company_sample.yaml` 是否存在

控制台只显示：

- 存在 / 不存在
- 已配置 / 缺失
- sample-found / unselected

不会显示 Key、Secret、Webhook 原文。

## 7. 如何查看日志

打开 `Logs` 页面可看到：

- 最近日志文件列表
- 最新日志文件的末尾摘要

日志页只读取 `logs/*.log`，不会读取 `.env`。

## 8. 如何查看来源目录

打开 `Sources` 页面可看到：

- 来源总数
- supported / alpha / candidate / planned / blocked 统计
- 来源名称、地区、来源类型、状态、adapter、访问风险、附件可能性、备注

页面会明确提示：

- `candidate / planned` 不代表已经支持抓取
- `supported / alpha` 才与当前 adapter 有关
- 本页只是来源知识库，不会触发抓取

它不提供：

- 新增/编辑/删除来源
- 一键接入
- 立即抓取
- Feishu 操作
- AI 操作

## 9. 当前 Alpha 边界

当前只做本地 Web 控制台骨架和只读来源目录，不包含：

- 用户自定义来源
- 附件下载
- PDF / DOC / DOCX 解析
- AI 招标文件研判
- 投标文件生成
- Word 导出
- 自动生成 adapter
- 全国全站爬虫
- 多用户 / 权限 / 后台

## 10. 后续规划

后续阶段可以继续接入：

- 更丰富的 Source Catalog 元信息
- 附件下载
- AI 招标文件研判

但这些能力不在当前 Alpha 范围内。

## 11. 常见问题

### 页面里为什么没有“一键运行”？

因为当前版本优先保证安全边界，不误触发 Feishu、AI 或额外抓取流程，所以先只提供推荐命令。

### 为什么配置页没有显示 Key？

这是刻意设计。控制台只显示配置状态，不显示任何真实 Secret。

### latest.html 不存在怎么办？

先在仓库根目录运行：

```bash
python run_mvp.py --local-html --profile design_consulting
```

然后刷新 `Report` 页面。

### 控制台会改数据库 schema 吗？

当前不会。它只读取现有文件、目录、日志、报告状态和来源目录配置。
