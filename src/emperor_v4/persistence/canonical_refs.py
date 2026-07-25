from __future__ import annotations

from hashlib import sha256
import re
import unicodedata


def canonical_hashed_ref(prefix: str, value: object, *, length: int = 16) -> str:
    rendered = unicodedata.normalize("NFKC", str(value).strip())
    if not rendered:
        raise ValueError(f"{prefix} canonical reference requires a source value")
    if re.fullmatch(rf"{re.escape(prefix)}-[0-9A-F]{{{length}}}", rendered):
        return rendered
    digest = sha256(rendered.encode("utf-8")).hexdigest()[:length].upper()
    return f"{prefix}-{digest}"


def canonical_assertion_id(value: object) -> str:
    return canonical_hashed_ref("AST-V4", value, length=20)


def canonical_section_id(value: object) -> str:
    return canonical_hashed_ref("SEC-V4", value)


def canonical_source_profile_ref(value: object) -> str:
    return canonical_hashed_ref("SPR-V4", value)


def canonical_person_ref(value: object) -> str:
    rendered = str(value).strip()
    candidate = re.fullmatch(r"RULER-NAME-CANDIDATE-([0-9A-F]{12})", rendered)
    if candidate:
        return f"PER-V4-{candidate.group(1)}"
    fixed = {
        "PER-LI-SHIMIN": "PER-V4-737E2C4D60AC",
        "PER-V4-78F48EBC67F8": "PER-V4-737E2C4D60AC",
        "per-4eb7ac987fecc59f": "PER-V4-4EB7AC987FEC",
        "per-e15c1b65f12f0ae6": "PER-V4-E15C1B65F12F",
        "杨广": "PER-V4-C93016BB741A", "胡亥": "PER-V4-75EF40579300",
        "PER-FANG-XUANLING": "PER-V4-C37ED24688F5",
        "PER-NAME-CANDIDATE-CHANGSUN-WUJI": "PER-V4-839C5A8CB43C",
        "PER-NAME-CANDIDATE-FANG-YIAI": "PER-V4-B3237391DC6C",
        "PER-NAME-CANDIDATE-HOU-JUNJI": "PER-V4-BBB439491EC7",
        "PER-NAME-CANDIDATE-LI-DAOYU": "PER-V4-D1A161DEDA40",
        "PER-NAME-CANDIDATE-LI-YOULIANG": "PER-V4-7B0F18DD6A7E",
        "PER-NAME-CANDIDATE-WANG-GUI": "PER-V4-6CAF227D2D39",
        "PER-NAME-CANDIDATE-ZHANG-XUANSU": "PER-V4-429CE79493C8",
        "PER-GROUP-CANDIDATE-LI-ROYAL-KIN": "GRP-V4-6D9014C97B41",
        "PER-GROUP-CANDIDATE-QINFU-OLD-FOLLOWERS": "GRP-V4-68FC831D2408",
        "二世": "PER-V4-75EF40579300", "二世使者": "GRP-V4-3169839A92A8",
        "叔孙通": "PER-V4-6F877F064B0B", "屈突通": "PER-V4-C1923EA6B469",
        "李斯": "PER-V4-A18E9558AE21", "炀帝": "PER-V4-C93016BB741A",
        "胡亥使者": "GRP-V4-CBD654AFB735", "萧瑀": "PER-V4-B817E6DF722E",
        "隋炀帝": "PER-V4-C93016BB741A",
    }
    return fixed.get(rendered, rendered)
