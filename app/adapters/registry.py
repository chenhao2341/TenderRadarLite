from __future__ import annotations

import importlib
from typing import Any


def resolve_adapter_class(source: dict[str, Any]):
    module_name = str(source["module"])
    class_name = str(source["class"])
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def build_adapter(source: dict[str, Any], fetcher: Any):
    adapter_class = resolve_adapter_class(source)
    return adapter_class(
        source_name=source["name"],
        url=source["url"],
        region=source["region"],
        fetcher=fetcher,
        source_config=source,
    )
