from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v3_contracts import (
    NON_CORE_RETRIEVAL_RULES,
    PROCESS_DOC_PATH,
    coverage_matrix_template,
)
from scripts.dev.retrieval_v3_pg_schema import (
    DEFAULT_PG_SCHEMA,
    DEFAULT_V3_DSN_ENV,
    render_sql,
    schema_cursor,
)


DEFAULT_SCHEMA_PATH = ROOT / "db" / "migrations" / "20260704_retrieval_v3_control_plane.sql"
DEFAULT_SCHEMA_PATHS = (
    DEFAULT_SCHEMA_PATH,
    ROOT / "db" / "migrations" / "20260705_retrieval_v3_consumption.sql",
    ROOT / "db" / "migrations" / "20260706_retrieval_v3_item_rule_score_weights.sql",
    ROOT / "db" / "migrations" / "20260707_retrieval_v3_candidate_lanes.sql",
    ROOT / "db" / "migrations" / "20260708_retrieval_v3_claim_cache.sql",
    ROOT / "db" / "migrations" / "20260709_retrieval_v3_claim_event_groups.sql",
    ROOT / "db" / "migrations" / "20260708_retrieval_v3_claim_extraction_jobs.sql",
    ROOT / "db" / "migrations" / "20260708_retrieval_v3_object_source_cache_jobs.sql",
)
DEFAULT_SOURCE_DSN_ENV = "EMPEROR_EVAL_RETRIEVAL_V3_DSN"
DEFAULT_TARGET_DSN_ENV = DEFAULT_V3_DSN_ENV
DEFAULT_CONTRACT_CODE = "I5B-RETRIEVAL-V2-20260704"


class RetrievalV3BootstrapError(RuntimeError):
    pass


@dataclass(frozen=True)
class SourceSnapshot:
    item_rows: list[dict[str, Any]]
    rule_rows: list[dict[str, Any]]
    material_policy_rows: list[dict[str, Any]]
    predicate_option_rows: list[dict[str, Any]]
    factor_rows: list[dict[str, Any]] = field(default_factory=list)
    factor_option_rows: list[dict[str, Any]] = field(default_factory=list)

    @property
    def fingerprint(self) -> str:
        return stable_fingerprint(
            {
                "items": self.item_rows,
                "rules": self.rule_rows,
                "material_policies": self.material_policy_rows,
                "predicate_options": self.predicate_option_rows,
                "factors": self.factor_rows,
                "factor_options": self.factor_option_rows,
            }
        )


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def stable_fingerprint(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def normalize_alias(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()


def code_hash(value: str, *, length: int = 12) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length].upper()


def read_schema_sql(path: Path | None = None, *, schema_name: str = DEFAULT_PG_SCHEMA) -> str:
    paths = (path,) if path is not None else DEFAULT_SCHEMA_PATHS
    chunks: list[str] = []
    for schema_path in paths:
        if not schema_path.exists():
            raise RetrievalV3BootstrapError(f"schema file missing: {schema_path}")
        chunks.append(schema_path.read_text(encoding="utf-8").rstrip())
    return render_sql("\n\n".join(chunks) + "\n", schema_name=schema_name)


def resolve_dsn(env_name: str) -> str:
    value = os.environ.get(env_name)
    if not value:
        raise RetrievalV3BootstrapError(f"missing PostgreSQL DSN env var: {env_name}")
    return value


def load_env_file(path: Path) -> list[str]:
    if not path.exists():
        raise RetrievalV3BootstrapError(f"env file missing: {path}")
    loaded: list[str] = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value
        loaded.append(key)
    return loaded


def import_psycopg():
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ModuleNotFoundError as exc:  # pragma: no cover - environment guard
        raise RetrievalV3BootstrapError("psycopg is required for live retrieval_v3 bootstrap") from exc
    return psycopg, dict_row


def table_exists(cur: Any, table_name: str) -> bool:
    cur.execute("select to_regclass(%s) is not null as exists", (f"public.{table_name}",))
    row = cur.fetchone()
    return bool(row["exists"])


def fetch_json_rows(cur: Any, sql: str, params: Sequence[Any]) -> list[dict[str, Any]]:
    cur.execute(sql, params)
    rows: list[dict[str, Any]] = []
    for row in cur.fetchall():
        payload = row["row"]
        if not isinstance(payload, dict):
            raise RetrievalV3BootstrapError("expected PostgreSQL to_jsonb(row) payload to decode as object")
        rows.append(payload)
    return rows


def fetch_source_snapshot(source_dsn: str, *, item_code: str) -> SourceSnapshot:
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(source_dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            if not table_exists(cur, "eval_items") or not table_exists(cur, "eval_rules"):
                raise RetrievalV3BootstrapError("source database must contain public.eval_items and public.eval_rules")
            item_rows = fetch_json_rows(
                cur,
                """
                select to_jsonb(i) as row
                  from public.eval_items i
                 where i.item_code = %s
                 order by i.id
                """,
                (item_code,),
            )
            if not item_rows:
                raise RetrievalV3BootstrapError(f"source database has no eval_items row for item_code={item_code}")
            rule_rows = fetch_json_rows(
                cur,
                """
                select to_jsonb(r) || jsonb_build_object('item_code', i.item_code) as row
                  from public.eval_rules r
                  join public.eval_items i on i.id = r.item_id
                 where i.item_code = %s
                 order by r.id
                """,
                (item_code,),
            )
            material_policy_rows: list[dict[str, Any]] = []
            if table_exists(cur, "eval_rule_material_policies"):
                material_policy_rows = fetch_json_rows(
                    cur,
                    """
                    select to_jsonb(p) as row
                      from public.eval_rule_material_policies p
                     where p.item_code = %s
                        or p.item_id in (select i.id from public.eval_items i where i.item_code = %s)
                     order by p.selection_priority, p.id
                    """,
                    (item_code, item_code),
                )
            factor_rows: list[dict[str, Any]] = []
            factor_option_rows: list[dict[str, Any]] = []
            if table_exists(cur, "eval_rule_factors"):
                factor_rows = fetch_json_rows(
                    cur,
                    """
                    select to_jsonb(f) as row
                      from public.eval_rule_factors f
                     where f.item_code = %s
                        or f.item_id in (select i.id from public.eval_items i where i.item_code = %s)
                     order by f.formula_code, f.rule_code, f.factor_scope, f.factor_name, f.id
                    """,
                    (item_code, item_code),
                )
            if table_exists(cur, "eval_rule_factors") and table_exists(cur, "eval_rule_factor_options"):
                factor_option_rows = fetch_json_rows(
                    cur,
                    """
                    select to_jsonb(o) || jsonb_build_object(
                               'item_code', f.item_code,
                               'rule_code', f.rule_code,
                               'formula_code', f.formula_code,
                               'factor_name', f.factor_name,
                               'factor_scope', f.factor_scope
                           ) as row
                      from public.eval_rule_factor_options o
                      join public.eval_rule_factors f on f.id = o.factor_id
                     where f.item_code = %s
                        or f.item_id in (select i.id from public.eval_items i where i.item_code = %s)
                     order by f.formula_code, f.rule_code, f.factor_name, o.sort_no, o.id
                    """,
                    (item_code, item_code),
                )
            predicate_option_rows: list[dict[str, Any]] = []
            if table_exists(cur, "fact_relation_predicate_options"):
                predicate_option_rows = fetch_json_rows(
                    cur,
                    """
                    select to_jsonb(p) as row
                      from public.fact_relation_predicate_options p
                     where p.item_code = %s
                        or p.item_id in (select i.id from public.eval_items i where i.item_code = %s)
                     order by p.rule_code, p.scoring_role, p.predicate, p.id
                    """,
                    (item_code, item_code),
                )
    return SourceSnapshot(
        item_rows=item_rows,
        rule_rows=rule_rows,
        material_policy_rows=material_policy_rows,
        predicate_option_rows=predicate_option_rows,
        factor_rows=factor_rows,
        factor_option_rows=factor_option_rows,
    )


def text_from(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return ""


def int_from(row: Mapping[str, Any], *keys: str, default: int = 100) -> int:
    for key in keys:
        value = row.get(key)
        if value is None or value == "":
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return default


def list_from(row: Mapping[str, Any], key: str) -> list[str]:
    value = row.get(key)
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def json_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str) and value.strip():
        payload = json.loads(value)
        if isinstance(payload, Mapping):
            return dict(payload)
    return {}


def json_param(value: Any) -> str:
    return stable_json(value)


def upsert_item(cur: Any, row: Mapping[str, Any]) -> int:
    item_code = text_from(row, "item_code", "code")
    if not item_code:
        raise RetrievalV3BootstrapError(f"eval_items source row lacks item_code: {row}")
    cur.execute(
        """
        insert into retrieval_v3.eval_items (
            source_item_id, item_code, item_label, source_row, source_fingerprint
        )
        values (%s, %s, %s, %s::jsonb, %s)
        on conflict (source_item_id) do update set
            item_code = excluded.item_code,
            item_label = excluded.item_label,
            source_row = excluded.source_row,
            source_fingerprint = excluded.source_fingerprint,
            copied_at = now()
        returning id
        """,
        (
            int(row["id"]),
            item_code,
            text_from(row, "item_label", "label", "name", "title"),
            json_param(row),
            stable_fingerprint(row),
        ),
    )
    return int(cur.fetchone()["id"])


def upsert_rule(cur: Any, row: Mapping[str, Any], item_ids: Mapping[int, int]) -> int:
    source_item_id = int(row["item_id"])
    item_id = item_ids[source_item_id]
    rule_code = text_from(row, "rule_code", "code")
    if not rule_code:
        raise RetrievalV3BootstrapError(f"eval_rules source row lacks rule_code: {row}")
    cur.execute(
        """
        insert into retrieval_v3.eval_rules (
            item_id, source_rule_id, item_code, rule_code, rule_label, rule_status, source_row, source_fingerprint
        )
        values (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
        on conflict (source_rule_id) do update set
            item_id = excluded.item_id,
            item_code = excluded.item_code,
            rule_code = excluded.rule_code,
            rule_label = excluded.rule_label,
            rule_status = excluded.rule_status,
            source_row = excluded.source_row,
            source_fingerprint = excluded.source_fingerprint,
            copied_at = now()
        returning id
        """,
        (
            item_id,
            int(row["id"]),
            text_from(row, "item_code"),
            rule_code,
            text_from(row, "rule_label", "label", "name", "title"),
            text_from(row, "status", "lifecycle_status") or "active",
            json_param(row),
            stable_fingerprint(row),
        ),
    )
    return int(cur.fetchone()["id"])


def upsert_factor(cur: Any, row: Mapping[str, Any], item_ids: Mapping[int, int], rule_ids_by_code: Mapping[str, int]) -> int:
    source_item_id = int(row["item_id"])
    item_id = item_ids[source_item_id]
    rule_code = text_from(row, "rule_code")
    cur.execute(
        """
        insert into retrieval_v3.eval_rule_factors (
            item_id, source_factor_id, item_code, rule_id, rule_code, formula_code,
            factor_name, factor_scope, value_source, source_doc, source_heading,
            description, factor_status, source_row, source_fingerprint
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
        on conflict (source_factor_id) do update set
            item_id = excluded.item_id,
            item_code = excluded.item_code,
            rule_id = excluded.rule_id,
            rule_code = excluded.rule_code,
            formula_code = excluded.formula_code,
            factor_name = excluded.factor_name,
            factor_scope = excluded.factor_scope,
            value_source = excluded.value_source,
            source_doc = excluded.source_doc,
            source_heading = excluded.source_heading,
            description = excluded.description,
            factor_status = excluded.factor_status,
            source_row = excluded.source_row,
            source_fingerprint = excluded.source_fingerprint,
            copied_at = now()
        returning id
        """,
        (
            item_id,
            int(row["id"]),
            text_from(row, "item_code"),
            rule_ids_by_code.get(rule_code) if rule_code else None,
            rule_code,
            text_from(row, "formula_code"),
            text_from(row, "factor_name"),
            text_from(row, "factor_scope") or "rule",
            text_from(row, "value_source") or "markdown",
            text_from(row, "source_doc"),
            text_from(row, "source_heading"),
            text_from(row, "description"),
            text_from(row, "status") or "active",
            json_param(row),
            stable_fingerprint(row),
        ),
    )
    return int(cur.fetchone()["id"])


def upsert_factor_option(cur: Any, row: Mapping[str, Any], factor_ids_by_source: Mapping[int, int]) -> int:
    source_factor_id = int(row["factor_id"])
    factor_id = factor_ids_by_source[source_factor_id]
    cur.execute(
        """
        insert into retrieval_v3.eval_rule_factor_options (
            factor_id, source_option_id, option_code, label, value_num, sort_no,
            option_note, source_doc, source_line, option_status, source_row, source_fingerprint
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
        on conflict (source_option_id) do update set
            factor_id = excluded.factor_id,
            option_code = excluded.option_code,
            label = excluded.label,
            value_num = excluded.value_num,
            sort_no = excluded.sort_no,
            option_note = excluded.option_note,
            source_doc = excluded.source_doc,
            source_line = excluded.source_line,
            option_status = excluded.option_status,
            source_row = excluded.source_row,
            source_fingerprint = excluded.source_fingerprint,
            copied_at = now()
        returning id
        """,
        (
            factor_id,
            int(row["id"]),
            text_from(row, "option_code"),
            text_from(row, "label"),
            row.get("value_num"),
            int_from(row, "sort_no", default=0),
            text_from(row, "note"),
            text_from(row, "source_doc"),
            row.get("source_line"),
            text_from(row, "status") or "active",
            json_param(row),
            stable_fingerprint(row),
        ),
    )
    return int(cur.fetchone()["id"])


def upsert_material_policy(cur: Any, row: Mapping[str, Any], item_ids_by_code: Mapping[str, int], rule_ids_by_code: Mapping[str, int]) -> int:
    item_code = text_from(row, "item_code")
    rule_code = text_from(row, "rule_code")
    cur.execute(
        """
        insert into retrieval_v3.eval_rule_material_policies (
            item_id, rule_id, source_policy_id, item_code, rule_code, policy_code, policy_version,
            selection_priority, carrier_mode, material_source, allowed_scoring_roles, context_roles,
            disallowed_scored_obj_types, discouraged_scored_obj_types, candidate_obj_types,
            require_attrs, calc_detail_component_paths, single_scored_per_chain, policy_payload,
            policy_status, source_row, source_fingerprint
        )
        values (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s
        )
        on conflict (source_policy_id) do update set
            item_id = excluded.item_id,
            rule_id = excluded.rule_id,
            item_code = excluded.item_code,
            rule_code = excluded.rule_code,
            policy_code = excluded.policy_code,
            policy_version = excluded.policy_version,
            selection_priority = excluded.selection_priority,
            carrier_mode = excluded.carrier_mode,
            material_source = excluded.material_source,
            allowed_scoring_roles = excluded.allowed_scoring_roles,
            context_roles = excluded.context_roles,
            disallowed_scored_obj_types = excluded.disallowed_scored_obj_types,
            discouraged_scored_obj_types = excluded.discouraged_scored_obj_types,
            candidate_obj_types = excluded.candidate_obj_types,
            require_attrs = excluded.require_attrs,
            calc_detail_component_paths = excluded.calc_detail_component_paths,
            single_scored_per_chain = excluded.single_scored_per_chain,
            policy_payload = excluded.policy_payload,
            policy_status = excluded.policy_status,
            source_row = excluded.source_row,
            source_fingerprint = excluded.source_fingerprint,
            copied_at = now()
        returning id
        """,
        (
            item_ids_by_code.get(item_code),
            rule_ids_by_code.get(rule_code),
            int(row["id"]),
            item_code,
            rule_code,
            text_from(row, "policy_code"),
            text_from(row, "policy_version") or "v1",
            int_from(row, "selection_priority"),
            text_from(row, "carrier_mode"),
            text_from(row, "material_source"),
            list_from(row, "allowed_scoring_roles"),
            list_from(row, "context_roles"),
            list_from(row, "disallowed_scored_obj_types"),
            list_from(row, "discouraged_scored_obj_types"),
            list_from(row, "candidate_obj_types"),
            list_from(row, "require_attrs"),
            list_from(row, "calc_detail_component_paths"),
            bool(row.get("single_scored_per_chain") or False),
            json_param(row.get("policy_payload") or {}),
            text_from(row, "status") or "active",
            json_param(row),
            stable_fingerprint(row),
        ),
    )
    return int(cur.fetchone()["id"])


def upsert_predicate_option(cur: Any, row: Mapping[str, Any], item_ids_by_code: Mapping[str, int], rule_ids_by_code: Mapping[str, int]) -> int:
    item_code = text_from(row, "item_code")
    rule_code = text_from(row, "rule_code")
    cur.execute(
        """
        insert into retrieval_v3.fact_relation_predicate_options (
            item_id, rule_id, source_option_id, item_code, rule_code, scoring_role, predicate,
            relation_role, subject_obj_type, object_obj_type, direction, option_status, source_row, source_fingerprint
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
        on conflict (source_option_id) do update set
            item_id = excluded.item_id,
            rule_id = excluded.rule_id,
            item_code = excluded.item_code,
            rule_code = excluded.rule_code,
            scoring_role = excluded.scoring_role,
            predicate = excluded.predicate,
            relation_role = excluded.relation_role,
            subject_obj_type = excluded.subject_obj_type,
            object_obj_type = excluded.object_obj_type,
            direction = excluded.direction,
            option_status = excluded.option_status,
            source_row = excluded.source_row,
            source_fingerprint = excluded.source_fingerprint,
            copied_at = now()
        returning id
        """,
        (
            item_ids_by_code.get(item_code),
            rule_ids_by_code.get(rule_code),
            int(row["id"]),
            item_code,
            rule_code,
            text_from(row, "scoring_role"),
            text_from(row, "predicate"),
            text_from(row, "relation_role"),
            text_from(row, "subject_obj_type"),
            text_from(row, "object_obj_type"),
            text_from(row, "direction"),
            text_from(row, "status") or "active",
            json_param(row),
            stable_fingerprint(row),
        ),
    )
    return int(cur.fetchone()["id"])


def contract_rule_payloads(snapshot: SourceSnapshot, rule_code: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    material = [row for row in snapshot.material_policy_rows if text_from(row, "rule_code") == rule_code]
    predicates = [row for row in snapshot.predicate_option_rows if text_from(row, "rule_code") == rule_code]
    return material, predicates


def rule_order(row: Mapping[str, Any], fallback: int) -> int:
    return int_from(row, "sort_order", "display_order", "rule_order", "order_index", default=fallback)


def requirement_payload(rule_code: str, material_rows: Sequence[Mapping[str, Any]], predicate_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    min_usable_claims = 1 if rule_code not in NON_CORE_RETRIEVAL_RULES else 0
    coverage_matrix = coverage_matrix_template(
        rule_code,
        material_policy_codes=(text_from(row, "policy_code") for row in material_rows),
        predicate_options=(text_from(row, "predicate", "predicate_code") for row in predicate_rows),
    )
    return {
        "binding_grain": "claim_rule_binding",
        "is_core_for_retrieval": rule_code not in NON_CORE_RETRIEVAL_RULES,
        "min_usable_claims": min_usable_claims,
        "material_policy_count": len(material_rows),
        "predicate_option_count": len(predicate_rows),
        "coverage_matrix": coverage_matrix,
        "secondary_rule_hints": coverage_matrix["secondary_rule_hints"],
        "gap_policy": {
            "gap_event_idempotent": True,
            "needs_refinement_is_worker_signal": True,
            "true_lack_requires_alias_and_source_exhaustion": True,
        },
        "clean_process_doc": PROCESS_DOC_PATH,
    }


def retrieval_intent_payload(
    *,
    emperor_name: str,
    item_code: str,
    rule_code: str,
    requirement: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "emperor": emperor_name,
        "item_code": item_code,
        "rule_code": rule_code,
        "intent_summary": "Find source-backed material claims that satisfy this rule contract.",
        "coverage_matrix": requirement.get("coverage_matrix") or {},
        "secondary_rule_hints": requirement.get("secondary_rule_hints") or [],
        "clean_input_policy": {
            "process_doc": PROCESS_DOC_PATH,
            "forbid_old_source_packs": True,
            "forbid_old_object_pool_results": True,
            "forbid_old_judgement_outputs": True,
            "judge_stage_no_network": True,
            "judge_stage_no_memory": True,
        },
    }


def upsert_contract(cur: Any, *, snapshot: SourceSnapshot, item_code: str, contract_code: str, source_database_label: str) -> int:
    payload = {
        "source_tables": {
            "eval_items": len(snapshot.item_rows),
            "eval_rules": len(snapshot.rule_rows),
            "eval_rule_factors": len(snapshot.factor_rows),
            "eval_rule_factor_options": len(snapshot.factor_option_rows),
            "eval_rule_material_policies": len(snapshot.material_policy_rows),
            "fact_relation_predicate_options": len(snapshot.predicate_option_rows),
        },
        "tool": "scripts/dev/retrieval_v3_bootstrap.py",
    }
    cur.execute(
        """
        insert into retrieval_v3.rule_contracts (
            contract_code, item_code, source_database_label, source_fingerprint, contract_payload, status
        )
        values (%s, %s, %s, %s, %s::jsonb, 'active')
        on conflict (contract_code) do update set
            item_code = excluded.item_code,
            source_database_label = excluded.source_database_label,
            source_snapshot_at = now(),
            source_fingerprint = excluded.source_fingerprint,
            contract_payload = excluded.contract_payload,
            status = excluded.status,
            updated_at = now()
        returning id
        """,
        (contract_code, item_code, source_database_label, snapshot.fingerprint, json_param(payload)),
    )
    return int(cur.fetchone()["id"])


def upsert_contract_rules(
    cur: Any,
    *,
    snapshot: SourceSnapshot,
    contract_id: int,
    rule_ids_by_code: Mapping[str, int],
) -> int:
    count = 0
    for index, row in enumerate(snapshot.rule_rows, start=1):
        rule_code = text_from(row, "rule_code", "code")
        material_rows, predicate_rows = contract_rule_payloads(snapshot, rule_code)
        requirement = requirement_payload(rule_code, material_rows, predicate_rows)
        source_payload = {
            "rule": row,
            "material_policies": material_rows,
            "predicate_options": predicate_rows,
            "requirement": requirement,
        }
        cur.execute(
            """
            insert into retrieval_v3.rule_contract_rules (
                contract_id, rule_id, rule_code, rule_label, rule_order, is_core_for_retrieval,
                material_policy_payload, predicate_policy_payload, requirement_payload, source_fingerprint
            )
            values (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s)
            on conflict (contract_id, rule_code) do update set
                rule_id = excluded.rule_id,
                rule_label = excluded.rule_label,
                rule_order = excluded.rule_order,
                is_core_for_retrieval = excluded.is_core_for_retrieval,
                material_policy_payload = excluded.material_policy_payload,
                predicate_policy_payload = excluded.predicate_policy_payload,
                requirement_payload = excluded.requirement_payload,
                source_fingerprint = excluded.source_fingerprint
            """,
            (
                contract_id,
                rule_ids_by_code[rule_code],
                rule_code,
                text_from(row, "rule_label", "label", "name", "title"),
                rule_order(row, index * 10),
                bool(requirement["is_core_for_retrieval"]),
                json_param(material_rows),
                json_param(predicate_rows),
                json_param(requirement),
                stable_fingerprint(source_payload),
            ),
        )
        count += 1
    return count


def seed_target(cur: Any, *, emperor_name: str, item_code: str, contract_id: int, contract_code: str) -> dict[str, Any]:
    target_code = f"TGT-{item_code}-{code_hash(contract_code + ':' + emperor_name)}"
    payload = {"seed_source": "retrieval_v3_bootstrap", "contract_code": contract_code}
    cur.execute(
        """
        insert into retrieval_v3.retrieval_targets (
            target_code, emperor_name, item_code, contract_id, target_payload
        )
        values (%s, %s, %s, %s, %s::jsonb)
        on conflict (contract_id, emperor_name) do update set
            target_code = excluded.target_code,
            item_code = excluded.item_code,
            target_payload = retrieval_v3.retrieval_targets.target_payload || excluded.target_payload,
            updated_at = now()
        returning id, target_code
        """,
        (target_code, emperor_name, item_code, contract_id, json_param(payload)),
    )
    target_row = cur.fetchone()
    target_id = int(target_row["id"])
    cur.execute(
        """
        insert into retrieval_v3.target_aliases (target_id, alias, alias_type, norm_alias, source)
        values (%s, %s, 'name', %s, 'seed')
        on conflict (target_id, alias_type, norm_alias) do update set
            alias = excluded.alias,
            status = 'active'
        """,
        (target_id, emperor_name, normalize_alias(emperor_name)),
    )
    cur.execute(
        """
        select id, rule_code, rule_order, is_core_for_retrieval, requirement_payload
          from retrieval_v3.rule_contract_rules
         where contract_id = %s
         order by rule_order, rule_code
        """,
        (contract_id,),
    )
    requirement_count = 0
    intent_count = 0
    for rule in cur.fetchall():
        requirement = json_mapping(rule["requirement_payload"])
        min_claims = int(requirement.get("min_usable_claims") or (1 if bool(rule["is_core_for_retrieval"]) else 0))
        cur.execute(
            """
            insert into retrieval_v3.target_rule_requirements (
                target_id, contract_rule_id, priority, min_usable_claims, requirement_payload
            )
            values (%s, %s, %s, %s, %s::jsonb)
            on conflict (target_id, contract_rule_id) do update set
                priority = excluded.priority,
                min_usable_claims = excluded.min_usable_claims,
                requirement_payload = excluded.requirement_payload,
                requirement_status = 'active',
                updated_at = now()
            returning id
            """,
            (
                target_id,
                int(rule["id"]),
                int(rule["rule_order"]),
                min_claims,
                json_param(requirement),
            ),
        )
        requirement_id = int(cur.fetchone()["id"])
        requirement_count += 1
        intent_code = f"INT-{item_code}-{code_hash(contract_code + ':' + emperor_name + ':' + rule['rule_code'])}"
        intent_payload = retrieval_intent_payload(
            emperor_name=emperor_name,
            item_code=item_code,
            rule_code=str(rule["rule_code"]),
            requirement=requirement,
        )
        cur.execute(
            """
            insert into retrieval_v3.retrieval_intents (
                intent_code, target_id, contract_rule_id, target_rule_requirement_id, priority, intent_payload
            )
            values (%s, %s, %s, %s, %s, %s::jsonb)
            on conflict (intent_code) do update set
                target_id = excluded.target_id,
                contract_rule_id = excluded.contract_rule_id,
                target_rule_requirement_id = excluded.target_rule_requirement_id,
                priority = excluded.priority,
                intent_payload = excluded.intent_payload,
                status = 'ready',
                updated_at = now()
            """,
            (intent_code, target_id, int(rule["id"]), requirement_id, int(rule["rule_order"]), json_param(intent_payload)),
        )
        intent_count += 1
    return {
        "emperor": emperor_name,
        "target_code": target_row["target_code"],
        "requirements": requirement_count,
        "retrieval_intents": intent_count,
    }


def apply_schema(target_dsn: str, *, schema_path: Path | None = None, schema_name: str = DEFAULT_PG_SCHEMA) -> None:
    psycopg, dict_row = import_psycopg()
    sql = read_schema_sql(schema_path, schema_name=schema_name)
    with psycopg.connect(target_dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()


def copy_rule_contract(
    *,
    source_dsn: str,
    target_dsn: str,
    item_code: str,
    contract_code: str,
    source_database_label: str,
    seed_targets: Sequence[str],
    schema_name: str = DEFAULT_PG_SCHEMA,
) -> dict[str, Any]:
    snapshot = fetch_source_snapshot(source_dsn, item_code=item_code)
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(target_dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            item_ids_by_source = {int(row["id"]): upsert_item(cur, row) for row in snapshot.item_rows}
            item_ids_by_code = {text_from(row, "item_code", "code"): item_ids_by_source[int(row["id"])] for row in snapshot.item_rows}
            rule_ids_by_code: dict[str, int] = {}
            for row in snapshot.rule_rows:
                rule_id = upsert_rule(cur, row, item_ids_by_source)
                rule_ids_by_code[text_from(row, "rule_code", "code")] = rule_id
            factor_ids_by_source: dict[int, int] = {}
            factor_count = 0
            for row in snapshot.factor_rows:
                factor_id = upsert_factor(cur, row, item_ids_by_source, rule_ids_by_code)
                factor_ids_by_source[int(row["id"])] = factor_id
                factor_count += 1
            factor_option_count = 0
            for row in snapshot.factor_option_rows:
                upsert_factor_option(cur, row, factor_ids_by_source)
                factor_option_count += 1
            material_count = 0
            for row in snapshot.material_policy_rows:
                upsert_material_policy(cur, row, item_ids_by_code, rule_ids_by_code)
                material_count += 1
            predicate_count = 0
            for row in snapshot.predicate_option_rows:
                upsert_predicate_option(cur, row, item_ids_by_code, rule_ids_by_code)
                predicate_count += 1
            contract_id = upsert_contract(
                cur,
                snapshot=snapshot,
                item_code=item_code,
                contract_code=contract_code,
                source_database_label=source_database_label,
            )
            contract_rule_count = upsert_contract_rules(
                cur,
                snapshot=snapshot,
                contract_id=contract_id,
                rule_ids_by_code=rule_ids_by_code,
            )
            seeded_targets = [
                seed_target(
                    cur,
                    emperor_name=name,
                    item_code=item_code,
                    contract_id=contract_id,
                    contract_code=contract_code,
                )
                for name in seed_targets
            ]
        conn.commit()
    return {
        "ok": True,
        "contract_code": contract_code,
        "item_code": item_code,
        "source_fingerprint": snapshot.fingerprint,
        "copied": {
            "eval_items": len(snapshot.item_rows),
            "eval_rules": len(snapshot.rule_rows),
            "eval_rule_factors": factor_count,
            "eval_rule_factor_options": factor_option_count,
            "eval_rule_material_policies": material_count,
            "fact_relation_predicate_options": predicate_count,
            "rule_contract_rules": contract_rule_count,
        },
        "seeded_targets": seeded_targets,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap the retrieval_v3 source-pack control plane.")
    parser.add_argument("--schema-path", type=Path, default=None)
    parser.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    parser.add_argument("--print-schema", action="store_true", help="Print the retrieval_v3 SQL schema and exit.")
    parser.add_argument("--apply-schema", action="store_true", help="Apply the retrieval_v3 schema to the target DSN.")
    parser.add_argument("--copy-rule-contract", action="store_true", help="Copy item/rule/policy snapshots from source DSN to target DSN.")
    parser.add_argument("--env-file", type=Path, default=None, help="Load DSN environment variables from a local .env-style file.")
    parser.add_argument("--source-dsn-env", default=DEFAULT_SOURCE_DSN_ENV)
    parser.add_argument("--target-dsn-env", default=DEFAULT_TARGET_DSN_ENV)
    parser.add_argument("--item-code", default="I5B")
    parser.add_argument("--contract-code", default=DEFAULT_CONTRACT_CODE)
    parser.add_argument("--source-database-label", default="")
    parser.add_argument("--seed-target", action="append", default=[], help="Emperor name to seed as retrieval target; repeatable.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    loaded_env_keys: list[str] = []
    if args.env_file is not None:
        loaded_env_keys = load_env_file(args.env_file)
    if args.print_schema:
        sys.stdout.write(read_schema_sql(args.schema_path, schema_name=args.pg_schema))
        return 0
    report: dict[str, Any] = {"ok": True, "actions": [], "loaded_env_keys": loaded_env_keys}
    target_dsn = resolve_dsn(args.target_dsn_env) if (args.apply_schema or args.copy_rule_contract) else ""
    if args.apply_schema:
        apply_schema(target_dsn, schema_path=args.schema_path, schema_name=args.pg_schema)
        report["actions"].append("apply_schema")
    if args.copy_rule_contract:
        source_dsn = resolve_dsn(args.source_dsn_env)
        copy_report = copy_rule_contract(
            source_dsn=source_dsn,
            target_dsn=target_dsn,
            item_code=args.item_code,
            contract_code=args.contract_code,
            source_database_label=args.source_database_label,
            seed_targets=args.seed_target,
            schema_name=args.pg_schema,
        )
        report["actions"].append("copy_rule_contract")
        report["copy_rule_contract"] = copy_report
    if not report["actions"]:
        raise RetrievalV3BootstrapError("no action requested; use --print-schema, --apply-schema, or --copy-rule-contract")
    sys.stdout.write(pretty_json(report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    try:
        raise SystemExit(main())
    except RetrievalV3BootstrapError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
