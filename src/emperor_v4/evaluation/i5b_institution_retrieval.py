from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


CONTRACT_SCHEMA_VERSION = "i5b-institution-retrieval-contract-v1"
REPORT_SCHEMA_VERSION = "i5b-institution-retrieval-regression-v1"
REQUIRED_AXES = (
    "person_event",
    "ruler_institution",
    "cross_person_cluster",
)
REQUIRED_PREDICATES = {
    "formal_channel_established",
    "channel_operation_observed",
    "expression_safety_observed",
}


def _stable_hash(payload: object) -> str:
    rendered = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(rendered.encode("utf-8")).hexdigest()


def _nonempty_strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _validate_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        raise ValueError("制度检索合同版本非法")
    if contract.get("status") != "offline_candidate_retrieval_regression":
        raise ValueError("制度检索合同必须保持离线候选回归状态")

    policy = contract.get("safety_boundary") or {}
    expected_boundary = {
        "output_disposition": "candidate_only",
        "fact_acceptance_allowed": False,
        "factor_choice_allowed": False,
        "score_contribution_allowed": False,
        "database_write_allowed": False,
        "network_access_allowed": False,
    }
    if any(policy.get(key) != value for key, value in expected_boundary.items()):
        raise ValueError("制度检索回归不得接受事实、选择因子、计分、联网或写库")

    query = contract.get("query") or {}
    supplied = set(_nonempty_strings(query.get("supplied_hint_types")))
    if supplied != {"ruler_name", "rule_code", "candidate_source_catalog"}:
        raise ValueError("制度检索回归只能接收皇帝、rule 与候选语料目录提示")
    forbidden = set(_nonempty_strings(query.get("forbidden_hint_types")))
    if not {"chapter_title", "passage_locator", "institution_answer"} <= forbidden:
        raise ValueError("制度检索回归必须显式禁止章节名、段落定位和制度答案提示")
    if not str(query.get("ruler_name") or "").strip() or not str(
        query.get("rule_code") or ""
    ).strip():
        raise ValueError("制度检索回归缺少皇帝或 rule")

    thresholds = contract.get("candidate_thresholds") or {}
    expected_thresholds = {
        "formal_channel_establishment_min": 1,
        "independent_operation_observation_min": 2,
        "operation_year_min": 2,
        "distinct_expression_actor_min": 2,
        "formal_subject_min": 1,
        "expression_safety_observation_min": 1,
        "required_axis_count": 3,
    }
    if any(thresholds.get(key) != value for key, value in expected_thresholds.items()):
        raise ValueError("制度候选门槛必须完整且不得放宽")

    axes = contract.get("retrieval_axes") or {}
    if tuple(axes) != REQUIRED_AXES:
        raise ValueError("制度检索必须按人物事件、皇帝制度、跨人物聚合三轴输入")
    seen_refs: set[str] = set()
    institution_keys: set[str] = set()
    for axis in REQUIRED_AXES:
        observations = axes.get(axis)
        if not isinstance(observations, list) or not observations:
            raise ValueError(f"制度检索轴缺少观察: {axis}")
        for observation in observations:
            observation_ref = str(observation.get("observation_ref") or "").strip()
            institution_key = str(observation.get("institution_key") or "").strip()
            predicates = set(_nonempty_strings(observation.get("predicates")))
            if (
                not observation_ref
                or observation_ref in seen_refs
                or not institution_key
                or not predicates
                or not predicates <= REQUIRED_PREDICATES
                or observation.get("axis") != axis
                or not str(observation.get("source_ref") or "").strip()
                or not str(observation.get("passage_ref") or "").strip()
                or not isinstance(observation.get("year"), int)
            ):
                raise ValueError(f"制度检索观察非法: {observation_ref or axis}")
            seen_refs.add(observation_ref)
            institution_keys.add(institution_key)
    if len(institution_keys) != 1:
        raise ValueError("冻结回归案例必须聚合为单一制度候选")


def _gate_result(
    *, observed: int, required: int, evidence_refs: set[str]
) -> dict[str, Any]:
    return {
        "observed": observed,
        "required": required,
        "passed": observed >= required,
        "evidence_refs": sorted(evidence_refs),
    }


def evaluate_i5b_institution_retrieval(
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate the frozen offline retrieval case without accepting any fact."""

    _validate_contract(contract)
    thresholds = contract["candidate_thresholds"]
    observations = [
        observation
        for axis in REQUIRED_AXES
        for observation in contract["retrieval_axes"][axis]
    ]
    institution_key = str(observations[0]["institution_key"])

    predicate_refs: dict[str, set[str]] = {
        predicate: set() for predicate in REQUIRED_PREDICATES
    }
    operation_years: set[int] = set()
    expression_actors: set[str] = set()
    formal_subjects: set[str] = set()
    axis_refs: dict[str, set[str]] = {axis: set() for axis in REQUIRED_AXES}
    source_refs: set[str] = set()
    passage_refs: set[str] = set()
    for observation in observations:
        ref = str(observation["observation_ref"])
        axis_refs[str(observation["axis"])].add(ref)
        source_refs.add(str(observation["source_ref"]))
        passage_refs.add(str(observation["passage_ref"]))
        predicates = set(observation["predicates"])
        for predicate in predicates:
            predicate_refs[predicate].add(ref)
        if "channel_operation_observed" in predicates:
            operation_years.add(int(observation["year"]))
        expression_actors.update(_nonempty_strings(observation.get("expression_actors")))
        formal_subjects.update(_nonempty_strings(observation.get("formal_subjects")))

    gates = {
        "formal_channel_establishment": _gate_result(
            observed=len(predicate_refs["formal_channel_established"]),
            required=int(thresholds["formal_channel_establishment_min"]),
            evidence_refs=predicate_refs["formal_channel_established"],
        ),
        "independent_operation_observations": _gate_result(
            observed=len(predicate_refs["channel_operation_observed"]),
            required=int(thresholds["independent_operation_observation_min"]),
            evidence_refs=predicate_refs["channel_operation_observed"],
        ),
        "operation_years": _gate_result(
            observed=len(operation_years),
            required=int(thresholds["operation_year_min"]),
            evidence_refs=predicate_refs["channel_operation_observed"],
        ),
        "distinct_expression_actors": _gate_result(
            observed=len(expression_actors),
            required=int(thresholds["distinct_expression_actor_min"]),
            evidence_refs={
                str(row["observation_ref"])
                for row in observations
                if _nonempty_strings(row.get("expression_actors"))
            },
        ),
        "formal_subjects": _gate_result(
            observed=len(formal_subjects),
            required=int(thresholds["formal_subject_min"]),
            evidence_refs={
                str(row["observation_ref"])
                for row in observations
                if _nonempty_strings(row.get("formal_subjects"))
            },
        ),
        "expression_safety": _gate_result(
            observed=len(predicate_refs["expression_safety_observed"]),
            required=int(thresholds["expression_safety_observation_min"]),
            evidence_refs=predicate_refs["expression_safety_observed"],
        ),
        "three_axis_coverage": _gate_result(
            observed=sum(bool(axis_refs[axis]) for axis in REQUIRED_AXES),
            required=int(thresholds["required_axis_count"]),
            evidence_refs={ref for refs in axis_refs.values() for ref in refs},
        ),
    }
    candidate_formed = all(gate["passed"] for gate in gates.values())

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "institution_candidate_recalled" if candidate_formed else "no_candidate",
        "case_ref": contract["case_ref"],
        "contract_sha256": _stable_hash(contract),
        "query": {
            "ruler_name": contract["query"]["ruler_name"],
            "rule_code": contract["query"]["rule_code"],
            "chapter_title_supplied": False,
            "passage_locator_supplied": False,
            "institution_answer_supplied": False,
            "candidate_source_catalog_ref": contract["query"][
                "candidate_source_catalog_ref"
            ],
        },
        "axis_coverage": {
            axis: {
                "observation_count": len(axis_refs[axis]),
                "observation_refs": sorted(axis_refs[axis]),
            }
            for axis in REQUIRED_AXES
        },
        "candidate": {
            "institution_key": institution_key,
            "candidate_type": "ruler_level_cross_person_institution",
            "disposition": "candidate_only" if candidate_formed else "not_formed",
            "gate_results": gates,
            "operation_years": sorted(operation_years),
            "expression_actors": sorted(expression_actors),
            "formal_subjects": sorted(formal_subjects),
            "source_refs": sorted(source_refs),
            "passage_refs": sorted(passage_refs),
        },
        "summary": {
            "candidate_count": int(candidate_formed),
            "observation_count": len(observations),
            "retrieval_axis_count": len(REQUIRED_AXES),
            "network_requests_performed": 0,
            "database_write_count": 0,
            "facts_accepted": 0,
            "factor_choices_created": 0,
            "score_contributions_created": 0,
            "formal_scoring_allowed": False,
        },
        "next_gate": (
            "source_passage_assertion_and_human_or_rule_acceptance_review"
            if candidate_formed
            else "expand_candidate_catalog_without_answer_hints"
        ),
    }


def generate_i5b_institution_retrieval_report(
    contract_path: Path, output_path: Path
) -> dict[str, Any]:
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    if not isinstance(contract, Mapping):
        raise ValueError("制度检索合同必须为对象")
    report = evaluate_i5b_institution_retrieval(contract)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="生成第五项跨人物制度检索离线回归报告")
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    generate_i5b_institution_retrieval_report(args.contract, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
