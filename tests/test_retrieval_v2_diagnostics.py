from __future__ import annotations

import json
from pathlib import Path

from scripts.dev.retrieval_v2_diagnostics_lib import actions, cli, orchestrator, score_chain, selectors


def test_build_next_actions_maps_checks_to_commands() -> None:
    readiness = {
        "blockers": [
            {
                "code": "material_review_pending",
                "count": 2,
                "severity": "blocking",
                "owner": "human",
                "description": "review queue pending",
            }
        ],
        "downstream_required": [
            {
                "code": "factorization_required",
                "count": 3,
                "severity": "downstream",
                "owner": "agent_or_human",
                "description": "factorization needed",
            }
        ],
    }
    coverage = {
        "checks": [
            {
                "code": "material_score_required",
                "count": 4,
                "severity": "downstream",
                "owner": "agent_or_human",
                "description": "score needed",
            },
            {
                "code": "factorization_required",
                "count": 3,
                "severity": "downstream",
                "owner": "agent_or_human",
                "description": "duplicate from readiness",
            },
        ]
    }
    duplicates = {
        "checks": [
            {
                "code": "duplicate_factor_judgment_idem_key",
                "count": 1,
                "severity": "blocking",
                "owner": "human",
                "description": "duplicate",
            }
        ]
    }

    rows = actions.build_next_actions(
        readiness=readiness,
        coverage=coverage,
        duplicates=duplicates,
        item_code="I5B",
        rule_code="appointment_delegation",
        formula_code="evidence_cluster_signal_v3",
        scope="accepted-packs",
    )

    assert [row["code"] for row in rows] == [
        "material_review_pending",
        "factorization_required",
        "material_score_required",
        "duplicate_factor_judgment_idem_key",
    ]
    assert "retrieval_v2_material_review_consumer.py worklist" in rows[0]["next_command"]
    assert "retrieval_v2_factorization_worklists.py worklist" in rows[1]["next_command"]
    assert "retrieval_v2_rule_scorer.py apply" in rows[2]["next_command"]
    assert rows[3]["next_command"] == ""


def test_fetch_report_combines_components(monkeypatch) -> None:
    calls: list[str] = []

    def fake_fetch_db_report(**kwargs):
        calls.append(kwargs["command"])
        if kwargs["command"] == "summary":
            return {
                "ok": True,
                "command": "summary",
                "totals": {"targets": 2, "rule_score_clusters": 1},
            }
        if kwargs["command"] == "coverage":
            return {
                "ok": True,
                "command": "coverage",
                "checks": [
                    {
                        "code": "rule_score_required",
                        "status": "downstream",
                        "severity": "downstream",
                        "owner": "agent_or_human",
                        "count": 1,
                        "description": "cluster missing",
                    }
                ],
            }
        if kwargs["command"] == "duplicates":
            return {
                "ok": True,
                "command": "duplicates",
                "checks": [
                    {
                        "code": "duplicate_rule_score_cluster_key",
                        "status": "ok",
                        "severity": "blocking",
                        "owner": "human",
                        "count": 0,
                        "description": "duplicate check",
                    }
                ],
            }
        raise AssertionError(kwargs["command"])

    monkeypatch.setattr(orchestrator, "fetch_db_report", fake_fetch_db_report)
    monkeypatch.setattr(
        orchestrator,
        "fetch_readiness_report",
        lambda **_: {"ok": True, "command": "readiness", "blockers": [], "warnings": [], "downstream_required": []},
    )

    payload = orchestrator.fetch_report(
        env_file=None,
        dsn_env="NEW_DSN",
        item_code="I5B",
        rule_code="appointment_delegation",
        formula_code="evidence_cluster_signal_v3",
        scope="accepted-packs",
    )

    assert calls == ["summary", "coverage", "duplicates"]
    assert payload["ok"] is True
    assert payload["summary"]["totals"]["targets"] == 2
    assert payload["totals"]["next_actions"] == 1
    assert payload["next_actions"][0]["code"] == "rule_score_required"


def test_fetch_report_blocks_duplicate_checks(monkeypatch) -> None:
    def fake_fetch_db_report(**kwargs):
        if kwargs["command"] == "summary":
            return {"ok": True, "command": "summary", "totals": {}}
        if kwargs["command"] == "coverage":
            return {"ok": True, "command": "coverage", "checks": []}
        if kwargs["command"] == "duplicates":
            return {
                "ok": False,
                "command": "duplicates",
                "checks": [
                    {
                        "code": "duplicate_factor_choice_natural_key",
                        "status": "blocking",
                        "severity": "blocking",
                        "owner": "human",
                        "count": 1,
                        "description": "duplicate",
                    }
                ],
            }
        raise AssertionError(kwargs["command"])

    monkeypatch.setattr(orchestrator, "fetch_db_report", fake_fetch_db_report)
    monkeypatch.setattr(orchestrator, "fetch_readiness_report", lambda **_: {"ok": True})

    payload = orchestrator.fetch_report(
        env_file=None,
        dsn_env="NEW_DSN",
        item_code="I5B",
        rule_code="appointment_delegation",
        formula_code="evidence_cluster_signal_v3",
        scope="accepted-packs",
    )

    assert payload["ok"] is False
    assert payload["totals"]["duplicate_issues"] == 1


def test_main_report_writes_json_and_markdown(tmp_path: Path, monkeypatch, capsys) -> None:
    output_json = tmp_path / "diagnostics.json"
    output_md = tmp_path / "diagnostics.md"
    fake_payload = {
        "generated_by": "scripts/dev/retrieval_v2_diagnostics.py",
        "command": "report",
        "ok": True,
        "scope": {
            "item_code": "I5B",
            "rule_code": "appointment_delegation",
            "formula_code": "evidence_cluster_signal_v3",
            "scope": "accepted-packs",
        },
        "summary": {"totals": {"targets": 8, "rule_score_clusters": 8}},
        "readiness": {"checks": []},
        "coverage": {"checks": []},
        "duplicates": {"checks": []},
        "next_actions": [],
        "totals": {"next_actions": 0},
    }
    monkeypatch.setattr(cli, "fetch_report", lambda **_: fake_payload)

    assert cli.main([
        "report",
        "--env-file",
        ".env",
        "--item-code",
        "I5B",
        "--rule-code",
        "appointment_delegation",
        "--output-json",
        str(output_json),
        "--output-md",
        str(output_md),
    ]) == 0

    assert json.loads(output_json.read_text(encoding="utf-8"))["ok"] is True
    md = output_md.read_text(encoding="utf-8")
    assert "# retrieval_v2 diagnostics" in md
    assert "rule_score_clusters" in md
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_fetch_score_chain_builds_target_material_chain(monkeypatch) -> None:
    cluster_rows = [
        {
            "target_id": 1,
            "target_code": "TGT-I5B-LB",
            "emperor_name": "刘邦",
            "item_code": "I5B",
            "rule_code": "appointment_delegation",
            "formula_code": "evidence_cluster_signal_v3",
            "positive_signal": "2.500",
            "negative_signal": "1.000",
            "scored_judgment_count": 2,
            "supporting_judgment_count": 1,
            "excluded_judgment_count": 0,
            "object_side_scores": {"positive": {"10": "2.500"}, "negative": {"11": "1.000"}},
            "calc_detail": {
                "formula_params": {"material_score_cap": "4.0", "same_object_secondary_factor": "0.35"},
                "object_side_scores": {
                    "positive": {"10": {"object_name": "萧何", "score": "2.500"}},
                    "negative": {"11": {"object_name": "韩信", "score": "1.000"}},
                },
            },
            "review_status": "accepted",
        }
    ]
    material_rows = [
        {
            "target_code": "TGT-I5B-LB",
            "emperor_name": "刘邦",
            "factor_judgment_id": 101,
            "binding_id": 201,
            "binding_code": "BND-101",
            "claim_id": 301,
            "claim_code": "CLM-301",
            "claim_summary": "刘邦委任萧何主持关中转输。",
            "claim_object_name": "萧何",
            "claim_direction": "positive",
            "predicate": "delegated_authority",
            "binding_direction": "positive",
            "object_role": "civil_delegate",
            "object_id": 10,
            "target_object_id": 1001,
            "object_name": "萧何",
            "side": "positive",
            "judgment_side": "positive",
            "raw_score": "2.500",
            "abs_score": "2.500",
            "factor_values": {"appointment_effect": "1.0"},
            "factor_choices": [
                {
                    "factor_name": "appointment_effect",
                    "option_code": "valid",
                    "option_label": "有效信任",
                    "value_num": "1.0",
                }
            ],
            "passages": [
                {
                    "source_title": "史记",
                    "title": "卷八",
                    "locator": "高祖本纪",
                    "passage_code": "PAS-1",
                    "quote": "萧何主关中。",
                }
            ],
        },
        {
            "target_code": "TGT-I5B-LB",
            "emperor_name": "刘邦",
            "factor_judgment_id": 102,
            "binding_id": 202,
            "binding_code": "BND-102",
            "claim_id": 302,
            "claim_code": "CLM-302",
            "claim_summary": "刘邦疑韩信。",
            "claim_object_name": "韩信",
            "claim_direction": "negative",
            "predicate": "delegated_authority",
            "binding_direction": "negative",
            "object_role": "military_delegate",
            "object_id": 11,
            "target_object_id": 1002,
            "object_name": "韩信",
            "side": "negative",
            "judgment_side": "negative",
            "raw_score": "1.000",
            "abs_score": "1.000",
            "factor_values": {"appointment_effect": "1.0"},
            "factor_choices": [],
            "passages": [],
        },
    ]

    def fake_fetch_rows(_cur, sql, _params):
        if "target_rule_score_clusters" in sql:
            return cluster_rows
        if "claim_rule_binding_material_scores" in sql:
            return material_rows
        raise AssertionError(sql)

    monkeypatch.setattr(score_chain, "fetch_rows", fake_fetch_rows)

    payload = score_chain.fetch_score_chain(
        object(),
        item_code="I5B",
        rule_code="appointment_delegation",
        formula_code="evidence_cluster_signal_v3",
        scope="accepted-packs",
        emperors=["刘邦"],
        top_materials_per_target=1,
    )

    assert payload["ok"] is True
    assert payload["totals"]["material_scores"] == 2
    assert payload["formula_params"]["material_score_cap"] == "4.0"
    target = payload["targets"][0]
    assert target["positive_signal"] == "2.500"
    assert target["object_side_scores"]["positive"][0]["object_name"] == "萧何"
    assert target["object_side_scores"]["positive"][0]["material_count"] == 1
    assert len(target["top_materials"]) == 1
    assert target["top_materials"][0]["claim_summary_short"] == "刘邦委任萧何主持关中转输。"
    assert target["materials"][0]["factor_choices"][0]["option_label"] == "有效信任"


def test_score_chain_can_render_rule_scorer_dry_run_payload() -> None:
    payload = score_chain.build_score_chain_from_rule_scorer_payload(
        {
            "generated_by": "scripts/dev/retrieval_v2_rule_scorer.py",
            "item_code": "I5B",
            "rule_code": "appointment_delegation",
            "formula_code": "evidence_cluster_signal_v3",
            "write_db": False,
            "detailed_clusters": [
                {
                    "target_id": 1,
                    "target_code": "TGT-I5B-LS",
                    "emperor_name": "李世民",
                    "item_code": "I5B",
                    "rule_code": "appointment_delegation",
                    "formula_code": "evidence_cluster_signal_v3",
                    "positive_signal": "2.500",
                    "negative_signal": "1.000",
                    "action_counts": {"score": 2},
                    "calc_detail": {
                        "formula_params": {"material_score_cap": "4.0"},
                        "object_side_scores": {
                            "positive": {"10": {"object_name": "房玄龄", "score": "2.500"}},
                            "negative": {"11": {"object_name": "萧瑀", "score": "1.000"}},
                        },
                        "materials": [
                            {
                                "factor_judgment_id": 101,
                                "binding_code": "BND-101",
                                "claim_id": 301,
                                "object_id": 10,
                                "target_object_id": 1001,
                                "object_name": "房玄龄",
                                "side": "positive",
                                "judgment_side": "positive",
                                "raw_score": "2.500",
                                "abs_score": "2.500",
                                "factor_refs": {
                                    "appointment_effect": {
                                        "option_code": "strong_success",
                                        "label": "强成功",
                                        "value_num": "1.5",
                                    }
                                },
                            },
                            {
                                "factor_judgment_id": 102,
                                "binding_code": "BND-102",
                                "claim_id": 302,
                                "object_id": 11,
                                "target_object_id": 1002,
                                "object_name": "萧瑀",
                                "side": "negative",
                                "judgment_side": "negative",
                                "raw_score": "-1.000",
                                "abs_score": "1.000",
                                "factor_refs": {},
                            },
                        ],
                    },
                }
            ],
        },
        emperors=["李世民"],
        top_materials_per_target=1,
    )

    assert payload["ok"] is True
    assert payload["source"]["kind"] == "rule_scorer_json"
    assert payload["source"]["write_db"] is False
    assert payload["totals"]["material_scores"] == 2
    target = payload["targets"][0]
    assert target["object_side_scores"]["positive"][0]["object_name"] == "房玄龄"
    assert target["object_side_scores"]["negative"][0]["object_name"] == "萧瑀"
    assert target["top_materials"][0]["factor_choices"][0]["option_label"] == "强成功"


def test_enrich_score_chain_claim_details_fills_claim_and_passages(monkeypatch) -> None:
    payload = {
        "source": {"kind": "rule_scorer_json", "write_db": False},
        "targets": [
            {
                "target_code": "TGT-I5B-LS",
                "materials": [{"claim_id": 301, "claim_summary": "", "passages": []}],
                "top_materials": [{"claim_id": 301, "claim_summary": "", "passages": []}],
            }
        ],
    }

    def fake_fetch_rows(_cur, sql, params):
        assert "material_claims" in sql
        assert params == ([301],)
        return [
            {
                "claim_id": 301,
                "claim_code": "CLM-301",
                "claim_summary": "李世民任用房玄龄。",
                "claim_object_name": "房玄龄",
                "claim_direction": "positive",
                "passages": [{"source_title": "旧唐书", "title": "房玄龄传", "locator": "卷", "passage_code": "PAS-1", "quote": "太宗任之。"}],
            }
        ]

    monkeypatch.setattr(score_chain, "fetch_rows", fake_fetch_rows)

    enriched = score_chain.enrich_score_chain_claim_details(object(), payload)

    material = enriched["targets"][0]["materials"][0]
    assert material["claim_summary"] == "李世民任用房玄龄。"
    assert material["passages"][0]["source_title"] == "旧唐书"
    assert enriched["source"]["claim_details_enriched"] is True


def test_input_rule_scorer_enrichment_keeps_native_claim_schema(monkeypatch, tmp_path: Path) -> None:
    input_path = tmp_path / "rule_scorer.json"
    input_path.write_text(
        json.dumps(
            {
                "generated_by": "scripts/dev/retrieval_v2_rule_scorer.py",
                "write_db": True,
                "item_code": "I5B",
                "rule_code": "appointment_delegation",
                "formula_code": "appointment_delegation_v1",
                "detailed_clusters": [],
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "score_chain.json"
    raw_cursor = object()

    class CursorContext:
        def __enter__(self):
            return raw_cursor

        def __exit__(self, *_args):
            return None

    class ConnectionContext:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def cursor(self):
            return CursorContext()

    class Psycopg:
        @staticmethod
        def connect(*_args, **_kwargs):
            return ConnectionContext()

    monkeypatch.setattr(cli, "load_env_file", lambda _path: None)
    monkeypatch.setattr(cli, "resolve_dsn", lambda _name: "dsn")
    monkeypatch.setattr(cli, "import_psycopg", lambda: (Psycopg, object()))
    monkeypatch.setattr(
        cli,
        "enrich_score_chain_claim_details",
        lambda cursor, payload: {**payload, "native_cursor": cursor is raw_cursor},
    )

    assert cli.main(
        [
            "score-chain",
            "--env-file",
            str(tmp_path / ".env"),
            "--input-rule-scorer-json",
            str(input_path),
            "--output-json",
            str(output_path),
        ]
    ) == 0
    assert json.loads(output_path.read_text(encoding="utf-8"))["native_cursor"] is True


def test_score_chain_filter_values_accepts_multiple_emperors_and_targets() -> None:
    target_codes, emperors = selectors.score_chain_filter_values(
        target_code="TGT-I5B-LB",
        target_codes=["TGT-I5B-YJ", "TGT-I5B-LB", ""],
        emperors=["刘邦", "杨坚", "刘邦"],
    )

    assert target_codes == ["TGT-I5B-LB", "TGT-I5B-YJ"]
    assert emperors == ["刘邦", "杨坚"]


def test_build_score_chain_selectors_accepts_generic_person_emperor_names() -> None:
    payload = selectors.build_score_chain_selectors(
        selector_type="person",
        selector_role="emperor",
        names=["刘邦", "杨坚", "刘邦"],
    )

    assert payload["target_codes"] == []
    assert payload["emperors"] == ["刘邦", "杨坚"]
    assert payload["selectors"] == [
        {
            "type": "person",
            "role": "emperor",
            "names": ["刘邦", "杨坚"],
            "source": "--type/--role/--name",
        }
    ]


def test_build_score_chain_observations_flags_duplicate_claim_object_side() -> None:
    observations = score_chain.build_score_chain_observations(
        [
            {
                "target_code": "TGT-I5B-X",
                "emperor_name": "玄烨",
                "positive_signal": "3.000",
                "negative_signal": "3.500",
                "materials": [
                    {
                        "claim_id": 1,
                        "object_id": 10,
                        "object_name": "施琅",
                        "side": "positive",
                        "judgment_side": "negative",
                        "binding_code": "BND-1",
                        "raw_score": "4.500",
                        "abs_score": "4.000",
                        "claim_summary": "康熙任施琅负责进取台湾。",
                    },
                    {
                        "claim_id": 1,
                        "object_id": 10,
                        "object_name": "施琅",
                        "side": "positive",
                        "binding_code": "BND-2",
                        "raw_score": "3.000",
                        "abs_score": "3.000",
                        "claim_summary": "康熙任施琅负责进取台湾。",
                    },
                ],
            }
        ]
    )

    by_code = {row["code"]: row for row in observations}
    assert by_code["score_chain_duplicate_claim_object_side"]["count"] == 1
    assert by_code["score_chain_duplicate_claim_object_side"]["examples"][0]["binding_codes"] == ["BND-1", "BND-2"]
    assert by_code["score_chain_negative_ge_positive"]["count"] == 1
    assert by_code["score_chain_material_score_capped"]["count"] == 1
    assert by_code["score_chain_judgment_side_score_side_mismatch"]["count"] == 1
    assert by_code["score_chain_judgment_side_score_side_mismatch"]["examples"][0]["judgment_side"] == "negative"


def test_main_score_chain_writes_json_and_markdown(tmp_path: Path, monkeypatch, capsys) -> None:
    output_json = tmp_path / "score_chain.json"
    output_md = tmp_path / "score_chain.md"
    fake_payload = {
        "generated_by": "scripts/dev/retrieval_v2_diagnostics.py",
        "command": "score-chain",
        "ok": True,
        "scope": {
            "item_code": "I5B",
            "rule_code": "appointment_delegation",
            "formula_code": "evidence_cluster_signal_v3",
            "scope": "accepted-packs",
            "target_code": "",
            "target_codes": [],
            "emperors": ["刘邦", "杨坚"],
            "selectors": [
                {
                    "type": "person",
                    "role": "emperor",
                    "names": ["刘邦", "杨坚"],
                    "source": "--type/--role/--name",
                }
            ],
        },
        "render_options": {"top_materials_per_target": 1},
        "formula_params": {"material_score_cap": "4.0", "same_object_secondary_factor": "0.35"},
        "totals": {"targets": 1, "material_scores": 1},
        "targets": [
            {
                "target_code": "TGT-I5B-LB",
                "emperor_name": "刘邦",
                "positive_signal": "2.500",
                "negative_signal": "0.000",
                "scored_judgment_count": 1,
                "supporting_judgment_count": 0,
                "excluded_judgment_count": 0,
                "materials": [{"abs_score": "2.500"}],
                "object_side_scores": {"positive": [{"object_name": "萧何", "score": "2.500", "material_count": 1}], "negative": []},
                "top_materials": [
                    {
                        "side": "positive",
                        "object_name": "萧何",
                        "abs_score": "2.500",
                        "raw_score": "2.500",
                        "factor_choices": [
                            {
                                "factor_name": "appointment_effect",
                                "option_label": "有效信任",
                                "value_num": "1.0",
                            }
                        ],
                        "claim_summary": "刘邦委任萧何主持关中转输。",
                    }
                ],
            }
        ],
    }

    def fake_fetch_db_report(**kwargs):
        assert kwargs["command"] == "score-chain"
        assert kwargs["target_code"] == ""
        assert kwargs["target_codes"] == []
        assert kwargs["emperors"] == []
        assert kwargs["selector_type"] == "person"
        assert kwargs["selector_role"] == "emperor"
        assert kwargs["names"] == ["刘邦", "杨坚"]
        assert kwargs["top_materials_per_target"] == 1
        return fake_payload

    monkeypatch.setattr(cli, "fetch_db_report", fake_fetch_db_report)

    assert cli.main([
        "score-chain",
        "--env-file",
        ".env",
        "--item-code",
        "I5B",
        "--rule-code",
        "appointment_delegation",
        "--type",
        "person",
        "--role",
        "emperor",
        "--name",
        "刘邦",
        "--name",
        "杨坚",
        "--top-materials-per-target",
        "1",
        "--output-json",
        str(output_json),
        "--output-md",
        str(output_md),
    ]) == 0

    assert json.loads(output_json.read_text(encoding="utf-8"))["command"] == "score-chain"
    md = output_md.read_text(encoding="utf-8")
    assert "# retrieval_v2 score chain" in md
    assert "萧何" in md
    assert "有效信任" in md
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_main_score_chain_can_render_rule_scorer_json(tmp_path: Path, capsys) -> None:
    input_json = tmp_path / "rule_scorer.json"
    output_json = tmp_path / "score_chain.json"
    output_md = tmp_path / "score_chain.md"
    input_json.write_text(
        json.dumps(
            {
                "generated_by": "scripts/dev/retrieval_v2_rule_scorer.py",
                "item_code": "I5B",
                "rule_code": "appointment_delegation",
                "formula_code": "evidence_cluster_signal_v3",
                "write_db": False,
                "detailed_clusters": [
                    {
                        "target_id": 1,
                        "target_code": "TGT-I5B-LS",
                        "emperor_name": "李世民",
                        "item_code": "I5B",
                        "rule_code": "appointment_delegation",
                        "formula_code": "evidence_cluster_signal_v3",
                        "positive_signal": "2.500",
                        "negative_signal": "0.000",
                        "action_counts": {"score": 1},
                        "calc_detail": {
                            "formula_params": {"material_score_cap": "4.0"},
                            "object_side_scores": {
                                "positive": {"10": {"object_name": "房玄龄", "score": "2.500"}},
                                "negative": {},
                            },
                            "materials": [
                                {
                                    "factor_judgment_id": 101,
                                    "binding_code": "BND-101",
                                    "claim_id": 301,
                                    "object_id": 10,
                                    "object_name": "房玄龄",
                                    "side": "positive",
                                    "judgment_side": "positive",
                                    "raw_score": "2.500",
                                    "abs_score": "2.500",
                                    "factor_refs": {
                                        "appointment_effect": {
                                            "option_code": "strong_success",
                                            "label": "强成功",
                                            "value_num": "1.5",
                                        }
                                    },
                                }
                            ],
                        },
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert cli.main(
        [
            "score-chain",
            "--input-rule-scorer-json",
            str(input_json),
            "--emperor",
            "李世民",
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
        ]
    ) == 0

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["source"]["path"] == str(input_json)
    assert payload["totals"]["material_scores"] == 1
    md = output_md.read_text(encoding="utf-8")
    assert "source: `rule_scorer_json`" in md
    assert "房玄龄" in md
    assert "强成功" in md
    assert json.loads(capsys.readouterr().out)["ok"] is True
