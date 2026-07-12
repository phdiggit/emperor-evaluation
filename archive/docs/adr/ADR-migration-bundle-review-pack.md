# ADR: Migration Bundle Review Pack

## Status
Proposed

## Context

- Schema diff draft renderer exists.
- Migration SQL draft renderer exists.
- Production migration dry-run package exists.
- Production migration admission card exists.
- Formal migration proposal exists.
- Cutover readiness matrix exists.

## Decision

- This ADR defines a review pack only.
- This PR does not execute production migration.
- This PR does not execute production seed.
- This PR does not modify db/schema.sql.
- This PR does not modify db/postgres/001_init.sql.
- This PR does not connect to PostgreSQL.
- Future production migration PR remains separately required.
- `future production migration PR required`
- `migration_bundle_review_only=true`
- `production_migration_executed=false`
- `production_seed_executed=false`
- `schema_files_modified=false`
- `sql_executed=false`
- `production_db_connected=false`

## Bundle Contents

- schema diff draft report
- migration SQL draft report
- dry-run package report
- admission report
- formal migration proposal report
- cutover readiness report
- operator checklist
- validation command matrix
- rollback checklist
- seed artifact checksum review
- human sign-off checklist
- risk register

## Review Pack Boundaries

- Review pack is stdout / in-memory JSON only by default.
- Review pack is not written to data paths.
- Review pack is not written to exports paths.
- Review pack is not a migration artifact.
- Review pack is not executable.
- Review pack does not imply production readiness.
- Future production migration PR remains separately required.

## Required Bundle Gates

- schema diff draft available
- migration SQL draft available
- SQL draft lint passed
- schema diff lint passed
- dry-run package available
- admission report available
- formal proposal available
- cutover readiness available
- all production flags remain false
- no blocked report terms

## Human Review Checklist

- schema reviewer sign-off
- source-of-truth reviewer sign-off
- seed checksum reviewer sign-off
- rollback owner sign-off
- operator sign-off
- final maintainer sign-off

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

- Future production migration PR can attach one coherent review pack.
- Executable schema change still requires separate approved PR.
