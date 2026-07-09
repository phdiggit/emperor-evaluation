from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev import retrieval_v2_claim_quality as claim_quality  # noqa: E402
from scripts.dev.retrieval_v2_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v2_pg_schema import DEFAULT_PG_SCHEMA, DEFAULT_V3_DSN_ENV, schema_cursor, table_label  # noqa: E402


DEFAULT_DSN_ENV = DEFAULT_V3_DSN_ENV
OUTCOME_SUPPORTS = {"direct", "implicit", "missing", "not_applicable", "mixed"}
USAGE_ROLES = {"direct_material_candidate", "supporting_context", "evaluation_context", "background_context", "rejected"}
OWNER_SCOPES = {"target_emperor", "external_or_unregistered_owner", "blank_owner"}
DEFAULT_OWNER_SCOPES = ("target_emperor",)


class ClaimEventGroupError(RuntimeError):
    pass


def text(value: Any) -> str:
    return str(value or "").strip()


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def enum_value(value: Any, allowed: set[str], default: str) -> str:
    candidate = text(value)
    return candidate if candidate in allowed else default


def json_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def counter_json(values: Sequence[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def owner_scope_values(values: Sequence[str] | None) -> list[str]:
    scopes = [text(value) for value in values or [] if text(value)]
    if not scopes:
        return list(DEFAULT_OWNER_SCOPES)
    bad = [scope for scope in scopes if scope not in OWNER_SCOPES]
    if bad:
        raise ClaimEventGroupError(f"unsupported owner scope: {', '.join(bad)}")
    return sorted(set(scopes))


def claim_member_row(claim: Mapping[str, Any]) -> dict[str, Any]:
    quality = claim_quality.claim_quality_payload(claim)
    atomic_payload = json_mapping(claim.get("atomic_fact_payload")) or quality["atomic_fact_payload"]
    negative_support = text(atomic_payload.get("negative_support")) or quality["negative_support_payload"]["support"]
    outcome_support = enum_value(claim.get("outcome_support") or quality["outcome_support"], OUTCOME_SUPPORTS, "missing")
    member_role = enum_value(quality["usage_role_hint"], USAGE_ROLES, "supporting_context")
    return {
        "group_key": text(claim.get("event_group_key") or quality["event_group_key"]),
        "claim_key": text(claim.get("claim_key")),
        "member_role": member_role,
        "outcome_support": outcome_support,
        "member_payload": {
            "claim_summary": text(claim.get("claim_summary")),
            "fact_type": text(claim.get("fact_type") or quality["fact_type"]),
            "atomic_fact_payload": atomic_payload,
            "negative_support": {
                "support": negative_support,
                "has_governance_damage": negative_support == "governance_damage_supported",
                "has_negative_context": negative_support in {
                    "governance_damage_supported",
                    "negative_context_without_damage_anchor",
                },
            },
        },
    }


def claim_fact(claim: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = claim.get("fact_payload")
    return payload if isinstance(payload, Mapping) else {}


def claim_field(claim: Mapping[str, Any], field: str) -> str:
    fact = claim_fact(claim)
    return text(claim.get(field) or fact.get(field))


def claim_group_seed(claim: Mapping[str, Any]) -> dict[str, Any]:
    quality = claim_quality.claim_quality_payload(claim)
    payload = json_mapping(claim.get("event_group_payload")) or quality["event_group_payload"]
    return {
        "group_key": text(claim.get("event_group_key") or quality["event_group_key"]),
        "emperor_name": text(claim.get("emperor_name")),
        "object_name": text(claim.get("object_name")),
        "fact_type": text(claim.get("fact_type") or quality["fact_type"]),
        "action_type": claim_field(claim, "action_type"),
        "event_scope": claim_field(claim, "event_scope"),
        "office_or_domain": claim_field(claim, "office_or_domain"),
        "time_context": claim_field(claim, "time_context"),
        "group_payload": payload,
    }


def build_event_groups(claims: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    members_by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for claim in claims:
        if text(claim.get("status") or "active") not in {"", "active"}:
            continue
        seed = claim_group_seed(claim)
        group_key = seed["group_key"]
        groups.setdefault(group_key, seed)
        members_by_group[group_key].append(claim_member_row(claim))

    group_rows: list[dict[str, Any]] = []
    member_rows: list[dict[str, Any]] = []
    for group_key, group in sorted(groups.items()):
        members = sorted(members_by_group[group_key], key=lambda row: row["claim_key"])
        supports = [row["outcome_support"] for row in members]
        roles = [row["member_role"] for row in members]
        row = {
            **group,
            "member_count": len(members),
            "outcome_support_summary": counter_json(supports),
            "usage_summary": counter_json(roles),
        }
        group_rows.append(row)
        member_rows.extend(members)
    return {"groups": group_rows, "members": member_rows}


def group_category(group: Mapping[str, Any]) -> str:
    support = group.get("outcome_support_summary") if isinstance(group.get("outcome_support_summary"), Mapping) else {}
    direct = int(support.get("direct") or 0) + int(support.get("implicit") or 0)
    missing = int(support.get("missing") or 0)
    if direct and missing:
        return "action_only_with_result_claims"
    if direct:
        return "result_supported"
    if missing:
        return "action_only_context"
    return "non_action_or_evaluation_context"


def summarize_event_groups(groups: Sequence[Mapping[str, Any]], members: Sequence[Mapping[str, Any]], *, sample_limit: int = 20) -> dict[str, Any]:
    categories = Counter(group_category(group) for group in groups)
    by_object: Counter[str] = Counter(text(group.get("object_name")) for group in groups)
    object_context: dict[str, Counter[str]] = defaultdict(Counter)
    for group in groups:
        object_name = text(group.get("object_name"))
        if object_name:
            object_context[object_name][group_category(group)] += 1
    samples: list[dict[str, Any]] = []
    for group in groups:
        if len(samples) >= sample_limit:
            break
        category = group_category(group)
        if category in {"action_only_context", "action_only_with_result_claims"}:
            samples.append(
                {
                    "group_key": group.get("group_key"),
                    "category": category,
                    "emperor_name": group.get("emperor_name"),
                    "object_name": group.get("object_name"),
                    "fact_type": group.get("fact_type"),
                    "action_type": group.get("action_type"),
                    "time_context": group.get("time_context"),
                    "member_count": group.get("member_count"),
                    "outcome_support_summary": group.get("outcome_support_summary"),
                    "usage_summary": group.get("usage_summary"),
                }
            )
    return {
        "totals": {
            "event_groups": len(groups),
            "group_members": len(members),
            "action_only_context_groups": categories.get("action_only_context", 0),
            "action_only_with_result_claim_groups": categories.get("action_only_with_result_claims", 0),
            "result_supported_groups": categories.get("result_supported", 0),
            "non_action_or_evaluation_context_groups": categories.get("non_action_or_evaluation_context", 0),
        },
        "category_counts": dict(sorted(categories.items())),
        "top_objects": [
            {"object_name": object_name, "event_group_count": count}
            for object_name, count in by_object.most_common(30)
            if object_name
        ],
        "object_context": [
            {
                "object_name": object_name,
                "event_group_count": sum(counter.values()),
                "action_only_context_groups": counter.get("action_only_context", 0),
                "action_only_with_result_claim_groups": counter.get("action_only_with_result_claims", 0),
                "result_supported_groups": counter.get("result_supported", 0),
            }
            for object_name, counter in sorted(
                object_context.items(),
                key=lambda item: (
                    -(item[1].get("action_only_context", 0) + item[1].get("action_only_with_result_claims", 0)),
                    item[0],
                ),
            )
        ][:40],
        "sample_groups": samples,
    }


def fetch_claim_rows(
    cur: Any,
    *,
    emperor_names: Sequence[str],
    statuses: Sequence[str],
    owner_scopes: Sequence[str],
    last_run_codes: Sequence[str],
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    clean_emperors = [text(name) for name in emperor_names if text(name)]
    clean_statuses = [text(status) for status in statuses if text(status)]
    clean_owner_scopes = owner_scope_values(owner_scopes)
    clean_run_codes = [text(code) for code in last_run_codes if text(code)]
    if clean_emperors:
        clauses.append("c.emperor_name = any(%s)")
        params.append(clean_emperors)
    if clean_statuses:
        clauses.append("c.status::text = any(%s)")
        params.append(clean_statuses)
    if clean_run_codes:
        clauses.append("c.last_run_code = any(%s)")
        params.append(clean_run_codes)
    clauses.append("os.owner_scope = any(%s)")
    params.append(clean_owner_scopes)
    cur.execute(
        f"""
        select
            c.claim_key,
            c.emperor_name,
            c.object_name,
            c.object_type::text as object_type,
            c.fact_type,
            c.outcome_support::text as outcome_support,
            c.action_type,
            c.event_scope,
            c.office_or_domain,
            c.time_context,
            c.outcome,
            c.claim_summary,
            c.fact_payload,
            c.atomic_fact_payload,
            c.event_group_key,
            c.event_group_payload,
            c.status::text as status,
            os.owner_scope,
            os.owner_target_code
          from retrieval_v2.claim_atomic_facts c
          join retrieval_v2.claim_owner_scopes os on os.claim_key = c.claim_key
          {'where ' + ' and '.join(clauses) if clauses else ''}
         order by c.emperor_name, c.object_name, c.claim_key
        """,
        params,
    )
    return [dict(row) for row in cur.fetchall()]


def fetch_owner_scope_inventory(
    cur: Any,
    *,
    emperor_names: Sequence[str],
    statuses: Sequence[str],
    owner_scopes: Sequence[str],
    last_run_codes: Sequence[str],
) -> dict[str, Any]:
    clauses: list[str] = []
    params: list[Any] = []
    clean_emperors = [text(name) for name in emperor_names if text(name)]
    clean_statuses = [text(status) for status in statuses if text(status)]
    clean_owner_scopes = owner_scope_values(owner_scopes)
    clean_run_codes = [text(code) for code in last_run_codes if text(code)]
    if clean_emperors:
        clauses.append("owner_name = any(%s)")
        params.append(clean_emperors)
    if clean_statuses:
        clauses.append("status::text = any(%s)")
        params.append(clean_statuses)
    if clean_run_codes:
        clauses.append("last_run_code = any(%s)")
        params.append(clean_run_codes)
    cur.execute(
        f"""
        select owner_scope, count(*) as claim_count
          from retrieval_v2.claim_owner_scopes
          {'where ' + ' and '.join(clauses) if clauses else ''}
         group by owner_scope
         order by owner_scope
        """,
        params,
    )
    by_scope = {text(row["owner_scope"]): int(row["claim_count"]) for row in cur.fetchall()}
    selected = sum(count for scope, count in by_scope.items() if scope in clean_owner_scopes)
    total = sum(by_scope.values())
    return {
        "claim_count_by_owner_scope": dict(sorted(by_scope.items())),
        "selected_owner_scopes": clean_owner_scopes,
        "selected_claim_count": selected,
        "skipped_claim_count": max(0, total - selected),
    }


def delete_excluded_owner_scope_event_groups(cur: Any, owner_scopes: Sequence[str]) -> int:
    clean_owner_scopes = owner_scope_values(owner_scopes)
    cur.execute(
        """
        delete from retrieval_v2.claim_event_groups g
         where (
            case
                when btrim(g.emperor_name) = '' then 'blank_owner'
                when exists (
                    select 1
                      from retrieval_v2.retrieval_targets t
                     where t.emperor_name = g.emperor_name
                ) then 'target_emperor'
                else 'external_or_unregistered_owner'
            end
         ) <> all(%s)
        """,
        (clean_owner_scopes,),
    )
    return int(getattr(cur, "rowcount", 0) or 0)


def selected_event_group_where(*, owner_scopes: Sequence[str], emperor_names: Sequence[str]) -> tuple[str, list[Any]]:
    clauses = [
        """
        (
            case
                when btrim(g.emperor_name) = '' then 'blank_owner'
                when exists (
                    select 1
                      from retrieval_v2.retrieval_targets t
                     where t.emperor_name = g.emperor_name
                ) then 'target_emperor'
                else 'external_or_unregistered_owner'
            end
        ) = any(%s)
        """
    ]
    params: list[Any] = [owner_scope_values(owner_scopes)]
    clean_emperors = [text(name) for name in emperor_names if text(name)]
    if clean_emperors:
        clauses.append("g.emperor_name = any(%s)")
        params.append(clean_emperors)
    return " and ".join(clauses), params


def replace_existing_event_groups(cur: Any, *, owner_scopes: Sequence[str], emperor_names: Sequence[str]) -> dict[str, int]:
    where_sql, params = selected_event_group_where(owner_scopes=owner_scopes, emperor_names=emperor_names)
    cur.execute(
        f"""
        delete from retrieval_v2.claim_event_group_members m
         using retrieval_v2.claim_event_groups g
         where m.group_key = g.group_key
           and {where_sql}
        """,
        params,
    )
    deleted_members = int(getattr(cur, "rowcount", 0) or 0)
    cur.execute(
        f"""
        delete from retrieval_v2.claim_event_groups g
         where {where_sql}
        """,
        params,
    )
    deleted_groups = int(getattr(cur, "rowcount", 0) or 0)
    return {"deleted_groups": deleted_groups, "deleted_members": deleted_members}


def upsert_event_group(cur: Any, row: Mapping[str, Any]) -> None:
    cur.execute(
        """
        insert into retrieval_v2.claim_event_groups (
            group_key, emperor_name, object_name, fact_type, action_type, event_scope,
            office_or_domain, time_context, member_count, outcome_support_summary,
            usage_summary, group_payload
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb)
        on conflict (group_key) do update set
            emperor_name = excluded.emperor_name,
            object_name = excluded.object_name,
            fact_type = excluded.fact_type,
            action_type = excluded.action_type,
            event_scope = excluded.event_scope,
            office_or_domain = excluded.office_or_domain,
            time_context = excluded.time_context,
            member_count = excluded.member_count,
            outcome_support_summary = excluded.outcome_support_summary,
            usage_summary = excluded.usage_summary,
            group_payload = excluded.group_payload,
            updated_at = now()
        """,
        (
            row["group_key"],
            row["emperor_name"],
            row["object_name"],
            row["fact_type"],
            row["action_type"],
            row["event_scope"],
            row["office_or_domain"],
            row["time_context"],
            row["member_count"],
            stable_json(row["outcome_support_summary"]),
            stable_json(row["usage_summary"]),
            stable_json(row["group_payload"]),
        ),
    )


def upsert_event_group_member(cur: Any, row: Mapping[str, Any]) -> None:
    cur.execute(
        """
        insert into retrieval_v2.claim_event_group_members (
            group_key, claim_key, member_role, outcome_support, member_payload
        )
        values (%s, %s, %s, %s, %s::jsonb)
        on conflict (group_key, claim_key) do update set
            member_role = excluded.member_role,
            outcome_support = excluded.outcome_support,
            member_payload = excluded.member_payload,
            updated_at = now()
        """,
        (
            row["group_key"],
            row["claim_key"],
            row["member_role"],
            row["outcome_support"],
            stable_json(row["member_payload"]),
        ),
    )


def apply_event_groups(
    cur: Any,
    payload: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    schema_name: str,
    owner_scopes: Sequence[str],
    emperor_names: Sequence[str],
    replace_existing: bool,
) -> dict[str, int]:
    groups = list(payload.get("groups") or [])
    members = list(payload.get("members") or [])
    replaced = {"deleted_groups": 0, "deleted_members": 0}
    deleted = 0
    if replace_existing:
        replaced = replace_existing_event_groups(cur, owner_scopes=owner_scopes, emperor_names=emperor_names)
    else:
        deleted = delete_excluded_owner_scope_event_groups(cur, owner_scopes)
    for group in groups:
        upsert_event_group(cur, group)
    for member in members:
        upsert_event_group_member(cur, member)
    return {
        table_label("claim_event_groups", schema_name=schema_name): len(groups),
        table_label("claim_event_group_members", schema_name=schema_name): len(members),
        f"{table_label('claim_event_groups', schema_name=schema_name)}_deleted_by_owner_scope": deleted,
        f"{table_label('claim_event_groups', schema_name=schema_name)}_replace_deleted": replaced["deleted_groups"],
        f"{table_label('claim_event_group_members', schema_name=schema_name)}_replace_deleted": replaced["deleted_members"],
    }


def event_group_report(
    *,
    env_file: Path | None,
    dsn_env: str,
    schema_name: str,
    emperor_names: Sequence[str],
    statuses: Sequence[str],
    owner_scopes: Sequence[str],
    last_run_codes: Sequence[str],
    execute: bool,
    replace_existing: bool,
    sample_limit: int,
) -> dict[str, Any]:
    if env_file is not None:
        load_env_file(env_file)
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(resolve_dsn(dsn_env), row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            owner_scope_inventory = fetch_owner_scope_inventory(
                cur,
                emperor_names=emperor_names,
                statuses=statuses,
                owner_scopes=owner_scopes,
                last_run_codes=last_run_codes,
            )
            claims = fetch_claim_rows(
                cur,
                emperor_names=emperor_names,
                statuses=statuses,
                owner_scopes=owner_scopes,
                last_run_codes=last_run_codes,
            )
            built = build_event_groups(claims)
            summary = summarize_event_groups(built["groups"], built["members"], sample_limit=sample_limit)
            executed_counts: dict[str, int] = {}
            if execute:
                executed_counts = apply_event_groups(
                    cur,
                    built,
                    schema_name=schema_name,
                    owner_scopes=owner_scopes,
                    emperor_names=emperor_names,
                    replace_existing=replace_existing,
                )
        if execute:
            conn.commit()
        else:
            conn.rollback()
    return {
        "ok": True,
        "generated_by": "scripts/dev/retrieval_v2_claim_event_groups.py",
        "mode": "execute" if execute else "dry_run_event_group_audit",
        "write_db": execute,
        "replace_existing": bool(replace_existing),
        "schema_name": schema_name,
        "filters": {
            "emperor_names": [text(name) for name in emperor_names if text(name)],
            "statuses": [text(status) for status in statuses if text(status)],
            "owner_scopes": owner_scope_values(owner_scopes),
            "last_run_codes": [text(code) for code in last_run_codes if text(code)],
        },
        "owner_scope_inventory": owner_scope_inventory,
        **summary,
        "executed_counts": executed_counts,
    }


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pretty_json(payload), encoding="utf-8", newline="\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build shadow claim event groups from atomic claim_cache rows.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    parser.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    parser.add_argument("--emperor-name", action="append", default=[])
    parser.add_argument("--status", action="append", default=["active"])
    parser.add_argument("--owner-scope", action="append", default=[], choices=sorted(OWNER_SCOPES), help="Owner scope to include; defaults to target_emperor only.")
    parser.add_argument("--last-run-code", action="append", default=[], help="Limit claim rows to specific claim_cache last_run_code values.")
    parser.add_argument("--sample-limit", type=int, default=20)
    parser.add_argument("--execute", action="store_true", help="Write claim_event_groups shadow tables.")
    parser.add_argument("--replace-existing", action="store_true", help="With --execute, replace existing event groups in the selected owner/emperor scope before upsert.")
    parser.add_argument("--output-json", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = event_group_report(
        env_file=args.env_file,
        dsn_env=args.dsn_env,
        schema_name=args.pg_schema,
        emperor_names=args.emperor_name or [],
        statuses=args.status or [],
        owner_scopes=args.owner_scope or [],
        last_run_codes=args.last_run_code or [],
        execute=bool(args.execute),
        replace_existing=bool(args.replace_existing),
        sample_limit=max(0, int(args.sample_limit)),
    )
    if args.output_json is not None:
        write_json(args.output_json, report)
    print(json.dumps({"ok": report["ok"], "mode": report["mode"], "totals": report["totals"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ClaimEventGroupError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
