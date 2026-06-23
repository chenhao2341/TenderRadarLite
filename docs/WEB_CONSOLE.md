# TenderRadarLite Web 控制台

## 当前定位

当前 Web 控制台仍是本地单用户 Alpha，不是多用户平台，不是后台调度系统，也不是 SaaS。

它现在有两个层次的能力：

- 只读查看：仪表盘、报告入口、日志、配置状态、来源目录
- 单次运行：在页面中安全触发一次固定的本地扫描

## 启动方式

```powershell
python scripts/start_web_console.py
```

或双击：

```text
启动Web控制台.bat
```

默认地址：

```text
http://127.0.0.1:8765
```

## 当前真实运行入口

`/run` 页面新增了一个真实按钮：

- `运行一次本地扫描`

按钮固定调用以下主链路：

```powershell
python run_mvp.py --local-html --profile design_consulting
```

服务端实际执行时使用当前 Python：

```python
[sys.executable, "run_mvp.py", "--local-html", "--profile", "design_consulting"]
```

并且固定：

- `shell=False`
- `cwd=D:\TenderRadarLite`
- 不接受页面自定义命令
- 不接受页面自定义参数

## 安全边界

当前 Web 控制台的真实运行入口默认是安全模式：

- 默认不触发 Feishu
- 默认不调用 AI
- 默认不修改来源 enabled 状态
- 默认不下载附件
- 默认不解析 PDF / DOC / DOCX
- 不暴露 `.env` 内容
- 只展示脱敏后的 stdout / stderr 摘要

页面不会开放：

- 任意命令执行
- shell 命令拼接
- URL 参数切换 Feishu / AI / config
- commit / tag / push / 删除类操作

## 运行状态

`/run` 页面会显示最近一次运行的状态摘要：

- `idle`
- `running`
- `success`
- `failed`

同时展示：

- 开始时间
- 结束时间
- 耗时
- return code
- 是否成功
- `reports/latest.html` 路径
- `reports/latest.html` 是否存在
- stdout / stderr 最近若干行

运行中按钮会禁用，后端也会拒绝并发重复启动。

## 报告与日志

运行完成后，用户可以：

- 点击打开 `latest.html`
- 跳转到日志页查看摘要

控制台不会把历史日志中的旧错误误报成本次失败；本次结果以本次固定命令的 return code 和本次 stdout / stderr 摘要为准。

## Alpha 边界

当前版本可以准确描述为：

- 本地 Web 控制台 Alpha
- 支持安全触发一次本地扫描
- 默认安全模式

当前版本仍不能准确描述为：

- 成熟控制台
- 多用户平台
- 后台调度系统
- 自动投标系统
- 全国覆盖 SaaS
