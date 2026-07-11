do $$
begin
    if not exists (
        select 1 from pg_type t join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v3' and t.typname = 'rv3_authority_consensus'
    ) then
        create type retrieval_v3.rv3_authority_consensus as enum (
            'none', 'weak', 'moderate', 'strong', 'disputed'
        );
    end if;
    if not exists (
        select 1 from pg_type t join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v3' and t.typname = 'rv3_evidence_strength'
    ) then
        create type retrieval_v3.rv3_evidence_strength as enum (
            'none', 'weak', 'moderate', 'strong'
        );
    end if;
    if not exists (
        select 1 from pg_type t join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v3' and t.typname = 'rv3_evidence_coverage'
    ) then
        create type retrieval_v3.rv3_evidence_coverage as enum (
            'insufficient', 'partial', 'substantial', 'comprehensive'
        );
    end if;
    if not exists (
        select 1 from pg_type t join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v3' and t.typname = 'rv3_negative_talent_severity'
    ) then
        create type retrieval_v3.rv3_negative_talent_severity as enum (
            'minor', 'material', 'major', 'historic'
        );
    end if;
end $$;

do $$
begin
    alter type retrieval_v3.rv3_negative_talent_class add value if not exists 'favorite';
    alter type retrieval_v3.rv3_negative_talent_class add value if not exists 'power_abuser';
    alter type retrieval_v3.rv3_negative_talent_class add value if not exists 'framer';
    alter type retrieval_v3.rv3_negative_talent_class add value if not exists 'extractive_official';
    alter type retrieval_v3.rv3_negative_talent_class add value if not exists 'cruel_official';
    alter type retrieval_v3.rv3_negative_talent_class add value if not exists 'incompetent_harmful';
    alter type retrieval_v3.rv3_negative_talent_class add value if not exists 'traitorous_actor';
    alter type retrieval_v3.rv3_negative_talent_class add value if not exists 'mixed_or_disputed';
end $$;

alter table retrieval_v3.person_profiles
    add column if not exists talent_grade_confidence numeric(5,4),
    add column if not exists talent_authority_consensus retrieval_v3.rv3_authority_consensus,
    add column if not exists talent_performance_support retrieval_v3.rv3_evidence_strength,
    add column if not exists talent_evidence_coverage retrieval_v3.rv3_evidence_coverage,
    add column if not exists negative_talent_severity retrieval_v3.rv3_negative_talent_severity,
    add column if not exists negative_talent_confidence numeric(5,4),
    add column if not exists negative_authority_consensus retrieval_v3.rv3_authority_consensus,
    add column if not exists negative_fact_support retrieval_v3.rv3_evidence_strength,
    add column if not exists negative_evidence_coverage retrieval_v3.rv3_evidence_coverage,
    add column if not exists negative_talent_basis text not null default '',
    add column if not exists negative_talent_version text not null default '';

alter table retrieval_v3.person_profiles
    drop constraint if exists rv3_person_profiles_talent_grade_confidence_ck,
    drop constraint if exists rv3_person_profiles_negative_talent_confidence_ck,
    drop constraint if exists rv3_person_profiles_negative_talent_shape_ck,
    drop constraint if exists rv3_person_profiles_negative_talent_class_v2_ck;

alter table retrieval_v3.person_profiles
    add constraint rv3_person_profiles_talent_grade_confidence_ck check (
        talent_grade_confidence is null
        or (talent_grade_confidence >= 0 and talent_grade_confidence <= 1)
    ),
    add constraint rv3_person_profiles_negative_talent_confidence_ck check (
        negative_talent_confidence is null
        or (negative_talent_confidence >= 0 and negative_talent_confidence <= 1)
    ),
    add constraint rv3_person_profiles_negative_talent_class_v2_ck check (
        negative_talent_class is null
        or negative_talent_class::text in (
            'sycophant', 'favorite', 'power_abuser', 'framer',
            'extractive_official', 'cruel_official', 'incompetent_harmful',
            'traitorous_actor', 'mixed_or_disputed'
        )
    ),
    add constraint rv3_person_profiles_negative_talent_shape_ck check (
        (negative_talent_class is null and negative_talent_severity is null)
        or (negative_talent_class is not null and negative_talent_severity is not null)
    );

comment on type retrieval_v3.rv3_authority_consensus is '史论权威共识强度：none 无有效评价，weak 单一或弱来源，moderate 多条但独立性有限，strong 多个相对独立来源稳定一致，disputed 权威来源明显冲突。';
comment on type retrieval_v3.rv3_evidence_strength is '事实证据支持强度：none 无事实支撑，weak 少量或间接支撑，moderate 有明确但不完整支撑，strong 多项直接且一致的事实支撑。';
comment on type retrieval_v3.rv3_evidence_coverage is '人物证据覆盖度：insufficient 不足以稳定判断，partial 只覆盖部分领域或时期，substantial 覆盖主要领域，comprehensive 主要领域与长期影响均有充分覆盖。';
comment on type retrieval_v3.rv3_negative_talent_severity is '人物负面政治风险严重度：minor 局部轻微，material 已造成实质损害，major 政权或大范围重大损害，historic 形成结构性且跨时代的负面标杆。';
comment on type retrieval_v3.rv3_negative_talent_class is '人物负面政治风险类型；sycophant 谄媚迎合，favorite 依赖私人宠信，power_abuser 滥权专权，framer 构陷制造冤害，extractive_official 聚敛盘剥，cruel_official 酷烈滥刑，incompetent_harmful 居关键位置且无能致害，traitorous_actor 明确背叛共同体，mixed_or_disputed 来源冲突。旧值 major_sycophant 与 historic_sycophant 仅为枚举兼容，不允许写入 v2 画像。';

comment on column retrieval_v3.person_profiles.talent_grade_confidence is '人才等级结论置信度，范围 0 到 1；与人物等级分离，避免把材料不足直接解释为低能力。';
comment on column retrieval_v3.person_profiles.talent_authority_consensus is '人才能力的正史论赞、后世史论和现代研究权威共识强度。';
comment on column retrieval_v3.person_profiles.talent_performance_support is '具体事迹对人才等级的事实校准支持强度，不单独承担全局定级。';
comment on column retrieval_v3.person_profiles.talent_evidence_coverage is '人才能力材料对主要领域、时期和长期影响的覆盖程度。';
comment on column retrieval_v3.person_profiles.negative_talent_class is '人物负面政治风险类型；与人才能力等级正交，高能力人物也可以具有负面风险。';
comment on column retrieval_v3.person_profiles.negative_talent_severity is '人物负面政治风险造成损害的严重度；不得由能力等级、被诛被贬或政治结局直接推导。';
comment on column retrieval_v3.person_profiles.negative_talent_confidence is '负面政治风险结论置信度，范围 0 到 1。';
comment on column retrieval_v3.person_profiles.negative_authority_consensus is '正史论赞、后世史论和现代研究对负面政治风险定性的共识强度。';
comment on column retrieval_v3.person_profiles.negative_fact_support is '具体行为和后果对负面政治风险定性的事实支持强度。';
comment on column retrieval_v3.person_profiles.negative_evidence_coverage is '负面政治风险材料对相关时期、行为类型和后果的覆盖程度。';
comment on column retrieval_v3.person_profiles.negative_talent_basis is '负面政治风险中文依据；应区分能力、品格、政治立场与胜者叙事，并记录主要反证或争议。';
comment on column retrieval_v3.person_profiles.negative_talent_version is '负面政治风险分类规则版本；当前目标版本为 negative-talent-v1。';
comment on column retrieval_v3.person_profiles.talent_grade_version is '人才等级规则版本；talent-grade-v1 为事迹绩效试评，talent-grade-v2 为史论共识基础加事实校准。';

create index if not exists rv3_person_profiles_talent_v2_idx
on retrieval_v3.person_profiles(talent_grade_version, talent_grade, talent_authority_consensus, review_status);

create index if not exists rv3_person_profiles_negative_v1_idx
on retrieval_v3.person_profiles(negative_talent_version, negative_talent_class, negative_talent_severity, review_status);

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
 and pp.talent_grade_version in ('talent-grade-v1', 'talent-grade-v2')
where p.rule_code = 'team_building'
  and p.policy_status = 'active'
  and p.require_attrs @> array['talent_quality']::text[]
  and (p.candidate_obj_types = array[]::text[] or 'person' = any(p.candidate_obj_types));
