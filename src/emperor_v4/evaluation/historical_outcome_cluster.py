from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from emperor_v4.adapters.structured_output_contract import (
    validate_payload_against_schema,
)
from emperor_v4.contracts.episode import (
    AssertionLink,
    EpisodeParticipant,
    HistoricalEpisodePacket,
)
from emperor_v4.persistence.canonical_refs import canonical_hashed_ref, canonical_person_ref
from emperor_v4.evaluation.talent_grade_domain_equivalence import (
    assess_domain_historic_path,
)


SCHEMA_VERSION = "historical-outcome-cluster-registry-v2"
SCALES = ("local", "important", "regional", "national", "era_shaping")
CAMPAIGN_TIERS = ("C", "B", "A", "S-", "S", "S+")
STRATEGIC_RESULT_TIER = {
    "local_tactical": "C",
    "important_objective": "B",
    "major_stage_or_crisis": "A",
    "independent_direction": "S-",
    "single_pole_or_state_terminal": "S",
    "composite_poles_terminal": "S+",
    "unification_terminal": "S+",
    "external_hegemony_terminal": "S+",
}
LEGACY_CAMPAIGN_TIER_BY_SCALE = {
    "local": "C",
    "important": "B",
    "regional": "A",
    "national": "S",
    "era_shaping": "S+",
}
REALIZED_RESULTS = {"implemented", "operated", "completed", "mixed"}
TALENT_GRADES = ("ordinary", "usable", "important", "top", "historic")
CAMPAIGN_ROLES = {
    "commander_in_chief": "主帅",
    "principal_commander": "主将",
    "participant": "从攻",
    "not_in_command_chain": "不在军事指挥链",
}
RULER_CAMPAIGN_RELATIONS = {
    "authorization_only": "仅授权",
    "operational_direction": "战役筹划与统筹",
    "frontline_command": "前线最高指挥",
}
LAND_STRATEGIC_VALUES = {
    "local_point": "局部据点",
    "important_region": "重要区域",
    "strategic_gateway": "战略门户",
    "core_heartland": "核心根据地",
    "capital_or_state_survival": "都城或国家存亡区",
}
def campaign_tier(cluster: Mapping[str, object]) -> str:
    payload = cluster.get("payload") or {}
    explicit = str(payload.get("campaign_tier") or "")
    if explicit:
        return explicit
    return LEGACY_CAMPAIGN_TIER_BY_SCALE[str(cluster["scale"]["level"])]
GOVERNANCE_ROLES = {
    "exclusive": "独占",
    "lead": "主导",
    "governance_participant": "参与",
    "authorized": "授权",
    "reign_holder": "统治窗口归属",
}
STATECRAFT_ROLES = GOVERNANCE_ROLES
COUNTED_TOP_ROLES = {
    "campaign": {"commander_in_chief", "principal_commander"},
    "governance": {"exclusive", "lead"},
    "statecraft": {"exclusive", "lead"},
}
COUNTED_IMPORTANT_ROLES = {
    "campaign": COUNTED_TOP_ROLES["campaign"],
    "governance": COUNTED_TOP_ROLES["governance"],
    "statecraft": COUNTED_TOP_ROLES["statecraft"],
}
CAMPAIGN_SCALE_BASES = {
    "local": {"local_tactical"},
    "important": {"important_objective"},
    "regional": {"regional_theater_control"},
    "national": {
        "national_war_outcome",
        "state_survival",
        "unification",
        "state_conquest",
    },
    "era_shaping": {"era_order_reconstruction"},
}
GOVERNANCE_SCALE_BASES = {
    "local": {"local_public_result"},
    "important": {"important_public_result"},
    "regional": {"regional_governance_result"},
    "national": {
        "national_core_subsystem",
        "national_public_result",
        "national_cultural_corpus",
    },
    "era_shaping": {
        "era_order_reconstruction",
        "civilization_foundational_corpus",
    },
}


def _digest(value: object) -> str:
    return sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def outcome_episode_ref(cluster: Mapping[str, object]) -> str:
    identity = {
        "kind": cluster["outcome_kind"],
        "independent_key": cluster["independent_key"],
    }
    return "EP-OUTCOME-" + _digest(identity)[:20].upper()


def cluster_semantic_fingerprint(cluster: Mapping[str, object]) -> str:
    unsigned = dict(cluster)
    unsigned.pop("semantic_fingerprint", None)
    return _digest(unsigned)


def validate_historical_outcome_registry(
    registry: Mapping[str, object],
    *,
    schema_path: Path,
    facts: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validate_payload_against_schema(registry, schema)
    clusters = list(registry.get("clusters") or ())
    clusters_by_ref = {str(row["outcome_ref"]): row for row in clusters}
    refs: set[str] = set()
    keys: set[tuple[str, str]] = set()
    episode_refs: set[str] = set()
    actor_refs: set[str] = set()
    counts = {"campaign": 0, "governance": 0, "statecraft": 0}
    for cluster in clusters:
        ref = str(cluster["outcome_ref"])
        kind = str(cluster["outcome_kind"])
        settlement_scope = str(cluster["settlement_scope"])
        if kind == "campaign" and settlement_scope not in {
            "war_terminal_context",
            "ruler_campaign_parent",
            "person_campaign_subresult",
        }:
            raise ValueError(f"{ref} 战役结算范围不正确")
        if kind == "governance" and settlement_scope not in {
            "governance_result",
            "person_governance_result",
            "reign_macro_outcome",
        }:
            raise ValueError(f"{ref} 治理结算范围不正确")
        if kind == "statecraft" and settlement_scope != "person_statecraft_result":
            raise ValueError(f"{ref} 谋略成果只能进入人物画像结算")
        key = (kind, str(cluster["independent_key"]))
        if ref in refs or key in keys:
            raise ValueError("成果簇身份或同类 independent_key 重复")
        refs.add(ref)
        keys.add(key)
        counts[kind] += 1
        expected_episode_ref = outcome_episode_ref(cluster)
        if list(cluster["episode_refs"]) != [expected_episode_ref]:
            raise ValueError(f"{ref} 当前成果簇必须引用确定性 Episode")
        if expected_episode_ref in episode_refs:
            raise ValueError("不同成果簇不得共享同一个确定性 Episode 身份")
        episode_refs.add(expected_episode_ref)
        if cluster["semantic_fingerprint"] != cluster_semantic_fingerprint(cluster):
            raise ValueError(f"{ref} semantic_fingerprint 不匹配")
        unknown_facts = sorted(set(cluster["fact_refs"]) - set(facts))
        if unknown_facts:
            raise ValueError(f"{ref} 引用未知当前事实: {unknown_facts}")
        derived_sources = {
            f"{facts[str(fact_ref)]['source_page']}@"
            f"{facts[str(fact_ref)]['revision_ref']}"
            for fact_ref in cluster["fact_refs"]
        }
        if any(
            not any(str(source_ref).startswith(derived) for source_ref in cluster["source_refs"])
            for derived in derived_sources
        ):
            raise ValueError(f"{ref} source_refs 未覆盖事实史源")
        role_contract = CAMPAIGN_ROLES if kind == "campaign" else GOVERNANCE_ROLES
        members = list(cluster["members"])
        member_keys = {
            (str(row["actor_ref"]), str(row["actor_kind"])) for row in members
        }
        if len(member_keys) != len(members):
            raise ValueError(f"{ref} 成果成员重复")
        for member in members:
            if member["role_code"] not in role_contract:
                raise ValueError(f"{ref} 成员角色不属于 {kind} 合同")
            if member.get("ruler_campaign_relation") is not None and (
                kind != "campaign" or member.get("sovereign_at_event") is not True
            ):
                raise ValueError(f"{ref} 只有事件发生时的实际统治者可以登记控制方式")
            actor_refs.add(str(member["actor_ref"]))
            if kind == "campaign" and not member.get("talent_credit"):
                raise ValueError(f"{ref} 战役成员缺少人才独立信用声明")
        level = str(cluster["scale"]["level"])
        basis = str(cluster["scale"]["consequence_basis"])
        bases = CAMPAIGN_SCALE_BASES if kind == "campaign" else GOVERNANCE_SCALE_BASES
        if basis not in bases[level]:
            raise ValueError(f"{ref} 规模与 consequence_basis 不匹配")
        if kind == "campaign":
            payload = cluster["payload"]
            required_campaign_fields = {
                "theater": payload.get("theater"),
                "strategic_objective": payload.get("strategic_objective"),
                "battle_result": payload.get("battle_result"),
                "objective_completion": payload.get("objective_completion"),
                "opponent_condition": payload.get("opponent_condition"),
                "opponent_strategic_weight": payload.get(
                    "opponent_strategic_weight"
                ),
                "strategic_result_class": payload.get("strategic_result_class"),
                "campaign_tier": payload.get("campaign_tier"),
                "campaign_tier_basis": payload.get("campaign_tier_basis"),
                "land_strategic_value": payload.get("land_strategic_value"),
                "strategic_stakes": payload.get("strategic_stakes"),
                "prewar_context": payload.get("prewar_context"),
                "failure_stakes": payload.get("failure_stakes"),
                "combat_difficulty": payload.get("combat_difficulty"),
                "combat_difficulty_basis": payload.get("combat_difficulty_basis"),
            }
            missing_campaign_fields = [
                key for key, value in required_campaign_fields.items() if not value
            ]
            if missing_campaign_fields:
                raise ValueError(
                    f"{ref} 战役必须声明战区、目标、背景、利害、三轴、战略结果、难度和等级: "
                    + ", ".join(missing_campaign_fields)
                )
            strategic_result_class = str(payload["strategic_result_class"])
            expected_tier = STRATEGIC_RESULT_TIER[strategic_result_class]
            if payload["campaign_tier"] != expected_tier:
                raise ValueError(
                    f"{ref} 战略结果类 {strategic_result_class} 必须映射为 {expected_tier}"
                )
            for field in (
                "operational_costs",
                "objective_shortfalls",
                "attributable_failures",
            ):
                for item in payload.get(field) or ():
                    if any(
                        str(source_ref) not in cluster["source_refs"]
                        for source_ref in item["source_refs"]
                    ):
                        raise ValueError(f"{ref} {field} 史源必须来自战役簇")
            for failure in payload.get("attributable_failures") or ():
                if not failure.get("actor_ref") or not failure.get("actor_name"):
                    raise ValueError(f"{ref} 可归责失败必须绑定责任人")
                if failure.get("severity_index") not in {0.2, 0.4, 0.6, 0.7, 1}:
                    raise ValueError(f"{ref} 可归责失败严重度非法")
            sovereign_members = [
                member for member in members if member.get("sovereign_at_event") is True
            ]
            if len(sovereign_members) > 1:
                raise ValueError(f"{ref} 战役不能登记多个事件实际统治者")
            if sovereign_members:
                sovereign_member = sovereign_members[0]
                relation = str(
                    sovereign_member.get("ruler_campaign_relation") or ""
                )
                if not relation:
                    raise ValueError(f"{ref} 事件实际统治者缺少唯一控制方式")
                if (
                    relation == "authorization_only"
                    and sovereign_member["role_code"] != "not_in_command_chain"
                ):
                    raise ValueError(f"{ref} 仅授权的统治者不得进入军事指挥链")
                if (
                    relation != "authorization_only"
                    and sovereign_member["role_code"] == "not_in_command_chain"
                ):
                    raise ValueError(f"{ref} 进入战区统筹的统治者必须登记实际指挥角色")
                if relation == "authorization_only" and not sovereign_member.get(
                    "authorization_mode"
                ):
                    raise ValueError(f"{ref} 仅授权必须区分正式授权或默许")
                if relation in {
                    "operational_direction",
                    "frontline_command",
                } and not sovereign_member.get("control_extent"):
                    raise ValueError(f"{ref} 战区控制必须声明覆盖范围")
            for member in members:
                if member.get("sovereign_at_event") is not True and any(
                    member.get(field) is not None
                    for field in (
                        "ruler_campaign_relation",
                        "authorization_mode",
                        "control_extent",
                        "obstruction_status",
                    )
                ):
                    raise ValueError(f"{ref} 非事件统治者不得携带统治者控制字段")
            parent_ref = str(cluster.get("parent_outcome_ref") or "")
            parent = clusters_by_ref.get(parent_ref) if parent_ref else None
            if settlement_scope == "war_terminal_context":
                if parent_ref:
                    raise ValueError(f"{ref} 战争终局根节点不得再有父级")
                if any(
                    member.get("talent_credit") != "not_applicable"
                    for member in members
                ):
                    raise ValueError(f"{ref} 战争终局根节点不得进入人才结算")
            elif settlement_scope == "ruler_campaign_parent" and parent_ref:
                if (
                    not parent
                    or parent.get("outcome_kind") != "campaign"
                    or parent.get("settlement_scope") != "war_terminal_context"
                ):
                    raise ValueError(f"{ref} 战役群父级必须是战争终局根节点")
            if settlement_scope == "person_campaign_subresult":
                if (
                    not parent
                    or parent.get("outcome_kind") != "campaign"
                    or parent.get("settlement_scope") != "ruler_campaign_parent"
                ):
                    raise ValueError(f"{ref} 人物子战役缺少有效父级战役群")
            if settlement_scope != "war_terminal_context" and not any(
                member["role_code"]
                in {"commander_in_chief", "principal_commander", "participant"}
                for member in members
            ):
                raise ValueError(f"{ref} 父级战役群缺少实际军事指挥链成员")
            tier_basis = str(payload["campaign_tier_basis"])
            required_axis_values = (
                f"土地轴={payload['land_strategic_value']}",
                f"对手轴={payload['opponent_strategic_weight']}/{payload['opponent_condition']}",
                f"结果轴={payload['battle_result']}/{payload['objective_completion']}",
            )
            if not all(token in tier_basis for token in required_axis_values):
                raise ValueError(f"{ref} 战役定级依据与土地、对手或结果字段不一致")
            if payload["campaign_tier"] == "S+" and strategic_result_class not in {
                "composite_poles_terminal",
                "unification_terminal",
                "external_hegemony_terminal",
            }:
                raise ValueError(f"{ref} S+ 不属于允许的战略终局路径")
            if payload["campaign_tier"] == "S+" and (
                payload["battle_result"] != "victory"
                or payload["objective_completion"] != "complete"
            ):
                raise ValueError(f"{ref} S+ 必须实际取得胜利并完成终局目标")
            required_opponent_weight = {
                "composite_poles_terminal": {"first_tier_pole", "dominant_pole"},
                "unification_terminal": {"dominant_pole"},
                "external_hegemony_terminal": {"external_hegemony"},
            }.get(strategic_result_class)
            if required_opponent_weight and payload[
                "opponent_strategic_weight"
            ] not in required_opponent_weight:
                raise ValueError(f"{ref} S+ 战略终局与对手竞争位置不匹配")
            if payload["campaign_tier"] in {"S", "S+"} and payload[
                "opponent_condition"
            ] == "residual":
                raise ValueError("残余对手不能仅凭灭国名义登记为S级以上")
        else:
            payload = cluster["payload"]
            if (
                settlement_scope == "person_governance_result"
                and cluster["ruler_window_status"] != "outside_window"
            ):
                raise ValueError(f"{ref} 人物生涯治理成果必须位于当前皇帝窗口之外")
            missing_governance_fields = [
                key
                for key in ("domain", "authorization_status", "causal_attribution_status")
                if not payload.get(key)
            ]
            missing_governance_fields.extend(
                key
                for key in ("foundational", "durable_cross_stage")
                if not isinstance(payload.get(key), bool)
            )
            if missing_governance_fields:
                raise ValueError(
                    f"{ref} 治理成果必须声明领域、授权与持续性: "
                    + ", ".join(missing_governance_fields)
                )
            substantive_members = [
                member
                for member in members
                if member["role_code"]
                in {"exclusive", "lead", "governance_participant"}
            ]
            if settlement_scope == "reign_macro_outcome":
                causal_status = str(payload["causal_attribution_status"])
                if causal_status == "source_attributed":
                    if not any(
                        member["actor_kind"] == "ruler"
                        and member["role_code"] in {"exclusive", "lead"}
                        for member in members
                    ):
                        raise ValueError(f"{ref} 史源归因宏观结果缺少总体治理主导者")
                elif causal_status == "limited":
                    if not any(
                        member["actor_kind"] == "ruler"
                        and member["role_code"] == "reign_holder"
                        for member in members
                    ):
                        raise ValueError(f"{ref} 因果有限宏观结果缺少统治窗口归属")
                else:
                    raise ValueError(f"{ref} 宏观统治结果因果归责状态不正确")
            elif not substantive_members:
                raise ValueError(f"{ref} 治理或谋略成果不能只有授权者")
            exclusive_members = [
                member for member in members if member["role_code"] == "exclusive"
            ]
            if exclusive_members and len(substantive_members) != 1:
                raise ValueError(f"{ref} exclusive 不能与其他实施责任角色并列")
        if (
            cluster["result_direction"] == "positive"
            and cluster["result_status"] not in REALIZED_RESULTS
        ):
            raise ValueError("未实现成果不得登记为正向结果")
    return {
        "schema_version": "historical-outcome-cluster-validation-v1",
        "status": "passed",
        "cluster_count": len(clusters),
        "kind_counts": counts,
        "episode_count": len(episode_refs),
        "actor_count": len(actor_refs),
        "database_write_count": 0,
    }


def build_outcome_episode(
    cluster: Mapping[str, object],
    *,
    facts: Mapping[str, Mapping[str, object]],
) -> HistoricalEpisodePacket:
    fact_rows = [facts[str(ref)] for ref in cluster["fact_refs"]]
    assertion_links = []
    for fact in fact_rows:
        for assertion in fact.get("assertions") or ():
            assertion_links.append(
                AssertionLink(
                    assertion_ref=str(assertion["assertion_ref"]),
                    source_passage_ref=(
                        f"{fact['source_page']}@{fact['revision_ref']}#"
                        f"{assertion['locator_anchor']}"
                    ),
                    relation="supports",
                    supported_fields=("identity", "action", "outcome"),
                    evidence_status="accepted",
                    representative=not assertion_links,
                )
            )
    if not assertion_links:
        raise ValueError(f"{cluster['outcome_ref']} 缺少 Assertion lineage")
    def episode_person_ref(actor_ref: object) -> str:
        canonical = canonical_person_ref(actor_ref)
        return (
            canonical
            if canonical.startswith("PER-")
            else canonical_hashed_ref("PER-V4", actor_ref, length=12)
        )

    members = list(cluster["members"])
    if members:
        primary_actor_ref = next(
            (
                row["actor_ref"]
                for row in members
                if row["actor_kind"] == "person"
            ),
            members[0]["actor_ref"],
        )
        participants = tuple(
            EpisodeParticipant(
                person_ref=episode_person_ref(row["actor_ref"]),
                role_codes=(str(row["role_code"]),),
                role_status="resolved",
            )
            for row in members
        )
        responsibility = "；".join(
            f"{row['actor_name']}以{row['role_code']}承担{row['contribution_scope']}"
            for row in members
        )
    else:
        # 战争总终局根不承载皇帝或人才结算，但 Episode 合同仍需用史源中
        # 已解析的人物维持 identity lineage；这些参与者不反写成果 members。
        fact_actors = list(
            dict.fromkeys(
                str(fact["person_ref"])
                for fact in fact_rows
                if fact.get("person_ref")
            )
        )
        if not fact_actors:
            raise ValueError(f"{cluster['outcome_ref']} 战争总终局缺少人物 lineage")
        primary_actor_ref = fact_actors[0]
        participants = (
            EpisodeParticipant(
                person_ref=episode_person_ref(primary_actor_ref),
                role_codes=("participant",),
                role_status="resolved",
            ),
        )
        responsibility = "战争总终局只表达总结果，不承担皇帝或人才结算"
    provenance = {
        "builder": "historical_outcome_cluster_v1",
        "input_hash": cluster_semantic_fingerprint(cluster),
    }
    return HistoricalEpisodePacket(
        episode_id=outcome_episode_ref(cluster),
        episode_type=f"{cluster['outcome_kind']}_outcome_chain",
        episode_status="accepted",
        evaluation_context=episode_person_ref(primary_actor_ref),
        semantic_fingerprint=_digest(
            {
                "cluster": cluster["semantic_fingerprint"],
                "facts": list(cluster["fact_refs"]),
            }
        ),
        time_start=str(cluster["period"]["start"]),
        time_end=str(cluster["period"]["end"]),
        time_precision="historical_text_range",
        locations=tuple(
            [str(cluster["payload"]["theater"])]
            if cluster["outcome_kind"] == "campaign"
            else ()
        ),
        participants=participants,
        action=str(cluster["canonical_label"]),
        responsibility=responsibility,
        outcome=(str(cluster["observable_result"]),),
        consequence=(str(cluster["scale"]["reason"]),),
        assertion_links=tuple(assertion_links),
        conflicts=(),
        uncertainties=tuple(str(value) for value in cluster["limitations"]),
        completeness={
            "identity": "complete",
            "time": "complete",
            "action": "complete",
            "responsibility": "complete",
            "outcome": "complete",
            "consequence": "complete",
            "source_diversity": "partial",
            "conflict_resolution": "not_applicable",
        },
        lineage={"source_refs": ";".join(cluster["source_refs"])},
        provenance=provenance,
    )


def _assess_person_talent_grade_single_domain(
    *,
    person_ref: str,
    clusters: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    scale_rank = {value: index for index, value in enumerate(SCALES)}
    tier_rank = {value: index for index, value in enumerate(CAMPAIGN_TIERS)}
    eligible = []
    for cluster in clusters:
        if (
            cluster["result_status"] not in REALIZED_RESULTS
            or cluster.get("settlement_scope") == "war_terminal_context"
        ):
            continue
        member = next(
            (
                row
                for row in cluster["members"]
                if str(row["actor_ref"]) == person_ref
            ),
            None,
        )
        if member is None:
            continue
        if (
            cluster["outcome_kind"] == "campaign"
            and member.get("talent_credit") != "independent"
        ):
            continue
        kind = str(cluster["outcome_kind"])
        role = str(member["role_code"])
        if role not in COUNTED_IMPORTANT_ROLES[kind]:
            continue
        eligible.append((cluster, member))
    top_eligible = [
        (cluster, member)
        for cluster, member in eligible
        if member["role_code"] in COUNTED_TOP_ROLES[str(cluster["outcome_kind"])]
        and (
            cluster["result_direction"] != "mixed"
            or bool(cluster["stable_delivery"])
        )
    ]
    historic_candidates: list[tuple[str, dict[str, object], list[tuple[Mapping[str, object], Mapping[str, object]]]]] = []
    for outcome_kind, domain in (("campaign", "military"), ("governance", "civil_governance")):
        domain_rows = [
            (cluster, member)
            for cluster, member in top_eligible
            if cluster["outcome_kind"] == outcome_kind
        ]
        achievements = []
        for cluster, member in domain_rows:
            status = str(cluster["result_status"])
            result = (
                "implemented_mixed"
                if cluster["result_direction"] == "mixed"
                else "completed_positive"
                if status == "completed"
                else "implemented_positive"
            )
            achievements.append(
                {
                    "independent_key": cluster["independent_key"],
                    "scale": cluster["scale"]["level"],
                    "campaign_tier": (
                        campaign_tier(cluster)
                        if outcome_kind == "campaign"
                        else None
                    ),
                    "responsibility_role": (
                        "participant"
                        if member["role_code"] == "governance_participant"
                        else member["role_code"]
                    ),
                    "result": result,
                    "positive_result_preserved": bool(cluster["stable_delivery"]),
                    "consequence_basis": cluster["scale"]["consequence_basis"],
                    "decisive": cluster["scale"]["decisiveness"] == "decisive",
                    "foundational": bool((cluster.get("payload") or {}).get("foundational")),
                    "durable_cross_stage": bool(
                        (cluster.get("payload") or {}).get("durable_cross_stage")
                    ),
                }
            )
        assessment = assess_domain_historic_path(domain, achievements)
        if assessment["historic_fact_path_status"] == "eligible":
            matched_keys = {
                str(value)
                for value in assessment.get("matched_independent_keys", [])
            }
            counted_rows = (
                [
                    row
                    for row in domain_rows
                    if str(row[0]["independent_key"]) in matched_keys
                ]
                if matched_keys
                else domain_rows
            )
            historic_candidates.append((domain, assessment, counted_rows))
    top_anchors = [
        row
        for row in top_eligible
        if (
            row[0]["outcome_kind"] == "campaign"
            and tier_rank[campaign_tier(row[0])] >= tier_rank["S-"]
        )
        or (
            row[0]["outcome_kind"] == "governance"
            and scale_rank[str(row[0]["scale"]["level"])] >= scale_rank["national"]
        )
    ]
    second_major = [
        row
        for row in top_eligible
        if (
            row[0]["outcome_kind"] == "campaign"
            and tier_rank[campaign_tier(row[0])] >= tier_rank["A"]
        )
        or (
            row[0]["outcome_kind"] == "governance"
            and scale_rank[str(row[0]["scale"]["level"])] >= scale_rank["regional"]
        )
    ]
    top_candidate = None
    for top_anchor in top_anchors:
        outcome_kind = str(top_anchor[0]["outcome_kind"])
        same_domain_major = [
            row for row in second_major if row[0]["outcome_kind"] == outcome_kind
        ]
        supported = bool(
            (
                outcome_kind == "campaign"
                and campaign_tier(top_anchor[0]) == "S+"
            )
            or top_anchor[0]["stable_delivery"]
            or top_anchor[0]["important_method_or_legacy"]
            or any(
                row[0]["outcome_ref"] != top_anchor[0]["outcome_ref"]
                for row in same_domain_major
            )
        )
        if supported:
            top_candidate = (top_anchor, same_domain_major)
            break
    statecraft_national = [
        row
        for row in top_eligible
        if row[0]["outcome_kind"] == "statecraft"
        and scale_rank[str(row[0]["scale"]["level"])] >= scale_rank["national"]
    ]
    if len(statecraft_national) >= 3:
        grade = "historic"
        rule_path = "statecraft_three_national_results"
        counted = statecraft_national
    elif len(statecraft_national) >= 2:
        grade = "top"
        rule_path = "statecraft_two_national_results"
        counted = statecraft_national
    elif historic_candidates:
        domain, historic_assessment, counted = historic_candidates[0]
        grade = "historic"
        rule_path = str(historic_assessment["matched_path"])
    elif top_candidate is not None:
        grade = "top"
        rule_path = "top_fallback"
        counted = top_candidate[1]
    elif eligible:
        important_governance = [
            row
            for row in eligible
            if row[0]["outcome_kind"] == "governance"
            and scale_rank[str(row[0]["scale"]["level"])] >= scale_rank["important"]
        ]
        important_statecraft = [
            row
            for row in eligible
            if row[0]["outcome_kind"] == "statecraft"
            and scale_rank[str(row[0]["scale"]["level"])] >= scale_rank["regional"]
        ]
        important_campaigns = [
            row
            for row in eligible
            if row[0]["outcome_kind"] == "campaign"
            and tier_rank[campaign_tier(row[0])] >= tier_rank["A"]
        ]
        supporting_campaigns = [
            row
            for row in eligible
            if row[0]["outcome_kind"] == "campaign"
            and tier_rank[campaign_tier(row[0])] >= tier_rank["B"]
        ]
        important = [*important_governance, *important_campaigns, *important_statecraft]
        if not important and len(supporting_campaigns) >= 2:
            important = supporting_campaigns
        if important:
            grade = "important"
            rule_path = "domain_important_threshold"
            counted = important
        else:
            grade = "usable"
            rule_path = "domain_usable_threshold"
            counted = eligible
    else:
        grade = "ordinary"
        rule_path = "coverage_complete_below_usable"
        counted = []
    role_labels = {**CAMPAIGN_ROLES, **GOVERNANCE_ROLES}
    basis_parts = []
    for cluster, member in counted:
        result_scope = ""
        if cluster["result_direction"] == "mixed":
            result_scope = "；专业目标已实现，整体混合结果及跨领域代价另行结算"
        level_text = (
            f"{campaign_tier(cluster)}级战役群"
            if cluster["outcome_kind"] == "campaign"
            else (
                f"{cluster['scale']['level']}级治理结果"
                if cluster["outcome_kind"] == "governance"
                else f"{cluster['scale']['level']}级谋略结果"
            )
        )
        basis_parts.append(
            f"作为{role_labels[str(member['role_code'])]}完成“{cluster['canonical_label']}”，"
            f"属{level_text}{result_scope}"
        )
    basis = "；".join(basis_parts) or "完整覆盖后未建立达到可用门槛的独立成果簇"
    return {
        "grade": grade,
        "basis": basis + "。",
        "policy_ref": "config/talent-grade-v11-domain-equivalent-historic.yml",
        "rule_path": rule_path,
        "outcome_refs": sorted(str(row[0]["outcome_ref"]) for row in counted),
        "eligible_outcome_count": len(eligible),
        "status": "accepted_current",
    }


def _culture_talent_grade(
    *,
    person_ref: str,
    clusters: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    scale_rank = {value: index for index, value in enumerate(SCALES)}
    eligible: list[tuple[Mapping[str, object], Mapping[str, object]]] = []
    for cluster in clusters:
        if cluster["outcome_kind"] != "governance":
            continue
        if (cluster.get("payload") or {}).get("domain") != "culture_scholarship":
            continue
        if cluster["result_status"] not in REALIZED_RESULTS:
            continue
        member = next(
            (
                row
                for row in cluster["members"]
                if str(row["actor_ref"]) == person_ref
            ),
            None,
        )
        if member is None or member["role_code"] not in {"exclusive", "lead"}:
            continue
        if cluster["result_direction"] == "mixed" and not cluster["stable_delivery"]:
            continue
        eligible.append((cluster, member))
    national = [
        row
        for row in eligible
        if scale_rank[str(row[0]["scale"]["level"])] >= scale_rank["national"]
    ]
    achievements = [
        {
            "independent_key": cluster["independent_key"],
            "scale": cluster["scale"]["level"],
            "responsibility_role": member["role_code"],
            "result": (
                "implemented_mixed"
                if cluster["result_direction"] == "mixed"
                else "completed_positive"
                if cluster["result_status"] == "completed"
                else "implemented_positive"
            ),
            "positive_result_preserved": bool(cluster["stable_delivery"]),
            "foundational": bool((cluster.get("payload") or {}).get("foundational")),
            "durable_cross_stage": bool(
                (cluster.get("payload") or {}).get("durable_cross_stage")
            ),
            "personally_authored_or_finalized": bool(
                (cluster.get("payload") or {}).get("personally_authored_or_finalized")
            ),
        }
        for cluster, member in eligible
    ]
    historic = assess_domain_historic_path("culture_and_scholarship", achievements)
    if historic["historic_fact_path_status"] == "eligible":
        grade = "historic"
        rule_path = str(historic["matched_path"])
        counted = eligible
    elif national and (
        len(eligible) >= 2
        or any(row[0]["stable_delivery"] for row in national)
        or any(row[0]["important_method_or_legacy"] for row in national)
    ):
        grade = "top"
        rule_path = "culture_top_fallback"
        counted = eligible
    elif eligible:
        grade = "important"
        rule_path = "culture_important_threshold"
        counted = eligible
    else:
        grade = "ordinary"
        rule_path = "coverage_complete_below_usable"
        counted = []
    basis = "；".join(
        f"作为{GOVERNANCE_ROLES[str(member['role_code'])]}完成“{cluster['canonical_label']}”，"
        f"属{cluster['scale']['level']}级文化学术结果"
        for cluster, member in counted
    )
    return {
        "grade": grade,
        "basis": (basis or "未建立达到可用门槛的文化学术成果") + "。",
        "rule_path": rule_path,
        "outcome_refs": sorted(str(row[0]["outcome_ref"]) for row in counted),
        "eligible_outcome_count": len(eligible),
    }


def assess_person_talent_grade(
    *,
    person_ref: str,
    clusters: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """先分领域定档，再取最高领域；仅显式全能路径允许跨领域升档。"""

    domain_clusters = {
        "military": [row for row in clusters if row["outcome_kind"] == "campaign"],
        "civil_governance": [
            row
            for row in clusters
            if row["outcome_kind"] == "governance"
            and (row.get("payload") or {}).get("domain") != "culture_scholarship"
        ],
        "statecraft": [row for row in clusters if row["outcome_kind"] == "statecraft"],
    }
    domains = {
        name: _assess_person_talent_grade_single_domain(
            person_ref=person_ref,
            clusters=rows,
        )
        for name, rows in domain_clusters.items()
    }
    domains["culture_and_scholarship"] = _culture_talent_grade(
        person_ref=person_ref,
        clusters=clusters,
    )
    grade_rank = {value: index for index, value in enumerate(TALENT_GRADES)}
    total_eligible = sum(
        int(value["eligible_outcome_count"]) for value in domains.values()
    )
    historic_domains = [
        name for name, value in domains.items() if value["grade"] == "historic"
    ]
    top_domains = [
        name for name, value in domains.items() if value["grade"] == "top"
    ]
    if total_eligible == 0:
        grade = "ordinary"
        primary_domains = []
        rule_path = "coverage_complete_below_usable"
    elif historic_domains:
        grade = "historic"
        primary_domains = historic_domains
        rule_path = str(domains[historic_domains[0]]["rule_path"])
    elif len(top_domains) >= 2:
        grade = "historic"
        primary_domains = top_domains
        rule_path = "all_round_multiple_independent_top_domains"
    else:
        grade = max(
            TALENT_GRADES,
            key=lambda value: (
                any(row["grade"] == value for row in domains.values()),
                grade_rank[value],
            ),
        )
        primary_domains = [
            name for name, value in domains.items() if value["grade"] == grade
        ]
        rule_path = str(domains[primary_domains[0]]["rule_path"])
    counted_domains = (
        top_domains
        if rule_path == "all_round_multiple_independent_top_domains"
        else primary_domains
    )
    outcome_refs = sorted(
        {
            str(ref)
            for name in counted_domains
            for ref in domains[name]["outcome_refs"]
        }
    )
    basis = "；".join(
        f"{name}：{str(domains[name]['basis']).rstrip('。')}"
        for name in counted_domains
    )
    if rule_path == "all_round_multiple_independent_top_domains":
        basis += "；两个领域分别达到top，按明确的全能型路径升为historic"
    return {
        "grade": grade,
        "basis": (basis or "完整覆盖后未建立达到可用门槛的独立成果簇") + "。",
        "policy_ref": "config/talent-grade-v11-domain-equivalent-historic.yml",
        "rule_path": rule_path,
        "outcome_refs": outcome_refs,
        "eligible_outcome_count": total_eligible,
        "primary_domains": primary_domains,
        "domain_grades": {
            name: {
                "grade": value["grade"],
                "basis": value["basis"],
                "rule_path": value["rule_path"],
                "outcome_refs": value["outcome_refs"],
            }
            for name, value in domains.items()
        },
        "status": "accepted_current",
    }


def outcome_registry_report(
    registry: Mapping[str, object],
    *,
    facts: Mapping[str, Mapping[str, object]],
    schema_path: Path,
) -> dict[str, object]:
    validation = validate_historical_outcome_registry(
        registry, schema_path=schema_path, facts=facts
    )
    episodes = [
        asdict(build_outcome_episode(cluster, facts=facts))
        for cluster in registry["clusters"]
    ]
    return {"validation": validation, "episodes": episodes}
