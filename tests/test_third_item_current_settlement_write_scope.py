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


def test_c_major_result_summary_counts_chains_and_separates_capability():
    from emperor_v4.evaluation.third_item_current_settlement import _current_c_task_basis_reason

    row = {
        "strategy_chains": [{
            "chain_id": "synthetic-pressure",
            "source_event_refs": ["phase-a", "phase-b", "phase-c", "phase-d"],
            "major_system_failure": True,
        }],
        "major_system_failure_refs": ["phase-a", "phase-b", "phase-c", "phase-d"],
        "capability_only_strategy_chains": [{
            "chain_id": "synthetic-capability", "major_system_success": True,
        }],
    }
    text = _current_c_task_basis_reason(row, row["major_system_failure_refs"], 0, {})
    assert "当前战略链重大体系胜绩0项、重大体系失败1项" in text
    assert "能力专用战略链胜绩1项、重大失败0项" in text


def test_changed_a_endpoints_do_not_restore_retired_atomic_scores(monkeypatch, tmp_path):
    from copy import deepcopy
    from emperor_v4.evaluation import third_item_current_settlement as settlement
    from emperor_v4.evaluation import five_dynasties_third_item as rendering

    # Independent synthetic endpoints exercise a writer transition, not ruler results.
    row = {
        "ruler_id": "synthetic", "ruler_name": "合成对象",
        "control_contribution_type": "INHERITED_ONLY",
        "axes": {name: {"axis_points": 99, "reason": name + "合成事实"}
                 for name in ("A1", "A2", "B4")},
    }
    adjudication = {
        "ruler_id": "synthetic", "ruler_name": "合成对象", "score_ready": True,
        "axes": {name: {"start_grade": 2, "end_grade": 2, "objective_delta": 0}
                 for name in ("A1", "A2")},
        "A120_points": 0, "B80_adjudication": {"B80_points": 0},
    }
    payloads = {settlement.AB_PATH: {"records": [row]},
                settlement.RESULT_CREDIT_ADJUDICATIONS_PATH: {"records": [adjudication]},
                settlement.AB_HANDOFF_ADJUDICATIONS_PATH: {}}
    monkeypatch.setattr(settlement, "_load", lambda path: payloads[path.relative_to(tmp_path)])
    monkeypatch.setattr(settlement, "_load_a_axis_narrative_adjudications", lambda root: {})
    # Scoring and evidence validation have separate tests; isolate the write boundary.
    for name in ("_validate_result_credit_contract", "_validate_ab_control_contribution_contract",
                 "_validate_ab_axis_narratives"):
        monkeypatch.setattr(settlement, name, lambda *args, **kwargs: None)
    monkeypatch.setattr(settlement, "_decompose_a120_axis", lambda *args: (0, 0))
    monkeypatch.setattr(settlement, "load_ruler_polities", lambda root: {})
    saved = []
    monkeypatch.setattr(settlement, "write_json", lambda path, payload, **kwargs: saved.append(deepcopy(payload)))
    monkeypatch.setattr(rendering, "_render_formal_markdown", lambda *args: "")
    monkeypatch.setattr(settlement, "_write_text_atomic", lambda *args: None)

    settlement._synchronize_current_ab_view(tmp_path)
    settlement._validate_current_ab_score_fields(saved[-1])
    for name in ("A1", "A2"):
        assert row["axes"][name]["end"] == settlement._a_axis_state_fields(name, adjudication["axes"][name])["end"]
        assert "axis_points" not in row["axes"][name]
    first = saved[-1]
    settlement._synchronize_current_ab_view(tmp_path)
    assert saved[-1] == first


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
