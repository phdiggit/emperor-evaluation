from __future__ import annotations

import re
import urllib.parse
from collections import defaultdict
from typing import Any, Iterable

from .common import (
    ADJACENT_LAYER,
    KNOWN_SOURCE_TITLE_VARIANTS,
    CandidateObject,
    DirectPagePlan,
    ExcerptPoolError,
    SearchPlan,
    compact_text,
    read_jsonl,
)


def load_profile(path: Path, person: str) -> dict[str, Any]:
    matches = [row for row in read_jsonl(path) if row.get("person") == person]
    if not matches:
        raise ExcerptPoolError(f"profile not found for person: {person}")
    if len(matches) > 1:
        raise ExcerptPoolError(f"multiple profiles found for person: {person}")
    return matches[0]


def _add_unique(values: list[str], value: str) -> None:
    cleaned = compact_text(value)
    if cleaned and cleaned not in values:
        values.append(cleaned)


def derive_search_terms(raw_name: str) -> tuple[str, ...]:
    terms: list[str] = []
    _add_unique(terms, raw_name)

    for part in re.split(r"[/／、,，；;\s]+", raw_name):
        _add_unique(terms, part)
        if "等" in part:
            _add_unique(terms, part.split("等", 1)[0])
        if "相关" in part:
            before_related = part.split("相关", 1)[0]
            _add_unique(terms, before_related)
            _add_unique(terms, before_related.replace("事件", ""))

    if raw_name.endswith("功臣"):
        _add_unique(terms, raw_name.removesuffix("功臣"))
        _add_unique(terms, "功臣")
    if "功臣" in raw_name:
        _add_unique(terms, "功臣")
    if "官员" in raw_name:
        _add_unique(terms, "官员")
    for suffix in ("冤狱", "罢斥", "贬谪", "被诬陷"):
        if raw_name.endswith(suffix):
            _add_unique(terms, raw_name.removesuffix(suffix))
            _add_unique(terms, suffix)

    return tuple(term for term in terms if len(term) >= 2)


def derive_query_terms(query: str) -> tuple[str, ...]:
    terms: list[str] = []
    for part in re.split(r"[/／、,，；;\s]+", query):
        _add_unique(terms, part)
    return tuple(
        sorted(
            (
                term
                for term in terms
                if len(term) >= 2 and not (len(term) == 2 and term.endswith(("帝", "宗", "祖", "王")))
            ),
            key=lambda term: (-len(term), terms.index(term)),
        )
    )


def iter_candidate_objects(profile: dict[str, Any], *, include_adjacent: bool = False) -> list[CandidateObject]:
    object_layers = profile.get("object_layers")
    if not isinstance(object_layers, dict):
        raise ExcerptPoolError("profile.object_layers: expected object")

    candidates: list[CandidateObject] = []
    for layer, names in object_layers.items():
        if layer == ADJACENT_LAYER and not include_adjacent:
            continue
        if not isinstance(names, list):
            raise ExcerptPoolError(f"profile.object_layers.{layer}: expected list")
        for name in names:
            if not isinstance(name, str) or not name.strip():
                raise ExcerptPoolError(f"profile.object_layers.{layer}: expected non-empty string")
            candidates.append(CandidateObject(name.strip(), layer, derive_search_terms(name.strip())))
    return candidates


def _bundle_matches(bundle: str, terms: Iterable[str]) -> bool:
    return any(term in bundle for term in terms)


def _bundle_mentions_other_candidate(bundle: str, candidate: CandidateObject, candidates: Iterable[CandidateObject]) -> bool:
    for other in candidates:
        if other.raw_name == candidate.raw_name:
            continue
        if _bundle_matches(bundle, other.search_terms):
            return True
    return False


def fallback_source_titles(profile: dict[str, Any]) -> tuple[str, ...]:
    titles = source_title_filters(profile)
    if titles:
        return titles
    return ("正史", "资治通鉴")


def fallback_object_queries(profile: dict[str, Any], *, person: str, primary: str) -> list[str]:
    queries: list[str] = []
    for source_title in fallback_source_titles(profile):
        _add_unique(queries, f"{person} {primary} {source_title} 任用 授权")
        _add_unique(queries, f"{person} {primary} {source_title} 人才安全")
    return queries


def build_search_plans(
    profile: dict[str, Any],
    *,
    include_adjacent: bool = False,
    max_queries_per_object: int | None = None,
) -> list[SearchPlan]:
    person = str(profile.get("person", "")).strip()
    if not person:
        raise ExcerptPoolError("profile.person: expected non-empty string")

    bundles = profile.get("query_bundles", [])
    if not isinstance(bundles, list):
        raise ExcerptPoolError("profile.query_bundles: expected list")
    query_bundles = [bundle.strip() for bundle in bundles if isinstance(bundle, str) and bundle.strip()]

    plans: list[SearchPlan] = []
    seen: set[tuple[str, str]] = set()
    candidates = iter_candidate_objects(profile, include_adjacent=include_adjacent)
    for candidate in candidates:
        object_plans = [
            bundle
            for bundle in query_bundles
            if _bundle_matches(bundle, candidate.search_terms)
        ]
        if not object_plans:
            primary = candidate.search_terms[0]
            object_plans = fallback_object_queries(profile, person=person, primary=primary)
        elif all(_bundle_mentions_other_candidate(bundle, candidate, candidates) for bundle in object_plans):
            primary = candidate.search_terms[0]
            for fallback_query in fallback_object_queries(profile, person=person, primary=primary):
                _add_unique(object_plans, fallback_query)

        selected_plans = object_plans
        if max_queries_per_object is not None:
            selected_plans = object_plans[:max_queries_per_object]
        for query in selected_plans:
            key = (candidate.raw_name, query)
            if key in seen:
                continue
            seen.add(key)
            query_terms = tuple(
                term
                for term in derive_query_terms(query)
                if term != person and term not in candidate.search_terms
            )
            plans.append(
                SearchPlan(
                    object_name=candidate.raw_name,
                    layer=candidate.layer,
                    query=query,
                    search_terms=(*query_terms, person, *candidate.search_terms),
                )
            )

    return plans


CHINESE_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "兩": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
CHINESE_UNITS = {"十": 10, "百": 100, "千": 1000}


def chinese_numeral_to_int(value: str) -> int | None:
    if not value:
        return None
    if value.isdigit():
        return int(value)
    total = 0
    number = 0
    saw_unit = False
    for char in value:
        if char in CHINESE_DIGITS:
            number = CHINESE_DIGITS[char]
            continue
        if char in CHINESE_UNITS:
            saw_unit = True
            unit = CHINESE_UNITS[char]
            total += (number or 1) * unit
            number = 0
            continue
        return None
    total += number
    return total if total or saw_unit else None


def normalize_volume_token(value: str) -> str | None:
    match = re.fullmatch(r"卷(?P<number>[0-9]+|[零〇一二两兩三四五六七八九十百千]+)(?P<suffix>[上下]?)", value.strip())
    if not match:
        return None
    number = chinese_numeral_to_int(match.group("number"))
    if number is None:
        return None
    return f"卷{number}{match.group('suffix')}"


def _known_source_title_pattern() -> str:
    variants = sorted(
        {variant for variants in KNOWN_SOURCE_TITLE_VARIANTS.values() for variant in variants},
        key=len,
        reverse=True,
    )
    return "|".join(re.escape(variant) for variant in variants)


SOURCE_TITLE_PATTERN = _known_source_title_pattern()
CACHE_DIRECT_GENERIC_TERMS = {"官员", "功臣", "团队", "机制", "对象", "事件", "边界"}


def explicit_page_titles_from_text(text: str) -> tuple[str, ...]:
    titles: list[str] = []
    for url in re.findall(r"https?://[^\s,，；;）)]+", text):
        parsed = urllib.parse.urlparse(url)
        path = urllib.parse.unquote(parsed.path).strip("/")
        if not path:
            continue
        parts = path.split("/")
        if parts and parts[0] in {"wiki", "zh", "zh-hans", "zh-hant"}:
            parts = parts[1:]
        if len(parts) >= 2 and parts[1].startswith("卷"):
            _add_unique(titles, "/".join(parts[:2]))

    volume_re = r"卷(?:[0-9]+|[零〇一二两兩三四五六七八九十百千]+)[上下]?"
    for match in re.finditer(
        rf"(?P<title>{SOURCE_TITLE_PATTERN})\s*[/／]\s*(?P<volume>{volume_re})",
        text,
    ):
        volume = normalize_volume_token(match.group("volume"))
        if volume:
            _add_unique(titles, f"{match.group('title')}/{volume}")
    for match in re.finditer(
        rf"(?P<title>{SOURCE_TITLE_PATTERN})\s+(?P<volume>{volume_re})",
        text,
    ):
        volume = normalize_volume_token(match.group("volume"))
        if volume:
            _add_unique(titles, f"{match.group('title')}/{volume}")
    return tuple(titles)


def explicit_page_targets(profile: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    targets: list[tuple[str, str]] = []
    seen: set[str] = set()
    for key in ("source_targets", "query_bundles"):
        value = profile.get(key, [])
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, str) or not item.strip():
                continue
            for title in explicit_page_titles_from_text(item):
                if title in seen:
                    continue
                seen.add(title)
                targets.append((title, item.strip()))
    return tuple(targets)


def direct_page_search_terms(person: str, candidate: CandidateObject) -> tuple[str, ...]:
    terms: list[str] = []
    for term in candidate.search_terms:
        _add_unique(terms, term)
    _add_unique(terms, person)
    return tuple(terms)


def cache_direct_object_terms(candidate: CandidateObject) -> tuple[str, ...]:
    return tuple(term for term in candidate.search_terms if term not in CACHE_DIRECT_GENERIC_TERMS)


def build_direct_page_plans(profile: dict[str, Any], *, include_adjacent: bool = False) -> list[DirectPagePlan]:
    person = str(profile.get("person", "")).strip()
    if not person:
        raise ExcerptPoolError("profile.person: expected non-empty string")
    targets = explicit_page_targets(profile)
    if not targets:
        return []

    plans: list[DirectPagePlan] = []
    for candidate in iter_candidate_objects(profile, include_adjacent=include_adjacent):
        for page_title, source_target in targets:
            plans.append(
                DirectPagePlan(
                    object_name=candidate.raw_name,
                    layer=candidate.layer,
                    page_title=page_title,
                    source_target=source_target,
                    search_terms=direct_page_search_terms(person, candidate),
                )
            )
    return plans


def build_cache_direct_page_plans(
    profile: dict[str, Any],
    page_text_cache: Any,
    *,
    include_adjacent: bool = False,
    explicit_page_titles: Iterable[str] = (),
) -> tuple[list[DirectPagePlan], dict[str, str], dict[str, Any]]:
    report = {
        "enabled": False,
        "considered_pages": 0,
        "excluded_broad_pages": 0,
        "excluded_auxiliary_pages": 0,
        "source_matched_pages": 0,
        "matched_plans": 0,
        "errors": [],
    }
    if page_text_cache is None or not hasattr(page_text_cache, "iter_pages"):
        return [], {}, report
    if not getattr(page_text_cache, "enabled", True) or getattr(page_text_cache, "refresh", False):
        return [], {}, report

    person = str(profile.get("person", "")).strip()
    if not person:
        raise ExcerptPoolError("profile.person: expected non-empty string")
    filters = source_title_filters(profile)
    if not filters:
        return [], {}, report
    auxiliary_filters = auxiliary_source_title_filters(profile)

    report["enabled"] = True
    explicit_titles = set(explicit_page_titles)
    cached_pages: list[tuple[str, str]] = []
    seed_texts: dict[str, str] = {}
    try:
        iterator = page_text_cache.iter_pages()
        if iterator is None:
            return [], {}, report
        for title, text in iterator:
            report["considered_pages"] += 1
            if "全覽" in title:
                report["excluded_broad_pages"] += 1
                continue
            if title in explicit_titles:
                continue
            if auxiliary_filters and title_matches_source_filters(title, auxiliary_filters):
                report["excluded_auxiliary_pages"] += 1
                continue
            if not title_matches_source_filters(title, filters):
                continue
            report["source_matched_pages"] += 1
            cached_pages.append((title, text))
    except Exception as exc:  # pragma: no cover - cache implementations should record their own errors.
        report["errors"].append({"error": repr(exc)})
        return [], {}, report

    plans: list[DirectPagePlan] = []
    seen: set[tuple[str, str]] = set()
    for candidate in iter_candidate_objects(profile, include_adjacent=include_adjacent):
        object_terms = cache_direct_object_terms(candidate)
        if not object_terms:
            continue
        for title, text in cached_pages:
            if not any(term and term in text for term in object_terms):
                continue
            key = (candidate.raw_name, title)
            if key in seen:
                continue
            seen.add(key)
            seed_texts[title] = text
            plans.append(
                DirectPagePlan(
                    object_name=candidate.raw_name,
                    layer=candidate.layer,
                    page_title=title,
                    source_target="page_text_cache",
                    search_terms=direct_page_search_terms(person, candidate),
                )
            )
    report["matched_plans"] = len(plans)
    return plans, seed_texts, report


def limit_search_plans(
    plans: list[SearchPlan],
    *,
    max_queries: int | None = None,
    max_queries_per_object: int | None = None,
) -> tuple[list[SearchPlan], list[dict[str, str]]]:
    selected: list[SearchPlan] = []
    skipped: list[dict[str, str]] = []
    per_object_counts: dict[str, int] = defaultdict(int)

    for plan in plans:
        reason = ""
        if max_queries_per_object is not None and per_object_counts[plan.object_name] >= max_queries_per_object:
            reason = "max_queries_per_object"
        elif max_queries is not None and len(selected) >= max_queries:
            reason = "max_queries"

        if reason:
            skipped.append(
                {
                    "object_name": plan.object_name,
                    "layer": plan.layer,
                    "query": plan.query,
                    "reason": reason,
                }
            )
            continue

        selected.append(plan)
        per_object_counts[plan.object_name] += 1

    return selected, skipped


def source_title_filters(profile: dict[str, Any]) -> tuple[str, ...]:
    haystacks: list[str] = []
    for key in ("source_targets", "query_bundles"):
        value = profile.get(key, [])
        if isinstance(value, list):
            haystacks.extend(item for item in value if isinstance(item, str))

    filters: list[str] = []
    for simplified, variants in KNOWN_SOURCE_TITLE_VARIANTS.items():
        if any(_contains_source_title(simplified, variants, text) for text in haystacks):
            for variant in variants:
                _add_unique(filters, variant)
    return tuple(filters)


def auxiliary_source_title_filters(profile: dict[str, Any]) -> tuple[str, ...]:
    source_targets = profile.get("source_targets", [])
    if not isinstance(source_targets, list):
        return ()

    filters: list[str] = []
    for item in source_targets:
        if not isinstance(item, str):
            continue
        if not any(marker in item for marker in ("辅助", "不直接")):
            continue
        for simplified, variants in KNOWN_SOURCE_TITLE_VARIANTS.items():
            if _contains_source_title(simplified, variants, item):
                for variant in variants:
                    _add_unique(filters, variant)
    return tuple(filters)


def _contains_source_title(simplified: str, variants: tuple[str, ...], text: str) -> bool:
    if simplified == "汉书":
        return bool(re.search(r"(?<!后)(?<!後)(汉书|漢書)", text))
    if simplified == "资治通鉴":
        return bool(re.search(r"(?<!续)(?<!續)(资治通鉴|資治通鑑)", text))
    if simplified == "明实录":
        return bool(re.search(r"明.{0,4}(实录|實錄)", text))
    if simplified == "清实录":
        return bool(re.search(r"清.{0,4}(实录|實錄)", text))
    return any(variant in text for variant in variants)


def title_matches_source_filters(title: str, filters: Iterable[str]) -> bool:
    source_filters = tuple(filters)
    if not source_filters:
        return True
    if any(source_filter in {"明实录", "明實錄"} for source_filter in source_filters):
        if re.match(r"明.{0,4}(实录|實錄)(/|／| |　|\(|（|$)", title):
            return True
    if any(source_filter in {"清实录", "清實錄"} for source_filter in source_filters):
        if re.match(r"清.{0,4}(实录|實錄)(/|／| |　|\(|（|$)", title):
            return True
    return any(
        title == source_filter
        or title.startswith(
            (
                f"{source_filter}/",
                f"{source_filter}／",
                f"{source_filter} ",
                f"{source_filter}　",
                f"{source_filter}(",
                f"{source_filter}（",
            )
        )
        for source_filter in source_filters
    )
