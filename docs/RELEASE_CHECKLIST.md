# GitHub 发布前检查清单

## 仓库状态

- [ ] `git status` clean
- [ ] 本轮变更仅包含预期的文档和示例说明

## 代码与测试

- [ ] `python -m compileall .` 通过
- [ ] `python -m pytest` 通过
- [ ] `python run_mvp.py --local-html` 可运行
- [ ] `python run_mvp.py --local-html --profile design_consulting` 可运行

## 敏感信息

- [ ] `.env` 未入 Git
- [ ] `.env.example` 无真实密钥
- [ ] `reports/latest.html` 未入 Git
- [ ] `data/bids.db` 未入 Git
- [ ] `logs/` 下真实日志未入 Git
- [ ] 文档中无真实 `Webhook`
- [ ] 文档中无真实 `chat_id`
- [ ] 文档中无真实 `App Secret`
- [ ] 文档中无真实 `tenant_access_token`

## 文档

- [ ] `README.md` 可读且适合开源展示
- [ ] `docs/WINDOWS_QUICKSTART.md` 可读
- [ ] `docs/LOCAL_HTML.md` 已说明本地 HTML 不需要飞书
- [ ] `docs/FEISHU_SETUP.md` 已明确飞书为可选
- [ ] `docs/PROFILES.md` 已说明 alpha/template 状态
- [ ] `docs/ARCHITECTURE.md` 已说明核心模块和数据流
- [ ] `docs/SECURITY.md` 已说明敏感信息边界
- [ ] `docs/ROADMAP.md` 未夸大为全国稳定平台

## 发布边界

- [ ] 未上传 GitHub
- [ ] 未 push
- [ ] 未提交 Git
- [ ] 未触发真实飞书接口
