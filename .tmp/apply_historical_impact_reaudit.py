from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEST = ROOT / "docs/评分结算/历史影响/01-历史影响正式结算/西汉.json"
EAST = ROOT / "docs/评分结算/历史影响/01-历史影响正式结算/东汉.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def record(data: dict, ruler_id: str) -> dict:
    for row in data["collections"]["records"]["records"]:
        if row["ruler_id"] == ruler_id:
            return row
    raise KeyError(ruler_id)


def add_source(row: dict, source: dict) -> int:
    url = source.get("url")
    title = source.get("title")
    for i, old in enumerate(row["source_refs"]):
        if url and old.get("url") == url:
            return i
        if not url and title and old.get("title") == title:
            return i
    row["source_refs"].append(source)
    return len(row["source_refs"]) - 1


def add_note(row: dict, note: str) -> None:
    notes = row.setdefault("historical_source_notes", [])
    if note not in notes:
        notes.append(note)


def patch_liubang(west: dict) -> None:
    row = record(west, "RULER-HAN-LIUBANG")
    assert row["dimensions"]["paradigm"]["grade"] in {"B", "S"}
    row["dimensions"]["paradigm"]["grade"] = "S"
    row["paradigm_analysis"] = (
        "范式S。刘邦不能只按“开国君主名望”处理；现已定位到跨朝、跨创业环境的最高权力实际接收。"
        "两汉之际，刘秀及其建国集团反复把光武创业与高祖对应，材料直接出现“同符高祖”，邓禹又以“立高祖之业”"
        "劝其建立新的统一政治主体。这里消费的是高祖从低起点创业、整合人才与受命建国的可识别政治样本，不只是“汉”国号本身。\n\n"
        "明初又出现独立接收：李善长向朱元璋明确提出汉高祖“豁达大度，知人善任，不嗜杀人”，并直言“法其所为”；"
        "朱元璋认可该论证。东汉与明初两个相距甚远的创业中枢都把高祖作为现实建国与用人政治的参照，已经超过形象传播，"
        "达到多朝最高权力反复接收。边界是：汉王朝长期合法性、国号连续和一般“布衣天子”文化名望不重复计入范式。"
    )
    idx_bnu = add_source(
        row,
        {
            "kind": "HISTORICAL_WEB_SOURCE",
            "title": "王尔：两汉之际“天子”“皇帝”名号",
            "url": "https://bnuhh.bnu.edu.cn/lsyj/0a60e8b10b1b4659b094b0abc899f4ab.html",
            "evidence_note": "《历史研究》2025年第10期成果转载。定向核对刘秀建国话语中的“同符高祖”、邓禹“立高祖之业”等内容；只用于高祖作为后世创业政治样本的实际接收，不把东汉王朝寿命回填刘邦深度。",
            "verification_mode": "DOMESTIC_RESEARCH_SCOPED_REVIEW",
        },
    )
    idx_mingshi = add_source(
        row,
        {
            "kind": "HISTORICAL_WEB_SOURCE",
            "title": "《明史·李善长传》",
            "url": "https://ctext.org/wiki.pl?chapter=933200&if=gb&remap=gb",
            "evidence_note": "定向核对李善长向朱元璋举汉高祖豁达、知人善任、少杀并明确提出“法其所为”，朱元璋称善。只用于明初最高创业中枢对高祖政治样本的实际接收。",
            "verification_mode": "PRIMARY_TEXT_WEB_SCOPED_REVIEW",
        },
    )
    add_note(row, "2026-09-15扩搜人物范式：补入东汉创业中枢与明初创业中枢对汉高祖的实际政治接收；范式由B改判S，总档不重复上调。")
    row["foundation"]["paradigm_adjustment"] = (
        "范式S已有跨朝独立最高权力接收闭环；但本人的基础S-已由个人因果S+上调至内部S，"
        "按合同不以同一记录再次越过主维度上限抬到S+，公众总档仍S。"
    )
    row["paradigm_review"] = {
        "evidence_status": "LOCATED_RECEPTION",
        "receptions": [
            {
                "receiver": "汉光武帝刘秀及其建国集团",
                "carrier": "两汉之际建国话语中的“同符高祖”与邓禹“立高祖之业”",
                "actual_use": "以高祖创业、整合人才与受命建国样本组织东汉创业合法性和政治方向",
                "source_basis": "DOMESTIC_RESEARCH_SCOPED_REVIEW",
            },
            {
                "receiver": "明太祖朱元璋及明初创业中枢",
                "carrier": "《明史·李善长传》所载法汉高祖之议",
                "actual_use": "把高祖的豁达、知人善任、少杀与快速定天下作为创业治理参照",
                "source_basis": "PRIMARY_TEXT_WEB_SCOPED_REVIEW",
            },
        ],
        "limitation": "只计已定位的创业政治接收；“汉”国号与王朝合法性连续属于路径/身份，不重复包装成个人范式。",
        "depth_separation": "制度和王朝路径持续只进入深度；后世最高权力把高祖样本用于创业、用人和建国论证才进入范式。",
        "source_ref_indices": [idx_bnu, idx_mingshi],
    }


def patch_liuche(west: dict) -> None:
    row = record(west, "RULER-HAN-LIUCHE")
    assert row["dimensions"]["depth_duration"]["grade"] == "S+"

    idx_state = add_source(
        row,
        {
            "kind": "HISTORICAL_WEB_SOURCE",
            "title": "王震中：中国古代“大一统”国家形态结构与中华民族共同体",
            "url": "https://www.nopss.gov.cn/BIG5/n1/2022/0627/c219544-32457360.html",
            "evidence_note": "定向核对汉武帝设置司隶校尉和十三州刺史部、东汉以后州逐渐行政区化及中央—地方层级结构演变。只取中央对区域治理新增中间组织接口及其后续功能转化，不声称后世州制职权原样由武帝创制。",
            "verification_mode": "DOMESTIC_RESEARCH_SCOPED_REVIEW",
        },
    )
    idx_xuanquan = add_source(
        row,
        {
            "kind": "HISTORICAL_WEB_SOURCE",
            "title": "孙海芳：悬泉汉简揭示中华文明统一性",
            "url": "https://www.cssn.cn/skgz/bwyc/202403/t20240314_5738361.shtml",
            "evidence_note": "定向核对河西四郡、丝路交通与悬泉置的国家治理网络；文中所述悬泉纪年材料从武帝元鼎六年至东汉永初元年，作为武帝期开辟的河西国家空间跨西汉—东汉持续运行的实证，不把整个丝路后史归于武帝。",
            "verification_mode": "DOMESTIC_RESEARCH_SCOPED_REVIEW",
        },
    )
    idx_hexi = add_source(
        row,
        {
            "kind": "HISTORICAL_WEB_SOURCE",
            "title": "雍际春：河西四郡及其战略地位论要",
            "url": "https://ksgb.cbpt.cnki.net/portal/journal/portal/client/paper/4766fa8ed592199bfa7e0749dac00ef4",
            "evidence_note": "定向核对武帝设置河西四郡及其在此后中原王朝经营西北、西域、边防和多民族治理中的长期战略地位。只取武帝窗口形成的河西国家空间增量及其长时段战略骨架，不回填后世具体经营成果。",
            "verification_mode": "DOMESTIC_JOURNAL_SCOPED_REVIEW",
        },
    )
    idx_jiaozhi = add_source(
        row,
        {
            "kind": "HISTORICAL_WEB_SOURCE",
            "title": "陈国保：内地移民与汉代南部边疆交趾地区的统一",
            "url": "https://zgld.cbpt.cnki.net/portal/journal/portal/client/paper/abea20e27dd677760154498ba7f8c926",
            "evidence_note": "定向核对元鼎六年后交趾、九真、日南等南部边疆进入汉帝国郡县治理并在两汉维持三百余年的行政、移民与文化整合。只取武帝时期纳入国家治理的增量，不抹去秦代岭南前制及后继独立治理信用。",
            "verification_mode": "DOMESTIC_JOURNAL_SCOPED_REVIEW",
        },
    )
    idx_southwest = add_source(
        row,
        {
            "kind": "HISTORICAL_WEB_SOURCE",
            "title": "杨丽华：两汉中央王朝经略西南夷的政策变迁",
            "url": "https://zhwl.cbpt.cnki.net/portal/journal/portal/client/paper/e3bbf984e0fbfa36bf2b16645c34e5e5",
            "evidence_note": "定向核对武帝至东汉末中央王朝持续经略西南夷、强化控制并推进区域整合的长时段链。只取武帝窗口启动和制度化的国家治理增量，后继调整另行分账。",
            "verification_mode": "DOMESTIC_JOURNAL_SCOPED_REVIEW",
        },
    )

    row["macro_chains"][0]["narrative"] = (
        "刘彻接手的是文景长期恢复后的强盘面，因此不能把国力基础、中央集权趋势以及主父偃、董仲舒、桑弘羊等人的专业设计全部归给本人。"
        "但在五十余年的最高权力窗口里，他持续选择更强的中央穿透、更高的财政动员、更积极的官僚与监察建设，并把这些工具与长期战争资源需求结合起来。"
        "推恩、刺史、太学—察举、盐铁—均输—平准等共同改变了后继皇帝接手的汉帝国运行强度。\n\n"
        "本轮扩搜把长期深度的主证从单一太学谱系移到更硬的国家组织链。国内研究明确把武帝设置司隶校尉、十三州刺史部放入秦汉以后中央—地方结构演变中观察："
        "武帝期形成的是中央跨郡监察和区域治理的中间组织接口，东汉以后州逐渐行政区化，职权与层级继续变化。这里计算的是可追溯的中央—区域组织层新增及其后续功能转化，"
        "不是声称后世州制职权原样沿袭，也不把秦以来郡县制整体归给武帝。"
    )
    row["macro_chains"][0]["source_ref_indices"] = [0, 3, 5, idx_state]

    row["macro_chains"][1]["narrative"] = (
        "河南—朔方与河西改变汉匈攻防及西北通道；南越终局后的岭南、朝鲜汉郡及西南边疆又分别形成实际行政或控制增量。"
        "当前第三项控制账同时列出这些方向，不能仅写河西—西域。卫青、霍去病、张骞及各方向执行者的专业因果另行分账；"
        "西域交通与战略进入同宣帝时期西域都护、匈奴称臣不是同一阶段。\n\n"
        "长期深度现在由多条独立国家空间链共同支撑。河西四郡把走廊从前沿战场转化为可持续治理、交通与边防空间；悬泉材料把这一国家网络从武帝元鼎六年一直实证到东汉。"
        "国内研究又把河西四郡视为后世中原王朝经营西北、西域和边防的长期战略骨架。南部边疆方面，交趾、九真、日南自元鼎六年后进入两汉郡县治理，相关研究直接指出三百余年的稳定统辖；"
        "西南夷治理也呈现从武帝起跨西汉、东汉持续推进的国家整合链。秦代岭南郡县前制、后继改制、反叛与再征服均保留，后世具体成果不回填。"
    )
    row["macro_chains"][1]["source_ref_indices"] = [1, 3, idx_xuanquan, idx_hexi, idx_jiaozhi, idx_southwest]

    row["grade_basis"] = (
        "深度S+维持，但依据重写。当前不再主要依赖“太学延续 + 岭南沿革”两条偏薄材料，而改由多个相互独立、能够跨统治周期乃至跨朝识别的国家结构共同支撑。\n\n"
        "第一，中央—地方组织接口：武帝设置司隶校尉和十三州刺史部，使中央跨郡监察形成稳定的区域组织层；东汉以后州逐渐行政区化，说明该层级发生功能转化而非简单消失。"
        "第二，西北国家空间：河西四郡及交通—驿置网络把河西走廊嵌入国家治理，悬泉材料从武帝元鼎六年延续到东汉永初元年；国内研究同时把河西视为此后王朝经营西北、西域和边防的长期战略骨架。"
        "第三，南部与西南边疆：元鼎六年后交趾、九真、日南等进入两汉郡县治理，研究直接闭合三百余年统辖；西南夷经略也从武帝起跨两汉持续推进。\n\n"
        "这些链条横跨中央—地方组织、战略地理与边疆行政三个基本接口，且都能辨认出武帝窗口的新增或重构部分，达到多域底层结构跨多轮统治持续锁定的S+语义。"
        "秦制中央国家、秦代岭南郡县、文景积累及主父偃等专业设计全部保留；州的后世行政职权、后继新增疆域、西域都护、后世再征服和具体经营成果另归建设者。\n\n"
        "范围S与这组长期国家化足迹共现，基础仍取S+；个人因果S-满足基础S+归责门槛，范式A不加档，公众S+。"
    )
    add_note(
        row,
        "2026-09-15扩搜国内研究材料重审深度S+：主证改为中央—地方组织接口、河西国家空间、南部/西南长期郡县嵌入三组独立结构链；原太学与《晋书》《通典》材料保留为辅助，不再承担最高档主支撑。",
    )
    row["scope_assessment"]["overall_grade_reasoning"] = (
        "全国国家组织转型与多方向新增治理空间相接：中央—区域组织接口、河西国家空间以及南部/西南郡县嵌入构成相互独立的长期结构组合。"
        "范围S、深度S+在同一国家化足迹上共现，取内部S+基础；个人因果S-满足归责门槛，范式A不加档，公众S+。"
    )
    row["foundation"]["joint_footprint_basis"] = row["scope_assessment"]["overall_grade_reasoning"]
    row["confidence_basis"] = (
        "MEDIUM：国内研究已把中央—区域组织、河西国家空间、南部/西南郡县治理三组长期链分别定位，S+不再依赖单一制度名的远期沿用。"
        "但秦代前制、后继功能转化与独立再建设仍要求严格分账，因此不提高个人因果或置信度。"
    )
    row["depth_review"] = {
        "basis": (
            "深度S+。主证由三组独立长期结构共同构成：一是武帝十三州刺史等中央—区域组织接口在东汉以后继续发生制度化转化；"
            "二是河西四郡与交通驿置网络从武帝窗口持续到东汉，并形成后世经营西北的长期战略地理骨架；"
            "三是交趾等南部郡县与西南夷治理从武帝窗口起跨两汉持续嵌入中央国家。三组足迹覆盖国家组织、战略空间和边疆行政，不靠单一机构长寿拼档。"
        ),
        "limits": (
            "秦代郡县与岭南前制、文景积累及专业设计均保留；十三州刺史到后世州制存在职能变化，不按官名连续计算；"
            "西域控制反复、西域都护和后继新增疆域另归后人；交趾及西南的反叛、再征服与后继调整设置截断点。"
            "原太学谱系及《晋书》《通典》沿革仅作辅助，不再单独承担S+主证。"
        ),
        "source_ref_indices": [idx_state, idx_xuanquan, idx_hexi, idx_jiaozhi, idx_southwest],
        "comparative_basis": (
            "与嬴政深度S+同尺：都按可追溯的国家功能结构而非官名原样判断；刘彻的证据现闭合中央—区域组织、河西战略地理、南部/西南行政嵌入多个基本接口，"
            "但其范围和个人因果仍低于开创统一国家形态的同档案例，因此不借深度反推其他维度。"
        ),
        "strongest_counterargument": (
            "最强反论证是这些结构均有前制且后继反复改造：秦已有郡县与岭南经营，刺史到州的性质变化很大，河西和南疆也经历反复。"
            "当前只领取武帝窗口可识别的新增/重构及其后续功能承接；如果只剩同名沿用或后继独立重建则截断。"
            "在此严格折扣后，仍有三组跨多代、其中多组跨西汉—东汉的独立国家结构链，故S+继续成立。"
        ),
    }


def patch_liuxun(west: dict) -> None:
    row = record(west, "RULER-HAN-LIUXUN")
    assert row["dimensions"]["paradigm"]["grade"] in {"B", "A"}
    row["dimensions"]["paradigm"]["grade"] = "A"
    row["paradigm_analysis"] = (
        "范式A。过去只把“汉家自有制度，本以霸王道杂之”视为高辨识度政治语言，因此停在B；本轮扩搜已经补到后世最高权力的实际接收。"
        "田丰对汉宣帝庙号废立的研究指出，东汉初政治文化重新向“霸王道杂之”回归时，“孝宣政治成为重要的参考”，并特别指出光武帝在建武十九年主动追尊宣帝庙号。\n\n"
        "这不是后世史家单纯称赞“孝宣之治”，而是新王朝最高权力在重建汉家政治传统、调整国家政治文化时主动把宣帝政治置入可援用的祖宗样本。"
        "当前闭合一个高质量最高权力接收回路，足以由B升A；但尚未闭合多名独立最高权力跨代反复使用，因此不到A+或S-。"
    )
    idx = add_source(
        row,
        {
            "kind": "HISTORICAL_WEB_SOURCE",
            "title": "田丰：汉宣帝庙号的废立与东汉初年的政治文化转型",
            "url": "https://zhwl.cbpt.cnki.net/portal/journal/portal/client/paper/9144551eef3047e5da3ee404097ff946",
            "evidence_note": "《中华文化论坛》2024年第4期。摘要明确指出东汉政治回归“霸王道杂之”时“孝宣政治成为重要的参考”，并指出光武帝建武十九年主动追尊宣帝庙号。用于闭合光武朝对宣帝政治样本的实际接收，不把东汉整体制度连续回填宣帝深度。",
            "verification_mode": "DOMESTIC_JOURNAL_SCOPED_REVIEW",
        },
    )
    add_note(row, "2026-09-15扩搜人物范式：补入光武朝对孝宣政治的实际接收，范式B改判A；主维度与总档不变。")
    row["foundation"]["paradigm_adjustment"] = (
        "范式A已闭合一个可信的最高权力实际接收案例；按合同A不抬总档，仅修正范式维度，内部A+、公众B均不变。"
    )
    row["paradigm_review"] = {
        "evidence_status": "LOCATED_RECEPTION",
        "receptions": [
            {
                "receiver": "汉光武帝刘秀及建武朝廷",
                "carrier": "建武十九年庙制调整与东汉初政治文化对“霸王道杂之”的回归",
                "actual_use": "把孝宣政治作为重建汉家政治传统的重要现实参考，并主动追尊宣帝庙号",
                "source_basis": "DOMESTIC_JOURNAL_SCOPED_REVIEW",
            }
        ],
        "limitation": "当前只闭合一个高质量最高权力接收回路；一句名言本身不计独立接收，未扩张到多代多朝反复使用。",
        "depth_separation": "宣帝制度被后继继续运行属于深度；光武朝把“孝宣政治”作为政治文化重建参照才计范式。",
        "source_ref_indices": [idx],
    }


def patch_liuxiu(east: dict) -> None:
    row = record(east, "RULER-HAN-LIUXIU")
    assert row["dimensions"]["paradigm"]["grade"] in {"B", "S"}
    row["dimensions"]["paradigm"]["grade"] = "S"
    row["paradigm_analysis"] = (
        "范式S。过去只看到“光武中兴”的人物形象，因缺少后世最高权力实际使用而停在B；本轮扩搜补到了可识别的即位—受命模板复用。"
        "王尔关于两汉之际“天子”“皇帝”名号的研究指出，刘秀即位时把“皇帝即位”与南郊柴燎告天分成前后两个步骤：先取得现实最高政治身份，再以告天完成天子受命。"
        "该研究进一步追踪到魏晋南北朝多个创业君主反复采用这一先后结构，包括宋武帝、齐高帝、梁武帝、北齐文宣帝等。\n\n"
        "这里不是因为后人赞美“光武中兴”而加档，而是刘秀在政权创建中的合法性程序被后世不同王朝最高权力实际复用，满足可识别政治内容—稳定礼仪/制度载体—多名独立最高权力接收的闭环。"
        "由于用途主要集中在创业君主的即位与受命合法性，而非跨多个治理领域的系统政治模板，取S而非S+。"
    )
    idx = add_source(
        row,
        {
            "kind": "HISTORICAL_WEB_SOURCE",
            "title": "王尔：两汉之际“天子”“皇帝”名号",
            "url": "https://bnuhh.bnu.edu.cn/lsyj/0a60e8b10b1b4659b094b0abc899f4ab.html",
            "evidence_note": "《历史研究》2025年第10期成果转载。定向核对刘秀“皇帝即位—南郊柴燎告天”的两步受命结构及宋武帝、齐高帝、梁武帝、北齐文宣帝等后世创业君主的复用。只用于即位合法性范式，不把后世王朝制度寿命回填刘秀深度。",
            "verification_mode": "DOMESTIC_RESEARCH_SCOPED_REVIEW",
        },
    )
    add_note(row, "2026-09-15扩搜人物范式：补入刘秀即位—受命程序被魏晋南北朝多位创业君主复用的研究证据，范式B改判S；总档不重复上调。")
    if "范式S" not in row["grade_basis"]:
        row["grade_basis"] += (
            "\n\n范式S另有独立证据：刘秀形成的“皇帝即位—南郊告天”受命程序被魏晋南北朝多位创业君主复用。"
            "该范式不回填基础或个人因果；当前基础S-已由个人因果S+上调到内部S，不再次抬为S+。"
        )
    row["foundation"]["paradigm_adjustment"] = (
        "范式S已闭合跨朝、多个独立最高权力对即位—受命模板的实际复用；但基础S-已由个人因果S+上调至内部S，"
        "按合同不重复越过主维度上限抬到S+，公众总档仍S。"
    )
    row["paradigm_review"] = {
        "evidence_status": "LOCATED_RECEPTION",
        "receptions": [
            {
                "receiver": "宋武帝刘裕",
                "carrier": "创业皇帝即位后南郊告天的受命程序",
                "actual_use": "沿用刘秀所典型化的“皇帝即位—告天受命”先后结构完成新朝合法性程序",
                "source_basis": "DOMESTIC_RESEARCH_SCOPED_REVIEW",
            },
            {
                "receiver": "齐高帝萧道成",
                "carrier": "创业皇帝即位后南郊告天的受命程序",
                "actual_use": "复用同类两步受命结构组织新朝即位合法性",
                "source_basis": "DOMESTIC_RESEARCH_SCOPED_REVIEW",
            },
            {
                "receiver": "梁武帝萧衍",
                "carrier": "创业皇帝即位后南郊告天的受命程序",
                "actual_use": "复用同类两步受命结构组织新朝即位合法性",
                "source_basis": "DOMESTIC_RESEARCH_SCOPED_REVIEW",
            },
            {
                "receiver": "北齐文宣帝高洋",
                "carrier": "创业皇帝即位后南郊告天的受命程序",
                "actual_use": "复用同类两步受命结构组织新朝即位合法性",
                "source_basis": "DOMESTIC_RESEARCH_SCOPED_REVIEW",
            },
        ],
        "limitation": "研究所闭合的是创业君主即位—受命合法性这一较窄主题；后世一般“中兴”赞誉、宽柔形象不另计独立接收，因此取S而非S+。",
        "depth_separation": "东汉制度与王朝寿命只进入深度；后世创业君主重新采用刘秀典型化的受命程序才进入范式。",
        "source_ref_indices": [idx],
    }


def main() -> None:
    west = load(WEST)
    east = load(EAST)
    patch_liubang(west)
    patch_liuche(west)
    patch_liuxun(west)
    patch_liuxiu(east)
    save(WEST, west)
    save(EAST, east)


if __name__ == "__main__":
    main()
