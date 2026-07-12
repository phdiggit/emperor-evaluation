drop view if exists public.v_evd_clusters_by_id;

alter table public.evd_clusters
drop constraint if exists evd_clusters_direction_net_chk,
drop constraint if exists evd_clusters_cluster_intensity_chk,
drop constraint if exists evd_clusters_net_strength_chk,
drop constraint if exists evd_clusters_positive_strength_chk,
drop constraint if exists evd_clusters_negative_strength_chk,
drop constraint if exists evd_clusters_positive_signal_chk,
drop constraint if exists evd_clusters_negative_signal_chk,
drop constraint if exists evd_clusters_signal_intensity_chk,
drop constraint if exists evd_clusters_direction_signal_chk;

alter table public.evd_clusters
drop column if exists net_strength,
drop column if exists cluster_intensity;

do $$
begin
    if exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'evd_clusters'
          and column_name = 'positive_strength'
    ) and not exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'evd_clusters'
          and column_name = 'positive_signal'
    ) then
        alter table public.evd_clusters
        rename column positive_strength to positive_signal;
    end if;

    if exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'evd_clusters'
          and column_name = 'negative_strength'
    ) and not exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'evd_clusters'
          and column_name = 'negative_signal'
    ) then
        alter table public.evd_clusters
        rename column negative_strength to negative_signal;
    end if;
end;
$$;

update public.evd_clusters
set
    positive_signal = case
        when positive_signal = 0 then 0
        when positive_signal < 5 then round((-5.0 * ln(1.0 - (positive_signal::double precision / 5.0)))::numeric, 3)
        else positive_signal
    end,
    negative_signal = case
        when negative_signal = 0 then 0
        when negative_signal < 5 then round((-5.0 * ln(1.0 - (negative_signal::double precision / 5.0)))::numeric, 3)
        else negative_signal
    end,
    formula_code = 'evidence_cluster_signal_v1',
    updated_at = now()
where formula_code = 'evidence_cluster_formula_v8';

alter table public.evd_clusters
add column if not exists net_signal numeric
generated always as (positive_signal - negative_signal) stored,
add column if not exists signal_intensity numeric
generated always as (greatest(positive_signal, negative_signal)) stored;

do $$
begin
    if exists (
        select 1
        from pg_constraint
        where conrelid = 'public.evd_clusters'::regclass
          and conname = 'evd_clusters_positive_strength_not_null'
    ) and not exists (
        select 1
        from pg_constraint
        where conrelid = 'public.evd_clusters'::regclass
          and conname = 'evd_clusters_positive_signal_not_null'
    ) then
        alter table public.evd_clusters
        rename constraint evd_clusters_positive_strength_not_null
        to evd_clusters_positive_signal_not_null;
    end if;

    if exists (
        select 1
        from pg_constraint
        where conrelid = 'public.evd_clusters'::regclass
          and conname = 'evd_clusters_negative_strength_not_null'
    ) and not exists (
        select 1
        from pg_constraint
        where conrelid = 'public.evd_clusters'::regclass
          and conname = 'evd_clusters_negative_signal_not_null'
    ) then
        alter table public.evd_clusters
        rename constraint evd_clusters_negative_strength_not_null
        to evd_clusters_negative_signal_not_null;
    end if;

    if not exists (
        select 1
        from pg_constraint
        where conrelid = 'public.evd_clusters'::regclass
          and conname = 'evd_clusters_positive_signal_chk'
    ) then
        alter table public.evd_clusters
        add constraint evd_clusters_positive_signal_chk
        check (positive_signal >= 0);
    end if;

    if not exists (
        select 1
        from pg_constraint
        where conrelid = 'public.evd_clusters'::regclass
          and conname = 'evd_clusters_negative_signal_chk'
    ) then
        alter table public.evd_clusters
        add constraint evd_clusters_negative_signal_chk
        check (negative_signal >= 0);
    end if;

    if not exists (
        select 1
        from pg_constraint
        where conrelid = 'public.evd_clusters'::regclass
          and conname = 'evd_clusters_signal_intensity_chk'
    ) then
        alter table public.evd_clusters
        add constraint evd_clusters_signal_intensity_chk
        check (signal_intensity >= 0);
    end if;

    if not exists (
        select 1
        from pg_constraint
        where conrelid = 'public.evd_clusters'::regclass
          and conname = 'evd_clusters_direction_signal_chk'
    ) then
        alter table public.evd_clusters
        add constraint evd_clusters_direction_signal_chk
        check (
            (cluster_direction = 'positive' and net_signal > 0)
            or (cluster_direction = 'negative' and net_signal < 0)
            or (cluster_direction = 'mixed' and net_signal = 0)
        );
    end if;
end;
$$;

drop view if exists public.v_evd_clusters_by_id;
create view public.v_evd_clusters_by_id as
select
    id,
    emp_id,
    item_id,
    rule_id,
    cluster_direction,
    positive_signal,
    negative_signal,
    net_signal,
    signal_intensity,
    formula_code,
    note,
    created_at,
    updated_at
from public.evd_clusters
order by id;

comment on table public.evd_clusters is '规则级证据簇表；由已回源对象材料聚合生成，保存正负原始信号，不在本层映射为极负到极正档位。';
comment on column public.evd_clusters.id is '主键。';
comment on column public.evd_clusters.emp_id is '皇帝 id，引用 emps.id。';
comment on column public.evd_clusters.item_id is '评价子项 id，引用 eval_items.id。';
comment on column public.evd_clusters.rule_id is '评价规则 id，引用 eval_rules.id。';
comment on column public.evd_clusters.cluster_direction is '证据簇净方向，由 net_signal 的符号确定：positive、negative、mixed。';
comment on column public.evd_clusters.positive_signal is '正向原始聚合信号；不封顶，不是旧式强度档位，后续定分公式再做响应函数。';
comment on column public.evd_clusters.negative_signal is '负向原始聚合信号；不封顶，不是旧式强度档位，后续定分公式再做响应函数。';
comment on column public.evd_clusters.net_signal is '正负原始信号差值，按 positive_signal - negative_signal 自动生成，不限幅。';
comment on column public.evd_clusters.signal_intensity is '正负两侧较大原始信号，按 greatest(positive_signal, negative_signal) 自动生成，不限幅。';
comment on column public.evd_clusters.formula_code is '对象材料聚合为原始信号的证据簇公式版本。';
comment on column public.evd_clusters.note is '证据簇说明，概括本 rule 下对象材料来源、方向和主要性质。';
comment on column public.evd_clusters.created_at is '记录创建时间，使用项目默认时区写入。';
comment on column public.evd_clusters.updated_at is '记录更新时间，使用项目默认时区写入。';
comment on view public.v_evd_clusters_by_id is 'evd_clusters 按主键排序的人工查看视图，展示原始信号字段。';
