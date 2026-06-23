from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT_DOC = next(path for path in (ROOT / "docs").glob("*config_loaders*.md"))
SHARED_PLAN_DOC = next(
    path
    for path in (ROOT / "docs").glob("scripts*.md")
    if "config_loaders.py" in path.read_text(encoding="utf-8")
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
        "配置说明",
        "*.comments.json",
    ):
        assert marker in content


def test_audit_doc_describes_key_public_api() -> None:
    content = AUDIT_DOC.read_text(encoding="utf-8")
    for api_name in (
        "I5B_PERSON_POOL_PATH",
        "I5B_VIEW_GROUPS_PATH",
        "I5B_KEYWORD_PROFILES_PATH",
        "I5B_KEYWORD_OVERRIDES_PATH",
        "I5B_CLUSTER_WARNING_RULES_PATH",
        "load_i5b_cluster_warning_rules",
        "get_i5b_targets",
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
    assert audit_doc_name in SHARED_PLAN_DOC.read_text(encoding="utf-8")
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    module = next(module for module in registry["modules"] if module["id"] == "config_loaders")
    assert audit_doc_name in module["audit_docs"]
    assert "docs/agent_rules/scripts_registry.json" in AGENTS.read_text(encoding="utf-8")


def test_layout_doc_records_config_loaders_migration() -> None:
    content = LAYOUT_DOC.read_text(encoding="utf-8")
    assert "docs/agent_rules/scripts_registry.json" in content
    assert "审计文档" in content


def test_canonical_import_path_remains_available() -> None:
    import importlib
    import sys

    sys.path.insert(0, str(SCRIPTS_DIR))
    shared = importlib.import_module("shared.config_loaders")

    assert shared.ROOT == ROOT
