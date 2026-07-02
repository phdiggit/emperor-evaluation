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
    assert config["default_person_group"] == "typical"
    assert "person_groups" in config
    assert "outputs" in config
    assert "derived_output_group" not in config["person_groups"]
    assert "candidate_pool" not in config
    assert "review_warning_rules" not in config
    assert config_loaders.get_i5b_active_person_targets() == config["person_groups"]["typical"]["persons"]
    assert config_loaders.get_i5b_trial_targets() == ["李世民", "刘秀", "刘庄"]
    assert "胤禛" in config["person_groups"]["typical"]["persons"]
    assert "雍正" not in config["person_groups"]["typical"]["persons"]
    all_persons = config_loaders.get_i5b_group_persons("all")
    assert all_persons is not None
    assert all_persons[:5] == ["嬴政", "刘邦", "刘恒", "刘彻", "刘询"]
    assert "铁木真" in all_persons
    assert "成吉思汗" not in all_persons
    assert "胤禛" in all_persons
    assert "雍正" not in all_persons
    assert "慈禧" in all_persons
    assert "洪秀全" in all_persons


def test_i5b_active_group_helpers_read_project_config(tmp_path: Path, monkeypatch, project_config_writer) -> None:
    config_path = project_config_writer(
        tmp_path / "project_config.yml",
        default_person_group="custom_review_pool",
        groups={
            "three_pilot": {"label": "三人试点", "persons": ["甲", "乙"]},
            "custom_review_pool": {"label": "自定义复核池", "persons": ["丙"]},
        },
    )
    monkeypatch.setattr(config_loaders, "PROJECT_CONFIG_PATH", config_path)

    assert config_loaders.get_i5b_trial_targets() == ["甲", "乙"]
    assert config_loaders.get_i5b_active_person_targets() == ["丙"]


def test_i5b_custom_review_pool_key_drives_active_workflow(
    tmp_path: Path, monkeypatch, project_config_writer
) -> None:
    config_path = project_config_writer(
        tmp_path / "project_config.yml",
        default_person_group="custom_review_pool",
        groups={
            "custom_review_pool": {"label": "自定义复核池", "persons": ["甲", "乙"]},
            "another_review_pool": {"label": "另一个复核池", "persons": ["丙"]},
            "unused_review_pool": {"label": "未选中复核池", "persons": ["丁"]},
        },
        outputs={
            "matrix": True,
            "review_entry": True,
            "subitem_details": True,
            "evidence_indexes": True,
        },
    )
    monkeypatch.setattr(config_loaders, "PROJECT_CONFIG_PATH", config_path)

    workflow_config = config_loaders.get_i5b_active_workflow_config()

    assert workflow_config["default_person_group"] == "custom_review_pool"
    assert workflow_config["group"] == "custom_review_pool"
    assert workflow_config["group_label"] == "自定义复核池"
    assert workflow_config["targets"] == ["甲", "乙"]
    assert config_loaders.get_i5b_group("another_review_pool")["persons"] == ["丙"]


def test_i5b_custom_group_key_supports_persons_ref(tmp_path: Path, monkeypatch, project_config_writer) -> None:
    list_path = tmp_path / "data" / "configs" / "lists" / "custom_review_pool.yml"
    list_path.parent.mkdir(parents=True)
    list_path.write_text("- 甲\n- 乙\n", encoding="utf-8")
    config_path = project_config_writer(
        tmp_path / "project_config.yml",
        default_person_group="custom_review_pool",
        groups={
            "custom_review_pool": {
                "label": "自定义复核池",
                "persons_ref": "data/configs/lists/custom_review_pool.yml",
            },
        },
    )
    monkeypatch.setattr(config_loaders, "ROOT", tmp_path)
    monkeypatch.setattr(config_loaders, "PROJECT_CONFIG_PATH", config_path)

    assert config_loaders.get_i5b_active_person_targets() == ["甲", "乙"]
