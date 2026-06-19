from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "scripts" / "dev" / "repo_tool.py"
sys.path.insert(0, str(ROOT / "tests"))

from _git_helpers import changed_files_against_base, git_changed_files

ALLOWED_CHANGED_FILES = {
    "AGENTS.md",
    "scripts/dev/repo_tool.py",
    "tests/test_repo_tool.py",
}


def load_repo_tool(repo_root: Path):
    spec = importlib.util.spec_from_file_location("repo_tool_under_test", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = repo_root
    return module


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

    monkeypatch.setattr(repo_tool.subprocess, "run", fake_run)

    assert repo_tool.changed_files("origin/GPT...HEAD") == ["nested/more/file.txt", "中文/路径.md"]
    assert repo_tool.status_files() == ["nested/more/file.txt", "中文/路径.md"]
    assert calls[0][0][:3] == ("git", "-c", "core.quotepath=false")
    assert calls[0][3] is False
    assert calls[0][2] is True


def test_repo_tool_source_mentions_git_encoding_guards() -> None:
    content = TOOL_PATH.read_text(encoding="utf-8")
    for needle in [
        '"git", "-c", "core.quotepath=false"',
        "text=False",
        '.decode("utf-8")',
    ]:
        assert needle in content


def test_agents_contains_repo_tool_rule() -> None:
    assert "python scripts/dev/repo_tool.py read/write/replace" in (ROOT / "AGENTS.md").read_text(
        encoding="utf-8"
    )


def test_pr_diff_stays_inside_issue_93_whitelist() -> None:
    assert changed_files() <= ALLOWED_CHANGED_FILES
