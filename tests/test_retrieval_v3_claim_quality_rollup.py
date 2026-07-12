from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v3_claim_quality_rollup as tool


def write_audit(path: Path, *, claims: int, evidence: int, issues: dict[str, int]) -> None:
    path.write_text(
        json.dumps(
            {
                "totals": {"active_claims": claims, "active_evidence": evidence, "findings": sum(issues.values())},
                "issue_counts": issues,
                "claim_opportunity_estimate": {
                    "totals": {
                        "suggested_claim_budget": claims,
                        "actual_claim_count": claims,
                        "undercoverage_objects": 0,
                    }
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def test_rollup_aggregates_samples_and_policy_decisions(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    write_audit(first, claims=10, evidence=20, issues={})
    write_audit(second, claims=5, evidence=8, issues={"action_type_authorization_anchor_missing": 2})

    payload = tool.build_rollup([("first", first), ("second", second)])

    assert payload["totals"]["sample_count"] == 2
    assert payload["totals"]["claims"] == 15
    assert payload["totals"]["evidence"] == 28
    assert payload["aggregate_issue_counts"] == {"action_type_authorization_anchor_missing": 2}
    decisions = {row["policy_code"]: row["decision"] for row in payload["policy_decisions"]}
    assert decisions["evidence_object_integrity_gate"] == "keep_hard_gate"
    assert decisions["near_duplicate_claim_group"] == "audit_only"
    assert decisions["action_type_authorization_anchor_missing"] == "review_only"


def test_cli_writes_json_and_markdown(tmp_path: Path, capsys) -> None:
    audit = tmp_path / "audit.json"
    write_audit(audit, claims=3, evidence=4, issues={"near_duplicate_claim_group": 1})
    out_json = tmp_path / "rollup.json"
    out_md = tmp_path / "rollup.md"

    assert tool.main([
        "--audit",
        f"pilot={audit}",
        "--output-json",
        str(out_json),
        "--output-md",
        str(out_md),
    ]) == 0

    assert json.loads(out_json.read_text(encoding="utf-8"))["samples"][0]["label"] == "pilot"
    assert "candidate_auto_canonicalize_after_manual_review" in out_md.read_text(encoding="utf-8")
    assert json.loads(capsys.readouterr().out)["ok"] is True
