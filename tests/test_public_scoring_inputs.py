from pathlib import Path

from emperor_v4.evaluation.battle_registry_store import load_battle_registry
from emperor_v4.evaluation.talent_registry_store import load_talent_registry


ROOT = Path(__file__).resolve().parents[1]


def test_public_military_registries_are_complete_and_unique() -> None:
    battles = load_battle_registry(ROOT / "docs/公共成果/军事/01-战役登记.json")
    assert len({row["war_event_id"] for row in battles["records"]}) == len(battles["records"])

    talents = load_talent_registry(ROOT / "docs/公共成果/军事/02-武将人才等级.json")
    assert talents["profile_count"] == len(talents["profiles"])
    assert len({row["person_ref"] for row in talents["profiles"]}) == talents["profile_count"]
