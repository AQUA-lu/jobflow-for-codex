from __future__ import annotations

import argparse

from jobflow_common import (
    add_common_ledger_arg,
    read_jsonl,
    resolve_ledger,
    validate_rows,
    write_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a JobFlow applications JSONL ledger.")
    add_common_ledger_arg(parser)
    parser.add_argument("--strict", action="store_true", help="Treat warnings such as duplicates as validation failures.")
    args = parser.parse_args()

    ledger = resolve_ledger(args)
    rows, parse_errors = read_jsonl(ledger)
    validation = validate_rows(rows)
    duplicate_urls = [item for item in validation["warnings"] if item.get("error") == "duplicate_job_url"]
    duplicate_job_ids = [item for item in validation["warnings"] if item.get("error") == "duplicate_job_id"]
    result = {
        "ledger": str(ledger),
        "ok": not parse_errors and not validation["errors"] and (not args.strict or not validation["warnings"]),
        "rows": len(rows),
        "parse_errors": parse_errors,
        "validation_errors": validation["errors"],
        "warnings": validation["warnings"],
        "duplicate_urls": duplicate_urls,
        "duplicate_job_ids": duplicate_job_ids,
    }
    write_json(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
