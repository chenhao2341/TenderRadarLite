from __future__ import annotations

import unittest
from unittest import mock

from app.adapters.base import BaseAdapter
from app.adapters.registry import build_adapter, resolve_adapter_class
from app.models import Notice, RawNotice, RawNoticeDetail


class _StructuredAdapter(BaseAdapter):
    def fetch_list(self) -> list[RawNotice]:
        return [
            RawNotice(
                source_id="demo",
                source_name="Demo Source",
                source_type="demo-type",
                raw_id="raw-1",
                title="Demo Notice",
                url="https://example.com/demo",
                publish_time="2026-06-15 10:00:00",
                raw_payload={"id": "raw-1"},
            )
        ]

    def fetch_detail(self, item: RawNotice) -> RawNoticeDetail:
        return RawNoticeDetail(
            source_id=item.source_id,
            raw_id=item.raw_id,
            detail_url=item.url,
            content_text="normalized content",
            raw_payload={"detail": True},
            attachments=[{"name": "attachment.pdf"}],
            extracted_fields={"project_name": "Demo Project"},
        )

    def normalize(self, item: RawNotice, detail: RawNoticeDetail | None = None) -> Notice:
        return Notice(
            source=item.source_name,
            source_subtype=item.source_type,
            dedupe_key="",
            section_id=item.raw_id,
            project_name=str((detail or RawNoticeDetail(source_id=item.source_id)).extracted_fields.get("project_name", item.title)),
            notice_id=item.raw_id,
            notice_title=item.title,
            publish_time=item.publish_time,
            original_url=item.url,
            content_summary=(detail.content_text if detail else ""),
            fetched_at="2026-06-15 12:00:00",
            employee_readable_url=item.url,
        )


class AdapterFrameworkTests(unittest.TestCase):
    def test_raw_notice_models_can_be_created(self) -> None:
        raw_notice = RawNotice(
            source_id="source-1",
            source_name="Source One",
            source_type="construction",
            raw_id="raw-1",
            title="Title",
            url="https://example.com/1",
            publish_time="2026-06-15 10:00:00",
            raw_payload={"a": 1},
        )
        raw_detail = RawNoticeDetail(
            source_id="source-1",
            raw_id="raw-1",
            detail_url="https://example.com/detail/1",
            content_text="content",
            raw_payload={"detail": True},
            attachments=[{"name": "file.pdf"}],
            extracted_fields={"budget_amount": "1000"},
        )

        self.assertEqual(raw_notice.source_id, "source-1")
        self.assertEqual(raw_detail.attachments[0]["name"], "file.pdf")
        self.assertEqual(raw_detail.extracted_fields["budget_amount"], "1000")

    def test_base_adapter_crawl_supports_structured_pipeline(self) -> None:
        adapter = _StructuredAdapter(
            source_name="Demo Source",
            url="https://example.com/list",
            region="Hengyang",
            fetcher=mock.Mock(),
            source_config={"name": "demo", "source_type": "construction"},
        )

        notices = adapter.crawl()

        self.assertEqual(len(notices), 1)
        self.assertIsInstance(notices[0], Notice)
        self.assertEqual(notices[0].notice_id, "raw-1")
        self.assertEqual(notices[0].content_summary, "normalized content")

    def test_registry_builds_existing_adapter_from_module_and_class(self) -> None:
        source = {
            "name": "Hengyang Construction",
            "module": "app.adapters.hengyang_construction",
            "class": "HengyangConstructionAdapter",
            "url": "https://example.com/list",
            "region": "Hengyang",
            "source": "source",
            "source_subtype": "construction",
        }

        adapter_class = resolve_adapter_class(source)
        adapter = build_adapter(source, mock.Mock())

        self.assertEqual(adapter_class.__name__, "HengyangConstructionAdapter")
        self.assertIsInstance(adapter, adapter_class)

    def test_runner_build_adapter_delegates_to_registry(self) -> None:
        from app.fetcher import Fetcher
        from app.runner import _build_adapter

        source = {
            "name": "Hengyang Construction",
            "module": "app.adapters.hengyang_construction",
            "class": "HengyangConstructionAdapter",
            "url": "https://example.com/list",
            "region": "Hengyang",
            "source": "source",
            "source_subtype": "construction",
        }

        adapter = _build_adapter(source, mock.create_autospec(Fetcher, instance=True))
        self.assertEqual(type(adapter).__name__, "HengyangConstructionAdapter")


if __name__ == "__main__":
    unittest.main()
