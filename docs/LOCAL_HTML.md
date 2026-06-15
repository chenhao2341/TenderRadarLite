# 本地 HTML 报告

## 这是什么

本地 HTML 报告是 TenderRadarLite 的默认开箱即用查看方式。

它会在本地抓取和结构化处理完成后，生成一个可直接用浏览器打开的 HTML 文件，方便快速查看当次结果。

## 如何生成

```powershell
python -m pip install -r requirements.txt
python run_mvp.py --local-html
```

如果要使用行业 profile：

```powershell
python run_mvp.py --local-html --profile design_consulting
```

## 输出路径

默认输出到：

```text
reports/latest.html
```

每次重新生成时会覆盖这个最新文件。

## 是否需要飞书

不需要。

`--local-html` 会走本地模式，不要求配置飞书 App Secret、Webhook、chat_id 或其他飞书字段。

## 适合什么场景

- 先在本地验证抓取和结构化结果
- 不想配置飞书，只需要浏览器查看结果
- 做 profile 调整时快速观察分类效果
- Windows 用户双击脚本后直接看报告

## 常见问题

### 运行后没有看到报告

先检查命令行输出是否报错，再确认 `reports/latest.html` 是否生成。

### 报告生成了但没有自动打开

可以手动打开 `reports/latest.html`。自动打开失败不会影响报告文件本身生成。

### 本地 HTML 和飞书是什么关系

本地 HTML 是默认、本地优先的查看方式。飞书是可选高级输出插件，两者不是绑定关系。

### 可以配合 profile 使用吗

可以。推荐先用：

```powershell
python run_mvp.py --local-html --profile design_consulting
```

### 生成的 HTML 能直接提交到 Git 吗

不建议。`reports/latest.html` 属于本地生成产物，开源发布前应保持未入 Git。
