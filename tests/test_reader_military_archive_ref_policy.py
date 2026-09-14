from __future__ import annotations

import importlib.util
import json
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "reader" / "build_military_archive.py"
spec = importlib.util.spec_from_file_location("build_military_archive_ref_policy", MODULE_PATH)
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
