from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any, Mapping

from emperor_v4.evaluation.relation_blocking import (
    RELATION_BLOCKING_POLICY_VERSION,
    build_relation_candidate_blocks,
)


ENDPOINT_REVIEW_POLICY_VERSION = "relation-endpoint-review-v1"
ENDPOINT_REVIEW_SCHEMA_VERSION = "relation-endpoint-review-output-v1"
ENDPOINT_ADJUDICATION_SCHEMA_VERSION = "relation-endpoint-adjudication-output-v1"
DIRECT_RELATION_VALUES = frozenset({"yes", "no", "insufficient"})
COARSE_TYPE_VALUES = frozenset(
    {"authority_change", "mandate_or_outcome", "explicit_causal"}
)

_FORBIDDEN_INPUT_KEYS = frozenset(
    {
        "historical_gold",
        "relation_gold",
        "gold_relations",
        "relation_review",
        "candidate_relation",
        "score",
        "scores",
        "sample_manifest",
        "other_reviewer_output",
    }
)


def _hash(payload: object) -> str:
    rendered = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _reject_forbidden(payload: object, path: str = "$") -> None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            normalized = str(key).strip().casefold()
            if (
                (normalized == "gold_accessed" and value is False)
                or (normalized == "gold_fields_detected" and value == 0)
                or (normalized == "other_reviewer_output_accessed" and value is False)
            ):
                continue
            if normalized in _FORBIDDEN_INPUT_KEYS or normalized.startswith("gold_"):
                raise ValueError(f"Endpoint review 输入包含禁止字段: {path}.{key}")
            _reject_forbidden(value, f"{path}.{key}")
    elif isinstance(payload, (list, tuple)):
        for index, value in enumerate(payload):
            _reject_forbidden(value, f"{path}[{index}]")


def build_endpoint_review_worklist(
    blocking_report: Mapping[str, Any],
    candidate_graph: Mapping[str, Any],
    blind_input: Mapping[str, Any],
) -> dict[str, Any]:
    """为已通过 blocking 的 pair 生成最小 endpoint evidence 双审工作单。"""

    _reject_forbidden(blocking_report)
    _reject_forbidden(candidate_graph)
    _reject_forbidden(blind_input)
    expected_blocking = build_relation_candidate_blocks(candidate_graph, blind_input)
    if dict(blocking_report) != expected_blocking:
        raise ValueError("Endpoint review worklist 与当前 blocking 结果不一致")
    episode_by_code = {
        str(row["local_episode_code"]): row
        for row in candidate_graph.get("episode_groups") or ()
    }
    assertion_by_ref = {
        str(row["assertion_code"]): row
        for row in blind_input.get("assertions") or ()
    }
    passage_by_ref = {
        str(row["passage_code"]): row
        for row in blind_input.get("source_passages") or ()
    }
    if not episode_by_code or not assertion_by_ref or not passage_by_ref:
        raise ValueError("Endpoint review worklist 缺少 Episode/Assertion/Passage")

    tasks = []
    for candidate in blocking_report.get("candidates") or ():
        left_ref = str(candidate["left_episode_ref"])
        right_ref = str(candidate["right_episode_ref"])
        tasks.append(
            {
                "candidate_code": candidate["candidate_code"],
                "candidate_basis_sha256": candidate["candidate_basis_sha256"],
                "blocking_evidence_sha256": candidate["blocking_evidence_sha256"],
                "blocking_reasons": candidate["blocking_reasons"],
                "left": _endpoint_evidence(
                    episode_by_code[left_ref], assertion_by_ref, passage_by_ref
                ),
                "right": _endpoint_evidence(
                    episode_by_code[right_ref], assertion_by_ref, passage_by_ref
                ),
            }
        )
    worklist_basis = {
        "dataset_code": blocking_report.get("dataset_code"),
        "candidate_episode_basis_sha256": blocking_report.get(
            "candidate_episode_basis_sha256"
        ),
        "relation_blocking_policy_version": RELATION_BLOCKING_POLICY_VERSION,
        "endpoint_review_policy_version": ENDPOINT_REVIEW_POLICY_VERSION,
        "tasks": tasks,
    }
    return {
        "schema_version": 1,
        "status": "endpoint_review_worklist_ready",
        "dataset_code": blocking_report.get("dataset_code"),
        "task_code": f"G3R-ENDPOINT-{_hash(worklist_basis)[:20].upper()}",
        "worklist_sha256": _hash(worklist_basis),
        "relation_blocking_policy_version": RELATION_BLOCKING_POLICY_VERSION,
        "endpoint_review_policy_version": ENDPOINT_REVIEW_POLICY_VERSION,
        "output_schema_version": ENDPOINT_REVIEW_SCHEMA_VERSION,
        "policy": {
            "direct_relation": ["yes", "no", "insufficient"],
            "coarse_type": [
                "authority_change",
                "mandate_or_outcome",
                "explicit_causal",
                None,
            ],
            "rules": [
                "只根据两端 endpoint evidence 判断，不读取 Gold、旧 Relation、score 或另一 reviewer 输出。",
                "共享人物、时间、地点、责任族、passage 或一般主题本身不构成直接关系。",
                "direct_relation 为 no 或 insufficient 时 coarse_type 必须为 null。",
                "yes 必须引用两端至少一条 Assertion evidence；no/insufficient 也必须证明已检查两端证据。",
            ],
        },
        "forbidden_inputs": sorted(_FORBIDDEN_INPUT_KEYS),
        "candidate_count": len(tasks),
        "tasks": tasks,
        "formal_relation_count": 0,
        "database_write_count": 0,
    }


def validate_endpoint_adjudication_response(
    worklist: Mapping[str, Any], response: Mapping[str, Any]
) -> dict[str, Mapping[str, Any]]:
    _reject_forbidden(response)
    if (
        response.get("status") != "endpoint_adjudication_complete"
        or response.get("task_code") != worklist.get("task_code")
        or response.get("worklist_sha256") != worklist.get("worklist_sha256")
        or response.get("output_schema_version")
        != ENDPOINT_ADJUDICATION_SCHEMA_VERSION
        or not str(response.get("adjudicator") or "")
    ):
        raise ValueError("Endpoint adjudication response 与 worklist/schema 不一致")
    if (
        response.get("reviewed_without_forbidden_inputs") is not True
        or response.get("gold_accessed") is not False
        or response.get("old_relation_review_accessed") is not False
        or response.get("formal_acceptance_performed") is not False
    ):
        raise ValueError("Endpoint adjudicator 未声明完整隔离与非正式接受")
    task_by_code = {
        str(task["candidate_code"]): task for task in worklist.get("tasks") or ()
    }
    results = tuple(response.get("results") or ())
    result_by_code = {
        str(row.get("candidate_code") or ""): row for row in results
    }
    if (
        "" in result_by_code
        or len(result_by_code) != len(results)
        or set(result_by_code) != set(task_by_code)
    ):
        raise ValueError("Endpoint adjudicator 未完整且唯一覆盖候选")
    for code, task in task_by_code.items():
        row = result_by_code[code]
        direct = row.get("direct_relation")
        coarse = row.get("coarse_type")
        if direct not in DIRECT_RELATION_VALUES:
            raise ValueError("Endpoint adjudication direct_relation 非法")
        if direct == "yes":
            if coarse not in COARSE_TYPE_VALUES:
                raise ValueError("Endpoint adjudication yes 必须声明合法 coarse_type")
        elif coarse is not None:
            raise ValueError("Endpoint adjudication no/insufficient 的 coarse_type 必须为 null")
        if not str(row.get("reason") or "").strip():
            raise ValueError("Endpoint adjudication 缺少 reason")
        refs = tuple(str(ref) for ref in row.get("evidence_assertion_refs") or ())
        endpoint = task["endpoint_task"]
        left_refs = {
            str(item["assertion_ref"]) for item in endpoint["left"]["assertions"]
        }
        right_refs = {
            str(item["assertion_ref"]) for item in endpoint["right"]["assertions"]
        }
        if (
            not refs
            or len(refs) != len(set(refs))
            or not set(refs) <= left_refs | right_refs
            or not set(refs) & left_refs
            or not set(refs) & right_refs
        ):
            raise ValueError("Endpoint adjudication evidence 必须只引用且覆盖两端")
    return result_by_code


def apply_endpoint_adjudication(
    source_worklist: Mapping[str, Any],
    first: Mapping[str, Any],
    second: Mapping[str, Any],
    adjudication_worklist: Mapping[str, Any],
    response: Mapping[str, Any],
) -> dict[str, Any]:
    expected = build_endpoint_adjudication_worklist(source_worklist, first, second)
    if dict(adjudication_worklist) != expected:
        raise ValueError("Endpoint adjudication worklist 与冻结双审分歧不一致")
    adjudicated = validate_endpoint_adjudication_response(
        adjudication_worklist, response
    )
    comparison = compare_endpoint_reviewers(source_worklist, first, second)
    final_rows = []
    unresolved_count = 0
    for row in comparison["comparisons"]:
        code = str(row["candidate_code"])
        if row["proposed_disposition"] != "needs_adjudication":
            final_rows.append(dict(row))
            continue
        decision = adjudicated[code]
        direct = str(decision["direct_relation"])
        if direct == "yes":
            disposition = "proposed_direct_relation"
        elif direct == "no":
            disposition = "proposed_distinct_unrelated"
        else:
            disposition = "needs_endpoint_evidence"
            unresolved_count += 1
        final_rows.append(
            {
                "candidate_code": code,
                "direct_agreement": False,
                "coarse_type_agreement": False,
                "proposed_disposition": disposition,
                "direct_relation": direct,
                "coarse_type": decision.get("coarse_type"),
                "resolved_by_adjudication": direct != "insufficient",
            }
        )
    thresholds_met = (
        comparison["direct_agreement_rate"] >= 0.90
        and comparison["coarse_type_agreement_rate"] >= 0.80
    )
    gate_passed = thresholds_met and unresolved_count == 0
    return {
        "schema_version": 1,
        "status": (
            "endpoint_agreement_gate_passed_after_adjudication"
            if gate_passed
            else "endpoint_adjudication_complete_with_evidence_gaps"
        ),
        "source_task_code": source_worklist.get("task_code"),
        "adjudication_task_code": adjudication_worklist.get("task_code"),
        "candidate_count": len(final_rows),
        "direct_agreement_rate": comparison["direct_agreement_rate"],
        "coarse_type_agreement_rate": comparison["coarse_type_agreement_rate"],
        "agreement_thresholds_met": thresholds_met,
        "adjudicated_candidate_count": len(adjudicated),
        "remaining_evidence_gap_count": unresolved_count,
        "agreement_gate_passed": gate_passed,
        "final_proposals": final_rows,
        "formal_acceptance_performed": False,
        "formal_relation_count": 0,
        "database_write_count": 0,
    }


def build_stratified_endpoint_sample(
    worklists: Mapping[str, Mapping[str, Any]],
    dataset_quotas: Mapping[str, int],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """按数据集配额和 blocking 信号组合机械抽样，不读取判断结果或 Gold。"""

    if set(worklists) != set(dataset_quotas) or not worklists:
        raise ValueError("Endpoint sample worklist 与 dataset quota 必须一一对应")
    selected_tasks = []
    dataset_rows = {}
    for dataset in sorted(worklists):
        worklist = worklists[dataset]
        quota = int(dataset_quotas[dataset])
        tasks = tuple(worklist.get("tasks") or ())
        if (
            worklist.get("status") != "endpoint_review_worklist_ready"
            or worklist.get("dataset_code") != dataset
            or quota < 1
            or quota > len(tasks)
        ):
            raise ValueError("Endpoint sample dataset、状态或 quota 非法")
        buckets: dict[tuple[str, ...], list[Mapping[str, Any]]] = defaultdict(list)
        for task in tasks:
            signature = tuple(
                sorted(
                    {
                        str(reason.get("blocking_signal") or "")
                        for reason in task.get("blocking_reasons") or ()
                    }
                )
            )
            if not signature or "" in signature:
                raise ValueError("Endpoint sample 候选缺少 blocking signal")
            buckets[signature].append(task)
        for rows in buckets.values():
            rows.sort(key=lambda row: str(row["candidate_code"]))
        dataset_selected = []
        signatures = sorted(buckets)
        while len(dataset_selected) < quota:
            progressed = False
            for signature in signatures:
                if len(dataset_selected) >= quota:
                    break
                rows = buckets[signature]
                if not rows:
                    continue
                dataset_selected.append(rows.pop(0))
                progressed = True
            if not progressed:
                raise ValueError("Endpoint sample 无法满足 dataset quota")
        selected_tasks.extend(
            {**dict(task), "dataset_code": dataset} for task in dataset_selected
        )
        selected_signature_counts: dict[str, int] = defaultdict(int)
        for task in dataset_selected:
            signature = "+".join(
                sorted(
                    {
                        str(reason["blocking_signal"])
                        for reason in task["blocking_reasons"]
                    }
                )
            )
            selected_signature_counts[signature] += 1
        dataset_rows[dataset] = {
            "source_task_code": worklist["task_code"],
            "source_worklist_sha256": worklist["worklist_sha256"],
            "available_candidate_count": len(tasks),
            "selected_candidate_count": len(dataset_selected),
            "selected_signal_signature_counts": dict(
                sorted(selected_signature_counts.items())
            ),
        }

    selected_tasks.sort(
        key=lambda row: (str(row["dataset_code"]), str(row["candidate_code"]))
    )
    sample_basis = {
        "selection_policy": "dataset_quota_signal_signature_round_robin_v1",
        "dataset_quotas": dict(sorted(dataset_quotas.items())),
        "source_worklists": {
            dataset: worklists[dataset]["worklist_sha256"]
            for dataset in sorted(worklists)
        },
        "candidate_codes": [task["candidate_code"] for task in selected_tasks],
        "endpoint_review_policy_version": ENDPOINT_REVIEW_POLICY_VERSION,
    }
    sample_hash = _hash(sample_basis)
    first_worklist = worklists[sorted(worklists)[0]]
    sample_worklist = {
        "schema_version": 1,
        "status": "endpoint_review_worklist_ready",
        "dataset_code": "g3r_i_j_stratified_development_sample",
        "task_code": f"G3R-ENDPOINT-SAMPLE-{sample_hash[:20].upper()}",
        "worklist_sha256": sample_hash,
        "relation_blocking_policy_version": first_worklist[
            "relation_blocking_policy_version"
        ],
        "endpoint_review_policy_version": ENDPOINT_REVIEW_POLICY_VERSION,
        "output_schema_version": ENDPOINT_REVIEW_SCHEMA_VERSION,
        "policy": first_worklist["policy"],
        "forbidden_inputs": first_worklist["forbidden_inputs"],
        "candidate_count": len(selected_tasks),
        "tasks": selected_tasks,
        "formal_relation_count": 0,
        "database_write_count": 0,
    }
    manifest = {
        "schema_version": 1,
        "status": "endpoint_review_sample_frozen",
        "sample_task_code": sample_worklist["task_code"],
        "sample_worklist_sha256": sample_hash,
        "selection_policy": "dataset_quota_signal_signature_round_robin_v1",
        "dataset_quotas": dict(sorted(dataset_quotas.items())),
        "datasets": dataset_rows,
        "selected_candidate_count": len(selected_tasks),
        "selected_candidate_codes": [
            task["candidate_code"] for task in selected_tasks
        ],
        "gold_accessed": False,
        "old_relation_review_accessed": False,
        "reviewer_output_accessed": False,
    }
    return sample_worklist, manifest


def _endpoint_evidence(
    episode: Mapping[str, Any],
    assertion_by_ref: Mapping[str, Mapping[str, Any]],
    passage_by_ref: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    assertions = []
    passages = {}
    for assertion_ref in episode.get("core_assertion_refs") or ():
        assertion = assertion_by_ref.get(str(assertion_ref))
        if assertion is None:
            raise ValueError("Endpoint review Episode 引用了未知 Assertion")
        passage_ref = str(assertion.get("source_passage_ref") or "")
        passage = passage_by_ref.get(passage_ref)
        if passage is None:
            raise ValueError("Endpoint review Assertion 缺少 SourcePassage lineage")
        qualifiers = assertion.get("qualifiers") or {}
        assertions.append(
            {
                "assertion_ref": assertion_ref,
                "subject": assertion.get("subject"),
                "predicate": assertion.get("predicate"),
                "object": assertion.get("object"),
                "time_expression": assertion.get("time_expression"),
                "normalized_time": qualifiers.get("normalized_time"),
                "location_expression": assertion.get("location_expression"),
                "responsibility_family": qualifiers.get("responsibility_family"),
                "outcome": qualifiers.get("outcome"),
                "claim_summary": qualifiers.get("claim_summary"),
                "polarity": assertion.get("polarity"),
                "source_passage_ref": passage_ref,
            }
        )
        passages[passage_ref] = {
            "source_passage_ref": passage_ref,
            "document_code": passage.get("document_code"),
            "section_heading": passage.get("section_heading"),
            "locator": passage.get("locator"),
            "context_before": passage.get("context_before"),
            "raw_text": passage.get("raw_text"),
            "context_after": passage.get("context_after"),
        }
    return {
        "episode_ref": episode["local_episode_code"],
        "focal_person_ref": episode.get("focal_person_ref"),
        "focal_roles": episode.get("focal_roles") or (),
        "action": episode.get("action"),
        "responsibility": episode.get("responsibility"),
        "responsibility_family": episode.get("responsibility_family"),
        "assertions": sorted(assertions, key=lambda row: str(row["assertion_ref"])),
        "source_passages": sorted(
            passages.values(), key=lambda row: str(row["source_passage_ref"])
        ),
    }


def validate_endpoint_review_response(
    worklist: Mapping[str, Any],
    response: Mapping[str, Any],
    *,
    expected_reviewer: str | None = None,
) -> dict[str, Mapping[str, Any]]:
    _reject_forbidden(response)
    reviewer = str(response.get("reviewer") or "")
    if not reviewer or (expected_reviewer is not None and reviewer != expected_reviewer):
        raise ValueError("Endpoint reviewer 身份缺失或不匹配")
    if (
        response.get("status") != "endpoint_reviews_complete"
        or response.get("task_code") != worklist.get("task_code")
        or response.get("worklist_sha256") != worklist.get("worklist_sha256")
        or response.get("endpoint_review_policy_version")
        != ENDPOINT_REVIEW_POLICY_VERSION
        or response.get("output_schema_version") != ENDPOINT_REVIEW_SCHEMA_VERSION
    ):
        raise ValueError("Endpoint review response 与 worklist/policy/schema 不一致")
    if (
        response.get("reviewed_without_forbidden_inputs") is not True
        or response.get("gold_accessed") is not False
        or response.get("other_reviewer_output_accessed") is not False
        or response.get("formal_acceptance_performed") is not False
    ):
        raise ValueError("Endpoint reviewer 未声明完整隔离与非正式接受")
    task_by_code = {
        str(task["candidate_code"]): task for task in worklist.get("tasks") or ()
    }
    results = tuple(response.get("results") or ())
    result_by_code = {
        str(row.get("candidate_code") or ""): row for row in results
    }
    if (
        "" in result_by_code
        or len(result_by_code) != len(results)
        or set(result_by_code) != set(task_by_code)
    ):
        raise ValueError("Endpoint reviewer 未完整且唯一覆盖候选")
    for code, task in task_by_code.items():
        row = result_by_code[code]
        direct = row.get("direct_relation")
        coarse = row.get("coarse_type")
        if direct not in DIRECT_RELATION_VALUES:
            raise ValueError("Endpoint review direct_relation 非法")
        if direct == "yes":
            if coarse not in COARSE_TYPE_VALUES:
                raise ValueError("direct_relation=yes 必须声明合法 coarse_type")
        elif coarse is not None:
            raise ValueError("direct_relation=no/insufficient 时 coarse_type 必须为 null")
        if not str(row.get("reason") or "").strip():
            raise ValueError("Endpoint review 缺少 reason")
        evidence_refs = tuple(str(ref) for ref in row.get("evidence_assertion_refs") or ())
        if not evidence_refs or len(evidence_refs) != len(set(evidence_refs)):
            raise ValueError("Endpoint review evidence refs 缺失或重复")
        left_refs = {
            str(item["assertion_ref"]) for item in task["left"]["assertions"]
        }
        right_refs = {
            str(item["assertion_ref"]) for item in task["right"]["assertions"]
        }
        if (
            not set(evidence_refs) <= left_refs | right_refs
            or not set(evidence_refs) & left_refs
            or not set(evidence_refs) & right_refs
        ):
            raise ValueError("Endpoint review 必须只引用且覆盖两端 Assertion evidence")
    return result_by_code


def compare_endpoint_reviewers(
    worklist: Mapping[str, Any],
    first: Mapping[str, Any],
    second: Mapping[str, Any],
) -> dict[str, Any]:
    first_rows = validate_endpoint_review_response(worklist, first)
    second_rows = validate_endpoint_review_response(worklist, second)
    first_reviewer = str(first["reviewer"])
    second_reviewer = str(second["reviewer"])
    if first_reviewer == second_reviewer:
        raise ValueError("Endpoint 双审必须由不同 reviewer 完成")
    comparisons = []
    direct_agreement_count = 0
    coarse_agreement_count = 0
    adjudication_count = 0
    for task in worklist.get("tasks") or ():
        code = str(task["candidate_code"])
        left = first_rows[code]
        right = second_rows[code]
        direct_agreement = left["direct_relation"] == right["direct_relation"]
        coarse_agreement = left.get("coarse_type") == right.get("coarse_type")
        direct_agreement_count += int(direct_agreement)
        coarse_agreement_count += int(coarse_agreement)
        needs_adjudication = (
            not direct_agreement
            or not coarse_agreement
            or left["direct_relation"] == "insufficient"
        )
        adjudication_count += int(needs_adjudication)
        if needs_adjudication:
            proposal = "needs_adjudication"
        elif left["direct_relation"] == "yes":
            proposal = "proposed_direct_relation"
        else:
            proposal = "proposed_distinct_unrelated"
        comparisons.append(
            {
                "candidate_code": code,
                "direct_agreement": direct_agreement,
                "coarse_type_agreement": coarse_agreement,
                "proposed_disposition": proposal,
                "direct_relation": (
                    left["direct_relation"] if not needs_adjudication else None
                ),
                "coarse_type": left.get("coarse_type") if not needs_adjudication else None,
            }
        )
    total = len(comparisons)
    direct_rate = direct_agreement_count / total if total else 0.0
    coarse_rate = coarse_agreement_count / total if total else 0.0
    agreement_gate_passed = (
        total > 0
        and direct_rate >= 0.90
        and coarse_rate >= 0.80
        and adjudication_count == 0
    )
    return {
        "schema_version": 1,
        "status": (
            "endpoint_dual_review_agreement_passed"
            if agreement_gate_passed
            else "endpoint_dual_review_needs_adjudication"
        ),
        "task_code": worklist.get("task_code"),
        "worklist_sha256": worklist.get("worklist_sha256"),
        "reviewers": sorted((first_reviewer, second_reviewer)),
        "candidate_count": total,
        "direct_agreement_count": direct_agreement_count,
        "direct_agreement_rate": direct_rate,
        "coarse_type_agreement_count": coarse_agreement_count,
        "coarse_type_agreement_rate": coarse_rate,
        "needs_adjudication_count": adjudication_count,
        "agreement_gate_passed": agreement_gate_passed,
        "comparisons": comparisons,
        "formal_acceptance_performed": False,
        "database_write_count": 0,
    }


def build_endpoint_adjudication_worklist(
    worklist: Mapping[str, Any],
    first: Mapping[str, Any],
    second: Mapping[str, Any],
) -> dict[str, Any]:
    """把双审分歧机械封装为第三方裁决输入，不执行裁决或正式接受。"""

    first_rows = validate_endpoint_review_response(worklist, first)
    second_rows = validate_endpoint_review_response(worklist, second)
    comparison = compare_endpoint_reviewers(worklist, first, second)
    task_by_code = {
        str(task["candidate_code"]): task for task in worklist.get("tasks") or ()
    }
    disputed_codes = [
        str(row["candidate_code"])
        for row in comparison["comparisons"]
        if row["proposed_disposition"] == "needs_adjudication"
    ]
    if not disputed_codes:
        raise ValueError("Endpoint 双审没有需要裁决的候选")
    reviewers = (str(first["reviewer"]), str(second["reviewer"]))
    tasks = [
        {
            "candidate_code": code,
            "endpoint_task": task_by_code[code],
            "reviewer_results": {
                reviewers[0]: dict(first_rows[code]),
                reviewers[1]: dict(second_rows[code]),
            },
        }
        for code in disputed_codes
    ]
    basis = {
        "source_worklist_sha256": worklist.get("worklist_sha256"),
        "source_reviewers": sorted(reviewers),
        "source_response_sha256": sorted((_hash(first), _hash(second))),
        "candidate_codes": disputed_codes,
        "endpoint_review_policy_version": ENDPOINT_REVIEW_POLICY_VERSION,
    }
    basis_hash = _hash(basis)
    return {
        "schema_version": 1,
        "status": "endpoint_adjudication_worklist_ready",
        "task_code": f"G3R-ENDPOINT-ADJ-{basis_hash[:20].upper()}",
        "worklist_sha256": basis_hash,
        "source_task_code": worklist.get("task_code"),
        "source_worklist_sha256": worklist.get("worklist_sha256"),
        "endpoint_review_policy_version": ENDPOINT_REVIEW_POLICY_VERSION,
        "output_schema_version": ENDPOINT_ADJUDICATION_SCHEMA_VERSION,
        "candidate_count": len(tasks),
        "tasks": tasks,
        "adjudication_policy": {
            "allowed_decisions": ["yes", "no", "insufficient"],
            "allowed_coarse_types": sorted(COARSE_TYPE_VALUES) + [None],
            "rule": "只根据 endpoint evidence 与两份已冻结 reviewer 理由裁决；不得读取 Gold、旧 Relation 或 score。",
        },
        "gold_accessed": False,
        "formal_acceptance_performed": False,
        "formal_relation_count": 0,
        "database_write_count": 0,
    }
