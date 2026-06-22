from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "scripts" / "dev" / "pr_body_tool.py"
DOC_PATH = ROOT / "docs" / "scripts目录规范.md"


def load_pr_body_tool(repo_root: Path | None = None):
    spec = importlib.util.spec_from_file_location("pr_body_tool_under_test", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if repo_root is not None:
        module.ROOT = repo_root
    return module


def test_pr_body_tool_file_exists() -> None:
    assert TOOL_PATH.exists()


def test_normal_chinese_markdown_with_fence_passes(tmp_path: Path) -> None:
    body = tmp_path / "中文PR.md"
    body.write_text(
        "# 标题\n\n正文包含中文路径 `docs/scripts目录规范.md`。\n\n```text\nscripts/dev/pr_body_tool.py\n```\n",
        encoding="utf-8",
    )

    tool = load_pr_body_tool(tmp_path)

    tool.validate_file(body)


def test_normalize_writes_utf8_no_bom_and_lf(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    target = tmp_path / "out.md"
    source.write_bytes(b"\xef\xbb\xbf# Title\r\n\r\n```text\r\nok\r\n```\r\n")

    tool = load_pr_body_tool(tmp_path)
    tool.normalize_file(source, target)

    data = target.read_bytes()
    assert not data.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in data
    assert target.read_text(encoding="utf-8") == "# Title\n\n```text\nok\n```\n"


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("bad\x0bchar\n", "control characters"),
        ("bad � char\n", "U\\+FFFD"),
        ("bad ??? char\n", "encoding anomaly"),
        ("```text\nmissing close\n", "must be paired"),
        ("`\\text\n", "damaged Markdown code fence"),
    ],
)
def test_validate_rejects_corrupt_body(tmp_path: Path, payload: str, message: str) -> None:
    body = tmp_path / "body.md"
    body.write_text(payload, encoding="utf-8")
    tool = load_pr_body_tool(tmp_path)

    with pytest.raises(tool.PrBodyError, match=message):
        tool.validate_file(body)


def test_apply_does_not_call_gh_when_validate_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    body = tmp_path / "body.md"
    body.write_text("bad\x0bchar\n", encoding="utf-8")
    tool = load_pr_body_tool(tmp_path)
    called = False

    def fake_run(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(tool.subprocess, "run", fake_run)

    with pytest.raises(tool.PrBodyError):
        tool.apply_pr_body("185", body)
    assert called is False


def test_apply_uses_body_file_and_never_body_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    body = tmp_path / "body.md"
    body.write_text("# 标题\n\n```text\nok\n```\n", encoding="utf-8")
    tool = load_pr_body_tool(tmp_path)
    calls: list[list[str]] = []

    monkeypatch.setattr(tool.shutil, "which", lambda name: "gh.exe" if name == "gh" else None)

    def fake_run(args, cwd, check):
        calls.append(args)

    monkeypatch.setattr(tool.subprocess, "run", fake_run)

    tool.apply_pr_body("185", body)

    assert calls == [["gh", "pr", "edit", "185", "--body-file", str(body.resolve())]]
    assert "--body" not in calls[0]
    assert body.read_text(encoding="utf-8") not in calls[0]


def test_docs_and_agents_rules_exist() -> None:
    assert DOC_PATH.exists()
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "scripts/dev/pr_body_tool.py" in agents
    assert "--body-file" in agents
