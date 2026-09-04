import json
from pathlib import Path

import yaml

from emperor_v4.evaluation.canonical_ruler_pool import (
    build_canonical_ruler_pool,
    verify_canonical_ruler_pool,
)


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_pool_is_rebuildable_and_feasible() -> None:
    payload = build_canonical_ruler_pool(ROOT)
    included = [row for row in payload["records"] if row["pool_status"] == "INCLUDED"]
    excluded = [row for row in payload["records"] if row["pool_status"] == "EXCLUDED"]
    assert all(row["evidence_feasibility"]["third_item_formal"] for row in included)
    assert all(row["evidence_feasibility"]["fourth_item_formal"] for row in included)
    assert all(row["evidence_feasibility"]["fifth_item_formal"] for row in included)
    assert all(row["first_item_readiness"] == "NOT_APPLICABLE_EXCLUDED" for row in excluded)
    pending_second = [
        row
        for row in included
        if row["settlement_readiness"] == "PENDING_SECOND_ITEM_FORMAL_SETTLEMENT"
    ]
    assert all(not row["evidence_feasibility"]["second_item_formal"] for row in pending_second)
    assert all(not row["evidence_feasibility"]["second_item_score_snapshot_present"] for row in pending_second)
    assert all(row["evidence_feasibility"]["second_item_local_evidence_refs"] for row in pending_second)


def test_checked_in_pool_matches_current_settlements() -> None:
    verify_canonical_ruler_pool(ROOT)


def test_jin_taizong_identity_registry_has_one_canonical_id() -> None:
    payload = yaml.safe_load(
        (ROOT / "config/common/historical-entity-identities.yml").read_text(encoding="utf-8")
    )
    row = next(item for item in payload["entities"] if item["canonical_name"] == "完颜晟")
    assert row["person_ref"] == "RULER-JIN-TAIZONG"
    assert row["legacy_person_refs"] == [
        "RULER-JIN-WANYAN-SHENG",
        "RULER-ROSTER-6FB8C85A5180DFB2",
    ]
    assert {alias["surface"] for alias in row["aliases"]} == {"完颜吴乞买", "金太宗"}


def test_qing_second_item_ids_are_canonical_with_legacy_refs() -> None:
    identities = yaml.safe_load(
        (ROOT / "config/common/historical-entity-identities.yml").read_text(encoding="utf-8")
    )
    expected = {
        "努尔哈赤": "6E925E92C6F5ECA5",
        "皇太极": "6339E33979E7CCF5",
        "福临": "AD29E67DF9E98569",
        "玄烨": "5B02E75C191C9829",
        "胤禛": "4EB7AC987FECC59F",
        "弘历": "6DACD59C17927ECA",
        "颙琰": "93F6E8CA07BBD59F",
        "旻宁": "7C4ED87E9C80BF8A",
        "奕詝": "310D1C92CEE1924D",
    }
    by_name = {row["canonical_name"]: row for row in identities["entities"]}
    second = json.loads(
        (
            ROOT
            / "docs/评分结算/第二项治国净收益/01-第二项治国净收益正式结算.json"
        ).read_text(encoding="utf-8")
    )
    second_by_name = {row["ruler_name"]: row for row in second["records"]}
    for name, suffix in expected.items():
        canonical_id = f"RULER-PUBLIC-{suffix}"
        assert by_name[name]["person_ref"] == canonical_id
        assert by_name[name]["legacy_person_refs"] == [f"RULER-ROSTER-{suffix}"]
        assert second_by_name[name]["ruler_id"] == canonical_id
