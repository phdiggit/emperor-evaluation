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

    battles, commanders = module.build_indexes(tmp_path)

    assert battles["record_count"] == 1
    assert battles["records"][0]["id"] == "WAR-TEST-1"
    assert battles["records"][0]["source"].endswith("demo-00.json")
    assert battles["result_ref_to_battle"]["PCR-TEST-1"] == "WAR-TEST-1"
    assert commanders["profile_count"] == 1
    assert commanders["records"][0]["profile_ref"] == "MIL-PROFILE-TEST"
    assert commanders["records"][0]["source"].endswith("bucket-00.json")


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
