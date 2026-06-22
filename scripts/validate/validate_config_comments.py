from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONFIGS_DIR = ROOT / "data" / "configs"
COMMENTS_DIR_NAME = "配置说明"
COMMENTS_DIR = CONFIGS_DIR / COMMENTS_DIR_NAME
COMMENT_SUFFIX = ".comments.json"
NOTE_SECTIONS = ("$fields", "$value_notes", "$safe_edit_notes")
CHINESE_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
IMPORTANT_CONFIG_PATHS = (
    "field_labels.evidence_id",
    "value_labels.source_verified",
    "view_profiles.human_review.hidden_fields",
    "view_profiles.human_review.table_fields.net_evidence_cards",
    "view_profiles.human_review.table_fields.auto_adjudication_matrix",
    "list_render_policy.field_overrides.quote_context.strategy",
    "table_render_policy.max_inline_table_cell_chars",
)


def to_repo_path(path: Path, *, root_path: Path = ROOT) -> str:
    return path.relative_to(root_path).as_posix()


def expected_comment_path(
    config_path: Path,
    *,
    configs_dir: Path = CONFIGS_DIR,
    comments_dir: Path = COMMENTS_DIR,
) -> Path:
    relative = config_path.relative_to(configs_dir)
    flattened = "__".join(relative.with_suffix("").parts)
    return comments_dir / f"{flattened}{COMMENT_SUFFIX}"


def iter_real_config_paths(configs_dir: Path = CONFIGS_DIR) -> list[Path]:
    if not configs_dir.exists():
        return []
    paths: list[Path] = []
    for path in sorted(configs_dir.rglob("*.json")):
        try:
            relative_parts = path.relative_to(configs_dir).parts
        except ValueError:
            continue
        if COMMENTS_DIR_NAME in relative_parts or path.name.endswith(COMMENT_SUFFIX):
            continue
        paths.append(path)
    return paths


def load_json(path: Path) -> tuple[Any | None, list[str]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as exc:
        return None, [f"{path}: line {exc.lineno}: invalid JSON ({exc.msg})"]


def is_chinese_text(value: object) -> bool:
    return isinstance(value, str) and bool(CHINESE_PATTERN.search(value))


def collect_config_paths(value: Any, prefix: str = "") -> set[str]:
    paths: set[str] = set()

    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{prefix}.{key_text}" if prefix else key_text
            paths.add(child_path)
            paths.update(collect_config_paths(child, child_path))
        return paths

    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                paths.update(collect_config_paths(item, prefix))
            elif isinstance(item, list):
                paths.update(collect_config_paths(item, prefix))
        return paths

    return paths


def path_exists(value: Any, dotted_path: str) -> bool:
    parts = dotted_path.split(".") if dotted_path else []
    return _path_exists(value, parts)


def _path_exists(value: Any, parts: list[str]) -> bool:
    if not parts:
        return True

    head, *tail = parts
    if isinstance(value, dict):
        if head not in value:
            return False
        return _path_exists(value[head], tail)

    if isinstance(value, list):
        return any(_path_exists(item, parts) for item in value)

    return False


def validate_note_map(
    *,
    comment_path: Path,
    section_name: str,
    section_value: object,
    config_payload: Any,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(section_value, dict):
        return [f"{comment_path}: {section_name} must be a JSON object"]

    for key, value in sorted(section_value.items()):
        if not isinstance(key, str):
            errors.append(f"{comment_path}: {section_name} contains a non-string key")
            continue
        if not key.startswith("$") and not path_exists(config_payload, key):
            errors.append(f"{comment_path}: {section_name}.{key} does not match any key in target config")
        if not is_chinese_text(value):
            errors.append(f"{comment_path}: {section_name}.{key} must contain Chinese description text")

    return errors


def validate_comment_payload(
    comment_path: Path,
    config_path: Path,
    config_payload: Any,
    *,
    root_path: Path = ROOT,
) -> list[str]:
    errors: list[str] = []
    comment_payload, load_errors = load_json(comment_path)
    if load_errors:
        return load_errors
    if not isinstance(comment_payload, dict):
        return [f"{comment_path}: comment file must contain a top-level JSON object"]

    expected_target = to_repo_path(config_path, root_path=root_path)
    actual_target = comment_payload.get("$target_config")
    if actual_target != expected_target:
        errors.append(
            f"{comment_path}: $target_config must be {expected_target!r}, got {actual_target!r}"
        )

    for scalar_key in ("$schema_note", "$description"):
        if not is_chinese_text(comment_payload.get(scalar_key)):
            errors.append(f"{comment_path}: {scalar_key} must contain Chinese description text")

    fields = comment_payload.get("$fields")
    if not isinstance(fields, dict):
        errors.append(f"{comment_path}: $fields must be a JSON object")
        fields = {}

    for section_name in ("$value_notes", "$safe_edit_notes"):
        if section_name in comment_payload:
            errors.extend(
                validate_note_map(
                    comment_path=comment_path,
                    section_name=section_name,
                    section_value=comment_payload[section_name],
                    config_payload=config_payload,
                )
            )

    errors.extend(
        validate_note_map(
            comment_path=comment_path,
            section_name="$fields",
            section_value=fields,
            config_payload=config_payload,
        )
    )

    documented_paths = set(fields)
    for section_name in ("$value_notes", "$safe_edit_notes"):
        section = comment_payload.get(section_name)
        if isinstance(section, dict):
            documented_paths.update(str(key) for key in section if isinstance(key, str))

    config_paths = collect_config_paths(config_payload)
    missing_paths = sorted(path for path in config_paths if path not in documented_paths)
    for missing_path in missing_paths:
        errors.append(f"{comment_path}: missing Chinese description for config key {missing_path}")

    for important_path in IMPORTANT_CONFIG_PATHS:
        if path_exists(config_payload, important_path) and important_path not in documented_paths:
            errors.append(f"{comment_path}: missing important config description for {important_path}")

    return errors


def validate(
    *,
    configs_dir: Path = CONFIGS_DIR,
    comments_dir: Path = COMMENTS_DIR,
    root_path: Path = ROOT,
) -> list[str]:
    errors: list[str] = []
    config_paths = iter_real_config_paths(configs_dir)
    expected_comments = {
        expected_comment_path(path, configs_dir=configs_dir, comments_dir=comments_dir): path
        for path in config_paths
    }

    for config_path in config_paths:
        comment_path = expected_comment_path(config_path, configs_dir=configs_dir, comments_dir=comments_dir)
        if not comment_path.exists():
            errors.append(f"{config_path}: missing comments file {comment_path}")
            continue

        config_payload, load_errors = load_json(config_path)
        if load_errors:
            errors.extend(load_errors)
            continue
        errors.extend(validate_comment_payload(comment_path, config_path, config_payload, root_path=root_path))

    if comments_dir.exists():
        for comment_path in sorted(comments_dir.rglob("*.json")):
            if comment_path not in expected_comments:
                comment_payload, load_errors = load_json(comment_path)
                if load_errors:
                    errors.extend(load_errors)
                    continue
                target = comment_payload.get("$target_config") if isinstance(comment_payload, dict) else None
                errors.append(
                    f"{comment_path}: unexpected comments file for target {target!r}; "
                    "use the stable flattened comments path"
                )

    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(error)
        return 1

    print("Config comments validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
