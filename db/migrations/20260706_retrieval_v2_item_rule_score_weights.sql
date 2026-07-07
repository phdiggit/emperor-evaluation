create schema if not exists retrieval_v2;

-- 分项规则总分权重是所有评价项通用的规则快照，不绑定 I5B 专属表结构。

do $$
begin
    if not exists (
        select 1
          from pg_type t
          join pg_namespace n on n.oid = t.typnamespace
         where n.nspname = 'retrieval_v2'
           and t.typname = 'rv2_rule_weight_status'
    ) then
        execute 'create type retrieval_v2.rv2_rule_weight_status as enum (''active'', ''inactive'', ''retired'')';
    end if;
end;
$$;

create table if not exists retrieval_v2.item_rule_score_weights (
    id bigint generated always as identity primary key,
    item_id bigint references retrieval_v2.eval_items(id) on delete restrict,
    rule_id bigint references retrieval_v2.eval_rules(id) on delete restrict,
    item_code text not null,
    rule_code text not null,
    rule_label text not null default '',
    formula_code text not null,
    weight_version text not null default 'v1',
    weight_num numeric(12,6) not null,
    weight_order integer not null,
    weight_status retrieval_v2.rv2_rule_weight_status not null default 'active',
    weight_basis text not null default '',
    source_doc text not null default '',
    source_line integer,
    source_fingerprint text not null default '',
    weight_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv2_item_rule_score_weights_item_rule_formula_version_uk unique (item_code, rule_code, formula_code, weight_version),
    constraint rv2_item_rule_score_weights_item_not_blank check (btrim(item_code) <> ''),
    constraint rv2_item_rule_score_weights_rule_not_blank check (btrim(rule_code) <> ''),
    constraint rv2_item_rule_score_weights_formula_not_blank check (btrim(formula_code) <> ''),
    constraint rv2_item_rule_score_weights_version_not_blank check (btrim(weight_version) <> ''),
    constraint rv2_item_rule_score_weights_nonnegative check (weight_num >= 0),
    constraint rv2_item_rule_score_weights_order_positive check (weight_order > 0),
    constraint rv2_item_rule_score_weights_source_line_positive check (source_line is null or source_line > 0)
);

create index if not exists rv2_item_rule_score_weights_active_order_idx
on retrieval_v2.item_rule_score_weights(item_code, formula_code, weight_status, weight_order);

create index if not exists rv2_item_rule_score_weights_rule_idx
on retrieval_v2.item_rule_score_weights(rule_id)
where rule_id is not null;

with i5b_weights (
    item_code,
    rule_code,
    rule_label,
    formula_code,
    weight_version,
    weight_num,
    weight_order,
    weight_basis,
    source_doc,
    source_line
) as (
    values
        ('I5B', 'talent_discovery', '发现人才', 'evidence_cluster_signal_v3', 'v1', 0.190000::numeric(12,6), 10, 'I5B 总分权重：发现人才衡量统治者识别、引入和拔擢人才的能力。', 'docs/分项规则/第五项统治者政治素质/B用人与授权.md', 419),
        ('I5B', 'appointment_delegation', '任用授权', 'evidence_cluster_signal_v3', 'v1', 0.360000::numeric(12,6), 20, 'I5B 总分权重：任用授权衡量统治者是否把合适的人放到合适的位置、任务或权责链上，并产生合理后果。', 'docs/分项规则/第五项统治者政治素质/B用人与授权.md', 420),
        ('I5B', 'team_building', '建立团队', 'evidence_cluster_signal_v3', 'v1', 0.210000::numeric(12,6), 30, 'I5B 总分权重：建立团队衡量核心团队的人才密度、结构稳定性和负向污染程度。', 'docs/分项规则/第五项统治者政治素质/B用人与授权.md', 421),
        ('I5B', 'tolerate_talent', '容人保全', 'evidence_cluster_signal_v3', 'v1', 0.180000::numeric(12,6), 40, 'I5B 总分权重：容人保全衡量统治者对功臣、直臣和有缺陷人才的保护或损害。', 'docs/分项规则/第五项统治者政治素质/B用人与授权.md', 422),
        ('I5B', 'anti_nepotism', '避免任人唯亲', 'evidence_cluster_signal_v3', 'v1', 0.060000::numeric(12,6), 50, 'I5B 总分权重：避免任人唯亲衡量统治者抑制亲族、近幸、朋党和私门干政的能力。', 'docs/分项规则/第五项统治者政治素质/B用人与授权.md', 423)
),
resolved as (
    select
        ei.id as item_id,
        er.id as rule_id,
        w.*,
        md5(
            w.item_code || '|' ||
            w.rule_code || '|' ||
            w.formula_code || '|' ||
            w.weight_version || '|' ||
            w.weight_num::text || '|' ||
            w.source_doc || ':' ||
            w.source_line::text
        ) as source_fingerprint
    from i5b_weights w
    left join retrieval_v2.eval_items ei on ei.item_code = w.item_code
    left join retrieval_v2.eval_rules er on er.item_id = ei.id and er.rule_code = w.rule_code
)
insert into retrieval_v2.item_rule_score_weights (
    item_id,
    rule_id,
    item_code,
    rule_code,
    rule_label,
    formula_code,
    weight_version,
    weight_num,
    weight_order,
    weight_status,
    weight_basis,
    source_doc,
    source_line,
    source_fingerprint,
    weight_payload
)
select
    item_id,
    rule_id,
    item_code,
    rule_code,
    rule_label,
    formula_code,
    weight_version,
    weight_num,
    weight_order,
    'active'::retrieval_v2.rv2_rule_weight_status,
    weight_basis,
    source_doc,
    source_line,
    source_fingerprint,
    jsonb_build_object(
        'source', 'docs_score_formula',
        'scope', 'item_rule_total_weight',
        'applies_to_all_items_schema', true
    )
from resolved
on conflict on constraint rv2_item_rule_score_weights_item_rule_formula_version_uk do update
set
    item_id = coalesce(excluded.item_id, retrieval_v2.item_rule_score_weights.item_id),
    rule_id = coalesce(excluded.rule_id, retrieval_v2.item_rule_score_weights.rule_id),
    rule_label = excluded.rule_label,
    weight_num = excluded.weight_num,
    weight_order = excluded.weight_order,
    weight_status = excluded.weight_status,
    weight_basis = excluded.weight_basis,
    source_doc = excluded.source_doc,
    source_line = excluded.source_line,
    source_fingerprint = excluded.source_fingerprint,
    weight_payload = retrieval_v2.item_rule_score_weights.weight_payload || excluded.weight_payload,
    updated_at = now();

with labels(rule_code, rule_label) as (
    values
        ('talent_discovery', '发现人才'),
        ('appointment_delegation', '任用授权'),
        ('team_building', '建立团队'),
        ('tolerate_talent', '容人保全'),
        ('anti_nepotism', '避免任人唯亲')
)
update retrieval_v2.rule_contract_rules rcr
set rule_label = labels.rule_label
from retrieval_v2.rule_contracts rc,
     labels
where rcr.contract_id = rc.id
  and rc.item_code = 'I5B'
  and rcr.rule_code = labels.rule_code
  and rcr.rule_label is distinct from labels.rule_label;

comment on type retrieval_v2.rv2_rule_weight_status is '分项规则权重生命周期枚举：active 表示当前总分公式使用，inactive 表示暂不使用，retired 表示历史留档。';

comment on table retrieval_v2.item_rule_score_weights is '分项规则总分权重表：所有评价项通用，记录 item 下 rule 对总分公式的权重、排序、版本和文档来源。';
comment on column retrieval_v2.item_rule_score_weights.id is '本表内部主键。';
comment on column retrieval_v2.item_rule_score_weights.item_id is '关联 retrieval_v2.eval_items.id；规则快照未复制时可为空，但 item_code 仍必须保留。';
comment on column retrieval_v2.item_rule_score_weights.rule_id is '关联 retrieval_v2.eval_rules.id；规则快照未复制时可为空，但 rule_code 仍必须保留。';
comment on column retrieval_v2.item_rule_score_weights.item_code is '评价分项稳定代码，例如 I5B；同一张表可承载所有评价项。';
comment on column retrieval_v2.item_rule_score_weights.rule_code is '评价规则稳定代码，例如 appointment_delegation 或 team_building。';
comment on column retrieval_v2.item_rule_score_weights.rule_label is '规则中文名称，用于诊断、导出和人工核对。';
comment on column retrieval_v2.item_rule_score_weights.formula_code is '总分聚合公式版本，例如 evidence_cluster_signal_v3。';
comment on column retrieval_v2.item_rule_score_weights.weight_version is '权重版本；同一 item、rule、formula 的权重调整必须升版本或覆盖当前快照。';
comment on column retrieval_v2.item_rule_score_weights.weight_num is '该 rule 在所属 item 总分公式中的数值权重。';
comment on column retrieval_v2.item_rule_score_weights.weight_order is '该 rule 在总分公式和诊断展示中的排序，独立于抓包契约排序。';
comment on column retrieval_v2.item_rule_score_weights.weight_status is '权重生命周期状态；只有 active 权重进入当前总分聚合。';
comment on column retrieval_v2.item_rule_score_weights.weight_basis is '权重依据说明；只写中文具体口径和该 rule 承担的评分含义。';
comment on column retrieval_v2.item_rule_score_weights.source_doc is '权重来源文档路径；运行时不得读取文档，只用于审计追溯。';
comment on column retrieval_v2.item_rule_score_weights.source_line is '权重来源文档行号；运行时不得读取文档，只用于审计追溯。';
comment on column retrieval_v2.item_rule_score_weights.source_fingerprint is '权重来源和数值的稳定 hash，用于发现规则表与文档公式漂移。';
comment on column retrieval_v2.item_rule_score_weights.weight_payload is '脚本可读的结构化补充信息，例如来源类型和适用范围。';
comment on column retrieval_v2.item_rule_score_weights.created_at is '记录创建时间。';
comment on column retrieval_v2.item_rule_score_weights.updated_at is '记录最近更新时间。';
