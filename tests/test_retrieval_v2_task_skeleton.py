from __future__ import annotations

from scripts.dev import retrieval_v2_task_skeleton as tool


def sample_context() -> dict:
    return {
        "target_code": "TGT-I5B-ZKY",
        "emperor_name": "赵匡胤",
        "item_code": "I5B",
        "contract_code": "I5B-RETRIEVAL-V2-20260704",
        "intent_code": "INT-I5B-ZKY-DELEGATION",
        "rule_code": "delegation",
        "rule_label": "合理授权",
        "target_payload": {"period": "北宋", "title": "宋太祖"},
        "target_aliases": [
            {"alias": "赵匡胤", "alias_type": "name", "source": "seed"},
            {"alias": "太祖", "alias_type": "temple_name", "source": "manual"},
        ],
        "material_policy_payload": [{"policy_code": "person_authority_claim"}],
        "predicate_policy_payload": [{"predicate": "delegated_civil_authority"}],
        "requirement_payload": {
            "coverage_matrix": {
                "rule_code": "delegation",
                "role_families": [
                    {"family_code": "civil_delegate", "target_min_claims": 1, "required_directions": ["positive"]}
                ],
                "secondary_rule_hints": [{"rule_code": "team_building", "reason": "reuse"}],
            }
        },
        "intent_payload": {},
    }


def test_build_task_skeleton_fills_stable_contract_fields() -> None:
    skeleton = tool.build_task_skeleton(sample_context())

    assert skeleton["target_code"] == "TGT-I5B-ZKY"
    assert skeleton["rule_code"] == "delegation"
    assert skeleton["target_profile"]["primary_name"] == "赵匡胤"
    assert "太祖" in skeleton["target_profile"]["must_check_titles"]
    assert skeleton["coverage_matrix"]["role_families"][0]["family_code"] == "civil_delegate"
    assert skeleton["source_strategy"]["source_hints"] == ["宋史", "續資治通鑑長編", "資治通鑑"]
    assert "object_biographies_or_liezhuan" in skeleton["source_strategy"]["required_page_types"]
    assert skeleton["secondary_rule_candidates"] == [{"rule_code": "team_building", "reason": "reuse"}]
    assert skeleton["object_seeds"] == []
    assert skeleton["source_documents"] == []


def test_merge_taskgen_discovery_preserves_protected_fields() -> None:
    skeleton = tool.build_task_skeleton(sample_context())
    merged = tool.merge_taskgen_discovery(
        skeleton,
        {
            "target_code": "BAD",
            "rule_code": "BAD",
            "coverage_matrix": {"role_families": []},
            "target_profile": {"aliases": ["宋太祖"]},
            "rule": {"rule_code": "BAD", "keywords": ["命"]},
            "object_seeds": [{"name": "吕余庆", "aliases": [{"alias": "呂餘慶", "strength": "strong"}]}],
            "source_documents": [{"document_code": "DOC-SH-001", "title": "宋史/卷1", "text": "太祖命吕余庆。"}],
            "generation_notes": ["discovered from search"],
        },
    )

    assert merged["target_code"] == "TGT-I5B-ZKY"
    assert merged["rule_code"] == "delegation"
    assert merged["coverage_matrix"]["role_families"][0]["family_code"] == "civil_delegate"
    assert "宋太祖" in merged["target_profile"]["aliases"]
    assert merged["rule"]["keywords"] == ["命"]
    assert tool.validate_task_for_candidates(merged) == []


def test_discovery_profile_matches_rule_or_generic_target() -> None:
    context = sample_context()
    exact = {"emperor_name": "赵匡胤", "rule_code": "delegation"}
    generic = {"emperor_name": "赵匡胤"}
    wrong = {"emperor_name": "李世民", "rule_code": "delegation"}

    assert tool.profile_matches_context(exact, context) is True
    assert tool.profile_matches_context(generic, context) is True
    assert tool.profile_matches_context(wrong, context) is False
