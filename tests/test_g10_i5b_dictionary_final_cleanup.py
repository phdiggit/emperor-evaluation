from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import g10_i5b_dictionary_final_cleanup as cleanup  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / ".env",
    ROOT / "data" / "evidence_cards.jsonl",
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "exports",
]


def test_cleanup_report_declares_g10_1_scope_and_checkpoint() -> None:
    report = cleanup.build_cleanup_report()

    assert report["mode"] == "cleanup-report"
    assert report["package_version"] == "g10-i5b-dictionary-final-cleanup-v1"
    assert report["roadmap_issue"] == 287
    assert report["epic_issue"] == 312
    assert report["plan_issue"] == 331
    assert report["cleanup_issue"] == 332
    assert report["related_tech_debt_issue"] == 311
    assert report["prerequisite_pr"] == 336
    assert report["prerequisite_merge_commit"] == cleanup.PREREQUISITE_MERGE_COMMIT
    assert report["cleanup_blockers"] == []
    assert report["snapshot_validated"] is True
    assert report["does_not_write_postgres_dictionary_tables"] is True
    assert report["does_not_publish_scores"] is True
    assert report["does_not_publish_rankings"] is True
    assert report["does_not_move_delete_or_archive_files"] is True


def test_cleanup_current_state_marks_non_destructive_g10_execution() -> None:
    state = cleanup.build_cleanup_report()["current_state"]

    assert state["current_phase"] == "g10_i5b_dictionary_final_cleanup_ready"
    assert state["g10_1_i5b_dictionary_final_cleanup_ready"] is True
    assert state["g10_execution_started"] is True
    assert state["g10_cleanup_execution_started"] is True
    assert state["g10_destructive_cleanup_started"] is False
    assert state["issue311_completion_state_synchronized"] is True
    assert state["i5b_rule_runtime_text_readthrough_enabled"] is True
    assert state["i5b_formal_algorithm_display_readthrough_enabled"] is True
    assert state["i5b_adapter_auto_band_directions_readthrough_enabled"] is True
    assert state["i5b_remaining_python_text_classified"] is True
    assert state["i5b_snapshot_final_cleanup_digest_validation_passed"] is True
    assert state["i5b_no_legacy_runtime_copy_regressions"] is True
    assert state["postgres_dictionary_tables_created"] is False
    assert state["canonical_dictionary_write_performed"] is False
    assert state["ordinary_exports_require_live_dsn"] is False
    assert state["cross_subitem_leaderboard_released"] is False


def test_dictionary_payload_contains_final_cleanup_runtime_text_and_display_rows() -> None:
    payload = cleanup.build_cleanup_report()["dictionary_payload_summary"]

    assert payload["dictionary_payload_classification"] == "dictionary_payload"
    assert payload["rule_runtime_text_present"] is True
    assert payload["formal_algorithm_display_present"] is True
    assert payload["required_rule_runtime_text_keys_present"] is True
    assert payload["required_formal_algorithm_display_keys_present"] is True
    assert payload["mapping_row_count"] == 9
    assert set(payload["auto_band_direction_keys"]) == {
        "high_strong_extreme_candidate",
        "medium_positive_medium_negative_pressure",
        "medium_positive_strong_negative_pressure",
        "rule_review_pending",
        "strong_positive_blocked",
        "strong_positive_capped",
    }
    assert "auto_band_directions" in payload["rule_runtime_text_keys"]
    assert "FORMAL_ALGORITHM_DISPLAY" not in payload["formal_algorithm_display_keys"]


def test_runtime_sources_use_readthrough_and_do_not_reintroduce_business_copy() -> None:
    report = cleanup.build_cleanup_report()

    assert all(report["runtime_readthrough_checks"].values())
    assert report["legacy_runtime_copy_matches"] == []

    rules_source = (
        ROOT / "scripts" / "export" / "dimension_adapters" / "i5b_people_delegation" / "rules.py"
    ).read_text(encoding="utf-8")
    formal_source = (
        ROOT / "scripts" / "export" / "dimension_adapters" / "i5b_people_delegation" / "formal_algorithm.py"
    ).read_text(encoding="utf-8")
    adapter_source = (
        ROOT / "scripts" / "export" / "dimension_adapters" / "i5b_people_delegation" / "adapter.py"
    ).read_text(encoding="utf-8")

    assert '_RULE_DICTIONARY_VALUES["RULE_RUNTIME_TEXT"]' in rules_source
    assert 'AUTO_BAND_DIRECTIONS["high_strong_extreme_candidate"]' in adapter_source
    assert 'FORMAL_ALGORITHM_DISPLAY' in formal_source
    assert "同一维度内至少三个强正核心" not in rules_source
    assert "强负核心或中负升强负边界必须阻断高位上探" not in formal_source
    assert "高位强正，上探极正候选" not in adapter_source
    assert "自动草案待规则复核" not in adapter_source


def test_remaining_python_text_is_classified_by_role() -> None:
    report = cleanup.build_cleanup_report()
    by_path = {item["path"]: item for item in report["source_text_classifications"]}

    assert by_path["scripts/export/dimension_adapters/i5b_people_delegation/rules.py"]["classification"] == (
        "algorithm_invariant_runtime"
    )
    assert by_path["scripts/export/dimension_adapters/i5b_people_delegation/formal_algorithm.py"][
        "classification"
    ] == "algorithm_invariant_runtime"
    assert by_path["scripts/export/dimension_adapters/i5b_people_delegation/adapter.py"]["classification"] == (
        "display_copy"
    )
    assert by_path["scripts/shared/i5b_markdown_display_defaults.py"]["classification"] == (
        "display_config_source"
    )
    assert by_path["tests/test_i5b_dictionary_readthrough.py"]["classification"] == "test_fixture"
    assert by_path["tests/test_i5b_auto_adjudication.py"]["classification"] == "test_fixture"
    assert by_path["tests/test_g8_i5b_formal_algorithm_release.py"]["classification"] == "test_fixture"
    assert by_path["tests/test_g9_i5b_formal_publication_release.py"]["classification"] == "test_fixture"
    assert by_path["scripts/shared/i5b_markdown_display_defaults.py"]["chinese_string_literal_count"] > 0
    assert by_path["tests/test_i5b_auto_adjudication.py"]["chinese_string_literal_count"] > 0


def test_default_cleanup_report_is_side_effect_free(monkeypatch) -> None:
    original_read_text = Path.read_text
    allowed_reads = {
        cleanup.ROOT / target["path"] for target in cleanup.RUNTIME_SOURCE_TARGETS
    } | {
        cleanup.ROOT / relative_path for relative_path in cleanup.TEST_FIXTURE_TARGETS
    } | {cleanup.snapshot_loader.DEFAULT_SNAPSHOT_PATH}
    allowed_resolved = {path.resolve() for path in allowed_reads}

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        path = self.resolve()
        parts = tuple(path.parts)
        if path not in allowed_resolved:
            if (
                path.name == ".env"
                or "batches" in parts
                or ("archive" in parts and "data" in parts)
                or path.name == "evidence_cards.jsonl"
                or "exports" in parts
            ):
                raise AssertionError(f"forbidden path read: {path}")
        return original_read_text(self, *args, **kwargs)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in G10-1 cleanup tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = cleanup.build_cleanup_report()
    markdown = cleanup.render_cleanup_md()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["default_modes_side_effect_free"] is True
    assert report["does_not_read_canonical_jsonl"] is True
    assert report["does_not_write_business_tables"] is True
    assert "G10 I5B Dictionary Final Cleanup" in markdown


def test_cli_modes_emit_expected_outputs(capsys) -> None:
    assert cleanup.main(["--cleanup-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["cleanup_blockers"] == []

    assert cleanup.main(["--cleanup-md"]) == 0
    markdown = capsys.readouterr().out
    assert "adapter_auto_band_directions_readthrough" in markdown
    assert "issue333_historical_asset_retirement_after_inventory" in markdown


def test_source_does_not_import_runtime_or_secret_clients() -> None:
    source = (ROOT / "scripts" / "platform" / "g10_i5b_dictionary_final_cleanup.py").read_text(encoding="utf-8")

    assert "import psycopg" not in source
    assert "import pika" not in source
    assert "aio_pika" not in source
    assert "import requests" not in source
    assert "subprocess.run" not in source
    assert "EMPEROR_EVAL_PG_DSN" not in source
    assert "PG_SEARCH_BENCH_DSN" not in source
    assert "import scripts.export.dimension_adapters.i5b_people_delegation.adapter" not in source


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
