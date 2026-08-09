from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jobflow_common import normalize_row, read_jsonl


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate a JobFlow ledger to the v0.2 schema.")
    parser.add_argument("--ledger", required=True, help="Source applications.jsonl path.")
    parser.add_argument("--output", required=True, help="New migrated JSONL path.")
    parser.add_argument("--overwrite", action="store_true", help="Allow replacing an existing output file.")
    args = parser.parse_args()

    source = Path(args.ledger).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    if output.exists() and not args.overwrite:
        print(f"Output already exists: {output}; use --overwrite to replace it.", file=sys.stderr)
        return 2

    rows, errors = read_jsonl(source)
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
        return 1

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(normalize_row(row), ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")

    print(json.dumps({"ok": True, "source": str(source), "output": str(output), "rows": len(rows)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
