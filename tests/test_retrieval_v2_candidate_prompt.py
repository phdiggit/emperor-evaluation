from __future__ import annotations

from scripts.dev import retrieval_v2_candidate_prompt as tool


def sample_candidates() -> dict:
    return {
        "task_identity": {"rule_code": "delegation", "emperor_name": "李渊"},
        "target_profile": {"primary_name": "李渊", "aliases": ["李渊", "高祖"]},
        "rule": {"rule_code": "delegation", "keywords": ["命"]},
        "coverage_matrix": {"rule_code": "delegation", "role_families": []},
        "secondary_rule_candidates": [{"rule_code": "team_building", "reason": "reuse"}],
        "object_seeds": [
            {
                "name": "李世民",
                "aliases": [{"alias": "秦王", "strength": "medium"}],
                "role_families": ["military_delegate"],
                "predicate_candidates": ["delegated_authority"],
                "source_document_codes": ["DOC-001"],
            }
        ],
        "source_documents": [
            {
                "document_code": "DOC-001",
                "title": "旧唐书/fixture",
                "source_kind": "primary_source",
                "text_chars": 100,
                "cache_status": "hit",
                "why_selected": "verbose discovery note should be trimmed from prompt payload",
            }
        ],
        "candidate_slices": [
            {
                "slice_code": "SLI-001",
                "document_code": "DOC-001",
                "object_name": "李世民",
                "locator": "chars:0-20",
                "matched_aliases": ["秦王"],
                "matched_rule_terms": ["命"],
                "matched_outcome_terms": [],
                "matched_role_families": ["military_delegate"],
                "score": 99,
                "weak_alias_only": False,
                "merged_from_slice_codes": ["SLI-RAW"],
                "text": "高祖命秦王为西讨元帅。",
            }
        ],
    }


def test_prompt_payload_preserves_candidate_context() -> None:
    payload = tool.prompt_payload(sample_candidates())

    assert payload["object_seeds"][0]["aliases"][0]["alias"] == "秦王"
    assert payload["source_documents"][0]["why_selected"]
    assert payload["candidate_slices"][0]["score"] == 99


def test_build_prompt_keeps_budget_contract() -> None:
    prompt = tool.build_prompt(sample_candidates())

    assert "candidate_slices" in prompt
    assert "判读预算" in prompt
    assert "每个对象默认最多 2 个" in prompt
    assert '"slice_code": "SLI-001"' in prompt
