from __future__ import annotations

from scripts.dev import retrieval_v2_task_skeleton as tool


def sample_context() -> dict:
    return {
        "target_code": "TGT-I5B-ZKY",
        "emperor_name": "赵匡胤",
        "item_code": "I5B",
        "contract_code": "I5B-RETRIEVAL-V2-20260704",
        "intent_code": "INT-I5B-ZKY-APPOINTMENT-DELEGATION",
        "rule_code": "appointment_delegation",
        "rule_label": "任用授权质量",
        "target_payload": {"period": "北宋", "title": "宋太祖"},
        "target_aliases": [
            {"alias": "赵匡胤", "alias_type": "name", "source": "seed"},
            {"alias": "太祖", "alias_type": "temple_name", "source": "manual"},
        ],
        "material_policy_payload": [{"policy_code": "person_authority_claim"}],
        "predicate_policy_payload": [{"predicate": "delegated_civil_authority"}],
        "requirement_payload": {
            "coverage_matrix": {
                "rule_code": "appointment_delegation",
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
    assert skeleton["rule_code"] == "appointment_delegation"
    assert skeleton["target_profile"]["primary_name"] == "赵匡胤"
    assert "太祖" in skeleton["target_profile"]["must_check_titles"]
    assert skeleton["coverage_matrix"]["role_families"][0]["family_code"] == "civil_delegate"
    assert skeleton["source_strategy"]["source_hints"] == ["宋史", "續資治通鑑長編", "資治通鑑"]
    assert "object_biographies_or_liezhuan" in skeleton["source_strategy"]["required_page_types"]
    assert "royal_clan_delegate" in skeleton["source_strategy"]["object_discovery_families"]
    assert skeleton["secondary_rule_candidates"] == [{"rule_code": "team_building", "reason": "reuse"}]
    assert skeleton["object_seeds"] == []
    assert skeleton["source_documents"] == []


def test_default_secondary_rule_candidates_keep_future_hint_status() -> None:
    context = sample_context()
    context["requirement_payload"] = {}

    skeleton = tool.build_task_skeleton(context)
    by_rule = {row["rule_code"]: row for row in skeleton["secondary_rule_candidates"]}

    assert "tolerate_talent" in by_rule
    assert "anti_nepotism" in by_rule
    assert by_rule["central_military_power_control"]["hint_status"] == "future_rule_hint"
    assert by_rule["regional_clan_power_control"]["hint_status"] == "future_rule_hint"
    assert by_rule["inner_favorite_power_control"]["hint_status"] == "future_rule_hint"
    assert by_rule["political_character"]["hint_status"] == "future_rule_hint"


def test_item_wide_task_skeleton_uses_i5b_material_families() -> None:
    context = sample_context()
    context["rule_code"] = "i5b_item_wide"
    context["rule_label"] = "I5B item-wide material pool"
    context["requirement_payload"] = {}

    skeleton = tool.build_task_skeleton(context)
    family_codes = {row["family_code"] for row in skeleton["coverage_matrix"]["role_families"]}
    by_rule = {row["rule_code"]: row for row in skeleton["secondary_rule_candidates"]}

    assert skeleton["rule_code"] == "i5b_item_wide"
    assert "appointment_delegation_material" in family_codes
    assert "team_building_material" in family_codes
    assert "talent_discovery_material" in family_codes
    assert "tolerate_talent_material" in family_codes
    assert "anti_nepotism_material" in family_codes
    assert "future_power_character_hint" in family_codes
    assert "institution_or_office_context_pages" in skeleton["source_strategy"]["required_page_types"]
    assert "royal_clan_power_holder" in skeleton["source_strategy"]["object_discovery_families"]
    assert by_rule["appointment_delegation"]["reason"]
    assert by_rule["central_military_power_control"]["hint_status"] == "future_rule_hint"
    assert by_rule["regional_clan_power_control"]["hint_status"] == "future_rule_hint"
    assert by_rule["inner_favorite_power_control"]["hint_status"] == "future_rule_hint"


def test_item_wide_discovery_prompt_keeps_co_delegates_in_object_seeds() -> None:
    context = sample_context()
    context["rule_code"] = "i5b_item_wide"
    context["rule_label"] = "I5B item-wide material pool"
    context["requirement_payload"] = {}
    skeleton = tool.build_task_skeleton(context)

    prompt = tool.discovery_prompt(context, skeleton, allow_search=False)

    assert "I5B item-wide 可放宽到 14-26 个" in prompt
    assert "具名执行者和共同受命者" in prompt
    assert "同击、从击、使、将兵、分兵、给兵、奉使、说降、制礼" in prompt
    assert "不要只留最有名的一人" in prompt


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
    assert merged["rule_code"] == "appointment_delegation"
    assert merged["coverage_matrix"]["role_families"][0]["family_code"] == "civil_delegate"
    assert "宋太祖" in merged["target_profile"]["aliases"]
    assert merged["rule"]["keywords"] == ["命"]
    assert tool.validate_task_for_candidates(merged) == []


def test_discovery_profile_matches_rule_or_generic_target() -> None:
    context = sample_context()
    exact = {"emperor_name": "赵匡胤", "rule_code": "appointment_delegation"}
    generic = {"emperor_name": "赵匡胤"}
    wrong = {"emperor_name": "李世民", "rule_code": "appointment_delegation"}

    assert tool.profile_matches_context(exact, context) is True
    assert tool.profile_matches_context(generic, context) is True
    assert tool.profile_matches_context(wrong, context) is False
