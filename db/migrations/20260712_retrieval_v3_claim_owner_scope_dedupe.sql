create or replace view retrieval_v3.claim_owner_scopes as
select
    c.claim_key,
    c.emperor_name as owner_name,
    case
        when btrim(c.emperor_name) = '' then 'blank_owner'
        when t.target_code is not null then 'target_emperor'
        else 'external_or_unregistered_owner'
    end as owner_scope,
    t.target_code as owner_target_code,
    c.object_name,
    c.claim_summary,
    c.status,
    c.first_run_code,
    c.last_run_code,
    c.updated_at
from retrieval_v3.claim_cache c
left join lateral (
    select rt.target_code
      from retrieval_v3.retrieval_targets rt
     where rt.emperor_name = c.emperor_name
     order by rt.id
     limit 1
) t on true;

comment on view retrieval_v3.claim_owner_scopes is 'claim owner scope view; exactly one row per claim_key even when an emperor has multiple retrieval targets.';
