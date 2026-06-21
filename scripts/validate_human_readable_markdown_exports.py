from __future__ import annotations

import sys
from pathlib import Path

import config_loaders


ROOT = Path(__file__).resolve().parents[1]
INDEX_RELATIVE_PATH = Path("exports") / "markdown_views" / "第五项B三人自动结算草案.md"
DETAIL_FILENAME_TEMPLATE = "第五项B自动结算草案_{person}.md"
FORBIDDEN_MARKERS = ("<details", "<summary", "</details>", "……（共")
DETAIL_REQUIRED_MARKERS = (
    "[返回索引](./第五项B三人自动结算草案.md)",
    "### 证据簇自动结算",
    "### 自动特征",
    "### 自动结算结论",
    "**对象锚点**",
    "**相邻项剥离说明**",
)
OLD_CLUSTER_TABLE_MARKERS = ("| cluster_id |", "| polarity |", "| cluster_type |")
WARNING_HEADING = "## 人工复核提示（display-only）"
WARNING_MATCHED_FIELDS_LABEL = "**命中字段**"


def detail_relative_path(person: str) -> Path:
    return Path("exports") / "markdown_views" / DETAIL_FILENAME_TEMPLATE.format(person=person)


def detail_link(person: str) -> str:
    return f"[{person}详情](./{DETAIL_FILENAME_TEMPLATE.format(person=person)})"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def add_forbidden_marker_errors(path: Path, content: str, errors: list[str]) -> None:
    for marker in FORBIDDEN_MARKERS:
        if marker in content:
            errors.append(f"{path}: contains forbidden marker {marker!r}")


def existing_target_files(root: Path, targets: list[str]) -> list[Path]:
    files = [root / INDEX_RELATIVE_PATH]
    files.extend(root / detail_relative_path(person) for person in targets)
    return [path for path in files if path.exists()]


def existing_detail_files(root: Path, targets: list[str]) -> list[Path]:
    return [root / detail_relative_path(person) for person in targets if (root / detail_relative_path(person)).exists()]


def split_export_exists(root: Path, targets: list[str]) -> bool:
    index_path = root / INDEX_RELATIVE_PATH
    if index_path.exists():
        return "## 总览索引" in read_text(index_path)
    return bool(existing_detail_files(root, targets))


def validate_index(root: Path, targets: list[str], content: str, errors: list[str]) -> None:
    index_path = root / INDEX_RELATIVE_PATH
    if "## 总览索引" not in content:
        errors.append(f"{index_path}: missing required heading '## 总览索引'")

    for person in targets:
        link = detail_link(person)
        detail_path = root / detail_relative_path(person)
        if link not in content:
            errors.append(f"{index_path}: missing detail link {link}")
        if not detail_path.exists():
            errors.append(f"{index_path}: linked detail page does not exist: {detail_path}")


def validate_detail(path: Path, content: str, errors: list[str]) -> None:
    for marker in DETAIL_REQUIRED_MARKERS:
        if marker not in content:
            errors.append(f"{path}: missing required detail marker {marker!r}")

    if WARNING_HEADING in content and WARNING_MATCHED_FIELDS_LABEL not in content:
        errors.append(f"{path}: warning section is present but missing {WARNING_MATCHED_FIELDS_LABEL!r}")

    for marker in OLD_CLUSTER_TABLE_MARKERS:
        if marker in content:
            errors.append(f"{path}: contains old wide evidence cluster table marker {marker!r}")


def validate_exports(root: Path = ROOT, targets: list[str] | None = None) -> list[str]:
    resolved_targets = targets if targets is not None else list(config_loaders.get_i5b_trial_config().get("targets") or [])
    errors: list[str] = []
    existing_files = existing_target_files(root, resolved_targets)
    if not existing_files:
        return errors
    if not split_export_exists(root, resolved_targets):
        return errors

    for path in existing_files:
        add_forbidden_marker_errors(path, read_text(path), errors)

    index_path = root / INDEX_RELATIVE_PATH
    if not index_path.exists():
        errors.append(f"{index_path}: index page is missing while detail pages exist")
        return errors

    validate_index(root, resolved_targets, read_text(index_path), errors)
    for person in resolved_targets:
        detail_path = root / detail_relative_path(person)
        if detail_path.exists():
            validate_detail(detail_path, read_text(detail_path), errors)

    return errors


def main() -> int:
    targets = list(config_loaders.get_i5b_trial_config().get("targets") or [])
    existing_files = existing_target_files(ROOT, targets)
    if not existing_files or not split_export_exists(ROOT, targets):
        print("Human-readable Markdown export validation skipped: no I5B split export files found.")
        return 0

    errors = validate_exports(ROOT, targets)
    if errors:
        print("Human-readable Markdown export validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Human-readable Markdown export validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
