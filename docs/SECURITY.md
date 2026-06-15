# 安全说明

## 不应提交到 Git 的内容

- `.env`
- `data/bids.db`
- `reports/latest.html`
- `logs/*`
- 本地备份目录
- 任何包含真实密钥、真实 Webhook、真实 `chat_id`、真实 `tenant_access_token` 的文件

## `.env` 处理原则

- `.env` 只用于本地
- `.env.example` 只保留占位符
- 不要在 README、docs、测试示例里写入真实值

## 数据库和日志

- `data/bids.db` 是本地运行数据库，不应随仓库公开
- `logs/` 是本地运行日志目录，不应提交真实日志内容
- `reports/latest.html` 是本地生成产物，不应作为源码一部分提交

## 飞书相关安全注意事项

不要公开以下内容：

- `FEISHU_APP_SECRET`
- `FEISHU_WEBHOOK_URL`
- `FEISHU_CHAT_ID`
- `tenant_access_token`

同时也不要把这些值放进：

- 文档截图
- issue 内容
- 测试数据
- 示例配置

## GitHub 发布前安全检查

建议至少执行以下检查：

1. 确认 `git status` 干净或仅包含预期文档改动。
2. 确认 `.env` 未被 Git 跟踪。
3. 确认 `data/bids.db` 未被 Git 跟踪。
4. 确认 `reports/latest.html` 未被 Git 跟踪。
5. 确认 `logs/` 下无真实日志被 Git 跟踪。
6. 确认 `.env.example` 只有占位符。
7. 确认 README 和 docs 中未出现真实密钥。
8. 如仓库曾使用过真实密钥，额外检查 Git 历史是否带入敏感信息。

## 发布原则

开源发布前，优先保证：

- 源码可读
- 本地路径可运行
- 功能边界说明清楚
- 敏感信息不随仓库暴露
