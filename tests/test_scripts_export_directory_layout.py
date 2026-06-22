from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
EXPORT_DIR = SCRIPTS_DIR / "export"
MIGRATED_EXPORTERS = (
    "export_i5b_auto_adjudication",
    "export_i5b_views",
    "export_i5b_net_evidence",
    "export_i5b_expanded_batch1",
    "export_project_doc_views",
)


def test_scripts_export_directory_exists() -> None:
    assert EXPORT_DIR.is_dir()
    assert (EXPORT_DIR / "__init__.py").is_file()


def test_migrated_exporter_implementations_live_under_export_directory() -> None:
    for module_name in MIGRATED_EXPORTERS:
        assert (EXPORT_DIR / f"{module_name}.py").is_file()
        assert (SCRIPTS_DIR / f"{module_name}.py").is_file()


def test_legacy_exporter_paths_are_short_wrappers() -> None:
    for module_name in MIGRATED_EXPORTERS:
        wrapper_text = (SCRIPTS_DIR / f"{module_name}.py").read_text(encoding="utf-8")
        assert len(wrapper_text.splitlines()) <= 16
        assert f"from export.{module_name} import *" in wrapper_text
        assert "def " not in wrapper_text


def test_new_and_legacy_exporter_modules_are_importable() -> None:
    sys.path.insert(0, str(SCRIPTS_DIR))
    for module_name in MIGRATED_EXPORTERS:
        assert importlib.import_module(f"export.{module_name}") is not None
        assert importlib.import_module(module_name) is not None


def test_auto_adjudication_old_and_new_help_commands_still_run() -> None:
    commands = [
        [sys.executable, str(SCRIPTS_DIR / "export_i5b_auto_adjudication.py"), "--help"],
        [sys.executable, str(EXPORT_DIR / "export_i5b_auto_adjudication.py"), "--help"],
    ]
    for command in commands:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
        assert result.returncode == 0
        assert "--output-layout" in result.stdout


def test_export_md_entrypoint_implementation_lives_under_export_directory() -> None:
    implementation_path = EXPORT_DIR / "export_md.py"
    wrapper_path = SCRIPTS_DIR / "export_md.py"
    wrapper_text = wrapper_path.read_text(encoding="utf-8")

    assert implementation_path.is_file()
    assert wrapper_path.is_file()
    assert len(wrapper_text.splitlines()) <= 16
    assert "from export import export_md" in wrapper_text
    assert "def export_markdown" not in wrapper_text
    assert "DB_PATH =" not in wrapper_text


def test_docs_and_agents_mention_export_directory_rule() -> None:
    docs = (ROOT / "docs" / "scripts目录规范.md").read_text(encoding="utf-8")
    agents = (ROOT / "scripts" / "AGENTS.md").read_text(encoding="utf-8")
    assert "scripts/export/" in docs
    assert "新增 exporter 应放入这里" in docs
    assert "旧 exporter 只作为兼容 wrapper" in docs
    assert "`scripts/export/`" in agents
    assert "exporter" in agents
    assert "wrapper" in agents
    assert "主逻辑" in agents


def test_export_root_entrypoints_are_not_migrated() -> None:
    for script_name in (
        "export_md_scaffold.py",
        "build_db.py",
        "run_matrix.py",
        "validate_all.py",
        "config_loaders.py",
    ):
        assert (SCRIPTS_DIR / script_name).is_file()
        assert not (EXPORT_DIR / script_name).exists()
