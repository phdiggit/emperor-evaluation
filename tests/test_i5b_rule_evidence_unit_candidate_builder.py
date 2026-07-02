from __future__ import annotations

from scripts.dev import i5b_rule_evidence_unit_candidate_builder as builder


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
    )

    assert payload["emperor"] == "武则天"
    assert payload["item_code"] == "I5B"
    assert payload["units"] == []
    assert payload["preview"]["issue_count"] == 1
    assert payload["preview"]["issues"][0]["code"] == "missing_units"
