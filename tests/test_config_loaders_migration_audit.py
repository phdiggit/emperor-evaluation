from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT_DOC = ROOT / "archive" / "docs" / "audits" / "config_loaders迁移前依赖审计.md"
AUDIT_DOC_LEGACY_REF = "docs/config_loaders迁移前依赖审计.md"
SHARED_PLAN_DOC = ROOT / "archive" / "docs" / "audits" / "scripts共享工具依赖盘点.md"
LAYOUT_DOC = ROOT / "docs" / "展示与协作" / "scripts目录规范.md"
AGENTS = ROOT / "AGENTS.md"
REGISTRY = ROOT / "docs" / "文档与脚本登记" / "scripts_registry.json"
SCRIPTS_DIR = ROOT / "scripts"
SHARED_DIR = SCRIPTS_DIR / "shared"


def test_config_loaders_migration_audit_doc_exists() -> None:
    assert AUDIT_DOC.is_file()


def test_audit_doc_describes_legacy_and_shared_locations() -> None:
    content = AUDIT_DOC.read_text(encoding="utf-8")
    assert "scripts/config_loaders.py" in content
    assert "scripts/shared/config_loaders.py" in content
    assert "wrapper" in content


def test_audit_doc_describes_path_risks() -> None:
    content = AUDIT_DOC.read_text(encoding="utf-8")
    for marker in (
        "Path(__file__).resolve().parents[1]",
        "parents[2]",
        "data/configs",
    ):
        assert marker in content


def test_audit_doc_describes_key_public_api() -> None:
    content = (SHARED_DIR / "config_loaders.py").read_text(encoding="utf-8")
    for api_name in (
        "PROJECT_CONFIG_PATH",
        "load_project_config",
        "get_subitem_config",
        "load_i5b_cluster_warning_rules",
        "get_i5b_trial_targets",
        "get_i5b_net_evidence_targets",
    ):
        assert api_name in content


def test_config_loaders_legacy_wrapper_has_been_retired() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))

    assert not (SCRIPTS_DIR / "config_loaders.py").exists()
    assert (SHARED_DIR / "config_loaders.py").is_file()
    assert registry["retired_legacy_wrappers"]["scripts/config_loaders.py"] == "config_loaders"


def test_related_docs_and_agents_reference_config_loaders_audit() -> None:
    audit_doc_name = AUDIT_DOC.relative_to(ROOT).as_posix()
    shared_plan_content = SHARED_PLAN_DOC.read_text(encoding="utf-8")
    assert audit_doc_name in shared_plan_content or AUDIT_DOC_LEGACY_REF in shared_plan_content
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    module = next(module for module in registry["modules"] if module["id"] == "config_loaders")
    assert audit_doc_name in module["audit_docs"]
    assert "docs/文档与脚本登记/scripts_registry.json" in AGENTS.read_text(encoding="utf-8")


def test_layout_doc_records_config_loaders_migration() -> None:
    content = LAYOUT_DOC.read_text(encoding="utf-8")
    assert "docs/文档与脚本登记/scripts_registry.json" in content
    assert "审计文档" in content


def test_canonical_import_path_remains_available() -> None:
    import importlib
    import sys

    sys.path.insert(0, str(SCRIPTS_DIR))
    shared = importlib.import_module("shared.config_loaders")

    assert shared.ROOT == ROOT
