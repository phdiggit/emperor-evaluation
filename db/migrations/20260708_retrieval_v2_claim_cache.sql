create schema if not exists retrieval_v2;

-- retrieval_v2 claim cache 原则：
-- 1. 本迁移只建立 claim 管理基础设施，不从 clean run、JSONL cache 或消费层导入数据。
-- 2. claim cache 是可复用材料层，不直接写评分结论；入分仍经过 rule binding、factorization 和 scorer。
-- 3. 取值有限的字段使用 PostgreSQL enum type，不用 text + check 承载状态机。
-- 4. JSONB payload 保存分型事实细节；热查询字段保留为普通列，方便索引和审计。

do $$
begin
    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v2'
           and t.typname = 'rv2_claim_direction'
    ) then
        execute 'create type retrieval_v2.rv2_claim_direction as enum (''positive'', ''negative'', ''neutral'', ''mixed'')';
    end if;

    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v2'
           and t.typname = 'rv2_object_type'
    ) then
        execute 'create type retrieval_v2.rv2_object_type as enum (''person'', ''person_group'', ''institution'', ''place'', ''event'', ''text'', ''other'')';
    end if;

    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v2'
           and t.typname = 'rv2_claim_cache_type'
    ) then
        execute 'create type retrieval_v2.rv2_claim_cache_type as enum (''material_action'', ''outcome'', ''evaluation'', ''relationship'', ''institution'', ''numeric'', ''context'')';
    end if;

    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v2'
           and t.typname = 'rv2_claim_fact_schema'
    ) then
        execute 'create type retrieval_v2.rv2_claim_fact_schema as enum (''political_action_v1'', ''outcome_v1'', ''evaluation_v1'', ''relationship_v1'', ''institution_v1'', ''numeric_fact_v1'', ''context_v1'', ''unknown'')';
    end if;

    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v2'
           and t.typname = 'rv2_claim_cache_status'
    ) then
        execute 'create type retrieval_v2.rv2_claim_cache_status as enum (''active'', ''superseded'', ''needs_review'', ''rejected'')';
    end if;

    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v2'
           and t.typname = 'rv2_claim_support_level'
    ) then
        execute 'create type retrieval_v2.rv2_claim_support_level as enum (''direct'', ''indirect'', ''context'')';
    end if;

    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v2'
           and t.typname = 'rv2_claim_route_status'
    ) then
        execute 'create type retrieval_v2.rv2_claim_route_status as enum (''unrouted'', ''candidate'', ''accepted'', ''rejected'', ''needs_review'', ''retired'')';
    end if;

    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v2'
           and t.typname = 'rv2_profile_claim_field'
    ) then
        execute 'create type retrieval_v2.rv2_profile_claim_field as enum (''talent_grade'', ''negative_grade'', ''affiliation'', ''role'', ''identity'', ''authority_evaluation'')';
    end if;

    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v2'
           and t.typname = 'rv2_profile_claim_status'
    ) then
        execute 'create type retrieval_v2.rv2_profile_claim_status as enum (''candidate'', ''accepted'', ''rejected'', ''needs_review'', ''superseded'')';
    end if;
end;
$$;

comment on type retrieval_v2.rv2_claim_direction is 'claim 对评分语义的材料方向；positive、negative、neutral、mixed。';
comment on type retrieval_v2.rv2_object_type is 'claim 或对象身份的对象类型枚举；person、institution、event 等。';
comment on type retrieval_v2.rv2_claim_cache_type is 'claim cache 的分型材料类型；用于区分行为、结果、评价、关系、制度、数值和上下文材料。';
comment on type retrieval_v2.rv2_claim_fact_schema is 'claim fact_payload 采用的结构化事实 schema 版本。';
comment on type retrieval_v2.rv2_claim_cache_status is 'claim cache 生命周期状态；active 可复用，superseded/rejected 不应自动进入新包。';
comment on type retrieval_v2.rv2_claim_support_level is '证据对 claim 的支撑强度；direct 为直接支撑，indirect/context 需谨慎路由。';
comment on type retrieval_v2.rv2_claim_route_status is 'claim 到 rule 候选路由的生命周期状态。';
comment on type retrieval_v2.rv2_profile_claim_field is 'claim 可支撑的人物画像字段类型。';
comment on type retrieval_v2.rv2_profile_claim_status is 'claim 支撑画像字段候选的复核状态。';

create table if not exists retrieval_v2.claim_cache (
    claim_key text primary key,
    claim_type retrieval_v2.rv2_claim_cache_type not null default 'material_action',
    fact_schema retrieval_v2.rv2_claim_fact_schema not null default 'unknown',
    emperor_name text not null default '',
    object_name text not null,
    object_id bigint references retrieval_v2.objects(id) on delete set null,
    object_type retrieval_v2.rv2_object_type not null default 'person',
    direction retrieval_v2.rv2_claim_direction not null default 'neutral',
    action_type text not null default '',
    event_scope text not null default '',
    office_or_domain text not null default '',
    time_context text not null default '',
    outcome text not null default '',
    claim_summary text not null,
    confidence numeric(5,4),
    fact_payload jsonb not null default '{}'::jsonb,
    first_run_code text not null default '',
    last_run_code text not null default '',
    raw_output_path text not null default '',
    extractor_version text not null default '',
    status retrieval_v2.rv2_claim_cache_status not null default 'active',
    seen_count integer not null default 1,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv2_claim_cache_key_not_blank check (btrim(claim_key) <> ''),
    constraint rv2_claim_cache_object_not_blank check (btrim(object_name) <> ''),
    constraint rv2_claim_cache_summary_not_blank check (btrim(claim_summary) <> ''),
    constraint rv2_claim_cache_confidence_ck check (confidence is null or (confidence >= 0 and confidence <= 1)),
    constraint rv2_claim_cache_seen_count_ck check (seen_count >= 1),
    constraint rv2_claim_cache_fact_payload_ck check (jsonb_typeof(fact_payload) = 'object')
);

create table if not exists retrieval_v2.claim_source_slices (
    slice_hash text primary key,
    object_name text not null default '',
    object_id bigint references retrieval_v2.objects(id) on delete set null,
    document_code text not null default '',
    raw_document_code text not null default '',
    source_title text not null default '',
    source_url text not null default '',
    source_slice_ref text not null default '',
    text_hash text not null default '',
    slice_text_preview text not null default '',
    raw_text_path text not null default '',
    first_run_code text not null default '',
    seen_count integer not null default 1,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv2_claim_source_slices_hash_not_blank check (btrim(slice_hash) <> ''),
    constraint rv2_claim_source_slices_seen_count_ck check (seen_count >= 1)
);

create table if not exists retrieval_v2.claim_evidence (
    evidence_key text primary key,
    claim_key text not null references retrieval_v2.claim_cache(claim_key) on delete cascade,
    slice_hash text not null references retrieval_v2.claim_source_slices(slice_hash) on delete cascade,
    source_slice_ref text not null default '',
    document_code text not null default '',
    object_name text not null default '',
    object_id bigint references retrieval_v2.objects(id) on delete set null,
    support_level retrieval_v2.rv2_claim_support_level not null default 'direct',
    span_payload jsonb not null default '{}'::jsonb,
    quote_preview text not null default '',
    slice_text_preview text not null default '',
    raw_output_path text not null default '',
    first_run_code text not null default '',
    created_at timestamptz not null default now(),
    constraint rv2_claim_evidence_key_not_blank check (btrim(evidence_key) <> ''),
    constraint rv2_claim_evidence_span_payload_ck check (jsonb_typeof(span_payload) = 'object')
);

create table if not exists retrieval_v2.claim_route_cache (
    route_key text primary key,
    claim_key text not null references retrieval_v2.claim_cache(claim_key) on delete cascade,
    candidate_item_code text not null default '',
    candidate_rule_code text not null default '',
    candidate_lane text not null default '',
    candidate_direction retrieval_v2.rv2_claim_direction,
    route_status retrieval_v2.rv2_claim_route_status not null default 'unrouted',
    route_reason text not null default '',
    routed_by_profile text not null default '',
    candidate_payload jsonb not null default '{}'::jsonb,
    confidence numeric(5,4),
    resolved_binding_id bigint references retrieval_v2.claim_rule_bindings(id) on delete set null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv2_claim_route_cache_key_not_blank check (btrim(route_key) <> ''),
    constraint rv2_claim_route_cache_payload_ck check (jsonb_typeof(candidate_payload) = 'object'),
    constraint rv2_claim_route_cache_confidence_ck check (confidence is null or (confidence >= 0 and confidence <= 1))
);

create table if not exists retrieval_v2.person_profile_claim_links (
    link_key text primary key,
    claim_key text not null references retrieval_v2.claim_cache(claim_key) on delete cascade,
    object_id bigint references retrieval_v2.objects(id) on delete set null,
    object_name text not null default '',
    profile_field retrieval_v2.rv2_profile_claim_field not null,
    proposal_value text not null default '',
    proposal_status retrieval_v2.rv2_profile_claim_status not null default 'candidate',
    basis text not null default '',
    confidence numeric(5,4),
    link_payload jsonb not null default '{}'::jsonb,
    resolved_profile_id bigint references retrieval_v2.person_profiles(id) on delete set null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv2_person_profile_claim_links_key_not_blank check (btrim(link_key) <> ''),
    constraint rv2_person_profile_claim_links_payload_ck check (jsonb_typeof(link_payload) = 'object'),
    constraint rv2_person_profile_claim_links_confidence_ck check (confidence is null or (confidence >= 0 and confidence <= 1))
);

alter table retrieval_v2.claim_cache
    add column if not exists claim_type retrieval_v2.rv2_claim_cache_type not null default 'material_action',
    add column if not exists fact_schema retrieval_v2.rv2_claim_fact_schema not null default 'unknown',
    add column if not exists object_id bigint references retrieval_v2.objects(id) on delete set null,
    add column if not exists action_type text not null default '',
    add column if not exists event_scope text not null default '',
    add column if not exists office_or_domain text not null default '',
    add column if not exists time_context text not null default '',
    add column if not exists outcome text not null default '',
    add column if not exists first_run_code text not null default '',
    add column if not exists last_run_code text not null default '',
    add column if not exists raw_output_path text not null default '',
    add column if not exists extractor_version text not null default '',
    add column if not exists seen_count integer not null default 1,
    add column if not exists created_at timestamptz not null default now(),
    add column if not exists updated_at timestamptz not null default now();

alter table retrieval_v2.claim_source_slices
    add column if not exists object_id bigint references retrieval_v2.objects(id) on delete set null,
    add column if not exists raw_document_code text not null default '',
    add column if not exists source_title text not null default '',
    add column if not exists source_url text not null default '',
    add column if not exists text_hash text not null default '',
    add column if not exists raw_text_path text not null default '',
    add column if not exists first_run_code text not null default '',
    add column if not exists seen_count integer not null default 1,
    add column if not exists created_at timestamptz not null default now(),
    add column if not exists updated_at timestamptz not null default now();

alter table retrieval_v2.claim_evidence
    add column if not exists object_id bigint references retrieval_v2.objects(id) on delete set null,
    add column if not exists support_level retrieval_v2.rv2_claim_support_level not null default 'direct',
    add column if not exists quote_preview text not null default '',
    add column if not exists slice_text_preview text not null default '',
    add column if not exists raw_output_path text not null default '',
    add column if not exists first_run_code text not null default '',
    add column if not exists created_at timestamptz not null default now();

alter table retrieval_v2.claim_route_cache
    add column if not exists candidate_direction retrieval_v2.rv2_claim_direction,
    add column if not exists route_reason text not null default '',
    add column if not exists routed_by_profile text not null default '',
    add column if not exists candidate_payload jsonb not null default '{}'::jsonb,
    add column if not exists confidence numeric(5,4),
    add column if not exists resolved_binding_id bigint references retrieval_v2.claim_rule_bindings(id) on delete set null,
    add column if not exists created_at timestamptz not null default now(),
    add column if not exists updated_at timestamptz not null default now();

alter table retrieval_v2.claim_cache
    drop constraint if exists rv2_claim_cache_status_ck;

alter table retrieval_v2.claim_cache
    drop column if exists claim_kind;

alter table retrieval_v2.claim_route_cache
    drop column if exists route_payload;

do $$
begin
    if exists (
        select 1
          from information_schema.columns
         where table_schema = 'retrieval_v2'
           and table_name = 'claim_cache'
           and column_name = 'object_type'
           and udt_name <> 'rv2_object_type'
    ) then
        alter table retrieval_v2.claim_cache
            alter column object_type drop default,
            alter column object_type type retrieval_v2.rv2_object_type
                using case
                    when object_type::text in ('person', 'person_group', 'institution', 'place', 'event', 'text', 'other')
                        then object_type::text::retrieval_v2.rv2_object_type
                    else 'person'::retrieval_v2.rv2_object_type
                end,
            alter column object_type set default 'person';
    end if;

    if exists (
        select 1
          from information_schema.columns
         where table_schema = 'retrieval_v2'
           and table_name = 'claim_cache'
           and column_name = 'direction'
           and udt_name <> 'rv2_claim_direction'
    ) then
        alter table retrieval_v2.claim_cache
            alter column direction drop default,
            alter column direction type retrieval_v2.rv2_claim_direction
                using case
                    when direction::text in ('positive', 'negative', 'neutral', 'mixed')
                        then direction::text::retrieval_v2.rv2_claim_direction
                    else 'neutral'::retrieval_v2.rv2_claim_direction
                end,
            alter column direction set default 'neutral';
    end if;

    if exists (
        select 1
          from information_schema.columns
         where table_schema = 'retrieval_v2'
           and table_name = 'claim_cache'
           and column_name = 'status'
           and udt_name <> 'rv2_claim_cache_status'
    ) then
        alter table retrieval_v2.claim_cache
            alter column status drop default,
            alter column status type retrieval_v2.rv2_claim_cache_status
                using case
                    when status::text in ('active', 'superseded', 'needs_review', 'rejected')
                        then status::text::retrieval_v2.rv2_claim_cache_status
                    else 'active'::retrieval_v2.rv2_claim_cache_status
                end,
            alter column status set default 'active';
    end if;

    if exists (
        select 1
          from information_schema.columns
         where table_schema = 'retrieval_v2'
           and table_name = 'claim_route_cache'
           and column_name = 'route_status'
           and udt_name <> 'rv2_claim_route_status'
    ) then
        alter table retrieval_v2.claim_route_cache
            alter column route_status drop default,
            alter column route_status type retrieval_v2.rv2_claim_route_status
                using case
                    when route_status::text in ('unrouted', 'candidate', 'accepted', 'rejected', 'needs_review', 'retired')
                        then route_status::text::retrieval_v2.rv2_claim_route_status
                    else 'unrouted'::retrieval_v2.rv2_claim_route_status
                end,
            alter column route_status set default 'unrouted';
    end if;
end;
$$;

create index if not exists rv2_claim_cache_object_idx
on retrieval_v2.claim_cache(emperor_name, object_name, direction, status);

create index if not exists rv2_claim_cache_type_schema_idx
on retrieval_v2.claim_cache(claim_type, fact_schema, status);

create index if not exists rv2_claim_cache_action_idx
on retrieval_v2.claim_cache(action_type, event_scope, office_or_domain);

create index if not exists rv2_claim_source_slices_object_idx
on retrieval_v2.claim_source_slices(object_name, document_code);

create index if not exists rv2_claim_evidence_claim_idx
on retrieval_v2.claim_evidence(claim_key, slice_hash, support_level);

create index if not exists rv2_claim_evidence_slice_idx
on retrieval_v2.claim_evidence(slice_hash, claim_key);

create index if not exists rv2_claim_route_cache_rule_idx
on retrieval_v2.claim_route_cache(candidate_item_code, candidate_rule_code, candidate_lane, route_status);

create index if not exists rv2_person_profile_claim_links_object_idx
on retrieval_v2.person_profile_claim_links(object_name, profile_field, proposal_status);

comment on table retrieval_v2.claim_cache is 'claim 管理核心表；保存可复用材料事实，不直接代表最终评分。';
comment on table retrieval_v2.claim_source_slices is 'claim cache 使用的原文切片索引；按 slice_hash 去重并保留回源线索。';
comment on table retrieval_v2.claim_evidence is 'claim 与原文切片或证据 span 的连接表；用于证明 claim 可回源。';
comment on table retrieval_v2.claim_route_cache is 'claim 到评分规则候选路由的缓存表；不替代正式 claim_rule_bindings。';
comment on table retrieval_v2.person_profile_claim_links is 'claim 支撑人物画像字段的候选连接表；不直接改写人物画像结论。';

comment on column retrieval_v2.claim_cache.claim_key is 'claim cache 稳定主键；由规范化事实身份生成。';
comment on column retrieval_v2.claim_cache.claim_type is 'claim 分型材料类型，例如 material_action、evaluation、numeric。';
comment on column retrieval_v2.claim_cache.fact_schema is 'fact_payload 的结构化事实 schema 版本。';
comment on column retrieval_v2.claim_cache.emperor_name is 'claim 所属目标皇帝名称；未知或非皇帝目标时留空。';
comment on column retrieval_v2.claim_cache.object_name is 'claim 主要对象名称；人物 claim 通常为臣子或相关人物。';
comment on column retrieval_v2.claim_cache.object_id is '已解析对象的 retrieval_v2.objects.id；未解析时为空。';
comment on column retrieval_v2.claim_cache.object_type is 'claim 主要对象类型。';
comment on column retrieval_v2.claim_cache.direction is 'claim 对评分语义的材料方向。';
comment on column retrieval_v2.claim_cache.action_type is '行为类 claim 的动作类型；非行为类可留空。';
comment on column retrieval_v2.claim_cache.event_scope is '事件领域，例如军事、政务、人事、制度；未知时留空。';
comment on column retrieval_v2.claim_cache.office_or_domain is '官职、职责或治理领域；未知时留空。';
comment on column retrieval_v2.claim_cache.time_context is '时间语境；只保存原文或判读可支撑的时间信息。';
comment on column retrieval_v2.claim_cache.outcome is '结果、影响或后果摘要；未知时留空。';
comment on column retrieval_v2.claim_cache.claim_summary is 'claim 中文摘要；应为具体事实，不写模板句。';
comment on column retrieval_v2.claim_cache.confidence is 'claim 抽取置信度，范围 0 到 1；未知时为空。';
comment on column retrieval_v2.claim_cache.fact_payload is '按 fact_schema 保存的结构化事实 payload。';
comment on column retrieval_v2.claim_cache.first_run_code is '首次导入该 claim 的 run_code。';
comment on column retrieval_v2.claim_cache.last_run_code is '最近一次观察到该 claim 的 run_code。';
comment on column retrieval_v2.claim_cache.raw_output_path is '首次或主要抽取产物路径，用于追溯原始 judge 输出。';
comment on column retrieval_v2.claim_cache.extractor_version is '抽取器或 judge mode 版本；schema 或 prompt 变化时用于判断是否重抽。';
comment on column retrieval_v2.claim_cache.status is 'claim 生命周期状态；active 才默认参与缓存复用。';
comment on column retrieval_v2.claim_cache.seen_count is '该 claim 在导入或重放中被观察到的次数。';
comment on column retrieval_v2.claim_cache.created_at is 'claim 首次写入时间。';
comment on column retrieval_v2.claim_cache.updated_at is 'claim 最近更新时间。';

comment on column retrieval_v2.claim_source_slices.slice_hash is '原文切片稳定 hash；按对象、文档和切片文本生成。';
comment on column retrieval_v2.claim_source_slices.object_name is '切片命中的主要对象名称；未知时留空。';
comment on column retrieval_v2.claim_source_slices.object_id is '已解析对象的 retrieval_v2.objects.id；未解析时为空。';
comment on column retrieval_v2.claim_source_slices.document_code is 'clean run 中的 document_code。';
comment on column retrieval_v2.claim_source_slices.raw_document_code is '源包或原始抓取层的 document_code；未知时留空。';
comment on column retrieval_v2.claim_source_slices.source_title is '史源标题或页面标题；未知时留空。';
comment on column retrieval_v2.claim_source_slices.source_url is '史源 URL；未知时留空。';
comment on column retrieval_v2.claim_source_slices.source_slice_ref is 'clean run 中的 source_slice_ref 或 slice_code。';
comment on column retrieval_v2.claim_source_slices.text_hash is '切片正文 hash；用于诊断同源文本变体。';
comment on column retrieval_v2.claim_source_slices.slice_text_preview is '切片正文预览；用于人工快速核对，不代替全文。';
comment on column retrieval_v2.claim_source_slices.raw_text_path is '切片全文或页面缓存路径；未知时留空。';
comment on column retrieval_v2.claim_source_slices.first_run_code is '首次导入该切片的 run_code。';
comment on column retrieval_v2.claim_source_slices.seen_count is '该切片在导入或重放中被观察到的次数。';
comment on column retrieval_v2.claim_source_slices.created_at is '切片首次写入时间。';
comment on column retrieval_v2.claim_source_slices.updated_at is '切片最近更新时间。';

comment on column retrieval_v2.claim_evidence.evidence_key is 'claim-evidence 稳定主键；由 claim、slice 和 span 生成。';
comment on column retrieval_v2.claim_evidence.claim_key is '被支撑的 claim_cache.claim_key。';
comment on column retrieval_v2.claim_evidence.slice_hash is '支撑材料所在的 claim_source_slices.slice_hash。';
comment on column retrieval_v2.claim_evidence.source_slice_ref is '当前导入产物中的 slice 引用；用于回写包内 source_slice_refs。';
comment on column retrieval_v2.claim_evidence.document_code is '证据所在 clean run document_code。';
comment on column retrieval_v2.claim_evidence.object_name is '证据命中的主要对象名称；未知时留空。';
comment on column retrieval_v2.claim_evidence.object_id is '已解析对象的 retrieval_v2.objects.id；未解析时为空。';
comment on column retrieval_v2.claim_evidence.support_level is '证据支撑强度；direct 表示可直接支撑 claim。';
comment on column retrieval_v2.claim_evidence.span_payload is '证据 span payload，例如 action、outcome、evaluation 或 numeric span。';
comment on column retrieval_v2.claim_evidence.quote_preview is '证据短引文预览；用于人工核对，不代替全文。';
comment on column retrieval_v2.claim_evidence.slice_text_preview is '证据所在切片预览；用于快速定位上下文。';
comment on column retrieval_v2.claim_evidence.raw_output_path is '证据来源的原始 judge 输出路径。';
comment on column retrieval_v2.claim_evidence.first_run_code is '首次导入该 evidence 的 run_code。';
comment on column retrieval_v2.claim_evidence.created_at is 'evidence 首次写入时间。';

comment on column retrieval_v2.claim_route_cache.route_key is 'claim 路由候选稳定主键。';
comment on column retrieval_v2.claim_route_cache.claim_key is '被路由的 claim_cache.claim_key。';
comment on column retrieval_v2.claim_route_cache.candidate_item_code is '候选目标 item_code；未知时留空。';
comment on column retrieval_v2.claim_route_cache.candidate_rule_code is '候选目标 rule_code；未知时留空。';
comment on column retrieval_v2.claim_route_cache.candidate_lane is '宽包候选 lane，例如 I5B.team_building；未知时留空。';
comment on column retrieval_v2.claim_route_cache.candidate_direction is '候选路由方向；无方向或待定时为空。';
comment on column retrieval_v2.claim_route_cache.route_status is '候选路由状态；accepted 后才可同步为正式 binding。';
comment on column retrieval_v2.claim_route_cache.route_reason is '候选路由理由；只写中文具体判断，不写模板句。';
comment on column retrieval_v2.claim_route_cache.routed_by_profile is '产生路由的抓包 profile 或工具名。';
comment on column retrieval_v2.claim_route_cache.candidate_payload is '候选路由结构化 payload 和事实完整性标记。';
comment on column retrieval_v2.claim_route_cache.confidence is '候选路由置信度，范围 0 到 1；未知时为空。';
comment on column retrieval_v2.claim_route_cache.resolved_binding_id is '路由被接受后对应的 claim_rule_bindings.id；未接受时为空。';
comment on column retrieval_v2.claim_route_cache.created_at is '路由候选首次写入时间。';
comment on column retrieval_v2.claim_route_cache.updated_at is '路由候选最近更新时间。';

comment on column retrieval_v2.person_profile_claim_links.link_key is 'claim 支撑人物画像候选的稳定主键。';
comment on column retrieval_v2.person_profile_claim_links.claim_key is '支撑画像字段的 claim_cache.claim_key。';
comment on column retrieval_v2.person_profile_claim_links.object_id is '画像对象 retrieval_v2.objects.id；未解析时为空。';
comment on column retrieval_v2.person_profile_claim_links.object_name is '画像对象名称；未解析 object_id 前用于排队和审计。';
comment on column retrieval_v2.person_profile_claim_links.profile_field is 'claim 支撑的人物画像字段。';
comment on column retrieval_v2.person_profile_claim_links.proposal_value is '候选画像取值，例如 major_sycophant 或 important_talent。';
comment on column retrieval_v2.person_profile_claim_links.proposal_status is '画像候选状态；accepted 才能进入画像写入链。';
comment on column retrieval_v2.person_profile_claim_links.basis is '画像候选依据；只写中文具体史料评价或判断，不写模板句。';
comment on column retrieval_v2.person_profile_claim_links.confidence is '画像候选置信度，范围 0 到 1；未知时为空。';
comment on column retrieval_v2.person_profile_claim_links.link_payload is '画像候选 payload、来源 claim 和复核上下文。';
comment on column retrieval_v2.person_profile_claim_links.resolved_profile_id is '候选被采纳后对应的 person_profiles.id；未采纳时为空。';
comment on column retrieval_v2.person_profile_claim_links.created_at is '画像候选首次写入时间。';
comment on column retrieval_v2.person_profile_claim_links.updated_at is '画像候选最近更新时间。';
