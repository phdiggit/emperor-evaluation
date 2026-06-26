from __future__ import annotations

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
DIMENSION_EXPORT_FRAMEWORK_MODULES = (
    "dimension_export/data_loading.py",
    "dimension_export/evidence_index.py",
    "dimension_export/markdown_rendering.py",
    "dimension_export/output_layout.py",
    "dimension_export/pipeline.py",
    "dimension_export/validation.py",
    "dimension_adapters/i5b_people_delegation/adapter.py",
    "dimension_adapters/i5b_people_delegation/dictionary_readthrough.py",
    "dimension_adapters/i5b_people_delegation/output_specs.py",
    "dimension_adapters/i5b_people_delegation/rules.py",
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


def test_auto_adjudication_canonical_help_command_runs() -> None:
    result = subprocess.run(
        [sys.executable, str(EXPORT_DIR / "export_i5b_auto_adjudication.py"), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "--output-layout" in result.stdout


def test_auto_adjudication_entrypoint_is_thin_wrapper() -> None:
    wrapper = EXPORT_DIR / "export_i5b_auto_adjudication.py"
    lines = wrapper.read_text(encoding="utf-8").splitlines()

    assert len(lines) <= 30
    assert "dimension_adapters.i5b_people_delegation import adapter as _adapter" in "\n".join(lines)
    assert "main = _adapter.main" in "\n".join(lines)


def test_dimension_export_framework_modules_use_english_paths() -> None:
    for relative_path in DIMENSION_EXPORT_FRAMEWORK_MODULES:
        path = EXPORT_DIR / relative_path
        assert path.is_file(), relative_path
        assert relative_path.isascii(), relative_path

    for path in (EXPORT_DIR / "dimension_export").rglob("*"):
        assert path.relative_to(EXPORT_DIR).as_posix().isascii()
    for path in (EXPORT_DIR / "dimension_adapters").rglob("*"):
        assert path.relative_to(EXPORT_DIR).as_posix().isascii()


def test_export_md_entrypoint_implementation_lives_under_export_directory() -> None:
    assert (EXPORT_DIR / "export_md.py").is_file()
    assert not (SCRIPTS_DIR / "export_md.py").exists()


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
