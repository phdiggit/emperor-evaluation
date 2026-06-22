from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
SHARED_DIR = SCRIPTS_DIR / "shared"
SHARED_PLAN_DOC = ROOT / "docs" / "scripts共享工具依赖盘点.md"
SHARED_TOOLS = (
    "config_loaders.py",
    "export_md_scaffold.py",
    "i5b_markdown_display.py",
    "i5b_cluster_warning_display.py",
)


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


def test_current_shared_tools_remain_at_scripts_root() -> None:
    for tool_name in SHARED_TOOLS:
        assert (SCRIPTS_DIR / tool_name).is_file()
        assert not (SHARED_DIR / tool_name).exists()


def test_layout_docs_and_agents_describe_shared_directory_rules() -> None:
    layout_doc = (ROOT / "docs" / "scripts目录规范.md").read_text(encoding="utf-8")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert "scripts/shared/" in layout_doc
    assert "共享工具真实实现目录" in layout_doc
    assert "新增被 exporter、validator、pipeline 共同依赖的工具，应放入这里" in layout_doc
    assert "后续迁移共享工具时必须保留旧路径 wrapper" in layout_doc

    assert "新增被多个 exporter / validator / pipeline 共用的工具，应放入 `scripts/shared/`" in agents
    assert "迁移共享工具必须单独开 PR，保留旧路径 wrapper" in agents
    assert "不得在普通 exporter/validator 迁移 PR 中顺手迁移共享工具" in agents
