from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from emperor_v4.contracts.source import (
    PASSAGE_KINDS,
    PASSAGE_LINK_RELATIONS,
    SOURCE_CACHE_CONTRACT_V2,
    text_content_hash,
)
from emperor_v4.evaluation.boundary_score import score_boundary_graph


_NAVIGATION_MARKERS = (
    "姊妹计划",
    "数据项",
    "◄",
    "►",
    "[ 编辑 ]",
)
_V2_PASSAGE_FIELDS = frozenset(
    {
        "content_version",
        "section_id",
        "section_heading",
        "span_start",
        "span_end",
        "passage_kind",
        "linked_passages",
        "window_policy_version",
        "locator",
        "raw_text",
        "context_before",
        "context_after",
        "content_hash",
        "selection_reason",
    }
)


@dataclass(frozen=True, slots=True)
class QualificationThresholds:
    atomic_support_rate_minimum: float = 0.75
    context_only_rate_maximum: float = 0.25
    navigation_noise_count_maximum: int = 0
    linked_passage_lineage_minimum: float = 1.0
    source_contract_v2_coverage_minimum: float = 1.0
    gold_episode_minimum: int = 15
    gold_relation_minimum: int = 4
    gold_rule_evidence_unit_minimum: int = 4
    episode_recall_minimum: float = 0.85
    episode_precision_minimum: float = 0.90
    passage_lineage_minimum: float = 1.0
    assertion_disposition_coverage_minimum: float = 1.0
    catastrophic_wrong_merge_count_maximum: int = 0
    cross_ruler_contamination_count_maximum: int = 0
    unresolved_assertion_rate_maximum: float = 0.0
    strict_relation_precision_minimum: float = 0.90
    strict_relation_recall_minimum: float = 0.85


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _looks_like_navigation_noise(row: Mapping[str, Any]) -> bool:
    if row.get("passage_kind") == "navigation_noise":
        return True
    text = str(row.get("raw_text") or row.get("text") or "")
    marker_hits = sum(marker in text for marker in _NAVIGATION_MARKERS)
    return marker_hits >= 2 or "姊妹计划 : 数据项" in text


def _document_ref(row: Mapping[str, Any]) -> object:
    return row.get("document_code") or row.get("document_id")


def _is_v2_passage(row: Mapping[str, Any]) -> bool:
    contract = row.get("contract_version") or row.get("source_contract")
    if contract != SOURCE_CACHE_CONTRACT_V2:
        return False
    if not _V2_PASSAGE_FIELDS <= set(row):
        return False
    required_values = {
        "content_version",
        "section_id",
        "section_heading",
        "locator",
        "raw_text",
        "content_hash",
        "selection_reason",
        "passage_kind",
        "window_policy_version",
    }
    if any(row.get(field) in (None, "", [], ()) for field in required_values):
        return False
    raw_text = str(row["raw_text"])
    span_start = row.get("span_start")
    span_end = row.get("span_end")
    return all(
        (
            row.get("passage_kind") in PASSAGE_KINDS,
            isinstance(row.get("linked_passages"), (list, tuple)),
            isinstance(span_start, int),
            isinstance(span_end, int),
            isinstance(span_start, int) and span_start >= 0,
            isinstance(span_start, int)
            and isinstance(span_end, int)
            and span_end > span_start,
            isinstance(span_start, int)
            and isinstance(span_end, int)
            and span_end - span_start == len(raw_text),
            row.get("content_hash") == text_content_hash(raw_text),
        )
    )


def evaluate_source_assertion_qualification(
    payload: Mapping[str, Any],
    *,
    thresholds: QualificationThresholds = QualificationThresholds(),
) -> dict[str, Any]:
    passage_rows = tuple(payload.get("source_passages") or ())
    assertion_rows = tuple(payload.get("assertions") or ())
    passage_by_ref = {
        str(row.get("passage_code") or row.get("passage_id") or ""): row
        for row in passage_rows
    }
    if not passage_rows or "" in passage_by_ref or len(passage_by_ref) != len(passage_rows):
        raise ValueError("source qualification passages 必须非空且 code 唯一")
    assertion_by_passage: dict[str, list[Mapping[str, Any]]] = {}
    missing_lineage = []
    for assertion in assertion_rows:
        ref = str(assertion.get("source_passage_ref") or "")
        if ref not in passage_by_ref:
            missing_lineage.append(ref)
        assertion_by_passage.setdefault(ref, []).append(assertion)
    if missing_lineage:
        raise ValueError(f"source qualification assertion lineage 缺失: {sorted(set(missing_lineage))}")

    v2_refs = {ref for ref, row in passage_by_ref.items() if _is_v2_passage(row)}
    noise_refs = {
        ref for ref, row in passage_by_ref.items() if _looks_like_navigation_noise(row)
    }
    link_count = 0
    valid_link_count = 0
    for ref, row in passage_by_ref.items():
        for link in row.get("linked_passages") or ():
            link_count += 1
            target = str(link.get("passage_ref") or "")
            target_row = passage_by_ref.get(target)
            if (
                target_row is not None
                and target != ref
                and link.get("relation") in PASSAGE_LINK_RELATIONS
                and _document_ref(target_row) == _document_ref(row)
                and target_row.get("content_version") == row.get("content_version")
            ):
                valid_link_count += 1

    core_support_refs = set()
    context_only_refs = set()
    unsupported_core_refs = set()
    unclassified_refs = set(passage_by_ref)
    support_mode_counts: dict[str, int] = {}
    for ref, rows in assertion_by_passage.items():
        for assertion in rows:
            support = assertion.get("passage_support") or {}
            mode = str(support.get("support_mode") or "unclassified")
            support_mode_counts[mode] = support_mode_counts.get(mode, 0) + 1
            if mode == "context_only":
                context_only_refs.add(ref)
                unclassified_refs.discard(ref)
            elif mode in {"atomic_component", "single_passage", "equivalent_evidence"}:
                core_support_refs.add(ref)
                unclassified_refs.discard(ref)
                fields = set(support.get("supported_fields") or ())
                if not {"identity", "action"} <= fields:
                    unsupported_core_refs.add(ref)

    source_v2_coverage = _ratio(len(v2_refs), len(passage_by_ref)) or 0.0
    conflicting_support_refs = core_support_refs & context_only_refs
    linked_lineage = _ratio(valid_link_count, link_count)
    if linked_lineage is None:
        linked_lineage = 1.0
    atomic_rate = _ratio(len(core_support_refs), len(passage_by_ref)) or 0.0
    context_rate = _ratio(len(context_only_refs), len(passage_by_ref)) or 0.0
    s1_failures = []
    if source_v2_coverage < thresholds.source_contract_v2_coverage_minimum:
        s1_failures.append("source_contract_v2_coverage_below_minimum")
    if len(noise_refs) > thresholds.navigation_noise_count_maximum:
        s1_failures.append("navigation_noise_above_maximum")
    if linked_lineage < thresholds.linked_passage_lineage_minimum:
        s1_failures.append("linked_passage_lineage_below_minimum")
    s2_failures = []
    if atomic_rate < thresholds.atomic_support_rate_minimum:
        s2_failures.append("atomic_support_rate_below_minimum")
    if context_rate > thresholds.context_only_rate_maximum:
        s2_failures.append("context_only_rate_above_maximum")
    if unsupported_core_refs:
        s2_failures.append("core_without_identity_action_support")
    if conflicting_support_refs:
        s2_failures.append("passage_has_conflicting_support_modes")
    if unclassified_refs:
        s2_failures.append("passages_without_assertion_support_classification")

    can_start_boundary = not s1_failures and not s2_failures
    return {
        "schema_version": 1,
        "status": "qualified_for_boundary" if can_start_boundary else "stopped_before_boundary",
        "dataset_code": payload.get("dataset_code"),
        "thresholds": asdict(thresholds),
        "stages": {
            "S1_source_passage": {
                "passed": not s1_failures,
                "failures": s1_failures,
                "source_passage_count": len(passage_by_ref),
                "source_contract_v2_count": len(v2_refs),
                "source_contract_v2_coverage": source_v2_coverage,
                "source_contract_v2_invalid_count": len(passage_by_ref) - len(v2_refs),
                "navigation_noise_count": len(noise_refs),
                "navigation_noise_refs": sorted(noise_refs),
                "linked_passage_count": link_count,
                "linked_passage_lineage": linked_lineage,
            },
            "S2_assertion": {
                "passed": not s2_failures,
                "failures": s2_failures,
                "atomic_support_count": len(core_support_refs),
                "atomic_support_rate": atomic_rate,
                "context_only_count": len(context_only_refs),
                "context_only_rate": context_rate,
                "unclassified_passage_count": len(unclassified_refs),
                "unsupported_core_count": len(unsupported_core_refs),
                "conflicting_support_mode_count": len(conflicting_support_refs),
                "support_mode_counts": dict(sorted(support_mode_counts.items())),
            },
        },
        "decision": {
            "can_start_boundary": can_start_boundary,
            "stop_code": None if can_start_boundary else "STOP_BEFORE_BOUNDARY",
            "downstream_reviewers_started": False,
        },
    }


def evaluate_source_development_sets(
    payloads: Mapping[str, Mapping[str, Any]],
    *,
    thresholds: QualificationThresholds = QualificationThresholds(),
) -> dict[str, Any]:
    """把既有开放数据集当作开发回归集，不制造新的盲测结论。"""

    if not payloads:
        raise ValueError("source development qualification 至少需要一个数据集")
    reports = {
        code: evaluate_source_assertion_qualification(payload, thresholds=thresholds)
        for code, payload in sorted(payloads.items())
    }
    qualified = [
        code
        for code, report in reports.items()
        if report["decision"]["can_start_boundary"]
    ]
    blocked = sorted(set(reports) - set(qualified))
    all_qualified = not blocked
    return {
        "schema_version": 1,
        "status": (
            "development_sets_qualified_for_boundary"
            if all_qualified
            else "development_blocked_before_boundary"
        ),
        "evaluation_mode": "open_development_regression",
        "reports": reports,
        "summary": {
            "dataset_count": len(reports),
            "qualified_dataset_codes": qualified,
            "blocked_dataset_codes": blocked,
        },
        "decision": {
            "can_start_boundary": all_qualified,
            "stop_code": None if all_qualified else "STOP_BEFORE_BOUNDARY",
            "new_blind_holdout_authorized": False,
            "downstream_reviewers_started": False,
        },
    }


def evaluate_historical_coverage(
    historical_gold: Mapping[str, Any],
    *,
    thresholds: QualificationThresholds = QualificationThresholds(),
) -> dict[str, Any]:
    episode_count = len(historical_gold.get("gold_episodes") or ())
    relation_count = len(historical_gold.get("gold_relations") or ())
    failures = []
    if episode_count < thresholds.gold_episode_minimum:
        failures.append("gold_episode_count_below_minimum")
    if relation_count < thresholds.gold_relation_minimum:
        failures.append("gold_relation_count_below_minimum")
    return {
        "stage": "S4_relation_coverage",
        "passed": not failures,
        "failures": failures,
        "gold_episode_count": episode_count,
        "gold_relation_count": relation_count,
        "decision": {
            "can_start_rule_gold": not failures,
            "stop_code": None if not failures else "COVERAGE_INELIGIBLE_FOR_RELATION",
        },
    }


def evaluate_rule_coverage(
    rule_gold: Mapping[str, Any],
    *,
    thresholds: QualificationThresholds = QualificationThresholds(),
) -> dict[str, Any]:
    unit_count = len(rule_gold.get("gold_rule_evidence_units") or ())
    passed = unit_count >= thresholds.gold_rule_evidence_unit_minimum
    return {
        "stage": "S5_rule_evidence_unit_coverage",
        "passed": passed,
        "gold_rule_evidence_unit_count": unit_count,
        "decision": {
            "can_start_release_score": passed,
            "stop_code": None if passed else "COVERAGE_INELIGIBLE_FOR_RULE",
        },
    }


def evaluate_candidate_recall_upper_bound(
    *,
    candidate_episode_count: int,
    gold_episode_count: int,
    thresholds: QualificationThresholds = QualificationThresholds(),
) -> dict[str, Any]:
    upper_bound = _ratio(min(candidate_episode_count, gold_episode_count), gold_episode_count)
    passed = upper_bound is not None and upper_bound >= thresholds.episode_recall_minimum
    return {
        "stage": "S3_episode_boundary_upper_bound",
        "passed": passed,
        "candidate_episode_count": candidate_episode_count,
        "gold_episode_count": gold_episode_count,
        "maximum_possible_recall": upper_bound,
        "decision": {
            "can_start_rule_gold": passed,
            "stop_code": None if passed else "STOP_BEFORE_RULE_GOLD",
        },
    }


def evaluate_boundary_quality(
    boundary_score: Mapping[str, Any],
    *,
    thresholds: QualificationThresholds = QualificationThresholds(),
) -> dict[str, Any]:
    metrics = boundary_score.get("episode_metrics") or {}
    failures = []
    checks = (
        (
            "episode_recall_below_minimum",
            metrics.get("exact_episode_recall"),
            thresholds.episode_recall_minimum,
            "minimum",
        ),
        (
            "episode_precision_below_minimum",
            metrics.get("exact_candidate_precision"),
            thresholds.episode_precision_minimum,
            "minimum",
        ),
        (
            "passage_lineage_below_minimum",
            metrics.get("passage_lineage_completeness"),
            thresholds.passage_lineage_minimum,
            "minimum",
        ),
        (
            "assertion_disposition_coverage_below_minimum",
            metrics.get("primary_assertion_disposition_coverage"),
            thresholds.assertion_disposition_coverage_minimum,
            "minimum",
        ),
        (
            "catastrophic_wrong_merge_above_maximum",
            metrics.get("catastrophic_wrong_merge_count"),
            thresholds.catastrophic_wrong_merge_count_maximum,
            "maximum",
        ),
        (
            "cross_ruler_contamination_above_maximum",
            metrics.get("cross_ruler_contamination_count"),
            thresholds.cross_ruler_contamination_count_maximum,
            "maximum",
        ),
        (
            "unresolved_assertion_rate_above_maximum",
            metrics.get("unresolved_assertion_rate"),
            thresholds.unresolved_assertion_rate_maximum,
            "maximum",
        ),
    )
    for code, value, threshold, direction in checks:
        if value is None:
            failures.append(f"{code}_missing")
        elif direction == "minimum" and value < threshold:
            failures.append(code)
        elif direction == "maximum" and value > threshold:
            failures.append(code)
    passed = not failures
    return {
        "stage": "S3_episode_boundary_quality",
        "passed": passed,
        "failures": failures,
        "metrics": dict(metrics),
        "decision": {
            "can_start_rule_gold": passed,
            "stop_code": None if passed else "BOUNDARY_QUALITY_BELOW_MINIMUM",
        },
    }


def evaluate_relation_quality(
    boundary_score: Mapping[str, Any],
    *,
    thresholds: QualificationThresholds = QualificationThresholds(),
) -> dict[str, Any]:
    metrics = boundary_score.get("relation_metrics") or {}
    failures = []
    precision = metrics.get("strict_relation_precision")
    recall = metrics.get("strict_relation_recall")
    if precision is None:
        failures.append("strict_relation_precision_missing")
    elif precision < thresholds.strict_relation_precision_minimum:
        failures.append("strict_relation_precision_below_minimum")
    if recall is None:
        failures.append("strict_relation_recall_missing")
    elif recall < thresholds.strict_relation_recall_minimum:
        failures.append("strict_relation_recall_below_minimum")
    passed = not failures
    return {
        "stage": "S4_relation_graph_quality",
        "passed": passed,
        "failures": failures,
        "metrics": dict(metrics),
        "decision": {
            "can_start_rule_gold": passed,
            "stop_code": None if passed else "RELATION_QUALITY_BELOW_MINIMUM",
        },
    }


def evaluate_downstream_development_qualification(
    candidate_graph: Mapping[str, Any],
    historical_gold: Mapping[str, Any],
    rule_gold: Mapping[str, Any] | None = None,
    *,
    thresholds: QualificationThresholds = QualificationThresholds(),
    boundary_score: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    s3_upper_bound = evaluate_candidate_recall_upper_bound(
        candidate_episode_count=len(candidate_graph.get("episode_groups") or ()),
        gold_episode_count=len(historical_gold.get("gold_episodes") or ()),
        thresholds=thresholds,
    )
    measured_score = None
    s3_quality = None
    if s3_upper_bound["passed"]:
        measured_score = boundary_score or score_boundary_graph(
            candidate_graph, historical_gold
        )
        s3_quality = evaluate_boundary_quality(measured_score, thresholds=thresholds)
    s4_coverage = evaluate_historical_coverage(historical_gold, thresholds=thresholds)
    s4_quality = (
        evaluate_relation_quality(measured_score, thresholds=thresholds)
        if measured_score is not None
        and s3_quality is not None
        and s3_quality["passed"]
        and s4_coverage["passed"]
        else None
    )
    s5 = (
        evaluate_rule_coverage(rule_gold, thresholds=thresholds)
        if rule_gold is not None
        and s3_upper_bound["passed"]
        and s3_quality is not None
        and s3_quality["passed"]
        and s4_coverage["passed"]
        and s4_quality is not None
        and s4_quality["passed"]
        else None
    )
    if not s3_upper_bound["passed"]:
        status = "stopped_before_rule_gold"
        stop_code = s3_upper_bound["decision"]["stop_code"]
    elif s3_quality is not None and not s3_quality["passed"]:
        status = "boundary_quality_failed_before_rule_gold"
        stop_code = s3_quality["decision"]["stop_code"]
    elif not s4_coverage["passed"]:
        status = "coverage_ineligible_for_relation"
        stop_code = s4_coverage["decision"]["stop_code"]
    elif s4_quality is not None and not s4_quality["passed"]:
        status = "relation_quality_failed_before_rule_gold"
        stop_code = s4_quality["decision"]["stop_code"]
    elif s5 is None:
        status = "rule_gold_pending"
        stop_code = "RULE_GOLD_PENDING"
    elif not s5["passed"]:
        status = "coverage_ineligible_for_rule"
        stop_code = s5["decision"]["stop_code"]
    else:
        status = "development_downstream_qualified"
        stop_code = None
    return {
        "schema_version": 1,
        "status": status,
        "evaluation_mode": "open_development_regression",
        "dataset_code": candidate_graph.get("dataset_code"),
        "stages": {
            "S3_episode_boundary_upper_bound": s3_upper_bound,
            "S3_episode_boundary_quality": s3_quality,
            "S4_relation_coverage": s4_coverage,
            "S4_relation_graph_quality": s4_quality,
            "S5_rule_evidence_unit_coverage": s5,
        },
        "decision": {
            "development_downstream_qualified": stop_code is None,
            "stop_code": stop_code,
            "new_blind_holdout_authorized": False,
            "postgresql_g3_authorized": False,
        },
    }
