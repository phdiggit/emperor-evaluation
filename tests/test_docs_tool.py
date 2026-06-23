from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "scripts" / "dev" / "docs_tool.py"


def load_docs_tool(repo_root: Path):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    module = importlib.import_module("scripts.dev.docs_governance")
    module.constants.ROOT = repo_root
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


def add_project_driver(repo: Path) -> None:
    write(
        repo / "docs" / "driver.md",
        "# 中国古代皇帝综合评价体系 V3.2\n\n正收益总分 − 历史负债\n\n正收益合计\n\n历史负债\n",
    )


def seed_repo(repo: Path) -> str:
    write(repo / "AGENTS.md", "任务涉及 docs/** 时，修改前必须读取 docs/AGENTS.md。\n")
    write(repo / "README.md", "[中文](docs/中文说明.md)\n")
    write(repo / "docs" / "AGENTS.md", "# docs rules\n")
    write(repo / "docs" / "中文说明.md", "# 中文说明\n正文\n")
    write(repo / "docs" / "generated.md", "# Generated\n自动生成。\n")
    add_project_driver(repo)
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
                "content_role": "generated_output" if path == "docs/generated.md" else "rule_or_method",
                "placement_action": "move_to_exports" if path == "docs/generated.md" else "keep_in_docs",
                "placement_targets": ["exports/markdown_views/generated.md"] if path == "docs/generated.md" else [],
                "placement_reason": (
                    "临时仓库测试生成视图，后续只保留导出目标。"
                    if path == "docs/generated.md"
                    else "临时仓库测试稳定规则，继续保留在 docs。"
                ),
                "semantic_verification_required": False,
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
        "allowed_content_roles": sorted(docs_tool.ALLOWED_CONTENT_ROLES),
        "allowed_placement_actions": sorted(docs_tool.ALLOWED_PLACEMENT_ACTIONS),
        "project_driver_paths": ["docs/driver.md"],
        "documents": sorted(docs, key=lambda item: item["path"]),
    }


def write_registry(repo: Path, registry: dict) -> Path:
    path = repo / "docs" / "文档与脚本登记" / "docs_registry.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    run_git(repo, "add", "docs/文档与脚本登记/docs_registry.json")
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
    assert not (repo / "docs" / "文档与脚本登记" / "docs_registry.json").exists()


def test_inventory_reference_graph_uses_requested_ref_not_worktree(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    write(repo / "AGENTS.md", "docs/AGENTS.md\n")
    write(repo / "README.md", "[A](docs/a.md)\n")
    write(repo / "docs" / "AGENTS.md", "# docs rules\n")
    write(repo / "docs" / "a.md", "# A\n")
    write(repo / "docs" / "b.md", "# B\n")
    write(repo / "docs" / "sub" / "guide.md", "[A relative](../a.md)\n")
    base_sha = commit_all(repo, "base")
    write(repo / "README.md", "[B](docs/b.md)\n")
    write(repo / "docs" / "文档与脚本登记" / "docs_registry.json", '{"note": "docs/a.md"}\n')
    write(repo / "exports" / "governance" / "文档治理盘点报告.md", "治理引用 docs/a.md\n")
    commit_all(repo, "later")
    docs_tool = load_docs_tool(repo)

    base_inventory = docs_tool.build_inventory(base_sha)
    base_by_path = {item["path"]: item for item in base_inventory["documents"]}
    head_inventory = docs_tool.build_inventory("HEAD")
    head_by_path = {item["path"]: item for item in head_inventory["documents"]}

    assert base_by_path["docs/a.md"]["inbound_references"] == ["README.md", "docs/sub/guide.md"]
    assert base_by_path["docs/a.md"]["governance_references"] == []
    assert "docs/文档治理盘点报告.md" not in base_by_path
    assert head_by_path["docs/a.md"]["inbound_references"] == ["docs/sub/guide.md"]
    assert head_by_path["docs/a.md"]["governance_references"] == [
        "docs/文档与脚本登记/docs_registry.json",
    ]
    assert head_by_path["docs/b.md"]["inbound_references"] == ["README.md"]


def test_inventory_output_is_utf8_no_bom_and_restricted_to_tmp(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    seed_repo(repo)
    docs_tool = load_docs_tool(repo)

    assert docs_tool.main(["inventory", "--ref", "HEAD", "--output", ".tmp/docs/inventory.json"]) == 0
    data = (repo / ".tmp" / "docs" / "inventory.json").read_bytes()
    assert not data.startswith(b"\xef\xbb\xbf")
    assert json.loads(data.decode("utf-8"))["stats"]["total_files"] >= 1
    assert docs_tool.main(["inventory", "--ref", "HEAD", "--output", "docs/bad.json"]) == 1


def test_report_output_defaults_to_exports_governance(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    seed_repo(repo)
    docs_tool = load_docs_tool(repo)
    registry = valid_registry(repo, docs_tool.build_inventory("HEAD"))
    registry_path = write_registry(repo, registry)
    commit_all(repo, "registry")

    assert docs_tool.main(["report", "--registry", str(registry_path.relative_to(repo))]) == 0
    report_path = repo / "exports" / "governance" / "文档治理盘点报告.md"
    assert report_path.is_file()
    assert not report_path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert docs_tool.main(
        [
            "report",
            "--registry",
            str(registry_path.relative_to(repo)),
            "--output",
            "docs/文档治理盘点报告.md",
        ]
    ) == 1


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


def test_check_worktree_mode_detects_unstaged_added_and_deleted_docs(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    seed_repo(repo)
    docs_tool = load_docs_tool(repo)
    inventory = docs_tool.build_inventory("HEAD")
    registry = valid_registry(repo, inventory)
    registry_path = write_registry(repo, registry)
    commit_all(repo, "registry")

    write(repo / "docs" / "未暂存新增.md", "# 未暂存新增\n")

    assert docs_tool.check_registry(str(registry_path.relative_to(repo))) == []
    worktree_add_problems = docs_tool.check_registry(str(registry_path.relative_to(repo)), worktree=True)
    assert any("docs/未暂存新增.md: worktree docs file is not covered by docs registry" in problem for problem in worktree_add_problems)

    (repo / "docs" / "generated.md").unlink()

    worktree_delete_problems = docs_tool.check_registry(str(registry_path.relative_to(repo)), worktree=True)
    assert any("docs/generated.md: registry path is not a worktree docs file" in problem for problem in worktree_delete_problems)
    assert docs_tool.main(["check", "--registry", str(registry_path.relative_to(repo)), "--worktree"]) == 1


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


def test_check_validates_content_placement_governance_rules(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    seed_repo(repo)
    docs_tool = load_docs_tool(repo)
    inventory = docs_tool.build_inventory("HEAD")
    registry = valid_registry(repo, inventory)
    registry_path = write_registry(repo, registry)
    commit_all(repo, "registry")

    def problems_for(mutator) -> list[str]:
        broken = json.loads(json.dumps(registry, ensure_ascii=False))
        mutator(broken)
        registry_path.write_text(json.dumps(broken, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return docs_tool.check_registry(str(registry_path.relative_to(repo)))

    assert any("allowed_content_roles do not match supported set" in p for p in problems_for(lambda r: r.__setitem__("allowed_content_roles", [])))
    assert any("invalid content_role" in p for p in problems_for(lambda r: r["documents"][0].__setitem__("content_role", "bad_role")))
    assert any("invalid placement_action" in p for p in problems_for(lambda r: r["documents"][0].__setitem__("placement_action", "bad_action")))
    assert any(
        "content_role=generated_output cannot use placement_action=keep_in_docs" in p
        for p in problems_for(
            lambda r: (
                r["documents"][0].__setitem__("content_role", "generated_output"),
                r["documents"][0].__setitem__("placement_action", "keep_in_docs"),
            )
        )
    )
    assert any(
        "content_role=mixed requires placement_action" in p
        for p in problems_for(
            lambda r: (
                r["documents"][0].__setitem__("content_role", "mixed"),
                r["documents"][0].__setitem__("placement_action", "keep_in_docs"),
            )
        )
    )
    assert any(
        "semantic_verification_required=true" in p
        for p in problems_for(
            lambda r: (
                r["documents"][0].__setitem__("content_role", "instance_record"),
                r["documents"][0].__setitem__("placement_action", "absorb_into_canonical_data_then_export"),
                r["documents"][0].__setitem__("placement_targets", ["data/evidence_cards.jsonl"]),
                r["documents"][0].__setitem__("semantic_verification_required", False),
            )
        )
    )
    assert any(
        "requires non-empty placement_targets" in p
        for p in problems_for(lambda r: r["documents"][0].__setitem__("placement_action", "move_to_exports"))
    )
    assert any(
        "placement_targets must be repo-relative controlled paths" in p
        for p in problems_for(
            lambda r: (
                r["documents"][0].__setitem__("placement_action", "move_to_exports"),
                r["documents"][0].__setitem__("placement_targets", ["../exports/bad.md"]),
            )
        )
    )
    assert any(
        "placement_targets must be repo-relative controlled paths" in p
        for p in problems_for(
            lambda r: (
                r["documents"][0].__setitem__("placement_action", "move_to_exports"),
                r["documents"][0].__setitem__("placement_targets", ["README.md.bak"]),
            )
        )
    )
    assert any(
        "semantic_verification_required must be boolean" in p
        for p in problems_for(lambda r: r["documents"][0].__setitem__("semantic_verification_required", 1))
    )
    assert any(
        "keep_archive_exception is only allowed under archive/docs/" in p
        for p in problems_for(lambda r: r["documents"][0].__setitem__("placement_action", "keep_archive_exception"))
    )
    assert any(
        "keep_governance_exception is only allowed under docs/文档与脚本登记/" in p
        for p in problems_for(lambda r: r["documents"][0].__setitem__("placement_action", "keep_governance_exception"))
    )


def test_check_validates_project_driver_paths(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    seed_repo(repo)
    docs_tool = load_docs_tool(repo)
    registry = valid_registry(repo, docs_tool.build_inventory("HEAD"))
    driver_doc = next(doc for doc in registry["documents"] if doc["path"] == "docs/driver.md")
    driver_doc["title"] = "中国古代皇帝综合评价体系 V3.2"
    driver_doc["reason"] = "临时仓库项目上位驱动文档。"
    driver_doc["placement_reason"] = "临时仓库项目驱动文档，长期保留在 docs。"
    registry_path = write_registry(repo, registry)
    commit_all(repo, "registry")

    assert docs_tool.check_registry(str(registry_path.relative_to(repo))) == []

    def problems_for(mutator) -> list[str]:
        broken = json.loads(json.dumps(registry, ensure_ascii=False))
        mutator(broken)
        registry_path.write_text(json.dumps(broken, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return docs_tool.check_registry(str(registry_path.relative_to(repo)))

    assert any("project_driver_paths must be a non-empty list" in p for p in problems_for(lambda r: r.pop("project_driver_paths")))
    assert any("project_driver_paths must be a non-empty list" in p for p in problems_for(lambda r: r.__setitem__("project_driver_paths", [])))
    assert any("project driver is not registered" in p for p in problems_for(lambda r: r.__setitem__("project_driver_paths", ["docs/missing.md"])))
    assert any(
        "project driver is not registered" in p
        for p in problems_for(lambda r: r.__setitem__("documents", [d for d in r["documents"] if d["path"] != "docs/driver.md"]))
    )
    assert any(
        "project driver requires document_type='canonical_spec'" in p
        for p in problems_for(lambda r: next(d for d in r["documents"] if d["path"] == "docs/driver.md").__setitem__("document_type", "generated_view"))
    )
    assert any(
        "project driver requires lifecycle_status='active'" in p
        for p in problems_for(lambda r: next(d for d in r["documents"] if d["path"] == "docs/driver.md").__setitem__("lifecycle_status", "historical"))
    )
    assert any(
        "project driver requires proposed_action='keep'" in p
        for p in problems_for(lambda r: next(d for d in r["documents"] if d["path"] == "docs/driver.md").__setitem__("proposed_action", "archive"))
    )
    assert any(
        "project driver requires unique_source_risk=True" in p
        for p in problems_for(lambda r: next(d for d in r["documents"] if d["path"] == "docs/driver.md").__setitem__("unique_source_risk", False))
    )
    assert any(
        "project driver must not appear in archived_document_paths" in p
        for p in problems_for(lambda r: r.__setitem__("archived_document_paths", {"docs/old_driver.md": "docs/driver.md"}))
    )

    report = docs_tool.build_report(str(registry_path.relative_to(repo)))
    assert "## 2. 项目驱动文档" in report
    assert "docs/driver.md" in report


def test_check_validates_archived_document_paths(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    seed_repo(repo)
    (repo / "archive" / "docs" / "audits").mkdir(parents=True)
    run_git(repo, "mv", "docs/dated_20260620.md", "archive/docs/audits/dated_20260620.md")
    commit_all(repo, "archive dated doc")
    docs_tool = load_docs_tool(repo)
    registry = valid_registry(repo, docs_tool.build_inventory("HEAD"))
    archived_path = "archive/docs/audits/dated_20260620.md"
    for doc in registry["documents"]:
        if doc["path"] == archived_path:
            doc["document_type"] = "audit_record"
            doc["lifecycle_status"] = "historical"
            doc["proposed_action"] = "keep"
            doc["content_role"] = "historical_record"
            doc["placement_action"] = "keep_archive_exception"
            doc["placement_reason"] = "临时仓库已归档审计材料，保留历史追溯。"
            doc["human_confirmation_required"] = False
    registry["archived_document_paths"] = {"docs/dated_20260620.md": archived_path}
    registry_path = write_registry(repo, registry)
    commit_all(repo, "registry")

    assert docs_tool.check_registry(str(registry_path.relative_to(repo))) == []

    def problems_for(mutator) -> list[str]:
        broken = json.loads(json.dumps(registry, ensure_ascii=False))
        mutator(broken)
        registry_path.write_text(json.dumps(broken, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return docs_tool.check_registry(str(registry_path.relative_to(repo)))

    assert any("archived_document_paths must be an object" in p for p in problems_for(lambda r: r.__setitem__("archived_document_paths", [])))
    assert any("archived old path still exists" in p for p in problems_for(lambda r: (repo / "docs" / "dated_20260620.md").write_text("# old\n", encoding="utf-8")))
    (repo / "docs" / "dated_20260620.md").unlink()
    assert any("archived path does not exist" in p for p in problems_for(lambda r: r["archived_document_paths"].__setitem__("docs/dated_20260620.md", "archive/docs/audits/missing.md")))
    assert any("archived path must be under archive/docs/" in p for p in problems_for(lambda r: r["archived_document_paths"].__setitem__("docs/dated_20260620.md", "docs/other.md")))
    assert any("archived old path is still registered" in p for p in problems_for(lambda r: r["documents"].append({**r["documents"][0], "path": "docs/dated_20260620.md"})))
    assert any("archived path is not registered" in p for p in problems_for(lambda r: r.__setitem__("documents", [d for d in r["documents"] if d["path"] != archived_path])))
    assert any("lifecycle_status=historical" in p for p in problems_for(lambda r: next(d for d in r["documents"] if d["path"] == archived_path).__setitem__("lifecycle_status", "active")))
    assert any("proposed_action=keep" in p for p in problems_for(lambda r: next(d for d in r["documents"] if d["path"] == archived_path).__setitem__("proposed_action", "archive")))
    assert any("human_confirmation_required=false" in p for p in problems_for(lambda r: next(d for d in r["documents"] if d["path"] == archived_path).__setitem__("human_confirmation_required", True)))
    assert any("mapped from multiple old paths" in p for p in problems_for(lambda r: r["archived_document_paths"].__setitem__("docs/second_old.md", archived_path)))


def test_check_validates_retired_generated_document_paths(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    seed_repo(repo)
    docs_tool = load_docs_tool(repo)
    registry = valid_registry(repo, docs_tool.build_inventory("HEAD"))
    retired_old = "docs/generated.md"
    retired_target = "exports/markdown_views/generated.md"
    (repo / "exports" / "markdown_views").mkdir(parents=True)
    write(repo / retired_target, "# Generated export\n")
    run_git(repo, "add", retired_target)
    run_git(repo, "rm", retired_old)
    commit_all(repo, "retire generated docs copy")
    registry = valid_registry(repo, docs_tool.build_inventory("HEAD"))
    registry["documents"] = [doc for doc in registry["documents"] if doc["path"] != retired_old]
    registry["retired_generated_document_paths"] = {retired_old: retired_target}
    registry_path = write_registry(repo, registry)
    commit_all(repo, "registry")

    assert docs_tool.check_registry(str(registry_path.relative_to(repo))) == []
    report = docs_tool.build_report(str(registry_path.relative_to(repo)))
    assert "## 已迁出 docs 的生成文档摘要" in report
    assert "retired generated docs" in report
    assert retired_old not in report
    assert retired_target not in report

    def problems_for(mutator) -> list[str]:
        broken = json.loads(json.dumps(registry, ensure_ascii=False))
        mutator(broken)
        registry_path.write_text(json.dumps(broken, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return docs_tool.check_registry(str(registry_path.relative_to(repo)))

    assert any("retired_generated_document_paths must be an object" in p for p in problems_for(lambda r: r.__setitem__("retired_generated_document_paths", [])))
    assert any("retired generated old path still exists" in p for p in problems_for(lambda r: (repo / retired_old).write_text("# old\n", encoding="utf-8")))
    (repo / retired_old).unlink()
    assert any("retired generated old path is still registered" in p for p in problems_for(lambda r: r["documents"].append({**r["documents"][0], "path": retired_old})))
    assert any("retired generated target must be under exports/" in p for p in problems_for(lambda r: r["retired_generated_document_paths"].__setitem__(retired_old, "docs/generated.md")))
    assert any("retired generated target does not exist" in p for p in problems_for(lambda r: r["retired_generated_document_paths"].__setitem__(retired_old, "exports/markdown_views/missing.md")))
    assert any("project driver cannot be a retired generated old path" in p for p in problems_for(lambda r: r["retired_generated_document_paths"].__setitem__("docs/driver.md", retired_target)))
    assert any("conflicts with archived_document_paths" in p for p in problems_for(lambda r: (r.__setitem__("archived_document_paths", {retired_old: "archive/docs/audits/generated.md"}), r["retired_generated_document_paths"].__setitem__(retired_old, retired_target))))
    assert any("retired generated target is mapped from multiple old paths" in p for p in problems_for(lambda r: r["retired_generated_document_paths"].__setitem__("docs/second.md", retired_target)))


    assert any("retired generated target must be under exports/" in p for p in problems_for(lambda r: r["retired_generated_document_paths"].__setitem__(retired_old, "exports/../data/existing.md")))
    assert any("retired generated target must be under exports/" in p for p in problems_for(lambda r: r["retired_generated_document_paths"].__setitem__(retired_old, "exports/../../outside.md")))
    assert any("retired generated old path must be under docs/" in p for p in problems_for(lambda r: r["retired_generated_document_paths"].__setitem__("docs/../README.md", retired_target)))


def test_check_validates_retired_mixed_document_paths(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    seed_repo(repo)
    docs_tool = load_docs_tool(repo)
    mixed_old = "docs/中文说明.md"
    mixed_target = "exports/markdown_views/中文说明.md"
    write(repo / mixed_target, "# 中文说明 export\n")
    run_git(repo, "add", mixed_target)
    run_git(repo, "rm", mixed_old)
    commit_all(repo, "retire mixed docs copy")
    registry = valid_registry(repo, docs_tool.build_inventory("HEAD"))
    registry["documents"] = [doc for doc in registry["documents"] if doc["path"] != mixed_old]
    registry["retired_mixed_document_paths"] = {mixed_old: mixed_target}
    registry_path = write_registry(repo, registry)
    commit_all(repo, "registry")

    assert docs_tool.check_registry(str(registry_path.relative_to(repo))) == []
    report = docs_tool.build_report(str(registry_path.relative_to(repo)))
    assert "## 已迁出 docs 的混合审核文档摘要" in report
    assert "retired mixed docs" in report
    assert mixed_old not in report
    assert mixed_target not in report

    def problems_for(mutator) -> list[str]:
        broken = json.loads(json.dumps(registry, ensure_ascii=False))
        mutator(broken)
        registry_path.write_text(json.dumps(broken, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return docs_tool.check_registry(str(registry_path.relative_to(repo)))

    assert any("retired_mixed_document_paths must be an object" in p for p in problems_for(lambda r: r.__setitem__("retired_mixed_document_paths", [])))
    assert any("retired mixed old path still exists" in p for p in problems_for(lambda r: (repo / mixed_old).write_text("# old\n", encoding="utf-8")))
    (repo / mixed_old).unlink()
    assert any("retired mixed old path is still registered" in p for p in problems_for(lambda r: r["documents"].append({**r["documents"][0], "path": mixed_old})))
    assert any("retired mixed target must be under exports/ or archive/docs/" in p for p in problems_for(lambda r: r["retired_mixed_document_paths"].__setitem__(mixed_old, "data/generated.md")))
    assert any("retired mixed target does not exist" in p for p in problems_for(lambda r: r["retired_mixed_document_paths"].__setitem__(mixed_old, "exports/markdown_views/missing.md")))
    assert any("project driver cannot be a retired mixed old path" in p for p in problems_for(lambda r: r["retired_mixed_document_paths"].__setitem__("docs/driver.md", mixed_target)))
    assert any("conflicts with archived_document_paths" in p for p in problems_for(lambda r: (r.__setitem__("archived_document_paths", {mixed_old: "archive/docs/audits/中文说明.md"}), r["retired_mixed_document_paths"].__setitem__(mixed_old, mixed_target))))
    assert any("conflicts with retired_generated_document_paths" in p for p in problems_for(lambda r: (r.__setitem__("retired_generated_document_paths", {mixed_old: mixed_target}), r["retired_mixed_document_paths"].__setitem__(mixed_old, mixed_target))))
    assert any("retired mixed target is mapped from multiple old paths" in p for p in problems_for(lambda r: r["retired_mixed_document_paths"].__setitem__("docs/second.md", mixed_target)))
    assert any("retired mixed target must be under exports/ or archive/docs/" in p for p in problems_for(lambda r: r["retired_mixed_document_paths"].__setitem__(mixed_old, "exports/../data/existing.md")))
    assert any("retired mixed old path must be under docs/" in p for p in problems_for(lambda r: r["retired_mixed_document_paths"].__setitem__("docs/../README.md", mixed_target)))


def test_report_summary_prefers_current_export_only_todo_over_retired_history(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    seed_repo(repo)
    docs_tool = load_docs_tool(repo)
    retired_old = "docs/generated.md"
    retired_target = "exports/markdown_views/generated.md"
    (repo / "exports" / "markdown_views").mkdir(parents=True)
    write(repo / retired_target, "# Generated export\n")
    run_git(repo, "add", retired_target)
    run_git(repo, "rm", retired_old)
    write(repo / "docs" / "generated_later.md", "# Later generated\n自动生成。\n")
    run_git(repo, "add", "docs/generated_later.md")
    commit_all(repo, "retire one generated doc and add another pending one")

    registry = valid_registry(repo, docs_tool.build_inventory("HEAD"))
    registry["documents"] = [doc for doc in registry["documents"] if doc["path"] != retired_old]
    pending_doc = next(doc for doc in registry["documents"] if doc["path"] == "docs/generated_later.md")
    pending_doc.update(
        {
            "document_type": "generated_view",
            "lifecycle_status": "generated",
            "proposed_action": "regenerate_only",
            "content_role": "generated_output",
            "placement_action": "move_to_exports",
            "placement_targets": ["exports/markdown_views/generated_later.md"],
            "placement_reason": "临时仓库新增待迁出生成视图，测试当前候选摘要仍应显示待办。",
            "semantic_verification_required": False,
            "generator_candidates": ["scripts/make_docs.py"],
            "unique_source_risk": False,
        }
    )
    registry["retired_generated_document_paths"] = {retired_old: retired_target}
    registry_path = write_registry(repo, registry)
    commit_all(repo, "registry")

    assert docs_tool.check_registry(str(registry_path.relative_to(repo))) == []
    report = docs_tool.build_report(str(registry_path.relative_to(repo)))
    summary = report.split("## 当前候选摘要", 1)[1].split("## 9. 范围声明", 1)[0]
    assert "当前待迁出 exports" in summary
    assert "docs/generated_later.md" in summary
    assert "已完成" not in summary
    assert "Batch 1" not in report


def test_report_summary_prefers_current_split_todo_over_retired_history(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    seed_repo(repo)
    docs_tool = load_docs_tool(repo)
    mixed_old = "docs/generated.md"
    mixed_target = "exports/markdown_views/generated.md"
    (repo / "exports" / "markdown_views").mkdir(parents=True)
    write(repo / mixed_target, "# Generated export\n")
    run_git(repo, "add", mixed_target)
    run_git(repo, "rm", mixed_old)
    write(repo / "docs" / "mixed_later.md", "# Later mixed\n")
    run_git(repo, "add", "docs/mixed_later.md")
    commit_all(repo, "retire one mixed doc and add another pending one")

    registry = valid_registry(repo, docs_tool.build_inventory("HEAD"))
    registry["documents"] = [doc for doc in registry["documents"] if doc["path"] != mixed_old]
    pending_doc = next(doc for doc in registry["documents"] if doc["path"] == "docs/mixed_later.md")
    pending_doc.update(
        {
            "document_type": "operational_guide",
            "lifecycle_status": "active",
            "proposed_action": "keep",
            "content_role": "mixed",
            "placement_action": "split_keep_rules_generate_state",
            "placement_targets": ["exports/markdown_views/mixed_later.md"],
            "placement_reason": "临时仓库新增待拆 mixed 文档，测试当前候选摘要仍应显示待办。",
            "semantic_verification_required": False,
            "unique_source_risk": True,
        }
    )
    registry["retired_mixed_document_paths"] = {mixed_old: mixed_target}
    registry_path = write_registry(repo, registry)
    commit_all(repo, "registry")

    assert docs_tool.check_registry(str(registry_path.relative_to(repo))) == []
    report = docs_tool.build_report(str(registry_path.relative_to(repo)))
    summary = report.split("## 当前候选摘要", 1)[1].split("## 9. 范围声明", 1)[0]
    assert "当前待拆分 mixed 文档" in summary
    assert "docs/mixed_later.md" in summary
    assert "已完成" not in summary
    assert "Batch 2" not in report


def test_report_summary_has_no_historical_completion_when_no_needs_human_docs(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    seed_repo(repo)
    docs_tool = load_docs_tool(repo)
    registry = valid_registry(repo, docs_tool.build_inventory("HEAD"))
    assert not any(doc["lifecycle_status"] == "needs_human_confirmation" for doc in registry["documents"])
    registry_path = write_registry(repo, registry)
    commit_all(repo, "registry")

    report = docs_tool.build_report(str(registry_path.relative_to(repo)))
    summary = report.split("## 当前候选摘要", 1)[1].split("## 9. 范围声明", 1)[0]

    assert "当前待迁出 exports" in summary
    assert "docs/generated.md" in summary
    assert "Batch 6" not in report
    assert "已完成：历史治理材料已归档，不再等待逐份确认。" not in report
    assert "仅用户确认后三份历史治理材料才执行。" not in report


def test_report_outputs_candidate_sections_and_cli_return_codes(tmp_path: Path, capfd: pytest.CaptureFixture[str]) -> None:
    repo = init_repo(tmp_path)
    seed_repo(repo)
    archived_path = "archive/docs/audits/old-audit.md"
    write(repo / archived_path, "# Old Audit\n")
    commit_all(repo, "add archived doc")
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
    registry["documents"][2]["document_type"] = "historical_snapshot"
    registry["documents"][2]["unique_source_risk"] = False
    review_path = registry["documents"][2]["path"]
    mixed_doc = next(doc for doc in registry["documents"] if doc["path"] == "docs/中文说明.md")
    mixed_doc["content_role"] = "mixed"
    mixed_doc["placement_action"] = "split_keep_rules_generate_state"
    mixed_doc["placement_targets"] = ["data/configs/视图配置/test.json", "exports/markdown_views/test.md"]
    mixed_doc["placement_reason"] = "临时仓库 mixed 文档，测试不应进入事实源吸收章节。"
    instance_doc = next(doc for doc in registry["documents"] if doc["path"] == "docs/dup-a.md")
    instance_doc["content_role"] = "instance_record"
    instance_doc["placement_action"] = "absorb_into_canonical_data_then_export"
    instance_doc["placement_targets"] = ["data/evidence_cards.jsonl", "exports/markdown_views/dup-a.md"]
    instance_doc["placement_reason"] = "临时仓库 instance 文档，测试事实源吸收章节。"
    instance_doc["semantic_verification_required"] = True
    for doc in registry["documents"]:
        if doc["path"] == archived_path:
            doc["lifecycle_status"] = "historical"
            doc["proposed_action"] = "keep"
            doc["document_type"] = "audit_record"
            doc["human_confirmation_required"] = False
    registry["archived_document_paths"] = {"docs/old-audit.md": archived_path}
    registry_path = write_registry(repo, registry)
    commit_all(repo, "registry")

    report = docs_tool.build_report(str(registry_path.relative_to(repo)))
    assert "docs registry 覆盖文档数" in report
    assert "其中当前 `docs/` 层" in report
    assert "### 内容角色统计" in report
    assert "### 推荐归置动作统计" in report
    assert "## 当前仅保留 exports 候选" in report
    assert "## 已迁出 docs 的生成文档摘要" in report
    assert "## 已迁出 docs 的混合审核文档摘要" in report
    assert "## 当前内容归置待确认项" in report
    assert "## 当前生命周期 archive candidates" in report
    assert "## 当前生命周期 delete candidates" in report
    assert "## 当前生命周期 review / needs human confirmation" in report
    assert "## 历史归档摘要" in report
    assert "## 当前候选摘要" in report
    canonical_section = report.split("## 6. 事实源对账待办", 1)[1].split("## 当前仅保留 exports 候选", 1)[0]
    mixed_section = report.split("## 当前待拆分的混合文档", 1)[1].split("## 当前吸收后归档候选", 1)[0]
    lifecycle_review_section = report.split("## 当前生命周期 review / needs human confirmation", 1)[1].split("## 历史归档摘要", 1)[0]
    candidate_summary = report.split("## 当前候选摘要", 1)[1].split("## 9. 范围声明", 1)[0]
    assert "docs/dup-a.md" in canonical_section
    assert "docs/中文说明.md" not in canonical_section
    assert "docs/中文说明.md" in mixed_section
    assert "historical archive documents" in report
    assert "docs/old-audit.md" not in report
    assert review_path in lifecycle_review_section
    assert "当前事实源对账待办" in candidate_summary
    assert "当前待拆分 mixed 文档" in candidate_summary
    assert "当前 lifecycle review / needs human confirmation" in candidate_summary
    assert "Batch 6：needs-human-confirmation 历史材料" not in report
    assert "Batch 7：规则方法层归置核对" not in report
    assert "本报告对应 PR #206" not in report
    assert "推荐 #207" not in report
    assert not re.search(r"PR #\d+", report)
    assert "#207" not in report
    assert "本 PR" not in report
    assert docs_tool.main(["check", "--registry", str(registry_path.relative_to(repo))]) == 0
    assert docs_tool.main(["check", "--registry", "docs/missing.json"]) == 1
    captured = capfd.readouterr()
    assert "registry file is missing" in captured.err
