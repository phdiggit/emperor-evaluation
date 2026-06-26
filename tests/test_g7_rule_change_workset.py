from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import g7_rule_change_workset as g7  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / ".env",
    ROOT / "data" / "evidence_cards.jsonl",
    ROOT / "data" / "evidence_clusters.jsonl",
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "exports",
    ROOT / "docs" / "皇帝综合评价体系评分标准.md",
    ROOT / "docs" / "分项规则",
    ROOT / "docs" / "证据规则",
]


def test_workset_report_records_g7_rule_change_requirements_without_mutation() -> None:
    report = g7.build_workset_report()

    assert report["mode"] == "workset-report"
    assert report["package_version"] == "g7-rule-change-workset-v1"
    assert report["workset_id"] == "issue-292-g7-rule-change-workset-1"
    assert report["gate_status"] == "approved_workset_ready"
    assert report["g7_scope_pr"] == 306
    assert report["g7_scope_merge_commit"] == g7.G7_SCOPE_MERGE_COMMIT
    assert report["does_not_read_rule_sources"] is True
    assert report["does_not_modify_rule_sources"] is True
    assert report["does_not_write_business_tables"] is True
    assert report["ready_for_next_pr"] == "g7_rule_change_implementation_pr"
    assert report["next_required_user_gate"] == "G8"


def test_candidate_rule_paths_and_required_sections_are_explicit() -> None:
    report = g7.build_workset_report()
    paths = {item["path"] for item in report["candidate_rule_paths"]}
    required = set(report["rule_change_pr_required_sections"])

    assert "docs/皇帝综合评价体系评分标准.md" in paths
    assert "docs/分项规则/**" in paths
    assert "docs/证据规则/**" in paths
    assert "changed_rule_paths" in required
    assert "before_after_rule_diff_summary" in required
    assert "impact_scope_statement" in required
    assert "boundary_regression_tests" in required
    assert "algorithm_and_publication_gates_remain_blocked" in required


def test_followup_gates_remain_blocked() -> None:
    blocked = g7.build_workset_report()["blocked_until_followup_gate"]

    assert blocked["formal_algorithm_release"] == "G8"
    assert blocked["formal_output_values_or_publication"] == "G9"
    assert blocked["destructive_cleanup"] == "G10"
    assert blocked["epic_2_entry"] == "separate_ready_review"
    assert blocked["source_passages_business_tables"] == "followup_source_document_passage_gate"
    assert blocked["evidence_cluster_anchor_relationship_tables"] == "followup_relationship_gate"


def test_default_reports_do_not_read_secret_data_or_rule_sources(monkeypatch) -> None:
    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        parts = tuple(self.parts)
        if (
            self.name == ".env"
            or "batches" in parts
            or ("archive" in parts and "data" in parts)
            or self.name in {"evidence_cards.jsonl", "evidence_clusters.jsonl", "皇帝综合评价体系评分标准.md"}
            or "分项规则" in parts
            or "证据规则" in parts
        ):
            raise AssertionError(f"forbidden path read: {self}")
        return original_read_text(self, *args, **kwargs)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in G7 workset tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = g7.build_workset_report()
    markdown = g7.render_workset_md()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["default_modes_side_effect_free"] is True
    assert report["does_not_read_canonical_jsonl"] is True
    assert report["does_not_read_rule_sources"] is True
    assert "G7 Rule Change Workset" in markdown


def test_cli_modes_emit_expected_outputs(capsys) -> None:
    assert g7.main(["--workset-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "workset-report"

    assert g7.main(["--workset-md"]) == 0
    markdown = capsys.readouterr().out
    assert "G7 Rule Change Workset" in markdown


def test_source_does_not_import_runtime_or_secret_clients() -> None:
    source = (ROOT / "scripts" / "platform" / "g7_rule_change_workset.py").read_text(encoding="utf-8")

    assert "import psycopg" not in source
    assert "import pika" not in source
    assert "aio_pika" not in source
    assert "import requests" not in source
    assert "subprocess.run" not in source
    assert "EMPEROR_EVAL_PG_DSN" not in source
    assert "PG_SEARCH_BENCH_DSN" not in source


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
