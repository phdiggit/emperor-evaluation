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

from scripts.dev.retrieval_v3_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v3_pg_schema import DEFAULT_PG_SCHEMA, DEFAULT_V3_DSN_ENV, schema_cursor  # noqa: E402
from scripts.dev.retrieval_v3_candidate_review_worklist import stable_code, stable_json, text  # noqa: E402


PROFILE = "retrieval_v3_material_candidate_plan"
RULE_CODE = "appointment_delegation"
REVIEW_VERDICT = "needs_context"
APPOINTMENT_TERMS = ("任", "拜", "授", "命", "除", "迁", "摄", "典", "领", "总管", "将军", "丞相", "太傅", "副")
RESULT_TERMS = ("破", "定", "成", "获", "劳", "赏", "诏", "复用", "再任", "薨", "败")


class NeedsContextWorklistError(ValueError):
    pass


def read_json(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def current_review(candidate_payload: Any) -> Mapping[str, Any]:
    return read_json(read_json(candidate_payload).get("candidate_review"))


def material_protocol_satisfied(row: Mapping[str, Any]) -> bool:
    facts = read_json(current_review(row.get("candidate_payload")).get("required_facts"))
    return bool(
        facts.get("has_appointment_or_authorization")
        and facts.get("has_named_actor")
        and facts.get("has_task_or_responsibility")
        and (facts.get("has_result_or_feedback") or facts.get("has_continuity_or_reuse"))
    )


def classify_context_reasons(row: Mapping[str, Any]) -> list[str]:
    review = current_review(row.get("candidate_payload"))
    facts = read_json(review.get("required_facts"))
    passages = row.get("source_passages") if isinstance(row.get("source_passages"), list) else []
    reasons: list[str] = []
    if not passages:
        reasons.append("source_missing")
    combined = " ".join(text(item.get("raw_text")) for item in passages if isinstance(item, Mapping))
    if combined and len(combined) < 240:
        reasons.append("slice_short")
    if facts.get("has_appointment_or_authorization") is False:
        reasons.append("missing_appointment")
    if facts.get("has_task_or_responsibility") is False:
        reasons.append("missing_task")
    if facts.get("has_result_or_feedback") is False:
        reasons.append("missing_result")
    if facts.get("has_continuity_or_reuse") is False:
        reasons.append("missing_continuity")
    if text(review.get("identity_gate")) not in {"", "identity_ready"}:
        reasons.append("identity_blocked")
    return reasons or ["context_review"]


def next_action_for(row: Mapping[str, Any], context_passages: Sequence[Mapping[str, Any]]) -> str:
    if material_protocol_satisfied(row):
        return "identity_resolution_only"
    if context_passages:
        return "context_review"
    return "targeted_v3_source_pack_fetch"


def context_terms(row: Mapping[str, Any]) -> tuple[str, ...]:
    review = current_review(row.get("candidate_payload"))
    terms = [text(row.get("object_name")), text(row.get("emperor_name"))]
    reasons = classify_context_reasons(row)
    if any(reason in reasons for reason in ("missing_appointment", "missing_task")):
        terms.extend(APPOINTMENT_TERMS)
    if any(reason in reasons for reason in ("missing_result", "missing_continuity")):
        terms.extend(RESULT_TERMS)
    note = text(review.get("review_note"))
    if note:
        terms.extend(note.split()[:8])
    return tuple(dict.fromkeys(term for term in terms if term))


def score_context_passage(passage: Mapping[str, Any], row: Mapping[str, Any]) -> tuple[int, list[str]]:
    raw = text(passage.get("raw_text"))
    lowered = raw.casefold()
    object_name = text(row.get("object_name"))
    emperor_name = text(row.get("emperor_name"))
    score = 0
    matches: list[str] = []
    if object_name and object_name.casefold() in lowered:
        score += 60
        matches.append("object_name")
    if emperor_name and emperor_name.casefold() in lowered:
        score += 20
        matches.append("emperor_name")
    if any(term.casefold() in lowered for term in APPOINTMENT_TERMS):
        score += 10
        matches.append("appointment_term")
    if any(term.casefold() in lowered for term in RESULT_TERMS):
        score += 5
        matches.append("result_term")
    return score, matches


def rank_context_passages(rows: Sequence[Mapping[str, Any]], row: Mapping[str, Any], *, limit: int = 6) -> list[dict[str, Any]]:
    current_codes = {text(item.get("passage_code")) for item in row.get("source_passages", []) if isinstance(item, Mapping)}
    ranked: list[dict[str, Any]] = []
    for passage in rows:
        item = dict(passage)
        if text(item.get("passage_code")) in current_codes:
            continue
        score, matches = score_context_passage(item, row)
        if score <= 0:
            continue
        item["context_score"] = score
        item["context_match_reasons"] = matches
        item["same_source_document"] = True
        ranked.append(item)
    ranked.sort(key=lambda item: (-int(item.get("context_score") or 0), text(item.get("passage_code"))))
    return ranked[:limit]


def fetch_rows(cur: Any, *, limit: int) -> list[dict[str, Any]]:
    cur.execute(
        """
        with passage_agg as (
            select csp.claim_id,
                   jsonb_agg(jsonb_build_object(
                       'source_document_id', spg.source_document_id,
                       'passage_code', spg.passage_code,
                       'document_code', sd.document_code,
                       'source_title', coalesce(sd.source_title, sd.title),
                       'locator', coalesce(nullif(spg.locator, ''), sd.locator),
                       'raw_text', spg.raw_text
                   ) order by csp.id) as source_passages
              from retrieval_v3.claim_source_passages csp
              join retrieval_v3.source_passages spg on spg.id = csp.source_passage_id
              join retrieval_v3.source_documents sd on sd.id = spg.source_document_id
             group by csp.claim_id
        )
        select c.id as candidate_id, c.candidate_code, c.claim_id, c.candidate_payload,
               mc.claim_code, mc.object_name, mc.claim_summary, mc.emperor_name,
               mc.direction::text as claim_direction, sp.pack_code as source_pack_code,
               rt.target_code, coalesce(pa.source_passages, '[]'::jsonb) as source_passages
          from retrieval_v3.claim_rule_binding_candidates c
          join retrieval_v3.material_claims mc on mc.id = c.claim_id
          join retrieval_v3.source_packs sp on sp.id = mc.source_pack_id
          join retrieval_v3.retrieval_targets rt on rt.id = sp.target_id
          left join passage_agg pa on pa.claim_id = mc.id
         where c.routed_by_profile = %s
           and c.candidate_rule_code = %s
           and c.review_status::text = 'needs_review'
           and c.candidate_payload #>> '{candidate_review,review_verdict}' = %s
         order by mc.emperor_name, c.id
         limit case when %s > 0 then %s else 2147483647 end
        """,
        (PROFILE, RULE_CODE, REVIEW_VERDICT, limit, limit),
    )
    return [dict(row) for row in cur.fetchall()]


def fetch_document_passages(cur: Any, document_ids: Sequence[int]) -> dict[int, list[dict[str, Any]]]:
    passages_by_document: dict[int, list[dict[str, Any]]] = {}
    for document_id in sorted(set(document_ids)):
        cur.execute(
            """
            select spg.source_document_id, spg.passage_code, sd.document_code,
                   coalesce(sd.source_title, sd.title) as source_title,
                   coalesce(nullif(spg.locator, ''), sd.locator) as locator,
                   spg.raw_text
              from retrieval_v3.source_passages spg
              join retrieval_v3.source_documents sd on sd.id = spg.source_document_id
             where spg.source_document_id = %s
            """,
            (document_id,),
        )
        passages_by_document[document_id] = [dict(row) for row in cur.fetchall()]
    return passages_by_document


def build_workitem(row: Mapping[str, Any], document_passages: Mapping[int, Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    current = [dict(item) for item in row.get("source_passages", []) if isinstance(item, Mapping)]
    document_ids = [int(item["source_document_id"]) for item in current if item.get("source_document_id") is not None]
    context: list[dict[str, Any]] = []
    for document_id in document_ids:
        context.extend(rank_context_passages(document_passages.get(document_id, []), row))
    context.sort(key=lambda item: (-int(item.get("context_score") or 0), text(item.get("passage_code"))))
    next_action = next_action_for(row, context)
    return {
        "workitem_code": stable_code(f"needs-context::{text(row.get('candidate_code'))}"),
        "review_code": stable_code(text(row.get("candidate_code"))),
        "candidate_id": int(row["candidate_id"]),
        "candidate_code": text(row.get("candidate_code")),
        "claim_id": int(row["claim_id"]),
        "claim_code": text(row.get("claim_code")),
        "emperor_name": text(row.get("emperor_name")),
        "object_name": text(row.get("object_name")),
        "claim_summary": text(row.get("claim_summary")),
        "source_pack_code": text(row.get("source_pack_code")),
        "target_code": text(row.get("target_code")),
        "identity_gate": text(current_review(row.get("candidate_payload")).get("identity_gate")),
        "context_reasons": classify_context_reasons(row),
        "material_protocol_satisfied": material_protocol_satisfied(row),
        "next_action": next_action,
        "context_terms": list(context_terms(row)),
        "current_source_passages": current,
        "context_passages": context[:6],
        "candidate_review": dict(current_review(row.get("candidate_payload"))),
        "context_search_plan": {
            "scope": "retrieval_v3_same_source_document",
            "source_document_ids": document_ids,
            "terms": list(context_terms(row)),
            "fallback": (
                "identity_resolution_only"
                if next_action == "identity_resolution_only"
                else "targeted_v3_source_pack_fetch_required" if next_action == "targeted_v3_source_pack_fetch" else "none"
            ),
            "legacy_data_reads": False,
        },
    }


def build_workitems(*, dsn: str, schema_name: str, limit: int) -> list[dict[str, Any]]:
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            rows = fetch_rows(cur, limit=limit)
            document_ids = [
                int(item["source_document_id"])
                for row in rows
                for item in (row.get("source_passages") or [])
                if isinstance(item, Mapping) and item.get("source_document_id") is not None
            ]
            document_passages = fetch_document_passages(cur, document_ids)
    return [build_workitem(row, document_passages) for row in rows]


def identity_resolution_patch(item: Mapping[str, Any]) -> dict[str, Any]:
    review = dict(read_json(item.get("candidate_review")))
    if not review:
        raise NeedsContextWorklistError(f"{text(item.get('review_code'))}: candidate_review is required")
    review.update({
        "review_code": text(item.get("review_code")),
        "review_verdict": "accepted_candidate",
        "review_note": text(review.get("review_note")) + " [routing: material protocol satisfied; identity handled separately]",
        "scoring_candidate": True,
        "usable_for_scoring_cluster": True,
    })
    return review


def write_outputs(workitems: Sequence[Mapping[str, Any]], output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    workitem_path = output_root / "needs_context_workitems.jsonl"
    with workitem_path.open("w", encoding="utf-8", newline="\n") as handle:
        for item in workitems:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    by_action: dict[str, list[Mapping[str, Any]]] = {}
    for item in workitems:
        by_action.setdefault(text(item.get("next_action")), []).append(item)
    identity_items = by_action.get("identity_resolution_only", [])
    (output_root / "identity_resolution_workitems.jsonl").write_text(
        "".join(stable_json(item) + "\n" for item in identity_items), encoding="utf-8"
    )
    (output_root / "identity_resolution_promotion_patch.jsonl").write_text(
        "".join(stable_json(identity_resolution_patch(item)) + "\n" for item in identity_items), encoding="utf-8"
    )
    reason_counts: Counter[str] = Counter(
        reason for item in workitems for reason in item.get("context_reasons", [])
    )
    with_context = sum(bool(item.get("context_passages")) for item in workitems)
    summary = {
        "generated_by": "scripts/dev/retrieval_v3_needs_context_worklist.py",
        "candidate_count": len(workitems),
        "second_review_required": len(by_action.get("context_review", [])),
        "with_same_document_context": with_context,
        "without_same_document_context": len(workitems) - with_context,
        "next_action_counts": {key: len(value) for key, value in sorted(by_action.items())},
        "context_reason_counts": dict(sorted(reason_counts.items())),
        "workitem_path": str(workitem_path),
        "legacy_data_reads": False,
        "write_db": False,
    }
    (output_root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a read-only v3 same-document context worklist for needs_context reviews.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default=DEFAULT_V3_DSN_ENV)
    parser.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args(argv)
    if args.env_file:
        load_env_file(args.env_file)
    workitems = build_workitems(dsn=resolve_dsn(args.dsn_env), schema_name=args.pg_schema, limit=args.limit)
    summary = write_outputs(workitems, args.output_root)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
