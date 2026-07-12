# ADR: Production Migration PR Scaffold

## Status

Proposed / Scaffold only

## Context

- Previous migration-readiness chain exists.
- Production migration admission, dry-run package, draft renderers, review pack, and freeze checklist are already available.
- Freeze checklist exists, but it is not an execution approval.
- A future executable migration PR still needs explicit human approval.

## Decision

- Add a production migration PR scaffold contract.
- Scaffold must make non-execution status machine-readable.
- Scaffold must require human sign-off placeholders without recording fake sign-offs.
- Scaffold reports may render stdout and in-memory JSON only.
- Scaffold reports must keep production actions blocked until a later explicit approval PR.

## Non-goals

- No production migration execution.
- No production seed execution.
- No schema modification.
- No DB connection.
- No DSN access.
- No approval of production migration.
- No human sign-off forged.

## Required Flags

```text
production_migration_pr_scaffold_only=true
production_migration_approved=false
production_migration_executed=false
production_seed_executed=false
schema_files_modified=false
sql_executed=false
production_db_connected=false
human_signoffs_recorded=false
ready_for_production_migration=false
future_executable_migration_pr_required=true
```

## Scaffold Checklist

- scaffold contract is present
- scaffold report is machine-readable
- human sign-off placeholders are named
- risk checklist is named
- validation checklist is named
- forbidden production actions are named
- ready_for_production_migration remains false
- future executable migration PR required

## Human Sign-off Placeholders

- schema reviewer sign-off placeholder
- source-of-truth reviewer sign-off placeholder
- migration operator sign-off placeholder
- rollback owner sign-off placeholder
- seed reviewer sign-off placeholder
- final maintainer sign-off placeholder

## Forbidden Production Actions

- modify formal schema
- execute migration SQL
- execute production seed
- connect production DB
- read production DSN
- forge human sign-off

## Future Work

- Future executable migration PR may modify schema only after explicit user approval.
- Future seed/live apply PR may run only after explicit opt-in and separate review.
- Future production verification may use neutral platform terms such as metric_records, metric_releases, and downstream_release_tables.
