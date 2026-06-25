# ADR: Production Schema Live-Apply Execution Preflight

## Status

Proposed / Production schema live-apply execution preflight only

## Context

- #281 completed the formal schema file update.
- #282 added the live-apply entrypoint guard.
- #283 added the execution PR scaffold.
- This PR adds the final offline preflight package before a future live apply execution PR.
- This PR is not the live apply PR and does not approve execution.

## Decision

- Add a non-executing preflight package for production schema live-apply review.
- Read `db/schema.sql` and `db/postgres/001_init.sql` only for metadata fingerprints.
- Check schema byte identity, table-set consistency, and `anchors` table presence.
- Render operator evidence checklist markdown with placeholders only.
- Render a blocked-by-default future live apply PR body template.
- Render a lintable preflight JSON and gate report.
- Keep schema files read-only in this PR.

## Required Flags

```text
live_apply_execution_preflight_only=true
live_apply_pr_approved=false
live_apply_executed=false
sql_executed=false
production_db_connected=false
production_dsn_read=false
dsn_required_in_this_pr=false
production_seed_executed=false
seed_apply_executed=false
schema_files_modified=false
schema_files_read_only=true
schema_files_byte_identical_required=true
production_schema_hashes_rendered=true
operator_evidence_recorded=false
human_signoffs_recorded=false
ready_for_live_apply=false
ready_for_production_migration=false
future_live_apply_execution_pr_required=true
future_seed_apply_pr_required=true
```

This PR may also declare:

```text
future_live_apply_execution_pr_can_be_next=true
```

That flag only meant a later execution gate could follow after separate explicit approval. It did not mean this PR was approved, executed, or ready.

## Non-Goals

- No SQL execution.
- No DB connection.
- No DSN access.
- No production seed execution.
- No seed apply execution.
- No live apply execution.
- No public schema write.
- No human sign-off forgery.
- No live apply approval record.
- No production migration completion record.

## Preflight Outputs

- `--contract-report` prints the contract report.
- `--preflight-report` prints the preflight report.
- `--render-preflight-json` prints the preflight JSON.
- `--render-operator-evidence-checklist-md` prints operator evidence checklist markdown.
- `--render-future-live-apply-pr-body-template` prints a blocked-by-default future live apply PR body template.
- `--lint-preflight-report` prints the lint report.
- `--adr-check` runs the ADR check.

## Future Work Boundary

- The live apply execution gate has since been completed by #285.
- Seed/data import remains separate and is now governed by the Epic 1 target importer gate after the Epic 0 audit-scaffold boundary.
- Any future execution gate must define DSN handling, connection handling, exact apply process, operator evidence, rollback / restore evidence, transcript capture, and post-apply verification.
- This PR does not make `ready_for_live_apply` true.
- This PR does not make `ready_for_production_migration` true.

## Operator Boundary

- The operator evidence checklist is placeholder-only.
- The future PR body template is blocked by default.
- The preflight package does not record approval, sign-off, transcript, rollback evidence, restore evidence, or seed evidence.
- Human approval and operator evidence must be recorded in the separate future execution PR.

## Rejected Semantics

- Reject setting `live_apply_pr_approved` to `true`.
- Reject setting `live_apply_executed` to `true`.
- Reject setting `sql_executed` to `true`.
- Reject setting `production_db_connected` to `true`.
- Reject setting `production_dsn_read` to `true`.
- Reject setting `ready_for_live_apply` to `true`.
- Reject setting `ready_for_production_migration` to `true`.
- Reject claims that live apply is completed.
- Reject claims that seed apply is completed.
- Reject claims that production migration is completed.
