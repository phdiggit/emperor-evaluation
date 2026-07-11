from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.dev import retrieval_v3_expected_event_reconciliation as tool


def event() -> dict:
    return {
        "record_type": "expected_event",
        "event_inventory_code": "EEI-EAST-TURK",
        "emperor_name": "李世民",
        "object_id": 7,
        "object_name": "李靖",
        "event_label": "受诏统军出击东突厥并完成灭国俘可汗的北伐",
        "direction": "positive",
        "importance": "major",
        "domain": "military",
        "event_anchor_terms": ["东突厥", "颉利"],
        "duty_anchor_terms": ["行军总管", "统诸军"],
        "outcome_anchor_terms": ["颉利被擒", "东突厥平定"],
        "source_leads": [{"source_title": "旧唐书"}],
    }


def claim(*, group: str = "CEG-1", summary: str = "李靖为行军总管，统军出击东突厥。", outcome: str = "") -> dict:
    return {
        "claim_key": "CLMK-1",
        "emperor_name": "李世民",
        "object_id": 7,
        "object_name": "李靖",
        "action_type": "任命统军",
        "fact_type": "appointment",
        "office_or_domain": "定襄道行军总管",
        "outcome": outcome,
        "outcome_support": "direct" if outcome else "unknown",
        "claim_summary": summary,
        "event_group_keys": [group],
        "evidence": [{"source_slice_ref": "OSS-1"}],
    }


def source_slice(text: str = "大军追击颉利并将其擒获，东突厥遂平。") -> dict:
    return {
        "slice_hash": "SLICE-1",
        "object_id": 7,
        "object_name": "李靖",
        "document_code": "DOC-1",
        "source_title": "旧唐书",
        "source_slice_ref": "OSS-RESULT",
        "slice_text_preview": text,
    }


def test_lexical_score_prefers_explicit_outcome_group() -> None:
    weak = tool.lexical_score(event(), "李靖为行军总管出征东突厥。")
    strong = tool.lexical_score(event(), "李靖为行军总管出征东突厥，颉利被擒，东突厥平定。")

    assert strong > weak


def test_build_workitems_attaches_nearest_groups_and_cached_slices() -> None:
    workitems = tool.build_workitems(
        [event()],
        [claim(), claim(group="CEG-2", summary="无关任官材料")],
        [source_slice(), source_slice("普通人物介绍")],
        max_groups=2,
        max_slices=1,
    )

    assert len(workitems) == 1
    event_row = workitems[0]["events"][0]
    assert event_row["candidate_groups"][0]["group_key"] == "CEG-1"
    assert event_row["candidate_cached_slices"][0]["source_slice_ref"] == "OSS-RESULT"


def reconciliation_event() -> dict:
    workitem = tool.build_workitems([event()], [claim()], [source_slice()])[0]
    return workitem["events"][0]


def test_validate_already_covered_requires_cited_complete_group() -> None:
    candidate = reconciliation_event()
    row = {
        "event_inventory_code": "EEI-EAST-TURK",
        "decision": "already_covered",
        "has_appointment": True,
        "has_duty": True,
        "has_outcome": True,
        "same_event": True,
        "group_keys": ["CEG-1"],
        "claim_keys": ["CLMK-1"],
        "source_slice_refs": [],
        "missing_facets": [],
        "confidence": "high",
        "review_note": "同组 claim 已覆盖完整事实链。",
    }

    validated = tool.validate_result(row, candidate)

    assert validated["decision"] == "already_covered"
    assert validated["write_db"] is False


def test_validate_reextract_requires_actual_cached_slice_ref() -> None:
    candidate = reconciliation_event()
    row = {
        "event_inventory_code": "EEI-EAST-TURK",
        "decision": "reextract_cached_source",
        "has_appointment": True,
        "has_duty": True,
        "has_outcome": False,
        "same_event": True,
        "group_keys": ["CEG-1"],
        "claim_keys": ["CLMK-1"],
        "source_slice_refs": [],
        "missing_facets": ["outcome"],
        "confidence": "high",
        "review_note": "缓存切片含结果。",
    }

    with pytest.raises(tool.ExpectedEventReconciliationError, match="cached source refs"):
        tool.validate_result(row, candidate)


def write_merge_fixture(tmp_path: Path, *, decision: str) -> None:
    workitem = tool.build_workitems([event()], [claim()], [source_slice()])[0]
    (tmp_path / "patches").mkdir(parents=True)
    (tmp_path / "workitems.jsonl").write_text(json.dumps(workitem, ensure_ascii=False) + "\n", encoding="utf-8")
    patch = {
        "event_inventory_code": "EEI-EAST-TURK",
        "decision": decision,
        "has_appointment": decision != "fetch_missing_source",
        "has_duty": decision != "fetch_missing_source",
        "has_outcome": decision == "already_covered",
        "same_event": decision != "fetch_missing_source",
        "group_keys": ["CEG-1"] if decision != "fetch_missing_source" else [],
        "claim_keys": ["CLMK-1"] if decision != "fetch_missing_source" else [],
        "source_slice_refs": ["OSS-RESULT"] if decision == "reextract_cached_source" else [],
        "missing_facets": (
            []
            if decision == "already_covered"
            else (["outcome"] if decision == "reextract_cached_source" else ["appointment", "duty", "outcome", "same_event"])
        ),
        "confidence": "high",
        "review_note": "有限结论。",
    }
    (tmp_path / "patches" / "task.jsonl").write_text(json.dumps(patch, ensure_ascii=False) + "\n", encoding="utf-8")


def test_gate_stops_when_existing_source_resolution_rate_is_too_low(tmp_path: Path) -> None:
    write_merge_fixture(tmp_path, decision="fetch_missing_source")

    _, report = tool.merge_results(tmp_path, min_existing_source_resolution_rate=0.5)

    assert report["ok"] is True
    assert report["existing_source_resolution_rate"] == 0.0
    assert report["gate_passed"] is False
    assert report["progress_allowed"] is False
    assert report["next_action"] == "stop_and_optimize_reconciliation"


def test_gate_passes_for_cached_source_reextraction(tmp_path: Path) -> None:
    write_merge_fixture(tmp_path, decision="reextract_cached_source")

    _, report = tool.merge_results(tmp_path, min_existing_source_resolution_rate=0.5)

    assert report["existing_source_resolution_rate"] == 1.0
    assert report["gate_passed"] is True


def test_repair_verification_does_not_count_repeated_reextraction_as_resolved(tmp_path: Path) -> None:
    write_merge_fixture(tmp_path, decision="reextract_cached_source")

    _, report = tool.merge_results(
        tmp_path,
        min_existing_source_resolution_rate=0.5,
        gate_mode="repair_verification",
    )

    assert report["gate_metric"] == "verified_coverage_rate"
    assert report["actionable_without_new_source_rate"] == 1.0
    assert report["verified_coverage_rate"] == 0.0
    assert report["existing_source_resolution_rate"] == 0.0
    assert report["gate_passed"] is False
    assert report["progress_allowed"] is False


def test_repair_verification_passes_only_for_actual_coverage(tmp_path: Path) -> None:
    write_merge_fixture(tmp_path, decision="already_covered")

    _, report = tool.merge_results(
        tmp_path,
        min_existing_source_resolution_rate=0.5,
        gate_mode="repair_verification",
    )

    assert report["verified_coverage_rate"] == 1.0
    assert report["gate_passed"] is True
    assert report["next_action"] == "continue_verified_repairs"


def test_repair_verification_counts_fact_complete_event_group_rebuild(tmp_path: Path) -> None:
    workitem = tool.build_workitems([event()], [claim()], [source_slice()])[0]
    workitem["events"][0]["allowed_group_keys"].append("CEG-2")
    workitem["events"][0]["allowed_claim_keys"].append("CLMK-2")
    (tmp_path / "patches").mkdir(parents=True)
    (tmp_path / "workitems.jsonl").write_text(json.dumps(workitem, ensure_ascii=False) + "\n", encoding="utf-8")
    patch = {
        "event_inventory_code": "EEI-EAST-TURK",
        "decision": "rebuild_event_group",
        "has_appointment": True,
        "has_duty": True,
        "has_outcome": True,
        "same_event": True,
        "group_keys": ["CEG-1", "CEG-2"],
        "claim_keys": ["CLMK-1", "CLMK-2"],
        "source_slice_refs": [],
        "missing_facets": [],
        "confidence": "high",
        "review_note": "事实链完整但分属两个事件组。",
    }
    (tmp_path / "patches" / "task.jsonl").write_text(json.dumps(patch, ensure_ascii=False) + "\n", encoding="utf-8")

    _, report = tool.merge_results(
        tmp_path,
        min_existing_source_resolution_rate=0.5,
        gate_mode="repair_verification",
    )

    assert report["verified_coverage_rate"] == 1.0
    assert report["gate_passed"] is True


def test_merge_can_consume_capacity_retry_patch_root(tmp_path: Path) -> None:
    write_merge_fixture(tmp_path, decision="fetch_missing_source")
    original_patch = next((tmp_path / "patches").glob("*.jsonl"))
    retry_root = tmp_path / "retry-patches"
    retry_root.mkdir()
    original_patch.replace(retry_root / original_patch.name)

    _, report = tool.merge_results(
        tmp_path,
        min_existing_source_resolution_rate=0.5,
        patch_roots=[retry_root],
    )

    assert report["ok"] is True
    assert report["missing_event_codes"] == []


def test_runtime_stage_uses_one_object_tasks_with_two_workers() -> None:
    runtime = tool.agent_runtime_config.resolve_agent_stage("v3_expected_event_reconciliation")

    assert runtime["model"] == "gpt-5.6-luna"
    assert runtime["batch_size"] == 1
    assert runtime["max_workers"] == 2


def test_local_source_cache_rows_can_overlay_newly_fetched_slices(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    row = {
        "quote_hash": "HASH-1",
        "person_name": "李靖",
        "document_cache_code": "OSD-1",
        "source_title": "舊唐書/卷67",
        "slice_cache_code": "OSS-NEW",
        "raw_text": "李靖统军灭东突厥，颉利被擒。",
    }
    (cache_root / "mention_slices.jsonl").write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    rows = tool.local_source_cache_rows(cache_root)

    assert rows == [
        {
            "slice_hash": "HASH-1",
            "object_id": None,
            "object_name": "李靖",
            "document_code": "OSD-1",
            "source_title": "舊唐書/卷67",
            "source_url": "",
            "source_slice_ref": "OSS-NEW",
            "slice_text_preview": "李靖统军灭东突厥，颉利被擒。",
            "source_cache_root": str(cache_root),
        }
    ]


def test_local_extracted_claim_rows_can_overlay_repair_claims(tmp_path: Path) -> None:
    result_path = tmp_path / "judge.json"
    result_path.write_text(
        json.dumps(
            {
                "claims": [
                    {
                        "claim_code": "CLM-NEW",
                        "emperor_name": "李世民",
                        "object_name": "李绩",
                        "claim_summary": "李绩在诺真水大破薛延陀。",
                        "source_slice_refs": ["OSS-1"],
                        "evidence_spans": [{"source_slice_ref": "OSS-1", "text": "大破之"}],
                        "fact_payload": {
                            "action_type": "战役",
                            "office_or_domain": "诺真水",
                            "outcome": "大破薛延陀",
                        },
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    rows = tool.local_extracted_claim_rows(result_path)

    assert rows[0]["claim_key"] == "CLM-NEW"
    assert rows[0]["outcome_support"] == "direct"
    assert rows[0]["event_group_keys"][0].startswith("CEG-REX-")
    assert rows[0]["evidence"][0]["quote_preview"] == "大破之"


def test_reconciliation_is_read_only_and_does_not_use_legacy_contract_tables() -> None:
    source = Path(tool.__file__).read_text(encoding="utf-8")

    assert "target_rule_requirements" not in source
    assert "retrieval_intents" not in source
    assert "insert into" not in source.lower()
    assert "scoring_allowed" in source
