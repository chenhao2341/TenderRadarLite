from __future__ import annotations

import json
import unittest

from app.source_catalog import (
    find_source_by_id,
    get_source_catalog_summary,
    group_sources_by_status,
    list_sources,
    load_source_catalog,
    validate_source_catalog,
)


class SourceCatalogTests(unittest.TestCase):
    def test_catalog_file_can_be_loaded_and_validated(self) -> None:
        catalog = load_source_catalog()

        self.assertEqual(validate_source_catalog(catalog), [])
        self.assertEqual(len(catalog["sources"]), 18)

    def test_every_source_id_is_unique(self) -> None:
        catalog = load_source_catalog()
        source_ids = [item["id"] for item in catalog["sources"]]

        self.assertEqual(len(source_ids), len(set(source_ids)))

    def test_status_source_type_and_risk_enums_are_valid(self) -> None:
        catalog = load_source_catalog()
        allowed_statuses = {"supported", "alpha", "candidate", "planned", "blocked"}
        allowed_source_types = {
            "government_procurement",
            "public_resource_trading",
            "industry_platform",
            "enterprise_procurement",
            "aggregator",
            "unknown",
        }
        allowed_attachment_values = {"yes", "no", "likely", "unknown"}
        allowed_risk_values = {"low", "medium", "high", "unknown"}
        allowed_login_values = {"no", "likely", "yes", "unknown"}
        allowed_quality_values = {"high", "medium", "low", "unknown"}

        for source in catalog["sources"]:
            self.assertIn(source["status"], allowed_statuses)
            self.assertIn(source["source_type"], allowed_source_types)
            self.assertIn(source["has_detail_page"], {"yes", "no", "unknown"})
            self.assertIn(source["has_attachments"], allowed_attachment_values)
            self.assertIn(source["access_risk"], allowed_risk_values)
            self.assertIn(source["anti_bot_risk"], allowed_risk_values)
            self.assertIn(source["login_requirement"], allowed_login_values)
            self.assertIn(source["data_quality"], allowed_quality_values)

    def test_supported_and_alpha_sources_have_adapter(self) -> None:
        catalog = load_source_catalog()

        adapter_sources = [item for item in catalog["sources"] if item["status"] in {"supported", "alpha"}]

        self.assertTrue(adapter_sources)
        self.assertTrue(all(item["adapter"] for item in adapter_sources))

    def test_candidate_planned_and_blocked_are_not_treated_as_supported(self) -> None:
        catalog = load_source_catalog()
        grouped = group_sources_by_status(catalog)

        self.assertEqual(len(grouped["candidate"]), 6)
        self.assertEqual(len(grouped["planned"]), 6)
        self.assertEqual(len(grouped["blocked"]), 4)
        self.assertEqual(list_sources(catalog, status="supported")[0]["name"], "衡阳分平台 / 建设工程交易")
        self.assertEqual(find_source_by_id(catalog, "china-government-procurement")["status"], "candidate")

    def test_github_reference_sources_cannot_be_marked_supported(self) -> None:
        catalog = load_source_catalog()

        invalid_supported = [
            item for item in catalog["sources"] if item["status"] == "supported" and item["source_from"] == "github_reference"
        ]

        self.assertEqual(invalid_supported, [])

    def test_summary_counts_are_correct(self) -> None:
        catalog = load_source_catalog()
        summary = get_source_catalog_summary(catalog)

        self.assertEqual(
            summary,
            {
                "total": 18,
                "by_status": {
                    "supported": 1,
                    "alpha": 1,
                    "candidate": 6,
                    "planned": 6,
                    "blocked": 4,
                },
            },
        )

    def test_summary_and_sources_do_not_leak_secret_like_fields(self) -> None:
        catalog = load_source_catalog()
        serialized = json.dumps(
            {
                "summary": get_source_catalog_summary(catalog),
                "sources": list_sources(catalog),
            },
            ensure_ascii=False,
        )

        self.assertNotIn("secret", serialized.lower())
        self.assertNotIn("webhook", serialized.lower())
        self.assertNotIn("api_key", serialized.lower())


if __name__ == "__main__":
    unittest.main()
