# TenderRadarLite

## 项目简介

TenderRadarLite 是一个面向国内公开招投标网站的轻量线索监控工具。

当前版本聚焦：

- 公开接口或公开 HTML 抓取
- 公告列表扫描
- 详情解析
- 公告级 notice 去重
- 本地 SQLite 落库
- 规则分类
- 可选飞书多维表格写入
- 可选飞书群 Bot 提醒
- Windows 本地运行与日志留存

当前阶段是可开源准备版，不代表全国覆盖，也不包含重型后台。

## 当前能力

- 公开接口抓取
- 前 3 页扫描
- 详情解析
- 公告级 notice 去重
- SQLite
- DIRECT / WATCHLIST / EXCLUDE 规则分类
- 可选飞书多维表格
- 可选群 Bot
- Windows bat
- 日志
- 白名单 dry-run 与受控验收
- 错误退出码
- 国内站点默认直连，不依赖系统代理

## 当前支持来源

- 衡阳分平台建设工程交易：已验证
- 衡阳分平台政府采购交易：保留 adapter，但默认 `disabled`，当前不可靠

当前只是第一个已验证来源示例，不代表全国覆盖。

## Windows 快速开始

1. 安装 Python 3.11 或更高版本。
2. 在项目根目录创建虚拟环境：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

3. 安装依赖：

```powershell
python -m pip install -r requirements.txt
```

4. 复制配置模板：

```powershell
Copy-Item .env.example .env
```

5. 如需飞书输出，再按需填写 `.env` 中的飞书配置；不使用飞书可留空。
6. 准备白名单示例文件（可选）：

```powershell
Copy-Item examples\pilot_notice_ids.example.json examples\pilot_notice_ids.local.json
```

7. 本地 dry-run：

```powershell
python run_mvp.py --local-only
```

8. 正式入口：

```powershell
python run_mvp.py
```

9. 白名单验收：

```powershell
python run_mvp.py --pilot-notice-ids-file examples\pilot_notice_ids.local.json --dry-run
python run_mvp.py --pilot-notice-ids-file examples\pilot_notice_ids.local.json --execute
```

10. Windows bat：

```powershell
scripts\run_tender_radar.bat
```

11. 查看日志：

- 运行日志位于 `logs\`
- 本地数据库位于 `data\bids.db`

## 配置说明

- `config\sources.json`
  - 管理来源列表、模块路径、启用状态、分页参数
- `.env`
  - 飞书输出相关配置
  - 未配置飞书时，本地抓取、SQLite、日志仍可运行
- `examples\pilot_notice_ids.example.json`
  - 白名单受控验收示例，需要自行复制后填写
- AI API 当前尚未启用

## 安全说明

- 不要提交 `.env`
- 不要提交数据库
- 不要提交日志
- 不要提交真实 Secret、Token、Webhook
- 不要公开本地路径
- 公开前必须做一次脱敏审计

## 已知边界

- 公开网站可能改版
- adapter 需要持续维护
- 规则分类不能替代人工判断
- 附件暂不下载解析
- AI API 尚未接入
- 当前不做复杂后台

## Roadmap

- 更多国内常用来源
- Windows 初始化脚本
- optional AI analysis adapter
- 轻量本地 HTML 看板
- 钉钉或其他输出适配器
- 更完整的来源健康检查
