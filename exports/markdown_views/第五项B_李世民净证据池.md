# 第五项B_李世民净证据池

本文件为定档前净证据池视图；只汇总已回源原子证据与证据组裁量候选，不代表最终档位、得分或排名。

## 证据组裁量结论

| cluster_id | polarity | cluster_type | linked_evidence_ids | candidate_strength | upper_probe | adjudication_status | summary |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ADJ-I5B-LISHIMIN-POS-TALENT-ECOSYSTEM-001 | positive | talent_ecosystem_and_authorization | ["EVD-I5B-LISHIMIN-POS-SHIREN-FANGDU-001", "EVD-I5B-LISHIMIN-POS-SHIREN-WEIZHENG-001", "EVD-I5B-LISHIMIN-POS-SHOUQUAN-LIJING-001", "EVD-I5B-LISHIMIN-POS-RONGJIAN-WEIZHENG-001", "EVD-I5B-LISHIMIN-POS-SHIREN-MAZHOU-001", "EVD-I5B-LISHIMIN-POS-GONGCHEN-LIJI-001"] | 3 | extreme_positive_candidate_after_more_cross_type_evidence_and_human_review | source_verified_pending_human_adjudication | 已回源正证在原有幕府聚才、旧敌阵营人才转用、关键军事人才授权、谏臣反馈入口四个维度之外，新增寒门/后进人才通道（马周）与功臣安全/长期授权秩序（李勣）两条新维度。其余对长孙无忌、高士廉、褚遂良、戴胄、岑文本、张玄素、尉迟敬德的扫查仅构成代表性覆盖或同类厚度补充，后续同类正证只增厚元数据，不自动升强。 |
| ADJ-I5B-LISHIMIN-NEG-TALENT-RISK-001 | negative | talent_security_and_trust_risk | ["EVD-I5B-LISHIMIN-NEG-ZHANGLIANG-001", "EVD-I5B-LISHIMIN-NEG-HOUJUNJI-001", "EVD-I5B-LISHIMIN-NEG-WEIZHENG-001"] | 2 | no_extreme_probe_currently; revisit_if_more_systemic_purge_or_chilling_evidence_is_found | source_verified_pending_human_adjudication | 已回源负证显示李世民第五项B存在功臣处置、强嫌疑未坐实、谏臣身后信用受损等非零风险；但侯君集案有确认谋反链条，魏征身后追责未外溢且有复碑反转，张亮案虽为中负但有强安全风险和追悔减轻，故当前更适合作为中负候选证据组，而非系统性清洗或强负/极负证据组。 |

## 原子证据卡

| evidence_id | polarity | human_level | trigger_family | source_id | quote_short | object_anchor | evidence_role | mitigation_flag | upper_bound_flag | cluster_role | cross_item_split | scoring_effect | adjudication_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EVD-I5B-LISHIMIN-POS-GONGCHEN-LIJI-001 | positive | 强正 | 授权专任 | SRC-JTS-J67-LIJI-001 | 汝於李勣無恩，我今將責出之。我死後，汝當授以僕射，即荷汝恩，必致其死力。 |  |  |  |  |  | B项只计功臣安全机制与授权秩序；后续军事战果、边疆经营切第一项/第三项。 | 强正候选证据；不得直接入分，待人工裁判。 | source_verified_pending_human_adjudication |
| EVD-I5B-LISHIMIN-POS-RONGJIAN-WEIZHENG-001 | positive | 强正 | 容谏纳言 | SRC-JTS-J71-WEIZHENG-001 | 太宗與之言，未嘗不欣然納受。 |  |  |  |  |  | B项只计谏臣表达安全与反馈入口；政策纠错效果切第二项B2，认知反省切第五项E。 | 强正候选证据；不得直接入分，待人工裁判。 | source_verified_pending_human_adjudication |
| EVD-I5B-LISHIMIN-POS-SHIREN-FANGDU-001 | positive | 强正 | 识人拔擢 | SRC-JTS-J66-FANGDU-001 | 玄齡獨先收人物，致之幕府。及有謀臣猛將，皆與之潛相申結。 |  |  |  |  |  | B项只计发现和吸纳人才；房杜后续政务成绩切第二项，军事战果切第一项或第三项。 | 强正候选证据；不得直接入分，待人工裁判。 | source_verified_pending_human_adjudication |
| EVD-I5B-LISHIMIN-POS-SHIREN-MAZHOU-001 | positive | 中正 | 异质人才整合 | SRC-JTS-J74-MAZHOU-001 | 太宗怪其能，問何……太宗即日召之，未至間，遣使催促者數四。及謁見，與語甚悅，令直門下省。 |  |  |  |  |  | B项只计人才发现与入仕通道；后续升迁、政务成绩与文辞褒誉切第二项或评价项。 | 中正候选证据；不得直接入分，待人工裁判。 | source_verified_pending_human_adjudication |
| EVD-I5B-LISHIMIN-POS-SHIREN-WEIZHENG-001 | positive | 中正 | 识人拔擢 | SRC-JTS-J71-WEIZHENG-001 | 太宗素器之，引爲詹事主簿。及踐祚，擢拜諫議大夫。 |  |  |  |  |  | B项只计旧敌阵营人才的转化与任用；魏征后续纳谏效果切第二项B2或第五项E。 | 中正候选证据；不得直接入分，待人工裁判。 | source_verified_pending_human_adjudication |
| EVD-I5B-LISHIMIN-POS-SHOUQUAN-LIJING-001 | positive | 中正 | 授权专任 | SRC-JTS-J67-LIJING-001 | 以靖爲代州道行軍總管，率驍騎三千，自馬邑出其不意。 |  |  |  |  |  | B项只计授权与权责匹配；突厥战果与边疆收益切第一项或第三项，制度执行切第二项B3。 | 中正候选证据；不得直接入分，待人工裁判。 | source_verified_pending_human_adjudication |
| EVD-I5B-LISHIMIN-NEG-WEIZHENG-001 | negative | 中负 | 谏臣身后信用反转 | SRC-ZZTJ-J197-198-WEIZHENG-001 | 上始疑征阿黨……踣所撰碑；魏徵若在，不使我有是行也！……復立所制碑。 | 顶级谏臣 | 减轻型中负 | 复碑恢复 | 不得上探强负 | 边界负证，不作为强负核心 | B项只计顶级谏臣身后政治信用与表达安全预期的剩余损伤；魏征生前纳谏正证另入正向证据组，政策纠错效果切第二项B2，皇帝认知/反思能力切第五项E；复碑与恢复评价只作为减轻与封顶因素，不改写本项中负剩余。 | 中负候选证据；单证自动定级，不得上探强负，不得直接入分。 | source_verified_auto_classified_cluster_review_pending |
| EVD-I5B-LISHIMIN-NEG-ZHANGLIANG-001 | negative | 中负 | 疑忌杀害 | SRC-JTS-J69-ZHANGLIANG-001 | 亮有義兒五百，畜養此輩，將何為也？正欲反耳。 |  |  |  |  |  | 谋反和政权安全风险切第五项C；司法严酷或刑罚过重切第五项D；B项只保留功臣处置争议与授权预期受损。 | 中负候选证据；不得直接入分，待人工裁判。 | source_verified_pending_human_adjudication |
| EVD-I5B-LISHIMIN-NEG-HOUJUNJI-001 | negative | 弱负 | 疑忌杀害 | SRC-JTS-J69-HOUJUNJI-001 | 君集辭窮。太宗謂百僚曰：往者家國未安，君集實展其力。 |  |  |  |  |  | 太子谋反和政权安全切第五项C；司法严酷切第五项D；战功本身不在B项加分；B项仅计功臣处置严厉对功臣预期的弱影响。 | 弱负候选证据；不得直接入分，待人工裁判。 | source_verified_pending_human_adjudication |
