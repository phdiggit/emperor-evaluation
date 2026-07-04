from __future__ import annotations

import json

from scripts.dev import i5b_rule_evidence_unit_issue_summary as tool
from scripts.dev.rule_material_policy import policy_map_from_rows


def _payload_with_issue() -> dict[str, object]:
    return {
        "emperor": "武则天",
        "item_code": "I5B",
        "preview": {
            "emperor": "武则天",
            "unit_count": 2,
            "issues": [
                {
                    "severity": "block",
                    "code": "scored_obj_type_disallowed",
                    "rule_code": "anti_nepotism",
                    "causal_chain_key": "i5b:anti_nepotism:obj_src:966",
                    "object_name": "酷吏罗织机制",
                    "message": "该对象类型默认不能作为本 rule 的计分承载对象",
                }
            ],
        },
    }


def test_build_issue_summary_counts_blocks_and_warnings() -> None:
    clean_payload = {
        "emperor": "李世民",
        "item_code": "I5B",
        "preview": {"emperor": "李世民", "unit_count": 3, "issues": []},
    }

    summary = tool.build_issue_summary([_payload_with_issue(), clean_payload])

    assert summary["totals"]["emperors"] == 2
    assert summary["totals"]["units"] == 5
    assert summary["totals"]["issues"] == 1
    assert summary["totals"]["blocks"] == 1
    text = tool.render_markdown(summary)
    assert "酷吏罗织机制" in text
    assert "| 李世民 | 3 | 0 | 0 | 0 |" in text


def test_build_issue_summary_rebuilds_stale_preview_when_policies_are_provided() -> None:
    payload = {
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
            }
        ],
        "preview": {
            "emperor": "武则天",
            "unit_count": 1,
            "issues": [
                {
                    "severity": "block",
                    "code": "missing_rule_material_policy",
                    "rule_code": "anti_nepotism",
                    "causal_chain_key": "wuzetian-zhang-brothers-favoritism",
                    "object_name": "张易之",
                    "message": "旧 preview 不能覆盖当前 policy 审计",
                }
            ],
        },
    }
    policies = policy_map_from_rows(
        [
            {
                "item_code": "I5B",
                "rule_code": "anti_nepotism",
                "policy_code": "person_material_policy",
                "allowed_scoring_roles": ["favorite_beneficiary"],
                "context_roles": ["source_context"],
                "disallowed_scored_obj_types": ["event", "group", "mechanism"],
            }
        ]
    )

    summary = tool.build_issue_summary([payload], policies=policies)

    assert summary["totals"]["issues"] == 0
    assert summary["rows"][0]["unit_count"] == 1


def test_cli_can_fail_on_issue(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(tool, "resolve_dsn", lambda _env: "postgresql://example")
    monkeypatch.setattr(tool, "fetch_emperors_with_calc_details", lambda **_kwargs: ("武则天",))
    monkeypatch.setattr(tool, "build_payloads", lambda **_kwargs: [_payload_with_issue()])
    monkeypatch.setattr(tool, "fetch_policy_map_from_dsn", lambda **_kwargs: {})
    output = tmp_path / "summary.json"

    exit_code = tool.main(["--all-emperors", "--format", "json", "--output", str(output), "--fail-on-issue"])

    assert exit_code == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["totals"]["issues"] == 1
