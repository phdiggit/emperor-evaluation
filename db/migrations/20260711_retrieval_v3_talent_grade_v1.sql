do $$
begin
    alter type retrieval_v3.rv3_person_talent_grade add value if not exists 'usable_talent' after 'ordinary_talent';
exception
    when duplicate_object then null;
end $$;

do $$
begin
    if not exists (
        select 1 from pg_type t join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v3' and t.typname = 'rv3_negative_talent_class'
    ) then
        create type retrieval_v3.rv3_negative_talent_class as enum (
            'sycophant', 'major_sycophant', 'historic_sycophant'
        );
    end if;
end $$;

alter table retrieval_v3.person_profiles
    add column if not exists negative_talent_class retrieval_v3.rv3_negative_talent_class,
    add column if not exists talent_grade_version text not null default '';

alter table retrieval_v3.person_profiles
    drop constraint if exists rv3_person_profiles_talent_grade_v1_ck;

alter table retrieval_v3.person_profiles
    add constraint rv3_person_profiles_talent_grade_v1_ck check (
        talent_grade is null
        or talent_grade::text in (
            'ordinary_talent', 'usable_talent', 'important_talent', 'top_talent', 'historic_talent'
        )
    );

comment on column retrieval_v3.person_profiles.talent_grade is '人物全局能力与历史影响等级；只允许普通、可用、重要、顶级、历史级人才，不承载政治品格或佞幸分类。';
comment on column retrieval_v3.person_profiles.negative_talent_class is '人物政治危害类型；与人才能力等级正交，可与高能力等级同时存在。';
comment on column retrieval_v3.person_profiles.talent_grade_version is '人才等级 rubric 版本；当前正式版本为 talent-grade-v1。';

create or replace view retrieval_v3.v_team_building_talent_candidates as
select
    p.id as policy_id,
    p.policy_code,
    p.selection_priority,
    p.rule_code,
    p.require_attrs,
    rt.id as target_id,
    rt.target_code,
    tob.id as target_object_id,
    tob.target_object_code,
    o.id as object_id,
    o.object_code,
    o.canonical_name,
    pp.id as person_profile_id,
    pp.person_profile_code,
    pp.talent_grade,
    case pp.talent_grade::text
        when 'historic_talent' then '历史级人才'
        when 'top_talent' then '顶级人才'
        when 'important_talent' then '重要人才'
        when 'usable_talent' then '可用人才'
        when 'ordinary_talent' then '普通人才'
    end as talent_quality_label,
    'rule_requirement'::retrieval_v3.rv3_target_object_attribute_kind as attribute_kind,
    'talent_quality'::text as attribute_code,
    pp.review_status as profile_review_status,
    tob.review_status as target_object_review_status
from retrieval_v3.eval_rule_material_policies p
join retrieval_v3.target_objects tob on tob.scope_code = 'item'
join retrieval_v3.retrieval_targets rt on rt.id = tob.target_id and rt.item_code = p.item_code
join retrieval_v3.objects o on o.id = tob.object_id and o.object_type = 'person'
join retrieval_v3.person_profiles pp
  on pp.object_id = o.id
 and pp.review_status = 'accepted'
 and pp.talent_grade is not null
 and pp.talent_grade_version = 'talent-grade-v1'
where p.rule_code = 'team_building'
  and p.policy_status = 'active'
  and p.require_attrs @> array['talent_quality']::text[]
  and (p.candidate_obj_types = array[]::text[] or 'person' = any(p.candidate_obj_types));
