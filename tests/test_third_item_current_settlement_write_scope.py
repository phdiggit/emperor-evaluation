import json

import pytest

from emperor_v4.evaluation.third_item_current_settlement import (
    _preserve_mapping_order_if_equal,
    _replace_non_public_preserving_public,
    _validate_overlapping_subject_windows,
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


def _shared_window_payloads():
    scope = {axis: f"synthetic {axis}" for axis in ("A", "B", "C", "D")}
    reviews = {
        "li": {
            "review_id": "synthetic-shared-window",
            "status": "REVIEWED_SHARED_POWER_SINGLE_ACCOUNTING_OWNER",
            "component_scope": scope,
        },
        "wu": {
            "review_id": "synthetic-shared-window",
            "status": "REVIEWED_SHARED_POWER_SINGLE_ACCOUNTING_OWNER",
            "component_scope": scope,
        },
    }
    windows = {
        "li": [{"start": 1, "end": 2, "status": "ACCOUNTING_OWNER"}],
        "wu": [{"start": 1, "end": 2, "status": "NON_ACCOUNTING_OWNER"}],
    }
    rows = [
        {
            "ruler_id": "li",
            "ruler_name": "合成甲",
            "active_rule_windows": windows["li"],
            "overlapping_subject_window_review": reviews["li"],
        },
        {
            "ruler_id": "wu",
            "ruler_name": "合成乙",
            "active_rule_windows": windows["wu"],
            "overlapping_subject_window_review": reviews["wu"],
        },
    ]
    return {component: {"records": json.loads(json.dumps(rows))} for component in ("AB", "C", "D", "result_credit")}


def test_shared_power_window_requires_one_synchronized_component_review(tmp_path):
    path = tmp_path / "config/common/canonical-ruler-pool.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "ruler_id": "li",
                        "ruler_name": "合成甲",
                        "pool_status": "INCLUDED",
                        "actual_power_window": "1—2年与合成乙共享权力",
                        "actual_power_window_adjudication": {
                            "third_item_overlap_status": "COMPONENT_REVIEW_COMPLETE",
                            "overlap_review_id": "synthetic-shared-window",
                            "overlapping_ruler_ids": ["li", "wu"],
                        },
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    payloads = _shared_window_payloads()
    _validate_overlapping_subject_windows(tmp_path, payloads)
    payloads["D"]["records"][1].pop("overlapping_subject_window_review")
    with pytest.raises(ValueError, match="统一review_id"):
        _validate_overlapping_subject_windows(tmp_path, payloads)
