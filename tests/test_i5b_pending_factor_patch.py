from __future__ import annotations

from scripts.dev import i5b_pending_factor_patch as tool


def batch() -> dict[str, object]:
    return {
        "batch_id": "pending_material_batch_01",
        "groups": [
            {
                "emperor": "刘彻",
                "rule_code": "appointment_trust",
                "materials": [
                    {
                        "emperor": "刘彻",
                        "rule_code": "appointment_trust",
                        "obj_src_id": 2304,
                        "direction": "positive",
                        "obj_name": "儿宽",
                        "factor_patch_template": {
                            "side": "positive",
                            "factor_keys": ["trust_depth", "source_factor"],
                            "factor_refs": {"trust_depth": {"label": ""}, "source_factor": {"label": ""}},
                            "factor_option_candidates": {
                                "trust_depth": [{"label": "有实际职责的任用。", "value_num": "1"}],
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
            "trust_depth": {"label": "有实际职责的任用。"},
            "source_factor": {"label": "基础史源"},
        },
        "patch_note": "按材料补入常规任用信任因子。",
    }


def test_build_report_accepts_valid_score_patch() -> None:
    report = tool.build_report(batch(), [valid_patch_row()])

    assert report["ok"] is True
    assert report["error_count"] == 0
    assert report["action_counts"] == {"score": 1}


def test_build_report_flags_missing_patch_rows() -> None:
    report = tool.build_report(batch(), [])

    assert report["ok"] is False
    assert report["issues"][0]["status"] == "missing_patch_row"


def test_build_report_flags_unknown_factor_label() -> None:
    row = valid_patch_row()
    row["factor_refs"]["trust_depth"]["label"] = "不存在的档位"

    report = tool.build_report(batch(), [row])

    assert report["ok"] is False
    assert report["issues"][0]["status"] == "unknown_factor_label"
    assert report["issues"][0]["factor"] == "trust_depth"


def test_supporting_only_requires_patch_note() -> None:
    report = tool.build_report(batch(), [{"obj_src_id": 2304, "target_action": "supporting_only"}])

    assert report["ok"] is False
    assert report["issues"][0]["status"] == "missing_patch_note"


def test_score_requires_non_empty_factor_template() -> None:
    raw_batch = batch()
    raw_batch["groups"][0]["materials"][0]["factor_patch_template"]["factor_keys"] = []
    raw_batch["groups"][0]["materials"][0]["factor_patch_template"]["factor_refs"] = {}
    raw_batch["groups"][0]["materials"][0]["factor_patch_template"]["factor_option_candidates"] = {}

    report = tool.build_report(raw_batch, [{"obj_src_id": 2304, "target_action": "score", "side": "positive", "factor_refs": {}}])

    assert report["ok"] is False
    assert report["issues"][0]["status"] == "score_without_factor_template"


def test_score_rejects_disallowed_scored_obj_type() -> None:
    raw_batch = batch()
    raw_batch["groups"][0]["rule_code"] = "tolerate_talent"
    raw_batch["groups"][0]["materials"][0]["rule_code"] = "tolerate_talent"
    raw_batch["groups"][0]["materials"][0]["obj_type"] = "event"

    report = tool.build_report(raw_batch, [valid_patch_row()])

    assert report["ok"] is False
    assert report["issues"][0]["status"] == "scored_obj_type_disallowed"
    assert report["issues"][0]["obj_type"] == "event"
