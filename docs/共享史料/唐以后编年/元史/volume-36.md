# 《元史》卷036四域同读视图

- 任务：`YUAN-YUANSHI-036-MULTIDOMAIN`
- 状态：`shadow`
- 固定修订：`1814433`
- 输入指纹：`2496e8b06c28fe7892741997ade07dad166cea59f5f6554d661f8569c36754c9`
- 共享事实：37
- 战役交接路由：5
- 财政民生路由：20
- 大型工程路由：3
- 政治事件路由：9
- 完整通读：完成（shadow；未写正式事实或评分）

## 战役交接

### CHF-YUANSHI-036-GUANGXI-RAIDS

- 时间：至顺三年正月己卯—至顺三年正月己卯
- 地点：广西、那马违、那马安
- 行动：马武冲等联合诸洞兵万人攻陷那马违、那马安等寨，朝廷命广西宣慰司严军防御。
- 结果：广西多寨失守，地方转入军事防御。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-GUANGXI-RAIDS-1332`
- 引文：蟲賊兵萬人

### CHF-YUANSHI-036-HAINAN-RAID-50000

- 时间：至顺三年正月戊子—至顺三年正月戊子
- 地点：万安军、陵水县
- 行动：黎众王奴罗等聚集五万人进攻陵水县。
- 结果：卷35海南动乱延续并扩大。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-HAINAN-LINGSHUI-1332`
- 引文：集眾五萬人寇陵水縣

### CHF-YUANSHI-036-SICHUAN-REINFORCEMENT-REQUEST

- 时间：至顺三年正月己丑—至顺三年正月己丑
- 地点：四川、重庆、叙州、顺元
- 行动：帖木儿不花战伤后贼军侵境，四川请求调兵二千五百救援；顺元又报敌设十六行营，请分道备御。
- 结果：川黔边区面临持续军情并提出增援防御方案。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-SICHUAN-REINFORCEMENT-1332`
- 引文：與祿余賊兵戰被創

### CHF-YUANSHI-036-YUNNAN-MILITARY-DISCRETION

- 时间：至顺三年二月戊申—至顺三年二月戊申
- 地点：会通州、会川路、大渡河、金沙江
- 行动：云南报告阿赛、阿勒等与罗罗军进攻卜龙村，禄余拟合兵攻东川、会通；朝廷准其先招谕、不服则便宜进军。
- 结果：云南行省获得招抚失败后自主进军权。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-YUNNAN-DISCRETION-1332`
- 引文：賊兵千五百人寇會川路之卜龍村

### CHF-YUANSHI-036-HAINAN-REINFORCEMENT

- 时间：至顺三年七月丁丑—至顺三年七月丁丑
- 地点：湖广、海南
- 行动：湖广以黎乱猖獗请求增兵三千，朝廷令依前诏催移剌四奴限日进兵。
- 结果：中央催促既定海南进讨，增兵请求是否获准未明。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-HAINAN-REINFORCEMENT-1332`
- 引文：黎賊勢猖獗

## 财政民生

### CHF-YUANSHI-036-CAPITAL-GRAIN-RELIEF-JAN

- 时间：至顺三年正月丁丑—至顺三年正月丁丑
- 地点：京师
- 行动：官府以五万石米实行赈糶，救济京师贫民。
- 结果：京城贫民获得平价粮食救济。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-036-CAPITAL-GRAIN-RELIEF-JAN`
- 引文：賑糶米五萬石，濟京師貧民

### CHF-YUANSHI-036-JAN-REGIONAL-RELIEF

- 时间：至顺三年正月癸未—至顺三年正月癸未
- 地点：永昌路、宜山县、梅州
- 行动：朝廷分别救济永昌流民，并准以军粮二百八十石赈糶宜山饥疫，又发粟七百石赈糶连年水旱的梅州。
- 结果：三处流民、饥疫与水旱灾民获得粮食救济。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-036-JAN-REGIONAL-RELIEF`
- 引文：賑永昌路流民

### CHF-YUANSHI-036-ANNUAL-CURRENCY

- 时间：至顺三年正月丙戌—至顺三年正月丙戌
- 地点：全国
- 行动：按岁额印造至元钞九十九万六千锭、中统钞四千锭。
- 结果：年度钞本发行额被确定。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-036-ANNUAL-CURRENCY`
- 引文：印造歲額鈔本

### CHF-YUANSHI-036-GAOYAO-FAMINE-RELIEF

- 时间：至顺三年正月己丑—至顺三年正月己丑
- 地点：肇庆路高要县
- 行动：官府赈济高要县饥民九千五百四十口。
- 结果：近万人获得灾荒救济。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-036-GAOYAO-FAMINE-RELIEF`
- 引文：賑肇慶路高要縣饑民九千五百四十口

### CHF-YUANSHI-036-DENING-RELIEF

- 时间：至顺三年二月己酉—至顺三年二月己酉
- 地点：德宁路
- 行动：德宁前遭旱灾又遇霜雹，朝廷以粟三千石赈济饥民。
- 结果：复合农业灾害获得粮食救济。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-036-DENING-RELIEF`
- 引文：去年旱，復值霜雹

### CHF-YUANSHI-036-QIONGZHOU-SALT-WELLS

- 时间：至顺三年二月己巳—至顺三年二月己巳
- 地点：邛州
- 行动：地震后金凤、茅池两井盐水涌溢，民人侯坤自备器具煮盐纳课，朝廷命四川转运盐司主管。
- 结果：新恢复的盐井生产被纳入官府税务管理。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-036-QIONGZHOU-SALT-WELLS`
- 引文：震，鹽水湧溢

### CHF-YUANSHI-036-MILITARY-FUNERAL-AND-POST-RELIEF

- 时间：至顺三年三月庚午—至顺三年三月庚午
- 地点：全国、四川
- 行动：朝廷规定远戍军官死亡归葬可按民官例给路费，并因军兴耗损命官会同行省救济四川驿户。
- 结果：远戍军官丧葬与战区驿户获得财政保障。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-036-MILITARY-FUNERAL-AND-POST-RELIEF`
- 引文：給道里之費

### CHF-YUANSHI-036-DIANSHAN-FIELDS-TRANSFER

- 时间：至顺三年三月庚午—至顺三年三月庚午
- 地点：平江、松江、淀山湖
- 行动：燕铁木儿请求接管被占耕的五百余顷圩田，将官粮由七千七百石增至一万石，并以余米供养其弟，获准。
- 结果：官田租额增加，但剩余收益转供权臣家属。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-036-DIANSHAN-FIELDS-TRANSFER`
- 引文：圩田方五百頃有奇

### CHF-YUANSHI-036-MONGOL-ORPHAN-GRANT

- 时间：至顺三年三月乙未—至顺三年三月乙未
- 地点：大都
- 行动：命燕铁木儿依旧例将钞一万锭分给蒙古孤寡。
- 结果：蒙古孤寡获得专项救济。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-036-MONGOL-ORPHAN-GRANT`
- 引文：以鈔萬錠分給蒙古孤寡者

### CHF-YUANSHI-036-POST-STATIONS-RELIEF

- 时间：至顺三年三月丙申—至顺三年三月丙申
- 地点：木怜、苦盐泺、札哈、扫怜
- 行动：朝廷赈济四处驿站贫困户共四百五十二户。
- 结果：交通驿户获得生活救济。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-036-POST-STATIONS-RELIEF`
- 引文：賑木憐、苦鹽濼、札哈、掃憐九驛之貧者

### CHF-YUANSHI-036-WUSA-WUMENG-MILITARY-FUND

- 时间：至顺三年三月己亥—至顺三年三月己亥
- 地点：乌撒、乌蒙、陕西、四川
- 行动：朝廷拨钞四万锭给行枢密院，分发征乌撒、乌蒙所调陕西四川蒙古军及渐丁万人。
- 结果：云贵战事获得万人规模军队的专项军费。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-036-WUSA-WUMENG-MILITARY-FUND`
- 引文：賜行樞密院鈔四萬錠

### CHF-YUANSHI-036-GUARD-PAY-ADJUSTMENT

- 时间：至顺三年四月壬寅—至顺三年四月壬寅
- 地点：大都
- 行动：宿卫给钞人数由一万五千减去一千四百，核定一万三千六百人；太府监岁支币帛不足又增二百匹。
- 结果：宿卫支出对象缩减，同时补充太府监物料。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-036-GUARD-PAY-ADJUSTMENT`
- 引文：今減去千四百人

### CHF-YUANSHI-036-SICHUAN-YUNNAN-TAX-RELIEF

- 时间：至顺三年四月乙丑—至顺三年四月乙丑
- 地点：四川、云南
- 行动：朝廷免四川行省本年租，又免云南行省田租三年。
- 结果：长期用兵地区获得一年至三年的税负减免。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-036-SICHUAN-YUNNAN-TAX-RELIEF`
- 引文：免四川行省境內今年租

### CHF-YUANSHI-036-ANZHOU-YUNNAN-FAMINE-RELIEF

- 时间：至顺三年四月至五月—至顺三年四月至五月
- 地点：安州、大理、中庆
- 行动：安州饥荒以河间盐课钞一万锭赈济；云南大理、中庆等路大饥又发钞十万锭。
- 结果：安州与云南重灾区以专项钞款救荒。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-036-ANZHOU-YUNNAN-FAMINE-RELIEF`
- 引文：安州饑，給河間鹽課鈔萬錠賑之

### CHF-YUANSHI-036-MAY-DISASTER-RELIEF

- 时间：至顺三年五月丁酉—至顺三年五月丁酉
- 地点：河间清州、常宁州、杭州、池州
- 行动：滹沱河决淹屯田四十三顷；常宁饥荒赈糶米二千四百石；杭州、池州火灾分别波及九十一与七十三户，命行省量赈。
- 结果：水、饥、火灾获得不同程度救济，屯田损失被记录。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-036-MAY-DISASTER-RELIEF`
- 引文：沒河間清州等處屯田四十三頃

### CHF-YUANSHI-036-YUNNAN-RESERVE-FUND

- 时间：至顺三年六月戊午—至顺三年六月戊午
- 地点：云南
- 行动：朝廷拨钞五万锭给云南行省作为公储。
- 结果：云南获得地方应急储备资金。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-036-YUNNAN-RESERVE-FUND`
- 引文：給鈔五萬錠，賜雲南行省為公儲

### CHF-YUANSHI-036-MONGOL-MILITARY-REFUGEE-RELIEF

- 时间：至顺三年七月丁丑—至顺三年七月丁丑
- 地点：陕西
- 行动：朝廷给流离至陕西的蒙古军四百六十七户三月粮，并遣返原居，每户另给钞五十锭。
- 结果：流离军户获得口粮、返乡与安置费。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-036-MONGOL-MILITARY-REFUGEE-RELIEF`
- 引文：四百六十七戶糧三月

### CHF-YUANSHI-036-JULY-FAMINE-RELIEF

- 时间：至顺三年七月甲午—至顺三年七月甲午
- 地点：滕州、庆都县
- 行动：滕州饥民获赈糶米二万石，庆都大饥则以河间盐课钞一万锭救济。
- 结果：两地以粮食和盐课收入分别救荒。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-036-JULY-FAMINE-RELIEF`
- 引文：滕州民饑，賑糶米二萬石

### CHF-YUANSHI-036-BAODI-GRAIN-RELIEF

- 时间：至顺三年八月辛丑—至顺三年八月辛丑
- 地点：大都宝坻县
- 行动：朝廷从京畿运司拨粮一万石赈济宝坻饥民。
- 结果：京畿饥区获得粮食救济。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-036-BAODI-GRAIN-RELIEF`
- 引文：賑大都寶坻縣饑民以京畿運司糧萬石

### CHF-YUANSHI-036-MARITIME-GRAIN-ARRIVAL

- 时间：至顺三年八月丁未—至顺三年八月丁未
- 地点：京师
- 行动：海道漕运粮六十九万余石抵达京师。
- 结果：海运粮完成入京。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-036-MARITIME-GRAIN-ARRIVAL`
- 引文：海道漕運糧六十九萬餘石至京師

## 大型工程

### CHF-YUANSHI-036-CONSTRUCTION-SUSPENSION

- 时间：至顺三年正月己卯—至顺三年正月己卯
- 地点：全国
- 行动：朝廷停罢各项建造工役，仅允许城郭、河渠、桥道与仓库继续施工。
- 结果：一般工程被裁停，防务、水利、交通和仓储工程保留。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `WORK-THREAD-YUANSHI-036-CONSTRUCTION-SUSPENSION`
- 引文：罷諸建造工役

### CHF-YUANSHI-036-SACRED-HALL-AND-CONFUCIUS-TEMPLE

- 时间：至顺三年二月己巳—至顺三年二月己巳
- 地点：大都、曲阜
- 行动：燕铁木儿奉命会集翰林等机构议建太祖神御殿，同时诏修曲阜宣圣庙。
- 结果：两项国家祭祀建筑分别进入议建与修缮。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `WORK-THREAD-YUANSHI-036-SACRED-HALL-AND-CONFUCIUS-TEMPLE`
- 引文：議立太祖神御殿

### CHF-YUANSHI-036-RELIGIOUS-BUILDING-FUNDS

- 时间：至顺三年五月辛卯—至顺三年五月辛卯
- 地点：大都
- 行动：朝廷拨钞五万锭修建帝师八思巴影殿。
- 结果：帝师纪念建筑获得大额官款。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `WORK-THREAD-YUANSHI-036-RELIGIOUS-BUILDING-FUNDS`
- 引文：給鈔五萬錠，修帝師巴思八影殿

## 政治事件

### CHF-YUANSHI-036-KOREA-KING-RESTORED

- 时间：至顺三年正月癸酉—至顺三年正月癸酉
- 地点：高丽
- 行动：王燾病愈后，朝廷命其复任高丽国王并赐金印，先前袭爵的王禎退位。
- 结果：高丽王位恢复至王燾。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-036-KOREA-KING-RESTORED`
- 引文：命高麗國王王燾仍為高麗國王

### CHF-YUANSHI-036-HUBEI-OFFICIALS-DISMISSED

- 时间：至顺三年正月己亥—至顺三年正月己亥
- 地点：荆湖北道
- 行动：别列怯都强迫百姓代偿内府借钞并动用公帑，驴驹借修堤纵奴敛财，御史奏请后两人均被黜退。
- 结果：两名地方长官因侵民与挪用公款被罢。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-036-HUBEI-OFFICIALS-DISMISSED`
- 引文：威逼部民代償

### CHF-YUANSHI-036-LUYU-SURRENDER-PROPOSAL

- 时间：至顺三年二月己酉—至顺三年二月己酉
- 地点：乌撒、永宁路
- 行动：禄余自称受伯忽胁迫，请求再降赦诏并允其四路土官归降、改隶四川永宁路，朝廷交中书、枢密、御史杂议。
- 结果：长期叛乱首领提出有条件归降，中央尚未裁决。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-036-LUYU-SURRENDER-PROPOSAL`
- 引文：乞再降詔赦

### CHF-YUANSHI-036-RELIGIOUS-AGENCIES-RESTORED

- 时间：至顺三年三月己丑至癸巳—至顺三年三月己丑至癸巳
- 地点：大都
- 行动：朝廷恢复功德使司，又设置正三品兴瑞司掌中宫每年佛事。
- 结果：宫廷佛事形成恢复和新增的专门机构。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-036-RELIGIOUS-AGENCIES-RESTORED`
- 引文：復立功德使司

### CHF-YUANSHI-036-CONSPIRACY-EXECUTIONS

- 时间：至顺三年四月乙丑—至顺三年四月乙丑
- 地点：大都
- 行动：月鲁帖木儿与两名僧人因谋不轨受宗王大臣杂鞫，三人伏诛并籍没家产，财产多归寺院及权臣。
- 结果：一宗皇族谋逆案完成处决和大规模财产没收。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-036-CONSPIRACY-EXECUTIONS`
- 引文：坐與畏兀僧玉你達八的剌板的、國師必剌忒納失里沙津愛護持謀不軌

### CHF-YUANSHI-036-ILLICIT-SHRINE-TITLES-BANNED

- 时间：至顺三年五月壬辰—至顺三年五月壬辰
- 地点：全国
- 行动：太常博士指出各地滥封淫祠，朝廷采纳礼典标准，禁止今后为不合祀典之神加封。
- 结果：地方神祠加封被纳入国家礼制限制。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-036-ILLICIT-SHRINE-TITLES-BANNED`
- 引文：廟，濫及淫祠

### CHF-YUANSHI-036-AMNESTY-AND-TAX-RELIEF

- 时间：至顺三年六月己亥—至顺三年六月己亥
- 地点：全国、四川、陕西
- 行动：朝廷就月鲁帖木儿案诏告中外并大赦天下，同时免四川本年差税、陕西本年商税。
- 结果：谋逆案后实施全国赦免并对两省减税。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-036-AMNESTY-AND-TAX-RELIEF`
- 引文：以月魯帖木兒等罪詔告中外，赦天下

### CHF-YUANSHI-036-EMPEROR-DEATH-BURIAL

- 时间：至顺三年八月己酉至癸丑—至顺三年八月己酉至癸丑
- 地点：上都、起辇谷
- 行动：文宗在位五年、二十九岁去世，灵驾随后发引并葬起辇谷。
- 结果：文宗统治终结并完成安葬。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-036-EMPEROR-DEATH-BURIAL`
- 引文：帝崩，壽二十有九，在位五年

### CHF-YUANSHI-036-POSTHUMOUS-TITLE-TEMPLE-REMOVAL

- 时间：元统二年至后至元六年—元统二年至后至元六年
- 地点：大都、高丽途中
- 行动：文宗获尊谥、庙号并祔太庙；后因谋害明宗被诏除庙主，其子燕帖古思被放高丽并在途中遇害。
- 结果：文宗身后合法性被撤销，皇子亦遭杀害。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-036-POSTHUMOUS-TITLE-TEMPLE-REMOVAL`
- 引文：帝，廟號文宗
