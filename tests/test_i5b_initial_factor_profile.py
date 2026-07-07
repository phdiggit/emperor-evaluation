from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.dev import i5b_initial_factor_profile as tool
from scripts.dev.rule_material_policy import policy_map_from_rows


def material(
    *,
    obj_src_id: int = 2304,
    emperor: str = "刘彻",
    rule_code: str = "appointment_delegation",
    obj_name: str = "儿宽",
    direction: str = "positive",
    talent_quality: str = "",
) -> dict[str, object]:
    return {
        "emperor": emperor,
        "rule_code": rule_code,
        "obj_src_id": obj_src_id,
        "direction": direction,
        "emp_obj_id": 340,
        "obj_id": obj_src_id + 1000,
        "obj_type": "person",
        "obj_period": "西汉",
        "obj_name": obj_name,
        "src_key": "SRC-WS-237F6D77AD",
        "title": "漢書",
        "author": "班固",
        "dynasty": "东汉",
        "volume": "卷058",
        "locator": "漢書/卷058",
        "source_url": "",
        "obj_src_note": "任用材料。",
        "source_note": "source note",
        "talent_quality": talent_quality,
    }


def team_member(
    *,
    emp_obj_id: int = 340,
    emperor: str = "刘邦",
    obj_name: str = "萧何",
    talent_quality: str = "顶级人才",
) -> dict[str, object]:
    return {
        "emperor": emperor,
        "rule_code": "team_building",
        "obj_src_id": None,
        "direction": "positive",
        "emp_obj_id": emp_obj_id,
        "obj_id": emp_obj_id + 1000,
        "obj_type": "person",
        "obj_period": "西汉",
        "obj_name": obj_name,
        "src_key": "",
        "title": "",
        "author": "",
        "dynasty": "",
        "volume": "",
        "locator": "",
        "source_url": "",
        "obj_src_note": "team member",
        "source_note": "",
        "talent_quality": talent_quality,
    }


def factor_options() -> list[dict[str, object]]:
    return [
        {
            "rule_code": "appointment_delegation",
            "factor_name": "appointment_importance",
            "label": "有实际职责的任用、信任或单一领域真实授权。",
            "value_num": "1",
            "factor_option_id": 43,
        },
        {
            "rule_code": "appointment_delegation",
            "factor_name": "appointment_effect",
            "label": "任用授权结果基本有效。",
            "value_num": "1.2",
            "factor_option_id": 44,
        },
        {
            "rule_code": "appointment_delegation",
            "factor_name": "continuity_factor",
            "label": "持续任用。",
            "value_num": "1.1",
            "factor_option_id": 45,
        },
        {"rule_code": "", "factor_name": "attribution_factor", "label": "直接归因", "value_num": "1"},
        {"rule_code": "", "factor_name": "source_factor", "label": "基础史源", "value_num": "1"},
        {"rule_code": "", "factor_name": "context_factor", "label": "上下文清楚", "value_num": "1"},
        {
            "rule_code": "team_building",
            "factor_name": "talent_quality_factor",
            "label": "顶级人才",
            "value_num": "2.2",
            "factor_option_id": 80,
        },
        {
            "rule_code": "talent_discovery",
            "factor_name": "talent_quality_factor",
            "label": "顶级人才",
            "value_num": "1.8",
            "factor_option_id": 83,
        },
        {
            "rule_code": "team_building",
            "factor_name": "role_complementarity_factor",
            "label": "较强互补，至少三个功能面有重要及以上对象承担，并能形成决策、执行和纠偏/安全之间的配合。",
            "value_num": "1.2",
            "factor_option_id": 81,
        },
        {
            "rule_code": "team_building",
            "factor_name": "long_term_stability_factor",
            "label": "核心团队长期稳定，关键成员能持续发挥作用。",
            "value_num": "1.1",
            "factor_option_id": 82,
        },
    ]


def appointment_patch(obj_src_id: int = 2304) -> dict[str, object]:
    return {
        "obj_src_id": obj_src_id,
        "target_action": "score",
        "side": "positive",
        "factor_refs": {
            "appointment_importance": {"label": "有实际职责的任用、信任或单一领域真实授权。"},
            "appointment_effect": {"label": "任用授权结果基本有效。"},
            "continuity_factor": {"label": "持续任用。"},
            "attribution_factor": {"label": "直接归因"},
            "source_factor": {"label": "基础史源"},
            "context_factor": {"label": "上下文清楚"},
        },
        "patch_note": "按对象链首轮因子化。",
    }


def _patch_from_material_template(material_row: dict[str, object]) -> dict[str, object]:
    template = material_row["factor_patch_template"]
    assert isinstance(template, dict)
    candidates = template["factor_option_candidates"]
    assert isinstance(candidates, dict)
    factor_refs = {}
    for factor_name in template["factor_keys"]:
        ref = dict(template["factor_refs"].get(factor_name) or {})
        if not ref.get("label"):
            rows = candidates.get(factor_name) or []
            ref["label"] = rows[0]["label"] if rows else "保守占位"
        factor_refs[factor_name] = ref
    return {
        "obj_src_id": material_row["obj_src_id"],
        "target_action": "score",
        "side": template["side"],
        "factor_refs": factor_refs,
        "patch_note": "按候选因子保守计入。",
    }


def test_build_report_groups_initial_materials_and_team_template() -> None:
    report = tool.build_report_from_rows(
        [
            material(),
            material(
                obj_src_id=2401,
                emperor="刘邦",
                rule_code="team_building",
                obj_name="萧何",
                talent_quality="顶级人才",
            ),
        ],
        factor_options=factor_options(),
        batch_size=10,
    )

    assert report["initial_cluster_count"] == 2
    groups = {(group["emperor"], group["rule_code"]): group for group in report["groups"]}
    team_group = groups[("刘邦", "team_building")]

    assert team_group["materials"][0]["factor_patch_template"]["factor_refs"] == {
        "talent_quality_factor": {"label": "顶级人才"}
    }
    assert team_group["cluster_patch_template"]["team_factors"] == {
        "role_complementarity_factor": {"label": ""},
        "long_term_stability_factor": {"label": ""},
    }


def test_build_report_accepts_team_members_without_obj_src_id() -> None:
    report = tool.build_report_from_rows(
        [team_member(emp_obj_id=501, obj_name="张良")],
        factor_options=factor_options(),
        batch_size=10,
    )

    group = report["groups"][0]
    material_row = group["materials"][0]
    assert group["pending_material_ids"] == []
    assert group["pending_material_keys"] == ["emp_obj:501"]
    assert material_row["factor_patch_template"]["factor_refs"] == {
        "talent_quality_factor": {"label": "顶级人才"}
    }


def test_talent_discovery_template_prefills_talent_quality_attr() -> None:
    report = tool.build_report_from_rows(
        [
            material(
                rule_code="talent_discovery",
                obj_name="霍去病",
                talent_quality="顶级人才",
            )
        ],
        factor_options=factor_options(),
        batch_size=10,
    )

    template = report["groups"][0]["materials"][0]["factor_patch_template"]
    assert template["factor_refs"]["talent_quality_factor"] == {"label": "顶级人才"}
    assert template["factor_option_candidates"]["talent_quality_factor"] == [
        {
            "factor_option_id": 83,
            "label": "顶级人才",
            "source_doc": None,
            "source_line": None,
            "value_num": "1.8",
        }
    ]


def test_validate_initial_patch_requires_team_cluster_patch() -> None:
    report = tool.build_report_from_rows(
        [
            material(
                obj_src_id=2401,
                emperor="刘邦",
                rule_code="team_building",
                obj_name="萧何",
                talent_quality="顶级人才",
            )
        ],
        factor_options=factor_options(),
    )
    batch = report["suggested_batches"][0]

    with pytest.raises(tool.InitialFactorProfileError, match="missing team_building cluster patch"):
        tool.validate_initial_patch(
            batch,
            [
                {
                    "obj_src_id": 2401,
                    "target_action": "score",
                    "side": "positive",
                    "factor_refs": {"talent_quality_factor": {"label": "顶级人才"}},
                    "patch_note": "纳入团队质量。",
                }
            ],
        )


def test_validate_initial_patch_uses_rule_material_policy_map() -> None:
    report = tool.build_report_from_rows(
        [
            material(
                rule_code="talent_discovery",
                obj_name="霍去病",
                talent_quality="顶级人才",
            )
        ],
        factor_options=factor_options(),
    )
    batch = report["suggested_batches"][0]
    material_row = batch["groups"][0]["materials"][0]
    patch = [_patch_from_material_template(material_row)]

    missing_policy = tool.validate_initial_patch(batch, patch, policies={})
    assert any(issue["status"] == "missing_rule_material_policy" for issue in missing_policy["issues"])

    policies = policy_map_from_rows(
        [
            {
                "item_code": "I5B",
                "rule_code": "talent_discovery",
                "policy_code": "person_material_policy",
            }
        ]
    )
    report_with_policy = tool.validate_initial_patch(batch, patch, policies=policies)

    assert report_with_policy["ok"] is True


def test_build_profile_from_patches_writes_clusters_and_excluded_ids(tmp_path) -> None:
    report = tool.build_report_from_rows(
        [material(), material(obj_src_id=2305, obj_name="董仲舒")],
        factor_options=factor_options(),
        batch_size=10,
    )
    batch = report["suggested_batches"][0]
    batch_path = tmp_path / "batch.json"
    patch_path = tmp_path / "patch.jsonl"
    batch_path.write_text(json.dumps(batch, ensure_ascii=False), encoding="utf-8")
    patch_rows = [
        appointment_patch(2304),
        {"obj_src_id": 2305, "target_action": "exclude", "patch_note": "不属本 rule。"},
    ]
    patch_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in patch_rows) + "\n",
        encoding="utf-8",
    )

    profile = tool.build_profile_from_patches(tool.load_batch_patch_pairs([batch_path], [patch_path]))

    assert profile["factor_source"] == "table"
    assert len(profile["clusters"]) == 1
    cluster = profile["clusters"][0]
    assert cluster["emperor"] == "刘彻"
    assert cluster["rule_code"] == "appointment_delegation"
    assert cluster["material_ids"] == [2304, 2305]
    assert cluster["excluded_material_ids"] == [2305]
    assert cluster["materials"][0]["factors"]["appointment_importance"] == {
        "label": "有实际职责的任用、信任或单一领域真实授权。"
    }


def test_build_profile_from_supporting_only_writes_no_score_cluster(tmp_path) -> None:
    report = tool.build_report_from_rows(
        [material()],
        factor_options=factor_options(),
        batch_size=10,
    )
    batch = report["suggested_batches"][0]
    batch_path = tmp_path / "batch.json"
    patch_path = tmp_path / "patch.jsonl"
    batch_path.write_text(json.dumps(batch, ensure_ascii=False), encoding="utf-8")
    patch_path.write_text(
        json.dumps(
            {
                "obj_src_id": 2304,
                "target_action": "supporting_only",
                "patch_note": "没有合格计分承载，只作上下文。",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    profile = tool.build_profile_from_patches(tool.load_batch_patch_pairs([batch_path], [patch_path]))

    assert profile["skipped_groups"] == []
    assert profile["no_score_groups"] == [
        {
            "covered_material_ids": [2304],
            "emperor": "刘彻",
            "reason": "no_scored_materials",
            "rule_code": "appointment_delegation",
        }
    ]
    cluster = profile["clusters"][0]
    assert cluster["materials"] == []
    assert cluster["material_ids"] == [2304]
    assert cluster["supporting_material_ids"] == [2304]
    assert cluster["no_score_reason"] == "no_scored_materials"


def test_build_profile_from_team_patch() -> None:
    report = tool.build_report_from_rows(
        [
            material(
                obj_src_id=2401,
                emperor="刘邦",
                rule_code="team_building",
                obj_name="萧何",
                talent_quality="顶级人才",
            )
        ],
        factor_options=factor_options(),
    )
    batch = report["suggested_batches"][0]
    patch_rows = [
        {
            "obj_src_id": 2401,
            "target_action": "score",
            "side": "positive",
            "factor_refs": {"talent_quality_factor": {"label": "顶级人才"}},
            "patch_note": "纳入团队质量。",
        },
        {
            "patch_type": "cluster",
            "emperor": "刘邦",
            "rule_code": "team_building",
            "team_factors": {
                "role_complementarity_factor": {
                    "label": "较强互补，至少三个功能面有重要及以上对象承担，并能形成决策、执行和纠偏/安全之间的配合。"
                },
                "long_term_stability_factor": {"label": "核心团队长期稳定，关键成员能持续发挥作用。"},
            },
            "cluster_note": "团队互补和稳定性已判定。",
        },
    ]

    batch_path = Path("batch.json")
    profile = tool.build_profile_from_patches([(batch_path, batch, patch_rows)])

    assert profile["source_batches"] == [str(batch_path)]
    cluster = profile["clusters"][0]
    assert cluster["rule_code"] == "team_building"
    assert cluster["team_factors"]["long_term_stability_factor"] == {"label": "核心团队长期稳定，关键成员能持续发挥作用。"}


def test_build_profile_from_team_member_patch_without_obj_src_id() -> None:
    report = tool.build_report_from_rows(
        [team_member(emp_obj_id=501, obj_name="张良")],
        factor_options=factor_options(),
    )
    batch = report["suggested_batches"][0]
    patch_rows = [
        {
            "emp_obj_id": 501,
            "target_action": "score",
            "side": "positive",
            "factor_refs": {"talent_quality_factor": {"label": "顶级人才"}},
            "patch_note": "纳入团队质量。",
        },
        {
            "patch_type": "cluster",
            "emperor": "刘邦",
            "rule_code": "team_building",
            "team_factors": {
                "role_complementarity_factor": {
                    "label": "较强互补，至少三个功能面有重要及以上对象承担，并能形成决策、执行和纠偏/安全之间的配合。"
                },
                "long_term_stability_factor": {"label": "核心团队长期稳定，关键成员能持续发挥作用。"},
            },
            "cluster_note": "团队互补和稳定性已判定。",
        },
    ]

    validation = tool.validate_initial_patch(batch, patch_rows)
    assert validation["expected_materials"] == 1
    assert validation["patch_rows"] == 1
    assert validation["action_counts"] == {"score": 1}

    profile = tool.build_profile_from_patches([(Path("batch.json"), batch, patch_rows)])

    cluster = profile["clusters"][0]
    assert cluster["material_ids"] == []
    assert cluster["materials"] == [
        {
            "direction": "positive",
            "emp_obj_id": 501,
            "factors": {"talent_quality_factor": {"label": "顶级人才"}},
            "obj_id": 1501,
            "obj_key": "1501",
            "obj_name": "张良",
            "obj_period": "西汉",
        }
    ]
