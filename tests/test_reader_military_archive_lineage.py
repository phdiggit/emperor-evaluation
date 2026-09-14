from __future__ import annotations

import importlib.util
import json
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "reader" / "build_military_archive.py"
spec = importlib.util.spec_from_file_location("build_military_archive_lineage", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def write_first_item_c(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


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
