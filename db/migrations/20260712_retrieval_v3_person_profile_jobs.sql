create table if not exists retrieval_v3.person_profile_jobs (
    id bigserial primary key,
    job_code text not null unique,
    object_id bigint not null references retrieval_v3.objects(id) on delete cascade,
    status text not null default 'pending',
    stage text not null default 'queued',
    attempt_count integer not null default 0,
    max_attempts integer not null default 3,
    available_at timestamptz not null default now(),
    lease_expires_at timestamptz,
    worker_id text not null default '',
    last_error text not null default '',
    job_payload jsonb not null default '{}'::jsonb,
    result_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint rv3_person_profile_jobs_object_uk unique (object_id),
    constraint rv3_person_profile_jobs_status_ck check (status in ('pending','running','succeeded','failed')),
    constraint rv3_person_profile_jobs_attempt_ck check (attempt_count >= 0 and max_attempts > 0),
    constraint rv3_person_profile_jobs_payload_ck check (
        jsonb_typeof(job_payload)='object' and jsonb_typeof(result_payload)='object'
    )
);

create index if not exists rv3_person_profile_jobs_queue_idx
on retrieval_v3.person_profile_jobs(status,available_at,id);

create or replace function retrieval_v3.enqueue_person_profile_job(p_object_id bigint)
returns void
language plpgsql
as $$
declare
    v_profile retrieval_v3.person_profiles%rowtype;
begin
    if p_object_id is null then return; end if;
    select pp.* into v_profile
      from retrieval_v3.person_profiles pp
      join retrieval_v3.objects o on o.id=pp.object_id
     where pp.object_id=p_object_id
       and o.object_type='person'
       and o.identity_status='active';
    if not found or v_profile.readiness_status='no_claim' or v_profile.readiness_status='profile_complete' then
        return;
    end if;
    insert into retrieval_v3.person_profile_jobs (
        job_code,object_id,status,stage,job_payload
    ) values (
        'PPR-' || upper(substr(md5(p_object_id::text),1,16)),p_object_id,'pending','queued',
        jsonb_build_object('readiness_status',v_profile.readiness_status::text)
    )
    on conflict (object_id) do update set
        status=case
            when retrieval_v3.person_profile_jobs.status='running' then 'running'
            else 'pending'
        end,
        stage=case
            when retrieval_v3.person_profile_jobs.status='running' then retrieval_v3.person_profile_jobs.stage
            else 'queued'
        end,
        available_at=case
            when retrieval_v3.person_profile_jobs.status='running' then retrieval_v3.person_profile_jobs.available_at
            else now()
        end,
        last_error=case
            when retrieval_v3.person_profile_jobs.status='running' then retrieval_v3.person_profile_jobs.last_error
            else ''
        end,
        job_payload=excluded.job_payload,
        updated_at=now();
end $$;

create or replace function retrieval_v3.enqueue_person_profile_job_from_row()
returns trigger
language plpgsql
as $$
begin
    perform retrieval_v3.enqueue_person_profile_job(new.object_id);
    return new;
end $$;

drop trigger if exists rv3_person_profiles_job_enqueue_trg on retrieval_v3.person_profiles;
create trigger rv3_person_profiles_job_enqueue_trg
after insert or update of readiness_status on retrieval_v3.person_profiles
for each row execute function retrieval_v3.enqueue_person_profile_job_from_row();

do $$ declare r record; begin
    for r in
        select object_id from retrieval_v3.person_profiles
         where readiness_status in ('claim_pending_authority','talent_evaluable')
    loop
        perform retrieval_v3.enqueue_person_profile_job(r.object_id);
    end loop;
end $$;

comment on table retrieval_v3.person_profile_jobs is '人物画像后台状态机任务：claim可用后自动完成talent-grade与negative-talent评审。';
