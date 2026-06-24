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
        self.assertEqual(len(catalog["sources"]), 20)

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

        self.assertEqual(len(grouped["supported"]), 2)
        self.assertEqual(len(grouped["alpha"]), 3)
        self.assertEqual(len(grouped["candidate"]), 5)
        self.assertEqual(len(grouped["planned"]), 6)
        self.assertEqual(len(grouped["blocked"]), 4)
        supported_ids = {item["id"] for item in list_sources(catalog, status="supported")}
        self.assertEqual(supported_ids, {"hengyang-construction", "hengyang-procurement"})
        self.assertEqual(find_source_by_id(catalog, "china-government-procurement")["status"], "candidate")
        self.assertEqual(find_source_by_id(catalog, "changsha-procurement")["status"], "alpha")
        self.assertEqual(find_source_by_id(catalog, "china-government-procurement-local")["status"], "alpha")
        self.assertEqual(find_source_by_id(catalog, "zhejiang-government-procurement")["status"], "alpha")

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
                "total": 20,
                "by_status": {
                    "supported": 2,
                    "alpha": 3,
                    "candidate": 5,
                    "planned": 6,
                    "blocked": 4,
                },
            },
        )

    def test_procurement_source_is_now_supported_native_source(self) -> None:
        catalog = load_source_catalog()
        procurement = find_source_by_id(catalog, "hengyang-procurement")

        self.assertIsNotNone(procurement)
        self.assertEqual(procurement["status"], "supported")
        self.assertEqual(procurement["adapter"], "app.adapters.hengyang_procurement")
        self.assertEqual(procurement["source_from"], "native")

    def test_supported_and_alpha_sources_expose_runtime_source_mapping_fields(self) -> None:
        catalog = load_source_catalog()
        active_entries = {
            item["id"]: item
            for item in catalog["sources"]
            if item["id"]
            in {
                "hengyang-construction",
                "hengyang-procurement",
                "changsha-procurement",
                "china-government-procurement-local",
                "zhejiang-government-procurement",
            }
        }

        self.assertEqual(active_entries["zhejiang-government-procurement"]["source"], "浙江政府采购网")
        self.assertEqual(active_entries["zhejiang-government-procurement"]["source_subtype"], "政府采购 / JSON门户流")
        self.assertEqual(active_entries["china-government-procurement-local"]["source_subtype"], "地方公告")

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

    def test_source_quality_fields_cover_supported_alpha_and_reference_samples(self) -> None:
        catalog = load_source_catalog()
        expected = {
            "hengyang-construction": ("supported", True, "html_list_detail"),
            "hengyang-procurement": ("supported", True, "json_api"),
            "changsha-procurement": ("alpha", False, "json_api"),
            "china-government-procurement-local": ("alpha", False, "html_list_detail"),
            "zhejiang-government-procurement": ("alpha", False, "json_portal_flow"),
            "chongqing-government-procurement": ("candidate", False, "spa_runtime_required"),
            "guangdong-government-procurement": ("planned", False, "spa_runtime_required"),
            "enterprise-procurement-portals": ("blocked", False, "anti_bot"),
        }

        for source_id, (status, default_enabled, source_type_hint) in expected.items():
            source = find_source_by_id(catalog, source_id)
            self.assertIsNotNone(source)
            self.assertEqual(source["status"], status)
            self.assertEqual(source["default_enabled"], default_enabled)
            self.assertEqual(source["source_type_hint"], source_type_hint)
            self.assertIn(source["recommended_usage"], {"default_supported", "manual_alpha_test", "probe_reference", "planned", "blocked"})
            self.assertIn(source["probe_reuse_value"], {"high", "medium", "low", "blocked"})

    def test_supported_and_alpha_default_enabled_boundary_is_preserved(self) -> None:
        catalog = load_source_catalog()
        supported = list_sources(catalog, status="supported")
        alpha = list_sources(catalog, status="alpha")

        self.assertTrue(all(item["default_enabled"] is True for item in supported))
        self.assertTrue(all(item["default_enabled"] is False for item in alpha))


if __name__ == "__main__":
    unittest.main()
