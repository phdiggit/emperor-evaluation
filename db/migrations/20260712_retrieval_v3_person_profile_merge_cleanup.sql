create table if not exists retrieval_v3.person_profile_merge_audit (
    id bigserial primary key,
    old_profile_id bigint not null unique,
    object_id bigint not null,
    object_name text not null default '',
    identity_status text not null,
    merged_into_object_id bigint,
    profile_snapshot jsonb not null,
    archived_at timestamptz not null default now()
);

create or replace function retrieval_v3.archive_noncanonical_person_profile_by_id(p_object_id bigint)
returns void
language plpgsql
as $$
declare
    o record;
    r record;
begin
    select * into o from retrieval_v3.objects where id=p_object_id;
    if o.object_type='person' and o.identity_status in ('merged','rejected','retired') then
        for r in select * from retrieval_v3.person_profiles where object_id=o.id loop
            insert into retrieval_v3.person_profile_merge_audit (
                old_profile_id,object_id,object_name,identity_status,merged_into_object_id,profile_snapshot
            ) values (
                r.id,o.id,o.canonical_name,o.identity_status::text,
                case when coalesce(o.identity_payload->>'merged_into_object_id','') ~ '^[0-9]+$'
                     then (o.identity_payload->>'merged_into_object_id')::bigint else null end,
                to_jsonb(r)
            ) on conflict (old_profile_id) do nothing;
            delete from retrieval_v3.person_profiles where id=r.id;
        end loop;
    end if;
end $$;

create or replace function retrieval_v3.archive_noncanonical_person_profile()
returns trigger
language plpgsql
as $$
begin
    perform retrieval_v3.archive_noncanonical_person_profile_by_id(new.id);
    return new;
end $$;

drop trigger if exists rv3_objects_archive_noncanonical_profile_trg on retrieval_v3.objects;
create trigger rv3_objects_archive_noncanonical_profile_trg
after insert or update of identity_status on retrieval_v3.objects
for each row execute function retrieval_v3.archive_noncanonical_person_profile();

do $$
declare r record;
begin
    for r in
        select o.* from retrieval_v3.objects o
         where o.object_type='person' and o.identity_status in ('merged','rejected','retired')
           and exists(select 1 from retrieval_v3.person_profiles pp where pp.object_id=o.id)
    loop
        perform retrieval_v3.archive_noncanonical_person_profile_by_id(r.id);
    end loop;
end $$;
