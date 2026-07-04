from __future__ import annotations

from typing import Mapping

from scripts.dev.i5b_object_pool_integrity_common import (
    ALLOWED_DIRECTIONS,
    AMBIGUOUS_OBJ_SRC_NOTE_RE,
    CANONICAL_TALENT_QUALITY_VALUES,
    GENERIC_OBJ_SRC_NOTE_RE,
    I5B_SUBITEMS,
    OBJECT_ATTR_CODES,
    POLICY_MATERIAL_SOURCES,
    RAW_NOTE_FORBIDDEN_RE,
    RowCheck,
    _has,
)


def raw_object_checks(table_counts: Mapping[str, int]) -> list[RowCheck]:
    if not _has(table_counts, "raw_objs"):
        return []
    checks = [
        RowCheck(
            "raw_objs",
            "blank_identity_field",
            "error",
            "raw object identity fields must not be blank",
            """
            select id, obj_type, period, name
              from public.raw_objs
             where btrim(coalesce(obj_type, '')) = ''
                or btrim(coalesce(period, '')) = ''
                or btrim(coalesce(name, '')) = ''
             order by id
            """,
        ),
        RowCheck(
            "raw_objs",
            "duplicate_identity_key",
            "error",
            "raw objects must be unique by obj_type, period and name",
            """
            select obj_type, period, name, count(*) as duplicate_count, array_agg(id order by id) as ids
              from public.raw_objs
             group by obj_type, period, name
            having count(*) > 1
             order by duplicate_count desc, period, name
            """,
        ),
        RowCheck(
            "raw_objs",
            "canonical_alias_key_conflict",
            "error",
            "canonical object names must not conflict within one period before alias backfill",
            """
            with normalized as (
                select id, obj_type, period, name,
                       regexp_replace(btrim(name), '[[:space:]　]+', '', 'g') as normalized_name
                  from public.raw_objs
            )
            select normalized_name, period, count(*) as object_count,
                   array_agg(id order by id) as obj_ids,
                   array_agg(obj_type || ':' || name order by id) as objects
              from normalized
             group by normalized_name, period
            having count(*) > 1
             order by object_count desc, period, normalized_name
            """,
            hint="raw_obj_aliases has a period/scope alias key, so these rows must be merged or manually disambiguated before canonical alias backfill.",
        ),
        RowCheck(
            "raw_objs",
            "raw_note_contains_scoring_terms",
            "error",
            "raw_objs.note must not carry rule, direction or score semantics",
            """
            select id, name, note
              from public.raw_objs
             where coalesce(note, '') ~ %s
             order by id
            """,
            (RAW_NOTE_FORBIDDEN_RE,),
        ),
    ]
    if _has(table_counts, "obj_srcs"):
        checks.append(
            RowCheck(
                "raw_objs",
                "raw_object_without_source_link",
                "error",
                "each raw object must have at least one obj_srcs evidence link",
                """
                select ro.id, ro.obj_type, ro.period, ro.name
                  from public.raw_objs ro
                 where not exists (
                       select 1 from public.obj_srcs os where os.obj_id = ro.id
                 )
                 order by ro.id
                """,
            )
        )
    if _has(table_counts, "emp_objs", "emps", "obj_attrs"):
        checks.append(
            RowCheck(
                "raw_objs",
                "person_object_missing_talent_quality",
                "error",
                "person objects already bound into I5B must have obj_attrs.talent_quality",
                """
                select ro.id, ro.name, ro.period, array_agg(distinct e.name order by e.name) as emperors
                  from public.raw_objs ro
                  join public.emp_objs eo on eo.obj_id = ro.id
                  join public.emps e on e.id = eo.emp_id
                 where ro.obj_type = 'person'
                   and not exists (
                       select 1
                         from public.obj_attrs oa
                        where oa.obj_id = ro.id
                          and oa.attr_code = 'talent_quality'
                   )
                 group by ro.id, ro.name, ro.period
                 order by ro.id
                """,
                hint="This does not assign a level; it blocks reimport until the existing object identity is classified or retired.",
            )
        )
    return checks


def alias_checks(table_counts: Mapping[str, int]) -> list[RowCheck]:
    if not _has(table_counts, "raw_obj_aliases"):
        return []
    checks = [
        RowCheck(
            "raw_obj_aliases",
            "alias_points_to_missing_object",
            "error",
            "object aliases must point to existing raw_objs",
            """
            select a.id, a.obj_id, a.alias_text
              from public.raw_obj_aliases a
              left join public.raw_objs ro on ro.id = a.obj_id
             where ro.id is null
             order by a.id
            """,
        ),
        RowCheck(
            "raw_obj_aliases",
            "blank_alias_value",
            "error",
            "alias text and normalized alias must not be blank",
            """
            select id, obj_id, alias_text, normalized_alias
              from public.raw_obj_aliases
             where btrim(coalesce(alias_text, '')) = ''
                or btrim(coalesce(normalized_alias, '')) = ''
             order by id
            """,
        ),
        RowCheck(
            "raw_obj_aliases",
            "normalized_alias_mismatch",
            "error",
            "normalized_alias must equal the central whitespace-stripped alias normalizer",
            """
            select id, obj_id, alias_text, normalized_alias,
                   regexp_replace(btrim(alias_text), '[[:space:]　]+', '', 'g') as expected_normalized_alias
              from public.raw_obj_aliases
             where normalized_alias <> regexp_replace(btrim(alias_text), '[[:space:]　]+', '', 'g')
             order by id
            """,
        ),
        RowCheck(
            "raw_obj_aliases",
            "active_alias_identity_conflict",
            "error",
            "one active alias in one period/scope must not point to multiple objects",
            """
            select normalized_alias, period, coalesce(scope_emp_id, 0) as scope_emp_id,
                   count(distinct obj_id) as object_count,
                   array_agg(distinct obj_id order by obj_id) as obj_ids
              from public.raw_obj_aliases
             where active
             group by normalized_alias, period, coalesce(scope_emp_id, 0)
            having count(distinct obj_id) > 1
             order by object_count desc, normalized_alias
            """,
        ),
    ]
    if _has(table_counts, "raw_objs"):
        checks.append(
            RowCheck(
                "raw_obj_aliases",
                "canonical_alias_missing",
                "error",
                "each raw object must have an active canonical alias for import-time dedupe",
                """
                select ro.id, ro.obj_type, ro.period, ro.name
                  from public.raw_objs ro
                 where not exists (
                       select 1
                         from public.raw_obj_aliases a
                        where a.obj_id = ro.id
                          and a.active
                          and a.alias_kind = 'canonical'
                          and a.period = ro.period
                          and a.normalized_alias = regexp_replace(btrim(ro.name), '[[:space:]　]+', '', 'g')
                 )
                 order by ro.id
                """,
            )
        )
    return checks


def emperor_object_checks(table_counts: Mapping[str, int]) -> list[RowCheck]:
    if not _has(table_counts, "emp_objs"):
        return []
    checks = [
        RowCheck(
            "emp_objs",
            "emp_object_orphan_reference",
            "error",
            "emp_objs must reference existing emps and raw_objs",
            """
            select eo.id, eo.emp_id, eo.obj_id
              from public.emp_objs eo
              left join public.emps e on e.id = eo.emp_id
              left join public.raw_objs ro on ro.id = eo.obj_id
             where e.id is null or ro.id is null
             order by eo.id
            """,
        ),
        RowCheck(
            "emp_objs",
            "invalid_subitem",
            "error",
            "emp_objs.subitem must use the I5B finite-value registry",
            """
            select id, emp_id, obj_id, subitem
              from public.emp_objs
             where subitem <> all(%s)
             order by id
            """,
            (list(I5B_SUBITEMS),),
        ),
        RowCheck(
            "emp_objs",
            "duplicate_emp_object_binding",
            "error",
            "one emperor/object/subitem binding must be unique",
            """
            select emp_id, obj_id, subitem, count(*) as duplicate_count, array_agg(id order by id) as ids
              from public.emp_objs
             group by emp_id, obj_id, subitem
            having count(*) > 1
             order by duplicate_count desc, emp_id, obj_id
            """,
        ),
    ]
    if _has(table_counts, "obj_srcs"):
        checks.append(
            RowCheck(
                "emp_objs",
                "emp_object_without_source_link",
                "error",
                "each emperor-object binding must have at least one object-source link",
                """
                select eo.id, e.name as emperor, ro.name as object_name, eo.subitem
                  from public.emp_objs eo
                  join public.emps e on e.id = eo.emp_id
                  join public.raw_objs ro on ro.id = eo.obj_id
                 where not exists (
                       select 1 from public.obj_srcs os where os.emp_obj_id = eo.id
                 )
                 order by eo.id
                """,
            )
        )
    return checks


def source_doc_checks(table_counts: Mapping[str, int]) -> list[RowCheck]:
    if not _has(table_counts, "src_docs"):
        return []
    return [
        RowCheck(
            "src_docs",
            "blank_source_identity",
            "error",
            "source documents must have non-blank src_key and title",
            """
            select id, src_key, title, volume, locator
              from public.src_docs
             where btrim(coalesce(src_key, '')) = ''
                or btrim(coalesce(title, '')) = ''
             order by id
            """,
        ),
        RowCheck(
            "src_docs",
            "duplicate_src_key",
            "error",
            "src_docs.src_key must be unique",
            """
            select src_key, count(*) as duplicate_count, array_agg(id order by id) as ids
              from public.src_docs
             group by src_key
            having count(*) > 1
             order by duplicate_count desc, src_key
            """,
        ),
    ]


def object_source_checks(table_counts: Mapping[str, int]) -> list[RowCheck]:
    if not _has(table_counts, "obj_srcs"):
        return []
    return [
        RowCheck(
            "obj_srcs",
            "object_source_orphan_reference",
            "error",
            "obj_srcs must reference existing object, emperor-object, source, item and rule rows",
            """
            select os.id, os.obj_id, os.emp_obj_id, os.doc_id, os.item_id, os.rule_id
              from public.obj_srcs os
              left join public.raw_objs ro on ro.id = os.obj_id
              left join public.emp_objs eo on eo.id = os.emp_obj_id
              left join public.src_docs sd on sd.id = os.doc_id
              left join public.eval_items i on i.id = os.item_id
              left join public.eval_rules r on r.id = os.rule_id
             where ro.id is null
                or eo.id is null
                or sd.id is null
                or i.id is null
                or r.id is null
             order by os.id
            """,
        ),
        RowCheck(
            "obj_srcs",
            "object_source_emp_object_mismatch",
            "error",
            "obj_srcs.obj_id must match emp_objs.obj_id for the same emp_obj_id",
            """
            select os.id, os.obj_id, os.emp_obj_id, eo.obj_id as expected_obj_id
              from public.obj_srcs os
              join public.emp_objs eo on eo.id = os.emp_obj_id
             where eo.obj_id <> os.obj_id
             order by os.id
            """,
        ),
        RowCheck(
            "obj_srcs",
            "rule_item_mismatch",
            "error",
            "obj_srcs.item_id must match eval_rules.item_id",
            """
            select os.id, os.item_id, os.rule_id, r.item_id as expected_item_id
              from public.obj_srcs os
              join public.eval_rules r on r.id = os.rule_id
             where r.item_id <> os.item_id
             order by os.id
            """,
        ),
        RowCheck(
            "obj_srcs",
            "invalid_direction",
            "error",
            "obj_srcs.direction must use the I5B finite-value registry",
            """
            select id, direction, note
              from public.obj_srcs
             where direction <> all(%s)
             order by id
            """,
            (list(ALLOWED_DIRECTIONS),),
        ),
        RowCheck(
            "obj_srcs",
            "duplicate_object_source_link",
            "error",
            "object source links must be unique by emp_obj/doc/item/rule/direction",
            """
            select emp_obj_id, doc_id, item_id, rule_id, direction,
                   count(*) as duplicate_count,
                   array_agg(id order by id) as ids
              from public.obj_srcs
             group by emp_obj_id, doc_id, item_id, rule_id, direction
            having count(*) > 1
             order by duplicate_count desc, emp_obj_id, doc_id
            """,
        ),
        RowCheck(
            "obj_srcs",
            "generic_or_todo_source_note",
            "error",
            "obj_srcs.note must describe a concrete sourced fact, not a placeholder or generic template",
            """
            select id, obj_id, emp_obj_id, note
              from public.obj_srcs
             where btrim(coalesce(note, '')) = ''
                or coalesce(note, '') ~ %s
             order by id
            """,
            (GENERIC_OBJ_SRC_NOTE_RE,),
        ),
        RowCheck(
            "obj_srcs",
            "ambiguous_source_note",
            "warning",
            "obj_srcs.note contains review language that may hide score-splitting or non-scoring semantics",
            """
            select id, obj_id, emp_obj_id, note
              from public.obj_srcs
             where coalesce(note, '') ~ %s
             order by id
            """,
            (AMBIGUOUS_OBJ_SRC_NOTE_RE,),
        ),
    ]


def object_attr_checks(table_counts: Mapping[str, int]) -> list[RowCheck]:
    if not _has(table_counts, "obj_attrs"):
        return []
    return [
        RowCheck(
            "obj_attrs",
            "object_attr_orphan_reference",
            "error",
            "obj_attrs must reference existing object, source and optional obj_src rows",
            """
            select oa.id, oa.obj_id, oa.doc_id, oa.obj_src_id, oa.attr_code
              from public.obj_attrs oa
              left join public.raw_objs ro on ro.id = oa.obj_id
              left join public.src_docs sd on sd.id = oa.doc_id
              left join public.obj_srcs os on os.id = oa.obj_src_id
             where ro.id is null
                or sd.id is null
                or (oa.obj_src_id is not null and os.id is null)
             order by oa.id
            """,
        ),
        RowCheck(
            "obj_attrs",
            "object_attr_source_mismatch",
            "error",
            "obj_attrs.obj_src_id must point to a source link for the same object",
            """
            select oa.id, oa.obj_id, oa.obj_src_id, os.obj_id as source_obj_id
              from public.obj_attrs oa
              join public.obj_srcs os on os.id = oa.obj_src_id
             where os.obj_id <> oa.obj_id
             order by oa.id
            """,
        ),
        RowCheck(
            "obj_attrs",
            "invalid_attr_code",
            "error",
            "obj_attrs.attr_code must use the I5B finite-value registry",
            """
            select id, obj_id, attr_code, value_text
              from public.obj_attrs
             where attr_code <> all(%s)
             order by id
            """,
            (list(OBJECT_ATTR_CODES),),
        ),
        RowCheck(
            "obj_attrs",
            "blank_attr_value",
            "error",
            "object attrs must have a text or numeric value",
            """
            select id, obj_id, attr_code, value_text, value_num
              from public.obj_attrs
             where btrim(coalesce(value_text, '')) = ''
               and value_num is null
             order by id
            """,
        ),
        RowCheck(
            "obj_attrs",
            "invalid_talent_quality_value",
            "error",
            "talent_quality must use the canonical talent-quality enum",
            """
            select id, obj_id, value_text
              from public.obj_attrs
             where attr_code = 'talent_quality'
               and value_text <> all(%s)
             order by id
            """,
            (list(CANONICAL_TALENT_QUALITY_VALUES),),
        ),
        RowCheck(
            "obj_attrs",
            "talent_quality_on_non_person",
            "error",
            "talent_quality is only valid for person objects",
            """
            select oa.id, oa.obj_id, ro.name, ro.obj_type, oa.value_text
              from public.obj_attrs oa
              join public.raw_objs ro on ro.id = oa.obj_id
             where oa.attr_code = 'talent_quality'
               and ro.obj_type <> 'person'
             order by oa.id
            """,
        ),
        RowCheck(
            "obj_attrs",
            "conflicting_talent_quality",
            "error",
            "one object must not carry multiple talent_quality values",
            """
            select obj_id, count(distinct value_text) as value_count,
                   array_agg(distinct value_text order by value_text) as values,
                   array_agg(id order by id) as attr_ids
              from public.obj_attrs
             where attr_code = 'talent_quality'
             group by obj_id
            having count(distinct value_text) > 1
             order by obj_id
            """,
        ),
        RowCheck(
            "obj_attrs",
            "duplicate_object_attr",
            "warning",
            "duplicate object attributes should be merged before reimport",
            """
            select obj_id, attr_code, value_text, value_num, doc_id,
                   count(*) as duplicate_count,
                   array_agg(id order by id) as attr_ids
              from public.obj_attrs
             group by obj_id, attr_code, value_text, value_num, doc_id
            having count(*) > 1
             order by duplicate_count desc, obj_id, attr_code
            """,
        ),
        RowCheck(
            "obj_attrs",
            "attr_doc_not_linked_on_object",
            "warning",
            "attribute source doc should also appear in obj_srcs for the same object",
            """
            select oa.id, oa.obj_id, oa.attr_code, oa.doc_id
              from public.obj_attrs oa
             where not exists (
                   select 1
                     from public.obj_srcs os
                    where os.obj_id = oa.obj_id
                      and os.doc_id = oa.doc_id
             )
             order by oa.id
            """,
        ),
    ]


def policy_checks(table_counts: Mapping[str, int]) -> list[RowCheck]:
    checks: list[RowCheck] = []
    if _has(table_counts, "eval_rule_material_policies", "eval_items", "eval_rules"):
        checks.extend(
            [
                RowCheck(
                    "eval_rule_material_policies",
                    "missing_active_rule_policy",
                    "error",
                    "each I5B eval_rule must have an active material policy",
                    """
                    select er.id as rule_id, er.rule_code
                      from public.eval_rules er
                      join public.eval_items i on i.id = er.item_id
                     where i.item_code = 'I5B'
                       and not exists (
                           select 1
                             from public.eval_rule_material_policies p
                            where p.status = 'active'
                              and p.item_id = i.id
                              and p.rule_id = er.id
                       )
                     order by er.rule_code
                    """,
                ),
                RowCheck(
                    "eval_rule_material_policies",
                    "policy_rule_identity_mismatch",
                    "error",
                    "policy item_code/rule_code must match linked eval_items/eval_rules",
                    """
                    select p.id, p.item_id, p.item_code, i.item_code as expected_item_code,
                           p.rule_id, p.rule_code, er.rule_code as expected_rule_code
                      from public.eval_rule_material_policies p
                      left join public.eval_items i on i.id = p.item_id
                      left join public.eval_rules er on er.id = p.rule_id
                     where (p.item_id is not null and (i.id is null or i.item_code <> p.item_code))
                        or (p.rule_id is not null and (er.id is null or er.rule_code <> p.rule_code))
                     order by p.id
                    """,
                ),
                RowCheck(
                    "eval_rule_material_policies",
                    "invalid_material_source",
                    "error",
                    "policy material_source must use the runtime policy enum",
                    """
                    select id, rule_code, material_source
                      from public.eval_rule_material_policies
                     where material_source <> all(%s)
                     order by id
                    """,
                    (list(POLICY_MATERIAL_SOURCES),),
                ),
                RowCheck(
                    "eval_rule_material_policies",
                    "team_building_policy_not_specialized",
                    "error",
                    "team_building must use high-priority emp_objs policy with talent_quality requirement",
                    """
                    select id, rule_code, selection_priority, material_source, require_attrs
                      from public.eval_rule_material_policies
                     where status = 'active'
                       and rule_code = 'team_building'
                       and (
                           material_source <> 'emp_objs'
                           or selection_priority > 50
                           or not ('talent_quality' = any(require_attrs))
                       )
                     order by id
                    """,
                ),
            ]
        )
    if _has(table_counts, "fact_relation_predicate_options"):
        checks.append(
            RowCheck(
                "fact_relation_predicate_options",
                "invalid_predicate_option_direction",
                "error",
                "predicate option direction must use the evidence direction enum",
                """
                select id, rule_code, predicate, direction
                  from public.fact_relation_predicate_options
                 where direction <> all(%s)
                 order by id
                """,
                (list(ALLOWED_DIRECTIONS),),
            )
        )
    return checks




def core_checks(table_counts: Mapping[str, int]) -> list[RowCheck]:
    checks: list[RowCheck] = []
    checks.extend(raw_object_checks(table_counts))
    checks.extend(alias_checks(table_counts))
    checks.extend(emperor_object_checks(table_counts))
    checks.extend(source_doc_checks(table_counts))
    checks.extend(object_source_checks(table_counts))
    checks.extend(object_attr_checks(table_counts))
    checks.extend(policy_checks(table_counts))
    return checks
