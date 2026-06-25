from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.env_loader import read_dotenv_values  # noqa: E402


EXECUTION_VERSION = "g4-write-source-cutover-execution-v1"
APPROVAL_TOKEN = "USER_APPROVED_G4_WRITE_SOURCE_CUTOVER_ISSUE292"
G4_APPROVAL_REFERENCE = "https://github.com/phdiggit/emperor-evaluation/issues/292#issuecomment-4803139721"
G4_SOURCE_PR = 296
G4_SOURCE_HEAD_SHA = "7363c0fe07063fc5b023c3cb951636051812793f"
G4_SOURCE_MERGE_COMMIT = "50f5dcffe96614c168c28b30ce35e1d95353f5c9"
G3_EXECUTION_PLAN_SHA256 = "1138f4f0ef95e20e0026185f6530ad4671dc61aba13be330a466b20890ae315d"
DSN_ENV_NAME = "EMPEROR_EVAL_PG_DSN"
CUTOVER_IMPORT_CODE = "G4-WRITE-SOURCE-CUTOVER-ISSUE292"
CUTOVER_SOURCE_KIND = "write_source_cutover"
CUTOVER_SOURCE_REF = "issue-292-g4"
MARKER_TABLE = "imports"
G3_HOST_TABLE = "src_hosts"
EXPECTED_G3_SRC_HOST_CODES = ("zh.wikisource.org",)
SUPPORTED_MODES = (
    "contract-report",
    "cutover-plan-json",
    "operator-checklist-md",
    "execute",
    "observe",
)
BOUNDARIES = (
    "G4 approves the JSONL freeze and PostgreSQL unique write-source cutover package only.",
    "Default reports do not read DSN, connect PostgreSQL, or write repository files.",
    "Execute writes only an imports audit marker after G3 src_hosts readback passes.",
    "No source JSONL file is modified by this package.",
    "No source, passage, evidence, cluster, anchor, relationship, scoring, ranking, or runtime table is written.",
    "Production runtime, RabbitMQ workers, formal scoring, and formal ranking remain blocked by later gates.",
)


def build_contract_report(*, source_root: Path = ROOT) -> dict[str, Any]:
    plan = render_cutover_plan_json(source_root=source_root)
    return {
        "mode": "contract-report",
        "execution_version": EXECUTION_VERSION,
        "gate_status": "G4_APPROVED",
        "approval_token_required": True,
        "approval_token_value": APPROVAL_TOKEN,
        "supported_modes": list(SUPPORTED_MODES),
        "default_modes_db_touching": False,
        "dsn_env_name": DSN_ENV_NAME,
        "g4_approval_reference": G4_APPROVAL_REFERENCE,
        "source_pr": G4_SOURCE_PR,
        "source_head_sha": G4_SOURCE_HEAD_SHA,
        "source_merge_commit": G4_SOURCE_MERGE_COMMIT,
        "cutover_marker": plan["cutover_marker"],
        "cutover_plan_sha256": plan["cutover_plan_sha256"],
        "freeze_point": plan["freeze_point"],
        "rollback_point": plan["rollback_point"],
        "post_apply_observation_contract": plan["post_apply_observation_contract"],
        "cutover_completed_by_this_report": False,
        "post_apply_observation_completed_by_this_report": False,
        "next_user_gate": "G5_REQUIRED_BEFORE_PRODUCTION_RUNTIME_OR_ADDITIONAL_BUSINESS_WRITES",
        "boundaries": list(BOUNDARIES),
    }


def render_cutover_plan_json(*, source_root: Path = ROOT) -> dict[str, Any]:
    plan: dict[str, Any] = {
        "mode": "cutover-plan-json",
        "execution_version": EXECUTION_VERSION,
        "gate_status": "G4_APPROVED",
        "g1_canonical_manifest_approved": True,
        "g2_mapping_approved": True,
        "g3_first_business_write_approved": True,
        "g4_write_source_cutover_approved": True,
        "g4_approval_reference": G4_APPROVAL_REFERENCE,
        "source_pr": G4_SOURCE_PR,
        "source_head_sha": G4_SOURCE_HEAD_SHA,
        "source_merge_commit": G4_SOURCE_MERGE_COMMIT,
        "g3_execution_plan_sha256": G3_EXECUTION_PLAN_SHA256,
        "freeze_point": {
            "jsonl_write_freeze_scope": ["data/*.jsonl"],
            "freeze_after_merge_commit": G4_SOURCE_MERGE_COMMIT,
            "freeze_after_pr": G4_SOURCE_PR,
            "allowed_after_freeze_without_new_gate": [
                "read_only_exports",
                "validation_reports",
                "operator_notes",
            ],
            "not_frozen_by_this_package": [
                "docs",
                "tests",
                "scripts",
                "db/postgres",
            ],
        },
        "preconditions": {
            "approval_token": APPROVAL_TOKEN,
            "expected_plan_sha256_required": True,
            "dsn_required_only_for_execute_or_observe": True,
            "driver": "psycopg",
            "schema_must_exist": True,
            "g3_src_hosts_readback_required": True,
            "expected_g3_src_host_codes": list(EXPECTED_G3_SRC_HOST_CODES),
        },
        "cutover_marker": {
            "target_table": MARKER_TABLE,
            "code": CUTOVER_IMPORT_CODE,
            "source_kind": CUTOVER_SOURCE_KIND,
            "source_ref": CUTOVER_SOURCE_REF,
            "status": "succeeded",
            "row_count": 1,
            "input_hash_source": "cutover_plan_sha256",
        },
        "execute_write": {
            "write_kind": "idempotent_imports_marker_upsert",
            "target_tables": [MARKER_TABLE],
            "business_target_tables_written": [],
            "repository_files_written": [],
            "requires_g3_src_hosts_observation": True,
        },
        "write_source_state_after_cutover": expected_write_source_state(),
        "post_apply_observation_contract": {
            "marker_table": MARKER_TABLE,
            "marker_code": CUTOVER_IMPORT_CODE,
            "expected_marker_status": "succeeded",
            "g3_host_table": G3_HOST_TABLE,
            "expected_g3_src_host_codes": list(EXPECTED_G3_SRC_HOST_CODES),
            "success_requires_marker_and_g3_host_readback": True,
        },
        "rollback_point": {
            "previous_write_source": "jsonl",
            "rollback_action": "mark_or_remove_cutover_marker_and_restore_jsonl_write_policy",
            "database_data_deletion_allowed_by_this_plan": False,
            "preserve_postgres_audit_rows": True,
            "requires_explicit_followup_approval": True,
        },
        "boundaries": list(BOUNDARIES),
    }
    plan["cutover_plan_sha256"] = stable_json_sha256(plan)
    return plan


def render_operator_checklist_md(*, source_root: Path = ROOT) -> str:
    plan = render_cutover_plan_json(source_root=source_root)
    return "\n".join(
        [
            "# G4 Write-Source Cutover Operator Checklist",
            "",
            "- Confirm G4 approval reference is recorded in Issue #292.",
            f"- Confirm cutover plan sha256 is `{plan['cutover_plan_sha256']}`.",
            "- Confirm `EMPEROR_EVAL_PG_DSN` is set only in the operator environment.",
            "- Confirm G3 `src_hosts` observation already contains `zh.wikisource.org`.",
            "- Run `--execute` with the G4 approval token and expected plan sha256.",
            "- Confirm the returned observation reads back the `imports` cutover marker.",
            "- Treat `data/*.jsonl` as frozen for writes after successful observation.",
            "- Do not start production runtime, RabbitMQ workers, formal scoring, or formal ranking from this gate.",
            "",
        ]
    )


def execute_cutover(
    *,
    approval_token: str | None,
    expected_plan_sha256: str | None,
    source_root: Path = ROOT,
) -> dict[str, Any]:
    plan = render_cutover_plan_json(source_root=source_root)
    failures = pre_execution_failures(approval_token, expected_plan_sha256, plan)
    if failures:
        return build_blocked_execution_report(plan, failures, failure_stage="gate", dsn_read=False)

    dsn = read_dsn()
    if not dsn:
        return build_blocked_execution_report(plan, ["blocked_missing_dsn"], failure_stage="dsn", dsn_read=False)

    try:
        with connect_to_database(dsn) as conn:
            g3_observation = observe_g3_src_hosts(conn, EXPECTED_G3_SRC_HOST_CODES)
            if not g3_observation["observation_passed"]:
                return {
                    **base_execution_report(plan),
                    "mode": "execute-report",
                    "execution_status": "blocked",
                    "failure_stage": "g3_observation",
                    "blocking_failures": ["blocked_missing_g3_src_hosts_readback"],
                    "production_dsn_read": True,
                    "cutover_marker_written": False,
                    "g3_src_hosts_observation": g3_observation,
                    "post_apply_observation": None,
                    "post_apply_observation_completed": False,
                    "cutover_executed": False,
                    **uncutover_state(),
                }
            write_cutover_marker(conn, plan)
            observation = observe_cutover_state(conn, plan)
            conn.commit()
    except Exception as exc:  # pragma: no cover - fake failure tests cover redaction behavior indirectly.
        return {
            **base_execution_report(plan),
            "mode": "execute-report",
            "execution_status": "failed",
            "failure_stage": "database",
            "blocking_failures": ["database_error"],
            "production_dsn_read": True,
            "error": redact_secret(str(exc)),
            "cutover_marker_written": False,
            "g3_src_hosts_observation": None,
            "post_apply_observation": None,
            "post_apply_observation_completed": False,
            "cutover_executed": False,
            **uncutover_state(),
        }

    passed = observation["observation_passed"]
    return {
        **base_execution_report(plan),
        "mode": "execute-report",
        "execution_status": "succeeded" if passed else "failed_observation",
        "failure_stage": None if passed else "observation",
        "blocking_failures": [] if passed else ["post_apply_observation_failed"],
        "production_dsn_read": True,
        "cutover_marker_written": True,
        "g3_src_hosts_observation": observation["g3_src_hosts_observation"],
        "post_apply_observation": observation,
        "post_apply_observation_completed": True,
        "cutover_executed": passed,
        **(expected_write_source_state() if passed else uncutover_state()),
    }


def observe_cutover(
    *,
    approval_token: str | None,
    expected_plan_sha256: str | None,
    source_root: Path = ROOT,
) -> dict[str, Any]:
    plan = render_cutover_plan_json(source_root=source_root)
    failures = pre_execution_failures(approval_token, expected_plan_sha256, plan)
    if failures:
        return build_blocked_execution_report(plan, failures, failure_stage="gate", dsn_read=False, mode="observe-report")
    dsn = read_dsn()
    if not dsn:
        return build_blocked_execution_report(plan, ["blocked_missing_dsn"], failure_stage="dsn", dsn_read=False, mode="observe-report")
    try:
        with connect_to_database(dsn) as conn:
            observation = observe_cutover_state(conn, plan)
    except Exception as exc:  # pragma: no cover
        return {
            **base_execution_report(plan),
            "mode": "observe-report",
            "execution_status": "failed",
            "failure_stage": "database",
            "blocking_failures": ["database_error"],
            "production_dsn_read": True,
            "error": redact_secret(str(exc)),
            "post_apply_observation": None,
            "post_apply_observation_completed": False,
            "cutover_executed": False,
            **uncutover_state(),
        }
    passed = observation["observation_passed"]
    return {
        **base_execution_report(plan),
        "mode": "observe-report",
        "execution_status": "succeeded" if passed else "failed_observation",
        "failure_stage": None if passed else "observation",
        "blocking_failures": [] if passed else ["post_apply_observation_failed"],
        "production_dsn_read": True,
        "post_apply_observation": observation,
        "post_apply_observation_completed": True,
        "cutover_executed": False,
        **(expected_write_source_state() if passed else uncutover_state()),
    }


def pre_execution_failures(
    approval_token: str | None,
    expected_plan_sha256: str | None,
    plan: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    if approval_token != APPROVAL_TOKEN:
        failures.append("blocked_missing_or_invalid_g4_approval_token")
        return failures
    if not expected_plan_sha256:
        failures.append("blocked_missing_expected_plan_sha256")
        return failures
    if expected_plan_sha256 != plan["cutover_plan_sha256"]:
        failures.append("blocked_cutover_plan_sha256_mismatch")
    return failures


def build_blocked_execution_report(
    plan: Mapping[str, Any],
    failures: Sequence[str],
    *,
    failure_stage: str,
    dsn_read: bool,
    mode: str = "execute-report",
) -> dict[str, Any]:
    return {
        **base_execution_report(plan),
        "mode": mode,
        "execution_status": "blocked",
        "failure_stage": failure_stage,
        "blocking_failures": list(failures),
        "production_dsn_read": dsn_read,
        "cutover_marker_written": False,
        "post_apply_observation": None,
        "post_apply_observation_completed": False,
        "cutover_executed": False,
        **uncutover_state(),
    }


def base_execution_report(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "execution_version": EXECUTION_VERSION,
        "gate_status": "G4_APPROVED",
        "g4_approval_reference": G4_APPROVAL_REFERENCE,
        "source_pr": G4_SOURCE_PR,
        "source_head_sha": G4_SOURCE_HEAD_SHA,
        "source_merge_commit": G4_SOURCE_MERGE_COMMIT,
        "cutover_plan_sha256": plan["cutover_plan_sha256"],
        "cutover_marker": plan["cutover_marker"],
        "next_user_gate": "G5_REQUIRED_BEFORE_PRODUCTION_RUNTIME_OR_ADDITIONAL_BUSINESS_WRITES",
        "boundaries": list(BOUNDARIES),
    }


def write_cutover_marker(conn: Any, plan: Mapping[str, Any]) -> None:
    meta = marker_meta(plan)
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
                CUTOVER_IMPORT_CODE,
                CUTOVER_SOURCE_KIND,
                CUTOVER_SOURCE_REF,
                "succeeded",
                EXECUTION_VERSION,
                plan["cutover_plan_sha256"],
                1,
                json.dumps(meta, ensure_ascii=False, sort_keys=True),
            ),
        )
        cur.fetchone()


def observe_cutover_state(conn: Any, plan: Mapping[str, Any]) -> dict[str, Any]:
    marker = observe_cutover_marker(conn)
    g3_observation = observe_g3_src_hosts(conn, EXPECTED_G3_SRC_HOST_CODES)
    marker_passed = (
        marker is not None
        and marker["status"] == "succeeded"
        and marker["input_hash"] == plan["cutover_plan_sha256"]
        and marker["meta"].get("canonical_write_source") == "postgresql"
        and marker["meta"].get("jsonl_write_frozen") is True
        and marker["meta"].get("postgres_unique_write_source") is True
    )
    return {
        "marker_table": MARKER_TABLE,
        "marker_code": CUTOVER_IMPORT_CODE,
        "marker_observed": marker,
        "marker_passed": marker_passed,
        "g3_src_hosts_observation": g3_observation,
        "observation_passed": marker_passed and g3_observation["observation_passed"],
    }


def observe_cutover_marker(conn: Any) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT code, source_kind, source_ref, status, tool_version, input_hash, row_count, meta
            FROM imports
            WHERE code = %s
            """,
            (CUTOVER_IMPORT_CODE,),
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


def observe_g3_src_hosts(conn: Any, expected_codes: Sequence[str]) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT code, name, trust_class, base_url, adapter, status
            FROM src_hosts
            WHERE code = ANY(%s)
            ORDER BY code
            """,
            (list(expected_codes),),
        )
        rows = cur.fetchall()
    observed = [
        {
            "code": row[0],
            "name": row[1],
            "trust_class": row[2],
            "base_url": row[3],
            "adapter": row[4],
            "status": row[5],
        }
        for row in rows
    ]
    observed_codes = sorted(item["code"] for item in observed)
    expected = sorted(expected_codes)
    return {
        "target_table": G3_HOST_TABLE,
        "expected_codes": expected,
        "observed_codes": observed_codes,
        "expected_row_count": len(expected),
        "observed_row_count": len(observed_codes),
        "missing_codes": [code for code in expected if code not in observed_codes],
        "unexpected_codes": [code for code in observed_codes if code not in expected],
        "rows": observed,
        "observation_passed": observed_codes == expected,
    }


def marker_meta(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **expected_write_source_state(),
        "execution_version": EXECUTION_VERSION,
        "g4_approval_reference": G4_APPROVAL_REFERENCE,
        "source_pr": G4_SOURCE_PR,
        "source_head_sha": G4_SOURCE_HEAD_SHA,
        "source_merge_commit": G4_SOURCE_MERGE_COMMIT,
        "g3_execution_plan_sha256": G3_EXECUTION_PLAN_SHA256,
        "cutover_plan_sha256": plan["cutover_plan_sha256"],
        "cutover_marker_code": CUTOVER_IMPORT_CODE,
    }


def expected_write_source_state() -> dict[str, Any]:
    return {
        "canonical_write_source": "postgresql",
        "jsonl_write_frozen": True,
        "postgres_unique_write_source": True,
        "production_runtime_live": False,
        "formal_scoring_released": False,
        "formal_ranking_released": False,
    }


def uncutover_state() -> dict[str, Any]:
    return {
        "canonical_write_source": "jsonl",
        "jsonl_write_frozen": False,
        "postgres_unique_write_source": False,
        "production_runtime_live": False,
        "formal_scoring_released": False,
        "formal_ranking_released": False,
    }


def read_dsn(*, env: Mapping[str, str] | None = None, env_path: Path = ROOT / ".env") -> str | None:
    if env is None:
        env = os.environ
    if env.get(DSN_ENV_NAME):
        return env[DSN_ENV_NAME]
    dotenv = read_dotenv_values(env_path)
    return dotenv.get(DSN_ENV_NAME)


def connect_to_database(dsn: str) -> Any:
    import psycopg

    return psycopg.connect(dsn)


def stable_json_sha256(payload: Mapping[str, Any]) -> str:
    basis = {key: value for key, value in payload.items() if key != "cutover_plan_sha256"}
    encoded = json.dumps(basis, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def redact_secret(text: str) -> str:
    redacted = text
    if "postgresql://" in redacted:
        redacted = redacted.split("postgresql://", 1)[0] + "postgresql://<redacted-dsn>"
    redacted = redacted.replace("password=", "password=<redacted>")
    return redacted


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build or execute the Epic 1 G4 write-source cutover package.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--contract-report", action="store_true")
    mode.add_argument("--cutover-plan-json", action="store_true")
    mode.add_argument("--operator-checklist-md", action="store_true")
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--observe", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument("--expected-plan-sha256")
    parser.add_argument("--source-root", type=Path, default=ROOT)
    args = parser.parse_args(argv)

    if args.cutover_plan_json:
        report: Any = render_cutover_plan_json(source_root=args.source_root)
    elif args.operator_checklist_md:
        sys.stdout.write(render_operator_checklist_md(source_root=args.source_root))
        return 0
    elif args.execute:
        report = execute_cutover(
            approval_token=args.approval_token,
            expected_plan_sha256=args.expected_plan_sha256,
            source_root=args.source_root,
        )
    elif args.observe:
        report = observe_cutover(
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
