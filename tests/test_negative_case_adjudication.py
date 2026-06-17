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


def evidence_by_id() -> dict[str, dict[str, object]]:
    return {row["evidence_id"]: row for row in read_jsonl(EVIDENCE_CARDS_PATH)}


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


def test_task005b3_lishimin_negative_cases_follow_005r_strengths() -> None:
    cards = evidence_by_id()

    zhang = cards["EVD-I5B-LISHIMIN-NEG-ZHANGLIANG-001"]
    assert zhang["strength"] == 2
    assert zhang["human_level"] == "中负"
    assert zhang["case_classification"] == "suspected_rebellion_unproven"
    assert zhang["risk_status"] == "strong_suspicion"

    hou = cards["EVD-I5B-LISHIMIN-NEG-HOUJUNJI-001"]
    assert hou["strength"] == 1
    assert hou["human_level"] == "弱负"
    assert hou["case_classification"] == "confirmed_rebellion_or_security_case"
    assert hou["risk_status"] == "confirmed_rebellion"

    wei = cards["EVD-I5B-LISHIMIN-NEG-WEIZHENG-001"]
    assert wei["strength"] == 1
    assert wei["human_level"] == "弱负"
    assert wei["case_classification"] == "posthumous_trust_reversal"
    assert "restored_tablet" in wei["reversal_or_rehabilitation"]
    assert "trust_restored" in wei["reversal_or_rehabilitation"]


def test_search_log_statuses_include_only_verified_negative_cards() -> None:
    search_logs = read_jsonl(SEARCH_LOGS_PATH)
    created_ids = {
        row["search_id"]
        for row in search_logs
        if row["result_status"] == "evidence_found_card_created"
    }

    assert created_ids == {
        "SRCH-I5B-LISHIMIN-POS-SHIREN-001",
        "SRCH-I5B-LISHIMIN-POS-SHOUQUAN-001",
        "SRCH-I5B-LISHIMIN-POS-RONGJIAN-001",
        "SRCH-I5B-LISHIMIN-POS-MAZHOU-001",
        "SRCH-I5B-LISHIMIN-POS-LIJI-001",
        "SRCH-I5B-LIUXIU-POS-SHIREN-001",
        "SRCH-I5B-LIUXIU-POS-SHOUQUAN-001",
        "SRCH-I5B-LIUXIU-POS-RONGJIAN-FENGYI-001",
        "SRCH-I5B-LISHIMIN-NEG-YIJI-001",
        "SRCH-I5B-LIUXIU-NEG-RONGJIAN-001",
        "SRCH-I5B-LIUXIU-NEG-YISHIXINGTAI-001",
        "SRCH-I5B-LIUXIU-NEG-TINGZHANG-001",
        "SRCH-I5B-LIUZHUANG-NEG-YIJI-001",
    }


def test_lishimin_positive_cards_use_005r_compatible_adjudication_fields() -> None:
    cards = evidence_by_id()

    for evidence_id, expected_strength, expected_level in [
        ("EVD-I5B-LISHIMIN-POS-SHIREN-FANGDU-001", 3, "强正"),
        ("EVD-I5B-LISHIMIN-POS-SHIREN-WEIZHENG-001", 2, "中正"),
        ("EVD-I5B-LISHIMIN-POS-SHOUQUAN-LIJING-001", 2, "中正"),
        ("EVD-I5B-LISHIMIN-POS-RONGJIAN-WEIZHENG-001", 3, "强正"),
        ("EVD-I5B-LISHIMIN-POS-SHIREN-MAZHOU-001", 2, "中正"),
        ("EVD-I5B-LISHIMIN-POS-GONGCHEN-LIJI-001", 3, "强正"),
    ]:
        row = cards[evidence_id]
        assert row["polarity"] == "positive"
        assert row["strength"] == expected_strength
        assert row["human_level"] == expected_level
        assert row["case_classification"] == "other"
        assert row["risk_status"] == "not_applicable"
        assert row["mitigating_factors"] == []
        assert row["aggravating_factors"] == []
        assert row["reversal_or_rehabilitation"] == ["not_found"]
        assert row["adjudication_status"] == "source_verified_pending_human_adjudication"


def test_lishimin_positive_leads_are_now_converted() -> None:
    search_logs = {
        row["search_id"]: row
        for row in read_jsonl(SEARCH_LOGS_PATH)
    }
    for search_id, linked_id in {
        "SRCH-I5B-LISHIMIN-POS-SHIREN-001": "EVD-I5B-LISHIMIN-POS-SHIREN-FANGDU-001",
        "SRCH-I5B-LISHIMIN-POS-SHOUQUAN-001": "EVD-I5B-LISHIMIN-POS-SHOUQUAN-LIJING-001",
        "SRCH-I5B-LISHIMIN-POS-RONGJIAN-001": "EVD-I5B-LISHIMIN-POS-RONGJIAN-WEIZHENG-001",
        "SRCH-I5B-LISHIMIN-POS-MAZHOU-001": "EVD-I5B-LISHIMIN-POS-SHIREN-MAZHOU-001",
        "SRCH-I5B-LISHIMIN-POS-LIJI-001": "EVD-I5B-LISHIMIN-POS-GONGCHEN-LIJI-001",
        "SRCH-I5B-LIUXIU-POS-SHIREN-001": "EVD-I5B-LIUXIU-POS-SHIREN-DENGYU-001",
        "SRCH-I5B-LIUXIU-POS-SHOUQUAN-001": "EVD-I5B-LIUXIU-POS-SHOUQUAN-WUHAN-001",
        "SRCH-I5B-LIUXIU-POS-RONGJIAN-FENGYI-001": "EVD-I5B-LIUXIU-POS-RONGJIAN-FENGYI-001",
    }.items():
        assert search_logs[search_id]["result_status"] == "evidence_found_card_created"
        assert search_logs[search_id]["linked_evidence_id"] == linked_id
