from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from typing import Any, Mapping


RELATION_BLOCKING_POLICY_VERSION = "episode-relation-blocking-v1"
RELATION_BLOCKING_SCHEMA_VERSION = "episode-relation-candidates-v1"
TEMPORAL_WINDOW_YEARS = 10
MAX_SELECTIVE_ENTITY_EPISODES = 6

_FORBIDDEN_KEYS = frozenset(
    {
        "gold_episode_code",
        "gold_relation_code",
        "gold_relations",
        "historical_gold",
        "relation_review",
        "score",
        "scores",
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
            ):
                continue
            if normalized in _FORBIDDEN_KEYS or normalized.startswith("gold_"):
                raise ValueError(f"Relation blocking 输入包含禁止字段: {path}.{key}")
            _reject_forbidden(value, f"{path}.{key}")
    elif isinstance(payload, (list, tuple)):
        for index, value in enumerate(payload):
            _reject_forbidden(value, f"{path}[{index}]")


def build_relation_candidate_blocks(
    candidate_graph: Mapping[str, Any], blind_input: Mapping[str, Any]
) -> dict[str, Any]:
    """用确定性索引生成 G3R 候选；不枚举 context 内全部 Episode pair。"""

    _reject_forbidden(candidate_graph)
    _reject_forbidden(blind_input)
    if candidate_graph.get("input_sha256") != _hash(blind_input):
        raise ValueError("Relation blocking blind input 与 Candidate graph hash 不一致")
    episode_rows = tuple(candidate_graph.get("episode_groups") or ())
    if not episode_rows:
        raise ValueError("Relation blocking 需要非空 Episode graph")
    assertions = {
        str(row.get("assertion_code") or ""): row
        for row in blind_input.get("assertions") or ()
    }
    if not assertions or "" in assertions:
        raise ValueError("Relation blocking blind input 缺少 Assertion")

    episodes: dict[str, dict[str, Any]] = {}
    contexts: dict[str, list[str]] = defaultdict(list)
    entity_index: dict[tuple[str, str], list[str]] = defaultdict(list)
    passage_index: dict[tuple[str, str], list[str]] = defaultdict(list)
    focal_index: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in episode_rows:
        code = str(row.get("local_episode_code") or "")
        context = str(row.get("evaluation_context") or "")
        if not code or code in episodes or not context:
            raise ValueError("Relation blocking episode code/context 缺失或重复")
        assertion_refs = tuple(str(ref) for ref in row.get("core_assertion_refs") or ())
        if not assertion_refs or any(ref not in assertions for ref in assertion_refs):
            raise ValueError("Relation blocking Episode 引用了未知 Assertion")
        episode_assertions = tuple(assertions[ref] for ref in assertion_refs)
        focal = str(row.get("focal_person_ref") or "")
        focal_normalized = focal.strip().casefold()
        entities = sorted(
            {
                str(value).strip().casefold()
                for assertion in episode_assertions
                for value in (assertion.get("subject"), assertion.get("object"))
                if str(value or "").strip()
                and str(value).strip().casefold() != focal_normalized
            }
        )
        passages = sorted(
            {
                str(assertion.get("source_passage_ref") or "")
                for assertion in episode_assertions
                if str(assertion.get("source_passage_ref") or "")
            }
        )
        times = sorted(
            {
                int(normalized["start_sort_key"])
                for assertion in episode_assertions
                for normalized in [
                    (assertion.get("qualifiers") or {}).get("normalized_time") or {}
                ]
                if normalized.get("start_sort_key") is not None
            }
        )
        episodes[code] = {
            "evaluation_context": context,
            "focal_person_ref": focal,
            "assertion_refs": assertion_refs,
            "entities": tuple(entities),
            "passages": tuple(passages),
            "times": tuple(times),
        }
        contexts[context].append(code)
        for entity in entities:
            entity_index[(context, entity)].append(code)
        for passage in passages:
            passage_index[(context, passage)].append(code)
        if focal and times:
            focal_index[(context, focal)].append(code)

    reasons_by_pair: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for (context, entity), codes in sorted(entity_index.items()):
        unique_codes = sorted(set(codes))
        if (
            not 2 <= len(unique_codes) <= MAX_SELECTIVE_ENTITY_EPISODES
            or len(unique_codes) == len(contexts[context])
        ):
            continue
        for left_index, left in enumerate(unique_codes):
            for right in unique_codes[left_index + 1 :]:
                reasons_by_pair[(left, right)].append(
                    {
                        "blocking_signal": "shared_selective_endpoint_entity",
                        "value": entity,
                        "context_episode_frequency": len(unique_codes),
                    }
                )

    for (_, passage), codes in sorted(passage_index.items()):
        unique_codes = sorted(set(codes))
        for left_index, left in enumerate(unique_codes):
            for right in unique_codes[left_index + 1 :]:
                reasons_by_pair[(left, right)].append(
                    {
                        "blocking_signal": "shared_source_passage",
                        "value": passage,
                    }
                )

    for (_, focal), codes in sorted(focal_index.items()):
        unique_codes = sorted(set(codes))
        for left_index, left in enumerate(unique_codes):
            for right in unique_codes[left_index + 1 :]:
                gap = min(
                    abs(left_time - right_time)
                    for left_time in episodes[left]["times"]
                    for right_time in episodes[right]["times"]
                )
                if gap <= TEMPORAL_WINDOW_YEARS:
                    reasons_by_pair[(left, right)].append(
                        {
                            "blocking_signal": "shared_focal_temporal_window",
                            "value": focal,
                            "minimum_year_gap": gap,
                            "window_years": TEMPORAL_WINDOW_YEARS,
                        }
                    )

    candidates = []
    for pair, reasons in sorted(reasons_by_pair.items()):
        left, right = pair
        if episodes[left]["evaluation_context"] != episodes[right]["evaluation_context"]:
            raise AssertionError("blocking index 生成跨 evaluation context pair")
        identity = {
            "left_episode_ref": left,
            "right_episode_ref": right,
            "left_assertion_refs": episodes[left]["assertion_refs"],
            "right_assertion_refs": episodes[right]["assertion_refs"],
            "policy_version": RELATION_BLOCKING_POLICY_VERSION,
        }
        candidate_hash = _hash(identity)
        candidates.append(
            {
                "candidate_code": f"RBC-{candidate_hash[:20].upper()}",
                "evaluation_context": episodes[left]["evaluation_context"],
                "left_episode_ref": left,
                "right_episode_ref": right,
                "left_assertion_refs": list(episodes[left]["assertion_refs"]),
                "right_assertion_refs": list(episodes[right]["assertion_refs"]),
                "blocking_reasons": reasons,
                "candidate_basis_sha256": candidate_hash,
                "blocking_evidence_sha256": _hash(reasons),
                "review_status": "proposed_for_relation_review",
            }
        )

    possible_pair_count = sum(
        len(codes) * (len(codes) - 1) // 2 for codes in contexts.values()
    )
    candidate_count = len(candidates)
    return {
        "schema_version": 1,
        "status": "relation_candidates_blocked",
        "dataset_code": candidate_graph.get("dataset_code"),
        "candidate_episode_basis_sha256": _hash(
            {
                "dataset_code": candidate_graph.get("dataset_code"),
                "input_sha256": candidate_graph.get("input_sha256"),
                "episode_groups": episode_rows,
            }
        ),
        "relation_blocking_policy_version": RELATION_BLOCKING_POLICY_VERSION,
        "output_schema_version": RELATION_BLOCKING_SCHEMA_VERSION,
        "episode_count": len(episodes),
        "evaluation_context_count": len(contexts),
        "possible_pair_count": possible_pair_count,
        "candidate_pair_count": candidate_count,
        "excluded_unreviewed_pair_count": possible_pair_count - candidate_count,
        "candidate_reduction_ratio": (
            (possible_pair_count - candidate_count) / possible_pair_count
            if possible_pair_count
            else 0.0
        ),
        "candidates": candidates,
        "excluded_pair_semantics": "not_review_eligible_not_distinct_unrelated",
        "formal_relation_count": 0,
        "model_call_count": 0,
        "database_write_count": 0,
        "gold_fields_detected": 0,
    }
