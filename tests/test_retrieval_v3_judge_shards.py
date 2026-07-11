from __future__ import annotations

from scripts.dev import retrieval_v3_judge_shards as tool


def sample_candidates() -> dict:
    return {
        "task_identity": {"job_code": "JOB-I5B-ZKY-DELEGATION", "rule_code": "delegation"},
        "rule": {"rule_code": "delegation"},
        "coverage_matrix": {
            "rule_code": "delegation",
            "role_families": [{"family_code": "civil_delegate", "target_min_claims": 1}],
        },
        "object_seeds": [
            {"name": "吕余庆", "aliases": [{"alias": "吕余庆", "strength": "strong"}]},
            {"name": "赵普", "aliases": [{"alias": "赵普", "strength": "strong"}]},
        ],
        "source_documents": [{"document_code": "DOC-001", "title": "宋史/fixture", "source_kind": "primary_source"}],
        "candidate_slices": [
            {
                "slice_code": "SLI-LYQ",
                "document_code": "DOC-001",
                "object_name": "吕余庆",
                "matched_role_families": ["civil_delegate"],
                "text": "太祖命吕余庆参知政事。",
            },
            {
                "slice_code": "SLI-ZP",
                "document_code": "DOC-001",
                "object_name": "赵普",
                "matched_role_families": ["civil_delegate"],
                "text": "太祖命赵普为相。",
            },
        ],
        "coverage_gaps": [],
    }


def shard_result(shard_code: str, object_name: str) -> dict:
    return {
        "shard": {"shard_code": shard_code, "object_names": [object_name]},
        "elapsed_seconds": 1.0,
        "usage": {"input_tokens": 5},
        "output_path": f"{shard_code}.json",
        "payload": {
            "status": "succeeded",
            "documents": [{"document_code": "DOC-001", "title": "宋史/fixture"}],
            "passages": [{"passage_code": "PAS-001", "document_code": "DOC-001", "slice_code": f"SLI-{object_name}"}],
            "claims": [
                {
                    "claim_code": "CLM-001",
                    "object_name": object_name,
                    "direction": "positive",
                    "source_passage_refs": ["PAS-001"],
                    "source_slice_refs": [f"SLI-{object_name}"],
                }
            ],
            "primary_bindings": [
                {
                    "claim_code": "CLM-001",
                    "rule_code": "delegation",
                    "predicate": "delegated_civil_authority",
                    "object_role": "civil_delegate",
                }
            ],
            "coverage": {"checked_objects": [object_name], "missing_core_objects": []},
            "coverage_gaps": [],
        },
    }


def test_build_judge_shards_is_object_scoped() -> None:
    shards = tool.build_judge_shards(sample_candidates(), max_objects_per_shard=1, round_index=0)

    assert [row["object_names"] for row in shards] == [["吕余庆"], ["赵普"]]
    assert all(len(row["payload"]["candidate_slices"]) == 1 for row in shards)
    assert "只判读本 shard" in tool.build_judge_shard_prompt(shards[0]["payload"])


def test_build_judge_shards_balances_by_candidate_text() -> None:
    candidates = sample_candidates()
    candidates["object_seeds"].append({"name": "曹彬", "aliases": [{"alias": "曹彬", "strength": "strong"}]})
    candidates["candidate_slices"].append(
        {
            "slice_code": "SLI-CB",
            "document_code": "DOC-001",
            "object_name": "曹彬",
            "matched_role_families": ["civil_delegate"],
            "text": "太祖命曹彬。" * 200,
        }
    )

    shards = tool.build_judge_shards(candidates, max_objects_per_shard=2, round_index=0)
    object_sets = [set(row["object_names"]) for row in shards]

    assert len(shards) == 2
    assert any("曹彬" in names and len(names) == 1 for names in object_sets)
    assert all(row["payload"]["judge_shard"]["estimated_slice_chars"] > 0 for row in shards)


def test_build_judge_shards_penalizes_alias_only_risky_slices() -> None:
    candidates = sample_candidates()
    candidates["object_seeds"].append({"name": "李文忠", "aliases": [{"alias": "曹国公", "strength": "medium"}]})
    candidates["candidate_slices"].append(
        {
            "slice_code": "SLI-LWZ-RISK",
            "document_code": "DOC-001",
            "object_name": "李文忠",
            "matched_aliases": ["曹国公"],
            "matched_alias_strengths": {"曹国公": "medium"},
            "matched_outcome_terms": ["败绩"],
            "matched_role_families": ["civil_delegate"],
            "text": "曹国公李景隆代将，连败于郑村坝、白沟河。",
        }
    )

    shards = tool.build_judge_shards(candidates, max_objects_per_shard=2, round_index=0)
    object_sets = [set(row["object_names"]) for row in shards]

    assert any(names == {"李文忠"} for names in object_sets)


def test_merge_judge_shards_rewrites_colliding_codes() -> None:
    merged = tool.merge_judge_shard_results(
        candidates=sample_candidates(),
        shard_results=[
            shard_result("JSH-R00-01", "吕余庆"),
            shard_result("JSH-R00-02", "赵普"),
        ],
        elapsed_seconds=1.5,
        usage={"input_tokens": 10},
    )

    claim_codes = [row["claim_code"] for row in merged["claims"]]
    passage_codes = [row["passage_code"] for row in merged["passages"]]
    assert merged["status"] == "succeeded"
    assert merged["_shard_count"] == 2
    assert len(set(claim_codes)) == 2
    assert len(set(passage_codes)) == 2
    assert all(code.startswith("JSH-R00-") for code in claim_codes)
    assert all(binding["claim_code"] in claim_codes for binding in merged["primary_bindings"])


def test_merge_judge_shards_repairs_evidence_span_refs_from_candidate_slices() -> None:
    candidates = sample_candidates()
    candidates["candidate_slices"].append(
        {
            "slice_code": "SLI-CORRECT",
            "document_code": "DOC-001",
            "object_name": "赵普",
            "matched_role_families": ["civil_delegate"],
            "text": "太祖命吕余庆参知政事，吕余庆奏事称旨。",
        }
    )
    result = shard_result("JSH-R00-01", "吕余庆")
    claim = result["payload"]["claims"][0]
    claim["claim_summary"] = "太祖命吕余庆参知政事，吕余庆奏事称旨。"
    claim["source_slice_refs"] = ["SLI-LYQ"]
    claim["evidence_spans"] = [
        {
            "source_slice_ref": "SLI-LYQ",
            "span_type": "outcome",
            "text": "吕余庆奏事称旨",
        }
    ]
    claim["fact_payload"] = {"source_span_refs": ["SLI-LYQ"]}

    merged = tool.merge_judge_shard_results(
        candidates=candidates,
        shard_results=[result],
        elapsed_seconds=1.0,
        usage={},
    )

    merged_claim = merged["claims"][0]
    assert merged_claim["evidence_spans"][0]["source_slice_ref"] == "SLI-CORRECT"
    assert "SLI-CORRECT" in merged_claim["source_slice_refs"]
    assert "SLI-CORRECT" in merged_claim["fact_payload"]["source_span_refs"]
    assert any(passage["slice_code"] == "SLI-CORRECT" for passage in merged["passages"])


def test_merge_judge_shards_repairs_span_refs_when_current_slice_has_no_document_code() -> None:
    candidates = sample_candidates()
    candidates["candidate_slices"][0].pop("document_code", None)
    candidates["candidate_slices"].append(
        {
            "slice_code": "SLI-CORRECT",
            "document_code": "DOC-001",
            "object_name": "吕余庆",
            "matched_role_families": ["civil_delegate"],
            "text": "吕余庆奏事称旨。",
        }
    )
    result = shard_result("JSH-R00-01", "吕余庆")
    claim = result["payload"]["claims"][0]
    claim["source_slice_refs"] = ["SLI-LYQ"]
    claim["evidence_spans"] = [{"source_slice_ref": "SLI-LYQ", "span_type": "outcome", "text": "奏事称旨"}]

    merged = tool.merge_judge_shard_results(
        candidates=candidates,
        shard_results=[result],
        elapsed_seconds=1.0,
        usage={},
    )

    assert merged["claims"][0]["evidence_spans"][0]["source_slice_ref"] == "SLI-CORRECT"


def test_merge_judge_shards_drops_unknown_source_slice_refs() -> None:
    result = shard_result("JSH-R00-01", "吕余庆")
    claim = result["payload"]["claims"][0]
    claim["source_slice_refs"] = ["SLI-LYQ", "SLI-HALLUCINATED"]
    claim["fact_payload"] = {"source_span_refs": ["SLI-LYQ", "SLI-HALLUCINATED"]}

    merged = tool.merge_judge_shard_results(
        candidates=sample_candidates(),
        shard_results=[result],
        elapsed_seconds=1.0,
        usage={},
    )

    assert merged["claims"][0]["source_slice_refs"] == ["SLI-LYQ"]
    assert merged["claims"][0]["fact_payload"]["source_span_refs"] == ["SLI-LYQ"]


def test_merge_judge_shards_infers_candidate_payload_profiles() -> None:
    result = shard_result("JSH-R00-01", "吕余庆")
    claim = result["payload"]["claims"][0]
    claim["fact_payload"] = {
        "fact_schema": "political_action_v1",
        "object": "吕余庆",
        "action_type": "任命",
        "office_or_domain": "中枢",
        "outcome": "参知政事",
        "completeness": {"same_event_chain": True},
    }
    result["payload"]["secondary_binding_candidates"] = [
        {
            "claim_code": "CLM-001",
            "rule_code": "appointment_delegation",
            "candidate_item_code": "I5B",
            "candidate_lane": "I5B.appointment_delegation",
            "hint_status": "current_rule_candidate",
            "direction": "positive",
            "candidate_payload": {"scoring_candidate": True, "usable_for_scoring_cluster": True},
        }
    ]

    merged = tool.merge_judge_shard_results(
        candidates=sample_candidates(),
        shard_results=[result],
        elapsed_seconds=1.0,
        usage={},
    )

    payload = merged["secondary_binding_candidates"][0]["candidate_payload"]
    assert payload["personnel_profile"]["person"] == "吕余庆"
    assert payload["personnel_profile"]["action_type"] == "任命"
    assert payload["personnel_profile"]["same_event_chain"] is True


def test_merge_judge_shards_filters_object_role_gaps_resolved_elsewhere() -> None:
    first = shard_result("JSH-R00-01", "吕余庆")
    first["payload"]["status"] = "needs_refinement"
    first["payload"]["coverage_gaps"] = [
        {
            "gap_type": "predicate_missing",
            "object_name": "吕余庆",
            "family_code": "civil_delegate",
            "diagnosis": "this shard missed a civil delegation claim",
        }
    ]

    merged = tool.merge_judge_shard_results(
        candidates=sample_candidates(),
        shard_results=[first, shard_result("JSH-R00-02", "赵普")],
        elapsed_seconds=1.5,
        usage={"input_tokens": 10},
    )

    assert merged["status"] == "succeeded"
    assert merged["coverage_gaps"] == []


def test_merge_judge_shards_filters_diagnosisless_object_undercoverage_when_candidate_exists() -> None:
    first = shard_result("JSH-R00-01", "吕余庆")
    first["payload"]["claims"][0]["claim_summary"] = "赵匡胤授权吕余庆处理政务。"
    first["payload"]["claims"][0]["claim_completeness"] = {
        "has_action_span": True,
        "has_object_span": True,
        "has_outcome_span": True,
        "needs_source_extension": False,
        "outcome_same_event_chain": True,
    }
    first["payload"]["primary_bindings"] = []
    first["payload"]["secondary_binding_candidates"] = [
        {
            "claim_code": "CLM-001",
            "candidate_lane": "I5B.appointment_delegation",
            "hint_status": "current_rule_candidate",
            "candidate_payload": {"personnel_profile": {"person": "吕余庆"}},
        }
    ]
    first["payload"]["coverage_gaps"] = [
        {
            "gap_type": "object_claim_undercoverage",
            "object_name": "吕余庆",
            "family_code": "appointment_delegation_material",
        }
    ]

    merged = tool.merge_judge_shard_results(
        candidates=sample_candidates(),
        shard_results=[first, shard_result("JSH-R00-02", "赵普")],
        elapsed_seconds=1.5,
        usage={"input_tokens": 10},
    )

    assert merged["coverage_gaps"] == []


def test_merge_judge_shards_keeps_actionable_object_undercoverage_diagnosis() -> None:
    first = shard_result("JSH-R00-01", "吕余庆")
    first["payload"]["claims"][0]["claim_summary"] = "赵匡胤授权吕余庆处理政务。"
    first["payload"]["claim_completeness"] = {
        "has_action_span": True,
        "has_object_span": True,
        "has_outcome_span": True,
        "needs_source_extension": False,
        "outcome_same_event_chain": True,
    }
    first["payload"]["secondary_binding_candidates"] = [
        {
            "claim_code": "CLM-001",
            "candidate_lane": "I5B.appointment_delegation",
            "hint_status": "current_rule_candidate",
            "candidate_payload": {"personnel_profile": {"person": "吕余庆"}},
        }
    ]
    first["payload"]["coverage_gaps"] = [
        {
            "gap_type": "object_claim_undercoverage",
            "object_name": "吕余庆",
            "family_code": "appointment_delegation_material",
            "diagnosis": "另有共同任务链未拆出赵普。",
            "recommended_action": "rerun_object_shard",
        }
    ]

    merged = tool.merge_judge_shard_results(
        candidates=sample_candidates(),
        shard_results=[first, shard_result("JSH-R00-02", "赵普")],
        elapsed_seconds=1.5,
        usage={"input_tokens": 10},
    )

    assert [row["gap_type"] for row in merged["coverage_gaps"]] == ["object_claim_undercoverage"]


def test_merge_judge_shards_keeps_queueable_gaps_without_blocking_status() -> None:
    first = shard_result("JSH-R00-01", "吕余庆")
    first["payload"]["status"] = "needs_refinement"
    first["payload"]["coverage_gaps"] = [
        {
            "gap_type": "negative_undercoverage",
            "object_name": "吕余庆",
            "family_code": "revoked_or_failed_delegate",
            "diagnosis": "disposition-only material needs consumer-side profile review",
        },
        {
            "gap_type": "fetch_error",
            "object_name": "",
            "family_code": "",
            "diagnosis": "HTTP Error 429",
        },
    ]

    merged = tool.merge_judge_shard_results(
        candidates=sample_candidates(),
        shard_results=[first, shard_result("JSH-R00-02", "赵普")],
        elapsed_seconds=1.5,
        usage={"input_tokens": 10},
    )

    assert merged["status"] == "succeeded"
    assert merged["coverage"]["ready_for_object_pool"] is False
    assert [row["gap_type"] for row in merged["coverage_gaps"]] == ["negative_undercoverage", "fetch_error"]


def test_merge_judge_shards_preserves_blocked_status() -> None:
    first = shard_result("JSH-R00-01", "吕余庆")
    first["payload"]["status"] = "blocked"
    first["payload"]["coverage_gaps"] = [
        {
            "gap_type": "negative_undercoverage",
            "object_name": "吕余庆",
            "family_code": "revoked_or_failed_delegate",
            "diagnosis": "blocked shard must remain blocked",
        }
    ]

    merged = tool.merge_judge_shard_results(
        candidates=sample_candidates(),
        shard_results=[first, shard_result("JSH-R00-02", "赵普")],
        elapsed_seconds=1.5,
        usage={"input_tokens": 10},
    )

    assert merged["status"] == "blocked"


def test_enrich_judge_payload_materializes_passages_from_slice_refs() -> None:
    payload = {
        "status": "succeeded",
        "claims": [
            {
                "claim_code": "CLM-001",
                "object_name": "吕余庆",
                "claim_summary": "赵匡胤授权吕余庆参与政务。",
                "direction": "positive",
                "source_slice_refs": ["SLI-LYQ"],
            }
        ],
        "primary_bindings": [],
    }

    enriched = tool.enrich_judge_payload(sample_candidates(), payload)

    assert enriched["documents"][0]["document_code"] == "DOC-001"
    assert enriched["passages"][0]["slice_code"] == "SLI-LYQ"
    assert enriched["passages"][0]["quote"].startswith("太祖命吕余庆")
    assert enriched["claims"][0]["source_passage_refs"] == [enriched["passages"][0]["passage_code"]]


def test_materialized_passage_keeps_full_candidate_slice_text() -> None:
    candidates = sample_candidates()
    long_result_text = "后续战果：" + ("北取州郡、破敌军。" * 20)
    full_text = "太祖命常遇春留督诸军，任平章政事。" + ("授权背景。" * 20) + long_result_text
    candidates["candidate_slices"][0]["slice_code"] = "SLI-CYC"
    candidates["candidate_slices"][0]["object_name"] = "常遇春"
    candidates["candidate_slices"][0]["text"] = full_text
    payload = {
        "status": "succeeded",
        "claims": [
            {
                "claim_code": "CLM-CYC",
                "object_name": "常遇春",
                "claim_summary": "朱元璋命常遇春督军并取得后续战果。",
                "direction": "positive",
                "source_slice_refs": ["SLI-CYC"],
            }
        ],
        "primary_bindings": [],
    }

    enriched = tool.enrich_judge_payload(candidates, payload)
    passage = enriched["passages"][0]

    assert len(full_text) > 120
    assert passage["quote"] == full_text
    assert passage["raw_text"] == full_text
    assert long_result_text in passage["quote"]
