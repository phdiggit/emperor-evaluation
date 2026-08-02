from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "battle-outcome-worklist-v4"
_UNKNOWN_MARKERS = ("未知", "未见", "不详")
_DISPOSITION_ORDER = {
    "UNIFICATION_DEEP_REVIEW": 0,
    "AUTO_REGISTER": 1,
    "BATCH_REVIEW": 2,
    "HOLD_OR_REJECT": 3,
}
_STATECRAFT_PATTERN = re.compile(
    r"定策|献[^，。；]{0,16}计|用[^，。；]{0,16}计|奇计|反间|离间|"
    r"诈(?:降|败|称|为)|佯(?:退|败|攻|走|出|降)|诱(?:敌|降|出|深入|兵)|"
    r"谋划|密谋(?!反)|说[^，。；]{0,24}(?:从|纳)|劝[^，。；]{0,24}(?:从|纳)"
)


def _digest(value: object) -> str:
    return sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _known(value: object) -> bool:
    text = str(value or "").strip()
    return bool(text) and not any(marker in text for marker in _UNKNOWN_MARKERS)


def _iter_text(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for key, nested in value.items():
            yield str(key)
            yield from _iter_text(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _iter_text(nested)


def _statecraft_leads(rows: list[Mapping[str, Any]]) -> list[str]:
    leads: list[str] = []
    for row in rows:
        for text in _iter_text(row.get("source_fact_fields") or {}):
            normalized = " ".join(text.split())
            if _STATECRAFT_PATTERN.search(normalized) and normalized not in leads:
                leads.append(normalized)
    return leads[:8]


def _unique(rows: Iterable[object]) -> list[str]:
    return sorted({str(value) for value in rows if value not in (None, "")})


_COMMAND_TOPOLOGIES = {
    "single_integrated_command",
    "joint_integrated_command",
    "federated_directions",
    "opposed_commands",
    "distributed_response",
    "command_unresolved",
    "sequential_successor_command",
}
_MILITARY_CAPABILITY_MODES = {
    "integrated_command",
    "independent_direction",
    "operational_design",
    "tactical_execution",
    "authorization_only",
    "nominal_only",
    "unresolved",
}
_DECISIVE_RELATIONS = {
    "decisive_creator",
    "decisive_successor",
    "co_decisive",
    "terminal_finisher",
    "stage_executor",
    "none",
    "unresolved",
}


def _validate_campaign_command_topology(
    path: Path,
    campaign_ref: str,
    topology: object,
    members: Sequence[Mapping[str, Any]],
) -> None:
    topology = str(topology or "")
    if topology not in _COMMAND_TOPOLOGIES:
        raise ValueError(f"{path} 战役群指挥拓扑非法: {campaign_ref}/{topology}")
    commanders = [member for member in members if member.get("role_code") == "commander_in_chief"]
    principals = [member for member in members if member.get("role_code") == "principal_commander"]
    modes = [str((member.get("person_command_index") or {}).get("consumption_mode") or "") for member in members]
    if topology == "single_integrated_command" and len(commanders) != 1:
        raise ValueError(f"{path} 单一统合指挥必须且只能有一个实质主帅: {campaign_ref}")
    if topology == "joint_integrated_command":
        if len(commanders) < 2:
            raise ValueError(f"{path} 共同统合指挥至少需要两名共同主帅: {campaign_ref}")
        if any(
            (member.get("person_command_index") or {}).get("consumption_mode")
            not in {"joint_parent", "person_result"}
            for member in commanders
        ):
            raise ValueError(
                f"{path} 共同主帅必须保留共同父级或显式人物成果: {campaign_ref}"
            )
    if topology == "federated_directions":
        if len(principals) < 2 or any(
            (member.get("person_command_index") or {}).get("consumption_mode") != "none"
            for member in commanders
        ):
            raise ValueError(
                f"{path} 分立方面指挥至少需要两名方面主将；名义总节度不得消费父成果: {campaign_ref}"
            )
    if topology == "opposed_commands":
        command_sides = {
            str(member.get("command_side") or "")
            for member in commanders
            if member.get("command_side")
        }
        if len(commanders) < 2 or len(command_sides) < 2:
            raise ValueError(f"{path} 敌对指挥链至少需要两名分属不同阵营的实质主帅: {campaign_ref}")
        if any(
            member.get("command_result_direction")
            not in {"positive", "mixed_review", "negative", "unclear"}
            for member in commanders
        ):
            raise ValueError(f"{path} 敌对主帅必须保存本人结果方向: {campaign_ref}")
    if topology in {"distributed_response", "command_unresolved"} and commanders:
        raise ValueError(f"{path} 当前指挥拓扑不得补造父级主帅: {campaign_ref}")
    if topology == "sequential_successor_command":
        predecessors = [
            member
            for member in principals
            if (member.get("person_command_index") or {}).get("result_direction")
            in {"negative", "mixed_review"}
        ]
        if (
            len(commanders) != 1
            or (commanders[0].get("person_command_index") or {}).get("consumption_mode")
            != "full_parent"
            or not predecessors
        ):
            raise ValueError(
                f"{path} 顺序接任指挥必须有一名后任完整消费且至少一名前任保留负面事实: {campaign_ref}"
            )
    if topology not in {"single_integrated_command", "sequential_successor_command"} and "full_parent" in modes:
        if topology != "opposed_commands" or modes.count("full_parent") != 1:
            raise ValueError(f"{path} 非单一统合指挥不得完整消费父成果: {campaign_ref}")


def _validate_person_command_projection(
    path: Path,
    campaign_ref: str,
    command_index: Mapping[str, Any],
) -> None:
    mode = command_index.get("consumption_mode")
    projected_tier = command_index.get("projected_result_tier")
    projected_difficulty = command_index.get("projected_combat_difficulty")
    if mode == "scoped_projection" and (
        projected_tier not in {"C", "B", "A"}
        or projected_difficulty not in {"D0", "D1", "D2"}
    ):
        raise ValueError(
            f"{path} 轻量方向投影不得绕过人物子成果门禁: {campaign_ref}"
        )
    if mode == "person_result_required" and (
        projected_tier is not None or projected_difficulty is not None
    ):
        raise ValueError(
            f"{path} 待建人物子成果不得预填高档投影: {campaign_ref}"
        )
    if mode == "operational_result" and (
        projected_tier not in {"C", "B", "A", "S-", "S", "S+"}
        or projected_difficulty is not None
    ):
        raise ValueError(
            f"{path} 战略指导只能消费结果档且不得继承前线难度: {campaign_ref}"
        )


def load_battle_ledger_rows(ledger_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(ledger_root.rglob("战役底账.jsonl")):
        dynasty = path.parent.name
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            row = json.loads(line)
            if not row.get("war_event_id"):
                raise ValueError(f"{path}:{line_number} 缺少 war_event_id")
            rows.append(
                {
                    **row,
                    "_dynasty": dynasty,
                    "_ledger_path": path.as_posix(),
                    "_line_number": line_number,
                }
            )
    return rows


def load_military_settlements(path: Path) -> dict[str, dict[str, Any]]:
    settlements: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return settlements
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        row = json.loads(line)
        war_event_id = str(row.get("war_event_id") or "")
        if not war_event_id:
            raise ValueError(f"{path}:{line_number} 缺少 war_event_id")
        if war_event_id in settlements:
            raise ValueError(f"{path}:{line_number} 重复 war_event_id: {war_event_id}")
        settlements[war_event_id] = row
    return settlements


def load_unification_scope_adjudications(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "unification-campaign-scope-adjudications-v1":
        raise ValueError(f"{path} schema_version 不受支持")
    indexed: dict[str, dict[str, Any]] = {}
    allowed_kinds = {
        "FULL_REALM_UNIFICATION",
        "REGIONAL_REGIME_FOUNDATION",
        "REGIONAL_ANNEXATION",
        "NOT_A_UNIFICATION_PORTFOLIO",
    }
    for group in payload.get("adjudications") or []:
        scope_kind = str(group.get("scope_kind") or "")
        if scope_kind not in allowed_kinds:
            raise ValueError(f"{path} 非法 scope_kind: {scope_kind}")
        portfolio_ref = str(group.get("portfolio_ref") or "")
        basis = str(group.get("basis") or "")
        if not portfolio_ref or not basis:
            raise ValueError(f"{path} 分型组缺少 portfolio_ref 或 basis")
        for war_event_ref in group.get("war_event_refs") or []:
            war_event_id = str(war_event_ref)
            if war_event_id in indexed:
                raise ValueError(f"{path} 重复裁决 war_event_id: {war_event_id}")
            indexed[war_event_id] = {
                "status": "ADJUDICATED",
                "scope_kind": scope_kind,
                "portfolio_ref": portfolio_ref,
                "basis": basis,
            }
    return indexed


def load_ordinary_campaign_adjudications(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "ordinary-campaign-adjudications-v2":
        raise ValueError(f"{path} schema_version 不受支持")
    if payload.get("evidence_maturity") != "REGISTERED_NOT_GOLD":
        raise ValueError(f"{path} 普通战役裁决必须明确标记为非Gold登记")
    if payload.get("numeric_weights_frozen") is not False:
        raise ValueError(f"{path} 当前不得冻结普通战役数值权重")
    tier_by_result_class = {
        "local_tactical": "C",
        "important_objective": "B",
        "major_stage_or_crisis": "A",
        "independent_direction": "S-",
        "single_pole_decisive_defeat": "S",
        "external_hegemony_decisive_defeat": "S",
        "single_pole_or_state_terminal": "S",
        "composite_poles_terminal": "S+",
        "unification_terminal": "S+",
        "external_hegemony_terminal": "S+",
    }
    indexed: dict[str, dict[str, Any]] = {}
    for row in payload.get("adjudications") or []:
        war_event_id = str(row.get("war_event_id") or "")
        if not war_event_id or war_event_id in indexed:
            raise ValueError(f"{path} 普通战役 war_event_id 缺失或重复: {war_event_id}")
        status = str(row.get("status") or "")
        if row.get("candidate_disposition") not in {
            "AUTO_REGISTER", "BATCH_REVIEW", "HOLD_OR_REJECT"
        }:
            raise ValueError(f"{path} 普通战役缺少合法候选路由: {war_event_id}")
        if status == "MERGED_INTO_CAMPAIGN_GROUP":
            if (
                row.get("registration_role") != "CAMPAIGN_GROUP_SOURCE_MEMBER"
                or not row.get("merged_into_war_event_ref")
                or not row.get("basis")
            ):
                raise ValueError(f"{path} 战役父子合并裁决结构不完整: {war_event_id}")
            indexed[war_event_id] = dict(row)
            continue
        if status in {
            "REDIRECT_NON_BATTLE_OUTCOME",
            "BELOW_PUBLIC_OUTCOME_THRESHOLD",
            "CAMPAIGN_ADJUDICATION_REQUIRED",
            "HOLD_AGGREGATE_SECURITY_STATE",
            "HOLD_MIXED_EVENT_CHAIN",
            "HOLD_RESULT_UNCLOSED",
            "HOLD_SOURCE_FINALIZATION_REQUIRED",
            "HOLD_SOURCE_BACKFILL_REQUIRED",
        }:
            expected_role = (
                "CAMPAIGN_CANDIDATE"
                if status == "CAMPAIGN_ADJUDICATION_REQUIRED"
                else "NEUTRAL_EVENT_ONLY"
            )
            if row.get("registration_role") != expected_role or not row.get("basis"):
                raise ValueError(f"{path} 非正式成果裁决结构不完整: {war_event_id}")
            indexed[war_event_id] = dict(row)
            continue
        if status != "ADJUDICATED_SOURCE_BACKFILL_REQUIRED":
            raise ValueError(f"{path} 普通战役状态非法: {war_event_id}/{status}")
        if row.get("registration_role") != "CAMPAIGN_GROUP":
            raise ValueError(f"{path} 普通战役登记角色非法: {war_event_id}")
        if row.get("source_backfill_status") != "exact_quote_required":
            raise ValueError(f"{path} 普通战役必须显式保留逐字回源缺口: {war_event_id}")
        source_refs = row.get("source_refs") or []
        members = row.get("members") or []
        battle = row.get("payload") or {}
        topology = str(row.get("campaign_command_topology") or "")
        members_optional = topology in {"distributed_response", "command_unresolved"}
        if not source_refs or (not members and not members_optional) or not row.get("basis"):
            raise ValueError(f"{path} 普通战役缺少史源、必要人物或依据: {war_event_id}")
        result_class = str(battle.get("strategic_result_class") or "")
        if tier_by_result_class.get(result_class) != battle.get("campaign_tier"):
            raise ValueError(f"{path} 普通战役结果类别与档位不一致: {war_event_id}")
        if battle.get("combat_difficulty") not in {"D0", "D1", "D2", "D3", "D4"}:
            raise ValueError(f"{path} 普通战役难度非法: {war_event_id}")
        _validate_campaign_command_topology(
            path,
            war_event_id,
            row.get("campaign_command_topology"),
            members,
        )
        if battle.get("combat_difficulty") == "D4":
            if (
                battle.get("battle_result") != "victory"
                or battle.get("objective_completion") != "complete"
            ):
                raise ValueError(
                    f"{path} D4必须是完成逆转的胜利结果: {war_event_id}"
                )
        ruler_relations = [
            member
            for member in members
            if member.get("sovereign_at_event") is True
            or member.get("ruler_campaign_relation") is not None
        ]
        if topology == "opposed_commands":
            ruler_sides = [str(member.get("command_side") or "") for member in ruler_relations]
            if any(not side for side in ruler_sides) or len(ruler_sides) != len(set(ruler_sides)):
                raise ValueError(f"{path} 敌对指挥链每方最多只能有一个统治者授权关系: {war_event_id}")
        elif len(ruler_relations) > 1:
            raise ValueError(f"{path} 普通战役只能有一个统治者授权关系: {war_event_id}")
        for member in members:
            command_index = member.get("person_command_index") or {}
            required_index_fields = {
                "consumption_mode", "command_scope", "result_direction",
                "projected_result_tier", "projected_combat_difficulty",
                "detail_status", "basis", "source_refs",
            }
            allowed_index_fields = required_index_fields | {
                "capability_mode", "decisive_relation",
            }
            if (
                not required_index_fields.issubset(command_index)
                or not set(command_index).issubset(allowed_index_fields)
                or (
                    ("capability_mode" in command_index)
                    != ("decisive_relation" in command_index)
                )
            ):
                raise ValueError(f"{path} 普通战役人物轻量索引不完整: {war_event_id}")
            if command_index["consumption_mode"] not in {
                "full_parent", "joint_parent", "scoped_projection", "person_result",
                "operational_result",
                "person_result_required", "none",
            }:
                raise ValueError(f"{path} 普通战役人物消费方式非法: {war_event_id}")
            if command_index["command_scope"] not in {
                "full_campaign", "joint_full_campaign", "opposed_full_campaign",
                "independent_direction", "operational_strategy",
                "operational_direction_unresolved",
                "supporting_participation", "limited_person_contribution",
                "no_person_command_credit",
            }:
                raise ValueError(f"{path} 普通战役人物指挥范围非法: {war_event_id}")
            if command_index["result_direction"] not in {
                "positive", "mixed_review", "negative", "unclear", "not_applicable",
            }:
                raise ValueError(f"{path} 普通战役人物结果方向非法: {war_event_id}")
            if command_index["projected_result_tier"] not in {
                None, "C", "B", "A", "S-", "S", "S+",
            } or command_index["projected_combat_difficulty"] not in {
                None, "D0", "D1", "D2", "D3", "D4",
            }:
                raise ValueError(f"{path} 普通战役人物投影非法: {war_event_id}")
            if command_index["detail_status"] not in {
                "not_required", "resolved_person_result", "operational_direction_resolved",
                "person_result_required", "failure_review_required",
            }:
                raise ValueError(f"{path} 普通战役人物补证状态非法: {war_event_id}")
            _validate_person_command_projection(path, war_event_id, command_index)
            if not set(command_index["source_refs"]).issubset(source_refs):
                raise ValueError(f"{path} 普通战役人物索引史源越界: {war_event_id}")
        indexed[war_event_id] = dict(row)
    for war_event_id, row in indexed.items():
        if row.get("status") != "MERGED_INTO_CAMPAIGN_GROUP":
            continue
        parent_ref = str(row["merged_into_war_event_ref"])
        parent = indexed.get(parent_ref) or {}
        if (
            parent.get("status") != "ADJUDICATED_SOURCE_BACKFILL_REQUIRED"
            or war_event_id not in (parent.get("source_war_event_refs") or ())
            or not set(row.get("source_refs") or ()).issubset(
                parent.get("source_refs") or ()
            )
        ):
            raise ValueError(
                f"{path} 普通战役合并子事件血缘未闭合: "
                f"{war_event_id}->{parent_ref}"
            )
    return indexed


def load_unification_tier_adjudications(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "unification-campaign-tier-adjudications-v2":
        raise ValueError(f"{path} schema_version 不受支持")
    if payload.get("evidence_maturity") != "REGISTERED_NOT_GOLD":
        raise ValueError(f"{path} 当前档位裁决必须明确标记为非Gold登记")
    if payload.get("numeric_weights_frozen") is not False:
        raise ValueError(f"{path} 当前不得冻结档位数值权重")
    indexed: dict[str, dict[str, Any]] = {}
    portfolio_refs: set[str] = set()
    campaign_group_ids: set[str] = set()
    for row in payload.get("adjudications") or []:
        portfolio_ref = str(row.get("portfolio_ref") or "")
        if not portfolio_ref or portfolio_ref in portfolio_refs:
            raise ValueError(f"{path} 统一进程ID缺失或重复: {portfolio_ref}")
        portfolio_refs.add(portfolio_ref)
        if row.get("status") != "REGISTERED_NOT_GOLD":
            raise ValueError(f"{path} 统一进程必须标记为非Gold登记: {portfolio_ref}")
        if row.get("registration_role") != "UNIFICATION_CAMPAIGN_PORTFOLIO":
            raise ValueError(f"{path} 统一进程登记角色非法: {portfolio_ref}")
        if not isinstance(row.get("allow_open_portfolio_root"), bool):
            raise ValueError(f"{path} 统一进程缺少未闭合父根开关: {portfolio_ref}")
        if not row.get("basis"):
            raise ValueError(f"{path} 统一进程缺少裁决依据: {portfolio_ref}")
        war_event_refs = [str(ref) for ref in row.get("war_event_refs") or []]
        if not war_event_refs or len(war_event_refs) != len(set(war_event_refs)):
            raise ValueError(f"{path} 统一进程底账事件缺失或重复: {portfolio_ref}")
        groups_by_event: dict[str, list[dict[str, Any]]] = {
            ref: [] for ref in war_event_refs
        }
        for child in row.get("campaign_groups") or []:
            child_id = str(child.get("campaign_group_id") or "")
            if not child_id or child_id in campaign_group_ids:
                raise ValueError(f"{path} 子战役群ID缺失或重复: {portfolio_ref}/{child_id}")
            campaign_group_ids.add(child_id)
            if not child.get("status") or not child.get("registration_role") or not child.get("basis"):
                raise ValueError(f"{path} 子战役群缺少状态、登记角色或依据: {child_id}")
            if any(key in child for key in ("numeric_weight", "score", "weighted_score")):
                raise ValueError(f"{path} 当前不得写入子战役群数值权重或分数: {child_id}")
            if child.get("registration_role") == "CAMPAIGN_GROUP":
                payload = child.get("payload")
                required_payload_fields = {
                    "theater",
                    "strategic_objective",
                    "battle_result",
                    "objective_completion",
                    "opponent_condition",
                    "opponent_strategic_weight",
                    "strategic_result_class",
                    "campaign_tier",
                    "campaign_tier_basis",
                    "land_strategic_value",
                    "strategic_stakes",
                    "prewar_context",
                    "failure_stakes",
                    "combat_difficulty",
                    "combat_difficulty_basis",
                    "operational_costs",
                    "objective_shortfalls",
                    "attributable_failures",
                }
                allowed_payload_fields = required_payload_fields | {
                    "opponent_force_effect"
                }
                if (
                    not isinstance(payload, dict)
                    or not required_payload_fields.issubset(payload)
                    or not set(payload).issubset(allowed_payload_fields)
                ):
                    raise ValueError(f"{path} 正式战役群三轴合同不完整: {child_id}")
                if payload.get("opponent_force_effect") not in {
                    None,
                    "none",
                    "limited_attrition",
                    "major_degradation",
                    "main_force_destroyed",
                    "military_system_collapsed",
                }:
                    raise ValueError(
                        f"{path} 子战役群敌军战力结果轴非法: {child_id}"
                    )
                if payload["campaign_tier"] not in {"C", "B", "A", "S-", "S", "S+"}:
                    raise ValueError(
                        f"{path} 子战役群档位非法: {child_id}/{payload['campaign_tier']}"
                    )
                tier_by_result_class = {
                    "local_tactical": "C",
                    "important_objective": "B",
                    "major_stage_or_crisis": "A",
                    "independent_direction": "S-",
                    "single_pole_decisive_defeat": "S",
                    "external_hegemony_decisive_defeat": "S",
                    "single_pole_or_state_terminal": "S",
                    "composite_poles_terminal": "S+",
                    "unification_terminal": "S+",
                    "external_hegemony_terminal": "S+",
                }
                expected_tier = tier_by_result_class.get(
                    payload["strategic_result_class"]
                )
                if expected_tier != payload["campaign_tier"]:
                    raise ValueError(
                        f"{path} 子战役群结果类别与档位不一致: "
                        f"{child_id}/{payload['strategic_result_class']}="
                        f"{payload['campaign_tier']}，应为{expected_tier}"
                    )
                if payload["battle_result"] not in {
                    "victory",
                    "mixed",
                    "defeat",
                    "unclear",
                }:
                    raise ValueError(
                        f"{path} 子战役群结果方向非法: {child_id}/{payload['battle_result']}"
                    )
                enum_fields = {
                    "objective_completion": {"complete", "partial", "failed", "unclear"},
                    "opponent_condition": {"strong", "viable", "weakened", "residual", "unclear"},
                    "opponent_strategic_weight": {"minor", "regional_major", "first_tier_pole", "dominant_pole", "external_state", "external_hegemony", "unclear"},
                    "strategic_result_class": {"local_tactical", "important_objective", "major_stage_or_crisis", "independent_direction", "single_pole_decisive_defeat", "external_hegemony_decisive_defeat", "single_pole_or_state_terminal", "composite_poles_terminal", "unification_terminal", "external_hegemony_terminal"},
                    "land_strategic_value": {"local_point", "important_region", "strategic_gateway", "core_heartland", "capital_or_state_survival"},
                    "strategic_stakes": {"bounded", "major", "critical", "existential"},
                    "combat_difficulty": {"D0", "D1", "D2", "D3", "D4"},
                }
                for field, allowed in enum_fields.items():
                    if payload[field] not in allowed:
                        raise ValueError(
                            f"{path} 子战役群字段非法: {child_id}/{field}={payload[field]}"
                        )
                if not isinstance(child.get("members"), list) or not child["members"]:
                    raise ValueError(f"{path} 正式战役群缺少人物角色: {child_id}")
                for campaign_member in child["members"]:
                    if not {
                        "actor_ref",
                        "actor_name",
                        "actor_kind",
                        "role_code",
                        "contribution_scope",
                    }.issubset(campaign_member):
                        raise ValueError(f"{path} 正式战役群人物角色不完整: {child_id}")
                    command_index = campaign_member.get("person_command_index")
                    required_command_index_fields = {
                        "consumption_mode",
                        "command_scope",
                        "result_direction",
                        "projected_result_tier",
                        "projected_combat_difficulty",
                        "detail_status",
                        "basis",
                        "source_refs",
                    }
                    allowed_command_index_fields = required_command_index_fields | {
                        "capability_mode",
                        "decisive_relation",
                    }
                    if (
                        not isinstance(command_index, dict)
                        or not required_command_index_fields.issubset(command_index)
                        or not set(command_index).issubset(allowed_command_index_fields)
                        or (
                            ("capability_mode" in command_index)
                            != ("decisive_relation" in command_index)
                        )
                    ):
                        raise ValueError(f"{path} 人物轻量指挥索引不完整: {child_id}")
                    if command_index["consumption_mode"] not in {
                        "full_parent",
                        "joint_parent",
                        "scoped_projection",
                        "person_result",
                        "operational_result",
                        "person_result_required",
                        "none",
                    }:
                        raise ValueError(f"{path} 人物消费方式非法: {child_id}")
                    if command_index["command_scope"] not in {
                        "full_campaign",
                        "joint_full_campaign",
                        "opposed_full_campaign",
                        "independent_direction",
                        "operational_strategy",
                        "operational_direction_unresolved",
                            "supporting_participation",
                            "limited_person_contribution",
                            "no_person_command_credit",
                    }:
                        raise ValueError(f"{path} 人物指挥范围非法: {child_id}")
                    if command_index["result_direction"] not in {
                        "positive",
                        "mixed_review",
                        "negative",
                        "unclear",
                        "not_applicable",
                    }:
                        raise ValueError(f"{path} 人物结果方向非法: {child_id}")
                    if command_index["projected_result_tier"] not in {
                        None,
                        "C",
                        "B",
                        "A",
                        "S-",
                        "S",
                        "S+",
                    }:
                        raise ValueError(f"{path} 人物成果投影非法: {child_id}")
                    if command_index["projected_combat_difficulty"] not in {
                        None,
                        "D0",
                        "D1",
                        "D2",
                        "D3",
                        "D4",
                    }:
                        raise ValueError(f"{path} 人物难度投影非法: {child_id}")
                    if command_index["detail_status"] not in {
                        "not_required",
                        "resolved_person_result",
                        "operational_direction_resolved",
                        "person_result_required",
                        "failure_review_required",
                    }:
                        raise ValueError(f"{path} 人物补证状态非法: {child_id}")
                    _validate_person_command_projection(path, child_id, command_index)
                    if command_index["consumption_mode"] == "full_parent" and (
                        command_index["projected_result_tier"]
                        != payload["campaign_tier"]
                        or command_index["projected_combat_difficulty"]
                        != payload["combat_difficulty"]
                    ):
                        raise ValueError(
                            f"{path} 完整父级消费必须与父战役档位和难度一致: "
                            f"{child_id}/{campaign_member['actor_name']}"
                        )
                    if not command_index["basis"] or not command_index["source_refs"]:
                        raise ValueError(f"{path} 人物轻量指挥索引缺少依据: {child_id}")
                    if not set(command_index["source_refs"]).issubset(child["source_refs"]):
                        raise ValueError(f"{path} 人物轻量指挥索引史源越界: {child_id}")
                _validate_campaign_command_topology(
                    path,
                    child_id,
                    child.get("campaign_command_topology"),
                    child["members"],
                )
                ruler_controllers = [
                    campaign_member
                    for campaign_member in child["members"]
                    if campaign_member.get("sovereign_at_event") is True
                    or campaign_member.get("ruler_campaign_relation") is not None
                ]
                if len(ruler_controllers) > 1:
                    raise ValueError(f"{path} 正式战役群只能有一个统治者授权关系: {child_id}")
                if ruler_controllers:
                    ruler_controller = ruler_controllers[0]
                    relation = ruler_controller.get("ruler_campaign_relation")
                    role_code = ruler_controller["role_code"]
                    if ruler_controller.get("sovereign_at_event") is not True or not relation:
                        raise ValueError(f"{path} 统治者授权关系缺少唯一事实轴: {child_id}")
                    if relation == "authorization_only" and role_code != "not_in_command_chain":
                        raise ValueError(f"{path} 仅授权者不得进入军事指挥链: {child_id}")
                    if relation == "frontline_command" and role_code not in {
                        "commander_in_chief",
                        "principal_commander",
                    }:
                        raise ValueError(f"{path} 完整亲征必须进入最高实际指挥层: {child_id}")
                    if relation == "operational_direction" and role_code not in {
                        "commander_in_chief",
                        "principal_commander",
                        "not_in_command_chain",
                    }:
                        raise ValueError(f"{path} 战役筹划与统筹角色非法: {child_id}")
                if not isinstance(child.get("stable_delivery"), bool):
                    raise ValueError(f"{path} 正式战役群缺少稳定交付判断: {child_id}")
                if not isinstance(child.get("source_refs"), list) or not child["source_refs"]:
                    raise ValueError(f"{path} 正式战役群缺少逐字史源: {child_id}")
            elif any(
                key in child
                for key in ("members", "stable_delivery", "payload")
            ):
                raise ValueError(f"{path} 非战役上下文不得伪装为正式成果: {child_id}")
            child_war_event_refs = [
                str(ref) for ref in child.get("war_event_refs") or []
            ]
            if not child_war_event_refs or not set(child_war_event_refs).issubset(
                war_event_refs
            ):
                raise ValueError(f"{path} 子战役群底账映射非法: {child_id}")
            normalized_child = {**child, "war_event_refs": child_war_event_refs}
            for war_event_ref in child_war_event_refs:
                groups_by_event[war_event_ref].append(normalized_child)
        uncovered_refs = [
            ref for ref, groups in groups_by_event.items() if not groups
        ]
        if uncovered_refs:
            raise ValueError(
                f"{path} 统一进程存在未挂战役群的底账事件: "
                f"{portfolio_ref}/{uncovered_refs}"
            )
        for war_event_ref in war_event_refs:
            if war_event_ref in indexed:
                raise ValueError(f"{path} 底账事件跨统一进程重复: {war_event_ref}")
            indexed[war_event_ref] = {
                "portfolio_ref": portfolio_ref,
                "status": row["status"],
                "registration_role": row["registration_role"],
                "allow_open_portfolio_root": row["allow_open_portfolio_root"],
                "war_event_refs": war_event_refs,
                "basis": row["basis"],
                "campaign_groups": groups_by_event[war_event_ref],
            }
    return indexed


def _military_capability_contribution(
    member: Mapping[str, Any],
) -> tuple[str, str, str, list[str]]:
    """读取人物实际军事贡献；旧字段只作迁移期事实兼容，不作为角色门槛。"""

    raw = member.get("military_capability_contribution")
    if isinstance(raw, Mapping):
        capability_mode = str(raw.get("capability_mode") or "unresolved")
        decisive_relation = str(raw.get("decisive_relation") or "unresolved")
        if (
            capability_mode not in _MILITARY_CAPABILITY_MODES
            or decisive_relation not in _DECISIVE_RELATIONS
            or not raw.get("basis")
            or not raw.get("source_refs")
            or (
                capability_mode
                in {"operational_design", "authorization_only", "nominal_only"}
                and decisive_relation not in {"none", "unresolved"}
            )
        ):
            raise ValueError("人物军事能力贡献两轴不完整或互相矛盾")
        return (
            capability_mode,
            decisive_relation,
            str(raw.get("basis") or member.get("contribution_scope") or ""),
            list(raw.get("source_refs") or ()),
        )

    legacy_class = str(member.get("talent_contribution_class") or "")
    legacy_map = {
        "decisive_creator": ("integrated_command", "decisive_creator"),
        "decisive_successor": ("integrated_command", "decisive_successor"),
        "co_decisive": ("independent_direction", "co_decisive"),
        "terminal_finisher": ("tactical_execution", "terminal_finisher"),
        "stage_executor": ("tactical_execution", "stage_executor"),
        "strategic_director": ("operational_design", "none"),
        "nominal_only": ("nominal_only", "none"),
    }
    capability_mode, decisive_relation = legacy_map.get(
        legacy_class, ("unresolved", "unresolved")
    )
    return (
        capability_mode,
        decisive_relation,
        str(member.get("contribution_scope") or ""),
        [],
    )


def derive_person_command_index(
    member: Mapping[str, Any],
    *,
    campaign_tier: str,
    combat_difficulty: str,
    battle_result: str,
    source_refs: Sequence[str],
    attributable_failures: Sequence[Mapping[str, Any]] = (),
    campaign_command_topology: str = "single_integrated_command",
) -> dict[str, Any]:
    """生成门槛无关的轻量人物指挥索引；档位仅是当前可安全消费投影。"""

    tier_order = ("C", "B", "A", "S-", "S", "S+")
    difficulty_order = ("D0", "D1", "D2", "D3", "D4")
    role = str(member.get("role_code") or "")
    actor_kind = str(member.get("actor_kind") or "")
    relation = str(member.get("ruler_campaign_relation") or "")
    strategic_relation = str(member.get("strategic_command_relation") or "")
    control_extent = str(member.get("control_extent") or "")
    talent_credit = str(member.get("talent_credit") or "")
    capability_mode, decisive_relation, basis, contribution_source_refs = (
        _military_capability_contribution(member)
    )
    result_direction = {
        "victory": "positive",
        "mixed": "mixed_review",
        "defeat": "negative",
        "unclear": "unclear",
    }[battle_result]
    resolved_source_refs = contribution_source_refs or list(source_refs)
    actor_ref = str(member.get("actor_ref") or "")
    actor_name = str(member.get("actor_name") or "")
    has_attributable_failure = any(
        (actor_ref and str(failure.get("actor_ref") or "") == actor_ref)
        or (actor_name and str(failure.get("actor_name") or "") == actor_name)
        for failure in attributable_failures
    )
    has_explicit_failure_basis = any(
        marker in basis
        for marker in (
            "失败责任",
            "承担败绩",
        )
    )
    # 多方、联邦或接续指挥链中，人物所属一方可能与父群的总体结果相反。
    # 显式人物方向优先于父群方向，不能只在 opposed_commands 中生效。
    if member.get("command_result_direction"):
        result_direction = str(member["command_result_direction"])

    if capability_mode in {"authorization_only", "nominal_only"}:
        return {
            "consumption_mode": "none",
            "command_scope": "no_person_command_credit",
            "capability_mode": capability_mode,
            "decisive_relation": decisive_relation,
            "result_direction": "not_applicable",
            "projected_result_tier": None,
            "projected_combat_difficulty": None,
            "detail_status": "not_required",
            "basis": basis,
            "source_refs": resolved_source_refs,
        }

    if capability_mode == "operational_design" and talent_credit == "none":
        return {
            "consumption_mode": "none",
            "command_scope": "no_person_command_credit",
            "capability_mode": capability_mode,
            "decisive_relation": decisive_relation,
            "result_direction": "not_applicable",
            "projected_result_tier": None,
            "projected_combat_difficulty": None,
            "detail_status": "not_required",
            "basis": basis,
            "source_refs": resolved_source_refs,
        }

    if capability_mode == "operational_design":
        return {
            "consumption_mode": "operational_result",
            "command_scope": "operational_strategy",
            "capability_mode": capability_mode,
            "decisive_relation": decisive_relation,
            "result_direction": result_direction,
            "projected_result_tier": campaign_tier,
            "projected_combat_difficulty": None,
            "detail_status": "operational_direction_resolved",
            "basis": basis,
            "source_refs": resolved_source_refs,
        }

    # 人物角色只描述组织位置；已经人工裁定为未形成决定性关系时，
    # 不得再由“主帅/主将”旧快路径反推出父级或降档成果。
    if decisive_relation == "none":
        return {
            "consumption_mode": "none",
            "command_scope": "no_person_command_credit",
            "capability_mode": capability_mode,
            "decisive_relation": decisive_relation,
            "result_direction": "not_applicable",
            "projected_result_tier": None,
            "projected_combat_difficulty": None,
            "detail_status": "not_required",
            "basis": basis,
            "source_refs": resolved_source_refs,
        }

    if decisive_relation in {"stage_executor", "terminal_finisher"}:
        if (
            result_direction != "positive"
            or has_attributable_failure
            or has_explicit_failure_basis
        ):
            return {
                "consumption_mode": "person_result_required",
                "command_scope": "limited_person_contribution",
                "capability_mode": capability_mode,
                "decisive_relation": decisive_relation,
                "result_direction": (
                    "negative" if result_direction == "negative" else "mixed_review"
                ),
                "projected_result_tier": None,
                "projected_combat_difficulty": None,
                "detail_status": "failure_review_required",
                "basis": basis,
                "source_refs": resolved_source_refs,
            }
        projected_tier = tier_order[
            min(tier_order.index(campaign_tier), tier_order.index("A"))
        ]
        projected_difficulty = difficulty_order[
            min(
                difficulty_order.index(combat_difficulty),
                difficulty_order.index("D2"),
            )
        ]
        return {
            "consumption_mode": "scoped_projection",
            "command_scope": "limited_person_contribution",
            "capability_mode": capability_mode,
            "decisive_relation": decisive_relation,
            "result_direction": result_direction,
            "projected_result_tier": projected_tier,
            "projected_combat_difficulty": projected_difficulty,
            "detail_status": "person_result_required",
            "basis": basis,
            "source_refs": resolved_source_refs,
        }

    if decisive_relation in {"decisive_creator", "decisive_successor"}:
        if campaign_command_topology == "opposed_commands":
            return {
                "consumption_mode": "person_result_required",
                "command_scope": "opposed_full_campaign",
                "capability_mode": capability_mode,
                "decisive_relation": decisive_relation,
                "result_direction": str(
                    member.get("command_result_direction") or "unclear"
                ),
                "projected_result_tier": None,
                "projected_combat_difficulty": None,
                "detail_status": "person_result_required",
                "basis": basis,
                "source_refs": resolved_source_refs,
            }
        integrated_full_parent = capability_mode == "integrated_command"
        return {
            "consumption_mode": (
                "full_parent" if integrated_full_parent else "person_result_required"
            ),
            "command_scope": (
                "decisive_contribution"
                if integrated_full_parent
                else "limited_person_contribution"
            ),
            "capability_mode": capability_mode,
            "decisive_relation": decisive_relation,
            "result_direction": result_direction,
            "projected_result_tier": campaign_tier if integrated_full_parent else None,
            "projected_combat_difficulty": (
                combat_difficulty if integrated_full_parent else None
            ),
            "detail_status": (
                "not_required"
                if integrated_full_parent and result_direction == "positive"
                else "failure_review_required"
                if result_direction in {"negative", "mixed_review"}
                else "person_result_required"
            ),
            "basis": basis,
            "source_refs": resolved_source_refs,
        }

    if decisive_relation == "co_decisive":
        return {
            "consumption_mode": "person_result_required",
            "command_scope": "co_decisive_contribution",
            "capability_mode": capability_mode,
            "decisive_relation": decisive_relation,
            "result_direction": result_direction,
            "projected_result_tier": None,
            "projected_combat_difficulty": None,
            "detail_status": "person_result_required",
            "basis": basis,
            "source_refs": resolved_source_refs,
        }

    if campaign_command_topology == "opposed_commands" and role == "commander_in_chief":
        opposed_direction = str(member.get("command_result_direction") or "unclear")
        return {
            "consumption_mode": "person_result_required",
            "command_scope": "opposed_full_campaign",
            "capability_mode": "integrated_command",
            "decisive_relation": "decisive_creator",
            "result_direction": opposed_direction,
            "projected_result_tier": None,
            "projected_combat_difficulty": None,
            "detail_status": (
                "failure_review_required"
                if opposed_direction in {"mixed_review", "negative"}
                else "person_result_required"
            ),
            "basis": basis,
            "source_refs": resolved_source_refs,
        }

    if campaign_command_topology == "joint_integrated_command" and role == "commander_in_chief":
        return {
            "consumption_mode": "joint_parent",
            "command_scope": "joint_full_campaign",
            "capability_mode": "integrated_command",
            "decisive_relation": "co_decisive",
            "result_direction": result_direction,
            "projected_result_tier": campaign_tier,
            "projected_combat_difficulty": combat_difficulty,
            "detail_status": (
                "person_result_required"
                if result_direction == "positive"
                else "failure_review_required"
            ),
            "basis": basis,
            "source_refs": resolved_source_refs,
        }

    full_parent = campaign_command_topology == "single_integrated_command" and role == "commander_in_chief" and (
        (
            actor_kind == "ruler"
            and relation == "frontline_command"
        )
        or (
            actor_kind != "ruler"
            and talent_credit
            not in {"not_applicable", "covered_by_child", "scoped"}
        )
    )
    if full_parent:
        return {
            "consumption_mode": "full_parent",
            "command_scope": "full_campaign",
            "capability_mode": "integrated_command",
            "decisive_relation": "decisive_creator",
            "result_direction": result_direction,
            "projected_result_tier": campaign_tier,
            "projected_combat_difficulty": combat_difficulty,
            "detail_status": (
                "not_required"
                if result_direction == "positive"
                else "failure_review_required"
            ),
            "basis": basis,
            "source_refs": resolved_source_refs,
        }

    if (
        actor_kind == "ruler"
        and relation == "operational_direction"
        and role == "not_in_command_chain"
    ):
        return {
            "consumption_mode": "operational_result",
            "command_scope": "operational_strategy",
            "capability_mode": "operational_design",
            "decisive_relation": "none",
            "result_direction": result_direction,
            "projected_result_tier": campaign_tier,
            "projected_combat_difficulty": None,
            "detail_status": "operational_direction_resolved",
            "basis": basis,
            "source_refs": resolved_source_refs,
        }
    if actor_kind == "ruler" and relation == "operational_direction":
        return {
            "consumption_mode": "person_result_required",
            "command_scope": "operational_direction_unresolved",
            "capability_mode": "operational_design",
            "decisive_relation": "unresolved",
            "result_direction": result_direction,
            "projected_result_tier": None,
            "projected_combat_difficulty": None,
            "detail_status": "person_result_required",
            "basis": basis,
            "source_refs": resolved_source_refs,
        }
    if (
        actor_kind != "ruler"
        and strategic_relation == "operational_direction"
        and role == "not_in_command_chain"
    ):
        return {
            "consumption_mode": "operational_result",
            "command_scope": "operational_strategy",
            "capability_mode": "operational_design",
            "decisive_relation": "none",
            "result_direction": result_direction,
            "projected_result_tier": campaign_tier,
            "projected_combat_difficulty": None,
            "detail_status": "operational_direction_resolved",
            "basis": basis,
            "source_refs": resolved_source_refs,
        }

    if role == "principal_commander" or (
        role == "commander_in_chief" and talent_credit == "covered_by_child"
    ):
        if (
            result_direction != "positive"
            or has_attributable_failure
            or has_explicit_failure_basis
        ):
            return {
                "consumption_mode": "person_result_required",
                "command_scope": "independent_direction",
                "capability_mode": "independent_direction",
                "decisive_relation": "stage_executor",
                "result_direction": (
                    "negative" if result_direction == "negative" else "mixed_review"
                ),
                "projected_result_tier": None,
                "projected_combat_difficulty": None,
                "detail_status": "failure_review_required",
                "basis": basis,
                "source_refs": resolved_source_refs,
            }
        projected_tier = tier_order[min(tier_order.index(campaign_tier), tier_order.index("A"))]
        projected_difficulty = difficulty_order[
            min(
                difficulty_order.index(combat_difficulty),
                difficulty_order.index("D2"),
            )
        ]
        needs_detail = (
            tier_order.index(campaign_tier) >= tier_order.index("S-")
            or difficulty_order.index(combat_difficulty) >= difficulty_order.index("D3")
        )
        return {
            "consumption_mode": "scoped_projection",
            "command_scope": "independent_direction",
            "capability_mode": "independent_direction",
            "decisive_relation": "stage_executor",
            "result_direction": result_direction,
            "projected_result_tier": projected_tier,
            "projected_combat_difficulty": projected_difficulty,
            "detail_status": (
                "failure_review_required"
                if result_direction != "positive"
                else "person_result_required"
                if needs_detail
                else "not_required"
            ),
            "basis": basis,
            "source_refs": resolved_source_refs,
        }

    return {
        "consumption_mode": "none",
        "command_scope": (
            "supporting_participation"
            if role == "participant"
            else "no_person_command_credit"
        ),
        "capability_mode": "nominal_only",
        "decisive_relation": "none",
        "result_direction": "not_applicable",
        "projected_result_tier": None,
        "projected_combat_difficulty": None,
        "detail_status": "not_required",
        "basis": basis,
        "source_refs": resolved_source_refs,
    }


def _grade_number(value: object) -> int | None:
    match = re.search(r"(\d+)", str(value or ""))
    return int(match.group(1)) if match else None


def _settlement_summary(row: Mapping[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {
            "status": "missing",
            "strategic_security_grade": None,
            "war_cost_grade": None,
            "war_return_clues": [],
            "return_class": None,
            "portfolio_usable": False,
            "adjudication_status": None,
            "benefit_readiness": None,
            "grade_contract_complete": False,
            "high_impact_review": False,
        }
    strategic_grade = row.get("strategic_security_grade")
    cost_grade = row.get("wc_consistency_grade") or (row.get("cost_axes") or {}).get("WC")
    return_clues = _unique(row.get("wr_clues") or [])
    impact_numbers = [
        value
        for value in (
            _grade_number(strategic_grade),
            _grade_number(cost_grade),
            *(_grade_number(value) for value in return_clues),
        )
        if value is not None
    ]
    return {
        "status": "joined",
        "strategic_security_grade": strategic_grade,
        "war_cost_grade": cost_grade,
        "war_return_clues": return_clues,
        "return_class": row.get("return_class"),
        "portfolio_usable": bool(row.get("portfolio_usable")),
        "adjudication_status": row.get("adjudication_status"),
        "benefit_readiness": row.get("benefit_readiness"),
        "grade_contract_complete": bool(
            re.fullmatch(r"(?:SB|SN)\d+", str(strategic_grade or ""))
            and re.fullmatch(r"WC\d+", str(cost_grade or ""))
        ),
        "high_impact_review": max(impact_numbers, default=0) >= 4,
    }


def _registration_disposition(candidate: Mapping[str, Any]) -> tuple[str, list[str]]:
    routing = set(candidate["account_routing"])
    readiness = candidate["evidence_readiness"]
    settlement = candidate["military_settlement"]
    if "UNIFICATION_ONLY" in routing:
        return (
            "UNIFICATION_DEEP_REVIEW",
            [
                "统一、创业或兼并战争必须按皇帝统一组合横向校准",
                "普通战役批次不得自动定档或拆分累计",
            ],
        )

    weak_source_reasons: list[str] = []
    if candidate["source_is_draft_or_nonfinal"]:
        weak_source_reasons.append("来源仍标记为草稿或非最终版")
    if not readiness["source_anchor_present"]:
        weak_source_reasons.append("缺少可回查来源锚点")
    if not readiness["result_known"]:
        weak_source_reasons.append("终局结果仍未知")
    if weak_source_reasons:
        if settlement["high_impact_review"]:
            return (
                "BATCH_REVIEW",
                weak_source_reasons + ["既有SB/SN、WR或WC达到4级以上，保留优先复核"],
            )
        return "HOLD_OR_REJECT", weak_source_reasons

    automatic_conditions = (
        readiness["command_attribution_known"]
        and candidate["stage_count"] == 0
        and settlement["status"] == "joined"
        and settlement["portfolio_usable"]
        and settlement["adjudication_status"] == "REVIEWED"
        and settlement["benefit_readiness"] == "READY_BENEFIT"
        and settlement["grade_contract_complete"]
    )
    if automatic_conditions:
        return "AUTO_REGISTER", ["终局、指挥归属和来源锚点齐备，且既有军事结算已复核可用"]

    reasons = ["事实足以进入结构化批审，但尚不满足无判断登记条件"]
    if candidate["stage_count"]:
        reasons.append("含阶段卡，需确认父子边界和一次结算范围")
    if not readiness["command_attribution_known"]:
        reasons.append("指挥归属仍需裁决")
    if not settlement["portfolio_usable"]:
        reasons.append("既有军事结算尚不可用于成果组合")
    if not settlement["grade_contract_complete"]:
        reasons.append("SB/SN或WC尚未形成合法确定档位")
    return "BATCH_REVIEW", reasons


def _build_throughput_probe(
    candidates: list[Mapping[str, Any]], *, per_route: int = 20
) -> dict[str, Any]:
    selected: list[dict[str, Any]] = []
    for disposition in ("AUTO_REGISTER", "BATCH_REVIEW"):
        route_rows = [
            row
            for row in candidates
            if row["registration_disposition"] == disposition
        ][:per_route]
        selected.extend(
            {
                "candidate_ref": row["candidate_ref"],
                "dynasty": row["dynasty"],
                "war_event_id": row["war_event_id"],
                "registration_disposition": disposition,
                "high_impact_review": row["military_settlement"][
                    "high_impact_review"
                ],
            }
            for row in route_rows
        )
    return {
        "status": "UNADJUDICATED_THROUGHPUT_PROBE",
        "selection_method": "前20个AUTO_REGISTER加前20个BATCH_REVIEW；统一战争排除",
        "target_count": per_route * 2,
        "selected_count": len(selected),
        "candidates": selected,
    }


def build_battle_outcome_worklist(
    rows: list[Mapping[str, Any]],
    *,
    existing_registry: Mapping[str, Any] | None = None,
    military_settlements: Mapping[str, Mapping[str, Any]] | None = None,
    unification_scope_adjudications: Mapping[str, Mapping[str, Any]] | None = None,
    unification_tier_adjudications: Mapping[str, Mapping[str, Any]] | None = None,
    ordinary_campaign_adjudications: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["_dynasty"]), str(row["war_event_id"]))].append(row)

    existing_refs_by_war_event: dict[str, list[str]] = defaultdict(list)
    for outcome in (existing_registry or {}).get("outcomes") or []:
        registration_ref = str(
            outcome.get("registration_ref") or outcome.get("outcome_ref") or ""
        )
        for source_war_event_ref in outcome.get("source_war_event_refs") or []:
            if registration_ref:
                existing_refs_by_war_event[str(source_war_event_ref)].append(
                    registration_ref
                )

    candidates: list[dict[str, Any]] = []
    skipped_open_groups = 0
    manually_adjudicated_open_unification_roots = 0
    for (dynasty, war_event_id), group_rows in sorted(grouped.items()):
        terminal_rows = [
            row
            for row in group_rows
            if row.get("settlement_role") == "terminal"
            and row.get("settlement_status") == "closed"
        ]
        scope_adjudication = (unification_scope_adjudications or {}).get(
            war_event_id
        ) or {}
        tier_adjudication = (unification_tier_adjudications or {}).get(
            war_event_id
        ) or {}
        manually_adjudicated_open_root = (
            not terminal_rows
            and scope_adjudication.get("scope_kind") == "FULL_REALM_UNIFICATION"
            and tier_adjudication.get("registration_role")
            == "UNIFICATION_CAMPAIGN_PORTFOLIO"
            and tier_adjudication.get("allow_open_portfolio_root") is True
        )
        if not terminal_rows and not manually_adjudicated_open_root:
            skipped_open_groups += 1
            continue
        if manually_adjudicated_open_root:
            manually_adjudicated_open_unification_roots += 1

        source_refs = _unique(
            ref
            for row in group_rows
            for ref in (row.get("source_revision_refs") or [])
        )
        source_cards = _unique(row.get("source_card_id") for row in group_rows)
        source_files = _unique(
            occurrence.get("source_file")
            for row in group_rows
            for occurrence in (row.get("source_occurrences") or [])
        )
        draft = any(
            "source_marked_draft_or_nonfinal" in (row.get("review_flags") or [])
            for row in group_rows
        )
        result_rows = terminal_rows or group_rows
        terminal_results = [row.get("outcome") for row in result_rows]
        terminal_commands = [
            row.get("command_attribution") for row in result_rows
        ]
        terminal_nodes = [
            {
                "battle_id": row.get("battle_id"),
                "campaign_group": row.get("campaign_group"),
                "title": row.get("title"),
                "time_range": row.get("time_range"),
                "evaluation_subject": row.get("evaluation_subject"),
                "outcome": row.get("outcome"),
                "objective_completion": row.get("objective_completion"),
                "opponent_status": row.get("opponent_status"),
                "operational_difficulty": row.get("operational_difficulty"),
                "command_attribution": row.get("command_attribution"),
                "source_fact_fields": row.get("source_fact_fields") or {},
                "source_card_id": row.get("source_card_id"),
                "source_revision_refs": row.get("source_revision_refs") or [],
            }
            for row in sorted(
                result_rows,
                key=lambda item: str(item.get("battle_id") or ""),
            )
        ]
        stage_nodes = [
            {
                "battle_id": row.get("battle_id"),
                "parent_battle_id": row.get("parent_battle_id"),
                "campaign_group": row.get("campaign_group"),
                "title": row.get("title"),
                "time_range": row.get("time_range"),
                "outcome": row.get("outcome"),
                "objective_completion": row.get("objective_completion"),
                "opponent_status": row.get("opponent_status"),
                "operational_difficulty": row.get("operational_difficulty"),
                "command_attribution": row.get("command_attribution"),
                "source_card_id": row.get("source_card_id"),
                "source_revision_refs": row.get("source_revision_refs") or [],
            }
            for row in sorted(
                group_rows,
                key=lambda item: (
                    item.get("settlement_role") != "terminal",
                    str(item.get("battle_id") or ""),
                ),
            )
            if row.get("settlement_role") == "stage"
        ]
        settlement = _settlement_summary((military_settlements or {}).get(war_event_id))
        candidate = {
            "candidate_ref": "BOW-"
            + _digest({"dynasty": dynasty, "war_event_id": war_event_id})[
                :20
            ].upper(),
            "dynasty": dynasty,
            "war_event_id": war_event_id,
            "account_routing": _unique(
                row.get("account_routing") for row in group_rows
            ),
            "campaign_groups": _unique(
                row.get("campaign_group") for row in group_rows
            ),
            "terminal_battle_ids": _unique(
                row.get("battle_id") for row in terminal_rows
            ),
            "source_settlement_closed": bool(terminal_rows),
            "terminal_nodes": terminal_nodes,
            "stage_count": sum(
                row.get("settlement_role") == "stage" for row in group_rows
            ),
            "stage_nodes": stage_nodes,
            "titles": _unique(row.get("title") for row in group_rows),
            "time_ranges": _unique(row.get("time_range") for row in group_rows),
            "evaluation_subjects": _unique(
                row.get("evaluation_subject") for row in group_rows
            ),
            "source_card_ids": source_cards,
            "source_files": source_files,
            "source_revision_refs": source_refs,
            "source_is_draft_or_nonfinal": draft,
            "evidence_readiness": {
                "result_known": any(_known(value) for value in terminal_results),
                "command_attribution_known": any(
                    _known(value) for value in terminal_commands
                ),
                "source_anchor_present": bool(source_refs),
                "cost_route_present": any(
                    row.get("cost_ref") not in (None, "") for row in group_rows
                ),
                "defense_route_present": any(
                    row.get("defense_ref") not in (None, "") for row in group_rows
                ),
            },
            "statecraft_review": {
                "status": "pending_manual_review",
                "lead_passages": _statecraft_leads(group_rows),
                "note": "线索仅用于定位；必须另证具名提出、采纳、实施和独立战略结果。",
            },
            "military_settlement": settlement,
            "existing_registration_refs": sorted(
                set(existing_refs_by_war_event.get(war_event_id) or [])
            ),
            "existing_link_status": (
                "linked_by_war_event_id"
                if existing_refs_by_war_event.get(war_event_id)
                else "unresolved_missing_war_event_link"
            ),
        }
        disposition, reasons = _registration_disposition(candidate)
        candidate["registration_disposition"] = disposition
        candidate["disposition_reasons"] = reasons
        if disposition == "UNIFICATION_DEEP_REVIEW":
            candidate["unification_scope_adjudication"] = dict(
                (unification_scope_adjudications or {}).get(war_event_id)
                or {"status": "MISSING_ADJUDICATION"}
            )
            if (
                candidate["unification_scope_adjudication"].get("scope_kind")
                == "FULL_REALM_UNIFICATION"
            ):
                candidate["unification_tier_adjudication"] = dict(
                    (unification_tier_adjudications or {}).get(war_event_id)
                    or {"status": "MISSING_ADJUDICATION"}
                )
        ordinary_adjudication = (ordinary_campaign_adjudications or {}).get(
            war_event_id
        )
        if ordinary_adjudication is not None:
            if ordinary_adjudication.get("candidate_disposition") != disposition:
                raise ValueError(
                    f"普通战役裁决路由不一致: {war_event_id}/{disposition}"
                )
            if ordinary_adjudication.get("status") == (
                "ADJUDICATED_SOURCE_BACKFILL_REQUIRED"
            ):
                missing_source_refs = sorted(
                    set(candidate["source_revision_refs"])
                    - set(ordinary_adjudication.get("source_refs") or ())
                )
                if missing_source_refs:
                    raise ValueError(
                        "普通战役正式裁决遗漏父群或阶段史源: "
                        f"{war_event_id}/{missing_source_refs}"
                    )
            candidate["ordinary_campaign_adjudication"] = dict(
                ordinary_adjudication
            )
            if not candidate["existing_registration_refs"]:
                candidate["existing_link_status"] = "registered_not_gold_adjudication"
        candidates.append(candidate)

    candidates.sort(
        key=lambda row: (
            _DISPOSITION_ORDER[row["registration_disposition"]],
            not row["military_settlement"]["high_impact_review"],
            row["dynasty"],
            row["war_event_id"],
        )
    )
    candidate_input_fingerprint = _digest(
        [
            {
                key: value
                for key, value in candidate.items()
                if key
                not in {
                    "ordinary_campaign_adjudication",
                    "unification_scope_adjudication",
                    "unification_tier_adjudication",
                    "existing_link_status",
                }
            }
            for candidate in candidates
        ]
    )

    existing_campaigns = []
    if existing_registry is not None:
        existing_campaigns = [
            {
                "registration_ref": row.get("registration_ref"),
                "event_level": row.get("event_level"),
                "canonical_label": row.get("canonical_label"),
                "source_war_event_refs": row.get("source_war_event_refs") or [],
            }
            for row in (existing_registry.get("outcomes") or [])
            if row.get("event_level")
            in {"war_terminal", "campaign_group", "person_command_result"}
        ]

    unification_candidate_ids = {
        row["war_event_id"]
        for row in candidates
        if row["registration_disposition"] == "UNIFICATION_DEEP_REVIEW"
    }
    adjudicated_ids = set(unification_scope_adjudications or {})
    full_realm_ids = {
        row["war_event_id"]
        for row in candidates
        if row.get("unification_scope_adjudication", {}).get("scope_kind")
        == "FULL_REALM_UNIFICATION"
    }
    full_realm_portfolio_refs = {
        row.get("unification_scope_adjudication", {}).get("portfolio_ref")
        for row in candidates
        if row.get("unification_scope_adjudication", {}).get("scope_kind")
        == "FULL_REALM_UNIFICATION"
    }
    full_realm_portfolio_refs.discard(None)
    tier_adjudicated_ids = set(unification_tier_adjudications or {})
    auto_register_ids = {
        row["war_event_id"]
        for row in candidates
        if row["registration_disposition"] == "AUTO_REGISTER"
        and not row["existing_registration_refs"]
    }
    ordinary_candidate_ids = {
        row["war_event_id"]
        for row in candidates
        if row["registration_disposition"] != "UNIFICATION_DEEP_REVIEW"
        and not row["existing_registration_refs"]
    }
    ordinary_adjudicated_ids = set(ordinary_campaign_adjudications or {})
    tier_portfolios: dict[str, dict[str, Any]] = {}
    for adjudication in (unification_tier_adjudications or {}).values():
        portfolio_ref = str(adjudication.get("portfolio_ref") or "")
        portfolio = tier_portfolios.setdefault(
            portfolio_ref,
            {
                "portfolio_ref": portfolio_ref,
                "status": adjudication.get("status"),
                "registration_role": adjudication.get("registration_role"),
                "allow_open_portfolio_root": adjudication.get(
                    "allow_open_portfolio_root"
                ),
                "war_event_refs": adjudication.get("war_event_refs") or [],
                "basis": adjudication.get("basis"),
                "campaign_groups": [],
            },
        )
        known_group_ids = {
            group.get("campaign_group_id")
            for group in portfolio["campaign_groups"]
        }
        for group in adjudication.get("campaign_groups") or []:
            if group.get("campaign_group_id") not in known_group_ids:
                portfolio["campaign_groups"].append(group)
                known_group_ids.add(group.get("campaign_group_id"))
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "routed_for_registration_review",
        "candidate_input_fingerprint": candidate_input_fingerprint,
        "declarations": {
            "ledger_row_count": len(rows),
            "unique_war_event_count": len(grouped),
            "candidate_count": len(candidates),
            "skipped_open_group_count": skipped_open_groups,
            "manually_adjudicated_open_unification_root_count": (
                manually_adjudicated_open_unification_roots
            ),
            "draft_or_nonfinal_candidate_count": sum(
                row["source_is_draft_or_nonfinal"] for row in candidates
            ),
            "statecraft_lead_candidate_count": sum(
                bool(row["statecraft_review"]["lead_passages"])
                for row in candidates
            ),
            "existing_registered_campaign_node_count": len(existing_campaigns),
            "existing_linked_candidate_count": sum(
                bool(row["existing_registration_refs"]) for row in candidates
            ),
            "existing_link_gap": bool(existing_campaigns)
            and (
                any(not row["source_war_event_refs"] for row in existing_campaigns)
                or any(not row["existing_registration_refs"] for row in candidates)
            ),
            "military_settlement_joined_count": sum(
                row["military_settlement"]["status"] == "joined"
                for row in candidates
            ),
            "disposition_counts": {
                disposition: sum(
                    row["registration_disposition"] == disposition
                    for row in candidates
                )
                for disposition in _DISPOSITION_ORDER
            },
            "unification_scope_counts": {
                scope_kind: sum(
                    row.get("unification_scope_adjudication", {}).get("scope_kind")
                    == scope_kind
                    for row in candidates
                )
                for scope_kind in (
                    "FULL_REALM_UNIFICATION",
                    "REGIONAL_REGIME_FOUNDATION",
                    "REGIONAL_ANNEXATION",
                    "NOT_A_UNIFICATION_PORTFOLIO",
                )
            },
            "full_realm_portfolio_count": len(full_realm_portfolio_refs),
            "ordinary_campaign_adjudicated_count": len(
                ordinary_adjudicated_ids & auto_register_ids
            ),
            "ordinary_candidate_adjudicated_count": len(
                ordinary_adjudicated_ids & ordinary_candidate_ids
            ),
            "ordinary_candidate_pending_ids": sorted(
                ordinary_candidate_ids - ordinary_adjudicated_ids
            ),
            "ordinary_campaign_pending_ids": sorted(
                auto_register_ids - ordinary_adjudicated_ids
            ),
            "ordinary_campaign_extra_ids": sorted(
                ordinary_adjudicated_ids - ordinary_candidate_ids
            ),
            "unification_scope_missing_ids": sorted(
                unification_candidate_ids - adjudicated_ids
            ),
            "unification_scope_extra_ids": sorted(
                adjudicated_ids - unification_candidate_ids
            ),
            "unification_tier_missing_ids": sorted(
                full_realm_ids - tier_adjudicated_ids
            ),
            "unification_tier_extra_ids": sorted(
                tier_adjudicated_ids - full_realm_ids
            ),
            "unification_tier_status_counts": {
                status: sum(
                    row.get("status") == status
                    for row in tier_portfolios.values()
                )
                for status in sorted(
                    {
                        str(row.get("status"))
                        for row in tier_portfolios.values()
                    }
                )
            },
        },
        "unification_portfolios": list(tier_portfolios.values()),
        "existing_campaign_nodes_without_war_event_link": existing_campaigns,
        "ordinary_throughput_probe": _build_throughput_probe(candidates),
        "candidates": candidates,
    }
    payload["fingerprint"] = _digest(payload)
    return payload


def render_battle_outcome_worklist_markdown(report: Mapping[str, Any]) -> str:
    declarations = report["declarations"]
    def cell(value: object) -> str:
        return " ".join(str(value or "—").split()).replace("|", "\\|")

    lines = [
        "# 战役公共成果候选清单",
        "",
        f"- 状态：`{report['status']}`",
        f"- 战役底账行：{declarations['ledger_row_count']}",
        f"- 唯一 `war_event_id`：{declarations['unique_war_event_count']}",
        f"- 战役成果候选：{declarations['candidate_count']}",
        f"- 未闭合、未进入候选：{declarations['skipped_open_group_count']}",
        "- 显式人工接入的未闭合统一根："
        f"{declarations['manually_adjudicated_open_unification_root_count']}",
        f"- 含草稿或非最终来源：{declarations['draft_or_nonfinal_candidate_count']}",
        f"- 含谋略检索线索：{declarations['statecraft_lead_candidate_count']}",
        f"- 现有公共战役节点：{declarations['existing_registered_campaign_node_count']}",
        f"- 已接入最终军事结算：{declarations['military_settlement_joined_count']}",
        "- 四路分流："
        + "、".join(
            f"`{key}` {value}"
            for key, value in declarations["disposition_counts"].items()
        ),
        "- 统一深审分型："
        + "、".join(
            f"`{key}` {value}"
            for key, value in declarations["unification_scope_counts"].items()
        ),
        "- 大一统统一进程组合状态："
        + "、".join(
            f"`{key}` {value}"
            for key, value in declarations["unification_tier_status_counts"].items()
        ),
        f"- 全国统一进程组合：{declarations['full_realm_portfolio_count']}",
        f"- AUTO候选非Gold裁决：{declarations['ordinary_campaign_adjudicated_count']}",
        f"- 普通战役待裁决：{len(declarations['ordinary_campaign_pending_ids'])}",
        f"- 全部普通候选已裁决：{declarations['ordinary_candidate_adjudicated_count']}",
        f"- 全部普通候选待裁决：{len(declarations['ordinary_candidate_pending_ids'])}",
        "",
        "> `AUTO_REGISTER` 只表示可确定性生成登记骨架，不自动定字母档、不自动晋升正式成果。`UNIFICATION_DEEP_REVIEW` 必须先完成统一组合横向校准；谋略关键词仍只作定位线索。",
        "",
    ]
    unification_portfolios = report.get("unification_portfolios") or []
    if unification_portfolios:
        lines.extend(
            [
                "## 大一统朝代统一进程战役群裁决",
                "",
                "> 六个顶层对象均为统一进程组合；具体战役一律列在组合之下。这里只登记字母档和裁决状态，不含档位数值权重或正式分数。",
                "",
                "| 统一进程 | 底账事件 | 战役群 | 状态 | 角色 | 结果方向 | 档位 | 裁决依据 |",
                "| --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for portfolio in unification_portfolios:
            portfolio_ref = portfolio.get("portfolio_ref")
            portfolio_war_event_refs = portfolio.get("war_event_refs") or []
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{cell(portfolio_ref)}`",
                        cell("、".join(portfolio_war_event_refs)),
                        "统一进程父组合",
                        cell(portfolio.get("status")),
                        cell(portfolio.get("registration_role")),
                        "—",
                        "—",
                        cell(portfolio.get("basis")),
                    ]
                )
                + " |"
            )
            for child in portfolio.get("campaign_groups") or []:
                child_payload = child.get("payload") or {}
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            f"`{cell(portfolio_ref)}`",
                            cell("、".join(child.get("war_event_refs") or [])),
                            f"`{cell(child.get('campaign_group_id'))}`",
                            cell(child.get("status")),
                            cell(child.get("registration_role")),
                            cell(child_payload.get("battle_result")),
                            cell(child_payload.get("campaign_tier")),
                            cell(child.get("basis")),
                        ]
                    )
                    + " |"
                )
        lines.append("")
    by_dynasty: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for candidate in report["candidates"]:
        by_dynasty[str(candidate["dynasty"])].append(candidate)
    for dynasty, candidates in by_dynasty.items():
        lines.extend(
            [
                f"## {dynasty}",
                "",
                "| 候选 | 战役 | 时段 | 分流 | 非Gold裁决 | SB/SN | WC | 阶段卡 | 结果 | 指挥 | 来源 | 草稿 | 谋略线索 |",
                "| --- | --- | --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- |",
            ]
        )
        for row in candidates:
            readiness = row["evidence_readiness"]
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{row['candidate_ref']}`",
                        "、".join(row["titles"]) or row["war_event_id"],
                        "、".join(row["time_ranges"]) or "未知",
                        row["registration_disposition"],
                        row.get("ordinary_campaign_adjudication", {}).get("status")
                        or ("EXISTING_REGISTERED" if row["existing_registration_refs"] else "—"),
                        row["military_settlement"]["strategic_security_grade"] or "—",
                        row["military_settlement"]["war_cost_grade"] or "—",
                        str(row["stage_count"]),
                        "有" if readiness["result_known"] else "缺",
                        "有" if readiness["command_attribution_known"] else "缺",
                        "有" if readiness["source_anchor_present"] else "缺",
                        "是" if row["source_is_draft_or_nonfinal"] else "否",
                        "有" if row["statecraft_review"]["lead_passages"] else "未检出",
                    ]
                )
                + " |"
            )
        lines.append("")
    lines.extend(["## 指纹", "", f"`{report['fingerprint']}`", ""])
    return "\n".join(lines)


def write_battle_outcome_worklist(
    workspace_root: Path, output_dir: Path | None = None
) -> dict[str, Path]:
    ledger_root = workspace_root / "tmp/治理/正式底账/01-战役"
    registry_path = workspace_root / "eval/historical_outcome_registry/current.json"
    existing_registry = (
        json.loads(registry_path.read_text(encoding="utf-8"))
        if registry_path.exists()
        else None
    )
    settlement_path = (
        workspace_root
        / "tmp/治理/正式底账/04-军事与边疆/02-成本收益结算/军事成本收益结算底账.jsonl"
    )
    scope_adjudication_path = (
        workspace_root / "config/unification-campaign-scope-adjudications.json"
    )
    tier_adjudication_path = (
        workspace_root / "config/unification-campaign-tier-adjudications.json"
    )
    ordinary_adjudication_path = (
        workspace_root / "config/ordinary-campaign-adjudications.json"
    )
    report = build_battle_outcome_worklist(
        load_battle_ledger_rows(ledger_root),
        existing_registry=existing_registry,
        military_settlements=load_military_settlements(settlement_path),
        unification_scope_adjudications=load_unification_scope_adjudications(
            scope_adjudication_path
        ),
        unification_tier_adjudications=load_unification_tier_adjudications(
            tier_adjudication_path
        ),
        ordinary_campaign_adjudications=load_ordinary_campaign_adjudications(
            ordinary_adjudication_path
        ),
    )
    target = output_dir or workspace_root / "tmp/战役登记/公共成果候选"
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / "current.json"
    markdown_path = target / "current.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_battle_outcome_worklist_markdown(report), encoding="utf-8"
    )
    return {"json": json_path, "markdown": markdown_path}
