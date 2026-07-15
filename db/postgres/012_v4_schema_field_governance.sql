BEGIN;

CREATE SCHEMA IF NOT EXISTS v4_governance;
REVOKE ALL ON SCHEMA v4_governance FROM PUBLIC;

CREATE TABLE IF NOT EXISTS v4_governance.schema_migration_state (
    migration_key TEXT PRIMARY KEY,
    migration_sha256 TEXT NOT NULL CHECK (migration_sha256 ~ '^[0-9a-f]{64}$'),
    inventory_sha256 TEXT NOT NULL CHECK (inventory_sha256 ~ '^[0-9a-f]{64}$'),
    report JSONB NOT NULL CHECK (jsonb_typeof(report) = 'object'),
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS v4_governance.field_contracts (
    schema_name TEXT NOT NULL,
    table_name TEXT NOT NULL,
    column_name TEXT NOT NULL,
    contract_kind TEXT NOT NULL,
    contract_value TEXT NOT NULL,
    legacy_policy TEXT NOT NULL CHECK (
        legacy_policy IN ('accepted_typed', 'quarantined_debt', 'canonical_only')
    ),
    description TEXT NOT NULL,
    PRIMARY KEY (schema_name, table_name, column_name)
);

CREATE TABLE IF NOT EXISTS v4_governance.field_quality_baselines (
    metric_key TEXT PRIMARY KEY,
    schema_name TEXT NOT NULL,
    table_name TEXT NOT NULL,
    column_name TEXT NOT NULL,
    metric_kind TEXT NOT NULL,
    baseline_count INTEGER NOT NULL CHECK (baseline_count >= 0),
    measured_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS v4_governance.identity_reference_aliases (
    source_ref TEXT PRIMARY KEY,
    reference_kind TEXT NOT NULL,
    resolution_status TEXT NOT NULL CHECK (
        resolution_status IN ('canonical', 'alias', 'candidate', 'non_person', 'unresolved')
    ),
    canonical_ref TEXT,
    canonical_name TEXT,
    basis_ref TEXT NOT NULL,
    source_priority INTEGER NOT NULL CHECK (source_priority > 0),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (resolution_status IN ('canonical', 'alias') AND canonical_ref IS NOT NULL)
        OR (resolution_status NOT IN ('canonical', 'alias') AND canonical_ref IS NULL)
    )
);

CREATE TABLE IF NOT EXISTS v4_governance.legacy_value_dispositions (
    issue_code TEXT NOT NULL,
    schema_name TEXT NOT NULL,
    table_name TEXT NOT NULL,
    column_name TEXT NOT NULL,
    legacy_value_sha256 TEXT NOT NULL CHECK (legacy_value_sha256 ~ '^[0-9a-f]{64}$'),
    legacy_value TEXT NOT NULL,
    occurrence_count INTEGER NOT NULL CHECK (occurrence_count > 0),
    disposition TEXT NOT NULL CHECK (
        disposition IN ('canonical_target', 'quarantined')
    ),
    canonical_value TEXT,
    basis TEXT NOT NULL,
    classification TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (issue_code, legacy_value_sha256),
    CHECK (
        (disposition = 'canonical_target' AND canonical_value IS NOT NULL)
        OR (disposition = 'quarantined' AND canonical_value IS NULL)
    )
);

ALTER TABLE v4_governance.legacy_value_dispositions
    ADD COLUMN IF NOT EXISTS classification TEXT;

INSERT INTO v4_governance.field_contracts (
    schema_name, table_name, column_name, contract_kind,
    contract_value, legacy_policy, description
) VALUES
    ('public', 'assertions', 'assertion_id', 'typed_identifier',
     'AST|ASTA|ASTD|K0', 'accepted_typed',
     '四类历史断言标识按来源显式接受，禁止未登记的第五种格式。'),
    ('public', 'assertions', 'assertion_semantic_key', 'typed_semantic_key',
     'ASK|CLMK', 'accepted_typed',
     'ASK 为 V4 语义键，CLMK 为带 lineage 的迁移 claim 键。'),
    ('public', 'episode_participants', 'person_ref', 'canonical_reference',
     'uppercase-hyphen-ref', 'quarantined_debt',
     '新增参与者必须使用大写连字符引用；中文名和小写旧引用只作为待处置历史债务。'),
    ('public', 'historical_episodes', 'evaluation_context', 'canonical_reference',
     'uppercase-hyphen-ref', 'quarantined_debt',
     '新增事件必须保存统治者规范引用，不再把中文显示名写入引用字段。'),
    ('public', 'source_documents', 'document_id', 'typed_identifier',
     'SCD|WSD', 'accepted_typed',
     'SCD 与 WSD 是两类显式文献载体标识。'),
    ('v4_person_profile', 'import_batches', 'import_batch_id', 'typed_identifier',
     'V4PP|PP|IMPORT|legacy-slug', 'accepted_typed',
     '历史批次格式被显式分类；新生产方应使用 V4PP 前缀。'),
    ('v4_person_profile', 'import_batches', 'source_freeze_ref', 'typed_reference',
     'sha256|semantic-freeze-tag', 'accepted_typed',
     '内容哈希与冻结标签均允许，但必须能明确分类。'),
    ('v4_person_profile', 'person_identity_registry', 'historical_context',
     'code_or_narrative', 'machine-code|Chinese narrative', 'accepted_typed',
     '机器上下文码与人物说明是两种显式内容类型，消费者不得把该字段当作单一枚举。'),
    ('v4_person_profile', 'person_profile_lineage', 'source_ref',
     'typed_lineage_reference', 'classified by lineage_kind', 'accepted_typed',
     '引用格式由 lineage_kind 解释，不得脱离类型按字符串前缀猜测。')
ON CONFLICT (schema_name, table_name, column_name) DO UPDATE SET
    contract_kind = EXCLUDED.contract_kind,
    contract_value = EXCLUDED.contract_value,
    legacy_policy = EXCLUDED.legacy_policy,
    description = EXCLUDED.description;

DO $governance$
BEGIN
    IF to_regclass('public.assertions') IS NOT NULL THEN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'public.assertions'::regclass
              AND conname = 'assertions_assertion_id_family_check'
        ) THEN
            ALTER TABLE public.assertions
                ADD CONSTRAINT assertions_assertion_id_family_check
                CHECK (assertion_id ~ '^(AST|ASTA|ASTD)-[A-Z0-9-]+$|^K0-[A-Z0-9-]+@SP-[A-Z0-9-]+$');
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'public.assertions'::regclass
              AND conname = 'assertions_semantic_key_family_check'
        ) THEN
            ALTER TABLE public.assertions
                ADD CONSTRAINT assertions_semantic_key_family_check
                CHECK (assertion_semantic_key ~ '^(ASK|CLMK)-[A-Z0-9-]+$');
        END IF;
    END IF;

    IF to_regclass('public.episode_participants') IS NOT NULL
       AND NOT EXISTS (
           SELECT 1 FROM pg_constraint
           WHERE conrelid = 'public.episode_participants'::regclass
             AND conname = 'episode_participants_canonical_person_ref_check'
       ) THEN
        ALTER TABLE public.episode_participants
            ADD CONSTRAINT episode_participants_canonical_person_ref_check
            CHECK (person_ref ~ '^[A-Z][A-Z0-9]*(-[A-Z0-9]+)+$') NOT VALID;
    END IF;

    IF to_regclass('public.episode_participants') IS NOT NULL
       AND NOT EXISTS (
           SELECT 1 FROM pg_constraint
           WHERE conrelid = 'public.episode_participants'::regclass
             AND conname = 'episode_participants_no_candidate_ref_check'
       ) THEN
        ALTER TABLE public.episode_participants
            ADD CONSTRAINT episode_participants_no_candidate_ref_check
            CHECK (person_ref !~ '-(NAME|GROUP)-CANDIDATE-') NOT VALID;
    END IF;

    IF to_regclass('public.historical_episodes') IS NOT NULL
       AND NOT EXISTS (
           SELECT 1 FROM pg_constraint
           WHERE conrelid = 'public.historical_episodes'::regclass
             AND conname = 'historical_episodes_canonical_evaluation_context_check'
       ) THEN
        ALTER TABLE public.historical_episodes
            ADD CONSTRAINT historical_episodes_canonical_evaluation_context_check
            CHECK (evaluation_context ~ '^[A-Z][A-Z0-9]*(-[A-Z0-9]+)+$') NOT VALID;
    END IF;

    IF to_regclass('public.source_documents') IS NOT NULL
       AND NOT EXISTS (
           SELECT 1 FROM pg_constraint
           WHERE conrelid = 'public.source_documents'::regclass
             AND conname = 'source_documents_document_id_family_check'
       ) THEN
        ALTER TABLE public.source_documents
            ADD CONSTRAINT source_documents_document_id_family_check
            CHECK (document_id ~ '^(SCD|WSD)-[A-Z0-9-]+$');
    END IF;

    IF to_regclass('v4_person_profile.person_identity_registry') IS NOT NULL
       AND NOT EXISTS (
           SELECT 1 FROM pg_constraint
           WHERE conrelid = 'v4_person_profile.person_identity_registry'::regclass
             AND conname = 'person_identity_registry_canonical_ref_check'
       ) THEN
        ALTER TABLE v4_person_profile.person_identity_registry
            ADD CONSTRAINT person_identity_registry_canonical_ref_check
            CHECK (person_ref ~ '^(PER|RULER)-[A-Z0-9-]+$');
    END IF;

    IF to_regclass('v4_person_profile.import_batches') IS NOT NULL THEN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'v4_person_profile.import_batches'::regclass
              AND conname = 'import_batches_id_family_check'
        ) THEN
            ALTER TABLE v4_person_profile.import_batches
                ADD CONSTRAINT import_batches_id_family_check
                CHECK (
                    import_batch_id ~ '^(V4PP|PP|IMPORT)-[A-Z0-9-]+$'
                    OR import_batch_id ~ '^v4-[a-z0-9-]+$'
                );
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'v4_person_profile.import_batches'::regclass
              AND conname = 'import_batches_source_freeze_ref_type_check'
        ) THEN
            ALTER TABLE v4_person_profile.import_batches
                ADD CONSTRAINT import_batches_source_freeze_ref_type_check
                CHECK (
                    source_freeze_ref ~ '^[0-9a-f]{64}$'
                    OR source_freeze_ref ~ '^[a-z][a-z0-9-]*$'
                );
        END IF;
    END IF;
END
$governance$;

DO $resolved_views$
BEGIN
    IF to_regclass('public.episode_participants') IS NOT NULL THEN
        EXECUTE $view$
            CREATE OR REPLACE VIEW v4_governance.resolved_episode_participants AS
            SELECT p.episode_id, p.semantic_version,
                   p.person_ref AS source_person_ref,
                   a.canonical_ref,
                   a.canonical_name,
                   a.reference_kind,
                   a.resolution_status,
                   p.role_code, p.role_status, p.created_at
            FROM public.episode_participants AS p
            LEFT JOIN v4_governance.identity_reference_aliases AS a
              ON a.source_ref = p.person_ref AND a.active
        $view$;
    END IF;
    IF to_regclass('public.historical_episodes') IS NOT NULL THEN
        EXECUTE $view$
            CREATE OR REPLACE VIEW v4_governance.resolved_historical_episodes AS
            SELECT e.episode_id, e.identity_anchor,
                   e.evaluation_context AS source_evaluation_context,
                   a.canonical_ref AS canonical_evaluation_context,
                   a.canonical_name AS evaluation_context_name,
                   a.resolution_status AS evaluation_context_resolution_status,
                   e.active_semantic_version, e.active_evidence_version,
                   e.active_semantic_fingerprint, e.created_at, e.updated_at
            FROM public.historical_episodes AS e
            LEFT JOIN v4_governance.identity_reference_aliases AS a
              ON a.source_ref = e.evaluation_context AND a.active
        $view$;
    END IF;
END
$resolved_views$;

CREATE OR REPLACE FUNCTION v4_governance.ensure_schema_comments()
RETURNS INTEGER
LANGUAGE plpgsql
AS $comments$
DECLARE
    relation_row RECORD;
    column_row RECORD;
    relation_description TEXT;
    column_description TEXT;
    write_count INTEGER := 0;
    table_descriptions JSONB := jsonb_build_object(
        'assertions', '正式证据断言及其来源定位。',
        'boundary_review_cache', '事件边界复核的幂等缓存。',
        'episode_assertion_dispositions', '断言在事件版本中的采用处置。',
        'episode_participants', '历史事件版本的参与者及角色。',
        'historical_episode_versions', '历史事件的不可变语义和证据版本。',
        'historical_episodes', '历史事件稳定身份及活动版本指针。',
        'review_artifacts', '边界与关系复核产生的只读工件。',
        'source_documents', '正式证据链使用的版本化文献。',
        'source_passages', '文献中的可定位证据片段。',
        'assertion_drafts', 'Claim Extractor 产生的断言草稿。',
        'job_runs', '异步作业的逐次运行记录。',
        'jobs', '可租约重试的异步作业。',
        'request_assertions', '抽取请求与断言草稿的关联。',
        'requests', '服务请求及其幂等状态。',
        'import_batches', '人物画像导入批次及来源冻结。',
        'person_identity_registry', 'V4 人物规范身份注册表。',
        'person_legacy_refs', '旧人物引用到 V4 身份的 lineage 映射。',
        'person_profile_catalog', '可直接读取的人物画像目录。',
        'person_profile_lineage', '人物画像版本的来源 lineage。',
        'person_profile_snapshots', '不可变人物画像快照。',
        'ruler_team_window_members', '统治者团队窗口成员快照。',
        'ruler_team_window_snapshots', '统治者团队窗口定义。',
        'talent_grade_calibrations', '多政策版本的人才档位校准记录。',
        'document_revisions', 'Source Cache 文献修订内容。',
        'passages', 'Source Cache 的证据片段缓存。',
        'request_documents', 'Source Cache 请求与文献修订关联。',
        'request_passages', 'Source Cache 请求与片段关联。',
        'schema_migration_state', '字段治理 migration 的幂等状态。',
        'field_contracts', '关键字段的格式、类型和历史兼容合同。'
        ,'field_quality_baselines', '字段一致性债务的不可反弹质量基线。'
        ,'legacy_value_dispositions', '历史非规范字段值的逐值处置和规范目标。'
        ,'identity_reference_aliases', '跨 Core、I5B 与人物画像命名空间的身份引用解析表。'
        ,'resolved_episode_participants', '保留原值并给出规范身份解析的事件参与者只读视图。'
        ,'resolved_historical_episodes', '保留原值并给出规范统治者引用的历史事件只读视图。'
    );
    column_descriptions JSONB := jsonb_build_object(
        'idempotency_key', '写入口幂等键。',
        'payload', '符合对应业务合同的结构化载荷。',
        'created_at', '记录创建时间。',
        'updated_at', '记录最后更新时间。',
        'status', '当前状态机状态。',
        'person_ref', '人物规范引用；不得保存显示名称。',
        'evaluation_context', '被评价统治者的规范引用。',
        'assertion_id', '断言稳定标识。',
        'assertion_semantic_key', '跨来源归并使用的断言语义键。',
        'document_id', '文献稳定标识。',
        'passage_id', '证据片段稳定标识。',
        'source_ref', '带类型解释的来源引用。',
        'lineage_ref', 'lineage 节点稳定引用。',
        'historical_context', '人物历史上下文码或中文说明；类型由字段合同解释。',
        'source_freeze_ref', '来源冻结引用；可以是内容哈希或语义冻结标签。',
        'reason', '处置或判断依据。',
        'follow_up', '后续处置说明。',
        'description', '面向人工阅读的中文说明。',
        'report', '本次治理执行的机器可读报告。',
        'migration_sha256', '治理 migration 内容哈希。',
        'inventory_sha256', '执行时数据库表字段清单哈希。',
        'applied_at', '治理 migration 最近应用时间。'
        ,'metric_key', '字段质量指标稳定键。'
        ,'metric_kind', '字段质量指标类型。'
        ,'baseline_count', '允许的历史债务上限；治理后只能下降。'
        ,'measured_at', '质量基线最近测量时间。'
        ,'issue_code', '一致性问题稳定代码。'
        ,'legacy_value_sha256', '历史字段值的 SHA-256 指纹。'
        ,'legacy_value', '仅用于 lineage 的历史原值。'
        ,'occurrence_count', '该历史值当前出现次数。'
        ,'disposition', '历史值处置结论。'
        ,'canonical_value', '唯一匹配时采用的规范引用。'
        ,'basis', '处置结论依据。'
        ,'active', '该历史债务当前是否仍存在。'
        ,'observed_at', '最近一次观测时间。'
        ,'source_ref', '需要解析的原始身份引用。'
        ,'reference_kind', '引用所属命名空间或实体类型。'
        ,'resolution_status', '规范、别名、候选、非人物或未解析状态。'
        ,'canonical_ref', '跨命名空间选定的规范人物引用。'
        ,'canonical_name', '规范人物名称。'
        ,'basis_ref', '身份解析所依据的合同或证据引用。'
        ,'source_priority', '身份解析来源的优先级。'
        ,'classification', '隔离值的细分类型。'
        ,'source_person_ref', '历史事件中保存的原参与者引用。'
        ,'source_evaluation_context', '历史事件中保存的原评价上下文。'
        ,'canonical_evaluation_context', '解析后的规范统治者引用。'
        ,'evaluation_context_name', '解析后的统治者名称。'
        ,'evaluation_context_resolution_status', '评价上下文的解析状态。'
    );
BEGIN
    FOR relation_row IN
        SELECT n.nspname AS schema_name, c.relname AS relation_name, c.oid
        FROM pg_class AS c
        JOIN pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname IN (
            'public', 'v4_source_cache', 'v4_claim_extractor',
            'v4_person_profile', 'v4_governance'
        )
          AND c.relkind IN ('r', 'p', 'v', 'm')
          AND c.relname NOT LIKE 'pg_%'
        ORDER BY n.nspname, c.relname
    LOOP
        relation_description := COALESCE(
            table_descriptions ->> relation_row.relation_name,
            format('V4 业务关系 %s.%s。', relation_row.schema_name, relation_row.relation_name)
        );
        IF obj_description(relation_row.oid, 'pg_class') IS DISTINCT FROM relation_description THEN
            EXECUTE format(
                'COMMENT ON %s %I.%I IS %L',
                CASE (SELECT relkind FROM pg_class WHERE oid = relation_row.oid)
                    WHEN 'v' THEN 'VIEW'
                    WHEN 'm' THEN 'MATERIALIZED VIEW'
                    ELSE 'TABLE'
                END,
                relation_row.schema_name, relation_row.relation_name, relation_description
            );
            write_count := write_count + 1;
        END IF;

        FOR column_row IN
            SELECT a.attname AS column_name, a.attnum
            FROM pg_attribute AS a
            WHERE a.attrelid = relation_row.oid
              AND a.attnum > 0
              AND NOT a.attisdropped
            ORDER BY a.attnum
        LOOP
            column_description := COALESCE(
                column_descriptions ->> column_row.column_name,
                format('%s中的 %s 字段。', relation_description, column_row.column_name)
            );
            IF col_description(relation_row.oid, column_row.attnum)
               IS DISTINCT FROM column_description THEN
                EXECUTE format(
                    'COMMENT ON COLUMN %I.%I.%I IS %L',
                    relation_row.schema_name, relation_row.relation_name,
                    column_row.column_name, column_description
                );
                write_count := write_count + 1;
            END IF;
        END LOOP;
    END LOOP;
    RETURN write_count;
END
$comments$;

SELECT v4_governance.ensure_schema_comments();

REVOKE ALL ON ALL TABLES IN SCHEMA v4_governance FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA v4_governance FROM PUBLIC;

COMMIT;
