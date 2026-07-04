from __future__ import annotations

from scripts.dev.rule_material_policy import candidate_scoring_role_from_policy, policy_map_from_rows


def test_policy_map_prefers_lower_selection_priority() -> None:
    policies = policy_map_from_rows(
        [
            {
                "item_code": "I5B",
                "rule_code": "team_building",
                "policy_code": "ordinary",
                "selection_priority": 100,
                "allowed_scoring_roles": ["ordinary_member"],
            },
            {
                "item_code": "I5B",
                "rule_code": "team_building",
                "policy_code": "special_team_policy",
                "selection_priority": 10,
                "allowed_scoring_roles": ["team_member"],
                "candidate_obj_types": ["person"],
                "require_attrs": ["talent_quality"],
            },
        ]
    )

    policy = policies["team_building"]
    assert policy.policy_code == "special_team_policy"
    assert policy.allowed_scoring_roles == frozenset({"team_member"})
    assert policy.candidate_obj_types == frozenset({"person"})
    assert policy.require_attrs == frozenset({"talent_quality"})


def test_candidate_scoring_role_uses_policy_payload_rules() -> None:
    policy = policy_map_from_rows(
        [
            {
                "item_code": "I5B",
                "rule_code": "anti_nepotism",
                "policy_code": "person_material_policy",
                "context_roles": ["mechanism_context"],
                "policy_payload": {
                    "context_roles_by_obj_type": {"mechanism": "mechanism_context"},
                    "candidate_role_rules": [
                        {"when": {"side": "positive"}, "role": "anti_nepotism_resisted_actor"},
                        {"when": {"obj_type": "person", "names": ["张易之"]}, "role": "favorite_beneficiary"},
                    ],
                    "default_scoring_roles_by_direction": {"negative": "appointment_interferer"},
                },
            }
        ]
    )["anti_nepotism"]

    assert (
        candidate_scoring_role_from_policy(policy, side="negative", obj_type="person", obj_name="张易之")
        == "favorite_beneficiary"
    )
    assert (
        candidate_scoring_role_from_policy(policy, side="positive", obj_type="person", obj_name="魏徵")
        == "anti_nepotism_resisted_actor"
    )
    assert (
        candidate_scoring_role_from_policy(policy, side="negative", obj_type="mechanism", obj_name="酷吏罗织机制")
        == "mechanism_context"
    )
