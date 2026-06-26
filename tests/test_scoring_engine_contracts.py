from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from shared.scoring_engine_contracts import (  # noqa: E402
    ContractValidationError,
    EvidenceProfile,
    FormalGradeResult,
    NoOverridePolicy,
    ScorePublicationResult,
    ScoreRange,
    SubitemProfile,
    validate_interface_bundle,
)


def sample_subitem() -> SubitemProfile:
    return SubitemProfile(
        subitem_id="contract_fixture_subitem",
        subitem_name="Contract Fixture Subitem",
        score_cap="45",
        grade_scale_version="v3.2-nine-grade",
        algorithm_version="contract-fixture-algorithm-v1",
        g8_gate_status="released_for_contract_fixture",
        g9_publication_status="publication_fixture_only",
    )


def sample_evidence() -> EvidenceProfile:
    return EvidenceProfile(
        person_id="contract_fixture_person",
        subitem_id="contract_fixture_subitem",
        positive_signal_profile={"coverage": "fixture"},
        negative_signal_profile={"boundary": "none"},
        confidence="fixture",
        cross_item_split_signals=("fixture_split_reviewed",),
        source_traceability_status="fixture_traceable",
    )


def sample_grade() -> FormalGradeResult:
    return FormalGradeResult(
        person_id="contract_fixture_person",
        subitem_id="contract_fixture_subitem",
        formal_grade="contract_fixture_grade",
        score_range=ScoreRange("10", "20"),
        candidate_value="15",
        algorithm_version="contract-fixture-algorithm-v1",
        deterministic_rerun_key="contract-fixture-rerun-key",
    )


def sample_publication() -> ScorePublicationResult:
    return ScorePublicationResult(
        person_id="contract_fixture_person",
        subitem_id="contract_fixture_subitem",
        formal_score_value="15",
        subitem_rank=1,
        publication_gate="G9",
        publication_scope="subitem_internal_fixture_only",
    )


def test_interface_bundle_serializes_contract_objects_without_total_or_leaderboard_release() -> None:
    bundle = validate_interface_bundle(
        subitem=sample_subitem(),
        evidence=sample_evidence(),
        formal_grade=sample_grade(),
        publication=sample_publication(),
    )

    assert bundle["subitem_profile"]["score_cap"] == "45"
    assert bundle["formal_grade_result"]["candidate_value"] == "15"
    assert bundle["formal_grade_result"]["no_override_policy"] == {
        "person_specific_override_allowed": False,
        "manual_final_grade_allowed": False,
        "manual_final_score_allowed": False,
    }
    assert bundle["publication_result"]["publication_gate"] == "G9"
    assert bundle["stage_or_final_total_table_released"] is False
    assert bundle["cross_subitem_leaderboard_released"] is False


def test_score_range_rejects_out_of_range_candidate_and_cap_overflow() -> None:
    subitem = sample_subitem()

    with pytest.raises(ContractValidationError, match="inside score_range"):
        FormalGradeResult(
            person_id="contract_fixture_person",
            subitem_id="contract_fixture_subitem",
            formal_grade="contract_fixture_grade",
            score_range=ScoreRange("10", "20"),
            candidate_value="25",
            algorithm_version="contract-fixture-algorithm-v1",
            deterministic_rerun_key="contract-fixture-rerun-key",
        ).validate(subitem=subitem)

    with pytest.raises(ContractValidationError, match="must not exceed score_cap"):
        ScoreRange("10", "50").validate(score_cap=subitem.score_cap)


def test_no_override_policy_rejects_manual_or_person_specific_override() -> None:
    for policy in (
        NoOverridePolicy(person_specific_override_allowed=True),
        NoOverridePolicy(manual_final_grade_allowed=True),
        NoOverridePolicy(manual_final_score_allowed=True),
    ):
        with pytest.raises(ContractValidationError):
            policy.validate()


def test_publication_requires_g9_and_blocks_total_or_cross_subitem_outputs() -> None:
    subitem = sample_subitem()
    grade = sample_grade()

    with pytest.raises(ContractValidationError, match="requires G9"):
        ScorePublicationResult(
            person_id="contract_fixture_person",
            subitem_id="contract_fixture_subitem",
            formal_score_value="15",
            subitem_rank=1,
            publication_gate="G8",
            publication_scope="subitem_internal_fixture_only",
        ).validate(formal_grade=grade, subitem=subitem)

    with pytest.raises(ContractValidationError, match="stage/final total"):
        ScorePublicationResult(
            person_id="contract_fixture_person",
            subitem_id="contract_fixture_subitem",
            formal_score_value="15",
            subitem_rank=1,
            publication_gate="G9",
            publication_scope="subitem_internal_fixture_only",
            stage_or_final_total_table_released=True,
        ).validate(formal_grade=grade, subitem=subitem)

    with pytest.raises(ContractValidationError, match="cross-subitem leaderboard"):
        ScorePublicationResult(
            person_id="contract_fixture_person",
            subitem_id="contract_fixture_subitem",
            formal_score_value="15",
            subitem_rank=1,
            publication_gate="G9",
            publication_scope="subitem_internal_fixture_only",
            cross_subitem_leaderboard_released=True,
        ).validate(formal_grade=grade, subitem=subitem)


def test_bundle_rejects_mismatched_person_or_subitem() -> None:
    with pytest.raises(ContractValidationError, match="formal grade person_id"):
        validate_interface_bundle(
            subitem=sample_subitem(),
            evidence=sample_evidence(),
            formal_grade=FormalGradeResult(
                person_id="other_person",
                subitem_id="contract_fixture_subitem",
                formal_grade="contract_fixture_grade",
                score_range=ScoreRange("10", "20"),
                candidate_value="15",
                algorithm_version="contract-fixture-algorithm-v1",
                deterministic_rerun_key="contract-fixture-rerun-key",
            ),
        )

    with pytest.raises(ContractValidationError, match="evidence subitem_id"):
        validate_interface_bundle(
            subitem=sample_subitem(),
            evidence=EvidenceProfile(
                person_id="contract_fixture_person",
                subitem_id="other_subitem",
                positive_signal_profile={},
                negative_signal_profile={},
                confidence="fixture",
                cross_item_split_signals=(),
                source_traceability_status="fixture_traceable",
            ),
            formal_grade=sample_grade(),
        )
