from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
EXPORT_DIR = SCRIPTS_DIR / "export"
MIGRATED_EXPORTERS = (
    "export_md",
)
DIMENSION_EXPORT_FRAMEWORK_MODULES = (
    "dimension_export/data_loading.py",
    "dimension_export/evidence_index.py",
    "dimension_export/markdown_rendering.py",
    "dimension_export/output_layout.py",
    "dimension_export/pipeline.py",
    "dimension_export/validation.py",
)


def test_scripts_export_directory_exists() -> None:
    assert EXPORT_DIR.is_dir()
    assert (EXPORT_DIR / "__init__.py").is_file()


def test_migrated_exporter_implementations_live_under_export_directory() -> None:
    for module_name in MIGRATED_EXPORTERS:
        assert (EXPORT_DIR / f"{module_name}.py").is_file()
        assert not (SCRIPTS_DIR / f"{module_name}.py").exists()


def test_canonical_exporter_modules_are_importable() -> None:
    sys.path.insert(0, str(SCRIPTS_DIR))
    for module_name in MIGRATED_EXPORTERS:
        __import__(f"export.{module_name}")


def test_dimension_export_framework_modules_use_english_paths() -> None:
    for relative_path in DIMENSION_EXPORT_FRAMEWORK_MODULES:
        path = EXPORT_DIR / relative_path
        assert path.is_file(), relative_path
        assert relative_path.isascii(), relative_path

    for path in (EXPORT_DIR / "dimension_export").rglob("*"):
        assert path.relative_to(EXPORT_DIR).as_posix().isascii()
    adapters_dir = EXPORT_DIR / "dimension_adapters"
    if adapters_dir.exists():
        for path in adapters_dir.rglob("*"):
            assert path.relative_to(EXPORT_DIR).as_posix().isascii()


def test_docs_and_agents_mention_export_directory_rule() -> None:
    docs = next((ROOT / "docs").rglob("scripts*.md")).read_text(encoding="utf-8")
    agents = (ROOT / "scripts" / "AGENTS.md").read_text(encoding="utf-8")
    assert "scripts/export/" in docs
    assert "retired_legacy_wrappers" in docs
    assert "`scripts/export/`" in agents
    assert "retired_legacy_wrappers" in agents


def test_scripts_root_has_no_export_python_entrypoints() -> None:
    for script_name in (
        "export_md_scaffold.py",
        "build_db.py",
        "run_matrix.py",
        "validate_all.py",
        "config_loaders.py",
    ):
        assert not (SCRIPTS_DIR / script_name).exists()
        assert not (EXPORT_DIR / script_name).exists()
