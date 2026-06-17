import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEARCH_LOG_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "第五项B三人试点检索线索.md"
EVIDENCE_CARDS_PATH = ROOT / "data" / "evidence_cards.jsonl"
SOURCES_PATH = ROOT / "data" / "sources.jsonl"


def run_script(script_name: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script_name)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_validate_evidence_passes_with_i5b_search_leads() -> None:
    result = run_script("validate_evidence.py")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Validation passed." in result.stdout


def test_export_md_generates_i5b_trial_search_leads_view() -> None:
    build_result = run_script("build_db.py")
    assert build_result.returncode == 0, build_result.stdout + build_result.stderr

    export_result = run_script("export_md.py")
    assert export_result.returncode == 0, export_result.stdout + export_result.stderr
    assert SEARCH_LOG_EXPORT_PATH.exists()

    content = SEARCH_LOG_EXPORT_PATH.read_text(encoding="utf-8")
    assert "李世民" in content
    assert "刘秀" in content
    assert "刘庄" in content
    assert "lead_needs_source_review" in content
    assert "分数" not in content
    assert "总榜" not in content
    assert "排名" not in content


def test_task005a_does_not_add_evidence_cards_or_sources() -> None:
    assert EVIDENCE_CARDS_PATH.read_text(encoding="utf-8").strip() == ""
    assert SOURCES_PATH.read_text(encoding="utf-8").strip() == ""
