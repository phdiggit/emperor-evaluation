from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

VALIDATE_CLUSTER_CONFIGS_SPEC = importlib.util.spec_from_file_location(
    "validate_i5b_cluster_adjudication_configs",
    ROOT / "scripts" / "validate_i5b_cluster_adjudication_configs.py",
)
assert VALIDATE_CLUSTER_CONFIGS_SPEC is not None
validate_i5b_cluster_adjudication_configs = importlib.util.module_from_spec(VALIDATE_CLUSTER_CONFIGS_SPEC)
assert VALIDATE_CLUSTER_CONFIGS_SPEC.loader is not None
VALIDATE_CLUSTER_CONFIGS_SPEC.loader.exec_module(validate_i5b_cluster_adjudication_configs)


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")


def valid_rule(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "rule_id": "I5B-CLUSTER-WARN-TEST",
        "enabled": False,
        "subitem": "第五项B",
        "trigger_type": "trigger_terms",
        "trigger_terms": ["测试词"],
        "polarity_scope": ["positive", "negative"],
        "evidence_strength_scope": ["candidate_strength_3"],
        "warning_type": "source_review_required",
        "warning_message": "仅提示人工复核，不产生裁判结论。",
        "adjacent_item_risk": ["第五项C"],
        "required_human_review": True,
        "note": "本规则只提示人工复核，不产生裁判结论、定档、分数或排名。",
    }
    row.update(overrides)
    return row


def test_validate_i5b_cluster_adjudication_configs_cli_passes_on_repo_disabled_rules() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_i5b_cluster_adjudication_configs.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "I5B cluster adjudication config validation passed." in result.stdout


def test_repo_config_contains_four_disabled_warning_rules() -> None:
    rows = json.loads(validate_i5b_cluster_adjudication_configs.CONFIG_PATH.read_text(encoding="utf-8"))

    assert [row["rule_id"] for row in rows] == [
        "I5B-CLUSTER-WARN-ADJACENT-CONTAMINATION",
        "I5B-CLUSTER-WARN-SINGLE-EVIDENCE-LIMIT",
        "I5B-CLUSTER-WARN-SOURCE-REVIEW-REQUIRED",
        "I5B-CLUSTER-WARN-MIXED-POLARITY",
    ]
    assert all(row["enabled"] is False for row in rows)
    assert all(row["required_human_review"] is True for row in rows)


def test_empty_array_passes(tmp_path: Path) -> None:
    config_path = tmp_path / "第五项B_证据簇裁判提示.json"
    write_json(config_path, [])

    assert validate_i5b_cluster_adjudication_configs.validate(config_path) == []


def test_non_array_top_level_fails(tmp_path: Path) -> None:
    config_path = tmp_path / "第五项B_证据簇裁判提示.json"
    write_json(config_path, {"rule_id": "RULE"})

    errors = validate_i5b_cluster_adjudication_configs.validate(config_path)

    assert errors == [f"{config_path}: line 1: expected top-level JSON array, got dict"]


def test_non_object_array_item_fails(tmp_path: Path) -> None:
    config_path = tmp_path / "第五项B_证据簇裁判提示.json"
    write_json(config_path, [["not", "object"]])

    errors = validate_i5b_cluster_adjudication_configs.validate(config_path)

    assert errors == [f"{config_path}: line 1: expected array item to be JSON object, got list"]


def test_required_fields_fail_when_missing_or_wrong_type(tmp_path: Path) -> None:
    config_path = tmp_path / "第五项B_证据簇裁判提示.json"
    write_json(
        config_path,
        [
            {
                "trigger_type": "",
                "warning_type": "",
                "note": "",
                "required_human_review": "yes",
            }
        ],
    )

    errors = validate_i5b_cluster_adjudication_configs.validate(config_path)

    assert any(error.endswith("rule_id must be a non-empty string") for error in errors)
    assert any(error.endswith("subitem must be '第五项B'") for error in errors)
    assert any(error.endswith("trigger_type must be a non-empty string") for error in errors)
    assert any(error.endswith("warning_type must be a non-empty string") for error in errors)
    assert any(error.endswith("warning_message must be a non-empty string") for error in errors)
    assert any(error.endswith("required_human_review must be a bool") for error in errors)
    assert any(error.endswith("note must be a non-empty string") for error in errors)
    assert any(error.endswith("enabled is required") for error in errors)
    assert any(error.endswith("trigger_terms is required") for error in errors)
    assert any(error.endswith("polarity_scope is required") for error in errors)
    assert any(error.endswith("evidence_strength_scope is required") for error in errors)
    assert any(error.endswith("adjacent_item_risk is required") for error in errors)


def test_duplicate_rule_id_fails(tmp_path: Path) -> None:
    config_path = tmp_path / "第五项B_证据簇裁判提示.json"
    write_json(config_path, [valid_rule(), valid_rule(warning_type="single_evidence_limit")])

    errors = validate_i5b_cluster_adjudication_configs.validate(config_path)

    assert any("duplicate rule_id 'I5B-CLUSTER-WARN-TEST'" in error for error in errors)


def test_forbidden_result_fields_fail(tmp_path: Path) -> None:
    config_path = tmp_path / "第五项B_证据簇裁判提示.json"
    write_json(
        config_path,
        [
            valid_rule(
                final_score=100,
                ranking=1,
                definitive_band="极正",
            )
        ],
    )

    errors = validate_i5b_cluster_adjudication_configs.validate(config_path)

    assert any("forbidden result field is not allowed" in error and "final_score" in error for error in errors)
    assert any("forbidden result field is not allowed" in error and "ranking" in error for error in errors)
    assert any("forbidden result field is not allowed" in error and "definitive_band" in error for error in errors)


def test_first_phase_concrete_binding_fields_fail(tmp_path: Path) -> None:
    config_path = tmp_path / "第五项B_证据簇裁判提示.json"
    write_json(
        config_path,
        [
            valid_rule(
                person="刘邦",
                cluster_id="ADJ-I5B-TEST",
                evidence_id="EVD-I5B-TEST",
                auto_band_direction="强正受压制",
                candidate_strength=3,
            )
        ],
    )

    errors = validate_i5b_cluster_adjudication_configs.validate(config_path)

    assert any("first-phase skeleton must not bind concrete adjudication data field: person" in error for error in errors)
    assert any("first-phase skeleton must not bind concrete adjudication data field: cluster_id" in error for error in errors)
    assert any("first-phase skeleton must not bind concrete adjudication data field: evidence_id" in error for error in errors)
    assert any("first-phase skeleton must not bind concrete adjudication data field: auto_band_direction" in error for error in errors)
    assert any("first-phase skeleton must not bind concrete adjudication data field: candidate_strength" in error for error in errors)


def test_enabled_true_fails(tmp_path: Path) -> None:
    config_path = tmp_path / "第五项B_证据簇裁判提示.json"
    write_json(config_path, [valid_rule(enabled=True)])

    errors = validate_i5b_cluster_adjudication_configs.validate(config_path)

    assert any(validate_i5b_cluster_adjudication_configs.ENABLED_RULE_ERROR in error for error in errors)


def test_missing_enabled_fails(tmp_path: Path) -> None:
    config_path = tmp_path / "第五项B_证据簇裁判提示.json"
    row = valid_rule()
    row.pop("enabled")
    write_json(config_path, [row])

    errors = validate_i5b_cluster_adjudication_configs.validate(config_path)

    assert any(error.endswith("enabled is required") for error in errors)


def test_enabled_must_be_bool(tmp_path: Path) -> None:
    config_path = tmp_path / "第五项B_证据簇裁判提示.json"
    write_json(config_path, [valid_rule(enabled="false")])

    errors = validate_i5b_cluster_adjudication_configs.validate(config_path)

    assert any(error.endswith("enabled must be a bool") for error in errors)


def test_required_human_review_false_fails(tmp_path: Path) -> None:
    config_path = tmp_path / "第五项B_证据簇裁判提示.json"
    write_json(config_path, [valid_rule(required_human_review=False)])

    errors = validate_i5b_cluster_adjudication_configs.validate(config_path)

    assert any(error.endswith("required_human_review must be true") for error in errors)


def test_missing_required_human_review_fails(tmp_path: Path) -> None:
    config_path = tmp_path / "第五项B_证据簇裁判提示.json"
    row = valid_rule()
    row.pop("required_human_review")
    write_json(config_path, [row])

    errors = validate_i5b_cluster_adjudication_configs.validate(config_path)

    assert any(error.endswith("required_human_review is required") for error in errors)


def test_string_array_fields_must_be_non_empty_string_arrays(tmp_path: Path) -> None:
    config_path = tmp_path / "第五项B_证据簇裁判提示.json"
    write_json(
        config_path,
        [
            valid_rule(
                trigger_terms=[],
                polarity_scope="positive",
                evidence_strength_scope=[""],
                adjacent_item_risk=["第五项C"],
            )
        ],
    )

    errors = validate_i5b_cluster_adjudication_configs.validate(config_path)

    assert any(error.endswith("trigger_terms must be a non-empty list of non-empty strings") for error in errors)
    assert any(error.endswith("polarity_scope must be a non-empty list of non-empty strings") for error in errors)
    assert any(error.endswith("evidence_strength_scope must be a non-empty list of non-empty strings") for error in errors)


def test_rule_id_must_not_contain_person_or_evidence_cluster_ids(tmp_path: Path) -> None:
    config_path = tmp_path / "第五项B_证据簇裁判提示.json"
    write_json(
        config_path,
        [
            valid_rule(rule_id="I5B-CLUSTER-WARN-刘邦"),
            valid_rule(rule_id="I5B-CLUSTER-WARN-EVD-I5B-TEST"),
            valid_rule(rule_id="I5B-CLUSTER-WARN-ADJ-I5B-TEST"),
        ],
    )

    errors = validate_i5b_cluster_adjudication_configs.validate(config_path)

    assert sum("rule_id must not contain person names or evidence/cluster/search/source ids" in error for error in errors) == 3


def test_cjk_unicode_escape_fails(tmp_path: Path) -> None:
    config_path = tmp_path / "第五项B_证据簇裁判提示.json"
    config_path.write_text(
        '[{"rule_id": "RULE", "enabled": false, "subitem": "\\u7b2c\\u4e94\\u9879B", "trigger_type": "x", "trigger_terms": ["x"], "polarity_scope": ["positive"], "evidence_strength_scope": ["candidate_strength_1"], "warning_type": "x", "warning_message": "x", "adjacent_item_risk": ["x"], "required_human_review": true, "note": "x"}]\n',
        encoding="utf-8",
    )

    errors = validate_i5b_cluster_adjudication_configs.validate(config_path)

    assert errors == [
        f"{config_path}: line 1: found escaped CJK unicode sequence '\\\\u7b2c'; "
        "user-editable config must use UTF-8 Chinese text directly"
    ]
