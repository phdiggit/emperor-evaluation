from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

VALIDATE_VIEW_CONFIGS_SPEC = importlib.util.spec_from_file_location(
    "validate_view_configs",
    ROOT / "scripts" / "validate_view_configs.py",
)
assert VALIDATE_VIEW_CONFIGS_SPEC is not None
validate_view_configs = importlib.util.module_from_spec(VALIDATE_VIEW_CONFIGS_SPEC)
assert VALIDATE_VIEW_CONFIGS_SPEC.loader is not None
VALIDATE_VIEW_CONFIGS_SPEC.loader.exec_module(validate_view_configs)


def test_validate_view_configs_cli_passes_on_repo_data() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_view_configs.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "View config validation passed." in result.stdout


def test_validate_view_configs_rejects_invalid_json(tmp_path: Path, monkeypatch) -> None:
    config_dir = tmp_path / "view_configs"
    config_dir.mkdir()
    (config_dir / "broken.jsonl").write_text("{bad json}\n", encoding="utf-8")

    monkeypatch.setattr(validate_view_configs, "VIEW_CONFIG_DIR", config_dir)

    errors = validate_view_configs.validate()

    assert len(errors) == 1
    assert "broken.jsonl: line 1: invalid JSON" in errors[0]


def test_validate_view_configs_rejects_non_object_rows(tmp_path: Path, monkeypatch) -> None:
    config_dir = tmp_path / "view_configs"
    config_dir.mkdir()
    (config_dir / "not-object.jsonl").write_text('["not", "object"]\n', encoding="utf-8")

    monkeypatch.setattr(validate_view_configs, "VIEW_CONFIG_DIR", config_dir)

    errors = validate_view_configs.validate()

    assert errors == [f"{config_dir / 'not-object.jsonl'}: line 1: expected JSON object, got list"]


def test_validate_view_configs_checks_i5b_required_fields_and_priority(
    tmp_path: Path, monkeypatch
) -> None:
    config_dir = tmp_path / "view_configs"
    config_dir.mkdir()
    i5b_path = config_dir / "i5b_expanded_candidate_pool.jsonl"
    i5b_path.write_text(
        (
            '{"person": "A", "candidate_type": "B", "why_selected": "C", '
            '"expected_rule_pressure": "D", "required_evidence_focus": "E", '
            '"adjacent_item_risk": "F", "recommended_priority": "priority"}\n'
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(validate_view_configs, "VIEW_CONFIG_DIR", config_dir)
    monkeypatch.setattr(validate_view_configs, "I5B_EXPANDED_CANDIDATE_POOL_PATH", i5b_path)

    errors = validate_view_configs.validate()

    assert len(errors) == 2
    assert (
        f"{i5b_path}: line 1: missing required fields: negative_scan_focus" in errors
    )
    assert (
        f"{i5b_path}: line 1: recommended_priority must match P<number>, got 'priority'" in errors
    )


def test_validate_view_configs_checks_i5b_net_evidence_targets_schema(
    tmp_path: Path, monkeypatch
) -> None:
    config_dir = tmp_path / "view_configs"
    config_dir.mkdir()
    targets_path = config_dir / "i5b_net_evidence_targets.jsonl"
    targets_path.write_text('{"person": "", "output_path": "exports/x.md"}\n', encoding="utf-8")

    monkeypatch.setattr(validate_view_configs, "VIEW_CONFIG_DIR", config_dir)
    monkeypatch.setattr(validate_view_configs, "I5B_NET_EVIDENCE_TARGETS_PATH", targets_path)

    errors = validate_view_configs.validate()

    assert len(errors) == 2
    assert f"{targets_path}: line 1: missing required fields: export_path" in errors
    assert f"{targets_path}: line 1: person must be a non-empty string" in errors


def test_validate_view_configs_checks_i5b_expanded_batch1_targets_schema(
    tmp_path: Path, monkeypatch
) -> None:
    config_dir = tmp_path / "view_configs"
    config_dir.mkdir()
    targets_path = config_dir / "i5b_expanded_batch1_targets.jsonl"
    targets_path.write_text('{"target": ""}\n', encoding="utf-8")

    monkeypatch.setattr(validate_view_configs, "VIEW_CONFIG_DIR", config_dir)
    monkeypatch.setattr(validate_view_configs, "I5B_EXPANDED_BATCH1_TARGETS_PATH", targets_path)

    errors = validate_view_configs.validate()

    assert len(errors) == 2
    assert f"{targets_path}: line 1: missing required fields: person" in errors
    assert f"{targets_path}: line 1: target must be a non-empty string" in errors


def test_validate_view_configs_checks_i5b_trial_targets_schema(
    tmp_path: Path, monkeypatch
) -> None:
    config_dir = tmp_path / "view_configs"
    config_dir.mkdir()
    targets_path = config_dir / "i5b_trial_targets.jsonl"
    targets_path.write_text('{"target": ""}\n', encoding="utf-8")

    monkeypatch.setattr(validate_view_configs, "VIEW_CONFIG_DIR", config_dir)
    monkeypatch.setattr(validate_view_configs, "I5B_TRIAL_TARGETS_PATH", targets_path)

    errors = validate_view_configs.validate()

    assert len(errors) == 2
    assert f"{targets_path}: line 1: missing required fields: person" in errors
    assert f"{targets_path}: line 1: target must be a non-empty string" in errors
