# 第五项B扩展第一批检索线索

本文件为机器审计视图，用于代码审查、数据追踪和回源定位，不作为人工业务审核主入口。

本文件导出待回源检索线索；未回源材料不得入分。

- **活动人物组**：扩展第一批
- **覆盖人物**：刘邦、雍正、朱元璋

| search_id | person | subitem | polarity | trigger_family | query_terms | result_status | result_summary | linked_evidence_id | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SRCH-I5B-LIUBANG-NEG-GONGCHEN-001 | 刘邦 | 第五项B | negative | 功臣安全 | 韩信;彭越;英布;诛;族;谋反;疑;吕后 | evidence_found_card_created | 已回源韩信、彭越、英布三条功臣安全相关材料，均已转为刘邦第五项B负证卡，并已汇入刘邦负向证据组；当前进入人工裁量前复核阶段。 | EVD-I5B-LIUBANG-NEG-HANXIN-001;EVD-I5B-LIUBANG-NEG-PENGYUE-001;EVD-I5B-LIUBANG-NEG-YINGBU-CHILL-001 | 已形成 source/evidence 链接，并纳入 cluster_id=ADJ-I5B-LIUBANG-NEG-MERIT-SUBJECT-SAFETY-001；不得直接入分。 |
| SRCH-I5B-LIUBANG-CUT-ADJACENT-001 | 刘邦 | 第五项B | negative | 相邻项切分 | 楚汉;战功;封赏;谋反;政权安全;诛杀;用人 | lead_needs_source_review | 专门用于回源后切分战役胜负、封赏政治、谋反政权安全与人才生态剩余影响；刘邦其他线索虽已在证据卡中完成相邻项剥离，但本条尚未形成独立 source/evidence 链。 |  | 不得强行绑定已存在证据卡；待后续是否需要单列切分锚点再处理。 |
| SRCH-I5B-LIUBANG-POS-RONGJIAN-001 | 刘邦 | 第五项B | positive | 容谏反馈 | 谏;从之;纳;沛公;汉王;高帝;张良;萧何 | evidence_found_card_created | 已据《史记》卷五十五回源张良多次进策与霸上听谏材料，并转为刘邦第五项B容谏反馈正证卡；该卡现已纳入刘邦正向证据组。 | EVD-I5B-LIUBANG-POS-ZHANGLIANG-RONGJIAN-001 | 已形成 source/evidence 链接，并纳入 cluster_id=ADJ-I5B-LIUBANG-POS-TALENT-AUTHORIZATION-001；不得直接入分。 |
| SRCH-I5B-LIUBANG-POS-RONGREN-001 | 刘邦 | 第五项B | positive | 异质人才整合 | 韩信;陈平;雍齿;降臣;旧怨;复用;赦 | evidence_found_card_created | 已据《史记》卷五十六回源陈平自楚来降、遭群议后仍获护军中尉授权材料，并转为刘邦第五项B异质人才整合正证卡；该卡现已纳入刘邦正向证据组。 | EVD-I5B-LIUBANG-POS-CHENPING-001 | 已形成 source/evidence 链接，并纳入 cluster_id=ADJ-I5B-LIUBANG-POS-TALENT-AUTHORIZATION-001；不得直接入分。 |
| SRCH-I5B-LIUBANG-POS-SHOUQUAN-001 | 刘邦 | 第五项B | positive | 授权专任 | 萧何;韩信;张良;陈平;拜大将;留守;将兵;委任 | evidence_found_card_created | 已据《史记》卷八回源韩信请假王、张良劝立齐王材料，并转为刘邦第五项B授权专任正证卡；该卡现已纳入刘邦正向证据组。 | EVD-I5B-LIUBANG-POS-HANXIN-QIWANG-001 | 已形成 source/evidence 链接，并纳入 cluster_id=ADJ-I5B-LIUBANG-POS-TALENT-AUTHORIZATION-001；不得直接入分。 |
| SRCH-I5B-LIUBANG-POS-SHIREN-001 | 刘邦 | 第五项B | positive | 识人拔擢 | 萧何;张良;韩信;陈平;任用;拜;举;荐 | evidence_found_card_created | 已据《史记》卷八回源三杰与“吾能用之”材料，并转为刘邦第五项B识人拔擢正证卡；该卡现已纳入刘邦正向证据组。 | EVD-I5B-LIUBANG-POS-SANJIE-001 | 已形成 source/evidence 链接，并纳入 cluster_id=ADJ-I5B-LIUBANG-POS-TALENT-AUTHORIZATION-001；不得直接入分。 |
| SRCH-I5B-ZHUYUANZHANG-NEG-HULAN-001 | 朱元璋 | 第五项B | negative | 功臣安全 | 胡惟庸;蓝玉;李善长;族诛;坐;党案;功臣 | lead_needs_source_review | 待查胡蓝党案及李善长等功臣处置对人才安全感和授权预期的影响，政权安全和政治残酷性切相邻项。 |  | 下一批初始检索线索；待回源，不得入分。 |
| SRCH-I5B-ZHUYUANZHANG-CUT-ADJACENT-001 | 朱元璋 | 第五项B | negative | 相邻项切分 | 战功;制度;丞相;党案;司法;政权安全;人才生态 | lead_needs_source_review | 专门用于切分战功、废相制度、党案政权安全、司法残酷与第五项B人才生态/表达安全剩余影响。 |  | 下一批初始检索线索；待回源，不得入分。 |
| SRCH-I5B-ZHUYUANZHANG-NEG-QIANLIAN-001 | 朱元璋 | 第五项B | negative | 系统性清洗/牵连扩大 | 空印;郭桓;坐死;株连;杀;官吏;牵连 | lead_needs_source_review | 待查空印、郭桓等案件是否对官僚人才安全感和表达生态构成第五项B负面剩余；行政整肃、司法残酷、政治残酷性需切相邻项。 |  | 下一批初始检索线索；待回源，不得入分。 |
| SRCH-I5B-ZHUYUANZHANG-POS-RONGREN-001 | 朱元璋 | 第五项B | positive | 异质人才整合 | 降臣;儒士;刘基;宋濂;李善长;浙东;淮西;任用 | lead_needs_source_review | 待查朱元璋对不同地域、派系、文武与降附人才的整合能力；派系政治本身切相邻项。 |  | 下一批初始检索线索；待回源，不得入分。 |
| SRCH-I5B-ZHUYUANZHANG-POS-SHOUQUAN-001 | 朱元璋 | 第五项B | positive | 授权专任 | 徐达;常遇春;李善长;刘基;总兵;丞相;委任;专任 | lead_needs_source_review | 待查朱元璋对核心文武人才的授权专任和职责匹配，剥离战役成果和制度收益。 |  | 下一批初始检索线索；待回源，不得入分。 |
| SRCH-I5B-ZHUYUANZHANG-POS-SHIREN-001 | 朱元璋 | 第五项B | positive | 识人拔擢 | 刘基;李善长;徐达;常遇春;宋濂;任用;拜;征 | lead_needs_source_review | 待查朱元璋创业期和建国初期对文武人才的识别、拔擢与吸纳；不得把明初战果或制度成效回填第五项B。 |  | 下一批初始检索线索；待回源，不得入分。 |
