from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "validate_human_readable_markdown_exports.py"
sys.path.insert(0, str(ROOT / "scripts"))

VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "validate_human_readable_markdown_exports",
    SCRIPT_PATH,
)
assert VALIDATOR_SPEC is not None
validator = importlib.util.module_from_spec(VALIDATOR_SPEC)
assert VALIDATOR_SPEC.loader is not None
VALIDATOR_SPEC.loader.exec_module(validator)


def write_split_export(root: Path, targets: list[str]) -> None:
    export_dir = root / "exports" / "markdown_views" / "第五项B" / "自动结算草案"
    detail_dir = export_dir / "人物详情"
    appendix_dir = export_dir / "附录"
    detail_dir.mkdir(parents=True)
    appendix_dir.mkdir(parents=True)
    index_rows = []
    for person in targets:
        filename = f"{person}.md"
        index_rows.append(f"| {person} | 摘要 | 2 | 1 | [{person}详情](./人物详情/{filename}) |")
        (detail_dir / filename).write_text(
            "\n".join(
                [
                    f"# {person}：第五项B自动结算草案",
                    "",
                    "[返回索引](../第五项B三人自动结算草案.md)",
                    "",
                    "## 人物详情",
                    "",
                    "### 证据簇自动结算",
                    "",
                    "* **对象锚点（linked_object_anchors）**：",
                    "  1. 测试锚点",
                    "",
                    "* **相邻项剥离说明（cross_item_split_signals）**：",
                    "  1. 本项直接证据",
                    "",
                    "### 自动特征",
                    "",
                    f"* **正向证据簇（positive_cluster_ids）**：[见附录：正向证据簇（positive_cluster_ids）](../附录/{person}_长字段附录.md#appendix-positive_cluster_ids)",
                    "* **置信度（confidence）**：high",
                    "",
                    "## 人工复核提示（display-only）",
                    "",
                    "* **命中字段**：",
                    "  1. linked_cards[0].scoring_effect",
                    "",
                    "### 自动结算结论",
                    "",
                    "- **自动结算方向（band_direction）**：测试",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (appendix_dir / f"{person}_长字段附录.md").write_text(
            "\n".join(
                [
                    f"# {person}：第五项B自动结算草案长字段附录",
                    "",
                    f"[返回人物详情](../人物详情/{filename})",
                    "",
                    "## appendix-positive_cluster_ids",
                    "",
                    "### 正向证据簇（positive_cluster_ids）",
                    "",
                    "```json",
                    "[",
                    "  \"ADJ-TEST-POS-001\"",
                    "]",
                    "```",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    (export_dir / "第五项B三人自动结算草案.md").write_text(
        "\n".join(
            [
                "# 第五项B三人自动结算草案",
                "",
                "## 总览索引",
                "",
                "| 人物 | 自动特征摘要 | 证据簇数量 | 人工复核提示数量 | 详情页 |",
                "| --- | --- | --- | --- | --- |",
                *index_rows,
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_validate_exports_accepts_valid_split_export(tmp_path: Path) -> None:
    targets = ["李世民", "刘秀", "刘庄"]
    write_split_export(tmp_path, targets)

    assert validator.validate_exports(tmp_path, targets) == []


def test_validate_exports_reports_forbidden_html_details(tmp_path: Path) -> None:
    targets = ["李世民"]
    write_split_export(tmp_path, targets)
    detail_path = tmp_path / validator.detail_relative_path("李世民")
    detail_path.write_text(detail_path.read_text(encoding="utf-8") + "\n<details>\n", encoding="utf-8")

    errors = validator.validate_exports(tmp_path, targets)

    assert any("contains forbidden marker '<details'" in error for error in errors)
    assert any(str(detail_path) in error for error in errors)


def test_validate_exports_reports_truncation_marker(tmp_path: Path) -> None:
    targets = ["李世民"]
    write_split_export(tmp_path, targets)
    detail_path = tmp_path / validator.detail_relative_path("李世民")
    detail_path.write_text(detail_path.read_text(encoding="utf-8") + "\n……（共10项）\n", encoding="utf-8")

    errors = validator.validate_exports(tmp_path, targets)

    assert any("……（共" in error for error in errors)


def test_validate_exports_reports_missing_index_link_and_detail_page(tmp_path: Path) -> None:
    targets = ["李世民", "刘秀"]
    write_split_export(tmp_path, targets)
    missing_detail_path = tmp_path / validator.detail_relative_path("刘秀")
    missing_detail_path.unlink()
    index_path = tmp_path / validator.INDEX_RELATIVE_PATH
    index_path.write_text(
        index_path.read_text(encoding="utf-8").replace("[刘秀详情](./人物详情/刘秀.md)", "刘秀详情缺失"),
        encoding="utf-8",
    )

    errors = validator.validate_exports(tmp_path, targets)

    assert any("missing detail link [刘秀详情](./人物详情/刘秀.md)" in error for error in errors)
    assert any("linked detail page does not exist" in error and "刘秀" in error for error in errors)


def test_validate_exports_reports_detail_without_backlink(tmp_path: Path) -> None:
    targets = ["李世民"]
    write_split_export(tmp_path, targets)
    detail_path = tmp_path / validator.detail_relative_path("李世民")
    detail_path.write_text(
        detail_path.read_text(encoding="utf-8").replace("[返回索引](../第五项B三人自动结算草案.md)", ""),
        encoding="utf-8",
    )

    errors = validator.validate_exports(tmp_path, targets)

    assert any("missing required detail marker '[返回索引](../第五项B三人自动结算草案.md)'" in error for error in errors)


def test_validate_exports_reports_legacy_flat_export(tmp_path: Path) -> None:
    targets = ["李世民"]
    write_split_export(tmp_path, targets)
    legacy_path = tmp_path / "exports" / "markdown_views" / "第五项B三人自动结算草案.md"
    legacy_path.write_text("# 旧平铺产物\n", encoding="utf-8")

    errors = validator.validate_exports(tmp_path, targets)

    assert any("legacy flat I5B export must be removed" in error for error in errors)


def test_validate_exports_reports_old_wide_cluster_table(tmp_path: Path) -> None:
    targets = ["李世民"]
    write_split_export(tmp_path, targets)
    detail_path = tmp_path / validator.detail_relative_path("李世民")
    detail_path.write_text(detail_path.read_text(encoding="utf-8") + "\n| cluster_id | polarity | cluster_type |\n", encoding="utf-8")

    errors = validator.validate_exports(tmp_path, targets)

    assert any("old wide evidence cluster table marker '| cluster_id |'" in error for error in errors)


def test_validate_exports_reports_warning_section_without_matched_fields(tmp_path: Path) -> None:
    targets = ["李世民"]
    write_split_export(tmp_path, targets)
    detail_path = tmp_path / validator.detail_relative_path("李世民")
    detail_path.write_text(detail_path.read_text(encoding="utf-8").replace("* **命中字段**：", ""), encoding="utf-8")

    errors = validator.validate_exports(tmp_path, targets)

    assert any("warning section is present but missing '**命中字段**'" in error for error in errors)


def write_evidence_chain_export(root: Path, content: str) -> Path:
    export_path = root / "exports" / "markdown_views" / "第五项B" / "证据链" / "净证据池" / "测试.md"
    export_path.parent.mkdir(parents=True, exist_ok=True)
    export_path.write_text(content, encoding="utf-8")
    appendix_path = root / "exports" / "markdown_views" / "第五项B" / "证据链" / "附录" / "测试附录.md"
    appendix_path.parent.mkdir(parents=True, exist_ok=True)
    appendix_path.write_text(
        "\n".join(["# 测试附录", "", "## e-i5b-001-quote_short", "", "原始长字段", ""]),
        encoding="utf-8",
    )
    return export_path


def write_human_review_export(root: Path, content: str, appendix_content: str | None = None) -> Path:
    export_path = root / "exports" / "markdown_views" / "第五项B" / "人工审核" / "净证据池" / "测试.md"
    export_path.parent.mkdir(parents=True, exist_ok=True)
    export_path.write_text(content, encoding="utf-8")
    appendix_path = root / "exports" / "markdown_views" / "第五项B" / "人工审核" / "附录" / "测试附录.md"
    appendix_path.parent.mkdir(parents=True, exist_ok=True)
    appendix_path.write_text(
        appendix_content
        or "\n".join(["# 测试附录", "", "## card-001", "", "### 机器定位信息", "", "```text", "evidence_id: CARD-001", "```", ""]),
        encoding="utf-8",
    )
    return export_path


def write_machine_audit_export(root: Path, content: str) -> Path:
    export_path = root / "exports" / "markdown_views" / "第五项B" / "机器审计" / "净证据池" / "测试.md"
    export_path.parent.mkdir(parents=True, exist_ok=True)
    export_path.write_text(content, encoding="utf-8")
    return export_path


def test_validate_exports_reports_evidence_chain_bare_english_table_header(tmp_path: Path) -> None:
    write_evidence_chain_export(
        tmp_path,
        "\n".join(
            [
                "# 测试",
                "",
                "| evidence_id | 短摘（quote_short） |",
                "| --- | --- |",
                "| E-I5B-001 | [见附录：短摘](../附录/测试附录.md#e-i5b-001-quote_short) |",
                "",
            ]
        ),
    )

    errors = validator.validate_exports(tmp_path, [])

    assert any("table header exposes bare English field 'evidence_id'" in error for error in errors)


def test_validate_exports_reports_evidence_chain_long_cell_without_appendix_link(tmp_path: Path) -> None:
    write_evidence_chain_export(
        tmp_path,
        "\n".join(
            [
                "# 测试",
                "",
                "| 证据ID（evidence_id） | 短摘（quote_short） |",
                "| --- | --- |",
                "| E-I5B-001 | " + "长字段" * 30 + " |",
                "",
            ]
        ),
    )

    errors = validator.validate_exports(tmp_path, [])

    assert any("table cell longer than 72 chars must use a positioned appendix link" in error for error in errors)


def test_validate_exports_reports_context_long_field_without_appendix_link(tmp_path: Path) -> None:
    write_evidence_chain_export(
        tmp_path,
        "\n".join(
            [
                "# 测试",
                "",
                "| 证据ID（evidence_id） | 上下文摘录（quote_context） |",
                "| --- | --- |",
                "| E-I5B-001 | 即使较短也应进入附录链接 |",
                "",
            ]
        ),
    )

    errors = validator.validate_exports(tmp_path, [])

    assert any("context long field must use a positioned appendix link" in error for error in errors)


def test_validate_exports_reports_evidence_chain_broken_appendix_link(tmp_path: Path) -> None:
    write_evidence_chain_export(
        tmp_path,
        "\n".join(
            [
                "# 测试",
                "",
                "| 证据ID（evidence_id） | 短摘（quote_short） |",
                "| --- | --- |",
                "| E-I5B-001 | [见附录：短摘](../附录/缺失.md#e-i5b-001-quote_short) |",
                "",
            ]
        ),
    )

    errors = validator.validate_exports(tmp_path, [])

    assert any("appendix link target does not exist" in error for error in errors)


def test_validate_exports_reports_evidence_chain_unbolded_key_value_label(tmp_path: Path) -> None:
    write_evidence_chain_export(
        tmp_path,
        "\n".join(
            [
                "# 测试",
                "",
                "- 正向证据簇：ADJ-I5B-001",
                "",
            ]
        ),
    )

    errors = validator.validate_exports(tmp_path, [])

    assert any("Markdown key-value label must be bold" in error for error in errors)


def test_validate_exports_reports_human_review_machine_field_header(tmp_path: Path) -> None:
    write_human_review_export(
        tmp_path,
        "\n".join(
            [
                "# 测试",
                "",
                "本文件为人工审核视图，隐藏机器追踪字段，只保留业务判断所需信息。",
                "",
                "| 证据ID（evidence_id） | 人物（person） |",
                "| --- | --- |",
                "| CARD-001 | 测试人物 |",
                "",
            ]
        ),
    )

    errors = validator.validate_exports(tmp_path, [])

    assert any("human review table exposes machine field" in error for error in errors)


def test_validate_exports_reports_human_review_unmapped_enum(tmp_path: Path) -> None:
    write_human_review_export(
        tmp_path,
        "\n".join(
            [
                "# 测试",
                "",
                "本文件为人工审核视图，隐藏机器追踪字段，只保留业务判断所需信息。",
                "",
                "| 人物（person） | 裁判状态（adjudication_status） |",
                "| --- | --- |",
                "| 测试人物 | source_verified_auto_classified_cluster_review_pending |",
                "",
            ]
        ),
    )

    errors = validator.validate_exports(tmp_path, [])

    assert any("human review table exposes unmapped enum value" in error for error in errors)


def test_validate_exports_reports_machine_audit_missing_declaration(tmp_path: Path) -> None:
    write_machine_audit_export(
        tmp_path,
        "\n".join(
            [
                "# 测试",
                "",
                "| 证据ID（evidence_id） |",
                "| --- |",
                "| CARD-001 |",
                "",
            ]
        ),
    )

    errors = validator.validate_exports(tmp_path, [])

    assert any("missing machine audit purpose declaration" in error for error in errors)


def test_standalone_cli_passes_on_current_repo_exports() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Human-readable Markdown export validation" in result.stdout
