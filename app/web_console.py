from __future__ import annotations

import html
import json
import os
import re
import subprocess
import sys
import threading
from dataclasses import asdict, dataclass, field
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
RUN_OUTPUT_TAIL_LIMIT = 20
RUN_HISTORY_LIMIT = 5
RUN_TIMEOUT_SECONDS = 300
SENSITIVE_LINE_PATTERN = re.compile(
    r"(?i)\b([A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|WEBHOOK|PASSWORD|FEISHU|DEEPSEEK)[A-Z0-9_]*)\b\s*([:=])\s*([^\s,;]+)"
)
AUTHORIZATION_PATTERN = re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)([^\s,;]+)")

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


class RunConflictError(RuntimeError):
    """Raised when a second scan is requested while one is already running."""


@dataclass(frozen=True)
class WebConsoleConfig:
    root_dir: Path
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT


@dataclass
class RunState:
    status: str = "idle"
    started_at: str = ""
    finished_at: str = ""
    duration_seconds: float | None = None
    command: str = ""
    returncode: int | None = None
    success: bool | None = None
    stdout_tail: list[str] = field(default_factory=list)
    stderr_tail: list[str] = field(default_factory=list)
    report_path: str = ""
    report_exists: bool = False
    error_message: str = ""


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
        self._run_state_lock = threading.Lock()
        self._run_process_lock = threading.Lock()
        self._run_history: list[RunState] = []
        self._run_state = self._new_run_state()

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
            ("GET", "/api/run/status"): self.get_run_status_payload,
            ("GET", "/api/run/history"): self.get_run_history_payload,
            ("POST", "/api/run/local-scan"): self.start_local_scan,
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
        run_status = self.get_run_status_payload()
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
                "safety_notice": "默认不触发 Feishu，默认不调用 AI。",
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
            "run": {
                "status": run_status["status"],
                "started_at": run_status["started_at"],
                "finished_at": run_status["finished_at"],
                "returncode": run_status["returncode"],
                "report_exists": run_status["report_exists"],
            },
            "recommended_command": self._build_recommended_command(),
        }

    def get_run_payload(self) -> dict[str, Any]:
        company_profile = self._detect_company_profile()
        run_status = self.get_run_status_payload()
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
            "run_button_enabled": run_status["status"] != "running",
            "run_mode": "single-shot-local-scan",
            "status_url": "/api/run/status",
            "history_url": "/api/run/history",
            "start_url": "/api/run/local-scan",
            "safety_notice": "固定执行一次本地扫描：默认不触发 Feishu，不调用 AI，不修改来源配置。",
        }

    def get_run_action_payload(self) -> dict[str, Any]:
        company_profile = self._detect_company_profile()
        return {
            "mode": "command-only",
            "recommended_command": self._build_recommended_command(),
            "enterprise_command": self._build_recommended_command(
                company_profile_path=company_profile["suggested_path"] if company_profile["sample_exists"] else ""
            ),
            "message": "旧接口保留为只读提示。真实执行请使用 POST /api/run/local-scan。",
            "will_trigger_feishu": False,
            "will_trigger_ai": False,
        }

    def get_run_status_payload(self) -> dict[str, Any]:
        with self._run_state_lock:
            state = asdict(self._run_state)
        state["open_report_url"] = "/artifacts/report/latest" if state["report_exists"] else ""
        return state

    def get_run_history_payload(self) -> dict[str, Any]:
        with self._run_state_lock:
            items = [asdict(item) for item in self._run_history]
        for item in items:
            item["open_report_url"] = "/artifacts/report/latest" if item["report_exists"] else ""
        return {"items": items}

    def start_local_scan(self) -> dict[str, Any]:
        with self._run_state_lock:
            if self._run_state.status == "running":
                raise RunConflictError("已有任务正在运行")
            started_at = self._format_now()
            self._run_state = RunState(
                status="running",
                started_at=started_at,
                command=self._command_to_text(self._build_local_scan_command()),
                report_path=str(self.report_path),
                report_exists=self.report_path.exists(),
            )
        thread = threading.Thread(target=self._execute_local_scan, name="tenderradar-local-scan", daemon=True)
        thread.start()
        return self.get_run_status_payload()

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
                latest_lines = [self._sanitize_display_line(line) for line in raw_lines[-SAFE_LOG_LINE_LIMIT:]]
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
            "safe_notice": "候选/计划研究不代表已经支持抓取；本页只是来源知识库，不会触发抓取。",
            "will_trigger_feishu": False,
            "will_trigger_ai": False,
        }

    def _execute_local_scan(self) -> None:
        if not self._run_process_lock.acquire(blocking=False):
            self._finish_run(
                status="failed",
                returncode=None,
                stdout="",
                stderr="",
                error_message="已有任务正在运行",
            )
            return
        started_at = datetime.now()
        try:
            command = self._build_local_scan_command()
            result = subprocess.run(
                command,
                cwd=str(self.root_dir),
                shell=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=RUN_TIMEOUT_SECONDS,
                check=False,
            )
            self._finish_run(
                status="success" if result.returncode == 0 else "failed",
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                started_at=started_at,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = self._coerce_output_text(exc.stdout)
            stderr = self._coerce_output_text(exc.stderr)
            self._finish_run(
                status="failed",
                returncode=None,
                stdout=stdout,
                stderr=stderr,
                started_at=started_at,
                error_message=f"运行超时：超过 {RUN_TIMEOUT_SECONDS} 秒",
            )
        except Exception as exc:  # pragma: no cover
            self._finish_run(
                status="failed",
                returncode=None,
                stdout="",
                stderr="",
                started_at=started_at,
                error_message=f"启动失败：{exc}",
            )
        finally:
            self._run_process_lock.release()

    def _finish_run(
        self,
        status: str,
        returncode: int | None,
        stdout: str,
        stderr: str,
        started_at: datetime | None = None,
        error_message: str = "",
    ) -> None:
        finished_at = datetime.now()
        with self._run_state_lock:
            previous_started_at = self._run_state.started_at
            started_at_text = previous_started_at or self._format_datetime(started_at or finished_at)
            duration_seconds = None
            if started_at is not None:
                duration_seconds = round((finished_at - started_at).total_seconds(), 3)
            state = RunState(
                status=status,
                started_at=started_at_text,
                finished_at=self._format_datetime(finished_at),
                duration_seconds=duration_seconds,
                command=self._command_to_text(self._build_local_scan_command()),
                returncode=returncode,
                success=True if status == "success" else False,
                stdout_tail=self._tail_output(stdout),
                stderr_tail=self._tail_output(stderr),
                report_path=str(self.report_path),
                report_exists=self.report_path.exists(),
                error_message=self._sanitize_display_line(error_message) if error_message else "",
            )
            self._run_state = state
            self._run_history.insert(0, state)
            self._run_history = self._run_history[:RUN_HISTORY_LIMIT]

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

    def _build_local_scan_command(self) -> list[str]:
        return [sys.executable, "run_mvp.py", "--local-html", "--profile", DEFAULT_PROFILE_ID]

    def _command_to_text(self, command: list[str]) -> str:
        return subprocess.list2cmdline(command)

    def _new_run_state(self) -> RunState:
        return RunState(
            status="idle",
            command=self._command_to_text(self._build_local_scan_command()),
            report_path=str(self.report_path),
            report_exists=self.report_path.exists(),
        )

    def _coerce_output_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)

    def _tail_output(self, text: str) -> list[str]:
        if not text:
            return []
        lines = [self._sanitize_display_line(line) for line in text.splitlines() if line.strip()]
        if len(lines) <= RUN_OUTPUT_TAIL_LIMIT:
            return lines
        return lines[-RUN_OUTPUT_TAIL_LIMIT:]

    def _sanitize_display_line(self, line: str) -> str:
        sanitized = str(line or "").replace("\r", "").strip()
        sanitized = SENSITIVE_LINE_PATTERN.sub(r"\1\2***", sanitized)
        sanitized = AUTHORIZATION_PATTERN.sub(r"\1***", sanitized)
        return sanitized

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

    def _status_label(self, value: Any) -> str:
        return "已配置" if str(value or "").strip() else "缺失"

    def _format_mtime(self, path: Path) -> str:
        try:
            return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        except OSError:
            return ""

    def _format_datetime(self, value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")

    def _format_now(self) -> str:
        return self._format_datetime(datetime.now())

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
        run = status["run"]
        report_action = (
            '<a class="button" href="/artifacts/report/latest" target="_blank" rel="noopener">打开 latest.html</a>'
            if report["exists"]
            else '<a class="button secondary" href="/run">进入运行入口</a>'
        )
        log_lines = "".join(f"<li>{html.escape(line)}</li>" for line in logs["latest_lines"]) or "<li>暂无日志摘要。</li>"
        return f"""
        <section class="hero">
          <div>
            <p class="eyebrow">TenderRadarLite 本地控制台 Alpha</p>
            <h1>本地优先的投标线索扫描入口</h1>
            <p class="hero-copy">复用现有控制台骨架，默认安全模式。运行入口固定执行本地单次扫描，不触发 Feishu，不调用 AI。</p>
          </div>
          <div class="hero-actions">
            <a class="button" href="/run">运行入口</a>
            {report_action}
          </div>
        </section>
        <section class="grid">
          {self._card("项目状态", f"<p>当前 Git 版本：<strong>{html.escape(status['project']['git_head'])}</strong></p><p>工作区状态：<strong>{self._git_clean_label(status['project']['git_clean'])}</strong></p>")}
          {self._card("报告状态", f"<p>latest.html：<strong>{'已生成' if report['exists'] else '未生成'}</strong></p><p>更新时间：{html.escape(report['updated_at'] or '暂无')}</p>")}
          {self._card("运行状态", f"<p>当前状态：<strong>{html.escape(run['status'])}</strong></p><p>最近 return code：{html.escape(str(run['returncode']) if run['returncode'] is not None else '暂无')}</p>")}
          {self._card("配置状态", f"<p>AI：<strong>{html.escape(status['integrations']['ai_analysis'])}</strong></p><p>Feishu：<strong>{html.escape(status['integrations']['feishu'])}</strong></p>")}
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
        run_status = self.get_run_status_payload()
        history = self.get_run_history_payload()["items"]
        profiles = "".join(f"<li>{html.escape(item)}</li>" for item in payload["profiles"]) or "<li>暂无 industry profile</li>"
        optional_company_paths = "".join(
            f"<li>{html.escape(item)}</li>" for item in payload["company_profile"]["optional_paths"]
        ) or "<li>暂无 company profile</li>"
        return f"""
        <section class="panel">
          <div class="panel-header"><h1>运行入口</h1></div>
          <p>{html.escape(payload['safety_notice'])}</p>
          <div class="grid">
            {self._card("默认选项", "<p>本地 HTML 报告：开启</p><p>AI 分析：关闭</p><p>Feishu 同步：关闭</p><p>附件下载：关闭</p><p>PDF / DOC 解析：关闭</p>")}
            {self._card("行业配置", f"<ul>{profiles}</ul><p>当前固定使用 design_consulting 作为安全默认 profile。</p>")}
            {self._card("企业画像", f"<p>状态：{html.escape(payload['company_profile']['status'])}</p><p>建议路径：{html.escape(payload['company_profile']['suggested_path'] or '未发现')}</p><ul>{optional_company_paths}</ul>")}
          </div>
        </section>
        <section class="panel">
          <div class="panel-header"><h2>运行一次本地扫描</h2></div>
          <p>固定命令如下，页面不会接受任何自定义命令或参数。</p>
          <pre id="recommended-command">{html.escape(run_status['command'])}</pre>
          <div class="button-row">
            <button class="button" id="run-local-scan-button" type="button" onclick="startLocalScan()">{'运行中…' if run_status['status'] == 'running' else '运行一次本地扫描'}</button>
            <button class="button secondary" type="button" onclick="copyCommand()">复制命令</button>
            <a class="button secondary" id="open-latest-link" href="/artifacts/report/latest" target="_blank" rel="noopener" {'style="display:none;"' if not run_status['report_exists'] else ''}>打开 latest.html</a>
            <a class="button secondary" href="/logs">查看日志</a>
          </div>
          <div id="run-error-banner" class="error-banner" {'style="display:none;"' if not run_status['error_message'] else ''}>{html.escape(run_status['error_message'])}</div>
        </section>
        <section class="grid">
          {self._card("本次运行状态", self._render_run_state_summary(run_status))}
          {self._card("运行历史", self._render_run_history(history))}
        </section>
        <section class="grid">
          {self._card("stdout 摘要", self._render_output_panel("run-stdout-tail", run_status["stdout_tail"]))}
          {self._card("stderr 摘要", self._render_output_panel("run-stderr-tail", run_status["stderr_tail"]))}
        </section>
        <script>
          async function refreshRunStatus() {{
            const response = await fetch("{payload['status_url']}", {{ cache: "no-store" }});
            if (!response.ok) {{
              throw new Error("status fetch failed");
            }}
            const data = await response.json();
            updateRunView(data);
            return data;
          }}

          async function refreshRunHistory() {{
            const response = await fetch("{payload['history_url']}", {{ cache: "no-store" }});
            if (!response.ok) {{
              return;
            }}
            const data = await response.json();
            updateRunHistory(data.items || []);
          }}

          function setText(id, value) {{
            const el = document.getElementById(id);
            if (el) {{
              el.textContent = value || "暂无";
            }}
          }}

          function setLines(id, lines, emptyText) {{
            const el = document.getElementById(id);
            if (!el) return;
            el.textContent = (lines && lines.length) ? lines.join("\\n") : emptyText;
          }}

          function updateRunView(data) {{
            const button = document.getElementById("run-local-scan-button");
            const openLink = document.getElementById("open-latest-link");
            const errorBanner = document.getElementById("run-error-banner");
            setText("run-status-value", data.status);
            setText("run-started-at", data.started_at || "暂无");
            setText("run-finished-at", data.finished_at || "暂无");
            setText("run-duration", data.duration_seconds === null ? "暂无" : String(data.duration_seconds) + " 秒");
            setText("run-returncode", data.returncode === null ? "暂无" : String(data.returncode));
            setText("run-success", data.success === null ? "暂无" : (data.success ? "是" : "否"));
            setText("run-report-path", data.report_path || "暂无");
            setText("run-report-exists", data.report_exists ? "是" : "否");
            setLines("run-stdout-tail", data.stdout_tail || [], "暂无 stdout 输出");
            setLines("run-stderr-tail", data.stderr_tail || [], "暂无 stderr 输出");
            if (button) {{
              const running = data.status === "running";
              button.disabled = running;
              button.textContent = running ? "运行中…" : "运行一次本地扫描";
            }}
            if (openLink) {{
              openLink.style.display = data.report_exists ? "inline-block" : "none";
            }}
            if (errorBanner) {{
              errorBanner.textContent = data.error_message || "";
              errorBanner.style.display = data.error_message ? "block" : "none";
            }}
          }}

          function updateRunHistory(items) {{
            const el = document.getElementById("run-history-list");
            if (!el) return;
            if (!items.length) {{
              el.innerHTML = "<li>暂无运行记录。</li>";
              return;
            }}
            el.innerHTML = items.map(function(item) {{
              const returnCode = item.returncode === null ? "暂无" : item.returncode;
              const duration = item.duration_seconds === null ? "暂无" : item.duration_seconds + " 秒";
              return "<li><strong>" + item.status + "</strong> | started_at=" + (item.started_at || "暂无") + " | returncode=" + returnCode + " | duration=" + duration + " | report_exists=" + (item.report_exists ? "是" : "否") + "</li>";
            }}).join("");
          }}

          async function startLocalScan() {{
            const button = document.getElementById("run-local-scan-button");
            if (button) {{
              button.disabled = true;
              button.textContent = "运行中…";
            }}
            try {{
              const response = await fetch("{payload['start_url']}", {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
              }});
              const data = await response.json();
              updateRunView(data);
              if (response.status === 409) {{
                throw new Error(data.error || "已有任务正在运行");
              }}
            }} catch (error) {{
              const errorBanner = document.getElementById("run-error-banner");
              if (errorBanner) {{
                errorBanner.textContent = error.message || "启动失败";
                errorBanner.style.display = "block";
              }}
            }} finally {{
              await refreshRunStatus().catch(function() {{}});
              await refreshRunHistory().catch(function() {{}});
            }}
          }}

          document.addEventListener("DOMContentLoaded", function () {{
            refreshRunStatus().catch(function() {{}});
            refreshRunHistory().catch(function() {{}});
            window.setInterval(function () {{
              refreshRunStatus().catch(function() {{}});
              refreshRunHistory().catch(function() {{}});
            }}, 3000);
          }});
        </script>
        """

    def _render_report_page(self) -> str:
        payload = self.get_report_payload()
        action = (
            '<a class="button" href="/artifacts/report/latest" target="_blank" rel="noopener">打开报告</a>'
            if payload["exists"]
            else '<a class="button secondary" href="/run">先执行本地扫描</a>'
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
        run_status = self.get_run_status_payload()
        file_items = "".join(f"<li>{html.escape(item)}</li>" for item in payload["files"]) or "<li>暂无日志文件。</li>"
        log_items = "".join(f"<li>{html.escape(line)}</li>" for line in payload["latest_lines"]) or "<li>暂无日志摘要。</li>"
        error_block = f"<p class='error'>{html.escape(payload['error'])}</p>" if payload["error"] else ""
        latest_run = (
            f"<p>状态：<strong>{html.escape(run_status['status'])}</strong></p>"
            f"<p>开始时间：{html.escape(run_status['started_at'] or '暂无')}</p>"
            f"<p>结束时间：{html.escape(run_status['finished_at'] or '暂无')}</p>"
            f"<p>return code：{html.escape(str(run_status['returncode']) if run_status['returncode'] is not None else '暂无')}</p>"
        )
        return f"""
        <section class="panel">
          <div class="panel-header"><h1>日志</h1></div>
          {error_block}
          <div class="grid">
            {self._card("本次运行记录", latest_run)}
            {self._card("日志文件", f"<ul>{file_items}</ul>")}
          </div>
        </section>
        <section class="panel">
          <div class="panel-header"><h2>最新日志摘要</h2></div>
          <ul class="log-list">{log_items}</ul>
        </section>
        """

    def _render_config_page(self) -> str:
        payload = self.get_config_status_payload()
        return f"""
        <section class="panel">
          <div class="panel-header"><h1>配置状态</h1></div>
          <div class="grid">
            {self._card("环境文件", f"<p>.env：<strong>{'存在' if payload['env_file_exists'] else '不存在'}</strong></p><p>.env.example：<strong>{'存在' if payload['env_example_exists'] else '不存在'}</strong></p>")}
            {self._card("Feishu", self._render_status_table(payload['feishu']))}
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
          <p>已支持与 Alpha 才与当前 adapter 有关；候选、计划研究、暂不建议仅用于来源知识库记录。</p>
          <p>本页不会新增、编辑、删除来源，也不会提供抓取按钮、Feishu 或 AI 操作。</p>
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

    def _render_run_state_summary(self, run_status: dict[str, Any]) -> str:
        return (
            '<div class="run-summary-grid">'
            f'<p>当前状态：<strong id="run-status-value">{html.escape(run_status["status"])}</strong></p>'
            f'<p>开始时间：<span id="run-started-at">{html.escape(run_status["started_at"] or "暂无")}</span></p>'
            f'<p>结束时间：<span id="run-finished-at">{html.escape(run_status["finished_at"] or "暂无")}</span></p>'
            f'<p>耗时：<span id="run-duration">{html.escape(str(run_status["duration_seconds"]) + " 秒" if run_status["duration_seconds"] is not None else "暂无")}</span></p>'
            f'<p>return code：<span id="run-returncode">{html.escape(str(run_status["returncode"]) if run_status["returncode"] is not None else "暂无")}</span></p>'
            f'<p>是否成功：<span id="run-success">{html.escape("是" if run_status["success"] else "否" if run_status["success"] is not None else "暂无")}</span></p>'
            f'<p>report path：<code id="run-report-path">{html.escape(run_status["report_path"] or "暂无")}</code></p>'
            f'<p>report exists：<span id="run-report-exists">{html.escape("是" if run_status["report_exists"] else "否")}</span></p>'
            "</div>"
        )

    def _render_run_history(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return '<ul id="run-history-list"><li>暂无运行记录。</li></ul>'
        rows = []
        for item in items:
            returncode = item["returncode"] if item["returncode"] is not None else "暂无"
            duration = f'{item["duration_seconds"]} 秒' if item["duration_seconds"] is not None else "暂无"
            rows.append(
                f"<li><strong>{html.escape(item['status'])}</strong> | started_at={html.escape(item['started_at'] or '暂无')} | returncode={html.escape(str(returncode))} | duration={html.escape(duration)} | report_exists={'是' if item['report_exists'] else '否'}</li>"
            )
        return f'<ul id="run-history-list">{"".join(rows)}</ul>'

    def _render_output_panel(self, element_id: str, lines: list[str]) -> str:
        text = "\n".join(lines) if lines else f"暂无 {'stdout' if 'stdout' in element_id else 'stderr'} 输出"
        return f"<pre id=\"{element_id}\">{html.escape(text)}</pre>"

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
      <p class="sidebar-note">Alpha 边界：本地单用户、本地单次扫描，不做多用户系统，不做后台调度，不默认触发 Feishu 或 AI。</p>
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
                payload = self.service.handle_api_request(method, parsed.path)
                status = HTTPStatus.ACCEPTED if (method == "POST" and parsed.path == "/api/run/local-scan") else HTTPStatus.OK
                self._send_json(payload, status=status)
                return
            if parsed.path == "/artifacts/report/latest":
                self._send_report_file()
                return
            if parsed.path == "/static/style.css":
                self._send_static_file(self.service.web_static_dir / "style.css", "text/css; charset=utf-8")
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
        except RunConflictError as exc:
            self._send_json(
                {
                    "error": str(exc),
                    **self.service.get_run_status_payload(),
                },
                status=HTTPStatus.CONFLICT,
            )
        except FileNotFoundError:
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
        except Exception as exc:  # pragma: no cover
            if parsed.path.startswith("/api/"):
                self._send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return
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
