# JobFlow Ledger Schema v0.2

`applications.jsonl` is a local, user-owned file. It must stay outside the public repository.

## Required fields

- `platform`: canonical platform name such as `BOSS` or `Liepin`.
- `status`: canonical workflow status.

The migration tool also adds:

- `job_id`: deterministic identifier beginning with `job-`.
- `schema_version`: `2`.
- `contacted_at`: the first known contact timestamp when it can be inferred safely.

## Recommended fields

`job_title`, `company`, `recruiter`, `location`, `salary`, `job_url`, `status_stage`, `last_action_at`, `last_reviewed_at`, `next_follow_up_at`, `source_slot`, and `notes` are recommended but may be absent in older records.

## Compatibility

The migration keeps unknown fields and preserves changed legacy values in `legacy_platform` or `legacy_status`. Known aliases include:

- `BOSS直聘` -> `BOSS`
- `猎聘` -> `Liepin`
- `已打招呼` -> `contacted`
- `已发简历` -> `resume_sent`
- `不合适` -> `not_suitable`
- `需用户处理` -> `needs_user_action`

Unknown statuses and platforms become warnings. They are not silently deleted or rewritten.

## Migration and updates

Create a new migrated file, leaving the source untouched:

```text
python skills/jobflow/scripts/migrate_ledger.py \
  --ledger <private-workspace>/data/job_search/applications.jsonl \
  --output <private-workspace>/data/job_search/applications.v0.2.jsonl
```

Use `upsert_ledger.py` to append or update a record by `job_id`. The command writes atomically and only operates on the local path supplied by the user.
