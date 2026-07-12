from __future__ import annotations

from itertools import combinations
from typing import Any, Iterable, Mapping


def _group_map(
    rows: Iterable[Mapping[str, Any]], *, code_key: str
) -> dict[str, frozenset[str]]:
    result = {}
    owners = {}
    for row in rows:
        code = str(row.get(code_key) or "")
        refs = frozenset(row.get("core_assertion_refs") or row.get("expected_assertion_refs") or ())
        if not code or not refs or code in result:
            raise ValueError("Episode partition 的 code/refs 缺失或重复")
        result[code] = refs
        for ref in refs:
            previous = owners.setdefault(ref, code)
            if previous != code:
                raise ValueError(f"Assertion 被多个 episode core 占用: {ref}")
    return result


def _same_episode_pairs(groups: Iterable[frozenset[str]]) -> set[frozenset[str]]:
    return {
        frozenset(pair)
        for group in groups
        for pair in combinations(sorted(group), 2)
    }


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _relation_signatures(
    rows: Iterable[Mapping[str, Any]],
    groups: Mapping[str, frozenset[str]],
) -> set[tuple[frozenset[str], frozenset[str], str]]:
    signatures = set()
    for row in rows:
        source = str(row.get("from_episode") or row.get("from_episode_ref") or "")
        target = str(row.get("to_episode") or row.get("to_episode_ref") or "")
        relation_type = str(row.get("relation_type") or "")
        if source not in groups or target not in groups or not relation_type:
            raise ValueError("Relation 引用了未知 episode 或缺少 relation_type")
        signatures.add((groups[source], groups[target], relation_type))
    return signatures


def score_boundary_graph(
    candidate: Mapping[str, Any], gold: Mapping[str, Any]
) -> dict[str, Any]:
    """Score episode partitions and relation graph independently."""

    candidates = _group_map(candidate.get("episode_groups") or (), code_key="local_episode_code")
    gold_groups = _group_map(gold.get("gold_episodes") or (), code_key="gold_episode_code")

    exact_candidate = {
        candidate_code: gold_code
        for candidate_code, candidate_refs in candidates.items()
        for gold_code, gold_refs in gold_groups.items()
        if candidate_refs == gold_refs
    }
    exact_gold = {gold_code: candidate_code for candidate_code, gold_code in exact_candidate.items()}
    overlaps = {
        candidate_code: {
            gold_code
            for gold_code, gold_refs in gold_groups.items()
            if candidate_refs & gold_refs
        }
        for candidate_code, candidate_refs in candidates.items()
    }
    wrong_merges = sorted(code for code, items in overlaps.items() if len(items) > 1)
    gold_overlaps = {
        gold_code: {
            candidate_code
            for candidate_code, candidate_refs in candidates.items()
            if candidate_refs & gold_refs
        }
        for gold_code, gold_refs in gold_groups.items()
    }
    wrong_splits = sorted(code for code, items in gold_overlaps.items() if len(items) > 1)
    safe_fragments = sorted(
        candidate_code
        for candidate_code, candidate_refs in candidates.items()
        if len(overlaps[candidate_code]) == 1
        and any(candidate_refs < gold_groups[gold_code] for gold_code in overlaps[candidate_code])
    )

    candidate_pairs = _same_episode_pairs(candidates.values())
    gold_pairs = _same_episode_pairs(gold_groups.values())
    true_pairs = candidate_pairs & gold_pairs

    catastrophic_pairs = {
        frozenset(pair)
        for pair in gold.get("catastrophic_must_not_merge_pairs") or ()
        if len(pair) == 2
    }
    catastrophic = sorted(
        candidate_code
        for candidate_code, items in overlaps.items()
        if any(pair <= items for pair in catastrophic_pairs)
    )

    candidate_relations = _relation_signatures(
        candidate.get("relations") or (), candidates
    )
    gold_relations = _relation_signatures(gold.get("gold_relations") or (), gold_groups)
    correct_relations = candidate_relations & gold_relations
    relation_types = sorted(
        {item[2] for item in candidate_relations | gold_relations}
    )
    relation_type_metrics = {}
    for relation_type in relation_types:
        proposed = {item for item in candidate_relations if item[2] == relation_type}
        expected = {item for item in gold_relations if item[2] == relation_type}
        correct = proposed & expected
        relation_type_metrics[relation_type] = {
            "precision": _ratio(len(correct), len(proposed)),
            "recall": _ratio(len(correct), len(expected)),
        }

    mandate_types = {"continues", "same_mandate_phase", "renews_authority"}
    feedback_types = {"revokes", "outcome_of"}
    causal_types = {"causal_followup"}

    def coverage(types: set[str]) -> float | None:
        expected = {item for item in gold_relations if item[2] in types}
        return _ratio(len(expected & candidate_relations), len(expected))

    return {
        "schema_version": 2,
        "status": "episode_and_relation_scored_separately",
        "episode_metrics": {
            "exact_episode_recall": _ratio(len(exact_gold), len(gold_groups)),
            "exact_candidate_precision": _ratio(
                len(exact_candidate), len(candidates)
            ),
            "pairwise_same_episode_precision": _ratio(
                len(true_pairs), len(candidate_pairs)
            ),
            "pairwise_same_episode_recall": _ratio(len(true_pairs), len(gold_pairs)),
            "wrong_merge_count": len(wrong_merges),
            "wrong_split_count": len(wrong_splits),
            "safe_fragment_count": len(safe_fragments),
            "catastrophic_wrong_merge_count": len(catastrophic),
        },
        "relation_metrics": {
            "relation_precision": _ratio(
                len(correct_relations), len(candidate_relations)
            ),
            "relation_recall": _ratio(len(correct_relations), len(gold_relations)),
            "relation_type_metrics": relation_type_metrics,
            "mandate_chain_coverage": coverage(mandate_types),
            "revocation_outcome_linkage_coverage": coverage(feedback_types),
            "causal_responsibility_preservation": coverage(causal_types),
        },
        "diagnostics": {
            "exact_candidate_matches": exact_candidate,
            "wrong_merge_candidate_codes": wrong_merges,
            "wrong_split_gold_episode_codes": wrong_splits,
            "safe_fragment_candidate_codes": safe_fragments,
            "catastrophic_wrong_merge_candidate_codes": catastrophic,
        },
    }
