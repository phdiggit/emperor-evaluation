# PostgreSQL schema contract

`001_init.sql` is retained as a historical/future PostgreSQL schema contract for the emperor-evaluation source-data platform. After #354, the active product workflow no longer has tracked `scripts/platform/` or `scripts/source_ingest/` entrypoints.

## Current Status

- Current product workflow remains JSONL -> SQLite cache -> Markdown/export views.
- Canonical business facts remain in `data/*.jsonl`.
- PostgreSQL is not the unique business write source.
- No production runtime, worker, outbox dispatcher, RabbitMQ integration, or source-ingest runner is active in this repository.
- CI and local development do not require PostgreSQL.

## How To Read This Directory

`001_init.sql` and `bench_search.sql` are schema/reference artifacts only. They are useful when reviewing historical PostgreSQL platform decisions or drafting a future, separately approved product migration, but they are not current runnable workflow entrypoints.

The old platform helper commands such as `postgres_bootstrap.py`, `jsonl_import_dry_run.py`, `jsonl_target_mapping.py`, `g3_*`, `g4_*`, `g5_*`, `g6_*`, `g10_*`, and `post_g10_*` were removed by #354. Git history is the restore mechanism if a future approved task needs to examine or revive a deleted prototype.

## Safety Boundary

Do not infer production readiness from this schema directory. A future PostgreSQL migration would need a new issue, explicit approval, a current implementation plan, fresh validation, and a new PR. Until then, use the existing product workflow:

```bash
python scripts/build/build_db.py
python scripts/export/export_md.py --list-profiles
python scripts/validate/validate_all.py
```
