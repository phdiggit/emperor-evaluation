# 《元史》卷038四域同读视图

- 任务：`YUAN-YUANSHI-038-MULTIDOMAIN`
- 状态：`shadow`
- 固定修订：`2642605`
- 输入指纹：`f339d0d6a7f13ee36cebbbe04609118c5abc1b0c5b23bbbfb0852610a7b1c9ed`
- 共享事实：61
- 战役交接路由：7
- 财政民生路由：23
- 大型工程路由：1
- 政治事件路由：30
- 完整通读：完成（shadow；未写正式事实或评分）

## 战役交接

### CHF-YUANSHI-038-GUANGXI-DAOZHOU-RAID

- 时间：元统元年十二月乙丑—元统元年十二月乙丑
- 地点：广西、湖南道州
- 行动：广西徭军进犯湖南并攻陷道州，千户郭震战死，徭军焚掠后撤。
- 结果：道州失陷并遭焚掠，守将阵亡。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-GUANGXI-DAOZHOU-1333`
- 引文：廣西徭寇湖南，陷道州

### CHF-YUANSHI-038-GUANGXI-CAMPAIGNS-1334

- 时间：元统二年三月癸巳至壬子—元统二年三月癸巳至壬子
- 地点：广西、庆远、全州
- 行动：广西徭军再起，杀元帅吉烈思并掠库；朝廷先遣右丞领军，后又以二万军进击进犯全州的徭军。
- 结果：广西镇压升级为两次中央调兵行动。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-GUANGXI-1334`
- 引文：廣西徭賊復起，殺同知元帥吉烈思

### CHF-YUANSHI-038-BANDIT-CAPTURE-INCENTIVES

- 时间：元统二年三月乙巳—元统二年三月乙巳
- 地点：益都、真定
- 行动：因两地盗起，朝廷派省院官督捕，提高擒获奖赏，捕获三人者授一官。
- 结果：地方缉盗获得中央督导和官爵激励。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-YIDU-ZHENDING-BANDITS-1334`
- 引文：益都、真定盜起

### CHF-YUANSHI-038-HEZHOU-CAPTURE-CAMPAIGN

- 时间：元统二年九月甲午—元统二年九月甲午
- 地点：贺州、广西
- 行动：徭军攻陷贺州，朝廷调河南、江浙、江西、湖广诸军与八番义从，由广西宣慰使统兵反击。
- 结果：贺州失陷后形成跨省联合进讨。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-HEZHOU-1334`
- 引文：徭賊陷賀州

### CHF-YUANSHI-038-HUGUANG-GARRISON-FARMS

- 时间：元统二年十月丁卯—元统二年十月丁卯
- 地点：湖广
- 行动：朝廷设黎兵屯田万户府，下辖十三千户所，每所兵千人、屯户五百，并给田牛种具、免除差徭。
- 结果：湖广建立本地化军屯体系与十三所武装编制。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-HUGUANG-LI-GARRISON-FARMS`
- 引文：立湖廣黎兵屯田萬戶府

### CHF-YUANSHI-038-GUANGXI-REVOLT-1335

- 时间：至元元年八月—至元元年八月
- 地点：广西
- 行动：广西徭众再次反叛，朝廷命湖广行省右丞完者领军进讨。
- 结果：广西战事在新年继续。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-GUANGXI-1335`
- 引文：月，廣西徭反

### CHF-YUANSHI-038-WESTERN-REBELLION

- 时间：至元元年十二月丁丑—至元元年十二月丁丑
- 地点：西番
- 行动：西番叛乱发生，朝廷派兵进击。
- 结果：西部进入军事镇压。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-WESTERN-REBELLION-1335`
- 引文：西番賊起，遣兵擊之

## 财政民生

### CHF-YUANSHI-038-INITIAL-FLOOD-FAMINE-RELIEF

- 时间：至顺四年六月—至顺四年六月
- 地点：京畿、关中、河南、两淮
- 行动：京畿霖雨水深丈余、饥民四十余万，朝廷发钞四万锭；泾河、黄河泛滥且两淮旱饥。
- 结果：新帝即位之初多区灾荒，京畿饥民获得赈钞。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-038-INITIAL-FLOOD-FAMINE-RELIEF`
- 引文：饑民四十餘萬

### CHF-YUANSHI-038-NINGXIA-RELIEF

- 时间：元统元年九月—元统元年九月
- 地点：宁夏
- 行动：朝廷赈恤宁夏饥民五万三千人一月。
- 结果：五万余饥民获得一个月救济。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-038-NINGXIA-RELIEF`
- 引文：賑恤寧夏饑民五萬三千人一月

### CHF-YUANSHI-038-REVENUE-OFFICE-CHANGES

- 时间：元统元年十一月—元统元年十一月
- 地点：富州、江西、湖广、江浙、河南
- 行动：朝廷罢富州金课，并在四省恢复榷茶运司。
- 结果：一处矿课取消，跨省茶税专营机构恢复。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-038-REVENUE-OFFICE-CHANGES`
- 引文：罷富州金課

### CHF-YUANSHI-038-JIANGZHE-FAMINE-RELIEF-1333

- 时间：元统元年十一月—元统元年十一月
- 地点：江浙
- 行动：江浙旱饥，朝廷发义仓粮并募集富人出粟赈济。
- 结果：灾区粮源由义仓和民间捐粟共同补充。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-038-JIANGZHE-FAMINE-RELIEF-1333`
- 引文：府。江浙旱饑

### CHF-YUANSHI-038-WINTER-REGIONAL-RELIEF-1334

- 时间：元统二年正月至二月—元统二年正月至二月
- 地点：东平、济宁、曹州、塞北、安丰、永平、瑞州
- 行动：多地水旱雹灾并饥，朝廷先发钞六万锭，又动用仓粮、麦一万六千七百石、钞五千锭和米一万石分区赈济。
- 结果：七地灾民获得钞粮救济。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-038-WINTER-REGIONAL-RELIEF-1334`
- 引文：詔以鈔六萬錠賑之

### CHF-YUANSHI-038-RELIGIOUS-LABOR-EQUALITY

- 时间：元统二年正月癸卯—元统二年正月癸卯
- 地点：全国
- 行动：朝廷规定僧道与普通民户一体承担差役。
- 结果：宗教人口原有役法优待被取消。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-038-RELIGIOUS-LABOR-EQUALITY`
- 引文：敕僧道與民一體充役

### CHF-YUANSHI-038-SOUTHERN-MASS-RELIEF

- 时间：元统二年三月庚子—元统二年三月庚子
- 地点：杭州、镇江、嘉兴、常州、松江、江阴
- 行动：六地水旱疾疫，朝廷发义仓粮赈饥民五十七万二千户。
- 结果：五十七万余户获得仓粮救济。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-038-SOUTHERN-MASS-RELIEF`
- 引文：陰水旱疾疫

### CHF-YUANSHI-038-BUDDHIST-RITUAL-COST-CUT

- 时间：元统二年三月甲辰—元统二年三月甲辰
- 地点：兴和路
- 行动：兴和一路佛事耗钞一万三千五百三十余锭，朝廷改按两都例给膳僧钱以削减冗费。
- 结果：地方佛事支出被定额化压缩。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-038-BUDDHIST-RITUAL-COST-CUT`
- 引文：一路所費，為鈔萬三千五百三十餘錠

### CHF-YUANSHI-038-SHANDONG-HUAIXI-RELIEF

- 时间：元统二年三月—元统二年三月
- 地点：山东、淮西
- 行动：山东霖雨水涌、淮西饥荒，分别赈糶米二万二千石与二万石。
- 结果：两区共投放四万二千石救荒粮。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-038-SHANDONG-HUAIXI-RELIEF`
- 引文：山東霖雨，水湧，民饑

### CHF-YUANSHI-038-YUNNAN-WAR-DEATH-BURIAL

- 时间：元统二年四月庚午—元统二年四月庚午
- 地点：云南
- 行动：朝廷规定云南出征军士死亡者每人给钞二锭安葬。
- 结果：出征阵亡军士形成定额丧葬抚恤。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-038-YUNNAN-WAR-DEATH-BURIAL`
- 引文：雲南出征軍士亡歿者

### CHF-YUANSHI-038-CAPITAL-SALT-BUREAUS

- 时间：元统二年四月癸未—元统二年四月癸未
- 地点：京师南城、京师北城
- 行动：朝廷在京师南北城设置盐局，由官府直接卖盐以纠正专利弊端。
- 结果：京师食盐销售转为官营网点。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-038-CAPITAL-SALT-BUREAUS`
- 引文：立鹽局于京師南北城

### CHF-YUANSHI-038-BUDDHIST-DONATION-CUT

- 时间：元统二年四月乙酉—元统二年四月乙酉
- 地点：全国
- 行动：因佛事布施较世祖时每年大增金银、帛与钞，朝廷除历朝周年忌日外全部停止。
- 结果：宫廷佛事常年支出被大幅裁减。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-038-BUDDHIST-DONATION-CUT`
- 引文：佛事布施，費用太廣

### CHF-YUANSHI-038-JIANGZHE-GREAT-FAMINE

- 时间：元统二年五月—元统二年五月
- 地点：江浙
- 行动：江浙大饥波及五十九万五百六十四户，朝廷发米六万七百石、钞二千八百锭，募富民并动用常平义仓，同时留存海运粮七十八万余石备急。
- 结果：大规模饥荒获得多源粮钞救济与海漕储备。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-038-JIANGZHE-GREAT-FAMINE`
- 引文：江浙大饑，以戶計者五十九萬五百六十四

### CHF-YUANSHI-038-PRIVILEGED-CORVEE-EQUALITY

- 时间：元统二年五月—元统二年五月
- 地点：京师诸县
- 行动：王侯宗戚所属军站、人匠、鹰房、控鹤等户凡隶京师诸县者，均须与当地民户一体服役。
- 结果：特权属户被纳入地方统一差役。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-038-PRIVILEGED-CORVEE-EQUALITY`
- 引文：王侯宗戚軍站、人匠、鷹房、控鶴

### CHF-YUANSHI-038-YUNNAN-NORTHEAST-RELIEF

- 时间：元统二年六月—元统二年六月
- 地点：云南大理中庆、辽东多地
- 行动：云南因叛乱、失业与灾伤发钞十万锭；大宁至懿州水旱蝗并大饥，再发钞二万锭遣官赈济。
- 结果：西南与东北重灾区合获十二万锭赈款。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-038-YUNNAN-NORTHEAST-RELIEF`
- 引文：民多失業，加以災傷，民饑

### CHF-YUANSHI-038-MIDYEAR-DISASTER-RELIEF

- 时间：元统二年七月至九月—元统二年七月至九月
- 地点：池州、南康、吉安
- 行动：池州饥发米千石并募富民，南康旱蝗赈糶十二万三千石，吉安水灾再发粮二万石。
- 结果：三地合获粮食救济并动员民间捐粟。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-038-MIDYEAR-DISASTER-RELIEF`
- 引文：發米一千石及募富民出粟賑之

### CHF-YUANSHI-038-HALF-RENT-REMISSION

- 时间：元统二年十月己卯—元统二年十月己卯
- 地点：全国
- 行动：皇太后上尊号后大赦，并免当年民租一半。
- 结果：全国民户获得半额租税减免。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-038-HALF-RENT-REMISSION`
- 引文：思與普天同茲大慶，其赦天下

### CHF-YUANSHI-038-SPRING-RELIEF-1335

- 时间：至元元年三月—至元元年三月
- 地点：河州、龙兴、益都
- 行动：河州大雪冻死多数牲畜并致饥；龙兴发粮九万九千八百石，益都旱饥赈米一万石。
- 结果：三地极端天气与旱荒获不同程度救济。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-038-SPRING-RELIEF-1335`
- 引文：大雪十日，深八尺

### CHF-YUANSHI-038-SALT-SURTAX-SUSPENDED

- 时间：至元元年三月甲辰—至元元年三月甲辰
- 地点：山东、河间、两淮、福建
- 行动：四地原拟增盐课十八万五千引，朝廷暂缓征收，只催办原有正额。
- 结果：盐业新增税负被暂停。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-038-SALT-SURTAX-SUSPENDED`
- 引文：增鹽課一十八萬五千引

### CHF-YUANSHI-038-FIFTY-MYRIAD-GRANT

- 时间：至元元年四月丙寅—至元元年四月丙寅
- 地点：大都
- 行动：朝廷拨钞五十万锭，由徽政院分给达达兀鲁思、怯薛丹及各爱马。
- 结果：宫廷与宿卫相关群体获得巨额钞款。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-038-FIFTY-MYRIAD-GRANT`
- 引文：詔以鈔五十萬錠

### CHF-YUANSHI-038-ROYAL-FOOD-COST-CUT

- 时间：至元元年十二月丙辰—至元元年十二月丙辰
- 地点：全国
- 行动：朝廷裁减诸王、公主、驸马的饮膳费用。
- 结果：宗室日常财政支出被压缩。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-038-ROYAL-FOOD-COST-CUT`
- 引文：制省諸王、公主、駙馬飲饍之費

### CHF-YUANSHI-038-SICHUAN-SALT-WELL-REFORM

- 时间：至元元年闰月乙酉—至元元年闰月乙酉
- 地点：四川
- 行动：四川盐运司保留原有官井制盐，其余盐井准民间煮造并按三成征课。
- 结果：四川盐业形成官井保留、民井纳三成税的新制。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-038-SICHUAN-SALT-WELL-REFORM`
- 引文：鹽井仍舊造鹽

### CHF-YUANSHI-038-YEAR-END-RELIEF-AND-RENT

- 时间：至元元年岁末—至元元年岁末
- 地点：江西、全国
- 行动：江西大水饥荒赈糶米七万七千石，并赐天下田租一半。
- 结果：江西灾民获粮，全国田租减半。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-038-YEAR-END-RELIEF-AND-RENT`
- 引文：江西大水，民饑

## 大型工程

### CHF-YUANSHI-038-WENZONG-TEMPORARY-SHRINE

- 时间：元统元年十一月辛亥—元统元年十一月辛亥
- 地点：太庙
- 行动：因文宗寝庙未建，朝廷在英宗室旁临时结彩殿安奉文宗神主。
- 结果：文宗神主取得临时奉安空间。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `WORK-THREAD-YUANSHI-038-WENZONG-TEMPORARY-SHRINE`
- 引文：時寢廟未建

## 政治事件

### CHF-YUANSHI-038-LINEAGE-AND-EXILE

- 时间：延祐七年至至顺元年—延祐七年至至顺元年
- 地点：北方、高丽大青岛、广西静江
- 行动：明宗后遇害后，妥懽帖睦尔先被徙高丽隔绝，继又以非明宗子之说移居静江。
- 结果：妥懽帖睦尔在即位前长期遭贬逐与身份攻击。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-038-LINEAGE-AND-EXILE`
- 引文：遂徙帝于高麗，使居大青島中，不與人接

### CHF-YUANSHI-038-DELAYED-SUCCESSION

- 时间：宁宗崩后至元统元年六月—宁宗崩后至元统元年六月
- 地点：静江、大都
- 行动：文宗后坚持迎立明宗长子，燕铁木儿因疑惧与太史异议拖延即位数月；燕铁木儿死后，皇后与大臣才定议立帝。
- 结果：妥懽帖睦尔结束数月待立并取得玺绶。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-038-DELAYED-SUCCESSION`
- 引文：子，禮當立之

### CHF-YUANSHI-038-ACCESSION-AMNESTY

- 时间：至顺四年六月己巳—至顺四年六月己巳
- 地点：上都、全国
- 行动：妥懽帖睦尔即位诏回顾继统依据，并宣布大赦天下。
- 结果：新朝施行即位赦令。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-038-ACCESSION-AMNESTY`
- 引文：平。其赦天下

### CHF-YUANSHI-038-EMPEROR-WITHDRAWS

- 时间：至顺四年六月—至顺四年六月
- 地点：宫中
- 行动：阿鲁辉帖木儿劝帝将天下事委任宰相，帝听从后深居宫中而不亲自决断。
- 结果：皇帝主动放弃日常专断，宰相权力扩大。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-038-EMPEROR-WITHDRAWS`
- 引文：天下事重，宜委宰相決之

### CHF-YUANSHI-038-PROMOTION-RESTRICTION

- 时间：元统元年九月甲寅—元统元年九月甲寅
- 地点：全国
- 行动：朝廷因官员递升妨碍选法，规定除省、院、台官外，其余官员不许递升。
- 结果：官员升迁渠道被收紧。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-038-PROMOTION-RESTRICTION`
- 引文：官員遞陞，窒礙選法

### CHF-YUANSHI-038-CHANCELLORS-CENTRALIZE

- 时间：元统元年九月至十一月—元统元年九月至十一月
- 地点：大都
- 行动：诏伯颜、撒敦专理国家大事，限制其余官员兼领三职，继而命二人统百官、总庶政。
- 结果：中枢政务集中于伯颜、撒敦。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-038-CHANCELLORS-CENTRALIZE`
- 引文：專理國家大事

### CHF-YUANSHI-038-YUANTONG-ERA

- 时间：元统元年十月戊辰—元统元年十月戊辰
- 地点：全国
- 行动：朝廷将至顺四年改称元统元年。
- 结果：新君建立元统年号。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-038-YUANTONG-ERA`
- 引文：其以至順四年為元統元年

### CHF-YUANSHI-038-NATIONWIDE-PRISON-REVIEW-1333

- 时间：元统元年十二月壬申—元统元年十二月壬申
- 地点：全国
- 行动：朝廷派省、台官分理天下囚案，明罪处决、冤者辨释、疑案复谳，并追究淹滞官员。
- 结果：全国刑狱获得分类复核和积案问责。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-038-NATIONWIDE-PRISON-REVIEW-1333`
- 引文：遣省、臺官分理天下囚

### CHF-YUANSHI-038-HUIZHENG-EXPANSION

- 时间：元统元年十二月乙亥—元统元年十二月乙亥
- 地点：大都
- 行动：朝廷为皇太后设置徽政院，置官属三百六十六员。
- 结果：皇太后宫政形成规模庞大的专门机构。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-038-HUIZHENG-EXPANSION`
- 引文：為皇太后置徽政院

### CHF-YUANSHI-038-EDUCATION-RESTORATION

- 时间：元统二年二月至三月—元统二年二月至三月
- 地点：全国
- 行动：朝廷要求内外兴办学校，并恢复科举、国子学积分与膳学钱粮、儒人免役等旧制。
- 结果：学校与科举财政制度按历朝旧制恢复。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-038-EDUCATION-RESTORATION`
- 引文：詔內外興舉學校

### CHF-YUANSHI-038-ETHNIC-CRIMINAL-JURISDICTION

- 时间：元统二年三月丁巳—元统二年三月丁巳
- 地点：全国
- 行动：朝廷规定蒙古、色目人的奸盗诈伪罪归宗正府，汉人、南人同罪归普通有司。
- 结果：刑事管辖按族群分流。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-038-ETHNIC-CRIMINAL-JURISDICTION`
- 引文：蒙古、色目犯奸盜詐偽之罪者，隸宗正府

### CHF-YUANSHI-038-MONGOL-THEFT-NO-TATTOO

- 时间：元统二年七月壬寅—元统二年七月壬寅
- 地点：全国
- 行动：朝廷规定蒙古、色目人犯盗罪免于刺字。
- 结果：盗罪附加刑按族群形成差别。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-038-MONGOL-THEFT-NO-TATTOO`
- 引文：蒙古、色目人犯盜者免刺

### CHF-YUANSHI-038-AGRICULTURAL-OFFICER-AUDIT

- 时间：至元元年正月癸巳—至元元年正月癸巳
- 地点：全国
- 行动：朝廷再命廉访司考察郡县劝农官勤惰，上报大司农司作为升黜依据。
- 结果：劝农官形成监察、考核与任免联动。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-038-AGRICULTURAL-OFFICER-AUDIT`
- 引文：察郡縣勸農官勤惰

### CHF-YUANSHI-038-REDUNDANT-OFFICES-AND-HUNT

- 时间：至元元年二月—至元元年二月
- 地点：大都、柳林
- 行动：朝廷裁革冗官；帝欲赴柳林狩猎，御史以民劳农忙及安全风险进谏，帝停止出猎。
- 结果：行政冗员被裁，扰民且危险的春猎被谏止。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-038-REDUNDANT-OFFICES-AND-HUNT`
- 引文：二月甲寅朔，革冗官

### CHF-YUANSHI-038-NATIONWIDE-PRISON-DECISIONS-1335

- 时间：至元元年三月癸未—至元元年三月癸未
- 地点：全国
- 行动：朝廷派五府官员巡行裁决天下囚犯。
- 结果：全国刑狱再次由中央跨机构复核。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-038-NATIONWIDE-PRISON-DECISIONS-1335`
- 引文：詔遣五府官決天下囚

### CHF-YUANSHI-038-NATIVE-CHIEFS-SURRENDER

- 时间：至元元年三月癸未—至元元年三月癸未
- 地点：平伐、都云、定云
- 行动：宝郎、天都虫等酋长归降，朝廷在当地恢复宣抚司并任用土酋为官。
- 结果：归降区域纳入带有土官参与的行政体系。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-038-NATIVE-CHIEFS-SURRENDER`
- 引文：酋長寶郎、天都蟲等來降

### CHF-YUANSHI-038-KOREA-CONSORT-SELECTION-BAN

- 时间：至元元年三月庚子—至元元年三月庚子
- 地点：高丽
- 行动：御史指出元廷屡赴高丽选取媵妾，导致女婴不举、成年女子不嫁，朝廷准予禁止。
- 结果：强制选女造成的社会伤害获得制度性制止。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-038-KOREA-CONSORT-SELECTION-BAN`
- 引文：屢遣使往選取媵妾

### CHF-YUANSHI-038-HISTORIES-AND-OFFICE-CUTS

- 时间：至元元年四月己卯至庚辰—至元元年四月己卯至庚辰
- 地点：大都
- 行动：朝廷命翰林国史院纂修历朝实录及后妃功臣列传，同时裁罢功德、典瑞、营缮等九类提举司。
- 结果：国家启动史书编纂并压缩一批宫廷机构。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-038-HISTORIES-AND-OFFICE-CUTS`
- 引文：纂修累朝實錄及后妃、功臣列傳

### CHF-YUANSHI-038-TANGQISHI-PURGE

- 时间：至元元年六月庚辰至七月—至元元年六月庚辰至七月
- 地点：大都、开平
- 行动：伯颜奏唐其势兄弟谋逆并诛杀，皇后先被幽禁后由伯颜杀死；继而不置左丞相，由伯颜独任右丞相。
- 结果：燕铁木儿家族及其皇后被清除，伯颜垄断中书权力。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-038-TANGQISHI-PURGE`
- 引文：唐其勢及其弟塔剌海謀逆，誅之

### CHF-YUANSHI-038-PLOT-AFTERMATH-AMNESTY

- 时间：至元元年七月乙巳至戊申—至元元年七月乙巳至戊申
- 地点：大都、全国
- 行动：朝廷罢免燕铁木儿、唐其势所举用官员，处死答里等并发布诏书清算其党，同时大赦天下。
- 结果：旧权臣网络遭系统清洗，伯颜因平乱获政治奖励。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-038-PLOT-AFTERMATH-AMNESTY`
- 引文：罷燕鐵木兒、唐其勢舉用之人

### CHF-YUANSHI-038-EUNUCH-CUTS

- 时间：至元元年九月庚子—至元元年九月庚子
- 地点：内府
- 行动：御史报告内府宦官由国初数人膨胀至千余，请求依旧制裁减以省费，朝廷采纳。
- 结果：宦官机构启动大规模裁冗。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-038-EUNUCH-CUTS`
- 引文：今內府執事不下千餘

### CHF-YUANSHI-038-WUSA-WUMENG-TRANSFER

- 时间：至元元年九月丙午—至元元年九月丙午
- 地点：乌撒、乌蒙、四川
- 行动：朝廷将乌撒、乌蒙地区改隶四川行省。
- 结果：两地行政军事归属从原体系转入四川。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-038-WUSA-WUMENG-TRANSFER`
- 引文：詔以烏撒、烏蒙之地隸四川行省

### CHF-YUANSHI-038-CENSOR-RESIGNATIONS

- 时间：至元元年十月—至元元年十月
- 地点：大都
- 行动：十九名监察御史弹劾彻里帖木儿未被采纳，除拒绝署名的陈允文外皆辞职。
- 结果：中枢拒绝弹劾引发监察官集体离任。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-038-CENSOR-RESIGNATIONS`
- 引文：十九人劾奏徹里帖木兒之罪，不聽

### CHF-YUANSHI-038-CIVIL-EXAMS-ABOLISHED

- 时间：至元元年十一月庚辰—至元元年十一月庚辰
- 地点：全国
- 行动：朝廷将儒学贡士庄田租拨给宿卫衣粮，并下诏停止科举。
- 结果：教育资产转供宿卫，科举取士中断。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-038-CIVIL-EXAMS-ABOLISHED`
- 引文：儒學貢士莊田租給宿衞衣糧

### CHF-YUANSHI-038-RECOMMENDATION-ABOLISHED

- 时间：至元元年十一月乙酉—至元元年十一月乙酉
- 地点：全国
- 行动：伯颜请求内外官一律按资历铨注，今后不得保举，朝廷准行。
- 结果：元统二年的举荐守令制度被改为循资选官。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-038-RECOMMENDATION-ABOLISHED`
- 引文：內外官悉循資銓注

### CHF-YUANSHI-038-KOREA-LANDS-RESTORED

- 时间：至元元年十一月甲午—至元元年十一月甲午
- 地点：高丽
- 行动：朝廷将燕铁木儿、唐其势、答里夺取的高丽田宅归还高丽王。
- 结果：被权臣侵夺的藩国财产得到返还。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-038-KOREA-LANDS-RESTORED`
- 引文：所奪高麗田宅

### CHF-YUANSHI-038-FALSELY-EXILED-OFFICIALS-RESTORED

- 时间：至元元年十一月戊戌—至元元年十一月戊戌
- 地点：大都
- 行动：两名曾谋诛燕铁木儿而遭诬贬的知枢密院事被召回京师平反。
- 结果：燕铁木儿时期的政治贬逐得到纠正。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-038-FALSELY-EXILED-OFFICIALS-RESTORED`
- 引文：謀誅燕鐵木兒，為所誣貶

### CHF-YUANSHI-038-ZHIYUAN-ERA-AND-GRANARIES

- 时间：至元元年十一月辛丑—至元元年十一月辛丑
- 地点：全国
- 行动：因星象示警，朝廷将元统三年改为至元元年、赦天下，并建立常平仓。
- 结果：新年号、赦令和粮价储备制度同时启动。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-038-ZHIYUAN-ERA-AND-GRANARIES`
- 引文：改元統三年仍為至元元年

### CHF-YUANSHI-038-CHELI-IMPEACHED-EXILED

- 时间：至元元年闰月戊戌至壬寅—至元元年闰月戊戌至壬寅
- 地点：大都、南安
- 行动：御史再次弹劾彻里帖木儿，朝廷终于罢免并流放南安。
- 结果：此前被拒的监察指控最终导致其去职远徙。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-038-CHELI-IMPEACHED-EXILED`
- 引文：復劾奏中書平章政事徹里帖木兒罪

### CHF-YUANSHI-038-MARRIED-MONKS-POLICY-REVERSAL

- 时间：至元元年岁末—至元元年岁末
- 地点：全国
- 行动：朝廷先令有妻室的僧人还俗为民，随后又准其恢复僧籍。
- 结果：僧侣婚姻资格政策在年内反复。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-038-MARRIED-MONKS-POLICY-REVERSAL`
- 引文：凡有妻室之僧，令還俗為民
