from __future__ import annotations

from typing import Any

from scripts.dev.retrieval_v2_diagnostics_lib.common import (
    check_entry,
    fetch_scalar,
    scoped_with,
    base_params,
    rule_params,
)

def fetch_summary(cur: Any, *, item_code: str, rule_code: str, formula_code: str, scope: str) -> dict[str, Any]:
    with_cte = scoped_with(scope)
    item_params = base_params(item_code)
    rule_formula_params = rule_params(item_code, rule_code, formula_code)
    summary = {
        "targets": fetch_scalar(cur, with_cte + " select count(*)::int as n from scoped_targets", item_params),
        "accepted_source_packs": fetch_scalar(
            cur,
            with_cte
            + """
            select count(*)::int as n
              from retrieval_v2.source_packs sp
              join scoped_targets st on st.id = sp.target_id
             where sp.status = 'accepted'
            """,
            item_params,
        ),
        "material_claims": fetch_scalar(
            cur,
            with_cte
            + """
            select count(*)::int as n
              from retrieval_v2.material_claims mc
              join retrieval_v2.source_packs sp on sp.id = mc.source_pack_id
              join scoped_targets st on st.id = sp.target_id
            """,
            item_params,
        ),
        "claim_rule_bindings": fetch_scalar(
            cur,
            with_cte
            + """
            select count(*)::int as n
              from retrieval_v2.claim_rule_bindings crb
              join retrieval_v2.material_claims mc on mc.id = crb.claim_id
              join retrieval_v2.source_packs sp on sp.id = mc.source_pack_id
              join scoped_targets st on st.id = sp.target_id
             where (%s = '' or crb.rule_code = %s)
            """,
            item_params + (rule_code, rule_code),
        ),
        "factor_judgments": fetch_scalar(
            cur,
            with_cte
            + """
            select count(*)::int as n
              from retrieval_v2.claim_rule_binding_factor_judgments j
              join scoped_targets st on st.id = j.target_id
             where (%s = '' or j.rule_code = %s)
               and j.formula_code = %s
            """,
            rule_formula_params,
        ),
        "material_scores": fetch_scalar(
            cur,
            with_cte
            + """
            select count(*)::int as n
              from retrieval_v2.claim_rule_binding_material_scores ms
              join scoped_targets st on st.id = ms.target_id
             where (%s = '' or ms.rule_code = %s)
               and ms.formula_code = %s
            """,
            rule_formula_params,
        ),
        "rule_score_clusters": fetch_scalar(
            cur,
            with_cte
            + """
            select count(*)::int as n
              from retrieval_v2.target_rule_score_clusters c
              join scoped_targets st on st.id = c.target_id
             where (%s = '' or c.rule_code = %s)
               and c.formula_code = %s
            """,
            rule_formula_params,
        ),
        "material_review_pending": fetch_scalar(
            cur,
            with_cte
            + """
            select count(*)::int as n
              from retrieval_v2.material_review_queue mrq
              join retrieval_v2.material_claims mc on mc.id = mrq.claim_id
              join retrieval_v2.source_packs sp on sp.id = mc.source_pack_id
              join scoped_targets st on st.id = sp.target_id
             where mrq.queue_status in ('ready', 'needs_review')
            """,
            item_params,
        ),
    }
    return {
        "generated_by": "scripts/dev/retrieval_v2_diagnostics.py",
        "command": "summary",
        "ok": True,
        "scope": {"item_code": item_code, "rule_code": rule_code, "formula_code": formula_code, "scope": scope},
        "totals": summary,
    }

def fetch_coverage_checks(cur: Any, *, item_code: str, rule_code: str, formula_code: str, scope: str) -> dict[str, Any]:
    with_cte = scoped_with(scope)
    params = rule_params(item_code, rule_code, formula_code)
    factorization_missing_sql = (
        with_cte
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
        """
    )
    material_score_missing_sql = (
        with_cte
        + """
        select count(*)::int as n
          from retrieval_v2.claim_rule_binding_factor_judgments j
          join scoped_targets st on st.id = j.target_id
         where (%s = '' or j.rule_code = %s)
           and j.formula_code = %s
           and j.target_action = 'score'
           and j.review_status = 'accepted'
           and not exists (
                select 1
                  from retrieval_v2.claim_rule_binding_material_scores ms
                 where ms.factor_judgment_id = j.id
           )
        """
    )
    rule_score_missing_sql = (
        with_cte
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
        """
    )
    role_link_missing_sql = (
        with_cte
        + """
        select count(*)::int as n
          from retrieval_v2.claim_rule_binding_factor_judgments j
          join retrieval_v2.claim_rule_bindings crb on crb.id = j.binding_id
          join scoped_targets st on st.id = j.target_id
          left join retrieval_v2.material_object_links mol on mol.claim_id = j.claim_id and mol.role = crb.object_role
         where (%s = '' or j.rule_code = %s)
           and j.formula_code = %s
           and j.target_action = 'score'
           and j.review_status = 'accepted'
           and mol.id is null
        """
    )
    stale_cluster_sql = (
        with_cte
        + """
        select count(*)::int as n
          from retrieval_v2.target_rule_score_clusters c
          join scoped_targets st on st.id = c.target_id
          left join (
                select
                    j.target_id,
                    j.rule_code,
                    j.formula_code,
                    count(*) filter (where j.target_action = 'score')::int as scored,
                    count(*) filter (where j.target_action = 'supporting_only')::int as supporting,
                    count(*) filter (where j.target_action = 'exclude')::int as excluded
                  from retrieval_v2.claim_rule_binding_factor_judgments j
                 where j.review_status = 'accepted'
                 group by j.target_id, j.rule_code, j.formula_code
          ) j on j.target_id = c.target_id and j.rule_code = c.rule_code and j.formula_code = c.formula_code
         where (%s = '' or c.rule_code = %s)
           and c.formula_code = %s
           and (
                c.scored_judgment_count <> coalesce(j.scored, 0)
                or c.supporting_judgment_count <> coalesce(j.supporting, 0)
                or c.excluded_judgment_count <> coalesce(j.excluded, 0)
           )
        """
    )
    counts = {
        "factorization_required": fetch_scalar(cur, factorization_missing_sql, params),
        "role_matched_object_link_missing": fetch_scalar(cur, role_link_missing_sql, params),
        "material_score_required": fetch_scalar(cur, material_score_missing_sql, params),
        "rule_score_required": fetch_scalar(cur, rule_score_missing_sql, params),
        "rule_score_stale": fetch_scalar(cur, stale_cluster_sql, params),
    }
    checks = [
        check_entry(
            "factorization_required",
            count=counts["factorization_required"],
            severity="downstream",
            owner="agent_or_human",
            description="可计分 binding 尚未生成 score/supporting_only/exclude 因子化判定。",
        ),
        check_entry(
            "role_matched_object_link_missing",
            count=counts["role_matched_object_link_missing"],
            severity="blocking",
            owner="agent_or_human",
            description="score judgment 缺少按 binding.object_role 精确匹配的 material_object_links。",
        ),
        check_entry(
            "material_score_required",
            count=counts["material_score_required"],
            severity="downstream",
            owner="agent_or_human",
            description="已有 score judgment 尚未生成 claim_rule_binding_material_scores。",
        ),
        check_entry(
            "rule_score_required",
            count=counts["rule_score_required"],
            severity="downstream",
            owner="agent_or_human",
            description="已有因子化 target/rule 尚未生成 target_rule_score_clusters。",
        ),
        check_entry(
            "rule_score_stale",
            count=counts["rule_score_stale"],
            severity="downstream",
            owner="agent_or_human",
            description="规则聚合行的 scored/supporting/excluded 计数与当前 factor judgments 不一致，需要重跑 scorer。",
        ),
    ]
    return {
        "generated_by": "scripts/dev/retrieval_v2_diagnostics.py",
        "command": "coverage",
        "ok": not any(check["status"] == "blocking" for check in checks),
        "scope": {"item_code": item_code, "rule_code": rule_code, "formula_code": formula_code, "scope": scope},
        "checks": checks,
        "totals": counts,
    }

def fetch_duplicate_checks(cur: Any, *, item_code: str, rule_code: str, formula_code: str, scope: str) -> dict[str, Any]:
    with_cte = scoped_with(scope)
    params = rule_params(item_code, rule_code, formula_code)
    duplicate_queries = {
        "duplicate_factor_judgment_idem_key": (
            with_cte
            + """
            select count(*)::int as n
              from (
                    select j.idem_key
                      from retrieval_v2.claim_rule_binding_factor_judgments j
                      join scoped_targets st on st.id = j.target_id
                     where (%s = '' or j.rule_code = %s)
                       and j.formula_code = %s
                     group by j.idem_key
                    having count(*) > 1
              ) d
            """
        ),
        "duplicate_factor_choice_natural_key": (
            with_cte
            + """
            select count(*)::int as n
              from (
                    select c.factor_judgment_id, c.factor_name
                      from retrieval_v2.claim_rule_binding_factor_choices c
                      join retrieval_v2.claim_rule_binding_factor_judgments j on j.id = c.factor_judgment_id
                      join scoped_targets st on st.id = j.target_id
                     where (%s = '' or j.rule_code = %s)
                       and j.formula_code = %s
                     group by c.factor_judgment_id, c.factor_name
                    having count(*) > 1
              ) d
            """
        ),
        "duplicate_material_score_idem_key": (
            with_cte
            + """
            select count(*)::int as n
              from (
                    select ms.idem_key
                      from retrieval_v2.claim_rule_binding_material_scores ms
                      join scoped_targets st on st.id = ms.target_id
                     where (%s = '' or ms.rule_code = %s)
                       and ms.formula_code = %s
                     group by ms.idem_key
                    having count(*) > 1
              ) d
            """
        ),
        "duplicate_rule_score_cluster_key": (
            with_cte
            + """
            select count(*)::int as n
              from (
                    select c.target_id, c.rule_code, c.formula_code
                      from retrieval_v2.target_rule_score_clusters c
                      join scoped_targets st on st.id = c.target_id
                     where (%s = '' or c.rule_code = %s)
                       and c.formula_code = %s
                     group by c.target_id, c.rule_code, c.formula_code
                    having count(*) > 1
              ) d
            """
        ),
    }
    checks = [
        check_entry(
            code,
            count=fetch_scalar(cur, sql, params),
            severity="blocking",
            owner="human",
            description="数据库中出现幂等键或自然键重复；应先人工确认来源，不自动修复。",
        )
        for code, sql in duplicate_queries.items()
    ]
    return {
        "generated_by": "scripts/dev/retrieval_v2_diagnostics.py",
        "command": "duplicates",
        "ok": not any(check["count"] for check in checks),
        "scope": {"item_code": item_code, "rule_code": rule_code, "formula_code": formula_code, "scope": scope},
        "checks": checks,
        "totals": {check["code"]: check["count"] for check in checks},
    }

