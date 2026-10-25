"""Independent synthetic C joint judgments, never copies of ruler decisions."""
from emperor_v4.evaluation.third_item_c_joint import SCHEMA,score_fields

def row(g=3,position='MID'):
    if g is None:position=None
    chains=[dict(chain_id='SYNTHETIC-A',label='合成主防御',basis='合成作战过程',terminal_result_class='UNKNOWN',major_system_success=True)]
    cap=[dict(chain_id='SYNTHETIC-B',label='合成早期任务',basis='合成独立任务',terminal_result_class='NOT_APPLICABLE_CAPABILITY_ONLY')]
    a=dict(schema_version=SCHEMA,position=position,positive_evidence='合成正证',adverse_evidence='合成反证',reason='合成整体判断',
        position_basis='合成位置依据',scope_boundary='本人窗口与材料限制',independent_revalidation_basis='合成独立复验',
        adopted_chain_refs=['SYNTHETIC-A','SYNTHETIC-B'],opponent_windows=[],key_phase_reviews=[],excluded_observations={},limitations=[])
    material=dict(id='FACT',observation_ref='SYNTHETIC-A',label='合成守御材料',kind='既有史实摘要',text='合成作战事实',
        scope='本人窗口',c_chain_refs=['SYNTHETIC-A'],sources=[dict(path='synthetic.md',label='合成来源')],source_passages=[])
    return dict(ruler_id='SYNTHETIC',ruler_name='合成主体',score_ready=g is not None,
        combat_delivery_grade='UNKNOWN' if g is None else f'C1-{g}',final_grade='UNKNOWN' if g is None else f'C-{g}',
        strategy_chains=chains,capability_only_strategy_chains=cap,strategy_chain_refs=['SYNTHETIC-A'],
        capability_only_strategy_chain_refs=['SYNTHETIC-B'],joint_assessment=a,
        public_reading=dict(schema_version='third-item-c-joint-public-v1',story='合成整体判断',window='合成时期',
            position_explanation='合成位置的独立说明',task_titles={'SYNTHETIC-A':'合成主防御','SYNTHETIC-B':'合成早期任务'},
            responsibility='本人国家授权',boundary='本人材料限制',source_note='合成来源说明',evidence_items=[material]),
        **score_fields(g,position))
