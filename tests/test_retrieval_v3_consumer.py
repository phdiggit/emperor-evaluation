from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v3_consumer as tool


def object_report(*, blockers: list[dict] | None = None) -> dict:
    return {
        "ok": not blockers,
        "totals": {
            "queue_rows": 2,
            "auto_accepted_objects": 2,
        },
        "blockers": blockers or [],
    }


def profile_report(*, missing: int = 1, conflicting: int = 0, unsupported: int = 0) -> dict:
    return {
        "ok": True,
        "totals": {
            "profile_rows": 2,
            "matched_old_talent_quality": 1,
            "missing_old_talent_quality": missing,
            "conflicting_old_talent_quality": conflicting,
            "unsupported_old_talent_quality": unsupported,
        },
        "review_needed": [
            {
                "object_id": 10,
                "canonical_name": "傅友德",
                "normalized_name": "傅友德",
                "match_status": "missing_old_talent_quality",
            }
        ]
        if missing
        else [],
    }


def context_report(*, missing_role: int = 1, missing_target_period: int = 0) -> dict:
    return {
        "ok": True,
        "totals": {
            "affiliation_rows": 3,
            "role_rows": 2,
            "missing_role_candidate": missing_role,
            "missing_target_period": missing_target_period,
        },
        "review_needed": {
            "missing_role_candidate": [
                {
                    "object_id": 10,
                    "canonical_name": "傅友德",
                    "target_code": "TGT-I5B-MING",
                    "material_roles": {"revoked_or_failed_delegate": 1},
                }
            ]
            if missing_role
            else [],
            "missing_target_period": [],
        },
    }


def target_report(*, missing_period: int = 0) -> dict:
    return {
        "ok": True,
        "totals": {
            "profile_rows": 2,
            "emperor_role_rows": 2,
            "missing_emperor_period": missing_period,
        },
        "review_needed": {
            "missing_emperor_period": [
                {
                    "target_id": 1,
                    "target_code": "TGT-I5B-LH",
                    "emperor_name": "刘恒",
                    "item_code": "I5B",
                }
            ]
            if missing_period
            else []
        },
    }


def test_completion_stage_delegates_to_existing_consumers(monkeypatch) -> None:
    calls: list[tuple[str, bool]] = []

    def fake_target_consumer(**kwargs):
        calls.append(("targets", kwargs["execute"]))
        return target_report()

    def fake_object_consumer(**kwargs):
        calls.append(("objects", kwargs["execute"]))
        return object_report()

    def fake_profile_consumer(**kwargs):
        calls.append(("profiles", kwargs["execute"]))
        return profile_report()

    def fake_context_consumer(**kwargs):
        calls.append(("context", kwargs["execute"]))
        return context_report()

    monkeypatch.setattr(tool.target_person_consumer, "execute_target_person_consumer", fake_target_consumer)
    monkeypatch.setattr(tool.object_consumer, "execute_object_consumer", fake_object_consumer)
    monkeypatch.setattr(tool.profile_consumer, "execute_person_profile_consumer", fake_profile_consumer)
    monkeypatch.setattr(tool.context_consumer, "execute_person_context_consumer", fake_context_consumer)

    payload = tool.execute_completion_stage(env_file=None, dsn_env="NEW_DSN", reference_dsn_env="REFERENCE_DSN", execute=False)

    assert calls == [("targets", False), ("objects", False), ("profiles", False), ("context", False)]
    assert payload["stage"] == "completion"
    assert payload["write_db"] is False
    assert payload["ok"] is True
    assert payload["totals"]["target_emperor_profiles"] == 2
    assert payload["totals"]["missing_old_talent_quality"] == 1
    assert payload["worklists"]["agent_tasks"][0]["code"] == "missing_talent_grade"
    assert payload["components"]["person_context"]["totals"]["role_rows"] == 2


def test_completion_stage_surfaces_identity_and_talent_blockers(monkeypatch) -> None:
    monkeypatch.setattr(tool.target_person_consumer, "execute_target_person_consumer", lambda **_: target_report())
    monkeypatch.setattr(tool.object_consumer, "execute_object_consumer", lambda **_: object_report(blockers=[{"code": "mixed_object_types"}]))
    monkeypatch.setattr(tool.profile_consumer, "execute_person_profile_consumer", lambda **_: profile_report(missing=0, conflicting=1))
    monkeypatch.setattr(tool.context_consumer, "execute_person_context_consumer", lambda **_: context_report(missing_role=0))

    payload = tool.execute_completion_stage(env_file=None, dsn_env="NEW_DSN", reference_dsn_env="REFERENCE_DSN", execute=True)

    assert payload["ok"] is False
    assert [item["code"] for item in payload["worklists"]["blockers"]] == [
        "ambiguous_identity",
        "conflicting_old_talent_grade",
    ]


def test_classify_readiness_escalates_talent_gap_for_talent_rules() -> None:
    snapshot = {
        "person_objects": 5,
        "missing_person_profiles": 0,
        "missing_talent_grade": 2,
        "needs_review_profiles": 2,
        "duplicate_profiles": 0,
        "missing_person_roles": 5,
        "missing_person_affiliations": 5,
        "missing_script_variants": 0,
        "target_emperors": 2,
        "missing_target_emperor_objects": 0,
        "missing_target_emperor_profiles": 0,
        "missing_target_emperor_roles": 0,
        "missing_target_emperor_affiliations": 0,
        "material_review_pending": 0,
    }

    delegation = tool.classify_readiness(snapshot, rule_code="delegation")
    team_building = tool.classify_readiness(snapshot, rule_code="team_building")

    assert delegation["ok"] is True
    assert [item["code"] for item in delegation["warnings"]] == [
        "missing_talent_grade",
        "missing_person_role",
        "missing_person_affiliation",
    ]
    assert team_building["ok"] is False
    assert team_building["blockers"][0]["code"] == "missing_talent_grade"


def test_classify_readiness_blocks_missing_target_emperor_profile() -> None:
    snapshot = {
        "person_objects": 0,
        "missing_person_profiles": 0,
        "missing_talent_grade": 0,
        "needs_review_profiles": 0,
        "duplicate_profiles": 0,
        "missing_person_roles": 0,
        "missing_person_affiliations": 0,
        "missing_script_variants": 0,
        "target_emperors": 2,
        "missing_target_emperor_objects": 1,
        "missing_target_emperor_profiles": 0,
        "missing_target_emperor_roles": 0,
        "missing_target_emperor_affiliations": 0,
        "material_review_pending": 0,
    }

    payload = tool.classify_readiness(snapshot, rule_code="delegation")

    assert payload["ok"] is False
    assert payload["blockers"][0]["code"] == "missing_target_emperor_profile"


def test_classify_readiness_blocks_pending_material_review() -> None:
    snapshot = {
        "person_objects": 2,
        "missing_person_profiles": 0,
        "missing_talent_grade": 0,
        "needs_review_profiles": 0,
        "duplicate_profiles": 0,
        "missing_person_roles": 0,
        "missing_person_affiliations": 0,
        "missing_script_variants": 0,
        "target_emperors": 1,
        "missing_target_emperor_objects": 0,
        "missing_target_emperor_profiles": 0,
        "missing_target_emperor_roles": 0,
        "missing_target_emperor_affiliations": 0,
        "material_review_pending": 1,
    }

    payload = tool.classify_readiness(snapshot, rule_code="delegation")

    assert payload["ok"] is False
    assert payload["blockers"][0]["code"] == "material_review_pending"


def test_classify_readiness_reports_downstream_factorization_and_rule_score_counts() -> None:
    snapshot = {
        "person_objects": 2,
        "missing_person_profiles": 0,
        "missing_talent_grade": 0,
        "needs_review_profiles": 0,
        "duplicate_profiles": 0,
        "missing_person_roles": 0,
        "missing_person_affiliations": 0,
        "missing_script_variants": 0,
        "target_emperors": 1,
        "missing_target_emperor_objects": 0,
        "missing_target_emperor_profiles": 0,
        "missing_target_emperor_roles": 0,
        "missing_target_emperor_affiliations": 0,
        "material_review_pending": 0,
        "factorization_required": 3,
        "rule_score_required": 2,
    }

    payload = tool.classify_readiness(snapshot, rule_code="delegation")

    downstream = {item["code"]: item["count"] for item in payload["downstream_required"]}
    assert downstream["factorization_required"] == 3
    assert downstream["rule_score_required"] == 2


def test_target_scope_cte_supports_accepted_packs() -> None:
    accepted = tool.target_scope_cte("accepted-packs")
    active = tool.target_scope_cte("active-targets")

    assert "retrieval_v3.source_packs" in accepted
    assert "distinct on (sp2.target_id, sp2.contract_id)" in accepted
    assert "sp2.status = 'accepted'" in accepted
    assert "sp2.coverage_status = 'passed'" in accepted
    assert "rt.target_status = 'active'" not in accepted
    assert "rt.target_status = 'active'" in active


def test_cli_readiness_passes_scope(tmp_path: Path, monkeypatch, capsys) -> None:
    calls: list[str] = []

    def fake_readiness(**kwargs):
        calls.append(kwargs["scope"])
        return {
            "generated_by": "test",
            "command": "readiness",
            "ok": True,
            "scope": kwargs["scope"],
            "snapshot": {"person_objects": 0},
            "blockers": [],
            "warnings": [],
            "agent_tasks": [],
        }

    monkeypatch.setattr(tool, "fetch_readiness_report", fake_readiness)
    output_json = tmp_path / "readiness.json"
    output_md = tmp_path / "readiness.md"

    assert tool.main([
        "readiness",
        "--scope",
        "accepted-packs",
        "--output-json",
        str(output_json),
        "--output-md",
        str(output_md),
    ]) == 0

    assert calls == ["accepted-packs"]
    assert json.loads(output_json.read_text(encoding="utf-8"))["scope"] == "accepted-packs"
    assert "- scope: `accepted-packs`" in output_md.read_text(encoding="utf-8")
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_cli_apply_writes_json_and_markdown(tmp_path: Path, monkeypatch, capsys) -> None:
    payload = {
        "generated_by": "test",
        "command": "apply",
        "stage": "completion",
        "write_db": False,
        "ok": True,
        "totals": {"profile_rows": 2},
        "worklists": {"blockers": [], "warnings": [], "agent_tasks": []},
    }
    monkeypatch.setattr(tool, "execute_completion_stage", lambda **_: payload)
    output_json = tmp_path / "consumer.json"
    output_md = tmp_path / "consumer.md"

    assert tool.main([
        "apply",
        "--stage",
        "completion",
        "--output-json",
        str(output_json),
        "--output-md",
        str(output_md),
    ]) == 0

    assert json.loads(output_json.read_text(encoding="utf-8"))["stage"] == "completion"
    assert "retrieval_v3 consumer report" in output_md.read_text(encoding="utf-8")
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_reason_catalog_records_non_automated_boundaries() -> None:
    assert tool.REASON_CATALOG["missing_talent_grade"]["owner"] == "agent_or_human"
    assert tool.REASON_CATALOG["claim_scoring_decision_required"]["severity_default"] == "downstream"
    assert tool.REASON_CATALOG["factorization_required"]["owner"] == "agent_or_human"
