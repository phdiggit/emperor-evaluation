from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.dev import retrieval_v3_expected_event_source_refinement as tool
from scripts.dev import retrieval_v2_object_source_cache as object_cache
from scripts.dev.retrieval_v2_taskgen_preseed import source_roots_for_hint


def inventory(event_code: str, *, object_name: str = "李绩", importance: str = "major") -> dict:
    return {
        "record_type": "expected_event",
        "event_inventory_code": event_code,
        "emperor_name": "李世民",
        "object_id": 148,
        "object_name": object_name,
        "event_label": f"事件 {event_code}",
        "direction": "positive",
        "importance": importance,
        "domain": "military",
        "event_anchor_terms": ["东突厥"],
        "duty_anchor_terms": ["行军总管"],
        "outcome_anchor_terms": ["平定"],
        "source_leads": [
            {"source_title": "《旧唐书·李绩传》", "locator_hint": "《旧唐书》卷六十七贞观三年", "query_terms": ["李世勣", "东突厥"]}
        ],
    }


def result(event_code: str, *, object_name: str = "李绩", decision: str = "fetch_missing_source") -> dict:
    return {
        "event_inventory_code": event_code,
        "emperor_name": "李世民",
        "object_id": 148,
        "object_name": object_name,
        "decision": decision,
        "missing_facets": ["outcome"],
        "claim_keys": ["CLMK-1"],
        "group_keys": ["CEG-1"],
        "source_slice_refs": ["OSS-1"],
    }


def test_coalesces_multiple_events_into_one_object_package_and_cache_seed() -> None:
    packages, seeds, report = tool.build_refinement_packages(
        [inventory("EEI-1"), inventory("EEI-2")],
        [result("EEI-1"), result("EEI-2")],
    )

    assert len(packages) == 1
    assert len(seeds) == 1
    assert packages[0]["missing_event_count"] == 2
    assert packages[0]["already_checked"]["source_slice_refs"] == ["OSS-1"]
    assert "李勣" in packages[0]["aliases"]
    assert "李世勣" in packages[0]["query_terms"]
    assert seeds[0]["capture_profile"] == "expected_event_source_refinement"
    assert seeds[0]["source_document_hints"][0]["volume"] == "卷六十七"
    assert seeds[0]["source_hints"] == ["旧唐书"]
    assert len(seeds[0]["expected_event_refinement"]["search_queries"]) == 1
    query_rows = tool.object_source_cache_query_rows(seeds[0])
    assert len(query_rows) == 1
    assert query_rows[0]["query_kind"] == "expected_event_refinement"
    assert query_rows[0]["event_inventory_code"] == "EEI-1"
    assert report["fetch_event_requests"] == 2
    assert report["object_refinement_packages"] == 1
    assert report["requests_avoided_by_coalescing"] == 1
    assert report["event_direction_counts"] == {"positive": 2}
    assert report["progress_allowed"] is False


def test_non_fetch_decisions_do_not_create_source_packages() -> None:
    packages, seeds, report = tool.build_refinement_packages(
        [inventory("EEI-1")],
        [result("EEI-1", decision="already_covered")],
    )

    assert packages == []
    assert seeds == []
    assert report["fetch_event_requests"] == 0


def test_simplified_source_hint_resolves_to_canonical_wikisource_root() -> None:
    assert source_roots_for_hint("旧唐书", emp_metadata={}) == ["舊唐書"]
    assert source_roots_for_hint("资治通鉴", emp_metadata={}) == ["資治通鑑"]


def test_identity_mismatch_is_rejected() -> None:
    with pytest.raises(tool.ExpectedEventSourceRefinementError, match="identity mismatch"):
        tool.build_refinement_packages([inventory("EEI-1")], [result("EEI-1", object_name="李靖")])


def test_cli_writes_report_only_handoff(tmp_path: Path) -> None:
    inventory_path = tmp_path / "inventory.jsonl"
    results_path = tmp_path / "results.jsonl"
    gate_path = tmp_path / "gate.json"
    output_root = tmp_path / "out"
    inventory_path.write_text(json.dumps(inventory("EEI-1"), ensure_ascii=False) + "\n", encoding="utf-8")
    results_path.write_text(json.dumps(result("EEI-1"), ensure_ascii=False) + "\n", encoding="utf-8")
    gate_path.write_text(json.dumps({"progress_allowed": False}), encoding="utf-8")

    assert tool.main(
        [
            "--inventory-jsonl",
            str(inventory_path),
            "--reconciliation-jsonl",
            str(results_path),
            "--reconciliation-report-json",
            str(gate_path),
            "--output-root",
            str(output_root),
        ]
    ) == 0

    assert (output_root / "source_refinement_packages.jsonl").exists()
    assert (output_root / "object_source_cache_seeds.jsonl").exists()
    selected = tool.read_jsonl(output_root / "event_selection.jsonl")
    assert [row["event_inventory_code"] for row in selected] == ["EEI-1"]
    report = json.loads((output_root / "report.json").read_text(encoding="utf-8"))
    assert report["write_db"] is False
    assert report["enqueue_allowed"] is False
    assert report["scoring_allowed"] is False


def test_gate_bypass_is_rejected(tmp_path: Path) -> None:
    inventory_path = tmp_path / "inventory.jsonl"
    results_path = tmp_path / "results.jsonl"
    gate_path = tmp_path / "gate.json"
    inventory_path.write_text(json.dumps(inventory("EEI-1"), ensure_ascii=False) + "\n", encoding="utf-8")
    results_path.write_text(json.dumps(result("EEI-1"), ensure_ascii=False) + "\n", encoding="utf-8")
    gate_path.write_text(json.dumps({"progress_allowed": True}), encoding="utf-8")

    with pytest.raises(tool.ExpectedEventSourceRefinementError, match="not the gate bypass"):
        tool.main(
            [
                "--inventory-jsonl",
                str(inventory_path),
                "--reconciliation-jsonl",
                str(results_path),
                "--reconciliation-report-json",
                str(gate_path),
                "--output-root",
                str(tmp_path / "out"),
            ]
        )


def test_tool_is_report_only_and_does_not_use_legacy_contract_tables() -> None:
    source = Path(tool.__file__).read_text(encoding="utf-8")

    assert "target_rule_requirements" not in source
    assert "retrieval_intents" not in source
    assert "insert into" not in source.lower()
    assert "enqueue_allowed" in source
