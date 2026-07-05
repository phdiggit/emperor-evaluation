create schema if not exists retrieval_v2;

create table if not exists retrieval_v2.eval_items (
    id bigint generated always as identity primary key,
    source_item_id bigint not null,
    item_code text not null,
    item_label text not null default '',
    source_row jsonb not null,
    source_fingerprint text not null,
    copied_at timestamptz not null default now(),
    constraint rv2_eval_items_source_item_uk unique (source_item_id),
    constraint rv2_eval_items_item_code_uk unique (item_code),
    constraint rv2_eval_items_item_code_not_blank check (btrim(item_code) <> '')
);

create table if not exists retrieval_v2.eval_rules (
    id bigint generated always as identity primary key,
    item_id bigint not null references retrieval_v2.eval_items(id) on delete restrict,
    source_rule_id bigint not null,
    item_code text not null,
    rule_code text not null,
    rule_label text not null default '',
    rule_status text not null default 'active',
    source_row jsonb not null,
    source_fingerprint text not null,
    copied_at timestamptz not null default now(),
    constraint rv2_eval_rules_source_rule_uk unique (source_rule_id),
    constraint rv2_eval_rules_rule_uk unique (item_id, rule_code),
    constraint rv2_eval_rules_item_code_not_blank check (btrim(item_code) <> ''),
    constraint rv2_eval_rules_rule_code_not_blank check (btrim(rule_code) <> '')
);

create table if not exists retrieval_v2.eval_rule_factors (
    id bigint generated always as identity primary key,
    item_id bigint not null references retrieval_v2.eval_items(id) on delete restrict,
    source_factor_id bigint not null,
    item_code text not null,
    rule_id bigint references retrieval_v2.eval_rules(id) on delete restrict,
    rule_code text not null default '',
    formula_code text not null,
    factor_name text not null,
    factor_scope text not null,
    value_source text not null default 'markdown',
    source_doc text not null default '',
    source_heading text not null default '',
    description text not null default '',
    factor_status text not null default 'active',
    source_row jsonb not null,
    source_fingerprint text not null,
    copied_at timestamptz not null default now(),
    constraint rv2_eval_rule_factors_source_uk unique (source_factor_id),
    constraint rv2_eval_rule_factors_code_uk unique (item_code, rule_code, formula_code, factor_name),
    constraint rv2_eval_rule_factors_item_code_not_blank check (btrim(item_code) <> ''),
    constraint rv2_eval_rule_factors_formula_code_not_blank check (btrim(formula_code) <> ''),
    constraint rv2_eval_rule_factors_factor_name_not_blank check (btrim(factor_name) <> ''),
    constraint rv2_eval_rule_factors_scope_known check (factor_scope in ('default', 'shared', 'rule', 'attribute_mapping', 'team', 'retired')),
    constraint rv2_eval_rule_factors_value_source_known check (value_source in ('markdown', 'manual', 'generated')),
    constraint rv2_eval_rule_factors_status_known check (factor_status in ('active', 'inactive', 'retired')),
    constraint rv2_eval_rule_factors_rule_code_consistency check (
        (rule_id is null and rule_code = '')
        or (rule_id is not null and btrim(rule_code) <> '')
    )
);

create table if not exists retrieval_v2.eval_rule_factor_options (
    id bigint generated always as identity primary key,
    factor_id bigint not null references retrieval_v2.eval_rule_factors(id) on delete cascade,
    source_option_id bigint not null,
    option_code text not null default '',
    label text not null,
    value_num numeric(12,4) not null,
    sort_no integer not null default 0,
    option_note text not null default '',
    source_doc text not null default '',
    source_line integer,
    option_status text not null default 'active',
    source_row jsonb not null,
    source_fingerprint text not null,
    copied_at timestamptz not null default now(),
    constraint rv2_eval_rule_factor_options_source_uk unique (source_option_id),
    constraint rv2_eval_rule_factor_options_factor_label_uk unique (factor_id, label),
    constraint rv2_eval_rule_factor_options_label_not_blank check (btrim(label) <> ''),
    constraint rv2_eval_rule_factor_options_status_known check (option_status in ('active', 'inactive', 'retired')),
    constraint rv2_eval_rule_factor_options_source_line_positive check (source_line is null or source_line > 0)
);

create table if not exists retrieval_v2.eval_rule_material_policies (
    id bigint generated always as identity primary key,
    item_id bigint references retrieval_v2.eval_items(id) on delete restrict,
    rule_id bigint references retrieval_v2.eval_rules(id) on delete restrict,
    source_policy_id bigint not null,
    item_code text not null,
    rule_code text not null,
    policy_code text not null,
    policy_version text not null default 'v1',
    selection_priority integer not null default 100,
    carrier_mode text not null default '',
    material_source text not null default '',
    allowed_scoring_roles text[] not null default array[]::text[],
    context_roles text[] not null default array[]::text[],
    disallowed_scored_obj_types text[] not null default array[]::text[],
    discouraged_scored_obj_types text[] not null default array[]::text[],
    candidate_obj_types text[] not null default array[]::text[],
    require_attrs text[] not null default array[]::text[],
    calc_detail_component_paths text[] not null default array[]::text[],
    single_scored_per_chain boolean not null default false,
    policy_payload jsonb not null default '{}'::jsonb,
    policy_status text not null default 'active',
    source_row jsonb not null,
    source_fingerprint text not null,
    copied_at timestamptz not null default now(),
    constraint rv2_material_policies_source_uk unique (source_policy_id),
    constraint rv2_material_policies_policy_uk unique (item_code, rule_code, policy_code, policy_version),
    constraint rv2_material_policies_item_code_not_blank check (btrim(item_code) <> ''),
    constraint rv2_material_policies_rule_code_not_blank check (btrim(rule_code) <> ''),
    constraint rv2_material_policies_policy_code_not_blank check (btrim(policy_code) <> ''),
    constraint rv2_material_policies_priority_positive check (selection_priority > 0)
);

create table if not exists retrieval_v2.fact_relation_predicate_options (
    id bigint generated always as identity primary key,
    item_id bigint references retrieval_v2.eval_items(id) on delete restrict,
    rule_id bigint references retrieval_v2.eval_rules(id) on delete restrict,
    source_option_id bigint not null,
    item_code text not null,
    rule_code text not null,
    scoring_role text not null,
    predicate text not null,
    relation_role text not null,
    subject_obj_type text not null,
    object_obj_type text not null default '',
    direction text not null default '',
    option_status text not null default 'active',
    source_row jsonb not null,
    source_fingerprint text not null,
    copied_at timestamptz not null default now(),
    constraint rv2_predicate_options_source_uk unique (source_option_id),
    constraint rv2_predicate_options_option_uk unique (
        item_code,
        rule_code,
        scoring_role,
        predicate,
        relation_role,
        subject_obj_type,
        object_obj_type
    ),
    constraint rv2_predicate_options_item_code_not_blank check (btrim(item_code) <> ''),
    constraint rv2_predicate_options_rule_code_not_blank check (btrim(rule_code) <> ''),
    constraint rv2_predicate_options_scoring_role_not_blank check (btrim(scoring_role) <> ''),
    constraint rv2_predicate_options_predicate_not_blank check (btrim(predicate) <> ''),
    constraint rv2_predicate_options_relation_role_not_blank check (btrim(relation_role) <> ''),
    constraint rv2_predicate_options_subject_type_not_blank check (btrim(subject_obj_type) <> '')
);

create table if not exists retrieval_v2.rule_contracts (
    id bigint generated always as identity primary key,
    contract_code text not null,
    item_code text not null,
    source_database_label text not null default '',
    source_snapshot_at timestamptz not null default now(),
    source_fingerprint text not null,
    contract_payload jsonb not null default '{}'::jsonb,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv2_rule_contracts_code_uk unique (contract_code),
    constraint rv2_rule_contracts_item_code_not_blank check (btrim(item_code) <> ''),
    constraint rv2_rule_contracts_status_ck check (status in ('draft', 'active', 'retired'))
);

create table if not exists retrieval_v2.rule_contract_rules (
    id bigint generated always as identity primary key,
    contract_id bigint not null references retrieval_v2.rule_contracts(id) on delete cascade,
    rule_id bigint not null references retrieval_v2.eval_rules(id) on delete restrict,
    rule_code text not null,
    rule_label text not null default '',
    rule_order integer not null default 100,
    is_core_for_retrieval boolean not null default true,
    material_policy_payload jsonb not null default '[]'::jsonb,
    predicate_policy_payload jsonb not null default '[]'::jsonb,
    requirement_payload jsonb not null default '{}'::jsonb,
    source_fingerprint text not null,
    created_at timestamptz not null default now(),
    constraint rv2_contract_rules_rule_uk unique (contract_id, rule_code),
    constraint rv2_contract_rules_rule_code_not_blank check (btrim(rule_code) <> ''),
    constraint rv2_contract_rules_rule_order_positive check (rule_order > 0)
);

create table if not exists retrieval_v2.retrieval_targets (
    id bigint generated always as identity primary key,
    target_code text not null,
    emperor_name text not null,
    item_code text not null,
    contract_id bigint not null references retrieval_v2.rule_contracts(id) on delete restrict,
    target_status text not null default 'active',
    target_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv2_targets_code_uk unique (target_code),
    constraint rv2_targets_contract_person_uk unique (contract_id, emperor_name),
    constraint rv2_targets_emperor_not_blank check (btrim(emperor_name) <> ''),
    constraint rv2_targets_item_code_not_blank check (btrim(item_code) <> ''),
    constraint rv2_targets_status_ck check (target_status in ('active', 'paused', 'completed', 'retired'))
);

create table if not exists retrieval_v2.target_aliases (
    id bigint generated always as identity primary key,
    target_id bigint not null references retrieval_v2.retrieval_targets(id) on delete cascade,
    alias text not null,
    alias_type text not null default 'name',
    norm_alias text not null,
    source text not null default 'manual',
    status text not null default 'active',
    alias_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    constraint rv2_target_aliases_alias_uk unique (target_id, alias_type, norm_alias),
    constraint rv2_target_aliases_alias_not_blank check (btrim(alias) <> ''),
    constraint rv2_target_aliases_norm_not_blank check (btrim(norm_alias) <> ''),
    constraint rv2_target_aliases_status_ck check (status in ('active', 'inactive', 'rejected'))
);

create table if not exists retrieval_v2.target_rule_requirements (
    id bigint generated always as identity primary key,
    target_id bigint not null references retrieval_v2.retrieval_targets(id) on delete cascade,
    contract_rule_id bigint not null references retrieval_v2.rule_contract_rules(id) on delete cascade,
    requirement_status text not null default 'active',
    priority integer not null default 100,
    min_usable_claims integer not null default 1,
    requirement_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv2_target_rule_requirements_uk unique (target_id, contract_rule_id),
    constraint rv2_target_rule_requirements_status_ck check (requirement_status in ('active', 'waived', 'satisfied', 'blocked', 'retired')),
    constraint rv2_target_rule_requirements_priority_positive check (priority > 0),
    constraint rv2_target_rule_requirements_min_claims_nonnegative check (min_usable_claims >= 0)
);

create table if not exists retrieval_v2.retrieval_intents (
    id bigint generated always as identity primary key,
    intent_code text not null,
    target_id bigint not null references retrieval_v2.retrieval_targets(id) on delete cascade,
    contract_rule_id bigint references retrieval_v2.rule_contract_rules(id) on delete restrict,
    target_rule_requirement_id bigint references retrieval_v2.target_rule_requirements(id) on delete set null,
    intent_kind text not null default 'initial_rule_coverage',
    status text not null default 'ready',
    priority integer not null default 100,
    intent_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv2_retrieval_intents_code_uk unique (intent_code),
    constraint rv2_retrieval_intents_kind_ck check (
        intent_kind in ('initial_rule_coverage', 'gap_refinement', 'alias_expansion', 'source_validation', 'manual_review')
    ),
    constraint rv2_retrieval_intents_status_ck check (status in ('draft', 'ready', 'running', 'succeeded', 'needs_refinement', 'blocked', 'cancelled')),
    constraint rv2_retrieval_intents_priority_positive check (priority > 0)
);

create table if not exists retrieval_v2.jobs (
    id bigint generated always as identity primary key,
    job_code text not null,
    idem_key text not null,
    kind text not null,
    status text not null default 'ready',
    priority integer not null default 100,
    next_run_at timestamptz not null default now(),
    attempt_count integer not null default 0,
    max_attempts integer not null default 3,
    locked_by text,
    locked_at timestamptz,
    lease_until timestamptz,
    payload jsonb not null default '{}'::jsonb,
    last_error text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv2_jobs_code_uk unique (job_code),
    constraint rv2_jobs_idem_uk unique (idem_key),
    constraint rv2_jobs_kind_ck check (
        kind in ('search', 'fetch', 'parse', 'claim_extract', 'coverage_check', 'codex_source_pack_refine', 'codex_material_review')
    ),
    constraint rv2_jobs_status_ck check (
        status in ('queued', 'ready', 'running', 'retry_wait', 'succeeded', 'failed', 'dead_lettered', 'blocked', 'cancelled')
    ),
    constraint rv2_jobs_attempts_ck check (attempt_count >= 0 and max_attempts > 0),
    constraint rv2_jobs_priority_positive check (priority > 0)
);

create table if not exists retrieval_v2.job_runs (
    id bigint generated always as identity primary key,
    run_code text not null,
    job_id bigint not null references retrieval_v2.jobs(id) on delete cascade,
    started_at timestamptz not null default now(),
    ended_at timestamptz,
    worker_id text not null default '',
    status text not null default 'running',
    input_fingerprint text not null default '',
    output_fingerprint text not null default '',
    error_type text not null default '',
    error_msg text not null default '',
    trace_id text not null default '',
    run_payload jsonb not null default '{}'::jsonb,
    constraint rv2_job_runs_code_uk unique (run_code),
    constraint rv2_job_runs_status_ck check (status in ('running', 'succeeded', 'failed', 'cancelled'))
);

create table if not exists retrieval_v2.search_tasks (
    id bigint generated always as identity primary key,
    task_code text not null,
    retrieval_intent_id bigint not null references retrieval_v2.retrieval_intents(id) on delete cascade,
    job_id bigint references retrieval_v2.jobs(id) on delete set null,
    search_mode text not null default 'wikisource',
    source_scope text not null default 'primary_source',
    query_text text not null,
    idem_key text not null,
    status text not null default 'ready',
    priority integer not null default 100,
    task_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv2_search_tasks_code_uk unique (task_code),
    constraint rv2_search_tasks_idem_uk unique (idem_key),
    constraint rv2_search_tasks_query_not_blank check (btrim(query_text) <> ''),
    constraint rv2_search_tasks_status_ck check (
        status in ('queued', 'ready', 'running', 'retry_wait', 'succeeded', 'failed', 'blocked', 'cancelled')
    ),
    constraint rv2_search_tasks_priority_positive check (priority > 0)
);

create table if not exists retrieval_v2.source_packs (
    id bigint generated always as identity primary key,
    pack_code text not null,
    target_id bigint not null references retrieval_v2.retrieval_targets(id) on delete restrict,
    contract_id bigint not null references retrieval_v2.rule_contracts(id) on delete restrict,
    pack_version text not null default 'v1',
    status text not null default 'draft',
    pack_root text not null default '',
    manifest_payload jsonb not null default '{}'::jsonb,
    coverage_status text not null default 'not_checked',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv2_source_packs_code_uk unique (pack_code),
    constraint rv2_source_packs_target_contract_version_uk unique (target_id, contract_id, pack_version),
    constraint rv2_source_packs_status_ck check (status in ('draft', 'ready', 'needs_refinement', 'accepted', 'blocked', 'retired')),
    constraint rv2_source_packs_coverage_ck check (coverage_status in ('not_checked', 'passed', 'needs_refinement', 'blocked', 'true_lack'))
);

create table if not exists retrieval_v2.source_pack_artifacts (
    id bigint generated always as identity primary key,
    source_pack_id bigint not null references retrieval_v2.source_packs(id) on delete cascade,
    artifact_kind text not null,
    artifact_path text not null,
    sha256 text not null default '',
    artifact_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    constraint rv2_source_pack_artifacts_uk unique (source_pack_id, artifact_kind, artifact_path),
    constraint rv2_source_pack_artifacts_kind_not_blank check (btrim(artifact_kind) <> ''),
    constraint rv2_source_pack_artifacts_path_not_blank check (btrim(artifact_path) <> '')
);

create table if not exists retrieval_v2.source_documents (
    id bigint generated always as identity primary key,
    source_pack_id bigint not null references retrieval_v2.source_packs(id) on delete cascade,
    document_code text not null,
    source_title text not null default '',
    title text not null,
    locator text not null default '',
    canon_url text not null default '',
    canon_url_hash text not null default '',
    source_kind text not null default 'wikisource_page',
    document_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv2_source_documents_code_uk unique (document_code),
    constraint rv2_source_documents_pack_doc_uk unique (source_pack_id, document_code),
    constraint rv2_source_documents_title_not_blank check (btrim(title) <> '')
);

create table if not exists retrieval_v2.source_passages (
    id bigint generated always as identity primary key,
    source_document_id bigint not null references retrieval_v2.source_documents(id) on delete cascade,
    passage_code text not null,
    locator text not null default '',
    raw_text text not null,
    norm_text text not null default '',
    quote_hash text not null default '',
    passage_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    constraint rv2_source_passages_code_uk unique (passage_code),
    constraint rv2_source_passages_doc_passage_uk unique (source_document_id, passage_code),
    constraint rv2_source_passages_raw_text_not_blank check (btrim(raw_text) <> '')
);

create table if not exists retrieval_v2.search_hits (
    id bigint generated always as identity primary key,
    search_task_id bigint not null references retrieval_v2.search_tasks(id) on delete cascade,
    source_document_id bigint references retrieval_v2.source_documents(id) on delete set null,
    hit_code text not null,
    url text not null default '',
    url_hash text not null,
    title text not null default '',
    snippet text not null default '',
    hit_position integer,
    status text not null default 'new',
    hit_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    constraint rv2_search_hits_code_uk unique (hit_code),
    constraint rv2_search_hits_task_url_uk unique (search_task_id, url_hash),
    constraint rv2_search_hits_status_ck check (status in ('new', 'accepted', 'rejected', 'fetched', 'blocked')),
    constraint rv2_search_hits_position_positive check (hit_position is null or hit_position > 0)
);

create table if not exists retrieval_v2.material_claims (
    id bigint generated always as identity primary key,
    source_pack_id bigint not null references retrieval_v2.source_packs(id) on delete cascade,
    source_passage_id bigint references retrieval_v2.source_passages(id) on delete set null,
    claim_code text not null,
    emperor_name text not null,
    object_name text not null,
    object_type text not null default 'person',
    claim_kind text not null default 'material_claim',
    claim_summary text not null,
    direction text not null,
    confidence numeric(5,4),
    review_status text not null default 'pending',
    claim_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv2_material_claims_code_uk unique (claim_code),
    constraint rv2_material_claims_pack_claim_uk unique (source_pack_id, claim_code),
    constraint rv2_material_claims_emperor_not_blank check (btrim(emperor_name) <> ''),
    constraint rv2_material_claims_object_not_blank check (btrim(object_name) <> ''),
    constraint rv2_material_claims_direction_ck check (direction in ('positive', 'negative', 'neutral', 'mixed')),
    constraint rv2_material_claims_confidence_ck check (confidence is null or (confidence >= 0 and confidence <= 1)),
    constraint rv2_material_claims_review_ck check (review_status in ('pending', 'accepted', 'rejected', 'needs_review', 'supporting_context'))
);

create table if not exists retrieval_v2.claim_rule_bindings (
    id bigint generated always as identity primary key,
    claim_id bigint not null references retrieval_v2.material_claims(id) on delete cascade,
    contract_rule_id bigint not null references retrieval_v2.rule_contract_rules(id) on delete restrict,
    rule_code text not null,
    predicate text not null default '',
    direction text not null,
    object_role text not null,
    usable_for_object_payload boolean not null default false,
    usable_for_scoring_cluster boolean not null default false,
    confidence numeric(5,4),
    review_status text not null default 'pending',
    binding_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv2_claim_rule_bindings_uk unique (claim_id, contract_rule_id, predicate, object_role),
    constraint rv2_claim_rule_bindings_rule_code_not_blank check (btrim(rule_code) <> ''),
    constraint rv2_claim_rule_bindings_object_role_not_blank check (btrim(object_role) <> ''),
    constraint rv2_claim_rule_bindings_direction_ck check (direction in ('positive', 'negative', 'neutral', 'mixed')),
    constraint rv2_claim_rule_bindings_confidence_ck check (confidence is null or (confidence >= 0 and confidence <= 1)),
    constraint rv2_claim_rule_bindings_review_ck check (review_status in ('pending', 'accepted', 'rejected', 'needs_review', 'supporting_context'))
);

create table if not exists retrieval_v2.coverage_reports (
    id bigint generated always as identity primary key,
    source_pack_id bigint not null references retrieval_v2.source_packs(id) on delete cascade,
    report_code text not null,
    report_status text not null default 'needs_refinement',
    ready_for_object_pool boolean not null default false,
    core_no_material_rules text[] not null default array[]::text[],
    core_zero_signal_rules text[] not null default array[]::text[],
    report_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    constraint rv2_coverage_reports_code_uk unique (report_code),
    constraint rv2_coverage_reports_pack_report_uk unique (source_pack_id, report_code),
    constraint rv2_coverage_reports_status_ck check (report_status in ('passed', 'needs_refinement', 'blocked', 'true_lack', 'manual_review'))
);

create table if not exists retrieval_v2.coverage_gap_events (
    id bigint generated always as identity primary key,
    event_code text not null,
    idem_key text not null,
    target_id bigint not null references retrieval_v2.retrieval_targets(id) on delete cascade,
    contract_rule_id bigint references retrieval_v2.rule_contract_rules(id) on delete set null,
    source_pack_id bigint references retrieval_v2.source_packs(id) on delete set null,
    coverage_report_id bigint references retrieval_v2.coverage_reports(id) on delete set null,
    gap_type text not null,
    queue text not null,
    diagnosis text not null default '',
    recommended_action text not null default '',
    status text not null default 'ready',
    priority integer not null default 100,
    event_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv2_coverage_gap_events_code_uk unique (event_code),
    constraint rv2_coverage_gap_events_idem_uk unique (idem_key),
    constraint rv2_coverage_gap_events_gap_type_ck check (
        gap_type in (
            'core_no_material',
            'core_zero_signal',
            'alias_unsearched',
            'alias_missing',
            'source_missing',
            'fetch_error',
            'source_fetch_failed',
            'needs_primary_source',
            'predicate_missing',
            'civil_undercoverage',
            'negative_undercoverage',
            'weak_alias_noise',
            'mixed_claim_not_split',
            'mixed_claim_needs_review',
            'negative_claim_not_scoring_without_gap',
            'material_classification_review',
            'object_payload_gap',
            'policy_block',
            'true_lack',
            'other'
        )
    ),
    constraint rv2_coverage_gap_events_queue_ck check (
        queue in (
            'source_pack_refinement',
            'material_classification_review',
            'policy_block_review',
            'object_payload_or_source_review',
            'true_lack_note',
            'codex_review'
        )
    ),
    constraint rv2_coverage_gap_events_status_ck check (
        status in ('queued', 'ready', 'running', 'retry_wait', 'resolved', 'blocked', 'deferred', 'cancelled')
    ),
    constraint rv2_coverage_gap_events_priority_positive check (priority > 0)
);

alter table retrieval_v2.coverage_gap_events
    drop constraint if exists rv2_coverage_gap_events_gap_type_ck;

alter table retrieval_v2.coverage_gap_events
    add constraint rv2_coverage_gap_events_gap_type_ck check (
        gap_type in (
            'core_no_material',
            'core_zero_signal',
            'alias_unsearched',
            'alias_missing',
            'source_missing',
            'fetch_error',
            'source_fetch_failed',
            'needs_primary_source',
            'predicate_missing',
            'civil_undercoverage',
            'negative_undercoverage',
            'weak_alias_noise',
            'mixed_claim_not_split',
            'mixed_claim_needs_review',
            'negative_claim_not_scoring_without_gap',
            'material_classification_review',
            'object_payload_gap',
            'policy_block',
            'true_lack',
            'other'
        )
    );

create index if not exists rv2_eval_rules_lookup_idx
on retrieval_v2.eval_rules(item_code, rule_code, rule_status);

create index if not exists rv2_eval_rule_factors_lookup_idx
on retrieval_v2.eval_rule_factors(item_code, rule_code, formula_code, factor_scope, factor_status);

create index if not exists rv2_eval_rule_factor_options_factor_idx
on retrieval_v2.eval_rule_factor_options(factor_id);

create index if not exists rv2_eval_rule_factor_options_value_idx
on retrieval_v2.eval_rule_factor_options(factor_id, value_num);

create index if not exists rv2_material_policies_lookup_idx
on retrieval_v2.eval_rule_material_policies(item_code, rule_code, selection_priority, policy_status);

create index if not exists rv2_predicate_options_lookup_idx
on retrieval_v2.fact_relation_predicate_options(item_code, rule_code, scoring_role, predicate, option_status);

create index if not exists rv2_contract_rules_lookup_idx
on retrieval_v2.rule_contract_rules(contract_id, rule_order, rule_code);

create index if not exists rv2_target_alias_norm_idx
on retrieval_v2.target_aliases(norm_alias) where status = 'active';

create index if not exists rv2_target_rule_requirements_ready_idx
on retrieval_v2.target_rule_requirements(priority, updated_at) where requirement_status in ('active', 'blocked');

create index if not exists rv2_retrieval_intents_ready_idx
on retrieval_v2.retrieval_intents(priority, created_at) where status in ('ready', 'needs_refinement');

create index if not exists rv2_jobs_ready_idx
on retrieval_v2.jobs(next_run_at, priority, created_at) where status in ('ready', 'retry_wait');

create index if not exists rv2_job_runs_job_idx
on retrieval_v2.job_runs(job_id, started_at desc);

create index if not exists rv2_search_tasks_intent_idx
on retrieval_v2.search_tasks(retrieval_intent_id, priority, created_at);

create index if not exists rv2_source_packs_target_idx
on retrieval_v2.source_packs(target_id, contract_id, status);

create index if not exists rv2_source_passages_document_idx
on retrieval_v2.source_passages(source_document_id);

create index if not exists rv2_material_claims_pack_idx
on retrieval_v2.material_claims(source_pack_id, review_status);

create index if not exists rv2_claim_rule_bindings_rule_idx
on retrieval_v2.claim_rule_bindings(contract_rule_id, review_status, usable_for_scoring_cluster);

create index if not exists rv2_coverage_reports_pack_idx
on retrieval_v2.coverage_reports(source_pack_id, report_status);

create index if not exists rv2_coverage_gap_events_ready_idx
on retrieval_v2.coverage_gap_events(priority, created_at) where status in ('ready', 'retry_wait');

comment on schema retrieval_v2 is '抓包链路 v2 控制面：按规则契约驱动 source pack、claim、rule binding 和缺口反馈；不承载正式对象池和计分结果。';
comment on table retrieval_v2.eval_items is '评价分项快照表：从源库复制 eval_items，用于构建抓包规则契约。';
comment on table retrieval_v2.eval_rules is '评价规则快照表：从源库复制 eval_rules，按 item_code/rule_code 固定抓包规则边界。';
comment on table retrieval_v2.eval_rule_factors is '计分因子目录快照表：复制源库结构化因子定义，供消费侧因子化候选和 patch 验收使用。';
comment on table retrieval_v2.eval_rule_factor_options is '计分因子取值快照表：复制源库结构化取值标签、数值和来源行，供消费侧只读使用。';
comment on table retrieval_v2.eval_rule_material_policies is '规则材料策略快照表：复制源库材料承载策略，供 claim 到 rule binding 和覆盖验收使用。';
comment on table retrieval_v2.fact_relation_predicate_options is '事实谓词词表快照表：复制源库谓词选项，供 claim、binding 和人工复核使用。';
comment on table retrieval_v2.rule_contracts is '规则契约表：source pack 绑定到某一版规则快照，不直接读取实时规则文档。';
comment on table retrieval_v2.rule_contract_rules is '规则契约明细表：展开某契约下每条 rule 及其材料策略、谓词策略和最低需求。';
comment on table retrieval_v2.retrieval_targets is '抓包目标表：某皇帝在某 item 和规则契约下的检索目标。';
comment on table retrieval_v2.target_aliases is '目标别名表：用于召回扩展和避免同一目标重复建档。';
comment on table retrieval_v2.target_rule_requirements is '目标规则需求表：某目标在某条规则下进入可消费 source pack 的最低要求。';
comment on table retrieval_v2.retrieval_intents is '检索意图表：面向 rule 的抓包意图，后续缺口事件应转成新的 refinement intent。';
comment on table retrieval_v2.jobs is '抓包任务表：dispatcher 和一次性 Codex CLI worker 的 canonical job 状态。';
comment on table retrieval_v2.job_runs is '抓包任务运行记录表：记录每次 job attempt 的输入输出摘要、状态和错误。';
comment on table retrieval_v2.search_tasks is '检索任务表：从 retrieval_intent 展开的具体检索 query。';
comment on table retrieval_v2.source_packs is '抓包包络表：绑定一个目标和一个规则契约的 source pack。';
comment on table retrieval_v2.source_pack_artifacts is '抓包文件产物表：记录 source pack 生成的文件路径、hash 和附加元数据。';
comment on table retrieval_v2.source_documents is '史源文档表：source pack 内收录的文档或页面。';
comment on table retrieval_v2.source_passages is '史源段落表：从文档中抽取的段落或摘录。';
comment on table retrieval_v2.search_hits is '检索命中表：构建 source pack 时产生的搜索命中。';
comment on table retrieval_v2.material_claims is '材料事实单元表：从段落中抽取的原子 claim，尚不是正式对象池记录。';
comment on table retrieval_v2.claim_rule_bindings is 'claim 规则绑定表：逐 rule 记录 claim 的 predicate、方向、承载角色和可消费状态。';
comment on table retrieval_v2.coverage_reports is '覆盖验收报告表：source pack 的下游消费 dry-run 结果。';
comment on table retrieval_v2.coverage_gap_events is '覆盖缺口事件表：下游验收向抓包 worker 回传的结构化补包信号。';

comment on column retrieval_v2.eval_items.id is '本表内部主键。';
comment on column retrieval_v2.eval_items.source_item_id is '源库 eval_items.id，用于追溯规则快照来源。';
comment on column retrieval_v2.eval_items.item_code is '评价分项稳定代码，例如 I5B。';
comment on column retrieval_v2.eval_items.item_label is '评价分项中文名称或人工标签。';
comment on column retrieval_v2.eval_items.source_row is '源库 eval_items 整行 JSON 快照。';
comment on column retrieval_v2.eval_items.source_fingerprint is 'source_row 的稳定 hash，用于判断规则快照是否漂移。';
comment on column retrieval_v2.eval_items.copied_at is '本行从源库复制或刷新到 retrieval_v2 的时间。';

comment on column retrieval_v2.eval_rules.id is '本表内部主键。';
comment on column retrieval_v2.eval_rules.item_id is '关联 retrieval_v2.eval_items.id。';
comment on column retrieval_v2.eval_rules.source_rule_id is '源库 eval_rules.id，用于追溯规则来源。';
comment on column retrieval_v2.eval_rules.item_code is '冗余评价分项代码，便于人工查询和导出。';
comment on column retrieval_v2.eval_rules.rule_code is '规则稳定代码，例如 talent_discovery 或 delegation。';
comment on column retrieval_v2.eval_rules.rule_label is '规则中文名称或人工标签。';
comment on column retrieval_v2.eval_rules.rule_status is '源规则生命周期状态快照。';
comment on column retrieval_v2.eval_rules.source_row is '源库 eval_rules 整行 JSON 快照。';
comment on column retrieval_v2.eval_rules.source_fingerprint is 'source_row 的稳定 hash，用于判断规则行是否漂移。';
comment on column retrieval_v2.eval_rules.copied_at is '本行从源库复制或刷新到 retrieval_v2 的时间。';

comment on column retrieval_v2.eval_rule_factors.id is '本表内部主键。';
comment on column retrieval_v2.eval_rule_factors.item_id is '关联 retrieval_v2.eval_items.id。';
comment on column retrieval_v2.eval_rule_factors.source_factor_id is '源库 eval_rule_factors.id，用于追溯规则表快照来源。';
comment on column retrieval_v2.eval_rule_factors.item_code is '评价分项代码冗余字段，例如 I5B。';
comment on column retrieval_v2.eval_rule_factors.rule_id is '关联 retrieval_v2.eval_rules.id；通用或共享因子可为空。';
comment on column retrieval_v2.eval_rule_factors.rule_code is '评价规则代码冗余字段；通用或共享因子为空字符串。';
comment on column retrieval_v2.eval_rule_factors.formula_code is '细则所属公式版本，例如 evidence_cluster_signal_v3。';
comment on column retrieval_v2.eval_rule_factors.factor_name is '因子稳定代码，例如 source_factor。';
comment on column retrieval_v2.eval_rule_factors.factor_scope is '因子范围，例如 default、shared、rule、attribute_mapping 或 team。';
comment on column retrieval_v2.eval_rule_factors.value_source is '结构化取值来源，例如 markdown、manual 或 generated。';
comment on column retrieval_v2.eval_rule_factors.source_doc is '因子定义来源文档路径。';
comment on column retrieval_v2.eval_rule_factors.source_heading is '因子定义来源文档小节。';
comment on column retrieval_v2.eval_rule_factors.description is '因子级中文说明；保存整组因子的适用口径，不复制到每个取值行。';
comment on column retrieval_v2.eval_rule_factors.factor_status is '源因子生命周期状态快照。';
comment on column retrieval_v2.eval_rule_factors.source_row is '源库 eval_rule_factors 整行 JSON 快照。';
comment on column retrieval_v2.eval_rule_factors.source_fingerprint is 'source_row 的稳定 hash，用于判断因子定义是否漂移。';
comment on column retrieval_v2.eval_rule_factors.copied_at is '本行从源库复制或刷新到 retrieval_v2 的时间。';

comment on column retrieval_v2.eval_rule_factor_options.id is '本表内部主键。';
comment on column retrieval_v2.eval_rule_factor_options.factor_id is '关联 retrieval_v2.eval_rule_factors.id。';
comment on column retrieval_v2.eval_rule_factor_options.source_option_id is '源库 eval_rule_factor_options.id，用于追溯规则取值快照来源。';
comment on column retrieval_v2.eval_rule_factor_options.option_code is '取值代码；源表为空时保留空字符串。';
comment on column retrieval_v2.eval_rule_factor_options.label is '可选因子标签；消费侧 patch 必须引用该标签。';
comment on column retrieval_v2.eval_rule_factor_options.value_num is '该标签对应的计算数值。';
comment on column retrieval_v2.eval_rule_factor_options.sort_no is '同一因子下取值展示排序。';
comment on column retrieval_v2.eval_rule_factor_options.option_note is '取值级中文说明；只写单个标签无法表达的特殊边界，默认留空。';
comment on column retrieval_v2.eval_rule_factor_options.source_doc is '取值来源文档路径。';
comment on column retrieval_v2.eval_rule_factor_options.source_line is '取值来源文档行号。';
comment on column retrieval_v2.eval_rule_factor_options.option_status is '源取值生命周期状态快照。';
comment on column retrieval_v2.eval_rule_factor_options.source_row is '源库 eval_rule_factor_options 整行 JSON 快照。';
comment on column retrieval_v2.eval_rule_factor_options.source_fingerprint is 'source_row 的稳定 hash，用于判断取值标签是否漂移。';
comment on column retrieval_v2.eval_rule_factor_options.copied_at is '本行从源库复制或刷新到 retrieval_v2 的时间。';

comment on column retrieval_v2.eval_rule_material_policies.id is '本表内部主键。';
comment on column retrieval_v2.eval_rule_material_policies.item_id is '关联 retrieval_v2.eval_items.id；可为空表示跨分项或源行未绑定。';
comment on column retrieval_v2.eval_rule_material_policies.rule_id is '关联 retrieval_v2.eval_rules.id；可为空表示分项级通用策略。';
comment on column retrieval_v2.eval_rule_material_policies.source_policy_id is '源库 eval_rule_material_policies.id。';
comment on column retrieval_v2.eval_rule_material_policies.item_code is '评价分项代码冗余字段。';
comment on column retrieval_v2.eval_rule_material_policies.rule_code is '评价规则代码冗余字段。';
comment on column retrieval_v2.eval_rule_material_policies.policy_code is '策略稳定代码，例如 person_material_policy。';
comment on column retrieval_v2.eval_rule_material_policies.policy_version is '策略版本；同一 rule 策略变化时用于区分历史。';
comment on column retrieval_v2.eval_rule_material_policies.selection_priority is '策略选择优先级，数字越小越优先。';
comment on column retrieval_v2.eval_rule_material_policies.carrier_mode is '计分或验收承载模式，例如 obj_src_material 或 team_core_members。';
comment on column retrieval_v2.eval_rule_material_policies.material_source is '候选材料来源表或来源层，例如 obj_srcs、emp_objs、calc_detail。';
comment on column retrieval_v2.eval_rule_material_policies.allowed_scoring_roles is '允许作为计分承载的 role 枚举快照。';
comment on column retrieval_v2.eval_rule_material_policies.context_roles is '允许作为上下文成员的 role 枚举快照。';
comment on column retrieval_v2.eval_rule_material_policies.disallowed_scored_obj_types is '禁止作为计分承载的对象类型枚举快照。';
comment on column retrieval_v2.eval_rule_material_policies.discouraged_scored_obj_types is '不建议作为计分承载但可进入 warning 的对象类型枚举快照。';
comment on column retrieval_v2.eval_rule_material_policies.candidate_obj_types is '覆盖审计候选对象类型过滤条件快照。';
comment on column retrieval_v2.eval_rule_material_policies.require_attrs is '候选对象必须具备的属性代码列表快照。';
comment on column retrieval_v2.eval_rule_material_policies.calc_detail_component_paths is '从 calc_detail 识别已覆盖对象的组件路径快照。';
comment on column retrieval_v2.eval_rule_material_policies.single_scored_per_chain is '是否要求同一因果链最多一个计分承载单元。';
comment on column retrieval_v2.eval_rule_material_policies.policy_payload is '脚本可读的结构化补充策略快照。';
comment on column retrieval_v2.eval_rule_material_policies.policy_status is '源策略生命周期状态快照。';
comment on column retrieval_v2.eval_rule_material_policies.source_row is '源库 eval_rule_material_policies 整行 JSON 快照。';
comment on column retrieval_v2.eval_rule_material_policies.source_fingerprint is 'source_row 的稳定 hash，用于判断策略行是否漂移。';
comment on column retrieval_v2.eval_rule_material_policies.copied_at is '本行从源库复制或刷新到 retrieval_v2 的时间。';

comment on column retrieval_v2.fact_relation_predicate_options.id is '本表内部主键。';
comment on column retrieval_v2.fact_relation_predicate_options.item_id is '关联 retrieval_v2.eval_items.id；可为空表示跨分项谓词。';
comment on column retrieval_v2.fact_relation_predicate_options.rule_id is '关联 retrieval_v2.eval_rules.id；可为空表示分项级通用谓词。';
comment on column retrieval_v2.fact_relation_predicate_options.source_option_id is '源库 fact_relation_predicate_options.id。';
comment on column retrieval_v2.fact_relation_predicate_options.item_code is '评价分项代码冗余字段。';
comment on column retrieval_v2.fact_relation_predicate_options.rule_code is '评价规则代码冗余字段。';
comment on column retrieval_v2.fact_relation_predicate_options.scoring_role is '规则承载角色，用于从 claim 或 rule evidence unit 映射谓词。';
comment on column retrieval_v2.fact_relation_predicate_options.predicate is '允许生成或绑定的事实关系谓词。';
comment on column retrieval_v2.fact_relation_predicate_options.relation_role is '谓词在规则判断中的关系角色，例如 scored_candidate 或 context。';
comment on column retrieval_v2.fact_relation_predicate_options.subject_obj_type is '允许作为关系主体的对象类型。';
comment on column retrieval_v2.fact_relation_predicate_options.object_obj_type is '允许作为关系宾语的对象类型；空字符串表示第一版不要求宾语。';
comment on column retrieval_v2.fact_relation_predicate_options.direction is '该谓词默认材料方向。';
comment on column retrieval_v2.fact_relation_predicate_options.option_status is '源谓词选项生命周期状态快照。';
comment on column retrieval_v2.fact_relation_predicate_options.source_row is '源库 fact_relation_predicate_options 整行 JSON 快照。';
comment on column retrieval_v2.fact_relation_predicate_options.source_fingerprint is 'source_row 的稳定 hash，用于判断谓词选项是否漂移。';
comment on column retrieval_v2.fact_relation_predicate_options.copied_at is '本行从源库复制或刷新到 retrieval_v2 的时间。';

comment on column retrieval_v2.rule_contracts.id is '本表内部主键。';
comment on column retrieval_v2.rule_contracts.contract_code is '规则契约稳定代码，source pack 和目标都绑定到该代码。';
comment on column retrieval_v2.rule_contracts.item_code is '该契约所属评价分项代码。';
comment on column retrieval_v2.rule_contracts.source_database_label is '源库标签，用于人工区分从哪个源库复制而来。';
comment on column retrieval_v2.rule_contracts.source_snapshot_at is '本契约最近一次从源库快照规则的时间。';
comment on column retrieval_v2.rule_contracts.source_fingerprint is 'items、rules、material policies 和 predicate options 的整体稳定 hash。';
comment on column retrieval_v2.rule_contracts.contract_payload is '契约级结构化元数据，例如源表计数和生成工具。';
comment on column retrieval_v2.rule_contracts.status is '契约生命周期状态：draft、active 或 retired。';
comment on column retrieval_v2.rule_contracts.created_at is '记录创建时间。';
comment on column retrieval_v2.rule_contracts.updated_at is '记录最近更新时间。';

comment on column retrieval_v2.rule_contract_rules.id is '本表内部主键。';
comment on column retrieval_v2.rule_contract_rules.contract_id is '关联 retrieval_v2.rule_contracts.id。';
comment on column retrieval_v2.rule_contract_rules.rule_id is '关联 retrieval_v2.eval_rules.id。';
comment on column retrieval_v2.rule_contract_rules.rule_code is '该契约明细对应的规则代码。';
comment on column retrieval_v2.rule_contract_rules.rule_label is '该契约明细对应的规则名称或标签。';
comment on column retrieval_v2.rule_contract_rules.rule_order is '规则在本契约内的排序值。';
comment on column retrieval_v2.rule_contract_rules.is_core_for_retrieval is '该 rule 是否为抓包 ready 的核心覆盖规则。';
comment on column retrieval_v2.rule_contract_rules.material_policy_payload is '该 rule 在本契约下的材料策略 JSON 数组快照。';
comment on column retrieval_v2.rule_contract_rules.predicate_policy_payload is '该 rule 在本契约下的谓词策略 JSON 数组快照。';
comment on column retrieval_v2.rule_contract_rules.requirement_payload is '该 rule 的最低可消费条件和验收补充配置。';
comment on column retrieval_v2.rule_contract_rules.source_fingerprint is '该 rule 契约明细的稳定 hash。';
comment on column retrieval_v2.rule_contract_rules.created_at is '记录创建时间。';

comment on column retrieval_v2.retrieval_targets.id is '本表内部主键。';
comment on column retrieval_v2.retrieval_targets.target_code is '抓包目标稳定代码。';
comment on column retrieval_v2.retrieval_targets.emperor_name is '目标皇帝名称。';
comment on column retrieval_v2.retrieval_targets.item_code is '目标所属评价分项代码。';
comment on column retrieval_v2.retrieval_targets.contract_id is '关联 retrieval_v2.rule_contracts.id，表示本目标按哪版规则抓包。';
comment on column retrieval_v2.retrieval_targets.target_status is '目标生命周期状态：active、paused、completed 或 retired。';
comment on column retrieval_v2.retrieval_targets.target_payload is '目标画像补充信息，例如种子来源、朝代、候选对象线索。';
comment on column retrieval_v2.retrieval_targets.created_at is '记录创建时间。';
comment on column retrieval_v2.retrieval_targets.updated_at is '记录最近更新时间。';

comment on column retrieval_v2.target_aliases.id is '本表内部主键。';
comment on column retrieval_v2.target_aliases.target_id is '关联 retrieval_v2.retrieval_targets.id。';
comment on column retrieval_v2.target_aliases.alias is '目标别名原文。';
comment on column retrieval_v2.target_aliases.alias_type is '别名类型，例如 name、temple_name、posthumous_name、reign_title。';
comment on column retrieval_v2.target_aliases.norm_alias is '规范化别名，用于去重和检索匹配。';
comment on column retrieval_v2.target_aliases.source is '别名来源，例如 seed、manual、profile 或 import。';
comment on column retrieval_v2.target_aliases.status is '别名生命周期状态：active、inactive 或 rejected。';
comment on column retrieval_v2.target_aliases.alias_payload is '别名补充元数据。';
comment on column retrieval_v2.target_aliases.created_at is '记录创建时间。';

comment on column retrieval_v2.target_rule_requirements.id is '本表内部主键。';
comment on column retrieval_v2.target_rule_requirements.target_id is '关联 retrieval_v2.retrieval_targets.id。';
comment on column retrieval_v2.target_rule_requirements.contract_rule_id is '关联 retrieval_v2.rule_contract_rules.id。';
comment on column retrieval_v2.target_rule_requirements.requirement_status is '需求状态：active、waived、satisfied、blocked 或 retired。';
comment on column retrieval_v2.target_rule_requirements.priority is '该目标 rule 需求的处理优先级，数字越小越靠前。';
comment on column retrieval_v2.target_rule_requirements.min_usable_claims is '该 rule 至少需要多少条可消费 claim；0 表示不作为 ready 硬要求。';
comment on column retrieval_v2.target_rule_requirements.requirement_payload is '目标级 rule 验收补充配置。';
comment on column retrieval_v2.target_rule_requirements.created_at is '记录创建时间。';
comment on column retrieval_v2.target_rule_requirements.updated_at is '记录最近更新时间。';

comment on column retrieval_v2.retrieval_intents.id is '本表内部主键。';
comment on column retrieval_v2.retrieval_intents.intent_code is '检索意图稳定代码。';
comment on column retrieval_v2.retrieval_intents.target_id is '关联 retrieval_v2.retrieval_targets.id。';
comment on column retrieval_v2.retrieval_intents.contract_rule_id is '关联 retrieval_v2.rule_contract_rules.id；可为空表示跨 rule 意图。';
comment on column retrieval_v2.retrieval_intents.target_rule_requirement_id is '关联 target_rule_requirements.id；缺口补抓时可为空。';
comment on column retrieval_v2.retrieval_intents.intent_kind is '检索意图类型，例如初始覆盖、缺口补强、别名扩展或材料复核。';
comment on column retrieval_v2.retrieval_intents.status is '意图状态：draft、ready、running、succeeded、needs_refinement、blocked 或 cancelled。';
comment on column retrieval_v2.retrieval_intents.priority is '检索意图处理优先级，数字越小越靠前。';
comment on column retrieval_v2.retrieval_intents.intent_payload is '检索意图结构化内容，包括皇帝、rule、查询方向和补强说明。';
comment on column retrieval_v2.retrieval_intents.created_at is '记录创建时间。';
comment on column retrieval_v2.retrieval_intents.updated_at is '记录最近更新时间。';

comment on column retrieval_v2.jobs.id is '本表内部主键。';
comment on column retrieval_v2.jobs.job_code is '抓包任务稳定代码。';
comment on column retrieval_v2.jobs.idem_key is '幂等键；重复提交同一工作只应命中同一 job。';
comment on column retrieval_v2.jobs.kind is '任务类型，例如 search、fetch、claim_extract 或 Codex 复核任务。';
comment on column retrieval_v2.jobs.status is '任务状态：queued、ready、running、retry_wait、succeeded、failed、dead_lettered、blocked 或 cancelled。';
comment on column retrieval_v2.jobs.priority is '任务调度优先级，数字越小越优先。';
comment on column retrieval_v2.jobs.next_run_at is '任务下次可被调度的时间。';
comment on column retrieval_v2.jobs.attempt_count is '任务已尝试次数。';
comment on column retrieval_v2.jobs.max_attempts is '任务最大尝试次数。';
comment on column retrieval_v2.jobs.locked_by is '当前持有任务 lease 的 worker 标识。';
comment on column retrieval_v2.jobs.locked_at is '当前任务被锁定的时间。';
comment on column retrieval_v2.jobs.lease_until is '当前任务锁过期时间。';
comment on column retrieval_v2.jobs.payload is '任务执行所需结构化参数；大文件只存引用路径或 code。';
comment on column retrieval_v2.jobs.last_error is '最近一次失败的错误摘要。';
comment on column retrieval_v2.jobs.created_at is '记录创建时间。';
comment on column retrieval_v2.jobs.updated_at is '记录最近更新时间。';

comment on column retrieval_v2.job_runs.id is '本表内部主键。';
comment on column retrieval_v2.job_runs.run_code is '任务运行尝试稳定代码。';
comment on column retrieval_v2.job_runs.job_id is '关联 retrieval_v2.jobs.id。';
comment on column retrieval_v2.job_runs.started_at is '本次运行开始时间。';
comment on column retrieval_v2.job_runs.ended_at is '本次运行结束时间；运行中为空。';
comment on column retrieval_v2.job_runs.worker_id is '执行本次运行的 worker 标识。';
comment on column retrieval_v2.job_runs.status is '本次运行状态：running、succeeded、failed 或 cancelled。';
comment on column retrieval_v2.job_runs.input_fingerprint is '本次运行输入摘要 hash。';
comment on column retrieval_v2.job_runs.output_fingerprint is '本次运行输出摘要 hash。';
comment on column retrieval_v2.job_runs.error_type is '失败类型，成功时为空。';
comment on column retrieval_v2.job_runs.error_msg is '失败信息摘要，成功时为空。';
comment on column retrieval_v2.job_runs.trace_id is '跨 worker 或日志系统追踪 id。';
comment on column retrieval_v2.job_runs.run_payload is '本次运行的结构化审计元数据。';

comment on column retrieval_v2.search_tasks.id is '本表内部主键。';
comment on column retrieval_v2.search_tasks.task_code is '检索任务稳定代码。';
comment on column retrieval_v2.search_tasks.retrieval_intent_id is '关联 retrieval_v2.retrieval_intents.id。';
comment on column retrieval_v2.search_tasks.job_id is '关联 retrieval_v2.jobs.id；可为空表示尚未派发执行任务。';
comment on column retrieval_v2.search_tasks.search_mode is '检索模式，例如 wikisource、direct_page 或 alias_expansion。';
comment on column retrieval_v2.search_tasks.source_scope is '史源范围，例如 primary_source 或 context_source。';
comment on column retrieval_v2.search_tasks.query_text is '实际提交给检索后端的查询文本。';
comment on column retrieval_v2.search_tasks.idem_key is '检索任务幂等键。';
comment on column retrieval_v2.search_tasks.status is '检索任务状态。';
comment on column retrieval_v2.search_tasks.priority is '检索任务优先级，数字越小越优先。';
comment on column retrieval_v2.search_tasks.task_payload is '检索任务结构化参数，例如别名、目标 rule、查询意图。';
comment on column retrieval_v2.search_tasks.created_at is '记录创建时间。';
comment on column retrieval_v2.search_tasks.updated_at is '记录最近更新时间。';

comment on column retrieval_v2.source_packs.id is '本表内部主键。';
comment on column retrieval_v2.source_packs.pack_code is 'source pack 稳定代码。';
comment on column retrieval_v2.source_packs.target_id is '关联 retrieval_v2.retrieval_targets.id。';
comment on column retrieval_v2.source_packs.contract_id is '关联 retrieval_v2.rule_contracts.id。';
comment on column retrieval_v2.source_packs.pack_version is '同一目标和契约下的 source pack 版本。';
comment on column retrieval_v2.source_packs.status is 'source pack 生命周期状态：draft、ready、needs_refinement、accepted、blocked 或 retired。';
comment on column retrieval_v2.source_packs.pack_root is 'source pack 文件目录或对象存储根路径。';
comment on column retrieval_v2.source_packs.manifest_payload is 'source pack manifest 的结构化摘要。';
comment on column retrieval_v2.source_packs.coverage_status is '覆盖验收状态：not_checked、passed、needs_refinement、blocked 或 true_lack。';
comment on column retrieval_v2.source_packs.created_at is '记录创建时间。';
comment on column retrieval_v2.source_packs.updated_at is '记录最近更新时间。';

comment on column retrieval_v2.source_pack_artifacts.id is '本表内部主键。';
comment on column retrieval_v2.source_pack_artifacts.source_pack_id is '关联 retrieval_v2.source_packs.id。';
comment on column retrieval_v2.source_pack_artifacts.artifact_kind is '文件产物类型，例如 manifest、documents、passages、coverage_report。';
comment on column retrieval_v2.source_pack_artifacts.artifact_path is '文件产物路径或对象存储 key。';
comment on column retrieval_v2.source_pack_artifacts.sha256 is '文件内容 sha256；暂不可得时为空字符串。';
comment on column retrieval_v2.source_pack_artifacts.artifact_payload is '文件产物补充元数据。';
comment on column retrieval_v2.source_pack_artifacts.created_at is '记录创建时间。';

comment on column retrieval_v2.source_documents.id is '本表内部主键。';
comment on column retrieval_v2.source_documents.source_pack_id is '关联 retrieval_v2.source_packs.id。';
comment on column retrieval_v2.source_documents.document_code is '史源文档稳定代码。';
comment on column retrieval_v2.source_documents.source_title is '史源书名或来源标题。';
comment on column retrieval_v2.source_documents.title is '页面、卷目或文档标题。';
comment on column retrieval_v2.source_documents.locator is '卷、篇、页、段等定位信息。';
comment on column retrieval_v2.source_documents.canon_url is '规范化 URL。';
comment on column retrieval_v2.source_documents.canon_url_hash is '规范化 URL 的 hash，用于去重。';
comment on column retrieval_v2.source_documents.source_kind is '史源类型，例如 wikisource_page、local_text、manual_source。';
comment on column retrieval_v2.source_documents.document_payload is '史源文档补充元数据。';
comment on column retrieval_v2.source_documents.created_at is '记录创建时间。';
comment on column retrieval_v2.source_documents.updated_at is '记录最近更新时间。';

comment on column retrieval_v2.source_passages.id is '本表内部主键。';
comment on column retrieval_v2.source_passages.source_document_id is '关联 retrieval_v2.source_documents.id。';
comment on column retrieval_v2.source_passages.passage_code is '史源段落稳定代码。';
comment on column retrieval_v2.source_passages.locator is '段落在文档中的定位信息。';
comment on column retrieval_v2.source_passages.raw_text is '段落原文。';
comment on column retrieval_v2.source_passages.norm_text is '规范化后的段落文本，用于检索和匹配。';
comment on column retrieval_v2.source_passages.quote_hash is '段落或摘录文本 hash，用于去重和引用稳定性检查。';
comment on column retrieval_v2.source_passages.passage_payload is '段落补充元数据。';
comment on column retrieval_v2.source_passages.created_at is '记录创建时间。';

comment on column retrieval_v2.search_hits.id is '本表内部主键。';
comment on column retrieval_v2.search_hits.search_task_id is '关联 retrieval_v2.search_tasks.id。';
comment on column retrieval_v2.search_hits.source_document_id is '命中已转成文档时关联 retrieval_v2.source_documents.id。';
comment on column retrieval_v2.search_hits.hit_code is '检索命中稳定代码。';
comment on column retrieval_v2.search_hits.url is '命中 URL。';
comment on column retrieval_v2.search_hits.url_hash is '命中 URL hash，用于同一 search_task 下去重。';
comment on column retrieval_v2.search_hits.title is '命中标题。';
comment on column retrieval_v2.search_hits.snippet is '检索后端返回的摘要。';
comment on column retrieval_v2.search_hits.hit_position is '命中排序位置；未知时为空。';
comment on column retrieval_v2.search_hits.status is '命中状态：new、accepted、rejected、fetched 或 blocked。';
comment on column retrieval_v2.search_hits.hit_payload is '命中补充元数据。';
comment on column retrieval_v2.search_hits.created_at is '记录创建时间。';

comment on column retrieval_v2.material_claims.id is '本表内部主键。';
comment on column retrieval_v2.material_claims.source_pack_id is '关联 retrieval_v2.source_packs.id。';
comment on column retrieval_v2.material_claims.source_passage_id is '关联 retrieval_v2.source_passages.id；无法定位到具体段落时可为空。';
comment on column retrieval_v2.material_claims.claim_code is '材料事实单元稳定代码。';
comment on column retrieval_v2.material_claims.emperor_name is '该 claim 关联的皇帝名称。';
comment on column retrieval_v2.material_claims.object_name is '该 claim 的主要对象名称。';
comment on column retrieval_v2.material_claims.object_type is '主要对象类型，例如 person、event、group、mechanism。';
comment on column retrieval_v2.material_claims.claim_kind is 'claim 类型，例如 material_claim、context_claim、counter_claim。';
comment on column retrieval_v2.material_claims.claim_summary is 'claim 的人工可读事实摘要。';
comment on column retrieval_v2.material_claims.direction is 'claim 的基础方向：positive、negative、neutral 或 mixed。';
comment on column retrieval_v2.material_claims.confidence is 'claim 抽取或复核置信度，范围 0 到 1。';
comment on column retrieval_v2.material_claims.review_status is 'claim 复核状态：pending、accepted、rejected、needs_review 或 supporting_context。';
comment on column retrieval_v2.material_claims.claim_payload is 'claim 的结构化补充信息，例如别名命中、原文片段、候选解释。';
comment on column retrieval_v2.material_claims.created_at is '记录创建时间。';
comment on column retrieval_v2.material_claims.updated_at is '记录最近更新时间。';

comment on column retrieval_v2.claim_rule_bindings.id is '本表内部主键。';
comment on column retrieval_v2.claim_rule_bindings.claim_id is '关联 retrieval_v2.material_claims.id。';
comment on column retrieval_v2.claim_rule_bindings.contract_rule_id is '关联 retrieval_v2.rule_contract_rules.id。';
comment on column retrieval_v2.claim_rule_bindings.rule_code is '该 binding 对应的规则代码冗余字段。';
comment on column retrieval_v2.claim_rule_bindings.predicate is 'claim 在本 rule 下命中的谓词；无正式谓词时为空字符串。';
comment on column retrieval_v2.claim_rule_bindings.direction is '该 claim 在本 rule 下的方向。';
comment on column retrieval_v2.claim_rule_bindings.object_role is '该 claim 对象在本 rule 下的承载角色。';
comment on column retrieval_v2.claim_rule_bindings.usable_for_object_payload is '该 binding 是否足以生成后续对象 payload 候选。';
comment on column retrieval_v2.claim_rule_bindings.usable_for_scoring_cluster is '该 binding 是否足以进入后续计分 cluster 候选。';
comment on column retrieval_v2.claim_rule_bindings.confidence is '该 binding 的规则适配置信度，范围 0 到 1。';
comment on column retrieval_v2.claim_rule_bindings.review_status is 'binding 复核状态：pending、accepted、rejected、needs_review 或 supporting_context。';
comment on column retrieval_v2.claim_rule_bindings.binding_payload is 'binding 的结构化补充信息，例如命中谓词、承载解释、排除理由。';
comment on column retrieval_v2.claim_rule_bindings.created_at is '记录创建时间。';
comment on column retrieval_v2.claim_rule_bindings.updated_at is '记录最近更新时间。';

comment on column retrieval_v2.coverage_reports.id is '本表内部主键。';
comment on column retrieval_v2.coverage_reports.source_pack_id is '关联 retrieval_v2.source_packs.id。';
comment on column retrieval_v2.coverage_reports.report_code is '覆盖验收报告稳定代码。';
comment on column retrieval_v2.coverage_reports.report_status is '验收报告状态：passed、needs_refinement、blocked、true_lack 或 manual_review。';
comment on column retrieval_v2.coverage_reports.ready_for_object_pool is '该 source pack 是否已达到后续对象池消费的最低条件。';
comment on column retrieval_v2.coverage_reports.core_no_material_rules is '核心 rule 中完全无可用材料的 rule_code 列表。';
comment on column retrieval_v2.coverage_reports.core_zero_signal_rules is '核心 rule 中有材料但 dry-run 信号为零的 rule_code 列表。';
comment on column retrieval_v2.coverage_reports.report_payload is '覆盖验收的完整结构化报告。';
comment on column retrieval_v2.coverage_reports.created_at is '记录创建时间。';

comment on column retrieval_v2.coverage_gap_events.id is '本表内部主键。';
comment on column retrieval_v2.coverage_gap_events.event_code is '覆盖缺口事件稳定代码。';
comment on column retrieval_v2.coverage_gap_events.idem_key is '缺口事件幂等键，用于避免同一缺口重复派工。';
comment on column retrieval_v2.coverage_gap_events.target_id is '关联 retrieval_v2.retrieval_targets.id。';
comment on column retrieval_v2.coverage_gap_events.contract_rule_id is '关联 retrieval_v2.rule_contract_rules.id；跨 rule 缺口可为空。';
comment on column retrieval_v2.coverage_gap_events.source_pack_id is '关联产生缺口的 source pack；尚未成包时可为空。';
comment on column retrieval_v2.coverage_gap_events.coverage_report_id is '关联产生缺口的 coverage report；人工创建缺口时可为空。';
comment on column retrieval_v2.coverage_gap_events.gap_type is '缺口类型，例如 core_no_material、predicate_missing、policy_block 或 true_lack。';
comment on column retrieval_v2.coverage_gap_events.queue is '缺口应进入的处理队列，例如 source_pack_refinement 或 codex_review。';
comment on column retrieval_v2.coverage_gap_events.diagnosis is '缺口诊断摘要。';
comment on column retrieval_v2.coverage_gap_events.recommended_action is '建议后续 worker 或 Codex 子进程执行的动作。';
comment on column retrieval_v2.coverage_gap_events.status is '缺口事件状态：queued、ready、running、retry_wait、resolved、blocked、deferred 或 cancelled。';
comment on column retrieval_v2.coverage_gap_events.priority is '缺口事件处理优先级，数字越小越优先。';
comment on column retrieval_v2.coverage_gap_events.event_payload is '缺口事件完整结构化上下文。';
comment on column retrieval_v2.coverage_gap_events.created_at is '记录创建时间。';
comment on column retrieval_v2.coverage_gap_events.updated_at is '记录最近更新时间。';
