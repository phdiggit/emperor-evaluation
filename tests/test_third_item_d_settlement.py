from __future__ import annotations

from copy import deepcopy
import json
from math import sqrt
from pathlib import Path

import pytest

from emperor_v4.evaluation.third_item_d_settlement import (
    benefit_claim_ref,
    build_cycle_settlements,
    build_formal_linear_q_analysis,
    classify_legacy_unknown_cycle,
    p_penalty,
    render_markdown,
    validate_paired_anchor_batches,
    validate_paired_anchor_closures,
)


build_shadow = build_cycle_settlements


ROOT = Path(__file__).resolve().parents[1]


def _cycles() -> list[dict]:
    return json.loads(
        (ROOT / "config" / "third-item-d-cycle-adjudications.json").read_text(
            encoding="utf-8"
        )
    )["cycles"]


def _records() -> dict[str, dict]:
    return {
        row["investment_cycle_ref"]: row
        for row in build_shadow(_cycles())["records"]
    }


def _paired_payload() -> dict:
    return json.loads(
        (ROOT / "config/third-item-d-paired-anchor-closures.json").read_text(
            encoding="utf-8"
        )
    )


def _formula(row: dict, *, a_grade: int | None = None, **overrides: int) -> int:
    axes = {**row["parent_axes"], **overrides}
    a_value = row["asset_components"]["A_scoring"] if a_grade is None else a_grade
    return (
        4 * (axes["SB"] - axes["SN"])
        + 3 * (axes["BCP"] - axes["BCN"])
        + 2 * axes["WR"]
        - p_penalty(axes["P"]) - 4 * axes["S"] - axes["M"] - a_value
    )


def _asset_cycle(*, reusable: int, consumed: int, lost: int, scoring: int) -> dict:
    suffix = f"{reusable}-{consumed}-{lost}-{scoring}"
    return {
        "sample_label": "资产组件", "ruler_name": "测试",
        "evaluation_subject_ref": "TEST",
        "default_cost_burden_bearer": "TEST",
        "default_benefit_recipient": "TEST",
        "investment_cycle_ref": f"ASSET-{suffix}",
        "strategic_result_chain_refs": ["CHAIN-ASSET"],
        "boundary_decision": {
            "mode": "FIRST_CYCLE_IN_CHAIN", "reason": "独立组件校验",
            "source_refs": ["SRC-ASSET"],
        },
        "cost_axis_adjudications": {
            "M": {
                "grade": 1, "supporting_fact_refs": [f"M-{suffix}"],
                "source_refs": ["SRC-ASSET"], "basis": "局部动员",
                "gate_evidence": {"scope": "local", "duration": "short"},
            }
        },
        "asset_scoring_adjudication": {
            "parent_components": {
                "gross_commitment_grade": 3,
                "reusable_input_grade": reusable,
                "consumed_asset_grade": consumed,
                "lost_or_destroyed_asset_grade": lost,
            },
            "selected_grade": scoring, "lower_grade": scoring,
            "upper_grade": scoring, "confidence": "HIGH",
            "supporting_fact_refs": [f"A-{suffix}"],
            "source_refs": ["SRC-ASSET"], "basis": "组件边界测试",
        },
        "benefit_axis_gates": {},
        "ordered_phases": [{
            "phase_ref": f"PHASE-{suffix}", "start": "1000-01-01",
            "end": "1000-12-31", "source_refs": ["SRC-ASSET"],
            "cost_facts": [
                {"fact_ref": f"M-{suffix}", "fact_type": "MOBILIZATION",
                 "mobilization_input_ref": f"INPUT-{suffix}", "grade": 1,
                 "source_refs": ["SRC-ASSET"]},
                {"fact_ref": f"A-{suffix}", "fact_type": "ASSET_BURDEN",
                 "asset_object_ref": f"OBJECT-{suffix}", "gross_grade": 3,
                 "reusable_grade": reusable, "consumed_grade": consumed,
                 "lost_grade": lost, "source_refs": ["SRC-ASSET"]},
            ],
            "benefit_facts": [],
        }],
    }


def _state_cycle(
    ref: str, *, from_state: str, to_state: str,
    start: str, end: str, prior_ref: str | None = None,
) -> dict:
    cycle = _asset_cycle(reusable=0, consumed=0, lost=0, scoring=0)
    cycle["sample_label"] = ref
    cycle["investment_cycle_ref"] = ref
    phase = cycle["ordered_phases"][0]
    phase["phase_ref"] = f"PHASE-{ref}"
    phase["start"], phase["end"] = start, end
    for fact in phase["cost_facts"]:
        fact["fact_ref"] = f"{fact['fact_ref']}-{ref}"
        if fact.get("mobilization_input_ref"):
            fact["mobilization_input_ref"] += f"-{ref}"
        if fact.get("asset_object_ref"):
            fact["asset_object_ref"] += f"-{ref}"
    m_ref, a_ref = (fact["fact_ref"] for fact in phase["cost_facts"])
    cycle["cost_axis_adjudications"]["M"]["supporting_fact_refs"] = [m_ref]
    cycle["asset_scoring_adjudication"]["supporting_fact_refs"] = [a_ref]
    claim_ref = f"BENEFIT-{ref}"
    phase["benefit_facts"] = [{
        "fact_ref": claim_ref, "historical_object_ref": "OBJECT-STATE-CHAIN",
        "from_state": from_state, "to_state": to_state,
        "benefit_window_start": start, "benefit_window_end": end,
        "axis_grades": {"SB": 2}, "source_refs": ["SRC-STATE"],
    }]
    cycle["benefit_axis_gates"] = {
        "SB": {
            "grade": 2, "supporting_fact_refs": [claim_ref],
            "source_refs": ["SRC-STATE"], "basis": "状态链测试",
            "gate_evidence": {"scope": "test", "persistence": "test"},
        }
    }
    if prior_ref:
        cycle["boundary_decision"] = {
            "mode": "SPLIT_FROM_PREVIOUS_INVESTMENT",
            "prior_investment_cycle_ref": prior_ref,
            "prior_force_withdrawn_or_demobilized": True,
            "new_authorization": True, "new_mobilization": True,
            "reason": "状态链后轮", "source_refs": ["SRC-STATE"],
        }
    return cycle


def test_config_uses_explicit_subjects_and_axis_adjudication_not_parent_axes() -> None:
    for cycle in _cycles():
        assert "parent_axes" not in cycle
        assert cycle["evaluation_subject_ref"]
        assert cycle["default_cost_burden_bearer"] == cycle["evaluation_subject_ref"]
        assert cycle["default_benefit_recipient"] == cycle["evaluation_subject_ref"]
        assert cycle["cost_axis_adjudications"]["M"]["gate_evidence"]
        assert cycle["asset_scoring_adjudication"]["basis"]
        if "wr_simplified_adjudication" in cycle:
            assert {
                "asset_base_grade", "transfer_mode", "realization_retention",
            } <= set(cycle["wr_simplified_adjudication"])


def test_xueyantuo_terminal_sb5_is_composite_and_subject_direction_is_closed() -> None:
    row = _records()["CAMPAIGN-TANG-XUEYANTUO-645-647"]
    claims = {claim["fact_ref"]: claim for claim in row["benefit_claims"]}
    assert claims["BENEFIT-XUE-646-THREAT-END"]["axis_grades"]["SB"] == 4
    assert claims["BENEFIT-XUE-647-MONGLIAN-INTEGRATION"]["axis_grades"]["SB"] == 3
    assert set(row["benefit_axis_gates"]["SB"]["supporting_fact_refs"]) == {
        "BENEFIT-XUE-646-THREAT-END",
        "BENEFIT-XUE-647-MONGLIAN-INTEGRATION",
    }
    assert row["parent_axes"]["SB"] == 5
    post = claims["BENEFIT-XUE-647-POST-SERVICE"]
    assert post["benefit_provider"] == "SUBMITTED_TRIBES"
    assert post["effective_recipient"] == "TANG"
    assert row["asset_components"]["asset_object_refs"] == [
        "TANG-XUE-BESTOWAL-647"
    ]
    assert "不混入诸部供驿负担" in row["asset_components"]["A_scoring_basis"]
    actual = claims["BENEFIT-XUE-647-ACTUAL-TRIBUTE"]
    future = claims["BENEFIT-XUE-647-SABLE-OBLIGATION"]
    assert actual["resource_realization_status"] == "REALIZED_QUANTITY_UNRECORDED"
    assert actual["axis_grades"]["WR"] == 1
    assert future["resource_realization_status"] == "INSTITUTIONAL_OBLIGATION_NOT_CAPITALIZED"
    assert future["axis_grades"]["WR"] == 0
    assert row["asset_components"]["A_scoring_lower"] == 0
    assert row["asset_components"]["A_scoring_upper"] == 1
    assert row["parent_axes"]["P"] == 1
    p_fact = next(
        fact for phase in row["ordered_phase_facts"]
        for fact in phase["cost_facts"] if fact["fact_ref"] == "COST-XUE-646-P"
    )
    assert (p_fact["equivalent_min"], p_fact["equivalent_max"]) == (1, 99)
    assert "敌军斩五千余、俘三万余不得反推唐方损失" in p_fact["basis"]
    assert "完整事件边界内已有围城或持续相持" not in p_fact["basis"]
    assert row["q_candidate_range"] == {
        "lower": 29, "upper": 32,
        "boundary_driver": "EXPLICIT_AXIS_AND_A_ADJUDICATION_BOUNDS",
    }


def test_lingbei_preserves_sb3_and_asset_uncertainty_as_joint_q_boundary() -> None:
    row = _records()["MTJ-MING-NORTHERN-WAR-1372"]
    ranges = [
        (fact["equivalent_min"], fact["equivalent_max"])
        for phase in row["ordered_phase_facts"] for fact in phase["cost_facts"]
        if fact["fact_type"] == "PERSONNEL_LOSS"
    ]
    low, high = sum(item[0] for item in ranges), sum(item[1] for item in ranges)
    assert (low, high) == (21101, 71097)
    assert row["personnel_rollup"]["center_equivalent"] == round(sqrt(low * high), 2)
    assert row["parent_axes"] == {
        "P": 4, "S": 0, "M": 4, "SB": 3, "SN": 3,
        "BCP": 4, "BCN": 0, "WR": 4,
    }
    assert row["benefit_axis_gates"]["SB"]["lower_grade"] == 3
    assert row["benefit_axis_gates"]["SB"]["upper_grade"] == 4
    assert row["asset_components"]["A_scoring_confidence"] == "LOW"
    assert row["asset_components"]["A_scoring_lower"] == 0
    assert row["asset_components"]["A_scoring_upper"] == 3
    assert _formula(row, SB=3, WR=4, a_grade=3) == -3
    assert _formula(row, SB=4, WR=4, a_grade=3) == 1
    assert row["wr_evidence_adjudication"]["selected_grade"] == 4
    assert row["axis_candidate_ranges"]["WR"] == {"lower": 4, "upper": 4}
    assert row["q_candidate_range"]["lower"] == -3
    assert row["q_candidate_range"]["upper"] == 4


def test_s_rollup_keeps_full_damage_trajectory_after_recovery() -> None:
    cycle = deepcopy(next(item for item in _cycles() if item[
        "investment_cycle_ref"
    ] == "MTJ-MING-SICHUAN-PENGPUGUI-1379"))
    recovery_ref = "COST-PENG-S-RECOVERY"
    cycle["ordered_phases"].append({
        "phase_ref": "PHASE-PENG-RECOVERY", "start": "1381-01-01",
        "end": "1381-12-31", "source_refs": ["SRC-PENG-RECOVERY"],
        "cost_facts": [{
            "fact_ref": recovery_ref, "fact_type": "SYSTEM_DAMAGE",
            "affected_system_ref": "MING-SICHUAN-FOURTEEN-COUNTIES",
            "gross_damage_grade": 1, "flow_disruption_grade": 0,
            "terminal_residual_grade": 0, "source_refs": ["SRC-PENG-RECOVERY"],
        }], "benefit_facts": [],
    })
    cycle["cost_axis_adjudications"]["S"]["supporting_fact_refs"].append(recovery_ref)
    row = build_shadow([cycle])["records"][0]
    trajectory = row["system_damage_rollup"]["damage_trajectories"][
        "MING-SICHUAN-FOURTEEN-COUNTIES"
    ]
    assert len(trajectory) == 2
    assert [fact["gross_damage_grade"] for fact in trajectory] == [4, 1]
    assert row["system_damage_rollup"]["gross_damage_grade"] == 4
    assert row["system_damage_rollup"]["S_floor_from_realized_damage"] == 4
    assert row["parent_axes"]["S"] == 4
    cycle["cost_axis_adjudications"]["S"]["grade"] = 0
    with pytest.raises(ValueError, match="父级S低于既发损害保底"):
        build_shadow([cycle])


def test_parent_s_cannot_short_circuit_realized_gross_and_flow_damage() -> None:
    cycle = deepcopy(next(item for item in _cycles() if item[
        "investment_cycle_ref"
    ] == "MTJ-MING-SICHUAN-PENGPUGUI-1379"))
    cycle["cost_axis_adjudications"]["S"]["grade"] = 0
    with pytest.raises(ValueError, match="父级S低于既发损害保底"):
        build_shadow([cycle])
    cycle["cost_axis_adjudications"]["S"]["grade"] = 3
    with pytest.raises(ValueError, match="父级S低于既发损害保底"):
        build_shadow([cycle])


def test_s_never_becomes_unknown() -> None:
    cycle = deepcopy(next(item for item in _cycles() if item[
        "investment_cycle_ref"
    ] == "CAMPAIGN-TANG-SHIP-LABOR-648"))
    system_fact = next(fact for fact in cycle["ordered_phases"][0]["cost_facts"]
                       if fact["fact_type"] == "SYSTEM_DAMAGE")
    system_fact["gross_damage_grade"] = None
    with pytest.raises(ValueError, match="S事实三组件不得UNKNOWN"):
        build_shadow([cycle])


def test_no_generic_two_peer_plus_one_exists_for_m_or_benefits() -> None:
    lingbei = deepcopy(next(item for item in _cycles() if item[
        "investment_cycle_ref"
    ] == "MTJ-MING-NORTHERN-WAR-1372"))
    lingbei["cost_axis_adjudications"]["M"]["grade"] = 3
    assert build_shadow([lingbei])["records"][0]["parent_axes"]["M"] == 3
    xue_cycles = deepcopy(_cycles()[:2])
    xue_cycles[1]["benefit_axis_gates"]["SB"]["grade"] = 4
    row = build_shadow(xue_cycles)["records"][1]
    assert row["parent_axes"]["SB"] == 4


def test_null_asset_components_keep_bounded_scoring_and_q() -> None:
    row = _records()["CAMPAIGN-TANG-XUEYANTUO-645-647"]
    assets = row["asset_components"]
    assert assets["gross_commitment_grade"] is None
    assert assets["consumed_asset_grade"] is None
    assert assets["A_scoring"] == 0
    assert assets["A_scoring_lower"] == 0
    assert assets["A_scoring_upper"] == 1
    assert assets["A_scoring_confidence"] == "LOW"
    assert row["q_contribution"] == 30
    assert row["q_candidate_range"]["lower"] == 29
    assert row["q_candidate_range"]["upper"] == 32


def test_same_gross_destroyed_asset_scores_no_lower_than_reusable_asset() -> None:
    reusable = build_shadow([_asset_cycle(
        reusable=3, consumed=1, lost=0, scoring=1
    )])["records"][0]
    destroyed = build_shadow([_asset_cycle(
        reusable=0, consumed=0, lost=3, scoring=3
    )])["records"][0]
    assert destroyed["asset_components"]["A_scoring"] >= reusable[
        "asset_components"
    ]["A_scoring"]
    copied = _asset_cycle(reusable=2, consumed=1, lost=3, scoring=3)
    with pytest.raises(ValueError, match="gross投入整档复制"):
        build_shadow([copied])


def test_two_independent_same_grade_assets_require_explicit_component_regrade() -> None:
    cycle = _asset_cycle(reusable=1, consumed=1, lost=0, scoring=1)
    phase = cycle["ordered_phases"][0]
    second = deepcopy(next(
        fact for fact in phase["cost_facts"] if fact["fact_type"] == "ASSET_BURDEN"
    ))
    second["fact_ref"] += "-SECOND"
    second["asset_object_ref"] += "-SECOND"
    phase["cost_facts"].append(second)
    cycle["asset_scoring_adjudication"]["supporting_fact_refs"].append(
        second["fact_ref"]
    )
    with pytest.raises(ValueError, match="多个独立资产对象必须显式重定档"):
        build_shadow([cycle])

    cycle["asset_scoring_adjudication"]["multi_object_component_gate"] = {
        "asset_object_refs": [
            fact["asset_object_ref"] for fact in phase["cost_facts"]
            if fact["fact_type"] == "ASSET_BURDEN"
        ],
        "aggregation_basis": "两个局部对象合计仍未跨过父级A2数量门槛",
        "regrade_status": "REVIEWED_REMAINS_GRADE_1",
    }
    row = build_shadow([cycle])["records"][0]
    assert row["asset_components"]["gross_commitment_grade"] == 3
    assert len(row["asset_components"]["asset_object_refs"]) == 2


def test_state_dedupe_uses_transition_and_continuity_not_window_overlap() -> None:
    first = _state_cycle(
        "STATE-1", from_state="A", to_state="B",
        start="1000-01-01", end="1001-12-31",
    )
    continuous = _state_cycle(
        "STATE-2", from_state="B", to_state="C",
        start="1001-01-01", end="1002-12-31", prior_ref="STATE-1",
    )
    payload = build_shadow([first, continuous])
    continuous_claim = payload["records"][1]["benefit_claims"][0]
    assert continuous_claim["consumed"] is True
    assert len(continuous_claim["overlapping_prior_claim_refs"]) == 1
    duplicate = _state_cycle(
        "STATE-3", from_state="A", to_state="B",
        start="1001-01-01", end="1003-12-31", prior_ref="STATE-2",
    )
    payload = build_shadow([first, continuous, duplicate])
    assert payload["records"][2]["benefit_claims"][0]["consumed"] is False
    broken = _state_cycle(
        "STATE-4", from_state="X", to_state="D",
        start="1001-01-01", end="1002-12-31", prior_ref="STATE-1",
    )
    with pytest.raises(ValueError, match="收益状态链不连续"):
        build_shadow([first, broken])


def test_claim_identity_is_axis_free_and_requires_from_to_state() -> None:
    claim = _state_cycle(
        "IDENTITY", from_state="A", to_state="B",
        start="1000-01-01", end="1000-12-31",
    )["ordered_phases"][0]["benefit_facts"][0]
    assert not benefit_claim_ref(claim).endswith(("::SB", "::BCP", "::WR"))
    del claim["to_state"]
    with pytest.raises(ValueError, match="收益claim身份未闭合"):
        benefit_claim_ref(claim)


def test_cost_bearer_and_benefit_recipient_are_gated() -> None:
    cycle = deepcopy(_cycles()[1])
    cycle["ordered_phases"][0]["cost_facts"][0]["burden_bearer"] = "TRIBES"
    with pytest.raises(ValueError, match="成本承担主体不属于评价主体"):
        build_shadow([_cycles()[0], cycle])
    cycle = deepcopy(_cycles()[1])
    cycle["ordered_phases"][0]["benefit_facts"][0]["recipient"] = "TRIBES"
    with pytest.raises(ValueError, match="收益接收主体不属于评价主体"):
        build_shadow([_cycles()[0], cycle])


def test_linear_q_and_formal_write_gate_remain_closed() -> None:
    payload = build_shadow(_cycles())
    rows = {row["sample_label"]: row for row in payload["records"]}
    for row in rows.values():
        if row["q_contribution"] is None:
            assert row["parent_axes"]["WR"] is None
            assert row["q_candidate_range"]["lower"] is None
            assert row["q_candidate_range"]["upper"] is None
            continue
        assert row["q_contribution"] == _formula(row)
    assert sum(row["q_contribution"] is None for row in rows.values()) == 0
    assert payload["formal_score_write"] is False
    assert payload["calibration_status"] == "CALIBRATION_PENDING"
    assert "Q候选" in render_markdown(payload)


def test_land_or_administration_cannot_be_relabelled_as_wr() -> None:
    cycles = deepcopy(_cycles()[3:5])
    claim = cycles[1]["ordered_phases"][0]["benefit_facts"][0]
    claim["axis_grades"]["WR"] = 1
    claim["resource_realization_status"] = "REALIZED_AND_USABLE"
    claim["resource_kind"] = "LAND_OR_ADMIN_CONTROL"
    cycles[1]["benefit_axis_gates"]["WR"] = {
        "grade": 1, "supporting_fact_refs": [claim["fact_ref"]],
        "source_refs": ["SRC"], "basis": "非法WR",
        "gate_evidence": {"resource": "land"},
    }
    with pytest.raises(ValueError, match="土地或设治只进BCP"):
        build_shadow(cycles)


BASELINE_Q = {
    "CAMPAIGN-TANG-XUEYANTUO-641": (6, 6, 8),
    "CAMPAIGN-TANG-XUEYANTUO-645-647": (30, 29, 32),
    "MTJ-MING-NORTHERN-WAR-1372": (0, -3, 4),
    "CAMPAIGN-TANG-HELU-651-656": (-11, -11, -9),
    "CAMPAIGN-TANG-HELU-657-658": (23, 21, 27),
    "MTJ-MING-BOZHOU-1594": (4, 4, 4),
    "MTJ-MING-BOZHOU-1596-1600": (-6, -6, -6),
    "CAMPAIGN-TANG-GOGURYEO-644-645": (2, 2, 2),
    "MTJ-MING-SICHUAN-PENGPUGUI-1379": (-16, -16, -16),
    "CAMPAIGN-TANG-SHIP-LABOR-648": (-5, -5, -5),
    "XZTJ-050-NONGZHIGAO-NANTIAN-YONGZHOU-1049": (-12, -12, -12),
}


def test_original_eleven_samples_do_not_regress() -> None:
    records = _records()
    assert set(BASELINE_Q) <= set(records)
    for ref, expected in BASELINE_Q.items():
        row = records[ref]
        assert (
            row["q_contribution"],
            row["q_candidate_range"]["lower"],
            row["q_candidate_range"]["upper"],
        ) == expected


def test_xue_and_peng_personnel_loss_horizontal_calibration_matches_local_sources() -> None:
    rows = _records()
    xue = rows["CAMPAIGN-TANG-XUEYANTUO-645-647"]
    peng = rows["MTJ-MING-SICHUAN-PENGPUGUI-1379"]
    assert xue["parent_axes"]["P"] == 1
    assert peng["parent_axes"]["P"] == 2
    assert peng["parent_axes"]["P"] >= xue["parent_axes"]["P"]
    peng_fact = next(
        fact for phase in peng["ordered_phase_facts"]
        for fact in phase["cost_facts"] if fact["fact_ref"] == "COST-PENG-P"
    )
    assert (peng_fact["equivalent_min"], peng_fact["equivalent_max"]) == (100, 500)
    assert all(term in peng_fact["basis"] for term in (
        "顾师胜", "民兵力战", "十四州县", "普亮", "不能克", "丁玉", "P2估",
    ))

    public = json.loads((
        ROOT / "docs" / "公共成果" / "军事" / "01-战役登记" / "ming-09.json"
    ).read_text(encoding="utf-8"))
    phases = []

    def collect(value: object) -> None:
        if isinstance(value, dict):
            if value.get("evaluation_subject_phase") == "明朝眉县—四川地方军民 × 叛乱扩散受损阶段":
                phases.append(value)
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(public)
    assert len(phases) == 1
    assert phases[0]["cost_axes"]["P"] == "P2估"
    assert "100—500死亡当量" in phases[0]["P_inference"]["basis"]

    formal_text = (
        ROOT / "docs" / "评分结算" / "第三项军事与边疆净收益"
        / "军事成本收益比" / "01-皇帝D项正式结算.json"
    ).read_text(encoding="utf-8")
    anchor = formal_text.index(
        '"canonical_parent_cycle_ref": "MTJ-MING-SICHUAN-PENGPUGUI-1379"'
    )
    assert '"P": 2' in formal_text[anchor:anchor + 700]


def test_p_basis_root_cause_scan_and_parent_chain_gate() -> None:
    payload = build_shadow(_cycles())
    audit = payload["sample_statistics"]["p_basis_audit"]
    assert audit["computed_from_records"] is True
    assert audit["record_count"] == 25
    assert audit["fact_semantically_reviewed_count"] == 4
    assert audit["formal_value_match_only_count"] == 13
    assert audit["unreviewed_count"] == 8
    assert audit["basis_missing_fact_count"] == 11
    assert audit["canonical_value_not_located_count"] == 7
    assert audit["discovered_error_lower_bound_count"] == 4
    assert audit["upstream_unresolved_conflict_count"] == 3
    assert audit["formal_value_divergence_unreviewed_count"] == 1
    assert "error_rate" not in audit
    records = {item["investment_cycle_ref"]: item for item in audit["records"]}
    xue = records["CAMPAIGN-TANG-XUEYANTUO-645-647"]
    assert xue["parent_p_grade"] == 1
    assert xue["review_status"] == "FACT_SEMANTICALLY_REVIEWED"
    assert xue["canonical_status"] == "UPSTREAM_CONFLICT_SHADOW_OVERRIDE_ONLY"
    assert xue["upstream_unresolved"] is True
    peng = records["MTJ-MING-SICHUAN-PENGPUGUI-1379"]
    assert peng["parent_p_grade"] == 2
    assert peng["review_status"] == "FACT_SEMANTICALLY_REVIEWED"
    assert peng["canonical_status"] == "FORMAL_VALUE_MATCH_ONLY"
    assert all(
        item["canonical_refs"]
        for item in audit["records"]
        if item["review_status"] != "UNREVIEWED"
    )

    source = (
        ROOT / "src" / "emperor_v4" / "evaluation" / "third_item_d_settlement.py"
    ).read_text(encoding="utf-8")
    assert "P_SHADOW_AUDIT_EXPECTATIONS" not in source
    assert "P_FORMAL_SAME_REF_GRADES" not in source
    report = render_markdown(payload)
    assert "P轴25例只读根因扫描" in report
    assert "当前已发现错误下限=4/25" in report
    assert "样本错误率估计" not in report
    assert "UPSTREAM_CONFLICT_SHADOW_OVERRIDE_ONLY" in report
    assert "原卡错误仍保留" in report
    assert "冲突性同对象双算：0；合法互补共存：1" in report

    volume = (
        ROOT / "docs" / "史料通读产物" / "唐以前编年" / "唐"
        / "卷198-通读总结.md"
    ).read_text(encoding="utf-8")
    assert "P_scoring=P2估" in volume
    assert "推定依据=完整事件边界内已有围城或持续相持" in volume
    assert "### WAR-LEAD-TANG-TIELE-INTEGRATION" in volume
    terminal = volume.split("### WAR-LEAD-TANG-TIELE-INTEGRATION", 1)[1]
    assert "P0〔本父链未载唐方人员死亡" in terminal


def test_information_rich_sample_coverage_and_ruler_quota() -> None:
    payload = build_shadow(_cycles())
    rows = payload["records"]
    assert 23 <= len(rows) <= 29
    assert sum(row["parent_axes"]["SB"] >= 4 for row in rows) >= 4
    assert sum(row["parent_axes"]["BCP"] >= 4 for row in rows) >= 4
    assert sum(row["axis_candidate_ranges"]["WR"]["upper"] >= 4 for row in rows) >= 4
    assert sum(max(row["parent_axes"]["P"], row["parent_axes"]["S"]) >= 4 for row in rows) >= 4
    assert sum(row["event_type"] == "INTERNAL_RESTORATION" for row in rows) >= 3
    assert sum(
        row["asset_components"]["component_split_status"]
        == "UNRESOLVED_REUSE_LOSS_DESTRUCTION_SPLIT"
        or len(row["asset_components"]["asset_object_refs"]) > 1
        for row in rows
    ) >= 3
    split_chains = {
        tuple(row["strategic_result_chain_refs"])
        for row in rows
        if row["boundary_decision"]["mode"] == "SPLIT_FROM_PREVIOUS_INVESTMENT"
    }
    assert len(split_chains) >= 3
    ruler_counts = {
        ruler: sum(row["ruler_name"] == ruler for row in rows)
        for ruler in {row["ruler_name"] for row in rows}
    }
    assert ruler_counts["李世民"] >= 4
    assert ruler_counts["朱元璋"] >= 4
    assert len(ruler_counts) >= 6
    assert all(row["event_type"] != "UNCLASSIFIED" for row in rows)


def test_new_samples_close_high_axis_fact_gates_and_subject_direction() -> None:
    payload = build_shadow(_cycles())
    rows = payload["records"][len(BASELINE_Q):]
    assert len(rows) == 14
    for row in rows:
        subject = next(
            cycle["evaluation_subject_ref"] for cycle in _cycles()
            if cycle["investment_cycle_ref"] == row["investment_cycle_ref"]
        )
        for phase in row["ordered_phase_facts"]:
            assert all(
                fact["effective_burden_bearer"] == subject
                for fact in phase["cost_facts"]
            )
            assert all(
                fact["effective_recipient"] == subject
                for fact in phase["benefit_facts"]
            )
        for axis, gate in row["benefit_axis_gates"].items():
            assert gate["supporting_fact_refs"]
            assert gate["source_refs"]
            assert gate["gate_evidence"]
            if gate["grade"] >= 4:
                assert gate["basis"]
    central = next(row for row in rows if row["investment_cycle_ref"] == "PARENT-HEHUANG-CENTRAL-RECEPTION-848-849")
    guiyi = next(row for row in rows if row["investment_cycle_ref"] == "PARENT-HEHUANG-GUIYI-851")
    assert central["parent_axes"] == {
        "P": 1, "S": 0, "M": 2, "SB": 3, "SN": 0,
        "BCP": 3, "BCN": 0, "WR": 2,
    }
    assert central["asset_components"]["A_scoring"] == 2
    assert central["q_contribution"] == 17
    assert central["q_candidate_range"] == {
        "lower": 16, "upper": 17,
        "boundary_driver": "EXPLICIT_AXIS_AND_A_ADJUDICATION_BOUNDS",
    }
    assert guiyi["parent_axes"] == {
        "P": 1, "S": 0, "M": 2, "SB": 4, "SN": 0,
        "BCP": 4, "BCN": 0, "WR": 0,
    }
    assert guiyi["asset_components"]["A_scoring"] == 1
    assert guiyi["q_contribution"] == 21
    assert guiyi["q_candidate_range"] == {
        "lower": 20, "upper": 21,
        "boundary_driver": "EXPLICIT_AXIS_AND_A_ADJUDICATION_BOUNDS",
    }
    assert central["wr_evidence_adjudication"]["selected_grade"] == 2
    assert guiyi["wr_evidence_adjudication"]["status"] == "CONFIRMED_NONE"
    sarhu = next(row for row in rows if row["investment_cycle_ref"] == "MTJ-MING-QING-SARHU-1619")
    assert sarhu["parent_axes"]["P"] == 4
    assert "不沿用旧P5" in sarhu["ordered_phase_facts"][0]["cost_facts"][0]["basis"]


def test_hehuang_state_scope_split_and_claim_symmetry_gates() -> None:
    cycles = _cycles()
    rows = _records()
    central = rows["PARENT-HEHUANG-CENTRAL-RECEPTION-848-849"]
    guiyi = rows["PARENT-HEHUANG-GUIYI-851"]

    assert central["strategic_result_chain_refs"] == guiyi[
        "strategic_result_chain_refs"
    ] == ["CHAIN-TANG-HEHUANG-RECOVERY"]
    boundary = guiyi["boundary_decision"]
    assert boundary["prior_investment_cycle_ref"] == central["investment_cycle_ref"]
    assert boundary["prior_result_closed"] is True
    assert boundary["independent_force_and_logistics"] is True
    assert boundary["new_authorization"] is True
    assert boundary["new_mobilization"] is True

    for row in (central, guiyi):
        scope = row["national_scope_adjudication"]
        assert scope["status"] == "NATIONAL_COST_RESULT_SYMMETRY"
        assert scope["cost_community"] == scope["benefit_community"] == "TANG"
        assert row["parent_axes"]["P"] == 1
        assert row["personnel_rollup"]["equivalent_min"] > 0
        assert row["q_contribution"] == _formula(row)
        assert row["system_damage_rollup"]["zero_adjudication"]["status"] == (
            "NO_SYSTEM_DAMAGE_BRIDGE_FACT"
        )

    assert {claim["benefit_claim_ref"] for claim in central["benefit_claims"]}.isdisjoint(
        claim["benefit_claim_ref"] for claim in guiyi["benefit_claims"]
    )
    assert build_shadow(cycles)["D_business_audit"][
        "consumed_cross_parent_duplicate_claim_count"
    ] == 0

    guiyi_input = deepcopy(next(
        cycle for cycle in cycles
        if cycle["investment_cycle_ref"] == "PARENT-HEHUANG-GUIYI-851"
    ))
    guiyi_input["authorization_discount"] = 0.5
    with pytest.raises(ValueError, match="禁止个人贡献折减字段"):
        build_shadow([guiyi_input])

    guiyi_input.pop("authorization_discount")
    guiyi_input["national_scope_adjudication"]["cost_community"] = "LOCAL_ONLY"
    with pytest.raises(ValueError, match="成本承担共同体与收益接收共同体不对称"):
        build_shadow([guiyi_input])


def test_xueyantuo_641_s0_is_affirmative_not_source_silence() -> None:
    row = _records()["CAMPAIGN-TANG-XUEYANTUO-641"]
    assert row["parent_axes"]["S"] == 0
    assert row["system_damage_reaudit"] is None
    assert row["system_damage_rollup"]["zero_adjudication"]["status"] == (
        "NO_SYSTEM_DAMAGE_BRIDGE_FACT"
    )
    basis = row["system_damage_rollup"]["zero_adjudication"]["basis"]
    assert "无败绩、战线未退缩" in basis
    assert "并非因史料沉默机械归零" in basis
    assert all(
        fact["fact_type"] != "SYSTEM_DAMAGE"
        for phase in row["ordered_phase_facts"] for fact in phase["cost_facts"]
    )
    assert row["q_contribution"] == 6
    assert row["q_candidate_range"] == {
        "lower": 6, "upper": 8,
        "boundary_driver": "EXPLICIT_AXIS_AND_A_ADJUDICATION_BOUNDS",
    }
    report = render_markdown(build_shadow(_cycles()))
    assert "S轴桥梁召回轻量审计" in report
    assert "未处置C/D/E：0" in report

    for cycle in _cycles():
        if cycle["investment_cycle_ref"] == "CAMPAIGN-TANG-XUEYANTUO-641":
            continue
        assert "WAR-LEAD-TANG-XUEYANTUO-641" not in json.dumps(
            cycle, ensure_ascii=False
        )


def test_four_s_recall_cases_feed_generic_s_and_q_candidate_ranges() -> None:
    rows = _records()
    expected = {
        "CAMPAIGN-TANG-XUEYANTUO-641": (0, 0, 0, 6, 6, 8),
        "MTJ-OIRAT-MING-1449-BEIJING-ZHUQIYU-WINDOW": (1, 1, 2, 11, 6, 13),
        "CAMPAIGN-TANG-KHITAN-696-700": (5, 4, 5, -32, -33, -28),
        "XZTJ-SOUTHERNSONG-YANGYAO-DONGTING-1133-1135": (2, 1, 2, 3, 3, 7),
    }
    for ref, (selected_s, lower_s, upper_s, q, lower_q, upper_q) in expected.items():
        row = rows[ref]
        assert row["parent_axes"]["S"] == selected_s
        assert row["axis_candidate_ranges"]["S"] == {
            "lower": lower_s, "upper": upper_s,
        }
        assert row["q_contribution"] == q
        assert row["q_candidate_range"]["lower"] == lower_q
        assert row["q_candidate_range"]["upper"] == upper_q


def test_s_bridge_recall_audit_closes_cde_and_removes_resolved_b_records() -> None:
    payload = build_shadow(_cycles())
    audit = payload["D_business_audit"]
    assert audit["investment_cycle_count"] == len(_cycles())
    assert audit["system_damage_bridge_recall_count"] == 3
    assert audit["system_damage_bridge_unresolved_cde_count"] == 0
    assert audit["system_damage_bridge_bounded_b_pending_count"] == 0
    records = {
        item["investment_cycle_ref"]: item
        for item in audit["system_damage_bridge_records"]
    }
    assert set(records) == {
        "MTJ-OIRAT-MING-1449-BEIJING-ZHUQIYU-WINDOW",
        "CAMPAIGN-TANG-KHITAN-696-700",
        "XZTJ-SOUTHERNSONG-YANGYAO-DONGTING-1133-1135",
    }
    assert all(records[ref]["recall_required"] for ref in (
        "MTJ-OIRAT-MING-1449-BEIJING-ZHUQIYU-WINDOW",
        "CAMPAIGN-TANG-KHITAN-696-700",
        "XZTJ-SOUTHERNSONG-YANGYAO-DONGTING-1133-1135",
    ))
    assert "MTJ-OIRAT-MING-1449-TUMU-ZHUQIZHEN-WINDOW" not in records
    assert "MTJ-MING-BOZHOU-1596-1600" not in records
    assert "XZTJ-SONG-XIA-FIVE-ROUTE-1081" not in records
    rows = {row["investment_cycle_ref"]: row for row in payload["records"]}
    for ref in (
        "MTJ-OIRAT-MING-1449-TUMU-ZHUQIZHEN-WINDOW",
        "MTJ-MING-BOZHOU-1596-1600",
    ):
        assert rows[ref]["parent_axes"]["S"] == 3
        assert rows[ref]["axis_candidate_ranges"]["S"] == {
            "lower": 3, "upper": 3,
        }


def test_sarhu_s_bridge_uses_only_its_own_case_lineage() -> None:
    row = _records()["MTJ-MING-QING-SARHU-1619"]
    expected = {
        "MTJ-MING-QING-FUSHUN-1618", "MTJ-MING-QING-SARHU-1619",
        "MTJ-MING-QING-KAIYUAN-1619", "MTJ-MING-QING-TIELING-1619",
    }
    parent = row["system_damage_rollup"]["parent_adjudication"]
    fact = next(
        fact for phase in row["ordered_phase_facts"] for fact in phase["cost_facts"]
        if fact["fact_type"] == "SYSTEM_DAMAGE"
    )
    assert set(parent["source_refs"]) == expected
    assert set(fact["source_refs"]) == expected
    assert "WAR-LEAD-TANG-XUEYANTUO-641" not in json.dumps(
        {"parent": parent, "fact": fact}, ensure_ascii=False
    )


def test_tumu_and_beijing_are_split_at_the_ruler_window() -> None:
    rows = _records()
    tumu = rows["MTJ-OIRAT-MING-1449-TUMU-ZHUQIZHEN-WINDOW"]
    beijing = rows["MTJ-OIRAT-MING-1449-BEIJING-ZHUQIYU-WINDOW"]
    assert tumu["ruler_name"] == "朱祁镇"
    assert beijing["ruler_name"] == "朱祁钰"
    assert tumu["strategic_result_chain_refs"] == beijing["strategic_result_chain_refs"]
    assert beijing["boundary_decision"]["prior_investment_cycle_ref"] == tumu[
        "investment_cycle_ref"
    ]
    assert tumu["parent_axes"]["SB"] == tumu["parent_axes"]["BCP"] == 0
    assert beijing["parent_axes"]["SN"] == beijing["parent_axes"]["BCN"] == 0
    assert {claim["fact_ref"] for claim in tumu["benefit_claims"]} == {
        "BENEFIT-TUMU-LOSS"
    }
    assert {claim["fact_ref"] for claim in beijing["benefit_claims"]} == {
        "BENEFIT-BEIJING-HOLD"
    }


def _cross_axis_trigger_cycle() -> dict:
    cycle = deepcopy(next(item for item in _cycles() if item[
        "investment_cycle_ref"
    ] == "XZTJ-SONG-XIA-FIVE-ROUTE-1081"))
    cycle.pop("cross_axis_overlap_adjudication", None)
    s_gate = cycle["cost_axis_adjudications"]["S"]
    s_gate.update({
        "grade": 3, "gross_damage_grade": 3,
        "flow_disruption_grade": 3, "terminal_residual_grade": 3,
    })
    s_fact = next(
        fact for fact in cycle["ordered_phases"][0]["cost_facts"]
        if fact["fact_type"] == "SYSTEM_DAMAGE"
    )
    s_fact.update({
        "gross_damage_grade": 3, "flow_disruption_grade": 3,
        "terminal_residual_grade": 3,
    })
    return cycle


def test_cross_axis_overlap_audit_hits_only_two_automatic_and_one_manual() -> None:
    payload = build_shadow(_cycles())
    audit = payload["D_business_audit"]
    assert audit["cross_axis_overlap_automatic_trigger_count"] == 2
    assert audit["cross_axis_overlap_remaining_trigger_count"] == 2
    assert audit["cross_axis_overlap_manual_review_count"] == 1
    auto_refs = {
        item["investment_cycle_ref"]
        for item in audit["cross_axis_overlap_records"]
        if item["automatic_triggered"]
    }
    assert auto_refs == {
        "MTJ-OIRAT-MING-1449-TUMU-ZHUQIZHEN-WINDOW",
        "MTJ-MING-QING-SARHU-1619",
    }
    assert audit["cross_axis_overlap_status_counts"] == {
        "INDEPENDENT": 2, "RESCOPED": 1, "UNRESOLVED": 0,
    }
    assert sum(
        row["cross_axis_overlap_adjudication"] is None
        for row in payload["records"]
    ) == len(payload["records"]) - 3


def test_cross_axis_trigger_requires_adjudication_and_independent_increment() -> None:
    cycle = _cross_axis_trigger_cycle()
    claim = cycle["ordered_phases"][0]["benefit_facts"][0]
    system_fact = next(
        fact for fact in cycle["ordered_phases"][0]["cost_facts"]
        if fact["fact_type"] == "SYSTEM_DAMAGE"
    )
    system_fact["affected_system_ref"] = claim["historical_object_ref"]
    with pytest.raises(ValueError, match="缺少父级裁决"):
        build_shadow([cycle])

    cycle["cross_axis_overlap_adjudication"] = {
        "status": "INDEPENDENT", "affected_axes": ["S", "SN"],
        "basis": "同对象换轴不能替代独立性说明。",
        "source_refs": ["SRC-OVERLAP"],
    }
    with pytest.raises(ValueError, match="独立事实增量"):
        build_shadow([cycle])

    cycle["cross_axis_overlap_adjudication"]["basis"] = (
        "S独立事实增量是行政交通系统持续停摆；"
        "SN独立事实增量是对手获得持续进攻能力。"
    )
    row = build_shadow([cycle])["records"][0]
    assert row["cross_axis_overlap_adjudication"]["status"] == "INDEPENDENT"
    assert row["q_contribution"] == _formula(row)


def test_cross_axis_unresolved_keeps_q_open_and_nontrigger_has_zero_burden() -> None:
    cycle = _cross_axis_trigger_cycle()
    cycle["cross_axis_overlap_adjudication"] = {
        "status": "UNRESOLVED", "affected_axes": ["S", "SN"],
        "basis": "S与SN是否存在独立增量尚未闭合。",
        "source_refs": ["SRC-OVERLAP"],
    }
    row = build_shadow([cycle])["records"][0]
    assert row["q_contribution"] is None
    assert row["q_candidate_range"]["lower"] is not None
    assert row["q_candidate_range"]["upper"] is not None

    nontrigger = _asset_cycle(reusable=0, consumed=0, lost=0, scoring=0)
    row = build_shadow([nontrigger])["records"][0]
    assert row["cross_axis_overlap_adjudication"] is None


def test_rescoped_overlap_must_change_parent_q_before_closure() -> None:
    cycle = _cross_axis_trigger_cycle()
    cycle["cross_axis_overlap_adjudication"] = {
        "status": "RESCOPED", "affected_axes": ["S", "SN"],
        "basis": "修订前Q=-47；已完成S与SN父轴重裁。",
        "source_refs": ["SRC-OVERLAP"],
    }
    with pytest.raises(ValueError, match="必须先完成会改变Q"):
        build_shadow([cycle])


def test_three_overlap_cases_are_rescoped_before_linear_q() -> None:
    rows = _records()
    tumu = rows["MTJ-OIRAT-MING-1449-TUMU-ZHUQIZHEN-WINDOW"]
    sarhu = rows["MTJ-MING-QING-SARHU-1619"]
    five_route = rows["XZTJ-SONG-XIA-FIVE-ROUTE-1081"]

    assert (tumu["parent_axes"]["S"], tumu["parent_axes"]["BCN"]) == (3, 0)
    assert tumu["q_contribution"] == -64
    assert tumu["q_candidate_range"] == {
        "lower": -64, "upper": -64,
        "boundary_driver": "EXPLICIT_AXIS_AND_A_ADJUDICATION_BOUNDS",
    }
    assert "不消费朱祁钰继位后的京师守御" in (
        tumu["mobilization_rollup"]["parent_adjudication"]["basis"]
    )
    assert "不消费朱祁钰窗口的京师守备" in (
        tumu["asset_components"]["A_scoring_basis"]
    )
    assert tumu["mobilization_rollup"]["mobilization_input_refs"] == [
        "MING-TUMU-ZHUQIZHEN-EXPEDITION"
    ]

    assert (sarhu["parent_axes"]["S"], sarhu["parent_axes"]["BCN"]) == (4, 3)
    assert sarhu["q_contribution"] == -69
    assert sarhu["q_candidate_range"]["lower"] == -70
    assert sarhu["q_candidate_range"]["upper"] == -69

    assert five_route["parent_axes"]["S"] == 2
    assert five_route["q_contribution"] == -43
    assert five_route["q_candidate_range"]["lower"] == -44
    assert five_route["q_candidate_range"]["upper"] == -43


def test_new_multi_asset_samples_have_explicit_parent_component_gate() -> None:
    cycles = {cycle["investment_cycle_ref"]: cycle for cycle in _cycles()}
    for ref in ("SUI-GOGURYEO-611-614", "CAMPAIGN-TANG-KHITAN-696-700"):
        cycle = cycles[ref]
        asset_facts = [
            fact for phase in cycle["ordered_phases"] for fact in phase["cost_facts"]
            if fact["fact_type"] == "ASSET_BURDEN"
        ]
        gate = cycle["asset_scoring_adjudication"]["multi_object_component_gate"]
        assert len(asset_facts) > 1
        assert set(gate["asset_object_refs"]) == {
            fact["asset_object_ref"] for fact in asset_facts
        }
        assert gate["aggregation_basis"] and gate["regrade_status"]


def test_three_case_horizontal_calibration_closes_fixed_card_gates() -> None:
    rows = _records()
    tuyuhun = rows["CAMPAIGN-TANG-TUYUHUN-634-635"]
    nahacu = rows["MING-NORTHERN-YUAN-NAHACU-1387"]
    buyur = rows["MING-NORTHERN-YUAN-BUYUR-KARAKORUM-1388"]

    assert tuyuhun["parent_axes"]["BCP"] == 2
    assert tuyuhun["axis_candidate_ranges"]["BCP"] == {"lower": 0, "upper": 3}
    tuyuhun_bcp = tuyuhun["benefit_axis_gates"]["BCP"]
    assert tuyuhun_bcp["gate_evidence"]["control_mode"] == "CLIENT_BUFFER"
    assert all(
        term in tuyuhun_bcp["basis"]
        for term in ("扶立慕容顺", "李大亮精兵数千", "非直接领土接管")
    )
    assert any(
        all(term in note for term in ("CLIENT_BUFFER", "实际立君", "册封"))
        for note in tuyuhun["notes"]
    )

    nahacu_p = nahacu["ordered_phase_facts"][0]["cost_facts"][0]
    assert nahacu["parent_axes"]["P"] == 3
    assert nahacu_p["equivalent_min"] == 3000
    assert "濮英三千骑" in nahacu_p["basis"]
    bcp_gate = nahacu["benefit_axis_gates"]["BCP"]
    assert bcp_gate["grade"] == 3
    assert all(term in bcp_gate["basis"] for term in ("四城", "驻兵", "大宁都指挥使司"))
    wr_gate = nahacu["benefit_axis_gates"]["WR"]
    assert wr_gate["grade"] == 4
    assert "百余里" in wr_gate["basis"]
    assert "受降士卒" in wr_gate["basis"]

    assert buyur["ordered_phase_refs"] == [
        "PHASE-MING-BUYUR-1388",
        "PHASE-MING-KARAKORUM-1388",
    ]
    phases = {phase["phase_ref"]: phase for phase in buyur["ordered_phase_facts"]}
    karakorum = phases["PHASE-MING-KARAKORUM-1388"]
    assert next(fact for fact in karakorum["cost_facts"] if fact["fact_type"] == "PERSONNEL_LOSS")["equivalent_max"] == 99
    assert next(fact for fact in karakorum["cost_facts"] if fact["fact_type"] == "MOBILIZATION")["grade"] == 2
    karakorum_asset = next(fact for fact in karakorum["cost_facts"] if fact["fact_type"] == "ASSET_BURDEN")
    assert karakorum_asset["observed_a_grade"] == 1
    assert all(karakorum_asset[field] is None for field in ("gross_grade", "reusable_grade", "consumed_grade"))
    assert buyur["parent_axes"]["P"] == 1
    assert len(buyur["personnel_rollup"]["casualty_group_refs"]) == 2
    assert buyur["parent_axes"]["M"] == 3
    assert set(buyur["mobilization_rollup"]["parent_adjudication"]["supporting_fact_refs"]) == {
        "COST-BUYUR-M", "COST-KARAKORUM-M",
    }
    assert "禁止3+2" in buyur["mobilization_rollup"]["parent_adjudication"]["gate_evidence"]["rollup_rule"]
    assets = buyur["asset_components"]
    assert all(
        assets[field] is None
        for field in ("gross_commitment_grade", "reusable_input_grade", "consumed_asset_grade")
    )
    assert assets["A_scoring"] == 1
    assert (assets["A_scoring_lower"], assets["A_scoring_upper"]) == (1, 2)
    assert len(assets["asset_object_refs"]) == 2
    assert "UNKNOWN" in assets["A_scoring_basis"]
    wr_claims = {
        claim["fact_ref"]: claim for claim in buyur["benefit_claims"]
        if claim["axis_grades"]["WR"]
    }
    assert set(wr_claims) == {"BENEFIT-BUYUR-RESOURCES", "BENEFIT-KARAKORUM-RESOURCES"}
    assert wr_claims["BENEFIT-KARAKORUM-RESOURCES"]["quantity_anchor"] == "获人畜六万"
    assert "人口" in buyur["benefit_axis_gates"]["WR"]["basis"]
    tuyuhun_wr = tuyuhun["benefit_axis_gates"]["WR"]
    assert tuyuhun["parent_axes"]["WR"] == 4
    assert buyur["parent_axes"]["WR"] == 4
    assert tuyuhun["parent_axes"]["WR"] == buyur["parent_axes"]["WR"]
    assert all(term in tuyuhun_wr["basis"] for term in ("二十余万", "捕鱼儿海", "WR4"))
    assert "补充军食" in tuyuhun_wr["gate_evidence"]["realization"]


def test_three_case_q_differences_are_computed_from_records() -> None:
    payload = build_shadow(_cycles())
    rows = {row["investment_cycle_ref"]: row for row in payload["records"]}
    comparison = payload["sample_statistics"]["three_case_q_comparison"]
    samples = {item["investment_cycle_ref"]: item for item in comparison["samples"]}
    for ref, sample in samples.items():
        assert sample["q_contribution"] == rows[ref]["q_contribution"]
        assert sum(sample["axis_contributions"].values()) == sample["q_contribution"]

    pairs = {(item["target_ref"], item["baseline_ref"]): item for item in comparison["pair_differences"]}
    nahacu_pair = pairs[("MING-NORTHERN-YUAN-NAHACU-1387", "CAMPAIGN-TANG-TUYUHUN-634-635")]
    assert nahacu_pair["q_difference"] == -1
    assert nahacu_pair["axis_contribution_deltas"]["BCP"] == 3
    assert nahacu_pair["axis_contribution_deltas"]["WR"] == 0
    buyur_pair = pairs[("MING-NORTHERN-YUAN-BUYUR-KARAKORUM-1388", "CAMPAIGN-TANG-TUYUHUN-634-635")]
    assert buyur_pair["q_difference"] == -3
    assert buyur_pair["axis_contribution_deltas"]["P"] == 8
    assert buyur_pair["axis_contribution_deltas"]["SB"] == -4
    assert buyur_pair["axis_contribution_deltas"]["BCP"] == -6
    assert all("军事成就" in item["metric_warning"] for item in pairs.values())
    assert comparison["tuyuhun_bcp_scenarios"] == [
        {"BCP": 0, "q_contribution": 9, "q_candidate_range": {"lower": 7, "upper": 9}, "difference_from_nahacu": 5, "difference_from_buyur": 3},
        {"BCP": 2, "q_contribution": 15, "q_candidate_range": {"lower": 13, "upper": 15}, "difference_from_nahacu": -1, "difference_from_buyur": -3},
        {"BCP": 3, "q_contribution": 18, "q_candidate_range": {"lower": 16, "upper": 18}, "difference_from_nahacu": -4, "difference_from_buyur": -6},
    ]
    recommendation = payload["shadow_contract_recommendation"]
    assert set(recommendation["control_modes"]) == {
        "DIRECT_TERRITORIAL", "CLIENT_BUFFER", "NOMINAL_TRIBUTARY",
    }
    assert recommendation["formal_contract_write"] is False


def test_wr_simplified_matrix_closes_intervals_without_freezing_formal_facts() -> None:
    payload = build_shadow(_cycles())
    rows = {row["investment_cycle_ref"]: row for row in payload["records"]}
    for ref in (
        "CAMPAIGN-TANG-TUYUHUN-634-635",
        "MING-NORTHERN-YUAN-NAHACU-1387",
        "MING-NORTHERN-YUAN-BUYUR-KARAKORUM-1388",
    ):
        assert rows[ref]["wr_evidence_adjudication"]["status"] == "EXPLICIT_REALIZED"

    audit = payload["D_business_audit"]
    assert audit["wr_evidence_status_counts"] == {
        "CONFIRMED_NONE": 11,
        "EXPLICIT_REALIZED": 9,
        "SIMPLIFIED_INFERRED": 5,
        "UNKNOWN": 0,
    }
    assert audit["wr_numeric_interval_count"] == 25
    assert audit["wr_unknown_count"] == 0
    expected = {
        "CAMPAIGN-TANG-XUEYANTUO-641": (0, 1),
        "CAMPAIGN-TANG-XUEYANTUO-645-647": (2, 3),
        "MTJ-MING-NORTHERN-WAR-1372": (4, 4),
        "CAMPAIGN-TANG-GOGURYEO-644-645": (4, 4),
        "CAMPAIGN-TANG-EASTERN-TURKS-629-630": (4, 4),
        "HAN-HEXICORRIDOR-121": (4, 4),
        "PARENT-HEHUANG-CENTRAL-RECEPTION-848-849": (2, 2),
        "PARENT-HEHUANG-GUIYI-851": (0, 0),
        "SUI-GOGURYEO-611-614": (0, 0),
    }
    for ref, bounds in expected.items():
        adjudication = rows[ref]["wr_evidence_adjudication"]
        assert (adjudication["lower_grade"], adjudication["upper_grade"]) == bounds
        if adjudication["status"] == "SIMPLIFIED_INFERRED":
            assert adjudication["formal_fact_freeze"] is False
    assert audit["wr_source_priority_counts"] == {
        "EXPLICIT_REALIZED": 9,
        "CONFIRMED_NONE": 1,
        "SIMPLIFIED_INFERRED": 15,
        "UNKNOWN": 0,
    }
    assert audit["wr_conflicting_same_object_double_adjudication_count"] == 0
    assert audit["wr_partial_floor_with_simplified_complement_count"] == 1
    assert audit["wr_explicit_rollup_coverage_counts"] == {
        "EXPLICIT_COMPLETE_ROLLUP": 9,
        "EXPLICIT_PARTIAL_FLOOR": 1,
    }
    assert audit["wr_partial_floor_with_simplified_complement_count"] == 1
    assert audit["wr_same_resource_object_double_consumption_count"] == 0

    wr_contract = payload["shadow_contract_recommendation"]["WR"]
    assert "不以点值冒充精确裁决" in wr_contract["grade_policy"]
    assert all(
        factor in wr_contract["simplified_inference_factors"]
        for factor in ("asset_base_grade", "transfer_mode", "realization_retention")
    )


def test_wr_priority_explicit_then_confirmed_none_then_simplified() -> None:
    explicit = deepcopy(next(
        cycle for cycle in _cycles()
        if cycle["investment_cycle_ref"] == "CAMPAIGN-TANG-EASTERN-TURKS-629-630"
    ))
    explicit["wr_simplified_adjudication"] = {
        "asset_base_grade": 0,
        "transfer_mode": "NONE_OR_DESTROYED",
        "realization_retention": "LOST_RETURNED_UNUSABLE",
    }
    explicit_row = build_shadow([explicit])["records"][0]
    adjudication = explicit_row["wr_evidence_adjudication"]
    assert adjudication["effective_source_priority"] == "EXPLICIT_REALIZED"
    assert adjudication["explicit_rollup_coverage"] == "EXPLICIT_COMPLETE_ROLLUP"
    assert explicit_row["parent_axes"]["WR"] == 4
    assert adjudication["simplified_override_applied"] is False
    assert adjudication["ignored_lower_priority_inputs"] == [
        "wr_simplified_adjudication"
    ]

    confirmed = deepcopy(next(
        cycle for cycle in _cycles()
        if cycle["investment_cycle_ref"] == "CAMPAIGN-TANG-XUEYANTUO-641"
    ))
    confirmed["wr_zero_adjudication"] = {
        "status": "CONFIRMED_NONE",
        "basis": "固定卡明确本轮仅击退，敌方资产撤离且无唐方接收。",
        "source_refs": ["WAR-LEAD-TANG-XUEYANTUO-641"],
    }
    confirmed_row = build_shadow([confirmed])["records"][0]
    adjudication = confirmed_row["wr_evidence_adjudication"]
    assert adjudication["effective_source_priority"] == "CONFIRMED_NONE"
    assert adjudication["simplified_override_applied"] is False
    assert confirmed_row["axis_candidate_ranges"]["WR"] == {"lower": 0, "upper": 0}


def test_partial_explicit_floor_complements_residual_inference_without_overlap() -> None:
    row = _records()["CAMPAIGN-TANG-XUEYANTUO-645-647"]
    wr = row["wr_evidence_adjudication"]
    assert wr["explicit_rollup_coverage"] == "EXPLICIT_PARTIAL_FLOOR"
    assert wr["explicit_floor_grade"] == 1
    assert wr["simplified_override_applied"] is False
    assert wr["simplified_complement_applied"] is True
    assert wr["transfer_mode"] == "CAMP_OR_MAJOR_FORCE_CAPTURE"
    assert wr["realization_retention"] == "PARTIAL_OR_UNCERTAIN"
    assert wr["asset_base_grade"] == {"lower": 5, "upper": 5}
    assert (wr["lower_grade"], wr["selected_grade"], wr["upper_grade"]) == (2, 2, 3)
    assert wr["excluded_explicit_resource_object_refs"] == [
        "OBJECT-MONGLIAN-ACTUAL-TRIBUTE-647"
    ]
    assert wr["residual_resource_object_ref"] == (
        "OBJECT-XUEYANTUO-RESIDUAL-MILITARY-ASSET-POOL-645-647"
    )
    assert row["q_contribution"] == 30
    assert row["q_candidate_range"]["lower"] == 29
    assert row["q_candidate_range"]["upper"] == 32

    incomplete = deepcopy(next(
        cycle for cycle in _cycles()
        if cycle["investment_cycle_ref"] == "CAMPAIGN-TANG-XUEYANTUO-645-647"
    ))
    del incomplete["wr_simplified_adjudication"]
    incomplete_row = build_shadow([_cycles()[0], incomplete])["records"][1]
    assert incomplete_row["wr_evidence_adjudication"]["status"] == "UNKNOWN"
    assert incomplete_row["parent_axes"]["WR"] is None
    assert incomplete_row["q_contribution"] is None

    duplicate = deepcopy(next(
        cycle for cycle in _cycles()
        if cycle["investment_cycle_ref"] == "CAMPAIGN-TANG-XUEYANTUO-645-647"
    ))
    duplicate["wr_simplified_adjudication"]["residual_resource_object_ref"] = (
        "OBJECT-MONGLIAN-ACTUAL-TRIBUTE-647"
    )
    with pytest.raises(ValueError, match="同一resource_object不得同时显式与推定消费"):
        build_shadow([_cycles()[0], duplicate])


def test_eastern_turks_and_goguryeo_explicit_wr4_horizontal_scale() -> None:
    rows = _records()
    eastern = rows["CAMPAIGN-TANG-EASTERN-TURKS-629-630"]
    goguryeo = rows["CAMPAIGN-TANG-GOGURYEO-644-645"]
    tuyuhun = rows["CAMPAIGN-TANG-TUYUHUN-634-635"]
    buyur = rows["MING-NORTHERN-YUAN-BUYUR-KARAKORUM-1388"]
    assert {
        eastern["parent_axes"]["WR"], goguryeo["parent_axes"]["WR"],
        tuyuhun["parent_axes"]["WR"], buyur["parent_axes"]["WR"],
    } == {4}
    assert eastern["wr_evidence_adjudication"]["status"] == "EXPLICIT_REALIZED"
    assert eastern["axis_candidate_ranges"]["WR"] == {"lower": 4, "upper": 4}
    gog_gate = goguryeo["benefit_axis_gates"]["WR"]
    assert goguryeo["wr_evidence_adjudication"]["status"] == "EXPLICIT_REALIZED"
    assert goguryeo["axis_candidate_ranges"]["WR"] == {"lower": 4, "upper": 4}
    assert all(term in gog_gate["basis"] for term in (
        "牛五万", "马五万", "明光铠一万领", "WR4", "不到WR5",
    ))
    assert gog_gate["gate_evidence"]["resource_categories"] == [
        "战马五万", "运输畜力牛五万", "明光铠一万领",
    ]
    assert goguryeo["q_contribution"] == 2
    assert _formula(goguryeo, WR=3) == 0


def test_no_cycle_has_both_effective_explicit_and_simplified_wr() -> None:
    cycles = _cycles()
    for cycle in cycles:
        explicit_claims = [
            fact for phase in cycle["ordered_phases"]
            for fact in phase.get("benefit_facts") or ()
            if int((fact.get("axis_grades") or {}).get("WR") or 0) > 0
            and fact.get("wr_evidence_status") == "EXPLICIT_REALIZED"
        ]
        if explicit_claims and "wr_simplified_adjudication" in cycle:
            gate = cycle["benefit_axis_gates"]["WR"]
            simplified = cycle["wr_simplified_adjudication"]
            assert gate["wr_rollup_coverage"] == "EXPLICIT_PARTIAL_FLOOR"
            explicit_objects = {
                fact["historical_object_ref"] for fact in explicit_claims
            }
            assert set(simplified["excluded_explicit_resource_object_refs"]) == explicit_objects
            assert simplified["residual_resource_object_ref"] not in explicit_objects
    audit = build_shadow(cycles)["D_business_audit"]
    assert len(audit["wr_source_priority_records"]) == 25
    assert audit["wr_conflicting_same_object_double_adjudication_count"] == 0
    assert audit["wr_partial_floor_with_simplified_complement_count"] == 1
    assert audit["wr_partial_floor_with_simplified_complement_count"] == 1
    assert audit["wr_same_resource_object_double_consumption_count"] == 0


def test_internal_transfer_and_destroyed_assets_do_not_create_wr() -> None:
    internal = deepcopy(next(
        cycle for cycle in _cycles()
        if cycle["investment_cycle_ref"] == "MTJ-MING-BOZHOU-1594"
    ))
    assert build_shadow([internal])["records"][0]["axis_candidate_ranges"]["WR"] == {
        "lower": 0, "upper": 0,
    }
    internal["wr_simplified_adjudication"].update({
        "transfer_mode": "CAMP_OR_MAJOR_FORCE_CAPTURE",
        "realization_retention": "RETAINED_USABLE",
    })
    with pytest.raises(ValueError, match="同一国家系统转手不得推定正WR"):
        build_shadow([internal])

    destroyed = deepcopy(next(
        cycle for cycle in _cycles()
        if cycle["investment_cycle_ref"] == "SUI-GOGURYEO-611-614"
    ))
    row = build_shadow([destroyed])["records"][0]
    assert row["wr_evidence_adjudication"]["transfer_mode"] == "NONE_OR_DESTROYED"
    assert row["wr_evidence_adjudication"]["status"] == "CONFIRMED_NONE"
    assert row["axis_candidate_ranges"]["WR"] == {"lower": 0, "upper": 0}


def test_wr_interval_propagates_to_q_and_true_unknown_is_excluded() -> None:
    bounded = _asset_cycle(reusable=0, consumed=0, lost=0, scoring=0)
    bounded["wr_simplified_adjudication"] = {
        "asset_base_grade": 1,
        "transfer_mode": "PARTIAL_FIELD_CAPTURE",
        "realization_retention": "RETAINED_USABLE",
    }
    bounded_row = build_shadow([bounded])["records"][0]
    assert bounded_row["axis_candidate_ranges"]["WR"] == {"lower": 0, "upper": 1}
    assert (
        bounded_row["q_candidate_range"]["upper"]
        - bounded_row["q_candidate_range"]["lower"]
    ) == 2

    unknown = deepcopy(next(
        cycle for cycle in _cycles()
        if cycle["investment_cycle_ref"] == "CAMPAIGN-TANG-XUEYANTUO-641"
    ))
    del unknown["wr_simplified_adjudication"]
    payload = build_shadow([unknown])
    row = payload["records"][0]
    assert row["wr_evidence_adjudication"]["status"] == "UNKNOWN"
    assert row["parent_axes"]["WR"] is None
    assert row["q_contribution"] is None
    assert payload["sample_statistics"]["sample_count"] == 0
    assert payload["sample_statistics"]["unknown_q_refs"] == [
        "CAMPAIGN-TANG-XUEYANTUO-641"
    ]


def test_sample_statistics_are_computed_from_records() -> None:
    payload = build_shadow(_cycles())
    rows = payload["records"]
    stats = payload["sample_statistics"]
    closed = [row for row in rows if row["q_contribution"] is not None]
    q_values = sorted(row["q_contribution"] for row in closed)

    def percentile(values: list[int], position: float) -> float:
        point = (len(values) - 1) * position
        lower = int(point)
        upper = min(lower + 1, len(values) - 1)
        return round(values[lower] + (values[upper] - values[lower]) * (point - lower), 2)

    assert stats["total_sample_count"] == len(rows)
    assert stats["sample_count"] == len(closed)
    assert stats["unknown_q_count"] == len(rows) - len(closed)
    assert set(stats["unknown_q_refs"]) == {
        row["investment_cycle_ref"] for row in rows
        if row["q_contribution"] is None
    }
    assert stats["q"] == {
        "mean": round(sum(q_values) / len(q_values), 2),
        "median": percentile(q_values, 0.5),
        "q1": percentile(q_values, 0.25),
        "q3": percentile(q_values, 0.75),
    }
    assert stats["high_axis_counts"] == {
        axis: sum(row["parent_axes"][axis] >= 4 for row in closed)
        for axis in ("SB", "BCP", "WR")
    }
    assert sum(group["sample_count"] for group in stats["by_event_type"].values()) == len(closed)
    assert len(stats["highest_q_5"]) == min(5, len(closed))
    assert len(stats["lowest_q_5"]) == min(5, len(closed))
    assert len(stats["widest_interval_5"]) == min(5, len(closed))
    ranked_refs = {
        item["investment_cycle_ref"]
        for key in ("highest_q_5", "lowest_q_5", "widest_interval_5")
        for item in stats[key]
    }
    assert not ranked_refs & set(stats["unknown_q_refs"])
    assert "LOCAL_INFORMATION_RICH" in stats["sample_scope"]


def test_precision_review_triggers_are_computed_from_record_ranges() -> None:
    payload = build_shadow(_cycles())
    rows = {row["investment_cycle_ref"]: row for row in payload["records"]}
    precision = payload["sample_statistics"]["precision_review_triggers"]
    assert precision["computed_from_records"] is True
    assert precision["trigger_count"] == len(precision["records"])
    assert precision["future_d_candidate_q_boundaries"] == [12, 27]
    for item in precision["records"]:
        row = rows[item["investment_cycle_ref"]]
        assert item["q_candidate_range"] == row["q_candidate_range"]
        assert item["wr_candidate_range"] == row["axis_candidate_ranges"]["WR"]
        lower, upper = (
            row["q_candidate_range"]["lower"],
            row["q_candidate_range"]["upper"],
        )
        wr = row["axis_candidate_ranges"]["WR"]
        for reason in item["reasons"]:
            if reason == "Q_CROSSES_ZERO":
                assert lower < 0 <= upper or lower <= 0 < upper
            elif reason.startswith("Q_CROSSES_FUTURE_D_BOUNDARY_"):
                boundaries = [
                    boundary for boundary in (12, 27)
                    if lower < boundary <= upper
                ]
                assert boundaries
            elif reason == "WR_WIDTH_GE_3_WITH_SB3_OR_BCP2":
                assert wr["upper"] - wr["lower"] >= 3
                assert row["parent_axes"]["SB"] >= 3 or row["parent_axes"]["BCP"] >= 2
            else:
                assert reason == "TOP_OR_BOTTOM_5_MEMBERSHIP_SENSITIVE"


def test_double_generation_is_deterministic() -> None:
    first = build_shadow(_cycles())
    second = build_shadow(_cycles())
    assert first["semantic_fingerprint"] == second["semantic_fingerprint"]
    assert json.dumps(first, ensure_ascii=False, sort_keys=True) == json.dumps(
        second, ensure_ascii=False, sort_keys=True
    )
    assert render_markdown(first) == render_markdown(second)


def test_formal_linear_q_analysis_separates_curated_and_legacy_semantics() -> None:
    formal = json.loads(
        (
            ROOT
            / "docs/评分结算/第三项军事与边疆净收益/军事成本收益比/01-皇帝D项正式结算.json"
        ).read_text(encoding="utf-8")
    )
    config = json.loads(
        (ROOT / "config/third-item-d-cycle-adjudications.json").read_text(
            encoding="utf-8"
        )
    )
    analysis = build_formal_linear_q_analysis(formal["records"], config)
    audit = analysis["mapping_audit"]
    expected_fact_closed_refs = set(config["fact_closed_investment_cycle_refs"])
    assert audit["curated_cycle_count"] == len(expected_fact_closed_refs)
    assert (audit["same_id_count"], audit["split_id_count"]) == (15, 10)
    assert audit["initial_formal_mapping_gap_count"] == 19
    assert audit["programmatically_resolved_mapping_count"] == 19
    assert audit["formal_mapping_complete"] is True
    assert audit["formal_mapping_gap_refs"] == []
    assert all(
        row["mapping_status"] == "CLOSED"
        and row["ruler_window_ref"]
        and row["public_parent_cycle_ref"]
        and (
            row["ordered_public_member_refs"]
            or row["ordered_public_phase_refs"]
        )
        and row["strategic_result_chain_refs"]
        for row in audit["curated_investment_cycle_mappings"]
    )
    assert set(audit["old_parent_consumption"].values()) == {0}
    assert set(audit["new_parent_consumption"].values()) == {1}

    cycles = [
        cycle
        for ruler in analysis["records"]
        for cycle in (ruler.get("D_portfolio_metrics") or {}).get(
            "cycle_q_adjudications", ()
        )
    ]
    curated = [
        cycle for cycle in cycles
        if cycle["legacy_axis_semantics_status"]
        == "FACT_CLOSED_AXIS_ROLLUP"
    ]
    legacy = [
        cycle for cycle in cycles
        if cycle["legacy_axis_semantics_status"]
        == "LEGACY_AXIS_VALUES_LINEAR_Q_ONLY"
    ]
    assert {
        cycle["investment_cycle_ref"] for cycle in curated
    } == expected_fact_closed_refs
    assert all(
        cycle["system_damage_bridge_status"] == "CURATED_BRIDGE_CLOSED"
        for cycle in curated
        if int(cycle["cost_axes"]["S"]) > 0
    )
    assert all(
        cycle["system_damage_bridge_status"]
        == "LEGACY_S_BRIDGE_UNSTRUCTURED"
        for cycle in legacy
        if int(cycle["cost_axes"].get("S") or 0) > 0
    )
    assert not any(
        claim.get("from_state") == "PRE_INVESTMENT_PARENT_STATE"
        or claim.get("to_state") == "PARENT_TERMINAL_STATE"
        for cycle in legacy
        for claim in cycle.get("benefit_claims") or ()
    )


def test_paired_anchor_closures_replace_only_li_shimin_and_zhu_yuanzhang() -> None:
    formal = json.loads(
        (
            ROOT
            / "docs/评分结算/第三项军事与边疆净收益/军事成本收益比/01-皇帝D项正式结算.json"
        ).read_text(encoding="utf-8")
    )
    config = json.loads(
        (ROOT / "config/third-item-d-cycle-adjudications.json").read_text(
            encoding="utf-8"
        )
    )
    paired = _paired_payload()

    audit = validate_paired_anchor_closures(paired)
    assert audit["legacy_input_count"] == 18
    assert audit["final_cycle_count"] == 23
    assert audit["suppressed_duplicate_count"] == 2
    assert audit["excluded_non_investment_member_count"] == 2
    assert len(audit["final_cycle_refs"]) == len(set(audit["final_cycle_refs"]))
    assert {
        row["strategic_result_chain_ref"]: row["chain_net_q"]
        for row in audit["strategic_result_chain_rollups"]
        if row["investment_cycle_count"] > 1
    } == {
        "CHAIN-MING-WOKOU-1391-1394": -25,
        "CHAIN-MING-WUKAI-CONTROL-1378-1392": -16,
    }
    assert all(
        cycle["system_damage_adjudication"]["status"]
        in {"DIRECT", "INFERRED_BOUNDED"}
        and {
            "S_scoring", "affected_area_refs", "functional_symptoms",
            "duration_basis", "source_refs", "confidence",
        } <= set(cycle["system_damage_adjudication"])
        for cycle in audit["final_cycles"]
        if int(cycle["cost_axes"]["S"]) > 0
    )

    first = build_formal_linear_q_analysis(formal["records"], config, paired)
    second = build_formal_linear_q_analysis(formal["records"], config, paired)
    assert json.dumps(first, ensure_ascii=False, sort_keys=True) == json.dumps(
        second, ensure_ascii=False, sort_keys=True
    )
    summaries = {row["ruler_name"]: row for row in first["ruler_summaries"]}
    assert summaries["李世民"] | {} == {
        **summaries["李世民"],
        "Q": 84, "Q_mean": 8.4, "T": 10, "K": 10,
        "positive": 7, "zero": 0, "negative": 3,
        "paired_anchor_new_cycle_count": 4,
    }
    assert summaries["朱元璋"] | {} == {
        **summaries["朱元璋"],
        "Q": -54, "Q_mean": -2.3478, "T": 23, "K": 23,
        "positive": 5, "zero": 1, "negative": 17,
        "paired_anchor_new_cycle_count": 19,
    }

    mapping = first["mapping_audit"]
    canonical = first["canonical_audit"]
    assert mapping["reused_legacy_parent_ref_count"] == 27
    assert mapping["reused_known_legacy_parent_ref_count"] == 19
    assert mapping["reused_unknown_legacy_parent_ref_count"] == 1
    assert mapping["reused_mixed_known_unknown_parent_ref_count"] == 7
    assert mapping["namespaced_legacy_cycle_count"] == 51
    assert mapping["duplicate_parent_consumption_count"] == 0
    assert mapping["source_material_conservation_mismatch_count"] == 0
    assert mapping["potential_material_ref_count"] == 237
    assert canonical["ruler_count"] == 148
    assert canonical["material_cycle_count_total"] == 759
    assert canonical["investment_cycle_count"] == 759
    assert canonical["strict_curated_cycle_count"] == 106
    assert canonical["base_curated_cycle_count"] == 25
    assert canonical["paired_anchor_curated_cycle_count"] == 23
    assert canonical["manual_residual_fact_closed_cycle_count"] == 58
    assert canonical["strict_curated_cycle_count"] == sum((
        canonical["base_curated_cycle_count"],
        canonical["paired_anchor_curated_cycle_count"],
        canonical["manual_residual_fact_closed_cycle_count"],
    ))
    assert canonical["legacy_linear_cycle_count"] == 599
    assert canonical["legacy_unknown_cycle_count"] == 54
    assert canonical["duplicate_investment_cycle_id_count"] == 0
    assert canonical["duplicate_strict_benefit_claim_count"] == 0
    assert canonical["strict_legacy_parent_conflict_count"] == 0
    assert canonical["unification_exclusion_mismatch_count"] == 0
    assert canonical["identified_cycle_unknown_q_count"] == 54
    assert canonical["identity_conservation_mismatch_count"] == 0
    assert canonical["identity_status"] == "IDENTITY_COMPLETE"
    assert canonical["semantic_q_status"] == "SEMANTIC_Q_INCOMPLETE"
    assert canonical["formal_export_prerequisite_status"] == (
        "IDENTITY_COMPLETE_SEMANTIC_Q_INCOMPLETE"
    )
    unknown_audit = first["legacy_unknown_classification_audit"]
    assert unknown_audit["input_named_unknown_count"] == 53
    assert unknown_audit["automatic_closure_count"] == 0
    assert unknown_audit["residual_count"] == 53
    assert sum(unknown_audit["primary_residual_reason_counts"].values()) == 53
    assert {
        row["ruler_name"] for row in unknown_audit["matrix"]
        if row["ruler_name"] in {"李雄", "朱温", "冯太后"}
    } == set()
    assert canonical["guangdong_1380_1382"] == {
        "ruler_name": "朱元璋",
        "investment_cycle_ref": "MTJ-MING-GUANGDONG-PACIFICATION-1380-1382",
        "Q": -5,
    }
    migrated = [
        cycle
        for ruler in first["records"]
        for cycle in ruler["D_portfolio_metrics"]["cycle_q_adjudications"]
        if cycle["legacy_axis_semantics_status"]
        == "LEGACY_AXIS_VALUES_LINEAR_Q_ONLY"
    ]
    assert all(
        cycle["benefit_claim_structure_status"] == "LEGACY_UNSTRUCTURED"
        and cycle["benefit_claims"] == []
        and cycle["d_investment_cycle_identity"].startswith("DINV::")
        and (
            int((cycle.get("cost_axes") or {}).get("S") or 0) == 0
            or cycle["system_damage_bridge_status"]
            == "LEGACY_S_BRIDGE_UNSTRUCTURED"
        )
        for cycle in migrated
    )

    source_by_ruler = {row["ruler_name"]: row for row in formal["records"]}
    result_by_ruler = {row["ruler_name"]: row for row in first["records"]}
    for ruler_name, source_ruler in source_by_ruler.items():
        source_metrics = source_ruler["D_portfolio_metrics"]
        assert source_metrics["material_cycle_count"] == (
            source_metrics["known_material_cycle_count"]
            + len(source_metrics["material_unknown_cycle_refs"])
        )
        result_metrics = result_by_ruler[ruler_name]["D_portfolio_metrics"]
        assert result_metrics["T"] == len(
            result_metrics["cycle_q_adjudications"]
        )

    xiaoyan_source = source_by_ruler["萧衍"]["D_portfolio_metrics"]
    xiaoyan_result = result_by_ruler["萧衍"]["D_portfolio_metrics"]
    xiaoyan_unknown = [
        cycle for cycle in xiaoyan_result["cycle_q_adjudications"]
        if cycle["q_contribution"] is None
    ]
    assert xiaoyan_unknown == []
    assert all(
        cycle["legacy_axis_semantics_status"] == "LEGACY_UNSTRUCTURED"
        and cycle["net_direction"] == "UNKNOWN"
        and cycle["q_contribution"] is None
        and cycle["q_contribution"] != 0
        and cycle["legacy_unknown_reasons"]
        for cycle in xiaoyan_unknown
    )
    for ruler_name, source_ruler in source_by_ruler.items():
        admitted_source_refs = {
            cycle.get(
                "source_canonical_parent_cycle_ref",
                cycle["investment_cycle_ref"],
            )
            for cycle in result_by_ruler[ruler_name]["D_portfolio_metrics"][
                "cycle_q_adjudications"
            ]
        }
        potential_refs = set(
            source_ruler["D_portfolio_metrics"]["potential_material_cycle_refs"]
        )
        assert not admitted_source_refs & potential_refs


def test_unknown_auto_closure_requires_explicit_same_subject_nine_axes() -> None:
    cycle = {
        "canonical_parent_cycle_ref": "PARENT-X",
        "d_investment_cycle_identity": "DINV::RULER-X::PARENT-X",
        "ruler_window_ref": "RULER-X",
        "member_cycle_refs": ["PHASE-X"],
        "unknown_axes": ["PARENT_COST_AXES_MISSING"],
        "source_ref": "docs/source.md#L1",
        "cost_axes": {"P": 0, "S": 0, "M": 0, "A": 0},
        "benefit_axes": {"SB": 0, "SN": 0, "BCP": 0, "BCN": 0, "WR": 0},
        "return_class": "HIGH_RETURN",
        "WC": 5,
    }
    weak = classify_legacy_unknown_cycle(
        cycle,
        ruler_id="RULER-X",
        ruler_name="测试帝",
        evidence_records=[{
            "evidence_ref": "weak",
            "evidence_level": "STRUCTURED_REFERENCE_ONLY",
            "matched_refs": ["PARENT-X"],
            "ruler_id": "RULER-X",
            "cost_axes": cycle["cost_axes"],
            "benefit_axes": cycle["benefit_axes"],
        }],
    )
    assert weak["classification_status"] == "RESIDUAL_REVIEW_REQUIRED"
    assert weak["auto_close_cost_axes"] is None

    explicit = classify_legacy_unknown_cycle(
        cycle,
        ruler_id="RULER-X",
        ruler_name="测试帝",
        evidence_records=[{
            "evidence_ref": "parent-axis-record",
            "evidence_level": "PARENT_AXIS_ADJUDICATION",
            "matched_refs": ["PARENT-X"],
            "ruler_id": "RULER-X",
            "cost_axes": {"P": 1, "S": 2, "M": 3, "A": 1},
            "benefit_axes": {"SB": 2, "SN": 1, "BCP": 1, "BCN": 0, "WR": 1},
        }],
    )
    assert explicit["classification_status"] == (
        "AUTO_CLOSABLE_EXPLICIT_NINE_AXES"
    )
    assert explicit["auto_close_cost_axes"] == {"P": 1, "S": 2, "M": 3, "A": 1}


def test_manual_unknown_batch_01_retains_three_closures_and_one_replacement() -> None:
    formal = json.loads(
        (
            ROOT
            / "docs/评分结算/第三项军事与边疆净收益/军事成本收益比/01-皇帝D项正式结算.json"
        ).read_text(encoding="utf-8")
    )
    config = json.loads(
        (ROOT / "config/third-item-d-cycle-adjudications.json").read_text(
            encoding="utf-8"
        )
    )
    analysis = build_formal_linear_q_analysis(
        formal["records"], config, _paired_payload()
    )
    audit = analysis["legacy_unknown_manual_batch_audit"]
    batch_rows = [
        row for row in audit["records"]
        if row["batch_ref"] == "LEGACY-UNKNOWN-MANUAL-BATCH-01"
    ]
    assert len(batch_rows) == 4
    assert {row["execution_status"] for row in batch_rows} == {
        "CLOSED", "REPLACED_BY_CURATED",
    }

    cycles = {
        (
            ruler["ruler_name"],
            cycle.get(
                "source_canonical_parent_cycle_ref",
                cycle["canonical_parent_cycle_ref"],
            ),
        ): cycle
        for ruler in analysis["records"]
        for cycle in ruler["D_portfolio_metrics"]["cycle_q_adjudications"]
    }
    expected = {
        ("李雄", "WAR-LEAD-QIUCHI-323"): (
            {"P": 3, "S": 0, "M": 2, "A": 0},
            {"SB": 0, "SN": 0, "BCP": 0, "BCN": 0, "WR": 0},
            -14, {"lower": -14, "upper": -14},
        ),
        ("刘询", "WAR-LEAD-HAN-CHESHI-67-64"): (
            {"P": 1, "S": 2, "M": 3, "A": 2},
            {"SB": 0, "SN": 2, "BCP": 0, "BCN": 2, "WR": 0},
            -31, {"lower": -35, "upper": -26},
        ),
        ("刘询", "HAN-WESTERN-QIANG-61-60"): (
            {"P": 2, "S": 3, "M": 4, "A": 3},
            {"SB": 3, "SN": 0, "BCP": 2, "BCN": 0, "WR": 3},
            -3, {"lower": -4, "upper": 1},
        ),
    }
    for key, (costs, benefits, q_value, q_range) in expected.items():
        cycle = cycles[key]
        assert cycle["cost_axes"] == costs
        assert cycle["benefit_axes"] == benefits
        assert cycle["q_contribution"] == q_value
        assert cycle["q_candidate_range"] == q_range
        assert cycle["legacy_axis_semantics_status"] == (
            "MANUAL_RESIDUAL_FACT_CLOSED"
        )
        assert cycle["strategic_chain_rollup"]["chain_net_q"] == q_value
        assert cycle["system_damage_adjudication"]["status"] in {
            "S0_CONFIRMED", "INFERRED_BOUNDED",
        }

    cheshi = cycles[("刘询", "WAR-LEAD-HAN-CHESHI-67-64")]
    assert cheshi["personnel_cost_adjudication"]["equivalent_range"] == [1, 199]
    assert cheshi["personnel_cost_adjudication"]["P_scoring"] == 1
    assert cheshi["personnel_cost_adjudication"]["scoring_policy"] == (
        "GEOMETRIC_MIDPOINT_TO_P_GRADE"
    )
    assert cheshi["axis_candidate_ranges"]["P"] == [1, 2]
    assert "前沿农业补给点及通道功能失效" in (
        cheshi["system_damage_adjudication"]["inference_basis"]
    )
    assert "安全轴只消费" in cheshi["benefit_axis_gates"]["SN"]
    assert "控制轴只消费" in cheshi["benefit_axis_gates"]["BCN"]

    all_refs = {
        cycle.get(
            "source_canonical_parent_cycle_ref",
            cycle["canonical_parent_cycle_ref"],
        )
        for ruler in analysis["records"]
        for cycle in ruler["D_portfolio_metrics"]["cycle_q_adjudications"]
    }
    assert "CAMPAIGN-MING-BEIJING-DEFENSE-1449" not in all_refs
    assert "MTJ-OIRAT-MING-1449-BEIJING-ZHUQIYU-WINDOW" in all_refs

    summaries = {row["ruler_name"]: row for row in analysis["ruler_summaries"]}
    assert (summaries["李雄"]["Q"], summaries["李雄"]["K"], summaries["李雄"]["T"]) == (11, 2, 2)
    assert (summaries["刘询"]["Q"], summaries["刘询"]["K"], summaries["刘询"]["T"]) == (-43, 4, 4)
    assert (summaries["朱祁钰"]["Q"], summaries["朱祁钰"]["K"], summaries["朱祁钰"]["T"]) == (12, 2, 3)


def test_manual_unknown_batch_02_closes_six_with_bounded_wu_wr() -> None:
    formal = json.loads(
        (
            ROOT
            / "docs/评分结算/第三项军事与边疆净收益/军事成本收益比/01-皇帝D项正式结算.json"
        ).read_text(encoding="utf-8")
    )
    config = json.loads(
        (ROOT / "config/third-item-d-cycle-adjudications.json").read_text(
            encoding="utf-8"
        )
    )
    analysis = build_formal_linear_q_analysis(
        formal["records"], config, _paired_payload()
    )
    audit = analysis["legacy_unknown_manual_batch_audit"]
    batch_rows = [
        row for row in audit["records"]
        if row["batch_ref"] == "LEGACY-UNKNOWN-MANUAL-BATCH-02"
    ]
    assert len(batch_rows) == 6
    assert sum(row["execution_status"] == "CLOSED" for row in batch_rows) == 6

    cycles = {
        (
            ruler["ruler_name"],
            cycle.get(
                "source_canonical_parent_cycle_ref",
                cycle["canonical_parent_cycle_ref"],
            ),
        ): cycle
        for ruler in analysis["records"]
        for cycle in ruler["D_portfolio_metrics"]["cycle_q_adjudications"]
    }
    expected = {
        ("刘启", "HAN-SEVEN-KINGDOMS"): (
            {"P": 4, "S": 5, "M": 4, "A": 3},
            {"SB": 4, "SN": 0, "BCP": 5, "BCN": 0, "WR": 0},
            -12, {"lower": -12, "upper": -12},
        ),
        ("刘彻", "WAR-LEAD-HAN-XIONGNU-124-123"): (
            {"P": 3, "S": 4, "M": 4, "A": 4},
            {"SB": 3, "SN": 2, "BCP": 0, "BCN": 0, "WR": 4},
            -24, {"lower": -24, "upper": -20},
        ),
        ("曹叡", "CAMPAIGN-SHU-FIRST-NORTH-227-228"): (
            {"P": 1, "S": 3, "M": 2, "A": 1},
            {"SB": 2, "SN": 0, "BCP": 3, "BCN": 0, "WR": 0},
            -2, {"lower": -7, "upper": 0},
        ),
        ("司马昭", "CAMPAIGN-V076-SG-SHU-DIDAO-255"): (
            {"P": 4, "S": 3, "M": 2, "A": 1},
            {"SB": 1, "SN": 0, "BCP": 2, "BCN": 0, "WR": 0},
            -21, {"lower": -22, "upper": -19},
        ),
        ("刘禅", "WAR-LEAD-SG-WEI-HANZHONG-244"): (
            {"P": 1, "S": 1, "M": 2, "A": 1},
            {"SB": 3, "SN": 0, "BCP": 3, "BCN": 0, "WR": 0},
            10, {"lower": 1, "upper": 12},
        ),
        ("孙权", "CAMPAIGN-V072-SG-WEI-WU-234"): (
            {"P": 1, "S": 0, "M": 4, "A": 2},
            {"SB": 0, "SN": 0, "BCP": 0, "BCN": 0, "WR": 1},
            -8, {"lower": -10, "upper": -5},
        ),
    }
    for key, (costs, benefits, q_value, q_range) in expected.items():
        cycle = cycles[key]
        assert cycle["cost_axes"] == costs
        assert cycle["benefit_axes"] == benefits
        assert cycle["q_contribution"] == q_value
        assert cycle["q_candidate_range"] == q_range
        assert cycle["strategic_chain_rollup"]["chain_net_q"] == q_value
        assert cycle["legacy_axis_semantics_status"] == (
            "MANUAL_RESIDUAL_FACT_CLOSED"
        )

    seven = cycles[("刘启", "HAN-SEVEN-KINGDOMS")]
    assert seven["personnel_cost_adjudication"]["P_scoring"] == 4
    assert seven["wr_evidence_adjudication"]["WR_scoring"] == 0
    assert "内部系统转手" in seven["wr_evidence_adjudication"]["basis"]
    caorui = cycles[("曹叡", "CAMPAIGN-SHU-FIRST-NORTH-227-228")]
    assert caorui["member_cycle_refs"] == [
        "WAR-LEAD-SG-SHU-NORTH-227", "WAR-LEAD-SG-SHU-NORTH-228",
    ]
    assert caorui["personnel_cost_adjudication"]["P_scoring"] == 1
    liushan = cycles[("刘禅", "WAR-LEAD-SG-WEI-HANZHONG-244")]
    assert liushan["personnel_cost_adjudication"]["P_scoring"] == 1
    assert liushan["system_damage_adjudication"]["S_scoring"] == 1

    sunquan = cycles[("孙权", "CAMPAIGN-V072-SG-WEI-WU-234")]
    assert sunquan["wr_evidence_adjudication"] | {} == {
        **sunquan["wr_evidence_adjudication"],
        "wr_evidence_status": "SIMPLIFIED_INFERRED",
        "asset_base_grade": {"lower": 1, "upper": 2},
        "transfer_mode": "PARTIAL_FIELD_CAPTURE",
        "realization_retention": "PARTIAL_OR_UNCERTAIN",
        "WR_lower": 0,
        "WR_upper": 2,
        "WR_scoring": 1,
    }
    assert sunquan["asset_components"] | {} == {
        **sunquan["asset_components"],
        "A_scoring": 2,
        "lower_grade": 1,
        "upper_grade": 2,
    }
    assert "不声称任何具体缴获清单" in (
        sunquan["wr_evidence_adjudication"]["basis"]
    )

    summaries = {row["ruler_name"]: row for row in analysis["ruler_summaries"]}
    assert (summaries["刘启"]["Q"], summaries["刘启"]["K"], summaries["刘启"]["T"]) == (-40, 2, 2)
    assert (summaries["刘彻"]["Q"], summaries["刘彻"]["K"], summaries["刘彻"]["T"]) == (-230, 19, 19)
    assert (summaries["曹叡"]["Q"], summaries["曹叡"]["K"], summaries["曹叡"]["T"]) == (-16, 4, 4)
    assert (summaries["司马昭"]["Q"], summaries["司马昭"]["K"], summaries["司马昭"]["T"]) == (-41, 3, 3)
    assert (summaries["刘禅"]["Q"], summaries["刘禅"]["K"], summaries["刘禅"]["T"]) == (-7, 4, 4)
    assert (summaries["孙权"]["Q"], summaries["孙权"]["K"], summaries["孙权"]["T"]) == (-78, 9, 9)


def test_manual_unknown_batch_03_closes_six_subject_views_and_parent_states() -> None:
    formal = json.loads(
        (
            ROOT
            / "docs/评分结算/第三项军事与边疆净收益/军事成本收益比/01-皇帝D项正式结算.json"
        ).read_text(encoding="utf-8")
    )
    config = json.loads(
        (ROOT / "config/third-item-d-cycle-adjudications.json").read_text(
            encoding="utf-8"
        )
    )
    analysis = build_formal_linear_q_analysis(
        formal["records"], config, _paired_payload()
    )
    audit = analysis["legacy_unknown_manual_batch_audit"]
    batch_rows = [
        row for row in audit["records"]
        if row["batch_ref"] == "LEGACY-UNKNOWN-MANUAL-BATCH-03"
    ]
    assert len(batch_rows) == 6
    assert {row["execution_status"] for row in batch_rows} == {"CLOSED"}

    cycles = {
        (
            ruler["ruler_name"],
            cycle.get(
                "source_canonical_parent_cycle_ref",
                cycle["canonical_parent_cycle_ref"],
            ),
        ): cycle
        for ruler in analysis["records"]
        for cycle in ruler["D_portfolio_metrics"]["cycle_q_adjudications"]
    }
    expected = {
        ("冯太后", "NC-HUAIBEI-FIVE-FORTS-480-481"): (
            {"P": 3, "S": 3, "M": 2, "A": 1},
            {"SB": 3, "SN": 0, "BCP": 3, "BCN": 0, "WR": 0},
            -6, {"lower": -11, "upper": -6},
        ),
        ("朱温", "ZZTJ-267-LINGZHOU-BINNING-0909"): (
            {"P": 3, "S": 0, "M": 3, "A": 3},
            {"SB": 2, "SN": 3, "BCP": 3, "BCN": 0, "WR": 1},
            -11, {"lower": -13, "upper": -9},
        ),
        ("刘奭", "HAN-LONGXI-QIANG-42"): (
            {"P": 2, "S": 2, "M": 3, "A": 2},
            {"SB": 2, "SN": 0, "BCP": 1, "BCN": 0, "WR": 0},
            -10, {"lower": -10, "upper": -5},
        ),
        ("刘奭", "HAN-ZHIZHI-44-36"): (
            {"P": 1, "S": 0, "M": 3, "A": 2},
            {"SB": 4, "SN": 0, "BCP": 0, "BCN": 0, "WR": 1},
            9, {"lower": 5, "upper": 10},
        ),
        ("孙皓", "WAR-LEAD-JINWU-JIAOZHI-268"): (
            {"P": 2, "S": 4, "M": 3, "A": 2},
            {"SB": 3, "SN": 0, "BCP": 4, "BCN": 0, "WR": 1},
            -3, {"lower": -5, "upper": 10},
        ),
        ("孙皓", "CAMPAIGN-V079-JINWU-XILING-272"): (
            {"P": 1, "S": 3, "M": 2, "A": 1},
            {"SB": 3, "SN": 0, "BCP": 3, "BCN": 0, "WR": 0},
            2, {"lower": -10, "upper": 4},
        ),
    }
    for key, (costs, benefits, q_value, q_range) in expected.items():
        cycle = cycles[key]
        assert cycle["cost_axes"] == costs
        assert cycle["benefit_axes"] == benefits
        assert cycle["q_contribution"] == q_value
        assert cycle["q_candidate_range"] == q_range
        assert cycle["strategic_chain_rollup"]["chain_net_q"] == q_value
        assert cycle["legacy_axis_semantics_status"] == (
            "MANUAL_RESIDUAL_FACT_CLOSED"
        )

    feng = cycles[("冯太后", "NC-HUAIBEI-FIVE-FORTS-480-481")]
    assert feng["route"] == "D_INTERNAL_SUPPRESSION"
    assert feng["personnel_cost_adjudication"]["equivalent_range"] == [6000, 9999]
    assert "北魏国家系统" in feng["wr_evidence_adjudication"]["basis"]

    zhu_wen = cycles[("朱温", "ZZTJ-267-LINGZHOU-BINNING-0909")]
    assert zhu_wen["system_damage_adjudication"]["status"] == "S0_CONFIRMED"
    assert zhu_wen["wr_evidence_adjudication"] | {} == {
        **zhu_wen["wr_evidence_adjudication"],
        "transfer_mode": "PARTIAL_FIELD_CAPTURE",
        "realization_retention": "PARTIAL_OR_UNCERTAIN",
        "WR_lower": 0,
        "WR_upper": 2,
        "WR_scoring": 1,
    }
    assert "阶段终点仍由后梁持有" in zhu_wen["benefit_axis_gates"]["BCP"]
    assert "不能从败退机械生成BCN" in zhu_wen["benefit_axis_gates"]["BCN"]

    zhizhi = cycles[("刘奭", "HAN-ZHIZHI-44-36")]
    assert zhizhi["system_damage_adjudication"]["status"] == "S0_CONFIRMED"
    assert zhizhi["benefit_axes"]["SB"] == 4
    assert "不上SB5" in zhizhi["benefit_axis_gates"]["SB"]
    assert zhizhi["wr_evidence_adjudication"]["wr_evidence_status"] == (
        "EXPLICIT_REALIZED"
    )

    jiaozhi = cycles[("孙皓", "WAR-LEAD-JINWU-JIAOZHI-268")]
    assert jiaozhi["system_damage_adjudication"]["affected_area_refs"] == [
        "交趾郡", "郁林郡", "九真郡", "日南郡及交州行政—交通网络",
    ]
    assert jiaozhi["wr_evidence_adjudication"]["transfer_mode"] == (
        "CAMP_OR_MAJOR_FORCE_CAPTURE"
    )
    xiling = cycles[("孙皓", "CAMPAIGN-V079-JINWU-XILING-272")]
    assert xiling["wr_evidence_adjudication"]["WR_scoring"] == 0
    assert "内部人口、城地" in xiling["wr_evidence_adjudication"]["basis"]

    summaries = {row["ruler_name"]: row for row in analysis["ruler_summaries"]}
    assert (summaries["冯太后"]["Q"], summaries["冯太后"]["K"], summaries["冯太后"]["T"]) == (13, 4, 4)
    assert (summaries["朱温"]["Q"], summaries["朱温"]["K"], summaries["朱温"]["T"]) == (9, 2, 2)
    assert (summaries["刘奭"]["Q"], summaries["刘奭"]["K"], summaries["刘奭"]["T"]) == (-1, 2, 2)
    assert (summaries["孙皓"]["Q"], summaries["孙皓"]["K"], summaries["孙皓"]["T"]) == (-4, 3, 3)


def test_manual_unknown_batch_04_splits_mixed_146_02_by_investment_boundary() -> None:
    formal = json.loads(
        (
            ROOT
            / "docs/评分结算/第三项军事与边疆净收益/军事成本收益比/01-皇帝D项正式结算.json"
        ).read_text(encoding="utf-8")
    )
    config = json.loads(
        (ROOT / "config/third-item-d-cycle-adjudications.json").read_text(
            encoding="utf-8"
        )
    )
    analysis = build_formal_linear_q_analysis(
        formal["records"], config, _paired_payload()
    )
    audit = analysis["legacy_unknown_manual_batch_audit"]
    batch_rows = [
        row for row in audit["records"]
        if row["batch_ref"] == "LEGACY-UNKNOWN-MANUAL-BATCH-04"
    ]
    assert len(batch_rows) == 9
    assert sum(row["execution_status"] == "CLOSED" for row in batch_rows) == 8
    assert sum(
        row["execution_status"] == "EXCLUDED_FROM_D_MATERIAL"
        for row in batch_rows
    ) == 1

    cycles = {
        cycle.get(
            "source_canonical_parent_cycle_ref",
            cycle["canonical_parent_cycle_ref"],
        ): cycle
        for ruler in analysis["records"]
        if ruler["ruler_name"] == "萧衍"
        for cycle in ruler["D_portfolio_metrics"]["cycle_q_adjudications"]
    }
    expected = {
        "NC-V145-LEAD-145-04": (
            {"P": 2, "S": 4, "M": 3, "A": 3},
            {"SB": 3, "SN": 0, "BCP": 4, "BCN": 0, "WR": 0},
            -6, {"lower": -6, "upper": -6},
        ),
        "NC-V146-LEAD-146-02-LUOKOU-YANGSHI": (
            {"P": 1, "S": 0, "M": 1, "A": 1},
            {"SB": 0, "SN": 0, "BCP": 0, "BCN": 0, "WR": 0},
            -6, {"lower": -6, "upper": -6},
        ),
        "NC-V146-LEAD-146-02-XIAOXIAN": (
            {"P": 1, "S": 0, "M": 1, "A": 1},
            {"SB": 0, "SN": 0, "BCP": 0, "BCN": 0, "WR": 0},
            -6, {"lower": -6, "upper": -6},
        ),
        "NC-V146-LEAD-146-02-YIZHOU-JIAOSENGHU": (
            {"P": 1, "S": 2, "M": 1, "A": 0},
            {"SB": 2, "SN": 0, "BCP": 1, "BCN": 0, "WR": 0},
            -2, {"lower": -2, "upper": 2},
        ),
        "NC-V146-LEAD-146-06": (
            {"P": 4, "S": 0, "M": 4, "A": 4},
            {"SB": 0, "SN": 3, "BCP": 0, "BCN": 0, "WR": 0},
            -36, {"lower": -36, "upper": -36},
        ),
        "NC-V147-LEAD-147-05": (
            {"P": 2, "S": 4, "M": 2, "A": 2},
            {"SB": 2, "SN": 0, "BCP": 3, "BCN": 0, "WR": 0},
            -11, {"lower": -14, "upper": -2},
        ),
        "NC-V150-LEAD-150-06": (
            {"P": 3, "S": 0, "M": 3, "A": 3},
            {"SB": 0, "SN": 3, "BCP": 0, "BCN": 0, "WR": 0},
            -30, {"lower": -30, "upper": -26},
        ),
        "NC-CHEN-QINGZHI-YUANHAO-529": (
            {"P": 3, "S": 0, "M": 3, "A": 3},
            {"SB": 0, "SN": 2, "BCP": 0, "BCN": 0, "WR": 0},
            -26, {"lower": -30, "upper": -26},
        ),
    }
    for ref, (costs, benefits, q_value, q_range) in expected.items():
        cycle = cycles[ref]
        assert cycle["cost_axes"] == costs
        assert cycle["benefit_axes"] == benefits
        assert cycle["q_contribution"] == q_value
        assert cycle["q_candidate_range"] == q_range
        assert cycle["strategic_chain_rollup"]["chain_net_q"] == q_value
        assert cycle["legacy_axis_semantics_status"] == (
            "MANUAL_RESIDUAL_FACT_CLOSED"
        )

    bazhou = cycles["NC-V154-LEAD-154-02-BAZHOU"]
    assert bazhou["system_damage_adjudication"] | {} == {
        **bazhou["system_damage_adjudication"],
        "S_lower": 2,
        "S_upper": 2,
        "S_scoring": 2,
    }
    assert "地方防御、行政短期中断" in bazhou[
        "system_damage_adjudication"
    ]["cross_axis_basis"]
    assert "BCN2只消费父周期终局" in bazhou[
        "system_damage_adjudication"
    ]["cross_axis_basis"]
    assert "主将与守军失亡分别由P/A消费" in bazhou[
        "system_damage_adjudication"
    ]["inference_basis"]

    xiao_hong = cycles["NC-V146-LEAD-146-06"]
    assert xiao_hong["system_damage_adjudication"]["status"] == "S0_CONFIRMED"
    assert "梁境" in xiao_hong["system_damage_adjudication"]["S0_basis"]
    pengcheng = cycles["NC-V150-LEAD-150-06"]
    assert pengcheng["benefit_axes"]["BCP"] == 0
    assert "阶段得而复失" in pengcheng["benefit_axis_gates"]["BCN"]
    yuanhao = cycles["NC-CHEN-QINGZHI-YUANHAO-529"]
    assert yuanhao["member_cycle_refs"] == [
        "WAR-LEAD-153-01", "WAR-LEAD-153-02",
    ]
    assert yuanhao["benefit_axes"]["BCP"] == 0
    assert yuanhao["wr_evidence_adjudication"]["WR_scoring"] == 0

    split_refs = {
        "NC-V146-LEAD-146-02-LUOKOU-YANGSHI",
        "NC-V146-LEAD-146-02-XIAOXIAN",
        "NC-V146-LEAD-146-02-YIZHOU-JIAOSENGHU",
    }
    assert "NC-V146-LEAD-146-02" not in cycles
    assert split_refs <= set(cycles)
    split_cycles = [cycles[ref] for ref in split_refs]
    assert len({cycle["d_investment_cycle_identity"] for cycle in split_cycles}) == 3
    assert len({tuple(cycle["member_cycle_refs"]) for cycle in split_cycles}) == 3
    claim_refs = [
        claim["benefit_claim_ref"]
        for cycle in split_cycles
        for claim in cycle.get("benefit_claims") or ()
    ]
    assert len(claim_refs) == len(set(claim_refs)) == 2
    assert "NC-V146-LEAD-146-02-YONGZHOU" not in cycles
    yizhou = cycles["NC-V146-LEAD-146-02-YIZHOU-JIAOSENGHU"]
    assert yizhou["route"] == "D_INTERNAL_SUPPRESSION"
    assert yizhou["benefit_axes"] == {
        "SB": 2, "SN": 0, "BCP": 1, "BCN": 0, "WR": 0,
    }
    assert all(
        "YIZHOU" not in str(cycle.get("benefit_claims") or ())
        for cycle in (
            cycles["NC-V146-LEAD-146-02-LUOKOU-YANGSHI"],
            cycles["NC-V146-LEAD-146-02-XIAOXIAN"],
        )
    )

    summaries = {row["ruler_name"]: row for row in analysis["ruler_summaries"]}
    assert (summaries["萧衍"]["Q"], summaries["萧衍"]["K"], summaries["萧衍"]["T"]) == (
        -542, 34, 34,
    )


def test_manual_unknown_batch_05_splits_xiao_yan_by_investment_boundary() -> None:
    formal = json.loads(
        (
            ROOT
            / "docs/评分结算/第三项军事与边疆净收益/军事成本收益比/01-皇帝D项正式结算.json"
        ).read_text(encoding="utf-8")
    )
    config = json.loads(
        (ROOT / "config/third-item-d-cycle-adjudications.json").read_text(
            encoding="utf-8"
        )
    )
    analysis = build_formal_linear_q_analysis(
        formal["records"], config, _paired_payload()
    )
    audit = analysis["legacy_unknown_manual_batch_audit"]
    batch_rows = [
        row for row in audit["records"]
        if row["batch_ref"] == "LEGACY-UNKNOWN-MANUAL-BATCH-05"
    ]
    assert len(batch_rows) == 15
    assert sum(row["execution_status"] == "CLOSED" for row in batch_rows) == 10
    assert sum(row["execution_status"].startswith("BLOCKED_AT_") for row in batch_rows) == 0
    assert sum(
        row["execution_status"] == "EXCLUDED_FROM_D_MATERIAL"
        for row in batch_rows
    ) == 5

    cycles = {
        cycle.get(
            "source_canonical_parent_cycle_ref",
            cycle["canonical_parent_cycle_ref"],
        ): cycle
        for ruler in analysis["records"]
        if ruler["ruler_name"] == "萧衍"
        for cycle in ruler["D_portfolio_metrics"]["cycle_q_adjudications"]
    }
    original_refs = {
        "NC-V154-LEAD-154-02",
        "NC-V156-LEAD-156-03",
        "NC-V158-LEAD-158-07",
        "NC-LI-BI-541-548",
        "NC-V162-LEAD-162-06",
        "NC-V162-LEAD-162-09",
    }
    assert original_refs.isdisjoint(cycles)

    expected = {
        "NC-V154-LEAD-154-02-BAZHOU": (
            {"P": 3, "S": 2, "M": 2, "A": 2},
            {"SB": 0, "SN": 1, "BCP": 0, "BCN": 2, "WR": 0},
            -34, {"lower": -42, "upper": -34},
        ),
        "NC-V154-LEAD-154-02-XUANHU": (
            {"P": 1, "S": 0, "M": 2, "A": 1},
            {"SB": 1, "SN": 0, "BCP": 0, "BCN": 0, "WR": 1},
            -1, {"lower": -7, "upper": 1},
        ),
        "NC-V156-LEAD-156-03-LIANG-HANNAN": (
            {"P": 1, "S": 4, "M": 2, "A": 3},
            {"SB": 0, "SN": 2, "BCP": 0, "BCN": 3, "WR": 0},
            -42, {"lower": -50, "upper": -42},
        ),
        "NC-LI-BI-541-544-FIRST-EXPEDITION": (
            {"P": 3, "S": 4, "M": 2, "A": 2},
            {"SB": 0, "SN": 2, "BCP": 0, "BCN": 4, "WR": 0},
            -52, {"lower": -56, "upper": -52},
        ),
        "NC-LI-BI-542-GUANGZHOU-MUTINY": (
            {"P": 1, "S": 2, "M": 1, "A": 1},
            {"SB": 2, "SN": 0, "BCP": 1, "BCN": 0, "WR": 0},
            -3, {"lower": -3, "upper": 1},
        ),
        "NC-LI-BI-545-546-RENEWED-EXPEDITION": (
            {"P": 1, "S": 0, "M": 3, "A": 1},
            {"SB": 3, "SN": 0, "BCP": 3, "BCN": 0, "WR": 1},
            15, {"lower": 6, "upper": 19},
        ),
        "NC-LI-BI-548-LITIANBAO-FINAL": (
            {"P": 1, "S": 2, "M": 2, "A": 1},
            {"SB": 3, "SN": 0, "BCP": 3, "BCN": 0, "WR": 0},
            6, {"lower": -1, "upper": 10},
        ),
        "NC-V162-LEAD-162-06-MAXI-FIRST": (
            {"P": 1, "S": 2, "M": 2, "A": 2},
            {"SB": 0, "SN": 2, "BCP": 0, "BCN": 0, "WR": 0},
            -24, {"lower": -28, "upper": -15},
        ),
        "NC-V162-LEAD-162-09-YUANJINGZHONG": (
            {"P": 1, "S": 2, "M": 1, "A": 0},
            {"SB": 1, "SN": 0, "BCP": 1, "BCN": 0, "WR": 0},
            -6, {"lower": -6, "upper": -2},
        ),
        "NC-V162-LEAD-162-09-LAN-BROTHERS": (
            {"P": 1, "S": 2, "M": 1, "A": 0},
            {"SB": 2, "SN": 0, "BCP": 1, "BCN": 0, "WR": 0},
            -2, {"lower": -2, "upper": 2},
        ),
    }
    for ref, (costs, benefits, q_value, q_range) in expected.items():
        cycle = cycles[ref]
        assert cycle["cost_axes"] == costs
        assert cycle["benefit_axes"] == benefits
        assert cycle["q_contribution"] == q_value
        assert cycle["q_candidate_range"] == q_range
        assert cycle["legacy_axis_semantics_status"] == (
            "MANUAL_RESIDUAL_FACT_CLOSED"
        )

    excluded_refs = {
        "NC-V154-LEAD-154-02-DEMOBILIZATION-TUNTIAN",
        "NC-V156-LEAD-156-03-WEI-YILI",
        "NC-V158-LEAD-158-07",
        "NC-V162-LEAD-162-06-CHANGSHA-SECOND",
        "NC-V162-LEAD-162-09-NORTHBOUND",
    }
    assert excluded_refs.isdisjoint(cycles)

    materialized_refs = set(expected)
    materialized = [cycles[ref] for ref in materialized_refs]
    assert len({cycle["d_investment_cycle_identity"] for cycle in materialized}) == 10
    assert len({tuple(cycle["member_cycle_refs"]) for cycle in materialized}) == 10
    claim_refs = [
        claim["benefit_claim_ref"]
        for cycle in materialized
        for claim in cycle.get("benefit_claims") or ()
    ]
    assert len(claim_refs) == len(set(claim_refs))

    li_bi_rebellion_refs = {
        "NC-LI-BI-541-544-FIRST-EXPEDITION",
        "NC-LI-BI-545-546-RENEWED-EXPEDITION",
        "NC-LI-BI-548-LITIANBAO-FINAL",
    }
    assert {
        cycles[ref]["strategic_result_chain_ref"] for ref in li_bi_rebellion_refs
    } == {
        "CHAIN-LIANG-LIBI-REBELLION-541-548"
    }
    assert cycles["NC-LI-BI-542-GUANGZHOU-MUTINY"][
        "strategic_result_chain_ref"
    ] == "CHAIN-LIANG-GUANGZHOU-MUTINY-542"
    assert sum(
        cycles[ref]["q_contribution"]
        for ref in li_bi_rebellion_refs | {"NC-LI-BI-542-GUANGZHOU-MUTINY"}
    ) == -34

    summaries = {row["ruler_name"]: row for row in analysis["ruler_summaries"]}
    assert (summaries["萧衍"]["Q"], summaries["萧衍"]["K"], summaries["萧衍"]["T"]) == (
        -542, 34, 34,
    )


def test_manual_unknown_batch_06_excludes_noninvestment_and_post_window_cycles() -> None:
    formal = json.loads(
        (
            ROOT
            / "docs/评分结算/第三项军事与边疆净收益/军事成本收益比/01-皇帝D项正式结算.json"
        ).read_text(encoding="utf-8")
    )
    config = json.loads(
        (ROOT / "config/third-item-d-cycle-adjudications.json").read_text(
            encoding="utf-8"
        )
    )
    target_refs = {
        "NC-V146-LEAD-146-02-YONGZHOU",
        "NC-V162-LEAD-162-06-CHANGSHA-SECOND",
        "NC-V162-LEAD-162-09-NORTHBOUND",
    }
    resolutions = {
        child["investment_cycle_ref"]: child
        for batch in config["legacy_unknown_manual_batches"]
        for record in batch["records"]
        for child in record.get("split_cycles") or ()
        if child.get("investment_cycle_ref") in target_refs
    }
    assert set(resolutions) == target_refs
    assert all(
        row["status"] == "EXCLUDED_FROM_D_MATERIAL"
        for row in resolutions.values()
    )
    assert "没有梁方防御授权" in resolutions[
        "NC-V146-LEAD-146-02-YONGZHOU"
    ]["reason"]
    assert "死亡后的六月—八月" in resolutions[
        "NC-V162-LEAD-162-06-CHANGSHA-SECOND"
    ]["reason"]
    assert resolutions["NC-V162-LEAD-162-06-CHANGSHA-SECOND"][
        "member_cycle_refs"
    ] == ["WAR-LEAD-162-06::CHANGSHA-SECOND", "WAR-LEAD-163-05"]
    assert "死亡后的九月至十二月" in resolutions[
        "NC-V162-LEAD-162-09-NORTHBOUND"
    ]["reason"]
    assert resolutions["NC-V162-LEAD-162-09-NORTHBOUND"][
        "member_cycle_refs"
    ] == ["WAR-LEAD-162-09::NORTHBOUND", "WAR-LEAD-163-01"]

    analysis = build_formal_linear_q_analysis(
        formal["records"], config, _paired_payload()
    )
    xiaoyan_cycles = [
        cycle
        for ruler in analysis["records"]
        if ruler["ruler_name"] == "萧衍"
        for cycle in ruler["D_portfolio_metrics"]["cycle_q_adjudications"]
    ]
    assert target_refs.isdisjoint({
        cycle.get(
            "source_canonical_parent_cycle_ref",
            cycle["canonical_parent_cycle_ref"],
        )
        for cycle in xiaoyan_cycles
    })
    assert all(cycle["q_contribution"] is not None for cycle in xiaoyan_cycles)
    assert len({cycle["d_investment_cycle_identity"] for cycle in xiaoyan_cycles}) == 34
    claim_refs = [
        claim["benefit_claim_ref"]
        for cycle in xiaoyan_cycles
        for claim in cycle.get("benefit_claims") or ()
    ]
    assert len(claim_refs) == len(set(claim_refs))
    assert analysis["canonical_audit"]["duplicate_investment_cycle_id_count"] == 0
    assert analysis["canonical_audit"]["duplicate_strict_benefit_claim_count"] == 0
    summaries = {row["ruler_name"]: row for row in analysis["ruler_summaries"]}
    assert (summaries["萧衍"]["Q"], summaries["萧衍"]["K"], summaries["萧衍"]["T"]) == (
        -542, 34, 34,
    )


def test_manual_unknown_batch_07_closes_yuwen_tai_with_distinct_yubi_cycles() -> None:
    formal = json.loads(
        (
            ROOT
            / "docs/评分结算/第三项军事与边疆净收益/军事成本收益比/01-皇帝D项正式结算.json"
        ).read_text(encoding="utf-8")
    )
    config = json.loads(
        (ROOT / "config/third-item-d-cycle-adjudications.json").read_text(
            encoding="utf-8"
        )
    )
    batch = next(
        row for row in config["legacy_unknown_manual_batches"]
        if row["batch_ref"] == "LEGACY-UNKNOWN-MANUAL-BATCH-07"
    )
    assert len(batch["records"]) == 6
    by_old = {row["old_parent_cycle_ref"]: row for row in batch["records"]}
    assert by_old["WAR-LEAD-157-05"]["status"] == "EXCLUDED_FROM_D_MATERIAL"
    assert by_old["NC-V158-LEAD-158-03"]["status"] == "MERGED_INTO_MANUAL"
    split = {
        row["investment_cycle_ref"]: row
        for row in by_old["NC-V158-LEAD-158-04"]["split_cycles"]
    }
    assert split["NC-V158-LEAD-158-04-HENAN-LOCAL-RESPONSES"][
        "first_blocked_step"
    ] == 3
    assert split["NC-V158-LEAD-158-04-JINYONG-TERMINAL"][
        "replacement_investment_cycle_ref"
    ] == "NC-WESTERN-WEI-MANGSHAN-RETURN-CHANGAN-538"

    analysis = build_formal_linear_q_analysis(
        formal["records"], config, _paired_payload()
    )
    yuwen_cycles = {
        cycle["canonical_parent_cycle_ref"]: cycle
        for ruler in analysis["records"]
        if ruler["ruler_name"] == "宇文泰"
        for cycle in ruler["D_portfolio_metrics"]["cycle_q_adjudications"]
    }
    expected = {
        "NC-WESTERN-WEI-MANGSHAN-RETURN-CHANGAN-538": (
            {"P": 1, "S": 4, "M": 3, "A": 3},
            {"SB": 3, "SN": 0, "BCP": 3, "BCN": 2, "WR": 2},
            -7,
        ),
        "NC-WESTERN-WEI-YUBI-FOUNDATION-FIRST-DEFENSE-538-542": (
            {"P": 1, "S": 1, "M": 2, "A": 2},
            {"SB": 2, "SN": 0, "BCP": 2, "BCN": 0, "WR": 0},
            2,
        ),
        "NC-WESTERN-WEI-YUBI-SECOND-DEFENSE-546": (
            {"P": 1, "S": 3, "M": 2, "A": 3},
            {"SB": 4, "SN": 0, "BCP": 2, "BCN": 0, "WR": 0},
            1,
        ),
        "NC-V163-LEAD-163-09": (
            {"P": 0, "S": 0, "M": 3, "A": 3},
            {"SB": 0, "SN": 0, "BCP": 0, "BCN": 0, "WR": 0},
            -6,
        ),
    }
    for ref, (costs, benefits, q) in expected.items():
        assert yuwen_cycles[ref]["cost_axes"] == costs
        assert yuwen_cycles[ref]["benefit_axes"] == benefits
        assert yuwen_cycles[ref]["q_contribution"] == q

    first_yubi = yuwen_cycles[
        "NC-WESTERN-WEI-YUBI-FOUNDATION-FIRST-DEFENSE-538-542"
    ]
    second_yubi = yuwen_cycles["NC-WESTERN-WEI-YUBI-SECOND-DEFENSE-546"]
    assert first_yubi["strategic_result_chain_ref"] == second_yubi[
        "strategic_result_chain_ref"
    ]
    assert first_yubi["benefit_claims"][0]["benefit_window_end"] < (
        second_yubi["benefit_claims"][0]["benefit_window_start"]
    )
    assert "不重复筑城" in second_yubi["boundary_decision"]["reason"]
    assert second_yubi["asset_components"]["status"] == (
        "REUSED_BASE_WITH_NEW_CONSUMPTION_ROLLUP"
    )

    assert "NC-V158-LEAD-158-04-HENAN-LOCAL-RESPONSES" not in yuwen_cycles
    assert {
        ref for ref, cycle in yuwen_cycles.items()
        if cycle["q_contribution"] is None
    } == {
        "NC-WESTERN-WEI-LUOYANG-SHIYUNBAO-RAID-538",
        "NC-WESTERN-WEI-GUANGZHOU-ZHAOGANG-RAID-538",
    }
    assert "NC-WESTERN-WEI-JIANGLING-554" in yuwen_cycles
    summaries = {row["ruler_name"]: row for row in analysis["ruler_summaries"]}
    assert (summaries["宇文泰"]["Q"], summaries["宇文泰"]["K"], summaries["宇文泰"]["T"]) == (
        -120, 11, 13,
    )
    assert analysis["canonical_audit"]["duplicate_investment_cycle_id_count"] == 0
    assert analysis["canonical_audit"]["duplicate_strict_benefit_claim_count"] == 0


def test_manual_unknown_batch_08_refines_henan_and_closes_jiangling() -> None:
    formal = json.loads(
        (
            ROOT
            / "docs/评分结算/第三项军事与边疆净收益/军事成本收益比/01-皇帝D项正式结算.json"
        ).read_text(encoding="utf-8")
    )
    config = json.loads(
        (ROOT / "config/third-item-d-cycle-adjudications.json").read_text(
            encoding="utf-8"
        )
    )
    batch = next(
        row for row in config["legacy_unknown_manual_batches"]
        if row["batch_ref"] == "LEGACY-UNKNOWN-MANUAL-BATCH-08"
    )
    assert len(batch["records"]) == 2

    analysis = build_formal_linear_q_analysis(
        formal["records"], config, _paired_payload()
    )
    yuwen_cycles = {
        cycle["canonical_parent_cycle_ref"]: cycle
        for ruler in analysis["records"]
        if ruler["ruler_name"] == "宇文泰"
        for cycle in ruler["D_portfolio_metrics"]["cycle_q_adjudications"]
    }
    expected = {
        "NC-WESTERN-WEI-YILU-KONGCHENG-RECOVERY-538": (
            {"P": 1, "S": 0, "M": 2, "A": 1},
            {"SB": 2, "SN": 0, "BCP": 2, "BCN": 0, "WR": 0},
            7,
            {"lower": 3, "upper": 9},
        ),
        "NC-WESTERN-WEI-XIAO-MIAN-CLEARANCE-538": (
            {"P": 1, "S": 0, "M": 1, "A": 0},
            {"SB": 2, "SN": 0, "BCP": 2, "BCN": 0, "WR": 0},
            9,
            {"lower": 2, "upper": 11},
        ),
        "NC-WESTERN-WEI-JIANGLING-554": (
            {"P": 1, "S": 0, "M": 3, "A": 2},
            {"SB": 3, "SN": 0, "BCP": 3, "BCN": 0, "WR": 3},
            18,
            {"lower": 11, "upper": 20},
        ),
    }
    for ref, (costs, benefits, q, q_range) in expected.items():
        assert yuwen_cycles[ref]["cost_axes"] == costs
        assert yuwen_cycles[ref]["benefit_axes"] == benefits
        assert yuwen_cycles[ref]["q_contribution"] == q
        assert yuwen_cycles[ref]["q_candidate_range"] == q_range

    assert "NC-V158-LEAD-158-04-HENAN-LOCAL-RESPONSES" not in yuwen_cycles
    blocked_refs = {
        ref for ref, cycle in yuwen_cycles.items()
        if cycle["q_contribution"] is None
    }
    assert blocked_refs == {
        "NC-WESTERN-WEI-LUOYANG-SHIYUNBAO-RAID-538",
        "NC-WESTERN-WEI-GUANGZHOU-ZHAOGANG-RAID-538",
    }
    assert {
        yuwen_cycles[ref]["manual_review_status"] for ref in blocked_refs
    } == {"BLOCKED_AT_8"}

    jiangling = yuwen_cycles["NC-WESTERN-WEI-JIANGLING-554"]
    assert jiangling["strategic_result_chain_ref"] == "V165-LEAD-165-WEISHU-553"
    assert jiangling["boundary_decision"]["prior_investment_cycle_ref"] == (
        "V165-LEAD-165-WEISHU-553"
    )
    assert jiangling["boundary_decision"]["prior_result_closed"] is True
    assert jiangling["wr_evidence_adjudication"]["WR_scoring"] == 3
    assert jiangling["wr_evidence_adjudication"]["resource_object_refs"] == [
        "OBJECT-WESTERN-WEI-JIANGLING-CENTRAL-TREASURY-RITUAL-ASSET-POOL-554"
    ]
    assert [
        claim["axis_grades"] for claim in jiangling["benefit_claims"]
    ] == [{"SB": 3}, {"BCP": 3}, {"WR": 3}]
    assert "不满足SB4门禁" in jiangling["benefit_axis_gates"]["SB"]
    assert "被俘人口" in jiangling["wr_evidence_adjudication"]["basis"]
    assert "萧察" in jiangling["asset_components"]["basis"]

    summaries = {row["ruler_name"]: row for row in analysis["ruler_summaries"]}
    yuwen = summaries["宇文泰"]
    assert (yuwen["Q"], yuwen["K"], yuwen["T"]) == (-120, 11, 13)
    known_q = [
        cycle["q_contribution"] for cycle in yuwen_cycles.values()
        if cycle["q_contribution"] is not None
    ]
    assert (
        sum(q > 0 for q in known_q), sum(q < 0 for q in known_q)
    ) == (6, 5)
    assert analysis["canonical_audit"]["duplicate_investment_cycle_id_count"] == 0
    assert analysis["canonical_audit"]["duplicate_strict_benefit_claim_count"] == 0


def test_manual_unknown_batch_09_closes_yuan_ke_and_routes_window_misattribution() -> None:
    formal = json.loads(
        (
            ROOT
            / "docs/评分结算/第三项军事与边疆净收益/军事成本收益比/01-皇帝D项正式结算.json"
        ).read_text(encoding="utf-8")
    )
    config = json.loads(
        (ROOT / "config/third-item-d-cycle-adjudications.json").read_text(
            encoding="utf-8"
        )
    )
    batch = next(
        row for row in config["legacy_unknown_manual_batches"]
        if row["batch_ref"] == "LEGACY-UNKNOWN-MANUAL-BATCH-09"
    )
    assert len(batch["records"]) == 5
    by_old = {row["old_parent_cycle_ref"]: row for row in batch["records"]}
    misattributed = by_old["NC-V148-LEAD-148-02"]
    assert misattributed | {} == {
        **misattributed,
        "status": "WINDOW_MISATTRIBUTED",
        "ruler_name": "元恪",
        "target_ruler_name": "元诩",
        "target_ruler_window_ref": None,
        "target_window_identity_status": "NOT_PRESENT_IN_CURRENT_FORMAL_D",
        "reassignment_status": "PENDING_TARGET_WINDOW_READJUDICATION",
        "exclusion_scope": "SOURCE_RULER_WINDOW_ONLY",
    }

    analysis = build_formal_linear_q_analysis(
        formal["records"], config, _paired_payload()
    )
    yuan_ke_cycles = {
        cycle["canonical_parent_cycle_ref"]: cycle
        for ruler in analysis["records"]
        if ruler["ruler_name"] == "元恪"
        for cycle in ruler["D_portfolio_metrics"]["cycle_q_adjudications"]
    }
    expected = {
        "NC-NORTHERN-WEI-LUYANG-HUYANG-502": (
            {"P": 4, "S": 3, "M": 3, "A": 0},
            {"SB": 2, "SN": 0, "BCP": 1, "BCN": 0, "WR": 0},
            -20,
            {"lower": -20, "upper": -20},
        ),
        "NC-NORTHERN-WEI-ZHONGLI-SHAOYANG-504": (
            {"P": 3, "S": 0, "M": 3, "A": 1},
            {"SB": 0, "SN": 0, "BCP": 0, "BCN": 0, "WR": 1},
            -14,
            {"lower": -17, "upper": -12},
        ),
        "NC-NORTHERN-WEI-JIZHOU-YU-REBELLION-508": (
            {"P": 1, "S": 2, "M": 2, "A": 1},
            {"SB": 2, "SN": 0, "BCP": 2, "BCN": 0, "WR": 0},
            -1,
            {"lower": -5, "upper": -1},
        ),
        "NC-NORTHERN-WEI-HUAIXU-XUANHU-506-508": (
            {"P": 1, "S": 4, "M": 4, "A": 1},
            {"SB": 2, "SN": 0, "BCP": 3, "BCN": 0, "WR": 0},
            -8,
            {"lower": -8, "upper": -8},
        ),
    }
    for ref, (costs, benefits, q, q_range) in expected.items():
        cycle = yuan_ke_cycles[ref]
        assert cycle["cost_axes"] == costs
        assert cycle["benefit_axes"] == benefits
        assert cycle["q_contribution"] == q
        assert cycle["q_candidate_range"] == q_range

    zhongli = yuan_ke_cycles["NC-NORTHERN-WEI-ZHONGLI-SHAOYANG-504"]
    assert zhongli["wr_evidence_adjudication"] | {} == {
        **zhongli["wr_evidence_adjudication"],
        "asset_base_grade": {"lower": 2, "upper": 3},
        "transfer_mode": "PARTIAL_FIELD_CAPTURE",
        "realization_retention": "PARTIAL_OR_UNCERTAIN",
        "WR_lower": 0,
        "WR_upper": 2,
        "WR_scoring": 1,
        "selection_policy": "LOWER_MIDPOINT",
    }
    assert "杀俘人数本身不进入WR" in zhongli[
        "wr_evidence_adjudication"
    ]["basis"]

    luyang = yuan_ke_cycles["NC-NORTHERN-WEI-LUYANG-HUYANG-502"]
    assert "P只消费人员终局" in luyang["personnel_cost_adjudication"]["basis"]
    assert "S3消费本方空间" in luyang["system_damage_adjudication"][
        "inference_basis"
    ]
    assert luyang["asset_components"]["A_scoring"] == 0
    assert luyang["wr_evidence_adjudication"]["WR_scoring"] == 0

    jizhou = yuan_ke_cycles["NC-NORTHERN-WEI-JIZHOU-YU-REBELLION-508"]
    huaixu = yuan_ke_cycles["NC-NORTHERN-WEI-HUAIXU-XUANHU-506-508"]
    assert "BCP2只消费父终点" in jizhou["system_damage_adjudication"][
        "inference_basis"
    ]
    assert huaixu["member_cycle_refs"] == ["WAR-LEAD-146-05", "WAR-LEAD-147-02"]
    assert huaixu["boundary_decision"]["absorbed_member_refs"] == [
        "WAR-LEAD-146-05"
    ]
    assert "BCP3只消费父终点" in huaixu["system_damage_adjudication"][
        "inference_basis"
    ]
    assert "NC-V148-LEAD-148-02" not in yuan_ke_cycles

    summaries = {row["ruler_name"]: row for row in analysis["ruler_summaries"]}
    assert summaries["元恪"] | {} == {
        **summaries["元恪"],
            "Q": -129,
            "Q_mean": -10.75,
        "T": 12,
        "K": 12,
        "positive": 2,
        "zero": 1,
        "negative": 9,
        "closure_rate": 1.0,
    }
    audit = analysis["legacy_unknown_manual_batch_audit"]
    assert audit["window_misattributed_count"] == 1
    batch_rows = [
        row for row in audit["records"]
        if row["batch_ref"] == "LEGACY-UNKNOWN-MANUAL-BATCH-09"
    ]
    assert [row["execution_status"] for row in batch_rows].count("CLOSED") == 4
    assert [row["execution_status"] for row in batch_rows].count(
        "WINDOW_MISATTRIBUTED_PENDING_REASSIGNMENT"
    ) == 1
    assert analysis["canonical_audit"]["duplicate_investment_cycle_id_count"] == 0
    assert analysis["canonical_audit"]["duplicate_strict_benefit_claim_count"] == 0


def test_manual_unknown_batch_10_closes_deng_sui_and_liu_bao() -> None:
    formal = json.loads(
        (
            ROOT
            / "docs/评分结算/第三项军事与边疆净收益/军事成本收益比/01-皇帝D项正式结算.json"
        ).read_text(encoding="utf-8")
    )
    config = json.loads(
        (ROOT / "config/third-item-d-cycle-adjudications.json").read_text(
            encoding="utf-8"
        )
    )
    batch = next(
        row for row in config["legacy_unknown_manual_batches"]
        if row["batch_ref"] == "LEGACY-UNKNOWN-MANUAL-BATCH-10"
    )
    assert batch["max_parent_cycles"] == 4
    assert [row["ruler_name"] for row in batch["records"]] == [
        "邓绥", "刘保", "刘保",
    ]
    assert all("刘宏" not in json.dumps(row, ensure_ascii=False) for row in batch["records"])

    analysis = build_formal_linear_q_analysis(
        formal["records"], config, _paired_payload()
    )
    cycles_by_ruler = {
        ruler["ruler_name"]: {
            cycle["canonical_parent_cycle_ref"]: cycle
            for cycle in ruler["D_portfolio_metrics"]["cycle_q_adjudications"]
        }
        for ruler in analysis["records"]
        if ruler["ruler_name"] in {"邓绥", "刘保"}
    }
    expected = {
        "HAN-XIYU-106-RELIEF": (
            {"P": 1, "S": 2, "M": 3, "A": 2},
            {"SB": 2, "SN": 0, "BCP": 1, "BCN": 0, "WR": 0},
            -6,
            {"lower": -6, "upper": 0},
        ),
        "HAN-XIYU-107-WITHDRAWAL": (
            {"P": 0, "S": 1, "M": 3, "A": 1},
            {"SB": 0, "SN": 0, "BCP": 0, "BCN": 3, "WR": 0},
            -17,
            {"lower": -18, "upper": -17},
        ),
        "HAN-JIAOZHI-136-138": (
            {"P": 1, "S": 4, "M": 3, "A": 3},
            {"SB": 3, "SN": 0, "BCP": 2, "BCN": 0, "WR": 0},
            -8,
            {"lower": -8, "upper": -8},
        ),
        "HAN-SOUTH-XIONGNU-140-144": (
            {"P": 1, "S": 5, "M": 3, "A": 2},
            {"SB": 3, "SN": 0, "BCP": 2, "BCN": 0, "WR": 0},
            -11,
            {"lower": -11, "upper": -11},
        ),
    }
    all_selected = cycles_by_ruler["邓绥"] | cycles_by_ruler["刘保"]
    for ref, (costs, benefits, q, q_range) in expected.items():
        cycle = all_selected[ref]
        assert cycle["cost_axes"] == costs
        assert cycle["benefit_axes"] == benefits
        assert cycle["q_contribution"] == q
        assert cycle["q_candidate_range"] == q_range

    relief = all_selected["HAN-XIYU-106-RELIEF"]
    withdrawal = all_selected["HAN-XIYU-107-WITHDRAWAL"]
    assert relief["strategic_result_chain_ref"] == withdrawal[
        "strategic_result_chain_ref"
    ]
    assert set(relief["member_cycle_refs"]).isdisjoint(
        withdrawal["member_cycle_refs"]
    )
    assert relief["benefit_claims"][0]["benefit_window_end"] < (
        withdrawal["benefit_claims"][0]["benefit_window_start"]
    )
    assert relief["wr_evidence_adjudication"] | {} == {
        **relief["wr_evidence_adjudication"],
        "wr_evidence_status": "SIMPLIFIED_INFERRED",
        "asset_base_grade": {"lower": 2, "upper": 3},
        "transfer_mode": "ROUT_WITH_ASSETS_ESCAPED",
        "realization_retention": "PARTIAL_OR_UNCERTAIN",
        "WR_lower": 0,
        "WR_upper": 1,
        "WR_scoring": 0,
        "selection_policy": "LOWER_MIDPOINT",
    }
    assert "不是史料沉默自动归零" in relief[
        "wr_evidence_adjudication"
    ]["basis"]
    assert withdrawal["asset_components"] | {} == {
        **withdrawal["asset_components"],
        "A_scoring": 1,
        "lower_grade": 1,
        "upper_grade": 2,
    }
    assert "历年屯费不补扣" in withdrawal["asset_components"]["basis"]
    assert "体系关闭只进BCN3" in withdrawal["asset_components"]["basis"]

    jiaozhi = all_selected["HAN-JIAOZHI-136-138"]
    south = all_selected["HAN-SOUTH-XIONGNU-140-144"]
    assert jiaozhi["boundary_decision"]["mode"] == (
        "SINGLE_CONTINUOUS_INVESTMENT_WITH_STRATEGY_CHANGE"
    )
    assert south["boundary_decision"]["mode"] == (
        "SINGLE_CONTINUOUS_MULTI_YEAR_INVESTMENT"
    )
    assert jiaozhi["system_damage_adjudication"]["S_scoring"] == 4
    assert south["system_damage_adjudication"]["S_scoring"] == 5
    assert "BCP2只消费" in jiaozhi["system_damage_adjudication"][
        "inference_basis"
    ]
    assert "BCP2只消费" in south["system_damage_adjudication"][
        "inference_basis"
    ]
    assert jiaozhi["wr_evidence_adjudication"]["WR_scoring"] == 0
    assert south["wr_evidence_adjudication"]["WR_scoring"] == 0
    assert "人口" in jiaozhi["wr_evidence_adjudication"]["basis"]
    assert "人口" in south["wr_evidence_adjudication"]["basis"]

    summaries = {row["ruler_name"]: row for row in analysis["ruler_summaries"]}
    assert summaries["邓绥"] | {} == {
        **summaries["邓绥"],
        "Q": -104,
        "Q_mean": -20.8,
        "T": 5,
        "K": 5,
        "positive": 0,
        "zero": 0,
        "negative": 5,
        "closure_rate": 1.0,
    }
    assert summaries["刘保"] | {} == {
        **summaries["刘保"],
        "Q": -63,
        "Q_mean": -21.0,
        "T": 3,
        "K": 3,
        "positive": 0,
        "zero": 0,
        "negative": 3,
        "closure_rate": 1.0,
    }
    xi_yu = [relief, withdrawal]
    assert sum(
        -p_penalty(cycle["cost_axes"]["P"])
        - 4 * cycle["cost_axes"]["S"]
        - cycle["cost_axes"]["M"]
        - cycle["cost_axes"]["A"]
        for cycle in xi_yu
    ) == -25
    assert sum(
        4 * (cycle["benefit_axes"]["SB"] - cycle["benefit_axes"]["SN"])
        + 3 * (cycle["benefit_axes"]["BCP"] - cycle["benefit_axes"]["BCN"])
        + 2 * cycle["benefit_axes"]["WR"]
        for cycle in xi_yu
    ) == 2
    assert sum(cycle["q_contribution"] for cycle in xi_yu) == -23
    assert analysis["canonical_audit"] | {} == {
        **analysis["canonical_audit"],
            "material_cycle_count_total": 759,
            "strict_curated_cycle_count": 106,
            "manual_residual_fact_closed_cycle_count": 58,
            "legacy_unknown_cycle_count": 54,
        "duplicate_investment_cycle_id_count": 0,
        "duplicate_strict_benefit_claim_count": 0,
        "identity_conservation_mismatch_count": 0,
    }


def test_manual_unknown_batch_11_closes_liu_hong_three_parent_cycles() -> None:
    formal = json.loads(
        (
            ROOT
            / "docs/评分结算/第三项军事与边疆净收益/军事成本收益比/01-皇帝D项正式结算.json"
        ).read_text(encoding="utf-8")
    )
    config = json.loads(
        (ROOT / "config/third-item-d-cycle-adjudications.json").read_text(
            encoding="utf-8"
        )
    )
    batch = next(
        row for row in config["legacy_unknown_manual_batches"]
        if row["batch_ref"] == "LEGACY-UNKNOWN-MANUAL-BATCH-11"
    )
    assert batch["max_parent_cycles"] == 3
    assert [row["old_parent_cycle_ref"] for row in batch["records"]] == [
        "WAR-LEAD-HAN-JIAOZHI-178-181",
        "HAN-YELLOW-TURBAN-184",
        "WAR-LEAD-HAN-ZHANGCHUN-WUHUAN-187-189",
    ]
    assert {row["ruler_name"] for row in batch["records"]} == {"刘宏"}

    analysis = build_formal_linear_q_analysis(
        formal["records"], config, _paired_payload()
    )
    liu_hong = next(
        row for row in analysis["records"] if row["ruler_name"] == "刘宏"
    )
    cycles = {
        cycle["canonical_parent_cycle_ref"]: cycle
        for cycle in liu_hong["D_portfolio_metrics"]["cycle_q_adjudications"]
    }
    expected = {
        "HAN-JIAOZHI-178-181": (
            {"P": 1, "S": 4, "M": 3, "A": 1},
            {"SB": 3, "SN": 0, "BCP": 3, "BCN": 0, "WR": 0},
            -3,
            {"lower": -4, "upper": -3},
        ),
        "HAN-YELLOW-TURBAN-184": (
            {"P": 1, "S": 5, "M": 4, "A": 4},
            {"SB": 3, "SN": 0, "BCP": 3, "BCN": 0, "WR": 0},
            -11,
            {"lower": -11, "upper": -10},
        ),
        "HAN-ZHANGCHUN-WUHUAN-187-189": (
            {"P": 3, "S": 5, "M": 3, "A": 2},
            {"SB": 3, "SN": 0, "BCP": 2, "BCN": 0, "WR": 0},
            -19,
            {"lower": -20, "upper": -17},
        ),
    }
    for ref, (costs, benefits, q_value, q_range) in expected.items():
        cycle = cycles[ref]
        assert cycle["cost_axes"] == costs
        assert cycle["benefit_axes"] == benefits
        assert cycle["q_contribution"] == q_value
        assert cycle["q_candidate_range"] == q_range
        assert cycle["strategic_chain_rollup"]["chain_cost_q"] + cycle[
            "strategic_chain_rollup"
        ]["chain_benefit_q"] == q_value
        assert cycle["legacy_axis_semantics_status"] == (
            "MANUAL_RESIDUAL_FACT_CLOSED"
        )

    jiaozhi = cycles["HAN-JIAOZHI-178-181"]
    assert jiaozhi["boundary_decision"]["mode"] == (
        "SINGLE_CONTINUOUS_FOUR_COMMANDERY_INVESTMENT"
    )
    assert jiaozhi["system_damage_adjudication"]["S_scoring"] == 4
    assert jiaozhi["asset_components"] | {} == {
        **jiaozhi["asset_components"],
        "A_scoring": 1,
        "lower_grade": 1,
        "upper_grade": 2,
    }
    assert "不得把郡县失控" in jiaozhi["asset_components"]["basis"]
    assert "高于136—138案" in jiaozhi["benefit_axis_gates"]["BCP"]
    assert jiaozhi["wr_evidence_adjudication"]["WR_scoring"] == 0

    yellow = cycles["HAN-YELLOW-TURBAN-184"]
    assert yellow["member_cycle_refs"] == ["WAR-LEAD-HAN-YELLOW-TURBAN-184"]
    assert yellow["boundary_decision"]["mode"] == (
        "SINGLE_NATIONAL_AUTHORIZATION_AND_MAIN_FORCE_CHAIN"
    )
    assert yellow["system_damage_adjudication"]["S_scoring"] == 5
    assert "不满足S6" in yellow["system_damage_adjudication"][
        "inference_basis"
    ]
    assert "八州数量和叛军规模本身不作为上档依据" in yellow[
        "system_damage_adjudication"
    ]["inference_basis"]
    assert "不上SB4" in yellow["benefit_axis_gates"]["SB"]
    assert "流量" in yellow["benefit_axis_gates"]["BCP"]
    assert yellow["wr_evidence_adjudication"]["wr_evidence_status"] == (
        "CONFIRMED_NONE"
    )

    zhangchun = cycles["HAN-ZHANGCHUN-WUHUAN-187-189"]
    assert zhangchun["member_cycle_refs"] == [
        "WAR-LEAD-HAN-ZHANGCHUN-WUHUAN-187",
        "WAR-LEAD-HAN-ZHANGCHUN-WUHUAN-187-189",
    ]
    assert zhangchun["personnel_cost_adjudication"]["P_scoring"] == 3
    assert "只消费东汉共同体" in zhangchun[
        "personnel_cost_adjudication"
    ]["basis"]
    assert "敌军死亡" in zhangchun["personnel_cost_adjudication"]["basis"]
    assert zhangchun["system_damage_adjudication"]["S_scoring"] == 5
    assert zhangchun["asset_components"] | {} == {
        **zhangchun["asset_components"],
        "A_scoring": 2,
        "lower_grade": 2,
        "upper_grade": 3,
    }
    assert zhangchun["wr_evidence_adjudication"] | {} == {
        **zhangchun["wr_evidence_adjudication"],
        "wr_evidence_status": "SIMPLIFIED_INFERRED",
        "asset_base_grade": {"lower": 2, "upper": 3},
        "transfer_mode": "ROUT_WITH_ASSETS_ESCAPED",
        "realization_retention": "PARTIAL_OR_UNCERTAIN",
        "WR_lower": 0,
        "WR_upper": 1,
        "WR_scoring": 0,
        "selection_policy": "LOWER_MIDPOINT",
    }
    assert "同一张纯—丘力居集团已收束" in zhangchun[
        "benefit_axis_gates"
    ]["SN"]
    assert "没有证明完整四州长期被占" in zhangchun[
        "benefit_axis_gates"
    ]["BCP"]

    summaries = {row["ruler_name"]: row for row in analysis["ruler_summaries"]}
    assert summaries["刘宏"] | {} == {
        **summaries["刘宏"],
        "Q": -198,
        "Q_mean": -19.8,
        "T": 10,
        "K": 10,
        "positive": 1,
        "zero": 0,
        "negative": 9,
        "closure_rate": 1.0,
    }
    seven = next(
        cycle
        for ruler in analysis["records"] if ruler["ruler_name"] == "刘启"
        for cycle in ruler["D_portfolio_metrics"]["cycle_q_adjudications"]
        if cycle["canonical_parent_cycle_ref"] == "HAN-SEVEN-KINGDOMS"
    )
    liu_bao_jiaozhi = next(
        cycle
        for ruler in analysis["records"] if ruler["ruler_name"] == "刘保"
        for cycle in ruler["D_portfolio_metrics"]["cycle_q_adjudications"]
        if cycle["canonical_parent_cycle_ref"] == "HAN-JIAOZHI-136-138"
    )
    assert (yellow["q_contribution"], seven["q_contribution"]) == (-11, -12)
    assert seven["cost_axes"]["P"] == 4 and yellow["cost_axes"]["P"] == 1
    assert seven["benefit_axes"] | {} == {
        **seven["benefit_axes"], "SB": 4, "BCP": 5,
    }
    assert (liu_bao_jiaozhi["q_contribution"], jiaozhi["q_contribution"]) == (
        -8, -3,
    )
    assert liu_bao_jiaozhi["cost_axes"]["A"] == 3
    assert jiaozhi["cost_axes"]["A"] == 1
    assert min(
        cycle["q_contribution"] for cycle in cycles.values()
        if cycle["q_contribution"] is not None
    ) == -58
    assert analysis["canonical_audit"] | {} == {
        **analysis["canonical_audit"],
            "material_cycle_count_total": 759,
            "strict_curated_cycle_count": 106,
            "manual_residual_fact_closed_cycle_count": 58,
            "legacy_unknown_cycle_count": 54,
        "duplicate_investment_cycle_id_count": 0,
        "duplicate_strict_benefit_claim_count": 0,
        "identity_conservation_mismatch_count": 0,
    }


def test_manual_unknown_batch_12_excludes_foundation_and_engineering_cycles() -> None:
    formal = json.loads(
        (
            ROOT
            / "docs/评分结算/第三项军事与边疆净收益/军事成本收益比/01-皇帝D项正式结算.json"
        ).read_text(encoding="utf-8")
    )
    config = json.loads(
        (ROOT / "config/third-item-d-cycle-adjudications.json").read_text(
            encoding="utf-8"
        )
    )
    batch = next(
        row for row in config["legacy_unknown_manual_batches"]
        if row["batch_ref"] == "LEGACY-UNKNOWN-MANUAL-BATCH-12"
    )
    assert batch["max_parent_cycles"] == 4
    by_old = {row["old_parent_cycle_ref"]: row for row in batch["records"]}
    assert by_old["NC-EAST-WEST-WEI-SPLIT-534"]["status"] == (
        "EXCLUDED_FROM_D_MATERIAL"
    )
    assert "第一项" in by_old["NC-EAST-WEST-WEI-SPLIT-534"]["reason"]
    assert by_old["DEF-LEAD-116-TONGWAN-413"]["status"] == (
        "EXCLUDED_FROM_D_MATERIAL"
    )
    assert "没有实际敌攻" in by_old["DEF-LEAD-116-TONGWAN-413"]["reason"]

    analysis = build_formal_linear_q_analysis(
        formal["records"], config, _paired_payload()
    )
    rulers = {row["ruler_name"]: row for row in analysis["records"]}
    summaries = {row["ruler_name"]: row for row in analysis["ruler_summaries"]}
    all_refs = {
        cycle["canonical_parent_cycle_ref"]
        for ruler in analysis["records"]
        for cycle in ruler["D_portfolio_metrics"]["cycle_q_adjudications"]
    }
    assert "NC-EAST-WEST-WEI-SPLIT-534" not in all_refs
    assert "DEF-LEAD-116-TONGWAN-413" not in all_refs

    gao_cycles = {
        cycle["canonical_parent_cycle_ref"]: cycle
        for cycle in rulers["高欢"]["D_portfolio_metrics"][
            "cycle_q_adjudications"
        ]
    }
    yubi = gao_cycles["NC-EASTERN-WEI-YUBI-SECOND-SIEGE-546"]
    assert yubi["cost_axes"] == {"P": 4, "S": 0, "M": 4, "A": 4}
    assert yubi["benefit_axes"] == {
        "SB": 0, "SN": 0, "BCP": 0, "BCN": 0, "WR": 0,
    }
    assert yubi["q_contribution"] == -24
    assert yubi["q_candidate_range"] == {"lower": -24, "upper": -24}
    assert yubi["system_damage_adjudication"]["status"] == "S0_CONFIRMED"
    assert "西魏控制" in yubi["system_damage_adjudication"]["S0_basis"]
    assert yubi["personnel_cost_adjudication"]["equivalent_range"] == [
        70000, 70000,
    ]
    assert summaries["高欢"] | {} == {
        **summaries["高欢"], "Q": -133, "Q_mean": -26.6, "T": 5, "K": 5,
        "positive": 0, "zero": 0, "negative": 5, "closure_rate": 1.0,
    }

    sui_cycles = {
        cycle["canonical_parent_cycle_ref"]: cycle
        for cycle in rulers["杨坚"]["D_portfolio_metrics"][
            "cycle_q_adjudications"
        ]
    }
    goguryeo = sui_cycles["SUI-GOGURYEO-EXPEDITION-598"]
    assert goguryeo["cost_axes"] == {"P": 5, "S": 0, "M": 4, "A": 3}
    assert goguryeo["benefit_axes"] == {
        "SB": 0, "SN": 0, "BCP": 0, "BCN": 0, "WR": 0,
    }
    assert goguryeo["q_contribution"] == -31
    assert goguryeo["personnel_cost_adjudication"]["equivalent_range"] == [
        240000, 270000,
    ]
    assert goguryeo["wr_evidence_adjudication"]["wr_evidence_status"] == (
        "CONFIRMED_NONE"
    )
    assert summaries["杨坚"] | {} == {
        **summaries["杨坚"], "Q": -46, "Q_mean": -7.6667, "T": 6, "K": 6,
        "positive": 2, "zero": 0, "negative": 4, "closure_rate": 1.0,
    }
    assert analysis["canonical_audit"] | {} == {
        **analysis["canonical_audit"],
        "material_cycle_count_total": 759,
        "strict_curated_cycle_count": 106,
        "manual_residual_fact_closed_cycle_count": 58,
            "legacy_unknown_cycle_count": 54,
        "unreviewed_manual_draft_cycle_count": 0,
        "duplicate_investment_cycle_id_count": 0,
        "duplicate_strict_benefit_claim_count": 0,
        "identity_conservation_mismatch_count": 0,
    }


def test_manual_unknown_batch_13_accepts_lixuan_window_slices() -> None:
    formal = json.loads(
        (
            ROOT
            / "docs/评分结算/第三项军事与边疆净收益/军事成本收益比/01-皇帝D项正式结算.json"
        ).read_text(encoding="utf-8")
    )
    config = json.loads(
        (ROOT / "config/third-item-d-cycle-adjudications.json").read_text(
            encoding="utf-8"
        )
    )
    batch = next(
        row for row in config["legacy_unknown_manual_batches"]
        if row["batch_ref"] == "LEGACY-UNKNOWN-MANUAL-BATCH-13-LIXUAN"
    )
    assert batch["review_status"] == "ACCEPTED_FOR_SHADOW"
    assert len(batch["records"]) == 5

    analysis = build_formal_linear_q_analysis(
        formal["records"], config, _paired_payload()
    )
    lixuan = next(
        row for row in analysis["records"] if row["ruler_name"] == "李儇"
    )
    summary = next(
        row for row in analysis["ruler_summaries"] if row["ruler_name"] == "李儇"
    )
    cycles = {
        cycle["canonical_parent_cycle_ref"]: cycle
        for cycle in lixuan["D_portfolio_metrics"]["cycle_q_adjudications"]
    }
    expected = {
        "HUANGCHAO-874-884": (
            {"P": 5, "S": 6, "M": 5, "A": 5},
            {"SB": 4, "SN": 0, "BCP": 3, "BCN": 0, "WR": 0},
            -33, {"lower": -33, "upper": -23},
        ),
        "YANGSHILI-DONGCHUAN-884": (
            {"P": 3, "S": 4, "M": 3, "A": 3},
            {"SB": 3, "SN": 0, "BCP": 3, "BCN": 0, "WR": 0},
            -13, {"lower": -13, "upper": -13},
        ),
        "SECOND-FLIGHT-ZHUMEI-885-886": (
            {"P": 2, "S": 6, "M": 5, "A": 5},
            {"SB": 1, "SN": 3, "BCP": 0, "BCN": 3, "WR": 0},
            -59, {"lower": -59, "upper": -59},
        ),
        "QINZONGQUAN-884-LIXUAN-WINDOW": (
            {"P": 4, "S": 7, "M": 5, "A": 5},
            {"SB": 3, "SN": 0, "BCP": 3, "BCN": 2, "WR": 0},
            -39, {"lower": -39, "upper": -39},
        ),
        "WEIBO-MUTINY-888-LIXUAN-WINDOW": (
            {"P": 3, "S": 3, "M": 3, "A": 2},
            {"SB": 0, "SN": 2, "BCP": 0, "BCN": 2, "WR": 0},
            -43, {"lower": -43, "upper": -38},
        ),
    }
    for cycle_ref, (cost, benefit, q_value, q_range) in expected.items():
        cycle = cycles[cycle_ref]
        assert cycle["cost_axes"] == cost
        assert cycle["benefit_axes"] == benefit
        assert cycle["q_contribution"] == q_value
        assert cycle["q_candidate_range"] == q_range
        assert cycle["manual_batch_review_status"] == "ACCEPTED_FOR_SHADOW"

    huangchao = cycles["HUANGCHAO-874-884"]
    assert huangchao["personnel_cost_adjudication"]["equivalent_range"] == [
        50000, 250000,
    ]
    assert (
        huangchao["personnel_cost_adjudication"]["center"],
        huangchao["personnel_cost_adjudication"]["P_scoring"],
    ) == (111803, 5)
    second_flight = cycles["SECOND-FLIGHT-ZHUMEI-885-886"]
    second_flight_input = next(
        row for row in batch["records"]
        if row["investment_cycle_ref"] == "SECOND-FLIGHT-ZHUMEI-885-886"
    )
    assert second_flight_input["cross_axis_overlap_adjudication"]["status"] == (
        "INDEPENDENT"
    )
    assert "民居" in second_flight_input["cross_axis_overlap_adjudication"][
        "basis"
    ]
    qin = cycles["QINZONGQUAN-884-LIXUAN-WINDOW"]
    assert {claim["benefit_window_end"] for claim in qin["benefit_claims"]} == {
        "0888-04-20"
    }
    assert all(
        "CAPTURE" not in fact_ref and "EXECUTION" not in fact_ref
        for claim in qin["benefit_claims"]
        for fact_ref in claim["supporting_fact_refs"]
    )
    weibo = cycles["WEIBO-MUTINY-888-LIXUAN-WINDOW"]
    assert "败魏军万余" in weibo["personnel_cost_adjudication"]["P_observed"]
    weibo_input = next(
        row for row in batch["records"]
        if row["investment_cycle_ref"] == "WEIBO-MUTINY-888-LIXUAN-WINDOW"
    )
    assert weibo_input["mobilization_adjudication"]["M_scoring"] == 3
    assert weibo_input["axis_candidate_ranges"]["A"] == [1, 2]
    assert summary | {} == {
        **summary, "Q": -300, "Q_mean": -21.4286, "T": 14, "K": 14,
        "positive": 0, "zero": 0, "negative": 14, "closure_rate": 1.0,
    }
    audit = analysis["canonical_audit"]
    assert audit["duplicate_investment_cycle_id_count"] == 0
    assert audit["duplicate_strict_benefit_claim_count"] == 0
    assert audit["unreviewed_manual_draft_cycle_count"] == 0


def test_manual_unknown_batch_rejects_personnel_center_grade_mismatch() -> None:
    formal = json.loads(
        (
            ROOT
            / "docs/评分结算/第三项军事与边疆净收益/军事成本收益比/01-皇帝D项正式结算.json"
        ).read_text(encoding="utf-8")
    )
    config = json.loads(
        (ROOT / "config/third-item-d-cycle-adjudications.json").read_text(
            encoding="utf-8"
        )
    )
    batch = next(
        row for row in config["legacy_unknown_manual_batches"]
        if row["batch_ref"] == "LEGACY-UNKNOWN-MANUAL-BATCH-13-LIXUAN"
    )
    huangchao = next(
        row for row in batch["records"]
        if row["investment_cycle_ref"] == "HUANGCHAO-874-884"
    )
    huangchao["P_adjudication"]["equivalent_range"] = [100000, 999999]
    huangchao["P_adjudication"]["center"] = 316227
    with pytest.raises(ValueError, match="center与P_scoring映射不一致"):
        build_formal_linear_q_analysis(
            formal["records"], config, _paired_payload()
        )


@pytest.mark.parametrize(
    ("p_grade", "expected_penalty"),
    list(enumerate((0, 4, 8, 12, 16, 24, 32, 40))),
)
def test_p_tail_penalty_contract_mapping(
    p_grade: int, expected_penalty: int,
) -> None:
    assert p_penalty(p_grade) == expected_penalty
    if p_grade <= 4:
        assert p_penalty(p_grade) == 4 * p_grade


def test_p_tail_shadow_recalculation_preserves_named_anchors_and_identity() -> None:
    formal = json.loads(
        (
            ROOT
            / "docs/评分结算/第三项军事与边疆净收益/军事成本收益比/01-皇帝D项正式结算.json"
        ).read_text(encoding="utf-8")
    )
    config = json.loads(
        (ROOT / "config/third-item-d-cycle-adjudications.json").read_text(
            encoding="utf-8"
        )
    )
    paired = _paired_payload()
    first = build_formal_linear_q_analysis(formal["records"], config, paired)
    second = build_formal_linear_q_analysis(formal["records"], config, paired)
    assert json.dumps(first, ensure_ascii=False, sort_keys=True) == json.dumps(
        second, ensure_ascii=False, sort_keys=True
    )
    cycles = {
        cycle["canonical_parent_cycle_ref"]: cycle
        for ruler in first["records"]
        for cycle in ruler["D_portfolio_metrics"]["cycle_q_adjudications"]
    }
    assert cycles["SUI-GOGURYEO-EXPEDITION-598"]["q_contribution"] == -31
    assert cycles["SUI-GOGURYEO-EXPEDITION-598"]["q_candidate_range"] == {
        "lower": -31, "upper": -31,
    }
    assert cycles["CAMPAIGN-TANG-QIANG-BETRAYAL-635"]["q_contribution"] == -24
    assert cycles["NC-EASTERN-WEI-YUBI-SECOND-SIEGE-546"]["q_contribution"] == -24
    assert cycles["HUANGCHAO-874-884"]["q_contribution"] == -33
    assert cycles["HUANGCHAO-874-884"]["manual_batch_review_status"] == (
        "ACCEPTED_FOR_SHADOW"
    )
    audit = first["canonical_audit"]
    assert audit["duplicate_investment_cycle_id_count"] == 0
    assert audit["duplicate_strict_benefit_claim_count"] == 0
    assert audit["p_tail_closed_cycle_count"] == sum(
        audit["p_tail_closed_cycle_count_by_grade"].values()
    )
    assert audit["p_tail_formal_grade_only_cycle_count"] == 0
    assert audit["p_tail_formalization_prerequisite_status"] == (
        "P_TAIL_FORMALIZATION_COMPLETE"
    )


def test_p_tail_backsource_closes_ranges_and_blocks_cross_window_ticket() -> None:
    formal = json.loads(
        (
            ROOT
            / "docs/评分结算/第三项军事与边疆净收益/军事成本收益比/01-皇帝D项正式结算.json"
        ).read_text(encoding="utf-8")
    )
    config = json.loads(
        (ROOT / "config/third-item-d-cycle-adjudications.json").read_text(
            encoding="utf-8"
        )
    )
    analysis = build_formal_linear_q_analysis(
        formal["records"], config, _paired_payload()
    )
    audit = analysis["p_tail_backsource_audit"]
    assert audit | {} == {
        **audit,
        "record_count": 14,
        "closed_count": 13,
        "window_slice_required_count": 1,
        "all_records_consumed_once": True,
    }
    changes = {
        (row["ruler_name"], row["source_parent_cycle_ref"]): row
        for row in audit["changes"]
    }
    expected = {
        ("元恪", "NC-V146-LEAD-146-07"): (5, 5, -32, -32),
        ("冉闵", "CAMPAIGN-LATERZHAO-RANWEI-COLLAPSE-349-352"): (5, 5, -90, -90),
        ("姚兴", "CAMPAIGN-V117-117-XIA-QIN-415"): (5, 4, -44, -36),
        ("李亨", "CAMPAIGN-TANG-ANSHI-755-763"): (5, None, -30, None),
        ("李隆基", "CAMPAIGN-TANG-NANZHAO-750-754"): (5, 5, -49, -49),
        ("杨广", "SUI-GOGURYEO-611-614"): (5, 5, -54, -54),
        ("武则天", "CAMPAIGN-TANG-KHITAN-696-700"): (5, 5, -32, -32),
        ("赵佶", "XZTJ-SONG-FANGLA-REBELLION-1120-1121"): (7, 7, -79, -79),
        ("赵光义", "XZTJ-SONG-LIJIQIAN-0984-0992"): (5, 4, -51, -43),
        ("赵昀", "XZTJ-MONGOL-SONG-HANZHONG-1231"): (5, 3, -83, -71),
        ("赵顼", "XZTJ-SONG-DAIVIET-WAR-1075-1077"): (5, 4, -56, -48),
        ("朱祁镇", "MTJ-OIRAT-MING-1449-TUMU-ZHUQIZHEN-WINDOW"): (5, 5, -64, -64),
        ("朱由检", "MTJ-LI-ZICHENG-HENAN-1642"): (6, 5, -94, -86),
        ("朱由检", "MTJ-MING-QING-NORTH-CHINA-INVASION-1638-1639"): (5, 4, -84, -76),
    }
    assert {
        key: (row["old_P"], row["new_P"], row["old_Q"], row["new_Q"])
        for key, row in changes.items()
    } == expected

    cycles = {
        (ruler["ruler_name"], cycle.get("source_canonical_parent_cycle_ref")
         or cycle["canonical_parent_cycle_ref"]): cycle
        for ruler in analysis["records"]
        for cycle in ruler["D_portfolio_metrics"]["cycle_q_adjudications"]
    }
    yaoxing = cycles[("姚兴", "CAMPAIGN-V117-117-XIA-QIN-415")]
    hanzhong = cycles[("赵昀", "XZTJ-MONGOL-SONG-HANZHONG-1231")]
    fangla = cycles[("赵佶", "XZTJ-SONG-FANGLA-REBELLION-1120-1121")]
    assert (yaoxing["personnel_cost_adjudication"]["center"], yaoxing["cost_axes"]["P"]) == (20000, 4)
    assert (hanzhong["personnel_cost_adjudication"]["center"], hanzhong["cost_axes"]["P"]) == (2828, 3)
    assert (fangla["personnel_cost_adjudication"]["center"], fangla["cost_axes"]["P"]) == (1414214, 7)
    assert fangla["personnel_cost_adjudication"]["scoring_policy"] == (
        "PREMODERN_SINGLE_GIANT_COUNT_MAGNITUDE_BAND"
    )
    liheng = cycles[("李亨", "CAMPAIGN-TANG-ANSHI-755-763")]
    assert liheng["q_contribution"] is None
    assert set(liheng["cost_axes"].values()) == {"UNKNOWN"}
    assert set(liheng["benefit_axes"].values()) == {"UNKNOWN"}
    assert liheng["personnel_cost_adjudication"]["status"] == (
        "WINDOW_SLICE_CANDIDATE_NOT_CONSUMED"
    )


def test_p_tail_backsource_rejects_center_grade_mismatch() -> None:
    formal = json.loads(
        (
            ROOT
            / "docs/评分结算/第三项军事与边疆净收益/军事成本收益比/01-皇帝D项正式结算.json"
        ).read_text(encoding="utf-8")
    )
    config = json.loads(
        (ROOT / "config/third-item-d-cycle-adjudications.json").read_text(
            encoding="utf-8"
        )
    )
    row = next(
        row for row in config["p_tail_backsource_adjudications"]
        if row["source_parent_cycle_ref"] == "CAMPAIGN-V117-117-XIA-QIN-415"
    )
    row["P_scoring"] = 5
    with pytest.raises(ValueError, match="center与P_scoring映射不一致"):
        build_formal_linear_q_analysis(
            formal["records"], config, _paired_payload()
        )


@pytest.mark.parametrize(
    ("member_refs", "unknown_axes", "chain_peer_count", "expected"),
    [
        (["A", "B"], ["PARENT_COST_AXES_MISSING"], 1, "PARENT_ROLLUP_REQUIRED"),
        (["A"], ["SUBJECT_AXIS_UNRESOLVED"], 1, "SUBJECT_AXIS_REQUIRED"),
        (["A"], ["SB"], 1, "BENEFIT_STATE_REQUIRED"),
        (["A"], ["P"], 1, "FACT_BACKSOURCE_REQUIRED"),
        (["A"], ["SB"], 2, "STRATEGIC_CHAIN_DEDUP_REQUIRED"),
    ],
)
def test_unknown_residual_classification_is_parameterized(
    member_refs: list[str], unknown_axes: list[str],
    chain_peer_count: int, expected: str,
) -> None:
    row = classify_legacy_unknown_cycle(
        {
            "canonical_parent_cycle_ref": "PARENT-X",
            "member_cycle_refs": member_refs,
            "unknown_axes": unknown_axes,
            "source_ref": "docs/source.md#L1",
        },
        ruler_id="RULER-X",
        ruler_name="测试帝",
        chain_peer_count=chain_peer_count,
    )
    assert row["primary_residual_reason"] == expected


def test_missing_literal_system_damage_wording_does_not_short_circuit_s_to_zero() -> None:
    paired = _paired_payload()
    audit = validate_paired_anchor_closures(paired)
    by_ref = {
        cycle["investment_cycle_ref"]: cycle
        for cycle in audit["final_cycles"]
    }
    inferred_refs = {
        "MING-WUKAI-DUYUN-BIJIE-1391-1392",
        "MING-HUGUANG-CHENGUI-1396",
        "MTJ-MING-WUKAI-WUMIAN-1378",
    }
    for ref in inferred_refs:
        cycle = by_ref[ref]
        bridge = cycle["system_damage_adjudication"]
        assert cycle["cost_axes"]["S"] > 0
        assert bridge["status"] == "INFERRED_BOUNDED"
        assert bridge["S_lower"] <= cycle["cost_axes"]["S"] <= bridge["S_upper"]
        assert bridge["functional_symptoms"]
        assert bridge["duration_basis"]
        assert bridge["inference_basis"]


def test_pair_contract_rejects_s0_without_positive_basis() -> None:
    paired = _paired_payload()
    cycle = paired["records"][0]["final_cycles"][0]
    paired["cycle_contract_adjudications"][
        cycle["investment_cycle_ref"]
    ]["system_damage_adjudication"] = {
        "status": "S0_CONFIRMED", "source_refs": ["SRC"],
        "confidence": "HIGH",
    }
    with pytest.raises(ValueError, match="S0缺肯定性S0_basis"):
        validate_paired_anchor_closures(paired)


def test_pair_contract_rejects_new_parent_without_independent_input_boundary() -> None:
    paired = _paired_payload()
    split_row = next(
        row for row in paired["records"]
        if row["disposition"] == "ONE_TO_MANY_RECLOSED"
        and len(row.get("final_cycles") or ()) > 1
    )
    cycle = split_row["final_cycles"][1]
    paired["cycle_contract_adjudications"][
        cycle["investment_cycle_ref"]
    ]["investment_boundary_adjudication"] = {
        "status": "INDEPENDENT_AFTER_CLOSURE",
        "decision_window": "TEST", "mobilization_window": "TEST",
        "force_refs": ["FORCE"], "logistics_refs": ["LOGISTICS"],
        "no_shared_continuous_input_basis": "TEST", "basis": "TEST",
        "source_refs": ["SRC"], "prior_cycle_closed": True,
        "prior_investment_cycle_ref": "PRIOR", "closure_basis": "TEST",
        "independent_force": False, "independent_logistics": False,
    }
    with pytest.raises(ValueError, match="闭合后新投入边界不成立"):
        validate_paired_anchor_closures(paired)


def test_pair_contract_rejects_positive_axis_without_stateful_claim() -> None:
    paired = _paired_payload()
    cycle = next(
        cycle
        for row in paired["records"]
        for cycle in row.get("final_cycles") or ()
        if int(cycle["axes"]["SB"]) > 0
    )
    paired["cycle_contract_adjudications"][
        cycle["investment_cycle_ref"]
    ]["benefit_claims"] = []
    with pytest.raises(ValueError, match="收益claim与父轴不一致"):
        validate_paired_anchor_closures(paired)


def test_gaochang_640_uses_bounded_costs_and_does_not_duplicate_occupation() -> None:
    paired = _paired_payload()
    old_row = next(
        row for row in paired["records"]
        if row["old_cycle_ref"] == "CAMPAIGN-TANG-GAOCHANG-632-640"
    )
    cycle = old_row["final_cycles"][0]
    assert old_row["old_axes"] == {
        "P": 0, "S": 0, "M": 2, "A_scoring": 0,
        "SB": 2, "SN": 0, "BCP": 3, "BCN": 0, "WR": 4,
    }
    assert old_row["old_q"] == 6
    assert cycle["member_cycle_refs"] == ["WAR-LEAD-TANG-GAOCHANG-640"]
    assert cycle["axes"] == {
        "P": 1, "S": 0, "M": 2, "A_scoring": 1,
        "SB": 2, "SN": 0, "BCP": 3, "BCN": 0, "WR": 2,
    }
    assert cycle["q_contribution"] == 14

    audit = validate_paired_anchor_closures(paired)
    normalized = next(
        row for row in audit["final_cycles"]
        if row["investment_cycle_ref"] == cycle["investment_cycle_ref"]
    )
    assert normalized["system_damage_adjudication"]["status"] == "S0_CONFIRMED"
    assert normalized["personnel_cost_adjudication"] | {} == {
        **normalized["personnel_cost_adjudication"],
        "P_lower": 1, "P_upper": 2, "P_scoring": 1,
    }
    assert normalized["asset_components"] | {} == {
        **normalized["asset_components"],
        "A_lower": 1, "A_upper": 2, "A_scoring": 1,
    }
    assert normalized["wr_evidence_adjudication"] | {} == {
        **normalized["wr_evidence_adjudication"],
        "wr_evidence_status": "SIMPLIFIED_INFERRED",
        "asset_base_grade": {"lower": 2, "upper": 3},
        "transfer_mode": "COMPLETE_FORCE_OR_CENTRAL_TRANSFER",
        "realization_retention": "PARTIAL_OR_UNCERTAIN",
        "WR_lower": 1, "WR_upper": 3, "WR_scoring": 2,
    }
    assert normalized["q_interval_adjudication"] | {} == {
        **normalized["q_interval_adjudication"],
        "Q_lower": 7, "Q_upper": 16, "Q_scoring": 14,
    }
    assert normalized["benefit_claims"][0]["benefit_window_end"] < "0641-01-01"
    assert "WAR-LEAD-TANG-GAOCHANG-OCCUPATION" not in normalized["member_cycle_refs"]


def test_pair_contract_rejects_asset_component_or_q_interval_drift() -> None:
    paired = _paired_payload()
    contract = paired["cycle_contract_adjudications"][
        "CAMPAIGN-TANG-GAOCHANG-632-640"
    ]
    contract["asset_components_adjudication"]["A_scoring"] = 0
    with pytest.raises(ValueError, match="A组件裁决不闭合"):
        validate_paired_anchor_closures(paired)

    paired = _paired_payload()
    paired["cycle_contract_adjudications"][
        "CAMPAIGN-TANG-GAOCHANG-632-640"
    ]["q_interval_adjudication"]["Q_upper"] = 13
    with pytest.raises(ValueError, match="Q区间传播不闭合"):
        validate_paired_anchor_closures(paired)


def test_pair_wr_four_state_and_fixed_enums_cover_every_closed_cycle() -> None:
    paired = _paired_payload()
    audit = validate_paired_anchor_closures(paired)
    assert len(audit["final_cycles"]) == 23
    assert all(
        cycle["wr_evidence_adjudication"]["wr_evidence_status"]
        in {"EXPLICIT_REALIZED", "SIMPLIFIED_INFERRED", "CONFIRMED_NONE"}
        for cycle in audit["final_cycles"]
    )
    assert all(
        cycle["benefit_axes"]["WR"] == 0
        and cycle["wr_evidence_adjudication"]["wr_evidence_status"]
        == "CONFIRMED_NONE"
        for cycle in audit["final_cycles"]
        if cycle["wr_evidence_adjudication"]["system_scope"]
        == "INTERNAL_SAME_STATE_SYSTEM"
    )

    paired = _paired_payload()
    paired["cycle_contract_adjudications"][
        "CAMPAIGN-TANG-GAOCHANG-632-640"
    ]["wr_evidence_adjudication"]["transfer_mode"] = "CUSTOM_TRANSFER"
    with pytest.raises(ValueError, match="transfer_mode非法"):
        validate_paired_anchor_closures(paired)

    paired = _paired_payload()
    paired["cycle_contract_adjudications"][
        "CAMPAIGN-TANG-GAOCHANG-632-640"
    ]["wr_evidence_adjudication"]["realization_retention"] = "CUSTOM_RETENTION"
    with pytest.raises(ValueError, match="realization_retention非法"):
        validate_paired_anchor_closures(paired)

    paired = _paired_payload()
    paired["cycle_contract_adjudications"][
        "CAMPAIGN-TANG-GAOCHANG-632-640"
    ]["wr_evidence_adjudication"]["WR_scoring"] = 1
    with pytest.raises(ValueError, match="WR四态裁决不闭合|固定算法"):
        validate_paired_anchor_closures(paired)


def test_pair_wr_rejects_internal_positive_inference_and_resource_overlap() -> None:
    paired = _paired_payload()
    cycle = next(
        cycle
        for row in paired["records"]
        for cycle in row.get("final_cycles") or ()
        if cycle["investment_cycle_ref"] == "MING-SOUTHWEST-YUNNAN-LOCAL-1386"
    )
    cycle["axes"]["WR"] = 2
    cycle["q_contribution"] += 4
    contract = paired["cycle_contract_adjudications"][
        cycle["investment_cycle_ref"]
    ]
    claim = contract["benefit_claims"][0]
    claim["axis_grades"]["WR"] = 2
    claim["resource_object_ref"] = "RESOURCE-INTERNAL-TRANSFER"
    contract["benefit_axis_rollup_basis"]["WR"] = {
        "grade": 2,
        "claim_refs": [claim["benefit_claim_ref"]],
        "basis": "TEST",
        "source_refs": cycle["source_refs"],
    }
    contract["wr_evidence_adjudication"].update({
        "wr_evidence_status": "SIMPLIFIED_INFERRED",
        "asset_base_grade": {"lower": 2, "upper": 3},
        "transfer_mode": "COMPLETE_FORCE_OR_CENTRAL_TRANSFER",
        "realization_retention": "RETAINED_USABLE",
        "WR_lower": 2,
        "WR_upper": 3,
        "WR_scoring": 2,
        "resource_object_refs": ["RESOURCE-INTERNAL-TRANSFER"],
    })
    with pytest.raises(ValueError, match="内部系统禁止简化推定正WR"):
        validate_paired_anchor_closures(paired)

    paired = _paired_payload()
    evidence = paired["cycle_contract_adjudications"][
        "CAMPAIGN-TANG-GAOCHANG-632-640"
    ]["wr_evidence_adjudication"]
    evidence["explicit_resource_object_refs"] = ["RESOURCE-DUPLICATE"]
    evidence["residual_resource_object_ref"] = "RESOURCE-DUPLICATE"
    with pytest.raises(ValueError, match="显式WR与残余推定资源重复"):
        validate_paired_anchor_closures(paired)


def test_pair_batches_follow_fixed_twelve_steps_and_keep_chains_whole() -> None:
    audit = validate_paired_anchor_batches(_paired_payload())
    assert audit["status"] == "CLOSED"
    assert audit["batch_count"] == 5
    assert audit["cycle_count"] == 23
    assert audit["batches"][0]["batch_ref"] == "PAIR-LISHIMIN-01"
    assert audit["batches"][0]["cycle_count"] == 4
    assert all(batch["cycle_count"] <= 6 for batch in audit["batches"])
    assert all(
        [step["step"] for step in batch["steps"]] == list(range(1, 13))
        and all(step["status"] == "CLOSED" for step in batch["steps"])
        for batch in audit["batches"]
    )
    wukai_batches = [
        batch for batch in audit["batches"]
        if any("WUKAI" in ref for ref in batch["cycle_refs"])
    ]
    assert len(wukai_batches) == 1
    assert {
        "MTJ-MING-WUKAI-WUMIAN-1378",
        "MTJ-WUKAI-WUMIAN-1385",
        "MING-WUKAI-DUYUN-BIJIE-1391-1392",
    } <= set(wukai_batches[0]["cycle_refs"])
    assert audit["ruler_pair_totals"] == {
        "李世民": {
            "paired_cycle_count": 4,
            "paired_Q": 2,
            "paired_Q_mean": 0.5,
        },
        "朱元璋": {
            "paired_cycle_count": 19,
            "paired_Q": -64,
            "paired_Q_mean": -3.3684,
        },
    }


def test_pair_batch_reports_first_blocked_step_and_stops_later_batches() -> None:
    paired = _paired_payload()
    first_ref = paired["adjudication_batches"][0]["cycle_refs"][0]
    paired["cycle_contract_adjudications"][first_ref][
        "investment_boundary_adjudication"
    ]["force_refs"] = []
    audit = validate_paired_anchor_batches(paired)
    assert audit["status"] == "BLOCKED_AT_03_INVESTMENT_CYCLE_BOUNDARY"
    assert audit["first_blocked_step"] == 3
    assert audit["batches"][0]["status"] == audit["status"]
    assert all(
        batch["status"] == "NOT_STARTED" for batch in audit["batches"][1:]
    )

    paired = _paired_payload()
    wukai_ref = "MING-WUKAI-DUYUN-BIJIE-1391-1392"
    paired["adjudication_batches"][2]["cycle_refs"].remove(wukai_ref)
    paired["adjudication_batches"][3]["cycle_refs"].append(wukai_ref)
    audit = validate_paired_anchor_batches(paired)
    assert audit["status"] == "BLOCKED_AT_04_STRATEGIC_RESULT_CHAIN"


def test_paired_anchor_fixed_reasons_match_axes_claims_and_rollups() -> None:
    paired = _paired_payload()
    raw_cycles = {
        cycle["investment_cycle_ref"]: cycle
        for row in paired["records"]
        for cycle in row.get("final_cycles") or ()
    }
    assert len(raw_cycles) == 23
    assert all(cycle["change_reason"].strip() for cycle in raw_cycles.values())

    expected_reason_fragments = {
        "CAMPAIGN-TANG-QIANG-BETRAYAL-635": ("SN2",),
        "CAMPAIGN-TANG-TIBET-638": ("S1", "SB1", "BCP2"),
        "CAMPAIGN-TANG-GAOCHANG-632-640": ("WR[1,3]", "A均按1—2"),
        "CAMPAIGN-TANG-KUCHA-648": ("SB3", "BCP2", "WR2"),
        "MING-SOUTHWEST-YUNNAN-LOCAL-1386": ("BCP1", "M2", "S2"),
        "MING-SOUTHWEST-DONGCHUAN-1388": ("S2", "BCP2"),
        "MING-HUGUANG-CHENGUI-1396": ("S取[1,2]上沿2",),
        "MING-JIANCHANG-YILUTEMUER-1392": ("A1",),
        "MING-LUCHUAN-DAO-GANMENG-1397-1398": ("BCP2", "A按实际耗尽和远征定2"),
        "MING-NORTHERN-YUAN-NAIRBUQA-1390": ("WR2",),
        "MING-SOUTHWEST-AZI-1388-1395": ("S2",),
        "MTJ-MING-GUANGDONG-PACIFICATION-1380-1382": (
            "S3", "M3", "SB3", "BCP1",
        ),
        "MTJ-MING-WUKAI-WUMIAN-1378": ("S[2,3]", "BCP1"),
        "MTJ-MING-YUNNAN-REBELLIONS-1382": ("P2/S3",),
        "MTJ-YUNNAN-GUANGXI-WUFU-1383": ("SB3", "BCP3", "M3", "A2"),
    }
    for ref, fragments in expected_reason_fragments.items():
        reason = raw_cycles[ref]["change_reason"]
        assert all(fragment in reason for fragment in fragments), (ref, reason)

    assert "解围只形成SB2" not in raw_cycles[
        "CAMPAIGN-TANG-TIBET-638"
    ]["change_reason"]
    assert "BCP0" not in raw_cycles[
        "MING-SOUTHWEST-YUNNAN-LOCAL-1386"
    ]["change_reason"]
    assert "SB2/BCP2" not in raw_cycles[
        "MTJ-MING-GUANGDONG-PACIFICATION-1380-1382"
    ]["change_reason"]

    audit = validate_paired_anchor_closures(paired)
    normalized = {
        cycle["investment_cycle_ref"]: cycle
        for cycle in audit["final_cycles"]
    }
    assert normalized["CAMPAIGN-TANG-TIBET-638"]["benefit_axes"] | {} == {
        **normalized["CAMPAIGN-TANG-TIBET-638"]["benefit_axes"],
        "SB": 1, "BCP": 2,
    }
    assert normalized["MING-SOUTHWEST-YUNNAN-LOCAL-1386"][
        "benefit_axes"
    ] | {} == {
        **normalized["MING-SOUTHWEST-YUNNAN-LOCAL-1386"]["benefit_axes"],
        "SB": 2, "BCP": 1,
    }

    guangdong = normalized["MTJ-MING-GUANGDONG-PACIFICATION-1380-1382"]
    assert guangdong["cost_axes"] == {"P": 1, "S": 3, "M": 3, "A": 1}
    assert guangdong["benefit_axes"] == {
        "SB": 3, "SN": 0, "BCP": 1, "BCN": 0, "WR": 0,
    }
    assert guangdong["q_contribution"] == -5
    claim = guangdong["benefit_claims"][0]
    assert claim["axis_grades"] == {"SB": 3, "BCP": 1}
    assert "长期失守" in claim["to_state"]
    assert "失去控制" not in claim["peak_state"]
    assert guangdong["benefit_axis_rollup_basis"]["BCP"]["grade"] == 1

    wufu = raw_cycles["MTJ-YUNNAN-GUANGXI-WUFU-1383"]
    assert wufu["q_contribution"] == 12
    assert "不是普通干净平乱" in wufu["change_reason"]
    assert all(
        fragment in wufu["change_reason"]
        for fragment in ("开箐道", "筑安庄与新城", "盘江转运")
    )
