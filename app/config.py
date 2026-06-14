from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT_DIR / "config"
DATA_DIR = ROOT_DIR / "data"
LOG_DIR = ROOT_DIR / "logs"
REPORT_DIR = ROOT_DIR / "reports"


@dataclass(frozen=True)
class FeishuEnvConfig:
    app_id: str
    app_secret: str
    bitable_url: str
    webhook_url: str
    bitable_app_token: str
    bitable_table_id: str
    bot_mode: str
    chat_id: str


def ensure_runtime_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)


def load_sources() -> list[dict[str, Any]]:
    with (CONFIG_DIR / "sources.json").open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_keywords() -> list[str]:
    path = CONFIG_DIR / "keywords.yaml"
    keywords: list[str] = []
    in_keywords = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line == "keywords:":
            in_keywords = True
            continue
        if in_keywords and line.startswith("- "):
            keywords.append(line[2:].strip())
    return keywords


def load_pilot_notice_ids(path: str | Path) -> list[str]:
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = ROOT_DIR / config_path
    with config_path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    notice_ids = payload.get("notice_ids") or []
    return [str(item).strip() for item in notice_ids if str(item).strip()]


def load_feishu_env() -> FeishuEnvConfig:
    bot_mode = os.getenv("FEISHU_BOT_MODE", "webhook").strip().lower() or "webhook"
    return FeishuEnvConfig(
        app_id=os.getenv("FEISHU_APP_ID", "").strip(),
        app_secret=os.getenv("FEISHU_APP_SECRET", "").strip(),
        bitable_url=os.getenv("FEISHU_BITABLE_URL", "").strip(),
        webhook_url=os.getenv("FEISHU_WEBHOOK_URL", "").strip(),
        bitable_app_token=os.getenv("FEISHU_BITABLE_APP_TOKEN", "").strip(),
        bitable_table_id=os.getenv("FEISHU_BITABLE_TABLE_ID", "").strip(),
        bot_mode=bot_mode,
        chat_id=os.getenv("FEISHU_CHAT_ID", "").strip(),
    )
