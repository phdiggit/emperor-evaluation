from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_LOADERS_SPEC = importlib.util.spec_from_file_location(
    "config_loaders",
    ROOT / "scripts" / "config_loaders.py",
)
assert CONFIG_LOADERS_SPEC is not None
config_loaders = importlib.util.module_from_spec(CONFIG_LOADERS_SPEC)
sys.modules[CONFIG_LOADERS_SPEC.name] = config_loaders
assert CONFIG_LOADERS_SPEC.loader is not None
CONFIG_LOADERS_SPEC.loader.exec_module(config_loaders)


def write_json_array(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")


def test_i5b_keyword_loaders_return_empty_when_configs_are_absent(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(config_loaders, "I5B_KEYWORD_PROFILES_PATH", tmp_path / "missing-profiles.json")
    monkeypatch.setattr(config_loaders, "I5B_KEYWORD_OVERRIDES_PATH", tmp_path / "missing-overrides.json")

    assert config_loaders.load_i5b_keyword_profiles() == []
    assert config_loaders.load_i5b_keyword_overrides() == []


def test_i5b_keyword_profile_loader_filters_common_scope_fields(
    tmp_path: Path, monkeypatch
) -> None:
    config_path = tmp_path / "第五项B_检索关键词基础.json"
    write_json_array(
        config_path,
        [
            {
                "profile_id": "KW-I5B-BASE",
                "subitem": "第五项B",
                "scope": "base",
                "terms": ["任用"],
            },
            {
                "keyword_profile_id": "KW-I5B-LIUBANG",
                "person": "刘邦",
                "scope": "person",
                "terms": ["三杰"],
            },
        ],
    )

    monkeypatch.setattr(config_loaders, "I5B_KEYWORD_PROFILES_PATH", config_path)

    assert [row["profile_id"] for row in config_loaders.get_i5b_keyword_profiles(scope="base")] == [
        "KW-I5B-BASE"
    ]
    assert [
        row["keyword_profile_id"] for row in config_loaders.get_i5b_keyword_profiles(person="刘邦")
    ] == ["KW-I5B-LIUBANG"]


def test_i5b_keyword_override_loader_filters_person_or_scope(
    tmp_path: Path, monkeypatch
) -> None:
    config_path = tmp_path / "第五项B_检索关键词补丁.json"
    write_json_array(
        config_path,
        [
            {
                "override_id": "KW-I5B-OVERRIDE-LB",
                "scope_type": "person",
                "scope_key": "刘邦",
                "append_terms": ["萧何"],
            },
            {
                "override_id": "KW-I5B-OVERRIDE-HAN",
                "scope_type": "dynasty",
                "scope_key": "汉",
                "append_terms": ["尚书"],
            },
        ],
    )

    monkeypatch.setattr(config_loaders, "I5B_KEYWORD_OVERRIDES_PATH", config_path)

    assert [
        row["override_id"] for row in config_loaders.get_i5b_keyword_overrides(person="刘邦")
    ] == ["KW-I5B-OVERRIDE-LB"]
    assert [
        row["override_id"] for row in config_loaders.get_i5b_keyword_overrides(scope="dynasty")
    ] == ["KW-I5B-OVERRIDE-HAN"]
