from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.web_console import DEFAULT_HOST, DEFAULT_PORT, run_web_console


def main() -> None:
    host = os.getenv("TENDERRADAR_WEB_HOST", DEFAULT_HOST)
    port = int(os.getenv("TENDERRADAR_WEB_PORT", str(DEFAULT_PORT)))
    run_web_console(host=host, port=port)


if __name__ == "__main__":
    main()
