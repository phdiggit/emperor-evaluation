from __future__ import annotations

from scripts.dev import i5b_pending_factor_patch_apply as tool


def material(obj_src_id: int, obj_name: str = "儿宽") -> dict[str, object]:
    return {
        "emperor": "刘彻",
        "rule_code": "appointment_delegation",
        "obj_src_id": obj_src_id,
        "direction": "positive",
        "obj_id": obj_src_id + 1000,
        "obj_name": obj_name,
    }


def test_apply_patch_rows_updates_scored_supporting_excluded_and_pending() -> None:
    detail = {
        "materials": [{"obj_src_id": 10, "obj_key": "1010", "obj_name": "旧材料", "side": "positive", "factor_refs": {}}],
        "covered_material_ids": [10, 11, 12, 13],
        "scored_material_ids": [10],
        "supporting_material_ids": [],
        "pending_material_ids": [11, 12, 13],
    }
    rows = [
        {
            "obj_src_id": 11,
            "target_action": "score",
            "side": "positive",
            "factor_refs": {"appointment_importance": {"label": "有实际职责的任用、信任或单一领域真实授权。"}},
            "patch_note": "可计分。",
        },
        {"obj_src_id": 12, "target_action": "supporting_only", "patch_note": "只作补源。"},
        {"obj_src_id": 13, "target_action": "exclude", "patch_note": "不属本 rule。"},
    ]

    updated = tool.apply_patch_rows_to_detail(
        detail,
        rows,
        {11: material(11), 12: material(12, "董仲舒"), 13: material(13, "霍光")},
    )

    assert updated["pending_material_ids"] == []
    assert updated["covered_material_ids"] == [10, 11, 12, 13]
    assert updated["scored_material_ids"] == [10, 11]
    assert updated["supporting_material_ids"] == [12]
    assert updated["excluded_material_ids"] == [13]
    assert [row["obj_src_id"] for row in updated["materials"]] == [10, 11]
    assert updated["materials"][1]["factor_refs"] == {
        "appointment_importance": {"label": "有实际职责的任用、信任或单一领域真实授权。"}
    }
    assert len(updated["pending_factor_patch_reviews"]) == 3


def test_apply_patch_rows_is_idempotent_for_existing_material() -> None:
    detail = {
        "materials": [{"obj_src_id": 11, "obj_key": "1011", "obj_name": "儿宽", "side": "positive", "factor_refs": {}}],
        "covered_material_ids": [11],
        "scored_material_ids": [11],
        "supporting_material_ids": [],
        "pending_material_ids": [11],
    }
    rows = [
        {
            "obj_src_id": 11,
            "target_action": "score",
            "side": "positive",
            "factor_refs": {"appointment_importance": {"label": "有实际职责的任用、信任或单一领域真实授权。"}},
            "patch_note": "更新。",
        }
    ]

    updated = tool.apply_patch_rows_to_detail(detail, rows, {11: material(11)})

    assert [row["obj_src_id"] for row in updated["materials"]] == [11]
    assert updated["pending_material_ids"] == []
    assert updated["scored_material_ids"] == [11]
