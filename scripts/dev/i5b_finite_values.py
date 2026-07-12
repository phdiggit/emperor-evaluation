from __future__ import annotations

import re
from typing import Any


ALLOWED_DIRECTIONS = ("positive", "negative", "neutral", "mixed")
CLUSTER_DIRECTIONS = ("positive", "negative", "mixed")
SCORING_SIDES = ("positive", "negative")
TALENT_QUALITY_ATTR = "talent_quality"
TALENT_PROFILE_NOTE_ATTR = "talent_profile_note"
GROUP_QUALITY_ATTR = "group_quality"
NEGATIVE_TALENT_QUALITY_VALUES = ("佞臣", "大佞臣", "历史级佞臣")
POSITIVE_TALENT_QUALITY_VALUES = ("普通人才", "重要人才", "顶级人才", "历史级人才")
HIGH_TALENT_QUALITY_VALUES = ("重要人才", "顶级人才", "历史级人才")
DEFERRED_TALENT_QUALITY_VALUES = ("高质量人才",)
CANONICAL_TALENT_QUALITY_VALUES = (
    *POSITIVE_TALENT_QUALITY_VALUES,
    *NEGATIVE_TALENT_QUALITY_VALUES,
)
TALENT_QUALITY_RANKS = {
    "普通人才": 1,
    "重要人才": 2,
    "高质量人才": 3,
    "顶级人才": 3,
    "历史级人才": 4,
}

TALENT_DISCOVERY_RULE_CODE = "talent_discovery"
APPOINTMENT_DELEGATION_RULE_CODE = "appointment_delegation"
TEAM_BUILDING_RULE_CODE = "team_building"
TOLERATE_TALENT_RULE_CODE = "tolerate_talent"
ANTI_NEPOTISM_RULE_CODE = "anti_nepotism"
I5B_RULE_CODES = (
    TALENT_DISCOVERY_RULE_CODE,
    APPOINTMENT_DELEGATION_RULE_CODE,
    TEAM_BUILDING_RULE_CODE,
    TOLERATE_TALENT_RULE_CODE,
    ANTI_NEPOTISM_RULE_CODE,
)
I5B_ITEM_CODES = ("I5B",)
I5B_SUBITEMS = ("第五项B",)
OBJECT_ATTR_CODES = (
    TALENT_QUALITY_ATTR,
    GROUP_QUALITY_ATTR,
    "career_track",
    "hard_merit_tags",
    "hard_merit_summary",
    "hard_merit_scope_hint",
    "hard_merit_limitations",
    "authority_eval_summary",
    "authority_eval_sources",
    "talent_quality_basis",
    TALENT_PROFILE_NOTE_ATTR,
)

OBJECT_ALIAS_KINDS = (
    "canonical",
    "alias",
    "personal_name",
    "courtesy_name",
    "posthumous_name",
    "temple_name",
    "title",
    "office",
    "style",
    "variant",
)
OBJECT_ALIAS_SCOPES = ("global", "emperor")

CANONICAL_PERIODS = (
    "秦",
    "西楚",
    "汉",
    "西汉",
    "新",
    "东汉",
    "曹魏",
    "蜀汉",
    "孙吴",
    "晋",
    "西晋",
    "东晋",
    "刘宋",
    "南齐",
    "南梁",
    "南陈",
    "十六国",
    "汉赵",
    "后赵",
    "前秦",
    "北魏",
    "东魏",
    "西魏",
    "北齐",
    "北周",
    "隋",
    "唐",
    "武周",
    "五代",
    "后梁",
    "后唐",
    "后晋",
    "后汉",
    "后周",
    "辽",
    "宋",
    "北宋",
    "南宋",
    "西夏",
    "金",
    "元",
    "明",
    "后金",
    "清",
    "民国",
)

PERIOD_ALIASES = {
    "qin": "秦",
    "chu-han": "西楚",
    "chuhan": "西楚",
    "western chu": "西楚",
    "westernchu": "西楚",
    "han": "汉",
    "westernhan": "西汉",
    "western han": "西汉",
    "xin": "新",
    "easternhan": "东汉",
    "eastern han": "东汉",
    "shuhan": "蜀汉",
    "shu han": "蜀汉",
    "wu": "孙吴",
    "sunwu": "孙吴",
    "sun wu": "孙吴",
    "wei": "曹魏",
    "caowei": "曹魏",
    "cao wei": "曹魏",
    "jin": "晋",
    "westernjin": "西晋",
    "western jin": "西晋",
    "easternjin": "东晋",
    "eastern jin": "东晋",
    "liu song": "刘宋",
    "liusong": "刘宋",
    "southern song liu": "刘宋",
    "南朝宋": "刘宋",
    "南朝刘宋": "刘宋",
    "萧齐": "南齐",
    "xiao qi": "南齐",
    "xiaoqi": "南齐",
    "southern qi": "南齐",
    "southernqi": "南齐",
    "南朝齐": "南齐",
    "南朝萧齐": "南齐",
    "萧梁": "南梁",
    "xiao liang": "南梁",
    "xiaoliang": "南梁",
    "southern liang": "南梁",
    "southernliang": "南梁",
    "南朝梁": "南梁",
    "南朝萧梁": "南梁",
    "南朝陈": "南陈",
    "southern chen": "南陈",
    "southernchen": "南陈",
    "han zhao": "汉赵",
    "hanzhao": "汉赵",
    "前赵": "汉赵",
    "former zhao": "汉赵",
    "formerzhao": "汉赵",
    "later zhao": "后赵",
    "laterzhao": "后赵",
    "sui": "隋",
    "tang": "唐",
    "wuzhou": "武周",
    "wu zhou": "武周",
    "tangwuzhou": "武周",
    "tang wu zhou": "武周",
    "tang, wu zhou": "武周",
    "tang/wu zhou": "武周",
    "唐、武周": "武周",
    "five dynasties": "五代",
    "fivedynasties": "五代",
    "laterliang": "后梁",
    "later liang": "后梁",
    "latertang": "后唐",
    "later tang": "后唐",
    "laterjin": "后晋",
    "later jin": "后晋",
    "laterhan": "后汉",
    "later han": "后汉",
    "laterzhou": "后周",
    "later zhou": "后周",
    "liao": "辽",
    "song": "宋",
    "northernsong": "北宋",
    "northern song": "北宋",
    "southernsong": "南宋",
    "southern song": "南宋",
    "xixia": "西夏",
    "xi xia": "西夏",
    "western xia": "西夏",
    "jin dynasty": "金",
    "jurchen jin": "金",
    "yuan": "元",
    "ming": "明",
    "later jin qing": "后金",
    "laterjin qing": "后金",
    "later jin/qing": "后金",
    "laterjin/qing": "后金",
    "houjin": "后金",
    "qing": "清",
    "republic": "民国",
    "republic of china": "民国",
}

TEAM_PERSON_PHASE_SUFFIXES = ("早期", "中期", "后期", "晚期")


class FiniteValueError(ValueError):
    pass


def _alias_key(value: str) -> str:
    collapsed = re.sub(r"[\s_\-]+", " ", value.strip()).casefold()
    compact = collapsed.replace(" ", "")
    return PERIOD_ALIASES.get(collapsed, PERIOD_ALIASES.get(compact, value.strip()))


def normalize_period_alias(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    return _alias_key(text)


def normalize_team_person_name(value: str) -> str:
    name = value.strip()
    for suffix in TEAM_PERSON_PHASE_SUFFIXES:
        if name.endswith(suffix) and len(name) > len(suffix):
            return name[: -len(suffix)]
    return name


def is_canonical_period(value: Any) -> bool:
    return normalize_period_alias(value) in CANONICAL_PERIODS


def require_choice(value: Any, *, choices: tuple[str, ...], field_name: str) -> str:
    text = str(value or "").strip()
    if text not in choices:
        allowed = ", ".join(choices)
        raise FiniteValueError(f"{field_name}: unsupported value {text}; expected one of {allowed}")
    return text


def require_canonical_period(value: Any, *, field_name: str) -> str:
    normalized = normalize_period_alias(value)
    if normalized not in CANONICAL_PERIODS:
        allowed = ", ".join(CANONICAL_PERIODS)
        raise FiniteValueError(f"{field_name}: unsupported period {value}; expected one of {allowed}")
    return normalized


def require_direction(value: Any, *, field_name: str = "direction") -> str:
    return require_choice(value, choices=ALLOWED_DIRECTIONS, field_name=field_name)


def require_talent_quality(value: Any, *, field_name: str = "talent_quality") -> str:
    return require_choice(value, choices=CANONICAL_TALENT_QUALITY_VALUES, field_name=field_name)


def talent_quality_rank(value: Any) -> int | None:
    return TALENT_QUALITY_RANKS.get(str(value or "").strip())


def talent_quality_polarity(value: Any) -> str:
    text = str(value or "").strip()
    if text in POSITIVE_TALENT_QUALITY_VALUES or text in DEFERRED_TALENT_QUALITY_VALUES:
        return "positive"
    if text in NEGATIVE_TALENT_QUALITY_VALUES:
        return "negative"
    return "unknown"
