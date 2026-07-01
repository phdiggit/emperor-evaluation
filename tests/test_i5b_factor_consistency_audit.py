from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "scripts" / "dev" / "i5b_factor_consistency_audit.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("i5b_factor_consistency_audit_under_test", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def cluster_rows(disposition: str) -> dict[tuple[str, str], dict[str, object]]:
    return {
        ("李世民", "tolerate_talent"): {
            "emperor": "李世民",
            "rule_code": "tolerate_talent",
            "formula_code": "evidence_cluster_signal_test",
            "calc_detail": {
                "materials": [
                    {
                        "obj_name": "魏徵",
                        "obj_src_id": 17,
                        "side": "negative",
                        "factor_values": {"disposition_severity": disposition},
                        "factor_refs": {"disposition_severity": {"label": "大规模牵连"}},
                    }
                ]
            },
        }
    }


def test_high_disposition_contradicted_by_note_is_error() -> None:
    tool = load_tool()

    report = tool.build_audit_report(
        cluster_rows=cluster_rows("2.5"),
        material_notes={
            17: {
                "obj_src_note": "停婚、仆碑，后又复碑；可作谏臣身后信用反转的负向边界材料，不等同于生前杀戮或系统清洗。"
            }
        },
    )

    assert report["ok"] is False
    assert report["error_count"] == 1
    assert report["issues"][0]["code"] == "high_disposition_contradicted_by_note"
    assert "魏徵" in tool.render_markdown(report)


def test_low_disposition_with_boundary_note_is_not_flagged() -> None:
    tool = load_tool()

    report = tool.build_audit_report(
        cluster_rows=cluster_rows("0.6"),
        material_notes={
            17: {
                "obj_src_note": "停婚、仆碑，后又复碑；可作谏臣身后信用反转的负向边界材料，不等同于生前杀戮或系统清洗。"
            }
        },
    )

    assert report["ok"] is True
    assert report["issues"] == []


def test_high_disposition_without_explicit_support_is_warning_only() -> None:
    tool = load_tool()

    report = tool.build_audit_report(
        cluster_rows=cluster_rows("2.5"),
        material_notes={17: {"obj_src_note": "事实链清楚，但注释只写个案边界。"}},
    )

    assert report["ok"] is True
    assert report["error_count"] == 0
    assert report["warning_count"] == 1
    assert report["issues"][0]["code"] == "high_disposition_without_explicit_support"


def test_high_disposition_with_explicit_support_is_not_flagged() -> None:
    tool = load_tool()

    report = tool.build_audit_report(
        cluster_rows=cluster_rows("2.5"),
        material_notes={17: {"obj_src_note": "案中出现连坐与跨群体牵连，造成长期人才生态破坏。"}},
    )

    assert report["ok"] is True
    assert report["issues"] == []


def test_assert_no_factor_consistency_errors_raises_on_hard_error() -> None:
    tool = load_tool()

    report = tool.build_audit_report(
        cluster_rows=cluster_rows("2.5"),
        material_notes={17: {"obj_src_note": "不等同于生前杀戮或系统清洗。"}},
    )

    try:
        tool.assert_no_factor_consistency_errors(report)
    except tool.I5BFactorConsistencyAuditError as exc:
        assert "李世民/tolerate_talent/魏徵#17" in str(exc)
    else:
        raise AssertionError("expected consistency audit error")
