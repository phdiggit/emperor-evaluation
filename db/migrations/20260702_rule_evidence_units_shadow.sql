do $$
begin
    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'public'
           and t.typname = 'eval_lifecycle_status'
    ) then
        execute 'create domain public.eval_lifecycle_status as text check (value in (''active'', ''inactive'', ''retired''))';
    end if;

    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'public'
           and t.typname = 'eval_review_status'
    ) then
        execute 'create domain public.eval_review_status as text check (value in (''draft'', ''needs_review'', ''accepted'', ''rejected''))';
    end if;

    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'public'
           and t.typname = 'eval_source_method'
    ) then
        execute 'create domain public.eval_source_method as text check (value in (''manual'', ''candidate_from_obj_srcs'', ''candidate_from_calc_detail'', ''candidate_from_payload'', ''db_backfill''))';
    end if;

    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'public'
           and t.typname = 'evidence_direction'
    ) then
        execute 'create domain public.evidence_direction as text check (value in (''positive'', ''negative'', ''neutral'', ''mixed''))';
    end if;

    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'public'
           and t.typname = 'rule_evidence_score_mode'
    ) then
        execute 'create domain public.rule_evidence_score_mode as text check (value in (''shadow'', ''scoring'', ''rejected''))';
    end if;
end;
$$;

create table if not exists public.fact_relations (
    id bigint generated always as identity primary key,
    emp_id bigint not null references public.emps(id) on delete cascade,
    item_id bigint references public.eval_items(id) on delete restrict,
    item_code text not null default '',
    rule_id bigint references public.eval_rules(id) on delete restrict,
    rule_code text not null default '',
    subject_obj_id bigint not null references public.raw_objs(id) on delete cascade,
    predicate text not null,
    object_obj_id bigint references public.raw_objs(id) on delete set null,
    doc_id bigint references public.src_docs(id) on delete set null,
    obj_src_id bigint references public.obj_srcs(id) on delete set null,
    causal_chain_key text not null,
    relation_role text not null default 'context',
    confidence numeric(5,4) not null default 0.8500,
    source_method public.eval_source_method not null default 'manual',
    review_status public.eval_review_status not null default 'draft',
    review_note text not null default '',
    note text not null default '',
    status public.eval_lifecycle_status not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint fact_relations_item_code_not_blank check (item_id is null or btrim(item_code) <> ''),
    constraint fact_relations_rule_code_not_blank check (rule_id is null or btrim(rule_code) <> ''),
    constraint fact_relations_predicate_not_blank check (btrim(predicate) <> ''),
    constraint fact_relations_chain_key_not_blank check (btrim(causal_chain_key) <> ''),
    constraint fact_relations_relation_role_not_blank check (btrim(relation_role) <> ''),
    constraint fact_relations_confidence_range check (confidence >= 0 and confidence <= 1)
);

create unique index if not exists fact_relations_active_uk
on public.fact_relations (
    emp_id,
    coalesce(item_id, 0),
    coalesce(rule_id, 0),
    subject_obj_id,
    predicate,
    coalesce(object_obj_id, 0),
    coalesce(obj_src_id, 0),
    causal_chain_key
)
where status = 'active';

create index if not exists fact_relations_lookup_idx
on public.fact_relations(emp_id, item_code, rule_code, causal_chain_key, review_status, status);

create index if not exists fact_relations_subject_idx
on public.fact_relations(subject_obj_id);

create index if not exists fact_relations_object_idx
on public.fact_relations(object_obj_id);

create table if not exists public.fact_relation_predicate_options (
    id bigint generated always as identity primary key,
    item_id bigint references public.eval_items(id) on delete restrict,
    item_code text not null default '',
    rule_id bigint references public.eval_rules(id) on delete restrict,
    rule_code text not null default '',
    scoring_role text not null default '',
    predicate text not null,
    relation_role text not null default 'scored_candidate',
    subject_obj_type text not null default 'person',
    object_obj_type text not null default '',
    direction public.evidence_direction not null,
    description text not null default '',
    note text not null default '',
    status public.eval_lifecycle_status not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint fact_relation_predicate_options_item_code_not_blank check (item_id is null or btrim(item_code) <> ''),
    constraint fact_relation_predicate_options_rule_code_not_blank check (rule_id is null or btrim(rule_code) <> ''),
    constraint fact_relation_predicate_options_scoring_role_not_blank check (btrim(scoring_role) <> ''),
    constraint fact_relation_predicate_options_predicate_not_blank check (btrim(predicate) <> ''),
    constraint fact_relation_predicate_options_relation_role_not_blank check (btrim(relation_role) <> ''),
    constraint fact_relation_predicate_options_subject_type_not_blank check (btrim(subject_obj_type) <> '')
);

create unique index if not exists fact_relation_predicate_options_active_uk
on public.fact_relation_predicate_options (
    coalesce(item_id, 0),
    coalesce(rule_id, 0),
    scoring_role,
    predicate,
    relation_role,
    subject_obj_type,
    object_obj_type,
    direction
)
where status = 'active';

create index if not exists fact_relation_predicate_options_lookup_idx
on public.fact_relation_predicate_options(item_code, rule_code, scoring_role, predicate, relation_role, status);

create table if not exists public.rule_evidence_units (
    id bigint generated always as identity primary key,
    emp_id bigint not null references public.emps(id) on delete cascade,
    item_id bigint not null references public.eval_items(id) on delete restrict,
    item_code text not null,
    rule_id bigint not null references public.eval_rules(id) on delete restrict,
    rule_code text not null,
    causal_chain_key text not null,
    scored_obj_id bigint references public.raw_objs(id) on delete set null,
    scored_obj_src_id bigint references public.obj_srcs(id) on delete set null,
    scoring_role text not null,
    direction public.evidence_direction not null,
    score_mode public.rule_evidence_score_mode not null default 'shadow',
    source_method public.eval_source_method not null default 'manual',
    review_status public.eval_review_status not null default 'draft',
    review_note text not null default '',
    note text not null default '',
    status public.eval_lifecycle_status not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rule_evidence_units_item_code_not_blank check (btrim(item_code) <> ''),
    constraint rule_evidence_units_rule_code_not_blank check (btrim(rule_code) <> ''),
    constraint rule_evidence_units_chain_key_not_blank check (btrim(causal_chain_key) <> ''),
    constraint rule_evidence_units_scoring_role_not_blank check (btrim(scoring_role) <> '')
);

create unique index if not exists rule_evidence_units_active_uk
on public.rule_evidence_units (
    emp_id,
    item_id,
    rule_id,
    causal_chain_key,
    scoring_role,
    coalesce(scored_obj_id, 0),
    coalesce(scored_obj_src_id, 0)
)
where status = 'active';

create index if not exists rule_evidence_units_lookup_idx
on public.rule_evidence_units(emp_id, item_code, rule_code, causal_chain_key, score_mode, review_status, status);

create index if not exists rule_evidence_units_scored_obj_idx
on public.rule_evidence_units(scored_obj_id);

create table if not exists public.rule_evidence_unit_members (
    id bigint generated always as identity primary key,
    unit_id bigint not null references public.rule_evidence_units(id) on delete cascade,
    obj_id bigint references public.raw_objs(id) on delete set null,
    obj_src_id bigint references public.obj_srcs(id) on delete set null,
    relation_id bigint references public.fact_relations(id) on delete set null,
    member_role text not null,
    source_method public.eval_source_method not null default 'manual',
    review_status public.eval_review_status not null default 'draft',
    review_note text not null default '',
    note text not null default '',
    status public.eval_lifecycle_status not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rule_evidence_unit_members_role_not_blank check (btrim(member_role) <> ''),
    constraint rule_evidence_unit_members_has_anchor check (
        obj_id is not null or obj_src_id is not null or relation_id is not null
    )
);

create unique index if not exists rule_evidence_unit_members_active_uk
on public.rule_evidence_unit_members (
    unit_id,
    member_role,
    coalesce(obj_id, 0),
    coalesce(obj_src_id, 0),
    coalesce(relation_id, 0)
)
where status = 'active';

create index if not exists rule_evidence_unit_members_unit_idx
on public.rule_evidence_unit_members(unit_id, member_role, review_status, status);

drop view if exists public.v_rule_evidence_unit_members_by_id;
drop view if exists public.v_rule_evidence_units_by_id;
drop view if exists public.v_fact_relation_predicate_options_by_id;
drop view if exists public.v_fact_relations_by_id;

alter table public.fact_relations
    drop constraint if exists fact_relations_source_method_known,
    drop constraint if exists fact_relations_review_status_known,
    drop constraint if exists fact_relations_status_known,
    alter column source_method type public.eval_source_method using source_method::public.eval_source_method,
    alter column review_status type public.eval_review_status using review_status::public.eval_review_status,
    alter column status type public.eval_lifecycle_status using status::public.eval_lifecycle_status;

alter table public.rule_evidence_units
    drop constraint if exists rule_evidence_units_direction_known,
    drop constraint if exists rule_evidence_units_score_mode_known,
    drop constraint if exists rule_evidence_units_source_method_known,
    drop constraint if exists rule_evidence_units_review_status_known,
    drop constraint if exists rule_evidence_units_status_known,
    alter column direction type public.evidence_direction using direction::public.evidence_direction,
    alter column score_mode type public.rule_evidence_score_mode using score_mode::public.rule_evidence_score_mode,
    alter column source_method type public.eval_source_method using source_method::public.eval_source_method,
    alter column review_status type public.eval_review_status using review_status::public.eval_review_status,
    alter column status type public.eval_lifecycle_status using status::public.eval_lifecycle_status;

alter table public.rule_evidence_unit_members
    drop constraint if exists rule_evidence_unit_members_source_method_known,
    drop constraint if exists rule_evidence_unit_members_review_status_known,
    drop constraint if exists rule_evidence_unit_members_status_known,
    alter column source_method type public.eval_source_method using source_method::public.eval_source_method,
    alter column review_status type public.eval_review_status using review_status::public.eval_review_status,
    alter column status type public.eval_lifecycle_status using status::public.eval_lifecycle_status;

alter table public.fact_relation_predicate_options
    alter column direction type public.evidence_direction using direction::public.evidence_direction,
    alter column status type public.eval_lifecycle_status using status::public.eval_lifecycle_status;

with seed(rule_code, scoring_role, predicate, relation_role, subject_obj_type, object_obj_type, direction, description) as (
    values
        ('talent_discovery', 'discovered_talent', 'discovered_talent', 'scored_candidate', 'person', '', 'positive', '发现或拔擢具体人才。'),
        ('talent_discovery', 'recommended_talent', 'recommended_talent', 'scored_candidate', 'person', '', 'positive', '通过荐举链进入视野的具体人才。'),
        ('talent_discovery', 'recognized_talent', 'recognized_talent', 'scored_candidate', 'person', '', 'positive', '识别、确认或信用修复的具体人才。'),
        ('talent_discovery', 'missed_talent', 'missed_talent', 'scored_candidate', 'person', '', 'negative', '被错失、压低或长期不用的具体人才。'),
        ('appointment_trust', 'appointed_talent', 'appointed_talent', 'scored_candidate', 'person', '', 'positive', '被恰当任用的具体人才。'),
        ('appointment_trust', 'trusted_minister', 'trusted_minister', 'scored_candidate', 'person', '', 'positive', '获得信任并承担政务的具体臣僚。'),
        ('appointment_trust', 'entrusted_official', 'entrusted_official', 'scored_candidate', 'person', '', 'positive', '被授以明确职任的具体官员。'),
        ('appointment_trust', 'misappointed_person', 'misappointed_person', 'scored_candidate', 'person', '', 'negative', '明显误任、纵任或污染任用秩序的具体人物。'),
        ('appointment_trust', 'suppressed_talent', 'suppressed_talent', 'scored_candidate', 'person', '', 'negative', '被政治性压制或排挤的具体人才。'),
        ('delegation', 'delegated_actor', 'delegated_authority', 'scored_candidate', 'person', '', 'positive', '获得授权并承担责任的具体人物。'),
        ('delegation', 'authority_recipient', 'delegated_authority', 'scored_candidate', 'person', '', 'positive', '获得权责配置的具体人物。'),
        ('delegation', 'authority_revoked_target', 'revoked_authority', 'scored_candidate', 'person', '', 'negative', '被不当撤权或破坏权责稳定的具体人物。'),
        ('delegation', 'misdelegated_actor', 'misdelegated_authority', 'scored_candidate', 'person', '', 'negative', '被错误授予权力或纵容用权的具体人物。'),
        ('team_building', 'team_member', 'team_member', 'scored_candidate', 'person', '', 'positive', '进入团队结构的正向具体成员。'),
        ('team_building', 'negative_team_member', 'negative_team_member', 'scored_candidate', 'person', '', 'negative', '进入团队结构的负向具体成员。'),
        ('tolerate_talent', 'protected_talent', 'protected_talent', 'scored_candidate', 'person', '', 'positive', '被保全、复用或修复信用的具体能臣。'),
        ('tolerate_talent', 'remonstrance_actor', 'accepted_remonstrance_actor', 'scored_candidate', 'person', '', 'positive', '被容纳表达或进谏的具体人物。'),
        ('tolerate_talent', 'harmed_talent', 'harmed_talent', 'scored_candidate', 'person', '', 'negative', '被压制、冤杀、排挤或安全受损的具体能臣。'),
        ('anti_nepotism', 'anti_nepotism_resisted_actor', 'resisted_nepotism', 'scored_candidate', 'person', '', 'positive', '体现抑制私亲任用、按才能或公正程序任用的具体人物。'),
        ('anti_nepotism', 'nepotistic_beneficiary', 'favored_kin', 'scored_candidate', 'person', '', 'negative', '亲族、外戚等亲缘偏私受益的具体人物。'),
        ('anti_nepotism', 'favorite_beneficiary', 'favored_private_person', 'scored_candidate', 'person', '', 'negative', '宠幸、近幸或私人偏好受益的具体人物。'),
        ('anti_nepotism', 'appointment_interferer', 'interfered_appointment', 'scored_candidate', 'person', '', 'negative', '实际干预任用秩序的具体人物。')
)
insert into public.fact_relation_predicate_options (
    item_id,
    item_code,
    rule_id,
    rule_code,
    scoring_role,
    predicate,
    relation_role,
    subject_obj_type,
    object_obj_type,
    direction,
    description
)
select
    i.id,
    i.item_code,
    r.id,
    r.rule_code,
    seed.scoring_role,
    seed.predicate,
    seed.relation_role,
    seed.subject_obj_type,
    seed.object_obj_type,
    seed.direction::public.evidence_direction,
    seed.description
  from seed
  join public.eval_items i on i.item_code = 'I5B'
  join public.eval_rules r on r.item_id = i.id and r.rule_code = seed.rule_code
 where not exists (
    select 1
      from public.fact_relation_predicate_options existing
     where existing.status = 'active'
       and existing.item_id = i.id
       and existing.rule_id = r.id
       and existing.scoring_role = seed.scoring_role
       and existing.predicate = seed.predicate
       and existing.relation_role = seed.relation_role
       and existing.subject_obj_type = seed.subject_obj_type
       and existing.object_obj_type = seed.object_obj_type
       and existing.direction = seed.direction::public.evidence_direction
);

update public.fact_relation_predicate_options
   set description = '体现抑制私亲任用、按才能或公正程序任用的具体人物。',
       updated_at = now()
 where item_code = 'I5B'
   and rule_code = 'anti_nepotism'
   and scoring_role = 'anti_nepotism_resisted_actor'
   and predicate = 'resisted_nepotism'
   and status = 'active';

update public.fact_relation_predicate_options
   set note = '',
       updated_at = now()
 where note = 'I5B 最小事实关系词表。';

update public.fact_relations
   set review_note = '',
       updated_at = now()
 where source_method = 'candidate_from_calc_detail'
   and review_status = 'needs_review'
   and review_note = '候选由 rule_evidence_units 与 fact_relation_predicate_options 映射生成；需人工确认主谓宾关系。';

update public.fact_relations
   set note = '',
       updated_at = now()
 where source_method = 'candidate_from_calc_detail'
   and review_status = 'needs_review'
   and note like '候选事实关系：%来自当前规则证据单元镜像，待人工回源确认。';

update public.rule_evidence_units
   set review_note = '',
       updated_at = now()
 where source_method = 'candidate_from_calc_detail'
   and review_status = 'needs_review'
   and review_note in (
        '候选来自当前 calc_detail.materials；因果链默认按 obj_src 分开，需人工合并同链。',
        '候选来自当前 calc_detail.materials；需人工复核。'
   );

update public.rule_evidence_units
   set note = '',
       updated_at = now()
 where source_method = 'candidate_from_calc_detail'
   and note like '候选承载对象：%';

update public.rule_evidence_unit_members
   set review_note = '',
       updated_at = now()
 where source_method = 'candidate_from_calc_detail'
   and review_status = 'needs_review'
   and review_note in (
        '候选来自当前 calc_detail.materials；因果链默认按 obj_src 分开，需人工合并同链。',
        '候选来自当前 calc_detail.materials；需人工复核。'
   );

update public.rule_evidence_unit_members
   set note = '',
       updated_at = now()
 where source_method = 'candidate_from_calc_detail'
   and note like '候选上下文成员：%';

create view public.v_fact_relations_by_id as
select
    fr.id,
    fr.emp_id,
    e.name as emperor_name,
    fr.item_id,
    fr.item_code,
    fr.rule_id,
    fr.rule_code,
    fr.subject_obj_id,
    subject_obj.name as subject_obj_name,
    fr.predicate,
    fr.object_obj_id,
    object_obj.name as object_obj_name,
    fr.doc_id,
    fr.obj_src_id,
    fr.causal_chain_key,
    fr.relation_role,
    fr.confidence,
    fr.source_method,
    fr.review_status,
    fr.review_note,
    fr.note,
    concat_ws(
        '',
        '事实关系：',
        coalesce(subject_obj.name, '未命名对象'),
        '在',
        e.name,
        ' ',
        fr.item_code,
        '/',
        fr.rule_code,
        ' 下对应 `',
        fr.predicate,
        '`',
        case
            when object_obj.name is not null then concat('，宾语为', object_obj.name)
            else ''
        end,
        '。'
    ) as display_note,
    fr.status,
    fr.created_at,
    fr.updated_at
from public.fact_relations fr
join public.emps e on e.id = fr.emp_id
join public.raw_objs subject_obj on subject_obj.id = fr.subject_obj_id
left join public.raw_objs object_obj on object_obj.id = fr.object_obj_id
order by fr.id;

create view public.v_fact_relation_predicate_options_by_id as
select
    opt.id,
    opt.item_id,
    opt.item_code,
    opt.rule_id,
    opt.rule_code,
    opt.scoring_role,
    opt.predicate,
    opt.relation_role,
    opt.subject_obj_type,
    opt.object_obj_type,
    opt.direction,
    opt.description,
    opt.note,
    opt.status,
    opt.created_at,
    opt.updated_at
from public.fact_relation_predicate_options opt
order by opt.id;

create view public.v_rule_evidence_units_by_id as
select
    reu.id,
    reu.emp_id,
    e.name as emperor_name,
    reu.item_id,
    reu.item_code,
    reu.rule_id,
    reu.rule_code,
    reu.causal_chain_key,
    reu.scored_obj_id,
    scored_obj.name as scored_obj_name,
    reu.scored_obj_src_id,
    reu.scoring_role,
    reu.direction,
    reu.score_mode,
    reu.source_method,
    reu.review_status,
    reu.review_note,
    reu.note,
    concat_ws(
        '',
        '规则证据单元：',
        coalesce(scored_obj.name, '未命名对象'),
        '在',
        e.name,
        ' ',
        reu.item_code,
        '/',
        reu.rule_code,
        ' 下作为 `',
        reu.scoring_role,
        '` 候选承载对象。'
    ) as display_note,
    reu.status,
    reu.created_at,
    reu.updated_at
from public.rule_evidence_units reu
join public.emps e on e.id = reu.emp_id
left join public.raw_objs scored_obj on scored_obj.id = reu.scored_obj_id
order by reu.id;

create view public.v_rule_evidence_unit_members_by_id as
select
    reum.id,
    reum.unit_id,
    reu.emp_id,
    e.name as emperor_name,
    reu.item_code,
    reu.rule_code,
    reu.causal_chain_key,
    reum.obj_id,
    ro.name as obj_name,
    reum.obj_src_id,
    reum.relation_id,
    reum.member_role,
    reum.source_method,
    reum.review_status,
    reum.review_note,
    reum.note,
    concat_ws(
        '',
        '规则证据单元成员：',
        coalesce(ro.name, '未命名对象'),
        '在',
        e.name,
        ' ',
        reu.item_code,
        '/',
        reu.rule_code,
        ' 下作为 `',
        reum.member_role,
        '` 上下文成员。'
    ) as display_note,
    reum.status,
    reum.created_at,
    reum.updated_at
from public.rule_evidence_unit_members reum
join public.rule_evidence_units reu on reu.id = reum.unit_id
join public.emps e on e.id = reu.emp_id
left join public.raw_objs ro on ro.id = reum.obj_id
order by reum.id;

comment on domain public.eval_lifecycle_status is '通用行生命周期状态：active 当前有效，inactive 暂不使用，retired 历史退役。';
comment on domain public.eval_review_status is '通用审核状态：draft 草稿，needs_review 待审，accepted 已确认，rejected 已驳回。';
comment on domain public.eval_source_method is '通用数据来源方法：manual 人工确认，candidate_* 脚本候选，db_backfill 历史回填。';
comment on domain public.evidence_direction is '证据方向：positive 正向，negative 负向，neutral 中性，mixed 混合。';
comment on domain public.rule_evidence_score_mode is '规则证据单元计分模式：shadow 只审计，scoring 未来正式计分，rejected 人工驳回。';
comment on table public.fact_relations is '规则承载对象影子层：记录对象之间的事实关系，不直接表示正式计分。';
comment on table public.fact_relation_predicate_options is '事实关系谓词词表：定义某分项、rule、scoring_role 可生成哪些 predicate / relation_role 组合。';
comment on table public.rule_evidence_units is '规则证据单元影子层：记录某 rule 选择哪个对象作为计分承载。score_mode=scoring 前不改变正式算分。';
comment on table public.rule_evidence_unit_members is '规则证据单元成员表：记录同一因果链中的施害者、机制、事件、群体、补源等上下文成员。';
comment on column public.fact_relations.id is '事实关系主键。';
comment on column public.fact_relations.emp_id is '关系所属皇帝。即便关系主体不是皇帝，也用该字段限定评价对象范围。';
comment on column public.fact_relations.item_id is '关系所属评价分项；可为空，表示该事实关系暂不绑定具体分项或可跨分项复用。';
comment on column public.fact_relations.item_code is '评价分项代码冗余字段，便于人工查询和导出；item_id 不为空时必须非空。';
comment on column public.fact_relations.rule_id is '关系关联的评价规则；可为空，表示该事实关系暂不绑定具体 rule。';
comment on column public.fact_relations.rule_code is '评价规则代码冗余字段，便于人工查询和导出；rule_id 不为空时必须非空。';
comment on column public.fact_relations.subject_obj_id is '事实关系主体对象，引用 raw_objs。';
comment on column public.fact_relations.predicate is '事实关系谓词，用稳定枚举或短语表达主体与宾语或上下文的关系。';
comment on column public.fact_relations.object_obj_id is '事实关系宾语对象，引用 raw_objs；无明确宾语时可为空。';
comment on column public.fact_relations.doc_id is '支撑该事实关系的史料文献，引用 src_docs；可为空等待补源。';
comment on column public.fact_relations.obj_src_id is '支撑该事实关系的对象史料边，引用 obj_srcs；用于回到具体对象-史料记录。';
comment on column public.fact_relations.causal_chain_key is '同一事实链或因果链的稳定键，用于发现机制、事件、人物和群体重复承载。';
comment on column public.fact_relations.relation_role is '该事实关系在规则判断中的角色，例如 scored_candidate、actor_context、mechanism_context、victim_context 或 context。';
comment on column public.fact_relations.confidence is '事实关系候选置信度，范围 0 到 1；人工确认后仍可保留原始置信度。';
comment on column public.fact_relations.source_method is '关系来源：manual 为人工确认；candidate_* 为脚本候选；db_backfill 为历史回填。';
comment on column public.fact_relations.review_status is '审核状态：draft、needs_review、accepted、rejected；accepted 前不得作为正式算分输入。';
comment on column public.fact_relations.review_note is '人工审核说明；脚本候选默认留空，只记录确认、驳回、合并或待补源的具体理由。';
comment on column public.fact_relations.note is '人工补充备注；默认留空，只写无法由皇帝、rule、主体对象、predicate、来源方法等结构字段还原的事实，不存模板展示句。';
comment on column public.fact_relations.status is '行生命周期状态：active 为当前有效，inactive 为暂不使用，retired 为历史退役。';
comment on column public.fact_relations.created_at is '记录创建时间。';
comment on column public.fact_relations.updated_at is '记录最近更新时间。';
comment on column public.fact_relation_predicate_options.id is '事实关系谓词词表主键。';
comment on column public.fact_relation_predicate_options.item_id is '词表项所属评价分项；为空时表示跨分项通用。';
comment on column public.fact_relation_predicate_options.item_code is '评价分项代码冗余字段，便于人工查询和导出。';
comment on column public.fact_relation_predicate_options.rule_id is '词表项所属评价规则；为空时表示分项内通用。';
comment on column public.fact_relation_predicate_options.rule_code is '评价规则代码冗余字段，便于人工查询和导出。';
comment on column public.fact_relation_predicate_options.scoring_role is '规则证据单元中的承载角色，用于从 rule_evidence_units 映射到事实关系谓词。';
comment on column public.fact_relation_predicate_options.predicate is '允许生成的事实关系谓词。';
comment on column public.fact_relation_predicate_options.relation_role is '该谓词在规则判断中的关系角色，例如 scored_candidate 或 context。';
comment on column public.fact_relation_predicate_options.subject_obj_type is '允许作为关系主体的 raw_objs.obj_type；第一版 I5B 事实关系只允许具体 person。';
comment on column public.fact_relation_predicate_options.object_obj_type is '允许作为关系宾语的 raw_objs.obj_type；为空表示第一版不要求宾语对象。';
comment on column public.fact_relation_predicate_options.direction is '该谓词默认证据方向。';
comment on column public.fact_relation_predicate_options.description is '中文语义说明，给人工审计和脚本报告使用。';
comment on column public.fact_relation_predicate_options.note is '维护备注；默认留空，只写单条词表项的特殊边界或迁移状态，不写全表统一说明。';
comment on column public.fact_relation_predicate_options.status is '行生命周期状态：active 为当前有效，inactive 为暂不使用，retired 为历史退役。';
comment on column public.fact_relation_predicate_options.created_at is '记录创建时间。';
comment on column public.fact_relation_predicate_options.updated_at is '记录最近更新时间。';
comment on column public.rule_evidence_units.id is '规则证据单元主键。';
comment on column public.rule_evidence_units.emp_id is '证据单元所属皇帝。';
comment on column public.rule_evidence_units.item_id is '证据单元所属评价分项。';
comment on column public.rule_evidence_units.item_code is '评价分项代码冗余字段，便于人工查询和导出。';
comment on column public.rule_evidence_units.rule_id is '证据单元所属评价规则。';
comment on column public.rule_evidence_units.rule_code is '评价规则代码冗余字段，便于人工查询和导出。';
comment on column public.rule_evidence_units.causal_chain_key is '本证据单元对应的事实链或因果链稳定键。';
comment on column public.rule_evidence_units.scored_obj_id is '本单元实际候选计分对象，引用 raw_objs；若单元只保留待补承载对象，可为空。';
comment on column public.rule_evidence_units.scored_obj_src_id is '本单元实际候选计分材料，引用 obj_srcs；用于回到对象史料边和当前 calc_detail。';
comment on column public.rule_evidence_units.scoring_role is '对象在本 rule 下的承载角色，例如 favorite_beneficiary、harmed_talent；群体、机制、事件通常只作上下文成员。';
comment on column public.rule_evidence_units.direction is '本证据单元方向：positive、negative、neutral 或 mixed。';
comment on column public.rule_evidence_units.score_mode is 'shadow 为只读影子预览，scoring 为未来正式算分输入，rejected 为人工审掉。';
comment on column public.rule_evidence_units.source_method is '证据单元来源：manual 为人工确认；candidate_* 为脚本候选；db_backfill 为历史回填。';
comment on column public.rule_evidence_units.review_status is '审核状态：draft、needs_review、accepted、rejected；accepted 前不得作为正式算分输入。';
comment on column public.rule_evidence_units.review_note is '人工审核说明；脚本候选默认留空，只记录承载对象确认、驳回、合并或拆分的具体理由。';
comment on column public.rule_evidence_units.note is '人工补充备注；默认留空，只写无法由皇帝、rule、承载对象、scoring_role、来源方法等结构字段还原的事实，不存模板展示句。';
comment on column public.rule_evidence_units.status is '行生命周期状态：active 为当前有效，inactive 为暂不使用，retired 为历史退役。';
comment on column public.rule_evidence_units.created_at is '记录创建时间。';
comment on column public.rule_evidence_units.updated_at is '记录最近更新时间。';
comment on column public.rule_evidence_unit_members.id is '规则证据单元成员主键。';
comment on column public.rule_evidence_unit_members.unit_id is '所属规则证据单元，引用 rule_evidence_units。';
comment on column public.rule_evidence_unit_members.obj_id is '成员对象，引用 raw_objs；可用于机制、事件、群体、施害者或补充人物。';
comment on column public.rule_evidence_unit_members.obj_src_id is '成员对象史料边，引用 obj_srcs；用于回到具体支撑材料。';
comment on column public.rule_evidence_unit_members.relation_id is '成员关联的事实关系，引用 fact_relations；当事实关系已结构化时用于连接主谓宾层。';
comment on column public.rule_evidence_unit_members.member_role is '成员在证据单元内的角色，例如 actor_context、mechanism_context、event_context。';
comment on column public.rule_evidence_unit_members.source_method is '成员来源：manual 为人工确认；candidate_* 为脚本候选；db_backfill 为历史回填。';
comment on column public.rule_evidence_unit_members.review_status is '成员审核状态；默认跟随候选单元等待人工确认。';
comment on column public.rule_evidence_unit_members.review_note is '人工审核说明；脚本候选默认留空，只记录成员保留、驳回、合并或补源的具体理由。';
comment on column public.rule_evidence_unit_members.note is '人工补充备注；默认留空，只写无法由皇帝、rule、成员对象、member_role、来源方法等结构字段还原的事实，不存模板展示句。';
comment on column public.rule_evidence_unit_members.status is '行生命周期状态：active 为当前有效，inactive 为暂不使用，retired 为历史退役。';
comment on column public.rule_evidence_unit_members.created_at is '记录创建时间。';
comment on column public.rule_evidence_unit_members.updated_at is '记录最近更新时间。';
comment on view public.v_fact_relations_by_id is '事实关系人工查看视图，展开皇帝和对象名称，并生成 display_note 展示文案。';
comment on view public.v_fact_relation_predicate_options_by_id is '事实关系谓词词表人工查看视图，展开 rule、scoring_role 与 predicate 映射。';
comment on view public.v_rule_evidence_units_by_id is '规则证据单元人工查看视图，展开皇帝和计分对象名称，并生成 display_note 展示文案。';
comment on view public.v_rule_evidence_unit_members_by_id is '规则证据单元成员人工查看视图，展开皇帝、rule 和成员对象名称，并生成 display_note 展示文案。';
comment on column public.v_fact_relations_by_id.display_note is '事实关系展示文案，由结构字段生成，不在 fact_relations.note 中冗余存储。';
comment on column public.v_rule_evidence_units_by_id.display_note is '规则证据单元展示文案，由结构字段生成，不在 rule_evidence_units.note 中冗余存储。';
comment on column public.v_rule_evidence_unit_members_by_id.display_note is '规则证据单元成员展示文案，由结构字段生成，不在 rule_evidence_unit_members.note 中冗余存储。';
