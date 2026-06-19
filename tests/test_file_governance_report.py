from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT_FILE = "\u9879\u76ee\u6587\u4ef6\u6cbb\u7406\u8bca\u65ad\u62a5\u544a.md"
REPORT_PATH = ROOT / "docs" / REPORT_FILE
ALLOWED_CHANGED_FILES = {
    f"docs/{REPORT_FILE}",
    "tests/test_file_governance_report.py",
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


def test_file_governance_report_exists() -> None:
    assert REPORT_PATH.exists()


def test_file_governance_report_contains_required_sections() -> None:
    content = read_report()
    for heading in [
        "## 1. 总体结论",
        "## 2. 文件与目录职责盘点",
        "## 3. 多余/疑似多余文件清单",
        "## 4. 大文件/大脚本风险清单",
        "## 5. 架构性能边界判断",
        "## 6. 治理优先级建议",
        "## 7. 不建议立刻做的事",
    ]:
        assert heading in content


def test_file_governance_report_is_read_only_diagnostic() -> None:
    content = read_report()
    assert "本轮不删除、不移动、不重构业务文件" in content
    assert "不删除文件" not in changed_files()


def test_file_governance_report_mentions_required_scripts_and_categories() -> None:
    content = read_report()
    for needle in [
        "scripts/export_md.py",
        "scripts/export_i5b_auto_adjudication.py",
        "scripts/validate_evidence.py",
        "keep_long_term",
        "keep_for_now",
        "archive_candidate",
        "delete_candidate",
        "needs_human_confirmation",
    ]:
        assert needle in content


def test_file_governance_report_rejects_external_infrastructure_for_now() -> None:
    content = read_report()
    assert "暂不需要 PostgreSQL、MySQL 等外部数据库" in content
    assert "暂不需要 Redis 或外部缓存" in content
    assert "暂不需要消息队列或中间件" in content
    assert "外部数据库、缓存、中间件暂不建议引入" in content


def test_file_governance_report_contains_priority_plan() -> None:
    content = read_report()
    for priority in ["P0", "P1", "P2", "P3"]:
        assert priority in content


def test_pr_diff_stays_inside_issue_80_whitelist() -> None:
    assert changed_files() <= ALLOWED_CHANGED_FILES
