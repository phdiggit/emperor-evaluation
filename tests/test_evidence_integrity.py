import subprocess
import sys
from pathlib import Path
from typing import Any
import importlib.util

import pytest


ROOT = Path(__file__).resolve().parents[1]
SUMMARY_EXPORT_ROOT = ROOT / "exports" / "markdown_views" / "综合汇总"
EXPORT_PATH = SUMMARY_EXPORT_ROOT / "史料证据卡索引.md"
EVIDENCE_CLUSTERS_EXPORT_PATH = SUMMARY_EXPORT_ROOT / "证据组裁量索引.md"
THEMATIC_ANCHORS_EXPORT_PATH = SUMMARY_EXPORT_ROOT / "专题锚点索引.md"
QUERY_PROFILES_EXPORT_PATH = SUMMARY_EXPORT_ROOT / "项目检索包索引.md"

VALIDATE_EVIDENCE_SPEC = importlib.util.spec_from_file_location(
    "validate.validate_evidence",
    ROOT / "scripts" / "validate" / "validate_evidence.py",
)
assert VALIDATE_EVIDENCE_SPEC is not None
validate_evidence = importlib.util.module_from_spec(VALIDATE_EVIDENCE_SPEC)
assert VALIDATE_EVIDENCE_SPEC.loader is not None
VALIDATE_EVIDENCE_SPEC.loader.exec_module(validate_evidence)


def test_validate_evidence_allows_empty_data() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate" / "validate_evidence.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Validation passed." in result.stdout


def test_existing_trigger_terms_jsonl_passes() -> None:
    errors = validate_evidence.validate()

    assert errors == []


@pytest.mark.export_full
@pytest.mark.integration
@pytest.mark.db
def test_export_md_generates_evidence_index() -> None:
    build_result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build" / "build_db.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert build_result.returncode == 0, build_result.stdout + build_result.stderr

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "export" / "export_md.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert EXPORT_PATH.exists()
    content = EXPORT_PATH.read_text(encoding="utf-8")
    assert "| evidence_id | person | subitem | human_level | source_id | quote_short | object_anchor |" in content
    assert "object_anchor" in content
    assert "evidence_role" in content
    assert "mitigation_flag" in content
    assert "upper_bound_flag" in content
    assert "cluster_role" in content
    assert EVIDENCE_CLUSTERS_EXPORT_PATH.exists()
    assert THEMATIC_ANCHORS_EXPORT_PATH.exists()
    assert QUERY_PROFILES_EXPORT_PATH.exists()


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    import json

    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


@pytest.fixture()
def validation_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for name in [
        "evidence_cards",
        "sources",
        "events",
        "trigger_terms",
        "search_logs",
        "evidence_clusters",
        "thematic_anchors",
        "query_profiles",
    ]:
        (data_dir / f"{name}.jsonl").write_text("", encoding="utf-8")

    monkeypatch.setattr(validate_evidence, "DATA_DIR", data_dir)
    monkeypatch.setattr(
        validate_evidence,
        "JSONL_FILES",
        [
            data_dir / "evidence_cards.jsonl",
            data_dir / "sources.jsonl",
            data_dir / "events.jsonl",
            data_dir / "trigger_terms.jsonl",
            data_dir / "search_logs.jsonl",
            data_dir / "evidence_clusters.jsonl",
            data_dir / "thematic_anchors.jsonl",
            data_dir / "query_profiles.jsonl",
        ],
    )
    return data_dir


def test_validate_empty_data_with_temp_dir(validation_data_dir: Path) -> None:
    assert validate_evidence.validate() == []


def test_trigger_terms_invalid_tier_fails(validation_data_dir: Path) -> None:
    write_jsonl(
        validation_data_dir / "trigger_terms.jsonl",
        [
            {
                "term_id": "TRG-I5B-POS-TEST-001",
                "item": "第五项",
                "subitem": "第五项B",
                "polarity": "positive",
                "trigger_family": "测试",
                "term": "测试词",
                "tier": "middle",
                "note": "",
            }
        ],
    )

    errors = validate_evidence.validate()

    assert any("tier must be core or extended" in error for error in errors)


def test_trigger_terms_duplicate_term_id_fails(validation_data_dir: Path) -> None:
    row = {
        "term_id": "TRG-I5B-POS-TEST-001",
        "item": "第五项",
        "subitem": "第五项B",
        "polarity": "positive",
        "trigger_family": "测试",
        "term": "测试词",
        "tier": "core",
        "note": "",
    }
    write_jsonl(validation_data_dir / "trigger_terms.jsonl", [row, {**row, "term": "测试词二"}])

    errors = validate_evidence.validate()

    assert any("duplicate term_id: TRG-I5B-POS-TEST-001" in error for error in errors)


def test_strength_four_positive_requires_extreme_positive(validation_data_dir: Path) -> None:
    write_jsonl(
        validation_data_dir / "sources.jsonl",
        [
            {
                "source_id": "SRC-TEST-VOL-001",
                "title": "测试来源",
                "author": "",
                "dynasty": "",
                "volume": "",
                "location": "",
                "url": "",
                "note": "",
            }
        ],
    )
    write_jsonl(
        validation_data_dir / "evidence_cards.jsonl",
        [
            {
                "evidence_id": "EVD-I5B-TEST-POS-001",
                "person": "测试人物",
                "item": "第五项",
                "subitem": "第五项B",
                "polarity": "positive",
                "strength": 4,
                "human_level": "强正",
                "source_id": "SRC-TEST-VOL-001",
                "quote_short": "测试短引",
                "interpretation": "测试解释",
                "trigger_family": "测试",
                "trigger_terms": ["测试词"],
                "cross_item_split": "",
                "scoring_effect": "",
                "verification_status": "verified",
            }
        ],
    )

    errors = validate_evidence.validate()

    assert any("requires human_level=极正" in error for error in errors)


def test_strength_three_positive_rejects_weak_positive(validation_data_dir: Path) -> None:
    write_jsonl(
        validation_data_dir / "sources.jsonl",
        [
            {
                "source_id": "SRC-TEST-VOL-001",
                "title": "测试来源",
                "author": "",
                "dynasty": "",
                "volume": "",
                "location": "",
                "url": "",
                "note": "",
            }
        ],
    )
    write_jsonl(
        validation_data_dir / "evidence_cards.jsonl",
        [
            {
                "evidence_id": "EVD-I5B-TEST-POS-001",
                "person": "测试人物",
                "item": "第五项",
                "subitem": "第五项B",
                "polarity": "positive",
                "strength": 3,
                "human_level": "弱正",
                "source_id": "SRC-TEST-VOL-001",
                "quote_short": "测试短引",
                "interpretation": "测试解释",
                "trigger_family": "测试",
                "trigger_terms": ["测试词"],
                "cross_item_split": "",
                "scoring_effect": "",
                "verification_status": "verified",
            }
        ],
    )

    errors = validate_evidence.validate()

    assert any("polarity=positive and strength=3 requires human_level=强正" in error for error in errors)


def test_strength_four_negative_requires_extreme_negative(validation_data_dir: Path) -> None:
    write_jsonl(
        validation_data_dir / "sources.jsonl",
        [
            {
                "source_id": "SRC-TEST-VOL-001",
                "title": "测试来源",
                "author": "",
                "dynasty": "",
                "volume": "",
                "location": "",
                "url": "",
                "note": "",
            }
        ],
    )
    write_jsonl(
        validation_data_dir / "evidence_cards.jsonl",
        [
            {
                "evidence_id": "EVD-I5B-TEST-NEG-001",
                "person": "测试人物",
                "item": "第五项",
                "subitem": "第五项B",
                "polarity": "negative",
                "strength": 4,
                "human_level": "强负",
                "source_id": "SRC-TEST-VOL-001",
                "quote_short": "测试短引",
                "interpretation": "测试解释",
                "trigger_family": "测试",
                "trigger_terms": ["测试词"],
                "cross_item_split": "测试切分",
                "scoring_effect": "",
                "verification_status": "verified",
            }
        ],
    )

    errors = validate_evidence.validate()

    assert any("requires human_level=极负" in error for error in errors)


def test_strength_two_negative_rejects_strong_negative(validation_data_dir: Path) -> None:
    write_jsonl(
        validation_data_dir / "sources.jsonl",
        [
            {
                "source_id": "SRC-TEST-VOL-001",
                "title": "测试来源",
                "author": "",
                "dynasty": "",
                "volume": "",
                "location": "",
                "url": "",
                "note": "",
            }
        ],
    )
    write_jsonl(
        validation_data_dir / "evidence_cards.jsonl",
        [
            {
                "evidence_id": "EVD-I5B-TEST-NEG-001",
                "person": "测试人物",
                "item": "第五项",
                "subitem": "第五项B",
                "polarity": "negative",
                "strength": 2,
                "human_level": "强负",
                "source_id": "SRC-TEST-VOL-001",
                "quote_short": "测试短引",
                "interpretation": "测试解释",
                "trigger_family": "测试",
                "trigger_terms": ["测试词"],
                "cross_item_split": "测试切分",
                "scoring_effect": "",
                "verification_status": "verified",
            }
        ],
    )

    errors = validate_evidence.validate()

    assert any("polarity=negative and strength=2 requires human_level=中负" in error for error in errors)


def test_i5b_context_required_missing_status_fails(validation_data_dir: Path) -> None:
    write_jsonl(validation_data_dir / "sources.jsonl", [source_row()])
    write_jsonl(
        validation_data_dir / "evidence_cards.jsonl",
        [basic_positive_row(context_required=True)],
    )

    errors = validate_evidence.validate()

    assert any("context_required=true requires context_status" in error for error in errors)


def test_i5b_context_source_verified_missing_bridge_fails(validation_data_dir: Path) -> None:
    write_jsonl(validation_data_dir / "sources.jsonl", [source_row()])
    row = basic_positive_row(
        context_required=True,
        context_status="source_verified",
        quote_context="完整上下文",
        context_summary="上下文摘要",
        context_scope="同段前后两句",
        context_effect="strengthen",
    )
    write_jsonl(validation_data_dir / "evidence_cards.jsonl", [row])

    errors = validate_evidence.validate()

    assert any("requires non-empty field: adjudication_bridge" in error for error in errors)


def test_i5b_context_not_required_does_not_force_context_fields(validation_data_dir: Path) -> None:
    write_jsonl(validation_data_dir / "sources.jsonl", [source_row()])
    write_jsonl(
        validation_data_dir / "evidence_cards.jsonl",
        [basic_positive_row(context_required=False)],
    )

    assert validate_evidence.validate() == []


def test_trigger_terms_missing_term_field_fails(validation_data_dir: Path) -> None:
    write_jsonl(
        validation_data_dir / "trigger_terms.jsonl",
        [
            {
                "term_id": "TRG-I5B-POS-TEST-001",
                "item": "第五项",
                "subitem": "第五项B",
                "polarity": "positive",
                "trigger_family": "测试",
                "tier": "core",
                "note": "",
            }
        ],
    )

    errors = validate_evidence.validate()

    assert any("missing required field: term" in error for error in errors)


def test_search_logs_missing_result_status_field_fails(validation_data_dir: Path) -> None:
    write_jsonl(
        validation_data_dir / "search_logs.jsonl",
        [
            {
                "search_id": "SRCH-I5B-TEST-POS-TEST-001",
                "person": "测试人物",
                "item": "第五项",
                "subitem": "第五项B",
                "polarity": "positive",
                "trigger_family": "测试",
                "query_terms": ["测试词"],
                "query": "",
                "source_scope": "",
                "searched_at": "",
                "result_summary": "",
                "linked_evidence_id": "",
                "note": "",
            }
        ],
    )

    errors = validate_evidence.validate()

    assert any("missing required field: result_status" in error for error in errors)


def test_evidence_cluster_unknown_evidence_id_fails(validation_data_dir: Path) -> None:
    write_jsonl(
        validation_data_dir / "evidence_clusters.jsonl",
        [
            {
                "cluster_id": "ADJ-I5B-TEST-POS-001",
                "person": "测试人物",
                "item": "第五项",
                "subitem": "第五项B",
                "cluster_type": "talent_ecosystem",
                "polarity": "positive",
                "linked_evidence_ids": ["EVD-NOT-EXIST-001", "EVD-NOT-EXIST-002"],
                "summary": "测试摘要",
                "five_axis_assessment": {"directness": "high"},
                "candidate_strength": 3,
                "upper_probe": "pending",
                "cross_item_split": "测试切分",
                "adjudication_status": "source_verified_pending_human_adjudication",
                "note": "",
            }
        ],
    )

    errors = validate_evidence.validate()

    assert any("linked_evidence_ids references unknown evidence_id" in error for error in errors)


def test_single_strong_evidence_cluster_is_allowed(validation_data_dir: Path) -> None:
    write_jsonl(validation_data_dir / "sources.jsonl", [source_row()])
    write_jsonl(
        validation_data_dir / "evidence_cards.jsonl",
        [
            high_risk_negative_row(
                evidence_id="EVD-I5B-TEST-NEG-CLUSTER-001",
                strength=3,
                human_level="强负",
            )
        ],
    )
    write_jsonl(
        validation_data_dir / "evidence_clusters.jsonl",
        [
            {
                "cluster_id": "ADJ-I5B-TEST-NEG-001",
                "person": "测试人物",
                "item": "第五项",
                "subitem": "第五项B",
                "cluster_type": "talent_security",
                "polarity": "negative",
                "linked_evidence_ids": ["EVD-I5B-TEST-NEG-CLUSTER-001"],
                "summary": "单卡强负组",
                "five_axis_assessment": {"directness": "high"},
                "candidate_strength": 3,
                "upper_probe": "pending",
                "cross_item_split": "测试切分",
                "adjudication_status": "source_verified_pending_human_adjudication",
                "note": "",
            }
        ],
    )

    assert validate_evidence.validate() == []


def test_single_medium_evidence_cluster_fails(validation_data_dir: Path) -> None:
    write_jsonl(validation_data_dir / "sources.jsonl", [source_row()])
    write_jsonl(
        validation_data_dir / "evidence_cards.jsonl",
        [
            high_risk_negative_row(
                evidence_id="EVD-I5B-TEST-NEG-CLUSTER-001",
                strength=2,
                human_level="中负",
            )
        ],
    )
    write_jsonl(
        validation_data_dir / "evidence_clusters.jsonl",
        [
            {
                "cluster_id": "ADJ-I5B-TEST-NEG-001",
                "person": "测试人物",
                "item": "第五项",
                "subitem": "第五项B",
                "cluster_type": "talent_security",
                "polarity": "negative",
                "linked_evidence_ids": ["EVD-I5B-TEST-NEG-CLUSTER-001"],
                "summary": "单卡中负组",
                "five_axis_assessment": {"directness": "medium"},
                "candidate_strength": 2,
                "upper_probe": "pending",
                "cross_item_split": "测试切分",
                "adjudication_status": "source_verified_pending_human_adjudication",
                "note": "",
            }
        ],
    )

    errors = validate_evidence.validate()

    assert any("a single linked evidence card requires candidate_strength>=3" in error for error in errors)


def test_thematic_anchor_unknown_cluster_id_fails(validation_data_dir: Path) -> None:
    write_jsonl(
        validation_data_dir / "thematic_anchors.jsonl",
        [
            {
                "anchor_id": "ANCHOR-I5B-TEST-001",
                "theme": "容谏",
                "item": "第五项",
                "subitem": "第五项B",
                "persons": ["测试人物"],
                "linked_evidence_ids": [],
                "linked_cluster_ids": ["ADJ-I5B-TEST-001"],
                "anchor_summary": "测试锚点",
                "comparative_value": "校准边界",
                "note": "",
            }
        ],
    )

    errors = validate_evidence.validate()

    assert any("linked_cluster_ids references unknown cluster_id" in error for error in errors)


def test_query_profile_list_fields_must_be_lists(validation_data_dir: Path) -> None:
    write_jsonl(
        validation_data_dir / "query_profiles.jsonl",
        [
            {
                "query_profile_id": "QRY-I5B-TEST-001",
                "item": "第五项",
                "subitem": "第五项B",
                "search_modes": "project_driven",
                "positive_terms": [],
                "negative_terms": [],
                "reversal_terms": [],
                "source_scopes": [],
                "reverse_search_required_when": [],
                "thematic_anchor_targets": [],
                "cross_item_split_notes": [],
                "note": "",
            }
        ],
    )

    errors = validate_evidence.validate()

    assert any("search_modes must be a list" in error for error in errors)


def source_row() -> dict[str, Any]:
    return {
        "source_id": "SRC-TEST-VOL-001",
        "title": "测试来源",
        "author": "",
        "dynasty": "",
        "volume": "",
        "location": "",
        "url": "",
        "note": "",
    }


def basic_positive_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "evidence_id": "EVD-I5B-TEST-POS-CONTEXT-001",
        "person": "测试人物",
        "item": "第五项",
        "subitem": "第五项B",
        "polarity": "positive",
        "strength": 1,
        "human_level": "弱正",
        "source_id": "SRC-TEST-VOL-001",
        "quote_short": "测试短引",
        "interpretation": "测试解释",
        "trigger_family": "测试",
        "trigger_terms": ["测试词"],
        "cross_item_split": "",
        "scoring_effect": "",
        "verification_status": "verified",
    }
    row.update(overrides)
    return row


def high_risk_negative_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "evidence_id": "EVD-I5B-TEST-NEG-001",
        "person": "测试人物",
        "item": "第五项",
        "subitem": "第五项B",
        "polarity": "negative",
        "strength": 3,
        "human_level": "强负",
        "source_id": "SRC-TEST-VOL-001",
        "quote_short": "测试短引",
        "interpretation": "测试解释",
        "trigger_family": "疑忌杀害",
        "trigger_terms": ["测试词"],
        "cross_item_split": "测试切分",
        "scoring_effect": "强负候选证据；不得直接入分，待人工裁判。",
        "verification_status": "source_verified",
        "case_classification": "political_case_expansion",
        "risk_status": "mixed_confirmed_case_with_expansion",
        "mitigating_factors": ["confirmed_rebellion"],
        "aggravating_factors": ["case_expansion"],
        "reversal_or_rehabilitation": ["not_found"],
        "adjudication_status": "source_verified_pending_human_adjudication",
    }
    row.update(overrides)
    return row


def write_high_risk_fixture(validation_data_dir: Path, row: dict[str, Any]) -> list[str]:
    write_jsonl(validation_data_dir / "sources.jsonl", [source_row()])
    write_jsonl(validation_data_dir / "evidence_cards.jsonl", [row])
    return validate_evidence.validate()


def test_high_risk_negative_missing_adjudication_fields_fails(validation_data_dir: Path) -> None:
    row = high_risk_negative_row()
    row.pop("case_classification")

    errors = write_high_risk_fixture(validation_data_dir, row)

    assert any("high-risk negative evidence missing required field: case_classification" in error for error in errors)


def test_confirmed_rebellion_non_expansion_strength_above_one_fails(validation_data_dir: Path) -> None:
    row = high_risk_negative_row(
        strength=2,
        human_level="中负",
        case_classification="confirmed_rebellion_or_security_case",
        risk_status="confirmed_rebellion",
    )

    errors = write_high_risk_fixture(validation_data_dir, row)

    assert any("confirmed_rebellion outside political_case_expansion" in error for error in errors)


def test_posthumous_trust_reversal_strength_above_one_fails(validation_data_dir: Path) -> None:
    row = high_risk_negative_row(
        strength=3,
        human_level="强负",
        case_classification="posthumous_trust_reversal",
        risk_status="not_applicable",
        mitigating_factors=["posthumous_event"],
        aggravating_factors=["chilling_effect_on_talent_ecology"],
    )

    errors = write_high_risk_fixture(validation_data_dir, row)

    assert any("posthumous_trust_reversal requires strength<=2" in error for error in errors)


def test_strength_three_with_mitigating_factors_requires_aggravating_factors(validation_data_dir: Path) -> None:
    row = high_risk_negative_row(aggravating_factors=[])

    errors = write_high_risk_fixture(validation_data_dir, row)

    assert any("strength>=3 with mitigating_factors requires aggravating_factors" in error for error in errors)


def test_strength_three_requires_pending_human_adjudication(validation_data_dir: Path) -> None:
    row = high_risk_negative_row(
        scoring_effect="强负候选证据。",
        adjudication_status="needs_more_source_review",
    )

    errors = write_high_risk_fixture(validation_data_dir, row)

    assert any("strength>=3 evidence requires pending human adjudication" in error for error in errors)
