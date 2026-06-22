from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

VALIDATE_CONFIG_COMMENTS_SPEC = importlib.util.spec_from_file_location(
    "validate_config_comments",
    ROOT / "scripts" / "validate" / "validate_config_comments.py",
)
assert VALIDATE_CONFIG_COMMENTS_SPEC is not None
validate_config_comments = importlib.util.module_from_spec(VALIDATE_CONFIG_COMMENTS_SPEC)
assert VALIDATE_CONFIG_COMMENTS_SPEC.loader is not None
VALIDATE_CONFIG_COMMENTS_SPEC.loader.exec_module(validate_config_comments)

CONFIG_LOADERS_SPEC = importlib.util.spec_from_file_location(
    "config_loaders",
    ROOT / "scripts" / "config_loaders.py",
)
assert CONFIG_LOADERS_SPEC is not None
config_loaders = importlib.util.module_from_spec(CONFIG_LOADERS_SPEC)
sys.modules[CONFIG_LOADERS_SPEC.name] = config_loaders
assert CONFIG_LOADERS_SPEC.loader is not None
CONFIG_LOADERS_SPEC.loader.exec_module(config_loaders)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sample_config() -> dict[str, object]:
    return {
        "field_labels": {"evidence_id": "证据ID"},
        "value_labels": {"source_verified": "已回源"},
        "view_profiles": {
            "human_review": {
                "hidden_fields": ["evidence_id"],
                "table_fields": {
                    "net_evidence_cards": ["person"],
                    "auto_adjudication_matrix": ["person"],
                },
            }
        },
        "list_render_policy": {
            "field_overrides": {
                "quote_context": {
                    "strategy": "appendix_link",
                }
            }
        },
        "table_render_policy": {"max_inline_table_cell_chars": 72},
    }


def write_comment(
    *,
    root_path: Path,
    configs_dir: Path,
    comments_dir: Path,
    config_path: Path,
    payload: object,
    omit_field: str | None = None,
    target_config: str | None = None,
    field_overrides: dict[str, str] | None = None,
) -> Path:
    fields = {
        path: f"{path} 的中文说明。"
        for path in sorted(validate_config_comments.collect_config_paths(payload))
        if path != omit_field
    }
    if field_overrides:
        fields.update(field_overrides)

    comment_path = validate_config_comments.expected_comment_path(
        config_path,
        configs_dir=configs_dir,
        comments_dir=comments_dir,
    )
    write_json(
        comment_path,
        {
            "$schema_note": "本文件为配置说明，不参与业务逻辑加载。",
            "$target_config": target_config
            if target_config is not None
            else config_path.relative_to(root_path).as_posix(),
            "$description": "测试配置文件的整体中文说明。",
            "$fields": fields,
            "$value_notes": {},
            "$safe_edit_notes": {},
        },
    )
    return comment_path


def validate_tmp(root_path: Path) -> list[str]:
    configs_dir = root_path / "data" / "configs"
    return validate_config_comments.validate(
        configs_dir=configs_dir,
        comments_dir=configs_dir / "配置说明",
        root_path=root_path,
    )


def test_validate_config_comments_cli_passes_on_repo_data() -> None:
    assert validate_config_comments.validate() == []


def test_each_real_repo_config_has_comments_file() -> None:
    for config_path in validate_config_comments.iter_real_config_paths():
        assert validate_config_comments.expected_comment_path(config_path).exists()


def test_validate_config_comments_rejects_missing_comments_file(tmp_path: Path) -> None:
    config_path = tmp_path / "data" / "configs" / "视图配置" / "sample.json"
    write_json(config_path, {"name": "值"})

    errors = validate_tmp(tmp_path)

    assert any("missing comments file" in error for error in errors)


def test_validate_config_comments_rejects_missing_top_level_key_description(tmp_path: Path) -> None:
    configs_dir = tmp_path / "data" / "configs"
    comments_dir = configs_dir / "配置说明"
    config_path = configs_dir / "视图配置" / "sample.json"
    payload = {"name": "值"}
    write_json(config_path, payload)
    write_comment(
        root_path=tmp_path,
        configs_dir=configs_dir,
        comments_dir=comments_dir,
        config_path=config_path,
        payload=payload,
        omit_field="name",
    )

    errors = validate_tmp(tmp_path)

    assert any("missing Chinese description for config key name" in error for error in errors)


def test_validate_config_comments_rejects_missing_important_nested_key_description(tmp_path: Path) -> None:
    configs_dir = tmp_path / "data" / "configs"
    comments_dir = configs_dir / "配置说明"
    config_path = configs_dir / "导出展示配置" / "sample.json"
    payload = sample_config()
    write_json(config_path, payload)
    write_comment(
        root_path=tmp_path,
        configs_dir=configs_dir,
        comments_dir=comments_dir,
        config_path=config_path,
        payload=payload,
        omit_field="view_profiles.human_review.table_fields.net_evidence_cards",
    )

    errors = validate_tmp(tmp_path)

    assert any("net_evidence_cards" in error for error in errors)


def test_validate_config_comments_rejects_non_chinese_description(tmp_path: Path) -> None:
    configs_dir = tmp_path / "data" / "configs"
    comments_dir = configs_dir / "配置说明"
    config_path = configs_dir / "视图配置" / "sample.json"
    payload = {"name": "值"}
    write_json(config_path, payload)
    write_comment(
        root_path=tmp_path,
        configs_dir=configs_dir,
        comments_dir=comments_dir,
        config_path=config_path,
        payload=payload,
        field_overrides={"name": "plain English only"},
    )

    errors = validate_tmp(tmp_path)

    assert any("$fields.name must contain Chinese description text" in error for error in errors)


def test_validate_config_comments_rejects_wrong_target_config(tmp_path: Path) -> None:
    configs_dir = tmp_path / "data" / "configs"
    comments_dir = configs_dir / "配置说明"
    config_path = configs_dir / "视图配置" / "sample.json"
    payload = {"name": "值"}
    write_json(config_path, payload)
    write_comment(
        root_path=tmp_path,
        configs_dir=configs_dir,
        comments_dir=comments_dir,
        config_path=config_path,
        payload=payload,
        target_config="data/configs/视图配置/missing.json",
    )

    errors = validate_tmp(tmp_path)

    assert any("$target_config must be" in error for error in errors)


def test_validate_config_comments_rejects_nonexistent_config_key_reference(tmp_path: Path) -> None:
    configs_dir = tmp_path / "data" / "configs"
    comments_dir = configs_dir / "配置说明"
    config_path = configs_dir / "视图配置" / "sample.json"
    payload = {"name": "值"}
    write_json(config_path, payload)
    write_comment(
        root_path=tmp_path,
        configs_dir=configs_dir,
        comments_dir=comments_dir,
        config_path=config_path,
        payload=payload,
        field_overrides={"ghost": "不存在配置项的中文说明。"},
    )

    errors = validate_tmp(tmp_path)

    assert any("$fields.ghost does not match any key in target config" in error for error in errors)


def test_comments_directory_and_comment_files_are_not_real_configs(tmp_path: Path) -> None:
    configs_dir = tmp_path / "data" / "configs"
    comments_dir = configs_dir / "配置说明"
    config_path = configs_dir / "视图配置" / "sample.json"
    payload = {"name": "值"}
    write_json(config_path, payload)
    write_comment(
        root_path=tmp_path,
        configs_dir=configs_dir,
        comments_dir=comments_dir,
        config_path=config_path,
        payload=payload,
    )

    paths = validate_config_comments.iter_real_config_paths(configs_dir)

    assert paths == [config_path]


def test_config_loader_paths_do_not_point_to_comments_files() -> None:
    loader_paths = [
        config_loaders.I5B_PERSON_POOL_PATH,
        config_loaders.I5B_VIEW_GROUPS_PATH,
        config_loaders.I5B_KEYWORD_PROFILES_PATH,
        config_loaders.I5B_KEYWORD_OVERRIDES_PATH,
        config_loaders.I5B_CLUSTER_WARNING_RULES_PATH,
    ]

    assert all("配置说明" not in path.parts for path in loader_paths)
    assert all(not path.name.endswith(".comments.json") for path in loader_paths)


def test_markdown_view_comments_include_human_review_table_fields() -> None:
    comment_path = (
        ROOT
        / "data"
        / "configs"
        / "配置说明"
        / "导出展示配置__第五项B_markdown_view.comments.json"
    )
    payload = json.loads(comment_path.read_text(encoding="utf-8"))

    assert "view_profiles.human_review.table_fields.net_evidence_cards" in payload["$fields"]
    assert "view_profiles.human_review.table_fields.auto_adjudication_matrix" in payload["$fields"]
