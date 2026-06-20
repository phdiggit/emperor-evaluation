from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DISPLAY_SPEC = importlib.util.spec_from_file_location(
    "i5b_cluster_warning_display",
    ROOT / "scripts" / "i5b_cluster_warning_display.py",
)
assert DISPLAY_SPEC is not None
i5b_cluster_warning_display = importlib.util.module_from_spec(DISPLAY_SPEC)
sys.modules[DISPLAY_SPEC.name] = i5b_cluster_warning_display
assert DISPLAY_SPEC.loader is not None
DISPLAY_SPEC.loader.exec_module(i5b_cluster_warning_display)

ALLOWED_WARNING_KEYS = {
    "cluster_id",
    "warning_rule_id",
    "warning_type",
    "warning_message",
    "matched_terms",
    "matched_fields",
    "matched_reason",
    "required_human_review",
    "display_only",
    "no_score_effect",
}

FORBIDDEN_OUTPUT_KEYS = {
    "person",
    "evidence_id",
    "linked_evidence_ids",
    "candidate_strength",
    "auto_band_direction",
    "net_adjudication_draft",
    "formal_score",
    "ranking",
    "final_band",
    "definitive_band",
}


def make_cluster(**overrides: object) -> dict[str, object]:
    cluster = {
        "cluster_id": "ADJ-I5B-TEST-001",
        "person": "刘邦",
        "polarity": "positive",
        "candidate_strength": 3,
        "cross_item_split": "",
        "five_axis_assessment": {"residual_after_split": "medium"},
        "trigger_terms": [],
        "summary": "",
    }
    cluster.update(overrides)
    return cluster


def make_card(**overrides: object) -> dict[str, object]:
    card = {
        "evidence_id": "EVD-I5B-TEST-001",
        "trigger_terms": [],
        "trigger_family": "",
        "scoring_effect": "",
        "cross_item_split": "",
        "evidence_role": "",
        "cluster_role": "",
        "strength": 2,
        "upper_bound_flag": "",
        "mitigation_flag": "",
        "summary": "",
    }
    card.update(overrides)
    return card


def make_rule(**overrides: object) -> dict[str, object]:
    rule = {
        "rule_id": "I5B-CLUSTER-WARN-TEST",
        "enabled": False,
        "subitem": "第五项B",
        "trigger_type": "trigger_terms",
        "trigger_terms": ["测试词"],
        "polarity_scope": ["positive", "negative"],
        "evidence_strength_scope": ["candidate_strength_3"],
        "warning_type": "source_review_required",
        "warning_message": "提示人工复核。",
        "adjacent_item_risk": ["第五项C"],
        "required_human_review": True,
    }
    rule.update(overrides)
    return rule


def match(
    cluster: dict[str, object],
    cards: list[dict[str, object]],
    rules: list[dict[str, object]],
) -> list[dict[str, object]]:
    return i5b_cluster_warning_display.match_display_only_cluster_warnings(cluster, cards, rules)


def assert_display_only_warning(warning: dict[str, object], warning_type: str) -> None:
    assert set(warning) == ALLOWED_WARNING_KEYS
    assert not (set(warning) & FORBIDDEN_OUTPUT_KEYS)
    assert warning["warning_type"] == warning_type
    assert warning["display_only"] is True
    assert warning["no_score_effect"] is True
    assert warning["required_human_review"] is True


def test_adjacent_item_contamination_rule_matches_readonly_text() -> None:
    cluster = make_cluster(cross_item_split="军功和行政成效不得回填第五项B。")
    rule = make_rule(
        rule_id="I5B-CLUSTER-WARN-ADJACENT-CONTAMINATION",
        trigger_terms=["统一", "军功", "行政成效"],
        warning_type="adjacent_item_contamination",
        warning_message="提示人工检查相邻项污染。",
    )

    warnings = match(cluster, [], [rule])

    assert len(warnings) == 1
    assert_display_only_warning(warnings[0], "adjacent_item_contamination")
    assert warnings[0]["matched_terms"] == ["军功", "行政成效"]
    assert "cluster.cross_item_split" in warnings[0]["matched_fields"]


def test_single_evidence_limit_rule_matches_card_text() -> None:
    cluster = make_cluster(candidate_strength=2)
    card = make_card(summary="该簇仍是单证结构，接近孤证。", strength=2)
    rule = make_rule(
        rule_id="I5B-CLUSTER-WARN-SINGLE-EVIDENCE-LIMIT",
        trigger_type="cluster_structure",
        trigger_terms=["单证", "孤证"],
        evidence_strength_scope=["candidate_strength_1", "candidate_strength_2", "candidate_strength_3"],
        warning_type="single_evidence_limit",
        warning_message="提示人工检查单证限制。",
    )

    warnings = match(cluster, [card], [rule])

    assert len(warnings) == 1
    assert_display_only_warning(warnings[0], "single_evidence_limit")
    assert warnings[0]["matched_terms"] == ["单证", "孤证"]
    assert "linked_cards[0].summary" in warnings[0]["matched_fields"]


def test_source_review_required_rule_matches_strength_and_text() -> None:
    cluster = make_cluster(candidate_strength=3, summary="强正上探候选需要回源。")
    rule = make_rule(
        rule_id="I5B-CLUSTER-WARN-SOURCE-REVIEW-REQUIRED",
        trigger_terms=["强负", "强正", "上探"],
        evidence_strength_scope=["candidate_strength_3", "candidate_strength_4"],
        warning_type="source_review_required",
        warning_message="提示人工回源核验。",
    )

    warnings = match(cluster, [], [rule])

    assert len(warnings) == 1
    assert_display_only_warning(warnings[0], "source_review_required")
    assert warnings[0]["matched_terms"] == ["强正", "上探"]


def test_mixed_polarity_rule_matches_text_or_both_polarity() -> None:
    text_cluster = make_cluster(
        polarity="positive",
        summary="本簇存在正负并存关系，不能简单抵消。",
    )
    both_cluster = make_cluster(polarity="both", summary="")
    rule = make_rule(
        rule_id="I5B-CLUSTER-WARN-MIXED-POLARITY",
        trigger_type="polarity_relation",
        trigger_terms=["正负并存"],
        polarity_scope=["both"],
        warning_type="mixed_polarity_review",
        warning_message="提示人工保留正负并存关系。",
    )

    text_warnings = match(text_cluster, [], [rule])
    both_warnings = match(both_cluster, [], [rule])

    assert len(text_warnings) == 1
    assert_display_only_warning(text_warnings[0], "mixed_polarity_review")
    assert text_warnings[0]["matched_terms"] == ["正负并存"]
    assert len(both_warnings) == 1
    assert_display_only_warning(both_warnings[0], "mixed_polarity_review")
    assert both_warnings[0]["matched_terms"] == ["polarity:both"]
    assert both_warnings[0]["matched_fields"] == ["cluster.polarity"]


def test_person_does_not_trigger_warning() -> None:
    cluster = make_cluster(person="刘邦")
    rule = make_rule(
        rule_id="I5B-CLUSTER-WARN-PERSON-NAME",
        trigger_terms=["刘邦"],
        warning_type="adjacent_item_contamination",
    )

    assert match(cluster, [], [rule]) == []


def test_cluster_id_and_evidence_id_do_not_trigger_warning() -> None:
    cluster = make_cluster(cluster_id="ADJ-I5B-TEST-001")
    card = make_card(evidence_id="EVD-I5B-TEST-001")
    rule = make_rule(
        rule_id="I5B-CLUSTER-WARN-ID",
        trigger_terms=["ADJ-I5B-TEST-001", "EVD-I5B-TEST-001"],
        warning_type="source_review_required",
    )

    assert match(cluster, [card], [rule]) == []


def test_matcher_does_not_mutate_inputs() -> None:
    cluster = make_cluster(
        cross_item_split="军功不回填。",
        auto_band_direction="强正受压制",
        net_adjudication_draft="原始草案",
    )
    cards = [make_card(trigger_terms=["军功"], scoring_effect="不得直接入分。")]
    rules = [
        make_rule(
            rule_id="I5B-CLUSTER-WARN-ADJACENT-CONTAMINATION",
            trigger_terms=["军功"],
            warning_type="adjacent_item_contamination",
        )
    ]
    before = copy.deepcopy((cluster, cards, rules))

    warnings = match(cluster, cards, rules)

    assert (cluster, cards, rules) == before
    assert warnings[0]["cluster_id"] == "ADJ-I5B-TEST-001"


def test_output_key_whitelist_and_auto_draft_fields_stay_out_of_warnings() -> None:
    cluster = make_cluster(
        candidate_strength=3,
        auto_band_direction="高位强正，上探极正候选",
        net_adjudication_draft="不得被输出",
        formal_score=100,
        ranking=1,
        summary="强正上探候选。",
    )
    rule = make_rule(
        trigger_terms=["强正", "上探"],
        warning_type="source_review_required",
        evidence_strength_scope=["candidate_strength_3"],
    )

    warnings = match(cluster, [], [rule])

    assert len(warnings) == 1
    assert set(warnings[0]) == ALLOWED_WARNING_KEYS
    assert not (set(warnings[0]) & FORBIDDEN_OUTPUT_KEYS)
    assert cluster["auto_band_direction"] == "高位强正，上探极正候选"
    assert cluster["net_adjudication_draft"] == "不得被输出"
    assert cluster["candidate_strength"] == 3


def test_enabled_true_rule_is_ignored() -> None:
    cluster = make_cluster(summary="强正上探候选。")
    rule = make_rule(
        enabled=True,
        trigger_terms=["强正", "上探"],
        warning_type="source_review_required",
    )

    assert match(cluster, [], [rule]) == []


def test_no_match_returns_empty_list() -> None:
    cluster = make_cluster(summary="没有额外提示。")
    rule = make_rule(trigger_terms=["军功"])

    assert match(cluster, [], [rule]) == []
