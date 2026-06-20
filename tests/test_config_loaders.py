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
                "scope_type": "subitem",
                "scope_key": "第五项B",
                "positive_terms": ["任用"],
            },
            {
                "keyword_profile_id": "KW-I5B-LIUBANG",
                "subitem": "第五项B",
                "person": "刘邦",
                "scope_type": "person",
                "scope_key": "刘邦",
                "append_terms": ["三杰"],
            },
        ],
    )

    monkeypatch.setattr(config_loaders, "I5B_KEYWORD_PROFILES_PATH", config_path)

    assert [row["profile_id"] for row in config_loaders.get_i5b_keyword_profiles(scope="subitem")] == [
        "KW-I5B-BASE"
    ]
    assert [
        row["keyword_profile_id"] for row in config_loaders.get_i5b_keyword_profiles(person="刘邦")
    ] == ["KW-I5B-LIUBANG"]
    assert len(config_loaders.get_i5b_keyword_profiles(subitem="第五项B")) == 2
    assert config_loaders.get_i5b_keyword_profiles(subitem="第五项A") == []


def test_i5b_keyword_override_loader_filters_person_or_scope(
    tmp_path: Path, monkeypatch
) -> None:
    config_path = tmp_path / "第五项B_检索关键词补丁.json"
    write_json_array(
        config_path,
        [
            {
                "override_id": "KW-I5B-OVERRIDE-LB",
                "subitem": "第五项B",
                "scope_type": "person",
                "scope_key": "刘邦",
                "append_terms": ["萧何"],
            },
            {
                "override_id": "KW-I5B-OVERRIDE-HAN",
                "subitem": "第五项B",
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
    assert len(config_loaders.get_i5b_keyword_overrides(subitem="第五项B")) == 2
    assert config_loaders.get_i5b_keyword_overrides(subitem="第五项A") == []


def test_i5b_cluster_warning_loader_reads_repo_disabled_rules() -> None:
    rows = config_loaders.load_i5b_cluster_warning_rules()

    assert [row["rule_id"] for row in rows] == [
        "I5B-CLUSTER-WARN-ADJACENT-CONTAMINATION",
        "I5B-CLUSTER-WARN-SINGLE-EVIDENCE-LIMIT",
        "I5B-CLUSTER-WARN-SOURCE-REVIEW-REQUIRED",
        "I5B-CLUSTER-WARN-MIXED-POLARITY",
    ]
    assert all(row["enabled"] is False for row in rows)
    assert all(row["required_human_review"] is True for row in rows)


def test_i5b_cluster_warning_loader_filters_by_rule_id_warning_type_trigger_type_and_subitem(
    tmp_path: Path, monkeypatch
) -> None:
    config_path = tmp_path / "第五项B_证据簇裁判提示.json"
    write_json_array(
        config_path,
        [
            {
                "rule_id": "I5B-CLUSTER-WARN-ONE",
                "enabled": False,
                "subitem": "第五项B",
                "trigger_type": "trigger_terms",
                "warning_type": "adjacent_item_contamination",
                "required_human_review": True,
            },
            {
                "rule_id": "I5B-CLUSTER-WARN-TWO",
                "enabled": False,
                "subitem": "第五项B",
                "trigger_type": "cluster_structure",
                "warning_type": "single_evidence_limit",
                "required_human_review": True,
            },
        ],
    )
    monkeypatch.setattr(config_loaders, "I5B_CLUSTER_WARNING_RULES_PATH", config_path)

    assert (
        config_loaders.get_i5b_cluster_warning_rule("I5B-CLUSTER-WARN-ONE")["warning_type"]
        == "adjacent_item_contamination"
    )
    assert config_loaders.get_i5b_cluster_warning_rule("I5B-CLUSTER-WARN-MISSING") is None
    assert [
        row["rule_id"]
        for row in config_loaders.get_i5b_cluster_warning_rules(
            warning_type="single_evidence_limit"
        )
    ] == ["I5B-CLUSTER-WARN-TWO"]
    assert [
        row["rule_id"]
        for row in config_loaders.get_i5b_cluster_warning_rules(
            trigger_type="trigger_terms"
        )
    ] == ["I5B-CLUSTER-WARN-ONE"]
    assert len(config_loaders.get_i5b_cluster_warning_rules(subitem="第五项B")) == 2
    assert config_loaders.get_i5b_cluster_warning_rules(subitem="第五项A") == []


def test_i5b_cluster_warning_loader_reads_fresh_objects_without_cache_pollution(
    tmp_path: Path, monkeypatch
) -> None:
    config_path = tmp_path / "第五项B_证据簇裁判提示.json"
    write_json_array(
        config_path,
        [
            {
                "rule_id": "I5B-CLUSTER-WARN-FRESH",
                "enabled": False,
                "subitem": "第五项B",
                "trigger_type": "trigger_terms",
                "warning_type": "source_review_required",
                "required_human_review": True,
            }
        ],
    )
    monkeypatch.setattr(config_loaders, "I5B_CLUSTER_WARNING_RULES_PATH", config_path)

    rows = config_loaders.load_i5b_cluster_warning_rules()
    rows[0]["rule_id"] = "MUTATED"

    assert config_loaders.load_i5b_cluster_warning_rules()[0]["rule_id"] == "I5B-CLUSTER-WARN-FRESH"

    write_json_array(
        config_path,
        [
            {
                "rule_id": "I5B-CLUSTER-WARN-UPDATED",
                "enabled": False,
                "subitem": "第五项B",
                "trigger_type": "trigger_terms",
                "warning_type": "mixed_polarity_review",
                "required_human_review": True,
            }
        ],
    )

    assert config_loaders.load_i5b_cluster_warning_rules()[0]["rule_id"] == "I5B-CLUSTER-WARN-UPDATED"
