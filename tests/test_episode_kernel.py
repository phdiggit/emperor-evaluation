from __future__ import annotations

from dataclasses import replace

import pytest

from emperor_v4.contracts.assertion import AssertionDraft, PassageSupport
from emperor_v4.contracts.boundary import (
    AssertionDisposition,
    EpisodeBoundaryGroup,
    EpisodeBoundaryReviewResult,
    EpisodePairDisposition,
    EpisodeRelation,
    EpisodeRelationDraft,
)
from emperor_v4.contracts.episode import EpisodeParticipant
from emperor_v4.domain.episode import (
    build_episode_packet,
    group_episode_candidates,
    group_episode_candidates_with_hints,
)
from emperor_v4.domain.boundary import (
    InMemoryBoundaryReviewCache,
    build_review_units,
    cluster_propositions,
    execute_boundary_reviews,
    materialize_boundary_review,
    plan_boundary_reviews,
    validate_episode_relation_graph,
)


def _assertion(
    code: str,
    *,
    passage: str,
    ruler: str = "李世民",
    person: str = "李靖",
    time: str = "贞观三年",
    domain: str = "北方战区",
    summary: str = "任李靖统兵",
    polarity: str = "asserted",
    normalized_start: int | None = None,
    responsibility_family: str = "military_command",
    participant_roles: tuple[tuple[str, str], ...] | None = None,
    focal_person_ref: str | None = None,
    passage_support: PassageSupport | None = None,
) -> AssertionDraft:
    qualifiers = {
        "evaluation_context": ruler,
        "candidate_participant_roles": participant_roles
        or ((ruler, "ruler"), (person, "commander")),
        "episode_type": "appointment_delegation",
        "office_or_domain": domain,
        "responsibility_family": responsibility_family,
        "outcome": "完成任务",
        "legacy_claim_summary": summary,
    }
    if normalized_start is not None:
        qualifiers["normalized_time"] = {
            "start_sort_key": normalized_start,
            "end_sort_key": normalized_start,
            "precision": "year",
            "dynasty_or_era": "唐",
        }
    if focal_person_ref:
        qualifiers["focal_person_ref"] = focal_person_ref
    return AssertionDraft(
        assertion_code=code,
        source_passage_ref=passage,
        assertion_type="event_fact",
        subject=ruler,
        predicate="任命统兵",
        object=person,
        time_expression=time,
        location_expression="北境",
        qualifiers=qualifiers,
        polarity=polarity,
        source_attribution={"document_code": f"D-{passage}"},
        candidate_episode_key=None,
        confidence=0.9,
        passage_support=passage_support,
    )


def _with_claim(assertion: AssertionDraft, claim_key: str) -> AssertionDraft:
    return replace(assertion, extraction_provenance={"claim_key": claim_key})


def test_proposition_cluster_collapses_passage_fanout_without_losing_lineage():
    first = _with_claim(_assertion("A-1", passage="P-1"), "CLAIM-1")
    second = _with_claim(_assertion("A-2", passage="P-2"), "CLAIM-1")

    clusters = cluster_propositions([first, second])

    assert len(clusters) == 1
    assert clusters[0].assertion_refs == ("A-1", "A-2")
    assert clusters[0].evidence_refs == ("P-1", "P-2")


def test_v27_proposition_cluster_respects_passage_scoped_atomic_components():
    first_support = PassageSupport(
        support_mode="atomic_component",
        assertion_semantic_key="component-appointment",
        supported_fields=("identity", "action", "responsibility"),
    )
    second_support = PassageSupport(
        support_mode="context_only",
        assertion_semantic_key="context-outcome",
        supported_fields=("outcome", "context"),
    )
    first = _with_claim(
        _assertion("A-1", passage="P-1", passage_support=first_support),
        "CLAIM-1",
    )
    second = _with_claim(
        _assertion("A-2", passage="P-2", passage_support=second_support),
        "CLAIM-1",
    )

    clusters = cluster_propositions([first, second])

    assert len(clusters) == 2
    assert {cluster.assertion_refs for cluster in clusters} == {("A-1",), ("A-2",)}


def test_v27_proposition_cluster_uses_equivalent_support_key_within_claim():
    support = PassageSupport(
        support_mode="equivalent_evidence",
        assertion_semantic_key="same-appointment",
        supported_fields=("identity", "action", "responsibility"),
    )
    first = _with_claim(
        _assertion("A-1", passage="P-1", passage_support=support), "CLAIM-1"
    )
    second = _with_claim(
        _assertion("A-2", passage="P-2", passage_support=support), "CLAIM-1"
    )

    clusters = cluster_propositions([first, second])

    assert len(clusters) == 1
    assert clusters[0].assertion_refs == ("A-1", "A-2")


def test_v27_rejects_context_only_assertion_as_episode_core():
    support = PassageSupport(
        support_mode="context_only",
        assertion_semantic_key="context-result",
        supported_fields=("outcome", "context"),
    )
    assertion = _with_claim(
        _assertion("A-1", passage="P-1", passage_support=support), "CLAIM-1"
    )
    clusters = cluster_propositions([assertion])
    unit = build_review_units(clusters)[0]
    review = EpisodeBoundaryReviewResult(
        review_unit_ref=unit.review_unit_code,
        review_unit_cache_key=unit.cache_key,
        proposition_semantic_hashes=unit.proposition_semantic_hashes,
        boundary_policy_version=unit.boundary_policy_version,
        output_schema_version=unit.output_schema_version,
        model_family=unit.model_family,
        episode_groups=(
            EpisodeBoundaryGroup(
                "E1", ("A-1",), "wrongly promoted context", 0.9, "CONTEXT-1"
            ),
        ),
        relations=(),
        assertion_dispositions=(
            AssertionDisposition("A-1", "core_of_episode", ("E1",), "wrong"),
        ),
        review_provenance={},
    )

    with pytest.raises(ValueError, match="context_only Assertion"):
        materialize_boundary_review(
            [assertion], review, review_unit=unit, proposition_clusters=clusters
        )


def test_v27_allows_context_only_review_unit_to_close_without_episode():
    support = PassageSupport(
        support_mode="context_only",
        assertion_semantic_key="context-result",
        supported_fields=("outcome", "context"),
    )
    assertion = _with_claim(
        _assertion("A-1", passage="P-1", passage_support=support), "CLAIM-1"
    )
    clusters = cluster_propositions([assertion])
    unit = build_review_units(clusters)[0]
    review = EpisodeBoundaryReviewResult(
        review_unit_ref=unit.review_unit_code,
        review_unit_cache_key=unit.cache_key,
        proposition_semantic_hashes=unit.proposition_semantic_hashes,
        boundary_policy_version=unit.boundary_policy_version,
        output_schema_version=unit.output_schema_version,
        model_family=unit.model_family,
        episode_groups=(),
        relations=(),
        assertion_dispositions=(
            AssertionDisposition(
                "A-1", "unresolved", (), "context-only passage has no episode core"
            ),
        ),
        review_provenance={},
    )

    result = materialize_boundary_review(
        [assertion], review, review_unit=unit, proposition_clusters=clusters
    )

    assert result.episode_packets == ()
    assert tuple(item.assertion_ref for item in result.unresolved_assertions) == (
        "A-1",
    )


def test_v27_proposition_identity_includes_claim_local_support_key():
    first = _with_claim(
        _assertion(
            "A-1",
            passage="P-1",
            passage_support=PassageSupport(
                "atomic_component",
                "component-one",
                ("identity", "action"),
            ),
        ),
        "CLAIM-1",
    )
    second = _with_claim(
        _assertion(
            "A-2",
            passage="P-2",
            passage_support=PassageSupport(
                "atomic_component",
                "component-two",
                ("identity", "action"),
            ),
        ),
        "CLAIM-1",
    )

    clusters = cluster_propositions([first, second])

    assert len(clusters) == 2
    assert len({item.proposition_code for item in clusters}) == 2


def test_structured_time_equivalence_ignores_display_expression_difference():
    first = _with_claim(
        _assertion(
            "A-1", passage="P-1", time="三年春正月甲子", normalized_start=27
        ),
        "CLAIM-1",
    )
    second = _with_claim(
        _assertion(
            "A-2", passage="P-2", time="建武三年春正月", normalized_start=27
        ),
        "CLAIM-2",
    )

    clusters = cluster_propositions([first, second])

    assert len(clusters) == 1
    assert set(clusters[0].assertion_refs) == {"A-1", "A-2"}


def test_v26_atomic_group_allows_responsibility_domain_surface_variants():
    first = _with_claim(
        _assertion(
            "A-1", passage="P-1", domain="温之战", normalized_start=25
        ),
        "CLAIM-1",
    )
    second = _with_claim(
        _assertion(
            "A-2", passage="P-2", domain="温地战事", normalized_start=25
        ),
        "CLAIM-2",
    )
    assertions = [first, second]
    clusters = cluster_propositions(assertions)
    unit = build_review_units(clusters)[0]
    review = EpisodeBoundaryReviewResult(
        review_unit_ref=unit.review_unit_code,
        review_unit_cache_key=unit.cache_key,
        proposition_semantic_hashes=unit.proposition_semantic_hashes,
        boundary_policy_version=unit.boundary_policy_version,
        output_schema_version=unit.output_schema_version,
        model_family=unit.model_family,
        episode_groups=(
            EpisodeBoundaryGroup(
                "E1", ("A-1", "A-2"), "same battle", 0.9, "BATTLE-WEN-25"
            ),
        ),
        relations=(),
        assertion_dispositions=(
            AssertionDisposition("A-1", "core_of_episode", ("E1",), "core"),
            AssertionDisposition("A-2", "core_of_episode", ("E1",), "core"),
        ),
        review_provenance={},
    )

    result = materialize_boundary_review(
        assertions, review, review_unit=unit, proposition_clusters=clusters
    )

    assert len(result.episode_packets) == 1
    assert result.episode_packets[0].responsibility == "温之战|温地战事"


def test_review_unit_cache_invalidates_only_changed_focal_person():
    lijing = [
        _with_claim(_assertion("A-1", passage="P-1"), "CLAIM-1"),
        _with_claim(_assertion("A-2", passage="P-2"), "CLAIM-1"),
    ]
    hou = [
        _with_claim(
            _assertion("A-3", passage="P-3", person="侯君集"), "CLAIM-2"
        )
    ]
    first_plan = plan_boundary_reviews([*lijing, *hou])
    cached_keys = {item.cache_key for item in first_plan.review_units}
    changed_lijing = _with_claim(
        _assertion("A-4", passage="P-4", time="贞观四年"), "CLAIM-3"
    )

    second_plan = plan_boundary_reviews(
        [*lijing, *hou, changed_lijing], cached_review_keys=cached_keys
    )

    assert len(first_plan.proposition_clusters) == 2
    assert len(first_plan.review_units) == 2
    assert second_plan.model_call_count == 1
    assert len(second_plan.cache_hit_unit_codes) == 1
    assert len(second_plan.cache_miss_unit_codes) == 1

    synonymous_evidence = _with_claim(
        _assertion("A-5", passage="P-5"), "CLAIM-1"
    )
    evidence_only_plan = plan_boundary_reviews(
        [*lijing, *hou, synonymous_evidence], cached_review_keys=cached_keys
    )
    assert evidence_only_plan.model_call_count == 0


def test_review_unit_uses_structured_time_and_responsibility_family():
    first = _with_claim(
        _assertion("A-1", passage="P-1", normalized_start=600), "CLAIM-1"
    )
    distant = _with_claim(
        _assertion("A-2", passage="P-2", normalized_start=640), "CLAIM-2"
    )
    other_family = _with_claim(
        _assertion(
            "A-3",
            passage="P-3",
            normalized_start=601,
            responsibility_family="civil_appointment",
        ),
        "CLAIM-3",
    )

    units = build_review_units(cluster_propositions([first, distant, other_family]))

    assert len(units) == 3
    assert {unit.responsibility_family for unit in units} == {
        "military_command",
        "civil_appointment",
    }


def test_focal_person_is_invariant_to_participant_order():
    roles_a = (("李世民", "ruler"), ("萧何", "advisor"), ("韩信", "commander"))
    roles_b = tuple(reversed(roles_a))
    first = _with_claim(
        _assertion("A-1", passage="P-1", participant_roles=roles_a), "CLAIM-1"
    )
    second = _with_claim(
        _assertion("A-2", passage="P-2", participant_roles=roles_b), "CLAIM-1"
    )

    cluster = cluster_propositions([first, second])[0]

    assert cluster.focal_person_ref == "韩信"
    assert cluster.focal_role == "commander"
    assert cluster.secondary_participant_refs == ("萧何",)


def test_boundary_review_keeps_atomic_episodes_and_materializes_relation():
    appointment = _with_claim(
        _assertion("A-1", passage="P-1", time="贞观三年"), "CLAIM-1"
    )
    renewal = _with_claim(
        _assertion("A-2", passage="P-2", time="贞观四年"), "CLAIM-2"
    )
    clusters = cluster_propositions([appointment, renewal])
    unit = build_review_units(clusters)[0]
    review = EpisodeBoundaryReviewResult(
        review_unit_ref=unit.review_unit_code,
        review_unit_cache_key=unit.cache_key,
        proposition_semantic_hashes=unit.proposition_semantic_hashes,
        boundary_policy_version=unit.boundary_policy_version,
        output_schema_version=unit.output_schema_version,
        model_family=unit.model_family,
        episode_groups=(
            EpisodeBoundaryGroup("E1", ("A-1",), "首次授权", 0.95, "AUTH-1"),
            EpisodeBoundaryGroup("E2", ("A-2",), "重新授权", 0.95, "AUTH-2"),
        ),
        relations=(
            EpisodeRelationDraft("E1", "E2", "renews_authority", ("A-2",), 0.9),
        ),
        assertion_dispositions=(
            AssertionDisposition("A-1", "core_of_episode", ("E1",), "首次授权"),
            AssertionDisposition("A-2", "core_of_episode", ("E2",), "重新授权"),
        ),
        review_provenance={"reviewer": "test"},
        pair_dispositions=(
            EpisodePairDisposition(
                "E1", "E2", "related", "重新授权延续首次授权", "renews_authority"
            ),
        ),
    )

    result = materialize_boundary_review(
        [appointment, renewal],
        review,
        review_unit=unit,
        proposition_clusters=clusters,
    )

    assert len(result.episode_packets) == 2
    assert len(result.episode_relations) == 1
    assert result.episode_relations[0].relation_type == "renews_authority"
    assert result.episode_relations[0].semantic_version == 1
    assert result.episode_relations[0].evidence_links[0].source_passage_ref == "P-2"


def test_v22_boundary_review_requires_every_episode_pair_disposition():
    with pytest.raises(ValueError, match="完整处置所有 Episode pairs"):
        EpisodeBoundaryReviewResult(
            review_unit_ref="RU-1",
            review_unit_cache_key="CACHE-1",
            proposition_semantic_hashes=("HASH-1", "HASH-2"),
            boundary_policy_version="episode-boundary-policy-v2.2",
            output_schema_version="episode-boundary-review-v2.2",
            model_family="M1",
            episode_groups=(
                EpisodeBoundaryGroup("E1", ("A-1",), "first", 0.9),
                EpisodeBoundaryGroup("E2", ("A-2",), "second", 0.9),
            ),
            relations=(),
            assertion_dispositions=(
                AssertionDisposition("A-1", "core_of_episode", ("E1",), "first"),
                AssertionDisposition("A-2", "core_of_episode", ("E2",), "second"),
            ),
            review_provenance={},
        )


def test_v22_materialization_rejects_cross_structure_episode_merge():
    assertions = [
        _with_claim(
            _assertion("A-1", passage="P-1", normalized_start=629), "CLAIM-1"
        ),
        _with_claim(
            _assertion("A-2", passage="P-2", normalized_start=630), "CLAIM-2"
        ),
    ]
    clusters = cluster_propositions(assertions)
    unit = build_review_units(clusters)[0]
    review = EpisodeBoundaryReviewResult(
        review_unit_ref=unit.review_unit_code,
        review_unit_cache_key=unit.cache_key,
        proposition_semantic_hashes=unit.proposition_semantic_hashes,
        boundary_policy_version=unit.boundary_policy_version,
        output_schema_version=unit.output_schema_version,
        model_family=unit.model_family,
        episode_groups=(
            EpisodeBoundaryGroup(
                "E1", ("A-1", "A-2"), "same mandate", 0.9, "MANDATE-1"
            ),
        ),
        relations=(),
        assertion_dispositions=(
            AssertionDisposition("A-1", "core_of_episode", ("E1",), "core"),
            AssertionDisposition("A-2", "core_of_episode", ("E1",), "core"),
        ),
        review_provenance={},
    )

    with pytest.raises(ValueError, match="必须拆成原子 Episode"):
        materialize_boundary_review(
            assertions, review, review_unit=unit, proposition_clusters=clusters
        )


def test_v22_materialization_rejects_unanchored_legacy_claim_fanout_merge():
    assertions = [
        _with_claim(_assertion("A-1", passage="P-1"), "CLAIM-1"),
        _with_claim(_assertion("A-2", passage="P-2"), "CLAIM-1"),
    ]
    clusters = cluster_propositions(assertions)
    unit = build_review_units(clusters)[0]
    review = EpisodeBoundaryReviewResult(
        review_unit_ref=unit.review_unit_code,
        review_unit_cache_key=unit.cache_key,
        proposition_semantic_hashes=unit.proposition_semantic_hashes,
        boundary_policy_version=unit.boundary_policy_version,
        output_schema_version=unit.output_schema_version,
        model_family=unit.model_family,
        episode_groups=(
            EpisodeBoundaryGroup("E1", ("A-1", "A-2"), "same legacy claim", 0.9),
        ),
        relations=(),
        assertion_dispositions=(
            AssertionDisposition("A-1", "core_of_episode", ("E1",), "core"),
            AssertionDisposition("A-2", "core_of_episode", ("E1",), "core"),
        ),
        review_provenance={},
    )

    with pytest.raises(ValueError, match="必须声明 atomic_event_key"):
        materialize_boundary_review(
            assertions, review, review_unit=unit, proposition_clusters=clusters
        )


def test_v22_materialization_allows_reviewer_frozen_atomic_key_across_passages():
    assertions = [
        _with_claim(_assertion("A-1", passage="P-1"), "CLAIM-1"),
        _with_claim(_assertion("A-2", passage="P-2"), "CLAIM-1"),
    ]
    clusters = cluster_propositions(assertions)
    current_unit = build_review_units(clusters)[0]
    unit = replace(
        current_unit,
        cache_key="V26-LEGACY-CACHE",
        boundary_policy_version="episode-boundary-policy-v2.6",
        output_schema_version="episode-boundary-review-v2.6",
    )
    review = EpisodeBoundaryReviewResult(
        review_unit_ref=unit.review_unit_code,
        review_unit_cache_key=unit.cache_key,
        proposition_semantic_hashes=unit.proposition_semantic_hashes,
        boundary_policy_version=unit.boundary_policy_version,
        output_schema_version=unit.output_schema_version,
        model_family=unit.model_family,
        episode_groups=(
            EpisodeBoundaryGroup(
                "E1", ("A-1", "A-2"), "shared atomic key", 0.9, "ATOMIC-1"
            ),
        ),
        relations=(),
        assertion_dispositions=(
            AssertionDisposition("A-1", "core_of_episode", ("E1",), "core"),
            AssertionDisposition("A-2", "core_of_episode", ("E1",), "core"),
        ),
        review_provenance={},
    )

    result = materialize_boundary_review(
        assertions, review, review_unit=unit, proposition_clusters=clusters
    )

    assert len(result.episode_packets) == 1
    assert len(result.episode_packets[0].assertion_links) == 2


def test_v27_reviewer_atomic_key_cannot_override_unscoped_claim_fanout():
    assertions = [
        _with_claim(_assertion("A-1", passage="P-1"), "CLAIM-1"),
        _with_claim(_assertion("A-2", passage="P-2"), "CLAIM-1"),
    ]
    clusters = cluster_propositions(assertions)
    unit = build_review_units(clusters)[0]
    review = EpisodeBoundaryReviewResult(
        review_unit_ref=unit.review_unit_code,
        review_unit_cache_key=unit.cache_key,
        proposition_semantic_hashes=unit.proposition_semantic_hashes,
        boundary_policy_version=unit.boundary_policy_version,
        output_schema_version=unit.output_schema_version,
        model_family=unit.model_family,
        episode_groups=(
            EpisodeBoundaryGroup(
                "E1", ("A-1", "A-2"), "reviewer guessed same event", 0.9, "ATOMIC-1"
            ),
        ),
        relations=(),
        assertion_dispositions=(
            AssertionDisposition("A-1", "core_of_episode", ("E1",), "core"),
            AssertionDisposition("A-2", "core_of_episode", ("E1",), "core"),
        ),
        review_provenance={},
    )

    with pytest.raises(ValueError, match="Reviewer atomic_event_key 不得覆盖"):
        materialize_boundary_review(
            assertions, review, review_unit=unit, proposition_clusters=clusters
        )


def test_v27_allows_explicit_equivalent_passage_evidence_merge():
    support = PassageSupport(
        support_mode="equivalent_evidence",
        assertion_semantic_key="same-event",
        supported_fields=("identity", "action", "responsibility", "outcome"),
    )
    assertions = [
        _with_claim(
            _assertion("A-1", passage="P-1", passage_support=support), "CLAIM-1"
        ),
        _with_claim(
            _assertion("A-2", passage="P-2", passage_support=support), "CLAIM-1"
        ),
    ]
    clusters = cluster_propositions(assertions)
    unit = build_review_units(clusters)[0]
    review = EpisodeBoundaryReviewResult(
        review_unit_ref=unit.review_unit_code,
        review_unit_cache_key=unit.cache_key,
        proposition_semantic_hashes=unit.proposition_semantic_hashes,
        boundary_policy_version=unit.boundary_policy_version,
        output_schema_version=unit.output_schema_version,
        model_family=unit.model_family,
        episode_groups=(
            EpisodeBoundaryGroup(
                "E1", ("A-1", "A-2"), "explicit equivalent evidence", 0.9, "ATOMIC-1"
            ),
        ),
        relations=(),
        assertion_dispositions=(
            AssertionDisposition("A-1", "core_of_episode", ("E1",), "core"),
            AssertionDisposition("A-2", "core_of_episode", ("E1",), "core"),
        ),
        review_provenance={},
    )

    result = materialize_boundary_review(
        assertions, review, review_unit=unit, proposition_clusters=clusters
    )

    assert len(result.episode_packets) == 1
    assert len(result.episode_packets[0].assertion_links) == 2


def test_v22_related_pair_must_match_relation_type():
    with pytest.raises(ValueError, match="related pair 与 EpisodeRelationDraft 不一致"):
        EpisodeBoundaryReviewResult(
            review_unit_ref="RU-1",
            review_unit_cache_key="CACHE-1",
            proposition_semantic_hashes=("HASH-1", "HASH-2"),
            boundary_policy_version="episode-boundary-policy-v2.2",
            output_schema_version="episode-boundary-review-v2.2",
            model_family="M1",
            episode_groups=(
                EpisodeBoundaryGroup("E1", ("A-1",), "first", 0.9),
                EpisodeBoundaryGroup("E2", ("A-2",), "second", 0.9),
            ),
            relations=(
                EpisodeRelationDraft("E1", "E2", "outcome_of", ("A-2",), 0.9),
            ),
            assertion_dispositions=(
                AssertionDisposition("A-1", "core_of_episode", ("E1",), "first"),
                AssertionDisposition("A-2", "core_of_episode", ("E2",), "second"),
            ),
            pair_dispositions=(
                EpisodePairDisposition(
                    "E1", "E2", "related", "mismatch", "renews_authority"
                ),
            ),
            review_provenance={},
        )


def test_v23_duplicate_structural_groups_fail_before_relation_materialization():
    assertions = [
        _with_claim(_assertion("A-1", passage="P-1"), "CLAIM-1"),
        _with_claim(_assertion("A-2", passage="P-2"), "CLAIM-2"),
    ]
    clusters = cluster_propositions(assertions)
    current_unit = build_review_units(clusters)[0]
    unit = replace(
        current_unit,
        cache_key="V23-CACHE",
        boundary_policy_version="episode-boundary-policy-v2.3",
        output_schema_version="episode-boundary-review-v2.3",
    )
    review = EpisodeBoundaryReviewResult(
        review_unit_ref=unit.review_unit_code,
        review_unit_cache_key=unit.cache_key,
        proposition_semantic_hashes=unit.proposition_semantic_hashes,
        boundary_policy_version=unit.boundary_policy_version,
        output_schema_version=unit.output_schema_version,
        model_family=unit.model_family,
        episode_groups=(
            EpisodeBoundaryGroup("E1", ("A-1",), "first atomic event", 0.9),
            EpisodeBoundaryGroup("E2", ("A-2",), "second atomic event", 0.9),
        ),
        relations=(),
        assertion_dispositions=(
            AssertionDisposition("A-1", "core_of_episode", ("E1",), "core"),
            AssertionDisposition("A-2", "core_of_episode", ("E2",), "core"),
        ),
        pair_dispositions=(
            EpisodePairDisposition(
                "E1", "E2", "distinct_unrelated", "two separate events"
            ),
        ),
        review_provenance={},
    )

    with pytest.raises(ValueError, match="生成重复 Episode ID"):
        materialize_boundary_review(
            assertions, review, review_unit=unit, proposition_clusters=clusters
        )


def test_boundary_review_rejects_assertion_in_two_episode_cores():
    with pytest.raises(ValueError, match="最多只能属于一个"):
        EpisodeBoundaryReviewResult(
            review_unit_ref="RU-1",
            review_unit_cache_key="CACHE-1",
            proposition_semantic_hashes=("HASH-1",),
            boundary_policy_version="P1",
            output_schema_version="S1",
            model_family="M1",
            episode_groups=(
                EpisodeBoundaryGroup("E1", ("A-1",), "first", 0.9),
                EpisodeBoundaryGroup("E2", ("A-1",), "second", 0.9),
            ),
            relations=(),
            assertion_dispositions=(
                AssertionDisposition("A-1", "core_of_episode", ("E1",), "first"),
            ),
            review_provenance={},
        )


def test_relation_evidence_cannot_replace_primary_assertion_disposition():
    assertions = [
        _with_claim(_assertion("A-1", passage="P-1"), "CLAIM-1"),
        _with_claim(_assertion("A-2", passage="P-2"), "CLAIM-2"),
    ]
    clusters = cluster_propositions(assertions)
    unit = build_review_units(clusters)[0]
    review = EpisodeBoundaryReviewResult(
        review_unit_ref=unit.review_unit_code,
        review_unit_cache_key=unit.cache_key,
        proposition_semantic_hashes=unit.proposition_semantic_hashes,
        boundary_policy_version=unit.boundary_policy_version,
        output_schema_version=unit.output_schema_version,
        model_family=unit.model_family,
        episode_groups=(
            EpisodeBoundaryGroup("E1", ("A-1",), "first", 0.9, "FIRST"),
            EpisodeBoundaryGroup("E2", ("A-2",), "second", 0.9, "SECOND"),
        ),
        relations=(
            EpisodeRelationDraft("E1", "E2", "outcome_of", ("A-2",), 0.9),
        ),
        assertion_dispositions=(
            AssertionDisposition("A-1", "core_of_episode", ("E1",), "first"),
        ),
        review_provenance={},
        pair_dispositions=(
            EpisodePairDisposition(
                "E1", "E2", "related", "结果对应首次行动", "outcome_of"
            ),
        ),
    )

    with pytest.raises(ValueError, match="主处置未完整覆盖"):
        review.validate_for_unit(
            unit, {item.proposition_code: item.assertion_refs for item in clusters}
        )


def test_materialization_preserves_context_unresolved_and_review_provenance():
    assertions = [
        _with_claim(
            _assertion(
                f"A-{index}", passage=f"P-{index}", time=f"贞观{index}年"
            ),
            f"CLAIM-{index}",
        )
        for index in range(1, 5)
    ]
    clusters = cluster_propositions(assertions)
    unit = build_review_units(clusters)[0]
    review = EpisodeBoundaryReviewResult(
        review_unit_ref=unit.review_unit_code,
        review_unit_cache_key=unit.cache_key,
        proposition_semantic_hashes=unit.proposition_semantic_hashes,
        boundary_policy_version=unit.boundary_policy_version,
        output_schema_version=unit.output_schema_version,
        model_family=unit.model_family,
        episode_groups=(
            EpisodeBoundaryGroup("E1", ("A-1",), "appointment", 0.9, "APPOINT"),
            EpisodeBoundaryGroup("E2", ("A-2",), "outcome", 0.9, "OUTCOME"),
        ),
        relations=(
            EpisodeRelationDraft("E1", "E2", "outcome_of", ("A-3",), 0.9),
        ),
        assertion_dispositions=(
            AssertionDisposition("A-1", "core_of_episode", ("E1",), "core"),
            AssertionDisposition("A-2", "core_of_episode", ("E2",), "core"),
            AssertionDisposition(
                "A-3", "context_for_episode", ("E1", "E2"), "shared context"
            ),
            AssertionDisposition(
                "A-4", "unresolved", (), "identity unresolved", "resolve person"
            ),
        ),
        review_provenance={"reviewer": "test-reviewer"},
        pair_dispositions=(
            EpisodePairDisposition(
                "E1", "E2", "related", "结果对应任命链", "outcome_of"
            ),
        ),
    )

    result = materialize_boundary_review(
        assertions,
        review,
        review_unit=unit,
        proposition_clusters=clusters,
    )

    assert result.context_assertion_links[0].assertion_ref == "A-3"
    assert result.unresolved_assertions[0].assertion_ref == "A-4"
    assert result.unresolved_assertions[0].follow_up == "resolve person"
    assert result.review_provenance["review_unit_cache_key"] == unit.cache_key


def test_clear_single_cluster_uses_zero_call_fast_path():
    assertion = _with_claim(
        _assertion(
            "A-1",
            passage="P-1",
            person="PER-LIJING",
            focal_person_ref="PER-LIJING",
            normalized_start=629,
        ),
        "CLAIM-1",
    )

    result = execute_boundary_reviews(
        [assertion],
        cache=InMemoryBoundaryReviewCache(),
        reviewer=lambda request: pytest.fail("clear unit must not call reviewer"),
    )

    assert result.model_call_count == 0
    assert len(result.deterministic_unit_codes) == 1
    assert result.review_results[0].review_provenance["route"] == (
        "deterministic_fast_path_v1"
    )


def test_per_unit_executor_caches_only_ambiguous_unit():
    assertions = [
        _with_claim(_assertion("A-1", passage="P-1"), "CLAIM-1"),
        _with_claim(_assertion("A-2", passage="P-2"), "CLAIM-2"),
    ]
    cache = InMemoryBoundaryReviewCache()

    def reviewer(request):
        unit = request.review_unit
        refs = request.assertion_refs
        return EpisodeBoundaryReviewResult(
            review_unit_ref=unit.review_unit_code,
            review_unit_cache_key=unit.cache_key,
            proposition_semantic_hashes=unit.proposition_semantic_hashes,
            boundary_policy_version=unit.boundary_policy_version,
            output_schema_version=unit.output_schema_version,
            model_family=unit.model_family,
            episode_groups=(
                EpisodeBoundaryGroup("E1", refs, "same event", 0.9, "SAME-EVENT"),
            ),
            relations=(),
            assertion_dispositions=tuple(
                AssertionDisposition(ref, "core_of_episode", ("E1",), "same event")
                for ref in refs
            ),
            review_provenance={"route": "reviewer"},
        )

    first = execute_boundary_reviews(assertions, cache=cache, reviewer=reviewer)
    second = execute_boundary_reviews(assertions, cache=cache, reviewer=None)

    assert first.model_call_count == 1
    assert second.model_call_count == 0
    assert second.cache_hit_unit_codes == first.model_called_unit_codes
    assert not second.pending_unit_codes

    stale = replace(
        first.review_results[0],
        proposition_semantic_hashes=("STALE",),
    )

    class StaleCache:
        def get(self, cache_key):
            return stale

        def put(self, cache_key, result):
            raise AssertionError("stale cache path must not write")

    with pytest.raises(ValueError, match="身份或版本不一致"):
        execute_boundary_reviews(assertions, cache=StaleCache(), reviewer=None)


def _formal_relation(code: str, source: str, target: str) -> EpisodeRelation:
    return EpisodeRelation(
        relation_id=code,
        from_episode_version_ref=source,
        to_episode_version_ref=target,
        relation_type="causal_followup",
        semantic_fingerprint=f"FP-{code}",
        semantic_version=1,
        evidence_version=1,
        relation_status="proposed",
        evidence_links=(),
        confidence=0.9,
        lineage={"origin": "created"},
        provenance={"builder": "test"},
    )


def test_relation_graph_rejects_temporal_cycle_and_cross_context():
    forward = _formal_relation("R1", "E1@v1", "E2@v1")
    backward = _formal_relation("R2", "E2@v1", "E1@v1")

    with pytest.raises(ValueError, match="不得形成环"):
        validate_episode_relation_graph(
            [forward, backward], {"E1@v1": "李世民", "E2@v1": "李世民"}
        )
    with pytest.raises(ValueError, match="不得跨 evaluation context"):
        validate_episode_relation_graph(
            [forward], {"E1@v1": "李世民", "E2@v1": "李治"}
        )


def test_same_structured_event_merges_across_source_wording():
    first = _assertion("A-1", passage="P-1", summary="命李靖出师")
    second = _assertion("A-2", passage="P-2", summary="以李靖为行军总管")

    groups = group_episode_candidates([first, second])

    assert len(groups) == 1
    assert {item.assertion_code for item in groups[0].assertions} == {"A-1", "A-2"}


@pytest.mark.parametrize(
    "changed",
    [
        {"ruler": "李治"},
        {"time": "贞观四年"},
        {"domain": "西方战区"},
        {"person": "侯君集"},
    ],
)
def test_context_time_responsibility_or_participant_change_splits(changed: dict):
    first = _assertion("A-1", passage="P-1")
    second = _assertion("A-2", passage="P-2", **changed)

    assert len(group_episode_candidates([first, second])) == 2


def test_new_authorization_action_splits_even_with_same_context_and_time():
    first = _assertion("A-1", passage="P-1")
    second = replace(_assertion("A-2", passage="P-2"), predicate="撤销授权")

    assert len(group_episode_candidates([first, second])) == 2


def test_cross_phase_chain_stays_split_when_responsibility_domains_do_not_overlap():
    appointment = _assertion(
        "A-1",
        passage="P-1",
        ruler="李治",
        person="苏定方",
        time="显庆二年",
        domain="伊丽道行军总管",
        summary="命苏定方讨沙钵罗可汗",
    )
    appointment = replace(
        appointment,
        predicate="任命",
        qualifiers={**appointment.qualifiers, "event_scope": "边疆"},
    )
    outcome = _assertion(
        "A-2",
        passage="P-2",
        ruler="李治",
        person="苏定方",
        time="显庆二年（657年）",
        domain="西突厥战事",
        summary="苏定方击败沙钵罗可汗",
    )
    outcome = replace(
        outcome,
        subject="苏定方",
        predicate="战役",
        object="沙钵罗可汗",
        qualifiers={**outcome.qualifiers, "event_scope": "边疆"},
    )

    groups = group_episode_candidates([appointment, outcome])

    assert len(groups) == 2


def test_same_source_topic_does_not_merge_distinct_regnal_year_tasks():
    first = replace(
        _assertion(
            "A-1",
            passage="P-1",
            ruler="李治",
            person="苏定方",
            time="显庆二年",
            domain="西域战事",
            summary="苏定方在西域作战",
        ),
        predicate="战役",
        source_attribution={"document_code": "D-1", "source_slice_ref": "S-SAME"},
    )
    second = replace(
        _assertion(
            "A-2",
            passage="P-2",
            ruler="李治",
            person="苏定方",
            time="显庆四年",
            domain="西域战事",
            summary="苏定方再次在西域作战",
        ),
        predicate="战役",
        source_attribution={"document_code": "D-1", "source_slice_ref": "S-SAME"},
    )

    assert len(group_episode_candidates([first, second])) == 2


def test_terminal_followup_does_not_merge_unrelated_earlier_appointment():
    appointment = _assertion(
        "A-1",
        passage="P-1",
        ruler="刘邦",
        person="萧何",
        time="至南郑时",
        domain="大将军任用",
        summary="萧何举荐韩信为大将",
    )
    followup = _assertion(
        "A-2",
        passage="P-2",
        ruler="刘邦",
        person="萧何",
        time="韩信被诛后",
        domain="相国封卫处置",
        summary="韩信被诛后萧何辞让封赏",
    )

    assert len(group_episode_candidates([appointment, followup])) == 2


def test_new_synonymous_evidence_does_not_change_episode_identity():
    first = _assertion("A-1", passage="P-1")
    second = _assertion("A-2", passage="P-2", summary="异源同义措辞")

    one = build_episode_packet(group_episode_candidates([first])[0])
    two = build_episode_packet(group_episode_candidates([first, second])[0])

    assert one.episode_id == two.episode_id
    assert one.semantic_fingerprint == two.semantic_fingerprint
    assert len(two.assertion_links) == 2


def test_conflicting_evidence_is_preserved_in_packet():
    support = _assertion("A-1", passage="P-1")
    dispute = replace(
        _assertion("A-2", passage="P-2", polarity="disputed"),
        qualifiers=support.qualifiers,
    )

    packet = build_episode_packet(group_episode_candidates([support, dispute])[0])

    assert packet.conflicts == ("A-2",)
    assert packet.completeness["conflict_resolution"] == "conflicted"
    assert {link.relation for link in packet.assertion_links} == {
        "supports",
        "contradicts",
    }


def test_accepted_episode_has_passage_lineage_and_slot_completeness():
    proposed = build_episode_packet(
        group_episode_candidates([_assertion("A-1", passage="P-1")])[0]
    )
    packet = replace(
        proposed,
        episode_status="accepted",
        evaluation_context="PER-LI-SHIMIN",
        participants=(
            EpisodeParticipant("PER-LI-SHIMIN", ("ruler",), "resolved"),
            EpisodeParticipant("PER-LI-JING", ("commander",), "resolved"),
        ),
        assertion_links=tuple(
            replace(link, evidence_status="accepted")
            for link in proposed.assertion_links
        ),
    )

    assert packet.assertion_links[0].source_passage_ref == "P-1"
    assert packet.completeness == {
        "identity": "complete",
        "time": "complete",
        "action": "complete",
        "responsibility": "complete",
        "outcome": "complete",
        "consequence": "not_applicable",
        "source_diversity": "partial",
        "conflict_resolution": "complete",
    }


@pytest.mark.parametrize(
    "change, message",
    [
        ({"evaluation_context": "李世民"}, "canonical person"),
        (
            {
                "participants": (
                    EpisodeParticipant("PER-LI-SHIMIN", ("ruler",), "unresolved"),
                )
            },
            "participant 必须全部 resolved",
        ),
    ],
)
def test_accepted_episode_rejects_unresolved_identity(change: dict, message: str):
    proposed = build_episode_packet(
        group_episode_candidates([_assertion("A-1", passage="P-1")])[0]
    )
    valid = replace(
        proposed,
        evaluation_context="PER-LI-SHIMIN",
        participants=(
            EpisodeParticipant("PER-LI-SHIMIN", ("ruler",), "resolved"),
        ),
        assertion_links=tuple(
            replace(link, evidence_status="accepted")
            for link in proposed.assertion_links
        ),
    )

    with pytest.raises(ValueError, match=message):
        replace(valid, episode_status="accepted", **change)


def test_accepted_episode_rejects_draft_evidence():
    proposed = build_episode_packet(
        group_episode_candidates([_assertion("A-1", passage="P-1")])[0]
    )

    with pytest.raises(ValueError, match="evidence 必须全部 accepted"):
        replace(
            proposed,
            episode_status="accepted",
            evaluation_context="PER-LI-SHIMIN",
            participants=(
                EpisodeParticipant("PER-LI-SHIMIN", ("ruler",), "resolved"),
            ),
        )


def test_accepted_episode_rejects_missing_completeness_slot():
    proposed = build_episode_packet(
        group_episode_candidates([_assertion("A-1", passage="P-1")])[0]
    )
    incomplete = dict(proposed.completeness)
    incomplete.pop("outcome")

    with pytest.raises(ValueError, match="completeness 缺少槽位"):
        replace(
            proposed,
            episode_status="accepted",
            evaluation_context="PER-LI-SHIMIN",
            participants=(
                EpisodeParticipant("PER-LI-SHIMIN", ("ruler",), "resolved"),
            ),
            assertion_links=tuple(
                replace(link, evidence_status="accepted")
                for link in proposed.assertion_links
            ),
            completeness=incomplete,
        )


def test_accepted_with_uncertainty_rejects_empty_uncertainty():
    proposed = build_episode_packet(
        group_episode_candidates([_assertion("A-1", passage="P-1")])[0]
    )

    with pytest.raises(ValueError, match="必须保留不确定性"):
        replace(
            proposed,
            episode_status="accepted_with_uncertainty",
            evaluation_context="PER-LI-SHIMIN",
            participants=(
                EpisodeParticipant("PER-LI-SHIMIN", ("ruler",), "resolved"),
            ),
            assertion_links=tuple(
                replace(link, evidence_status="accepted")
                for link in proposed.assertion_links
            ),
        )


def test_explicit_boundary_hint_merges_related_actions_without_using_summary_identity():
    appointment = _assertion("A-1", passage="P-1")
    outcome = replace(_assertion("A-2", passage="P-2"), predicate="奏捷反馈")

    groups = group_episode_candidates_with_hints(
        [appointment, outcome],
        {"A-1": "LIJING-DAIZHOU", "A-2": "LIJING-DAIZHOU"},
    )

    assert len(groups) == 1
    assert groups[0].boundary_hint == "LIJING-DAIZHOU"
    assert {item.assertion_code for item in groups[0].assertions} == {"A-1", "A-2"}


def test_gold_boundary_hint_does_not_change_semantic_fingerprint():
    first = _assertion("A-1", passage="P-1")
    second = _assertion("A-2", passage="P-2")

    groups = group_episode_candidates_with_hints(
        [first, second],
        {"A-1": "FIRST-AUTHORIZATION", "A-2": "SECOND-AUTHORIZATION"},
    )

    assert len(groups) == 2
    assert len({group.key.fingerprint for group in groups}) == 1


def test_hinted_packet_is_stable_under_assertion_input_order():
    appointment = _assertion("A-2", passage="P-2")
    outcome = replace(_assertion("A-1", passage="P-1"), predicate="奏捷反馈")
    hints = {"A-1": "LIJING-DAIZHOU", "A-2": "LIJING-DAIZHOU"}

    first = build_episode_packet(
        group_episode_candidates_with_hints([appointment, outcome], hints)[0]
    )
    second = build_episode_packet(
        group_episode_candidates_with_hints([outcome, appointment], hints)[0]
    )

    assert first.episode_id == second.episode_id
    assert first.semantic_fingerprint == second.semantic_fingerprint
    assert first.action == second.action == "任命统兵 | 奏捷反馈"
    assert first.assertion_links == second.assertion_links


def test_review_atomic_event_key_distinguishes_structurally_equal_episodes():
    first = _with_claim(_assertion("A-1", passage="P-1"), "CLAIM-1")
    second = _with_claim(_assertion("A-2", passage="P-2"), "CLAIM-2")
    hints = {"A-1": "E1", "A-2": "E2"}

    groups = group_episode_candidates_with_hints(
        [first, second], hints, {"E1": "ATOMIC-1", "E2": "ATOMIC-2"}
    )

    assert len(groups) == 2
    assert groups[0].key.fingerprint != groups[1].key.fingerprint


def test_boundary_hint_cannot_merge_across_rulers():
    first = _assertion("A-1", passage="P-1")
    second = _assertion("A-2", passage="P-2", ruler="李治")

    with pytest.raises(ValueError, match="跨 evaluation context"):
        group_episode_candidates_with_hints(
            [first, second],
            {"A-1": "SAME-HINT", "A-2": "SAME-HINT"},
        )
