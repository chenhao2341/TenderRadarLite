# Windows 快速开始

## 适用范围

这份说明面向希望在 Windows 本地运行 TenderRadarLite 并查看本地 HTML 报告的用户。

当前主路径是：

- 命令行运行
- Windows `.bat` 脚本运行
- 浏览器打开本地 `reports/latest.html`

Web 控制台当前仍是 Alpha 骨架，不应视为完整运行入口。

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

- 默认不会触发 Feishu
- 默认不会调用 AI
- 默认不会下载附件
- 默认不会解析 PDF / DOC / DOCX

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

## 如何理解 supported / alpha 来源

当前 `supported` 来源：

- 衡阳公共资源交易平台 / 建设工程交易
- 衡阳公共资源交易平台 / 政府采购交易

当前默认关闭的 `alpha` 来源：

- 长沙公共资源交易平台 / 长沙政府采购交易
- 中国政府采购网 / 地方公告

说明：

- `supported`：当前可作为默认可用来源
- `alpha`：已有 adapter，但不承诺稳定，默认关闭
- `alpha` 不等于不可用，只是不应作为当前开源版主能力承诺

## Web 控制台当前状态

当前 Web 控制台是本地只读 / 半只读 Alpha 骨架：

- 可以看状态、报告入口、日志摘要、来源目录
- 不能包装成成熟控制台
- 当前缺真实运行按钮和完整运行闭环

下一阶段重点见 [docs/WEB_CONSOLE.md](docs/WEB_CONSOLE.md) 与 [docs/ROADMAP.md](docs/ROADMAP.md)。

## 常见问题

### 没有飞书配置也能用吗

可以。默认主路径就是本地 HTML，不依赖 Feishu。

### 默认会调用 AI 吗

不会。只有显式传入相关 AI 参数时才会启用。

### 为什么有些来源默认关闭

因为它们当前是 `alpha` 来源，需要继续做稳定性和字段质量校准。

### 为什么报告里有些字段为空

这是当前 Alpha 阶段的正常现象，部分来源仍存在字段完整性风险，详见 [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md)。
