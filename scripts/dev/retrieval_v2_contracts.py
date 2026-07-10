from __future__ import annotations

import itertools
import re
from typing import Any, Iterable


PROCESS_DOC_PATH = "docs/数据结构与生成库/retrieval_v2_clean抓包流程.md"
NON_CORE_RETRIEVAL_RULES = {"anti_nepotism"}
PERSONNEL_POLITICAL_WIDE_PROFILE = "personnel_political_wide"
PERSONNEL_POLITICAL_WIDE_CAPTURE_MODE = "personnel_political_wide_shadow"
POLITICAL_ACTION_FACT_SCHEMA = "political_action_v1"
CANDIDATE_ROUTE_TABLE_VERSION = "personnel_political_v0_2"

CANDIDATE_HINT_STATUS_CURRENT, CANDIDATE_HINT_STATUS_FUTURE, CANDIDATE_HINT_STATUS_CONTEXT = "current_rule_candidate", "future_rule_hint", "rejected_or_context_only"

AD_FACTOR_HINT_KEY = "appointment_delegation_factor_hints"
AD_IMPORTANCE_HINTS = ("nominal_light", "real_duty", "key_military_political", "state_level_long_term", "unknown")
AD_EFFECT_HINTS = ("weak_feedback", "normal_success", "strong_success", "bad_result", "major_bad", "structural_bad", "unknown")
AD_CONTINUITY_HINTS = ("single_short", "stable", "long_multi_stage", "unknown")
AD_HINT_CONFIDENCE_KEYS, AD_HINT_CONFIDENCE_VALUES = ("importance", "effect", "continuity"), ("high", "medium", "low")
AD_UNCERTAINTY_FLAGS = ("effect_strength_needs_review", "same_chain_result_unclear", "continuity_needs_review", "negative_causality_needs_review")

PERSONNEL_POLITICAL_ROUTE_LANES = (
    {
        "candidate_item_code": "I5B",
        "candidate_lane": "I5B.appointment_delegation",
        "rule_code": "appointment_delegation",
        "hint_status": CANDIDATE_HINT_STATUS_CURRENT,
        "direction": "positive | negative | neutral",
        "required_facts": ["actor", "object", "action_type", "event_scope", "outcome", "source_span_refs"],
        "description": "任命、委任、信任、授权、误任、错授和同链条结果正式候选；必须由消费端窄验后才能晋升入分。",
    },
    {
        "candidate_item_code": "I5B",
        "candidate_lane": "team_building",
        "rule_code": "team_building",
        "hint_status": CANDIDATE_HINT_STATUS_CURRENT,
        "direction": "positive | negative | neutral",
        "required_facts": ["actor", "object", "office_or_domain", "outcome", "source_span_refs"],
        "description": "对象池全部人才对象、团队构成和长期人才结构材料正式候选。",
    },
    {
        "candidate_item_code": "I5B",
        "candidate_lane": "talent_discovery",
        "rule_code": "talent_discovery",
        "hint_status": CANDIDATE_HINT_STATUS_CURRENT,
        "direction": "positive | negative | neutral",
        "required_facts": ["actor", "object", "action_type", "outcome", "source_span_refs"],
        "description": "荐举、识别、拔擢或识人失误材料正式候选。",
    },
    {
        "candidate_item_code": "I5B",
        "candidate_lane": "tolerate_talent",
        "rule_code": "tolerate_talent",
        "hint_status": CANDIDATE_HINT_STATUS_CURRENT,
        "direction": "positive | negative | neutral",
        "required_facts": ["actor", "object", "action_type", "outcome", "source_span_refs"],
        "description": "保全、容忍、复用、疑忌和处置人才材料正式候选；处置本身不自动入分。",
    },
    {
        "candidate_item_code": "I5B",
        "candidate_lane": "anti_nepotism",
        "rule_code": "anti_nepotism",
        "hint_status": CANDIDATE_HINT_STATUS_CURRENT,
        "direction": "positive | negative | neutral",
        "required_facts": ["actor", "object", "action_type", "event_scope", "source_span_refs"],
        "description": "亲族、近臣、朋党、纳贿、专擅和谮害等正式候选。",
    },
    {
        "candidate_item_code": "I5C",
        "candidate_lane": "central_military_power_control",
        "rule_code": "central_military_power_control",
        "hint_status": CANDIDATE_HINT_STATUS_FUTURE,
        "direction": "positive | negative | neutral",
        "required_facts": ["actor", "object", "action_type", "event_scope", "outcome", "source_span_refs"],
        "description": "禁军、兵权、军头、中央宿卫和中枢军事权力收放等 I5C 中央军权控制候选。",
    },
    {
        "candidate_item_code": "I5C",
        "candidate_lane": "regional_clan_power_control",
        "rule_code": "regional_clan_power_control",
        "hint_status": CANDIDATE_HINT_STATUS_FUTURE,
        "direction": "positive | negative | neutral",
        "required_facts": ["actor", "object", "action_type", "event_scope", "outcome", "source_span_refs"],
        "description": "藩镇、削藩、宗室、外戚、地方强族、封国和区域割据风险等 I5C 地方/宗族权力控制候选。",
    },
    {
        "candidate_item_code": "I5C",
        "candidate_lane": "inner_favorite_power_control",
        "rule_code": "inner_favorite_power_control",
        "hint_status": CANDIDATE_HINT_STATUS_FUTURE,
        "direction": "positive | negative | neutral",
        "required_facts": ["actor", "object", "action_type", "event_scope", "outcome", "source_span_refs"],
        "description": "宦官、近臣、宠臣、内廷、私门、矫诏、专擅等 I5C 内廷近幸权力控制候选。",
    },
    {
        "candidate_item_code": "I5C",
        "candidate_lane": "institutional_constraint_correction",
        "rule_code": "institutional_constraint_correction",
        "hint_status": CANDIDATE_HINT_STATUS_FUTURE,
        "direction": "positive | negative | neutral",
        "required_facts": ["actor", "object", "action_type", "event_scope", "outcome", "source_span_refs"],
        "description": "制度约束、纠偏、收权、限权、问责和防止权力链条失控等 I5C 制度性制衡纠错候选。",
    },
    {
        "candidate_item_code": "I5D",
        "candidate_lane": "political_character",
        "rule_code": "political_character",
        "hint_status": CANDIDATE_HINT_STATUS_FUTURE,
        "direction": "positive | negative | neutral",
        "required_facts": ["actor", "object", "action_type", "outcome", "cost_or_damage", "source_span_refs"],
        "description": "功臣处置、猜忌、滥杀、背信、宽纵残害和处置程序等政治品格候选。",
    },
    {
        "candidate_item_code": "I5E",
        "candidate_lane": "cognition_learning",
        "rule_code": "cognition_learning",
        "hint_status": CANDIDATE_HINT_STATUS_FUTURE,
        "direction": "positive | negative | neutral",
        "required_facts": ["actor", "object", "action_type", "outcome", "time_context", "source_span_refs"],
        "description": "纳谏、拒谏、改错、复盘、问策和听取反证等认知纠错候选。",
    },
    {
        "candidate_item_code": "I6",
        "candidate_lane": "key_decision",
        "rule_code": "key_decision",
        "hint_status": CANDIDATE_HINT_STATUS_FUTURE,
        "direction": "positive | negative | neutral",
        "required_facts": ["actor", "action_type", "event_scope", "outcome", "cost_or_damage", "source_span_refs"],
        "description": "危机决策、战略取舍、迁都改革、继承安排和风险止损候选。",
    },
    {
        "candidate_item_code": "I3",
        "candidate_lane": "military_frontier_result",
        "rule_code": "military_frontier_result",
        "hint_status": CANDIDATE_HINT_STATUS_FUTURE,
        "direction": "positive | negative | neutral",
        "required_facts": ["actor", "object", "action_type", "event_scope", "outcome", "source_span_refs"],
        "description": "战役结果、边疆治理、军制改革和将帅任用结果候选。",
    },
    {
        "candidate_item_code": "I7",
        "candidate_lane": "historical_debt",
        "rule_code": "historical_debt",
        "hint_status": CANDIDATE_HINT_STATUS_FUTURE,
        "direction": "negative | neutral",
        "required_facts": ["actor", "object", "action_type", "cost_or_damage", "time_context", "source_span_refs"],
        "description": "大规模屠杀、制度性高压、财政民生长期损害和社会灾难候选。",
    },
)

DELEGATION_ROLE_FAMILIES = (
    {
        "family_code": "military_delegate",
        "target_min_claims": 2,
        "required_directions": ["positive", "negative"],
        "description": "将领任命、方面军、战役指挥、边防和军政委任。",
    },
    {
        "family_code": "civil_delegate",
        "target_min_claims": 1,
        "required_directions": ["positive"],
        "description": "宰辅、尚书、地方行政、财政、屯田、法制、选官和后勤治理委任。",
    },
    {
        "family_code": "strategic_delegate",
        "target_min_claims": 1,
        "required_directions": ["positive"],
        "description": "谋臣、参谋、规划者、顾问式授权和关键决策采纳。",
    },
    {
        "family_code": "revoked_or_failed_delegate",
        "target_min_claims": 1,
        "required_directions": ["negative"],
        "description": "撤权、误任、干预下属决策、亲信失职和授权后果失败；处置结果须同时证明任内具体治理或人才结构损害才算负向。",
    },
)

I5B_ITEM_WIDE_ROLE_FAMILIES = (
    {
        "family_code": "appointment_delegation_material",
        "target_min_claims": 2,
        "required_directions": ["positive", "negative"],
        "description": "任命、委任、信任、授权、误任、错授和同链条结果等可复核任用授权质量的事实材料。",
    },
    {
        "family_code": "team_building_material",
        "target_min_claims": 2,
        "required_directions": ["positive", "negative"],
        "description": "对象池全部人才对象及其职能、边疆/财政/水利/中枢等团队构成材料。",
    },
    {
        "family_code": "talent_discovery_material",
        "target_min_claims": 1,
        "required_directions": ["positive", "negative"],
        "description": "荐举、拔擢、识别新人、采纳推荐或识人失误材料。",
    },
    {
        "family_code": "tolerate_talent_material",
        "target_min_claims": 1,
        "required_directions": ["positive", "negative"],
        "description": "保全、容忍、复用、疑忌、处置功臣或人才材料；处置结果本身只作候选事实。",
    },
    {
        "family_code": "anti_nepotism_material",
        "target_min_claims": 1,
        "required_directions": ["positive", "negative"],
        "description": "亲族、近臣、朋党、结党、纳贿、专擅、谮害等反亲私材料。",
    },
    {
        "family_code": "future_power_character_hint",
        "target_min_claims": 0,
        "required_directions": ["positive", "negative", "neutral"],
        "description": "权臣、宗室、军权失控、矫诏专政、待功臣和政治伦理等 future hint，不进入当前 formal rule 消费。",
    },
)

NEGATIVE_AD_POWER_ABUSE_TERMS = (
    "宠任", "寵任", "专擅", "專擅", "威福", "弄权", "弄權", "壅蔽", "不奏", "径行", "徑行", "封事",
    "匿闻", "匿聞", "奔竞", "奔競", "趋附", "趨附",
)

DELEGATION_ROLE_FAMILY_TERMS = {
    "military_delegate": (
        "将军",
        "將軍",
        "行军",
        "行軍",
        "元帅",
        "元帥",
        "都督",
        "总管",
        "總管",
        "节度",
        "節度",
        "征",
        "讨",
        "討",
        "镇",
        "鎮",
        "留守",
    ),
    "civil_delegate": (
        "尚书",
        "尚書",
        "仆射",
        "僕射",
        "侍中",
        "中书",
        "中書",
        "政事",
        "刺史",
        "太守",
        "令",
        "尹",
        "屯田",
        "度支",
        "盐铁",
        "鹽鐵",
        "转运",
        "轉運",
        "选",
        "選",
        "律",
        "法",
    ),
    "strategic_delegate": (
        "谋",
        "謀",
        "策",
        "计",
        "計",
        "议",
        "議",
        "谏",
        "諫",
        "参谋",
        "參謀",
        "军师",
        "軍師",
        "帷幄",
    ),
    "revoked_or_failed_delegate": (
        "夺",
        "奪",
        "免",
        "罢",
        "罷",
        "废",
        "廢",
        "贬",
        "貶",
        "斥",
        "弃",
        "棄",
        "败",
        "敗",
        "陷",
        "误",
        "誤",
        "不听",
        "不聽",
        "诛",
        "誅",
    ),
}

SECONDARY_RULE_HINTS_BY_RULE = {
    "appointment_delegation": (
        {
            "rule_code": "team_building",
            "reason": "对象池全部人才对象及其职能材料可复核团队建设。",
        },
        {
            "rule_code": "talent_discovery",
            "reason": "荐举、拔擢、识别新人或采纳推荐材料可复核发现人才。",
        },
        {
            "rule_code": "tolerate_talent",
            "reason": "保全、容忍、复用、疑忌、处置功臣/人才等材料可复核容人保全；处置结果本身不是负向结论。",
        },
        {
            "rule_code": "anti_nepotism",
            "reason": "亲族、近臣、朋党、结党、纳贿、专擅、谮害等材料可复核避免任人唯亲。",
        },
        {
            "rule_code": "central_military_power_control",
            "candidate_item_code": "I5C",
            "candidate_lane": "central_military_power_control",
            "reason": "禁军、兵权、军头、宿卫和中枢军事权力收放等材料可复核 I5C 中央军权控制。",
            "hint_status": "future_rule_hint",
        },
        {
            "rule_code": "regional_clan_power_control",
            "candidate_item_code": "I5C",
            "candidate_lane": "regional_clan_power_control",
            "reason": "藩镇、削藩、宗室、外戚、地方强族和区域割据风险等材料可复核 I5C 地方/宗族权力控制。",
            "hint_status": "future_rule_hint",
        },
        {
            "rule_code": "inner_favorite_power_control",
            "candidate_item_code": "I5C",
            "candidate_lane": "inner_favorite_power_control",
            "reason": "宦官、近臣、宠臣、内廷、私门、矫诏和专擅等材料可复核 I5C 内廷近幸权力控制。",
            "hint_status": "future_rule_hint",
        },
        {
            "rule_code": "institutional_constraint_correction",
            "candidate_item_code": "I5C",
            "candidate_lane": "institutional_constraint_correction",
            "reason": "制度约束、纠偏、收权、限权、问责和防止权力链条失控等材料可复核 I5C 制度性制衡纠错。",
            "hint_status": "future_rule_hint",
        },
        {
            "rule_code": "political_character",
            "reason": "滥杀、待功臣、政治伦理、克制或不克制等材料仅作后续政治品格项候选。",
            "hint_status": "future_rule_hint",
        },
    ),
    "i5b_item_wide": (
        {
            "rule_code": "appointment_delegation",
            "candidate_item_code": "I5B",
            "candidate_lane": "I5B.appointment_delegation",
            "hint_status": CANDIDATE_HINT_STATUS_CURRENT,
            "reason": "任命、委任、信任、授权、误任、错授和同链条结果材料可复核任用授权质量。",
        },
        {
            "rule_code": "team_building",
            "candidate_item_code": "I5B",
            "candidate_lane": "team_building",
            "hint_status": CANDIDATE_HINT_STATUS_CURRENT,
            "reason": "对象池全部人才对象及其职能材料可复核团队建设。",
        },
        {
            "rule_code": "talent_discovery",
            "candidate_item_code": "I5B",
            "candidate_lane": "talent_discovery",
            "hint_status": CANDIDATE_HINT_STATUS_CURRENT,
            "reason": "荐举、拔擢、识别新人或采纳推荐材料可复核发现人才。",
        },
        {
            "rule_code": "tolerate_talent",
            "candidate_item_code": "I5B",
            "candidate_lane": "tolerate_talent",
            "hint_status": CANDIDATE_HINT_STATUS_CURRENT,
            "reason": "保全、容忍、复用、疑忌、处置功臣/人才等材料可复核容人保全；处置结果本身不是负向结论。",
        },
        {
            "rule_code": "anti_nepotism",
            "candidate_item_code": "I5B",
            "candidate_lane": "anti_nepotism",
            "hint_status": CANDIDATE_HINT_STATUS_CURRENT,
            "reason": "亲族、近臣、朋党、结党、纳贿、专擅、谮害等材料可复核避免任人唯亲。",
        },
        {
            "rule_code": "central_military_power_control",
            "candidate_item_code": "I5C",
            "candidate_lane": "central_military_power_control",
            "reason": "禁军、兵权、军头、宿卫和中枢军事权力收放等材料可复核 I5C 中央军权控制。",
            "hint_status": CANDIDATE_HINT_STATUS_FUTURE,
        },
        {
            "rule_code": "regional_clan_power_control",
            "candidate_item_code": "I5C",
            "candidate_lane": "regional_clan_power_control",
            "reason": "藩镇、削藩、宗室、外戚、地方强族和区域割据风险等材料可复核 I5C 地方/宗族权力控制。",
            "hint_status": CANDIDATE_HINT_STATUS_FUTURE,
        },
        {
            "rule_code": "inner_favorite_power_control",
            "candidate_item_code": "I5C",
            "candidate_lane": "inner_favorite_power_control",
            "reason": "宦官、近臣、宠臣、内廷、私门、矫诏和专擅等材料可复核 I5C 内廷近幸权力控制。",
            "hint_status": CANDIDATE_HINT_STATUS_FUTURE,
        },
        {
            "rule_code": "institutional_constraint_correction",
            "candidate_item_code": "I5C",
            "candidate_lane": "institutional_constraint_correction",
            "reason": "制度约束、纠偏、收权、限权、问责和防止权力链条失控等材料可复核 I5C 制度性制衡纠错。",
            "hint_status": CANDIDATE_HINT_STATUS_FUTURE,
        },
        {
            "rule_code": "political_character",
            "candidate_item_code": "I5D",
            "candidate_lane": "political_character",
            "reason": "滥杀、待功臣、政治伦理、克制或不克制等材料仅作后续政治品格项候选。",
            "hint_status": CANDIDATE_HINT_STATUS_FUTURE,
        },
        {
            "rule_code": "cognition_learning",
            "candidate_item_code": "I5E",
            "candidate_lane": "cognition_learning",
            "reason": "纳谏、拒谏、改错、复盘、问策、听取反证等材料仅作后续认知纠错项候选。",
            "hint_status": CANDIDATE_HINT_STATUS_FUTURE,
        },
        {
            "rule_code": "key_decision",
            "candidate_item_code": "I6",
            "candidate_lane": "key_decision",
            "reason": "危机决策、战略取舍、迁都改革、继承安排、风险止损等材料仅作后续关键决策项候选。",
            "hint_status": CANDIDATE_HINT_STATUS_FUTURE,
        },
        {
            "rule_code": "military_frontier_result",
            "candidate_item_code": "I3",
            "candidate_lane": "military_frontier_result",
            "reason": "战役结果、边疆治理、军制改革、将帅任用结果等材料仅作后续军事边疆项候选。",
            "hint_status": CANDIDATE_HINT_STATUS_FUTURE,
        },
        {
            "rule_code": "historical_debt",
            "candidate_item_code": "I7",
            "candidate_lane": "historical_debt",
            "reason": "大规模屠杀、制度性高压、财政民生长期损害、族群或社会灾难等材料仅作后续历史负债项候选。",
            "hint_status": CANDIDATE_HINT_STATUS_FUTURE,
        },
    ),
    PERSONNEL_POLITICAL_WIDE_PROFILE: tuple(
        {
            key: row[key]
            for key in ("rule_code", "candidate_item_code", "candidate_lane", "hint_status")
            if key in row
        }
        | {"reason": row["description"]}
        for row in PERSONNEL_POLITICAL_ROUTE_LANES
    ),
}
ALIAS_VARIANT_GROUPS = (
    ("党", "黨"),
    ("进", "進"),
    ("卫", "衛"),
    ("吕", "呂"),
    ("余", "餘", "馀"),
    ("庆", "慶"),
    ("张", "張"),
    ("孙", "孫"),
    ("儿", "兒"),
    ("尔", "爾"),
    ("长", "長"),
    ("无", "無"),
    ("万", "萬"),
    ("彻", "徹"),
    ("节", "節"),
    ("龄", "齡"),
    ("温", "溫"),
    ("荣", "榮"),
    ("庄", "莊"),
    ("后", "後"),
    ("吴", "吳"),
    ("机", "機"),
    ("绪", "緒"),
    ("颜", "顏"),
    ("铁", "鐵"),
    ("爱", "愛"),
    ("图", "圖"),
    ("鲁", "魯"),
    ("达", "達"),
    ("硕", "碩"),
    ("敌", "敵"),
    ("记", "記"),
    ("窝", "窩"),
    ("阔", "闊"),
    ("宪", "憲"),
    ("脱", "脫"),
    ("闵", "閔"),
    ("苌", "萇"),
    ("兴", "興"),
    ("逊", "遜"),
    ("义", "義"),
    ("骏", "駿"),
    ("齐", "齊"),
    ("鸾", "鸞"),
    ("绎", "繹"),
    ("陈", "陳"),
    ("顼", "頊"),
    ("宝", "寶"),
    ("欢", "歡"),
    ("纬", "緯"),
    ("显", "顯"),
    ("黄", "黃"),
    ("乔", "喬"),
    ("马", "馬"),
    ("迟", "遲"),
    ("冯", "馮"),
    ("尉", "尉"),
    ("征", "徵"),
    ("药", "藥"),
    ("卢", "盧"),
    ("贾", "賈"),
    ("绩", "勣", "𪟝"),
    ("辽", "遼"),
    ("陆", "陸"),
    ("离", "離"),
    ("郦", "酈"),
    ("钟", "鍾"),
    ("备", "備"),
    ("灵", "靈"),
    ("仆", "僕"),
    ("萧", "蕭"),
    ("乐", "樂"),
    ("参", "參"),
    ("谋", "謀"),
    ("议", "議"),
    ("谏", "諫"),
    ("谨", "謹"),
    ("军", "軍"),
    ("将", "將"),
    ("师", "師"),
    ("总", "總"),
    ("帅", "帥"),
    ("镇", "鎮"),
    ("书", "書"),
    ("载", "載"),
    ("国", "國"),
    ("挥", "揮"),
    ("权", "權"),
    ("术", "術"),
    ("纪", "紀"),
    ("员", "員"),
    ("赵", "趙"),
    ("匡",),
    ("胤",),
    ("渊", "淵"),
    ("刘", "劉"),
    ("杨", "楊"),
    ("广", "廣"),
    ("隆",),
    ("祯", "禎"),
    ("祐", "佑"),
    ("炽", "熾"),
    ("钰", "鈺"),
    ("见", "見"),
    ("樘",),
    ("瞻",),
    ("禛",),
    ("玄",),
    ("烨", "燁"),
    ("弘",),
    ("历", "曆", "歷"),
    ("继", "繼"),
    ("勋", "勳"),
    ("绛", "絳"),
    ("贤", "賢"),
    ("烟", "煙"),
    ("谅", "諒"),
    ("顺", "順"),
    ("买", "買"),
    ("曹",),
    ("操",),
    ("李",),
    ("世",),
    ("民",),
    ("建",),
    ("成",),
    ("元",),
    ("吉",),
    ("孝",),
    ("恭",),
    ("道",),
    ("玄",),
    ("普",),
    ("吕", "呂"),
    ("慶", "庆"),
    ("汤", "湯"),
    ("邓", "鄧"),
    ("蓝", "藍"),
    ("怀", "懷"),
    ("宽", "寬"),
    ("义", "義"),
    ("升", "昇"),
    ("苍", "蒼"),
    ("晔", "曄"),
    ("娄", "婁"),
    ("杰", "傑"),
)
ALIAS_CHAR_VARIANTS: dict[str, tuple[str, ...]] = {}
for _group in ALIAS_VARIANT_GROUPS:
    _unique_group = tuple(dict.fromkeys(str(item) for item in _group if str(item)))
    for _char in _unique_group:
        ALIAS_CHAR_VARIANTS[_char] = _unique_group


def unique_strings(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def alias_script_variants(value: str, *, max_variants: int = 64) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    choices: list[tuple[str, ...]] = []
    variant_space = 1
    simplified_chars: list[str] = []
    traditional_chars: list[str] = []
    for char in text:
        raw_variants = ALIAS_CHAR_VARIANTS.get(char, (char,))
        variants = tuple(dict.fromkeys([char, *[variant for variant in raw_variants if variant != char]]))
        choices.append(variants)
        simplified_chars.append(raw_variants[0])
        traditional_chars.append(raw_variants[-1])
        variant_space *= len(variants)
    preferred = unique_strings([text, "".join(simplified_chars), "".join(traditional_chars)])
    generated: list[str] = []
    for parts in itertools.product(*choices):
        generated.append("".join(parts))
        if len(generated) >= max_variants:
            break
    return unique_strings([*preferred, *generated])[:max_variants]


SOURCE_HINTS_BY_PERIOD = {
    "秦": ["史記", "資治通鑑"],
    "西汉": ["史記", "漢書", "資治通鑑"],
    "西漢": ["史記", "漢書", "資治通鑑"],
    "东汉": ["後漢書", "資治通鑑"],
    "東漢": ["後漢書", "資治通鑑"],
    "三国": ["三國志", "資治通鑑"],
    "三國": ["三國志", "資治通鑑"],
    "晋": ["晉書", "資治通鑑"],
    "晉": ["晉書", "資治通鑑"],
    "前秦": ["晉書", "資治通鑑"],
    "后赵": ["晉書", "資治通鑑"],
    "後趙": ["晉書", "資治通鑑"],
    "冉魏": ["晉書", "資治通鑑"],
    "成汉": ["晉書", "資治通鑑"],
    "成漢": ["晉書", "資治通鑑"],
    "后秦": ["晉書", "資治通鑑"],
    "後秦": ["晉書", "資治通鑑"],
    "后燕": ["晉書", "資治通鑑"],
    "後燕": ["晉書", "資治通鑑"],
    "南燕": ["晉書", "資治通鑑"],
    "后凉": ["晉書", "資治通鑑"],
    "後涼": ["晉書", "資治通鑑"],
    "西凉": ["晉書", "資治通鑑"],
    "西涼": ["晉書", "資治通鑑"],
    "北凉": ["晉書", "資治通鑑"],
    "北涼": ["晉書", "資治通鑑"],
    "胡夏": ["晉書", "資治通鑑"],
    "夏": ["晉書", "資治通鑑"],
    "北燕": ["晉書", "資治通鑑"],
    "十六国": ["晉書", "資治通鑑"],
    "十六國": ["晉書", "資治通鑑"],
    "刘宋": ["宋書", "南史", "資治通鑑"],
    "劉宋": ["宋書", "南史", "資治通鑑"],
    "南朝宋": ["宋書", "南史", "資治通鑑"],
    "南齐": ["南齊書", "南史", "資治通鑑"],
    "南齊": ["南齊書", "南史", "資治通鑑"],
    "南梁": ["梁書", "南史", "資治通鑑"],
    "梁": ["梁書", "南史", "資治通鑑"],
    "南陈": ["陳書", "南史", "資治通鑑"],
    "南陳": ["陳書", "南史", "資治通鑑"],
    "陈": ["陳書", "南史", "資治通鑑"],
    "陳": ["陳書", "南史", "資治通鑑"],
    "北魏": ["魏書", "北史", "資治通鑑"],
    "北齐": ["北齊書", "北史", "資治通鑑"],
    "北齊": ["北齊書", "北史", "資治通鑑"],
    "北周": ["周書", "北史", "資治通鑑"],
    "北朝": ["北史", "資治通鑑"],
    "隋": ["隋書", "資治通鑑"],
    "唐": ["舊唐書", "新唐書", "資治通鑑"],
    "五代": ["舊五代史", "新五代史", "資治通鑑", "十國春秋"],
    "后梁": ["舊五代史", "新五代史", "資治通鑑"],
    "後梁": ["舊五代史", "新五代史", "資治通鑑"],
    "后唐": ["舊五代史", "新五代史", "資治通鑑"],
    "後唐": ["舊五代史", "新五代史", "資治通鑑"],
    "后晋": ["舊五代史", "新五代史", "資治通鑑"],
    "後晉": ["舊五代史", "新五代史", "資治通鑑"],
    "后汉": ["舊五代史", "新五代史", "資治通鑑"],
    "後漢": ["舊五代史", "新五代史", "資治通鑑"],
    "后周": ["舊五代史", "新五代史", "資治通鑑"],
    "後周": ["舊五代史", "新五代史", "資治通鑑"],
    "十国": ["舊五代史", "新五代史", "資治通鑑", "十國春秋"],
    "十國": ["舊五代史", "新五代史", "資治通鑑", "十國春秋"],
    "南唐": ["舊五代史", "新五代史", "資治通鑑", "十國春秋"],
    "前蜀": ["舊五代史", "新五代史", "資治通鑑", "十國春秋"],
    "后蜀": ["舊五代史", "新五代史", "資治通鑑", "十國春秋"],
    "後蜀": ["舊五代史", "新五代史", "資治通鑑", "十國春秋"],
    "南汉": ["舊五代史", "新五代史", "資治通鑑", "十國春秋"],
    "南漢": ["舊五代史", "新五代史", "資治通鑑", "十國春秋"],
    "吴越": ["舊五代史", "新五代史", "資治通鑑", "十國春秋"],
    "吳越": ["舊五代史", "新五代史", "資治通鑑", "十國春秋"],
    "闽": ["舊五代史", "新五代史", "資治通鑑", "十國春秋"],
    "閩": ["舊五代史", "新五代史", "資治通鑑", "十國春秋"],
    "荆南": ["舊五代史", "新五代史", "資治通鑑", "十國春秋"],
    "荊南": ["舊五代史", "新五代史", "資治通鑑", "十國春秋"],
    "南平": ["舊五代史", "新五代史", "資治通鑑", "十國春秋"],
    "马楚": ["舊五代史", "新五代史", "資治通鑑", "十國春秋"],
    "馬楚": ["舊五代史", "新五代史", "資治通鑑", "十國春秋"],
    "北汉": ["舊五代史", "新五代史", "資治通鑑", "十國春秋"],
    "北漢": ["舊五代史", "新五代史", "資治通鑑", "十國春秋"],
    "辽": ["遼史", "契丹國志", "續資治通鑑長編"],
    "遼": ["遼史", "契丹國志", "續資治通鑑長編"],
    "西辽": ["遼史", "契丹國志"],
    "西遼": ["遼史", "契丹國志"],
    "契丹": ["遼史", "契丹國志", "續資治通鑑長編"],
    "西夏": ["宋史", "續資治通鑑長編", "遼史", "金史"],
    "金": ["金史", "大金國志", "續資治通鑑"],
    "女真": ["金史", "大金國志", "續資治通鑑"],
    "蒙古": ["元史", "新元史", "續資治通鑑"],
    "元": ["元史", "新元史", "續資治通鑑"],
    "北宋": ["宋史", "續資治通鑑長編", "資治通鑑"],
    "南宋": ["宋史", "續資治通鑑"],
    "宋": ["宋史", "續資治通鑑長編", "資治通鑑"],
    "明": ["明史", "明實錄"],
    "后金": ["清史稿", "清實錄"],
    "清": ["清史稿", "清實錄"],
}

SOURCE_ROOT_ALIASES = {
    "史記": ["史記"],
    "漢書": ["漢書"],
    "後漢書": ["後漢書"],
    "三國志": ["三國志"],
    "晉書": ["晉書"],
    "宋書": ["宋書"],
    "南齊書": ["南齊書"],
    "梁書": ["梁書"],
    "陳書": ["陳書"],
    "南史": ["南史"],
    "魏書": ["魏書"],
    "北史": ["北史"],
    "北齊書": ["北齊書"],
    "周書": ["周書"],
    "隋書": ["隋書"],
    "舊唐書": ["舊唐書"],
    "新唐書": ["新唐書"],
    "舊五代史": ["舊五代史"],
    "新五代史": ["新五代史"],
    "十國春秋": ["十國春秋"],
    "遼史": ["遼史"],
    "契丹國志": ["契丹國志"],
    "金史": ["金史"],
    "大金國志": ["大金國志"],
    "元史": ["元史"],
    "新元史": ["新元史"],
    "資治通鑑": ["資治通鑑"],
    "宋史": ["宋史"],
    "續資治通鑑長編": ["續資治通鑑長編"],
    "續資治通鑑": ["續資治通鑑"],
    "明史": ["明史"],
    "明實錄": ["明實錄", "大明太祖高皇帝實錄"],
    "清史稿": ["清史稿"],
    "清實錄": ["清實錄", "康熙朝實錄", "雍正朝實錄", "乾隆朝實錄"],
}

SOURCE_HINT_TEXT_ALIASES = {
    "史記": ("史記", "史记"),
    "漢書": ("漢書", "汉书"),
    "後漢書": ("後漢書", "后汉书"),
    "三國志": ("三國志", "三国志"),
    "晉書": ("晉書", "晋书"),
    "宋書": ("宋書", "宋书"),
    "南齊書": ("南齊書", "南齐书"),
    "梁書": ("梁書", "梁书"),
    "陳書": ("陳書", "陈书"),
    "魏書": ("魏書", "魏书"),
    "北史": ("北史",),
    "隋書": ("隋書", "隋书"),
    "舊唐書": ("舊唐書", "旧唐书"),
    "新唐書": ("新唐書", "新唐书"),
    "舊五代史": ("舊五代史", "旧五代史"),
    "新五代史": ("新五代史",),
    "十國春秋": ("十國春秋", "十国春秋"),
    "遼史": ("遼史", "辽史"),
    "契丹國志": ("契丹國志", "契丹国志"),
    "金史": ("金史",),
    "大金國志": ("大金國志", "大金国志"),
    "元史": ("元史",),
    "新元史": ("新元史",),
    "宋史": ("宋史",),
    "續資治通鑑長編": ("續資治通鑑長編", "续资治通鉴长编"),
    "續資治通鑑": ("續資治通鑑", "续资治通鉴"),
    "資治通鑑": ("資治通鑑", "资治通鉴"),
    "明史": ("明史",),
    "明實錄": ("明實錄", "明实录"),
    "清史稿": ("清史稿",),
    "清實錄": ("清實錄", "清实录"),
}

TARGET_SOURCE_ROOT_ALIASES = {
    "明實錄": (
        (("朱元璋", "明太祖", "太祖高皇帝", "洪武"), ("大明太祖高皇帝實錄", "明太祖實錄")),
        (("朱棣", "明成祖", "明太宗", "太宗文皇帝", "永樂", "永乐"), ("大明太宗文皇帝實錄", "明太宗實錄")),
        (("朱高炽", "朱高熾", "明仁宗", "仁宗昭皇帝", "洪熙"), ("大明仁宗昭皇帝實錄", "明仁宗實錄")),
        (("朱瞻基", "明宣宗", "宣宗章皇帝", "宣德"), ("大明宣宗章皇帝實錄", "明宣宗實錄")),
        (("朱祁镇", "朱祁鎮", "朱祁钰", "朱祁鈺", "明英宗", "明代宗", "正統", "景泰", "天順"), ("大明英宗睿皇帝實錄", "明英宗實錄")),
        (("朱见深", "朱見深", "明憲宗", "明宪宗", "成化"), ("大明憲宗純皇帝實錄", "明憲宗實錄")),
        (("朱祐樘", "朱佑樘", "明孝宗", "孝宗敬皇帝", "弘治"), ("大明孝宗敬皇帝實錄", "明孝宗實錄")),
        (
            ("朱常洛", "明光宗", "光宗貞皇帝", "泰昌"),
            ("大明光宗貞皇帝實錄", "明光宗實錄", "明實錄/光宗貞皇帝實錄"),
        ),
        (
            ("朱由校", "明熹宗", "熹宗悊皇帝", "天啟", "天启"),
            ("明熹宗悊皇帝實錄", "明熹宗實錄", "明實錄/熹宗悊皇帝實錄"),
        ),
        (("朱由檢", "朱由检", "崇禎", "崇祯", "明思宗", "明毅宗"), ("崇禎長編", "明季北略")),
    ),
    "清實錄": (
        (("努爾哈赤", "努尔哈赤", "清太祖", "太祖高皇帝", "天命"), ("清太祖高皇帝實錄", "太祖高皇帝實錄")),
        (("皇太極", "皇太极", "清太宗", "太宗文皇帝", "崇德"), ("清太宗文皇帝實錄", "太宗文皇帝實錄")),
        (("玄燁", "玄烨", "康熙", "清聖祖", "清圣祖"), ("康熙朝實錄", "清聖祖仁皇帝實錄")),
        (("胤禛", "雍正", "清世宗"), ("雍正朝實錄", "清世宗憲皇帝實錄")),
        (("弘曆", "弘历", "乾隆", "清高宗"), ("乾隆朝實錄", "清高宗純皇帝實錄")),
        (
            ("載湉", "载湉", "光緒", "光绪", "清德宗"),
            ("光緒朝實錄", "清德宗景皇帝實錄", "清實錄/德宗景皇帝實錄", "清實錄/大清德宗景皇帝實錄"),
        ),
    ),
}

THREE_KINGDOMS_MARKERS = ("曹魏", "三国", "三國", "魏武帝", "魏文帝", "魏明帝")

SOURCE_PAGE_STRATEGY_BY_RULE = {
    "appointment_delegation": {
        "required_page_types": [
            "target_annals_or_benji",
            "object_biographies_or_liezhuan",
            "chronicle_cross_check",
        ],
        "object_discovery_families": [
            "military_delegate",
            "civil_delegate",
            "strategic_delegate",
            "revoked_or_failed_delegate",
            "royal_clan_delegate",
        ],
        "notes": [
            "高密度目标不得只搜本纪；核心对象名必须回到本传或同源列传页补切片。",
            "同一 claim 可服务多个 rule，但必须拆成独立 bindings。",
        ],
    },
    "i5b_item_wide": {
        "required_page_types": [
            "target_annals_or_benji",
            "object_biographies_or_liezhuan",
            "chronicle_cross_check",
            "institution_or_office_context_pages",
        ],
        "object_discovery_families": [
            "appointment_delegation_material",
            "team_building_material",
            "talent_discovery_material",
            "tolerate_talent_material",
            "anti_nepotism_material",
            "future_power_character_hint",
            "royal_clan_power_holder",
        ],
        "notes": [
            "这是 I5B item-wide discovery，不得沿用单一任用授权对象族作为覆盖边界。",
            "对象发现必须覆盖任命信任、团队、荐举识才、容才保全、亲私朋党、皇子宗室和权力/政治品格 future hint。",
            "primary_bindings 必须为空；所有 formal rule 归属写入 secondary_binding_candidates。",
        ],
    }
}


def normalize_source_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def source_hints_for_period(period: str) -> list[str]:
    if period in SOURCE_HINTS_BY_PERIOD:
        return list(SOURCE_HINTS_BY_PERIOD[period])
    for key, hints in SOURCE_HINTS_BY_PERIOD.items():
        if key and key in period:
            return list(hints)
    return ["資治通鑑"]


def source_hints_from_source_targets(source_targets: Any) -> list[str]:
    if isinstance(source_targets, str):
        values = [source_targets]
    elif isinstance(source_targets, list):
        values = [str(value or "") for value in source_targets]
    else:
        values = []
    hints: list[str] = []
    alias_rows = [
        (canonical, alias)
        for canonical, aliases in SOURCE_HINT_TEXT_ALIASES.items()
        for alias in aliases
        if normalize_source_text(alias)
    ]
    for value in values:
        text = normalize_source_text(value)
        for canonical, alias in sorted(alias_rows, key=lambda row: len(normalize_source_text(row[1])), reverse=True):
            normalized_alias = normalize_source_text(alias)
            if canonical == "魏書" and ("三國志" in text or "三国志" in text) and f"{normalized_alias}/" not in text:
                continue
            if canonical == "漢書" and ("後漢書" in text or "后汉书" in text) and f"{normalized_alias}/" not in text:
                continue
            if normalize_source_text(alias) in text:
                hints.append(canonical)
    return unique_strings(hints)


def source_root_aliases_for_hint(source_hint: str, metadata: dict[str, Any] | None = None) -> list[str]:
    hint = normalize_source_text(source_hint)
    if not hint:
        return []
    marker_text = normalize_source_text(
        " ".join(
            str((metadata or {}).get(key) or "")
            for key in ("name", "emperor_name", "period", "title", "temple_name", "posthumous_name", "era", "note", "power_origin")
        )
    )
    target_roots: list[str] = []
    for markers, roots in TARGET_SOURCE_ROOT_ALIASES.get(hint, ()):
        if any(normalize_source_text(marker) and normalize_source_text(marker) in marker_text for marker in markers):
            target_roots.extend(roots)
    if target_roots:
        return unique_strings(target_roots)
    return unique_strings(SOURCE_ROOT_ALIASES.get(hint, [hint]))


def source_hints_for_metadata(metadata: dict[str, Any], *, max_hints: int | None = None) -> list[str]:
    marker_text = "".join(str(metadata.get(key) or "") for key in ("period", "title", "temple_name", "posthumous_name", "note", "power_origin"))
    hints: list[str] = []
    if any(marker in marker_text for marker in THREE_KINGDOMS_MARKERS):
        hints.append("三國志")
    hints.extend(source_hints_from_source_targets(metadata.get("source_targets")))
    hints.extend(source_hints_for_period(str(metadata.get("period") or "")))
    result = unique_strings(hints)
    if max_hints is not None:
        return result[: max(1, max_hints)]
    return result


def source_strategy_template(
    rule_code: str,
    *,
    metadata: dict[str, Any] | None = None,
    source_hint_limit: int | None = None,
) -> dict[str, Any]:
    strategy = dict(SOURCE_PAGE_STRATEGY_BY_RULE.get(rule_code, {}))
    strategy.setdefault("required_page_types", ["target_annals_or_benji", "object_relevant_pages"])
    strategy.setdefault("object_discovery_families", [])
    strategy.setdefault("notes", [])
    strategy["source_hints"] = source_hints_for_metadata(metadata or {}, max_hints=source_hint_limit)
    strategy["source_root_filter_required"] = True
    return strategy


def secondary_rule_hints(rule_code: str) -> list[dict[str, str]]:
    return [dict(row) for row in SECONDARY_RULE_HINTS_BY_RULE.get(rule_code, ())]


def role_family_terms(rule_code: str, family_code: str) -> list[str]:
    if rule_code == "appointment_delegation":
        return list(DELEGATION_ROLE_FAMILY_TERMS.get(family_code, ()))
    if rule_code == "i5b_item_wide":
        if family_code == "appointment_delegation_material":
            return ["任", "命", "授", "拜", "委", "信", "相", "將", "将", *NEGATIVE_AD_POWER_ABUSE_TERMS]
        if family_code == "team_building_material":
            return ["相", "將", "将", "大臣", "腹心", "帷幄", "勳", "勋"]
        if family_code == "talent_discovery_material":
            return ["薦", "荐", "舉", "举", "拔", "識", "识", "用"]
        if family_code == "tolerate_talent_material":
            return [
                "容",
                "赦",
                "保",
                "復",
                "复",
                "疑",
                "忌",
                "免",
                "誅",
                "诛",
                "谏",
                "諫",
                "诤",
                "諍",
                "直言",
                "上疏",
                "纳谏",
                "納諫",
                "受金",
                "盗嫂",
                "盜嫂",
                "谗",
                "讒",
                "谮",
                "譖",
                "短",
                "毁",
                "毀",
            ]
        if family_code == "anti_nepotism_material":
            return ["親", "亲", "党", "黨", "納賄", "纳贿", "專擅", "专擅", "譖", "谮"]
        if family_code == "future_power_character_hint":
            return [
                "權",
                "权",
                "藩",
                "削藩",
                "撤藩",
                "宗室",
                "外戚",
                "宦官",
                "军权",
                "軍權",
                "兵权",
                "兵權",
                "禁军",
                "禁軍",
                "矯詔",
                "矫诏",
                "專政",
                "专政",
                "擅权",
                "擅權",
                "濫殺",
                "滥杀",
                "冤杀",
                "冤殺",
                "族诛",
                "族誅",
                "株连",
                "株連",
                "罗织",
                "羅織",
                "构陷",
                "構陷",
                "大狱",
                "大獄",
                "问策",
                "問策",
                "从谏",
                "從諫",
                "拒谏",
                "拒諫",
                "迁都",
                "遷都",
                "废立",
                "廢立",
                "罢兵",
                "罷兵",
                "议和",
                "議和",
                "边疆",
                "邊疆",
                "设治",
                "設治",
                "羁縻",
                "羈縻",
                "都护",
                "都護",
                "失地",
                "诏狱",
                "詔獄",
                "崩坏",
                "崩壞",
            ]
    return []


def gap_type_for_role_family(family_code: str) -> str:
    if family_code == "civil_delegate":
        return "civil_undercoverage"
    if family_code == "revoked_or_failed_delegate":
        return "negative_undercoverage"
    if family_code == "strategic_delegate":
        return "predicate_missing"
    return "source_missing"


def coverage_matrix_template(
    rule_code: str,
    *,
    material_policy_codes: Iterable[Any] = (),
    predicate_options: Iterable[Any] = (),
) -> dict[str, Any]:
    if rule_code == "appointment_delegation":
        role_families = [dict(row) | {"objects_checked": [], "gaps": []} for row in DELEGATION_ROLE_FAMILIES]
    elif rule_code == "i5b_item_wide":
        role_families = [dict(row) | {"objects_checked": [], "gaps": []} for row in I5B_ITEM_WIDE_ROLE_FAMILIES]
    else:
        role_families = [
            {
                "family_code": "rule_material_claim",
                "target_min_claims": 0 if rule_code in NON_CORE_RETRIEVAL_RULES else 1,
                "required_directions": ["positive", "negative"],
                "description": "按规则材料策略和谓词选项抓取可用材料事实。",
                "objects_checked": [],
                "gaps": [],
            }
        ]
    return {
        "rule_code": rule_code,
        "role_families": role_families,
        "material_policy_codes": unique_strings(material_policy_codes),
        "predicate_options": unique_strings(predicate_options),
        "secondary_rule_hints": secondary_rule_hints(rule_code),
    }
