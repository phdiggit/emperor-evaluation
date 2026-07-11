from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import unquote

from scripts.dev.retrieval_v3_bootstrap import import_psycopg, load_env_file, resolve_dsn
from scripts.dev.retrieval_v3_contracts import SOURCE_HINT_TEXT_ALIASES, alias_script_variants, unique_strings
from scripts.dev.retrieval_v3_taskgen_preseed import (
    canonical_volume_title,
    chinese_volume_number,
    normalize_title,
    source_hints_for_context,
    source_root_from_title,
    text_from,
)


PERSON_SEEDS_SQL = """
select
    o.object_code,
    o.canonical_name as name,
    o.normalized_name,
    o.object_type::text as object_type,
    coalesce(
        array_remove(array_agg(distinct onm.name_text) filter (where onm.review_status in ('pending', 'accepted')), null),
        array[]::text[]
    ) as aliases,
    bool_or(coalesce(tob.object_role, '') = 'target_emperor') as is_emperor,
    coalesce(array_remove(array_agg(distinct rt.emperor_name), null), array[]::text[]) as target_emperors,
    coalesce(jsonb_agg(distinct rt.target_payload) filter (where rt.id is not null), '[]'::jsonb) as target_payloads,
    min(coalesce(tob.created_at, o.created_at)) as first_seen_at
from retrieval_v3.objects o
left join retrieval_v3.object_names onm on onm.object_id = o.id
left join retrieval_v3.target_objects tob on tob.object_id = o.id and tob.review_status in ('pending', 'accepted')
left join retrieval_v3.retrieval_targets rt on rt.id = tob.target_id
where o.object_type = 'person'
  and o.identity_status = 'active'
group by o.object_code, o.canonical_name, o.normalized_name, o.object_type
order by is_emperor desc, o.canonical_name
"""

OBJECT_POOL_PERSON_SEEDS_SQL = """
select
    'raw_obj:' || ro.id::text as object_code,
    ro.name,
    regexp_replace(ro.name, '\\s+', '', 'g') as normalized_name,
    ro.obj_type as object_type,
    ro.period,
    coalesce(
        (
            select array_remove(array_agg(distinct a.alias_text), null)
            from raw_obj_aliases a
            where a.obj_id = ro.id
              and a.active
              and (
                  a.scope_emp_id is null
                  or exists (
                      select 1
                      from emp_objs eo_scope
                      where eo_scope.obj_id = ro.id
                        and eo_scope.emp_id = a.scope_emp_id
                  )
              )
        ),
        array[]::text[]
    ) as aliases,
    coalesce(
        (
            select array_remove(array_agg(distinct e.name), null)
            from emp_objs eo
            join emps e on e.id = eo.emp_id
            where eo.obj_id = ro.id
        ),
        array[]::text[]
    ) as target_emperors,
    coalesce(
        (
            select array_remove(array_agg(distinct sd.title), null)
            from obj_srcs os
            join src_docs sd on sd.id = os.doc_id
            where os.obj_id = ro.id
        ),
        array[]::text[]
    ) as source_hints,
    coalesce(
        (
            select jsonb_agg(distinct jsonb_build_object(
                'title', sd.title,
                'volume', sd.volume,
                'locator', sd.locator,
                'url', sd.url
            ))
            from obj_srcs os
            join src_docs sd on sd.id = os.doc_id
            where os.obj_id = ro.id
        ),
        '[]'::jsonb
    ) as source_document_hints,
    ro.created_at as first_seen_at
from raw_objs ro
where ro.obj_type = 'person'
order by ro.period, ro.name
"""

OBJECT_POOL_ALIAS_ROWS_SQL = """
select
    ro.period,
    ro.name as canonical_name,
    a.alias_text,
    a.alias_kind,
    case when a.scope_emp_id is null then 'global' else 'emperor' end as scope,
    coalesce(e.name, '') as scope_emp_name,
    coalesce(e.title, '') as scope_emp_title
from raw_obj_aliases a
join raw_objs ro on ro.id = a.obj_id
left join emps e on e.id = a.scope_emp_id
where a.active
  and ro.obj_type = 'person'
  and ro.period = any(%s)
  and (ro.name = any(%s) or a.normalized_alias = any(%s))
order by ro.period, ro.name, a.alias_kind, a.alias_text
"""


class ObjectSourceCacheSeedError(RuntimeError):
    pass


STAGED_NAME_SUFFIXES = ("早期任用", "早期", "晚期", "前期", "后期", "後期")
COMPOUND_SURNAMES = (
    "司马",
    "司馬",
    "上官",
    "欧阳",
    "歐陽",
    "夏侯",
    "诸葛",
    "諸葛",
    "东方",
    "東方",
    "皇甫",
    "尉迟",
    "尉遲",
    "公孙",
    "公孫",
    "第五",
)


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def stable_hash(value: Any, *, length: int = 16) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()[:length].upper()


def clean_name(value: Any) -> str:
    return str(value or "").strip()


def normalized_name(value: Any) -> str:
    return normalize_title(clean_name(value))


def object_pool_normalized_alias(value: Any) -> str:
    return "".join(clean_name(value).replace("\u3000", " ").split())


def first_column(row: Any) -> Any:
    if row is None:
        return None
    if isinstance(row, Mapping):
        return next(iter(row.values()), None)
    return row[0] if row else None


def seed_name(seed: Mapping[str, Any]) -> str:
    return text_from(seed, "name", "person_name", "canonical_name", "object_name", "primary_name")


def stage_base_name(value: Any) -> str:
    name = clean_name(value)
    for suffix in STAGED_NAME_SUFFIXES:
        if name.endswith(suffix) and len(name) > len(suffix) + 1:
            return name[: -len(suffix)]
    return ""


def surname_prefix(value: Any) -> str:
    name = stage_base_name(value) or clean_name(value)
    for surname in COMPOUND_SURNAMES:
        if name.startswith(surname):
            return surname
    return name[:1]


def given_name_tail(value: Any) -> str:
    name = stage_base_name(value) or clean_name(value)
    prefix = surname_prefix(name)
    return name[len(prefix) :] if prefix and name.startswith(prefix) else ""


def locator_alias_token(value: str) -> str:
    token = clean_name(value).strip("，,。；;：:、()（）[]【】《》<>〈〉")
    token = re.sub(r"(等|傳|传)$", "", token)
    if not token or any(term in token for term in ("列传", "列傳", "卷", "本纪", "本紀", "四庫", "全書")):
        return ""
    if not (2 <= len(token) <= 6):
        return ""
    return token


def title_alias_tokens_from_locator_token(token: str, names: Sequence[str]) -> list[str]:
    aliases: list[str] = []
    title_markers = ("太子", "王", "公", "侯", "帝", "后", "後", "妃", "昭容")
    if not any(marker in token for marker in title_markers):
        return []
    for name in names:
        given = given_name_tail(name)
        if not given or not token.endswith(given) or len(token) <= len(given):
            continue
        title = token[: -len(given)]
        if 2 <= len(title) <= 5:
            aliases.extend([token, title])
    return unique_strings(aliases)


def source_document_locator_aliases(seed: Mapping[str, Any]) -> list[str]:
    names = unique_strings([seed_name(seed), stage_base_name(seed_name(seed)), *(seed.get("aliases") or [])])
    prefixes = unique_strings(surname_prefix(name) for name in names if surname_prefix(name))
    aliases: list[str] = []
    for hint in seed.get("source_document_hints") or []:
        if not isinstance(hint, Mapping):
            continue
        locator = text_from(hint, "locator")
        if not locator:
            continue
        for raw_token in re.split(r"[\s，,。；;：:、/／()（）\[\]【】《》<>〈〉]+", locator):
            token = locator_alias_token(raw_token)
            if not token:
                continue
            if any(token.startswith(prefix) or prefix in token for prefix in prefixes):
                aliases.append(token)
            aliases.extend(title_alias_tokens_from_locator_token(token, names))
    return unique_strings(aliases)


def seed_aliases(seed: Mapping[str, Any], *, include_script_variants: bool = True) -> list[str]:
    values: list[Any] = [seed_name(seed), seed.get("normalized_name")]
    values.append(stage_base_name(seed_name(seed)))
    for raw_alias in seed.get("aliases") or []:
        if isinstance(raw_alias, Mapping):
            values.append(raw_alias.get("alias") or raw_alias.get("name") or raw_alias.get("text") or raw_alias.get("value"))
        else:
            values.append(raw_alias)
    for key in ("title", "temple_name", "posthumous_name", "courtesy_name", "art_name"):
        values.append(seed.get(key))
    values.extend(source_document_locator_aliases(seed))
    aliases = unique_strings(clean_name(value) for value in values if clean_name(value))
    if not include_script_variants:
        return aliases
    expanded: list[str] = []
    for alias in aliases:
        expanded.append(alias)
        expanded.extend(alias_script_variants(alias))
    return unique_strings(expanded)


def seed_source_hints(seed: Mapping[str, Any], *, source_hint_limit: int) -> list[str]:
    explicit = unique_strings(seed.get("source_hints") or seed.get("source_roots") or [])
    if explicit:
        return explicit[: max(1, source_hint_limit)]
    context = {
        "emperor_name": seed_name(seed),
        "target_payload": seed,
    }
    return source_hints_for_context(context, emp_metadata=dict(seed), max_hints=max(1, source_hint_limit))


def seed_is_emperor(seed: Mapping[str, Any]) -> bool:
    value = seed.get("is_emperor")
    if isinstance(value, bool):
        return value
    if clean_name(seed.get("object_role")) == "target_emperor":
        return True
    return clean_name(seed.get("seed_kind")) in {"emperor", "target_emperor", "emperor_annals"}


def source_role_for_seed(seed: Mapping[str, Any]) -> str:
    return "emperor_context" if seed_is_emperor(seed) else "object_biography_or_mentions"


def person_cache_code(seed: Mapping[str, Any]) -> str:
    explicit = text_from(seed, "person_cache_code", "object_code")
    if explicit:
        return f"PSC-{stable_hash(explicit, length=18)}"
    return f"PSC-{stable_hash([seed_name(seed), seed_aliases(seed, include_script_variants=False)], length=18)}"


def seed_priority(seed: Mapping[str, Any]) -> int:
    try:
        return max(1, int(seed.get("priority") or 100))
    except (TypeError, ValueError):
        return 100


def seed_period(seed: Mapping[str, Any]) -> str:
    return text_from(seed, "period", "dynasty", "target_period")


def normalize_seed(seed: Mapping[str, Any], *, seed_source: str) -> dict[str, Any]:
    name = seed_name(seed)
    if not name:
        raise ObjectSourceCacheSeedError(f"seed missing person name: {seed}")
    sources = unique_strings([*(seed.get("seed_sources") or []), seed_source])
    normalized = dict(seed)
    normalized.update(
        {
            "person_cache_code": person_cache_code(seed),
            "name": name,
            "normalized_name": text_from(seed, "normalized_name") or normalized_name(name),
            "aliases": seed_aliases(seed, include_script_variants=False),
            "expanded_aliases": seed_aliases(seed),
            "is_emperor": seed_is_emperor(seed),
            "seed_sources": sources,
            "priority": seed_priority(seed),
        }
    )
    return normalized


def dedupe_seeds(seeds: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    for seed in seeds:
        name = seed_name(seed)
        if not name:
            continue
        key = text_from(seed, "object_code") or normalized_name(name)
        if key not in by_key:
            by_key[key] = dict(seed)
            continue
        current = by_key[key]
        current["aliases"] = unique_strings([*(current.get("aliases") or []), *(seed.get("aliases") or [])])
        current["expanded_aliases"] = unique_strings([*(current.get("expanded_aliases") or []), *(seed.get("expanded_aliases") or [])])
        current["seed_sources"] = unique_strings([*(current.get("seed_sources") or []), *(seed.get("seed_sources") or [])])
        current["is_emperor"] = bool(current.get("is_emperor")) or bool(seed.get("is_emperor"))
        current["priority"] = min(seed_priority(current), seed_priority(seed))
    return sorted(by_key.values(), key=lambda row: (seed_priority(row), not bool(row.get("is_emperor")), seed_name(row)))


def alias_text_from_row(row: Mapping[str, Any]) -> str:
    return text_from(row, "alias_text", "alias", "name", "text", "value")


def alias_matches_seed_scope(seed: Mapping[str, Any], row: Mapping[str, Any]) -> bool:
    scope = clean_name(row.get("scope")) or "global"
    if scope == "global":
        return True
    if scope != "emperor":
        return False
    target_names = unique_strings(
        [
            *(seed.get("target_emperors") or []),
            seed.get("emperor_name"),
            seed.get("target_emperor"),
            seed.get("title"),
            seed.get("temple_name"),
            seed.get("posthumous_name"),
        ]
    )
    expanded_targets: list[str] = []
    for target in target_names:
        expanded_targets.append(target)
        expanded_targets.extend(alias_script_variants(target))
    scope_names = unique_strings([row.get("scope_emp_name"), row.get("scope_emp_title")])
    expanded_scope: list[str] = []
    for scope_name in scope_names:
        expanded_scope.append(scope_name)
        expanded_scope.extend(alias_script_variants(scope_name))
    return bool(set(expanded_targets) & set(expanded_scope))


def unique_alias_values(values: Sequence[Any]) -> list[Any]:
    result: list[Any] = []
    seen: set[tuple[str, str]] = set()
    for value in values:
        if isinstance(value, Mapping):
            alias = alias_text_from_row(value)
            scope = clean_name(value.get("scope")) or "global"
            if not alias:
                continue
            key = (normalize_title(alias), scope)
            item: Any = dict(value)
        else:
            alias = clean_name(value)
            if not alias:
                continue
            key = (normalize_title(alias), "global")
            item = alias
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def merge_object_pool_alias_rows(seeds: Sequence[Mapping[str, Any]], alias_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for seed in seeds:
        row = dict(seed)
        period = seed_period(row)
        seed_terms = {normalize_title(value) for value in seed_aliases(row) if normalize_title(value)}
        added_aliases: list[dict[str, Any]] = []
        for alias_row in alias_rows:
            alias_period = clean_name(alias_row.get("period"))
            if period and alias_period and alias_period != period:
                continue
            alias_text = alias_text_from_row(alias_row)
            canonical = text_from(alias_row, "canonical_name", "name")
            lookup_terms = {normalize_title(value) for value in [canonical, alias_text] if normalize_title(value)}
            if not seed_terms.intersection(lookup_terms):
                continue
            if not alias_matches_seed_scope(row, alias_row):
                continue
            if not alias_text:
                continue
            added_aliases.append(
                {
                    "alias": alias_text,
                    "alias_kind": clean_name(alias_row.get("alias_kind")) or "alias",
                    "scope": clean_name(alias_row.get("scope")) or "global",
                    "source": "raw_obj_aliases",
                }
            )
        if added_aliases:
            row["aliases"] = unique_alias_values([*(row.get("aliases") or []), *added_aliases])
            row["seed_sources"] = unique_strings([*(row.get("seed_sources") or []), "raw_obj_aliases"])
            row["object_pool_aliases"] = added_aliases
            row = normalize_seed(row, seed_source="raw_obj_aliases")
        merged.append(row)
    return dedupe_seeds(merged)


def object_pool_alias_tables_available(cur: Any) -> bool:
    for relation in ("raw_obj_aliases", "raw_objs", "emps"):
        cur.execute("select to_regclass(%s)", (relation,))
        if first_column(cur.fetchone()) is None:
            return False
    return True


def relation_available(cur: Any, relation: str) -> bool:
    cur.execute("select to_regclass(%s)", (relation,))
    return first_column(cur.fetchone()) is not None


def object_pool_alias_rows_for_seeds(cur: Any, seeds: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if not seeds or not object_pool_alias_tables_available(cur):
        return []
    periods = unique_strings(seed_period(seed) for seed in seeds if seed_period(seed))
    if not periods:
        return []
    names: list[str] = []
    terms: list[str] = []
    for seed in seeds:
        for alias in seed_aliases(seed):
            names.append(alias)
            terms.append(object_pool_normalized_alias(alias))
    names = unique_strings(names)
    terms = unique_strings(terms)
    if not names or not terms:
        return []
    cur.execute(OBJECT_POOL_ALIAS_ROWS_SQL, (periods, names, terms))
    return [dict(row) for row in cur.fetchall()]


def title_from_wikisource_url(url: str) -> str:
    if not url:
        return ""
    for marker in ("/wiki/", "/zh-hans/", "/zh-hant/", "/zh/"):
        if marker not in url:
            continue
        title = unquote(url.rsplit(marker, 1)[-1]).replace("_", " ")
        return normalize_title(title.split("#", 1)[0].split("?", 1)[0])
    return ""


def normalize_source_document_title(title: str) -> str:
    normalized = normalize_title(title)
    match = re.match(r"^(.+?/卷[零〇一二两兩三四五六七八九十百\d]{1,6}[上下]?)", normalized)
    return match.group(1) if match else normalized


def normalized_volume_locator(root: str, volume: str) -> str:
    match = re.search(r"卷([零〇一二两兩三四五六七八九十百\d]{1,6})([上下]?)", normalize_title(volume))
    if not match:
        return ""
    volume_number = chinese_volume_number(match.group(1))
    if not volume_number:
        return ""
    title = canonical_volume_title(root, volume_number)
    if match.group(2):
        title = f"{title}{match.group(2)}"
    return title


def source_root_text_aliases(root: str) -> list[str]:
    normalized = normalize_title(root)
    for canonical, aliases in SOURCE_HINT_TEXT_ALIASES.items():
        if normalized == canonical or normalized in aliases:
            return unique_strings(aliases)
    return [normalized] if normalized else []


def source_document_title_candidates(title: str) -> list[str]:
    normalized = normalize_source_document_title(title)
    if "/" not in normalized:
        return []
    full_root = normalized.split("/", 1)[0]
    suffix = normalized[len(full_root) :]
    plain_root = source_root_from_title(normalized)
    if full_root == plain_root:
        roots = unique_strings([*source_root_text_aliases(plain_root), plain_root])
    else:
        roots = unique_strings([full_root, *source_root_text_aliases(full_root), plain_root, *source_root_text_aliases(plain_root)])
    suffixes = [suffix]
    subpath_volume = re.search(r"/(?:[^/]+/)+(卷[零〇一二两兩三四五六七八九十百\d]{1,6}[上下]?)$", suffix)
    if subpath_volume:
        suffixes.append(f"/{subpath_volume.group(1)}")
    for raw_suffix in list(suffixes):
        match = re.search(r"卷(0+\d+)([上下]?)$", raw_suffix)
        if match:
            suffixes.append(raw_suffix[: match.start(1)] + str(int(match.group(1))) + match.group(2))
    return unique_strings(f"{root}{candidate_suffix}" for candidate_suffix in suffixes for root in roots if root)


def source_document_hint_title_candidates(hint: Mapping[str, Any]) -> list[str]:
    candidates: list[str] = []
    locator = normalize_title(text_from(hint, "locator", "source_title", "wikisource_title"))
    if "/" in locator:
        candidates.extend(source_document_title_candidates(locator))
    url_title = title_from_wikisource_url(text_from(hint, "url"))
    if url_title:
        candidates.extend(source_document_title_candidates(url_title) or [normalize_title(url_title)])
    title_root = source_root_from_title(text_from(hint, "title", "source_root"))
    volume = text_from(hint, "volume")
    if title_root and volume:
        volume_title = normalized_volume_locator(title_root, volume)
        if volume_title:
            candidates.extend(source_document_title_candidates(volume_title))
    return unique_strings(candidates)


def title_from_source_document_hint(hint: Mapping[str, Any]) -> str:
    candidates = source_document_hint_title_candidates(hint)
    return candidates[0] if candidates else ""


def seed_source_document_hints(seed: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw_hint in seed.get("source_document_hints") or []:
        if isinstance(raw_hint, Mapping):
            title = title_from_source_document_hint(raw_hint)
            if title:
                row = dict(raw_hint)
                row["wikisource_title"] = title
                row["wikisource_title_candidates"] = source_document_hint_title_candidates(raw_hint)
                rows.append(row)
            elif text_from(raw_hint, "url") and text_from(raw_hint, "title", "source_title"):
                row = dict(raw_hint)
                row["title"] = text_from(raw_hint, "title", "source_title")
                row["source_title"] = row["title"]
                row["source_kind"] = text_from(raw_hint, "source_kind") or "url_page"
                row["fetch_mode"] = "url"
                rows.append(row)
    return rows


def _increment(counter: dict[str, int], key: str) -> None:
    counter[key or ""] = counter.get(key or "", 0) + 1


def _sorted_counts(counter: Mapping[str, int]) -> dict[str, int]:
    return dict(sorted(counter.items(), key=lambda item: (-item[1], item[0])))


def _hint_has_resolvable_locator(hint: Mapping[str, Any]) -> bool:
    if text_from(hint, "locator", "source_title", "wikisource_title"):
        return True
    if text_from(hint, "url").startswith(("http://", "https://")):
        return True
    return bool(source_root_from_title(text_from(hint, "title", "source_root")) and text_from(hint, "volume"))


def seed_audit_report(seeds: Sequence[Mapping[str, Any]], *, max_issue_rows: int = 100) -> dict[str, Any]:
    period_counts: dict[str, int] = {}
    source_hint_counts: dict[str, int] = {}
    seed_source_counts: dict[str, int] = {}
    issue_counts: dict[str, int] = {}
    issue_rows: list[dict[str, Any]] = []
    invalid_rows: list[dict[str, Any]] = []
    totals = {
        "persons": len(seeds),
        "emperors": 0,
        "with_aliases": 0,
        "with_object_pool_aliases": 0,
        "with_source_hints": 0,
        "with_source_document_hints": 0,
        "with_resolvable_source_document_hints": 0,
        "with_target_emperors": 0,
        "invalid_rows": 0,
    }

    for index, seed in enumerate(seeds, start=1):
        name = seed_name(seed)
        if not name:
            totals["invalid_rows"] += 1
            invalid_rows.append({"row_number": index, "issue_code": "missing_person_name"})
            _increment(issue_counts, "missing_person_name")
            continue
        aliases = seed_aliases(seed, include_script_variants=False)
        source_hints = unique_strings(seed.get("source_hints") or seed.get("source_roots") or [])
        source_document_hints = [hint for hint in seed.get("source_document_hints") or [] if isinstance(hint, Mapping)]
        resolvable_source_document_hints = seed_source_document_hints(seed)
        object_pool_aliases = [row for row in seed.get("object_pool_aliases") or [] if isinstance(row, Mapping)]
        target_emperors = unique_strings(seed.get("target_emperors") or [])
        period = seed_period(seed)
        issues: list[str] = []

        if seed_is_emperor(seed):
            totals["emperors"] += 1
        if aliases:
            totals["with_aliases"] += 1
        if object_pool_aliases:
            totals["with_object_pool_aliases"] += 1
        if source_hints:
            totals["with_source_hints"] += 1
        else:
            issues.append("no_source_hints")
        if source_document_hints:
            totals["with_source_document_hints"] += 1
        else:
            issues.append("no_source_document_hints")
        if resolvable_source_document_hints:
            totals["with_resolvable_source_document_hints"] += 1
        elif source_document_hints:
            issues.append("no_resolvable_source_document_hints")
        if target_emperors:
            totals["with_target_emperors"] += 1
        if not aliases:
            issues.append("no_aliases")
        if not period and not source_hints:
            issues.append("no_period_and_no_source_hints")
        for hint in source_document_hints:
            if not _hint_has_resolvable_locator(hint):
                issues.append("source_document_hint_without_resolvable_locator")
                break

        _increment(period_counts, period or "(blank)")
        for source_hint in source_hints:
            _increment(source_hint_counts, source_hint)
        for seed_source in unique_strings(seed.get("seed_sources") or []):
            _increment(seed_source_counts, seed_source)
        for issue in unique_strings(issues):
            _increment(issue_counts, issue)
        if issues and len(issue_rows) < max(0, max_issue_rows):
            issue_rows.append(
                {
                    "row_number": index,
                    "person_name": name,
                    "period": period,
                    "seed_sources": unique_strings(seed.get("seed_sources") or []),
                    "source_hints": source_hints,
                    "source_document_hint_count": len(source_document_hints),
                    "resolvable_source_document_hint_count": len(resolvable_source_document_hints),
                    "alias_count": len(aliases),
                    "object_pool_alias_count": len(object_pool_aliases),
                    "issue_codes": unique_strings(issues),
                }
            )

    return {
        "schema": "retrieval_v3_object_source_cache_seed_audit_v1",
        "totals": totals,
        "period_counts": _sorted_counts(period_counts),
        "source_hint_counts": _sorted_counts(source_hint_counts),
        "seed_source_counts": _sorted_counts(seed_source_counts),
        "issue_counts": _sorted_counts(issue_counts),
        "issue_rows": issue_rows,
        "invalid_rows": invalid_rows[: max(0, max_issue_rows)],
    }


def render_seed_audit_markdown(report: Mapping[str, Any]) -> str:
    totals = report.get("totals") if isinstance(report.get("totals"), Mapping) else {}
    issue_counts = report.get("issue_counts") if isinstance(report.get("issue_counts"), Mapping) else {}
    source_hint_counts = report.get("source_hint_counts") if isinstance(report.get("source_hint_counts"), Mapping) else {}
    issue_rows = report.get("issue_rows") if isinstance(report.get("issue_rows"), Sequence) else []
    lines = [
        "# retrieval_v3 object source cache seed audit",
        "",
        "## Summary",
        "",
        f"- persons: `{totals.get('persons', 0)}`",
        f"- emperors: `{totals.get('emperors', 0)}`",
        f"- with_source_hints: `{totals.get('with_source_hints', 0)}`",
        f"- with_source_document_hints: `{totals.get('with_source_document_hints', 0)}`",
        f"- with_resolvable_source_document_hints: `{totals.get('with_resolvable_source_document_hints', 0)}`",
        f"- with_object_pool_aliases: `{totals.get('with_object_pool_aliases', 0)}`",
        f"- invalid_rows: `{totals.get('invalid_rows', 0)}`",
        "",
        "## Issue Counts",
        "",
    ]
    if issue_counts:
        for key, value in issue_counts.items():
            lines.append(f"- {key}: `{value}`")
    else:
        lines.append("- none: `0`")
    lines.extend(["", "## Top Source Hints", ""])
    if source_hint_counts:
        for key, value in list(source_hint_counts.items())[:20]:
            lines.append(f"- {key}: `{value}`")
    else:
        lines.append("- none: `0`")
    if issue_rows:
        lines.extend(["", "## Issue Rows", "", "| row | person | issues |", "| --- | --- | --- |"])
        for row in issue_rows[:50]:
            if not isinstance(row, Mapping):
                continue
            lines.append(f"| {row.get('row_number')} | {row.get('person_name')} | {', '.join(row.get('issue_codes') or [])} |")
    return "\n".join(lines) + "\n"


def rows_from_db(
    *,
    env_file: Path | None,
    dsn_env: str,
    limit: int = 0,
    include_object_pool_aliases: bool = False,
    source: str = "auto",
) -> list[dict[str, Any]]:
    if env_file is not None:
        load_env_file(env_file)
    psycopg, dict_row = import_psycopg()
    dsn = resolve_dsn(dsn_env)
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            use_retrieval_v3 = source == "retrieval-v2" or (source == "auto" and relation_available(cur, "retrieval_v3.objects"))
            if source == "retrieval-v2" and not relation_available(cur, "retrieval_v3.objects"):
                raise ObjectSourceCacheSeedError("retrieval_v3.objects table is not available")
            if not use_retrieval_v3 and not relation_available(cur, "raw_objs"):
                raise ObjectSourceCacheSeedError("raw_objs table is not available")
            sql = PERSON_SEEDS_SQL if use_retrieval_v3 else OBJECT_POOL_PERSON_SEEDS_SQL
            seed_source = "retrieval_v3.objects" if use_retrieval_v3 else "raw_objs"
            params: list[Any] = []
            if limit > 0:
                sql += "\nlimit %s"
                params.append(limit)
            cur.execute(sql, params if params else None)
            rows = [dict(row) for row in cur.fetchall()]
        conn.rollback()
    result: list[dict[str, Any]] = []
    for row in rows:
        payloads = row.get("target_payloads") if isinstance(row.get("target_payloads"), list) else []
        merged_payload: dict[str, Any] = {}
        for payload in payloads:
            if isinstance(payload, Mapping):
                for key in ("period", "dynasty", "title", "temple_name", "posthumous_name", "era", "source_targets"):
                    if key in payload and key not in merged_payload:
                        merged_payload[key] = payload[key]
        seed = {
            "object_code": row.get("object_code") or "",
            "name": row.get("name") or "",
            "normalized_name": row.get("normalized_name") or "",
            "object_type": row.get("object_type") or "person",
            "period": row.get("period") or merged_payload.get("period") or merged_payload.get("dynasty") or "",
            "aliases": row.get("aliases") or [],
            "source_hints": unique_strings(source_root_from_title(value) for value in row.get("source_hints") or [] if source_root_from_title(value)),
            "source_document_hints": row.get("source_document_hints") or [],
            "is_emperor": bool(row.get("is_emperor")),
            "target_emperors": row.get("target_emperors") or [],
            "seed_sources": [seed_source],
            "priority": 20 if row.get("is_emperor") else 60,
            **merged_payload,
        }
        result.append(normalize_seed(seed, seed_source=seed_source))
    result = dedupe_seeds(result)
    if include_object_pool_aliases:
        with psycopg.connect(dsn, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                alias_rows = object_pool_alias_rows_for_seeds(cur, result)
            conn.rollback()
        result = merge_object_pool_alias_rows(result, alias_rows)
    return result
