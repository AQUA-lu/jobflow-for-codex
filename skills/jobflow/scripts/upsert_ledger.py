from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from jobflow_common import normalize_row, read_jsonl, stable_job_id


def write_rows_atomically(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Append or update one normalized JobFlow ledger record.")
    parser.add_argument("--ledger", required=True, help="Path to applications.jsonl.")
    parser.add_argument("--record-file", required=True, help="Path to a JSON object containing one record.")
    args = parser.parse_args()

    ledger = Path(args.ledger).expanduser().resolve()
    record_file = Path(args.record_file).expanduser().resolve()
    rows, errors = read_jsonl(ledger) if ledger.exists() else ([], [])
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
        return 1

    try:
        value = json.loads(record_file.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Unable to read record file: {exc}", file=sys.stderr)
        return 1
    if not isinstance(value, dict):
        print("Record file must contain one JSON object.", file=sys.stderr)
        return 2

    incoming = normalize_row(value)
    incoming_id = incoming["job_id"]
    replaced = False
    output_rows: list[dict[str, Any]] = []
    for row in rows:
        row_id = str(row.get("job_id") or stable_job_id(row))
        if row_id == incoming_id and not replaced:
            output_rows.append(normalize_row({**row, **incoming}))
            replaced = True
        else:
            output_rows.append(row)
    if not replaced:
        output_rows.append(incoming)

    write_rows_atomically(ledger, output_rows)
    print(json.dumps({"ok": True, "action": "updated" if replaced else "appended", "job_id": incoming_id}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
