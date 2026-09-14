from __future__ import annotations

import importlib.util
import json
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "reader" / "build_military_archive.py"
MILITARY_HTML = Path(__file__).resolve().parents[1] / "reader" / "military.html"
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
            "profiles": [
                {
                    "profile_ref": "MIL-PROFILE-TEST",
                    "person_ref": "MIL-PER-TEST",
                    "person": "测试将领",
                    "dynasty": "测试朝",
                    "military_grade": "elite",
                    "actor_ref_aliases": ["PERSON-TEST"],
                }
            ]
        },
    )


def test_military_archive_indexes_point_to_canonical_shards(tmp_path: Path):
    write_json(tmp_path / module.BATTLE_MANIFEST, {"record_count": 1})
    write_json(
        tmp_path / module.BATTLE_DIR / "demo-00.json",
        {
            "records": [
                {
                    "war_event_id": "WAR-TEST-1",
                    "dynasty": "测试朝",
                    "canonical_label": "测试战役",
                    "period": {"start": "1", "end": "2"},
                    "campaign_tier": "A",
                    "combat_difficulty": "D3",
                    "result_direction": "positive",
                    "members": [
                        {
                            "actor_name": "测试将领",
                            "person_command_result": [{"result_ref": "PCR-TEST-1"}],
                        }
                    ],
                }
            ]
        },
    )
    minimal_commander(tmp_path)

    battles, commanders = module.build_indexes(tmp_path)

    assert battles["record_count"] == 1
    assert battles["records"][0]["id"] == "WAR-TEST-1"
    assert battles["records"][0]["source"].endswith("demo-00.json")
    assert battles["result_ref_to_battle"]["PCR-TEST-1"] == "WAR-TEST-1"
    assert commanders["profile_count"] == 1
    assert commanders["records"][0]["profile_ref"] == "MIL-PROFILE-TEST"
    assert commanders["records"][0]["source"].endswith("bucket-00.json")


def test_first_item_c_anchor_binds_only_unique_matching_battle(tmp_path: Path):
    write_json(tmp_path / module.BATTLE_MANIFEST, {"record_count": 2})
    write_json(
        tmp_path / module.BATTLE_DIR / "demo-00.json",
        {
            "records": [
                {
                    "war_event_id": "WAR-TEST-NORTH-GATE",
                    "dynasty": "测试朝",
                    "canonical_label": "测试君主亲率主力完成北门决战",
                    "observable_result": "北门方向终局闭合。",
                    "campaign_tier": "A",
                    "combat_difficulty": "D3",
                    "members": [{
                        "actor_name": "测试君主",
                        "person_command_result": [{
                            "result_ref": "PCR-TEST-NORTH-GATE",
                            "result_label": "北门决战",
                            "result_tier": "A",
                            "combat_difficulty": "D3",
                        }],
                    }],
                },
                {
                    "war_event_id": "WAR-TEST-SOUTH-GATE",
                    "dynasty": "测试朝",
                    "canonical_label": "另一人物完成南门战役",
                    "campaign_tier": "A",
                    "combat_difficulty": "D3",
                    "members": [{
                        "actor_name": "另一人物",
                        "person_command_result": [{
                            "result_ref": "PCR-TEST-SOUTH-GATE",
                            "result_label": "南门战役",
                            "result_tier": "A",
                            "combat_difficulty": "D3",
                        }],
                    }],
                },
            ]
        },
    )
    minimal_commander(tmp_path)
    write_first_item_c(
        tmp_path / module.FIRST_ITEM_C_SETTLEMENT,
        "# 第一项C\n\n### 1. 测试君主\n\n- **结算依据**：统帅证据：第一项主链内已有北门决战A/D3，形成独立复核。\n",
    )

    battles, _ = module.build_indexes(tmp_path)

    anchors = battles["first_item_c_anchors"]
    assert len(anchors) == 1
    assert anchors[0]["status"] == "resolved_unique"
    assert anchors[0]["battle_id"] == "WAR-TEST-NORTH-GATE"
    assert battles["first_item_c_anchor_lookup"]["北门决战"] == "WAR-TEST-NORTH-GATE"


def test_first_item_c_anchor_keeps_ambiguous_match_out_of_direct_lookup(tmp_path: Path):
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
        "# 第一项C\n\n### 1. 测试君主\n\n- **结算依据**：统帅证据：已有北门决战A/D3。\n",
    )

    battles, _ = module.build_indexes(tmp_path)

    anchor = battles["first_item_c_anchors"][0]
    assert anchor["status"] == "ambiguous"
    assert anchor["battle_id"] is None
    assert "北门决战" not in battles["first_item_c_anchor_lookup"]


def test_military_archive_does_not_copy_full_adjudication_text(tmp_path: Path):
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


def test_military_page_upgrades_resolved_first_item_search_to_battle_id():
    html = MILITARY_HTML.read_text(encoding="utf-8")
    assert "first_item_c_anchor_lookup" in html
    assert 'location.replace(`#battle=${encodeURIComponent(battleId)}`)' in html
    assert "保留搜索回退" in html
