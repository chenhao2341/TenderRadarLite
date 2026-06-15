from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import ROOT_DIR


DEFAULT_PROFILE_ID = "design_consulting"
PROFILES_DIR = ROOT_DIR / "profiles"


class ProfileNotFoundError(ValueError):
    pass


def available_profile_ids() -> list[str]:
    if not PROFILES_DIR.exists():
        return []
    return sorted(path.stem for path in PROFILES_DIR.glob("*.json") if path.is_file())


def load_profile(profile_id: str | None = None) -> dict[str, Any]:
    resolved_profile_id = (profile_id or DEFAULT_PROFILE_ID).strip() or DEFAULT_PROFILE_ID
    path = PROFILES_DIR / f"{resolved_profile_id}.json"
    if not path.exists():
        available = ", ".join(available_profile_ids()) or "none"
        raise ProfileNotFoundError(
            f"Profile '{resolved_profile_id}' not found. Available profiles: {available}"
        )

    payload = json.loads(path.read_text(encoding="utf-8"))
    _validate_profile_payload(path, payload)
    return payload


def _validate_profile_payload(path: Path, payload: dict[str, Any]) -> None:
    required_fields = [
        "profile_id",
        "name",
        "description",
        "positive_keywords",
        "negative_keywords",
        "strong_positive_keywords",
        "exclude_keywords",
        "notice_type_weights",
    ]
    missing = [field for field in required_fields if field not in payload]
    if missing:
        raise ValueError(f"Profile file '{path.name}' is missing required fields: {', '.join(missing)}")

