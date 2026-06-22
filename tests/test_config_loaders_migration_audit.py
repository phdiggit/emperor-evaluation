from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT_DOC = ROOT / "docs" / "config_loaders迁移前依赖审计.md"
SHARED_PLAN_DOC = ROOT / "docs" / "scripts共享工具依赖盘点.md"
LAYOUT_DOC = ROOT / "docs" / "scripts目录规范.md"
AGENTS = ROOT / "AGENTS.md"
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


def test_config_loaders_has_been_migrated_with_legacy_wrapper() -> None:
    assert (SCRIPTS_DIR / "config_loaders.py").is_file()
    assert (SHARED_DIR / "config_loaders.py").is_file()

    wrapper_text = (SCRIPTS_DIR / "config_loaders.py").read_text(encoding="utf-8")
    assert len(wrapper_text.splitlines()) <= 12
    assert "from shared import config_loaders as _config_loaders" in wrapper_text
    assert "sys.modules[__name__] = _config_loaders" in wrapper_text
    assert "def " not in wrapper_text


def test_related_docs_and_agents_reference_config_loaders_audit() -> None:
    audit_doc_name = "docs/config_loaders迁移前依赖审计.md"
    assert audit_doc_name in SHARED_PLAN_DOC.read_text(encoding="utf-8")
    assert audit_doc_name in AGENTS.read_text(encoding="utf-8")


def test_layout_doc_records_config_loaders_migration() -> None:
    content = LAYOUT_DOC.read_text(encoding="utf-8")
    assert "config_loaders.py" in content
    assert "scripts/shared/config_loaders.py" in content
    assert "docs/config_loaders迁移前依赖审计.md" in content


def test_new_and_legacy_import_paths_remain_available() -> None:
    import importlib
    import sys

    sys.path.insert(0, str(SCRIPTS_DIR))
    legacy = importlib.import_module("config_loaders")
    shared = importlib.import_module("shared.config_loaders")

    assert legacy is shared
    assert legacy.ROOT == ROOT
