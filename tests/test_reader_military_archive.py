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


def test_military_archive_public_cost_labels_hide_internal_axis_codes():
    source = (Path(__file__).resolve().parents[1] / "reader" / "military-archive.js").read_text(encoding="utf-8")
    assert 'P:"人员损害"' in source
    assert 'S:"本土受损"' in source
    assert 'M:"动员投入"' in source
    assert 'A:"军事资产"' in source
    assert 'WC:"本阶段综合成本"' in source
    for leaked in ("人员损害 P", "本土受损 S", "动员投入 M", "军事资产 A", "本阶段成本 WC"):
        assert leaked not in source
