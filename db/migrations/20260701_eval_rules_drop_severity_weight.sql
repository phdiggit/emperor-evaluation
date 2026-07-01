drop view if exists public.v_eval_rules_by_id;

alter table public.eval_rules
drop constraint if exists eval_rules_severity_weight_range;

alter table public.eval_rules
drop column if exists severity_weight;

create view public.v_eval_rules_by_id as
select
    id,
    item_id,
    rule_code,
    rule_name,
    note,
    created_at,
    updated_at
from public.eval_rules
order by id;

comment on view public.v_eval_rules_by_id is 'eval_rules 按主键排序的人工查看视图；I5B v6 起不再使用 severity_weight。';
