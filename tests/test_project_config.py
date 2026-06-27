from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

PROJECT_CONFIG_SPEC = importlib.util.spec_from_file_location(
    "validate.validate_project_config",
    ROOT / "scripts" / "validate" / "validate_project_config.py",
)
assert PROJECT_CONFIG_SPEC is not None
validate_project_config = importlib.util.module_from_spec(PROJECT_CONFIG_SPEC)
sys.modules[PROJECT_CONFIG_SPEC.name] = validate_project_config
assert PROJECT_CONFIG_SPEC.loader is not None
PROJECT_CONFIG_SPEC.loader.exec_module(validate_project_config)


def valid_groups() -> dict[str, dict[str, object]]:
    return {
        "three_pilot": {"label": "三人试点", "persons": ["李世民", "刘秀", "刘庄"]},
        "expanded_batch1": {"label": "扩展第一批", "persons": ["刘邦", "雍正", "朱元璋"]},
    }


def write_raw_config(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False) + "\n", encoding="utf-8")
    return path


def valid_payload(*, groups: dict[str, dict[str, object]] | None = None) -> dict[str, object]:
    return {
        "version": 2,
        "active_subitem": "第五项B",
        "default_person_group": "expanded_batch1",
        "person_groups": groups or valid_groups(),
        "outputs": {
            "matrix": True,
            "auto_adjudication": True,
            "review_entry": True,
            "subitem_details": True,
            "net_evidence": True,
            "evidence_indexes": True,
        },
    }


def test_validate_project_config_cli_passes_on_repo_data() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate" / "validate_project_config.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Project config validation passed." in result.stdout


def test_validate_project_config_accepts_minimal_valid_config(tmp_path: Path, project_config_writer) -> None:
    config_path = project_config_writer(tmp_path / "project_config.yml", groups=valid_groups())

    assert validate_project_config.validate(config_path) == []


def test_validate_project_config_rejects_yaml_anchor_alias_and_document_marker(tmp_path: Path) -> None:
    config_path = tmp_path / "project_config.yml"
    config_path.write_text(
        """
---
version: 2
active_subitem: 第五项B
default_person_group: three_pilot
person_groups:
  three_pilot: &trial
    label: 三人试点
    persons: [李世民]
  expanded_batch1: *trial
outputs:
  matrix: true
  auto_adjudication: true
  review_entry: true
  subitem_details: true
  net_evidence: true
  evidence_indexes: true
""",
        encoding="utf-8",
    )

    errors = validate_project_config.validate(config_path)

    assert any("document markers are not allowed" in error for error in errors)
    assert any("YAML anchors are not allowed" in error for error in errors)
    assert any("YAML aliases are not allowed" in error for error in errors)


def test_validate_project_config_reports_broken_yaml_without_traceback(tmp_path: Path) -> None:
    config_path = tmp_path / "project_config.yml"
    config_path.write_text("version: [\n", encoding="utf-8")

    errors = validate_project_config.validate(config_path)

    assert any("invalid YAML" in error for error in errors)


def test_validate_project_config_allows_existing_persons_ref_under_lists(
    tmp_path: Path, project_config_writer
) -> None:
    list_path = tmp_path / "data" / "configs" / "lists" / "第五项B_测试.yml"
    list_path.parent.mkdir(parents=True)
    list_path.write_text("- 甲\n", encoding="utf-8")
    groups = valid_groups()
    groups["three_pilot"] = {"label": "三人试点", "persons_ref": "data/configs/lists/第五项B_测试.yml"}
    config_path = project_config_writer(tmp_path / "project_config.yml", groups=groups)

    old_root = validate_project_config.ROOT
    validate_project_config.ROOT = tmp_path
    try:
        assert validate_project_config.validate(config_path) == []
    finally:
        validate_project_config.ROOT = old_root


def test_validate_project_config_rejects_persons_ref_outside_lists(tmp_path: Path, project_config_writer) -> None:
    groups = valid_groups()
    groups["three_pilot"] = {"label": "三人试点", "persons_ref": "data/configs/第五项B_测试.yml"}
    config_path = project_config_writer(tmp_path / "project_config.yml", groups=groups)

    errors = validate_project_config.validate(config_path)

    assert any("persons_ref must stay under data/configs/lists/" in error for error in errors)


def test_validate_project_config_rejects_candidate_pool(tmp_path: Path) -> None:
    payload = valid_payload()
    payload["candidate_pool"] = []
    config_path = write_raw_config(tmp_path / "project_config.yml", payload)

    errors = validate_project_config.validate(config_path)

    assert any("candidate_pool is not allowed" in error for error in errors)


def test_validate_project_config_rejects_review_warning_rules(tmp_path: Path) -> None:
    payload = valid_payload()
    payload["review_warning_rules"] = []
    config_path = write_raw_config(tmp_path / "project_config.yml", payload)

    errors = validate_project_config.validate(config_path)

    assert any("review_warning_rules is not allowed" in error for error in errors)


def test_validate_project_config_rejects_path_template(tmp_path: Path, project_config_writer) -> None:
    groups = valid_groups()
    groups["three_pilot"] = {
        "label": "三人试点",
        "persons": ["李世民"],
        "path_template": "exports/markdown_views/{person}.md",
    }
    config_path = project_config_writer(tmp_path / "project_config.yml", groups=groups)

    errors = validate_project_config.validate(config_path)

    assert any("path_template is not allowed" in error for error in errors)


def test_validate_project_config_rejects_group_subitem(tmp_path: Path, project_config_writer) -> None:
    groups = valid_groups()
    groups["three_pilot"] = {
        "label": "三人试点",
        "persons": ["李世民"],
        "subitem": "第五项B",
    }
    config_path = project_config_writer(tmp_path / "project_config.yml", groups=groups)

    errors = validate_project_config.validate(config_path)

    assert any("subitem is not allowed" in error for error in errors)


def test_validate_project_config_groups_only_allow_small_fields(tmp_path: Path, project_config_writer) -> None:
    groups = valid_groups()
    groups["three_pilot"] = {
        "label": "三人试点",
        "persons": ["李世民"],
        "group_type": "试点人物组",
        "note": "重复说明",
    }
    config_path = project_config_writer(tmp_path / "project_config.yml", groups=groups)

    errors = validate_project_config.validate(config_path)

    assert any("person_groups only allow label/persons/persons_ref" in error for error in errors)
    assert any("group_type is not allowed" in error for error in errors)
    assert any("note is not allowed" in error for error in errors)


def test_validate_project_config_accepts_net_evidence_output_override(
    tmp_path: Path, project_config_writer
) -> None:
    config_path = project_config_writer(
        tmp_path / "project_config.yml",
        groups=valid_groups(),
        outputs={
            "matrix": True,
            "auto_adjudication": True,
            "review_entry": True,
            "subitem_details": True,
            "net_evidence": {"enabled": True, "person_group_override": "three_pilot"},
            "evidence_indexes": True,
        },
    )

    assert validate_project_config.validate(config_path) == []


def test_validate_project_config_rejects_net_evidence_fake_group(tmp_path: Path, project_config_writer) -> None:
    groups = valid_groups()
    groups["net_evidence"] = {"label": "净证据导出目标", "persons_from_group": "three_pilot"}
    config_path = project_config_writer(tmp_path / "project_config.yml", groups=groups)

    errors = validate_project_config.validate(config_path)

    assert any("persons_from_group is not allowed" in error for error in errors)
