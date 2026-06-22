from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import time
from types import SimpleNamespace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "scripts" / "dev" / "repo_tool.py"
sys.path.insert(0, str(ROOT / "tests"))

from _git_helpers import (
    changed_files_against_base,
    git_changed_files,
    skip_unless_pr_diff_checks_enabled,
)

ALLOWED_CHANGED_FILES = {
    "AGENTS.md",
    "docs/人工阅读型Markdown导出规范.md",
    "scripts/dev/repo_tool.py",
    "tests/test_agents_ready_for_review_rule.py",
    "tests/test_file_governance_policy.py",
    "tests/test_repo_tool.py",
}


def load_repo_tool(repo_root: Path):
    spec = importlib.util.spec_from_file_location(f"repo_tool_under_test_{id(repo_root)}", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = repo_root
    return module


def run_git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=repo_root,
        capture_output=True,
        text=False,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr.decode("utf-8", errors="replace"))
    return result.stdout.decode("utf-8")


def init_git_repo(repo_root: Path) -> None:
    repo_root.mkdir(parents=True)
    run_git(repo_root, "init", "-b", "GPT")
    run_git(repo_root, "config", "user.name", "Codex Test")
    run_git(repo_root, "config", "user.email", "codex@example.test")


def commit_all(repo_root: Path, message: str) -> None:
    last_error: AssertionError | None = None
    for _ in range(3):
        try:
            run_git(repo_root, "add", ".")
            run_git(repo_root, "commit", "-m", message)
            return
        except AssertionError as exc:
            last_error = exc
            if "unable to write new index file" not in str(exc):
                raise
            lock = repo_root / ".git" / "index.lock"
            if lock.exists():
                lock.unlink()
            time.sleep(0.1)
    assert last_error is not None
    raise last_error


def write_minimal_registry(repo_root: Path) -> None:
    registry = {
        "schema_version": 1,
        "agents_budgets": {
            "AGENTS.md": {"max_lines": 85, "max_bytes": 12288},
            "scripts/AGENTS.md": {"max_lines": 90, "max_bytes": 14336},
        },
        "directories": {
            "dev": "scripts/dev",
            "validate": "scripts/validate",
            "export": "scripts/export",
            "shared": "scripts/shared",
        },
        "modules": [
            {
                "id": "tool",
                "category": "dev",
                "status": "active",
                "implementation": "scripts/dev/tool.py",
                "legacy_wrapper": None,
                "audit_docs": [],
                "required_tests": ["tests/test_tool.py"],
            }
        ],
        "root_exceptions": [],
        "default_forbidden_patterns": ["data/**", "*.sqlite", "*.db"],
    }
    target = repo_root / "docs" / "agent_rules" / "scripts_registry.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_canonical_import_registry(repo_root: Path) -> None:
    for folder in ("scripts/dev", "scripts/export", "scripts/shared", "tests", "docs/agent_rules"):
        (repo_root / folder).mkdir(parents=True, exist_ok=True)
    (repo_root / "scripts" / "shared" / "config_loaders.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo_root / "scripts" / "config_loaders.py").write_text(
        "from shared.config_loaders import *\n",
        encoding="utf-8",
    )
    (repo_root / "tests" / "test_tool.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    registry = {
        "schema_version": 1,
        "agents_budgets": {
            "AGENTS.md": {"max_lines": 85, "max_bytes": 12288},
            "scripts/AGENTS.md": {"max_lines": 90, "max_bytes": 14336},
        },
        "directories": {
            "export": "scripts/export",
            "shared": "scripts/shared",
        },
        "modules": [
            {
                "id": "export_tool",
                "category": "export",
                "status": "migrated",
                "implementation": "scripts/export/tool.py",
                "legacy_wrapper": "scripts/tool.py",
                "audit_docs": [],
                "required_tests": ["tests/test_tool.py"],
            },
            {
                "id": "dev_tool",
                "category": "dev",
                "status": "active",
                "implementation": "scripts/dev/tool.py",
                "legacy_wrapper": None,
                "audit_docs": [],
                "required_tests": ["tests/test_tool.py"],
            },
            {
                "id": "config_loaders",
                "category": "shared",
                "status": "migrated",
                "implementation": "scripts/shared/config_loaders.py",
                "legacy_wrapper": "scripts/config_loaders.py",
                "audit_docs": [],
                "required_tests": ["tests/test_tool.py"],
            },
        ],
        "root_exceptions": [],
        "default_forbidden_patterns": [],
    }
    (repo_root / "docs" / "agent_rules" / "scripts_registry.json").write_text(
        json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_retired_wrapper_registry(repo_root: Path) -> None:
    for folder in ("scripts/dev", "scripts/export", "scripts/shared", "tests", "docs/agent_rules"):
        (repo_root / folder).mkdir(parents=True, exist_ok=True)
    (repo_root / "AGENTS.md").write_text("scripts/AGENTS.md\ndocs/agent_rules/scripts_registry.json\n", encoding="utf-8")
    (repo_root / "scripts" / "AGENTS.md").write_text("docs/agent_rules/scripts_registry.json\n", encoding="utf-8")
    (repo_root / "scripts" / "publish_pr.ps1").write_text("Write-Output 'ok'\n", encoding="utf-8")
    (repo_root / "scripts" / "shared" / "config_loaders.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo_root / "scripts" / "export" / "tool.py").write_text("from shared import config_loaders\n", encoding="utf-8")
    (repo_root / "scripts" / "dev" / "tool.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo_root / "tests" / "test_tool.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    registry = {
        "schema_version": 1,
        "legacy_wrapper_policy": "retired",
        "retired_legacy_wrappers": {
            "scripts/config_loaders.py": "config_loaders",
        },
        "agents_budgets": {
            "AGENTS.md": {"max_lines": 85, "max_bytes": 12288},
            "scripts/AGENTS.md": {"max_lines": 90, "max_bytes": 14336},
        },
        "directories": {
            "dev": "scripts/dev",
            "export": "scripts/export",
            "shared": "scripts/shared",
        },
        "modules": [
            {
                "id": "config_loaders",
                "category": "shared",
                "status": "migrated",
                "implementation": "scripts/shared/config_loaders.py",
                "legacy_wrapper": None,
                "audit_docs": [],
                "required_tests": ["tests/test_tool.py"],
            },
            {
                "id": "export_tool",
                "category": "export",
                "status": "active",
                "implementation": "scripts/export/tool.py",
                "legacy_wrapper": None,
                "audit_docs": [],
                "required_tests": ["tests/test_tool.py"],
            },
            {
                "id": "dev_tool",
                "category": "dev",
                "status": "active",
                "implementation": "scripts/dev/tool.py",
                "legacy_wrapper": None,
                "audit_docs": [],
                "required_tests": ["tests/test_tool.py"],
            },
        ],
        "root_exceptions": [
            {
                "path": "scripts/publish_pr.ps1",
                "planned_category": "dev",
                "reason": "stable publisher",
                "status": "stable_entrypoint",
            }
        ],
        "default_forbidden_patterns": [],
    }
    (repo_root / "docs" / "agent_rules" / "scripts_registry.json").write_text(
        json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def changed_files() -> set[str]:
    return set(changed_files_against_base()) | set(git_changed_files("diff", "--name-only")) | set(
        git_changed_files("diff", "--cached", "--name-only")
    )


def test_repo_tool_file_exists() -> None:
    assert TOOL_PATH.exists()


def test_read_reads_utf8_bom_and_chinese_text(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "docs").mkdir(parents=True)
    target = repo_root / "docs" / "中文.txt"
    target.write_bytes(b"\xef\xbb\xbf" + "你好，Codex".encode("utf-8"))

    repo_tool = load_repo_tool(repo_root)

    assert repo_tool.read_text_file("docs/中文.txt") == "你好，Codex"


def test_write_from_writes_utf8_chinese_text(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    source = tmp_path / "source.txt"
    source.write_text("写入中文内容", encoding="utf-8")

    repo_tool = load_repo_tool(repo_root)
    repo_tool.write_text_file("notes/输出.txt", source)

    assert (repo_root / "notes" / "输出.txt").read_text(encoding="utf-8") == "写入中文内容"


def test_replace_replaces_utf8_chinese_text(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "docs").mkdir(parents=True)
    target = repo_root / "docs" / "替换.txt"
    target.write_text("旧中文旧中文", encoding="utf-8")

    repo_tool = load_repo_tool(repo_root)
    replaced = repo_tool.replace_text_file("docs/替换.txt", "旧中文", "新中文")

    assert replaced == 2
    assert target.read_text(encoding="utf-8") == "新中文新中文"


def test_binary_extension_rejected(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    repo_tool = load_repo_tool(repo_root)

    with pytest.raises(ValueError, match="binary files are not supported"):
        repo_tool.read_text_file("data/sample.sqlite")

    with pytest.raises(ValueError, match="binary files are not supported"):
        repo_tool.write_text_file("data/sample.sqlite", tmp_path / "source.txt")


def test_outside_repo_path_rejected(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    repo_tool = load_repo_tool(repo_root)

    with pytest.raises(ValueError, match="path escapes repo root"):
        repo_tool.read_text_file(tmp_path.parent / "outside.txt")


def test_git_helpers_use_safe_encoding_and_normalize_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    repo_tool = load_repo_tool(repo_root)

    class FakeResult:
        def __init__(self, stdout: bytes) -> None:
            self.stdout = stdout

    calls: list[tuple[tuple[str, ...], Path, bool, bool, bool]] = []

    def fake_run(args, cwd, capture_output, text, check):
        calls.append((tuple(args), cwd, capture_output, text, check))
        if tuple(args[3:]) == ("status", "--short", "--untracked-files=normal"):
            return FakeResult(
                "?? 中文\\路径.md\n M .tmp/cache.txt\nR  old name.md -> nested\\more\\file.txt\n".encode(
                    "utf-8"
                )
            )
        return FakeResult("中文\\路径.md\n.tmp/cache.txt\nnested\\more\\file.txt\n".encode("utf-8"))

    monkeypatch.setattr(repo_tool, "subprocess", SimpleNamespace(run=fake_run))

    assert repo_tool.changed_files("origin/GPT...HEAD") == ["nested/more/file.txt", "中文/路径.md"]
    assert repo_tool.status_files() == ["nested/more/file.txt", "中文/路径.md"]
    assert calls[0][0][:3] == ("git", "-c", "core.quotepath=false")
    assert calls[0][3] is False
    assert calls[0][2] is True


def test_snapshot_lists_chinese_paths_and_is_stable(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    init_git_repo(repo_root)
    for folder in ("scripts/dev", "scripts/validate", "scripts/export", "scripts/shared", "tests", "docs"):
        (repo_root / folder).mkdir(parents=True, exist_ok=True)
    (repo_root / "AGENTS.md").write_text("# root\n", encoding="utf-8")
    (repo_root / "scripts" / "dev" / "tool.py").write_text("print('ok')\n", encoding="utf-8")
    (repo_root / "tests" / "test_tool.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    (repo_root / "docs" / "中文说明.md").write_text("你好\n", encoding="utf-8")
    commit_all(repo_root, "initial")

    repo_tool = load_repo_tool(repo_root)
    first = repo_tool.build_snapshot("HEAD")
    second = repo_tool.build_snapshot("HEAD")

    assert first == second
    assert "docs/中文说明.md" in first["tracked_files"]
    assert first["scripts"]["dev"] == ["scripts/dev/tool.py"]
    assert first["tests"] == ["tests/test_tool.py"]


def test_snapshot_uses_registry_directories_for_build_category(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    init_git_repo(repo_root)
    for folder in ("scripts/build", "scripts/dev", "docs/agent_rules"):
        (repo_root / folder).mkdir(parents=True, exist_ok=True)
    registry = {
        "directories": {
            "build": "scripts/build",
            "dev": "scripts/dev",
        }
    }
    (repo_root / "docs" / "agent_rules" / "scripts_registry.json").write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (repo_root / "scripts" / "build" / "__init__.py").write_text("", encoding="utf-8")
    (repo_root / "scripts" / "build" / "build_db.py").write_text("print('ok')\n", encoding="utf-8")
    (repo_root / "scripts" / "dev" / "tool.py").write_text("print('ok')\n", encoding="utf-8")
    commit_all(repo_root, "initial")

    repo_tool = load_repo_tool(repo_root)
    snapshot = repo_tool.build_snapshot("HEAD")

    assert snapshot["scripts"]["build"] == [
        "scripts/build/__init__.py",
        "scripts/build/build_db.py",
    ]
    assert snapshot["scripts"]["dev"] == ["scripts/dev/tool.py"]
    assert snapshot["scripts"]["other"] == []


def test_snapshot_output_writes_utf8_no_bom(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    init_git_repo(repo_root)
    (repo_root / "AGENTS.md").write_text("# root\n", encoding="utf-8")
    commit_all(repo_root, "initial")

    repo_tool = load_repo_tool(repo_root)
    output = ".tmp/repo_context/snapshot.json"
    repo_tool.write_json_output(repo_tool.build_snapshot("HEAD"), output)

    data = (repo_root / output).read_bytes()
    assert not data.startswith(b"\xef\xbb\xbf")
    assert json.loads(data.decode("utf-8"))["ref"] == "HEAD"


def test_pr_context_detects_added_modified_and_rename(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    init_git_repo(repo_root)
    for folder in ("scripts/dev", "scripts/validate", "scripts/export", "scripts/shared", "tests", "docs"):
        (repo_root / folder).mkdir(parents=True, exist_ok=True)
    (repo_root / "scripts" / "dev" / "tool.py").write_text("ROOT = 1\n", encoding="utf-8")
    (repo_root / "scripts" / "old_name.py").write_text("print('old')\n", encoding="utf-8")
    (repo_root / "tests" / "test_tool.py").write_text("scripts/dev/tool.py\n", encoding="utf-8")
    write_minimal_registry(repo_root)
    commit_all(repo_root, "base")
    base_sha = run_git(repo_root, "rev-parse", "HEAD").strip()

    (repo_root / "scripts" / "dev" / "tool.py").write_text("ROOT = 2\n", encoding="utf-8")
    (repo_root / "docs" / "new.md").write_text("new\n", encoding="utf-8")
    run_git(repo_root, "mv", "scripts/old_name.py", "scripts/new_name.py")
    commit_all(repo_root, "change")

    repo_tool = load_repo_tool(repo_root)
    context = repo_tool.build_pr_context(base_sha, "HEAD")
    by_path = {item["path"]: item for item in context["changed_files"]}

    assert context["base_sha"] == base_sha
    assert context["head_sha"] == run_git(repo_root, "rev-parse", "HEAD").strip()
    assert context["merge_base_sha"] == base_sha
    assert by_path["docs/new.md"]["status"] == "A"
    assert by_path["scripts/dev/tool.py"]["status"] == "M"
    assert by_path["scripts/new_name.py"]["status"] == "R"
    assert by_path["scripts/new_name.py"]["additions"] == 0
    assert by_path["scripts/new_name.py"]["deletions"] == 0
    assert context["renames"] == [{"old_path": "scripts/old_name.py", "path": "scripts/new_name.py"}]
    assert {"path": "scripts/new_name.py", "risk": "moved_python_file"} in context["path_risks"]
    assert any(risk["risk"] == "patch_touches_root" for risk in context["path_risks"])


def test_parse_numstat_path_keeps_brace_rename_prefix(tmp_path: Path) -> None:
    repo_tool = load_repo_tool(tmp_path)

    assert repo_tool._parse_numstat_path("scripts/{old_name.py => new_name.py}") == "scripts/new_name.py"
    assert repo_tool._parse_numstat_path("scripts/{old => new}/tool.py") == "scripts/new/tool.py"


def test_scope_check_blocks_forbid_and_untracked_files(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    init_git_repo(repo_root)
    (repo_root / "scripts" / "dev").mkdir(parents=True)
    (repo_root / "tests").mkdir()
    (repo_root / "scripts" / "dev" / "tool.py").write_text("print('ok')\n", encoding="utf-8")
    (repo_root / "tests" / "test_tool.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    write_minimal_registry(repo_root)
    commit_all(repo_root, "base")

    (repo_root / "data").mkdir()
    (repo_root / "data" / "bad.json").write_text("{}\n", encoding="utf-8")

    repo_tool = load_repo_tool(repo_root)
    problems = repo_tool.check_scope("HEAD", [], [], [])

    assert problems == ["data/bad.json: forbid=data/**"]


def test_scope_check_supports_allow_and_ignores_tmp(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    init_git_repo(repo_root)
    (repo_root / "scripts" / "dev").mkdir(parents=True)
    (repo_root / "tests").mkdir()
    (repo_root / "docs").mkdir()
    (repo_root / "scripts" / "dev" / "tool.py").write_text("print('ok')\n", encoding="utf-8")
    (repo_root / "tests" / "test_tool.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    write_minimal_registry(repo_root)
    commit_all(repo_root, "base")

    (repo_root / "docs" / "ok.md").write_text("ok\n", encoding="utf-8")
    (repo_root / "tests" / "bad.py").write_text("bad\n", encoding="utf-8")
    (repo_root / ".tmp" / "repo_context").mkdir(parents=True)
    (repo_root / ".tmp" / "repo_context" / "ignored.json").write_text("{}\n", encoding="utf-8")

    repo_tool = load_repo_tool(repo_root)
    problems = repo_tool.check_scope("HEAD", [], ["docs/**"], [])

    assert problems == ["tests/bad.py: not allowed by --allow"]


def test_agents_check_reports_budget_missing_paths_and_root_coverage(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    for folder in ("scripts/dev", "scripts/validate", "scripts/export", "scripts/shared", "tests", "docs/agent_rules"):
        (repo_root / folder).mkdir(parents=True, exist_ok=True)
    (repo_root / "AGENTS.md").write_text("scripts/AGENTS.md\ndocs/agent_rules/scripts_registry.json\nextra\n", encoding="utf-8")
    (repo_root / "scripts" / "AGENTS.md").write_text("docs/agent_rules/scripts_registry.json\n", encoding="utf-8")
    (repo_root / "scripts" / "dev" / "tool.py").write_text("print('ok')\n", encoding="utf-8")
    (repo_root / "scripts" / "loose.py").write_text("print('loose')\n", encoding="utf-8")
    registry = {
        "schema_version": 1,
        "agents_budgets": {
            "AGENTS.md": {"max_lines": 1, "max_bytes": 10},
            "scripts/AGENTS.md": {"max_lines": 90, "max_bytes": 14336},
        },
        "directories": {
            "dev": "scripts/dev",
            "validate": "scripts/validate",
            "export": "scripts/export",
            "shared": "scripts/shared",
        },
        "modules": [
            {
                "id": "tool",
                "category": "dev",
                "status": "active",
                "implementation": "scripts/dev/missing.py",
                "legacy_wrapper": None,
                "audit_docs": [],
                "required_tests": ["tests/missing_test.py"],
            }
        ],
        "root_exceptions": [],
        "default_forbidden_patterns": [],
    }
    registry_path = repo_root / "docs" / "agent_rules" / "scripts_registry.json"
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    repo_tool = load_repo_tool(repo_root)
    problems = repo_tool.check_agents()

    assert "AGENTS.md: 3 lines exceeds 1" in problems
    assert "AGENTS.md: 66 bytes exceeds 10" in problems
    assert "scripts/dev/missing.py: implementation path missing for tool" in problems
    assert "tests/missing_test.py: missing required_tests path for tool" in problems
    assert "scripts/loose.py: root script is neither legacy_wrapper nor root_exception" in problems


def test_agents_check_requires_reason_for_custom_wrapper_line_limit(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    for folder in ("scripts/dev", "scripts/validate", "scripts/export", "scripts/shared", "tests", "docs/agent_rules"):
        (repo_root / folder).mkdir(parents=True, exist_ok=True)
    (repo_root / "AGENTS.md").write_text("scripts/AGENTS.md\ndocs/agent_rules/scripts_registry.json\n", encoding="utf-8")
    (repo_root / "scripts" / "AGENTS.md").write_text("docs/agent_rules/scripts_registry.json\n", encoding="utf-8")
    (repo_root / "scripts" / "dev" / "tool.py").write_text("print('ok')\n", encoding="utf-8")
    (repo_root / "scripts" / "tool.py").write_text("from dev.tool import *\n", encoding="utf-8")
    (repo_root / "tests" / "test_tool.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    registry = {
        "schema_version": 1,
        "agents_budgets": {
            "AGENTS.md": {"max_lines": 85, "max_bytes": 12288},
            "scripts/AGENTS.md": {"max_lines": 90, "max_bytes": 14336},
        },
        "directories": {
            "dev": "scripts/dev",
            "validate": "scripts/validate",
            "export": "scripts/export",
            "shared": "scripts/shared",
        },
        "modules": [
            {
                "id": "tool",
                "category": "dev",
                "status": "migrated",
                "implementation": "scripts/dev/tool.py",
                "legacy_wrapper": "scripts/tool.py",
                "max_wrapper_lines": 40,
                "audit_docs": [],
                "required_tests": ["tests/test_tool.py"],
            }
        ],
        "root_exceptions": [],
        "default_forbidden_patterns": [],
    }
    (repo_root / "docs" / "agent_rules" / "scripts_registry.json").write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    repo_tool = load_repo_tool(repo_root)
    problems = repo_tool.check_agents()

    assert "scripts/tool.py: custom max_wrapper_lines requires exception_reason" in problems


def test_agents_check_scans_wrapper_markers_even_with_exception_reason(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    for folder in ("scripts/dev", "scripts/validate", "scripts/export", "scripts/shared", "tests", "docs/agent_rules"):
        (repo_root / folder).mkdir(parents=True, exist_ok=True)
    (repo_root / "AGENTS.md").write_text("scripts/AGENTS.md\ndocs/agent_rules/scripts_registry.json\n", encoding="utf-8")
    (repo_root / "scripts" / "AGENTS.md").write_text("docs/agent_rules/scripts_registry.json\n", encoding="utf-8")
    (repo_root / "scripts" / "dev" / "tool.py").write_text("print('ok')\n", encoding="utf-8")
    wrapper_body = "\n".join(["from dev.tool import *", "def build():", "    return 'not a wrapper'"]) + "\n"
    (repo_root / "scripts" / "tool.py").write_text(wrapper_body, encoding="utf-8")
    (repo_root / "tests" / "test_tool.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    registry = {
        "schema_version": 1,
        "agents_budgets": {
            "AGENTS.md": {"max_lines": 85, "max_bytes": 12288},
            "scripts/AGENTS.md": {"max_lines": 90, "max_bytes": 14336},
        },
        "directories": {
            "dev": "scripts/dev",
            "validate": "scripts/validate",
            "export": "scripts/export",
            "shared": "scripts/shared",
        },
        "modules": [
            {
                "id": "tool",
                "category": "dev",
                "status": "migrated",
                "implementation": "scripts/dev/tool.py",
                "legacy_wrapper": "scripts/tool.py",
                "max_wrapper_lines": 40,
                "exception_reason": "temporary compatibility shim",
                "audit_docs": [],
                "required_tests": ["tests/test_tool.py"],
            }
        ],
        "root_exceptions": [],
        "default_forbidden_patterns": [],
    }
    (repo_root / "docs" / "agent_rules" / "scripts_registry.json").write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    repo_tool = load_repo_tool(repo_root)
    problems = repo_tool.check_agents()

    assert "scripts/tool.py: wrapper appears to contain implementation marker 'def build'" in problems


def test_canonical_imports_report_legacy_import(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    write_canonical_import_registry(repo_root)
    (repo_root / "scripts" / "export" / "tool.py").write_text("import config_loaders\n", encoding="utf-8")

    repo_tool = load_repo_tool(repo_root)

    assert repo_tool.check_canonical_imports() == [
        "scripts/export/tool.py: imports legacy wrapper module 'config_loaders'; use 'shared.config_loaders'"
    ]


def test_canonical_imports_scan_implementation_without_legacy_wrapper(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    write_canonical_import_registry(repo_root)
    (repo_root / "scripts" / "export" / "tool.py").write_text("from shared import config_loaders\n", encoding="utf-8")
    (repo_root / "scripts" / "dev" / "tool.py").write_text("import config_loaders\n", encoding="utf-8")

    repo_tool = load_repo_tool(repo_root)

    assert repo_tool.check_canonical_imports() == [
        "scripts/dev/tool.py: imports legacy wrapper module 'config_loaders'; use 'shared.config_loaders'"
    ]


def test_canonical_imports_report_alias_and_from_import(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    write_canonical_import_registry(repo_root)
    (repo_root / "scripts" / "export" / "tool.py").write_text(
        "import config_loaders as loaders\nfrom config_loaders import load_config\n",
        encoding="utf-8",
    )

    repo_tool = load_repo_tool(repo_root)
    problems = repo_tool.check_canonical_imports()

    assert problems == [
        "scripts/export/tool.py: imports legacy wrapper module 'config_loaders'; use 'shared.config_loaders'"
    ]


def test_canonical_imports_allow_canonical_dotted_and_package_imports(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    write_canonical_import_registry(repo_root)
    (repo_root / "scripts" / "export" / "tool.py").write_text(
        "import shared.config_loaders\nfrom shared import config_loaders\n"
        "from shared.config_loaders import VALUE\n",
        encoding="utf-8",
    )

    repo_tool = load_repo_tool(repo_root)

    assert repo_tool.check_canonical_imports() == []


def test_canonical_imports_use_retired_wrapper_mapping(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    write_retired_wrapper_registry(repo_root)
    (repo_root / "scripts" / "export" / "tool.py").write_text("import config_loaders\n", encoding="utf-8")

    repo_tool = load_repo_tool(repo_root)

    assert repo_tool.check_canonical_imports() == [
        "scripts/export/tool.py: imports legacy wrapper module 'config_loaders'; use 'shared.config_loaders'"
    ]


def test_agents_check_allows_zero_active_wrappers_when_policy_retired(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    write_retired_wrapper_registry(repo_root)

    repo_tool = load_repo_tool(repo_root)

    assert repo_tool.check_agents() == []


def test_agents_check_rejects_active_wrapper_when_policy_retired(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    write_retired_wrapper_registry(repo_root)
    registry_path = repo_root / "docs" / "agent_rules" / "scripts_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["modules"][0]["legacy_wrapper"] = "scripts/config_loaders.py"
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    repo_tool = load_repo_tool(repo_root)

    assert (
        "scripts/config_loaders.py: legacy_wrapper must be null when legacy_wrapper_policy is retired"
        in repo_tool.check_agents()
    )


def test_agents_check_rejects_existing_retired_path(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    write_retired_wrapper_registry(repo_root)
    (repo_root / "scripts" / "config_loaders.py").write_text("from shared.config_loaders import *\n", encoding="utf-8")

    repo_tool = load_repo_tool(repo_root)
    problems = repo_tool.check_agents()

    assert "scripts/config_loaders.py: retired legacy wrapper path still exists" in problems
    assert "scripts/config_loaders.py: scripts root Python wrappers are retired and must not exist" in problems


def test_agents_check_rejects_unknown_retired_module_id(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    write_retired_wrapper_registry(repo_root)
    registry_path = repo_root / "docs" / "agent_rules" / "scripts_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["retired_legacy_wrappers"]["scripts/missing.py"] = "missing"
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    repo_tool = load_repo_tool(repo_root)

    assert "scripts/missing.py: retired legacy wrapper references unknown module id 'missing'" in repo_tool.check_agents()


def test_agents_check_rejects_retired_path_root_exception_conflict(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    write_retired_wrapper_registry(repo_root)
    registry_path = repo_root / "docs" / "agent_rules" / "scripts_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["root_exceptions"].append(
        {
            "path": "scripts/config_loaders.py",
            "planned_category": "shared",
            "reason": "invalid conflict",
            "status": "stable_entrypoint",
        }
    )
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    repo_tool = load_repo_tool(repo_root)

    assert "scripts/config_loaders.py: retired legacy wrapper cannot be a root exception" in repo_tool.check_agents()


def test_agents_check_rejects_new_root_python_file_when_policy_retired(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    write_retired_wrapper_registry(repo_root)
    (repo_root / "scripts" / "loose.py").write_text("print('no')\n", encoding="utf-8")

    repo_tool = load_repo_tool(repo_root)
    problems = repo_tool.check_agents()

    assert "scripts/loose.py: root script is neither legacy_wrapper nor root_exception" in problems
    assert "scripts/loose.py: scripts root Python wrappers are retired and must not exist" in problems


def test_canonical_imports_collect_multiple_files_and_syntax_errors(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    write_canonical_import_registry(repo_root)
    (repo_root / "scripts" / "export" / "tool.py").write_text("import config_loaders\n", encoding="utf-8")
    (repo_root / "scripts" / "shared" / "config_loaders.py").write_text("from config_loaders.submodule import x\n", encoding="utf-8")
    registry_path = repo_root / "docs" / "agent_rules" / "scripts_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["modules"].append(
        {
            "id": "bad_syntax",
            "category": "export",
            "status": "migrated",
            "implementation": "scripts/export/bad_syntax.py",
            "legacy_wrapper": "scripts/bad_syntax.py",
            "audit_docs": [],
            "required_tests": ["tests/test_tool.py"],
        }
    )
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (repo_root / "scripts" / "export" / "bad_syntax.py").write_text("def broken(:\n", encoding="utf-8")
    (repo_root / "scripts" / "bad_syntax.py").write_text("from export.bad_syntax import *\n", encoding="utf-8")

    repo_tool = load_repo_tool(repo_root)
    problems = repo_tool.check_canonical_imports()

    assert "scripts/export/tool.py: imports legacy wrapper module 'config_loaders'; use 'shared.config_loaders'" in problems
    assert "scripts/shared/config_loaders.py: imports legacy wrapper module 'config_loaders'; use 'shared.config_loaders'" in problems
    assert "scripts/export/bad_syntax.py: SyntaxError at line 1: invalid syntax" in problems


def test_canonical_imports_skip_legacy_wrapper_itself(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    write_canonical_import_registry(repo_root)
    (repo_root / "scripts" / "export" / "tool.py").write_text("from shared import config_loaders\n", encoding="utf-8")
    (repo_root / "scripts" / "tool.py").write_text("import config_loaders\n", encoding="utf-8")

    repo_tool = load_repo_tool(repo_root)

    assert repo_tool.check_canonical_imports() == []


def test_canonical_imports_cli_return_codes(tmp_path: Path, capfd: pytest.CaptureFixture[str]) -> None:
    repo_root = tmp_path / "repo"
    write_canonical_import_registry(repo_root)
    (repo_root / "scripts" / "export" / "tool.py").write_text("from shared import config_loaders\n", encoding="utf-8")
    repo_tool = load_repo_tool(repo_root)

    assert repo_tool.main(["canonical-imports-check"]) == 0

    (repo_root / "scripts" / "export" / "tool.py").write_text("import config_loaders\n", encoding="utf-8")

    assert repo_tool.main(["canonical-imports-check"]) == 1
    captured = capfd.readouterr()
    assert "scripts/export/tool.py: imports legacy wrapper module 'config_loaders'; use 'shared.config_loaders'" in captured.err


def test_agents_check_reuses_canonical_imports_check(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    write_canonical_import_registry(repo_root)
    (repo_root / "AGENTS.md").write_text("scripts/AGENTS.md\ndocs/agent_rules/scripts_registry.json\n", encoding="utf-8")
    (repo_root / "scripts" / "AGENTS.md").write_text("docs/agent_rules/scripts_registry.json\n", encoding="utf-8")
    (repo_root / "scripts" / "export" / "tool.py").write_text("import config_loaders\n", encoding="utf-8")
    (repo_root / "scripts" / "tool.py").write_text("from export.tool import *\n", encoding="utf-8")

    repo_tool = load_repo_tool(repo_root)

    assert "scripts/export/tool.py: imports legacy wrapper module 'config_loaders'; use 'shared.config_loaders'" in repo_tool.check_agents()


def test_repo_tool_source_mentions_git_encoding_guards() -> None:
    content = TOOL_PATH.read_text(encoding="utf-8")
    for needle in [
        '"git", "-c", "core.quotepath=false"',
        "text=False",
        '.decode("utf-8")',
    ]:
        assert needle in content


def test_agents_links_human_readable_markdown_spec() -> None:
    assert "docs/人工阅读型Markdown导出规范.md" in (ROOT / "AGENTS.md").read_text(encoding="utf-8")


def test_pr_diff_stays_inside_issue_93_whitelist() -> None:
    skip_unless_pr_diff_checks_enabled()
    assert changed_files() <= ALLOWED_CHANGED_FILES
