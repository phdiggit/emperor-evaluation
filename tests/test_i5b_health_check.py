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

    report = tool.build_health_report(dsn="postgresql://example", emperors=())

    assert report["ok"] is True
    assert report["emperors"] == ["刘邦"]
    assert report["gates"]["factor_consistency"]["warnings"] == 2
    assert report["gates"]["rule_evidence_unit_preview"]["details"]["units"] == 6
    markdown = tool.render_markdown(report)
    assert "| factor_consistency | true | 0 | 2 | - |" in markdown
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
