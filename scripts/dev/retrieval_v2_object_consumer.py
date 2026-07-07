from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v2_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v2_import_plan import ImportPlanError, json_param, stable_hash, write_json  # noqa: E402
from scripts.dev.retrieval_v2_intake_manifest import text  # noqa: E402


QUEUE_SQL = """
select
    q.id,
    q.resolution_code,
    q.idem_key,
    q.target_id,
    rt.target_code,
    q.source_pack_id,
    sp.pack_code as source_pack_code,
    q.claim_id,
    q.object_name,
    q.normalized_name,
    q.object_type::text as object_type,
    q.object_group_key,
    q.suggested_identity_key,
    q.queue_status::text as queue_status,
    q.diagnosis,
    q.resolution_note,
    q.resolved_object_id,
    q.queue_payload
from retrieval_v2.object_resolution_queue q
join retrieval_v2.retrieval_targets rt on rt.id = q.target_id
left join retrieval_v2.source_packs sp on sp.id = q.source_pack_id
where q.queue_status in ('ready', 'resolved')
order by q.priority, q.id
"""


MATERIAL_LINK_SQL = """
with primary_links as (
    select
        mc.id as claim_id,
        mc.claim_code,
        mc.object_name,
        mc.object_group_key,
        crb.object_role as role,
        max(crb.confidence) as confidence,
        array_agg(crb.id order by crb.id) as binding_ids,
        array_agg(crb.binding_code order by crb.id) as binding_codes,
        count(*) as binding_count,
        sp.id as source_pack_id,
        rt.id as target_id,
        rt.target_code
    from retrieval_v2.claim_rule_bindings crb
    join retrieval_v2.material_claims mc on mc.id = crb.claim_id
    join retrieval_v2.source_packs sp on sp.id = mc.source_pack_id
    join retrieval_v2.retrieval_targets rt on rt.id = sp.target_id
    where crb.usable_for_object_payload
    group by
        mc.id,
        mc.claim_code,
        mc.object_name,
        mc.object_group_key,
        crb.object_role,
        sp.id,
        rt.id,
        rt.target_code
),
claim_object_links as (
    select
        mc.id as claim_id,
        mc.claim_code,
        mc.object_name,
        mc.object_group_key,
        'claim_object' as role,
        mc.confidence as confidence,
        array[]::bigint[] as binding_ids,
        array[]::text[] as binding_codes,
        0 as binding_count,
        sp.id as source_pack_id,
        rt.id as target_id,
        rt.target_code
    from retrieval_v2.material_claims mc
    join retrieval_v2.source_packs sp on sp.id = mc.source_pack_id
    join retrieval_v2.retrieval_targets rt on rt.id = sp.target_id
    where not exists (
        select 1
          from retrieval_v2.claim_rule_bindings crb
         where crb.claim_id = mc.id
           and crb.usable_for_object_payload
    )
)
select * from primary_links
union all
select * from claim_object_links
order by claim_id, role
"""


def fetch_one_id(cur: Any) -> int:
    row = cur.fetchone()
    if not row or row.get("id") is None:
        raise ImportPlanError("expected statement to return id")
    return int(row["id"])


def list_text(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text(item) for item in value if text(item)]


def queue_payload(row: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = row.get("queue_payload")
    return payload if isinstance(payload, Mapping) else {}


def object_identity_key(row: Mapping[str, Any]) -> str:
    return "|".join(
        [
            "target",
            text(row.get("target_code")),
            "type",
            text(row.get("object_type") or "person"),
            "name",
            text(row.get("object_group_key")) or text(row.get("normalized_name")) or text(row.get("object_name")),
        ]
    )


def object_code(row: Mapping[str, Any]) -> str:
    return "OBJ-" + stable_hash(object_identity_key(row), length=16)


def object_name_code(*, object_id_key: str, normalized_name: str, name_kind: str) -> str:
    return "ONM-" + stable_hash([object_id_key, normalized_name, name_kind], length=16)


def target_object_code(*, target_code: str, object_id_key: str, scope_code: str) -> str:
    return "TOB-" + stable_hash([target_code, object_id_key, scope_code], length=16)


def material_link_code(*, claim_code: str, object_id_key: str, role: str) -> str:
    return "MOL-" + stable_hash([claim_code, object_id_key, role], length=16)


def script_variant_name(row: Mapping[str, Any]) -> str:
    canonical_name = text(row.get("object_name"))
    normalized_name = text(row.get("normalized_name"))
    if not normalized_name or normalized_name == canonical_name:
        return ""
    return normalized_name


def is_auto_acceptable(row: Mapping[str, Any]) -> tuple[bool, str]:
    if text(row.get("queue_status")) == "resolved":
        return bool(row.get("resolved_object_id")), "already_resolved" if row.get("resolved_object_id") else "resolved_without_object"
    if text(row.get("queue_status")) != "ready":
        return False, "status_not_ready"
    payload = queue_payload(row)
    reasons = set(list_text(payload.get("review_reasons")))
    observed_names = list_text(payload.get("observed_names"))
    object_types = set(list_text(payload.get("object_types")) or [text(row.get("object_type"))])
    if text(row.get("object_type")) != "person":
        return False, "object_type_not_person"
    if text(row.get("diagnosis")) != "single_person_like_name":
        return False, "diagnosis_not_single_person"
    if "single_person_like_name" not in reasons:
        return False, "missing_single_person_reason"
    if len(observed_names) != 1 or observed_names[0] != text(row.get("object_name")):
        return False, "observed_name_not_single"
    if object_types - {"person"}:
        return False, "mixed_object_types"
    return True, "single_person_like_name"


def resolution_note(row: Mapping[str, Any]) -> str:
    payload = queue_payload(row)
    claim_count = int(payload.get("claim_count") or 0)
    binding_count = int(payload.get("primary_binding_count") or 0)
    return (
        f"自动接受：{text(row.get('target_code'))} 下对象“{text(row.get('object_name'))}”"
        f"仅以单一 person 名称出现，关联 claim {claim_count} 条、primary binding {binding_count} 条。"
    )


def link_key(row: Mapping[str, Any]) -> tuple[int, str]:
    return (int(row.get("target_id") or 0), text(row.get("object_group_key")) or text(row.get("object_name")))


def build_object_plan(queue_rows: Sequence[Mapping[str, Any]], link_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    accepted: dict[tuple[int, str], Mapping[str, Any]] = {}
    blockers: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []

    for row in queue_rows:
        ok, reason = is_auto_acceptable(row)
        row_code = text(row.get("resolution_code"))
        if not ok:
            if text(row.get("queue_status")) == "ready":
                blockers.append({"table": "object_resolution_queue", "row_code": row_code, "code": reason, "message": text(row.get("object_name"))})
            else:
                skipped.append({"table": "object_resolution_queue", "row_code": row_code, "code": reason, "message": text(row.get("object_name"))})
            continue
        accepted[link_key(row)] = row

    link_candidates = [row for row in link_rows if link_key(row) in accepted]
    object_name_count = len(accepted) + sum(1 for row in accepted.values() if script_variant_name(row))
    operation_counts = {
        "retrieval_v2.objects": sum(1 for row in accepted.values() if text(row.get("queue_status")) == "ready"),
        "retrieval_v2.object_names": object_name_count,
        "retrieval_v2.target_objects": len(accepted),
        "retrieval_v2.object_resolution_queue": sum(1 for row in accepted.values() if text(row.get("queue_status")) == "ready"),
        "retrieval_v2.material_object_links": len(link_candidates),
    }
    return {
        "generated_by": "scripts/dev/retrieval_v2_object_consumer.py",
        "mode": "dry_run_object_consumer",
        "write_db": False,
        "executed": False,
        "ok": not blockers,
        "totals": {
            "queue_rows": len(queue_rows),
            "auto_accepted_objects": len(accepted),
            "material_object_links": len(link_candidates),
            "blockers": len(blockers),
            "skipped": len(skipped),
            "operations": sum(operation_counts.values()),
        },
        "operation_counts": operation_counts,
        "blockers": blockers,
        "skipped": skipped,
        "executed_counts": {},
    }


def fetch_queue_rows(cur: Any, *, source_pack_codes: Sequence[str] = ()) -> list[dict[str, Any]]:
    params: list[Any] = []
    sql = QUEUE_SQL
    codes = [text(code) for code in source_pack_codes if text(code)]
    if codes:
        sql = sql.replace("order by q.priority, q.id", "  and sp.pack_code = any(%s)\norder by q.priority, q.id")
        params.append(codes)
    cur.execute(sql, params if params else None)
    return [dict(row) for row in cur.fetchall()]


def fetch_link_rows(cur: Any, *, source_pack_codes: Sequence[str] = ()) -> list[dict[str, Any]]:
    params: list[Any] = []
    sql = MATERIAL_LINK_SQL
    codes = [text(code) for code in source_pack_codes if text(code)]
    if codes:
        sql = sql.replace(
            "where crb.usable_for_object_payload",
            "where crb.usable_for_object_payload\n      and sp.pack_code = any(%s)",
        )
        sql = sql.replace(
            "where not exists (",
            "where sp.pack_code = any(%s)\n      and not exists (",
        )
        params.extend([codes, codes])
    cur.execute(sql, params if params else None)
    return [dict(row) for row in cur.fetchall()]


def upsert_object(cur: Any, row: Mapping[str, Any]) -> int:
    identity_key = object_identity_key(row)
    payload = {
        "source": "retrieval_v2_object_consumer",
        "resolution_code": text(row.get("resolution_code")),
        "idem_key": text(row.get("idem_key")),
        "target_code": text(row.get("target_code")),
        "queue_payload": queue_payload(row),
    }
    cur.execute(
        """
        insert into retrieval_v2.objects (
            object_code, object_identity_key, canonical_name, normalized_name,
            object_type, identity_status, curator_note, identity_payload
        )
        values (%s, %s, %s, %s, %s::retrieval_v2.rv2_object_type, 'active', %s, %s::jsonb)
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
            object_code(row),
            identity_key,
            text(row.get("object_name")),
            text(row.get("normalized_name")) or text(row.get("object_name")),
            text(row.get("object_type") or "person"),
            resolution_note(row),
            json_param(payload),
        ),
    )
    return fetch_one_id(cur)


def upsert_object_name(cur: Any, row: Mapping[str, Any], object_id: int, *, name_kind: str = "canonical", name_text: str | None = None) -> int:
    identity_key = object_identity_key(row)
    display_name = text(name_text) or text(row.get("object_name"))
    normalized_name = display_name if name_kind == "script_variant" else text(row.get("normalized_name")) or display_name
    payload = {
        "source": "retrieval_v2_object_consumer",
        "resolution_code": text(row.get("resolution_code")),
        "name_kind": name_kind,
    }
    cur.execute(
        """
        insert into retrieval_v2.object_names (
            object_name_code, object_id, name_text, normalized_name, name_kind,
            script_variant_group_key, source, review_status, name_payload
        )
        values (%s, %s, %s, %s, %s::retrieval_v2.rv2_object_name_kind, %s, 'retrieval_v2_object_consumer', 'accepted', %s::jsonb)
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
            object_name_code(object_id_key=identity_key, normalized_name=normalized_name, name_kind=name_kind),
            object_id,
            display_name,
            normalized_name,
            name_kind,
            text(row.get("object_group_key")),
            json_param(payload),
        ),
    )
    return fetch_one_id(cur)


def upsert_target_object(cur: Any, row: Mapping[str, Any], object_id: int, first_claim_id: int | None) -> int:
    identity_key = object_identity_key(row)
    payload = {"source": "retrieval_v2_object_consumer", "resolution_code": text(row.get("resolution_code"))}
    cur.execute(
        """
        insert into retrieval_v2.target_objects (
            target_object_code, target_id, object_id, source_pack_id, first_claim_id,
            scope_code, object_role, review_status, target_object_payload
        )
        values (%s, %s, %s, %s, %s, 'item', '', 'accepted', %s::jsonb)
        on conflict on constraint rv2_target_objects_scope_uk do update set
            source_pack_id = coalesce(retrieval_v2.target_objects.source_pack_id, excluded.source_pack_id),
            first_claim_id = coalesce(retrieval_v2.target_objects.first_claim_id, excluded.first_claim_id),
            review_status = case
                when retrieval_v2.target_objects.review_status in ('rejected', 'retired') then retrieval_v2.target_objects.review_status
                else excluded.review_status
            end,
            target_object_payload = excluded.target_object_payload,
            updated_at = now()
        returning id
        """,
        (
            target_object_code(target_code=text(row.get("target_code")), object_id_key=identity_key, scope_code="item"),
            int(row.get("target_id")),
            object_id,
            row.get("source_pack_id"),
            first_claim_id,
            json_param(payload),
        ),
    )
    return fetch_one_id(cur)


def mark_queue_resolved(cur: Any, row: Mapping[str, Any], object_id: int) -> int:
    cur.execute(
        """
        update retrieval_v2.object_resolution_queue
           set queue_status = 'resolved',
               resolved_object_id = %s,
               resolution_note = case
                   when btrim(resolution_note) <> '' then resolution_note
                   else %s
               end,
               resolved_at = coalesce(resolved_at, now()),
               updated_at = now()
         where id = %s
           and queue_status in ('ready', 'resolved')
        returning id
        """,
        (object_id, resolution_note(row), int(row.get("id"))),
    )
    return fetch_one_id(cur)


def upsert_material_object_link(cur: Any, row: Mapping[str, Any], *, object_id: int, target_object_id: int, identity_key: str) -> int:
    role = text(row.get("role")) or "scored_object"
    payload = {
        "source": "retrieval_v2_object_consumer",
        "binding_codes": list_text(row.get("binding_codes")),
        "binding_ids": row.get("binding_ids") or [],
        "binding_count": int(row.get("binding_count") or 0),
    }
    cur.execute(
        """
        insert into retrieval_v2.material_object_links (
            link_code, claim_id, object_id, target_object_id, role,
            confidence, review_status, link_payload
        )
        values (%s, %s, %s, %s, %s, %s, 'accepted', %s::jsonb)
        on conflict on constraint rv2_material_object_links_uk do update set
            target_object_id = coalesce(retrieval_v2.material_object_links.target_object_id, excluded.target_object_id),
            confidence = case
                when excluded.confidence is null then retrieval_v2.material_object_links.confidence
                when retrieval_v2.material_object_links.confidence is null then excluded.confidence
                else greatest(retrieval_v2.material_object_links.confidence, excluded.confidence)
            end,
            review_status = case
                when retrieval_v2.material_object_links.review_status in ('rejected', 'retired') then retrieval_v2.material_object_links.review_status
                else excluded.review_status
            end,
            link_payload = excluded.link_payload,
            updated_at = now()
        returning id
        """,
        (
            material_link_code(claim_code=text(row.get("claim_code")), object_id_key=identity_key, role=role),
            int(row.get("claim_id")),
            object_id,
            target_object_id,
            role,
            row.get("confidence"),
            json_param(payload),
        ),
    )
    return fetch_one_id(cur)


def execute_upserts(cur: Any, queue_rows: Sequence[Mapping[str, Any]], link_rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    first_claim_by_object: dict[tuple[int, str], int] = {}
    link_rows_by_object: dict[tuple[int, str], list[Mapping[str, Any]]] = {}
    for row in link_rows:
        key = link_key(row)
        first_claim_by_object.setdefault(key, int(row.get("claim_id")))
        link_rows_by_object.setdefault(key, []).append(row)

    ids_by_key: dict[tuple[int, str], dict[str, int | str]] = {}
    counts: Counter[str] = Counter()

    for row in queue_rows:
        ok, _reason = is_auto_acceptable(row)
        if not ok:
            continue
        key = link_key(row)
        if row.get("resolved_object_id"):
            object_id = int(row["resolved_object_id"])
        else:
            object_id = upsert_object(cur, row)
            counts["retrieval_v2.objects"] += 1
        upsert_object_name(cur, row, object_id)
        counts["retrieval_v2.object_names"] += 1
        variant_name = script_variant_name(row)
        if variant_name:
            upsert_object_name(cur, row, object_id, name_kind="script_variant", name_text=variant_name)
            counts["retrieval_v2.object_names"] += 1
        target_object_id = upsert_target_object(cur, row, object_id, first_claim_by_object.get(key))
        counts["retrieval_v2.target_objects"] += 1
        if text(row.get("queue_status")) == "ready":
            mark_queue_resolved(cur, row, object_id)
            counts["retrieval_v2.object_resolution_queue"] += 1
        ids_by_key[key] = {
            "object_id": object_id,
            "target_object_id": target_object_id,
            "identity_key": object_identity_key(row),
        }

    for row in link_rows:
        ids = ids_by_key.get(link_key(row))
        if not ids:
            continue
        upsert_material_object_link(
            cur,
            row,
            object_id=int(ids["object_id"]),
            target_object_id=int(ids["target_object_id"]),
            identity_key=text(ids["identity_key"]),
        )
        counts["retrieval_v2.material_object_links"] += 1

    return dict(sorted(counts.items()))


def execute_object_consumer(*, env_file: Path | None, dsn_env: str, execute: bool, source_pack_codes: Sequence[str] = ()) -> dict[str, Any]:
    if env_file is not None:
        load_env_file(env_file)
    psycopg, dict_row = import_psycopg()
    dsn = resolve_dsn(dsn_env)
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            queue_rows = fetch_queue_rows(cur, source_pack_codes=source_pack_codes)
            link_rows = fetch_link_rows(cur, source_pack_codes=source_pack_codes)
            report = build_object_plan(queue_rows, link_rows)
            report["mode"] = "execute" if execute else "dry_run_object_consumer"
            report["write_db"] = execute
            report["source_pack_codes"] = [text(code) for code in source_pack_codes if text(code)]
            if not report["ok"]:
                conn.rollback()
                return report
            if not execute:
                conn.rollback()
                return report
            report["executed_counts"] = execute_upserts(cur, queue_rows, link_rows)
            report["executed"] = True
        conn.commit()
    return report


def markdown_report(payload: Mapping[str, Any]) -> str:
    lines = [
        "# retrieval_v2 object consumer report",
        "",
        f"- ok: `{str(payload.get('ok')).lower()}`",
        f"- write_db: `{str(payload.get('write_db')).lower()}`",
        f"- executed: `{str(payload.get('executed')).lower()}`",
        f"- queue_rows: `{payload.get('totals', {}).get('queue_rows', 0)}`",
        f"- auto_accepted_objects: `{payload.get('totals', {}).get('auto_accepted_objects', 0)}`",
        f"- material_object_links: `{payload.get('totals', {}).get('material_object_links', 0)}`",
        f"- blockers: `{payload.get('totals', {}).get('blockers', 0)}`",
        "",
        "| table | operations |",
        "| --- | ---: |",
    ]
    for table, count in (payload.get("operation_counts") or {}).items():
        lines.append(f"| {table} | {count} |")
    if payload.get("executed_counts"):
        lines.extend(["", "## Executed", "", "| table | rows |", "| --- | ---: |"])
        for table, count in (payload.get("executed_counts") or {}).items():
            lines.append(f"| {table} | {count} |")
    if payload.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        for item in payload.get("blockers") or []:
            lines.append(f"- `{item.get('row_code')}` `{item.get('code')}`: {item.get('message')}")
    if payload.get("skipped"):
        lines.extend(["", "## Skipped", ""])
        for item in payload.get("skipped") or []:
            lines.append(f"- `{item.get('row_code')}` `{item.get('code')}`: {item.get('message')}")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Consume retrieval_v2 object resolution queue; default is DB-backed dry-run.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    apply = subparsers.add_parser("apply", help="Resolve auto-acceptable object queue rows.")
    apply.add_argument("--output-json", type=Path, required=True)
    apply.add_argument("--output-md", type=Path, required=True)
    apply.add_argument("--env-file", type=Path)
    apply.add_argument("--dsn-env", default="EMPEROR_EVAL_RETRIEVAL_V2_DSN")
    apply.add_argument("--source-pack-code", action="append", default=[])
    apply.add_argument("--execute", action="store_true", help="Actually write objects and material-object links. Omit for dry-run.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "apply":
        raise ImportPlanError(f"unsupported command: {args.command}")
    payload = execute_object_consumer(
        env_file=args.env_file,
        dsn_env=args.dsn_env,
        execute=args.execute,
        source_pack_codes=args.source_pack_code,
    )
    write_json(args.output_json, payload)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(markdown_report(payload), encoding="utf-8")
    print(json.dumps({"ok": payload["ok"], "totals": payload["totals"]}, ensure_ascii=False, sort_keys=True))
    return 1 if not payload["ok"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
