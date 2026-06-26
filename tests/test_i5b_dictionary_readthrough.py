from __future__ import annotations

import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from export.dimension_adapters.i5b_people_delegation import dictionary_readthrough, formal_algorithm, rules  # noqa: E402
from scripts.platform import i5b_dictionary_snapshot_loader_validator as platform_loader  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / ".env",
    ROOT / "data" / "evidence_cards.jsonl",
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "exports",
]


def test_readthrough_loads_default_snapshot_and_matches_platform_validator() -> None:
    snapshot = dictionary_readthrough.load_dictionary_snapshot()

    assert snapshot["snapshot_version"] == dictionary_readthrough.SNAPSHOT_VERSION
    assert dictionary_readthrough.validate_dictionary_snapshot(snapshot) == []
    assert platform_loader.validate_snapshot(snapshot) == []
    assert len(snapshot["items"]) == 5


def test_readthrough_groups_dictionary_items_by_type() -> None:
    snapshot = dictionary_readthrough.load_validated_dictionary_snapshot()
    grouped = dictionary_readthrough.dictionary_items_by_type(snapshot)

    assert set(grouped) == {
        "direction_grade_mapping",
        "display_dictionary",
        "grade_dictionary",
        "rule_dictionary",
        "rule_keyword_dictionary",
    }
    assert grouped["grade_dictionary"][0]["rule_id"] == "i5b.grade_dictionary.v1"
    assert grouped["display_dictionary"][0]["payload"]["externalization_target"] == "i5b_display_dictionary"


def test_readthrough_supports_rule_id_lookup_and_source_symbol_index() -> None:
    snapshot = dictionary_readthrough.load_validated_dictionary_snapshot()

    item = dictionary_readthrough.dictionary_item_by_rule_id("i5b.rule_keyword_dictionary.v1", snapshot)
    assert item["dictionary_type"] == "rule_keyword_dictionary"
    assert "DIRECT_SAFETY_KEYWORDS" in item["payload"]["source_symbols"]

    symbols = dictionary_readthrough.source_symbols_by_dictionary_type(snapshot)
    assert "FORMAL_GRADE_ENUM" in symbols["grade_dictionary"]
    assert "render_formal_person_section" in symbols["display_dictionary"]


def test_readthrough_values_match_rules_module_keyword_exports() -> None:
    snapshot = dictionary_readthrough.load_validated_dictionary_snapshot()
    values = dictionary_readthrough.values_by_symbol("i5b.rule_keyword_dictionary.v1", snapshot)

    assert tuple(values["HIGH_VALUE_ANCHOR_KEYWORDS"]) == rules.HIGH_VALUE_ANCHOR_KEYWORDS
    assert tuple(values["STARTUP_ANCHOR_KEYWORDS"]) == rules.STARTUP_ANCHOR_KEYWORDS
    assert tuple(values["BOUNDARY_ANCHOR_KEYWORDS"]) == rules.BOUNDARY_ANCHOR_KEYWORDS
    assert tuple(values["DIRECT_SAFETY_KEYWORDS"]) == rules.DIRECT_SAFETY_KEYWORDS
    assert {
        core: tuple(keywords)
        for core, keywords in values["POSITIVE_CORE_KEYWORDS"].items()
    } == rules.POSITIVE_CORE_KEYWORDS


def test_readthrough_values_match_rules_module_sensitive_points() -> None:
    snapshot = dictionary_readthrough.load_validated_dictionary_snapshot()
    values = dictionary_readthrough.values_by_symbol("i5b.rule_dictionary.v1", snapshot)

    assert values["RULE_SENSITIVE_POINTS"] == rules.RULE_SENSITIVE_POINTS


def test_readthrough_values_match_formal_algorithm_grade_exports() -> None:
    snapshot = dictionary_readthrough.load_validated_dictionary_snapshot()
    values = dictionary_readthrough.values_by_symbol("i5b.grade_dictionary.v1", snapshot)

    assert tuple(values["FORMAL_GRADE_ENUM"]) == formal_algorithm.FORMAL_GRADE_ENUM
    assert {
        grade: {
            "min_pct": str(spec["min_pct"]),
            "max_pct": str(spec["max_pct"]),
            "max_exclusive": spec["max_exclusive"],
        }
        for grade, spec in formal_algorithm.FORMAL_GRADE_SPECS.items()
    } == values["FORMAL_GRADE_SPECS"]


def test_readthrough_values_match_formal_algorithm_direction_mapping_exports() -> None:
    snapshot = dictionary_readthrough.load_validated_dictionary_snapshot()
    values = dictionary_readthrough.values_by_symbol("i5b.direction_grade_mapping.v1", snapshot)

    assert values["AUTO_DIRECTION_TO_FORMAL_GRADE"] == formal_algorithm.AUTO_DIRECTION_TO_FORMAL_GRADE
    assert values["FORMAL_GRADE_BAND_POSITION"] == formal_algorithm.FORMAL_GRADE_BAND_POSITION


def test_rules_module_no_longer_embeds_keyword_or_sensitive_point_literals() -> None:
    source = (
        ROOT
        / "scripts"
        / "export"
        / "dimension_adapters"
        / "i5b_people_delegation"
        / "rules.py"
    ).read_text(encoding="utf-8")

    assert "HIGH_VALUE_ANCHOR_KEYWORDS = (" not in source
    assert "STARTUP_ANCHOR_KEYWORDS = (" not in source
    assert "BOUNDARY_ANCHOR_KEYWORDS = (" not in source
    assert "DIRECT_SAFETY_KEYWORDS = (" not in source
    assert "RULE-I5B-BOUNDARY-WEAK-TO-MEDIUM" not in source
    assert 'values_by_symbol("i5b.rule_keyword_dictionary.v1")' in source
    assert 'values_by_symbol("i5b.rule_dictionary.v1")' in source
    assert '_RULE_KEYWORD_VALUES["POSITIVE_CORE_KEYWORDS"]' in source
    assert '_RULE_DICTIONARY_VALUES["RULE_SENSITIVE_POINTS"]' in source


def test_formal_algorithm_no_longer_embeds_grade_or_direction_mapping_literals() -> None:
    source = (
        ROOT
        / "scripts"
        / "export"
        / "dimension_adapters"
        / "i5b_people_delegation"
        / "formal_algorithm.py"
    ).read_text(encoding="utf-8")

    assert "FORMAL_GRADE_ENUM = (" not in source
    assert '"历史极限": {"min_pct": Decimal("96")' not in source
    assert "AUTO_DIRECTION_TO_FORMAL_GRADE = {" not in source
    assert "FORMAL_GRADE_BAND_POSITION = {" not in source
    assert 'values_by_symbol("i5b.grade_dictionary.v1")' in source
    assert 'values_by_symbol("i5b.direction_grade_mapping.v1")' in source


def test_readthrough_rejects_tampered_digest() -> None:
    snapshot = dictionary_readthrough.load_dictionary_snapshot()
    snapshot["items"][0]["payload"]["source_symbols"].append("TAMPERED_SYMBOL")

    errors = dictionary_readthrough.validate_dictionary_snapshot(snapshot)

    assert "items[0].digest_sha256_mismatch" in errors


def test_readthrough_default_path_is_side_effect_free(monkeypatch) -> None:
    original_read_text = Path.read_text
    allowed_reads = {dictionary_readthrough.DEFAULT_SNAPSHOT_PATH.resolve()}

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
        raise AssertionError("network access is forbidden in readthrough tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    snapshot = dictionary_readthrough.load_validated_dictionary_snapshot()
    symbols = dictionary_readthrough.source_symbols_by_dictionary_type(snapshot)

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert "RULE_SENSITIVE_POINTS" in symbols["rule_dictionary"]


def test_source_does_not_import_runtime_or_secret_clients() -> None:
    source = (
        ROOT
        / "scripts"
        / "export"
        / "dimension_adapters"
        / "i5b_people_delegation"
        / "dictionary_readthrough.py"
    ).read_text(encoding="utf-8")

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
