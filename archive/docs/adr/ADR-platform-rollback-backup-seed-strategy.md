# ADR: platform rollback, backup, and seed strategy

## Status

Proposed.

This ADR is a strategy proposal only. It is not accepted, finalized, or a backup, restore, seed, or migration execution.

## Context

The platform chain has enough offline contracts to plan formal migration readiness, but it must still protect the JSONL source boundary and production schema. A later migration needs a documented rollback, backup, seed, and verification strategy before any DDL or cutover step is attempted.

## Decision

Require rollback, backup, seed, and verification artifacts before a formal migration is approved. All seed artifacts remain derived from canonical JSONL and must not replace canonical JSONL.

## Backup Strategy

Required backup inputs for a later migration:

- pre-migration repo state;
- pre-migration DB snapshot;
- seed artifact checksum;
- migration report artifact;
- schema version marker.

This PR does not create any backup or snapshot.

## Seed Strategy

- seed generated from canonical JSONL only;
- seed artifacts are derived;
- seed does not replace JSONL;
- seed must be reproducible;
- seed must not include secrets.

Seed generation requires a later approved implementation and must produce verifiable artifacts without reading secrets into reports.

## Rollback Strategy

- rollback by dropping isolated/proposed schema;
- rollback by restoring pre-migration DB snapshot;
- rollback by reverting config flags;
- rollback by reverting PR / commit;
- manual verification after rollback.

Rollback steps must be rehearsed against isolated environments before production use.

## Verification Strategy

- Validate repo state and changed-file scope before migration.
- Validate schema diff and schema version marker.
- Validate seed checksum and migration report artifact.
- Validate dual-read behavior before read-path enablement.
- Validate fallback to JSONL after rollback.
- Validate that downstream release tables and metric release tables remain outside early phases.

## Failure Modes

- Formal DDL diverges from prototype report expectations.
- Seed artifacts are not reproducible from canonical JSONL.
- A config flag enables target reads before dual-run verification.
- Relationship tables are populated before manual-review gates.
- Rollback drops the wrong schema or misses a read-path flag.
- A report leaks secrets or connection details.

## Manual Runbook Outline

1. Confirm repo state, PR SHA, and schema proposal version.
2. Confirm pre-migration DB snapshot exists.
3. Confirm seed artifact checksum and migration report artifact.
4. Confirm schema version marker and schema diff review.
5. Run isolated migration rehearsal.
6. Run dual-read verification.
7. Enable read path behind explicit config only after approval.
8. Revert config flags or restore snapshot if rollback is required.
9. Confirm manual verification after rollback.

## Future Work

- Define seed artifact naming and checksum format.
- Define schema version marker format.
- Define migration report artifact schema.
- Define rollback rehearsal evidence.
- Define target read-path flag names in a later implementation PR.
