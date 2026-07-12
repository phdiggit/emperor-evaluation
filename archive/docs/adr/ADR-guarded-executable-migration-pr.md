# ADR: Guarded Executable Migration PR Proposal

## Status

Proposed / Guarded proposal only

## Context

- Production migration PR scaffold exists.
- A future executable migration PR still requires explicit user approval.
- This ADR defines the guard contract before any schema-changing PR.
- Live apply and seed apply work still require separate explicit opt-in.

## Decision

- Add a guarded executable migration PR proposal contract.
- Future schema-changing PR must be blocked unless explicit user approval is recorded outside this PR.
- This PR may render PR body templates and machine-readable guard reports only.
- This PR must not modify formal schema files or execute SQL.
- This PR keeps future live apply and seed apply out of scope.

## Non-goals

- No production migration execution.
- No production seed execution.
- No schema modification.
- No DB connection.
- No DSN access.
- No approval of production migration.
- No schema-change PR approval.
- No human sign-off forged.

## Required Flags

```text
guarded_executable_migration_pr_proposal_only=true
production_migration_approved=false
production_migration_executed=false
production_seed_executed=false
schema_change_pr_approved=false
schema_files_modified=false
migration_sql_executable_in_this_pr=false
sql_executed=false
production_db_connected=false
production_dsn_read=false
human_signoffs_recorded=false
ready_for_production_migration=false
future_schema_change_pr_requires_explicit_user_approval=true
future_live_apply_pr_required=true
```

## Guard Checklist

- proposal contract is present
- proposal report is machine-readable
- future PR body template is blocked-by-default
- explicit user approval required for future schema-changing PR
- human sign-off placeholders are named
- schema file modifications remain forbidden in this PR
- ready_for_production_migration remains false
- future live apply PR required

## Future PR Body Template Boundaries

- Required approvals must remain placeholders until a later approved PR.
- Future schema file modifications must list exact files changed.
- Rollback and restore plan remains placeholder only in this proposal PR.
- Any live apply or seed apply must move to a separate opt-in PR.

## Future Work

- A future schema-changing PR may modify db/schema.sql / db/postgres/001_init.sql only after explicit user approval.
- A future live apply / seed apply PR may run only after separate explicit opt-in and separate review.
- Future production verification may use neutral platform terms such as metric_records, metric_releases, and downstream_release_tables.
