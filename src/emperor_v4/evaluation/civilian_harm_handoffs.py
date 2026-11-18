"""Validate current reciprocal outcome ownership, not historical independence."""
from pathlib import Path
from .formal_json_store import load_json

C4_PATH='docs/评分结算/净收益/第二项治国净收益/财政民生/04-C4正式结算.json'


def validate_pair(link, reverse):
    for field in ('binding_id','relation','basis'):
        if not link.get(field) or link[field] != reverse.get(field):
            raise ValueError(f'Cross-item handoff {field} mismatch')
    if (not link.get('owned_outcome') or not link.get('peer_owned_outcome')
            or link['owned_outcome'] != reverse.get('peer_owned_outcome')
            or link['peer_owned_outcome'] != reverse.get('owned_outcome')):
        raise ValueError('Cross-item outcome ownership mismatch')
    if link.get('institution_node_ids') != reverse.get('institution_node_ids'):
        raise ValueError('Cross-item institution-node binding mismatch')


def verify_handoffs(root: Path, rows):
    cache={};seen=set();count=0
    for row in rows:
        j=row.get('civilian_harm_adjudication',{})
        for link in j.get('cross_item_handoffs',[]):
            bid=link['binding_id']
            if bid in seen:raise ValueError('Duplicate cross-item binding')
            seen.add(bid)
            path=link['peer_source']
            if not path.startswith('docs/评分结算/') or '..' in path.split('/'):
                raise ValueError('Cross-item handoff must use a current formal source')
            if path not in cache:
                data=load_json(root/path)
                cache[path]={r['ruler_id']:r for r in data.get('records',data.get('scores',[]))}
            peer=cache[path].get(link['peer_ruler_id'])
            if peer is None:raise ValueError('Missing cross-item ruler')
            if node_ids:=link.get('institution_node_ids'):
                available={x['institution_node_id'] for x in peer.get('public_institution_nodes',[])}
                if len(node_ids)!=len(set(node_ids)) or not set(node_ids)<=available:
                    raise ValueError('Missing or duplicate institutional outcome')
            if result_id:=link.get('peer_result_id'):
                admitted=[x for a in peer['axis_results'] for x in a['results'] if x['result_id']==result_id]
                excluded=[x for a in peer['axis_results'] for x in a.get('nonadmitted_results',[]) if x['result_id']==result_id]
                if len(admitted)+len(excluded)!=1:raise ValueError('Missing or ambiguous fourth-item result')
                if bool(excluded)!=(link['relation']=='NO_ADDITIONAL_ADMITTED_PRICE'):
                    raise ValueError('Cross-item admission status drift')
                peer=(admitted+excluded)[0]['cross_item_handoff']
            matches=[x for x in peer.get('civilian_harm_handoffs',[]) if x['binding_id']==bid]
            if len(matches)!=1:raise ValueError('Missing or duplicate reciprocal handoff')
            reverse=matches[0]
            if (reverse.get('peer_component')!='I2.C4' or reverse.get('peer_source')!=C4_PATH or reverse.get('peer_ruler_id')!=row['ruler_id']
                    or reverse.get('peer_group_id')!=j['group_id']):
                raise ValueError('Reciprocal harm group target drift')
            validate_pair(link,reverse);count+=1
    return {'binding_count':count,'scope':'CURRENT_LINKS_AND_OWNERSHIP_NOT_SEMANTIC_PROOF'}
