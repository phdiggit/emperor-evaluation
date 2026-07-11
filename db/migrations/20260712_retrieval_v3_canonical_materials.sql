alter table retrieval_v3.material_claims
    add column if not exists canonical_event_key text not null default '',
    add column if not exists event_group_key text not null default '',
    add column if not exists material_rebuild_version text not null default '';

create unique index if not exists rv3_material_claims_canonical_event_uk
on retrieval_v3.material_claims(canonical_event_key)
where btrim(canonical_event_key) <> '';

create table if not exists retrieval_v3.material_claim_members (
    material_id bigint not null references retrieval_v3.material_claims(id) on delete cascade,
    claim_key text not null references retrieval_v3.claim_cache(claim_key) on delete cascade,
    member_role text not null default 'evidence_member',
    member_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    primary key(material_id, claim_key),
    constraint rv3_material_claim_members_claim_uk unique(claim_key),
    constraint rv3_material_claim_members_role_ck check(member_role in ('representative','evidence_member')),
    constraint rv3_material_claim_members_payload_ck check(jsonb_typeof(member_payload)='object')
);

create index if not exists rv3_material_claim_members_material_idx
on retrieval_v3.material_claim_members(material_id, member_role);

comment on column retrieval_v3.material_claims.canonical_event_key is 'Canonical semantic event identity; exactly one material subject per nonblank key.';
comment on table retrieval_v3.material_claim_members is 'Fan-in from source claim assertions to one canonical material subject.';
