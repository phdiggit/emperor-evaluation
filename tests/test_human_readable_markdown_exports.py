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
