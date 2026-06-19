from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_CHANGED_FILES = {
    "AGENTS.md",
    "tests/test_agents_ready_for_review_rule.py",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def changed_files() -> set[str]:
    commands = [
        ["git", "-c", "core.quotepath=false", "diff", "--name-only", "origin/GPT...HEAD"],
        ["git", "-c", "core.quotepath=false", "diff", "--name-only"],
        ["git", "-c", "core.quotepath=false", "diff", "--cached", "--name-only"],
    ]
    files: set[str] = set()
    for command in commands:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, check=False)
        if result.returncode != 0:
            continue
        stdout = result.stdout.decode("utf-8")
        files.update(line.strip().replace("\\", "/") for line in stdout.splitlines() if line.strip())
    return files


def test_agents_contains_ready_for_review_rule() -> None:
    content = read_text(ROOT / "AGENTS.md")
    assert "开 PR 后默认直接置为 ready for review" in content
    assert "除非 Issue 明确要求 draft，否则不要保持 draft" in content
    assert "任何 PR 都必须粘贴最终 `git diff --name-only`" in content


def test_pr_diff_stays_inside_issue_85_whitelist() -> None:
    assert changed_files() <= ALLOWED_CHANGED_FILES
