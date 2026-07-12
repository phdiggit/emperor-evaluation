from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.dev import retrieval_v3_expected_event_inventory as tool


def coverage_report() -> dict:
    return {
        "item_code": "I5B",
        "rule_code": "appointment_delegation",
        "objects": [
            {
                "emperor_name": "李世民",
                "object_id": 7,
                "object_name": "李靖",
                "object_type": "臣僚",
                "source_slice_count": 10,
                "claimed_source_slice_count": 10,
                "active_claim_count": 14,
                "event_group_count": 12,
                "material_claim_count": 17,
                "candidate_count": 6,
                "binding_count": 3,
                "factor_judgment_count": 3,
                "coverage_status": "complete",
            },
            {
                "emperor_name": "李世民",
                "object_id": 8,
                "object_name": "房玄龄",
                "object_type": "臣僚",
                "coverage_status": "complete",
            },
        ],
    }


def event_patch(workitem_code: str) -> dict:
    return {
        "workitem_code": workitem_code,
        "inventory_verdict": "events_expected",
        "identity_note": "人物与目标时期相符。",
        "coverage_note": "需要回源核验主要战果。",
        "events": [
            {
                "event_label": "受命出征并灭东突厥",
                "direction": "positive",
                "importance": "major",
                "domain": "military",
                "event_anchor_terms": ["东突厥", "颉利"],
                "duty_anchor_terms": ["行军总管", "出征"],
                "outcome_anchor_terms": ["俘颉利", "灭东突厥"],
                "source_leads": [
                    {"source_title": "旧唐书·李靖传", "locator_hint": "贞观四年", "query_terms": ["颉利", "阴山"]}
                ],
                "lead_note": "只作为回源线索。",
            }
        ],
    }


def test_select_workitems_supports_object_filter_and_does_not_include_claim_text() -> None:
    rows = tool.select_workitems(coverage_report(), emperors=["李世民"], objects=["李靖"])

    assert len(rows) == 1
    assert rows[0]["object_name"] == "李靖"
    assert rows[0]["observed_pipeline"]["binding_count"] == 3
    assert rows[0]["task_boundary"]["scoring_allowed"] is False
    assert "claims" not in rows[0]


def test_select_workitems_can_prioritize_false_green_pipeline_objects() -> None:
    report = coverage_report()
    report["objects"][1]["coverage_status"] = "blocked"

    rows = tool.select_workitems(report, coverage_statuses=["complete"])

    assert [row["object_name"] for row in rows] == ["李靖"]


def test_select_workitems_can_exclude_already_inventoried_objects() -> None:
    rows = tool.select_workitems(coverage_report(), excluded_objects=["房玄龄"])

    assert [row["object_name"] for row in rows] == ["李靖"]


def test_write_tasks_uses_configured_luna_stage_and_one_object_per_task(tmp_path: Path) -> None:
    workitems = tool.select_workitems(coverage_report())
    summary = tool.write_tasks(workitems, tmp_path, batch_size=1)
    tasks = tool.read_jsonl(tmp_path / "codex_tasks.jsonl")

    assert summary["agent_runtime"]["model"] == "gpt-5.6-luna"
    assert summary["agent_runtime"]["batch_size"] == 2
    assert summary["task_count"] == 2
    assert all(task["task_kind"] == "retrieval_v3_expected_event_inventory" for task in tasks)
    assert all(task["expected_outputs"][0]["kind"] == "jsonl_patch" for task in tasks)
    prompt = Path(tasks[0]["prompt_path"]).read_text(encoding="utf-8")
    assert "相邻项切分" in prompt
    assert "检索线索" in prompt
    assert "不是史料证据" in prompt


def test_validate_patch_generates_stable_lead_only_event() -> None:
    workitem = tool.select_workitems(coverage_report(), objects=["李靖"])[0]
    validated = tool.validate_patch_row(event_patch(workitem["workitem_code"]), workitem)
    event = validated["events"][0]

    assert event["event_inventory_code"].startswith("EEI-")
    assert event["evidence_status"] == "retrieval_lead_only"
    assert event["scoring_allowed"] is False
    assert event["outcome_anchor_terms"] == ["俘颉利", "灭东突厥"]


def test_validate_patch_drops_object_name_from_event_anchors() -> None:
    workitem = tool.select_workitems(coverage_report(), objects=["李靖"])[0]
    patch = event_patch(workitem["workitem_code"])
    patch["events"][0]["event_anchor_terms"] = ["李靖", "东突厥", "颉利"]

    event = tool.validate_patch_row(patch, workitem)["events"][0]

    assert event["event_anchor_terms"] == ["东突厥", "颉利"]
    assert event["dropped_subject_anchor_terms"] == ["李靖"]


def test_validate_patch_rejects_event_without_result_anchor() -> None:
    workitem = tool.select_workitems(coverage_report(), objects=["李靖"])[0]
    patch = event_patch(workitem["workitem_code"])
    patch["events"][0]["outcome_anchor_terms"] = []

    with pytest.raises(tool.ExpectedEventInventoryError, match="outcome_anchor_terms"):
        tool.validate_patch_row(patch, workitem)


def test_validate_patch_drops_locations_from_outcome_anchors() -> None:
    workitem = tool.select_workitems(coverage_report(), objects=["李靖"])[0]
    patch = event_patch(workitem["workitem_code"])
    patch["events"][0]["outcome_anchor_terms"] = ["定襄", "阴山", "颉利被擒", "东突厥平定"]

    event = tool.validate_patch_row(patch, workitem)["events"][0]

    assert event["outcome_anchor_terms"] == ["颉利被擒", "东突厥平定"]
    assert event["dropped_non_result_outcome_terms"] == ["定襄", "阴山"]


def test_validate_patch_rejects_outcome_anchors_with_only_locations() -> None:
    workitem = tool.select_workitems(coverage_report(), objects=["李靖"])[0]
    patch = event_patch(workitem["workitem_code"])
    patch["events"][0]["outcome_anchor_terms"] = ["定襄", "阴山"]

    with pytest.raises(tool.ExpectedEventInventoryError, match="explicit result marker"):
        tool.validate_patch_row(patch, workitem)


def test_outcome_term_accepts_explicit_classical_result_verbs() -> None:
    assert tool.is_explicit_outcome_term("遂下陈留") is True
    assert tool.is_explicit_outcome_term("虏荼") is True
    assert tool.is_explicit_outcome_term("复守敖仓") is True
    assert tool.is_explicit_outcome_term("定襄") is False
    assert tool.is_explicit_outcome_term("阴山") is False


def test_validate_patch_rejects_copied_prompt_placeholder() -> None:
    workitem = tool.select_workitems(coverage_report(), objects=["李靖"])[0]
    patch = event_patch(workitem["workitem_code"])
    patch["events"][0]["event_anchor_terms"] = ["制度名", "主持"]

    with pytest.raises(tool.ExpectedEventInventoryError, match="copied prompt placeholder"):
        tool.validate_patch_row(patch, workitem)


def test_merge_requires_exactly_one_patch_per_workitem(tmp_path: Path) -> None:
    workitems = tool.select_workitems(coverage_report(), objects=["李靖"])
    tool.write_tasks(workitems, tmp_path, batch_size=1)
    task = tool.read_jsonl(tmp_path / "codex_tasks.jsonl")[0]
    patch_path = Path(task["expected_outputs"][0]["path"])
    patch_path.write_text(json.dumps(event_patch(workitems[0]["workitem_code"]), ensure_ascii=False) + "\n", encoding="utf-8")

    events, report = tool.merge_patches(tmp_path)

    assert report["ok"] is True
    assert report["event_count"] == 1
    assert events[0]["object_name"] == "李靖"


def test_merge_preserves_no_relevant_events_as_object_assessment(tmp_path: Path) -> None:
    workitems = tool.select_workitems(coverage_report(), objects=["李靖"])
    tool.write_tasks(workitems, tmp_path, batch_size=1)
    task = tool.read_jsonl(tmp_path / "codex_tasks.jsonl")[0]
    patch_path = Path(task["expected_outputs"][0]["path"])
    patch_path.write_text(
        json.dumps(
            {
                "workitem_code": workitems[0]["workitem_code"],
                "inventory_verdict": "no_relevant_events",
                "identity_note": "身份相符。",
                "events": [],
                "coverage_note": "未发现符合本 rule 的重大事件。",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    rows, report = tool.merge_patches(tmp_path)

    assert report["event_count"] == 0
    assert report["object_assessment_count"] == 1
    assert rows[0]["record_type"] == "object_assessment"
    assert rows[0]["inventory_verdict"] == "no_relevant_events"


def test_inventory_never_writes_database_or_legacy_contract_tables() -> None:
    source = Path(tool.__file__).read_text(encoding="utf-8")

    assert "target_rule_requirements" not in source
    assert "retrieval_intents" not in source
    assert "insert into" not in source.lower()
    assert "scoring_allowed" in source
