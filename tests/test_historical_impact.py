"""Contract tests using independent synthetic decisions, not historical snapshots."""
from copy import deepcopy
from pathlib import Path
import json

import pytest
import yaml

from emperor_v4.evaluation.formal_json_store import write_polity_routed_json
from emperor_v4.evaluation.historical_impact import LABEL_MAPPING, verify, write_views


def _workspace(root: Path) -> tuple[dict, Path]:
    (root / "config").mkdir()
    pool = {"records": [{"ruler_id": "SYNTHETIC", "ruler_name": "合成对象", "polity": "合成政权", "pool_status": "INCLUDED", "actual_power_window": "100—110"}]}
    (root / "config/pool.json").write_text(json.dumps(pool), encoding="utf-8")
    entry = {"json": "result.json", "markdown": "result.md", "canonical_pool": "config/pool.json", "payload_schema_version": "historical-impact-formal-v1", "contract_version": "FORMAL-V1.0", "numerical_scoring_enabled": False, "composite_ranking_write": False, "profile_radar_write": False}
    entry.update(payload_schema_version="historical-impact-formal-v2", contract_version="FORMAL-V1.2")
    (root / "config/project.yml").write_text(yaml.safe_dump({"historical_impact_assessment": entry}), encoding="utf-8")
    row = {"ruler_id": "SYNTHETIC", "ruler_name": "合成对象", "identity_label": "合成对象", "polity": "合成政权", "reference_power_window": "100—110", "reading_start_year": 100, "pool_relation": "MAIN_POOL", "formal_status": "FORMAL_CURRENT", "task_code": "HISTORICAL-IMPACT-SYNTHETIC", "public_grade": "C", "internal_band": "A", "confidence": "MEDIUM", "impact_nature": "混合", "dimensions": {k: {"grade": "A", "boundary_note": ""} for k in ("scope", "depth_duration", "personal_causality", "paradigm")}, "nearest_feasible_counterfactual": "保留平台，替代者改变方案。", "personal_causal_boundary": "设计与执行分账。", "paradigm_analysis": "存在有限接收。", "grade_basis": "有限阶段结构变化。", "counterfactual_window_policy": "关键行动起点。", "historical_source_notes": [], "source_refs": [{"kind": "IMPORTED_ADJUDICATION", "document": "合成用例", "section": "独立构造"}], "macro_chains": [{"chain_id": "SYNTHETIC-CHAIN", "title": "结构变化", "narrative": "方案在区域实行并在继任期延续。", "source_ref_indices": [0]}]}
    row.pop("counterfactual_window_policy")
    row["macro_chains"][0]["chain_kind"] = "MACRO_TRANSFORMATION"
    row["source_refs"][0].update(subsection="结构变化", adopted_excerpt="方案在区域实行并在继任期延续。", evidence_role="SYNTHETIC_ADOPTED_PASSAGE")
    row["public_total_basis"] = "影响范围为A，深度与持续为A，两者共同形成基础影响量级A；个人因果为A，按本人实际选择与替代路径比较作有限修正；政治范式为A，只作有限补充；最终量级为A，对应公开等级C。"
    row["public_boundary"] = "范围边界：既有平台不重复计入。深度边界：后续独立重建不归入本人。个人因果边界：团队与前制责任另行区分。范式边界：仅计实际政治使用，不以一般声望替代。"
    for dimension, label in {
        "scope": "范围",
        "depth_duration": "深度与持续",
        "personal_causality": "个人因果",
        "paradigm": "范式",
    }.items():
        row["dimensions"][dimension]["public_basis"] = f"{label}为A；现有事实支持该维度的合成判断。"
    row.update(
        counterfactual_entry={"anchor": "独立构造的选择节点", "retained_conditions": "既有平台", "functional_alternative": "另一人改变执行方式", "identity_exclusion": "不要求相同姓名"},
        confidence_basis="替代执行方式存在分支。",
        source_trace={"status": "SYNTHETIC_ADOPTED_PASSAGE"},
        foundation={"base_band": "A", "chain_ids": ["SYNTHETIC-CHAIN"], "joint_footprint_basis": "同一地区的结构变化与接续。", "causal_adjustment": "基础A不再机械降档。", "causal_application": "平台共享。", "paradigm_adjustment": "范式A不抬档。", "decided_internal_band": "A", "decided_public_grade": "C"},
        paradigm_review={"evidence_status": "LOCATED_RECEPTION", "limitation": "仅一例", "depth_separation": "只取政治引用，不取制度延续。", "receptions": [{"receiver": "虚构继任者", "carrier": "合成材料", "actual_use": "引用该政治先例", "source_basis": "SYNTHETIC_CASE"}]},
        related_fact_entries=[],
    )
    payload = {"schema_version": entry["payload_schema_version"], "contract_version": entry["contract_version"], "public_label_mapping": LABEL_MAPPING, "numerical_scoring_enabled": False, "composite_ranking_write": False, "profile_radar_write": False, "record_count": 1, "supplementary_record_count": 0, "records": [row], "supplementary_records": []}
    return payload, root / "result.json"


def test_routed_reader_and_verifier_are_read_only(tmp_path: Path) -> None:
    payload, path = _workspace(tmp_path)
    write_polity_routed_json(path, payload, ruler_polities={})
    write_views(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*.json")}
    assert verify(tmp_path)["status"] == "PASS"
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*.json")}


def test_reader_exposes_decision_before_expandable_evidence(tmp_path: Path) -> None:
    from emperor_v4.evaluation.historical_impact import render
    payload, _ = _workspace(tmp_path)
    row = payload["records"][0]
    row["scope_assessment"] = {
        "actual_changes": "合成区域的服从关系改变。",
        "baseline_and_exclusions": "既有控制区不计新增。",
    }
    result = render(payload)
    anchor = "person-" + row["ruler_id"].lower()
    assert f"](#{anchor})" in result
    assert f'<a id="{anchor}"></a>' in result
    card = result.split(f'<a id="{anchor}"></a>', 1)[1]
    summary, evidence = card.split("<details>", 1)
    assert row["scope_assessment"]["actual_changes"] in summary
    assert row["scope_assessment"]["baseline_and_exclusions"] in summary
    assert row["macro_chains"][0]["title"] in summary
    assert row["nearest_feasible_counterfactual"] in evidence
    assert result.count("<details>") == result.count("</details>")


def test_reader_deduplicates_basis_without_losing_extra_reason(tmp_path: Path) -> None:
    from emperor_v4.evaluation.historical_impact import render
    payload, _ = _workspace(tmp_path)
    row = payload["records"][0]
    basis = row["foundation"]["joint_footprint_basis"]
    extra = "独立的边界理由须保留。"
    row["grade_basis"] = basis + "\n\n" + extra
    row["depth_review"] = {"basis": "合成后继继续运行。", "limits": "后续独立重建截断。"}
    result = render(payload)
    assert result.count(basis) == 1
    assert extra in result
    assert row["depth_review"]["basis"] in result
    assert row["depth_review"]["limits"] in result


def test_reader_uses_formal_public_fields_before_expandable_evidence(tmp_path: Path) -> None:
    from emperor_v4.evaluation.historical_impact import render
    payload, _ = _workspace(tmp_path)
    row = payload["records"][0]
    result = render(payload)
    card = result.split(f'<a id="person-{row["ruler_id"].lower()}"></a>', 1)[1]
    summary, evidence = card.split("<details>", 1)
    assert row["public_total_basis"] in summary
    assert row["public_boundary"] in summary
    assert all(row["dimensions"][key]["public_basis"] in summary for key in row["dimensions"])
    assert row["nearest_feasible_counterfactual"] in evidence


def test_public_fields_are_required_and_cannot_contain_internal_wording(tmp_path: Path) -> None:
    payload, path = _workspace(tmp_path)
    payload["records"][0]["public_total_basis"] = "项目底账重新拼装总档。"
    write_polity_routed_json(path, payload, ruler_polities={})
    with pytest.raises(ValueError, match="公开字段"):
        verify(tmp_path, check_reader=False)


def test_historical_reader_consumes_formal_public_text_without_semantic_rewrite() -> None:
    root = Path(__file__).resolve().parents[1]
    template = (root / "reader" / "index.template.html").read_text(encoding="utf-8")
    readability = (root / "reader" / "person-readability.js").read_text(encoding="utf-8")
    public_copy = (root / "reader" / "public-copy.json").read_text(encoding="utf-8")
    assert "public_total_basis" in template
    assert "public_boundary" in template
    assert "public_basis" in template
    assert "historyReaderText" not in template
    assert "historyReaderText" not in readability
    assert "publicTotalReason" not in readability
    assert "internalWording" not in public_copy
    assert "historical-impact-reading.js" not in public_copy


def test_repeated_receiver_does_not_become_independent_receptions(tmp_path: Path) -> None:
    payload, path = _workspace(tmp_path)
    row = payload["records"][0]
    row["dimensions"]["paradigm"]["grade"] = "S-"
    row["paradigm_review"]["receptions"].append(deepcopy(row["paradigm_review"]["receptions"][0]))
    write_polity_routed_json(path, payload, ruler_polities={})
    with pytest.raises(ValueError, match="独立接收者"):
        write_views(tmp_path)


def test_related_entry_is_not_promoted_to_chain_evidence(tmp_path: Path) -> None:
    from emperor_v4.evaluation.formal_json_store import load_json
    payload, path = _workspace(tmp_path)
    (tmp_path / "related.json").write_text(json.dumps({"records": [{"ruler_id": "SYNTHETIC"}]}), encoding="utf-8")
    payload["records"][0]["related_fact_entries"] = [{"kind": "LOCAL_FORMAL_RECORD", "path": "related.json", "ruler_id": "SYNTHETIC"}]
    write_polity_routed_json(path, payload, ruler_polities={})
    write_views(tmp_path)
    assert verify(tmp_path)["status"] == "PASS"
    row = load_json(path)["records"][0]
    assert all(ref.get("path") != "related.json" for ref in row["source_refs"])
    assert row["macro_chains"][0]["source_ref_indices"] == [0]


@pytest.mark.parametrize("violation", ["label", "source_index", "scope", "scoring", "scope_boundary", "scope_review", "engineering", "foundation_ref", "reception", "counterfactual"])
def test_invalid_current_contract_is_rejected(tmp_path: Path, violation: str) -> None:
    payload, path = _workspace(tmp_path)
    payload = deepcopy(payload)
    if violation == "label":
        payload["records"][0]["public_grade"] = "B"
    elif violation == "source_index":
        payload["records"][0]["macro_chains"][0]["source_ref_indices"] = [7]
    elif violation == "scope":
        payload["records"][0]["pool_relation"] = "SUPPLEMENTARY"
    elif violation == "scope_boundary":
        payload["records"][0]["dimensions"]["scope"]["boundary_note"] = "上沿"
    elif violation == "scope_review":
        payload["records"][0]["scope_assessment"] = {"actual_changes": "局部改变"}
    elif violation == "engineering":
        payload["records"][0]["macro_chains"][0]["chain_kind"] = "ENGINEERING_ONLY"
    elif violation == "foundation_ref":
        payload["records"][0]["foundation"]["chain_ids"] = ["MISSING"]
    elif violation == "reception":
        payload["records"][0]["dimensions"]["paradigm"]["grade"] = "S-"
    elif violation == "counterfactual":
        payload["records"][0]["counterfactual_entry"]["retained_conditions"] = ""
    else:
        payload["composite_ranking_write"] = True
    write_polity_routed_json(path, payload, ruler_polities={})
    with pytest.raises(ValueError):
        write_views(tmp_path)
        verify(tmp_path)
