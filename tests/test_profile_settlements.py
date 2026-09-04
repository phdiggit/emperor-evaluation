from __future__ import annotations

from pathlib import Path

from emperor_v4.evaluation.formal_json_store import load_json


ROOT = Path(__file__).resolve().parents[1]
PROFILE_ROOT = ROOT / "docs" / "评分结算" / "皇帝人物画像"
CONTRACT = ROOT / "docs" / "项目总纲" / "皇帝人物画像评估体系合同.md"
POOL = ROOT / "config" / "common" / "canonical-ruler-pool.json"


def _load(path: Path) -> dict:
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    return load_json(path)


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
    assert not any("sha256" in key.lower() or key.lower().endswith("_hash") for key in manifest)
    assert next(axis for axis in manifest["axes"] if axis["axis_code"] == "M3")["status"] == "FORMAL_CURRENT"
    for axis in manifest["axes"]:
        assert axis["record_count"] == len(_included_ids())
        assert (PROFILE_ROOT / axis["json"]).is_file()
        assert (PROFILE_ROOT / axis["markdown"]).is_file()
        assert not any("sha256" in key.lower() or key.lower().endswith("_hash") for key in axis)
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
        assert settlement["record_count"] == len(records)
        assert {record["ruler_id"] for record in records} == expected_ids
        assert len({record["task_code"] for record in records}) == len(records)
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
    assert audit["unit_count"] == len(units)
    assert len({unit["unit_id"] for unit in units}) == len(units)
    assert set(audit["status_counts"]) == {
        "SCORING_PARENT",
        "BACKGROUND_VALIDATION",
        "AXIS_OUT_WITH_REASON",
    }
    assert sum(audit["status_counts"].values()) == len(units)
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
    assert audit["policy"]["mi_is_material_strength_not_grade"] is True
    assert audit["policy"]["negative_evidence_automatically_caps_g5"] is False
    assert audit["policy"]["positive_mi4_automatically_grants_g5"] is False


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

    settlement_md = (PROFILE_ROOT / "M1/01-M1军事判断与统帅能力正式结算.md").read_text(encoding="utf-8")
    assert "- 武将登记逐项（成果等级/难度｜战役群名称/武将角色）：\n  " in settlement_md
    assert "- 战役成果等级/难度组合：" not in settlement_md
    assert "- 战役群名称/武将角色：" not in settlement_md


def test_m1_missing_profiles_include_founding_and_post_unification_command_windows() -> None:
    settlement = _load(PROFILE_ROOT / "M1/01-M1军事判断与统帅能力正式结算.json")
    audit = _load(PROFILE_ROOT / "M1/10-M1无档案战役与人才公共补录复核.json")

    assert audit["canonical_status"] == "FORMAL_CURRENT_AUDIT"
    assert audit["window_policy"] == "FOUNDING_UNIFICATION_AND_POST_UNIFICATION_PERSONAL_EXPEDITIONS_INCLUDED"
    assert all(
        decision["person_command_result_refs"]
        and decision["campaign_refs"]
        and decision["capability_episode_refs"]
        and decision["source_refs"]
        for decision in audit["profile_decisions"]
    )


def test_m1_full_pool_readjudication_closes_all_records_and_failure_rule() -> None:
    settlement = _load(PROFILE_ROOT / "M1/01-M1军事判断与统帅能力正式结算.json")
    audit = _load(PROFILE_ROOT / "M1/11-M1全池重新裁决复核.json")
    by_name = {record["ruler_name"]: record for record in settlement["records"]}

    assert audit["canonical_status"] == "FORMAL_CURRENT_AUDIT"
    assert audit["record_count"] == len(audit["rows"])
    assert {row["ruler_name"] for row in audit["rows"]} == set(by_name)
    assert audit["review_policy"]["target_nonachievement_automatically_treated_as_defeat"] is False
    assert all(record["full_pool_readjudication"]["status"] == "FULL_LIFETIME_REVIEWED" for record in settlement["records"])
    assert all("V0.5未重开" not in parent["intensity_and_role_basis"] for record in settlement["records"] for parent in record["representative_parent_contexts"])


def test_c5_chat_review_recalibration_is_publicly_supported() -> None:
    settlement = _load(PROFILE_ROOT / "C5/02-C5权力运用风格与克制正式结算.json")
    audit = _load(PROFILE_ROOT / "C5/07-C5高档与证据门结构复核.json")
    assert audit["source_quality_gate"]["status"] == "PASS"
    assert audit["source_quality_gate"]["minimum_public_basis_chars"] >= 200
    assert all(record["public_evidence_points"] and record["source_refs"] for record in settlement["records"])


def test_c5_boundary_and_strength_review_is_closed() -> None:
    from emperor_v4.evaluation.profile_c2_c5_verifier import verify

    result = verify()
    assert result["status"] == "PASS"


def test_c2_c5_cross_axis_drift_is_report_only() -> None:
    from emperor_v4.evaluation.profile_c2_c5_cross_axis_audit import inspect_cross_axis_drift

    result = inspect_cross_axis_drift()
    assert result["status"] in {"CURRENT", "REVIEW_REQUIRED"}
    assert result["status_mismatch_count"] == len(result["status_mismatches"])


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
