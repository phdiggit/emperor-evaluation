alter table retrieval_v3.claim_rule_binding_candidates add column if not exists canonical_event_key text not null default '';
alter table retrieval_v3.claim_rule_bindings add column if not exists canonical_event_key text not null default '';
alter table retrieval_v3.claim_rule_binding_factor_judgments add column if not exists canonical_event_key text not null default '';
alter table retrieval_v3.claim_rule_binding_material_scores add column if not exists canonical_event_key text not null default '';

create or replace function retrieval_v3.inherit_material_canonical_event_key()
returns trigger language plpgsql as $$
begin
    if btrim(coalesce(new.canonical_event_key,''))='' and new.claim_id is not null then
        select m.canonical_event_key into new.canonical_event_key
          from retrieval_v3.material_claims m where m.id=new.claim_id;
    end if;
    if btrim(coalesce(new.canonical_event_key,''))='' then
        raise exception 'canonical_event_key is required for %.%',tg_table_schema,tg_table_name using errcode='23514';
    end if;
    return new;
end;
$$;

do $$
declare table_name text; trigger_name text;
begin
    foreach table_name in array array[
      'claim_rule_binding_candidates','claim_rule_bindings',
      'claim_rule_binding_factor_judgments','claim_rule_binding_material_scores'
    ] loop
      trigger_name='rv3_inherit_event_'||table_name;
      execute format('drop trigger if exists %I on retrieval_v3.%I',trigger_name,table_name);
      execute format('create trigger %I before insert or update of claim_id,canonical_event_key on retrieval_v3.%I for each row execute function retrieval_v3.inherit_material_canonical_event_key()',trigger_name,table_name);
    end loop;
end;
$$;

create unique index if not exists rv3_binding_candidates_event_rule_uk
on retrieval_v3.claim_rule_binding_candidates(
  canonical_event_key,candidate_rule_code,candidate_predicate,candidate_object_role,candidate_direction
) nulls not distinct where btrim(canonical_event_key)<>'';

create unique index if not exists rv3_bindings_event_rule_uk
on retrieval_v3.claim_rule_bindings(
  canonical_event_key,contract_rule_id,predicate,object_role
) where btrim(canonical_event_key)<>'';

create unique index if not exists rv3_factor_judgments_event_rule_uk
on retrieval_v3.claim_rule_binding_factor_judgments(
  target_id,rule_code,canonical_event_key,formula_code,target_action,side
) nulls not distinct where btrim(canonical_event_key)<>'';

create unique index if not exists rv3_material_scores_event_rule_uk
on retrieval_v3.claim_rule_binding_material_scores(
  target_id,rule_code,canonical_event_key,formula_code,object_id,side
) where btrim(canonical_event_key)<>'';

create unique index if not exists rv3_score_clusters_target_rule_formula_uk
on retrieval_v3.target_rule_score_clusters(target_id,rule_code,formula_code);

comment on column retrieval_v3.claim_rule_bindings.canonical_event_key is 'Inherited from canonical material; prevents one semantic event from producing duplicate bindings.';
comment on column retrieval_v3.claim_rule_binding_factor_judgments.canonical_event_key is 'Inherited semantic event identity for factorization dedupe.';
comment on column retrieval_v3.claim_rule_binding_material_scores.canonical_event_key is 'Inherited semantic event identity for scorer dedupe.';
