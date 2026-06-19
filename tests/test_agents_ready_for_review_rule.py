from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from _git_helpers import changed_files_against_base, git_changed_files

ALLOWED_CHANGED_FILES = {
    "AGENTS.md",
    "tests/_git_helpers.py",
    "tests/test_agents_ready_for_review_rule.py",
    "tests/test_file_governance_policy.py",
    "tests/test_file_governance_report.py",
    "tests/test_redundant_file_candidates_report.py",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def changed_files() -> set[str]:
    return (
        changed_files_against_base()
        | git_changed_files("diff", "--name-only")
        | git_changed_files("diff", "--cached", "--name-only")
    )


def test_agents_contains_ready_for_review_rule() -> None:
    content = read_text(ROOT / "AGENTS.md")
    assert "开 PR 后默认直接置为 ready for review" in content
    assert "除非 Issue 明确要求 draft，否则不要保持 draft" in content
    assert "PR 说明必须粘贴最终 changed files 列表" in content


def test_pr_diff_stays_inside_issue_85_whitelist() -> None:
    assert changed_files() <= ALLOWED_CHANGED_FILES
