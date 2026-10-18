"""Verify current C5 admissions from local, ruler-scoped evidence.

This checks necessary conditions. Historical peak ability remains an authored
judgment; passing a count never assigns a grade or changes a score here.
"""
from typing import Any, Mapping

SCHEMA = "third-item-c-five-gate-v1"
SIGNIFICANT_TIERS = {"A", "S-", "S", "S+"}
HIGH_OPPONENT_GRADES = {"O4", "O5", "O6"}


def verify_five_gate(
    row: Mapping[str, Any],
    systems: Mapping[str, Mapping[str, Any]],
    profiles: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    axes = {"C1": "combat_delivery_grade", "C2": "operational_sustainability_cap",
            "C3": "system_reliability_cap"}
    requested = {a for a, field in axes.items() if row.get(field) == f"{a}-5"}
    gate = row.get("c5_axis_gate") or {}
    if gate.get("schema_version") != SCHEMA:
        if requested:
            raise ValueError(f"{row.get('ruler_name')}五档缺少当前逐项资格记录")
        return {"status": "NOT_REQUESTED"}

    chain_rows = {c["chain_id"]: c for c in
                  list(row.get("strategy_chains") or ()) +
                  list(row.get("capability_only_strategy_chains") or ())}
    admitted: dict[str, set[str]] = {}
    for entry in gate.get("C1_O4_plus_opponent_systems") or ():
        ref = entry["opponent_system_ref"]
        system = systems.get(ref)
        if system is None:
            raise ValueError("五档对手未在公共O库登记")
        accepted = set()
        for cid in entry.get("task_refs") or ():
            if cid not in chain_rows:
                raise ValueError("五档样本不是本人当前或能力专用战略链")
            chain = chain_rows[cid]
            windows = [w for w in system.get("window_assessments", {}).values()
                       if w.get("subject_ruler_id") == row.get("ruler_id")
                       and cid in w.get("source_chain_refs", [])]
            if windows:
                valid = any(w.get("organization_grade") in HIGH_OPPONENT_GRADES
                            for w in windows)
            else:
                refs = set(chain.get("source_event_refs") or ()) | set(
                    chain.get("source_parent_refs") or ()) | set(
                    chain.get("member_parent_refs") or ())
                refs.update(chain[key] for key in ("canonical_strategy_ref", "canonical_parent_ref")
                            if chain.get(key))
                valid = (system.get("organization_grade") in HIGH_OPPONENT_GRADES
                         and bool(refs & set(system.get("source_campaign_refs") or ())))
            if not valid:
                raise ValueError(f"五档对手实际窗口未核准，不得借用母体或他人高档：{row.get('ruler_name')}/{cid}/{ref}")
            accepted.add(cid)
        if accepted:
            admitted.setdefault(ref, set()).update(accepted)
    high_chains = set().union(*admitted.values()) if admitted else set()

    directions = set()
    for entry in gate.get("C2_O4_plus_strategic_directions") or ():
        refs = set(entry.get("opponent_system_refs") or ())
        cids = set(entry.get("task_refs") or ())
        if not refs or not cids or not cids <= high_chains or not refs <= set(admitted):
            raise ValueError("五档战略方向缺少本人已核高难任务")
        if not all(cids & admitted[ref] for ref in refs):
            raise ValueError("五档战略方向与对手任务不对应")
        if entry.get("direction"):
            directions.add(entry["direction"])

    commander_refs = set()
    for entry in gate.get("C3_top_commander_deliveries") or ():
        profile = profiles.get(entry.get("profile_ref"))
        if not profile or profile.get("military_grade") not in {"top", "historic"}:
            raise ValueError("五档将领未达正式人才等级")
        if profile.get("person") == row.get("ruler_name"):
            raise ValueError("统治者不得充作自己的部将资格")
        if (entry.get("subject_ruler_id") != row.get("ruler_id")
                or not entry.get("own_window_basis")):
            raise ValueError("五档将领成果缺少本人的有效窗口与归属裁决")
        results = {a["campaign_ref"]: a for a in profile.get("consumed_achievements") or ()}
        refs = list(entry.get("achievement_refs") or ())
        if not refs or any(ref not in results or
                           results[ref].get("campaign_tier") not in SIGNIFICANT_TIERS or
                           results[ref].get("result_direction") != "positive" for ref in refs):
            raise ValueError("五档将领未有本任A级及以上本人正向成果")
        commander_refs.add(profile["profile_ref"])

    failures = {c["chain_id"] for c in chain_rows.values() if c.get("major_system_failure")}
    outcome = gate.get("major_outcome_review") or {}
    zero_failure_reviewed = (outcome.get("failure_review_status") == "REVIEWED_ZERO"
                             and bool(outcome.get("failure_review_basis")))
    common = len(high_chains) >= 3
    passed = {"C1": common and len(admitted) >= 2 and not failures and zero_failure_reviewed,
              "C2": common and len(admitted) >= 2 and len(directions) >= 2
                    and not gate.get("logistics_group_collapse_refs"),
              "C3": common and len(commander_refs) >= 2}
    for axis in requested:
        current_successes = {c['chain_id'] for c in row.get('strategy_chains', ())
                             if c.get('major_system_success')}
        revalidation = gate.get('current_major_success_revalidation', {}).get(axis) or {}
        refs = set(revalidation.get('chain_refs') or ())
        if (not refs or not refs <= current_successes or not refs <= high_chains
                or revalidation.get('status') != 'PASSED' or not revalidation.get('basis')):
            raise ValueError(f"{row.get('ruler_name')}{axis}缺第三项本体重大体系胜绩复验，统一链只能建立五档候选")
        if any(chain_rows[cid].get('war_classification') == 'ORDINARY_INTERNAL_WAR' for cid in refs):
            raise ValueError('普通平乱不得充作高难本体重大体系胜绩复验')
        if any(chain_rows[cid].get('war_classification') != 'EXTERNAL_WAR' for cid in refs):
            raise ValueError('五档须由已明确分类的对外战争重大体系胜绩复验，内部平乱或未分类不能代替')
        if axis == 'C1' and failures:
            raise ValueError('C1五档不得有完整战略链上的重大体系失败')
        if axis == 'C1' and not zero_failure_reviewed:
            raise ValueError('C1五档缺少零重大体系失败的明确复核')
        if not passed[axis] or gate.get("axis_status", {}).get(axis) != "PASSED":
            raise ValueError(f"{row.get('ruler_name')}{axis}五档必要门未通过")
        finding = gate.get("axis_ability_review", {}).get(axis) or {}
        if finding.get("grade") != 5 or not finding.get("basis"):
            raise ValueError("资格数量通过不能代替五档能力事实裁定")
    if row.get("final_grade") == "C-5":
        outcome = gate.get("major_outcome_review") or {}
        if outcome.get("failure_review_status") != "REVIEWED_ZERO" or not outcome.get("failure_review_basis"):
            raise ValueError("最终五档缺少零重大体系失败的明确复核")
        successes = {c["chain_id"] for c in chain_rows.values() if c.get("major_system_success")}
        if len(successes) < 3 or failures or not all(passed.values()):
            raise ValueError("最终五档未满足重大成果、无重大体系失败及三轴条件")
    return {"status": "PASS", "high_chain_count": len(high_chains),
            "opponent_system_count": len(admitted), "commander_count": len(commander_refs),
            "necessary_axis_gates": passed}
