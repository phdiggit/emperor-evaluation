from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import yaml

from emperor_v4.contracts.boundary import RuleEvidenceMember
from emperor_v4.contracts.episode import AssertionLink, EpisodeParticipant, HistoricalEpisodePacket
from emperor_v4.evaluation.i5b_material_budget_scored_shadow import (
    APPOINTMENT_FACTORS,
    FACTOR_NAMES,
    ROOT,
    build_i5b_material_budget_shadow,
)
from emperor_v4.persistence.core_registry import RuleEvidenceUnitRecord


SCHEMA_VERSION = "i5b-current-value-report-v1"
SOURCE_PACK_SCHEMA_VERSION = "i5b-current-value-source-pack-v1"
RULES = ("talent_discovery", "appointment_delegation", "tolerate_talent", "anti_nepotism")


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: object, length: int | None = None) -> str:
    result = hashlib.sha256(_canonical(value)).hexdigest()
    return result[:length] if length else result


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON 顶层必须是对象: {path}")
    return value


def _policy_values(policy: Mapping[str, Any], rule: str, options: Mapping[str, str]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for name, option in options.items():
        catalog = policy["evidence_factor"].get(name)
        if catalog is None:
            catalog = policy["rules"][rule].get(name)
        if not isinstance(catalog, Mapping) or option not in catalog:
            raise ValueError(f"{rule}.{name} 未知语义选项: {option}")
        values[name] = catalog[option]
    return values


def _required_factor_names(rule: str, direction: str) -> tuple[str, ...]:
    if rule == "appointment_delegation":
        return APPOINTMENT_FACTORS
    return FACTOR_NAMES[rule][direction]


def _episode_and_reu(
    *, material: Mapping[str, Any], facts: Mapping[str, Mapping[str, Any]], ruler: str
) -> tuple[HistoricalEpisodePacket, RuleEvidenceUnitRecord]:
    fact_rows = [facts[str(ref)] for ref in material["fact_refs"]]
    assertion_links: list[AssertionLink] = []
    source_refs: set[str] = set()
    for fact in fact_rows:
        page = str(fact["source_page"])
        revision = str(fact["revision_ref"])
        for index, assertion in enumerate(fact.get("assertions") or (), start=1):
            anchor = str(assertion.get("locator_anchor") or index)
            quote = str(assertion["exact_quote"])
            passage_ref = "SP-" + _digest(
                {"page": page, "revision": revision, "anchor": anchor, "quote": quote}, 20
            ).upper()
            assertion_ref = str(assertion.get("assertion_ref") or "AS-" + _digest({"passage": passage_ref, "fact": assertion["fact"]}, 20).upper())
            source_refs.add(f"{page}@{revision}#{anchor}")
            assertion_links.append(
                AssertionLink(
                    assertion_ref=assertion_ref,
                    source_passage_ref=passage_ref,
                    relation="supports",
                    supported_fields=("identity", "action", "responsibility", "outcome"),
                    evidence_status="accepted",
                    representative=index == 1,
                )
            )
    if not assertion_links:
        raise ValueError(f"{material['material_id']} 没有可接受 Assertion")
    uncertainties = tuple([str(material["remaining_gap"])]) if material.get("remaining_gap") else ()
    episode_semantic = _digest(
        {
            "person_ref": material["person_ref"],
            "facts": material["fact_refs"],
            "action": material["episode_action"],
            "responsibility": material["episode_responsibility"],
            "outcomes": material["episode_outcomes"],
        }
    )
    reu_semantic = _digest(
        {
            "episode_semantic": episode_semantic,
            "rule": material["rule_code"],
            "direction": material["direction"],
            "independence_key": material["independence_key"],
        }
    )
    episode_id = "EP-" + episode_semantic[:20].upper()
    dates = [str(row.get("date") or "") for row in fact_rows if row.get("date")]
    episode = HistoricalEpisodePacket(
        episode_id=episode_id,
        episode_type="ruler_person_governance_event",
        episode_status="accepted_with_uncertainty" if uncertainties else "accepted",
        evaluation_context=str(material["person_ref"]),
        semantic_fingerprint=episode_semantic,
        time_start="；".join(dates) or None,
        time_end=None,
        time_precision="source_expression" if dates else "unknown",
        locations=(),
        participants=(EpisodeParticipant(person_ref=str(material["person_ref"]), role_codes=("subject",), role_status="resolved"),),
        action=str(material["episode_action"]),
        responsibility=str(material["episode_responsibility"]),
        outcome=tuple(str(value) for value in material["episode_outcomes"]),
        consequence=tuple(str(value) for value in material["episode_outcomes"]),
        assertion_links=tuple(assertion_links),
        conflicts=(),
        uncertainties=uncertainties,
        completeness={
            "identity": "complete",
            "time": "complete" if dates else "partial",
            "action": "complete",
            "responsibility": "complete",
            "outcome": "complete",
            "consequence": "complete",
            "source_diversity": "complete" if len(source_refs) > 1 else "partial",
            "conflict_resolution": "not_applicable",
        },
        lineage={"fact_refs": ";".join(str(ref) for ref in material["fact_refs"]), "source_refs": ";".join(sorted(source_refs))},
        provenance={"ruler": ruler, "source_unit_code": str(material["source_unit_code"]), "mode": "current_shadow"},
    )
    unit_ref = "REU-" + reu_semantic[:20].upper()
    reu = RuleEvidenceUnitRecord(
        unit_ref=unit_ref,
        rule_code=str(material["rule_code"]),
        evaluation_context=str(material["person_ref"]),
        direction=str(material["direction"]),
        semantic_fingerprint=reu_semantic,
        status="accepted_shadow",
        payload={
            "independence_key": material["independence_key"],
            "judge_reason": material["judge_reason"],
            "factor_option_codes": dict(material["factor_option_codes"]),
        },
        members=(RuleEvidenceMember(member_ref=episode_id, member_type="episode", member_role="core_evidence"),),
    )
    return episode, reu


def build_i5b_current_value(source_pack_path: Path) -> dict[str, Any]:
    source_pack_path = source_pack_path.resolve()
    pack = _load_json(source_pack_path)
    if pack.get("schema_version") != SOURCE_PACK_SCHEMA_VERSION:
        raise ValueError("current source pack schema_version 不匹配")
    declared_hash = str(pack.get("source_pack_sha256") or "")
    unsigned_pack = dict(pack)
    unsigned_pack.pop("source_pack_sha256", None)
    if declared_hash != _digest(unsigned_pack):
        raise ValueError("current source pack sha256 不匹配")
    three_channel = pack.get("three_channel_input") or {}
    channel_counts = three_channel.get("channel_counts") or {}
    if set(channel_counts) != {"ruler_chronicle", "person_biography", "dynasty_governance"} or any(int(value) <= 0 for value in channel_counts.values()):
        raise ValueError("current source pack 未闭合三路中性材料")
    dispositions = pack.get("three_channel_disposition") or {}
    if set(dispositions) != set(channel_counts):
        raise ValueError("current source pack 三路处置不闭合")
    if len(pack.get("ruler_context_materials") or ()) != int(dispositions["ruler_chronicle"]["ruler_window_context_count"]):
        raise ValueError("皇帝篇章 supporting context 数量不一致")
    if len(pack.get("governance_achievements") or ()) != int(dispositions["dynasty_governance"]["ruler_window_achievement_count"]):
        raise ValueError("朝代文治成果处置数量不一致")
    if pack.get("declarations", {}).get("formal_write") is not False:
        raise ValueError("current source pack 不得授权正式写入")

    policy_path = ROOT / str(pack["factor_acceptance"]["policy_ref"])
    policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    facts = {str(row["record_ref"]): row for row in pack.get("facts") or ()}
    materials = list(pack.get("materials") or ())
    material_ids = [str(row["material_id"]) for row in materials]
    if len(material_ids) != len(set(material_ids)):
        raise ValueError("current source pack material_id 重复")
    episode_by_id: dict[str, HistoricalEpisodePacket] = {}
    reus = []
    direct_by_rule: dict[str, list[dict[str, Any]]] = {rule: [] for rule in RULES}
    eligible_by_rule: dict[str, dict[str, list[dict[str, str]]]] = {
        rule: {"positive": [], "negative": []} for rule in RULES
    }
    for material in materials:
        rule = str(material["rule_code"])
        direction = str(material["direction"])
        if rule not in RULES or direction not in {"positive", "negative"}:
            raise ValueError(f"材料规则或方向非法: {material['material_id']}")
        unknown_facts = sorted(set(str(ref) for ref in material["fact_refs"]) - set(facts))
        if unknown_facts:
            raise ValueError(f"{material['material_id']} 引用未知当前事实: {unknown_facts}")
        options = dict(material["factor_option_codes"])
        required = set(_required_factor_names(rule, direction))
        if set(options) != required:
            raise ValueError(f"{material['material_id']} 因子集合不闭合")
        values = _policy_values(policy, rule, options)
        declared_values = {name: str(value) for name, value in (material.get("factor_values") or {}).items()}
        mapped_values = {name: str(value) for name, value in values.items()}
        if declared_values != mapped_values:
            raise ValueError(f"{material['material_id']} 数值不是政策确定性映射")
        episode, reu = _episode_and_reu(material=material, facts=facts, ruler=str(pack["ruler"]))
        existing_episode = episode_by_id.setdefault(episode.episode_id, episode)
        if existing_episode != episode:
            raise ValueError(f"Episode 语义指纹冲突: {episode.episode_id}")
        reus.append(reu)
        source_refs = sorted({
            f"{facts[str(ref)]['source_page']}@{facts[str(ref)]['revision_ref']}"
            for ref in material["fact_refs"]
        })
        direct_by_rule[rule].append(
            {
                "material_id": material["material_id"],
                "subject": material["subject"],
                "object_ref": material["person_ref"],
                "side": direction,
                "factor_values": values,
                "factor_option_codes": options,
                "fact": material["fact_summary"],
                "rule_evidence_unit_ref": reu.unit_ref,
                "source_refs": source_refs,
            }
        )
        eligible_by_rule[rule][direction].append(
            {
                "material_id": str(material["material_id"]),
                "independence_key": str(material["independence_key"]),
                "judge_reason": str(material["judge_reason"]),
            }
        )

    manifest = {
        "schema_version": "i5b-material-budget-shadow-manifest-v1",
        "task_code": f"I5B-CURRENT-{_digest({'pack': declared_hash, 'policy': policy}, 16).upper()}",
        "ruler": pack["ruler"],
        "ruler_ref": pack["ruler_ref"],
        "window": pack["window"],
        "policy": pack["factor_acceptance"]["policy_ref"],
        "settlement_mode": "policy_budget",
        "rules": {},
    }
    for rule in RULES:
        manifest["rules"][rule] = {
            "source": str(source_pack_path),
            "direct_materials": direct_by_rule[rule],
            "eligible": eligible_by_rule[rule],
            "excluded": [],
        }
    team = pack["team"]
    governance_by_ref = {
        str(row["achievement_ref"]): row
        for row in pack.get("governance_achievements") or ()
    }
    team_governance_refs = [
        str(value) for value in team.get("governance_achievement_refs") or ()
    ]
    unknown_governance = sorted(set(team_governance_refs) - set(governance_by_ref))
    if unknown_governance:
        raise ValueError(f"团队 REU 引用未知治理成果: {unknown_governance}")
    governance_results = [
        {
            "result": governance_by_ref[ref]["payload"]["observable_result"],
            "source_refs": governance_by_ref[ref]["payload"]["source_refs"],
            "governance_achievement_ref": ref,
        }
        for ref in team_governance_refs
    ]
    manifest["rules"]["team_building"] = {
        "source": str(source_pack_path),
        "positive_members": team["positive_members"],
        "negative_members": team["negative_members"],
        "functional_complementarity": team["functional_complementarity"],
        "long_term_stability": team["long_term_stability"],
        "remaining_member_judge_reason": "当前人物画像与窗口风险冻结后未进入正8/负3的成员仅作支持。",
        "governance_results": governance_results,
    }
    budget = build_i5b_material_budget_shadow(source_pack_path, manifest_payload=manifest)
    team_semantic = _digest(
        {
            "ruler_ref": pack["ruler_ref"],
            "positive_members": team["positive_members"],
            "negative_members": team["negative_members"],
            "governance_achievement_refs": team_governance_refs,
            "functional_complementarity": team["functional_complementarity"],
            "long_term_stability": team["long_term_stability"],
        }
    )
    team_reu = RuleEvidenceUnitRecord(
        unit_ref="REU-TEAM-" + team_semantic[:16].upper(),
        rule_code="team_building",
        evaluation_context=str(pack["ruler_ref"]),
        direction="net",
        semantic_fingerprint=team_semantic,
        status="accepted_shadow",
        payload={
            "positive_members": list(team["positive_members"]),
            "negative_members": list(team["negative_members"]),
            "functional_complementarity": team["functional_complementarity"],
            "long_term_stability": team["long_term_stability"],
            "ruler_context_inventory_fingerprint": _digest(pack["ruler_context_materials"]),
        },
        members=(
            RuleEvidenceMember(
                member_ref="TEAM-CONTEXT-" + team_semantic[:16].upper(),
                member_type="aggregate_context",
                member_role="team_window",
            ),
            *tuple(
                RuleEvidenceMember(
                    member_ref=ref,
                    member_type="governance_achievement",
                    member_role="governance_result_support",
                )
                for ref in team_governance_refs
            ),
        ),
    )
    episodes = sorted(episode_by_id.values(), key=lambda value: value.episode_id)
    by_person: dict[str, list[str]] = {}
    fact_owner = {str(row["person_ref"]): str(row["canonical_name"]) for row in facts.values()}
    for episode in episodes:
        by_person.setdefault(fact_owner[episode.evaluation_context], []).append(episode.episode_id)
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "current_shadow_chain_complete",
        "ruler": pack["ruler"],
        "ruler_ref": pack["ruler_ref"],
        "window": pack["window"],
        "source_pack_ref": str(source_pack_path.relative_to(ROOT)),
        "source_pack_sha256": declared_hash,
        "three_channel_input": three_channel,
        "three_channel_disposition": dispositions,
        "judge_coverage": pack["judge_coverage"],
        "episodes": [asdict(value) for value in episodes],
        "episode_index_by_person": {name: sorted(ids) for name, ids in sorted(by_person.items())},
        "rule_evidence_units": [asdict(value) for value in (*reus, team_reu)],
        "excluded_units": pack["excluded_units"],
        "material_budget": budget,
        "net_signal": budget["summary"]["weighted_raw_signal"],
        "declarations": {
            "current_value_only": True,
            "three_channel_materials_consumed": True,
            "episode_count": len(episodes),
            "rule_evidence_unit_count": len(reus) + 1,
            "external_retrieval_count": 0,
            "runtime_model_call_count": 0,
            "database_write_count": 0,
            "formal_score_write_count": 0,
            "score_45": None,
            "tier": None,
            "ranking": None,
        },
    }
    report["report_sha256"] = _digest(report)
    return report


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        f"# {report['ruler']} I5B 当前值影子结果",
        "",
        f"- 三路输入指纹：`{report['three_channel_input']['fingerprint']}`",
        f"- Episode：`{report['declarations']['episode_count']}`；REU：`{report['declarations']['rule_evidence_unit_count']}`",
        f"- 加权净信号：`{report['net_signal']}`",
        "- 45 分、档位和排名：未生成。",
        "",
        "## 五条规则",
        "",
        "| 规则 | 正向 | 负向 | 净信号 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for rule in report["material_budget"]["rules"]:
        lines.append(f"| {rule['rule_label']} | {rule['positive_signal']} | {rule['negative_signal']} | {rule['rule_raw_net']} |")
    lines.extend(["", "## 各臣子 Episode", ""])
    episode_by_id = {row["episode_id"]: row for row in report["episodes"]}
    rules_by_episode: dict[str, set[str]] = {}
    for reu in report["rule_evidence_units"]:
        for member in reu["members"]:
            if member["member_type"] == "episode":
                rules_by_episode.setdefault(member["member_ref"], set()).add(
                    reu["rule_code"]
                )
    for person, ids in report["episode_index_by_person"].items():
        lines.append(f"### {person}")
        lines.append("")
        for episode_id in ids:
            episode = episode_by_id[episode_id]
            rule_labels = "、".join(sorted(rules_by_episode[episode_id]))
            lines.append(f"- `{episode_id}`（{rule_labels}）：{episode['action']}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the current-only I5B neutral-material shadow chain")
    parser.add_argument("--source-pack", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    args = parser.parse_args()
    report = build_i5b_current_value(args.source_pack)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.output_markdown.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"ruler": report["ruler"], "status": report["status"], "episode_count": report["declarations"]["episode_count"], "reu_count": report["declarations"]["rule_evidence_unit_count"], "net_signal": report["net_signal"], "report_sha256": report["report_sha256"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
