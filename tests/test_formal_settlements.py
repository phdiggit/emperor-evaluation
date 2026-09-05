import json
from copy import deepcopy
from pathlib import Path

import pytest

from emperor_v4.evaluation.formal_settlements import (
    verify_formal_settlements,
    verify_second_item_a_snapshot,
    verify_second_item_b1_snapshot,
    verify_second_item_b2_snapshot,
)
from emperor_v4.evaluation.composite_ranking import build_composite_ranking
from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.second_item_b1_settlement import validate_gate_references


def test_all_five_formal_settlements_are_coherent() -> None:
    report = verify_formal_settlements(Path("."))
    assert report["status"] == "PASS"
    assert set(report["items"]) == {
        "first_item",
        "second_item",
        "third_item",
        "fourth_item",
        "fifth_item",
    }
    assert all(item["record_count"] > 0 for item in report["items"].values())


def test_second_item_a_snapshot_applies_v2_explicit_patch_and_registry() -> None:
    verify_second_item_a_snapshot(Path("."))
    payload = load_json(Path("docs/评分结算/第二项治国净收益/制度行政/01-A制度建设与实际运行方向卡.json"))
    assert all(row["C_A"] in {0, 0.5, 1, 2} for row in payload["records"])
    assert all(
        row["S_total"] >= 1 and row["S_net"] >= 0
        for row in payload["records"]
        if row["grade"] in {"G4", "G5"}
    )
    generic_mechanisms = {"其他制度行政机制", "法律、司法与刑罚运行", "选官、人事与官僚专业化", "地方行政与政策交付", "A"}
    assert not any(
        profile.get("mechanism") in generic_mechanisms
        for row in payload["records"]
        for group in ("M_positive_profile", "M_mixed_profile", "M_negative_profile")
        for profile in row[group]
    )
    markdown = Path(
        "docs/评分结算/第二项治国净收益/制度行政/01-A制度建设与实际运行方向卡.md"
    ).read_text(encoding="utf-8")
    ruler_sections = markdown.split("\n### ")[1:]
    assert len(ruler_sections) == len(payload["records"])
    assert all("\n- 材料依据：\n  - 《" in section for section in ruler_sections)
    material_lines = [line for line in markdown.splitlines() if line.startswith("  - ")]
    assert material_lines
    assert all(line.startswith("  - 《") for line in material_lines)
    assert not any(
        token in line
        for line in material_lines
        for token in ("material_id", "evidence_id", "source_url", "revision_ref", "sha256")
    )
    assert not any(
        token in line.split("》", 1)[0]
        for line in material_lines
        for token in ("底账", "登记", "方向卡", "结算", "清单", "index.php")
    )


def test_second_item_b1_snapshot_passes_current_verifier() -> None:
    verify_second_item_b1_snapshot(Path("."))


def test_second_item_b1_v54_validator_blocks_hidden_weights_severity_cross_low_gates_and_support_core() -> None:
    payload = load_json(Path("docs/评分结算/第二项治国净收益/制度行政/02-B1官僚治理与行政执行方向卡.json"))
    validate_gate_references(payload)

    broken = deepcopy(payload)
    next(profile for row in broken["records"] for profile in row["M_positive_profile"])["signed_weight"] = 999.0
    with pytest.raises(ValueError, match="M档与signed_weight不一致"):
        validate_gate_references(broken)

    broken = deepcopy(payload)
    negative_row = next(row for row in broken["records"] if row["M_negative_profile"] and "severity_scope" in row["M_negative_profile"][0])
    negative_row["M_negative_profile"][0].pop("severity_scope")
    with pytest.raises(ValueError, match="Severity scope"):
        validate_gate_references(broken)

    broken = deepcopy(payload)
    high_grade_row = next(row for row in broken["records"] if row.get("g4_core_profile_id"))
    core = next(profile for profile in high_grade_row["M_positive_profile"] if profile["profile_id"] == high_grade_row["g4_core_profile_id"])
    core["b1_role"] = "support"
    with pytest.raises(ValueError, match="不是B1-core正M3"):
        validate_gate_references(broken)

    broken = deepcopy(payload)
    low_grade_row = next(row for row in broken["records"] if row["grade"] == "G1" and len(row["M_negative_profile"]) == 1)
    profile = low_grade_row["M_negative_profile"][0]
    profile.update({"M": "M0", "direction": "context", "direction_factor": 0.0, "signed_weight": 0.0, "b1_role": "context"})
    for field in ("severity", "severity_scope", "severity_basis"):
        profile.pop(field, None)
    with pytest.raises(ValueError, match="B1 G1缺少"):
        validate_gate_references(broken)

    broken = deepcopy(payload)
    terminal_row = next(row for row in broken["records"] if row["grade"] == "G0" and sum(p.get("severity") == "N3-terminal" for p in row["M_negative_profile"]) == 1)
    terminal = next(profile for profile in terminal_row["M_negative_profile"] if profile.get("severity") == "N3-terminal")
    terminal["severity"] = "N3-cross"
    terminal["severity_scope"] = "major-stage"
    with pytest.raises(ValueError, match="B1 G0缺少"):
        validate_gate_references(broken)

    broken = deepcopy(payload)
    high_grade_negative_row = next(row for row in broken["records"] if row["grade"] in {"G4", "G5"} and row["M_negative_profile"])
    negative_profile = high_grade_negative_row["M_negative_profile"][0]
    negative_profile.update({"M": "M3", "direction": "negative", "direction_factor": -1.0, "signed_weight": -2.0, "severity": "N3-cross", "severity_scope": "major-stage", "b1_role": "core"})
    negative_profile.pop("position_weight_override", None)
    negative_profile.pop("position_count_mode", None)
    negative_profile["grade_independence_lifecycle_key"] = "TEST-INDEPENDENT-NEGATIVE"
    with pytest.raises(ValueError, match="major-stage/broad N3-cross"):
        validate_gate_references(broken)


def test_second_item_b2_snapshot_passes_current_verifier() -> None:
    verify_second_item_b2_snapshot(Path("."))


def test_composite_ranking_uses_only_ready_rulers_and_current_formula() -> None:
    payload = build_composite_ranking(Path("."))
    assert payload["formula"] == "T = S2 + S3 + 0.15 * 637 * (S1 / 240) ^ 1.25 + CIV4"
    assert all(
        row["ruler_name"] not in {pending["ruler_name"] for pending in payload["pending_second_item_records"]}
        for row in payload["records"]
    )
    for row in payload["records"]:
        expected = round(
            row["second_item_score"]
            + row["third_item_score"]
            + row["first_item_add_on"]
            + row["fourth_item_adjustment"],
            2,
        )
        assert abs(row["total_score"] - expected) <= 0.01


def test_c4_uses_one_current_destructive_amplification_verdict() -> None:
    path = Path("docs/评分结算/第二项治国净收益/财政民生/04-C4正式结算.json")
    payload = load_json(path)
    penalties = {
        "DA0": 0.0, "DA1": 4.5, "DA2": 9.0, "DA3": 13.5,
        "DA4": 18.0, "DA5": 22.5, "DA6": 27.0,
    }

    assert payload["attribution_readjudication"]["status"] == "FORMAL_COMPLETE"
    assert payload["review_progress"]["remaining_record_count"] == 0
    for row in payload["scores"]:
        grade = row["destructive_amplification_grade"]
        review = row["c4_attribution_readjudication"]
        assert row["destructive_amplification_penalty"] == penalties[grade]
        assert review["final_grade"] == grade
        assert review["final_penalty"] == penalties[grade]
        assert row["military_cost_review"]["final_grade"] == grade
        assert row["negative_tail_adjudication_reason"] == row["behavior_and_attribution"]
        assert row["attribution_readjudication_reason"] == row["behavior_and_attribution"]
        assert "previous_grade" not in review
        assert "original_adjudication_reason" not in review


def test_five_dynasties_batch_is_fully_settled() -> None:
    root = Path("docs/评分结算/第二项治国净收益")
    finance = root / "财政民生"
    files = {
        "C1": "01-C1正式结算.json",
        "C2": "02-C2正式结算.json",
        "C3": "03-C3正式结算.json",
        "C4": "04-C4正式结算.json",
        "result": "05-治理结果正式结算.json",
    }
    rows = {
        axis: {
            row["ruler_name"]: row
            for row in load_json(finance / filename)["scores"]
        }
        for axis, filename in files.items()
    }
    expected = {"杨行密", "钱镠", "马殷", "高季兴", "孟知祥", "李克用", "刘崇"}
    for name in expected:
        components = [rows[axis][name]["score"] for axis in ("C1", "C2", "C3", "C4")]
        assert rows["result"][name]["score"] == round(sum(components), 1)
    total_rows = {
        row["ruler_name"]: row
        for row in json.loads(
            (root / "01-第二项治国净收益正式结算.json").read_text(encoding="utf-8")
        )["records"]
    }
    for name in expected:
        row = total_rows[name]
        assert row["second_item_score"] == round(
            row["governance_method_score"] + row["governance_result_score"] + row["handoff_score"], 1
        )
