# ADR: Production Migration Dry-run Package

## Status

Proposed

`dry_run_package_only=true`

`production_migration_executed=false`

`production_seed_executed=false`

`schema_files_modified=false`

Future production migration PR required.

## Context

- production migration PR admission card exists
- formal migration proposal exists
- cutover readiness matrix exists
- isolated dry-apply exists
- rollback / restore rehearsal exists

The current platform chain can assemble a review package for a later production
migration PR, but this ADR does not approve or execute that migration.

## Decision

- This ADR defines a dry-run package only.
- This PR does not execute production migration.
- This PR does not execute production seed.
- This PR does not modify `db/schema.sql`.
- This PR does not modify `db/postgres/001_init.sql`.
- This PR does not write production tables.
- Future production migration PR remains separately required.

## Dry-run Package Contents

- schema diff outline
- migration SQL draft outline
- operator checklist
- validation command matrix
- rollback checklist
- seed artifact checksum review checklist

## Schema Diff Outline

- compare current formal schema draft with current db schema files
- report intended target tables
- report deferred Phase 2/3 tables
- report no executable schema change in this PR

## Migration SQL Draft Outline

- SQL draft is proposal text only
- SQL is not executed
- SQL is not written to `db/postgres/001_init.sql`
- SQL is not written to `db/schema.sql`

## Operator Checklist

- confirm backup point
- confirm maintenance window
- confirm rollback owner
- confirm seed artifact checksum
- confirm post-migration verification queries
- confirm emergency stop condition

## Validation Command Matrix

- full validation suite
- docs governance
- file governance
- cutover readiness matrix
- seed artifact validation
- dry-apply rehearsal
- rollback/restore rehearsal

## Rollback Checklist

- backup point is named before any later migration PR
- restore path is named before any later migration PR
- rollback owner is named before any later migration PR
- verification queries are listed before any later migration PR
- emergency stop condition is listed before any later migration PR

## Seed Artifact Checksum Review

- seed artifact checksum must be reviewed before any later seed step
- checksum review is manual confirmation only in this PR
- this PR does not write seed artifact files
- this PR does not apply seed data

## Explicit Non-goals

- no production migration in this PR
- no production seed in this PR
- no schema file edits in this PR
- no production DB connection
- no public schema write
- no production table write
- no evaluation metric changes
- no business conclusion changes

## Consequences

- future production migration PR can be prepared with a concrete package
- production migration remains blocked until separate approved PR
