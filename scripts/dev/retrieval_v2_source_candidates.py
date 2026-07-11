from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v2_contracts import (
    alias_script_variants,
    coverage_matrix_template,
    gap_type_for_role_family,
    role_family_terms as contract_role_family_terms,
    unique_strings,
)
from scripts.dev import retrieval_v2_candidate_prompt as candidate_prompt
from scripts.dev.retrieval_v2_public_ocr import extract_public_ocr_text
from scripts.dev.retrieval_v2_source_document_policy import source_document_skip

DEFAULT_CACHE_DIR = ROOT / "tmp" / "retrieval_v2_source_cache"
WIKISOURCE_API = "https://zh.wikisource.org/w/api.php"
USER_AGENT = "emperor-evaluation-retrieval-v2/0.1"
CONDITIONAL_RECALL_GUARD_WINDOW_CHARS = 48
DEFAULT_RULE_TERMS = (
    "命",
    "授",
    "拜",
    "遣",
    "使",
    "委",
    "委決",
    "统",
    "統",
    "总管",
    "總管",
    "元帅",
    "元帥",
    "节度",
    "節度",
    "便宜",
    "行事",
    "留守",
    "镇",
    "鎮",
    "率师",
    "率師",
    "征",
    "讨",
    "討",
    "招慰",
    "行军",
    "行軍",
    "大都督",
)
DEFAULT_OUTCOME_TERMS = (
    "败",
    "敗",
    "败绩",
    "敗績",
    "大溃",
    "大潰",
    "陷",
    "弃",
    "棄",
    "杀",
    "殺",
    "诛",
    "誅",
    "除名",
    "属吏",
    "屬吏",
    "坐",
    "无捍御之才",
    "無捍禦之才",
    "惶骇",
    "惶駭",
    "乱",
    "亂",
    "谋",
    "謀",
    "反",
)
ALIAS_STRENGTH_SCORES = {"strong": 12, "medium": 8, "weak": 2}
DELEGATION_AUTHORITY_TERMS = (
    "命",
    "令",
    "遣",
    "使",
    "拜",
    "授",
    "任",
    "以为",
    "以爲",
    "诏",
    "詔",
    "委",
)
DELEGATION_TASK_TERMS = (
    "将",
    "將",
    "帅",
    "帥",
    "率",
    "统",
    "統",
    "大将军",
    "大將軍",
    "副将军",
    "副將軍",
    "征",
    "讨",
    "討",
    "取",
    "守",
    "镇",
    "鎮",
    "出师",
    "出師",
    "行省",
    "按察",
    "巡行",
    "理",
    "抚纳",
    "撫納",
)
DELEGATION_RESULT_TERMS = (
    "克",
    "平",
    "定",
    "下",
    "破",
    "败",
    "敗",
    "降",
    "安",
    "击却",
    "擊卻",
    "诸郡皆下",
    "諸郡皆下",
    "民甚安",
    "寇盗尽平",
    "寇盜盡平",
    "献",
    "獻",
)
DISPOSITION_NOISE_TERMS = (
    "诛",
    "誅",
    "坐",
    "罪",
    "谋反",
    "謀反",
    "伏诛",
    "伏誅",
    "赐死",
    "賜死",
    "连坐",
    "連坐",
)
NEGATIVE_AD_POWER_ABUSE_TERMS = (
    "宠任",
    "寵任",
    "专擅",
    "專擅",
    "威福",
    "弄权",
    "弄權",
    "壅蔽",
    "不奏",
    "径行",
    "徑行",
    "封事",
    "匿闻",
    "匿聞",
    "奔竞",
    "奔競",
    "趋附",
    "趨附",
)
I5B_ITEM_WIDE_MATERIAL_TERMS = (
    "荐",
    "薦",
    "举",
    "舉",
    "拔",
    "擢",
    "任",
    "信",
    "相",
    "辅",
    "輔",
    "将",
    "將",
    "保全",
    "容",
    "谏",
    "諫",
    "诤",
    "諍",
    "直言",
    "上疏",
    "纳谏",
    "納諫",
    "问策",
    "問策",
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
    "从谏",
    "從諫",
    "拒谏",
    "拒諫",
    "改过",
    "改過",
    "弊政",
    "监察",
    "監察",
    "削藩",
    "撤藩",
    "收兵权",
    "收兵權",
    "夺兵权",
    "奪兵權",
    "军权",
    "軍權",
    "兵权",
    "兵權",
    "权臣",
    "權臣",
    "军头",
    "軍頭",
    "外戚",
    "宦官",
    "宗室",
    "禁军",
    "禁軍",
    "矫诏",
    "矯詔",
    "擅权",
    "擅權",
    "猜忌",
    "滥杀",
    "濫殺",
    "妄杀",
    "妄殺",
    "冤杀",
    "冤殺",
    "族诛",
    "族誅",
    "株连",
    "株連",
    "牵连",
    "牽連",
    "罗织",
    "羅織",
    "构陷",
    "構陷",
    "大狱",
    "大獄",
    "迁都",
    "遷都",
    "废立",
    "廢立",
    "立太子",
    "废太子",
    "廢太子",
    "继承",
    "繼承",
    "罢兵",
    "罷兵",
    "休兵",
    "班师",
    "班師",
    "议和",
    "議和",
    "和亲",
    "和親",
    "边疆",
    "邊疆",
    "边镇",
    "邊鎮",
    "设治",
    "設治",
    "羁縻",
    "羈縻",
    "都护",
    "都護",
    "关隘",
    "關隘",
    "屯田",
    "收复",
    "收復",
    "失地",
    "入寇",
    "屠",
    "坑",
    "连坐",
    "連坐",
    "告发",
    "告發",
    "诏狱",
    "詔獄",
    "徭役",
    "横征",
    "橫征",
    "民变",
    "民變",
    "崩坏",
    "崩壞",
    "亲",
    "親",
    "党",
    "黨",
    "贿",
    "賄",
    "专",
    "專",
    *NEGATIVE_AD_POWER_ABUSE_TERMS,
)


class RetrievalV2CandidateError(RuntimeError):
    pass


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def stable_fingerprint(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def strip_html(value: str) -> str:
    without_scripts = re.sub(r"<(script|style)\b.*?</\1>", " ", value, flags=re.IGNORECASE | re.DOTALL)
    without_tags = re.sub(r"<[^>]+>", " ", without_scripts)
    return compact_text(html.unescape(without_tags))


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


def normalized_alias_strength(value: Any) -> str:
    strength = str(value or "").strip().lower()
    if strength in ALIAS_STRENGTH_SCORES:
        return strength
    if strength in {"name", "primary_name", "courtesy_name", "zi"}:
        return "strong"
    if strength in {"title", "office", "rank", "fief", "honorific"}:
        return "medium"
    if strength in {"posthumous", "temple_name", "generic_title", "weak_title"}:
        return "weak"
    return "strong"


def alias_entries(seed: Mapping[str, Any]) -> list[dict[str, str]]:
    strengths = seed.get("alias_strengths") or {}
    if not isinstance(strengths, Mapping):
        strengths = {}
    rows: list[dict[str, str]] = []
    primary_name = str(seed.get("name") or seed.get("object_name") or seed.get("primary_name") or "").strip()
    if primary_name:
        rows.append({"alias": primary_name, "strength": "strong"})
    for raw_alias in seed.get("aliases") or []:
        if isinstance(raw_alias, Mapping):
            alias = str(
                raw_alias.get("alias")
                or raw_alias.get("name")
                or raw_alias.get("label")
                or raw_alias.get("text")
                or raw_alias.get("value")
                or ""
            ).strip()
            strength = normalized_alias_strength(
                raw_alias.get("strength") or raw_alias.get("alias_strength") or raw_alias.get("alias_type")
            )
        else:
            alias = str(raw_alias or "").strip()
            strength = normalized_alias_strength(strengths.get(alias))
        if alias:
            rows.append({"alias": alias, "strength": strength})
    deduped: dict[str, str] = {}
    for row in rows:
        alias = row["alias"]
        strength = row["strength"]
        current = deduped.get(alias)
        if current is None or ALIAS_STRENGTH_SCORES[strength] > ALIAS_STRENGTH_SCORES[current]:
            deduped[alias] = strength
    expanded: dict[str, str] = {}
    for alias, strength in deduped.items():
        variants = alias_script_variants(alias) if strength in {"strong", "medium"} else [alias]
        for variant in unique_strings([alias, *variants]):
            current = expanded.get(variant)
            if current is None or ALIAS_STRENGTH_SCORES[strength] > ALIAS_STRENGTH_SCORES[current]:
                expanded[variant] = strength
    return [{"alias": alias, "strength": strength} for alias, strength in expanded.items()]


def object_seed_name(seed: Mapping[str, Any]) -> str:
    explicit = str(seed.get("name") or seed.get("object_name") or seed.get("primary_name") or "").strip()
    if explicit:
        return explicit
    aliases = alias_entries(seed)
    for row in aliases:
        if row["strength"] == "strong":
            return row["alias"]
    if aliases:
        return aliases[0]["alias"]
    return ""


def matched_alias_strengths(text: str, aliases: Sequence[Mapping[str, str]]) -> dict[str, str]:
    return {row["alias"]: row["strength"] for row in aliases if row.get("alias") and row["alias"] in text}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RetrievalV2CandidateError(f"expected object JSON: {path}")
    return payload


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    atomic_write_text(path, pretty_json(dict(payload)))


def cache_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def cache_paths(cache_dir: Path, source_key: str) -> tuple[Path, Path]:
    stem = cache_key(source_key)
    return cache_dir / f"{stem}.txt", cache_dir / f"{stem}.meta.json"


def read_cached_text(cache_dir: Path, source_key: str) -> tuple[str, dict[str, Any]] | None:
    text_path, meta_path = cache_paths(cache_dir, source_key)
    if not text_path.exists() or not meta_path.exists():
        return None
    return text_path.read_text(encoding="utf-8"), load_json(meta_path)


def write_cached_text(cache_dir: Path, source_key: str, text: str, meta: Mapping[str, Any]) -> None:
    text_path, meta_path = cache_paths(cache_dir, source_key)
    atomic_write_text(text_path, text)
    atomic_write_json(meta_path, dict(meta))


def request_text(url: str, *, timeout: int) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    delays = (1.0, 2.0, 4.0, 8.0)
    for attempt, delay in enumerate((*delays, 0.0), start=1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            retryable = exc.code == 429 or 500 <= exc.code <= 599
            if not retryable or attempt > len(delays):
                raise
            time.sleep(delay)


def mediawiki_api_url(params: Mapping[str, str]) -> str:
    return f"{WIKISOURCE_API}?{urllib.parse.urlencode(dict(params))}"


def fetch_wikisource_title(title: str, *, timeout: int) -> str:
    fallback_match = re.search(r"/卷(\d{1,2})$", title)
    payload_text = request_text(
        mediawiki_api_url(
            {
                "action": "parse",
                "page": title,
                "prop": "text",
                "format": "json",
                "utf8": "1",
                "redirects": "1",
                "variant": "zh-hans",
            }
        ),
        timeout=timeout,
    )
    payload = json.loads(payload_text)
    html_text = payload.get("parse", {}).get("text", {}).get("*", "")
    if (not isinstance(html_text, str) or not html_text) and fallback_match:
        width = 3 if "資治通鑑" in title or "资治通鉴" in title else 2
        fallback_title = title[: fallback_match.start(1)] + fallback_match.group(1).zfill(width)
        if fallback_title != title:
            return fetch_wikisource_title(fallback_title, timeout=timeout)
    if not isinstance(html_text, str) or not html_text:
        raise RetrievalV2CandidateError(f"empty Wikisource page: {title}")
    return strip_html(html_text)


def fetch_document_text(
    document: Mapping[str, Any],
    *,
    cache_dir: Path,
    timeout: int,
) -> tuple[str, dict[str, Any]]:
    if isinstance(document.get("text"), str):
        return compact_text(str(document["text"])), {"cache_status": "embedded"}
    source_kind = str(document.get("source_kind") or "").strip()
    title = str(document.get("wikisource_title") or document.get("title") or "").strip()
    url = str(document.get("url") or "").strip()
    if document.get("fetch_mode") == "url" or (source_kind and "wikisource" not in source_kind):
        title = ""
    source_key = f"wikisource:{title}" if title else f"url:{url}"
    if not source_key.endswith(":"):
        cached = read_cached_text(cache_dir, source_key)
        if cached is not None:
            text, meta = cached
            meta["cache_status"] = "hit"
            return text, meta

    if title:
        try:
            text = fetch_wikisource_title(title, timeout=timeout)
            meta = {"cache_status": "miss", "source_kind": "wikisource", "source_key": source_key}
        except RetrievalV2CandidateError:
            if not url:
                raise
            raw_html = request_text(url, timeout=timeout)
            text, extractor = extract_public_ocr_text(url, raw_html)
            text = text if extractor else strip_html(raw_html)
            meta = {"cache_status": "miss", "source_kind": "url_fallback", "source_key": source_key, "fallback_url": url, **({"content_extractor": extractor} if extractor else {})}
    elif url:
        raw_html = request_text(url, timeout=timeout)
        text, extractor = extract_public_ocr_text(url, raw_html)
        text = text if extractor else strip_html(raw_html)
        meta = {"cache_status": "miss", "source_kind": "url", "source_key": source_key, **({"content_extractor": extractor} if extractor else {})}
    else:
        raise RetrievalV2CandidateError("document requires text, wikisource_title/title, or url")
    write_cached_text(cache_dir, source_key, text, meta)
    return text, meta


def object_aliases(seed: Mapping[str, Any]) -> list[str]:
    return [row["alias"] for row in alias_entries(seed)]


def rule_terms(task: Mapping[str, Any]) -> list[str]:
    terms: list[Any] = []
    terms.extend(task.get("rule_terms") or [])
    terms.extend(task.get("query_terms") or [])
    rule = task.get("rule") or task.get("rule_contract") or {}
    if isinstance(rule, Mapping):
        terms.extend(rule.get("keywords") or [])
        terms.extend(rule.get("predicate_candidates") or [])
    if rule_code(task) == "i5b_item_wide":
        terms.extend(I5B_ITEM_WIDE_MATERIAL_TERMS)
    if not terms:
        terms.extend(DEFAULT_RULE_TERMS)
    return unique_strings(terms)


def conditional_recall_terms(task: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for overlay in task.get("recall_term_overlays") or []:
        if not isinstance(overlay, Mapping):
            continue
        for raw in overlay.get("conditional_terms_not_injected") or overlay.get("conditional_terms") or []:
            if not isinstance(raw, Mapping):
                continue
            term = str(raw.get("term") or "").strip()
            guard = raw.get("guard") if isinstance(raw.get("guard"), Mapping) else {}
            requires_near_any = unique_strings(guard.get("requires_near_any") or [])
            if term and requires_near_any:
                rows.append(
                    {
                        "term": term,
                        "requires_near_any": requires_near_any,
                        "policy_group": raw.get("policy_group"),
                        "risk_level": raw.get("risk_level"),
                    }
                )
    seen: set[tuple[str, tuple[str, ...]]] = set()
    result: list[dict[str, Any]] = []
    for row in rows:
        key = (str(row["term"]), tuple(row["requires_near_any"]))
        if key not in seen:
            seen.add(key)
            result.append(row)
    return result


def outcome_terms(task: Mapping[str, Any]) -> list[str]:
    terms: list[Any] = []
    terms.extend(task.get("outcome_terms") or [])
    if not terms:
        terms.extend(DEFAULT_OUTCOME_TERMS)
    return unique_strings(terms)


def target_aliases(task: Mapping[str, Any]) -> list[str]:
    profile = task.get("target_profile") or {}
    if not isinstance(profile, Mapping):
        return []
    return unique_strings([profile.get("primary_name"), *(profile.get("aliases") or []), *(profile.get("must_check_titles") or [])])


def rule_code(task: Mapping[str, Any]) -> str:
    explicit = str(task.get("rule_code") or "").strip()
    if explicit:
        return explicit
    rule = task.get("rule") or task.get("rule_contract") or {}
    if isinstance(rule, Mapping):
        return str(rule.get("rule_code") or rule.get("code") or "").strip()
    return ""


def task_coverage_matrix(task: Mapping[str, Any]) -> dict[str, Any]:
    for value in (
        task.get("coverage_matrix"),
        (task.get("rule") or {}).get("coverage_matrix") if isinstance(task.get("rule"), Mapping) else None,
        (task.get("rule_contract") or {}).get("coverage_matrix") if isinstance(task.get("rule_contract"), Mapping) else None,
    ):
        if isinstance(value, Mapping) and value.get("role_families"):
            return dict(value)
    return json.loads(stable_json(coverage_matrix_template(rule_code(task))))


def role_family_terms(task: Mapping[str, Any]) -> dict[str, list[str]]:
    matrix = task_coverage_matrix(task)
    result: dict[str, list[str]] = {}
    for raw_family in matrix.get("role_families") or []:
        if not isinstance(raw_family, Mapping):
            continue
        family_code = str(raw_family.get("family_code") or "").strip()
        if not family_code:
            continue
        terms: list[Any] = []
        terms.extend(raw_family.get("match_terms") or [])
        terms.extend(raw_family.get("keywords") or [])
        if not terms:
            terms.extend(contract_role_family_terms(str(matrix.get("rule_code") or rule_code(task)), family_code))
        result[family_code] = unique_strings(terms)
    return result


def iter_term_positions(text: str, terms: Sequence[str]) -> Iterable[tuple[str, int]]:
    for term in terms:
        start = 0
        while True:
            index = text.find(term, start)
            if index < 0:
                break
            yield term, index
            start = index + max(1, len(term))


def context_bounds(text: str, center: int, *, context_chars: int) -> tuple[int, int]:
    start = max(0, center - context_chars)
    end = min(len(text), center + context_chars)
    for mark in ("。", "！", "？", "\n"):
        prev = text.rfind(mark, 0, start)
        if prev >= 0 and start - prev < context_chars // 2:
            start = prev + 1
            break
    for mark in ("。", "！", "？", "\n"):
        next_index = text.find(mark, end)
        if next_index >= 0 and next_index - end < context_chars // 2:
            end = next_index + 1
            break
    return start, end


def object_section_start(text: str, object_name: str, position: int) -> int | None:
    if not object_name:
        return None
    heading_bounds: list[tuple[int, int]] = []
    for name in unique_strings([object_name, *alias_script_variants(object_name)]):
        for marker in (f"{name} [ 编辑 ]", f"{name}[编辑]", f"{name} [ 編輯 ]", f"{name}[編輯]"):
            start = text.rfind(marker, 0, position + len(marker))
            if start >= 0:
                heading_bounds.append((start, start + len(marker)))
    if not heading_bounds:
        return None
    section_start, _heading_end = max(heading_bounds, key=lambda row: row[0])
    return section_start


def object_scoped_context_bounds(
    text: str,
    object_name: str,
    center: int,
    *,
    context_chars: int,
) -> tuple[int, int]:
    start, end = context_bounds(text, center, context_chars=context_chars)
    section_start = object_section_start(text, object_name, center)
    if section_start is None:
        return start, end
    return max(start, section_start), end


def parse_char_locator(value: Any) -> tuple[int, int] | None:
    match = re.fullmatch(r"chars:(\d+)-(\d+)", str(value or "").strip())
    if not match:
        return None
    start = int(match.group(1))
    end = int(match.group(2))
    if end < start:
        return None
    return start, end


def terms_in_text(text: str, terms: Sequence[str]) -> list[str]:
    return [term for term in terms if term and term in text]


def conditional_terms_in_text(
    text: str,
    conditional_terms: Sequence[Mapping[str, Any]],
    *,
    guard_window_chars: int = CONDITIONAL_RECALL_GUARD_WINDOW_CHARS,
) -> list[str]:
    matches: list[str] = []
    for row in conditional_terms:
        term = str(row.get("term") or "").strip()
        guard_terms = [
            guard_term
            for guard_term in unique_strings(row.get("requires_near_any") or [])
            if guard_term != term and guard_term not in term
        ]
        if not term or not guard_terms:
            continue
        start = 0
        while True:
            index = text.find(term, start)
            if index < 0:
                break
            window_start = max(0, index - guard_window_chars)
            window_end = min(len(text), index + len(term) + guard_window_chars)
            if terms_in_text(text[window_start:window_end], guard_terms):
                matches.append(term)
                break
            start = index + max(1, len(term))
    return unique_strings(matches)


def delegation_chain_signal_profile(text: str) -> dict[str, Any]:
    authority_terms = terms_in_text(text, DELEGATION_AUTHORITY_TERMS)
    task_terms = terms_in_text(text, DELEGATION_TASK_TERMS)
    result_terms = terms_in_text(text, DELEGATION_RESULT_TERMS)
    disposition_terms = terms_in_text(text, DISPOSITION_NOISE_TERMS)
    item_wide_terms = terms_in_text(text, I5B_ITEM_WIDE_MATERIAL_TERMS)
    negative_ad_power_abuse_terms = terms_in_text(text, NEGATIVE_AD_POWER_ABUSE_TERMS)
    has_authority = bool(authority_terms)
    has_task = bool(task_terms)
    has_result = bool(result_terms)
    has_disposition_noise = bool(disposition_terms)
    return {
        "authority_terms": authority_terms,
        "task_terms": task_terms,
        "result_terms": result_terms,
        "disposition_noise_terms": disposition_terms,
        "item_wide_terms": item_wide_terms,
        "negative_ad_power_abuse_terms": negative_ad_power_abuse_terms,
        "has_full_delegation_chain": has_authority and has_task and has_result,
        "has_authority_task_chain": has_authority and has_task,
        "has_task_result_chain": has_task and has_result,
        "has_item_wide_signal": bool(item_wide_terms),
        "has_negative_ad_power_abuse_signal": bool(negative_ad_power_abuse_terms),
        "disposition_noise_only": has_disposition_noise and not (has_authority and has_task and has_result),
    }


def delegation_chain_signal_score(text: str) -> int:
    profile = delegation_chain_signal_profile(text)
    score = 0
    if profile["has_full_delegation_chain"]:
        score += 24
    elif profile["has_authority_task_chain"]:
        score += 12
    elif profile["has_task_result_chain"]:
        score += 8
    if profile["disposition_noise_only"]:
        score -= 14
    return score


def slice_score(
    *,
    text: str,
    matched_alias_strengths: Mapping[str, str],
    matched_rule_terms: Sequence[str],
    matched_outcome_terms: Sequence[str],
    matched_target_aliases: Sequence[str],
    matched_role_families: Sequence[str],
) -> int:
    alias_score = sum(ALIAS_STRENGTH_SCORES.get(strength, 1) for strength in matched_alias_strengths.values())
    weak_only_penalty = 8 if matched_alias_strengths and set(matched_alias_strengths.values()) == {"weak"} and not matched_target_aliases else 0
    return (
        alias_score
        + len(matched_rule_terms) * 4
        + len(matched_outcome_terms) * 6
        + len(matched_target_aliases) * 2
        + len(matched_role_families) * 3
        + delegation_chain_signal_score(text)
        - weak_only_penalty
    )


def object_source_cache_owner(document: Mapping[str, Any]) -> str:
    payload = document.get("object_source_cache")
    if not isinstance(payload, Mapping):
        return ""
    return str(payload.get("person_name") or "").strip()


def object_source_cache_document_matches_seed(document: Mapping[str, Any], seed_name: str) -> bool:
    owner = object_source_cache_owner(document)
    if not owner:
        return True
    owner_terms = {owner, *alias_script_variants(owner)}
    seed_terms = {seed_name, *alias_script_variants(seed_name)}
    return bool(owner_terms & seed_terms)


def select_candidate_slices(
    task: Mapping[str, Any],
    documents: Sequence[Mapping[str, Any]],
    *,
    context_chars: int = 180,
    max_slices_per_object: int = 6,
) -> list[dict[str, Any]]:
    seeds = [seed for seed in task.get("object_seeds", []) if isinstance(seed, Mapping)]
    rule_match_terms = rule_terms(task)
    conditional_match_terms = conditional_recall_terms(task)
    outcome_match_terms = outcome_terms(task)
    target_terms = target_aliases(task)
    role_terms_by_family = role_family_terms(task)
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for seed in seeds:
        name = object_seed_name(seed)
        if not name:
            continue
        aliases = alias_entries(seed)
        alias_texts = [row["alias"] for row in aliases]
        object_rows: list[dict[str, Any]] = []
        for document in documents:
            if not object_source_cache_document_matches_seed(document, name):
                continue
            text = str(document.get("text") or "")
            if not text:
                continue
            for alias, position in iter_term_positions(text, alias_texts):
                start, end = object_scoped_context_bounds(text, name, position, context_chars=context_chars)
                excerpt = compact_text(text[start:end])
                alias_strengths = matched_alias_strengths(excerpt, aliases)
                matched_aliases = list(alias_strengths)
                matched_conditional_terms = conditional_terms_in_text(excerpt, conditional_match_terms)
                matched_rule_terms = unique_strings([*terms_in_text(excerpt, rule_match_terms), *matched_conditional_terms])
                if not matched_rule_terms:
                    continue
                matched_outcome_terms = terms_in_text(excerpt, outcome_match_terms)
                matched_target_aliases = terms_in_text(excerpt, target_terms)
                matched_role_families = [
                    family_code
                    for family_code, family_terms in role_terms_by_family.items()
                    if family_terms and terms_in_text(excerpt, family_terms)
                ]
                dedupe_key = (name, excerpt)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                score = slice_score(
                    text=excerpt,
                    matched_alias_strengths=alias_strengths,
                    matched_rule_terms=matched_rule_terms,
                    matched_outcome_terms=matched_outcome_terms,
                    matched_target_aliases=matched_target_aliases,
                    matched_role_families=matched_role_families,
                )
                object_rows.append(
                    {
                        "slice_code": f"SLI-{stable_fingerprint([document.get('document_code'), name, start, end])[:12].upper()}",
                        "document_code": document.get("document_code"),
                        "object_name": name,
                        "matched_aliases": matched_aliases,
                        "matched_alias_strengths": alias_strengths,
                        "matched_rule_terms": matched_rule_terms,
                        "matched_conditional_recall_terms": matched_conditional_terms,
                        "matched_outcome_terms": matched_outcome_terms,
                        "matched_target_aliases": matched_target_aliases,
                        "matched_role_families": matched_role_families,
                        "weak_alias_only": bool(alias_strengths) and set(alias_strengths.values()) == {"weak"},
                        "slice_profile": delegation_chain_signal_profile(excerpt),
                        "locator": f"chars:{start}-{end}",
                        "score": score,
                        "text": excerpt,
                    }
                )
        object_rows.sort(key=lambda row: (-int(row["score"]), str(row["document_code"]), str(row["locator"])))
        candidates.extend(object_rows[:max_slices_per_object])
    candidates.sort(key=lambda row: (str(row["object_name"]), -int(row["score"]), str(row["document_code"])))
    return candidates


def merge_alias_strengths(rows: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    strengths: dict[str, str] = {}
    for row in rows:
        for alias, strength in (row.get("matched_alias_strengths") or {}).items():
            alias_text = str(alias or "").strip()
            normalized = normalized_alias_strength(strength)
            current = strengths.get(alias_text)
            if alias_text and (current is None or ALIAS_STRENGTH_SCORES[normalized] > ALIAS_STRENGTH_SCORES[current]):
                strengths[alias_text] = normalized
    return strengths


def unique_row_values(rows: Sequence[Mapping[str, Any]], key: str) -> list[str]:
    return unique_strings(value for row in rows for value in (row.get(key) or []))


def merged_slice_row(
    rows: Sequence[Mapping[str, Any]],
    *,
    document_text: str,
    start: int,
    end: int,
) -> dict[str, Any]:
    first = rows[0]
    alias_strengths = merge_alias_strengths(rows)
    text = compact_text(document_text[start:end]) if document_text else compact_text(" ".join(str(row.get("text") or "") for row in rows))
    merged_from = [str(row.get("slice_code") or "") for row in rows if row.get("slice_code")]
    return {
        "slice_code": f"SLI-{stable_fingerprint([first.get('document_code'), first.get('object_name'), start, end, merged_from])[:12].upper()}",
        "document_code": first.get("document_code"),
        "object_name": first.get("object_name"),
        "matched_aliases": list(alias_strengths),
        "matched_alias_strengths": alias_strengths,
        "matched_rule_terms": unique_row_values(rows, "matched_rule_terms"),
        "matched_conditional_recall_terms": unique_row_values(rows, "matched_conditional_recall_terms"),
        "matched_outcome_terms": unique_row_values(rows, "matched_outcome_terms"),
        "matched_target_aliases": unique_row_values(rows, "matched_target_aliases"),
        "matched_role_families": unique_row_values(rows, "matched_role_families"),
        "weak_alias_only": bool(alias_strengths) and set(alias_strengths.values()) == {"weak"},
        "slice_profile": delegation_chain_signal_profile(text),
        "locator": f"chars:{start}-{end}",
        "score": max(int(row.get("score") or 0) for row in rows),
        "text": text,
        "merged_from_slice_codes": merged_from,
        "merged_slice_count": len(rows),
    }


def compacted_slice_row(rows: Sequence[Mapping[str, Any]], *, document_text: str, start: int, end: int) -> dict[str, Any]:
    if len(rows) == 1:
        return dict(rows[0])
    return merged_slice_row(rows, document_text=document_text, start=start, end=end)


def compact_candidate_slices(
    slices: Sequence[Mapping[str, Any]],
    documents: Sequence[Mapping[str, Any]],
    *,
    merge_gap_chars: int = 80,
    max_merged_chars: int = 900,
) -> list[dict[str, Any]]:
    text_by_doc = {str(document.get("document_code") or ""): str(document.get("text") or "") for document in documents}
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    passthrough: list[dict[str, Any]] = []
    for row in slices:
        locator = parse_char_locator(row.get("locator"))
        document_code = str(row.get("document_code") or "")
        object_name = str(row.get("object_name") or "")
        if locator is None or not document_code or not object_name:
            passthrough.append(dict(row))
            continue
        grouped.setdefault((object_name, document_code), []).append(row)

    compacted: list[dict[str, Any]] = []
    for (object_name, document_code), rows in grouped.items():
        sorted_rows = sorted(rows, key=lambda row: (parse_char_locator(row.get("locator")) or (0, 0), -int(row.get("score") or 0)))
        current_rows: list[Mapping[str, Any]] = []
        current_start = 0
        current_end = 0
        for row in sorted_rows:
            start, end = parse_char_locator(row.get("locator")) or (0, 0)
            can_merge = bool(current_rows) and start <= current_end + merge_gap_chars and end - current_start <= max_merged_chars
            if not current_rows:
                current_rows = [row]
                current_start, current_end = start, end
                continue
            if can_merge:
                current_rows.append(row)
                current_end = max(current_end, end)
                continue
            compacted.append(
                compacted_slice_row(
                    current_rows,
                    document_text=text_by_doc.get(document_code, ""),
                    start=current_start,
                    end=current_end,
                )
            )
            current_rows = [row]
            current_start, current_end = start, end
        if current_rows:
            compacted.append(
                compacted_slice_row(
                    current_rows,
                    document_text=text_by_doc.get(document_code, ""),
                    start=current_start,
                    end=current_end,
                )
            )
    compacted.extend(passthrough)
    compacted.sort(key=lambda row: (str(row.get("object_name")), -int(row.get("score") or 0), str(row.get("document_code"))))
    return compacted


def document_code(document: Mapping[str, Any], index: int) -> str:
    explicit = str(document.get("document_code") or "").strip()
    if explicit:
        return explicit
    title = str(document.get("wikisource_title") or document.get("title") or document.get("url") or f"doc-{index}")
    return f"DOC-{stable_fingerprint(title)[:10].upper()}"


def merge_secondary_rule_candidates(task: Mapping[str, Any], matrix: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in task.get("secondary_rule_candidates") or []:
        if isinstance(raw, Mapping):
            rule = str(raw.get("rule_code") or raw.get("code") or "").strip()
            reason = str(raw.get("reason") or "task-provided secondary rule candidate").strip()
        else:
            rule = str(raw or "").strip()
            reason = "task-provided secondary rule candidate"
        if rule:
            rows.append({"rule_code": rule, "reason": reason})
    for raw in matrix.get("secondary_rule_hints") or []:
        if not isinstance(raw, Mapping):
            continue
        rule = str(raw.get("rule_code") or raw.get("code") or "").strip()
        reason = str(raw.get("reason") or "coverage-matrix secondary rule hint").strip()
        if rule:
            rows.append({"rule_code": rule, "reason": reason})
    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        deduped.setdefault(row["rule_code"], row)
    return list(deduped.values())


def build_coverage_matrix(task: Mapping[str, Any], slices: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    matrix = task_coverage_matrix(task)
    role_families: list[dict[str, Any]] = []
    for raw_family in matrix.get("role_families") or []:
        if not isinstance(raw_family, Mapping):
            continue
        family_code = str(raw_family.get("family_code") or "").strip()
        if not family_code:
            continue
        family_slices = [row for row in slices if family_code in (row.get("matched_role_families") or [])]
        objects_checked = sorted({str(row.get("object_name")) for row in family_slices if row.get("object_name")})
        target_min_claims = int(raw_family.get("target_min_claims") or 0)
        gaps = [dict(gap) for gap in raw_family.get("gaps") or [] if isinstance(gap, Mapping)]
        if len(family_slices) < target_min_claims:
            gaps.append(
                {
                    "gap_type": gap_type_for_role_family(family_code),
                    "family_code": family_code,
                    "diagnosis": f"{family_code} candidate slices {len(family_slices)} below target {target_min_claims}",
                    "recommended_action": "supplement source documents, aliases, or rule-specific query terms for this role family",
                }
            )
        family_row = dict(raw_family)
        family_row.update(
            {
                "candidate_slice_count": len(family_slices),
                "objects_checked": objects_checked,
                "gaps": gaps,
            }
        )
        role_families.append(family_row)
    result = dict(matrix)
    result["role_families"] = role_families
    return result


def build_coverage_gaps(
    *,
    coverage_matrix: Mapping[str, Any],
    object_names: Sequence[str],
    counts_by_object: Mapping[str, int],
    slices: Sequence[Mapping[str, Any]],
    fetch_errors: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for name in object_names:
        if counts_by_object.get(name, 0) == 0:
            gaps.append(
                {
                    "gap_type": "alias_missing",
                    "object_name": name,
                    "diagnosis": "no candidate slices matched this object seed",
                    "recommended_action": "try strong and medium aliases before marking the object as lacking source material",
                }
            )
    for error in fetch_errors:
        gaps.append(
            {
                "gap_type": "fetch_error",
                "object_name": "",
                "diagnosis": str(error.get("error") or "source fetch failed"),
                "recommended_action": "retry, switch source page, or record temporary source unavailability",
                "source_document": {
                    key: error.get(key)
                    for key in ("document_code", "title", "wikisource_title", "url")
                    if error.get(key)
                },
            }
        )
    for family in coverage_matrix.get("role_families") or []:
        if not isinstance(family, Mapping):
            continue
        for gap in family.get("gaps") or []:
            if isinstance(gap, Mapping):
                gaps.append(dict(gap))
    by_object: dict[str, list[Mapping[str, Any]]] = {}
    for row in slices:
        by_object.setdefault(str(row.get("object_name") or ""), []).append(row)
    for name, object_slices in by_object.items():
        if name and object_slices and all(bool(row.get("weak_alias_only")) for row in object_slices):
            gaps.append(
                {
                    "gap_type": "weak_alias_noise",
                    "object_name": name,
                    "diagnosis": "all candidate slices rely only on weak aliases",
                    "recommended_action": "require target-era context co-occurrence or add stronger aliases before judging",
                }
            )
    deduped: dict[str, dict[str, Any]] = {}
    for gap in gaps:
        key = stable_fingerprint(
            [
                gap.get("gap_type"),
                gap.get("object_name"),
                gap.get("family_code"),
                gap.get("diagnosis"),
                gap.get("source_document"),
            ]
        )
        deduped.setdefault(key, gap)
    return list(deduped.values())


def build_candidates(
    task: Mapping[str, Any],
    *,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    timeout: int = 15,
    context_chars: int = 180,
    max_slices_per_object: int = 6,
    skip_fetch_errors: bool = False,
) -> dict[str, Any]:
    started = time.perf_counter()
    source_documents = task.get("source_documents") or task.get("documents") or []
    if not isinstance(source_documents, list) or not source_documents:
        raise RetrievalV2CandidateError("task requires source_documents")

    cache_dir.mkdir(parents=True, exist_ok=True)
    documents: list[dict[str, Any]] = []
    fetch_errors: list[dict[str, Any]] = []
    skipped_documents: list[dict[str, Any]] = []
    for index, raw_document in enumerate(source_documents, start=1):
        if not isinstance(raw_document, Mapping):
            continue
        skip = source_document_skip(task, raw_document)
        if str(raw_document.get("source_kind") or "").strip() == "wikisource_root_page":
            skip = skip or {"reason": "root_page_discovery_scaffold"}
        if skip is not None:
            skipped = {
                "document_code": document_code(raw_document, index),
                "title": raw_document.get("title") or raw_document.get("wikisource_title") or "",
                "wikisource_title": raw_document.get("wikisource_title") or "",
                "url": raw_document.get("url") or "",
                "reason": skip.get("reason") or "source_document_skipped",
            }
            for key in ("source_root", "allowed_source_roots"):
                if skip.get(key):
                    skipped[key] = skip[key]
            skipped_documents.append(skipped)
            continue
        try:
            text, fetch_meta = fetch_document_text(raw_document, cache_dir=cache_dir, timeout=timeout)
        except Exception as exc:
            if not skip_fetch_errors:
                raise
            fetch_errors.append(
                {
                    "document_code": document_code(raw_document, index),
                    "title": raw_document.get("title") or raw_document.get("wikisource_title") or "",
                    "wikisource_title": raw_document.get("wikisource_title") or "",
                    "url": raw_document.get("url") or "",
                    "error": str(exc),
                }
            )
            continue
        row = dict(raw_document)
        row["document_code"] = document_code(raw_document, index)
        row["text"] = text
        row["text_chars"] = len(text)
        row["fetch_meta"] = fetch_meta
        documents.append(row)

    raw_slices = select_candidate_slices(
        task,
        documents,
        context_chars=context_chars,
        max_slices_per_object=max_slices_per_object,
    )
    slices = compact_candidate_slices(raw_slices, documents)
    object_names = [
        object_seed_name(seed)
        for seed in task.get("object_seeds", [])
        if isinstance(seed, Mapping) and object_seed_name(seed)
    ]
    counts_by_object = {name: 0 for name in object_names}
    matched_aliases_by_object: dict[str, set[str]] = {name: set() for name in object_names}
    matched_alias_strengths_by_object: dict[str, dict[str, str]] = {name: {} for name in object_names}
    for row in slices:
        name = str(row["object_name"])
        counts_by_object[name] = counts_by_object.get(name, 0) + 1
        matched_aliases_by_object.setdefault(name, set()).update(str(alias) for alias in row.get("matched_aliases", []))
        matched_alias_strengths_by_object.setdefault(name, {}).update(
            {str(alias): str(strength) for alias, strength in (row.get("matched_alias_strengths") or {}).items()}
        )

    slim_documents = [
        {
            "document_code": row["document_code"],
            "title": row.get("title") or row.get("wikisource_title") or "",
            "url": row.get("url") or "",
            "source_kind": row.get("source_kind") or row.get("fetch_meta", {}).get("source_kind") or "unknown",
            "text_chars": row["text_chars"],
            "cache_status": row.get("fetch_meta", {}).get("cache_status"),
        }
        for row in documents
    ]
    finished = time.perf_counter()
    coverage_matrix = build_coverage_matrix(task, slices)
    coverage_gaps = build_coverage_gaps(
        coverage_matrix=coverage_matrix,
        object_names=object_names,
        counts_by_object=counts_by_object,
        slices=slices,
        fetch_errors=fetch_errors,
    )
    task_identity = {
        key: task.get(key)
        for key in (
            "job_code",
            "target_code",
            "emperor_name",
            "item_code",
            "contract_code",
            "rule_code",
            "capture_mode",
            "capture_profile",
            "fact_schema",
            "candidate_route_table_version",
        )
        if key in task
    }
    target_payload = task.get("target_payload") if isinstance(task.get("target_payload"), Mapping) else {}
    for key in ("capture_profile", "fact_schema", "candidate_route_table_version"):
        if key not in task_identity and key in target_payload:
            task_identity[key] = target_payload[key]
    payload = {
        "generated_by": "scripts/dev/retrieval_v2_source_candidates.py",
        "schema_version": 1,
        "task_identity": task_identity,
        "target_profile": task.get("target_profile") or {},
        "rule": task.get("rule") or task.get("rule_contract") or {},
        "coverage_matrix": coverage_matrix,
        "secondary_rule_candidates": merge_secondary_rule_candidates(task, coverage_matrix),
        "object_seeds": task.get("object_seeds") or [],
        "source_documents": slim_documents,
        "skipped_source_documents": skipped_documents,
        "fetch_errors": fetch_errors,
        "candidate_slices": slices,
        "coverage_gaps": coverage_gaps,
        "coverage": {
            "object_slice_counts": counts_by_object,
            "objects_without_slices": sorted(name for name, count in counts_by_object.items() if count == 0),
            "matched_aliases_by_object": {
                name: sorted(values) for name, values in matched_aliases_by_object.items()
            },
            "matched_alias_strengths_by_object": matched_alias_strengths_by_object,
            "coverage_gap_count": len(coverage_gaps),
            "ready_for_judgement": not fetch_errors and all(
                count > 0 for count in counts_by_object.values()
            ),
        },
        "stats": {
            "documents": len(documents),
            "skipped_source_documents": len(skipped_documents),
            "fetch_errors": len(fetch_errors),
            "document_chars": sum(int(row["text_chars"]) for row in documents),
            "raw_candidate_slices": len(raw_slices),
            "candidate_slices": len(slices),
            "raw_candidate_text_chars": sum(len(str(row.get("text") or "")) for row in raw_slices),
            "candidate_text_chars": sum(len(str(row.get("text") or "")) for row in slices),
            "candidate_compaction_removed_slices": len(raw_slices) - len(slices),
            "elapsed_seconds": round(finished - started, 3),
            "input_fingerprint": stable_fingerprint(task),
        },
    }
    return payload


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build retrieval_v2 source candidate slices for Codex CLI judging.")
    parser.add_argument("--input", type=Path, required=True, help="Task envelope JSON.")
    parser.add_argument("--output", type=Path, required=True, help="Candidate slice JSON output.")
    parser.add_argument("--prompt-output", type=Path, help="Optional compact Codex prompt output.")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--context-chars", type=int, default=180)
    parser.add_argument("--max-slices-per-object", type=int, default=6)
    parser.add_argument("--skip-fetch-errors", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    task = load_json(args.input)
    candidates = build_candidates(
        task,
        cache_dir=args.cache_dir,
        timeout=args.timeout,
        context_chars=args.context_chars,
        max_slices_per_object=args.max_slices_per_object,
        skip_fetch_errors=args.skip_fetch_errors,
    )
    atomic_write_json(args.output, candidates)
    if args.prompt_output is not None:
        atomic_write_text(args.prompt_output, candidate_prompt.build_prompt(candidates))
    print(
        pretty_json(
            {
                "ok": True,
                "output": str(args.output),
                "prompt_output": str(args.prompt_output) if args.prompt_output else None,
                "stats": candidates["stats"],
                "coverage": candidates["coverage"],
            }
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RetrievalV2CandidateError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
