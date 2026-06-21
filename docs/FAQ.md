# FAQ

## 这是不是成熟产品？

不是。当前是本地优先的 `v0.1-alpha`，更接近工程化 Alpha 工具，而不是成熟 SaaS 产品。

## 是否会自动投标？

不会。当前不提供自动投标能力。

## 是否默认调用 AI？

不会。AI 是可选 Alpha，默认不调用。

## 是否默认发送 Feishu？

不会。Feishu 是可选集成，默认主路径不触发。

## 为什么有些来源默认关闭？

因为这些来源当前是 `alpha`，已有 adapter，但稳定性或字段质量仍在继续校准，所以默认关闭。

## 为什么有些字段显示未提取到？

因为不同来源页面结构和公告类型差异较大，当前 Alpha 阶段仍存在字段完整性风险，详见 [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md)。

## 是否支持全国所有来源？

不支持。当前不承诺全国稳定覆盖。

## 是否支持 PDF / DOC 解析？

当前默认不解析 PDF / DOC / DOCX。

## 是否适合普通非技术用户？

当前不承诺普通非技术用户零门槛使用。更适合能接受本地命令行或 Windows 脚本路径的用户。

## 如何查看本地报告？

运行 `python run_mvp.py --local-html --profile design_consulting` 后，打开 `reports/latest.html` 即可。也可以双击 `scripts/打开最新报告.bat`。
