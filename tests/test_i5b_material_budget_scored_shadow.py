from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path

import pytest
import yaml

from emperor_v4.eval import main as eval_main
from emperor_v4.evaluation.i5b_material_budget_scored_shadow import (
    _appointment_density,
    _team_profile_members,
    build_i5b_material_budget_shadow,
    render_i5b_material_budget_shadow_markdown,
    write_i5b_material_budget_shadow,
)
from emperor_v4.evaluation.team_building_v8_scored_shadow import (
    _negative_review_state,
)
from emperor_v4.evaluation.i5b_joint_projection_scored_shadow import (
    build_i5b_joint_projection_scored_shadow,
)
from emperor_v4.evaluation.i5b_appointment_responsibility_contract import (
    build_appointment_responsibility_projection,
    render_appointment_responsibility_markdown,
)
from emperor_v4.evaluation.i5b_scoring_policy import evaluate_i5b_scoring_policy
from emperor_v4.evaluation.i5b_civil_candidate_retrieval import (
    SOURCE_PACK_SCHEMA_VERSION,
    _civil_candidate_queue,
    _fingerprint,
    build_civil_browser_worklist,
    run_civil_candidate_retrieval,
)
from emperor_v4.persistence.person_profile_read import (
    PROFILE_COLUMNS,
    _profile_from_row,
)


ROOT = Path(__file__).parents[1]
MANIFEST = (
    ROOT
    / "eval/i5b_team_building_historical_coverage/lishimin_material_budget_shadow_manifest_v1.yml"
)
LIUBANG_MANIFEST = (
    ROOT
    / "eval/i5b_team_building_historical_coverage/liubang_material_budget_shadow_manifest_v1.yml"
)
RESPONSIBILITY_MANIFEST = (
    ROOT
    / "tests/fixtures/i5b_appointment_responsibility_contract.yml"
)


def _by_rule(report: dict) -> dict[str, dict]:
    return {row["rule_code"]: row for row in report["rules"]}


def _offline_current_profiles() -> dict[str, dict]:
    sources = (
        ROOT
        / "eval/i5b_team_building_historical_coverage/lishimin_scored_shadow_report_v3.json",
        ROOT
        / "eval/i5b_team_building_historical_coverage/liubang_team_profile_freeze_v1.json",
    )
    profiles = {}
    for path in sources:
        source = json.loads(path.read_text(encoding="utf-8"))
        for row in source["members"]:
            negative = row.get("negative_profile") or {}
            risk_established = (
                negative.get("finding_status") == "established"
                or row.get("negative_talent_severity") is not None
            )
            person_ref = str(row["person_ref"])
            profiles[person_ref] = {
                "person_ref": person_ref,
                "review_status": "human_frozen",
                "talent_grade": str(row["effective_talent_grade"]),
                "talent_grade_basis": str(row.get("talent_grade_basis") or ""),
                "profile_ref": str(row["profile_ref"]),
                "profile_version": str(
                    row.get("profile_snapshot_version") or "offline-test-current-v1"
                ),
                "negative_risk_status": (
                    "established" if risk_established else "no_established_class"
                ),
                "negative_talent_class": (
                    negative.get("class")
                    if negative
                    else row.get("negative_talent_class")
                ),
                "negative_talent_severity": (
                    negative.get("severity")
                    if negative
                    else row.get("negative_talent_severity")
                ),
            }
    return profiles


def _mock_profile_table_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("emperor_v4.eval._v4_dsn", lambda _root: "offline-test")
    monkeypatch.setattr(
        "emperor_v4.eval.read_current_person_profiles",
        lambda _dsn: _offline_current_profiles(),
    )


def _mock_profile_read(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_profile_table_only(monkeypatch)
    monkeypatch.setattr(
        "emperor_v4.eval._load_civil_source_pack",
        lambda _path: {},
    )
    monkeypatch.setattr(
        "emperor_v4.eval.run_civil_candidate_retrieval",
        lambda **_kwargs: {
            "candidate_count": 0,
            "processed_candidate_count": 0,
            "deferred_candidate_count": 0,
            "materials": [],
            "eligible": [],
            "excluded": [],
        },
    )


def test_policy_requires_gate_then_strongest_n_without_empty_slot_penalty() -> None:
    policy = yaml.safe_load(
        (ROOT / "config/i5b-scoring-policy.yml").read_text(encoding="utf-8")
    )
    report = evaluate_i5b_scoring_policy(policy)

    assert report["summary"]["settlement_budget_enabled"] is True
    assert policy["settlement_budget"]["numeric_top_k_selection_allowed_after_gate"] is True
    assert policy["settlement_budget"]["domain_representation_quota_allowed"] is False
    assert policy["settlement_budget"]["unfilled_budget_reduces_score"] is False
    assert policy["settlement_budget"]["context_labels_are_scoring_slots"] is False
    assert "channel_factor" not in policy["rules"]["talent_discovery"]
    assert policy["rules"]["appointment_delegation"]["appointment_effect"][
        "exceptional_success"
    ] == 1.8


def test_current_person_profile_reader_contract_maps_the_one_table_shape() -> None:
    row = tuple(f"value-{index}" for index in range(len(PROFILE_COLUMNS)))

    profile = _profile_from_row(row)

    assert tuple(profile) == PROFILE_COLUMNS
    assert profile["person_ref"] == "value-0"
    with pytest.raises(ValueError, match="查询列与读取合同不一致"):
        _profile_from_row(row[:-1])


def test_civil_browser_source_pack_is_generic_bounded_and_deterministic() -> None:
    team = {
        "window": {"start": 1, "end": 10},
        "members": [
            {
                "person": "甲相",
                "person_ref": "PER-V4-000000000001",
                "role_families": ["administration"],
            },
            {
                "person": "乙将",
                "person_ref": "PER-V4-000000000002",
                "role_families": ["military", "decision"],
            },
            {
                "person": "丙官",
                "person_ref": "PER-V4-000000000003",
                "role_families": ["correction"],
            },
        ]
    }
    profiles = {
        "PER-V4-000000000001": {"talent_grade": "historic"},
        "PER-V4-000000000002": {"talent_grade": "historic"},
        "PER-V4-000000000003": {"talent_grade": "top"},
    }
    source_pack = {
        "schema_version": SOURCE_PACK_SCHEMA_VERSION,
        "ruler": "测试帝",
        "candidates": [
            {
                "person": person,
                "person_ref": person_ref,
                "leads": [
                    {
                        "measure": "通用浏览器检索发现的举措",
                        "delegated_responsibility": "受命治理",
                        "policy_or_civil_outcome": "形成治理结果",
                        "source_title": "测试史源",
                        "source_url": f"https://example.invalid/{person_ref}",
                        "source_locator": "卷一",
                        "source_excerpt": "受命治理并形成结果",
                        "judge_disposition": "eligible",
                        "judge_reason": "职责、运行和结果闭合",
                        "independence_key": f"appointment:{person_ref}:governance",
                        "appointment_importance": "major_affairs",
                        "appointment_effect": "major_success",
                        "continuity_factor": "stable",
                    }
                ],
            }
            for person, person_ref in (
                ("甲相", "PER-V4-000000000001"),
                (
                    "测试帝用人政策",
                    f"POLICY-{_fingerprint('测试帝')[:16].upper()}",
                ),
            )
        ],
    }

    queue = _civil_candidate_queue(team, profiles, ("测试帝",))
    worklist = build_civil_browser_worklist(
        ruler="测试帝",
        ruler_names=("测试帝",),
        team_source=team,
        current_profiles=profiles,
        max_candidate_judge_items=2,
    )
    first = run_civil_candidate_retrieval(
        ruler="测试帝",
        ruler_names=("测试帝",),
        team_source=team,
        current_profiles=profiles,
        max_candidate_judge_items=2,
        source_pack=source_pack,
    )
    second = run_civil_candidate_retrieval(
        ruler="测试帝",
        ruler_names=("测试帝",),
        team_source=team,
        current_profiles=profiles,
        max_candidate_judge_items=2,
        source_pack=source_pack,
    )

    assert [row["person"] for row in queue] == ["甲相", "丙官"]
    assert [row["query"] for row in worklist] == ["甲相 举措", "测试帝 用人政策"]
    assert len(first["eligible"]) == 2
    assert first["materials"][0]["factor_option_codes"] == {
        "appointment_importance": "major_affairs",
        "appointment_effect": "major_success",
        "continuity_factor": "stable",
        "attribution_factor": "direct",
        "source_factor": "complete_direct_chain",
        "context_factor": "clear",
    }
    assert second == first


def test_one_command_exports_full_ruler_scoring_detail(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_profile_read(monkeypatch)
    assert eval_main(
        [
            "i5b-scoring-detail-export",
            "--ruler",
            "李世民",
            "--workspace-root",
            str(ROOT),
            "--output-dir",
            str(tmp_path),
        ]
    ) == 0
    output_dir = tmp_path / "李世民"
    payload = json.loads(
        (output_dir / "scoring-detail.json").read_text(encoding="utf-8")
    )
    ruler = payload["selected_ruler_reports"][0]
    assert ruler["status"] == "report_only_scoring_detail_export"
    assert ruler["summary"]["historical_coverage_complete_rule_count"] == 5
    assert ruler["declarations"]["historical_coverage_complete"] is True
    assert ruler["declarations"]["current_factor_contracts_satisfied"] is True
    assert ruler["declarations"]["completion_claim_allowed"] is True
    assert ruler["selection_summary"] == {
        "selected_rule_count": 5,
        "selected_all_five_rules": True,
        "selected_rule_weighted_raw_signal": "10.091",
    }
    by_rule = _by_rule(ruler)
    assert by_rule["talent_discovery"]["historical_coverage_status"] == (
            "coverage_complete"
    )
    assert by_rule["tolerate_talent"]["factor_contract"]["status"] == (
        "current_contract"
    )
    assert not by_rule["tolerate_talent"]["factor_contract"][
        "missing_v4_factor_inputs"
    ]
    assert by_rule["talent_discovery"]["factor_contract"]["status"] == (
        "current_contract"
    )
    assert by_rule["anti_nepotism"]["factor_contract"]["status"] == (
        "current_contract"
    )
    markdown = (output_dir / "scoring-detail.md").read_text(encoding="utf-8")
    assert "### 计入材料" in markdown
    assert "| 对象 | 方向 | 材料分 | 实际计入信号 | 因子取值 |" in markdown
    assert "| 人物 | 正池贡献 | 负池贡献 |" in markdown
    assert "排名 / 衰减" not in markdown
    assert "### 人才发现候选优先级" in markdown
    assert "| 1 | 李靖 | 历史级 | 1.200 | 2.614 | 计入 |" in markdown
    assert "| 2 | 房玄龄 | 历史级 | 1.000 | 2.178 | 计入 |" in markdown
    assert "| 3 | 魏徵 | 顶级 | 1.200 | 2.105 | 计入 |" in markdown
    assert "| 4 | 马周 | 重要 | 1.200 | 1.670 | 合格，预算外 |" in markdown
    assert "候选扫描与材料预算边界" not in markdown
    assert "### 政策 / 文治成果" in markdown
    assert "五经定本与五经正义" in markdown
    assert "弘文馆精选文儒轮值宿直" in markdown
    assert "发现强度 1.200" in markdown
    assert "[discovery_level=" not in markdown
    assert "SP-8A9C97DF836016533342" not in markdown
    assert "投影模式：" not in markdown
    assert "明细对账：" not in markdown
    assert "**反馈入口强度**" not in markdown
    assert "制度化反馈入口 (`institutionalized_feedback_entry`) =" not in markdown
    assert "### 未计入材料" in markdown
    assert "| 材料 | 因子赋值 | 材料分 | 事实 |" in markdown
    assert "未计分材料与 judge 理由" not in markdown
    assert "已确认事实或争议点" not in markdown
    assert "材料分低于当前正向预算边界" not in markdown
    assert "judge_reviews" not in json.dumps(ruler, ensure_ascii=False)
    stdout = capsys.readouterr().out
    assert "文官材料：0条通过，0条排除，0人未领取" in stdout
    assert "计分详情：" in stdout


def test_person_filter_exports_group_material_individual_material_and_episodes(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_profile_read(monkeypatch)
    assert eval_main(
        [
            "i5b-scoring-detail-export",
            "--ruler",
            "李世民",
            "--person",
            "房玄龄",
            "--person",
            "杜如晦",
            "--workspace-root",
            str(ROOT),
            "--output-dir",
            str(tmp_path),
        ]
    ) == 0
    output_dir = tmp_path / "李世民"
    payload = json.loads(
        (output_dir / "scoring-detail.json").read_text(encoding="utf-8")
    )
    by_person = {row["person"]: row for row in payload["people"]}
    for person in ("房玄龄", "杜如晦"):
        kinds = {
            row["participation_kind"]
            for row in by_person[person]["participations"]
        }
        assert "counted_material" in kinds
        assert "unscored_material" in kinds
        assert "historical_episode" in kinds

    markdown = (output_dir / "scoring-detail.md").read_text(encoding="utf-8")
    assert markdown.startswith("# 臣子计分材料参与详情")
    assert "# 李世民当前计分详情" not in markdown
    assert "## 数据问题" in markdown
    assert (
        "李世民的“房玄龄、杜如晦跨阶段中枢治理责任群体”已经计入任用授权，"
        "但没有对应的同规则历史事件"
    ) in markdown
    assert "### 历史事件" in markdown
    assert "推荐核心团队成员；共同建立制度并互补决策；相须决策" in markdown
    assert "《大唐新語》自是，臺閣規模，皆二人所定" in markdown
    assert "房玄龄、杜如晦跨阶段中枢治理责任群体" in markdown
    assert "3.506580 |" in markdown
    assert "1.948100 |" in markdown
    assert "attribution_factor" not in markdown
    assert "context_factor" not in markdown
    assert "source_factor" not in markdown
    assert "`counted_material`" not in markdown
    assert "`unscored_material`" not in markdown
    assert "人才档 历史级；基础系数 1.6" in markdown
    assert "人才档 顶级；基础系数 1.2" in markdown
    assert "检索范围" not in markdown
    assert "Material ID" not in markdown
    assert "REU" not in markdown
    assert "Episode绑定" not in markdown
    assert "Source Passage" not in markdown
    assert "MAT-LSM-" not in markdown
    assert "REU-LSM-" not in markdown
    assert "SP-" not in markdown
    assert "EP-" not in markdown
    assert "安全声明" not in markdown
    assert "模型调用" not in markdown
    assert "数据库写入" not in markdown
    assert "supporting_judgment" not in markdown
    stdout = capsys.readouterr().out
    assert "臣子：房玄龄、杜如晦" in stdout
    assert "计分详情：" in stdout
    assert "结果状态" not in stdout
    assert "历史覆盖" not in stdout
    assert "raw signal" not in stdout
    assert "JSON：" not in stdout


def test_material_budget_detail_rejects_historical_coverage_override(
    tmp_path: Path,
) -> None:
    source = ROOT / (
        "eval/i5b_team_building_historical_coverage/"
        "lishimin_scoring_detail_manifest_v1.yml"
    )
    manifest = yaml.safe_load(source.read_text(encoding="utf-8"))
    manifest["historical_coverage_status_overrides"] = {
        rule_code: "coverage_complete"
        for rule_code in (
            "talent_discovery",
            "appointment_delegation",
            "team_building",
            "tolerate_talent",
            "anti_nepotism",
        )
    }
    manifest_path = tmp_path / "manifest.yml"
    manifest_path.write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="material budget detail may not override historical coverage status",
    ):
        eval_main(
            [
                "i5b-scoring-detail",
                "--manifest",
                str(manifest_path),
                "--workspace-root",
                str(ROOT),
                "--format",
                "json",
                "--output",
                str(tmp_path / "detail.json"),
            ]
        )


def test_one_command_closeout_stops_after_talent_budget_is_full(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_profile_read(monkeypatch)
    assert eval_main(
        [
            "i5b-historical-closeout",
            "--ruler",
            "李世民",
            "--workspace-root",
            str(ROOT),
            "--output-dir",
            str(tmp_path),
        ]
    ) == 0
    markdown = (tmp_path / "李世民/scoring-detail.md").read_text(encoding="utf-8")
    detail = json.loads(
        (tmp_path / "李世民/scoring-detail.json").read_text(encoding="utf-8")
    )
    assert "### 政策 / 文治成果" in markdown
    assert "五经定本与五经正义" in markdown
    assert detail["selected_ruler_reports"][0]["selection_summary"][
        "selected_rule_count"
    ] == 5
    material = json.loads(
        (tmp_path / "李世民/material-budget-shadow.json").read_text(
            encoding="utf-8"
        )
    )
    assert _by_rule(material)["team_building"]["profile_source"] == (
        "v4_person_profile.person_profiles"
    )
    stdout = capsys.readouterr().out
    assert "文官材料：0条通过，0条排除，0人未领取" in stdout
    assert "计分详情：" in stdout


def test_closeout_persists_civil_sources_and_merges_appointment_objects_before_top3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_profile_table_only(monkeypatch)

    assert eval_main(
        [
            "i5b-historical-closeout",
            "--ruler",
            "李世民",
            "--person",
            "房玄龄",
            "--workspace-root",
            str(ROOT),
            "--output-dir",
            str(tmp_path),
        ]
    ) == 0

    material = json.loads(
        (tmp_path / "李世民/material-budget-shadow.json").read_text(
            encoding="utf-8"
        )
    )
    appointment = _by_rule(material)["appointment_delegation"]
    positive = [
        row for row in appointment["settled_materials"] if row["side"] == "positive"
    ]
    positive_objects = {row["object_ref"] for row in positive}
    fang = [row for row in positive if row["subject"] == "房玄龄"]

    assert appointment["settlement_budget_unit"] == "delegated_person_or_group"
    assert len(positive_objects) == appointment["positive_budget"] == 3
    assert len(fang) >= 3
    assert len({row["object_aggregate_magnitude"] for row in fang}) == 1
    assert {row["object_aggregate_magnitude"] for row in fang} == {"3.506580"}
    assert any("《贞观律》" in row["fact"] for row in fang)
    assert any("《晋书》" in row["fact"] for row in fang)

    markdown = (tmp_path / "李世民/scoring-detail.md").read_text(encoding="utf-8")
    assert "对象合并分 / 排名" in markdown
    assert "《贞观律》" in markdown
    assert "《晋书》" in markdown
    assert "### 历史事件" in markdown

    detail_payload = json.loads(
        (tmp_path / "李世民/scoring-detail.json").read_text(encoding="utf-8")
    )
    appointment_detail = next(
        row
        for row in detail_payload["selected_ruler_reports"][0]["rules"]
        if row["rule_code"] == "appointment_delegation"
    )
    primary = next(
        source
        for source in appointment_detail["detail_sources"]
        if source["role"] == "primary"
    )["detail"]
    weighted_positive = sum(
        (
            Decimal(str(row["weighted_signal"]))
            for row in primary["materials"]
            if row["side"] == "positive"
        ),
        Decimal("0"),
    )
    assert abs(
        weighted_positive - Decimal(str(appointment_detail["positive_signal"]))
    ) < Decimal("0.00001")

    participations = detail_payload["people"][0]["participations"]
    counted_reus = {
        str(row["detail"]["rule_evidence_unit_ref"])
        for row in participations
        if row["rule_code"] == "appointment_delegation"
        and row["participation_kind"] == "counted_material"
        and row["detail"].get("subject") == "房玄龄"
    }
    episode_reus = {
        str((row["detail"].get("lineage") or {}).get("unit_ref"))
        for row in participations
        if row["rule_code"] == "appointment_delegation"
        and row["participation_kind"] == "historical_episode"
    }
    assert counted_reus <= episode_reus


def test_closeout_without_work_package_fails_closed_without_traceback(
    tmp_path: Path, capsys,
) -> None:
    assert eval_main(
        [
            "i5b-historical-closeout",
            "--ruler",
            "未配置皇帝",
            "--workspace-root",
            str(ROOT),
            "--output-dir",
            str(tmp_path),
        ]
    ) == 2
    assert not (tmp_path / "未配置皇帝/preflight.json").exists()
    assert not (tmp_path / "未配置皇帝/scoring-detail.json").exists()
    stdout = capsys.readouterr().out
    assert "未配置该皇帝" in stdout


def test_liubang_minimal_five_rule_package_closes_out_within_budget(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_profile_read(monkeypatch)
    assert eval_main(
        [
            "i5b-historical-closeout",
            "--ruler",
            "刘邦",
            "--workspace-root",
            str(ROOT),
            "--output-dir",
            str(tmp_path),
        ]
    ) == 0
    output_dir = tmp_path / "刘邦"
    detail = json.loads(
        (output_dir / "scoring-detail.json").read_text(encoding="utf-8")
    )["selected_ruler_reports"][0]
    rules = _by_rule(detail)
    material = json.loads(
        (output_dir / "material-budget-shadow.json").read_text(encoding="utf-8")
    )

    assert _by_rule(material)["team_building"]["profile_source"] == (
        "v4_person_profile.person_profiles"
    )
    assert detail["selection_summary"]["selected_rule_count"] == 5
    assert detail["declarations"]["current_factor_contracts_satisfied"] is True
    assert rules["talent_discovery"]["factor_contract"]["status"] == "current_contract"
    assert rules["anti_nepotism"]["factor_contract"]["status"] == "current_contract"
    markdown = (output_dir / "scoring-detail.md").read_text(encoding="utf-8")
    for expected in (
        "张良",
        "韩信",
        "陈平",
        "萧何守关中",
        "叔孙通朝仪",
        "樊哙",
        "卢绾私人亲幸",
    ):
        assert expected in markdown
    assert "计分详情：" in capsys.readouterr().out


def test_appointment_density_uses_competition_rank_for_ties() -> None:
    selected = [
        {"material_id": "A1", "rule_evidence_unit_ref": "EA", "object_ref": "A", "material_magnitude": Decimal("2.5")},
        {"material_id": "B1", "rule_evidence_unit_ref": "EB", "object_ref": "B", "material_magnitude": Decimal("2.5")},
        {"material_id": "C1", "rule_evidence_unit_ref": "EC", "object_ref": "C", "material_magnitude": Decimal("1.0")},
    ]

    expected = Decimal("1.5") * (
        Decimal("2.5") + Decimal("2.5") + Decimal("1") / Decimal("3").sqrt()
    )
    assert _appointment_density(selected, "positive", Decimal("3.50658")) == expected


def test_appointment_density_merges_multiple_materials_for_same_person() -> None:
    selected = [
        {"material_id": "A1", "rule_evidence_unit_ref": "EA1", "object_ref": "PERSON-A", "material_magnitude": Decimal("2")},
        {"material_id": "A2", "rule_evidence_unit_ref": "EA2", "object_ref": "PERSON-A", "material_magnitude": Decimal("1")},
        {"material_id": "B1", "rule_evidence_unit_ref": "EB1", "object_ref": "PERSON-B", "material_magnitude": Decimal("2")},
    ]

    expected = Decimal("1.5") * (
        Decimal("2.5") + Decimal("2") / Decimal("2").sqrt()
    )
    assert _appointment_density(selected, "positive", Decimal("3.50658")) == expected


def test_lishimin_budget_shadow_uses_original_aggregation_without_slots() -> None:
    report = build_i5b_material_budget_shadow(MANIFEST)
    rules = _by_rule(report)

    assert report["summary"]["weighted_raw_signal"] == "10.091101"
    assert report["summary"]["settled_event_positive_count"] == 12
    assert report["summary"]["settled_event_negative_count"] == 2
    assert report["summary"]["team_positive_member_count"] == 8
    assert report["summary"]["team_negative_member_count"] == 1
    assert rules["talent_discovery"]["rule_raw_net"] == "6.897000"
    assert rules["appointment_delegation"]["rule_raw_net"] == "12.643836"
    assert rules["team_building"]["rule_raw_net"] == "13.888000"
    assert rules["tolerate_talent"]["rule_raw_net"] == "6.304100"
    assert rules["anti_nepotism"]["rule_raw_net"] == "2.961200"
    assert "candidate_boundary_audit" not in rules["talent_discovery"]
    assert all("slot_rows" not in rule for rule in report["rules"])
    assert report["amplitude_diagnostic"]["amplitude_change_recommended"] is None
    assert report["amplitude_diagnostic"]["cohort_ruler_count"] == 1
    assert report["amplitude_diagnostic"]["theoretical_positive_envelope"][
        "appointment_delegation"
    ] == "13.706742"


def test_tolerate_projection_uses_current_v4_contract_and_rejudges_weizheng() -> None:
    projection_payload = json.loads(
        (
            ROOT
            / "eval/i5b_joint_projection_scored_shadow/"
            "tolerate_talent_projection_inputs.json"
        ).read_text(encoding="utf-8")
    )
    scoring_policy = yaml.safe_load(
        (ROOT / "config/i5b-scoring-policy.yml").read_text(encoding="utf-8")
    )
    report = build_i5b_joint_projection_scored_shadow(
        rule_code="tolerate_talent",
        projection_payload=projection_payload,
        scoring_policy=scoring_policy,
    )
    assert report["summary"]["current_v4_factor_projection_count"] == 11
    assert report["summary"]["legacy_factor_projection_count"] == 0
    assert report["declarations"][
        "all_projected_materials_use_current_v4_factor_contract"
    ] is True
    by_unit = {row["unit_ref"]: row for row in report["materials"]}
    weizheng = by_unit["TT-O01"]
    assert weizheng["material_score"] == "2.366"
    assert weizheng["numeric_projection"]["factor_option_codes"][
        "expression_safety"
    ] == "actively_protected_or_encouraged"
    assert weizheng["numeric_projection"]["v4_factor_projection"] == {
        "contract_version": "tolerate-talent-factor-agent-v3",
        "factor_choices": {
            "conflict_repair_continuity": "timely_repair",
            "feedback_reception": "accepted_after_conflict",
            "professional_autonomy": "professional_judgment_respected",
            "talent_safety": "safe_without_retaliation",
        },
    }
    assert by_unit["TT-O05"]["material_score"] == "0.653"

    broken = json.loads(json.dumps(projection_payload, ensure_ascii=False))
    broken_weizheng = next(
        row for row in broken["units"] if row["unit_ref"] == "TT-O01"
    )
    del broken_weizheng["v4_factor_choices"]["talent_safety"]
    with pytest.raises(ValueError, match="V4 factor choices 不完整"):
        build_i5b_joint_projection_scored_shadow(
            rule_code="tolerate_talent",
            projection_payload=broken,
            scoring_policy=scoring_policy,
        )


@pytest.mark.parametrize(
    ("report_path", "expected_count"),
    (
        (
            "eval/i5b_talent_discovery_historical_coverage/"
            "lishimin_scored_shadow_report_v2.json",
            7,
        ),
        (
            "eval/i5b_anti_nepotism_historical_coverage/"
            "lishimin_scored_shadow_report_v2.json",
            2,
        ),
    ),
)
def test_event_rule_canonical_reports_use_current_v4_factor_contract(
    report_path: str, expected_count: int,
) -> None:
    report = json.loads((ROOT / report_path).read_text(encoding="utf-8"))
    assert report["summary"]["current_v4_factor_projection_count"] == expected_count
    assert report["summary"]["legacy_factor_projection_count"] == 0
    assert report["declarations"][
        "all_projected_materials_use_current_v4_factor_contract"
    ] is True


def test_appointment_selects_strongest_objects_after_object_merge() -> None:
    appointment = _by_rule(build_i5b_material_budget_shadow(MANIFEST))[
        "appointment_delegation"
    ]
    selected_ids = {row["material_id"] for row in appointment["settled_materials"]}
    supporting_ids = {
        row["material_id"] for row in appointment["supporting_only_materials"]
    }

    assert {
        "MAT-LSM-FANGDU-CENTRAL-GOVERNANCE-POS",
        "MAT-LSM-LIJING-POS",
        "MAT-LSM-CHANGSUN-WUJI-CENTRAL-TRUST-POS",
    } <= selected_ids
    assert "MAT-LSM-HOUJUNJI-POS" in supporting_ids
    assert "MAT-LSM-FIVE-CLASSICS-POS" in supporting_ids
    assert "MAT-LSM-MAZHOU-POS" in supporting_ids
    assert "MAT-LSM-FANGXUANLING-POS-V2" in supporting_ids
    assert "MAT-LSM-ZHENGUAN-RITES-POS" in supporting_ids
    assert "MAT-LSM-INSTITUTION-MERIT-STAFFING-POS" in supporting_ids
    assert "MAT-LSM-HONGWEN-HALL-POS" in supporting_ids
    assert appointment["eligible_candidate_count"] == 14
    assert all(
        row["selection_basis"]
        == "eligibility_gate_then_object_merge_then_strongest_n_objects"
        for row in appointment["settled_materials"]
    )
    assert appointment["positive_budget"] == 3
    assert appointment["negative_budget"] == 3
    assert appointment["settlement_budget_unit"] == "delegated_person_or_group"

    by_id = {row["material_id"]: row for row in appointment["settled_materials"]}
    assert by_id["MAT-LSM-LIJING-POS"]["factor_option_codes"][
        "appointment_effect"
    ] == "exceptional_success"
    assert by_id["MAT-LSM-LIJING-POS"]["material_magnitude"] == "3.506580"
    assert by_id["MAT-LSM-FANGDU-CENTRAL-GOVERNANCE-POS"][
        "material_magnitude"
    ] == "3.506580"
    assert by_id["MAT-LSM-CHANGSUN-WUJI-CENTRAL-TRUST-POS"][
        "material_magnitude"
    ] == "2.922150"
    assert by_id["MAT-LSM-HOUJUNJI-NEG"]["factor_option_codes"][
        "appointment_effect"
    ] == "bounded_control_failure"
    assert by_id["MAT-LSM-HOUJUNJI-NEG"]["material_magnitude"] == "0.406560"
    assert "释放" in by_id["MAT-LSM-HOUJUNJI-NEG"]["fact"]


def test_liubang_team_pool_derives_values_from_frozen_profiles() -> None:
    report = build_i5b_material_budget_shadow(LIUBANG_MANIFEST)
    team = _by_rule(report)["team_building"]
    profile_pool = json.loads(
        (
            ROOT
            / "eval/i5b_team_building_historical_coverage/"
            "liubang_team_profile_freeze_v1.json"
        ).read_text(encoding="utf-8")
    )

    assert all("talent_value" not in row for row in profile_pool["members"])
    assert all("negative_value" not in row for row in profile_pool["members"])
    assert team["profile_source_enforced"] is True
    assert len(team["positive_members"]) == 8
    assert all(row["profile_ref"].startswith("PROFILE-") for row in team["positive_members"])
    assert all(row["profile_snapshot_version"] for row in team["positive_members"])
    assert [row["person"] for row in team["negative_members"]] == ["樊哙"]
    assert team["negative_members"][0]["negative_class"] == "cruel_official"
    assert team["negative_members"][0]["negative_severity"] == "material"
    assert team["negative_pool"] == "0.450000"
    assert report["declarations"]["team_profile_source_enforced"] is True

    broken = json.loads(json.dumps(profile_pool, ensure_ascii=False))
    fankuai = next(row for row in broken["members"] if row["person"] == "樊哙")
    fankuai["negative_profile"]["review_completed"] = False
    policy = yaml.safe_load(
        (ROOT / "config/i5b-scoring-policy.yml").read_text(encoding="utf-8")
    )
    with pytest.raises(ValueError, match="政治风险画像尚未审完"):
        _team_profile_members(broken, policy["rules"]["team_building"])


def test_insufficient_negative_profile_cannot_claim_completed_review() -> None:
    status, completed = _negative_review_state(
        {
            "review_completed": True,
            "finding_status": "no_established_negative_class",
            "class": None,
            "severity": None,
            "confidence": 0.0,
            "evidence_coverage": "insufficient",
        },
        {"negative_talent_version": "negative-talent-v1"},
    )
    assert status == "insufficient_evidence"
    assert completed is False


def test_unfilled_budget_is_neutral_and_team_is_one_window_unit() -> None:
    report = build_i5b_material_budget_shadow(MANIFEST)
    rules = _by_rule(report)
    anti = rules["anti_nepotism"]
    team = rules["team_building"]

    assert len(anti["settled_materials"]) == 3
    assert anti["positive_budget"] == 3
    assert anti["positive_signal"] == "2.961200"
    assert len(team["positive_members"]) == 8
    assert len(team["negative_members"]) == 1
    assert len(team["supporting_only_members"]) == 15
    assert team["positive_pool"] == "10.200000"
    assert team["negative_pool"] == "0.800000"
    assert team["negative_signal"] == "0.800000"


def test_team_negative_pool_is_independent_of_positive_structure_factors(
    tmp_path: Path,
) -> None:
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    team = manifest["rules"]["team_building"]
    team["functional_complementarity"] = "homogeneous"
    team["long_term_stability"] = "fragmented"
    weak_structure_manifest = tmp_path / "weak-structure.yml"
    weak_structure_manifest.write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    weak_structure = _by_rule(
        build_i5b_material_budget_shadow(weak_structure_manifest)
    )["team_building"]
    baseline = _by_rule(build_i5b_material_budget_shadow(MANIFEST))["team_building"]

    assert weak_structure["positive_signal"] != baseline["positive_signal"]
    assert weak_structure["negative_pool"] == baseline["negative_pool"] == "0.800000"
    assert weak_structure["negative_signal"] == baseline["negative_signal"] == "0.800000"


def test_report_is_deterministic_readable_and_byte_idempotent(tmp_path: Path) -> None:
    first = build_i5b_material_budget_shadow(MANIFEST)
    second = build_i5b_material_budget_shadow(MANIFEST)
    assert first == second

    markdown = render_i5b_material_budget_shadow_markdown(first)
    assert "不使用领域固定槽位" in markdown
    assert "未用满预算不扣分" in markdown
    assert "本报告不生成45分、tier或排名" in markdown
    assert "李绩" in markdown

    output_json = tmp_path / "report.json"
    output_md = tmp_path / "report.md"
    write_i5b_material_budget_shadow(
        manifest_path=MANIFEST,
        output_json=output_json,
        output_markdown=output_md,
    )
    before = (output_json.read_bytes(), output_md.read_bytes())
    write_i5b_material_budget_shadow(
        manifest_path=MANIFEST,
        output_json=output_json,
        output_markdown=output_md,
    )
    assert before == (output_json.read_bytes(), output_md.read_bytes())
    assert json.loads(output_json.read_text(encoding="utf-8"))["declarations"][
        "database_write_count"
    ] == 0


def test_appointment_responsibility_contract_supports_group_and_requires_operation(
    tmp_path: Path,
) -> None:
    acceptance = tmp_path / "acceptance.json"
    acceptance.write_text(
        json.dumps(
            {
                "units": [
                    {
                        "assertion_drafts": [
                            {
                                "assertion_code": code,
                                "formal_acceptance_disposition": "accept",
                                "source_passage_ref": f"SP-{index}",
                            }
                            for index, code in enumerate(
                                (
                                    "ASTA-0CC2E92D5ADF147CDB73",
                                    "ASTA-86D457E43B573C460F6A",
                                    "ASTA-25258DD38813785B020A",
                                ),
                                start=1,
                            )
                        ]
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    manifest = yaml.safe_load(RESPONSIBILITY_MANIFEST.read_text(encoding="utf-8"))
    manifest["formal_acceptance_source"] = str(acceptance)
    runtime_manifest = tmp_path / "responsibility.yml"
    runtime_manifest.write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    report = build_appointment_responsibility_projection(runtime_manifest)

    assert report["summary"] == {
        "unit_count": 2,
        "eligible_material_count": 1,
        "insufficient_unit_count": 1,
    }
    material = report["materials"][0]
    assert material["subject_kind"] == "responsibility_group"
    assert material["subject"] == "房玄龄等中枢员额责任群体"
    assert material["material_magnitude"] == "1.439900"
    assert material["factor_option_codes"] == {
        "appointment_importance": "critical_national_or_long_term",
        "appointment_effect": "normal_success",
        "continuity_factor": "short_or_one_off",
        "attribution_factor": "direct",
        "source_factor": "complete_direct_chain",
        "context_factor": "core_mechanism_direct",
    }
    assert report["insufficient_units"][0]["missing_inputs"] == [
        "actual_operation_observation"
    ]
    markdown = render_appointment_responsibility_markdown(report)
    assert "具体受任者" not in report["insufficient_units"][0]["judge_reason"]
    assert "本报告不生成45分、tier或排名" in markdown
