create table if not exists public.emp_item_results (
    id bigint generated always as identity primary key,
    emp_id bigint not null references public.emps(id) on delete cascade,
    item_id bigint not null references public.eval_items(id) on delete restrict,
    formula_code text not null,
    max_score numeric(8,3) not null,
    score numeric(8,3) not null,
    score_rate numeric(8,4) generated always as (score / max_score) stored,
    tier text not null,
    tier_band text not null default '',
    note text not null default '',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint emp_item_results_emp_item_uk unique (emp_id, item_id),
    constraint emp_item_results_formula_not_blank check (btrim(formula_code) <> ''),
    constraint emp_item_results_max_score_positive check (max_score > 0),
    constraint emp_item_results_score_range check (score >= 0 and score <= max_score),
    constraint emp_item_results_tier_chk check (
        tier in ('历史极限', '历史顶级', '优秀', '良好', '合格', '一般', '较差', '很差', '极差')
    ),
    constraint emp_item_results_tier_band_chk check (
        tier_band in ('', '高段', '正常', '低段')
    )
);

create index if not exists emp_item_results_emp_idx on public.emp_item_results(emp_id);
create index if not exists emp_item_results_item_idx on public.emp_item_results(item_id);
create index if not exists emp_item_results_formula_idx on public.emp_item_results(formula_code);
create index if not exists emp_item_results_tier_idx on public.emp_item_results(tier, tier_band);

drop view if exists public.v_emp_item_results_by_id;
create view public.v_emp_item_results_by_id as
select
    r.id,
    r.emp_id,
    e.name as emp_name,
    e.period as emp_period,
    r.item_id,
    i.item_code,
    i.item_name,
    r.formula_code,
    r.max_score,
    r.score,
    r.score_rate,
    r.tier,
    r.tier_band,
    r.note,
    r.created_at,
    r.updated_at
from public.emp_item_results r
join public.emps e on e.id = r.emp_id
join public.eval_items i on i.id = r.item_id
order by r.id;

comment on table public.emp_item_results is '皇帝子项正式定分定档结果表；由证据簇和子项公式生成，保存当前正式结果，不作为原始事实源。';
comment on column public.emp_item_results.id is '主键。';
comment on column public.emp_item_results.emp_id is '皇帝 id，引用 emps.id；一个皇帝一个子项只保留当前结果。';
comment on column public.emp_item_results.item_id is '评价子项 id，引用 eval_items.id；例如 I5B 用人与授权。';
comment on column public.emp_item_results.formula_code is '从证据簇到正式分值和档位的公式版本。';
comment on column public.emp_item_results.max_score is '该子项满分快照；例如第五项B用人与授权为 45 分。';
comment on column public.emp_item_results.score is '评分标准口径下的正式子项得分，取值 0 到 max_score；不是证据簇净强度。';
comment on column public.emp_item_results.score_rate is '得分率，自动按 score / max_score 生成，用于映射 V3.2 正式档位。';
comment on column public.emp_item_results.tier is 'V3.2 正式档位：历史极限、历史顶级、优秀、良好、合格、一般、较差、很差、极差。';
comment on column public.emp_item_results.tier_band is '档内位置：高段、正常、低段；无档内标记时为空字符串，不与正式档位混写。';
comment on column public.emp_item_results.note is '定分定档说明，记录证据簇概括、负证拦截、相邻项切分和档内落点理由。';
comment on column public.emp_item_results.created_at is '记录创建时间，使用项目默认时区写入。';
comment on column public.emp_item_results.updated_at is '记录更新时间，使用项目默认时区写入。';
comment on view public.v_emp_item_results_by_id is 'emp_item_results 按主键排序的人工查看视图，联出皇帝名称和子项代码。';
