from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "scripts" / "dev" / "docs_tool.py"


def load_docs_tool(repo_root: Path):
    spec = importlib.util.spec_from_file_location("docs_tool_under_test", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = repo_root
    return module


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=repo,
        capture_output=True,
        text=False,
        check=True,
    )
    return result.stdout.decode("utf-8")


def init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "-b", "GPT")
    run_git(repo, "config", "user.name", "Docs Tool Test")
    run_git(repo, "config", "user.email", "docs-tool@example.com")
    return repo


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def commit_all(repo: Path, message: str = "seed") -> str:
    run_git(repo, "add", ".")
    run_git(repo, "commit", "-m", message)
    return run_git(repo, "rev-parse", "HEAD").strip()


def seed_repo(repo: Path) -> str:
    write(repo / "AGENTS.md", "任务涉及 docs/** 时，修改前必须读取 docs/AGENTS.md。\n")
    write(repo / "README.md", "[中文](docs/中文说明.md)\n")
    write(repo / "docs" / "AGENTS.md", "# docs rules\n")
    write(repo / "docs" / "中文说明.md", "# 中文说明\n正文\n")
    write(repo / "docs" / "generated.md", "# Generated\n自动生成。\n")
    write(repo / "docs" / "dup-a.md", "# Dup\nsame  \n")
    write(repo / "docs" / "dup-b.md", "# Dup\nsame\n")
    write(repo / "docs" / "dated_20260620.md", "# Dated\n")
    (repo / "docs" / "binary.bin").write_bytes(b"\x00\xff\x00")
    write(
        repo / "scripts" / "make_docs.py",
        "from pathlib import Path\nPath('docs/generated.md').write_text('# Generated\\n', encoding='utf-8')\n",
    )
    write(repo / "tests" / "test_docs_ref.py", "def test_ref():\n    assert 'docs/中文说明.md'\n")
    return commit_all(repo)


def valid_registry(repo: Path, inventory: dict) -> dict:
    docs_tool = load_docs_tool(repo)
    docs = []
    for item in inventory["documents"]:
        path = item["path"]
        docs.append(
            {
                "path": path,
                "title": item["title"],
                "document_type": "generated_view" if path == "docs/generated.md" else "canonical_spec",
                "lifecycle_status": "generated" if path == "docs/generated.md" else "active",
                "proposed_action": "regenerate_only" if path == "docs/generated.md" else "keep",
                "inbound_references": item["inbound_references"],
                "referenced_by_tests": item["referenced_by_tests"],
                "generator_candidates": item["generator_candidates"],
                "replacement_path": None,
                "duplicate_group": item["exact_duplicate_group"],
                "exact_duplicate_group": item["exact_duplicate_group"],
                "normalized_duplicate_group": item["normalized_duplicate_group"],
                "unique_source_risk": path != "docs/generated.md",
                "reason": "临时仓库测试文档。",
                "human_confirmation_required": False,
            }
        )
    return {
        "schema_version": 1,
        "baseline_ref": "HEAD",
        "baseline_sha": run_git(repo, "rev-parse", "HEAD").strip(),
        "docs_agents_budget": {"max_lines": 80, "max_bytes": 12288},
        "allowed_document_types": sorted(docs_tool.ALLOWED_DOCUMENT_TYPES),
        "allowed_lifecycle_statuses": sorted(docs_tool.ALLOWED_LIFECYCLE_STATUSES),
        "allowed_proposed_actions": sorted(docs_tool.ALLOWED_PROPOSED_ACTIONS),
        "documents": sorted(docs, key=lambda item: item["path"]),
    }


def write_registry(repo: Path, registry: dict) -> Path:
    path = repo / "docs" / "agent_rules" / "docs_registry.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    run_git(repo, "add", "docs/agent_rules/docs_registry.json")
    return path


def test_inventory_tracks_ref_chinese_paths_references_generators_and_duplicates(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    first_sha = seed_repo(repo)
    write(repo / "docs" / "new_after_ref.md", "# Later\n")
    commit_all(repo, "later")
    docs_tool = load_docs_tool(repo)

    inventory = docs_tool.build_inventory(first_sha)
    by_path = {item["path"]: item for item in inventory["documents"]}

    assert "docs/中文说明.md" in by_path
    assert "docs/new_after_ref.md" not in by_path
    assert by_path["docs/中文说明.md"]["title"] == "中文说明"
    assert by_path["docs/中文说明.md"]["inbound_references"] == ["README.md", "tests/test_docs_ref.py"]
    assert by_path["docs/中文说明.md"]["referenced_by_tests"] == ["tests/test_docs_ref.py"]
    assert by_path["docs/generated.md"]["generator_candidates"] == ["scripts/make_docs.py"]
    assert by_path["docs/binary.bin"]["is_text"] is False
    assert by_path["docs/binary.bin"]["line_count"] is None
    assert by_path["docs/dated_20260620.md"]["date_suffix"] == "20260620"
    assert by_path["docs/dup-a.md"]["same_title_group"] == by_path["docs/dup-b.md"]["same_title_group"]
    assert by_path["docs/dup-a.md"]["normalized_duplicate_group"] == by_path["docs/dup-b.md"]["normalized_duplicate_group"]
    paths = [item["path"] for item in inventory["documents"]]
    assert paths == sorted(paths)
    assert not (repo / "docs" / "agent_rules" / "docs_registry.json").exists()


def test_inventory_output_is_utf8_no_bom_and_restricted_to_tmp(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    seed_repo(repo)
    docs_tool = load_docs_tool(repo)

    assert docs_tool.main(["inventory", "--ref", "HEAD", "--output", ".tmp/docs/inventory.json"]) == 0
    data = (repo / ".tmp" / "docs" / "inventory.json").read_bytes()
    assert not data.startswith(b"\xef\xbb\xbf")
    assert json.loads(data.decode("utf-8"))["stats"]["total_files"] >= 1
    assert docs_tool.main(["inventory", "--ref", "HEAD", "--output", "docs/bad.json"]) == 1


def test_check_reports_registry_problems_and_accepts_valid_registry(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    seed_repo(repo)
    docs_tool = load_docs_tool(repo)
    inventory = docs_tool.build_inventory("HEAD")
    registry = valid_registry(repo, inventory)
    registry_path = write_registry(repo, registry)
    commit_all(repo, "registry")

    assert docs_tool.check_registry(str(registry_path.relative_to(repo))) == []

    broken = json.loads(registry_path.read_text(encoding="utf-8"))
    broken["documents"] = broken["documents"][:-1]
    broken["documents"][0]["replacement_path"] = "docs/missing.md"
    broken["documents"][0]["proposed_action"] = "delete"
    broken["documents"][0]["lifecycle_status"] = "delete_candidate"
    broken["documents"][0]["human_confirmation_required"] = False
    broken["documents"][0]["unique_source_risk"] = True
    registry_path.write_text(json.dumps(broken, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    problems = docs_tool.check_registry(str(registry_path.relative_to(repo)))

    assert any("tracked docs file is not covered" in problem for problem in problems)
    assert any("replacement_path does not exist" in problem for problem in problems)
    assert any("delete candidate requires human_confirmation_required=true" in problem for problem in problems)
    assert any("unique_source_risk=true cannot use proposed_action=delete" in problem for problem in problems)


def test_check_requires_generated_view_generator_or_human_confirmation(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    seed_repo(repo)
    docs_tool = load_docs_tool(repo)
    inventory = docs_tool.build_inventory("HEAD")
    registry = valid_registry(repo, inventory)
    for doc in registry["documents"]:
        if doc["path"] == "docs/generated.md":
            doc["generator_candidates"] = []
            doc["lifecycle_status"] = "generated"
    registry_path = write_registry(repo, registry)
    commit_all(repo, "registry")

    assert any("generated_view requires generator_candidates" in problem for problem in docs_tool.check_registry(str(registry_path.relative_to(repo))))


def test_report_outputs_candidate_sections_and_cli_return_codes(tmp_path: Path, capfd: pytest.CaptureFixture[str]) -> None:
    repo = init_repo(tmp_path)
    seed_repo(repo)
    docs_tool = load_docs_tool(repo)
    registry = valid_registry(repo, docs_tool.build_inventory("HEAD"))
    registry["documents"][0]["lifecycle_status"] = "archive_candidate"
    registry["documents"][0]["proposed_action"] = "archive"
    registry["documents"][1]["lifecycle_status"] = "delete_candidate"
    registry["documents"][1]["proposed_action"] = "delete"
    registry["documents"][1]["unique_source_risk"] = False
    registry["documents"][1]["human_confirmation_required"] = True
    registry["documents"][2]["lifecycle_status"] = "needs_human_confirmation"
    registry["documents"][2]["proposed_action"] = "review"
    registry_path = write_registry(repo, registry)
    commit_all(repo, "registry")

    report = docs_tool.build_report(str(registry_path.relative_to(repo)))
    assert "## 8. archive candidates" in report
    assert "## 9. delete candidates" in report
    assert "## 10. needs human confirmation" in report
    assert docs_tool.main(["check", "--registry", str(registry_path.relative_to(repo))]) == 0
    assert docs_tool.main(["check", "--registry", "docs/missing.json"]) == 1
    captured = capfd.readouterr()
    assert "registry file is missing" in captured.err
