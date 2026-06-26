from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import i5b_rule_display_dictionary_contract as contract  # noqa: E402
from scripts.platform import i5b_runtime_adapter_dictionary_readiness as readiness  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / ".env",
    ROOT / "data" / "evidence_cards.jsonl",
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "exports",
]


def test_readiness_report_declares_runtime_dictionary_readiness_package() -> None:
    report = readiness.build_readiness_report()

    assert report["mode"] == "readiness-report"
    assert report["package_version"] == "i5b-runtime-adapter-dictionary-readiness-v1"
    assert report["roadmap_issue"] == 287
    assert report["epic_issue"] == 312
    assert report["tech_debt_issue"] == 311
    assert report["snapshot_loader_validator_pr"] == 321
    assert report["snapshot_loader_validator_merge_commit"] == readiness.SNAPSHOT_LOADER_VALIDATOR_MERGE_COMMIT
    assert report["readiness_blockers"] == []
    assert report["runtime_inventory_count"] == len(contract.HARD_CODED_INVENTORY)
    assert report["does_not_import_runtime_adapter"] is True
    assert report["does_not_render_exports"] is True
    assert report["does_not_modify_runtime_adapter"] is True
    assert report["does_not_write_postgres_dictionary_tables"] is True
    assert report["does_not_publish_scores"] is True
    assert report["does_not_publish_rankings"] is True


def test_runtime_inventory_covers_all_contract_symbols_and_definition_kinds() -> None:
    report = readiness.build_readiness_report()
    by_symbol = {item["symbol"]: item for item in report["runtime_inventory"]}

    assert set(by_symbol) == {str(item["symbol"]) for item in contract.HARD_CODED_INVENTORY}
    assert all(item["symbol_present"] is True for item in by_symbol.values())
    assert by_symbol["TRIAL_SCORE_MAP"]["definition_kind"] == "assignment"
    assert by_symbol["FORMAL_GRADE_ENUM"]["definition_kind"] == "assignment"
    assert by_symbol["render_score_mapping_draft"]["definition_kind"] == "function"
    assert by_symbol["render_formal_person_section"]["definition_kind"] == "function"


def test_readiness_keeps_runtime_migration_and_publication_flags_false() -> None:
    report = readiness.build_readiness_report()
    state = report["current_state"]

    assert state["issue311_runtime_adapter_dictionary_readiness_ready"] is True
    assert state["runtime_symbol_inventory_complete"] is True
    assert state["snapshot_validation_passed"] is True
    assert state["snapshot_inventory_coverage_complete"] is True
    assert state["runtime_adapter_migrated"] is False
    assert state["postgres_dictionary_tables_created"] is False
    assert state["canonical_dictionary_write_performed"] is False
    assert state["ordinary_exports_require_live_dsn"] is False
    assert state["g10_destructive_cleanup_entered"] is False


def test_migration_batches_are_output_compatible_and_gated() -> None:
    report = readiness.build_readiness_report()
    batch_ids = [batch["batch_id"] for batch in report["migration_batches"]]

    assert batch_ids == [
        "issue311_readthrough_loader_shim",
        "issue311_rules_py_keyword_dictionary_read",
        "issue311_formal_algorithm_grade_dictionary_read",
        "issue311_display_dictionary_read",
        "issue311_python_constant_cleanup_after_readthrough",
    ]
    assert all(batch["runtime_output_change_allowed"] is False for batch in report["migration_batches"])
    assert all(batch["requires_schema_gate"] is False for batch in report["migration_batches"])
    assert report["next_required_work"] == "issue311_readthrough_loader_shim_package"


def test_default_readiness_report_is_side_effect_free(monkeypatch) -> None:
    original_read_text = Path.read_text
    allowed_reads = {
        readiness.ROOT / source_path for source_path in contract.SOURCE_MODULES
    } | {readiness.snapshot_loader.DEFAULT_SNAPSHOT_PATH}
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
            ):
                raise AssertionError(f"forbidden path read: {path}")
        return original_read_text(self, *args, **kwargs)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in readiness tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = readiness.build_readiness_report()
    markdown = readiness.render_readiness_md()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["default_modes_side_effect_free"] is True
    assert report["does_not_read_canonical_jsonl"] is True
    assert report["does_not_write_business_tables"] is True
    assert "I5B Runtime Adapter Dictionary Readiness" in markdown


def test_cli_modes_emit_expected_outputs(capsys) -> None:
    assert readiness.main(["--readiness-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["readiness_blockers"] == []

    assert readiness.main(["--readiness-md"]) == 0
    markdown = capsys.readouterr().out
    assert "issue311_readthrough_loader_shim" in markdown
    assert "render_formal_person_section" in markdown


def test_source_does_not_import_runtime_or_secret_clients() -> None:
    source = (ROOT / "scripts" / "platform" / "i5b_runtime_adapter_dictionary_readiness.py").read_text(
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
