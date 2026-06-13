from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT_DIR / "config"
DATA_DIR = ROOT_DIR / "data"
LOG_DIR = ROOT_DIR / "logs"
REPORT_DIR = ROOT_DIR / "reports"


def ensure_runtime_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)


def load_sources() -> List[Dict[str, Any]]:
    with (CONFIG_DIR / "sources.json").open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_keywords() -> List[str]:
    path = CONFIG_DIR / "keywords.yaml"
    keywords: List[str] = []
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


def load_pilot_notice_ids(path: str | Path) -> List[str]:
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = ROOT_DIR / config_path
    with config_path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    notice_ids = payload.get("notice_ids") or []
    return [str(item).strip() for item in notice_ids if str(item).strip()]
