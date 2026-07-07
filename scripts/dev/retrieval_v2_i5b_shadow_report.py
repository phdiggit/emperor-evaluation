from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev import retrieval_v2_contracts as contracts
from scripts.dev.retrieval_v2_bootstrap import import_psycopg, load_env_file, resolve_dsn
from scripts.dev.retrieval_v2_candidate_promoter import run_promoter
from scripts.dev.retrieval_v2_factorization_worklists import DEFAULT_FORMULA_CODE
from scripts.dev.retrieval_v2_rule_scorer import apply_rule_scores


FORMAL_RULES = {
    "delegation",
    "appointment_trust",
    "team_building",
    "talent_discovery",
    "tolerate_talent",
    "anti_nepotism",
}
I5B_REVIEW_RULES = (
    "talent_discovery",
    "appointment_trust",
    "delegation",
    "team_building",
    "tolerate_talent",
    "anti_nepotism",
)
FUTURE_HINT_RULES = {
    "power_control",
    "political_character",
    "cognition_learning",
    "key_decision",
    "military_frontier_result",
    "historical_debt",
}
VALID_CAPTURE_MODES = {"i5b_wide_shadow", "i5b_item_wide_shadow", contracts.PERSONNEL_POLITICAL_WIDE_CAPTURE_MODE}
VALID_HINT_STATUSES = {
    contracts.CANDIDATE_HINT_STATUS_CURRENT,
    contracts.CANDIDATE_HINT_STATUS_FUTURE,
    contracts.CANDIDATE_HINT_STATUS_CONTEXT,
}
CURRENT_ITEM_CODES = {"I5B"}
POLITICAL_ACTION_FACT_FIELDS = (
    "fact_schema",
    "actor",
    "object",
    "action_type",
    "event_scope",
    "office_or_domain",
    "outcome",
    "cost_or_damage",
    "time_context",
    "source_span_refs",
    "confidence",
    "completeness",
)
POLITICAL_ACTION_COMPLETENESS_KEYS = (
    "has_actor",
    "has_object",
    "has_action",
    "has_outcome",
    "same_event_chain",
    "needs_source_extension",
)
DELEGATION_CHAIN_KEYS = (
    "has_authorization_or_office",
    "has_named_delegate",
    "has_task_or_responsibility",
    "has_same_chain_outcome",
)
DELEGATION_CANDIDATE_ROLES = {
    "delegated_actor",
    "authority_recipient",
    "authority_revoked_target",
    "misdelegated_actor",
}
DELEGATION_DOMAINS = {"military", "civil", "fiscal", "frontier", "strategic", "institutional"}
DISPOSITION_TERMS = (
    "伏诛",
    "被废",
    "被杀",
    "罢免",
    "削权",
    "撤权",
    "下狱",
    "夺职",
    "削爵",
    "圈禁",
    "禁锢",
    "诛族",
)
CONCRETE_HARM_TERMS = (
    "败",
    "反",
    "叛",
    "乱",
    "失",
    "专擅",
    "结党",
    "纳贿",
    "欺罔",
    "矫诏",
    "害",
    "损",
)
DROP_CHARS = set("年月日之其以为而于与及并或后又乃所者也矣焉的了在是将使令拜任")
COMPLETENESS_KEYS = (
    "has_action_span",
    "has_object_span",
    "has_outcome_span",
    "outcome_same_event_chain",
    "needs_source_extension",
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=str) + "\n"


def text(value: Any) -> str:
    return str(value or "").strip()


def number(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


def integer(value: Any) -> int:
    return int(number(value))


def as_rows(value: Any) -> list[Mapping[str, Any]]:
    return [row for row in value or [] if isinstance(row, Mapping)]


def normalized_claim_key(*parts: Any) -> str:
    raw = "|".join(text(part) for part in parts)
    return re.sub(r"[\s，。、《》：；;,.!?！？（）()【】\[\]\"'“”‘’]+", "", raw)


def cjk_signal_chars(value: str) -> set[str]:
    return {
        char
        for char in value
        if "\u4e00" <= char <= "\u9fff" and char not in DROP_CHARS
    }


def source_text_for_refs(slice_refs: Iterable[Any], slices_by_code: Mapping[str, Mapping[str, Any]]) -> str:
    texts: list[str] = []
    for ref in slice_refs:
        row = slices_by_code.get(text(ref))
        if row:
            texts.append(text(row.get("text")))
    return "\n".join(part for part in texts if part)


def compact_for_contains(value: str) -> str:
    return re.sub(r"\s+", "", value)


def weak_overlap(summary: str, source_text: str) -> bool:
    summary_chars = cjk_signal_chars(summary)
    if len(summary_chars) < 6 or not source_text:
        return False
    source_chars = cjk_signal_chars(source_text)
    if not source_chars:
        return True
    return len(summary_chars & source_chars) / len(summary_chars) < 0.35


def target_elapsed(events: Sequence[Mapping[str, Any]], emperor_name: str) -> float | None:
    start: float | None = None
    done: float | None = None
    for event in events:
        if text(event.get("emperor_name")) != emperor_name:
            continue
        if event.get("event") == "target_start":
            start = number(event.get("elapsed_seconds"))
        elif event.get("event") == "target_done":
            done = number(event.get("elapsed_seconds"))
    if start is None or done is None or done < start:
        return None
    return round(done - start, 3)


def last_event(events: Sequence[Mapping[str, Any]], emperor_name: str, event_name: str) -> Mapping[str, Any]:
    matched: Mapping[str, Any] = {}
    for event in events:
        if text(event.get("emperor_name")) == emperor_name and event.get("event") == event_name:
            matched = event
    return matched


def event_counts(events: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        name = text(event.get("event"))
        if name:
            counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


def is_future_hint(row: Mapping[str, Any]) -> bool:
    payload = row.get("candidate_payload")
    hint_status = payload.get("hint_status") if isinstance(payload, Mapping) else None
    row_hint_status = text(row.get("hint_status"))
    return (
        text(row.get("rule_code")) in FUTURE_HINT_RULES
        or text(hint_status) == contracts.CANDIDATE_HINT_STATUS_FUTURE
        or row_hint_status == contracts.CANDIDATE_HINT_STATUS_FUTURE
    )


def is_formal_candidate(row: Mapping[str, Any]) -> bool:
    return text(row.get("rule_code")) in FORMAL_RULES and not is_future_hint(row)


def candidate_payload(row: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = row.get("candidate_payload")
    return payload if isinstance(payload, Mapping) else {}


def candidate_hint_status(row: Mapping[str, Any]) -> str:
    payload = candidate_payload(row)
    status = text(row.get("hint_status") or payload.get("hint_status"))
    if status:
        return status
    return contracts.CANDIDATE_HINT_STATUS_FUTURE if text(row.get("rule_code")) in FUTURE_HINT_RULES else contracts.CANDIDATE_HINT_STATUS_CURRENT


def candidate_item_code(row: Mapping[str, Any]) -> str:
    value = text(row.get("candidate_item_code") or candidate_payload(row).get("candidate_item_code"))
    if value:
        return value
    return "I5B" if text(row.get("rule_code")) in FORMAL_RULES else ""


def candidate_lane(row: Mapping[str, Any]) -> str:
    return text(row.get("candidate_lane") or candidate_payload(row).get("candidate_lane") or row.get("rule_code"))


def boolish_true(value: Any) -> bool:
    return value is True or text(value).lower() == "true"


def delegation_candidate_stats(rows: Sequence[Mapping[str, Any]]) -> tuple[dict[str, int], list[dict[str, Any]]]:
    counts = {
        "delegation_candidate_count": 0,
        "delegation_scoring_candidate_count": 0,
        "delegation_scoring_candidate_invalid_count": 0,
        "delegation_review_candidate_count": 0,
    }
    examples: list[dict[str, Any]] = []
    for row in rows:
        if text(row.get("rule_code")) != "delegation":
            continue
        counts["delegation_candidate_count"] += 1
        payload = candidate_payload(row)
        chain = payload.get("delegation_chain")
        chain = chain if isinstance(chain, Mapping) else {}
        scoring = boolish_true(payload.get("scoring_candidate")) or boolish_true(payload.get("usable_for_scoring_cluster"))
        if not scoring:
            counts["delegation_review_candidate_count"] += 1
            continue
        counts["delegation_scoring_candidate_count"] += 1
        missing = [key for key in DELEGATION_CHAIN_KEYS if not boolish_true(chain.get(key))]
        role = text(payload.get("candidate_role"))
        domain = text(payload.get("delegation_domain"))
        problems = []
        if missing:
            problems.append("delegation_chain_not_all_true")
        if role not in DELEGATION_CANDIDATE_ROLES:
            problems.append("invalid_candidate_role")
        if domain and domain not in DELEGATION_DOMAINS:
            problems.append("invalid_delegation_domain")
        if problems:
            counts["delegation_scoring_candidate_invalid_count"] += 1
            examples.append(
                {
                    "claim_code": text(row.get("claim_code")),
                    "problems": problems,
                    "missing_chain_keys": missing,
                    "candidate_role": role,
                    "delegation_domain": domain,
                }
            )
    return counts, examples[:30]


def candidate_route_stats(rows: Sequence[Mapping[str, Any]]) -> tuple[dict[str, int], dict[str, int], dict[str, int], list[dict[str, Any]]]:
    status_counts: dict[str, int] = {}
    item_counts: dict[str, int] = {}
    lane_counts: dict[str, int] = {}
    examples: list[dict[str, Any]] = []
    for row in rows:
        status = candidate_hint_status(row)
        item_code = candidate_item_code(row)
        lane = candidate_lane(row)
        if status:
            status_counts[status] = status_counts.get(status, 0) + 1
        if item_code:
            item_counts[item_code] = item_counts.get(item_code, 0) + 1
        if lane:
            lane_counts[lane] = lane_counts.get(lane, 0) + 1
        problems = []
        if status and status not in VALID_HINT_STATUSES:
            problems.append("invalid_hint_status")
        if item_code and item_code not in CURRENT_ITEM_CODES and status == contracts.CANDIDATE_HINT_STATUS_CURRENT:
            problems.append("future_item_marked_current")
        if text(row.get("rule_code")) in FUTURE_HINT_RULES and status == contracts.CANDIDATE_HINT_STATUS_CURRENT:
            problems.append("future_rule_marked_current")
        if problems:
            examples.append(
                {
                    "claim_code": text(row.get("claim_code")),
                    "rule_code": text(row.get("rule_code")),
                    "candidate_item_code": item_code,
                    "candidate_lane": lane,
                    "hint_status": status,
                    "problems": problems,
                }
            )
    return dict(sorted(status_counts.items())), dict(sorted(item_counts.items())), dict(sorted(lane_counts.items())), examples[:30]


def negative_disposition_risks(
    claims: Sequence[Mapping[str, Any]], bindings: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    claims_by_code = {text(row.get("claim_code")): row for row in claims}
    rows: list[dict[str, Any]] = []
    for binding in bindings:
        if text(binding.get("direction")) != "negative":
            continue
        if binding.get("usable_for_scoring_cluster", True) is False:
            continue
        claim = claims_by_code.get(text(binding.get("claim_code")), {})
        combined = f"{text(claim.get('claim_summary'))} {text(claim.get('notes'))} {text(binding.get('binding_note'))}"
        if any(term in combined for term in DISPOSITION_TERMS) and not any(
            term in combined for term in CONCRETE_HARM_TERMS
        ):
            rows.append(
                {
                    "claim_code": text(binding.get("claim_code")),
                    "object_name": text(claim.get("object_name")),
                    "predicate": text(binding.get("predicate")),
                    "reason": "negative scoring binding contains disposal terms without clear concrete-harm terms",
                }
            )
    return rows


def claim_passage_risks(
    claims: Sequence[Mapping[str, Any]], candidates: Mapping[str, Any]
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    slices = as_rows(candidates.get("candidate_slices"))
    slices_by_code = {text(row.get("slice_code")): row for row in slices if text(row.get("slice_code"))}
    counts = {"missing_source_slice_refs": 0, "unknown_source_slice_refs": 0, "weak_text_overlap": 0}
    examples: list[dict[str, Any]] = []
    for claim in claims:
        refs = list(claim.get("source_slice_refs") or [])
        claim_code_value = text(claim.get("claim_code"))
        if not refs:
            counts["missing_source_slice_refs"] += 1
            examples.append({"claim_code": claim_code_value, "risk": "missing_source_slice_refs"})
            continue
        unknown = [text(ref) for ref in refs if text(ref) not in slices_by_code]
        if unknown:
            counts["unknown_source_slice_refs"] += 1
            examples.append({"claim_code": claim_code_value, "risk": "unknown_source_slice_refs", "refs": unknown})
            continue
        if weak_overlap(text(claim.get("claim_summary")), source_text_for_refs(refs, slices_by_code)):
            counts["weak_text_overlap"] += 1
            examples.append({"claim_code": claim_code_value, "risk": "weak_text_overlap", "refs": refs[:3]})
    return counts, examples[:30]


def claim_fact_structure_stats(
    claims: Sequence[Mapping[str, Any]],
    candidates: Mapping[str, Any],
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    slices = as_rows(candidates.get("candidate_slices"))
    slices_by_code = {text(row.get("slice_code")): row for row in slices if text(row.get("slice_code"))}
    counts = {
        "claims_with_fact_payload": 0,
        "claims_with_evidence_spans": 0,
        "claims_with_claim_completeness": 0,
        "evidence_span_count": 0,
        "span_missing_source_slice_ref": 0,
        "span_unknown_source_slice_ref": 0,
        "span_text_not_found": 0,
        "complete_action_object_claims": 0,
        "complete_outcome_chain_claims": 0,
        "needs_source_extension_claims": 0,
        "claims_with_political_action_v1": 0,
        "claims_missing_political_action_fact_fields": 0,
        "political_action_source_span_ref_missing": 0,
        "political_action_source_span_ref_unknown": 0,
        "political_action_complete_action_object_claims": 0,
        "political_action_complete_outcome_claims": 0,
        "political_action_needs_source_extension_claims": 0,
    }
    examples: list[dict[str, Any]] = []
    for claim in claims:
        claim_code_value = text(claim.get("claim_code"))
        fact_payload = claim.get("fact_payload")
        spans = as_rows(claim.get("evidence_spans"))
        completeness = claim.get("claim_completeness")
        if isinstance(fact_payload, Mapping) and any(text(value) for value in fact_payload.values()):
            counts["claims_with_fact_payload"] += 1
            if text(fact_payload.get("fact_schema")) == contracts.POLITICAL_ACTION_FACT_SCHEMA:
                counts["claims_with_political_action_v1"] += 1
                claim_source_refs = {text(ref) for ref in claim.get("source_slice_refs") or [] if text(ref)}
                missing_fields = [key for key in POLITICAL_ACTION_FACT_FIELDS if key not in fact_payload]
                if missing_fields:
                    counts["claims_missing_political_action_fact_fields"] += 1
                    examples.append(
                        {
                            "claim_code": claim_code_value,
                            "risk": "claims_missing_political_action_fact_fields",
                            "missing_fields": missing_fields,
                        }
                    )
                source_span_refs = [text(ref) for ref in fact_payload.get("source_span_refs") or [] if text(ref)]
                if not source_span_refs:
                    counts["political_action_source_span_ref_missing"] += 1
                    examples.append({"claim_code": claim_code_value, "risk": "political_action_source_span_ref_missing"})
                else:
                    unknown_refs = [ref for ref in source_span_refs if ref not in slices_by_code and ref not in claim_source_refs]
                    if unknown_refs:
                        counts["political_action_source_span_ref_unknown"] += 1
                        examples.append(
                            {
                                "claim_code": claim_code_value,
                                "risk": "political_action_source_span_ref_unknown",
                                "refs": unknown_refs,
                            }
                        )
                payload_completeness = fact_payload.get("completeness")
                if isinstance(payload_completeness, Mapping):
                    if (
                        payload_completeness.get("has_actor") is True
                        and payload_completeness.get("has_object") is True
                        and payload_completeness.get("has_action") is True
                    ):
                        counts["political_action_complete_action_object_claims"] += 1
                    if (
                        payload_completeness.get("has_actor") is True
                        and payload_completeness.get("has_object") is True
                        and payload_completeness.get("has_action") is True
                        and payload_completeness.get("has_outcome") is True
                        and payload_completeness.get("same_event_chain") is True
                    ):
                        counts["political_action_complete_outcome_claims"] += 1
                    if payload_completeness.get("needs_source_extension") is True:
                        counts["political_action_needs_source_extension_claims"] += 1
        if spans:
            counts["claims_with_evidence_spans"] += 1
        if isinstance(completeness, Mapping) and any(key in completeness for key in COMPLETENESS_KEYS):
            counts["claims_with_claim_completeness"] += 1
            if completeness.get("has_action_span") is True and completeness.get("has_object_span") is True:
                counts["complete_action_object_claims"] += 1
            if (
                completeness.get("has_action_span") is True
                and completeness.get("has_object_span") is True
                and completeness.get("has_outcome_span") is True
                and completeness.get("outcome_same_event_chain") is True
            ):
                counts["complete_outcome_chain_claims"] += 1
            if completeness.get("needs_source_extension") is True:
                counts["needs_source_extension_claims"] += 1
        for span in spans:
            counts["evidence_span_count"] += 1
            ref = text(span.get("source_slice_ref") or span.get("slice_code"))
            span_text = text(span.get("text"))
            if not ref:
                counts["span_missing_source_slice_ref"] += 1
                examples.append({"claim_code": claim_code_value, "risk": "span_missing_source_slice_ref"})
                continue
            source_slice = slices_by_code.get(ref)
            if not source_slice:
                counts["span_unknown_source_slice_ref"] += 1
                examples.append({"claim_code": claim_code_value, "risk": "span_unknown_source_slice_ref", "ref": ref})
                continue
            if span_text and compact_for_contains(span_text) not in compact_for_contains(text(source_slice.get("text"))):
                counts["span_text_not_found"] += 1
                examples.append(
                    {
                        "claim_code": claim_code_value,
                        "risk": "span_text_not_found",
                        "ref": ref,
                        "span_text": span_text[:80],
                    }
                )
    return counts, examples[:30]


def duplicate_claims(people: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, list[str]] = {}
    for person in people:
        for claim in as_rows(person.get("_claims")):
            key = normalized_claim_key(
                person.get("name"),
                claim.get("object_name"),
                claim.get("direction"),
                claim.get("claim_summary"),
            )
            if key:
                seen.setdefault(key, []).append(text(claim.get("claim_code")))
    return [
        {"key": key, "claim_codes": codes}
        for key, codes in sorted(seen.items())
        if len([code for code in codes if code]) > 1
    ][:50]


def person_report(person: Mapping[str, Any], events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    name = text(person.get("name"))
    candidates_path = text((person.get("files") or {}).get("final_candidates"))
    judge_path = text((person.get("files") or {}).get("final_judge_result"))
    candidates = load_json(Path(candidates_path)) if candidates_path and Path(candidates_path).exists() else {}
    judge = load_json(Path(judge_path)) if judge_path and Path(judge_path).exists() else {}
    claims = as_rows(judge.get("claims"))
    bindings = as_rows(judge.get("primary_bindings") or judge.get("bindings"))
    secondary = as_rows(judge.get("secondary_binding_candidates"))
    delegation_counts, delegation_examples = delegation_candidate_stats(secondary)
    status_counts, item_counts, lane_counts, route_examples = candidate_route_stats(secondary)
    passage_counts, passage_examples = claim_passage_risks(claims, candidates)
    fact_counts, fact_examples = claim_fact_structure_stats(claims, candidates)
    disposition_risks = negative_disposition_risks(claims, bindings)
    object_source_done = last_event(events, name, "taskgen_object_source_presearch_done")
    object_source_start = last_event(events, name, "taskgen_object_source_presearch_start")
    candidate_done = last_event(events, name, "candidate_done")
    return {
        "name": name,
        "target_code": text(person.get("target_code")),
        "capture_mode": text(person.get("capture_mode")),
        "formal_consumption_source": person.get("formal_consumption_source"),
        "elapsed_seconds": target_elapsed(events, name),
        "taskgen_elapsed_seconds": person.get("taskgen_elapsed_seconds"),
        "object_source_presearch_elapsed_seconds": object_source_done.get("elapsed_seconds_stage"),
        "object_source_presearch_hit_count": integer(object_source_done.get("hit_count")),
        "object_source_presearch_max_objects": integer(object_source_start.get("max_objects")),
        "object_source_presearch_pages_per_object": integer(object_source_start.get("pages_per_object")),
        "candidate_elapsed_seconds": candidate_done.get("elapsed_seconds_stage"),
        "judge_elapsed_seconds": person.get("judge_elapsed_seconds"),
        "candidate_slices": integer(person.get("candidate_slices")),
        "claim_count": len(claims),
        "primary_binding_count": len(bindings),
        "secondary_binding_count": len(secondary),
        "formal_secondary_candidate_count": sum(1 for row in secondary if is_formal_candidate(row)),
        "future_hint_count": sum(1 for row in secondary if is_future_hint(row)),
        "candidate_status_counts": status_counts,
        "candidate_item_counts": item_counts,
        "candidate_lane_counts": lane_counts,
        "candidate_route_problem_count": len(route_examples),
        "candidate_route_problem_examples": route_examples,
        **delegation_counts,
        "delegation_scoring_candidate_invalid_examples": delegation_examples,
        "fetch_error_count": integer(person.get("fetch_error_count")),
        "candidate_coverage_gap_count": integer(person.get("candidate_coverage_gap_count")),
        "judge_coverage_gap_count": integer(person.get("judge_coverage_gap_count")),
        "judge_anomaly_block_count": integer(person.get("judge_anomaly_block_count")),
        "judge_anomaly_warning_count": integer(person.get("judge_anomaly_warning_count")),
        "objects_without_slices": list(person.get("objects_without_slices") or []),
        "claim_passage_risk_counts": passage_counts,
        "claim_passage_risk_examples": passage_examples,
        "claim_fact_structure_counts": fact_counts,
        "claim_fact_structure_examples": fact_examples,
        "negative_disposition_risk_count": len(disposition_risks),
        "negative_disposition_risk_examples": disposition_risks[:20],
        "_claims": claims,
    }


def strip_private_fields(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [{key: value for key, value in row.items() if not key.startswith("_")} for row in rows]


def merge_count_maps(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in rows:
        values = row.get(key)
        if not isinstance(values, Mapping):
            continue
        for value_key, value_count in values.items():
            name = text(value_key)
            if name:
                result[name] = result.get(name, 0) + integer(value_count)
    return dict(sorted(result.items()))


def build_recommendations(report: Mapping[str, Any]) -> list[dict[str, str]]:
    totals = report["totals"]
    recommendations: list[dict[str, str]] = []
    if not report["shadow_contract"]["valid"]:
        recommendations.append({"severity": "block", "message": "run is not marked as a non-formal I5B-wide shadow pilot"})
    if totals["judge_anomaly_block_count"]:
        recommendations.append({"severity": "block", "message": "judge anomaly blocks must be repaired before promotion"})
    if totals["missing_source_slice_refs"] or totals["unknown_source_slice_refs"]:
        recommendations.append({"severity": "block", "message": "claims with missing or unknown source_slice_refs need repair"})
    if totals["weak_text_overlap"]:
        recommendations.append({"severity": "warning", "message": "sample weak-overlap claims for summary/passage drift"})
    if totals["claim_count"] and totals["claims_with_fact_payload"] < totals["claim_count"]:
        recommendations.append({"severity": "warning", "message": "some claims lack structured fact_payload"})
    if totals["capture_profile"] == contracts.PERSONNEL_POLITICAL_WIDE_PROFILE:
        if totals["claim_count"] and totals["claims_with_political_action_v1"] < totals["claim_count"]:
            recommendations.append({"severity": "warning", "message": "some claims lack political_action_v1 fact_payload"})
        if totals["claims_missing_political_action_fact_fields"]:
            recommendations.append({"severity": "warning", "message": "some political_action_v1 payloads miss fixed schema fields"})
        if totals["political_action_source_span_ref_missing"] or totals["political_action_source_span_ref_unknown"]:
            recommendations.append({"severity": "warning", "message": "political_action_v1 source_span_refs need repair"})
        if totals["candidate_route_problem_count"]:
            recommendations.append({"severity": "block", "message": "candidate lane/status contract has invalid current/future routing"})
    if totals["claim_count"] and totals["claims_with_evidence_spans"] < totals["claim_count"]:
        recommendations.append({"severity": "warning", "message": "some claims lack evidence_spans"})
    if totals["span_missing_source_slice_ref"] or totals["span_unknown_source_slice_ref"] or totals["span_text_not_found"]:
        recommendations.append({"severity": "warning", "message": "evidence_spans should point to exact source slice text"})
    if totals["duplicate_claim_risk_count"]:
        recommendations.append({"severity": "warning", "message": "dedupe repeated canonical claim summaries before widening"})
    if totals["formal_secondary_candidate_count"] == 0 and totals["claim_count"]:
        recommendations.append({"severity": "warning", "message": "shadow pilot produced claims but no formal secondary candidates"})
    if totals["delegation_scoring_candidate_invalid_count"]:
        recommendations.append({"severity": "block", "message": "delegation scoring candidates must have all chain flags true and valid candidate_role"})
    if totals["fetch_error_count"]:
        recommendations.append({"severity": "warning", "message": "fetch errors may hide source coverage gaps"})
    return recommendations


def build_report(run_root: Path) -> dict[str, Any]:
    summary = load_json(run_root / "summary.json")
    events = read_jsonl(run_root / "run_events.jsonl")
    people = [person_report(row, events) for row in as_rows(summary.get("people"))]
    duplicates = duplicate_claims(people)
    capture_profile = text(summary.get("capture_profile") or summary.get("clean_policy", {}).get("capture_profile"))
    totals = {
        "target_count": len(people),
        "capture_profile": capture_profile,
        "elapsed_seconds": number(summary.get("total_elapsed_seconds") or summary.get("elapsed_seconds")),
        "usage": summary.get("totals", {}).get("usage") if isinstance(summary.get("totals"), Mapping) else {},
        "candidate_slices": sum(row["candidate_slices"] for row in people),
        "claim_count": sum(row["claim_count"] for row in people),
        "primary_binding_count": sum(row["primary_binding_count"] for row in people),
        "secondary_binding_count": sum(row["secondary_binding_count"] for row in people),
        "formal_secondary_candidate_count": sum(row["formal_secondary_candidate_count"] for row in people),
        "future_hint_count": sum(row["future_hint_count"] for row in people),
        "candidate_status_counts": merge_count_maps(people, "candidate_status_counts"),
        "candidate_item_counts": merge_count_maps(people, "candidate_item_counts"),
        "candidate_lane_counts": merge_count_maps(people, "candidate_lane_counts"),
        "candidate_route_problem_count": sum(row["candidate_route_problem_count"] for row in people),
        "delegation_candidate_count": sum(row["delegation_candidate_count"] for row in people),
        "delegation_scoring_candidate_count": sum(row["delegation_scoring_candidate_count"] for row in people),
        "delegation_scoring_candidate_invalid_count": sum(
            row["delegation_scoring_candidate_invalid_count"] for row in people
        ),
        "delegation_review_candidate_count": sum(row["delegation_review_candidate_count"] for row in people),
        "fetch_error_count": sum(row["fetch_error_count"] for row in people),
        "candidate_coverage_gap_count": sum(row["candidate_coverage_gap_count"] for row in people),
        "judge_coverage_gap_count": sum(row["judge_coverage_gap_count"] for row in people),
        "judge_anomaly_block_count": sum(row["judge_anomaly_block_count"] for row in people),
        "judge_anomaly_warning_count": sum(row["judge_anomaly_warning_count"] for row in people),
        "missing_source_slice_refs": sum(row["claim_passage_risk_counts"]["missing_source_slice_refs"] for row in people),
        "unknown_source_slice_refs": sum(row["claim_passage_risk_counts"]["unknown_source_slice_refs"] for row in people),
        "weak_text_overlap": sum(row["claim_passage_risk_counts"]["weak_text_overlap"] for row in people),
        "negative_disposition_risk_count": sum(row["negative_disposition_risk_count"] for row in people),
        "claims_with_fact_payload": sum(row["claim_fact_structure_counts"]["claims_with_fact_payload"] for row in people),
        "claims_with_evidence_spans": sum(row["claim_fact_structure_counts"]["claims_with_evidence_spans"] for row in people),
        "claims_with_claim_completeness": sum(row["claim_fact_structure_counts"]["claims_with_claim_completeness"] for row in people),
        "evidence_span_count": sum(row["claim_fact_structure_counts"]["evidence_span_count"] for row in people),
        "span_missing_source_slice_ref": sum(row["claim_fact_structure_counts"]["span_missing_source_slice_ref"] for row in people),
        "span_unknown_source_slice_ref": sum(row["claim_fact_structure_counts"]["span_unknown_source_slice_ref"] for row in people),
        "span_text_not_found": sum(row["claim_fact_structure_counts"]["span_text_not_found"] for row in people),
        "complete_action_object_claims": sum(row["claim_fact_structure_counts"]["complete_action_object_claims"] for row in people),
        "complete_outcome_chain_claims": sum(row["claim_fact_structure_counts"]["complete_outcome_chain_claims"] for row in people),
        "needs_source_extension_claims": sum(row["claim_fact_structure_counts"]["needs_source_extension_claims"] for row in people),
        "claims_with_political_action_v1": sum(row["claim_fact_structure_counts"]["claims_with_political_action_v1"] for row in people),
        "claims_missing_political_action_fact_fields": sum(
            row["claim_fact_structure_counts"]["claims_missing_political_action_fact_fields"] for row in people
        ),
        "political_action_source_span_ref_missing": sum(
            row["claim_fact_structure_counts"]["political_action_source_span_ref_missing"] for row in people
        ),
        "political_action_source_span_ref_unknown": sum(
            row["claim_fact_structure_counts"]["political_action_source_span_ref_unknown"] for row in people
        ),
        "political_action_complete_action_object_claims": sum(
            row["claim_fact_structure_counts"]["political_action_complete_action_object_claims"] for row in people
        ),
        "political_action_complete_outcome_claims": sum(
            row["claim_fact_structure_counts"]["political_action_complete_outcome_claims"] for row in people
        ),
        "political_action_needs_source_extension_claims": sum(
            row["claim_fact_structure_counts"]["political_action_needs_source_extension_claims"] for row in people
        ),
        "duplicate_claim_risk_count": len(duplicates),
    }
    contract = {
        "capture_mode": text(summary.get("capture_mode") or summary.get("clean_policy", {}).get("capture_mode")),
        "capture_profile": capture_profile,
        "fact_schema": text(summary.get("fact_schema") or summary.get("clean_policy", {}).get("fact_schema")),
        "candidate_route_table_version": text(
            summary.get("candidate_route_table_version") or summary.get("clean_policy", {}).get("candidate_route_table_version")
        ),
        "formal_consumption_source": summary.get("formal_consumption_source"),
    }
    contract["valid"] = contract["capture_mode"] in VALID_CAPTURE_MODES and contract["formal_consumption_source"] is False
    if contract["capture_profile"] == contracts.PERSONNEL_POLITICAL_WIDE_PROFILE:
        contract["valid"] = (
            contract["valid"]
            and contract["fact_schema"] == contracts.POLITICAL_ACTION_FACT_SCHEMA
            and contract["candidate_route_table_version"] == contracts.CANDIDATE_ROUTE_TABLE_VERSION
        )
    report: dict[str, Any] = {
        "run_root": str(run_root),
        "summary_path": str(run_root / "summary.json"),
        "shadow_contract": contract,
        "event_counts": event_counts(events),
        "totals": totals,
        "people": strip_private_fields(people),
        "duplicate_claim_risks": duplicates,
    }
    report["recommendations"] = build_recommendations(report)
    return report


def markdown_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    output = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        output.append("| " + " | ".join(text(value) for value in row) + " |")
    return "\n".join(output)


def render_markdown(report: Mapping[str, Any]) -> str:
    totals = report["totals"]
    people = report["people"]
    rows = [
        [
            row["name"],
            row["elapsed_seconds"],
            row["object_source_presearch_elapsed_seconds"],
            row["candidate_slices"],
            row["claim_count"],
            row["secondary_binding_count"],
            row["formal_secondary_candidate_count"],
            row["future_hint_count"],
            row["delegation_scoring_candidate_count"],
            row["delegation_scoring_candidate_invalid_count"],
            row["judge_coverage_gap_count"],
            row["judge_anomaly_block_count"],
            row["negative_disposition_risk_count"],
        ]
        for row in people
    ]
    rec_rows = [[row["severity"], row["message"]] for row in report["recommendations"]]
    lines = [
        "# I5B-wide shadow pilot report",
        "",
        f"- run_root: `{report['run_root']}`",
        f"- shadow_contract_valid: `{report['shadow_contract']['valid']}`",
        f"- capture_mode: `{report['shadow_contract']['capture_mode']}`",
        f"- capture_profile: `{report['shadow_contract']['capture_profile']}`",
        f"- fact_schema: `{report['shadow_contract']['fact_schema']}`",
        f"- candidate_route_table_version: `{report['shadow_contract']['candidate_route_table_version']}`",
        f"- target_count: `{totals['target_count']}`",
        f"- elapsed_seconds: `{totals['elapsed_seconds']}`",
        f"- usage: `{stable_json(totals['usage']).strip()}`",
        "",
        markdown_table(
            [
                "target",
                "elapsed",
                "obj_presearch",
                "slices",
                "claims",
                "secondary",
                "formal_secondary",
                "future_hint",
                "delegation_scoring",
                "delegation_invalid",
                "judge_gaps",
                "blocks",
                "disposal_risk",
            ],
            rows,
        ),
        "",
        "## Quality Proxies",
        "",
        f"- missing_source_slice_refs: `{totals['missing_source_slice_refs']}`",
        f"- unknown_source_slice_refs: `{totals['unknown_source_slice_refs']}`",
        f"- weak_text_overlap: `{totals['weak_text_overlap']}`",
        f"- duplicate_claim_risk_count: `{totals['duplicate_claim_risk_count']}`",
        f"- negative_disposition_risk_count: `{totals['negative_disposition_risk_count']}`",
        f"- delegation_candidate_count: `{totals['delegation_candidate_count']}`",
        f"- delegation_scoring_candidate_count: `{totals['delegation_scoring_candidate_count']}`",
        f"- delegation_scoring_candidate_invalid_count: `{totals['delegation_scoring_candidate_invalid_count']}`",
        f"- delegation_review_candidate_count: `{totals['delegation_review_candidate_count']}`",
        f"- candidate_status_counts: `{stable_json(totals['candidate_status_counts']).strip()}`",
        f"- candidate_item_counts: `{stable_json(totals['candidate_item_counts']).strip()}`",
        f"- candidate_lane_counts: `{stable_json(totals['candidate_lane_counts']).strip()}`",
        f"- candidate_route_problem_count: `{totals['candidate_route_problem_count']}`",
        f"- claims_with_fact_payload: `{totals['claims_with_fact_payload']}` / `{totals['claim_count']}`",
        f"- claims_with_political_action_v1: `{totals['claims_with_political_action_v1']}` / `{totals['claim_count']}`",
        f"- claims_missing_political_action_fact_fields: `{totals['claims_missing_political_action_fact_fields']}`",
        f"- political_action_source_span_ref_missing: `{totals['political_action_source_span_ref_missing']}`",
        f"- political_action_source_span_ref_unknown: `{totals['political_action_source_span_ref_unknown']}`",
        f"- political_action_complete_action_object_claims: `{totals['political_action_complete_action_object_claims']}`",
        f"- political_action_complete_outcome_claims: `{totals['political_action_complete_outcome_claims']}`",
        f"- political_action_needs_source_extension_claims: `{totals['political_action_needs_source_extension_claims']}`",
        f"- claims_with_evidence_spans: `{totals['claims_with_evidence_spans']}` / `{totals['claim_count']}`",
        f"- claims_with_claim_completeness: `{totals['claims_with_claim_completeness']}` / `{totals['claim_count']}`",
        f"- evidence_span_count: `{totals['evidence_span_count']}`",
        f"- span_missing_source_slice_ref: `{totals['span_missing_source_slice_ref']}`",
        f"- span_unknown_source_slice_ref: `{totals['span_unknown_source_slice_ref']}`",
        f"- span_text_not_found: `{totals['span_text_not_found']}`",
        f"- complete_outcome_chain_claims: `{totals['complete_outcome_chain_claims']}`",
        f"- needs_source_extension_claims: `{totals['needs_source_extension_claims']}`",
        "",
        "## Recommendations",
        "",
        markdown_table(["severity", "message"], rec_rows) if rec_rows else "No block/warning recommendation.",
        "",
    ]
    return "\n".join(lines)


def fetch_rows(cur: Any, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
    cur.execute(sql, tuple(params))
    return [dict(row) for row in cur.fetchall()]


def fetch_consumed_candidate_lane_probe(*, dsn: str, source_pack_code: str) -> dict[str, Any]:
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            pack_rows = fetch_rows(
                cur,
                """
                select sp.id, sp.pack_code, sp.status, sp.coverage_status, rt.target_code, rt.emperor_name, rt.item_code
                  from retrieval_v2.source_packs sp
                  join retrieval_v2.retrieval_targets rt on rt.id = sp.target_id
                 where sp.pack_code = %s
                """,
                (source_pack_code,),
            )
            candidate_counts = fetch_rows(
                cur,
                """
                select
                    coalesce(nullif(c.hint_status, ''), '<blank>') as hint_status,
                    coalesce(nullif(c.candidate_item_code, ''), '<blank>') as candidate_item_code,
                    coalesce(nullif(c.candidate_lane, ''), '<blank>') as candidate_lane,
                    c.candidate_rule_code,
                    (c.candidate_contract_rule_id is not null) as has_candidate_contract_rule,
                    count(*)::int as n
                  from retrieval_v2.claim_rule_binding_candidates c
                  join retrieval_v2.material_claims mc on mc.id = c.claim_id
                  join retrieval_v2.source_packs sp on sp.id = mc.source_pack_id
                 where sp.pack_code = %s
                 group by 1, 2, 3, 4, 5
                 order by 1, 2, 3, 4, 5
                """,
                (source_pack_code,),
            )
            future_hint_resolved_count = fetch_rows(
                cur,
                """
                select count(*)::int as n
                  from retrieval_v2.claim_rule_binding_candidates c
                  join retrieval_v2.material_claims mc on mc.id = c.claim_id
                  join retrieval_v2.source_packs sp on sp.id = mc.source_pack_id
                 where sp.pack_code = %s
                   and (
                        c.hint_status = 'future_rule_hint'
                        or c.candidate_payload->>'hint_status' = 'future_rule_hint'
                        or c.candidate_payload->>'route_status' = 'future_rule_hint'
                   )
                   and c.resolved_binding_id is not null
                """,
                (source_pack_code,),
            )[0]["n"]
            required_facts_shapes = fetch_rows(
                cur,
                """
                select jsonb_typeof(c.required_facts_present) as json_type, count(*)::int as n
                  from retrieval_v2.claim_rule_binding_candidates c
                  join retrieval_v2.material_claims mc on mc.id = c.claim_id
                  join retrieval_v2.source_packs sp on sp.id = mc.source_pack_id
                 where sp.pack_code = %s
                 group by 1
                 order by 1
                """,
                (source_pack_code,),
            )
            sample_future_hints = fetch_rows(
                cur,
                """
                select c.candidate_code, c.candidate_rule_code, c.candidate_lane, c.hint_status, c.candidate_reason
                  from retrieval_v2.claim_rule_binding_candidates c
                  join retrieval_v2.material_claims mc on mc.id = c.claim_id
                  join retrieval_v2.source_packs sp on sp.id = mc.source_pack_id
                 where sp.pack_code = %s
                   and c.hint_status = 'future_rule_hint'
                 order by c.id
                 limit 20
                """,
                (source_pack_code,),
            )
    return {
        "pack_code": source_pack_code,
        "pack": pack_rows,
        "candidate_counts": candidate_counts,
        "future_hint_resolved_count": future_hint_resolved_count,
        "required_facts_shapes": required_facts_shapes,
        "sample_future_hints": sample_future_hints,
    }


def build_consumed_pack_review(
    *,
    env_file: Path | None,
    dsn_env: str,
    source_pack_code: str,
    item_code: str = "I5B",
    source_rule_code: str = "i5b_item_wide",
    formula_code: str = DEFAULT_FORMULA_CODE,
    emperors: Sequence[str] = (),
) -> dict[str, Any]:
    if env_file is not None:
        load_env_file(env_file)
    dsn = resolve_dsn(dsn_env)
    lane_probe = fetch_consumed_candidate_lane_probe(dsn=dsn, source_pack_code=source_pack_code)
    pack_rows = lane_probe.get("pack") or []
    inferred_emperors = tuple(text(row.get("emperor_name")) for row in pack_rows if text(row.get("emperor_name")))
    emperor_filters = tuple(text(value) for value in emperors if text(value)) or inferred_emperors
    promoter = run_promoter(
        env_file=None,
        dsn_env=dsn_env,
        item_code=item_code,
        source_rule_code=source_rule_code,
        scope="active-targets",
        candidate_rule_codes=(),
        emperors=emperor_filters,
        source_pack_codes=(source_pack_code,),
        execute=False,
    )
    scorer: dict[str, Any] = {}
    scorer_all_ok = True
    for rule_code in I5B_REVIEW_RULES:
        payload = apply_rule_scores(
            dsn=dsn,
            item_code=item_code,
            rule_code=rule_code,
            formula_code=formula_code,
            source_pack_codes=(source_pack_code,),
            execute=False,
        )
        scorer_all_ok = scorer_all_ok and bool(payload.get("ok"))
        scorer[rule_code] = {
            "ok": bool(payload.get("ok")),
            "executed": bool(payload.get("executed")),
            "totals": payload.get("totals") or {},
            "clusters": payload.get("clusters") or [],
        }
    source_pack_status = text(pack_rows[0].get("status")) if pack_rows else ""
    coverage_status = text(pack_rows[0].get("coverage_status")) if pack_rows else ""
    future_hint_resolved_count = integer(lane_probe.get("future_hint_resolved_count"))
    candidate_total = sum(integer(row.get("n")) for row in lane_probe.get("candidate_counts") or [])
    return {
        "generated_by": "scripts/dev/retrieval_v2_i5b_shadow_report.py",
        "command": "consumed-pack-review",
        "purpose": "已入库 I5B-wide/personnel-political-wide shadow source pack 的消费端审核包。",
        "pack_code": source_pack_code,
        "item_code": item_code,
        "source_rule_code": source_rule_code,
        "formula_code": formula_code,
        "source_pack": {
            "rows": pack_rows,
            "status": source_pack_status,
            "coverage_status": coverage_status,
        },
        "totals": {
            "candidate_count": candidate_total,
            "future_hint_resolved_count": future_hint_resolved_count,
            "promoter_candidate_rows": integer((promoter.get("totals") or {}).get("candidate_rows")),
            "promoter_promotions": integer((promoter.get("totals") or {}).get("promotions")),
            "promoter_skipped": integer((promoter.get("totals") or {}).get("skipped")),
            "scorer_ok_rules": sum(1 for row in scorer.values() if row.get("ok") is True),
        },
        "candidate_lane_probe": {
            "candidate_counts": lane_probe.get("candidate_counts") or [],
            "future_hint_resolved_count": future_hint_resolved_count,
            "required_facts_shapes": lane_probe.get("required_facts_shapes") or [],
            "sample_future_hints": lane_probe.get("sample_future_hints") or [],
        },
        "promoter_dry_run": {
            "totals": promoter.get("totals") or {},
            "promoted_by_rule": promoter.get("promoted_by_rule") or {},
            "skipped_by_reason": promoter.get("skipped_by_reason") or {},
            "promotions": promoter.get("promotions") or [],
            "skipped": promoter.get("skipped") or [],
        },
        "scorer_dry_run": scorer,
        "safety_checks": {
            "source_pack_is_draft": source_pack_status == "draft",
            "coverage_status_passed": coverage_status == "passed",
            "future_hints_not_resolved": future_hint_resolved_count == 0,
            "promoter_was_dry_run": promoter.get("executed") is False,
            "all_scorers_ok": scorer_all_ok,
            "all_scorers_dry_run": all(row.get("executed") is False for row in scorer.values()),
        },
    }


def render_consumed_markdown(report: Mapping[str, Any]) -> str:
    safety = report.get("safety_checks") or {}
    promoter = report.get("promoter_dry_run") or {}
    lines = [
        "# retrieval_v2 consumed shadow review",
        "",
        f"- pack_code: `{report.get('pack_code', '')}`",
        f"- source_pack_status: `{(report.get('source_pack') or {}).get('status', '')}`",
        f"- coverage_status: `{(report.get('source_pack') or {}).get('coverage_status', '')}`",
        f"- future_hint_resolved_count: `{(report.get('candidate_lane_probe') or {}).get('future_hint_resolved_count', 0)}`",
        f"- promoter_totals: `{stable_json(promoter.get('totals') or {}).strip()}`",
        f"- safety_checks: `{stable_json(safety).strip()}`",
        "",
        "## Candidate Counts",
        "",
    ]
    count_rows = [
        [
            row.get("hint_status"),
            row.get("candidate_item_code"),
            row.get("candidate_lane"),
            row.get("candidate_rule_code"),
            row.get("has_candidate_contract_rule"),
            row.get("n"),
        ]
        for row in (report.get("candidate_lane_probe") or {}).get("candidate_counts", [])
    ]
    lines.append(markdown_table(["hint_status", "item", "lane", "rule", "has_contract", "n"], count_rows))
    lines.extend(["", "## Scorer Dry Run", ""])
    scorer_rows = []
    for rule_code, payload in sorted((report.get("scorer_dry_run") or {}).items()):
        clusters = payload.get("clusters") or []
        cluster = clusters[0] if clusters else {}
        scorer_rows.append(
            [
                rule_code,
                payload.get("ok"),
                payload.get("executed"),
                cluster.get("positive_signal"),
                cluster.get("negative_signal"),
                (payload.get("totals") or {}).get("judgments"),
            ]
        )
    lines.append(markdown_table(["rule", "ok", "executed", "positive", "negative", "judgments"], scorer_rows))
    return "\n".join(lines) + "\n"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize an I5B-wide retrieval_v2 shadow pilot run.")
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--source-pack-code", default="", help="Build a DB-backed consumed shadow review for this source pack.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default="EMPEROR_EVAL_RETRIEVAL_V2_DSN")
    parser.add_argument("--item-code", default="I5B")
    parser.add_argument("--source-rule-code", default="i5b_item_wide")
    parser.add_argument("--formula-code", default=DEFAULT_FORMULA_CODE)
    parser.add_argument("--emperor", action="append", default=[])
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    args = parser.parse_args(argv)
    if not args.run_root and not text(args.source_pack_code):
        parser.error("one of --run-root or --source-pack-code is required")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if text(args.source_pack_code):
        report = build_consumed_pack_review(
            env_file=args.env_file,
            dsn_env=args.dsn_env,
            source_pack_code=text(args.source_pack_code),
            item_code=args.item_code,
            source_rule_code=args.source_rule_code,
            formula_code=args.formula_code,
            emperors=tuple(args.emperor or ()),
        )
        default_root = ROOT / "tmp" / "retrieval_v2_consumption" / text(args.source_pack_code)
        output_json = args.output_json or default_root / "i5b_consumed_shadow_review.json"
        output_md = args.output_md or default_root / "i5b_consumed_shadow_review.md"
        markdown = render_consumed_markdown(report)
    else:
        report = build_report(args.run_root)
        output_json = args.output_json or args.run_root / "i5b_shadow_report.json"
        output_md = args.output_md or args.run_root / "i5b_shadow_report.md"
        markdown = render_markdown(report)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(stable_json(report), encoding="utf-8")
    output_md.write_text(markdown, encoding="utf-8")
    print(stable_json({"ok": True, "output_json": str(output_json), "output_md": str(output_md), "totals": report["totals"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
