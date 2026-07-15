from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
from typing import Any, Mapping

from emperor_v4.contracts.person_snapshot import PersonProfileSnapshot


def _hash(value: object) -> str:
    return sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def build_supplemental_team_profiles(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != "supplemental-team-profile-evaluation-v1":
        raise ValueError("supplemental team profile schema_version 非法")
    authorization_ref = str(payload.get("authorization_ref") or "").strip()
    if not authorization_ref:
        raise ValueError("supplemental team profile 缺少 authorization_ref")
    items: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for evaluation in payload.get("evaluations", ()):
        name = str(evaluation.get("person") or "").strip()
        if not name or name in seen_names:
            raise ValueError("supplemental team profile person 必须非空且唯一")
        seen_names.add(name)
        source_refs = tuple(sorted({str(ref) for ref in evaluation["source_refs"]}))
        capability_domains = tuple(
            sorted({str(domain) for domain in evaluation["capability_domains"]})
        )
        if not source_refs or not capability_domains:
            raise ValueError(f"{name} 缺少 source_refs 或 capability_domains")
        person_ref = "PER-V4-" + _hash(
            {"canonical_name": name, "identity_scope": evaluation["identity_scope"]}
        )[:12].upper()
        semantic_source = {
            "person": name,
            "talent": evaluation["talent"],
            "negative": evaluation["negative"],
            "capability_domains": capability_domains,
            "source_refs": source_refs,
            "authorization_ref": authorization_ref,
        }
        source_row_fingerprint = _hash(semantic_source)
        snapshot_core = {
            "profile_ref": f"PROFILE-{person_ref}@v4-team-supplement-v1",
            "canonical_person_ref": person_ref,
            "snapshot_version": "v4-team-profile-supplement-v1",
            "talent_grade": evaluation["talent"]["grade"],
            "talent_grade_version": "talent-grade-v5-gatekeeper-supplement-v1",
            "talent_grade_confidence": float(
                evaluation["talent"]["confidence"]
            ),
            "talent_authority_consensus": evaluation["talent"][
                "authority_consensus"
            ],
            "talent_performance_support": evaluation["talent"][
                "performance_support"
            ],
            "talent_evidence_coverage": evaluation["talent"][
                "evidence_coverage"
            ],
            "capability_domains": capability_domains,
            "negative_talent_class": evaluation["negative"].get("class"),
            "negative_talent_severity": evaluation["negative"].get("severity"),
            "negative_talent_version": "negative-talent-v1-gatekeeper-supplement-v1",
            "lineage_refs": (authorization_ref, *source_refs),
            "source_profile_ref": "v4-supplemental-gatekeeper:" + name,
            "source_row_fingerprint": source_row_fingerprint,
            "review_status": "human_frozen",
        }
        snapshot = PersonProfileSnapshot(
            **snapshot_core,
            semantic_fingerprint=_hash(snapshot_core),
        )
        items.append(
            {
                "person": name,
                "identity_scope": evaluation["identity_scope"],
                "talent_evaluation": dict(evaluation["talent"]),
                "negative_evaluation": dict(evaluation["negative"]),
                "person_profile_snapshot": asdict(snapshot),
            }
        )
    items.sort(key=lambda item: item["person"])
    report: dict[str, Any] = {
        "schema_version": "supplemental-team-profile-promotion-report-v1",
        "status": "supplemental_team_profiles_human_frozen",
        "authorization_ref": authorization_ref,
        "summary": {
            "evaluated_profile_count": len(items),
            "human_frozen_profile_count": len(items),
            "database_write_count": 0,
            "model_research_profile_count": len(items),
            "research_agent_run_count": int(
                payload.get("research_agent_run_count", 0)
            ),
            "formal_scoring_allowed": False,
        },
        "items": items,
    }
    report["report_sha256"] = _hash(report)
    return report
