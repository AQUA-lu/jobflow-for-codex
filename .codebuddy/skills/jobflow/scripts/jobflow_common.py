from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


CANONICAL_PLATFORMS = {"BOSS", "Liepin"}
PLATFORM_ALIASES = {
    "boss": "BOSS",
    "boss直聘": "BOSS",
    "liepin": "Liepin",
    "猎聘": "Liepin",
}

CANONICAL_STATUSES = {
    "contacted",
    "resume_sent",
    "recruiter_replied",
    "interview_scheduled",
    "interviewed",
    "not_suitable",
    "rejected",
    "withdrawn",
    "offer",
    "no_response",
    "needs_user_action",
    "needs_review",
}

STATUS_ALIASES = {
    "已打招呼": "contacted",
    "contacted": "contacted",
    "已发简历": "resume_sent",
    "resume_sent": "resume_sent",
    "message_replied": "recruiter_replied",
    "recruiter_reply_handled": "recruiter_replied",
    "message_reviewed": "recruiter_replied",
    "read_no_reply_needed": "recruiter_replied",
    "interview_scheduled": "interview_scheduled",
    "interviewed": "interviewed",
    "不合适": "not_suitable",
    "不适合": "not_suitable",
    "not_suitable": "not_suitable",
    "unsuitable": "not_suitable",
    "rejected_by_recruiter": "not_suitable",
    "rejected": "rejected",
    "withdrawn": "withdrawn",
    "offer": "offer",
    "no_response": "no_response",
    "需要用户处理": "needs_user_action",
    "需用户处理": "needs_user_action",
    "needs_user_action": "needs_user_action",
    "needs_user_decision": "needs_user_action",
    "needs_attention": "needs_user_action",
    "contact_shared": "needs_user_action",
    "resume_exchange_pending": "needs_user_action",
    "待复核": "needs_review",
    "needs_review": "needs_review",
}

CONTACTED_STATUSES = {
    "contacted",
    "resume_sent",
    "recruiter_replied",
    "interview_scheduled",
    "interviewed",
    "not_suitable",
    "rejected",
    "withdrawn",
    "offer",
    "no_response",
    "needs_user_action",
}

TERMINAL_STATUSES = {"not_suitable", "rejected", "withdrawn", "offer", "no_response"}

REQUIRED_FIELDS = ["platform", "status"]
RECOMMENDED_FIELDS = [
    "platform",
    "job_title",
    "company",
    "recruiter",
    "location",
    "salary",
    "job_url",
    "status",
    "status_stage",
    "last_action_at",
    "last_reviewed_at",
    "next_follow_up_at",
    "source_slot",
    "notes",
]


def normalize_platform(value: Any) -> str:
    """Return the canonical platform name while leaving unknown values readable."""
    text = str(value or "").strip()
    return PLATFORM_ALIASES.get(text.casefold(), text)


def normalize_status(value: Any) -> str:
    """Return a canonical status when a known legacy alias is available."""
    text = str(value or "").strip()
    return STATUS_ALIASES.get(text.casefold(), text)


def stable_job_id(row: dict[str, Any]) -> str:
    """Create a deterministic, non-sensitive identifier from job identity fields."""
    identity = "|".join(
        [
            normalize_platform(row.get("platform")),
            str(row.get("job_url") or "").strip(),
            str(row.get("job_title") or "").strip(),
            str(row.get("company") or "").strip(),
            str(row.get("location") or "").strip(),
        ]
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return f"job-{digest}"


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize one record without dropping fields owned by a user's workflow."""
    normalized = dict(row)
    raw_platform = str(row.get("platform") or "").strip()
    raw_status = str(row.get("status") or "").strip()
    platform = normalize_platform(raw_platform)
    status = normalize_status(raw_status)

    if raw_platform and platform != raw_platform:
        normalized.setdefault("legacy_platform", raw_platform)
    if raw_status and status != raw_status:
        normalized.setdefault("legacy_status", raw_status)
    normalized["platform"] = platform
    normalized["status"] = status
    normalized.setdefault("job_id", stable_job_id(normalized))
    normalized["schema_version"] = 2

    if not normalized.get("contacted_at") and status in CONTACTED_STATUSES:
        normalized["contacted_at"] = normalized.get("last_action_at") or normalized.get("last_reviewed_at") or ""
    return normalized


def _contacted_day(row: dict[str, Any]) -> str:
    normalized = normalize_row(row)
    return iso_day(normalized.get("contacted_at")) or (
        iso_day(normalized.get("last_action_at")) if normalized["status"] in CONTACTED_STATUSES else ""
    )


def validate_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Validate portable v0.2 records, separating repairable warnings from errors."""
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    seen_ids: Counter[str] = Counter()
    seen_urls: Counter[str] = Counter()

    for index, row in enumerate(rows, start=1):
        normalized = normalize_row(row)
        for field in REQUIRED_FIELDS:
            if not str(normalized.get(field) or "").strip():
                errors.append({"line": index, "error": "missing_required_field", "field": field})

        status = normalized.get("status")
        if status and status not in CANONICAL_STATUSES:
            warnings.append({"line": index, "error": "unknown_status", "status": status})
        platform = normalized.get("platform")
        if platform and platform not in CANONICAL_PLATFORMS:
            warnings.append({"line": index, "error": "unknown_platform", "platform": platform})

        for field in ("last_action_at", "last_reviewed_at", "next_follow_up_at", "contacted_at"):
            value = str(normalized.get(field) or "").strip()
            if value:
                try:
                    parse_day(value[:10])
                except ValueError:
                    errors.append({"line": index, "error": "invalid_date", "field": field})

        for field in RECOMMENDED_FIELDS:
            if not str(row.get(field) or "").strip() and field not in REQUIRED_FIELDS:
                warnings.append({"line": index, "error": "missing_recommended_field", "field": field})

        job_id = str(normalized.get("job_id") or "").strip()
        if job_id:
            seen_ids[job_id] += 1
        url = str(row.get("job_url") or "").strip()
        if url:
            seen_urls[url] += 1

    warnings.extend(
        {"job_id": job_id, "count": count, "error": "duplicate_job_id"}
        for job_id, count in seen_ids.items()
        if count > 1
    )
    warnings.extend(
        {"job_url": url, "count": count, "error": "duplicate_job_url"}
        for url, count in seen_urls.items()
        if count > 1
    )
    return {"errors": errors, "warnings": warnings}


def job_search_dir(workspace: str | Path) -> Path:
    return Path(workspace).expanduser().resolve() / "data" / "job_search"


def skill_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def template_dir() -> Path:
    return skill_dir() / "templates"


def read_jsonl(path: str | Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ledger = Path(path).expanduser().resolve()
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    if not ledger.exists():
        return rows, [{"line": 0, "error": f"file not found: {ledger}"}]

    text = ledger.read_text(encoding="utf-8-sig")
    for index, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append({"line": index, "error": exc.msg})
            continue
        if not isinstance(value, dict):
            errors.append({"line": index, "error": "line is not a JSON object"})
            continue
        rows.append(value)
    return rows, errors


def write_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def iso_day(value: Any) -> str:
    text = str(value or "")
    return text[:10] if len(text) >= 10 else text


def parse_day(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def today_rows(rows: list[dict[str, Any]], day: str) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if iso_day(row.get("last_action_at")) == day
        or iso_day(row.get("last_reviewed_at")) == day
    ]


def contacted_rows(rows: list[dict[str, Any]], day: str) -> list[dict[str, Any]]:
    return [row for row in rows if _contacted_day(row) == day]


def due_rows(rows: list[dict[str, Any]], day: str) -> list[dict[str, Any]]:
    target = parse_day(day)
    due: list[dict[str, Any]] = []
    for row in rows:
        if normalize_status(row.get("status")) in TERMINAL_STATUSES:
            continue
        value = str(row.get("next_follow_up_at") or "").strip()
        if not value:
            continue
        try:
            if parse_day(value[:10]) <= target:
                due.append(row)
        except ValueError:
            continue
    return due


def platform_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(normalize_platform(row.get("platform")) or "unknown" for row in rows))


def add_common_ledger_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--ledger",
        default=None,
        help="Path to applications.jsonl. Defaults to <workspace>/data/job_search/applications.jsonl.",
    )
    parser.add_argument(
        "--workspace",
        default=".",
        help="Workspace root used when --ledger is omitted.",
    )


def resolve_ledger(args: argparse.Namespace) -> Path:
    if args.ledger:
        return Path(args.ledger).expanduser().resolve()
    return job_search_dir(args.workspace) / "applications.jsonl"
