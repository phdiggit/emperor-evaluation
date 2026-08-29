from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILE_ROOT = ROOT / "docs" / "评分结算" / "皇帝人物画像"
CONTRACT = ROOT / "docs" / "项目总纲" / "皇帝人物画像评估体系合同.md"
POOL = ROOT / "config" / "common" / "canonical-ruler-pool.json"


def _load(path: Path) -> dict:
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    return json.loads(raw.decode("utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _included_ids() -> set[str]:
    pool = _load(POOL)
    return {record["ruler_id"] for record in pool["records"] if record["pool_status"] == "INCLUDED"}


def test_profile_manifest_registers_all_eight_formal_axes() -> None:
    manifest = _load(PROFILE_ROOT / "00-已结算轴正式入口.json")
    assert manifest["canonical_status"] == "FORMAL_CURRENT"
    assert manifest["contract_version"] == "FORMAL-V2.0"
    assert manifest["settled_axis_count"] == 8
    assert manifest["unsettled_axis_count"] == 0
    assert manifest["profile_total_enabled"] is False
    assert manifest["profile_ranking_enabled"] is False
    assert manifest["composite_ranking_write"] is False
    assert [axis["axis_code"] for axis in manifest["axes"]] == ["M1", "M2", "M3", "M4", "C1", "C2", "C3", "C5"]
    assert manifest["contract_sha256"] == _sha256(CONTRACT)
    assert manifest["canonical_pool_sha256"] == _sha256(POOL)
    assert next(axis for axis in manifest["axes"] if axis["axis_code"] == "M3")["status"] == "FORMAL_CURRENT"
    for axis in manifest["axes"]:
        assert axis["record_count"] == 184
        assert axis["json_sha256"] == _sha256(PROFILE_ROOT / axis["json"])
    m1_axis = next(axis for axis in manifest["axes"] if axis["axis_code"] == "M1")
    assert "M1/08-M1武将锚别名与缺锚强度复核.json" in m1_axis["audit_jsons"]
    assert "M1/09-M1武将成果难度组合倒挂复核.json" in m1_axis["audit_jsons"]
    assert "M1/10-M1无档案战役与人才公共补录复核.json" in m1_axis["audit_jsons"]
    assert "M1/11-M1全池重新裁决复核.json" in m1_axis["audit_jsons"]


def test_profile_axis_records_cover_the_formal_pool_and_contract_fields() -> None:
    expected_ids = _included_ids()
    required = {
        "task_code",
        "ruler_id",
        "ruler_name",
        "axis_grade",
        "position",
        "radar_value",
        "axis_evidence_level",
        "output_mode",
        "confidence",
        "adjudication_ref",
        "representative_parent_contexts",
        "typical_pattern",
        "counterpattern",
        "grade_basis",
        "position_basis",
        "axis_relevance_check",
        "limitations",
        "formal_status",
    }
    for name in (
        "M1/01-M1军事判断与统帅能力正式结算.json",
        "C5/02-C5权力运用风格与克制正式结算.json",
        "M2/12-M2外交博弈与对外联盟能力正式结算.json",
        "C1/15-C1战略判断与风险控制正式结算.json",
        "C2/19-C2信息处理学习与纠错正式结算.json",
        "C3/24-C3人才识别配置与授权正式结算.json",
        "M4/34-M4政治联盟与内部联盟管理正式结算.json",
    ):
        settlement = _load(PROFILE_ROOT / name)
        records = settlement["records"]
        assert settlement["canonical_status"] == "FORMAL_CURRENT"
        assert settlement["contract_version"] == "FORMAL-V1.0"
        assert settlement["formal_profile_write"] is True
        assert settlement["formal_rank_write"] is False
        assert settlement["profile_total_enabled"] is False
        assert settlement["database_write"] is False
        assert settlement["record_order_policy"] == "RADAR_VALUE_DESC_THEN_RULER_ID_ASC"
        assert settlement["record_count"] == len(records) == 184
        assert {record["ruler_id"] for record in records} == expected_ids
        assert len({record["task_code"] for record in records}) == 184
        assert all(required <= record.keys() for record in records)
        assert all(record["formal_status"] == "FORMAL_CURRENT" for record in records)
        assert all(record["score_status"] in {"FINAL", "EVIDENCE_LIMITED"} for record in records)
        assert all(record["axis_evidence_level"] in {"E1", "E2", "E3"} for record in records)
        assert all(record["axis_grade"] in {f"G{i}" for i in range(6)} for record in records)
        assert all(record["position"] in {"LOW", "MID", "HIGH"} for record in records)
        assert all(record["radar_value"] == record["score_100"] for record in records)
        assert records == sorted(records, key=lambda record: (-record["radar_value"], record["ruler_id"]))


def test_c5_unit_dispositions_are_complete_and_do_not_score_background() -> None:
    settlement = _load(PROFILE_ROOT / "C5/02-C5权力运用风格与克制正式结算.json")
    audit = _load(PROFILE_ROOT / "C5/04-C5主要入口单元处置审计.json")
    units = audit["units"]
    assert audit["canonical_status"] == "FORMAL_CURRENT_AUDIT"
    assert audit["unit_count"] == len(units) == 1680
    assert len({unit["unit_id"] for unit in units}) == 1680
    assert set(audit["status_counts"]) == {
        "SCORING_PARENT",
        "BACKGROUND_VALIDATION",
        "AXIS_OUT_WITH_REASON",
    }
    assert sum(audit["status_counts"].values()) == 1680
    assert all(unit["status"] != "UNRESOLVED_GAP" for unit in units)
    assert all(
        (unit["status"] == "SCORING_PARENT") == bool(unit["scoring_parent_id"])
        for unit in units
    )
    settlement_parent_ids = {
        parent["parent_id"] for record in settlement["records"] for parent in record["parents"]
    }
    assert {
        unit["scoring_parent_id"] for unit in units if unit["status"] == "SCORING_PARENT"
    } <= settlement_parent_ids


def test_c5_high_grade_density_review_is_closed() -> None:
    settlement = _load(PROFILE_ROOT / "C5/02-C5权力运用风格与克制正式结算.json")
    audit = _load(PROFILE_ROOT / "C5/05-C5高档材料密度复核.json")
    high_ids = {r["ruler_id"] for r in settlement["records"] if r["axis_grade"] in {"G4", "G5"}}
    latent_high_ids = {r["ruler_id"] for r in settlement["records"] if r.get("latent_high_grade_hypothesis")}
    reviews = audit["reviews"]
    assert audit["canonical_status"] == "FORMAL_CURRENT_AUDIT"
    assert {review["ruler_id"] for review in reviews} == high_ids | latent_high_ids
    assert all(
        review["result"]
        in {"COVERAGE_CLOSED", "COUNTEREVIDENCE_FOUND", "MATERIAL_DENSITY_LIMITED"}
        for review in reviews
    )


def test_formal_contract_declares_eight_settled_axes_without_profile_total() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    assert "DRAFT-V0.5" not in text
    assert "FORMAL-V2.0" in text
    assert "FORMAL-V2.0 / EIGHT-AXES-FORMALLY-SETTLED" in text
    assert "C1、C2、C3、C5、M1、M2、M3与M4均满足上述轴级门禁" in text
    assert "仍不得生成画像总分、轴内排名或写入五项综合榜" in text
    assert "人物画像代码C4自本版撤销" in text
    assert "| C4 | 组织推动与执行韧性 |" not in text
    assert "跨轴落实深度与受阻重组证据门" in text
    assert "| M3 | 民生财政建设 |" in text
    assert "| M4 | 内部政治联盟与集团整合 |" in text


def test_m2_has_unique_radar_points_and_separates_background() -> None:
    settlement = _load(PROFILE_ROOT / "M2/12-M2外交博弈与对外联盟能力正式结算.json")
    records = settlement["records"]
    scoring_parents = [
        parent
        for record in records
        for parent in record["parents"]
        if parent["consumption_status"] == "SCORING_PARENT"
    ]
    assert settlement["summary"]["unresolved_count"] == 0
    assert all(record["axis_grade"] and record["position"] for record in records)
    assert all(record["radar_value"] is not None for record in records)
    assert all(record["parents"] for record in records)
    for record in records:
        scoring = {
            parent["parent_id"]
            for parent in record["parents"]
            if parent["consumption_status"] == "SCORING_PARENT"
        }
        assert set(record["axis_relevance_check"]["scoring_parent_refs"]) == scoring
        if record["axis_evidence_level"] == "E3":
            assert scoring
        if record["axis_evidence_level"] == "E2" and not scoring:
            assert record["score_status"] == "EVIDENCE_LIMITED"
        for parent in record["parents"]:
            assert parent["source_refs"]
            if parent["direction"] == "LIMITATION":
                assert parent["consumption_status"] == "BACKGROUND_VALIDATION"
            if parent.get("adversity_origin") == "SELF_CAUSED":
                assert parent["direction"] != "POSITIVE"
    assert any(
        parent["direction"] == "NEGATIVE" and parent["intensity"] == "MI1"
        for parent in scoring_parents
    )
    assert not any(
        parent["intensity"] in {"MI3", "MI4"}
        and all(ref.startswith("docs/评分结算/") for ref in parent["source_refs"])
        for parent in scoring_parents
    )
    by_name = {record["ruler_name"]: record for record in records}
    assert settlement["summary"]["grade_distribution"] == {
        "G0": 0, "G1": 15, "G2": 28, "G3": 114, "G4": 26, "G5": 1
    }
    assert (by_name["李世民"]["axis_grade"], by_name["李世民"]["position"]) == ("G5", "LOW")
    assert (by_name["王莽"]["axis_grade"], by_name["王莽"]["position"]) == ("G1", "LOW")
    assert (by_name["钱镠"]["axis_grade"], by_name["钱镠"]["position"], by_name["钱镠"]["radar_value"]) == ("G4", "LOW", 77)
    assert (by_name["刘启"]["axis_grade"], by_name["刘启"]["position"], by_name["刘启"]["radar_value"]) == ("G3", "LOW", 58)
    assert next(parent for parent in by_name["刘启"]["parents"] if parent["parent_id"] == "M2-P023-XIONGNU-HEQIN")["consumption_status"] == "BACKGROUND_VALIDATION"
    xuanye = by_name["玄烨"]
    assert (xuanye["axis_grade"], xuanye["position"], xuanye["radar_value"]) == ("G4", "HIGH", 87)
    dolon = next(parent for parent in xuanye["parents"] if parent["parent_id"] == "M2-P075-KHALKHA")
    assert (dolon["direction"], dolon["intensity"], dolon["adversity_origin"]) == (
        "POSITIVE", "MI4", "EXTERNAL"
    )
    liuheng = by_name["刘恒"]
    assert (liuheng["axis_grade"], liuheng["position"], liuheng["radar_value"]) == ("G3", "MID", 65)
    assert "正负各一条" not in liuheng["grade_basis"]
    liuzhi = by_name["刘志"]
    assert (liuzhi["axis_grade"], liuzhi["position"], liuzhi["radar_value"]) == ("G3", "LOW", 58)
    assert (liuzhi["axis_evidence_level"], liuzhi["score_status"]) == ("E2", "EVIDENCE_LIMITED")
    assert {parent["intensity"] for parent in liuzhi["parents"]} == {"MI2"}
    zhudi = by_name["朱棣"]
    assert (zhudi["axis_grade"], zhudi["position"], zhudi["radar_value"]) == ("G4", "LOW", 77)
    assert {parent["parent_id"] for parent in zhudi["parents"]} == {
        "M2-P048-MALACCA-SAFETY-ORDER",
        "M2-P048-CROSS-REGION-ENVOY-NETWORK",
        "M2-P048-NORTHERN-POLITY-BALANCING",
        "M2-P048-ANNAM-ANNEXATION",
    }
    assert all(
        parent["intensity"] != "MI3"
        for parent in scoring_parents
        if parent["source_support"] == "BOUNDED_LOCAL_SUPPORT"
    )
    assert all(
        parent["intensity"] == "MI1"
        for parent in scoring_parents
        if parent["source_support"] == "FORMAL_AGGREGATE_RESULT_WITHOUT_DIRECT_PROCESS"
    )


def test_m2_c5_capability_event_review_separates_mi_from_grade() -> None:
    audit = _load(PROFILE_ROOT / "交叉轴复核/14-M2与C5能力事件分布复核.json")
    assert audit["canonical_status"] == "FORMAL_CURRENT_AUDIT"
    assert audit["review_scope"] == {"M2": 184, "C5": 184}
    assert audit["policy"]["mi_is_material_strength_not_grade"] is True
    assert audit["policy"]["negative_evidence_automatically_caps_g5"] is False
    assert audit["policy"]["positive_mi4_automatically_grants_g5"] is False
    assert len(audit["grade_changes"]) == 3
    high_review = audit["m2_high_grade_recalibration"]
    assert high_review["scope_count"] == 27
    assert high_review["density_result_counts"] == {
        "COUNTEREVIDENCE_FOUND": 14,
        "COVERAGE_CLOSED": 13,
    }
    assert len(high_review["records"]) == 27
    high_changes = {item["ruler_name"]: item for item in high_review["position_changes"]}
    assert high_changes["玄烨"]["after"] == "G4-HIGH / 87"
    assert high_changes["钱镠"]["after"] == "G4-LOW / 77"
    assert high_changes["朱棣"]["after"] == "G4-LOW / 77"
    assert audit["m2_zhudi_recalibration"]["reputation_or_result_scale_used_as_score"] is False

    marriage_review = audit["m2_marriage_policy_review"]
    assert marriage_review["record_count"] == 184
    assert marriage_review["candidate_ruler_count"] == 33
    assert marriage_review["candidate_parent_count"] == 39
    assert marriage_review["disposition_counts"] == {
        "SCORING_EFFECT_VERIFIED": 16,
        "BACKGROUND_COMPONENT_PARENT_RETAINS_OTHER_MECHANISM": 13,
        "BACKGROUND_NO_VERIFIED_EFFECT": 9,
        "LEXICAL_FALSE_POSITIVE_NOT_MARRIAGE": 1,
    }
    marriage_by_parent = {item["parent_id"]: item for item in marriage_review["records"]}
    assert marriage_by_parent["M2-P023-XIONGNU-HEQIN"]["after"] == {
        "direction": "LIMITATION",
        "intensity": "MI1",
        "consumption_status": "BACKGROUND_VALIDATION",
    }
    assert marriage_by_parent["M2-P153-TIBET-WARTALK-MARRIAGE"]["disposition"] == "SCORING_EFFECT_VERIFIED"
    assert marriage_by_parent["M2-REVIEW-刘彧-02"]["disposition"] == "LEXICAL_FALSE_POSITIVE_NOT_MARRIAGE"

    intensity_review = audit["m2_intensity_grade_recalibration"]
    assert intensity_review["record_count"] == 184
    assert intensity_review["high_intensity_parent_count_before"] == 170
    assert intensity_review["hard_hit_ruler_count"] == 26
    assert intensity_review["weak_source_scoring_parent_count"] == 45
    assert intensity_review["intensity_change_count"] == 31
    assert intensity_review["intensity_change_counts"] == {"MI3_TO_MI2": 9, "MI2_TO_MI1": 22}
    assert intensity_review["grade_or_position_change_count"] == 12
    assert intensity_review["arithmetic_basis_rewrite_count"] == 5
    assert intensity_review["document_leakage_cleanup_count"] == 3


def test_m1_structural_review_narrows_g5_and_exposes_military_anchor() -> None:
    settlement = _load(PROFILE_ROOT / "M1/01-M1军事判断与统帅能力正式结算.json")
    audit = _load(PROFILE_ROOT / "M1/06-M1高档结构复核.json")
    by_name = {record["ruler_name"]: record for record in settlement["records"]}
    assert settlement["summary"]["grade_distribution"] == {
        "G0": 5, "G1": 25, "G2": 48, "G3": 71, "G4": 30, "G5": 5
    }
    assert audit["reviewed_count"] == 64
    assert audit["changed_count"] == 52
    assert all("military_talent_anchor" in record for record in settlement["records"])
    assert (by_name["完颜阿骨打"]["axis_grade"], by_name["完颜阿骨打"]["position"]) == ("G4", "HIGH")
    assert (by_name["曹操"]["axis_grade"], by_name["曹操"]["position"]) == ("G4", "HIGH")
    assert (by_name["柴荣"]["axis_grade"], by_name["柴荣"]["position"]) == ("G4", "MID")
    assert by_name["曹操"]["military_talent_anchor"]["stability_status"] == "stability_limited_repeated_major_failures"
    assert by_name["柴荣"]["military_talent_anchor"]["status"] == "FORMAL_PROFILE_CONNECTED"
    assert by_name["柴荣"]["military_talent_anchor"]["military_grade"] == "elite"
    assert (by_name["朱元璋"]["axis_grade"], by_name["朱元璋"]["position"]) == ("G5", "LOW")
    assert by_name["朱元璋"]["military_talent_anchor"]["military_grade"] == "historic"


def test_m1_talent_alias_and_missing_anchor_review_uses_independent_lifecycles() -> None:
    settlement = _load(PROFILE_ROOT / "M1/01-M1军事判断与统帅能力正式结算.json")
    audit = _load(PROFILE_ROOT / "M1/08-M1武将锚别名与缺锚强度复核.json")
    by_name = {record["ruler_name"]: record for record in settlement["records"]}
    review_by_name = {record["ruler_name"]: record for record in audit["reviews"]}

    assert audit["record_count"] == 184
    assert audit["profile_connected_count"] == 120
    assert audit["no_formal_profile_count"] == 64
    assert audit["ambiguous_resolution_count"] == 0
    assert audit["alias_match_count"] == 2
    assert audit["changed_count"] == 21

    zhu = by_name["朱温"]
    assert (zhu["axis_grade"], zhu["position"], zhu["radar_value"]) == ("G4", "HIGH", 87)
    assert zhu["military_talent_anchor"]["profile_person"] == "朱全忠"
    assert zhu["military_talent_anchor"]["match_method"] == "TALENT_NAME_ALIAS"
    assert zhu["military_talent_anchor"]["military_grade"] == "top"

    tuoba = by_name["拓跋宏"]
    assert (tuoba["axis_grade"], tuoba["position"], tuoba["radar_value"]) == ("G2", "HIGH", 51)
    assert tuoba["military_talent_anchor"]["profile_person"] == "元宏"
    assert tuoba["military_talent_anchor"]["match_method"] == "TALENT_NAME_ALIAS"
    assert tuoba["military_talent_anchor"]["stability_status"] == "stability_limited_major_failure"

    chai = review_by_name["柴荣"]
    assert chai["battle_registry_observation"]["independent_campaign_group_count"] == 3
    assert chai["first_item_c_personal_result_observation"]["personal_frontline_result_count"] == 2
    assert chai["first_item_c_personal_result_observation"]["difficulty_distribution"] == {"D2": 1, "D1": 1}
    assert chai["battle_registry_observation"]["win_rate_status"] == "NOT_LITERAL_WIN_RATE_PHASE_FRAGMENTS_AND_OUTCOMES_NOT_UNIFORM"


def test_m1_talent_result_difficulty_combinations_are_projected_and_inversions_closed() -> None:
    settlement = _load(PROFILE_ROOT / "M1/01-M1军事判断与统帅能力正式结算.json")
    audit = _load(PROFILE_ROOT / "M1/09-M1武将成果难度组合倒挂复核.json")
    by_name = {record["ruler_name"]: record for record in settlement["records"]}
    audit_by_name = {record["ruler_name"]: record for record in audit["records"]}

    assert audit["record_count"] == 120
    assert audit["mechanical_candidate_count"] == 19
    assert audit["changed_count"] == 8
    assert audit["mechanical_candidate_changed_count"] == 6
    assert audit["g4_position_recalibration_count"] == 1
    assert audit["retained_candidate_count"] == 13
    assert settlement["summary"]["military_talent_registry_projection_count"] == 120

    liubang = by_name["刘邦"]
    assert (liubang["axis_grade"], liubang["position"], liubang["radar_value"]) == ("G4", "MID", 82)
    assert "S-/D4" in liubang["military_talent_registry_projection"]["result_difficulty_combinations_display"]
    assert "恢复成皋敖仓并守住楚汉核心主战线" in liubang["military_talent_registry_projection"]["campaign_group_roles_display"]

    yuwenyong = by_name["宇文邕"]
    assert (yuwenyong["axis_grade"], yuwenyong["position"], yuwenyong["radar_value"]) == ("G4", "LOW", 77)
    assert audit_by_name["宇文邕"]["positive_combo_distribution"] == {"S/D3": 1}
    assert audit_by_name["宇文邕"]["adverse_combo_distribution"] == {"A/D2": 1}

    for name, expected in {
        "王建": ("G4", "MID"),
        "努尔哈赤": ("G4", "MID"),
        "多尔衮": ("G4", "LOW"),
        "慕容德": ("G4", "LOW"),
        "钱镠": ("G4", "LOW"),
    }.items():
        assert (by_name[name]["axis_grade"], by_name[name]["position"]) == expected

    chai_projection = by_name["柴荣"]["military_talent_registry_projection"]
    assert chai_projection["status"] == "FORMAL_PROFILE_MARKDOWN_CELLS_COPIED"
    assert len(chai_projection["paired_result_difficulty_campaign_role_items"]) == 3
    assert "高平" in chai_projection["paired_result_difficulty_campaign_roles_display"]
    assert "淮南" in chai_projection["paired_result_difficulty_campaign_roles_display"]
    assert "关南" in chai_projection["paired_result_difficulty_campaign_roles_display"]


def test_m1_talent_projection_cells_exactly_match_the_public_markdown() -> None:
    settlement = _load(PROFILE_ROOT / "M1/01-M1军事判断与统帅能力正式结算.json")
    talent_root = ROOT / "docs" / "公共成果" / "军事" / "02-武将人才等级"
    profiles = {}
    for path in sorted(talent_root.glob("bucket-*.json")):
        for profile in _load(path)["profiles"]:
            profiles[profile["profile_ref"]] = profile

    rows = {}
    talent_md = (ROOT / "docs" / "公共成果" / "军事" / "02-武将人才等级.md").read_text(encoding="utf-8")
    for line in talent_md.splitlines():
        if not line.startswith("| "):
            continue
        cells = [cell.strip() for cell in line[1:-1].split("|")]
        if len(cells) == 7 and cells[0] not in {"朝代", "---"}:
            rows[(cells[0], cells[1])] = (cells[5], cells[6])

    connected_count = 0
    for record in settlement["records"]:
        projection = record["military_talent_registry_projection"]
        profile_ref = record["military_talent_anchor"].get("profile_ref")
        if not profile_ref:
            assert projection["status"] == "NO_FORMAL_PROFILE"
            continue
        profile = profiles[profile_ref]
        expected = rows[(profile["dynasty"], profile["person"])]
        assert projection["result_difficulty_combinations_display"] == expected[0]
        assert projection["campaign_group_roles_display"] == expected[1]
        assert len(projection["result_difficulty_combination_items"]) == len(
            projection["campaign_group_role_items"]
        )
        expected_pair_count = 0 if expected == ("—", "—") else len(
            projection["result_difficulty_combination_items"]
        )
        assert len(projection["paired_result_difficulty_campaign_role_items"]) == expected_pair_count
        expected_paired_display = (
            "—" if expected == ("—", "—")
            else "<br>".join(projection["paired_result_difficulty_campaign_role_items"])
        )
        assert projection["paired_result_difficulty_campaign_roles_display"] == expected_paired_display
        connected_count += 1
    assert connected_count == 120

    settlement_md = (PROFILE_ROOT / "M1/01-M1军事判断与统帅能力正式结算.md").read_text(encoding="utf-8")
    assert "- 武将登记逐项（成果等级/难度｜战役群名称/武将角色）：\n  " in settlement_md
    assert "- 战役成果等级/难度组合：" not in settlement_md
    assert "- 战役群名称/武将角色：" not in settlement_md


def test_m1_missing_profiles_include_founding_and_post_unification_command_windows() -> None:
    settlement = _load(PROFILE_ROOT / "M1/01-M1军事判断与统帅能力正式结算.json")
    audit = _load(PROFILE_ROOT / "M1/10-M1无档案战役与人才公共补录复核.json")
    by_name = {record["ruler_name"]: record for record in settlement["records"]}

    assert audit["screened_no_profile_count"] == 73
    assert audit["canonical_status"] == "FORMAL_CURRENT_AUDIT"
    assert audit["new_profile_count"] == 9
    assert audit["new_public_record_count"] == 6
    assert audit["person_command_result_count"] == 22
    assert audit["window_policy"] == "FOUNDING_UNIFICATION_AND_POST_UNIFICATION_PERSONAL_EXPEDITIONS_INCLUDED"
    assert all(
        decision["person_command_result_refs"]
        and decision["campaign_refs"]
        and decision["capability_episode_refs"]
        and decision["source_refs"]
        for decision in audit["profile_decisions"]
    )

    chai = by_name["柴荣"]
    assert chai["military_talent_anchor"]["military_grade"] == "elite"
    assert "HUAINAN_PHASE_CARDS_MERGED_AS_ONE_CAPABILITY_EPISODE" in chai["limitations"]

    guo = by_name["郭威"]["military_talent_registry_projection"]["paired_result_difficulty_campaign_roles_display"]
    assert "河中长围" in guo
    assert "亲征兖州" in guo

    dashi = by_name["耶律大石"]
    assert dashi["military_talent_anchor"]["military_grade"] == "elite"
    assert dashi["military_talent_anchor"]["stability_status"] == "stability_limited_major_failure"
    dashi_rows = dashi["military_talent_registry_projection"]["paired_result_difficulty_campaign_roles_display"]
    assert "塔什干破联军并建立西辽" in dashi_rows
    assert "卡特万—花剌子模中亚霸权链" in dashi_rows
    assert "七万骑东征三年万里无所得" in dashi_rows
    assert "CENTRAL_ASIA_HEGEMONY_CONSUMES_OPERATIONAL_RESULT_WITHOUT_INHERITED_FRONTLINE_DIFFICULTY" in dashi["limitations"]

    xiao = by_name["萧绰"]["military_talent_registry_projection"]["paired_result_difficulty_campaign_roles_display"]
    assert "统筹+ `S-/—`" in xiao
    wanyan = by_name["完颜亮"]
    assert wanyan["military_talent_anchor"]["military_grade"] == "ordinary"
    assert "前线− `S/D3`" in wanyan["military_talent_registry_projection"]["paired_result_difficulty_campaign_roles_display"]


def test_m1_full_pool_readjudication_closes_all_records_and_failure_rule() -> None:
    settlement = _load(PROFILE_ROOT / "M1/01-M1军事判断与统帅能力正式结算.json")
    audit = _load(PROFILE_ROOT / "M1/11-M1全池重新裁决复核.json")
    by_name = {record["ruler_name"]: record for record in settlement["records"]}

    assert audit["canonical_status"] == "FORMAL_CURRENT_AUDIT"
    assert audit["record_count"] == len(audit["rows"]) == 184
    assert audit["changed_count"] == 37
    assert audit["retained_count"] == 147
    assert {row["ruler_name"] for row in audit["rows"]} == set(by_name)
    assert audit["review_policy"]["target_nonachievement_automatically_treated_as_defeat"] is False
    assert all(record["full_pool_readjudication"]["status"] == "FULL_LIFETIME_REVIEWED" for record in settlement["records"])
    assert all("V0.5未重开" not in parent["intensity_and_role_basis"] for record in settlement["records"] for parent in record["representative_parent_contexts"])

    assert (by_name["王建"]["axis_grade"], by_name["王建"]["position"]) == ("G4", "MID")
    assert (by_name["沮渠蒙逊"]["axis_grade"], by_name["沮渠蒙逊"]["position"]) == ("G4", "LOW")
    nurhaci = by_name["努尔哈赤"]
    assert (nurhaci["axis_grade"], nurhaci["position"]) == ("G4", "MID")
    assert nurhaci["military_talent_anchor"]["military_grade"] == "top"
    assert "不能仅凭未克" in nurhaci["counterpattern"]
    assert (by_name["胤禛"]["axis_grade"], by_name["胤禛"]["position"]) == ("G2", "MID")
    assert "资源优势下失常门" in by_name["胤禛"]["grade_basis"]
    assert (by_name["弘历"]["axis_grade"], by_name["弘历"]["position"]) == ("G2", "HIGH")
    assert (by_name["忽必烈"]["axis_grade"], by_name["忽必烈"]["position"]) == ("G4", "MID")
    assert (by_name["铁木真"]["axis_grade"], by_name["铁木真"]["position"]) == ("G5", "HIGH")
    assert (by_name["刘彻"]["axis_grade"], by_name["刘彻"]["position"]) == ("G3", "MID")
    assert (by_name["刘恒"]["axis_grade"], by_name["刘恒"]["position"]) == ("G3", "LOW")
    assert by_name["刘恒"]["score_100"] < by_name["刘彻"]["score_100"]
    assert "零场、零独立战役群" in by_name["刘恒"]["counterpattern"]
    assert audit["g3_strategy_third_item_review"] == {
        "population_count": 49,
        "mechanical_trigger_count": 25,
        "semantic_weak_hit_count": 21,
        "weak_hit_revised_count": 19,
        "weak_hit_retained_at_supported_lower_bound_count": 2,
        "screen_hit_retained_after_context_review_count": 4,
        "unresolved_count": 0,
    }
    assert (by_name["马殷"]["axis_grade"], by_name["马殷"]["position"]) == ("G3", "LOW")
    assert (by_name["李渊"]["axis_grade"], by_name["李渊"]["position"]) == ("G3", "MID")
    for name in ("邓绥", "李谅祚", "李乾顺", "陈顼", "完颜守绪"):
        assert (by_name[name]["axis_grade"], by_name[name]["position"]) == ("G2", "HIGH")
    assert audit["third_item_strategy_crosscheck_count"] == 184
    assert all(record["third_item_strategy_crosscheck"]["status"] == "FORMAL_THIRD_ITEM_CROSSCHECKED" for record in settlement["records"])
    wuzetian = by_name["武则天"]
    assert (wuzetian["axis_grade"], wuzetian["position"]) == ("G2", "HIGH")
    assert wuzetian["third_item_strategy_crosscheck"]["mode"] == "STRATEGIC_AUTHORIZATION_DOMINANT"
    assert "D_linear_Q_cost_return_diagnostic" not in wuzetian["third_item_strategy_crosscheck"]
    assert wuzetian["third_item_strategy_crosscheck"]["use_boundary"] == "PARENT_CYCLE_REFERENCE_ONLY_NOT_SCORE_OR_GRADE_MAPPING"


def test_c5_chat_review_recalibration_is_publicly_supported() -> None:
    settlement = _load(PROFILE_ROOT / "C5/02-C5权力运用风格与克制正式结算.json")
    audit = _load(PROFILE_ROOT / "C5/07-C5高档与证据门结构复核.json")
    remediation = _load(PROFILE_ROOT / "C5/08-C5聊天版全池二次校准整改复核.json")
    by_name = {record["ruler_name"]: record for record in settlement["records"]}
    assert settlement["summary"]["grade_distribution"] == {
        "G0": 17, "G1": 34, "G2": 59, "G3": 61, "G4": 10, "G5": 3
    }
    assert settlement["summary"]["axis_evidence_distribution"] == {"E1": 4, "E2": 42, "E3": 138}
    assert audit["density_limited_high_grade_changes"] == []
    assert len(audit["evidence_gate_changes"]) == 53
    assert audit["source_quality_gate"]["status"] == "PASS"
    assert audit["source_quality_gate"]["records_with_locator_count"] == 184
    assert audit["source_quality_gate"]["minimum_public_basis_chars"] >= 200
    assert remediation["decision_count"] == 184
    assert remediation["grade_or_position_change_count"] == 118
    assert remediation["evidence_level_change_count"] == 53
    record = by_name["李昪"]
    assert (record["axis_grade"], record["position"], record["radar_value"]) == ("G3", "HIGH", 71)
    assert "latent_high_grade_hypothesis" not in record
    assert all(record["public_evidence_points"] and record["source_refs"] for record in settlement["records"])


def test_c2_c5_joint_boundary_and_strength_review_is_closed() -> None:
    from emperor_v4.evaluation.profile_c2_c5_verifier import verify

    result = verify()
    assert result["status"] == "PASS"
    assert result["record_count"] == 184
    assert result["c5_unit_count"] == 1680


def test_profile_audit_sidecars_match_current_axis_grades() -> None:
    m1 = _load(PROFILE_ROOT / "M1/01-M1军事判断与统帅能力正式结算.json")
    m1_by_id = {record["ruler_id"]: record for record in m1["records"]}
    m1_audit = _load(PROFILE_ROOT / "M1/03-M1人才差异与高档门复核.json")
    for row in m1_audit["rows"]:
        current = m1_by_id[row["ruler_id"]]
        assert (row["revised_axis_grade"], row["revised_position"], row["revised_score_100"]) == (
            current["axis_grade"], current["position"], current["score_100"]
        )

    c5 = _load(PROFILE_ROOT / "C5/02-C5权力运用风格与克制正式结算.json")
    c5_by_id = {record["ruler_id"]: record for record in c5["records"]}
    c5_audit = _load(PROFILE_ROOT / "C5/05-C5高档材料密度复核.json")
    for review in c5_audit["reviews"]:
        current = c5_by_id[review["ruler_id"]]
        assert (review["final_grade"], review["position"], review["current_score_100"]) == (
            current["axis_grade"], current["position"], current["score_100"]
        )
