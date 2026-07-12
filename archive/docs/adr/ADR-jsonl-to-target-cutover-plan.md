# ADR: JSONL-to-target cutover plan

## Status

Proposed.

This ADR is a cutover proposal only. It is not accepted, finalized, or a write-source switch.

## Context

The current platform chain can describe target mappings and resolver boundaries, but canonical JSONL remains the operational source. PostgreSQL target tables are still prototype or future formal-migration surfaces until a separate migration is accepted.

This ADR defines cutover stages that prevent target-table work from silently changing read paths, write paths, or business conclusions.

## Decision

Adopt a multi-phase cutover plan where JSONL remains authoritative until a separate approval explicitly changes the source boundary. PostgreSQL targets stay derived/prototype during proposal and staging phases.

## Current Source of Truth

- canonical JSONL remains source of truth.
- PostgreSQL target remains derived/prototype until separate accepted migration.

## Cutover Phases

- Phase 0: contract/prototype smoke only.
- Phase 1: formal schema staging seed, JSONL remains write source.
- Phase 2: dual-read verification, no production write switch.
- Phase 3: target read path can be enabled behind explicit config.
- Phase 4: write source switch requires separate approval.

## Dual-Run Strategy

- Compare JSONL-derived reads and target-derived reads with explicit fixtures.
- Keep target reads behind configuration until review gates pass.
- Record mismatches as cutover blockers, not automatic target-table fixes.
- Keep relationship outputs out of dual-run success until manual-review gates are defined.

## Read Path Strategy

- Default reads continue to use canonical JSONL and existing generated views.
- Target reads can be exercised only through explicit configuration in a later stage.
- Any target read path must provide a clear fallback to JSONL.
- Read-path enablement must be reversible without data mutation.

## Write Path Strategy

- JSONL remains the write source through phases 0, 1, 2, and 3.
- Target-table writes in prototype tools remain isolated and opt-in.
- A production write-source switch requires a separate approval, separate PR, and rollback plan.
- No application writer changes are included in this proposal.

## Verification Gates

- Contract reports remain green for every mapper and resolver in the current platform chain.
- Prototype smoke contract matrix remains green offline.
- Formal schema diff is reviewed before any DDL is applied.
- Seed artifacts are reproducible from canonical JSONL only.
- Rollback, backup, and seed strategy are accepted before read-path enablement.
- Manual-review gates are accepted before relationship-table use.

## Non-Goals

- This PR does not switch the write source.
- This PR does not generate formal seed artifacts.
- This PR does not modify the app read path.
- This PR does not modify metric or adjudication logic.
- This PR does not write formal schema.

## Future Work

- Add dual-read fixtures after formal schema draft review.
- Add config-flag runbooks for target read enablement and rollback.
- Add seed checksum reporting.
- Add relationship resolver review output contracts.
