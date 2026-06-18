from __future__ import annotations

import html
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dotenv import dotenv_values

from .source_catalog import get_source_catalog_summary, list_sources, load_source_catalog, validate_source_catalog


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_PROFILE_ID = "design_consulting"
SAFE_LOG_LINE_LIMIT = 40
STATUS_LABELS = {
    "supported": "已支持",
    "alpha": "Alpha",
    "candidate": "候选",
    "planned": "计划研究",
    "blocked": "暂不建议",
}
SOURCE_TYPE_LABELS = {
    "government_procurement": "政府采购",
    "public_resource_trading": "公共资源交易",
    "industry_platform": "行业平台",
    "enterprise_procurement": "企业采购",
    "aggregator": "聚合来源",
    "sensitive": "敏感来源",
    "unknown": "未知",
}
RISK_LABELS = {
    "low": "低",
    "medium": "中",
    "high": "高",
    "unknown": "未知",
}
ATTACHMENT_LABELS = {
    "yes": "有",
    "likely": "可能有",
    "no": "无",
    "unknown": "未知",
}
LOGIN_REQUIREMENT_LABELS = {
    "no": "无需登录",
    "likely": "可能需要",
    "yes": "需要登录",
    "unknown": "未知",
}


@dataclass(frozen=True)
class WebConsoleConfig:
    root_dir: Path
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT


class WebConsoleService:
    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = (root_dir or Path(__file__).resolve().parent.parent).resolve()
        self.profiles_dir = self.root_dir / "profiles"
        self.reports_dir = self.root_dir / "reports"
        self.logs_dir = self.root_dir / "logs"
        self.web_static_dir = self.root_dir / "web" / "static"
        self.report_path = self.reports_dir / "latest.html"
        self.env_path = self.root_dir / ".env"
        self.env_example_path = self.root_dir / ".env.example"
        self.source_catalog_path = self.root_dir / "config" / "source_catalog.yaml"

    def handle_api_request(self, method: str, path: str) -> dict[str, Any]:
        routes: dict[tuple[str, str], Any] = {
            ("GET", "/api/status"): self.get_status_payload,
            ("GET", "/api/report"): self.get_report_payload,
            ("GET", "/api/logs"): self.get_logs_payload,
            ("GET", "/api/config-status"): self.get_config_status_payload,
            ("GET", "/api/profiles"): self.get_profiles_payload,
            ("GET", "/api/source-catalog"): self.get_source_catalog_payload,
            ("GET", "/api/run"): self.get_run_payload,
            ("POST", "/api/run"): self.get_run_action_payload,
        }
        try:
            return routes[(method.upper(), path)]()
        except KeyError as exc:
            raise FileNotFoundError(path) from exc

    def render_page(self, page: str) -> str:
        builders = {
            "dashboard": self._render_dashboard_page,
            "run": self._render_run_page,
            "report": self._render_report_page,
            "logs": self._render_logs_page,
            "config": self._render_config_page,
            "sources": self._render_sources_page,
        }
        builder = builders.get(page, self._render_dashboard_page)
        return self._render_layout(page, builder())

    def get_status_payload(self) -> dict[str, Any]:
        report = self.get_report_payload()
        config = self.get_config_status_payload()
        git_status = self._get_git_status()
        logs = self.get_logs_payload()
        source_catalog = self.get_source_catalog_payload()
        return {
            "project": {
                "name": "TenderRadarLite 本地控制台",
                "root_dir": str(self.root_dir),
                "git_head": git_status["head"],
                "git_clean": git_status["clean"],
            },
            "report": {
                "exists": report["exists"],
                "updated_at": report["updated_at"],
                "open_url": "/artifacts/report/latest" if report["exists"] else "",
            },
            "mode": {
                "default_public_mode": True,
                "enterprise_mode_optional": True,
                "safety_notice": "默认不触发飞书，默认不调用 AI。",
            },
            "profiles": {
                "available_profiles": self._available_profile_ids(),
                "company_profile_status": config["company_profile"]["status"],
            },
            "integrations": {
                "ai_analysis": config["ai"]["summary"],
                "feishu": config["feishu"]["summary"],
            },
            "logs": {
                "latest_file": logs["latest_file"],
                "latest_lines": logs["latest_lines"][:5],
            },
            "source_catalog": {
                "summary": source_catalog["summary"],
                "safe_notice": source_catalog["safe_notice"],
            },
            "recommended_command": self._build_recommended_command(),
        }

    def get_run_payload(self) -> dict[str, Any]:
        company_profile = self._detect_company_profile()
        return {
            "defaults": {
                "local_html": True,
                "ai_analysis": False,
                "feishu_sync": False,
            },
            "profiles": self._available_profile_ids(),
            "company_profile": company_profile,
            "recommended_command": self._build_recommended_command(),
            "enterprise_command": self._build_recommended_command(
                company_profile_path=company_profile["suggested_path"] if company_profile["sample_exists"] else ""
            ),
            "copy_supported": True,
            "run_button_enabled": False,
            "run_mode": "command-only",
            "safety_notice": "当前只提供推荐命令，不会从页面触发真实抓取。",
        }

    def get_run_action_payload(self) -> dict[str, Any]:
        company_profile = self._detect_company_profile()
        return {
            "mode": "command-only",
            "recommended_command": self._build_recommended_command(),
            "enterprise_command": self._build_recommended_command(
                company_profile_path=company_profile["suggested_path"] if company_profile["sample_exists"] else ""
            ),
            "message": "当前 Alpha 只提供安全推荐命令，未接入真实运行按钮。",
            "will_trigger_feishu": False,
            "will_trigger_ai": False,
        }

    def get_report_payload(self) -> dict[str, Any]:
        exists = self.report_path.exists()
        return {
            "exists": exists,
            "path": str(self.report_path),
            "updated_at": self._format_mtime(self.report_path) if exists else "",
            "open_url": "/artifacts/report/latest" if exists else "",
            "message": "" if exists else "尚未生成本地报告，请先运行 --local-html。",
        }

    def get_logs_payload(self) -> dict[str, Any]:
        log_files = sorted(
            [path for path in self.logs_dir.glob("*.log") if path.is_file()],
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        latest_file = ""
        latest_lines: list[str] = []
        error = ""
        if log_files:
            latest_file = log_files[0].name
            try:
                raw_lines = log_files[0].read_text(encoding="utf-8", errors="replace").splitlines()
                latest_lines = [self._sanitize_log_line(line) for line in raw_lines[-SAFE_LOG_LINE_LIMIT:]]
            except OSError as exc:
                error = f"日志读取失败：{exc}"
        return {
            "files": [path.name for path in log_files[:10]],
            "latest_file": latest_file,
            "latest_lines": latest_lines,
            "error": error,
        }

    def get_config_status_payload(self) -> dict[str, Any]:
        env_values = self._load_env_values()
        ai_key_present = bool((env_values.get("DEEPSEEK_API_KEY") or "").strip())
        ai_model_present = bool((env_values.get("DEEPSEEK_MODEL") or "").strip())
        ai_provider_present = bool(
            ai_key_present or ai_model_present or (env_values.get("DEEPSEEK_BASE_URL") or "").strip()
        )
        feishu_fields = {
            "app_id": self._status_label(env_values.get("FEISHU_APP_ID")),
            "app_secret": self._status_label(env_values.get("FEISHU_APP_SECRET")),
            "bitable_url": self._status_label(env_values.get("FEISHU_BITABLE_URL")),
            "webhook_url": self._status_label(env_values.get("FEISHU_WEBHOOK_URL")),
            "chat_id": self._status_label(env_values.get("FEISHU_CHAT_ID")),
        }
        feishu_summary = "已配置" if any(value == "已配置" for value in feishu_fields.values()) else "缺失"
        ai_summary = "已配置" if ai_key_present else ("部分配置" if ai_provider_present else "未启用")
        return {
            "env_file_exists": self.env_path.exists(),
            "env_example_exists": self.env_example_path.exists(),
            "feishu": {
                **feishu_fields,
                "summary": feishu_summary,
            },
            "ai": {
                "provider": "已配置" if ai_provider_present else "缺失",
                "model": "已配置" if ai_model_present else "缺失",
                "api_key": "已配置" if ai_key_present else "缺失",
                "summary": ai_summary,
            },
            "profiles_dir_exists": self.profiles_dir.exists(),
            "reports_dir_exists": self.reports_dir.exists(),
            "logs_dir_exists": self.logs_dir.exists(),
            "company_profile": self._detect_company_profile(),
        }

    def get_profiles_payload(self) -> dict[str, Any]:
        return {
            "industry_profiles": self._available_profile_ids(),
            "company_profile": self._detect_company_profile(),
        }

    def get_source_catalog_payload(self) -> dict[str, Any]:
        catalog = load_source_catalog(self.source_catalog_path)
        errors = validate_source_catalog(catalog)
        summary = get_source_catalog_summary(catalog)
        return {
            "summary": summary,
            "sources": list_sources(catalog),
            "validation_errors": errors,
            "safe_notice": "候选 / 计划研究 不代表已经支持抓取；本页只是来源知识库，不会触发抓取。",
            "will_trigger_feishu": False,
            "will_trigger_ai": False,
        }

    def _load_env_values(self) -> dict[str, str]:
        if not self.env_path.exists():
            return {}
        values = dotenv_values(self.env_path)
        return {str(key): str(value or "") for key, value in values.items()}

    def _available_profile_ids(self) -> list[str]:
        if not self.profiles_dir.exists():
            return []
        return sorted(path.stem for path in self.profiles_dir.glob("*.json") if path.is_file())

    def _detect_company_profile(self) -> dict[str, Any]:
        sample_path = self.profiles_dir / "company_sample.yaml"
        yaml_paths = sorted(path for path in self.profiles_dir.glob("*.yaml") if path.is_file())
        return {
            "status": "已发现示例" if sample_path.exists() else "未选择",
            "sample_exists": sample_path.exists(),
            "suggested_path": sample_path.relative_to(self.root_dir).as_posix() if sample_path.exists() else "",
            "optional_paths": [path.relative_to(self.root_dir).as_posix() for path in yaml_paths[:5]],
        }

    def _build_recommended_command(
        self,
        profile_id: str = DEFAULT_PROFILE_ID,
        company_profile_path: str = "",
    ) -> str:
        command_parts = ["python", "run_mvp.py", "--local-html"]
        if profile_id:
            command_parts.extend(["--profile", profile_id])
        if company_profile_path:
            command_parts.extend(["--company-profile", company_profile_path])
        return " ".join(command_parts)

    def _get_git_status(self) -> dict[str, Any]:
        try:
            head = subprocess.run(
                ["git", "-C", str(self.root_dir), "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            status_output = subprocess.run(
                ["git", "-C", str(self.root_dir), "status", "--short"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            return {"head": head or "unknown", "clean": not bool(status_output)}
        except (subprocess.CalledProcessError, FileNotFoundError):
            return {"head": "unknown", "clean": None}

    def _sanitize_log_line(self, line: str) -> str:
        sanitized = line.replace("\r", "").strip()
        sensitive_tokens = [
            "DEEPSEEK_API_KEY",
            "FEISHU_APP_SECRET",
            "FEISHU_WEBHOOK_URL",
            "tenant_access_token",
            "Authorization",
        ]
        for token in sensitive_tokens:
            if token in sanitized:
                sanitized = f"{token}=***"
        return sanitized

    def _status_label(self, value: Any) -> str:
        return "已配置" if str(value or "").strip() else "缺失"

    def _format_mtime(self, path: Path) -> str:
        try:
            return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        except OSError:
            return ""

    def _git_clean_label(self, git_clean: bool | None) -> str:
        if git_clean is True:
            return "工作区干净"
        if git_clean is False:
            return "有未提交变更"
        return "未知"

    def _render_dashboard_page(self) -> str:
        status = self.get_status_payload()
        report = status["report"]
        logs = status["logs"]
        report_action = (
            '<a class="button" href="/artifacts/report/latest" target="_blank" rel="noopener">打开 latest.html</a>'
            if report["exists"]
            else '<a class="button secondary" href="/run">查看推荐命令</a>'
        )
        log_lines = "".join(f"<li>{html.escape(line)}</li>" for line in logs["latest_lines"]) or "<li>暂无日志摘要。</li>"
        return f"""
        <section class="hero">
          <div>
            <p class="eyebrow">TenderRadarLite 本地控制台</p>
            <h1>本地优先的招投标线索监控入口</h1>
            <p class="hero-copy">公开模式默认，企业模式可选。默认不触发飞书，默认不调用 AI。</p>
          </div>
          <div class="hero-actions">
            <a class="button" href="/run">查看运行入口</a>
            {report_action}
          </div>
        </section>
        <section class="grid">
          {self._card("项目状态", f"<p>当前 Git 版本：<strong>{html.escape(status['project']['git_head'])}</strong></p><p>工作区状态：<strong>{self._git_clean_label(status['project']['git_clean'])}</strong></p>")}
          {self._card("报告状态", f"<p>本地报告：<strong>{'已生成' if report['exists'] else '未生成'}</strong></p><p>更新时间：{html.escape(report['updated_at'] or '暂无')}</p>")}
          {self._card("配置状态", f"<p>AI 分析：<strong>{html.escape(status['integrations']['ai_analysis'])}</strong></p><p>飞书：<strong>{html.escape(status['integrations']['feishu'])}</strong></p>")}
          {self._card("配置概览", f"<p>行业配置：<strong>{len(status['profiles']['available_profiles'])}</strong></p><p>企业画像：<strong>{html.escape(status['profiles']['company_profile_status'])}</strong></p>")}
          {self._card("来源目录摘要", self._render_source_summary(status["source_catalog"]["summary"]))}
        </section>
        <section class="panel">
          <div class="panel-header"><h2>最近日志摘要</h2><a href="/logs">查看全部</a></div>
          <ul class="log-list">{log_lines}</ul>
        </section>
        <section class="panel">
          <div class="panel-header"><h2>默认推荐命令</h2></div>
          <pre>{html.escape(status['recommended_command'])}</pre>
        </section>
        """

    def _render_run_page(self) -> str:
        payload = self.get_run_payload()
        profiles = "".join(f"<li>{html.escape(item)}</li>" for item in payload["profiles"]) or "<li>暂无 industry profile</li>"
        optional_company_paths = "".join(
            f"<li>{html.escape(item)}</li>" for item in payload["company_profile"]["optional_paths"]
        ) or "<li>暂无 company profile</li>"
        return f"""
        <section class="panel">
          <div class="panel-header"><h1>运行入口</h1></div>
          <p>{html.escape(payload['safety_notice'])}</p>
          <div class="grid">
            {self._card("默认选项", "<p>本地 HTML 报告：开启</p><p>AI 分析：关闭</p><p>飞书同步：关闭</p>")}
            {self._card("行业配置", f"<ul>{profiles}</ul><p>其他行业 profile 当前可用于测试或后续扩展。</p>")}
            {self._card("企业画像", f"<p>状态：{html.escape(payload['company_profile']['status'])}</p><p>建议路径：{html.escape(payload['company_profile']['suggested_path'] or '未发现')}</p><ul>{optional_company_paths}</ul>")}
          </div>
        </section>
        <section class="panel">
          <div class="panel-header"><h2>推荐命令</h2></div>
          <p><strong>公开模式：</strong>默认推荐，适合开源用户快速体验。</p>
          <pre id="recommended-command">{html.escape(payload['recommended_command'])}</pre>
          <button class="button" type="button" onclick="copyCommand()">复制命令</button>
          <p><strong>企业模式：</strong>可选，需要 company profile，用于企业商机初筛。</p>
          <pre>{html.escape(payload['enterprise_command'])}</pre>
          <p class="hint">当前不提供真实运行按钮，避免误触发飞书、AI 或额外抓取流程。</p>
        </section>
        """

    def _render_report_page(self) -> str:
        payload = self.get_report_payload()
        action = (
            '<a class="button" href="/artifacts/report/latest" target="_blank" rel="noopener">打开报告</a>'
            if payload["exists"]
            else '<a class="button secondary" href="/run">先查看推荐命令</a>'
        )
        message = payload["message"] if not payload["exists"] else "报告已就绪，可直接在浏览器中打开。"
        return f"""
        <section class="panel">
          <div class="panel-header"><h1>报告入口</h1></div>
          <p>latest.html：<strong>{'已生成' if payload['exists'] else '未生成'}</strong></p>
          <p>更新时间：{html.escape(payload['updated_at'] or '暂无')}</p>
          <p>{html.escape(message)}</p>
          {action}
        </section>
        """

    def _render_logs_page(self) -> str:
        payload = self.get_logs_payload()
        file_items = "".join(f"<li>{html.escape(item)}</li>" for item in payload["files"]) or "<li>暂无日志文件。</li>"
        log_items = "".join(f"<li>{html.escape(line)}</li>" for line in payload["latest_lines"]) or "<li>暂无日志摘要。</li>"
        error_block = f"<p class='error'>{html.escape(payload['error'])}</p>" if payload["error"] else ""
        return f"""
        <section class="panel">
          <div class="panel-header"><h1>日志</h1></div>
          {error_block}
          <div class="grid">
            {self._card("日志文件", f"<ul>{file_items}</ul>")}
            {self._card("最新摘要", f"<ul class='log-list'>{log_items}</ul>")}
          </div>
        </section>
        """

    def _render_config_page(self) -> str:
        payload = self.get_config_status_payload()
        return f"""
        <section class="panel">
          <div class="panel-header"><h1>配置状态</h1></div>
          <div class="grid">
            {self._card("环境文件", f"<p>.env：<strong>{'存在' if payload['env_file_exists'] else '不存在'}</strong></p><p>.env.example：<strong>{'存在' if payload['env_example_exists'] else '不存在'}</strong></p>")}
            {self._card("飞书", self._render_status_table(payload['feishu']))}
            {self._card("AI 分析", self._render_status_table(payload['ai']))}
            {self._card("目录状态", f"<p>profiles/：{'存在' if payload['profiles_dir_exists'] else '不存在'}</p><p>reports/：{'存在' if payload['reports_dir_exists'] else '不存在'}</p><p>logs/：{'存在' if payload['logs_dir_exists'] else '不存在'}</p>")}
          </div>
        </section>
        """

    def _render_sources_page(self) -> str:
        payload = self.get_source_catalog_payload()
        summary = payload["summary"]
        rows = []
        for source in payload["sources"]:
            source_type = self._source_type_label(source.get("source_type"))
            status = self._status_label_text(source.get("status"))
            access_risk = self._risk_label(source.get("access_risk"))
            attachments = self._attachment_label(source.get("has_attachments"))
            rows.append(
                "<tr>"
                f"<td class=\"name-cell\">{html.escape(str(source.get('name', '')))}</td>"
                f"<td class=\"region-cell\">{html.escape(str(source.get('region', '')))}</td>"
                f"<td class=\"type-cell\"><span class=\"badge badge-type\">{html.escape(source_type)}</span></td>"
                f"<td class=\"status-cell\"><span class=\"badge badge-status status-{html.escape(str(source.get('status') or 'unknown'))}\">{html.escape(status)}</span></td>"
                f"<td class=\"adapter-cell\"><code>{html.escape(str(source.get('adapter') or '-'))}</code></td>"
                f"<td class=\"risk-cell\"><span class=\"badge badge-risk risk-{html.escape(str(source.get('access_risk') or 'unknown'))}\">{html.escape(access_risk)}</span></td>"
                f"<td class=\"attachments-cell\"><span class=\"badge badge-attachment\">{html.escape(attachments)}</span></td>"
                f"<td class=\"notes-cell\">{html.escape(str(source.get('notes', '')))}</td>"
                "</tr>"
            )
        validation_block = ""
        if payload["validation_errors"]:
            validation_items = "".join(f"<li>{html.escape(item)}</li>" for item in payload["validation_errors"])
            validation_block = f"<section class='panel'><div class='panel-header'><h2>校验提醒</h2></div><ul>{validation_items}</ul></section>"
        return f"""
        <section class="panel">
          <div class="panel-header"><h1>来源目录</h1></div>
          <p>{html.escape(payload['safe_notice'])}</p>
          <p>已支持 / Alpha 才与当前 adapter 有关；候选 / 计划研究 / 暂不建议 仅用于来源知识库记录。</p>
          <p>本页不会新增、编辑、删除来源，也不会提供接入按钮、抓取按钮、Feishu 或 AI 操作。</p>
        </section>
        <section class="grid">
          {self._card("来源总数", f"<p><strong>{summary['total']}</strong></p>")}
          {self._card("状态统计", self._render_source_summary(summary))}
        </section>
        <section class="panel">
          <div class="panel-header"><h2>来源清单</h2></div>
          <div class="table-wrap">
          <table class="source-table">
            <thead>
              <tr>
                <th>名称</th>
                <th>地区</th>
                <th>来源类型</th>
                <th>状态</th>
                <th>adapter</th>
                <th>访问风险</th>
                <th>附件可能性</th>
                <th>备注</th>
              </tr>
            </thead>
            <tbody>{''.join(rows)}</tbody>
          </table>
          </div>
        </section>
        {validation_block}
        """

    def _render_source_summary(self, summary: dict[str, Any]) -> str:
        by_status = summary.get("by_status", {})
        return (
            f"<p>来源总数：<strong>{summary.get('total', 0)}</strong></p>"
            f"<p>已支持：<strong>{by_status.get('supported', 0)}</strong></p>"
            f"<p>Alpha：<strong>{by_status.get('alpha', 0)}</strong></p>"
            f"<p>候选：<strong>{by_status.get('candidate', 0)}</strong></p>"
            f"<p>计划研究：<strong>{by_status.get('planned', 0)}</strong></p>"
            f"<p>暂不建议：<strong>{by_status.get('blocked', 0)}</strong></p>"
        )

    def _status_label_text(self, value: Any) -> str:
        normalized = str(value or "").strip()
        return STATUS_LABELS.get(normalized, normalized or "未知")

    def _source_type_label(self, value: Any) -> str:
        normalized = str(value or "").strip()
        return SOURCE_TYPE_LABELS.get(normalized, normalized or "未知")

    def _risk_label(self, value: Any) -> str:
        normalized = str(value or "").strip()
        return RISK_LABELS.get(normalized, normalized or "未知")

    def _attachment_label(self, value: Any) -> str:
        normalized = str(value or "").strip()
        return ATTACHMENT_LABELS.get(normalized, normalized or "未知")

    def _render_status_table(self, payload: dict[str, Any]) -> str:
        rows = []
        for key, value in payload.items():
            if isinstance(value, dict):
                continue
            rows.append(f"<tr><td>{html.escape(str(key))}</td><td>{html.escape(str(value))}</td></tr>")
        return f"<table>{''.join(rows)}</table>"

    def _render_layout(self, active_page: str, body: str) -> str:
        return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TenderRadarLite 本地控制台</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <div class="shell">
    <aside class="sidebar">
      <h2>TenderRadarLite</h2>
      {self._render_nav(active_page)}
      <p class="sidebar-note">Alpha 边界：不生成投标文件，不导出 Word，不做多用户系统。</p>
    </aside>
    <main class="content">{body}</main>
  </div>
  <script>
    function copyCommand() {{
      const el = document.getElementById('recommended-command');
      if (!el) return;
      navigator.clipboard.writeText(el.innerText).catch(function () {{}});
    }}
  </script>
</body>
</html>"""

    def _render_nav(self, active_page: str) -> str:
        items = [
            ("dashboard", "/", "仪表盘"),
            ("run", "/run", "运行入口"),
            ("report", "/report", "报告入口"),
            ("logs", "/logs", "日志"),
            ("config", "/config", "配置状态"),
            ("sources", "/sources", "来源目录"),
        ]
        links = []
        for key, path, label in items:
            css_class = "active" if key == active_page else ""
            links.append(f'<a class="{css_class}" href="{path}">{label}</a>')
        return "<nav>" + "".join(links) + "</nav>"

    def _card(self, title: str, content: str) -> str:
        return f"<article class='card'><h3>{html.escape(title)}</h3>{content}</article>"


class WebConsoleRequestHandler(BaseHTTPRequestHandler):
    service: WebConsoleService

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def _dispatch(self, method: str) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path in {"/", "/run", "/report", "/logs", "/config", "/sources"}:
                page_name = {
                    "/": "dashboard",
                    "/run": "run",
                    "/report": "report",
                    "/logs": "logs",
                    "/config": "config",
                    "/sources": "sources",
                }[parsed.path]
                self._send_html(self.service.render_page(page_name))
                return
            if parsed.path.startswith("/api/"):
                self._send_json(self.service.handle_api_request(method, parsed.path))
                return
            if parsed.path == "/artifacts/report/latest":
                self._send_report_file()
                return
            if parsed.path == "/static/style.css":
                self._send_static_file(self.service.web_static_dir / "style.css", "text/css; charset=utf-8")
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
        except Exception as exc:  # pragma: no cover
            self._send_html(self._render_error_page(str(exc)), status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def _send_html(self, body: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_report_file(self) -> None:
        if not self.service.report_path.exists():
            self._send_html(self.service.render_page("report"), status=HTTPStatus.NOT_FOUND)
            return
        data = self.service.report_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_static_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Static file not found")
            return
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _render_error_page(self, message: str) -> str:
        safe_message = html.escape(message or "unknown error")
        return (
            "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
            "<title>TenderRadarLite 错误</title></head><body><main>"
            "<h1>页面暂时不可用</h1>"
            f"<p>{safe_message}</p><p><a href='/'>返回首页</a></p>"
            "</main></body></html>"
        )

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return


def create_server(config: WebConsoleConfig | None = None) -> ThreadingHTTPServer:
    active_config = config or WebConsoleConfig(root_dir=Path(__file__).resolve().parent.parent)
    service = WebConsoleService(root_dir=active_config.root_dir)

    class BoundHandler(WebConsoleRequestHandler):
        pass

    BoundHandler.service = service
    return ThreadingHTTPServer((active_config.host, active_config.port), BoundHandler)


def run_web_console(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, root_dir: Path | None = None) -> None:
    config = WebConsoleConfig(root_dir=(root_dir or Path(__file__).resolve().parent.parent), host=host, port=port)
    server = create_server(config)
    print(f"TenderRadarLite Web Console: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    host = os.getenv("TENDERRADAR_WEB_HOST", DEFAULT_HOST)
    port = int(os.getenv("TENDERRADAR_WEB_PORT", str(DEFAULT_PORT)))
    run_web_console(host=host, port=port)
