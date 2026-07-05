from __future__ import annotations

from scripts.dev import retrieval_v2_judge_shards as tool


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
