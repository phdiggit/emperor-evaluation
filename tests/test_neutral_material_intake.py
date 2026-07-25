from emperor_v4.evaluation.neutral_material_intake import (
    build_neutral_material_intake,
    outcome_records_from_registry,
)
from emperor_v4.persistence import CoreRegistryBatch, InMemoryCoreRegistry
from emperor_v4.persistence import RuleEvidenceUnitRecord
from emperor_v4.contracts.boundary import RuleEvidenceMember
from emperor_v4.contracts.episode import EpisodeParticipant, HistoricalEpisodePacket


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
    governance_facts = {
        "facts": [
            {
                "fact_ref": "GFACT-1",
                "title": "制度施行",
                "action": "制定并执行制度。",
                "implementation": "由主管官员持续执行。",
                "observable_result": "制度产生可观察结果。",
                "period": "某年",
                "source_refs": ["制度史/卷一@r3#Q1"],
                "ruler_contexts": ["RULER-A"],
            }
        ]
    }
    governance["achievements"][0]["neutral_fact_refs"].append("GFACT-1")

    result = build_neutral_material_intake(
        ruler_fanouts=(ruler,),
        person_lifecycle_fanouts=(biography,),
        governance_fact_sets=(governance_facts,),
        governance_registries=(governance,),
    )

    assert result["material_count"] == 3
    assert result["governance_achievements"][0]["projection_status"] == "ready_for_rule_judge"
    assert result["governance_achievements"][0]["neutral_material_refs"]
    governance_material = next(
        row for row in result["materials"] if row["neutral_fact_ref"] == "GFACT-1"
    )
    assert governance_material["source_channels"] == ["dynasty_governance"]
    assert governance_material["source_refs"] == ["制度史/卷一@r3#Q1"]
    assert governance_material["assertion_anchors"] == ["Q1"]
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


def test_governance_fact_without_exact_lineage_fails_closed() -> None:
    fact_set = {"facts": [{"fact_ref": "GFACT-1", "title": "无史源事实"}]}

    try:
        build_neutral_material_intake(governance_fact_sets=(fact_set,))
    except ValueError as exc:
        assert "fact_ref 和 source_refs" in str(exc)
    else:
        raise AssertionError("缺少制度史精确 lineage 时必须失败关闭")

    malformed = {
        "facts": [
            {
                "fact_ref": "GFACT-1",
                "title": "定位不完整",
                "source_refs": ["制度史/卷一@r1"],
            }
        ]
    }
    try:
        build_neutral_material_intake(governance_fact_sets=(malformed,))
    except ValueError as exc:
        assert "page@revision#quote" in str(exc)
    else:
        raise AssertionError("缺少 quote anchor 时必须失败关闭")


def test_unresolved_governance_achievement_does_not_enter_judge_queue() -> None:
    registry = {
        "achievements": [
            {
                "achievement_ref": "GOVACH-A",
                "independent_governance_key": "a",
                "canonical_label": "制度成果",
                "participants": [],
                "ruler_links": [],
                "neutral_fact_refs": ["MISSING-FACT"],
                "reuse_targets": ["i5b_team_building"],
            }
        ]
    }

    result = build_neutral_material_intake(governance_registries=(registry,))

    assert result["governance_achievements"][0]["projection_status"] == (
        "needs_fact_resolution"
    )
    assert result["projection_queue"] == []


def test_outcome_registry_converts_to_idempotent_current_rows() -> None:
    cluster = {
        "outcome_ref": "OUTCOME-A", "outcome_kind": "governance",
        "independent_key": "a", "canonical_label": "制度成果",
        "result_status": "operated", "result_direction": "positive",
        "scale": {"level": "national"}, "semantic_fingerprint": "fp-a",
        "fact_refs": ["FACT-A"], "source_refs": ["制度史@r1#Q1"],
        "members": [{"actor_ref": "PER-A", "actor_kind": "person", "role_code": "lead", "contribution_scope": "主持实行"}],
        "episode_refs": ["EP-OUTCOME-A"],
    }
    records = outcome_records_from_registry({"status": "shadow", "clusters": [cluster]})
    episode = HistoricalEpisodePacket(
        episode_id="EP-OUTCOME-A", episode_type="governance_outcome_chain",
        episode_status="proposed", evaluation_context="PER-A",
        semantic_fingerprint="fp-episode", time_start=None, time_end=None,
        time_precision="unknown", locations=(),
        participants=(EpisodeParticipant("PER-A", ("lead",), "resolved"),),
        action="制度成果", responsibility="甲主持", outcome=("已实行",),
        consequence=("国家级",), assertion_links=(), conflicts=(), uncertainties=(),
        completeness={}, lineage={}, provenance={},
    )
    registry = InMemoryCoreRegistry()
    batch = CoreRegistryBatch(episodes=(episode,), outcome_clusters=records)
    first = registry.apply(batch)
    second = registry.apply(batch)
    assert first.table_writes["historical_outcome_clusters"] == 1
    assert first.table_writes["outcome_cluster_members"] == 1
    assert first.table_writes["outcome_episode_links"] == 1
    assert second.business_write_count == 0


def test_rule_evidence_unit_is_current_membership_not_history() -> None:
    registry = InMemoryCoreRegistry()
    unit = RuleEvidenceUnitRecord(
        unit_ref="REU-A", rule_code="team_building", evaluation_context="RULER-A",
        direction="positive", semantic_fingerprint="fp-a", status="draft",
        payload={"reason": "治理成果支持团队建设判断"},
        members=(RuleEvidenceMember("OUTCOME-A", "outcome_cluster", "support"),),
    )
    first = registry.apply(CoreRegistryBatch(rule_evidence_units=(unit,)))
    second = registry.apply(CoreRegistryBatch(rule_evidence_units=(unit,)))
    assert first.table_writes["rule_evidence_units"] == 1
    assert first.table_writes["rule_evidence_members"] == 1
    assert second.business_write_count == 0
    assert registry.snapshot_counts()["rule_evidence_units"] == 1
