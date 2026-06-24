from __future__ import annotations

import unittest

from app.source_catalog import find_source_by_id, load_source_catalog
from app.source_quality import build_source_quality_matrix


class SourceQualityMatrixTests(unittest.TestCase):
    def test_matrix_covers_all_implemented_sources(self) -> None:
        rows = build_source_quality_matrix()
        implemented_rows = [row for row in rows if row["status"] in {"supported", "alpha"}]

        self.assertEqual(len(implemented_rows), 5)
        by_id = {row["source_key"]: row for row in rows}
        self.assertEqual(by_id["zhejiang-government-procurement"]["source_type_hint"], "json_portal_flow")
        self.assertEqual(by_id["china-government-procurement-local"]["source_type_hint"], "html_list_detail")
        self.assertEqual(by_id["hengyang-procurement"]["source_type_hint"], "json_api")
        self.assertEqual(by_id["changsha-procurement"]["source_type_hint"], "json_api")
        self.assertEqual(by_id["hengyang-construction"]["source_type_hint"], "html_list_detail")

    def test_matrix_preserves_default_enablement_and_runtime_boundaries(self) -> None:
        rows = build_source_quality_matrix()
        by_id = {row["source_key"]: row for row in rows}

        self.assertTrue(by_id["hengyang-construction"]["default_enabled"])
        self.assertTrue(by_id["hengyang-procurement"]["default_enabled"])
        self.assertFalse(by_id["changsha-procurement"]["default_enabled"])
        self.assertFalse(by_id["china-government-procurement-local"]["default_enabled"])
        self.assertFalse(by_id["zhejiang-government-procurement"]["default_enabled"])
        self.assertEqual(by_id["enterprise-procurement-portals"]["recommended_usage"], "blocked")

    def test_matrix_uses_current_run_summary_for_observability(self) -> None:
        catalog = load_source_catalog()
        changsha = find_source_by_id(catalog, "changsha-procurement")
        rows = build_source_quality_matrix(
            catalog=catalog,
            current_run_summaries=[
                {
                    "source_name": "Changsha Procurement",
                    "fetched_count": 10,
                    "inserted_count": 1,
                    "duplicate_count": 9,
                    "error_count": 0,
                    "detail_success_count": 10,
                    "latest_site_publish_time": "2026-06-20 10:00:00",
                    "latest_db_publish_time": "2026-06-20 10:00:00",
                }
            ],
            report_generated_at="2026-06-20 12:00:00",
        )
        by_id = {row["source_key"]: row for row in rows}

        self.assertEqual(by_id["changsha-procurement"]["display_name"], changsha["name"])
        self.assertTrue(by_id["changsha-procurement"]["participated_in_latest_run"])
        self.assertEqual(by_id["changsha-procurement"]["dedupe_signal"], "suspected_realtime_update")
        self.assertEqual(by_id["changsha-procurement"]["detail_observation"], "detail_success")


if __name__ == "__main__":
    unittest.main()
