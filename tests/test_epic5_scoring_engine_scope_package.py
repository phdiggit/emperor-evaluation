from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import epic5_scoring_engine_scope_package as epic5  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / ".env",
    ROOT / "data" / "evidence_cards.jsonl",
    ROOT / "data" / "evidence_clusters.jsonl",
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "exports",
]


def test_contract_report_declares_epic5_boundary_package() -> None:
    report = epic5.build_contract_report()

    assert report["mode"] == "contract-report"
    assert report["package_version"] == "epic5-scoring-engine-boundary-scope-package-v1"
    assert report["roadmap_issue"] == 287
    assert report["epic_issue"] == 312
    assert report["previous_epic_issue"] == 211
    assert report["previous_completed_pr"] == 310
    assert report["previous_completed_merge_commit"] == epic5.PREVIOUS_COMPLETED_MERGE_COMMIT
    assert report["current_state"]["current_phase"] == "epic5_boundary_scope_package_ready"
    assert report["current_state"]["positive_benefit_total"] == 1500
    assert report["current_state"]["former_active_cap_1440"] == "obsolete"
    assert report["current_state"]["fifth_item_b_score_values_released"] is True
    assert report["current_state"]["stage_or_final_total_table_released"] is False
    assert report["current_state"]["cross_subitem_leaderboard_released"] is False


def test_schema_draft_covers_issue_312_minimum_objects() -> None:
    report = epic5.build_contract_report()
    schema = {item["name"]: item for item in report["generic_schema_draft"]}

    assert {"subitem_profile", "evidence_profile", "formal_grade_result", "score_publication_result"} <= set(schema)
    assert "score_cap" in schema["subitem_profile"]["required_fields"]
    assert "positive_signal_profile" in schema["evidence_profile"]["required_fields"]
    assert "candidate_value" in schema["formal_grade_result"]["required_fields"]
    assert "subitem_rank" in schema["score_publication_result"]["required_fields"]
    assert "stage_or_final_total_table_released" in schema["score_publication_result"]["required_fields"]
    assert "cross_subitem_leaderboard_released" in schema["score_publication_result"]["required_fields"]


def test_g8_g9_reuse_and_no_override_boundaries_are_explicit() -> None:
    report = epic5.build_contract_report()
    reuse_rules = report["g8_g9_reuse_rules"]
    no_override = report["generic_no_override_constraints"]
    followup = report["followup_gate_boundaries"]

    assert "impact_report_without_formal_person_values" in reuse_rules["g8_per_subitem_algorithm_release_requires"]
    assert "formal_person_values_for_that_subitem" in reuse_rules["g9_per_subitem_publication_allows"]
    assert "cross_subitem_leaderboard" in reuse_rules["g9_per_subitem_publication_does_not_allow"]
    assert no_override == {
        "person_specific_override_allowed": False,
        "manual_final_grade_allowed": False,
        "manual_final_score_allowed": False,
        "override_policy": "algorithm_and_gate_outputs_only",
    }
    assert followup["per_subitem_formal_algorithm_release"] == "requires_g8_style_gate_for_each_new_subitem"
    assert followup["per_subitem_score_publication"] == "requires_g9_style_gate_for_each_new_subitem"
    assert followup["cross_subitem_leaderboard"] == "requires_separate_leaderboard_publication_gate"


def test_pilot_candidates_are_selected_without_publication() -> None:
    report = epic5.build_contract_report()
    candidates = report["pilot_subitem_candidates"]
    names = {candidate["subitem"] for candidate in candidates}

    assert {"第二项治国净收益", "第三项军事与边疆净收益", "第六项关键历史决策能力"} == names
    assert all(candidate["publication_allowed_in_this_package"] is False for candidate in candidates)
    assert "new_subitem_formal_score_publication" in report["prohibited_scope"]
    assert "stage_or_final_total_table_publication" in report["prohibited_scope"]
    assert "cross_subitem_leaderboard_publication" in report["prohibited_scope"]
    assert "rule_display_dictionary_canonical_write" in report["prohibited_scope"]


def test_default_reports_do_not_read_secret_data_or_runtime_paths(monkeypatch) -> None:
    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        parts = tuple(self.parts)
        if (
            self.name == ".env"
            or "batches" in parts
            or ("archive" in parts and "data" in parts)
            or self.name in {"evidence_cards.jsonl", "evidence_clusters.jsonl"}
        ):
            raise AssertionError(f"forbidden path read: {self}")
        return original_read_text(self, *args, **kwargs)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in Epic5 scope tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = epic5.build_contract_report()
    markdown = epic5.render_scope_md()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["default_modes_side_effect_free"] is True
    assert report["does_not_read_canonical_jsonl"] is True
    assert report["does_not_write_business_tables"] is True
    assert "Epic5 Scoring Engine Boundary Scope Package" in markdown


def test_cli_modes_emit_expected_outputs(capsys) -> None:
    assert epic5.main(["--contract-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "contract-report"

    assert epic5.main(["--scope-md"]) == 0
    markdown = capsys.readouterr().out
    assert "Epic5 Scoring Engine Boundary Scope Package" in markdown
    assert "score_publication_result" in markdown


def test_source_does_not_import_runtime_or_secret_clients() -> None:
    source = (ROOT / "scripts" / "platform" / "epic5_scoring_engine_scope_package.py").read_text(encoding="utf-8")

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
