from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.core.fingerprints import stable_json_sha256 as _stable_json_sha256  # noqa: E402
from scripts.platform.core.redaction import redact_connection_secrets  # noqa: E402
from scripts.platform.env_loader import read_dotenv_values  # noqa: E402
from scripts.platform.fake_runtime import FakeAckableMessage, FakePublisher, FakeRepository  # noqa: E402
from scripts.platform.models import JobMessage, JobRecord, OutboxMessage  # noqa: E402
from scripts.platform.outbox_dispatcher import OutboxDispatcher  # noqa: E402
from scripts.platform.worker_runtime import WorkerRuntime  # noqa: E402


EXECUTION_VERSION = "g5-runtime-execution-v1"
APPROVAL_TOKEN = "USER_APPROVED_G5_RUNTIME_CREDENTIALS_NETWORK_ISSUE292"
G5_APPROVAL_REFERENCE = "https://github.com/phdiggit/emperor-evaluation/issues/292"
G5_BOUNDARY_SOURCE_PR = 300
G5_BOUNDARY_HEAD_SHA = "d71b29a91d1184bc706b3c7c5beb58a00c93d374"
G5_BOUNDARY_MERGE_COMMIT = "7fb1d6b3592d195bc0b2b6eb17dcadc263a7f167"
G3_EXECUTION_PLAN_SHA256 = "1138f4f0ef95e20e0026185f6530ad4671dc61aba13be330a466b20890ae315d"
G4_CUTOVER_PLAN_SHA256 = "32d02b0d9ac77a7876fa503fb261f052a22bffe84dead3af865af23fe4806a4a"
G4_CUTOVER_IMPORT_CODE = "G4-WRITE-SOURCE-CUTOVER-ISSUE292"
G5_RUNTIME_IMPORT_CODE = "G5-RUNTIME-SMOKE-ISSUE292"
G5_SOURCE_KIND = "runtime_smoke"
G5_SOURCE_REF = "issue-292-g5"
DSN_ENV_NAME = "EMPEROR_EVAL_PG_DSN"
RABBITMQ_ENV_NAMES = (
    "RABBITMQ_URL",
    "RABBITMQ_VHOST",
    "RABBITMQ_EXCHANGE",
    "RABBITMQ_QUEUE",
    "RABBITMQ_ROUTING_KEY",
    "RABBITMQ_PREFETCH",
    "RABBITMQ_TLS_ENABLED",
)
NETWORK_ALLOWLIST_ENV_NAME = "G5_NETWORK_SOURCE_ALLOWLIST"
NETWORK_PILOT_URL_ENV_NAME = "G5_NETWORK_PILOT_URL"
NETWORK_TIMEOUT_ENV_NAME = "G5_NETWORK_TIMEOUT_SECONDS"
EXPECTED_G3_SRC_HOST_CODES = ("zh.wikisource.org",)
SUPPORTED_MODES = (
    "contract-report",
    "execution-plan-json",
    "operator-checklist-md",
    "execute",
    "observe",
)
BOUNDARIES = (
    "G5 is approved for runtime credential, PostgreSQL, RabbitMQ, and allowlisted network smoke only.",
    "Default reports do not read .env, connect PostgreSQL, connect RabbitMQ, or access the network.",
    "Execute requires the G5 approval token, expected plan sha256, operator DSN, RabbitMQ settings, and network allowlist.",
    "Execute may write only a G5 imports audit marker after all smoke checks pass.",
    "No source, passage, evidence, cluster, anchor, relationship, scoring, ranking, or Epic 2 table is written.",
    "No long-running runtime, RabbitMQ worker, formal evidence, formal scoring, or formal ranking is started or released.",
)


def build_contract_report(*, source_root: Path = ROOT) -> dict[str, Any]:
    plan = render_execution_plan_json(source_root=source_root)
    return {
        "mode": "contract-report",
        "execution_version": EXECUTION_VERSION,
        "gate_status": "G5_APPROVED",
        "approval_token_required": True,
        "approval_token_value": APPROVAL_TOKEN,
        "supported_modes": list(SUPPORTED_MODES),
        "default_modes_side_effect_free": True,
        "default_modes_read_dotenv": False,
        "default_modes_connect_database": False,
        "default_modes_connect_rabbitmq": False,
        "default_modes_access_network": False,
        "dsn_env_name": DSN_ENV_NAME,
        "rabbitmq_env_names": list(RABBITMQ_ENV_NAMES),
        "network_allowlist_env_name": NETWORK_ALLOWLIST_ENV_NAME,
        "network_pilot_url_env_name": NETWORK_PILOT_URL_ENV_NAME,
        "network_timeout_env_name": NETWORK_TIMEOUT_ENV_NAME,
        "g5_approval_reference": G5_APPROVAL_REFERENCE,
        "boundary_source_pr": G5_BOUNDARY_SOURCE_PR,
        "boundary_head_sha": G5_BOUNDARY_HEAD_SHA,
        "boundary_merge_commit": G5_BOUNDARY_MERGE_COMMIT,
        "execution_plan_sha256": plan["execution_plan_sha256"],
        "runtime_marker": plan["runtime_marker"],
        "execution_completed_by_this_report": False,
        "post_apply_observation_completed_by_this_report": False,
        "next_user_gate": "G6_REQUIRED_BEFORE_FORMAL_EVIDENCE_RELEASE",
        "boundaries": list(BOUNDARIES),
    }


def render_execution_plan_json(*, source_root: Path = ROOT) -> dict[str, Any]:
    plan: dict[str, Any] = {
        "mode": "execution-plan-json",
        "execution_version": EXECUTION_VERSION,
        "gate_status": "G5_APPROVED",
        "g5_approval_reference": G5_APPROVAL_REFERENCE,
        "boundary_source_pr": G5_BOUNDARY_SOURCE_PR,
        "boundary_head_sha": G5_BOUNDARY_HEAD_SHA,
        "boundary_merge_commit": G5_BOUNDARY_MERGE_COMMIT,
        "g3_execution_plan_sha256": G3_EXECUTION_PLAN_SHA256,
        "g4_cutover_plan_sha256": G4_CUTOVER_PLAN_SHA256,
        "preconditions": {
            "approval_token": APPROVAL_TOKEN,
            "expected_plan_sha256_required": True,
            "operator_dsn_required": DSN_ENV_NAME,
            "rabbitmq_settings_required": list(RABBITMQ_ENV_NAMES),
            "network_allowlist_required": NETWORK_ALLOWLIST_ENV_NAME,
            "network_pilot_url_required": NETWORK_PILOT_URL_ENV_NAME,
            "g3_src_hosts_readback_required": list(EXPECTED_G3_SRC_HOST_CODES),
            "g4_cutover_marker_readback_required": G4_CUTOVER_IMPORT_CODE,
        },
        "allowed_smoke_checks": [
            "postgres_runtime_connection_smoke",
            "rabbitmq_queue_exchange_binding_smoke",
            "outbox_dispatcher_worker_runtime_smoke",
            "allowlisted_network_ingestion_pilot",
            "runtime_observation_audit_marker",
        ],
        "runtime_marker": {
            "target_table": "imports",
            "code": G5_RUNTIME_IMPORT_CODE,
            "source_kind": G5_SOURCE_KIND,
            "source_ref": G5_SOURCE_REF,
            "status": "succeeded",
            "row_count": 1,
            "input_hash_source": "execution_plan_sha256",
        },
        "execute_write": {
            "write_kind": "idempotent_imports_marker_upsert",
            "target_tables": ["imports"],
            "business_target_tables_written": [],
            "repository_files_written": [],
            "requires_all_smoke_checks_to_pass": True,
        },
        "runtime_state_after_success": expected_runtime_state(),
        "followup_gate_boundaries": {
            "formal_evidence": "blocked_until_g6",
            "scoring_rules": "blocked_until_g7",
            "scoring_algorithm": "blocked_until_g8",
            "formal_publication": "blocked_until_g9",
            "destructive_cleanup": "blocked_until_g10",
            "epic_2_entry": "blocked_until_separate_ready_review",
            "source_passages_business_writes": "blocked_until_merge_policy_gate",
            "evidence_cluster_anchor_relationship_writes": "blocked_until_followup_business_table_gate",
        },
        "rollback_point": {
            "database_data_deletion_allowed_by_this_plan": False,
            "rabbitmq_topology_deletion_allowed_by_this_plan": False,
            "network_ingestion_promotion_allowed_by_this_plan": False,
            "action": "disable runtime settings and mark G5 runtime marker failed or superseded after explicit followup approval",
        },
        "boundaries": list(BOUNDARIES),
    }
    plan["execution_plan_sha256"] = stable_json_sha256(plan)
    return plan


def render_operator_checklist_md(*, source_root: Path = ROOT) -> str:
    plan = render_execution_plan_json(source_root=source_root)
    return "\n".join(
        [
            "# G5 Runtime Execution Operator Checklist",
            "",
            "- Confirm G5 approval is recorded in Issue #292.",
            f"- Confirm execution plan sha256 is `{plan['execution_plan_sha256']}`.",
            "- Confirm `EMPEROR_EVAL_PG_DSN` is set only in the operator environment.",
            "- Confirm RabbitMQ URL, vhost, exchange, queue, routing key, prefetch, and TLS flags are set.",
            "- Confirm `G5_NETWORK_SOURCE_ALLOWLIST` contains the host of `G5_NETWORK_PILOT_URL`.",
            "- Run `--execute` with the G5 approval token and expected plan sha256.",
            "- Confirm observation reads back G3 `src_hosts`, G4 cutover marker, and G5 runtime marker.",
            "- Do not start a long-running worker, publish formal evidence, publish scoring, publish ranking, or enter Epic 2.",
            "",
        ]
    )


def execute_runtime(
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
    config_failures = operator_config_failures(config)
    if config_failures:
        return build_blocked_execution_report(
            plan,
            config_failures,
            failure_stage="operator_configuration",
            operator_config_read=True,
            operator_config_status=config.status_report(),
        )

    assert config.dsn is not None
    try:
        with connect_to_database(config.dsn) as conn:
            postgres_smoke = observe_postgres_runtime_prerequisites(conn, plan)
            if not postgres_smoke["observation_passed"]:
                return build_blocked_execution_report(
                    plan,
                    ["blocked_postgres_runtime_prerequisite_readback"],
                    failure_stage="postgres_observation",
                    operator_config_read=True,
                    operator_config_status=config.status_report(),
                    postgres_runtime_smoke=postgres_smoke,
                )

            rabbitmq_smoke = run_rabbitmq_binding_smoke(config)
            if not rabbitmq_smoke["smoke_passed"]:
                return build_blocked_execution_report(
                    plan,
                    [rabbitmq_smoke["blocking_failure"]],
                    failure_stage="rabbitmq_smoke",
                    operator_config_read=True,
                    operator_config_status=config.status_report(),
                    postgres_runtime_smoke=postgres_smoke,
                    rabbitmq_smoke=rabbitmq_smoke,
                )

            runtime_smoke = run_outbox_worker_smoke()
            if not runtime_smoke["smoke_passed"]:
                return build_blocked_execution_report(
                    plan,
                    ["blocked_outbox_worker_runtime_smoke_failed"],
                    failure_stage="runtime_smoke",
                    operator_config_read=True,
                    operator_config_status=config.status_report(),
                    postgres_runtime_smoke=postgres_smoke,
                    rabbitmq_smoke=rabbitmq_smoke,
                    runtime_smoke=runtime_smoke,
                )

            network_smoke = run_network_ingestion_pilot(config)
            if not network_smoke["smoke_passed"]:
                return build_blocked_execution_report(
                    plan,
                    [network_smoke["blocking_failure"]],
                    failure_stage="network_ingestion_pilot",
                    operator_config_read=True,
                    operator_config_status=config.status_report(),
                    postgres_runtime_smoke=postgres_smoke,
                    rabbitmq_smoke=rabbitmq_smoke,
                    runtime_smoke=runtime_smoke,
                    network_smoke=network_smoke,
                )

            write_runtime_marker(conn, plan, postgres_smoke, rabbitmq_smoke, runtime_smoke, network_smoke)
            observation = observe_runtime_state(conn, plan)
            conn.commit()
    except Exception as exc:  # pragma: no cover - adapter-specific.
        return {
            **base_execution_report(plan),
            "mode": "execute-report",
            "execution_status": "failed",
            "failure_stage": "runtime_adapter",
            "blocking_failures": ["runtime_adapter_error"],
            "operator_config_read": True,
            "operator_config_status": config.status_report(),
            "error": redact_secret(str(exc)),
            "runtime_marker_written": False,
            "post_apply_observation": None,
            "post_apply_observation_completed": False,
            "g5_runtime_executed": False,
            **unexecuted_runtime_state(),
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
        "runtime_marker_written": True,
        "post_apply_observation": observation,
        "post_apply_observation_completed": True,
        "g5_runtime_executed": passed,
        **(expected_runtime_state() if passed else unexecuted_runtime_state()),
    }


def observe_runtime(
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
            observation = observe_runtime_state(conn, plan)
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
            "g5_runtime_executed": False,
            **unexecuted_runtime_state(),
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
        "g5_runtime_executed": False,
        **(expected_runtime_state() if passed else unexecuted_runtime_state()),
    }


def pre_execution_failures(
    approval_token: str | None,
    expected_plan_sha256: str | None,
    plan: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    if approval_token != APPROVAL_TOKEN:
        failures.append("blocked_missing_or_invalid_g5_approval_token")
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
    postgres_runtime_smoke: Mapping[str, Any] | None = None,
    rabbitmq_smoke: Mapping[str, Any] | None = None,
    runtime_smoke: Mapping[str, Any] | None = None,
    network_smoke: Mapping[str, Any] | None = None,
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
        "postgres_runtime_smoke": postgres_runtime_smoke,
        "rabbitmq_smoke": rabbitmq_smoke,
        "runtime_smoke": runtime_smoke,
        "network_smoke": network_smoke,
        "runtime_marker_written": False,
        "post_apply_observation": None,
        "post_apply_observation_completed": False,
        "g5_runtime_executed": False,
        **unexecuted_runtime_state(),
    }


def base_execution_report(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "execution_version": EXECUTION_VERSION,
        "gate_status": "G5_APPROVED",
        "g5_approval_reference": G5_APPROVAL_REFERENCE,
        "boundary_source_pr": G5_BOUNDARY_SOURCE_PR,
        "boundary_head_sha": G5_BOUNDARY_HEAD_SHA,
        "boundary_merge_commit": G5_BOUNDARY_MERGE_COMMIT,
        "execution_plan_sha256": plan["execution_plan_sha256"],
        "runtime_marker": plan["runtime_marker"],
        "next_user_gate": "G6_REQUIRED_BEFORE_FORMAL_EVIDENCE_RELEASE",
        "boundaries": list(BOUNDARIES),
    }


class OperatorConfig:
    def __init__(self, values: Mapping[str, str]) -> None:
        self.dsn = values.get(DSN_ENV_NAME)
        self.rabbitmq = {name: values.get(name) for name in RABBITMQ_ENV_NAMES}
        self.network_allowlist = parse_csv(values.get(NETWORK_ALLOWLIST_ENV_NAME))
        self.network_pilot_url = values.get(NETWORK_PILOT_URL_ENV_NAME)
        self.network_timeout_seconds = parse_float(values.get(NETWORK_TIMEOUT_ENV_NAME), default=5.0)

    def status_report(self) -> dict[str, Any]:
        pilot_host = parsed_url_host(self.network_pilot_url)
        return {
            "dsn_present": bool(self.dsn),
            "rabbitmq_settings_present": {
                key: bool(value)
                for key, value in self.rabbitmq.items()
            },
            "network_allowlist_hosts": list(self.network_allowlist),
            "network_pilot_host": pilot_host,
            "network_timeout_seconds": self.network_timeout_seconds,
        }


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


def operator_config_failures(config: OperatorConfig) -> list[str]:
    failures: list[str] = []
    if not config.dsn:
        failures.append("blocked_missing_dsn")
    for name in RABBITMQ_ENV_NAMES:
        if not config.rabbitmq.get(name):
            failures.append(f"blocked_missing_{name.lower()}")
    if not config.network_allowlist:
        failures.append("blocked_missing_g5_network_source_allowlist")
    if not config.network_pilot_url:
        failures.append("blocked_missing_g5_network_pilot_url")
    host = parsed_url_host(config.network_pilot_url)
    if config.network_pilot_url and not host:
        failures.append("blocked_invalid_g5_network_pilot_url")
    if host and host not in config.network_allowlist:
        failures.append("blocked_network_pilot_host_not_allowlisted")
    return failures


def observe_postgres_runtime_prerequisites(conn: Any, plan: Mapping[str, Any]) -> dict[str, Any]:
    g3_observation = observe_g3_src_hosts(conn, EXPECTED_G3_SRC_HOST_CODES)
    g4_marker = observe_import_marker(conn, G4_CUTOVER_IMPORT_CODE)
    g4_marker_passed = (
        g4_marker is not None
        and g4_marker["status"] == "succeeded"
        and g4_marker["input_hash"] == G4_CUTOVER_PLAN_SHA256
        and g4_marker["meta"].get("canonical_write_source") == "postgresql"
        and g4_marker["meta"].get("jsonl_write_frozen") is True
        and g4_marker["meta"].get("postgres_unique_write_source") is True
    )
    return {
        "smoke": "postgres_runtime_connection_smoke",
        "g3_src_hosts_observation": g3_observation,
        "g4_cutover_marker": g4_marker,
        "g4_cutover_marker_passed": g4_marker_passed,
        "observation_passed": g3_observation["observation_passed"] and g4_marker_passed,
    }


def run_rabbitmq_binding_smoke(config: OperatorConfig) -> dict[str, Any]:
    try:
        import pika  # type: ignore[import-not-found]
    except Exception:
        return {
            "smoke": "rabbitmq_queue_exchange_binding_smoke",
            "smoke_passed": False,
            "blocking_failure": "blocked_missing_rabbitmq_client_pika",
        }

    try:
        connection = pika.BlockingConnection(pika.URLParameters(str(config.rabbitmq["RABBITMQ_URL"])))
        channel = connection.channel()
        channel.exchange_declare(exchange=str(config.rabbitmq["RABBITMQ_EXCHANGE"]), exchange_type="direct", passive=True)
        channel.queue_declare(queue=str(config.rabbitmq["RABBITMQ_QUEUE"]), passive=True)
        channel.queue_bind(
            queue=str(config.rabbitmq["RABBITMQ_QUEUE"]),
            exchange=str(config.rabbitmq["RABBITMQ_EXCHANGE"]),
            routing_key=str(config.rabbitmq["RABBITMQ_ROUTING_KEY"]),
        )
        connection.close()
    except Exception as exc:
        return {
            "smoke": "rabbitmq_queue_exchange_binding_smoke",
            "smoke_passed": False,
            "blocking_failure": "blocked_rabbitmq_binding_smoke_failed",
            "error": redact_secret(str(exc)),
        }
    return {
        "smoke": "rabbitmq_queue_exchange_binding_smoke",
        "smoke_passed": True,
        "exchange": config.rabbitmq["RABBITMQ_EXCHANGE"],
        "queue": config.rabbitmq["RABBITMQ_QUEUE"],
        "routing_key": config.rabbitmq["RABBITMQ_ROUTING_KEY"],
    }


def run_outbox_worker_smoke() -> dict[str, Any]:
    repository = FakeRepository(
        outbox=[
            OutboxMessage(
                id=1,
                code="g5-runtime-smoke-outbox",
                event_kind="review_notify",
                aggregate_type="jobs",
                aggregate_id=1,
                payload={"job_id": 1, "kind": "review_notify", "schema_ver": "v1", "trace_id": "g5-smoke"},
                attempts=0,
            )
        ],
        jobs=[JobRecord(id=1, kind="review_notify", schema_ver="v1", status="ready", trace_id="g5-smoke")],
    )
    dispatcher = OutboxDispatcher(repository, FakePublisher())
    dispatch_report = dispatcher.dispatch_once(limit=1)
    delivery = FakeAckableMessage(JobMessage(job_id=1, kind="review_notify", schema_ver="v1", trace_id="g5-smoke"))
    runtime = WorkerRuntime(
        repository,
        lambda job_id: {"job_id": job_id, "runtime_smoke": "succeeded"},
        worker_id="g5-smoke-worker",
    )
    runtime.process(delivery)
    passed = (
        dispatch_report.seen == 1
        and dispatch_report.published == 1
        and dispatch_report.failed == 0
        and repository.jobs[1].status == "succeeded"
        and delivery.actions == [("ack", None)]
    )
    return {
        "smoke": "outbox_dispatcher_worker_runtime_smoke",
        "smoke_passed": passed,
        "dispatch_report": {
            "seen": dispatch_report.seen,
            "published": dispatch_report.published,
            "failed": dispatch_report.failed,
        },
        "worker_actions": list(delivery.actions),
        "job_status": repository.jobs[1].status,
    }


def run_network_ingestion_pilot(config: OperatorConfig) -> dict[str, Any]:
    assert config.network_pilot_url is not None
    host = parsed_url_host(config.network_pilot_url)
    if not host or host not in config.network_allowlist:
        return {
            "smoke": "allowlisted_network_ingestion_pilot",
            "smoke_passed": False,
            "blocking_failure": "blocked_network_pilot_host_not_allowlisted",
            "network_pilot_host": host,
        }
    request = urllib.request.Request(
        config.network_pilot_url,
        method="HEAD",
        headers={"User-Agent": "emperor-evaluation-g5-runtime-smoke/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=config.network_timeout_seconds) as response:
            status = getattr(response, "status", response.getcode())
    except urllib.error.HTTPError as exc:
        status = exc.code
    except Exception as exc:
        return {
            "smoke": "allowlisted_network_ingestion_pilot",
            "smoke_passed": False,
            "blocking_failure": "blocked_network_ingestion_pilot_failed",
            "network_pilot_host": host,
            "error": redact_secret(str(exc)),
        }
    return {
        "smoke": "allowlisted_network_ingestion_pilot",
        "smoke_passed": 200 <= int(status) < 500,
        "blocking_failure": None if 200 <= int(status) < 500 else "blocked_network_ingestion_pilot_failed",
        "network_pilot_host": host,
        "http_status": int(status),
    }


def write_runtime_marker(
    conn: Any,
    plan: Mapping[str, Any],
    postgres_smoke: Mapping[str, Any],
    rabbitmq_smoke: Mapping[str, Any],
    runtime_smoke: Mapping[str, Any],
    network_smoke: Mapping[str, Any],
) -> None:
    meta = marker_meta(plan, postgres_smoke, rabbitmq_smoke, runtime_smoke, network_smoke)
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
                G5_RUNTIME_IMPORT_CODE,
                G5_SOURCE_KIND,
                G5_SOURCE_REF,
                "succeeded",
                EXECUTION_VERSION,
                plan["execution_plan_sha256"],
                1,
                json.dumps(meta, ensure_ascii=False, sort_keys=True),
            ),
        )
        cur.fetchone()


def observe_runtime_state(conn: Any, plan: Mapping[str, Any]) -> dict[str, Any]:
    postgres_smoke = observe_postgres_runtime_prerequisites(conn, plan)
    marker = observe_import_marker(conn, G5_RUNTIME_IMPORT_CODE)
    marker_passed = (
        marker is not None
        and marker["status"] == "succeeded"
        and marker["input_hash"] == plan["execution_plan_sha256"]
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
        "postgres_runtime_smoke": postgres_smoke,
        "observation_passed": marker_passed and postgres_smoke["observation_passed"],
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
        "target_table": "src_hosts",
        "expected_codes": expected,
        "observed_codes": observed_codes,
        "expected_row_count": len(expected),
        "observed_row_count": len(observed_codes),
        "missing_codes": [code for code in expected if code not in observed_codes],
        "unexpected_codes": [code for code in observed_codes if code not in expected],
        "rows": observed,
        "observation_passed": observed_codes == expected,
    }


def marker_meta(
    plan: Mapping[str, Any],
    postgres_smoke: Mapping[str, Any],
    rabbitmq_smoke: Mapping[str, Any],
    runtime_smoke: Mapping[str, Any],
    network_smoke: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        **expected_runtime_state(),
        "execution_version": EXECUTION_VERSION,
        "g5_approval_reference": G5_APPROVAL_REFERENCE,
        "boundary_source_pr": G5_BOUNDARY_SOURCE_PR,
        "boundary_head_sha": G5_BOUNDARY_HEAD_SHA,
        "boundary_merge_commit": G5_BOUNDARY_MERGE_COMMIT,
        "g3_execution_plan_sha256": G3_EXECUTION_PLAN_SHA256,
        "g4_cutover_plan_sha256": G4_CUTOVER_PLAN_SHA256,
        "execution_plan_sha256": plan["execution_plan_sha256"],
        "runtime_marker_code": G5_RUNTIME_IMPORT_CODE,
        "postgres_runtime_smoke_passed": postgres_smoke["observation_passed"],
        "rabbitmq_smoke_passed": rabbitmq_smoke["smoke_passed"],
        "outbox_worker_smoke_passed": runtime_smoke["smoke_passed"],
        "network_ingestion_pilot_passed": network_smoke["smoke_passed"],
    }


def expected_runtime_state() -> dict[str, Any]:
    return {
        "canonical_write_source": "postgresql",
        "jsonl_write_frozen": True,
        "postgres_unique_write_source": True,
        "production_credentials_enabled": True,
        "rabbitmq_live": True,
        "network_ingestion_live": True,
        "production_runtime_live": True,
        "formal_evidence_released": False,
        "formal_scoring_released": False,
        "formal_ranking_released": False,
        "epic_2_entered": False,
    }


def unexecuted_runtime_state() -> dict[str, Any]:
    return {
        "canonical_write_source": "postgresql",
        "jsonl_write_frozen": True,
        "postgres_unique_write_source": True,
        "production_credentials_enabled": False,
        "rabbitmq_live": False,
        "network_ingestion_live": False,
        "production_runtime_live": False,
        "formal_evidence_released": False,
        "formal_scoring_released": False,
        "formal_ranking_released": False,
        "epic_2_entered": False,
    }


def connect_to_database(dsn: str) -> Any:
    import psycopg

    return psycopg.connect(dsn)


def stable_json_sha256(payload: Mapping[str, Any]) -> str:
    return _stable_json_sha256(payload, omit_key="execution_plan_sha256")


def parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_float(value: str | None, *, default: float) -> float:
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def parsed_url_host(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return None
    return parsed.hostname


def redact_secret(text: str) -> str:
    return redact_connection_secrets(text)


def report_as_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build or execute the Epic 1 G5 runtime package.")
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
        report = execute_runtime(
            approval_token=args.approval_token,
            expected_plan_sha256=args.expected_plan_sha256,
            source_root=args.source_root,
        )
    elif args.observe:
        report = observe_runtime(
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
