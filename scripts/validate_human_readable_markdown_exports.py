from __future__ import annotations

import sys
from pathlib import Path

import config_loaders


ROOT = Path(__file__).resolve().parents[1]
I5B_EXPORT_RELATIVE_ROOT = Path("exports") / "markdown_views" / "第五项B"
AUTO_DRAFT_RELATIVE_DIR = I5B_EXPORT_RELATIVE_ROOT / "自动结算草案"
DETAIL_RELATIVE_DIR = AUTO_DRAFT_RELATIVE_DIR / "人物详情"
APPENDIX_RELATIVE_DIR = AUTO_DRAFT_RELATIVE_DIR / "附录"
INDEX_RELATIVE_PATH = AUTO_DRAFT_RELATIVE_DIR / "第五项B三人自动结算草案.md"
DETAIL_FILENAME_TEMPLATE = "{person}.md"
FORBIDDEN_MARKERS = ("<details", "<summary", "</details>", "……（共")
DETAIL_REQUIRED_MARKERS = (
    "[返回索引](../第五项B三人自动结算草案.md)",
    "### 证据簇自动结算",
    "### 自动特征",
    "### 自动结算结论",
    "**对象锚点**",
    "**相邻项剥离说明**",
)
OLD_CLUSTER_TABLE_MARKERS = ("| cluster_id |", "| polarity |", "| cluster_type |")
OLD_AUTO_FEATURE_TABLE_MARKERS = ("| field | value |", "| positive_cluster_ids |", "| negative_cluster_ids |")
WARNING_HEADING = "## 人工复核提示（display-only）"
WARNING_MATCHED_FIELDS_LABEL = "**命中字段**"
LEGACY_FLAT_RELATIVE_PATHS = (
    Path("exports") / "markdown_views" / "第五项B三人自动结算草案.md",
    Path("exports") / "markdown_views" / "第五项B自动结算规则敏感点清单.md",
    Path("exports") / "markdown_views" / "第五项B三人正式定档落地表.md",
    Path("exports") / "markdown_views" / "第五项B评分标尺与档位映射草案.md",
    Path("exports") / "markdown_views" / "第五项B三人试点内部闭环收尾.md",
)


def detail_relative_path(person: str) -> Path:
    return DETAIL_RELATIVE_DIR / DETAIL_FILENAME_TEMPLATE.format(person=person)


def detail_link(person: str) -> str:
    return f"[{person}详情](./人物详情/{DETAIL_FILENAME_TEMPLATE.format(person=person)})"


def legacy_flat_relative_paths(targets: list[str]) -> list[Path]:
    paths = list(LEGACY_FLAT_RELATIVE_PATHS)
    paths.extend(Path("exports") / "markdown_views" / f"第五项B自动结算草案_{person}.md" for person in targets)
    return paths


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def add_forbidden_marker_errors(path: Path, content: str, errors: list[str]) -> None:
    for marker in FORBIDDEN_MARKERS:
        if marker in content:
            errors.append(f"{path}: contains forbidden marker {marker!r}")


def existing_target_files(root: Path, targets: list[str]) -> list[Path]:
    files = [root / INDEX_RELATIVE_PATH]
    files.extend(root / detail_relative_path(person) for person in targets)
    files.extend(root / APPENDIX_RELATIVE_DIR / f"{person}_长字段附录.md" for person in targets)
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
    for marker in OLD_AUTO_FEATURE_TABLE_MARKERS:
        if marker in content:
            errors.append(f"{path}: contains old auto feature table marker {marker!r}")
    if "（positive_cluster_ids）" not in content:
        errors.append(f"{path}: missing Chinese display label with machine trace for positive_cluster_ids")


def validate_no_legacy_flat_exports(root: Path, targets: list[str], errors: list[str]) -> None:
    if not (root / INDEX_RELATIVE_PATH).exists():
        return
    for relative_path in legacy_flat_relative_paths(targets):
        path = root / relative_path
        if path.exists():
            errors.append(f"{path}: legacy flat I5B export must be removed after nested export generation")


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
    validate_no_legacy_flat_exports(root, resolved_targets, errors)

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
