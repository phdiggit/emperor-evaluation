create or replace view retrieval_v3.v_team_building_talent_candidates as
select
    p.id as policy_id,p.policy_code,p.selection_priority,p.rule_code,p.require_attrs,
    rt.id as target_id,rt.target_code,tob.id as target_object_id,tob.target_object_code,
    o.id as object_id,o.object_code,o.canonical_name,pp.id as person_profile_id,
    pp.person_profile_code,pp.talent_grade,
    case pp.talent_grade::text
        when 'historic_talent' then '历史级人才'
        when 'top_talent' then '顶级人才'
        when 'important_talent' then '重要人才'
        when 'usable_talent' then '可用人才'
        when 'ordinary_talent' then '普通人才'
    end as talent_quality_label,
    'rule_requirement'::retrieval_v3.rv3_target_object_attribute_kind as attribute_kind,
    'talent_quality'::text as attribute_code,
    pp.review_status as profile_review_status,tob.review_status as target_object_review_status
from retrieval_v3.eval_rule_material_policies p
join retrieval_v3.target_objects tob on tob.scope_code='item'
join retrieval_v3.retrieval_targets rt on rt.id=tob.target_id and rt.item_code=p.item_code
join retrieval_v3.objects o on o.id=tob.object_id and o.object_type='person' and o.identity_status='active'
join retrieval_v3.person_profiles pp
  on pp.object_id=o.id and pp.review_status='accepted' and pp.talent_grade is not null
 and pp.talent_grade_version in ('talent-grade-v1','talent-grade-v2','talent-grade-v3','talent-grade-v4')
where p.rule_code='team_building' and p.policy_status='active'
  and p.require_attrs @> array['talent_quality']::text[]
  and (p.candidate_obj_types=array[]::text[] or 'person'=any(p.candidate_obj_types));

comment on column retrieval_v3.person_profiles.talent_grade_version is '人才等级规则版本；talent-grade-v4 增加传世军事理论加成并要求治理人物横向一致性。';
