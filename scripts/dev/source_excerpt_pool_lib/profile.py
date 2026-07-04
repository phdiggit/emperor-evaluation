from __future__ import annotations

import json
import re
import urllib.parse
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from .common import (
    ADJACENT_LAYER,
    DEFAULT_WORKFLOW_CODE,
    KNOWN_SOURCE_TITLE_VARIANTS,
    CandidateObject,
    DirectPagePlan,
    ExcerptPoolError,
    SearchPlan,
    compact_text,
    normalize_workflow_code,
    read_jsonl,
)


def profile_workflow_code(profile: dict[str, Any], *, default: str = DEFAULT_WORKFLOW_CODE) -> str:
    return normalize_workflow_code(profile.get("workflow_code") or default)


def profile_matches_workflow(profile: dict[str, Any], workflow_code: str | None) -> bool:
    return profile_workflow_code(profile) == normalize_workflow_code(workflow_code)


def load_profile(path: Path, person: str, *, workflow_code: str = DEFAULT_WORKFLOW_CODE) -> dict[str, Any]:
    workflow_code = normalize_workflow_code(workflow_code)
    matches = [row for row in read_jsonl(path) if row.get("person") == person and profile_matches_workflow(row, workflow_code)]
    if not matches:
        raise ExcerptPoolError(f"profile not found for person: {person} workflow_code={workflow_code}")
    if len(matches) > 1:
        raise ExcerptPoolError(f"multiple profiles found for person: {person} workflow_code={workflow_code}")
    return matches[0]


def _add_unique(values: list[str], value: str) -> None:
    cleaned = compact_text(value)
    if cleaned and cleaned not in values:
        values.append(cleaned)


ANNOTATION_RE = re.compile(r"[（(][^（）()]*[）)]")
SEARCH_LABEL_SUFFIXES = (
    "政治风险对象",
    "近臣风险",
    "早期任用",
    "早期信任",
    "后续处置",
    "任用边界",
    "处置边界",
    "信任回缩",
    "安全破坏",
    "安全链",
    "牵连对象",
    "相关对象",
    "相关官员",
    "可回源对象",
    "等可回源对象",
    "无谏诤机制",
    "功臣团队",
    "早期",
    "晚期",
    "冤狱",
    "罢斥",
    "贬谪",
    "被诬陷",
    "旧臣处置",
    "旧臣",
    "外戚",
    "近幸",
    "压力",
    "使用",
    "处置",
    "机制",
    "本体",
    "符号",
    "边界",
    "团队",
    "群体",
    "对象",
    "事件",
    "案",
)
CANDIDATE_INVENTORY_FIELD = "candidate_inventory"
INVENTORY_LAYER_KEYS = ("suggested_layer", "layer", "target_layer")
INVENTORY_NAME_KEYS = ("object_name", "name", "canonical_name")
INVENTORY_ALIAS_KEYS = ("aliases", "object_aliases", "search_aliases")
INVENTORY_SEARCH_TERM_KEYS = ("search_terms", "query_terms")


def strip_search_label_suffixes(value: str) -> str:
    cleaned = ANNOTATION_RE.sub("", value).strip()
    changed = True
    while changed:
        changed = False
        for suffix in SEARCH_LABEL_SUFFIXES:
            if cleaned.endswith(suffix) and len(cleaned) > len(suffix) + 1:
                cleaned = cleaned[: -len(suffix)].strip()
                changed = True
                break
    return cleaned


def derive_primary_search_terms(raw_name: str) -> tuple[str, ...]:
    terms: list[str] = []
    normalized = ANNOTATION_RE.sub("", raw_name).strip()
    parts = [part.strip() for part in re.split(r"[/／、,，；;\s]+", normalized) if part.strip()]
    if normalized != raw_name and len(parts) == 1 and "等" not in normalized:
        _add_unique(terms, strip_search_label_suffixes(normalized))
    for part in re.split(r"[/／、,，；;\s]+", normalized):
        part = part.strip()
        if len(part) < 2:
            continue
        if "等" in part:
            _add_unique(terms, strip_search_label_suffixes(part.split("等", 1)[0]))
        stripped = strip_search_label_suffixes(part)
        if stripped != part:
            _add_unique(terms, stripped)
        elif len(parts) > 1 and len(part) <= 4:
            _add_unique(terms, part)
    return tuple(term for term in terms if len(term) >= 2)


def derive_search_terms(raw_name: str) -> tuple[str, ...]:
    terms: list[str] = []
    for term in derive_primary_search_terms(raw_name):
        _add_unique(terms, term)
    _add_unique(terms, raw_name)

    normalized = ANNOTATION_RE.sub("", raw_name).strip()
    for part in re.split(r"[/／、,，；;\s]+", normalized):
        _add_unique(terms, part)
        if "等" in part:
            _add_unique(terms, strip_search_label_suffixes(part.split("等", 1)[0]))
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


def _declared_object_search_aliases(profile: dict[str, Any], raw_name: str) -> tuple[str, ...]:
    aliases: list[str] = []
    alias_map = profile.get("object_search_aliases", {})
    if alias_map is None:
        alias_map = {}
    if not isinstance(alias_map, dict):
        raise ExcerptPoolError("profile.object_search_aliases: expected object")

    raw_aliases = alias_map.get(raw_name, [])
    if isinstance(raw_aliases, str):
        _add_unique(aliases, raw_aliases)
    elif isinstance(raw_aliases, list):
        for alias in raw_aliases:
            if isinstance(alias, str):
                _add_unique(aliases, alias)
    elif raw_aliases is None:
        pass
    else:
        raise ExcerptPoolError(f"profile.object_search_aliases.{raw_name}: expected string or list")
    return tuple(aliases)


def object_search_aliases(profile: dict[str, Any], raw_name: str) -> tuple[str, ...]:
    aliases: list[str] = list(_declared_object_search_aliases(profile, raw_name))

    for item in candidate_inventory_items(profile):
        if item["object_name"] != raw_name:
            continue
        for alias in item["aliases"]:
            _add_unique(aliases, alias)
    return tuple(aliases)


def object_search_alias_terms(profile: dict[str, Any], raw_name: str) -> tuple[str, ...]:
    terms: list[str] = []
    for alias in object_search_aliases(profile, raw_name):
        for term in derive_search_terms(alias):
            _add_unique(terms, term)
    return tuple(terms)


def object_search_terms(profile: dict[str, Any], raw_name: str) -> tuple[str, ...]:
    terms: list[str] = []
    alias_terms = object_search_alias_terms(profile, raw_name)
    for term in alias_terms:
        _add_unique(terms, term)
    for item in candidate_inventory_items(profile):
        if item["object_name"] != raw_name:
            continue
        for term in item["search_terms"]:
            for derived in derive_search_terms(term):
                _add_unique(terms, derived)
    label_free_name = strip_search_label_suffixes(raw_name)
    for term in derive_search_terms(raw_name):
        if alias_terms and term == raw_name and label_free_name != raw_name:
            continue
        _add_unique(terms, term)
    return tuple(terms)


def fallback_object_queries_for_terms(profile: dict[str, Any], *, person: str, terms: tuple[str, ...]) -> list[str]:
    queries: list[str] = []
    per_term_queries: list[list[str]] = []
    for term in terms:
        if not term.strip():
            continue
        per_term_queries.append(fallback_object_queries(profile, person=person, primary=term))
    max_len = max((len(term_queries) for term_queries in per_term_queries), default=0)
    for index in range(max_len):
        for term_queries in per_term_queries:
            if index < len(term_queries):
                _add_unique(queries, term_queries[index])
    return queries


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


def _string_values(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if isinstance(value, list):
        values: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                _add_unique(values, item)
        return tuple(values)
    return ()


def _inventory_value(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in row:
            return row.get(key)
    return None


def _inventory_key(value: str) -> str:
    return re.sub(r"[\s　]+", "", value)


def _object_layer_names(profile: dict[str, Any]) -> tuple[str, ...]:
    object_layers = profile.get("object_layers")
    if not isinstance(object_layers, dict):
        return ()
    names: list[str] = []
    for raw_names in object_layers.values():
        if not isinstance(raw_names, list):
            continue
        for name in raw_names:
            if isinstance(name, str) and name.strip():
                _add_unique(names, name.strip())
    return tuple(names)


def _declared_alias_index(profile: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    index: dict[str, list[str]] = {}
    for object_name in _object_layer_names(profile):
        for term in (object_name, *_declared_object_search_aliases(profile, object_name)):
            key = _inventory_key(term)
            if not key:
                continue
            index.setdefault(key, [])
            _add_unique(index[key], object_name)
    return {key: tuple(names) for key, names in index.items()}


def _canonicalize_inventory_item(profile: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    alias_index = _declared_alias_index(profile)
    matches: set[str] = set()
    for term in (item["object_name"], *item["aliases"]):
        key = _inventory_key(term)
        if not key:
            continue
        names = alias_index.get(key, ())
        if len(names) == 1:
            matches.add(names[0])

    if len(matches) != 1:
        return item

    canonical_name = next(iter(matches))
    if canonical_name == item["object_name"]:
        return item

    updated = dict(item)
    updated["aliases"] = list(item["aliases"])
    _add_unique(updated["aliases"], item["object_name"])
    updated["object_name"] = canonical_name
    return updated


def _normalize_inventory_item(raw: Any, *, layer_hint: str = "supplemental_objects") -> dict[str, Any] | None:
    if isinstance(raw, str):
        name = raw.strip()
        if not name:
            return None
        return {
            "object_name": name,
            "suggested_layer": layer_hint,
            "aliases": [],
            "search_terms": [],
        }
    if not isinstance(raw, dict):
        return None
    include = raw.get("include_in_search", True)
    if include is False or str(raw.get("status") or "").strip() in {"excluded", "rejected", "ignore"}:
        return None
    name = str(_inventory_value(raw, INVENTORY_NAME_KEYS) or "").strip()
    if not name:
        return None
    layer = str(_inventory_value(raw, INVENTORY_LAYER_KEYS) or layer_hint or "supplemental_objects").strip()
    aliases: list[str] = []
    for key in INVENTORY_ALIAS_KEYS:
        for alias in _string_values(raw.get(key)):
            _add_unique(aliases, alias)
    search_terms: list[str] = []
    for key in INVENTORY_SEARCH_TERM_KEYS:
        for term in _string_values(raw.get(key)):
            _add_unique(search_terms, term)
    return {
        "object_name": name,
        "suggested_layer": layer or "supplemental_objects",
        "aliases": aliases,
        "search_terms": search_terms,
    }


def candidate_inventory_items(profile: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    raw_inventory = profile.get(CANDIDATE_INVENTORY_FIELD, [])
    rows: list[dict[str, Any]] = []
    if raw_inventory is None:
        return ()
    if isinstance(raw_inventory, dict):
        for layer, values in raw_inventory.items():
            if not isinstance(values, list):
                raise ExcerptPoolError(f"profile.{CANDIDATE_INVENTORY_FIELD}.{layer}: expected list")
            for value in values:
                item = _normalize_inventory_item(value, layer_hint=str(layer))
                if item is not None:
                    rows.append(_canonicalize_inventory_item(profile, item))
    elif isinstance(raw_inventory, list):
        for value in raw_inventory:
            item = _normalize_inventory_item(value)
            if item is not None:
                rows.append(_canonicalize_inventory_item(profile, item))
    else:
        raise ExcerptPoolError(f"profile.{CANDIDATE_INVENTORY_FIELD}: expected list or object")

    merged: dict[str, dict[str, Any]] = {}
    for item in rows:
        name = item["object_name"]
        current = merged.setdefault(
            name,
            {
                "object_name": name,
                "suggested_layer": item["suggested_layer"],
                "aliases": [],
                "search_terms": [],
            },
        )
        if current["suggested_layer"] != "negative_or_reversal_objects" and item["suggested_layer"] == "negative_or_reversal_objects":
            current["suggested_layer"] = item["suggested_layer"]
        for alias in item["aliases"]:
            _add_unique(current["aliases"], alias)
        for term in item["search_terms"]:
            _add_unique(current["search_terms"], term)
    return tuple(merged[name] for name in sorted(merged))


def _candidate_layer(layer: str, *, include_adjacent: bool) -> str | None:
    if layer == ADJACENT_LAYER and not include_adjacent:
        return None
    if not layer:
        return "supplemental_objects"
    return layer


def _merge_candidate(
    candidates: dict[str, CandidateObject],
    *,
    raw_name: str,
    layer: str,
    search_terms: Iterable[str],
) -> None:
    terms: list[str] = []
    if raw_name in candidates:
        existing = candidates[raw_name]
        layer = (
            "negative_or_reversal_objects"
            if existing.layer != "negative_or_reversal_objects" and layer == "negative_or_reversal_objects"
            else existing.layer
        )
        for term in existing.search_terms:
            _add_unique(terms, term)
    for term in search_terms:
        _add_unique(terms, term)
    candidates[raw_name] = CandidateObject(raw_name, layer, tuple(terms))


def iter_candidate_objects(profile: dict[str, Any], *, include_adjacent: bool = False) -> list[CandidateObject]:
    object_layers = profile.get("object_layers")
    if not isinstance(object_layers, dict):
        raise ExcerptPoolError("profile.object_layers: expected object")

    candidates: dict[str, CandidateObject] = {}
    for layer, names in object_layers.items():
        candidate_layer = _candidate_layer(str(layer), include_adjacent=include_adjacent)
        if candidate_layer is None:
            continue
        if not isinstance(names, list):
            raise ExcerptPoolError(f"profile.object_layers.{layer}: expected list")
        for name in names:
            if not isinstance(name, str) or not name.strip():
                raise ExcerptPoolError(f"profile.object_layers.{layer}: expected non-empty string")
            raw_name = name.strip()
            _merge_candidate(
                candidates,
                raw_name=raw_name,
                layer=candidate_layer,
                search_terms=object_search_terms(profile, raw_name),
            )

    for item in candidate_inventory_items(profile):
        layer = _candidate_layer(item["suggested_layer"], include_adjacent=include_adjacent)
        if layer is None:
            continue
        raw_name = item["object_name"]
        _merge_candidate(
            candidates,
            raw_name=raw_name,
            layer=layer,
            search_terms=object_search_terms(profile, raw_name),
        )
    return list(candidates.values())


def merge_candidate_inventory(profile: dict[str, Any], candidates: Iterable[dict[str, Any]]) -> dict[str, Any]:
    updated = json.loads(json.dumps(profile, ensure_ascii=False))
    inventory = updated.setdefault(CANDIDATE_INVENTORY_FIELD, [])
    if not isinstance(inventory, list):
        inventory = []
        updated[CANDIDATE_INVENTORY_FIELD] = inventory
    existing = {item["object_name"] for item in candidate_inventory_items(updated)}
    for candidate in candidates:
        item = _normalize_inventory_item(candidate)
        if item is not None:
            item = _canonicalize_inventory_item(updated, item)
        if item is None or item["object_name"] in existing:
            continue
        inventory.append(
            {
                "object_name": item["object_name"],
                "suggested_layer": item["suggested_layer"],
                "aliases": item["aliases"],
                "search_terms": item["search_terms"],
                "confidence": str(candidate.get("confidence") or "medium"),
                "reason": str(candidate.get("reason") or ""),
                "supporting_rows": candidate.get("supporting_rows") or [],
            }
        )
        existing.add(item["object_name"])
    return updated


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
    filters = source_title_filters(profile)
    if filters:
        titles: list[str] = []
        for simplified, variants in KNOWN_SOURCE_TITLE_VARIANTS.items():
            if any(variant in filters for variant in variants):
                _add_unique(titles, simplified)
        return tuple(titles or filters)
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
            object_plans = fallback_object_queries_for_terms(profile, person=person, terms=candidate.search_terms)
        elif all(_bundle_mentions_other_candidate(bundle, candidate, candidates) for bundle in object_plans):
            for fallback_query in fallback_object_queries_for_terms(profile, person=person, terms=candidate.search_terms):
                _add_unique(object_plans, fallback_query)

        elif len(object_plans) < MIN_OBJECT_QUERY_PLANS_BEFORE_FALLBACK:
            for fallback_query in fallback_object_queries_for_terms(profile, person=person, terms=candidate.search_terms):
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
MIN_OBJECT_QUERY_PLANS_BEFORE_FALLBACK = 2


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
                    "query_terms": list(derive_query_terms(plan.query)),
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
