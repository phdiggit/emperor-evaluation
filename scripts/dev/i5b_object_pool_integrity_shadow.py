from __future__ import annotations

from typing import Mapping

from scripts.dev.i5b_object_pool_integrity_common import (
    ALLOWED_DIRECTIONS,
    LIFECYCLE_STATUSES,
    REVIEW_STATUSES,
    SCORE_MODES,
    SOURCE_METHODS,
    RowCheck,
    _has,
)


def fact_relation_checks(table_counts: Mapping[str, int]) -> list[RowCheck]:
    if not _has(table_counts, "fact_relations"):
        return []
    checks = [
        RowCheck(
            "fact_relations",
            "fact_relation_orphan_reference",
            "error",
            "fact relations must reference existing emperor, item/rule, objects, source and optional obj_src rows",
            """
            select fr.id, fr.emp_id, fr.item_id, fr.rule_id, fr.subject_obj_id,
                   fr.object_obj_id, fr.doc_id, fr.obj_src_id
              from public.fact_relations fr
              left join public.emps e on e.id = fr.emp_id
              left join public.eval_items i on i.id = fr.item_id
              left join public.eval_rules er on er.id = fr.rule_id
              left join public.raw_objs subject on subject.id = fr.subject_obj_id
              left join public.raw_objs object on object.id = fr.object_obj_id
              left join public.src_docs sd on sd.id = fr.doc_id
              left join public.obj_srcs os on os.id = fr.obj_src_id
             where e.id is null
                or (fr.item_id is not null and i.id is null)
                or (fr.rule_id is not null and er.id is null)
                or subject.id is null
                or (fr.object_obj_id is not null and object.id is null)
                or (fr.doc_id is not null and sd.id is null)
                or (fr.obj_src_id is not null and os.id is null)
             order by fr.id
            """,
        ),
        RowCheck(
            "fact_relations",
            "fact_relation_source_chain_mismatch",
            "error",
            "fact_relations.obj_src_id must belong to the same emperor/item/rule chain when present",
            """
            select fr.id, fr.emp_id, fr.item_id, fr.rule_id, fr.obj_src_id,
                   eo.emp_id as source_emp_id, os.item_id as source_item_id, os.rule_id as source_rule_id
              from public.fact_relations fr
              join public.obj_srcs os on os.id = fr.obj_src_id
              join public.emp_objs eo on eo.id = os.emp_obj_id
             where eo.emp_id <> fr.emp_id
                or (fr.item_id is not null and os.item_id <> fr.item_id)
                or (fr.rule_id is not null and os.rule_id <> fr.rule_id)
             order by fr.id
            """,
        ),
        RowCheck(
            "fact_relations",
            "invalid_fact_relation_status",
            "error",
            "fact relation status fields must use lifecycle/review/source enums",
            """
            select id, source_method, review_status, status
              from public.fact_relations
             where source_method <> all(%s)
                or review_status <> all(%s)
                or status <> all(%s)
             order by id
            """,
            (list(SOURCE_METHODS), list(REVIEW_STATUSES), list(LIFECYCLE_STATUSES)),
        ),
    ]
    if _has(table_counts, "fact_relation_predicate_options", "raw_objs"):
        checks.append(
            RowCheck(
                "fact_relations",
                "predicate_not_in_active_catalog",
                "warning",
                "active fact relation predicate should be backed by fact_relation_predicate_options",
                """
                select fr.id, fr.rule_code, fr.predicate, fr.relation_role,
                       subject.obj_type as subject_obj_type,
                       coalesce(object.obj_type, '') as object_obj_type
                  from public.fact_relations fr
                  join public.raw_objs subject on subject.id = fr.subject_obj_id
                  left join public.raw_objs object on object.id = fr.object_obj_id
                 where fr.status = 'active'
                   and not exists (
                       select 1
                         from public.fact_relation_predicate_options opt
                        where opt.status = 'active'
                          and opt.item_code = fr.item_code
                          and opt.rule_code = fr.rule_code
                          and opt.predicate = fr.predicate
                          and opt.relation_role = fr.relation_role
                          and opt.subject_obj_type = subject.obj_type
                          and opt.object_obj_type = coalesce(object.obj_type, '')
                   )
                 order by fr.id
                """,
            )
        )
    return checks


def rule_evidence_unit_checks(table_counts: Mapping[str, int]) -> list[RowCheck]:
    if not _has(table_counts, "rule_evidence_units"):
        return []
    checks = [
        RowCheck(
            "rule_evidence_units",
            "rule_unit_orphan_reference",
            "error",
            "rule evidence units must reference existing emperor, item/rule, and optional scored object/source rows",
            """
            select reu.id, reu.emp_id, reu.item_id, reu.rule_id, reu.scored_obj_id, reu.scored_obj_src_id
              from public.rule_evidence_units reu
              left join public.emps e on e.id = reu.emp_id
              left join public.eval_items i on i.id = reu.item_id
              left join public.eval_rules er on er.id = reu.rule_id
              left join public.raw_objs ro on ro.id = reu.scored_obj_id
              left join public.obj_srcs os on os.id = reu.scored_obj_src_id
             where e.id is null
                or i.id is null
                or er.id is null
                or (reu.scored_obj_id is not null and ro.id is null)
                or (reu.scored_obj_src_id is not null and os.id is null)
             order by reu.id
            """,
        ),
        RowCheck(
            "rule_evidence_units",
            "rule_unit_identity_mismatch",
            "error",
            "rule unit item_code/rule_code must match linked eval_items/eval_rules",
            """
            select reu.id, reu.item_id, reu.item_code, i.item_code as expected_item_code,
                   reu.rule_id, reu.rule_code, er.rule_code as expected_rule_code
              from public.rule_evidence_units reu
              join public.eval_items i on i.id = reu.item_id
              join public.eval_rules er on er.id = reu.rule_id
             where i.item_code <> reu.item_code
                or er.rule_code <> reu.rule_code
                or er.item_id <> reu.item_id
             order by reu.id
            """,
        ),
        RowCheck(
            "rule_evidence_units",
            "rule_unit_scored_source_mismatch",
            "error",
            "scored_obj_src_id must match scored_obj_id and the same emperor/item/rule chain",
            """
            select reu.id, reu.emp_id, reu.item_id, reu.rule_id,
                   reu.scored_obj_id, reu.scored_obj_src_id,
                   os.obj_id as source_obj_id, eo.emp_id as source_emp_id,
                   os.item_id as source_item_id, os.rule_id as source_rule_id
              from public.rule_evidence_units reu
              join public.obj_srcs os on os.id = reu.scored_obj_src_id
              join public.emp_objs eo on eo.id = os.emp_obj_id
             where (reu.scored_obj_id is not null and os.obj_id <> reu.scored_obj_id)
                or eo.emp_id <> reu.emp_id
                or os.item_id <> reu.item_id
                or os.rule_id <> reu.rule_id
             order by reu.id
            """,
        ),
        RowCheck(
            "rule_evidence_units",
            "invalid_rule_unit_status",
            "error",
            "rule evidence unit status fields must use lifecycle/review/source/score-mode enums",
            """
            select id, direction, score_mode, source_method, review_status, status
              from public.rule_evidence_units
             where direction <> all(%s)
                or score_mode <> all(%s)
                or source_method <> all(%s)
                or review_status <> all(%s)
                or status <> all(%s)
             order by id
            """,
            (list(ALLOWED_DIRECTIONS), list(SCORE_MODES), list(SOURCE_METHODS), list(REVIEW_STATUSES), list(LIFECYCLE_STATUSES)),
        ),
    ]
    if _has(table_counts, "eval_rule_material_policies"):
        checks.append(
            RowCheck(
                "rule_evidence_units",
                "rule_unit_scoring_role_not_in_policy",
                "warning",
                "rule unit scoring_role should be declared by the active material policy",
                """
                select reu.id, reu.rule_code, reu.scoring_role
                  from public.rule_evidence_units reu
                 where reu.status = 'active'
                   and not exists (
                       select 1
                         from public.eval_rule_material_policies p
                        where p.status = 'active'
                          and p.item_id = reu.item_id
                          and p.rule_id = reu.rule_id
                          and reu.scoring_role = any(p.allowed_scoring_roles)
                   )
                 order by reu.id
                """,
            )
        )
    return checks


def rule_evidence_member_checks(table_counts: Mapping[str, int]) -> list[RowCheck]:
    if not _has(table_counts, "rule_evidence_unit_members"):
        return []
    checks = [
        RowCheck(
            "rule_evidence_unit_members",
            "rule_member_orphan_reference",
            "error",
            "rule evidence members must reference existing unit and optional object/source/relation rows",
            """
            select m.id, m.unit_id, m.obj_id, m.obj_src_id, m.relation_id
              from public.rule_evidence_unit_members m
              left join public.rule_evidence_units reu on reu.id = m.unit_id
              left join public.raw_objs ro on ro.id = m.obj_id
              left join public.obj_srcs os on os.id = m.obj_src_id
              left join public.fact_relations fr on fr.id = m.relation_id
             where reu.id is null
                or (m.obj_id is not null and ro.id is null)
                or (m.obj_src_id is not null and os.id is null)
                or (m.relation_id is not null and fr.id is null)
             order by m.id
            """,
        ),
        RowCheck(
            "rule_evidence_unit_members",
            "rule_member_source_object_mismatch",
            "error",
            "member obj_src_id must point to the same object when member obj_id is present",
            """
            select m.id, m.obj_id, m.obj_src_id, os.obj_id as source_obj_id
              from public.rule_evidence_unit_members m
              join public.obj_srcs os on os.id = m.obj_src_id
             where m.obj_id is not null
               and os.obj_id <> m.obj_id
             order by m.id
            """,
        ),
        RowCheck(
            "rule_evidence_unit_members",
            "rule_member_relation_chain_mismatch",
            "error",
            "member relation_id must belong to the same emperor/item/rule chain as the unit",
            """
            select m.id, m.unit_id, m.relation_id,
                   reu.emp_id, reu.item_id, reu.rule_id,
                   fr.emp_id as relation_emp_id, fr.item_id as relation_item_id, fr.rule_id as relation_rule_id
              from public.rule_evidence_unit_members m
              join public.rule_evidence_units reu on reu.id = m.unit_id
              join public.fact_relations fr on fr.id = m.relation_id
             where fr.emp_id <> reu.emp_id
                or (fr.item_id is not null and fr.item_id <> reu.item_id)
                or (fr.rule_id is not null and fr.rule_id <> reu.rule_id)
             order by m.id
            """,
        ),
        RowCheck(
            "rule_evidence_unit_members",
            "invalid_rule_member_status",
            "error",
            "rule evidence member status fields must use lifecycle/review/source enums",
            """
            select id, source_method, review_status, status
              from public.rule_evidence_unit_members
             where source_method <> all(%s)
                or review_status <> all(%s)
                or status <> all(%s)
             order by id
            """,
            (list(SOURCE_METHODS), list(REVIEW_STATUSES), list(LIFECYCLE_STATUSES)),
        ),
    ]
    if _has(table_counts, "eval_rule_material_policies", "rule_evidence_units"):
        checks.append(
            RowCheck(
                "rule_evidence_unit_members",
                "rule_member_role_not_in_policy",
                "warning",
                "member_role should be declared by active rule material policy as scoring or context role",
                """
                select m.id, reu.rule_code, m.member_role
                  from public.rule_evidence_unit_members m
                  join public.rule_evidence_units reu on reu.id = m.unit_id
                 where m.status = 'active'
                   and not exists (
                       select 1
                         from public.eval_rule_material_policies p
                        where p.status = 'active'
                          and p.item_id = reu.item_id
                          and p.rule_id = reu.rule_id
                          and (
                              m.member_role = any(p.allowed_scoring_roles)
                              or m.member_role = any(p.context_roles)
                          )
                   )
                 order by m.id
                """,
            )
        )
    return checks


def calc_detail_checks(table_counts: Mapping[str, int]) -> list[RowCheck]:
    if not _has(table_counts, "evd_cluster_calc_details", "evd_clusters", "obj_srcs"):
        return []
    checks: list[RowCheck] = []
    for field in ("material_ids", "covered_material_ids", "scored_material_ids", "supporting_material_ids"):
        checks.append(
            RowCheck(
                "evd_cluster_calc_details",
                f"{field}_missing_obj_src",
                "error",
                f"{field} must reference existing obj_srcs rows",
                f"""
                select d.cluster_id, '{field}' as field_name, material_id as obj_src_id
                  from public.evd_cluster_calc_details d
                  cross join lateral unnest(d.{field}) as material_id
                  left join public.obj_srcs os on os.id = material_id
                 where os.id is null
                 order by d.cluster_id, material_id
                """,
            )
        )
        checks.append(
            RowCheck(
                "evd_cluster_calc_details",
                f"{field}_chain_mismatch",
                "error",
                f"{field} must point to obj_srcs in the same emperor/item/rule cluster",
                f"""
                select d.cluster_id, '{field}' as field_name, material_id as obj_src_id,
                       c.emp_id, c.item_id, c.rule_id,
                       eo.emp_id as material_emp_id, os.item_id as material_item_id, os.rule_id as material_rule_id
                  from public.evd_cluster_calc_details d
                  join public.evd_clusters c on c.id = d.cluster_id
                  cross join lateral unnest(d.{field}) as material_id
                  join public.obj_srcs os on os.id = material_id
                  join public.emp_objs eo on eo.id = os.emp_obj_id
                 where eo.emp_id <> c.emp_id
                    or os.item_id <> c.item_id
                    or os.rule_id <> c.rule_id
                 order by d.cluster_id, material_id
                """,
            )
        )
    checks.extend(
        [
            RowCheck(
                "evd_cluster_calc_details",
                "scored_material_not_covered",
                "error",
                "scored_material_ids must be a subset of covered_material_ids",
                """
                select d.cluster_id, array_agg(scored_id order by scored_id) as scored_ids_not_covered
                  from public.evd_cluster_calc_details d
                  cross join lateral unnest(d.scored_material_ids) as scored_id
                 where not (scored_id = any(d.covered_material_ids))
                 group by d.cluster_id
                 order by d.cluster_id
                """,
            ),
            RowCheck(
                "evd_cluster_calc_details",
                "material_not_covered",
                "warning",
                "material_ids should be a subset of covered_material_ids",
                """
                select d.cluster_id, array_agg(material_id order by material_id) as material_ids_not_covered
                  from public.evd_cluster_calc_details d
                  cross join lateral unnest(d.material_ids) as material_id
                 where not (material_id = any(d.covered_material_ids))
                 group by d.cluster_id
                 order by d.cluster_id
                """,
            ),
            RowCheck(
                "evd_cluster_calc_details",
                "calc_detail_material_missing_obj_src",
                "error",
                "calc_detail.materials obj_src_id must reference existing obj_srcs rows",
                """
                select d.cluster_id, (material->>'obj_src_id')::bigint as obj_src_id
                  from public.evd_cluster_calc_details d
                  cross join lateral jsonb_array_elements(coalesce(d.calc_detail->'materials', '[]'::jsonb)) as material
                  left join public.obj_srcs os on os.id = (material->>'obj_src_id')::bigint
                 where (material->>'obj_src_id') ~ '^\\d+$'
                   and os.id is null
                 order by d.cluster_id, obj_src_id
                """,
            ),
            RowCheck(
                "evd_cluster_calc_details",
                "calc_detail_material_invalid_obj_src_id",
                "error",
                "calc_detail.materials obj_src_id must be a numeric id when present",
                """
                select d.cluster_id, material->>'obj_src_id' as obj_src_id
                  from public.evd_cluster_calc_details d
                  cross join lateral jsonb_array_elements(coalesce(d.calc_detail->'materials', '[]'::jsonb)) as material
                 where material ? 'obj_src_id'
                   and not ((material->>'obj_src_id') ~ '^\\d+$')
                 order by d.cluster_id
                """,
            ),
        ]
    )
    return checks




def shadow_checks(table_counts: Mapping[str, int]) -> list[RowCheck]:
    checks: list[RowCheck] = []
    checks.extend(fact_relation_checks(table_counts))
    checks.extend(rule_evidence_unit_checks(table_counts))
    checks.extend(rule_evidence_member_checks(table_counts))
    checks.extend(calc_detail_checks(table_counts))
    return checks
