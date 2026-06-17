import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_CARDS_PATH = ROOT / "data" / "evidence_cards.jsonl"
SEARCH_LOGS_PATH = ROOT / "data" / "search_logs.jsonl"
EVIDENCE_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "史料证据卡索引.md"


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run_script(script_name: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script_name)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_all_existing_high_risk_negative_cards_have_adjudication_fields() -> None:
    required_fields = {
        "case_classification",
        "risk_status",
        "mitigating_factors",
        "aggravating_factors",
        "reversal_or_rehabilitation",
        "adjudication_status",
    }

    for row in read_jsonl(EVIDENCE_CARDS_PATH):
        assert required_fields <= row.keys()
        assert row["case_classification"]
        assert row["risk_status"]
        assert row["reversal_or_rehabilitation"]
        assert row["adjudication_status"]


def test_evidence_export_contains_adjudication_columns_and_no_score_outputs() -> None:
    build_result = run_script("build_db.py")
    assert build_result.returncode == 0, build_result.stdout + build_result.stderr

    export_result = run_script("export_md.py")
    assert export_result.returncode == 0, export_result.stdout + export_result.stderr

    content = EVIDENCE_EXPORT_PATH.read_text(encoding="utf-8")
    assert "case_classification" in content
    assert "risk_status" in content
    assert "mitigating_factors" in content
    assert "aggravating_factors" in content
    assert "reversal_or_rehabilitation" in content
    assert "adjudication_status" in content
    assert "评分" not in content
    assert "排名" not in content
    assert "总榜" not in content
    assert "定档" not in content


def test_task005r_does_not_change_search_log_statuses_or_add_lishimin_cards() -> None:
    search_logs = read_jsonl(SEARCH_LOGS_PATH)
    created_ids = {
        row["search_id"]
        for row in search_logs
        if row["result_status"] == "evidence_found_card_created"
    }
    evidence_ids = {row["evidence_id"] for row in read_jsonl(EVIDENCE_CARDS_PATH)}

    assert created_ids == {
        "SRCH-I5B-LIUXIU-NEG-RONGJIAN-001",
        "SRCH-I5B-LIUXIU-NEG-YISHIXINGTAI-001",
        "SRCH-I5B-LIUXIU-NEG-TINGZHANG-001",
        "SRCH-I5B-LIUZHUANG-NEG-YIJI-001",
    }
    assert not any(evidence_id.startswith("EVD-I5B-LISHIMIN-") for evidence_id in evidence_ids)
