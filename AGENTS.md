# TenderRadarLite Agent Notes

## 1. 项目定位

- 轻量招投标线索监控工具
- 优先复用公开接口、HTML、JSON
- 不默认引入浏览器自动化
- 不做重型后台

## 2. 当前真实入口

- 正式入口：`python run_mvp.py`
- 本地 dry-run：`python run_mvp.py --local-only`
- 本地结构化预览：`python run_mvp.py --local-structured-preview`
- 白名单验收入口：
  - `python run_mvp.py --pilot-notice-ids-file <配置文件> --dry-run`
  - `python run_mvp.py --pilot-notice-ids-file <配置文件> --execute`

## 3. 工程规则

- 代码修改完成 != 产品真实可用
- 离线测试通过 != 用户入口可用
- Agent 报告完成 != 真实验收通过
- 修改前先确认唯一调用链
- 优先最小修改
- 禁止无必要重构
- 禁止新增平行 runner
- 禁止新增第二套数据库
- 失败时停止继续打补丁
- 真实突破后再 Git commit

## 4. 数据安全

- `.env` 不进入 Git
- 数据库不进入 Git
- 日志不进入 Git
- backup 不进入 Git
- Secret、Webhook、Token 不打印
- 开源前必须做脱敏审计

## 5. 当前边界

- 当前只验证了一个主要公开来源
- P0-2 默认 disabled
- 当前不代表全国覆盖
- AI API 尚未接入
- HTML 页面尚未开发
- Windows 计划任务不自动创建、不自动启用
