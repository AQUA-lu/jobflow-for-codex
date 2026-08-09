from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PROJECT_ROOT / "skills" / "jobflow" / "scripts"


def run_script(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


class JobFlowCliTests(unittest.TestCase):
    def test_init_creates_empty_ledger_and_keeps_example_separate(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            result = run_script("init_jobflow.py", "--workspace", workspace)
            ledger = Path(workspace) / "data" / "job_search" / "applications.jsonl"
            example = Path(workspace) / "data" / "job_search" / "applications.example.jsonl"
            profile = Path(workspace) / "data" / "job_search" / "user_profile.yaml"

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(ledger.read_text(encoding="utf-8"), "")
            self.assertTrue(example.exists())
            self.assertTrue(profile.exists())
            self.assertIn('display_name: "Your Name"', profile.read_text(encoding="utf-8"))

    def test_force_requires_backup_for_existing_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            first = run_script("init_jobflow.py", "--workspace", workspace)
            self.assertEqual(first.returncode, 0, first.stderr)
            ledger = Path(workspace) / "data" / "job_search" / "applications.jsonl"
            ledger.write_text("private sentinel\n", encoding="utf-8")

            result = run_script("init_jobflow.py", "--workspace", workspace, "--force")

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(ledger.read_text(encoding="utf-8"), "private sentinel\n")

    def test_migrate_normalizes_aliases_without_changing_source(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            source = Path(workspace) / "source.jsonl"
            output = Path(workspace) / "migrated.jsonl"
            source.write_text(
                json.dumps(
                    {
                        "platform": "猎聘",
                        "job_title": "Example role",
                        "company": "Example company",
                        "status": "已发简历",
                        "last_action_at": "2026-08-09",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            result = run_script(
                "migrate_ledger.py",
                "--ledger",
                str(source),
                "--output",
                str(output),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"platform": "猎聘"', source.read_text(encoding="utf-8"))
            migrated = json.loads(output.read_text(encoding="utf-8").strip())
            self.assertEqual(migrated["platform"], "Liepin")
            self.assertEqual(migrated["status"], "resume_sent")
            self.assertEqual(migrated["schema_version"], 2)

    def test_validate_returns_nonzero_for_missing_platform(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            ledger = Path(workspace) / "ledger.jsonl"
            ledger.write_text(json.dumps({"job_id": "job-1", "status": "contacted"}) + "\n", encoding="utf-8")

            result = run_script("validate_ledger.py", "--ledger", str(ledger))

            self.assertNotEqual(result.returncode, 0)
            self.assertIn('"ok": false', result.stdout)

    def test_validate_strict_rejects_duplicate_job_ids(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            ledger = Path(workspace) / "ledger.jsonl"
            rows = [
                {"job_id": "job-1", "platform": "BOSS", "status": "contacted"},
                {"job_id": "job-1", "platform": "BOSS", "status": "resume_sent"},
            ]
            ledger.write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )

            result = run_script("validate_ledger.py", "--ledger", str(ledger), "--strict")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("duplicate_job_id", result.stdout)

    def test_check_targets_counts_resume_sent_as_contacted(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            ledger = Path(workspace) / "ledger.jsonl"
            ledger.write_text(
                json.dumps(
                    {
                        "platform": "BOSS直聘",
                        "status": "已发简历",
                        "last_action_at": "2026-08-09",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            result = run_script(
                "check_targets.py",
                "--ledger",
                str(ledger),
                "--date",
                "2026-08-09",
                "--boss",
                "1",
                "--liepin",
                "0",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"ok": true', result.stdout)
            self.assertIn('"BOSS": 1', result.stdout)

    def test_daily_report_normalizes_platform_and_status_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            ledger = Path(workspace) / "ledger.jsonl"
            ledger.write_text(
                json.dumps(
                    {
                        "platform": "BOSS直聘",
                        "status": "已发简历",
                        "last_action_at": "2026-08-09",
                        "job_title": "Example role",
                        "company": "Example company",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            result = run_script(
                "summarize_day.py",
                "--ledger",
                str(ledger),
                "--date",
                "2026-08-09",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("- BOSS contacted: 1", result.stdout)
            self.assertIn("- Resumes sent: 1", result.stdout)
            self.assertIn("## Automation Health", result.stdout)

    def test_upsert_updates_by_job_id_without_duplicate_rows(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            ledger = Path(workspace) / "ledger.jsonl"
            record = Path(workspace) / "record.json"
            ledger.write_text(
                json.dumps(
                    {
                        "job_id": "job-1",
                        "platform": "BOSS",
                        "status": "contacted",
                        "notes": "keep this note",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            record.write_text(
                json.dumps(
                    {
                        "job_id": "job-1",
                        "platform": "BOSS直聘",
                        "status": "已发简历",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = run_script("upsert_ledger.py", "--ledger", str(ledger), "--record-file", str(record))

            self.assertEqual(result.returncode, 0, result.stderr)
            rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "resume_sent")
            self.assertEqual(rows[0]["notes"], "keep this note")


if __name__ == "__main__":
    unittest.main()
