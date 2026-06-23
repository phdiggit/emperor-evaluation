from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS_AGENTS = ROOT / "docs" / "AGENTS.md"
DOCS_REGISTRY = ROOT / "docs" / "agent_rules" / "docs_registry.json"
DOCS_TOOL = ROOT / "scripts" / "dev" / "docs_tool.py"
REPORT = ROOT / "docs" / "文档治理盘点报告.md"
ALLOWED_DOCS_CHANGES = {
    "docs/AGENTS.md",
    "docs/agent_rules/README.md",
    "docs/agent_rules/docs_registry.json",
    "docs/agent_rules/scripts_registry.json",
    "docs/文档治理盘点报告.md",
}


def load_docs_tool():
    spec = importlib.util.spec_from_file_location("docs_tool_real_repo", DOCS_TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git_lines(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=ROOT,
        capture_output=True,
        text=False,
        check=True,
    )
    return result.stdout.decode("utf-8").splitlines()


def load_registry() -> dict:
    return json.loads(DOCS_REGISTRY.read_text(encoding="utf-8"))


def test_docs_agents_exists_and_stays_inside_budget() -> None:
    registry = load_registry()
    budget = registry["docs_agents_budget"]

    assert DOCS_AGENTS.is_file()
    assert len(DOCS_AGENTS.read_text(encoding="utf-8").splitlines()) <= budget["max_lines"]
    assert len(DOCS_AGENTS.read_bytes()) <= budget["max_bytes"]


def test_root_agents_routes_to_docs_agents() -> None:
    content = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert "docs/AGENTS.md" in content


def test_docs_registry_is_valid_and_tool_check_passes() -> None:
    assert not DOCS_REGISTRY.read_bytes().startswith(b"\xef\xbb\xbf")
    registry = load_registry()

    assert registry["schema_version"] == 1
    assert "docs/agent_rules/docs_registry.json" in registry["registry_exclusions"]

    result = subprocess.run(
        [sys.executable, str(DOCS_TOOL), "check", "--registry", "docs/agent_rules/docs_registry.json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_docs_registry_covers_every_tracked_docs_file_except_itself() -> None:
    registry = load_registry()
    expected = {path for path in git_lines("ls-files", "docs") if path != "docs/agent_rules/docs_registry.json"}
    actual = {doc["path"] for doc in registry["documents"]}

    assert actual == expected


def test_docs_registry_candidate_safety_rules() -> None:
    registry = load_registry()
    for doc in registry["documents"]:
        if doc["proposed_action"] == "delete" or doc["lifecycle_status"] == "delete_candidate":
            assert doc["human_confirmation_required"] is True
            assert doc["reason"].strip()
        if doc["unique_source_risk"]:
            assert doc["proposed_action"] != "delete"
        if doc["replacement_path"]:
            assert (ROOT / doc["replacement_path"]).exists()
        for field in ("generator_candidates", "referenced_by_tests", "inbound_references"):
            for rel_path in doc[field]:
                assert (ROOT / rel_path).exists(), f"{doc['path']} has missing {field}: {rel_path}"


def test_generated_views_have_generators_or_need_human_confirmation() -> None:
    registry = load_registry()
    for doc in registry["documents"]:
        if doc["document_type"] == "generated_view":
            assert doc["generator_candidates"] or doc["lifecycle_status"] == "needs_human_confirmation"


def test_governance_report_exists_and_lists_candidate_classes() -> None:
    assert REPORT.is_file()
    content = REPORT.read_text(encoding="utf-8")
    for needle in [
        "## 8. archive candidates",
        "## 9. delete candidates",
        "## 10. needs human confirmation",
        "本 PR 未删除、移动或重写现有业务文档",
    ]:
        assert needle in content


def test_pr_does_not_delete_rename_or_modify_business_docs() -> None:
    name_status = git_lines("diff", "--name-status", "--find-renames", "origin/GPT...HEAD")
    name_status += git_lines("diff", "--name-status", "--find-renames", "--cached")

    for line in name_status:
        if not line:
            continue
        parts = line.split("\t")
        status = parts[0]
        paths = parts[1:]
        if not any(path.startswith("docs/") for path in paths):
            continue
        assert not status.startswith("D"), line
        assert not status.startswith("R"), line
        for path in paths:
            if path.startswith("docs/"):
                assert path in ALLOWED_DOCS_CHANGES, line
