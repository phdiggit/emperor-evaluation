from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
SHARED_DIR = SCRIPTS_DIR / "shared"
SHARED_PLAN_DOC = ROOT / "archive" / "docs" / "audits" / "scripts共享工具依赖盘点.md"
MIGRATED_SHARED_TOOLS = (
    "config_loaders.py",
    "export_md_scaffold.py",
    "i5b_markdown_display.py",
)
NEW_SHARED_TOOLS = ("scoring_engine_contracts.py",)
ROOT_SHARED_TOOLS: tuple[str, ...] = ()
SHARED_TOOLS = MIGRATED_SHARED_TOOLS + NEW_SHARED_TOOLS + ROOT_SHARED_TOOLS


def test_shared_dependency_plan_doc_exists_and_lists_tools() -> None:
    assert SHARED_PLAN_DOC.is_file()
    content = SHARED_PLAN_DOC.read_text(encoding="utf-8")
    for tool_name in MIGRATED_SHARED_TOOLS:
        assert tool_name in content
    assert "scripts/shared/" in content


def test_scripts_shared_placeholder_exists_without_import_side_effects() -> None:
    placeholder = SHARED_DIR / "__init__.py"
    assert placeholder.is_file()
    content = placeholder.read_text(encoding="utf-8")
    assert "import config_loaders" not in content
    assert "import export_md_scaffold" not in content
    assert "import i5b_markdown_display" not in content


def test_current_shared_tools_have_retired_root_paths() -> None:
    for tool_name in ROOT_SHARED_TOOLS:
        assert not (SCRIPTS_DIR / tool_name).exists()
    for tool_name in MIGRATED_SHARED_TOOLS:
        assert not (SCRIPTS_DIR / tool_name).exists()
        assert (SHARED_DIR / tool_name).is_file()


def test_layout_docs_and_agents_describe_shared_directory_rules() -> None:
    layout_doc = (ROOT / "docs" / "展示与协作" / "scripts目录规范.md").read_text(encoding="utf-8")
    agents = (ROOT / "scripts" / "AGENTS.md").read_text(encoding="utf-8")

    assert "scripts/shared/" in layout_doc
    assert "retired_legacy_wrappers" in layout_doc
    assert "`scripts/shared/`" in agents
    assert "retired_legacy_wrappers" in agents


def test_shared_canonical_implementations_exist() -> None:
    for tool_name in MIGRATED_SHARED_TOOLS:
        assert (SHARED_DIR / tool_name).is_file()
        assert not (SCRIPTS_DIR / tool_name).exists()


def test_canonical_shared_imports() -> None:
    import importlib
    import sys

    sys.path.insert(0, str(SCRIPTS_DIR))
    for module_name in (
        "shared.export_md_scaffold",
        "shared.i5b_markdown_display",
        "shared.config_loaders",
        "shared.scoring_engine_contracts",
    ):
        assert importlib.import_module(module_name) is not None


def test_exporters_and_export_md_import_scaffold_through_supported_paths() -> None:
    import importlib
    import sys

    sys.path.insert(0, str(SCRIPTS_DIR))
    for module_name in (
        "export.export_md",
    ):
        assert importlib.import_module(module_name) is not None
