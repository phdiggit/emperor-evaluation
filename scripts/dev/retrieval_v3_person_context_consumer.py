from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.i5b_finite_values import CANONICAL_PERIODS, normalize_period_alias  # noqa: E402
from scripts.dev.retrieval_v3_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v3_import_plan import ImportPlanError, json_param, stable_hash, write_json  # noqa: E402
from scripts.dev.retrieval_v3_intake_manifest import text  # noqa: E402


SOURCE = "retrieval_v3_person_context_consumer"
ROLE_KIND_BY_MATERIAL_ROLE = {
    "civil_delegate": "official",
    "strategic_delegate": "official",
    "military_delegate": "general",
}
IGNORED_MATERIAL_ROLES = {"revoked_or_failed_delegate"}
GENERIC_NOTE_MARKERS = (
    "摘录材料中见其与",
    "当前文件仅保留",
    "仅保留身份",
    "旧库",
    "导入",
    "审计",
    "候选",
)
TECHNICAL_NOTE_RE = re.compile(r"[A-Za-z0-9_#=]")

NEW_PERSON_SQL = """
select
    id as object_id,
    object_code,
    object_identity_key,
    canonical_name,
    normalized_name,
    identity_status::text as identity_status
from retrieval_v3.objects
where object_type = 'person'
order by canonical_name, id
"""

OLD_PERSON_PERIOD_SQL = """
select
    ro.id as old_obj_id,
    ro.name as old_name,
    ro.period as old_period,
    ro.note as old_note,
    a.alias_text,
    a.normalized_alias,
    a.alias_kind
from public.raw_objs ro
left join public.raw_obj_aliases a on a.obj_id = ro.id and coalesce(a.active, true)
where ro.obj_type = 'person'
order by ro.name, ro.period, ro.id
"""

OLD_EMP_SQL = """
select
    name,
    period,
    title
from public.emps
order by name, id
"""

TARGET_CONTEXT_SQL = """
select
    o.id as object_id,
    o.object_code,
    o.object_identity_key,
    o.canonical_name,
    o.normalized_name,
    tob.id as target_object_id,
    rt.id as target_id,
    rt.target_code,
    rt.emperor_name,
    mol.role as material_role,
    count(mol.id)::int as link_count
from retrieval_v3.objects o
join retrieval_v3.target_objects tob on tob.object_id = o.id
join retrieval_v3.retrieval_targets rt on rt.id = tob.target_id
left join retrieval_v3.material_object_links mol on mol.target_object_id = tob.id
where o.object_type = 'person'
  and tob.review_status in ('pending', 'accepted')
  and tob.object_role <> 'target_emperor'
group by
    o.id,
    o.object_code,
    o.object_identity_key,
    o.canonical_name,
    o.normalized_name,
    tob.id,
    rt.id,
    rt.target_code,
    rt.emperor_name,
    mol.role
order by o.canonical_name, rt.emperor_name, mol.role
"""


def fetch_one_id(cur: Any) -> int:
    row = cur.fetchone()
    if not row or row.get("id") is None:
        raise ImportPlanError("expected statement to return id")
    return int(row["id"])


def person_match_keys(person: Mapping[str, Any]) -> list[str]:
    keys: list[str] = []
    for value in [person.get("canonical_name"), person.get("normalized_name")]:
        key = text(value)
        if key and key not in keys:
            keys.append(key)
    return keys


def old_match_keys(row: Mapping[str, Any]) -> list[str]:
    keys: list[str] = []
    for value in [row.get("old_name"), row.get("alias_text"), row.get("normalized_alias")]:
        key = text(value)
        if key and key not in keys:
            keys.append(key)
    return keys


def normalize_period(value: Any) -> tuple[str, bool]:
    normalized = normalize_period_alias(value)
    return normalized, bool(normalized and normalized in CANONICAL_PERIODS)


def clean_basis(value: str) -> str:
    segments: list[str] = []
    for raw_segment in re.split(r"[。；;\n]+", value):
        segment = text(raw_segment).strip("。；; ")
        if not segment:
            continue
        if TECHNICAL_NOTE_RE.search(segment):
            continue
        if any(marker in segment for marker in GENERIC_NOTE_MARKERS):
            continue
        if not re.search(r"[\u4e00-\u9fff]", segment):
            continue
        segments.append(segment)
    return "；".join(dict.fromkeys(segments))


def build_old_period_index(old_rows: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in old_rows:
        normalized_period, period_supported = normalize_period(row.get("old_period"))
        normalized = {
            "old_obj_id": row.get("old_obj_id"),
            "old_name": text(row.get("old_name")),
            "old_period": text(row.get("old_period")),
            "period": normalized_period,
            "period_supported": period_supported,
            "old_note": text(row.get("old_note")),
            "alias_text": text(row.get("alias_text")),
            "normalized_alias": text(row.get("normalized_alias")),
            "alias_kind": text(row.get("alias_kind")),
        }
        for key in old_match_keys(row):
            index[key].append(normalized)
    return dict(index)


def unique_old_period_matches(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, str]] = set()
    unique: list[dict[str, Any]] = []
    for row in rows:
        key = (row.get("old_obj_id"), text(row.get("period")) or text(row.get("old_period")))
        if key in seen:
            continue
        seen.add(key)
        unique.append(dict(row))
    return unique


def match_old_periods(person: Mapping[str, Any], old_index: Mapping[str, Sequence[Mapping[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for key in person_match_keys(person):
        rows.extend(old_index.get(key, []))
    return unique_old_period_matches(rows)


def affiliation_code(person_affiliation_key: str) -> str:
    return "PAF-" + stable_hash(person_affiliation_key, length=16)


def role_code(person_role_key: str) -> str:
    return "PRO-" + stable_hash(person_role_key, length=16)


def old_dynasty_affiliation_key(person: Mapping[str, Any], period: str) -> str:
    return "|".join(["object", text(person.get("object_code")), "affiliation", "dynasty", "period", period])


def service_affiliation_key(context: Mapping[str, Any], period: str) -> str:
    return "|".join(
        [
            "object",
            text(context.get("object_code")),
            "affiliation",
            "service",
            "target",
            text(context.get("target_code")),
            "period",
            period,
        ]
    )


def role_key(context: Mapping[str, Any], role_kind: str) -> str:
    return "|".join(
        [
            "object",
            text(context.get("object_code")),
            "role",
            role_kind,
            "target",
            text(context.get("target_code")),
        ]
    )


def old_dynasty_affiliation_row(person: Mapping[str, Any], matches: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    periods = sorted({text(match.get("period")) for match in matches if text(match.get("period")) and match.get("period_supported")})
    unsupported = sorted({text(match.get("old_period")) for match in matches if text(match.get("old_period")) and not match.get("period_supported")})
    if len(periods) != 1 or unsupported:
        return None
    period = periods[0]
    notes = [clean_basis(text(match.get("old_note"))) for match in matches]
    basis = "；".join(note for note in dict.fromkeys(notes) if note)
    key = old_dynasty_affiliation_key(person, period)
    return {
        "person_affiliation_code": affiliation_code(key),
        "person_affiliation_key": key,
        "object_id": int(person.get("object_id")),
        "affiliation_kind": "dynasty",
        "dynasty_label": period,
        "polity_label": "",
        "affiliation_label": "",
        "period_label": "",
        "period_start_year": None,
        "period_end_year": None,
        "affiliation_basis": basis,
        "review_status": "accepted",
        "affiliation_payload": {
            "source": SOURCE,
            "match_status": "matched_old_person_period",
            "match_keys": person_match_keys(person),
            "old_matches": [
                {
                    "old_obj_id": match.get("old_obj_id"),
                    "old_name": match.get("old_name"),
                    "old_period": match.get("old_period"),
                    "period": match.get("period"),
                    "alias_text": match.get("alias_text"),
                    "normalized_alias": match.get("normalized_alias"),
                    "alias_kind": match.get("alias_kind"),
                }
                for match in matches[:10]
            ],
        },
    }


def target_period_index(old_emp_rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    for row in old_emp_rows:
        period, supported = normalize_period(row.get("period"))
        if not supported:
            continue
        name = text(row.get("name"))
        if not name:
            continue
        index.setdefault(name, {"period": period, "title": text(row.get("title"))})
    return index


def build_context_groups(target_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[int, str], dict[str, Any]] = {}
    for row in target_rows:
        key = (int(row.get("object_id")), text(row.get("target_code")))
        group = groups.setdefault(
            key,
            {
                "object_id": int(row.get("object_id")),
                "object_code": text(row.get("object_code")),
                "object_identity_key": text(row.get("object_identity_key")),
                "canonical_name": text(row.get("canonical_name")),
                "normalized_name": text(row.get("normalized_name")),
                "target_object_id": row.get("target_object_id"),
                "target_id": row.get("target_id"),
                "target_code": text(row.get("target_code")),
                "emperor_name": text(row.get("emperor_name")),
                "material_roles": Counter(),
            },
        )
        material_role = text(row.get("material_role"))
        if material_role:
            group["material_roles"][material_role] += int(row.get("link_count") or 0)
    result: list[dict[str, Any]] = []
    for group in groups.values():
        payload = dict(group)
        payload["material_roles"] = dict(sorted(group["material_roles"].items()))
        result.append(payload)
    return sorted(result, key=lambda item: (text(item.get("canonical_name")), text(item.get("target_code"))))


def service_affiliation_row(context: Mapping[str, Any], target_periods: Mapping[str, Mapping[str, str]]) -> dict[str, Any] | None:
    target = target_periods.get(text(context.get("emperor_name"))) or {}
    period = text(target.get("period"))
    if not period:
        return None
    key = service_affiliation_key(context, period)
    emperor_name = text(context.get("emperor_name"))
    return {
        "person_affiliation_code": affiliation_code(key),
        "person_affiliation_key": key,
        "object_id": int(context.get("object_id")),
        "affiliation_kind": "service",
        "dynasty_label": period,
        "polity_label": "",
        "affiliation_label": f"{emperor_name}评价语境" if emperor_name else "",
        "period_label": "",
        "period_start_year": None,
        "period_end_year": None,
        "affiliation_basis": "",
        "review_status": "pending",
        "affiliation_payload": {
            "source": SOURCE,
            "match_status": "target_service_context",
            "target_code": text(context.get("target_code")),
            "target_emperor": emperor_name,
            "target_title": text(target.get("title")),
            "target_period": period,
            "material_roles": context.get("material_roles") or {},
        },
    }


def role_rows_for_context(context: Mapping[str, Any], service_row: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    material_roles = {text(key): int(value or 0) for key, value in (context.get("material_roles") or {}).items()}
    role_kinds = sorted({ROLE_KIND_BY_MATERIAL_ROLE[role] for role in material_roles if role in ROLE_KIND_BY_MATERIAL_ROLE})
    rows: list[dict[str, Any]] = []
    for role_kind in role_kinds:
        key = role_key(context, role_kind)
        rows.append(
            {
                "person_role_code": role_code(key),
                "person_role_key": key,
                "object_id": int(context.get("object_id")),
                "person_affiliation_key": service_row.get("person_affiliation_key") if service_row else "",
                "role_kind": role_kind,
                "dynasty_label": text(service_row.get("dynasty_label")) if service_row else "",
                "polity_label": "",
                "role_title": "",
                "period_label": f"{text(context.get('emperor_name'))}评价语境" if text(context.get("emperor_name")) else "",
                "period_start_year": None,
                "period_end_year": None,
                "role_basis": "",
                "review_status": "pending",
                "role_payload": {
                    "source": SOURCE,
                    "match_status": "material_role_candidate",
                    "target_code": text(context.get("target_code")),
                    "target_emperor": text(context.get("emperor_name")),
                    "material_roles": material_roles,
                    "mapped_from_material_roles": sorted(
                        role for role, mapped in ROLE_KIND_BY_MATERIAL_ROLE.items() if mapped == role_kind and role in material_roles
                    ),
                    "ignored_material_roles": sorted(role for role in material_roles if role in IGNORED_MATERIAL_ROLES),
                },
            }
        )
    return rows


def build_context_plan(
    person_rows: Sequence[Mapping[str, Any]],
    old_person_rows: Sequence[Mapping[str, Any]],
    old_emp_rows: Sequence[Mapping[str, Any]],
    target_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    old_index = build_old_period_index(old_person_rows)
    target_periods = target_period_index(old_emp_rows)
    contexts = build_context_groups(target_rows)

    old_affiliations: list[dict[str, Any]] = []
    old_status_counts: Counter[str] = Counter()
    old_review_needed: list[dict[str, Any]] = []
    for person in person_rows:
        matches = match_old_periods(person, old_index)
        supported_periods = sorted({text(match.get("period")) for match in matches if text(match.get("period")) and match.get("period_supported")})
        unsupported_periods = sorted({text(match.get("old_period")) for match in matches if text(match.get("old_period")) and not match.get("period_supported")})
        if unsupported_periods:
            status = "unsupported_old_person_period"
        elif len(supported_periods) == 1:
            status = "matched_old_person_period"
            row = old_dynasty_affiliation_row(person, matches)
            if row:
                old_affiliations.append(row)
        elif supported_periods:
            status = "conflicting_old_person_period"
        else:
            status = "missing_old_person_period"
        old_status_counts[status] += 1
        if status != "matched_old_person_period":
            old_review_needed.append(
                {
                    "object_id": int(person.get("object_id")),
                    "canonical_name": text(person.get("canonical_name")),
                    "normalized_name": text(person.get("normalized_name")),
                    "match_status": status,
                    "periods": supported_periods or unsupported_periods,
                }
            )

    service_affiliations: list[dict[str, Any]] = []
    role_rows: list[dict[str, Any]] = []
    missing_target_periods: list[dict[str, Any]] = []
    missing_role_candidates: list[dict[str, Any]] = []
    ignored_material_role_counts: Counter[str] = Counter()
    service_keys: set[str] = set()
    role_keys: set[str] = set()
    for context in contexts:
        service = service_affiliation_row(context, target_periods)
        if service:
            if service["person_affiliation_key"] not in service_keys:
                service_keys.add(service["person_affiliation_key"])
                service_affiliations.append(service)
        else:
            missing_target_periods.append(
                {
                    "object_id": int(context.get("object_id")),
                    "canonical_name": text(context.get("canonical_name")),
                    "target_code": text(context.get("target_code")),
                    "emperor_name": text(context.get("emperor_name")),
                }
            )

        material_roles = {text(key): int(value or 0) for key, value in (context.get("material_roles") or {}).items()}
        for role, count in material_roles.items():
            if role in IGNORED_MATERIAL_ROLES:
                ignored_material_role_counts[role] += count
        rows = role_rows_for_context(context, service)
        if not rows:
            missing_role_candidates.append(
                {
                    "object_id": int(context.get("object_id")),
                    "canonical_name": text(context.get("canonical_name")),
                    "target_code": text(context.get("target_code")),
                    "material_roles": material_roles,
                }
            )
        for row in rows:
            if row["person_role_key"] in role_keys:
                continue
            role_keys.add(row["person_role_key"])
            role_rows.append(row)

    affiliation_rows = old_affiliations + service_affiliations
    return {
        "generated_by": "scripts/dev/retrieval_v3_person_context_consumer.py",
        "mode": "dry_run_person_context_consumer",
        "write_db": False,
        "executed": False,
        "ok": True,
        "totals": {
            "person_objects": len(person_rows),
            "old_period_affiliations": len(old_affiliations),
            "target_service_affiliations": len(service_affiliations),
            "affiliation_rows": len(affiliation_rows),
            "role_rows": len(role_rows),
            "matched_old_person_period": old_status_counts.get("matched_old_person_period", 0),
            "missing_old_person_period": old_status_counts.get("missing_old_person_period", 0),
            "conflicting_old_person_period": old_status_counts.get("conflicting_old_person_period", 0),
            "unsupported_old_person_period": old_status_counts.get("unsupported_old_person_period", 0),
            "missing_target_period": len(missing_target_periods),
            "missing_role_candidate": len(missing_role_candidates),
        },
        "old_period_status_counts": dict(sorted(old_status_counts.items())),
        "ignored_material_role_counts": dict(sorted(ignored_material_role_counts.items())),
        "operation_counts": {
            "retrieval_v3.person_affiliations": len(affiliation_rows),
            "retrieval_v3.person_roles": len(role_rows),
        },
        "review_needed": {
            "old_period": old_review_needed,
            "missing_target_period": missing_target_periods,
            "missing_role_candidate": missing_role_candidates,
        },
        "affiliation_rows": affiliation_rows,
        "role_rows": role_rows,
        "executed_counts": {},
    }


def fetch_new_person_rows(cur: Any) -> list[dict[str, Any]]:
    cur.execute(NEW_PERSON_SQL)
    return [dict(row) for row in cur.fetchall()]


def fetch_target_context_rows(cur: Any) -> list[dict[str, Any]]:
    cur.execute(TARGET_CONTEXT_SQL)
    return [dict(row) for row in cur.fetchall()]


def fetch_old_person_rows(cur: Any) -> list[dict[str, Any]]:
    cur.execute(OLD_PERSON_PERIOD_SQL)
    return [dict(row) for row in cur.fetchall()]


def fetch_old_emp_rows(cur: Any) -> list[dict[str, Any]]:
    cur.execute(OLD_EMP_SQL)
    return [dict(row) for row in cur.fetchall()]


def upsert_person_affiliation(cur: Any, row: Mapping[str, Any]) -> int:
    cur.execute(
        """
        insert into retrieval_v3.person_affiliations (
            person_affiliation_code, person_affiliation_key, object_id, affiliation_kind,
            dynasty_label, polity_label, affiliation_label, period_label,
            period_start_year, period_end_year, affiliation_basis, review_status,
            affiliation_payload
        )
        values (
            %s, %s, %s, %s::retrieval_v3.rv3_person_affiliation_kind,
            %s, %s, %s, %s,
            %s, %s, %s, %s::retrieval_v3.rv3_review_status,
            %s::jsonb
        )
        on conflict on constraint rv3_person_affiliations_key_uk do update set
            dynasty_label = excluded.dynasty_label,
            polity_label = excluded.polity_label,
            affiliation_label = excluded.affiliation_label,
            period_label = excluded.period_label,
            period_start_year = excluded.period_start_year,
            period_end_year = excluded.period_end_year,
            affiliation_basis = case
                when btrim(excluded.affiliation_basis) = '' and btrim(retrieval_v3.person_affiliations.affiliation_basis) <> ''
                    then retrieval_v3.person_affiliations.affiliation_basis
                else excluded.affiliation_basis
            end,
            review_status = case
                when retrieval_v3.person_affiliations.review_status in ('rejected', 'retired')
                    then retrieval_v3.person_affiliations.review_status
                when retrieval_v3.person_affiliations.review_status = 'accepted'
                 and excluded.review_status = 'pending'
                    then retrieval_v3.person_affiliations.review_status
                else excluded.review_status
            end,
            affiliation_payload = excluded.affiliation_payload,
            updated_at = now()
        returning id
        """,
        (
            text(row.get("person_affiliation_code")),
            text(row.get("person_affiliation_key")),
            int(row.get("object_id")),
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


def upsert_person_role(cur: Any, row: Mapping[str, Any], *, affiliation_id: int | None) -> int:
    cur.execute(
        """
        insert into retrieval_v3.person_roles (
            person_role_code, person_role_key, object_id, person_affiliation_id,
            role_kind, dynasty_label, polity_label, role_title, period_label,
            period_start_year, period_end_year, role_basis, review_status,
            role_payload
        )
        values (
            %s, %s, %s, %s,
            %s::retrieval_v3.rv3_person_role_kind, %s, %s, %s, %s,
            %s, %s, %s, %s::retrieval_v3.rv3_review_status,
            %s::jsonb
        )
        on conflict on constraint rv3_person_roles_key_uk do update set
            person_affiliation_id = coalesce(excluded.person_affiliation_id, retrieval_v3.person_roles.person_affiliation_id),
            dynasty_label = excluded.dynasty_label,
            polity_label = excluded.polity_label,
            role_title = excluded.role_title,
            period_label = excluded.period_label,
            period_start_year = excluded.period_start_year,
            period_end_year = excluded.period_end_year,
            role_basis = case
                when btrim(excluded.role_basis) = '' and btrim(retrieval_v3.person_roles.role_basis) <> ''
                    then retrieval_v3.person_roles.role_basis
                else excluded.role_basis
            end,
            review_status = case
                when retrieval_v3.person_roles.review_status in ('rejected', 'retired')
                    then retrieval_v3.person_roles.review_status
                when retrieval_v3.person_roles.review_status = 'accepted'
                 and excluded.review_status = 'pending'
                    then retrieval_v3.person_roles.review_status
                else excluded.review_status
            end,
            role_payload = excluded.role_payload,
            updated_at = now()
        returning id
        """,
        (
            text(row.get("person_role_code")),
            text(row.get("person_role_key")),
            int(row.get("object_id")),
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


def execute_upserts(cur: Any, affiliation_rows: Sequence[Mapping[str, Any]], role_rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    affiliation_ids: dict[str, int] = {}
    for row in affiliation_rows:
        affiliation_id = upsert_person_affiliation(cur, row)
        affiliation_ids[text(row.get("person_affiliation_key"))] = affiliation_id
        counts["retrieval_v3.person_affiliations"] += 1
    for row in role_rows:
        affiliation_key = text(row.get("person_affiliation_key"))
        upsert_person_role(cur, row, affiliation_id=affiliation_ids.get(affiliation_key))
        counts["retrieval_v3.person_roles"] += 1
    return dict(sorted(counts.items()))


def execute_person_context_consumer(
    *,
    env_file: Path | None,
    dsn_env: str,
    reference_dsn_env: str,
    execute: bool,
) -> dict[str, Any]:
    if env_file is not None:
        load_env_file(env_file)
    psycopg, dict_row = import_psycopg()
    new_dsn = resolve_dsn(dsn_env)
    reference_dsn = resolve_dsn(reference_dsn_env)

    with psycopg.connect(reference_dsn, row_factory=dict_row) as reference_conn:
        with reference_conn.cursor() as old_cur:
            old_person_rows = fetch_old_person_rows(old_cur)
            old_emp_rows = fetch_old_emp_rows(old_cur)

    with psycopg.connect(new_dsn, row_factory=dict_row) as new_conn:
        with new_conn.cursor() as new_cur:
            person_rows = fetch_new_person_rows(new_cur)
            target_rows = fetch_target_context_rows(new_cur)
            report = build_context_plan(person_rows, old_person_rows, old_emp_rows, target_rows)
            report["mode"] = "execute" if execute else "dry_run_person_context_consumer"
            report["write_db"] = execute
            if not execute:
                new_conn.rollback()
                return report
            report["executed_counts"] = execute_upserts(new_cur, report["affiliation_rows"], report["role_rows"])
            report["executed"] = True
        new_conn.commit()
    return report


def markdown_report(payload: Mapping[str, Any]) -> str:
    totals = payload.get("totals") or {}
    lines = [
        "# retrieval_v3 person context consumer report",
        "",
        f"- ok: `{str(payload.get('ok')).lower()}`",
        f"- write_db: `{str(payload.get('write_db')).lower()}`",
        f"- executed: `{str(payload.get('executed')).lower()}`",
        f"- person_objects: `{totals.get('person_objects', 0)}`",
        f"- affiliation_rows: `{totals.get('affiliation_rows', 0)}`",
        f"- role_rows: `{totals.get('role_rows', 0)}`",
        f"- missing_role_candidate: `{totals.get('missing_role_candidate', 0)}`",
        "",
        "## Operation Counts",
        "",
        "| table | rows |",
        "| --- | ---: |",
    ]
    for table, count in (payload.get("operation_counts") or {}).items():
        lines.append(f"| {table} | {count} |")
    if payload.get("executed_counts"):
        lines.extend(["", "## Executed", "", "| table | rows |", "| --- | ---: |"])
        for table, count in (payload.get("executed_counts") or {}).items():
            lines.append(f"| {table} | {count} |")
    role_missing = list((payload.get("review_needed") or {}).get("missing_role_candidate") or [])
    if role_missing:
        lines.extend(["", "## Missing Role Candidate", "", "| object_id | name | target | material_roles |", "| ---: | --- | --- | --- |"])
        for row in role_missing[:80]:
            lines.append(
                f"| {row.get('object_id')} | {row.get('canonical_name')} | {row.get('target_code')} | "
                f"{json.dumps(row.get('material_roles') or {}, ensure_ascii=False, sort_keys=True)} |"
            )
        if len(role_missing) > 80:
            lines.append(f"|  |  |  | ... {len(role_missing) - 80} more |")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Populate retrieval_v3 person role and affiliation candidates from current objects and reference context.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    apply = subparsers.add_parser("apply", help="Upsert person_affiliations and person_roles candidates.")
    apply.add_argument("--output-json", type=Path, required=True)
    apply.add_argument("--output-md", type=Path, required=True)
    apply.add_argument("--env-file", type=Path)
    apply.add_argument("--dsn-env", default="EMPEROR_EVAL_RETRIEVAL_V3_DSN")
    apply.add_argument("--reference-dsn-env", default="EMPEROR_EVAL_RETRIEVAL_V3_DSN")
    apply.add_argument("--execute", action="store_true", help="Actually write context rows. Omit for dry-run.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "apply":
        raise ImportPlanError(f"unsupported command: {args.command}")
    payload = execute_person_context_consumer(
        env_file=args.env_file,
        dsn_env=args.dsn_env,
        reference_dsn_env=args.reference_dsn_env,
        execute=args.execute,
    )
    write_json(args.output_json, payload)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(markdown_report(payload), encoding="utf-8")
    print(json.dumps({"ok": payload["ok"], "totals": payload["totals"]}, ensure_ascii=False, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
