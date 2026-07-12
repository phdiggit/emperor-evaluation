create schema if not exists retrieval_v3;

-- Shadow middle layer for retrieval_v3 claim-cache calibration:
-- claim_cache stays an atomic fact cache. Direction-like scoring judgment belongs
-- to event groups and rule routes, not to the atomic claim itself.

do $$
begin
    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v3'
           and t.typname = 'rv3_claim_outcome_support'
    ) then
        execute 'create type retrieval_v3.rv3_claim_outcome_support as enum (''direct'', ''implicit'', ''missing'', ''not_applicable'', ''mixed'')';
    end if;

    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v3'
           and t.typname = 'rv3_claim_usage_role'
    ) then
        execute 'create type retrieval_v3.rv3_claim_usage_role as enum (''direct_material_candidate'', ''supporting_context'', ''evaluation_context'', ''background_context'', ''rejected'')';
    end if;
end;
$$;

comment on type retrieval_v3.rv3_claim_outcome_support is '原子 claim 是否自带结果支撑：direct、implicit、missing、not_applicable、mixed。';
comment on type retrieval_v3.rv3_claim_usage_role is 'claim 在事件组或规则路由中的使用角色；direction 不在原子 claim 层裁决。';

alter table retrieval_v3.claim_cache
    add column if not exists fact_type text not null default '',
    add column if not exists outcome_support retrieval_v3.rv3_claim_outcome_support not null default 'missing',
    add column if not exists atomic_fact_payload jsonb not null default '{}'::jsonb,
    add column if not exists event_group_key text not null default '',
    add column if not exists event_group_payload jsonb not null default '{}'::jsonb,
    add column if not exists claim_usage_flags jsonb not null default '[]'::jsonb;

alter table retrieval_v3.claim_cache
    drop column if exists direction;

alter table retrieval_v3.claim_cache
    drop constraint if exists rv3_claim_cache_atomic_payload_ck,
    drop constraint if exists rv3_claim_cache_event_group_payload_ck,
    drop constraint if exists rv3_claim_cache_usage_flags_ck;

alter table retrieval_v3.claim_cache
    add constraint rv3_claim_cache_atomic_payload_ck check (jsonb_typeof(atomic_fact_payload) = 'object'),
    add constraint rv3_claim_cache_event_group_payload_ck check (jsonb_typeof(event_group_payload) = 'object'),
    add constraint rv3_claim_cache_usage_flags_ck check (jsonb_typeof(claim_usage_flags) = 'array');

create table if not exists retrieval_v3.claim_event_groups (
    group_key text primary key,
    emperor_name text not null default '',
    object_name text not null default '',
    fact_type text not null default '',
    action_type text not null default '',
    event_scope text not null default '',
    office_or_domain text not null default '',
    time_context text not null default '',
    member_count integer not null default 0,
    outcome_support_summary jsonb not null default '{}'::jsonb,
    usage_summary jsonb not null default '{}'::jsonb,
    group_payload jsonb not null default '{}'::jsonb,
    group_status retrieval_v3.rv3_claim_route_status not null default 'unrouted',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv3_claim_event_groups_key_not_blank check (btrim(group_key) <> ''),
    constraint rv3_claim_event_groups_member_count_ck check (member_count >= 0),
    constraint rv3_claim_event_groups_outcome_summary_ck check (jsonb_typeof(outcome_support_summary) = 'object'),
    constraint rv3_claim_event_groups_usage_summary_ck check (jsonb_typeof(usage_summary) = 'object'),
    constraint rv3_claim_event_groups_payload_ck check (jsonb_typeof(group_payload) = 'object')
);

create table if not exists retrieval_v3.claim_event_group_members (
    group_key text not null references retrieval_v3.claim_event_groups(group_key) on delete cascade,
    claim_key text not null references retrieval_v3.claim_cache(claim_key) on delete cascade,
    member_role retrieval_v3.rv3_claim_usage_role not null default 'supporting_context',
    outcome_support retrieval_v3.rv3_claim_outcome_support not null default 'missing',
    member_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (group_key, claim_key),
    constraint rv3_claim_event_group_members_payload_ck check (jsonb_typeof(member_payload) = 'object')
);

create table if not exists retrieval_v3.claim_rule_routes (
    route_key text primary key,
    group_key text references retrieval_v3.claim_event_groups(group_key) on delete cascade,
    claim_key text references retrieval_v3.claim_cache(claim_key) on delete cascade,
    candidate_item_code text not null default '',
    candidate_rule_code text not null default '',
    usage_role retrieval_v3.rv3_claim_usage_role not null default 'supporting_context',
    route_direction retrieval_v3.rv3_claim_direction,
    route_status retrieval_v3.rv3_claim_route_status not null default 'unrouted',
    route_reason text not null default '',
    route_payload jsonb not null default '{}'::jsonb,
    confidence numeric(5,4),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv3_claim_rule_routes_key_not_blank check (btrim(route_key) <> ''),
    constraint rv3_claim_rule_routes_payload_ck check (jsonb_typeof(route_payload) = 'object'),
    constraint rv3_claim_rule_routes_confidence_ck check (confidence is null or (confidence >= 0 and confidence <= 1)),
    constraint rv3_claim_rule_routes_scope_ck check (group_key is not null or claim_key is not null)
);

create index if not exists rv3_claim_cache_event_group_idx
on retrieval_v3.claim_cache(event_group_key, outcome_support, status);

create index if not exists rv3_claim_event_groups_object_idx
on retrieval_v3.claim_event_groups(emperor_name, object_name, fact_type, action_type, group_status);

create index if not exists rv3_claim_event_group_members_claim_idx
on retrieval_v3.claim_event_group_members(claim_key, member_role, outcome_support);

create index if not exists rv3_claim_rule_routes_group_idx
on retrieval_v3.claim_rule_routes(group_key, candidate_rule_code, route_status);

create or replace view retrieval_v3.claim_atomic_facts as
select
    claim_key,
    claim_type,
    fact_schema,
    emperor_name,
    object_name,
    object_id,
    object_type,
    fact_type,
    outcome_support,
    action_type,
    event_scope,
    office_or_domain,
    time_context,
    outcome,
    claim_summary,
    confidence,
    fact_payload,
    atomic_fact_payload,
    event_group_key,
    event_group_payload,
    claim_usage_flags,
    canonical_event_key,
    canonical_event_payload,
    near_duplicate_group_payload,
    claim_grain,
    quality_flags,
    first_run_code,
    last_run_code,
    raw_output_path,
    extractor_version,
    status,
    seen_count,
    created_at,
    updated_at
from retrieval_v3.claim_cache;

create or replace view retrieval_v3.claim_owner_scopes as
select
    c.claim_key,
    c.emperor_name as owner_name,
    case
        when btrim(c.emperor_name) = '' then 'blank_owner'
        when t.id is not null then 'target_emperor'
        else 'external_or_unregistered_owner'
    end as owner_scope,
    t.target_code as owner_target_code,
    c.object_name,
    c.claim_summary,
    c.status,
    c.first_run_code,
    c.last_run_code,
    c.updated_at
from retrieval_v3.claim_cache c
left join retrieval_v3.retrieval_targets t
  on t.emperor_name = c.emperor_name;

comment on column retrieval_v3.claim_cache.fact_type is '原子事实类型，例如 material_action、evaluation、relationship；从 claim_type/fact_schema 派生，供事件组聚合。';
comment on column retrieval_v3.claim_cache.outcome_support is '原子 claim 自身是否支撑结果：direct、implicit、missing、not_applicable 或 mixed。';
comment on column retrieval_v3.claim_cache.atomic_fact_payload is '不含 scoring direction 的原子事实规范化 payload。';
comment on column retrieval_v3.claim_cache.event_group_key is '不含 scoring direction 的事件组 key；用于聚合同一对象同一事件链的动作、结果和评价 claim。';
comment on column retrieval_v3.claim_cache.event_group_payload is '生成 event_group_key 的规范化字段 payload。';
comment on column retrieval_v3.claim_cache.claim_usage_flags is 'claim 在中间层使用前的审计/提示 flag；不直接代表评分结论。';
comment on table retrieval_v3.claim_event_groups is 'claim 中间层事件组；聚合同一事件链的原子事实，不直接写评分结论。';
comment on table retrieval_v3.claim_event_group_members is '事件组与原子 claim 的成员关系，记录 direct/supporting/evaluation/background 使用角色。';
comment on table retrieval_v3.claim_rule_routes is '事件组或 claim 到规则的 shadow route；最终 rule direction 只在这里或正式 binding 层裁决。';
comment on view retrieval_v3.claim_atomic_facts is '无 direction 字段的原子事实视图；中间层和消费前工具应优先读取此视图，避免把 claim 当作正式评分方向。';
comment on view retrieval_v3.claim_owner_scopes is '零 token owner scope 视图；从 PG claim_cache 左连 retrieval_targets 判定 target_emperor、external_or_unregistered_owner 或 blank_owner，不进入 prompt。';
