from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest
import yaml

from emperor_v4.evaluation.battle_outcome_worklist import (
    build_battle_outcome_worklist,
    derive_person_command_index,
    load_military_settlements,
    load_ordinary_campaign_adjudications,
    load_unification_scope_adjudications,
    load_unification_tier_adjudications,
    render_battle_outcome_worklist_markdown,
)
from emperor_v4.evaluation.battle_exact_evidence import (
    build_current_battle_exact_evidence,
)
from emperor_v4.evaluation.ordinary_battle_outcome_pack import (
    build_ordinary_battle_outcome_packs,
)
from emperor_v4.evaluation.battle_parent_contract_registry import (
    TIER_BY_RESULT_CLASS,
    VALID_BATTLE_RESULT,
    VALID_LAND_AXIS,
    VALID_OBJECTIVE_COMPLETION,
    VALID_OPPONENT_CONDITION,
    VALID_OPPONENT_WEIGHT,
    _contract_row,
    _merge_unification_registry,
    _validate_external_hegemony_terminal_assessment,
    _validate_internal_independent_direction_scale,
    _validate_land_axis_basis,
    _validate_materialized_person_results,
    _validate_problem_difficulty,
    _validate_residual_opponent_result_ceiling,
    _validate_single_pole_decisive_defeat,
    build_battle_parent_contract_registry,
    render_battle_parent_contract_registry_markdown,
)
from emperor_v4.evaluation.battle_registry_store import (
    MANIFEST_SCHEMA,
    load_battle_registry,
    write_battle_registry,
)
from emperor_v4.evaluation.talent_registry_store import (
    MANIFEST_SCHEMA as TALENT_MANIFEST_SCHEMA,
    load_talent_registry,
)
from emperor_v4.evaluation.battle_adjudication_store import (
    MANIFEST_SCHEMA as ADJUDICATION_MANIFEST_SCHEMA,
    load_battle_parent_adjudications,
)
from emperor_v4.evaluation.military_talent_grade_registry import (
    _achievement,
    _capability_episode_index,
    _failure_stability_rows,
    _grade,
    _major_adverse_episode_refs,
    _net_strategic_value,
    build_military_talent_grade_registry,
    render_military_talent_grade_markdown,
    write_military_talent_grade_registry,
)
from emperor_v4.evaluation.first_item_c_registry import (
    _c2_axis,
    build_first_item_c_registry,
    render_first_item_c_registry_markdown,
    validate_first_item_c_territorial_control,
)
from emperor_v4.evaluation.first_item_a_registry import (
    build_first_item_a_registry,
    load_qin_qing_first_item_roster,
    render_first_item_a_registry_markdown,
)
from emperor_v4.evaluation.first_item_b_registry import build_first_item_b_registry
from emperor_v4.evaluation.historical_outcome_registry import (
    load_configured_dynasty_outcome_packs,
)
from emperor_v4.persistence.canonical_refs import canonical_hashed_ref


ROOT = Path(__file__).resolve().parents[1]


def test_current_battle_registry_is_verified_manifest_with_bounded_shards() -> None:
    manifest_path = ROOT / "docs/公共成果/军事/01-战役登记.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == MANIFEST_SCHEMA
    assert "records" not in manifest
    assert manifest["record_count"] == 9133
    assert manifest["bucket_count"] == 24
    assert max(
        (manifest_path.parent / entry["path"]).stat().st_size
        for entry in manifest["shards"]
    ) < 1_250_000
    payload = load_battle_registry(manifest_path)
    assert payload["schema_version"] == "battle-parent-contract-registry-v5"
    assert len(payload["records"]) == manifest["record_count"]
    assert len({row["war_event_id"] for row in payload["records"]}) == len(
        payload["records"]
    )


def test_battle_registry_store_detects_shard_tampering(tmp_path: Path) -> None:
    manifest_path = tmp_path / "registry.json"
    payload = {
        "schema_version": "test-content-v1",
        "records": [
            {"war_event_id": "WAR-A", "dynasty_partition": "a", "value": 1},
            {"war_event_id": "WAR-B", "dynasty_partition": "b", "value": 2},
        ],
        "semantic_fingerprint": "test",
    }
    manifest = write_battle_registry(manifest_path, payload, bucket_count=2)
    assert load_battle_registry(manifest_path) == payload
    shard_path = manifest_path.parent / manifest["shards"][0]["path"]
    shard_path.write_bytes(shard_path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="shard字节指纹漂移"):
        load_battle_registry(manifest_path)


def test_current_talent_registry_is_verified_manifest_with_bounded_shards() -> None:
    manifest_path = ROOT / "docs/公共成果/军事/02-武将人才等级.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == TALENT_MANIFEST_SCHEMA
    assert "profiles" not in manifest
    assert manifest["profile_count"] == 2016
    assert max(
        (manifest_path.parent / entry["path"]).stat().st_size
        for entry in manifest["shards"]
    ) < 1_000_000
    payload = load_talent_registry(manifest_path)
    assert payload["schema_version"] == "military-talent-grade-registry-v3"
    assert len(payload["profiles"]) == manifest["profile_count"]


def test_current_talent_rebuild_refuses_canonical_identity_loss() -> None:
    with pytest.raises(ValueError, match="canonical人物身份连续性"):
        write_military_talent_grade_registry(ROOT)
    payload = load_talent_registry(
        ROOT / "docs/公共成果/军事/02-武将人才等级.json"
    )
    assert len(payload["profiles"]) == 2016


def test_current_battle_parent_adjudications_use_verified_bounded_shards() -> None:
    manifest_path = ROOT / "config/battle-parent-contract-adjudications.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == ADJUDICATION_MANIFEST_SCHEMA
    assert "adjudications" not in manifest
    assert manifest["adjudication_count"] == 959
    assert max(
        (manifest_path.parent / entry["path"]).stat().st_size
        for entry in manifest["shards"]
    ) < 650_000
    payload = load_battle_parent_adjudications(manifest_path)
    assert payload["schema_version"] == "battle-parent-contract-adjudications-v1"
    assert len(payload["adjudications"]) == manifest["adjudication_count"]


def test_battle_registry_markdown_only_lists_tiered_battles_and_has_dynasty_matrix() -> None:
    payload = {
        "ordinary_candidate_count": 3,
        "ordinary_public_outcome_count": 2,
        "unification_public_outcome_count": 0,
        "post_tang_candidate_count": 0,
        "public_outcome_count": 2,
        "pending_count": 0,
        "disposition_counts": {"REGISTERED_CONTRACT": 2, "EXCLUDED_BELOW_PUBLIC_THRESHOLD": 1},
        "tier_counts": {"C": 1, "S": 1},
        "records": [
            {
                "war_event_id": "WAR-QIN-TIERED",
                "dynasty": "秦",
                "disposition": "REGISTERED_CONTRACT",
                "public_outcome_registered": True,
                "campaign_tier": "C",
                "combat_difficulty": "D1",
                "observable_result": "秦定档战役",
            },
            {
                "war_event_id": "WAR-TANG-TIERED",
                "dynasty": "唐",
                "disposition": "REGISTERED_CONTRACT",
                "public_outcome_registered": True,
                "campaign_tier": "S",
                "combat_difficulty": "D3",
                "observable_result": "唐定档战役",
            },
            {
                "war_event_id": "WAR-QIN-BELOW",
                "dynasty": "秦",
                "disposition": "EXCLUDED_BELOW_PUBLIC_THRESHOLD",
                "public_outcome_registered": False,
                "campaign_tier": None,
                "combat_difficulty": "D_NOT_REQUIRED",
                "observable_result": "门槛下战役",
            },
        ],
        "semantic_fingerprint": "test-fingerprint",
    }

    markdown = render_battle_parent_contract_registry_markdown(payload)

    assert "| 朝代 | S+ | S | S- | A | B | C | 合计 |" in markdown
    assert "| 秦 | 0 | 0 | 0 | 0 | 0 | 1 | 1 |" in markdown
    assert "| 唐 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |" in markdown
    assert "WAR-QIN-TIERED" in markdown
    assert "WAR-TANG-TIERED" in markdown
    assert "WAR-QIN-BELOW" not in markdown
    assert "秦至清 S- 以上单项/战役群清单" not in markdown


def test_resolved_person_consumption_requires_materialized_result() -> None:
    base = {
        "war_event_id": "WAR-TEST-MATERIALIZED-PERSON-RESULT",
        "public_outcome_registered": True,
        "members": [
            {
                "actor_name": "测试主帅",
                "person_command_index": {
                    "consumption_mode": "person_result",
                    "result_direction": "negative",
                    "detail_status": "resolved_person_result",
                },
            }
        ],
    }
    with pytest.raises(ValueError, match="person_result 缺少显式人物子成果"):
        _validate_materialized_person_results([base])

    base["members"][0]["person_command_index"]["consumption_mode"] = "full_parent"
    with pytest.raises(ValueError, match="负向或混合父级消费缺少显式人物子成果"):
        _validate_materialized_person_results([base])

    base["members"][0]["person_command_result"] = {
        "result_direction": "negative"
    }
    _validate_materialized_person_results([base])


def test_positive_person_result_cannot_exceed_parent_tier() -> None:
    record = {
        "war_event_id": "WAR-TEST-PERSON-TIER-CEILING",
        "public_outcome_registered": True,
        "campaign_tier": "A",
        "members": [
            {
                "actor_name": "测试主帅",
                "person_command_index": {
                    "consumption_mode": "full_parent",
                    "result_direction": "positive",
                    "projected_result_tier": "S-",
                    "detail_status": "not_required",
                },
            }
        ],
    }

    with pytest.raises(ValueError, match="正向人物成果S-不得越过父级A"):
        _validate_materialized_person_results([record])


def test_person_result_and_consumption_index_must_describe_the_same_contribution() -> None:
    record = {
        "war_event_id": "WAR-TEST-CROSS-CAMPAIGN-CONSUMPTION",
        "public_outcome_registered": True,
        "campaign_tier": "S-",
        "source_refs": ["SOURCE-CURRENT-CAMPAIGN"],
        "members": [
            {
                "actor_name": "测试主将",
                "military_capability_contribution": {
                    "capability_mode": "integrated_command",
                    "decisive_relation": "decisive_creator",
                },
                "person_command_result": {
                    "result_direction": "positive",
                    "result_tier": "S-",
                    "combat_difficulty": "D2",
                    "military_capability_contribution": {
                        "capability_mode": "integrated_command",
                        "decisive_relation": "decisive_creator",
                    },
                },
                "person_command_index": {
                    "consumption_mode": "operational_result",
                    "capability_mode": "operational_design",
                    "decisive_relation": "none",
                    "result_direction": "positive",
                    "projected_result_tier": "S-",
                    "projected_combat_difficulty": None,
                    "detail_status": "operational_direction_resolved",
                    "source_refs": ["SOURCE-OTHER-CAMPAIGN"],
                },
            }
        ],
    }

    with pytest.raises(ValueError, match="人物成果贡献轴不一致"):
        _validate_materialized_person_results([record])

    record["members"][0]["person_command_index"].update(
        {
            "capability_mode": "integrated_command",
            "decisive_relation": "decisive_creator",
        }
    )
    with pytest.raises(ValueError, match="父战役以外的史源"):
        _validate_materialized_person_results([record])


def test_military_talent_grade_uses_tier_difficulty_and_consumption_mode() -> None:
    def row(
        campaign_ref: str,
        tier: str | None,
        difficulty: str | None,
        *,
        mode: str = "full_parent",
        episode_ref: str | None = None,
        durable: bool = False,
    ) -> dict[str, object]:
        return {
            "campaign_ref": campaign_ref,
            "consumption_mode": mode,
            "result_direction": "positive",
            "campaign_tier": tier,
            "combat_difficulty": difficulty,
            "capability_episode_ref": episode_ref or campaign_ref,
            "outcome_durability": durable,
        }

    assert _grade([row("s-minus-d2", "S-", "D2")])[0] == "elite"
    assert _grade([row("s-minus-d3", "S-", "D3")])[0] == "elite"
    assert _grade([row("hard-a-1", "A", "D3"), row("hard-a-2", "A", "D3")]) == (
        "elite",
        "elite_hard_campaign_specialist",
    )
    assert _grade([
        row("hard-a-phase-1", "A", "D3", episode_ref="same-hard-operation"),
        row("hard-a-phase-2", "A", "D3", episode_ref="same-hard-operation"),
    ])[0] == "important"
    assert _grade([row("hard", "S-", "D3"), row("major", "A", "D2")])[0] == "elite"
    assert _grade([
        row("hard", "S-", "D3"),
        row("major-1", "A", "D2"),
        row("major-2", "A", "D2"),
    ])[0] == "top"
    assert _grade([
        row("hard", "S-", "D3"),
        row("major-1", "A", "D2"),
        row("major-2", "A", "D2"),
    ])[0] == "top"
    assert _grade([row("s-1", "S-", "D2"), row("s-2", "S-", "D2")])[0] == "elite"
    assert _grade([row("s", "S", "D2"), row("s-minus", "S-", "D2", durable=True)]) == (
        "top",
        "top_national_strategic_peak",
    )
    assert _grade([row("s-plus", "S+", "D3")])[0] == "top"
    assert _grade([row("stable-s", "S", "D3", durable=True)])[0] == "elite"
    assert _grade([row("s-plus", "S+", "D3"), row("major", "A", "D3")]) == (
        "historic",
        "historic_era_defining_peak",
    )
    assert _grade(
        [
            row("extreme-terminal", "S", "D4"),
            row("durable-state-terminal", "S-", "D2", durable=True),
            row("independent-major", "A", "D2"),
        ]
    )[0] == "top"
    assert _grade(
        [
            row("extreme-terminal", "S", "D4"),
            row("non-durable-terminal", "S-", "D2"),
            row("independent-major", "A", "D2"),
        ]
    )[0] == "top"
    assert _grade([row("s-d4", "S", "D4"), row("a-d2", "A", "D2")]) == (
        "top",
        "top_national_strategic_peak",
    )
    assert _grade(
        [row("s-minus-d4", "S-", "D4"), row("a-d3", "A", "D3")]
    ) == (
        "top",
        "top_hard_problem_solver",
    )
    four_major = [row(f"major-{index}", "A", "D2") for index in range(4)]
    assert _grade(four_major)[0] == "elite"
    four_major_with_hard_validation = [
        row("major-hard", "A", "D3"),
        *[row(f"major-{index}", "A", "D2") for index in range(3)],
    ]
    assert _grade(four_major_with_hard_validation) == (
        "top",
        "top_sustained_first_line_command",
    )
    assert _grade([
        row("extreme-s", "S", "D4"),
        row("hard-s-minus", "S-", "D3"),
        row("major-validation", "A", "D2"),
    ]) == ("historic", "historic_extreme_problem_solver")
    assert _grade([
        row("extreme-s", "S", "D4"),
        row("hard-s-minus", "S-", "D3"),
    ])[0] == "top"
    terminal_finishers = [
        {
            **row(f"terminal-{index}", "A", "D2"),
            "capability_mode": "tactical_execution",
            "decisive_relation": "terminal_finisher",
        }
        for index in range(4)
    ]
    assert _grade(terminal_finishers)[0] == "important"
    same_episode = [
        row("phase-1", "S-", "D3", episode_ref="one-operation"),
        row("phase-2", "A", "D2", episode_ref="one-operation"),
        row("phase-3", "A", "D2", episode_ref="one-operation"),
    ]
    assert _grade(same_episode)[0] == "elite"
    assert _grade([row("pending", None, None, mode="person_result_required")])[0] == "ordinary"
    operational_portfolio = [
        row("frontline-anchor", "S-", "D3"),
        row("strategy-1", "S", None, mode="operational_result"),
        row("strategy-2", "S-", None, mode="operational_result"),
        row("strategy-3", "S-", None, mode="operational_result"),
    ]
    assert _grade(operational_portfolio)[0] == "elite"
    assert _grade([
        row("frontline-s", "S", "D2"),
        row("independent-strategy", "S", None, mode="operational_result"),
        row("frontline-validation", "A", "D3"),
    ]) == ("top", "top_national_strategic_peak")
    assert _grade([
        row("frontline-validation", "A", "D3"),
        row("independent-strategy", "S", None, mode="operational_result"),
    ])[0] == "elite"
    assert _grade([
        row("frontline-s", "S", "D2"),
        row("independent-strategy", "S-", None, mode="operational_result"),
        row("frontline-validation", "A", "D3"),
    ])[0] == "elite"
    assert _grade([
        row("s-minus-1", "S-", "D2", durable=True),
        row("s-minus-2", "S-", "D2"),
    ])[0] == "elite"
    assert _grade([
        row("s-plus", "S+", "D2"),
        row("s-minus", "S-", "D3"),
        row("major", "A", "D3"),
    ]) == ("historic", "historic_sustained_grand_command")

    comparable_defeat = {
        "campaign_ref": "comparable-defeat",
        "consumption_mode": "person_result",
        "result_direction": "negative",
        "campaign_tier": "S-",
        "combat_difficulty": "D3",
        "parent_campaign_tier": "S+",
        "parent_combat_difficulty": "D4",
        "role_code": "commander_in_chief",
        "capability_mode": "integrated_command",
        "decisive_relation": "decisive_creator",
        "stable_delivery": False,
    }
    assert _grade([row("anchor", "S-", "D3"), row("a", "A", "D2"), comparable_defeat])[0] == "elite"
    assert _grade([
        row("anchor", "S-", "D3"),
        row("a-1", "A", "D2"),
        row("a-2", "A", "D2"),
        comparable_defeat,
    ])[0] == "top"
    comparable_mixed = {**comparable_defeat, "result_direction": "mixed_review"}
    assert _grade(
        [row("peak", "S", "D4"), row("a", "A", "D3"), comparable_mixed]
    )[0] == "top"
    three_major = [
        row("anchor", "S-", "D3"),
        row("a-1", "A", "D2"),
        row("a-2", "A", "D2"),
    ]
    assert _grade([*three_major, comparable_defeat])[0] == "top"
    secondary_defeat = {
        **comparable_defeat,
        "decisive_relation": "stage_executor",
    }
    assert _grade([*three_major, secondary_defeat])[0] == "top"
    none_relation_defeat = {
        **comparable_defeat,
        "decisive_relation": "none",
    }
    assert _grade([*three_major, none_relation_defeat])[0] == "top"
    assert _grade([
        row("anchor", "S-", "D3"), row("a-1", "A", "D2"),
        row("a-2", "A", "D2"), row("a-3", "A", "D2"), comparable_defeat,
    ])[0] == "top"

    repeated_adverse = {
        **comparable_defeat,
        "result_direction": "mixed_review",
        "campaign_tier": "A",
        "combat_difficulty": "D2",
        "parent_campaign_tier": "A",
        "parent_combat_difficulty": "D2",
    }
    # 重大败责只限制稳定性，不反写已由正向实绩成立的能力峰值。
    assert _grade(four_major_with_hard_validation + [
        {**repeated_adverse, "campaign_ref": "adverse-1"},
        {**repeated_adverse, "campaign_ref": "adverse-2"},
    ])[0] == "top"

    attributable_failures = [
        {
            "campaign_ref": f"failure-{index}",
            "campaign_tier": "A",
            "combat_difficulty": "D2",
            "responsibility": "primary",
            "severity_index": 0.7,
            "basis": "明确重大失误。",
        }
        for index in range(2)
    ]
    assert _grade(
        [
            *four_major_with_hard_validation,
            *_failure_stability_rows(
                four_major_with_hard_validation, attributable_failures
            ),
        ]
    )[0] == "top"
    war_conduct_failures = [
        {**failure, "failure_domain": "war_conduct"}
        for failure in attributable_failures
    ]
    assert _failure_stability_rows(four_major, war_conduct_failures) == []
    deduplicated_failures = _failure_stability_rows(
        four_major,
        attributable_failures,
        person="同一人物",
        episode_index={
            ("同一人物", "failure-0"): "same-failure-operation",
            ("同一人物", "failure-1"): "same-failure-operation",
        },
    )
    assert {
        row["capability_episode_ref"] for row in deduplicated_failures
    } == {"same-failure-operation"}
    adverse_context = {
        **comparable_defeat,
        "result_direction": "mixed_review",
        "campaign_tier": "A",
        "combat_difficulty": "D2",
    }
    assert _major_adverse_episode_refs(
        [
            {**adverse_context, "campaign_ref": "mixed-1"},
            {**adverse_context, "campaign_ref": "mixed-2"},
        ],
        [],
    ) == {"mixed-1", "mixed-2"}
    assert _major_adverse_episode_refs(
        [
            {
                **adverse_context,
                "campaign_ref": "mixed-phase-1",
                "capability_episode_ref": "same-adverse-context",
            },
            {
                **adverse_context,
                "campaign_ref": "mixed-phase-2",
                "capability_episode_ref": "same-adverse-context",
            },
        ],
        [],
    ) == {"same-adverse-context"}


def test_person_subresults_only_share_capability_episode_when_explicitly_adjudicated() -> None:
    record = {
        "war_event_id": "WAR-POST-ONE-PARENT",
        "source_target_ref": "CAMPAIGN-ONE-PARENT",
        "campaign_tier": "A",
        "combat_difficulty": "D3",
        "post_tang_evidence_lower_bound": True,
        "source_refs": ["source/ref"],
    }
    member = {
        "role_code": "principal_commander",
        "person_command_index": {
            "consumption_mode": "person_result",
            "capability_mode": "independent_direction",
            "decisive_relation": "co_decisive",
            "result_direction": "positive",
            "projected_result_tier": "A",
            "projected_combat_difficulty": "D3",
            "detail_status": "resolved_person_result",
        },
    }
    results = [
        {
            "result_ref": f"PCR-{index}",
            "result_label": f"阶段{index}",
            "result_direction": "positive",
            "result_tier": "A",
            "combat_difficulty": "D3",
            "capability_episode_ref": "MIL-EPISODE-SAME-DIRECTION",
            "military_capability_contribution": {
                "capability_mode": "independent_direction",
                "decisive_relation": "co_decisive",
            },
        }
        for index in (1, 2)
    ]
    achievements = [_achievement(record, member, item) for item in results]
    assert {item["capability_episode_ref"] for item in achievements} == {
        "MIL-EPISODE-SAME-DIRECTION"
    }
    assert _grade(achievements)[0] == "important"



def test_military_capability_contribution_overrides_historical_role() -> None:
    decisive_subordinate = derive_person_command_index(
        {
            "actor_ref": "PER-DECISIVE-SUBORDINATE",
            "actor_name": "实际统军者",
            "actor_kind": "person",
            "role_code": "principal_commander",
            "military_capability_contribution": {
                "capability_mode": "integrated_command",
                "decisive_relation": "decisive_creator",
                "basis": "虽非名义主帅，实际统合三军并完成终局。",
                "source_refs": ["SOURCE-1"],
            },
            "contribution_scope": "虽非名义主帅，实际统合三军并完成终局。",
        },
        campaign_tier="S",
        combat_difficulty="D3",
        battle_result="victory",
        source_refs=["SOURCE-1"],
    )
    assert decisive_subordinate["consumption_mode"] == "full_parent"
    assert decisive_subordinate["capability_mode"] == "integrated_command"
    assert decisive_subordinate["decisive_relation"] == "decisive_creator"
    assert decisive_subordinate["projected_result_tier"] == "S"
    assert decisive_subordinate["projected_combat_difficulty"] == "D3"

    nominal_commander = derive_person_command_index(
        {
            "actor_ref": "PER-NOMINAL-COMMANDER",
            "actor_name": "名义主帅",
            "actor_kind": "person",
            "role_code": "commander_in_chief",
            "military_capability_contribution": {
                "capability_mode": "nominal_only",
                "decisive_relation": "none",
                "basis": "仅有名义节制关系。",
                "source_refs": ["SOURCE-2"],
            },
            "contribution_scope": "仅有名义节制关系。",
        },
        campaign_tier="S",
        combat_difficulty="D3",
        battle_result="victory",
        source_refs=["SOURCE-2"],
    )
    assert nominal_commander["consumption_mode"] == "none"
    assert nominal_commander["capability_mode"] == "nominal_only"
    assert nominal_commander["decisive_relation"] == "none"

    direction_without_result = derive_person_command_index(
        {
            "actor_ref": "PER-DIRECTION-WITHOUT-RESULT",
            "actor_name": "仅领一路但无闭合战果者",
            "actor_kind": "person",
            "role_code": "principal_commander",
            "military_capability_contribution": {
                "capability_mode": "independent_direction",
                "decisive_relation": "none",
                "basis": "只载领军出发，未载该方向取得成果。",
                "source_refs": ["SOURCE-NO-RESULT"],
            },
        },
        campaign_tier="A",
        combat_difficulty="D3",
        battle_result="victory",
        source_refs=["SOURCE-NO-RESULT"],
        campaign_command_topology="federated_directions",
    )
    assert direction_without_result["consumption_mode"] == "none"
    assert direction_without_result["projected_result_tier"] is None
    assert direction_without_result["projected_combat_difficulty"] is None

    decisive_participant = derive_person_command_index(
        {
            "actor_ref": "PER-DECISIVE-PARTICIPANT",
            "actor_name": "有明确实绩的从攻",
            "actor_kind": "person",
            "role_code": "participant",
            "military_capability_contribution": {
                "capability_mode": "tactical_execution",
                "decisive_relation": "co_decisive",
                "basis": "身份为从攻，但实际完成可独立验收的关键突击。",
                "source_refs": ["SOURCE-PARTICIPANT"],
            },
        },
        campaign_tier="A",
        combat_difficulty="D3",
        battle_result="victory",
        source_refs=["SOURCE-PARTICIPANT"],
    )
    assert decisive_participant["consumption_mode"] == "person_result_required"
    assert decisive_participant["decisive_relation"] == "co_decisive"

    ruler_as_actual_commander = derive_person_command_index(
        {
            "actor_ref": "RULER-ACTUAL-COMMANDER",
            "actor_name": "实际指挥皇帝",
            "actor_kind": "ruler",
            "role_code": "not_in_command_chain",
            "military_capability_contribution": {
                "capability_mode": "integrated_command",
                "decisive_relation": "decisive_successor",
                "basis": "接手败局后持续控制战场并完成逆转。",
                "source_refs": ["SOURCE-3"],
            },
            "contribution_scope": "接手败局后持续控制战场并完成逆转。",
        },
        campaign_tier="S-",
        combat_difficulty="D4",
        battle_result="victory",
        source_refs=["SOURCE-3"],
        campaign_command_topology="sequential_successor_command",
    )
    assert ruler_as_actual_commander["consumption_mode"] == "full_parent"
    assert ruler_as_actual_commander["capability_mode"] == "integrated_command"
    assert ruler_as_actual_commander["decisive_relation"] == "decisive_successor"

    legacy_frontline_ruler = derive_person_command_index(
        {
            "actor_ref": "RULER-LEGACY-FRONTLINE",
            "actor_name": "旧裁决中的亲征统帅",
            "actor_kind": "ruler",
            "role_code": "commander_in_chief",
            "ruler_campaign_relation": "frontline_command",
            "talent_credit": "not_applicable",
            "contribution_scope": "亲率主力并持续控制完整战役。",
        },
        campaign_tier="A",
        combat_difficulty="D3",
        battle_result="victory",
        source_refs=["SOURCE-LEGACY-FRONTLINE"],
    )
    assert legacy_frontline_ruler["consumption_mode"] == "full_parent"
    assert legacy_frontline_ruler["capability_mode"] == "integrated_command"
    assert legacy_frontline_ruler["decisive_relation"] == "decisive_creator"

    operational_director = derive_person_command_index(
        {
            "actor_ref": "PER-OPERATIONAL-DIRECTOR",
            "actor_name": "实际统筹者",
            "actor_kind": "person",
            "role_code": "commander_in_chief",
            "military_capability_contribution": {
                "capability_mode": "operational_design",
                "decisive_relation": "none",
                "basis": "持续决定目标、时机与多方向资源，但未直接控制前线。",
                "source_refs": ["SOURCE-4"],
            },
        },
        campaign_tier="S",
        combat_difficulty="D4",
        battle_result="victory",
        source_refs=["SOURCE-4"],
    )
    assert operational_director["consumption_mode"] == "operational_result"
    assert operational_director["projected_combat_difficulty"] is None

    unrealized_operational_advice = derive_person_command_index(
        {
            "actor_ref": "PER-UNREALIZED-OPERATIONAL-ADVICE",
            "actor_name": "正确但未被采用的设计者",
            "actor_kind": "person",
            "role_code": "principal_commander",
            "talent_credit": "none",
            "military_capability_contribution": {
                "capability_mode": "operational_design",
                "decisive_relation": "none",
                "basis": "方案被否决，未转化为已实现结果。",
                "source_refs": ["SOURCE-UNREALIZED-DESIGN"],
            },
        },
        campaign_tier="S-",
        combat_difficulty="D2",
        battle_result="defeat",
        source_refs=["SOURCE-UNREALIZED-DESIGN"],
    )
    assert unrealized_operational_advice["consumption_mode"] == "none"
    assert unrealized_operational_advice["result_direction"] == "not_applicable"
    assert unrealized_operational_advice["projected_result_tier"] is None

    authorization_overrides_legacy_relation = derive_person_command_index(
        {
            "actor_ref": "RULER-AUTHORIZATION-ONLY",
            "actor_name": "仅批准既定方案的皇帝",
            "actor_kind": "ruler",
            "role_code": "not_in_command_chain",
            "ruler_campaign_relation": "operational_direction",
            "military_capability_contribution": {
                "capability_mode": "authorization_only",
                "decisive_relation": "none",
                "basis": "只批准将领提出的路线，未设计或持续控制战区行动。",
                "source_refs": ["SOURCE-AUTHORIZATION-ONLY"],
            },
        },
        campaign_tier="A",
        combat_difficulty="D3",
        battle_result="victory",
        source_refs=["SOURCE-AUTHORIZATION-ONLY"],
    )
    assert authorization_overrides_legacy_relation["consumption_mode"] == "none"
    assert authorization_overrides_legacy_relation["projected_result_tier"] is None
    assert (
        authorization_overrides_legacy_relation["projected_combat_difficulty"]
        is None
    )

    with pytest.raises(ValueError, match="军事能力贡献两轴"):
        derive_person_command_index(
            {
                "actor_ref": "PER-INVALID-NOMINAL",
                "actor_name": "错误挂名者",
                "actor_kind": "person",
                "role_code": "commander_in_chief",
                "military_capability_contribution": {
                    "capability_mode": "nominal_only",
                    "decisive_relation": "decisive_creator",
                    "basis": "纯挂名却声称制造决定性成果。",
                    "source_refs": ["SOURCE-5"],
                },
            },
            campaign_tier="S",
            combat_difficulty="D4",
            battle_result="victory",
            source_refs=["SOURCE-5"],
        )


def test_military_talent_net_value_and_markdown_show_combined_campaign_details() -> None:
    positive = [
        {
            "campaign_ref": "frontline-a",
            "canonical_label": "前线甲",
            "role_code": "commander_in_chief",
            "consumption_mode": "full_parent",
            "result_direction": "positive",
            "campaign_tier": "A",
            "combat_difficulty": "D2",
        },
        {
            "campaign_ref": "operational-s",
            "canonical_label": "统筹乙",
            "role_code": "not_in_command_chain",
            "consumption_mode": "operational_result",
            "result_direction": "positive",
            "campaign_tier": "S",
            "combat_difficulty": None,
        },
    ]
    adverse = [
        {
            "campaign_ref": "defeat-b",
            "canonical_label": "败战丙",
            "role_code": "principal_commander",
            "consumption_mode": "person_result",
            "result_direction": "negative",
            "campaign_tier": "B",
            "combat_difficulty": "D2",
        }
    ]
    assert _net_strategic_value(positive, adverse) == {
        "frontline_positive": 1.0,
        "operational_positive": 1.44,
        "command_adverse": -0.27,
        "net": 2.17,
    }
    stable_marked = [{**row, "stable_delivery": True} for row in positive]
    assert _net_strategic_value(stable_marked, adverse) == _net_strategic_value(
        positive, adverse
    )
    duplicated_episode = [
        {**positive[0], "capability_episode_ref": "same-operation"},
        {
            **positive[0],
            "campaign_ref": "frontline-a-phase-2",
            "capability_episode_ref": "same-operation",
        },
    ]
    assert _net_strategic_value(duplicated_episode, [])["frontline_positive"] == 1.0
    negative_operational = {
        "campaign_ref": "failed-operational-b",
        "consumption_mode": "operational_result",
        "result_direction": "negative",
        "campaign_tier": "B",
        "combat_difficulty": None,
    }
    assert _net_strategic_value([], [negative_operational])["net"] == -0.13
    secondary_adverse = {
        **adverse[0],
        "capability_mode": "tactical_execution",
        "decisive_relation": "stage_executor",
    }
    assert _net_strategic_value([], [secondary_adverse])["net"] == -0.11
    none_relation_adverse = {
        **adverse[0],
        "capability_mode": "integrated_command",
        "decisive_relation": "none",
    }
    assert _net_strategic_value([], [none_relation_adverse])["net"] == -0.32
    markdown = render_military_talent_grade_markdown(
        {
            "profile_count": 1,
            "identity_alias_group_count": 0,
            "grade_counts": {"important": 1},
            "profiles": [
                {
                    "dynasty": "汉",
                    "person": "测试将",
                    "military_grade": "important",
                    "net_strategic_value": 2.17,
                    "consumed_achievements": positive,
                    "negative_or_mixed_command_records": adverse,
                    "attributable_failures": [],
                }
            ],
            "registry_fingerprint": "test",
        }
    )
    assert "| 朝代 | 人物 | 档位 | 履历结构 | 净值 | 战役成果等级/难度组合 | 战役群名称/武将角色 |" in markdown
    assert "状态" not in markdown
    assert "前线+ `A/D2`" in markdown
    assert "统筹+ `S/—`" in markdown
    assert "前线− `B/D2`" in markdown
    assert "前线甲／主帅" in markdown


def test_capability_episode_registry_rejects_cross_group_duplicate() -> None:
    with pytest.raises(ValueError, match="不得进入两个能力情境"):
        _capability_episode_index(
            {
                "episodes": [
                    {
                        "episode_ref": "episode-1",
                        "person": "测试将",
                        "campaign_refs": ["campaign-1", "campaign-2"],
                    },
                    {
                        "episode_ref": "episode-2",
                        "person": "测试将",
                        "campaign_refs": ["campaign-1", "campaign-3"],
                    },
                ]
            }
        )


def test_military_seven_grade_boundaries_separate_peak_from_repeatability() -> None:
    def result(ref: str, tier: str, difficulty: str) -> dict[str, object]:
        return {
            "campaign_ref": ref,
            "capability_episode_ref": ref,
            "consumption_mode": "full_parent",
            "result_direction": "positive",
            "campaign_tier": tier,
            "combat_difficulty": difficulty,
            "role_code": "commander_in_chief",
            "capability_mode": "integrated_command",
            "decisive_relation": "decisive_creator",
        }

    assert _grade([])[0] == "ordinary"
    assert _grade([result("b", "B", "D2")])[0] == "usable"
    assert _grade([result("a-easy", "A", "D1")])[0] == "capable"
    assert _grade([result("a-hard", "A", "D2")])[0] == "important"
    assert _grade([result("strategic-peak", "S-", "D2")])[0] == "elite"
    assert _grade([
        {**result("national-peak", "S", "D2"), "outcome_durability": True},
        result("strategic-validation", "S-", "D2"),
    ])[0] == "top"
    assert _grade([
        result("hegemonic-terminal", "S+", "D3"),
        result("hard-validation", "S-", "D3"),
    ])[0] == "historic"


def test_military_talent_consumes_independent_person_results_inside_mega_war() -> None:
    result = build_military_talent_grade_registry({
        "semantic_fingerprint": "fixture",
        "records": [{
            "war_event_id": "WAR-MEGA",
            "dynasty": "唐",
            "public_outcome_registered": True,
            "canonical_label": "大型战争总链",
            "campaign_tier": "S-",
            "combat_difficulty": "D3",
            "members": [{
                "actor_name": "测试主将",
                "actor_ref": "PER-TEST",
                "actor_kind": "person",
                "role_code": "principal_commander",
                "person_command_result": [{
                    "result_ref": "WAR-PERSON-FIRST",
                    "result_label": "第一独立方向",
                    "result_direction": "positive",
                    "result_tier": "A",
                    "combat_difficulty": "D3",
                    "basis": "第一方向完成。",
                    "source_refs": ["SOURCE-1"],
                }, {
                    "result_ref": "WAR-PERSON-SECOND",
                    "result_label": "第二独立方向",
                    "result_direction": "positive",
                    "result_tier": "A",
                    "combat_difficulty": "D4",
                    "basis": "第二方向完成。",
                    "source_refs": ["SOURCE-2"],
                }],
                "person_command_index": {
                    "consumption_mode": "person_result",
                    "result_direction": "positive",
                    "projected_result_tier": "A",
                    "projected_combat_difficulty": "D4",
                },
            }],
        }],
    })
    profile = result["profiles"][0]
    assert {row["campaign_ref"] for row in profile["consumed_achievements"]} == {
        "WAR-PERSON-FIRST", "WAR-PERSON-SECOND"
    }
    assert profile["military_grade"] == "elite"


@pytest.mark.parametrize(
    ("detail_status", "result_direction"),
    [
        ("person_result_required", "positive"),
        ("failure_review_required", "negative"),
        ("failure_review_required", "mixed_review"),
    ],
)
def test_pending_person_result_status_blocks_every_talent_consumption_path(
    detail_status: str,
    result_direction: str,
) -> None:
    pending = {
        "campaign_ref": "WAR-PENDING",
        "consumption_mode": "full_parent",
        "result_direction": result_direction,
        "campaign_tier": "S+",
        "combat_difficulty": "D4",
        "role_code": "commander_in_chief",
        "capability_mode": "integrated_command",
        "decisive_relation": "decisive_creator",
        "detail_status": detail_status,
    }

    assert _grade([pending]) == (
        "ordinary",
        "no_consumable_positive_command_result",
    )
    assert _net_strategic_value(
        [pending] if result_direction == "positive" else [],
        [pending] if result_direction != "positive" else [],
    ) == {
        "frontline_positive": 0,
        "operational_positive": 0,
        "command_adverse": 0,
        "net": 0,
    }
    assert _major_adverse_episode_refs([pending], []) == set()


def test_pending_command_rows_are_reported_without_hiding_attributable_failure() -> None:
    members = []
    for name, status, direction, role in (
        ("正向待补", "person_result_required", "positive", "commander_in_chief"),
        ("负向待补", "failure_review_required", "negative", "principal_commander"),
        ("非指挥链待补", "failure_review_required", "negative", "participant"),
    ):
        members.append(
            {
                "actor_name": name,
                "actor_ref": f"PER-{name}",
                "actor_kind": "person",
                "role_code": role,
                "person_command_index": {
                    "consumption_mode": "person_result_required",
                    "result_direction": direction,
                    "projected_result_tier": "A",
                    "projected_combat_difficulty": "D3",
                    "detail_status": status,
                    "capability_mode": "integrated_command",
                    "decisive_relation": "decisive_creator",
                },
            }
        )
    result = build_military_talent_grade_registry(
        {
            "semantic_fingerprint": "pending-fixture",
            "records": [
                {
                    "war_event_id": "WAR-PENDING",
                    "dynasty": "唐",
                    "public_outcome_registered": True,
                    "canonical_label": "待补战役",
                    "campaign_tier": "A",
                    "combat_difficulty": "D3",
                    "members": members,
                    "attributable_failures": [
                        {
                            "actor_name": "负向待补",
                            "campaign_ref": "WAR-PENDING",
                            "campaign_tier": "A",
                            "combat_difficulty": "D3",
                            "responsibility": "primary",
                            "failure_domain": "command_failure",
                            "severity_index": 0.8,
                            "basis": "独立负面归责。",
                        }
                    ],
                }
            ],
        }
    )
    by_name = {profile["person"]: profile for profile in result["profiles"]}

    for name in ("正向待补", "负向待补"):
        profile = by_name[name]
        assert profile["grade_status"] == "lower_bound_pending_person_result"
        assert len(profile["pending_person_command_results"]) == 1
        assert profile["consumed_achievements"] == []
        assert profile["negative_or_mixed_command_records"] == []
        assert profile["capability_episode_anchors"] == []
        assert profile["net_strategic_value"] == 0
    assert by_name["非指挥链待补"]["pending_person_command_results"] == []
    assert _failure_stability_rows(
        by_name["负向待补"]["pending_person_command_results"],
        by_name["负向待补"]["attributable_failures"],
    )


def test_federated_losing_side_does_not_inherit_parent_victory() -> None:
    index = derive_person_command_index(
        {
            "actor_kind": "person",
            "actor_name": "败方统帅",
            "actor_ref": "PER-LOSING-SIDE",
            "role_code": "principal_commander",
            "contribution_scope": "所属一方的战略目标失败。",
            "command_result_direction": "negative",
        },
        campaign_tier="A",
        combat_difficulty="D3",
        battle_result="victory",
        source_refs=["SOURCE"],
        campaign_command_topology="federated_directions",
    )

    assert index["result_direction"] == "negative"
    assert index["consumption_mode"] == "person_result_required"
    assert index["projected_result_tier"] is None
    assert index["detail_status"] == "failure_review_required"


def test_non_ruler_strategic_director_consumes_operational_result() -> None:
    index = derive_person_command_index(
        {
            "actor_kind": "person",
            "actor_name": "事实最高军事决策者",
            "actor_ref": "PER-STRATEGIC-DIRECTOR",
            "role_code": "not_in_command_chain",
            "contribution_scope": "密定主攻路线、疑兵方向与阶段目标。",
            "strategic_command_relation": "operational_direction",
        },
        campaign_tier="S-",
        combat_difficulty="D3",
        battle_result="victory",
        source_refs=["SOURCE"],
        campaign_command_topology="single_integrated_command",
    )

    assert index["consumption_mode"] == "operational_result"
    assert index["command_scope"] == "operational_strategy"
    assert index["result_direction"] == "positive"
    assert index["projected_result_tier"] == "S-"
    assert index["projected_combat_difficulty"] is None


def test_current_zhu_quanzhong_keeps_top_without_losing_side_false_positive() -> None:
    payload = load_talent_registry(
        ROOT / "docs/公共成果/军事/02-武将人才等级.json"
    )
    profile = next(row for row in payload["profiles"] if row["person"] == "朱全忠")
    assert profile["military_grade"] == "top"
    assert "WAR-LEAD-257-WEIBO-END" not in {
        row["campaign_ref"] for row in profile["consumed_achievements"]
    }
    weibo_failure = next(
        row
        for row in profile["negative_or_mixed_command_records"]
        if row["campaign_ref"] == "WAR-LEAD-257-WEIBO-END"
    )
    assert weibo_failure["result_direction"] == "negative"
    assert weibo_failure["campaign_tier"] == "B"
    assert "WAR-LEAD-265-WEIBO-END" not in {
        row["campaign_ref"]
        for row in profile["negative_or_mixed_command_records"]
    }


def test_current_operational_direction_requires_actual_control_and_consumes_signed_result() -> None:
    battles = load_battle_registry(
        ROOT / "docs/公共成果/军事/01-战役登记.json"
    )
    operational = [
        (record, member)
        for record in battles["records"]
        for member in record.get("members") or ()
        if member.get("ruler_campaign_relation") == "operational_direction"
        or member.get("strategic_command_relation") == "operational_direction"
    ]
    control_markers = (
        "统筹", "统摄", "统合", "部署", "分兵", "分路", "两路", "三路",
        "四路", "五路", "多路", "路线", "方向", "主攻",
        "疑兵", "会攻", "追击", "回援", "围堵", "守城", "求援", "缓战",
        "撤军", "班师", "退屯", "藏旗", "议和", "节奏", "调度", "奏报式",
        "亲征", "亲总兵", "亲自组织", "持续", "阶段", "增发", "屯田",
    )
    assert operational
    for record, member in operational:
        index = member.get("person_command_index") or {}
        if index.get("capability_mode") == "operational_design":
            assert index.get("consumption_mode") == "operational_result", record[
                "war_event_id"
            ]
            assert index.get("projected_combat_difficulty") is None
        else:
            assert index.get("consumption_mode") in {
                "person_result",
                "person_result_required",
            }, record["war_event_id"]
        assert any(
            marker in str(member.get("contribution_scope") or "")
            for marker in control_markers
        ), record["war_event_id"]

    forbidden = {
        ("WAR-LEAD-TANG-LI-JINGYE-684", "武则天"),
        ("WAR-LEAD-TANG-KHITAN-697", "武则天"),
        ("WAR-LEAD-HAN-YELLOW-TURBAN-184", "刘宏"),
        ("WAR-LEAD-SG-WEI-LIAODONG-238", "曹叡"),
        ("WAR-PARENT-NC-HUAN-TIANSHENG-487-488", "萧赜"),
    }
    assert not forbidden & {
        (str(record["war_event_id"]), str(member["actor_name"]))
        for record, member in operational
    }


def test_current_net_values_are_auxiliary_sorted_values_not_grade_shortcuts() -> None:
    payload = load_talent_registry(
        ROOT / "docs/公共成果/军事/02-武将人才等级.json"
    )
    profiles = payload["profiles"]
    values = [profile["net_strategic_value"] for profile in profiles]
    assert values == sorted(values, reverse=True)
    by_name = {profile["person"]: profile for profile in profiles}

    assert by_name["刘裕"]["military_grade"] == "top"
    assert by_name["朱全忠"]["military_grade"] == "top"
    assert by_name["李光弼"]["military_grade"] == "top"
    assert by_name["郭子仪"]["military_grade"] == "elite"
    assert by_name["霍去病"]["military_grade"] == "top"
    assert by_name["刘裕"]["net_strategic_value"] > by_name["朱全忠"][
        "net_strategic_value"
    ]
    assert by_name["朱全忠"]["net_strategic_value"] > by_name["李光弼"][
        "net_strategic_value"
    ]
    assert by_name["武则天"]["military_grade"] == "ordinary"
    assert by_name["武则天"]["net_strategic_value"] == 0
    assert by_name["武则天"]["consumed_achievements"] == []
    assert "武曌" not in by_name
    for canonical, alias in (
        ("李国昌", "朱邪赤心"),
        ("李光颜", "阿跌光颜"),
        ("元宏", "拓跋宏"),
        ("高长恭", "兰陵王"),
    ):
        assert alias not in by_name
        assert alias in by_name[canonical]["name_aliases"]
    for canonical, aliases in {
        "铁木真": {"铁木真", "成吉思汗", "蒙古太祖"},
        "完颜阿骨打": {"完颜阿骨打", "阿骨打"},
        "耶律阿保机": {"耶律阿保机", "阿保机"},
        "耶律斜轸": {"耶律斜轸", "斜轸"},
        "朱棣": {"燕王朱棣", "明成祖朱棣"},
    }.items():
        assert aliases <= set(by_name[canonical]["name_aliases"])
        assert not (aliases - {canonical}) & set(by_name)
    for canonical, alias in {
        "完颜晟": "金太宗",
        "赵光义": "宋太宗赵光义",
        "耶律宗真": "辽兴宗耶律宗真",
        "朱瞻基": "明宣宗朱瞻基",
        "朱祁镇": "明英宗朱祁镇",
    }.items():
        assert canonical in by_name
        assert alias not in by_name
        assert alias in by_name[canonical]["name_aliases"]
    for cross_period_name, expected_dynasties in {
        "高颎": {"隋", "南北朝"},
        "叔孙建": {"两晋", "南北朝"},
            "吴汉": {"东汉"},
            "来歙": {"东汉"},
            "梁习": {"东汉", "三国"},
        "杜慧度": {"两晋", "南北朝"},
        "檀道济": {"两晋", "南北朝"},
        "于仲文": {"南北朝", "隋"},
        "虞庆则": {"南北朝", "隋"},
        "长孙晟": {"南北朝", "隋"},
            "张既": {"东汉", "三国"},
        "冯盎": {"隋", "唐"},
        "洗夫人": {"南北朝", "隋"},
        "李世民": {"隋", "唐"},
        "杨广": {"南北朝", "隋"},
    }.items():
        matches = [profile for profile in profiles if profile["person"] == cross_period_name]
        assert len(matches) == 1
        assert set(matches[0]["dynasty_aliases"]) == expected_dynasties


def test_current_battle_registry_drives_military_talent_grades_directly() -> None:
    battle_registry = load_battle_registry(
        ROOT / "docs/公共成果/军事/01-战役登记.json"
    )

    identity_registry = yaml.safe_load(
        (ROOT / "config/historical-entity-identities.yml").read_text(
            encoding="utf-8"
        )
    )
    result = build_military_talent_grade_registry(
        battle_registry,
        identity_registry=identity_registry,
        capability_episode_registry=json.loads(
            (ROOT / "config/military-capability-episodes.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    profiles = {
        (profile["dynasty"], profile["person"]): profile
        for profile in result["profiles"]
    }

    assert result["source_registry_fingerprint"] == battle_registry[
        "semantic_fingerprint"
    ]
    assert result["supersedes_prior_military_talent_grades"] is True
    assert result["profile_count"] == len(profiles)
    assert profiles[("汉", "韩信")]["military_grade"] == "historic"
    assert profiles[("东汉", "耿弇")]["military_grade"] == "elite"
    assert profiles[("东汉", "马成")]["military_grade"] == "elite"
    assert profiles[("唐", "王雄诞")]["military_grade"] == "elite"
    assert profiles[("唐", "钱镠")]["military_grade"] == "elite"
    assert profiles[("东汉", "冯异")]["military_grade"] == "important"
    assert profiles[("唐", "李靖")]["military_grade"] == "historic"
    assert next(
        profile for profile in result["profiles"] if profile["person"] == "李世民"
    )["military_grade"] == "historic"
    liu_yu = profiles[("两晋", "刘裕")]
    assert liu_yu["military_grade"] == "top"
    assert liu_yu["rule_path"] == "top_national_strategic_peak"
    liu_yu_achievements = {
        row["campaign_ref"]: row for row in liu_yu["consumed_achievements"]
    }
    assert liu_yu_achievements["WAR-LEAD-115-HUAN-REMNANTS-410"][
        "campaign_tier"
    ] == "S-"
    assert liu_yu_achievements["WAR-LEAD-116-LUXUN-END-411"][
        "combat_difficulty"
    ] == "D4"
    assert liu_yu_achievements["WAR-LEAD-116-LIUYU-SHU-413"][
        "consumption_mode"
    ] == "operational_result"
    cao_cao = next(profile for profile in result["profiles"] if profile["person"] == "曹操")
    assert set(cao_cao["dynasty_aliases"]) == {"汉", "东汉"}
    assert len(cao_cao["actor_ref_aliases"]) >= 2
    liu_bei_profiles = [
        profile for profile in result["profiles"] if profile["person"] == "刘备"
    ]
    assert len(liu_bei_profiles) == 1
    liu_bei = liu_bei_profiles[0]
    assert liu_bei["dynasty_aliases"] == ["汉", "东汉", "三国"]
    assert liu_bei["military_grade"] == "elite"
    assert any(
        row["campaign_ref"] == "WAR-LEAD-SG-WU-HAN-YILING-221-222"
        for row in liu_bei["negative_or_mixed_command_records"]
    )
    expected_top = {
        "慕容垂",
        "李勣",
        "苏定方",
        "卫青",
        "陶侃",
        "石勒",
        "王翦",
        "杨素",
        "慕容皝",
        "李克用",
    }
    assert expected_top.issubset({
        profile["person"]
        for profile in result["profiles"]
        if profile["military_grade"] in {"top", "historic"}
    })
    assert profiles[("汉", "刘邦")]["military_grade"] == "elite"
    assert profiles[("南北朝", "宇文泰")]["military_grade"] == "top"
    allowed_high_tier_paths = {
        "historic": {
            "historic_era_defining_peak",
            "historic_extreme_problem_solver",
            "historic_sustained_grand_command",
        },
        "top": {
            "top_national_strategic_peak",
            "top_hard_problem_solver",
            "top_sustained_first_line_command",
            "historic_blocked_by_repeated_major_failures",
            "historic_blocked_by_failure_pressure",
        },
        "elite": {
            "elite_strategic_peak",
            "elite_hard_campaign_specialist",
            "elite_reliable_major_command",
            "top_blocked_by_failure_pressure",
        },
    }
    for grade, allowed_paths in allowed_high_tier_paths.items():
        actual_paths = {
            profile["rule_path"]
            for profile in result["profiles"]
            if profile["military_grade"] == grade
        }
        assert actual_paths <= allowed_paths
    zhu_quanzhong = next(
        profile for profile in result["profiles"] if profile["person"] == "朱全忠"
    )
    bianyun_episode_refs = {
        row["capability_episode_ref"]
        for row in zhu_quanzhong["consumed_achievements"]
        if row["campaign_ref"]
        in {"WAR-LEAD-259-XUBIAN-END", "WAR-LEAD-261-BIANYUN-END"}
    }
    assert bianyun_episode_refs == {"MIL-EPISODE-ZHUQUANZHONG-BIANYUN-887-897"}
    expected_important = {"姚兴", "李建成"}
    assert expected_important.issubset(
        {
            profile["person"]
            for profile in result["profiles"]
            if profile["military_grade"] == "important"
        }
    )
    assert profiles[("东汉", "张辽")]["military_grade"] == "elite"
    assert profiles[("南北朝", "段韶")]["military_grade"] == "elite"

    yuwen_yong = profiles[("南北朝", "宇文邕")]
    assert yuwen_yong["military_grade"] == "elite"
    yuwen_yong_terminal = next(
        row
        for row in yuwen_yong["consumed_achievements"]
        if row["campaign_ref"] == "WAR-LEAD-NC-ZHOU-DESTROY-QI-577"
    )
    assert (
        yuwen_yong_terminal["campaign_tier"],
        yuwen_yong_terminal["combat_difficulty"],
    ) == ("S", "D3")

    pei_xingjian = profiles[("唐", "裴行俭")]
    assert pei_xingjian["military_grade"] == "important"
    assert any(
        row["campaign_ref"] == "CAMPAIGN-TANG-PEIXINGJIAN-TURK-679-681"
        and row["campaign_tier"] == "A"
        and row["combat_difficulty"] == "D3"
        for row in pei_xingjian["consumed_achievements"]
    )

    wang_zhongsi = profiles[("唐", "王忠嗣")]
    assert any(
        row["campaign_ref"] == "PCR-TANG-WANGZHONGSI-TURK-FLANKS-742-744"
        and row["campaign_tier"] == "A"
        and row["combat_difficulty"] == "D2"
        for row in wang_zhongsi["consumed_achievements"]
    )

    hulu_guang = profiles[("南北朝", "斛律光")]
    assert any(
        row["campaign_ref"] == "PCR-NC-HULVGUANG-MANGSHAN-RIGHT-564"
        and row["campaign_tier"] == "B"
        and row["combat_difficulty"] == "D3"
        for row in hulu_guang["consumed_achievements"]
    )

    liu_yuanjing = profiles[("南北朝", "柳元景")]
    assert next(
        row
        for row in liu_yuanjing["consumed_achievements"]
        if row["campaign_ref"]
        == "PCR-AUDIT-WAR-LEAD-NC-YIXUAN-ZANGZHI-454-柳元景"
    )["decisive_relation"] == "co_decisive"

    shi_hu = profiles[("两晋", "石虎")]
    assert next(
        row
        for row in shi_hu["consumed_achievements"]
        if row["campaign_ref"]
        == "PCR-AUDIT-JIN-LATER-ZHAO-YANCI-319-321-石虎"
    )["decisive_relation"] == "co_decisive"
    li_guangbi = profiles[("唐", "李光弼")]
    assert {
        row["campaign_ref"] for row in li_guangbi["consumed_achievements"]
    } == {
        "WAR-PERSON-TANG-LIGUANGBI-CHANGSHAN-755-756",
        "WAR-PERSON-TANG-LIGUANGBI-JIASHAN-756",
        "WAR-PERSON-TANG-LIGUANGBI-TAIYUAN-757",
        "WAR-PERSON-TANG-LIGUANGBI-HEYANG-HUAIZHOU-759-760",
    }
    su_dingfang = profiles[("唐", "苏定方")]
    baekje = next(
        row
        for row in su_dingfang["consumed_achievements"]
        if row["campaign_ref"] == "WAR-LEAD-TANG-BAEKJE-663"
    )
    assert baekje["campaign_tier"] == "S-"
    assert baekje["combat_difficulty"] == "D3"
    assert baekje["consumption_mode"] == "person_result"
    assert baekje["capability_mode"] == "integrated_command"
    assert baekje["decisive_relation"] == "decisive_creator"
    assert su_dingfang["military_grade"] == "historic"
    assert su_dingfang["rule_path"] == "historic_extreme_problem_solver"
    assert next(
        profile for profile in result["profiles"] if profile["person"] == "公孙瓒"
    )["military_grade"] == "important"
    assert profiles[("三国", "司马懿")]["military_grade"] == "important"
    assert profiles[("三国", "邓艾")]["military_grade"] == "elite"
    murong_chui_profiles = [
        profile for profile in result["profiles"] if profile["person"] == "慕容垂"
    ]
    assert len(murong_chui_profiles) == 1
    assert murong_chui_profiles[0]["name_aliases"] == ["慕容垂", "慕容霸"]
    liu_xiu_profiles = [
        profile for profile in result["profiles"] if profile["person"] == "刘秀"
    ]
    assert len(liu_xiu_profiles) == 1
    assert liu_xiu_profiles[0]["dynasty_aliases"] == ["汉", "东汉"]
    assert liu_xiu_profiles[0]["military_grade"] == "top"
    assert liu_xiu_profiles[0]["rule_path"] == "top_national_strategic_peak"
    assert any(
        failure["campaign_ref"] == "HAN-STARTUP-CENTRAL-25-26"
        and failure["responsibility"] == "primary"
        and failure["failure_impact_tier"] == "A"
        for failure in liu_xiu_profiles[0]["attributable_failures"]
    )
    assert any(
        row["campaign_ref"] == "WAR-LEAD-XIN-COLLAPSE-23"
        and row["canonical_label"] == "昆阳之战"
        and row["campaign_tier"] == "S-"
        and row["combat_difficulty"] == "D4"
        for row in liu_xiu_profiles[0]["consumed_achievements"]
    )
    assert all(
        next(
            profile
            for profile in result["profiles"]
            if profile["person"] == name
        )["grade_status"] == "current_battle_registry_grade"
        for name in ("霍去病", "陆逊", "谢玄", "周亚夫", "司马懿")
    )
    li_shimin = next(
        profile for profile in result["profiles"] if profile["person"] == "李世民"
    )
    assert not {
        "WAR-LEAD-TANG-KUCHA-648",
        "WAR-LEAD-TANG-WEISHUI-626",
        "WAR-LEAD-TANG-YANQI-644",
    } & {
        row["campaign_ref"]
        for row in li_shimin["negative_or_mixed_command_records"]
    }
    assert any(
        row["campaign_ref"] == "WAR-PERSON-TANG-LISHIMIN-TURK-624"
        and row["result_direction"] == "positive"
        for row in li_shimin["consumed_achievements"]
    )
    assert profiles[("汉", "卫青")]["grade_status"] == "current_battle_registry_grade"
    resolved_person_results = {
        achievement["campaign_ref"]: achievement
        for profile in result["profiles"]
        for achievement in profile["consumed_achievements"]
        if achievement["consumption_mode"] == "person_result"
    }
    assert resolved_person_results["WAR-LEAD-261-QINGKOU-END"][
        "combat_difficulty"
    ] == "D3"
    assert resolved_person_results["WAR-LEAD-263-FENGXIANG-END"][
        "campaign_tier"
    ] == "A"
    assert resolved_person_results["WAR-LEAD-264-PINGLU-END"][
        "campaign_tier"
    ] == "S-"
    assert all(
        achievement["consumption_mode"]
        in {
            "full_parent",
            "scoped_projection",
            "joint_parent",
            "person_result",
            "operational_result",
        }
        for profile in result["profiles"]
        for achievement in profile["consumed_achievements"]
    )


def test_external_hegemony_order_reshaping_requires_s_plus_hard_path() -> None:
    prewar_assessment = {
        "sustained_core_pressure": True,
        "national_security_order_reoriented": True,
        "existential_capability": True,
        "basis": "战前已持续压迫核心疆域并具存亡级威胁。",
    }
    assessment = {
        "ruling_structure_collapsed": True,
        "security_order_persistently_reversed": True,
        "basis": "外部霸权统治结构崩解且本国安全秩序被持久逆转。",
    }
    with pytest.raises(ValueError, match="外部霸权终局事实与结果类别矛盾"):
        _validate_external_hegemony_terminal_assessment(
            war_event_id="WAR-TEST-EXTERNAL-HEGEMONY",
            fields={
                "result_class": "single_pole_or_state_terminal",
                "opponent_strategic_weight": "external_hegemony",
                "battle_result": "victory",
                "objective_completion": "complete",
            },
            assessment=assessment,
            prewar_assessment=prewar_assessment,
        )
    _validate_external_hegemony_terminal_assessment(
        war_event_id="WAR-TEST-EXTERNAL-HEGEMONY",
        fields={
            "result_class": "external_hegemony_terminal",
            "opponent_strategic_weight": "external_hegemony",
            "battle_result": "victory",
            "objective_completion": "complete",
        },
        assessment=assessment,
        prewar_assessment=prewar_assessment,
    )


def test_external_hegemony_core_destruction_is_at_least_d3_problem() -> None:
    fields = {
        "result_class": "external_hegemony_terminal",
        "opponent_strategic_weight": "external_hegemony",
        "battle_result": "victory",
        "objective_completion": "complete",
        "combat_difficulty": "D2",
    }
    with pytest.raises(ValueError, match="不得因执行顺利降至D2以下"):
        _validate_problem_difficulty(
            war_event_id="WAR-TEST-HEGEMONY-CLEAN-VICTORY",
            fields=fields,
        )
    _validate_problem_difficulty(
        war_event_id="WAR-TEST-HEGEMONY-CLEAN-VICTORY",
        fields={**fields, "combat_difficulty": "D3"},
    )


def test_external_hegemony_decisive_defeat_requires_destroyed_main_force() -> None:
    prewar_assessment = {
        "sustained_core_pressure": True,
        "national_security_order_reoriented": True,
        "existential_capability": True,
        "basis": "战前已持续压迫核心疆域并具存亡级威胁。",
    }
    assessment = {
        "ruling_structure_collapsed": False,
        "security_order_persistently_reversed": False,
        "basis": "王庭主力被击溃，但统治结构仍存且安全秩序尚未持久逆转。",
    }
    with pytest.raises(ValueError, match="必须至少摧毁当次方向主力"):
        _validate_external_hegemony_terminal_assessment(
            war_event_id="WAR-TEST-EXTERNAL-HEGEMONY-DEFEAT",
            fields={
                "result_class": "external_hegemony_decisive_defeat",
                "opponent_strategic_weight": "external_hegemony",
                "opponent_force_effect": "major_degradation",
                "battle_result": "victory",
                "objective_completion": "complete",
            },
            assessment=assessment,
            prewar_assessment=prewar_assessment,
        )
    _validate_external_hegemony_terminal_assessment(
        war_event_id="WAR-TEST-EXTERNAL-HEGEMONY-DEFEAT",
        fields={
            "result_class": "external_hegemony_decisive_defeat",
            "opponent_strategic_weight": "external_hegemony",
            "opponent_force_effect": "main_force_destroyed",
            "battle_result": "victory",
            "objective_completion": "complete",
        },
        assessment=assessment,
        prewar_assessment=prewar_assessment,
    )

    with pytest.raises(ValueError, match="缺少战前身份裁定"):
        _validate_external_hegemony_terminal_assessment(
            war_event_id="WAR-TEST-EXTERNAL-HEGEMONY-PREWAR",
            fields={
                "result_class": "external_hegemony_decisive_defeat",
                "opponent_strategic_weight": "external_hegemony",
                "opponent_force_effect": "main_force_destroyed",
                "battle_result": "victory",
                "objective_completion": "complete",
            },
            assessment=assessment,
        )


def test_external_hegemony_identity_requires_prewar_assessment_at_every_tier() -> None:
    fields = {
        "result_class": "important_objective",
        "opponent_strategic_weight": "external_hegemony",
        "opponent_force_effect": "limited_attrition",
        "battle_result": "victory",
        "objective_completion": "partial",
    }
    with pytest.raises(ValueError, match="外部霸权对手缺少战前身份裁定"):
        _validate_external_hegemony_terminal_assessment(
            war_event_id="WAR-TEST-EXTERNAL-HEGEMONY-LOW-TIER",
            fields=fields,
            assessment=None,
        )

    _validate_external_hegemony_terminal_assessment(
        war_event_id="WAR-TEST-EXTERNAL-HEGEMONY-LOW-TIER",
        fields=fields,
        assessment=None,
        prewar_assessment={
            "sustained_core_pressure": True,
            "national_security_order_reoriented": True,
            "existential_capability": True,
            "basis": "小规模战役不改变对手在开战前已经闭合的霸权身份。",
        },
    )

    with pytest.raises(ValueError, match="必须面对external_hegemony对手"):
        _validate_external_hegemony_terminal_assessment(
            war_event_id="WAR-TEST-EXTERNAL-HEGEMONY-WRONG-OPPONENT",
            fields={
                **fields,
                "result_class": "external_hegemony_decisive_defeat",
                "opponent_strategic_weight": "external_state",
            },
            assessment=None,
        )


def test_residual_opponent_cannot_be_promoted_by_complete_terminal_wording() -> None:
    with pytest.raises(ValueError, match="残余对手不得仅凭完整收束登记为S-以上"):
        _validate_residual_opponent_result_ceiling(
            war_event_id="WAR-TEST-RESIDUAL-TERMINAL",
            fields={
                "result_class": "independent_direction",
                "opponent_condition": "residual",
                "battle_result": "victory",
                "objective_completion": "complete",
            },
        )


def test_internal_independent_direction_requires_regional_scale() -> None:
    fields = {
        "result_class": "independent_direction",
        "opponent_strategic_weight": "regional_major",
        "battle_result": "victory",
        "objective_completion": "complete",
    }
    _validate_internal_independent_direction_scale(
        war_event_id="WAR-TEST-REGIONAL-DIRECTION",
        fields=fields,
    )
    with pytest.raises(ValueError, match="至少达到区域主要对手"):
        _validate_internal_independent_direction_scale(
            war_event_id="WAR-TEST-MINOR-RESTORATION",
            fields={**fields, "opponent_strategic_weight": "minor"},
        )


def test_high_tier_land_axis_cannot_be_derived_from_administrative_unit_count() -> None:
    with pytest.raises(ValueError, match="土地轴说明与结构字段不一致"):
        _validate_land_axis_basis(
            war_event_id="WAR-TEST-LAND-MISMATCH",
            fields={
                "campaign_tier": "A",
                "land_strategic_value": "strategic_gateway",
                "campaign_tier_basis": "土地轴=local_point；仅摧毁一处敌方据点。",
            },
        )

    with pytest.raises(ValueError, match="仅列行政单位数量"):
        _validate_land_axis_basis(
            war_event_id="WAR-TEST-LAND-COUNT",
            fields={
                "campaign_tier": "S-",
                "campaign_tier_basis": "攻取十二州，形成独立区域终局。",
            },
        )

    _validate_land_axis_basis(
        war_event_id="WAR-TEST-LAND-FUNCTION",
        fields={
            "campaign_tier": "S-",
            "campaign_tier_basis": (
                "十二州仅作范围定位；该区域形成可持续征兵、征税、"
                "供粮和驻军的连片军政基地。"
            ),
        },
    )
def test_single_pole_decisive_defeat_requires_first_tier_destroyed_main_force() -> None:
    valid = {
        "result_class": "single_pole_decisive_defeat",
        "opponent_strategic_weight": "first_tier_pole",
        "opponent_force_effect": "main_force_destroyed",
        "battle_result": "victory",
        "objective_completion": "complete",
    }
    _validate_single_pole_decisive_defeat(
        war_event_id="WAR-TEST-SINGLE-POLE-DEFEAT",
        fields=valid,
    )
    with pytest.raises(ValueError, match="必须面对战前第一梯队"):
        _validate_single_pole_decisive_defeat(
            war_event_id="WAR-TEST-REGIONAL-DEFEAT",
            fields={**valid, "opponent_strategic_weight": "regional_major"},
        )
    with pytest.raises(ValueError, match="必须完成对主力"):
        _validate_single_pole_decisive_defeat(
            war_event_id="WAR-TEST-LIMITED-DEFEAT",
            fields={**valid, "opponent_force_effect": "major_degradation"},
        )
    _validate_residual_opponent_result_ceiling(
        war_event_id="WAR-TEST-RESIDUAL-MAJOR-STAGE",
        fields={
            "result_class": "major_stage_or_crisis",
            "opponent_condition": "residual",
            "battle_result": "victory",
            "objective_completion": "complete",
        },
    )


def test_institutional_default_ruler_is_forbidden_at_s_minus_or_above() -> None:
    adjudication = {
        "disposition": "REGISTERED_CONTRACT",
        "canonical_label": "高档测试战役",
        "period": {"start": "1年", "end": "1年"},
        "result_class": "independent_direction",
        "campaign_tier": "S-",
        "land_strategic_value": "important_region",
        "opponent_strategic_weight": "regional_major",
        "opponent_condition": "viable",
        "battle_result": "victory",
        "objective_completion": "complete",
        "observable_result": "完成独立战略方向。",
        "tier_basis": "土地轴、对手轴与结果轴均已闭合。",
        "combat_difficulty": "D1",
        "combat_difficulty_basis": "过程简略。",
        "campaign_command_topology": "command_unresolved",
        "ruler_role_status": "resolved",
        "ruler_role_basis": "制度性默认授权，非逐字指挥证据。",
        "members": [
            {
                "actor_kind": "ruler",
                "actor_name": "测试皇帝",
                "actor_ref": "RULER-BATTLE-06905AFDD07BFBF4",
                "role_code": "not_in_command_chain",
                "contribution_scope": "仅作制度性归属。",
                "ruler_campaign_relation": "authorization_only",
                "authorization_mode": "institutional_default",
            }
        ],
        "attributable_failures": [],
        "source_refs": ["資治通鑑/卷001@1"],
    }
    with pytest.raises(ValueError, match="S-以上不得使用皇帝制度性默认授权"):
        _contract_row(
            {"war_event_id": "WAR-TEST-RULER-DEFAULT", "dynasty": "测试"},
            {},
            adjudication,
        )


def test_authorization_only_ruler_cannot_enter_command_chain() -> None:
    adjudication = {
        "disposition": "REGISTERED_CONTRACT",
        "canonical_label": "授权角色测试战役",
        "period": {"start": "1年", "end": "1年"},
        "result_class": "important_objective",
        "campaign_tier": "B",
        "land_strategic_value": "important_region",
        "opponent_strategic_weight": "regional_major",
        "opponent_condition": "viable",
        "battle_result": "victory",
        "objective_completion": "complete",
        "observable_result": "完成重要目标。",
        "tier_basis": "土地轴、对手轴与结果轴均已闭合。",
        "combat_difficulty": "D1",
        "combat_difficulty_basis": "常规行动。",
        "campaign_command_topology": "single_integrated_command",
        "ruler_role_status": "resolved",
        "ruler_role_basis": "皇帝只作明确授权。",
        "members": [
            {
                "actor_kind": "person",
                "actor_name": "测试主帅",
                "actor_ref": "PER-BATTLE-BEDA86EAF945BF44",
                "role_code": "commander_in_chief",
                "contribution_scope": "统率完整战役。",
            },
            {
                "actor_kind": "ruler",
                "actor_name": "测试皇帝",
                "actor_ref": "RULER-BATTLE-06905AFDD07BFBF4",
                "role_code": "participant",
                "contribution_scope": "只作授权。",
                "ruler_campaign_relation": "authorization_only",
                "authorization_mode": "explicit",
            },
        ],
        "attributable_failures": [],
        "source_refs": ["資治通鑑/卷001@1"],
    }
    with pytest.raises(ValueError, match="仅授权皇帝不得进入指挥链"):
        _contract_row(
            {"war_event_id": "WAR-TEST-RULER-AUTH", "dynasty": "测试"},
            {},
            adjudication,
        )

    adjudication["members"][1]["ruler_campaign_relation"] = "operational_direction"
    with pytest.raises(ValueError, match="皇帝战略指导不得登记为从攻"):
        _contract_row(
            {"war_event_id": "WAR-TEST-RULER-OPERATIONAL", "dynasty": "测试"},
            {},
            adjudication,
        )


def test_opposed_person_result_is_independently_tiered_from_parent_side() -> None:
    adjudication = {
        "disposition": "REGISTERED_CONTRACT",
        "canonical_label": "败方口径双向战役",
        "period": {"start": "1年", "end": "1年"},
        "result_class": "major_stage_or_crisis",
        "campaign_tier": "A",
        "land_strategic_value": "strategic_gateway",
        "opponent_strategic_weight": "regional_major",
        "opponent_condition": "strong",
        "battle_result": "defeat",
        "objective_completion": "failed",
        "observable_result": "败方主力撤退，胜方终结本次进攻。",
        "tier_basis": "父卡按败方重大方向失败登记。",
        "combat_difficulty": "D3",
        "combat_difficulty_basis": "双方均有现实胜路。",
        "campaign_command_topology": "opposed_commands",
        "ruler_role_status": "unresolved",
        "ruler_role_basis": "卡内未闭合统治者关系。",
        "members": [{
            "actor_kind": "person",
            "actor_name": "胜方统帅",
            "actor_ref": canonical_hashed_ref(
                "PER-BATTLE", "测试|胜方统帅", length=16
            ),
            "role_code": "commander_in_chief",
            "command_side": "WINNER",
            "command_result_direction": "positive",
            "contribution_scope": "统合胜方反击并终结来攻。",
            "person_command_result": {
                "result_direction": "positive",
                "result_tier": "S",
                "combat_difficulty": "D3",
                "basis": "胜方按自身已实现结果独立定级，不继承败方父卡档位。",
                "source_refs": ["SOURCE-1"],
            },
        }, {
            "actor_kind": "person",
            "actor_name": "败方统帅",
            "actor_ref": canonical_hashed_ref(
                "PER-BATTLE", "测试|败方统帅", length=16
            ),
            "role_code": "commander_in_chief",
            "command_side": "LOSER",
            "command_result_direction": "negative",
            "contribution_scope": "统合败方来攻并承担撤退结果。",
        }],
        "attributable_failures": [],
        "source_refs": ["SOURCE-1"],
    }
    row = _contract_row(
        {"war_event_id": "WAR-TEST-OPPOSED-WINNER", "dynasty": "测试"},
        {},
        adjudication,
    )
    assert row["members"][0]["person_command_result"]["result_tier"] == "S"

    adjudication["campaign_command_topology"] = "single_integrated_command"
    adjudication["members"] = adjudication["members"][:1]
    with pytest.raises(ValueError, match="仅敌对指挥链的反向人物结果允许独立定级"):
        _contract_row(
            {"war_event_id": "WAR-TEST-OPPOSED-WINNER", "dynasty": "测试"},
            {},
            adjudication,
        )


def test_joint_command_index_does_not_duplicate_full_parent_credit() -> None:
    command_index = derive_person_command_index(
        {
            "actor_ref": "PER-TEST-JOINT",
            "actor_name": "共同主帅甲",
            "actor_kind": "person",
            "role_code": "commander_in_chief",
            "talent_credit": "independent",
            "contribution_scope": "与另一主帅共同承担最高统合责任。",
        },
        campaign_tier="S",
        combat_difficulty="D3",
        battle_result="victory",
        source_refs=["資治通鑑/卷001@1"],
        campaign_command_topology="joint_integrated_command",
    )

    assert command_index["consumption_mode"] == "joint_parent"
    assert command_index["command_scope"] == "joint_full_campaign"
    assert command_index["detail_status"] == "person_result_required"


def test_opposed_command_index_requires_person_result() -> None:
    command_index = derive_person_command_index(
        {
            "actor_ref": "PER-TEST-OPPOSED",
            "actor_name": "敌对主帅甲",
            "actor_kind": "person",
            "role_code": "commander_in_chief",
            "talent_credit": "independent",
            "command_side": "SIDE-A",
            "command_result_direction": "negative",
            "contribution_scope": "独立统率本方完整指挥链并承担败绩。",
        },
        campaign_tier="S",
        combat_difficulty="D4",
        battle_result="victory",
        source_refs=["資治通鑑/卷001@1"],
        campaign_command_topology="opposed_commands",
    )

    assert command_index == {
        "consumption_mode": "person_result_required",
        "command_scope": "opposed_full_campaign",
        "capability_mode": "integrated_command",
        "decisive_relation": "decisive_creator",
        "result_direction": "negative",
        "projected_result_tier": None,
        "projected_combat_difficulty": None,
        "detail_status": "failure_review_required",
        "basis": "独立统率本方完整指挥链并承担败绩。",
        "source_refs": ["資治通鑑/卷001@1"],
    }


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "_dynasty": "汉",
        "war_event_id": "WAR-TEST-001",
        "battle_id": "BATTLE-TEST-001",
        "campaign_group": "CAMPAIGN-TEST-001",
        "settlement_role": "terminal",
        "settlement_status": "closed",
        "account_routing": "THREE_LEDGER_STANDARD",
        "title": "测试战役",
        "time_range": "前200年",
        "evaluation_subject": "汉",
        "source_card_id": "WAR-TEST-001",
        "source_revision_refs": ["資治通鑑/卷001@1"],
        "source_occurrences": [{"source_file": "卷001-通读总结.md"}],
        "review_flags": [],
        "outcome": "完成战略目标",
        "command_attribution": "甲独立统帅",
        "cost_ref": "cost:war_event_id:WAR-TEST-001",
        "defense_ref": "defense:war_event_id:WAR-TEST-001",
        "source_fact_fields": {"谋略": ["乙献反间计，甲从之，敌军内乱。"]},
    }
    row.update(overrides)
    return row


def test_worklist_groups_stages_under_closed_terminal() -> None:
    stage = _row(
        battle_id="BATTLE-TEST-STAGE",
        settlement_role="stage",
        settlement_status="absorbed",
        title="测试战役阶段",
    )
    report = build_battle_outcome_worklist(
        [_row(), stage],
        military_settlements={
            "WAR-TEST-001": {
                "war_event_id": "WAR-TEST-001",
                "strategic_security_grade": "SB4",
                "wc_consistency_grade": "WC3",
                "wr_clues": ["WR3"],
                "portfolio_usable": True,
                "adjudication_status": "REVIEWED",
                "benefit_readiness": "READY_BENEFIT",
            }
        },
    )
    assert report["declarations"]["ledger_row_count"] == 2
    assert report["declarations"]["candidate_count"] == 1
    candidate = report["candidates"][0]
    assert candidate["stage_count"] == 1
    assert candidate["terminal_nodes"][0]["outcome"] == "完成战略目标"
    assert candidate["terminal_nodes"][0]["command_attribution"] == "甲独立统帅"
    assert candidate["terminal_nodes"][0]["source_fact_fields"]["谋略"]
    assert candidate["stage_nodes"][0]["battle_id"] == "BATTLE-TEST-STAGE"
    assert candidate["evidence_readiness"]["result_known"] is True
    assert candidate["statecraft_review"]["lead_passages"]
    assert candidate["registration_disposition"] == "BATCH_REVIEW"
    assert candidate["military_settlement"]["high_impact_review"] is True


def test_worklist_routes_unification_before_source_readiness() -> None:
    report = build_battle_outcome_worklist(
        [
            _row(
                account_routing="UNIFICATION_ONLY",
                source_revision_refs=[],
                outcome="未知",
                command_attribution="未知",
            )
        ]
    )
    assert (
        report["candidates"][0]["registration_disposition"]
        == "UNIFICATION_DEEP_REVIEW"
    )
    assert (
        report["candidates"][0]["unification_scope_adjudication"]["status"]
        == "MISSING_ADJUDICATION"
    )


def test_worklist_attaches_unification_scope_adjudication() -> None:
    report = build_battle_outcome_worklist(
        [_row(account_routing="UNIFICATION_ONLY")],
        unification_scope_adjudications={
            "WAR-TEST-001": {
                "status": "ADJUDICATED",
                "scope_kind": "REGIONAL_ANNEXATION",
                "portfolio_ref": "UCP-TEST",
                "basis": "测试区域兼并。",
            }
        },
    )
    candidate = report["candidates"][0]
    assert candidate["unification_scope_adjudication"]["portfolio_ref"] == "UCP-TEST"
    assert report["declarations"]["unification_scope_missing_ids"] == []
    assert report["declarations"]["unification_scope_extra_ids"] == []


def test_worklist_attaches_full_realm_tier_adjudication() -> None:
    report = build_battle_outcome_worklist(
        [_row(account_routing="UNIFICATION_ONLY")],
        unification_scope_adjudications={
            "WAR-TEST-001": {
                "status": "ADJUDICATED",
                "scope_kind": "FULL_REALM_UNIFICATION",
                "portfolio_ref": "UCP-TEST",
                "basis": "测试全国统一。",
            }
        },
        unification_tier_adjudications={
            "WAR-TEST-001": {
                "portfolio_ref": "UCP-TEST",
                "status": "REGISTERED_NOT_GOLD",
                "registration_role": "UNIFICATION_CAMPAIGN_PORTFOLIO",
                "allow_open_portfolio_root": False,
                "war_event_refs": ["WAR-TEST-001"],
                "basis": "测试统一进程。",
                "campaign_groups": [
                    {
                        "campaign_group_id": "CAMPAIGN-TEST-001",
                        "war_event_refs": ["WAR-TEST-001"],
                        "status": "READY_FOR_PACK",
                        "registration_role": "CAMPAIGN_GROUP",
                        "campaign_tier": "S",
                        "basis": "终结第一梯队竞争极。",
                    }
                ],
            }
        },
    )
    candidate = report["candidates"][0]
    assert candidate["unification_tier_adjudication"]["campaign_groups"][0][
        "campaign_tier"
    ] == "S"
    assert report["declarations"]["unification_tier_missing_ids"] == []
    assert report["declarations"]["unification_tier_extra_ids"] == []
    assert report["declarations"]["full_realm_portfolio_count"] == 1
    markdown = render_battle_outcome_worklist_markdown(report)
    assert "大一统朝代统一进程战役群裁决" in markdown
    assert "只登记字母档" in markdown
    assert "`UCP-TEST`" in markdown
    assert "终结第一梯队竞争极" in markdown


def test_worklist_keeps_explicitly_adjudicated_open_unification_root() -> None:
    report = build_battle_outcome_worklist(
        [
            _row(
                account_routing="UNIFICATION_ONLY",
                settlement_role="stage",
                settlement_status="absorbed",
            )
        ],
        unification_scope_adjudications={
            "WAR-TEST-001": {
                "status": "ADJUDICATED",
                "scope_kind": "FULL_REALM_UNIFICATION",
                "portfolio_ref": "UCP-TEST",
                "basis": "测试统一根。",
            }
        },
        unification_tier_adjudications={
            "WAR-TEST-001": {
                "portfolio_ref": "UCP-TEST",
                "status": "REGISTERED_NOT_GOLD",
                "registration_role": "UNIFICATION_CAMPAIGN_PORTFOLIO",
                "allow_open_portfolio_root": True,
                "war_event_refs": ["WAR-TEST-001"],
                "basis": "测试父根。",
                "campaign_groups": [
                    {
                        "campaign_group_id": "CAMPAIGN-TEST-001",
                        "war_event_refs": ["WAR-TEST-001"],
                        "status": "READY_FOR_PACK",
                        "registration_role": "CAMPAIGN_GROUP",
                        "basis": "测试战役群。",
                    }
                ],
            }
        },
    )
    assert report["declarations"]["candidate_count"] == 1
    assert report["declarations"][
        "manually_adjudicated_open_unification_root_count"
    ] == 1
    assert report["candidates"][0]["source_settlement_closed"] is False


def test_worklist_auto_register_requires_reviewed_settlement() -> None:
    report = build_battle_outcome_worklist(
        [_row()],
        military_settlements={
            "WAR-TEST-001": {
                "war_event_id": "WAR-TEST-001",
                "strategic_security_grade": "SB3",
                "wc_consistency_grade": "WC2",
                "wr_clues": ["WR3"],
                "portfolio_usable": True,
                "adjudication_status": "REVIEWED",
                "benefit_readiness": "READY_BENEFIT",
            }
        },
    )
    assert report["candidates"][0]["registration_disposition"] == "AUTO_REGISTER"


def test_worklist_keeps_weak_high_impact_candidate_for_batch_review() -> None:
    report = build_battle_outcome_worklist(
        [_row(source_revision_refs=[], outcome="未知")],
        military_settlements={
            "WAR-TEST-001": {
                "war_event_id": "WAR-TEST-001",
                "strategic_security_grade": "SN5",
                "wc_consistency_grade": "WC4",
                "wr_clues": ["WR0"],
                "portfolio_usable": False,
                "adjudication_status": "REVIEWED",
                "benefit_readiness": "HOLD",
            }
        },
    )
    assert report["candidates"][0]["registration_disposition"] == "BATCH_REVIEW"


def test_worklist_rejects_placeholder_grade_from_auto_register() -> None:
    report = build_battle_outcome_worklist(
        [_row()],
        military_settlements={
            "WAR-TEST-001": {
                "war_event_id": "WAR-TEST-001",
                "strategic_security_grade": "待后续",
                "wc_consistency_grade": "WC4",
                "wr_clues": ["WR2"],
                "portfolio_usable": True,
                "adjudication_status": "REVIEWED",
                "benefit_readiness": "READY_BENEFIT",
            }
        },
    )
    candidate = report["candidates"][0]
    assert candidate["registration_disposition"] == "BATCH_REVIEW"
    assert candidate["military_settlement"]["grade_contract_complete"] is False


def test_worklist_skips_open_group_and_exposes_existing_link_gap() -> None:
    open_row = _row(settlement_role="stage", settlement_status="open")
    existing = {
        "outcomes": [
            {
                "registration_ref": "HOUT-001",
                "event_level": "campaign_group",
                "canonical_label": "既有成果",
            }
        ]
    }
    report = build_battle_outcome_worklist([open_row], existing_registry=existing)
    assert report["declarations"]["candidate_count"] == 0
    assert report["declarations"]["skipped_open_group_count"] == 1
    assert report["declarations"]["existing_link_gap"] is True


def test_worklist_render_is_deterministic() -> None:
    first = build_battle_outcome_worklist([_row()])
    second = build_battle_outcome_worklist([_row()])
    assert first["fingerprint"] == second["fingerprint"]
    assert render_battle_outcome_worklist_markdown(first) == (
        render_battle_outcome_worklist_markdown(second)
    )


def test_candidate_input_fingerprint_ignores_adjudication_progress() -> None:
    before = build_battle_outcome_worklist([_row()])
    after = build_battle_outcome_worklist(
        [_row()],
        ordinary_campaign_adjudications={
            "WAR-TEST-001": {
                "status": "BELOW_PUBLIC_OUTCOME_THRESHOLD",
                "registration_role": "NEUTRAL_EVENT_ONLY",
                "candidate_disposition": "BATCH_REVIEW",
                "basis": "测试裁决进度不得改变候选输入指纹。",
            }
        },
    )

    assert before["candidate_input_fingerprint"] == after["candidate_input_fingerprint"]
    assert before["fingerprint"] != after["fingerprint"]


def test_formal_ordinary_adjudication_must_cover_all_candidate_source_refs() -> None:
    with pytest.raises(ValueError, match="遗漏父群或阶段史源"):
        build_battle_outcome_worklist(
            [_row()],
            ordinary_campaign_adjudications={
                "WAR-TEST-001": {
                    "status": "ADJUDICATED_SOURCE_BACKFILL_REQUIRED",
                    "candidate_disposition": "BATCH_REVIEW",
                    "source_refs": ["資治通鑑/卷002@2"],
                }
            },
        )


def test_exact_evidence_current_requires_complete_formal_coverage() -> None:
    adjudications = {
        "adjudications": [
            {
                "war_event_id": "WAR-TEST-EXACT",
                "status": "ADJUDICATED_SOURCE_BACKFILL_REQUIRED",
                "dynasty": "汉",
                "source_refs": ["資治通鑑/卷001@rev-1"],
                "members": [],
                "payload": {
                    "combat_difficulty": "D1",
                    "operational_costs": [],
                },
            }
        ]
    }
    input_payload = {
        "schema_version": "battle-exact-evidence-backfill-v1",
        "items": [
            {
                "dynasty": "汉",
                "war_event_id": "WAR-TEST-EXACT",
                "source_refs": ["資治通鑑/卷001@rev-1"],
                "source_card_ids": ["WAR-TEST-EXACT"],
                "worklist_candidate_ref": "BOW-TEST",
                "evidence_units": [
                    {
                        "source_page": "資治通鑑/卷001",
                        "revision_ref": "rev-1",
                        "exact_quote": "大破之",
                        "fact": "取得明确胜利",
                        "supported_fields": ["observable_result"],
                    }
                ],
                "unresolved_requirements": [],
            }
        ],
    }
    current = build_current_battle_exact_evidence(
        [input_payload],
        ordinary_adjudications=adjudications,
        source_pages={("資治通鑑/卷001", "rev-1"): "其军大破之，遂还。"},
    )
    assert current["item_count"] == 1
    assert current["evidence_unit_count"] == 1
    assert current["items"][0]["evidence_ref"].startswith("BATTLE-EVIDENCE-")

    missing_failure_evidence = json.loads(
        json.dumps(adjudications, ensure_ascii=False)
    )
    missing_failure_evidence["adjudications"][0]["payload"][
        "attributable_failures"
    ] = [
        {
            "actor_name": "测试人物",
            "actor_ref": "PER-TEST",
            "basis": "测试人物存在可归责失误。",
            "responsibility": "primary",
            "severity_index": 0.6,
            "source_refs": ["資治通鑑/卷001@rev-1"],
        }
    ]
    with pytest.raises(ValueError, match="缺少逐字可归责失败证据"):
        build_current_battle_exact_evidence(
            [input_payload],
            ordinary_adjudications=missing_failure_evidence,
        )

    input_payload["items"][0]["unresolved_requirements"] = ["仍缺指挥证据"]
    with pytest.raises(ValueError, match="仍有未闭合逐字证据"):
        build_current_battle_exact_evidence(
            [input_payload],
            ordinary_adjudications=adjudications,
        )


def test_current_ordinary_battle_packs_keep_parent_and_person_boundaries() -> None:
    packs = build_ordinary_battle_outcome_packs(
        ordinary_adjudications=json.loads(
            (ROOT / "config/ordinary-campaign-adjudications.json").read_text(
                encoding="utf-8"
            )
        ),
        exact_evidence=json.loads(
            (ROOT / "eval/battle_exact_evidence/current.json").read_text(
                encoding="utf-8"
            )
        ),
        person_identities=json.loads(
            (ROOT / "config/ordinary-battle-person-identities.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    clusters = [
        cluster
        for pack in packs.values()
        for cluster in pack["outcome_registry"]["clusters"]
    ]
    members = [member for cluster in clusters for member in cluster["members"]]

    assert len(packs) == 7
    assert len(clusters) == 119
    assert sum(member["talent_credit"] == "independent" for member in members) == 44
    assert (
        sum(member["talent_credit"] == "covered_by_child" for member in members)
            == 162
    )
    unresolved_identities = [
        member for member in members if "DRAFT" in member["actor_ref"]
    ]
    assert [member["actor_name"] for member in unresolved_identities] == [
        "高凉王乐真"
    ]
    no_named_command = [
        cluster
        for cluster in clusters
        if not any(
            member["role_code"]
            in {"commander_in_chief", "principal_commander", "participant"}
            for member in cluster["members"]
        )
    ]
    assert len(no_named_command) == 12
    assert {
        cluster["campaign_command_topology"] for cluster in no_named_command
    }.issubset({"distributed_response", "command_unresolved"})
    assert not any(
        "旧严重度" in limitation
        for cluster in clusters
        for limitation in cluster["limitations"]
    )
    failures = [
        failure
        for cluster in clusters
        for failure in cluster["payload"]["attributable_failures"]
    ]
    assert len(failures) == 27
    assert {
        (failure["actor_name"], failure["responsibility"])
        for failure in failures
    } >= {
        ("胡济", "subordinate_execution"),
        ("马谡", "disobedience"),
        ("史抗", "shared"),
        ("温儒雅", "shared"),
        ("李道宗", "shared"),
        ("傅伏爱", "primary"),
    }


def test_throughput_probe_never_contains_unification() -> None:
    report = build_battle_outcome_worklist(
        [
            _row(war_event_id="WAR-TEST-UNIFY", account_routing="UNIFICATION_ONLY"),
            _row(war_event_id="WAR-TEST-ORDINARY"),
        ]
    )
    selected = report["ordinary_throughput_probe"]["candidates"]
    assert all(
        row["registration_disposition"] != "UNIFICATION_DEEP_REVIEW"
        for row in selected
    )


def test_qin_dynasty_battle_pack_keeps_tree_and_window_boundaries() -> None:
    project = yaml.safe_load((ROOT / "config/project.yml").read_text(encoding="utf-8"))
    pack = load_configured_dynasty_outcome_packs(ROOT, project)["QIN"]
    clusters = pack["outcome_registry"]["clusters"]
    scopes = [row["settlement_scope"] for row in clusters]

    assert len(clusters) == 16
    assert scopes.count("war_terminal_context") == 1
    assert scopes.count("ruler_campaign_parent") == 7
    assert scopes.count("person_campaign_subresult") == 6
    assert scopes.count("person_statecraft_result") == 2
    assert all(row["ruler_window_status"] == "unresolved" for row in clusters)
    assert all(not row.get("ruler_context_refs") for row in clusters)
    assert {
        ref for row in clusters for ref in row["source_war_event_refs"]
    } == {
        "WAR-LEAD-QIN-UNIFICATION",
        "WAR-LEAD-QIN-XIONGNU-WALL",
    }
    assert not any("岭南" in row["canonical_label"] for row in clusters)


def test_current_unification_scope_adjudications_have_expected_partition() -> None:
    rows = load_unification_scope_adjudications(
        ROOT / "config/unification-campaign-scope-adjudications.json"
    )
    assert len(rows) == 82
    counts: dict[str, int] = {}
    for row in rows.values():
        scope_kind = row["scope_kind"]
        counts[scope_kind] = counts.get(scope_kind, 0) + 1
    assert counts == {
        "FULL_REALM_UNIFICATION": 20,
        "REGIONAL_REGIME_FOUNDATION": 22,
        "REGIONAL_ANNEXATION": 21,
        "NOT_A_UNIFICATION_PORTFOLIO": 19,
    }


def test_current_unification_tier_adjudications_cover_full_realm_and_head_relevant_regional_terminals() -> None:
    payload = json.loads(
        (ROOT / "config/unification-campaign-tier-adjudications.json").read_text(
            encoding="utf-8"
        )
    )
    portfolios = payload["adjudications"]
    assert len(portfolios) == 30
    assert all(
        {
            "portfolio_ref",
            "status",
            "registration_role",
            "allow_open_portfolio_root",
            "war_event_refs",
            "basis",
            "campaign_groups",
        }.issubset(portfolio)
        and set(portfolio).issubset(
            {
                "portfolio_ref",
                "status",
                "registration_role",
                "allow_open_portfolio_root",
                "war_event_refs",
                "basis",
                "campaign_groups",
                "dynasty",
            }
        )
        for portfolio in portfolios
    )
    assert all(
        portfolio["status"] == "REGISTERED_NOT_GOLD"
        and portfolio["registration_role"] == "UNIFICATION_CAMPAIGN_PORTFOLIO"
        for portfolio in portfolios
    )
    assert all(
        group.get("war_event_refs")
        for portfolio in portfolios
        for group in portfolio["campaign_groups"]
    )
    rows = load_unification_tier_adjudications(
        ROOT / "config/unification-campaign-tier-adjudications.json"
    )
    assert len(rows) == 63
    assert len({row["portfolio_ref"] for row in rows.values()}) == 30
    assert rows["WAR-LEAD-HAN-GONGSUNZAN-END-199"]["campaign_groups"][0][
        "payload"
    ]["campaign_tier"] == "S-"
    qin_children = rows["WAR-LEAD-QIN-UNIFICATION"]["campaign_groups"]
    assert len(qin_children) == 6
    assert {child["payload"]["campaign_tier"] for child in qin_children} == {
        "A",
        "S-",
        "S",
    }
    liu_bang_children = rows["WAR-LEAD-CHUHAN"]["campaign_groups"]
    assert len(liu_bang_children) == 8
    assert {child["payload"]["battle_result"] for child in liu_bang_children} == {
        "victory",
        "defeat",
        "mixed",
    }
    assert {
        child["payload"]["campaign_tier"] for child in liu_bang_children
    } == {"A", "S-", "S"}
    liu_xiu_children = rows[
        "WAR-LEAD-HAN-STARTUP-UNIFICATION-23-36"
    ]["campaign_groups"]
    assert len(liu_xiu_children) == 11
    assert {
        child["payload"]["campaign_tier"]
        for child in liu_xiu_children
        if child.get("payload")
    } == {"A", "S-", "S"}
    formal_groups = [
        child
        for portfolio in portfolios
        for child in portfolio["campaign_groups"]
        if child["registration_role"] == "CAMPAIGN_GROUP"
    ]
    assert len(formal_groups) == 75
    tang_fugongshi = next(
        child
        for portfolio in portfolios
        for child in portfolio["campaign_groups"]
        if child["campaign_group_id"] == "WAR-LEAD-TANG-FUGONGSHI"
    )
    assert (
        tang_fugongshi["payload"]["campaign_tier"],
        tang_fugongshi["payload"]["combat_difficulty"],
    ) == ("A", "D3")
    assert all(
        child.get("members")
        and child.get("campaign_command_topology")
        in {
                "single_integrated_command",
                "joint_integrated_command",
                "federated_directions",
                "opposed_commands",
                "distributed_response",
                "command_unresolved",
                "sequential_successor_command",
        }
        and isinstance(child.get("stable_delivery"), bool)
        and child.get("source_refs")
        and child.get("payload")
        for child in formal_groups
    )
    qin_by_group = {child["campaign_group_id"]: child for child in qin_children}
    qin_chu = qin_by_group["OUTCOME-QIN-CHU"]
    assert qin_chu["campaign_command_topology"] == "sequential_successor_command"
    assert next(
        member for member in qin_chu["members"] if member["actor_name"] == "王翦"
    )["person_command_index"]["consumption_mode"] == "full_parent"
    assert any(
        failure["actor_name"] == "李信"
        for failure in qin_chu["payload"]["attributable_failures"]
    )
    assert (
        qin_by_group["OUTCOME-QIN-ZHAO"]["campaign_command_topology"],
        qin_by_group["OUTCOME-QIN-YAN"]["campaign_command_topology"],
    ) == ("command_unresolved", "command_unresolved")
    assert all(
        member["role_code"] == "principal_commander"
        for group_id in ("OUTCOME-QIN-ZHAO", "OUTCOME-QIN-YAN")
        for member in qin_by_group[group_id]["members"]
        if member["actor_kind"] == "person"
    )
    command_indices = [
        member["person_command_index"]
        for child in formal_groups
        for member in child["members"]
    ]
    assert Counter(index["consumption_mode"] for index in command_indices) == {
        "full_parent": 47,
        "person_result": 87,
        "operational_result": 15,
        "none": 34,
    }
    jin_wu = next(
        child
        for portfolio in portfolios
        for child in portfolio["campaign_groups"]
        if child["campaign_group_id"] == "WAR-LEAD-JIN-CONQUEST-WU-280"
    )
    jin_wu_members = {member["actor_name"]: member for member in jin_wu["members"]}
    assert (
        jin_wu_members["王濬"]["person_command_index"]["projected_result_tier"],
        jin_wu_members["王濬"]["person_command_index"][
            "projected_combat_difficulty"
        ],
        jin_wu_members["杜预"]["person_command_index"]["projected_result_tier"],
        jin_wu_members["杜预"]["person_command_index"][
            "projected_combat_difficulty"
        ],
    ) == ("A", "D3", "S-", "D3")
    assert (
        jin_wu_members["司马炎"]["ruler_campaign_relation"],
        jin_wu_members["司马炎"]["person_command_index"]["consumption_mode"],
        jin_wu_members["司马炎"]["person_command_index"][
            "projected_combat_difficulty"
        ],
    ) == ("operational_direction", "operational_result", None)
    liu_bang_by_group = {
        child["campaign_group_id"]: child for child in liu_bang_children
    }
    gaixia_liubang = next(
        member
        for member in liu_bang_by_group["HAN-CHUHAN-GAIXIA-BCE203-202"]["members"]
        if member["actor_name"] == "刘邦"
    )
    assert (
        gaixia_liubang["person_command_index"]["consumption_mode"],
        gaixia_liubang["person_command_index"]["projected_result_tier"],
        gaixia_liubang["person_command_index"]["projected_combat_difficulty"],
        gaixia_liubang["person_command_index"]["capability_mode"],
    ) == ("operational_result", "A", None, "operational_design")
    three_qin_members = {
        member["actor_name"]: member
        for member in liu_bang_by_group["HAN-CHUHAN-THREE-QIN-BCE206-205"][
            "members"
        ]
    }
    assert (
        three_qin_members["周勃"]["person_command_index"]["projected_result_tier"],
        three_qin_members["曹参"]["person_command_index"]["projected_result_tier"],
    ) == ("B", "B")
    wei_members = {
        member["actor_name"]: member
        for member in liu_bang_by_group["HAN-CHUHAN-WEI-BCE205"]["members"]
    }
    assert (
        wei_members["曹参"]["person_command_index"]["projected_result_tier"],
        wei_members["灌婴"]["person_command_index"]["projected_result_tier"],
    ) == ("A", "B")
    assert qin_by_group["OUTCOME-QIN-ZHAO"]["members"][3]["person_command_index"][
        "decisive_relation"
    ] == "terminal_finisher"
    qin_zhao_wangjian = next(
        member
        for member in qin_by_group["OUTCOME-QIN-ZHAO"]["members"]
        if member["actor_name"] == "王翦"
    )
    assert (
        qin_zhao_wangjian["person_command_index"]["projected_result_tier"],
        qin_zhao_wangjian["person_command_index"]["capability_mode"],
        qin_zhao_wangjian["person_command_index"]["decisive_relation"],
    ) == ("S", "integrated_command", "decisive_creator")
    east = next(
        child for child in liu_xiu_children
        if child["campaign_group_id"] == "HAN-STARTUP-EAST-26-30"
    )
    geng_yan = next(member for member in east["members"] if member["actor_name"] == "耿弇")
    assert (
        geng_yan["person_command_index"]["projected_result_tier"],
        geng_yan["person_command_index"]["projected_combat_difficulty"],
        geng_yan["person_command_index"]["decisive_relation"],
        ) == ("S-", "D3", "decisive_creator")
    shu = next(
        child for child in liu_xiu_children
        if child["campaign_group_id"] == "HAN-STARTUP-SHU-33-36"
    )
    wu_han_shu = next(member for member in shu["members"] if member["actor_name"] == "吴汉")
    assert (
        wu_han_shu["person_command_index"]["projected_result_tier"],
        wu_han_shu["person_command_index"]["result_direction"],
        wu_han_shu["person_command_index"]["decisive_relation"],
    ) == ("S", "positive", "decisive_creator")
    xiaoxian = next(
        child
        for portfolio in portfolios
        for child in portfolio["campaign_groups"]
        if child["campaign_group_id"] == "WAR-LEAD-TANG-XIAOXIAN-621"
    )
    xiaoxian_members = {member["actor_name"]: member for member in xiaoxian["members"]}
    assert xiaoxian_members["李孝恭"]["role_code"] == "commander_in_chief"
    assert xiaoxian_members["李孝恭"]["person_command_index"]["consumption_mode"] == "none"
    assert xiaoxian_members["李靖"]["role_code"] == "principal_commander"
    assert xiaoxian_members["李靖"]["person_command_index"]["consumption_mode"] == "full_parent"
    sui_terminal = next(
        child
        for portfolio in portfolios
        for child in portfolio["campaign_groups"]
        if child["campaign_group_id"] == "WAR-PARENT-SUI-UNIFICATION-589"
    )
    sui_members = {member["actor_name"]: member for member in sui_terminal["members"]}
    assert sui_members["杨广"]["role_code"] == "commander_in_chief"
    assert sui_members["杨广"]["person_command_index"]["consumption_mode"] == "none"
    assert sui_members["高颎"]["role_code"] == "principal_commander"
    assert sui_members["高颎"]["person_command_index"]["consumption_mode"] == "operational_result"
    assert sui_members["贺若弼"]["person_command_index"]["consumption_mode"] == "person_result"
    assert sui_members["韩擒虎"]["person_command_index"]["consumption_mode"] == "person_result"
    tang_liu_heita = next(
        child
        for portfolio in portfolios
        for child in portfolio["campaign_groups"]
        if child["campaign_group_id"] == "WAR-LEAD-TANG-LIUHEITA-622"
    )
    liu_heita_members = {
        member["actor_name"]: member for member in tang_liu_heita["members"]
    }
    assert liu_heita_members["李世民"]["person_command_index"][
        "projected_combat_difficulty"
    ] == "D4"
    assert (
        liu_heita_members["李建成"]["person_command_index"]["projected_result_tier"],
        liu_heita_members["李建成"]["person_command_index"][
            "projected_combat_difficulty"
        ],
    ) == ("A", "D2")
    tang_xuyuanlang = next(
        child
        for portfolio in portfolios
        for child in portfolio["campaign_groups"]
        if child["campaign_group_id"] == "WAR-LEAD-TANG-XUYUANLANG-621"
    )
    tang_xuyuanlang_liji = next(
        member for member in tang_xuyuanlang["members"] if member["actor_name"] == "李勣"
    )
    assert (
        tang_xuyuanlang_liji["person_command_index"]["projected_result_tier"],
        tang_xuyuanlang_liji["person_command_index"]["capability_mode"],
        tang_xuyuanlang_liji["person_command_index"]["decisive_relation"],
    ) == ("B", "tactical_execution", "stage_executor")
    fugongshi_lijing = next(
        member for member in tang_fugongshi["members"] if member["actor_name"] == "李靖"
    )
    assert (
        fugongshi_lijing["person_command_index"]["projected_result_tier"],
        fugongshi_lijing["person_command_index"]["projected_combat_difficulty"],
        fugongshi_lijing["person_command_index"]["capability_mode"],
    ) == ("A", "D3", "integrated_command")
    members_by_name = {
        (child["campaign_group_id"], member["actor_name"]): member
        for child in formal_groups
        for member in child["members"]
    }
    assert members_by_name[
        ("HAN-CHUHAN-GUANZHONG-ENTRY-BCE207-206", "刘邦")
    ]["person_command_index"]["consumption_mode"] == "full_parent"
    assert members_by_name[
        ("HAN-STARTUP-CENTRAL-25-26", "刘秀")
    ]["person_command_index"]["consumption_mode"] == "operational_result"
    assert members_by_name[
        ("HAN-STARTUP-CENTRAL-25-26", "刘秀")
    ]["person_command_index"]["projected_combat_difficulty"] is None
    liu_xiu_by_group = {
        child["campaign_group_id"]: child for child in liu_xiu_children
    }
    assert (
        liu_xiu_by_group["HAN-STARTUP-CENTRAL-25-26"][
            "campaign_command_topology"
        ],
        liu_xiu_by_group["HAN-STARTUP-EAST-26-30"][
            "campaign_command_topology"
        ],
    ) == ("federated_directions", "federated_directions")
    assert liu_xiu_by_group["HAN-STARTUP-GUANZHONG-24-27"][
        "campaign_command_topology"
    ] == "sequential_successor_command"
    assert next(
        member
        for member in liu_xiu_by_group["HAN-STARTUP-GUANZHONG-24-27"]["members"]
        if member["actor_name"] == "冯异"
    )["person_command_index"]["consumption_mode"] == "full_parent"
    assert all(
        liu_xiu_by_group[group_id]["campaign_command_topology"]
        == "command_unresolved"
        for group_id in ("HAN-STARTUP-LONGYOU-30-34", "HAN-STARTUP-SHU-33-36")
    )
    assert members_by_name[
        ("WAR-PARENT-SUI-UNIFICATION-589", "杨广")
    ]["person_command_index"]["consumption_mode"] == "none"
    assert members_by_name[
        ("WAR-PARENT-SUI-UNIFICATION-589", "高颎")
    ]["person_command_index"]["consumption_mode"] == "operational_result"
    yuchi = members_by_name[("WAR-LEAD-TANG-LUOYANG-END", "尉迟敬德")][
        "person_command_index"
    ]
    assert yuchi["consumption_mode"] == "person_result"
    assert yuchi["projected_result_tier"] == "B"
    assert yuchi["projected_combat_difficulty"] == "D3"
    wu_han = members_by_name[("HAN-STARTUP-DENGFENG-NANYANG-26-27", "吴汉")][
        "person_command_index"
    ]
    assert wu_han["consumption_mode"] == "person_result"
    assert wu_han["result_direction"] == "negative"
    assert wu_han["detail_status"] == "resolved_person_result"
    li_xin = members_by_name[("OUTCOME-QIN-CHU", "李信")]["person_command_index"]
    assert li_xin["consumption_mode"] == "person_result"
    assert li_xin["result_direction"] == "negative"
    assert (
        li_xin["projected_result_tier"],
        li_xin["projected_combat_difficulty"],
    ) == ("A", "D3")
    assert all(
        sum(
            member["role_code"] == "commander_in_chief"
            for member in child["members"]
        )
        == 1
        for child in formal_groups
        if child["campaign_command_topology"] == "single_integrated_command"
    )
    assert all(
        not any(
            member["role_code"] == "commander_in_chief"
            for member in qin_by_group[group_id]["members"]
        )
        for group_id in ("OUTCOME-QIN-ZHAO", "OUTCOME-QIN-YAN")
    )
    assert all(
        sum(
            member.get("sovereign_at_event") is True
            or member.get("ruler_campaign_relation") is not None
            for member in child["members"]
        )
        <= 1
        for child in formal_groups
    )
    assert Counter(
        child["payload"]["combat_difficulty"] for child in formal_groups
    ) == {"D0": 2, "D1": 7, "D2": 30, "D3": 27, "D4": 9}
    sui_children = {
        child["campaign_group_id"]: child
        for event_id in (
            "WAR-PARENT-SUI-UNIFICATION-589",
            "WAR-PARENT-SUI-SOUTH-CONSOLIDATION-590",
        )
        for child in rows[event_id]["campaign_groups"]
    }
    assert (
        sui_children["WAR-PARENT-SUI-UNIFICATION-589"]["payload"]["campaign_tier"],
        sui_children["SUI-SOUTH-CONSOLIDATION-JIANGNAN-590"]["payload"][
            "campaign_tier"
        ],
        sui_children["SUI-SOUTH-CONSOLIDATION-LINGNAN-590"]["payload"][
            "campaign_tier"
        ],
    ) == ("S", "A", "B")
    assert (
        sui_children["SUI-SOUTH-CONSOLIDATION-LINGNAN-590"][
            "campaign_command_topology"
        ]
        == "command_unresolved"
    )
    assert all(
        member["role_code"] != "commander_in_chief"
        for member in sui_children["SUI-SOUTH-CONSOLIDATION-LINGNAN-590"][
            "members"
        ]
    )
    difficulty_by_group = {
        child["campaign_group_id"]: child["payload"]["combat_difficulty"]
        for child in formal_groups
    }
    assert difficulty_by_group["OUTCOME-QIN-CHU"] == "D3"
    assert difficulty_by_group["HAN-STARTUP-HEBEI-23-24"] == "D3"
    assert difficulty_by_group["HAN-STARTUP-SHU-33-36"] == "D3"
    assert difficulty_by_group["SUI-SOUTH-CONSOLIDATION-JIANGNAN-590"] == "D2"
    assert difficulty_by_group["WAR-LEAD-TANG-HEDONG-RECOVERY"] == "D4"
    assert next(
        child
        for portfolio in portfolios
        for child in portfolio["campaign_groups"]
        if child["campaign_group_id"] == "WAR-LEAD-TANG-HEXI-619"
    )["registration_role"] == "REDIRECT_NON_BATTLE_OUTCOME"
    assert difficulty_by_group["WAR-LEAD-TANG-FUGONGSHI"] == "D3"
    assert difficulty_by_group["WAR-LEAD-TANG-LIUHEITA-622"] == "D4"
    assert difficulty_by_group["HAN-CHUHAN-GAIXIA-BCE203-202"] == "D2"
    tier_by_group = {
        child["campaign_group_id"]: child["payload"]["campaign_tier"]
        for child in formal_groups
    }
    assert all(
        (
            member["person_command_index"]["projected_result_tier"],
            member["person_command_index"]["projected_combat_difficulty"],
        )
        == (child["payload"]["campaign_tier"], child["payload"]["combat_difficulty"])
        for child in formal_groups
        for member in child["members"]
        if member["person_command_index"]["consumption_mode"] == "full_parent"
    )
    assert tier_by_group["SUI-SOUTH-CONSOLIDATION-LINGNAN-590"] == "B"
    assert tier_by_group["WAR-LEAD-TANG-LIANGSHIDU-628"] == "A"
    gaixia = next(
        child
        for child in formal_groups
        if child["campaign_group_id"] == "HAN-CHUHAN-GAIXIA-BCE203-202"
    )
    assert gaixia["payload"]["opponent_strategic_weight"] == "dominant_pole"
    assert gaixia["payload"]["opponent_condition"] == "weakened"
    li_yuan_children = rows[
        "WAR-LEAD-SUI-LIYUAN-GUANZHONG-617"
    ]["campaign_groups"]
    guanzhong = next(
        child
        for child in li_yuan_children
        if child["campaign_group_id"] == "WAR-LEAD-SUI-LIYUAN-GUANZHONG-617"
    )
    assert guanzhong["payload"]["campaign_tier"] == "A"
    tang_lingnan = rows["WAR-LEAD-TANG-LINGNAN-620"]["campaign_groups"]
    assert tang_lingnan[0]["registration_role"] == "NEUTRAL_EVENT_ONLY"
    assert not any(
        key in child
        for child in liu_xiu_children
        for key in ("numeric_weight", "score", "weighted_score")
    )
    assert {row["status"] for row in rows.values()} == {"REGISTERED_NOT_GOLD"}


def test_unification_tier_adjudication_rejects_duplicate_command_or_authority(
    tmp_path: Path,
) -> None:
    source = json.loads(
        (ROOT / "config/unification-campaign-tier-adjudications.json").read_text(
            encoding="utf-8"
        )
    )
    duplicate_commander = json.loads(json.dumps(source, ensure_ascii=False))
    duplicate_commander["adjudications"][0]["campaign_groups"][0]["members"][
        1
    ]["role_code"] = "commander_in_chief"
    duplicate_commander_path = tmp_path / "duplicate-commander.json"
    duplicate_commander_path.write_text(
        json.dumps(duplicate_commander, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="一个实质主帅"):
        load_unification_tier_adjudications(duplicate_commander_path)

    duplicate_authority = json.loads(json.dumps(source, ensure_ascii=False))
    duplicate_authority["adjudications"][0]["campaign_groups"][0]["members"].append(
        {
            "actor_ref": "RULER-TEST-DUPLICATE",
            "actor_name": "重复授权者",
            "actor_kind": "ruler",
            "role_code": "not_in_command_chain",
            "contribution_scope": "测试重复授权关系。",
            "sovereign_at_event": True,
            "ruler_campaign_relation": "authorization_only",
                "authorization_mode": "explicit",
                "person_command_index": {
                    "consumption_mode": "none",
                    "command_scope": "no_person_command_credit",
                    "result_direction": "not_applicable",
                    "projected_result_tier": None,
                    "projected_combat_difficulty": None,
                    "detail_status": "not_required",
                    "basis": "测试重复授权关系。",
                    "source_refs": duplicate_authority["adjudications"][0][
                        "campaign_groups"
                    ][0]["source_refs"],
                },
            }
        )
    duplicate_authority_path = tmp_path / "duplicate-authority.json"
    duplicate_authority_path.write_text(
        json.dumps(duplicate_authority, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="只能有一个统治者授权关系"):
        load_unification_tier_adjudications(duplicate_authority_path)

    invalid_difficulty = json.loads(json.dumps(source, ensure_ascii=False))
    invalid_difficulty["adjudications"][0]["campaign_groups"][0]["payload"][
        "combat_difficulty"
    ] = "D5"
    invalid_difficulty_path = tmp_path / "invalid-difficulty.json"
    invalid_difficulty_path.write_text(
        json.dumps(invalid_difficulty, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="combat_difficulty=D5"):
        load_unification_tier_adjudications(invalid_difficulty_path)

    mismatched_tier = json.loads(json.dumps(source, ensure_ascii=False))
    mismatched_tier["adjudications"][0]["campaign_groups"][0]["payload"][
        "campaign_tier"
    ] = "S-"
    mismatched_tier_path = tmp_path / "mismatched-tier.json"
    mismatched_tier_path.write_text(
        json.dumps(mismatched_tier, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="结果类别与档位不一致"):
        load_unification_tier_adjudications(mismatched_tier_path)

    missing_index = json.loads(json.dumps(source, ensure_ascii=False))
    del missing_index["adjudications"][0]["campaign_groups"][0]["members"][0][
        "person_command_index"
    ]
    missing_index_path = tmp_path / "missing-command-index.json"
    missing_index_path.write_text(
        json.dumps(missing_index, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="人物轻量指挥索引不完整"):
        load_unification_tier_adjudications(missing_index_path)


def test_current_ordinary_campaign_adjudications_cover_all_ordinary_candidates() -> None:
    rows = load_ordinary_campaign_adjudications(
        ROOT / "config/ordinary-campaign-adjudications.json"
    )

    assert len(rows) == 1201
    assert Counter(row["status"] for row in rows.values()) == {
        "HOLD_RESULT_UNCLOSED": 643,
        "HOLD_SOURCE_FINALIZATION_REQUIRED": 163,
        "ADJUDICATED_SOURCE_BACKFILL_REQUIRED": 119,
        "HOLD_SOURCE_BACKFILL_REQUIRED": 100,
        "BELOW_PUBLIC_OUTCOME_THRESHOLD": 61,
        "REDIRECT_NON_BATTLE_OUTCOME": 54,
        "CAMPAIGN_ADJUDICATION_REQUIRED": 2,
        "HOLD_MIXED_EVENT_CHAIN": 49,
        "MERGED_INTO_CAMPAIGN_GROUP": 5,
        "HOLD_AGGREGATE_SECURITY_STATE": 5,
    }
    nanzhong = rows["WAR-LEAD-SG-SHU-NANZHONG-223-225"]
    assert nanzhong["payload"]["campaign_tier"] == "B"
    assert nanzhong["payload"]["combat_difficulty"] == "D2"
    assert nanzhong["campaign_command_topology"] == "single_integrated_command"
    assert nanzhong["stable_delivery"] is True
    duangu = rows["WAR-LEAD-SG-DUANGU-256"]
    assert duangu["payload"]["battle_result"] == "defeat"
    huji = next(member for member in duangu["members"] if member["actor_name"] == "胡济")
    assert huji["person_command_index"]["consumption_mode"] == "person_result"
    assert rows["WAR-LEAD-SG-ZHONGHUI-264"]["registration_role"] == "NEUTRAL_EVENT_ONLY"
    deterrence = rows["WAR-LEAD-HAN-NORTHERN-DETERRENCE-110"]
    assert deterrence["status"] == "REDIRECT_NON_BATTLE_OUTCOME"
    assert rows["WAR-LEAD-HAN-NANYUE-RESTORATION"]["status"] == "REDIRECT_NON_BATTLE_OUTCOME"
    assert rows["WAR-LEAD-SG-WU-JIAOZHOU-226"]["payload"]["campaign_tier"] == "B"
    tang_coup = rows["WAR-LEAD-TANG-713-COUP"]
    assert tang_coup["status"] == "REDIRECT_NON_BATTLE_OUTCOME"
    assert rows["WAR-LEAD-HAN-JIBEI"]["status"] == "BELOW_PUBLIC_OUTCOME_THRESHOLD"
    nanyue = rows["WAR-LEAD-HAN-NANYUE-112-111"]
    assert nanyue["payload"]["campaign_tier"] == "S-"
    assert nanyue["campaign_command_topology"] == "federated_directions"
    assert not any(
        member["person_command_index"]["consumption_mode"] == "full_parent"
        for member in nanyue["members"]
    )
    nanzhao = rows["WAR-LEAD-TANG-NANZHAO-EXPANSION-756"]
    assert nanzhao["campaign_command_topology"] == "command_unresolved"
    assert nanzhao["members"] == []
    yongwang = rows["WAR-LEAD-TANG-YONGBWANG-LIN"]
    assert yongwang["payload"]["campaign_tier"] == "B"
    assert yongwang["campaign_command_topology"] == "command_unresolved"
    assert yongwang["members"] == []
    assert rows["WAR-LEAD-TANG-LINGNAN-726-728"]["status"] == "HOLD_MIXED_EVENT_CHAIN"


def test_d4_reversal_commander_requires_person_result_without_full_parent(
    tmp_path: Path,
) -> None:
    source = json.loads(
        (ROOT / "config/ordinary-campaign-adjudications.json").read_text(
            encoding="utf-8"
        )
    )
    row = next(
        item
        for item in source["adjudications"]
        if item["war_event_id"] == "WAR-LEAD-SG-SHU-NANZHONG-223-225"
    )
    row["payload"]["combat_difficulty"] = "D4"
    row["payload"][
        "combat_difficulty_basis"
    ] = "接任主将承接前任败局并完成可追踪逆转，父群无跨期唯一主帅。"
    row["campaign_command_topology"] = "command_unresolved"
    reversal_commander = row["members"][0]
    reversal_commander["role_code"] = "principal_commander"
    reversal_commander["person_command_index"].update(
        {
            "consumption_mode": "person_result_required",
            "command_scope": "independent_direction",
            "projected_result_tier": None,
            "projected_combat_difficulty": None,
            "detail_status": "person_result_required",
            "basis": "接手前任败局并负责决定性逆转阶段。",
        }
    )
    path = tmp_path / "d4-command-unresolved.json"
    path.write_text(
        json.dumps(source, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    loaded = load_ordinary_campaign_adjudications(path)

    loaded_row = loaded["WAR-LEAD-SG-SHU-NANZHONG-223-225"]
    assert loaded_row["payload"][
        "combat_difficulty"
    ] == "D4"
    assert loaded_row["campaign_command_topology"] == "command_unresolved"
    loaded_reversal_commander = loaded_row["members"][0]
    assert loaded_reversal_commander["role_code"] == "principal_commander"
    assert (
        loaded_reversal_commander["person_command_index"]["consumption_mode"]
        == "person_result_required"
    )
    assert (
        loaded_reversal_commander["person_command_index"][
            "projected_combat_difficulty"
        ]
        is None
    )

    reversal_commander["person_command_index"].update(
        {
            "consumption_mode": "scoped_projection",
            "projected_result_tier": "A",
            "projected_combat_difficulty": "D4",
        }
    )
    invalid_path = tmp_path / "d4-scoped-projection.json"
    invalid_path.write_text(
        json.dumps(source, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="轻量方向投影不得绕过人物子成果门禁"):
        load_ordinary_campaign_adjudications(invalid_path)


def test_merged_ordinary_campaign_child_requires_closed_parent_lineage(
    tmp_path: Path,
) -> None:
    source = json.loads(
        (ROOT / "config/ordinary-campaign-adjudications.json").read_text(
            encoding="utf-8"
        )
    )
    parent = next(
        row
        for row in source["adjudications"]
        if row["war_event_id"] == "WAR-LEAD-115-SOUTHNORTHLIANG-410"
    )
    parent["source_war_event_refs"].remove(
        "WAR-LEAD-116-NORTHSOUTHLIANG-411"
    )
    broken = tmp_path / "broken-merged-lineage.json"
    broken.write_text(
        json.dumps(source, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="合并子事件血缘未闭合"):
        load_ordinary_campaign_adjudications(broken)


def test_split_children_reusing_one_source_card_require_distinct_partitions() -> None:
    worklist = json.loads(
        (ROOT / "tmp/战役登记/公共成果候选/current.json").read_text(
            encoding="utf-8"
        )
    )
    adjudications = json.loads(
        (ROOT / "config/ordinary-campaign-adjudications.json").read_text(
            encoding="utf-8"
        )
    )
    contract_adjudications = load_battle_parent_adjudications(
        ROOT / "config/battle-parent-contract-adjudications.json"
    )
    split = next(
        row
        for row in contract_adjudications["adjudications"]
        if row["war_event_id"] == "WAR-LEAD-HAN-FANCHENG-JINGZHOU-219"
    )
    split["split_campaigns"][0].pop("source_partition")
    settlements = load_military_settlements(
        ROOT
        / "tmp/治理/正式底账/04-军事与边疆/02-成本收益结算/军事成本收益结算底账.jsonl"
    )

    with pytest.raises(ValueError, match="拆分战役群边界或lineage非法"):
        build_battle_parent_contract_registry(
            worklist=worklist,
            ordinary_adjudications=adjudications,
            military_settlements=settlements,
            contract_adjudications=contract_adjudications,
        )


def test_current_contract_parent_registry_closes_all_ordinary_candidates() -> None:
    worklist = json.loads(
        (ROOT / "tmp/战役登记/公共成果候选/current.json").read_text(
            encoding="utf-8"
        )
    )
    adjudications = json.loads(
        (ROOT / "config/ordinary-campaign-adjudications.json").read_text(
            encoding="utf-8"
        )
    )
    contract_adjudications = load_battle_parent_adjudications(
        ROOT / "config/battle-parent-contract-adjudications.json"
    )
    settlements = load_military_settlements(
        ROOT
        / "tmp/治理/正式底账/04-军事与边疆/02-成本收益结算/军事成本收益结算底账.jsonl"
    )

    result = build_battle_parent_contract_registry(
        worklist=worklist,
        ordinary_adjudications=adjudications,
        military_settlements=settlements,
        contract_adjudications=contract_adjudications,
    )
    records = result["records"]
    by_id = {row["war_event_id"]: row for row in records}

    combined = _merge_unification_registry(
        result,
        json.loads(
            (
                ROOT / "config/unification-campaign-tier-adjudications.json"
            ).read_text(encoding="utf-8")
        ),
    )
    combined_by_id = {row["war_event_id"]: row for row in combined["records"]}
    assert combined["ordinary_public_outcome_count"] == 797
    assert combined["unification_public_outcome_count"] == 75
    assert combined["public_outcome_count"] == 872
    assert combined["unification_campaign_group_count"] == 85
    assert combined_by_id["WAR-LEAD-TANG-FUGONGSHI"]["campaign_tier"] == "A"
    assert {
        event_id: (
            combined_by_id[event_id]["campaign_tier"],
            combined_by_id[event_id]["result_class"],
            combined_by_id[event_id]["combat_difficulty"],
        )
        for event_id in (
            "HAN-CHUHAN-WEI-BCE205",
            "HAN-STARTUP-QINFENG-JINGZHOU-24-29",
            "HAN-STARTUP-LIXIAN-JIANGHUAI-28-30",
            "WAR-LEAD-HAN-XUZHOU-LUBU-196-198",
            "WAR-LEAD-HAN-HANZHONG-215",
            "JIN-LATER-ZHAO-HENAN-325",
        )
    } == {
        "HAN-CHUHAN-WEI-BCE205": ("A", "major_stage_or_crisis", "D2"),
        "HAN-STARTUP-QINFENG-JINGZHOU-24-29": (
            "A",
            "major_stage_or_crisis",
            "D2",
        ),
            "HAN-STARTUP-LIXIAN-JIANGHUAI-28-30": (
                "S-",
                "independent_direction",
                "D2",
            ),
        "WAR-LEAD-HAN-XUZHOU-LUBU-196-198": (
            "A",
            "major_stage_or_crisis",
            "D3",
        ),
        "WAR-LEAD-HAN-HANZHONG-215": ("A", "major_stage_or_crisis", "D2"),
        "JIN-LATER-ZHAO-HENAN-325": ("A", "major_stage_or_crisis", "D2"),
    }
    assert combined_by_id["WAR-LEAD-107-WEI-LIUWEICHEN-391"][
        "combat_difficulty"
    ] == "D3"
    assert (
        combined_by_id["WAR-LEAD-105-FEISHUI-383"]["campaign_tier"],
        combined_by_id["WAR-LEAD-105-FEISHUI-383"]["result_class"],
        combined_by_id["WAR-LEAD-105-FEISHUI-383"]["opponent_force_effect"],
    ) == ("S", "single_pole_decisive_defeat", "main_force_destroyed")
    assert (
        combined_by_id["WAR-LEAD-SG-WU-HAN-YILING-221-222"]["campaign_tier"],
        combined_by_id["WAR-LEAD-SG-WU-HAN-YILING-221-222"]["result_class"],
    ) == ("S", "single_pole_decisive_defeat")
    yiling_members = {
        row["actor_name"]: row
        for row in combined_by_id["WAR-LEAD-SG-WU-HAN-YILING-221-222"]["members"]
    }
    assert (
        yiling_members["刘备"]["person_command_index"]["result_direction"],
        yiling_members["刘备"]["person_command_index"]["projected_result_tier"],
    ) == ("negative", "S")
    princes = combined_by_id["WAR-LEAD-TANG-PRINCES-688"]
    princes_members = {row["actor_name"]: row for row in princes["members"]}
    assert (princes["campaign_tier"], princes["combat_difficulty"]) == ("B", "D1")
    assert princes_members["张光辅"]["person_command_index"][
        "capability_mode"
    ] == "integrated_command"
    assert {
        name: princes_members[name]["person_command_index"][
            "projected_result_tier"
        ]
        for name in ("岑长倩", "麴崇裕", "张光辅")
    } == {"岑长倩": "C", "麴崇裕": "C", "张光辅": "B"}
    dongxing_members = {
        row["actor_name"]: row
        for row in combined_by_id["WAR-LEAD-SG-WEI-WU-DONGXING-252"]["members"]
    }
    assert (
        dongxing_members["司马师"]["person_command_index"]["consumption_mode"],
        dongxing_members["司马师"]["person_command_index"]["result_direction"],
        dongxing_members["司马师"]["person_command_index"][
            "projected_combat_difficulty"
        ],
    ) == ("operational_result", "negative", None)
    assert combined_by_id["WAR-LEAD-SG-WEISHU-263"]["campaign_tier"] == "S-"
    assert combined_by_id["WAR-LEAD-SG-WEISHU-263"]["opponent_strategic_weight"] == "regional_major"
    qin_wei = combined_by_id["OUTCOME-QIN-WEI"]
    qin_wei_members = {row["actor_name"]: row for row in qin_wei["members"]}
    assert (
        qin_wei["campaign_tier"],
        qin_wei_members["王贲"]["person_command_index"]["projected_result_tier"],
        qin_wei_members["王贲"]["person_command_index"][
            "projected_combat_difficulty"
        ],
    ) == ("S-", "S-", "D2")
    assert combined_by_id["WAR-LEAD-HAN-WUHUAN-206-207"][
        "opponent_strategic_weight"
    ] == "external_state"
    assert (
        combined_by_id["WAR-LEAD-HAN-ZHIZHI-44-36"]["campaign_tier"],
        combined_by_id["WAR-LEAD-HAN-ZHIZHI-44-36"]["result_class"],
        combined_by_id["WAR-LEAD-HAN-ZHIZHI-44-36"][
            "opponent_strategic_weight"
        ],
        combined_by_id["WAR-LEAD-HAN-ZHIZHI-44-36"]["land_strategic_value"],
    ) == ("A", "major_stage_or_crisis", "external_state", "local_point")
    assert combined_by_id["WAR-LEAD-096-YAN-GOGURYEO-339-341"][
        "land_strategic_value"
    ] == "strategic_gateway"
    assert (
        combined_by_id["WAR-LEAD-108-DIWEI-392"]["campaign_tier"],
        combined_by_id["WAR-LEAD-108-DIWEI-392"]["result_class"],
    ) == ("A", "major_stage_or_crisis")
    assert combined_by_id["WAR-LEAD-096-MIYUN-338"]["campaign_tier"] == "B"
    assert combined_by_id["WAR-LEAD-096-MIYUN-338"]["combat_difficulty"] == "D2"
    yan_fall = combined_by_id["WAR-LEAD-102-YAN-FALL-370"]
    yan_fall_members = {row["actor_name"]: row for row in yan_fall["members"]}
    assert (yan_fall["campaign_tier"], yan_fall["combat_difficulty"]) == (
        "S",
        "D4",
    )
    assert (
        yan_fall_members["王猛"]["person_command_result"]["result_tier"],
        yan_fall_members["王猛"]["person_command_result"]["combat_difficulty"],
        yan_fall_members["苻坚"]["person_command_result"]["result_tier"],
    ) == ("S", "D4", "A")
    zhongli_members = {
        row["actor_name"]: row
        for row in combined_by_id["WAR-LEAD-146-07"]["members"]
    }
    assert combined_by_id["WAR-LEAD-146-07"]["combat_difficulty"] == "D4"
    assert zhongli_members["韦睿"]["person_command_result"][
        "combat_difficulty"
    ] == "D4"
    assert zhongli_members["昌义之"]["person_command_result"][
        "combat_difficulty"
    ] == "D4"
    feishui_members = {
        row["actor_name"]: row
        for row in combined_by_id["WAR-LEAD-105-FEISHUI-383"]["members"]
    }
    assert combined_by_id["WAR-LEAD-105-FEISHUI-383"]["combat_difficulty"] == "D4"
    assert feishui_members["谢玄"]["person_command_result"][
        "combat_difficulty"
    ] == "D4"
    assert combined_by_id["WAR-LEAD-SG-WEI-LIAODONG-238"][
        "combat_difficulty"
    ] == "D2"
    liuyu_qin_members = {
        row["actor_name"]: row
        for row in combined_by_id["WAR-LEAD-118-LIUYU-QIN-417"]["members"]
    }
    assert liuyu_qin_members["刘裕"]["role_code"] == "commander_in_chief"
    assert liuyu_qin_members["王镇恶"]["person_command_result"][
        "combat_difficulty"
    ] == "D4"
    assert liuyu_qin_members["沈田子"]["person_command_result"][
        "combat_difficulty"
    ] == "D4"
    assert liuyu_qin_members["傅弘之"]["person_command_result"]["result_tier"] == "B"
    qinzongquan_members = {
        row["actor_name"]: row
        for row in combined_by_id["WAR-LEAD-257-QINZONGQUAN-END"]["members"]
    }
    assert (
        qinzongquan_members["朱全忠"]["person_command_result"]["result_tier"],
        qinzongquan_members["朱全忠"]["person_command_result"][
            "combat_difficulty"
        ],
    ) == ("A", "D2")
    zhizhi = combined_by_id["WAR-LEAD-HAN-ZHIZHI-44-36"]
    zhizhi_members = {row["actor_name"]: row for row in zhizhi["members"]}
    assert zhizhi["campaign_command_topology"] == "joint_integrated_command"
    assert (
        zhizhi_members["陈汤"]["person_command_index"]["consumption_mode"],
        zhizhi_members["陈汤"]["person_command_result"]["result_tier"],
        zhizhi_members["甘延寿"]["person_command_index"]["consumption_mode"],
        zhizhi_members["甘延寿"]["person_command_result"]["result_tier"],
    ) == ("person_result", "A", "person_result", "A")
    yizhou_members = {
        row["actor_name"]: row
        for row in combined_by_id["WAR-LEAD-SG-WU-YIZHOU-230-231"]["members"]
    }
    assert [
        result["result_direction"]
        for result in yizhou_members["卫温"]["person_command_result"]
    ] == ["positive", "negative"]
    assert [
        result["result_direction"]
        for result in yizhou_members["诸葛直"]["person_command_result"]
    ] == ["positive", "negative"]
    yizhou_failures = combined_by_id["WAR-LEAD-SG-WU-YIZHOU-230-231"][
        "attributable_failures"
    ]
    assert {
        failure["actor_name"]: failure.get("failure_domain", "command_failure")
        for failure in yizhou_failures
    } == {"孙权": "command_failure", "卫温": "war_conduct", "诸葛直": "war_conduct"}
    yuzhang_members = {
        row["actor_name"]: row
        for row in combined_by_id["WAR-LEAD-167-YUZHANG-559"]["members"]
    }
    assert (
        yuzhang_members["周文育"]["person_command_result"]["result_direction"],
        yuzhang_members["侯安都"]["person_command_result"]["result_direction"],
        yuzhang_members["侯安都"]["person_command_result"]["combat_difficulty"],
    ) == ("negative", "positive", "D3")
    fengxiang_court_members = {
        row["actor_name"]: row
        for row in combined_by_id["WAR-LEAD-259-FENGXIANG-COURT-END"]["members"]
    }
    assert (
        fengxiang_court_members["李嗣周"]["person_command_result"][
            "result_direction"
        ],
        fengxiang_court_members["李嗣周"]["person_command_result"]["result_tier"],
    ) == ("negative", "A")
    fengxiang_end_members = {
        row["actor_name"]: row
        for row in combined_by_id["WAR-LEAD-263-FENGXIANG-END"]["members"]
    }
    assert (
        fengxiang_end_members["李茂贞"]["person_command_result"][
            "result_direction"
        ],
        fengxiang_end_members["李茂贞"]["person_command_result"]["result_tier"],
    ) == ("negative", "A")
    rouran_pursuit_members = {
        row["actor_name"]: row
        for row in combined_by_id["WAR-LEAD-149-05"]["members"]
    }
    assert (
        rouran_pursuit_members["李崇"]["person_command_result"]["result_direction"],
        rouran_pursuit_members["元纂"]["person_command_result"]["result_direction"],
        rouran_pursuit_members["于谨"]["person_command_result"]["result_direction"],
        rouran_pursuit_members["于谨"]["person_command_result"][
            "combat_difficulty"
        ],
    ) == ("negative", "negative", "positive", "D4")
    dangxiang_members = {
        row["actor_name"]: row
        for row in combined_by_id["WAR-LEAD-249-01"]["members"]
    }
    assert dangxiang_members["白敏中"]["person_command_index"][
        "consumption_mode"
    ] == "none"
    assert (
        dangxiang_members["毕諴"]["person_command_result"]["result_tier"],
        dangxiang_members["毕諴"]["person_command_result"]["combat_difficulty"],
    ) == ("B", None)
    yang_zhong = combined_by_id["WAR-LEAD-163-02"]
    assert (yang_zhong["campaign_tier"], yang_zhong["combat_difficulty"]) == (
        "A",
        "D2",
    )
    assert {
        row["actor_name"]: row for row in yang_zhong["members"]
    }["杨忠"]["person_command_result"]["result_tier"] == "A"
    baideng_members = {
        row["actor_name"]: row
        for row in combined_by_id["WAR-LEAD-HAN-XIONGNU-BAIDENG"]["members"]
    }
    assert baideng_members["陈平"]["person_command_result"][
        "combat_difficulty"
    ] is None
    assert baideng_members["刘敬"]["person_command_index"][
        "consumption_mode"
    ] == "none"
    chencang_members = {
        row["actor_name"]: row
        for row in combined_by_id["WAR-LEAD-SG-SHU-CHENCANG-228"]["members"]
    }
    assert chencang_members["郝昭"]["person_command_result"][
        "result_direction"
    ] == "positive"
    assert chencang_members["诸葛亮"]["person_command_result"][
        "result_direction"
    ] == "negative"
    gaoguli_members = {
        row["actor_name"]: row
        for row in combined_by_id["WAR-LEAD-HAN-GAOGULI-121-122"]["members"]
    }
    assert gaoguli_members["冯焕"]["person_command_result"][
        "result_direction"
    ] == "negative"
    assert gaoguli_members["姚光"]["person_command_result"][
        "result_direction"
    ] == "negative"
    rouran_members = {
        row["actor_name"]: row
        for row in combined_by_id["WAR-LEAD-NC-WEI-RURAN-448-449"]["members"]
    }
    assert "拓跋濬" not in rouran_members
    assert rouran_members["拓跋焘"]["person_command_result"][
        "combat_difficulty"
    ] is None
    assert rouran_members["高凉王那"]["person_command_result"][
        "combat_difficulty"
    ] == "D4"
    hezhong_members = {
        row["actor_name"]: row
        for row in combined_by_id["WAR-LEAD-232-01"]["members"]
    }
    assert hezhong_members["马燧"]["person_command_result"][
        "result_direction"
    ] == "positive"
    assert hezhong_members["李怀光"]["person_command_result"][
        "result_direction"
    ] == "negative"
    jiangling_members = {
        row["actor_name"]: row
        for row in combined_by_id["WAR-LEAD-165-JIANGLING-554"]["members"]
    }
    assert jiangling_members["萧绎"]["actor_kind"] == "ruler"
    assert jiangling_members["萧绎"]["person_command_result"][
        "result_direction"
    ] == "negative"
    assert jiangling_members["杨忠"]["person_command_result"][
        "result_tier"
    ] == "A"
    assert jiangling_members["胡僧祐"]["person_command_result"][
        "combat_difficulty"
    ] == "D4"
    tibet_742_747 = combined_by_id["WAR-LEAD-TANG-TIBET-742-747"]
    assert tibet_742_747["disposition"] == "SPLIT_CAMPAIGN_PORTFOLIO"
    assert set(tibet_742_747["split_campaign_ids"]) == {
        "WAR-CONTRACT-TANG-TIBET-HUANGFU-742-743",
        "WAR-CONTRACT-TANG-WANGZHONGSI-QINGHAI-JISHI-746-747",
    }
    assert combined_by_id[
        "WAR-CONTRACT-TANG-WANGZHONGSI-QINGHAI-JISHI-746-747"
    ]["combat_difficulty"] == "D3"
    fancheng = combined_by_id["WAR-LEAD-HAN-FANCHENG-219"]
    jingzhou = combined_by_id["WAR-LEAD-HAN-JINGZHOU-219"]
    assert fancheng["campaign_tier"] == "A"
    assert fancheng["battle_result"] == "mixed"
    assert jingzhou["campaign_tier"] == "S-"
    assert {
        row["actor_name"]: row for row in jingzhou["members"]
    }["吕蒙"]["person_command_result"]["result_tier"] == "S-"
    yubi_members = {
        row["actor_name"]: row
        for row in combined_by_id["WAR-LEAD-159-04"]["members"]
    }
    assert combined_by_id["WAR-LEAD-159-04"]["campaign_tier"] == "A"
    assert combined_by_id["WAR-LEAD-159-04"]["combat_difficulty"] == "D4"
    assert yubi_members["韦孝宽"]["person_command_index"]["result_direction"] == "positive"
    assert yubi_members["韦孝宽"]["person_command_index"]["decisive_relation"] == "decisive_creator"
    assert yubi_members["高欢"]["person_command_result"]["result_direction"] == "negative"
    chaibi_members = {
        row["actor_name"]: row
        for row in combined_by_id["WAR-LEAD-112-CHAIBI-402"]["members"]
    }
    assert chaibi_members["拓跋珪"]["person_command_result"][
        "result_direction"
    ] == "positive"
    assert chaibi_members["姚平"]["person_command_result"][
        "result_direction"
    ] == "negative"
    assert combined_by_id["WAR-LEAD-231-02"]["campaign_tier"] == "S-"
    huang_chao_members = {
        row["actor_name"]: row
        for row in combined_by_id["WAR-LEAD-256-HUANGCHAO-END"]["members"]
    }
    assert (
        huang_chao_members["高骈"]["person_command_result"]["result_direction"],
        huang_chao_members["高骈"]["person_command_result"]["result_tier"],
        huang_chao_members["高骈"]["person_command_result"]["combat_difficulty"],
    ) == ("negative", "A", "D3")
    assert combined_by_id["WAR-LEAD-231-02"]["canonical_label"] == "李晟收复长安与朱泚政权覆亡"
    huan_chu = combined_by_id["WAR-LEAD-115-HUAN-REMNANTS-410"]
    assert huan_chu["campaign_tier"] == "S-"
    assert huan_chu["opponent_strategic_weight"] == "regional_major"
    assert huan_chu["result_class"] == "independent_direction"
    assert huan_chu["combat_difficulty"] == "D3"
    huan_chu_members = {row["actor_name"]: row for row in huan_chu["members"]}
    assert huan_chu_members["刘裕"]["person_command_result"]["result_tier"] == "S-"
    assert huan_chu_members["桓玄"]["command_result_direction"] == "negative"
    erzhu = combined_by_id["WAR-LEAD-155-05"]
    erzhu_members = {row["actor_name"]: row for row in erzhu["members"]}
    assert (erzhu["campaign_tier"], erzhu["result_class"]) == (
        "S",
        "single_pole_or_state_terminal",
    )
    assert erzhu_members["高欢"]["person_command_result"]["result_tier"] == "S"
    qi_liang = combined_by_id["WAR-LEAD-144-07"]
    assert (qi_liang["campaign_tier"], qi_liang["result_class"]) == (
        "S",
        "single_pole_or_state_terminal",
    )
    wang_jun = combined_by_id["JIN-SHILE-YOUZHOU-313-314"]
    assert (wang_jun["campaign_tier"], wang_jun["result_class"]) == (
        "A",
        "major_stage_or_crisis",
    )
    assert (
        wang_jun["land_strategic_value"],
        wang_jun["combat_difficulty"],
        {row["actor_name"]: row for row in wang_jun["members"]}["石勒"][
            "person_command_index"
        ]["projected_result_tier"],
    ) == ("local_point", "D3", "A")
    assert combined_by_id["JIN-LATER-ZHAO-YANCI-319-321"][
        "opponent_condition"
    ] == "residual"
    assert combined_by_id["WAR-LEAD-116-SOUTHLIANG-END-414"][
        "campaign_tier"
    ] == "S-"
    assert combined_by_id["WAR-LEAD-DUTAO-315"]["campaign_tier"] == "A"
    assert combined_by_id["WAR-LEAD-JIN-CHENMIN-305"]["campaign_tier"] == "S-"
    assert any(
        portfolio["portfolio_ref"] == "UCP-TANG-LIYUAN-617-628"
        and len(portfolio["campaign_groups"]) == 13
        for portfolio in combined["unification_portfolios"]
    )

    for portfolio_id, child_ids in {
        "WAR-LEAD-164-07": {
            "CAMPAIGN-NC-HOUJING-JIANKANG-548-549",
            "CAMPAIGN-NC-HOUJING-BALING-551",
            "CAMPAIGN-NC-HOUJING-JIANKANG-END-552",
        },
        "WAR-PARENT-SUI-GOGURYEO-611-614": {
            "CAMPAIGN-SUI-GOGURYEO-611-612",
            "CAMPAIGN-SUI-GOGURYEO-613",
            "CAMPAIGN-SUI-GOGURYEO-614",
        },
        "WAR-LEAD-TANG-SHIPU-749": {
            "CAMPAIGN-TANG-STONE-FORT-729",
            "CAMPAIGN-TANG-TIBET-HEXISHIPU-738-741",
            "CAMPAIGN-TANG-STONE-FORT-745-747",
            "CAMPAIGN-TANG-STONE-FORT-749",
        },
        "WAR-LEAD-161-01": {
            "CAMPAIGN-NC-HOUJING-WESTWEI-RECEIPT-547",
            "CAMPAIGN-NC-HANSHAN-PENGCHENG-547",
            "CAMPAIGN-NC-WOYANG-547-548",
        },
        "WAR-LEAD-157-08": {
            "CAMPAIGN-NC-XIAOGUAN-537",
            "CAMPAIGN-NC-SHAYUAN-537",
            "CAMPAIGN-NC-SHAYUAN-EXPANSION-537",
        },
        "WAR-LEAD-SUI-TURK-584-587": {
            "CAMPAIGN-SUI-TURK-WAR-581-583",
            "CAMPAIGN-SUI-TURK-SUBMISSION-584-587",
        },
        "WAR-LEAD-HAN-XIYU-73-94": {
            "CAMPAIGN-HAN-XIYU-OPENING-73-75",
            "CAMPAIGN-HAN-XIYU-BANCHAO-76-94",
        },
    }.items():
        portfolio = combined_by_id[portfolio_id]
        assert portfolio["disposition"] == "SPLIT_CAMPAIGN_PORTFOLIO"
        assert portfolio["public_outcome_registered"] is False
        assert set(portfolio["split_campaign_ids"]) == child_ids
        parent_cards = set(portfolio["source_lineage"]["source_card_ids"])
        child_card_sets = []
        for child_id in child_ids:
            child = combined_by_id[child_id]
            assert child["public_outcome_registered"] is True
            assert child["war_portfolio_ref"] == portfolio_id
            assert set(child["source_lineage"]["source_card_ids"]) <= parent_cards
            child_card_sets.append(set(child["source_lineage"]["source_card_ids"]))
        assert sum(map(len, child_card_sets)) == len(set().union(*child_card_sets))

    assert [
        combined_by_id[event_id]["campaign_tier"]
        for event_id in (
            "CAMPAIGN-NC-HOUJING-JIANKANG-548-549",
            "CAMPAIGN-NC-HOUJING-BALING-551",
            "CAMPAIGN-NC-HOUJING-JIANKANG-END-552",
        )
    ] == ["S-", "A", "S-"]
    assert [
        combined_by_id[event_id]["campaign_tier"]
        for event_id in (
            "CAMPAIGN-SUI-GOGURYEO-611-612",
            "CAMPAIGN-SUI-GOGURYEO-613",
            "CAMPAIGN-SUI-GOGURYEO-614",
        )
    ] == ["A", "A", "A"]
    assert [
        combined_by_id[event_id]["campaign_tier"]
        for event_id in (
            "CAMPAIGN-TANG-STONE-FORT-729",
            "CAMPAIGN-TANG-TIBET-HEXISHIPU-738-741",
            "CAMPAIGN-TANG-STONE-FORT-745-747",
            "CAMPAIGN-TANG-STONE-FORT-749",
        )
    ] == ["A", "A", "B", "A"]
    assert "龙驹岛" not in combined_by_id["CAMPAIGN-TANG-STONE-FORT-749"][
        "observable_result"
    ]
    assert [
        combined_by_id[event_id]["campaign_tier"]
        for event_id in (
            "CAMPAIGN-NC-HOUJING-WESTWEI-RECEIPT-547",
            "CAMPAIGN-NC-HANSHAN-PENGCHENG-547",
            "CAMPAIGN-NC-WOYANG-547-548",
        )
    ] == ["A", "A", "A"]
    assert not any(
        member["actor_name"] == "高欢"
        for event_id in (
            "CAMPAIGN-NC-HOUJING-WESTWEI-RECEIPT-547",
            "CAMPAIGN-NC-HANSHAN-PENGCHENG-547",
            "CAMPAIGN-NC-WOYANG-547-548",
        )
        for member in combined_by_id[event_id]["members"]
    )
    shayuan = combined_by_id["CAMPAIGN-NC-SHAYUAN-537"]
    assert (
        shayuan["campaign_tier"],
        shayuan["result_class"],
        shayuan["combat_difficulty"],
        shayuan["campaign_command_topology"],
    ) == ("S", "single_pole_decisive_defeat", "D4", "opposed_commands")
    shayuan_members = {member["actor_name"]: member for member in shayuan["members"]}
    assert shayuan_members["宇文泰"]["person_command_result"]["result_direction"] == "positive"
    assert shayuan_members["高欢"]["person_command_result"]["result_direction"] == "negative"
    later_zhao_terminal = combined_by_id[
        "JIN-LATER-ZHAO-FRONT-ZHAO-END-328-329"
    ]
    later_zhao_members = {
        member["actor_name"]: member for member in later_zhao_terminal["members"]
    }
    assert later_zhao_members["石勒"]["person_command_result"]["result_tier"] == "S"
    assert later_zhao_members["石勒"]["person_command_result"][
        "military_capability_contribution"
    ] == {
        "capability_mode": "integrated_command",
        "decisive_relation": "decisive_creator",
    }
    assert later_zhao_members["石虎"]["person_command_result"]["result_tier"] == "A"
    jin_wu = combined_by_id["WAR-LEAD-JIN-CONQUEST-WU-280"]
    wang_jun = next(member for member in jin_wu["members"] if member["actor_name"] == "王濬")
    assert (
        wang_jun["person_command_result"]["result_tier"],
        wang_jun["person_command_result"]["combat_difficulty"],
    ) == ("A", "D3")

    current = load_battle_registry(
        ROOT / "docs/公共成果/军事/01-战役登记.json"
    )
    scope = json.loads(
        (ROOT / "config/unification-campaign-scope-adjudications.json").read_text(
            encoding="utf-8"
        )
    )
    scoped_refs = {
        str(ref)
        for adjudication in scope["adjudications"]
        for ref in adjudication["war_event_refs"]
    }
    current_routed_refs = {
        str(row["war_event_id"]) for row in current["records"]
    } | {
        str(ref)
        for row in current["records"]
        for ref in (row.get("source_lineage") or {}).get("source_card_ids") or ()
    }
    assert scoped_refs.issubset(current_routed_refs)
    assert current["unification_scope_unresolved_count"] == 18

    assert len(records) == 1235
    assert result["ordinary_candidate_count"] == 1203
    assert result["ordinary_record_count"] == 1235
    assert len(by_id) == len(records)
    assert result["pending_count"] == 0
    assert result["prior_adjudication_count"] == 1201
    assert result["new_direct_compile_count"] == 2
    assert result["contract_adjudication_count"] == 961
    assert {
        candidate["war_event_id"]
        for candidate in worklist["candidates"]
        if candidate["war_event_id"] in by_id
        and "UNIFICATION_ONLY" in set(candidate.get("account_routing") or ())
    } == set(contract_adjudications.get("ordinary_route_overrides") or ())
    assert all(
        row["campaign_tier"] is not None
        for row in records
        if row["public_outcome_registered"]
    )
    assert not any(
        "FAST" in row["disposition"] for row in records
    )
    for merged in (
        row
        for row in records
        if row["disposition"] == "MERGED_INTO_PARENT"
        and row.get("contract_adjudication")
    ):
        target = by_id[merged["merged_into"]]
        assert target["public_outcome_registered"] is True
        assert merged["war_event_id"] in target["absorbed_event_ids"]
        assert set(merged["source_lineage"]["source_card_ids"]) <= set(
            target["source_lineage"]["source_card_ids"]
        )
    assert not any(
        not row.get("observable_result")
        or str(row["observable_result"]).startswith("未知")
        for row in records
        if row["public_outcome_registered"]
    )
    assert all(
        row["campaign_tier"] is None
        and row["source_lineage"]["source_card_ids"]
        for row in records
        if row["disposition"] == "EVIDENCE_ONLY_TERMINAL"
    )
    assert sum(
        row["disposition"] == "REGISTERED_FULL" for row in records
    ) == 119
    assert all(
        isinstance(row.get("members"), list)
        and isinstance(row.get("attributable_failures"), list)
        and row.get("ruler_role_status") in {"resolved", "unresolved"}
        and row.get("ruler_role_basis")
        and row.get("detail_expansion_status") == "COMPLETE"
        for row in records
        if row["disposition"] == "REGISTERED_FULL"
    )
    assert all(
        TIER_BY_RESULT_CLASS[row["result_class"]]
        == row["campaign_tier"]
        and row["land_strategic_value"] in VALID_LAND_AXIS
        and row["opponent_strategic_weight"] in VALID_OPPONENT_WEIGHT
        and row["opponent_condition"] in VALID_OPPONENT_CONDITION
        and row["battle_result"] in VALID_BATTLE_RESULT
        and row["objective_completion"] in VALID_OBJECTIVE_COMPLETION
        and row["tier_basis"]
        and row["source_refs"]
        for row in records
        if row["public_outcome_registered"]
    )
    assert (
        by_id["WAR-LEAD-100-GUANGGU-355-356"]["disposition"]
        == "REGISTERED_CONTRACT"
    )
    assert by_id["WAR-LEAD-100-GUANGGU-355-356"]["campaign_tier"] == "S-"
    assert by_id["WAR-LEAD-100-GUANGGU-355-356"]["combat_difficulty"] == "D3"
    assert (
        by_id["WAR-LEAD-SG-WEI-LIAODONG-238"]["campaign_tier"],
        by_id["WAR-LEAD-SG-WEI-LIAODONG-238"]["result_class"],
        by_id["WAR-LEAD-SG-WEI-LIAODONG-238"]["land_strategic_value"],
    ) == ("A", "major_stage_or_crisis", "important_region")
    assert (
        by_id["WAR-LEAD-CHENAN-END-323"]["campaign_tier"],
        by_id["WAR-LEAD-CHENAN-END-323"]["result_class"],
    ) == ("A", "major_stage_or_crisis")
    assert all(
        (
            by_id[war_event_id]["campaign_tier"],
            by_id[war_event_id]["result_class"],
        )
        == ("A", "major_stage_or_crisis")
        for war_event_id in ("WAR-LEAD-DUTAO-315", "WAR-LEAD-DUZENG-END-319")
    )
    assert by_id["WAR-LEAD-SG-WU-LIAOSHI-239-240"]["campaign_tier"] == "B"
    assert by_id["WAR-LEAD-SG-WU-JIAOZHOU-226"]["campaign_tier"] == "B"
    assert (
        by_id["WAR-LEAD-098-LIANGDU-349"]["campaign_tier"],
        by_id["WAR-LEAD-108-CANHE-395"]["campaign_tier"],
        by_id["WAR-LEAD-110-SOUTHLIANG-LINGNAN-398"]["campaign_tier"],
        by_id["WAR-LEAD-NC-YUCHIJIONG-580"]["campaign_tier"],
        by_id["WAR-LEAD-HAN-YANZHOU-LUBU-194-195"]["campaign_tier"],
        by_id["WAR-LEAD-098-YAN-350"]["campaign_tier"],
        by_id["WAR-LEAD-109-ZHONGSHAN-397"]["campaign_tier"],
        ) == ("A", "S", "A", "A", "A", "A", "A")
    assert by_id["WAR-LEAD-108-CANHE-395"]["combat_difficulty"] == "D3"
    assert by_id["WAR-LEAD-105-FEISHUI-383"]["combat_difficulty"] == "D4"
    assert by_id["WAR-LEAD-115-LIUYU-SOUTHYAN-409"]["combat_difficulty"] == "D3"
    assert by_id["WAR-LEAD-HAN-NANYUE-112-111"]["campaign_tier"] == "S-"
    assert by_id["WAR-LEAD-TANG-GOGURYEO-666-669"]["campaign_tier"] == "S"
    west_qin_longxi = by_id["WAR-LEAD-108-WESTQIN-LONGXI-394"]
    assert west_qin_longxi["campaign_command_topology"] == "federated_directions"
    assert all(
        member["role_code"] == "principal_commander"
        for member in west_qin_longxi["members"]
    )
    assert next(
        member
        for member in by_id["WAR-LEAD-118-LIUYU-QIN-417"]["members"]
        if member["actor_kind"] == "ruler"
    )["actor_name"] == "司马德宗"
    assert next(
        member
        for member in by_id["WAR-LEAD-256-HUANGCHAO-END"]["members"]
        if member["actor_kind"] == "ruler"
    )["actor_name"] == "李儇"
    assert by_id["WAR-LEAD-132-02"]["ruler_role_status"] == "unresolved"
    assert by_id["WAR-LEAD-144-07"]["ruler_role_status"] == "unresolved"
    assert by_id["WAR-LEAD-252-04"]["ruler_role_status"] == "unresolved"
    assert by_id["WAR-LEAD-HAN-ZHIZHI-44-36"]["ruler_role_status"] == "unresolved"
    assert by_id["WAR-LEAD-TANG-LIANCHENG-715"]["ruler_role_status"] == "unresolved"
    assert (
        by_id["WAR-LEAD-TANG-LIANCHENG-715"]["campaign_tier"],
        by_id["CAMPAIGN-SUI-TURK-SUBMISSION-584-587"]["campaign_tier"],
    ) == ("A", "A")
    assert by_id["WAR-LEAD-TANG-TUYUHUN-634-635"]["combat_difficulty"] == "D3"
    assert by_id["WAR-LEAD-HAN-MOBEI-119"]["combat_difficulty"] == "D3"
    assert all(
        by_id[war_event_id]["combat_difficulty"] == "D2"
        for war_event_id in (
            "WAR-LEAD-256-ZHEDONG-END",
            "WAR-LEAD-259-XUBIAN-END",
            "WAR-LEAD-NC-NORTHERN-LIANG-WESTERN-LIANG",
            "WAR-LEAD-TANG-ANXI-708",
        )
    )
    assert all(
        by_id[war_event_id]["combat_difficulty"] == "D3"
        for war_event_id in (
            "WAR-LEAD-097-HUANSHU-346-347",
            "WAR-LEAD-100-GUANGGU-355-356",
            "WAR-LEAD-116-LIUYU-SHU-413",
            "WAR-LEAD-108-DIWEI-392",
            "WAR-LEAD-111-LATERCIN-WESTQIN-400",
            "WAR-LEAD-261-BIANYUN-END",
            "WAR-LEAD-264-PINGLU-END",
            "WAR-LEAD-HAN-JIAOZHI-40-43",
            "WAR-LEAD-HAN-XIYU-119-127",
            "WAR-LEAD-QIN-XIONGNU-WALL",
            "WAR-LEAD-TANG-BAEKJE-663",
        )
    )
    assert by_id["WAR-LEAD-249-02"]["combat_difficulty"] == "D1"
    assert (
        by_id["WAR-LEAD-151-07"]["battle_result"],
        by_id["WAR-LEAD-151-07"]["objective_completion"],
        by_id["WAR-LEAD-151-07"]["combat_difficulty"],
        by_id["WAR-LEAD-151-07"]["campaign_command_topology"],
    ) == ("victory", "complete", "D3", "single_integrated_command")
    assert by_id["WAR-LEAD-QIUCHI-323"]["combat_difficulty"] == "D2"
    assert by_id["WAR-LEAD-ZHAO-LUOYANG-328"]["combat_difficulty"] == "D3"
    assert by_id["WAR-LEAD-112-CHAIBI-402"]["combat_difficulty"] == "D3"
    assert (
        by_id["WAR-LEAD-156-01"]["campaign_tier"],
        by_id["WAR-LEAD-TANG-XIZHOU-724"]["campaign_tier"],
        by_id["WAR-LEAD-149-05"]["campaign_tier"],
    ) == ("B", "B", "B")
    assert all(
        by_id[war_event_id]["combat_difficulty"] == "D4"
        for war_event_id in (
            "WAR-LEAD-259-HUAINAN-END",
            "WAR-LEAD-HAN-YOUZHOU-LIUYU-193",
        )
    )
    assert by_id["WAR-LEAD-111-LATERCIN-WESTQIN-400"]["campaign_tier"] == "A"
    assert by_id["WAR-LEAD-HAN-WUHUAN-206-207"]["combat_difficulty"] == "D3"
    assert by_id["CAMPAIGN-HAN-XIYU-BANCHAO-76-94"]["campaign_tier"] == "S-"
    assert by_id["WAR-LEAD-HAN-XIYU-119-127"]["campaign_tier"] == "S-"
    assert (
        by_id["WAR-LEAD-TANG-TIBET-FOUR-GARRISONS-692-696"]["campaign_tier"]
        == "S-"
    )
    assert all(
        next(
            member
            for member in by_id[war_event_id]["members"]
            if member["actor_kind"] == "ruler"
        )["actor_name"]
        == "李治"
        for war_event_id in (
            "WAR-LEAD-TANG-BAEKJE-663",
            "WAR-LEAD-TANG-WESTERN-TURKS-656-658",
        )
    )
    assert all(
        by_id[war_event_id]["ruler_role_status"] == "resolved"
        and any(
            member["actor_kind"] == "ruler"
            and member["ruler_campaign_relation"] == "authorization_only"
            for member in by_id[war_event_id]["members"]
        )
        for war_event_id in (
            "WAR-LEAD-103-QIN-SHU-373",
            "WAR-LEAD-105-FEISHUI-383",
            "WAR-LEAD-241-01",
            "WAR-LEAD-SG-WU-HAN-YILING-221-222",
            "WAR-LEAD-TANG-GOGURYEO-666-669",
        )
    )
    assert by_id["WAR-LEAD-QIN-CIVIL-WAR"]["campaign_tier"] == "S"
    assert (
        by_id["WAR-LEAD-TANG-GOGURYEO-645"]["opponent_force_effect"]
        == "main_force_destroyed"
    )
    goguryeo_645 = by_id["WAR-LEAD-TANG-GOGURYEO-645"]
    assert (
        goguryeo_645["campaign_tier"],
        goguryeo_645["result_class"],
        goguryeo_645["battle_result"],
        goguryeo_645["objective_completion"],
        goguryeo_645["ruler_role_status"],
    ) == ("S-", "independent_direction", "mixed", "partial", "resolved")
    assert goguryeo_645["objective_shortfalls"] == [
        {
            "basis": "安市未克，入冬前撤军，高丽政权核心未被终结。",
            "source_refs": ["資治通鑑/卷198@1502841"],
        }
    ]
    goguryeo_members = {
        member["actor_name"]: member for member in goguryeo_645["members"]
    }
    assert goguryeo_members["李世民"]["actor_kind"] == "ruler"
    assert goguryeo_members["李世民"]["ruler_campaign_relation"] == "frontline_command"
    assert goguryeo_members["李世民"]["person_command_result"]["result_tier"] == "S-"
    assert all(
        goguryeo_members[name]["person_command_result"]["result_tier"] == "A"
        and goguryeo_members[name]["person_command_index"]["consumption_mode"]
        == "person_result"
        for name in ("李世勣", "长孙无忌")
    )
    goguryeo_failures = {
        failure["actor_name"]: failure
        for failure in goguryeo_645["attributable_failures"]
    }
    assert (
        goguryeo_failures["李道宗"]["responsibility"],
        goguryeo_failures["李道宗"]["severity_index"],
        goguryeo_failures["李道宗"]["failure_impact_tier"],
    ) == ("shared", 0.7, "A")
    assert (
        goguryeo_failures["傅伏爱"]["responsibility"],
        goguryeo_failures["傅伏爱"]["failure_impact_tier"],
    ) == ("primary", "A")
    assert (
        combined_by_id["WAR-LEAD-TANG-LIUHEITA-622"]["opponent_force_effect"]
        == "main_force_destroyed"
    )
    assert combined_by_id[
        "HAN-CHUHAN-GUANZHONG-ENTRY-BCE207-206"
    ]["objective_shortfalls"]
    assert (
        by_id["WAR-LEAD-226-01"]["campaign_tier"],
        by_id["WAR-LEAD-226-01"]["combat_difficulty"],
        by_id["WAR-LEAD-226-01"]["opponent_force_effect"],
    ) == ("S-", "D3", "main_force_destroyed")
    assert (
        by_id["WAR-LEAD-104-HUAINAN-378-379"]["opponent_force_effect"]
        == "main_force_destroyed"
    )
    assert next(
        member
        for member in by_id["WAR-LEAD-HANMIAN-317"]["members"]
        if member["actor_name"] == "周访"
    )["person_command_index"]["projected_result_tier"] == "A"
    for war_event_id, successor in (
        ("WAR-LEAD-252-04", "高骈"),
        ("WAR-LEAD-TANG-ANRONG-738-740", "许远"),
    ):
        row = by_id[war_event_id]
        assert row["campaign_command_topology"] == "sequential_successor_command"
        successor_member = next(
            member for member in row["members"] if member["actor_name"] == successor
        )
        assert successor_member["role_code"] == "commander_in_chief"
        assert (
            successor_member["person_command_index"]["consumption_mode"]
            == "full_parent"
        )
    assert next(
        failure
        for failure in by_id["WAR-LEAD-TANG-TIELE-661-662"][
            "attributable_failures"
        ]
        if failure["actor_name"] == "郑仁泰"
    )["failure_impact_tier"] == "A"
    assert by_id["WAR-LEAD-261-HUNAN-END"]["disposition"] == "EXCLUDED_UNIFICATION"
    assert not by_id["WAR-LEAD-261-HUNAN-END"]["public_outcome_registered"]
    assert by_id["WAR-LEAD-QIN-LINGNAN"]["disposition"] == "EXCLUDED_UNIFICATION"
    assert by_id["WAR-LEAD-HAN-SHANGYONG-219"]["disposition"] == "EXCLUDED_UNIFICATION"
    assert by_id["WAR-LEAD-SG-WEI-SHANGYONG-220"]["disposition"] == "EXCLUDED_UNIFICATION"
    assert (
        by_id["WAR-LEAD-HAN-MAYI-133"]["disposition"]
        == "REDIRECTED_NON_BATTLE_OUTCOME"
    )
    assert (
        by_id["WAR-LEAD-NC-QINLONG-436"]["disposition"]
        == "REDIRECTED_NON_BATTLE_OUTCOME"
    )
    assert by_id["WAR-LEAD-JINWU-268"]["disposition"] == "REDIRECTED_MIXED_PARENT"
    assert by_id["WAR-LEAD-SG-WU-YIZHOU-230-231"]["campaign_tier"] == "B"
    assert (
        by_id["WAR-LEAD-SG-WU-YIZHOU-230-231"]["result_class"]
        == "important_objective"
    )
    assert (
        by_id["WAR-LEAD-TANG-EASTERN-TURKS-629-630"]["campaign_tier"]
        == "S+"
    )
    assert (
        by_id["WAR-LEAD-TANG-EASTERN-TURKS-629-630"]["result_class"]
        == "external_hegemony_terminal"
    )
    assert (
        by_id["WAR-LEAD-TANG-EASTERN-TURKS-629-630"]["combat_difficulty"]
        == "D3"
    )
    eastern_turks_members = {
        member["actor_name"]: member
        for member in by_id["WAR-LEAD-TANG-EASTERN-TURKS-629-630"]["members"]
    }
    assert eastern_turks_members["李靖"]["person_command_result"][
        "combat_difficulty"
    ] == "D3"
    assert by_id["WAR-LEAD-HAN-MOBEI-119"]["campaign_tier"] == "S"
    assert (
        by_id["WAR-LEAD-HAN-MOBEI-119"]["result_class"]
        == "external_hegemony_decisive_defeat"
    )
    assert by_id["WAR-LEAD-HAN-HEXICORRIDOR-121"]["combat_difficulty"] == "D3"
    mobei_members = {
        member["actor_name"]: member
        for member in by_id["WAR-LEAD-HAN-MOBEI-119"]["members"]
    }
    assert mobei_members["霍去病"]["person_command_result"][
        "combat_difficulty"
    ] == "D3"
    western_han_xiongnu_ids = {
        "WAR-LEAD-HAN-HENAN-SHUFANG",
        "WAR-LEAD-HAN-HEXICORRIDOR-121",
        "WAR-LEAD-HAN-MOBEI-119",
        "WAR-LEAD-HAN-XIONGNU-124-123",
        "WAR-LEAD-HAN-XIONGNU-129/128/126-125",
        "WAR-LEAD-HAN-XIONGNU-BAIDENG",
    }
    assert all(
        by_id[war_event_id]["opponent_strategic_weight"]
        == "external_hegemony"
        for war_event_id in western_han_xiongnu_ids
    )
    post_mobei_xiongnu_ids = {
        "WAR-LEAD-HAN-CHESHI-67-64",
        "WAR-LEAD-HAN-XIONGNU-90",
        "WAR-LEAD-HAN-ZHAOPONU-103",
    }
    assert all(
        by_id[war_event_id]["opponent_strategic_weight"] == "external_state"
        for war_event_id in post_mobei_xiongnu_ids
    )
    assert all(
        row["external_hegemony_prewar_assessment"]
        and all(
            row["external_hegemony_prewar_assessment"].get(key) is True
            for key in (
                "sustained_core_pressure",
                "national_security_order_reoriented",
                "existential_capability",
            )
        )
        for row in records
        if row.get("opponent_strategic_weight") == "external_hegemony"
        and row.get("public_outcome_registered")
    )
    assert by_id["WAR-LEAD-HAN-XIONGNU-BAIDENG"]["combat_difficulty"] == "D3"
    for war_event_id, actor_name, tier, difficulty in (
            ("CAMPAIGN-HAN-XIYU-BANCHAO-76-94", "班超", "S-", "D3"),
        ("WAR-LEAD-HAN-XIYU-119-127", "班勇", "S-", "D3"),
        ("WAR-LEAD-251-04", "康承训", "A", "D3"),
    ):
        member = next(
            member
            for member in by_id[war_event_id]["members"]
            if member["actor_name"] == actor_name
        )
        assert member["person_command_index"]["consumption_mode"] == "full_parent"
        assert member["person_command_index"]["projected_result_tier"] == tier
        assert (
            member["person_command_index"]["projected_combat_difficulty"]
            == difficulty
        )
    houjing_campaign = by_id["CAMPAIGN-NC-HOUJING-JIANKANG-548-549"]
    assert houjing_campaign["campaign_command_topology"] == "opposed_commands"
    houjing_members = {
        member["actor_name"]: member["person_command_index"]
        for member in houjing_campaign["members"]
    }
    assert houjing_members["侯景"]["projected_result_tier"] == "S-"
    assert houjing_members["侯景"]["result_direction"] == "positive"
    assert houjing_members["柳仲礼"]["projected_result_tier"] == "A"
    assert houjing_members["柳仲礼"]["result_direction"] == "negative"
    taokan = next(
        member
        for member in by_id["WAR-LEAD-SUJUN-END-329"]["members"]
        if member["actor_name"] == "陶侃"
    )
    assert taokan["person_command_index"]["projected_result_tier"] == "S-"
    assert taokan["person_command_index"]["projected_combat_difficulty"] == "D3"
    assert all(
        member["person_command_index"]["consumption_mode"] != "none"
        or member["person_command_index"]["capability_mode"] == "nominal_only"
        for row in records
        if row["public_outcome_registered"]
        and row["campaign_tier"] in {"S-", "S", "S+"}
        for member in row.get("members") or ()
        if member["role_code"] == "commander_in_chief"
    )
    assert all(
        member["person_command_index"]["capability_mode"]
        == "integrated_command"
        for row in records
        if row["public_outcome_registered"]
        for member in row.get("members") or ()
        if member["person_command_index"]["consumption_mode"] == "full_parent"
    )
    assert by_id["WAR-LEAD-TANG-EASTERN-TURKS-629-630"]["period"] == {
        "start": "629年",
        "end": "630年",
    }
    assert by_id["WAR-LEAD-TANG-ANSHI-END"]["campaign_tier"] == "S-"
    assert (
        by_id["WAR-LEAD-TANG-ANSHI-END"]["canonical_label"]
        == "安史政权终结战役群"
    )
    assert by_id["WAR-LEAD-TANG-ANSHI-END"]["period"] == {
        "start": "755年",
        "end": "763年",
    }
    assert by_id["WAR-LEAD-165-WULING-553"]["campaign_tier"] == "A"
    assert by_id["WAR-LEAD-118-NORTHWESTLIANG-417"]["campaign_tier"] == "B"
    chaoge = by_id["WAR-LEAD-HAN-CHAOGE-110"]
    assert chaoge["campaign_tier"] == "C"
    assert chaoge["combat_difficulty"] == "D2"
    assert chaoge["detail_expansion_status"] == "COMPLETE"
    assert chaoge["ruler_role_status"] == "unresolved"
    assert chaoge["attributable_failures"] == []
    assert [
        (member["actor_name"], member["role_code"])
        for member in chaoge["members"]
    ] == [("虞诩", "commander_in_chief")]
    assert (
        chaoge["members"][0]["person_command_index"]["consumption_mode"]
        == "full_parent"
    )
    assert (
        by_id["WAR-LEAD-162-08"]["disposition"]
        == "REDIRECTED_NON_BATTLE_OUTCOME"
    )
    assert (
        by_id["WAR-LEAD-HAN-QINGHE-147"]["disposition"]
        == "EXCLUDED_BELOW_PUBLIC_THRESHOLD"
    )
    assert (
        by_id["WAR-LEAD-XIN-LIUCHONG-6"]["disposition"]
        == "EXCLUDED_BELOW_PUBLIC_THRESHOLD"
    )
    assert (
        by_id["WAR-LEAD-226-02"]["disposition"]
        == "REDIRECTED_MIXED_PARENT"
    )
    assert (
        by_id["WAR-LEAD-HAN-JING-TAISHAN-141-142"]["disposition"]
        == "REDIRECTED_NON_BATTLE_OUTCOME"
    )
    assert (
        by_id["WAR-PARENT-NC-QI-COUPS-494"]["disposition"]
        == "REDIRECTED_MIXED_PARENT"
    )
    bowang = by_id["WAR-LEAD-HAN-BOWANG-202"]
    assert (bowang["campaign_tier"], bowang["combat_difficulty"]) == (
        "C",
        "D2",
    )
    assert bowang["members"][0]["actor_name"] == "刘备"
    assert (
        bowang["members"][0]["person_command_index"]["consumption_mode"]
        == "full_parent"
    )
    assert [
        (failure["actor_name"], failure["responsibility"])
        for failure in bowang["attributable_failures"]
    ] == [("夏侯惇", "primary")]
    baima = by_id["WAR-LEAD-HAN-BAIMA-QIANG-148"]
    assert (baima["campaign_tier"], baima["combat_difficulty"]) == (
        "C",
        "D1",
    )
    assert baima["campaign_command_topology"] == "command_unresolved"
    assert baima["members"] == []
    liuzhou = by_id["WAR-LEAD-SG-SHU-LIUZHOU-233"]
    assert (liuzhou["campaign_tier"], liuzhou["combat_difficulty"]) == (
        "C",
        "D1",
    )
    assert [
        (
            member["actor_name"],
            member["role_code"],
            member["person_command_index"]["consumption_mode"],
        )
        for member in liuzhou["members"]
    ] == [
        ("马忠", "commander_in_chief", "full_parent"),
        ("张翼", "participant", "none"),
    ]
    assert (
        by_id["WAR-LEAD-SG-JUSHUI-CANCEL-261"]["disposition"]
        == "REDIRECTED_NON_BATTLE_OUTCOME"
    )
    assert (
        by_id["WAR-LEAD-SG-SHU-WEIYAN-234"]["disposition"]
        == "REDIRECTED_MIXED_PARENT"
    )
    assert (
        by_id["WAR-LEAD-237-04"]["disposition"]
        == "EXCLUDED_BELOW_PUBLIC_THRESHOLD"
    )
    yuezhi = by_id["WAR-LEAD-HAN-YUEZHI-90"]
    assert (yuezhi["campaign_tier"], yuezhi["combat_difficulty"]) == (
        "B",
        "D3",
    )
    assert yuezhi["members"][0]["actor_name"] == "班超"
    assert (
        yuezhi["members"][0]["person_command_index"]["consumption_mode"]
        == "full_parent"
    )
    tiele = by_id["WAR-LEAD-TANG-TIELE-INTEGRATION"]
    assert tiele["disposition"] == "REGISTERED_CONTRACT"
    assert (tiele["campaign_tier"], tiele["result_class"]) == (
        "S-",
        "independent_direction",
    )
    tiele_members = {row["actor_name"]: row for row in tiele["members"]}
    assert (
        tiele_members["李世民"]["person_command_index"]["consumption_mode"],
        tiele_members["李世民"]["person_command_index"]["capability_mode"],
        tiele_members["李世民"]["person_command_index"]["projected_result_tier"],
        tiele_members["李世民"]["person_command_index"][
            "projected_combat_difficulty"
        ],
    ) == ("operational_result", "operational_design", "S-", None)
    assert "資治通鑑/卷198@1502841" in tiele_members["李世民"][
        "person_command_index"
    ]["source_refs"]
    goguryeo_658 = by_id["WAR-LEAD-TANG-GOGURYEO-658-662"]
    assert goguryeo_658["disposition"] == "REGISTERED_CONTRACT"
    assert (goguryeo_658["campaign_tier"], goguryeo_658["combat_difficulty"]) == (
        "A",
        "D3",
    )
    assert (
        by_id["WAR-LEAD-QIN-XIONGNU-WALL"]["disposition"]
        == "REGISTERED_CONTRACT"
    )
    assert by_id["WAR-LEAD-QIN-XIONGNU-WALL"]["campaign_tier"] == "S-"
    assert by_id["WAR-LEAD-QIN-XIONGNU-WALL"]["combat_difficulty"] == "D3"


def test_unification_full_parent_cannot_exceed_or_undershoot_parent(
    tmp_path: Path,
) -> None:
    source = json.loads(
        (ROOT / "config/unification-campaign-tier-adjudications.json").read_text(
            encoding="utf-8"
        )
    )
    hedong = next(
        group
        for portfolio in source["adjudications"]
        for group in portfolio["campaign_groups"]
        if group["campaign_group_id"] == "WAR-LEAD-TANG-HEDONG-RECOVERY"
    )
    hedong["members"][0]["person_command_index"]["projected_result_tier"] = "S"
    broken = tmp_path / "full-parent-tier-mismatch.json"
    broken.write_text(
        json.dumps(source, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="完整父级消费必须与父战役档位和难度一致"):
        load_unification_tier_adjudications(broken)


def _load_current_first_item_c_inputs() -> dict[str, dict]:
    def load(relative_path: str) -> dict:
        return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))

    return {
        "battle_registry": load_battle_registry(
            ROOT / "docs/公共成果/军事/01-战役登记.json"
        ),
        "talent_registry": load_talent_registry(
            ROOT / "docs/公共成果/军事/02-武将人才等级.json"
        ),
        "roster": load_qin_qing_first_item_roster(
            ROOT, load("config/first-item-a-strategic-efficiency-inputs.json")
        ),
        "scope_inputs": load("config/first-item-a-strategic-efficiency-inputs.json"),
        "window_config": load("config/first-item-c-acquisition-windows.json"),
        "control_registry": load(
            "config/first-item-c-territorial-control-adjudications.json"
        ),
    }


def test_first_item_c_control_is_private_to_c_and_fully_calibrated() -> None:
    inputs = _load_current_first_item_c_inputs()
    public = inputs["battle_registry"]
    assert "territorial_control_pending_count" not in public
    assert "campaign_tier_recalibration_pending_count" not in public
    assert all(
        "territorial_control_result" not in row
        for row in public["unification_portfolios"]
    )

    summary = validate_first_item_c_territorial_control(
        battle_registry=public,
        window_config=inputs["window_config"],
        control_registry=inputs["control_registry"],
    )
    assert summary["portfolio_count"] == 30
    assert summary["manual_window_count"] == 14
    assert summary["pending_window_count"] == 0
    assert summary["pending_portfolio_refs"] == []
    assert summary["pending_manual_rulers"] == []
    assert summary["missing_profile_refs"] == {}
    assert len(inputs["control_registry"]["manual_window_adjudications"]) == 14
    assert summary["raw_net_control"]["MANUAL:冉闵"] == -1.0
    assert summary["raw_net_control"]["MANUAL:姚苌"] == 0.0
    assert summary["raw_net_control"]["MANUAL:苻坚"] > summary[
        "raw_net_control"
    ]["MANUAL:高欢"]
    liu_bang = next(
        row
        for row in inputs["control_registry"]["portfolio_adjudications"]
        if row["portfolio_ref"] == "UCP-HAN-LIUBANG-BCE207-BCE202"
    )
    assert liu_bang["value_era_id"] == "C-ERA-QIN-CHUHAN-BCE230-BCE202"
    assert liu_bang["region_value_overrides"] == []
    assert all(
        "region_profiles" not in row
        for section in ("portfolio_adjudications", "manual_window_adjudications")
        for row in inputs["control_registry"][section]
    )
    assert len(inputs["control_registry"]["value_era_catalog"]) == 8
    assert len(inputs["control_registry"]["era_region_value_profiles"]) == 120
    assert summary["baseline_profile_status_counts"] == {
        "CALIBRATED": 76,
        "PENDING_SOURCE": 44,
    }
    assert summary["profile_status_counts"] == {"CALIBRATED": 132}
    assert sum(summary["profile_status_counts"].values()) == sum(
        sum(
            1
            for region_id in {
                *(item["region_id"] for item in row["baseline_snapshot"]),
                *(item["region_id"] for item in row["terminal_snapshot"]),
            }
            if next(
                (
                    item["control_fraction"]
                    for item in row["baseline_snapshot"]
                    if item["region_id"] == region_id
                ),
                0,
            )
            != next(
                (
                    item["control_fraction"]
                    for item in row["terminal_snapshot"]
                    if item["region_id"] == region_id
                ),
                0,
            )
        )
        for section in ("portfolio_adjudications", "manual_window_adjudications")
        for row in inputs["control_registry"][section]
    )
    net = summary["raw_net_control"]
    assert net["UCP-TANG-LIYUAN-617-628"] > net["UCP-HAN-LIUXIU-23-36"]
    assert net["UCP-HAN-LIUXIU-23-36"] >= net[
        "UCP-HAN-LIUBANG-BCE207-BCE202"
    ]
    assert net["UCP-HAN-LIUBANG-BCE207-BCE202"] > net[
        "UCP-QIN-YINGZHENG-230-221"
    ]
    assert net["UCP-QIN-YINGZHENG-230-221"] > 2 * net[
        "UCP-SUI-YANGJIAN-587-591"
    ]


def test_first_item_c_registry_is_complete_and_matches_calibration_anchors() -> None:
    inputs = _load_current_first_item_c_inputs()
    payload = build_first_item_c_registry(**inputs)
    markdown = render_first_item_c_registry_markdown(payload)
    assert payload["record_count"] == 185
    assert payload["score_ready_count"] == 185
    assert payload["eligible_count"] == 77
    assert payload["excluded_count"] == 108
    assert payload["pending_count"] == 0
    assert payload["default_count"] >= 3
    assert sum(payload["coverage_status_counts"].values()) == 185
    assert all(row["score_ready"] for row in payload["records"])
    assert all(row["unresolved_gaps"] == [] for row in payload["records"])
    assert payload["schema_version"] == "first-item-c-registry-v3"
    assert "C1战役成果指数（非得分率）" in markdown
    assert "C1实际得分" in markdown
    assert payload["canonical_status"] == "CURRENT"
    assert "C2_bands" not in payload["method"]
    assert all(
        row["C2"]["peak_quality_index"] <= 7.5
        for row in payload["records"]
        if row["score_applicable"]
    )
    assert {
        row["ruler_name"]
        for row in payload["records"]
        if row["default_applied"]
    } >= {"李雄", "刘玄", "冯跋"}

    by_name = {row["ruler_name"]: row for row in payload["records"]}
    assert by_name["李世民"]["canonical_rank"] < by_name["刘裕"]["canonical_rank"]
    assert by_name["刘裕"]["canonical_rank"] < by_name["刘秀"]["canonical_rank"]
    assert by_name["刘秀"]["canonical_rank"] < by_name["曹操"]["canonical_rank"]
    assert by_name["曹操"]["canonical_rank"] < by_name["刘邦"]["canonical_rank"]
    assert by_name["刘秀"]["C1"]["raw_index"] == 37.0
    assert by_name["曹操"]["C1"]["raw_index"] == 34.0
    assert by_name["刘邦"]["C1"]["raw_index"] == 14.0
    assert payload["method"]["C1_result_values"] == {
        "C": 1, "B": 2, "A": 4, "S-": 6, "S": 9, "S+": 18,
    }
    assert payload["method"]["C1_position_cutoffs"] == {"5": [36.0, 42.0]}
    assert payload["method"]["C2_rate_table"]["5"] == {
        "LOW": 84, "MID": 92, "HIGH": 100,
    }
    assert by_name["李世民"]["C1"]["raw_index"] == 42.0
    assert by_name["李世民"]["C1"]["position"] == "HIGH"
    assert by_name["刘裕"]["C1"]["raw_index"] == 40.0
    assert by_name["刘裕"]["C1"]["position"] == "MID"
    assert {
        row["ruler_name"]
        for row in payload["records"]
        if row["score_applicable"] and row["C2"]["grade"] == 5
    } >= {"李世民", "刘裕", "铁木真", "李存勖", "忽必烈"}
    assert by_name["李世民"]["C2"]["peak_quality_index"] == 7.2
    assert by_name["李世民"]["C2"]["position"] == "HIGH"
    assert by_name["李世民"]["C2"]["points"] == 30.0
    assert by_name["刘裕"]["C2"]["position"] == "LOW"
    assert by_name["刘裕"]["C2"]["points"] == 25.2
    assert by_name["高欢"]["C2"]["peak_quality_index"] == 6.2
    assert by_name["高欢"]["C2"]["grade"] == 4
    assert by_name["高欢"]["C2"]["position"] == "HIGH"
    assert by_name["高欢"]["C2"]["positive_context_count"] == 2
    assert by_name["刘邦"]["C2"]["negative_context_count"] == 1
    assert by_name["刘邦"]["C2"]["grade_cap"] == 4
    assert by_name["石勒"]["C2"]["negative_context_count"] == 2
    assert by_name["曹操"]["C2"]["positive_context_count"] == 9
    assert by_name["曹操"]["C2"]["negative_context_count"] == 3
    assert by_name["曹操"]["C2"]["command_failure_count"] == 1
    assert by_name["曹操"]["C2"]["grade"] == 4
    assert by_name["曹操"]["C2"]["position"] == "LOW"
    assert {
        row["campaign_group_id"]
        for row in by_name["郭威"]["C1"]["campaign_results"]
    } == {"WAR-FD-4EB2D06F9A06F863C24A"}
    assert {
        row["campaign_group_id"]
        for row in by_name["柴荣"]["C1"]["campaign_results"]
    } == {
        "WAR-FD-5BBD5B7C2142B0068991",
        "WAR-FD-94BC9E431A3BAF3AC07C",
    }
    for row in payload["records"]:
        if not row["score_applicable"]:
            continue
        for axis in ("C1", "C2"):
            results = (
                row[axis]["campaign_results"]
                if axis == "C1"
                else row[axis]["frontline_results"]
            )
            parent_directions = [
                (result["campaign_group_id"], result["result_direction"])
                for result in results
            ]
            assert len(parent_directions) == len(set(parent_directions))
    for ruler_name in ("王建", "朱温"):
        for axis, field in (("C1", "campaign_results"), ("C2", "frontline_results")):
            parent_directions = [
                (result["campaign_group_id"], result["result_direction"])
                for result in by_name[ruler_name][axis][field]
            ]
            assert len(parent_directions) == len(set(parent_directions))
    assert {
        result["result_direction"]
        for result in by_name["刘秀"]["C1"]["campaign_results"]
        if result["campaign_group_id"] == "HAN-STARTUP-CENTRAL-25-26"
    } == {"positive", "negative"}
    for ruler_name in ("福临", "玄烨"):
        assert by_name[ruler_name]["C_score_points"] == 0.0
        assert not by_name[ruler_name]["default_applied"]
    for ruler_name in ("胤禛", "弘历"):
        assert by_name[ruler_name]["scope_status"] == "NOT_APPLICABLE_NON_FOUNDER"
        assert by_name[ruler_name]["C_score_points"] is None


    assert by_name["刘秀"]["C2"]["positive_context_count"] == 3
    assert by_name["刘秀"]["C2"]["negative_context_count"] == 1
    assert {
        row["campaign_group_id"] for row in by_name["刘秀"]["C1"]["campaign_results"]
    } >= {"WAR-LEAD-XIN-COLLAPSE-23", "HAN-STARTUP-CENTRAL-25-26"}
    assert by_name["沮渠蒙逊"]["C2"]["positive_context_count"] == 4
    assert {
        row["campaign_group_id"]
        for row in by_name["沮渠蒙逊"]["C2"]["frontline_results"]
    } >= {
        "WAR-LEAD-115-SOUTHNORTHLIANG-410",
        "WAR-LEAD-117-NORTHLIANG-WESTQIN-415",
    }
    assert sum(
        row["C2"]["negative_context_count"]
        for row in payload["records"]
        if row["score_applicable"]
    ) >= 9
    assert sum(
        row["C2"]["command_failure_count"]
        for row in payload["records"]
        if row["score_applicable"]
    ) >= 1

    windows = {row["window_ref"]: row for row in payload["window_metrics"]}
    ordered = [
        "UCP-TANG-LIYUAN-617-628",
        "UCP-HAN-LIUXIU-23-36",
        "UCP-HAN-LIUBANG-BCE207-BCE202",
        "UCP-QIN-YINGZHENG-230-221",
        "UCP-SUI-YANGJIAN-587-591",
        "UCP-JIN-SIMAYAN-279-280",
    ]
    values = [windows[key]["calibrated_weighted_net_control"] for key in ordered]
    assert values[:4] == sorted(values[:4], reverse=True)
    assert values[3] > values[4]
    assert values[4] >= values[5]


def test_first_item_c2_peak_separates_s_d4_from_sustained_s_minus_quantity() -> None:
    def result(ref: str, tier: str, difficulty: str, direction: str = "positive") -> dict:
        tier_score = {"A": 3, "S-": 4, "S": 5}[tier]
        difficulty_score = int(difficulty[1:])
        return {
            "capability_episode_ref": ref,
            "result_direction": direction,
            "personal_result_tier": tier,
            "combat_difficulty": difficulty,
            "quality_index": tier_score + 0.3 * difficulty_score,
        }

    sustained_s_minus = _c2_axis(
        {
            "s-minus-1": result("s-minus-1", "S-", "D3"),
            "s-minus-2": result("s-minus-2", "S-", "D3"),
            "a-d4": result("a-d4", "A", "D4"),
        },
        {},
    )
    higher_peak_with_thick_validation = _c2_axis(
        {
            "s-d4": result("s-d4", "S", "D4"),
            "s-d3": result("s-d3", "S", "D3"),
            "s-minus-d3": result("s-minus-d3", "S-", "D3"),
            "a-loss": result("a-loss", "A", "D3", "negative"),
        },
        {},
    )

    assert sustained_s_minus["grade"] == 5
    assert sustained_s_minus["position"] == "LOW"
    assert sustained_s_minus["points"] == 25.2
    assert higher_peak_with_thick_validation["grade"] == 5
    assert higher_peak_with_thick_validation["position"] == "MID"
    assert higher_peak_with_thick_validation["points"] == 27.6
    assert higher_peak_with_thick_validation["abundant_grade_5_validation"] is True


def test_first_item_c_registry_is_deterministic() -> None:
    inputs = _load_current_first_item_c_inputs()
    assert build_first_item_c_registry(**inputs) == build_first_item_c_registry(**inputs)


def _load_current_first_item_b_inputs() -> dict[str, dict]:
    def load(path: str) -> dict:
        return json.loads((ROOT / path).read_text(encoding="utf-8"))

    efficiency_inputs = load("config/first-item-a-strategic-efficiency-inputs.json")
    return {
        "adjudications": load(
            "config/first-item-b-team-contribution-adjudications.json"
        ),
        "roster": load_qin_qing_first_item_roster(ROOT, efficiency_inputs),
        "battle_registry": load_battle_registry(
            ROOT / "docs/公共成果/军事/01-战役登记.json"
        ),
        "talent_registry": load_talent_registry(
            ROOT / "docs/公共成果/军事/02-武将人才等级.json"
        ),
    }


def test_first_item_b_registry_is_complete_non_founder_contribution_scoring() -> None:
    inputs = _load_current_first_item_b_inputs()
    payload = build_first_item_b_registry(**inputs)
    assert payload == build_first_item_b_registry(**inputs)
    assert payload["schema_version"] == "first-item-b-registry-v3"
    assert payload["canonical_status"] == "CURRENT"
    assert payload["record_count"] == 185
    assert payload["eligible_count"] == 77
    assert payload["excluded_count"] == 108
    assert payload["score_ready_count"] == 185
    assert payload["unresolved_count"] == 0
    assert payload["unanchored_context_outcome_count"] == 0
    assert payload["unanchored_scoring_outcome_count"] == 0
    assert payload["formal_score_write"] is False
    assert payload["database_write"] is False
    assert payload["ranking_write"] is False

    eligible = [row for row in payload["records"] if row["score_applicable"]]
    assert all(row["B1"]["outcome_evidence"] for row in eligible)
    assert all(0 <= row["B1"]["points"] <= 30 for row in eligible)
    assert all(0 <= row["B2"]["points"] <= 30 for row in eligible)
    assert all(len(row["B2"]["organization_axes"]) == 3 for row in eligible)
    assert all(0 <= row["B_score_points"] <= 60 for row in eligible)
    by_name = {row["ruler_name"]: row for row in payload["records"]}
    assert by_name["刘邦"]["B_score_points"] == 58.0
    assert by_name["刘邦"]["canonical_rank"] == 1
    assert by_name["刘邦"]["B_score_points"] > by_name["刘秀"]["B_score_points"]
    assert by_name["刘秀"]["B_score_points"] == 53.5
    assert by_name["嬴政"]["B_score_points"] == 58.0
    assert by_name["李渊"]["B1"]["points"] == 28.5
    assert by_name["李渊"]["B2"]["points"] == 28.0
    assert by_name["李渊"]["B_score_points"] == 56.5
    assert by_name["李世民"]["B1"]["points"] == 19.5
    assert by_name["李世民"]["B2"]["points"] == 22.0
    assert by_name["李世民"]["B_score_points"] == 41.5
    assert by_name["李世民"]["canonical_rank"] > 20
    assert by_name["铁木真"]["B_score_points"] == 58.0
    assert by_name["朱元璋"]["B_score_points"] == 56.5
    assert by_name["刘聪"]["B_score_points"] == 41.4
    assert by_name["洪秀全"]["B_score_points"] == 40.0
    assert by_name["曹丕"]["B_score_points"] == 30.4
    assert by_name["冉闵"]["B_score_points"] == 10.3
    assert by_name["武则天"]["scope_status"] == "NOT_APPLICABLE_NON_FOUNDER"
    assert by_name["武则天"]["B_score_points"] is None
    li_yuan_chains = by_name["李渊"]["B1"]["outcome_evidence"]
    assert any("李世民" in chain["actors"] for chain in li_yuan_chains)
    li_shimin_chains = by_name["李世民"]["B1"]["outcome_evidence"]
    assert all("李世民" not in chain["actors"] for chain in li_shimin_chains)
    assert any(chain["chain"] == "陕东道大行台日常行政后勤" for chain in li_shimin_chains)
    xiao_he_chains = [
        chain for chain in by_name["刘邦"]["B1"]["outcome_evidence"]
        if "萧何" in chain["actors"]
    ]
    assert xiao_he_chains[0]["outcome_level"] == "FOUNDATION_PILLAR"
    assert len(by_name["刘邦"]["B1"]["scoring_outcomes"]) == 2
    assert {
        axis["axis"]: axis["level"]
        for axis in by_name["刘邦"]["B2"]["organization_axes"]
    } == {
        "parallel_execution": 5,
        "continuity_resilience": 4,
        "heterogeneous_integration": 5,
    }
    assert payload["source_registry_fingerprints"]["battle"] == inputs[
        "battle_registry"
    ].get("semantic_fingerprint")
    assert payload["source_registry_fingerprints"]["talent"] == inputs[
        "talent_registry"
    ]["registry_fingerprint"]
    assert all(
        row["B1"]["points"]
        == round(min(30, row["B1"]["raw_points"]), 1)
        for row in eligible
    )


def test_first_item_b_score_does_not_increase_when_more_names_are_listed() -> None:
    inputs = _load_current_first_item_b_inputs()
    baseline = build_first_item_b_registry(**inputs)
    changed = json.loads(json.dumps(inputs["adjudications"], ensure_ascii=False))
    li_bang = next(row for row in changed["records"] if row["ruler_name"] == "刘邦")
    li_bang["outcome_evidence"][0]["actors"].extend(["后方属官甲", "后方属官乙", "后方属官丙"])
    mutated = build_first_item_b_registry(**{**inputs, "adjudications": changed})
    baseline_row = next(row for row in baseline["records"] if row["ruler_name"] == "刘邦")
    mutated_row = next(row for row in mutated["records"] if row["ruler_name"] == "刘邦")
    assert mutated_row["B_score_points"] == baseline_row["B_score_points"]
    assert mutated_row["B1"]["points"] == baseline_row["B1"]["points"]
    assert mutated_row["B2"]["points"] == baseline_row["B2"]["points"]


def test_first_item_summary_matches_current_abc_results() -> None:
    a_payload = json.loads((ROOT / "docs/评分结算/第一项创业与政权取得能力/战略决策能力/01-第一项A战略决策能力结算.json").read_text(encoding="utf-8"))
    b_payload = json.loads((ROOT / "docs/评分结算/第一项创业与政权取得能力/政治整合能力/01-第一项B政治整合能力结算.json").read_text(encoding="utf-8"))
    c_payload = json.loads((ROOT / "docs/评分结算/第一项创业与政权取得能力/军事夺取能力/01-第一项C军事夺取能力结算.json").read_text(encoding="utf-8"))
    formal_payload = json.loads((ROOT / "docs/评分结算/第一项创业与政权取得能力/01-第一项创业与政权取得能力正式结算.json").read_text(encoding="utf-8"))
    formal_markdown = (ROOT / "docs/评分结算/第一项创业与政权取得能力/01-第一项创业与政权取得能力正式结算.md").read_text(encoding="utf-8")
    summary = (ROOT / "docs/评分结算/第一项创业与政权取得能力/02-第一项结算总结分析.md").read_text(encoding="utf-8")
    by_b = {row["ruler_name"]: row for row in b_payload["records"]}
    by_c = {row["ruler_name"]: row for row in c_payload["records"]}
    totals = []
    for a_row in a_payload["records"]:
        if (
            not a_row["score_applicable"]
            or a_row["ruler_name"] not in by_b
            or not by_b[a_row["ruler_name"]].get("score_applicable")
        ):
            continue
        name = a_row["ruler_name"]
        total = round(
            a_row["A_score_points"]
            + by_b[name]["B_score_points"]
            + by_c[name]["C_score_points"],
            1,
        )
        totals.append((name, total))
        assert f"| {name} |" in formal_markdown
    totals.sort(key=lambda item: (-item[1], item[0]))
    assert len(totals) == 77
    assert totals[:4] == [
        ("李世民", 211.5),
        ("朱元璋", 210.2),
        ("刘秀", 205.6),
        ("铁木真", 202.8),
    ]
    assert "李世民（211.5）" in summary
    assert formal_payload["schema_version"] == "first-item-formal-settlement-v2"
    assert formal_payload["record_count"] == 185
    assert formal_payload["eligible_count"] == 77
    assert formal_payload["excluded_count"] == 108
    assert formal_payload["unresolved_count"] == 0
    assert formal_payload["records"][0]["ruler_name"] == "李世民"
    assert formal_payload["records"][0]["first_item_score_points"] == 211.5
    assert not (ROOT / "docs/评分结算/第一项创业与政权取得能力/政治整合能力/01-秦至唐第一项B政治整合能力试算.json").exists()
    assert not (ROOT / "docs/评分结算/第一项创业与政权取得能力/政治整合能力/01-秦至唐第一项B政治整合能力试算.md").exists()


def _load_current_first_item_a_inputs() -> dict[str, dict]:
    def load(path: str) -> dict:
        return json.loads((ROOT / path).read_text(encoding="utf-8"))

    return {
        "efficiency_inputs": load(
            "config/first-item-a-strategic-efficiency-inputs.json"
        ),
        "competitive_landscapes": load(
            "config/first-item-a-competitive-landscapes.json"
        ),
        "battle_registry": load_battle_registry(
            ROOT / "docs/公共成果/军事/01-战役登记.json"
        ),
        "territorial_inputs": load(
            "config/first-item-c-territorial-control-adjudications.json"
        ),
        "acquisition_windows": load(
            "config/first-item-c-acquisition-windows.json"
        ),
        "roster": load_qin_qing_first_item_roster(
            ROOT, load("config/first-item-a-strategic-efficiency-inputs.json")
        ),
    }


def test_first_item_a_only_scores_dynasty_founders() -> None:
    payload = build_first_item_a_registry(**_load_current_first_item_a_inputs())
    eligible = {
        row["ruler_name"] for row in payload["records"] if row["score_applicable"]
    }
    original_eligible = {
        "李世民", "刘秀", "刘裕", "刘邦", "高欢", "萧衍", "慕容垂", "石勒",
        "曹操", "陈霸先", "刘备", "宇文泰", "吕光", "慕容德", "苻健",
        "赫连勃勃", "司马炎", "沮渠蒙逊", "拓跋珪", "萧道成", "刘渊",
        "李暠", "李渊", "司马昭", "冉闵", "孙权", "姚苌", "冯跋", "刘玄",
        "司马懿", "司马睿", "嬴政", "曹丕", "李雄", "杨坚",
        "王莽", "高洋", "司马师",
    }
    assert original_eligible < eligible
    assert {
        "刘聪", "姚兴", "宇文邕", "拓跋焘", "石虎", "苻坚",
        "朱温", "李存勖", "李嗣源", "耶律阿保机", "赵匡胤",
        "铁木真", "窝阔台", "蒙哥", "忽必烈", "朱元璋",
        "努尔哈赤", "皇太极", "多尔衮", "玄烨",
    } < eligible
    assert payload["record_count"] == 185
    assert payload["eligible_count"] == 77
    assert payload["excluded_count"] == 108
    assert payload["unresolved_count"] == 0

    by_name = {row["ruler_name"]: row for row in payload["records"]}
    for ruler_name in ("刘恒", "李隆基", "武则天", "胤禛", "弘历"):
        row = by_name[ruler_name]
        assert row["scope_status"] == "NOT_APPLICABLE_NON_FOUNDER"
        assert row["canonical_rank"] is None
        assert row["A1"] is None
        assert row["A2"] is None
        assert row["A_score_points"] is None
    for ruler_name in (
        "曹操", "曹丕", "高欢", "高洋", "司马懿", "司马师", "司马昭", "司马炎",
        "李渊", "李世民",
    ):
        assert by_name[ruler_name]["scope_status"] == "ELIGIBLE_DYNASTY_FOUNDER"


def test_first_item_a_registry_is_complete_calibrated_and_deterministic() -> None:
    inputs = _load_current_first_item_a_inputs()
    payload = build_first_item_a_registry(**inputs)
    assert payload == build_first_item_a_registry(**inputs)
    assert payload["schema_version"] == "first-item-a-registry-v7"
    assert payload["canonical_status"] == "CURRENT"
    assert payload["score_ready_count"] == 185
    assert payload["max_points"] == 100
    assert payload["formal_score_write"] is False
    assert payload["database_write"] is False
    assert payload["ranking_write"] is False
    assert payload["method"]["D_merge"].startswith("原D")
    assert payload["strategic_positive_decision_event_count"] == 50
    assert payload["a2_cap_count"] == 0

    eligible = [row for row in payload["records"] if row["score_applicable"]]
    assert [row["canonical_rank"] for row in eligible] == list(range(1, 78))
    assert all(0 <= row["A_score_points"] <= 100 for row in eligible)
    assert eligible[0]["ruler_name"] == "李世民"
    by_name = {row["ruler_name"]: row for row in eligible}
    landscapes = inputs["competitive_landscapes"]
    assert landscapes["schema_version"] == "first-item-a-competitive-landscapes-v8"
    assert "campaign_threat_sources" not in landscapes
    assert len(landscapes["opponent_system_windows"]) == 59
    assert len(landscapes["relative_only_threat_justifications"]) == 18
    assert not (
        set(landscapes["opponent_system_windows"])
        & set(landscapes["relative_only_threat_justifications"])
    )
    assert by_name["李世民"]["A_score_points"] == 90.0
    assert by_name["刘邦"]["A_score_points"] == 85.4
    assert by_name["刘秀"]["A_score_points"] == 84.2
    assert by_name["朱元璋"]["A_score_points"] == 84.0
    assert by_name["李渊"]["A_score_points"] == 68.3
    assert by_name["刘邦"]["A_score_points"] > by_name["刘秀"]["A_score_points"]
    assert by_name["李世民"]["A_score_points"] > by_name["李渊"]["A_score_points"]
    assert by_name["刘邦"]["A_score_points"] > by_name["李渊"]["A_score_points"]
    assert by_name["刘邦"]["A_score_points"] > by_name["嬴政"]["A_score_points"]
    assert by_name["赵匡胤"]["A2"]["created_net_control_value"] == 265.0
    assert by_name["赵光义"]["A2"]["created_net_control_value"] == 60.0
    assert by_name["完颜阿骨打"]["A2"]["created_net_control_value"] == 100.0
    assert by_name["完颜吴乞买"]["A2"]["created_net_control_value"] == 225.0
    assert by_name["铁木真"]["A2"]["created_net_control_value"] == 540.0
    assert by_name["窝阔台"]["A2"]["created_net_control_value"] == 180.0
    assert by_name["蒙哥"]["A2"]["created_net_control_value"] == 80.0
    assert by_name["忽必烈"]["A2"]["created_net_control_value"] == 420.0
    assert by_name["多尔衮"]["A2"]["created_net_control_value"] == 770.0
    assert by_name["福临"]["A2"]["created_net_control_value"] == 40.0
    assert by_name["玄烨"]["A2"]["created_net_control_value"] == 0.0
    assert by_name["玄烨"]["A2"]["recovered_net_control_value"] == 300.0
    assert by_name["玄烨"]["A2"]["gross_unification_control_value"] == 300.0
    assert by_name["玄烨"]["A2"]["effective_unification_control_value"] == 150.0
    assert all(
        not ({
            "created_net_control_value",
            "recovered_net_control_value",
            "gross_unification_control_value",
            "effective_unification_control_value",
            "raw_control_scale_rate",
            "control_scale_score_rate",
        } & set(row["A1"]))
        for row in eligible
    )
    assert all("raw_control_scale_rate" in row["A2"] for row in eligible)
    assert all("control_scale_score_rate" in row["A2"] for row in eligible)
    assert all("a1_strategic_responsibility_factor" not in row["A2"] for row in eligible)
    assert all(
        event["source_refs"]
        for row in eligible
        for event in row["A2"]["strategic_positive_decisions"]
    )
    assert by_name["刘邦"]["A2"]["raw_control_scale_rate"] == 55.02
    assert by_name["刘邦"]["A2"]["control_scale_score_rate"] == 74.18
    assert by_name["刘邦"]["A_score_points"] > by_name["多尔衮"]["A_score_points"]
    assert by_name["刘邦"]["A_score_points"] > by_name["王建"]["A_score_points"]
    assert by_name["刘邦"]["A_score_points"] > by_name["石虎"]["A_score_points"]
    assert by_name["王建"]["A2"]["strategic_positive_decisions"] == []
    assert by_name["石虎"]["A2"]["strategic_positive_decisions"] == []
    assert by_name["王建"]["A2"]["strategic_positive_decision_points"] == 0.0
    assert by_name["石虎"]["A2"]["strategic_positive_decision_points"] == 0.0
    assert by_name["曹操"]["A_score_points"] == 58.6
    assert by_name["苻坚"]["A1"]["points"] == 33.5
    assert by_name["苻坚"]["A2"]["strategic_error_points"] == 10.0
    assert by_name["苻坚"]["A_score_points"] == 40.5
    assert by_name["刘秀"]["A1"]["starting_resource_share"] == 0.5
    assert by_name["嬴政"]["A1"]["starting_resource_share"] == 35.0
    assert by_name["杨坚"]["A1"]["starting_resource_share"] == 8.0
    assert by_name["杨坚"]["A1"]["project_start_resource_share"] == 65.0
    assert by_name["宇文邕"]["A1"]["project_start_resource_share"] == 42.0
    assert by_name["宇文邕"]["A1"]["difficulty_rate"] > by_name["杨坚"]["A1"]["difficulty_rate"]
    assert by_name["高欢"]["A1"]["terminal_completion_rate"] == 55.0
    assert by_name["司马懿"]["A2"]["created_net_control_value"] == 30.0
    assert by_name["王莽"]["A_score_points"] == 7.0
    assert by_name["司马懿"]["A_score_points"] < 55
    assert by_name["高欢"]["A_score_points"] < 75
    assert by_name["李世民"]["A2"]["strategic_error_points"] == 0.0
    assert by_name["李世民"]["A2"]["strategic_positive_decisions"][0]["impact"] == "DECISIVE"
    assert by_name["李世民"]["A2"]["strategic_positive_decision_points"] == 5.0
    assert by_name["李世民"]["strategic_error_events"] == []
    assert payload["strategic_error_review_counts"] == {
        "REVIEWED_ERRORS": 27,
        "REVIEWED_NO_THRESHOLD_ERROR": 50,
    }
    assert payload["strategic_error_event_count"] == 31
    assert all(
        row["strategic_error_review"]["searched_evidence_refs"]
        and row["strategic_error_review"]["review_status"]
        == (
            "REVIEWED_ERRORS"
            if row["strategic_error_events"]
            else "REVIEWED_NO_THRESHOLD_ERROR"
        )
        for row in eligible
    )
    assert all(
        event["source_refs"] and event["c_nonduplication_basis"]
        for row in eligible
        for event in row["strategic_error_events"]
    )
    assert by_name["铁木真"]["strategic_error_events"] == []
    assert by_name["铁木真"]["A1"]["opponent_threat_source_status"] == (
        "OPPONENT_SYSTEM_O_GRADE_WITH_RELATIVE_RESOURCES"
    )
    assert by_name["铁木真"]["A1"]["opponent_pressure"] == 68.22
    assert by_name["铁木真"]["A1"]["opponent_system_pressure"] == 78.45
    assert by_name["铁木真"]["A1"]["relative_resource_pressure"] == 44.36
    assert by_name["铁木真"]["A1"]["major_opponent_count"] == 5
    assert {
        row["organization_grade"]
        for row in by_name["铁木真"]["A1"]["major_opponent_systems"]
    } == {"O4", "O5"}
    assert all(
        len(row["A1"]["major_opponent_systems"])
        == len({system.get("opponent_system_ref") for system in row["A1"]["major_opponent_systems"]})
        for row in eligible
        if row["A1"]["opponent_system_pressure"] is not None
    )
    assert all(
        not ({"campaign_tier", "combat_difficulty", "field_threat_rate"} & set(system))
        for row in eligible
        for system in row["A1"]["major_opponent_systems"]
    )
    assert by_name["铁木真"]["A1"]["opponent_pressure"] > by_name["嬴政"]["A1"]["opponent_pressure"]
    assert by_name["铁木真"]["A1"]["difficulty_rate"] > by_name["嬴政"]["A1"]["difficulty_rate"]
    assert by_name["努尔哈赤"]["strategic_error_events"] == []
    assert by_name["李存勖"]["A2"]["strategic_error_points"] == 12.0
    assert by_name["洪秀全"]["A2"]["strategic_error_points"] == 10.0
    assert "foundation_coverage_rate" not in by_name["李世民"]["A2"]
    assert by_name["李渊"]["A1"]["starting_resource_share"] == 4.0
    assert by_name["李渊"]["A1"]["major_opponent_count"] == 13
    assert by_name["李渊"]["A1"]["opponent_pressure"] > by_name["刘秀"]["A1"]["opponent_pressure"]
    assert by_name["杨坚"]["A1"]["opponent_system_pressure"] == 52.5
    assert by_name["杨坚"]["A1"]["relative_resource_pressure"] == 21.44
    assert by_name["杨坚"]["A1"]["opponent_pressure"] == 43.18
    assert {
        row["organization_grade"]
        for row in by_name["杨坚"]["A1"]["major_opponent_systems"]
    } == {"O4"}
    assert by_name["嬴政"]["A1"]["opponent_system_pressure"] == 80.45
    assert by_name["嬴政"]["A1"]["relative_resource_pressure"] == 21.21
    assert by_name["嬴政"]["A1"]["opponent_pressure"] == 62.68
    assert by_name["杨坚"]["A1"]["opponent_pressure"] < by_name["刘裕"]["A1"]["opponent_pressure"]
    assert not any(
        "刘黑闼" in row["opponent_label"]
        for row in by_name["李渊"]["A1"]["major_opponent_systems"]
    )
    eastern_turks = next(
        row
        for row in by_name["李世民"]["A1"]["major_opponent_systems"]
        if row["opponent_label"] == "东突厥汗国战争机器"
    )
    assert eastern_turks["organization_grade"] == "O6"
    assert by_name["李渊"]["A2"]["created_net_control_value"] == 934.25
    assert by_name["李世民"]["A2"]["created_net_control_value"] == 934.25
    assert by_name["李世民"]["A1"]["terminal_completion_rate"] == 100.0
    assert "personal_route_coverage_rate" not in by_name["李渊"]["A1"]
    assert "route_coverage_source_status" not in by_name["李世民"]["A1"]
    assert "effective_net_control_value" not in by_name["李世民"]["A2"]
    assert by_name["李渊"]["A2"]["strategic_error_points"] == 10.0
    assert by_name["李渊"]["A2"]["strategic_positive_decision_points"] == 5.0
    assert payload["opponent_threat_source_counts"] == {
        "OPPONENT_SYSTEM_O_GRADE_WITH_RELATIVE_RESOURCES": 59,
        "RELATIVE_RESOURCE_ONLY_EVIDENCE_LOWER_BOUND": 18,
    }
    fallback_rows = [
        row for row in eligible
        if row["A1"]["opponent_threat_source_status"]
        == "RELATIVE_RESOURCE_ONLY_EVIDENCE_LOWER_BOUND"
    ]
    assert len(fallback_rows) == 18
    assert all(row["A1"]["opponent_threat_routing_basis"] for row in fallback_rows)
    zhao_decisions = by_name["赵匡胤"]["A2"]["strategic_positive_decisions"]
    assert [row["impact"] for row in zhao_decisions] == ["EXCEPTIONAL"]
    assert zhao_decisions[0]["source_refs"]
    assert by_name["赵匡胤"]["A2"]["strategic_positive_decision_points"] == 8.0
    assert by_name["赵匡胤"]["A2"]["points"] > by_name["杨坚"]["A2"]["points"]
    markdown = render_first_item_a_registry_markdown(payload)
    opponent_lines = [
        line for line in markdown.splitlines()
        if line.startswith("- 主要对手压力：")
    ]
    assert len(opponent_lines) == 77
    assert all(
        token not in line
        for line in opponent_lines
        for token in (
            "WAR-",
            "PUBLIC_BATTLE_",
            "COMPLETE_DEFAULT_",
            "负荷0.",
            "对手路由依据",
        )
    )
    assert "克烈部草原霸权体系（O4）" in markdown
    assert "花剌子模国家机器（O5）" in markdown
    assert "战场危险度" not in markdown
    assert [event["severity"] for event in by_name["李渊"]["strategic_error_events"]] == ["MAJOR", "MAJOR"]
    assert "处死窦建德" in by_name["李渊"]["strategic_error_events"][1]["event"]
    assert by_name["李渊"]["A2"]["value_weighted_acquisition_years"] == 4.0
    assert by_name["李渊"]["A2"]["closure_years"] == 10.0
    assert by_name["李渊"]["A2"]["created_net_control_value"] > by_name["刘秀"]["A2"]["created_net_control_value"]
    assert by_name["刘秀"]["A2"]["created_net_control_value"] > by_name["刘邦"]["A2"]["created_net_control_value"]
    assert by_name["刘邦"]["A2"]["created_net_control_value"] > by_name["嬴政"]["A2"]["created_net_control_value"]
    assert by_name["李世民"]["A2"]["control_acquisition_efficiency"] > by_name["刘邦"]["A2"]["control_acquisition_efficiency"]
    assert by_name["刘邦"]["A2"]["control_acquisition_efficiency"] > by_name["刘秀"]["A2"]["control_acquisition_efficiency"]
    assert "grade" not in by_name["刘秀"]["A1"]
    assert all(
        row["start_boundary"]
        and row["end_boundary"]
        and row["starting_position"]
        and row["responsibility_basis"]
        for row in eligible
    )
    assert by_name["冉闵"]["A_score_points"] < 20
    assert by_name["刘玄"]["A_score_points"] < 20

    public_liuheita = next(
        row for row in inputs["battle_registry"]["records"]
        if row["war_event_id"] == "WAR-LEAD-TANG-LIUHEITA-622"
    )
    members = {member["actor_name"]: member for member in public_liuheita["members"]}
    assert members["李世民"]["person_command_index"]["projected_combat_difficulty"] == "D4"
    assert members["李建成"]["person_command_result"]["combat_difficulty"] == "D2"
    assert "与李世民第一次击毁主力的A/D4成果分开消费" in members["李建成"]["person_command_result"]["basis"]


def test_post_tang_battle_partitions_cover_handoffs_exactly_once() -> None:
    from emperor_v4.evaluation.post_tang_battle_registry import (
        build_post_tang_battle_partitions,
    )

    with pytest.raises(ValueError, match="旧registry输入已退役"):
        build_post_tang_battle_partitions(ROOT)

    assert not (ROOT / "docs/史料通读产物/唐以后编年").exists()
    assert (ROOT / "docs/史料通读产物/五代十国/资治通鉴").is_dir()
    assert (ROOT / "docs/史料通读产物/北宋/续资治通鉴").is_dir()


def test_current_battle_registry_preserves_qin_tang_and_accepts_post_tang() -> None:
    payload = load_battle_registry(
        ROOT / "docs/公共成果/军事/01-战役登记.json"
    )
    post_records = [record for record in payload["records"] if record.get("post_tang_evidence_lower_bound")]
    assert payload["schema_version"] == "battle-parent-contract-registry-v5"
    assert payload["qin_tang_semantic_fingerprint"] == "d8bf11d3b8ad433c1c1e01ff3302a62bff1b66ecc2790574376babc61b3bdb9e"
    tiered_dynasty_counts = Counter(
        row["dynasty"] for row in payload["records"] if row.get("campaign_tier")
    )
    assert tiered_dynasty_counts["汉"] == 66
    assert tiered_dynasty_counts["东汉"] == 102
    assert len(post_records) == 2761
    assert sum(record["public_outcome_registered"] for record in post_records) == 919
    assert payload["post_tang_candidate_count"] == 4000
    assert payload["post_tang_source_fact_count"] == 4090
    promotion = payload["five_dynasties_promotion"]
    assert promotion["battle_card_count"] == 521
    assert promotion["subject_phase_count"] == 1434
    assert promotion["supplemental_record_count"] == 2
    assert promotion["retired_stale_record_count"] == 433
    north_promotion = payload["north_song_promotion"]
    assert north_promotion["volume_count"] == 97
    assert north_promotion["battle_card_count"] == 716
    assert north_promotion["subject_phase_count"] == 1586
    assert north_promotion["retired_stale_record_count"] == 801
    assert len({record["war_event_id"] for record in payload["records"]}) == len(payload["records"])
    difficulty_review = payload["high_difficulty_contract_review_summary"]
    assert difficulty_review["status"] == "ACCEPTED_CURRENT"
    assert difficulty_review["current_d3_d4_count"] == 338
    assert difficulty_review["current_difficulty_counts"] == {"D3": 312, "D4": 26}
    assert difficulty_review["post_tang_source_reviewed_record_count"] == 104
    assert difficulty_review["pending_count"] == 0
    current_high_difficulty = [
        record
        for record in payload["records"]
        if record.get("public_outcome_registered")
        and record.get("combat_difficulty") in {"D3", "D4"}
    ]
    assert len(current_high_difficulty) == 338
    assert all(record.get("combat_difficulty_basis") for record in current_high_difficulty)
    assert {
        record["source_target_ref"]
        for record in post_records
        if record.get("public_outcome_registered")
        and record.get("combat_difficulty") == "D4"
    } == {
        "CAMPAIGN-MING-BEIJING-DEFENSE-1449",
        "CAMPAIGN-QING-SARHU-AND-YEHE-1619",
        "CAMPAIGN-YUAN-KERAIT-TERMINAL-1203",
        "SPLIT-QING-AGUI-JINCHUAN-1773-1776",
    }
    assert all(
        record.get("battle_result") in {"victory", "mixed"}
        and record.get("objective_completion") == "complete"
        for record in current_high_difficulty
        if record["combat_difficulty"] == "D4"
    )
    zhangping = next(
        record for record in payload["records"]
        if record["war_event_id"] == "WAR-LEAD-100-ZHANGPING-358"
    )
    assert zhangping["combat_difficulty"] == "D2"
    dengqiang = next(
        member for member in zhangping["members"] if member["actor_name"] == "邓羌"
    )
    assert dengqiang["person_command_result"]["combat_difficulty"] == "D3"
    for record in post_records:
        if "UNIFICATION_ONLY" in set(record.get("account_routing") or ()):
            assert record["defense_consumption"] == "EXCLUDED_UNIFICATION"
            assert record["settlement_scope"] == "BATTLE_LEDGER_ONLY"

    calibration = payload["unification_horizontal_calibration"]
    benchmark = {
        row["portfolio_ref"]: row for row in calibration["benchmark_records"]
    }
    assert benchmark["UCP-TANG-LIYUAN-617-628"]["horizontal_total_band"] == "H1"
    assert benchmark["UCP-QIN-YINGZHENG-230-221"]["horizontal_total_band"] == "H1"
    assert benchmark["UCP-HAN-LIUXIU-23-36"]["horizontal_total_band"] == "H2"
    assert benchmark["UCP-JIN-SIMAYAN-279-280"]["horizontal_total_band"] == "H3"
    assert benchmark["UCP-SUI-YANGJIAN-587-591"]["horizontal_total_band"] == "H5"
    assert set(calibration["grade_groups"]["H1"]) == {
        "UCP-POST-YUAN-1205-1279",
        "UCP-TANG-LIYUAN-617-628",
        "UCP-QIN-YINGZHENG-230-221",
        "UCP-HAN-LIUBANG-BCE207-BCE202",
    }
    assert benchmark["UCP-TANG-LIYUAN-617-628"]["credited_opponent_counts"]["O5"] == 2
    assert benchmark["UCP-HAN-LIUXIU-23-36"]["credited_opponent_counts"]["O5"] == 0
    assert benchmark["UCP-HAN-LIUXIU-23-36"]["credited_opponent_counts"]["O4"] == 4

    all_portfolios = payload["unification_campaign_portfolios"]
    assert len(all_portfolios) == 17
    assert len({tuple(sorted(row)) for row in all_portfolios}) == 1
    assert len({tuple(sorted(row["control_audit"])) for row in all_portfolios}) == 1
    assert "pre_tang_unification_control_calibrations" not in payload
    assert "post_tang_unification_portfolios" not in payload
    pre_tang_controls = {
        row["dynasty"]: row
        for row in all_portfolios
        if row["chronology_scope"] == "PRE_TANG"
    }
    assert {
        dynasty: row["created_net_control_value"]
        for dynasty, row in pre_tang_controls.items()
    } == {
        "唐": 760.0,
        "东汉": 825.0,
        "西汉": 745.0,
        "秦": 580.0,
        "晋": 300.0,
        "隋": 245.0,
    }
    assert all(
        row["control_audit"]["source_configs"]
        == [
            "config/first-item-c-territorial-control-adjudications.json",
            "config/pre-tang-unification-war-control-adjudications.json",
            "config/period-war-region-value-adjudications.json",
            "config/unification-chain-opponent-calibrations.json",
        ]
        and "baseline_snapshot" in row["control_audit"]
        and row["control_audit"]["terminal_snapshot"]
        and row["control_audit"]["group_control_results"]
        and row["control_audit"]["control_deltas"]
        and round(
            sum(
                delta["weighted_war_acquired_value"]
                for delta in row["control_audit"]["control_deltas"]
            ),
            2,
        )
        == row["created_net_control_value"]
        for row in pre_tang_controls.values()
    )
    tang_deltas = {
        row["region_id"]: row
        for row in pre_tang_controls["唐"]["control_audit"]["control_deltas"]
    }
    assert tang_deltas["MR-BASHU"]["war_acquired_retained_fraction"] == 0.0
    assert tang_deltas["MR-BASHU"]["excluded_non_war_fraction"] == 1.0
    assert tang_deltas["MR-BASHU"]["unknown_acquisition_fraction"] == 0.0
    assert payload["high_tier_recalibration_summary"]["current_tier_counts"] == {
        "S": 48,
        "S+": 2,
        "S-": 150,
    }
    assert payload["high_tier_recalibration_summary"]["current_high_tier_count"] == 200
    assert payload["high_tier_recalibration_summary"]["changed_decision_count"] == 74
    assert payload["high_tier_recalibration_summary"]["ordinary_opponent_audit_count"] == 160
    assert payload["high_tier_recalibration_summary"]["current_ordinary_high_tier_count"] == 136
    assert payload["high_tier_recalibration_summary"]["structural_a_promotion_pending_count"] == 0
    assert {
        row["campaign_group_id"]
        for row in pre_tang_controls["隋"]["control_audit"]["excluded_non_battle_groups"]
    } == {"WAR-LEAD-SUI-ABSORB-LIANG-587"}

    portfolios = {
        row["portfolio_ref"]: row
        for row in all_portfolios
        if row["chronology_scope"] == "POST_TANG"
    }
    assert set(portfolios) == {
        "UCP-POST-GORYEO-936",
        "UCP-POST-LIAO-901-926",
        "UCP-POST-SONG-963-979",
        "UCP-POST-PROTO-JIN-SHILU",
        "UCP-POST-JIN-1114-1126",
        "UCP-POST-YUAN-ANCESTRAL-BODONCHAR",
        "UCP-POST-YUAN-ANCESTRAL-HAIDU",
        "UCP-POST-YUAN-1205-1279",
        "UCP-POST-MING-1353-1382",
        "UCP-POST-QING-FOUNDING-1607-1662",
        "UCP-POST-QING-REUNIFICATION-1673-1683",
    }
    assert all("portfolio_total_tier" not in row for row in portfolios.values())
    assert portfolios["UCP-POST-GORYEO-936"]["campaign_group_refs"] == [
        "WAR-FD-013B3B0607C76A755F16"
    ]
    assert portfolios["UCP-POST-SONG-963-979"]["created_net_control_value"] == 325.0
    assert portfolios["UCP-POST-SONG-963-979"]["horizontal_total_band"] == "H2"
    current_event_ids = {row["war_event_id"] for row in payload["records"]}
    song_portfolio = portfolios["UCP-POST-SONG-963-979"]
    assert len(song_portfolio["campaign_group_refs"]) == 22
    assert set(song_portfolio["campaign_group_refs"]) <= current_event_ids
    assert all(
        set(opponent["source_campaign_refs"]) <= current_event_ids
        for opponent in song_portfolio["opponent_systems"]
    )
    assert portfolios["UCP-POST-JIN-1114-1126"]["created_net_control_value"] == 325.0
    assert portfolios["UCP-POST-JIN-1114-1126"]["horizontal_total_band"] == "H2"
    assert portfolios["UCP-POST-YUAN-1205-1279"]["created_net_control_value"] == 1140.0
    assert portfolios["UCP-POST-YUAN-1205-1279"]["horizontal_total_band"] == "H1"
    assert portfolios["UCP-POST-MING-1353-1382"]["created_net_control_value"] == 957.0
    assert portfolios["UCP-POST-MING-1353-1382"]["horizontal_total_band"] == "H2"
    assert portfolios["UCP-POST-QING-FOUNDING-1607-1662"]["created_net_control_value"] == 910.0
    assert portfolios["UCP-POST-QING-FOUNDING-1607-1662"]["horizontal_total_band"] == "H2"
    assert portfolios["UCP-POST-QING-REUNIFICATION-1673-1683"]["created_net_control_value"] == 0.0
    assert portfolios["UCP-POST-QING-REUNIFICATION-1673-1683"]["recovered_net_control_value"] == 300.0
    assert portfolios["UCP-POST-QING-REUNIFICATION-1673-1683"]["horizontal_total_band"] == "H3"
    assert all(
        delta["region_value_period_id"] == row["region_value_period_id"]
        and delta["war_region_grade"] in {"R2", "R3", "R4", "R5"}
        and delta["region_value_weight"] in {40.0, 60.0, 80.0, 100.0}
        for row in portfolios.values()
        for delta in row["control_audit"].get("control_deltas") or ()
    )
    region_policy = json.loads(
        (ROOT / "config/period-war-region-value-adjudications.json").read_text(
            encoding="utf-8"
        )
    )
    period_profiles = {
        row["period_id"]: row["regions"] for row in region_policy["period_profiles"]
    }
    assert period_profiles["WAR-REGION-TANG-617-628"]["MR-BASHU"]["R"] == "R3"
    assert period_profiles["WAR-REGION-THREE-KINGDOMS-184-280"]["MR-BASHU"]["R"] == "R5"
    assert all(
        row["defense_consumption"] == "EXCLUDED_UNIFICATION"
        for row in portfolios.values()
    )
    assert not any(row.get("campaign_tier") == "S+" for row in post_records)
    by_target = {row.get("source_target_ref"): row for row in post_records}
    assert by_target["CAMPAIGN-LIAO-PREACCESSION-EXPANSION-901-903"]["account_routing"] == ["UNIFICATION_ONLY"]
    assert by_target["CAMPAIGN-PROTO-JIN-SHILU-TRIBAL-CONSOLIDATION"]["defense_consumption"] == "EXCLUDED_UNIFICATION"
    assert by_target["CAMPAIGN-QING-TAIWAN-1683"]["campaign_tier"] == "S-"
    assert by_target["CAMPAIGN-QING-TAIWAN-1683"]["defense_consumption"] == "EXCLUDED_UNIFICATION"
    assert by_target["CAMPAIGN-MING-HUAI-EAST-CONQUEST-1366"]["merged_into"] == by_target["CAMPAIGN-MING-HUAIDONG-1365-1366"]["war_event_id"]
    assert not by_target["CAMPAIGN-MING-HUAI-EAST-CONQUEST-1366"]["public_outcome_registered"]
    five_dynasties = [
        row for row in payload["records"]
        if row.get("dynasty_partition") == "five_dynasties"
    ]
    assert len(five_dynasties) == 523
    assert sum(row["subject_phase_count"] for row in five_dynasties) == 1436
    assert all(row["wc_grade"] is None and row["security_grade"] is None for row in five_dynasties)
    assert {
        row["war_event_id"] for row in five_dynasties
        if row["record_level"] == "targeted_primary_source_supplement"
    } == {
        "WAR-FD-SUPPLEMENT-LATER-SHU-COLLAPSE-965",
        "WAR-FD-SUPPLEMENT-SOUTHERN-TANG-COLLAPSE-974-975",
    }
    north_song = [
        row for row in payload["records"]
        if row.get("dynasty_partition") == "north_song"
    ]
    assert len(north_song) == 716
    assert sum(row["subject_phase_count"] for row in north_song) == 1586
    assert all(row["record_level"] == "chronicle_battle_card" for row in north_song)
    assert all(row["wc_grade"] is None and row["security_grade"] is None for row in north_song)
    assert all(not row["war_event_id"].startswith("WAR-POST-") for row in north_song)
    assert not any(
        "docs/史料通读产物/唐以后编年/续资治通鉴-北宋" in source_file
        for row in north_song
        for source_file in row["source_lineage"]["source_files"]
    )


def test_current_talent_registry_keeps_card_partitions_outside_person_grade_consumption() -> None:
    battle = load_battle_registry(
        ROOT / "docs/公共成果/军事/01-战役登记.json"
    )
    talent = load_talent_registry(
        ROOT / "docs/公共成果/军事/02-武将人才等级.json"
    )
    lower_bounds = [profile for profile in talent["profiles"] if profile["grade_status"] == "evidence_lower_bound"]
    canonical_cards = [
        row for row in battle["records"]
        if row.get("dynasty_partition") in {"five_dynasties", "north_song"}
    ]
    assert talent["source_registry_fingerprint"] != battle["semantic_fingerprint"]
    assert canonical_cards
    assert all(not row.get("post_tang_evidence_lower_bound") for row in canonical_cards)
    assert all(not row.get("members") for row in canonical_cards)
    assert talent["evidence_lower_bound_profile_count"] == len(lower_bounds) == 733
    assert Counter(profile["military_grade"] for profile in lower_bounds) == {
        "capable": 23,
        "elite": 27,
        "historic": 4,
        "important": 166,
        "ordinary": 226,
        "top": 17,
        "usable": 270,
    }


def test_o4_recalibration_rejects_local_residual_and_duplicate_system_credit() -> None:
    accepted_o3_refs = {
        "BATTLE-LEAD-XZZTJ-167-WUXIAN-NINE-FORTS-1233",
        "BATTLE-LEAD-XZZTJ-183-E043",
        "CAMPAIGN-MING-JIAOZHI-REBELLION-1408-1414",
        "CAMPAIGN-QING-TAIPING-NORTHERN-EXPEDITION-1853-1855",
        "CAMPAIGN-QING-TIBET-CONQUEST-1720",
        "CAMPAIGN-SONG204-UPPER-CAPITAL-WAR",
        "CAMPAIGN-SONG210-XUZHOU-REDTURBAN",
        "CAMPAIGN-YUAN-TANZHOU-1276",
        "SPLIT-QING-ZHENG-TAIWAN-1661-1662",
        "WAR-LEAD-259-HUAINAN-END",
        "WAR-LEAD-261-BIANYUN-END",
        "WAR-LEAD-265-XIANGJING-END",
        "SPLIT-YUAN-NAYAN-MILITARY-1287",
        "CAMPAIGN-QING-GALDAN-FINAL-1696-1697",
    }
    review = json.loads(
        (ROOT / "config/high-tier-campaign-recalibrations.json").read_text(
            encoding="utf-8"
        )
    )
    audit_by_ref = {
        row["battle_ref"]: row
        for row in review["ordinary_high_tier_opponent_audit"]["adjudications"]
    }
    battle = load_battle_registry(
        ROOT / "docs/公共成果/军事/01-战役登记.json"
    )
    battle_by_ref = {row["war_event_id"]: row for row in battle["records"]}
    battle_by_ref.update(
        {
            row["source_target_ref"]: row
            for row in battle["records"]
            if row.get("source_target_ref") in accepted_o3_refs
        }
    )
    assert all(
        audit_by_ref[ref]["effective_opponent_grade"] == "O3"
        and audit_by_ref[ref]["final_tier"] == "A"
        and battle_by_ref[ref]["campaign_tier"] == "A"
        for ref in accepted_o3_refs
    )

    a_payload = build_first_item_a_registry(**_load_current_first_item_a_inputs())
    li_yuan = next(row for row in a_payload["records"] if row["ruler_name"] == "李渊")
    system_refs = {
        row["opponent_system_ref"] for row in li_yuan["A1"]["major_opponent_systems"]
    }
    assert "OPP-TANG-DOUJIANDE" in system_refs
    assert "OPP-TANG-LIUHEITA" not in system_refs
    assert next(
        row
        for row in li_yuan["A1"]["major_opponent_systems"]
        if row["opponent_system_ref"] == "OPP-TANG-EASTERN-TURKS"
    )["organization_grade"] == "O6"


def test_post_tang_ruler_operational_results_require_actual_design_not_authorization() -> None:
    battle = load_battle_registry(
        ROOT / "docs/公共成果/军事/01-战役登记.json"
    )
    talent = load_talent_registry(
        ROOT / "docs/公共成果/军事/02-武将人才等级.json"
    )
    by_target = {
        record.get("source_target_ref"): record for record in battle["records"]
    }

    expected = {
        "CAMPAIGN-YUAN-SONG-CONQUEST": ("忽必烈", "positive", "S"),
        "CAMPAIGN-MING-NORTHERN-EXPEDITION-1367-1368": ("朱元璋", "positive", "S"),
        "HANDOFF-XZZTJ-138-WULIN-RETREAT": ("赵昚", "negative", "S-"),
        "CAMPAIGN-QING-GALDAN-FINAL-1696-1697": ("玄烨", "positive", "A"),
    }
    for target_ref, (ruler, direction, tier) in expected.items():
        operational = [
            member
            for member in by_target[target_ref]["members"]
            if member["person_command_index"]["consumption_mode"]
            == "operational_result"
        ]
        assert [member["actor_name"] for member in operational] == [ruler]
        index = operational[0]["person_command_index"]
        assert index["capability_mode"] == "operational_design"
        assert index["result_direction"] == direction
        assert index["projected_result_tier"] == tier
        assert index["projected_combat_difficulty"] is None

    taiwan_names = {
        member["actor_name"]
        for member in by_target["CAMPAIGN-QING-TAIWAN-1683"]["members"]
    }
    assert "施琅" in taiwan_names
    assert "玄烨" not in taiwan_names
    assert "康熙" not in taiwan_names
    assert not [
        row
        for row in battle["records"]
        if row.get("public_outcome_registered")
        and row.get("post_tang_evidence_lower_bound")
        and row.get("command_status") == "PERSON_DETAIL_PENDING"
    ]
    assert Counter(
        row["command_status"]
        for row in battle["records"]
        if row.get("post_tang_evidence_lower_bound")
        and row.get("public_outcome_registered")
    ) == {
        "PERSON_COMMAND_UNKNOWN": 421,
        "RESOLVED_EXPLICIT_ACTORS": 498,
    }
    person_adjudications = json.loads(
        (ROOT / "config/post-tang-battle-person-adjudications.json").read_text(
            encoding="utf-8"
        )
    )
    differential_gate = person_adjudications["public_outcome_person_coverage_gate"][
        "resolved_record_differential_gate"
    ]
    assert differential_gate["reviewed_candidate_count"] == 98
    assert differential_gate["integrated_candidate_count"] == 94
    assert differential_gate["remaining_high_confidence_candidate_count"] == 0
    assert differential_gate["explicit_exclusion_count"] == 4
    by_person = {profile["person"]: profile for profile in talent["profiles"]}
    assert by_person["赵匡胤"]["military_grade"] == "important"
    assert len(by_person["赵匡胤"]["consumed_achievements"]) == 5
    assert len(by_person["边镐"]["consumed_achievements"]) == 1
    assert by_person["查文徽"]["military_grade"] == "ordinary"
    assert len(by_person["查文徽"]["attributable_failures"]) == 1
    assert len(by_person["张汉真"]["attributable_failures"]) == 1
    assert by_person["李存勖"]["military_grade"] == "historic"
    assert {
        row["decisive_relation"]
        for row in by_person["李存勖"]["consumed_achievements"]
    } == {
        "decisive_creator",
        "decisive_successor",
        "terminal_finisher",
        "co_decisive",
    }
    assert len(by_person["李存勖"]["consumed_achievements"]) == 10
    assert len(by_person["李存勖"]["attributable_failures"]) == 4
    assert by_person["朱元璋"]["military_grade"] == "top"
    assert len(by_person["朱元璋"]["consumed_achievements"]) == 9
    assert not by_person["朱元璋"]["attributable_failures"]
    assert by_person["徐达"]["military_grade"] == "historic"
    assert len(by_person["徐达"]["consumed_achievements"]) == 9
    assert len(by_person["徐达"]["attributable_failures"]) == 1
    assert by_person["徐达"]["attributable_failures"][0]["failure_impact_tier"] == "A"
    assert by_person["铁木真"]["name_aliases"] == ["成吉思汗", "蒙古太祖", "铁木真"]
    assert by_person["铁木真"]["military_grade"] == "historic"
    assert len(by_person["铁木真"]["consumed_achievements"]) == 11
    assert len(by_person["铁木真"]["negative_or_mixed_command_records"]) == 5
    assert len(by_person["铁木真"]["attributable_failures"]) == 3
    assert any(
        row["result_direction"] == "mixed_review"
        and "十三翼之战胜负存在史源冲突" in row["canonical_label"]
        and any(ref.startswith("元朝秘史/卷04@853105#") for ref in row["source_refs"])
        for row in by_person["铁木真"]["negative_or_mixed_command_records"]
    )
    assert by_person["朱棣"]["military_grade"] == "top"
    assert len(by_person["朱棣"]["consumed_achievements"]) == 10
    assert len(by_person["朱棣"]["negative_or_mixed_command_records"]) == 3
    assert len(by_person["朱棣"]["attributable_failures"]) == 3
    assert {row["failure_impact_tier"] for row in by_person["朱棣"]["attributable_failures"]} == {"A", "B"}
    assert by_person["李继迁"]["name_aliases"] == ["保吉", "李继迁", "赵保吉"]
    assert by_person["李继迁"]["military_grade"] == "important"
    assert len(by_person["李继迁"]["attributable_failures"]) == 5
    assert by_person["朱厚照"]["name_aliases"] == ["明武宗朱厚照", "朱厚照"]
    assert len(by_person["耶律阿保机"]["consumed_achievements"]) == 10
    assert len(by_person["曹彬"]["attributable_failures"]) == 2
    assert len(by_person["韩世忠"]["consumed_achievements"]) == 7
    assert len(by_person["韩世忠"]["attributable_failures"]) == 3
    assert len(by_person["刘法"]["attributable_failures"]) == 1
    assert len(by_person["蒙哥"]["attributable_failures"]) == 1
    assert len(by_person["僧格林沁"]["consumed_achievements"]) == 3
    assert len(by_person["僧格林沁"]["attributable_failures"]) == 1
    assert by_person["于谦"]["military_grade"] == "elite"
    assert by_person["石亨"]["military_grade"] == "important"
    assert by_person["蓝玉"]["military_grade"] == "elite"
    assert by_person["阿里海牙"]["military_grade"] == "important"
    assert by_person["吕文德"]["name_aliases"] == ["吕文德", "文德"]
    assert len(by_person["吕文德"]["consumed_achievements"]) == 2
    assert "文德" not in by_person
    by_target = {row.get("source_target_ref"): row for row in battle["records"]}
    for target_ref, actor_name in {
        "CAMPAIGN-JIN-SONG-SOUTHERN-PURSUIT-1129-1130": "完颜宗弼",
        "CAMPAIGN-XIXIA-HUANZHOU-BAIMAZU-1003": "赵保吉",
        "CAMPAIGN-LIAO-SONG-CHANYUAN-1004": "萧挞凛",
        "CAMPAIGN-SONG212-CHAHAN-HENAN": "察罕特穆尔",
    }.items():
        member = next(
            row for row in by_target[target_ref]["members"] if row["actor_name"] == actor_name
        )
        assert {row["result_direction"] for row in member["person_command_result"]} == {
            "positive",
            "negative",
        }
        assert any(
            row["actor_name"] == actor_name
            for row in by_target[target_ref]["attributable_failures"]
        )

    five_dynasties_a = [
        row for row in battle["records"]
        if row.get("dynasty_partition") == "five_dynasties"
        and row.get("tier_review_source_tier") == "A"
        and row.get("tier_adjudication_status") in {"ADJUDICATED_EXPLICIT", "REVIEWED_RETAINED_A"}
    ]
    assert five_dynasties_a == []
    assert all(
        row.get("record_level")
        in {"chronicle_battle_card", "targeted_primary_source_supplement"}
        and not row.get("members")
        and not row.get("attributable_failures")
        for row in battle["records"]
        if row.get("dynasty_partition") == "five_dynasties"
    )
    assert battle["post_tang_tier_review_summary"] == {
        "reviewed_batch_count": 9,
        "reviewed_record_count": 364,
            "explicit_s_tier_count": 76,
        "pending_a_review_count": 0,
        "difficulty_contract_reviewed_record_count": 104,
        "difficulty_contract_review_fingerprint": "f552e6042f5feef45521cd90764255649fadd53cee0df5a1345451f22f1bb2ec",
        "difficulty_contract_pending_count": 0,
    }

    liao_a = [
        row for row in battle["records"]
        if row.get("dynasty_partition") == "liao"
        and row.get("tier_review_source_tier") == "A"
        and row.get("tier_adjudication_status") in {"ADJUDICATED_EXPLICIT", "REVIEWED_RETAINED_A"}
    ]
    assert len(liao_a) == 11
    assert Counter(row["command_status"] for row in liao_a) == {
        "RESOLVED_EXPLICIT_ACTORS": 5,
        "PERSON_COMMAND_UNKNOWN": 6,
    }
    assert sum(len(row.get("members") or ()) for row in liao_a) == 8
    assert sum(len(row.get("attributable_failures") or ()) for row in liao_a) == 4
    assert not any(row["command_status"] == "PERSON_DETAIL_PENDING" for row in liao_a)
    assert Counter(row["campaign_tier"] for row in liao_a) == {"A": 10, "S-": 1}
    assert {
        row["source_target_ref"]
        for row in liao_a
        if row["campaign_tier"] == "S-"
        } == {
            "CAMPAIGN-LIAO-SHANXI-RECOVERY-AND-YANG-YE-CAPTURE-986",
        }


def test_current_registry_does_not_duplicate_literal_full_parent_consumption() -> None:
    battle = load_battle_registry(
        ROOT / "docs/公共成果/军事/01-战役登记.json"
    )
    records = battle["records"]

    duplicate_full_parent = {
        row["war_event_id"]: [
            member["actor_name"]
            for member in row.get("members") or ()
            if (member.get("person_command_index") or {}).get("consumption_mode")
            == "full_parent"
        ]
        for row in records
    }
    duplicate_full_parent = {
        event_id: names
        for event_id, names in duplicate_full_parent.items()
        if len(names) > 1
    }
    assert duplicate_full_parent == {}

    dali = next(
        row
        for row in records
        if row["war_event_id"] == "WAR-POST-711EBFAACFECB8C58F08"
    )
    dali_members = {member["actor_name"]: member for member in dali["members"]}
    assert (
        dali_members["忽必烈"]["person_command_index"]["command_scope"],
        dali_members["忽必烈"]["person_command_result"][0]["result_tier"],
        dali_members["兀良合台"]["person_command_index"]["command_scope"],
        dali_members["兀良合台"]["person_command_result"][0]["result_tier"],
    ) == ("full_campaign", "S-", "scoped_stage", "A")

    same_parent_scoped_exceptions = []
    for row in records:
        matching = []
        for member in row.get("members") or ():
            results = member.get("person_command_result") or ()
            if isinstance(results, dict):
                results = (results,)
            if any(
                result.get("result_direction") == "positive"
                and result.get("result_tier") == row.get("campaign_tier")
                and result.get("combat_difficulty") == row.get("combat_difficulty")
                for result in results
            ):
                matching.append(member)
        if len(matching) < 2 or row.get("campaign_tier") == "C":
            continue
        for member in matching:
            index = member.get("person_command_index") or {}
            if index.get("capability_mode") == "tactical_execution" or index.get(
                "decisive_relation"
            ) in {"stage_executor", "terminal_finisher"}:
                same_parent_scoped_exceptions.append(
                    (row["war_event_id"], member["actor_name"])
                )
    assert same_parent_scoped_exceptions == [
        ("WAR-POST-8FB3095C479B065DB083", "阿骨打")
    ]

    strict_examples = {
        row["war_event_id"]: {
            member["actor_name"]: member
            for member in row.get("members") or ()
        }
        for row in records
        if row["war_event_id"]
        in {
            "WAR-LEAD-TANG-GOGURYEO-645",
            "WAR-LEAD-TANG-ANSHI-END",
            "WAR-POST-6553D2D79DD1103A1546",
            "WAR-POST-967717D1C017F2D3443C",
        }
    }
    assert strict_examples["WAR-LEAD-TANG-GOGURYEO-645"]["李世勣"][
        "person_command_result"
    ]["result_tier"] == "A"
    assert strict_examples["WAR-LEAD-TANG-ANSHI-END"]["郭子仪"][
        "person_command_result"
    ][0]["result_tier"] == "A"
    assert strict_examples["WAR-POST-6553D2D79DD1103A1546"]["速不台"][
        "person_command_result"
    ][0]["result_tier"] == "S-"
    nian = strict_examples["WAR-POST-967717D1C017F2D3443C"]["年羹尧"]
    assert (
        nian["person_command_index"]["command_scope"],
        nian["person_command_result"][0]["result_tier"],
        nian["person_command_result"][0]["combat_difficulty"],
    ) == ("full_campaign", "A", "D2")
    talent = load_talent_registry(
        ROOT / "docs/公共成果/军事/02-武将人才等级.json"
    )
    assert not [
        profile
        for profile in talent["profiles"]
        if profile["grade_status"] == "lower_bound_pending_person_result"
    ]


def test_elite_review_closes_major_defeat_accountability_and_applies_caps() -> None:
    talent = load_talent_registry(
        ROOT / "docs/公共成果/军事/02-武将人才等级.json"
    )
    by_name = {profile["person"]: profile for profile in talent["profiles"]}
    reviewed = [
        profile
        for profile in talent["profiles"]
        if profile["military_grade"] in {"elite", "top", "historic"}
        or "blocked_by_failure_pressure" in profile["rule_path"]
    ]
    for profile in reviewed:
        for row in profile.get("failure_accountability") or ():
            if row.get("campaign_tier") not in {"A", "S-", "S", "S+"}:
                continue
            if row.get("combat_difficulty") not in {"D2", "D3", "D4"}:
                continue
            assert row.get("outcome_responsibility")
            assert row.get("causal_fault") not in {None, "", "UNKNOWN"}

    assert by_name["苏定方"]["military_grade"] == "historic"
    assert by_name["刘裕"]["military_grade"] == "top"
    assert by_name["马援"]["military_grade"] == "elite"
    assert by_name["铁木真"]["military_grade"] == "historic"
    assert by_name["吴汉"]["military_grade"] == "elite"
    assert by_name["郭子仪"]["military_grade"] == "elite"
    assert by_name["吴璘"]["military_grade"] == "elite"
    assert by_name["陈庆之"]["military_grade"] == "top"
    assert any(
        row.get("causal_fault") == "NO_FAULT_MANDATORY_ORDER"
        for row in by_name["吴璘"]["failure_accountability"]
    )
    assert any(
        row.get("causal_fault") == "NO_FAULT_EXTERNAL_DISASTER"
        for row in by_name["陈庆之"]["failure_accountability"]
    )
    assert any(
        row.get("causal_fault") == "ATTRIBUTABLE_ROUTE_SELECTION"
        for row in by_name["马援"]["failure_accountability"]
    )
