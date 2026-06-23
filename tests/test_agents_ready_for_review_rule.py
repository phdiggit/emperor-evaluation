from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from _git_helpers import changed_files_against_base, git_changed_files, skip_unless_pr_diff_checks_enabled

ALLOWED_CHANGED_FILES = {
    "AGENTS.md",
    "docs/30_operations/人工阅读型Markdown导出规范.md",
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


def test_agents_contains_markdown_export_guardrails() -> None:
    content = read_text(ROOT / "AGENTS.md")
    assert "人工阅读型 Markdown 导出高压线" in content
    for needle in [
        "展示优化不得改变源数据、评分、定档、排名、warning 语义或裁判结论",
        "人工复核型 Markdown 默认纯 Markdown，不使用 HTML details",
        "不用宽表承载长字段、裁判说明、相邻项剥离说明、warning matched_fields 或 linked evidence 长字段",
        "`linked_*`、`cross_item_split_signals / 相邻项剥离说明`、warning `matched_fields` 必须全量展示，不得截断",
        "详细规范见 `docs/30_operations/人工阅读型Markdown导出规范.md`",
    ]:
        assert needle in content


def test_pr_diff_stays_inside_issue_85_whitelist() -> None:
    skip_unless_pr_diff_checks_enabled()
    assert changed_files() <= ALLOWED_CHANGED_FILES
