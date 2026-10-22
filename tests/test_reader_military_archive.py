from __future__ import annotations

import importlib.util
import json
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "reader" / "build_military_archive.py"
spec = importlib.util.spec_from_file_location("build_military_archive", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def write_first_item_c(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def minimal_commander(tmp_path: Path) -> None:
    write_json(tmp_path / module.COMMANDER_MANIFEST, {"profile_count": 1})
    write_json(
        tmp_path / module.COMMANDER_DIR / "bucket-00.json",
        {
            "profiles": [{
                "profile_ref": "MIL-PROFILE-TEST",
                "person_ref": "MIL-PER-TEST",
                "person": "测试将领",
                "dynasty": "测试朝",
                "military_grade": "elite",
                "actor_ref_aliases": ["PERSON-TEST"],
            }]
        },
    )


def test_military_archive_indexes_point_to_canonical_shards(tmp_path: Path):
    write_json(tmp_path / module.BATTLE_MANIFEST, {"record_count": 1})
    write_json(
        tmp_path / module.BATTLE_DIR / "demo-00.json",
        {
            "records": [{
                "war_event_id": "WAR-TEST-1",
                "dynasty": "测试朝",
                "canonical_label": "测试战役",
                "campaign_tier": "A",
                "combat_difficulty": "D3",
                "members": [{
                    "actor_name": "测试将领",
                    "person_command_result": [{"result_ref": "PCR-TEST-1"}],
                }],
            }]
        },
    )
    minimal_commander(tmp_path)

    battles, commanders = module.build_indexes(tmp_path)

    assert battles["record_count"] == 1
    assert battles["records"][0]["id"] == "WAR-TEST-1"
    assert battles["result_ref_to_battle"]["PCR-TEST-1"] == "WAR-TEST-1"
    assert commanders["profile_count"] == 1
    assert commanders["records"][0]["profile_ref"] == "MIL-PROFILE-TEST"


def test_person_only_registration_does_not_duplicate_its_public_parent(tmp_path: Path):
    write_json(tmp_path / module.BATTLE_MANIFEST, {"record_count": 2})
    write_json(tmp_path / module.BATTLE_DIR / "demo-00.json", {"records": [
        {"war_event_id": "WAR-SYNTHETIC", "canonical_label": "独立构造的战争",
         "members": [{"actor_name": "测试将领", "person_command_result": [{"result_ref": "PCR-SYNTHETIC"}]}]},
        {"war_event_id": "PCR-SYNTHETIC", "canonical_label": "既有本人成果的来源补登记",
         "record_level": "person_command_result_registration", "settlement_scope": "PERSON_RESULT_ONLY",
         "public_outcome_registered": False, "members": []}]})
    minimal_commander(tmp_path)
    battles, _ = module.build_indexes(tmp_path)
    assert battles["record_count"] == len(battles["records"]) == 1
    assert battles["result_ref_to_battle"]["PCR-SYNTHETIC"] == "WAR-SYNTHETIC"
    # Input count is still checked against all current registry records.
    write_json(tmp_path / module.BATTLE_MANIFEST, {"record_count": 3})
    import pytest
    with pytest.raises(ValueError, match="count mismatch"):
        module.build_indexes(tmp_path)


def test_first_item_c_anchor_binds_only_unique_matching_battle(tmp_path: Path):
    write_json(tmp_path / module.BATTLE_MANIFEST, {"record_count": 2})
    write_json(
        tmp_path / module.BATTLE_DIR / "demo-00.json",
        {
            "records": [
                {
                    "war_event_id": "WAR-TEST-NORTH",
                    "dynasty": "测试朝",
                    "canonical_label": "测试君主亲率主力完成北门决战",
                    "campaign_tier": "A",
                    "combat_difficulty": "D3",
                    "members": [{
                        "actor_name": "测试君主",
                        "person_command_result": [{
                            "result_ref": "PCR-TEST-NORTH",
                            "result_label": "北门决战",
                            "result_tier": "A",
                            "combat_difficulty": "D3",
                        }],
                    }],
                },
                {
                    "war_event_id": "WAR-TEST-SOUTH",
                    "dynasty": "测试朝",
                    "canonical_label": "另一人物完成南门战役",
                    "campaign_tier": "A",
                    "combat_difficulty": "D3",
                    "members": [{"actor_name": "另一人物"}],
                },
            ]
        },
    )
    minimal_commander(tmp_path)
    write_first_item_c(
        tmp_path / module.FIRST_ITEM_C_SETTLEMENT,
        "# 第一项C\n\n### 1. 测试君主\n\n- **结算依据**：已有北门决战A/D3。\n",
    )

    battles, _ = module.build_indexes(tmp_path)
    anchor = battles["first_item_c_anchors"][0]

    assert anchor["status"] == "resolved_unique"
    assert anchor["battle_id"] == "WAR-TEST-NORTH"
    assert battles["first_item_c_anchor_lookup"]["北门决战"] == "WAR-TEST-NORTH"


def test_first_item_c_structured_battle_list_preserves_roles(tmp_path: Path):
    write_json(tmp_path / module.BATTLE_MANIFEST, {"record_count": 1})
    write_json(
        tmp_path / module.BATTLE_DIR / "demo-00.json",
        {
            "records": [{
                "war_event_id": "WAR-TEST-STRUCTURED",
                "dynasty": "测试朝",
                "canonical_label": "测试君主完成北门决战",
                "campaign_tier": "A",
                "combat_difficulty": "D3",
                "members": [{
                    "actor_name": "测试君主",
                    "person_command_result": [{
                        "result_ref": "PCR-TEST-STRUCTURED",
                        "result_tier": "A",
                        "combat_difficulty": "D3",
                    }],
                }],
            }],
        },
    )
    minimal_commander(tmp_path)
    write_first_item_c(
        tmp_path / module.FIRST_ITEM_C_SETTLEMENT,
        "# 第一项C\n\n### 1. 测试君主\n\n"
        "- **统一链战役清单**：北门决战｜前线作战｜A｜D3；全局方案｜战略统筹｜S｜—。\n",
    )

    battles, _ = module.build_indexes(tmp_path)
    by_anchor = {row["anchor"]: row for row in battles["first_item_c_anchors"]}

    assert by_anchor["北门决战"]["role"] == "前线作战"
    assert by_anchor["北门决战"]["status"] == "resolved_unique"
    assert by_anchor["全局方案"]["role"] == "战略统筹"
    assert by_anchor["全局方案"]["anchor_kind"] == "strategic"
    assert by_anchor["全局方案"]["status"] == "search_only_strategic"


def test_first_item_c_aggregate_anchor_remains_search_only(tmp_path: Path):
    write_json(tmp_path / module.BATTLE_MANIFEST, {"record_count": 1})
    write_json(
        tmp_path / module.BATTLE_DIR / "demo-00.json",
        {"records": [{
            "war_event_id": "WAR-TEST-AGG",
            "dynasty": "测试朝",
            "canonical_label": "测试君主北门作战",
            "campaign_tier": "A",
            "combat_difficulty": "D3",
            "members": [{"actor_name": "测试君主"}],
        }]},
    )
    minimal_commander(tmp_path)
    write_first_item_c(
        tmp_path / module.FIRST_ITEM_C_SETTLEMENT,
        "# 第一项C\n\n### 1. 测试君主\n\n- **结算依据**：北门诸战与南门终局形成多次A/D3。\n",
    )

    battles, _ = module.build_indexes(tmp_path)
    anchor = battles["first_item_c_anchors"][0]

    assert anchor["status"] == "search_only_aggregate"
    assert anchor["battle_id"] is None


def test_first_item_c_ambiguous_match_is_not_directly_bound(tmp_path: Path):
    write_json(tmp_path / module.BATTLE_MANIFEST, {"record_count": 2})
    records = []
    for suffix in ("A", "B"):
        records.append({
            "war_event_id": f"WAR-TEST-{suffix}",
            "dynasty": "测试朝",
            "canonical_label": "测试君主参加北门决战",
            "campaign_tier": "A",
            "combat_difficulty": "D3",
            "members": [{
                "actor_name": "测试君主",
                "person_command_result": [{
                    "result_ref": f"PCR-TEST-{suffix}",
                    "result_label": "北门决战",
                    "result_tier": "A",
                    "combat_difficulty": "D3",
                }],
            }],
        })
    write_json(tmp_path / module.BATTLE_DIR / "demo-00.json", {"records": records})
    minimal_commander(tmp_path)
    write_first_item_c(
        tmp_path / module.FIRST_ITEM_C_SETTLEMENT,
        "# 第一项C\n\n### 1. 测试君主\n\n- **结算依据**：已有北门决战A/D3。\n",
    )

    battles, _ = module.build_indexes(tmp_path)
    anchor = battles["first_item_c_anchors"][0]

    assert anchor["status"] == "ambiguous"
    assert anchor["battle_id"] is None
    assert "北门决战" not in battles["first_item_c_anchor_lookup"]


def test_military_archive_index_does_not_copy_full_adjudication_text(tmp_path: Path):
    long_basis = "不应进入轻量索引" * 30
    write_json(tmp_path / module.BATTLE_MANIFEST, {"record_count": 1})
    write_json(
        tmp_path / module.BATTLE_DIR / "demo-00.json",
        {"records": [{
            "war_event_id": "WAR-TEST-2",
            "dynasty": "测试朝",
            "canonical_label": "测试战役二",
            "tier_basis": long_basis,
            "combat_difficulty_basis": long_basis,
            "source_refs": [long_basis],
            "members": [],
        }]},
    )
    write_json(tmp_path / module.COMMANDER_MANIFEST, {"profile_count": 1})
    write_json(
        tmp_path / module.COMMANDER_DIR / "bucket-00.json",
        {"profiles": [{
            "profile_ref": "MIL-PROFILE-TEST-2",
            "person": "测试将领二",
            "dynasty": "测试朝",
            "military_grade": "top",
            "consumed_achievements": [{"basis": long_basis}],
        }]},
    )

    battles, commanders = module.build_indexes(tmp_path)
    packed = json.dumps({"b": battles, "c": commanders}, ensure_ascii=False)

    assert long_basis not in packed


def setup_commander_manifest(tmp_path: Path, profile: dict) -> None:
    write_json(tmp_path / module.COMMANDER_MANIFEST, {"profile_count": 1})
    write_json(tmp_path / module.COMMANDER_DIR / "bucket-00.json", {"profiles": [profile]})


def test_campaign_ref_can_point_directly_to_war_event_id(tmp_path: Path):
    write_json(tmp_path / module.BATTLE_MANIFEST, {"record_count": 1})
    write_json(
        tmp_path / module.BATTLE_DIR / "demo-00.json",
        {"records": [{
            "war_event_id": "WAR-TEST-GAOPING",
            "dynasty": "测试朝",
            "canonical_label": "高平会战",
            "campaign_tier": "A",
            "combat_difficulty": "D3",
        }]},
    )
    setup_commander_manifest(tmp_path, {
        "profile_ref": "MIL-PROFILE-RULER",
        "person": "测试君主",
        "dynasty": "测试朝",
        "consumed_achievements": [{
            "campaign_ref": "WAR-TEST-GAOPING",
            "canonical_label": "高平右军先溃后的亲督逆转",
            "campaign_tier": "A",
            "combat_difficulty": "D3",
        }],
    })
    write_first_item_c(
        tmp_path / module.FIRST_ITEM_C_SETTLEMENT,
        "# 第一项C\n\n### 1. 测试君主\n\n- **结算依据**：高平亲督逆转A/D3。\n",
    )

    battles, _ = module.build_indexes(tmp_path)
    anchor = battles["first_item_c_anchors"][0]
    assert anchor["status"] == "resolved_unique"
    assert anchor["resolution_mode"] == "registry_ref"
    assert anchor["battle_id"] == "WAR-TEST-GAOPING"


def test_more_specific_capability_ref_is_tried_when_campaign_ref_is_unmapped(tmp_path: Path):
    write_json(tmp_path / module.BATTLE_MANIFEST, {"record_count": 1})
    write_json(
        tmp_path / module.BATTLE_DIR / "demo-00.json",
        {"records": [{
            "war_event_id": "WAR-TEST-PHASE",
            "dynasty": "测试朝",
            "canonical_label": "青丘会战",
            "subject_phase_views": [{
                "phase_id": "WAR-TEST-PHASE-P01",
                "evaluation_subject_phase": "青丘反击阶段",
            }],
        }]},
    )
    setup_commander_manifest(tmp_path, {
        "profile_ref": "MIL-PROFILE-RULER",
        "person": "测试君主",
        "dynasty": "测试朝",
        "consumed_achievements": [{
            "campaign_ref": "UNMAPPED-BROAD-CAMPAIGN",
            "capability_episode_ref": "WAR-TEST-PHASE-P01",
            "canonical_label": "青丘反击",
            "campaign_tier": "A",
            "combat_difficulty": "D3",
        }],
    })
    write_first_item_c(
        tmp_path / module.FIRST_ITEM_C_SETTLEMENT,
        "# 第一项C\n\n### 1. 测试君主\n\n- **结算依据**：青丘反击A/D3。\n",
    )

    battles, _ = module.build_indexes(tmp_path)
    anchor = battles["first_item_c_anchors"][0]
    assert anchor["status"] == "resolved_unique"
    assert anchor["resolution_mode"] == "registry_ref"
    assert anchor["battle_id"] == "WAR-TEST-PHASE"


def test_strategic_and_window_phrases_do_not_become_fake_atomic_battles(tmp_path: Path):
    write_json(tmp_path / module.BATTLE_MANIFEST, {"record_count": 1})
    write_json(
        tmp_path / module.BATTLE_DIR / "demo-00.json",
        {"records": [{
            "war_event_id": "WAR-TEST-ONLY",
            "dynasty": "测试朝",
            "canonical_label": "测试战役",
        }]},
    )
    setup_commander_manifest(tmp_path, {
        "profile_ref": "MIL-PROFILE-RULER",
        "person": "测试君主",
        "dynasty": "测试朝",
    })
    write_first_item_c(
        tmp_path / module.FIRST_ITEM_C_SETTLEMENT,
        "# 第一项C\n\n### 1. 测试君主\n\n"
        "- **结算依据**：魏博方向B/D2；建立测试政权B/D2；南方政权的创业战争A/D3；"
        "欺敌渡河并建立核心A/D3；松锦围攻未克是同窗口B/D1。\n",
    )

    battles, _ = module.build_indexes(tmp_path)
    by_anchor = {row["anchor"]: row for row in battles["first_item_c_anchors"]}
    assert by_anchor["魏博方向"]["status"] == "search_only_strategic"
    assert by_anchor["建立测试政权"]["status"] == "search_only_strategic"
    assert by_anchor["南方政权的创业战争"]["status"] == "search_only_strategic"
    assert by_anchor["欺敌渡河并建立核心"]["status"] == "search_only_strategic"
    assert by_anchor["松锦围攻未克是同窗口"]["status"] == "search_only_nonspecific"
    assert battles["first_item_c_anchor_stats"]["unresolved_atomic"] == 0


def test_named_battle_prefix_is_retained_from_process_description():
    variants = module._anchor_variants("高平之战亲征中的现场稳定与组织")
    assert module._compact_text("高平之战") in variants
    assert module._compact_text("成都之围") in module._anchor_variants("成都之围反败为胜")
    assert module._compact_text("梁侯驿") in module._anchor_variants("梁侯驿伏击及断楚军粮道")


def test_shared_campaign_group_ref_is_not_forced_to_one_battle(tmp_path: Path):
    write_json(tmp_path / module.BATTLE_MANIFEST, {"record_count": 2})
    write_json(
        tmp_path / module.BATTLE_DIR / "demo-00.json",
        {"records": [
            {
                "war_event_id": "WAR-TEST-A",
                "dynasty": "测试朝",
                "canonical_label": "北门甲战",
                "campaign_group_ref": "GROUP-SHARED",
            },
            {
                "war_event_id": "WAR-TEST-B",
                "dynasty": "测试朝",
                "canonical_label": "南门乙战",
                "campaign_group_ref": "GROUP-SHARED",
            },
        ]},
    )
    setup_commander_manifest(tmp_path, {
        "profile_ref": "MIL-PROFILE-RULER",
        "person": "测试君主",
        "dynasty": "测试朝",
        "consumed_achievements": [{
            "campaign_ref": "GROUP-SHARED",
            "canonical_label": "中门决战",
            "campaign_tier": "A",
            "combat_difficulty": "D3",
        }],
    })
    write_first_item_c(
        tmp_path / module.FIRST_ITEM_C_SETTLEMENT,
        "# 第一项C\n\n### 1. 测试君主\n\n- **结算依据**：中门决战A/D3。\n",
    )

    battles, _ = module.build_indexes(tmp_path)
    anchor = battles["first_item_c_anchors"][0]
    assert anchor["status"] == "unresolved_atomic"
    assert anchor["battle_id"] is None


def test_negative_command_record_can_resolve_first_item_c_anchor(tmp_path: Path):
    write_json(tmp_path / module.BATTLE_MANIFEST, {"record_count": 1})
    write_json(
        tmp_path / module.BATTLE_DIR / "demo-00.json",
        {"records": [{
            "war_event_id": "WAR-TEST-NEGATIVE",
            "dynasty": "测试朝",
            "canonical_label": "高平会战",
            "campaign_tier": "A",
            "combat_difficulty": "D3",
        }]},
    )
    setup_commander_manifest(tmp_path, {
        "profile_ref": "MIL-PROFILE-RULER",
        "person": "测试君主",
        "dynasty": "测试朝",
        "negative_or_mixed_command_records": [{
            "person_command_result_ref": "PCR-TEST-NEGATIVE",
            "campaign_ref": "WAR-TEST-NEGATIVE",
            "canonical_label": "高平会战主力崩溃",
            "result_direction": "negative",
            "campaign_tier": "A",
            "combat_difficulty": "D3",
        }],
    })
    write_first_item_c(
        tmp_path / module.FIRST_ITEM_C_SETTLEMENT,
        "# 第一项C\n\n### 1. 测试君主\n\n- **结算依据**：高平会战主力崩溃A/D3。\n",
    )

    battles, _ = module.build_indexes(tmp_path)
    anchor = battles["first_item_c_anchors"][0]
    assert anchor["status"] == "resolved_unique"
    assert anchor["resolution_mode"] == "registry_ref"
    assert anchor["battle_id"] == "WAR-TEST-NEGATIVE"


def test_registry_fallback_disambiguates_only_structured_candidates(tmp_path: Path):
    write_json(tmp_path / module.BATTLE_MANIFEST, {"record_count": 2})
    write_json(
        tmp_path / module.BATTLE_DIR / "demo-00.json",
        {"records": [
            {
                "war_event_id": "WAR-TEST-GONGAN",
                "dynasty": "测试朝",
                "canonical_label": "公安方向作战",
            },
            {
                "war_event_id": "WAR-TEST-JIANGLING",
                "dynasty": "测试朝",
                "canonical_label": "江陵方向作战",
            },
        ]},
    )
    setup_commander_manifest(tmp_path, {
        "profile_ref": "MIL-PROFILE-RULER",
        "person": "测试君主",
        "dynasty": "测试朝",
        "consumed_achievements": [
            {
                "campaign_ref": "WAR-TEST-GONGAN",
                "canonical_label": "公安断粮击退雷彦恭、楚联军",
                "campaign_tier": "B",
                "combat_difficulty": "D2",
                "basis": "亲自屯兵公安并切断进攻军粮道，迫雷彦恭败退、楚军撤离，保住江陵核心。",
            },
            {
                "campaign_ref": "WAR-TEST-JIANGLING",
                "canonical_label": "坚守江陵迫三面围军撤退",
                "campaign_tier": "B",
                "combat_difficulty": "D2",
                "basis": "在三面压力下坚壁并求援，保持江陵直至敌军因雨疫和粮运失败撤退。",
            },
        ],
    })
    write_first_item_c(
        tmp_path / module.FIRST_ITEM_C_SETTLEMENT,
        "# 第一项C\n\n### 1. 测试君主\n\n- **结算依据**：断楚军粮道并迫退敌军B/D2。\n",
    )

    battles, _ = module.build_indexes(tmp_path)
    anchor = battles["first_item_c_anchors"][0]
    assert anchor["status"] == "resolved_unique"
    assert anchor["resolution_mode"] == "registry_ref"
    assert anchor["battle_id"] == "WAR-TEST-GONGAN"


def test_unbound_registry_evidence_stays_search_fallback(tmp_path: Path):
    write_json(tmp_path / module.BATTLE_MANIFEST, {"record_count": 1})
    write_json(
        tmp_path / module.BATTLE_DIR / "demo-00.json",
        {"records": [{
            "war_event_id": "WAR-TEST-UNRELATED",
            "dynasty": "测试朝",
            "canonical_label": "无关战役",
        }]},
    )
    setup_commander_manifest(tmp_path, {
        "profile_ref": "MIL-PROFILE-RULER",
        "person": "测试君主",
        "dynasty": "测试朝",
        "consumed_achievements": [{
            "campaign_ref": "PCR-UNBOUND-ONLY",
            "capability_episode_ref": "PCR-UNBOUND-ONLY",
            "canonical_label": "采纳直取大梁方案、亲率主力长驱并完成灭梁。",
            "campaign_tier": "S",
            "combat_difficulty": "D3",
            "basis": "本人作为实际总帅完成大梁终局。",
        }],
    })
    write_first_item_c(
        tmp_path / module.FIRST_ITEM_C_SETTLEMENT,
        "# 第一项C\n\n### 1. 测试君主\n\n- **结算依据**：大梁S/D3。\n",
    )

    battles, _ = module.build_indexes(tmp_path)
    anchor = battles["first_item_c_anchors"][0]
    assert anchor["status"] == "search_only_unbound_registry"
    assert anchor["resolution_mode"] == "unbound_registry"
    assert anchor["battle_id"] is None
    assert battles["first_item_c_anchor_stats"]["search_only_unbound_registry"] == 1
    assert battles["first_item_c_anchor_stats"]["unresolved_atomic"] == 0
    assert "大梁" not in battles["first_item_c_anchor_lookup"]


def test_exact_unbound_registry_evidence_beats_weak_routable_candidate(tmp_path: Path):
    write_json(tmp_path / module.BATTLE_MANIFEST, {"record_count": 1})
    write_json(
        tmp_path / module.BATTLE_DIR / "demo-00.json",
        {"records": [{
            "war_event_id": "WAR-TEST-WEAK-OTHER",
            "dynasty": "测试朝",
            "canonical_label": "北门粮道压迫并迫敌退却",
            "campaign_tier": "A",
            "combat_difficulty": "D3",
        }]},
    )
    setup_commander_manifest(
        tmp_path,
        {
            "profile_ref": "MIL-PROFILE-UNBOUND-FIRST",
            "person": "测试君主",
            "dynasty": "测试朝",
            "military_grade": "elite",
            "consumed_achievements": [
                {
                    "campaign_ref": "PCR-UNBOUND-EXACT",
                    "capability_episode_ref": "PCR-UNBOUND-EXACT",
                    "canonical_label": "北门断粮迫退敌军",
                    "campaign_tier": "A",
                    "combat_difficulty": "D3",
                    "basis": "北门断粮迫退敌军，完整闭合。",
                },
                {
                    "campaign_ref": "WAR-TEST-WEAK-OTHER",
                    "canonical_label": "北门粮道压迫并迫敌退却",
                    "campaign_tier": "A",
                    "combat_difficulty": "D3",
                    "basis": "另一结构化战役只与该说法部分相似。",
                },
            ],
        },
    )
    write_first_item_c(
        tmp_path / module.FIRST_ITEM_C_SETTLEMENT,
        "# 第一项C\n\n### 1. 测试君主\n\n- **结算依据**：北门断粮迫退敌军A/D3。\n",
    )

    battles, _ = module.build_indexes(tmp_path)
    anchor = battles["first_item_c_anchors"][0]
    assert anchor["status"] == "search_only_unbound_registry"
    assert anchor["resolution_mode"] == "unbound_registry"
    assert anchor["battle_id"] is None


def write_commander(tmp_path: Path) -> None:
    write_json(tmp_path / module.COMMANDER_MANIFEST, {"profile_count": 1})
    write_json(
        tmp_path / module.COMMANDER_DIR / "bucket-00.json",
        {
            "profiles": [{
                "profile_ref": "MIL-PROFILE-LINEAGE",
                "person_ref": "MIL-PER-LINEAGE",
                "person": "测试君主",
                "name_aliases": ["测试君主"],
                "dynasty": "测试朝",
                "dynasty_aliases": ["测试朝"],
                "military_grade": "elite",
                "consumed_achievements": [{
                    "campaign_ref": "PCR-UNBOUND-LINEAGE",
                    "capability_episode_ref": "PCR-UNBOUND-LINEAGE",
                    "canonical_label": "采纳直取北门方案并完成终局",
                    "campaign_tier": "A",
                    "combat_difficulty": "D3",
                    "basis": "测试君主亲率主力直取北门并完成终局。",
                    "source_refs": [
                        "测试史/卷777@REV777#攻北门守将开门出降",
                        "测试史/卷777@REV777#主力直取北门",
                    ],
                }],
            }]
        },
    )


def old_style_battle(battle_id: str, label: str, quotes: list[str]) -> dict:
    return {
        "war_event_id": battle_id,
        "dynasty": "测试朝",
        "canonical_label": label,
        "campaign_group_ref": "TEST-LINEAGE-CAMPAIGN",
        "source_lineage": {
            "source_card_ids": ["SRC-TEST-777-REV777#CARD-001"],
            "source_files": ["docs/source/volume-777.battle-adjudications.json"],
            "source_revision_refs": ["REV777"],
        },
        "source_quotes": quotes,
        "subject_phase_views": [{
            "phase_id": f"{battle_id}-P01",
            "evaluation_subject_phase": "测试朝主力 × 北门终局阶段",
            "actual_process": "主力倍道直取北门，守将开门出降。",
            "campaign_group_ref": "TEST-LINEAGE-CAMPAIGN",
        }],
    }


def test_first_item_c_unbound_registry_can_follow_unique_source_lineage(tmp_path: Path):
    write_json(tmp_path / module.BATTLE_MANIFEST, {"record_count": 1})
    write_json(
        tmp_path / module.BATTLE_DIR / "demo-00.json",
        {
            "records": [
                old_style_battle(
                    "WAR-TEST-LINEAGE",
                    "中军决战—倍道取北门—终局",
                    ["主力直取北门", "攻北门守将开门出降"],
                )
            ]
        },
    )
    write_commander(tmp_path)
    write_first_item_c(
        tmp_path / module.FIRST_ITEM_C_SETTLEMENT,
        "# 第一项C\n\n### 1. 测试君主\n\n- **结算依据**：统帅证据：直取北门A/D3形成核心前线峰值。\n",
    )

    battles, _ = module.build_indexes(tmp_path)

    anchor = battles["first_item_c_anchors"][0]
    assert anchor["status"] == "resolved_unique"
    assert anchor["resolution_mode"] == "registry_lineage"
    assert anchor["battle_id"] == "WAR-TEST-LINEAGE"
    assert battles["first_item_c_anchor_lookup"]["北门"] == "WAR-TEST-LINEAGE"
    assert battles["first_item_c_anchor_stats"]["resolved_registry_lineage"] == 1
    assert battles["first_item_c_anchor_stats"]["search_only_unbound_registry"] == 0


def test_first_item_c_source_lineage_refuses_equal_parent_candidates(tmp_path: Path):
    write_json(tmp_path / module.BATTLE_MANIFEST, {"record_count": 2})
    write_json(
        tmp_path / module.BATTLE_DIR / "demo-00.json",
        {
            "records": [
                old_style_battle(
                    "WAR-TEST-LINEAGE-A",
                    "北门终局甲",
                    ["主力直取北门", "攻北门守将开门出降"],
                ),
                old_style_battle(
                    "WAR-TEST-LINEAGE-B",
                    "北门终局乙",
                    ["主力直取北门", "攻北门守将开门出降"],
                ),
            ]
        },
    )
    write_commander(tmp_path)
    write_first_item_c(
        tmp_path / module.FIRST_ITEM_C_SETTLEMENT,
        "# 第一项C\n\n### 1. 测试君主\n\n- **结算依据**：统帅证据：直取北门A/D3形成核心前线峰值。\n",
    )

    battles, _ = module.build_indexes(tmp_path)

    anchor = battles["first_item_c_anchors"][0]
    assert anchor["status"] == "search_only_unbound_registry"
    assert anchor["resolution_mode"] == "unbound_registry"
    assert anchor["battle_id"] is None
    assert battles["first_item_c_anchor_stats"]["resolved_registry_lineage"] == 0
    assert battles["first_item_c_anchor_stats"]["search_only_unbound_registry"] == 1
