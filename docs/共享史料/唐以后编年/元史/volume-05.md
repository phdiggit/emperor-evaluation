# 《元史》卷005四域同读视图

- 任务：`YUAN-YUANSHI-005-MULTIDOMAIN`
- 状态：`shadow`
- 固定修订：`2201384`
- 输入指纹：`f982f1db8aafb4a840fb64751e1b884e6dfbdfea088b448e6f0409a9cc470285`
- 共享事实：37
- 战役交接路由：7
- 财政民生路由：18
- 大型工程路由：6
- 政治事件路由：15
- 完整通读：完成（shadow；未写正式事实或评分）

## 战役交接

### CHF-YUANSHI-005-LITAN-REBELLION-OUTBREAK

- 时间：中统三年二月—中统三年二月
- 地点：漣州、海州、益都、濟南
- 行动：李璮杀蒙古戍军，以涟海三城降宋，进入益都发府库犒军并占据济南；王文统因同谋被诛。
- 结果：山东发生大规模叛乱，朝廷中央同谋遭清洗。
- 代价：蒙古戍军被杀，数量未载。
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-LITAN-REBELLION-1262`
- 引文：李璮反，以漣、海三城獻于宋

### CHF-YUANSHI-005-LITAN-MOBILIZATION

- 时间：中统三年二月至三月—中统三年二月至三月
- 地点：山東、燕京、河南、平陽、太原
- 行动：朝廷发蒙古汉军讨李璮，诸路会师济南，强征民兵、逃军、宗教与匠户等户丁，并设置山东行省和多处宣慰机构。
- 结果：形成围剿李璮的跨路军政动员体系。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-LITAN-REBELLION-1262`
- 引文：發諸蒙古、漢軍討李璮

### CHF-YUANSHI-005-LITAN-FIELD-DEFEATS

- 时间：中统三年三月—中统三年三月
- 地点：濟南、高苑
- 行动：史枢、阿术赴济南途中邀击李璮军，斩首四千；韩世安等又在高苑击败叛军并俘傅珪。
- 结果：李璮退守济南，外围军队连续失利。
- 代价：叛军至少四千人被斩。
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-LITAN-REBELLION-1262`
- 引文：邀擊大破之，斬首四千

### CHF-YUANSHI-005-JINAN-SIEGE

- 时间：中统三年四月至七月—中统三年四月至七月
- 地点：濟南、大明湖
- 行动：官军树栅掘壕包围济南，五月筑环城使李璮不得出；七月李璮投大明湖被俘，与囊家一同伏诛并分尸示众。
- 结果：济南围城结束，李璮叛乱主力覆灭。
- 代价：围城双方伤亡与城内饥困未载。
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-LITAN-REBELLION-1262`
- 引文：樹柵鑿塹，圍璮于濟南

### CHF-YUANSHI-005-REBUILD-BORDER-CITIES

- 时间：中统三年十月至十二月—中统三年十月至十二月
- 地点：宿州、蘄縣、邳州、息州
- 行动：命万户修复宿州、蕲县、邳州城郭，并复立息州城安民。
- 结果：宋元边区数座城防获得恢复。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-SONG-BORDER-1262`
- 引文：修復宿州、蘄縣

### CHF-YUANSHI-005-ARIQ-SURRENDER

- 时间：至元元年七月—至元元年七月
- 地点：上都
- 行动：阿里不哥战败后与诸王来归；忽必烈释放太祖后裔诸王，不追究其罪，但处死不鲁花等谋臣。
- 结果：皇位内战结束，宗室获宽赦，核心谋臣被诛。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-SUCCESSION-WAR-1260`
- 引文：阿里不哥自昔木土之敗，不復能軍

### CHF-YUANSHI-005-GUWEI-EXPEDITION

- 时间：至元元年十一月—至元元年十一月
- 地点：骨嵬、吉里迷
- 行动：因吉里迷称骨嵬、亦里于岁侵其境，元廷发兵征骨嵬。
- 结果：东北海外方向军事行动启动，战果未载。
- 代价：未载
- 路由：`HANDOFF_BATTLE_WORKFLOW` → `CAMPAIGN-YUAN-GUWEI-1264`
- 引文：吉里迷內附

## 财政民生

### CHF-YUANSHI-005-DEBT-SUSPENSION-1262

- 时间：中统三年正月—中统三年正月
- 地点：诸路
- 行动：因军兴人民劳苦，朝廷停止追征公私逋负，并罢忽剌忽儿部上供羊。
- 结果：战时债务追征暂停，饥困部民的上供负担减少。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-005-DEBT-SUSPENSION-1262`
- 引文：以軍興人民勞苦

### CHF-YUANSHI-005-MILITARY-GRAIN-AND-POOR-SOLDIERS

- 时间：中统三年正月—中统三年正月
- 地点：北京、河南
- 行动：增价籴米三万石饷诸王军，命军官考察匠户军贫富并存恤无力者，另禁戍兵势家牲畜践踏农作物。
- 结果：北方军粮增加，贫困军户获原则性救助，农田受到禁牧保护。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-005-MILITARY-GRAIN-AND-POOR-SOLDIERS`
- 引文：增價糴米三萬石益之

### CHF-YUANSHI-005-LITAN-MOBILIZATION

- 时间：中统三年二月至三月—中统三年二月至三月
- 地点：山東、燕京、河南、平陽、太原
- 行动：朝廷发蒙古汉军讨李璮，诸路会师济南，强征民兵、逃军、宗教与匠户等户丁，并设置山东行省和多处宣慰机构。
- 结果：形成围剿李璮的跨路军政动员体系。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：發諸蒙古、漢軍討李璮

### CHF-YUANSHI-005-LITAN-AMNESTIES

- 时间：中统三年四月至十月—中统三年四月至十月
- 地点：博興、高苑、益都、濟南
- 行动：朝廷数次赦免被李璮胁从的军民，禁官军掠夺，并令被掠民马归还原主。
- 结果：多数胁从者免罪，部分被掠财产获得返还原则。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：嘗為李璮脅從者，並釋其罪

### CHF-YUANSHI-005-AGRICULTURE-PROTECTION-1262

- 时间：中统三年四月至五月—中统三年四月至五月
- 地点：徐州、邳州、益都、诸路
- 行动：命安辑徐邳民，禁止军士势官纵畜伤禾；劝百姓垦田植桑枣，不得兴不急之役妨农时，并在益都禁军剽掠。
- 结果：战区恢复以护农、开垦和限制额外徭役为原则。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-005-AGRICULTURE-PROTECTION-1262`
- 引文：禁征戍軍士及勢官，毋縱畜牧傷其禾稼桑棗

### CHF-YUANSHI-005-WARTIME-TAX-RELIEF-1262

- 时间：中统三年三月至五月—中统三年三月至五月
- 地点：西京、北京、廣寧、懿州、濱棣、東平
- 行动：免西京丝银税，免北京广宁等军兴地区当年税赋，滨棣减田租一半、东平减三成。
- 结果：多处战乱地区获得不同幅度税免。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-005-WARTIME-TAX-RELIEF-1262`
- 引文：免西京今年絲銀稅

### CHF-YUANSHI-005-SILK-SILVER-RELIEF

- 时间：中统三年三月至七月—中统三年三月至七月
- 地点：诸路、西京
- 行动：免当年丝银、仅征田租，西京同免丝银；后恢复蒙古军站户差赋，但农民包银减半、俘户仅输丝。
- 结果：春季普遍减征，七月按户类重定赋役。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-005-SILK-SILVER-RELIEF`
- 引文：免今歲絲銀，止輸田租

### CHF-YUANSHI-005-EASTPING-DEBT-FORGIVENESS

- 时间：中统三年六月—中统三年六月
- 地点：東平
- 行动：严忠济此前为民借钱输赋四十三万七千四百锭，并借用课程、钞本和盐课银一万五千余两，朝廷下令不再追征。
- 结果：东平巨额代民输赋债务与公款借用获豁免。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-005-EASTPING-DEBT-FORGIVENESS`
- 引文：為民貸錢輸賦四十三萬七千四百錠

### CHF-YUANSHI-005-JINAN-FAMINE-RELIEF

- 时间：中统三年闰九月—中统三年闰九月
- 地点：濟南
- 行动：济南民饥，朝廷免赋并发粟三十万石赈济。
- 结果：刚经历围城的济南获得大额粮赈与税免。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-005-JINAN-FAMINE-RELIEF`
- 引文：濟南民饑，免其賦稅

### CHF-YUANSHI-005-DEMOBILIZATION-1262

- 时间：中统三年十月—中统三年十月
- 地点：金州、大名、河南、平陽
- 行动：释放金州屯军二千、大名河南新签防城军及平阳军九百一十五人为民，并免军户其他徭役。
- 结果：至少二千九百余名军人及未载数量的新签军复归民籍。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-005-DEMOBILIZATION-1262`
- 引文：放金州所屯軍士二千人

### CHF-YUANSHI-005-HUAI-NEW-FARMERS

- 时间：中统三年十一月至十二月—中统三年十一月至十二月
- 地点：應州、懷州
- 行动：河西移民中不能自给的160户获牛具、种子和布；怀州新民获耕牛二百头种水田。
- 结果：移民和新民获得恢复农业生产的实物资本。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-005-HUAI-NEW-FARMERS`
- 引文：不能自贍者百六十戶，給牛具及粟麥種

### CHF-YUANSHI-005-YEAR4-TAX-AND-IRON

- 时间：中统四年正月至五月—中统四年正月至五月
- 地点：诸路、河南、东平
- 行动：诸路包银改以钞缴，丝料本色或以钞折纳；清查漏附籍户起冶，后设铁冶年输铁并铸农器二十万件换粟四万石。
- 结果：户税货币化规则明确，官营铁业与农器粮食交换扩大。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-005-YEAR4-TAX-AND-IRON`
- 引文：諸路包銀以鈔輸納

### CHF-YUANSHI-005-PINGZHUN-WAREHOUSES

- 时间：中统四年五月至至元元年正月—中统四年五月至至元元年正月
- 地点：燕京、诸路
- 行动：在燕京设平准库以平物价、通钞法，至元元年扩设诸路平准库。
- 结果：价格调节与纸币流通机构由首都推广全国。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-005-PINGZHUN-WAREHOUSES`
- 引文：立燕京平準庫

### CHF-YUANSHI-005-DROUGHT-TAX-RELIEF-1263

- 时间：中统四年八月至十一月—中统四年八月至十一月
- 地点：彰德、洺州、磁州、東平、大名
- 行动：彰德旱免田租一半，洺磁免六成；后因岁歉与旱灾减军粮和田租。
- 结果：受旱地区获得按比例税粮减免。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-005-DROUGHT-TAX-RELIEF-1263`
- 引文：免彰德今歲田租之半

### CHF-YUANSHI-005-XILIANG-RELIEF

- 时间：中统四年八月—中统四年八月
- 地点：西涼
- 行动：西凉经兵后居民困弊，朝廷发钞赈济、免租赋三年，并规定流民复业者复其家三年。
- 结果：西凉战后居民与返乡流民获得三年税役恢复期。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-005-XILIANG-RELIEF`
- 引文：西涼經兵，居民困弊

### CHF-YUANSHI-005-ZHIYUAN-REFORM-EDICT

- 时间：至元元年八月—至元元年八月
- 地点：诸路
- 行动：阿里不哥归降后改元至元并大赦，颁行省并县、定员品秩俸禄公田、考课、均役、招流民、禁擅科与官物私用、恤孤劝农平价等综合条格。
- 结果：内战后全国行政、财政、民政与监察规则集中重建。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：改中統五年為至元元年

### CHF-YUANSHI-005-PRINCELY-ENVOY-LIMITS-1264

- 时间：至元元年八月—至元元年八月
- 地点：诸路
- 行动：统一诸王使臣的驿传、税赋、差发规则，禁止擅招民户、向非投下人放斡脱银、口传敕旨和追呼省臣属官；站户限田四顷免税。
- 结果：宗王使臣特权受到制度约束，站户免税田额明确。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：不許擅招民戶

### CHF-YUANSHI-005-FLOOD-1264

- 时间：至元元年—至元元年
- 地点：真定、順天、大名、東平、濟南、河間等
- 行动：真定、顺天、大名、东平、济南、河间等二十余州路发生大水。
- 结果：广泛水灾被记录，但本卷未载专项赈免。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `FIN-THREAD-YUANSHI-005-FLOOD-1264`
- 引文：真定、順天、洺、磁、順德、大名、東平、曹、濮州、泰安、高唐、濟州、博州、德州、濟南、濱、棣、淄、萊、河間大水

## 大型工程

### CHF-YUANSHI-005-BAOSHAN-WATER-CLOCK

- 时间：中统三年二月—中统三年二月
- 地点：寶山、燕京
- 行动：郭守敬制造宝山漏刻完成，并迁至燕京。
- 结果：新制计时仪器进入燕京使用。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `WORK-THREAD-YUANSHI-005-BAOSHAN-WATER-CLOCK`
- 引文：郭守敬造寶山漏成，徙至燕京

### CHF-YUANSHI-005-POST-AND-TRANSPORT-1262

- 时间：中统三年三月至闰九月—中统三年三月至闰九月
- 地点：燕京、濟南、開平、古北口
- 行动：燕京至济南设八处海青驿，燕京至开平设牛驿并官给钞购车牛，随后又设多处驿站。
- 结果：平叛和北方交通形成连续驿运节点。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `WORK-THREAD-YUANSHI-005-POST-AND-TRANSPORT-1262`
- 引文：燕京至濟南置海青驛凡八所

### CHF-YUANSHI-005-IRONWORKS-1262

- 时间：中统三年六月—中统三年六月
- 地点：小峪、蘆子、寧武軍、赤泥泉
- 行动：新设小峪、芦子、宁武军、赤泥泉四处铁冶，并令宁武军岁输所产铁。
- 结果：北方官营铁冶体系扩张。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `WORK-THREAD-YUANSHI-005-IRONWORKS-1262`
- 引文：歲輸所產鐵

### CHF-YUANSHI-005-GUANGJI-YUQUAN-CANALS

- 时间：中统三年八月—中统三年八月
- 地点：玉泉、邢州、洺州、漳河、滏河
- 行动：郭守敬请引玉泉水通漕，王允中请开邢洺漳滏河及达泉灌田，朝廷均批准。
- 结果：漕运与灌溉工程获得立项。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `WORK-THREAD-YUANSHI-005-GUANGJI-YUQUAN-CANALS`
- 引文：請開玉泉水以通漕運

### CHF-YUANSHI-005-REBUILD-BORDER-CITIES

- 时间：中统三年十月至十二月—中统三年十月至十二月
- 地点：宿州、蘄縣、邳州、息州
- 行动：命万户修复宿州、蕲县、邳州城郭，并复立息州城安民。
- 结果：宋元边区数座城防获得恢复。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `WORK-THREAD-YUANSHI-005-REBUILD-BORDER-CITIES`
- 引文：修復宿州、蘄縣

### CHF-YUANSHI-005-YEAR4-TAX-AND-IRON

- 时间：中统四年正月至五月—中统四年正月至五月
- 地点：诸路、河南、东平
- 行动：诸路包银改以钞缴，丝料本色或以钞折纳；清查漏附籍户起冶，后设铁冶年输铁并铸农器二十万件换粟四万石。
- 结果：户税货币化规则明确，官营铁业与农器粮食交换扩大。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：諸路包銀以鈔輸納

## 政治事件

### CHF-YUANSHI-005-LITAN-REBELLION-OUTBREAK

- 时间：中统三年二月—中统三年二月
- 地点：漣州、海州、益都、濟南
- 行动：李璮杀蒙古戍军，以涟海三城降宋，进入益都发府库犒军并占据济南；王文统因同谋被诛。
- 结果：山东发生大规模叛乱，朝廷中央同谋遭清洗。
- 代价：蒙古戍军被杀，数量未载。
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：李璮反，以漣、海三城獻于宋

### CHF-YUANSHI-005-LITAN-MOBILIZATION

- 时间：中统三年二月至三月—中统三年二月至三月
- 地点：山東、燕京、河南、平陽、太原
- 行动：朝廷发蒙古汉军讨李璮，诸路会师济南，强征民兵、逃军、宗教与匠户等户丁，并设置山东行省和多处宣慰机构。
- 结果：形成围剿李璮的跨路军政动员体系。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：發諸蒙古、漢軍討李璮

### CHF-YUANSHI-005-OFFICIAL-SALARIES

- 时间：中统三年二月—中统三年二月
- 地点：中央与诸路
- 行动：首次制定中外官员俸禄，命大司农姚枢议定条格。
- 结果：官俸由临时给付转为成文标准。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-005-OFFICIAL-SALARIES`
- 引文：始定中外官俸

### CHF-YUANSHI-005-LITAN-AMNESTIES

- 时间：中统三年四月至十月—中统三年四月至十月
- 地点：博興、高苑、益都、濟南
- 行动：朝廷数次赦免被李璮胁从的军民，禁官军掠夺，并令被掠民马归还原主。
- 结果：多数胁从者免罪，部分被掠财产获得返还原则。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-005-LITAN-AMNESTIES`
- 引文：嘗為李璮脅從者，並釋其罪

### CHF-YUANSHI-005-STRICT-DEATH-REVIEW

- 时间：中统三年四月至十二月—中统三年四月至十二月
- 地点：诸路
- 行动：规定部曲重罪须审实奏闻后才能处刑，命详谳冤狱；对擅杀伪钞犯者追究违制，年底又令五十三名死刑犯重加详审。
- 结果：死刑处置被反复要求上奏复核。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-005-STRICT-DEATH-REVIEW`
- 引文：必先奏聞，然後置諸法

### CHF-YUANSHI-005-SHANDONG-MILITARY-CIVIL-SEPARATION

- 时间：中统三年九月至十月—中统三年九月至十月
- 地点：益都、山東
- 行动：益都军民分治，董文炳统军、撒吉思治民；武卫军按十户取二，后明确军民籍。
- 结果：李璮乱后山东地方军政分权，军户抽取制度化。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-005-SHANDONG-MILITARY-CIVIL-SEPARATION`
- 引文：每十戶惟取其二充武衞軍

### CHF-YUANSHI-005-RESTRAIN-POWERFUL-HARASSMENT

- 时间：中统三年十月—中统三年十月
- 地点：诸路
- 行动：禁止诸王、使臣和军队倚势扰民，地方发现者须拘执上报。
- 结果：对宗室、使臣和军队扰民建立现场拘捕机制。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-005-RESTRAIN-POWERFUL-HARASSMENT`
- 引文：禁諸王、使臣、師旅敢有恃勢擾民者，所在執以聞

### CHF-YUANSHI-005-ANGER-DEATH-DELAY

- 时间：中统三年十一月—中统三年十一月
- 地点：朝廷
- 行动：忽必烈告诫史天泽，自己若因愤怒欲诛人，臣下应延迟一两日后再覆奏执行。
- 结果：皇帝自设情绪性诛杀的延迟复奏约束。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-005-ANGER-DEATH-DELAY`
- 引文：朕或乘怒欲有所誅殺，卿等宜遲留一二日，覆奏行之

### CHF-YUANSHI-005-CIVIL-MILITARY-OFFICE-SEPARATION

- 时间：中统三年十二月—中统三年十二月
- 地点：诸路
- 行动：规定总管兼万户者只理民事不预军政，罢管民官子弟分管州县等事务，并重申管民官、管军官互不统摄。
- 结果：李璮乱后军政分职成为全国性制度。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-005-CIVIL-MILITARY-OFFICE-SEPARATION`
- 引文：止理民事，軍政勿預

### CHF-YUANSHI-005-SHANGDU-AND-PRIVY-COUNCIL

- 时间：中统四年五月—中统四年五月
- 地点：開平、上都
- 行动：初立枢密院，由燕王真金兼判；同时升开平府为上都，设置路级长官。
- 结果：中央军事机关与上都行政地位确立，真金兼领中书枢密。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-005-SHANGDU-AND-PRIVY-COUNCIL`
- 引文：初立樞密院

### CHF-YUANSHI-005-ARIQ-SURRENDER

- 时间：至元元年七月—至元元年七月
- 地点：上都
- 行动：阿里不哥战败后与诸王来归；忽必烈释放太祖后裔诸王，不追究其罪，但处死不鲁花等谋臣。
- 结果：皇位内战结束，宗室获宽赦，核心谋臣被诛。
- 代价：未载
- 路由：`CONTEXT_ONLY` → `NONE`
- 引文：阿里不哥自昔木土之敗，不復能軍

### CHF-YUANSHI-005-ZHIYUAN-REFORM-EDICT

- 时间：至元元年八月—至元元年八月
- 地点：诸路
- 行动：阿里不哥归降后改元至元并大赦，颁行省并县、定员品秩俸禄公田、考课、均役、招流民、禁擅科与官物私用、恤孤劝农平价等综合条格。
- 结果：内战后全国行政、财政、民政与监察规则集中重建。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-005-ZHIYUAN-REFORM-EDICT`
- 引文：改中統五年為至元元年

### CHF-YUANSHI-005-PRINCELY-ENVOY-LIMITS-1264

- 时间：至元元年八月—至元元年八月
- 地点：诸路
- 行动：统一诸王使臣的驿传、税赋、差发规则，禁止擅招民户、向非投下人放斡脱银、口传敕旨和追呼省臣属官；站户限田四顷免税。
- 结果：宗王使臣特权受到制度约束，站户免税田额明确。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-005-PRINCELY-ENVOY-LIMITS-1264`
- 引文：不許擅招民戶

### CHF-YUANSHI-005-ZHENJIN-STATE-ROLE

- 时间：至元元年八月—至元元年八月
- 地点：中书省
- 行动：命燕王真金署敕，并在省中另置幕位，每月一两次到省判署朝政；刘秉忠拜太保参领中书。
- 结果：真金正式参与最高行政签署，刘秉忠进入中枢。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-005-ZHENJIN-STATE-ROLE`
- 引文：命燕王署敕

### CHF-YUANSHI-005-ABOLISH-HEREDITARY-LORDS

- 时间：至元元年十二月—至元元年十二月
- 地点：诸路
- 行动：罢各投下达鲁花赤，罢部分枢密院断事与奥鲁官，由总管府兼押；最终罢诸侯世守，建立官员迁转法。
- 结果：地方世袭与投下官权进一步转入流官和总管体系。
- 代价：未载
- 路由：`CLOSE_CANDIDATE` → `POL-THREAD-YUANSHI-005-ABOLISH-HEREDITARY-LORDS`
- 引文：罷各投下達魯花赤
