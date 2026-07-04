create table if not exists public.eval_rule_material_policies (
    id bigint generated always as identity primary key,
    item_id bigint references public.eval_items(id) on delete restrict,
    item_code text not null default '',
    rule_id bigint references public.eval_rules(id) on delete restrict,
    rule_code text not null default '',
    policy_code text not null,
    policy_version text not null default 'v1',
    selection_priority integer not null default 100,
    carrier_mode text not null default 'obj_src_material',
    material_source text not null default 'obj_srcs',
    allowed_scoring_roles text[] not null default array[]::text[],
    context_roles text[] not null default array[]::text[],
    disallowed_scored_obj_types text[] not null default array[]::text[],
    discouraged_scored_obj_types text[] not null default array[]::text[],
    candidate_obj_types text[] not null default array[]::text[],
    require_attrs text[] not null default array[]::text[],
    calc_detail_component_paths text[] not null default array[]::text[],
    single_scored_per_chain boolean not null default false,
    policy_payload jsonb not null default '{}'::jsonb,
    description text not null default '',
    note text not null default '',
    status public.eval_lifecycle_status not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint eval_rule_material_policies_item_code_not_blank check (item_id is null or btrim(item_code) <> ''),
    constraint eval_rule_material_policies_rule_code_not_blank check (rule_id is null or btrim(rule_code) <> ''),
    constraint eval_rule_material_policies_policy_code_not_blank check (btrim(policy_code) <> ''),
    constraint eval_rule_material_policies_policy_version_not_blank check (btrim(policy_version) <> ''),
    constraint eval_rule_material_policies_carrier_mode_not_blank check (btrim(carrier_mode) <> ''),
    constraint eval_rule_material_policies_material_source_not_blank check (btrim(material_source) <> ''),
    constraint eval_rule_material_policies_selection_priority_positive check (selection_priority > 0)
);

create unique index if not exists eval_rule_material_policies_active_uk
on public.eval_rule_material_policies (
    coalesce(item_id, 0),
    coalesce(rule_id, 0),
    policy_code,
    policy_version
)
where status = 'active';

create index if not exists eval_rule_material_policies_lookup_idx
on public.eval_rule_material_policies(item_code, rule_code, selection_priority, status);

with seed as (
    select *
    from (
        values
            (
                'talent_discovery',
                'person_material_policy',
                100,
                'obj_src_material',
                'obj_srcs',
                array['discovered_talent','recommended_talent','recognized_talent','missed_talent']::text[],
                array['source_context','event_context','mechanism_context']::text[],
                array['mechanism']::text[],
                array['event','group']::text[],
                array[]::text[],
                array[]::text[],
                array[]::text[],
                false,
                jsonb_build_object(
                    'context_roles_by_obj_type', jsonb_build_object(
                        'mechanism', 'mechanism_context',
                        'event', 'event_context',
                        'group', 'source_context'
                    ),
                    'default_scoring_roles_by_direction', jsonb_build_object(
                        'non_negative', 'discovered_talent',
                        'negative', 'missed_talent'
                    )
                ),
                '发现人才：以具体人才材料为主要计分承载。'
            ),
            (
                'appointment_trust',
                'person_material_policy',
                100,
                'obj_src_material',
                'obj_srcs',
                array['appointed_talent','trusted_minister','entrusted_official','misappointed_person','suppressed_talent']::text[],
                array['source_context','event_context','mechanism_context']::text[],
                array['mechanism']::text[],
                array['event','group']::text[],
                array[]::text[],
                array[]::text[],
                array[]::text[],
                false,
                jsonb_build_object(
                    'context_roles_by_obj_type', jsonb_build_object(
                        'mechanism', 'mechanism_context',
                        'event', 'event_context',
                        'group', 'source_context'
                    ),
                    'default_scoring_roles_by_direction', jsonb_build_object(
                        'non_negative', 'trusted_minister',
                        'negative', 'misappointed_person'
                    )
                ),
                '任人信任：以具体被任用、被信任或误任人物为主要计分承载。'
            ),
            (
                'delegation',
                'person_material_policy',
                100,
                'obj_src_material',
                'obj_srcs',
                array['delegated_actor','authority_recipient','authority_revoked_target','misdelegated_actor']::text[],
                array['source_context','event_context','mechanism_context']::text[],
                array['mechanism']::text[],
                array['event','group']::text[],
                array[]::text[],
                array[]::text[],
                array[]::text[],
                false,
                jsonb_build_object(
                    'context_roles_by_obj_type', jsonb_build_object(
                        'mechanism', 'mechanism_context',
                        'event', 'event_context',
                        'group', 'source_context'
                    ),
                    'default_scoring_roles_by_direction', jsonb_build_object(
                        'non_negative', 'delegated_actor',
                        'negative', 'misdelegated_actor'
                    )
                ),
                '合理授权：以获得授权、被撤权或被错授的人物为主要计分承载。'
            ),
            (
                'team_building',
                'team_core_member_policy',
                10,
                'team_core_members',
                'emp_objs',
                array['team_member','negative_team_member']::text[],
                array['source_context','event_context','mechanism_context']::text[],
                array['mechanism','event','group']::text[],
                array[]::text[],
                array['person']::text[],
                array['talent_quality']::text[],
                array['team_quality_components','materials']::text[],
                false,
                jsonb_build_object(
                    'context_roles_by_obj_type', jsonb_build_object(
                        'mechanism', 'mechanism_context',
                        'event', 'event_context',
                        'group', 'source_context'
                    ),
                    'default_scoring_roles_by_direction', jsonb_build_object(
                        'non_negative', 'team_member',
                        'negative', 'negative_team_member'
                    )
                ),
                '建立团队：优先扫描带人才等级的人物 emp_objs，再用团队质量组件确认覆盖。'
            ),
            (
                'tolerate_talent',
                'single_person_chain_policy',
                100,
                'obj_src_material',
                'obj_srcs',
                array['protected_talent','remonstrance_actor','expression_safety_unit','harmed_talent']::text[],
                array['actor_context','event_context','group_context','mechanism_context','source_context']::text[],
                array['event','group','mechanism']::text[],
                array[]::text[],
                array[]::text[],
                array[]::text[],
                array[]::text[],
                true,
                jsonb_build_object(
                    'context_roles_by_obj_type', jsonb_build_object(
                        'mechanism', 'mechanism_context',
                        'event', 'event_context',
                        'group', 'group_context'
                    ),
                    'candidate_role_rules', jsonb_build_array(
                        jsonb_build_object('when', jsonb_build_object('side', 'positive', 'obj_type', 'person'), 'role', 'protected_talent'),
                        jsonb_build_object('when', jsonb_build_object('side', 'negative', 'obj_type', 'person'), 'role', 'harmed_talent')
                    ),
                    'default_scoring_roles_by_direction', jsonb_build_object(
                        'non_negative', 'protected_talent',
                        'negative', 'harmed_talent'
                    )
                ),
                '容人保全：同一因果链默认只允许一个人物计分承载，事件和机制作为上下文。'
            ),
            (
                'anti_nepotism',
                'person_material_policy',
                100,
                'obj_src_material',
                'obj_srcs',
                array['anti_nepotism_resisted_actor','nepotistic_beneficiary','favorite_beneficiary','appointment_interferer']::text[],
                array['actor_context','event_context','group_context','mechanism_context','source_context']::text[],
                array['event','group','mechanism']::text[],
                array[]::text[],
                array[]::text[],
                array[]::text[],
                array[]::text[],
                false,
                jsonb_build_object(
                    'context_roles_by_obj_type', jsonb_build_object(
                        'mechanism', 'mechanism_context',
                        'event', 'event_context',
                        'group', 'group_context'
                    ),
                    'candidate_role_rules', jsonb_build_array(
                        jsonb_build_object('when', jsonb_build_object('side', 'positive'), 'role', 'anti_nepotism_resisted_actor'),
                        jsonb_build_object('when', jsonb_build_object('obj_type', 'person', 'name_prefixes', jsonb_build_array('武')), 'role', 'nepotistic_beneficiary'),
                        jsonb_build_object('when', jsonb_build_object('obj_type', 'person', 'names', jsonb_build_array('张易之','张昌宗','薛怀义')), 'role', 'favorite_beneficiary')
                    ),
                    'default_scoring_roles_by_direction', jsonb_build_object(
                        'non_negative', 'anti_nepotism_resisted_actor',
                        'negative', 'appointment_interferer'
                    )
                ),
                '抑制亲私：以具体受益、干预或抵制偏私的人物为主要计分承载。'
            )
    ) as seed(
        rule_code,
        policy_code,
        selection_priority,
        carrier_mode,
        material_source,
        allowed_scoring_roles,
        context_roles,
        disallowed_scored_obj_types,
        discouraged_scored_obj_types,
        candidate_obj_types,
        require_attrs,
        calc_detail_component_paths,
        single_scored_per_chain,
        policy_payload,
        description
    )
)
insert into public.eval_rule_material_policies (
    item_id,
    item_code,
    rule_id,
    rule_code,
    policy_code,
    selection_priority,
    carrier_mode,
    material_source,
    allowed_scoring_roles,
    context_roles,
    disallowed_scored_obj_types,
    discouraged_scored_obj_types,
    candidate_obj_types,
    require_attrs,
    calc_detail_component_paths,
    single_scored_per_chain,
    policy_payload,
    description
)
select
    i.id,
    i.item_code,
    r.id,
    r.rule_code,
    seed.policy_code,
    seed.selection_priority,
    seed.carrier_mode,
    seed.material_source,
    seed.allowed_scoring_roles,
    seed.context_roles,
    seed.disallowed_scored_obj_types,
    seed.discouraged_scored_obj_types,
    seed.candidate_obj_types,
    seed.require_attrs,
    seed.calc_detail_component_paths,
    seed.single_scored_per_chain,
    seed.policy_payload,
    seed.description
  from seed
  join public.eval_items i on i.item_code = 'I5B'
  join public.eval_rules r on r.item_id = i.id and r.rule_code = seed.rule_code
 where not exists (
    select 1
      from public.eval_rule_material_policies existing
     where existing.status = 'active'
       and existing.item_id = i.id
       and existing.rule_id = r.id
       and existing.policy_code = seed.policy_code
       and existing.policy_version = 'v1'
);

drop view if exists public.v_eval_rule_material_policies_by_id;

create view public.v_eval_rule_material_policies_by_id as
select
    policy.id,
    policy.item_id,
    policy.item_code,
    policy.rule_id,
    policy.rule_code,
    policy.policy_code,
    policy.policy_version,
    policy.selection_priority,
    policy.carrier_mode,
    policy.material_source,
    policy.allowed_scoring_roles,
    policy.context_roles,
    policy.disallowed_scored_obj_types,
    policy.discouraged_scored_obj_types,
    policy.candidate_obj_types,
    policy.require_attrs,
    policy.calc_detail_component_paths,
    policy.single_scored_per_chain,
    policy.policy_payload,
    policy.description,
    policy.note,
    policy.status,
    policy.created_at,
    policy.updated_at
from public.eval_rule_material_policies policy
order by policy.id;

comment on table public.eval_rule_material_policies is '规则材料选择策略表：定义某 item/rule 如何筛选计分承载对象、上下文角色和覆盖审计候选。运行时代码只读本表，不读取评分规则文档。';
comment on column public.eval_rule_material_policies.id is '规则材料策略主键。';
comment on column public.eval_rule_material_policies.item_id is '策略所属评价分项；为空时表示跨分项通用策略。';
comment on column public.eval_rule_material_policies.item_code is '评价分项代码冗余字段，便于人工查询和跨项目同步。';
comment on column public.eval_rule_material_policies.rule_id is '策略所属评价规则；为空时表示分项内通用策略。';
comment on column public.eval_rule_material_policies.rule_code is '评价规则代码冗余字段，便于人工查询和跨项目同步。';
comment on column public.eval_rule_material_policies.policy_code is '策略稳定代码，例如 person_material_policy 或 team_core_member_policy。';
comment on column public.eval_rule_material_policies.policy_version is '策略版本；同一 rule 规则变化时新建版本并退役旧版本。';
comment on column public.eval_rule_material_policies.selection_priority is '策略选择优先级，数字越小优先级越高。特殊材料筛选规则应高于普通 obj_srcs 材料策略。';
comment on column public.eval_rule_material_policies.carrier_mode is '计分承载模式，例如 obj_src_material、team_core_members。';
comment on column public.eval_rule_material_policies.material_source is '候选材料来源，例如 obj_srcs、emp_objs、calc_detail。';
comment on column public.eval_rule_material_policies.allowed_scoring_roles is '本 rule 允许作为计分承载的 scoring_role 枚举。';
comment on column public.eval_rule_material_policies.context_roles is '本 rule 允许作为上下文成员的 role 枚举。';
comment on column public.eval_rule_material_policies.disallowed_scored_obj_types is '禁止作为计分承载的 raw_objs.obj_type 枚举。';
comment on column public.eval_rule_material_policies.discouraged_scored_obj_types is '通常不建议作为计分承载的 raw_objs.obj_type 枚举；审计为 warning。';
comment on column public.eval_rule_material_policies.candidate_obj_types is '覆盖审计候选对象类型过滤；为空表示不额外限制。';
comment on column public.eval_rule_material_policies.require_attrs is '覆盖审计候选必须具备的 obj_attrs.attr_code；为空表示不额外要求。';
comment on column public.eval_rule_material_policies.calc_detail_component_paths is '从 calc_detail 识别已覆盖对象的组件路径；为空时使用材料 id 覆盖。';
comment on column public.eval_rule_material_policies.single_scored_per_chain is '是否要求同一因果链最多一个计分承载单元。';
comment on column public.eval_rule_material_policies.policy_payload is '结构化补充策略，只存脚本可读枚举和匹配条件，不存评分文档原文。';
comment on column public.eval_rule_material_policies.description is '中文语义说明，给人工审计和脚本报告使用。';
comment on column public.eval_rule_material_policies.note is '维护备注；默认留空，只写单条策略的特殊边界或迁移状态。';
comment on column public.eval_rule_material_policies.status is '行生命周期状态：active 当前有效，inactive 暂不使用，retired 历史退役。';
comment on column public.eval_rule_material_policies.created_at is '记录创建时间。';
comment on column public.eval_rule_material_policies.updated_at is '记录最近更新时间。';
comment on view public.v_eval_rule_material_policies_by_id is '规则材料策略人工查看视图，按主键展开当前策略字段。';
