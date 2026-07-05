from __future__ import annotations

import json
import os

import pytest

from scripts.dev import retrieval_v2_bootstrap as tool


def test_stable_fingerprint_is_key_order_independent() -> None:
    left = {"b": [2, 1], "a": {"z": "x"}}
    right = {"a": {"z": "x"}, "b": [2, 1]}

    assert tool.stable_fingerprint(left) == tool.stable_fingerprint(right)
    assert len(tool.stable_fingerprint(left)) == 64


def test_normalize_alias_removes_spacing_and_casefolds() -> None:
    assert tool.normalize_alias(" Li  Shi Min ") == "lishimin"
    assert tool.normalize_alias("李 世 民") == "李世民"


def test_requirement_payload_keeps_anti_nepotism_non_core_for_retrieval_ready() -> None:
    core = tool.requirement_payload("delegation", [{"policy_code": "person"}], [])
    non_core = tool.requirement_payload("anti_nepotism", [], [])

    assert core["is_core_for_retrieval"] is True
    assert core["min_usable_claims"] == 1
    assert non_core["is_core_for_retrieval"] is False
    assert non_core["min_usable_claims"] == 0
    assert core["clean_process_doc"] == "docs/数据结构与生成库/retrieval_v2_clean抓包流程.md"


def test_delegation_requirement_payload_contains_coverage_contract() -> None:
    payload = tool.requirement_payload(
        "delegation",
        [{"policy_code": "person"}],
        [{"predicate": "delegated_authority"}],
    )

    matrix = payload["coverage_matrix"]
    family_codes = {row["family_code"] for row in matrix["role_families"]}
    secondary_rules = {row["rule_code"] for row in matrix["secondary_rule_hints"]}

    assert {"military_delegate", "civil_delegate", "strategic_delegate", "revoked_or_failed_delegate"} <= family_codes
    assert "appointment_trust" in secondary_rules
    assert matrix["material_policy_codes"] == ["person"]
    assert matrix["predicate_options"] == ["delegated_authority"]


def test_retrieval_intent_payload_embeds_clean_policy_and_coverage_matrix() -> None:
    requirement = tool.requirement_payload("delegation", [], [])

    payload = tool.retrieval_intent_payload(
        emperor_name="李渊",
        item_code="I5B",
        rule_code="delegation",
        requirement=requirement,
    )

    assert payload["coverage_matrix"]["rule_code"] == "delegation"
    assert payload["clean_input_policy"]["forbid_old_judgement_outputs"] is True
    assert payload["clean_input_policy"]["judge_stage_no_memory"] is True


def test_source_snapshot_fingerprint_covers_rule_policy_and_predicate_rows() -> None:
    snapshot = tool.SourceSnapshot(
        item_rows=[{"id": 1, "item_code": "I5B"}],
        rule_rows=[{"id": 10, "item_id": 1, "item_code": "I5B", "rule_code": "delegation"}],
        material_policy_rows=[{"id": 20, "rule_code": "delegation", "policy_code": "person"}],
        predicate_option_rows=[{"id": 30, "rule_code": "delegation", "predicate": "delegated_authority"}],
        factor_rows=[{"id": 40, "rule_code": "delegation", "factor_name": "source_factor"}],
        factor_option_rows=[{"id": 50, "factor_id": 40, "label": "基础史源"}],
    )
    changed = tool.SourceSnapshot(
        item_rows=snapshot.item_rows,
        rule_rows=snapshot.rule_rows,
        material_policy_rows=snapshot.material_policy_rows,
        predicate_option_rows=snapshot.predicate_option_rows,
        factor_rows=snapshot.factor_rows,
        factor_option_rows=[{"id": 50, "factor_id": 40, "label": "不同取值"}],
    )

    assert snapshot.fingerprint != changed.fingerprint


def test_contract_rule_payloads_are_rule_scoped() -> None:
    snapshot = tool.SourceSnapshot(
        item_rows=[],
        rule_rows=[],
        material_policy_rows=[
            {"id": 1, "rule_code": "delegation"},
            {"id": 2, "rule_code": "talent_discovery"},
        ],
        predicate_option_rows=[
            {"id": 3, "rule_code": "delegation"},
            {"id": 4, "rule_code": "tolerate_talent"},
        ],
    )

    material, predicates = tool.contract_rule_payloads(snapshot, "delegation")

    assert material == [{"id": 1, "rule_code": "delegation"}]
    assert predicates == [{"id": 3, "rule_code": "delegation"}]


def test_read_schema_sql_points_to_retrieval_v2_migration() -> None:
    sql = tool.read_schema_sql()

    assert "create schema if not exists retrieval_v2" in sql
    assert "create table if not exists retrieval_v2.rule_contracts" in sql
    assert "create table if not exists retrieval_v2.claim_rule_binding_candidates" in sql
    assert "create type retrieval_v2.rv2_review_status as enum" in sql


def test_print_schema_cli_outputs_sql(capsys: pytest.CaptureFixture[str]) -> None:
    assert tool.main(["--print-schema"]) == 0

    captured = capsys.readouterr()
    assert "retrieval_v2.claim_rule_bindings" in captured.out
    assert "retrieval_v2.claim_rule_binding_candidates" in captured.out


def test_missing_action_is_a_usage_error() -> None:
    with pytest.raises(tool.RetrievalV2BootstrapError, match="no action requested"):
        tool.main([])


def test_pretty_json_keeps_utf8() -> None:
    payload = {"emperor": "李渊"}

    assert json.loads(tool.pretty_json(payload)) == payload


def test_load_env_file_sets_missing_keys_without_overriding(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "# ignored",
                "EMPEROR_EVAL_PG_DSN=postgresql://source",
                "EXISTING_DSN=should_not_win",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("EMPEROR_EVAL_PG_DSN", raising=False)
    monkeypatch.setenv("EXISTING_DSN", "already-set")

    loaded = tool.load_env_file(env_path)

    assert loaded == ["EMPEROR_EVAL_PG_DSN"]
    assert os.environ["EMPEROR_EVAL_PG_DSN"] == "postgresql://source"
    assert os.environ["EXISTING_DSN"] == "already-set"
