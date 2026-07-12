from __future__ import annotations

from scripts.dev import retrieval_v3_coverage_runner as tool


def contract_row(emperor: str, rule: str = "appointment_delegation") -> dict:
    return {
        "target_code": f"T-{emperor}", "emperor_name": emperor, "item_code": "I5B",
        "contract_code": "RC-I5B", "rule_code": rule, "rule_label": rule,
        "rule_order": 10, "is_core_for_retrieval": True, "source_fingerprint": "sha",
    }


def test_contract_grouping_covers_every_emperor_rule_cell() -> None:
    rows = [contract_row("甲"), contract_row("乙"), contract_row("甲", "talent_discovery")]
    scopes = tool.group_contract(rows)

    assert [(row["rule_code"], row["emperor_count"]) for row in scopes] == [
        ("appointment_delegation", 2), ("talent_discovery", 1)]
    assert sum(row["emperor_count"] for row in scopes) == len(rows)


def test_full_report_keeps_contract_and_history_coverage_separate() -> None:
    contract = [contract_row("甲"), contract_row("乙")]
    reports = [{
        "item_code": "I5B", "rule_code": "appointment_delegation", "emperors": ["甲", "乙"],
        "counts": {"objects": 2}, "mechanical_coverage_counts": {"complete": 2},
        "convergence_counts": {"unassessed": 1, "verified": 1}, "gap_counts": {},
        "expected_event_count": 1,
        "objects": [
            {"historical_event_coverage_status": "unassessed"},
            {"historical_event_coverage_status": "assessed"},
        ],
    }]
    result = tool.build_full_report(contract, reports)

    assert result["ok"] is True
    assert result["contract_cell_count"] == 2
    assert result["covered_emperor_rule_cell_count"] == 2
    assert result["historically_assessed_object_count"] == 1
    assert result["forbidden_contract_tables_used"] is False
    assert result["controller_status"] == "complete_read_only_control_plane"
    assert result["data_converged"] is False
    assert result["side_effects_authorized"] is False
    assert result["delta_counts"] == {}
    assert result["handoff_counts"] == {}


def test_duplicate_contract_rows_do_not_create_false_missing_cells() -> None:
    contract = [contract_row("甲"), contract_row("甲")]
    reports = [{
        "item_code": "I5B", "rule_code": "appointment_delegation", "emperors": ["甲"],
        "counts": {"objects": 0}, "mechanical_coverage_counts": {}, "convergence_counts": {},
        "gap_counts": {}, "expected_event_count": 0, "objects": [],
    }]
    result = tool.build_full_report(contract, reports)

    assert result["contract_row_count"] == 2
    assert result["contract_cell_count"] == 1
    assert result["duplicate_contract_row_count"] == 1
    assert result["covered_emperor_rule_cell_count"] == 1


def test_contract_cells_include_empty_emperor_rule_scope() -> None:
    report = {
        "item_code": "I5B", "rule_code": "appointment_delegation", "emperors": ["甲", "乙"],
        "objects": [{
            "emperor_name": "甲", "mechanical_coverage_status": "complete",
            "convergence_state": "unassessed", "historical_event_coverage_status": "unassessed",
        }],
    }
    cells = tool.build_contract_cell_assessments(report)

    assert cells[0]["cell_status"] == "observed_objects"
    assert cells[1]["cell_status"] == "empty_no_objects"
    assert cells[1]["object_count"] == 0


def test_runner_source_does_not_use_forbidden_contract_tables() -> None:
    source = open(tool.__file__, encoding="utf-8").read()
    assert "target_rule_" + "requirements" not in source
    assert "retrieval_" + "intents" not in source
    assert "insert into" not in source.lower()


def test_run_contract_routes_manifest_pack_scope(monkeypatch, tmp_path) -> None:
    captured: dict = {}

    def fake_fetch_rows(**kwargs):
        captured.update(kwargs)
        return [], [], [], []

    monkeypatch.setattr(tool, "fetch_rows", fake_fetch_rows)
    monkeypatch.setattr(tool, "build_report", lambda **kwargs: {
        "item_code": "I5B", "rule_code": "appointment_delegation", "emperors": ["甲"],
        "objects": [], "counts": {}, "mechanical_coverage_counts": {},
        "convergence_counts": {}, "gap_counts": {}, "expected_event_count": 0,
    })

    tool.run_contract(
        dsn="postgresql://unused", schema_name="retrieval_v3",
        contract_rows=[contract_row("甲")], output_root=tmp_path,
        scope_inputs={"I5B__appointment_delegation": {"source_pack_codes": ["SPK-A", "SPK-B"]}},
    )

    assert captured["source_pack_codes"] == ["SPK-A", "SPK-B"]
