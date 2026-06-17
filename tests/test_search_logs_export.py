import subprocess
import sys
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEARCH_LOG_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "第五项B三人试点检索线索.md"
EVIDENCE_CARDS_PATH = ROOT / "data" / "evidence_cards.jsonl"
SOURCES_PATH = ROOT / "data" / "sources.jsonl"
SEARCH_LOGS_PATH = ROOT / "data" / "search_logs.jsonl"
ALLOWED_CREATED_SEARCH_IDS = {
    "SRCH-I5B-LIUXIU-NEG-RONGJIAN-001",
    "SRCH-I5B-LIUXIU-NEG-YISHIXINGTAI-001",
    "SRCH-I5B-LIUXIU-NEG-TINGZHANG-001",
}


def run_script(script_name: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script_name)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def read_jsonl(path: Path) -> list[dict[str, object]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


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
    assert "evidence_found_card_created" in content
    assert "EVD-I5B-LIUXIU-NEG-HANXIN-001" in content
    assert "EVD-I5B-LIUXIU-NEG-HUANTAN-001" in content
    assert "EVD-I5B-LIUXIU-NEG-TINGZHANG-001" in content
    assert "分数" not in content
    assert "总榜" not in content
    assert "排名" not in content
    assert "定档" not in content


def test_task005b1_evidence_cards_reference_existing_sources_and_have_valid_strong_negative_split() -> None:
    sources = read_jsonl(SOURCES_PATH)
    evidence_cards = read_jsonl(EVIDENCE_CARDS_PATH)
    source_ids = {row["source_id"] for row in sources}

    assert {row["evidence_id"] for row in evidence_cards} == {
        "EVD-I5B-LIUXIU-NEG-HANXIN-001",
        "EVD-I5B-LIUXIU-NEG-HUANTAN-001",
        "EVD-I5B-LIUXIU-NEG-TINGZHANG-001",
    }
    assert all(row["person"] == "刘秀" for row in evidence_cards)
    assert all(row["source_id"] in source_ids for row in evidence_cards)
    assert all(row["polarity"] == "negative" for row in evidence_cards)
    assert all(row["strength"] == 3 for row in evidence_cards)
    assert all(row["human_level"] == "强负" for row in evidence_cards)
    assert all(row["cross_item_split"] or row["scoring_effect"] for row in evidence_cards)


def test_only_three_liuxiu_negative_search_logs_have_created_evidence_status() -> None:
    search_logs = read_jsonl(SEARCH_LOGS_PATH)
    created_ids = {
        row["search_id"]
        for row in search_logs
        if row["result_status"] == "evidence_found_card_created"
    }

    assert created_ids == ALLOWED_CREATED_SEARCH_IDS


def test_sources_are_only_task005b1_public_text_sources() -> None:
    source_ids = {row["source_id"] for row in read_jsonl(SOURCES_PATH)}

    assert source_ids == {
        "SRC-ZZTJ-J43-HANXIN-001",
        "SRC-HHS-HUANTAN-001",
        "SRC-HHS-SHENTUGANG-001",
    }
