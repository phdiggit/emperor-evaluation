create schema if not exists retrieval_v3;

-- retrieval_v3 消费层原则：
-- 1. 本迁移只建空表、补字段、补幂等索引，不导入 clean 包。
-- 2. 旧对象池只作人工参考，不做外键、不复用旧 ID、不同步写入。
-- 3. 说明类字段必须写中文高信息文本；模板句、字段名复述和低信息套话留空。
-- 4. 取值有限的字段使用 PostgreSQL enum type，不用 text + check 承载状态机。

do $$
begin
    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v3'
           and t.typname = 'rv3_claim_direction'
    ) then
        execute 'create type retrieval_v3.rv3_claim_direction as enum (''positive'', ''negative'', ''neutral'', ''mixed'')';
    end if;

    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v3'
           and t.typname = 'rv3_review_status'
    ) then
        execute 'create type retrieval_v3.rv3_review_status as enum (''pending'', ''accepted'', ''rejected'', ''needs_review'', ''resolved'', ''retired'')';
    end if;

    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v3'
           and t.typname = 'rv3_object_identity_status'
    ) then
        execute 'create type retrieval_v3.rv3_object_identity_status as enum (''draft'', ''active'', ''needs_review'', ''merged'', ''rejected'', ''retired'')';
    end if;

    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v3'
           and t.typname = 'rv3_queue_status'
    ) then
        execute 'create type retrieval_v3.rv3_queue_status as enum (''ready'', ''running'', ''resolved'', ''needs_review'', ''blocked'', ''cancelled'')';
    end if;

    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v3'
           and t.typname = 'rv3_object_type'
    ) then
        execute 'create type retrieval_v3.rv3_object_type as enum (''person'', ''person_group'', ''institution'', ''place'', ''event'', ''text'', ''other'')';
    end if;

    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v3'
           and t.typname = 'rv3_person_talent_grade'
    ) then
        execute 'create type retrieval_v3.rv3_person_talent_grade as enum (''historic_talent'', ''top_talent'', ''important_talent'', ''ordinary_talent'', ''sycophant'', ''major_sycophant'', ''historic_sycophant'')';
    end if;

    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v3'
           and t.typname = 'rv3_person_role_kind'
    ) then
        execute 'create type retrieval_v3.rv3_person_role_kind as enum (''emperor'', ''heir'', ''prince'', ''minister'', ''general'', ''official'', ''consort'', ''clan_member'', ''eunuch'', ''scholar'', ''rebel'', ''other'')';
    end if;

    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v3'
           and t.typname = 'rv3_person_affiliation_kind'
    ) then
        execute 'create type retrieval_v3.rv3_person_affiliation_kind as enum (''dynasty'', ''polity'', ''service'', ''origin'', ''faction'', ''family'', ''other'')';
    end if;

    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v3'
           and t.typname = 'rv3_object_name_kind'
    ) then
        execute 'create type retrieval_v3.rv3_object_name_kind as enum (''canonical'', ''alias'', ''script_variant'', ''courtesy_name'', ''art_name'', ''posthumous_name'', ''temple_name'', ''reign_title'', ''other'')';
    end if;

    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v3'
           and t.typname = 'rv3_target_object_scope'
    ) then
        execute 'create type retrieval_v3.rv3_target_object_scope as enum (''item'', ''rule'', ''source_pack'', ''manual'')';
    end if;

    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v3'
           and t.typname = 'rv3_target_object_attribute_kind'
    ) then
        execute 'create type retrieval_v3.rv3_target_object_attribute_kind as enum (''scoring_role'', ''rule_requirement'', ''factor_input'', ''assessment'')';
    end if;

    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v3'
           and t.typname = 'rv3_claim_passage_relation_kind'
    ) then
        execute 'create type retrieval_v3.rv3_claim_passage_relation_kind as enum (''supporting_quote'', ''context_quote'', ''source_pointer'')';
    end if;

    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v3'
           and t.typname = 'rv3_factor_target_action'
    ) then
        execute 'create type retrieval_v3.rv3_factor_target_action as enum (''score'', ''supporting_only'', ''exclude'')';
    end if;

    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v3'
           and t.typname = 'rv3_factor_side'
    ) then
        execute 'create type retrieval_v3.rv3_factor_side as enum (''positive'', ''negative'')';
    end if;
end;
$$;

do $$
begin
    if not exists (
        select 1
          from pg_enum e
          join pg_type t on t.oid = e.enumtypid
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v3'
           and t.typname = 'rv3_object_type'
           and e.enumlabel = 'person_group'
    ) then
        alter type retrieval_v3.rv3_object_type add value 'person_group' after 'person';
    end if;
end;
$$;

do $$
begin
    if not exists (
        select 1
          from pg_enum e
          join pg_type t on t.oid = e.enumtypid
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v3'
           and t.typname = 'rv3_object_name_kind'
           and e.enumlabel = 'art_name'
    ) then
        alter type retrieval_v3.rv3_object_name_kind add value 'art_name' after 'courtesy_name';
    end if;
end;
$$;

alter table retrieval_v3.source_packs
    add column if not exists accepted_run_fingerprint text not null default '',
    add column if not exists intake_manifest_path text not null default '';

alter table retrieval_v3.source_documents
    add column if not exists raw_document_code text not null default '';

alter table retrieval_v3.source_passages
    add column if not exists raw_passage_code text not null default '',
    add column if not exists deduped_raw_passage_codes text[] not null default array[]::text[];

alter table retrieval_v3.material_claims
    add column if not exists raw_claim_code text not null default '',
    add column if not exists claim_summary_hash text not null default '',
    add column if not exists object_group_key text not null default '';

alter table retrieval_v3.claim_rule_bindings
    add column if not exists binding_code text not null default '',
    add column if not exists raw_binding_code text not null default '';

alter table retrieval_v3.claim_rule_bindings
    drop constraint if exists rv3_claim_rule_bindings_uk;

do $$
begin
    if not exists (
        select 1
          from pg_constraint c
          join pg_namespace n on n.oid = c.connamespace
         where n.nspname = 'retrieval_v3'
           and c.conname = 'rv3_claim_rule_bindings_uk'
    ) then
        alter table retrieval_v3.claim_rule_bindings
            add constraint rv3_claim_rule_bindings_uk unique (claim_id, contract_rule_id, predicate, direction, object_role);
    end if;
end;
$$;

create unique index if not exists rv3_source_documents_pack_raw_doc_uk
on retrieval_v3.source_documents(source_pack_id, raw_document_code)
where btrim(raw_document_code) <> '';

create unique index if not exists rv3_source_passages_doc_raw_passage_uk
on retrieval_v3.source_passages(source_document_id, raw_passage_code)
where btrim(raw_passage_code) <> '';

create unique index if not exists rv3_material_claims_pack_raw_claim_uk
on retrieval_v3.material_claims(source_pack_id, raw_claim_code)
where btrim(raw_claim_code) <> '';

create index if not exists rv3_material_claims_semantic_candidate_idx
on retrieval_v3.material_claims(source_pack_id, emperor_name, object_group_key, direction, claim_summary_hash)
where btrim(object_group_key) <> '' and btrim(claim_summary_hash) <> '';

create unique index if not exists rv3_claim_rule_bindings_binding_code_uk
on retrieval_v3.claim_rule_bindings(binding_code)
where btrim(binding_code) <> '';

create table if not exists retrieval_v3.claim_source_passages (
    id bigint generated always as identity primary key,
    claim_id bigint not null references retrieval_v3.material_claims(id) on delete cascade,
    source_passage_id bigint not null references retrieval_v3.source_passages(id) on delete cascade,
    source_pack_id bigint not null references retrieval_v3.source_packs(id) on delete cascade,
    relation_kind retrieval_v3.rv3_claim_passage_relation_kind not null default 'supporting_quote',
    relation_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    constraint rv3_claim_source_passages_uk unique (claim_id, source_passage_id, relation_kind)
);

create table if not exists retrieval_v3.claim_rule_binding_candidates (
    id bigint generated always as identity primary key,
    candidate_code text not null,
    claim_id bigint not null references retrieval_v3.material_claims(id) on delete cascade,
    source_contract_rule_id bigint references retrieval_v3.rule_contract_rules(id) on delete set null,
    candidate_contract_rule_id bigint references retrieval_v3.rule_contract_rules(id) on delete set null,
    source_item_code text not null default '',
    source_rule_code text not null,
    candidate_item_code text not null default '',
    candidate_rule_code text not null,
    candidate_predicate text not null default '',
    candidate_object_role text not null default '',
    candidate_direction retrieval_v3.rv3_claim_direction,
    reason_hash text not null default '',
    candidate_reason text not null default '',
    confidence numeric(5,4),
    review_status retrieval_v3.rv3_review_status not null default 'pending',
    resolved_binding_id bigint references retrieval_v3.claim_rule_bindings(id) on delete set null,
    candidate_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv3_claim_rule_binding_candidates_code_uk unique (candidate_code),
    constraint rv3_claim_rule_binding_candidates_uk unique (
        claim_id,
        source_rule_code,
        candidate_item_code,
        candidate_rule_code,
        reason_hash
    ),
    constraint rv3_claim_rule_binding_candidates_source_rule_not_blank check (btrim(source_rule_code) <> ''),
    constraint rv3_claim_rule_binding_candidates_candidate_rule_not_blank check (btrim(candidate_rule_code) <> ''),
    constraint rv3_claim_rule_binding_candidates_confidence_ck check (confidence is null or (confidence >= 0 and confidence <= 1))
);

create table if not exists retrieval_v3.objects (
    id bigint generated always as identity primary key,
    object_code text not null,
    object_identity_key text not null,
    canonical_name text not null,
    normalized_name text not null,
    object_type retrieval_v3.rv3_object_type not null default 'person',
    identity_status retrieval_v3.rv3_object_identity_status not null default 'draft',
    curator_note text not null default '',
    identity_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv3_objects_code_uk unique (object_code),
    constraint rv3_objects_identity_key_uk unique (object_identity_key),
    constraint rv3_objects_canonical_name_not_blank check (btrim(canonical_name) <> ''),
    constraint rv3_objects_normalized_name_not_blank check (btrim(normalized_name) <> '')
);

create table if not exists retrieval_v3.person_profiles (
    id bigint generated always as identity primary key,
    person_profile_code text not null,
    object_id bigint not null references retrieval_v3.objects(id) on delete cascade,
    talent_grade retrieval_v3.rv3_person_talent_grade,
    talent_grade_basis text not null default '',
    review_status retrieval_v3.rv3_review_status not null default 'pending',
    profile_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv3_person_profiles_code_uk unique (person_profile_code),
    constraint rv3_person_profiles_object_uk unique (object_id)
);

alter table retrieval_v3.person_profiles
    alter column talent_grade drop not null;

create table if not exists retrieval_v3.person_affiliations (
    id bigint generated always as identity primary key,
    person_affiliation_code text not null,
    person_affiliation_key text not null,
    object_id bigint not null references retrieval_v3.objects(id) on delete cascade,
    affiliation_kind retrieval_v3.rv3_person_affiliation_kind not null,
    dynasty_label text not null default '',
    polity_label text not null default '',
    affiliation_label text not null default '',
    period_label text not null default '',
    period_start_year integer,
    period_end_year integer,
    affiliation_basis text not null default '',
    review_status retrieval_v3.rv3_review_status not null default 'pending',
    affiliation_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv3_person_affiliations_code_uk unique (person_affiliation_code),
    constraint rv3_person_affiliations_key_uk unique (person_affiliation_key),
    constraint rv3_person_affiliations_label_ck check (
        btrim(dynasty_label) <> ''
        or btrim(polity_label) <> ''
        or btrim(affiliation_label) <> ''
    ),
    constraint rv3_person_affiliations_period_ck check (period_start_year is null or period_end_year is null or period_start_year <= period_end_year)
);

create table if not exists retrieval_v3.person_roles (
    id bigint generated always as identity primary key,
    person_role_code text not null,
    person_role_key text not null,
    object_id bigint not null references retrieval_v3.objects(id) on delete cascade,
    person_affiliation_id bigint references retrieval_v3.person_affiliations(id) on delete set null,
    role_kind retrieval_v3.rv3_person_role_kind not null,
    dynasty_label text not null default '',
    polity_label text not null default '',
    role_title text not null default '',
    period_label text not null default '',
    period_start_year integer,
    period_end_year integer,
    role_basis text not null default '',
    review_status retrieval_v3.rv3_review_status not null default 'pending',
    role_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv3_person_roles_code_uk unique (person_role_code),
    constraint rv3_person_roles_key_uk unique (person_role_key),
    constraint rv3_person_roles_period_ck check (period_start_year is null or period_end_year is null or period_start_year <= period_end_year)
);

alter table retrieval_v3.person_roles
    add column if not exists person_affiliation_id bigint references retrieval_v3.person_affiliations(id) on delete set null;

create table if not exists retrieval_v3.object_names (
    id bigint generated always as identity primary key,
    object_name_code text not null,
    object_id bigint not null references retrieval_v3.objects(id) on delete cascade,
    name_text text not null,
    normalized_name text not null,
    name_kind retrieval_v3.rv3_object_name_kind not null default 'canonical',
    script_variant_group_key text not null default '',
    source text not null default 'retrieval_v3_review',
    review_status retrieval_v3.rv3_review_status not null default 'pending',
    name_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    constraint rv3_object_names_code_uk unique (object_name_code),
    constraint rv3_object_names_name_uk unique (object_id, normalized_name, name_kind),
    constraint rv3_object_names_text_not_blank check (btrim(name_text) <> ''),
    constraint rv3_object_names_normalized_not_blank check (btrim(normalized_name) <> '')
);

create table if not exists retrieval_v3.target_objects (
    id bigint generated always as identity primary key,
    target_object_code text not null,
    target_id bigint not null references retrieval_v3.retrieval_targets(id) on delete cascade,
    object_id bigint not null references retrieval_v3.objects(id) on delete cascade,
    source_pack_id bigint references retrieval_v3.source_packs(id) on delete set null,
    first_claim_id bigint references retrieval_v3.material_claims(id) on delete set null,
    scope_code retrieval_v3.rv3_target_object_scope not null default 'item',
    object_role text not null default '',
    review_status retrieval_v3.rv3_review_status not null default 'pending',
    target_object_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv3_target_objects_code_uk unique (target_object_code),
    constraint rv3_target_objects_scope_uk unique (target_id, object_id, scope_code)
);

create table if not exists retrieval_v3.material_object_links (
    id bigint generated always as identity primary key,
    link_code text not null,
    claim_id bigint not null references retrieval_v3.material_claims(id) on delete cascade,
    object_id bigint not null references retrieval_v3.objects(id) on delete cascade,
    target_object_id bigint references retrieval_v3.target_objects(id) on delete set null,
    role text not null,
    confidence numeric(5,4),
    review_status retrieval_v3.rv3_review_status not null default 'pending',
    link_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv3_material_object_links_code_uk unique (link_code),
    constraint rv3_material_object_links_uk unique (claim_id, object_id, role),
    constraint rv3_material_object_links_role_not_blank check (btrim(role) <> ''),
    constraint rv3_material_object_links_confidence_ck check (confidence is null or (confidence >= 0 and confidence <= 1))
);

create table if not exists retrieval_v3.target_object_attributes (
    id bigint generated always as identity primary key,
    target_object_attribute_code text not null,
    idem_key text not null,
    target_object_id bigint not null references retrieval_v3.target_objects(id) on delete cascade,
    target_id bigint not null references retrieval_v3.retrieval_targets(id) on delete cascade,
    object_id bigint not null references retrieval_v3.objects(id) on delete cascade,
    contract_rule_id bigint references retrieval_v3.rule_contract_rules(id) on delete set null,
    rule_code text not null,
    source_policy_id bigint references retrieval_v3.eval_rule_material_policies(id) on delete set null,
    source_material_object_link_id bigint references retrieval_v3.material_object_links(id) on delete set null,
    attribute_kind retrieval_v3.rv3_target_object_attribute_kind not null,
    attribute_code text not null,
    attribute_label text not null default '',
    direction retrieval_v3.rv3_claim_direction,
    confidence numeric(5,4),
    review_status retrieval_v3.rv3_review_status not null default 'pending',
    attribute_basis text not null default '',
    attribute_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv3_target_object_attributes_code_uk unique (target_object_attribute_code),
    constraint rv3_target_object_attributes_idem_uk unique (idem_key),
    constraint rv3_target_object_attributes_natural_uk unique (target_object_id, rule_code, attribute_kind, attribute_code),
    constraint rv3_target_object_attributes_rule_code_not_blank check (btrim(rule_code) <> ''),
    constraint rv3_target_object_attributes_attr_code_not_blank check (btrim(attribute_code) <> ''),
    constraint rv3_target_object_attributes_confidence_ck check (confidence is null or (confidence >= 0 and confidence <= 1))
);

create table if not exists retrieval_v3.object_resolution_queue (
    id bigint generated always as identity primary key,
    resolution_code text not null,
    idem_key text not null,
    target_id bigint not null references retrieval_v3.retrieval_targets(id) on delete cascade,
    source_pack_id bigint references retrieval_v3.source_packs(id) on delete set null,
    claim_id bigint references retrieval_v3.material_claims(id) on delete set null,
    object_name text not null,
    normalized_name text not null,
    object_type retrieval_v3.rv3_object_type not null default 'person',
    object_group_key text not null default '',
    suggested_identity_key text not null default '',
    queue_status retrieval_v3.rv3_queue_status not null default 'ready',
    priority integer not null default 100,
    diagnosis text not null default '',
    resolution_note text not null default '',
    resolved_object_id bigint references retrieval_v3.objects(id) on delete set null,
    queue_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    resolved_at timestamptz,
    constraint rv3_object_resolution_queue_code_uk unique (resolution_code),
    constraint rv3_object_resolution_queue_idem_uk unique (idem_key),
    constraint rv3_object_resolution_queue_name_not_blank check (btrim(object_name) <> ''),
    constraint rv3_object_resolution_queue_normalized_not_blank check (btrim(normalized_name) <> ''),
    constraint rv3_object_resolution_queue_priority_positive check (priority > 0)
);

create table if not exists retrieval_v3.material_review_queue (
    id bigint generated always as identity primary key,
    review_code text not null,
    idem_key text not null,
    claim_id bigint not null references retrieval_v3.material_claims(id) on delete cascade,
    binding_id bigint references retrieval_v3.claim_rule_bindings(id) on delete set null,
    candidate_id bigint references retrieval_v3.claim_rule_binding_candidates(id) on delete set null,
    review_kind text not null,
    queue_status retrieval_v3.rv3_queue_status not null default 'ready',
    priority integer not null default 100,
    diagnosis text not null default '',
    recommended_action text not null default '',
    review_note text not null default '',
    review_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    resolved_at timestamptz,
    constraint rv3_material_review_queue_code_uk unique (review_code),
    constraint rv3_material_review_queue_idem_uk unique (idem_key),
    constraint rv3_material_review_queue_kind_not_blank check (btrim(review_kind) <> ''),
    constraint rv3_material_review_queue_priority_positive check (priority > 0)
);

create table if not exists retrieval_v3.claim_rule_binding_factor_judgments (
    id bigint generated always as identity primary key,
    factor_judgment_code text not null,
    idem_key text not null,
    binding_id bigint not null references retrieval_v3.claim_rule_bindings(id) on delete cascade,
    claim_id bigint not null references retrieval_v3.material_claims(id) on delete cascade,
    target_id bigint not null references retrieval_v3.retrieval_targets(id) on delete cascade,
    source_pack_id bigint not null references retrieval_v3.source_packs(id) on delete cascade,
    item_code text not null,
    rule_code text not null,
    formula_code text not null,
    target_action retrieval_v3.rv3_factor_target_action not null,
    side retrieval_v3.rv3_factor_side,
    factor_summary jsonb not null default '{}'::jsonb,
    patch_note text not null default '',
    review_status retrieval_v3.rv3_review_status not null default 'accepted',
    judgment_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv3_claim_rule_binding_factor_judgments_code_uk unique (factor_judgment_code),
    constraint rv3_claim_rule_binding_factor_judgments_idem_uk unique (idem_key),
    constraint rv3_claim_rule_binding_factor_judgments_binding_uk unique (binding_id, formula_code),
    constraint rv3_claim_rule_binding_factor_judgments_item_not_blank check (btrim(item_code) <> ''),
    constraint rv3_claim_rule_binding_factor_judgments_rule_not_blank check (btrim(rule_code) <> ''),
    constraint rv3_claim_rule_binding_factor_judgments_formula_not_blank check (btrim(formula_code) <> ''),
    constraint rv3_claim_rule_binding_factor_judgments_score_side_ck check (
        (target_action = 'score' and side is not null)
        or (target_action <> 'score')
    )
);

create table if not exists retrieval_v3.claim_rule_binding_factor_choices (
    id bigint generated always as identity primary key,
    factor_choice_code text not null,
    idem_key text not null,
    factor_judgment_id bigint not null references retrieval_v3.claim_rule_binding_factor_judgments(id) on delete cascade,
    binding_id bigint not null references retrieval_v3.claim_rule_bindings(id) on delete cascade,
    factor_id bigint not null references retrieval_v3.eval_rule_factors(id) on delete restrict,
    factor_option_id bigint not null references retrieval_v3.eval_rule_factor_options(id) on delete restrict,
    factor_name text not null,
    option_code text not null,
    option_label text not null,
    value_num numeric(18,6),
    choice_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv3_claim_rule_binding_factor_choices_code_uk unique (factor_choice_code),
    constraint rv3_claim_rule_binding_factor_choices_idem_uk unique (idem_key),
    constraint rv3_claim_rule_binding_factor_choices_factor_uk unique (factor_judgment_id, factor_name),
    constraint rv3_claim_rule_binding_factor_choices_factor_not_blank check (btrim(factor_name) <> ''),
    constraint rv3_claim_rule_binding_factor_choices_option_code_not_blank check (btrim(option_code) <> ''),
    constraint rv3_claim_rule_binding_factor_choices_option_label_not_blank check (btrim(option_label) <> '')
);

create table if not exists retrieval_v3.claim_rule_binding_material_scores (
    id bigint generated always as identity primary key,
    material_score_code text not null,
    idem_key text not null,
    factor_judgment_id bigint not null references retrieval_v3.claim_rule_binding_factor_judgments(id) on delete cascade,
    binding_id bigint not null references retrieval_v3.claim_rule_bindings(id) on delete cascade,
    claim_id bigint not null references retrieval_v3.material_claims(id) on delete cascade,
    target_id bigint not null references retrieval_v3.retrieval_targets(id) on delete cascade,
    source_pack_id bigint not null references retrieval_v3.source_packs(id) on delete cascade,
    object_id bigint not null references retrieval_v3.objects(id) on delete restrict,
    target_object_id bigint references retrieval_v3.target_objects(id) on delete set null,
    item_code text not null,
    rule_code text not null,
    formula_code text not null,
    side retrieval_v3.rv3_factor_side not null,
    raw_score numeric(18,6) not null,
    abs_score numeric(18,6) not null,
    factor_values jsonb not null default '{}'::jsonb,
    score_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv3_claim_rule_binding_material_scores_code_uk unique (material_score_code),
    constraint rv3_claim_rule_binding_material_scores_idem_uk unique (idem_key),
    constraint rv3_claim_rule_binding_material_scores_judgment_uk unique (factor_judgment_id),
    constraint rv3_claim_rule_binding_material_scores_item_not_blank check (btrim(item_code) <> ''),
    constraint rv3_claim_rule_binding_material_scores_rule_not_blank check (btrim(rule_code) <> ''),
    constraint rv3_claim_rule_binding_material_scores_formula_not_blank check (btrim(formula_code) <> ''),
    constraint rv3_claim_rule_binding_material_scores_abs_nonnegative check (abs_score >= 0)
);

create table if not exists retrieval_v3.target_rule_score_clusters (
    id bigint generated always as identity primary key,
    rule_score_code text not null,
    idem_key text not null,
    target_id bigint not null references retrieval_v3.retrieval_targets(id) on delete cascade,
    item_code text not null,
    rule_code text not null,
    formula_code text not null,
    positive_signal numeric(18,6) not null default 0,
    negative_signal numeric(18,6) not null default 0,
    scored_judgment_count integer not null default 0,
    supporting_judgment_count integer not null default 0,
    excluded_judgment_count integer not null default 0,
    object_side_scores jsonb not null default '{}'::jsonb,
    calc_detail jsonb not null default '{}'::jsonb,
    review_status retrieval_v3.rv3_review_status not null default 'accepted',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv3_target_rule_score_clusters_code_uk unique (rule_score_code),
    constraint rv3_target_rule_score_clusters_idem_uk unique (idem_key),
    constraint rv3_target_rule_score_clusters_target_rule_uk unique (target_id, rule_code, formula_code),
    constraint rv3_target_rule_score_clusters_item_not_blank check (btrim(item_code) <> ''),
    constraint rv3_target_rule_score_clusters_rule_not_blank check (btrim(rule_code) <> ''),
    constraint rv3_target_rule_score_clusters_formula_not_blank check (btrim(formula_code) <> ''),
    constraint rv3_target_rule_score_clusters_signal_nonnegative check (positive_signal >= 0 and negative_signal >= 0),
    constraint rv3_target_rule_score_clusters_counts_nonnegative check (
        scored_judgment_count >= 0
        and supporting_judgment_count >= 0
        and excluded_judgment_count >= 0
    )
);

create index if not exists rv3_claim_source_passages_pack_idx
on retrieval_v3.claim_source_passages(source_pack_id, claim_id);

create index if not exists rv3_claim_rule_binding_candidates_review_idx
on retrieval_v3.claim_rule_binding_candidates(review_status, candidate_rule_code, created_at);

create index if not exists rv3_objects_name_idx
on retrieval_v3.objects(normalized_name, object_type, identity_status);

create index if not exists rv3_person_profiles_grade_idx
on retrieval_v3.person_profiles(talent_grade, review_status);

create index if not exists rv3_person_affiliations_object_idx
on retrieval_v3.person_affiliations(object_id, affiliation_kind, review_status);

create index if not exists rv3_person_roles_object_idx
on retrieval_v3.person_roles(object_id, role_kind, review_status);

create index if not exists rv3_person_roles_affiliation_idx
on retrieval_v3.person_roles(person_affiliation_id) where person_affiliation_id is not null;

create index if not exists rv3_object_names_variant_idx
on retrieval_v3.object_names(script_variant_group_key, normalized_name) where review_status in ('pending', 'accepted');

create index if not exists rv3_target_objects_target_idx
on retrieval_v3.target_objects(target_id, review_status, scope_code);

create index if not exists rv3_material_object_links_claim_idx
on retrieval_v3.material_object_links(claim_id, review_status);

create index if not exists rv3_target_object_attributes_rule_idx
on retrieval_v3.target_object_attributes(target_id, rule_code, attribute_kind, review_status);

create index if not exists rv3_object_resolution_queue_ready_idx
on retrieval_v3.object_resolution_queue(priority, created_at) where queue_status in ('ready', 'needs_review');

create index if not exists rv3_material_review_queue_ready_idx
on retrieval_v3.material_review_queue(priority, created_at) where queue_status in ('ready', 'needs_review');

create index if not exists rv3_claim_rule_binding_factor_judgments_target_idx
on retrieval_v3.claim_rule_binding_factor_judgments(target_id, item_code, rule_code, target_action, review_status);

create index if not exists rv3_claim_rule_binding_factor_choices_option_idx
on retrieval_v3.claim_rule_binding_factor_choices(factor_id, factor_option_id);

create index if not exists rv3_claim_rule_binding_material_scores_target_idx
on retrieval_v3.claim_rule_binding_material_scores(target_id, item_code, rule_code, side);

create index if not exists rv3_claim_rule_binding_material_scores_object_idx
on retrieval_v3.claim_rule_binding_material_scores(object_id, side, abs_score);

create index if not exists rv3_target_rule_score_clusters_target_idx
on retrieval_v3.target_rule_score_clusters(target_id, item_code, rule_code, review_status);

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
    case pp.talent_grade
        when 'historic_talent' then '历史级人才'
        when 'top_talent' then '顶级人才'
        when 'important_talent' then '重要人才'
        when 'ordinary_talent' then '普通人才'
        when 'sycophant' then '佞臣'
        when 'major_sycophant' then '大佞臣'
        when 'historic_sycophant' then '历史级佞臣'
    end as talent_quality_label,
    'rule_requirement'::retrieval_v3.rv3_target_object_attribute_kind as attribute_kind,
    'talent_quality'::text as attribute_code,
    pp.review_status as profile_review_status,
    tob.review_status as target_object_review_status
from retrieval_v3.eval_rule_material_policies p
join retrieval_v3.target_objects tob on tob.scope_code = 'item'
join retrieval_v3.retrieval_targets rt on rt.id = tob.target_id and rt.item_code = p.item_code
join retrieval_v3.objects o on o.id = tob.object_id and o.object_type = 'person'
join retrieval_v3.person_profiles pp on pp.object_id = o.id and pp.review_status in ('pending', 'accepted') and pp.talent_grade is not null
where p.rule_code = 'team_building'
  and p.policy_status = 'active'
  and p.require_attrs @> array['talent_quality']::text[]
  and (p.candidate_obj_types = array[]::text[] or 'person' = any(p.candidate_obj_types));

create or replace view retrieval_v3.v_person_profile_names as
select
    pp.id as person_profile_id,
    pp.person_profile_code,
    o.id as object_id,
    o.object_code,
    o.canonical_name,
    o.normalized_name,
    coalesce(array_remove(array_agg(distinct onm.name_text) filter (where onm.name_kind::text = 'canonical'), null), array[]::text[]) as canonical_names,
    coalesce(array_remove(array_agg(distinct onm.name_text) filter (where onm.name_kind::text = 'script_variant'), null), array[]::text[]) as script_variant_names,
    coalesce(array_remove(array_agg(distinct onm.name_text) filter (where onm.name_kind::text = 'courtesy_name'), null), array[]::text[]) as courtesy_names,
    coalesce(array_remove(array_agg(distinct onm.name_text) filter (where onm.name_kind::text = 'art_name'), null), array[]::text[]) as art_names,
    coalesce(array_remove(array_agg(distinct onm.name_text) filter (where onm.name_kind::text = 'alias'), null), array[]::text[]) as alias_names,
    coalesce(array_remove(array_agg(distinct onm.name_text) filter (where onm.name_kind::text = 'temple_name'), null), array[]::text[]) as temple_names,
    coalesce(array_remove(array_agg(distinct onm.name_text) filter (where onm.name_kind::text = 'posthumous_name'), null), array[]::text[]) as posthumous_names,
    coalesce(array_remove(array_agg(distinct onm.name_text) filter (where onm.name_kind::text = 'reign_title'), null), array[]::text[]) as reign_titles,
    pp.talent_grade,
    pp.talent_grade_basis,
    pp.review_status
from retrieval_v3.person_profiles pp
join retrieval_v3.objects o on o.id = pp.object_id and o.object_type = 'person'
left join retrieval_v3.object_names onm on onm.object_id = o.id and onm.review_status in ('pending', 'accepted')
group by
    pp.id,
    pp.person_profile_code,
    o.id,
    o.object_code,
    o.canonical_name,
    o.normalized_name,
    pp.talent_grade,
    pp.talent_grade_basis,
    pp.review_status;

comment on type retrieval_v3.rv3_claim_direction is 'claim 或候选绑定方向枚举：只允许 positive、negative、neutral、mixed。';
comment on type retrieval_v3.rv3_review_status is '消费层复核状态枚举：用于候选、对象名称、对象链接和目标对象挂载。';
comment on type retrieval_v3.rv3_object_identity_status is '对象身份生命周期枚举：区分草稿、有效、待复核、合并、拒绝和退役。';
comment on type retrieval_v3.rv3_queue_status is '消费层队列状态枚举：重复导入不得把 running 或 resolved 改回 ready。';
comment on type retrieval_v3.rv3_object_type is '消费层对象类型枚举：区分单个人物 person、人物集合 person_group、机构、地点、事件、文本和其他对象。';
comment on type retrieval_v3.rv3_person_talent_grade is '人物画像人才等级枚举：包括历史级、顶级、重要、普通人才，以及佞臣、大佞臣、历史级佞臣。';
comment on type retrieval_v3.rv3_person_role_kind is '人物身份阶段枚举：区分皇帝、继承人、亲王、臣僚、将领、后妃、宗室、宦官、学者、叛乱者和其他身份。';
comment on type retrieval_v3.rv3_person_affiliation_kind is '人物归属类型枚举：区分朝代、政权、任仕、出身、派系、家族和其他归属。';
comment on type retrieval_v3.rv3_object_name_kind is '对象名称类型枚举：区分 canonical、alias、script_variant、字、号及常见历史称谓。';
comment on type retrieval_v3.rv3_target_object_scope is '目标对象作用域枚举：区分 item、rule、source_pack 和人工挂载。';
comment on type retrieval_v3.rv3_target_object_attribute_kind is '目标对象规则语境属性类型枚举：区分计分角色、规则必需属性、因子输入和综合评估。';
comment on type retrieval_v3.rv3_claim_passage_relation_kind is 'claim 与 passage 关系类型枚举：区分直接支持、上下文和来源指针。';
comment on type retrieval_v3.rv3_factor_target_action is 'binding 因子化去向枚举：区分直接入分、仅作上下文和排除。';
comment on type retrieval_v3.rv3_factor_side is 'binding 因子化计分方向枚举：只允许正向或负向。';

comment on table retrieval_v3.claim_source_passages is 'claim 与史源段落的多对多引用表：保留 clean 包中一个 claim 对多个 passage 的证据关系，可幂等重放。';
comment on table retrieval_v3.claim_rule_binding_candidates is 'claim 跨规则候选池：保存 secondary binding 线索，等待未来 item 或 rule contract 解析为正式 binding。';
comment on table retrieval_v3.objects is '消费层对象身份表：只保存经过对象身份复核后的 canonical object，不复用旧对象池 ID。';
comment on table retrieval_v3.person_profiles is '人物画像表：只承载 person 对象的人才等级等人物专属画像，不作为泛属性桶。';
comment on table retrieval_v3.person_affiliations is '人物归属阶段表：记录 person 与朝代、政权、任仕、出身、派系或家族的多段关系，供身份阶段和计分语境引用。';
comment on table retrieval_v3.person_roles is '人物身份阶段表：记录同一 person 在不同朝代、阶段或政治语境下的身份，不拆分 canonical person。';
comment on table retrieval_v3.object_names is '消费层对象名称表：保存 canonical 名、别名、繁简异名和名称复核状态。';
comment on table retrieval_v3.target_objects is '目标对象挂载表：记录某 retrieval target 下已经确认出现的对象身份。';
comment on table retrieval_v3.material_object_links is '材料事实到对象身份的角色关系表：把 claim 中的人或对象解析为 canonical object。';
comment on table retrieval_v3.target_object_attributes is '目标对象规则语境属性表：保存某 target/rule 下的对象计分角色、规则必需属性和因子输入，不承载人物本体画像。';
comment on table retrieval_v3.object_resolution_queue is '对象身份复核队列表：承接 object_resolution_worklist，说明字段只写具体冲突和处置结论。';
comment on table retrieval_v3.material_review_queue is '材料复核队列表：承接 material_review_worklist，说明字段只写具体诊断、动作和复核结论。';
comment on table retrieval_v3.claim_rule_binding_factor_judgments is 'binding 因子化判定表：记录每条 primary binding 是否入分、仅作上下文或排除。';
comment on table retrieval_v3.claim_rule_binding_factor_choices is 'binding 因子枚举选择表：把入分 binding 的每个 factor 解析到规则快照中的枚举选项。';
comment on table retrieval_v3.claim_rule_binding_material_scores is 'binding 材料分表：把已入分因子判定计算为单条材料 raw_score 和封顶 abs_score。';
comment on table retrieval_v3.target_rule_score_clusters is '目标规则信号聚合表：按 target/rule/formula 保存同对象折减后的正负信号。';
comment on view retrieval_v3.v_team_building_talent_candidates is '建立团队人才候选适配视图：只读规则策略表 require_attrs=talent_quality，并映射到 person_profiles.talent_grade。';
comment on view retrieval_v3.v_person_profile_names is '人物画像名称聚合视图：按 object_id 汇总 canonical 名、繁简异名、字、号、庙号、谥号和年号，便于人物画像连表查询。';

comment on column retrieval_v3.source_packs.accepted_run_fingerprint is 'accepted clean run 的稳定指纹；参与识别同一轮收货包，不承载说明文本。';
comment on column retrieval_v3.source_packs.intake_manifest_path is '生成本包的 intake_manifest.json 仓库相对路径，用于重放和审计。';
comment on column retrieval_v3.source_documents.raw_document_code is 'clean judge 原始 document_code；同一 source_pack 内作为文档幂等键。';
comment on column retrieval_v3.source_passages.raw_passage_code is 'clean judge 原始 passage_code；同一 source_document 内作为段落幂等键。';
comment on column retrieval_v3.source_passages.deduped_raw_passage_codes is '生成 rowset 时被合并到本段落的原始 passage_code 列表。';
comment on column retrieval_v3.material_claims.raw_claim_code is 'clean judge 原始 claim_code；同一 source_pack 内作为 claim 幂等键。';
comment on column retrieval_v3.material_claims.claim_summary_hash is 'claim_summary 的稳定 hash；仅用于语义重复候选检查，不直接删除重复 claim。';
comment on column retrieval_v3.material_claims.object_group_key is '对象名繁简或脚本变体归并键；用于发现疑似同对象 claim。';
comment on column retrieval_v3.claim_rule_bindings.binding_code is 'clean judge primary binding 稳定代码；非空时全局唯一。';
comment on column retrieval_v3.claim_rule_bindings.raw_binding_code is 'clean judge 原始 binding_code；用于重放和导入审计。';

comment on column retrieval_v3.claim_source_passages.id is '本表内部主键。';
comment on column retrieval_v3.claim_source_passages.claim_id is '被史源段落支持的 material_claims.id。';
comment on column retrieval_v3.claim_source_passages.source_passage_id is '提供原文支持的 source_passages.id。';
comment on column retrieval_v3.claim_source_passages.source_pack_id is '冗余保存 source_packs.id，便于按包删除、重放和审计。';
comment on column retrieval_v3.claim_source_passages.relation_kind is 'claim 与 passage 的关系类型，例如 supporting_quote。';
comment on column retrieval_v3.claim_source_passages.relation_payload is '关系原始 payload；保存导入时的证据引用上下文。';
comment on column retrieval_v3.claim_source_passages.created_at is '关系首次写入时间。';

comment on column retrieval_v3.claim_rule_binding_candidates.id is '本表内部主键。';
comment on column retrieval_v3.claim_rule_binding_candidates.candidate_code is '跨规则候选稳定代码；来自 rowset candidate_code。';
comment on column retrieval_v3.claim_rule_binding_candidates.claim_id is '候选绑定指向的 material_claims.id。';
comment on column retrieval_v3.claim_rule_binding_candidates.source_contract_rule_id is '产生候选的源 rule contract rule；允许为空以支持旧包回放。';
comment on column retrieval_v3.claim_rule_binding_candidates.candidate_contract_rule_id is '候选未来可能解析到的 rule contract rule；contract 未上线时为空。';
comment on column retrieval_v3.claim_rule_binding_candidates.source_item_code is '产生候选的源 item_code，例如 I5B。';
comment on column retrieval_v3.claim_rule_binding_candidates.source_rule_code is '产生候选的源 rule_code，例如 delegation。';
comment on column retrieval_v3.claim_rule_binding_candidates.candidate_item_code is '候选目标 item_code；未知时留空，不用猜测。';
comment on column retrieval_v3.claim_rule_binding_candidates.candidate_rule_code is '候选目标 rule_code，例如 team_building。';
comment on column retrieval_v3.claim_rule_binding_candidates.candidate_predicate is '候选目标 predicate；未知时留空。';
comment on column retrieval_v3.claim_rule_binding_candidates.candidate_object_role is '候选目标 object_role；未知时留空。';
comment on column retrieval_v3.claim_rule_binding_candidates.candidate_direction is '候选目标方向；未知时为空。';
comment on column retrieval_v3.claim_rule_binding_candidates.reason_hash is 'candidate_reason 的稳定 hash；参与候选幂等键。';
comment on column retrieval_v3.claim_rule_binding_candidates.candidate_reason is '候选原因；只写中文高信息判断，模板式原因留空。';
comment on column retrieval_v3.claim_rule_binding_candidates.confidence is '候选置信度，范围 0 到 1；未知时为空。';
comment on column retrieval_v3.claim_rule_binding_candidates.review_status is '候选复核状态；pending 表示尚未解析为正式 binding。';
comment on column retrieval_v3.claim_rule_binding_candidates.resolved_binding_id is '候选解析成功后对应的 claim_rule_bindings.id。';
comment on column retrieval_v3.claim_rule_binding_candidates.candidate_payload is '候选原始 payload；保存 judge 输出和导入来源。';
comment on column retrieval_v3.claim_rule_binding_candidates.created_at is '候选首次写入时间。';
comment on column retrieval_v3.claim_rule_binding_candidates.updated_at is '候选最近更新时间。';

comment on column retrieval_v3.objects.id is '本表内部主键。';
comment on column retrieval_v3.objects.object_code is '消费层对象稳定代码；不复用旧对象池 ID。';
comment on column retrieval_v3.objects.object_identity_key is '对象身份幂等键；由人工复核或可信规则生成。';
comment on column retrieval_v3.objects.canonical_name is '对象 canonical 展示名。';
comment on column retrieval_v3.objects.normalized_name is '对象归一化名称，用于检索和冲突检查。';
comment on column retrieval_v3.objects.object_type is '对象类型，例如 person 或 person_group。';
comment on column retrieval_v3.objects.identity_status is '对象身份生命周期状态。';
comment on column retrieval_v3.objects.curator_note is '对象身份复核说明；只写具体中文判断，模板文本留空。';
comment on column retrieval_v3.objects.identity_payload is '对象身份复核原始 payload 和外部参考摘要。';
comment on column retrieval_v3.objects.created_at is '对象身份首次写入时间。';
comment on column retrieval_v3.objects.updated_at is '对象身份最近更新时间。';

comment on column retrieval_v3.person_profiles.id is '本表内部主键。';
comment on column retrieval_v3.person_profiles.person_profile_code is '人物画像稳定代码。';
comment on column retrieval_v3.person_profiles.object_id is '画像所属 objects.id；调用方必须只挂载 object_type 为 person 的对象。';
comment on column retrieval_v3.person_profiles.talent_grade is '人物人才等级结构化枚举；旧库无命中或待人工复核时为空。';
comment on column retrieval_v3.person_profiles.talent_grade_basis is '人物评价简介；非空时以 canonical 人名加中文逗号开头，只写中文具体判断和关键材料，不写模板文本。';
comment on column retrieval_v3.person_profiles.review_status is '人物画像复核状态。';
comment on column retrieval_v3.person_profiles.profile_payload is '人物画像来源 payload 和复核上下文。';
comment on column retrieval_v3.person_profiles.created_at is '人物画像首次写入时间。';
comment on column retrieval_v3.person_profiles.updated_at is '人物画像最近更新时间。';

comment on column retrieval_v3.person_affiliations.id is '本表内部主键。';
comment on column retrieval_v3.person_affiliations.person_affiliation_code is '人物归属阶段稳定代码。';
comment on column retrieval_v3.person_affiliations.person_affiliation_key is '人物归属阶段幂等键；重复导入不得生成第二条同阶段归属。';
comment on column retrieval_v3.person_affiliations.object_id is '归属所属 objects.id；调用方必须只挂载 object_type 为 person 的对象。';
comment on column retrieval_v3.person_affiliations.affiliation_kind is '人物归属类型，例如 dynasty、polity、service。';
comment on column retrieval_v3.person_affiliations.dynasty_label is '朝代展示标签；跨朝人物可有多条归属阶段。';
comment on column retrieval_v3.person_affiliations.polity_label is '政权或政治实体展示标签；与朝代不完全相同时填写。';
comment on column retrieval_v3.person_affiliations.affiliation_label is '归属展示名；朝代和政权字段不能准确表达时填写。';
comment on column retrieval_v3.person_affiliations.period_label is '归属阶段展示名，例如武周任仕、开元初。';
comment on column retrieval_v3.person_affiliations.period_start_year is '归属阶段起始年份；未知时为空。';
comment on column retrieval_v3.person_affiliations.period_end_year is '归属阶段结束年份；未知时为空。';
comment on column retrieval_v3.person_affiliations.affiliation_basis is '归属阶段依据；只写中文具体判断和关键材料，不写模板文本。';
comment on column retrieval_v3.person_affiliations.review_status is '人物归属阶段复核状态。';
comment on column retrieval_v3.person_affiliations.affiliation_payload is '人物归属阶段来源 payload 和复核上下文。';
comment on column retrieval_v3.person_affiliations.created_at is '人物归属阶段首次写入时间。';
comment on column retrieval_v3.person_affiliations.updated_at is '人物归属阶段最近更新时间。';

comment on column retrieval_v3.person_roles.id is '本表内部主键。';
comment on column retrieval_v3.person_roles.person_role_code is '人物身份阶段稳定代码。';
comment on column retrieval_v3.person_roles.person_role_key is '人物身份阶段幂等键；重复导入不得生成第二条同阶段身份。';
comment on column retrieval_v3.person_roles.object_id is '身份所属 objects.id；调用方必须只挂载 object_type 为 person 的对象。';
comment on column retrieval_v3.person_roles.person_affiliation_id is '身份阶段引用的人物归属阶段；无法确定或暂未归一时为空。';
comment on column retrieval_v3.person_roles.role_kind is '人物身份阶段类型，例如 emperor、minister、general。';
comment on column retrieval_v3.person_roles.dynasty_label is '朝代展示标签；跨朝人物可有多条身份阶段。';
comment on column retrieval_v3.person_roles.polity_label is '政权或政治实体展示标签；与朝代不完全相同时填写。';
comment on column retrieval_v3.person_roles.role_title is '身份或官职展示名；未知时留空。';
comment on column retrieval_v3.person_roles.period_label is '阶段展示名，例如登基前、在位期、晚年。';
comment on column retrieval_v3.person_roles.period_start_year is '身份阶段起始年份；未知时为空。';
comment on column retrieval_v3.person_roles.period_end_year is '身份阶段结束年份；未知时为空。';
comment on column retrieval_v3.person_roles.role_basis is '身份阶段依据；只写中文具体判断和关键材料，不写模板文本。';
comment on column retrieval_v3.person_roles.review_status is '人物身份阶段复核状态。';
comment on column retrieval_v3.person_roles.role_payload is '人物身份阶段来源 payload 和复核上下文。';
comment on column retrieval_v3.person_roles.created_at is '人物身份阶段首次写入时间。';
comment on column retrieval_v3.person_roles.updated_at is '人物身份阶段最近更新时间。';

comment on column retrieval_v3.object_names.id is '本表内部主键。';
comment on column retrieval_v3.object_names.object_name_code is '对象名称记录稳定代码。';
comment on column retrieval_v3.object_names.object_id is '名称所属 objects.id。';
comment on column retrieval_v3.object_names.name_text is '对象名称原文。';
comment on column retrieval_v3.object_names.normalized_name is '对象名称归一化文本。';
comment on column retrieval_v3.object_names.name_kind is '名称类型，例如 canonical、alias、script_variant、courtesy_name、art_name。';
comment on column retrieval_v3.object_names.script_variant_group_key is '繁简或脚本变体归并键；用于发现别名重复。';
comment on column retrieval_v3.object_names.source is '名称来源，例如 retrieval_v3_review。';
comment on column retrieval_v3.object_names.review_status is '名称复核状态。';
comment on column retrieval_v3.object_names.name_payload is '名称来源 payload 和复核上下文。';
comment on column retrieval_v3.object_names.created_at is '名称首次写入时间。';

comment on column retrieval_v3.target_objects.id is '本表内部主键。';
comment on column retrieval_v3.target_objects.target_object_code is '目标对象挂载稳定代码。';
comment on column retrieval_v3.target_objects.target_id is '对象出现的 retrieval_targets.id。';
comment on column retrieval_v3.target_objects.object_id is '已解析的 objects.id。';
comment on column retrieval_v3.target_objects.source_pack_id is '首次确认该对象的 source_packs.id；未知时为空。';
comment on column retrieval_v3.target_objects.first_claim_id is '首次支持该对象挂载的 material_claims.id。';
comment on column retrieval_v3.target_objects.scope_code is '挂载作用域，例如 item 或具体 rule。';
comment on column retrieval_v3.target_objects.object_role is '对象在目标下的主要角色；未知时留空。';
comment on column retrieval_v3.target_objects.review_status is '目标对象挂载复核状态。';
comment on column retrieval_v3.target_objects.target_object_payload is '目标对象挂载 payload 和来源上下文。';
comment on column retrieval_v3.target_objects.created_at is '目标对象首次写入时间。';
comment on column retrieval_v3.target_objects.updated_at is '目标对象最近更新时间。';

comment on column retrieval_v3.material_object_links.id is '本表内部主键。';
comment on column retrieval_v3.material_object_links.link_code is 'claim-object 关系稳定代码。';
comment on column retrieval_v3.material_object_links.claim_id is '关系来源 material_claims.id。';
comment on column retrieval_v3.material_object_links.object_id is '关系目标 objects.id。';
comment on column retrieval_v3.material_object_links.target_object_id is '同一目标下的 target_objects.id；未挂载前为空。';
comment on column retrieval_v3.material_object_links.role is '对象在 claim 中的角色，例如 scored_object、context_object。';
comment on column retrieval_v3.material_object_links.confidence is '对象解析置信度，范围 0 到 1；未知时为空。';
comment on column retrieval_v3.material_object_links.review_status is 'claim-object 关系复核状态。';
comment on column retrieval_v3.material_object_links.link_payload is 'claim-object 关系 payload 和复核上下文。';
comment on column retrieval_v3.material_object_links.created_at is '关系首次写入时间。';
comment on column retrieval_v3.material_object_links.updated_at is '关系最近更新时间。';

comment on column retrieval_v3.target_object_attributes.id is '本表内部主键。';
comment on column retrieval_v3.target_object_attributes.target_object_attribute_code is '目标对象规则语境属性稳定代码。';
comment on column retrieval_v3.target_object_attributes.idem_key is '目标对象规则语境属性幂等键；重复导入不得新增第二条。';
comment on column retrieval_v3.target_object_attributes.target_object_id is '属性所属 target_objects.id。';
comment on column retrieval_v3.target_object_attributes.target_id is '属性所属 retrieval_targets.id。';
comment on column retrieval_v3.target_object_attributes.object_id is '属性所属 objects.id。';
comment on column retrieval_v3.target_object_attributes.contract_rule_id is '属性对应的 rule_contract_rules.id；跨规则候选未解析时可为空。';
comment on column retrieval_v3.target_object_attributes.rule_code is '属性所属 rule_code；例如 team_building。';
comment on column retrieval_v3.target_object_attributes.source_policy_id is '触发该属性的 eval_rule_material_policies.id；未知时为空。';
comment on column retrieval_v3.target_object_attributes.source_material_object_link_id is '触发该属性的 material_object_links.id；由对象材料推导时填写。';
comment on column retrieval_v3.target_object_attributes.attribute_kind is '规则语境属性类型，例如 scoring_role 或 rule_requirement。';
comment on column retrieval_v3.target_object_attributes.attribute_code is '规则语境属性代码；来自规则策略、因子或对象关系词表。';
comment on column retrieval_v3.target_object_attributes.attribute_label is '规则语境属性中文展示标签；未知时留空。';
comment on column retrieval_v3.target_object_attributes.direction is '规则语境属性方向；无方向时为空。';
comment on column retrieval_v3.target_object_attributes.confidence is '规则语境属性置信度，范围 0 到 1；未知时为空。';
comment on column retrieval_v3.target_object_attributes.review_status is '规则语境属性复核状态。';
comment on column retrieval_v3.target_object_attributes.attribute_basis is '规则语境属性依据；只写中文具体判断和关键材料，不写模板文本。';
comment on column retrieval_v3.target_object_attributes.attribute_payload is '规则语境属性来源 payload 和复核上下文。';
comment on column retrieval_v3.target_object_attributes.created_at is '规则语境属性首次写入时间。';
comment on column retrieval_v3.target_object_attributes.updated_at is '规则语境属性最近更新时间。';

comment on column retrieval_v3.object_resolution_queue.id is '本表内部主键。';
comment on column retrieval_v3.object_resolution_queue.resolution_code is '对象身份复核任务稳定代码。';
comment on column retrieval_v3.object_resolution_queue.idem_key is '对象身份复核任务幂等键；重复导入不得新增第二条。';
comment on column retrieval_v3.object_resolution_queue.target_id is '复核对象所属 retrieval_targets.id。';
comment on column retrieval_v3.object_resolution_queue.source_pack_id is '触发复核的 source_packs.id；未知时为空。';
comment on column retrieval_v3.object_resolution_queue.claim_id is '触发复核的 material_claims.id；无具体 claim 时为空。';
comment on column retrieval_v3.object_resolution_queue.object_name is '待解析对象名原文。';
comment on column retrieval_v3.object_resolution_queue.normalized_name is '待解析对象名归一化文本。';
comment on column retrieval_v3.object_resolution_queue.object_type is '待解析对象类型。';
comment on column retrieval_v3.object_resolution_queue.object_group_key is '繁简或脚本变体归并键。';
comment on column retrieval_v3.object_resolution_queue.suggested_identity_key is '工具建议的对象身份键；人工未确认前只作参考。';
comment on column retrieval_v3.object_resolution_queue.queue_status is '对象复核队列状态；重复导入不得把 running 或 resolved 打回 ready。';
comment on column retrieval_v3.object_resolution_queue.priority is '复核优先级；数字越小越优先。';
comment on column retrieval_v3.object_resolution_queue.diagnosis is '对象复核诊断；只写中文具体冲突、缺源或同名风险。';
comment on column retrieval_v3.object_resolution_queue.resolution_note is '对象复核结论；只写中文具体处置意见，模板文本留空。';
comment on column retrieval_v3.object_resolution_queue.resolved_object_id is '复核完成后解析到的 objects.id。';
comment on column retrieval_v3.object_resolution_queue.queue_payload is '对象复核任务 payload 和来源上下文。';
comment on column retrieval_v3.object_resolution_queue.created_at is '复核任务首次写入时间。';
comment on column retrieval_v3.object_resolution_queue.updated_at is '复核任务最近更新时间。';
comment on column retrieval_v3.object_resolution_queue.resolved_at is '复核任务完成时间。';

comment on column retrieval_v3.material_review_queue.id is '本表内部主键。';
comment on column retrieval_v3.material_review_queue.review_code is '材料复核任务稳定代码。';
comment on column retrieval_v3.material_review_queue.idem_key is '材料复核任务幂等键；重复导入不得新增第二条。';
comment on column retrieval_v3.material_review_queue.claim_id is '复核任务关联的 material_claims.id。';
comment on column retrieval_v3.material_review_queue.binding_id is '复核任务关联的 claim_rule_bindings.id；无正式 binding 时为空。';
comment on column retrieval_v3.material_review_queue.candidate_id is '复核任务关联的 claim_rule_binding_candidates.id；无候选时为空。';
comment on column retrieval_v3.material_review_queue.review_kind is '复核类型，例如 object_payload_gap 或 non_atomic_direction。';
comment on column retrieval_v3.material_review_queue.queue_status is '材料复核队列状态；重复导入不得把 running 或 resolved 打回 ready。';
comment on column retrieval_v3.material_review_queue.priority is '复核优先级；数字越小越优先。';
comment on column retrieval_v3.material_review_queue.diagnosis is '材料复核诊断；只写中文具体问题和证据定位。';
comment on column retrieval_v3.material_review_queue.recommended_action is '建议动作；只写中文具体处置，不写模板句。';
comment on column retrieval_v3.material_review_queue.review_note is '人工复核结论；只写中文具体判断，未复核时留空。';
comment on column retrieval_v3.material_review_queue.review_payload is '材料复核任务 payload 和来源上下文。';
comment on column retrieval_v3.material_review_queue.created_at is '复核任务首次写入时间。';
comment on column retrieval_v3.material_review_queue.updated_at is '复核任务最近更新时间。';
comment on column retrieval_v3.material_review_queue.resolved_at is '复核任务完成时间。';

comment on column retrieval_v3.claim_rule_binding_factor_judgments.id is '本表内部主键。';
comment on column retrieval_v3.claim_rule_binding_factor_judgments.factor_judgment_code is 'binding 因子化判定稳定代码。';
comment on column retrieval_v3.claim_rule_binding_factor_judgments.idem_key is 'binding 因子化判定幂等键；同一 binding 和公式重复导入不得新增第二条。';
comment on column retrieval_v3.claim_rule_binding_factor_judgments.binding_id is '被因子化的 claim_rule_bindings.id。';
comment on column retrieval_v3.claim_rule_binding_factor_judgments.claim_id is 'binding 所属 material_claims.id，冗余保存便于审计。';
comment on column retrieval_v3.claim_rule_binding_factor_judgments.target_id is 'binding 所属 retrieval_targets.id，冗余保存便于按目标汇总。';
comment on column retrieval_v3.claim_rule_binding_factor_judgments.source_pack_id is 'binding 来源 source_packs.id，便于按包重放和回滚。';
comment on column retrieval_v3.claim_rule_binding_factor_judgments.item_code is '因子化判定所属 item_code，例如 I5B。';
comment on column retrieval_v3.claim_rule_binding_factor_judgments.rule_code is '因子化判定所属 rule_code，例如 delegation。';
comment on column retrieval_v3.claim_rule_binding_factor_judgments.formula_code is '因子化判定使用的公式代码，例如 evidence_cluster_signal_v3。';
comment on column retrieval_v3.claim_rule_binding_factor_judgments.target_action is '因子化去向：score 入分、supporting_only 仅作上下文、exclude 排除。';
comment on column retrieval_v3.claim_rule_binding_factor_judgments.side is '入分方向；target_action 为 score 时必须填写 positive 或 negative。';
comment on column retrieval_v3.claim_rule_binding_factor_judgments.factor_summary is '原始 factor_refs 摘要；仅保存子表已解析选项的可读镜像。';
comment on column retrieval_v3.claim_rule_binding_factor_judgments.patch_note is '因子化判断说明；只写中文具体判断和关键材料，不写模板文本。';
comment on column retrieval_v3.claim_rule_binding_factor_judgments.review_status is '因子化判定复核状态；默认 accepted 表示已通过消费侧校验。';
comment on column retrieval_v3.claim_rule_binding_factor_judgments.judgment_payload is '因子化原始 patch、来源批次和消费上下文。';
comment on column retrieval_v3.claim_rule_binding_factor_judgments.created_at is '因子化判定首次写入时间。';
comment on column retrieval_v3.claim_rule_binding_factor_judgments.updated_at is '因子化判定最近更新时间。';

comment on column retrieval_v3.claim_rule_binding_factor_choices.id is '本表内部主键。';
comment on column retrieval_v3.claim_rule_binding_factor_choices.factor_choice_code is 'binding 因子选项稳定代码。';
comment on column retrieval_v3.claim_rule_binding_factor_choices.idem_key is 'binding 因子选项幂等键；同一判定和 factor 重复导入不得新增第二条。';
comment on column retrieval_v3.claim_rule_binding_factor_choices.factor_judgment_id is '所属 claim_rule_binding_factor_judgments.id。';
comment on column retrieval_v3.claim_rule_binding_factor_choices.binding_id is '被选择因子的 claim_rule_bindings.id，冗余保存便于算分 join。';
comment on column retrieval_v3.claim_rule_binding_factor_choices.factor_id is '规则因子快照 eval_rule_factors.id。';
comment on column retrieval_v3.claim_rule_binding_factor_choices.factor_option_id is '规则因子选项快照 eval_rule_factor_options.id。';
comment on column retrieval_v3.claim_rule_binding_factor_choices.factor_name is '因子英文稳定名，例如 authorization_intensity。';
comment on column retrieval_v3.claim_rule_binding_factor_choices.option_code is '因子选项代码，来自 eval_rule_factor_options.option_code。';
comment on column retrieval_v3.claim_rule_binding_factor_choices.option_label is '因子选项中文标签，来自 eval_rule_factor_options.label。';
comment on column retrieval_v3.claim_rule_binding_factor_choices.value_num is '因子选项数值，来自 eval_rule_factor_options.value_num 的导入快照。';
comment on column retrieval_v3.claim_rule_binding_factor_choices.choice_payload is '因子选项来源 patch 和解析上下文。';
comment on column retrieval_v3.claim_rule_binding_factor_choices.created_at is '因子选项首次写入时间。';
comment on column retrieval_v3.claim_rule_binding_factor_choices.updated_at is '因子选项最近更新时间。';

comment on column retrieval_v3.claim_rule_binding_material_scores.id is '本表内部主键。';
comment on column retrieval_v3.claim_rule_binding_material_scores.material_score_code is 'binding 材料分稳定代码。';
comment on column retrieval_v3.claim_rule_binding_material_scores.idem_key is 'binding 材料分幂等键；同一因子判定重复重算不得新增第二条。';
comment on column retrieval_v3.claim_rule_binding_material_scores.factor_judgment_id is '材料分来源 claim_rule_binding_factor_judgments.id。';
comment on column retrieval_v3.claim_rule_binding_material_scores.binding_id is '材料分来源 claim_rule_bindings.id。';
comment on column retrieval_v3.claim_rule_binding_material_scores.claim_id is '材料分来源 material_claims.id，冗余保存便于追溯。';
comment on column retrieval_v3.claim_rule_binding_material_scores.target_id is '材料分所属 retrieval_targets.id。';
comment on column retrieval_v3.claim_rule_binding_material_scores.source_pack_id is '材料分来源 source_packs.id，便于按包审计。';
comment on column retrieval_v3.claim_rule_binding_material_scores.object_id is '材料分承载对象 objects.id；按 binding.object_role 精确匹配 material_object_links。';
comment on column retrieval_v3.claim_rule_binding_material_scores.target_object_id is '材料分承载对象在当前 target 下的 target_objects.id；缺失时为空。';
comment on column retrieval_v3.claim_rule_binding_material_scores.item_code is '材料分所属 item_code，例如 I5B。';
comment on column retrieval_v3.claim_rule_binding_material_scores.rule_code is '材料分所属 rule_code，例如 delegation。';
comment on column retrieval_v3.claim_rule_binding_material_scores.formula_code is '材料分使用的公式代码，例如 evidence_cluster_signal_v3。';
comment on column retrieval_v3.claim_rule_binding_material_scores.side is '材料分入分方向；来自因子化判定的 positive 或 negative。';
comment on column retrieval_v3.claim_rule_binding_material_scores.raw_score is '单条材料原始分；由因子取值相乘得到，未做单条材料封顶。';
comment on column retrieval_v3.claim_rule_binding_material_scores.abs_score is '单条材料绝对分；对 raw_score 取绝对值并按规则封顶到 4。';
comment on column retrieval_v3.claim_rule_binding_material_scores.factor_values is '本材料参与计算的 factor_name 到数值映射。';
comment on column retrieval_v3.claim_rule_binding_material_scores.score_payload is '材料分计算上下文；保存 binding_code、对象名和因子选项追溯信息。';
comment on column retrieval_v3.claim_rule_binding_material_scores.created_at is '材料分首次写入时间。';
comment on column retrieval_v3.claim_rule_binding_material_scores.updated_at is '材料分最近更新时间。';

comment on column retrieval_v3.target_rule_score_clusters.id is '本表内部主键。';
comment on column retrieval_v3.target_rule_score_clusters.rule_score_code is '目标规则信号聚合稳定代码。';
comment on column retrieval_v3.target_rule_score_clusters.idem_key is '目标规则信号聚合幂等键；同一 target、rule 和公式重复重算不得新增第二条。';
comment on column retrieval_v3.target_rule_score_clusters.target_id is '聚合所属 retrieval_targets.id。';
comment on column retrieval_v3.target_rule_score_clusters.item_code is '聚合所属 item_code，例如 I5B。';
comment on column retrieval_v3.target_rule_score_clusters.rule_code is '聚合所属 rule_code，例如 delegation。';
comment on column retrieval_v3.target_rule_score_clusters.formula_code is '聚合使用的公式代码，例如 evidence_cluster_signal_v3。';
comment on column retrieval_v3.target_rule_score_clusters.positive_signal is '正向规则信号；由同对象折减后的正向对象分平方和开方得到。';
comment on column retrieval_v3.target_rule_score_clusters.negative_signal is '负向规则信号；由同对象折减后的负向对象分平方和开方得到。';
comment on column retrieval_v3.target_rule_score_clusters.scored_judgment_count is '参与入分的 binding 因子化判定数量。';
comment on column retrieval_v3.target_rule_score_clusters.supporting_judgment_count is '仅作上下文的 binding 因子化判定数量。';
comment on column retrieval_v3.target_rule_score_clusters.excluded_judgment_count is '被排除的 binding 因子化判定数量。';
comment on column retrieval_v3.target_rule_score_clusters.object_side_scores is '同对象折减后的对象侧分，按 positive 和 negative 分组保存。';
comment on column retrieval_v3.target_rule_score_clusters.calc_detail is '规则信号聚合明细；保存材料分、覆盖 judgment 和公式参数。';
comment on column retrieval_v3.target_rule_score_clusters.review_status is '规则信号聚合复核状态；默认 accepted 表示由已验收因子化结果生成。';
comment on column retrieval_v3.target_rule_score_clusters.created_at is '规则信号聚合首次写入时间。';
comment on column retrieval_v3.target_rule_score_clusters.updated_at is '规则信号聚合最近更新时间。';
