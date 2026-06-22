from __future__ import annotations

import re
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import config_loaders
from i5b_markdown_display import display_field_label, human_review_table_fields, load_display_dictionary


ROOT = Path(__file__).resolve().parents[2]
MARKDOWN_VIEW_RELATIVE_ROOT = Path("exports") / "markdown_views"
I5B_EXPORT_RELATIVE_ROOT = Path("exports") / "markdown_views" / "第五项B"
HUMAN_REVIEW_RELATIVE_DIR = I5B_EXPORT_RELATIVE_ROOT / "人工审核"
MACHINE_AUDIT_RELATIVE_DIR = I5B_EXPORT_RELATIVE_ROOT / "机器审计"
HUMAN_AUTO_ADJUDICATION_RELATIVE_DIR = HUMAN_REVIEW_RELATIVE_DIR / "自动裁判链"
AUTO_DRAFT_RELATIVE_DIR = HUMAN_AUTO_ADJUDICATION_RELATIVE_DIR / "自动结算草案"
DETAIL_RELATIVE_DIR = AUTO_DRAFT_RELATIVE_DIR / "人物详情"
APPENDIX_RELATIVE_DIR = AUTO_DRAFT_RELATIVE_DIR / "附录"
EVIDENCE_CHAIN_RELATIVE_DIR = I5B_EXPORT_RELATIVE_ROOT / "证据链"
INDEX_RELATIVE_PATH = AUTO_DRAFT_RELATIVE_DIR / "第五项B三人自动结算草案.md"
VIEW_INDEX_RELATIVE_PATH = MARKDOWN_VIEW_RELATIVE_ROOT / "导出视图总索引.md"
DETAIL_FILENAME_TEMPLATE = "{person}.md"
FORBIDDEN_MARKERS = ("<details", "<summary", "</details>", "……（共")
DETAIL_REQUIRED_MARKERS = (
    "[返回索引](../第五项B三人自动结算草案.md)",
    "### 证据簇自动结算",
    "### 自动特征",
    "### 自动结算结论",
    "**对象锚点（linked_object_anchors）**",
    "**相邻项剥离说明（cross_item_split_signals）**",
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
LEGACY_FLAT_EVIDENCE_CHAIN_FILENAME_PATTERNS = (
    re.compile(r"^第五项B_.+净证据池\.md$"),
    re.compile(r"^第五项B三人试点检索线索\.md$"),
    re.compile(r"^第五项B扩展试点第一批证据卡与证据簇草案\.md$"),
    re.compile(r"^第五项B扩展试点第一批证据簇结算草案\.md$"),
)
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)#]+)(?:#([^)]+))?\)")
CHINESE_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")
BARE_ENGLISH_HEADER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
UNBOLDED_KV_RE = re.compile(r"^\s*[-*]\s+(?!\*\*)([^：\n]{1,80})：")
CONTEXT_APPENDIX_HEADER_MARKERS = ("上下文摘录", "上下文摘要", "裁判桥接说明")
HUMAN_REVIEW_DECLARATION = "本文件为人工审核视图，隐藏机器追踪字段，只保留业务判断所需信息。"
MACHINE_AUDIT_DECLARATION = "本文件为机器审计视图，用于代码审查、数据追踪和回源定位，不作为人工业务审核主入口。"
NOT_HUMAN_MAIN_ENTRY_DECLARATION = "不作为人工业务审核主入口"
ROOT_MARKDOWN_ALLOWLIST = {"导出视图总索引.md"}
I5B_TOP_LEVEL_ALLOWED_DIRS = {"人工审核", "机器审计", "归档或兼容层"}
I5B_TOP_LEVEL_FORBIDDEN_DIRS = {
    "自动结算草案",
    "规则敏感点",
    "正式定档草案",
    "试点闭环",
    "证据链",
}
I5B_HUMAN_AUTO_CHAIN_REQUIRED_DIRS = {
    "自动结算草案",
    "规则敏感点",
    "正式定档草案",
    "试点闭环",
}
I5B_HUMAN_EVIDENCE_CHAIN_REQUIRED_DIRS = {
    "净证据池",
    "证据卡",
    "证据簇",
    "附录",
}
I5B_MACHINE_EVIDENCE_CHAIN_REQUIRED_DIRS = {
    "净证据池",
    "证据卡",
    "证据簇",
    "检索包",
    "附录",
}
HUMAN_FORBIDDEN_HEADER_MARKERS = (
    "证据ID",
    "来源ID",
    "证据簇ID",
    "查询配置ID",
    "evidence_id",
    "source_id",
    "cluster_id",
    "linked_evidence_ids",
    "query_profile_id",
    "search_id",
    "raw_json",
)
RAW_ENUM_RE = re.compile(r"\b[a-z]+(?:_[a-z0-9]+){1,}\b")
HUMAN_REVIEW_TABLE_KEY_BY_HEADING = {
    "自动结算总览": "auto_adjudication_matrix",
    "总览索引": "auto_adjudication_overview",
    "一、正式落地总览": "formal_landing_overview",
    "一、内部闭环总览": "trial_closure_overview",
    "五、档位到分值映射草案": "score_mapping_draft",
    "人员准备度总览": "expanded_batch_readiness",
    "定向补证来源": "targeted_supplement_sources",
    "定向补证证据卡": "targeted_supplement_evidence_cards",
    "朱元璋 micro supplement 来源": "targeted_supplement_sources",
    "朱元璋 micro supplement 证据卡": "micro_supplement_evidence_cards",
    "readiness follow-up 人物总览": "expanded_batch_followup",
    "会审总览": "human_review_package_overview",
    "逐人准备表": "relative_band_preparation",
    "证据组裁量结论": "net_evidence_clusters",
    "原子证据卡": "net_evidence_cards",
    "证据卡": "evidence_cards_index",
    "证据簇": "evidence_clusters_index",
}


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


def iter_markdown_exports(root: Path) -> list[Path]:
    markdown_root = root / MARKDOWN_VIEW_RELATIVE_ROOT
    if not markdown_root.exists():
        return []
    return sorted(markdown_root.rglob("*.md"))


def add_forbidden_marker_errors(path: Path, content: str, errors: list[str]) -> None:
    for marker in FORBIDDEN_MARKERS:
        if marker in content:
            errors.append(f"{path}: contains forbidden marker {marker!r}")


def validate_forbidden_markers_for_all_markdown_exports(root: Path, errors: list[str]) -> None:
    for path in iter_markdown_exports(root):
        add_forbidden_marker_errors(path, read_text(path), errors)


def add_forbidden_marker_errors_for_all_i5b_exports(root: Path, errors: list[str]) -> None:
    i5b_root = root / I5B_EXPORT_RELATIVE_ROOT
    if not i5b_root.exists():
        return
    for path in i5b_root.rglob("*.md"):
        add_forbidden_marker_errors(path, read_text(path), errors)


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


def validate_no_legacy_flat_evidence_chain_exports(root: Path, errors: list[str]) -> None:
    markdown_root = root / "exports" / "markdown_views"
    if not markdown_root.exists():
        return
    for path in markdown_root.glob("*.md"):
        for pattern in LEGACY_FLAT_EVIDENCE_CHAIN_FILENAME_PATTERNS:
            if pattern.match(path.name):
                errors.append(f"{path}: legacy flat I5B evidence-chain export must be migrated or removed")
                break


def validate_markdown_view_root_layout(root: Path, errors: list[str]) -> None:
    markdown_root = root / MARKDOWN_VIEW_RELATIVE_ROOT
    if not markdown_root.exists():
        return
    for path in sorted(markdown_root.glob("*.md")):
        if path.name not in ROOT_MARKDOWN_ALLOWLIST:
            errors.append(f"{path}: root Markdown export must be classified into a subdirectory")


def validate_i5b_directory_layout(root: Path, errors: list[str]) -> None:
    i5b_root = root / I5B_EXPORT_RELATIVE_ROOT
    if not i5b_root.exists():
        return

    for path in sorted(i5b_root.glob("*.md")):
        errors.append(f"{path}: Fifth item B Markdown must live under 人工审核, 机器审计, or 归档或兼容层")

    for directory in sorted(p for p in i5b_root.iterdir() if p.is_dir()):
        if directory.name in I5B_TOP_LEVEL_FORBIDDEN_DIRS:
            errors.append(f"{directory}: legacy Fifth item B top-level export directory is forbidden")
        elif directory.name not in I5B_TOP_LEVEL_ALLOWED_DIRS:
            errors.append(f"{directory}: unexpected Fifth item B top-level directory")

    human_auto_root = root / HUMAN_AUTO_ADJUDICATION_RELATIVE_DIR
    for name in I5B_HUMAN_AUTO_CHAIN_REQUIRED_DIRS:
        required_dir = human_auto_root / name
        if not required_dir.exists():
            errors.append(f"{required_dir}: missing Fifth item B human auto-adjudication directory")

    human_evidence_root = root / HUMAN_REVIEW_RELATIVE_DIR / "证据链"
    for name in I5B_HUMAN_EVIDENCE_CHAIN_REQUIRED_DIRS:
        required_dir = human_evidence_root / name
        if not required_dir.exists():
            errors.append(f"{required_dir}: missing Fifth item B human evidence-chain directory")

    machine_evidence_root = root / MACHINE_AUDIT_RELATIVE_DIR / "证据链"
    for name in I5B_MACHINE_EVIDENCE_CHAIN_REQUIRED_DIRS:
        required_dir = machine_evidence_root / name
        if not required_dir.exists():
            errors.append(f"{required_dir}: missing Fifth item B machine evidence-chain directory")


def validate_compatibility_layer_declarations(root: Path, errors: list[str]) -> None:
    i5b_compat_root = root / I5B_EXPORT_RELATIVE_ROOT / "归档或兼容层"
    if not i5b_compat_root.exists():
        return
    for path in sorted(i5b_compat_root.rglob("*.md")):
        if NOT_HUMAN_MAIN_ENTRY_DECLARATION not in read_text(path):
            errors.append(f"{path}: compatibility/archive layer must declare it is not a human business review main entry")


def validate_view_index(root: Path, errors: list[str]) -> None:
    index_path = root / VIEW_INDEX_RELATIVE_PATH
    if not index_path.exists():
        errors.append(f"{index_path}: export view index is missing")
        return

    content = read_text(index_path)
    required_markers = (
        "## 目录结构说明",
        "## 人工审核主入口",
        "## 机器审计入口",
        "## 待人工确认清单",
        "## 旧根目录平铺文件禁用说明",
    )
    for marker in required_markers:
        if marker not in content:
            errors.append(f"{index_path}: missing required index section {marker!r}")

    for line_number, line in enumerate(content.splitlines(), start=1):
        for link_target, anchor in MARKDOWN_LINK_RE.findall(line):
            if link_target.startswith(("http://", "https://", "mailto:")):
                continue
            target_path = (index_path.parent / link_target).resolve()
            if not _anchor_exists(target_path, anchor or None):
                errors.append(f"{index_path}:{line_number}: linked index path does not exist: {link_target}#{anchor}")


def _split_markdown_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return []
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def _is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(set(cell.replace(":", "").strip()) <= {"-"} for cell in cells)


def _anchor_exists(target_path: Path, anchor: str | None) -> bool:
    if anchor is None:
        return target_path.exists()
    if not target_path.exists():
        return False
    content = read_text(target_path)
    return f"## {anchor}" in content or f"### {anchor}" in content


def validate_evidence_chain_markdown(root: Path, errors: list[str]) -> None:
    evidence_root = root / EVIDENCE_CHAIN_RELATIVE_DIR
    if not evidence_root.exists():
        return
    for path in evidence_root.rglob("*.md"):
        content = read_text(path)
        add_forbidden_marker_errors(path, content, errors)
        lines = content.splitlines()
        for line_number, line in enumerate(lines, start=1):
            kv_match = UNBOLDED_KV_RE.match(line)
            if kv_match and not line.lstrip().startswith(("- [", "* [")):
                errors.append(f"{path}:{line_number}: Markdown key-value label must be bold")
            for link_target, anchor in MARKDOWN_LINK_RE.findall(line):
                if not link_target.endswith(".md"):
                    continue
                target_path = (path.parent / link_target).resolve()
                if not _anchor_exists(target_path, anchor or None):
                    errors.append(f"{path}:{line_number}: appendix link target does not exist: {link_target}#{anchor}")

        for index, line in enumerate(lines[:-1]):
            header_cells = _split_markdown_table_row(line)
            separator_cells = _split_markdown_table_row(lines[index + 1])
            if not header_cells or not _is_separator_row(separator_cells):
                continue
            for header in header_cells:
                if BARE_ENGLISH_HEADER_RE.match(header):
                    errors.append(f"{path}:{index + 1}: table header exposes bare English field {header!r}")
                if not CHINESE_CHAR_RE.search(header):
                    errors.append(f"{path}:{index + 1}: table header must include Chinese field label: {header!r}")
            row_index = index + 2
            while row_index < len(lines):
                row_cells = _split_markdown_table_row(lines[row_index])
                if not row_cells:
                    break
                context_cell_indexes = [
                    cell_index
                    for cell_index, header in enumerate(header_cells)
                    if any(marker in header for marker in CONTEXT_APPENDIX_HEADER_MARKERS)
                ]
                for cell in row_cells:
                    if len(cell) > 72 and not cell.startswith("["):
                        errors.append(
                            f"{path}:{row_index + 1}: table cell longer than 72 chars must use a positioned appendix link"
                        )
                for cell_index in context_cell_indexes:
                    if cell_index >= len(row_cells):
                        continue
                    cell = row_cells[cell_index]
                    if cell and not cell.startswith("["):
                        errors.append(
                            f"{path}:{row_index + 1}: context long field must use a positioned appendix link"
                        )
                row_index += 1


def _validate_markdown_links(path: Path, lines: list[str], errors: list[str]) -> None:
    for line_number, line in enumerate(lines, start=1):
        for link_target, anchor in MARKDOWN_LINK_RE.findall(line):
            if not link_target.endswith(".md"):
                continue
            target_path = (path.parent / link_target).resolve()
            if not _anchor_exists(target_path, anchor or None):
                errors.append(f"{path}:{line_number}: appendix link target does not exist: {link_target}#{anchor}")


def _nearest_heading(lines: list[str], index: int) -> str:
    for line in reversed(lines[:index]):
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return ""


def _human_header_to_field_map(config: dict[str, object]) -> dict[str, str]:
    mapped: dict[str, str] = {}
    for table_key in HUMAN_REVIEW_TABLE_KEY_BY_HEADING.values():
        for field in human_review_table_fields(table_key, config):
            mapped[display_field_label(field, config)] = field
            labels = config.get("field_labels") if isinstance(config.get("field_labels"), dict) else {}
            if field in labels:
                mapped[str(labels[field])] = field
    return mapped


def _validate_chinese_table_headers(path: Path, lines: list[str], errors: list[str]) -> list[tuple[int, list[str], str]]:
    table_headers: list[tuple[int, list[str], str]] = []
    for index, line in enumerate(lines[:-1]):
        header_cells = _split_markdown_table_row(line)
        separator_cells = _split_markdown_table_row(lines[index + 1])
        if not header_cells or not _is_separator_row(separator_cells):
            continue
        table_headers.append((index, header_cells, _nearest_heading(lines, index)))
        for header in header_cells:
            if BARE_ENGLISH_HEADER_RE.match(header):
                errors.append(f"{path}:{index + 1}: table header exposes bare English field {header!r}")
            if not CHINESE_CHAR_RE.search(header):
                errors.append(f"{path}:{index + 1}: table header must include Chinese field label: {header!r}")
    return table_headers


def validate_human_review_markdown(root: Path, errors: list[str]) -> None:
    human_root = root / HUMAN_REVIEW_RELATIVE_DIR
    if not human_root.exists():
        return
    display_config = load_display_dictionary()
    header_to_field = _human_header_to_field_map(display_config)
    for path in human_root.rglob("*.md"):
        content = read_text(path)
        lines = content.splitlines()
        add_forbidden_marker_errors(path, content, errors)
        _validate_markdown_links(path, lines, errors)
        relative_parts = path.relative_to(human_root).parts
        is_evidence_chain = bool(relative_parts and relative_parts[0] == "证据链")
        is_auto_adjudication_chain = bool(relative_parts and relative_parts[0] == "自动裁判链")
        is_appendix = path.parent.name == "附录"
        if is_evidence_chain and not is_appendix and HUMAN_REVIEW_DECLARATION not in content:
            errors.append(f"{path}: missing human review purpose declaration")
        for header_index, header_cells, heading in _validate_chinese_table_headers(path, lines, errors):
            for header in header_cells:
                for marker in HUMAN_FORBIDDEN_HEADER_MARKERS:
                    if marker in header:
                        errors.append(f"{path}:{header_index + 1}: human review table exposes machine field {marker!r}")
            table_key = HUMAN_REVIEW_TABLE_KEY_BY_HEADING.get(heading)
            if (is_evidence_chain or is_auto_adjudication_chain) and not is_appendix and table_key:
                allowed_fields = set(human_review_table_fields(table_key, display_config))
                for header in header_cells:
                    field = header_to_field.get(header)
                    if field is None:
                        errors.append(
                            f"{path}:{header_index + 1}: human review table {heading!r} header is not mapped to a configured field: {header!r}"
                        )
                    elif field not in allowed_fields:
                        errors.append(
                            f"{path}:{header_index + 1}: human review table {heading!r} field {field!r} is not allowed by table_fields.{table_key}"
                        )
            row_index = header_index + 2
            while row_index < len(lines):
                row_cells = _split_markdown_table_row(lines[row_index])
                if not row_cells:
                    break
                for cell in row_cells:
                    if is_evidence_chain and len(cell) > 72 and not cell.startswith("["):
                        errors.append(
                            f"{path}:{row_index + 1}: table cell longer than 72 chars must use a positioned appendix link"
                        )
                    if cell and not cell.startswith("[") and RAW_ENUM_RE.search(cell):
                        errors.append(
                            f"{path}:{row_index + 1}: human review table {heading!r} exposes unmapped enum value {cell!r}"
                        )
                row_index += 1


def validate_machine_audit_markdown(root: Path, errors: list[str]) -> None:
    machine_root = root / MACHINE_AUDIT_RELATIVE_DIR
    if not machine_root.exists():
        return
    for path in machine_root.rglob("*.md"):
        content = read_text(path)
        add_forbidden_marker_errors(path, content, errors)
        if path.parent.name != "附录" and MACHINE_AUDIT_DECLARATION not in content:
            errors.append(f"{path}: missing machine audit purpose declaration")


def validate_exports(root: Path = ROOT, targets: list[str] | None = None) -> list[str]:
    resolved_targets = targets if targets is not None else list(config_loaders.get_i5b_trial_config().get("targets") or [])
    errors: list[str] = []
    validate_forbidden_markers_for_all_markdown_exports(root, errors)
    validate_markdown_view_root_layout(root, errors)
    validate_i5b_directory_layout(root, errors)
    validate_compatibility_layer_declarations(root, errors)
    validate_view_index(root, errors)
    validate_evidence_chain_markdown(root, errors)
    validate_human_review_markdown(root, errors)
    validate_machine_audit_markdown(root, errors)
    validate_no_legacy_flat_evidence_chain_exports(root, errors)
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
    evidence_chain_exists = (ROOT / EVIDENCE_CHAIN_RELATIVE_DIR).exists()
    markdown_view_exists = (ROOT / MARKDOWN_VIEW_RELATIVE_ROOT).exists()
    if not markdown_view_exists and (not existing_files or not split_export_exists(ROOT, targets)) and not evidence_chain_exists:
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
