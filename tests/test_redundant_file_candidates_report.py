from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "docs" / "\u591a\u4f59\u6587\u4ef6\u5019\u9009\u786e\u8ba4\u62a5\u544a.md"
ALLOWED_CHANGED_FILES = {
    "docs/\u591a\u4f59\u6587\u4ef6\u5019\u9009\u786e\u8ba4\u62a5\u544a.md",
    "tests/test_redundant_file_candidates_report.py",
}


def read_report() -> str:
    return REPORT_PATH.read_text(encoding="utf-8")


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


def test_redundant_file_candidates_report_exists() -> None:
    assert REPORT_PATH.exists()


def test_redundant_file_candidates_report_contains_required_sections() -> None:
    content = read_report()
    for heading in [
        "## 1. \u603b\u4f53\u7ed3\u8bba",
        "## 2. \u626b\u63cf\u65b9\u6cd5",
        "## 3. \u5019\u9009\u6587\u4ef6\u786e\u8ba4\u8868",
        "## 4. \u53ef\u8fdb\u5165\u4e0b\u4e00\u8f6e\u5c0f PR \u7684\u5019\u9009",
        "## 5. \u5fc5\u987b\u4eba\u5de5\u786e\u8ba4\u7684\u5019\u9009",
        "## 6. \u4e0d\u5efa\u8bae\u5904\u7406\u7684\u5019\u9009",
        "## 7. \u4e0b\u4e00\u6b65\u5efa\u8bae Issue",
    ]:
        assert heading in content
    assert "| path | original_category | scan_status | unique_source_risk | recommendation | next_action | risk_level | notes |" in content


def test_redundant_file_candidates_report_contains_required_fields() -> None:
    content = read_report()
    for needle in [
        "archive_candidate",
        "delete_candidate",
        "needs_human_confirmation",
        "additional_candidate",
        "referenced",
        "not_referenced",
        "generated_by_script",
        "unknown",
        "yes",
        "no",
        "low",
        "medium",
        "high",
        "archive_later_low_or_medium_risk",
        "delete_later_requires_final_reference_check",
        "needs_human_confirmation_before_any_cleanup",
        "\u5019\u9009\u786e\u8ba4\u4e0d\u7b49\u4e8e\u6388\u6743\u5220\u9664",
        "\u9ad8\u98ce\u9669",
        "\u6b63\u5f0f\u5b9a\u6863",
        "\u4e0d\u5141\u8bb8\u76f4\u63a5\u5220\u9664",
        "original_category",
        "scan_status",
        "unique_source_risk",
        "next_action",
        "risk_level",
        "notes",
    ]:
        assert needle in content


def test_redundant_file_candidates_report_covers_all_candidates() -> None:
    content = read_report()
    for needle in [
        "exports/markdown_views/project_file_governance_audit_20260618.md",
        "exports/markdown_views/i5b_three_pilot_methodology_migration_audit_20260618.md",
        "exports/markdown_views/i5b_three_pilot_human_adjudication_reading_guide_20260618.md",
        "exports/markdown_views/i5b_liubang_net_evidence_review_20260618.md",
        "docs/\u5168\u5c40\u603b\u6807\u5c3a\u51b3\u7b56\u7b80\u62a5_\u8ba8\u8bba\u7248.md",
        "exports/markdown_views/\u7b2c\u4e94\u9879B\u4e09\u4eba\u6b63\u5f0f\u5b9a\u6863\u8349\u6848.md",
        "exports/markdown_views/\u7b2c\u4e94\u9879B\u4e09\u4eba\u6b63\u5f0f\u5b9a\u6863\u8868.md",
        "exports/markdown_views/\u7b2c\u4e94\u9879B\u4e09\u4eba\u8bd5\u70b9\u5bf9\u8c61\u951a\u70b9\u89c6\u56fe.md",
        "data/events.jsonl",
        "data/query_profile_batches/i5b_three_pilot_profiles_migration_20260618.jsonl",
        "data/search_log_batches/i5b_next_four_20260618.jsonl",
        "data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl",
        "data/archive_old_scores/README.md",
        "exports/markdown_views/i5b_liubang_pregrade_adjudication_checklist_20260618.md",
    ]:
        assert needle in content


def test_redundant_file_candidates_report_is_read_only_diagnostic() -> None:
    content = read_report()
    assert "\u672c\u8f6e\u4e0d\u5220\u9664\u3001\u4e0d\u79fb\u52a8\u3001\u4e0d\u5f52\u6863" in content
    assert "\u5019\u9009\u786e\u8ba4\u4e0d\u7b49\u4e8e\u6388\u6743\u5220\u9664" in content
    assert "\u9ad8\u98ce\u9669\u6b63\u5f0f\u5b9a\u6863\u76f8\u5173\u5bfc\u51fa" in content


def test_pr_diff_stays_inside_the_whitelist() -> None:
    assert changed_files() <= ALLOWED_CHANGED_FILES
