do $$
begin
    if not exists (
        select 1 from pg_type t join pg_namespace n on n.oid=t.typnamespace
         where n.nspname='retrieval_v3' and t.typname='rv3_person_profile_readiness'
    ) then
        create type retrieval_v3.rv3_person_profile_readiness as enum (
            'no_claim',
            'claim_pending_authority',
            'talent_evaluable',
            'profile_complete'
        );
    end if;
end $$;

alter table retrieval_v3.person_profiles
    add column if not exists readiness_status retrieval_v3.rv3_person_profile_readiness not null default 'no_claim',
    add column if not exists readiness_payload jsonb not null default '{}'::jsonb,
    add column if not exists readiness_updated_at timestamptz not null default now();

create or replace function retrieval_v3.refresh_person_profile_readiness(p_object_id bigint)
returns void
language plpgsql
as $$
declare
    v_claim_count integer;
    v_authority_count integer;
    v_status retrieval_v3.rv3_person_profile_readiness;
begin
    if p_object_id is null then
        return;
    end if;
    select count(*) into v_claim_count
      from retrieval_v3.claim_cache cc
      join retrieval_v3.objects o on o.id=p_object_id
     where cc.status='active'
       and (
            cc.object_id=p_object_id
            or lower(cc.object_name)=lower(o.canonical_name)
            or exists (
                select 1 from retrieval_v3.object_names onm
                 where onm.object_id=p_object_id and onm.review_status='accepted'
                   and (lower(onm.name_text)=lower(cc.object_name) or lower(onm.normalized_name)=lower(cc.object_name))
            )
       );
    select count(*) into v_authority_count
      from retrieval_v3.person_profile_claim_links ppl
      join retrieval_v3.objects o on o.id=p_object_id
     where (ppl.object_id=p_object_id or lower(ppl.object_name)=lower(o.canonical_name))
       and ppl.profile_field='authority_evaluation'
       and ppl.proposal_status='accepted';

    select case
        when coalesce(pp.talent_grade_version,'')<>''
         and pp.talent_grade is not null
         and coalesce(pp.negative_talent_version,'')<>'' then 'profile_complete'::retrieval_v3.rv3_person_profile_readiness
        when v_claim_count=0 then 'no_claim'::retrieval_v3.rv3_person_profile_readiness
        when v_authority_count=0 then 'claim_pending_authority'::retrieval_v3.rv3_person_profile_readiness
        else 'talent_evaluable'::retrieval_v3.rv3_person_profile_readiness
    end into v_status
      from retrieval_v3.person_profiles pp where pp.object_id=p_object_id;

    update retrieval_v3.person_profiles
       set readiness_status=v_status,
           readiness_payload=jsonb_build_object(
               'active_claim_count',v_claim_count,
               'accepted_authority_evaluation_count',v_authority_count,
               'talent_review_completed',coalesce(talent_grade_version,'')<>'',
               'negative_review_completed',coalesce(negative_talent_version,'')<>''
           ),
           readiness_updated_at=now()
     where object_id=p_object_id;
end $$;

create or replace function retrieval_v3.sync_person_profile_readiness_from_row()
returns trigger
language plpgsql
as $$
declare
    p_object_id bigint;
begin
    perform retrieval_v3.refresh_person_profile_readiness(coalesce(new.object_id,old.object_id));
    if tg_table_name in ('claim_cache','person_profile_claim_links') then
        for p_object_id in
            select distinct o.id
              from retrieval_v3.objects o
              left join retrieval_v3.object_names onm on onm.object_id=o.id and onm.review_status='accepted'
             where o.object_type='person'
               and o.identity_status in ('active','draft','needs_review')
               and (
                    lower(o.canonical_name)=lower(coalesce(new.object_name,old.object_name,''))
                    or lower(onm.name_text)=lower(coalesce(new.object_name,old.object_name,''))
                    or lower(onm.normalized_name)=lower(coalesce(new.object_name,old.object_name,''))
               )
        loop
            perform retrieval_v3.refresh_person_profile_readiness(p_object_id);
        end loop;
    end if;
    if tg_op='UPDATE' and old.object_id is distinct from new.object_id then
        perform retrieval_v3.refresh_person_profile_readiness(old.object_id);
    end if;
    return coalesce(new,old);
end $$;

drop trigger if exists rv3_claim_cache_profile_readiness_trg on retrieval_v3.claim_cache;
create trigger rv3_claim_cache_profile_readiness_trg
after insert or delete or update of object_id,status on retrieval_v3.claim_cache
for each row execute function retrieval_v3.sync_person_profile_readiness_from_row();

drop trigger if exists rv3_profile_claim_links_readiness_trg on retrieval_v3.person_profile_claim_links;
create trigger rv3_profile_claim_links_readiness_trg
after insert or delete or update of object_id,profile_field,proposal_status on retrieval_v3.person_profile_claim_links
for each row execute function retrieval_v3.sync_person_profile_readiness_from_row();

drop trigger if exists rv3_person_profiles_readiness_trg on retrieval_v3.person_profiles;
create trigger rv3_person_profiles_readiness_trg
after insert or update of talent_grade,talent_grade_version,negative_talent_class,negative_talent_version on retrieval_v3.person_profiles
for each row execute function retrieval_v3.sync_person_profile_readiness_from_row();

do $$
declare r record;
begin
    for r in select object_id from retrieval_v3.person_profiles loop
        perform retrieval_v3.refresh_person_profile_readiness(r.object_id);
    end loop;
end $$;

create index if not exists rv3_person_profiles_readiness_idx
on retrieval_v3.person_profiles(readiness_status,review_status,object_id);

comment on column retrieval_v3.person_profiles.readiness_status is '人物画像流水线状态：无claim、claim待权威评价、可评人才等级、画像完整。';
comment on column retrieval_v3.person_profiles.readiness_payload is '画像就绪状态的活动claim数、权威评价数及人才/政治风险评审完成标记。';
