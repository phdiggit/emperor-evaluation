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
from scripts.dev.retrieval_v2_import_plan import ImportPlanError, json_param  # noqa: E402
from scripts.dev.retrieval_v2_intake_manifest import text  # noqa: E402
from scripts.dev.retrieval_v2_pg_schema import DEFAULT_PG_SCHEMA, DEFAULT_V3_DSN_ENV, schema_cursor  # noqa: E402


DEFAULT_DSN_ENV = DEFAULT_V3_DSN_ENV
REVIEW_SCOPES = ("active-targets", "accepted-packs")
PATCH_QUEUE_STATUSES = {"resolved", "blocked", "cancelled", "needs_review"}
TERMINAL_QUEUE_STATUSES = {"resolved", "blocked", "cancelled"}
BINDING_REVIEW_STATUSES = {"pending", "accepted", "rejected", "needs_review", "supporting_context"}
CANDIDATE_REVIEW_STATUSES = {"pending", "accepted", "rejected", "needs_review", "resolved", "retired"}


class MaterialReviewConsumerError(ImportPlanError):
    pass


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def read_patch_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise MaterialReviewConsumerError(f"{path}:{line_no}: expected JSON object")
        payload["_source_path"] = str(path)
        payload["_line_no"] = line_no
        rows.append(payload)
    return rows


def has_cjk(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)


def require_high_information_note(value: Any, *, line_ref: str) -> str:
    note = text(value)
    if not note:
        raise MaterialReviewConsumerError(f"{line_ref}: review_note is required")
    if len(note) < 24 or not has_cjk(note):
        raise MaterialReviewConsumerError(f"{line_ref}: review_note must be high-information Chinese text")
    low_information_notes = {"已处理", "同意", "无需处理", "不入分", "保留上下文", "见材料"}
    if note in low_information_notes:
        raise MaterialReviewConsumerError(f"{line_ref}: review_note is too generic")
    return note


def line_ref(row: Mapping[str, Any]) -> str:
    source = text(row.get("_source_path"))
    line_no = text(row.get("_line_no"))
    return f"{source}:{line_no}" if source or line_no else "patch row"


def validate_patch_row(row: Mapping[str, Any]) -> dict[str, Any]:
    ref = line_ref(row)
    review_code = text(row.get("review_code"))
    if not review_code:
        raise MaterialReviewConsumerError(f"{ref}: review_code is required")
    queue_status = text(row.get("queue_status"))
    if queue_status not in PATCH_QUEUE_STATUSES:
        raise MaterialReviewConsumerError(f"{ref}: unsupported queue_status {queue_status}")
    review_note = require_high_information_note(row.get("review_note"), line_ref=ref)
    binding_review_status = text(row.get("binding_review_status"))
    if binding_review_status and binding_review_status not in BINDING_REVIEW_STATUSES:
        raise MaterialReviewConsumerError(f"{ref}: unsupported binding_review_status {binding_review_status}")
    candidate_review_status = text(row.get("candidate_review_status"))
    if candidate_review_status and candidate_review_status not in CANDIDATE_REVIEW_STATUSES:
        raise MaterialReviewConsumerError(f"{ref}: unsupported candidate_review_status {candidate_review_status}")
    payload_patch = row.get("review_payload_patch")
    if payload_patch is None:
        payload_patch = {}
    if not isinstance(payload_patch, Mapping):
        raise MaterialReviewConsumerError(f"{ref}: review_payload_patch must be an object")
    return {
        "review_code": review_code,
        "queue_status": queue_status,
        "review_note": review_note,
        "binding_review_status": binding_review_status,
        "candidate_review_status": candidate_review_status,
        "review_payload_patch": dict(payload_patch),
        "_source_path": text(row.get("_source_path")),
        "_line_no": row.get("_line_no"),
    }


def validate_patch_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    validated = [validate_patch_row(row) for row in rows]
    counts = Counter(row["review_code"] for row in validated)
    duplicates = sorted(code for code, count in counts.items() if count > 1)
    if duplicates:
        raise MaterialReviewConsumerError(f"duplicate review_code in patch: {', '.join(duplicates)}")
    return validated


def scope_filter(scope: str) -> str:
    if scope == "accepted-packs":
        return "sp.status = 'accepted'"
    if scope == "active-targets":
        return "rt.target_status = 'active'"
    raise MaterialReviewConsumerError(f"unsupported scope: {scope}")


def fetch_material_review_items(cur: Any, *, item_code: str, scope: str) -> list[dict[str, Any]]:
    cur.execute(
        f"""
        select
            mrq.id,
            mrq.review_code,
            mrq.idem_key,
            mrq.review_kind,
            mrq.queue_status::text as queue_status,
            mrq.priority,
            mrq.diagnosis,
            mrq.recommended_action,
            mrq.review_note,
            mrq.review_payload,
            rt.target_code,
            rt.emperor_name,
            rt.item_code,
            sp.pack_code as source_pack_code,
            mc.claim_code,
            mc.raw_claim_code,
            mc.object_name,
            mc.object_type::text as object_type,
            mc.direction::text as claim_direction,
            mc.claim_summary,
            crb.binding_code,
            crb.raw_binding_code,
            crb.rule_code,
            crb.predicate,
            crb.direction::text as binding_direction,
            crb.object_role,
            crb.usable_for_object_payload,
            crb.usable_for_scoring_cluster,
            crb.confidence,
            crb.review_status as binding_review_status
          from retrieval_v2.material_review_queue mrq
          join retrieval_v2.material_claims mc on mc.id = mrq.claim_id
          join retrieval_v2.source_packs sp on sp.id = mc.source_pack_id
          join retrieval_v2.retrieval_targets rt on rt.id = sp.target_id
          left join retrieval_v2.claim_rule_bindings crb on crb.id = mrq.binding_id
         where mrq.queue_status in ('ready', 'needs_review')
           and {scope_filter(scope)}
           and (%s = '' or rt.item_code = %s)
         order by mrq.priority, mrq.id
        """,
        (item_code, item_code),
    )
    return [dict(row) for row in cur.fetchall()]


def fetch_review_row(cur: Any, review_code: str) -> dict[str, Any]:
    cur.execute(
        """
        select
            mrq.id,
            mrq.review_code,
            mrq.queue_status::text as queue_status,
            mrq.review_note,
            mrq.binding_id,
            mrq.candidate_id
          from retrieval_v2.material_review_queue mrq
         where mrq.review_code = %s
        """,
        (review_code,),
    )
    row = cur.fetchone()
    if not row:
        raise MaterialReviewConsumerError(f"material_review_queue row not found: {review_code}")
    return dict(row)


def resolution_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    payload = {
        "source": "retrieval_v2_material_review_consumer",
        "patch": {key: value for key, value in row.items() if not str(key).startswith("_")},
    }
    payload["patch"].update(dict(row.get("review_payload_patch") or {}))
    return {"material_review_resolution": payload}


def assert_terminal_idempotent(*, current: Mapping[str, Any], requested: Mapping[str, Any]) -> None:
    current_status = text(current.get("queue_status"))
    if current_status not in TERMINAL_QUEUE_STATUSES:
        return
    requested_status = text(requested.get("queue_status"))
    if current_status != requested_status:
        raise MaterialReviewConsumerError(
            f"{requested.get('review_code')}: terminal status is {current_status}, cannot change to {requested_status}"
        )
    current_note = text(current.get("review_note"))
    requested_note = text(requested.get("review_note"))
    if current_note and current_note != requested_note:
        raise MaterialReviewConsumerError(f"{requested.get('review_code')}: terminal review_note differs from patch")


def update_material_review(cur: Any, row: Mapping[str, Any]) -> dict[str, Any]:
    current = fetch_review_row(cur, text(row.get("review_code")))
    assert_terminal_idempotent(current=current, requested=row)
    terminal = text(row.get("queue_status")) in TERMINAL_QUEUE_STATUSES
    payload = resolution_payload(row)
    cur.execute(
        """
        update retrieval_v2.material_review_queue
           set queue_status = %s::retrieval_v2.rv2_queue_status,
               review_note = %s,
               review_payload = review_payload || %s::jsonb,
               resolved_at = case when %s then coalesce(resolved_at, now()) else resolved_at end,
               updated_at = now()
         where id = %s
        """,
        (
            text(row.get("queue_status")),
            text(row.get("review_note")),
            json_param(payload),
            terminal,
            int(current["id"]),
        ),
    )
    binding_status = text(row.get("binding_review_status"))
    if binding_status and current.get("binding_id"):
        cur.execute(
            """
            update retrieval_v2.claim_rule_bindings
               set review_status = %s,
                   binding_payload = binding_payload || %s::jsonb,
                   updated_at = now()
             where id = %s
            """,
            (binding_status, json_param(payload), int(current["binding_id"])),
        )
    candidate_status = text(row.get("candidate_review_status"))
    if candidate_status and current.get("candidate_id"):
        cur.execute(
            """
            update retrieval_v2.claim_rule_binding_candidates
               set review_status = %s::retrieval_v2.rv2_review_status,
                   candidate_payload = candidate_payload || %s::jsonb,
                   updated_at = now()
             where id = %s
            """,
            (candidate_status, json_param(payload), int(current["candidate_id"])),
        )
    return {
        "review_code": text(row.get("review_code")),
        "from_status": text(current.get("queue_status")),
        "to_status": text(row.get("queue_status")),
        "binding_updated": bool(binding_status and current.get("binding_id")),
        "candidate_updated": bool(candidate_status and current.get("candidate_id")),
    }


def apply_patch_rows(*, dsn: str, rows: Sequence[Mapping[str, Any]], execute: bool, schema_name: str = "retrieval_v2") -> dict[str, Any]:
    validated = validate_patch_rows(rows)
    psycopg, dict_row = import_psycopg()
    counts: Counter[str] = Counter()
    reviews: list[dict[str, Any]] = []
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            for row in validated:
                result = update_material_review(cur, row)
                counts["retrieval_v2.material_review_queue"] += 1
                if result["binding_updated"]:
                    counts["retrieval_v2.claim_rule_bindings"] += 1
                if result["candidate_updated"]:
                    counts["retrieval_v2.claim_rule_binding_candidates"] += 1
                reviews.append(result)
        if execute:
            conn.commit()
        else:
            conn.rollback()
    return {
        "generated_by": "scripts/dev/retrieval_v2_material_review_consumer.py",
        "command": "apply-patch",
        "write_db": execute,
        "executed": execute,
        "ok": True,
        "rows": len(validated),
        "applied_counts": dict(sorted(counts.items())),
        "reviews": reviews,
    }


def worklist_report(*, env_file: Path | None, dsn_env: str, item_code: str, scope: str, schema_name: str = "retrieval_v2") -> dict[str, Any]:
    if env_file is not None:
        load_env_file(env_file)
    psycopg, dict_row = import_psycopg()
    dsn = resolve_dsn(dsn_env)
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            rows = fetch_material_review_items(cur, item_code=item_code, scope=scope)
    status_counts = Counter(text(row.get("queue_status")) for row in rows)
    kind_counts = Counter(text(row.get("review_kind")) for row in rows)
    return {
        "generated_by": "scripts/dev/retrieval_v2_material_review_consumer.py",
        "command": "worklist",
        "item_code": item_code,
        "scope": scope,
        "ok": True,
        "totals": {
            "material_review_items": len(rows),
            "ready": status_counts.get("ready", 0),
            "needs_review": status_counts.get("needs_review", 0),
        },
        "status_counts": dict(sorted(status_counts.items())),
        "review_kind_counts": dict(sorted(kind_counts.items())),
        "items": rows,
    }


def markdown_report(payload: Mapping[str, Any]) -> str:
    lines = [
        "# retrieval_v2 material review consumer report",
        "",
        f"- command: `{payload.get('command', '')}`",
        f"- ok: `{str(payload.get('ok')).lower()}`",
        f"- write_db: `{str(payload.get('write_db', False)).lower()}`",
        f"- executed: `{str(payload.get('executed', False)).lower()}`",
        f"- scope: `{payload.get('scope', '')}`",
        "",
    ]
    totals = payload.get("totals")
    if isinstance(totals, Mapping):
        lines.extend(["## Totals", "", "| key | value |", "| --- | ---: |"])
        for key, value in totals.items():
            lines.append(f"| {key} | {value} |")
        lines.append("")
    if payload.get("applied_counts"):
        lines.extend(["## Applied", "", "| table | rows |", "| --- | ---: |"])
        for table, count in (payload.get("applied_counts") or {}).items():
            lines.append(f"| {table} | {count} |")
        lines.append("")
    items = payload.get("items")
    if isinstance(items, list) and items:
        lines.extend(["## Items", ""])
        for item in items:
            lines.append(
                f"- `{item.get('review_code')}` `{item.get('queue_status')}` "
                f"{item.get('emperor_name')} / {item.get('object_name')}: {item.get('claim_summary')}"
            )
    reviews = payload.get("reviews")
    if isinstance(reviews, list) and reviews:
        lines.extend(["## Reviews", ""])
        for item in reviews:
            lines.append(f"- `{item.get('review_code')}`: `{item.get('from_status')}` -> `{item.get('to_status')}`")
    return "\n".join(lines).rstrip() + "\n"


def write_report(output_json: Path, output_md: Path | None, payload: Mapping[str, Any]) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(markdown_report(payload), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Consume retrieval_v2 material review queue patches; dry-run unless --execute.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--env-file", type=Path)
    common.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    common.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    common.add_argument("--output-json", type=Path, required=True)
    common.add_argument("--output-md", type=Path)

    worklist = subparsers.add_parser("worklist", parents=[common], help="List pending material review rows.")
    worklist.add_argument("--item-code", default="I5B")
    worklist.add_argument("--scope", choices=REVIEW_SCOPES, default="accepted-packs")

    apply = subparsers.add_parser("apply-patch", parents=[common], help="Apply material review patch JSONL.")
    apply.add_argument("--patch-jsonl", type=Path, action="append", required=True)
    apply.add_argument("--execute", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.env_file is not None:
        load_env_file(args.env_file)
    if args.command == "worklist":
        payload = worklist_report(env_file=None, dsn_env=args.dsn_env, item_code=args.item_code, scope=args.scope, schema_name=args.pg_schema)
    elif args.command == "apply-patch":
        rows = [row for path in args.patch_jsonl for row in read_patch_jsonl(path)]
        payload = apply_patch_rows(dsn=resolve_dsn(args.dsn_env), rows=rows, execute=args.execute, schema_name=args.pg_schema)
    else:
        raise MaterialReviewConsumerError(f"unsupported command: {args.command}")
    write_report(args.output_json, args.output_md, payload)
    print(json.dumps({"ok": payload["ok"], "command": args.command, "output_json": str(args.output_json)}, ensure_ascii=False, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
