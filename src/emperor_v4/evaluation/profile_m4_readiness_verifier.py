from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from emperor_v4.evaluation.profile_m4_readiness import AUDIT, MANUAL, REPORT, ROOT, build


PROJECT = ROOT / "config/project.yml"


def _load_json(path: Path) -> Any:
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), f"UTF-8 BOM forbidden: {path}"
    return json.loads(raw.decode("utf-8"))


def verify_payload(audit: dict[str, Any], report: str) -> dict[str, Any]:
    expected = build(write=False)
    assert audit == expected["audit"], "M4 readiness JSON is stale"
    assert report == expected["report"], "M4 readiness Markdown is stale"
    assert audit["canonical_status"] == "UNSETTLED_EVIDENCE_REVIEW"
    assert audit["population_count"] == 184
    assert audit["formal_profile_write"] is False
    assert audit["profile_total_enabled"] is False
    assert audit["profile_ranking_enabled"] is False
    assert audit["database_write"] is False
    assert audit["two_pass_review"] == {
        "mechanical_screen_count": 184,
        "semantic_review_count": 184,
        "actual_grade_change_count": 0,
    }
    assert audit["summary"]["formal_record_count"] == 0
    assert audit["summary"]["mandatory_topology_ruler_count"] == 184
    assert audit["summary"]["mandatory_group_domain_task_count"] == 1104
    assert audit["summary"]["ruler_with_zero_group_obligation_count"] == 0
    assert len(audit["records"]) == len({row["ruler_id"] for row in audit["records"]}) == 184
    assert len({row["task_code"] for row in audit["records"]}) == 184
    assert all(row["formal_grade"] is None for row in audit["records"])
    assert all(row["semantic_disposition"] in {
        "GROUP_LIFECYCLE_SOURCE_REVIEW_REQUIRED",
        "TOPOLOGY_RECONSTRUCTION_AND_CROSS_AXIS_REVIEW_REQUIRED",
        "TOPOLOGY_RECONSTRUCTION_REQUIRED",
    } for row in audit["records"])
    assert all(len(row["group_topology_tasks"]) == 6 for row in audit["records"])
    assert all(task["review_status"] == "RECONSTRUCTION_REQUIRED" for row in audit["records"] for task in row["group_topology_tasks"])
    assert all(audit["publication_gates"].values())
    forbidden = {"axis_grade", "radar_value", "score_100", "position"}
    assert not any(forbidden & row.keys() for row in audit["records"])

    manual = _load_json(MANUAL)
    priority_ids = [row["ruler_id"] for row in manual["priority_group_candidates"]]
    assert len(priority_ids) == len(set(priority_ids))
    assert set(priority_ids) == {
        row["ruler_id"] for row in audit["records"]
        if row["semantic_disposition"] == "GROUP_LIFECYCLE_SOURCE_REVIEW_REQUIRED"
    }

    project = yaml.safe_load(PROJECT.read_text(encoding="utf-8"))
    profile = project["profile_assessment"]
    assert profile["status"] == "seven_axes_formally_settled"
    assert "M4" not in profile["settled_axes"]
    pending = profile["unsettled_axes"]["M4"]
    assert pending["status"] == "UNSETTLED_EVIDENCE_REVIEW"
    assert pending["readiness_audit_json"] == AUDIT.relative_to(ROOT).as_posix()
    assert pending["readiness_report_markdown"] == REPORT.relative_to(ROOT).as_posix()
    assert pending["formal_profile_write"] is False
    assert pending["profile_total_enabled"] is False
    return {
        "status": "PASS",
        "checks": 29,
        "population_count": 184,
        "priority_group_candidate_count": audit["summary"]["priority_group_candidate_count"],
        "formal_record_count": 0,
    }


def verify() -> dict[str, Any]:
    return verify_payload(_load_json(AUDIT), REPORT.read_text(encoding="utf-8"))
