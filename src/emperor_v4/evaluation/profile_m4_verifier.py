from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.profile_parent_schema import parent_chains
from emperor_v4.evaluation.profile_record_integrity import verify_current_records

from emperor_v4.evaluation.profile_m4_settlement import (
    AUDIT,
    FULL_POOL_REVIEW,
    HIGH_REVIEW,
    MANIFEST,
    MARKDOWN,
    NORMATIVE_ENTRIES,
    POOL,
    PROJECT,
    ROOT,
    SCORES,
    SETTLEMENT,
)
from emperor_v4.evaluation.profile_markdown import render_profile_markdown


def _read(path: Path) -> bytes:
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), f"UTF-8 BOM forbidden: {path}"
    raw.decode("utf-8")
    return raw


def _load(path: Path) -> Any:
    _read(path)
    return load_json(path)


def _walk(value: Any):
    yield value
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def verify_payloads(settlement: dict) -> dict:
    records = settlement["records"]
    pool = _load(POOL)
    included = {row["ruler_id"] for row in pool["records"] if row["pool_status"] == "INCLUDED"}
    assert settlement["schema_version"] == "profile-m4-formal-settlement-v2"
    assert settlement["canonical_status"] == "FORMAL_CURRENT"
    assert settlement["axis_code"] == "M4"
    assert settlement["authority_mode"] == "FORMAL_SETTLEMENT_PATCH_SOURCE"
    assert settlement["contract_version"]
    assert "manual_adjudication" not in settlement
    assert settlement["record_count"] == len(records) == len(included)
    assert {row["ruler_id"] for row in records} == included
    assert len({row["task_code"] for row in records}) == len(records)
    assert all(row["task_code"] == f"PROFILE-M4-{row['ruler_id']}" for row in records)
    assert records == sorted(records, key=lambda row: (-row["radar_value"], row["ruler_id"]))
    assert not any(settlement[key] for key in (
        "formal_rank_write", "profile_total_enabled", "profile_ranking_enabled",
        "composite_ranking_write", "database_write",
    ))
    assert settlement["unresolved_evidence_gap_count"] == 0
    assert settlement["unclosed_non_scoring_observation_count"] == sum(
        len(row.get("non_scoring_unclosed_observations", [])) for row in records
    )
    forbidden = {
        "source_axis_grade", "source_axis_position", "source_axis_score", "inherited_grade",
        "keyword_score", "group_count_score", "material_count_score", "first_item_b_score",
        "fourth_item_a_score", "second_item_score", "profile_rank",
    }
    assert not any(isinstance(value, str) and value in forbidden for value in _walk(settlement))
    parent_ids = []
    for row in records:
        parents = parent_chains(row)
        assert "adjudication_ref" not in row
        assert row["radar_value"] == row["score_100"] == SCORES[row["axis_grade"]][row["position"]]
        assert row["axis_evidence_level"] in {"E1", "E2", "E3"}
        assert row["output_mode"] in {"EPISODE_TAG", "BOUNDED_PROFILE", "FULL_GRADE"}
        assert row["score_status"] in {"FINAL", "EVIDENCE_LIMITED"}
        assert row["formal_status"] == "FORMAL_CURRENT"
        if not parents:
            assert row["axis_evidence_level"] == "E1"
            assert row["output_mode"] == "EPISODE_TAG"
            assert row["score_status"] == "EVIDENCE_LIMITED"
        assert len(row["typical_pattern"]) >= 20
        assert isinstance(row["limitations"], list) and row["counterpattern"]
        if row["score_status"] == "EVIDENCE_LIMITED":
            assert row["limitations"], "bounded profile must state its evidence gaps"
        assert set(row["major_mechanisms_observed"]) == {
            "ALLIANCE_FORMATION", "INTEREST_STATUS_CONFIGURATION", "POLITICAL_CREDIT", "CONFLICT_AND_EXIT",
        }
        assert row["axis_relevance_check"] == {
            "m2_external_alliance_used": False,
            "c3_individual_talent_grade_used": False,
            "c5_ethics_grade_used": False,
            "first_item_b_score_used": False,
            "fourth_item_a_result_backsolve_used": False,
            "second_item_result_used": False,
            "group_count_used": False,
            "material_count_used": False,
        }
        for parent in parents:
            parent_ids.append(parent["parent_id"])
            assert parent["closure_status"] == "CLOSED"
            assert parent["direction"] in {"POSITIVE", "NEGATIVE", "MIXED", "MIXED_POSITIVE", "MIXED_NEGATIVE"}
            assert parent["material_intensity"] in {"MI1_CASE", "MI2_LIFECYCLE", "MI3_SUSTAINED_SYSTEMIC", "MI4_CROSS_PHASE_SYSTEMIC"}
            for field in (
                "actual_power_phase", "coalition_task", "group_structure",
                "interests_and_security_expectations", "personal_choice",
                "status_and_resource_configuration", "political_credit_and_delivery",
                "feedback_and_conflict_handling", "exit_result",
            ):
                assert str(parent[field]).strip(), f"open M4 lifecycle {parent['parent_id']} {field}"
            assert parent["source_refs"]
            assert all(urlparse(ref).scheme in {"http", "https"} for ref in parent["source_refs"])
            source_ids = {source["source_id"] for source in row["source_register"]}
            assert set(parent["source_ids"]) <= source_ids
            assert set(parent.get("portable_fallback_source_ids", [])) <= source_ids
            assert not (set(parent.get("excluded_nonportable_source_ids", [])) & source_ids)
            assert set(parent["boundary_review"]) == {"m2", "c3", "c5", "result_axes"}
        for observation in row.get("non_scoring_unclosed_observations", []):
            assert observation["closure_status"] != "CLOSED"
            assert observation["parent_id"] not in parent_ids
            assert all(urlparse(ref).scheme in {"http", "https"} for ref in observation["source_refs"])
        assert len(row["group_topology"]) == 6
        assert row["positive_search"] and row["negative_search"]
        assert all(source["source_id"] and source["title"] for source in row["source_register"])
        assert all(
            source["url_status"] == "DIRECT_HTTP_REFERENCE"
            and urlparse(source["url"]).scheme in {"http", "https"}
            for source in row["source_register"]
        )
        if row["axis_grade"] in {"G4", "G5"}:
            if row["score_status"] == "FINAL":
                assert row["axis_evidence_level"] == "E3"
                assert row["output_mode"] == "FULL_GRADE"
                assert row["confidence"] == "HIGH"
                assert row["source_density_review"] in {"COVERAGE_CLOSED", "COUNTEREVIDENCE_FOUND"}
            else:
                assert row["axis_evidence_level"] in {"E1", "E2"}
                assert row["output_mode"] in {"EPISODE_TAG", "BOUNDED_PROFILE"}
                assert row["confidence"] in {"LOW", "MEDIUM"}
                assert row["source_density_review"] == "MATERIAL_DENSITY_LIMITED"
    assert len(parent_ids) == len(set(parent_ids))
    assert len({row["typical_pattern"] for row in records}) == len(records)
    verify_current_records(settlement)
    return {"status": "PASS", "record_count": len(records), "parent_count": sum(len(parent_chains(r)) for r in records)}


def verify() -> dict:
    settlement = _load(SETTLEMENT)
    assert _read(MARKDOWN).decode("utf-8") == render_profile_markdown(settlement), "reading view differs from current formal records"
    result = verify_payloads(settlement)
    profile = yaml.safe_load(_read(PROJECT).decode("utf-8"))["profile_assessment"]
    entry = profile["settled_axes"]["M4"]
    assert (ROOT / entry["json"]).resolve() == SETTLEMENT.resolve()
    assert (ROOT / entry["markdown"]).resolve() == MARKDOWN.resolve()
    manifest = _load(MANIFEST)
    registered = next(r for r in manifest["axes"] if r["axis_code"] == "M4")
    assert registered["json"] == SETTLEMENT.relative_to(MANIFEST.parent).as_posix()
    assert registered["markdown"] == MARKDOWN.relative_to(MANIFEST.parent).as_posix()
    assert registered["record_count"] == len(settlement["records"])
    return result


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
