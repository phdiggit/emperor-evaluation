from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.i5b_finite_values import CANONICAL_PERIODS, normalize_period_alias  # noqa: E402
from scripts.dev.retrieval_v2_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v2_import_plan import ImportPlanError, json_param, stable_hash, write_json  # noqa: E402
from scripts.dev.retrieval_v2_intake_manifest import text  # noqa: E402


SOURCE = "retrieval_v2_target_person_consumer"
TARGET_SQL = """
select
    id as target_id,
    target_code,
    emperor_name,
    item_code,
    target_status,
    target_payload
from retrieval_v2.retrieval_targets
where target_status = 'active'
  and (%s = '' or item_code = %s)
order by item_code, emperor_name, id
"""

OLD_EMP_SQL = """
select
    name,
    period,
    title
from public.emps
order by name, id
"""


def fetch_one_id(cur: Any) -> int:
    row = cur.fetchone()
    if not row or row.get("id") is None:
        raise ImportPlanError("expected statement to return id")
    return int(row["id"])


def normalize_period(value: Any) -> tuple[str, bool]:
    normalized = normalize_period_alias(value)
    return normalized, bool(normalized and normalized in CANONICAL_PERIODS)


def chinese_text(value: Any) -> str:
    raw = text(value)
    if not raw:
        return ""
    if re.search(r"[A-Za-z0-9_#=]", raw):
        return ""
    return raw if re.search(r"[\u4e00-\u9fff]", raw) else ""


def old_emp_index(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    for row in rows:
        name = text(row.get("name"))
        if not name or name in index:
            continue
        period, supported = normalize_period(row.get("period"))
        index[name] = {
            "period": period if supported else "",
            "raw_period": text(row.get("period")),
            "title": chinese_text(row.get("title")),
        }
    return index


def object_identity_key(row: Mapping[str, Any]) -> str:
    return "|".join(["target_emperor", "item", text(row.get("item_code")), "name", text(row.get("emperor_name"))])


def object_code(identity_key: str) -> str:
    return "OBJ-" + stable_hash(identity_key, length=16)


def object_name_code(*, identity_key: str, normalized_name: str, name_kind: str) -> str:
    return "ONM-" + stable_hash([identity_key, normalized_name, name_kind], length=16)


def target_object_code(*, target_code: str, identity_key: str) -> str:
    return "TOB-" + stable_hash([target_code, identity_key, "target_emperor"], length=16)


def profile_code(identity_key: str) -> str:
    return "PRF-" + stable_hash(["target_emperor_profile", identity_key], length=16)


def affiliation_key(identity_key: str, period: str) -> str:
    return "|".join([identity_key, "affiliation", "dynasty", period])


def affiliation_code(key: str) -> str:
    return "PAF-" + stable_hash(key, length=16)


def role_key(identity_key: str) -> str:
    return "|".join([identity_key, "role", "emperor"])


def role_code(key: str) -> str:
    return "PRO-" + stable_hash(key, length=16)


def description_parts(name: str, meta: Mapping[str, str]) -> list[str]:
    parts = ["当前评价项目标皇帝"]
    period = text(meta.get("period"))
    title = text(meta.get("title"))
    if period:
        parts.append(f"朝代为{period}")
    if title:
        parts.append(f"称号为{title}")
    return [part for part in parts if part]


def profile_basis(name: str, meta: Mapping[str, str]) -> str:
    parts = description_parts(name, meta)
    if len(parts) <= 1:
        return f"{name}，当前评价项目标皇帝。"
    return f"{name}，{'；'.join(parts)}。"


def context_basis(meta: Mapping[str, str]) -> str:
    parts = description_parts("", meta)
    if len(parts) <= 1:
        return "当前评价项目标皇帝。"
    return f"{'；'.join(parts)}。"


def rows_for_target(row: Mapping[str, Any], meta: Mapping[str, str]) -> dict[str, Any]:
    name = text(row.get("emperor_name"))
    identity_key = object_identity_key(row)
    obj_code = object_code(identity_key)
    payload = {
        "source": SOURCE,
        "target_id": row.get("target_id"),
        "target_code": text(row.get("target_code")),
        "item_code": text(row.get("item_code")),
        "emperor_name": name,
        "old_emp_period": text(meta.get("raw_period")),
        "normalized_period": text(meta.get("period")),
        "old_emp_title": text(meta.get("title")),
    }
    target_object = {
        "target_object_code": target_object_code(target_code=text(row.get("target_code")), identity_key=identity_key),
        "target_id": int(row.get("target_id")),
        "object_code": obj_code,
        "scope_code": "item",
        "object_role": "target_emperor",
        "review_status": "accepted",
        "target_object_payload": payload,
    }
    profile = {
        "person_profile_code": profile_code(identity_key),
        "object_code": obj_code,
        "talent_grade": None,
        "talent_grade_basis": profile_basis(name, meta),
        "review_status": "accepted",
        "profile_payload": payload,
    }
    period = text(meta.get("period"))
    affiliation = None
    if period:
        key = affiliation_key(identity_key, period)
        affiliation = {
            "person_affiliation_code": affiliation_code(key),
            "person_affiliation_key": key,
            "object_code": obj_code,
            "affiliation_kind": "dynasty",
            "dynasty_label": period,
            "polity_label": "",
            "affiliation_label": "",
            "period_label": "",
            "period_start_year": None,
            "period_end_year": None,
            "affiliation_basis": context_basis(meta),
            "review_status": "accepted",
            "affiliation_payload": payload,
        }
    r_key = role_key(identity_key)
    role = {
        "person_role_code": role_code(r_key),
        "person_role_key": r_key,
        "object_code": obj_code,
        "person_affiliation_key": affiliation["person_affiliation_key"] if affiliation else "",
        "role_kind": "emperor",
        "dynasty_label": period,
        "polity_label": "",
        "role_title": text(meta.get("title")),
        "period_label": "",
        "period_start_year": None,
        "period_end_year": None,
        "role_basis": context_basis(meta),
        "review_status": "accepted",
        "role_payload": payload,
    }
    return {
        "object": {
            "object_code": obj_code,
            "object_identity_key": identity_key,
            "canonical_name": name,
            "normalized_name": name,
            "object_type": "person",
            "identity_status": "active",
            "curator_note": context_basis(meta),
            "identity_payload": payload,
        },
        "object_name": {
            "object_name_code": object_name_code(identity_key=identity_key, normalized_name=name, name_kind="canonical"),
            "object_code": obj_code,
            "name_text": name,
            "normalized_name": name,
            "name_kind": "canonical",
            "script_variant_group_key": name,
            "source": SOURCE,
            "review_status": "accepted",
            "name_payload": payload,
        },
        "target_object": target_object,
        "profile": profile,
        "affiliation": affiliation,
        "role": role,
    }


def build_target_person_plan(target_rows: Sequence[Mapping[str, Any]], old_emp_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    emp_index = old_emp_index(old_emp_rows)
    objects: list[dict[str, Any]] = []
    names: list[dict[str, Any]] = []
    target_objects: list[dict[str, Any]] = []
    profiles: list[dict[str, Any]] = []
    affiliations: list[dict[str, Any]] = []
    roles: list[dict[str, Any]] = []
    missing_period: list[dict[str, Any]] = []
    for row in target_rows:
        meta = emp_index.get(text(row.get("emperor_name"))) or {"period": "", "raw_period": "", "title": ""}
        grouped = rows_for_target(row, meta)
        objects.append(grouped["object"])
        names.append(grouped["object_name"])
        target_objects.append(grouped["target_object"])
        profiles.append(grouped["profile"])
        if grouped["affiliation"]:
            affiliations.append(grouped["affiliation"])
        else:
            missing_period.append(
                {
                    "target_id": int(row.get("target_id")),
                    "target_code": text(row.get("target_code")),
                    "emperor_name": text(row.get("emperor_name")),
                    "item_code": text(row.get("item_code")),
                }
            )
        roles.append(grouped["role"])

    return {
        "generated_by": "scripts/dev/retrieval_v2_target_person_consumer.py",
        "mode": "dry_run_target_person_consumer",
        "write_db": False,
        "executed": False,
        "ok": True,
        "totals": {
            "target_rows": len(target_rows),
            "object_rows": len(objects),
            "object_name_rows": len(names),
            "target_object_rows": len(target_objects),
            "profile_rows": len(profiles),
            "dynasty_affiliation_rows": len(affiliations),
            "emperor_role_rows": len(roles),
            "missing_emperor_period": len(missing_period),
        },
        "operation_counts": {
            "retrieval_v2.objects": len(objects),
            "retrieval_v2.object_names": len(names),
            "retrieval_v2.target_objects": len(target_objects),
            "retrieval_v2.person_profiles": len(profiles),
            "retrieval_v2.person_affiliations": len(affiliations),
            "retrieval_v2.person_roles": len(roles),
        },
        "review_needed": {"missing_emperor_period": missing_period},
        "object_rows": objects,
        "object_name_rows": names,
        "target_object_rows": target_objects,
        "profile_rows": profiles,
        "affiliation_rows": affiliations,
        "role_rows": roles,
        "executed_counts": {},
    }


def fetch_target_rows(cur: Any, *, item_code: str) -> list[dict[str, Any]]:
    cur.execute(TARGET_SQL, (item_code, item_code))
    return [dict(row) for row in cur.fetchall()]


def fetch_old_emp_rows(cur: Any) -> list[dict[str, Any]]:
    cur.execute(OLD_EMP_SQL)
    return [dict(row) for row in cur.fetchall()]


def upsert_object(cur: Any, row: Mapping[str, Any]) -> int:
    cur.execute(
        """
        insert into retrieval_v2.objects (
            object_code, object_identity_key, canonical_name, normalized_name,
            object_type, identity_status, curator_note, identity_payload
        )
        values (%s, %s, %s, %s, %s::retrieval_v2.rv2_object_type, %s::retrieval_v2.rv2_object_identity_status, %s, %s::jsonb)
        on conflict on constraint rv2_objects_identity_key_uk do update set
            canonical_name = excluded.canonical_name,
            normalized_name = excluded.normalized_name,
            object_type = excluded.object_type,
            identity_status = case
                when retrieval_v2.objects.identity_status in ('merged', 'rejected', 'retired') then retrieval_v2.objects.identity_status
                else excluded.identity_status
            end,
            curator_note = case
                when btrim(retrieval_v2.objects.curator_note) <> '' then retrieval_v2.objects.curator_note
                else excluded.curator_note
            end,
            identity_payload = excluded.identity_payload,
            updated_at = now()
        returning id
        """,
        (
            text(row.get("object_code")),
            text(row.get("object_identity_key")),
            text(row.get("canonical_name")),
            text(row.get("normalized_name")),
            text(row.get("object_type")),
            text(row.get("identity_status")),
            text(row.get("curator_note")),
            json_param(row.get("identity_payload") or {}),
        ),
    )
    return fetch_one_id(cur)


def upsert_object_name(cur: Any, row: Mapping[str, Any], *, object_id: int) -> int:
    cur.execute(
        """
        insert into retrieval_v2.object_names (
            object_name_code, object_id, name_text, normalized_name, name_kind,
            script_variant_group_key, source, review_status, name_payload
        )
        values (%s, %s, %s, %s, %s::retrieval_v2.rv2_object_name_kind, %s, %s, %s::retrieval_v2.rv2_review_status, %s::jsonb)
        on conflict on constraint rv2_object_names_name_uk do update set
            name_text = excluded.name_text,
            script_variant_group_key = excluded.script_variant_group_key,
            review_status = case
                when retrieval_v2.object_names.review_status in ('rejected', 'retired') then retrieval_v2.object_names.review_status
                else excluded.review_status
            end,
            name_payload = excluded.name_payload
        returning id
        """,
        (
            text(row.get("object_name_code")),
            object_id,
            text(row.get("name_text")),
            text(row.get("normalized_name")),
            text(row.get("name_kind")),
            text(row.get("script_variant_group_key")),
            text(row.get("source")),
            text(row.get("review_status")),
            json_param(row.get("name_payload") or {}),
        ),
    )
    return fetch_one_id(cur)


def upsert_target_object(cur: Any, row: Mapping[str, Any], *, object_id: int) -> int:
    cur.execute(
        """
        insert into retrieval_v2.target_objects (
            target_object_code, target_id, object_id, scope_code, object_role,
            review_status, target_object_payload
        )
        values (%s, %s, %s, %s::retrieval_v2.rv2_target_object_scope, %s, %s::retrieval_v2.rv2_review_status, %s::jsonb)
        on conflict on constraint rv2_target_objects_scope_uk do update set
            object_role = excluded.object_role,
            review_status = case
                when retrieval_v2.target_objects.review_status in ('rejected', 'retired') then retrieval_v2.target_objects.review_status
                else excluded.review_status
            end,
            target_object_payload = excluded.target_object_payload,
            updated_at = now()
        returning id
        """,
        (
            text(row.get("target_object_code")),
            int(row.get("target_id")),
            object_id,
            text(row.get("scope_code")),
            text(row.get("object_role")),
            text(row.get("review_status")),
            json_param(row.get("target_object_payload") or {}),
        ),
    )
    return fetch_one_id(cur)


def upsert_profile(cur: Any, row: Mapping[str, Any], *, object_id: int) -> int:
    cur.execute(
        """
        insert into retrieval_v2.person_profiles (
            person_profile_code, object_id, talent_grade, talent_grade_basis,
            review_status, profile_payload
        )
        values (%s, %s, %s::retrieval_v2.rv2_person_talent_grade, %s, %s::retrieval_v2.rv2_review_status, %s::jsonb)
        on conflict on constraint rv2_person_profiles_object_uk do update set
            person_profile_code = excluded.person_profile_code,
            talent_grade = coalesce(retrieval_v2.person_profiles.talent_grade, excluded.talent_grade),
            talent_grade_basis = case
                when btrim(retrieval_v2.person_profiles.talent_grade_basis) <> ''
                    then retrieval_v2.person_profiles.talent_grade_basis
                else excluded.talent_grade_basis
            end,
            review_status = case
                when retrieval_v2.person_profiles.review_status in ('rejected', 'retired')
                    then retrieval_v2.person_profiles.review_status
                else excluded.review_status
            end,
            profile_payload = retrieval_v2.person_profiles.profile_payload || excluded.profile_payload,
            updated_at = now()
        returning id
        """,
        (
            text(row.get("person_profile_code")),
            object_id,
            row.get("talent_grade"),
            text(row.get("talent_grade_basis")),
            text(row.get("review_status")),
            json_param(row.get("profile_payload") or {}),
        ),
    )
    return fetch_one_id(cur)


def upsert_affiliation(cur: Any, row: Mapping[str, Any], *, object_id: int) -> int:
    cur.execute(
        """
        insert into retrieval_v2.person_affiliations (
            person_affiliation_code, person_affiliation_key, object_id, affiliation_kind,
            dynasty_label, polity_label, affiliation_label, period_label,
            period_start_year, period_end_year, affiliation_basis, review_status,
            affiliation_payload
        )
        values (
            %s, %s, %s, %s::retrieval_v2.rv2_person_affiliation_kind,
            %s, %s, %s, %s,
            %s, %s, %s, %s::retrieval_v2.rv2_review_status,
            %s::jsonb
        )
        on conflict on constraint rv2_person_affiliations_key_uk do update set
            dynasty_label = excluded.dynasty_label,
            polity_label = excluded.polity_label,
            affiliation_label = excluded.affiliation_label,
            period_label = excluded.period_label,
            period_start_year = excluded.period_start_year,
            period_end_year = excluded.period_end_year,
            affiliation_basis = case
                when btrim(retrieval_v2.person_affiliations.affiliation_basis) <> ''
                    then retrieval_v2.person_affiliations.affiliation_basis
                else excluded.affiliation_basis
            end,
            review_status = case
                when retrieval_v2.person_affiliations.review_status in ('rejected', 'retired')
                    then retrieval_v2.person_affiliations.review_status
                else excluded.review_status
            end,
            affiliation_payload = excluded.affiliation_payload,
            updated_at = now()
        returning id
        """,
        (
            text(row.get("person_affiliation_code")),
            text(row.get("person_affiliation_key")),
            object_id,
            text(row.get("affiliation_kind")),
            text(row.get("dynasty_label")),
            text(row.get("polity_label")),
            text(row.get("affiliation_label")),
            text(row.get("period_label")),
            row.get("period_start_year"),
            row.get("period_end_year"),
            text(row.get("affiliation_basis")),
            text(row.get("review_status")),
            json_param(row.get("affiliation_payload") or {}),
        ),
    )
    return fetch_one_id(cur)


def upsert_role(cur: Any, row: Mapping[str, Any], *, object_id: int, affiliation_id: int | None) -> int:
    cur.execute(
        """
        insert into retrieval_v2.person_roles (
            person_role_code, person_role_key, object_id, person_affiliation_id,
            role_kind, dynasty_label, polity_label, role_title, period_label,
            period_start_year, period_end_year, role_basis, review_status,
            role_payload
        )
        values (
            %s, %s, %s, %s,
            %s::retrieval_v2.rv2_person_role_kind, %s, %s, %s, %s,
            %s, %s, %s, %s::retrieval_v2.rv2_review_status,
            %s::jsonb
        )
        on conflict on constraint rv2_person_roles_key_uk do update set
            person_affiliation_id = coalesce(excluded.person_affiliation_id, retrieval_v2.person_roles.person_affiliation_id),
            dynasty_label = coalesce(nullif(excluded.dynasty_label, ''), retrieval_v2.person_roles.dynasty_label),
            polity_label = coalesce(nullif(excluded.polity_label, ''), retrieval_v2.person_roles.polity_label),
            role_title = coalesce(nullif(excluded.role_title, ''), retrieval_v2.person_roles.role_title),
            period_label = coalesce(nullif(excluded.period_label, ''), retrieval_v2.person_roles.period_label),
            period_start_year = coalesce(excluded.period_start_year, retrieval_v2.person_roles.period_start_year),
            period_end_year = coalesce(excluded.period_end_year, retrieval_v2.person_roles.period_end_year),
            role_basis = case
                when btrim(retrieval_v2.person_roles.role_basis) <> ''
                    then retrieval_v2.person_roles.role_basis
                else excluded.role_basis
            end,
            review_status = case
                when retrieval_v2.person_roles.review_status in ('rejected', 'retired')
                    then retrieval_v2.person_roles.review_status
                else excluded.review_status
            end,
            role_payload = retrieval_v2.person_roles.role_payload || excluded.role_payload,
            updated_at = now()
        returning id
        """,
        (
            text(row.get("person_role_code")),
            text(row.get("person_role_key")),
            object_id,
            affiliation_id,
            text(row.get("role_kind")),
            text(row.get("dynasty_label")),
            text(row.get("polity_label")),
            text(row.get("role_title")),
            text(row.get("period_label")),
            row.get("period_start_year"),
            row.get("period_end_year"),
            text(row.get("role_basis")),
            text(row.get("review_status")),
            json_param(row.get("role_payload") or {}),
        ),
    )
    return fetch_one_id(cur)


def execute_upserts(cur: Any, payload: Mapping[str, Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    object_ids: dict[str, int] = {}
    affiliation_ids: dict[str, int] = {}
    for row in payload.get("object_rows") or []:
        object_ids[text(row.get("object_code"))] = upsert_object(cur, row)
        counts["retrieval_v2.objects"] += 1
    for row in payload.get("object_name_rows") or []:
        upsert_object_name(cur, row, object_id=object_ids[text(row.get("object_code"))])
        counts["retrieval_v2.object_names"] += 1
    for row in payload.get("target_object_rows") or []:
        upsert_target_object(cur, row, object_id=object_ids[text(row.get("object_code"))])
        counts["retrieval_v2.target_objects"] += 1
    for row in payload.get("profile_rows") or []:
        upsert_profile(cur, row, object_id=object_ids[text(row.get("object_code"))])
        counts["retrieval_v2.person_profiles"] += 1
    for row in payload.get("affiliation_rows") or []:
        affiliation_id = upsert_affiliation(cur, row, object_id=object_ids[text(row.get("object_code"))])
        affiliation_ids[text(row.get("person_affiliation_key"))] = affiliation_id
        counts["retrieval_v2.person_affiliations"] += 1
    for row in payload.get("role_rows") or []:
        upsert_role(
            cur,
            row,
            object_id=object_ids[text(row.get("object_code"))],
            affiliation_id=affiliation_ids.get(text(row.get("person_affiliation_key"))),
        )
        counts["retrieval_v2.person_roles"] += 1
    return dict(sorted(counts.items()))


def execute_target_person_consumer(
    *,
    env_file: Path | None,
    dsn_env: str,
    old_dsn_env: str,
    item_code: str,
    execute: bool,
) -> dict[str, Any]:
    if env_file is not None:
        load_env_file(env_file)
    psycopg, dict_row = import_psycopg()
    new_dsn = resolve_dsn(dsn_env)
    old_dsn = resolve_dsn(old_dsn_env)

    with psycopg.connect(old_dsn, row_factory=dict_row) as old_conn:
        with old_conn.cursor() as old_cur:
            old_rows = fetch_old_emp_rows(old_cur)

    with psycopg.connect(new_dsn, row_factory=dict_row) as new_conn:
        with new_conn.cursor() as new_cur:
            target_rows = fetch_target_rows(new_cur, item_code=item_code)
            report = build_target_person_plan(target_rows, old_rows)
            report["mode"] = "execute" if execute else "dry_run_target_person_consumer"
            report["write_db"] = execute
            if not execute:
                new_conn.rollback()
                return report
            report["executed_counts"] = execute_upserts(new_cur, report)
            report["executed"] = True
        new_conn.commit()
    return report


def markdown_report(payload: Mapping[str, Any]) -> str:
    totals = payload.get("totals") or {}
    lines = [
        "# retrieval_v2 target person consumer report",
        "",
        f"- ok: `{str(payload.get('ok')).lower()}`",
        f"- write_db: `{str(payload.get('write_db')).lower()}`",
        f"- executed: `{str(payload.get('executed')).lower()}`",
        f"- target_rows: `{totals.get('target_rows', 0)}`",
        f"- profile_rows: `{totals.get('profile_rows', 0)}`",
        f"- dynasty_affiliation_rows: `{totals.get('dynasty_affiliation_rows', 0)}`",
        f"- emperor_role_rows: `{totals.get('emperor_role_rows', 0)}`",
        f"- missing_emperor_period: `{totals.get('missing_emperor_period', 0)}`",
        "",
        "## Operation Counts",
        "",
        "| table | rows |",
        "| --- | ---: |",
    ]
    for table, count in (payload.get("operation_counts") or {}).items():
        lines.append(f"| {table} | {count} |")
    missing = list((payload.get("review_needed") or {}).get("missing_emperor_period") or [])
    if missing:
        lines.extend(["", "## Missing Emperor Period", "", "| target_id | emperor | item |", "| ---: | --- | --- |"])
        for row in missing[:100]:
            lines.append(f"| {row.get('target_id')} | {row.get('emperor_name')} | {row.get('item_code')} |")
        if len(missing) > 100:
            lines.append(f"|  | ... {len(missing) - 100} more |  |")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ensure retrieval_v2 target emperors have person objects, profiles, affiliations, and emperor roles.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    apply = subparsers.add_parser("apply", help="Upsert target emperor person rows; dry-run unless --execute.")
    apply.add_argument("--output-json", type=Path, required=True)
    apply.add_argument("--output-md", type=Path, required=True)
    apply.add_argument("--env-file", type=Path)
    apply.add_argument("--dsn-env", default="EMPEROR_EVAL_RETRIEVAL_V2_DSN")
    apply.add_argument("--old-dsn-env", default="EMPEROR_EVAL_PG_DSN")
    apply.add_argument("--item-code", default="I5B")
    apply.add_argument("--execute", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "apply":
        raise ImportPlanError(f"unsupported command: {args.command}")
    payload = execute_target_person_consumer(
        env_file=args.env_file,
        dsn_env=args.dsn_env,
        old_dsn_env=args.old_dsn_env,
        item_code=args.item_code,
        execute=args.execute,
    )
    write_json(args.output_json, payload)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(markdown_report(payload), encoding="utf-8")
    print(json.dumps({"ok": payload["ok"], "totals": payload["totals"]}, ensure_ascii=False, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
