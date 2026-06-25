# ADR: Production Migration Freeze Checklist

## Status
Proposed

## Context

- Migration bundle review pack exists.
- Schema diff draft renderer exists.
- Migration SQL draft renderer exists.
- Production migration dry-run package exists.
- Production migration admission card exists.
- Formal migration proposal exists.
- Cutover readiness matrix exists.

## Decision

- This ADR defines a freeze checklist only.
- This PR does not approve production migration.
- This PR does not execute production migration.
- This PR does not execute production seed.
- This PR does not modify db/schema.sql.
- This PR does not modify db/postgres/001_init.sql.
- This PR does not connect to PostgreSQL.
- Future production migration PR remains separately required.
- `future production migration PR required`
- `production_migration_freeze_checklist_only=true`
- `production_migration_approved=false`
- `production_migration_executed=false`
- `production_seed_executed=false`
- `schema_files_modified=false`
- `sql_executed=false`
- `production_db_connected=false`
- `human_signoffs_recorded=false`
- `ready_for_production_migration=false`

## Freeze Inputs

- migration bundle review pack report
- schema diff draft report
- migration SQL draft report
- dry-run package report
- admission report
- formal migration proposal report
- cutover readiness report
- rollback checklist
- operator checklist
- seed artifact checksum review
- human sign-off checklist

## Freeze Gate Categories

- source report gates
- schema/file immutability gates
- production action false-flag gates
- validation command gates
- human sign-off gates
- rollback readiness gates
- seed checksum gates

## Human Freeze Checklist

- schema reviewer sign-off required
- source-of-truth reviewer sign-off required
- seed checksum reviewer sign-off required
- rollback owner sign-off required
- operator sign-off required
- final maintainer sign-off required

## Freeze Boundaries

- Freeze checklist is stdout / in-memory JSON only by default.
- Freeze checklist is not written to data paths.
- Freeze checklist is not written to business exports paths.
- Freeze checklist is not a migration artifact.
- Freeze checklist does not approve production migration.
- Freeze checklist does not imply production readiness by itself.
- Future production migration PR remains separately required.

## Explicit Non-goals

- no production migration in this PR
- no production seed in this PR
- no db/schema.sql edit
- no db/postgres/001_init.sql edit
- no schema file edits in this PR
- no production DB connection
- no SQL execution
- no evaluation metric, ordering, or business conclusion changes

## Consequences

- Future production migration PR scaffold can reference a freeze checklist.
- Executable schema change still requires separate approved PR.
