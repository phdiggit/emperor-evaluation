from __future__ import annotations

import importlib.util
import json
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "reader" / "build_military_archive.py"
spec = importlib.util.spec_from_file_location("build_military_archive_unbound_registry", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def write_first_item_c(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def setup_commander_manifest(tmp_path: Path, profile: dict) -> None:
    write_json(tmp_path / module.COMMANDER_MANIFEST, {"profile_count": 1})
    write_json(tmp_path / module.COMMANDER_DIR / "bucket-00.json", {"profiles": [profile]})


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
