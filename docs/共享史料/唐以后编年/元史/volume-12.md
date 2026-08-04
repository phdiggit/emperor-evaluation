# 《元史》卷012四域同读视图

- 任务：`YUAN-YUANSHI-012-MULTIDOMAIN`
- 状态：`shadow`
- 固定修订：`1812923`
- 输入指纹：`1f6ee19c35c9934f7b340038770c67415e439d4b71d2f8c6f58bbc194f256942`
- 共享事实：40
- 战役交接路由：8
- 财政民生路由：17
- 大型工程路由：12
- 政治事件路由：15
- 完整通读：完成（shadow；未写正式事实或评分）

## 战役交接

### CHF-YUANSHI-012-XILIEJI-REBELLION

- 时间：至元十九年正月—至元十九年正月
- 地点：阿里麻里、海都辖境
- 行动：昔里吉等谋劫北平王叛乱并求援海都，撒里蛮悔过擒其同党。
- 结果：北平王控制得以恢复，叛乱首领被送报朝廷。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-XILIEJI-1282`
- 引文：謀劫皇子北平王以叛

### CHF-YUANSHI-012-YEKEBUSHUE-BURMA-WARS

- 时间：至元十九年二月至六月—至元十九年二月至六月
- 地点：也可不薛、緬國、烏蒙
- 行动：元廷调一万五千军征也可不薛、议发多路军征缅，并出军镇压乌蒙叛乱。
- 结果：西南多条战线同时推进，也可不薛最终平定设官驻军。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-SOUTHWEST-1282`
- 引文：調軍一萬五千、馬五千匹，征也可不薛

### CHF-YUANSHI-012-JIANGNAN-WARSHIPS-1000

- 时间：至元十九年二月—至元十九年二月
- 地点：乾山、江南
- 行动：派使赴乾山制造江南战船一千艘。
- 结果：海外战争继续推动大规模造船。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-OVERSEAS-NAVAL-PREP-1282`
- 引文：造江南戰船千艘

### CHF-YUANSHI-012-CHAMPA-EXPEDITION-1282

- 时间：至元十九年六月至二十年五月—至元十九年六月至二十年五月
- 地点：占城
- 行动：占城降而复叛，元廷发五千军及海战船三百五十艘征讨；后攻破占城，国主逃走。
- 结果：元军夺取占城都城但未擒国主，战事继续。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-CHAMPA-1282`
- 引文：占城既服復叛

### CHF-YUANSHI-012-JAPAN-BURDEN-DEBATE

- 时间：至元二十年四月至七月—至元二十年四月至七月
- 地点：江南、高麗、日本
- 行动：继续重建征东行省、征军造船；崔彧以拘水手造船致民不聊生与盗起请求暂缓，未获采纳，后才命造船稍缓并归还商船。
- 结果：征日准备继续，但民生压力最终促成局部缓工与还船。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-JAPAN-PREP-1283`
- 引文：皆緣拘水手、造海船，民不聊生

### CHF-YUANSHI-012-SHIP-LEVY-RELIEF

- 时间：至元二十年八月—至元二十年八月
- 地点：浙西、江南沿海
- 行动：原征日本船五百艘摊派民间致困，改修现有官船并给钞招募自愿水手。
- 结果：造船与水手征集从民间摊派转向修船和付费招募。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-JAPAN-PREP-1283`
- 引文：征日本船五百艘科諸民間，民病之

### CHF-YUANSHI-012-HUANGHUA-REBELLION

- 时间：至元二十年十月—至元二十年十月
- 地点：建寧、崇安、浦城
- 行动：黄华聚众近十万反叛并围建宁，元廷发二万二千军讨平。
- 结果：福建大规模叛乱被镇压。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-HUANGHUA-1283`
- 引文：叛，眾幾十萬

### CHF-YUANSHI-012-SHIZHOU-REBELLION

- 时间：至元二十年十二月—至元二十年十二月
- 地点：雲南施州、羅羅斯
- 行动：施州子童起兵为乱，元廷命阿合八失合罗罗斯军讨伐并给布万匹。
- 结果：云南地方叛乱进入军事镇压。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-SHIZHOU-1283`
- 引文：雲南施州子童興兵為亂

## 财政民生

### CHF-YUANSHI-012-GANSU-DESERTER-RESETTLEMENT

- 时间：至元十九年二月—至元十九年二月
- 地点：甘州
- 行动：二千二百逃军愿携家属四千九百余口返戍，朝廷给钞、布和驴。
- 结果：逃军家庭获资助后恢复戍役。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-012-GANSU-DESERTER-RESETTLEMENT`
- 引文：逃軍二千二百人

### CHF-YUANSHI-012-WAR-DEBT-AMNESTY-INTEREST-CAP

- 时间：至元十九年四月—至元十九年四月
- 地点：天下
- 行动：因海外战争供给繁重，暂缓逋欠钱粮和官吏侵盗追理，并规定民间借贷利息以三分为限。
- 结果：军需压力下实施债税缓征并建立利率上限。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-012-WAR-DEBT-AMNESTY-INTEREST-CAP`
- 引文：天下供給繁重

### CHF-YUANSHI-012-CORRUPTION-PROCEEDS-RELIEF

- 时间：至元十九年四月—至元十九年四月
- 地点：中央
- 行动：将现有赃罚钞三万锭及相当金银珠玉币帛留作救济贫乏者。
- 结果：反腐没收财产转用于社会救助。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-012-CORRUPTION-PROCEEDS-RELIEF`
- 引文：贓罰鈔三萬錠

### CHF-YUANSHI-012-SOUTHERN-SOLDIERS-FREED

- 时间：至元十九年六月—至元十九年六月
- 地点：江南
- 行动：亡宋军无论有无手号一律允许转为民籍，并招无籍军给衣粮。
- 结果：部分原宋军解除军籍，流散军人获得补给。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-012-SOUTHERN-SOLDIERS-FREED`
- 引文：亡宋軍有手號及無手號者，並聽為民

### CHF-YUANSHI-012-JIANGNAN-DROUGHT-RELIEF

- 时间：至元十九年八月至九月—至元十九年八月至九月
- 地点：江南、真定以南
- 行动：江南水灾、真定以南旱灾造成饥荒流移，命开仓赈济，并给流民粮食返乡。
- 结果：灾民获得粮赈与返乡资助。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-012-JIANGNAN-DROUGHT-RELIEF`
- 引文：江南水，民饑者眾

### CHF-YUANSHI-012-YUNNAN-REGISTRATION-TAX

- 时间：至元十九年九月—至元十九年九月
- 地点：雲南
- 行动：停止反复籍户扰民，只籍新附者；云南税赋以金为准并允许贝子折纳。
- 结果：云南户籍范围收紧，税制形成金贝折算标准。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-012-YUNNAN-REGISTRATION-TAX`
- 引文：凡八籍民戶，四籍民田，民以為病

### CHF-YUANSHI-012-SALT-CANAL-TREASURY-REFORM

- 时间：至元十九年十月—至元十九年十月
- 地点：大都至中灤、中灤至瓜州
- 行动：整治钞法，设南北两漕运司和五处盐使司，并将宫廷出纳分为内藏、右藏、左藏三库。
- 结果：漕运、盐政和宫廷财库形成分工体系。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：詔整治鈔法

### CHF-YUANSHI-012-DROUGHT-TAX-SUSPENSION

- 时间：至元二十年正月—至元二十年正月
- 地点：燕南、河北、山東
- 行动：因上年旱灾暂停在民税粮，规定灾情迟报的管民官和不及时查验的按察司治罪。
- 结果：灾民获缓征，灾情申报责任得到制度化。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-012-DROUGHT-TAX-SUSPENSION`
- 引文：去歲旱，稅糧之在民者，權停勿徵

### CHF-YUANSHI-012-GARRISON-ROTATION-FAMILY-SUPPORT

- 时间：至元二十年二月—至元二十年二月
- 地点：兩廣、四川
- 行动：规定两广、四川戍军二三年轮换，官府供养家属并给军官俸禄。
- 结果：长期戍边形成轮换和家庭保障制度。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-012-GARRISON-ROTATION-FAMILY-SUPPORT`
- 引文：定兩廣、四川戍軍二三年一更，廩其家屬，軍官給俸以贍之

### CHF-YUANSHI-012-JAPAN-BURDEN-DEBATE

- 时间：至元二十年四月至七月—至元二十年四月至七月
- 地点：江南、高麗、日本
- 行动：继续重建征东行省、征军造船；崔彧以拘水手造船致民不聊生与盗起请求暂缓，未获采纳，后才命造船稍缓并归还商船。
- 结果：征日准备继续，但民生压力最终促成局部缓工与还船。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：皆緣拘水手、造海船，民不聊生

### CHF-YUANSHI-012-JIANGNAN-TAX-TWO-THIRDS

- 时间：至元二十年五月—至元二十年五月
- 地点：江南
- 行动：免除江南税粮三分之二，并要求军需按民力、实付物价和自愿招募水手的建议虽未停止征日但形成减负背景。
- 结果：江南获得大幅度年度税粮减免。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-012-JIANGNAN-TAX-TWO-THIRDS`
- 引文：免江南稅糧三之二

### CHF-YUANSHI-012-MARITIME-TAX-RULE

- 时间：至元二十年六月—至元二十年六月
- 地点：市舶诸港
- 行动：制定市舶抽分例，货物原则按十分之一抽取。
- 结果：海外贸易实物税率形成统一规则。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-012-MARITIME-TAX-RULE`
- 引文：定市舶抽分例

### CHF-YUANSHI-012-SONG-SOLDIER-REGISTRATION

- 时间：至元二十年六月—至元二十年六月
- 地点：江南
- 行动：将所括原宋手号军八万三千六百人编立牌甲、设官统领并给衣粮。
- 结果：大量新附军被正式编组纳入元军。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：所括宋手號軍八萬三千六百人

### CHF-YUANSHI-012-SHIP-LEVY-RELIEF

- 时间：至元二十年八月—至元二十年八月
- 地点：浙西、江南沿海
- 行动：原征日本船五百艘摊派民间致困，改修现有官船并给钞招募自愿水手。
- 结果：造船与水手征集从民间摊派转向修船和付费招募。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-012-SHIP-LEVY-RELIEF`
- 引文：征日本船五百艘科諸民間，民病之

### CHF-YUANSHI-012-VOLUNTARY-HUAINAN-SETTLEMENT

- 时间：至元二十年十月—至元二十年十月
- 地点：淮南、江南诸郡
- 行动：纠正押亦迷失跨郡强收民户种淮南田，规定只能在治所自愿招募、不得强迫。
- 结果：移民垦殖从强制转为本地公开招募。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-012-VOLUNTARY-HUAINAN-SETTLEMENT`
- 引文：往各郡轉收民戶

### CHF-YUANSHI-012-YUNNAN-DEBT-SLAVERY-RESTRAINT

- 时间：至元二十年十一月—至元二十年十一月
- 地点：雲南
- 行动：禁止云南课官额外取钱、权势者多取债息、没人口为奴及黥面。
- 结果：地方税外收费、高利贷和债务奴役受到集中限制。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-012-YUNNAN-DEBT-SLAVERY-RESTRAINT`
- 引文：禁雲南管課官於常額外多取餘錢

### CHF-YUANSHI-012-YEAR20-POST-AND-FAMINE-RELIEF

- 时间：至元二十年十二月—至元二十年十二月
- 地点：水達達四十九站、女直
- 行动：发粟赈济水达达四十九站，并赈女直饥民一千户。
- 结果：边地驿站和女直灾户获得粮食救济。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-012-YEAR20-POST-AND-FAMINE-RELIEF`
- 引文：發粟賑水達達四十九站

## 大型工程

### CHF-YUANSHI-012-ASTRONOMY-PALACE-WORKS

- 时间：至元十九年二月—至元十九年二月
- 地点：大都
- 行动：制作铜轮仪表刻漏，并修宫城、太庙与司天台。
- 结果：天文计时设施和中央礼制宫城同步修缮。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `WORK-THREAD-YUANSHI-012-ASTRONOMY-PALACE-WORKS`
- 引文：製飾銅輪儀表刻漏

### CHF-YUANSHI-012-JIANGNAN-WARSHIPS-1000

- 时间：至元十九年二月—至元十九年二月
- 地点：乾山、江南
- 行动：派使赴乾山制造江南战船一千艘。
- 结果：海外战争继续推动大规模造船。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：造江南戰船千艘

### CHF-YUANSHI-012-OFFICIAL-CARRIAGES-NO-LEVY

- 时间：至元十九年四月—至元十九年四月
- 地点：濼河
- 行动：规定官用车辆不得再向民间征取，改在泺河制造并由官给粮费。
- 结果：官府运输工具从摊派转为官造供给。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `WORK-THREAD-YUANSHI-012-OFFICIAL-CARRIAGES-NO-LEVY`
- 引文：自今歲用官車，勿賦於民

### CHF-YUANSHI-012-PINGLUAN-SHIPBUILDING

- 时间：至元十九年五月—至元十九年五月
- 地点：平灤州
- 行动：议在平滦造船，征军民九千伐木，并允许从山林寺观坟墓取材但官给价。
- 结果：大型造船获得劳力木材，同时以付价形式补偿。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `WORK-THREAD-YUANSHI-012-PINGLUAN-SHIPBUILDING`
- 引文：發軍民合九千人

### CHF-YUANSHI-012-ASTABUSU-EARTH-WALL

- 时间：至元十九年七月—至元十九年七月
- 地点：阿失答不速
- 行动：原议筑皇城需木十二万且运输困难，改采察罕脑儿做法筑土墙。
- 结果：工程方案因材料运输成本改为土筑。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `WORK-THREAD-YUANSHI-012-ASTABUSU-EARTH-WALL`
- 引文：用木十二萬，地遠難致

### CHF-YUANSHI-012-JICHUAN-RIVER-DREDGE

- 时间：至元十九年十二月—至元十九年十二月
- 地点：濟川河
- 行动：疏浚济川河。
- 结果：当地水运河道得到整治。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `WORK-THREAD-YUANSHI-012-JICHUAN-RIVER-DREDGE`
- 引文：之。浚濟川河

### CHF-YUANSHI-012-SHIP-TIMBER-BURDEN-RELOCATION

- 时间：至元二十年正月至五月—至元二十年正月至五月
- 地点：平灤、陽河
- 行动：造船伐木十四万余、征军贴户五千和民夫三千运输；因平滦距木源远、民疲于役，改在阳河造船，后放部分造船军归耕。
- 结果：造船工程因运输民困迁址并部分轮换劳力。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `WORK-THREAD-YUANSHI-012-SHIP-TIMBER-BURDEN-RELOCATION`
- 引文：伐船材于烈堝都山、乾山凡十四萬二千有奇

### CHF-YUANSHI-012-STOP-40000-LABOR-PROJECTS

- 时间：至元二十年三月—至元二十年三月
- 地点：平灤、五臺山、南城
- 行动：御史指出造船建寺伐木役四万人，朝廷立即停止伐木建寺，造船另议。
- 结果：大型宗教工程因役重被叫停，但军船工程未立即终止。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `WORK-THREAD-YUANSHI-012-STOP-40000-LABOR-PROJECTS`
- 引文：凡役四萬人，乞罷之

### CHF-YUANSHI-012-JAPAN-BURDEN-DEBATE

- 时间：至元二十年四月至七月—至元二十年四月至七月
- 地点：江南、高麗、日本
- 行动：继续重建征东行省、征军造船；崔彧以拘水手造船致民不聊生与盗起请求暂缓，未获采纳，后才命造船稍缓并归还商船。
- 结果：征日准备继续，但民生压力最终促成局部缓工与还船。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：皆緣拘水手、造海船，民不聊生

### CHF-YUANSHI-012-JISHAN-CANAL-COMPLETION

- 时间：至元二十年五月至八月—至元二十年五月至八月
- 地点：神山河、濟州
- 行动：江南粮运改走新开神山河及海道；济州新开河完工并设都漕运司。
- 结果：新河道投入漕运并形成专门管理机构。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `WORK-THREAD-YUANSHI-012-JISHAN-CANAL-COMPLETION`
- 引文：於阿八赤新開神山河及海道兩道運之

### CHF-YUANSHI-012-SHIP-LEVY-RELIEF

- 时间：至元二十年八月—至元二十年八月
- 地点：浙西、江南沿海
- 行动：原征日本船五百艘摊派民间致困，改修现有官船并给钞招募自愿水手。
- 结果：造船与水手征集从民间摊派转向修船和付费招募。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：征日本船五百艘科諸民間，民病之

### CHF-YUANSHI-012-EAST-A-RIVER-POSTS

- 时间：至元二十年十月—至元二十年十月
- 地点：東阿、御河、濟州、魯橋鎮
- 行动：设东阿至御河水陆驿并迁济州潭口驿至新河鲁桥镇。
- 结果：新河漕运获得配套驿站网络。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `WORK-THREAD-YUANSHI-012-EAST-A-RIVER-POSTS`
- 引文：立東阿至御河水陸驛，以便遞運

## 政治事件

### CHF-YUANSHI-012-XILIEJI-REBELLION

- 时间：至元十九年正月—至元十九年正月
- 地点：阿里麻里、海都辖境
- 行动：昔里吉等谋劫北平王叛乱并求援海都，撒里蛮悔过擒其同党。
- 结果：北平王控制得以恢复，叛乱首领被送报朝廷。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：謀劫皇子北平王以叛

### CHF-YUANSHI-012-YEKEBUSHUE-BURMA-WARS

- 时间：至元十九年二月至六月—至元十九年二月至六月
- 地点：也可不薛、緬國、烏蒙
- 行动：元廷调一万五千军征也可不薛、议发多路军征缅，并出军镇压乌蒙叛乱。
- 结果：西南多条战线同时推进，也可不薛最终平定设官驻军。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：調軍一萬五千、馬五千匹，征也可不薛

### CHF-YUANSHI-012-MILITARY-SUCCESSION-LAW

- 时间：至元十九年二月—至元十九年二月
- 地点：诸军
- 行动：制定军官承袭规则：阵亡者子袭职，病故者之子降一等授官。
- 结果：军职世袭按死亡原因形成差等。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-012-MILITARY-SUCCESSION-LAW`
- 引文：軍官陣亡者，其子襲職

### CHF-YUANSHI-012-AHAMAT-ASSASSINATION-PURGE

- 时间：至元十九年三月至六月—至元十九年三月至六月
- 地点：大都、中央
- 行动：王著等杀阿合马后被诛；朝廷随即封籍其府库，追治阿合马及亲党，裁黜大批官员与机构。
- 结果：阿合马政治财政网络遭系统清算。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-012-AHAMAT-ASSASSINATION-PURGE`
- 引文：以阿合馬蠹國害民，與高和尚合謀殺之

### CHF-YUANSHI-012-RETURN-SLAVES-LAND

- 时间：至元十九年四月—至元十九年四月
- 地点：江南等地
- 行动：将阿里海牙占为奴的降民归还官府，核还阿合马侵占民田原主，并放其奴婢为民。
- 结果：权臣将领侵占的人口和土地获得复原。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-012-RETURN-SLAVES-LAND`
- 引文：降民還之有司

### CHF-YUANSHI-012-SALT-CANAL-TREASURY-REFORM

- 时间：至元十九年十月—至元十九年十月
- 地点：大都至中灤、中灤至瓜州
- 行动：整治钞法，设南北两漕运司和五处盐使司，并将宫廷出纳分为内藏、右藏、左藏三库。
- 结果：漕运、盐政和宫廷财库形成分工体系。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-012-SALT-CANAL-TREASURY-REFORM`
- 引文：詔整治鈔法

### CHF-YUANSHI-012-SICHUAN-BUREAUCRACY-REDUCTION

- 时间：至元十九年十月至二十年二月—至元十九年十月至二十年二月
- 地点：四川
- 行动：四川仅十二万户却有官府二百五十余，朝廷连续裁并宣慰司、万户府和安抚司。
- 结果：四川征服后过密官署大幅收缩。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-012-SICHUAN-BUREAUCRACY-REDUCTION`
- 引文：四川民僅十二萬戶，所設官府二百五十餘

### CHF-YUANSHI-012-WEN-TIANXIANG-EXECUTION

- 时间：至元十九年十二月—至元十九年十二月
- 地点：大都
- 行动：因匿名告变事件，元廷处死原宋丞相文天祥。
- 结果：南宋重要抵抗象征被处决。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-012-WEN-TIANXIANG-EXECUTION`
- 引文：上匿名書告變

### CHF-YUANSHI-012-ANONYMOUS-ACCUSATION-LAW

- 时间：至元二十年正月—至元二十年正月
- 地点：天下
- 行动：查明薛宝住匿名告变为妄言后诛之，规定诉事实名赴省台，匿名告事重者死、轻者流。
- 结果：实名申诉与登闻鼓形成正式路径，匿名告发受到严惩。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-012-ANONYMOUS-ACCUSATION-LAW`
- 引文：賞。」敕誅之。又

### CHF-YUANSHI-012-AGRICULTURE-OFFICE-GRIEVANCE-LADDER

- 时间：至元二十年正月—至元二十年正月
- 地点：中央
- 行动：设置务农司，并规定诉事先赴省台，裁决不平者可击登闻鼓。
- 结果：农业管理与分级申诉制度同时落地。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-012-AGRICULTURE-OFFICE-GRIEVANCE-LADDER`
- 引文：之。設務農司

### CHF-YUANSHI-012-DROUGHT-TAX-SUSPENSION

- 时间：至元二十年正月—至元二十年正月
- 地点：燕南、河北、山東
- 行动：因上年旱灾暂停在民税粮，规定灾情迟报的管民官和不及时查验的按察司治罪。
- 结果：灾民获缓征，灾情申报责任得到制度化。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：去歲旱，稅糧之在民者，權停勿徵

### CHF-YUANSHI-012-JAPAN-BURDEN-DEBATE

- 时间：至元二十年四月至七月—至元二十年四月至七月
- 地点：江南、高麗、日本
- 行动：继续重建征东行省、征军造船；崔彧以拘水手造船致民不聊生与盗起请求暂缓，未获采纳，后才命造船稍缓并归还商船。
- 结果：征日准备继续，但民生压力最终促成局部缓工与还船。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：皆緣拘水手、造海船，民不聊生

### CHF-YUANSHI-012-DEATH-PENALTY-CENTRAL-REVIEW

- 时间：至元二十年五月—至元二十年五月
- 地点：雲南
- 行动：取消云南重囚便宜处决，规定所有大辟必须待中央批复。
- 结果：边地死刑重新纳入中央复核。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-012-DEATH-PENALTY-CENTRAL-REVIEW`
- 引文：恐濫及無辜

### CHF-YUANSHI-012-SONG-SOLDIER-REGISTRATION

- 时间：至元二十年六月—至元二十年六月
- 地点：江南
- 行动：将所括原宋手号军八万三千六百人编立牌甲、设官统领并给衣粮。
- 结果：大量新附军被正式编组纳入元军。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-012-SONG-SOLDIER-REGISTRATION`
- 引文：所括宋手號軍八萬三千六百人

### CHF-YUANSHI-012-YUNNAN-DEBT-SLAVERY-RESTRAINT

- 时间：至元二十年十一月—至元二十年十一月
- 地点：雲南
- 行动：禁止云南课官额外取钱、权势者多取债息、没人口为奴及黥面。
- 结果：地方税外收费、高利贷和债务奴役受到集中限制。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：禁雲南管課官於常額外多取餘錢
