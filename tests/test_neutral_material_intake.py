from emperor_v4.evaluation.neutral_material_intake import (
    build_neutral_material_intake,
    governance_records_from_registry,
)
from emperor_v4.persistence import CoreRegistryBatch, InMemoryCoreRegistry
from emperor_v4.persistence import RuleEvidenceUnitRecord
from emperor_v4.contracts.boundary import RuleEvidenceMember


def test_three_channels_share_current_intake_without_premature_projection() -> None:
    ruler = {
        "ruler": {"ruler_ref": "RULER-A"},
        "person_fanout": [
            {
                "person_ref": "PER-A",
                "records": [
                    {
                        "neutral_record_id": "FACT-RULER-1",
                        "neutral_summary": "皇帝任命甲处理政务。",
                        "source_page": "通鉴/卷一",
                        "revision_ref": "r1",
                        "date": "某年",
                        "review": {
                            "supporting_assertion_anchors": ["任甲"],
                            "profile_eligibility": True,
                        },
                    }
                ],
            }
        ],
    }
    biography = {
        "people": [
            {
                "person_ref": "PER-A",
                "records": [
                    {
                        "record_ref": "PFACT-1",
                        "neutral_summary": "甲主持制度实行。",
                        "source_page": "列传/卷一",
                        "revision_ref": "r2",
                        "date": "某年",
                        "ruler_contexts": ["RULER-A"],
                        "assertions": [{"locator_anchor": "制度实行"}],
                    }
                ],
            }
        ]
    }
    governance = {
        "achievements": [
            {
                "achievement_ref": "GOVACH-A",
                "independent_governance_key": "a",
                "canonical_label": "制度成果",
                "participants": [{"person_ref": "PER-A"}],
                "ruler_links": [{"ruler_ref": "RULER-A"}],
                "neutral_fact_refs": ["PFACT-1"],
                "reuse_targets": ["i5b_team_building"],
            }
        ]
    }

    result = build_neutral_material_intake(
        ruler_fanouts=(ruler,),
        person_lifecycle_fanouts=(biography,),
        governance_registries=(governance,),
    )

    assert result["material_count"] == 2
    assert result["governance_achievements"][0]["projection_status"] == "ready_for_rule_judge"
    assert result["governance_achievements"][0]["neutral_material_refs"]
    assert result["projection_queue"] == [
        {
            "candidate_ref": result["projection_queue"][0]["candidate_ref"],
            "target": "i5b_team_building",
            "achievement_ref": "GOVACH-A",
            "status": "needs_rule_judge",
        }
    ]
    assert all(
        row["episode_intake_status"] == "needs_assertion_lineage"
        for row in result["materials"]
    )
    assert result["database_writes"] == result["score_writes"] == 0


def test_only_native_fact_identity_is_automatically_deduplicated() -> None:
    biography = {
        "people": [
            {
                "person_ref": person,
                "records": [
                    {
                        "record_ref": "PFACT-SHARED",
                        "neutral_summary": "共同议定。",
                        "source_page": "列传/卷一",
                        "revision_ref": "r1",
                        "date": "某年",
                        "ruler_contexts": ["RULER-A"],
                        "assertions": [{"locator_anchor": "共同议定"}],
                    }
                ],
            }
            for person in ("PER-A", "PER-B")
        ]
    }

    result = build_neutral_material_intake(person_lifecycle_fanouts=(biography,))

    assert result["material_count"] == 1
    assert result["materials"][0]["person_refs"] == ["PER-A", "PER-B"]


def test_governance_registry_converts_to_idempotent_current_rows() -> None:
    achievement = {
        "achievement_ref": "GOVACH-A", "independent_governance_key": "a",
        "canonical_label": "制度成果", "domain": "central_institutions",
        "implementation_status": "operated", "result_direction": "positive",
        "scale": {"level": "national"},
        "participants": [{"person_ref": "PER-A", "responsibility_role": "lead"}],
        "ruler_links": [{"ruler_ref": "RULER-A", "authorization_status": "explicit"}],
    }
    records = governance_records_from_registry({"achievements": [achievement]}, dynasty="唐")
    registry = InMemoryCoreRegistry()
    first = registry.apply(CoreRegistryBatch(governance_achievements=records))
    second = registry.apply(CoreRegistryBatch(governance_achievements=records))
    assert first.table_writes["governance_achievements"] == 1
    assert first.table_writes["governance_achievement_members"] == 2
    assert second.business_write_count == 0


def test_rule_evidence_unit_is_current_membership_not_history() -> None:
    registry = InMemoryCoreRegistry()
    unit = RuleEvidenceUnitRecord(
        unit_ref="REU-A", rule_code="team_building", evaluation_context="RULER-A",
        direction="positive", semantic_fingerprint="fp-a", status="draft",
        payload={"reason": "治理成果支持团队建设判断"},
        members=(RuleEvidenceMember("GOVACH-A", "governance_achievement", "support"),),
    )
    first = registry.apply(CoreRegistryBatch(rule_evidence_units=(unit,)))
    second = registry.apply(CoreRegistryBatch(rule_evidence_units=(unit,)))
    assert first.table_writes["rule_evidence_units"] == 1
    assert first.table_writes["rule_evidence_members"] == 1
    assert second.business_write_count == 0
    assert registry.snapshot_counts()["rule_evidence_units"] == 1
