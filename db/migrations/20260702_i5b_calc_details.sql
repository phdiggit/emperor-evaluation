create table if not exists public.evd_cluster_calc_details (
    cluster_id bigint primary key references public.evd_clusters(id) on delete cascade,
    item_code text not null,
    formula_code text not null,
    calc_note text not null default '',
    material_ids bigint[] not null default '{}',
    covered_material_ids bigint[] not null default '{}',
    scored_material_ids bigint[] not null default '{}',
    supporting_material_ids bigint[] not null default '{}',
    calc_detail jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists evd_cluster_calc_details_formula_idx
    on public.evd_cluster_calc_details (formula_code);

create index if not exists evd_cluster_calc_details_material_ids_gin
    on public.evd_cluster_calc_details using gin (material_ids);

create index if not exists evd_cluster_calc_details_calc_detail_gin
    on public.evd_cluster_calc_details using gin (calc_detail jsonb_path_ops);

create table if not exists public.emp_item_result_calc_details (
    result_id bigint primary key references public.emp_item_results(id) on delete cascade,
    item_code text not null,
    cluster_formula text not null,
    formula_code text not null,
    base_core numeric,
    score_rate numeric,
    calc_detail jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists emp_item_result_calc_details_formula_idx
    on public.emp_item_result_calc_details (formula_code, cluster_formula);

create index if not exists emp_item_result_calc_details_calc_detail_gin
    on public.emp_item_result_calc_details using gin (calc_detail jsonb_path_ops);

comment on table public.evd_cluster_calc_details is 'I5B 证据簇计算明细当前表；替代 JSONL 计算日志承载复算、筛选和审查所需的 calc_detail。';
comment on column public.evd_cluster_calc_details.cluster_id is 'evd_clusters.id，一条证据簇只保留当前计算明细。';
comment on column public.evd_cluster_calc_details.material_ids is '本次证据簇覆盖的 obj_srcs id。';
comment on column public.evd_cluster_calc_details.covered_material_ids is '完整覆盖材料 id，通常等同 material_ids。';
comment on column public.evd_cluster_calc_details.scored_material_ids is '实际进入公式计分的材料 id。';
comment on column public.evd_cluster_calc_details.supporting_material_ids is '只作为属性、身份或补源上下文的材料 id。';
comment on column public.evd_cluster_calc_details.calc_detail is '材料因子、factor_refs、对象侧聚合、覆盖关系和证据簇内部计算过程。';

comment on table public.emp_item_result_calc_details is 'I5B 定分计算明细当前表；替代 JSONL 结果日志承载 rules、响应函数参数和最终定分过程。';
comment on column public.emp_item_result_calc_details.result_id is 'emp_item_results.id，一条定分结果只保留当前计算明细。';
comment on column public.emp_item_result_calc_details.cluster_formula is '本次定分读取的 evd_clusters.formula_code。';
comment on column public.emp_item_result_calc_details.calc_detail is '规则输入、响应函数参数、base_core、score_rate、score、tier 等定分过程。';
