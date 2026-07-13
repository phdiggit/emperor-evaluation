from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest

from emperor_v4.evaluation.relation_blocking import build_relation_candidate_blocks


def _hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _assertion(code: str, person: str, year: int, passage: str) -> dict:
    return {
        "assertion_code": code,
        "source_passage_ref": passage,
        "subject": "皇帝",
        "object": person,
        "qualifiers": {"normalized_time": {"start_sort_key": year}},
    }


def _payloads(rows: list[tuple[str, str, int, str]]) -> tuple[dict, dict]:
    assertions = [
        _assertion(f"A-{index}", person, year, passage)
        for index, (_, person, year, passage) in enumerate(rows)
    ]
    blind = {"dataset_code": "blocking-test", "assertions": assertions}
    graph = {
        "dataset_code": "blocking-test",
        "input_sha256": _hash(blind),
        "episode_groups": [
            {
                "local_episode_code": episode,
                "evaluation_context": "PER-RULER",
                "focal_person_ref": person,
                "core_assertion_refs": [f"A-{index}"],
            }
            for index, (episode, person, _, _) in enumerate(rows)
        ],
    }
    return graph, blind


def test_shared_focal_inside_temporal_window_is_auditable_candidate() -> None:
    graph, blind = _payloads(
        [("EP-1", "官员甲", 100, "SP-1"), ("EP-2", "官员甲", 108, "SP-2")]
    )

    report = build_relation_candidate_blocks(graph, blind)

    assert report["candidate_pair_count"] == 1
    assert report["excluded_unreviewed_pair_count"] == 0
    signals = {
        row["blocking_signal"] for row in report["candidates"][0]["blocking_reasons"]
    }
    assert "shared_focal_temporal_window" in signals
    assert report["formal_relation_count"] == 0
    assert report["model_call_count"] == 0


def test_far_same_focal_pair_is_excluded_not_marked_unrelated() -> None:
    graph, blind = _payloads(
        [("EP-1", "官员甲", 100, "SP-1"), ("EP-2", "官员甲", 120, "SP-2")]
    )

    report = build_relation_candidate_blocks(graph, blind)

    assert report["candidate_pair_count"] == 0
    assert report["excluded_unreviewed_pair_count"] == 1
    assert report["excluded_pair_semantics"] == "not_review_eligible_not_distinct_unrelated"


def test_selective_entity_and_shared_passage_are_independent_blockers() -> None:
    graph, blind = _payloads(
        [
            ("EP-1", "官员甲", 100, "SP-X"),
            ("EP-2", "官员乙", 130, "SP-X"),
            ("EP-3", "官员丙", 300, "SP-3"),
        ]
    )
    blind["assertions"][0]["subject"] = "共同决策者"
    blind["assertions"][1]["subject"] = "共同决策者"
    graph["input_sha256"] = _hash(blind)

    report = build_relation_candidate_blocks(graph, blind)
    signals = {
        row["blocking_signal"] for row in report["candidates"][0]["blocking_reasons"]
    }

    assert signals == {"shared_selective_endpoint_entity", "shared_source_passage"}


def test_ubiquitous_entity_does_not_recreate_all_pairs() -> None:
    rows = [
        (f"EP-{index}", f"官员-{index}", 100 + index * 20, f"SP-{index}")
        for index in range(20)
    ]
    graph, blind = _payloads(rows)

    report = build_relation_candidate_blocks(graph, blind)

    assert report["possible_pair_count"] == 190
    assert report["candidate_pair_count"] == 0
    assert report["candidate_reduction_ratio"] == 1.0


def test_unrelated_episode_addition_preserves_existing_candidate_identity() -> None:
    graph, blind = _payloads(
        [("EP-1", "官员甲", 100, "SP-1"), ("EP-2", "官员甲", 108, "SP-2")]
    )
    first = build_relation_candidate_blocks(graph, blind)
    expanded_graph, expanded_blind = _payloads(
        [
            ("EP-1", "官员甲", 100, "SP-1"),
            ("EP-2", "官员甲", 108, "SP-2"),
            ("EP-3", "官员乙", 300, "SP-3"),
        ]
    )

    second = build_relation_candidate_blocks(expanded_graph, expanded_blind)

    assert second["candidates"][0]["candidate_code"] == first["candidates"][0]["candidate_code"]
    assert second["candidates"][0]["candidate_basis_sha256"] == first["candidates"][0]["candidate_basis_sha256"]


def test_blocking_is_deterministic_and_rejects_gold_or_hash_leakage() -> None:
    graph, blind = _payloads(
        [("EP-1", "官员甲", 100, "SP-1"), ("EP-2", "官员甲", 108, "SP-2")]
    )
    assert build_relation_candidate_blocks(graph, blind) == build_relation_candidate_blocks(
        deepcopy(graph), deepcopy(blind)
    )

    leaked = deepcopy(graph)
    leaked["gold_relations"] = []
    with pytest.raises(ValueError, match="禁止字段"):
        build_relation_candidate_blocks(leaked, blind)

    mismatched = deepcopy(graph)
    mismatched["input_sha256"] = "wrong"
    with pytest.raises(ValueError, match="hash 不一致"):
        build_relation_candidate_blocks(mismatched, blind)
