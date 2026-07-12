from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from scripts.dev.retrieval_v3_bootstrap import import_psycopg, load_env_file, resolve_dsn, schema_cursor


REBUILD_VERSION = 'canonical-material-v1'


def rebuild(cur: Any) -> dict[str, int]:
    cur.execute("set local retrieval_v3.rebuild_bypass='on'")
    cur.execute('create temp table old_material on commit drop as table retrieval_v3.material_claims')
    cur.execute('create temp table old_passages on commit drop as table retrieval_v3.claim_source_passages')
    cur.execute('create temp table old_objects on commit drop as table retrieval_v3.material_object_links')
    cur.execute('create temp table old_target_first on commit drop as select id,first_claim_id from retrieval_v3.target_objects where first_claim_id is not null')
    cur.execute("select count(*)::int as missing_count from old_material m left join retrieval_v3.claim_cache c on c.claim_key=m.raw_claim_code where c.claim_key is null or btrim(c.canonical_event_key)=''")
    missing = int(cur.fetchone()['missing_count'])
    if missing:
        raise RuntimeError(f'material rebuild blocked: {missing} rows lack canonical claim identity')
    cur.execute('update retrieval_v3.target_objects set first_claim_id=null where first_claim_id is not null')
    cur.execute('delete from retrieval_v3.material_review_queue')
    cur.execute('delete from retrieval_v3.material_claims')
    old_material_rows = cur.rowcount
    cur.execute(
        """
        with ranked as (
            select m.*,c.canonical_event_key as new_canonical_event_key,c.event_group_key as new_event_group_key,c.claim_key,
                   row_number() over(partition by c.canonical_event_key order by
                     case m.review_status when 'accepted' then 0 when 'pending' then 1 else 2 end,
                     m.confidence desc nulls last,m.id) as rn
              from old_material m join retrieval_v3.claim_cache c on c.claim_key=m.raw_claim_code
        )
        insert into retrieval_v3.material_claims(
            source_pack_id,source_passage_id,claim_code,emperor_name,object_name,object_type,
            claim_kind,claim_summary,direction,confidence,review_status,claim_payload,
            raw_claim_code,claim_summary_hash,object_group_key,canonical_event_key,event_group_key,material_rebuild_version
        )
        select r.source_pack_id,r.source_passage_id,
               'CLM-CAN-'||substr(replace(r.new_canonical_event_key,'CEK-',''),1,20),
               r.emperor_name,r.object_name,r.object_type,r.claim_kind,r.claim_summary,'neutral',r.confidence,'pending',
               r.claim_payload || jsonb_build_object(
                 'canonical_event_key',r.new_canonical_event_key,'event_group_key',r.new_event_group_key,
                 'material_rebuild_version',%s::text,
                 'member_claim_keys',(select jsonb_agg(distinct m2.raw_claim_code order by m2.raw_claim_code) from old_material m2 join retrieval_v3.claim_cache c2 on c2.claim_key=m2.raw_claim_code where c2.canonical_event_key=r.new_canonical_event_key)
               ),
               r.raw_claim_code,r.claim_summary_hash,r.object_group_key,r.new_canonical_event_key,r.new_event_group_key,%s
          from ranked r where r.rn=1
        """,
        (REBUILD_VERSION, REBUILD_VERSION),
    )
    canonical_material_rows = cur.rowcount
    cur.execute(
        """
        insert into retrieval_v3.material_claim_members(material_id,claim_key,member_role,member_payload)
        select m.id,c.claim_key,
               case when c.claim_key=m.raw_claim_code then 'representative' else 'evidence_member' end,
               jsonb_build_object('canonical_event_key',c.canonical_event_key,'rebuild_version',%s::text)
          from retrieval_v3.claim_cache c
          join retrieval_v3.material_claims m on m.canonical_event_key=c.canonical_event_key
         where c.status='active'
        on conflict(claim_key) do nothing
        """,
        (REBUILD_VERSION,),
    )
    member_rows = cur.rowcount
    cur.execute(
        """
        insert into retrieval_v3.claim_source_passages(claim_id,source_passage_id,source_pack_id,relation_kind,relation_payload)
        select nm.id,op.source_passage_id,min(op.source_pack_id),op.relation_kind,
               jsonb_build_object('rebuild_version',%s::text,'old_link_count',count(*))
          from old_passages op join old_material om on om.id=op.claim_id
          join retrieval_v3.claim_cache c on c.claim_key=om.raw_claim_code
          join retrieval_v3.material_claims nm on nm.canonical_event_key=c.canonical_event_key
         group by nm.id,op.source_passage_id,op.relation_kind
        """,
        (REBUILD_VERSION,),
    )
    passage_rows = cur.rowcount
    cur.execute(
        """
        insert into retrieval_v3.material_object_links(link_code,claim_id,object_id,target_object_id,role,confidence,review_status,link_payload)
        select 'MOL-CAN-'||upper(substr(md5(nm.id::text||'|'||oo.object_id::text||'|'||oo.role),1,20)),
               nm.id,oo.object_id,min(oo.target_object_id),oo.role,max(oo.confidence),
               case when bool_or(oo.review_status::text='accepted') then 'accepted'::retrieval_v3.rv3_review_status else 'pending'::retrieval_v3.rv3_review_status end,
               jsonb_build_object('rebuild_version',%s::text,'old_link_count',count(*))
          from old_objects oo join old_material om on om.id=oo.claim_id
          join retrieval_v3.claim_cache c on c.claim_key=om.raw_claim_code
          join retrieval_v3.material_claims nm on nm.canonical_event_key=c.canonical_event_key
         group by nm.id,oo.object_id,oo.role
        """,
        (REBUILD_VERSION,),
    )
    object_rows = cur.rowcount
    cur.execute(
        """
        update retrieval_v3.target_objects t set first_claim_id=x.new_claim_id,updated_at=now()
          from (
            select ot.id target_object_id,min(nm.id) new_claim_id
              from old_target_first ot join old_material om on om.id=ot.first_claim_id
              join retrieval_v3.claim_cache c on c.claim_key=om.raw_claim_code
              join retrieval_v3.material_claims nm on nm.canonical_event_key=c.canonical_event_key
             group by ot.id
          ) x where t.id=x.target_object_id
        """
    )
    target_first_rows = cur.rowcount
    return {'old_material_rows':old_material_rows,'canonical_material_rows':canonical_material_rows,'member_rows':member_rows,'passage_rows':passage_rows,'object_rows':object_rows,'target_first_rows':target_first_rows}


def main(argv: Sequence[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description='Replace frozen material rows with one canonical material per semantic event.')
    parser.add_argument('--env-file',type=Path)
    parser.add_argument('--dsn-env',default='EMPEROR_EVAL_RETRIEVAL_V3_DSN')
    parser.add_argument('--pg-schema',default='retrieval_v3')
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--output-json',type=Path)
    args=parser.parse_args(argv)
    if not args.execute: raise SystemExit('--execute is required for the guarded material replacement')
    if args.env_file is not None: load_env_file(args.env_file)
    psycopg,dict_row=import_psycopg()
    with psycopg.connect(resolve_dsn(args.dsn_env),row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur: counts=rebuild(schema_cursor(raw_cur,schema_name=args.pg_schema))
        conn.commit()
    payload={'ok':True,'rebuild_version':REBUILD_VERSION,'counts':counts}
    if args.output_json:
        args.output_json.parent.mkdir(parents=True,exist_ok=True)
        args.output_json.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(payload,ensure_ascii=False,sort_keys=True))
    return 0


if __name__=='__main__': raise SystemExit(main())
