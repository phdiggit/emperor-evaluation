"""Synthetic lifecycle invariants and live source/view parity; no frozen rulings."""
import copy
import importlib

import pytest

from emperor_v4.evaluation.profile_record_integrity import ROLES, verify_current_records


def sample(axis="C2"):
    parent = {"parent_id": "P1", "capability_episode_ref": "episode-one",
              "direction": "POSITIVE", "intensity": "MI2", "material_intensity": "MI2"}
    record = {"ruler_id": "synthetic-ruler", "ruler_name": "合成对象", "axis_grade": "G3",
              "position": "MID", "radar_value": 65, "score_100": 65,
              "parent_chains": [parent], "representative_parent_ids": ["P1"],
              "axis_relevance_check": {"scoring_parent_refs": ["P1"]}}
    if axis == "M1":
        record["m1_role_projection"] = {"items": [{"capability_episode_ref": "episode-one",
             "m1_role_class": "STRATEGIC_DIRECTION", "direction": "MIXED"}]}
        record["m1_role_distribution"] = {"unique_episode_count": 1, **{
            role: {"episode_count": int(role == "STRATEGIC_DIRECTION"),
                   "episode_refs": ["episode-one"] if role == "STRATEGIC_DIRECTION" else []}
            for role in ROLES}}
    return {"axis_code": axis, "record_count": 1, "records": [record]}


def test_source_alias_is_traceable_but_not_another_scoring_parent():
    payload = sample()
    payload["records"][0]["parent_chains"][0]["source_alias_parent_ids"] = ["old-source"]
    verify_current_records(payload)


@pytest.mark.parametrize("defect", ["episode", "alias", "disposition", "suppression", "score", "intensity"])
def test_rejects_conflicting_current_fields(defect):
    payload = sample()
    row = payload["records"][0]
    if defect == "episode":
        duplicate = copy.deepcopy(row["parent_chains"][0])
        duplicate["parent_id"] = "P2"
        row["parent_chains"].append(duplicate)
    elif defect == "alias":
        row["parent_chains"][0]["source_alias_parent_ids"] = ["P1"]
    elif defect == "disposition":
        row["non_scoring_observations"] = [{"source_parent_ref": "P1", "reason": "轴外",
                                           "source_refs": ["source"]}]
    elif defect == "suppression":
        row["directional_strength_balance_review"] = {"suppression_parent_ids": ["removed-parent"]}
    elif defect == "score":
        row["radar_value"] += 1
    else:
        row["parent_chains"][0]["material_intensity"] = "MI3"
    with pytest.raises(AssertionError):
        verify_current_records(payload)


def test_military_stages_are_kept_inside_one_cycle():
    payload = sample("M1")
    item = payload["records"][0]["m1_role_projection"]["items"][0]
    item["phase_evidence"] = [
        {"m1_role_class": "STRATEGIC_DIRECTION", "direction": "NEGATIVE"},
        {"m1_role_class": "OPERATIONAL_COORDINATION", "direction": "POSITIVE"},
    ]
    verify_current_records(payload)


def test_nominal_authorization_cannot_carry_personal_military_failure():
    payload = sample("M1")
    row = payload["records"][0]
    row["m1_role_projection"]["items"][0].update(m1_role_class="NOMINAL_AUTHORIZATION", direction="NEGATIVE")
    row["m1_role_distribution"]["STRATEGIC_DIRECTION"] = {"episode_count": 0, "episode_refs": []}
    row["m1_role_distribution"]["NOMINAL_AUTHORIZATION"] = {"episode_count": 1, "episode_refs": ["episode-one"]}
    with pytest.raises(AssertionError, match="nominal role"):
        verify_current_records(payload)


def test_role_distribution_must_match_current_projection():
    payload = sample("M1")
    payload["records"][0]["m1_role_distribution"]["unique_episode_count"] = 2
    with pytest.raises(AssertionError, match="stale role count"):
        verify_current_records(payload)


def test_cross_calibration_must_reference_current_axis_records():
    payload = sample()
    payload["records"][0]["horizontal_calibration"] = {
        "decision_basis": "已核对任务与本人归责", "scores_used_as_formula": False,
        "comparators": [{"ruler_id": "missing-a", "comparison": "相邻档"},
                        {"ruler_id": "missing-b", "comparison": "同档"}]}
    with pytest.raises(AssertionError):
        verify_current_records(payload)


@pytest.mark.parametrize("axis", ["m1", "c2", "c3", "m4"])
def test_current_formal_records_and_views(axis):
    module = importlib.import_module(f"emperor_v4.evaluation.profile_{axis}_verifier")
    module.verify()
