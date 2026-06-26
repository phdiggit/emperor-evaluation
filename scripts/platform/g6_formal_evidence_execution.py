from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.env_loader import read_dotenv_values  # noqa: E402


EXECUTION_VERSION = "g6-formal-evidence-execution-v1"
APPROVAL_TOKEN = "USER_APPROVED_G6_FORMAL_EVIDENCE_RELEASE_ISSUE292"
G6_APPROVAL_REFERENCE = "https://github.com/phdiggit/emperor-evaluation/issues/292"
G6_BOUNDARY_SOURCE_PR = 303
G6_BOUNDARY_HEAD_SHA = "6d435eaa0cf374ea630e3f046426e03e5646da63"
G6_BOUNDARY_MERGE_COMMIT = "8f4a9adbbe4ce7da962731e3451fcfbf7d77c98b"
G5_EXECUTION_PLAN_SHA256 = "590b083e27e8d6f9b93c3742936ef043e17262abc041a0132d4bcf5364d0edbd"
G5_RUNTIME_IMPORT_CODE = "G5-RUNTIME-SMOKE-ISSUE292"
G6_FORMAL_EVIDENCE_IMPORT_CODE = "G6-FORMAL-EVIDENCE-RELEASE-ISSUE292"
G6_SOURCE_KIND = "formal_evidence_release"
G6_SOURCE_REF = "issue-292-g6"
DSN_ENV_NAME = "EMPEROR_EVAL_PG_DSN"
SUPPORTED_MODES = (
    "contract-report",
    "execution-plan-json",
    "operator-checklist-md",
    "execute",
    "observe",
)
BOUNDARIES = (
    "G6 is approved for formal evidence release marker execution and observation only.",
    "Default reports do not read .env, connect PostgreSQL, connect RabbitMQ, access network, or read canonical JSONL.",
    "Execute requires the G6 approval token, expected plan sha256, and operator DSN.",
    "Execute may write only a G6 imports audit marker after G5 runtime marker readback passes.",
    "No source, passage, evidence, cluster, anchor, relationship, scoring, ranking, or Epic 2 table is written.",
    "No formal scoring, score, ranking, scoring algorithm, destructive cleanup, or Epic 2 entry is released.",
)


def build_contract_report(*, source_root: Path = ROOT) -> dict[str, Any]:
    plan = render_execution_plan_json(source_root=source_root)
    return {
        "mode": "contract-report",
        "execution_version": EXECUTION_VERSION,
        "gate_status": "G6_APPROVED",
        "approval_token_required": True,
        "approval_token_value": APPROVAL_TOKEN,
        "supported_modes": list(SUPPORTED_MODES),
        "default_modes_side_effect_free": True,
        "default_modes_read_dotenv": False,
        "default_modes_connect_database": False,
        "default_modes_connect_rabbitmq": False,
        "default_modes_access_network": False,
        "default_modes_read_canonical_jsonl": False,
        "dsn_env_name": DSN_ENV_NAME,
        "g6_approval_reference": G6_APPROVAL_REFERENCE,
        "boundary_source_pr": G6_BOUNDARY_SOURCE_PR,
        "boundary_head_sha": G6_BOUNDARY_HEAD_SHA,
        "boundary_merge_commit": G6_BOUNDARY_MERGE_COMMIT,
        "execution_plan_sha256": plan["execution_plan_sha256"],
        "formal_evidence_marker": plan["formal_evidence_marker"],
        "execution_completed_by_this_report": False,
        "post_apply_observation_completed_by_this_report": False,
        "next_user_gate": "G7_REQUIRED_BEFORE_SCORING_RULE_CHANGE",
        "boundaries": list(BOUNDARIES),
    }


def render_execution_plan_json(*, source_root: Path = ROOT) -> dict[str, Any]:
    plan: dict[str, Any] = {
        "mode": "execution-plan-json",
        "execution_version": EXECUTION_VERSION,
        "gate_status": "G6_APPROVED",
        "g6_approval_reference": G6_APPROVAL_REFERENCE,
        "boundary_source_pr": G6_BOUNDARY_SOURCE_PR,
        "boundary_head_sha": G6_BOUNDARY_HEAD_SHA,
        "boundary_merge_commit": G6_BOUNDARY_MERGE_COMMIT,
        "g5_execution_plan_sha256": G5_EXECUTION_PLAN_SHA256,
        "preconditions": {
            "approval_token": APPROVAL_TOKEN,
            "expected_plan_sha256_required": True,
            "operator_dsn_required": DSN_ENV_NAME,
            "g5_runtime_marker_readback_required": G5_RUNTIME_IMPORT_CODE,
            "formal_evidence_candidate_workset_declared": formal_evidence_workset(),
        },
        "allowed_release_steps": [
            "g5_runtime_marker_readback",
            "formal_evidence_release_marker_upsert",
            "post_apply_observation_readback",
            "followup_checkpoint_update_after_observed_release_pr",
        ],
        "formal_evidence_marker": {
            "target_table": "imports",
            "code": G6_FORMAL_EVIDENCE_IMPORT_CODE,
            "source_kind": G6_SOURCE_KIND,
            "source_ref": G6_SOURCE_REF,
            "status": "succeeded",
            "row_count": 1,
            "input_hash_source": "execution_plan_sha256",
        },
        "execute_write": {
            "write_kind": "idempotent_imports_marker_upsert",
            "target_tables": ["imports"],
            "business_target_tables_written": [],
            "repository_files_written": [],
            "requires_g5_runtime_marker_to_pass": True,
        },
        "runtime_state_after_success": expected_formal_evidence_state(),
        "followup_gate_boundaries": {
            "source_passages_business_writes": "blocked_until_merge_policy_gate",
            "evidence_cluster_anchor_relationship_writes": "blocked_until_followup_business_table_gate",
            "scoring_rules": "blocked_until_g7",
            "scoring_algorithm": "blocked_until_g8",
            "formal_score_or_ranking_publication": "blocked_until_g9",
            "destructive_cleanup": "blocked_until_g10",
            "epic_2_entry": "blocked_until_separate_ready_review",
        },
        "rollback_point": {
            "database_data_deletion_allowed_by_this_plan": False,
            "formal_evidence_supersession_allowed_only_after_followup_approval": True,
            "action": "mark G6 formal evidence marker failed or superseded after explicit followup approval",
        },
        "boundaries": list(BOUNDARIES),
    }
    plan["execution_plan_sha256"] = stable_json_sha256(plan)
    return plan


def render_operator_checklist_md(*, source_root: Path = ROOT) -> str:
    plan = render_execution_plan_json(source_root=source_root)
    return "\n".join(
        [
            "# G6 Formal Evidence Execution Operator Checklist",
            "",
            "- Confirm G6 approval is recorded in Issue #292.",
            f"- Confirm execution plan sha256 is `{plan['execution_plan_sha256']}`.",
            "- Confirm `EMPEROR_EVAL_PG_DSN` is set only in the operator environment.",
            "- Confirm G5 runtime marker readback still passes.",
            "- Run `--execute` with the G6 approval token and expected plan sha256.",
            "- Confirm observation reads back the G6 formal evidence release marker.",
            "- Do not publish scoring, scores, rankings, destructive cleanup, or enter Epic 2.",
            "",
        ]
    )


def execute_formal_evidence_release(
    *,
    approval_token: str | None,
    expected_plan_sha256: str | None,
    source_root: Path = ROOT,
) -> dict[str, Any]:
    plan = render_execution_plan_json(source_root=source_root)
    failures = pre_execution_failures(approval_token, expected_plan_sha256, plan)
    if failures:
        return build_blocked_execution_report(plan, failures, failure_stage="gate", operator_config_read=False)

    config = read_operator_config()
    if not config.dsn:
        return build_blocked_execution_report(
            plan,
            ["blocked_missing_dsn"],
            failure_stage="operator_configuration",
            operator_config_read=True,
            operator_config_status=config.status_report(),
        )

    try:
        with connect_to_database(config.dsn) as conn:
            prerequisite = observe_g5_runtime_marker(conn, plan)
            if not prerequisite["observation_passed"]:
                return build_blocked_execution_report(
                    plan,
                    ["blocked_missing_or_invalid_g5_runtime_marker"],
                    failure_stage="g5_observation",
                    operator_config_read=True,
                    operator_config_status=config.status_report(),
                    g5_runtime_observation=prerequisite,
                )
            write_formal_evidence_marker(conn, plan, prerequisite)
            observation = observe_formal_evidence_state(conn, plan)
            conn.commit()
    except Exception as exc:  # pragma: no cover - adapter-specific.
        return {
            **base_execution_report(plan),
            "mode": "execute-report",
            "execution_status": "failed",
            "failure_stage": "database",
            "blocking_failures": ["database_error"],
            "operator_config_read": True,
            "operator_config_status": config.status_report(),
            "error": redact_secret(str(exc)),
            "formal_evidence_marker_written": False,
            "post_apply_observation": None,
            "post_apply_observation_completed": False,
            "g6_formal_evidence_executed": False,
            **unexecuted_formal_evidence_state(),
        }

    passed = observation["observation_passed"]
    return {
        **base_execution_report(plan),
        "mode": "execute-report",
        "execution_status": "succeeded" if passed else "failed_observation",
        "failure_stage": None if passed else "observation",
        "blocking_failures": [] if passed else ["post_apply_observation_failed"],
        "operator_config_read": True,
        "operator_config_status": config.status_report(),
        "formal_evidence_marker_written": True,
        "post_apply_observation": observation,
        "post_apply_observation_completed": True,
        "g6_formal_evidence_executed": passed,
        **(expected_formal_evidence_state() if passed else unexecuted_formal_evidence_state()),
    }


def observe_formal_evidence_release(
    *,
    approval_token: str | None,
    expected_plan_sha256: str | None,
    source_root: Path = ROOT,
) -> dict[str, Any]:
    plan = render_execution_plan_json(source_root=source_root)
    failures = pre_execution_failures(approval_token, expected_plan_sha256, plan)
    if failures:
        return build_blocked_execution_report(
            plan,
            failures,
            failure_stage="gate",
            operator_config_read=False,
            mode="observe-report",
        )
    config = read_operator_config()
    if not config.dsn:
        return build_blocked_execution_report(
            plan,
            ["blocked_missing_dsn"],
            failure_stage="operator_configuration",
            operator_config_read=True,
            operator_config_status=config.status_report(),
            mode="observe-report",
        )
    try:
        with connect_to_database(config.dsn) as conn:
            observation = observe_formal_evidence_state(conn, plan)
    except Exception as exc:  # pragma: no cover
        return {
            **base_execution_report(plan),
            "mode": "observe-report",
            "execution_status": "failed",
            "failure_stage": "database",
            "blocking_failures": ["database_error"],
            "operator_config_read": True,
            "operator_config_status": config.status_report(),
            "error": redact_secret(str(exc)),
            "post_apply_observation": None,
            "post_apply_observation_completed": False,
            "g6_formal_evidence_executed": False,
            **unexecuted_formal_evidence_state(),
        }
    passed = observation["observation_passed"]
    return {
        **base_execution_report(plan),
        "mode": "observe-report",
        "execution_status": "succeeded" if passed else "failed_observation",
        "failure_stage": None if passed else "observation",
        "blocking_failures": [] if passed else ["post_apply_observation_failed"],
        "operator_config_read": True,
        "operator_config_status": config.status_report(),
        "post_apply_observation": observation,
        "post_apply_observation_completed": True,
        "g6_formal_evidence_executed": False,
        **(expected_formal_evidence_state() if passed else unexecuted_formal_evidence_state()),
    }


def pre_execution_failures(
    approval_token: str | None,
    expected_plan_sha256: str | None,
    plan: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    if approval_token != APPROVAL_TOKEN:
        failures.append("blocked_missing_or_invalid_g6_approval_token")
        return failures
    if not expected_plan_sha256:
        failures.append("blocked_missing_expected_plan_sha256")
        return failures
    if expected_plan_sha256 != plan["execution_plan_sha256"]:
        failures.append("blocked_execution_plan_sha256_mismatch")
    return failures


def build_blocked_execution_report(
    plan: Mapping[str, Any],
    failures: Sequence[str],
    *,
    failure_stage: str,
    operator_config_read: bool,
    operator_config_status: Mapping[str, Any] | None = None,
    g5_runtime_observation: Mapping[str, Any] | None = None,
    mode: str = "execute-report",
) -> dict[str, Any]:
    return {
        **base_execution_report(plan),
        "mode": mode,
        "execution_status": "blocked",
        "failure_stage": failure_stage,
        "blocking_failures": list(failures),
        "operator_config_read": operator_config_read,
        "operator_config_status": dict(operator_config_status or {}),
        "g5_runtime_observation": g5_runtime_observation,
        "formal_evidence_marker_written": False,
        "post_apply_observation": None,
        "post_apply_observation_completed": False,
        "g6_formal_evidence_executed": False,
        **unexecuted_formal_evidence_state(),
    }


def base_execution_report(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "execution_version": EXECUTION_VERSION,
        "gate_status": "G6_APPROVED",
        "g6_approval_reference": G6_APPROVAL_REFERENCE,
        "boundary_source_pr": G6_BOUNDARY_SOURCE_PR,
        "boundary_head_sha": G6_BOUNDARY_HEAD_SHA,
        "boundary_merge_commit": G6_BOUNDARY_MERGE_COMMIT,
        "execution_plan_sha256": plan["execution_plan_sha256"],
        "formal_evidence_marker": plan["formal_evidence_marker"],
        "next_user_gate": "G7_REQUIRED_BEFORE_SCORING_RULE_CHANGE",
        "boundaries": list(BOUNDARIES),
    }


class OperatorConfig:
    def __init__(self, values: Mapping[str, str]) -> None:
        self.dsn = values.get(DSN_ENV_NAME)

    def status_report(self) -> dict[str, Any]:
        return {"dsn_present": bool(self.dsn)}


def read_operator_config(
    *,
    environ: Mapping[str, str] | None = None,
    env_path: Path = ROOT / ".env",
) -> OperatorConfig:
    if environ is None:
        environ = os.environ
    values: MutableMapping[str, str] = {}
    values.update(read_dotenv_values(env_path))
    values.update({key: value for key, value in environ.items() if value})
    return OperatorConfig(values)


def observe_g5_runtime_marker(conn: Any, plan: Mapping[str, Any]) -> dict[str, Any]:
    marker = observe_import_marker(conn, G5_RUNTIME_IMPORT_CODE)
    marker_passed = (
        marker is not None
        and marker["status"] == "succeeded"
        and marker["input_hash"] == G5_EXECUTION_PLAN_SHA256
        and marker["meta"].get("production_credentials_enabled") is True
        and marker["meta"].get("rabbitmq_live") is True
        and marker["meta"].get("network_ingestion_live") is True
        and marker["meta"].get("production_runtime_live") is True
        and marker["meta"].get("formal_evidence_released") is False
        and marker["meta"].get("formal_scoring_released") is False
        and marker["meta"].get("formal_ranking_released") is False
        and marker["meta"].get("epic_2_entered") is False
    )
    return {
        "marker_table": "imports",
        "marker_code": G5_RUNTIME_IMPORT_CODE,
        "marker_observed": marker,
        "marker_passed": marker_passed,
        "observation_passed": marker_passed,
    }


def write_formal_evidence_marker(
    conn: Any,
    plan: Mapping[str, Any],
    g5_runtime_observation: Mapping[str, Any],
) -> None:
    meta = marker_meta(plan, g5_runtime_observation)
    sql = """
    INSERT INTO imports (
        code, source_kind, source_ref, status, tool_version, input_hash, row_count, ended_at, meta
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, now(), %s::jsonb)
    ON CONFLICT (code) DO UPDATE SET
        source_kind = EXCLUDED.source_kind,
        source_ref = EXCLUDED.source_ref,
        status = EXCLUDED.status,
        tool_version = EXCLUDED.tool_version,
        input_hash = EXCLUDED.input_hash,
        row_count = EXCLUDED.row_count,
        ended_at = EXCLUDED.ended_at,
        meta = imports.meta || EXCLUDED.meta
    RETURNING code
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            (
                G6_FORMAL_EVIDENCE_IMPORT_CODE,
                G6_SOURCE_KIND,
                G6_SOURCE_REF,
                "succeeded",
                EXECUTION_VERSION,
                plan["execution_plan_sha256"],
                1,
                json.dumps(meta, ensure_ascii=False, sort_keys=True),
            ),
        )
        cur.fetchone()


def observe_formal_evidence_state(conn: Any, plan: Mapping[str, Any]) -> dict[str, Any]:
    g5_runtime_observation = observe_g5_runtime_marker(conn, plan)
    marker = observe_import_marker(conn, G6_FORMAL_EVIDENCE_IMPORT_CODE)
    marker_passed = (
        marker is not None
        and marker["status"] == "succeeded"
        and marker["input_hash"] == plan["execution_plan_sha256"]
        and marker["meta"].get("g6_approved") is True
        and marker["meta"].get("formal_evidence_released") is True
        and marker["meta"].get("formal_scoring_released") is False
        and marker["meta"].get("formal_ranking_released") is False
        and marker["meta"].get("epic_2_entered") is False
    )
    return {
        "marker_table": "imports",
        "marker_code": G6_FORMAL_EVIDENCE_IMPORT_CODE,
        "marker_observed": marker,
        "marker_passed": marker_passed,
        "g5_runtime_observation": g5_runtime_observation,
        "observation_passed": marker_passed and g5_runtime_observation["observation_passed"],
    }


def observe_import_marker(conn: Any, code: str) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT code, source_kind, source_ref, status, tool_version, input_hash, row_count, meta
            FROM imports
            WHERE code = %s
            """,
            (code,),
        )
        row = cur.fetchone()
    if not row:
        return None
    meta = row[7]
    if isinstance(meta, str):
        meta = json.loads(meta)
    return {
        "code": row[0],
        "source_kind": row[1],
        "source_ref": row[2],
        "status": row[3],
        "tool_version": row[4],
        "input_hash": row[5],
        "row_count": row[6],
        "meta": meta if isinstance(meta, dict) else {},
    }


def marker_meta(plan: Mapping[str, Any], g5_runtime_observation: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **expected_formal_evidence_state(),
        "execution_version": EXECUTION_VERSION,
        "g6_approval_reference": G6_APPROVAL_REFERENCE,
        "boundary_source_pr": G6_BOUNDARY_SOURCE_PR,
        "boundary_head_sha": G6_BOUNDARY_HEAD_SHA,
        "boundary_merge_commit": G6_BOUNDARY_MERGE_COMMIT,
        "g5_execution_plan_sha256": G5_EXECUTION_PLAN_SHA256,
        "execution_plan_sha256": plan["execution_plan_sha256"],
        "formal_evidence_marker_code": G6_FORMAL_EVIDENCE_IMPORT_CODE,
        "formal_evidence_workset": formal_evidence_workset(),
        "g5_runtime_marker_passed": g5_runtime_observation["observation_passed"],
    }


def formal_evidence_workset() -> dict[str, Any]:
    return {
        "workset_id": "issue-292-g6-formal-evidence-release-marker",
        "release_scope": "audit_marker_only",
        "candidate_evidence_ids": [],
        "business_table_writes": [],
        "requires_followup_for_evidence_business_table_writes": True,
    }


def expected_formal_evidence_state() -> dict[str, Any]:
    return {
        "canonical_write_source": "postgresql",
        "jsonl_write_frozen": True,
        "postgres_unique_write_source": True,
        "production_credentials_enabled": True,
        "rabbitmq_live": True,
        "network_ingestion_live": True,
        "production_runtime_live": True,
        "g6_approved": True,
        "formal_evidence_released": True,
        "formal_scoring_released": False,
        "formal_ranking_released": False,
        "epic_2_entered": False,
    }


def unexecuted_formal_evidence_state() -> dict[str, Any]:
    return {
        "canonical_write_source": "postgresql",
        "jsonl_write_frozen": True,
        "postgres_unique_write_source": True,
        "production_credentials_enabled": True,
        "rabbitmq_live": True,
        "network_ingestion_live": True,
        "production_runtime_live": True,
        "g6_approved": True,
        "formal_evidence_released": False,
        "formal_scoring_released": False,
        "formal_ranking_released": False,
        "epic_2_entered": False,
    }


def connect_to_database(dsn: str) -> Any:
    import psycopg

    return psycopg.connect(dsn)


def stable_json_sha256(payload: Mapping[str, Any]) -> str:
    basis = {key: value for key, value in payload.items() if key != "execution_plan_sha256"}
    encoded = json.dumps(basis, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def redact_secret(text: str) -> str:
    redacted = text
    if "postgresql://" in redacted and "@" in redacted.split("postgresql://", 1)[1]:
        prefix, rest = redacted.split("postgresql://", 1)
        redacted = prefix + "postgresql://<redacted-credentials>@" + rest.split("@", 1)[1]
    return redacted.replace("password=", "password=<redacted>")


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build or execute the Epic 1 G6 formal evidence package.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--execution-plan-json", action="store_true")
    mode.add_argument("--operator-checklist-md", action="store_true")
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--observe", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument("--expected-plan-sha256")
    parser.add_argument("--source-root", type=Path, default=ROOT)
    args = parser.parse_args(argv)

    if args.execution_plan_json:
        report: Any = render_execution_plan_json(source_root=args.source_root)
    elif args.operator_checklist_md:
        sys.stdout.write(render_operator_checklist_md(source_root=args.source_root))
        return 0
    elif args.execute:
        report = execute_formal_evidence_release(
            approval_token=args.approval_token,
            expected_plan_sha256=args.expected_plan_sha256,
            source_root=args.source_root,
        )
    elif args.observe:
        report = observe_formal_evidence_release(
            approval_token=args.approval_token,
            expected_plan_sha256=args.expected_plan_sha256,
            source_root=args.source_root,
        )
    else:
        report = build_contract_report(source_root=args.source_root)

    sys.stdout.write(report_as_json(report))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
