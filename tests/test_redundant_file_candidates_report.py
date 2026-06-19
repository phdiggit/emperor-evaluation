import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "docs" / "多余文件候选确认报告.md"
ALLOWED_FILES = {
    "docs/多余文件候选确认报告.md",
    "tests/test_redundant_file_candidates_report.py",
}


def test_redundant_file_candidates_report_covers_all_candidates() -> None:
    assert REPORT_PATH.exists()

    content = REPORT_PATH.read_text(encoding="utf-8")

    assert "## 1. 总体结论" in content
    assert "## 2. 扫描方法" in content
    assert "## 3. 候选文件确认表" in content
    assert "## 4. 可进入下一轮小 PR 的候选" in content
    assert "## 5. 必须人工确认的候选" in content
    assert "## 6. 不建议处理的候选" in content
    assert "## 7. 下一步建议 Issue" in content
    assert "本轮不删除、不移动、不归档" in content
    assert "本表不构成删除授权" in content
    assert "archive_candidate" in content
    assert "delete_candidate" in content
    assert "needs_human_confirmation" in content
    assert "additional_candidate" in content
    assert "original_category" in content
    assert "unique_source" in content
    assert "next_step_action" in content
    assert "risk_level" in content
    assert "archive_later_low_or_medium_risk" in content
    assert "delete_later_requires_final_reference_check" in content
    assert "needs_human_confirmation_before_any_cleanup" in content

    for needle in [
        "referenced",
        "not_referenced",
        "generated_by_script",
        "unknown",
        "yes",
        "no",
        "keep",
        "archive_later",
        "delete_later",
        "merge_then_archive",
        "needs_human_confirmation",
        "exports/markdown_views/project_file_governance_audit_20260618.md",
        "exports/markdown_views/i5b_three_pilot_methodology_migration_audit_20260618.md",
        "exports/markdown_views/i5b_three_pilot_human_adjudication_reading_guide_20260618.md",
        "exports/markdown_views/i5b_liubang_net_evidence_review_20260618.md",
        "docs/全局总标尺决策简报_讨论版.md",
        "exports/markdown_views/第五项B三人正式定档草案.md",
        "exports/markdown_views/第五项B三人正式定档表.md",
        "exports/markdown_views/第五项B三人试点对象锚点视图.md",
        "data/events.jsonl",
        "data/query_profile_batches/i5b_three_pilot_profiles_migration_20260618.jsonl",
        "data/search_log_batches/i5b_next_four_20260618.jsonl",
        "data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl",
        "data/archive_old_scores/README.md",
        "exports/markdown_views/i5b_liubang_pregrade_adjudication_checklist_20260618.md",
    ]:
        assert needle in content

    assert "本表不构成删除授权" in content


def test_worktree_diff_is_limited_to_the_whitelist() -> None:
    commands = [
        ["git", "-c", "core.quotepath=false", "diff", "--name-only", "origin/GPT...HEAD"],
        ["git", "-c", "core.quotepath=false", "diff", "--name-only"],
        ["git", "-c", "core.quotepath=false", "diff", "--cached", "--name-only"],
    ]
    changed_files: set[str] = set()
    for command in commands:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, check=False)
        if result.returncode != 0:
            continue
        stdout = result.stdout.decode("utf-8")
        changed_files.update(line.strip().replace("\\", "/") for line in stdout.splitlines() if line.strip())
    assert changed_files <= ALLOWED_FILES
    assert changed_files == ALLOWED_FILES
