from __future__ import annotations

import json

from scripts.dev import i5b_health_check as tool


def _breakdown_report() -> dict[str, object]:
    return {
        "warnings": [],
        "emperors": [
            {
                "emperor": "刘邦",
                "score": "39.024",
                "tier": "优秀",
                "tier_band": "高段",
                "base_core": "2.754",
                "score_rate": "0.8672",
                "rules": [
                    {
                        "rule_code": "talent_discovery",
                        "result": {
                            "no_material": False,
                            "positive_signal": "1.0",
                            "negative_signal": "0.0",
                        },
                    }
                ],
            }
        ],
    }


def test_score_rows_are_derived_from_calc_breakdown() -> None:
    assert tool.score_rows_from_breakdown(_breakdown_report()) == [
        {
            "emperor": "刘邦",
            "score": "39.024",
            "tier": "优秀",
            "tier_band": "高段",
            "base_core": "2.754",
            "score_rate": "0.8672",
        }
    ]


def test_score_coverage_warns_on_core_no_material_or_zero_signal() -> None:
    breakdown = {
        "emperors": [
            {
                "emperor": "刘邦",
                "rules": [
                    {"rule_code": "talent_discovery", "result": {"no_material": True}},
                    {
                        "rule_code": "team_building",
                        "result": {"no_material": False, "positive_signal": "0.0", "negative_signal": "0.0"},
                    },
                    {"rule_code": "anti_nepotism", "result": {"no_material": True}},
                ],
            }
        ]
    }

    assert tool.score_coverage_rows_from_breakdown(breakdown) == [
        {
            "emperor": "刘邦",
            "core_no_material_rules": ["talent_discovery"],
            "core_zero_signal_rules": ["team_building"],
            "no_material_rules": ["talent_discovery", "anti_nepotism"],
            "zero_signal_rules": ["team_building"],
        }
    ]


def test_duplicate_scored_objects_warns_on_same_rule_side_object_key() -> None:
    breakdown = {
        "emperors": [
            {
                "emperor": "刘彻",
                "rules": [
                    {
                        "rule_code": "tolerate_talent",
                        "cluster": {
                            "materials": {
                                "positive": [],
                                "negative": [
                                    {"obj_key": "241", "obj_name": "司马迁", "obj_src_id": 561, "abs_score": "1.080"},
                                    {"obj_key": "241", "obj_name": "司马迁", "obj_src_id": 2308, "abs_score": "0.864"},
                                ],
                            }
                        },
                    }
                ],
            }
        ]
    }

    assert tool.duplicate_scored_object_rows_from_breakdown(breakdown) == [
        {
            "emperor": "刘彻",
            "rule_code": "tolerate_talent",
            "side": "negative",
            "obj_key": "241",
            "obj_name": "司马迁",
            "obj_src_ids": [561, 2308],
            "abs_scores": ["1.080", "0.864"],
        }
    ]


def test_signal_balance_warns_when_result_has_only_one_signal_side() -> None:
    breakdown = {
        "emperors": [
            {
                "emperor": "赵匡胤",
                "rules": [
                    {"rule_code": "talent_discovery", "result": {"positive_signal": "3.2", "negative_signal": "0"}},
                    {"rule_code": "appointment_delegation", "result": {"positive_signal": "1.1", "negative_signal": "0"}},
                ],
            }
        ]
    }

    assert tool.signal_balance_rows_from_breakdown(breakdown) == [
        {
            "emperor": "赵匡胤",
            "signal_balance": "positive_only",
            "positive_signal_sum": "4.3",
            "negative_signal_sum": "0",
        }
    ]


def test_build_health_report_combines_read_only_gates(monkeypatch) -> None:
    monkeypatch.setattr(tool, "fetch_emperors_with_results", lambda **_kwargs: ("刘邦",))
    monkeypatch.setattr(tool, "build_audit_report", lambda **_kwargs: {"ok": True, "error_count": 0, "warning_count": 2})
    monkeypatch.setattr(tool, "build_payloads", lambda **_kwargs: [{"emperor": "刘邦"}])
    monkeypatch.setattr(
        tool,
        "build_issue_summary",
        lambda _payloads: {"totals": {"units": 6, "issues": 0, "blocks": 0, "warnings": 0}},
    )
    monkeypatch.setattr(
        tool,
        "build_gap_summary_from_db",
        lambda **_kwargs: {
            "totals": {
                "total": 0,
                "non_person": 0,
                "direction_mismatch": 0,
                "missing_relation": 0,
            }
        },
    )
    monkeypatch.setattr(tool, "build_breakdown_report", lambda **_kwargs: _breakdown_report())
    monkeypatch.setattr(
        tool,
        "fetch_pending_materials",
        lambda **_kwargs: [{"emperor": "刘邦", "rule_code": "appointment_delegation", "pending_material_ids": [2278]}],
    )
    monkeypatch.setattr(tool, "build_finite_value_report", lambda **_kwargs: {"ok": True, "error_count": 0, "warning_count": 0, "issues": []})

    report = tool.build_health_report(dsn="postgresql://example", emperors=())

    assert report["ok"] is True
    assert report["emperors"] == ["刘邦"]
    assert report["gates"]["factor_consistency"]["warnings"] == 2
    assert report["gates"]["rule_evidence_unit_preview"]["details"]["units"] == 6
    assert report["gates"]["pending_materials"]["warnings"] == 1
    assert report["gates"]["score_coverage"]["warnings"] == 0
    assert report["gates"]["duplicate_scored_objects"]["warnings"] == 0
    assert report["gates"]["signal_balance"]["warnings"] == 1
    assert report["gates"]["finite_values"]["errors"] == 0
    assert report["gates"]["pending_materials"]["details"]["materials"] == 1
    markdown = tool.render_markdown(report)
    assert "| factor_consistency | true | 0 | 2 | - |" in markdown
    assert "| 刘邦 | appointment_delegation | 2278 |" in markdown
    assert "刘邦" in markdown


def test_main_can_fail_on_health_issue(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(tool, "resolve_dsn", lambda _env: "postgresql://example")
    monkeypatch.setattr(
        tool,
        "build_health_report",
        lambda **_kwargs: {
            "ok": False,
            "gates": {"fact_relation_gap": {"ok": False, "errors": 1, "warnings": 0, "details": {}}},
        },
    )
    output = tmp_path / "health.json"

    exit_code = tool.main(["--format", "json", "--output", str(output), "--fail-on-issue"])

    assert exit_code == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["ok"] is False
