from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v2_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v2_import_plan import ImportPlanError, write_json  # noqa: E402
from scripts.dev import retrieval_v2_object_consumer as object_consumer  # noqa: E402
from scripts.dev import retrieval_v2_person_context_consumer as context_consumer  # noqa: E402
from scripts.dev import retrieval_v2_person_profile_consumer as profile_consumer  # noqa: E402
from scripts.dev import retrieval_v2_target_person_consumer as target_person_consumer  # noqa: E402


STAGES = ("completion",)
READINESS_SCOPES = ("active-targets", "accepted-packs")
RULES_REQUIRING_TALENT_GRADE = {"team_building", "talent_discovery", "appointment_delegation", "tolerate_talent"}
DEFAULT_CLUSTER_FORMULA = "evidence_cluster_signal_v3"

REASON_CATALOG: dict[str, dict[str, str]] = {
    "missing_talent_grade": {
        "owner": "agent_or_human",
        "severity_default": "warning",
        "description": "人物缺人才等级；需依据正史、史论、后世史书或现代研究的评价共识生成候选，不能由 consumer 临场定级。",
    },
    "missing_person_role": {
        "owner": "agent_or_human",
        "severity_default": "warning",
        "description": "人物缺身份阶段；需要判定皇帝、臣子、将领、亲王等阶段身份，代码不能猜。",
    },
    "missing_person_affiliation": {
        "owner": "agent_or_human",
        "severity_default": "warning",
        "description": "人物缺朝代、政权、任仕、出身或派系归属；跨朝人物需要智能体或人工拆阶段。",
    },
    "missing_name_variant": {
        "owner": "agent_or_human",
        "severity_default": "warning",
        "description": "人物缺字、号、谥号、庙号或可用别名来源；consumer 只写确定名称，不猜称谓。",
    },
    "ambiguous_identity": {
        "owner": "human",
        "severity_default": "blocking",
        "description": "对象身份有同名、别名或重复画像风险；必须复核后才能合并或入分。",
    },
    "conflicting_old_talent_grade": {
        "owner": "human",
        "severity_default": "blocking",
        "description": "旧库同一人物命中多个不同人才等级；consumer 不自动选择。",
    },
    "unsupported_talent_grade": {
        "owner": "human",
        "severity_default": "blocking",
        "description": "旧库或候选中出现新库枚举外的人才等级；需要扩展枚举或人工改写。",
    },
    "cross_rule_candidate_unresolved": {
        "owner": "agent_or_human",
        "severity_default": "warning",
        "description": "claim 可能关联其他 rule，但目标 rule contract 或语境未解析，先保留候选。",
    },
    "claim_scoring_decision_required": {
        "owner": "human",
        "severity_default": "downstream",
        "description": "claim 是否入分、只作上下文或排除，需要规则语境和人工/智能体验收。",
    },
    "factorization_required": {
        "owner": "agent_or_human",
        "severity_default": "downstream",
        "description": "可计分材料还需选择规则表因子，consumer 不算分。",
    },
    "rule_score_required": {
        "owner": "agent_or_human",
        "severity_default": "downstream",
        "description": "已因子化材料还需生成规则信号聚合；先跑 retrieval_v2_rule_scorer，再进入跨 rule 汇总。",
    },
    "accepted_missing_required": {
        "owner": "human",
        "severity_default": "warning",
        "description": "若确认某缺口暂不补，需显式登记 accepted_missing，不能静默跳过。",
    },
    "missing_target_emperor_profile": {
        "owner": "agent_or_human",
        "severity_default": "blocking",
        "description": "控制面目标皇帝缺 person object 或人物画像；必须先补成目标人物，不能只存在 retrieval_targets。",
    },
    "material_review_pending": {
        "owner": "human",
        "severity_default": "blocking",
        "description": "材料复核队列仍有 ready 或 needs_review 项；必须写入具体复核结论后才能进入入分或因子化。",
    },
}


def _count(payload: Mapping[str, Any], *path: str) -> int:
    value: Any = payload
    for key in path:
        value = value.get(key) if isinstance(value, Mapping) else None
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def reason_entry(code: str, *, count: int, severity: str | None = None, message: str = "") -> dict[str, Any]:
    catalog = REASON_CATALOG[code]
    return {
        "code": code,
        "severity": severity or catalog["severity_default"],
        "owner": catalog["owner"],
        "count": int(count),
        "description": catalog["description"],
        "message": message,
    }


def build_completion_worklists(
    target_report: Mapping[str, Any],
    object_report: Mapping[str, Any],
    profile_report: Mapping[str, Any],
    context_report: Mapping[str, Any],
) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    agent_tasks: list[dict[str, Any]] = []

    object_blockers = list(object_report.get("blockers") or [])
    if object_blockers:
        blockers.append(reason_entry("ambiguous_identity", count=len(object_blockers), message="对象队列存在无法自动接受的身份项。"))

    conflicting = _count(profile_report, "totals", "conflicting_old_talent_quality")
    if conflicting:
        blockers.append(reason_entry("conflicting_old_talent_grade", count=conflicting))

    unsupported = _count(profile_report, "totals", "unsupported_old_talent_quality")
    if unsupported:
        blockers.append(reason_entry("unsupported_talent_grade", count=unsupported))

    missing_talent = _count(profile_report, "totals", "missing_old_talent_quality")
    if missing_talent:
        warnings.append(reason_entry("missing_talent_grade", count=missing_talent))
        agent_tasks.append(
            {
                "code": "missing_talent_grade",
                "items": list(profile_report.get("review_needed") or []),
                "handoff": "交给智能体按正史、史论、后世史书和现代研究评价共识补人才等级候选。",
            }
        )

    missing_roles = _count(context_report, "totals", "missing_role_candidate")
    if missing_roles:
        warnings.append(reason_entry("missing_person_role", count=missing_roles, message="材料角色无法映射为人物身份候选，需人工或智能体复核。"))
        agent_tasks.append(
            {
                "code": "missing_person_role",
                "items": list((context_report.get("review_needed") or {}).get("missing_role_candidate") or []),
                "handoff": REASON_CATALOG["missing_person_role"]["description"],
            }
        )

    missing_affiliations = _count(context_report, "totals", "missing_target_period")
    if missing_affiliations:
        warnings.append(reason_entry("missing_person_affiliation", count=missing_affiliations, message="目标皇帝朝代未能从参考 emperor 表解析。"))
        agent_tasks.append(
            {
                "code": "missing_person_affiliation",
                "items": list((context_report.get("review_needed") or {}).get("missing_target_period") or []),
                "handoff": REASON_CATALOG["missing_person_affiliation"]["description"],
            }
        )

    missing_target_period = _count(target_report, "totals", "missing_emperor_period")
    if missing_target_period:
        warnings.append(reason_entry("missing_person_affiliation", count=missing_target_period, message="部分目标皇帝缺朝代参考，已写画像和皇帝身份，但朝代归属仍需补。"))
        agent_tasks.append(
            {
                "code": "missing_person_affiliation",
                "items": list((target_report.get("review_needed") or {}).get("missing_emperor_period") or []),
                "handoff": REASON_CATALOG["missing_person_affiliation"]["description"],
            }
        )

    warnings.append(reason_entry("missing_name_variant", count=0, message="canonical 和 script_variant 可自动消费；字、号、庙号、谥号需外部候选。"))

    return {
        "blockers": [item for item in blockers if item["count"] > 0],
        "warnings": [item for item in warnings if item["count"] > 0 or item["code"] == "missing_name_variant"],
        "agent_tasks": agent_tasks,
        "downstream_required": [
            reason_entry("claim_scoring_decision_required", count=0),
            reason_entry("factorization_required", count=0),
            reason_entry("accepted_missing_required", count=0),
        ],
    }


def execute_completion_stage(*, env_file: Path | None, dsn_env: str, old_dsn_env: str, execute: bool) -> dict[str, Any]:
    target_report = target_person_consumer.execute_target_person_consumer(
        env_file=env_file,
        dsn_env=dsn_env,
        old_dsn_env=old_dsn_env,
        item_code="I5B",
        execute=execute,
    )
    object_report = object_consumer.execute_object_consumer(env_file=env_file, dsn_env=dsn_env, execute=execute)
    profile_report = profile_consumer.execute_person_profile_consumer(
        env_file=env_file,
        dsn_env=dsn_env,
        old_dsn_env=old_dsn_env,
        execute=execute,
    )
    context_report = context_consumer.execute_person_context_consumer(
        env_file=env_file,
        dsn_env=dsn_env,
        old_dsn_env=old_dsn_env,
        execute=execute,
    )
    worklists = build_completion_worklists(target_report, object_report, profile_report, context_report)
    ok = (
        bool(target_report.get("ok"))
        and bool(object_report.get("ok"))
        and bool(profile_report.get("ok"))
        and bool(context_report.get("ok"))
        and not worklists["blockers"]
    )
    return {
        "generated_by": "scripts/dev/retrieval_v2_consumer.py",
        "command": "apply",
        "stage": "completion",
        "write_db": execute,
        "executed": execute,
        "ok": ok,
        "components": {
            "target_persons": target_report,
            "objects": object_report,
            "person_profiles": profile_report,
            "person_context": context_report,
        },
        "totals": {
            "target_emperor_profiles": _count(target_report, "totals", "profile_rows"),
            "target_emperor_roles": _count(target_report, "totals", "emperor_role_rows"),
            "missing_emperor_period": _count(target_report, "totals", "missing_emperor_period"),
            "object_queue_rows": _count(object_report, "totals", "queue_rows"),
            "auto_accepted_objects": _count(object_report, "totals", "auto_accepted_objects"),
            "profile_rows": _count(profile_report, "totals", "profile_rows"),
            "matched_old_talent_quality": _count(profile_report, "totals", "matched_old_talent_quality"),
            "missing_old_talent_quality": _count(profile_report, "totals", "missing_old_talent_quality"),
            "person_affiliation_rows": _count(context_report, "totals", "affiliation_rows"),
            "person_role_rows": _count(context_report, "totals", "role_rows"),
            "missing_role_candidate": _count(context_report, "totals", "missing_role_candidate"),
            "blockers": len(worklists["blockers"]),
            "warnings": len(worklists["warnings"]),
            "agent_task_groups": len(worklists["agent_tasks"]),
        },
        "worklists": worklists,
    }


def plan_consumer(
    *,
    env_file: Path | None,
    dsn_env: str,
    old_dsn_env: str,
    item_code: str,
    rule_code: str,
    scope: str,
) -> dict[str, Any]:
    completion = execute_completion_stage(env_file=env_file, dsn_env=dsn_env, old_dsn_env=old_dsn_env, execute=False)
    readiness = fetch_readiness_report(env_file=env_file, dsn_env=dsn_env, item_code=item_code, rule_code=rule_code, scope=scope)
    return {
        "generated_by": "scripts/dev/retrieval_v2_consumer.py",
        "command": "plan",
        "ok": completion["ok"] and readiness["ok"],
        "stages": list(STAGES),
        "selected_item_code": item_code,
        "selected_rule_code": rule_code,
        "scope": scope,
        "completion_dry_run": completion,
        "readiness": readiness,
        "cannot_do": list(REASON_CATALOG.values()),
    }


def fetch_scalar(cur: Any, sql: str, params: Sequence[Any] = ()) -> int:
    cur.execute(sql, params)
    row = cur.fetchone()
    return int((row or {}).get("n") or 0)


def target_scope_cte(scope: str) -> str:
    if scope == "accepted-packs":
        return """
            scoped_targets as (
                select distinct rt.id
                  from retrieval_v2.retrieval_targets rt
                  join retrieval_v2.source_packs sp on sp.target_id = rt.id
                 where sp.id in (
                        select distinct on (sp2.target_id, sp2.contract_id) sp2.id
                          from retrieval_v2.source_packs sp2
                         where sp2.status = 'accepted'
                           and sp2.coverage_status = 'passed'
                         order by sp2.target_id, sp2.contract_id, sp2.updated_at desc, sp2.id desc
                   )
                   and (%s = '' or rt.item_code = %s)
            )
        """
    if scope == "active-targets":
        return """
            scoped_targets as (
                select rt.id
                  from retrieval_v2.retrieval_targets rt
                 where rt.target_status = 'active'
                   and (%s = '' or rt.item_code = %s)
            )
        """
    raise ImportPlanError(f"unsupported readiness scope: {scope}")


def fetch_readiness_snapshot(cur: Any, *, item_code: str, rule_code: str = "", scope: str = "active-targets") -> dict[str, int]:
    params = (item_code, item_code)
    target_cte = target_scope_cte(scope)
    scope_cte = f"""
        with {target_cte},
        scoped_persons as (
            select distinct o.id
              from retrieval_v2.objects o
              join retrieval_v2.target_objects tob on tob.object_id = o.id
              join scoped_targets st on st.id = tob.target_id
             where o.object_type = 'person'
               and coalesce(tob.object_role, '') <> 'target_emperor'
        )
    """
    target_scope_with = f"with {target_cte}"
    return {
        "person_objects": fetch_scalar(cur, scope_cte + " select count(*)::int as n from scoped_persons", params),
        "missing_person_profiles": fetch_scalar(
            cur,
            scope_cte
            + """
              select count(*)::int as n
                from scoped_persons sp
                left join retrieval_v2.person_profiles pp on pp.object_id = sp.id
               where pp.id is null
            """,
            params,
        ),
        "missing_talent_grade": fetch_scalar(
            cur,
            scope_cte
            + """
              select count(*)::int as n
                from scoped_persons sp
                join retrieval_v2.person_profiles pp on pp.object_id = sp.id
               where pp.talent_grade is null
            """,
            params,
        ),
        "needs_review_profiles": fetch_scalar(
            cur,
            scope_cte
            + """
              select count(*)::int as n
                from scoped_persons sp
                join retrieval_v2.person_profiles pp on pp.object_id = sp.id
               where pp.review_status = 'needs_review'
            """,
            params,
        ),
        "duplicate_profiles": fetch_scalar(
            cur,
            scope_cte
            + """
              select count(*)::int as n
                from (
                    select pp.object_id
                      from scoped_persons sp
                      join retrieval_v2.person_profiles pp on pp.object_id = sp.id
                     group by pp.object_id
                    having count(*) > 1
                ) d
            """,
            params,
        ),
        "missing_person_roles": fetch_scalar(
            cur,
            scope_cte
            + """
              select count(*)::int as n
                from scoped_persons sp
               where not exists (
                    select 1 from retrieval_v2.person_roles pr
                     where pr.object_id = sp.id
                       and pr.review_status in ('pending', 'accepted')
               )
            """,
            params,
        ),
        "missing_person_affiliations": fetch_scalar(
            cur,
            scope_cte
            + """
              select count(*)::int as n
                from scoped_persons sp
               where not exists (
                    select 1 from retrieval_v2.person_affiliations pa
                     where pa.object_id = sp.id
                       and pa.review_status in ('pending', 'accepted')
               )
            """,
            params,
        ),
        "missing_script_variants": fetch_scalar(
            cur,
            scope_cte
            + """
              select count(*)::int as n
                from scoped_persons sp
                join retrieval_v2.objects o on o.id = sp.id
               where o.canonical_name <> o.normalized_name
                 and not exists (
                    select 1 from retrieval_v2.object_names onm
                     where onm.object_id = o.id
                       and onm.name_kind::text = 'script_variant'
                       and onm.review_status in ('pending', 'accepted')
                 )
            """,
            params,
        ),
        "target_emperors": fetch_scalar(
            cur,
            target_scope_with
            + """
            select count(*)::int as n
              from scoped_targets
            """,
            params,
        ),
        "missing_target_emperor_objects": fetch_scalar(
            cur,
            target_scope_with
            + """
            select count(*)::int as n
              from scoped_targets st
             where not exists (
                   select 1
                     from retrieval_v2.target_objects tob
                     join retrieval_v2.objects o on o.id = tob.object_id
                    where tob.target_id = st.id
                      and tob.object_role = 'target_emperor'
                      and o.object_type = 'person'
               )
            """,
            params,
        ),
        "missing_target_emperor_profiles": fetch_scalar(
            cur,
            target_scope_with
            + """
            select count(*)::int as n
              from scoped_targets st
             where not exists (
                   select 1
                     from retrieval_v2.target_objects tob
                     join retrieval_v2.objects o on o.id = tob.object_id
                     join retrieval_v2.person_profiles pp on pp.object_id = o.id
                    where tob.target_id = st.id
                      and tob.object_role = 'target_emperor'
                      and o.object_type = 'person'
                      and pp.review_status in ('pending', 'accepted')
               )
               and exists (
                   select 1
                     from retrieval_v2.target_objects tob
                     join retrieval_v2.objects o on o.id = tob.object_id
                    where tob.target_id = st.id
                      and tob.object_role = 'target_emperor'
                      and o.object_type = 'person'
               )
            """,
            params,
        ),
        "missing_target_emperor_roles": fetch_scalar(
            cur,
            target_scope_with
            + """
            select count(*)::int as n
              from scoped_targets st
             where not exists (
                   select 1
                     from retrieval_v2.target_objects tob
                     join retrieval_v2.objects o on o.id = tob.object_id
                     join retrieval_v2.person_roles pr on pr.object_id = o.id
                    where tob.target_id = st.id
                      and tob.object_role = 'target_emperor'
                      and o.object_type = 'person'
                      and pr.role_kind = 'emperor'
                      and pr.review_status in ('pending', 'accepted')
               )
               and exists (
                   select 1
                     from retrieval_v2.target_objects tob
                     join retrieval_v2.objects o on o.id = tob.object_id
                    where tob.target_id = st.id
                      and tob.object_role = 'target_emperor'
                      and o.object_type = 'person'
               )
            """,
            params,
        ),
        "missing_target_emperor_affiliations": fetch_scalar(
            cur,
            target_scope_with
            + """
            select count(*)::int as n
              from scoped_targets st
             where not exists (
                   select 1
                     from retrieval_v2.target_objects tob
                     join retrieval_v2.objects o on o.id = tob.object_id
                     join retrieval_v2.person_affiliations pa on pa.object_id = o.id
                    where tob.target_id = st.id
                      and tob.object_role = 'target_emperor'
                      and o.object_type = 'person'
                      and pa.affiliation_kind = 'dynasty'
                      and pa.review_status in ('pending', 'accepted')
               )
               and exists (
                   select 1
                     from retrieval_v2.target_objects tob
                     join retrieval_v2.objects o on o.id = tob.object_id
                    where tob.target_id = st.id
                      and tob.object_role = 'target_emperor'
                      and o.object_type = 'person'
               )
            """,
            params,
        ),
        "material_review_pending": fetch_scalar(
            cur,
            target_scope_with
            + """
            select count(*)::int as n
              from retrieval_v2.material_review_queue mrq
              join retrieval_v2.material_claims mc on mc.id = mrq.claim_id
              join retrieval_v2.source_packs sp on sp.id = mc.source_pack_id
              join scoped_targets st on st.id = sp.target_id
             where mrq.queue_status in ('ready', 'needs_review')
            """,
            params,
        ),
        "factorization_required": fetch_scalar(
            cur,
            target_scope_with
            + """
            select count(*)::int as n
              from retrieval_v2.claim_rule_bindings crb
              join retrieval_v2.material_claims mc on mc.id = crb.claim_id
             join retrieval_v2.source_packs sp on sp.id = mc.source_pack_id
             join scoped_targets st on st.id = sp.target_id
             where (%s = '' or crb.rule_code = %s)
               and crb.usable_for_scoring_cluster
               and crb.review_status in ('pending', 'accepted')
               and not exists (
                    select 1
                      from retrieval_v2.claim_rule_binding_factor_judgments j
                     where j.binding_id = crb.id
                       and j.formula_code = %s
               )
            """,
            params + (rule_code, rule_code, DEFAULT_CLUSTER_FORMULA),
        ),
        "rule_score_required": fetch_scalar(
            cur,
            target_scope_with
            + """
            select count(*)::int as n
              from (
                    select distinct j.target_id, j.rule_code, j.formula_code
                      from retrieval_v2.claim_rule_binding_factor_judgments j
                      join scoped_targets st on st.id = j.target_id
                     where (%s = '' or j.rule_code = %s)
                       and j.formula_code = %s
                       and j.review_status = 'accepted'
               ) factorized
             where not exists (
                    select 1
                      from retrieval_v2.target_rule_score_clusters c
                     where c.target_id = factorized.target_id
                       and c.rule_code = factorized.rule_code
                       and c.formula_code = factorized.formula_code
               )
            """,
            params + (rule_code, rule_code, DEFAULT_CLUSTER_FORMULA),
        ),
    }


def classify_readiness(snapshot: Mapping[str, int], *, rule_code: str) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    agent_tasks: list[dict[str, Any]] = []

    if int(snapshot.get("duplicate_profiles") or 0):
        blockers.append(reason_entry("ambiguous_identity", count=int(snapshot["duplicate_profiles"]), message="同一 object 出现多条人物画像。"))

    if int(snapshot.get("missing_person_profiles") or 0):
        blockers.append(reason_entry("ambiguous_identity", count=int(snapshot["missing_person_profiles"]), message="person object 缺人物画像，无法进入稳定消费层。"))

    missing_target_profile = int(snapshot.get("missing_target_emperor_objects") or 0) + int(snapshot.get("missing_target_emperor_profiles") or 0)
    if missing_target_profile:
        blockers.append(reason_entry("missing_target_emperor_profile", count=missing_target_profile))

    if int(snapshot.get("missing_target_emperor_roles") or 0):
        blockers.append(reason_entry("missing_person_role", count=int(snapshot["missing_target_emperor_roles"]), message="目标皇帝缺 emperor 身份阶段。"))

    if int(snapshot.get("missing_target_emperor_affiliations") or 0):
        warnings.append(
            reason_entry(
                "missing_person_affiliation",
                count=int(snapshot["missing_target_emperor_affiliations"]),
                message="目标皇帝缺朝代归属；不阻塞 retrieval_v2 消费，但会影响按朝代筛选和后续人物画像检索。",
            )
        )

    if int(snapshot.get("material_review_pending") or 0):
        blockers.append(
            reason_entry(
                "material_review_pending",
                count=int(snapshot["material_review_pending"]),
                message="材料复核队列未清空；先处理 material_review_queue 再进入 claim 入分和因子化。",
            )
        )

    missing_talent = int(snapshot.get("missing_talent_grade") or 0)
    if missing_talent:
        severity = "blocking" if rule_code in RULES_REQUIRING_TALENT_GRADE else "warning"
        entry = reason_entry("missing_talent_grade", count=missing_talent, severity=severity)
        if severity == "blocking":
            blockers.append(entry)
        else:
            warnings.append(entry)
        agent_tasks.append({"code": "missing_talent_grade", "count": missing_talent, "handoff": REASON_CATALOG["missing_talent_grade"]["description"]})

    for code, key in [
        ("missing_person_role", "missing_person_roles"),
        ("missing_person_affiliation", "missing_person_affiliations"),
        ("missing_name_variant", "missing_script_variants"),
    ]:
        count = int(snapshot.get(key) or 0)
        if count:
            warnings.append(reason_entry(code, count=count))
            agent_tasks.append({"code": code, "count": count, "handoff": REASON_CATALOG[code]["description"]})

    factorization_required = int(snapshot.get("factorization_required") or 0)
    rule_score_required = int(snapshot.get("rule_score_required") or 0)

    return {
        "ok": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "agent_tasks": agent_tasks,
        "downstream_required": [
            reason_entry("claim_scoring_decision_required", count=0),
            reason_entry("factorization_required", count=factorization_required),
            reason_entry("rule_score_required", count=rule_score_required),
            reason_entry("accepted_missing_required", count=0),
        ],
    }


def fetch_readiness_report(*, env_file: Path | None, dsn_env: str, item_code: str, rule_code: str, scope: str = "active-targets") -> dict[str, Any]:
    if env_file is not None:
        load_env_file(env_file)
    psycopg, dict_row = import_psycopg()
    dsn = resolve_dsn(dsn_env)
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            snapshot = fetch_readiness_snapshot(cur, item_code=item_code, rule_code=rule_code, scope=scope)
    classified = classify_readiness(snapshot, rule_code=rule_code)
    return {
        "generated_by": "scripts/dev/retrieval_v2_consumer.py",
        "command": "readiness",
        "item_code": item_code,
        "rule_code": rule_code,
        "scope": scope,
        "ok": classified["ok"],
        "snapshot": snapshot,
        **classified,
    }


def markdown_report(payload: Mapping[str, Any]) -> str:
    lines = [
        "# retrieval_v2 consumer report",
        "",
        f"- command: `{payload.get('command', '')}`",
        f"- ok: `{str(payload.get('ok')).lower()}`",
        f"- stage: `{payload.get('stage', '')}`",
        f"- write_db: `{str(payload.get('write_db', False)).lower()}`",
        f"- scope: `{payload.get('scope', '')}`",
        "",
    ]
    totals = payload.get("totals")
    if isinstance(totals, Mapping):
        lines.extend(["## Totals", "", "| key | value |", "| --- | ---: |"])
        for key, value in totals.items():
            lines.append(f"| {key} | {value} |")
        lines.append("")

    snapshot = payload.get("snapshot")
    if isinstance(snapshot, Mapping):
        lines.extend(["## Snapshot", "", "| key | value |", "| --- | ---: |"])
        for key, value in snapshot.items():
            lines.append(f"| {key} | {value} |")
        lines.append("")

    worklists = payload.get("worklists") if isinstance(payload.get("worklists"), Mapping) else payload
    for title, key in [("Blockers", "blockers"), ("Warnings", "warnings"), ("Agent Tasks", "agent_tasks")]:
        items = list(worklists.get(key) or []) if isinstance(worklists, Mapping) else []
        if not items:
            continue
        lines.extend([f"## {title}", ""])
        for item in items:
            lines.append(f"- `{item.get('code')}` count `{item.get('count', len(item.get('items', []) or []))}`: {item.get('description') or item.get('handoff') or item.get('message') or ''}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_report(output_json: Path, output_md: Path, payload: Mapping[str, Any]) -> None:
    write_json(output_json, payload)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(markdown_report(payload), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unified retrieval_v2 consumer entrypoint; default operations are dry-run/read-only.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--env-file", type=Path)
    common.add_argument("--dsn-env", default="EMPEROR_EVAL_RETRIEVAL_V2_DSN")
    common.add_argument("--old-dsn-env", default="EMPEROR_EVAL_PG_DSN")
    common.add_argument("--output-json", type=Path, required=True)
    common.add_argument("--output-md", type=Path, required=True)

    plan = subparsers.add_parser("plan", parents=[common], help="Dry-run completion and show readiness.")
    plan.add_argument("--item-code", default="")
    plan.add_argument("--rule-code", default="")
    plan.add_argument("--scope", choices=READINESS_SCOPES, default="active-targets")

    apply = subparsers.add_parser("apply", parents=[common], help="Run a consumer stage; dry-run unless --execute is set.")
    apply.add_argument("--stage", choices=STAGES, required=True)
    apply.add_argument("--execute", action="store_true")

    readiness = subparsers.add_parser("readiness", parents=[common], help="Read-only consumer readiness gate.")
    readiness.add_argument("--item-code", default="")
    readiness.add_argument("--rule-code", default="")
    readiness.add_argument("--scope", choices=READINESS_SCOPES, default="active-targets")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "plan":
        payload = plan_consumer(
            env_file=args.env_file,
            dsn_env=args.dsn_env,
            old_dsn_env=args.old_dsn_env,
            item_code=args.item_code,
            rule_code=args.rule_code,
            scope=args.scope,
        )
    elif args.command == "apply":
        if args.stage != "completion":
            raise ImportPlanError(f"unsupported stage: {args.stage}")
        payload = execute_completion_stage(env_file=args.env_file, dsn_env=args.dsn_env, old_dsn_env=args.old_dsn_env, execute=args.execute)
    elif args.command == "readiness":
        payload = fetch_readiness_report(env_file=args.env_file, dsn_env=args.dsn_env, item_code=args.item_code, rule_code=args.rule_code, scope=args.scope)
    else:
        raise ImportPlanError(f"unsupported command: {args.command}")

    write_report(args.output_json, args.output_md, payload)
    print(json.dumps({"ok": payload["ok"], "command": args.command, "output_json": str(args.output_json)}, ensure_ascii=False, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
