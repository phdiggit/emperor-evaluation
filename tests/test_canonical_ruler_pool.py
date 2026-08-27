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
    assert payload["candidate_pool_count"] == 201
    assert payload["included_count"] == 184
    assert payload["composite_ready_count"] == 174
    assert payload["pending_second_item_count"] == 10
    assert payload["pending_first_item_scope_count"] == 0
    assert payload["pending_first_item_formal_settlement_count"] == 0
    assert payload["first_item_outside_candidate_pool_count"] == 5
    assert payload["excluded_count"] == 17
    assert payload["exclusion_reason_counts"] == {
        "EXCLUDED_NO_EFFECTIVE_POWER": 1,
        "EXCLUDED_LIMITED_INDEPENDENT_POWER": 2,
        "EXCLUDED_EFFECTIVE_POWER_LT_3_YEARS": 14,
    }
    included = [row for row in payload["records"] if row["pool_status"] == "INCLUDED"]
    excluded = [row for row in payload["records"] if row["pool_status"] == "EXCLUDED"]
    assert all(row["evidence_feasibility"]["third_item_formal"] for row in included)
    assert all(row["evidence_feasibility"]["fourth_item_formal"] for row in included)
    assert all(row["evidence_feasibility"]["fifth_item_formal"] for row in included)
    assert all(row["first_item_readiness"] == "NOT_APPLICABLE_EXCLUDED" for row in excluded)
    composite_ready = [
        row for row in included if row["settlement_readiness"] == "COMPOSITE_READY"
    ]
    first_item_absent = [
        row for row in composite_ready if row["source_item_ids"]["first_item"] is None
    ]
    assert [(row["ruler_name"], row["first_item_scope_note"]) for row in first_item_absent] == [
        ("完颜永济", "非奠基者；没有可归责的建国或统一主链贡献，第一项明确不适用，F=0。"),
        ("赵佶", "非奠基者；第一项源快照未收录不影响F=0。"),
    ]
    pending_second = [
        row
        for row in included
        if row["settlement_readiness"] == "PENDING_SECOND_ITEM_FORMAL_SETTLEMENT"
    ]
    assert len(pending_second) == 10
    assert all(not row["evidence_feasibility"]["second_item_formal"] for row in pending_second)
    assert all(not row["evidence_feasibility"]["second_item_score_snapshot_present"] for row in pending_second)
    assert all(row["evidence_feasibility"]["second_item_local_evidence_refs"] for row in pending_second)
    readjudicated = {
        row["ruler_name"]: row for row in composite_ready
        if row["ruler_name"] in {"刘祜", "刘志"}
    }
    assert set(readjudicated) == {"刘祜", "刘志"}
    assert {
        row["second_item_window_adjudication"]["status"]
        for row in readjudicated.values()
    } == {"ACCEPTED_AFTER_WINDOW_NARROWING"}
    pending_first = {
        row["ruler_name"]
        for row in included
        if row["first_item_readiness"] == "PENDING_FIRST_ITEM_FORMAL_SETTLEMENT"
    }
    assert pending_first == set()
    explicit_f0 = {
        row["ruler_name"]
        for row in included
        if row["first_item_readiness"] == "EXPLICIT_NOT_APPLICABLE_F0"
    }
    assert explicit_f0 == {"赵佶", "完颜永济", "载湉", "拓跋弘", "李安全", "李秉常", "李德旺"}
    jin_taizong = next(row for row in included if row["ruler_name"] == "完颜晟")
    assert jin_taizong["ruler_id"] == "RULER-JIN-TAIZONG"
    assert jin_taizong["source_item_names"]["first_item"] == "完颜吴乞买"
    assert jin_taizong["source_item_ids"]["first_item"] == "RULER-ROSTER-6FB8C85A5180DFB2"
    assert jin_taizong["first_item_readiness"] == "FORMAL_RECORD_PRESENT_ALIAS_NORMALIZED"
    assert jin_taizong["identity_resolution"]["legacy_id_refs"] == [
        "RULER-JIN-WANYAN-SHENG",
        "RULER-ROSTER-6FB8C85A5180DFB2",
    ]
    assert {row["ruler_name"] for row in payload["first_item_outside_candidate_pool"]} == {
        "塔不烟", "洪秀全", "耶律璟", "萧普速完", "黄巢"
    }


def test_checked_in_pool_matches_current_settlements() -> None:
    report = verify_canonical_ruler_pool(ROOT)
    assert report["included_count"] == 184
    assert report["composite_ready_count"] == 174
    assert report["pending_second_item_count"] == 10
    assert report["second_item_ranked_count"] == 174
    assert report["second_item_not_ranked_snapshot_count"] == 11
    assert report["pending_first_item_scope_count"] == 0
    assert report["pending_first_item_formal_settlement_count"] == 0
    assert report["first_item_outside_candidate_pool_count"] == 5


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
            / "docs/评分结算/第二项治国净收益/01-第二项治国净收益405分正式结算.json"
        ).read_text(encoding="utf-8")
    )
    second_by_name = {row["ruler_name"]: row for row in second["records"]}
    for name, suffix in expected.items():
        canonical_id = f"RULER-PUBLIC-{suffix}"
        assert by_name[name]["person_ref"] == canonical_id
        assert by_name[name]["legacy_person_refs"] == [f"RULER-ROSTER-{suffix}"]
        assert second_by_name[name]["ruler_id"] == canonical_id


def test_first_item_default_basis_is_disclosed_in_formal_limitations() -> None:
    c_payload = json.loads(
        (
            ROOT
            / "docs/评分结算/第一项创业与政权取得能力/军事夺取能力/01-第一项C军事夺取能力结算.json"
        ).read_text(encoding="utf-8")
    )
    formal_payload = json.loads(
        (
            ROOT
            / "docs/评分结算/第一项创业与政权取得能力/01-第一项创业与政权取得能力正式结算.json"
        ).read_text(encoding="utf-8")
    )
    formal_by_id = {row["ruler_id"]: row for row in formal_payload["records"]}
    defaults = [row for row in c_payload["records"] if row.get("default_applied")]
    assert {row["ruler_name"] for row in defaults} == {
        "李雄", "述律平", "冯跋", "刘龑", "黄巢", "刘玄"
    }
    for row in defaults:
        assert f"C：{row['default_basis']}" in formal_by_id[row["ruler_id"]]["limitations"]
