from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

VALIDATE_REVIEW_CONFIGS_SPEC = importlib.util.spec_from_file_location(
    "validate_review_configs",
    ROOT / "scripts" / "validate_review_configs.py",
)
assert VALIDATE_REVIEW_CONFIGS_SPEC is not None
validate_review_configs = importlib.util.module_from_spec(VALIDATE_REVIEW_CONFIGS_SPEC)
assert VALIDATE_REVIEW_CONFIGS_SPEC.loader is not None
VALIDATE_REVIEW_CONFIGS_SPEC.loader.exec_module(validate_review_configs)


def test_validate_review_configs_cli_passes_on_repo_data() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_review_configs.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Review config validation passed." in result.stdout


def test_validate_review_configs_rejects_invalid_json(tmp_path: Path, monkeypatch) -> None:
    profiles_path = tmp_path / "search_keyword_profiles.jsonl"
    overrides_path = tmp_path / "search_keyword_overrides.jsonl"
    profiles_path.write_text("{bad json}\n", encoding="utf-8")
    overrides_path.write_text("", encoding="utf-8")

    monkeypatch.setattr(validate_review_configs, "SEARCH_KEYWORD_PROFILES_PATH", profiles_path)
    monkeypatch.setattr(validate_review_configs, "SEARCH_KEYWORD_OVERRIDES_PATH", overrides_path)

    errors = validate_review_configs.validate()

    assert len(errors) == 1
    assert f"{profiles_path}: line 1: invalid JSON" in errors[0]


def test_validate_review_configs_rejects_non_object_rows(tmp_path: Path, monkeypatch) -> None:
    profiles_path = tmp_path / "search_keyword_profiles.jsonl"
    overrides_path = tmp_path / "search_keyword_overrides.jsonl"
    profiles_path.write_text('["not", "object"]\n', encoding="utf-8")
    overrides_path.write_text("", encoding="utf-8")

    monkeypatch.setattr(validate_review_configs, "SEARCH_KEYWORD_PROFILES_PATH", profiles_path)
    monkeypatch.setattr(validate_review_configs, "SEARCH_KEYWORD_OVERRIDES_PATH", overrides_path)

    errors = validate_review_configs.validate()

    assert errors == [f"{profiles_path}: line 1: expected JSON object, got list"]


def test_validate_review_configs_checks_missing_profile_fields(tmp_path: Path, monkeypatch) -> None:
    profiles_path = tmp_path / "search_keyword_profiles.jsonl"
    overrides_path = tmp_path / "search_keyword_overrides.jsonl"
    profiles_path.write_text(
        '{"profile_id": "A", "item": "I", "subitem": "S", "dimension": "D", "polarity": "invalid", '
        '"keyword_family": "positive_scan", "terms": [], "priority": "priority"}\n',
        encoding="utf-8",
    )
    overrides_path.write_text("", encoding="utf-8")

    monkeypatch.setattr(validate_review_configs, "SEARCH_KEYWORD_PROFILES_PATH", profiles_path)
    monkeypatch.setattr(validate_review_configs, "SEARCH_KEYWORD_OVERRIDES_PATH", overrides_path)

    errors = validate_review_configs.validate()

    assert f"{profiles_path}: line 1: missing required fields: purpose" in errors
    assert (
        f"{profiles_path}: line 1: terms must be a non-empty list of non-empty strings" in errors
    )
    assert (
        f"{profiles_path}: line 1: polarity must be one of "
        f"{sorted(validate_review_configs.ALLOWED_POLARITIES)}, got 'invalid'" in errors
    )
    assert f"{profiles_path}: line 1: priority must match P<number>, got 'priority'" in errors


def test_validate_review_configs_rejects_duplicate_profile_ids(tmp_path: Path, monkeypatch) -> None:
    profiles_path = tmp_path / "search_keyword_profiles.jsonl"
    overrides_path = tmp_path / "search_keyword_overrides.jsonl"
    profiles_path.write_text(
        (
            '{"profile_id": "DUP", "item": "I", "subitem": "S", "dimension": "D", '
            '"polarity": "positive", "keyword_family": "positive_scan", '
            '"terms": ["a"], "purpose": "p", "priority": "P1"}\n'
            '{"profile_id": "DUP", "item": "I", "subitem": "S", "dimension": "D", '
            '"polarity": "positive", "keyword_family": "positive_scan", '
            '"terms": ["b"], "purpose": "p", "priority": "P1"}\n'
        ),
        encoding="utf-8",
    )
    overrides_path.write_text("", encoding="utf-8")

    monkeypatch.setattr(validate_review_configs, "SEARCH_KEYWORD_PROFILES_PATH", profiles_path)
    monkeypatch.setattr(validate_review_configs, "SEARCH_KEYWORD_OVERRIDES_PATH", overrides_path)

    errors = validate_review_configs.validate()

    assert (
        f"{profiles_path}: line 2: duplicate profile_id 'DUP' (already defined at line 1)" in errors
    )


def test_validate_review_configs_checks_override_reference_and_types(
    tmp_path: Path, monkeypatch
) -> None:
    profiles_path = tmp_path / "search_keyword_profiles.jsonl"
    overrides_path = tmp_path / "search_keyword_overrides.jsonl"
    profiles_path.write_text(
        (
            '{"profile_id": "BASE", "item": "I", "subitem": "S", "dimension": "D", '
            '"polarity": "positive", "keyword_family": "positive_scan", '
            '"terms": ["a"], "purpose": "p", "priority": "P1"}\n'
        ),
        encoding="utf-8",
    )
    overrides_path.write_text(
        (
            '{"override_id": "O1", "base_profile_id": "MISSING", "scope_type": "bad", '
            '"scope_key": "", "add_terms": ["ok", ""], "suppress_terms": "bad", '
            '"replace_terms": [], "reason": ""}\n'
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(validate_review_configs, "SEARCH_KEYWORD_PROFILES_PATH", profiles_path)
    monkeypatch.setattr(validate_review_configs, "SEARCH_KEYWORD_OVERRIDES_PATH", overrides_path)

    errors = validate_review_configs.validate()

    assert f"{overrides_path}: line 1: scope_key must be a non-empty string" in errors
    assert f"{overrides_path}: line 1: reason must be a non-empty string" in errors
    assert f"{overrides_path}: line 1: add_terms must be a list of non-empty strings" in errors
    assert f"{overrides_path}: line 1: suppress_terms must be a list of non-empty strings" in errors
    assert f"{overrides_path}: line 1: replace_terms must be an object" in errors
    assert (
        f"{overrides_path}: line 1: scope_type must be one of "
        f"{sorted(validate_review_configs.ALLOWED_SCOPE_TYPES)}, got 'bad'" in errors
    )
    assert (
        f"{overrides_path}: line 1: base_profile_id 'MISSING' does not exist in "
        "search_keyword_profiles.jsonl" in errors
    )


def test_validate_review_configs_rejects_duplicate_override_ids(
    tmp_path: Path, monkeypatch
) -> None:
    profiles_path = tmp_path / "search_keyword_profiles.jsonl"
    overrides_path = tmp_path / "search_keyword_overrides.jsonl"
    profiles_path.write_text(
        (
            '{"profile_id": "BASE", "item": "I", "subitem": "S", "dimension": "D", '
            '"polarity": "positive", "keyword_family": "positive_scan", '
            '"terms": ["a"], "purpose": "p", "priority": "P1"}\n'
        ),
        encoding="utf-8",
    )
    overrides_path.write_text(
        (
            '{"override_id": "DUP", "base_profile_id": "BASE", "scope_type": "era", '
            '"scope_key": "E", "add_terms": [], "reason": "r"}\n'
            '{"override_id": "DUP", "base_profile_id": "BASE", "scope_type": "person", '
            '"scope_key": "P", "add_terms": [], "reason": "r"}\n'
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(validate_review_configs, "SEARCH_KEYWORD_PROFILES_PATH", profiles_path)
    monkeypatch.setattr(validate_review_configs, "SEARCH_KEYWORD_OVERRIDES_PATH", overrides_path)

    errors = validate_review_configs.validate()

    assert (
        f"{overrides_path}: line 2: duplicate override_id 'DUP' (already defined at line 1)" in errors
    )
