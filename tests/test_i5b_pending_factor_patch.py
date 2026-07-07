from __future__ import annotations

from scripts.dev import i5b_pending_factor_patch as tool
from scripts.dev.rule_material_policy import policy_map_from_rows


def policy_map() -> dict:
    return policy_map_from_rows(
        [
            {
                "item_code": "I5B",
                "rule_code": "appointment_delegation",
                "policy_code": "person_material_policy",
                "allowed_scoring_roles": ["delegated_actor", "misdelegated_actor"],
                "context_roles": ["source_context"],
                "disallowed_scored_obj_types": ["mechanism"],
            },
            {
                "item_code": "I5B",
                "rule_code": "tolerate_talent",
                "policy_code": "single_person_chain_policy",
                "allowed_scoring_roles": ["protected_talent", "harmed_talent"],
                "context_roles": ["event_context", "group_context", "mechanism_context", "source_context"],
                "disallowed_scored_obj_types": ["event", "group", "mechanism"],
            },
        ]
    )


def batch() -> dict[str, object]:
    return {
        "batch_id": "pending_material_batch_01",
        "groups": [
            {
                "emperor": "刘彻",
                "rule_code": "appointment_delegation",
                "materials": [
                    {
                        "emperor": "刘彻",
                        "rule_code": "appointment_delegation",
                        "obj_src_id": 2304,
                        "direction": "positive",
                        "obj_name": "儿宽",
                        "factor_patch_template": {
                            "side": "positive",
                            "factor_keys": ["appointment_importance", "source_factor"],
                            "factor_refs": {"appointment_importance": {"label": ""}, "source_factor": {"label": ""}},
                            "factor_option_candidates": {
                                "appointment_importance": [
                                    {"label": "有实际职责的任用、信任或单一领域真实授权。", "value_num": "1"}
                                ],
                                "source_factor": [{"label": "基础史源", "value_num": "1"}],
                            },
                        },
                    }
                ],
            }
        ],
    }


def valid_patch_row() -> dict[str, object]:
    return {
        "obj_src_id": 2304,
        "target_action": "score",
        "side": "positive",
        "factor_refs": {
            "appointment_importance": {"label": "有实际职责的任用、信任或单一领域真实授权。"},
            "source_factor": {"label": "基础史源"},
        },
        "patch_note": "按材料补入常规任用授权因子。",
    }


def test_build_report_accepts_valid_score_patch() -> None:
    report = tool.build_report(batch(), [valid_patch_row()], policies=policy_map())

    assert report["ok"] is True
    assert report["error_count"] == 0
    assert report["action_counts"] == {"score": 1}


def test_build_report_flags_missing_patch_rows() -> None:
    report = tool.build_report(batch(), [], policies=policy_map())

    assert report["ok"] is False
    assert report["issues"][0]["status"] == "missing_patch_row"


def test_build_report_flags_unknown_factor_label() -> None:
    row = valid_patch_row()
    row["factor_refs"]["appointment_importance"]["label"] = "不存在的档位"

    report = tool.build_report(batch(), [row], policies=policy_map())

    assert report["ok"] is False
    assert report["issues"][0]["status"] == "unknown_factor_label"
    assert report["issues"][0]["factor"] == "appointment_importance"


def test_supporting_only_requires_patch_note() -> None:
    report = tool.build_report(batch(), [{"obj_src_id": 2304, "target_action": "supporting_only"}], policies=policy_map())

    assert report["ok"] is False
    assert report["issues"][0]["status"] == "missing_patch_note"


def test_score_requires_non_empty_factor_template() -> None:
    raw_batch = batch()
    raw_batch["groups"][0]["materials"][0]["factor_patch_template"]["factor_keys"] = []
    raw_batch["groups"][0]["materials"][0]["factor_patch_template"]["factor_refs"] = {}
    raw_batch["groups"][0]["materials"][0]["factor_patch_template"]["factor_option_candidates"] = {}

    report = tool.build_report(
        raw_batch,
        [{"obj_src_id": 2304, "target_action": "score", "side": "positive", "factor_refs": {}}],
        policies=policy_map(),
    )

    assert report["ok"] is False
    assert report["issues"][0]["status"] == "score_without_factor_template"


def test_score_rejects_disallowed_scored_obj_type() -> None:
    raw_batch = batch()
    raw_batch["groups"][0]["rule_code"] = "tolerate_talent"
    raw_batch["groups"][0]["materials"][0]["rule_code"] = "tolerate_talent"
    raw_batch["groups"][0]["materials"][0]["obj_type"] = "event"

    report = tool.build_report(raw_batch, [valid_patch_row()], policies=policy_map())

    assert report["ok"] is False
    assert report["issues"][0]["status"] == "scored_obj_type_disallowed"
    assert report["issues"][0]["obj_type"] == "event"
