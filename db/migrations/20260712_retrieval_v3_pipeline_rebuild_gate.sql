create table if not exists retrieval_v3.pipeline_rebuild_gates (
    rule_code text primary key,
    gate_status text not null default 'active',
    blocked_stages text[] not null default array[]::text[],
    reason text not null default '',
    audit_root text not null default '',
    gate_payload jsonb not null default '{}'::jsonb,
    activated_at timestamptz not null default now(),
    released_at timestamptz,
    updated_at timestamptz not null default now(),
    constraint rv3_pipeline_rebuild_gates_status_ck check (gate_status in ('active', 'released')),
    constraint rv3_pipeline_rebuild_gates_payload_ck check (jsonb_typeof(gate_payload) = 'object')
);

create or replace function retrieval_v3.enforce_pipeline_rebuild_gate()
returns trigger language plpgsql as $$
declare
    stage_name text := tg_argv[0];
    rule_column text := case when tg_nargs > 1 then tg_argv[1] else '' end;
    row_payload jsonb := case when tg_op = 'DELETE' then to_jsonb(old) else to_jsonb(new) end;
    row_rule text := '';
    active_rules text[];
begin
    if coalesce(current_setting('retrieval_v3.rebuild_bypass', true), '') = 'on' then
        return case when tg_op = 'DELETE' then old else new end;
    end if;
    if rule_column <> '' then row_rule := coalesce(row_payload ->> rule_column, ''); end if;
    select array_agg(g.rule_code order by g.rule_code) into active_rules
      from retrieval_v3.pipeline_rebuild_gates g
     where g.gate_status = 'active' and stage_name = any(g.blocked_stages)
       and (rule_column = '' or row_rule = '' or g.rule_code = row_rule);
    if coalesce(array_length(active_rules, 1), 0) > 0 then
        raise exception 'pipeline rebuild gate blocks % on %.% for stage %, active rules=%', tg_op, tg_table_schema, tg_table_name, stage_name, active_rules
            using errcode = '55000';
    end if;
    return case when tg_op = 'DELETE' then old else new end;
end;
$$;

do $$
declare spec text[]; trigger_name text;
begin
    foreach spec slice 1 in array array[
        array['claim_cache','claim',''], array['claim_source_slices','claim',''], array['claim_evidence','claim',''],
        array['claim_event_groups','event_group',''], array['claim_event_group_members','event_group',''],
        array['material_claims','material',''], array['claim_source_passages','material',''], array['material_object_links','material',''],
        array['object_resolution_queue','material',''], array['material_review_queue','material',''],
        array['claim_rule_routes','route','candidate_rule_code'], array['claim_route_cache','route','candidate_rule_code'],
        array['claim_rule_binding_candidates','binding','candidate_rule_code'], array['claim_rule_bindings','binding','rule_code'],
        array['claim_rule_binding_factor_judgments','factorization','rule_code'], array['claim_rule_binding_factor_choices','factorization',''],
        array['claim_rule_binding_material_scores','material_score','rule_code'], array['target_rule_score_clusters','cluster','rule_code'],
        array['target_object_attributes','object_attribute','rule_code'], array['coverage_gap_events','coverage','']
    ] loop
        if to_regclass(format('retrieval_v3.%I', spec[1])) is null then continue; end if;
        trigger_name := 'rv3_rebuild_gate_' || spec[1];
        execute format('drop trigger if exists %I on retrieval_v3.%I', trigger_name, spec[1]);
        if spec[3] = '' then
            execute format('create trigger %I before insert or update or delete on retrieval_v3.%I for each row execute function retrieval_v3.enforce_pipeline_rebuild_gate(%L)', trigger_name, spec[1], spec[2]);
        else
            execute format('create trigger %I before insert or update or delete on retrieval_v3.%I for each row execute function retrieval_v3.enforce_pipeline_rebuild_gate(%L,%L)', trigger_name, spec[1], spec[2], spec[3]);
        end if;
    end loop;
end;
$$;

comment on table retrieval_v3.pipeline_rebuild_gates is 'Controlled rebuild gate. Active rows block ordinary writes by pipeline stage; rebuild transactions must explicitly set retrieval_v3.rebuild_bypass=on.';
