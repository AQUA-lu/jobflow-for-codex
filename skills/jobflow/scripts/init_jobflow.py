from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path

from jobflow_common import job_search_dir, template_dir


def copy_template(name: str, dest: Path, force: bool) -> bool:
    source = template_dir() / name
    if dest.exists() and not force:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, dest)
    return True


def backup_existing(paths: list[Path], backup_dir: Path) -> list[Path]:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backups = []
    for path in paths:
        if not path.exists():
            continue
        backup = backup_dir / f"{path.name}.{timestamp}.bak"
        shutil.copyfile(path, backup)
        backups.append(backup)
    return backups


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize a private JobFlow workspace.")
    parser.add_argument("--workspace", default=".", help="Workspace root.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing JobFlow files.")
    parser.add_argument(
        "--backup-dir",
        default="",
        help="Required with --force when files already exist; stores backups before overwrite.",
    )
    args = parser.parse_args()

    root = job_search_dir(args.workspace)
    root.mkdir(parents=True, exist_ok=True)
    (root / "reports").mkdir(exist_ok=True)

    created = []
    skipped = []
    mappings = {
        "user_profile.example.yaml": root / "user_profile.yaml",
        "screening_rules.md": root / "screening_rules.md",
        "applications.example.jsonl": root / "applications.example.jsonl",
        "automation_prompt.md": root / "automation_prompt.md",
        "daily_report.md": root / "reports" / "daily_report.template.md",
    }

    ledger = root / "applications.jsonl"
    existing_paths = list(mappings.values()) + [ledger]
    if args.force and any(path.exists() for path in existing_paths) and not args.backup_dir:
        parser.error("--force requires --backup-dir when JobFlow files already exist")
    if args.force and args.backup_dir:
        backups = backup_existing(existing_paths, Path(args.backup_dir).expanduser().resolve())
        for path in backups:
            print(f"backup: {path}")

    for template, dest in mappings.items():
        if copy_template(template, dest, args.force):
            created.append(str(dest))
        else:
            skipped.append(str(dest))

    if ledger.exists() and not args.force:
        skipped.append(str(ledger))
    else:
        ledger.write_text("", encoding="utf-8")
        created.append(str(ledger))

    print("JobFlow workspace initialized")
    print(f"workspace: {Path(args.workspace).expanduser().resolve()}")
    print(f"data_dir: {root}")
    print(f"created: {len(created)}")
    for path in created:
        print(f"  + {path}")
    if skipped:
        print(f"skipped_existing: {len(skipped)}")
        for path in skipped:
            print(f"  = {path}")


if __name__ == "__main__":
    main()
