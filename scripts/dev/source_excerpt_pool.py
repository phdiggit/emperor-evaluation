from __future__ import annotations

import argparse
import html
import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE = ROOT / "data" / "query_profile_batches" / "i5b_layered_retrieval_profiles_20260630.jsonl"
WIKISOURCE_API = "https://zh.wikisource.org/w/api.php"
USER_AGENT = "emperor-evaluation-source-excerpt-pool/0.1"
ADJACENT_LAYER = "adjacent_split_objects"
KNOWN_SOURCE_TITLE_VARIANTS = {
    "史记": ("史记", "史記"),
    "汉书": ("汉书", "漢書"),
    "后汉书": ("后汉书", "後漢書"),
    "三国志": ("三国志", "三國志"),
    "晋书": ("晋书", "晉書"),
    "宋书": ("宋书", "宋書"),
    "南史": ("南史",),
    "北史": ("北史",),
    "隋书": ("隋书", "隋書"),
    "旧唐书": ("旧唐书", "舊唐書"),
    "新唐书": ("新唐书", "新唐書"),
    "宋史": ("宋史",),
    "建炎以来系年要录": ("建炎以来系年要录", "建炎以來繫年要錄"),
    "续资治通鉴": ("续资治通鉴", "續資治通鑑"),
    "资治通鉴": ("资治通鉴", "資治通鑑"),
    "贞观政要": ("贞观政要", "貞觀政要"),
    "唐会要": ("唐会要", "唐會要"),
    "册府元龟": ("册府元龟", "冊府元龜"),
    "战国策": ("战国策", "戰國策"),
    "东观汉记": ("东观汉记", "東觀漢記"),
    "明史": ("明史",),
    "明实录": ("明实录", "明實錄"),
    "清史稿": ("清史稿",),
    "清实录": ("清实录", "清實錄"),
    "元史": ("元史",),
    "辽史": ("辽史", "遼史"),
    "金史": ("金史",),
}


class ExcerptPoolError(ValueError):
    pass


@dataclass(frozen=True)
class CandidateObject:
    raw_name: str
    layer: str
    search_terms: tuple[str, ...]


@dataclass(frozen=True)
class SearchPlan:
    object_name: str
    layer: str
    query: str
    search_terms: tuple[str, ...]


def compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def strip_html(value: str) -> str:
    without_scripts = re.sub(r"<(script|style)\b.*?</\1>", " ", value, flags=re.IGNORECASE | re.DOTALL)
    without_tags = re.sub(r"<[^>]+>", " ", without_scripts)
    return compact_text(without_tags)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ExcerptPoolError(f"{path}:{line_number}: invalid JSON") from exc
        if not isinstance(value, dict):
            raise ExcerptPoolError(f"{path}:{line_number}: expected JSON object")
        rows.append(value)
    return rows


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
    for suffix in ("冤狱", "罢斥", "贬谪"):
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


def build_search_plans(
    profile: dict[str, Any],
    *,
    include_adjacent: bool = False,
    max_queries_per_object: int = 3,
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
    for candidate in iter_candidate_objects(profile, include_adjacent=include_adjacent):
        object_plans = [
            bundle
            for bundle in query_bundles
            if _bundle_matches(bundle, candidate.search_terms)
        ]
        if not object_plans:
            primary = candidate.search_terms[0]
            object_plans = [
                f"{person} {primary} 后汉书 任用 授权",
                f"{person} {primary} 资治通鉴 人才安全",
            ]

        for query in object_plans[:max_queries_per_object]:
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


def _fetch_json(url: str, *, timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read().decode("utf-8")
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ExcerptPoolError(f"unexpected JSON response from {url}")
    return value


def _api_url(params: dict[str, str]) -> str:
    query = urllib.parse.urlencode(params)
    return f"{WIKISOURCE_API}?{query}"


def wikisource_page_url(title: str) -> str:
    quoted = urllib.parse.quote(title.replace(" ", "_"), safe="/")
    return f"https://zh.wikisource.org/zh-hans/{quoted}"


def search_wikisource(
    query: str,
    *,
    limit: int,
    timeout: int,
    title_filters: Iterable[str] = (),
) -> list[dict[str, str]]:
    search_limit = max(limit, min(50, limit * 5))
    payload = _fetch_json(
        _api_url(
            {
                "action": "query",
                "list": "search",
                "srnamespace": "0",
                "srlimit": str(search_limit),
                "srsearch": query,
                "format": "json",
                "utf8": "1",
            }
        ),
        timeout=timeout,
    )
    results = payload.get("query", {}).get("search", [])
    if not isinstance(results, list):
        return []
    pages: list[dict[str, str]] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        title = str(result.get("title", "")).strip()
        if not title:
            continue
        if not title_matches_source_filters(title, title_filters):
            continue
        pages.append(
            {
                "title": title,
                "url": wikisource_page_url(title),
                "snippet": strip_html(str(result.get("snippet", ""))),
            }
        )
        if len(pages) >= limit:
            break
    return pages


def fetch_wikisource_plain_text(title: str, *, timeout: int) -> str:
    payload = _fetch_json(
        _api_url(
            {
                "action": "parse",
                "page": title,
                "prop": "text",
                "format": "json",
                "utf8": "1",
                "redirects": "1",
                "uselang": "zh-hans",
                "variant": "zh-hans",
            }
        ),
        timeout=timeout,
    )
    html_text = payload.get("parse", {}).get("text", {}).get("*", "")
    if not isinstance(html_text, str) or not html_text:
        return ""
    return strip_html(html_text)


def extract_passages(
    text: str,
    terms: Iterable[str],
    *,
    context_chars: int,
    max_passages: int,
) -> list[dict[str, str]]:
    normalized = compact_text(text)
    passages: list[dict[str, str]] = []
    occupied: list[tuple[int, int]] = []

    for term in terms:
        if len(term) < 2:
            continue
        for match in re.finditer(re.escape(term), normalized):
            start = max(0, match.start() - context_chars)
            end = min(len(normalized), match.end() + context_chars)
            if any(not (end < used_start or start > used_end) for used_start, used_end in occupied):
                continue
            occupied.append((start, end))
            passages.append(
                {
                    "matched_term": term,
                    "text": normalized[start:end],
                }
            )
            if len(passages) >= max_passages:
                return passages
    return passages


def build_excerpt_pool(
    profile: dict[str, Any],
    *,
    include_adjacent: bool = False,
    max_queries: int | None = None,
    max_queries_per_object: int = 3,
    pages_per_query: int = 2,
    context_chars: int = 220,
    max_passages_per_page: int = 2,
    timeout: int = 20,
    offline: bool = False,
) -> dict[str, Any]:
    plans = build_search_plans(
        profile,
        include_adjacent=include_adjacent,
        max_queries_per_object=max_queries_per_object,
    )
    if max_queries is not None:
        plans = plans[:max_queries]

    objects = [
        {
            "name": candidate.raw_name,
            "layer": candidate.layer,
            "search_terms": list(candidate.search_terms),
        }
        for candidate in iter_candidate_objects(profile, include_adjacent=include_adjacent)
    ]
    report: dict[str, Any] = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "person": profile.get("person"),
        "query_profile_id": profile.get("query_profile_id"),
        "offline": offline,
        "objects": objects,
        "title_filters": list(source_title_filters(profile)),
        "errors": [],
        "search_plans": [
            {
                "object_name": plan.object_name,
                "layer": plan.layer,
                "query": plan.query,
                "search_terms": list(plan.search_terms),
            }
            for plan in plans
        ],
        "excerpts": [],
    }
    if offline:
        return report

    page_cache: dict[str, str] = {}
    excerpts: list[dict[str, Any]] = []
    title_filters = source_title_filters(profile)
    for plan in plans:
        try:
            pages = search_wikisource(plan.query, limit=pages_per_query, timeout=timeout, title_filters=title_filters)
        except Exception as exc:  # pragma: no cover - exercised by live network only.
            report["errors"].append({"stage": "search", "query": plan.query, "error": repr(exc)})
            continue
        for page in pages:
            title = page["title"]
            if title not in page_cache:
                try:
                    page_cache[title] = fetch_wikisource_plain_text(title, timeout=timeout)
                except Exception as exc:  # pragma: no cover - exercised by live network only.
                    report["errors"].append(
                        {
                            "stage": "fetch_page",
                            "query": plan.query,
                            "page_title": title,
                            "error": repr(exc),
                        }
                    )
                    continue
            passages = extract_passages(
                page_cache[title],
                plan.search_terms,
                context_chars=context_chars,
                max_passages=max_passages_per_page,
            )
            if not passages and page["snippet"]:
                passages = [{"matched_term": "search_snippet", "text": page["snippet"]}]
            if not passages:
                continue
            excerpts.append(
                {
                    "object_name": plan.object_name,
                    "layer": plan.layer,
                    "query": plan.query,
                    "page_title": title,
                    "page_url": page["url"],
                    "search_snippet": page["snippet"],
                    "passages": passages,
                }
            )

    report["excerpts"] = excerpts
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# {report.get('person', '')} source excerpt pool",
        "",
        f"- query_profile_id: `{report.get('query_profile_id', '')}`",
        f"- offline: `{report.get('offline')}`",
        f"- objects: `{len(report.get('objects', []))}`",
        f"- excerpts: `{len(report.get('excerpts', []))}`",
        "",
        "## Objects",
        "",
    ]
    for obj in report.get("objects", []):
        terms = ", ".join(f"`{term}`" for term in obj.get("search_terms", []))
        lines.append(f"- `{obj.get('name')}` ({obj.get('layer')}): {terms}")

    lines.extend(["", "## Search Plans", ""])
    for plan in report.get("search_plans", []):
        lines.append(f"- `{plan.get('object_name')}`: {plan.get('query')}")

    lines.extend(["", "## Excerpts", ""])
    for item in report.get("excerpts", []):
        lines.append(f"### {item.get('object_name')} / {item.get('page_title')}")
        lines.append("")
        lines.append(f"- layer: `{item.get('layer')}`")
        lines.append(f"- query: `{item.get('query')}`")
        lines.append(f"- page: {item.get('page_url')}")
        for passage in item.get("passages", []):
            lines.append("")
            lines.append(f"> [{passage.get('matched_term')}] {passage.get('text')}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_report(path: Path, report: dict[str, Any], *, output_format: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "json":
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return
    if output_format == "markdown":
        path.write_text(render_markdown(report), encoding="utf-8")
        return
    raise ExcerptPoolError(f"unknown output format: {output_format}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a review-first source excerpt pool from an I5B query profile.")
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE, help="Query-profile JSONL path.")
    parser.add_argument("--person", required=True, help="Profile person name.")
    parser.add_argument("--output", type=Path, required=True, help="Output report path.")
    parser.add_argument("--format", choices=("json", "markdown"), default="json", help="Output format.")
    parser.add_argument("--include-adjacent", action="store_true", help="Include adjacent_split_objects.")
    parser.add_argument("--offline", action="store_true", help="Only build object/query plans; do not call Wikisource.")
    parser.add_argument("--max-queries", type=int, default=None, help="Global maximum query count.")
    parser.add_argument("--max-queries-per-object", type=int, default=3, help="Maximum queries per object.")
    parser.add_argument("--pages-per-query", type=int, default=2, help="Wikisource pages to inspect per query.")
    parser.add_argument("--context-chars", type=int, default=220, help="Characters before/after each hit.")
    parser.add_argument("--max-passages-per-page", type=int, default=2, help="Passages to keep per page.")
    parser.add_argument("--timeout", type=int, default=20, help="Network timeout in seconds.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    profile = load_profile(args.profile, args.person)
    report = build_excerpt_pool(
        profile,
        include_adjacent=args.include_adjacent,
        max_queries=args.max_queries,
        max_queries_per_object=args.max_queries_per_object,
        pages_per_query=args.pages_per_query,
        context_chars=args.context_chars,
        max_passages_per_page=args.max_passages_per_page,
        timeout=args.timeout,
        offline=args.offline,
    )
    write_report(args.output, report, output_format=args.format)
    print(json.dumps({"output": str(args.output), "objects": len(report["objects"]), "excerpts": len(report["excerpts"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
