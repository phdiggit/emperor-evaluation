from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

JSONL_FILES = [
    DATA_DIR / "evidence_cards.jsonl",
    DATA_DIR / "sources.jsonl",
    DATA_DIR / "events.jsonl",
    DATA_DIR / "trigger_terms.jsonl",
    DATA_DIR / "search_logs.jsonl",
    DATA_DIR / "evidence_clusters.jsonl",
    DATA_DIR / "thematic_anchors.jsonl",
    DATA_DIR / "query_profiles.jsonl",
]

VALID_POLARITIES = {"positive", "negative"}
VALID_TIERS = {"core", "extended"}
VALID_SEARCH_RESULT_STATUSES = {
    "checked_no_hard_evidence",
    "evidence_found_card_created",
    "lead_needs_source_review",
    "routed_to_adjacent_item",
}
VALID_CASE_CLASSIFICATIONS = {
    "confirmed_rebellion_or_security_case",
    "suspected_rebellion_unproven",
    "remonstrance_suppression",
    "ideological_suppression",
    "corporal_humiliation",
    "political_case_expansion",
    "posthumous_trust_reversal",
    "judicial_or_punishment_dispute",
    "other",
}
VALID_RISK_STATUSES = {
    "confirmed_rebellion",
    "strong_suspicion",
    "weak_suspicion",
    "unproven_or_disputed",
    "no_rebellion_context",
    "mixed_confirmed_case_with_expansion",
    "not_applicable",
}
VALID_ADJUDICATION_STATUSES = {
    "source_verified_pending_human_adjudication",
    "source_verified_auto_classified_cluster_review_pending",
    "needs_more_source_review",
    "routed_to_adjacent_item_only",
    "human_adjudicated_candidate",
}
VALID_CONTEXT_STATUSES = {"missing", "pending", "supplied", "source_verified"}
VALID_CONTEXT_EFFECTS = {"strengthen", "limit", "reverse", "split_only", "neutral"}
CONTEXT_STABLE_STATUSES = {"supplied", "source_verified"}
REQUIRED_STABLE_CONTEXT_FIELDS = [
    "quote_context",
    "context_summary",
    "context_scope",
    "context_effect",
    "adjudication_bridge",
]
HIGH_RISK_TRIGGER_FAMILIES = {"疑忌杀害", "功臣旧臣处置", "谏臣身后信用反转", "廷杖刑辱", "意识形态压制", "容谏纳言"}
HIGH_RISK_TERMS = {
    "谋反",
    "下狱",
    "诛",
    "杀",
    "赐死",
    "族",
    "图谶",
    "谶",
    "鞭",
    "杖",
    "捶扑",
    "停婚",
    "阿党",
}
HUMAN_LEVEL_BY_POLARITY_AND_STRENGTH = {
    ("positive", 1): "弱正",
    ("positive", 2): "中正",
    ("positive", 3): "强正",
    ("positive", 4): "极正",
    ("negative", 1): "弱负",
    ("negative", 2): "中负",
    ("negative", 3): "强负",
    ("negative", 4): "极负",
}

REQUIRED_EVIDENCE_FIELDS = [
    "evidence_id",
    "person",
    "item",
    "subitem",
    "polarity",
    "strength",
    "human_level",
    "source_id",
    "quote_short",
    "interpretation",
    "trigger_family",
    "trigger_terms",
    "cross_item_split",
    "scoring_effect",
    "verification_status",
]
REQUIRED_HIGH_RISK_NEGATIVE_FIELDS = [
    "case_classification",
    "risk_status",
    "mitigating_factors",
    "aggravating_factors",
    "reversal_or_rehabilitation",
    "adjudication_status",
]
REQUIRED_TRIGGER_TERM_FIELDS = [
    "term_id",
    "item",
    "subitem",
    "polarity",
    "trigger_family",
    "term",
    "tier",
    "note",
]
REQUIRED_SEARCH_LOG_FIELDS = [
    "search_id",
    "person",
    "item",
    "subitem",
    "polarity",
    "trigger_family",
    "query_terms",
    "query",
    "source_scope",
    "searched_at",
    "result_status",
    "result_summary",
    "linked_evidence_id",
    "note",
]
REQUIRED_EVIDENCE_CLUSTER_FIELDS = [
    "cluster_id",
    "person",
    "item",
    "subitem",
    "cluster_type",
    "polarity",
    "linked_evidence_ids",
    "summary",
    "five_axis_assessment",
    "candidate_strength",
    "upper_probe",
    "cross_item_split",
    "adjudication_status",
    "note",
]
REQUIRED_THEMATIC_ANCHOR_FIELDS = [
    "anchor_id",
    "theme",
    "item",
    "subitem",
    "persons",
    "linked_evidence_ids",
    "linked_cluster_ids",
    "anchor_summary",
    "comparative_value",
    "note",
]
REQUIRED_QUERY_PROFILE_FIELDS = [
    "query_profile_id",
    "item",
    "subitem",
    "search_modes",
    "positive_terms",
    "negative_terms",
    "reversal_terms",
    "source_scopes",
    "reverse_search_required_when",
    "thematic_anchor_targets",
    "cross_item_split_notes",
    "note",
]


def read_jsonl(path: Path, errors: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        errors.append(f"{path}: file does not exist")
        return rows

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError as exc:
                errors.append(f"{path}: line {line_number}: invalid JSON: {exc.msg}")
                continue
            if not isinstance(value, dict):
                errors.append(f"{path}: line {line_number}: JSONL row must be an object")
                continue
            rows.append(value)
    return rows


def is_filled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def validate_required_fields(
    row: dict[str, Any],
    required_fields: list[str],
    line_label: str,
    errors: list[str],
) -> None:
    for field in required_fields:
        if field not in row:
            errors.append(f"{line_label}: missing required field: {field}")


def text_for_high_risk_scan(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(text_for_high_risk_scan(item) for item in value)
    if isinstance(value, dict):
        return " ".join(text_for_high_risk_scan(item) for item in value.values())
    if value is None:
        return ""
    return str(value)


def is_high_risk_negative(row: dict[str, Any]) -> bool:
    if row.get("polarity") != "negative":
        return False
    if row.get("trigger_family") in HIGH_RISK_TRIGGER_FAMILIES:
        return True

    scanned_text = " ".join(
        text_for_high_risk_scan(row.get(field))
        for field in ["trigger_terms", "quote_short", "interpretation"]
    )
    return any(term in scanned_text for term in HIGH_RISK_TERMS)


def validate_list_field(row: dict[str, Any], field: str, line_label: str, errors: list[str]) -> None:
    if field in row and not isinstance(row.get(field), list):
        errors.append(f"{line_label}: {field} must be a list")


def validate_high_risk_negative(
    row: dict[str, Any],
    line_label: str,
    errors: list[str],
) -> None:
    if not is_high_risk_negative(row):
        return

    for field in REQUIRED_HIGH_RISK_NEGATIVE_FIELDS:
        if field not in row:
            errors.append(f"{line_label}: high-risk negative evidence missing required field: {field}")
        elif field != "mitigating_factors" and not is_filled(row.get(field)):
            errors.append(f"{line_label}: high-risk negative evidence requires non-empty field: {field}")

    case_classification = row.get("case_classification")
    if is_filled(case_classification) and case_classification not in VALID_CASE_CLASSIFICATIONS:
        errors.append(f"{line_label}: case_classification is not an allowed value: {case_classification}")

    risk_status = row.get("risk_status")
    if is_filled(risk_status) and risk_status not in VALID_RISK_STATUSES:
        errors.append(f"{line_label}: risk_status is not an allowed value: {risk_status}")

    adjudication_status = row.get("adjudication_status")
    if is_filled(adjudication_status) and adjudication_status not in VALID_ADJUDICATION_STATUSES:
        errors.append(f"{line_label}: adjudication_status is not an allowed value: {adjudication_status}")

    for field in ["mitigating_factors", "aggravating_factors", "reversal_or_rehabilitation"]:
        validate_list_field(row, field, line_label, errors)

    strength = row.get("strength")
    mitigating_factors = row.get("mitigating_factors")
    aggravating_factors = row.get("aggravating_factors")
    scoring_effect = row.get("scoring_effect")

    if risk_status == "confirmed_rebellion" and case_classification != "political_case_expansion":
        if strength in {2, 3, 4} and adjudication_status != "human_adjudicated_candidate":
            errors.append(
                f"{line_label}: confirmed_rebellion outside political_case_expansion "
                "requires strength<=1 unless human adjudicated"
            )

    if case_classification == "posthumous_trust_reversal" and strength in {3, 4}:
        errors.append(f"{line_label}: posthumous_trust_reversal requires strength<=2")

    if is_filled(mitigating_factors) and strength in {3, 4} and not is_filled(aggravating_factors):
        errors.append(f"{line_label}: strength>=3 with mitigating_factors requires aggravating_factors")

    if strength in {3, 4}:
        has_pending_text = isinstance(scoring_effect, str) and "待人工裁判" in scoring_effect
        has_pending_status = adjudication_status == "source_verified_pending_human_adjudication"
        if not (has_pending_text or has_pending_status):
            errors.append(f"{line_label}: strength>=3 evidence requires pending human adjudication")


def is_context_required(row: dict[str, Any]) -> bool:
    return row.get("context_required") is True


def validate_i5b_context_fields(row: dict[str, Any], line_label: str, errors: list[str]) -> None:
    if row.get("subitem") != "第五项B":
        return

    if "context_status" in row and is_filled(row.get("context_status")):
        context_status = row.get("context_status")
        if context_status not in VALID_CONTEXT_STATUSES:
            errors.append(f"{line_label}: context_status is not an allowed value: {context_status}")

    if "context_effect" in row and is_filled(row.get("context_effect")):
        context_effect = row.get("context_effect")
        if context_effect not in VALID_CONTEXT_EFFECTS:
            errors.append(f"{line_label}: context_effect is not an allowed value: {context_effect}")

    if "context_required" in row and not isinstance(row.get("context_required"), bool):
        errors.append(f"{line_label}: context_required must be a boolean")
        return

    if not is_context_required(row):
        return

    if "context_status" not in row or not is_filled(row.get("context_status")):
        errors.append(f"{line_label}: context_required=true requires context_status")
        return

    if row.get("context_status") in CONTEXT_STABLE_STATUSES:
        for field in REQUIRED_STABLE_CONTEXT_FIELDS:
            if not is_filled(row.get(field)):
                errors.append(
                    f"{line_label}: context_required=true and context_status={row.get('context_status')} "
                    f"requires non-empty field: {field}"
                )


def validate_evidence_card(row: dict[str, Any], line_label: str, source_ids: set[str], errors: list[str]) -> None:
    validate_required_fields(row, REQUIRED_EVIDENCE_FIELDS, line_label, errors)

    polarity = row.get("polarity")
    if polarity not in VALID_POLARITIES:
        errors.append(f"{line_label}: polarity must be positive or negative")

    strength = row.get("strength")
    if strength not in {1, 2, 3, 4}:
        errors.append(f"{line_label}: strength must be one of 1, 2, 3, 4")

    human_level = row.get("human_level")
    expected_human_level = HUMAN_LEVEL_BY_POLARITY_AND_STRENGTH.get((polarity, strength))
    if expected_human_level is not None and human_level != expected_human_level:
        errors.append(
            f"{line_label}: polarity={polarity} and strength={strength} "
            f"requires human_level={expected_human_level}"
        )

    if polarity == "negative" and human_level in {"强负", "极负"}:
        if not (is_filled(row.get("cross_item_split")) or is_filled(row.get("scoring_effect"))):
            errors.append(f"{line_label}: 强负 or 极负 evidence requires cross_item_split or scoring_effect")

    source_id = row.get("source_id")
    if source_id and source_id not in source_ids:
        errors.append(f"{line_label}: source_id not found in sources.jsonl: {source_id}")

    validate_high_risk_negative(row, line_label, errors)
    validate_i5b_context_fields(row, line_label, errors)


def validate_trigger_term(
    row: dict[str, Any],
    line_label: str,
    seen_term_ids: set[str],
    errors: list[str],
) -> None:
    validate_required_fields(row, REQUIRED_TRIGGER_TERM_FIELDS, line_label, errors)

    polarity = row.get("polarity")
    if polarity not in VALID_POLARITIES:
        errors.append(f"{line_label}: polarity must be positive or negative")

    tier = row.get("tier")
    if tier not in VALID_TIERS:
        errors.append(f"{line_label}: tier must be core or extended")

    term_id = row.get("term_id")
    if is_filled(term_id):
        if term_id in seen_term_ids:
            errors.append(f"{line_label}: duplicate term_id: {term_id}")
        seen_term_ids.add(term_id)


def validate_search_log(row: dict[str, Any], line_label: str, errors: list[str]) -> None:
    validate_required_fields(row, REQUIRED_SEARCH_LOG_FIELDS, line_label, errors)

    polarity = row.get("polarity")
    if is_filled(polarity) and polarity not in VALID_POLARITIES:
        errors.append(f"{line_label}: polarity must be positive or negative")

    result_status = row.get("result_status")
    if is_filled(result_status) and result_status not in VALID_SEARCH_RESULT_STATUSES:
        errors.append(f"{line_label}: result_status must be an allowed value: {result_status}")


def validate_evidence_cluster(
    row: dict[str, Any],
    line_label: str,
    source_evidence_ids: set[str],
    seen_cluster_ids: set[str],
    errors: list[str],
) -> None:
    validate_required_fields(row, REQUIRED_EVIDENCE_CLUSTER_FIELDS, line_label, errors)

    cluster_id = row.get("cluster_id")
    if is_filled(cluster_id):
        if cluster_id in seen_cluster_ids:
            errors.append(f"{line_label}: duplicate cluster_id: {cluster_id}")
        seen_cluster_ids.add(cluster_id)

    polarity = row.get("polarity")
    if is_filled(polarity) and polarity not in VALID_POLARITIES:
        errors.append(f"{line_label}: polarity must be positive or negative")

    linked_evidence_ids = row.get("linked_evidence_ids")
    if not isinstance(linked_evidence_ids, list):
        errors.append(f"{line_label}: linked_evidence_ids must be a list")
    candidate_strength = row.get("candidate_strength")
    if candidate_strength not in {1, 2, 3, 4}:
        errors.append(f"{line_label}: candidate_strength must be one of 1, 2, 3, 4")
    elif isinstance(linked_evidence_ids, list):
        if len(linked_evidence_ids) == 0:
            errors.append(f"{line_label}: linked_evidence_ids must reference at least one evidence card")
        elif len(linked_evidence_ids) == 1 and candidate_strength < 3:
            errors.append(
                f"{line_label}: a single linked evidence card requires candidate_strength>=3"
            )

    if isinstance(linked_evidence_ids, list):
        for evidence_id in linked_evidence_ids:
            if evidence_id not in source_evidence_ids:
                errors.append(f"{line_label}: linked_evidence_ids references unknown evidence_id: {evidence_id}")

    if "five_axis_assessment" in row and not isinstance(row.get("five_axis_assessment"), dict):
        errors.append(f"{line_label}: five_axis_assessment must be an object")

    if candidate_strength == 4 and row.get("adjudication_status") != "source_verified_pending_human_adjudication":
        errors.append(f"{line_label}: candidate_strength=4 requires pending human adjudication")


def validate_thematic_anchor(
    row: dict[str, Any],
    line_label: str,
    source_evidence_ids: set[str],
    source_cluster_ids: set[str],
    seen_anchor_ids: set[str],
    errors: list[str],
) -> None:
    validate_required_fields(row, REQUIRED_THEMATIC_ANCHOR_FIELDS, line_label, errors)

    anchor_id = row.get("anchor_id")
    if is_filled(anchor_id):
        if anchor_id in seen_anchor_ids:
            errors.append(f"{line_label}: duplicate anchor_id: {anchor_id}")
        seen_anchor_ids.add(anchor_id)

    for field in ["persons", "linked_evidence_ids", "linked_cluster_ids"]:
        validate_list_field(row, field, line_label, errors)

    linked_evidence_ids = row.get("linked_evidence_ids")
    if isinstance(linked_evidence_ids, list):
        for evidence_id in linked_evidence_ids:
            if evidence_id not in source_evidence_ids:
                errors.append(f"{line_label}: linked_evidence_ids references unknown evidence_id: {evidence_id}")

    linked_cluster_ids = row.get("linked_cluster_ids")
    if isinstance(linked_cluster_ids, list):
        for cluster_id in linked_cluster_ids:
            if cluster_id not in source_cluster_ids:
                errors.append(f"{line_label}: linked_cluster_ids references unknown cluster_id: {cluster_id}")


def validate_query_profile(
    row: dict[str, Any],
    line_label: str,
    seen_query_profile_ids: set[str],
    errors: list[str],
) -> None:
    validate_required_fields(row, REQUIRED_QUERY_PROFILE_FIELDS, line_label, errors)

    query_profile_id = row.get("query_profile_id")
    if is_filled(query_profile_id):
        if query_profile_id in seen_query_profile_ids:
            errors.append(f"{line_label}: duplicate query_profile_id: {query_profile_id}")
        seen_query_profile_ids.add(query_profile_id)

    for field in [
        "search_modes",
        "positive_terms",
        "negative_terms",
        "reversal_terms",
        "source_scopes",
        "reverse_search_required_when",
        "thematic_anchor_targets",
        "cross_item_split_notes",
    ]:
        validate_list_field(row, field, line_label, errors)


def nonblank_line_numbers(path: Path) -> list[int]:
    with path.open("r", encoding="utf-8") as handle:
        return [number for number, line in enumerate(handle, start=1) if line.strip()]


def validate() -> list[str]:
    errors: list[str] = []
    parsed = {path: read_jsonl(path, errors) for path in JSONL_FILES}

    sources = parsed[DATA_DIR / "sources.jsonl"]
    source_ids = {row.get("source_id") for row in sources if is_filled(row.get("source_id"))}

    evidence_path = DATA_DIR / "evidence_cards.jsonl"
    evidence_line_numbers = nonblank_line_numbers(evidence_path)

    for row, line_number in zip(parsed[evidence_path], evidence_line_numbers):
        validate_evidence_card(row, f"{evidence_path}: line {line_number}", source_ids, errors)

    trigger_terms_path = DATA_DIR / "trigger_terms.jsonl"
    trigger_term_line_numbers = nonblank_line_numbers(trigger_terms_path)
    seen_term_ids: set[str] = set()
    for row, line_number in zip(parsed[trigger_terms_path], trigger_term_line_numbers):
        validate_trigger_term(row, f"{trigger_terms_path}: line {line_number}", seen_term_ids, errors)

    search_logs_path = DATA_DIR / "search_logs.jsonl"
    search_log_line_numbers = nonblank_line_numbers(search_logs_path)
    for row, line_number in zip(parsed[search_logs_path], search_log_line_numbers):
        validate_search_log(row, f"{search_logs_path}: line {line_number}", errors)

    evidence_ids = {
        row.get("evidence_id")
        for row in parsed[evidence_path]
        if is_filled(row.get("evidence_id"))
    }

    evidence_clusters_path = DATA_DIR / "evidence_clusters.jsonl"
    evidence_cluster_line_numbers = nonblank_line_numbers(evidence_clusters_path)
    seen_cluster_ids: set[str] = set()
    for row, line_number in zip(parsed[evidence_clusters_path], evidence_cluster_line_numbers):
        validate_evidence_cluster(
            row,
            f"{evidence_clusters_path}: line {line_number}",
            evidence_ids,
            seen_cluster_ids,
            errors,
        )

    thematic_anchors_path = DATA_DIR / "thematic_anchors.jsonl"
    thematic_anchor_line_numbers = nonblank_line_numbers(thematic_anchors_path)
    seen_anchor_ids: set[str] = set()
    for row, line_number in zip(parsed[thematic_anchors_path], thematic_anchor_line_numbers):
        validate_thematic_anchor(
            row,
            f"{thematic_anchors_path}: line {line_number}",
            evidence_ids,
            seen_cluster_ids,
            seen_anchor_ids,
            errors,
        )

    query_profiles_path = DATA_DIR / "query_profiles.jsonl"
    query_profile_line_numbers = nonblank_line_numbers(query_profiles_path)
    seen_query_profile_ids: set[str] = set()
    for row, line_number in zip(parsed[query_profiles_path], query_profile_line_numbers):
        validate_query_profile(
            row,
            f"{query_profiles_path}: line {line_number}",
            seen_query_profile_ids,
            errors,
        )

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
