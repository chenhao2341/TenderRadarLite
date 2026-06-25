# 安全说明

## 开源默认安全边界

- Feishu 默认关闭
- AI 默认关闭
- `alpha` 来源默认关闭
- 当前主路径是本地 HTML，不依赖真实外部集成
- 当前仅面向公开可访问来源，不绕过登录 / 验证码 / 强反爬

## 不应提交到 Git 的内容

- `.env`
- `data/bids.db`
- `reports/latest.html`
- `logs/*`
- 本地备份目录
- 任意包含真实 Key / Secret / Webhook / Token / Password 的文件

## `.env` 处理原则

- `.env` 只用于本地
- `.env.example` 只保留占位符
- 文档、示例、截图、日志中不得出现真实值

## 运行产物边界

- `data/bids.db` 是本地 SQLite 数据库，不应公开
- `reports/latest.html` 是本地生成产物，不应作为源码提交
- `logs/` 是本地运行日志目录，不应提交真实日志

## Feishu 与 AI 的安全定位

Feishu 相关真实值不应公开：

- `FEISHU_APP_SECRET`
- `FEISHU_WEBHOOK_URL`
- `FEISHU_CHAT_ID`
- `FEISHU_BITABLE_APP_TOKEN`
- `FEISHU_BITABLE_TABLE_ID`

AI 相关真实值不应公开：

- `OPENAI_API_KEY`
- `ARK_API_KEY`
- `DEEPSEEK_API_KEY`
- `GEMINI_API_KEY`
- 任何其他 `API_KEY`

说明：

- 文档中出现这些字段名是为了说明边界
- 可以出现占位字段名
- 不可以出现真实值

## Git 发布前最小审计

建议至少检查：

1. `git status --short` 仅包含预期文档改动
2. `.env` 未被跟踪
3. `data/bids.db` 未被跟踪
4. `reports/latest.html` 未被跟踪
5. `logs/` 下无真实日志被跟踪
6. `.env.example` 只有占位符
7. README 和 docs 中无真实密钥
8. `git ls-files` 中无本地数据库、报告、日志

## 不承诺的高风险能力

当前项目不承诺：

- 登录 / 验证码绕过
- 高强度反爬对抗
- 自动投标
- 附件深度解析
- 全国稳定覆盖

## 公开来源与合规使用

- 本项目当前仅面向公开来源页面
- 用户需自行确认目标网站条款、robots、访问频率和当地法律法规
- 不鼓励绕过访问限制、身份验证或站点防护机制
- 数据内容及页面版权归原始发布网站或权利人所有

## 发布原则

开源发布前优先保证：

- 边界说明清楚
- 敏感信息不泄露
- 本地主路径可运行
- `alpha` 与 `supported` 不混淆
