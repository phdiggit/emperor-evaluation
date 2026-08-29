from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

import yaml

from emperor_v4.evaluation.profile_m3_livelihood_settlement import (
    C4_ATTRIBUTION,
    C_PATHS,
    M3_ACCEPTANCE,
    M3_MARKDOWN,
    M3_REVIEW,
    M3_SETTLEMENT,
    MISSING,
    POOL,
    RESULT,
    ROOT,
    SUPPLEMENT,
)
from emperor_v4.evaluation.profile_markdown import render_profile_markdown


PROJECT = ROOT / "config/project.yml"


def _load(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), f"UTF-8 BOM forbidden: {path}"
    return json.loads(raw.decode("utf-8"))


def verify_payloads() -> dict[str, Any]:
    pool = {row["ruler_id"] for row in _load(POOL)["records"] if row["pool_status"] == "INCLUDED"}
    missing = _load(MISSING)
    supplement = _load(SUPPLEMENT)
    attribution = _load(C4_ATTRIBUTION)
    result = _load(RESULT)
    settlement = _load(M3_SETTLEMENT)
    review = _load(M3_REVIEW)
    finance = {
        axis: {row["ruler_id"]: row for row in _load(path)["scores"]}
        for axis, path in C_PATHS.items()
    }
    assert len(pool) == 184
    assert missing["record_count"] == len(missing["records"]) == 10
    assert supplement["record_count"] == len(supplement["records"]) == 184
    assert supplement["parent_chain_count"] == 204
    assert supplement["candidate_trace_count"] == 316
    assert {row["ruler_id"] for row in supplement["records"]} == pool
    assert all(row["review_status"] == "FULLY_ROUTED_TO_C1_C2_C3_C4" for row in supplement["records"])
    assert all(set(row["axis_resolutions"]) == set(C_PATHS) for row in supplement["records"])
    assert attribution["record_count"] == len(attribution["records"]) == 184
    assert {row["ruler_id"] for row in attribution["records"]} == pool
    assert all(row["review_status"] == "FULLY_ADJUDICATED" for row in attribution["records"])
    assert all(row["source_refs"] for row in attribution["records"])
    assert all(
        row["closed_residual_harm_observations"]
        for row in attribution["records"]
        if row["decision"]["final_grade"] != "DA0"
    )
    assert all(
        len({item["observation"] for item in row["closed_residual_harm_observations"]})
        == len(row["closed_residual_harm_observations"])
        for row in attribution["records"]
    )
    grade_counts = {
        grade: sum(row["decision"]["final_grade"] == grade for row in attribution["records"])
        for grade in ("DA0", "DA1", "DA2", "DA3", "DA4")
    }
    assert attribution["grade_counts"] == grade_counts == {"DA0": 15, "DA1": 51, "DA2": 74, "DA3": 41, "DA4": 3}
    records_hash = hashlib.sha256(
        json.dumps(attribution["records"], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert attribution["records_sha256"] == records_hash
    assert all(len(rows) == 195 and pool <= set(rows) for rows in finance.values())
    attribution_by_id = {row["ruler_id"]: row for row in attribution["records"]}
    for ruler_id in pool:
        c4_row = finance["C4"][ruler_id]
        decision = attribution_by_id[ruler_id]["decision"]
        assert c4_row["destructive_amplification_grade"] == decision["final_grade"]
        assert c4_row["destructive_amplification_penalty"] == decision["final_penalty"]
        assert c4_row["c4_attribution_readjudication"]["review_status"] == "FULLY_ADJUDICATED"
    assert result["record_count"] == len(result["scores"]) == 195
    result_by_id = {row["ruler_id"]: row for row in result["scores"]}
    assert set(result_by_id) == set(finance["C1"])
    for ruler_id, row in result_by_id.items():
        expected = round(sum(float(finance[axis][ruler_id]["score"]) for axis in C_PATHS), 1)
        assert row["score"] == expected
    assert settlement["schema_version"] == "profile-m3-livelihood-finance-formal-settlement-v1"
    assert settlement["canonical_status"] == "FORMAL_CURRENT"
    assert settlement["contract_version"] == "FORMAL-V2.0"
    assert settlement["axis_name"] == "民生财政建设"
    assert settlement["formal_profile_write"] is True
    assert settlement["formal_rank_write"] is False
    assert settlement["profile_total_enabled"] is False
    assert settlement["profile_ranking_enabled"] is False
    assert settlement["composite_ranking_write"] is False
    assert settlement["database_write"] is False
    assert settlement["record_order_policy"] == "RADAR_VALUE_DESC_THEN_RULER_ID_ASC"
    assert settlement["record_count"] == len(settlement["records"]) == 184
    assert {row["ruler_id"] for row in settlement["records"]} == pool
    assert settlement["records"] == sorted(
        settlement["records"], key=lambda row: (-row["radar_value"], row["ruler_id"])
    )
    for row in settlement["records"]:
        result_row = result_by_id[row["ruler_id"]]
        expected = round(max(0.0, min(100.0, result_row["score"] / 220 * 100)))
        assert row["score_100"] == row["radar_value"] == expected
        assert row["component_total_220"] == result_row["score"]
        assert set(row["components"]) == set(C_PATHS)
        assert row["value_mode"] == "SECOND_ITEM_C1_C2_C3_C4_SYNCHRONIZED"
        assert row["formal_status"] == "FORMAL_CURRENT"
        assert row["output_mode"] == "FORMAL_RESULT_SYNCHRONIZATION"
        assert row["score_status"] == "FINAL"
        assert row["limitations"]
        for axis in C_PATHS:
            source_review = finance[axis][row["ruler_id"]]["m3_supplement_review"]
            assert len(source_review["applied_parent_chain_supplements"]) == len(
                source_review["applied_parent_ids"]
            )
            assert len(source_review["applied_orphan_candidate_supplements"]) == len(
                source_review["applied_orphan_candidate_ids"]
            )
    assert review["record_count"] == 184
    assert review["parent_chain_count"] == 204
    assert review["candidate_trace_count"] == 316
    assert review["c4_attribution_readjudication"]["record_count"] == 184
    assert review["c4_attribution_readjudication"]["grade_counts"] == grade_counts
    assert M3_MARKDOWN.exists() and M3_ACCEPTANCE.exists()
    assert M3_MARKDOWN.read_text(encoding="utf-8") == render_profile_markdown(settlement)
    project = yaml.safe_load(PROJECT.read_text(encoding="utf-8"))
    assert project["profile_assessment"]["contract_version"] == "FORMAL-V2.0"
    entry = project["profile_assessment"]["settled_axes"]["M3"]
    assert entry["name"] == "民生财政建设"
    assert ROOT / entry["json"] == M3_SETTLEMENT
    assert ROOT / entry["markdown"] == M3_MARKDOWN
    assert ROOT / project["formal_settlements"]["second_item"]["c4_attribution_readjudications_json"] == C4_ATTRIBUTION
    manifest = _load(ROOT / "docs/评分结算/皇帝人物画像/00-已结算轴正式入口.json")
    manifest_entry = next(axis for axis in manifest["axes"] if axis["axis_code"] == "M3")
    assert manifest["contract_version"] == "FORMAL-V2.0"
    assert manifest_entry["json"] == M3_SETTLEMENT.relative_to(M3_SETTLEMENT.parents[1]).as_posix()
    assert manifest_entry["json_sha256"] == hashlib.sha256(M3_SETTLEMENT.read_bytes()).hexdigest()
    assert manifest_entry["markdown_sha256"] == hashlib.sha256(M3_MARKDOWN.read_bytes()).hexdigest()
    return {
        "profile_population": 184,
        "finance_population": 195,
        "old_m3_candidate_count": 316,
        "old_m3_parent_chain_count": 204,
        "new_finance_record_count": 10,
    }


def verify() -> dict[str, Any]:
    return verify_payloads()


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, sort_keys=True))
