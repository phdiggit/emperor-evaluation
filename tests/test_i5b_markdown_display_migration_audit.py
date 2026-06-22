from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT_DOC = ROOT / "docs" / "i5b_markdown_display迁移前依赖审计.md"
SHARED_PLAN_DOC = ROOT / "docs" / "scripts共享工具依赖盘点.md"
LAYOUT_DOC = ROOT / "docs" / "scripts目录规范.md"
AGENTS = ROOT / "AGENTS.md"
SCRIPTS_DIR = ROOT / "scripts"
SHARED_DIR = SCRIPTS_DIR / "shared"


def test_i5b_markdown_display_migration_audit_doc_exists() -> None:
    assert AUDIT_DOC.is_file()


def test_audit_doc_describes_current_location_and_public_api() -> None:
    content = AUDIT_DOC.read_text(encoding="utf-8")
    assert "#196 已完成实迁" in content
    assert "scripts/shared/i5b_markdown_display.py" in content
    assert "scripts/i5b_markdown_display.py" in content
    for api_name in (
        "display_field_label",
        "display_value",
        "load_display_dictionary",
        "render_markdown_table",
        "render_markdown_kv",
        "render_appendix_page",
        "AppendixEntry",
        "human_review_table_fields",
    ):
        assert api_name in content


def test_audit_doc_describes_migration_risks_and_target() -> None:
    content = AUDIT_DOC.read_text(encoding="utf-8")
    for marker in (
        "展示语义变化",
        "人工审核表头白名单",
        "长字段附录",
        "machine key",
        "scripts/shared/i5b_markdown_display.py",
    ):
        assert marker in content


def test_i5b_markdown_display_has_been_migrated_with_legacy_wrapper() -> None:
    assert (SCRIPTS_DIR / "i5b_markdown_display.py").is_file()
    assert (SHARED_DIR / "i5b_markdown_display.py").is_file()

    wrapper_text = (SCRIPTS_DIR / "i5b_markdown_display.py").read_text(encoding="utf-8")
    assert len(wrapper_text.splitlines()) <= 12
    assert "from shared.i5b_markdown_display import *" in wrapper_text
    assert "def " not in wrapper_text


def test_related_docs_and_agents_reference_migration_audit() -> None:
    audit_doc_name = "docs/i5b_markdown_display迁移前依赖审计.md"
    assert audit_doc_name in SHARED_PLAN_DOC.read_text(encoding="utf-8")
    assert audit_doc_name in AGENTS.read_text(encoding="utf-8")


def test_layout_doc_keeps_i5b_markdown_display_unmigrated() -> None:
    content = LAYOUT_DOC.read_text(encoding="utf-8")
    assert "i5b_markdown_display.py" in content
    assert "已迁移" in content
    assert "docs/i5b_markdown_display迁移前依赖审计.md" in content


def test_new_and_legacy_import_paths_remain_available() -> None:
    import importlib
    import sys

    sys.path.insert(0, str(SCRIPTS_DIR))
    assert importlib.import_module("shared.i5b_markdown_display") is not None
    assert importlib.import_module("i5b_markdown_display") is not None


def test_remaining_unmigrated_shared_tool_stays_at_scripts_root() -> None:
    assert (SCRIPTS_DIR / "config_loaders.py").is_file()
    assert not (SHARED_DIR / "config_loaders.py").exists()
