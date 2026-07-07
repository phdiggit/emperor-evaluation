from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v2_recall_term_sampler import recall_term_policy, stable_json, text, unique_strings, write_json


FEEDBACK_REPORT_VERSION = "recall_feedback_overlay_v0_2"
TERM_FIELDS = ("recall_terms", "matched_rule_terms", "source_terms", "trigger_terms", "terms")
SOURCE_REFINEMENT_GAP_TYPES = {"source_missing", "object_claim_undercoverage"}
ACCEPTED_STATUSES = {"accepted", "score", "scored"}
WEAK_STATUSES = {"supporting_only", "future_hint_only"}
REJECTED_STATUSES = {"rejected", "exclude", "excluded"}
CONTEXT_REJECT_REASONS = {"context_only", "duplicate", "weak_same_chain", "missing_required_fact"}
ROUTING_REJECT_REASONS = {"wrong_lane", "wrong_rule", "offscope", "candidate_profile_problem"}
FEEDBACK_CONTEXT_TERMS = {
    "丞相",
    "中书",
    "中書",
    "都督",
    "总兵",
    "總兵",
    "大将",
    "大將",
    "立太子",
    "异姓王",
    "異姓王",
    "班师",
    "班師",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        raw = line.strip()
        if not raw:
            continue
        payload = json.loads(raw)
        if not isinstance(payload, Mapping):
            raise ValueError(f"{path}:{line_no} is not a JSON object")
        rows.append(dict(payload))
    return rows


def terms_from_feedback(row: Mapping[str, Any]) -> list[str]:
    if should_exclude_from_recall_overlay(row):
        return []
    values: list[Any] = []
    for field in TERM_FIELDS:
        raw = row.get(field)
        if isinstance(raw, str):
            values.append(raw)
        elif isinstance(raw, Iterable):
            values.extend(raw)
    return unique_strings(values)


def gap_type(row: Mapping[str, Any]) -> str:
    return text(row.get("gap_type") or "not_a_gap")


def should_exclude_from_recall_overlay(row: Mapping[str, Any]) -> bool:
    return boolish(row.get("do_not_add_recall_terms")) or gap_type(row) in SOURCE_REFINEMENT_GAP_TYPES


def feedback_status(row: Mapping[str, Any]) -> str:
    return text(row.get("consumption_status") or row.get("status") or row.get("target_action")).lower()


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def term_feedback_rows(rows: Sequence[Mapping[str, Any]]) -> tuple[dict[str, list[Mapping[str, Any]]], int]:
    by_term: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    missing_terms = 0
    for row in rows:
        terms = terms_from_feedback(row)
        if not terms:
            missing_terms += 1
            continue
        for term in terms:
            by_term[term].append(row)
    return by_term, missing_terms


def source_gap_feedback_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        if gap_type(row) not in SOURCE_REFINEMENT_GAP_TYPES:
            continue
        result.append(
            {
                "claim_id": text(row.get("claim_id")),
                "binding_code": text(row.get("binding_code")),
                "emperor_name": text(row.get("emperor_name")),
                "object_name": text(row.get("object_name")),
                "candidate_lane": text(row.get("candidate_lane")),
                "rule_code": text(row.get("rule_code") or row.get("candidate_rule_code")),
                "consumption_status": feedback_status(row),
                "reject_reason": text(row.get("reject_reason") or row.get("reason")),
                "gap_type": gap_type(row),
                "gap_reason": text(row.get("gap_reason")),
                "queue": text(row.get("queue") or "source_pack_refinement"),
                "required_source_type": unique_strings(row.get("required_source_type") or []),
                "observed_material": unique_strings(row.get("observed_material") or []),
                "missing_material": unique_strings(row.get("missing_material") or []),
                "recommended_action": text(row.get("recommended_action") or "run_object_source_refiner"),
                "do_not_add_recall_terms": boolish(row.get("do_not_add_recall_terms")),
            }
        )
    return result


def gap_type_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(gap_type(row) for row in rows).items()))


def summarize_feedback_term(term: str, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    statuses = Counter(feedback_status(row) or "unknown" for row in rows)
    reject_reasons = Counter(text(row.get("reject_reason") or row.get("reason") or "unknown") for row in rows)
    accepted_count = sum(count for status, count in statuses.items() if status in ACCEPTED_STATUSES)
    weak_count = sum(count for status, count in statuses.items() if status in WEAK_STATUSES)
    rejected_count = sum(count for status, count in statuses.items() if status in REJECTED_STATUSES)
    context_reject_count = sum(count for reason, count in reject_reasons.items() if reason in CONTEXT_REJECT_REASONS)
    routing_reject_count = sum(count for reason, count in reject_reasons.items() if reason in ROUTING_REJECT_REASONS)
    hint_overridden_count = sum(1 for row in rows if boolish(row.get("factor_hint_overridden")))
    total = len(rows)
    return {
        "term": term,
        "policy": feedback_term_policy(term),
        "total_feedback_count": total,
        "accepted_count": accepted_count,
        "weak_count": weak_count,
        "rejected_count": rejected_count,
        "context_reject_count": context_reject_count,
        "routing_reject_count": routing_reject_count,
        "factor_hint_overridden_count": hint_overridden_count,
        "accept_rate": round(accepted_count / total, 4) if total else 0.0,
        "reject_rate": round(rejected_count / total, 4) if total else 0.0,
        "status_counts": dict(sorted(statuses.items())),
        "reject_reason_counts": dict(sorted(reject_reasons.items())),
        "candidate_lanes": sorted({text(row.get("candidate_lane")) for row in rows if text(row.get("candidate_lane"))}),
        "rule_codes": sorted({text(row.get("rule_code") or row.get("candidate_rule_code")) for row in rows if text(row.get("rule_code") or row.get("candidate_rule_code"))}),
        "examples": [
            {
                "claim_id": text(row.get("claim_id")),
                "status": feedback_status(row),
                "reject_reason": text(row.get("reject_reason") or row.get("reason")),
                "candidate_lane": text(row.get("candidate_lane")),
            }
            for row in rows[:3]
        ],
    }


def feedback_term_policy(term: str) -> dict[str, Any]:
    value = text(term)
    if len(value) < 2:
        return {
            "term": value,
            "profile_action": "reject_term",
            "policy_group": "feedback_token_noise",
            "risk_level": "block",
            "guard": {},
        }
    if value in FEEDBACK_CONTEXT_TERMS:
        return {
            "term": value,
            "profile_action": "context_only",
            "policy_group": "feedback_context",
            "risk_level": "block",
            "guard": {},
        }
    return recall_term_policy(value)


def suggestion_bucket(
    row: Mapping[str, Any],
    *,
    min_feedback: int,
    min_accept_rate: float,
    max_reject_rate: float,
    min_demote_reject_rate: float,
) -> str:
    policy = row.get("policy") if isinstance(row.get("policy"), Mapping) else {}
    action = text(policy.get("profile_action"))
    total = int(row.get("total_feedback_count") or 0)
    accept_rate = float(row.get("accept_rate") or 0)
    reject_rate = float(row.get("reject_rate") or 0)
    context_reject_count = int(row.get("context_reject_count") or 0)
    routing_reject_count = int(row.get("routing_reject_count") or 0)
    hint_overridden_count = int(row.get("factor_hint_overridden_count") or 0)
    if action == "reject_term":
        return "demote_terms"
    if total >= min_feedback and context_reject_count == total:
        return "context_only_terms"
    if action == "context_only":
        return "context_only_terms"
    if total >= min_feedback and accept_rate >= min_accept_rate and reject_rate <= max_reject_rate and action in {"append_rule_term", "conditional_term"}:
        return "promote_next_run_terms"
    if total >= min_feedback and reject_rate >= min_demote_reject_rate and int(row.get("accepted_count") or 0) == 0:
        return "demote_terms"
    if routing_reject_count or hint_overridden_count or action == "needs_taxonomy_review":
        return "needs_human_review_terms"
    return "observe_terms"


def build_feedback_overlay_report(
    feedback_paths: Sequence[Path],
    *,
    min_feedback: int,
    min_accept_rate: float,
    max_reject_rate: float,
    min_demote_reject_rate: float,
) -> dict[str, Any]:
    feedback_rows = [row for path in feedback_paths for row in load_jsonl(path)]
    by_term, missing_term_count = term_feedback_rows(feedback_rows)
    source_gap_rows = source_gap_feedback_rows(feedback_rows)
    source_missing_rows = [row for row in source_gap_rows if row.get("gap_type") == "source_missing"]
    excluded_from_overlay_count = sum(1 for row in feedback_rows if should_exclude_from_recall_overlay(row))
    term_rows = [
        summarize_feedback_term(term, rows)
        for term, rows in sorted(by_term.items())
    ]
    buckets: dict[str, list[dict[str, Any]]] = {
        "promote_next_run_terms": [],
        "demote_terms": [],
        "context_only_terms": [],
        "needs_human_review_terms": [],
        "observe_terms": [],
    }
    for row in term_rows:
        bucket = suggestion_bucket(
            row,
            min_feedback=min_feedback,
            min_accept_rate=min_accept_rate,
            max_reject_rate=max_reject_rate,
            min_demote_reject_rate=min_demote_reject_rate,
        )
        buckets[bucket].append(row)
    for rows in buckets.values():
        rows.sort(key=lambda row: (-int(row["total_feedback_count"]), -float(row["accept_rate"]), str(row["term"])))
    return {
        "generated_by": "scripts/dev/retrieval_v2_recall_feedback.py",
        "version": FEEDBACK_REPORT_VERSION,
        "report_type": "recall_feedback_overlay_report",
        "inputs": {
            "feedback_paths": [str(path) for path in feedback_paths],
            "feedback_row_count": len(feedback_rows),
            "rows_without_terms": missing_term_count,
            "excluded_from_overlay_count": excluded_from_overlay_count,
            "min_feedback": min_feedback,
            "min_accept_rate": min_accept_rate,
            "max_reject_rate": max_reject_rate,
            "min_demote_reject_rate": min_demote_reject_rate,
        },
        "safety": {
            "writes_profile": False,
            "writes_prompt": False,
            "writes_db": False,
            "requires_ab_before_profile_update": True,
        },
        "summary": {
            "term_count": len(term_rows),
            "suggestion_counts": {key: len(value) for key, value in buckets.items()},
            "gap_type_counts": gap_type_counts(feedback_rows),
            "source_missing_rows": len(source_missing_rows),
            "source_refinement_rows": len(source_gap_rows),
        },
        "source_gap_feedback": {
            "rows": source_gap_rows,
            "recommended_action_counts": dict(sorted(Counter(row["recommended_action"] for row in source_gap_rows).items())),
            "safety": {
                "writes_task": False,
                "writes_source_profile": False,
                "writes_db": False,
                "excluded_from_recall_overlay": True,
                "handles_object_claim_undercoverage": True,
            },
        },
        "suggestions": buckets,
        "terms": sorted(term_rows, key=lambda row: (-int(row["total_feedback_count"]), str(row["term"]))),
    }


def render_feedback_overlay_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), Mapping) else {}
    inputs = report.get("inputs") if isinstance(report.get("inputs"), Mapping) else {}
    lines = [
        "# retrieval_v2 recall feedback overlay report",
        "",
        f"- version: `{report.get('version')}`",
        f"- feedback_row_count: `{inputs.get('feedback_row_count')}`",
        f"- rows_without_terms: `{inputs.get('rows_without_terms')}`",
        f"- excluded_from_overlay_count: `{inputs.get('excluded_from_overlay_count')}`",
        f"- suggestion_counts: `{json.dumps(summary.get('suggestion_counts') or {}, ensure_ascii=False, sort_keys=True)}`",
        f"- gap_type_counts: `{json.dumps(summary.get('gap_type_counts') or {}, ensure_ascii=False, sort_keys=True)}`",
        "",
    ]
    source_gap = report.get("source_gap_feedback") if isinstance(report.get("source_gap_feedback"), Mapping) else {}
    source_gap_rows = source_gap.get("rows") if isinstance(source_gap.get("rows"), list) else []
    if source_gap_rows:
        lines.extend(
            [
                "## source_gap_feedback",
                "",
                "| emperor | object | lane | gap_type | gap_reason | required_source_type | missing_material | action |",
                "| --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for row in source_gap_rows:
            if not isinstance(row, Mapping):
                continue
            lines.append(
                "| {emperor} | {object} | {lane} | {gap_type} | {reason} | {source_type} | {missing} | {action} |".format(
                    emperor=row.get("emperor_name"),
                    object=row.get("object_name"),
                    lane=row.get("candidate_lane"),
                    gap_type=row.get("gap_type"),
                    reason=row.get("gap_reason"),
                    source_type=json.dumps(row.get("required_source_type") or [], ensure_ascii=False).replace("|", "｜"),
                    missing=json.dumps(row.get("missing_material") or [], ensure_ascii=False).replace("|", "｜"),
                    action=row.get("recommended_action"),
                )
            )
        lines.append("")
    suggestions = report.get("suggestions") if isinstance(report.get("suggestions"), Mapping) else {}
    for bucket in ("promote_next_run_terms", "demote_terms", "context_only_terms", "needs_human_review_terms", "observe_terms"):
        rows = suggestions.get(bucket) if isinstance(suggestions.get(bucket), list) else []
        lines.extend([f"## {bucket}", "", "| term | policy | group | total | accepted | rejected | accept_rate | reject_rate | reasons |", "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |"])
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            policy = row.get("policy") if isinstance(row.get("policy"), Mapping) else {}
            lines.append(
                "| {term} | {action} | {group} | {total} | {accepted} | {rejected} | {accept_rate} | {reject_rate} | {reasons} |".format(
                    term=row.get("term"),
                    action=policy.get("profile_action"),
                    group=policy.get("policy_group"),
                    total=row.get("total_feedback_count"),
                    accepted=row.get("accepted_count"),
                    rejected=row.get("rejected_count"),
                    accept_rate=row.get("accept_rate"),
                    reject_rate=row.get("reject_rate"),
                    reasons=json.dumps(row.get("reject_reason_counts") or {}, ensure_ascii=False, sort_keys=True).replace("|", "｜"),
                )
            )
        lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize retrieval_v2 consumer feedback into recall overlay suggestions.")
    parser.add_argument("--feedback-jsonl", type=Path, action="append", required=True)
    parser.add_argument("--min-feedback", type=int, default=3)
    parser.add_argument("--min-accept-rate", type=float, default=0.6)
    parser.add_argument("--max-reject-rate", type=float, default=0.25)
    parser.add_argument("--min-demote-reject-rate", type=float, default=0.75)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    report = build_feedback_overlay_report(
        args.feedback_jsonl,
        min_feedback=args.min_feedback,
        min_accept_rate=args.min_accept_rate,
        max_reject_rate=args.max_reject_rate,
        min_demote_reject_rate=args.min_demote_reject_rate,
    )
    if args.output_json is not None:
        write_json(args.output_json, report)
    if args.output_md is not None:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(render_feedback_overlay_markdown(report), encoding="utf-8")
    print(stable_json({"ok": True, "summary": report["summary"], "inputs": report["inputs"]}))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
