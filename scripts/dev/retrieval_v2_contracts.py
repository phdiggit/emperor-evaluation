from __future__ import annotations

import itertools
import re
from typing import Any, Iterable


PROCESS_DOC_PATH = "docs/数据结构与生成库/retrieval_v2_clean抓包流程.md"
NON_CORE_RETRIEVAL_RULES = {"anti_nepotism"}

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
        "description": "撤权、误任、干预下属决策、亲信失职和授权后果失败。",
    },
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
    "delegation": (
        {
            "rule_code": "appointment_trust",
            "reason": "同一任用事实可能支撑任人信任与授权效果判断。",
        },
        {
            "rule_code": "team_building",
            "reason": "同一任用事实可能支撑团队建设成员和角色互补。",
        },
        {
            "rule_code": "talent_discovery",
            "reason": "授权或任命对象若含首次发现、拔擢或重用线索，可留给发现人才复核。",
        },
    )
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
    ("长", "長"),
    ("无", "無"),
    ("万", "萬"),
    ("彻", "徹"),
    ("节", "節"),
    ("龄", "齡"),
    ("乔", "喬"),
    ("马", "馬"),
    ("迟", "遲"),
    ("尉", "尉"),
    ("征", "徵"),
    ("药", "藥"),
    ("卢", "盧"),
    ("绩", "勣"),
    ("辽", "遼"),
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
    ("樘",),
    ("瞻",),
    ("禛",),
    ("玄",),
    ("烨", "燁"),
    ("弘",),
    ("历", "曆", "歷"),
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
    "隋": ["隋書", "資治通鑑"],
    "唐": ["舊唐書", "新唐書", "資治通鑑"],
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
    "隋書": ["隋書"],
    "舊唐書": ["舊唐書"],
    "新唐書": ["新唐書"],
    "資治通鑑": ["資治通鑑"],
    "宋史": ["宋史"],
    "續資治通鑑長編": ["續資治通鑑長編"],
    "續資治通鑑": ["續資治通鑑"],
    "明史": ["明史"],
    "明實錄": ["明實錄", "大明太祖高皇帝實錄"],
    "清史稿": ["清史稿"],
    "清實錄": ["清實錄", "康熙朝實錄", "雍正朝實錄", "乾隆朝實錄"],
}

TARGET_SOURCE_ROOT_ALIASES = {
    "明實錄": (
        (("朱元璋", "明太祖", "太祖高皇帝", "洪武"), ("大明太祖高皇帝實錄", "明太祖實錄")),
        (("朱棣", "明成祖", "明太宗", "太宗文皇帝", "永樂", "永乐"), ("大明太宗文皇帝實錄", "明太宗實錄")),
        (("朱瞻基", "明宣宗", "宣宗章皇帝", "宣德"), ("大明宣宗章皇帝實錄", "明宣宗實錄")),
        (("朱祐樘", "朱佑樘", "明孝宗", "孝宗敬皇帝", "弘治"), ("大明孝宗敬皇帝實錄", "明孝宗實錄")),
        (("朱由檢", "朱由检", "崇禎", "崇祯", "明思宗", "明毅宗"), ("崇禎長編", "明季北略")),
    ),
    "清實錄": (
        (("皇太極", "皇太极", "清太宗", "太宗文皇帝", "崇德"), ("清太宗文皇帝實錄", "太宗文皇帝實錄")),
        (("玄燁", "玄烨", "康熙", "清聖祖", "清圣祖"), ("康熙朝實錄", "清聖祖仁皇帝實錄")),
        (("胤禛", "雍正", "清世宗"), ("雍正朝實錄", "清世宗憲皇帝實錄")),
        (("弘曆", "弘历", "乾隆", "清高宗"), ("乾隆朝實錄", "清高宗純皇帝實錄")),
    ),
}

THREE_KINGDOMS_MARKERS = ("曹魏", "三国", "三國", "魏武帝", "魏文帝", "魏明帝")

SOURCE_PAGE_STRATEGY_BY_RULE = {
    "delegation": {
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
        ],
        "notes": [
            "高密度目标不得只搜本纪；核心对象名必须回到本传或同源列传页补切片。",
            "同一 claim 可服务多个 rule，但必须拆成独立 bindings。",
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
        return unique_strings([hint, *target_roots])
    return unique_strings(SOURCE_ROOT_ALIASES.get(hint, [hint]))


def source_hints_for_metadata(metadata: dict[str, Any], *, max_hints: int | None = None) -> list[str]:
    marker_text = "".join(str(metadata.get(key) or "") for key in ("period", "title", "temple_name", "posthumous_name", "note", "power_origin"))
    hints: list[str] = []
    if any(marker in marker_text for marker in THREE_KINGDOMS_MARKERS):
        hints.append("三國志")
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
    if rule_code == "delegation":
        return list(DELEGATION_ROLE_FAMILY_TERMS.get(family_code, ()))
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
    if rule_code == "delegation":
        role_families = [dict(row) | {"objects_checked": [], "gaps": []} for row in DELEGATION_ROLE_FAMILIES]
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
