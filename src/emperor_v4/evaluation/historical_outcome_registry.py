from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4

import yaml

from emperor_v4.evaluation.historical_outcome_cluster import (
    cluster_semantic_fingerprint,
)


SCHEMA_VERSION = "historical-outcome-unbound-registry-v1"


def _digest(value: object) -> str:
    return sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _registration_ref(outcome_kind: str, independent_key: str) -> str:
    return "HOUT-" + _digest(
        {"outcome_kind": outcome_kind, "independent_key": independent_key}
    )[:20].upper()


def _event_level(cluster: Mapping[str, Any]) -> str:
    scope = str(cluster.get("settlement_scope") or "")
    if cluster["outcome_kind"] == "campaign":
        return (
            "campaign_subresult"
            if scope == "person_campaign_subresult"
            else "campaign_group"
        )
    return "macro_public_result" if scope == "reign_macro_outcome" else "governance_result"


def _unbound_member(member: Mapping[str, Any]) -> dict[str, Any]:
    result = {
        key: value
        for key, value in member.items()
        if key not in {"actor_kind", "talent_credit", "ruler_campaign_relation"}
    }
    if member.get("ruler_campaign_relation") is not None:
        result["sovereign_relation"] = member["ruler_campaign_relation"]
    return result


def _unbound_outcome(cluster: Mapping[str, Any]) -> dict[str, Any]:
    result = {
        key: value
        for key, value in cluster.items()
        if key
        not in {
            "outcome_ref",
            "semantic_fingerprint",
            "settlement_scope",
            "ruler_window_status",
            "ruler_context_refs",
            "parent_outcome_ref",
        }
    }
    result["registration_ref"] = _registration_ref(
        str(cluster["outcome_kind"]), str(cluster["independent_key"])
    )
    result["event_level"] = _event_level(cluster)
    result["members"] = [_unbound_member(row) for row in cluster["members"]]
    result["origin_outcome_refs"] = [str(cluster["outcome_ref"])]
    if cluster.get("parent_outcome_ref"):
        result["origin_parent_outcome_ref"] = str(cluster["parent_outcome_ref"])
    return result


def build_unbound_historical_outcome_registry(
    source_packs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build the auditable outcome layer before any ruler-window projection."""

    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    origin_to_registration: dict[str, str] = {}
    conflicts: list[dict[str, Any]] = []
    source_pack_refs = []
    duplicate_count = 0
    for source_pack in source_packs:
        source_pack_ref = str(source_pack.get("source_pack_sha256") or "")
        if not source_pack_ref:
            raise ValueError("成果总登记输入缺少 source_pack_sha256")
        source_pack_refs.append(source_pack_ref)
        registry = source_pack.get("outcome_registry") or {}
        for cluster in registry.get("clusters") or ():
            key = (str(cluster["outcome_kind"]), str(cluster["independent_key"]))
            candidate = _unbound_outcome(cluster)
            origin_ref = str(cluster["outcome_ref"])
            origin_to_registration[origin_ref] = candidate["registration_ref"]
            existing = by_key.get(key)
            if existing is None:
                by_key[key] = candidate
                continue
            duplicate_count += 1
            comparable_existing = {
                name: value
                for name, value in existing.items()
                if name
                not in {
                    "fact_refs",
                    "source_refs",
                    "episode_refs",
                    "origin_outcome_refs",
                }
            }
            comparable_candidate = {
                name: value
                for name, value in candidate.items()
                if name
                not in {
                    "fact_refs",
                    "source_refs",
                    "episode_refs",
                    "origin_outcome_refs",
                }
            }
            if comparable_existing != comparable_candidate:
                conflicts.append(
                    {
                        "outcome_kind": key[0],
                        "independent_key": key[1],
                        "origin_outcome_refs": sorted(
                            {
                                *existing["origin_outcome_refs"],
                                *candidate["origin_outcome_refs"],
                            }
                        ),
                        "reason": "同一全局成果键的成果本体不一致，必须先人工归并。",
                    }
                )
                continue
            for field in ("fact_refs", "source_refs", "episode_refs", "origin_outcome_refs"):
                existing[field] = sorted(
                    {*(existing.get(field) or ()), *(candidate.get(field) or ())}
                )

    outcomes = list(by_key.values())
    for outcome in outcomes:
        origin_parent = outcome.pop("origin_parent_outcome_ref", None)
        if origin_parent:
            parent_ref = origin_to_registration.get(str(origin_parent))
            if parent_ref is None:
                conflicts.append(
                    {
                        "outcome_kind": outcome["outcome_kind"],
                        "independent_key": outcome["independent_key"],
                        "origin_outcome_refs": outcome["origin_outcome_refs"],
                        "reason": "人物子战役的父级成果不在总登记输入中。",
                    }
                )
            else:
                outcome["parent_registration_ref"] = parent_ref
        outcome["registration_fingerprint"] = _digest(
            {
                key: value
                for key, value in outcome.items()
                if key not in {"origin_outcome_refs", "registration_fingerprint"}
            }
        )
    outcomes.sort(
        key=lambda row: (
            0 if row["outcome_kind"] == "campaign" else 1,
            str((row.get("period") or {}).get("start") or ""),
            str(row["canonical_label"]),
        )
    )
    campaign_count = sum(row["outcome_kind"] == "campaign" for row in outcomes)
    governance_count = len(outcomes) - campaign_count
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "needs_review" if conflicts else "current_shadow_unbound",
        "declarations": {
            "source_pack_count": len(source_packs),
            "source_pack_refs": sorted(source_pack_refs),
            "outcome_count": len(outcomes),
            "campaign_count": campaign_count,
            "governance_count": governance_count,
            "duplicate_registration_count": duplicate_count,
            "window_binding_count": 0,
            "rule_evidence_unit_count": 0,
            "score_contribution_count": 0,
            "formal_write_count": 0,
        },
        "conflicts": conflicts,
        "outcomes": outcomes,
    }
    report["registry_fingerprint"] = _digest(report)
    return report


def build_ruler_outcome_bindings(
    source_pack: Mapping[str, Any],
    registry: Mapping[str, Any],
) -> dict[str, Any]:
    """Extract only post-registration ruler-window and talent projections."""

    registration_by_key = {
        (str(row["outcome_kind"]), str(row["independent_key"])): row
        for row in registry["outcomes"]
    }
    bindings = []
    for cluster in (source_pack.get("outcome_registry") or {}).get("clusters") or ():
        registration = registration_by_key.get(
            (str(cluster["outcome_kind"]), str(cluster["independent_key"]))
        )
        if registration is None:
            raise ValueError(f"成果未进入总登记: {cluster['outcome_ref']}")
        binding = {
            "registration_ref": registration["registration_ref"],
            "outcome_ref": cluster["outcome_ref"],
            "ruler_window_status": cluster["ruler_window_status"],
            "campaign_talent_credits": {
                str(member["actor_ref"]): member["talent_credit"]
                for member in cluster["members"]
                if cluster["outcome_kind"] == "campaign"
            },
        }
        if "ruler_context_refs" in cluster:
            binding["ruler_context_refs"] = list(
                cluster.get("ruler_context_refs") or ()
            )
        bindings.append(binding)
    bindings.sort(key=lambda row: str(row["registration_ref"]))
    report = {
        "schema_version": "ruler-outcome-binding-v1",
        "status": "current_shadow_binding",
        "ruler_ref": source_pack["ruler_ref"],
        "projected_registry_status": source_pack["outcome_registry"]["status"],
        "source_pack_sha256": source_pack["source_pack_sha256"],
        "registry_fingerprint": registry["registry_fingerprint"],
        "binding_count": len(bindings),
        "formal_write_count": 0,
        "bindings": bindings,
    }
    report["binding_fingerprint"] = _digest(report)
    return report


def materialize_ruler_outcome_registry(
    registry: Mapping[str, Any],
    binding_report: Mapping[str, Any],
) -> dict[str, Any]:
    """Join the accepted outcome layer with one ruler projection for consumers."""

    if binding_report.get("registry_fingerprint") != registry.get(
        "registry_fingerprint"
    ):
        raise ValueError("皇帝窗口绑定与成果总登记版本不一致")
    ruler_ref = str(binding_report["ruler_ref"])
    outcomes_by_ref = {
        str(row["registration_ref"]): row for row in registry["outcomes"]
    }
    bindings_by_registration = {
        str(row["registration_ref"]): row for row in binding_report["bindings"]
    }
    outcome_ref_by_registration = {
        registration_ref: str(binding["outcome_ref"])
        for registration_ref, binding in bindings_by_registration.items()
    }
    clusters = []
    for registration_ref, binding in bindings_by_registration.items():
        registered = outcomes_by_ref.get(registration_ref)
        if registered is None:
            raise ValueError(f"窗口绑定引用未知成果: {registration_ref}")
        cluster = {
            key: json.loads(json.dumps(value, ensure_ascii=False))
            for key, value in registered.items()
            if key
            not in {
                "registration_ref",
                "registration_fingerprint",
                "event_level",
                "origin_outcome_refs",
                "parent_registration_ref",
            }
        }
        cluster["outcome_ref"] = binding["outcome_ref"]
        cluster["ruler_window_status"] = binding["ruler_window_status"]
        if "ruler_context_refs" in binding:
            cluster["ruler_context_refs"] = list(
                binding.get("ruler_context_refs") or ()
            )
        event_level = str(registered["event_level"])
        if event_level == "campaign_group":
            cluster["settlement_scope"] = "ruler_campaign_parent"
        elif event_level == "campaign_subresult":
            cluster["settlement_scope"] = "person_campaign_subresult"
            parent_registration_ref = str(registered["parent_registration_ref"])
            parent_outcome_ref = outcome_ref_by_registration.get(parent_registration_ref)
            if parent_outcome_ref is None:
                raise ValueError(f"窗口绑定缺少人物子战役父级: {registration_ref}")
            cluster["parent_outcome_ref"] = parent_outcome_ref
        elif event_level == "macro_public_result":
            cluster["settlement_scope"] = "reign_macro_outcome"
        else:
            cluster["settlement_scope"] = (
                "person_governance_result"
                if binding["ruler_window_status"] == "outside_window"
                else "governance_result"
            )
        talent_credits = binding.get("campaign_talent_credits") or {}
        members = []
        for registered_member in registered["members"]:
            member = dict(registered_member)
            sovereign_relation = member.pop("sovereign_relation", None)
            actor_ref = str(member["actor_ref"])
            member["actor_kind"] = "ruler" if actor_ref == ruler_ref else "person"
            if registered["outcome_kind"] == "campaign":
                if actor_ref not in talent_credits:
                    raise ValueError(
                        f"战役窗口绑定缺少人物信用: {registration_ref}/{actor_ref}"
                    )
                member["talent_credit"] = talent_credits[actor_ref]
                if sovereign_relation is not None:
                    member["ruler_campaign_relation"] = sovereign_relation
            members.append(member)
        cluster["members"] = members
        cluster["semantic_fingerprint"] = cluster_semantic_fingerprint(cluster)
        clusters.append(cluster)
    clusters.sort(key=lambda row: str(row["outcome_ref"]))
    return {
        "schema_version": "historical-outcome-cluster-registry-v1",
        "status": binding_report["projected_registry_status"],
        "clusters": clusters,
    }


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    replacement = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    replacement.write_text(content, encoding="utf-8", newline="\n")
    os.replace(replacement, path)


def write_current_outcome_layers(workspace_root: Path) -> dict[str, Any]:
    """Publish unbound outcomes first, then isolated ruler bindings."""

    workspace_root = workspace_root.resolve()
    project = yaml.safe_load(
        (workspace_root / "config/project.yml").read_text(encoding="utf-8")
    )
    configured = (project.get("i5b_current_value") or {}).get("rulers") or {}
    configured_packs = []
    for ruler_name, ruler_config in configured.items():
        if not isinstance(ruler_config, Mapping):
            continue
        source_path = workspace_root / str(ruler_config["source_pack"])
        source_pack = json.loads(source_path.read_text(encoding="utf-8"))
        configured_packs.append((str(ruler_name), ruler_config, source_pack))
    if not configured_packs:
        raise ValueError("当前配置没有可汇总的成果 source pack")
    registry = build_unbound_historical_outcome_registry(
        [row[2] for row in configured_packs]
    )
    registry_config = project.get("historical_outcome_registry") or {}
    output_json = workspace_root / str(
        registry_config.get("current_json")
        or "eval/historical_outcome_registry/current.json"
    )
    output_markdown = workspace_root / str(
        registry_config.get("current_markdown")
        or "eval/historical_outcome_registry/current.md"
    )
    prepared_bindings = []
    for ruler_name, ruler_config, source_pack in configured_packs:
        binding = build_ruler_outcome_bindings(source_pack, registry)
        materialized = materialize_ruler_outcome_registry(registry, binding)
        if materialized != source_pack["outcome_registry"]:
            raise ValueError(f"{ruler_name} 窗口绑定无法无损还原当前成果投影")
        binding_path = ruler_config.get("outcome_binding")
        if not binding_path:
            raise ValueError(f"{ruler_name} 缺少 outcome_binding 配置")
        binding_output = workspace_root / str(binding_path)
        prepared_bindings.append((ruler_name, binding_output, binding))

    _atomic_text(
        output_json,
        json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    _atomic_text(
        output_markdown,
        render_unbound_historical_outcome_registry_markdown(registry),
    )
    binding_paths = {}
    for ruler_name, binding_output, binding in prepared_bindings:
        _atomic_text(
            binding_output,
            json.dumps(binding, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
        binding_paths[ruler_name] = str(binding_output)
    return {
        "registry": registry,
        "registry_json": str(output_json),
        "registry_markdown": str(output_markdown),
        "binding_paths": binding_paths,
    }


def _members_text(members: Sequence[Mapping[str, Any]]) -> str:
    values = []
    for member in members:
        relation = member.get("sovereign_relation")
        suffix = f"；皇权角色={relation}" if relation else ""
        values.append(
            f"{member['actor_name']}（{member['role_code']}{suffix}；"
            f"{member['contribution_scope']}）"
        )
    return "、".join(values)


def _period_text(period: Mapping[str, Any]) -> str:
    start = str(period.get("start") or "")
    end = str(period.get("end") or "")
    return start if not end or end == start else f"{start}—{end}"


def _escape(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_unbound_historical_outcome_registry_markdown(
    registry: Mapping[str, Any],
) -> str:
    declarations = registry["declarations"]
    lines = [
        "# 战役与治理成果总登记（未绑定皇帝窗口）",
        "",
        "> 本表只审成果本体。皇帝窗口、规则材料、人才信用和计分均未投影。",
        "",
        f"- 总成果：{declarations['outcome_count']}",
        f"- 战役：{declarations['campaign_count']}",
        f"- 治理：{declarations['governance_count']}",
        f"- 窗口绑定：{declarations['window_binding_count']}",
        f"- 规则材料：{declarations['rule_evidence_unit_count']}",
        f"- 计分贡献：{declarations['score_contribution_count']}",
        "",
    ]
    if registry.get("conflicts"):
        lines.extend(["## 待归并冲突", ""])
        for conflict in registry["conflicts"]:
            lines.append(
                f"- `{conflict['independent_key']}`：{conflict['reason']}"
            )
        lines.append("")

    campaigns = [
        row for row in registry["outcomes"] if row["outcome_kind"] == "campaign"
    ]
    lines.extend(
        [
            "## 战役登记",
            "",
            "| 登记号 | 战役成果 | 层级 | 时段 | 等级与依据 | 土地轴 | 对手轴 | 结果轴 | 过程负面及归责 | 参与者责任 | 已实现结果 | 史源 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in campaigns:
        payload = row["payload"]
        attributions = "、".join(
            f"{item.get('actor_name') or '外部因素'}:{item['responsibility']}({item['basis']})"
            for item in payload.get("process_adversity_attributions") or ()
        ) or "无"
        adverse = (
            f"{payload['process_adversity']} / N={payload['process_adversity_index']}；"
            f"{payload['process_adversity_basis']}；{attributions}"
        )
        result = f"{payload['battle_result']} / {payload['objective_completion']}"
        opponent = (
            f"{payload['opponent_strategic_weight']} / "
            f"{payload['opponent_condition']}"
        )
        lines.append(
            "| "
            + " | ".join(
                _escape(value)
                for value in (
                    row["registration_ref"],
                    row["canonical_label"],
                    row["event_level"],
                    _period_text(row["period"]),
                    f"{payload['campaign_tier']}；{payload['campaign_tier_basis']}",
                    payload["land_strategic_value"],
                    opponent,
                    result,
                    adverse,
                    _members_text(row["members"]),
                    row["observable_result"],
                    "、".join(row["source_refs"]),
                )
            )
            + " |"
        )

    governance = [
        row for row in registry["outcomes"] if row["outcome_kind"] == "governance"
    ]
    lines.extend(
        [
            "",
            "## 治理登记",
            "",
            "| 登记号 | 治理成果 | 类型 | 时段 | 规模 | 因果归责 | 参与者责任 | 已实现结果 | 限制 | 史源 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in governance:
        payload = row["payload"]
        scale = row["scale"]
        lines.append(
            "| "
            + " | ".join(
                _escape(value)
                for value in (
                    row["registration_ref"],
                    row["canonical_label"],
                    row["event_level"],
                    _period_text(row["period"]),
                    f"{scale['level']} / {scale['consequence_basis']}；{scale['reason']}",
                    payload["causal_attribution_status"],
                    _members_text(row["members"]),
                    row["observable_result"],
                    "；".join(row["limitations"]) or "无",
                    "、".join(row["source_refs"]),
                )
            )
            + " |"
        )
    return "\n".join(lines) + "\n"
