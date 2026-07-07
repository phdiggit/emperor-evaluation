alter table retrieval_v2.claim_rule_binding_candidates
    add column if not exists candidate_lane text not null default '',
    add column if not exists hint_status text not null default 'formal_candidate',
    add column if not exists required_facts_present jsonb not null default '{}'::jsonb,
    add column if not exists routed_by_profile text not null default '';

update retrieval_v2.claim_rule_binding_candidates
   set hint_status = case
           when nullif(candidate_payload->>'hint_status', '') is not null
               then candidate_payload->>'hint_status'
           when nullif(candidate_payload->>'route_status', '') = 'future_rule_hint'
               then 'future_rule_hint'
           else hint_status
       end,
       candidate_lane = coalesce(
           nullif(candidate_payload->>'candidate_lane', ''),
           nullif(candidate_payload->>'lane', ''),
           nullif(candidate_payload->'source_binding'->>'candidate_lane', ''),
           nullif(candidate_payload->'source_binding'->>'lane', ''),
           nullif(candidate_rule_code, ''),
           candidate_lane
       ),
       required_facts_present = case
           when jsonb_typeof(candidate_payload->'required_facts_present') in ('object', 'array')
               then candidate_payload->'required_facts_present'
           when jsonb_typeof(candidate_payload->'source_binding'->'required_facts_present') in ('object', 'array')
               then candidate_payload->'source_binding'->'required_facts_present'
           else required_facts_present
       end,
       routed_by_profile = coalesce(
           nullif(candidate_payload->>'routed_by_profile', ''),
           nullif(candidate_payload->>'capture_profile', ''),
           nullif(candidate_payload->>'created_from', ''),
           routed_by_profile
       )
 where candidate_payload <> '{}'::jsonb;

do $$
begin
    if not exists (
        select 1
          from pg_constraint
         where conname = 'rv2_claim_rule_binding_candidates_hint_status_ck'
           and conrelid = 'retrieval_v2.claim_rule_binding_candidates'::regclass
    ) then
        alter table retrieval_v2.claim_rule_binding_candidates
            add constraint rv2_claim_rule_binding_candidates_hint_status_ck
            check (hint_status in ('formal_candidate', 'current_rule_candidate', 'future_rule_hint', 'context_only', 'rejected'));
    end if;
    if not exists (
        select 1
          from pg_constraint
         where conname = 'rv2_claim_rule_binding_candidates_required_facts_present_ck'
           and conrelid = 'retrieval_v2.claim_rule_binding_candidates'::regclass
    ) then
        alter table retrieval_v2.claim_rule_binding_candidates
            add constraint rv2_claim_rule_binding_candidates_required_facts_present_ck
            check (jsonb_typeof(required_facts_present) in ('object', 'array'));
    end if;
end $$;

create index if not exists rv2_claim_rule_binding_candidates_lane_idx
on retrieval_v2.claim_rule_binding_candidates(candidate_item_code, candidate_lane, hint_status, candidate_rule_code);

create index if not exists rv2_claim_rule_binding_candidates_future_hint_idx
on retrieval_v2.claim_rule_binding_candidates(candidate_item_code, candidate_lane, candidate_rule_code, created_at)
where hint_status = 'future_rule_hint';

comment on column retrieval_v2.claim_rule_binding_candidates.candidate_lane is '跨项候选 lane，例如 I5B.team_building 或 I5C.power_control；未知时留空或按 rule_code 回退。';
comment on column retrieval_v2.claim_rule_binding_candidates.hint_status is '候选性质：formal_candidate/current_rule_candidate 可进入窄验；future_rule_hint/context_only/rejected 只能沉淀或复核。';
comment on column retrieval_v2.claim_rule_binding_candidates.required_facts_present is 'judge 输出的候选事实完整性标记；仅供路由和复核，不直接入分。';
comment on column retrieval_v2.claim_rule_binding_candidates.routed_by_profile is '产生候选路由的抓包 profile 或工具名，例如 personnel_political_wide。';
