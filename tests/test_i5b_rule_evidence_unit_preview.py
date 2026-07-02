from __future__ import annotations

import json

from scripts.dev import i5b_rule_evidence_unit_preview as tool


def valid_wuzetian_payload() -> dict[str, object]:
    return {
        "emperor": "武则天",
        "item_code": "I5B",
        "units": [
            {
                "rule_code": "anti_nepotism",
                "causal_chain_key": "wuzetian-zhang-brothers-favoritism",
                "direction": "negative",
                "scoring_role": "favorite_beneficiary",
                "scored_obj": {
                    "name": "张易之",
                    "obj_type": "person",
                    "obj_src_id": 1631,
                },
                "members": [
                    {
                        "role": "actor_context",
                        "name": "张昌宗",
                        "obj_type": "person",
                        "obj_src_id": 1632,
                    }
                ],
            },
            {
                "rule_code": "tolerate_talent",
                "causal_chain_key": "wuzetian-cruel-officials-false-accusation",
                "direction": "negative",
                "scoring_role": "harmed_talent",
                "scored_obj": {
                    "name": "黑齿常之",
                    "obj_type": "person",
                    "obj_src_id": 1629,
                },
                "members": [
                    {
                        "role": "mechanism_context",
                        "name": "酷吏罗织机制",
                        "obj_type": "mechanism",
                        "obj_src_id": 966,
                    },
                    {
                        "role": "group_context",
                        "name": "被诬陷牵连官员",
                        "obj_type": "group",
                        "obj_src_id": 968,
                    },
                ],
            },
        ],
    }


def test_preview_accepts_rule_bearing_object_with_context_members() -> None:
    preview = tool.build_preview(valid_wuzetian_payload())

    assert preview["issue_count"] == 0
    markdown = tool.render_markdown(preview)
    assert "张易之" in markdown
    assert "黑齿常之" in markdown
    assert "酷吏罗织机制" in markdown


def test_preview_flags_mechanism_as_wrong_anti_nepotism_carrier() -> None:
    payload = valid_wuzetian_payload()
    payload["units"] = [
        {
            "rule_code": "anti_nepotism",
            "causal_chain_key": "wuzetian-cruel-officials",
            "direction": "negative",
            "scoring_role": "mechanism_context",
            "scored_obj": {
                "name": "酷吏罗织机制",
                "obj_type": "mechanism",
                "obj_src_id": 967,
            },
        }
    ]

    issues = tool.audit_payload(payload)
    codes = {issue.code for issue in issues}

    assert "context_role_used_as_scoring_role" in codes
    assert "scored_obj_type_disallowed" in codes


def test_preview_warns_when_same_tolerate_talent_chain_scores_twice() -> None:
    payload = valid_wuzetian_payload()
    payload["units"] = [
        {
            "rule_code": "tolerate_talent",
            "causal_chain_key": "wuzetian-cruel-officials-false-accusation",
            "direction": "negative",
            "scoring_role": "group_context",
            "scored_obj": {
                "name": "被诬陷牵连官员",
                "obj_type": "group",
                "obj_src_id": 968,
            },
        },
        {
            "rule_code": "tolerate_talent",
            "causal_chain_key": "wuzetian-cruel-officials-false-accusation",
            "direction": "negative",
            "scoring_role": "harmed_talent",
            "scored_obj": {
                "name": "黑齿常之",
                "obj_type": "person",
                "obj_src_id": 1630,
            },
        },
    ]

    issues = tool.audit_payload(payload)

    codes = {issue.code for issue in issues}
    assert "context_role_used_as_scoring_role" in codes
    assert "scored_obj_type_disallowed" in codes


def test_cli_outputs_json_and_can_fail_on_issue(tmp_path) -> None:
    payload_path = tmp_path / "units.json"
    payload = valid_wuzetian_payload()
    payload["units"] = [
        {
            "rule_code": "tolerate_talent",
            "causal_chain_key": "wuzetian-cruel-officials-group",
            "direction": "negative",
            "scoring_role": "group_context",
            "scored_obj": {
                "name": "被诬陷牵连官员",
                "obj_type": "group",
                "obj_src_id": 968,
            },
        },
        {
            "rule_code": "tolerate_talent",
            "causal_chain_key": "wuzetian-cruel-officials-event",
            "direction": "negative",
            "scoring_role": "group_context",
            "scored_obj": {
                "name": "同一材料重复承载",
                "obj_type": "group",
                "obj_src_id": 968,
            },
        },
    ]
    payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    output_path = tmp_path / "preview.json"

    exit_code = tool.main(
        [
            "--input",
            str(payload_path),
            "--output",
            str(output_path),
            "--format",
            "json",
            "--fail-on-issue",
        ]
    )

    assert exit_code == 1
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["issue_count"] >= 1
    assert any(issue["code"] == "same_material_scored_multiple_times" for issue in report["issues"])
