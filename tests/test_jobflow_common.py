from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "skills" / "jobflow" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from jobflow_common import (  # noqa: E402
    contacted_rows,
    due_rows,
    normalize_platform,
    normalize_row,
    normalize_status,
    platform_counts,
    validate_rows,
)


class JobFlowCommonTests(unittest.TestCase):
    def test_normalizes_platform_and_status_aliases(self) -> None:
        self.assertEqual(normalize_platform("BOSS直聘"), "BOSS")
        self.assertEqual(normalize_platform("猎聘"), "Liepin")
        self.assertEqual(normalize_status("已发简历"), "resume_sent")
        self.assertEqual(normalize_status("需用户处理"), "needs_user_action")

    def test_normalize_row_adds_stable_id_and_preserves_legacy_values(self) -> None:
        row = {
            "platform": "BOSS直聘",
            "job_title": "Example role",
            "company": "Example company",
            "status": "已打招呼",
            "last_action_at": "2026-08-09",
        }

        normalized = normalize_row(row)

        self.assertEqual(normalized["platform"], "BOSS")
        self.assertEqual(normalized["status"], "contacted")
        self.assertEqual(normalized["legacy_platform"], "BOSS直聘")
        self.assertEqual(normalized["legacy_status"], "已打招呼")
        self.assertTrue(normalized["job_id"].startswith("job-"))
        self.assertEqual(normalized["schema_version"], 2)

    def test_contact_counts_include_later_statuses_and_platform_aliases(self) -> None:
        rows = [
            {
                "platform": "BOSS直聘",
                "status": "已发简历",
                "last_action_at": "2026-08-09",
            },
            {
                "platform": "猎聘",
                "status": "已打招呼",
                "last_action_at": "2026-08-09",
            },
        ]

        contacted = contacted_rows(rows, "2026-08-09")

        self.assertEqual(len(contacted), 2)
        self.assertEqual(platform_counts(contacted), {"BOSS": 1, "Liepin": 1})

    def test_due_rows_ignore_terminal_records(self) -> None:
        rows = [
            {
                "status": "not_suitable",
                "next_follow_up_at": "2026-08-08",
            },
            {
                "status": "contacted",
                "next_follow_up_at": "2026-08-08",
            },
        ]

        due = due_rows(rows, "2026-08-09")

        self.assertEqual(len(due), 1)
        self.assertEqual(due[0]["status"], "contacted")

    def test_validate_rows_separates_warnings_from_errors(self) -> None:
        rows = [
            {
                "job_id": "job-1",
                "platform": "BOSS",
                "status": "custom_future_status",
            },
            {
                "job_id": "job-1",
                "platform": "BOSS",
                "status": "contacted",
            },
        ]

        result = validate_rows(rows)

        self.assertEqual(result["errors"], [])
        self.assertTrue(result["warnings"])
        self.assertIn("duplicate_job_id", {item["error"] for item in result["warnings"]})
        self.assertIn("unknown_status", {item["error"] for item in result["warnings"]})


if __name__ == "__main__":
    unittest.main()
