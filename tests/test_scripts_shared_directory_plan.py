from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
SHARED_DIR = SCRIPTS_DIR / "shared"
SHARED_PLAN_DOC = ROOT / "docs" / "scripts共享工具依赖盘点.md"
MIGRATED_SHARED_TOOLS = (
    "config_loaders.py",
    "export_md_scaffold.py",
    "i5b_cluster_warning_display.py",
    "i5b_markdown_display.py",
)
ROOT_SHARED_TOOLS: tuple[str, ...] = ()
SHARED_TOOLS = MIGRATED_SHARED_TOOLS + ROOT_SHARED_TOOLS


def test_shared_dependency_plan_doc_exists_and_lists_tools() -> None:
    assert SHARED_PLAN_DOC.is_file()
    content = SHARED_PLAN_DOC.read_text(encoding="utf-8")
    for tool_name in SHARED_TOOLS:
        assert tool_name in content
    assert "共享工具迁移必须单独 PR" in content
    assert "必须保留旧路径 wrapper" in content
    assert "普通 exporter 或 validator 迁移 PR 不得顺手迁移共享工具" in content


def test_scripts_shared_placeholder_exists_without_import_side_effects() -> None:
    placeholder = SHARED_DIR / "__init__.py"
    assert placeholder.is_file()
    content = placeholder.read_text(encoding="utf-8")
    assert "import config_loaders" not in content
    assert "import export_md_scaffold" not in content
    assert "import i5b_markdown_display" not in content
    assert "import i5b_cluster_warning_display" not in content


def test_current_shared_tools_have_legacy_wrappers() -> None:
    for tool_name in ROOT_SHARED_TOOLS:
        assert (SCRIPTS_DIR / tool_name).is_file()
        assert not (SHARED_DIR / tool_name).exists()
    for tool_name in MIGRATED_SHARED_TOOLS:
        assert (SCRIPTS_DIR / tool_name).is_file()
        assert (SHARED_DIR / tool_name).is_file()


def test_layout_docs_and_agents_describe_shared_directory_rules() -> None:
    layout_doc = (ROOT / "docs" / "scripts目录规范.md").read_text(encoding="utf-8")
    agents = (ROOT / "scripts" / "AGENTS.md").read_text(encoding="utf-8")

    assert "scripts/shared/" in layout_doc
    assert "共享工具真实实现目录" in layout_doc
    assert "新增被 exporter、validator、pipeline 共同依赖的工具，应放入这里" in layout_doc
    assert "后续迁移共享工具时必须保留旧路径 wrapper" in layout_doc

    assert "`scripts/shared/`：多职责链共享实现目录" in agents
    assert "共享工具" in agents
    assert "单独" in agents
    assert "顺手迁移" in agents


def test_export_md_scaffold_migrated_with_short_legacy_wrapper() -> None:
    assert_short_shared_wrapper("export_md_scaffold.py")


def test_i5b_cluster_warning_display_migrated_with_short_legacy_wrapper() -> None:
    assert_short_shared_wrapper("i5b_cluster_warning_display.py")


def test_config_loaders_migrated_with_legacy_module_forwarder() -> None:
    wrapper_path = SCRIPTS_DIR / "config_loaders.py"
    implementation_path = SHARED_DIR / "config_loaders.py"
    wrapper_text = wrapper_path.read_text(encoding="utf-8")

    assert implementation_path.is_file()
    assert wrapper_path.is_file()
    assert len(wrapper_text.splitlines()) <= 12
    assert "from shared import config_loaders as _config_loaders" in wrapper_text
    assert "sys.modules[__name__] = _config_loaders" in wrapper_text
    assert "def " not in wrapper_text


def assert_short_shared_wrapper(tool_name: str) -> None:
    module_name = tool_name.removesuffix(".py")
    wrapper_path = SCRIPTS_DIR / tool_name
    implementation_path = SHARED_DIR / tool_name
    wrapper_text = wrapper_path.read_text(encoding="utf-8")

    assert implementation_path.is_file()
    assert wrapper_path.is_file()
    assert len(wrapper_text.splitlines()) <= 12
    assert f"from shared.{module_name} import *" in wrapper_text
    assert "def " not in wrapper_text


def test_new_and_legacy_export_md_scaffold_imports() -> None:
    import importlib
    import sys

    sys.path.insert(0, str(SCRIPTS_DIR))
    assert importlib.import_module("export_md_scaffold") is not None
    assert importlib.import_module("shared.export_md_scaffold") is not None


def test_new_and_legacy_i5b_cluster_warning_display_imports() -> None:
    import importlib
    import sys

    sys.path.insert(0, str(SCRIPTS_DIR))
    assert importlib.import_module("i5b_cluster_warning_display") is not None
    assert importlib.import_module("shared.i5b_cluster_warning_display") is not None


def test_new_and_legacy_i5b_markdown_display_imports() -> None:
    import importlib
    import sys

    sys.path.insert(0, str(SCRIPTS_DIR))
    assert importlib.import_module("i5b_markdown_display") is not None
    assert importlib.import_module("shared.i5b_markdown_display") is not None


def test_new_and_legacy_config_loaders_imports_resolve_to_same_module() -> None:
    import importlib
    import sys

    sys.path.insert(0, str(SCRIPTS_DIR))
    legacy = importlib.import_module("config_loaders")
    shared = importlib.import_module("shared.config_loaders")

    assert legacy is shared
    assert legacy.ROOT == ROOT


def test_exporters_and_export_md_import_scaffold_through_supported_paths() -> None:
    import importlib
    import sys

    sys.path.insert(0, str(SCRIPTS_DIR))
    for module_name in (
        "export.export_i5b_net_evidence",
        "export.export_i5b_expanded_batch1",
        "export.export_project_doc_views",
        "export.export_i5b_views",
        "export_md",
        "export.export_i5b_auto_adjudication",
    ):
        assert importlib.import_module(module_name) is not None


def test_display_dependents_import_shared_i5b_markdown_display() -> None:
    import importlib
    import sys

    sys.path.insert(0, str(SCRIPTS_DIR))
    for module_name in (
        "export.export_i5b_net_evidence",
        "export.export_i5b_expanded_batch1",
        "export.export_project_doc_views",
        "export.export_i5b_auto_adjudication",
        "validate.validate_human_readable_markdown_exports",
    ):
        module = importlib.import_module(module_name)
        assert module is not None
