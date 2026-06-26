from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import i5b_dictionary_snapshot_loader_validator as loader  # noqa: E402
from scripts.platform import i5b_rule_display_dictionary_contract as contract  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / ".env",
    ROOT / "data" / "evidence_cards.jsonl",
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "exports",
]


def test_default_snapshot_report_validates_loader_validator_package() -> None:
    report = loader.build_snapshot_report()

    assert report["mode"] == "snapshot-report"
    assert report["package_version"] == "i5b-dictionary-snapshot-loader-validator-v1"
    assert report["roadmap_issue"] == 287
    assert report["epic_issue"] == 312
    assert report["tech_debt_issue"] == 311
    assert report["contract_pr"] == 320
    assert report["contract_merge_commit"] == loader.CONTRACT_MERGE_COMMIT
    assert report["snapshot_path"] == (
        "scripts/platform/i5b_dictionary_snapshots/i5b_rule_display_dictionary_snapshot_v1.json"
    )
    assert report["validated"] is True
    assert report["validation_errors"] == []
    assert report["snapshot_item_count"] == 5
    assert report["inventory_symbol_count"] == len(contract.HARD_CODED_INVENTORY)
    assert report["covered_inventory_symbol_count"] == len(contract.HARD_CODED_INVENTORY)
    assert report["does_not_write_postgres_dictionary_tables"] is True
    assert report["does_not_modify_runtime_adapter"] is True
    assert report["does_not_publish_scores"] is True
    assert report["does_not_publish_rankings"] is True


def test_snapshot_covers_all_contract_inventory_symbols_once() -> None:
    report = loader.build_snapshot_report()
    expected_symbols = sorted(str(item["symbol"]) for item in contract.HARD_CODED_INVENTORY)

    assert report["covered_inventory_symbols"] == expected_symbols
    assert report["current_state"]["hardcoded_inventory_symbols_covered"] is True
    assert report["current_state"]["issue311_dictionary_snapshot_loader_validator_ready"] is True
    assert report["current_state"]["runtime_adapter_migrated"] is False
    assert report["current_state"]["postgres_dictionary_tables_created"] is False
    assert report["current_state"]["canonical_dictionary_write_performed"] is False
    assert report["current_state"]["ordinary_exports_require_live_dsn"] is False
    assert report["current_state"]["g10_destructive_cleanup_entered"] is False


def test_snapshot_item_schema_and_digest_validation_are_enforced() -> None:
    snapshot = loader.load_snapshot()
    assert loader.validate_snapshot(snapshot) == []

    tampered = loader.clone_snapshot(snapshot)
    tampered["items"][0]["payload"]["source_symbols"].append("TAMPERED_SYMBOL")
    errors = loader.validate_snapshot(tampered)
    assert "items[0].digest_sha256_mismatch" in errors
    assert "items[0].payload.source_symbols_unknown:TAMPERED_SYMBOL" in errors

    missing_locale = loader.clone_snapshot(snapshot)
    del missing_locale["items"][-1]["locale"]
    assert "items[4].locale_missing" in loader.validate_snapshot(missing_locale)

    duplicate = loader.clone_snapshot(snapshot)
    duplicate["items"][1]["rule_id"] = duplicate["items"][0]["rule_id"]
    duplicate["items"][1]["locale"] = duplicate["items"][0]["locale"]
    duplicate["items"][1]["scope"] = duplicate["items"][0]["scope"]
    assert "items[1].rule_id_duplicate" in loader.validate_snapshot(duplicate)


def test_dictionary_type_must_match_contract_inventory() -> None:
    snapshot = loader.load_snapshot()
    mismatched = loader.clone_snapshot(snapshot)
    mismatched["items"][0]["dictionary_type"] = "display_dictionary"

    errors = loader.validate_snapshot(mismatched)

    assert "items[0].payload.dictionary_type_mismatch:TRIAL_SCORE_MAP" in errors
    assert "items[0].payload.dictionary_type_mismatch:FORMAL_GRADE_ENUM" in errors
    assert "items[0].payload.dictionary_type_mismatch:FORMAL_GRADE_SPECS" in errors


def test_default_loader_is_side_effect_free_and_avoids_runtime_paths(monkeypatch) -> None:
    original_read_text = Path.read_text
    allowed_reads = {loader.DEFAULT_SNAPSHOT_PATH.resolve()}

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        path = self.resolve()
        parts = tuple(path.parts)
        if path not in allowed_reads:
            if (
                path.name == ".env"
                or "batches" in parts
                or ("archive" in parts and "data" in parts)
                or path.name == "evidence_cards.jsonl"
            ):
                raise AssertionError(f"forbidden path read: {path}")
        return original_read_text(self, *args, **kwargs)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in snapshot loader tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = loader.build_snapshot_report()
    markdown = loader.render_snapshot_md()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["default_modes_side_effect_free"] is True
    assert report["does_not_read_canonical_jsonl"] is True
    assert report["does_not_write_business_tables"] is True
    assert "I5B Dictionary Snapshot Loader Validator" in markdown


def test_cli_modes_emit_expected_outputs(capsys) -> None:
    assert loader.main(["--snapshot-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["validated"] is True

    assert loader.main(["--validate-snapshot"]) == 0
    validation_report = json.loads(capsys.readouterr().out)
    assert validation_report["validation_errors"] == []

    assert loader.main(["--snapshot-md"]) == 0
    markdown = capsys.readouterr().out
    assert "i5b.display_dictionary.v1" in markdown
    assert "snapshot_file_sha256" in markdown


def test_source_does_not_import_runtime_or_secret_clients() -> None:
    source = (ROOT / "scripts" / "platform" / "i5b_dictionary_snapshot_loader_validator.py").read_text(
        encoding="utf-8"
    )

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
