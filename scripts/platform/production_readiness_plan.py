from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import platform_chain_checkpoint


PLAN_VERSION = "production-readiness-plan-v1"
ADR_FILES = (
    "docs/adr/ADR-postgres-formal-migration-plan.md",
    "docs/adr/ADR-jsonl-to-target-cutover-plan.md",
    "docs/adr/ADR-platform-rollback-backup-seed-strategy.md",
)
FORMAL_MIGRATION_PRECONDITIONS = (
    "all contract reports green",
    "apply smoke matrix green with live primary PostgreSQL DSN",
    "schema diff reviewed",
    "rollback plan accepted",
    "seed strategy accepted",
    "read path dual-run accepted",
    "manual review gates for relationship tables accepted",
)
CUTOVER_PHASES = (
    "Phase 0: contract/prototype smoke only",
    "Phase 1: formal schema staging seed, JSONL remains write source",
    "Phase 2: dual-read verification, no production write switch",
    "Phase 3: target read path can be enabled behind explicit config",
    "Phase 4: write source switch requires separate approval",
)
ROLLBACK_STRATEGY = (
    "rollback by dropping isolated/proposed schema",
    "rollback by restoring pre-migration DB snapshot",
    "rollback by reverting config flags",
    "rollback by reverting PR / commit",
    "manual verification after rollback",
)
BACKUP_STRATEGY = (
    "pre-migration repo state",
    "pre-migration DB snapshot",
    "seed artifact checksum",
    "migration report artifact",
    "schema version marker",
)
SEED_STRATEGY = (
    "seed generated from canonical JSONL only",
    "seed artifacts are derived",
    "seed does not replace JSONL",
    "seed must be reproducible",
    "seed must not include secrets",
)
VALIDATION_GATES = (
    "production readiness contract report",
    "platform chain checkpoint contract report",
    "platform prototype smoke contract matrix",
    "anchors resolver contract report",
    "anchors target mapper contract report",
    "evidence clusters resolver contract report",
    "evidence cards target mapper contract report",
    "sources target mapper contract report",
    "query search target mapper contract report",
    "staging resolver contract report",
    "unknown field triage contract report",
    "staging mapper contract report",
    "docs registry check",
    "agents check",
    "canonical imports check",
    "validate all",
    "diff check",
    "scope check",
)
NON_GOALS = (
    "does not switch the JSONL write source",
    "does not generate formal seed artifacts",
    "does not modify the app read path",
    "does not modify metric or adjudication logic",
    "does not write formal schema",
    "does not write target business tables",
)
STRICT_BOUNDARIES = (
    "does_not_read_dotenv",
    "does_not_read_dsn",
    "does_not_connect_to_database",
    "does_not_read_data_batches_or_archive_data",
    "does_not_modify_canonical_jsonl",
    "does_not_modify_db_schema_sql",
    "does_not_modify_postgres_init_sql",
    "does_not_write_target_business_tables",
    "does_not_switch_jsonl_write_source",
    "does_not_generate_seed_artifact",
    "does_not_run_backup_or_restore",
)
FUTURE_WORK = (
    "formal schema draft batch",
    "isolated DDL proposal report",
    "schema diff report",
    "table by table gate",
    "seed checksum report",
    "dual-read fixture report",
    "relationship manual-review gates",
    "downstream_release_tables later",
    "metric_release_tables later",
)
LIMITATIONS = (
    "proposal_only",
    "offline_contract_report_only",
    "does_not_read_dotenv",
    "does_not_read_dsn",
    "does_not_connect_to_database",
    "does_not_read_batch_or_archive_inputs",
    "does_not_generate_business_conclusions",
)
BLOCKED_REPORT_TERMS = ("score", "rank", "final_score", "leaderboard")


def build_contract_report() -> dict[str, Any]:
    return {
        "mode": "contract-report",
        "plan_version": PLAN_VERSION,
        "status": "Proposed",
        "adr_files": list(ADR_FILES),
        "completed_platform_chain": list(platform_chain_checkpoint.COMPLETED_CHAIN),
        "formal_migration_preconditions": list(FORMAL_MIGRATION_PRECONDITIONS),
        "cutover_phases": list(CUTOVER_PHASES),
        "rollback_strategy": list(ROLLBACK_STRATEGY),
        "backup_strategy": list(BACKUP_STRATEGY),
        "seed_strategy": list(SEED_STRATEGY),
        "validation_gates": list(VALIDATION_GATES),
        "non_goals": list(NON_GOALS),
        "strict_boundaries": list(STRICT_BOUNDARIES),
        "future_work": list(FUTURE_WORK),
        "limitations": list(LIMITATIONS),
    }


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Report production-readiness proposal contracts.")
    parser.add_argument("--contract-report", action="store_true", help="print the proposal contract report")
    args = parser.parse_args(argv)
    if not args.contract_report:
        parser.error("--contract-report is required")

    sys.stdout.write(report_as_json(build_contract_report()))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
