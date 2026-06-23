from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT_DOC = next(path for path in (ROOT / "docs").glob("*i5b_markdown_display*.md"))
SHARED_PLAN_DOC = next(
    path
    for path in (ROOT / "docs").glob("scripts*.md")
    if "i5b_markdown_display.py" in path.read_text(encoding="utf-8")
)
LAYOUT_DOC = next(
    path
    for path in (ROOT / "docs").glob("scripts*.md")
    if "## scripts/dev/" in path.read_text(encoding="utf-8")
)
AGENTS = ROOT / "AGENTS.md"
REGISTRY = ROOT / "docs" / "agent_rules" / "scripts_registry.json"
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


def test_i5b_markdown_display_legacy_wrapper_has_been_retired() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))

    assert not (SCRIPTS_DIR / "i5b_markdown_display.py").exists()
    assert (SHARED_DIR / "i5b_markdown_display.py").is_file()
    assert registry["retired_legacy_wrappers"]["scripts/i5b_markdown_display.py"] == "i5b_markdown_display"


def test_related_docs_and_agents_reference_migration_audit() -> None:
    audit_doc_name = AUDIT_DOC.relative_to(ROOT).as_posix()
    assert audit_doc_name in SHARED_PLAN_DOC.read_text(encoding="utf-8")
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    module = next(module for module in registry["modules"] if module["id"] == "i5b_markdown_display")
    assert audit_doc_name in module["audit_docs"]
    assert "docs/agent_rules/scripts_registry.json" in AGENTS.read_text(encoding="utf-8")


def test_layout_doc_keeps_i5b_markdown_display_unmigrated() -> None:
    content = LAYOUT_DOC.read_text(encoding="utf-8")
    assert "docs/agent_rules/scripts_registry.json" in content
    assert "审计文档" in content


def test_canonical_import_path_remains_available() -> None:
    import importlib
    import sys

    sys.path.insert(0, str(SCRIPTS_DIR))
    assert importlib.import_module("shared.i5b_markdown_display") is not None


def test_config_loaders_legacy_wrapper_has_been_retired() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))

    assert not (SCRIPTS_DIR / "config_loaders.py").exists()
    assert (SHARED_DIR / "config_loaders.py").is_file()
    assert registry["retired_legacy_wrappers"]["scripts/config_loaders.py"] == "config_loaders"
