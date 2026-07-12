create table if not exists public.eval_rule_factors (
    id bigint generated always as identity primary key,
    item_id bigint not null references public.eval_items(id) on delete restrict,
    item_code text not null,
    rule_id bigint references public.eval_rules(id) on delete restrict,
    rule_code text not null default '',
    formula_code text not null,
    factor_name text not null,
    factor_scope text not null,
    value_source text not null default 'markdown',
    source_doc text not null default '',
    source_heading text not null default '',
    description text not null default '',
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint eval_rule_factors_item_code_not_blank check (btrim(item_code) <> ''),
    constraint eval_rule_factors_formula_code_not_blank check (btrim(formula_code) <> ''),
    constraint eval_rule_factors_factor_name_not_blank check (btrim(factor_name) <> ''),
    constraint eval_rule_factors_scope_known check (factor_scope in ('default', 'shared', 'rule', 'attribute_mapping', 'team', 'retired')),
    constraint eval_rule_factors_value_source_known check (value_source in ('markdown', 'manual', 'generated')),
    constraint eval_rule_factors_status_known check (status in ('active', 'inactive', 'retired')),
    constraint eval_rule_factors_rule_code_consistency check (
        (rule_id is null and rule_code = '')
        or (rule_id is not null and btrim(rule_code) <> '')
    )
);

create unique index if not exists eval_rule_factors_code_uk
on public.eval_rule_factors(item_code, rule_code, formula_code, factor_name);

create index if not exists eval_rule_factors_item_idx
on public.eval_rule_factors(item_id);

create index if not exists eval_rule_factors_rule_idx
on public.eval_rule_factors(rule_id);

create index if not exists eval_rule_factors_lookup_idx
on public.eval_rule_factors(item_code, rule_code, factor_scope, status);

create table if not exists public.eval_rule_factor_options (
    id bigint generated always as identity primary key,
    factor_id bigint not null references public.eval_rule_factors(id) on delete cascade,
    option_code text not null default '',
    label text not null,
    value_num numeric(12,4) not null,
    sort_no integer not null default 0,
    note text not null default '',
    source_doc text not null default '',
    source_line integer,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint eval_rule_factor_options_label_not_blank check (btrim(label) <> ''),
    constraint eval_rule_factor_options_status_known check (status in ('active', 'inactive', 'retired')),
    constraint eval_rule_factor_options_source_line_positive check (source_line is null or source_line > 0)
);

create unique index if not exists eval_rule_factor_options_factor_label_uk
on public.eval_rule_factor_options(factor_id, label);

create index if not exists eval_rule_factor_options_factor_idx
on public.eval_rule_factor_options(factor_id);

create index if not exists eval_rule_factor_options_value_idx
on public.eval_rule_factor_options(factor_id, value_num);

drop view if exists public.v_eval_rule_factor_options_by_id;
drop view if exists public.v_eval_rule_factors_by_id;

create view public.v_eval_rule_factors_by_id as
select
    erf.id,
    erf.item_id,
    erf.item_code,
    erf.rule_id,
    erf.rule_code,
    erf.formula_code,
    erf.factor_name,
    erf.factor_scope,
    erf.value_source,
    erf.source_doc,
    erf.source_heading,
    erf.description,
    erf.status,
    erf.created_at,
    erf.updated_at
from public.eval_rule_factors erf
order by erf.id;

create view public.v_eval_rule_factor_options_by_id as
select
    erfo.id,
    erf.item_code,
    erf.rule_code,
    erf.formula_code,
    erf.factor_name,
    erf.factor_scope,
    erfo.option_code,
    erfo.label,
    erfo.value_num,
    erfo.sort_no,
    erfo.note,
    erfo.source_doc,
    erfo.source_line,
    erfo.status,
    erfo.created_at,
    erfo.updated_at
from public.eval_rule_factor_options erfo
join public.eval_rule_factors erf on erf.id = erfo.factor_id
order by erf.item_code, erf.rule_code, erf.factor_name, erfo.sort_no, erfo.id;

comment on table public.eval_rule_factors is '计分细则因子目录；按 item/rule/formula/factor_name 保存从规则文档同步来的因子定义。';
comment on table public.eval_rule_factor_options is '计分细则因子取值表；保存每个因子可选标签、数值和文档来源行。';
comment on column public.eval_rule_factors.item_id is '评价子项 id，引用 eval_items.id。';
comment on column public.eval_rule_factors.item_code is '评价子项代码冗余列，用于文档同步和人工核对；例如 I5B。';
comment on column public.eval_rule_factors.rule_id is '评价规则 id，引用 eval_rules.id；通用或共享因子可为空。';
comment on column public.eval_rule_factors.rule_code is '评价规则代码冗余列；通用或共享因子为空字符串。';
comment on column public.eval_rule_factors.formula_code is '细则所属公式版本，例如 evidence_cluster_signal_v3。';
comment on column public.eval_rule_factors.factor_scope is '因子范围：default/shared/rule/attribute_mapping/team/retired。';
comment on column public.eval_rule_factors.value_source is '结构化细则来源：markdown/manual/generated。';
comment on column public.eval_rule_factors.description is '因子级中文说明；保存整组因子的适用口径，不复制到每个取值行。';
comment on column public.eval_rule_factor_options.label is '文档中的取值标签或枚举口径。';
comment on column public.eval_rule_factor_options.value_num is '该标签对应的计算数值。';
comment on column public.eval_rule_factor_options.note is '取值级备注；默认留空，只写单个取值标签无法表达的特殊边界，不存因子级整段说明。';
comment on column public.eval_rule_factor_options.source_line is '同步时记录的 Markdown 源行号，便于审计文档与表是否一致。';
comment on view public.v_eval_rule_factors_by_id is '计分因子目录人工查看视图，按主键排序。';
comment on view public.v_eval_rule_factor_options_by_id is '计分因子取值人工查看视图，带 item/rule/factor 冗余信息。';
