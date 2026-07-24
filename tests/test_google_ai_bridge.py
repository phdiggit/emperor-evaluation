from __future__ import annotations

import bz2
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Mapping

import pytest
import yaml

from emperor_v4.adapters.source_cache_discovery import (
    has_subject_section,
    locate_lead_span,
    omission_has_distinctive_match,
)
from emperor_v4.adapters.hanchi_locator import (
    build_hanchi_batch_search_plan,
    build_hanchi_post_fields,
    build_hanchi_search_plan,
    execute_hanchi_batch_plan,
    HanchiPostTemplate,
    load_hanchi_curl_template,
    merge_hanchi_locator_hits,
    parse_hanchi_result_html,
    select_simple_recall_terms,
)
from emperor_v4.adapters.source_text_index import (
    LocalSourceTextIndex,
    build_local_recall_report,
    build_local_source_index,
    iter_wikisource_dump,
)
from emperor_v4.adapters.subject_mention_index import (
    build_first_review_worklist,
    build_shared_review_plan,
    build_subject_mention_index,
    build_subject_mention_report,
    build_identity_verified_passage_worklist,
    cluster_first_review_windows,
    refetch_first_review_worklist,
)
from emperor_v4.adapters.shared_neutral_extraction import (
    build_shared_neutral_extraction_prompt,
    build_shared_neutral_fact_fanout,
)
from emperor_v4.adapters.ruler_neutral_person_recall import (
    build_ruler_neutral_person_fanout,
    build_ruler_neutral_person_recall_plan,
)
from emperor_v4.adapters.person_lifecycle_scan import (
    build_person_lifecycle_fanout,
)
from emperor_v4.evaluation.i5b_source_review_decision import (
    merge_i5b_source_review_decisions,
)
from emperor_v4.application.discovery_source_backfill import (
    DEFAULT_I5B_SOURCE_SCOPE_PATH,
    WORKLIST_SCHEMA_VERSION,
    artifact_omission_gap,
    build_backfill_worklist,
    build_hanchi_policy_backfill_worklist,
    build_hanchi_policy_judge_worklist,
    build_i5b_ready_worklist,
    build_ready_person_worklists,
    load_i5b_source_search_scope,
    merge_hanchi_policy_judge_results,
    write_backfill_worklist,
)
from emperor_v4.adapters.wikisource import (
    WikisourcePageSnapshot,
    snapshot_from_revision_payload,
    snapshots_from_plaintext_batch_payload,
    snapshots_from_revision_batch_payload,
)
from emperor_v4.runtime.person_rebuild_shadow import (
    backfill_ready_people,
    backfill_person_worklist,
    build_person_shadow_candidate,
    claim_ready_sources,
    run_discovery_ready_pipeline,
    run_ready_pipeline,
)
from emperor_v4.infrastructure.google_ai_bridge import (
    GoogleAiBridgeError,
    GoogleAiTaskQueue,
    RESULT_SCHEMA_VERSION,
    _worker_bootstrap_url,
)
from emperor_v4.evaluation.i5b_source_review_quality_probe import (
    _validated_episode_scope,
    _validated_policy_review,
    _validated_profile_basis,
    build_i5b_source_review_quality_probe,
)
from emperor_v4.evaluation.i5b_source_review_projector import (
    apply_projection_results,
    build_projection_tasks,
)
from emperor_v4.application.google_ai_discovery_prompt import (
    build_i5b_discovery_manifest,
    load_discovery_prompt_policy,
)


def test_i5b_source_review_quality_probe_derives_numbers_from_policy(
    tmp_path: Path,
) -> None:
    passage_ref = "MENTIONPASSAGE-TEST"
    refetch = {
        "schema_version": "subject-mention-refetch-result-v1",
        "passages": [
                {
                    "passage_ref": passage_ref,
                    "status": "succeeded",
                    "lineage_status": "exact_revision_offset_match",
                    "subject_ref": "PER-TEST",
                    "raw_text": "测试臣受命任事，并取得成效。",
                }
        ],
    }
    event_inputs = {
        "talent_discovery": {
            "direction_sign": "positive",
            "discovery_level": "recommendation_entry",
            "talent_quality_factor": "important",
            "attribution_factor": "direct",
            "source_factor": "standard",
            "context_factor": "clear",
        },
        "appointment_delegation": {
            "appointment_importance": "major_affairs",
            "appointment_effect": "normal_success",
            "continuity_factor": "stable",
            "attribution_factor": "direct",
            "source_factor": "standard",
            "context_factor": "clear",
        },
        "tolerate_talent": {
            "feedback_entry": "single_acceptance_or_tolerance",
            "expression_safety": "basically_safe",
            "protection_repair": "none",
            "attribution_factor": "direct",
            "source_factor": "standard",
            "context_factor": "clear",
        },
        "anti_nepotism": {
            "selection_openness": "merit_or_formal_basis",
            "institutionalization": "single_event",
            "office_weight": "important",
            "attribution_factor": "direct",
            "source_factor": "standard",
            "context_factor": "clear",
        },
    }
    rules = {}
    for rule_code, option_codes in event_inputs.items():
        material_id = f"MAT-{rule_code}"
        rules[rule_code] = {
            "materials": [
                {
                    "material_id": material_id,
                    "subject": "测试臣",
                    "side": "positive",
                    "fact": "测试事实",
                    "episode_scope": {
                        "episode_ref": f"EP-{rule_code}",
                        "time_boundary": "测试帝在位期",
                        "action_boundary": "一次可区分行动",
                        "result_boundary": "该行动的直接结果",
                        **({"authorization_key": "AUTH-TEST"} if rule_code == "appointment_delegation" else {}),
                    },
                        "passage_refs": [passage_ref],
                        "subject_refs": ["PER-TEST"],
                        "factor_option_codes": option_codes,
                }
            ],
            "eligible": {
                "positive": [
                    {
                        "material_id": material_id,
                        "independence_key": f"test:{rule_code}",
                        "judge_reason": "测试通过",
                    }
                ],
                "negative": [],
            },
            "excluded": [],
        }
    rules["team_building"] = {
        "members": [
            {
                "person": "测试臣",
                "person_ref": "PER-TEST",
                "talent_grade": "important",
                "talent_grade_basis": "测试依据",
                "talent_profile_basis": {
                    "confidence": 0.8,
                    "authority_consensus": "moderate",
                    "performance_support": "moderate",
                    "evidence_coverage": "substantial",
                    "achievement_clusters": [
                        {"cluster_ref": "ACH-TEST", "summary": "完成测试职责", "passage_refs": [passage_ref]}
                    ],
                    "authority_evaluations": [
                        {"evaluation_ref": "AUTH-TEST", "summary": "评价其可以任事", "passage_refs": [passage_ref]}
                    ],
                },
                "political_risk": {
                    "assessment_status": "insufficient_evidence",
                    "severity": None,
                    "historical_reach": None,
                    "event_assessments": [],
                },
                "role_families": ["administration"],
                "passage_refs": [passage_ref],
            }
        ],
        "positive_members": ["测试臣"],
        "negative_members": [],
        "functional_complementarity": "homogeneous",
        "long_term_stability": "stable_window",
        "governance_results": ["测试治理成果"],
    }
    decision = {
        "schema_version": "i5b-source-review-quality-probe-v1",
        "task_code": "I5B-TEST",
        "ruler": "测试帝",
        "ruler_ref": "RULER-TEST",
        "window": "1-2",
        "policy": "config/i5b-scoring-policy.yml",
        "retrieved_person_refs": ["PER-TEST"],
        "rules": rules,
    }
    policy = yaml.safe_load(
        Path("config/i5b-scoring-policy.yml").read_text(encoding="utf-8")
    )

    report = build_i5b_source_review_quality_probe(
        decision,
        refetch=refetch,
        policy=policy,
        runtime_dir=tmp_path,
    )

    talent = next(
        row
        for row in report["material_report"]["rules"]
        if row["rule_code"] == "talent_discovery"
    )
    assert talent["settled_materials"][0]["factor_values"] == {
        "direction_sign": "1.000000",
        "discovery_level": "0.800000",
        "talent_quality_factor": "1.150000",
        "attribution_factor": "1.000000",
        "source_factor": "1.000000",
        "context_factor": "1.000000",
    }
    assert report["score_preview"]["formal_45_point_score"] is None
    assert report["score_preview"]["mapping_status"] == "blocked_pending_cross_ruler_snapshot"
    assert report["quality_declarations"]["factor_numeric_values_derived_from_policy"] is True
    team_rule = next(
        row
        for row in report["material_report"]["rules"]
        if row["rule_code"] == "team_building"
    )
    assert team_rule["governance_results"] == [{"result": "测试治理成果"}]

    member = decision["rules"]["team_building"]["members"][0]
    talent_profile_basis = member.pop("talent_profile_basis")
    with pytest.raises(ValueError, match="缺少结构化 talent_profile_basis"):
        build_i5b_source_review_quality_probe(
            decision,
            refetch=refetch,
            policy=policy,
            runtime_dir=tmp_path / "missing-talent-basis",
        )
    member["talent_profile_basis"] = talent_profile_basis

    political_risk = member["political_risk"]
    member["political_risk"] = {
        "assessment_status": "established",
        "severity": "major",
        "historical_reach": "national",
        "event_assessments": [
            {
                "event_ref": "RISK-ATTEMPT",
                "summary": "严重企图被制止",
                "realization": "attempted",
                "responsibility": "direct_execution",
                "passage_refs": [passage_ref],
            }
        ],
    }
    member["negative_talent_class"] = "state_subversion"
    member["negative_talent_severity"] = "major"
    with pytest.raises(ValueError, match="未实现风险不得定为 major"):
        build_i5b_source_review_quality_probe(
            decision,
            refetch=refetch,
            policy=policy,
            runtime_dir=tmp_path / "attempted-major",
        )
    member["political_risk"] = political_risk
    member["negative_talent_class"] = None
    member["negative_talent_severity"] = None

    appointment = decision["rules"]["appointment_delegation"]["materials"][0]
    appointment["factor_option_codes"]["continuity_factor"] = (
        "long_term_multi_stage"
    )
    with pytest.raises(ValueError, match="缺少投影事实观察"):
        build_i5b_source_review_quality_probe(
            decision,
            refetch=refetch,
            policy=policy,
            runtime_dir=tmp_path / "missing-observations",
        )

    second_passage_ref = "MENTIONPASSAGE-TEST-SECOND"
    refetch["passages"].append(
        {
            "passage_ref": second_passage_ref,
            "status": "succeeded",
            "lineage_status": "exact_revision_offset_match",
            "raw_text": "测试臣后来再次受命并取得结果。",
        }
    )
    appointment["passage_refs"] = [passage_ref, second_passage_ref]
    appointment["projection_observations"] = [
        {"fact": "首次授权并实际履职", "passage_refs": [passage_ref]},
        {"fact": "后续继续授权并取得结果", "passage_refs": [second_passage_ref]},
    ]
    multi_observation_report = build_i5b_source_review_quality_probe(
        decision,
        refetch=refetch,
        policy=policy,
        runtime_dir=tmp_path / "multi-observations",
    )
    appointment_rule = next(
        row
        for row in multi_observation_report["material_report"]["rules"]
        if row["rule_code"] == "appointment_delegation"
    )
    assert appointment_rule["settled_materials"][0]["fact"] == (
        "首次授权并实际履职；后续继续授权并取得结果。"
    )
    assert len(
        appointment_rule["settled_materials"][0]["projection_observations"]
    ) == 2

    decision["rules"]["talent_discovery"]["materials"][0]["passage_refs"] = [
        "MISSING"
    ]
    with pytest.raises(ValueError, match="不存在或未精确回源"):
        build_i5b_source_review_quality_probe(
            decision,
            refetch=refetch,
            policy=policy,
            runtime_dir=tmp_path / "invalid",
        )


def test_i5b_source_review_v2_separates_full_career_profile_and_ruler_episode() -> None:
    passage_ref = "MENTIONPASSAGE-CAREER"
    catalog = {passage_ref: {"raw_text": "测试臣完整生涯实绩"}}
    member = {
        "person_ref": "PER-TEST",
        "talent_grade": "top",
        "negative_talent_class": None,
        "negative_talent_severity": None,
        "talent_profile_basis": {
            "confidence": 0.9,
            "authority_consensus": "strong",
            "performance_support": "strong",
            "evidence_coverage": "comprehensive",
            "profile_scope": "full_career",
            "career_coverage": {
                "start_boundary": "入仕",
                "end_boundary": "卒年",
                "ruler_contexts_reviewed": ["甲帝", "乙帝"],
                "coverage_status": "complete",
                "major_phase_omissions": [],
            },
            "achievement_clusters": [
                {"cluster_ref": "ACH-TEST", "summary": "跨朝实绩", "passage_refs": [passage_ref]}
            ],
            "authority_evaluations": [
                {"evaluation_ref": "AUTH-TEST", "summary": "权威定评", "passage_refs": [passage_ref]}
            ],
        },
        "political_risk": {
            "assessment_status": "insufficient_evidence",
            "severity": None,
            "historical_reach": None,
            "event_assessments": [],
            "profile_scope": "full_career",
            "career_coverage_ref": "talent_profile_basis.career_coverage",
        },
    }
    profile, _ = _validated_profile_basis(
        member,
        passage_refs=[passage_ref],
        catalog=catalog,
        require_full_career_scope=True,
    )
    assert profile["career_coverage"]["ruler_contexts_reviewed"] == ["甲帝", "乙帝"]
    member["talent_profile_basis"]["career_coverage"]["major_phase_omissions"] = ["乙帝时期"]
    with pytest.raises(ValueError, match="comprehensive 不允许遗漏"):
        _validated_profile_basis(
            member,
            passage_refs=[passage_ref],
            catalog=catalog,
            require_full_career_scope=True,
        )

    material = {
        "material_id": "MAT-TEST",
        "episode_scope": {
            "episode_ref": "EP-TEST",
            "ruler_window": "3-4",
            "time_boundary": "乙帝时期",
            "action_boundary": "任命",
            "result_boundary": "成功",
        },
    }
    with pytest.raises(ValueError, match="episode 超出本皇帝窗口"):
        _validated_episode_scope(material, rule_code="talent_discovery", ruler_window="1-2")


def test_i5b_source_review_v2_requires_policy_exact_passage_disposition_closure() -> None:
    catalog = {
        "P1": {"subject_ref": "RULER-TEST", "subject_name": "测试帝政策"},
        "P2": {"subject_ref": "RULER-TEST", "subject_name": "测试帝政策"},
    }
    decision = {
        "ruler_ref": "RULER-TEST",
        "policy_review": {
            "candidate_reviews": [
                {
                    "candidate_ref": "POLICY-TEST-1",
                    "label": "测试政策",
                    "disposition": "counted",
                    "reason": "形成独立计分事件。",
                    "material_ids": ["MAT-POLICY"],
                }
            ],
            "dispositions": [{
                "review_ref": "COUNTED",
                "disposition": "counted",
                "passage_refs": ["P1"],
                "material_ids": ["MAT-POLICY"],
            }]
        },
    }
    with pytest.raises(ValueError, match="未闭合全部政策"):
        _validated_policy_review(
            decision, catalog=catalog, material_passage_refs={"MAT-POLICY": {"P1"}}
        )
    decision["policy_review"]["dispositions"].append(
        {
            "review_ref": "SUPPORTING",
            "disposition": "supporting",
            "passage_refs": ["P2"],
            "material_ids": [],
            "reason": "未形成独立 episode。",
        }
    )
    review = _validated_policy_review(
        decision, catalog=catalog, material_passage_refs={"MAT-POLICY": {"P1"}}
    )
    assert review["exact_policy_passage_count"] == 2
    assert review["candidate_reviews"][0]["reason"] == "形成独立计分事件。"


def test_i5b_source_review_quality_probe_rejects_retrieval_label_without_text_match(
    tmp_path: Path,
) -> None:
    passage_ref = "MENTIONPASSAGE-WRONG-SUBJECT"
    refetch = {
        "schema_version": "subject-mention-refetch-result-v1",
        "passages": [
            {
                "passage_ref": passage_ref,
                "status": "succeeded",
                "lineage_status": "exact_revision_offset_match",
                "subject_ref": "PER-MAZHOU",
                "subject_name": "马周",
                "raw_text": "杜如晦临机断事，时人称善。",
            }
        ],
    }
    empty_rule = {"materials": [], "eligible": {"positive": [], "negative": []}, "excluded": []}
    rules = {rule_code: dict(empty_rule) for rule_code in (
        "talent_discovery", "appointment_delegation", "tolerate_talent", "anti_nepotism"
    )}
    rules["talent_discovery"] = {
        "materials": [
            {
                "material_id": "MAT-MAZHOU",
                "subject": "马周",
                "side": "positive",
                "fact": "马周被发现",
                "episode_scope": {
                    "episode_ref": "EP-MAZHOU-DISCOVERY",
                    "time_boundary": "贞观初",
                    "action_boundary": "召见马周",
                    "result_boundary": "转化任用",
                },
                "passage_refs": [passage_ref],
                "subject_refs": ["PER-MAZHOU"],
                "factor_option_codes": {
                    "direction_sign": "positive",
                    "discovery_level": "recommendation_entry",
                    "talent_quality_factor": "important",
                    "attribution_factor": "direct",
                    "source_factor": "standard",
                    "context_factor": "clear",
                },
            }
        ],
        "eligible": {"positive": [{"material_id": "MAT-MAZHOU", "independence_key": "mazhou", "judge_reason": "test"}], "negative": []},
        "excluded": [],
    }
    rules["team_building"] = {
        "members": [
            {
                "person": "马周",
                "person_ref": "PER-MAZHOU",
                "talent_grade": "important",
                "talent_grade_basis": "测试",
                "talent_profile_basis": {
                    "confidence": 0.8,
                    "authority_consensus": "moderate",
                    "performance_support": "moderate",
                    "evidence_coverage": "partial",
                    "achievement_clusters": [
                        {"cluster_ref": "ACH-MAZHOU", "summary": "形成治理成果", "passage_refs": [passage_ref]}
                    ],
                    "authority_evaluations": [
                        {"evaluation_ref": "AUTH-MAZHOU", "summary": "评价其有治理能力", "passage_refs": [passage_ref]}
                    ],
                },
                "political_risk": {
                    "assessment_status": "insufficient_evidence",
                    "severity": None,
                    "historical_reach": None,
                    "event_assessments": [],
                },
                "role_families": ["administration"],
                "passage_refs": [passage_ref],
            }
        ],
        "positive_members": ["马周"],
        "negative_members": [],
        "functional_complementarity": "homogeneous",
        "long_term_stability": "stable_window",
    }
    decision = {
        "schema_version": "i5b-source-review-quality-probe-v1",
        "task_code": "I5B-WRONG-SUBJECT",
        "ruler": "唐太宗",
        "ruler_ref": "PER-LISHIMIN",
        "window": "626-649",
        "policy": "config/i5b-scoring-policy.yml",
        "retrieved_person_refs": ["PER-MAZHOU"],
        "rules": rules,
    }
    policy = yaml.safe_load(Path("config/i5b-scoring-policy.yml").read_text(encoding="utf-8"))

    with pytest.raises(ValueError, match="passage 正文未命中人物 PER-MAZHOU"):
        build_i5b_source_review_quality_probe(
            decision,
            refetch=refetch,
            policy=policy,
            runtime_dir=tmp_path,
        )


def test_identity_verified_worklist_uses_text_match_and_carries_variants() -> None:
    result = build_identity_verified_passage_worklist(
        {
            "people": [
                {
                    "person_ref": "PER-MAZHOU",
                    "subject_name": "马周",
                    "recall_terms": ["马周"],
                }
            ]
        },
        {
            "schema_version": "subject-mention-refetch-result-v1",
            "passages": [
                {
                    "passage_ref": "PASSAGE-WRONG",
                    "status": "shadow_source_passage",
                    "lineage_status": "exact_revision_offset_match",
                    "subject_ref": "PER-MAZHOU",
                    "page_title": "旧唐书/卷66",
                    "revision_ref": "1",
                    "start_offset": 0,
                    "end_offset": 10,
                    "raw_text": "杜如晦善断。",
                },
                {
                    "passage_ref": "PASSAGE-RIGHT",
                    "status": "shadow_source_passage",
                    "lineage_status": "exact_revision_offset_match",
                    "subject_ref": "PER-OTHER",
                    "page_title": "旧唐书/卷74",
                    "revision_ref": "2",
                    "start_offset": 20,
                    "end_offset": 40,
                    "raw_text": "常何荐馬周，帝召见之。",
                },
            ],
        },
    )

    person = result["people"][0]
    assert person["passage_count"] == 1
    assert person["passages"][0]["passage_ref"] == "PASSAGE-RIGHT"
    assert "馬周" in person["surface_forms"]


def test_i5b_source_review_projection_uses_subject_section_and_fails_closed(
    tmp_path: Path,
) -> None:
    cache_path = tmp_path / "source-page.json"
    raw_text = (
        "==他人==\n\n无关内容。\n\n"
        "==测试臣==\n\n测试臣早期受任并实际履职。\n\n"
        "测试臣后来再次受命并取得结果。\n\n"
        "==下一人==\n\n不得混入。\n"
    )
    cache_path.write_text(
        json.dumps({"raw_text": raw_text}, ensure_ascii=False), encoding="utf-8"
    )
    decision = {
        "ruler": "测试帝",
        "ruler_ref": "RULER-TEST",
        "rules": {
            "appointment_delegation": {
                "materials": [
                    {
                        "material_id": "MAT-TEST",
                        "subject": "测试臣连续责任",
                        "object_ref": "PER-TEST",
                        "fact": "旧摘要",
                        "passage_refs": ["PASSAGE-TEST"],
                        "factor_option_codes": {
                            "continuity_factor": "stable"
                        },
                    }
                ]
            }
        },
    }
    refetch = {
        "passages": [
            {
                "passage_ref": "PASSAGE-TEST",
                "subject_ref": "PER-TEST",
                "subject_name": "测试臣",
                "raw_text": "测试臣后来再次受命并取得结果。",
            }
        ],
        "source_pages": [
            {
                "page_title": "测试书/卷1",
                "revision_ref": "1",
                "revision_timestamp": "2026-01-01T00:00:00Z",
                "source_url": "https://example.test/1",
                "subject_refs": ["PER-TEST"],
                "cache_path": str(cache_path),
            }
        ],
    }

    tasks, chunks = build_projection_tasks(decision, refetch)

    assert len(tasks) == 1
    assert len(chunks) == 2
    assert all("不得混入" not in row["raw_text"] for row in chunks.values())
    task = tasks[0]
    chunk_refs = [row["passage_ref"] for row in task["source_chunks"]]
    incomplete = {
        "material_id": "MAT-TEST",
        "status": "succeeded",
        "payload": {
            "coverage_complete": False,
            "coverage_gaps": ["仍缺结果"],
            "observations": [
                {
                    "observation_code": "O1",
                    "observation_type": "authorization",
                    "authorization_key": "first",
                    "effect_support": "positive",
                    "fact": "测试臣早期受任",
                    "source_chunk_refs": [chunk_refs[0]],
                    "disposition": "counted",
                    "reason": "直接任用",
                }
            ],
        },
    }
    unchanged = apply_projection_results(decision, results=[incomplete])
    material = unchanged["rules"]["appointment_delegation"]["materials"][0]
    assert material["fact"] == "旧摘要"
    assert material["passage_refs"] == ["PASSAGE-TEST"]
    assert material["projection_coverage"]["coverage_complete"] is False

    complete = json.loads(json.dumps(incomplete, ensure_ascii=False))
    complete["payload"]["coverage_complete"] = True
    complete["payload"]["coverage_gaps"] = []
    complete["payload"]["observations"].append(
        {
            "observation_code": "O2",
            "observation_type": "authorization",
            "authorization_key": "second",
            "effect_support": "positive",
            "fact": "测试臣后来再次受命",
            "source_chunk_refs": [chunk_refs[1]],
            "disposition": "counted",
            "reason": "第二次直接任用",
        }
    )
    updated = apply_projection_results(decision, results=[complete])
    material = updated["rules"]["appointment_delegation"]["materials"][0]
    assert material["passage_refs"] == ["PASSAGE-TEST"]
    assert material["factor_option_codes"]["continuity_factor"] == "stable"
    assert [
        row["authorization_key"] for row in material["atomic_authorization_candidates"]
    ] == ["first", "second"]
    assert material["atomic_judge_required"] is True

    advice_without_effect = json.loads(json.dumps(complete, ensure_ascii=False))
    advice_without_effect["payload"]["observations"].append(
        {
            "observation_code": "O3",
            "observation_type": "policy_advice",
            "authorization_key": "first",
            "effect_support": "not_established",
            "fact": "测试臣另有政策建议，但效果未建立",
            "source_chunk_refs": [chunk_refs[0]],
            "disposition": "counted",
            "reason": "与既有职务有关",
        }
    )
    advice_without_effect_updated = apply_projection_results(
        decision, results=[advice_without_effect]
    )
    advice_without_effect_material = advice_without_effect_updated["rules"][
        "appointment_delegation"
    ]["materials"][0]
    assert len(advice_without_effect_material["atomic_authorization_candidates"]) == 2
    assert advice_without_effect_material["projection_coverage"][
        "supporting_observations"
    ][0]["observation_code"] == "O3"

    advice_only = json.loads(json.dumps(complete, ensure_ascii=False))
    advice_only["payload"]["observations"] = [
        {
            "observation_code": "O3",
            "observation_type": "policy_advice",
            "authorization_key": "invented_consultation_key",
            "effect_support": "positive",
            "fact": "测试臣提出建议后政策见效",
            "source_chunk_refs": [chunk_refs[0]],
            "disposition": "counted",
            "reason": "被咨询并进言",
        }
    ]
    advice_updated = apply_projection_results(decision, results=[advice_only])
    advice_material = advice_updated["rules"]["appointment_delegation"]["materials"][0]
    assert advice_material["fact"] == "旧摘要"
    assert advice_material["projection_coverage"]["suggested_counted_observations"] == []
    assert advice_material["projection_coverage"]["supporting_observations"][0][
        "disposition"
    ] == "supporting"


def test_i5b_source_review_projection_expands_window_to_complete_paragraph(
    tmp_path: Path,
) -> None:
    cache_path = tmp_path / "source-page.json"
    raw_text = (
        "==刑法志==\n\n"
        "前帝命群才修律，历年修成并颁行天下。\n\n"
        "及测试帝即位，奉命修律，先行断趾。后来复议，乃除断趾法，改为加役流。\n\n"
        "下一段不得混入。\n"
    )
    window_start = raw_text.index("前帝命群才") + 8
    window_end = raw_text.index("改为加役流") - 2
    selected_text = raw_text[window_start:window_end]
    start = window_start
    end = window_end
    cache_path.write_text(
        json.dumps({"raw_text": raw_text}, ensure_ascii=False), encoding="utf-8"
    )
    decision = {
        "ruler": "测试帝",
        "ruler_ref": "RULER-TEST",
        "rules": {
            "appointment_delegation": {
                "materials": [
                    {
                        "material_id": "MAT-LAW",
                        "subject": "修律责任群体",
                        "object_ref": "GROUP-LAW",
                        "fact": "旧摘要",
                        "passage_refs": ["PASSAGE-LAW"],
                        "factor_option_codes": {"continuity_factor": "stable"},
                    }
                ]
            }
        },
    }
    refetch = {
        "passages": [
            {
                "passage_ref": "PASSAGE-LAW",
                "subject_ref": "GROUP-LAW",
                "subject_name": "修律责任群体",
                "page_title": "测试书/刑法志",
                "revision_ref": "1",
                "start_offset": start,
                "end_offset": end,
                "raw_text": selected_text,
            }
        ],
        "source_pages": [
            {
                "page_title": "测试书/刑法志",
                "revision_ref": "1",
                "revision_timestamp": "2026-01-01T00:00:00Z",
                "source_url": "https://example.test/law",
                "subject_refs": ["GROUP-LAW"],
                "cache_path": str(cache_path),
            }
        ],
    }

    tasks, chunks = build_projection_tasks(decision, refetch)

    assert len(tasks) == 1
    assert tasks[0]["source_scope_status"] == "complete_cached_passage_paragraphs"
    assert len(chunks) == 1
    chunk = next(iter(chunks.values()))
    assert chunk["raw_text"] == (
        "及测试帝即位，奉命修律，先行断趾。后来复议，乃除断趾法，改为加役流。"
    )
    assert "前帝命群才" not in chunk["raw_text"]
    assert "下一段不得混入" not in chunk["raw_text"]
    assert raw_text[chunk["start_offset"] : chunk["end_offset"]] == chunk["raw_text"]
    assert chunk["content_hash"] == sha256(chunk["raw_text"].encode("utf-8")).hexdigest()


def test_omission_sweep_requires_a_distinctive_anchor() -> None:
    omitted = "贞观九年李靖奉命击破吐谷浑、平定西域领土的重大成就"

    assert not omission_has_distinctive_match(
        ("击破", "平定", "李靖"),
        omitted_lead=omitted,
        subject_name="李靖",
    )
    assert omission_has_distinctive_match(
        ("击破", "吐谷浑"),
        omitted_lead=omitted,
        subject_name="李靖",
    )
    assert not has_subject_section("颉利将奔吐谷浑。", "李靖")
    assert has_subject_section("== 李靖 ==\n靖西定吐谷浑。", "李靖")
    located = locate_lead_span(
        "== 李靖 ==\n李靖传。吐谷浑寇边，靖决计而进。",
        {"lead": omitted, "subject_action": "", "observable_result": ""},
        subject_name="李靖",
        include_subject_term=False,
        terms_override=("吐谷浑",),
    )
    assert located is not None
    assert "吐谷浑" in located[2]


def test_local_text_index_discovers_volume_from_book_and_lead_terms(
    tmp_path: Path,
) -> None:
    index_path = tmp_path / "tang-books.sqlite3"
    result = build_local_source_index(
        [
            {
                "page_title": "舊唐書/卷65",
                "work_title": "舊唐書",
                "source_url": "https://zh.wikisource.org/wiki/舊唐書/卷65",
                "revision_ref": "65",
                "raw_text": "房玄齡早年事跡，未涉及律令。",
            },
            {
                "page_title": "舊唐書/卷50",
                "work_title": "舊唐書",
                "source_url": "https://zh.wikisource.org/wiki/舊唐書/卷50",
                "revision_ref": "50",
                "raw_text": "長孫無忌與房玄齡奉詔修定律令，頒行天下。",
            },
        ],
        index_path,
    )

    index = LocalSourceTextIndex(index_path)
    hits = index.search(
        works=("旧唐书",),
        terms=("房玄龄", "长孙无忌", "修定律令"),
        limit=2,
    )

    assert result["page_count"] == 2
    assert index.identity == result["index_identity"]
    assert hits[0].page_title == "舊唐書/卷50"
    assert "修定律令" in hits[0].matched_terms


def test_hanchi_simple_recall_uses_the_widest_non_redundant_surface_form() -> None:
    assert select_simple_recall_terms({"房玄龄": 121, "玄龄": 156}) == ("玄龄",)
    assert select_simple_recall_terms({"李靖": 84, "靖": 4000, "药师": 0, "卫国公": 0}) == (
        "李靖",
    )
    assert select_simple_recall_terms({"太宗": 993, "李世民": 6}) == (
        "太宗",
        "李世民",
    )
    assert select_simple_recall_terms({"魏徵": 31, "魏征": 31}) == ("魏徵",)


def test_hanchi_priority_search_never_filters_the_simple_recall_pool() -> None:
    plan = build_hanchi_search_plan(
        subject_name="房玄龄",
        observed_simple_hits={"房玄龄": 121, "玄龄": 156},
        dynasty_scope="隋唐五代",
        broad_topics=("律令",),
        professional_anchors=(),
    )

    assert plan["simple_recall_terms"] == ["玄龄"]
    assert [query["mode"] for query in plan["queries"]] == ["simple", "advanced"]
    assert not any(query["mode"] == "professional" for query in plan["queries"])
    assert plan["merge_policy"]["simple_hits"] == "mandatory_and_never_filtered"
    assert plan["execution_policy"] == {
        "order": ["simple", "advanced", "professional"],
        "batch_by_mode": True,
        "concurrency": 1,
        "reuse_returned_form_state": True,
    }

    merged = merge_hanchi_locator_hits(
        (
            {
                "locator_key": "旧唐书/卷50/段1",
                "mode": "simple",
                "query": "玄龄",
            },
            {
                "locator_key": "旧唐书/卷66/段2",
                "mode": "simple",
                "query": "玄龄",
            },
            {
                "locator_key": "旧唐书/卷50/段1",
                "mode": "advanced",
                "query": "玄龄 AND 律令",
            },
        )
    )

    assert [row["locator_key"] for row in merged] == [
        "旧唐书/卷50/段1",
        "旧唐书/卷66/段2",
    ]
    assert merged[0]["priority_tier"] == "advanced"
    assert merged[1]["matched_modes"] == ["simple"]
    assert merged[1]["recall_origin"] == "simple"


def test_hanchi_professional_query_requires_an_explicit_attested_anchor() -> None:
    plan = build_hanchi_search_plan(
        subject_name="李靖",
        observed_simple_hits={"李靖": 84, "药师": 0, "卫国公": 0},
        dynasty_scope="隋唐五代",
        broad_topics=("军事治理",),
        professional_anchors=("突厥",),
    )

    professional = [query for query in plan["queries"] if query["mode"] == "professional"]
    assert professional == [
        {
            "mode": "professional",
            "subject_term": "李靖",
            "dynasty_scope": "隋唐五代",
            "result_role": "priority_only",
            "topic_term": "突厥",
            "distance_lower": 1,
            "distance_upper": 20,
            "variant_search": True,
        }
    ]


def test_hanchi_batch_caps_people_at_twelve_and_keeps_policy_separate() -> None:
    plan = build_hanchi_batch_search_plan(
        ruler="唐太宗",
        dynasty_scope="隋唐五代",
        people=tuple(
            {
                "person_ref": f"PER-{index:02d}",
                "subject_name": f"文臣{index:02d}",
            }
            for index in range(1, 15)
        ),
        policy_entries=(
            {
                "entry_ref": "POLICY-TAIZONG",
                "subject_name": "太宗",
                "recall_terms": ["太宗"],
            },
        ),
    )

    assert plan["selected_person_count"] == 12
    assert len([row for row in plan["entries"] if row["entry_kind"] == "person"]) == 12
    assert len([row for row in plan["entries"] if row["entry_kind"] == "policy"]) == 1
    assert [row["person_ref"] for row in plan["deferred_people"]] == [
        "PER-13",
        "PER-14",
    ]
    assert all(row["mode"] == "simple" for row in plan["queries"])
    assert plan["execution_policy"]["concurrency"] == 1
    assert plan["execution_policy"]["persist_cookies"] is False

    with pytest.raises(ValueError, match="1至12"):
        build_hanchi_batch_search_plan(
            ruler="唐太宗",
            dynasty_scope="隋唐五代",
            people=(),
            max_person_entries=13,
        )


def test_hanchi_curl_capture_becomes_runtime_post_template_without_cookie(
    tmp_path: Path,
) -> None:
    capture = tmp_path / "hanchi-curl.txt"
    capture.write_text(
        "curl 'https://hanchi.ihp.sinica.edu.tw/ihpc/hanjiquery?@@123' "
        "-H 'Cookie: never-persist=this' -H 'User-Agent: fixture' "
        "--data-raw '_TTS_CONTROL=runtime-only&XX.1.0.0.0.T=old&"
        "XX.1.1.0.0.T=old-topic&DY.0.2.9.3.S=on&_IMG_搜尋.x=1'",
        encoding="utf-8",
    )

    template = load_hanchi_curl_template(capture)
    fields = dict(
        build_hanchi_post_fields(
            template,
            {
                "mode": "simple",
                "subject_term": "玄龄",
                "dynasty_scope": "隋唐五代",
                "variant_search": True,
            },
        )
    )

    assert all(name.lower() != "cookie" for name, _value in template.headers)
    assert fields["_TTS_CONTROL"] == "runtime-only"
    assert fields["XX.0.0.0.0.T"] == "玄龄"
    assert fields["DY.0.2.9.3.S"] == "on"
    assert not any(name.startswith("XX.1.") for name in fields)


def test_hanchi_professional_post_uses_verified_two_term_distance_fields() -> None:
    template = HanchiPostTemplate(
        url="https://hanchi.ihp.sinica.edu.tw/ihpc/hanjiquery?@@123",
        headers=(),
        form_fields=(("_TTS_CONTROL", "runtime-only"),),
    )

    fields = dict(
        build_hanchi_post_fields(
            template,
            {
                "mode": "professional",
                "subject_term": "李靖",
                "topic_term": "突厥",
                "distance_lower": 1,
                "distance_upper": 20,
                "dynasty_scope": "隋唐五代",
            },
        )
    )

    assert fields["XX.1.0.0.0.T"] == "李靖"
    assert fields["XX.1.1.0.0.T"] == "突厥"
    assert fields["XX.1.4.0.4.T"] == "1"
    assert fields["XX.1.5.0.4.T"] == "20"
    advanced = dict(
        build_hanchi_post_fields(
            template,
            {
                "mode": "advanced",
                "subject_term": "李靖",
                "topic_term": "军事",
                "dynasty_scope": "隋唐五代",
            },
        )
    )
    assert advanced["_TTS_SBT0"] == "李靖"
    assert advanced["_TTS.SBC1"] == "AND"
    assert advanced["_TTS.SBT1"] == "军事"
    assert advanced["_TTS.SBF1"] == "TX"


def test_hanchi_html_parser_filters_locator_books_before_backfill() -> None:
    parsed = parse_hanchi_result_html(
        "<p>共計 3本書, 8個章節 12筆 (玄龄)</p>"
        "<a href='hanjiquery?book=1'>舊唐書 卷六十六</a>"
        "<a href='hanjiquery?book=2'>宋史 卷一</a>",
        allowed_books=("旧唐书", "新唐书"),
    )

    assert parsed["book_count"] == 3
    assert parsed["chapter_count"] == 8
    assert parsed["hit_count"] == 12
    assert len(parsed["locator_hits"]) == 1
    assert parsed["locator_hits"][0]["locator"]["title"] == "旧唐书"
    assert parsed["locator_hits"][0]["locator"]["source_work"] == "旧唐书"


def test_hanchi_html_parser_rejects_unscoped_page_number_as_hit_count() -> None:
    parsed = parse_hanchi_result_html(
        "<form><p>一般說明 1106筆 (不是本次結果摘要)</p></form>"
    )

    assert parsed == {
        "book_count": None,
        "chapter_count": None,
        "hit_count": None,
        "locator_hits": [],
    }


def test_hanchi_returned_form_state_keeps_only_successful_controls() -> None:
    from emperor_v4.adapters.hanchi_locator import _hanchi_form_fields

    fields = _hanchi_form_fields(
        "<input type='hidden' name='_TTS_CONTROL' value='fresh'>"
        "<input type='text' name='XX.1.0.0.0.T' value='太宗'>"
        "<input type='checkbox' name='DY.0.2.9.3.S' value='on' checked>"
        "<input type='checkbox' name='DY.0.2.12.3.S' value='on'>"
        "<input type='image' name='_IMG_搜尋' value='搜尋'>"
    )

    assert fields == {
        "_TTS_CONTROL": "fresh",
        "XX.1.0.0.0.T": "太宗",
        "DY.0.2.9.3.S": "on",
    }


def test_hanchi_validated_empty_professional_response_is_a_zero_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import emperor_v4.adapters.hanchi_locator as hanchi

    html = (
        "<form action='hanjiquery?@@next'>"
        "<input type='hidden' name='_TTS_ACTION' value='111'>"
        "<input type='hidden' name='_TTS_CONTROL' value='fresh'>"
        "<input type='hidden' name='@XX.1.0.0.0.T' value='1'>"
        "<input type='text' name='XX.1.0.0.0.T' value='太宗'>"
        "<input type='hidden' name='@XX.1.1.0.0.T' value='1'>"
        "<input type='text' name='XX.1.1.0.0.T' value='裁并'>"
        "<input type='image' name='_IMG_搜尋'>"
        "</form>"
    )
    monkeypatch.setattr(hanchi, "_post_hanchi_fields", lambda *_args, **_kwargs: html)
    template = HanchiPostTemplate(
        url="https://hanchi.ihp.sinica.edu.tw/ihpc/hanjiquery?@@current",
        headers=(),
        form_fields=(
            ("_TTS_ACTION", "111"),
            ("_TTS_CONTROL", "current"),
            ("XX.1.0.0.0.T", "太宗"),
        ),
    )

    result = hanchi.submit_hanchi_post_query(
        template,
        {
            "mode": "professional",
            "subject_term": "太宗",
            "topic_term": "裁并",
            "dynasty_scope": "隋唐五代",
        },
        form_state={
            "mode": "professional",
            "url": template.url,
            "fields": dict(template.form_fields),
        },
    )

    assert result["hit_count"] == 0
    assert result["result_status"] == "completed_no_match"
    assert result["zero_result_basis"] == "validated_echo_mode_action_and_controls"


def test_hanchi_batch_executor_is_serial_and_never_persists_session_state() -> None:
    plan = build_hanchi_batch_search_plan(
        ruler="唐太宗",
        dynasty_scope="隋唐五代",
        people=(
            {"person_ref": "PER-FANG", "subject_name": "房玄龄"},
            {"person_ref": "PER-LI", "subject_name": "李靖"},
        ),
    )
    calls = []

    def submit(query: Mapping[str, object], state: Mapping[str, object]) -> Mapping[str, object]:
        calls.append((query["entry_ref"], dict(state)))
        return {
            "hits": [
                {
                    "locator_key": f"旧唐书/{query['entry_ref']}",
                    "locator": {"title": str(query["entry_ref"])},
                }
            ],
            "form_state": {"step": len(calls)},
        }

    result = execute_hanchi_batch_plan(plan, submit_query=submit)

    assert [entry_ref for entry_ref, _state in calls] == ["PER-FANG", "PER-LI"]
    assert calls[0][1] == {}
    assert calls[1][1] == {"step": 1}
    assert result["request_count"] == 2
    assert result["transport_declarations"]["cookies_persisted"] is False
    assert "form_state" not in result


def test_hanchi_policy_candidate_lineage_reaches_parallel_judge_pack() -> None:
    candidate_ref = "POLICY-LSM-GOVERNOR-SCREEN"
    plan = build_hanchi_batch_search_plan(
        ruler="李世民",
        dynasty_scope="隋唐五代",
        people=(),
        policy_entries=(
            {
                "entry_ref": candidate_ref,
                "candidate_ref": candidate_ref,
                "candidate_summary": "刺史屏风记功并据以赏罚",
                "subject_name": "太宗",
                "recall_terms": ["太宗"],
                "professional_anchors": ["屏风"],
                "source_recall_terms": ["屏风", "刺史姓名", "得失皆注"],
                "allowed_books": ["贞观政要", "资治通鉴"],
                "target_rule_hints": ["anti_nepotism"],
            },
        ),
    )
    policy_entry = plan["entries"][0]
    assert policy_entry["candidate_ref"] == candidate_ref
    assert [row["mode"] for row in plan["queries"]] == ["simple", "professional"]

    def submit(query: Mapping[str, object], _state: Mapping[str, object]):
        return {
            "hits": [
                {
                    "locator_key": "hanchi-title:zgzy",
                    "locator": {
                        "title": "贞观政要 卷三择官",
                        "source_work": "贞观政要",
                        "resolution": "independent_source_backfill",
                    },
                }
            ],
            "form_state": {},
        }

    hanchi_result = execute_hanchi_batch_plan(plan, submit_query=submit)
    assert hanchi_result["transport_declarations"]["google_used_for_retrieval"] is False
    backfill = build_hanchi_policy_backfill_worklist(
        hanchi_plan=plan,
        hanchi_result=hanchi_result,
        ruler_ref="RULER-LSM",
        ruler_name="李世民",
    )
    assert backfill["hanchi_policy_lineage"]["candidate_count"] == 1
    assert backfill["i5b_selection"] == {
        "ruler_ref": "RULER-LSM",
        "ruler_name": "李世民",
        "civil_discovery_lead_limit": 0,
        "ruler_policy_lead_limit": None,
        "policy_stop_condition": "candidate_disposition_closed",
        "deferred_discovery_leads": [],
        "formal_write_allowed": False,
        "database_write_allowed": False,
    }
    assert backfill["tasks"][0]["hanchi_lineage"]["candidate_ref"] == candidate_ref
    assert backfill["tasks"][0]["discovery_input_version"] == (
        "hanchi-locator-batch-result-v1"
    )
    assert len(backfill["tasks"][0]["discovery_input_fingerprint"]) == 64
    assert backfill["tasks"][0]["discovery_captured_at"] == (
        "not_recorded:hanchi_post_batch"
    )
    assert backfill["tasks"][0]["period_or_ruler_context"] == "李世民（太宗）"
    assert backfill["tasks"][0]["source_recall_terms"] == [
        "屏风",
        "刺史姓名",
        "得失皆注",
    ]
    assert backfill["source_batches"][0]["leads"][0]["hanchi_lineage"][
        "retrieval_route"
    ] == "hanchi_post"

    source_report = {
        "response": {
            "passages": [
                {
                    "passage_id": "PASSAGE-SCREEN",
                    "raw_text": "太宗以刺史姓名书于屏风，坐卧观之，得失皆注于名下。",
                    "selection_reason": [
                        "discovery_source_backfill",
                        f"{candidate_ref}:H1",
                    ],
                    "lineage_status": "exact_revision_offset_match",
                }
            ]
        }
    }
    judge_worklist = build_hanchi_policy_judge_worklist(
        backfill, source_reports=[source_report], max_concurrency=3
    )
    assert judge_worklist["execution_policy"]["parallelizable"] is True
    assert judge_worklist["execution_policy"]["main_session_semantic_rejudge_required"] is False
    assert [row["candidate_ref"] for row in judge_worklist["tasks"]] == [candidate_ref]

    review_pack = merge_hanchi_policy_judge_results(
        judge_worklist,
        [
            {
                "schema_version": "i5b-hanchi-policy-judge-result-v1",
                "task_code": f"{candidate_ref}-JUDGE",
                "candidate_ref": candidate_ref,
                "disposition": "counted",
                "judge_reason": "原文具备皇帝归责、考课行动和可观察记录机制。",
                "target_rule": "anti_nepotism",
                "passage_refs": ["PASSAGE-SCREEN"],
                "episode": {
                    "time_boundary": "贞观时期",
                    "ruler_attribution": "李世民直接推行",
                    "action_boundary": "记录刺史政绩",
                    "result_boundary": "政绩得失持续记入屏风",
                },
                "factor_option_codes": {
                    "selection_openness": "merit_or_formal_basis",
                    "institutionalization": "repeated_stable_practice",
                },
            }
        ],
    )
    assert review_pack["status"] == "acceptance_ready_shadow_policy_review"
    assert review_pack["declarations"]["google_used_for_retrieval"] is False
    assert review_pack["candidate_reviews"][0]["disposition"] == "counted"


def test_hanchi_policy_candidate_without_filtered_locator_closes_as_gap() -> None:
    plan = build_hanchi_batch_search_plan(
        ruler="李世民",
        dynasty_scope="隋唐五代",
        people=(),
        policy_entries=(
            {
                "entry_ref": "POLICY-NO-HIT",
                "candidate_ref": "POLICY-NO-HIT",
                "candidate_summary": "待核政策",
                "subject_name": "太宗",
                "recall_terms": ["太宗"],
                "broad_topics": ["待核政策"],
                "allowed_books": ["旧唐书"],
            },
        ),
    )
    result = execute_hanchi_batch_plan(
        plan,
        submit_query=lambda _query, _state: {"hits": [], "form_state": {}},
    )
    backfill = build_hanchi_policy_backfill_worklist(
        hanchi_plan=plan,
        hanchi_result=result,
        ruler_ref="RULER-LSM",
        ruler_name="李世民",
    )
    judge = build_hanchi_policy_judge_worklist(backfill, source_reports=[])
    assert judge["tasks"] == []
    assert judge["automatic_gaps"] == [
        {
            "candidate_ref": "POLICY-NO-HIT",
            "disposition": "insufficient",
            "reason": "no_filtered_hanchi_locator",
        }
    ]
    pack = merge_hanchi_policy_judge_results(judge, [])
    assert pack["declarations"]["candidate_disposition_closed"] is True


def test_hanchi_reuses_identical_simple_policy_query_across_candidates() -> None:
    common = {
        "subject_name": "太宗",
        "recall_terms": ["太宗"],
        "allowed_books": ["贞观政要"],
    }
    plan = build_hanchi_batch_search_plan(
        ruler="李世民",
        dynasty_scope="隋唐五代",
        people=(),
        policy_entries=(
            common
            | {
                "entry_ref": "POLICY-A",
                "candidate_ref": "POLICY-A",
                "candidate_summary": "政策甲",
                "professional_anchors": ["屏风"],
            },
            common
            | {
                "entry_ref": "POLICY-B",
                "candidate_ref": "POLICY-B",
                "candidate_summary": "政策乙",
                "professional_anchors": ["四考"],
            },
        ),
    )
    calls = []

    def submit(query: Mapping[str, object], _state: Mapping[str, object]):
        calls.append((query["mode"], query.get("topic_term")))
        return {"hits": [], "form_state": {}}

    result = execute_hanchi_batch_plan(plan, submit_query=submit)
    assert calls == [("simple", None), ("professional", "屏风"), ("professional", "四考")]
    assert result["request_count"] == 3
    assert result["query_fanout_reuse_count"] == 1


def test_source_review_merge_retains_baseline_and_separates_team_candidate_pool() -> None:
    def event_rule(code: str, *, with_material: bool) -> dict:
        material_id = f"OLD-{code}"
        return {
            "materials": ([{"material_id": material_id, "side": "positive"}] if with_material else []),
            "eligible": {
                "positive": ([{"material_id": material_id}] if with_material else []),
                "negative": [],
            },
            "excluded": [],
        }

    baseline = {
        "schema_version": "i5b-source-review-quality-probe-v1",
        "ruler": "李世民",
        "ruler_ref": "RULER-LSM",
        "window": "626-649",
        "rules": {
            **{
                code: event_rule(code, with_material=True)
                for code in (
                    "talent_discovery",
                    "appointment_delegation",
                    "tolerate_talent",
                    "anti_nepotism",
                )
            },
            "team_building": {
                "members": [{"person_ref": "PER-OLD", "person": "旧臣"}],
                "positive_members": ["PER-OLD"],
                "negative_members": [],
            },
        },
    }
    increment = {
        **baseline,
        "retrieved_person_refs": ["PER-OLD", "PER-NEW"],
        "rules": {
            **{
                code: event_rule(code, with_material=False)
                for code in (
                    "talent_discovery",
                    "appointment_delegation",
                    "tolerate_talent",
                    "anti_nepotism",
                )
            },
            "team_building": {
                "members": [{"person_ref": "PER-NEW", "person": "新臣"}],
                "positive_members": ["PER-NEW"],
                "negative_members": [],
            },
        },
    }

    merged = merge_i5b_source_review_decisions(baseline, increment)

    assert merged["baseline_retention"]["event_material_count"] == 4
    assert merged["rules"]["talent_discovery"]["materials"][0]["material_id"].startswith("OLD-")
    assert [row["person_ref"] for row in merged["rules"]["team_building"]["members"]] == [
        "PER-OLD",
        "PER-NEW",
    ]
    assert merged["rules"]["team_building"]["positive_members"] == ["PER-NEW"]


def test_source_review_merge_rejects_team_pool_gaps_and_freeze_overflow() -> None:
    event_rules = {
        code: {"materials": [], "eligible": {"positive": [], "negative": []}, "excluded": []}
        for code in (
            "talent_discovery",
            "appointment_delegation",
            "tolerate_talent",
            "anti_nepotism",
        )
    }
    baseline = {
        "ruler": "李世民",
        "ruler_ref": "RULER-LSM",
        "window": "626-649",
        "rules": {**event_rules, "team_building": {"members": []}},
    }
    increment = {
        **baseline,
        "retrieved_person_refs": ["PER-MISSING"],
        "rules": {
            **event_rules,
            "team_building": {
                "members": [{"person_ref": f"PER-{index}", "person": str(index)} for index in range(9)],
                "positive_members": [f"PER-{index}" for index in range(9)],
                "negative_members": [],
            },
        },
    }

    with pytest.raises(ValueError, match="正8负3"):
        merge_i5b_source_review_decisions(baseline, increment)


def test_biography_heading_does_not_outrank_concrete_action_result_volume(
    tmp_path: Path,
) -> None:
    index_path = tmp_path / "tang-books.sqlite3"
    build_local_source_index(
        [
            {
                "page_title": "舊唐書/卷66",
                "work_title": "舊唐書",
                "source_url": "https://zh.wikisource.org/wiki/舊唐書/卷66",
                "revision_ref": "66",
                "raw_text": "== 房玄齡 ==\n房玄齡為良相。",
            },
            {
                "page_title": "舊唐書/卷50",
                "work_title": "舊唐書",
                "source_url": "https://zh.wikisource.org/wiki/舊唐書/卷50",
                "revision_ref": "50",
                "raw_text": "長孫無忌與房玄齡奉詔修定律令，頒行天下。",
            },
        ],
        index_path,
    )

    hits = LocalSourceTextIndex(index_path).search(
        works=("旧唐书",),
        terms=("房玄龄", "修定律令", "颁行天下"),
        limit=2,
    )

    assert hits[0].page_title == "舊唐書/卷50"


def test_local_text_recall_has_no_candidate_cap_and_priority_never_filters(
    tmp_path: Path,
) -> None:
    index_path = tmp_path / "all-recall.sqlite3"
    build_local_source_index(
        [
            {
                "page_title": f"舊唐書/卷{number}",
                "work_title": "舊唐書",
                "source_url": f"https://example.test/{number}",
                "revision_ref": str(number),
                "raw_text": (
                    "房玄齡修定律令" if number == 205 else f"房玄齡記事{number}"
                ),
            }
            for number in range(1, 206)
        ],
        index_path,
    )

    index = LocalSourceTextIndex(index_path)
    hits = index.recall(
        works=("旧唐书",),
        recall_terms=("玄龄",),
        attribution_terms=("房玄龄",),
        priority_terms=("修定律令",),
    )

    assert len(hits) == 205
    assert hits[0].page_title == "舊唐書/卷205"
    assert hits[0].matched_priority_terms == ("修定律令",)
    assert hits[0].matched_attribution_terms == ("房玄龄",)
    assert hits[0].closest_priority_distance is not None
    assert sum(not hit.matched_priority_terms for hit in hits) == 204


def test_local_recall_report_preserves_every_unprioritized_locator(
    tmp_path: Path,
) -> None:
    index_path = tmp_path / "recall-report.sqlite3"
    build_local_source_index(
        [
            {
                "page_title": "舊唐書/卷50",
                "work_title": "舊唐書",
                "source_url": "https://example.test/50",
                "revision_ref": "50",
                "raw_text": "房玄齡修定律令。",
            },
            {
                "page_title": "舊唐書/卷66",
                "work_title": "舊唐書",
                "source_url": "https://example.test/66",
                "revision_ref": "66",
                "raw_text": "玄齡為相。",
            },
        ],
        index_path,
    )

    report = build_local_recall_report(
        LocalSourceTextIndex(index_path),
        (
            {
                "subject_name": "房玄龄",
                "works": ["旧唐书"],
                "recall_terms": ["玄龄"],
                "attribution_terms": ["房玄龄"],
                "priority_terms": ["律令"],
            },
        ),
    )

    subject = report["subjects"][0]
    assert subject["hit_count"] == 2
    assert subject["prioritized_hit_count"] == 1
    assert subject["unprioritized_retained_count"] == 1
    assert subject["explicit_attribution_hit_count"] == 1
    assert subject["short_form_only_retained_count"] == 1
    assert [hit["page_title"] for hit in subject["hits"]] == [
        "舊唐書/卷50",
        "舊唐書/卷66",
    ]


def test_local_recall_excludes_other_dynasties_by_configured_volume_range(
    tmp_path: Path,
) -> None:
    index_path = tmp_path / "dynasty-range.sqlite3"
    build_local_source_index(
        [
            {
                "page_title": "資治通鑑/卷033",
                "work_title": "資治通鑑",
                "source_url": "https://example.test/33",
                "revision_ref": "33",
                "raw_text": "其人无忌。",
            },
            {
                "page_title": "資治通鑑/卷199",
                "work_title": "資治通鑑",
                "source_url": "https://example.test/199",
                "revision_ref": "199",
                "raw_text": "长孙无忌辅政。",
            },
        ],
        index_path,
    )

    hits = LocalSourceTextIndex(index_path).recall(
        works=("资治通鉴",),
        recall_terms=("无忌",),
        attribution_terms=("长孙无忌",),
        page_ranges={"资治通鉴": (185, 265)},
    )

    assert [hit.page_title for hit in hits] == ["資治通鑑/卷199"]
    assert hits[0].matched_attribution_terms == ("长孙无忌",)


def test_subject_mention_sidecar_preserves_short_forms_and_core_ruler_context(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "source.sqlite3"
    build_local_source_index(
        [
            {
                "page_title": "舊唐書/卷50",
                "work_title": "舊唐書",
                "source_url": "https://example.test/50",
                "revision_ref": "50",
                "raw_text": "房玄齡奉詔修定律令，頒行天下。其後玄齡又定官制。",
            },
            {
                "page_title": "舊唐書/卷66",
                "work_title": "舊唐書",
                "source_url": "https://example.test/66",
                "revision_ref": "66",
                "raw_text": "玄齡為相，務在寬平。",
            },
            {
                "page_title": "舊唐書/卷67",
                "work_title": "舊唐書",
                "source_url": "https://example.test/67",
                "revision_ref": "67",
                "raw_text": "==房玄齡==\n甲乙丙丁戊己庚辛壬癸甲乙丙丁戊己庚辛壬癸甲乙丙丁戊己庚辛壬癸玄齡奉命省官。",
            },
            {
                "page_title": "舊唐書/卷2",
                "work_title": "舊唐書",
                "source_url": "https://example.test/2",
                "revision_ref": "2",
                "raw_text": "上曰百姓新離湯火，不可復勞。下詔減役。",
            },
            {
                "page_title": "舊唐書/卷90",
                "work_title": "舊唐書",
                "source_url": "https://example.test/90",
                "revision_ref": "90",
                "raw_text": "上曰當減役。",
            },
        ],
        source_path,
    )
    source_index = LocalSourceTextIndex(source_path)
    plan = {
        "source_index_identity": source_index.identity,
        "subjects": [
            {
                "subject_ref": "PER-FANG",
                "subject_name": "房玄龄",
                "works": ["旧唐书"],
                "surface_forms": ["玄龄"],
                "attribution_terms": ["房玄龄"],
                "priority_terms": ["律令", "省官"],
                "review_kind": "person_governance",
                "action_terms": ["修定", "定官制", "省官"],
                "implementation_terms": ["奉诏", "奉命"],
                "result_terms": ["颁行"],
            },
            {
                "subject_ref": "PER-RULER",
                "subject_name": "李世民政策",
                "works": ["旧唐书"],
                "surface_forms": ["太宗", "李世民"],
                "attribution_terms": ["太宗", "李世民"],
                "priority_terms": ["减役"],
                "review_kind": "ruler_policy",
                "action_terms": ["诏", "减役"],
                "implementation_terms": ["下诏"],
                "result_terms": ["百姓"],
                "context_rules": [
                    {
                        "page_titles": ["舊唐書/卷2"],
                        "markers": ["上曰", "诏"],
                    }
                ],
            },
        ],
    }
    mention_path = tmp_path / "mentions.sqlite3"

    first = build_subject_mention_index(source_index, plan, mention_path)
    second = build_subject_mention_index(source_index, plan, mention_path)
    report = build_subject_mention_report(
        source_index, mention_path, window_chars=40, merge_gap_chars=10
    )

    assert first["changed"] is True
    assert second["changed"] is False
    subjects = {row["subject_ref"]: row for row in report["subjects"]}
    fang = subjects["PER-FANG"]
    assert fang["mention_count"] == 4
    assert fang["merged_window_count"] == 3
    assert fang["explicit_attribution_window_count"] == 1
    assert fang["short_form_only_window_count"] == 1
    assert fang["unprioritized_retained_count"] == 1
    assert fang["review_tier_counts"] == {"A": 1, "B": 1, "C": 0, "D": 1}
    assert {row["page_title"] for row in fang["windows"]} == {
        "舊唐書/卷50",
        "舊唐書/卷66",
        "舊唐書/卷67",
    }
    section_window = next(row for row in fang["windows"] if row["page_title"] == "舊唐書/卷67")
    assert section_window["attribution_mode"] == "biography_section"
    assert section_window["section_title"] == "房玄齡"
    ruler = subjects["PER-RULER"]
    assert ruler["mention_count"] == 2
    assert ruler["merged_window_count"] == 1
    assert ruler["ruler_context_window_count"] == 1
    assert ruler["prioritized_window_count"] == 1
    assert ruler["windows"][0]["mention_kinds"] == ["ruler_context"]
    assert ruler["review_tier_counts"] == {"A": 1, "B": 0, "C": 0, "D": 0}
    assert "卷90" not in {row["page_title"] for row in ruler["windows"]}
    assert max(
        len(window["text"])
        for subject in report["subjects"]
        for window in subject["windows"]
    ) <= 50
    assert report["network_requests"] == 0
    assert report["formal_writes"] == 0


def test_subject_mention_sidecar_fails_closed_on_source_identity_drift(
    tmp_path: Path,
) -> None:
    first_path = tmp_path / "first.sqlite3"
    second_path = tmp_path / "second.sqlite3"
    row = {
        "page_title": "舊唐書/卷50",
        "work_title": "舊唐書",
        "source_url": "https://example.test/50",
        "revision_ref": "50",
        "raw_text": "房玄齡修律。",
    }
    build_local_source_index([row], first_path)
    build_local_source_index([row | {"raw_text": "房玄齡修律頒行。"}], second_path)
    first = LocalSourceTextIndex(first_path)
    plan = {
        "source_index_identity": first.identity,
        "subjects": [
            {
                "subject_ref": "PER-FANG",
                "subject_name": "房玄龄",
                "works": ["旧唐书"],
                "surface_forms": ["玄龄"],
            }
        ],
    }
    mention_path = tmp_path / "mentions.sqlite3"
    build_subject_mention_index(first, plan, mention_path)

    with pytest.raises(ValueError, match="identity"):
        build_subject_mention_report(LocalSourceTextIndex(second_path), mention_path)


def test_first_review_clustering_requires_conservative_shared_evidence() -> None:
    def window(
        ref: str,
        page: str,
        start: int,
        *,
        tier: str = "A",
        priority: tuple[str, ...] = ("律令",),
        action: tuple[str, ...] = ("修定",),
        implementation: tuple[str, ...] = ("奉诏",),
        result: tuple[str, ...] = ("颁行",),
        periods: tuple[str, ...] = ("贞观十一年",),
    ) -> dict[str, object]:
        return {
            "window_ref": ref,
            "review_tier": tier,
            "page_title": page,
            "work_title": "旧唐书" if "舊" in page else "新唐书",
            "source_url": "https://example.test/" + page,
            "revision_ref": page,
            "start_offset": start,
            "end_offset": start + 100,
            "matched_nearby_priority_terms": list(priority),
            "matched_action_terms": list(action),
            "matched_implementation_terms": list(implementation),
            "matched_result_terms": list(result),
            "period_markers": list(periods),
            "attribution_mode": "explicit_name",
            "text": f"{ref} review text",
        }

    windows = (
        window("W1", "舊唐書/卷50", 0),
        window("W2", "舊唐書/卷50", 500),
        window("W3", "新唐書/卷056", 1000),
        window(
            "W4",
            "新唐書/卷057",
            2000,
            action=("裁省",),
            implementation=("有司",),
            result=("岁省",),
        ),
        window("W5", "舊唐書/卷50", 1500, tier="B"),
    )

    clusters = cluster_first_review_windows("PER-FANG", windows)

    assert sorted(cluster["window_count"] for cluster in clusters) == [1, 3]
    merged = next(cluster for cluster in clusters if cluster["window_count"] == 3)
    assert set(merged["window_refs"]) == {"W1", "W2", "W3"}
    assert merged["merge_basis"] == "cross_source_period_and_signature"
    assert {ref for cluster in clusters for ref in cluster["window_refs"]} == {
        "W1",
        "W2",
        "W3",
        "W4",
    }

    worklist = build_first_review_worklist(
        {
            "schema_version": "subject-mention-shadow-report-v3",
            "source_index_identity": "a" * 64,
            "mention_index_fingerprint": "b" * 64,
            "subjects": [
                {
                    "subject_ref": "PER-FANG",
                    "subject_name": "房玄龄",
                    "windows": list(windows),
                    "first_review_clusters": list(clusters),
                }
            ],
        }
    )
    assert worklist["review_card_count"] == 2
    assert worklist["unique_refetch_page_count"] == 3
    assert worklist["subject_summaries"] == [
        {
            "subject_ref": "PER-FANG",
            "subject_name": "房玄龄",
            "review_card_count": 2,
            "single_work_card_count": 1,
            "missing_period_card_count": 0,
            "unique_refetch_page_count": 3,
            "review_flag_counts": {
                "cross_source_merge_requires_confirmation": 1,
                "single_page_only": 1,
                "single_work_only": 1,
            },
        }
    ]
    assert all(page["refetch_status"] == "not_started" for page in worklist["refetch_pages"])
    assert worklist["network_requests"] == 0

    with pytest.raises(ValueError, match="v3"):
        build_first_review_worklist({"schema_version": "old"})


def test_shared_review_plan_merges_overlapping_people_without_merging_responsibility() -> None:
    def window(
        ref: str,
        page: str,
        revision: str,
        start: int,
        text: str,
        *,
        tier: str = "A",
        surface: str,
    ) -> dict[str, object]:
        return {
            "window_ref": ref,
            "review_tier": tier,
            "page_title": page,
            "work_title": "旧唐书",
            "source_url": "https://example.test/" + page,
            "revision_ref": revision,
            "start_offset": start,
            "end_offset": start + len(text),
            "surface_forms": [surface],
            "mention_offsets": [start + 1],
            "text": text,
        }

    report = {
        "schema_version": "subject-mention-shadow-report-v3",
        "source_index_identity": "a" * 64,
        "mention_index_fingerprint": "b" * 64,
        "subjects": [
            {
                "subject_ref": "PER-FANG",
                "subject_name": "房玄龄",
                "windows": [
                    window("W1", "舊唐書/卷50", "50", 0, "abcdefghij", surface="房玄龄"),
                    window("W3", "舊唐書/卷50", "50", 20, "pqrst", tier="B", surface="玄龄"),
                ],
            },
            {
                "subject_ref": "PER-LONGSUN",
                "subject_name": "长孙无忌",
                "windows": [
                    window("W2", "舊唐書/卷50", "50", 5, "fghijklmno", surface="长孙无忌"),
                    window("W4", "舊唐書/卷51", "51", 0, "uvwxyz", tier="C", surface="无忌"),
                ],
            },
        ],
    }

    plan = build_shared_review_plan(report)
    repeated = build_shared_review_plan(report)

    assert plan == repeated
    assert plan["schema_version"] == "subject-shared-review-plan-v1"
    assert plan["review_tiers"] == ["A", "B"]
    assert plan["subject_count"] == 2
    assert plan["scheduled_window_count"] == 3
    assert plan["source_page_count"] == 1
    assert plan["model_call_budget"] == 1
    batch = plan["page_batches"][0]
    assert batch["subject_refs"] == ["PER-FANG", "PER-LONGSUN"]
    assert batch["window_refs"] == ["W1", "W2", "W3"]
    assert batch["segment_count"] == 2
    shared = batch["segments"][0]
    assert shared["text"] == "abcdefghijklmno"
    assert shared["subject_refs"] == ["PER-FANG", "PER-LONGSUN"]
    assert {row["window_ref"] for row in shared["members"]} == {"W1", "W2"}
    assert all("role" not in row for row in shared["members"])
    assert plan["formal_writes"] == 0
    assert plan["model_calls"] == 0

    broken = json.loads(json.dumps(report))
    broken["subjects"][1]["windows"][0]["text"] = "XXXXXklmno"
    with pytest.raises(ValueError, match="重叠原文不一致"):
        build_shared_review_plan(broken)


def test_shared_neutral_fact_fanout_keeps_context_actor_out_of_profile_credit() -> None:
    text = "房玄龄与法司修定律令，颁行天下。长孙无忌误带佩刀入阁。"
    plan = {
        "schema_version": "subject-shared-review-plan-v1",
        "source_index_identity": "a" * 64,
        "mention_index_fingerprint": "b" * 64,
        "page_batches": [
            {
                "batch_ref": "BATCH-1",
                "page_title": "舊唐書/卷50",
                "work_title": "旧唐书",
                "source_url": "https://example.test/50",
                "revision_ref": "50",
                "segments": [
                    {
                        "segment_ref": "SEG-1",
                        "text": text,
                        "text_sha256": sha256(text.encode("utf-8")).hexdigest(),
                        "subject_refs": ["PER-FANG", "PER-LONGSUN"],
                    }
                ],
            }
        ],
    }
    result = {
        "schema_version": "shared-neutral-extraction-output-v2",
        "batch_ref": "BATCH-1",
        "page_title": "舊唐書/卷50",
        "revision_ref": "50",
        "segment_count": 1,
        "segment_reviews": [
            {
                "segment_ref": "SEG-1",
                "decision": "accept",
                "facts": [
                    {
                        "fact_id": "F001",
                        "exact_quote": "房玄龄与法司修定律令，颁行天下。",
                        "fact_kind": "legal_change",
                        "action_summary": "房玄龄与法司共同修律并颁行。",
                        "actors": [
                            {
                                "source_name": "房玄龄",
                                "canonical_name": "房玄龄",
                                "subject_ref": "PER-FANG",
                                "role": "designer",
                                "responsibility_strength": "core_joint",
                                "attribution_basis": "原文明载共同修定。",
                            },
                            {
                                "source_name": "法司",
                                "canonical_name": "未解析法司人员",
                                "subject_ref": None,
                                "role": "compiler",
                                "responsibility_strength": "core_joint",
                                "attribution_basis": "原文仅载官署。",
                            },
                        ],
                        "implementation_status": "nationally_promulgated",
                        "result": "颁行天下",
                        "legacy_status": "not_shown",
                        "legacy_basis": "未载后续沿用。",
                        "projection_eligibility": "direct_neutral_fact",
                        "uncertainty": "法司成员未具名。",
                    },
                    {
                        "fact_id": "F002",
                        "exact_quote": "长孙无忌误带佩刀入阁。",
                        "fact_kind": "procedural_case",
                        "action_summary": "长孙无忌误带佩刀入阁。",
                        "actors": [
                            {
                                "source_name": "长孙无忌",
                                "canonical_name": "长孙无忌",
                                "subject_ref": "PER-LONGSUN",
                                "role": "affected_person",
                                "responsibility_strength": "context_only",
                                "attribution_basis": "本人是案件对象。",
                            }
                        ],
                        "implementation_status": "not_shown",
                        "result": "形成程序案件",
                        "legacy_status": "not_shown",
                        "legacy_basis": "无",
                        "projection_eligibility": "direct_neutral_fact",
                        "uncertainty": "无",
                    },
                ],
                "reason": "两项均为可回指的中性事实。",
            }
        ],
        "limitations": [],
    }

    fanout = build_shared_neutral_fact_fanout(plan, [result])
    repeated = build_shared_neutral_fact_fanout(plan, [result])

    assert fanout == repeated
    assert fanout["fact_count"] == 2
    assert fanout["person_count"] == 2
    assert fanout["unresolved_actor_count"] == 1
    people = {row["subject_ref"]: row for row in fanout["person_fanout"]}
    assert people["PER-FANG"]["profile_eligible_count"] == 1
    assert people["PER-LONGSUN"]["profile_eligible_count"] == 0
    assert fanout["formal_writes"] == 0
    assert fanout["score_writes"] == 0

    broken = json.loads(json.dumps(result))
    broken["segment_reviews"][0]["facts"][0]["exact_quote"] = "不存在的引文"
    with pytest.raises(ValueError, match="无法回指"):
        build_shared_neutral_fact_fanout(plan, [broken])

    mentioned_only = json.loads(json.dumps(result))
    mentioned_only["segment_reviews"][0]["facts"] = [
        mentioned_only["segment_reviews"][0]["facts"][1]
    ]
    mentioned_only["segment_reviews"][0]["facts"][0]["actors"][0][
        "role"
    ] = "mentioned_only"
    with pytest.raises(ValueError, match="mentioned_only 不能取得事实归属"):
        build_shared_neutral_fact_fanout(plan, [mentioned_only])


def test_shared_neutral_prompt_is_tool_free_rule_neutral_and_filters_routine_ceremony() -> None:
    prompt = build_shared_neutral_extraction_prompt(
        {
            "batch_ref": "BATCH-1",
            "segments": [
                {
                    "segment_ref": "SEG-1",
                    "subject_refs": ["PER-FANG"],
                    "text": "是日大酺三日。",
                }
            ],
        }
    )

    assert "EXECUTION_MODE: STRUCTURED_OUTPUT_NO_TOOLS" in prompt
    assert "普通宴饮、庆典、大酺、游猎、巡幸和祭祀" in prompt
    assert "subject_refs 只是召回候选" in prompt
    assert "不得为了归责而创建 mentioned_only actor" in prompt
    assert "规则复用建议" in prompt
    assert "reuse_candidates" not in prompt


def test_ruler_neutral_person_recall_batches_once_and_preserves_person_boundaries() -> None:
    records = [
        {
            "neutral_record_id": "NREC-1",
            "source_page": "史记/卷008",
            "revision_ref": "R1",
            "date": "汉五年",
            "neutral_summary": "萧何留守关中，韩信率军出战。",
            "assertions": [
                {"exact_quote": "蕭何守關中", "fact": "萧何留守", "locator_anchor": "蕭何"},
                {"exact_quote": "韓信將兵", "fact": "韩信率军", "locator_anchor": "韓信"},
            ],
        },
        {
            "neutral_record_id": "NREC-2",
            "source_page": "史记/卷093",
            "revision_ref": "R2",
            "date": "汉十年",
            "neutral_summary": "韩王信反。",
            "assertions": [
                {"exact_quote": "韓王信反", "fact": "韩王信反", "locator_anchor": "韓王信"}
            ],
        },
    ]
    people = [
        {"person_ref": "PER-XH", "canonical_name": "萧何", "aliases": []},
        {"person_ref": "PER-HX", "canonical_name": "韩信", "aliases": []},
        {"person_ref": "PER-HWX", "canonical_name": "韩王信", "aliases": []},
    ]

    result = build_ruler_neutral_person_recall_plan(
        ruler="刘邦", records=records, people=people, batch_count=2
    )

    assert result["candidate_record_count"] == 2
    assert result["model_call_budget"] == 2
    recalled = {
        row["neutral_record_id"]: {
            person["person_ref"] for person in row["matched_people"]
        }
        for batch in result["batches"]
        for row in batch["records"]
    }
    assert recalled == {
        "NREC-1": {"PER-XH", "PER-HX"},
        "NREC-2": {"PER-HWX"},
    }
    assert result["database_writes"] == result["formal_writes"] == 0

    batch_results = []
    for batch in result["batches"]:
        batch_results.append(
            {
                "schema_version": "ruler-neutral-shared-fanout-v1",
                "task_code": batch["task_code"],
                "record_count": batch["record_count"],
                "record_reviews": [
                    {
                        "neutral_record_id": row["neutral_record_id"],
                        "reason": "测试",
                        "person_reviews": [
                            {
                                "person_ref": person["person_ref"],
                                "canonical_name": person["canonical_name"],
                                "disposition": "achievement",
                                "role": "executor",
                                "responsibility_strength": "primary",
                                "actual_action": "测试行动",
                                "result": "测试结果",
                                "profile_eligibility": True,
                                "supporting_assertion_anchors": [
                                    row["assertions"][0]["locator_anchor"]
                                ],
                                "reason": "测试",
                            }
                            for person in row["matched_people"]
                        ],
                    }
                    for row in batch["records"]
                ],
                "limitations": [],
            }
        )
    fanout = build_ruler_neutral_person_fanout(result, batch_results)
    assert fanout["reviewed_record_count"] == 2
    assert fanout["person_review_count"] == 3
    assert fanout["profile_eligible_count"] == 3
    assert fanout["formal_writes"] == fanout["score_writes"] == 0


def test_person_lifecycle_fanout_audits_plaintext_and_assigns_stable_refs() -> None:
    source_text = "萧何留守关中，转给馈饷，军得以供。史臣称其识大体。"
    manifest = {
        "tasks": [
            {
                "task_code": "PERSON-PAGE-1",
                "source_page": "史記/卷053",
                "revision_ref": "53",
                "source_sha256": sha256(source_text.encode("utf-8")).hexdigest(),
                "people": [
                    {
                        "person_ref": "PER-XH",
                        "canonical_name": "萧何",
                        "person_scan_key": "PSCAN-XH-53",
                    }
                ],
            }
        ]
    }
    result = {
        "schema_version": "neutral-person-lifecycle-source-scan-v1",
        "task_code": "PERSON-PAGE-1",
        "source_page": "史記/卷053",
        "revision_ref": "53",
        "coverage_scope": "FULL_LIFECYCLE_SOURCE",
        "people": [
            {
                "person_ref": "PER-XH",
                "person_scan_key": "PSCAN-XH-53",
                "canonical_name": "萧何",
                "records": [
                    {
                        "record_type": "pattern",
                        "date": "楚汉之际",
                        "dynasty_or_regime": "汉",
                        "ruler_contexts": ["刘邦"],
                        "subject_role": "留守",
                        "neutral_summary": "萧何留守并供应军需。",
                        "assertions": [
                            {
                                "kind": "action",
                                "fact": "萧何留守关中并供应军需。",
                                "exact_quote": "萧何留守关中，转给馈饷，军得以供。",
                                "locator_anchor": "转给馈饷",
                            }
                        ],
                    }
                ],
                "leads": [
                    {
                        "date": "史臣评价",
                        "dynasty_or_regime": "汉",
                        "ruler_contexts": [],
                        "specific_claim": "史臣评价萧何识大体。",
                        "exact_quote": "史臣称其识大体",
                        "locator_anchor": "识大体",
                        "needs": "只作权威评价。",
                    }
                ],
                "scan_notes": "全页扫描。",
            }
        ],
    }

    fanout = build_person_lifecycle_fanout(
        manifest,
        [result],
        {"史記/卷053": source_text},
    )
    repeated = build_person_lifecycle_fanout(
        manifest,
        [result],
        {"史記/卷053": source_text},
    )

    assert fanout == repeated
    assert fanout["person_count"] == 1
    assert fanout["record_count"] == 1
    assert fanout["lead_count"] == 1
    assert fanout["audited_quote_count"] == 2
    person = fanout["people"][0]
    assert person["records"][0]["record_ref"].startswith("PFACT-")
    assert person["leads"][0]["lead_ref"].startswith("PLEAD-")
    assert person["records"][0]["formal_write"] is False
    assert fanout["database_writes"] == fanout["score_writes"] == 0

    broken = json.loads(json.dumps(result))
    broken["people"][0]["records"][0]["assertions"][0]["exact_quote"] = "不存在"
    with pytest.raises(ValueError, match="无法逐字回指"):
        build_person_lifecycle_fanout(
            manifest,
            [broken],
            {"史記/卷053": source_text},
        )


def test_wikisource_revision_batch_preserves_requested_redirect_key() -> None:
    raw_text = "淮陰侯列傳正文"
    payload = {
        "query": {
            "redirects": [{"from": "史記/卷092", "to": "史記/淮陰侯列傳"}],
            "pages": [
                {
                    "title": "史記/淮陰侯列傳",
                    "revisions": [
                        {
                            "revid": 92,
                            "timestamp": "2026-07-20T00:00:00Z",
                            "slots": {"main": {"content": raw_text}},
                        }
                    ],
                }
            ],
        }
    }

    snapshots = snapshots_from_revision_batch_payload(
        requested_titles=("史記/卷092",),
        payload=payload,
        retrieved_at="2026-07-20T00:01:00Z",
    )

    assert set(snapshots) == {"史記/卷092"}
    assert snapshots["史記/卷092"].requested_title == "史記/卷092"
    assert snapshots["史記/卷092"].canonical_title == "史記/淮陰侯列傳"
    assert snapshots["史記/卷092"].raw_text == raw_text


def test_wikisource_plaintext_batch_preserves_revision_and_requested_key() -> None:
    payload = {
        "query": {
            "redirects": [{"from": "漢書/卷023", "to": "漢書/刑法志"}],
            "pages": [
                {
                    "title": "漢書/刑法志",
                    "extract": "刑法志纯文本",
                    "revisions": [
                        {"revid": 23, "timestamp": "2026-07-20T00:00:00Z"}
                    ],
                }
            ],
        }
    }

    snapshots = snapshots_from_plaintext_batch_payload(
        requested_titles=("漢書/卷023",),
        payload=payload,
        retrieved_at="2026-07-20T00:01:00Z",
    )

    assert set(snapshots) == {"漢書/卷023"}
    assert snapshots["漢書/卷023"].canonical_title == "漢書/刑法志"
    assert snapshots["漢書/卷023"].revision_id == 23
    assert snapshots["漢書/卷023"].raw_text == "刑法志纯文本"


def test_wikisource_plaintext_batch_uses_revision_bound_rendered_fallback() -> None:
    payload = {
        "query": {
            "pages": [
                {
                    "title": "通典/卷002",
                    "extract": "",
                    "revisions": [
                        {"revid": 2002, "timestamp": "2026-07-20T00:00:00Z"}
                    ],
                }
            ]
        }
    }
    snapshots = snapshots_from_plaintext_batch_payload(
        requested_titles=("通典/卷002",),
        payload=payload,
        retrieved_at="2026-07-20T00:01:00Z",
        rendered_html_by_revision={
            2002: "<div><p>唐制租庸调。</p><table><tr><td>目录</td></tr></table>"
            "<p>开元中更定之。</p></div>"
        },
    )

    assert snapshots["通典/卷002"].revision_id == 2002
    assert snapshots["通典/卷002"].raw_text == "唐制租庸调。\n开元中更定之。"


def test_revision_payload_and_refetch_preserve_exact_offsets_and_cache(
    tmp_path: Path,
) -> None:
    raw_text = "前文房玄齡奉詔修定律令，頒行天下。後文"
    start = raw_text.index("房玄齡")
    end = raw_text.index("。", start) + 1
    expected_text = raw_text[start:end]
    payload = {
        "query": {
            "pages": [
                {
                    "title": "舊唐書/卷50",
                    "revisions": [
                        {
                            "revid": 50,
                            "timestamp": "2026-07-18T00:00:00Z",
                            "slots": {"main": {"content": raw_text}},
                        }
                    ],
                }
            ]
        }
    }
    parsed = snapshot_from_revision_payload(
        page_code="SOURCEPAGE-50",
        requested_title="舊唐書/卷50",
        payload=payload,
        retrieved_at="2026-07-18T00:00:01Z",
    )
    assert parsed.raw_text == raw_text
    worklist = {
        "schema_version": "subject-mention-review-worklist-v2",
        "source_index_identity": "a" * 64,
        "mention_index_fingerprint": "b" * 64,
        "refetch_pages": [
            {
                "page_title": "舊唐書/卷50",
                "work_title": "旧唐书",
                "source_url": "https://example.test/50",
                "revision_ref": "50",
                "subject_refs": ["PER-FANG"],
                "cluster_refs": ["CLUSTER-1"],
                "window_refs": ["WINDOW-1"],
                "refetch_status": "not_started",
            }
        ],
        "review_cards": [
            {
                "cluster_ref": "CLUSTER-1",
                "subject_ref": "PER-FANG",
                "subject_name": "房玄龄",
                "window_refs": ["WINDOW-1"],
                "source_pages": [
                    {
                        "page_title": "舊唐書/卷50",
                        "work_title": "旧唐书",
                        "source_url": "https://example.test/50",
                        "revision_ref": "50",
                        "window_refs": ["WINDOW-1"],
                        "window_spans": [
                            {
                                "window_ref": "WINDOW-1",
                                "start_offset": start,
                                "end_offset": end,
                                "expected_text_hash": sha256(
                                    expected_text.encode("utf-8")
                                ).hexdigest(),
                            }
                        ],
                    }
                ],
            }
        ],
    }
    calls = []

    def fetch(**kwargs):
        calls.append(kwargs)
        return parsed

    first, first_audit = refetch_first_review_worklist(
        worklist, state_dir=tmp_path / "state", fetch=fetch
    )
    second, second_audit = refetch_first_review_worklist(
        worklist,
        state_dir=tmp_path / "state",
        fetch=lambda **_kwargs: pytest.fail("cache replay must not fetch"),
    )

    assert first == second
    assert first["passage_count"] == 1
    assert first["passages"][0]["raw_text"] == expected_text
    assert first["passages"][0]["lineage_status"] == "exact_revision_offset_match"
    assert first["complete_cluster_count"] == 1
    assert first_audit == {
        "network_request_count": 1,
        "cache_hit_count": 0,
        "state_write_count": 1,
    }
    assert second_audit == {
        "network_request_count": 0,
        "cache_hit_count": 1,
        "state_write_count": 0,
    }
    assert len(calls) == 1


def test_locator_rejects_subject_name_only_false_positive() -> None:
    located = locate_lead_span(
        "== 房玄龄 ==\n房玄龄位居宰辅，太宗论其功。",
        {
            "lead": "裁并冗员",
            "subject_action": "房玄龄参与裁并冗员",
            "observable_result": "省中央官员",
        },
        subject_name="房玄龄",
    )

    assert located is None


def test_policy_locator_accepts_attested_source_recall_synonym() -> None:
    located = locate_lead_span(
        "太宗谓房玄龄曰：官在得人，不在员多。命玄龄并省，留文武六百四十三员。",
        {
            "lead": "贞观初裁并中央机构并精简官员编制",
            "lead_type": "policy",
            "subject_action": "裁并中央机构",
            "observable_result": "精简官员编制",
            "period_or_ruler_context": "李世民（太宗）",
            "source_recall_terms": ["官在得人", "六百四十三"],
        },
        subject_name="李世民",
        terms_override=("官在得人", "六百四十三"),
    )

    assert located is not None


def test_locator_rejects_action_owned_by_another_person_outside_biography() -> None:
    located = locate_lead_span(
        "高宗时，裴炎受遗诏辅政，军国大事取天后进止。",
        {
            "lead": "辅政",
            "subject_action": "长孙无忌受遗诏辅政",
            "observable_result": "辅佐高宗",
            "period_or_ruler_context": "唐高宗",
        },
        subject_name="长孙无忌",
    )

    assert located is None


def test_locator_rejects_collaborator_names_without_focus_action() -> None:
    located = locate_lead_span(
        "太宗与长孙无忌、房玄龄、李勣等计议，立晋王为皇太子。",
        {
            "lead": "修定律令",
            "subject_action": "房玄龄与长孙无忌等修定律令",
            "observable_result": "律令颁行",
            "period_or_ruler_context": "唐太宗",
        },
        subject_name="房玄龄",
    )

    assert located is None


def test_local_index_preanchor_avoids_fetching_false_candidate(tmp_path: Path) -> None:
    index_path = tmp_path / "tang-books.sqlite3"
    build_local_source_index(
        [
            {
                "page_title": "資治通鑑/卷203",
                "work_title": "資治通鑑",
                "source_url": "https://zh.wikisource.org/wiki/資治通鑑/卷203",
                "revision_ref": "203",
                "raw_text": "高宗时，裴炎受遗诏辅政，军国大事取天后进止。",
            }
        ],
        index_path,
    )
    worklist = {
        "schema_version": WORKLIST_SCHEMA_VERSION,
        "tasks": [{"subject_ref": "PER-ZS", "subject_name": "长孙无忌", "discovery_captured_at": "2026-07-18T00:00:00Z"}],
        "source_batches": [{
            "source_batch_code": "SRCB-ZS",
            "subject_ref": "PER-ZS",
            "subject_name": "长孙无忌",
            "source_url": "",
            "source_works": ["资治通鉴"],
            "requested_sections": [],
            "projection_targets": ["historical_episode_candidate"],
            "leads": [{
                "lead_ref": "ZS:L1",
                "lead_type": "achievement",
                "lead": "辅政",
                "subject_action": "长孙无忌受遗诏辅政",
                "observable_result": "辅佐高宗",
                "period_or_ruler_context": "唐高宗",
                "projection_targets": ["historical_episode_candidate"],
            }],
        }],
        "unresolved_locators": [],
    }
    worklist_path = tmp_path / "worklist.json"
    worklist_path.write_text(json.dumps(worklist, ensure_ascii=False), encoding="utf-8")

    def forbidden_fetch(**_kwargs):
        raise AssertionError("offline pre-anchor must reject this page")

    report = backfill_person_worklist(
        worklist_path,
        state_dir=tmp_path / "state",
        output_dir=tmp_path / "reports",
        service_release_sha="a" * 40,
        fetch=forbidden_fetch,
        local_source_index_path=index_path,
    )

    assert report["runtime_audit"]["network_request_count"] == 0
    assert report["response"]["passages"] == []


@pytest.mark.parametrize(
    ("requested", "canonical", "required_work"),
    (
        ("前汉", "西汉", "汉书"),
        ("曹魏", "三国", "三国志"),
        ("东晋", "两晋十六国", "晋书"),
        ("北魏", "南北朝", "魏书"),
        ("武周", "唐", "旧唐书"),
        ("北宋", "宋", "宋史"),
        ("后金", "清", "清实录"),
    ),
)
def test_dynasty_source_routes_are_explicit_and_alias_safe(
    requested: str,
    canonical: str,
    required_work: str,
) -> None:
    routed_dynasty, scopes = load_i5b_source_search_scope(
        DEFAULT_I5B_SOURCE_SCOPE_PATH,
        dynasty=requested,
    )

    assert routed_dynasty == canonical
    assert required_work in scopes["ruler_policy_discovery"]


def test_wikisource_dump_import_streams_only_configured_works(tmp_path: Path) -> None:
    dump = tmp_path / "pages.xml.bz2"
    dump.write_bytes(
        bz2.compress(
            (
                '<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/">'
                "<page><title>舊唐書/卷50</title><ns>0</ns>"
                "<revision><id>50</id><text>房玄齡修律</text></revision></page>"
                "<page><title>宋史/卷1</title><ns>0</ns>"
                "<revision><id>1</id><text>不应导入</text></revision></page>"
                "</mediawiki>"
            ).encode("utf-8")
        )
    )

    rows = list(iter_wikisource_dump(dump, works=("舊唐書",)))

    assert [row["page_title"] for row in rows] == ["舊唐書/卷50"]
    assert rows[0]["revision_ref"] == "50"
    assert rows[0]["raw_text"] == "房玄齡修律"


def test_book_only_lead_uses_local_index_before_revision_fetch(tmp_path: Path) -> None:
    raw_text = "長孫無忌與房玄齡奉詔修定律令，頒行天下。"
    index_path = tmp_path / "tang-books.sqlite3"
    build_local_source_index(
        [
            {
                "page_title": "舊唐書/卷50",
                "work_title": "舊唐書",
                "source_url": "https://zh.wikisource.org/wiki/舊唐書/卷50",
                "revision_ref": "49",
                "raw_text": raw_text,
            }
        ],
        index_path,
    )
    worklist = {
        "schema_version": WORKLIST_SCHEMA_VERSION,
        "tasks": [
            {
                "subject_ref": "PER-FANG",
                "subject_name": "房玄龄",
                "discovery_captured_at": "2026-07-18T00:00:00Z",
            }
        ],
        "source_batches": [
            {
                "source_batch_code": "SRCB-FANG-LAW",
                "subject_ref": "PER-FANG",
                "subject_name": "房玄龄",
                "source_url": "未核",
                "source_works": ["旧唐书"],
                "requested_sections": ["未核"],
                "projection_targets": ["historical_episode_candidate"],
                "leads": [
                    {
                        "lead_ref": "FANG-LAW:L1",
                        "lead_type": "achievement",
                        "lead": "房玄龄与长孙无忌修律",
                        "subject_action": "奉诏修定律令",
                        "observable_result": "颁行天下",
                        "period_or_ruler_context": "唐太宗",
                        "projection_targets": ["historical_episode_candidate"],
                    }
                ],
            }
        ],
        "unresolved_locators": [],
    }
    worklist_path = tmp_path / "worklist.json"
    worklist_path.write_text(
        json.dumps(worklist, ensure_ascii=False), encoding="utf-8"
    )
    calls = []

    def fetch(**kwargs):
        calls.append(kwargs)
        assert kwargs["page_title"] == "舊唐書/卷50"
        return WikisourcePageSnapshot(
            page_code="JTS-50",
            requested_title="舊唐書/卷50",
            canonical_title="舊唐書/卷50",
            canonical_url="https://zh.wikisource.org/wiki/舊唐書/卷50",
            revision_id=50,
            revision_timestamp="2026-07-18T00:00:00Z",
            retrieved_at="2026-07-18T00:00:01Z",
            raw_text=raw_text,
            content_hash=sha256(raw_text.encode("utf-8")).hexdigest(),
        )

    report = backfill_person_worklist(
        worklist_path,
        state_dir=tmp_path / "state",
        output_dir=tmp_path / "reports",
        service_release_sha="a" * 40,
        fetch=fetch,
        local_source_index_path=index_path,
    )

    assert len(calls) == 1
    assert report["runtime_audit"]["network_request_count"] == 1
    assert len(report["response"]["passages"]) == 1
    assert report["response"]["provenance"]["provider"] == (
        "local_text_index_then_wikisource_revision:v23"
    )


def _task(
    code: str,
    subject: str = "李斯",
    purpose_code: str = "political_risk_discovery",
):
    return {
        "task_code": code,
        "input_version": "fixture-v1",
        "purpose_code": purpose_code,
        "subject_ref": f"PER-{code}",
        "subject_name": subject,
        "query": f"{subject} 劣迹,要有史料来源",
        "requested_outputs": ["event_leads", "source_hints"],
        "lease_seconds": 60,
        "max_attempts": 2,
    }


def test_worker_bootstrap_does_not_create_blank_ai_conversation() -> None:
    url = _worker_bootstrap_url("session-1")
    assert "gai_bridge=1" in url
    assert "gai_session=session-1" in url
    assert "udm=50" not in url
    assert "Google+AI+Bridge" not in url


def test_content_script_recovers_compact_authority_leads_after_timeout_boundary() -> None:
    script = (
        Path(__file__).parents[1]
        / "src/emperor_v4/infrastructure/google_ai_extension/content.js"
    ).read_text(encoding="utf-8")

    assert "normalizeCompactAnswer" in script
    assert "normalizeMarkdownAnswer" in script
    assert "normalizeSourceUrlFields" in script
    assert '"locator_anchor", "locator_confidence", "locator_uncertainty"' in script
    assert "const POLL_INTERVAL_MS = 10_000" in script
    assert ".pCTyYe" in script
    assert 'reason = "invalid_contract"' in script
    assert "LEAD\\s+L1\\s*[:：]" in script
    assert "captureGraceDeadline = deadline + 30_000" in script
    assert "replace(/^\\s*yaml\\s*\\n/i, \"\")" in script
    assert 'task.purpose_code !== "authority_evaluation_discovery"' in script
    assert 'task.response_mode === "free_text"' in script


def _result(claim: dict, subject: str = "李斯") -> dict:
    answer = (
        "DISCOVERY_SUMMARY\n"
        "searched_categories: 制度风险, 人身损害\n"
        "uncovered_categories: 无\n"
        "stop_reason: exhausted_categories\n"
        "LEAD L1\n"
        "lead_type: risk\n"
        f"lead: {subject}实施了可归责的相关行动\n"
        "period_or_ruler_context: 测试时期\n"
        f"subject_action: {subject}直接推动并实施相关行动\n"
        "responsibility: direct\n"
        + "observable_result: "
        + "该行动产生了可观察且需要进一步回源核验的政治与制度结果。" * 4
        + "\nproject_relevance: 用于政治风险候选复核\n"
        "source_hints:\n"
        "  - source_work: 史记\n"
        "    volume_or_section: 未核\n"
        "    source_url: https://ctext.org/shiji/zh\n"
        "uncertainty: 仍需 SourcePassage 回源\n"
        "OMISSIONS\n"
        "omitted_leads: 无\n"
        "omission_reason: 无"
    )
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "task_code": claim["task_code"],
        "input_fingerprint": claim["input_fingerprint"],
        "answer_text": answer,
        "source_links": [{"title": "史记", "url": "https://ctext.org/shiji/zh"}],
        "page_title": f"{subject} - Google AI",
        "page_url": "https://www.google.com/search?udm=50&q=test",
        "captured_at": "2026-07-17T00:00:00Z",
        "attempt_started_at": "2026-07-17T00:00:00Z",
        "answer_ready_at": "2026-07-17T00:00:12Z",
        "discovery_duration_seconds": 12.0,
    }


def test_free_text_response_mode_keeps_bridge_business_agnostic(tmp_path: Path) -> None:
    queue = GoogleAiTaskQueue(tmp_path)
    queue.enqueue(
        [
            _task("FREE-TEXT", "李世民", "i5a_self_discipline_discovery")
            | {
                "query": "请按本任务自带模板返回李世民自律与勤政宽搜结果",
                "response_mode": "free_text",
            }
        ]
    )
    claim = queue.claim("worker")
    assert claim
    assert claim["response_mode"] == "free_text"
    result = _result(claim, "李世民")
    result["answer_text"] = (
        "任意模板标题\nsubject: 李世民\noverall_pattern: 长期处理政务，晚年阶段仍需回源核验。"
        * 4
    )
    result["source_links"] = []

    artifact = queue.complete("worker", claim["lease_token"], result)

    saved = json.loads(artifact.read_text(encoding="utf-8"))
    assert saved["answer_text"].startswith("任意模板标题")
    assert saved["purpose_code"] == "i5a_self_discipline_discovery"


def test_locator_only_i5b_result_passes_without_external_links(tmp_path: Path) -> None:
    policy = load_discovery_prompt_policy(
        Path(__file__).parents[1] / "config/google-ai-discovery-prompt.yml"
    )
    task = build_i5b_discovery_manifest(
        policy,
        ruler_ref="PER-TAIZONG",
        ruler_name="李世民",
        ruler_dynasty="唐",
        input_version="i5b-calibration-v1",
        civil_people=(),
    )["tasks"][0]
    queue = GoogleAiTaskQueue(tmp_path)
    queue.enqueue([task])
    claim = queue.claim("worker")
    assert claim
    result = _result(claim, "李世民")
    result["answer_text"] = (
        result["answer_text"]
        .replace("lead_type: risk", "lead_type: policy")
        .replace(
            "  - source_work: 史记\n"
            "    volume_or_section: 未核\n"
            "    source_url: https://ctext.org/shiji/zh",
            "  - source_type: political_compendium\n"
            "    source_work: 贞观政要\n"
            "    volume_or_section: 任贤\n"
            "    locator_anchor: 李世民 任贤 用人\n"
            "    locator_confidence: probable\n"
            "    locator_uncertainty: 具体条目仍需回源核对\n"
            "    source_url: 未核",
        )
    )
    result["source_links"] = []

    artifact = queue.complete("worker", claim["lease_token"], result)

    assert artifact.is_file()
    assert json.loads(artifact.read_text(encoding="utf-8"))["source_links"] == []


def test_queue_is_serial_and_tasks_are_isolated(tmp_path: Path) -> None:
    queue = GoogleAiTaskQueue(tmp_path)
    queue.enqueue(
        [
            _task("RISK-LISI"),
            _task("CIVIL-FANG", "房玄龄", "civil_governance_discovery")
            | {"query": "房玄龄 举措"},
            _task("POLICY-TANG", "唐太宗", "ruler_policy_discovery")
            | {"query": "唐太宗 用人政策"},
            _task("BIO-DURU", "杜如晦", "person_biography_discovery")
            | {
                "query": "杜如晦生平,每一条都要有史料来源,最后附上史学家或学者评价",
                "requested_outputs": [
                    "timeline",
                    "source_hints",
                    "authority_evaluations",
                ],
            },
        ]
    )
    first = queue.claim("worker-a")
    assert first and first["task_code"] == "RISK-LISI"
    assert queue.claim("worker-b") is None
    queue.complete("worker-a", first["lease_token"], _result(first))
    second = queue.claim("worker-b")
    assert second and second["task_code"] == "CIVIL-FANG"
    assert second["purpose_code"] == "civil_governance_discovery"


def test_unchanged_enqueue_and_completed_rerun_write_nothing(tmp_path: Path) -> None:
    queue = GoogleAiTaskQueue(tmp_path)
    task = _task("RISK-LISI")
    assert queue.enqueue([task]) == 1
    claim = queue.claim("worker")
    assert claim
    artifact = queue.complete("worker", claim["lease_token"], _result(claim))
    state_bytes = queue.state_path.read_bytes()
    artifact_bytes = artifact.read_bytes()

    assert queue.enqueue([task]) == 0
    assert queue.claim("worker") is None
    assert queue.state_path.read_bytes() == state_bytes
    assert artifact.read_bytes() == artifact_bytes


def test_expired_lease_is_recovered_and_resumed(tmp_path: Path) -> None:
    now = datetime(2026, 7, 17, tzinfo=timezone.utc)
    queue = GoogleAiTaskQueue(tmp_path, clock=lambda: now)
    queue.enqueue([_task("RISK-LISI")])
    first = queue.claim("dead-worker")
    assert first
    now += timedelta(seconds=61)
    resumed = queue.claim("resume-worker")
    assert resumed and resumed["task_code"] == "RISK-LISI"
    assert resumed["lease_token"] != first["lease_token"]


def test_quality_failure_closes_only_task_and_other_tasks_continue(tmp_path: Path) -> None:
    queue = GoogleAiTaskQueue(tmp_path)
    queue.enqueue([_task("RISK-LISI"), _task("RISK-HANXIN", "韩信")])
    claim = queue.claim("worker")
    assert claim
    invalid = _result(claim) | {"answer_text": "李斯：内容过短"}
    with pytest.raises(GoogleAiBridgeError, match="过短"):
        queue.complete("worker", claim["lease_token"], invalid)
    rejected = tmp_path / "rejected/RISK-LISI-attempt-1.json"
    assert rejected.is_file()
    rejected_payload = json.loads(rejected.read_text(encoding="utf-8"))
    assert rejected_payload["result"]["answer_text"] == "李斯：内容过短"
    status = queue.status()
    assert status.failed_closed == 1
    assert status.pending == 1
    assert status.paused is False
    next_claim = queue.claim("worker")
    assert next_claim and next_claim["task_code"] == "RISK-HANXIN"


def test_invalid_contract_closes_only_that_task_without_retry_or_pause(tmp_path: Path) -> None:
    queue = GoogleAiTaskQueue(tmp_path)
    queue.enqueue([_task("RISK-LISI"), _task("RISK-HANXIN", "韩信")])
    claim = queue.claim("worker")
    assert claim
    queue.fail("worker", claim["lease_token"], "invalid_contract", "format rejected")
    status = queue.status()
    assert status.failed_closed == 1
    assert status.retryable == 0
    assert status.paused is False
    next_claim = queue.claim("worker")
    assert next_claim and next_claim["task_code"] == "RISK-HANXIN"


def test_prompt_echo_and_google_navigation_link_are_rejected(tmp_path: Path) -> None:
    queue = GoogleAiTaskQueue(tmp_path)
    queue.enqueue(
        [
            _task("RISK-LISI")
            | {"quality_requirements": {"min_source_links": 1}}
        ]
    )
    claim = queue.claim("worker")
    assert claim
    invalid = _result(claim) | {
        "answer_text": _result(claim)["answer_text"]
        + "\n"
        + claim["query"]
        + ("\n模板回显内容" * 20),
        "source_links": [
            {"title": "Google products", "url": "https://www.google.co.jp/intl/zh-CN/about/products"}
        ],
    }
    with pytest.raises(GoogleAiBridgeError, match="混入查询 prompt 或模板"):
        queue.complete("worker", claim["lease_token"], invalid)


def test_homepage_only_source_links_close_only_invalid_task(tmp_path: Path) -> None:
    queue = GoogleAiTaskQueue(tmp_path)
    queue.enqueue(
        [
            _task("RISK-LISI")
            | {"quality_requirements": {"min_source_links": 1}}
        ]
    )
    claim = queue.claim("worker")
    assert claim
    invalid = _result(claim)
    invalid["source_links"] = [
        {"title": "Wikisource", "url": "https://wikisource.org/"}
    ]
    with pytest.raises(GoogleAiBridgeError, match="少于任务质量要求"):
        queue.complete("worker", claim["lease_token"], invalid)
    assert queue.status().failed_closed == 1
    assert queue.status().paused is False


@pytest.mark.parametrize(
    ("replacement", "message"),
    [
        ("“据史书原文”", "包含引文或仿写原文"),
        ("source_url: wikisource.org", "含裸域名或站点首页 source_url"),
        (
            "searched_categories:\n  - 军事\nuncovered_categories:\n  - 军事",
            "已检索与未覆盖类别自相矛盾",
        ),
    ],
)
def test_semantic_quality_gates_reject_unusable_discovery_output(
    tmp_path: Path, replacement: str, message: str
) -> None:
    queue = GoogleAiTaskQueue(tmp_path)
    queue.enqueue([_task("RISK-LISI")])
    claim = queue.claim("worker")
    assert claim
    invalid = _result(claim)
    if replacement.startswith("source_url:"):
        invalid["answer_text"] = invalid["answer_text"].replace(
            "source_url: https://ctext.org/shiji/zh", replacement
        )
    elif replacement.startswith("searched_categories:"):
        invalid["answer_text"] = re.sub(
            r"(?ms)^searched_categories:.*?^stop_reason:",
            f"{replacement}\nstop_reason:",
            invalid["answer_text"],
        )
    else:
        invalid["answer_text"] += f"\n{replacement}"
    with pytest.raises(GoogleAiBridgeError, match=message):
        queue.complete("worker", claim["lease_token"], invalid)


def test_authority_lead_must_be_a_short_locator_not_a_narrative(tmp_path: Path) -> None:
    queue = GoogleAiTaskQueue(tmp_path)
    queue.enqueue([_task("AUTH-LIJING", "李靖", "authority_evaluation_discovery")])
    claim = queue.claim("worker")
    assert claim
    invalid = _result(claim, "李靖")
    invalid["answer_text"] = invalid["answer_text"].replace(
        "lead_type: risk\nlead: 李靖实施了可归责的相关行动",
        "lead_type: authority_evaluation\nlead: 旧唐书史臣以长篇战役叙事评价李靖",
    )
    with pytest.raises(GoogleAiBridgeError, match="lead 未保持纯定位格式"):
        queue.complete("worker", claim["lease_token"], invalid)


def test_transient_failure_retries_without_pausing_other_tasks(tmp_path: Path) -> None:
    queue = GoogleAiTaskQueue(tmp_path)
    queue.enqueue([_task("RISK-LISI"), _task("RISK-HANXIN", "韩信")])
    first = queue.claim("worker")
    assert first
    queue.fail("worker", first["lease_token"], "transient_page_error", "timeout")
    status = queue.status()
    assert status.retryable == 1
    assert status.pending == 1
    assert status.paused is False


def test_success_artifact_is_discovery_only_and_contract_valid(tmp_path: Path) -> None:
    queue = GoogleAiTaskQueue(tmp_path)
    queue.enqueue([_task("RISK-LISI")])
    claim = queue.claim("worker")
    assert claim
    artifact = queue.complete("worker", claim["lease_token"], _result(claim))
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["quality"]["status"] == "passed"
    assert payload["provenance"] == {
        "collector": "chrome_extension",
        "usage": "discovery_lead_only",
        "direct_assertion_write_allowed": False,
        "source_passage_required_before_claim_extraction": True,
        "downstream_context": {},
    }
    assert "assertions" not in payload
    assert "episodes" not in payload


def test_transient_failure_preserves_rejected_diagnostic(tmp_path: Path) -> None:
    queue = GoogleAiTaskQueue(tmp_path)
    queue.enqueue([_task("RISK-LISI")])
    claim = queue.claim("worker")
    assert claim
    queue.fail(
        "worker",
        claim["lease_token"],
        "transient_page_error",
        "timeout",
        "https://www.google.com/search?udm=50&mstk=test-session",
        _result(claim),
    )

    assert queue.status().retryable == 1
    assert (tmp_path / "rejected/RISK-LISI-attempt-1.json").is_file()


def test_subject_alias_satisfies_subject_mention_gate(tmp_path: Path) -> None:
    queue = GoogleAiTaskQueue(tmp_path)
    task = _task("RISK-LISHIMIN", "李世民") | {"subject_aliases": ["唐太宗"]}
    queue.enqueue([task])
    claim = queue.claim("worker")
    assert claim
    artifact = queue.complete(
        "worker",
        claim["lease_token"],
        _result(claim, "唐太宗"),
    )
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["quality"]["matched_subject_mentions"] == ["唐太宗"]


def test_civil_governance_accepts_one_consistent_achievement_type(tmp_path: Path) -> None:
    queue = GoogleAiTaskQueue(tmp_path)
    task = _task(
        "CIVIL-FANG",
        "房玄龄",
        "civil_governance_discovery",
    )
    queue.enqueue([task])
    claim = queue.claim("worker")
    assert claim
    result = _result(claim, "房玄龄")
    result["answer_text"] = result["answer_text"].replace(
        "lead_type: risk",
        "lead_type: achievement",
    )
    assert queue.complete("worker", claim["lease_token"], result).is_file()


def test_civil_governance_accepts_mixed_policy_and_achievement_leads(tmp_path: Path) -> None:
    queue = GoogleAiTaskQueue(tmp_path)
    queue.enqueue([_task("CIVIL-FANG", "房玄龄", "civil_governance_discovery")])
    claim = queue.claim("worker")
    assert claim
    result = _result(claim, "房玄龄").copy()
    result["answer_text"] = result["answer_text"].replace(
        "OMISSIONS\n",
        "LEAD L2\n"
        "lead_type: achievement\n"
        "lead: 房玄龄另一项独立治理成果\n"
        "period_or_ruler_context: 唐太宗\n"
        "subject_action: 房玄龄实施另一项治理举措\n"
        "responsibility: direct\n"
        "observable_result: 形成另一项可观察治理结果。\n"
        "project_relevance: historical_episode_candidate\n"
        "source_hints:\n"
        "  - source_work: 旧唐书\n"
        "    volume_or_section: 卷六十六\n"
        "    source_url: https://zh.wikisource.org/wiki/舊唐書/卷66\n"
        "uncertainty: 待回源\n"
        "OMISSIONS\n",
    ).replace("lead_type: risk", "lead_type: policy")
    assert queue.complete("worker", claim["lease_token"], result).is_file()


def test_i5b_ready_worklist_limits_only_civil_source_backfill(tmp_path: Path) -> None:
    queue = GoogleAiTaskQueue(tmp_path / "queue")
    context = {
        "consumer": "i5b_shadow_source_backfill",
        "ruler_ref": "PER-TAIZONG",
        "ruler_name": "唐太宗",
        "ruler_dynasty": "唐",
    }
    tasks = [
        _task(f"I5B-CIVIL-FANG-{index}", "房玄龄", "civil_governance_discovery")
        | {"downstream_context": context, "subject_ref": "PER-00-FANG"}
        for index in range(4)
    ]
    tasks.extend(
        _task(f"I5B-CIVIL-{index:02d}", f"文臣{index:02d}", "civil_governance_discovery")
        | {"downstream_context": context, "subject_ref": f"PER-{index:02d}"}
        for index in range(1, 13)
    )
    tasks.append(
        _task("I5B-POLICY-TAIZONG", "唐太宗", "ruler_policy_discovery")
        | {"downstream_context": context}
    )
    artifacts = []
    for index, task in enumerate(tasks):
        queue.enqueue([task])
        claim = queue.claim("worker")
        assert claim
        result = _result(claim, task["subject_name"])
        lead_type = "policy" if task["purpose_code"] == "ruler_policy_discovery" else "achievement"
        result["answer_text"] = result["answer_text"].replace(
            "lead_type: risk", f"lead_type: {lead_type}"
        ).replace(
            f"lead: {task['subject_name']}实施了可归责的相关行动",
            f"lead: {task['subject_name']}独立治理事项{index}",
        ).replace(
            f"subject_action: {task['subject_name']}直接推动并实施相关行动",
            f"subject_action: {task['subject_name']}实施独立事项{index}",
        )
        artifacts.append(queue.complete("worker", claim["lease_token"], result))

    payload = build_i5b_ready_worklist(
        artifacts,
        ruler_ref="PER-TAIZONG",
        ruler_name="唐太宗",
        ruler_dynasty="唐",
    )

    civil = [row for row in payload["tasks"] if row["purpose_code"] == "civil_governance_discovery"]
    policy = [row for row in payload["tasks"] if row["purpose_code"] == "ruler_policy_discovery"]
    assert len(civil) == 14
    assert len(policy) == 1
    assert payload["i5b_selection"]["max_person_retrieval_entries"] == 12
    assert payload["i5b_selection"]["selected_person_count"] == 12
    assert payload["i5b_selection"]["policy_entry_counts_against_person_limit"] is False
    assert payload["i5b_selection"]["ruler_policy_lead_limit"] is None
    deferred = payload["i5b_selection"]["deferred_discovery_leads"]
    assert len(deferred) == 2
    assert {row["reason"] for row in deferred} == {
        "civil_first_pass_lead_limit",
        "deferred_boundary_candidate",
    }
    assert payload["i5b_selection"]["source_route"] == (
        "curated_local_text_index_then_revision_fetch"
    )
    assert payload["i5b_selection"]["google_locator_usage"] == (
        "audit_only_not_executable_route"
    )
    assert "贞观政要" in payload["i5b_selection"]["source_search_scopes"][
        "ruler_policy_discovery"
    ]
    assert all(
        task["source_route"] == "curated_local_text_index"
        and task["discovery_locators"]
        for task in payload["tasks"]
    )
    assert all(
        batch["source_url"] == "local-source-index:"
        for batch in payload["source_batches"]
    )
    assert payload["projection_policy"]["formal_write_allowed"] is False


def test_i5b_manifest_caps_people_at_twelve_and_carries_ruler_scope() -> None:
    policy = load_discovery_prompt_policy(
        Path(__file__).parents[1] / "config/google-ai-discovery-prompt.yml"
    )
    manifest = build_i5b_discovery_manifest(
        policy,
        ruler_ref="PER-TAIZONG",
        ruler_name="唐太宗",
        ruler_dynasty="唐",
        input_version="i5b-v1",
        civil_people=(
            {"person_ref": "PER-01", "person_name": "文臣01"},
            {"person_ref": "PER-01", "person_name": "文臣01"},
            *(
                {"person_ref": f"PER-{index:02d}", "person_name": f"文臣{index:02d}"}
                for index in range(2, 15)
            ),
        ),
    )

    assert len(manifest["tasks"]) == 13
    assert [task["purpose_code"] for task in manifest["tasks"][:12]] == [
        "civil_governance_discovery"
    ] * 12
    assert manifest["tasks"][-1]["purpose_code"] == "ruler_policy_discovery"
    selection = manifest["i5b_selection"]
    assert selection["max_person_retrieval_entries"] == 12
    assert selection["selected_person_count"] == 12
    assert selection["policy_entry_counts_against_person_limit"] is False
    assert [row["person_ref"] for row in selection["deferred_people"]] == [
        "PER-13",
        "PER-14",
    ]
    assert all(
        task["downstream_context"]["person_retrieval_priority"] == index
        for index, task in enumerate(manifest["tasks"][:12], start=1)
    )
    assert all("不限数量" in task["query"] for task in manifest["tasks"])
    assert all(
        task["downstream_context"]["ruler_ref"] == "PER-TAIZONG"
        and task["downstream_context"]["ruler_name"] == "唐太宗"
        and task["downstream_context"]["ruler_dynasty"] == "唐"
        for task in manifest["tasks"]
    )

    with pytest.raises(ValueError, match="不得超过配置"):
        build_i5b_discovery_manifest(
            policy,
            ruler_ref="PER-TAIZONG",
            ruler_name="唐太宗",
            ruler_dynasty="唐",
            input_version="i5b-v1",
            civil_people=(),
            max_person_retrieval_entries=13,
        )


def test_i5b_manifest_ranks_rough_impact_and_preserves_risk_lane() -> None:
    policy = load_discovery_prompt_policy(
        Path(__file__).parents[1] / "config/google-ai-discovery-prompt.yml"
    )
    people = [
        {
            "person_ref": f"PER-CORE-{index:02d}",
            "person_name": f"核心臣子{index:02d}",
            "estimated_i5b_impact": "high",
            "i5b_rule_lanes": ["team_building"],
            "selection_priority": index,
        }
        for index in range(1, 14)
    ]
    people.append(
        {
            "person_ref": "PER-RISK",
            "person_name": "高影响风险人物",
            "estimated_i5b_impact": "critical",
            "i5b_rule_lanes": ["appointment_delegation", "political_risk"],
            "selection_priority": 20,
        }
    )

    manifest = build_i5b_discovery_manifest(
        policy,
        ruler_ref="PER-RULER",
        ruler_name="测试皇帝",
        ruler_dynasty="唐",
        input_version="rough-impact-v1",
        civil_people=people,
    )

    selected_refs = [task["subject_ref"] for task in manifest["tasks"][:-1]]
    assert len(selected_refs) == 12
    assert "PER-RISK" in selected_refs
    assert manifest["i5b_selection"]["deferred_people"] == [
        {
            "person_ref": "PER-CORE-12",
            "person_name": "核心臣子12",
            "reason": "deferred_boundary_candidate",
        },
        {
            "person_ref": "PER-CORE-13",
            "person_name": "核心臣子13",
            "reason": "deferred_boundary_candidate",
        },
    ]


def test_open_purpose_contract_supports_new_workflow_without_bridge_changes(
    tmp_path: Path,
) -> None:
    queue = GoogleAiTaskQueue(tmp_path)
    biography = _task("BIO-DURU", "杜如晦", "person_biography_discovery") | {
        "query": "杜如晦生平,每一条都要有史料来源,最后附上史学家或学者评价",
        "requested_outputs": [
            "timeline",
            "source_hints",
            "authority_evaluations",
        ],
        "downstream_context": {
            "consumer": "source_discovery",
            "possible_projections": ["claim_extraction", "person_profile_review"],
        },
    }
    assert queue.enqueue([biography]) == 1
    claim = queue.claim("worker")
    assert claim and claim["purpose_code"] == "person_biography_discovery"
    assert claim["requested_outputs"] == biography["requested_outputs"]


def test_person_rebuild_allows_atomic_history_talent_and_evaluation_leads(
    tmp_path: Path,
) -> None:
    queue = GoogleAiTaskQueue(tmp_path)
    task = _task("PERSON-LIJING", "李靖", "person_rebuild_discovery") | {
        "query": "李靖人物重建文献地图",
    }
    queue.enqueue([task])
    claim = queue.claim("worker")
    assert claim
    result = _result(claim, "李靖")
    result["answer_text"] = result["answer_text"].replace(
        "lead_type: risk",
        "lead_type: event",
    ).replace(
        "OMISSIONS\n",
        "LEAD L2\n"
        "lead_type: achievement\n"
        "lead: 李靖取得另一项可独立回源的重大功业\n"
        "period_or_ruler_context: 唐太宗\n"
        "subject_action: 李靖直接统军实施行动\n"
        "responsibility: direct\n"
        "observable_result: 取得可观察的军事结果\n"
        "project_relevance: 人才等级重审\n"
        "source_hints:\n"
        "  - source_work: 旧唐书\n"
        "    volume_or_section: 卷六十七\n"
        "    source_url: https://zh.wikisource.org/zh-hans/旧唐书/卷67\n"
        "uncertainty: 无\n"
        "OMISSIONS\n",
    )
    assert queue.complete("worker", claim["lease_token"], result).is_file()


def test_person_rebuild_discards_off_focus_leads_without_a_second_google_query(
    tmp_path: Path,
) -> None:
    queue = GoogleAiTaskQueue(tmp_path)
    task = _task("PERSON-LIJING", "李靖", "person_rebuild_discovery")
    queue.enqueue([task])
    claim = queue.claim("worker")
    assert claim
    result = _result(claim, "李靖")
    result["answer_text"] = result["answer_text"].replace(
        "lead_type: risk", "lead_type: event"
    ).replace(
        "OMISSIONS\n",
        "LEAD L2\n"
        "lead_type: risk\n"
        "lead: 李靖另一项风险线索\n"
        "period_or_ruler_context: 唐\n"
        "subject_action: 李靖被指存在相关行为\n"
        "responsibility: disputed\n"
        "observable_result: 待回源\n"
        "project_relevance: historical_episode_candidate\n"
        "source_hints:\n"
        "  - source_work: 旧唐书\n"
        "    volume_or_section: 卷六十七\n"
        "    source_url: https://zh.wikisource.org/zh-hans/旧唐书/卷67\n"
        "uncertainty: disputed\n"
        "OMISSIONS\n",
    )

    artifact = json.loads(
        queue.complete("worker", claim["lease_token"], result).read_text(encoding="utf-8")
    )

    assert artifact["quality"]["ignored_off_focus_lead_count"] == 1
    assert "lead_type: risk" not in artifact["answer_text"]


def test_revalidate_closed_recovers_saved_result_without_new_browser_claim(
    tmp_path: Path,
) -> None:
    queue = GoogleAiTaskQueue(tmp_path)
    task = _task("PERSON-LIJING", "李靖", "person_rebuild_discovery")
    queue.enqueue([task])
    state = queue._load()
    row = state["tasks"][0]
    row["status"] = "failed_closed"
    row["attempts"] = 1
    queue._save(state)
    result = _result(row["task"], "李靖")
    result["answer_text"] = result["answer_text"].replace(
        "lead_type: risk", "lead_type: event"
    )
    rejected_path = tmp_path / "rejected/PERSON-LIJING-attempt-1.json"
    rejected_path.parent.mkdir()
    rejected_path.write_text(
        json.dumps(
            {
                "input_fingerprint": row["task"]["input_fingerprint"],
                "result": result,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert queue.revalidate_failed_closed() == {"revalidated": 1, "still_closed": 0}
    assert queue.status().succeeded == 1
    assert queue.claim("worker") is None


def test_discovery_artifact_builds_generic_idempotent_backfill_worklist(
    tmp_path: Path,
) -> None:
    queue = GoogleAiTaskQueue(tmp_path / "queue")
    queue.enqueue([_task("RISK-LISI")])
    claim = queue.claim("worker")
    assert claim
    artifact = queue.complete("worker", claim["lease_token"], _result(claim))

    payload = build_backfill_worklist([artifact])
    assert payload["schema_version"] == WORKLIST_SCHEMA_VERSION
    assert payload["input_artifacts"] == ["RISK-LISI.json"]
    assert payload["discovery_omissions"] == []
    assert payload["tasks"] == [
        {
            "task_code": "RISK-LISI-L1-BACKFILL",
            "discovery_task_code": "RISK-LISI",
            "discovery_input_version": "fixture-v1",
            "discovery_input_fingerprint": claim["input_fingerprint"],
            "discovery_captured_at": "2026-07-17T00:00:00Z",
            "discovery_artifact": "RISK-LISI.json",
            "lead_code": "L1",
            "subject_ref": "PER-RISK-LISI",
            "subject_name": "李斯",
            "purpose_code": "political_risk_discovery",
            "lead_type": "risk",
            "lead": "李斯实施了可归责的相关行动",
            "period_or_ruler_context": "测试时期",
            "subject_action": "李斯直接推动并实施相关行动",
            "responsibility": "direct",
            "observable_result": "该行动产生了可观察且需要进一步回源核验的政治与制度结果。" * 4,
            "project_relevance": "用于政治风险候选复核",
            "locators": [
                {
                    "source_work": "史记",
                    "volume_or_section": "未核",
                    "source_url": "https://ctext.org/shiji/zh",
                    "locator_status": "work_and_url",
                }
            ],
            "verification_query": "李斯 李斯实施了可归责的相关行动 史记",
            "uncertainty": "仍需 SourcePassage 回源",
            "usage": "source_backfill_candidate_only",
            "source_passage_required": True,
        }
    ]
    assert payload["source_batches"] == [
        {
            "subject_ref": "PER-RISK-LISI",
            "subject_name": "李斯",
            "source_url": "https://ctext.org/shiji/zh",
            "source_works": ["史记"],
            "requested_sections": ["未核"],
            "lead_refs": ["RISK-LISI:L1"],
            "leads": [
                {
                    "lead_ref": "RISK-LISI:L1",
                    "lead_type": "risk",
                    "lead": "李斯实施了可归责的相关行动",
                    "period_or_ruler_context": "测试时期",
                    "subject_action": "李斯直接推动并实施相关行动",
                    "responsibility": "direct",
                    "observable_result": "该行动产生了可观察且需要进一步回源核验的政治与制度结果。" * 4,
                    "project_relevance": "用于政治风险候选复核",
                    "uncertainty": "仍需 SourcePassage 回源",
                    "projection_targets": [
                        "historical_episode_candidate",
                        "political_risk_profile_candidate",
                    ],
                }
            ],
            "projection_targets": [
                "historical_episode_candidate",
                "political_risk_profile_candidate",
            ],
            "usage": "source_backfill_candidate_only",
            "source_batch_code": payload["source_batches"][0]["source_batch_code"],
        }
    ]
    assert payload["unresolved_locators"] == []
    assert payload["projection_policy"]["formal_write_allowed"] is False
    output = tmp_path / "backfill.json"
    assert write_backfill_worklist(output, payload) is True
    first = output.read_bytes()
    assert write_backfill_worklist(output, payload) is False
    assert output.read_bytes() == first


def test_discovery_omissions_remain_visible_to_downstream_review(
    tmp_path: Path,
) -> None:
    queue = GoogleAiTaskQueue(tmp_path / "queue")
    queue.enqueue([_task("PERSON-LIJING", "李靖", "person_rebuild_discovery")])
    claim = queue.claim("worker")
    assert claim
    result = _result(claim, "李靖")
    result["answer_text"] = result["answer_text"].replace(
        "lead_type: risk",
        "lead_type: achievement",
    ).replace(
        "omitted_leads: 无\nomission_reason: 无",
        "omitted_leads: 吐谷浑战役\nomission_reason: 本轮归责定位不足",
    )
    artifact = queue.complete("worker", claim["lease_token"], result)

    assert artifact_omission_gap(
        json.loads(artifact.read_text(encoding="utf-8")),
        artifact_name=artifact.name,
    ) == {
        "discovery_task_code": "PERSON-LIJING",
        "discovery_artifact": "PERSON-LIJING.json",
        "purpose_code": "person_rebuild_discovery",
        "omitted_leads": "吐谷浑战役",
        "omission_reason": "本轮归责定位不足",
        "blocks_profile_review": True,
    }
    payload = build_backfill_worklist([artifact])
    assert payload["discovery_omissions"][0]["omitted_leads"] == "吐谷浑战役"


def test_multiline_omissions_with_blank_reason_remain_a_nonblocking_gap(
    tmp_path: Path,
) -> None:
    queue = GoogleAiTaskQueue(tmp_path / "queue")
    queue.enqueue([_task("PERSON-LIJING", "李靖", "person_rebuild_discovery")])
    claim = queue.claim("worker")
    assert claim
    result = _result(claim, "李靖")
    result["answer_text"] = (
        result["answer_text"]
        .replace("lead_type: risk", "lead_type: event")
        .replace(
            "omitted_leads: 无\nomission_reason: 无",
            "omitted_leads:\n吐谷浑战役\n晚年兵法传承\nomission_reason:",
        )
    )
    artifact = queue.complete("worker", claim["lease_token"], result)

    omission = artifact_omission_gap(
        json.loads(artifact.read_text(encoding="utf-8")), artifact_name=artifact.name
    )
    assert omission is not None
    assert omission["omitted_leads"] == "吐谷浑战役\n晚年兵法传承"
    assert omission["omission_reason"] == "模型未说明，待回源补充"


def test_blank_lead_uncertainty_becomes_a_nonfactual_backfill_default(
    tmp_path: Path,
) -> None:
    queue = GoogleAiTaskQueue(tmp_path / "queue")
    queue.enqueue([_task("RISK-LISI")])
    claim = queue.claim("worker")
    assert claim
    result = _result(claim).copy()
    result["answer_text"] = result["answer_text"].replace(
        "uncertainty: 仍需 SourcePassage 回源\nOMISSIONS",
        "uncertainty:\nOMISSIONS",
    )
    artifact = queue.complete("worker", claim["lease_token"], result)

    payload = build_backfill_worklist([artifact])
    assert payload["tasks"][0]["uncertainty"] == "模型未说明，待回源核验"


def test_backfill_groups_same_document_once_and_rejects_homepage_locator(
    tmp_path: Path,
) -> None:
    queue = GoogleAiTaskQueue(tmp_path / "queue")
    queue.enqueue([_task("RISK-LISI")])
    claim = queue.claim("worker")
    assert claim
    result = _result(claim)
    result["answer_text"] = result["answer_text"].replace(
        "OMISSIONS\n",
        "LEAD L2\n"
        "lead_type: risk\n"
        "lead: 李斯另一项待核政治风险\n"
        "period_or_ruler_context: 秦\n"
        "subject_action: 李斯被指存在另一项行动\n"
        "responsibility: disputed\n"
        "observable_result: 结果待核\n"
        "project_relevance: 政治风险重审\n"
        "source_hints:\n"
        "  - source_work: 史记\n"
        "    volume_or_section: 李斯列传\n"
        "    source_url: https://ctext.org/shiji/zh\n"
        "  - source_work: 汉典\n"
        "    volume_or_section: 未核\n"
        "    source_url: 未核\n"
        "uncertainty: 归责待核\n"
        "OMISSIONS\n",
    )
    artifact = queue.complete("worker", claim["lease_token"], result)
    payload = build_backfill_worklist([artifact])

    assert len(payload["source_batches"]) == 1
    assert payload["source_batches"][0]["lead_refs"] == [
        "RISK-LISI:L1",
        "RISK-LISI:L2",
    ]
    assert payload["unresolved_locators"] == []


def test_precise_work_and_volume_remain_executable_without_lead_url(
    tmp_path: Path,
) -> None:
    queue = GoogleAiTaskQueue(tmp_path / "queue")
    queue.enqueue([_task("PERSON-LIJING", "李靖", "person_rebuild_discovery")])
    claim = queue.claim("worker")
    assert claim
    result = _result(claim, "李靖")
    result["answer_text"] = result["answer_text"].replace(
        "lead_type: risk",
        "lead_type: achievement",
    ).replace(
        "source_work: 史记\n    volume_or_section: 未核\n    source_url: https://ctext.org/shiji/zh",
        "source_work: 旧唐书\n    volume_or_section: 卷六十七\n    source_url: 未核",
    )
    artifact = queue.complete("worker", claim["lease_token"], result)
    payload = build_backfill_worklist([artifact])

    assert len(payload["source_batches"]) == 1
    assert payload["source_batches"][0]["source_works"] == ["旧唐书"]
    assert payload["source_batches"][0]["requested_sections"] == ["卷六十七"]
    assert payload["unresolved_locators"] == []


def test_person_handoff_becomes_ready_without_waiting_for_other_people(
    tmp_path: Path,
) -> None:
    queue = GoogleAiTaskQueue(tmp_path / "queue")
    history = _task("PERSON-LIJING", "李靖", "person_rebuild_discovery")
    risk = _task("RISK-LIJING", "李靖", "political_risk_discovery") | {
        "subject_ref": history["subject_ref"]
    }
    authority = _task("AUTHORITY-LIJING", "李靖", "authority_evaluation_discovery") | {
        "subject_ref": history["subject_ref"]
    }
    waiting = _task("PERSON-FANG", "房玄龄", "person_rebuild_discovery")
    artifacts = []
    for task in (history, waiting):
        queue.enqueue([task])
        claim = queue.claim("worker")
        assert claim
        result = _result(claim, task["subject_name"])
        result["answer_text"] = result["answer_text"].replace(
            "lead_type: risk", "lead_type: event"
        )
        artifacts.append(queue.complete("worker", claim["lease_token"], result))

    assert build_ready_person_worklists(artifacts) == {}
    queue.enqueue([risk])
    claim = queue.claim("worker")
    assert claim
    artifacts.append(queue.complete("worker", claim["lease_token"], _result(claim, "李靖")))

    assert build_ready_person_worklists(artifacts) == {}
    queue.enqueue([authority])
    claim = queue.claim("worker")
    assert claim
    authority_result = _result(claim, "李靖")
    authority_result["answer_text"] = authority_result["answer_text"].replace(
            "lead_type: risk", "lead_type: authority_evaluation"
        ).replace(
            "lead: 李靖实施了可归责的相关行动",
            "lead: 旧唐书｜正｜统帅用兵",
        )
    artifacts.append(
        queue.complete("worker", claim["lease_token"], authority_result)
    )

    ready = build_ready_person_worklists(artifacts)
    assert len(ready) == 1
    lijing = ready[history["subject_ref"]]
    assert lijing["tasks"][0]["subject_name"] == "李靖"
    assert {row["purpose_code"] for row in lijing["tasks"]} == {
        "authority_evaluation_discovery",
        "person_rebuild_discovery",
        "political_risk_discovery",
    }


def test_ready_person_backfill_deduplicates_page_and_replays_without_network(
    tmp_path: Path,
) -> None:
    raw_text = (
        "李靖从平萧铣，江南遂定。其后袭定襄，颉利可汗败。"
        "御史大夫温彦博譖靖军无纲纪，太宗后谓前有人讒公。"
    )
    worklist = {
        "schema_version": WORKLIST_SCHEMA_VERSION,
        "tasks": [
            {
                "subject_ref": "PER-LIJING",
                "subject_name": "李靖",
                "discovery_captured_at": "2026-07-17T00:00:00Z",
            }
        ],
        "source_batches": [
            {
                "source_batch_code": "SRCB-LIJING",
                "subject_ref": "PER-LIJING",
                "subject_name": "李靖",
                "source_url": "https://zh.wikisource.org/wiki/舊唐書/卷67",
                "source_works": ["旧唐书"],
                "requested_sections": ["卷六十七"],
                "projection_targets": [
                    "historical_episode_candidate",
                    "talent_profile_candidate",
                    "political_risk_profile_candidate",
                ],
                "leads": [
                    {
                        "lead_ref": "PERSON-LIJING:L1",
                        "lead_type": "achievement",
                        "lead": "李靖平定萧铣",
                        "subject_action": "李靖从平萧铣",
                        "observable_result": "江南遂定",
                        "period_or_ruler_context": "唐高祖",
                        "projection_targets": [
                            "historical_episode_candidate",
                            "talent_profile_candidate",
                        ],
                    },
                    {
                        "lead_ref": "RISK-LIJING:L1",
                        "lead_type": "risk",
                        "lead": "温彦博弹劾李靖",
                        "subject_action": "温彦博譖靖军无纲纪",
                        "observable_result": "太宗后澄清",
                        "period_or_ruler_context": "唐太宗",
                        "projection_targets": [
                            "historical_episode_candidate",
                            "political_risk_profile_candidate",
                        ],
                    },
                ],
            }
        ],
        "unresolved_locators": [],
    }
    worklist_path = tmp_path / "ready/PER-LIJING.json"
    worklist_path.parent.mkdir()
    worklist_path.write_text(json.dumps(worklist, ensure_ascii=False), encoding="utf-8")
    calls = []

    def fetch(**kwargs):
        calls.append(kwargs)
        return WikisourcePageSnapshot(
            page_code="JTS-67",
            requested_title="舊唐書/卷67",
            canonical_title="舊唐書/卷67",
            canonical_url="https://zh.wikisource.org/wiki/舊唐書/卷67",
            revision_id=67,
            revision_timestamp="2026-07-17T00:00:00Z",
            retrieved_at="2026-07-17T00:00:01Z",
            raw_text=raw_text,
            content_hash=sha256(raw_text.encode("utf-8")).hexdigest(),
        )

    first = backfill_person_worklist(
        worklist_path,
        state_dir=tmp_path / "state",
        output_dir=tmp_path / "source",
        service_release_sha="a" * 40,
        fetch=fetch,
    )
    second = backfill_person_worklist(
        worklist_path,
        state_dir=tmp_path / "state",
        output_dir=tmp_path / "source",
        service_release_sha="a" * 40,
        fetch=fetch,
    )

    assert len(first["response"]["passages"]) == 2
    assert first["runtime_audit"]["network_request_count"] == 1
    assert second["runtime_audit"] == {
        "cache_hit": True,
        "provider_call_count": 0,
        "network_request_count": 0,
        "state_write_count": 0,
        "database_write_count": 0,
        "model_call_count": 0,
    }
    assert len(calls) == 1

    passages = first["response"]["passages"]
    talent_passage = next(
        row for row in passages if "PERSON-LIJING:L1" in row["selection_reason"]
    )
    risk_passage = next(
        row for row in passages if "RISK-LIJING:L1" in row["selection_reason"]
    )
    claim_report = {
        "person_ref": "PER-LIJING",
        "response": {
            "output_fingerprint": "b" * 64,
            "coverage_gaps": [],
            "assertions": [
                {
                    "assertion_code": "A-TALENT",
                    "source_passage_ref": talent_passage["passage_id"],
                    "predicate": "平定",
                    "object": "萧铣",
                    "polarity": "affirmed",
                },
                {
                    "assertion_code": "A-RISK-DISPUTED",
                    "source_passage_ref": risk_passage["passage_id"],
                    "predicate": "被弹劾",
                    "object": "军无纲纪",
                    "polarity": "disputed",
                },
                {
                    "assertion_code": "A-RISK-PAGE-NORMAL-EVENT",
                    "source_passage_ref": risk_passage["passage_id"],
                    "subject": "李靖",
                    "predicate": "进军",
                    "object": "定襄",
                    "polarity": "affirmed",
                    "qualifiers": {"event_scope": "普通军事事件"},
                },
            ],
        },
    }
    candidate = build_person_shadow_candidate(first, claim_report)
    assert candidate["profile_candidate"]["talent_assertion_refs"] == ["A-TALENT"]
    assert candidate["profile_candidate"]["political_risk_assertion_refs"] == []
    assert candidate["profile_candidate"]["political_risk_excluded_assertion_refs"] == [
        "A-RISK-DISPUTED",
        "A-RISK-PAGE-NORMAL-EVENT",
    ]
    assert candidate["profile_candidate"]["political_risk_counterevidence_refs"] == []
    assert candidate["historical_episode_exclusions"] == [
        {
            "assertion_ref": "A-RISK-DISPUTED",
            "reason": "disputed_or_negated",
            "source_passage_ref": risk_passage["passage_id"],
        }
    ]
    assert all(value == 0 for value in candidate["formal_writes"].values())


def test_claim_batch_rejects_invalid_budget_and_empty_workset_is_zero_call(
    tmp_path: Path,
) -> None:
    def forbidden_provider():
        raise AssertionError("empty workset must not construct a provider")

    with pytest.raises(ValueError, match="并发和截止时间"):
        claim_ready_sources(
            tmp_path / "source",
            profiles_path=Path("config/claim-extraction-profiles.yml"),
            state_dir=tmp_path / "state",
            output_dir=tmp_path / "output",
            provider_factory=forbidden_provider,
            service_release_sha="a" * 40,
            max_workers=0,
            deadline_seconds=900,
        )

    report = claim_ready_sources(
        tmp_path / "source",
        profiles_path=Path("config/claim-extraction-profiles.yml"),
        state_dir=tmp_path / "state",
        output_dir=tmp_path / "output",
        provider_factory=forbidden_provider,
        service_release_sha="a" * 40,
        max_workers=4,
        deadline_seconds=900,
    )
    assert report["completed"] == []
    assert report["discarded_after_deadline"] == []
    assert report["failed"] == {}
    assert report["not_started"] == []


def test_ready_pipeline_empty_workset_is_zero_model_call_and_within_budget(
    tmp_path: Path,
) -> None:
    report = run_ready_pipeline(
        tmp_path / "ready",
        source_state_dir=tmp_path / "source-state",
        source_report_dir=tmp_path / "source-reports",
        claim_state_dir=tmp_path / "claim-state",
        claim_report_dir=tmp_path / "claim-reports",
        shadow_output_dir=tmp_path / "shadow",
        profiles_path=Path("config/claim-extraction-profiles.yml"),
        output_schema_path=Path("config/claim-extraction-output.schema.json"),
        codex_bin="must-not-run",
        model="gpt-5.6-luna",
        reasoning_effort="low",
        per_claim_timeout_seconds=180,
        service_release_sha="a" * 40,
        source_max_workers=6,
        max_source_documents_per_person=2,
        claim_max_workers=6,
        claim_max_attempts_per_source=2,
        wall_clock_budget_seconds=60,
    )

    assert report["within_budget"] is True
    assert report["source_backfill"]["completed"] == []
    assert report["claim_extraction"]["completed"] == []
    assert report["assembly"]["assembled"] == []
    assert report["formal_writes"] == 0


def test_discovery_ready_pipeline_dispatches_empty_results_without_model_call(
    tmp_path: Path,
) -> None:
    report = run_discovery_ready_pipeline(
        tmp_path / "results",
        tmp_path / "ready",
        source_state_dir=tmp_path / "source-state",
        source_report_dir=tmp_path / "source-reports",
        claim_state_dir=tmp_path / "claim-state",
        claim_report_dir=tmp_path / "claim-reports",
        shadow_output_dir=tmp_path / "shadow",
        profiles_path=Path("config/claim-extraction-profiles.yml"),
        output_schema_path=Path("config/claim-extraction-output.schema.json"),
        codex_bin="must-not-run",
        model="gpt-5.6-luna",
        reasoning_effort="low",
        per_claim_timeout_seconds=180,
        service_release_sha="a" * 40,
        source_max_workers=6,
        max_source_documents_per_person=2,
        claim_max_workers=6,
        claim_max_attempts_per_source=2,
        wall_clock_budget_seconds=60,
    )

    assert report["dispatch"]["ready_people"] == 0
    assert report["pipeline"]["claim_extraction"]["completed"] == []
    assert report["formal_writes"] == 0


def test_source_backfill_batch_rejects_invalid_concurrency(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="source backfill 并发"):
        backfill_ready_people(
            tmp_path / "ready",
            state_dir=tmp_path / "state",
            output_dir=tmp_path / "output",
            service_release_sha="a" * 40,
            max_workers=0,
        )
