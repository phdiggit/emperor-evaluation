from __future__ import annotations

import copy

import pytest

from emperor_v4.evaluation.profile_m4_readiness import build
from emperor_v4.evaluation.profile_m4_readiness_verifier import verify, verify_payload


def test_profile_m4_readiness_audit_passes_stable_verifier() -> None:
    report = verify()
    assert report["status"] == "PASS"
    assert report["population_count"] == 184
    assert report["formal_record_count"] == 0


def test_profile_m4_readiness_is_deterministic() -> None:
    first = build(write=False)
    second = build(write=False)
    assert first == second


def test_profile_m4_does_not_publish_a_default_grade() -> None:
    payload = build(write=False)
    broken = copy.deepcopy(payload["audit"])
    broken["records"][0]["axis_grade"] = "G3"
    with pytest.raises(AssertionError):
        verify_payload(broken, payload["report"])


def test_profile_m4_does_not_promote_c3_or_c5_hits_to_formal_records() -> None:
    payload = build(write=False)["audit"]
    assert payload["summary"]["substantive_candidate_unit_count"] > 0
    assert payload["summary"]["formal_record_count"] == 0
    assert all(row["formal_grade"] is None for row in payload["records"])


def test_profile_m4_requires_group_topology_for_every_ruler() -> None:
    payload = build(write=False)["audit"]
    assert payload["summary"]["mandatory_topology_ruler_count"] == 184
    assert payload["summary"]["mandatory_group_domain_task_count"] == 184 * 6
    assert payload["summary"]["ruler_with_zero_group_obligation_count"] == 0
    assert all(len(row["group_topology_tasks"]) == 6 for row in payload["records"])
    assert all(row["semantic_disposition"] != "LOCAL_STRUCTURED_ENTRY_GAP" for row in payload["records"])


def test_profile_m4_keeps_external_alliances_on_m2() -> None:
    payload = build(write=False)["audit"]
    assert "外国" in payload["routing_rules"]["m2"]
    assert "PROFILE_M2" not in payload["entry_candidate_counts"]
