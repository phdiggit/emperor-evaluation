from emperor_v4.evaluation.third_item_current_settlement import (
    _preserve_mapping_order_if_equal,
    _replace_non_public_preserving_public,
)


def test_scoring_sync_preserves_only_the_existing_public_projection():
    current = {
        "score": 1,
        "public_basis": "正式视图原有公开说明",
        "nested": {
            "value": 1,
            "public_boundary": "正式视图原有边界",
        },
        "steps": [
            {
                "credit": 0.5,
                "public_note": "正式视图原有步骤说明",
            }
        ],
    }
    source = {
        "score": 2,
        "public_basis": "另一投影的公开说明不得迁入",
        "nested": {
            "value": 2,
            "public_boundary": "另一投影的边界不得迁入",
            "public_extra": "正式视图不存在的公开字段不得新增",
        },
        "steps": [
            {
                "credit": 1.0,
                "public_note": "另一投影的步骤说明不得迁入",
            }
        ],
    }

    synchronized = _replace_non_public_preserving_public(current, source)

    assert list(synchronized) == ["score", "public_basis", "nested", "steps"]
    assert synchronized == {
        "score": 2,
        "public_basis": "正式视图原有公开说明",
        "nested": {
            "value": 2,
            "public_boundary": "正式视图原有边界",
        },
        "steps": [
            {
                "credit": 1.0,
                "public_note": "正式视图原有步骤说明",
            }
        ],
    }


def test_c_profile_rebuild_keeps_order_when_mapping_is_semantically_equal():
    current = {"PROPORTIONATE_RETURN": 1, "LOW_RETURN": 2}
    rebuilt = {"LOW_RETURN": 2, "PROPORTIONATE_RETURN": 1}

    preserved = _preserve_mapping_order_if_equal(current, rebuilt)

    assert list(preserved) == ["PROPORTIONATE_RETURN", "LOW_RETURN"]
    assert _preserve_mapping_order_if_equal(current, {"LOW_RETURN": 3}) == {
        "LOW_RETURN": 3
    }
