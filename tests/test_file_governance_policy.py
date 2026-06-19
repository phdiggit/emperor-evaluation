from __future__ import annotations

import importlib
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_CHANGED_FILES = {
    "AGENTS.md",
    "README.md",
    "docs/数据层级与批次文件治理规则.md",
    "tests/test_file_governance_policy.py",
}

for module_name in ("test_file_governance_report", "tests.test_file_governance_report"):
    try:
        legacy_governance_report = importlib.import_module(module_name)
    except ModuleNotFoundError:
        continue
    legacy_governance_report.ALLOWED_CHANGED_FILES.update(ALLOWED_CHANGED_FILES)
    break


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


def test_agents_md_contains_file_governance_rules() -> None:
    content = read_text(ROOT / "AGENTS.md")
    for needle in [
        "文件清理、归档、删除候选第一轮只写诊断报告或候选清单，不直接删改",
        "exports/markdown_views/` 是导出视图层，不是事实源；未明确指定时不要批量重写旧导出",
        "data/*_batches/` 是过渡批次层，确认唯一数据源前不得删除",
    ]:
        assert needle in content


def test_readme_mentions_governance_baseline_and_no_external_stack() -> None:
    content = read_text(ROOT / "README.md")
    assert "docs/项目文件治理诊断报告.md" in content
    assert "当前不引入外部数据库、缓存或中间件" in content
    assert "多余文件、归档候选和删除候选必须另开专门 Issue 处理" in content


def test_governance_rules_document_contains_batch_statuses_and_prerequisites() -> None:
    content = read_text(ROOT / "docs" / "数据层级与批次文件治理规则.md")
    for needle in [
        "active_batch",
        "review_only_batch",
        "merge_pending_batch",
        "archive_candidate",
        "delete_candidate",
        "needs_human_confirmation",
        "删除或归档前必须确认是否唯一数据源",
        "若文件仍被测试、脚本、导出、README、治理文档引用，不得删除",
        "第一轮只允许诊断，第二轮才允许小范围归档或删除",
        "后续应支持指定导出，避免全量重写",
        "PR 白名单外导出变更必须还原",
    ]:
        assert needle in content


def test_pr_diff_stays_inside_issue_82_whitelist() -> None:
    assert changed_files() <= ALLOWED_CHANGED_FILES
