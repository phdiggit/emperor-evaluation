from __future__ import annotations

import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
config_loaders = importlib.import_module("shared.config_loaders")


def test_project_config_loader_reads_repo_config() -> None:
    config = config_loaders.load_project_config()

    assert config["version"] == 2
    assert config["active_subitem"] == "第五项B"
    assert config["default_person_group"] == "expanded_batch1"
    assert "person_groups" in config
    assert "outputs" in config
    assert "net_evidence" not in config["person_groups"]
    assert "candidate_pool" not in config
    assert "review_warning_rules" not in config
    assert config_loaders.get_i5b_active_person_targets() == ["刘邦", "雍正", "朱元璋"]
    assert config_loaders.get_i5b_trial_targets() == ["李世民", "刘秀", "刘庄"]
    assert config_loaders.get_i5b_expanded_batch1_targets() == ["刘邦", "雍正", "朱元璋"]
    assert [person for person, _path in config_loaders.get_i5b_net_evidence_targets()] == [
        "刘邦",
        "雍正",
        "朱元璋",
    ]
    assert [row["person"] for row in config_loaders.get_i5b_expanded_candidate_pool_rows()] == [
        "刘邦",
        "雍正",
        "朱元璋",
        "赵匡胤",
        "嬴政",
        "刘彻",
        "武则天",
    ]


def test_i5b_active_group_helpers_read_project_config(tmp_path: Path, monkeypatch, project_config_writer) -> None:
    config_path = project_config_writer(
        tmp_path / "project_config.yml",
        default_person_group="expanded_batch1",
        view_groups=[
            {
                "group_id": "第五项B_三人试点",
                "group_name": "三人试点",
                "group_type": "试点人物组",
                "subitem": "第五项B",
                "persons": ["甲", "乙"],
                "note": "测试",
            },
            {
                "group_id": "第五项B_扩展第一批",
                "group_name": "扩展第一批",
                "group_type": "扩展人物组",
                "subitem": "第五项B",
                "persons": ["丙"],
                "note": "测试",
            },
        ],
    )
    monkeypatch.setattr(config_loaders, "PROJECT_CONFIG_PATH", config_path)

    assert config_loaders.get_i5b_trial_targets() == ["甲", "乙"]
    assert config_loaders.get_i5b_expanded_batch1_targets() == ["丙"]
    assert config_loaders.get_i5b_active_person_targets() == ["丙"]
    assert config_loaders.get_i5b_net_evidence_targets() == [
        (
            "丙",
            config_loaders.ROOT
            / "exports"
            / "markdown_views"
            / "第五项B"
            / "人工审核"
            / "证据链"
            / "净证据池"
            / "第五项B_丙人工审核净证据池.md",
        )
    ]


def test_i5b_net_evidence_output_override_can_use_another_person_group(
    tmp_path: Path, monkeypatch, project_config_writer
) -> None:
    config_path = project_config_writer(
        tmp_path / "project_config.yml",
        default_person_group="expanded_batch1",
        groups={
            "three_pilot": {"label": "三人试点", "persons": ["甲"]},
            "expanded_batch1": {"label": "扩展第一批", "persons": ["乙"]},
        },
        outputs={
            "matrix": True,
            "auto_adjudication": True,
            "review_entry": True,
            "subitem_details": True,
            "net_evidence": {"enabled": True, "person_group_override": "three_pilot"},
            "evidence_indexes": True,
        },
    )
    monkeypatch.setattr(config_loaders, "PROJECT_CONFIG_PATH", config_path)

    assert config_loaders.get_i5b_active_person_targets() == ["乙"]
    assert [person for person, _path in config_loaders.get_i5b_net_evidence_targets()] == ["甲"]


def test_i5b_cluster_warning_loader_filters_by_rule_id_warning_type_trigger_type_and_subitem(monkeypatch) -> None:
    monkeypatch.setattr(
        config_loaders,
        "default_i5b_review_warning_rules",
        lambda: [
            {
                "rule_id": "I5B-CLUSTER-WARN-ONE",
                "enabled": False,
                "display_only": True,
                "subitem": "第五项B",
                "trigger_type": "trigger_terms",
                "warning_type": "adjacent_item_contamination",
                "required_human_review": True,
            },
            {
                "rule_id": "I5B-CLUSTER-WARN-TWO",
                "enabled": False,
                "display_only": True,
                "subitem": "第五项B",
                "trigger_type": "cluster_structure",
                "warning_type": "single_evidence_limit",
                "required_human_review": True,
            },
        ],
    )

    assert (
        config_loaders.get_i5b_cluster_warning_rule("I5B-CLUSTER-WARN-ONE")["warning_type"]
        == "adjacent_item_contamination"
    )
    assert config_loaders.get_i5b_cluster_warning_rule("I5B-CLUSTER-WARN-MISSING") is None
    assert [
        row["rule_id"]
        for row in config_loaders.get_i5b_cluster_warning_rules(warning_type="single_evidence_limit")
    ] == ["I5B-CLUSTER-WARN-TWO"]
    assert [
        row["rule_id"]
        for row in config_loaders.get_i5b_cluster_warning_rules(trigger_type="trigger_terms")
    ] == ["I5B-CLUSTER-WARN-ONE"]
    assert len(config_loaders.get_i5b_cluster_warning_rules(subitem="第五项B")) == 2
    assert config_loaders.get_i5b_cluster_warning_rules(subitem="第五项A") == []


def test_i5b_runtime_default_sections_return_fresh_objects_without_cache_pollution(monkeypatch) -> None:
    monkeypatch.setattr(
        config_loaders,
        "default_i5b_review_warning_rules",
        lambda: [
            {
                "rule_id": "I5B-CLUSTER-WARN-FRESH",
                "enabled": False,
                "display_only": True,
                "subitem": "第五项B",
                "trigger_type": "trigger_terms",
                "warning_type": "source_review_required",
                "required_human_review": True,
            }
        ],
    )

    rows = config_loaders.load_i5b_cluster_warning_rules()
    rows[0]["rule_id"] = "MUTATED"

    assert config_loaders.load_i5b_cluster_warning_rules()[0]["rule_id"] == "I5B-CLUSTER-WARN-FRESH"
