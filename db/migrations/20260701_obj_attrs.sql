create table if not exists public.obj_attrs (
    id bigint generated always as identity primary key,
    obj_id bigint not null references public.raw_objs(id) on delete cascade,
    obj_name text not null default '',
    attr_code text not null,
    value_text text not null default '',
    value_num numeric,
    value_unit text not null default '',
    period_start integer,
    period_end integer,
    region text not null default '',
    doc_id bigint not null references public.src_docs(id),
    obj_src_id bigint references public.obj_srcs(id) on delete set null,
    confidence numeric(4,2) not null default 1.00,
    note text not null default '',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint obj_attrs_attr_code_not_blank check (btrim(attr_code) <> ''),
    constraint obj_attrs_value_present check (value_text <> '' or value_num is not null),
    constraint obj_attrs_period_order check (period_start is null or period_end is null or period_start <= period_end),
    constraint obj_attrs_confidence_range check (confidence >= 0 and confidence <= 1.00)
);

create unique index if not exists obj_attrs_obj_attr_scope_uk
on public.obj_attrs (
    obj_id,
    attr_code,
    coalesce(period_start, -999999),
    coalesce(period_end, 999999),
    region
);

create index if not exists obj_attrs_obj_idx on public.obj_attrs(obj_id);
create index if not exists obj_attrs_attr_code_idx on public.obj_attrs(attr_code);
create index if not exists obj_attrs_doc_idx on public.obj_attrs(doc_id);
create index if not exists obj_attrs_obj_src_idx on public.obj_attrs(obj_src_id);
create index if not exists obj_attrs_lookup_idx on public.obj_attrs(obj_id, attr_code);

create or replace function public.fill_obj_attrs_obj_name()
returns trigger
language plpgsql
as $$
begin
    select ro.name into new.obj_name
    from public.raw_objs ro
    where ro.id = new.obj_id;

    if new.obj_name is null or btrim(new.obj_name) = '' then
        raise exception 'obj_attrs.obj_id % has no raw_objs.name', new.obj_id
            using errcode = '23503';
    end if;

    return new;
end;
$$;

drop trigger if exists obj_attrs_fill_obj_name_before_write on public.obj_attrs;
create trigger obj_attrs_fill_obj_name_before_write
before insert or update of obj_id on public.obj_attrs
for each row execute function public.fill_obj_attrs_obj_name();

drop view if exists public.v_obj_attrs_by_id;
create view public.v_obj_attrs_by_id as
select
    id,
    obj_id,
    obj_name,
    attr_code,
    value_text,
    value_num,
    value_unit,
    period_start,
    period_end,
    region,
    doc_id,
    obj_src_id,
    confidence,
    note,
    created_at,
    updated_at
from public.obj_attrs
order by id;

comment on table public.obj_attrs is '对象属性事实表；保存可复用、已回源的对象属性，不污染 raw_objs，也不保存公式临时拍脑袋参数。';
comment on column public.obj_attrs.id is '主键。';
comment on column public.obj_attrs.obj_id is '对象 id，引用 raw_objs.id；属性主体必须是原始对象。';
comment on column public.obj_attrs.obj_name is '对象显示名，冗余自 raw_objs.name，方便人工查阅；不作为事实源或唯一键。';
comment on column public.obj_attrs.attr_code is '属性代码，如 talent_quality、group_quality、tax_rate、grain_price、population_growth_rate。';
comment on column public.obj_attrs.value_text is '文本或枚举属性值；分类属性优先写这里，如 历史级人才、顶级人才。';
comment on column public.obj_attrs.value_num is '数值属性值；数量型属性写这里，如税率、粮价、人口增长率。';
comment on column public.obj_attrs.value_unit is '数值单位或口径单位，如 fraction、钱/斗、percent；无单位时为空字符串。';
comment on column public.obj_attrs.period_start is '属性适用起始年份；未知或不适用则为空。';
comment on column public.obj_attrs.period_end is '属性适用结束年份；未知或不适用则为空。';
comment on column public.obj_attrs.region is '属性适用地区；无地区限定时为空字符串。';
comment on column public.obj_attrs.doc_id is '属性事实所依据的史料文献 id，引用 src_docs.id。';
comment on column public.obj_attrs.obj_src_id is '触发或支撑该属性入库的对象材料 id，引用 obj_srcs.id；非由某条材料触发时可为空。';
comment on column public.obj_attrs.confidence is '属性事实置信度，0 到 1；表示属性判断本身的可靠程度，不是公式加权因子。';
comment on column public.obj_attrs.note is '属性说明，写明属性性质、适用边界和为什么可复用。';
comment on column public.obj_attrs.created_at is '记录创建时间，使用项目默认时区写入。';
comment on column public.obj_attrs.updated_at is '记录更新时间，使用项目默认时区写入。';
comment on function public.fill_obj_attrs_obj_name() is '写入 obj_attrs 时从 raw_objs.name 自动填充 obj_name。';
comment on trigger obj_attrs_fill_obj_name_before_write on public.obj_attrs is 'obj_attrs 写入前同步对象显示名。';
comment on view public.v_obj_attrs_by_id is 'obj_attrs 按主键排序的人工查看视图，包含对象显示名。';
