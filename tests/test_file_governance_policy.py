from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from _git_helpers import changed_files_against_base, git_changed_files, skip_unless_pr_diff_checks_enabled

ALLOWED_CHANGED_FILES = {
    "AGENTS.md",
    "README.md",
    "docs/README.md",
    "docs/00_project/README.md",
    "docs/10_methodology/README.md",
    "docs/20_dimensions/README.md",
    "docs/30_operations/README.md",
    "docs/AGENTS.md",
    "docs/agent_rules/README.md",
    "docs/agent_rules/docs_registry.json",
    "docs/人工阅读型Markdown导出规范.md",
    "docs/数据层级与批次文件治理规则.md",
    "exports/governance/文档治理盘点报告.md",
    "tests/test_docs_governance.py",
    "tests/test_docs_tool.py",
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
    return (
        changed_files_against_base()
        | git_changed_files("diff", "--name-only")
        | git_changed_files("diff", "--cached", "--name-only")
    )


def test_agents_md_contains_file_governance_rules() -> None:
    content = read_text(ROOT / "AGENTS.md")
    for needle in [
        "展示优化不得改变源数据、评分、定档、排名、warning 语义或裁判结论",
        "人工复核型 Markdown 默认纯 Markdown，不使用 HTML details",
        "详细规范见 `docs/人工阅读型Markdown导出规范.md`",
    ]:
        assert needle in content


def test_human_readable_markdown_spec_contains_detailed_rules() -> None:
    content = read_text(ROOT / "docs" / "人工阅读型Markdown导出规范.md")
    for needle in [
        "不使用 `<details>`、`<summary>`、`</details>`",
        "详情页不要使用宽表承载长字段、裁判说明、相邻项剥离说明、warning `matched_fields` 或 linked evidence 长字段",
        "`linked_*` 字段必须全量展示，不得隐藏",
        "`cross_item_split_signals / 相邻项剥离说明` 必须全量展示，不得隐藏",
        "warning `matched_fields / 命中字段` 必须全量展示，不得截断",
        "不使用 `……（共N项）` 或类似文案截断长列表",
        "[李世民详情](./第五项B自动结算草案_李世民.md)",
    ]:
        assert needle in content


def test_readme_mentions_governance_baseline_and_no_external_stack() -> None:
    content = read_text(ROOT / "README.md")
    assert "exports/governance/文档治理盘点报告.md" in content
    assert "archive/docs/" in content
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


def test_file_governance_allowlist_has_no_one_off_migration_paths() -> None:
    forbidden_prefixes = (
        ".tmp/",
        "archive/docs/",
        "data/",
        "exports/markdown_views/",
    )
    forbidden_exact_paths = {
        "docs/文档治理盘点报告.md",
    }
    forbidden_fragments = (
        "_20260620",
        "_20260621",
    )

    offenders = {
        path
        for path in ALLOWED_CHANGED_FILES
        if path in forbidden_exact_paths
        or path.startswith(forbidden_prefixes)
        or any(fragment in path for fragment in forbidden_fragments)
    }

    assert offenders == set()


def test_pr_diff_stays_inside_issue_82_whitelist() -> None:
    skip_unless_pr_diff_checks_enabled()
    assert changed_files() <= ALLOWED_CHANGED_FILES
