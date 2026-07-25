from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from decimal import Decimal
from functools import lru_cache
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
from threading import Event, Lock
import time

import pytest
import yaml

from emperor_v4.evaluation.historical_outcome_cluster import (
    cluster_semantic_fingerprint,
    outcome_episode_ref,
    validate_historical_outcome_registry,
)
from emperor_v4.evaluation.historical_outcome_registry import (
    build_ruler_outcome_bindings,
    build_unbound_historical_outcome_registry,
    materialize_ruler_outcome_registry,
    normalize_outcome_registry_for_public_view,
    public_registry_matches_source_pack,
    render_unbound_historical_outcome_registry_markdown,
    write_current_outcome_layers,
)
from emperor_v4.evaluation.historical_person_profile_registry import (
    build_historical_person_profile_registry,
    render_historical_person_profile_registry_markdown,
)
from emperor_v4.adapters.historical_entity_identity import HistoricalEntityResolver
from emperor_v4.adapters.shared_neutral_extraction import (
    build_shared_neutral_fact_fanout,
)
from emperor_v4.adapters.source_text_index import LocalSourceTextIndex, build_local_source_index
from emperor_v4.adapters.structured_output_contract import validate_codex_output_schema
from emperor_v4.evaluation.current_source_pack_compiler import (
    SCHEMA_VERSION as SOURCE_PACK_INCREMENT_SCHEMA_VERSION,
    apply_source_pack_increment,
    compile_outcome_candidate_payloads,
    compile_source_pack_increment,
)
from emperor_v4.evaluation import (
    current_source_pack_compiler as current_source_pack_compiler_module,
)
from emperor_v4.evaluation.i5b_current_value_runner import (
    _appointment_window_outcomes,
    _ruler_window_outcomes,
    build_i5b_current_value as _build_i5b_current_value,
    main as runner_main,
    render_scoring_detail_markdown,
)
from emperor_v4.eval import main as eval_main
from emperor_v4.runtime.emperor_rebuild import (
    RebuildLimits,
    _accept_stage,
    _project_event_signatures_for_ruler,
    _resolve_source_index,
    _restore_stage_artifacts,
    _ruler_backbone_fact_refs,
    _run_with_model_anomaly_recovery,
    _shared_backbone_identity,
    _shared_backbone_contract,
    _shared_current_has_complete_subject_coverage,
    _shared_subject_coverage,
)
from emperor_v4.runtime import (
    dynasty_governance_session,
    emperor_rebuild as emperor_rebuild_module,
    emperor_session_control,
)
from emperor_v4.runtime.emperor_neutral_scan import (
    NEUTRAL_EXTRACTION_POLICY_VERSION,
    _canonicalize_result,
    _digest as neutral_digest,
    build_backbone_event_signatures,
    build_chronicle_role_projections,
    build_deterministic_backbone_event_signatures,
    build_deterministic_fact_resolution_plan,
    build_event_directed_neutral_plan,
    build_high_value_reject_review,
    build_ruler_neutral_plan,
    extract_current_neutral_materials,
    merge_dynasty_governance_current,
    seed_deterministic_campaign_facts,
)
from emperor_v4.runtime.emperor_outcome_projection import (
    PROJECTION_POLICY_VERSION,
    _expand_fact_quote_to_same_revision_paragraph,
    _normalize_candidate_sources,
    _validate_candidate_payload_coverage,
    build_outcome_transport_schema,
    project_current_outcomes,
)
from emperor_v4.runtime.deterministic_campaign_extraction import (
    discover_deterministic_backbone_campaigns,
)
from emperor_v4.runtime.dynasty_governance_rebuild import (
    dynasty_governance_catalog_fingerprint,
    load_dynasty_governance_catalog_entry,
    validate_dynasty_governance_current_catalog,
)
from emperor_v4.runtime.structured_codex_runner import (
    ModelBatchAnomalyError,
    StructuredCodexRunner,
)


ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=None)
def _cached_current_value_report(source_pack_path: str) -> dict:
    return _build_i5b_current_value(Path(source_pack_path))


def build_i5b_current_value(source_pack_path: Path, **kwargs) -> dict:
    """Reuse immutable checked-in source packs within this regression module."""
    resolved = Path(source_pack_path).resolve()
    current_root = (ROOT / "eval/i5b_current_value").resolve()
    if not kwargs and resolved.is_relative_to(current_root):
        return deepcopy(_cached_current_value_report(str(resolved)))
    return _build_i5b_current_value(source_pack_path, **kwargs)


def test_actorless_public_result_is_preserved_before_attribution() -> None:
    batch = {
        "batch_ref": "BATCH-ACTORLESS",
        "page_title": "史书/卷一",
        "work_title": "史书",
        "source_url": "local:test",
        "revision_ref": "1",
        "segments": [
            {
                "segment_ref": "SEG-ACTORLESS",
                "text": "米价下降，商旅野次，无复盗贼。",
                "text_sha256": "a" * 64,
                "subject_refs": [],
            }
        ],
    }
    plan = {
        "schema_version": "subject-shared-review-plan-v1",
        "source_index_identity": "INDEX-1",
        "mention_index_fingerprint": "MENTION-1",
        "page_batches": [batch],
    }
    result = {
        "schema_version": "shared-neutral-extraction-output-v2",
        "batch_ref": batch["batch_ref"],
        "page_title": batch["page_title"],
        "revision_ref": batch["revision_ref"],
        "segment_count": 1,
        "segment_reviews": [
            {
                "segment_ref": "SEG-ACTORLESS",
                "decision": "accept",
                "context_status": "sufficient",
                "facts": [
                    {
                        "fact_id": "F1",
                        "exact_quote": "米价下降，商旅野次，无复盗贼。",
                        "evidence_span_refs": ["SPAN-1"],
                        "fact_kind": "other_material_fact",
                        "evidence_roles": ["public_result"],
                        "effect_domains": [
                            "productivity_livelihood",
                            "state_people_security",
                        ],
                        "action_summary": "记录米价与治安公共结果",
                        "actors": [],
                        "implementation_status": "not_shown",
                        "result": "米价下降且商旅无盗",
                        "legacy_status": "not_shown",
                        "legacy_basis": "",
                        "projection_eligibility": "direct_neutral_fact",
                        "outcome_candidate_status": "linkable_chain_fact",
                        "outcome_candidate_reason": "可与措施和责任事实闭合。",
                        "uncertainty": "",
                    }
                ],
                "reason": "",
            }
        ],
        "limitations": [],
    }

    fanout = build_shared_neutral_fact_fanout(plan, [result])

    assert fanout["fact_count"] == 1
    assert fanout["person_count"] == 0
    assert fanout["facts"][0]["actors"] == []
    assert fanout["facts"][0]["evidence_roles"] == ["public_result"]


def _campaign_candidate_payload(*, relation: str | None = "frontline_command") -> dict:
    member = {
        "actor_name": "李世民",
        "actor_kind": "ruler",
        "role_code": (
            "not_in_command_chain"
            if relation == "authorization_only"
            else "commander_in_chief"
        ),
        "talent_credit": "not_applicable",
        "sovereign_at_event": True,
        "ruler_campaign_relation": relation,
        "authorization_mode": "explicit" if relation else None,
        "control_extent": (
            "sustained"
            if relation in {"operational_direction", "frontline_command"}
            else None
        ),
        "obstruction_status": "none" if relation else None,
        "contribution_scope": "亲征并承担前线核心统帅责任",
        "contribution_types": ["implementation_lead"],
        "contribution_basis_fact_refs": ["NEUTRALFACT-TEST"],
        "responsibility_scope": "not_applicable",
        "authorization_quotes": [],
    }
    return {
        "schema_version": "current-outcome-candidate-output-v3",
        "task_code": "TEST-CAMPAIGN-CONTRACT",
        "candidates": [
            {
                "candidate_key": "test-campaign-contract",
                "canonical_label": "测试战役",
                "source_page": "史书/卷一",
                "revision_ref": "1",
                "exact_quotes": ["测试战役取得阶段结果。"],
                "evidence_links": [
                    {
                        "fact_ref": "NEUTRALFACT-TEST",
                        "source_page": "史书/卷一",
                        "revision_ref": "1",
                        "exact_quote": "测试战役取得阶段结果。",
                        "evidence_roles": [
                            "implementation_or_operation",
                            "public_result",
                            "responsibility_or_attribution",
                        ],
                    }
                ],
                "neutral_summary": "测试战役取得阶段结果。",
                "period_start": "贞观元年",
                "period_end": "贞观元年",
                "origin": "ruler_chronicle",
                "outcome_kind": "campaign",
                "settlement_scope": "ruler_campaign_parent",
                "result_status": "completed",
                "result_direction": "positive",
                "observable_result": "取得阶段结果",
                "scale_level": "regional",
                "scale_basis": "regional_theater_control",
                "decisiveness": "major",
                "scale_reason": "形成区域战果",
                "stable_delivery": True,
                "important_method_or_legacy": False,
                "ruler_window_status": "within_window",
                "members": [member],
                "payload": {
                    "domain": None,
                    "foundational": None,
                    "durable_cross_stage": None,
                    "authorization_status": None,
                    "causal_attribution_status": None,
                    "theater": "测试战区",
                    "strategic_objective": "取得区域目标",
                    "battle_result": "victory",
                    "objective_completion": "partial",
                    "opponent_condition": "viable",
                    "opponent_strategic_weight": "regional_major",
                    "strategic_result_class": "major_stage_or_crisis",
                    "campaign_tier": "A",
                    "campaign_tier_basis": "土地轴=important_region；对手轴=regional_major/viable；结果轴=victory/partial，完成重要区域阶段目标，定A。",
                    "land_strategic_value": "important_region",
                    "strategic_stakes": "major",
                    "prewar_context": "开战前需要夺取测试区域目标，对手仍具完整作战能力。",
                    "failure_stakes": "若失败将造成重要区域或战区阶段损失，但不会直接导致国家核心崩溃。",
                    "combat_difficulty": "D1",
                    "combat_difficulty_basis": "常态可战对手，未见额外极端困难。",
                    "operational_costs": [],
                    "objective_shortfalls": [],
                    "attributable_failures": [],
                },
                "limitations": [],
            }
        ],
        "rejections": [],
    }


def _campaign_contract_index(tmp_path: Path) -> LocalSourceTextIndex:
    index_path = tmp_path / "campaign-contract.sqlite3"
    build_local_source_index(
        [
            {
                "page_title": "史书/卷一",
                "work_title": "史书",
                "source_url": "local:test",
                "revision_ref": "1",
                "raw_text": "测试战役取得阶段结果。",
            }
        ],
        index_path,
    )
    return LocalSourceTextIndex(index_path)


def _governance_candidate_payload(*, role_code: str = "lead") -> dict:
    payload = _campaign_candidate_payload()
    candidate = payload["candidates"][0]
    candidate.update(
        {
            "candidate_key": "test-governance-contract",
            "canonical_label": "测试治理成果",
            "outcome_kind": "governance",
            "settlement_scope": "governance_result",
            "scale_level": "important",
            "scale_basis": "important_public_result",
            "members": [
                {
                    "actor_name": "李世民",
                    "actor_kind": "ruler",
                    "role_code": role_code,
                    "ruler_campaign_relation": None,
                    "contribution_scope": "主导制度并形成公共结果",
                    "contribution_types": ["implementation_lead"],
                    "contribution_basis_fact_refs": ["NEUTRALFACT-TEST"],
                    "responsibility_scope": "major_affairs",
                    "authorization_quotes": ["测试战役取得阶段结果。"],
                }
            ],
            "payload": {
                "domain": "central_institutions",
                "foundational": False,
                "durable_cross_stage": False,
                "authorization_status": "explicit",
                "causal_attribution_status": "established",
                "value_judgment": {
                    "comparison_basis": "inferred_prior_state",
                    "baseline_fact_refs": [],
                    "overall_direction": "positive",
                    "overall_magnitude": "significant",
                    "axes": {
                        "productivity_livelihood": {
                            "direction": "positive",
                            "magnitude": "significant",
                            "basis_fact_refs": ["NEUTRALFACT-TEST"],
                            "basis": "形成公共收益。",
                        },
                        "civilization_institutions": {
                            "direction": "positive",
                            "magnitude": "significant",
                            "basis_fact_refs": ["NEUTRALFACT-TEST"],
                            "basis": "制度投入运行。",
                        },
                        "state_people_security": {
                            "direction": "not_established",
                            "magnitude": "not_established",
                            "basis_fact_refs": [],
                            "basis": "",
                        },
                        "culture_education_thought": {
                            "direction": "not_established",
                            "magnitude": "not_established",
                            "basis_fact_refs": [],
                            "basis": "",
                        },
                    },
                    "effect_horizon": "long",
                    "basis": "基线：既有制度尚未形成该公共收益；变化：制度投入运行；结果：材料记载已经形成公共收益。",
                },
                "theater": None,
                "strategic_objective": None,
                "battle_result": None,
                "objective_completion": None,
                "opponent_condition": None,
                "opponent_strategic_weight": None,
                "strategic_result_class": None,
                "campaign_tier": None,
                "campaign_tier_basis": None,
                "land_strategic_value": None,
                "combat_difficulty": None,
                "combat_difficulty_basis": None,
                "operational_costs": None,
                "objective_shortfalls": None,
                "attributable_failures": None,
            },
        }
    )
    return payload


def test_governance_candidate_compiles_cross_source_lineage_once(
    tmp_path: Path,
) -> None:
    source_pack = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    index_path = tmp_path / "cross-source.sqlite3"
    build_local_source_index(
        [
            {
                "page_title": "政书/卷一",
                "work_title": "政书",
                "source_url": "local:governance",
                "revision_ref": "1",
                "raw_text": "下令修订制度并颁行天下。",
            },
            {
                "page_title": "列传/卷二",
                "work_title": "列传",
                "source_url": "local:biography",
                "revision_ref": "2",
                "raw_text": "测试人物持续主持施行，制度遂定。",
            },
        ],
        index_path,
    )
    payload = _governance_candidate_payload()
    candidate = payload["candidates"][0]
    candidate["source_page"] = "政书/卷一"
    candidate["revision_ref"] = "1"
    candidate["exact_quotes"] = [
        "下令修订制度并颁行天下。",
        "测试人物持续主持施行，制度遂定。",
    ]
    candidate["evidence_links"] = [
        {
            "fact_ref": "NEUTRALFACT-MEASURE",
            "source_page": "政书/卷一",
            "revision_ref": "1",
            "exact_quote": "下令修订制度并颁行天下。",
            "evidence_roles": [
                "measure_or_design",
                "implementation_or_operation",
                "public_result",
            ],
        },
        {
            "fact_ref": "NEUTRALFACT-RESPONSIBILITY",
            "source_page": "列传/卷二",
            "revision_ref": "2",
            "exact_quote": "测试人物持续主持施行，制度遂定。",
            "evidence_roles": [
                "continuity_or_reversal",
                "responsibility_or_attribution",
            ],
        },
    ]
    candidate["members"][0]["authorization_quotes"] = [
        "下令修订制度并颁行天下。"
    ]
    candidate["members"][0]["contribution_basis_fact_refs"] = [
        "NEUTRALFACT-MEASURE",
        "NEUTRALFACT-RESPONSIBILITY",
    ]
    judgment = candidate["payload"]["value_judgment"]
    for axis in judgment["axes"].values():
        if axis["direction"] != "not_established":
            axis["basis_fact_refs"] = [
                "NEUTRALFACT-MEASURE",
                "NEUTRALFACT-RESPONSIBILITY",
            ]

    increment = compile_outcome_candidate_payloads(
        source_pack,
        [payload],
        source_index=LocalSourceTextIndex(index_path),
        schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
    )

    assert len(increment["outcomes"]) == 1
    assert {row["record_ref"] for row in increment["facts"]} == {
        "NEUTRALFACT-MEASURE",
        "NEUTRALFACT-RESPONSIBILITY",
    }
    assert increment["outcomes"][0]["fact_refs"] == [
        "NEUTRALFACT-MEASURE",
        "NEUTRALFACT-RESPONSIBILITY",
    ]
    assert len(increment["outcomes"][0]["source_refs"]) == 2


def test_dynasty_governance_named_creator_joins_public_roster(
    tmp_path: Path,
) -> None:
    source_pack = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    quote = "孟简主持开浚孟渎，得沃壤四千余顷。"
    index_path = tmp_path / "dynasty-governance-attribution.sqlite3"
    build_local_source_index(
        [
            {
                "page_title": "政书/卷一",
                "work_title": "政书",
                "source_url": "local:governance",
                "revision_ref": "1",
                "raw_text": quote,
            }
        ],
        index_path,
    )
    payload = _governance_candidate_payload()
    candidate = payload["candidates"][0]
    candidate.update(
        {
            "origin": "dynasty_governance",
            "source_page": "政书/卷一",
            "revision_ref": "1",
            "exact_quotes": [quote],
            "neutral_summary": "孟简主持开浚孟渎并形成沃壤。",
            "observable_result": "开浚孟渎后形成沃壤四千余顷。",
            "evidence_links": [
                {
                    "fact_ref": "NEUTRALFACT-TEST",
                    "source_page": "政书/卷一",
                    "revision_ref": "1",
                    "exact_quote": quote,
                    "evidence_roles": [
                        "implementation_or_operation",
                        "public_result",
                        "responsibility_or_attribution",
                    ],
                }
            ],
        }
    )
    candidate["members"][0].update(
        {
            "actor_name": "孟简",
            "actor_kind": "person",
            "contribution_scope": "主持开浚孟渎并交付沃壤结果",
            "contribution_types": ["implementation_lead", "operational_delivery"],
            "authorization_quotes": [quote],
        }
    )

    increment = compile_outcome_candidate_payloads(
        source_pack,
        [payload],
        source_index=LocalSourceTextIndex(index_path),
        schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
    )
    member = increment["outcomes"][0]["members"][0]
    assert member["actor_name"] == "孟简"
    assert member["actor_ref"].startswith("PER-V4-")

    compiled = compile_source_pack_increment(source_pack, increment)
    assert {
        (row["person"], row["person_ref"]) for row in compiled["members"]
    } >= {("孟简", member["actor_ref"])}


def test_dynasty_governance_new_actor_requires_verbatim_name(
    tmp_path: Path,
) -> None:
    source_pack = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    payload = _governance_candidate_payload()
    candidate = payload["candidates"][0]
    candidate["origin"] = "dynasty_governance"
    candidate["members"][0].update(
        {"actor_name": "未见于引文者", "actor_kind": "person"}
    )
    with pytest.raises(ValueError, match="参与者不属于当前皇帝或团队"):
        compile_outcome_candidate_payloads(
            source_pack,
            [payload],
            source_index=_campaign_contract_index(tmp_path),
            schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
        )


def test_dynasty_governance_session_reaches_review_without_ruler_lease(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    index_root = tmp_path / "indexes"
    index_root.mkdir()
    index_path = index_root / "han.sqlite3"
    build_local_source_index(
        [
            {
                "page_title": "漢書/卷019",
                "work_title": "漢書",
                "source_url": "local:han",
                "revision_ref": "1",
                "raw_text": "漢朝治理材料。",
            }
        ],
        index_path,
    )

    def fake_rebuild(**kwargs: object) -> dict:
        runtime_root = Path(str(kwargs["runtime_root"]))
        current = {
            "schema_version": "dynasty-governance-current-v2",
            "status": "quality_accepted_shadow",
            "dynasty": "西汉",
            "dynasty_token": "HAN",
            "input_fingerprint": "INPUT-HAN",
            "source_index_identity": LocalSourceTextIndex(index_path).identity,
            "chains": [],
        }
        target = runtime_root / "HAN/current.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(current, ensure_ascii=False), encoding="utf-8"
        )
        return {"model_call_count": 0, "reused": True}

    monkeypatch.setattr(
        dynasty_governance_session, "rebuild_dynasty_governance", fake_rebuild
    )
    monkeypatch.setattr(
        dynasty_governance_session,
        "project_current_outcomes",
        lambda **_kwargs: {
            "status": "awaiting_main_session_review",
            "review_worklist": {
                "schema_version": "current-outcome-main-review-worklist-v1",
                "task_code": "DYNASTY-HAN-REVIEW",
                "facts": [],
            },
        },
    )

    report = dynasty_governance_session.run_dynasty_governance_session(
        workspace_root=ROOT,
        source_index_root=index_root,
        runtime_root=tmp_path / "runtime",
        dynasty="汉",
    )

    assert report["status"] == "awaiting_review"
    assert report["dynasty"] == "西汉"
    assert report["dynasty_token"] == "HAN"
    assert Path(report["outcome_worklist"]).is_file()
    assert not (tmp_path / "runtime/session-control").exists()

    review_path = tmp_path / "han-review.json"
    review_path.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        dynasty_governance_session,
        "project_current_outcomes",
        lambda **_kwargs: {"status": "quality_accepted"},
    )
    accepted = dynasty_governance_session.run_dynasty_governance_session(
        workspace_root=ROOT,
        source_index_root=index_root,
        runtime_root=tmp_path / "runtime",
        dynasty="汉",
        outcome_review_path=review_path,
    )
    handoff = json.loads(
        Path(accepted["handoff"]).read_text(encoding="utf-8")
    )
    assert accepted["status"] == "quality_accepted"
    assert handoff["dynasty_token"] == "HAN"
    assert Path(handoff["outcome_registry_current"]).is_file()
    assert handoff["outcome_count"] == 0


def test_outcome_projection_normalizes_governance_window_scope() -> None:
    payload = _governance_candidate_payload()
    candidate = payload["candidates"][0]
    candidate["settlement_scope"] = "person_governance_result"
    candidate["ruler_window_status"] = "leadership_formation"
    facts = [
        {
            "fact_ref": "NEUTRALFACT-TEST",
            "segment_ref": "SEG-TEST",
            "page_title": "史书/卷一",
            "revision_ref": "1",
            "exact_quote": "测试战役取得阶段结果。",
        }
    ]

    normalized = _normalize_candidate_sources(payload, facts)

    assert normalized["candidates"][0]["settlement_scope"] == "governance_result"

    payload = _governance_candidate_payload()
    candidate = payload["candidates"][0]
    candidate["settlement_scope"] = "person_statecraft_result"
    candidate["ruler_window_status"] = "outside_window"

    normalized = _normalize_candidate_sources(payload, facts)

    assert normalized["candidates"][0]["settlement_scope"] == (
        "person_governance_result"
    )


def test_outcome_projection_preserves_declared_fact_refs_after_quote_expansion() -> None:
    payload = _governance_candidate_payload()
    candidate = payload["candidates"][0]
    candidate["evidence_links"][0]["fact_ref"] = "LEGACY-FACT-TEST"
    candidate["members"][0]["contribution_basis_fact_refs"] = [
        "LEGACY-FACT-TEST"
    ]
    for axis in candidate["payload"]["value_judgment"]["axes"].values():
        axis["basis_fact_refs"] = [
            "LEGACY-FACT-TEST"
            for _ in axis["basis_fact_refs"]
        ]
    candidate["evidence_links"].append(
        {
            "fact_ref": "LEGACY-FACT-COST",
            "source_page": "史书/卷一",
            "revision_ref": "1",
            "exact_quote": "工程因岁饥而停止。后续另有议论。",
            "evidence_roles": ["public_cost_or_harm"],
        }
    )
    candidate["payload"]["value_judgment"]["axes"][
        "productivity_livelihood"
    ]["basis_fact_refs"] = ["LEGACY-FACT-COST"]
    facts = [
        {
            "fact_ref": "NEUTRALFACT-TEST",
            "segment_ref": "SEG-TEST",
            "page_title": "史书/卷一",
            "revision_ref": "1",
            "exact_quote": "测试战役取得阶段结果。",
        },
        {
            "fact_ref": "NEUTRALFACT-COST",
            "segment_ref": "SEG-COST",
            "page_title": "史书/卷一",
            "revision_ref": "1",
            "exact_quote": "工程因岁饥而停止。",
        },
    ]

    normalized = _normalize_candidate_sources(payload, facts)

    assert {
        row["fact_ref"] for row in normalized["candidates"][0]["evidence_links"]
    } == {"NEUTRALFACT-TEST", "NEUTRALFACT-COST"}
    assert normalized["candidates"][0]["payload"]["value_judgment"]["axes"][
        "productivity_livelihood"
    ]["basis_fact_refs"] == ["NEUTRALFACT-COST"]


def test_outcome_projection_normalizes_ruler_talent_credit() -> None:
    payload = _campaign_candidate_payload()
    candidate = payload["candidates"][0]
    candidate["members"][0].pop("talent_credit")
    facts = [
        {
            "segment_ref": "SEG-TEST",
            "page_title": "史书/卷一",
            "revision_ref": "1",
            "exact_quote": "测试战役取得阶段结果。",
        }
    ]

    normalized = _normalize_candidate_sources(payload, facts)

    assert normalized["candidates"][0]["members"][0]["talent_credit"] == (
        "not_applicable"
    )


def test_outcome_projection_normalizes_direct_ruler_command_relation() -> None:
    payload = _campaign_candidate_payload(relation="operational_direction")
    candidate = payload["candidates"][0]
    candidate["members"][0]["role_code"] = "commander_in_chief"
    candidate["members"][0]["authorization_quotes"] = ["皇帝命诸军攻城。"]
    candidate["exact_quotes"] = ["皇帝命诸军攻城，遂克都城。"]
    candidate["period_start"] = "618-11"
    candidate["period_end"] = "618-11"
    candidate["ruler_window_status"] = "leadership_formation"
    facts = [
        {
            "segment_ref": "SEG-TEST",
            "page_title": "史书/卷一",
            "revision_ref": "1",
            "period": None,
            "exact_quote": "皇帝命诸军攻城，遂克都城。",
        }
    ]

    normalized = _normalize_candidate_sources(payload, facts)
    normalized_candidate = normalized["candidates"][0]

    assert normalized_candidate["members"][0]["ruler_campaign_relation"] == (
        "operational_direction"
    )
    assert normalized_candidate["period_start"] == "创业期"
    assert normalized_candidate["period_end"] == "创业期"


def test_outcome_projection_binds_li_yuan_pre_accession_context() -> None:
    payload = _governance_candidate_payload()
    candidate = payload["candidates"][0]
    candidate["members"][0]["actor_name"] = "李渊"
    candidate["ruler_window_status"] = "within_window"
    candidate["period_start"] = "武德元年"
    candidate["period_end"] = "武德元年"
    candidate["exact_quotes"] = ["唐公入城，迎代王，与民约法，悉除隋苛禁。"]
    candidate["members"][0]["authorization_quotes"] = list(
        candidate["exact_quotes"]
    )
    facts = [
        {
            "segment_ref": "SEG-TEST",
            "page_title": "史书/卷一",
            "revision_ref": "1",
            "exact_quote": candidate["exact_quotes"][0],
        }
    ]

    normalized = _normalize_candidate_sources(payload, facts)
    normalized_candidate = normalized["candidates"][0]

    assert normalized_candidate["ruler_window_status"] == "outside_window"
    assert normalized_candidate["settlement_scope"] == "person_governance_result"
    assert normalized_candidate["period_start"] == "创业期"


def test_outcome_projection_rejects_palace_seizure_governance() -> None:
    payload = _governance_candidate_payload()
    candidate = payload["candidates"][0]
    candidate["canonical_label"] = "玄武门之变后平定宫廷军乱"
    facts = [
        {
            "segment_ref": "SEG-TEST",
            "page_title": "史书/卷一",
            "revision_ref": "1",
            "exact_quote": "测试战役取得阶段结果。",
        }
    ]

    normalized = _normalize_candidate_sources(payload, facts)

    assert normalized["candidates"] == []
    assert "夺权或宫廷清洗" in normalized["rejections"][0]["reason"]


def test_outcome_projection_rejects_disguised_palace_seizure_governance() -> None:
    payload = _governance_candidate_payload()
    candidate = payload["candidates"][0]
    candidate["canonical_label"] = "授权处置军队并平定宫廷冲突"
    source_quote = (
        "秦王以太子、齐王作乱，举兵诛之。"
        "敬德请降手敕，令诸军并受秦王处分，上从之。"
    )
    candidate["exact_quotes"] = [source_quote]
    candidate["members"][0]["authorization_quotes"] = [source_quote]
    facts = [
        {
            "segment_ref": "SEG-TEST",
            "page_title": "史书/卷一",
            "revision_ref": "1",
            "exact_quote": source_quote,
        }
    ]

    normalized = _normalize_candidate_sources(payload, facts)

    assert normalized["candidates"] == []
    assert "夺权或宫廷清洗" in normalized["rejections"][0]["reason"]


def test_outcome_projection_normalizes_chang_an_command_relation() -> None:
    payload = _campaign_candidate_payload(relation="operational_direction")
    candidate = payload["candidates"][0]
    candidate["members"][0]["actor_name"] = "李渊"
    source_quote = "甲辰，李渊命诸攻城。军头雷永吉先登，遂克长安。"
    candidate["exact_quotes"] = [source_quote]
    candidate["members"][0]["authorization_quotes"] = ["李渊命诸攻城"]
    facts = [
        {
            "segment_ref": "SEG-TEST",
            "page_title": "史书/卷一",
            "revision_ref": "1",
            "exact_quote": source_quote,
        }
    ]

    normalized = _normalize_candidate_sources(payload, facts)

    assert normalized["candidates"][0]["members"][0][
        "ruler_campaign_relation"
    ] == "operational_direction"


def test_outcome_projection_does_not_invent_cross_stage_durability() -> None:
    payload = _governance_candidate_payload()
    candidate = payload["candidates"][0]
    candidate["payload"]["durable_cross_stage"] = True
    candidate["limitations"] = ["原文未说明持续执行范围及后续制度寿命。"]
    facts = [
        {
            "segment_ref": "SEG-TEST",
            "page_title": "史书/卷一",
            "revision_ref": "1",
            "exact_quote": candidate["exact_quotes"][0],
        }
    ]

    normalized = _normalize_candidate_sources(payload, facts)

    assert normalized["candidates"][0]["payload"]["durable_cross_stage"] is False


def test_outcome_projection_requires_explicit_legal_governance_candidate() -> None:
    fact = {
        "segment_ref": "SEG-LAW",
        "exact_quote": "唐公入城，迎代王，与民约法十二条，悉除隋苛禁。",
    }
    payload = {
        "candidates": [
            {
                "outcome_kind": "campaign",
                "exact_quotes": [fact["exact_quote"]],
            }
        ],
        "rejections": [],
    }

    with pytest.raises(ValueError, match="独立 governance"):
        _validate_candidate_payload_coverage(payload, [fact])


def test_outcome_projection_requires_explicit_chang_an_campaign_candidate() -> None:
    fact = {
        "segment_ref": "SEG-CAMPAIGN",
        "exact_quote": "军头雷永吉先登，遂克长安。与民约法十二条，悉除隋苛禁。",
    }
    payload = {
        "candidates": [
            {
                "outcome_kind": "governance",
                "exact_quotes": [fact["exact_quote"]],
            }
        ],
        "rejections": [],
    }

    with pytest.raises(ValueError, match="独立 campaign"):
        _validate_candidate_payload_coverage(payload, [fact])


def test_outcome_projection_maps_operational_cost_quote_terminal_punctuation() -> None:
    payload = _campaign_candidate_payload()
    candidate = payload["candidates"][0]
    candidate["payload"]["operational_costs"] = [
        {
            "basis": "测试",
            "exact_quotes": ["前军战小却。"],
        }
    ]
    facts = [
        {
            "segment_ref": "SEG-TEST",
            "page_title": "史书/卷一",
            "revision_ref": "1",
            "exact_quote": "测试战役取得阶段结果，前军战小却，后军继进。",
        }
    ]

    normalized = _normalize_candidate_sources(payload, facts)

    assert normalized["candidates"][0]["payload"][
        "operational_costs"
    ][0]["exact_quotes"] == ["前军战小却"]


def test_outcome_projection_expands_quote_to_same_revision_paragraph(
    tmp_path: Path,
) -> None:
    index_path = tmp_path / "source.sqlite3"
    paragraph = "皇帝命诸军攻城。军士先登，遂克都城。与民约法，悉除苛禁。"
    build_local_source_index(
        [
            {
                "page_title": "史书/卷一",
                "work_title": "史书",
                "source_url": "local:test",
                "revision_ref": "1",
                "raw_text": f"前段。<BR>\n{paragraph}<BR>\n后段。",
            }
        ],
        index_path,
    )
    index = LocalSourceTextIndex(index_path)
    page = next(index.iter_pages(works=["史书"], page_titles=["史书/卷一"]))

    expanded = _expand_fact_quote_to_same_revision_paragraph(
        {
            "page_title": "史书/卷一",
            "revision_ref": "1",
            "exact_quote": "皇帝命诸军攻城。",
        },
        pages_by_title={page.page_title: page},
    )

    assert expanded["exact_quote"] == paragraph


def test_outcome_projection_restores_dropped_paragraph_whitespace(
    tmp_path: Path,
) -> None:
    index_path = tmp_path / "source.sqlite3"
    paragraph = "弘道元年十二月。遗诏废之。\n\n　　文明元年二月。改为道观。"
    build_local_source_index(
        [
            {
                "page_title": "史书/卷一",
                "work_title": "史书",
                "source_url": "local:test",
                "revision_ref": "1",
                "raw_text": f"前段。\n\n{paragraph}\n\n后段。",
            }
        ],
        index_path,
    )
    index = LocalSourceTextIndex(index_path)
    page = next(index.iter_pages(works=["史书"], page_titles=["史书/卷一"]))

    expanded = _expand_fact_quote_to_same_revision_paragraph(
        {
            "page_title": "史书/卷一",
            "revision_ref": "1",
            "exact_quote": "弘道元年十二月。遗诏废之。文明元年二月。改为道观。",
        },
        pages_by_title={page.page_title: page},
    )

    assert expanded["exact_quote"] == paragraph


def test_outcome_projection_rejects_candidate_disclaiming_quote_support() -> None:
    payload = _governance_candidate_payload()
    candidate = payload["candidates"][0]
    candidate["limitations"] = ["关键治理结果未在 exact_quote 中展开。"]
    facts = [
        {
            "segment_ref": "SEG-TEST",
            "page_title": "史书/卷一",
            "revision_ref": "1",
            "exact_quote": "测试战役取得阶段结果。",
        }
    ]

    normalized = _normalize_candidate_sources(payload, facts)

    assert normalized["candidates"] == []
    assert normalized["rejections"] == [
        {
            "fact_ref": "NEUTRALFACT-TEST",
            "reason": (
                "test-governance-contract 自认关键结果未由 exact_quote "
                "直接支持，确定性拒绝并保留中性材料。"
            ),
        }
    ]


def test_outcome_projection_rejects_summary_only_quote_support() -> None:
    payload = _governance_candidate_payload()
    candidate = payload["candidates"][0]
    candidate["limitations"] = [
        "exact_quote直接记载命令，治理结果依据来自同一输入事实的action_summary与result字段。"
    ]
    facts = [
        {
            "segment_ref": "SEG-TEST",
            "page_title": "史书/卷一",
            "revision_ref": "1",
            "exact_quote": "测试战役取得阶段结果。",
        }
    ]

    normalized = _normalize_candidate_sources(payload, facts)

    assert normalized["candidates"] == []
    assert "未由 exact_quote 直接支持" in normalized["rejections"][0]["reason"]


def test_outcome_projection_rejects_payload_omitting_input_segment() -> None:
    facts = [
        {
            "segment_ref": "SEG-ONE",
            "exact_quote": "第一项事实已经完成。",
        },
        {
            "segment_ref": "SEG-TWO",
            "exact_quote": "第二项事实已经完成。",
        },
    ]
    payload = {
        "candidates": [],
        "rejections": [{"segment_ref": "SEG-ONE", "reason": "明确拒绝"}],
    }

    with pytest.raises(ValueError, match="SEG-TWO"):
        _validate_candidate_payload_coverage(payload, facts)


def test_outcome_projection_accepts_candidate_covering_shared_segment() -> None:
    facts = [
        {
            "segment_ref": "SEG-SHARED",
            "exact_quote": "军士先登，遂克都城。",
        },
        {
            "segment_ref": "SEG-SHARED",
            "exact_quote": "军士先登，遂克都城。",
        },
    ]
    payload = {
        "candidates": [{"exact_quotes": ["遂克都城"]}],
        "rejections": [],
    }

    _validate_candidate_payload_coverage(payload, facts)


def test_outcome_projection_declared_fact_link_does_not_absorb_neighbour_fact() -> None:
    payload = _governance_candidate_payload()
    candidate = payload["candidates"][0]
    candidate["exact_quotes"] = ["同段制度施行，形成甲项结果。"]
    candidate["evidence_links"][0].update(
        {
            "fact_ref": "NEUTRALFACT-ONE",
            "exact_quote": "同段制度施行，形成甲项结果。",
        }
    )
    candidate["members"][0]["contribution_basis_fact_refs"] = ["NEUTRALFACT-ONE"]
    candidate["members"][0]["authorization_quotes"] = [
        "同段制度施行，形成甲项结果。"
    ]
    judgment = candidate["payload"]["value_judgment"]
    judgment["axes"]["productivity_livelihood"]["basis_fact_refs"] = [
        "NEUTRALFACT-ONE"
    ]
    judgment["axes"]["civilization_institutions"]["basis_fact_refs"] = [
        "NEUTRALFACT-ONE"
    ]
    facts = [
        {
            "fact_ref": "NEUTRALFACT-ONE",
            "segment_ref": "SEG-SHARED",
            "page_title": "史书/卷一",
            "revision_ref": "1",
            "exact_quote": "同段制度施行，形成甲项结果。",
            "evidence_roles": ["implementation_or_operation", "public_result"],
        },
        {
            "fact_ref": "NEUTRALFACT-TWO",
            "segment_ref": "SEG-SHARED",
            "page_title": "史书/卷一",
            "revision_ref": "1",
            "exact_quote": "同段制度施行，形成甲项结果。另有乙项结果。",
            "evidence_roles": ["implementation_or_operation", "public_result"],
        },
    ]

    normalized = _normalize_candidate_sources(payload, facts)

    assert [
        row["fact_ref"]
        for row in normalized["candidates"][0]["evidence_links"]
    ] == ["NEUTRALFACT-ONE"]


def test_outcome_projection_rejects_victory_without_result_quote() -> None:
    payload = _campaign_candidate_payload()
    candidate = payload["candidates"][0]
    candidate["payload"]["objective_completion"] = "complete"
    candidate["exact_quotes"] = ["皇帝命诸军攻城。"]
    candidate["members"][0]["authorization_quotes"] = ["皇帝命诸军攻城。"]
    facts = [
        {
            "segment_ref": "SEG-TEST",
            "page_title": "史书/卷一",
            "revision_ref": "1",
            "exact_quote": "皇帝命诸军攻城。",
        }
    ]

    normalized = _normalize_candidate_sources(payload, facts)

    assert normalized["candidates"] == []
    assert "exact_quote 缺少结果信号" in normalized["rejections"][0]["reason"]


def test_outcome_projection_rejects_missing_governance_result_support() -> None:
    payload = _governance_candidate_payload()
    candidate = payload["candidates"][0]
    candidate["observable_result"] = "约法十二条实施，前朝苛禁被废除。"
    candidate["limitations"] = ["输入未逐条列出约法内容。"]
    facts = [
        {
            "segment_ref": "SEG-TEST",
            "page_title": "史书/卷一",
            "revision_ref": "1",
            "exact_quote": "皇帝命诸军攻城。",
        }
    ]
    candidate["exact_quotes"] = [facts[0]["exact_quote"]]
    candidate["members"][0]["authorization_quotes"] = [facts[0]["exact_quote"]]

    normalized = _normalize_candidate_sources(payload, facts)

    assert normalized["candidates"] == []
    assert "无实质词组重合" in normalized["rejections"][0]["reason"]


def test_outcome_projection_normalizes_campaign_tier_basis() -> None:
    payload = _campaign_candidate_payload()
    candidate = payload["candidates"][0]
    candidate["payload"]["campaign_tier_basis"] = (
        "土地轴=战略网关；对手轴=强敌/常态；结果轴=攻克/完整，测试解释。"
    )
    facts = [
        {
            "segment_ref": "SEG-TEST",
            "page_title": "史书/卷一",
            "revision_ref": "1",
            "exact_quote": "测试战役取得阶段结果。",
        }
    ]

    normalized = _normalize_candidate_sources(payload, facts)

    assert normalized["candidates"][0]["payload"]["campaign_tier_basis"] == (
        "土地轴=important_region；对手轴=regional_major/viable；"
        "结果轴=victory/partial，测试解释。"
    )


def test_campaign_candidate_requires_one_ruler_relation(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="必须登记唯一控制方式"):
        compile_outcome_candidate_payloads(
            {"ruler": "李世民", "ruler_ref": "RULER-LI-SHIMIN", "members": [], "facts": []},
            [_campaign_candidate_payload(relation=None)],
            source_index=_campaign_contract_index(tmp_path),
            schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
        )


def test_campaign_candidate_requires_letter_tier_and_land_axis(tmp_path: Path) -> None:
    payload = _campaign_candidate_payload()
    payload["candidates"][0]["payload"]["campaign_tier"] = None
    with pytest.raises(ValueError, match="缺少等级、土地轴或成本责任分轴"):
        compile_outcome_candidate_payloads(
            {"ruler": "李世民", "ruler_ref": "RULER-LI-SHIMIN", "members": [], "facts": []},
            [payload],
            source_index=_campaign_contract_index(tmp_path),
            schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
        )


def test_campaign_candidate_tier_is_fixed_by_strategic_result(tmp_path: Path) -> None:
    payload = _campaign_candidate_payload()
    payload["candidates"][0]["payload"]["campaign_tier"] = "S+"
    with pytest.raises(ValueError, match="必须映射为 A"):
        compile_outcome_candidate_payloads(
            {"ruler": "李世民", "ruler_ref": "RULER-LI-SHIMIN", "members": [], "facts": []},
            [payload],
            source_index=_campaign_contract_index(tmp_path),
            schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
        )


def test_campaign_candidate_requires_cost_shortfall_failure_axes(tmp_path: Path) -> None:
    payload = _campaign_candidate_payload()
    payload["candidates"][0]["payload"]["objective_shortfalls"] = None
    with pytest.raises(ValueError, match="缺少等级、土地轴或成本责任分轴"):
        compile_outcome_candidate_payloads(
            {"ruler": "李世民", "ruler_ref": "RULER-LI-SHIMIN", "members": [], "facts": []},
            [payload],
            source_index=_campaign_contract_index(tmp_path),
            schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
        )


def test_campaign_candidate_requires_failure_actor_in_allowed_people(tmp_path: Path) -> None:
    payload = _campaign_candidate_payload()
    candidate = payload["candidates"][0]
    source_index = _campaign_contract_index(tmp_path)
    candidate["payload"]["attributable_failures"] = [
        {
            "responsibility": "primary",
            "severity_index": 0.4,
            "actor_name": "不存在人物",
            "basis": "测试可归责失败。",
            "exact_quotes": ["测试战役取得阶段结果。"],
        }
    ]
    with pytest.raises(ValueError, match="责任人不在允许人物中"):
        compile_outcome_candidate_payloads(
            {"ruler": "李世民", "ruler_ref": "RULER-LI-SHIMIN", "members": [], "facts": []},
            [payload],
            source_index=source_index,
            schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
        )


def test_source_attributed_macro_result_requires_ruler_lead(tmp_path: Path) -> None:
    payload = _governance_candidate_payload(role_code="lead")
    candidate = payload["candidates"][0]
    candidate["settlement_scope"] = "reign_macro_outcome"
    candidate["payload"]["causal_attribution_status"] = "source_attributed"
    source_index = _campaign_contract_index(tmp_path)
    increment = compile_outcome_candidate_payloads(
        {"ruler": "李世民", "ruler_ref": "RULER-LI-SHIMIN", "members": [], "facts": []},
        [payload],
        source_index=source_index,
        schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
    )
    assert increment["outcomes"][0]["settlement_scope"] == "reign_macro_outcome"
    assert increment["outcomes"][0]["members"][0]["role_code"] == "lead"


def test_person_governance_result_is_outside_ruler_view(tmp_path: Path) -> None:
    payload = _governance_candidate_payload(role_code="lead")
    candidate = payload["candidates"][0]
    candidate.update(
        {
            "settlement_scope": "person_governance_result",
            "ruler_window_status": "outside_window",
            "scale_level": "national",
            "scale_basis": "national_cultural_corpus",
        }
    )
    candidate["members"][0].update(
        {"actor_name": "长孙无忌", "actor_kind": "person"}
    )
    source_index = _campaign_contract_index(tmp_path)
    increment = compile_outcome_candidate_payloads(
        {
            "ruler": "李世民",
            "ruler_ref": "RULER-LI-SHIMIN",
            "members": [{"person": "长孙无忌", "person_ref": "PERSON-ZHANGSUN"}],
            "facts": [],
        },
        [payload],
        source_index=source_index,
        schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
    )
    outcome = increment["outcomes"][0]
    assert outcome["settlement_scope"] == "person_governance_result"
    assert _ruler_window_outcomes([outcome]) == []

    candidate["ruler_window_status"] = "within_window"
    with pytest.raises(ValueError, match="必须位于当前皇帝窗口之外"):
        compile_outcome_candidate_payloads(
            {
                "ruler": "李世民",
                "ruler_ref": "RULER-LI-SHIMIN",
                "members": [
                    {"person": "长孙无忌", "person_ref": "PERSON-ZHANGSUN"}
                ],
                "facts": [],
            },
            [payload],
            source_index=source_index,
            schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
        )


def test_governance_window_overlap_without_ruler_responsibility_is_not_ruler_outcome() -> None:
    shared = {
        "outcome_kind": "governance",
        "settlement_scope": "governance_result",
        "ruler_window_status": "within_window",
        "members": [
            {
                "actor_kind": "person",
                "actor_ref": "PERSON-OFFICIAL",
                "role_code": "lead",
            }
        ],
    }
    attributed = json.loads(json.dumps(shared))
    attributed["members"].append(
        {
            "actor_kind": "ruler",
            "actor_ref": "RULER-CURRENT",
            "role_code": "authorized",
        }
    )

    assert _ruler_window_outcomes([shared]) == []
    assert _appointment_window_outcomes([shared]) == [shared]
    assert _ruler_window_outcomes([attributed]) == [attributed]
    assert (
        _ruler_window_outcomes([attributed], ruler_ref="RULER-OTHER") == []
    )
    assert _ruler_window_outcomes(
        [attributed], ruler_ref="RULER-CURRENT"
    ) == [attributed]


def test_independent_campaign_group_is_available_to_ruler_and_appointment_projection() -> None:
    payload = json.loads(
        (ROOT / "eval/i5b_current_value/刘邦/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    outcome = next(
        row
        for row in payload["outcome_registry"]["clusters"]
        if row["outcome_ref"] == "OUTCOME-QUALITY-LB-HANXIN-QI"
    )

    assert outcome["settlement_scope"] == "ruler_campaign_parent"
    assert outcome in _ruler_window_outcomes([outcome])
    assert outcome in _appointment_window_outcomes([outcome])


def test_campaign_candidate_allows_person_only_group_without_current_ruler(tmp_path: Path) -> None:
    payload = _campaign_candidate_payload()
    payload["candidates"][0]["members"][0].update(
        {
            "actor_name": "李靖",
            "actor_kind": "person",
            "role_code": "commander_in_chief",
            "sovereign_at_event": False,
            "ruler_campaign_relation": None,
            "authorization_mode": None,
            "control_extent": None,
            "obstruction_status": None,
            "talent_credit": "independent",
        }
    )
    increment = compile_outcome_candidate_payloads(
        {
            "ruler": "李世民",
            "ruler_ref": "RULER-LI-SHIMIN",
            "members": [{"person": "李靖", "person_ref": "PERSON-LI-JING"}],
            "facts": [],
        },
        [payload],
        source_index=_campaign_contract_index(tmp_path),
        schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
    )
    assert increment["outcomes"][0]["members"][0]["actor_name"] == "李靖"


def test_campaign_commander_without_repeated_appointment_quote_gets_tacit_authorization(
    tmp_path: Path,
) -> None:
    payload = _campaign_candidate_payload()
    member = payload["candidates"][0]["members"][0]
    member.update(
        {
            "actor_name": "李靖",
            "actor_kind": "person",
            "role_code": "commander_in_chief",
            "sovereign_at_event": False,
            "ruler_campaign_relation": None,
            "authorization_mode": None,
            "control_extent": None,
            "obstruction_status": None,
            "talent_credit": "independent",
            "responsibility_scope": "major_affairs",
            "authorization_quotes": [],
        }
    )
    increment = compile_outcome_candidate_payloads(
        {
            "ruler": "李世民",
            "ruler_ref": "RULER-LI-SHIMIN",
            "members": [{"person": "李靖", "person_ref": "PERSON-LI-JING"}],
            "facts": [],
        },
        [payload],
        source_index=_campaign_contract_index(tmp_path),
        schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
    )

    responsibility = increment["outcomes"][0]["members"][0][
        "delegated_responsibility"
    ]
    assert responsibility["authorizer_ref"] == "RULER-LI-SHIMIN"
    assert responsibility["scope"] == "major_affairs"
    assert responsibility["authorization_refs"] == [
        "史书/卷一@1#测试战役取得阶段结果。"
    ]
    assert "默示授权" in increment["outcomes"][0]["limitations"][-1]


def test_outside_window_person_campaign_does_not_require_current_ruler(tmp_path: Path) -> None:
    payload = _campaign_candidate_payload()
    candidate = payload["candidates"][0]
    candidate["ruler_window_status"] = "outside_window"
    candidate["settlement_scope"] = "person_campaign_subresult"
    candidate["parent_outcome_ref"] = "OUTCOME-TEST-PARENT"
    candidate["members"][0].update(
        {
            "actor_name": "李靖",
            "actor_kind": "person",
            "role_code": "commander_in_chief",
            "sovereign_at_event": False,
            "ruler_campaign_relation": None,
            "authorization_mode": None,
            "control_extent": None,
            "obstruction_status": None,
            "talent_credit": "independent",
        }
    )
    increment = compile_outcome_candidate_payloads(
        {
            "ruler": "李世民",
            "ruler_ref": "RULER-LI-SHIMIN",
            "members": [{"person": "李靖", "person_ref": "PERSON-LI-JING"}],
            "facts": [],
        },
        [payload],
        source_index=_campaign_contract_index(tmp_path),
        schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
    )
    assert increment["outcomes"][0]["ruler_window_status"] == "outside_window"
    assert increment["outcomes"][0]["members"][0]["actor_name"] == "李靖"
    outcome = increment["outcomes"][0]
    outcome["episode_refs"] = [outcome_episode_ref(outcome)]
    outcome["semantic_fingerprint"] = cluster_semantic_fingerprint(outcome)
    parent = json.loads(json.dumps(outcome, ensure_ascii=False))
    parent["outcome_ref"] = "OUTCOME-TEST-PARENT"
    parent["independent_key"] = "test-campaign-parent"
    parent["settlement_scope"] = "ruler_campaign_parent"
    parent.pop("parent_outcome_ref")
    parent["members"][0]["talent_credit"] = "covered_by_child"
    parent["episode_refs"] = [outcome_episode_ref(parent)]
    parent["semantic_fingerprint"] = cluster_semantic_fingerprint(parent)
    validation = validate_historical_outcome_registry(
        {
            "schema_version": "historical-outcome-cluster-registry-v3",
            "status": "shadow",
            "clusters": [parent, outcome],
        },
        schema_path=ROOT / "config/historical-outcome-cluster-registry.schema.json",
        facts={row["record_ref"]: row for row in increment["facts"]},
    )
    assert validation["status"] == "passed"
    outcome_without_campaign_context = json.loads(json.dumps(outcome, ensure_ascii=False))
    outcome_without_campaign_context["payload"]["theater"] = ""
    outcome_without_campaign_context["payload"]["strategic_objective"] = None
    outcome_without_campaign_context["semantic_fingerprint"] = (
        cluster_semantic_fingerprint(outcome_without_campaign_context)
    )
    with pytest.raises(ValueError, match="战区、目标、背景、利害、三轴、战略结果、难度和等级"):
        validate_historical_outcome_registry(
            {
                "schema_version": "historical-outcome-cluster-registry-v3",
                "status": "shadow",
                "clusters": [parent, outcome_without_campaign_context],
            },
            schema_path=ROOT / "config/historical-outcome-cluster-registry.schema.json",
            facts={row["record_ref"]: row for row in increment["facts"]},
        )
    outcome_without_window = json.loads(json.dumps(outcome, ensure_ascii=False))
    outcome_without_window.pop("ruler_window_status")
    outcome_without_window["semantic_fingerprint"] = cluster_semantic_fingerprint(
        outcome_without_window
    )
    with pytest.raises(ValueError):
        validate_historical_outcome_registry(
            {
                "schema_version": "historical-outcome-cluster-registry-v3",
                "status": "shadow",
                "clusters": [parent, outcome_without_window],
            },
            schema_path=ROOT / "config/historical-outcome-cluster-registry.schema.json",
            facts={row["record_ref"]: row for row in increment["facts"]},
        )


def test_campaign_candidate_keeps_outcome_when_ruler_window_is_unresolved(
    tmp_path: Path,
) -> None:
    payload = _campaign_candidate_payload()
    payload["candidates"][0]["ruler_window_status"] = "unresolved"
    increment = compile_outcome_candidate_payloads(
        {"ruler": "李世民", "ruler_ref": "RULER-LI-SHIMIN", "members": [], "facts": []},
        [payload],
        source_index=_campaign_contract_index(tmp_path),
        schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
    )
    assert len(increment["outcomes"]) == 1
    assert increment["outcomes"][0]["ruler_window_status"] == "unresolved"


def test_governance_candidate_rejects_authorization_only_member(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="角色不属于 governance 合同"):
        compile_outcome_candidate_payloads(
            {"ruler": "李世民", "ruler_ref": "RULER-LI-SHIMIN", "members": [], "facts": []},
            [_governance_candidate_payload(role_code="authorized")],
            source_index=_campaign_contract_index(tmp_path),
            schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
        )


def test_public_governance_candidate_can_remain_unbound(tmp_path: Path) -> None:
    payload = _governance_candidate_payload()
    payload["candidates"][0]["members"] = []
    increment = compile_outcome_candidate_payloads(
        {"ruler": "李世民", "ruler_ref": "RULER-LI-SHIMIN", "members": [], "facts": []},
        [payload],
        source_index=_campaign_contract_index(tmp_path),
        schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
    )
    assert increment["outcomes"][0]["members"] == []


def test_governance_candidate_keeps_scale_and_lead_role(tmp_path: Path) -> None:
    increment = compile_outcome_candidate_payloads(
        {"ruler": "李世民", "ruler_ref": "RULER-LI-SHIMIN", "members": [], "facts": []},
        [_governance_candidate_payload()],
        source_index=_campaign_contract_index(tmp_path),
        schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
    )
    outcome = increment["outcomes"][0]
    assert outcome["scale"]["level"] == "important"
    assert outcome["members"][0]["role_code"] == "lead"
    assert outcome["payload"]["value_judgment"]["overall_direction"] == "positive"
    outcome["episode_refs"] = [outcome_episode_ref(outcome)]
    outcome["semantic_fingerprint"] = cluster_semantic_fingerprint(outcome)
    validation = validate_historical_outcome_registry(
        {
            "schema_version": "historical-outcome-cluster-registry-v3",
            "status": "shadow",
            "clusters": [outcome],
        },
        schema_path=ROOT / "config/historical-outcome-cluster-registry.schema.json",
        facts={row["record_ref"]: row for row in increment["facts"]},
    )
    assert validation["status"] == "passed"


def test_structured_runner_timeout_terminates_tree_without_waiting_on_pipes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class HangingProcess:
        pid = 12345
        returncode = None

        def __init__(self) -> None:
            self.stdin = io.StringIO()
            self.stdout = io.StringIO()
            self.stderr = io.StringIO()
            self.communicate_calls = 0

        def communicate(self, **_kwargs: object) -> tuple[str, str]:
            self.communicate_calls += 1
            raise subprocess.TimeoutExpired("codex", 1)

        def poll(self) -> None:
            return None

        def kill(self) -> None:
            self.returncode = -9

    process = HangingProcess()
    terminated: list[int] = []
    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: process)
    monkeypatch.setattr(
        "emperor_v4.runtime.structured_codex_runner._terminate_process_tree",
        lambda value: terminated.append(value.pid),
    )
    runner = StructuredCodexRunner(
        codex_bin="codex",
        model="test-model",
        reasoning_effort="low",
        output_schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
        timeout_seconds=15,
        cwd=ROOT,
    )

    with pytest.raises(ModelBatchAnomalyError, match="熔断同批调用"):
        runner.run("test")

    assert terminated == [12345]
    assert process.communicate_calls >= 2


def test_outcome_transport_schema_drops_api_conditionals_only() -> None:
    source = json.loads(
        (ROOT / "config/current-outcome-candidate-output.schema.json").read_text(
            encoding="utf-8"
        )
    )
    transport = build_outcome_transport_schema(
        ROOT / "config/current-outcome-candidate-output.schema.json"
    )

    assert "allOf" in source["properties"]["candidates"]["items"]
    candidate = transport["properties"]["candidates"]["items"]
    assert "allOf" not in candidate
    assert set(candidate["required"]) == set(candidate["properties"])
    member = candidate["properties"]["members"]["items"]
    assert set(member["required"]) == set(member["properties"])
    assert member["properties"]["talent_credit"]["type"] == ["string", "null"]
    assert member["properties"]["talent_credit"]["enum"][-1] is None
    axes = candidate["properties"]["payload"]["properties"]["value_judgment"][
        "properties"
    ]["axes"]["properties"]
    assert all(axis["type"] == "object" for axis in axes.values())
    assert all("$ref" not in axis for axis in axes.values())
    validate_codex_output_schema(transport, require_all_properties=True)


def test_emperor_rebuild_recovers_model_anomaly_with_fresh_smaller_runner() -> None:
    runners = []
    observed_batch_sizes = []

    class Runner:
        def __init__(self, number: int) -> None:
            self.number = number

    def runner_factory():
        runner = Runner(len(runners) + 1)
        runners.append(runner)
        return runner

    def operation(runner, batch_size: int):
        observed_batch_sizes.append(batch_size)
        if runner.number == 1:
            raise ModelBatchAnomalyError("测试异常")
        return "completed"

    result, recovery_count, final_batch_size = _run_with_model_anomaly_recovery(
        runner_factory=runner_factory,
        operation=operation,
        initial_batch_size=8,
    )

    assert result == "completed"
    assert recovery_count == 1
    assert final_batch_size == 4
    assert observed_batch_sizes == [8, 4]
    assert len(runners) == 2


def test_emperor_rebuild_can_reduce_outcome_batch_twice() -> None:
    runners = []
    observed_batch_sizes = []

    def runner_factory():
        runner = object()
        runners.append(runner)
        return runner

    def operation(_runner, batch_size: int):
        observed_batch_sizes.append(batch_size)
        if batch_size > 4:
            raise ModelBatchAnomalyError("成果批次超时")
        return "completed"

    result, recovery_count, final_batch_size = _run_with_model_anomaly_recovery(
        runner_factory=runner_factory,
        operation=operation,
        initial_batch_size=16,
        maximum_recoveries=2,
    )

    assert result == "completed"
    assert recovery_count == 2
    assert final_batch_size == 4
    assert observed_batch_sizes == [16, 8, 4]
    assert len(runners) == 3


def _session_release_fixture(tmp_path: Path) -> Path:
    release = tmp_path / "release"
    shutil.copytree(ROOT / "config", release / "config")
    package = release / "src/emperor_v4"
    package.mkdir(parents=True)
    shutil.copy2(ROOT / "src/emperor_v4/__init__.py", package / "__init__.py")
    for relative_path in emperor_session_control.SESSION_RULE_DOCUMENTS:
        source = ROOT / relative_path
        target = release / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    for ruler in ("李世民", "李渊", "李治", "刘邦"):
        shutil.copytree(
            ROOT / "eval/i5b_current_value" / ruler,
            release / "eval/i5b_current_value" / ruler,
        )
    shutil.copytree(
        ROOT / "eval/historical_outcome_registry",
        release / "eval/historical_outcome_registry",
    )
    shutil.copytree(
        ROOT / "eval/historical_person_profiles",
        release / "eval/historical_person_profiles",
    )
    shutil.copytree(
        ROOT / "eval/historical_outcome_bindings",
        release / "eval/historical_outcome_bindings",
    )
    return release


def _accepted_rebuild_stage_results() -> list[dict[str, str]]:
    return [
        {
            "stage": stage,
            "status": "quality_accepted",
            "input_fingerprint": f"{stage}-input",
            "producer_contract_fingerprint": f"{stage}-contract",
        }
        for stage in emperor_session_control.REQUIRED_REBUILD_STAGES
    ]


def _write_bootstrap_binding(workspace: Path, ruler: str) -> None:
    source_pack = json.loads(
        (
            workspace / "eval/i5b_current_value" / ruler / "source-pack.json"
        ).read_text(encoding="utf-8")
    )
    registry = json.loads(
        (
            workspace / "eval/historical_outcome_registry/current.json"
        ).read_text(encoding="utf-8")
    )
    binding = build_ruler_outcome_bindings(source_pack, registry)
    target = workspace / "eval/historical_outcome_bindings" / f"{ruler}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(binding, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_emperor_sessions_atomically_split_rulers_and_global_model_slots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = _session_release_fixture(tmp_path)
    monkeypatch.setattr(
        emperor_session_control, "_release_identity", lambda _root: "a" * 40
    )
    state = tmp_path / "state"

    first = emperor_session_control.claim_session(
        state_root=state,
        release_root=release,
        session_id="SESSION-A",
        model_slot_count=2,
    )
    second = emperor_session_control.claim_session(
        state_root=state,
        release_root=release,
        session_id="SESSION-B",
        model_slot_count=2,
    )

    assert (first["ruler"], second["ruler"]) == ("李世民", "李治")
    assert set(first["model_slots"]).isdisjoint(second["model_slots"])
    assert emperor_session_control.session_status(state_root=state)[
        "available_model_slot_count"
    ] == 0
    with pytest.raises(emperor_session_control.SessionControlError, match="没有可认领皇帝"):
        emperor_session_control.claim_session(
            state_root=state,
            release_root=release,
            session_id="SESSION-C",
            model_slot_count=1,
        )

    emperor_session_control.abandon_session(
        state_root=state, session_id="SESSION-A"
    )
    emperor_session_control.abandon_session(
        state_root=state, session_id="SESSION-B"
    )
    assert emperor_session_control.session_status(state_root=state)["sessions"] == []


def test_emperor_session_claim_allows_first_run_without_derived_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = _session_release_fixture(tmp_path)
    configured = json.loads(
        json.dumps(
            yaml.safe_load(
                (release / "config/project.yml").read_text(encoding="utf-8")
            ),
            ensure_ascii=False,
        )
    )["i5b_current_value"]["rulers"]["李世民"]
    for key in ("neutral_materials", "result", "outcome_binding"):
        path = release / configured[key]
        path.unlink(missing_ok=True)
        if key == "result":
            path.with_suffix(".md").unlink(missing_ok=True)
    monkeypatch.setattr(
        emperor_session_control, "_release_identity", lambda _root: "e" * 40
    )

    lease = emperor_session_control.claim_session(
        state_root=tmp_path / "state",
        release_root=release,
        session_id="SESSION-FIRST-RUN",
        ruler="李世民",
        model_slot_count=1,
    )

    workspace = Path(lease["workspace_root"])
    assert (workspace / configured["source_pack"]).is_file()
    assert not (workspace / configured["result"]).exists()
    assert (workspace / "eval/i5b_current_value/刘邦/source-pack.json").is_file()


def test_li_zhi_bootstrap_claims_only_its_exclusive_chronicle_range(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = _session_release_fixture(tmp_path)
    monkeypatch.setattr(
        emperor_session_control, "_release_identity", lambda _root: "d" * 40
    )
    state = tmp_path / "state"

    lease = emperor_session_control.claim_session(
        state_root=state,
        release_root=release,
        session_id="SESSION-LI-ZHI-BOOTSTRAP",
        ruler="李治",
        model_slot_count=1,
    )

    assert lease["ruler"] == "李治"
    assert lease["shared_tokens"] == []
    source_pack = (
        Path(lease["workspace_root"])
        / "eval/i5b_current_value/李治/source-pack.json"
    )
    assert source_pack.is_file()
    assert source_pack.stat().st_mode & stat.S_IWUSR
    assert source_pack.parent.stat().st_mode & stat.S_IWUSR
    project = yaml.safe_load(
        (
            Path(lease["workspace_root"]) / "config/project.yml"
        ).read_text(encoding="utf-8")
    )
    assert project["i5b_current_value"]["rulers"]["李治"][
        "neutral_scan_backbone_page_ranges"
    ] == {"資治通鑑": [200, 203]}
    emperor_session_control.abandon_session(
        state_root=state, session_id="SESSION-LI-ZHI-BOOTSTRAP"
    )


def test_unconfigured_ruler_claim_stays_alive_for_isolated_bootstrap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = _session_release_fixture(tmp_path)
    monkeypatch.setattr(
        emperor_session_control, "_release_identity", lambda _root: "c" * 40
    )
    state = tmp_path / "state"

    lease = emperor_session_control.claim_session(
        state_root=state,
        release_root=release,
        session_id="SESSION-ZHU-YUANZHANG",
        ruler="朱元璋",
        model_slot_count=2,
    )
    report = emperor_session_control.run_claimed_session(
        state_root=state,
        session_id="SESSION-ZHU-YUANZHANG",
        release_root=release,
        source_index_root=tmp_path / "indexes",
        dynasty_governance_root=tmp_path / "governance",
    )

    workspace = Path(lease["workspace_root"])
    assert lease["stage"] == "bootstrap_required"
    assert lease["bootstrap_required"] is True
    assert lease["shared_tokens"] == []
    assert report["status"] == "awaiting_bootstrap"
    assert report["database_write_count"] == 0
    assert report["formal_score_write_count"] == 0
    assert (workspace / "config/project.yml").is_file()
    assert (
        workspace / "eval/i5b_current_value/李世民/source-pack.json"
    ).is_file()
    assert emperor_session_control.session_status(state_root=state)[
        "sessions"
    ][0]["stage"] == "bootstrap_required"


def test_two_unconfigured_rulers_can_bootstrap_concurrently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = _session_release_fixture(tmp_path)
    monkeypatch.setattr(
        emperor_session_control, "_release_identity", lambda _root: "c" * 40
    )
    state = tmp_path / "state"

    first = emperor_session_control.claim_session(
        state_root=state,
        release_root=release,
        session_id="SESSION-ZHU-YUANZHANG",
        ruler="朱元璋",
        model_slot_count=2,
    )
    second = emperor_session_control.claim_session(
        state_root=state,
        release_root=release,
        session_id="SESSION-KANGXI",
        ruler="康熙",
        model_slot_count=2,
    )

    assert set(first["model_slots"]).isdisjoint(second["model_slots"])
    assert first["resource_ruler_ref"] != second["resource_ruler_ref"]
    assert emperor_session_control.session_status(state_root=state)[
        "available_model_slot_count"
    ] == 0
    emperor_session_control.abandon_session(
        state_root=state, session_id="SESSION-ZHU-YUANZHANG"
    )
    emperor_session_control.abandon_session(
        state_root=state, session_id="SESSION-KANGXI"
    )


def test_unconfigured_ruler_bootstrap_materializes_spec_and_waits_for_assets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = _session_release_fixture(tmp_path)
    monkeypatch.setattr(
        emperor_session_control, "_release_identity", lambda _root: "c" * 40
    )
    state = tmp_path / "state"
    lease = emperor_session_control.claim_session(
        state_root=state,
        release_root=release,
        session_id="SESSION-ZHU-YUANZHANG",
        ruler="朱元璋",
        model_slot_count=1,
    )
    spec = {
        "schema_version": emperor_session_control.BOOTSTRAP_SCHEMA_VERSION,
        "ruler": "朱元璋",
        "ruler_ref": "RULER-MING-ZHUYUANZHANG",
        "dynasty": "明",
        "window": "1368-1398",
        "ruler_config": {
            "source_pack": "eval/i5b_current_value/朱元璋/source-pack.json",
            "outcome_binding": "eval/historical_outcome_bindings/朱元璋.json",
            "neutral_materials": "eval/i5b_current_value/朱元璋/neutral-materials.json",
            "result": "eval/i5b_current_value/朱元璋/result.json",
            "neutral_scan_backbone_works": ["明史"],
            "neutral_scan_backbone_page_ranges": {"明史": [1, 3]},
            "dynasty_governance_material_token": "MING",
            "dynasty_governance_period_terms": ["洪武", "明太祖", "朱元璋"],
        },
        "members": [],
        "identity_entries": [
            {
                "person_ref": "RULER-MING-ZHUYUANZHANG",
                "canonical_name": "朱元璋",
                "dynasty": "明",
                "aliases": [
                    {"surface": "明太祖", "alias_type": "temple_name"}
                ],
            }
        ],
    }
    spec_path = tmp_path / "zhu-bootstrap.json"
    spec_path.write_text(
        json.dumps(spec, ensure_ascii=False), encoding="utf-8"
    )
    rejected = json.loads(json.dumps(spec, ensure_ascii=False))
    rejected["ruler_config"]["neutral_scan_backbone_works"] = [
        "大明太祖高皇帝實錄"
    ]
    rejected["ruler_config"]["neutral_scan_backbone_page_ranges"] = {
        "大明太祖高皇帝實錄": [1, 257]
    }
    rejected_path = tmp_path / "zhu-bootstrap-rejected.json"
    rejected_path.write_text(
        json.dumps(rejected, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(
        emperor_session_control.SessionControlError,
        match="禁止整套扫描高体量史书",
    ):
        emperor_session_control.complete_session_bootstrap(
            state_root=state,
            session_id="SESSION-ZHU-YUANZHANG",
            bootstrap_spec_path=rejected_path,
            source_index_root=tmp_path / "indexes",
            dynasty_governance_root=tmp_path / "governance",
        )

    report = emperor_session_control.complete_session_bootstrap(
        state_root=state,
        session_id="SESSION-ZHU-YUANZHANG",
        bootstrap_spec_path=spec_path,
        source_index_root=tmp_path / "indexes",
        dynasty_governance_root=tmp_path / "governance",
    )

    source_pack = (
        Path(lease["workspace_root"])
        / "eval/i5b_current_value/朱元璋/source-pack.json"
    )
    assert report["status"] == "awaiting_bootstrap"
    assert any(value.startswith("fixed_source_index:") for value in report["missing"])
    assert source_pack.is_file()
    payload = json.loads(source_pack.read_text(encoding="utf-8"))
    declared = payload.pop("source_pack_sha256")
    assert declared == hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    session = emperor_session_control.session_status(state_root=state)[
        "sessions"
    ][0]
    assert session["stage"] == "bootstrap_assets_required"
    assert session["bootstrap_required"] is True

    index_path = tmp_path / "indexes/ming/ming.sqlite3"
    index_path.parent.mkdir(parents=True)
    build_local_source_index(
        [
            {
                "page_title": "明史/卷1",
                "work_title": "明史",
                "source_url": "local:ming-annals",
                "revision_ref": "1",
                "raw_text": "洪武元年即皇帝位。",
            },
        ],
        index_path,
    )
    governance_path = tmp_path / "governance/MING/current.json"
    governance_path.parent.mkdir(parents=True)
    project_catalog = yaml.safe_load(
        (release / "config/project.yml").read_text(encoding="utf-8")
    )["dynasty_governance_catalog"]
    ming_catalog = {
        **project_catalog["dynasties"]["明"],
        "quality_requires_catalog_source_families": project_catalog[
            "quality_requires_catalog_source_families"
        ],
    }
    governance_path.write_text(
        json.dumps(
            {
                "schema_version": "dynasty-governance-current-v2",
                "status": "quality_accepted_shadow",
                "dynasty_token": "MING",
                "source_index_identity": "INDEPENDENT-MING-GOVERNANCE-INDEX",
                "input_fingerprint": "MING-GOVERNANCE-FINGERPRINT",
                "catalog_fingerprint": dynasty_governance_catalog_fingerprint(
                    ming_catalog
                ),
                    "sources": [
                        {"page_title": page_title}
                        for source in ming_catalog["source_works"]
                        for page_title in source.get("page_titles") or ()
                    ]
                    + [
                        {
                            "work": "明㑹典 (四庫全書本)",
                            "page_title": "明㑹典 (四庫全書本)/全覽6",
                        }
                    ],
            }
        ),
        encoding="utf-8",
    )
    outcome_pack_path = governance_path.with_name("outcome-pack.json")
    outcome_pack_path.write_text(
        json.dumps(
            {
                "pack_scope": "dynasty_governance",
                "dynasty_token": "MING",
                "source_pack_sha256": "MING-OUTCOME-PACK",
            }
        ),
        encoding="utf-8",
    )
    registry_path = (
        tmp_path
        / "governance/historical_outcome_registry/MING/current.json"
    )
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps({"registry_fingerprint": "MING-REGISTRY"}),
        encoding="utf-8",
    )
    governance_path.with_name("handoff.json").write_text(
        json.dumps(
            {
                "schema_version": "dynasty-governance-handoff-v1",
                "status": "quality_accepted_shadow",
                "dynasty_token": "MING",
                "governance_input_fingerprint": (
                    "MING-GOVERNANCE-FINGERPRINT"
                ),
                "outcome_pack": str(outcome_pack_path),
                "outcome_pack_sha256": "MING-OUTCOME-PACK",
                "outcome_registry_current": str(registry_path),
                "outcome_registry_fingerprint": "MING-REGISTRY",
            }
        ),
        encoding="utf-8",
    )

    ready = emperor_session_control.complete_session_bootstrap(
        state_root=state,
        session_id="SESSION-ZHU-YUANZHANG",
        bootstrap_spec_path=spec_path,
        source_index_root=tmp_path / "indexes",
        dynasty_governance_root=tmp_path / "governance",
    )

    assert ready["status"] == "bootstrap_ready"
    session = emperor_session_control.session_status(state_root=state)[
        "sessions"
    ][0]
    assert session["stage"] == "claimed"
    assert session["bootstrap_required"] is False
    assert session["ruler_ref"] == "RULER-MING-ZHUYUANZHANG"

    lease_path = emperor_session_control._session_path(
        state, "SESSION-ZHU-YUANZHANG"
    )
    failed = json.loads(lease_path.read_text(encoding="utf-8"))
    failed["stage"] = "failed_reusable"
    emperor_session_control._atomic_json(lease_path, failed)
    revised_spec = json.loads(spec_path.read_text(encoding="utf-8"))
    revised_spec["ruler_config"]["neutral_scan_backbone_page_ranges"] = {
        "明史": [1, 2]
    }
    spec_path.write_text(
        json.dumps(revised_spec, ensure_ascii=False), encoding="utf-8"
    )

    revised = emperor_session_control.complete_session_bootstrap(
        state_root=state,
        session_id="SESSION-ZHU-YUANZHANG",
        bootstrap_spec_path=spec_path,
        source_index_root=tmp_path / "indexes",
        dynasty_governance_root=tmp_path / "governance",
    )

    assert revised["status"] == "bootstrap_ready"
    workspace_project = yaml.safe_load(
        (
            Path(lease["workspace_root"]) / "config/project.yml"
        ).read_text(encoding="utf-8")
    )
    assert workspace_project["i5b_current_value"]["rulers"]["朱元璋"][
        "neutral_scan_backbone_page_ranges"
    ] == {"明史": [1, 2]}


def test_dynasty_governance_catalog_covers_supported_eras() -> None:
    project = yaml.safe_load(
        (ROOT / "config/project.yml").read_text(encoding="utf-8")
    )
    catalog = project["dynasty_governance_catalog"]
    assert catalog["schema_version"] == "dynasty-governance-catalog-v1"
    assert catalog["quality_requires_catalog_source_families"] is True
    assert (
        catalog["shared_current_root_contract"]
        == "dynasty_neutral_materials/<dynasty_token>/current.json"
    )
    rows = catalog["dynasties"]
    assert set(rows) == {
        "秦",
        "西汉",
        "东汉",
        "三国",
        "两晋十六国",
        "南北朝",
        "隋",
        "唐",
        "五代十国",
        "辽",
        "宋",
        "西夏",
        "金",
        "元",
        "明",
        "清",
        "太平天国",
    }
    for dynasty, row in rows.items():
        assert row["dynasty_token"], dynasty
        assert row["source_works"], dynasty
        _canonical, loaded = load_dynasty_governance_catalog_entry(
            ROOT, dynasty
        )
        assert loaded["quality_requires_catalog_source_families"] is True
        for source in row["source_works"]:
            assert source["work"]
            assert source["target_scope"]
            assert source["domain_focus"]
            assert source["section_groups"]
    ming_pages = rows["明"]["source_works"][0]["page_titles"]
    assert ming_pages == [f"明史/卷{number}" for number in range(40, 96)]
    tang_works = {
        (source["work"], source["source_genre"]): source
        for source in rows["唐"]["source_works"]
    }
    assert tang_works[
        ("新唐書", "official_history_geography_context")
    ]["page_titles"] == [
        "新唐書/卷037",
        "新唐書/卷038",
        "新唐書/卷039",
        "新唐書/卷040",
        "新唐書/卷041",
        "新唐書/卷042",
        "新唐書/卷043上",
        "新唐書/卷043下",
    ]
    assert ("明㑹典 (四庫全書本)", "targeted_institutional_compendium") in {
        (source["work"], source["source_genre"])
        for source in rows["明"]["source_works"]
    }
    eastern_han_works = {
        source["work"]: source for source in rows["东汉"]["source_works"]
    }
    assert set(eastern_han_works) == {"後漢書", "東漢會要"}
    assert set(eastern_han_works["後漢書"]["section_groups"]) == {
        "bureaucracy",
        "ritual_and_public_order",
        "frontier",
    }
    assert set(eastern_han_works["東漢會要"]["section_groups"]) == {
        "education_and_selection",
        "law_and_discipline",
        "economy_and_relief",
        "military",
    }
    assert "地理志" not in {
        term
        for source in rows["西汉"]["source_works"]
        for terms in source["section_groups"].values()
        for term in terms
    }
    assert project["i5b_current_value"]["rulers"]["李治"][
        "dynasty_governance_material_token"
    ] == "TANG"
    assert "dynasty_governance_scans" not in project


def test_ming_governance_current_must_bind_catalog_and_treatise_pages() -> None:
    project = yaml.safe_load(
        (ROOT / "config/project.yml").read_text(encoding="utf-8")
    )
    token_name, token_configured = load_dynasty_governance_catalog_entry(
        ROOT, "MING"
    )
    assert token_name == "明"
    assert token_configured["dynasty_token"] == "MING"
    configured = {
        **project["dynasty_governance_catalog"]["dynasties"]["明"],
        "quality_requires_catalog_source_families": True,
    }
    old_annals_only = {
        "schema_version": "dynasty-governance-current-v2",
        "status": "quality_accepted_shadow",
        "dynasty_token": "MING",
        "source_index_identity": "OLD-MING-ANNALS",
        "sources": [
            {"page_title": "明史/卷2"},
            {"page_title": "明史/卷3"},
        ],
    }

    with pytest.raises(ValueError, match="未绑定当前书目目录"):
        validate_dynasty_governance_current_catalog(
            old_annals_only, configured
        )

    required_pages = [
        page_title
        for source in configured["source_works"]
        for page_title in source.get("page_titles") or ()
    ]
    missing_one = {
        **old_annals_only,
        "catalog_fingerprint": dynasty_governance_catalog_fingerprint(configured),
        "sources": [
            {"page_title": page_title}
            for page_title in required_pages[:-1]
        ]
        + [
            {
                "work": "明㑹典 (四庫全書本)",
                "page_title": "明㑹典 (四庫全書本)/占位",
            }
        ],
    }
    with pytest.raises(ValueError, match="缺少目录指定专题篇章"):
        validate_dynasty_governance_current_catalog(missing_one, configured)

    complete = {
        **missing_one,
        "sources": [
            {"page_title": page_title}
            for page_title in required_pages
        ]
        + [
            {
                "work": "明㑹典 (四庫全書本)",
                "page_title": "明㑹典 (四庫全書本)/全覽6",
            }
        ],
    }
    validate_dynasty_governance_current_catalog(complete, configured)

    traditional_work = {
        "dynasty_token": "TANG",
        "source_works": [{"work": "貞觀政要"}],
        "quality_requires_catalog_source_families": True,
    }
    normalized_current = {
        "catalog_fingerprint": dynasty_governance_catalog_fingerprint(
            traditional_work
        ),
        "sources": [
            {
                "work": "贞观政要",
                "page_title": "貞觀政要/卷01",
            }
        ],
    }
    validate_dynasty_governance_current_catalog(
        normalized_current, traditional_work
    )


def test_neutral_material_source_strategy_covers_supported_dynasty_routes() -> None:
    payload = yaml.safe_load(
        (ROOT / "config/i5b-source-search-scope.yml").read_text(
            encoding="utf-8"
        )
    )
    assert payload["schema_version"] == "i5b-source-search-scope-v4"
    defaults = payload["neutral_material_defaults"]
    assert defaults["scan_start"] == {
        "polity_founder": "verified_independent_foundation_activity",
        "non_founder": "accession",
    }
    assert defaults["fragmented_regime_person_fallback"] == [
        "polity_official_biography",
        "official_history_zai_ji_shi_jia_or_guo_zhuan",
        "polity_chronicle_named_person_aggregation",
    ]
    strategies = {
        dynasty: row["neutral_material_strategy"]
        for dynasty, row in payload["dynasties"].items()
    }
    assert set(strategies) == {
        "秦",
        "西汉",
        "东汉",
        "三国",
        "两晋十六国",
        "南北朝",
        "隋",
        "唐",
        "五代十国",
        "辽",
        "宋",
        "西夏",
        "金",
        "元",
        "明",
        "清",
        "太平天国",
    }
    assert strategies["秦"]["ruler_chronicles"] == ["资治通鉴"]
    assert strategies["宋"]["period_routes"]["北宋"] == [
        "资治通鉴",
        "续资治通鉴长编",
    ]
    assert strategies["明"]["event_backsource"] == []
    assert strategies["明"]["ruler_chronicles"] == ["明史"]
    assert strategies["明"]["person_biographies"] == ["明史"]
    assert strategies["清"]["event_backsource"] == []
    assert strategies["清"]["ruler_chronicles"] == ["清史稿"]
    assert strategies["清"]["person_biographies"] == ["清史稿"]
    assert strategies["两晋十六国"]["fragmented_regime_routes"]["十六国"][
        "person_materials"
    ] == ["晋书载记", "十六国春秋", "资治通鉴"]
    assert strategies["五代十国"]["fragmented_regime_routes"]["十国"][
        "person_materials"
    ][0] == "十国春秋"
    assert strategies["明"]["fragmented_regime_routes"]["南明"][
        "person_materials"
    ] == ["明史列传", "海东逸史", "南疆绎史"]
    assert strategies["西夏"]["standalone_biography_required"] is False


def test_emperor_session_claim_rejects_overlapping_range_before_leases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = _session_release_fixture(tmp_path)
    project_path = release / "config/project.yml"
    project = yaml.safe_load(project_path.read_text(encoding="utf-8"))
    project["i5b_current_value"]["rulers"]["刘邦"][
        "neutral_scan_backbone_page_ranges"
    ] = {"資治通鑑": [190, 205]}
    project_path.write_text(
        yaml.safe_dump(project, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        emperor_session_control, "_release_identity", lambda _root: "f" * 40
    )
    state = tmp_path / "state"

    with pytest.raises(
        emperor_session_control.SessionControlError,
        match="重叠但未复用同一中央 token",
    ):
        emperor_session_control.claim_session(
            state_root=state,
            release_root=release,
            session_id="SESSION-OVERLAP",
            ruler="刘邦",
            model_slot_count=1,
        )

    assert not (state / "session-control").exists()


def test_quality_accepted_stage_can_resume_across_release_workspace(
    tmp_path: Path,
) -> None:
    first_workspace = tmp_path / "release-a"
    second_workspace = tmp_path / "release-b"
    source = first_workspace / "neutral-materials.json"
    source.parent.mkdir(parents=True)
    source.write_text('{"facts":["accepted"]}\n', encoding="utf-8")
    cache = tmp_path / "state/stage-cache/RULER-A"

    _accept_stage(
        runtime_root=tmp_path / "runtime-a",
        stage_cache_root=cache,
        stage="neutral_materials",
        input_fingerprint="INPUT-A",
        producer_contract_fingerprint="CONTRACT-A",
        quality_checks={"coverage_complete": True},
        artifacts={"neutral_materials": source},
    )
    target = second_workspace / "neutral-materials.json"
    restored = _restore_stage_artifacts(
        stage_cache_root=cache,
        stage="neutral_materials",
        input_fingerprint="INPUT-A",
        producer_contract_fingerprint="CONTRACT-A",
        targets={"neutral_materials": target},
    )

    assert restored is not None
    assert restored["status"] == "quality_accepted"
    assert target.read_text(encoding="utf-8") == '{"facts":["accepted"]}\n'

    target.unlink()
    assert (
        _restore_stage_artifacts(
            stage_cache_root=cache,
            stage="neutral_materials",
            input_fingerprint="INPUT-A",
            producer_contract_fingerprint="CONTRACT-B",
            targets={"neutral_materials": target},
        )
        is None
    )
    assert not target.exists()

    (cache / "neutral_materials/neutral_materials.json").write_text(
        '{"facts":["corrupted"]}\n', encoding="utf-8"
    )
    assert (
        _restore_stage_artifacts(
            stage_cache_root=cache,
            stage="neutral_materials",
            input_fingerprint="INPUT-A",
            producer_contract_fingerprint="CONTRACT-A",
            targets={"neutral_materials": target},
        )
        is None
    )
    assert not target.exists()


def test_shared_backbone_contract_is_one_extraction_for_all_token_owners() -> None:
    project = {
        "i5b_current_value": {
            "rulers": {
                "甲": {"neutral_scan_backbone_material_token": "SHARED"},
                "乙": {"neutral_scan_backbone_material_token": "SHARED"},
            }
        },
        "neutral_material_reuse": {
            "shared_chronicle_materials": {
                "SHARED": {
                    "works": ["某编年史"],
                    "page_ranges": {"某编年史": [100, 120]},
                    "subjects": ["甲", "乙"],
                    "extraction_contract": "shared-neutral-v1",
                }
            }
        },
    }

    first = _shared_backbone_contract(project=project, ruler="甲")
    second = _shared_backbone_contract(project=project, ruler="乙")

    assert first == second
    assert first == {
        "material_token": "SHARED",
        "owners": ["乙", "甲"],
        "works": ["某编年史"],
        "page_ranges": {"某编年史": [100, 120]},
        "extraction_contract": "shared-neutral-v1",
    }


def test_shared_backbone_contract_rejects_per_ruler_redefinition_or_subject_drift() -> None:
    project = {
        "i5b_current_value": {
            "rulers": {
                "甲": {
                    "neutral_scan_backbone_material_token": "SHARED",
                    "neutral_scan_backbone_page_ranges": {"某编年史": [100, 120]},
                },
                "乙": {"neutral_scan_backbone_material_token": "SHARED"},
            }
        },
        "neutral_material_reuse": {
            "shared_chronicle_materials": {
                "SHARED": {
                    "works": ["某编年史"],
                    "page_ranges": {"某编年史": [100, 120]},
                    "subjects": ["甲", "乙"],
                    "extraction_contract": "shared-neutral-v1",
                }
            }
        },
    }

    with pytest.raises(ValueError, match="只能在中央目录定义"):
        _shared_backbone_contract(project=project, ruler="甲")

    del project["i5b_current_value"]["rulers"]["甲"][
        "neutral_scan_backbone_page_ranges"
    ]
    project["neutral_material_reuse"]["shared_chronicle_materials"]["SHARED"][
        "subjects"
    ] = ["甲"]
    with pytest.raises(ValueError, match="主体闭包与引用皇帝不一致"):
        _shared_backbone_contract(project=project, ruler="甲")


def test_new_ruler_overlapping_existing_catalog_must_reuse_token() -> None:
    project = {
        "i5b_current_value": {
            "rulers": {
                "前任": {"neutral_scan_backbone_material_token": "EXISTING"},
                "新任": {
                    "neutral_scan_backbone_works": ["某编年史"],
                    "neutral_scan_backbone_page_ranges": {"某编年史": [115, 125]},
                },
            }
        },
        "neutral_material_reuse": {
            "shared_chronicle_materials": {
                "EXISTING": {
                    "works": ["某编年史"],
                    "page_ranges": {"某编年史": [100, 120]},
                    "subjects": ["前任"],
                    "extraction_contract": "shared-neutral-v1",
                }
            }
        },
    }

    with pytest.raises(ValueError, match="重叠但未复用同一中央 token"):
        _shared_backbone_contract(project=project, ruler="新任")


def test_different_shared_tokens_may_not_own_overlapping_ranges() -> None:
    project = {
        "i5b_current_value": {
            "rulers": {
                "甲": {"neutral_scan_backbone_material_token": "FIRST"},
                "乙": {"neutral_scan_backbone_material_token": "SECOND"},
            }
        },
        "neutral_material_reuse": {
            "shared_chronicle_materials": {
                "FIRST": {
                    "works": ["另一编年史"],
                    "page_ranges": {"另一编年史": [10, 20]},
                    "subjects": ["甲"],
                    "extraction_contract": "shared-neutral-v1",
                },
                "SECOND": {
                    "works": ["另一编年史"],
                    "page_ranges": {"另一编年史": [20, 30]},
                    "subjects": ["乙"],
                    "extraction_contract": "shared-neutral-v1",
                },
            }
        },
    }

    with pytest.raises(ValueError, match="重叠但未复用同一中央 token"):
        _shared_backbone_contract(project=project, ruler="甲")


def test_two_ruler_local_ranges_must_be_promoted_when_they_overlap() -> None:
    project = {
        "i5b_current_value": {
            "rulers": {
                "甲": {
                    "neutral_scan_backbone_works": ["通史"],
                    "neutral_scan_backbone_page_ranges": {"通史": [40, 50]},
                },
                "乙": {
                    "neutral_scan_backbone_works": ["通史"],
                    "neutral_scan_backbone_page_ranges": {"通史": [48, 60]},
                },
            }
        }
    }

    with pytest.raises(ValueError, match="重叠但未复用同一中央 token"):
        _shared_backbone_contract(project=project, ruler="乙")


def test_current_tang_shared_backbone_has_one_contract_and_no_ruler_pack_reuse() -> None:
    project = yaml.safe_load((ROOT / "config/project.yml").read_text(encoding="utf-8"))
    rulers = project["i5b_current_value"]["rulers"]
    dynasty_execution = project["i5b_current_value"]["dynasty_execution"]
    neutral_reuse = project["neutral_material_reuse"]

    li_shimin = _shared_backbone_contract(project=project, ruler="李世民")
    li_yuan = _shared_backbone_contract(project=project, ruler="李渊")
    li_zhi = _shared_backbone_contract(project=project, ruler="李治")

    assert li_shimin == li_yuan
    assert li_zhi is None
    assert li_yuan == {
        "material_token": "TANG-EARLY-CONTINUOUS",
        "owners": ["李世民", "李渊"],
        "works": ["資治通鑑"],
        "page_ranges": {"資治通鑑": [184, 199]},
        "extraction_contract": "shared-ruler-chronicle-neutral-v2",
    }
    assert all(
        "neutral_scan_backbone_works" not in rulers[name]
        and "neutral_scan_backbone_page_ranges" not in rulers[name]
        and "neutral_scan_shared_subjects" not in rulers[name]
        for name in ("李世民", "李渊")
    )
    assert rulers["李治"]["neutral_scan_backbone_page_ranges"] == {
        "資治通鑑": [200, 203]
    }
    assert all(
        "neutral_material_reuse_rulers" not in configured
        for configured in rulers.values()
    )
    assert dynasty_execution == {
        "same_dynasty_ruler_mode": "serial",
        "governance_baseline_before_ruler_chain": True,
        "ruler_governance_increment_sources": [
            "ruler_chronicle",
            "person_biography",
        ],
        "next_ruler_requires_previous_public_registry_accepted": True,
    }
    assert neutral_reuse["single_dynasty_governance_workflow"] == (
        "docs/证据规则/单朝代治理会话工作流.md"
    )
    assert neutral_reuse["single_emperor_session_workflow"] == (
        "docs/证据规则/单皇帝主控会话工作流.md"
    )


def test_shared_subject_coverage_requires_every_ruler_window_to_be_resolved() -> None:
    plan = {
        "page_batches": [
            {
                "segments": [
                    {
                        "segment_ref": "SEG-A",
                        "subject_refs": ["RULER-A"],
                        "chronicle_ruler_ref": "RULER-A",
                    },
                    {
                        "segment_ref": "SEG-B",
                        "subject_refs": ["RULER-B"],
                        "chronicle_ruler_ref": "RULER-B",
                    },
                    {
                        "segment_ref": "SEG-B-NAMED",
                        "subject_refs": ["RULER-B"],
                    },
                ]
            }
        ]
    }
    materials = {
        "batch_results": [
            {
                "segment_reviews": [
                    {"segment_ref": "SEG-A"},
                    {"segment_ref": "SEG-B"},
                ]
            }
        ],
        "deterministic_routing": {
            "deterministic_empty_segment_refs": ["SEG-B-NAMED"]
        },
        "fanout": {
            "facts": [
                {
                    "fact_ref": "FACT-A",
                    "actors": [
                        {
                            "subject_ref": "RULER-A",
                            "role": "decision_maker",
                        }
                    ],
                }
            ]
        },
    }

    coverage = _shared_subject_coverage(
        plan=plan,
        materials=materials,
        owner_refs={"甲": "RULER-A", "乙": "RULER-B"},
        deterministic_empty_segment_refs=["SEG-B-NAMED"],
    )

    assert coverage["coverage_complete"] is True
    assert coverage["subjects"] == [
        {
            "canonical_name": "乙",
            "subject_ref": "RULER-B",
            "eligible_segment_count": 2,
            "window_segment_count": 1,
            "resolved_segment_count": 2,
            "neutral_fact_count": 0,
            "neutral_fact_refs": [],
            "missing_segment_refs": [],
            "coverage_complete": True,
        },
        {
            "canonical_name": "甲",
            "subject_ref": "RULER-A",
            "eligible_segment_count": 1,
            "window_segment_count": 1,
            "resolved_segment_count": 1,
            "neutral_fact_count": 1,
            "neutral_fact_refs": ["FACT-A"],
            "missing_segment_refs": [],
            "coverage_complete": True,
        },
    ]


def test_shared_subject_coverage_rejects_missing_or_unidentified_ruler_window() -> None:
    coverage = _shared_subject_coverage(
        plan={
            "page_batches": [
                {
                    "segments": [
                        {
                            "segment_ref": "SEG-A",
                            "subject_refs": ["RULER-A"],
                            "chronicle_ruler_ref": "RULER-A",
                        },
                        {
                            "segment_ref": "SEG-B",
                            "subject_refs": ["RULER-B"],
                        },
                    ]
                }
            ]
        },
        materials={
            "batch_results": [
                {"segment_reviews": [{"segment_ref": "SEG-A"}]}
            ],
            "deterministic_routing": {
                "deterministic_empty_segment_refs": []
            },
            "fanout": {"facts": []},
        },
        owner_refs={"甲": "RULER-A", "乙": "RULER-B"},
        deterministic_empty_segment_refs=[],
    )

    assert coverage["coverage_complete"] is False
    incomplete = next(
        row for row in coverage["subjects"] if row["subject_ref"] == "RULER-B"
    )
    assert incomplete["window_segment_count"] == 0
    assert incomplete["missing_segment_refs"] == ["SEG-B"]
    assert incomplete["coverage_complete"] is False


def test_shared_current_without_reproducible_subject_coverage_is_not_reusable() -> None:
    coverage = {
        "schema_version": "shared-chronicle-subject-coverage-v1",
        "coverage_complete": True,
        "subjects": [
            {"subject_ref": "RULER-A", "coverage_complete": True},
            {"subject_ref": "RULER-B", "coverage_complete": True},
        ],
    }

    assert _shared_current_has_complete_subject_coverage(
        candidate={
            "backbone_identity": "IDENTITY",
            "subject_coverage": coverage,
        },
        expected_backbone_identity="IDENTITY",
        recomputed_coverage=coverage,
    )
    assert not _shared_current_has_complete_subject_coverage(
        candidate={"backbone_identity": "IDENTITY"},
        expected_backbone_identity="IDENTITY",
        recomputed_coverage=coverage,
    )
    assert not _shared_current_has_complete_subject_coverage(
        candidate={
            "backbone_identity": "IDENTITY",
            "subject_coverage": {
                **coverage,
                "subjects": coverage["subjects"][:1],
            },
        },
        expected_backbone_identity="IDENTITY",
        recomputed_coverage=coverage,
    )


def test_shared_backbone_identity_does_not_change_with_current_ruler(
    tmp_path: Path,
) -> None:
    resolver = HistoricalEntityResolver.load(
        ROOT / "config/historical-entity-identities.yml"
    )
    index_path = tmp_path / "shared.sqlite3"
    build_local_source_index(
        [
            {
                "page_title": "資治通鑑/卷184",
                "work_title": "資治通鑑",
                "source_url": "local:184",
                "revision_ref": "1",
                "raw_text": (
                    "=== 高祖神堯大聖光孝皇帝 ===\n"
                    "上命秦王李世民统军，秦王奉诏出师。\n"
                    "=== 太宗文武大聖大廣孝皇帝 ===\n"
                    "上即皇帝位。"
                ),
            }
        ],
        index_path,
    )
    index = LocalSourceTextIndex(index_path)
    li_shimin_ref = resolver.entity_for_name("李世民").person_ref
    li_yuan_ref = resolver.entity_for_name("李渊").person_ref

    li_shimin_plan = build_ruler_neutral_plan(
        source_pack={
            "ruler": "李世民",
            "ruler_ref": li_shimin_ref,
            "members": [],
        },
        source_index=index,
        inventory={"subjects": []},
        identity_resolver=resolver,
        allowed_works=["資治通鑑"],
        allowed_page_ranges={"資治通鑑": [184, 184]},
        shared_subjects={"李渊": li_yuan_ref},
    )
    li_yuan_plan = build_ruler_neutral_plan(
        source_pack={
            "ruler": "李渊",
            "ruler_ref": li_yuan_ref,
            "members": [],
        },
        source_index=index,
        inventory={"subjects": []},
        identity_resolver=resolver,
        allowed_works=["資治通鑑"],
        allowed_page_ranges={"資治通鑑": [184, 184]},
        shared_subjects={"李世民": li_shimin_ref},
    )

    assert _shared_backbone_identity(li_shimin_plan) == _shared_backbone_identity(
        li_yuan_plan
    )
    assert {
        str(segment.get("chronicle_ruler_ref") or "")
        for batch in li_shimin_plan["page_batches"]
        for segment in batch["segments"]
        if segment.get("chronicle_ruler_ref")
    } == {li_shimin_ref, li_yuan_ref}
    assert {
        str(value)
        for batch in li_shimin_plan["page_batches"]
        for segment in batch["segments"]
        for value in segment["subject_refs"]
    } == {li_shimin_ref, li_yuan_ref}
    assert _shared_backbone_identity(
        li_shimin_plan, extraction_contract="shared-neutral-v1"
    ) != _shared_backbone_identity(
        li_shimin_plan, extraction_contract="shared-neutral-v2"
    )
    current = {
        "batch_fingerprints": {
            str(batch["batch_ref"]): neutral_digest(
                {
                    "batch": batch,
                    "extraction_policy": NEUTRAL_EXTRACTION_POLICY_VERSION,
                }
            )
            for batch in li_shimin_plan["page_batches"]
        },
        "batch_results": [
            {
                "schema_version": "shared-neutral-extraction-output-v2",
                "batch_ref": batch["batch_ref"],
                "page_title": batch["page_title"],
                "revision_ref": batch["revision_ref"],
                "segment_count": len(batch["segments"]),
                "segment_reviews": [
                    {
                        "segment_ref": segment["segment_ref"],
                        "decision": "reject",
                        "context_status": "sufficient",
                        "facts": [],
                        "reason": "测试共享原子已完成。",
                    }
                    for segment in batch["segments"]
                ],
                "limitations": [],
            }
            for batch in li_shimin_plan["page_batches"]
        ],
    }

    class NoCallRunner:
        def run(self, _prompt: str):
            raise AssertionError("同一共享 token 切换当前皇帝不得重新抽取")

    reused = extract_current_neutral_materials(
        plan=li_yuan_plan,
        current=current,
        runner=NoCallRunner(),
        max_workers=1,
        checkpoint_dir=tmp_path / "checkpoint",
        subject_ref_by_name={
            "李世民": li_shimin_ref,
            "李渊": li_yuan_ref,
        },
        identity_resolver=resolver,
    )
    assert reused["model_call_count"] == 0


def test_shared_atoms_project_to_each_ruler_before_directed_backsource() -> None:
    plan = {
        "page_batches": [
            {
                "segments": [
                    {
                        "segment_ref": "SEG-LIYUAN",
                        "chronicle_ruler_ref": "RULER-LIYUAN",
                    },
                    {
                        "segment_ref": "SEG-LISHIMIN",
                        "chronicle_ruler_ref": "RULER-LISHIMIN",
                    },
                ]
            }
        ]
    }
    signatures = [
        {
            "event_ref": "EVENT-LIYUAN-DELEGATION",
            "subject_bindings": [{"subject_ref": "RULER-LISHIMIN"}],
            "backbone_quotes": [{"segment_ref": "SEG-LIYUAN"}],
        },
        {
            "event_ref": "EVENT-LISHIMIN-REIGN",
            "subject_bindings": [{"subject_ref": "RULER-LISHIMIN"}],
            "backbone_quotes": [{"segment_ref": "SEG-LISHIMIN"}],
        },
    ]
    neutral = {
        "fanout": {
            "facts": [
                {
                    "fact_ref": "FACT-DELEGATED",
                    "segment_ref": "SEG-LIYUAN",
                    "actors": [{"subject_ref": "RULER-LISHIMIN"}],
                },
                {
                    "fact_ref": "FACT-LISHIMIN-REIGN",
                    "segment_ref": "SEG-LISHIMIN",
                    "actors": [{"subject_ref": "RULER-LISHIMIN"}],
                },
            ]
        }
    }

    li_yuan_signatures = _project_event_signatures_for_ruler(
        plan=plan,
        signatures=signatures,
        ruler_ref="RULER-LIYUAN",
    )
    li_shimin_signatures = _project_event_signatures_for_ruler(
        plan=plan,
        signatures=signatures,
        ruler_ref="RULER-LISHIMIN",
    )

    assert [row["event_ref"] for row in li_yuan_signatures] == [
        "EVENT-LIYUAN-DELEGATION"
    ]
    assert [row["event_ref"] for row in li_shimin_signatures] == [
        "EVENT-LIYUAN-DELEGATION",
        "EVENT-LISHIMIN-REIGN",
    ]
    assert _ruler_backbone_fact_refs(
        plan=plan,
        neutral_materials=neutral,
        ruler_ref="RULER-LIYUAN",
    ) == ["FACT-DELEGATED"]
    assert _ruler_backbone_fact_refs(
        plan=plan,
        neutral_materials=neutral,
        ruler_ref="RULER-LISHIMIN",
    ) == ["FACT-DELEGATED", "FACT-LISHIMIN-REIGN"]


def test_claimed_session_uses_owned_slots_and_reuses_completed_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = _session_release_fixture(tmp_path)
    monkeypatch.setattr(
        emperor_session_control, "_release_identity", lambda _root: "b" * 40
    )
    state = tmp_path / "state"
    lease = emperor_session_control.claim_session(
        state_root=state,
        release_root=release,
        session_id="SESSION-RUN",
        ruler="李世民",
        model_slot_count=2,
    )
    calls = []
    observed_stage = {}

    def rebuild(**kwargs):
        calls.append(kwargs)
        kwargs["stage_callback"](
            "neutral_materials",
            "quality_accepted",
            {
                "input_fingerprint": "NEUTRAL-INPUT",
                "producer_contract_fingerprint": "NEUTRAL-CONTRACT",
            },
        )
        observed_stage.update(
            emperor_session_control.session_status(state_root=state)["sessions"][0]
        )
        return {
            "schema_version": "emperor-rebuild-v1",
            "status": "rebuilt_before_database_write",
            "ruler": "李世民",
            "database_write_count": 0,
            "formal_score_write_count": 0,
            "stage_results": _accepted_rebuild_stage_results(),
        }

    monkeypatch.setattr(
        emperor_session_control,
        "rebuild_emperor",
        rebuild,
    )

    first = emperor_session_control.run_claimed_session(
        state_root=state,
        session_id="SESSION-RUN",
        release_root=release,
        source_index_root=tmp_path / "indexes",
        dynasty_governance_root=tmp_path / "governance",
        reuse_accepted_ruler_neutral=True,
    )
    second = emperor_session_control.run_claimed_session(
        state_root=state,
        session_id="SESSION-RUN",
        release_root=release,
        source_index_root=tmp_path / "indexes",
        dynasty_governance_root=tmp_path / "governance",
    )

    assert first["limits"]["model_workers"] == 2
    assert second["reused"] is True
    assert len(calls) == 1
    assert calls[0]["shared_backbone_root"] == Path(lease["shared_backbone_root"])
    assert calls[0]["stage_cache_root"] == Path(lease["stage_cache_root"])
    assert calls[0]["reuse_accepted_ruler_neutral"] is True
    assert observed_stage["stage"] == "neutral_materials"
    assert observed_stage["stage_status"] == "quality_accepted"
    assert observed_stage["stage_input_fingerprint"] == "NEUTRAL-INPUT"
    assert not (
        state / "session-control/shared-writers/TANG-EARLY-CONTINUOUS.json"
    ).exists()


def test_claimed_session_cannot_publish_without_every_stage_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = _session_release_fixture(tmp_path)
    monkeypatch.setattr(
        emperor_session_control, "_release_identity", lambda _root: "8" * 40
    )
    state = tmp_path / "state"
    emperor_session_control.claim_session(
        state_root=state,
        release_root=release,
        session_id="SESSION-MISSING-STAGE",
        ruler="李世民",
        model_slot_count=1,
    )
    monkeypatch.setattr(
        emperor_session_control,
        "rebuild_emperor",
        lambda **_kwargs: {
            "schema_version": "emperor-rebuild-v1",
            "status": "rebuilt_before_database_write",
            "ruler": "李世民",
            "database_write_count": 0,
            "formal_score_write_count": 0,
            "stage_results": _accepted_rebuild_stage_results()[:-1],
        },
    )

    with pytest.raises(
        emperor_session_control.SessionControlError,
        match="阶段监督清单不完整",
    ):
        emperor_session_control.run_claimed_session(
            state_root=state,
            session_id="SESSION-MISSING-STAGE",
            release_root=release,
            source_index_root=tmp_path / "indexes",
            dynasty_governance_root=tmp_path / "governance",
        )

    session = emperor_session_control.session_status(state_root=state)["sessions"][0]
    assert session["stage"] == "failed_reusable"


def test_failed_session_can_adopt_repaired_release_without_losing_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = _session_release_fixture(tmp_path)
    release_sha = {"value": "1" * 40}
    monkeypatch.setattr(
        emperor_session_control,
        "_release_identity",
        lambda _root: release_sha["value"],
    )
    state = tmp_path / "state"
    lease = emperor_session_control.claim_session(
        state_root=state,
        release_root=release,
        session_id="SESSION-UPGRADE",
        ruler="李治",
        model_slot_count=1,
    )
    lease_path = (
        state
        / "session-control/sessions/SESSION-UPGRADE/current.json"
    )
    failed = json.loads(lease_path.read_text(encoding="utf-8"))
    failed["stage"] = "failed_reusable"
    lease_path.write_text(
        json.dumps(failed, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    checkpoint = Path(lease["runtime_root"]) / "checkpoint/keep.json"
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.write_text("{}\n", encoding="utf-8")
    workspace_project_path = Path(lease["workspace_root"]) / "config/project.yml"
    workspace_project = yaml.safe_load(
        workspace_project_path.read_text(encoding="utf-8")
    )
    workspace_project["i5b_current_value"]["rulers"]["李治"][
        "dynasty_governance_material_token"
    ] = "TANG-GAOZONG-LEGACY"
    workspace_project_path.write_text(
        yaml.safe_dump(
            workspace_project, allow_unicode=True, sort_keys=False
        ),
        encoding="utf-8",
    )
    other_source_pack = release / "eval/i5b_current_value/李世民/source-pack.json"
    other_source_pack.write_text(
        other_source_pack.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    release_sha["value"] = "2" * 40

    report = emperor_session_control.upgrade_failed_session_release(
        state_root=state,
        session_id="SESSION-UPGRADE",
        release_root=release,
    )
    upgraded = json.loads(lease_path.read_text(encoding="utf-8"))

    assert report["from_release_sha"] == "1" * 40
    assert report["release_sha"] == "2" * 40
    assert report["checkpoint_preserved"] is True
    assert checkpoint.is_file()
    assert upgraded["stage"] == "failed_reusable"
    assert upgraded["release_sha"] == "2" * 40
    refreshed_project = yaml.safe_load(
        workspace_project_path.read_text(encoding="utf-8")
    )
    assert refreshed_project["i5b_current_value"]["rulers"]["李治"][
        "dynasty_governance_material_token"
    ] == "TANG"
    workspace_other_source_pack = (
        Path(lease["workspace_root"])
        / "eval/i5b_current_value/李世民/source-pack.json"
    )
    assert workspace_other_source_pack.read_bytes() == other_source_pack.read_bytes()
    assert report["other_ruler_canonical_refreshes"] == [
        "eval/i5b_current_value/李世民/source-pack.json"
    ]


def test_bootstrap_assets_required_session_can_adopt_repaired_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = _session_release_fixture(tmp_path)
    release_sha = {"value": "1" * 40}
    monkeypatch.setattr(
        emperor_session_control,
        "_release_identity",
        lambda _root: release_sha["value"],
    )
    state = tmp_path / "state"
    lease = emperor_session_control.claim_session(
        state_root=state,
        release_root=release,
        session_id="SESSION-BOOTSTRAP-UPGRADE",
        ruler="李治",
        model_slot_count=1,
    )
    lease_path = (
        state
        / "session-control/sessions/SESSION-BOOTSTRAP-UPGRADE/current.json"
    )
    waiting = json.loads(lease_path.read_text(encoding="utf-8"))
    waiting["stage"] = "bootstrap_assets_required"
    waiting["bootstrap_spec"] = str(tmp_path / "bootstrap-spec.json")
    lease_path.write_text(
        json.dumps(waiting, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    checkpoint = Path(lease["runtime_root"]) / "checkpoint/keep.json"
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.write_text("{}\n", encoding="utf-8")
    release_sha["value"] = "2" * 40

    report = emperor_session_control.upgrade_failed_session_release(
        state_root=state,
        session_id="SESSION-BOOTSTRAP-UPGRADE",
        release_root=release,
    )
    upgraded = json.loads(lease_path.read_text(encoding="utf-8"))

    assert report["release_sha"] == "2" * 40
    assert report["checkpoint_preserved"] is True
    assert checkpoint.is_file()
    assert upgraded["stage"] == "bootstrap_assets_required"
    assert upgraded["release_sha"] == "2" * 40


def test_awaiting_review_session_can_adopt_repaired_release_without_losing_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = _session_release_fixture(tmp_path)
    release_sha = {"value": "1" * 40}
    monkeypatch.setattr(
        emperor_session_control,
        "_release_identity",
        lambda _root: release_sha["value"],
    )
    state = tmp_path / "state"
    lease = emperor_session_control.claim_session(
        state_root=state,
        release_root=release,
        session_id="SESSION-REVIEW-UPGRADE",
        ruler="李治",
        model_slot_count=1,
    )
    lease_path = (
        state
        / "session-control/sessions/SESSION-REVIEW-UPGRADE/current.json"
    )
    waiting = json.loads(lease_path.read_text(encoding="utf-8"))
    waiting["stage"] = "awaiting_review"
    waiting["review_stage"] = "outcome_projection"
    lease_path.write_text(
        json.dumps(waiting, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    checkpoint = Path(lease["runtime_root"]) / "checkpoint/keep.json"
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.write_text("{}\n", encoding="utf-8")
    registry_path = release / "eval/historical_outcome_registry/current.json"
    registry_path.write_text('{"migrated": true}\n', encoding="utf-8")
    release_sha["value"] = "2" * 40

    report = emperor_session_control.upgrade_failed_session_release(
        state_root=state,
        session_id="SESSION-REVIEW-UPGRADE",
        release_root=release,
    )
    upgraded = json.loads(lease_path.read_text(encoding="utf-8"))

    assert report["release_sha"] == "2" * 40
    assert checkpoint.is_file()
    assert upgraded["stage"] == "awaiting_review"
    assert upgraded["review_stage"] == "outcome_projection"
    assert report["shared_canonical_migrations"] == ["outcome_registry_json"]
    assert upgraded["canonical_expected_sha256"]["outcome_registry_json"] == (
        hashlib.sha256(registry_path.read_bytes()).hexdigest()
    )


@pytest.mark.acceptance
@pytest.mark.parametrize("lease_stage", ["awaiting_review", "failed_reusable"])
def test_review_upgrade_preserves_quality_accepted_stage_source_pack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, lease_stage: str
) -> None:
    release = _session_release_fixture(tmp_path)
    release_sha = {"value": "1" * 40}
    monkeypatch.setattr(
        emperor_session_control,
        "_release_identity",
        lambda _root: release_sha["value"],
    )
    state = tmp_path / "state"
    lease = emperor_session_control.claim_session(
        state_root=state,
        release_root=release,
        session_id="SESSION-ACCEPTED-STAGE-UPGRADE",
        ruler="李治",
        model_slot_count=1,
    )
    lease_path = (
        state
        / "session-control/sessions/SESSION-ACCEPTED-STAGE-UPGRADE/current.json"
    )
    waiting = json.loads(lease_path.read_text(encoding="utf-8"))
    waiting["stage"] = lease_stage
    waiting["review_stage"] = "outcome_projection"
    lease_path.write_text(
        json.dumps(waiting, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    configured = yaml.safe_load(
        (release / "config/project.yml").read_text(encoding="utf-8")
    )["i5b_current_value"]["rulers"]["李治"]
    workspace_pack = Path(lease["workspace_root"]) / configured["source_pack"]
    accepted = json.loads(workspace_pack.read_text(encoding="utf-8"))
    accepted["facts"] = [{"record_ref": "PFACT-SESSION-ACCEPTED"}]
    accepted.pop("source_pack_sha256", None)
    accepted["source_pack_sha256"] = emperor_session_control._digest(accepted)
    workspace_pack.write_text(
        json.dumps(accepted, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    accepted_sha = hashlib.sha256(workspace_pack.read_bytes()).hexdigest()
    stage_root = (
        Path(lease["runtime_root"]) / "stages" / "outcome_projection"
    )
    stage_root.mkdir(parents=True)
    shutil.copy2(workspace_pack, stage_root / "source_pack.json")
    (stage_root / "current.json").write_text(
        json.dumps(
            {
                "schema_version": "emperor-stage-manifest-v1",
                "stage": "outcome_projection",
                "status": "quality_accepted",
                "artifacts": {
                    "source_pack": {
                        "file": "source_pack.json",
                        "sha256": accepted_sha,
                    }
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    release_pack = release / configured["source_pack"]
    release_pack.write_text(
        release_pack.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    release_sha["value"] = "2" * 40

    report = emperor_session_control.upgrade_failed_session_release(
        state_root=state,
        session_id="SESSION-ACCEPTED-STAGE-UPGRADE",
        release_root=release,
    )
    upgraded = json.loads(lease_path.read_text(encoding="utf-8"))

    assert report["accepted_stage_source_pack_preserved"] is True
    assert report["accepted_stage_source_pack_restored"] is False
    assert json.loads(workspace_pack.read_text(encoding="utf-8")) == accepted
    assert upgraded["canonical_expected_sha256"]["source_pack"] == accepted_sha
    assert upgraded["stage"] == lease_stage
    assert upgraded["review_stage"] == "outcome_projection"


@pytest.mark.acceptance
def test_failed_review_upgrade_restores_quality_accepted_stage_source_pack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = _session_release_fixture(tmp_path)
    release_sha = {"value": "1" * 40}
    monkeypatch.setattr(
        emperor_session_control,
        "_release_identity",
        lambda _root: release_sha["value"],
    )
    state = tmp_path / "state"
    lease = emperor_session_control.claim_session(
        state_root=state,
        release_root=release,
        session_id="SESSION-FAILED-REVIEW-RESTORE",
        ruler="李治",
        model_slot_count=1,
    )
    lease_path = (
        state
        / "session-control/sessions/SESSION-FAILED-REVIEW-RESTORE/current.json"
    )
    failed = json.loads(lease_path.read_text(encoding="utf-8"))
    failed["stage"] = "failed_reusable"
    failed["review_stage"] = "outcome_projection"
    lease_path.write_text(
        json.dumps(failed, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    configured = yaml.safe_load(
        (release / "config/project.yml").read_text(encoding="utf-8")
    )["i5b_current_value"]["rulers"]["李治"]
    workspace_pack = Path(lease["workspace_root"]) / configured["source_pack"]
    accepted = json.loads(workspace_pack.read_text(encoding="utf-8"))
    accepted["facts"] = [{"record_ref": "PFACT-ACCEPTED"}]
    accepted.pop("source_pack_sha256", None)
    accepted["source_pack_sha256"] = emperor_session_control._digest(accepted)
    workspace_pack.write_text(
        json.dumps(accepted, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    accepted_sha = hashlib.sha256(workspace_pack.read_bytes()).hexdigest()
    stage_root = (
        Path(lease["runtime_root"]) / "stages" / "outcome_projection"
    )
    stage_root.mkdir(parents=True)
    shutil.copy2(workspace_pack, stage_root / "source_pack.json")
    (stage_root / "current.json").write_text(
        json.dumps(
            {
                "schema_version": "emperor-stage-manifest-v1",
                "stage": "outcome_projection",
                "status": "quality_accepted",
                "artifacts": {
                    "source_pack": {
                        "file": "source_pack.json",
                        "sha256": accepted_sha,
                    }
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    failed_replay = json.loads(
        json.dumps(accepted, ensure_ascii=False)
    )
    failed_replay["facts"].append({"record_ref": "PFACT-FAILED-REPLAY"})
    failed_replay.pop("source_pack_sha256", None)
    failed_replay["source_pack_sha256"] = emperor_session_control._digest(
        failed_replay
    )
    workspace_pack.write_text(
        json.dumps(
            failed_replay, ensure_ascii=False, indent=2, sort_keys=True
        )
        + "\n",
        encoding="utf-8",
    )
    release_sha["value"] = "2" * 40

    report = emperor_session_control.upgrade_failed_session_release(
        state_root=state,
        session_id="SESSION-FAILED-REVIEW-RESTORE",
        release_root=release,
    )

    assert report["accepted_stage_source_pack_preserved"] is True
    assert report["accepted_stage_source_pack_restored"] is True
    assert json.loads(workspace_pack.read_text(encoding="utf-8")) == accepted
    upgraded = json.loads(lease_path.read_text(encoding="utf-8"))
    assert upgraded["canonical_expected_sha256"]["source_pack"] == accepted_sha


@pytest.mark.acceptance
def test_release_upgrade_still_rejects_current_ruler_source_pack_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = _session_release_fixture(tmp_path)
    release_sha = {"value": "1" * 40}
    monkeypatch.setattr(
        emperor_session_control,
        "_release_identity",
        lambda _root: release_sha["value"],
    )
    state = tmp_path / "state"
    emperor_session_control.claim_session(
        state_root=state,
        release_root=release,
        session_id="SESSION-PROTECTED-UPGRADE",
        ruler="李治",
        model_slot_count=1,
    )
    lease_path = (
        state
        / "session-control/sessions/SESSION-PROTECTED-UPGRADE/current.json"
    )
    failed = json.loads(lease_path.read_text(encoding="utf-8"))
    failed["stage"] = "failed_reusable"
    lease_path.write_text(
        json.dumps(failed, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    configured = yaml.safe_load(
        (release / "config/project.yml").read_text(encoding="utf-8")
    )["i5b_current_value"]["rulers"]["李治"]
    source_pack = release / configured["source_pack"]
    source_pack.write_text('{"changed": true}\n', encoding="utf-8")
    release_sha["value"] = "2" * 40

    with pytest.raises(
        emperor_session_control.SessionControlError,
        match="source_pack",
    ):
        emperor_session_control.upgrade_failed_session_release(
            state_root=state,
            session_id="SESSION-PROTECTED-UPGRADE",
            release_root=release,
        )


@pytest.mark.acceptance
def test_release_upgrade_adopts_only_empty_current_ruler_registry_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = _session_release_fixture(tmp_path)
    configured = yaml.safe_load(
        (release / "config/project.yml").read_text(encoding="utf-8")
    )["i5b_current_value"]["rulers"]["李治"]
    source_pack_path = release / configured["source_pack"]
    source_pack = json.loads(source_pack_path.read_text(encoding="utf-8"))
    assert source_pack["outcome_registry"]["clusters"] == []
    source_pack["outcome_registry"]["schema_version"] = (
        "historical-outcome-cluster-registry-v2"
    )
    source_pack.pop("source_pack_sha256", None)
    source_pack["source_pack_sha256"] = emperor_session_control._digest(source_pack)
    source_pack_path.write_text(
        json.dumps(source_pack, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    release_sha = {"value": "1" * 40}
    monkeypatch.setattr(
        emperor_session_control,
        "_release_identity",
        lambda _root: release_sha["value"],
    )
    state = tmp_path / "state"
    lease = emperor_session_control.claim_session(
        state_root=state,
        release_root=release,
        session_id="SESSION-EMPTY-REGISTRY-UPGRADE",
        ruler="李治",
        model_slot_count=1,
    )
    lease_path = (
        state
        / "session-control/sessions/SESSION-EMPTY-REGISTRY-UPGRADE/current.json"
    )
    failed = json.loads(lease_path.read_text(encoding="utf-8"))
    failed["stage"] = "failed_reusable"
    lease_path.write_text(
        json.dumps(failed, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    source_pack["outcome_registry"]["schema_version"] = (
        "historical-outcome-cluster-registry-v3"
    )
    source_pack.pop("source_pack_sha256", None)
    source_pack["source_pack_sha256"] = emperor_session_control._digest(source_pack)
    source_pack_path.write_text(
        json.dumps(source_pack, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    release_sha["value"] = "2" * 40

    report = emperor_session_control.upgrade_failed_session_release(
        state_root=state,
        session_id="SESSION-EMPTY-REGISTRY-UPGRADE",
        release_root=release,
    )

    assert report["current_ruler_source_pack_schema_migration"] == (
        "empty_outcome_registry_v2_to_v3"
    )
    workspace_pack = Path(lease["workspace_root"]) / configured["source_pack"]
    assert workspace_pack.read_bytes() == source_pack_path.read_bytes()
    upgraded = json.loads(lease_path.read_text(encoding="utf-8"))
    assert upgraded["canonical_expected_sha256"]["source_pack"] == hashlib.sha256(
        source_pack_path.read_bytes()
    ).hexdigest()


@pytest.mark.acceptance
@pytest.mark.parametrize("bootstrap_source_pack", [False, True])
def test_release_upgrade_resets_v2_outcome_review_but_preserves_verified_facts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bootstrap_source_pack: bool,
) -> None:
    release = _session_release_fixture(tmp_path)
    configured = yaml.safe_load(
        (release / "config/project.yml").read_text(encoding="utf-8")
    )["i5b_current_value"]["rulers"]["李治"]
    source_pack_path = release / configured["source_pack"]
    source_pack = json.loads(source_pack_path.read_text(encoding="utf-8"))
    source_pack["outcome_registry"]["schema_version"] = (
        "historical-outcome-cluster-registry-v2"
    )
    source_pack.pop("source_pack_sha256", None)
    source_pack["source_pack_sha256"] = emperor_session_control._digest(source_pack)
    source_pack_path.write_text(
        json.dumps(source_pack, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    release_sha = {"value": "1" * 40}
    monkeypatch.setattr(
        emperor_session_control,
        "_release_identity",
        lambda _root: release_sha["value"],
    )
    state = tmp_path / "state"
    lease = emperor_session_control.claim_session(
        state_root=state,
        release_root=release,
        session_id="SESSION-OUTCOME-CONTRACT-RESET",
        ruler="李治",
        model_slot_count=1,
    )
    lease_path = (
        state
        / "session-control/sessions/SESSION-OUTCOME-CONTRACT-RESET/current.json"
    )
    waiting = json.loads(lease_path.read_text(encoding="utf-8"))
    waiting["stage"] = "awaiting_review"
    waiting["review_stage"] = "outcome_projection"
    if bootstrap_source_pack:
        waiting["bootstrap_spec"] = str(tmp_path / "bootstrap-spec.json")
        waiting["canonical_expected_sha256"].pop("source_pack", None)
    lease_path.write_text(
        json.dumps(waiting, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    checkpoint = Path(lease["runtime_root"]) / "checkpoint/keep.json"
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.write_text("{}\n", encoding="utf-8")

    workspace_pack_path = Path(lease["workspace_root"]) / configured["source_pack"]
    workspace_pack = json.loads(workspace_pack_path.read_text(encoding="utf-8"))
    workspace_pack["facts"] = [
        {
            "record_ref": "PFACT-VERIFIED-001",
            "assertions": [{"assertion_ref": "ASSERTION-VERIFIED-001"}],
        }
    ]
    workspace_pack["outcome_registry"]["clusters"] = [
        {"outcome_ref": "HOUT-REVIEWED-001"}
    ]
    workspace_pack["three_channel_disposition"] = {
        "dynasty_governance": {"ruler_window_achievement_count": 1}
    }
    workspace_pack.pop("source_pack_sha256", None)
    workspace_pack["source_pack_sha256"] = emperor_session_control._digest(
        workspace_pack
    )
    workspace_pack_path.write_text(
        json.dumps(
            workspace_pack, ensure_ascii=False, indent=2, sort_keys=True
        )
        + "\n",
        encoding="utf-8",
    )

    source_pack["outcome_registry"]["schema_version"] = (
        "historical-outcome-cluster-registry-v3"
    )
    source_pack.pop("source_pack_sha256", None)
    source_pack["source_pack_sha256"] = emperor_session_control._digest(source_pack)
    source_pack_path.write_text(
        json.dumps(source_pack, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    release_sha["value"] = "2" * 40

    report = emperor_session_control.upgrade_failed_session_release(
        state_root=state,
        session_id="SESSION-OUTCOME-CONTRACT-RESET",
        release_root=release,
    )

    migrated = json.loads(workspace_pack_path.read_text(encoding="utf-8"))
    assert migrated["facts"] == workspace_pack["facts"]
    assert migrated["outcome_registry"]["schema_version"] == (
        "historical-outcome-cluster-registry-v3"
    )
    assert migrated["outcome_registry"]["clusters"] == []
    assert "three_channel_disposition" not in migrated
    assert migrated["source_pack_sha256"] == emperor_session_control._digest(
        {
            key: value
            for key, value in migrated.items()
            if key != "source_pack_sha256"
        }
    )
    assert checkpoint.is_file()
    assert report["outcome_review_contract_reset"] == {
        "invalidated_outcome_count": 1,
        "preserved_fact_count": 1,
        "review_payload_reuse_allowed": False,
    }
    upgraded = json.loads(lease_path.read_text(encoding="utf-8"))
    assert upgraded["stage"] == "awaiting_review"
    assert upgraded["review_stage"] == "outcome_projection"
    assert upgraded["canonical_expected_sha256"]["source_pack"] == hashlib.sha256(
        workspace_pack_path.read_bytes()
    ).hexdigest()

    if bootstrap_source_pack:
        source_pack_path.unlink()
    release_sha["value"] = "3" * 40
    followup = emperor_session_control.upgrade_failed_session_release(
        state_root=state,
        session_id="SESSION-OUTCOME-CONTRACT-RESET",
        release_root=release,
    )
    assert followup["session_owned_outcome_review_pack_preserved"] is True
    assert json.loads(workspace_pack_path.read_text(encoding="utf-8")) == migrated


@pytest.mark.acceptance
def test_release_upgrade_refreshes_other_ruler_pack_before_shared_render(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = _session_release_fixture(tmp_path)
    release_sha = {"value": "1" * 40}
    monkeypatch.setattr(
        emperor_session_control,
        "_release_identity",
        lambda _root: release_sha["value"],
    )
    state = tmp_path / "state"
    lease = emperor_session_control.claim_session(
        state_root=state,
        release_root=release,
        session_id="SESSION-SHARED-BASELINE-UPGRADE",
        ruler="李治",
        model_slot_count=1,
    )
    lease_path = (
        state
        / "session-control/sessions/SESSION-SHARED-BASELINE-UPGRADE/current.json"
    )
    failed = json.loads(lease_path.read_text(encoding="utf-8"))
    failed["stage"] = "failed_reusable"
    lease_path.write_text(
        json.dumps(failed, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    workspace = Path(lease["workspace_root"])
    other_source_pack = (
        workspace / "eval/i5b_current_value/李世民/source-pack.json"
    )
    stale = json.loads(other_source_pack.read_text(encoding="utf-8"))
    for outcome in stale["outcome_registry"]["clusters"]:
        if outcome["outcome_kind"] == "governance":
            outcome["payload"].pop("value_judgment", None)
    other_source_pack.write_text(
        json.dumps(stale, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    release_sha["value"] = "2" * 40

    report = emperor_session_control.upgrade_failed_session_release(
        state_root=state,
        session_id="SESSION-SHARED-BASELINE-UPGRADE",
        release_root=release,
    )
    refreshed = json.loads(other_source_pack.read_text(encoding="utf-8"))
    governance = [
        row
        for row in refreshed["outcome_registry"]["clusters"]
        if row["outcome_kind"] == "governance"
    ]

    assert governance
    assert all("value_judgment" in row["payload"] for row in governance)
    assert report["other_ruler_canonical_refreshes"] == [
        "eval/i5b_current_value/李世民/source-pack.json"
    ]
    published = write_current_outcome_layers(workspace)
    assert Path(published["registry_json"]).is_file()
    assert Path(published["registry_markdown"]).is_file()


def test_claimed_session_can_pause_after_outcome_review_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = _session_release_fixture(tmp_path)
    monkeypatch.setattr(
        emperor_session_control, "_release_identity", lambda _root: "7" * 40
    )
    state = tmp_path / "state"
    emperor_session_control.claim_session(
        state_root=state,
        release_root=release,
        session_id="SESSION-OUTCOME-REVIEW",
        ruler="李世民",
        model_slot_count=1,
    )
    observed = {}

    def rebuild(**kwargs):
        observed.update(kwargs)
        return {
            "schema_version": "emperor-rebuild-review-v1",
            "status": "awaiting_review",
            "ruler": "李世民",
            "review_stage": "outcome_projection",
            "database_write_count": 0,
            "formal_score_write_count": 0,
            "stage_results": _accepted_rebuild_stage_results()[:3],
        }

    monkeypatch.setattr(emperor_session_control, "rebuild_emperor", rebuild)

    result = emperor_session_control.run_claimed_session(
        state_root=state,
        session_id="SESSION-OUTCOME-REVIEW",
        release_root=release,
        source_index_root=tmp_path / "indexes",
        dynasty_governance_root=tmp_path / "governance",
        stop_after_stage="outcome_projection",
    )

    session = emperor_session_control.session_status(state_root=state)["sessions"][0]
    assert result["status"] == "awaiting_review"
    assert observed["stop_after_stage"] == "outcome_projection"
    assert observed["outcome_review_path"] is None
    assert observed["allow_outcome_model_draft"] is False
    assert "governance_review_only" not in observed
    assert session["stage"] == "awaiting_review"
    assert session["review_stage"] == "outcome_projection"
    with pytest.raises(
        emperor_session_control.SessionControlError,
        match="尚未完成重建与质量验证",
    ):
        emperor_session_control.publish_session(
            state_root=state,
            session_id="SESSION-OUTCOME-REVIEW",
            canonical_root=release,
        )


def test_claimed_session_defaults_to_main_outcome_review_worklist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = _session_release_fixture(tmp_path)
    monkeypatch.setattr(
        emperor_session_control, "_release_identity", lambda _root: "8" * 40
    )
    state = tmp_path / "state"
    emperor_session_control.claim_session(
        state_root=state,
        release_root=release,
        session_id="SESSION-MAIN-OUTCOME-REVIEW",
        ruler="李世民",
        model_slot_count=1,
    )
    observed = {}

    def rebuild(**kwargs):
        observed.update(kwargs)
        return {
            "schema_version": "emperor-rebuild-review-v1",
            "status": "awaiting_review",
            "ruler": "李世民",
            "review_stage": "neutral_materials",
            "outcome_review_worklist": "runtime/review/outcome-worklist.json",
            "database_write_count": 0,
            "formal_score_write_count": 0,
            "stage_results": _accepted_rebuild_stage_results()[:2],
        }

    monkeypatch.setattr(emperor_session_control, "rebuild_emperor", rebuild)

    result = emperor_session_control.run_claimed_session(
        state_root=state,
        session_id="SESSION-MAIN-OUTCOME-REVIEW",
        release_root=release,
        source_index_root=tmp_path / "indexes",
        dynasty_governance_root=tmp_path / "governance",
    )

    session = emperor_session_control.session_status(state_root=state)["sessions"][0]
    assert result["status"] == "awaiting_review"
    assert result["review_stage"] == "neutral_materials"
    assert observed["outcome_review_path"] is None
    assert observed["allow_outcome_model_draft"] is False
    assert session["stage"] == "awaiting_review"
    assert session["review_stage"] == "neutral_materials"


@pytest.mark.acceptance
def test_session_publish_fails_closed_when_canonical_changed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = _session_release_fixture(tmp_path)
    canonical = tmp_path / "canonical"
    shutil.copytree(release, canonical)
    monkeypatch.setattr(
        emperor_session_control, "_release_identity", lambda _root: "c" * 40
    )
    state = tmp_path / "state"
    lease = emperor_session_control.claim_session(
        state_root=state,
        release_root=release,
        session_id="SESSION-PUBLISH",
        ruler="李世民",
        model_slot_count=1,
    )
    monkeypatch.setattr(
        emperor_session_control,
        "rebuild_emperor",
        lambda **_kwargs: {
            "schema_version": "emperor-rebuild-v1",
            "status": "rebuilt_before_database_write",
            "ruler": "李世民",
            "database_write_count": 0,
            "formal_score_write_count": 0,
            "stage_results": _accepted_rebuild_stage_results(),
        },
    )
    emperor_session_control.run_claimed_session(
        state_root=state,
        session_id="SESSION-PUBLISH",
        release_root=release,
        source_index_root=tmp_path / "indexes",
        dynasty_governance_root=tmp_path / "governance",
    )
    _write_bootstrap_binding(Path(lease["workspace_root"]), "李治")
    target = canonical / "eval/i5b_current_value/李世民/result.md"
    target.write_text(target.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8")

    with pytest.raises(
        emperor_session_control.SessionControlError,
        match="canonical 在会话运行期间已变化",
    ):
        emperor_session_control.publish_session(
            state_root=state,
            session_id="SESSION-PUBLISH",
            canonical_root=canonical,
        )


@pytest.mark.acceptance
def test_session_publish_validates_all_people_and_releases_current_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = _session_release_fixture(tmp_path)
    canonical = tmp_path / "canonical"
    shutil.copytree(release, canonical)
    monkeypatch.setattr(
        emperor_session_control, "_release_identity", lambda _root: "d" * 40
    )
    monkeypatch.setattr(
        emperor_session_control,
        "rebuild_emperor",
        lambda **_kwargs: {
            "schema_version": "emperor-rebuild-v1",
            "status": "rebuilt_before_database_write",
            "ruler": "李世民",
            "database_write_count": 0,
            "formal_score_write_count": 0,
            "stage_results": _accepted_rebuild_stage_results(),
        },
    )
    state = tmp_path / "state"
    lease = emperor_session_control.claim_session(
        state_root=state,
        release_root=release,
        session_id="SESSION-PUBLISH-OK",
        ruler="李世民",
        model_slot_count=1,
    )
    stage_cache = Path(lease["stage_cache_root"])
    stage_cache.mkdir(parents=True)
    (stage_cache / "temporary-stage.json").write_text(
        "{}\n", encoding="utf-8"
    )
    emperor_session_control.run_claimed_session(
        state_root=state,
        session_id="SESSION-PUBLISH-OK",
        release_root=release,
        source_index_root=tmp_path / "indexes",
        dynasty_governance_root=tmp_path / "governance",
    )
    _write_bootstrap_binding(Path(lease["workspace_root"]), "李治")

    result = emperor_session_control.publish_session(
        state_root=state,
        session_id="SESSION-PUBLISH-OK",
        canonical_root=canonical,
    )

    assert result["status"] == "published_current"
    assert result["database_write_count"] == 0
    assert len(
        [
            key
            for key in result["published_sha256"]
            if key.startswith("outcome_binding")
        ]
    ) == 4
    registry = json.loads(
        (canonical / "eval/historical_outcome_registry/current.json").read_text(
            encoding="utf-8"
        )
    )
    for ruler in ("李世民", "李渊", "刘邦"):
        binding = json.loads(
            (
                canonical / "eval/historical_outcome_bindings" / f"{ruler}.json"
            ).read_text(encoding="utf-8")
        )
        assert binding["registry_fingerprint"] == registry["registry_fingerprint"]
    assert emperor_session_control.session_status(state_root=state)["sessions"] == []
    assert not list((state / "session-control/model-slots").glob("*.json"))
    assert not stage_cache.exists()


@pytest.mark.acceptance
def test_bootstrap_ruler_publish_atomically_adds_config_and_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = _session_release_fixture(tmp_path)
    canonical = tmp_path / "canonical"
    shutil.copytree(release, canonical)
    monkeypatch.setattr(
        emperor_session_control, "_release_identity", lambda _root: "d" * 40
    )
    state = tmp_path / "state"
    lease = emperor_session_control.claim_session(
        state_root=state,
        release_root=release,
        session_id="SESSION-ZHU-PUBLISH",
        ruler="朱元璋",
        model_slot_count=1,
    )
    workspace = Path(lease["workspace_root"])
    configured = {
        "source_pack": "eval/i5b_current_value/朱元璋/source-pack.json",
        "outcome_binding": "eval/historical_outcome_bindings/朱元璋.json",
        "neutral_materials": "eval/i5b_current_value/朱元璋/neutral-materials.json",
        "result": "eval/i5b_current_value/朱元璋/result.json",
        "neutral_scan_backbone_works": ["明太祖實錄"],
        "neutral_scan_backbone_page_ranges": {"明太祖實錄": [1, 2]},
        "neutral_scan_backsource_works": ["明史"],
        "dynasty_governance_material_token": "MING-HONGWU",
        "dynasty_governance_period_terms": ["洪武", "明太祖"],
    }
    project_path = workspace / "config/project.yml"
    project = yaml.safe_load(project_path.read_text(encoding="utf-8"))
    project["i5b_current_value"]["rulers"]["朱元璋"] = configured
    project_path.write_text(
        yaml.safe_dump(project, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    identity_path = workspace / "config/historical-entity-identities.yml"
    identities = yaml.safe_load(identity_path.read_text(encoding="utf-8"))
    identities["entities"].append(
        {
            "person_ref": "RULER-MING-ZHUYUANZHANG",
            "canonical_name": "朱元璋",
            "dynasty": "明",
            "aliases": [
                {"surface": "明太祖", "alias_type": "temple_name"}
            ],
        }
    )
    identity_path.write_text(
        yaml.safe_dump(identities, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    source_paths = emperor_session_control._canonical_paths(
        workspace, configured
    )
    for key, source in source_paths.items():
        source.parent.mkdir(parents=True, exist_ok=True)
        if not source.exists():
            source.write_text(
                "bootstrap markdown\n" if key.endswith("markdown") else "{}\n",
                encoding="utf-8",
            )
    monkeypatch.setattr(
        emperor_session_control,
        "_validate_publish_payload",
        lambda **_kwargs: source_paths,
    )
    target_paths = emperor_session_control._canonical_paths(
        canonical, configured
    )
    current_path = (
        state
        / "session-control/sessions/SESSION-ZHU-PUBLISH/current.json"
    )
    current = json.loads(current_path.read_text(encoding="utf-8"))
    current.update(
        {
            "stage": "ready_to_publish",
            "bootstrap_required": False,
            "bootstrap_spec": str(tmp_path / "bootstrap-spec.json"),
            "ruler_ref": "RULER-MING-ZHUYUANZHANG",
            "canonical_expected_sha256": {
                key: emperor_session_control._file_sha256(target)
                for key, target in target_paths.items()
            },
        }
    )
    current_path.write_text(
        json.dumps(current, ensure_ascii=False), encoding="utf-8"
    )

    result = emperor_session_control.publish_session(
        state_root=state,
        session_id="SESSION-ZHU-PUBLISH",
        canonical_root=canonical,
    )

    assert result["status"] == "published_current"
    canonical_project = yaml.safe_load(
        (canonical / "config/project.yml").read_text(encoding="utf-8")
    )
    assert canonical_project["i5b_current_value"]["rulers"]["朱元璋"] == configured
    canonical_identities = yaml.safe_load(
        (
            canonical / "config/historical-entity-identities.yml"
        ).read_text(encoding="utf-8")
    )
    assert any(
        row["canonical_name"] == "朱元璋"
        and row["person_ref"] == "RULER-MING-ZHUYUANZHANG"
        for row in canonical_identities["entities"]
    )
    assert (
        canonical / "eval/i5b_current_value/朱元璋/source-pack.json"
    ).is_file()
    assert emperor_session_control.session_status(state_root=state)["sessions"] == []


def test_session_abandon_preserves_quality_accepted_stage_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = _session_release_fixture(tmp_path)
    monkeypatch.setattr(
        emperor_session_control, "_release_identity", lambda _root: "9" * 40
    )
    state = tmp_path / "state"
    lease = emperor_session_control.claim_session(
        state_root=state,
        release_root=release,
        session_id="SESSION-ABANDON-CACHE",
        ruler="李世民",
        model_slot_count=1,
    )
    stage_cache = Path(lease["stage_cache_root"])
    stage_cache.mkdir(parents=True)
    accepted = stage_cache / "neutral_materials/current.json"
    accepted.parent.mkdir(parents=True)
    accepted.write_text('{"status":"quality_accepted"}\n', encoding="utf-8")

    emperor_session_control.abandon_session(
        state_root=state,
        session_id="SESSION-ABANDON-CACHE",
    )

    assert accepted.is_file()


def test_accepted_ruler_neutral_reuse_requires_verified_stage_artifact(
    tmp_path: Path,
) -> None:
    runtime = tmp_path / "runtime"
    stage = runtime / "stages/neutral_materials"
    stage.mkdir(parents=True)
    artifact = stage / "neutral_materials.json"
    artifact.write_text(
        json.dumps({"fanout": {"facts": []}}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (stage / "current.json").write_text(
        json.dumps(
            {
                "status": "quality_accepted",
                "input_fingerprint": "INPUT",
                "producer_contract_fingerprint": "CONTRACT",
                "artifacts": {
                    "neutral_materials": {
                        "file": artifact.name,
                        "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                    }
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    assert emperor_rebuild_module._load_accepted_ruler_neutral(runtime) == {
        "fanout": {"facts": []}
    }
    artifact.write_text('{"fanout":{"facts":[{}]}}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="产物校验失败"):
        emperor_rebuild_module._load_accepted_ruler_neutral(runtime)


def test_emperor_rebuild_does_not_require_preextracted_governance_works_in_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    shutil.copytree(ROOT / "config", workspace / "config")
    shutil.copytree(
        ROOT / "eval/i5b_current_value/李世民",
        workspace / "eval/i5b_current_value/李世民",
    )
    observed = {}

    def resolve(**kwargs):
        observed["required_works"] = kwargs["required_works"]
        raise RuntimeError("stop after index contract")

    monkeypatch.setattr(emperor_rebuild_module, "_resolve_source_index", resolve)
    with pytest.raises(RuntimeError, match="index contract"):
        emperor_rebuild_module.rebuild_emperor(
            workspace_root=workspace,
            ruler="李世民",
            source_index_path=None,
            source_index_root=tmp_path / "indexes",
            dynasty_governance_root=tmp_path / "governance",
            runtime_root=tmp_path / "runtime",
        )

    assert observed["required_works"] == ["資治通鑑", "舊唐書", "新唐書"]


def test_structured_runner_requires_same_size_baseline_for_adaptive_timeout() -> None:
    runner = StructuredCodexRunner(
        codex_bin="codex",
        model="test-model",
        reasoning_effort="low",
        output_schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
        timeout_seconds=120,
        cwd=ROOT,
    )
    runner._record_success(prompt_chars=6_000, elapsed_seconds=40)
    runner._record_success(prompt_chars=5_000, elapsed_seconds=50)
    runner._record_success(prompt_chars=5_500, elapsed_seconds=45)

    assert runner._adaptive_timeout_seconds(5_500) == 90
    assert runner._adaptive_timeout_seconds(500) == 120


def test_structured_runner_keeps_hard_timeout_ratio_floor() -> None:
    runner = StructuredCodexRunner(
        codex_bin="codex",
        model="test-model",
        reasoning_effort="low",
        output_schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
        timeout_seconds=120,
        cwd=ROOT,
    )
    for elapsed_seconds in (13, 14, 15):
        runner._record_success(prompt_chars=5_500, elapsed_seconds=elapsed_seconds)

    assert runner._adaptive_timeout_seconds(5_500) == 90


def test_structured_runner_stops_slow_peer_after_twice_normal_duration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "schema_version": "current-outcome-candidate-output-v3",
        "task_code": "TEST",
        "candidates": [],
        "rejections": [],
    }

    class TimedProcess:
        pid = 12345

        def __init__(self, output: Path) -> None:
            self.output = output
            self.returncode = None
            self.stdin = io.StringIO()
            self.stdout = io.StringIO()
            self.stderr = io.StringIO()
            self.started: float | None = None
            self.duration = 0.0
            self.label = ""

        def communicate(
            self, *, input: str | None = None, timeout: float = 0
        ) -> tuple[str, str]:
            if input is not None and self.started is None:
                self.label = input
                self.duration = 0.1 if "BATCH-AUTO-AAAA" in input else 2.0
                self.started = time.monotonic()
            if self.returncode is not None:
                return "", ""
            assert self.started is not None
            remaining = self.duration - (time.monotonic() - self.started)
            if remaining <= timeout:
                time.sleep(max(0.0, remaining))
                self.output.write_text(json.dumps(payload), encoding="utf-8")
                self.returncode = 0
                return "", ""
            time.sleep(timeout)
            raise subprocess.TimeoutExpired("codex", timeout)

        def poll(self):
            return self.returncode

        def kill(self) -> None:
            self.returncode = -9

    processes: list[TimedProcess] = []

    def popen(command, **_kwargs):
        output = Path(command[command.index("--output-last-message") + 1])
        process = TimedProcess(output)
        processes.append(process)
        return process

    terminated: list[str] = []
    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(
        "emperor_v4.runtime.structured_codex_runner._terminate_process_tree",
        lambda process: (terminated.append(process.label), process.kill()),
    )
    monkeypatch.setattr(
        "emperor_v4.runtime.structured_codex_runner.MIN_ADAPTIVE_TIMEOUT_SECONDS",
        0.5,
    )
    monkeypatch.setattr(
        "emperor_v4.runtime.structured_codex_runner.MIN_ADAPTIVE_TIMEOUT_RATIO",
        0.0,
    )
    runner = StructuredCodexRunner(
        codex_bin="codex",
        model="test-model",
        reasoning_effort="low",
        output_schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
        timeout_seconds=10,
        cwd=ROOT,
    )
    for _ in range(3):
        runner._record_success(prompt_chars=len("BATCH-AUTO-BBBB"), elapsed_seconds=0.1)

    started = time.monotonic()
    errors = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(runner.run, prompt)
            for prompt in ("BATCH-AUTO-AAAA", "BATCH-AUTO-BBBB")
        ]
        for future in as_completed(futures):
            try:
                future.result()
            except ModelBatchAnomalyError as exc:
                errors.append(exc)

    assert time.monotonic() - started < 1.2
    assert len(errors) == 1
    assert terminated == ["BATCH-AUTO-BBBB"]
    assert "prompt_sha256=" in str(errors[0])
    assert "comparable_calls=4" in str(errors[0])
    assert "BATCH-AUTO-BBBB" in str(errors[0])


@pytest.mark.parametrize("ruler", ["李世民", "刘邦"])
def test_current_value_chain_is_complete_shadow_with_frozen_profiles(ruler: str) -> None:
    report = build_i5b_current_value(ROOT / "eval/i5b_current_value" / ruler / "source-pack.json")

    assert report["status"] == "current_shadow_chain_complete"
    assert report["declarations"]["three_channel_materials_consumed"] is True
    assert report["declarations"]["linked_ruler_context_count"] > 0
    assert set(report["three_channel_input"]["channel_counts"]) == {
        "ruler_chronicle",
        "person_biography",
        "dynasty_governance",
    }
    assert report["declarations"]["episode_count"] > 0
    assert report["declarations"]["rule_evidence_unit_count"] > 0
    assert set(report["three_channel_disposition"]) == set(report["three_channel_input"]["channel_counts"])
    assert any(row["rule_code"] == "team_building" for row in report["rule_evidence_units"])
    assert report["declarations"]["database_write_count"] == 0
    assert report["declarations"]["formal_score_write_count"] == 0
    assert report["declarations"]["profile_material_coverage_complete"] is True
    assert report["declarations"]["profile_values_frozen"] is True
    assert report["declarations"]["profile_freeze_gate_passed"] is True
    assert report["declarations"]["formal_scoring_ready"] is False
    assert report["declarations"]["profile_member_with_open_gap_count"] == 0
    assert report["declarations"]["person_profile_registry_count"] == 41
    assert report["declarations"]["person_profile_registry_with_open_gap_count"] == 17
    assert report["declarations"]["historical_outcome_cluster_count"] > 0
    assert report["declarations"]["campaign_outcome_count"] > 0
    assert report["declarations"]["governance_outcome_count"] > 0
    assert report["declarations"]["statecraft_outcome_count"] == {
        "李世民": 1,
        "刘邦": 5,
    }[ruler]
    assert report["net_signal_status"] == "stable_profile_inputs"
    assert all(
        row["value_status"] == "frozen_after_complete_coverage"
        for row in report["profile_projection_review"]
    )
    assert "person_profile_registry" not in report
    assert (
        report["person_profile_registry_ref"]
        == "eval/historical_person_profiles/current.json"
    )
    shared_registry = json.loads(
        (ROOT / report["person_profile_registry_ref"]).read_text(encoding="utf-8")
    )
    profile_registry = {
        row["person"]: row for row in shared_registry["profiles"]
    }
    assert {"侯君集", "高士廉", "房玄龄", "韩信"} <= set(profile_registry)
    assert all(
        "team_building_projection" not in row and "political_risk" not in row
        for row in profile_registry.values()
    )
    if ruler == "李世民":
        assert profile_registry["房玄龄"]["domain_grades"]["civil_governance"]["grade"] == "top"
        assert profile_registry["房玄龄"]["domain_grades"]["culture_and_scholarship"]["grade"] == "top"
        assert profile_registry["魏徵"]["primary_domains"] == ["culture_and_scholarship"]
    else:
        assert profile_registry["张良"]["domain_grades"]["statecraft"]["grade"] == "historic"
        assert profile_registry["刘敬"]["overall_grade"] == "ordinary"
        assert profile_registry["樊哙"]["overall_grade"] == "ordinary"
    assert sum(
        bool(row["coverage_gaps"]) for row in report["profile_projection_review"]
    ) == 0
    assert report["declarations"]["score_45"] is None
    assert report["declarations"]["ranking"] is None
    assert report["net_signal"] == report["material_budget"]["summary"]["weighted_raw_signal"]
    assert {episode["episode_type"] for episode in report["episodes"]} >= {
        "ruler_person_governance_event", "campaign_outcome_chain", "governance_outcome_chain"
    }
    linked_episodes = [
        episode for episode in report["episodes"]
        if episode["lineage"].get("ruler_context_refs")
    ]
    assert linked_episodes
    assert all(
        any(link["relation"] == "corroborates" for link in episode["assertion_links"])
        for episode in linked_episodes
    )
    episode_member_refs = [
        member["member_ref"]
        for reu in report["rule_evidence_units"]
        for member in reu["members"]
        if member["member_type"] == "episode"
    ]
    assert len(episode_member_refs) > len(set(episode_member_refs))


def test_person_profiles_are_shared_before_ruler_window_projection() -> None:
    li_shimin = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    )
    li_yuan = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/李渊/source-pack.json"
    )

    assert (
        li_shimin["person_profile_registry_fingerprint"]
        == li_yuan["person_profile_registry_fingerprint"]
    )
    assert "person_profile_registry" not in li_shimin
    assert "person_profile_registry" not in li_yuan
    assert (
        li_shimin["person_profile_registry_ref"]
        == li_yuan["person_profile_registry_ref"]
        == "eval/historical_person_profiles/current.json"
    )
    shared_registry = json.loads(
        (ROOT / li_shimin["person_profile_registry_ref"]).read_text(
            encoding="utf-8"
        )
    )
    profiles = {
        row["person"]: row for row in shared_registry["profiles"]
    }
    assert profiles["侯君集"]["overall_grade"] == "top"
    assert profiles["高士廉"]["overall_grade"] == "important"
    assert all(
        not any(
            key in episode
            for key in ("semantic_version", "evidence_version", "previous_status")
        )
        for episode in li_shimin["episodes"]
    )


def test_current_li_shimin_corrections_follow_rule_documents() -> None:
    pack = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    members = {row["person"]: row for row in pack["members"]}
    assert "long_term_stability" not in pack["team"]
    report = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    )
    team = next(
        row for row in report["material_budget"]["rules"]
        if row["rule_code"] == "team_building"
    )
    assert team["long_term_stability"] == "durable_multi_stage"
    assert team["functional_complementarity"] == "balanced_four"
    assert pack["team"]["positive_members"] == [
        "房玄龄",
        "李勣",
        "李靖",
        "长孙无忌",
        "魏徵",
        "戴胄",
        "杜如晦",
    ]
    assert pack["team"]["attribution_exclusions"] == [
        {
            "person": "苏定方",
            "person_ref": "PER-V4-CB67FCF2FC79",
            "reason": (
                "当前固定证据只证明苏定方以匡道府折冲随李靖参加平东突厥，"
                "未证明李世民亲自识别、任用或授予其独立责任；"
                "其高宗朝主帅成果只进入共享人物画像，不递归计入李世民团队。"
            ),
        }
    ]
    assert len(pack["team"]["stability_stages"]) == 3
    assert members["尉迟敬德"]["negative_talent_severity"] == "material"
    assert members["高士廉"]["negative_talent_severity"] == "material"
    assert members["尉迟敬德"]["profile_review"]["political_risk"]["evidence_refs"] == [
        "PFACT-LSM-YUCHI-COURT-ASSAULT"
    ]
    assert members["高士廉"]["profile_review"]["political_risk"]["evidence_refs"] == [
        "PFACT-LSM-GAOSHI-LIMITED-POWER-ABUSE"
    ]
    assert members["侯君集"]["profile_review"]["political_risk"]["evidence_refs"] == [
        "PFACT-LSM-HOUJUNJI-LOOTING-AND-CONSPIRACY"
    ]
    assert members["侯君集"]["effective_talent_grade"] == "top"
    tuyuhun = next(
        row
        for row in pack["outcome_registry"]["clusters"]
        if row["outcome_ref"] == "OUTCOME-LSM-CAMPAIGN-TUYUHUN"
    )
    tuyuhun_members = {row["actor_name"]: row for row in tuyuhun["members"]}
    assert tuyuhun_members["李靖"]["role_code"] == "commander_in_chief"
    assert tuyuhun_members["侯君集"]["role_code"] == "principal_commander"
    assert not any(
        member["role_code"] == "deputy_commander"
        for outcome in pack["outcome_registry"]["clusters"]
        if outcome["outcome_kind"] == "campaign"
        for member in outcome["members"]
    )
    materials = {row["material_id"]: row for row in pack["materials"]}
    assert materials[
        "MAT-李世民-TT-ZHANGLIANG-WRONGFUL-EXECUTION-REVIEW-1"
    ]["factor_option_codes"]["target_fault_factor"] == "disputed_suspicion"
    assert materials["MAT-李世民-TT-WEIZHENG-CAREER-SUPPLEMENT-1"][
        "factor_option_codes"
    ]["expression_safety"] == "actively_protected_or_encouraged"
    institution = materials[
        "MAT-李世民-TT-ZHENGUAN-FORMAL-REMONSTRANCE-CHANNEL"
    ]
    assert institution["factor_option_codes"]["feedback_entry"] == (
        "institutionalized_feedback_entry"
    )
    assert len(institution["ruler_context_refs"]) >= 3
    assert all(
        row.get("public_power_effect") is True
        for row in pack["materials"]
        if row["rule_code"] == "anti_nepotism"
    )
    assert "MAT-李世民-AN-WEIZHENG-POSTHUMOUS-MARRIAGE" not in materials
    assert not any(
        row["rule_code"] == "appointment_delegation"
        and row["direction"] == "positive"
        for row in pack["materials"]
    )


def test_profile_and_outcome_changes_rebuild_downstream_materials(
    tmp_path: Path,
) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    hou_junji = next(
        row
        for row in payload["materials"]
        if row["material_id"] == "MAT-李世民-TD-HOU-EARLY-ENTRY"
    )
    hou_junji["factor_option_codes"]["talent_quality_factor"] = "ordinary"
    hou_junji["factor_values"]["talent_quality_factor"] = 0.6
    law = next(
        row
        for row in payload["outcome_registry"]["clusters"]
        if row["canonical_label"] == "贞观律令与刑罚体系修订"
    )
    law["payload"]["durable_cross_stage"] = False
    law["semantic_fingerprint"] = cluster_semantic_fingerprint(law)
    payload.pop("source_pack_sha256")
    payload["source_pack_sha256"] = hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    target = tmp_path / "source-pack.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    source_packs = [
        payload,
        json.loads(
            (ROOT / "eval/i5b_current_value/刘邦/source-pack.json").read_text(
                encoding="utf-8"
            )
        ),
    ]
    registry = build_unbound_historical_outcome_registry(source_packs)
    binding = build_ruler_outcome_bindings(payload, registry)
    report = build_i5b_current_value(
        target,
        outcome_layers=(registry, binding),
    )
    discovery = next(
        row
        for row in report["material_budget"]["rules"]
        if row["rule_code"] == "talent_discovery"
    )
    hou_junji_result = next(
        row for row in discovery["settled_materials"] if row["subject"] == "侯君集"
    )
    assert hou_junji_result["factor_option_codes"]["talent_quality_factor"] == "top"
    assert hou_junji_result["factor_values"]["talent_quality_factor"] == "1.450000"
    appointment = next(
        row
        for row in report["material_budget"]["rules"]
        if row["rule_code"] == "appointment_delegation"
    )
    law_rows = [
        row
        for row in appointment["settled_materials"]
        + appointment["supporting_only_materials"]
        if "贞观律令与刑罚体系修订" in row.get("fact", "")
    ]
    assert law_rows
    assert all(
        row["factor_option_codes"]["continuity_factor"] == "stable"
        for row in law_rows
    )


def test_anti_nepotism_requires_public_power_effect(tmp_path: Path) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    material = next(
        row for row in payload["materials"] if row["rule_code"] == "anti_nepotism"
    )
    material["public_power_effect"] = False
    payload.pop("source_pack_sha256")
    payload["source_pack_sha256"] = hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    target = tmp_path / "source-pack.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    registry = build_unbound_historical_outcome_registry([payload])
    binding = build_ruler_outcome_bindings(payload, registry)
    with pytest.raises(ValueError, match="公共权力作用 Gate"):
        build_i5b_current_value(target, outcome_layers=(registry, binding))


def test_shared_outcome_reuse_preserves_first_pack_lineage_order() -> None:
    first = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    second = json.loads(json.dumps(first, ensure_ascii=False))
    target = next(
        row
        for row in second["outcome_registry"]["clusters"]
        if len(row.get("source_refs") or ()) > 1
    )
    target["source_refs"] = list(reversed(target["source_refs"]))
    second["source_pack_sha256"] = "shared-reuse-test-pack"

    registry = build_unbound_historical_outcome_registry([first, second])
    binding = build_ruler_outcome_bindings(first, registry)
    materialized = materialize_ruler_outcome_registry(registry, binding)

    assert public_registry_matches_source_pack(
        materialized,
        first["outcome_registry"],
        ruler_ref=str(first["ruler_ref"]),
    )
    materialized_target = next(
        row
        for row in materialized["clusters"]
        if row["independent_key"] == target["independent_key"]
    )
    first_target = next(
        row
        for row in first["outcome_registry"]["clusters"]
        if row["independent_key"] == target["independent_key"]
    )
    assert materialized_target["source_refs"] == first_target["source_refs"]


def test_shared_outcome_reuse_merges_cross_source_evidence_and_members() -> None:
    first = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    cluster = next(
        row
        for row in first["outcome_registry"]["clusters"]
        if row["outcome_kind"] == "governance" and row["members"]
    )
    first["outcome_registry"]["clusters"] = [cluster]
    second = json.loads(json.dumps(first, ensure_ascii=False))
    second_cluster = second["outcome_registry"]["clusters"][0]
    second_cluster["fact_refs"] = ["FACT-SECOND-SOURCE"]
    second_cluster["source_refs"] = ["SOURCE-SECOND"]
    second_cluster["evidence_lineage"] = [
        {
            "fact_ref": "FACT-SECOND-SOURCE",
            "evidence_roles": ["responsibility_or_attribution"],
        }
    ]
    second_judgment = second_cluster["payload"]["value_judgment"]
    second_judgment["basis"] = "另一固定史源对同一公共效果的表述。"
    for axis in second_judgment["axes"].values():
        if axis["basis_fact_refs"]:
            axis["basis"] = "另一固定史源对同一轴向效果的表述。"
            axis["basis_fact_refs"] = ["FACT-SECOND-SOURCE"]
    second_cluster["members"].append(
        {
            "actor_ref": "RULER-SECOND",
            "actor_name": "后续皇帝",
            "actor_kind": "ruler",
            "role_code": "authorized",
            "contribution_scope": "以另一固定史源证明其完成重要完善。",
            "contribution_types": ["authorization"],
            "contribution_basis_fact_refs": ["FACT-SECOND-SOURCE"],
        }
    )
    second["source_pack_sha256"] = "second-source-pack"

    registry = build_unbound_historical_outcome_registry([first, second])

    assert registry["status"] == "current_shadow_unbound"
    assert registry["declarations"]["outcome_count"] == 1
    outcome = registry["outcomes"][0]
    assert "FACT-SECOND-SOURCE" in outcome["fact_refs"]
    assert "SOURCE-SECOND" in outcome["source_refs"]
    assert any(
        "FACT-SECOND-SOURCE" in axis["basis_fact_refs"]
        for axis in outcome["payload"]["value_judgment"]["axes"].values()
    )
    assert {row["actor_ref"] for row in outcome["members"]} >= {
        cluster["members"][0]["actor_ref"],
        "RULER-SECOND",
    }


def test_shared_governance_responsibility_can_bind_without_copying_outcome() -> None:
    first = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    cluster = next(
        row
        for row in first["outcome_registry"]["clusters"]
        if row["outcome_kind"] == "governance"
    )
    cluster["members"].append(
        {
            "actor_ref": "RULER-SHARED",
            "actor_name": "后续皇帝",
            "actor_kind": "ruler",
            "role_code": "authorized",
            "contribution_scope": "完成重要完善。",
            "contribution_types": ["authorization"],
            "contribution_basis_fact_refs": [cluster["fact_refs"][0]],
        }
    )
    first["outcome_registry"]["clusters"] = [cluster]
    second = {
        "ruler": "后续皇帝",
        "ruler_ref": "RULER-SHARED",
        "source_pack_sha256": "shared-ruler-pack",
        "outcome_registry": {"status": "shadow", "clusters": []},
    }
    registry = build_unbound_historical_outcome_registry([first, second])

    binding = build_ruler_outcome_bindings(second, registry)

    assert binding["binding_count"] == 1
    assert binding["bindings"][0]["ruler_actor_refs"] == ["RULER-SHARED"]
    assert binding["bindings"][0]["ruler_window_status"] == "within_window"


def test_public_registry_normalizes_legacy_governance_value_contract() -> None:
    source = json.loads(
        (ROOT / "eval/i5b_current_value/李渊/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    legacy = next(
        row
        for row in source["outcome_registry"]["clusters"]
        if row["outcome_kind"] == "governance"
        and row["payload"]["value_judgment"]["comparison_basis"]
        == "public_effect_without_explicit_baseline"
    )
    legacy["result_status"] = "mixed"
    legacy["payload"]["value_judgment"]["axes"][
        "civilization_institutions"
    ]["basis"] = "制度改善但方向实际为负面"
    legacy["payload"]["value_judgment"]["axes"][
        "civilization_institutions"
    ]["direction"] = "negative"
    source["outcome_registry"]["clusters"] = [legacy]
    registry = build_unbound_historical_outcome_registry([source])
    outcome = registry["outcomes"][0]

    assert outcome["result_status"] == "operated"
    judgment = outcome["payload"]["value_judgment"]
    assert judgment["comparison_basis"] == "inferred_prior_state"
    assert all(marker in judgment["basis"] for marker in ("基线：", "变化：", "结果："))
    assert "改善" not in judgment["axes"]["civilization_institutions"]["basis"]


def test_current_long_term_stability_is_derived_from_stage_coverage() -> None:
    li = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    )
    liu = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/刘邦/source-pack.json"
    )
    li_team = next(
        row for row in li["material_budget"]["rules"] if row["rule_code"] == "team_building"
    )
    liu_team = next(
        row for row in liu["material_budget"]["rules"] if row["rule_code"] == "team_building"
    )
    assert (li_team["long_term_stability"], li_team["long_term_stability_factor"]) == (
        "durable_multi_stage",
        "1.200000",
    )
    assert (liu_team["long_term_stability"], liu_team["long_term_stability_factor"]) == (
        "durable_multi_stage",
        "1.200000",
    )


def test_appointment_budget_counts_aggregated_objects_not_internal_chains() -> None:
    report = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    )
    appointment = next(
        row
        for row in report["material_budget"]["rules"]
        if row["rule_code"] == "appointment_delegation"
    )

    assert appointment["positive_settled_unit_count"] == 8
    assert appointment["negative_settled_unit_count"] == 1
    assert len(
        [row for row in appointment["settled_materials"] if row["side"] == "positive"]
    ) == 16
    fang = next(row for row in appointment["settled_objects"] if row["subject"] == "房玄龄")
    zhangsun = next(
        row for row in appointment["settled_objects"] if row["subject"] == "长孙无忌"
    )
    assert fang["supporting_chain_count"] == 4
    assert fang["object_aggregate_magnitude"] == "6.165294"
    assert fang["actual_signal_contribution"] == "9.247941"
    assert zhangsun["supporting_chain_count"] == 1
    assert zhangsun["actual_signal_contribution"] == "4.781700"


def test_campaign_appointment_audit_keeps_direct_chains_and_window_boundary() -> None:
    expected = {
        "李世民": {
            "OUTCOME-LSM-CAMPAIGN-GOGURYEO-645": {"李勣", "张亮", "李道宗"},
            "OUTCOME-LSM-CAMPAIGN-GOGURYEO-647": {"李勣", "牛进达"},
            "OUTCOME-LSM-CAMPAIGN-JINGYANG-FRONTLINE": {"尉迟敬德"},
            "OUTCOME-LSM-CAMPAIGN-LIANGSHIDU": {"柴绍", "薛万均"},
            "OUTCOME-LSM-CAMPAIGN-TUYUHUN": {"李道宗"},
        },
        "刘邦": {
            "OUTCOME-QUALITY-00D8D77E3DA87015434B": {"灌婴"},
            "OUTCOME-QUALITY-906584A5507566463BCC": {"灌婴", "周勃"},
            "OUTCOME-QUALITY-AD575D15421EF2621DDA": {"灌婴", "柴武"},
            "OUTCOME-QUALITY-E5BBCD4462D4825DE72F": {"曹参", "周勃"},
            "OUTCOME-QUALITY-LB-HANXIN-WEI": {"曹参", "灌婴"},
        },
    }
    authorizers = {
        "李世民": "RULER-58130F2446A25CC1",
        "刘邦": "RULER-NAME-CANDIDATE-3D3FE911CF34",
    }
    for ruler, expected_outcomes in expected.items():
        source_pack = json.loads(
            (ROOT / "eval/i5b_current_value" / ruler / "source-pack.json").read_text(
                encoding="utf-8"
            )
        )
        clusters = {
            row["outcome_ref"]: row
            for row in source_pack["outcome_registry"]["clusters"]
        }
        for outcome_ref, expected_people in expected_outcomes.items():
            actual_people = {
                member["actor_name"]
                for member in clusters[outcome_ref]["members"]
                if (member.get("delegated_responsibility") or {}).get(
                    "authorizer_ref"
                )
                == authorizers[ruler]
            }
            assert expected_people <= actual_people

    lishimin = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    for outcome_ref in (
        "OUTCOME-LSM-CAMPAIGN-HULAO",
        "OUTCOME-LSM-CAMPAIGN-XUYUANLANG",
    ):
        cluster = next(
            row
            for row in lishimin["outcome_registry"]["clusters"]
            if row["outcome_ref"] == outcome_ref
        )
        assert not any(
            (member.get("delegated_responsibility") or {}).get("authorizer_ref")
            == authorizers["李世民"]
            for member in cluster["members"]
        )


def test_source_pack_hash_fails_closed(tmp_path: Path) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["materials"][0]["fact_summary"] += "篡改"
    target = tmp_path / "source-pack.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="sha256"):
        build_i5b_current_value(target)


def test_duplicate_settlement_event_fails_closed(tmp_path: Path) -> None:
    source = ROOT / "eval/i5b_current_value/刘邦/source-pack.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["materials"][1]["settlement_event_key"] = payload["materials"][0][
        "independence_key"
    ]
    payload["source_pack_sha256"] = hashlib.sha256(
        json.dumps(
            {key: value for key, value in payload.items() if key != "source_pack_sha256"},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    target = tmp_path / "source-pack.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    registry = build_unbound_historical_outcome_registry([payload])
    binding = build_ruler_outcome_bindings(payload, registry)
    with pytest.raises(ValueError, match="重复结算事件"):
        build_i5b_current_value(target, outcome_layers=(registry, binding))


def test_profile_values_cannot_freeze_before_material_coverage(tmp_path: Path) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["profile_projection_gate"]["freeze_allowed"] = True
    payload["profile_projection_gate"]["material_coverage_complete"] = False
    payload["source_pack_sha256"] = hashlib.sha256(
        json.dumps(
            {key: value for key, value in payload.items() if key != "source_pack_sha256"},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    target = tmp_path / "source-pack.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    registry = build_unbound_historical_outcome_registry([payload])
    binding = build_ruler_outcome_bindings(payload, registry)
    with pytest.raises(ValueError, match="材料覆盖未闭合"):
        build_i5b_current_value(target, outcome_layers=(registry, binding))


def test_profile_freeze_review_requires_independent_candidate_roster_closure(
    tmp_path: Path,
) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["profile_projection_gate"] = {
        "status": "ready_for_freeze_review",
        "material_coverage_complete": True,
        "freeze_allowed": False,
        "candidate_roster_review": {
            "status": "complete",
            "coverage_bases": [
                "ruler_window_appointments",
                "outcome_participants",
            ],
            "included_person_refs": ["PER-EXAMPLE"],
        },
    }
    payload["source_pack_sha256"] = hashlib.sha256(
        json.dumps(
            {key: value for key, value in payload.items() if key != "source_pack_sha256"},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    target = tmp_path / "source-pack.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    registry = build_unbound_historical_outcome_registry([payload])
    binding = build_ruler_outcome_bindings(payload, registry)
    with pytest.raises(ValueError, match="潜在高等级全生涯候选"):
        build_i5b_current_value(target, outcome_layers=(registry, binding))


def test_profile_values_rebuild_missing_grade_registry_links(
    tmp_path: Path,
) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["profile_projection_gate"]["freeze_allowed"] = True
    payload["profile_projection_gate"]["material_coverage_complete"] = True
    payload["members"][0]["profile_review"]["talent_grade"]["rule_alignment"]["outcome_refs"] = []
    payload["source_pack_sha256"] = hashlib.sha256(
        json.dumps(
            {key: value for key, value in payload.items() if key != "source_pack_sha256"},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    target = tmp_path / "source-pack.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    registry = build_unbound_historical_outcome_registry([payload])
    binding = build_ruler_outcome_bindings(payload, registry)
    report = build_i5b_current_value(
        target,
        outcome_layers=(registry, binding),
    )
    rebuilt = next(
        row
        for row in report["profile_projection_review"]
        if row["person_ref"] == payload["members"][0]["person_ref"]
    )
    assert rebuilt["talent_grade_rule_alignment"]["rule_path"]
    assert rebuilt["profile_evidence_refs"]["talent_grade"]


def test_high_value_model_rejects_require_main_session_review() -> None:
    source_rows = [
        (
            "SEG-LIU",
            "淵命劉文靜使於突厥以請兵。",
            ["ruler_delegation"],
        ),
        (
            "SEG-PEI",
            "以裴寂為晉州道行軍總管，聽以便宜從事；寂軍遂潰，失亡略盡。",
            ["ruler_delegation", "severe_command_failure"],
        ),
        (
            "SEG-YUANJI",
            "元吉攜其妻妾棄州奔還長安，土豪以城納武周。",
            ["severe_command_failure"],
        ),
        ("SEG-ORDINARY", "群臣皆賀，宴三日。", []),
    ]
    plan = {
        "page_batches": [
            {
                "page_title": "資治通鑒/卷184",
                "revision_ref": "1",
                "segments": [
                    {
                        "segment_ref": segment_ref,
                        "subject_refs": ["RULER-LIYUAN"],
                        "subject_names": ["李淵"],
                        "chronicle_ruler_ref": "RULER-LIYUAN",
                        "text": text,
                    }
                    for segment_ref, text, _ in source_rows
                ]
            }
        ]
    }
    materials = {
        "batch_results": [
            {
                "segment_reviews": [
                    {
                        "segment_ref": segment_ref,
                        "decision": "reject",
                        "reason": "片段未形成直接中性事实。",
                        "facts": [],
                    }
                    for segment_ref, _, _ in source_rows
                ]
            }
        ]
    }

    review = build_high_value_reject_review(plan=plan, materials=materials)

    assert review["status"] == "pending_main_session_review"
    assert review["candidate_count"] == 3
    assert {row["revision_ref"] for row in review["candidates"]} == {"1"}
    assert {
        row["segment_ref"]: row["signal_codes"] for row in review["candidates"]
    } == {
        segment_ref: signals
        for segment_ref, _, signals in source_rows
        if signals
    }


def test_person_statecraft_result_can_feed_appointment_without_becoming_ruler_outcome() -> None:
    cluster = {
        "outcome_kind": "statecraft",
        "settlement_scope": "person_statecraft_result",
        "ruler_window_status": "leadership_formation",
    }

    assert _appointment_window_outcomes([cluster]) == [cluster]
    assert _ruler_window_outcomes([cluster]) == []


def test_appointment_importance_comes_from_responsibility_not_result_scale(
    tmp_path: Path,
) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    law = next(
        row
        for row in payload["outcome_registry"]["clusters"]
        if row["canonical_label"] == "贞观律令与刑罚体系修订"
    )
    for member in law["members"]:
        if member["actor_kind"] == "person" and member["role_code"] == "lead":
            member["delegated_responsibility"]["scope"] = "major_affairs"
    law["semantic_fingerprint"] = cluster_semantic_fingerprint(law)
    payload.pop("source_pack_sha256")
    payload["source_pack_sha256"] = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    target = tmp_path / "source-pack.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    registry = build_unbound_historical_outcome_registry([payload])
    binding = build_ruler_outcome_bindings(payload, registry)
    report = build_i5b_current_value(
        target,
        outcome_layers=(registry, binding),
    )
    appointment = next(
        row for row in report["material_budget"]["rules"]
        if row["rule_code"] == "appointment_delegation"
    )
    rows = [
        row
        for bucket in ("settled_materials", "supporting_only_materials")
        for row in appointment[bucket]
        if "贞观律令与刑罚体系修订" in row.get("fact", "")
    ]
    assert rows
    assert {row["factor_option_codes"]["appointment_importance"] for row in rows} == {"major_affairs"}
    assert {row["factor_option_codes"]["appointment_effect"] for row in rows} == {"exceptional_success"}


def test_governance_support_is_selected_by_current_result_quality() -> None:
    report = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    )
    team_reu = next(
        row for row in report["rule_evidence_units"] if row["rule_code"] == "team_building"
    )
    selected = {
        row["outcome_ref"]
        for row in team_reu["payload"]["governance_dispositions"]
        if row["disposition"] == "selected_team_result_support"
    }
    selected_labels = {
        row["canonical_label"]
        for row in report["historical_outcome_clusters"]
        if row["outcome_ref"] in selected
    }
    assert "精简中枢员额并确立宰相量才授职" in selected_labels
    assert "贡举中以文体轻薄黜落知名候选人" not in selected_labels
    disposition_by_label = {
        next(
            cluster["canonical_label"]
            for cluster in report["historical_outcome_clusters"]
            if cluster["outcome_ref"] == row["outcome_ref"]
        ): row["disposition"]
        for row in report["governance_dispositions"]
    }
    assert disposition_by_label["建立州县义仓并用于赈给"] == (
        "selected_team_result_support"
    )
    assert disposition_by_label["贞观律令与刑罚体系修订"] == (
        "selected_team_result_support"
    )
    assert disposition_by_label["贞观学校与经学建设"] == (
        "supporting_policy_context_not_i5b_team_score"
    )


def test_representative_ruler_policies_render_with_current_disposition() -> None:
    li = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    )
    li_rendered = render_scoring_detail_markdown(li)
    assert "| 功臣世袭刺史 | 正向 |" in li_rendered
    assert "| 皇子出任地方实职 | 正向 |" in li_rendered
    assert "建立州县义仓并用于赈给" in li_rendered
    assert "高宗以后仓粮逐渐被借作他费" in li_rendered
    assert "## 治理成果登记" in li_rendered
    assert "## 战役登记" in li_rendered
    assert "OUTCOME-LSM-CAMPAIGN-EASTERN-TURKS" in li_rendered
    assert "贞观四年平东突厥战役群" in li_rendered
    assert any(
        row["canonical_label"] == "李勣攻克平壤平定高句丽"
        for row in li["historical_outcome_clusters"]
    )
    assert not any(
        row["canonical_label"] == "李勣攻克平壤平定高句丽"
        for row in li["historical_outcome_clusters"]
        if row["outcome_ref"] in set(li["ruler_historical_outcome_refs"])
    )
    appointment = next(
        row
        for row in li["material_budget"]["rules"]
        if row["rule_code"] == "appointment_delegation"
    )
    assert not any(
        "李勣攻克平壤平定高句丽" in row.get("fact", "")
        for bucket in ("settled_materials", "supporting_only_materials")
        for row in appointment[bucket]
    )
    assert not any(
        campaign in row.get("fact", "")
        for campaign in (
            "柏壁—介休平刘武周宋金刚战役群",
            "洛阳—虎牢灭王世充窦建德战役群",
            "洺水击破刘黑闼战役群",
            "浅水原平薛仁杲战役群",
            "曹州—淮泗平徐圆朗战役群",
        )
        for bucket in ("settled_materials", "supporting_only_materials")
        for row in appointment[bucket]
    )
    assert "魏徵家族婚约 | 负向" not in li_rendered
    assert "李靖临刑获救入幕、魏徵跨东宫转化" not in li_rendered

    liu = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/刘邦/source-pack.json"
    )
    policy_contexts = {
        next(
            cluster["canonical_label"]
            for cluster in liu["historical_outcome_clusters"]
            if cluster["outcome_ref"] == row["outcome_ref"]
        )
        for row in liu["governance_dispositions"]
        if row["disposition"] == "supporting_policy_context_not_i5b_team_score"
    }
    assert policy_contexts == {
        "入关约法三章与秦地安堵",
        "叔孙通制定汉朝朝仪",
        "汉初轻田租与官用财政约束",
    }


@pytest.mark.acceptance
@pytest.mark.parametrize("ruler", ["李世民", "刘邦"])
def test_current_detail_exposes_public_outcome_review_fields(ruler: str) -> None:
    report = json.loads(
        (ROOT / "eval/i5b_current_value" / ruler / "result.json").read_text(
            encoding="utf-8"
        )
    )
    rendered = render_scoring_detail_markdown(report)
    assert "| 登记号 | 成果 | 参与角色 | 规模 | 规模依据 |" in rendered
    assert (
            "| 登记号 | 战役群 | 战前背景 | 失败利害 | 战略结果等级 | 作战难度 | 战果 / 目标完成 | "
        "战争成本 | 目标未完成 | 可归责失败 | 统治者控制 | 将领角色 | 土地、对手与结果依据 | "
        "已实现结果 | 史源 |"
        in rendered
    )
    assert "土地=" in rendered
    assert "对手=" in rendered
    assert "结果=" in rendered
    assert "定级=" in rendered


def test_representative_military_materials_keep_three_channel_lineage() -> None:
    li = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    )
    li_contexts = set(li["linked_ruler_context_refs"])
    assert "NMAT-900F470DB8A079C3F11F" in li_contexts
    assert "NMAT-2830CE53C58D4AF38E77" in li_contexts

    liu = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/刘邦/source-pack.json"
    )
    appointment = next(
        row for row in liu["material_budget"]["rules"]
        if row["rule_code"] == "appointment_delegation"
    )
    appointment_rows = [
        row
        for key in ("settled_materials", "supporting_only_materials")
        for row in appointment[key]
    ]
    positive_effects = {"normal_success", "major_success", "exceptional_success"}
    assert all(
        row["material_id"].startswith("MAT-AUTO-AD-")
        for row in appointment_rows
        if row["factor_option_codes"]["appointment_effect"] in positive_effects
    )
    assert any("平定燕王卢绾叛乱战役群" in row["fact"] for row in appointment_rows)
    zhou_bo = next(
        row for row in liu["profile_projection_review"] if row["person"] == "周勃"
    )
    assert zhou_bo["candidate_negative_talent_severity"] == "serious"
    assert set(zhou_bo["profile_evidence_refs"]["political_risk"]) == {
        "PFACT-B16F3241641256A60A24",
        "PFACT-41CE7721509571B8E874",
    }


@pytest.mark.acceptance
def test_current_value_cli_writes_only_current_result(tmp_path: Path) -> None:
    assert eval_main([
        "i5b-current-value",
        "--ruler",
        "刘邦",
        "--workspace-root",
        str(ROOT),
        "--output-dir",
        str(tmp_path),
    ]) == 0
    assert (tmp_path / "result.json").is_file()
    assert (tmp_path / "result.md").is_file()
    report = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    result_markdown = (tmp_path / "result.md").read_text(encoding="utf-8")
    assert result_markdown == render_scoring_detail_markdown(report)
    assert "| 对象 | 方向 | 材料分 | 实际计入信号 | 因子取值 | 计分事实 |" in result_markdown
    assert "## 各臣子 Episode" not in result_markdown


def test_emperor_rebuild_limits_reject_runaway_concurrency() -> None:
    assert RebuildLimits().wall_clock_seconds is None
    with pytest.raises(ValueError, match="史料召回并发"):
        RebuildLimits(source_workers=17)
    with pytest.raises(ValueError, match="导出并发"):
        RebuildLimits(export_workers=9)


def test_emperor_rebuild_resolves_current_index_from_runtime_root(
    tmp_path: Path,
) -> None:
    index_path = tmp_path / "current" / "source.sqlite3"
    built = build_local_source_index(
        [
            {
                "page_title": "甲书/卷1",
                "work_title": "甲书",
                "source_url": "local:1",
                "revision_ref": "1",
                "raw_text": "甲书人物治理事实",
            },
            {
                "page_title": "乙书/卷1",
                "work_title": "乙书",
                "source_url": "local:2",
                "revision_ref": "1",
                "raw_text": "乙书人物战役事实",
            },
        ],
        index_path,
    )
    source_pack = {
        "facts": [
            {"source_page": "甲书/卷1"},
            {"source_page": "乙书/卷1"},
        ]
    }

    resolved = _resolve_source_index(
        source_pack=source_pack,
        source_index_path=None,
        source_index_root=tmp_path,
    )

    assert resolved.identity == built["index_identity"]


def test_governance_index_resolution_prefers_current_identity_until_catalog_expands(
    tmp_path: Path,
) -> None:
    current_path = tmp_path / "current/source.sqlite3"
    current = build_local_source_index(
        [
            {
                "page_title": "政书/卷1",
                "work_title": "政书",
                "source_url": "local:current:1",
                "revision_ref": "1",
                "raw_text": "既有治理事实",
            }
        ],
        current_path,
    )
    expanded_path = tmp_path / "expanded/source.sqlite3"
    expanded = build_local_source_index(
        [
            {
                "page_title": "政书/卷1",
                "work_title": "政书",
                "source_url": "local:current:1",
                "revision_ref": "1",
                "raw_text": "既有治理事实",
            },
            {
                "page_title": "政书/卷2",
                "work_title": "政书",
                "source_url": "local:expanded:2",
                "revision_ref": "2",
                "raw_text": "新增治理事实",
            },
        ],
        expanded_path,
    )

    reused = _resolve_source_index(
        source_pack={"facts": []},
        source_index_path=None,
        source_index_root=tmp_path,
        required_works=("政书",),
        required_page_titles=("政书/卷1",),
        preferred_index_identity=current["index_identity"],
    )
    expanded_for_required_page = _resolve_source_index(
        source_pack={"facts": []},
        source_index_path=None,
        source_index_root=tmp_path,
        required_works=("政书",),
        required_page_titles=("政书/卷1", "政书/卷2"),
        preferred_index_identity=current["index_identity"],
    )

    assert reused.identity == current["index_identity"]
    assert expanded_for_required_page.identity == expanded["index_identity"]


def test_emperor_rebuild_index_resolution_requires_configured_backbone(
    tmp_path: Path,
) -> None:
    partial_path = tmp_path / "partial/source.sqlite3"
    build_local_source_index(
        [
            {
                "page_title": f"甲书/卷{position}",
                "work_title": "甲书",
                "source_url": f"local:partial:{position}",
                "revision_ref": "1",
                "raw_text": "甲书人物治理事实",
            }
            for position in range(3)
        ],
        partial_path,
    )
    complete_path = tmp_path / "complete/source.sqlite3"
    complete = build_local_source_index(
        [
            {
                "page_title": "甲书/卷1",
                "work_title": "甲书",
                "source_url": "local:complete:1",
                "revision_ref": "1",
                "raw_text": "甲书人物治理事实",
            },
            {
                "page_title": "编年书/卷1",
                "work_title": "编年书",
                "source_url": "local:complete:2",
                "revision_ref": "1",
                "raw_text": "编年书人物治理事实",
            },
        ],
        complete_path,
    )

    resolved = _resolve_source_index(
        source_pack={"facts": [{"source_page": "甲书/卷1"}]},
        source_index_path=None,
        source_index_root=tmp_path,
        required_works=("编年书",),
    )

    assert resolved.identity == complete["index_identity"]


def test_emperor_rebuild_index_resolution_ignores_preextracted_governance_work(
    tmp_path: Path,
) -> None:
    index_path = tmp_path / "current/source.sqlite3"
    built = build_local_source_index(
        [
            {
                "page_title": "编年书/卷1",
                "work_title": "编年书",
                "source_url": "local:chronicle",
                "revision_ref": "1",
                "raw_text": "编年人物治理事实",
            }
        ],
        index_path,
    )

    resolved = _resolve_source_index(
        source_pack={"facts": [{"source_page": "政书/卷1"}]},
        source_index_path=None,
        source_index_root=tmp_path,
        required_works=("编年书",),
        preextracted_works=("政书",),
    )

    assert resolved.identity == built["index_identity"]


def test_emperor_rebuild_index_resolution_compares_normalized_work_names(
    tmp_path: Path,
) -> None:
    index_path = tmp_path / "current/source.sqlite3"
    built = build_local_source_index(
        [
            {
                "page_title": "资治通鉴/卷1",
                "work_title": "资治通鉴",
                "source_url": "local:chronicle",
                "revision_ref": "1",
                "raw_text": "编年人物治理事实",
            }
        ],
        index_path,
    )

    resolved = _resolve_source_index(
        source_pack={"facts": []},
        source_index_path=None,
        source_index_root=tmp_path,
        required_works=("資治通鑑",),
    )

    assert resolved.identity == built["index_identity"]


def test_neutral_result_canonicalization_only_binds_owned_facts_and_layout_quotes() -> None:
    batch = {
        "batch_ref": "BATCH-1",
        "page_title": "史书/卷1",
        "revision_ref": "1",
        "segments": [
            {
                "segment_ref": "SEG-1",
                "text": "甲\n乙",
                "subject_refs": ["PER-1"],
            }
        ],
    }
    result = {
        "schema_version": "shared-neutral-extraction-output-v2",
        "batch_ref": "BATCH-1",
        "page_title": "史书/卷1",
        "revision_ref": "1",
        "segment_count": 1,
        "segment_reviews": [
            {
                "segment_ref": "SEG-1",
                "decision": "accept",
                "reason": "raw",
                "facts": [
                    {
                        "fact_id": "F1",
                        "exact_quote": "甲乙",
                        "actors": [
                            {
                                "canonical_name": "人物甲",
                                "subject_ref": None,
                                "role": "executor",
                            }
                        ],
                    },
                    {
                        "fact_id": "F2",
                        "exact_quote": "甲",
                        "actors": [
                            {
                                "canonical_name": "旁人",
                                "subject_ref": "PER-WRONG",
                                "role": "executor",
                            }
                        ],
                    },
                ],
            }
        ],
        "limitations": [],
    }

    repaired = _canonicalize_result(
        batch, result, subject_ref_by_name={"人物甲": "PER-1"}
    )

    facts = repaired["segment_reviews"][0]["facts"]
    assert [row["fact_id"] for row in facts] == ["F1"]
    assert facts[0]["exact_quote"] == "甲\n乙"
    assert facts[0]["actors"][0]["subject_ref"] == "PER-1"


def test_historical_identity_resolver_prevents_lijing_liji_suffix_misbinding() -> None:
    source_pack = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    resolver = HistoricalEntityResolver.load(
        ROOT / "config/historical-entity-identities.yml", source_pack=source_pack
    )
    liji = resolver.entity_for_name("李勣")
    lijing = resolver.entity_for_name("李靖")

    resolved = resolver.resolve(
        "勣", allowed_subject_refs=[liji.person_ref, lijing.person_ref]
    )

    assert resolved.status == "resolved"
    assert resolved.canonical_name == "李勣"
    assert "徐世勣" in resolver.recall_terms("李勣")
    assert "勣" not in resolver.recall_terms("李勣")
    assert resolver.resolve(
        "靖", allowed_subject_refs=[liji.person_ref, lijing.person_ref]
    ).canonical_name == "李靖"
    assert resolver.resolve(
        "静", allowed_subject_refs=[liji.person_ref, lijing.person_ref]
    ).status == "unresolved"

    batch = {
        "segments": [
            {
                "segment_ref": "S1",
                "text": "勣率兵平定其地。",
                "subject_refs": [liji.person_ref, lijing.person_ref],
            }
        ]
    }
    result = {
        "segment_reviews": [
            {
                "segment_ref": "S1",
                "decision": "accept",
                "reason": "raw",
                "facts": [
                    {
                        "exact_quote": "勣率兵平定其地。",
                        "actors": [
                            {
                                "source_name": "勣",
                                "canonical_name": "李靖",
                                "subject_ref": lijing.person_ref,
                                "role": "executor",
                            }
                        ],
                    }
                ],
            }
        ],
        "limitations": [],
    }
    repaired = _canonicalize_result(
        batch,
        result,
        subject_ref_by_name={"李靖": lijing.person_ref, "李勣": liji.person_ref},
        identity_resolver=resolver,
    )
    actor = repaired["segment_reviews"][0]["facts"][0]["actors"][0]
    assert actor["canonical_name"] == "李勣"
    assert actor["subject_ref"] == liji.person_ref


def test_historical_identity_resolver_covers_liyuan_current_team() -> None:
    source_pack = json.loads(
        (ROOT / "eval/i5b_current_value/李渊/source-pack.json").read_text(
            encoding="utf-8"
        )
    )

    resolver = HistoricalEntityResolver.load(
        ROOT / "config/historical-entity-identities.yml", source_pack=source_pack
    )

    liu_wenjing = resolver.entity_for_name("刘文静")
    assert liu_wenjing.person_ref == "PER-ACTOR-9D09781AE311"
    assert "劉文靜" in resolver.recall_terms("刘文静")


def test_ruler_binding_adds_missing_war_terminal_ancestor_as_context() -> None:
    source = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    clusters = source["outcome_registry"]["clusters"]
    terminal = next(
        row for row in clusters if row["settlement_scope"] == "war_terminal_context"
    )
    child = next(
        row
        for row in clusters
        if row.get("parent_outcome_ref") == terminal["outcome_ref"]
        and row["settlement_scope"] == "ruler_campaign_parent"
    )
    terminal_pack = json.loads(json.dumps(source, ensure_ascii=False))
    terminal_pack["source_pack_sha256"] = "TERMINAL-PACK"
    terminal_pack["outcome_registry"]["clusters"] = [terminal]
    child_pack = json.loads(json.dumps(source, ensure_ascii=False))
    child_pack["ruler"] = "测试皇帝"
    child_pack["ruler_ref"] = "RULER-TEST"
    child_pack["source_pack_sha256"] = "CHILD-PACK"
    child_pack["outcome_registry"]["clusters"] = [child]

    registry = build_unbound_historical_outcome_registry(
        [terminal_pack, child_pack]
    )
    binding = build_ruler_outcome_bindings(child_pack, registry)
    context = next(
        row for row in binding["bindings"] if row.get("context_only_ancestor")
    )
    materialized = materialize_ruler_outcome_registry(registry, binding)

    assert binding["binding_count"] == 2
    assert context["outcome_ref"] == terminal["outcome_ref"]
    assert {
        row["settlement_scope"] for row in materialized["clusters"]
    } == {"war_terminal_context", "ruler_campaign_parent"}


def test_neutral_plan_scans_whole_biography_by_event_unit_and_uses_small_context(
    tmp_path: Path,
) -> None:
    source_pack = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    resolver = HistoricalEntityResolver.load(
        ROOT / "config/historical-entity-identities.yml", source_pack=source_pack
    )
    index_path = tmp_path / "source.sqlite3"
    build_local_source_index(
        [
            {
                "page_title": "舊唐書/卷67",
                "work_title": "舊唐書",
                "source_url": "local:67",
                "revision_ref": "1",
                "raw_text": (
                    "==李靖==\n李靖少有文武材略。\n\n"
                    "四年，靖陳十策以圖蕭銑，高祖從之。孝恭未更戎旅，三軍之任一以委靖。\n\n"
                    "六年，靖平輔公祏，江南遂定。"
                ),
            }
        ],
        index_path,
    )
    minimal_pack = {
        "ruler": source_pack["ruler"],
        "ruler_ref": source_pack["ruler_ref"],
        "members": [
            next(row for row in source_pack["members"] if row["person"] == "李靖")
        ],
    }
    plan = build_ruler_neutral_plan(
        source_pack=minimal_pack,
        source_index=LocalSourceTextIndex(index_path),
        inventory={
            "subjects": [{"subject": "李靖", "pages": ["舊唐書/卷67"]}]
        },
        identity_resolver=resolver,
    )

    segments = plan["page_batches"][0]["segments"]
    combined = "".join(row["initial_text"] for row in segments)
    assert "靖陳十策以圖蕭銑" in combined
    assert "靖平輔公祏" in combined
    assert all(len(row["initial_text"]) <= 420 for row in segments)


def test_backbone_range_scans_every_unit_and_bounds_ruler_pronouns(
    tmp_path: Path,
) -> None:
    source_pack = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    minimal_pack = {
        "ruler": source_pack["ruler"],
        "ruler_ref": source_pack["ruler_ref"],
        "members": [
            next(row for row in source_pack["members"] if row["person"] == "李靖"),
            next(row for row in source_pack["members"] if row["person"] == "魏徵"),
        ],
    }
    resolver = HistoricalEntityResolver.load(
        ROOT / "config/historical-entity-identities.yml", source_pack=minimal_pack
    )
    index_path = tmp_path / "source.sqlite3"
    build_local_source_index(
        [
            {
                "page_title": "資治通鑑/卷184",
                "work_title": "資治通鑑",
                "source_url": "local:184",
                "revision_ref": "1",
                "raw_text": "=== 高祖神堯大聖光孝皇帝 ===\n\n上徵兵以備軍。\n\n秦王命李靖统兵平定其地。\n\n"
                + "\n\n".join(
                    f"秦王命军士执行事项{index}。" for index in range(11)
                ),
            },
            {
                "page_title": "資治通鑑/卷185",
                "work_title": "資治通鑑",
                "source_url": "local:185",
                "revision_ref": "2",
                "raw_text": "=== 太宗文武大聖大廣孝皇帝 ===\n\n上命诸军进击，高丽兵大溃。",
            },
            {
                "page_title": "資治通鑑/卷186",
                "work_title": "資治通鑑",
                "source_url": "local:186",
                "revision_ref": "3",
                "raw_text": "李靖獨自統兵平定其地。",
            },
            {
                "page_title": "資治通鑑/卷187",
                "work_title": "資治通鑑",
                "source_url": "local:187",
                "revision_ref": "4",
                "raw_text": "=== 高宗天皇大聖大弘孝皇帝 ===\n\n上命诸军进击。",
            },
        ],
        index_path,
    )

    plan = build_ruler_neutral_plan(
        source_pack=minimal_pack,
        source_index=LocalSourceTextIndex(index_path),
        inventory={"subjects": []},
        identity_resolver=resolver,
        allowed_works=["資治通鑑"],
        allowed_page_ranges={"資治通鑑": [184, 187]},
        shared_subjects={
            "李渊": resolver.entity_for_name("李渊").person_ref,
        },
    )

    assert {row["page_title"] for row in plan["page_batches"]} == {
        "資治通鑑/卷184",
        "資治通鑑/卷185",
        "資治通鑑/卷186",
        "資治通鑑/卷187",
    }
    page_184_batches = [
        batch for batch in plan["page_batches"] if batch["page_title"] == "資治通鑑/卷184"
    ]
    assert len(page_184_batches) == 2
    assert max(len(batch["segments"]) for batch in page_184_batches) <= 8
    page_184 = next(
        segment
        for batch in page_184_batches
        for segment in batch["segments"]
        if "李靖" in segment["text"]
    )
    assert set(page_184["subject_names"]) == {"李渊", "李世民", "李靖"}
    assert page_184["chronicle_ruler_active"] is False
    assert page_184["chronicle_ruler_ref"] == resolver.entity_for_name("李渊").person_ref
    assert all(
        "魏徵" not in segment["subject_names"]
        for batch in plan["page_batches"]
        for segment in batch["segments"]
    )
    role_projections = build_chronicle_role_projections(
        plan=plan,
        neutral_materials={
            "fanout": {
                "facts": [
                    {
                        "fact_ref": "FACT-QIN-PRINCE",
                        "segment_ref": page_184["segment_ref"],
                        "actors": [
                            {
                                "subject_ref": source_pack["ruler_ref"],
                                "role": "executor",
                            }
                        ],
                    }
                ]
            }
        },
    )
    assert role_projections == [
        {
            "chronicle_ruler_ref": resolver.entity_for_name("李渊").person_ref,
            "profile_subject_ref": source_pack["ruler_ref"],
            "fact_refs": ["FACT-QIN-PRINCE"],
        }
    ]
    assert next(
        segment["subject_names"]
        for batch in page_184_batches
        for segment in batch["segments"]
        if "李靖" in segment["text"]
    ) == page_184["subject_names"]
    page_185 = next(
        segment
        for batch in plan["page_batches"]
        if batch["page_title"] == "資治通鑑/卷185"
        for segment in batch["segments"]
        if "高丽兵大溃" in segment["text"]
    )
    assert page_185["subject_names"] == ["李世民"]
    assert page_185["chronicle_ruler_active"] is True
    assert page_185["chronicle_ruler_ref"] == source_pack["ruler_ref"]
    page_186 = next(
        segment
        for batch in plan["page_batches"]
        if batch["page_title"] == "資治通鑑/卷186"
        for segment in batch["segments"]
    )
    assert page_186["subject_names"] == ["李世民", "李靖"]
    assert page_186["chronicle_ruler_active"] is True
    page_187 = next(
        segment
        for batch in plan["page_batches"]
        if batch["page_title"] == "資治通鑑/卷187"
        for segment in batch["segments"]
        if "上命诸军" in segment["text"]
    )
    assert page_187["subject_names"] == []
    assert page_187["subject_refs"] == []
    assert page_187["chronicle_ruler_active"] is False
    routed = build_deterministic_fact_resolution_plan(plan)
    assert routed["deterministic_routing"]["unbound_segment_count"] >= 1
    assert all(
        page_187["segment_ref"] != segment["segment_ref"]
        for batch in routed["page_batches"]
        for segment in batch["segments"]
    )
    assert "世民" in resolver.recall_terms("李世民")


def test_independent_backbone_closes_explicit_actors_and_stops_at_ruler_death(
    tmp_path: Path,
) -> None:
    source_pack = json.loads(
        (ROOT / "eval/i5b_current_value/李治/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    resolver = HistoricalEntityResolver.load(
        ROOT / "config/historical-entity-identities.yml", source_pack=source_pack
    )
    index_path = tmp_path / "source.sqlite3"
    build_local_source_index(
        [
            {
                "page_title": "資治通鑑/卷203",
                "work_title": "資治通鑑",
                "source_url": "local:203",
                "revision_ref": "1",
                "raw_text": (
                    "=== 高宗天皇大聖大弘孝皇帝下弘道元年（癸未，公元六八三年）===\n"
                    "以左武衛大將軍程務挺為單于道安撫大使，以備突厥。\n"
                    "上崩於貞觀殿。命劉仁軌專知西京留守事。\n"
                    "=== 高宗天皇大聖大弘孝皇帝下光宅元年（甲申，公元六八四年）===\n"
                    "詔以李孝逸為左玉鈐衛大將軍，討徐敬業。"
                ),
            },
            {
                "page_title": "舊唐書/卷84",
                "work_title": "舊唐書",
                "source_url": "local:84",
                "revision_ref": "2",
                "raw_text": "任雅相奉詔出師，與諸將分道進討，破其眾。",
            },
        ],
        index_path,
    )

    plan = build_ruler_neutral_plan(
        source_pack=source_pack,
        source_index=LocalSourceTextIndex(index_path),
        inventory={"subjects": []},
        identity_resolver=resolver,
        allowed_works=["資治通鑑"],
        allowed_page_ranges={"資治通鑑": [203, 203]},
        ruler_window="649-683",
    )
    segments = [
        segment
        for batch in plan["page_batches"]
        for segment in batch["segments"]
    ]
    appointment = next(segment for segment in segments if "程務挺" in segment["text"])
    assert "李治" in appointment["subject_names"]
    assert "程务挺" in appointment["subject_names"]
    provisional = next(
        row
        for row in plan["provisional_subject_bindings"]
        if row["canonical_name"] == "程务挺"
    )
    assert provisional["identity_status"] == "provisional_actor_name"
    assert provisional["subject_ref"] in appointment["subject_refs"]
    assert all(
        segment.get("chronicle_ruler_ref") != source_pack["ruler_ref"]
        for segment in segments
        if "劉仁軌專知" in segment["text"] or "徐敬業" in segment["text"]
    )

    provisional_name = "任雅相"
    provisional_ref = "PER-ACTOR-TEST-REN"
    event_signatures = [
        {
            "event_ref": "EVENT-REN-YAXIANG",
            "subject_bindings": [
                {
                    "subject_ref": provisional_ref,
                    "canonical_name": provisional_name,
                    "recall_terms": [provisional_name],
                }
            ],
            "chronology_anchors": [],
            "location_anchors": [],
            "action_anchors": ["奉诏出师", "分道进讨"],
            "result_anchors": ["破其众"],
            "quote_anchors": ["奉诏出师", "分道进讨", "破其众"],
            "backbone_quotes": [],
        }
    ]
    directed = build_event_directed_neutral_plan(
        backbone_plan=plan,
        event_signatures=event_signatures,
        source_index=LocalSourceTextIndex(index_path),
        identity_resolver=resolver,
        backsource_works=["舊唐書"],
        supplement_works=[],
    )
    targeted = [
        segment
        for batch in directed["page_batches"]
        for segment in batch["segments"]
        if segment.get("source_role") == "backsource"
    ]
    assert targeted
    assert targeted[0]["subject_refs"] == [provisional_ref]


@pytest.mark.parametrize(
    ("heading_terms", "active_heading"),
    [
        (["洪武"], "洪武元年"),
        (["建隆", "乾德", "開寶"], "乾德元年"),
        (["康熙"], "康熙元年"),
        (["秦始皇帝"], "秦始皇帝"),
    ],
)
def test_chronicle_heading_contract_is_dynasty_agnostic(
    tmp_path: Path,
    heading_terms: list[str],
    active_heading: str,
) -> None:
    source_pack = json.loads(
        (ROOT / "eval/i5b_current_value/李治/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    resolver = HistoricalEntityResolver.load(
        ROOT / "config/historical-entity-identities.yml", source_pack=source_pack
    )
    index_path = tmp_path / "source.sqlite3"
    build_local_source_index(
        [
            {
                "page_title": "编年史/卷1",
                "work_title": "编年史",
                "source_url": "local:1",
                "revision_ref": "1",
                "raw_text": (
                    f"== {active_heading} ==\n上命甲统兵。\n"
                    "== 贊 ==\n后世论其功。"
                ),
            }
        ],
        index_path,
    )

    plan = build_ruler_neutral_plan(
        source_pack=source_pack,
        source_index=LocalSourceTextIndex(index_path),
        inventory={"subjects": []},
        identity_resolver=resolver,
        allowed_works=["编年史"],
        allowed_page_ranges={"编年史": [1, 1]},
        ruler_window="649-683",
        ruler_heading_terms=heading_terms,
    )
    segments = [
        segment
        for batch in plan["page_batches"]
        for segment in batch["segments"]
    ]

    assert next(
        segment for segment in segments if "上命甲统兵" in segment["text"]
    )["chronicle_ruler_ref"] == source_pack["ruler_ref"]
    assert all(
        segment.get("chronicle_ruler_ref") != source_pack["ruler_ref"]
        for segment in segments
        if "后世论其功" in segment["text"]
    )


def test_deterministic_backbone_campaign_discovery_routes_only_ambiguity() -> None:
    source_pack = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    resolver = HistoricalEntityResolver.load(
        ROOT / "config/historical-entity-identities.yml", source_pack=source_pack
    )
    texts = [
        "武德三年，秦王世民引兵追宋金剛，大破之。",
        "太宗先克遼東城，攻安市不克，遂班師。",
        "秦王府置文學館，召學士入直。",
    ]
    segments = []
    offset = 0
    for index, text in enumerate(texts, start=1):
        segments.append(
            {
                "segment_ref": f"SEG-{index}",
                "start_offset": offset,
                "end_offset": offset + len(text),
                "text": text,
                "initial_text": text,
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "subject_refs": [source_pack["ruler_ref"]],
                "subject_names": [source_pack["ruler"]],
                "spans": [
                    {
                        "span_ref": f"SPAN-{offset}-{offset + len(text)}",
                        "start_offset": offset,
                        "end_offset": offset + len(text),
                        "text": text,
                    }
                ],
            }
        )
        offset += len(text) + 1
    plan = {
        "schema_version": "subject-shared-review-plan-v1",
        "ruler": source_pack["ruler"],
        "source_index_identity": "INDEX-1",
        "mention_index_fingerprint": "MENTION-1",
        "page_batches": [
            {
                "batch_ref": "BATCH-1",
                "page_title": "資治通鑑/卷188",
                "work_title": "資治通鑑",
                "source_url": "local:188",
                "revision_ref": "1",
                "segments": segments,
            }
        ],
    }

    discovery = discover_deterministic_backbone_campaigns(
        backbone_plan=plan,
        ruler_name=source_pack["ruler"],
        ruler_ref=source_pack["ruler_ref"],
        identity_resolver=resolver,
    )

    assert discovery["model_call_count"] == 0
    assert discovery["event_count"] == 2
    assert discovery["deterministic_clear_count"] == 1
    assert discovery["needs_judgment_count"] == 1
    assert discovery["events"][0]["result_status"] == "completed"
    assert discovery["events"][1]["result_status"] == "mixed"
    assert discovery["events"][1]["resolution_status"] == "needs_judgment"
    assert all(
        event["neutral_fact"]["exact_quote"] in texts
        for event in discovery["events"]
    )

    seeded = seed_deterministic_campaign_facts(
        plan=plan,
        current=None,
        discovery=discovery,
    )
    assert seeded["seeded_segment_refs"] == ["SEG-1", "SEG-2"]
    assert seeded["seeded_fact_count"] == 2
    assert seeded["outcome_judgment_pending_segment_count"] == 1

    routed = build_deterministic_fact_resolution_plan(plan)
    assert routed["deterministic_routing"]["scanned_segment_count"] == 3
    assert routed["deterministic_routing"]["model_segment_count"] == 3
    no_action_plan = {
        **plan,
        "page_batches": [
            {
                **plan["page_batches"][0],
                "segments": [
                    {
                        **segments[0],
                        "segment_ref": "SEG-NO-ACTION",
                        "text": "秦王世民朝謁之暇，與學士討論文籍。",
                    }
                ],
            }
        ],
    }
    no_action = build_deterministic_fact_resolution_plan(no_action_plan)
    assert no_action["page_batches"] == []
    assert no_action["deterministic_routing"]["deterministic_empty_count"] == 1


def test_deterministic_campaign_does_not_invert_target_or_protected_ruler() -> None:
    source_pack = json.loads(
        (ROOT / "eval/i5b_current_value/刘邦/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    resolver = HistoricalEntityResolver.load(
        ROOT / "config/historical-entity-identities.yml", source_pack=source_pack
    )
    texts = [
        "范增召项庄，使以剑舞，因击沛公于坐，杀之。",
        "项伯拔剑起舞，常以身翼蔽沛公，庄不得击。",
        "汉王引兵从故道出，袭雍，雍兵败走。",
    ]
    segments = []
    offset = 0
    for index, text in enumerate(texts, start=1):
        segments.append(
            {
                "segment_ref": f"SEG-LB-{index}",
                "start_offset": offset,
                "end_offset": offset + len(text),
                "text": text,
                "initial_text": text,
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "subject_refs": [source_pack["ruler_ref"]],
                "subject_names": [source_pack["ruler"]],
                "spans": [
                    {
                        "span_ref": f"SPAN-{offset}-{offset + len(text)}",
                        "start_offset": offset,
                        "end_offset": offset + len(text),
                        "text": text,
                    }
                ],
            }
        )
        offset += len(text) + 1
    plan = {
        "schema_version": "subject-shared-review-plan-v1",
        "ruler": source_pack["ruler"],
        "source_index_identity": "INDEX-LB-ACTOR",
        "mention_index_fingerprint": "MENTION-LB-ACTOR",
        "page_batches": [
            {
                "batch_ref": "BATCH-LB-ACTOR",
                "page_title": "資治通鑑/卷009",
                "work_title": "資治通鑑",
                "source_url": "local:009",
                "revision_ref": "1",
                "segments": segments,
            }
        ],
    }

    discovery = discover_deterministic_backbone_campaigns(
        backbone_plan=plan,
        ruler_name=source_pack["ruler"],
        ruler_ref=source_pack["ruler_ref"],
        identity_resolver=resolver,
    )

    assert discovery["event_count"] == 1
    assert discovery["events"][0]["segment_ref"] == "SEG-LB-3"


def test_deterministic_clear_campaign_seed_skips_generic_model(tmp_path: Path) -> None:
    source_pack = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    resolver = HistoricalEntityResolver.load(
        ROOT / "config/historical-entity-identities.yml", source_pack=source_pack
    )
    text = "武德三年，秦王世民引兵追宋金剛，大破之。"
    plan = {
        "schema_version": "subject-shared-review-plan-v1",
        "ruler": source_pack["ruler"],
        "source_index_identity": "INDEX-SEED",
        "mention_index_fingerprint": "MENTION-SEED",
        "page_batches": [
            {
                "batch_ref": "BATCH-SEED",
                "page_title": "資治通鑑/卷188",
                "work_title": "資治通鑑",
                "source_url": "local:188",
                "revision_ref": "1",
                "segments": [
                    {
                        "segment_ref": "SEG-SEED",
                        "start_offset": 0,
                        "end_offset": len(text),
                        "text": text,
                        "initial_text": text,
                        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                        "subject_refs": [source_pack["ruler_ref"]],
                        "subject_names": [source_pack["ruler"]],
                        "spans": [
                            {
                                "span_ref": f"SPAN-0-{len(text)}",
                                "start_offset": 0,
                                "end_offset": len(text),
                                "text": text,
                            }
                        ],
                    }
                ],
            }
        ],
    }
    discovery = discover_deterministic_backbone_campaigns(
        backbone_plan=plan,
        ruler_name=source_pack["ruler"],
        ruler_ref=source_pack["ruler_ref"],
        identity_resolver=resolver,
    )
    seed = seed_deterministic_campaign_facts(
        plan=plan,
        current=None,
        discovery=discovery,
    )

    materials = extract_current_neutral_materials(
        plan=plan,
        current=seed["current"],
        runner=object(),
        max_workers=1,
        checkpoint_dir=tmp_path / "checkpoint",
        subject_ref_by_name={source_pack["ruler"]: source_pack["ruler_ref"]},
        identity_resolver=resolver,
    )

    assert materials["model_call_count"] == 0
    assert materials["fanout"]["fact_count"] == 1
    assert materials["fanout"]["facts"][0]["exact_quote"] == text

    empty_current = {
        "batch_results": [
            {
                "schema_version": "shared-neutral-extraction-output-v2",
                "batch_ref": "BATCH-SEED",
                "page_title": "資治通鑑/卷188",
                "revision_ref": "1",
                "segment_count": 1,
                "segment_reviews": [
                    {
                        "segment_ref": "SEG-SEED",
                        "decision": "reject",
                        "context_status": "sufficient",
                        "facts": [],
                        "reason": "通用抽取未返回事实。",
                    }
                ],
                "limitations": [],
            }
        ]
    }
    supplemented = extract_current_neutral_materials(
        plan=plan,
        current=empty_current,
        runner=object(),
        max_workers=1,
        checkpoint_dir=tmp_path / "supplemental-checkpoint",
        subject_ref_by_name={source_pack["ruler"]: source_pack["ruler_ref"]},
        identity_resolver=resolver,
        supplemental_facts_by_segment={
            "SEG-SEED": [discovery["events"][0]["neutral_fact"]]
        },
    )
    assert supplemented["model_call_count"] == 0
    assert supplemented["fanout"]["fact_count"] == 1


def test_deterministic_campaign_discovery_uses_only_active_ruler_pronouns() -> None:
    source_pack = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    resolver = HistoricalEntityResolver.load(
        ROOT / "config/historical-entity-identities.yml", source_pack=source_pack
    )
    text = "上命诸军鼓噪并进，高丽兵大溃，斩首二万余级。"
    segment = {
        "segment_ref": "SEG-PRONOUN-CAMPAIGN",
        "start_offset": 0,
        "end_offset": len(text),
        "text": text,
        "initial_text": text,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "subject_refs": [source_pack["ruler_ref"]],
        "subject_names": [source_pack["ruler"]],
        "chronicle_ruler_active": True,
        "spans": [
            {
                "span_ref": f"SPAN-0-{len(text)}",
                "start_offset": 0,
                "end_offset": len(text),
                "text": text,
            }
        ],
    }
    plan = {
        "schema_version": "subject-shared-review-plan-v1",
        "ruler": source_pack["ruler"],
        "source_index_identity": "INDEX-PRONOUN",
        "mention_index_fingerprint": "MENTION-PRONOUN",
        "page_batches": [
            {
                "batch_ref": "BATCH-PRONOUN",
                "page_title": "資治通鑑/卷198",
                "work_title": "資治通鑑",
                "source_url": "local:198",
                "revision_ref": "1",
                "segments": [segment],
            }
        ],
    }

    active = discover_deterministic_backbone_campaigns(
        backbone_plan=plan,
        ruler_name=source_pack["ruler"],
        ruler_ref=source_pack["ruler_ref"],
        identity_resolver=resolver,
    )
    assert active["event_count"] == 1
    assert active["events"][0]["neutral_fact"]["actors"][0]["source_name"] == "上"

    inactive = discover_deterministic_backbone_campaigns(
        backbone_plan={
            **plan,
            "page_batches": [
                {
                    **plan["page_batches"][0],
                    "segments": [{**segment, "chronicle_ruler_active": False}],
                }
            ],
        },
        ruler_name=source_pack["ruler"],
        ruler_ref=source_pack["ruler_ref"],
        identity_resolver=resolver,
    )
    assert inactive["event_count"] == 0


def test_event_directed_plan_uses_backbone_signature_to_target_other_works(
    tmp_path: Path,
) -> None:
    source_pack = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    ruler = source_pack["ruler"]
    member = next(row for row in source_pack["members"] if row["person"] == "李靖")
    minimal_pack = {
        "ruler": ruler,
        "ruler_ref": source_pack["ruler_ref"],
        "members": [member],
    }
    resolver = HistoricalEntityResolver.load(
        ROOT / "config/historical-entity-identities.yml", source_pack=minimal_pack
    )
    index_path = tmp_path / "source.sqlite3"
    build_local_source_index(
        [
            {
                "page_title": "資治通鑑/卷193",
                "work_title": "資治通鑑",
                "source_url": "local:backbone",
                "revision_ref": "1",
                    "raw_text": "貞觀四年，太宗命李靖統兵討伐突厥，平定其地。",
            },
            {
                "page_title": "資治通鑑/卷005",
                "work_title": "資治通鑑",
                "source_url": "local:ancient-qin",
                "revision_ref": "0",
                "raw_text": "秦王用范睢之謀，使五大夫綰伐魏。",
            },
            {
                "page_title": "舊唐書/卷67",
                "work_title": "舊唐書",
                "source_url": "local:old",
                "revision_ref": "2",
                "raw_text": "==李靖==\n貞觀四年，李靖統兵討伐突厥，平定其地。\n\n李靖少有文武材略。",
            },
            {
                "page_title": "新唐書/卷93",
                "work_title": "新唐書",
                "source_url": "local:new",
                "revision_ref": "3",
                "raw_text": "李靖討伐突厥，平定其地，遂班師。",
            },
            {
                "page_title": "貞觀政要/卷01",
                "work_title": "貞觀政要",
                "source_url": "local:supplement",
                "revision_ref": "4",
                "raw_text": "太宗命李靖討伐突厥，既而平定其地。",
            },
        ],
        index_path,
    )
    index = LocalSourceTextIndex(index_path)
    assert [
        page.page_title
        for page in index.iter_pages(
            works=["舊唐書"], page_titles=["舊唐書/卷67"]
        )
    ] == ["舊唐書/卷67"]
    assert list(index.iter_pages(works=["舊唐書"], page_titles=[])) == []
    assert {
        page.page_title
        for page in index.iter_pages_matching_terms(
            works=["舊唐書", "新唐書"], terms=["李靖"]
        )
    } == {"舊唐書/卷67", "新唐書/卷93"}
    backbone_plan = build_ruler_neutral_plan(
        source_pack=minimal_pack,
        source_index=index,
        inventory={
            "subjects": [
                {
                    "subject": ruler,
                    "pages": ["資治通鑑/卷005", "資治通鑑/卷193"],
                },
                {"subject": "李靖", "pages": ["資治通鑑/卷193"]},
            ]
        },
        identity_resolver=resolver,
        allowed_works=["資治通鑑"],
        allowed_page_ranges={"資治通鑑": [184, 199]},
    )
    assert {row["page_title"] for row in backbone_plan["page_batches"]} == {
        "資治通鑑/卷193"
    }
    segment = backbone_plan["page_batches"][0]["segments"][0]
    fact = {
        "fact_ref": "NEUTRALFACT-1",
        "segment_ref": segment["segment_ref"],
        "segment_text_sha256": segment["text_sha256"],
        "page_title": "資治通鑑/卷193",
        "work_title": "資治通鑑",
        "revision_ref": "1",
        "exact_quote": "貞觀四年，太宗命李靖統兵討伐突厥，平定其地。",
        "action_summary": "李靖统兵讨伐突厥。",
        "result": "平定其地。",
        "actors": [
            {
                "canonical_name": "李靖",
                "subject_ref": member["person_ref"],
                "role": "executor",
            }
        ],
    }
    backbone_materials = {"fanout": {"facts": [fact]}}

    signatures = build_backbone_event_signatures(
        backbone_plan=backbone_plan,
        backbone_materials=backbone_materials,
        identity_resolver=resolver,
    )
    assert len(signatures) == 1
    assert signatures[0]["chronology_anchors"] == ["贞观四年"]
    assert signatures[0]["subject_bindings"][0]["canonical_name"] == "李靖"
    assert signatures[0]["backbone_quotes"][0]["revision_ref"] == "1"

    pre_model_signatures = build_deterministic_backbone_event_signatures(
        backbone_plan=backbone_plan,
        identity_resolver=resolver,
    )
    assert len(pre_model_signatures) == 1
    assert pre_model_signatures[0]["resolution_status"] == "needs_fact_resolution"
    assert {
        row["canonical_name"]
        for row in pre_model_signatures[0]["subject_bindings"]
    } == {"李世民", "李靖"}
    assert pre_model_signatures[0]["backbone_quotes"][0]["exact_quote"] == segment["text"]

    pre_model_directed = build_event_directed_neutral_plan(
        backbone_plan=backbone_plan,
        event_signatures=pre_model_signatures,
        source_index=index,
        identity_resolver=resolver,
        backsource_works=["舊唐書", "新唐書"],
        supplement_works=["貞觀政要"],
    )
    assert {
        batch["work_title"] for batch in pre_model_directed["page_batches"]
    } == {"資治通鑑", "舊唐書", "新唐書", "貞觀政要"}

    directed = build_event_directed_neutral_plan(
        backbone_plan=backbone_plan,
        backbone_materials=backbone_materials,
        source_index=index,
        identity_resolver=resolver,
        backsource_works=["舊唐書", "新唐書"],
        supplement_works=["貞觀政要"],
    )
    targeted = [
        segment
        for batch in directed["page_batches"]
        for segment in batch["segments"]
        if segment.get("source_role")
    ]
    assert {row["source_role"] for row in targeted} == {"backsource", "supplement"}
    assert {batch["work_title"] for batch in directed["page_batches"]} == {
        "資治通鑑",
        "舊唐書",
        "新唐書",
        "貞觀政要",
    }
    assert all("李靖" in row["initial_text"] for row in targeted)
    assert len(directed["target_segment_event_bindings"]) == len(targeted) + 1


def test_dynasty_governance_current_is_filtered_and_merged_without_model() -> None:
    source_pack = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    resolver = HistoricalEntityResolver.load(
        ROOT / "config/historical-entity-identities.yml", source_pack=source_pack
    )
    subject_ref_by_name = {
        str(source_pack["ruler"]): str(source_pack["ruler_ref"]),
        **{
            str(row["person"]): str(row["person_ref"])
            for row in source_pack.get("members") or ()
        },
    }
    neutral = {
        "schema_version": "current-neutral-materials-v1",
        "fanout": {
            "facts": [],
            "person_fanout": [],
            "event_groups": [],
            "fact_count": 0,
            "person_count": 0,
        },
    }
    current = {
        "schema_version": "dynasty-governance-current-v2",
        "status": "quality_accepted_shadow",
        "dynasty": "唐",
        "dynasty_token": "TANG",
        "input_fingerprint": "DYNASTY-CURRENT-1",
        "source_index_identity": "INDEX-1",
        "chains": [
            {
                "chain_key": "zhenguan-law",
                "title": "贞观修律",
                "domain": "law_and_adjudication",
                "period": "贞观年间",
                "action": "太宗授权修订法律。",
                "implementation": "法律完成修订。",
                "observable_result": "新律颁行。",
                "operation_status": "implemented",
                "temporal_scope": "long_term_pattern",
                "effect_domains": ["civilization_institutions"],
                "actors": [
                    {
                        "name": "太宗",
                        "responsibility_role": "lead",
                        "contribution_phases": ["authorized"],
                        "role_basis": "原文记载太宗授权。",
                        "quote_refs": ["Q-1"],
                    }
                ],
                "evidence": [
                    {
                        "quote_ref": "Q-1",
                        "page_title": "貞觀政要/卷08",
                        "revision_ref": "1",
                        "exact_quote": "太宗授权群臣修订法律条文。",
                        "evidence_roles": [
                            "implementation_or_operation",
                            "responsibility_or_attribution",
                        ],
                    },
                    {
                        "quote_ref": "Q-1R",
                        "page_title": "貞觀政要/卷08-result",
                        "revision_ref": "1",
                        "exact_quote": "新律颁行天下。",
                        "evidence_roles": ["public_result"],
                    },
                ],
                "uncertainty": "",
            },
            {
                **{
                    "chain_key": "gaozong-law",
                    "title": "高宗修律",
                    "domain": "law_and_adjudication",
                    "period": "永徽年间",
                    "action": "长孙无忌主持修订法律。",
                    "implementation": "完成修订。",
                    "observable_result": "新律颁行。",
                    "operation_status": "implemented",
                    "temporal_scope": "long_term_pattern",
                    "actors": [
                        {
                            "name": "长孙无忌",
                            "responsibility_role": "lead",
                            "contribution_phases": ["implemented"],
                            "role_basis": "原文记载长孙无忌主持修律。",
                            "quote_refs": ["Q-2"],
                        }
                    ],
                    "evidence": [
                        {
                            "quote_ref": "Q-2",
                            "page_title": "舊唐書/卷50",
                            "revision_ref": "1",
                            "exact_quote": "长孙无忌主持修律并颁行天下。",
                        }
                    ],
                    "uncertainty": "",
                }
            },
            {
                "chain_key": "zhenguan-public-order",
                "title": "贞观社会秩序改善",
                "domain": "livelihood_social_order",
                "period": "贞观年间",
                "action": "原文未载单一举措。",
                "implementation": "原文未载单一实施链。",
                "observable_result": "商旅野次，无复盗贼。",
                "operation_status": "observed_outcome",
                "temporal_scope": "repeated_pattern",
                "effect_domains": [
                    "productivity_livelihood",
                    "state_people_security",
                ],
                "actors": [],
                "evidence": [
                    {
                        "quote_ref": "Q-3",
                        "page_title": "貞觀政要/卷01",
                        "revision_ref": "1",
                        "exact_quote": "商旅野次，无复盗贼。",
                        "evidence_roles": ["public_result"],
                    }
                ],
                "uncertainty": "本条未载单一人物责任。",
            },
            {
                "chain_key": "zhenguan-office-name",
                "title": "贞观官署名称",
                "domain": "central_government",
                "period": "贞观年间",
                "action": "调整官署名称。",
                "implementation": "诏令已经发布。",
                "observable_result": "官署形成新名称。",
                "operation_status": "enacted",
                "temporal_scope": "single_event",
                "effect_domains": ["civilization_institutions"],
                "actors": [],
                "evidence": [
                    {
                        "quote_ref": "Q-4",
                        "page_title": "唐六典/卷01",
                        "revision_ref": "1",
                        "exact_quote": "贞观年间改官署之名。",
                        "evidence_roles": ["measure_or_design"],
                    }
                ],
                "uncertainty": "",
            },
            {
                "chain_key": "zhenguan-public-burden",
                "title": "贞观公共负担",
                "domain": "livelihood_social_order",
                "period": "贞观年间",
                "action": "征发民力。",
                "implementation": "征发已经执行。",
                "observable_result": "原文未载进一步结果。",
                "cost_or_burden": "百姓承担额外徭役。",
                "operation_status": "implemented",
                "temporal_scope": "single_event",
                "effect_domains": ["productivity_livelihood"],
                "actors": [],
                "evidence": [
                    {
                        "quote_ref": "Q-5",
                        "page_title": "唐會要/卷01",
                        "revision_ref": "1",
                        "exact_quote": "发民治役，百姓劳苦。",
                        "evidence_roles": ["cost_or_burden"],
                    }
                ],
                "uncertainty": "",
            },
            {
                "chain_key": "gaozong-public-famine",
                "title": "高宗京师饥荒",
                "domain": "livelihood_social_order",
                "period": "永淳元年",
                "action": "原文未载单一举措。",
                "implementation": "原文未载单一实施链。",
                "observable_result": "京师人相食。",
                "operation_status": "observed_outcome",
                "temporal_scope": "single_event",
                "effect_domains": [
                    "productivity_livelihood",
                    "state_people_security",
                ],
                "actors": [],
                "evidence": [
                    {
                        "quote_ref": "Q-6",
                        "page_title": "舊唐書/卷5",
                        "revision_ref": "1",
                        "exact_quote": "京师人相食。",
                        "evidence_roles": ["public_result", "cost_or_burden"],
                    }
                ],
                "uncertainty": "",
            },
        ],
    }

    merged = merge_dynasty_governance_current(
        neutral_materials=neutral,
        current=current,
        expected_dynasty_token="TANG",
        expected_source_index_identity="INDEX-1",
        period_terms=["贞观"],
        identity_resolver=resolver,
        subject_ref_by_name=subject_ref_by_name,
        ruler_ref=str(source_pack["ruler_ref"]),
        event_signatures=[
            {
                "event_ref": "EVENT-TONGJIAN-LAW",
                "subject_bindings": [
                    {
                        "subject_ref": source_pack["ruler_ref"],
                        "canonical_name": "李世民",
                    }
                ],
                "chronology_anchors": ["贞观"],
                "location_anchors": [],
                "action_anchors": [],
                "result_anchors": [],
                "quote_anchors": [],
                "backbone_quotes": [
                    {"exact_quote": "太宗授权群臣修订法律条文。"}
                ],
            }
        ],
    )
    repeated = merge_dynasty_governance_current(
        neutral_materials=merged,
        current=current,
        expected_dynasty_token="TANG",
        expected_source_index_identity="INDEX-1",
        period_terms=["贞观"],
        identity_resolver=resolver,
        subject_ref_by_name=subject_ref_by_name,
        ruler_ref=str(source_pack["ruler_ref"]),
        event_signatures=[
            {
                "event_ref": "EVENT-TONGJIAN-LAW",
                "subject_bindings": [
                    {
                        "subject_ref": source_pack["ruler_ref"],
                        "canonical_name": "李世民",
                    }
                ],
                "chronology_anchors": ["贞观"],
                "location_anchors": [],
                "action_anchors": [],
                "result_anchors": [],
                "quote_anchors": [],
                "backbone_quotes": [
                    {"exact_quote": "太宗授权群臣修订法律条文。"}
                ],
            }
        ],
    )

    assert repeated == merged
    assert merged["dynasty_governance_current"] == {
        "dynasty_token": "TANG",
        "input_fingerprint": "DYNASTY-CURRENT-1",
        "source_index_identity": "INDEX-1",
        "selected_chain_count": 5,
        "aligned_to_backbone_chain_count": 1,
        "four_axis_candidate_chain_count": 4,
        "context_only_chain_count": 1,
        "fact_count": 6,
        "model_call_count": 0,
    }
    facts_by_page = {
        row["page_title"]: row for row in merged["fanout"]["facts"]
    }
    fact = facts_by_page["貞觀政要/卷08"]
    assert fact["source_role"] == "dynasty_governance"
    assert fact["actors"][0]["canonical_name"] == "李世民"
    assert fact["actors"][0]["role"] == "authorizer"
    assert fact["outcome_candidate_status"] == "linkable_chain_fact"
    assert fact["event_refs"] == ["EVENT-TONGJIAN-LAW"]
    assert fact["result"] == ""
    assert facts_by_page["貞觀政要/卷08-result"]["result"] == "新律颁行。"
    lifetime_fact = facts_by_page["舊唐書/卷50"]
    assert lifetime_fact["actors"][0]["canonical_name"] == "长孙无忌"
    assert lifetime_fact["period"] == "永徽年间"
    public_result = facts_by_page["貞觀政要/卷01"]
    assert public_result["actors"] == []
    assert public_result["evidence_roles"] == ["public_result"]
    assert public_result["effect_domains"] == [
        "productivity_livelihood",
        "state_people_security",
    ]
    static_context = facts_by_page["唐六典/卷01"]
    assert static_context["outcome_candidate_status"] == "context_only"
    assert static_context["result"] == ""
    assert "保留为背景" in static_context["outcome_candidate_reason"]
    public_burden = facts_by_page["唐會要/卷01"]
    assert public_burden["outcome_candidate_status"] == "linkable_chain_fact"
    assert public_burden["evidence_roles"] == ["public_cost_or_harm"]

    dynasty_review = merge_dynasty_governance_current(
        neutral_materials=neutral,
        current=current,
        expected_dynasty_token="TANG",
        expected_source_index_identity="INDEX-1",
        period_terms=[],
        identity_resolver=resolver,
        subject_ref_by_name=subject_ref_by_name,
        ruler_ref=str(source_pack["ruler_ref"]),
        include_all_dynasty_chains=True,
    )
    assert dynasty_review["dynasty_governance_current"]["selected_chain_count"] == 6
    assert {
        row["page_title"] for row in dynasty_review["fanout"]["facts"]
    } >= {"舊唐書/卷50", "唐六典/卷01"}

    with pytest.raises(ValueError, match="索引版本不一致"):
        merge_dynasty_governance_current(
            neutral_materials=neutral,
            current=current,
            expected_dynasty_token="TANG",
            expected_source_index_identity="INDEX-2",
            period_terms=["贞观"],
            identity_resolver=resolver,
            subject_ref_by_name=subject_ref_by_name,
            ruler_ref=str(source_pack["ruler_ref"]),
        )


def test_seeded_invalid_neutral_segment_retries_without_fresh_page_group(
    tmp_path: Path,
) -> None:
    segment = {
        "segment_ref": "SEG-1",
        "start_offset": 0,
        "end_offset": 4,
        "text": "甲乙人物",
        "text_sha256": hashlib.sha256("甲乙人物".encode("utf-8")).hexdigest(),
        "subject_refs": ["PER-1"],
        "subject_names": ["人物"],
    }
    batch = {
        "batch_ref": "BATCH-1",
        "page_title": "史书/卷1",
        "work_title": "史书",
        "source_url": "local:1",
        "revision_ref": "1",
        "segments": [segment],
    }
    plan = {
        "schema_version": "subject-shared-review-plan-v1",
        "ruler": "皇帝",
        "source_index_identity": "INDEX-1",
        "mention_index_fingerprint": "MENTION-1",
        "page_batches": [batch],
    }

    def fact(quote: str) -> dict:
        return {
            "fact_id": "F1",
            "exact_quote": quote,
            "fact_kind": "institutional_action",
            "action_summary": "人物实施事项",
            "actors": [
                {
                    "source_name": "人物",
                    "canonical_name": "人物",
                    "subject_ref": "PER-1",
                    "role": "executor",
                    "responsibility_strength": "primary",
                    "attribution_basis": "原文直载",
                }
            ],
            "implementation_status": "implemented",
            "result": "事项完成",
            "legacy_status": "not_shown",
            "legacy_basis": "",
                "projection_eligibility": "direct_neutral_fact",
                "outcome_candidate_status": "clear_candidate",
                "outcome_candidate_reason": "行动、结果和责任明确。",
                "uncertainty": "",
        }

    current_result = {
        "schema_version": "shared-neutral-extraction-output-v2",
        "batch_ref": "BATCH-1",
        "page_title": "史书/卷1",
        "revision_ref": "1",
        "segment_count": 1,
        "segment_reviews": [
            {
                "segment_ref": "SEG-1",
                "decision": "accept",
                "facts": [fact("不存在")],
                "reason": "raw",
            }
        ],
        "limitations": [],
    }

    class Runner:
        def run(self, prompt: str):
            input_batch = json.loads(prompt.split("INPUT_BATCHES:\n", 1)[1])[0]
            compact_fact = fact("甲乙人物")
            for key in (
                "fact_id", "legacy_status", "legacy_basis", "projection_eligibility"
            ):
                compact_fact.pop(key)
            compact_fact["segment_ref"] = input_batch["segments"][0]["segment_ref"]
            return (
                {
                    "schema_version": "current-compact-neutral-output-v1",
                    "results": [
                        {
                            "batch_ref": input_batch["batch_ref"],
                            "facts": [compact_fact],
                            "context_requests": [],
                            "limitations": [],
                        }
                    ],
                },
                {},
            )

    output = extract_current_neutral_materials(
        plan=plan,
        current={
            "batch_fingerprints": {
                "BATCH-1": neutral_digest(
                    {
                        "batch": batch,
                        "extraction_policy": NEUTRAL_EXTRACTION_POLICY_VERSION,
                    }
                )
            },
            "batch_results": [current_result],
        },
        runner=Runner(),
        max_workers=1,
        checkpoint_dir=tmp_path / "checkpoint",
        pages_per_call=3,
        subject_ref_by_name={"人物": "PER-1"},
    )

    assert output["model_call_count"] == 1
    assert output["fanout"]["fact_count"] == 1
    assert (tmp_path / "checkpoint/BATCH-1.json").is_file()


def test_neutral_checkpoint_segment_reuse_survives_batch_regrouping(
    tmp_path: Path,
) -> None:
    segment = {
        "segment_ref": "SEG-STABLE",
        "start_offset": 0,
        "end_offset": 4,
        "text": "人物无事",
        "initial_text": "人物无事",
        "text_sha256": hashlib.sha256("人物无事".encode("utf-8")).hexdigest(),
        "subject_refs": ["PER-1"],
        "subject_names": ["人物"],
        "spans": [],
    }
    new_batch = {
        "batch_ref": "BATCH-NEW",
        "page_title": "史书/卷1",
        "work_title": "史书",
        "source_url": "local:1",
        "revision_ref": "1",
        "segments": [segment],
    }
    plan = {
        "schema_version": "subject-shared-review-plan-v1",
        "ruler": "皇帝",
        "source_index_identity": "INDEX-1",
        "mention_index_fingerprint": "MENTION-NEW",
        "page_batches": [new_batch],
    }
    current = {
        "batch_fingerprints": {"BATCH-OLD": "OLD"},
        "batch_results": [
            {
                "schema_version": "shared-neutral-extraction-output-v2",
                "batch_ref": "BATCH-OLD",
                "page_title": "史书/卷1",
                "revision_ref": "1",
                "segment_count": 1,
                "segment_reviews": [
                    {
                        "segment_ref": "SEG-STABLE",
                        "decision": "reject",
                        "context_status": "sufficient",
                        "facts": [],
                        "reason": "无直接中性事实。",
                    }
                ],
                "limitations": [],
            }
        ],
    }
    checkpoint_dir = tmp_path / "checkpoint"
    checkpoint_dir.mkdir()
    (checkpoint_dir / "BATCH-OLD.json").write_text(
        json.dumps(
            {
                "batch_fingerprint": "OLD",
                "result": current["batch_results"][0],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class NoCallRunner:
        def run(self, _prompt: str):
            raise AssertionError("稳定 segment 不应因 batch 重排重新调用模型")

    output = extract_current_neutral_materials(
        plan=plan,
        current=None,
        runner=NoCallRunner(),
        max_workers=1,
        checkpoint_dir=checkpoint_dir,
        subject_ref_by_name={"人物": "PER-1"},
    )

    assert output["model_call_count"] == 0
    assert output["batch_results"][0]["batch_ref"] == "BATCH-NEW"
    assert output["fanout"]["fact_count"] == 0


def test_partial_neutral_segment_reuse_keeps_new_segment_in_normal_group(
    tmp_path: Path,
) -> None:
    def segment(ref: str, text: str) -> dict:
        return {
            "segment_ref": ref,
            "start_offset": 0,
            "end_offset": len(text),
            "text": text,
            "initial_text": text,
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "subject_refs": ["PER-1"],
            "subject_names": ["人物"],
            "spans": [],
        }

    stable = segment("SEG-STABLE", "人物无事")
    fresh = segment("SEG-FRESH", "人物新行事项")
    batch = {
        "batch_ref": "BATCH-MIXED-CACHE",
        "page_title": "史书/卷1",
        "work_title": "史书",
        "source_url": "local:1",
        "revision_ref": "1",
        "segments": [stable, fresh],
    }
    plan = {
        "schema_version": "subject-shared-review-plan-v1",
        "ruler": "皇帝",
        "source_index_identity": "INDEX-1",
        "mention_index_fingerprint": "MENTION-1",
        "page_batches": [batch],
    }
    current = {
        "batch_fingerprints": {"BATCH-OLD": "OLD"},
        "batch_results": [
            {
                "schema_version": "shared-neutral-extraction-output-v2",
                "batch_ref": "BATCH-OLD",
                "page_title": "史书/卷1",
                "revision_ref": "1",
                "segment_count": 1,
                "segment_reviews": [
                    {
                        "segment_ref": "SEG-STABLE",
                        "decision": "reject",
                        "context_status": "sufficient",
                        "facts": [],
                        "reason": "无直接中性事实。",
                    }
                ],
                "limitations": [],
            }
        ],
    }

    class Runner:
        calls = 0

        def run(self, prompt: str):
            self.calls += 1
            input_batches = json.loads(prompt.split("INPUT_BATCHES:\n", 1)[1])
            assert [
                row["segment_ref"]
                for row in input_batches[0]["segments"]
            ] == ["SEG-FRESH"]
            return (
                {
                    "schema_version": "current-compact-neutral-output-v1",
                    "results": [],
                },
                {},
            )

    runner = Runner()
    output = extract_current_neutral_materials(
        plan=plan,
        current=current,
        runner=runner,
        max_workers=1,
        checkpoint_dir=tmp_path / "checkpoint",
        subject_ref_by_name={"人物": "PER-1"},
    )

    assert runner.calls == 1
    assert output["model_call_count"] == 1
    assert [
        row["segment_ref"] for row in output["batch_results"][0]["segment_reviews"]
    ] == ["SEG-STABLE", "SEG-FRESH"]
    assert output["fanout"]["fact_count"] == 0


def test_compact_sparse_output_can_omit_an_empty_batch(tmp_path: Path) -> None:
    def batch(index: int) -> dict:
        text = f"人物无事{index}"
        return {
            "batch_ref": f"BATCH-{index}",
            "page_title": f"史书/卷{index}",
            "work_title": "史书",
            "source_url": f"local:{index}",
            "revision_ref": str(index),
            "segments": [
                {
                    "segment_ref": f"SEG-{index}",
                    "start_offset": 0,
                    "end_offset": len(text),
                    "text": text,
                    "initial_text": text,
                    "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "subject_refs": ["PER-1"],
                    "subject_names": ["人物"],
                    "spans": [],
                }
            ],
        }

    batches = [batch(1), batch(2)]
    plan = {
        "schema_version": "subject-shared-review-plan-v1",
        "ruler": "皇帝",
        "source_index_identity": "INDEX-1",
        "mention_index_fingerprint": "MENTION-1",
        "page_batches": batches,
    }

    class SparseRunner:
        def __init__(self) -> None:
            self.calls = 0
            self.input_batches = []

        def run(self, prompt: str):
            self.calls += 1
            self.input_batches = json.loads(prompt.split("INPUT_BATCHES:\n", 1)[1])
            return (
                {
                    "schema_version": "current-compact-neutral-output-v1",
                    "results": [],
                },
                {},
            )

    runner = SparseRunner()
    output = extract_current_neutral_materials(
        plan=plan,
        current=None,
        runner=runner,
        max_workers=1,
        checkpoint_dir=tmp_path / "checkpoint",
        pages_per_call=5,
        subject_ref_by_name={"人物": "PER-1"},
    )

    assert runner.calls == 1
    assert output["model_call_count"] == 1
    assert output["fanout"]["fact_count"] == 0
    assert len(output["batch_results"]) == 2
    assert runner.input_batches[0]["subject_bindings"] == [
        {"aliases": [], "canonical_name": "人物", "subject_ref": "PER-1"}
    ]
    assert runner.input_batches[0]["segments"][0]["subject_refs"] == ["PER-1"]
    assert "subject_bindings" not in runner.input_batches[0]["segments"][0]
    assert "text_sha256" not in runner.input_batches[0]["segments"][0]


def test_neutral_scan_finishes_one_canary_before_parallel_fanout(
    tmp_path: Path,
) -> None:
    batches = []
    for index in range(3):
        text = f"人物无事{index}"
        batches.append(
            {
                "batch_ref": f"BATCH-CANARY-{index}",
                "page_title": f"史书/卷{index}",
                "work_title": "史书",
                "source_url": f"local:{index}",
                "revision_ref": str(index),
                "segments": [
                    {
                        "segment_ref": f"SEG-CANARY-{index}",
                        "start_offset": 0,
                        "end_offset": len(text),
                        "text": text,
                        "initial_text": text,
                        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                        "subject_refs": ["PER-1"],
                        "subject_names": ["人物"],
                        "spans": [],
                    }
                ],
            }
        )
    plan = {
        "schema_version": "subject-shared-review-plan-v1",
        "ruler": "皇帝",
        "source_index_identity": "INDEX-1",
        "mention_index_fingerprint": "MENTION-CANARY",
        "page_batches": batches,
    }

    class CanaryRunner:
        def __init__(self) -> None:
            self.calls = 0
            self.lock = Lock()
            self.later_started = Event()
            self.fanout_started_before_canary_finished = False

        def run(self, _prompt: str):
            with self.lock:
                call_index = self.calls
                self.calls += 1
            if call_index == 0:
                if self.later_started.wait(0.1):
                    self.fanout_started_before_canary_finished = True
            else:
                self.later_started.set()
            return (
                {
                    "schema_version": "current-compact-neutral-output-v1",
                    "results": [],
                },
                {},
            )

    runner = CanaryRunner()
    output = extract_current_neutral_materials(
        plan=plan,
        current=None,
        runner=runner,
        max_workers=3,
        checkpoint_dir=tmp_path / "checkpoint",
        pages_per_call=1,
        subject_ref_by_name={"人物": "PER-1"},
    )

    assert runner.calls == 3
    assert runner.fanout_started_before_canary_finished is False
    assert output["model_call_count"] == 3


def test_neutral_scan_packs_sparse_segments_but_bounds_dense_campaigns(
    tmp_path: Path,
) -> None:
    def plan(weight: int) -> dict:
        batches = []
        for batch_index in range(2):
            segments = []
            for segment_index in range(8):
                text = f"人物执行事项{batch_index}-{segment_index}。"
                segments.append(
                    {
                        "segment_ref": f"SEG-{weight}-{batch_index}-{segment_index}",
                        "start_offset": 0,
                        "end_offset": len(text),
                        "text": text,
                        "initial_text": text,
                        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                        "subject_refs": ["PER-1"],
                        "subject_names": ["人物"],
                        "model_weight": weight,
                        "spans": [],
                    }
                )
            batches.append(
                {
                    "batch_ref": f"BATCH-{weight}-{batch_index}",
                    "page_title": "史书/卷1",
                    "work_title": "史书",
                    "source_url": f"local:{batch_index}",
                    "revision_ref": "1",
                    "segments": segments,
                }
            )
        return {
            "schema_version": "subject-shared-review-plan-v1",
            "ruler": "皇帝",
            "source_index_identity": "INDEX-1",
            "mention_index_fingerprint": f"MENTION-{weight}",
            "page_batches": batches,
        }

    class Runner:
        def __init__(self) -> None:
            self.calls = 0
            self.input_batch_counts = []

        def run(self, prompt: str):
            self.calls += 1
            self.input_batch_counts.append(
                len(json.loads(prompt.split("INPUT_BATCHES:\n", 1)[1]))
            )
            return {
                "schema_version": "current-compact-neutral-output-v1",
                "results": [],
            }, {}

    sparse_runner = Runner()
    sparse = extract_current_neutral_materials(
        plan=plan(1),
        current=None,
        runner=sparse_runner,
        max_workers=2,
        checkpoint_dir=tmp_path / "sparse",
        pages_per_call=2,
        subject_ref_by_name={"人物": "PER-1"},
    )
    dense_runner = Runner()
    dense = extract_current_neutral_materials(
        plan=plan(2),
        current=None,
        runner=dense_runner,
        max_workers=2,
        checkpoint_dir=tmp_path / "dense",
        pages_per_call=2,
        subject_ref_by_name={"人物": "PER-1"},
    )

    assert sparse["model_call_count"] == sparse_runner.calls == 1
    assert sparse_runner.input_batch_counts == [1]
    assert dense["model_call_count"] == dense_runner.calls == 2


def test_neutral_scan_splits_groups_with_too_many_distinct_subjects(
    tmp_path: Path,
) -> None:
    batches = []
    subject_ref_by_name = {}
    for batch_index in range(2):
        refs = [f"PER-{batch_index * 3 + offset}" for offset in range(3)]
        for ref in refs:
            subject_ref_by_name[ref] = ref
        text = f"人物组{batch_index}执行事项。"
        batches.append(
            {
                "batch_ref": f"BATCH-SUBJECTS-{batch_index}",
                "page_title": "史书/卷1",
                "work_title": "史书",
                "source_url": "local:1",
                "revision_ref": "1",
                "segments": [
                    {
                        "segment_ref": f"SEG-SUBJECTS-{batch_index}",
                        "start_offset": 0,
                        "end_offset": len(text),
                        "text": text,
                        "initial_text": text,
                        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                        "subject_refs": refs,
                        "subject_names": refs,
                        "spans": [],
                    }
                ],
            }
        )

    class Runner:
        def __init__(self) -> None:
            self.calls = 0

        def run(self, _prompt: str):
            self.calls += 1
            return {"schema_version": "current-compact-neutral-output-v1", "results": []}, {}

    runner = Runner()
    output = extract_current_neutral_materials(
        plan={
            "schema_version": "subject-shared-review-plan-v1",
            "ruler": "皇帝",
            "source_index_identity": "INDEX-SUBJECTS",
            "mention_index_fingerprint": "MENTION-SUBJECTS",
            "page_batches": batches,
        },
        current=None,
        runner=runner,
        max_workers=2,
        checkpoint_dir=tmp_path / "checkpoint",
        pages_per_call=2,
        subject_ref_by_name=subject_ref_by_name,
    )

    assert output["model_call_count"] == runner.calls == 2


def test_neutral_scan_propagates_model_anomaly_without_segment_fallback(
    tmp_path: Path,
) -> None:
    text = "人物完成事项。"
    batch = {
        "batch_ref": "BATCH-ANOMALY",
        "page_title": "史书/卷1",
        "work_title": "史书",
        "source_url": "local:1",
        "revision_ref": "1",
        "segments": [
            {
                "segment_ref": "SEG-ANOMALY",
                "start_offset": 0,
                "end_offset": len(text),
                "text": text,
                "initial_text": text,
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "subject_refs": ["PER-1"],
                "subject_names": ["人物"],
                "spans": [],
            }
        ],
    }
    plan = {
        "schema_version": "subject-shared-review-plan-v1",
        "ruler": "皇帝",
        "source_index_identity": "INDEX-1",
        "mention_index_fingerprint": "MENTION-1",
        "page_batches": [batch],
    }

    class AnomalyRunner:
        def __init__(self) -> None:
            self.calls = 0

        def run(self, _prompt: str):
            self.calls += 1
            raise ModelBatchAnomalyError("测试异常子进程")

    runner = AnomalyRunner()
    with pytest.raises(ModelBatchAnomalyError, match="测试异常子进程"):
        extract_current_neutral_materials(
            plan=plan,
            current=None,
            runner=runner,
            max_workers=1,
            checkpoint_dir=tmp_path / "checkpoint",
            subject_ref_by_name={"人物": "PER-1"},
        )

    assert runner.calls == 1
    assert not (tmp_path / "checkpoint/_segments").exists()


def test_neutral_scan_propagates_single_fallback_model_anomaly(
    tmp_path: Path,
) -> None:
    text = "人物完成事项。"
    batch = {
        "batch_ref": "BATCH-ANOMALY-FALLBACK",
        "page_title": "史书/卷1",
        "work_title": "史书",
        "source_url": "local:1",
        "revision_ref": "1",
        "segments": [
            {
                "segment_ref": "SEG-ANOMALY-FALLBACK",
                "start_offset": 0,
                "end_offset": len(text),
                "text": text,
                "initial_text": text,
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "subject_refs": ["PER-1"],
                "subject_names": ["人物"],
                "spans": [],
            }
        ],
    }
    plan = {
        "schema_version": "subject-shared-review-plan-v1",
        "ruler": "皇帝",
        "source_index_identity": "INDEX-1",
        "mention_index_fingerprint": "MENTION-1",
        "page_batches": [batch],
    }

    class AnomalyRunner:
        def run(self, _prompt: str):
            raise ModelBatchAnomalyError("测试异常子进程")

    segment_checkpoint = (
        tmp_path
        / "checkpoint/_segments/BATCH-ANOMALY-FALLBACK--SEG-ANOMALY-FALLBACK.json"
    )
    segment_checkpoint.parent.mkdir(parents=True)
    segment_checkpoint.write_text(
        json.dumps(
            {
                "batch_fingerprint": neutral_digest(
                    {
                        "batch": batch,
                        "extraction_policy": NEUTRAL_EXTRACTION_POLICY_VERSION,
                    }
                ),
                "review": {"invalid": True},
                "limitations": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ModelBatchAnomalyError, match="测试异常子进程"):
        extract_current_neutral_materials(
            plan=plan,
            current=None,
            runner=AnomalyRunner(),
            max_workers=1,
            checkpoint_dir=tmp_path / "checkpoint",
            subject_ref_by_name={"人物": "PER-1"},
        )

    # The anomaly cannot be converted into a false deterministic rejection.
    assert segment_checkpoint.is_file()
    assert json.loads(segment_checkpoint.read_text(encoding="utf-8"))["review"] == {
        "invalid": True
    }


def test_compact_rows_route_by_segment_ref_despite_bad_batch_refs(tmp_path: Path) -> None:
    def make_batch(index: int) -> dict:
        text = f"人物完成事项{index}。"
        return {
            "batch_ref": f"BATCH-{index}",
            "page_title": f"史书/卷{index}",
            "work_title": "史书",
            "source_url": f"local:{index}",
            "revision_ref": str(index),
            "segments": [
                {
                    "segment_ref": f"SEG-{index}",
                    "start_offset": 0,
                    "end_offset": len(text),
                    "text": text,
                    "initial_text": text,
                    "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "subject_refs": ["PER-1"],
                    "subject_names": ["人物"],
                    "spans": [],
                }
            ],
        }

    batches = [make_batch(1), make_batch(2)]
    plan = {
        "schema_version": "subject-shared-review-plan-v1",
        "ruler": "皇帝",
        "source_index_identity": "INDEX-1",
        "mention_index_fingerprint": "MENTION-1",
        "page_batches": batches,
    }

    def compact_fact(index: int) -> dict:
        return {
            "segment_ref": f"SEG-{index}",
            "exact_quote": f"人物完成事项{index}。",
            "fact_kind": "institutional_action",
            "action_summary": f"完成事项{index}",
            "actors": [
                {
                    "source_name": "人物",
                    "canonical_name": "人物",
                    "subject_ref": "PER-1",
                    "role": "executor",
                    "responsibility_strength": "primary",
                    "attribution_basis": "原文直载",
                }
            ],
            "implementation_status": "implemented",
            "result": "事项完成",
            "outcome_candidate_status": "clear_candidate",
            "outcome_candidate_reason": "行动和结果明确。",
            "uncertainty": "",
        }

    class BadContainerRunner:
        def __init__(self) -> None:
            self.calls = 0

        def run(self, _prompt: str):
            self.calls += 1
            return (
                {
                    "schema_version": "current-compact-neutral-output-v1",
                    "results": [
                        {
                            "batch_ref": "UNKNOWN",
                            "facts": [compact_fact(1)],
                            "context_requests": [],
                            "limitations": [],
                        },
                        {
                            "batch_ref": "UNKNOWN",
                            "facts": [compact_fact(2)],
                            "context_requests": [],
                            "limitations": [],
                        },
                    ],
                },
                {},
            )

    runner = BadContainerRunner()
    output = extract_current_neutral_materials(
        plan=plan,
        current=None,
        runner=runner,
        max_workers=1,
        checkpoint_dir=tmp_path / "checkpoint",
        pages_per_call=5,
        subject_ref_by_name={"人物": "PER-1"},
    )

    assert runner.calls == 1
    assert output["model_call_count"] == 1
    assert output["fanout"]["fact_count"] == 2


def test_directed_hits_send_full_context_without_serial_expansion(tmp_path: Path) -> None:
    text = "前文人物行事后文"
    segment = {
        "segment_ref": "SEG-DIRECTED",
        "source_role": "backsource",
        "start_offset": 0,
        "end_offset": len(text),
        "text": text,
        "initial_start_offset": 2,
        "initial_end_offset": 6,
        "initial_text": text[2:6],
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "subject_refs": ["PER-1"],
        "subject_names": ["人物"],
        "spans": [],
    }
    batch = {
        "batch_ref": "BATCH-DIRECTED",
        "page_title": "史书/卷1",
        "work_title": "史书",
        "source_url": "local:1",
        "revision_ref": "1",
        "segments": [segment],
    }
    plan = {
        "schema_version": "subject-shared-review-plan-v1",
        "ruler": "皇帝",
        "source_index_identity": "INDEX-1",
        "mention_index_fingerprint": "MENTION-1",
        "page_batches": [batch],
    }

    class ContextRunner:
        def __init__(self) -> None:
            self.calls = 0
            self.visible_text = ""

        def run(self, prompt: str):
            self.calls += 1
            input_batch = json.loads(prompt.split("INPUT_BATCHES:\n", 1)[1])[0]
            self.visible_text = input_batch["segments"][0]["text"]
            return (
                {
                    "schema_version": "current-compact-neutral-output-v1",
                    "results": [
                        {
                            "batch_ref": input_batch["batch_ref"],
                            "facts": [],
                            "context_requests": [
                                {
                                    "segment_ref": "SEG-DIRECTED",
                                    "context_status": "need_both",
                                }
                            ],
                            "limitations": [],
                        }
                    ],
                },
                {},
            )

    runner = ContextRunner()
    output = extract_current_neutral_materials(
        plan=plan,
        current=None,
        runner=runner,
        max_workers=1,
        checkpoint_dir=tmp_path / "checkpoint",
        subject_ref_by_name={"人物": "PER-1"},
    )

    assert runner.visible_text == text
    assert runner.calls == 1
    assert output["model_call_count"] == 1


def test_unverifiable_compact_quote_is_rejected_without_model_retry(tmp_path: Path) -> None:
    text = "人物完成其事。"
    segment = {
        "segment_ref": "SEG-QUOTE",
        "start_offset": 0,
        "end_offset": len(text),
        "text": text,
        "initial_text": text,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "subject_refs": ["PER-1"],
        "subject_names": ["人物"],
        "spans": [],
    }
    batch = {
        "batch_ref": "BATCH-QUOTE",
        "page_title": "史书/卷1",
        "work_title": "史书",
        "source_url": "local:1",
        "revision_ref": "1",
        "segments": [segment],
    }
    plan = {
        "schema_version": "subject-shared-review-plan-v1",
        "ruler": "皇帝",
        "source_index_identity": "INDEX-1",
        "mention_index_fingerprint": "MENTION-1",
        "page_batches": [batch],
    }

    class QuoteRunner:
        def __init__(self) -> None:
            self.calls = 0

        def run(self, prompt: str):
            self.calls += 1
            input_batch = json.loads(prompt.split("INPUT_BATCHES:\n", 1)[1])[0]
            return (
                {
                    "schema_version": "current-compact-neutral-output-v1",
                    "results": [
                        {
                            "batch_ref": input_batch["batch_ref"],
                            "facts": [
                                {
                                    "segment_ref": "SEG-QUOTE",
                                    "exact_quote": "人物圆满完成了此事",
                                    "fact_kind": "institutional_action",
                                    "action_summary": "人物完成事项",
                                    "actors": [
                                        {
                                            "source_name": "人物",
                                            "canonical_name": "人物",
                                            "subject_ref": "PER-1",
                                            "role": "executor",
                                            "responsibility_strength": "primary",
                                            "attribution_basis": "原文直载",
                                        }
                                    ],
                                    "implementation_status": "implemented",
                                    "result": "事项完成",
                                    "outcome_candidate_status": "clear_candidate",
                                    "outcome_candidate_reason": "行动和结果明确。",
                                    "uncertainty": "",
                                }
                            ],
                            "context_requests": [],
                            "limitations": [],
                        }
                    ],
                },
                {},
            )

    runner = QuoteRunner()
    output = extract_current_neutral_materials(
        plan=plan,
        current=None,
        runner=runner,
        max_workers=1,
        checkpoint_dir=tmp_path / "checkpoint",
        subject_ref_by_name={"人物": "PER-1"},
    )

    assert runner.calls == 1
    assert output["model_call_count"] == 1
    assert output["fanout"]["fact_count"] == 0
    assert output["batch_results"][0]["limitations"] == [
        "引文重试后仍无法逐字回指的事实已拒绝接纳。"
    ]


def test_duplicate_facts_are_deduplicated_without_model_retry(tmp_path: Path) -> None:
    text = "人物完成其事。"
    segment = {
        "segment_ref": "SEG-DUPLICATE",
        "start_offset": 0,
        "end_offset": len(text),
        "text": text,
        "initial_text": text,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "subject_refs": ["PER-1"],
        "subject_names": ["人物"],
        "spans": [],
    }
    batch = {
        "batch_ref": "BATCH-DUPLICATE",
        "page_title": "史书/卷1",
        "work_title": "史书",
        "source_url": "local:1",
        "revision_ref": "1",
        "segments": [segment],
    }
    plan = {
        "schema_version": "subject-shared-review-plan-v1",
        "ruler": "皇帝",
        "source_index_identity": "INDEX-1",
        "mention_index_fingerprint": "MENTION-1",
        "page_batches": [batch],
    }
    fact = {
        "segment_ref": "SEG-DUPLICATE",
        "exact_quote": text,
        "fact_kind": "institutional_action",
        "action_summary": "人物完成事项",
        "actors": [
            {
                "source_name": "人物",
                "canonical_name": "人物",
                "subject_ref": "PER-1",
                "role": "executor",
                "responsibility_strength": "primary",
                "attribution_basis": "原文直载",
            }
        ],
        "implementation_status": "implemented",
        "result": "事项完成",
        "outcome_candidate_status": "clear_candidate",
        "outcome_candidate_reason": "行动和结果明确。",
        "uncertainty": "",
    }

    class DuplicateRunner:
        def __init__(self) -> None:
            self.calls = 0

        def run(self, _prompt: str):
            self.calls += 1
            return (
                {
                    "schema_version": "current-compact-neutral-output-v1",
                    "results": [
                        {
                            "batch_ref": "BATCH-DUPLICATE",
                            "facts": [fact, fact],
                            "context_requests": [],
                            "limitations": [],
                        }
                    ],
                },
                {},
            )

    runner = DuplicateRunner()
    output = extract_current_neutral_materials(
        plan=plan,
        current=None,
        runner=runner,
        max_workers=1,
        checkpoint_dir=tmp_path / "checkpoint",
        subject_ref_by_name={"人物": "PER-1"},
    )

    assert runner.calls == 1
    assert output["model_call_count"] == 1
    assert output["fanout"]["fact_count"] == 1
    assert "模型返回的完全重复中性事实已确定性去重。" in output[
        "batch_results"
    ][0]["limitations"]


def test_strict_quote_retry_rejects_only_unverifiable_fact() -> None:
    batch = {
        "segments": [
            {
                "segment_ref": "SEG-1",
                "text": "可回指原文",
                "subject_refs": ["PER-1"],
            }
        ]
    }
    result = {
        "segment_reviews": [
            {
                "segment_ref": "SEG-1",
                "decision": "accept",
                "reason": "raw",
                "facts": [
                    {
                        "exact_quote": "模型改写引文",
                        "actors": [
                            {
                                "canonical_name": "人物",
                                "subject_ref": "PER-1",
                                "role": "executor",
                            }
                        ],
                    }
                ],
            }
        ],
        "limitations": [],
    }

    repaired = _canonicalize_result(
        batch,
        result,
        subject_ref_by_name={"人物": "PER-1"},
        drop_unverifiable_quotes=True,
    )

    assert repaired["segment_reviews"][0]["decision"] == "reject"
    assert repaired["segment_reviews"][0]["facts"] == []
    assert "引文重试后仍无法逐字回指" in repaired["limitations"][0]


def test_outcome_projection_makes_zero_model_calls_for_settled_quotes(
    tmp_path: Path,
) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    source_pack = json.loads(source.read_text(encoding="utf-8"))
    exact_quote = source_pack["facts"][0]["assertions"][0]["exact_quote"]
    target = tmp_path / "source-pack.json"
    target.write_bytes(source.read_bytes())
    neutral = {
        "fanout": {
            "facts": [
                {
                    "projection_eligibility": "direct_neutral_fact",
                    "exact_quote": exact_quote,
                    "implementation_status": "implemented",
                    "result": "已有结果",
                    "fact_kind": "institutional_action",
                    "actors": [{"subject_ref": source_pack["ruler_ref"]}],
                }
            ]
        }
    }

    outcome = project_current_outcomes(
        source_pack_path=target,
        neutral_materials=neutral,
        source_index=None,  # settled path never dereferences the index
        schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
        runner=None,  # settled path never invokes a model
        checkpoint_dir=tmp_path / "checkpoint",
        workspace_root=ROOT,
        max_workers=1,
    )

    assert outcome["model_call_count"] == 0
    assert outcome["source_pack_changed"] is False


def test_outcome_projection_pauses_for_main_session_review(
    tmp_path: Path,
) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    source_pack = json.loads(source.read_text(encoding="utf-8"))
    target = tmp_path / "source-pack.json"
    target.write_bytes(source.read_bytes())
    fact = {
        "fact_ref": "NEUTRALFACT-MAIN-REVIEW",
        "segment_ref": "SEG-MAIN-REVIEW",
        "page_title": "史书/卷一",
        "revision_ref": "1",
        "exact_quote": "测试战役取得阶段结果。",
        "projection_eligibility": "direct_neutral_fact",
        "implementation_status": "implemented",
        "result": "取得阶段结果",
        "fact_kind": "institutional_action",
        "outcome_candidate_status": "clear_candidate",
        "actors": [{"subject_ref": source_pack["ruler_ref"]}],
    }

    outcome = project_current_outcomes(
        source_pack_path=target,
        neutral_materials={"fanout": {"facts": [fact]}},
        source_index=_campaign_contract_index(tmp_path),
        schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
        runner=None,
        checkpoint_dir=tmp_path / "checkpoint",
        workspace_root=ROOT,
        max_workers=1,
    )

    assert outcome["status"] == "awaiting_main_session_review"
    assert outcome["model_call_count"] == 0
    assert outcome["source_pack_changed"] is False
    assert outcome["review_worklist"]["facts"][0]["fact_ref"] == fact["fact_ref"]


def test_outcome_projection_can_limit_review_to_dynasty_governance(
    tmp_path: Path,
) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    source_pack = json.loads(source.read_text(encoding="utf-8"))
    target = tmp_path / "source-pack.json"
    target.write_bytes(source.read_bytes())
    base = {
        "page_title": "史书/卷一",
        "revision_ref": "1",
        "projection_eligibility": "direct_neutral_fact",
        "implementation_status": "implemented",
        "result": "取得结果",
        "fact_kind": "institutional_action",
        "outcome_candidate_status": "clear_candidate",
        "actors": [{"subject_ref": source_pack["ruler_ref"]}],
    }
    governance = {
        **base,
        "fact_ref": "DYNGOV-FACT-REVIEW",
        "segment_ref": "DYNGOV-SEG-REVIEW",
        "exact_quote": "测试治理取得结果。",
        "source_role": "dynasty_governance",
        "ruler_window_match": True,
    }
    campaign = {
        **base,
        "fact_ref": "NEUTRALFACT-CAMPAIGN",
        "segment_ref": "SEG-CAMPAIGN",
        "exact_quote": "测试战役取得结果。",
        "source_role": "backbone",
    }

    outcome = project_current_outcomes(
        source_pack_path=target,
        neutral_materials={"fanout": {"facts": [governance, campaign]}},
        source_index=_campaign_contract_index(tmp_path),
        schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
        runner=None,
        checkpoint_dir=tmp_path / "checkpoint",
        workspace_root=ROOT,
        max_workers=1,
        included_source_roles=["dynasty_governance"],
    )

    assert [
        row["fact_ref"] for row in outcome["review_worklist"]["facts"]
    ] == ["DYNGOV-FACT-REVIEW"]


def test_outcome_projection_applies_main_session_review_without_model(
    tmp_path: Path,
) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    source_pack = json.loads(source.read_text(encoding="utf-8"))
    target = tmp_path / "source-pack.json"
    target.write_bytes(source.read_bytes())
    fact = {
        "fact_ref": "NEUTRALFACT-MAIN-REVIEW",
        "segment_ref": "SEG-MAIN-REVIEW",
        "page_title": "史书/卷一",
        "revision_ref": "1",
        "exact_quote": "测试战役取得阶段结果。",
        "projection_eligibility": "direct_neutral_fact",
        "implementation_status": "implemented",
        "result": "取得阶段结果",
        "fact_kind": "institutional_action",
        "outcome_candidate_status": "clear_candidate",
        "actors": [{"subject_ref": source_pack["ruler_ref"]}],
    }

    outcome = project_current_outcomes(
        source_pack_path=target,
        neutral_materials={"fanout": {"facts": [fact]}},
        source_index=_campaign_contract_index(tmp_path),
        schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
        runner=None,
        checkpoint_dir=tmp_path / "checkpoint",
        workspace_root=ROOT,
        max_workers=1,
        reviewed_payload=_governance_candidate_payload(),
    )

    written = json.loads(target.read_text(encoding="utf-8"))
    assert outcome["model_call_count"] == 0
    assert outcome["source_pack_changed"] is True
    existing_auto_refs = {
        row["outcome_ref"]
        for row in source_pack["outcome_registry"]["clusters"]
        if row["outcome_ref"].startswith("OUTCOME-AUTO-")
    }
    assert existing_auto_refs <= {
        row["outcome_ref"] for row in written["outcome_registry"]["clusters"]
    }
    assert any(
        row["independent_key"] == "test-governance-contract"
        for row in written["outcome_registry"]["clusters"]
    )
    settled_fact = {
        **fact,
        "fact_ref": "NEUTRALFACT-ALREADY-SETTLED",
        "segment_ref": "SEG-ALREADY-SETTLED",
        "exact_quote": "法者，非朕一人之法，乃天下之法也。",
    }
    clear_non_candidate = {
        **fact,
        "fact_ref": "NEUTRALFACT-CLEAR-NON-CANDIDATE",
        "segment_ref": "SEG-CLEAR-NON-CANDIDATE",
        "exact_quote": "仅为背景叙述，不构成独立成果。",
        "outcome_candidate_status": "clear_non_candidate",
        "outcome_candidate_reason": "背景叙述无独立可验收结果。",
    }
    replay = project_current_outcomes(
        source_pack_path=target,
        neutral_materials={
            "fanout": {
                "facts": [fact, settled_fact, clear_non_candidate],
            }
        },
        source_index=_campaign_contract_index(tmp_path),
        schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
        runner=None,
        checkpoint_dir=tmp_path / "checkpoint",
        workspace_root=ROOT,
        max_workers=1,
        reviewed_payload=_governance_candidate_payload(),
    )
    assert replay["candidate_count"] == 1
    assert replay["source_pack_changed"] is False
    clear_disposition = next(
        row
        for row in replay["dispositions"]
        if row["fact_ref"] == clear_non_candidate["fact_ref"]
    )
    assert clear_disposition["decision"] == "rejected"
    assert clear_disposition["reason"] == clear_non_candidate[
        "outcome_candidate_reason"
    ]


def test_main_review_fact_refs_do_not_expand_by_quote_containment(
    tmp_path: Path,
) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    source_pack = json.loads(source.read_text(encoding="utf-8"))
    target = tmp_path / "source-pack.json"
    target.write_bytes(source.read_bytes())
    reviewed = {
        "fact_ref": "NEUTRALFACT-MAIN-REVIEW",
        "segment_ref": "SEG-MAIN-REVIEW",
        "page_title": "史书/卷一",
        "revision_ref": "1",
        "exact_quote": "测试战役取得阶段结果。",
        "projection_eligibility": "direct_neutral_fact",
        "implementation_status": "implemented",
        "result": "取得阶段结果",
        "fact_kind": "institutional_action",
        "outcome_candidate_status": "clear_candidate",
        "actors": [{"subject_ref": source_pack["ruler_ref"]}],
    }
    neighbouring = {
        **reviewed,
        "fact_ref": "NEUTRALFACT-NEIGHBOUR",
        "segment_ref": "SEG-NEIGHBOUR",
        "exact_quote": "测试战役取得阶段结果。另有相邻事实。",
    }

    outcome = project_current_outcomes(
        source_pack_path=target,
        neutral_materials={"fanout": {"facts": [reviewed, neighbouring]}},
        source_index=_campaign_contract_index(tmp_path),
        schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
        runner=None,
        checkpoint_dir=tmp_path / "checkpoint",
        workspace_root=ROOT,
        max_workers=1,
        reviewed_payload=_governance_candidate_payload(),
    )

    assert outcome["candidate_count"] == 1
    assert all(
        row["fact_ref"] != neighbouring["fact_ref"]
        for row in outcome["dispositions"]
    )


def test_outcome_review_keeps_explicit_actorless_measure_chain_fact(
    tmp_path: Path,
) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    source_pack = json.loads(source.read_text(encoding="utf-8"))
    target = tmp_path / "source-pack.json"
    target.write_bytes(source.read_bytes())
    index_path = tmp_path / "review-measure-chain.sqlite3"
    build_local_source_index(
        [
            {
                "page_title": "政书/卷一",
                "work_title": "政书",
                "source_url": "local:measure",
                "revision_ref": "1",
                "raw_text": "下令建立制度。",
            },
            {
                "page_title": "政书/卷二",
                "work_title": "政书",
                "source_url": "local:result",
                "revision_ref": "2",
                "raw_text": "制度投入运行并形成公共收益。",
            },
        ],
        index_path,
    )
    measure = {
        "fact_ref": "NEUTRALFACT-MEASURE",
        "segment_ref": "SEG-MEASURE",
        "page_title": "政书/卷一",
        "revision_ref": "1",
        "exact_quote": "下令建立制度。",
        "source_role": "dynasty_governance",
        "ruler_window_match": True,
        "projection_eligibility": "linkable_chain_fact",
        "implementation_status": "implemented",
        "result": "建立制度",
        "fact_kind": "institutional_action",
        "outcome_candidate_status": "linkable_chain_fact",
        "evidence_roles": ["measure_or_design"],
        "actors": [],
    }
    result = {
        **measure,
        "fact_ref": "NEUTRALFACT-RESULT",
        "segment_ref": "SEG-RESULT",
        "page_title": "政书/卷二",
        "revision_ref": "2",
        "exact_quote": "制度投入运行并形成公共收益。",
        "projection_eligibility": "direct_neutral_fact",
        "result": "形成公共收益",
        "outcome_candidate_status": "clear_candidate",
        "evidence_roles": ["public_result"],
        "actors": [{"subject_ref": source_pack["ruler_ref"]}],
    }
    payload = _governance_candidate_payload()
    candidate = payload["candidates"][0]
    candidate["source_page"] = measure["page_title"]
    candidate["revision_ref"] = measure["revision_ref"]
    candidate["exact_quotes"] = [
        measure["exact_quote"],
        result["exact_quote"],
    ]
    candidate["evidence_links"] = [
        {
            "fact_ref": measure["fact_ref"],
            "source_page": measure["page_title"],
            "revision_ref": measure["revision_ref"],
            "exact_quote": measure["exact_quote"],
            "evidence_roles": measure["evidence_roles"],
        },
        {
            "fact_ref": result["fact_ref"],
            "source_page": result["page_title"],
            "revision_ref": result["revision_ref"],
            "exact_quote": result["exact_quote"],
            "evidence_roles": result["evidence_roles"],
        },
    ]
    candidate["members"][0]["contribution_basis_fact_refs"] = [
        measure["fact_ref"]
    ]
    candidate["members"][0]["authorization_quotes"] = [
        measure["exact_quote"]
    ]
    for axis in candidate["payload"]["value_judgment"]["axes"].values():
        if axis["basis_fact_refs"]:
            axis["basis_fact_refs"] = [result["fact_ref"]]

    outcome = project_current_outcomes(
        source_pack_path=target,
        neutral_materials={"fanout": {"facts": [measure, result]}},
        source_index=LocalSourceTextIndex(index_path),
        schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
        runner=None,
        checkpoint_dir=tmp_path / "checkpoint",
        workspace_root=ROOT,
        max_workers=1,
        reviewed_payload=payload,
        included_source_roles=["dynasty_governance"],
    )

    assert outcome["model_call_count"] == 0
    assert outcome["candidate_count"] == 1
    written = json.loads(target.read_text(encoding="utf-8"))
    registered = next(
        row
        for row in written["outcome_registry"]["clusters"]
        if row["independent_key"] == "test-governance-contract"
    )
    assert set(registered["fact_refs"]) == {
        measure["fact_ref"],
        result["fact_ref"],
    }


def test_public_registry_match_accepts_cross_source_evidence_union() -> None:
    source = json.loads(
        (
            ROOT / "eval/i5b_current_value/李世民/source-pack.json"
        ).read_text(encoding="utf-8")
    )["outcome_registry"]
    expected = normalize_outcome_registry_for_public_view(source)
    materialized = json.loads(json.dumps(expected, ensure_ascii=False))
    target = materialized["clusters"][0]
    target["fact_refs"].append("PFACT-CROSS-SOURCE")
    target["source_refs"].append("政书/卷一@1#新增证据")
    target["episode_refs"].append("EP-CROSS-SOURCE")
    target["limitations"].append("新增史源只补证据，不改变成果本体。")
    target["evidence_lineage"].append(
        {
            "fact_ref": "PFACT-CROSS-SOURCE",
            "evidence_roles": ["public_result"],
        }
    )
    target["members"][0]["contribution_basis_fact_refs"].append(
        "PFACT-CROSS-SOURCE"
    )
    target["members"][0]["contribution_types"].append("operational_delivery")
    target["semantic_fingerprint"] = cluster_semantic_fingerprint(target)

    assert public_registry_matches_source_pack(materialized, source)

    target["observable_result"] = "改写了成果本体。"
    target["semantic_fingerprint"] = cluster_semantic_fingerprint(target)
    assert not public_registry_matches_source_pack(materialized, source)


def test_governance_without_current_ruler_is_public_but_not_bound() -> None:
    source_pack = json.loads(
        (
            ROOT / "eval/i5b_current_value/李世民/source-pack.json"
        ).read_text(encoding="utf-8")
    )
    governance = next(
        row
        for row in source_pack["outcome_registry"]["clusters"]
        if row["outcome_kind"] == "governance" and row.get("members")
    )
    public_only = json.loads(json.dumps(governance, ensure_ascii=False))
    public_only.update(
        {
            "outcome_ref": "OUTCOME-AUTO-PUBLIC-ONLY",
            "independent_key": "public-only-without-current-ruler",
            "canonical_label": "仅登记为公共成果",
            "members": [
                {
                    **public_only["members"][0],
                    "actor_kind": "person",
                    "actor_ref": "PERSON-PUBLIC-OFFICIAL",
                }
            ],
        }
    )
    public_only["semantic_fingerprint"] = cluster_semantic_fingerprint(public_only)
    source_pack["outcome_registry"]["clusters"].append(public_only)

    registry = build_unbound_historical_outcome_registry([source_pack])
    binding = build_ruler_outcome_bindings(source_pack, registry)
    materialized = materialize_ruler_outcome_registry(registry, binding)

    bound_keys = {
        row["independent_key"] for row in materialized.get("clusters") or ()
    }
    assert public_only["independent_key"] not in bound_keys
    assert any(
        row["independent_key"] == public_only["independent_key"]
        for row in registry["outcomes"]
    )
    assert public_registry_matches_source_pack(
        materialized,
        source_pack["outcome_registry"],
        ruler_ref=str(source_pack["ruler_ref"]),
    )
    assert not public_registry_matches_source_pack(
        materialized, source_pack["outcome_registry"]
    )


def test_shared_outcome_export_includes_reviewed_open_profile_pack(
    tmp_path: Path,
) -> None:
    workspace = _session_release_fixture(tmp_path)
    source_pack_path = (
        workspace / "eval/i5b_current_value/李世民/source-pack.json"
    )
    source_pack = json.loads(source_pack_path.read_text(encoding="utf-8"))
    source_pack["profile_projection_gate"].update(
        {
            "status": "material_coverage_open",
            "material_coverage_complete": False,
            "freeze_allowed": False,
        }
    )
    source_pack_path.write_text(
        json.dumps(source_pack, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )

    published = write_current_outcome_layers(
        workspace,
        include_rulers=["李世民"],
    )
    source_outcome_refs = {
        str(row["outcome_ref"])
        for row in source_pack["outcome_registry"]["clusters"]
    }
    registered_origin_refs = {
        str(origin_ref)
        for row in published["registry"]["outcomes"]
        for origin_ref in row.get("origin_outcome_refs") or ()
    }

    assert "李世民" in published["included_rulers"]
    assert source_outcome_refs <= registered_origin_refs
    assert "TANG" in published["partition_paths"]
    open_profiles = [
        row
        for row in published["profile_registry"]["profiles"]
        if row["coverage_status"] == "registered_outcomes_only"
    ]
    assert open_profiles
    assert all(
        row["overall_grade_status"] == "registered_outcomes_lower_bound"
        for row in open_profiles
    )


def test_shared_outcome_export_merges_dynasty_baseline_before_ruler_binding(
    tmp_path: Path,
) -> None:
    workspace = _session_release_fixture(tmp_path)
    ruler_pack = json.loads(
        (
            workspace / "eval/i5b_current_value/李世民/source-pack.json"
        ).read_text(encoding="utf-8")
    )
    baseline_cluster = deepcopy(ruler_pack["outcome_registry"]["clusters"][0])
    baseline_cluster.update(
        {
            "outcome_ref": "OUTCOME-DYNASTY-BASELINE-ONLY",
            "independent_key": "DYNASTY-BASELINE-ONLY",
            "canonical_label": "朝代政书独立治理成果",
        }
    )
    baseline_cluster["semantic_fingerprint"] = cluster_semantic_fingerprint(
        baseline_cluster
    )
    baseline_pack = {
        "schema_version": "dynasty-governance-outcome-pack-v1",
        "pack_scope": "dynasty_governance",
        "dynasty": "唐",
        "dynasty_token": "TANG",
        "ruler": "唐治理底账",
        "ruler_ref": "DYNASTY-TANG",
        "window": "全朝",
        "members": [],
        "facts": [],
        "source_pack_sha256": "DYNASTY-BASELINE-PACK",
        "outcome_registry": {
            "schema_version": "historical-outcome-cluster-registry-v1",
            "status": "shadow",
            "clusters": [baseline_cluster],
        },
    }

    published = write_current_outcome_layers(
        workspace,
        include_rulers=["李世民"],
        dynasty_outcome_packs={"TANG": baseline_pack},
    )

    registered = {
        str(origin_ref)
        for row in published["registry"]["outcomes"]
        for origin_ref in row.get("origin_outcome_refs") or ()
    }
    assert "OUTCOME-DYNASTY-BASELINE-ONLY" in registered
    partition = json.loads(
        Path(published["partition_paths"]["TANG"]["outcome_json"]).read_text(
            encoding="utf-8"
        )
    )
    assert "DYNASTY-BASELINE-PACK" in partition["declarations"][
        "source_pack_refs"
    ]


def test_outcome_projection_ignores_shared_fact_outside_current_team(
    tmp_path: Path,
) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    target = tmp_path / "source-pack.json"
    target.write_bytes(source.read_bytes())
    neutral = {
        "fanout": {
            "facts": [
                {
                    "fact_ref": "NEUTRALFACT-LIYUAN-ONLY",
                    "projection_eligibility": "direct_neutral_fact",
                    "exact_quote": "高祖命有司施行。",
                    "implementation_status": "implemented",
                    "result": "已施行",
                    "fact_kind": "institutional_action",
                    "actors": [
                        {"subject_ref": "RULER-NAME-CANDIDATE-LIYUAN"}
                    ],
                }
            ]
        }
    }

    outcome = project_current_outcomes(
        source_pack_path=target,
        neutral_materials=neutral,
        source_index=None,
        schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
        runner=None,
        checkpoint_dir=tmp_path / "checkpoint",
        workspace_root=ROOT,
        max_workers=1,
    )

    assert outcome["candidate_count"] == 0
    assert outcome["model_call_count"] == 0
    assert outcome["source_pack_changed"] is False


def test_outcome_projection_includes_dynasty_governance_outside_ruler_window(
    tmp_path: Path,
) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    target = tmp_path / "source-pack.json"
    target.write_bytes(source.read_bytes())
    index_path = tmp_path / "source.sqlite3"
    build_local_source_index(
        [
            {
                "page_title": "政书/卷一",
                "work_title": "政书",
                "source_url": "local:test",
                "revision_ref": "1",
                "raw_text": "另一在位窗口的政书事实形成公共结果。",
            }
        ],
        index_path,
    )
    neutral = {
        "fanout": {
            "facts": [
                {
                    "fact_ref": "FACT-OUTSIDE-GOVERNANCE-WINDOW",
                    "source_role": "dynasty_governance",
                    "ruler_window_match": False,
                    "projection_eligibility": "direct_neutral_fact",
                    "outcome_candidate_status": "clear_candidate",
                    "evidence_roles": ["public_result"],
                    "page_title": "政书/卷一",
                    "revision_ref": "1",
                    "exact_quote": "另一在位窗口的政书事实形成公共结果。",
                    "implementation_status": "implemented",
                    "result": "已经完成",
                    "fact_kind": "institutional_action",
                    "actors": [{"subject_ref": "RULER-OTHER"}],
                },
            ]
        },
    }

    outcome = project_current_outcomes(
        source_pack_path=target,
        neutral_materials=neutral,
        source_index=LocalSourceTextIndex(index_path),
        schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
        runner=None,
        checkpoint_dir=tmp_path / "checkpoint",
        workspace_root=ROOT,
        max_workers=1,
    )

    assert outcome["status"] == "awaiting_main_session_review"
    assert [row["fact_ref"] for row in outcome["review_worklist"]["facts"]] == [
        "FACT-OUTSIDE-GOVERNANCE-WINDOW"
    ]
    assert outcome["model_call_count"] == 0
    assert outcome["source_pack_changed"] is False


def test_outcome_projection_keeps_accepted_dispositions_across_runner_changes(
    tmp_path: Path,
) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    target = tmp_path / "source-pack.json"
    target.write_bytes(source.read_bytes())
    fact = {
        "fact_ref": "NEUTRALFACT-STABLE-PROJECTION",
        "segment_ref": "SEG-STABLE-PROJECTION",
        "page_title": "测试史书/卷1",
        "revision_ref": "1",
        "exact_quote": "已经验收且不应因调度变化重跑的独立引文。",
        "projection_eligibility": "direct_neutral_fact",
        "implementation_status": "implemented",
        "result": "已有验收结论",
        "fact_kind": "institutional_action",
        "outcome_candidate_status": "ambiguous",
    }
    policy_fingerprint = hashlib.sha256(
        json.dumps(
            {"projection_policy": PROJECTION_POLICY_VERSION},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    class ChangedRunner:
        policy_fingerprint = "new-model-or-scheduler"

        def run(self, _prompt: str):
            raise AssertionError("已验收 disposition 不得因 runner 变化重跑")

    outcome = project_current_outcomes(
        source_pack_path=target,
        neutral_materials={
            "fanout": {"facts": [fact]},
            "outcome_projection": {
                "policy_fingerprint": policy_fingerprint,
                "dispositions": [
                    {
                        "fact_ref": fact["fact_ref"],
                        "decision": "rejected",
                        "reason": "已验收为非独立成果。",
                    }
                ],
            },
        },
        source_index=None,
        schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
        runner=ChangedRunner(),
        checkpoint_dir=tmp_path / "checkpoint",
        workspace_root=ROOT,
        max_workers=1,
    )

    assert outcome["model_call_count"] == 0
    assert outcome["source_pack_changed"] is False
    assert outcome["policy_fingerprint"] == policy_fingerprint


def test_outcome_projection_keeps_cross_source_event_atomic(tmp_path: Path) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    source_pack = json.loads(source.read_text(encoding="utf-8"))
    target = tmp_path / "source-pack.json"
    target.write_bytes(source.read_bytes())

    class RejectingRunner:
        policy_fingerprint = "test-policy"

        def __init__(self) -> None:
            self.calls: list[list[dict]] = []

        def run(self, prompt: str) -> tuple[dict, str]:
            facts = json.loads(prompt.split("INPUT_FACTS:\n", 1)[1])
            self.calls.append(facts)
            task_code = re.search(r"task_code=(OUTCOME-AUTO-[A-F0-9]+)", prompt)
            assert task_code is not None
            return (
                {
                    "schema_version": "current-outcome-candidate-output-v3",
                    "task_code": task_code.group(1),
                    "candidates": [],
                    "rejections": [
                        {"segment_ref": fact["segment_ref"], "reason": "测试拒绝"}
                        for fact in facts
                    ],
                },
                "",
            )

    facts = [
        {
            "fact_ref": f"NEUTRALFACT-{index}",
            "segment_ref": f"SEG-{index}",
            "page_title": f"史书/卷{index}",
            "revision_ref": str(index),
            "exact_quote": f"同一事件独立史源引文{index}",
            "projection_eligibility": "direct_neutral_fact",
            "implementation_status": "implemented",
            "result": "形成可观察结果",
            "fact_kind": "institutional_action",
                "outcome_candidate_status": "clear_candidate",
                "event_refs": ["EVENT-SAME"],
                "actors": [{"subject_ref": source_pack["ruler_ref"]}],
        }
        for index in (1, 2)
    ]
    facts[0]["source_url"] = "local:must-not-enter-model-prompt"
    facts[0]["segment_text_sha256"] = "redundant-hash"
    runner = RejectingRunner()
    index_path = tmp_path / "source.sqlite3"
    build_local_source_index(
        [
            {
                "page_title": "史书/卷1",
                "work_title": "史书",
                "source_url": "local:test",
                "revision_ref": "1",
                "raw_text": "测试",
            }
        ],
        index_path,
    )
    outcome = project_current_outcomes(
        source_pack_path=target,
        neutral_materials={"fanout": {"facts": facts}},
        source_index=LocalSourceTextIndex(index_path),
        schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
        runner=runner,
        checkpoint_dir=tmp_path / "checkpoint",
        workspace_root=ROOT,
        max_workers=1,
        facts_per_call=1,
    )

    assert len(runner.calls) == 1
    assert {row["event_refs"][0] for row in runner.calls[0]} == {"EVENT-SAME"}
    assert "source_url" not in runner.calls[0][0]
    assert "segment_text_sha256" not in runner.calls[0][0]
    assert outcome["model_call_count"] == 1


def test_outcome_projection_finishes_one_canary_before_parallel_fanout(
    tmp_path: Path,
) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    source_pack = json.loads(source.read_text(encoding="utf-8"))
    target = tmp_path / "source-pack.json"
    target.write_bytes(source.read_bytes())
    index_path = tmp_path / "source.sqlite3"
    build_local_source_index(
        [
            {
                "page_title": "史书/卷1",
                "work_title": "史书",
                "source_url": "local:test",
                "revision_ref": "1",
                "raw_text": "人物完成新的治理事项。",
            }
        ],
        index_path,
    )

    class CanaryRunner:
        policy_fingerprint = "test-canary-policy"

        def __init__(self) -> None:
            self.calls = 0
            self.lock = Lock()
            self.later_started = Event()
            self.fanout_started_before_canary_finished = False

        def run(self, prompt: str):
            with self.lock:
                call_index = self.calls
                self.calls += 1
            if call_index == 0:
                if self.later_started.wait(0.1):
                    self.fanout_started_before_canary_finished = True
            else:
                self.later_started.set()
            facts = json.loads(prompt.split("INPUT_FACTS:\n", 1)[1])
            task_code = re.search(r"task_code=(OUTCOME-AUTO-[A-F0-9]+)", prompt)
            assert task_code is not None
            return (
                {
                    "schema_version": "current-outcome-candidate-output-v3",
                    "task_code": task_code.group(1),
                    "candidates": [],
                    "rejections": [
                        {"segment_ref": fact["segment_ref"], "reason": "测试拒绝"}
                        for fact in facts
                    ],
                },
                {},
            )

    facts = [
        {
            "fact_ref": f"NEUTRALFACT-CANARY-{index}",
            "segment_ref": f"SEG-CANARY-{index}",
            "page_title": "史书/卷1",
            "revision_ref": "1",
            "exact_quote": "人物完成新的治理事项。",
            "projection_eligibility": "direct_neutral_fact",
            "implementation_status": "implemented",
            "result": f"形成结果{index}",
            "fact_kind": "institutional_action",
                "outcome_candidate_status": "ambiguous",
                "event_refs": [f"EVENT-CANARY-{index}"],
                "actors": [{"subject_ref": source_pack["ruler_ref"]}],
        }
        for index in range(3)
    ]
    runner = CanaryRunner()
    outcome = project_current_outcomes(
        source_pack_path=target,
        neutral_materials={"fanout": {"facts": facts}},
        source_index=LocalSourceTextIndex(index_path),
        schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
        runner=runner,
        checkpoint_dir=tmp_path / "checkpoint",
        workspace_root=ROOT,
        max_workers=3,
        facts_per_call=1,
    )

    assert runner.calls == 3
    assert runner.fanout_started_before_canary_finished is False
    assert outcome["model_call_count"] == 3


def test_outcome_projection_propagates_model_anomaly_without_split(
    tmp_path: Path,
) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    source_pack = json.loads(source.read_text(encoding="utf-8"))
    target = tmp_path / "source-pack.json"
    target.write_bytes(source.read_bytes())
    index_path = tmp_path / "source.sqlite3"
    build_local_source_index(
        [
            {
                "page_title": "史书/卷1",
                "work_title": "史书",
                "source_url": "local:test",
                "revision_ref": "1",
                "raw_text": "人物完成新的治理事项。",
            }
        ],
        index_path,
    )

    class AnomalyRunner:
        policy_fingerprint = "test-policy"

        def __init__(self) -> None:
            self.calls = 0

        def run(self, _prompt: str):
            self.calls += 1
            raise ModelBatchAnomalyError("成果投影异常子进程")

    runner = AnomalyRunner()
    neutral = {
        "fanout": {
            "facts": [
                {
                    "fact_ref": "NEUTRALFACT-ANOMALY",
                    "segment_ref": "SEG-ANOMALY",
                    "page_title": "史书/卷1",
                    "revision_ref": "1",
                    "exact_quote": "人物完成新的治理事项。",
                    "projection_eligibility": "direct_neutral_fact",
                    "implementation_status": "implemented",
                    "result": "形成新的可观察结果",
                    "fact_kind": "institutional_action",
                        "outcome_candidate_status": "clear_candidate",
                        "event_refs": ["EVENT-ANOMALY"],
                        "actors": [{"subject_ref": source_pack["ruler_ref"]}],
                }
            ]
        }
    }

    with pytest.raises(ModelBatchAnomalyError, match="成果投影异常子进程"):
        project_current_outcomes(
            source_pack_path=target,
            neutral_materials=neutral,
            source_index=LocalSourceTextIndex(index_path),
            schema_path=ROOT / "config/current-outcome-candidate-output.schema.json",
            runner=runner,
            checkpoint_dir=tmp_path / "checkpoint",
            workspace_root=ROOT,
            max_workers=1,
        )

    assert runner.calls == 1


def test_current_source_pack_increment_is_validated_and_idempotent(tmp_path: Path) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    increment = {
        "schema_version": SOURCE_PACK_INCREMENT_SCHEMA_VERSION,
        "ruler": "李世民",
        "facts": [],
        "outcomes": [],
    }
    compiled = compile_source_pack_increment(payload, increment)
    assert compiled == payload
    target = tmp_path / "source-pack.json"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    assert apply_source_pack_increment(
        target, increment, workspace_root=ROOT
    ) is False

    conflicting = dict(payload["facts"][0])
    conflicting["neutral_summary"] = "冲突内容"
    with pytest.raises(ValueError, match="record_ref 冲突"):
        compile_source_pack_increment(
            payload,
            {**increment, "facts": [conflicting]},
        )

    replacement_outcome = dict(payload["outcome_registry"]["clusters"][0])
    replacement_outcome["canonical_label"] += "（审定替换）"
    replacement = compile_source_pack_increment(
        payload,
        {
            **increment,
            "facts": [conflicting],
            "outcomes": [replacement_outcome],
        },
        replace_incoming=True,
    )
    replaced_facts = {row["record_ref"]: row for row in replacement["facts"]}
    replaced_outcomes = {
        row["outcome_ref"]: row
        for row in replacement["outcome_registry"]["clusters"]
    }
    assert replaced_facts[conflicting["record_ref"]]["neutral_summary"] == "冲突内容"
    assert (
        replaced_outcomes[replacement_outcome["outcome_ref"]]["canonical_label"]
        == replacement_outcome["canonical_label"]
    )
    assert len(replacement["facts"]) == len(payload["facts"])
    assert len(replaced_outcomes) == len(payload["outcome_registry"]["clusters"])
    untouched_outcome = payload["outcome_registry"]["clusters"][1]
    assert replaced_outcomes[untouched_outcome["outcome_ref"]] == untouched_outcome

    old_outcome = next(
        row
        for row in payload["outcome_registry"]["clusters"]
        if row["outcome_ref"].startswith("OUTCOME-AUTO-")
    )
    old_fact_ref = old_outcome["fact_refs"][0]
    replacement_fact = next(
        row for row in payload["facts"] if row["record_ref"] == old_fact_ref
    )
    rekeyed_outcome = json.loads(json.dumps(old_outcome, ensure_ascii=False))
    rekeyed_outcome["outcome_ref"] = "OUTCOME-AUTO-REKEYED"
    rekeyed_outcome["independent_key"] = "rekeyed-reviewed-outcome"
    rekeyed = compile_source_pack_increment(
        payload,
        {
            **increment,
            "facts": [replacement_fact],
            "outcomes": [rekeyed_outcome],
        },
        replace_incoming=True,
    )
    rekeyed_refs = {
        row["outcome_ref"] for row in rekeyed["outcome_registry"]["clusters"]
    }
    assert old_outcome["outcome_ref"] not in rekeyed_refs
    assert rekeyed_outcome["outcome_ref"] in rekeyed_refs


def test_source_pack_increment_does_not_run_downstream_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    target = tmp_path / "source-pack.json"
    target.write_bytes(source.read_bytes())
    current = json.loads(source.read_text(encoding="utf-8"))
    compiled = {**current, "stage_test_marker": True}
    monkeypatch.setattr(
        current_source_pack_compiler_module,
        "compile_source_pack_increment",
        lambda *_args, **_kwargs: compiled,
    )
    changed = apply_source_pack_increment(
        target,
        {
            "schema_version": SOURCE_PACK_INCREMENT_SCHEMA_VERSION,
            "ruler": "李世民",
            "facts": [],
            "outcomes": [],
        },
        workspace_root=ROOT,
    )

    assert changed is True
    assert json.loads(target.read_text(encoding="utf-8"))["stage_test_marker"] is True


def test_current_li_and_liu_outcome_quality_decisions_are_pinned() -> None:
    li = json.loads(
        (ROOT / "eval/i5b_current_value/李世民/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    li_outcomes = {
        row["outcome_ref"]: row for row in li["outcome_registry"]["clusters"]
    }
    goguryeo = li_outcomes["OUTCOME-LSM-CAMPAIGN-GOGURYEO-645"]
    assert goguryeo["payload"]["campaign_tier"] == "S-"
    assert goguryeo["payload"]["operational_costs"] == []
    assert len(goguryeo["payload"]["objective_shortfalls"]) == 1
    assert [
        (row["actor_name"], row["severity_index"])
        for row in goguryeo["payload"]["attributable_failures"]
    ] == [("张君乂", 0.2)]
    hulao = li_outcomes["OUTCOME-LSM-CAMPAIGN-HULAO"]
    assert hulao["payload"]["campaign_tier"] == "S+"
    assert hulao["payload"]["strategic_result_class"] == "composite_poles_terminal"
    assert hulao["payload"]["combat_difficulty"] == "D3"
    assert hulao["payload"]["operational_costs"] == []
    assert hulao["payload"]["objective_shortfalls"] == []
    assert hulao["payload"]["attributable_failures"] == []

    labels = {row["canonical_label"]: row for row in li_outcomes.values()}
    clan_registry = labels["考订并颁行氏族志"]
    assert clan_registry["scale"]["level"] == "national"
    assert clan_registry["scale"]["consequence_basis"] == "national_cultural_corpus"
    historiography = labels["贞观五代史官修工程"]
    assert historiography["scale"]["level"] == "national"
    assert "五代史" in historiography["observable_result"]
    historiography_roles = {
        row["actor_name"]: row["role_code"] for row in historiography["members"]
    }
    assert historiography_roles == {
        "李世民": "authorized",
        "房玄龄": "lead",
        "魏徵": "lead",
    }
    jinshu = labels["贞观《晋书》官修工程"]
    assert jinshu["scale"]["consequence_basis"] == "national_cultural_corpus"
    assert {
        row["actor_name"]: row["role_code"] for row in jinshu["members"]
    } == {
        "李世民": "authorized",
        "房玄龄": "lead",
        "褚遂良": "governance_participant",
    }
    veritable_records = labels["高祖太宗实录修撰"]
    assert veritable_records["scale"]["level"] == "important"
    assert veritable_records["important_method_or_legacy"] is False
    prince_tenure = labels["王府官僚任职不得超过四考"]
    assert prince_tenure["outcome_kind"] == "governance"
    assert prince_tenure["result_direction"] == "positive"
    assert prince_tenure["scale"]["level"] == "important"
    lingnan = labels["岭南冲突遣使安抚定局"]
    assert lingnan["outcome_kind"] == "statecraft"
    assert lingnan["settlement_scope"] == "person_statecraft_result"
    zhangsun_lifetime = [
        row
        for row in li_outcomes.values()
        if row["settlement_scope"] == "person_governance_result"
        and "长孙无忌" in {member["actor_name"] for member in row["members"]}
    ]
    assert {row["canonical_label"] for row in zhangsun_lifetime} == {
        "长孙无忌与褚遂良共同辅政并促成永徽百姓阜安",
        "永徽律令格式与《律疏》编定颁行",
    }
    assert all(row["ruler_window_status"] == "outside_window" for row in zhangsun_lifetime)
    assert all(
        row not in _ruler_window_outcomes(list(li_outcomes.values()))
        for row in zhangsun_lifetime
    )
    assert not {
        "OUTCOME-LSM-GOV-LUXURY-SHIFT",
        "OUTCOME-LSM-GOV-LATE-COMMUNICATION",
        "OUTCOME-LSM-GOV-LATE-JUSTICE",
        "OUTCOME-LSM-GOV-FAMINE-RELIEF",
    } & set(li_outcomes)

    liu = json.loads(
        (ROOT / "eval/i5b_current_value/刘邦/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    liu_outcomes = liu["outcome_registry"]["clusters"]
    assert any(row["canonical_label"] == "西进入关灭秦战役群" for row in liu_outcomes)
    all_campaigns = [
        row
        for row in [*li_outcomes.values(), *liu_outcomes]
        if row["outcome_kind"] == "campaign"
    ]
    assert all(
        all(
            token in row["payload"]["campaign_tier_basis"]
            for token in ("土地轴=", "对手轴=", "结果轴=")
        )
        for row in all_campaigns
    )
    liu_labels = {row["canonical_label"]: row for row in liu_outcomes}
    statecraft_labels = {
        row["canonical_label"]
        for row in liu_outcomes
        if row["outcome_kind"] == "statecraft"
    }
    assert statecraft_labels == {
        "陈平白登解围处置",
        "陈平荥阳解围与最高统帅脱险处置",
        "张良重组彭城败后联盟与方面用将",
        "张良修复固陵诸侯失期危机",
        "张良制止复立六国后方案",
    }
    assert all(
        row["settlement_scope"] == "person_statecraft_result"
        for row in liu_outcomes
        if row["outcome_kind"] == "statecraft"
    )
    assert "陈平云梦诱捕韩信" not in liu_labels
    assert sum(row["outcome_kind"] == "governance" for row in liu_outcomes) == 7
    assert "采纳娄敬张良建议定都长安" not in liu_labels
    assert "汉匈和亲约" not in liu_labels
    assert liu_labels["平定陈豨叛乱战役群"]["payload"]["campaign_tier"] == "A"
    tang_unification_labels = {
        "洛阳—虎牢灭王世充窦建德战役群",
        "柏壁—介休平刘武周宋金刚战役群",
        "浅水原平薛仁杲战役群",
        "洺水击破刘黑闼战役群",
        "曹州—淮泗平徐圆朗战役群",
    }
    han_unification_labels = {
        "还定三秦战役群",
        "韩信破代赵并定燕战役群",
        "韩信潍水破齐并平定齐地",
        "韩信平定魏地",
        "垓下灭楚终局战役群",
        "彭越经营梁地并断楚粮道战役群",
    }
    tang_unification = {
        labels[name]["payload"]["campaign_tier"]
        for name in tang_unification_labels
    }
    han_unification = {
        liu_labels[name]["payload"]["campaign_tier"]
        for name in han_unification_labels
    }
    assert tang_unification == {"S+", "S-", "A"}
    assert han_unification == {"S+", "S-", "A"}
    assert liu_labels["垓下灭楚终局战役群"]["payload"]["strategic_result_class"] == "unification_terminal"
    assert liu_labels["平城白登汉匈战役群"]["payload"]["combat_difficulty"] == "D3"
    assert liu_labels["平城白登汉匈战役群"]["payload"]["campaign_tier"] == "A"
    assert labels["洺水击破刘黑闼战役群"]["payload"]["combat_difficulty"] == "D3"
    assert labels["贞观四年平东突厥战役群"]["payload"]["strategic_result_class"] == "external_hegemony_terminal"
    western_turks = labels["苏定方平西突厥战役群"]["payload"]
    assert western_turks["campaign_tier"] == "S"
    assert western_turks["strategic_result_class"] == "single_pole_or_state_terminal"
    assert western_turks["opponent_strategic_weight"] == "external_state"
    assert "万余" in western_turks["combat_difficulty_basis"]
    assert "十万" in western_turks["combat_difficulty_basis"]
    congling = labels["苏定方平都曼与葱岭战役群"]["payload"]
    assert congling["campaign_tier"] == "A"
    assert congling["combat_difficulty"] == "D2"
    assert congling["objective_completion"] == "complete"
    pyongyang = labels["苏定方平壤道征高丽战役群"]["payload"]
    assert pyongyang["campaign_tier"] == "A"
    assert pyongyang["combat_difficulty"] == "D2"
    assert pyongyang["battle_result"] == "mixed"
    assert pyongyang["objective_completion"] == "partial"
    hanxin = [
        row
        for row in liu_outcomes
        if row["settlement_scope"] == "ruler_campaign_parent"
        and "韩信" in {member["actor_name"] for member in row["members"]}
        and row["canonical_label"] in han_unification_labels
    ]
    assert {row["canonical_label"] for row in hanxin} == {
        "韩信平定魏地",
        "韩信破代赵并定燕战役群",
        "韩信潍水破齐并平定齐地",
        "垓下灭楚终局战役群",
    }
    for row in hanxin:
        members = {member["actor_name"]: member for member in row["members"]}
        assert members["韩信"]["role_code"] == "commander_in_chief"
        if row["canonical_label"] == "垓下灭楚终局战役群":
            assert members["刘邦"]["role_code"] == "principal_commander"
            assert (
                members["刘邦"]["ruler_campaign_relation"]
                == "operational_direction"
            )
            assert row["payload"]["campaign_tier"] == "S+"
        else:
            assert members["刘邦"]["role_code"] == "not_in_command_chain"
            assert members["刘邦"]["ruler_campaign_relation"] == "authorization_only"

    external_wars = {
        "贞观十九年亲征高句丽战役群",
        "平城白登汉匈战役群",
    }
    assert external_wars <= set(labels) | set(liu_labels)
    assert not external_wars & tang_unification_labels
    assert not external_wars & han_unification_labels


def test_unbound_outcome_registry_precedes_ruler_window_projection() -> None:
    source_packs = [
        json.loads(
            (ROOT / "eval/i5b_current_value" / ruler / "source-pack.json").read_text(
                encoding="utf-8"
            )
        )
        for ruler in ("李世民", "刘邦")
    ]
    registry = build_unbound_historical_outcome_registry(source_packs)
    assert registry["status"] == "current_shadow_unbound"
    assert registry["declarations"]["outcome_count"] == 78
    assert registry["declarations"]["campaign_count"] == 39
    assert registry["declarations"]["governance_count"] == 33
    assert registry["declarations"]["statecraft_count"] == 6
    assert registry["declarations"]["window_binding_count"] == 0
    for outcome in registry["outcomes"]:
        assert "ruler_window_status" not in outcome
        assert "settlement_scope" not in outcome
        assert "ruler_context_refs" not in outcome
        for member in outcome["members"]:
            assert "actor_kind" not in member
            assert "talent_credit" not in member
            assert "ruler_campaign_relation" not in member

    rendered = render_unbound_historical_outcome_registry_markdown(registry)
    assert "# 战役、治理与谋略成果总登记（未绑定皇帝窗口）" in rendered
    assert "总成果：78" in rendered
    assert "谋略：6" in rendered
    assert "永徽律令格式与《律疏》编定颁行" in rendered
    assert "ruler_window_status" not in rendered
    assert "战役群" in rendered
    assert "主帅" in rendered
    assert "前线指挥" in rendered
    assert "全国核心子系统" in rendered
    assert "因果已建立" in rendered
    assert "campaign_group" not in rendered
    assert "commander_in_chief" not in rendered
    assert "frontline_command" not in rendered
    assert "national_core_subsystem" not in rendered
    assert "established" not in rendered
    assert " / N=" not in rendered
    assert "固定 固定版本" not in rendered
    for source_pack in source_packs:
        binding = build_ruler_outcome_bindings(source_pack, registry)
        assert binding["schema_version"] == "ruler-outcome-binding-v2"
        registered_by_ref = {
            row["registration_ref"]: row for row in registry["outcomes"]
        }
        for row in binding["bindings"]:
            if row.get("context_only_ancestor"):
                continue
            registered = registered_by_ref[row["registration_ref"]]
            if registered["outcome_kind"] == "governance":
                assert any(
                    member["actor_ref"] == source_pack["ruler_ref"]
                    for member in registered["members"]
                )
        materialized = materialize_ruler_outcome_registry(registry, binding)
        assert public_registry_matches_source_pack(
            materialized,
            source_pack["outcome_registry"],
            ruler_ref=str(source_pack["ruler_ref"]),
        )
        if source_pack["ruler"] == "李世民":
            hulao = next(
                row
                for row in materialized["clusters"]
                if row["outcome_ref"] == "OUTCOME-LSM-CAMPAIGN-HULAO"
            )
            actor_kind = {
                row["actor_name"]: row["actor_kind"] for row in hulao["members"]
            }
            assert actor_kind["李渊"] == "ruler"
            assert actor_kind["李世民"] == "ruler"
            sovereign_at_event = {
                row["actor_name"]: row["sovereign_at_event"]
                for row in hulao["members"]
                if row["actor_name"] in {"李渊", "李世民"}
            }
            assert sovereign_at_event == {"李世民": False, "李渊": True}


def test_shared_person_profile_registry_precedes_ruler_window_projection() -> None:
    source_packs = [
        json.loads(
            (ROOT / "eval/i5b_current_value" / ruler / "source-pack.json").read_text(
                encoding="utf-8"
            )
        )
        for ruler in ("李世民", "李渊", "刘邦")
    ]
    outcomes = build_unbound_historical_outcome_registry(source_packs)
    profiles = build_historical_person_profile_registry(outcomes, source_packs)

    assert profiles["declarations"]["profile_count"] == 41
    assert profiles["declarations"]["ruler_window_binding_count"] == 0
    assert profiles["declarations"]["team_projection_count"] == 0
    assert profiles["declarations"]["political_risk_projection_count"] == 0
    assert all(
        "political_risk" not in row and "team_building_projection" not in row
        for row in profiles["profiles"]
    )
    sudingfang = next(
        row for row in profiles["profiles"] if row["person"] == "苏定方"
    )
    assert sudingfang["overall_grade"] == "historic"
    assert {
        row["canonical_label"] for row in sudingfang["grade_basis_outcomes"]
    } == {
        "苏定方平西突厥战役群",
        "苏定方平都曼与葱岭战役群",
        "苏定方平百济战役群",
        "苏定方平壤道征高丽战役群",
    }
    assert len(sudingfang["talent_grade_outcome_refs"]) == 2
    lishimin = next(
        row for row in profiles["profiles"] if row["person"] == "李世民"
    )
    assert lishimin["domain_grades"]["civil_governance"]["grade"] == "ordinary"
    assert lishimin["talent_grade_exclusions"]
    assert {
        row["reason"] for row in lishimin["talent_grade_exclusions"]
    } == {"ruler_own_reign_governance"}
    assert {
        row["outcome_ref"] for row in lishimin["talent_grade_exclusions"]
    } <= set(lishimin["outcome_refs"])
    assert not (
        {
            row["outcome_ref"] for row in lishimin["talent_grade_exclusions"]
        }
        & set(lishimin["talent_grade_outcome_refs"])
    )
    rendered = render_historical_person_profile_registry_markdown(profiles)
    assert "# 人物全生涯画像总登记（未绑定皇帝窗口）" in rendered
    assert "侯君集" in rendered
    assert "高士廉" in rendered
    assert "[4 项，查看明细]" in rendered
    assert "## 完整定级依据" in rendered
    assert "苏定方平壤道征高丽战役群" in rendered
    assert "ruler_own_reign_governance" in rendered


def test_dynasty_partitions_merge_without_duplicate_public_objects() -> None:
    outcome_root = ROOT / "eval/historical_outcome_registry"
    profile_root = ROOT / "eval/historical_person_profiles"
    global_outcomes = json.loads(
        (outcome_root / "current.json").read_text(encoding="utf-8")
    )
    global_profiles = json.loads(
        (profile_root / "current.json").read_text(encoding="utf-8")
    )
    outcome_partitions = [
        json.loads((outcome_root / token / "current.json").read_text(encoding="utf-8"))
        for token in ("HAN", "TANG")
    ]
    profile_partitions = [
        json.loads((profile_root / token / "current.json").read_text(encoding="utf-8"))
        for token in ("HAN", "TANG")
    ]
    assert [row["registry_partition"] for row in outcome_partitions] == [
        "HAN",
        "TANG",
    ]
    assert [row["registry_partition"] for row in profile_partitions] == [
        "HAN",
        "TANG",
    ]
    partition_outcome_refs = [
        row["registration_ref"]
        for partition in outcome_partitions
        for row in partition["outcomes"]
    ]
    partition_person_refs = [
        row["person_ref"]
        for partition in profile_partitions
        for row in partition["profiles"]
    ]
    assert len(partition_outcome_refs) == len(set(partition_outcome_refs))
    assert len(partition_person_refs) == len(set(partition_person_refs))
    assert set(partition_outcome_refs) == {
        row["registration_ref"] for row in global_outcomes["outcomes"]
    }
    assert set(partition_person_refs) == {
        row["person_ref"] for row in global_profiles["profiles"]
    }


@pytest.mark.acceptance
def test_direct_runner_uses_the_same_markdown_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_json = tmp_path / "result.json"
    output_markdown = tmp_path / "result.md"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "i5b_current_value_runner",
            "--source-pack",
            str(ROOT / "eval/i5b_current_value/刘邦/source-pack.json"),
            "--output-json",
            str(output_json),
            "--output-markdown",
            str(output_markdown),
        ],
    )

    assert runner_main() == 0
    report = json.loads(output_json.read_text(encoding="utf-8"))
    markdown = output_markdown.read_text(encoding="utf-8")
    assert markdown == render_scoring_detail_markdown(report)
    assert "## 共享人物全生涯画像登记" not in markdown
    assert (
        "[共享人物画像总登记](../../historical_person_profiles/current.md)"
        in markdown
    )


def test_liyuan_team_table_explains_membership_and_links_shared_profiles() -> None:
    markdown = (
        ROOT / "eval/i5b_current_value/李渊/result.md"
    ).read_text(encoding="utf-8")
    team_section = markdown.split("## 团队建设", 1)[1].split("## 容人保全", 1)[0]

    assert "计入团队依据 / 风险事实" in team_section
    assert "李渊在统一战争中持续直接授予方面主帅责任" in team_section
    assert (
        "[李世民](../../historical_person_profiles/current.md"
        "#profile-pinv-637b07646a8dd7c229dc)"
    ) in team_section
    assert "## 共享人物全生涯画像登记" not in markdown
    assert "civil_governance：作为主导完成" not in team_section


def test_liyuan_appointment_uses_harmonic_decay_without_person_cap() -> None:
    report = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/李渊/source-pack.json"
    )
    appointment = next(
        row
        for row in report["material_budget"]["rules"]
        if row["rule_code"] == "appointment_delegation"
    )
    objects = {
        row["subject"]: row for row in appointment["settled_objects"]
        if row["side"] == "positive"
    }

    assert "same_object_value_cap" not in appointment
    assert Decimal(objects["李世民"]["object_aggregate_magnitude"]) == Decimal(
        "5.540013"
    )
    assert Decimal(objects["李靖"]["object_aggregate_magnitude"]) == Decimal(
        "4.261583"
    )
    assert Decimal(objects["刘文静"]["object_aggregate_magnitude"]) == Decimal(
        "2.629688"
    )
    assert (
        Decimal(objects["李世民"]["object_aggregate_magnitude"])
        > Decimal(objects["李靖"]["object_aggregate_magnitude"])
        > Decimal(objects["刘文静"]["object_aggregate_magnitude"])
    )

    pack = json.loads(
        (ROOT / "eval/i5b_current_value/李渊/source-pack.json").read_text(
            encoding="utf-8"
        )
    )
    wude_code = next(
        row
        for row in pack["outcome_registry"]["clusters"]
        if row["canonical_label"] == "武德律令编定并颁行天下"
    )
    liu_wenjing = next(
        row for row in wude_code["members"] if row["actor_name"] == "刘文静"
    )
    assert liu_wenjing["role_code"] == "governance_participant"
    assert liu_wenjing["delegated_responsibility"]["scope"] == "major_affairs"
    assert "未覆盖国家存亡或全国核心制度" in (
        liu_wenjing["delegated_responsibility"]["importance_basis"]
    )
    assert liu_wenjing["delegated_responsibility"]["appointment_effect"] == (
        "major_success"
    )
    assert liu_wenjing["delegated_responsibility"]["continuity_factor"] == (
        "short_or_one_off"
    )
    liu_material = next(
        row
        for row in appointment["settled_materials"]
        if row["subject"] == "刘文静"
        and "武德律令编定并颁行天下" in row["fact"]
    )
    assert "个人责任范围：奉诏与通识之士据开皇律令完成初期损益编修" in (
        liu_material["fact"]
    )


@pytest.mark.parametrize(
    ("ruler", "subject", "label", "importance", "effect"),
    [
        (
            "李渊",
            "李世民",
            "柏壁—介休平刘武周宋金刚战役群",
            "critical_national_or_long_term",
            "exceptional_success",
        ),
        (
            "李渊",
            "李世民",
            "洛阳—虎牢灭王世充窦建德战役群",
            "critical_national_or_long_term",
            "exceptional_success",
        ),
        (
            "李渊",
            "李靖",
            "李靖在灵州硖石击退突厥",
            "major_affairs",
            "normal_success",
        ),
        (
            "李世民",
            "房玄龄",
            "贞观五代史官修工程",
            "major_affairs",
            "major_success",
        ),
        (
            "刘邦",
            "韩信",
            "垓下灭楚终局战役群",
            "critical_national_or_long_term",
            "exceptional_success",
        ),
    ],
)
def test_appointment_importance_and_effect_use_independent_boundaries(
    ruler: str,
    subject: str,
    label: str,
    importance: str,
    effect: str,
) -> None:
    report = build_i5b_current_value(
        ROOT / "eval/i5b_current_value" / ruler / "source-pack.json"
    )
    appointment = next(
        row
        for row in report["material_budget"]["rules"]
        if row["rule_code"] == "appointment_delegation"
    )
    material = next(
        row
        for row in appointment["settled_materials"]
        if row["subject"] == subject and label in row["fact"]
    )

    assert material["factor_option_codes"]["appointment_importance"] == importance
    assert material["factor_option_codes"]["appointment_effect"] == effect
    assert "责任重要度依据：" in material["fact"]


@pytest.mark.parametrize(
    ("ruler", "person", "basis"),
    [
        (
            "李世民",
            "房玄龄",
            "李世民亲自将房玄龄署为秦王府记室参军并引为谋主",
        ),
        (
            "刘邦",
            "韩信",
            "刘邦直接拜韩信为大将并授予独立方面统军责任",
        ),
    ],
)
def test_team_tables_link_canonical_profiles_and_explain_ruler_attribution(
    ruler: str,
    person: str,
    basis: str,
) -> None:
    markdown = (
        ROOT / "eval/i5b_current_value" / ruler / "result.md"
    ).read_text(encoding="utf-8")
    team_section = markdown.split("## 团队建设", 1)[1].split("## 容人保全", 1)[0]

    assert (
        f"[{person}](../../historical_person_profiles/current.md#profile-pinv-"
        in team_section
    )
    assert basis in team_section
    assert "已通过当前皇帝窗口团队归责审阅。" not in team_section
    assert "## 共享人物全生涯画像登记" not in markdown


@pytest.mark.acceptance
def test_i5b_run_uses_current_ruler_catalog_and_can_export_detail(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    source_dir = workspace / "eval/current/ruler"
    source_dir.mkdir(parents=True)
    source = ROOT / "eval/i5b_current_value/刘邦/source-pack.json"
    (source_dir / "source-pack.json").write_bytes(source.read_bytes())
    registry_dir = workspace / "eval/outcomes"
    registry_dir.mkdir(parents=True)
    (registry_dir / "current.json").write_bytes(
        (ROOT / "eval/historical_outcome_registry/current.json").read_bytes()
    )
    (registry_dir / "刘邦-binding.json").write_bytes(
        (ROOT / "eval/historical_outcome_bindings/刘邦.json").read_bytes()
    )
    config_dir = workspace / "config"
    config_dir.mkdir()
    (config_dir / "project.yml").write_text(
        """i5b_current_value:
  rulers:
        刘邦:
          source_pack: eval/current/ruler/source-pack.json
          outcome_binding: eval/outcomes/刘邦-binding.json
          result: eval/current/ruler/result.json
historical_outcome_registry:
  current_json: eval/outcomes/current.json
  current_markdown: eval/outcomes/current.md
""",
        encoding="utf-8",
    )
    detail = tmp_path / "detail.md"

    assert eval_main([
        "i5b-run",
        "--ruler",
        "刘邦",
        "--workspace-root",
        str(workspace),
        "--detail-output",
        str(detail),
    ]) == 0
    result = json.loads(
        (source_dir / "result.json").read_text(encoding="utf-8")
    )
    assert result["source_pack_ref"] == str(Path("eval/current/ruler/source-pack.json"))
    assert str(workspace.resolve()) not in json.dumps(result, ensure_ascii=False)
    assert (source_dir / "result.md").is_file()
    assert "| 对象 | 方向 | 材料分 | 实际计入信号 |" in detail.read_text(
        encoding="utf-8"
    )


def test_i5b_run_rejects_unconfigured_ruler(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "project.yml").write_text(
        "i5b_current_value:\n  rulers: {}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="尚未进入当前 I5B 运行目录"):
        eval_main([
            "i5b-run",
            "--ruler",
            "unknown",
            "--workspace-root",
            str(tmp_path),
        ])


@pytest.mark.acceptance
def test_current_scoring_detail_export_uses_factor_values_for_settled_materials(
    tmp_path: Path,
) -> None:
    report = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/李世民/source-pack.json"
    )
    rendered = render_scoring_detail_markdown(report)

    assert "| 对象 | 方向 | 材料分 | 实际计入信号 | 因子取值 | 计分事实 |" in rendered
    assert "### 未计分支持材料" not in rendered
    assert "| 对象 | 判定 | 说明 | 事实 |" not in rendered
    assert "识才方向 1.000000" in rendered
    assert "材料分低于当前" not in rendered
    team = next(
        row for row in report["material_budget"]["rules"]
        if row["rule_code"] == "team_building"
    )
    assert all(row["political_risk"].get("basis") for row in team["negative_members"])
    assert all(row["political_risk"]["basis"] in rendered for row in team["negative_members"])

    output = tmp_path / "scoring-detail.md"
    assert eval_main([
        "i5b-scoring-detail",
        "--ruler",
        "李世民",
        "--workspace-root",
        str(ROOT),
        "--output",
        str(output),
    ]) == 0
    assert output.read_text(encoding="utf-8") == rendered


def test_scoring_detail_can_filter_one_person(tmp_path: Path) -> None:
    report = build_i5b_current_value(
        ROOT / "eval/i5b_current_value/刘邦/source-pack.json"
    )
    rendered = render_scoring_detail_markdown(report, person="周勃")

    assert "# 刘邦 / 周勃第五项B材料预算计分验证" in rendered
    assert "## 当前人物画像" in rendered
    assert "人才等级确立理由" in rendered
    assert "规则对应" in rendered
    assert "登记支撑" in rendered
    assert "config/talent-grade-v11-domain-equivalent-historic.yml#top_fallback" in rendered
    assert "## 人才等级成果登记" in rendered
    assert "campaign" in rendered
    assert "serious" in rendered
    assert "屠马邑" in rendered
    assert "屠浑都存在地名与人名断句争议" in rendered
    assert "## HistoricalEpisode" in rendered
    assert "英布 |" not in rendered
    episode_ids = report["episode_index_by_person"]["周勃"]
    assert len(episode_ids) == len(set(episode_ids))
    outcome_ids = [value for value in episode_ids if value.startswith("EP-OUTCOME-")]
    assert len(outcome_ids) >= 1
    assert all(rendered.count(outcome_id) == 1 for outcome_id in outcome_ids)

    output = tmp_path / "zhou-bo.md"
    assert eval_main([
        "i5b-scoring-detail",
        "--ruler",
        "刘邦",
        "--person",
        "周勃",
        "--workspace-root",
        str(ROOT),
        "--output",
        str(output),
    ]) == 0
    assert output.read_text(encoding="utf-8") == rendered

    with pytest.raises(ValueError, match="不存在臣子"):
        render_scoring_detail_markdown(report, person="不存在")


@pytest.mark.parametrize(
    ("ruler", "person", "relative_output"),
    [
        ("李世民", None, Path("tmp/i5b_scoring_detail/李世民/scoring-detail.md")),
        ("刘邦", "周勃", Path("tmp/i5b_scoring_detail/刘邦/persons/周勃.md")),
    ],
)
@pytest.mark.acceptance
def test_scoring_detail_output_is_optional(
    tmp_path: Path,
    ruler: str,
    person: str | None,
    relative_output: Path,
) -> None:
    workspace = tmp_path / "workspace"
    current_dir = workspace / "eval/i5b_current_value" / ruler
    current_dir.mkdir(parents=True)
    source = ROOT / "eval/i5b_current_value" / ruler / "source-pack.json"
    (current_dir / "source-pack.json").write_bytes(source.read_bytes())
    (workspace / "config").mkdir(parents=True)
    shutil.copy2(ROOT / "config/project.yml", workspace / "config/project.yml")
    registry_dir = workspace / "eval/historical_outcome_registry"
    registry_dir.mkdir(parents=True)
    shutil.copy2(
        ROOT / "eval/historical_outcome_registry/current.json",
        registry_dir / "current.json",
    )
    profile_dir = workspace / "eval/historical_person_profiles"
    profile_dir.mkdir(parents=True)
    shutil.copy2(
        ROOT / "eval/historical_person_profiles/current.json",
        profile_dir / "current.json",
    )
    binding_dir = workspace / "eval/historical_outcome_bindings"
    binding_dir.mkdir(parents=True)
    shutil.copy2(
        ROOT / "eval/historical_outcome_bindings" / f"{ruler}.json",
        binding_dir / f"{ruler}.json",
    )
    argv = [
        "i5b-scoring-detail",
        "--ruler",
        ruler,
        "--workspace-root",
        str(workspace),
    ]
    if person:
        argv.extend(("--person", person))

    assert eval_main(argv) == 0
    output = workspace / relative_output
    assert output.is_file()
    assert output.read_text(encoding="utf-8") == render_scoring_detail_markdown(
        build_i5b_current_value(source), person=person
    )


@pytest.mark.acceptance
def test_default_detail_export_rebuilds_from_source_pack_not_stale_result(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    current_dir = workspace / "eval/i5b_current_value/刘邦"
    current_dir.mkdir(parents=True)
    source = ROOT / "eval/i5b_current_value/刘邦/source-pack.json"
    (current_dir / "source-pack.json").write_bytes(source.read_bytes())
    (workspace / "config").mkdir(parents=True)
    shutil.copy2(ROOT / "config/project.yml", workspace / "config/project.yml")
    registry_dir = workspace / "eval/historical_outcome_registry"
    registry_dir.mkdir(parents=True)
    shutil.copy2(
        ROOT / "eval/historical_outcome_registry/current.json",
        registry_dir / "current.json",
    )
    profile_dir = workspace / "eval/historical_person_profiles"
    profile_dir.mkdir(parents=True)
    shutil.copy2(
        ROOT / "eval/historical_person_profiles/current.json",
        profile_dir / "current.json",
    )
    binding_dir = workspace / "eval/historical_outcome_bindings"
    binding_dir.mkdir(parents=True)
    shutil.copy2(
        ROOT / "eval/historical_outcome_bindings/刘邦.json",
        binding_dir / "刘邦.json",
    )
    (current_dir / "result.json").write_text(
        '{"ruler":"刘邦","stale":true}', encoding="utf-8"
    )
    output = tmp_path / "han-xin.md"

    assert eval_main([
        "i5b-scoring-detail",
        "--ruler",
        "刘邦",
        "--person",
        "韩信",
        "--workspace-root",
        str(workspace),
        "--output",
        str(output),
    ]) == 0
    assert "# 刘邦 / 韩信第五项B材料预算计分验证" in output.read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("ruler", ["李世民", "刘邦"])
def test_current_signals_do_not_exceed_theoretical_envelopes(ruler: str) -> None:
    report = build_i5b_current_value(
        ROOT / "eval/i5b_current_value" / ruler / "source-pack.json"
    )
    diagnostic = report["material_budget"]["amplitude_diagnostic"]

    for rule in report["material_budget"]["rules"]:
        code = rule["rule_code"]
        if code == "appointment_delegation":
            assert diagnostic["theoretical_positive_envelope"][code] is None
            assert diagnostic["theoretical_negative_envelope"][code] is None
            assert "same_object_value_cap" not in rule
            continue
        assert Decimal(rule["positive_signal"]) <= Decimal(
            diagnostic["theoretical_positive_envelope"][code]
        )
        assert Decimal(rule["negative_signal"]) <= Decimal(
            diagnostic["theoretical_negative_envelope"][code]
        )
