# Windows 快速开始

## 适用人群

这份说明适合希望在 Windows 本地运行 TenderRadarLite 并生成本地 HTML 报告的用户。

本地 HTML 报告模式不依赖飞书，不需要 App Secret，不需要 Webhook，也不需要 `chat_id`。飞书属于高级可选功能，不是 Windows 本地报告的前置条件。

## 首次使用前

1. 安装 Python 3.11 或更高版本，并确认 `python` 命令可用。
2. 进入项目根目录 `D:\TenderRadarLite`。
3. 可选创建虚拟环境：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

4. 安装依赖：

```powershell
python -m pip install -r requirements.txt
```

## 推荐使用流程

1. 双击 `scripts/检查运行环境.bat`
2. 双击 `scripts/启动本地招投标报告.bat`
3. 打开 `reports/latest.html` 查看最新本地报告

## 脚本说明

### `scripts/启动本地招投标报告.bat`

- 执行 `python run_mvp.py --local-html`
- 生成本地 HTML 报告 `reports/latest.html`
- 成功后由 Python 内部尝试自动打开浏览器

### `scripts/打开最新报告.bat`

- 直接打开 `reports/latest.html`
- 不重新抓取数据

### `scripts/查看运行日志.bat`

- 打开 `logs/` 目录
- 方便查看本地运行日志

### `scripts/检查运行环境.bat`

- 检查当前目录是否正确
- 检查 Python 是否可用
- 检查 `requirements.txt`、`run_mvp.py`、`data/`、`logs/`、`reports/`
- 检查关键依赖是否可导入
- 不自动安装依赖，不自动修改环境

## 常见问题

### 双击后窗口一闪而过

先运行 `scripts/检查运行环境.bat`，根据停留窗口里的提示补齐 Python 或依赖问题。

### 没有生成报告

先检查脚本窗口输出，再查看 `logs/` 目录中的本地运行日志。

### `reports/latest.html` 在哪里

位于项目根目录下的 `reports/latest.html`。

### 没有飞书配置也能用吗

可以。本地 HTML 是默认可用路径。
