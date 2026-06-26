from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import i5b_python_constant_cleanup_after_readthrough as cleanup  # noqa: E402
from scripts.platform import i5b_rule_display_dictionary_contract as contract  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / ".env",
    ROOT / "data" / "evidence_cards.jsonl",
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "exports",
]


def test_cleanup_report_declares_python_constant_cleanup_package() -> None:
    report = cleanup.build_cleanup_report()

    assert report["mode"] == "cleanup-report"
    assert report["package_version"] == "i5b-python-constant-cleanup-after-readthrough-v1"
    assert report["roadmap_issue"] == 287
    assert report["epic_issue"] == 312
    assert report["tech_debt_issue"] == 311
    assert report["display_readthrough_pr"] == 327
    assert report["display_readthrough_merge_commit"] == cleanup.DISPLAY_READTHROUGH_MERGE_COMMIT
    assert report["cleanup_blockers"] == []
    assert report["cleanup_inventory_count"] == len(contract.HARD_CODED_INVENTORY)
    assert report["does_not_import_runtime_adapter"] is True
    assert report["does_not_render_exports"] is True
    assert report["does_not_write_postgres_dictionary_tables"] is True
    assert report["does_not_publish_scores"] is True
    assert report["does_not_publish_rankings"] is True


def test_cleanup_current_state_keeps_pre_g10_boundaries() -> None:
    state = cleanup.build_cleanup_report()["current_state"]

    assert state["current_phase"] == "issue311_i5b_python_constant_cleanup_after_readthrough_ready"
    assert state["issue311_python_constant_cleanup_after_readthrough_ready"] is True
    assert state["runtime_adapter_migrated"] is True
    assert state["legacy_python_dictionary_text_removed"] is True
    assert state["readthrough_references_complete"] is True
    assert state["snapshot_validation_passed"] is True
    assert state["postgres_dictionary_tables_created"] is False
    assert state["canonical_dictionary_write_performed"] is False
    assert state["ordinary_exports_require_live_dsn"] is False
    assert state["g10_destructive_cleanup_entered"] is False


def test_cleanup_inventory_has_readthrough_references_and_no_legacy_literals() -> None:
    report = cleanup.build_cleanup_report()
    by_symbol = {item["symbol"]: item for item in report["cleanup_inventory"]}

    assert set(by_symbol) == {str(item["symbol"]) for item in contract.HARD_CODED_INVENTORY}
    assert all(item["symbol_present"] is True for item in by_symbol.values())
    assert all(item["readthrough_reference_present"] is True for item in by_symbol.values())
    assert all(item["legacy_literal_container_present"] is False for item in by_symbol.values())
    assert all(item["legacy_literal_markers_present"] is False for item in by_symbol.values())
    assert report["missing_symbols"] == []
    assert report["missing_readthrough_references"] == []
    assert report["legacy_literal_symbols"] == []
    assert by_symbol["TRIAL_SCORE_MAP"]["definition_kind"] == "assignment"
    assert by_symbol["FORMAL_GRADE_ENUM"]["definition_kind"] == "assignment"
    assert by_symbol["render_score_mapping_draft"]["definition_kind"] == "function"
    assert by_symbol["render_formal_person_section"]["definition_kind"] == "function"


def test_default_cleanup_report_is_side_effect_free(monkeypatch) -> None:
    original_read_text = Path.read_text
    allowed_reads = {
        cleanup.ROOT / source_path for source_path in contract.SOURCE_MODULES
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
        raise AssertionError("network access is forbidden in cleanup tests")

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
    assert "I5B Python Constant Cleanup After Readthrough" in markdown


def test_cli_modes_emit_expected_outputs(capsys) -> None:
    assert cleanup.main(["--cleanup-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["cleanup_blockers"] == []

    assert cleanup.main(["--cleanup-md"]) == 0
    markdown = capsys.readouterr().out
    assert "TRIAL_SCORE_MAP" in markdown
    assert "issue_311_rule_display_dictionary_governance_gate" in markdown


def test_source_does_not_import_runtime_or_secret_clients() -> None:
    source = (ROOT / "scripts" / "platform" / "i5b_python_constant_cleanup_after_readthrough.py").read_text(
        encoding="utf-8"
    )

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
