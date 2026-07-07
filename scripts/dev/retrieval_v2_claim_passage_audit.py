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
from scripts.dev.retrieval_v2_factorization_worklists import scope_predicate  # noqa: E402
from scripts.dev.retrieval_v2_import_plan import claim_passage_alignment_issue, stable_hash  # noqa: E402
from scripts.dev.retrieval_v2_intake_manifest import repo_relative, text  # noqa: E402
from scripts.dev.retrieval_v2_intake_rows import stable_json  # noqa: E402

DEFAULT_DSN_ENV = "EMPEROR_EVAL_RETRIEVAL_V2_DSN"
DEFAULT_ITEM_CODE = "I5B"
DEFAULT_RULE_CODE = ""
OPEN_REVIEW_STATUSES = ("ready", "needs_review", "running", "blocked")
REPAIR_GAP_TYPE = "material_classification_review"
REPAIR_QUEUE = "codex_review"
REPAIR_FAMILY = "claim_passage_alignment"


def json_param(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def fetch_claim_rows(
    cur: Any,
    *,
    item_code: str,
    rule_code: str,
    scope: str,
    target_names: Sequence[str],
    target_codes: Sequence[str],
) -> list[dict[str, Any]]:
    rule_filter = """
           and (
                %s = ''
                or exists (
                    select 1 from retrieval_v2.claim_rule_bindings b
                     where b.claim_id = mc.id and b.rule_code = %s
                )
                or exists (
                    select 1 from retrieval_v2.claim_rule_binding_candidates c
                     where c.claim_id = mc.id and c.source_rule_code = %s
                )
           )
    """
    cur.execute(
        f"""
        with passage_agg as (
            select
                csp.claim_id,
                jsonb_agg(
                    jsonb_build_object(
                        'passage_code', spg.passage_code,
                        'raw_text', spg.raw_text,
                        'source_title', sd.source_title,
                        'title', sd.title,
                        'locator', coalesce(nullif(spg.locator, ''), sd.locator)
                    )
                    order by csp.id
                ) as source_passages
              from retrieval_v2.claim_source_passages csp
              join retrieval_v2.source_passages spg on spg.id = csp.source_passage_id
              join retrieval_v2.source_documents sd on sd.id = spg.source_document_id
             group by csp.claim_id
        )
        select
            mc.id as claim_id,
            mc.claim_code,
            mc.object_name,
            mc.direction::text as claim_direction,
            mc.claim_summary,
            sp.id as source_pack_id,
            sp.pack_code as source_pack_code,
            rt.id as target_id,
            coalesce(
                nullif(%s, ''),
                (
                    select min(b.rule_code)
                      from retrieval_v2.claim_rule_bindings b
                     where b.claim_id = mc.id
                ),
                (
                    select min(c.source_rule_code)
                      from retrieval_v2.claim_rule_binding_candidates c
                     where c.claim_id = mc.id
                ),
                ''
            ) as source_rule_code,
            (
                select crr.id
                  from retrieval_v2.rule_contract_rules crr
                 where crr.contract_id = rt.contract_id
                   and crr.rule_code = coalesce(
                       nullif(%s, ''),
                       (
                           select min(b.rule_code)
                             from retrieval_v2.claim_rule_bindings b
                            where b.claim_id = mc.id
                       ),
                       (
                           select min(c.source_rule_code)
                             from retrieval_v2.claim_rule_binding_candidates c
                            where c.claim_id = mc.id
                       ),
                       ''
                   )
                 limit 1
            ) as contract_rule_id,
            rt.target_code,
            rt.emperor_name,
            rt.item_code,
            coalesce(pa.source_passages, '[]'::jsonb) as source_passages,
            (
                select count(*) from retrieval_v2.claim_rule_binding_candidates c
                 where c.claim_id = mc.id
            )::int as candidate_count,
            (
                select count(*) from retrieval_v2.claim_rule_binding_candidates c
                 where c.claim_id = mc.id and c.resolved_binding_id is not null
            )::int as resolved_candidate_count,
            (
                select count(*) from retrieval_v2.claim_rule_bindings b
                 where b.claim_id = mc.id
            )::int as binding_count,
            (
                select count(*) from retrieval_v2.claim_rule_binding_factor_judgments j
                 where j.claim_id = mc.id and j.review_status = 'accepted'
            )::int as factor_judgment_count,
            (
                select count(*) from retrieval_v2.claim_rule_binding_material_scores ms
                 where ms.claim_id = mc.id
            )::int as material_score_count,
            (
                select count(*) from retrieval_v2.material_review_queue mrq
                 where mrq.claim_id = mc.id
                   and mrq.queue_status in ('ready', 'needs_review', 'running', 'blocked')
            )::int as open_material_review_count
          from retrieval_v2.material_claims mc
          join retrieval_v2.source_packs sp on sp.id = mc.source_pack_id
          join retrieval_v2.retrieval_targets rt on rt.id = sp.target_id
          left join passage_agg pa on pa.claim_id = mc.id
         where rt.item_code = %s
           {rule_filter}
           and {scope_predicate(scope)}
           and (coalesce(array_length(%s::text[], 1), 0) = 0 or rt.emperor_name = any(%s::text[]))
           and (coalesce(array_length(%s::text[], 1), 0) = 0 or rt.target_code = any(%s::text[]))
         order by rt.emperor_name, source_rule_code, mc.id
        """,
        (rule_code, rule_code, item_code, rule_code, rule_code, rule_code, list(target_names), list(target_names), list(target_codes), list(target_codes)),
    )
    return [dict(row) for row in cur.fetchall()]


def audit_claim_row(row: Mapping[str, Any]) -> dict[str, Any]:
    passages = {
        text(passage.get("passage_code")): passage
        for passage in row.get("source_passages") or []
        if isinstance(passage, Mapping) and text(passage.get("passage_code"))
    }
    claim = {
        "claim_summary": text(row.get("claim_summary")),
        "object_name": text(row.get("object_name")),
        "source_passage_refs": list(passages),
    }
    issue = claim_passage_alignment_issue(claim, passages)
    status = "ok" if not issue else text(issue.get("severity")) or "warning"
    return {
        "claim_id": int(row.get("claim_id") or 0),
        "claim_code": text(row.get("claim_code")),
        "target_id": int(row.get("target_id") or 0),
        "target_code": text(row.get("target_code")),
        "emperor_name": text(row.get("emperor_name")),
        "source_pack_id": int(row.get("source_pack_id") or 0),
        "source_pack_code": text(row.get("source_pack_code")),
        "source_rule_code": text(row.get("source_rule_code")),
        "contract_rule_id": int(row.get("contract_rule_id") or 0),
        "object_name": text(row.get("object_name")),
        "claim_direction": text(row.get("claim_direction")),
        "claim_summary": text(row.get("claim_summary")),
        "passage_count": len(passages),
        "status": status,
        "issue_code": text(issue.get("code")) if issue else "",
        "issue_message": text(issue.get("message")) if issue else "",
        "candidate_count": int(row.get("candidate_count") or 0),
        "resolved_candidate_count": int(row.get("resolved_candidate_count") or 0),
        "binding_count": int(row.get("binding_count") or 0),
        "factor_judgment_count": int(row.get("factor_judgment_count") or 0),
        "material_score_count": int(row.get("material_score_count") or 0),
        "open_material_review_count": int(row.get("open_material_review_count") or 0),
        "source_passage_samples": [
            {
                "passage_code": text(passage.get("passage_code")),
                "source_title": text(passage.get("source_title")),
                "title": text(passage.get("title")),
                "locator": text(passage.get("locator")),
                "raw_text": text(passage.get("raw_text"))[:240],
            }
            for passage in list(row.get("source_passages") or [])[:3]
            if isinstance(passage, Mapping)
        ],
    }


def build_audit(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    claims = [audit_claim_row(row) for row in rows]
    flagged = [row for row in claims if row["status"] != "ok"]
    issue_counts = Counter(row["issue_code"] for row in flagged)
    status_counts = Counter(row["status"] for row in claims)
    downstream_impacted = [
        row
        for row in flagged
        if row["resolved_candidate_count"] or row["factor_judgment_count"] or row["material_score_count"]
    ]
    return {
        "ok": True,
        "generated_by": "scripts/dev/retrieval_v2_claim_passage_audit.py",
        "write_db": False,
        "executed": False,
        "totals": {
            "claims": len(claims),
            "flagged_claims": len(flagged),
            "downstream_impacted_claims": len(downstream_impacted),
            "already_queued_claims": sum(1 for row in flagged if row["open_material_review_count"]),
        },
        "status_counts": dict(sorted(status_counts.items())),
        "issue_counts": dict(sorted(issue_counts.items())),
        "sample_flagged": flagged[:20],
        "sample_downstream_impacted": downstream_impacted[:20],
        "flagged_claims": flagged,
    }


def enqueue_material_reviews(cur: Any, flagged_claims: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter()
    for row in flagged_claims:
        issue_code = text(row.get("issue_code")) or "claim_passage_alignment_review"
        review_code = "MRQ-CPA-" + stable_hash([row.get("claim_id"), issue_code], length=16)
        idem_key = "|".join(["claim_passage_alignment", text(row.get("claim_id")), issue_code])
        payload = {
            "source": "retrieval_v2_claim_passage_audit",
            "issue_code": issue_code,
            "issue_message": text(row.get("issue_message")),
            "claim_code": text(row.get("claim_code")),
            "claim_summary": text(row.get("claim_summary")),
            "object_name": text(row.get("object_name")),
            "downstream": {
                "candidate_count": row.get("candidate_count"),
                "resolved_candidate_count": row.get("resolved_candidate_count"),
                "binding_count": row.get("binding_count"),
                "factor_judgment_count": row.get("factor_judgment_count"),
                "material_score_count": row.get("material_score_count"),
            },
        }
        cur.execute(
            """
            insert into retrieval_v2.material_review_queue (
                review_code, idem_key, claim_id, binding_id, candidate_id, review_kind,
                queue_status, priority, diagnosis, recommended_action, review_note, review_payload
            )
            values (
                %s, %s, %s, null, null, %s,
                'ready', %s, %s, %s, '', %s::jsonb
            )
            on conflict on constraint rv2_material_review_queue_idem_uk do update set
                review_code = excluded.review_code,
                queue_status = retrieval_v2.material_review_queue.queue_status,
                priority = least(retrieval_v2.material_review_queue.priority, excluded.priority),
                diagnosis = excluded.diagnosis,
                recommended_action = excluded.recommended_action,
                review_payload = retrieval_v2.material_review_queue.review_payload || excluded.review_payload,
                updated_at = now()
            """,
            (
                review_code,
                idem_key,
                int(row["claim_id"]),
                issue_code,
                10 if row.get("status") == "blocker" else 40,
                issue_code,
                "暂停自动晋升、因子化和入分；回看 claim_summary 与 source_passages 是否直接支撑。",
                json_param(payload),
            ),
        )
        counts["retrieval_v2.material_review_queue"] += 1
    return dict(counts)


def repair_event_from_claim(row: Mapping[str, Any]) -> dict[str, Any]:
    rule_code = text(row.get("source_rule_code")) or "appointment_delegation"
    predicate = "claim:" + stable_hash(text(row.get("claim_code")), length=16)
    event = {
        "target_code": text(row.get("target_code")),
        "rule_code": rule_code,
        "item_code": DEFAULT_ITEM_CODE,
        "emperor_name": text(row.get("emperor_name")),
        "source_pack_code": text(row.get("source_pack_code")),
        "gap_type": REPAIR_GAP_TYPE,
        "queue": REPAIR_QUEUE,
        "status": "ready",
        "priority": 20 if row.get("status") == "blocker" else 70,
        "family_code": REPAIR_FAMILY,
        "object_name": text(row.get("object_name")),
        "predicate": predicate,
        "diagnosis": f"{row.get('issue_code')}: {row.get('issue_message')}",
        "recommended_action": "补判该 claim 的 source_slice_refs/source_passage_refs；若原文不能直接支撑 summary，则拆分、改写为 needs_review，或废弃该 claim。",
        "source": "retrieval_v2_claim_passage_audit",
        "claim_id": int(row.get("claim_id") or 0),
        "claim_code": text(row.get("claim_code")),
        "claim_summary": text(row.get("claim_summary")),
        "issue_code": text(row.get("issue_code")),
        "source_passage_samples": row.get("source_passage_samples") or [],
        "downstream": {
            "candidate_count": row.get("candidate_count"),
            "resolved_candidate_count": row.get("resolved_candidate_count"),
            "binding_count": row.get("binding_count"),
            "factor_judgment_count": row.get("factor_judgment_count"),
            "material_score_count": row.get("material_score_count"),
        },
    }
    event["idem_key"] = "|".join(
        [
            event["target_code"],
            event["rule_code"],
            event["source_pack_code"],
            event["gap_type"],
            event["family_code"],
            event["object_name"],
            event["predicate"],
        ]
    )
    event["event_code"] = "CGE-" + stable_hash(event["idem_key"], length=12)
    return event


def enqueue_gap_events(cur: Any, flagged_claims: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter()
    for row in flagged_claims:
        event = repair_event_from_claim(row)
        cur.execute(
            """
            insert into retrieval_v2.coverage_gap_events (
                event_code, idem_key, target_id, contract_rule_id, source_pack_id,
                gap_type, queue, diagnosis, recommended_action, status, priority, event_payload
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'ready', %s, %s::jsonb)
            on conflict on constraint rv2_coverage_gap_events_idem_uk do update set
                gap_type = excluded.gap_type,
                queue = excluded.queue,
                diagnosis = excluded.diagnosis,
                recommended_action = excluded.recommended_action,
                status = case
                    when retrieval_v2.coverage_gap_events.status in ('queued', 'running', 'retry_wait', 'deferred', 'resolved', 'blocked', 'cancelled')
                        then retrieval_v2.coverage_gap_events.status
                    else 'ready'
                end,
                priority = least(retrieval_v2.coverage_gap_events.priority, excluded.priority),
                event_payload = excluded.event_payload,
                updated_at = now()
            """,
            (
                event["event_code"],
                event["idem_key"],
                int(row.get("target_id") or 0),
                int(row.get("contract_rule_id") or 0) or None,
                int(row.get("source_pack_id") or 0),
                event["gap_type"],
                event["queue"],
                event["diagnosis"],
                event["recommended_action"],
                int(event["priority"]),
                json_param(event),
            ),
        )
        counts["retrieval_v2.coverage_gap_events"] += 1
    return dict(counts)


def run_audit(
    *,
    dsn: str,
    item_code: str,
    rule_code: str,
    scope: str,
    target_names: Sequence[str],
    target_codes: Sequence[str],
    execute: bool,
    write_gap_events: bool,
) -> dict[str, Any]:
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            rows = fetch_claim_rows(
                cur,
                item_code=item_code,
                rule_code=rule_code,
                scope=scope,
                target_names=target_names,
                target_codes=target_codes,
            )
            payload = build_audit(rows)
            payload["scope"] = {
                "item_code": item_code,
                "rule_code": rule_code,
                "scope": scope,
                "target_names": sorted(set(text(name) for name in target_names if text(name))),
                "target_codes": sorted(set(text(code) for code in target_codes if text(code))),
            }
            payload["write_db"] = execute
            payload["write_gap_events"] = write_gap_events
            if execute:
                counts = enqueue_material_reviews(cur, payload["flagged_claims"])
                if write_gap_events:
                    counts.update(enqueue_gap_events(cur, payload["flagged_claims"]))
                conn.commit()
                payload["executed"] = True
                payload["applied_counts"] = counts
            else:
                conn.rollback()
                payload["applied_counts"] = {}
    return payload


def render_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# retrieval_v2 claim passage audit",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- write_db: `{payload.get('write_db')}`",
        f"- executed: `{payload.get('executed')}`",
        "",
        "## Totals",
        "",
    ]
    for key, value in (payload.get("totals") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Issue Counts", ""])
    for key, value in (payload.get("issue_counts") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Sample Flagged", "", "| emperor | issue | downstream | summary |", "| --- | --- | ---: | --- |"])
    for row in payload.get("sample_flagged") or []:
        downstream = int(row.get("resolved_candidate_count") or 0) + int(row.get("factor_judgment_count") or 0) + int(row.get("material_score_count") or 0)
        summary = text(row.get("claim_summary")).replace("|", "\\|")
        lines.append(f"| {row.get('emperor_name')} | `{row.get('issue_code')}` | {downstream} | {summary} |")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit accepted retrieval_v2 claims for claim_summary/source_passage drift.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    parser.add_argument("--item-code", default=DEFAULT_ITEM_CODE)
    parser.add_argument("--rule-code", default=DEFAULT_RULE_CODE)
    parser.add_argument("--scope", default="accepted-packs", choices=("accepted-packs", "all"))
    parser.add_argument("--target-name", action="append", default=[])
    parser.add_argument("--target-code", action="append", default=[])
    parser.add_argument("--execute", action="store_true", help="Enqueue flagged claims into material_review_queue. Omit for dry-run.")
    parser.add_argument("--write-gap-events", action="store_true", help="With --execute, also enqueue codex_review coverage_gap_events for抓包返修.")
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.env_file is not None:
        load_env_file(args.env_file)
    payload = run_audit(
        dsn=resolve_dsn(args.dsn_env),
        item_code=args.item_code,
        rule_code=args.rule_code,
        scope=args.scope,
        target_names=args.target_name,
        target_codes=args.target_code,
        execute=args.execute,
        write_gap_events=args.write_gap_events,
    )
    write_json(args.output_json, payload)
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"ok": payload["ok"], "output_json": repo_relative(args.output_json), "executed": payload["executed"]}, ensure_ascii=False, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
