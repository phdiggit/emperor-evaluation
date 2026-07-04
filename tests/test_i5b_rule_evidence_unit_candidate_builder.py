from __future__ import annotations

from scripts.dev import i5b_rule_evidence_unit_candidate_builder as builder
from scripts.dev.rule_material_policy import policy_map_from_rows


def policy_map() -> dict:
    return policy_map_from_rows(
        [
            {
                "item_code": "I5B",
                "rule_code": "anti_nepotism",
                "policy_code": "person_material_policy",
                "allowed_scoring_roles": [
                    "anti_nepotism_resisted_actor",
                    "nepotistic_beneficiary",
                    "favorite_beneficiary",
                    "appointment_interferer",
                ],
                "context_roles": ["actor_context", "event_context", "group_context", "mechanism_context", "source_context"],
                "disallowed_scored_obj_types": ["event", "group", "mechanism"],
                "policy_payload": {
                    "context_roles_by_obj_type": {
                        "mechanism": "mechanism_context",
                        "event": "event_context",
                        "group": "group_context",
                    },
                    "candidate_role_rules": [
                        {"when": {"side": "positive"}, "role": "anti_nepotism_resisted_actor"},
                        {"when": {"obj_type": "person", "name_prefixes": ["武"]}, "role": "nepotistic_beneficiary"},
                        {"when": {"obj_type": "person", "names": ["张易之", "张昌宗", "薛怀义"]}, "role": "favorite_beneficiary"},
                    ],
                    "default_scoring_roles_by_direction": {
                        "non_negative": "anti_nepotism_resisted_actor",
                        "negative": "appointment_interferer",
                    },
                },
            },
            {
                "item_code": "I5B",
                "rule_code": "tolerate_talent",
                "policy_code": "single_person_chain_policy",
                "allowed_scoring_roles": ["protected_talent", "remonstrance_actor", "expression_safety_unit", "harmed_talent"],
                "context_roles": ["actor_context", "event_context", "group_context", "mechanism_context", "source_context"],
                "disallowed_scored_obj_types": ["event", "group", "mechanism"],
                "single_scored_per_chain": True,
                "policy_payload": {
                    "context_roles_by_obj_type": {
                        "mechanism": "mechanism_context",
                        "event": "event_context",
                        "group": "group_context",
                    },
                    "candidate_role_rules": [
                        {"when": {"side": "positive", "obj_type": "person"}, "role": "protected_talent"},
                        {"when": {"side": "negative", "obj_type": "person"}, "role": "harmed_talent"},
                    ],
                },
            },
        ]
    )


def test_candidate_builder_marks_mechanism_as_review_needed_carrier() -> None:
    cluster_rows = {
        ("武则天", "anti_nepotism"): {
            "calc_detail": {
                "materials": [
                    {
                        "obj_src_id": 967,
                        "obj_name": "酷吏罗织机制",
                        "obj_key": "488",
                        "side": "negative",
                        "raw_score": "3.672",
                        "abs_score": "3.672",
                    }
                ]
            }
        }
    }
    materials_report = {
        "rules": {
            "anti_nepotism": [
                {
                    "obj_src_id": 967,
                    "obj_id": 488,
                    "emp_obj_id": 700,
                    "obj_name": "酷吏罗织机制",
                    "obj_type": "mechanism",
                    "direction": "negative",
                }
            ]
        }
    }

    payload = builder.build_candidate_payload(
        emperor="武则天",
        cluster_rows=cluster_rows,
        materials_report=materials_report,
        policies=policy_map(),
    )

    unit = payload["units"][0]
    assert unit["scoring_role"] == "mechanism_context"
    assert unit["review_status"] == "needs_review"
    assert unit["review_note"] == ""
    assert payload["preview"]["has_blocking_issue"] is True
    codes = {issue["code"] for issue in payload["preview"]["issues"]}
    assert "context_role_used_as_scoring_role" in codes
    assert "scored_obj_type_disallowed" in codes


def test_candidate_builder_classifies_positive_anti_nepotism_as_resisted_actor() -> None:
    cluster_rows = {
        ("李世民", "anti_nepotism"): {
            "calc_detail": {
                "materials": [
                    {
                        "obj_src_id": 139,
                        "obj_name": "魏徵",
                        "obj_key": "501",
                        "side": "positive",
                    }
                ]
            }
        }
    }
    materials_report = {
        "rules": {
            "anti_nepotism": [
                {
                    "obj_src_id": 139,
                    "obj_id": 501,
                    "emp_obj_id": 601,
                    "obj_name": "魏徵",
                    "obj_type": "person",
                    "direction": "positive",
                }
            ]
        }
    }

    payload = builder.build_candidate_payload(
        emperor="李世民",
        cluster_rows=cluster_rows,
        materials_report=materials_report,
        policies=policy_map(),
    )

    assert payload["units"][0]["scoring_role"] == "anti_nepotism_resisted_actor"
    assert payload["preview"]["has_blocking_issue"] is False


def test_candidate_builder_classifies_tolerate_talent_carriers_and_supporting_member() -> None:
    cluster_rows = {
        ("武则天", "tolerate_talent"): {
            "calc_detail": {
                "materials": [
                    {
                        "obj_src_id": 968,
                        "obj_name": "被诬陷牵连官员",
                        "obj_key": "489",
                        "side": "negative",
                    },
                    {
                        "obj_src_id": 1629,
                        "obj_name": "黑齿常之",
                        "obj_key": "777",
                        "side": "negative",
                    },
                ],
                "supporting_material_ids": [1630],
            }
        }
    }
    materials_report = {
        "rules": {
            "tolerate_talent": [
                {
                    "obj_src_id": 968,
                    "obj_id": 489,
                    "emp_obj_id": 701,
                    "obj_name": "被诬陷牵连官员",
                    "obj_type": "group",
                    "direction": "negative",
                },
                {
                    "obj_src_id": 1629,
                    "obj_id": 777,
                    "emp_obj_id": 702,
                    "obj_name": "黑齿常之",
                    "obj_type": "person",
                    "direction": "negative",
                },
                {
                    "obj_src_id": 1630,
                    "obj_id": 777,
                    "emp_obj_id": 702,
                    "obj_name": "黑齿常之",
                    "obj_type": "person",
                    "direction": "neutral",
                },
            ]
        }
    }

    payload = builder.build_candidate_payload(
        emperor="武则天",
        cluster_rows=cluster_rows,
        materials_report=materials_report,
        policies=policy_map(),
    )

    by_name = {unit["scored_obj"]["name"]: unit for unit in payload["units"]}
    assert by_name["被诬陷牵连官员"]["scoring_role"] == "group_context"
    assert by_name["黑齿常之"]["scoring_role"] == "harmed_talent"
    assert by_name["黑齿常之"]["members"][0]["obj_src_id"] == 1630
    assert payload["preview"]["has_blocking_issue"] is True
    codes = {issue["code"] for issue in payload["preview"]["issues"]}
    assert "context_role_used_as_scoring_role" in codes
    assert "scored_obj_type_disallowed" in codes


def test_candidate_builder_outputs_preview_compatible_json() -> None:
    payload = builder.build_candidate_payload(
        emperor="武则天",
        cluster_rows={},
        materials_report={"rules": {}},
        policies=policy_map(),
    )

    assert payload["emperor"] == "武则天"
    assert payload["item_code"] == "I5B"
    assert payload["units"] == []
    assert payload["preview"]["issue_count"] == 1
    assert payload["preview"]["issues"][0]["code"] == "missing_units"


def test_candidate_builder_declares_rules_with_only_supporting_materials() -> None:
    payload = builder.build_candidate_payload(
        emperor="刘询",
        cluster_rows={
            ("刘询", "anti_nepotism"): {
                "calc_detail": {
                    "materials": [],
                    "supporting_material_ids": [2376],
                    "no_score_reason": "no_scored_materials",
                }
            }
        },
        materials_report={
            "rules": {
                "anti_nepotism": [
                    {
                        "obj_src_id": 2376,
                        "obj_id": 9001,
                        "obj_name": "霍氏处置边界",
                        "obj_type": "case",
                        "direction": "negative",
                    }
                ]
            }
        },
        policies=policy_map(),
    )

    assert payload["rule_codes"] == ["anti_nepotism"]
    assert payload["units"] == []
    assert payload["supporting_materials"][0]["obj_src_id"] == 2376
