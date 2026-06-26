from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import i5b_rule_display_dictionary_contract as dictionary  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / ".env",
    ROOT / "data" / "evidence_cards.jsonl",
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "exports",
]


def test_contract_report_declares_issue_311_dictionary_contract_package() -> None:
    report = dictionary.build_contract_report()

    assert report["mode"] == "contract-report"
    assert report["package_version"] == "i5b-rule-display-dictionary-contract-v1"
    assert report["roadmap_issue"] == 287
    assert report["epic_issue"] == 312
    assert report["tech_debt_issue"] == 311
    assert report["rerun_report_contract_pr"] == 319
    assert report["rerun_report_contract_merge_commit"] == dictionary.RERUN_REPORT_CONTRACT_MERGE_COMMIT
    assert report["does_not_write_postgres_dictionary_tables"] is True
    assert report["does_not_modify_runtime_adapter"] is True
    assert report["does_not_publish_scores"] is True
    assert report["does_not_publish_rankings"] is True
    assert report["current_state"]["current_phase"] == "issue311_i5b_dictionary_externalization_contract_ready"
    assert report["current_state"]["active_tech_debt"] == 311
    assert report["current_state"]["hardcoded_inventory_count"] == len(dictionary.HARD_CODED_INVENTORY)
    assert report["current_state"]["snapshot_schema_defined"] is True
    assert report["current_state"]["loader_contract_defined"] is True
    assert report["current_state"]["validator_contract_defined"] is True
    assert report["current_state"]["runtime_adapter_migrated"] is False
    assert report["current_state"]["postgres_dictionary_tables_created"] is False
    assert report["current_state"]["canonical_dictionary_write_performed"] is False
    assert report["current_state"]["ordinary_exports_require_live_dsn"] is False


def test_inventory_covers_rules_formal_algorithm_and_display_defaults() -> None:
    report = dictionary.build_contract_report()
    inventory = {(item["source_path"], item["symbol"]): item for item in report["hardcoded_inventory"]}

    assert (
        "scripts/export/dimension_adapters/i5b_people_delegation/rules.py",
        "RULE_SENSITIVE_POINTS",
    ) in inventory
    assert (
        "scripts/export/dimension_adapters/i5b_people_delegation/rules.py",
        "POSITIVE_CORE_KEYWORDS",
    ) in inventory
    assert (
        "scripts/export/dimension_adapters/i5b_people_delegation/formal_algorithm.py",
        "FORMAL_GRADE_ENUM",
    ) in inventory
    assert (
        "scripts/export/dimension_adapters/i5b_people_delegation/formal_algorithm.py",
        "AUTO_DIRECTION_TO_FORMAL_GRADE",
    ) in inventory
    assert (
        "scripts/export/dimension_adapters/i5b_people_delegation/adapter.py",
        "render_score_mapping_draft",
    ) in inventory
    assert (
        "scripts/export/dimension_adapters/i5b_people_delegation/adapter.py",
        "render_formal_person_section",
    ) in inventory


def test_inventory_separates_rule_keyword_grade_mapping_and_display_dictionaries() -> None:
    by_type = dictionary.build_contract_report()["inventory_by_type"]

    assert "rule_dictionary" in by_type
    assert "rule_keyword_dictionary" in by_type
    assert "grade_dictionary" in by_type
    assert "direction_grade_mapping" in by_type
    assert "display_dictionary" in by_type
    assert "RULE_SENSITIVE_POINTS" in by_type["rule_dictionary"]
    assert "DIRECT_SAFETY_KEYWORDS" in by_type["rule_keyword_dictionary"]
    assert "FORMAL_GRADE_SPECS" in by_type["grade_dictionary"]
    assert "FORMAL_GRADE_BAND_POSITION" in by_type["direction_grade_mapping"]
    assert "render_formal_person_section" in by_type["display_dictionary"]


def test_snapshot_loader_and_validator_contracts_are_auditable_and_offline() -> None:
    report = dictionary.build_contract_report()

    schema = report["snapshot_schema"]
    assert set(dictionary.SNAPSHOT_SCHEMA_REQUIRED_FIELDS) <= set(schema["required_fields"])
    assert schema["digest_policy"] == "sha256_over_stable_json_payload"
    assert schema["canonical_target"] == "postgres_or_versioned_snapshot_followup"

    loader = report["loader_contract"]
    assert loader["runtime_dsn_required"] is False
    assert loader["offline_deterministic_rerun_required"] is True
    assert set(dictionary.LOADER_CONTRACT_REQUIRED_CHECKS) <= set(loader["required_checks"])

    validator = report["validator_contract"]
    assert validator["fails_if_missing_digest"] is True
    assert validator["fails_if_unversioned"] is True
    assert validator["fails_if_locale_missing_for_display"] is True
    assert set(dictionary.VALIDATOR_CONTRACT_REQUIRED_CHECKS) <= set(validator["required_checks"])


def test_blocked_outputs_keep_contract_from_becoming_runtime_migration() -> None:
    report = dictionary.build_contract_report()

    assert "postgres_dictionary_table_creation" in report["blocked_outputs"]
    assert "canonical_dictionary_write" in report["blocked_outputs"]
    assert "runtime_adapter_migration" in report["blocked_outputs"]
    assert "ordinary_export_runtime_dsn_dependency" in report["blocked_outputs"]
    assert "g10_destructive_cleanup" in report["blocked_outputs"]
    assert report["next_required_work"] == "issue311_dictionary_snapshot_loader_validator_package"


def test_report_text_does_not_claim_runtime_migration_or_publication_release() -> None:
    text = dictionary.report_as_json(dictionary.build_contract_report()).lower()

    assert '"runtime_adapter_migrated": false' in text
    assert '"postgres_dictionary_tables_created": false' in text
    assert '"canonical_dictionary_write_performed": false' in text
    assert '"ordinary_exports_require_live_dsn": false' in text
    assert '"g10_destructive_cleanup_entered": false' in text
    assert '"runtime_adapter_migrated": true' not in text
    assert '"canonical_dictionary_write_performed": true' not in text
    assert '"ordinary_exports_require_live_dsn": true' not in text
    assert '"new_subitem_formal_scores_released": true' not in text


def test_default_reports_do_not_read_secret_data_or_runtime_paths(monkeypatch) -> None:
    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        parts = tuple(self.parts)
        if (
            self.name == ".env"
            or "batches" in parts
            or ("archive" in parts and "data" in parts)
            or self.name == "evidence_cards.jsonl"
        ):
            raise AssertionError(f"forbidden path read: {self}")
        return original_read_text(self, *args, **kwargs)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in dictionary contract tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = dictionary.build_contract_report()
    markdown = dictionary.render_dictionary_md()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["default_modes_side_effect_free"] is True
    assert report["does_not_read_canonical_jsonl"] is True
    assert report["does_not_write_business_tables"] is True
    assert "I5B Rule And Display Dictionary Contract" in markdown


def test_cli_modes_emit_expected_outputs(capsys) -> None:
    assert dictionary.main(["--contract-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "contract-report"

    assert dictionary.main(["--dictionary-md"]) == 0
    markdown = capsys.readouterr().out
    assert "I5B Rule And Display Dictionary Contract" in markdown
    assert "rule_keyword_dictionary" in markdown
    assert "digest_sha256" in markdown


def test_source_does_not_import_runtime_or_secret_clients() -> None:
    source = (ROOT / "scripts" / "platform" / "i5b_rule_display_dictionary_contract.py").read_text(
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
