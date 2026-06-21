# Release Checklist

## 仓库状态

- [ ] `git status --short` clean，或仅包含本轮允许的文档改动
- [ ] 当前改动只在 `README.md`、`docs/`、`docs/assets/`
- [ ] 未修改 `app/adapters/`
- [ ] 未修改 `app/main.py`
- [ ] 未修改 `app/html_report.py`
- [ ] 未修改 `run_mvp.py`
- [ ] 未修改 `config/sources.json`
- [ ] 未修改 `config/source_catalog.yaml`
- [ ] 未修改 `tests/`

## 文档收口

- [ ] `README.md` 已明确项目定位和开源边界
- [ ] `docs/WINDOWS_QUICKSTART.md` 已明确命令行 / bat / 本地 HTML 主路径
- [ ] `docs/SOURCE_CATALOG.md` 已明确 `supported / alpha / candidate / planned / blocked`
- [ ] `docs/WEB_CONSOLE.md` 已明确当前只是 Alpha 骨架
- [ ] `docs/KNOWN_LIMITATIONS.md` 已存在且可读
- [ ] `docs/RELEASE_NOTES_v0.1-alpha.md` 已存在
- [ ] `docs/ROADMAP.md` 已对齐当前阶段

## 敏感信息

- [ ] `.env` 未入 Git
- [ ] `.env.example` 无真实密钥
- [ ] `data/bids.db` 未入 Git
- [ ] `reports/latest.html` 未入 Git
- [ ] `logs/` 下真实日志未入 Git
- [ ] 文档中无真实 `Webhook`
- [ ] 文档中无真实 `Token`
- [ ] 文档中无真实 `Secret`
- [ ] 文档中无真实 `Password`

## 发布边界

- [ ] 未把 `alpha` 来源包装成 `supported`
- [ ] 未承诺全国稳定覆盖
- [ ] 未承诺自动投标
- [ ] 未承诺成熟 SaaS
- [ ] 未承诺登录 / 验证码绕过
- [ ] 未承诺附件深度解析
- [ ] README 已明确默认不触发 Feishu
- [ ] README 已明确默认不调用 AI

## 验证

- [ ] `python -m pytest` 通过
- [ ] 当前通过数量不低于 200
- [ ] 文档修改后未引入额外依赖
- [ ] 未提交真实截图或敏感样例
