# 飞书可选配置

## 先说结论

飞书是可选高级功能，不是 TenderRadarLite 本地使用的前置依赖。

如果你只想生成本地报告，直接运行：

```powershell
python run_mvp.py --local-html
```

这条路径不需要飞书。

## 什么时候才需要飞书

当你需要以下能力时，才需要自己配置 `.env`：

- 飞书多维表格写入
- 飞书 Webhook 群消息
- 飞书 App Bot 群消息

## 配置原则

- 真实配置只放在本地 `.env`
- 仓库中的 `.env.example` 只能保留占位符
- 不要提交真实 `Webhook`
- 不要提交真实 `chat_id`
- 不要提交真实 `App Secret`
- 不要提交真实 `tenant_access_token`

## 建议流程

1. 复制示例文件：

```powershell
Copy-Item .env.example .env
```

2. 只在本地填入你自己的飞书配置。
3. 提交或公开仓库前再次确认 `.env` 未入 Git。

## `.env.example` 应该是什么样

应该只有字段名和占位说明，不能放任何真实值。

## 本项目对飞书的定位

- 飞书是可选输出插件
- 本地 HTML 是默认、最轻量的使用方式
- 开源发布时应优先保证无飞书配置也能完成本地验证

## 开源发布前检查

- `.env` 未入 Git
- `.env.example` 无真实密钥
- README 明确写清“飞书可选”
- 不在文档、示例、截图、日志里暴露真实飞书配置
