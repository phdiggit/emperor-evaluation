from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping, Sequence
from uuid import uuid4

from opencc import OpenCC
import yaml

from emperor_v4.adapters.source_text_index import LocalSourceTextIndex
from emperor_v4.adapters.structured_output_contract import validate_payload_against_schema
from emperor_v4.evaluation.historical_outcome_cluster import (
    CAMPAIGN_SCALE_BASES,
    GOVERNANCE_SCALE_BASES,
    STRATEGIC_RESULT_TIER,
    cluster_semantic_fingerprint,
)
from emperor_v4.evaluation.historical_outcome_registry import (
    build_ruler_outcome_bindings,
    build_unbound_historical_outcome_registry,
)
from emperor_v4.evaluation.i5b_current_value_runner import build_i5b_current_value


SCHEMA_VERSION = "current-source-pack-increment-v1"
CANDIDATE_SCHEMA_VERSION = "current-outcome-candidate-output-v2"
_T2S = OpenCC("t2s")


def _digest(value: object) -> str:
    return sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _merge_current(
    existing: Sequence[Mapping[str, Any]],
    incoming: Sequence[Mapping[str, Any]],
    *,
    key: str,
) -> list[dict[str, Any]]:
    merged = {str(row[key]): dict(row) for row in existing}
    if len(merged) != len(existing):
        raise ValueError(f"current source pack {key} 重复")
    for row in incoming:
        identity = str(row.get(key) or "")
        if not identity:
            raise ValueError(f"increment 缺少 {key}")
        previous = merged.get(identity)
        if previous is not None and previous != row:
            raise ValueError(f"increment 与当前 {key} 冲突: {identity}")
        merged[identity] = dict(row)
    return [merged[value] for value in sorted(merged)]


def compile_source_pack_increment(
    source_pack: Mapping[str, Any],
    increment: Mapping[str, Any],
    *,
    replace_auto: bool = False,
) -> dict[str, Any]:
    if increment.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("source-pack increment schema_version 不匹配")
    if increment.get("ruler") != source_pack.get("ruler"):
        raise ValueError("source-pack increment 皇帝不匹配")
    allowed = {"schema_version", "ruler", "facts", "outcomes"}
    if set(increment) != allowed:
        raise ValueError("source-pack increment 字段不闭合")
    compiled = json.loads(json.dumps(source_pack, ensure_ascii=False))
    if replace_auto:
        retained_clusters = [
            row
            for row in (compiled.get("outcome_registry") or {}).get("clusters") or ()
            if not str(row.get("outcome_ref") or "").startswith("OUTCOME-AUTO-")
        ]
        retained_fact_refs = {
            str(fact_ref)
            for cluster in retained_clusters
            for fact_ref in cluster.get("fact_refs") or ()
        }
        compiled["facts"] = [
            row
            for row in compiled.get("facts") or ()
            if not str(row.get("record_ref") or "").startswith("PFACT-AUTO-")
            or str(row.get("record_ref") or "") in retained_fact_refs
        ]
        compiled["outcome_registry"]["clusters"] = retained_clusters
    compiled["facts"] = _merge_current(
        compiled.get("facts") or (), increment.get("facts") or (), key="record_ref"
    )
    clusters = _merge_current(
        (compiled.get("outcome_registry") or {}).get("clusters") or (),
        increment.get("outcomes") or (),
        key="outcome_ref",
    )
    for cluster in clusters:
        cluster["episode_refs"] = [
            "EP-OUTCOME-"
            + _digest(
                {
                    "kind": cluster["outcome_kind"],
                    "independent_key": cluster["independent_key"],
                }
            )[:20].upper()
        ]
        cluster["semantic_fingerprint"] = cluster_semantic_fingerprint(cluster)
    compiled["outcome_registry"]["clusters"] = clusters
    dispositions = compiled.get("three_channel_disposition") or {}
    dynasty_governance = dispositions.get("dynasty_governance") or {}
    dynasty_governance["ruler_window_achievement_count"] = sum(
        row["origin"] == "dynasty_governance"
        and row["outcome_kind"] == "governance"
        for row in clusters
    )
    dispositions["dynasty_governance"] = dynasty_governance
    compiled["three_channel_disposition"] = dispositions
    if increment.get("facts") or increment.get("outcomes"):
        gate = dict(compiled.get("profile_projection_gate") or {})
        gate.update(
            {
                "status": "material_coverage_open",
                "material_coverage_complete": False,
                "freeze_allowed": False,
            }
        )
        compiled["profile_projection_gate"] = gate
    compiled.pop("source_pack_sha256", None)
    compiled["source_pack_sha256"] = _digest(compiled)
    return compiled


def compile_outcome_candidate_payloads(
    source_pack: Mapping[str, Any],
    payloads: Sequence[Mapping[str, Any]],
    *,
    source_index: LocalSourceTextIndex,
    schema_path: Path,
) -> dict[str, Any]:
    """Turn schema-bound model drafts into a deterministic source-pack increment."""

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    actor_refs = {
        str(source_pack["ruler"]): (str(source_pack["ruler_ref"]), "ruler"),
        **{
            str(row["person"]): (str(row["person_ref"]), "person")
            for row in source_pack.get("members") or ()
        },
    }
    actor_names_by_simplified = {
        _T2S.convert(name): name for name in actor_refs
    }
    dynasty_or_regime = next(
        (
            str(row["dynasty_or_regime"])
            for row in source_pack.get("facts") or ()
            if row.get("dynasty_or_regime")
        ),
        str(source_pack["ruler"]),
    )
    candidate_pages = {
        str(candidate["source_page"])
        for payload in payloads
        for candidate in payload.get("candidates") or ()
    }
    works = sorted({page.split("/", 1)[0] for page in candidate_pages})
    pages_by_title = {
        page.page_title: page for page in source_index.iter_pages(works=works)
    }
    facts: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    candidate_keys: set[str] = set()
    campaign_roles = {
        "commander_in_chief", "principal_commander", "participant",
        "not_in_command_chain",
    }
    governance_roles = {"exclusive", "lead", "governance_participant", "authorized", "reign_holder"}
    for payload in payloads:
        validate_payload_against_schema(payload, schema)
        if payload.get("schema_version") != CANDIDATE_SCHEMA_VERSION:
            raise ValueError("outcome candidate schema_version 不匹配")
        for candidate in payload.get("candidates") or ():
            candidate_key = str(candidate["candidate_key"])
            if candidate_key in candidate_keys:
                raise ValueError(f"outcome candidate_key 重复: {candidate_key}")
            candidate_keys.add(candidate_key)
            settlement_scope = str(candidate["settlement_scope"])
            if candidate["outcome_kind"] == "campaign" and settlement_scope not in {
                "war_terminal_context",
                "ruler_campaign_parent",
                "person_campaign_subresult",
            }:
                raise ValueError(f"{candidate_key} 战役结算范围不正确")
            if candidate["outcome_kind"] == "governance" and settlement_scope not in {
                "governance_result",
                "person_governance_result",
                "reign_macro_outcome",
            }:
                raise ValueError(f"{candidate_key} 治理结算范围不正确")
            if (
                candidate["outcome_kind"] == "statecraft"
                and settlement_scope != "person_statecraft_result"
            ):
                raise ValueError(f"{candidate_key} 谋略成果只能进入人物画像结算")
            if settlement_scope == "person_campaign_subresult" and not candidate.get(
                "parent_outcome_ref"
            ):
                raise ValueError(f"{candidate_key} 人物子战役缺少父级战役群")
            if (
                settlement_scope == "person_governance_result"
                and candidate["ruler_window_status"] != "outside_window"
            ):
                raise ValueError(
                    f"{candidate_key} 人物生涯治理成果必须位于当前皇帝窗口之外"
                )
            page = pages_by_title.get(str(candidate["source_page"]))
            if page is None or page.revision_ref != candidate["revision_ref"]:
                raise ValueError(f"{candidate_key} 史源页或 revision 不匹配")
            quotes = list(
                dict.fromkeys(str(value) for value in candidate["exact_quotes"])
            )
            if candidate["outcome_kind"] == "campaign":
                for field in (
                    "operational_costs",
                    "objective_shortfalls",
                    "attributable_failures",
                ):
                    for item in candidate["payload"].get(field) or ():
                        quotes.extend(
                            str(value) for value in item.get("exact_quotes") or ()
                        )
                quotes = list(dict.fromkeys(quotes))
            if any(quote not in page.raw_text for quote in quotes):
                raise ValueError(f"{candidate_key} exact_quote 无法逐字回指")
            members = []
            member_names = set()
            candidate_limitations = list(candidate["limitations"])
            if candidate["outcome_kind"] == "campaign":
                missing_campaign_axes = [
                    key
                    for key in (
                        "campaign_tier",
                        "campaign_tier_basis",
                        "land_strategic_value",
                        "strategic_result_class",
                        "combat_difficulty",
                        "combat_difficulty_basis",
                        "operational_costs",
                        "objective_shortfalls",
                        "attributable_failures",
                    )
                    if candidate["payload"].get(key) is None
                ]
                if missing_campaign_axes:
                    raise ValueError(
                        f"{candidate_key} 战役登记缺少等级、土地轴或成本责任分轴: "
                        + ", ".join(missing_campaign_axes)
                    )
                tier_basis = str(candidate["payload"]["campaign_tier_basis"])
                required_axis_values = (
                    f"土地轴={candidate['payload']['land_strategic_value']}",
                    f"对手轴={candidate['payload']['opponent_strategic_weight']}/{candidate['payload']['opponent_condition']}",
                    f"结果轴={candidate['payload']['battle_result']}/{candidate['payload']['objective_completion']}",
                )
                if not all(token in tier_basis for token in required_axis_values):
                    raise ValueError(
                        f"{candidate_key} 战役定级依据与土地、对手或结果字段不一致"
                    )
                strategic_result_class = str(
                    candidate["payload"]["strategic_result_class"]
                )
                expected_tier = STRATEGIC_RESULT_TIER[strategic_result_class]
                if candidate["payload"]["campaign_tier"] != expected_tier:
                    raise ValueError(
                        f"{candidate_key} 战略结果类 {strategic_result_class} 必须映射为 {expected_tier}"
                    )
                if expected_tier == "S+" and (
                    candidate["payload"]["battle_result"] != "victory"
                    or candidate["payload"]["objective_completion"] != "complete"
                ):
                    raise ValueError(
                        f"{candidate_key} S+ 必须实际取得胜利并完成终局目标"
                    )
                required_opponent_weight = {
                    "composite_poles_terminal": {"first_tier_pole", "dominant_pole"},
                    "unification_terminal": {"dominant_pole"},
                    "external_hegemony_terminal": {"external_hegemony"},
                }.get(strategic_result_class)
                if required_opponent_weight and candidate["payload"][
                    "opponent_strategic_weight"
                ] not in required_opponent_weight:
                    raise ValueError(
                        f"{candidate_key} S+ 战略终局与对手竞争位置不匹配"
                    )
                for failure in candidate["payload"]["attributable_failures"]:
                    if not failure.get("actor_name"):
                        raise ValueError(f"{candidate_key} 可归责失败缺少责任人")
            else:
                missing_governance_fields = [
                    key
                    for key in (
                        "domain",
                        "foundational",
                        "durable_cross_stage",
                        "authorization_status",
                        "causal_attribution_status",
                    )
                    if candidate["payload"].get(key) is None
                ]
                if missing_governance_fields:
                    raise ValueError(
                        f"{candidate_key} 治理或谋略登记缺少类型或实施状态: "
                        + ", ".join(missing_governance_fields)
                    )
            scale_bases = (
                CAMPAIGN_SCALE_BASES
                if candidate["outcome_kind"] == "campaign"
                else GOVERNANCE_SCALE_BASES
            )
            scale_order = ["local", "important", "regional", "national", "era_shaping"]
            declared_level = str(candidate["scale_level"])
            declared_basis = str(candidate["scale_basis"])
            implied_level = next(
                (
                    level
                    for level, bases in scale_bases.items()
                    if declared_basis in bases
                ),
                None,
            )
            if implied_level is None:
                candidate["scale_basis"] = sorted(scale_bases[declared_level])[0]
                candidate_limitations.append(
                    "模型影响依据不属于当前成果类型，已按声明档位保守归一。"
                )
            elif declared_basis not in scale_bases[declared_level]:
                if scale_order.index(implied_level) < scale_order.index(declared_level):
                    candidate["scale_level"] = implied_level
                else:
                    candidate["scale_basis"] = sorted(scale_bases[declared_level])[0]
                candidate_limitations.append(
                    "模型规模档位与影响依据不兼容，已按两者下界保守归一。"
                )
            if (
                candidate["outcome_kind"] == "campaign"
                and candidate["scale_level"] in {"national", "era_shaping"}
                and candidate["payload"]["opponent_condition"] == "residual"
            ):
                candidate["scale_level"] = "regional"
                candidate["scale_basis"] = "regional_theater_control"
                candidate_limitations.append(
                    "对手仅属残余势力，未按灭国名义登记为国家级。"
                )
            for raw_member in candidate["members"]:
                raw_name = str(raw_member["actor_name"])
                name = actor_names_by_simplified.get(_T2S.convert(raw_name), raw_name)
                if name in member_names:
                    raise ValueError(f"{candidate_key} 参与者重复: {name}")
                member_names.add(name)
                binding = actor_refs.get(name)
                if binding is None or binding[1] != raw_member["actor_kind"]:
                    raise ValueError(f"{candidate_key} 参与者不属于当前皇帝或团队: {name}")
                authorization_quotes = list(
                    dict.fromkeys(
                        str(value) for value in raw_member["authorization_quotes"]
                    )
                )
                if any(quote not in page.raw_text for quote in authorization_quotes):
                    raise ValueError(f"{candidate_key}/{name} 授权引文无法回指")
                member = {
                    "actor_ref": binding[0],
                    "actor_name": name,
                    "actor_kind": binding[1],
                    "role_code": raw_member["role_code"],
                    "contribution_scope": raw_member["contribution_scope"],
                }
                if candidate["outcome_kind"] == "campaign":
                    talent_credit = raw_member.get("talent_credit")
                    if not talent_credit:
                        raise ValueError(
                            f"{candidate_key}/{name} 战役成员缺少人才独立信用声明"
                        )
                    member["talent_credit"] = talent_credit
                    member["sovereign_at_event"] = bool(
                        raw_member.get("sovereign_at_event")
                    )
                ruler_campaign_relation = raw_member.get("ruler_campaign_relation")
                if (
                    candidate["outcome_kind"] == "campaign"
                    and raw_member.get("sovereign_at_event") is True
                    and ruler_campaign_relation is None
                ):
                    raise ValueError(
                        f"{candidate_key}/{name} 事件实际统治者必须登记唯一控制方式"
                    )
                if ruler_campaign_relation is not None:
                    if (
                        candidate["outcome_kind"] != "campaign"
                        or raw_member.get("sovereign_at_event") is not True
                    ):
                        raise ValueError(
                            f"{candidate_key}/{name} 只有事件实际统治者可以登记控制方式"
                        )
                    member["ruler_campaign_relation"] = ruler_campaign_relation
                for field in (
                    "authorization_mode",
                    "control_extent",
                    "obstruction_status",
                ):
                    if raw_member.get(field) is not None:
                        member[field] = raw_member[field]
                if (
                    raw_member["role_code"] == "not_in_command_chain"
                    and raw_member.get("sovereign_at_event") is not True
                ):
                    raise ValueError(
                        f"{candidate_key}/{name} not_in_command_chain 仅用于事件实际统治者"
                    )
                allowed_roles = (
                    campaign_roles
                    if candidate["outcome_kind"] == "campaign"
                    else governance_roles
                )
                if member["role_code"] not in allowed_roles:
                    raise ValueError(
                        f"{candidate_key}/{name} 角色不属于 {candidate['outcome_kind']} 合同"
                    )
                if raw_member["responsibility_scope"] != "not_applicable":
                    if not authorization_quotes:
                        candidate_limitations.append(
                            f"{name}未提供逐字授权引文，责任范围未登记。"
                        )
                    else:
                        member["delegated_responsibility"] = {
                            "scope": raw_member["responsibility_scope"],
                            "basis": raw_member["contribution_scope"],
                            "authorization_refs": [
                                f"{page.page_title}@{page.revision_ref}#{quote[:32]}"
                                for quote in authorization_quotes
                            ],
                        }
                members.append(member)
            if candidate["outcome_kind"] == "campaign":
                sovereign_members = [
                    member
                    for member in members
                    if member.get("sovereign_at_event") is True
                ]
                if len(sovereign_members) > 1:
                    raise ValueError(f"{candidate_key} 战役不能登记多个事件实际统治者")
                if sovereign_members:
                    sovereign_member = sovereign_members[0]
                    relation = str(sovereign_member["ruler_campaign_relation"])
                    if relation == "authorization_only" and (
                        sovereign_member["role_code"] != "not_in_command_chain"
                    ):
                        raise ValueError(
                            f"{candidate_key} 仅授权的统治者必须标为 not_in_command_chain"
                        )
                    if relation != "authorization_only" and (
                        sovereign_member["role_code"] == "not_in_command_chain"
                    ):
                        raise ValueError(
                            f"{candidate_key} 进入战区统筹的统治者必须登记实际指挥角色"
                        )
                if (
                    candidate["settlement_scope"] != "war_terminal_context"
                    and not any(
                    member["role_code"]
                    in {"commander_in_chief", "principal_commander", "participant"}
                    for member in members
                    )
                ):
                    raise ValueError(f"{candidate_key} 父级战役群缺少实际军事指挥链成员")
            else:
                substantive_members = [
                    member
                    for member in members
                    if member["role_code"]
                    in {"exclusive", "lead", "governance_participant"}
                ]
                if (
                    candidate["settlement_scope"] != "reign_macro_outcome"
                    and not substantive_members
                ):
                    raise ValueError(f"{candidate_key} 治理或谋略成果不能只有授权者")
                exclusive_members = [
                    member for member in members if member["role_code"] == "exclusive"
                ]
                if exclusive_members and len(substantive_members) != 1:
                    raise ValueError(
                        f"{candidate_key} exclusive 不能与其他实施责任角色并列"
                    )
                if candidate["settlement_scope"] == "reign_macro_outcome":
                    causal_status = candidate["payload"]["causal_attribution_status"]
                    if causal_status == "source_attributed":
                        if not any(
                            member["actor_kind"] == "ruler"
                            and member["role_code"] in {"exclusive", "lead"}
                            for member in members
                        ):
                            raise ValueError(
                                f"{candidate_key} 史源归因宏观结果缺少总体治理主导者"
                            )
                    elif causal_status == "limited":
                        if not any(
                            member["actor_kind"] == "ruler"
                            and member["role_code"] == "reign_holder"
                            for member in members
                        ):
                            raise ValueError(
                                f"{candidate_key} 因果有限宏观结果缺少统治窗口归属"
                            )
                    else:
                        raise ValueError(f"{candidate_key} 宏观结果因果归责状态不正确")
            fact_ref = "PFACT-AUTO-" + _digest(
                {"candidate_key": candidate_key, "quotes": quotes}
            )[:20].upper()
            primary_person = next(
                (member for member in members if member["actor_kind"] == "person"),
                (
                    members[0]
                    if members
                    else {
                        "actor_ref": source_pack["ruler_ref"],
                        "actor_name": source_pack["ruler"],
                    }
                ),
            )
            assertions = [
                {
                    "assertion_ref": "PASS-AUTO-"
                    + _digest({"candidate_key": candidate_key, "quote": quote})[:20].upper(),
                    "exact_quote": quote,
                    "fact": candidate["neutral_summary"],
                    "kind": "outcome",
                    "locator_anchor": quote[:32],
                }
                for quote in quotes
            ]
            facts.append(
                {
                    "record_ref": fact_ref,
                    "record_type": "event",
                    "person_ref": primary_person["actor_ref"],
                    "canonical_name": primary_person["actor_name"],
                    "person_scan_key": "PSCAN-AUTO-" + _digest(candidate_key)[:16].upper(),
                    "source_page": page.page_title,
                    "revision_ref": page.revision_ref,
                    "date": candidate["period_start"],
                    "dynasty_or_regime": dynasty_or_regime,
                    "ruler_contexts": (
                        [source_pack["ruler"]]
                        if candidate["ruler_window_status"]
                        in {"within_window", "leadership_formation"}
                        else []
                    ),
                    "subject_role": "；".join(
                        str(member["role_code"]) for member in members
                    ),
                    "neutral_summary": candidate["neutral_summary"],
                    "assertions": assertions,
                }
            )
            raw_payload = dict(candidate["payload"])
            if candidate["outcome_kind"] == "campaign":
                outcome_payload = {
                    key: raw_payload[key]
                    for key in (
                        "theater",
                        "strategic_objective",
                        "battle_result",
                        "objective_completion",
                    "opponent_condition",
                    "opponent_strategic_weight",
                    "strategic_result_class",
                )
                }
                for key in (
                    "campaign_tier",
                    "campaign_tier_basis",
                    "land_strategic_value",
                    "combat_difficulty",
                    "combat_difficulty_basis",
                ):
                    if raw_payload.get(key) is not None:
                        outcome_payload[key] = raw_payload[key]
                for field in ("operational_costs", "objective_shortfalls"):
                    outcome_payload[field] = [
                        {
                            "basis": item["basis"],
                            "source_refs": [
                                f"{page.page_title}@{page.revision_ref}#{quote[:32]}"
                                for quote in dict.fromkeys(item["exact_quotes"])
                            ],
                        }
                        for item in raw_payload.get(field) or ()
                    ]
                outcome_payload["attributable_failures"] = []
                for raw_failure in raw_payload.get("attributable_failures") or ():
                    actor_name = actor_names_by_simplified.get(
                        _T2S.convert(str(raw_failure["actor_name"])),
                        str(raw_failure["actor_name"]),
                    )
                    binding = actor_refs.get(actor_name)
                    if binding is None:
                        raise ValueError(
                            f"{candidate_key} 可归责失败责任人不在允许人物中: {actor_name}"
                        )
                    outcome_payload["attributable_failures"].append(
                        {
                            "responsibility": raw_failure["responsibility"],
                            "severity_index": raw_failure["severity_index"],
                            "actor_ref": binding[0],
                            "actor_name": actor_name,
                            "basis": raw_failure["basis"],
                            "source_refs": [
                                f"{page.page_title}@{page.revision_ref}#{quote[:32]}"
                                for quote in dict.fromkeys(
                                    raw_failure["exact_quotes"]
                                )
                            ],
                        }
                    )
            else:
                outcome_payload = {
                    key: raw_payload[key]
                    for key in (
                        "domain",
                        "foundational",
                        "durable_cross_stage",
                        "authorization_status",
                        "causal_attribution_status",
                    )
                }
            outcome_ref = "OUTCOME-AUTO-" + _digest(candidate_key)[:20].upper()
            outcomes.append(
                {
                    "outcome_ref": outcome_ref,
                    "outcome_kind": candidate["outcome_kind"],
                    "settlement_scope": candidate["settlement_scope"],
                    **(
                        {"parent_outcome_ref": candidate["parent_outcome_ref"]}
                        if candidate.get("parent_outcome_ref")
                        else {}
                    ),
                    "independent_key": candidate_key,
                    "canonical_label": candidate["canonical_label"],
                    "origin": candidate["origin"],
                    "period": {
                        "start": candidate["period_start"],
                        "end": candidate["period_end"],
                    },
                    "result_status": candidate["result_status"],
                    "result_direction": candidate["result_direction"],
                    "observable_result": candidate["observable_result"],
                    "scale": {
                        "level": candidate["scale_level"],
                        "consequence_basis": candidate["scale_basis"],
                        "decisiveness": candidate["decisiveness"],
                        "reason": candidate["scale_reason"],
                    },
                    "stable_delivery": candidate["stable_delivery"],
                    "important_method_or_legacy": candidate[
                        "important_method_or_legacy"
                    ],
                    "episode_refs": ["EP-OUTCOME-PLACEHOLDER"],
                    "ruler_context_refs": [],
                    "ruler_window_status": candidate["ruler_window_status"],
                    "fact_refs": [fact_ref],
                    "source_refs": [
                        f"{page.page_title}@{page.revision_ref}#{quote[:32]}"
                        for quote in quotes
                    ],
                    "members": members,
                    "limitations": list(dict.fromkeys(candidate_limitations)),
                    "payload": outcome_payload,
                    "semantic_fingerprint": "placeholder",
                }
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "ruler": source_pack["ruler"],
        "facts": facts,
        "outcomes": outcomes,
    }


def apply_source_pack_increment(
    source_pack_path: Path,
    increment: Mapping[str, Any],
    *,
    workspace_root: Path,
    replace_auto: bool = False,
    require_current_projection_ready: bool = True,
) -> bool:
    source_pack_path = source_pack_path.resolve()
    current = json.loads(source_pack_path.read_text(encoding="utf-8"))
    compiled = compile_source_pack_increment(
        current, increment, replace_auto=replace_auto
    )
    rendered = json.dumps(compiled, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if source_pack_path.read_text(encoding="utf-8") == rendered:
        return False
    with tempfile.TemporaryDirectory(prefix="emperor-source-pack-") as temporary:
        candidate = Path(temporary) / "source-pack.json"
        candidate.write_text(rendered, encoding="utf-8", newline="\n")
        project = yaml.safe_load(
            (workspace_root / "config/project.yml").read_text(encoding="utf-8")
        )
        configured = (project.get("i5b_current_value") or {}).get("rulers") or {}
        source_packs = []
        compiled_ruler = str(compiled["ruler"])
        if compiled_ruler not in configured:
            raise ValueError(f"current source pack 皇帝未配置: {compiled_ruler}")
        for ruler_name, ruler_config in configured.items():
            configured_path = (
                workspace_root / str(ruler_config["source_pack"])
            ).resolve()
            source_packs.append(
                compiled
                if str(ruler_name) == compiled_ruler
                else json.loads(configured_path.read_text(encoding="utf-8"))
            )
        registry = build_unbound_historical_outcome_registry(source_packs)
        binding = build_ruler_outcome_bindings(compiled, registry)
        if require_current_projection_ready:
            build_i5b_current_value(
                candidate,
                workspace_root=workspace_root,
                outcome_layers=(registry, binding),
            )
    replacement = source_pack_path.with_name(f".{source_pack_path.name}.{uuid4().hex}.tmp")
    replacement.write_text(rendered, encoding="utf-8", newline="\n")
    os.replace(replacement, source_pack_path)
    return True
