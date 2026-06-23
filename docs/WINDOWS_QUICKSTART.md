# Windows 快速开始

## 适用范围

本文面向希望在 Windows 本地运行 TenderRadarLite 并查看本地 HTML 报告的用户。

当前主路径仍然是：

- 命令行运行
- Windows `.bat` 脚本运行
- 浏览器打开本地 `reports/latest.html`

另外，当前仓库也提供一个本地 Web 控制台 Alpha。

## 运行前准备

1. 安装 Python 3.11 或更高版本，并确认 `python` 命令可用。
2. 进入项目根目录 `D:\TenderRadarLite`。
3. 安装依赖：

```powershell
python -m pip install -r requirements.txt
```

可选虚拟环境：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## 推荐入口命令

默认推荐命令：

```powershell
python run_mvp.py --local-html --profile design_consulting
```

更简化的本地 HTML 路径：

```powershell
python run_mvp.py --local-html
```

说明：

- 默认不触发 Feishu
- 默认不调用 AI
- 默认不下载附件
- 默认不解析 PDF / DOC / DOCX

## Windows 双击路径

推荐流程：

1. 双击 `scripts/检查运行环境.bat`
2. 双击 `scripts/启动本地招投标报告.bat`
3. 生成完成后打开 `reports/latest.html`

辅助脚本：

- `scripts/打开最新报告.bat`
- `scripts/查看运行日志.bat`

## 输出路径

默认报告路径：

```text
reports/latest.html
```

这是当前最重要的展示产物。每次新运行通常会覆盖该文件。

## 如何打开本地 HTML 报告

可用任一方式：

1. 运行完成后由程序自动尝试打开浏览器
2. 双击 `scripts/打开最新报告.bat`
3. 在资源管理器中手动打开 `reports/latest.html`

如果报告未生成，先看控制台输出和 `logs/`。

## 如何查看日志

日志目录：

```text
logs/
```

可用方式：

1. 双击 `scripts/查看运行日志.bat`
2. 手动打开 `logs/` 查看最新 `.log`

优先检查：

- Python 是否可用
- 依赖是否安装完整
- 当前路径是否是 `D:\TenderRadarLite`
- 运行命令是否包含 `--local-html`

## Web 控制台当前状态

当前 Web 控制台仍是本地 Alpha，但已经支持一个真实、安全、单次运行的入口。

启动方式：

```powershell
python scripts/start_web_console.py
```

或双击：

```text
启动Web控制台.bat
```

打开地址：

```text
http://127.0.0.1:8765
```

进入“运行入口”后，可以点击“运行一次本地扫描”。

该入口固定执行：

```powershell
python run_mvp.py --local-html --profile design_consulting
```

并保持以下边界：

- 固定参数
- 默认不触发 Feishu
- 默认不调用 AI
- 不修改 config
- 不下载附件
- 不解析 PDF / DOC / DOCX
- 不是多用户系统
- 不是后台调度系统

更多说明见 [docs/WEB_CONSOLE.md](docs/WEB_CONSOLE.md)。
