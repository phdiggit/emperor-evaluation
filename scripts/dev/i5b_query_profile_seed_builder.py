from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.i5b_query_profile_refiner import load_profile_rows, load_status_rows  # noqa: E402
from scripts.dev.i5b_source_pack_status import DEFAULT_ALL_LIST, _default_source_pack_root  # noqa: E402
from scripts.dev.source_excerpt_pool_lib.cache import FetchContext, load_source_excerpt_cache_config, make_cache_backends  # noqa: E402
from scripts.dev.source_excerpt_pool_lib.common import (  # noqa: E402
    DEFAULT_MAX_RETRIES,
    DEFAULT_PROFILE,
    DEFAULT_REQUEST_DELAY_SECONDS,
    DEFAULT_RETRY_BACKOFF_SECONDS,
    DEFAULT_USER_AGENT,
    DEFAULT_WORKFLOW_CODE,
    KNOWN_SOURCE_TITLE_VARIANTS,
    load_source_excerpt_pool_paths,
    normalize_workflow_code,
    read_jsonl,
)
from scripts.dev.source_excerpt_pool_lib.profile import (  # noqa: E402
    ExcerptPoolError,
    chinese_numeral_to_int,
    fallback_source_titles,
    source_title_filters,
)
from scripts.dev.source_excerpt_pool_lib.wikisource import fetch_wikisource_plain_text, search_wikisource  # noqa: E402


DEFAULT_CANDIDATE_SOURCES = (
    ROOT / "data" / "query_lane_coverage.jsonl",
    ROOT / "data" / "evidence_cards.jsonl",
    ROOT / "data" / "source_packs.jsonl",
    ROOT / "data" / "anchors.jsonl",
    ROOT / "data" / "search_logs.jsonl",
)
DEFAULT_TARGET_STATUSES = ("profile_needs_work",)
PLACEHOLDER_MARKERS = ("待识别",)
STOP_TERMS = {
    "任用",
    "授权",
    "宰相",
    "大臣",
    "将领",
    "团队",
    "功臣",
    "辅政",
    "地方",
    "边疆",
    "制度",
    "执行",
    "吏治",
    "选官",
    "近臣",
    "外戚",
    "宦官",
    "宠臣",
    "权臣",
    "处置",
    "罢黜",
    "流放",
    "宗室",
    "姻亲",
    "谏臣",
    "直言",
    "纳谏",
    "上疏",
    "对象",
    "相关",
    "相邻",
    "本纪",
    "列传",
}
DISCOVERY_POSITIVE_ACTIONS = (
    "拜",
    "任",
    "使",
    "命",
    "召",
    "擢",
    "举",
    "舉",
    "荐",
    "薦",
    "用",
    "署",
    "除",
    "授",
    "迁",
    "遷",
)
DISCOVERY_POSITIVE_OFFICES = (
    "为",
    "爲",
    "任",
    "相",
    "将",
    "將",
    "守",
    "太守",
    "刺史",
    "尚书",
    "尚書",
    "侍中",
    "司空",
    "司徒",
    "太尉",
    "将军",
    "將軍",
    "中书",
    "中書",
    "令",
    "仆射",
    "僕射",
    "郎",
    "校尉",
    "都督",
    "总管",
    "總管",
    "宰相",
)
DISCOVERY_FEEDBACK_ACTIONS = ("谏", "諫", "争", "爭", "诤", "諍", "直言", "上疏", "奏")
DISCOVERY_NEGATIVE_ACTIONS = ("诛", "誅", "杀", "殺", "斩", "斬", "赐死", "賜死", "流", "贬", "貶", "黜", "罢", "罷", "废", "廢")
DISCOVERY_FAVOR_ACTIONS = ("宠", "寵", "幸", "嬖", "亲信", "親信")
COMMON_COMPOUND_SURNAMES = (
    "司马",
    "诸葛",
    "夏侯",
    "欧阳",
    "上官",
    "皇甫",
    "尉迟",
    "公孙",
    "长孙",
    "慕容",
    "拓跋",
    "宇文",
    "独孤",
    "令狐",
    "赫连",
    "耶律",
    "完颜",
    "述律",
    "斛律",
    "贺兰",
    "呼延",
    "乞伏",
    "秃发",
)
COMMON_SINGLE_SURNAMES = set(
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻"
    "柏窦章苏潘葛范彭郎鲁韦马苗方俞任袁柳鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝"
    "安常乐于时傅卞齐康伍余元卜顾孟平黄穆萧尹姚邵汪祁毛禹狄米贝明伏成戴宋"
    "庞熊纪舒屈项祝董梁杜阮蓝季麻贾路娄危江童颜郭梅盛林钟徐邱骆高夏蔡田胡"
    "凌霍虞万支柯管卢莫房解应宗丁宣邓洪包左石崔吉龚程邢裴陆荣翁荀羊惠甄家"
    "封芮靳段焦巴牧山谷车侯全班甘祖武符刘景詹束龙叶司韶黎薄白蒲从索卓蔺蒙"
    "乔习鱼向古易廖庾居衡步都耿满弘匡国文寇广东利蔚越师聂晁辛阚简饶空曾沙"
    "丰巢关蒯相查游竺权益桓公"
)


def _add_unique(values: list[str], value: str) -> None:
    cleaned = " ".join(str(value).split())
    if cleaned and cleaned not in values:
        values.append(cleaned)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_source_rows(paths: Iterable[Path]) -> list[tuple[Path, dict[str, Any]]]:
    rows: list[tuple[Path, dict[str, Any]]] = []
    for path in paths:
        if not path.exists():
            continue
        for row in read_jsonl(path):
            rows.append((path, row))
    return rows


def _row_matches_person(row: Mapping[str, Any], person: str) -> bool:
    if row.get("person") == person:
        return True
    linked = row.get("linked_persons")
    return isinstance(linked, list) and person in linked


def _split_terms(value: Any) -> list[str]:
    terms: list[str] = []
    if isinstance(value, list):
        for item in value:
            terms.extend(_split_terms(item))
        return terms
    if not isinstance(value, str):
        return []
    for part in re.split(r"[;；、,，/\s]+", value):
        part = part.strip()
        if part:
            terms.append(part)
    return terms


def _candidate_terms(row: Mapping[str, Any]) -> list[str]:
    fields = (
        "object_name",
        "label",
        "trigger_terms",
        "query_terms",
        "positive_terms",
        "negative_terms",
        "reversal_terms",
    )
    terms: list[str] = []
    for field in fields:
        for term in _split_terms(row.get(field)):
            if _looks_like_person_term(term):
                _add_unique(terms, term)
    return terms


def _looks_like_person_term(value: str) -> bool:
    if value in STOP_TERMS:
        return False
    if any(char in value for char in "為为者其之以而於于也矣乎乃所此斯則则"):
        return False
    if any(marker in value for marker in PLACEHOLDER_MARKERS):
        return False
    if not re.fullmatch(r"[\u4e00-\u9fff]{2,5}", value):
        return False
    if value.endswith(("对象", "团队", "制度", "机制", "事件", "政治", "政策", "风险", "安全", "本纪", "列传")):
        return False
    if value in {"任人唯亲", "相邻项", "人才安全", "政权安全"}:
        return False
    return True


def _has_likely_person_name_start(value: str) -> bool:
    if any(value.startswith(surname) for surname in COMMON_COMPOUND_SURNAMES):
        return True
    if value.startswith("公"):
        return False
    return bool(value and value[0] in COMMON_SINGLE_SURNAMES)


def _looks_like_discovery_person_term(value: str, context: str) -> bool:
    if not _looks_like_person_term(value):
        return False
    if not _has_likely_person_name_start(value):
        return False
    if any(marker in value for marker in ("曰", "太子", "魏王", "天子", "将军", "將軍", "骠骑", "驃騎")):
        return False
    if f"{value}人" in context or f"{value}氏" in context:
        return False
    return True


def _suggested_layer(row: Mapping[str, Any]) -> str:
    haystack = " ".join(str(row.get(key) or "") for key in ("polarity", "lane_group", "lane_name", "trigger_family", "source_pack_id", "evidence_id", "search_id"))
    if any(marker in haystack.upper() for marker in ("NEG", "NEGATIVE")) or "negative" in haystack or "负" in haystack:
        return "negative_or_reversal_objects"
    if any(marker in haystack for marker in ("谏", "反馈", "容谏", "直言")):
        return "supplemental_objects"
    return "core_positive_objects"


def _confidence(row: Mapping[str, Any]) -> str:
    text = " ".join(str(row.get(key) or "") for key in ("review_status", "verification_status", "coverage_status", "result_status", "anchor_status"))
    if any(marker in text for marker in ("source_verified", "converted_to_card", "evidence_found")):
        return "high"
    return "medium"


def collect_local_candidates(person: str, source_rows: Sequence[tuple[Path, Mapping[str, Any]]]) -> list[dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    for path, row in source_rows:
        if not _row_matches_person(row, person):
            continue
        layer = _suggested_layer(row)
        for term in _candidate_terms(row):
            item = candidates.setdefault(
                term,
                {
                    "object_name": term,
                    "suggested_layer": layer,
                    "confidence": _confidence(row),
                    "supporting_rows": [],
                    "reason": "来自本地已登记 search/source/evidence/anchor 行的同人对象候选。",
                },
            )
            if item["suggested_layer"] != "negative_or_reversal_objects" and layer == "negative_or_reversal_objects":
                item["suggested_layer"] = layer
            if item["confidence"] != "high" and _confidence(row) == "high":
                item["confidence"] = "high"
            item["supporting_rows"].append(
                {
                    "path": str(path),
                    "id": str(
                        row.get("evidence_id")
                        or row.get("source_pack_id")
                        or row.get("lane_coverage_id")
                        or row.get("anchor_id")
                        or row.get("search_id")
                        or ""
                    ),
                }
            )
    return sorted(candidates.values(), key=lambda item: (item["suggested_layer"], item["object_name"]))


def _layer_from_probe_query(query: str) -> str:
    if any(term in query for term in ("风险", "处置", "诛", "誅", "杀", "殺", "宠臣", "外戚", "宦官", "任人唯亲", "宗室")):
        return "negative_or_reversal_objects"
    if any(term in query for term in ("谏", "諫", "直言", "纳谏", "上疏")):
        return "supplemental_objects"
    return "core_positive_objects"


def _probe_candidate_terms(text: str, *, person: str) -> list[str]:
    terms: list[str] = []
    boundary = r"(?=为|爲|任|参|參|兼|领|領|拜|使|相|将|將|，|。|、|；|;|,|$)"
    for match in re.finditer(rf"(拜|为|爲|任|使|举|舉|荐|薦|谏|諫|诛|誅|杀|殺|宠|幸)([\u4e00-\u9fff]{{2,4}}){boundary}", text):
        term = match.group(2)
        if term != person and _looks_like_person_term(term):
            _add_unique(terms, term)
    return terms


def _dedupe_candidates(candidates: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        name = str(candidate.get("object_name") or "").strip()
        if not name:
            continue
        item = merged.setdefault(
            name,
            {
                "object_name": name,
                "suggested_layer": str(candidate.get("suggested_layer") or "supplemental_objects"),
                "confidence": str(candidate.get("confidence") or "medium"),
                "supporting_rows": [],
                "reason": str(candidate.get("reason") or ""),
            },
        )
        if item["suggested_layer"] != "negative_or_reversal_objects" and candidate.get("suggested_layer") == "negative_or_reversal_objects":
            item["suggested_layer"] = "negative_or_reversal_objects"
        if item["confidence"] != "high" and candidate.get("confidence") == "high":
            item["confidence"] = "high"
        for ref in candidate.get("supporting_rows") or []:
            if ref not in item["supporting_rows"]:
                item["supporting_rows"].append(ref)
    return sorted(merged.values(), key=lambda item: (item["suggested_layer"], item["object_name"]))


def collect_online_probe_candidates(
    profile: Mapping[str, Any],
    *,
    max_queries: int,
    pages_per_query: int,
    timeout: int,
    request_delay_seconds: float,
    user_agent: str,
    use_source_filters: bool = False,
) -> list[dict[str, Any]]:
    person = str(profile.get("person") or "").strip()
    if not person:
        return []
    query_bundles = profile.get("query_bundles")
    queries = [str(query).strip() for query in query_bundles if str(query).strip()] if isinstance(query_bundles, list) else []
    if not queries:
        queries = _source_discovery_queries(profile, max_queries=max_queries)
    filters = source_title_filters(dict(profile)) if use_source_filters else ()
    context = FetchContext(
        request_delay_seconds=request_delay_seconds,
        max_retries=DEFAULT_MAX_RETRIES,
        retry_backoff_seconds=DEFAULT_RETRY_BACKOFF_SECONDS,
        retry_events=[],
        user_agent=user_agent,
    )
    candidates: list[dict[str, Any]] = []
    for query in queries[:max_queries]:
        try:
            pages = search_wikisource(query, limit=pages_per_query, timeout=timeout, title_filters=filters, fetch_context=context)
        except Exception:
            continue
        for page in pages:
            probe_text = f"{page.get('title', '')} {page.get('snippet', '')}"
            for term in _probe_candidate_terms(probe_text, person=person):
                candidates.append(
                    {
                        "object_name": term,
                        "suggested_layer": _layer_from_probe_query(query),
                        "confidence": "low",
                        "supporting_rows": [
                            {
                                "path": "online_wikisource_search",
                                "id": f"{query} -> {page.get('title', '')}",
                            }
                        ],
                        "reason": "来自显式 online-probe 的 Wikisource search snippet；需人工确认后才可写入 profile。",
                    }
                )
    return _dedupe_candidates(candidates)


def _person_alias_terms(profile: Mapping[str, Any]) -> tuple[str, ...]:
    terms: list[str] = []
    person = str(profile.get("person") or "").strip()
    _add_unique(terms, person)

    def add_alias(value: str) -> None:
        alias = value.strip()
        if not alias:
            return
        _add_unique(terms, alias)
        if len(alias) == 3 and alias.endswith("帝"):
            _add_unique(terms, alias[1:])
            _add_unique(terms, f"{alias[1]}皇帝")
        if len(alias) == 4 and alias.endswith("皇帝"):
            _add_unique(terms, alias[1:])

    title = str(profile.get("title") or "")
    for part in re.split(r"[\s,，、/]+", title):
        if 2 <= len(part) <= 5 and part != person and part.endswith(("帝", "王", "后", "太后", "汗")):
            add_alias(part)
    bundles = profile.get("query_bundles")
    if isinstance(bundles, list):
        for bundle in bundles:
            if not isinstance(bundle, str):
                continue
            for part in re.split(r"[\s,，、/]+", bundle):
                if 2 <= len(part) <= 5 and part != person and part.endswith(("帝", "王", "后", "太后", "汗")):
                    add_alias(part)
    return tuple(terms)


def _person_anchor_terms(profile: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(_person_alias_terms(profile))


def _candidate_context(text: str, start: int, end: int, *, context_chars: int) -> str:
    left = max(0, start - context_chars)
    right = min(len(text), end + context_chars)
    return re.sub(r"\s+", " ", text[left:right]).strip()


def _person_anchored_windows(text: str, person_terms: Sequence[str], *, context_chars: int) -> list[str]:
    window_chars = max(context_chars * 2, 160)
    spans: list[tuple[int, int]] = []
    for term in person_terms:
        if not term:
            continue
        if len(term) == 1 and text.count(term) > 40:
            continue
        for match in re.finditer(re.escape(term), text):
            spans.append((max(0, match.start() - window_chars), min(len(text), match.end() + window_chars)))
    if not spans:
        return []

    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            prev_start, prev_end = merged[-1]
            merged[-1] = (prev_start, max(prev_end, end))
    return [text[start:end] for start, end in merged]


def _extract_person_after_action(
    text: str,
    *,
    actions: Sequence[str],
    layer: str,
    reason: str,
    context_chars: int,
    person_terms: Sequence[str],
) -> list[dict[str, Any]]:
    action_pattern = "|".join(re.escape(action) for action in sorted(actions, key=len, reverse=True))
    office_pattern = "|".join(re.escape(office) for office in sorted(DISCOVERY_POSITIVE_OFFICES, key=len, reverse=True))
    pattern = rf"(?P<action>{action_pattern})(?P<name>[\u4e00-\u9fff]{{2,4}}?)(?P<tail>.{{0,4}}?)(?={office_pattern}|，|。|、|；|;|,|$)"
    candidates: list[dict[str, Any]] = []
    for match in re.finditer(pattern, text):
        name = match.group("name")
        action = match.group("action")
        following = text[match.end() : match.end() + 8]
        if action in {"任", "使", "命", "用"} and not any(following.startswith(office) for office in DISCOVERY_POSITIVE_OFFICES):
            continue
        context = _candidate_context(text, match.start(), match.end(), context_chars=context_chars)
        if name in person_terms or not _looks_like_discovery_person_term(name, context):
            continue
        candidates.append(
            {
                "object_name": name,
                "suggested_layer": layer,
                "confidence": "low",
                "supporting_rows": [],
                "reason": reason,
                "matched_action": action,
                "context": context,
            }
        )
    return candidates


def _extract_person_before_action(
    text: str,
    *,
    actions: Sequence[str],
    layer: str,
    reason: str,
    context_chars: int,
    person_terms: Sequence[str],
) -> list[dict[str, Any]]:
    action_pattern = "|".join(re.escape(action) for action in sorted(actions, key=len, reverse=True))
    pattern = rf"(?P<name>[\u4e00-\u9fff]{{2,4}})(?P<action>{action_pattern})"
    candidates: list[dict[str, Any]] = []
    for match in re.finditer(pattern, text):
        name = match.group("name")
        context = _candidate_context(text, match.start(), match.end(), context_chars=context_chars)
        if name in person_terms or not _looks_like_discovery_person_term(name, context):
            continue
        candidates.append(
            {
                "object_name": name,
                "suggested_layer": layer,
                "confidence": "low",
                "supporting_rows": [],
                "reason": reason,
                "matched_action": match.group("action"),
                "context": context,
            }
        )
    return candidates


def _extract_person_yiwei(
    text: str,
    *,
    layer: str,
    reason: str,
    context_chars: int,
    person_terms: Sequence[str],
) -> list[dict[str, Any]]:
    office_pattern = "|".join(re.escape(office) for office in sorted(DISCOVERY_POSITIVE_OFFICES, key=len, reverse=True))
    candidates: list[dict[str, Any]] = []
    for match in re.finditer(rf"以(?P<name>[\u4e00-\u9fff]{{2,4}}?)(?=为|爲)(?:为|爲)(?P<office>{office_pattern})", text):
        name = match.group("name")
        context = _candidate_context(text, match.start(), match.end(), context_chars=context_chars)
        if name in person_terms or not _looks_like_discovery_person_term(name, context):
            continue
        candidates.append(
            {
                "object_name": name,
                "suggested_layer": layer,
                "confidence": "low",
                "supporting_rows": [],
                "reason": reason,
                "matched_action": "以为",
                "context": context,
            }
        )
    return candidates


def _looks_like_anchor_page(text: str, anchor_terms: Sequence[str]) -> bool:
    head = text[:600]
    return any(term and term in head for term in anchor_terms)


def extract_source_discovery_candidates_from_text(
    text: str,
    *,
    profile: Mapping[str, Any],
    page_title: str,
    query: str,
    context_chars: int,
) -> list[dict[str, Any]]:
    person_terms = _person_alias_terms(profile)
    anchor_terms = _person_anchor_terms(profile)
    require_context_anchor = not _looks_like_anchor_page(text, anchor_terms)
    windows = [text] if not require_context_anchor else _person_anchored_windows(text, anchor_terms, context_chars=context_chars)
    if not windows:
        return []
    raw_candidates = [
        candidate
        for window in windows
        for candidate in (
            *_extract_person_after_action(
                window,
                actions=DISCOVERY_POSITIVE_ACTIONS,
                layer="core_positive_objects",
                reason="页面全文中靠近君主名号处出现任用、授官、授权类动作。",
                context_chars=context_chars,
                person_terms=person_terms,
            ),
            *_extract_person_yiwei(
                window,
                layer="core_positive_objects",
                reason="页面全文中出现“以某人为某官”的授官任用句式。",
                context_chars=context_chars,
                person_terms=person_terms,
            ),
            *_extract_person_before_action(
                window,
                actions=DISCOVERY_FEEDBACK_ACTIONS,
                layer="supplemental_objects",
                reason="页面全文中靠近君主名号处出现谏诤、上疏、直言类动作。",
                context_chars=context_chars,
                person_terms=person_terms,
            ),
            *_extract_person_after_action(
                window,
                actions=DISCOVERY_NEGATIVE_ACTIONS,
                layer="negative_or_reversal_objects",
                reason="页面全文中靠近君主名号处出现诛杀、贬黜、废罢等处置动作。",
                context_chars=context_chars,
                person_terms=person_terms,
            ),
            *_extract_person_before_action(
                window,
                actions=DISCOVERY_NEGATIVE_ACTIONS,
                layer="negative_or_reversal_objects",
                reason="页面全文中靠近君主名号处出现诛杀、贬黜、废罢等处置动作。",
                context_chars=context_chars,
                person_terms=person_terms,
            ),
            *_extract_person_after_action(
                window,
                actions=DISCOVERY_FAVOR_ACTIONS,
                layer="negative_or_reversal_objects",
                reason="页面全文中靠近君主名号处出现宠幸、亲信类风险动作。",
                context_chars=context_chars,
                person_terms=person_terms,
            ),
        )
    ]
    raw_candidates = [
        item
        for item in raw_candidates
        if not require_context_anchor or any(term in str(item.get("context") or "") for term in anchor_terms)
    ]
    candidates: list[dict[str, Any]] = []
    for item in raw_candidates:
        candidates.append(
            {
                "object_name": item["object_name"],
                "suggested_layer": item["suggested_layer"],
                "confidence": item["confidence"],
                "supporting_rows": [
                    {
                        "path": "source_discovery_page_text",
                        "id": f"{query} -> {page_title}",
                        "matched_action": item.get("matched_action", ""),
                        "context": item.get("context", ""),
                    }
                ],
                "reason": item["reason"],
            }
        )
    return candidates


def _is_discovery_page(title: str) -> bool:
    if not title.strip():
        return False
    if "全覽" in title or "全览" in title:
        return False
    return True


def _profile_source_variants(profile: Mapping[str, Any]) -> tuple[str, ...]:
    variants: list[str] = []
    for title in fallback_source_titles(dict(profile)):
        for variant in KNOWN_SOURCE_TITLE_VARIANTS.get(title, (title,)):
            _add_unique(variants, variant)
    return tuple(variants)


def _source_base_from_title(title: str, profile: Mapping[str, Any]) -> str:
    for variant in sorted(_profile_source_variants(profile), key=len, reverse=True):
        if title == variant or title.startswith(f"{variant} ") or title.startswith(f"{variant}(") or title.startswith(f"{variant}（"):
            return variant
        if title.startswith(f"{variant}/") or title.startswith(f"{variant}／"):
            return variant
    return ""


def _is_source_index_page(title: str, profile: Mapping[str, Any]) -> bool:
    base = _source_base_from_title(title, profile)
    return bool(base and "/" not in title and "／" not in title)


def _volume_width_for_source(source_title: str) -> int:
    if source_title in {"资治通鉴", "資治通鑑", "史记", "史記"}:
        return 3
    return 2


def _volume_numbers_from_text(text: str, *, limit: int = 8, anchor_terms: Sequence[str] = ()) -> list[int]:
    matches = list(re.finditer(r"卷\s*第?\s*(?P<number>[0-9]+|[零〇一二两兩三四五六七八九十百千]+)", text))
    anchored: list[int] = []
    compact_anchor_terms = [re.sub(r"\s+", "", term) for term in anchor_terms if term]
    for index, match in enumerate(matches):
        span_end = matches[index + 1].start() if index + 1 < len(matches) else min(len(text), match.end() + 120)
        segment = text[match.start() : span_end]
        compact_segment = re.sub(r"\s+", "", segment)
        if not any(term in compact_segment for term in compact_anchor_terms):
            continue
        number = chinese_numeral_to_int(match.group("number"))
        if number is not None and 0 < number < 1000 and number not in anchored:
            anchored.append(number)
            if len(anchored) >= limit:
                return anchored
    if compact_anchor_terms:
        return anchored

    numbers: list[int] = []
    number_pattern = r"[0-9]+|[零〇一二两兩三四五六七八九十百千]+"
    for match in re.finditer(rf"卷\s*第?\s*(?P<number>{number_pattern})", text):
        number = chinese_numeral_to_int(match.group("number"))
        if number is not None and 0 < number < 1000 and number not in numbers:
            numbers.append(number)
            if len(numbers) >= limit:
                break
    return numbers


def _expanded_page_titles_from_search_page(page: Mapping[str, Any], profile: Mapping[str, Any]) -> list[str]:
    title = str(page.get("title") or "")
    base = _source_base_from_title(title, profile)
    if not base or not _is_source_index_page(title, profile):
        return []
    haystack = f"{title} {page.get('snippet') or ''}"
    width = _volume_width_for_source(base)
    expanded: list[str] = []
    for number in _volume_numbers_from_text(haystack, anchor_terms=_person_anchor_terms(profile)):
        _add_unique(expanded, f"{base}/卷{number:0{width}d}")
    return expanded


def collect_source_discovery_candidates(
    profile: Mapping[str, Any],
    *,
    max_queries: int,
    pages_per_query: int,
    max_pages_per_person: int,
    context_chars: int,
    max_candidates: int,
    timeout: int,
    request_delay_seconds: float,
    user_agent: str,
    use_source_filters: bool = True,
    cache_enabled: bool | None = None,
    cache_backend: str | None = None,
    cache_dsn_env: str | None = None,
    cache_schema: str | None = None,
) -> list[dict[str, Any]]:
    person = str(profile.get("person") or "").strip()
    if not person:
        return []
    queries = _source_discovery_queries(profile, max_queries=max_queries)
    filters = source_title_filters(dict(profile)) if use_source_filters else ()
    cache_config = load_source_excerpt_cache_config()
    api_cache, page_text_cache, cache_store, _cache_report_config = make_cache_backends(
        cache_config=cache_config,
        cache_dir=None,
        cache_enabled=cache_enabled,
        cache_refresh=False,
        cache_backend=cache_backend,
        cache_dsn_env=cache_dsn_env,
        cache_schema=cache_schema,
    )
    context = FetchContext(
        request_delay_seconds=request_delay_seconds,
        max_retries=DEFAULT_MAX_RETRIES,
        retry_backoff_seconds=DEFAULT_RETRY_BACKOFF_SECONDS,
        retry_events=[],
        user_agent=user_agent,
        api_cache=api_cache,
        page_text_cache=page_text_cache,
    )
    page_sources: list[tuple[str, str]] = []
    seen_pages: set[str] = set()
    try:
        for query in queries:
            try:
                pages = search_wikisource(query, limit=pages_per_query, timeout=timeout, title_filters=filters, fetch_context=context)
            except Exception:
                continue
            for page in pages:
                title = str(page.get("title") or "")
                expanded_titles = _expanded_page_titles_from_search_page(page, profile)
                candidate_titles = [*expanded_titles]
                if _is_discovery_page(title) and not _is_source_index_page(title, profile):
                    candidate_titles.append(title)
                for candidate_title in candidate_titles:
                    if candidate_title in seen_pages or not _is_discovery_page(candidate_title):
                        continue
                    seen_pages.add(candidate_title)
                    page_sources.append((query, candidate_title))
                    if len(page_sources) >= max_pages_per_person:
                        break
                if len(page_sources) >= max_pages_per_person:
                    break
            if len(page_sources) >= max_pages_per_person:
                break

        candidates: list[dict[str, Any]] = []
        for query, title in page_sources:
            try:
                text = fetch_wikisource_plain_text(title, timeout=timeout, fetch_context=context)
            except Exception:
                continue
            candidates.extend(
                extract_source_discovery_candidates_from_text(
                    text,
                    profile=profile,
                    page_title=title,
                    query=query,
                    context_chars=context_chars,
                )
            )
            if len(candidates) >= max_candidates * 2:
                break
    finally:
        if cache_store is not None:
            cache_store.close()

    deduped = _dedupe_candidates(candidates)
    for item in deduped:
        if len(item["supporting_rows"]) >= 2:
            item["confidence"] = "medium"
    return deduped[:max_candidates]


def _existing_adjacent(profile: Mapping[str, Any]) -> list[str]:
    layers = profile.get("object_layers")
    if isinstance(layers, Mapping):
        values = layers.get("adjacent_split_objects")
        if isinstance(values, list):
            return [str(value).strip() for value in values if str(value).strip()]
    return ["军事成败", "制度治理成效", "政权安全案件", "财政经济政策"]


def _build_object_layers(profile: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
    layers = {
        "core_positive_objects": [],
        "supplemental_objects": [],
        "negative_or_reversal_objects": [],
        "adjacent_split_objects": _existing_adjacent(profile),
    }
    for candidate in candidates:
        layer = str(candidate.get("suggested_layer") or "supplemental_objects")
        if layer not in layers or layer == "adjacent_split_objects":
            layer = "supplemental_objects"
        _add_unique(layers[layer], str(candidate.get("object_name") or ""))
    return layers


def _build_queries(profile: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]], *, max_queries_per_person: int) -> list[str]:
    person = str(profile.get("person") or "").strip()
    source_titles = list(fallback_source_titles(dict(profile)))[:3]
    queries: list[str] = []
    for candidate in candidates:
        object_name = str(candidate.get("object_name") or "").strip()
        if not object_name:
            continue
        layer = str(candidate.get("suggested_layer") or "")
        contexts = ("任用 信任", "授权 容人") if layer != "negative_or_reversal_objects" else ("任用风险", "人才安全")
        for source_title in source_titles:
            for context in contexts:
                _add_unique(queries, f"{person} {object_name} {source_title} {context}")
                if len(queries) >= max_queries_per_person:
                    return queries
    if not queries:
        raw = profile.get("query_bundles")
        if isinstance(raw, list):
            for query in raw:
                _add_unique(queries, str(query))
                if len(queries) >= max_queries_per_person:
                    break
    return queries


def _source_discovery_queries(profile: Mapping[str, Any], *, max_queries: int) -> list[str]:
    person = str(profile.get("person") or "").strip()
    titles = list(fallback_source_titles(dict(profile)))[:4]
    templates = ("任用 授权 大臣", "谏臣 直言 纳谏", "功臣 团队 辅政", "宠臣 外戚 宗室 任用风险")
    queries: list[str] = []
    for title in titles:
        _add_unique(queries, f"{person} {title}")
        if len(queries) >= max_queries:
            return queries
    for alias in _person_alias_terms(profile):
        if alias == person:
            continue
        for title in titles:
            _add_unique(queries, f"{alias} {title}")
            if len(queries) >= max_queries:
                return queries
    for title in titles:
        for template in templates:
            _add_unique(queries, f"{person} {title} {template}")
            if len(queries) >= max_queries:
                return queries
    return queries


def build_seed_candidate(
    profile: Mapping[str, Any],
    row: Mapping[str, Any],
    *,
    source_rows: Sequence[tuple[Path, Mapping[str, Any]]],
    online_candidates: Sequence[Mapping[str, Any]] = (),
    max_queries_per_person: int,
) -> dict[str, Any]:
    person = str(row.get("person") or profile.get("person") or "").strip()
    candidates = _dedupe_candidates([*collect_local_candidates(person, source_rows), *online_candidates])
    layers = _build_object_layers(profile, candidates)
    readyish = bool(layers["core_positive_objects"] or layers["negative_or_reversal_objects"])
    return {
        "person": person,
        "query_profile_id": profile.get("query_profile_id") or "",
        "action_status": row.get("action_status") or "",
        "status": "seed_candidates_generated" if candidates else "needs_external_discovery",
        "ready_for_profile_review": readyish,
        "requires_review": True,
        "candidate_objects": candidates,
        "seed_profile_patch_candidate": {
            "replace_object_layers": layers if candidates else {},
            "append_query_bundles": _build_queries(profile, candidates, max_queries_per_person=max_queries_per_person) if candidates else [],
            "merge_object_search_aliases": {},
        },
        "discovery_queries": _source_discovery_queries(profile, max_queries=max_queries_per_person),
        "note": "候选只用于把半成品 profile 推进到人工审查；脚本不直接改 query profile。",
    }


def build_seed_report(
    *,
    profiles: Mapping[str, dict[str, Any]],
    status_rows: Sequence[Mapping[str, Any]],
    source_rows: Sequence[tuple[Path, Mapping[str, Any]]],
    workflow_code: str = DEFAULT_WORKFLOW_CODE,
    persons: Sequence[str] = (),
    target_statuses: Sequence[str] = DEFAULT_TARGET_STATUSES,
    max_queries_per_person: int = 12,
    online_probe: bool = False,
    online_probe_queries_per_person: int = 4,
    online_pages_per_query: int = 3,
    timeout: int = 20,
    request_delay_seconds: float = DEFAULT_REQUEST_DELAY_SECONDS,
    user_agent: str = DEFAULT_USER_AGENT,
    online_probe_source_filter: bool = False,
    source_discovery: bool = False,
    source_discovery_queries_per_person: int = 4,
    source_discovery_pages_per_query: int = 3,
    source_discovery_max_pages_per_person: int = 6,
    source_discovery_context_chars: int = 80,
    source_discovery_max_candidates: int = 20,
    source_discovery_source_filter: bool = True,
    cache_enabled: bool | None = None,
    cache_backend: str | None = None,
    cache_dsn_env: str | None = None,
    cache_schema: str | None = None,
) -> dict[str, Any]:
    normalized_workflow_code = normalize_workflow_code(workflow_code)
    person_filter = {person for person in persons if person}
    status_filter = set(target_statuses)
    selected_rows = [
        row
        for row in status_rows
        if (not person_filter or row.get("person") in person_filter)
        and (not status_filter or row.get("action_status") in status_filter)
    ]
    seeds: list[dict[str, Any]] = []
    for row in selected_rows:
        profile = profiles.get(str(row.get("person") or ""), {})
        online_candidates: list[dict[str, Any]] = []
        if online_probe:
            online_candidates.extend(
                collect_online_probe_candidates(
                    profile,
                    max_queries=online_probe_queries_per_person,
                    pages_per_query=online_pages_per_query,
                    timeout=timeout,
                    request_delay_seconds=request_delay_seconds,
                    user_agent=user_agent,
                    use_source_filters=online_probe_source_filter,
                )
            )
        if source_discovery:
            online_candidates.extend(
                collect_source_discovery_candidates(
                    profile,
                    max_queries=source_discovery_queries_per_person,
                    pages_per_query=source_discovery_pages_per_query,
                    max_pages_per_person=source_discovery_max_pages_per_person,
                    context_chars=source_discovery_context_chars,
                    max_candidates=source_discovery_max_candidates,
                    timeout=timeout,
                    request_delay_seconds=request_delay_seconds,
                    user_agent=user_agent,
                    use_source_filters=source_discovery_source_filter,
                    cache_enabled=cache_enabled,
                    cache_backend=cache_backend,
                    cache_dsn_env=cache_dsn_env,
                    cache_schema=cache_schema,
                )
            )
        seeds.append(
            build_seed_candidate(
                profile,
                row,
                source_rows=source_rows,
                online_candidates=online_candidates,
                max_queries_per_person=max_queries_per_person,
            )
        )
    return {
        "workflow_code": normalized_workflow_code,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "review_required": True,
        "target_statuses": list(target_statuses),
        "totals": {
            "persons": len(seeds),
            "with_local_candidates": sum(1 for item in seeds if item["candidate_objects"]),
            "candidate_objects": sum(len(item["candidate_objects"]) for item in seeds),
            "ready_for_profile_review": sum(1 for item in seeds if item["ready_for_profile_review"]),
        },
        "seeds": seeds,
}


def _markdown_cell(value: str) -> str:
    return " ".join(value.replace("|", "/").split())


def render_markdown(report: Mapping[str, Any]) -> str:
    totals = report.get("totals") if isinstance(report.get("totals"), Mapping) else {}
    workflow_code = str(report.get("workflow_code") or DEFAULT_WORKFLOW_CODE)
    lines = [
        f"# {workflow_code} 半成品检索包种子候选",
        "",
        f"- workflow_code: `{workflow_code}`",
        f"- generated_at: `{report.get('generated_at') or ''}`",
        f"- persons: `{totals.get('persons', 0)}`",
        f"- with_local_candidates: `{totals.get('with_local_candidates', 0)}`",
        f"- candidate_objects: `{totals.get('candidate_objects', 0)}`",
        f"- ready_for_profile_review: `{totals.get('ready_for_profile_review', 0)}`",
        "- review_required: `true`",
        "",
        "候选只用于审查，不会自动改 query profile，也不会投抓包队列。",
        "",
    ]
    for seed in report.get("seeds") or []:
        if not isinstance(seed, Mapping):
            continue
        lines.extend([f"## {seed.get('person', '')}", ""])
        lines.append(f"- status: `{seed.get('status', '')}`")
        lines.append(f"- ready_for_profile_review: `{str(seed.get('ready_for_profile_review', False)).lower()}`")
        candidates = seed.get("candidate_objects") if isinstance(seed.get("candidate_objects"), list) else []
        if candidates:
            lines.append("| 对象 | 建议层 | 置信度 | 支撑 | 摘录 |")
            lines.append("| --- | --- | --- | --- | --- |")
            for candidate in candidates:
                refs = candidate.get("supporting_rows") if isinstance(candidate.get("supporting_rows"), list) else []
                ref_text = "、".join(str(ref.get("id") or ref.get("path") or "") for ref in refs[:3] if isinstance(ref, Mapping))
                contexts = [
                    _markdown_cell(str(ref.get("context") or ""))[:80]
                    for ref in refs[:2]
                    if isinstance(ref, Mapping) and ref.get("context")
                ]
                lines.append(
                    f"| {candidate.get('object_name', '')} | {candidate.get('suggested_layer', '')} | {candidate.get('confidence', '')} | {ref_text} | {'；'.join(contexts)} |"
                )
        lines.append("- discovery_queries:")
        for query in seed.get("discovery_queries") or []:
            lines.append(f"  - {query}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate review-only seed candidates for half-baked I5B query profiles.")
    parser.add_argument("--profile", type=Path, default=None)
    parser.add_argument("--workflow-code", default=DEFAULT_WORKFLOW_CODE, help="Workflow/subitem code for report metadata and status discovery.")
    parser.add_argument("--status-report", type=Path, default=None)
    parser.add_argument("--source-pack-root", type=Path, default=None)
    parser.add_argument("--all-list", type=Path, default=DEFAULT_ALL_LIST)
    parser.add_argument("--jobs-dir", type=Path, default=None)
    parser.add_argument("--logs-dir", type=Path, default=None)
    parser.add_argument("--candidate-source", action="append", type=Path, default=[])
    parser.add_argument("--person", action="append", default=[])
    parser.add_argument("--status", action="append", default=[])
    parser.add_argument("--max-queries-per-person", type=int, default=12)
    parser.add_argument("--online-probe", action="store_true", help="Run small Wikisource search probes to discover concrete object candidates.")
    parser.add_argument("--online-probe-queries-per-person", type=int, default=4)
    parser.add_argument("--online-pages-per-query", type=int, default=3)
    parser.add_argument("--online-probe-source-filter", action="store_true", help="Restrict online probe search results to source titles in the profile.")
    parser.add_argument(
        "--source-discovery",
        action="store_true",
        help="Search and fetch Wikisource page text to discover review-only object candidates for half-baked profiles.",
    )
    parser.add_argument("--source-discovery-queries-per-person", type=int, default=4)
    parser.add_argument("--source-discovery-pages-per-query", type=int, default=3)
    parser.add_argument("--source-discovery-max-pages-per-person", type=int, default=6)
    parser.add_argument("--source-discovery-context-chars", type=int, default=80)
    parser.add_argument("--source-discovery-max-candidates", type=int, default=20)
    parser.add_argument(
        "--source-discovery-no-source-filter",
        action="store_false",
        dest="source_discovery_source_filter",
        help="Do not restrict source-discovery search results to source titles in the profile.",
    )
    parser.set_defaults(source_discovery_source_filter=True)
    parser.add_argument("--no-cache", action="store_true", help="Disable source-discovery API/page-text cache for this run.")
    parser.add_argument("--cache-backend", choices=("filesystem", "postgres"), default=None)
    parser.add_argument("--cache-dsn-env", default=None)
    parser.add_argument("--cache-schema", default=None)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--request-delay", type=float, default=DEFAULT_REQUEST_DELAY_SECONDS)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    workflow_code = normalize_workflow_code(args.workflow_code)
    source_paths = load_source_excerpt_pool_paths(workflow_code=workflow_code)
    profile_path = args.profile or source_paths.get("query_profile") or DEFAULT_PROFILE
    source_pack_root = args.source_pack_root or source_paths.get("source_pack_root") or _default_source_pack_root(workflow_code=workflow_code)
    jobs_dir = args.jobs_dir or source_paths.get("jobs_dir") or source_pack_root.parent / "jobs"
    logs_dir = args.logs_dir or source_paths.get("logs_dir") or source_pack_root.parent / "logs"
    profiles = load_profile_rows(profile_path, workflow_code=workflow_code) if profile_path.exists() else {}
    status_rows = load_status_rows(
        status_report=args.status_report,
        profile_path=profile_path,
        source_pack_root=source_pack_root,
        all_list=args.all_list,
        jobs_dir=jobs_dir,
        logs_dir=logs_dir,
        workflow_code=workflow_code,
    )
    source_rows = _read_source_rows(args.candidate_source or list(DEFAULT_CANDIDATE_SOURCES))
    report = build_seed_report(
        profiles=profiles,
        status_rows=status_rows,
        source_rows=source_rows,
        workflow_code=workflow_code,
        persons=args.person,
        target_statuses=args.status or list(DEFAULT_TARGET_STATUSES),
        max_queries_per_person=args.max_queries_per_person,
        online_probe=args.online_probe,
        online_probe_queries_per_person=args.online_probe_queries_per_person,
        online_pages_per_query=args.online_pages_per_query,
        timeout=args.timeout,
        request_delay_seconds=args.request_delay,
        user_agent=args.user_agent,
        online_probe_source_filter=args.online_probe_source_filter,
        source_discovery=args.source_discovery,
        source_discovery_queries_per_person=args.source_discovery_queries_per_person,
        source_discovery_pages_per_query=args.source_discovery_pages_per_query,
        source_discovery_max_pages_per_person=args.source_discovery_max_pages_per_person,
        source_discovery_context_chars=args.source_discovery_context_chars,
        source_discovery_max_candidates=args.source_discovery_max_candidates,
        source_discovery_source_filter=args.source_discovery_source_filter,
        cache_enabled=False if args.no_cache else None,
        cache_backend=args.cache_backend,
        cache_dsn_env=args.cache_dsn_env,
        cache_schema=args.cache_schema,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n" if args.format == "json" else render_markdown(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
