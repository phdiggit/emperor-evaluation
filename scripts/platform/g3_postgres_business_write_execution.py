from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.core.fingerprints import stable_json_sha256 as _stable_json_sha256  # noqa: E402
from scripts.platform.core.redaction import redact_connection_secrets  # noqa: E402
from scripts.platform.env_loader import read_dotenv_values  # noqa: E402
from scripts.platform.jsonl_staging_diff_verification import build_verification_report  # noqa: E402


EXECUTION_VERSION = "g3-postgres-business-write-execution-v1"
APPROVAL_TOKEN = "USER_APPROVED_G3_POSTGRES_BUSINESS_WRITE_ISSUE292"
G3_APPROVAL_REFERENCE = "https://github.com/phdiggit/emperor-evaluation/issues/292#issuecomment-4802591018"
G1_MANIFEST_SHA256 = "1d395d0bc5c859e02add21de4ccde62f8172332123facd668cecb9c10bd8431f"
G3_BASE_DRY_RUN_MERGE_COMMIT = "c7199882b328f87769d9262e2e397c1057bc3e27"
DSN_ENV_NAME = "EMPEROR_EVAL_PG_DSN"
TARGET_SOURCE_FILE = "data/sources.jsonl"
TARGET_TABLE = "src_hosts"
SUPPORTED_MODES = (
    "contract-report",
    "execution-plan-json",
    "operator-checklist-md",
    "execute",
    "observe",
)
BOUNDARIES = (
    "G3 approves the first formal PostgreSQL business write gate only.",
    "This package targets src_hosts only.",
    "No src_docs, doc_revs, passages, evidence, cluster, anchor, relationship, write-source, or runtime tables are written.",
    "JSONL remains the canonical write source.",
    "G4 is still required before JSONL freeze or PostgreSQL unique write-source cutover.",
    "No formal outcome release is performed.",
)


@dataclass(frozen=True)
class SourceHostRow:
    code: str
    name: str
    trust_class: str
    base_url: str
    adapter: str
    status: str
    source_file: str
    source_ids: tuple[str, ...]

    def as_sql_params(self) -> tuple[str, str, str, str, str, str, str]:
        meta = {
            "source_file": self.source_file,
            "source_id_count": len(self.source_ids),
            "source_ids": list(self.source_ids),
            "g1_manifest_sha256": G1_MANIFEST_SHA256,
            "g3_approval_reference": G3_APPROVAL_REFERENCE,
            "write_scope": "g3_first_business_write_src_hosts_only",
        }
        return (
            self.code,
            self.name,
            self.trust_class,
            self.base_url,
            self.adapter,
            self.status,
            json.dumps(meta, ensure_ascii=False, sort_keys=True),
        )

    def as_report(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "trust_class": self.trust_class,
            "base_url": self.base_url,
            "adapter": self.adapter,
            "status": self.status,
            "source_file": self.source_file,
            "source_id_count": len(self.source_ids),
            "source_ids": list(self.source_ids),
        }


def build_contract_report(*, source_root: Path = ROOT) -> dict[str, Any]:
    plan = render_execution_plan_json(source_root=source_root)
    return {
        "mode": "contract-report",
        "execution_version": EXECUTION_VERSION,
        "gate_status": "G3_APPROVED",
        "approval_token_required": True,
        "approval_token_value": APPROVAL_TOKEN,
        "supported_modes": list(SUPPORTED_MODES),
        "default_modes_db_touching": False,
        "dsn_env_name": DSN_ENV_NAME,
        "g3_approval_reference": G3_APPROVAL_REFERENCE,
        "g3_base_dry_run_merge_commit": G3_BASE_DRY_RUN_MERGE_COMMIT,
        "target_write_scope": plan["target_write_scope"],
        "planned_rows_by_table": plan["planned_rows_by_table"],
        "execution_plan_sha256": plan["execution_plan_sha256"],
        "preflight_summary": plan["preflight_summary"],
        "blocked_followup_writes": plan["blocked_followup_writes"],
        "production_write_completed_by_this_report": False,
        "post_apply_observation_completed_by_this_report": False,
        "next_user_gate": "G4_REQUIRED_BEFORE_JSONL_FREEZE_OR_POSTGRES_UNIQUE_WRITE_SOURCE",
        "boundaries": list(BOUNDARIES),
    }


def render_execution_plan_json(*, source_root: Path = ROOT) -> dict[str, Any]:
    verification = build_verification_report(source_root=source_root)
    source_rows = load_source_rows(source_root)
    planned_host_rows = build_source_host_rows(source_rows)
    duplicate_url_groups = find_duplicate_url_groups(source_rows)
    plan: dict[str, Any] = {
        "mode": "execution-plan-json",
        "execution_version": EXECUTION_VERSION,
        "gate_status": "G3_APPROVED",
        "g1_manifest_sha256": G1_MANIFEST_SHA256,
        "manifest_matches_g1": verification["manifest_matches_g1"],
        "g2_mapping_approved": True,
        "g3_approved": True,
        "g3_approval_reference": G3_APPROVAL_REFERENCE,
        "g3_base_dry_run_merge_commit": G3_BASE_DRY_RUN_MERGE_COMMIT,
        "target_write_scope": {
            "source_files": [TARGET_SOURCE_FILE],
            "target_tables": [TARGET_TABLE],
            "write_kind": "idempotent_upsert",
            "first_business_write": True,
        },
        "planned_rows_by_table": {TARGET_TABLE: len(planned_host_rows)},
        "planned_src_hosts": [row.as_report() for row in planned_host_rows],
        "preflight_summary": {
            "sources_jsonl_rows": len(source_rows),
            "source_host_rows_planned": len(planned_host_rows),
            "manifest_matches_g1": verification["manifest_matches_g1"],
            "staging_row_count_diffs_empty": verification["row_count_diffs_by_file"] == {},
            "staging_id_count_diffs_empty": verification["id_count_diffs_by_file"] == {},
            "staging_orphan_reference_count": verification["orphan_reference_report"]["total_orphan_references"],
            "staging_validation_errors": verification["staging_report_summary"]["rows_with_validation_errors"],
        },
        "blocked_followup_writes": [
            {
                "target_tables": ["src_docs", "doc_revs", "passages"],
                "status": "blocked_until_source_document_merge_policy",
                "reason": "multiple source_id rows can share one canonical URL; formal document/revision merge rules must be approved before these tables are written",
                "duplicate_url_groups": duplicate_url_groups,
            },
            {
                "target_tables": [
                    "evd_cards",
                    "evd_src_links",
                    "clusters",
                    "cluster_evd",
                    "anchors",
                    "anchor_links",
                ],
                "status": "blocked_until_resolver_and_manual_review_outputs",
                "reason": "person, subitem, passage, evidence, cluster and anchor references still require resolver or manual-review outputs",
            },
        ],
        "execution_requirements": {
            "approval_token": APPROVAL_TOKEN,
            "expected_plan_sha256_required": True,
            "dsn_required_only_for_execute_or_observe": True,
            "driver": "psycopg",
            "schema_must_exist": True,
            "target_table_must_exist": TARGET_TABLE,
        },
        "observation_contract": {
            "query_target_table": TARGET_TABLE,
            "expected_codes": [row.code for row in planned_host_rows],
            "expected_row_count": len(planned_host_rows),
            "post_apply_success_requires_readback": True,
        },
        "boundaries": list(BOUNDARIES),
    }
    plan["execution_plan_sha256"] = stable_json_sha256(plan)
    return plan


def render_operator_checklist_md(*, source_root: Path = ROOT) -> str:
    plan = render_execution_plan_json(source_root=source_root)
    return "\n".join(
        [
            "# G3 PostgreSQL Business Write Operator Checklist",
            "",
            "- Confirm G3 approval reference is recorded in Issue #292.",
            f"- Confirm execution plan sha256 is `{plan['execution_plan_sha256']}`.",
            "- Confirm `EMPEROR_EVAL_PG_DSN` is set only in the operator environment.",
            "- Confirm the target PostgreSQL schema already contains `src_hosts` from the live schema baseline.",
            "- Confirm this execution writes only `src_hosts`.",
            "- Confirm `src_docs`, `doc_revs`, `passages`, evidence, cluster, anchor and relationship tables remain blocked.",
            "- Run `--execute` with the approval token and expected plan sha256.",
            "- Run or inspect the returned post-apply observation before claiming success.",
            "- Do not freeze JSONL or switch PostgreSQL to unique write source; that still requires G4.",
            "",
        ]
    )


def execute_business_write(
    *,
    approval_token: str | None,
    expected_plan_sha256: str | None,
    source_root: Path = ROOT,
) -> dict[str, Any]:
    plan = render_execution_plan_json(source_root=source_root)
    failures = pre_execution_failures(approval_token, expected_plan_sha256, plan)
    if failures:
        return build_blocked_execution_report(plan, failures, failure_stage="gate", dsn_read=False)

    dsn = read_dsn()
    if not dsn:
        return build_blocked_execution_report(plan, ["blocked_missing_dsn"], failure_stage="dsn", dsn_read=False)

    try:
        with connect_to_database(dsn) as conn:
            written = write_src_hosts(conn, build_source_host_rows(load_source_rows(source_root)))
            observation = observe_src_hosts(conn, plan["observation_contract"]["expected_codes"])
            conn.commit()
    except Exception as exc:  # pragma: no cover - exercised with fake connection failure tests
        return {
            **base_execution_report(plan),
            "mode": "execute-report",
            "execution_status": "failed",
            "failure_stage": "database",
            "blocking_failures": ["database_error"],
            "production_dsn_read": True,
            "error": redact_secret(str(exc)),
            "target_table_rows_written": {TARGET_TABLE: 0},
            "post_apply_observation": None,
            "post_apply_observation_completed": False,
            "production_business_write_executed": False,
        }

    passed = observation["observation_passed"]
    return {
        **base_execution_report(plan),
        "mode": "execute-report",
        "execution_status": "succeeded" if passed else "failed_observation",
        "failure_stage": None if passed else "observation",
        "blocking_failures": [] if passed else ["post_apply_observation_failed"],
        "production_dsn_read": True,
        "target_table_rows_written": {TARGET_TABLE: written},
        "post_apply_observation": observation,
        "post_apply_observation_completed": True,
        "production_business_write_executed": passed,
        "g4_approved": False,
        "jsonl_write_frozen": False,
        "postgres_unique_write_source": False,
    }


def observe_business_write(
    *,
    approval_token: str | None,
    expected_plan_sha256: str | None,
    source_root: Path = ROOT,
) -> dict[str, Any]:
    plan = render_execution_plan_json(source_root=source_root)
    failures = pre_execution_failures(approval_token, expected_plan_sha256, plan)
    if failures:
        return build_blocked_execution_report(plan, failures, failure_stage="gate", dsn_read=False, mode="observe-report")
    dsn = read_dsn()
    if not dsn:
        return build_blocked_execution_report(plan, ["blocked_missing_dsn"], failure_stage="dsn", dsn_read=False, mode="observe-report")
    try:
        with connect_to_database(dsn) as conn:
            observation = observe_src_hosts(conn, plan["observation_contract"]["expected_codes"])
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
            "production_business_write_executed": False,
        }
    return {
        **base_execution_report(plan),
        "mode": "observe-report",
        "execution_status": "succeeded" if observation["observation_passed"] else "failed_observation",
        "failure_stage": None if observation["observation_passed"] else "observation",
        "blocking_failures": [] if observation["observation_passed"] else ["post_apply_observation_failed"],
        "production_dsn_read": True,
        "post_apply_observation": observation,
        "post_apply_observation_completed": True,
        "production_business_write_executed": False,
    }


def pre_execution_failures(
    approval_token: str | None,
    expected_plan_sha256: str | None,
    plan: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    if approval_token != APPROVAL_TOKEN:
        failures.append("blocked_missing_or_invalid_g3_approval_token")
        return failures
    if not expected_plan_sha256:
        failures.append("blocked_missing_expected_plan_sha256")
        return failures
    if expected_plan_sha256 != plan["execution_plan_sha256"]:
        failures.append("blocked_execution_plan_sha256_mismatch")
        return failures
    if not plan["manifest_matches_g1"]:
        failures.append("blocked_manifest_drift_from_g1")
    if plan["preflight_summary"]["staging_validation_errors"]:
        failures.append("blocked_staging_validation_errors")
    if plan["preflight_summary"]["staging_orphan_reference_count"]:
        failures.append("blocked_orphan_references")
    if plan["planned_rows_by_table"][TARGET_TABLE] != 1:
        failures.append("blocked_unexpected_src_host_row_count")
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
        "target_table_rows_written": {TARGET_TABLE: 0},
        "post_apply_observation": None,
        "post_apply_observation_completed": False,
        "production_business_write_executed": False,
    }


def base_execution_report(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "execution_version": EXECUTION_VERSION,
        "gate_status": "G3_APPROVED",
        "g3_approval_reference": G3_APPROVAL_REFERENCE,
        "execution_plan_sha256": plan["execution_plan_sha256"],
        "target_write_scope": plan["target_write_scope"],
        "planned_rows_by_table": plan["planned_rows_by_table"],
        "next_user_gate": "G4_REQUIRED_BEFORE_JSONL_FREEZE_OR_POSTGRES_UNIQUE_WRITE_SOURCE",
        "boundaries": list(BOUNDARIES),
    }


def load_source_rows(source_root: Path) -> list[dict[str, Any]]:
    path = source_root / TARGET_SOURCE_FILE
    rows: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if raw_line.strip():
            payload = json.loads(raw_line)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def build_source_host_rows(source_rows: Sequence[Mapping[str, Any]]) -> list[SourceHostRow]:
    source_ids_by_host: dict[str, set[str]] = {}
    schemes_by_host: dict[str, str] = {}
    for row in source_rows:
        source_id = str(row.get("source_id", "")).strip()
        for url in split_urls(row.get("url")):
            parsed = urlparse(url)
            host = parsed.netloc.lower().strip()
            if not host:
                continue
            source_ids_by_host.setdefault(host, set()).add(source_id)
            schemes_by_host.setdefault(host, parsed.scheme or "https")
    return [
        SourceHostRow(
            code=host,
            name=host,
            trust_class="canonical_jsonl_source_host",
            base_url=f"{schemes_by_host.get(host, 'https')}://{host}",
            adapter="manual_source_jsonl",
            status="active",
            source_file=TARGET_SOURCE_FILE,
            source_ids=tuple(sorted(source_ids)),
        )
        for host, source_ids in sorted(source_ids_by_host.items())
    ]


def split_urls(value: Any) -> list[str]:
    if not isinstance(value, str):
        return []
    urls: list[str] = []
    for part in value.replace("；", ";").split(";"):
        stripped = part.strip()
        if stripped:
            urls.append(stripped)
    return urls


def find_duplicate_url_groups(source_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[str]] = {}
    for row in source_rows:
        source_id = str(row.get("source_id", "")).strip()
        for url in split_urls(row.get("url")):
            parsed = urlparse(url)
            groups.setdefault((parsed.netloc.lower(), url), []).append(source_id)
    return [
        {"host": host, "url": url, "source_ids": sorted(source_ids), "source_id_count": len(source_ids)}
        for (host, url), source_ids in sorted(groups.items())
        if len(source_ids) > 1
    ]


def write_src_hosts(conn: Any, rows: Sequence[SourceHostRow]) -> int:
    sql = """
    INSERT INTO src_hosts (code, name, trust_class, base_url, adapter, status, meta)
    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
    ON CONFLICT (code) DO UPDATE SET
        name = EXCLUDED.name,
        trust_class = EXCLUDED.trust_class,
        base_url = EXCLUDED.base_url,
        adapter = EXCLUDED.adapter,
        status = EXCLUDED.status,
        meta = src_hosts.meta || EXCLUDED.meta
    RETURNING code
    """
    written = 0
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(sql, row.as_sql_params())
            if cur.fetchone():
                written += 1
    return written


def observe_src_hosts(conn: Any, expected_codes: Sequence[str]) -> dict[str, Any]:
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
        "target_table": TARGET_TABLE,
        "expected_codes": expected,
        "observed_codes": observed_codes,
        "expected_row_count": len(expected),
        "observed_row_count": len(observed_codes),
        "missing_codes": [code for code in expected if code not in observed_codes],
        "unexpected_codes": [code for code in observed_codes if code not in expected],
        "rows": observed,
        "observation_passed": observed_codes == expected,
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
    return _stable_json_sha256(payload, omit_key="execution_plan_sha256")


def redact_secret(text: str) -> str:
    return redact_connection_secrets(text, schemes=("postgres", "postgresql"))


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build or execute the Epic 1 G3 first PostgreSQL business write package.")
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
        report = execute_business_write(
            approval_token=args.approval_token,
            expected_plan_sha256=args.expected_plan_sha256,
            source_root=args.source_root,
        )
    elif args.observe:
        report = observe_business_write(
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
