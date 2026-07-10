from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v2_contracts import unique_strings  # noqa: E402
from scripts.dev.retrieval_v2_object_source_cache_seed import (  # noqa: E402
    seed_source_document_hints,
    source_document_hint_title_candidates,
    title_from_wikisource_url,
)
from scripts.dev.retrieval_v2_taskgen_preseed import normalize_title, source_root_from_title, text_from  # noqa: E402


SCHEMA_VERSION = "1.0"
DEFAULT_USER_AGENT = "emperor-evaluation-retrieval-v2-summary-lead/0.1"
DEFAULT_LEAD_TERMS = (
    "赐死",
    "賜死",
    "被杀",
    "被殺",
    "诛杀",
    "誅殺",
    "诛死",
    "誅死",
    "诛",
    "誅",
    "处死",
    "處死",
    "株连",
    "株連",
    "三族",
    "九族",
    "连坐",
    "連坐",
    "谋反",
    "謀反",
    "伏诛",
    "伏誅",
    "自尽",
    "自盡",
    "自刎",
    "籍其家",
    "籍没",
    "籍沒",
    "流放",
    "流徙",
    "大逆",
)


class SummaryLeadDiscoveryError(RuntimeError):
    pass


def compact_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def stable_hash(value: Any, *, length: int = 18) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()[:length].upper()


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pretty_json(dict(payload)), encoding="utf-8", newline="\n")


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(stable_json(row) + "\n" for row in rows), encoding="utf-8", newline="\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise SummaryLeadDiscoveryError(f"{path}:{line_no}: expected JSON object")
        rows.append(payload)
    return rows


def fetch_url(url: str, *, timeout: int) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


class WikipediaSectionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.page_title = ""
        self.current_section = ""
        self._heading_tag = ""
        self._heading_parts: list[str] = []
        self._block_tag = ""
        self._block_parts: list[str] = []
        self._link_href = ""
        self._link_parts: list[str] = []
        self._skip_depth = 0
        self.sections: dict[str, list[str]] = {}
        self.links_by_section: dict[str, list[dict[str, str]]] = {}
        self.all_links: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {key: value or "" for key, value in attrs}
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "h1" and not self.page_title:
            self._heading_tag = tag
            self._heading_parts = []
            return
        if tag in {"h2", "h3"}:
            self._heading_tag = tag
            self._heading_parts = []
            return
        if tag in {"p", "li"} and self.current_section:
            self._block_tag = tag
            self._block_parts = []
        if tag == "a":
            self._link_href = attrs_map.get("href", "")
            self._link_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag == self._heading_tag:
            heading = clean_heading("".join(self._heading_parts))
            if tag == "h1" and heading and not self.page_title:
                self.page_title = heading
            elif heading:
                self.current_section = heading
                self.sections.setdefault(heading, [])
            self._heading_tag = ""
            self._heading_parts = []
        if tag == self._block_tag:
            text = compact_text("".join(self._block_parts))
            if text and self.current_section:
                self.sections.setdefault(self.current_section, []).append(text)
            self._block_tag = ""
            self._block_parts = []
        if tag == "a" and self._link_href:
            link_text = compact_text("".join(self._link_parts))
            row = {"href": html.unescape(self._link_href), "text": link_text}
            self.all_links.append(row)
            if self.current_section:
                self.links_by_section.setdefault(self.current_section, []).append(row)
            self._link_href = ""
            self._link_parts = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._heading_tag:
            self._heading_parts.append(data)
        if self._block_tag:
            self._block_parts.append(data)
        if self._link_href:
            self._link_parts.append(data)


def clean_heading(value: str) -> str:
    text = compact_text(value)
    text = re.sub(r"\[\s*编辑\s*\]$", "", text)
    return text.strip()


def parse_wikipedia_html(html_text: str) -> dict[str, Any]:
    parser = WikipediaSectionParser()
    parser.feed(html_text)
    parser.close()
    return {
        "page_title": parser.page_title,
        "sections": parser.sections,
        "links_by_section": parser.links_by_section,
        "all_links": parser.all_links,
    }


def section_matches(name: str, wanted: str) -> bool:
    return normalize_title(name) == normalize_title(wanted)


def section_payload(parsed: Mapping[str, Any], section_title: str) -> tuple[str, str, list[dict[str, str]]]:
    sections = parsed.get("sections") if isinstance(parsed.get("sections"), Mapping) else {}
    links_by_section = parsed.get("links_by_section") if isinstance(parsed.get("links_by_section"), Mapping) else {}
    all_links = parsed.get("all_links") if isinstance(parsed.get("all_links"), list) else []
    for title, paragraphs in sections.items():
        if section_matches(str(title), section_title):
            text = compact_text(" ".join(str(row) for row in paragraphs if str(row).strip()))
            links = [dict(row) for row in links_by_section.get(title, []) if isinstance(row, Mapping)]
            if not links:
                links = [dict(row) for row in all_links if isinstance(row, Mapping)]
            return str(title), text, links
    available = ", ".join(str(key) for key in sections.keys())
    raise SummaryLeadDiscoveryError(f"section not found: {section_title}; available={available}")


def absolute_url(href: str, *, base_url: str) -> str:
    return urllib.parse.urljoin(base_url, href)


def is_wikisource_url(url: str) -> bool:
    host = urllib.parse.urlparse(url).netloc.lower()
    return host.endswith("wikisource.org") and "/wiki/" in url


def source_hint_from_wikisource_link(link: Mapping[str, str], *, base_url: str, section_title: str) -> dict[str, Any]:
    url = absolute_url(text_from(link, "href"), base_url=base_url)
    title = title_from_wikisource_url(url)
    link_text = text_from(link, "text")
    root = source_root_from_title(title) or source_root_from_title(link_text)
    hint = {
        "title": root or link_text or title,
        "locator": title or link_text,
        "url": url,
        "discovery_source_kind": "wikipedia_summary",
        "discovery_section_title": section_title,
        "evidence_policy": "lead_only_not_provenance",
    }
    candidates = source_document_hint_title_candidates(hint)
    if candidates:
        hint["wikisource_title"] = candidates[0]
        hint["wikisource_title_candidates"] = candidates
    return hint


def source_document_hints_from_links(links: Sequence[Mapping[str, str]], *, base_url: str, section_title: str) -> list[dict[str, Any]]:
    hints: list[dict[str, Any]] = []
    seen: set[str] = set()
    for link in links:
        url = absolute_url(text_from(link, "href"), base_url=base_url)
        if not is_wikisource_url(url):
            continue
        hint = source_hint_from_wikisource_link(link, base_url=base_url, section_title=section_title)
        key = text_from(hint, "wikisource_title", "url", "locator")
        if not key or key in seen:
            continue
        seen.add(key)
        hints.append(hint)
    return hints


def matched_lead_terms(section_text: str, terms: Sequence[str]) -> list[str]:
    return unique_strings(term for term in terms if term and term in section_text)


def source_roots_from_hints(hints: Sequence[Mapping[str, Any]]) -> list[str]:
    roots: list[str] = []
    for hint in hints:
        root = text_from(hint, "title")
        if root:
            roots.append(root)
    return unique_strings(roots)


def build_summary_lead(
    *,
    person_name: str,
    discovery_url: str,
    page_title: str,
    section_title: str,
    section_text: str,
    source_document_hints: Sequence[Mapping[str, Any]],
    lead_terms: Sequence[str],
) -> dict[str, Any]:
    terms = matched_lead_terms(section_text, lead_terms)
    return {
        "schema_version": SCHEMA_VERSION,
        "lead_code": f"SLD-{stable_hash([person_name, discovery_url, section_title, terms])}",
        "person_name": person_name,
        "lead_source_kind": "wikipedia_summary",
        "discovery_url": discovery_url,
        "discovery_title": page_title,
        "section_title": section_title,
        "lead_terms": terms,
        "summary_text": section_text,
        "source_document_hints": list(source_document_hints),
        "source_roots": source_roots_from_hints(source_document_hints),
        "evidence_policy": "lead_only_not_provenance",
    }


def seed_patch_from_leads(person_name: str, leads: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    hints: list[dict[str, Any]] = []
    source_hints: list[str] = []
    lead_refs: list[dict[str, Any]] = []
    for lead in leads:
        for hint in lead.get("source_document_hints") or []:
            if isinstance(hint, Mapping):
                hints.append(dict(hint))
        source_hints.extend(str(value) for value in lead.get("source_roots") or [] if str(value).strip())
        lead_refs.append(
            {
                "lead_code": lead.get("lead_code"),
                "lead_source_kind": lead.get("lead_source_kind"),
                "discovery_url": lead.get("discovery_url"),
                "section_title": lead.get("section_title"),
                "lead_terms": lead.get("lead_terms") or [],
                "evidence_policy": lead.get("evidence_policy"),
            }
        )
    seed = {
        "name": person_name,
        "seed_sources": ["summary_lead_discovery:wikipedia"],
        "source_hints": unique_strings(source_hints),
        "source_document_hints": dedupe_hints(hints),
        "summary_leads": lead_refs,
    }
    # Normalize resolvable hints now so downstream object-source cache can take
    # the fast path without searching.
    seed["source_document_hints"] = seed_source_document_hints(seed)
    return seed


def dedupe_hints(hints: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for hint in hints:
        key = text_from(hint, "wikisource_title", "url", "locator", "title")
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append(dict(hint))
    return rows


def discover_from_html(
    html_text: str,
    *,
    person_name: str,
    discovery_url: str,
    section_titles: Sequence[str],
    lead_terms: Sequence[str] = DEFAULT_LEAD_TERMS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    parsed = parse_wikipedia_html(html_text)
    page_title = text_from(parsed, "page_title") or person_name
    all_links = [dict(row) for row in parsed.get("all_links") or [] if isinstance(row, Mapping)]
    leads: list[dict[str, Any]] = []
    for requested_section in section_titles:
        actual_section, text, links = section_payload(parsed, requested_section)
        hints = source_document_hints_from_links(links, base_url=discovery_url, section_title=actual_section)
        if not hints:
            hints = source_document_hints_from_links(all_links, base_url=discovery_url, section_title=actual_section)
        leads.append(
            build_summary_lead(
                person_name=person_name,
                discovery_url=discovery_url,
                page_title=page_title,
                section_title=actual_section,
                section_text=text,
                source_document_hints=hints,
                lead_terms=lead_terms,
            )
        )
    report = {
        "ok": True,
        "generated_by": "scripts/dev/retrieval_v2_summary_lead_discovery.py",
        "lead_count": len(leads),
        "person_name": person_name,
        "discovery_url": discovery_url,
        "sections": [lead["section_title"] for lead in leads],
        "source_document_hint_count": sum(len(lead.get("source_document_hints") or []) for lead in leads),
        "resolvable_source_document_hint_count": len(seed_patch_from_leads(person_name, leads).get("source_document_hints") or []),
    }
    return leads, report


def job_sections(job: Mapping[str, Any]) -> list[str]:
    raw = job.get("sections") or job.get("section")
    if isinstance(raw, str):
        values = [raw]
    elif isinstance(raw, Sequence) and not isinstance(raw, (bytes, str)):
        values = [str(value or "") for value in raw]
    else:
        values = []
    sections = unique_strings(value.strip() for value in values if value.strip())
    if not sections:
        raise SummaryLeadDiscoveryError(f"lead discovery job missing section(s): {job}")
    return sections


def job_lead_terms(job: Mapping[str, Any], base_terms: Sequence[str]) -> list[str]:
    raw = job.get("lead_terms") or job.get("lead_term") or []
    if isinstance(raw, str):
        values = [raw]
    elif isinstance(raw, Sequence) and not isinstance(raw, (bytes, str)):
        values = [str(value or "") for value in raw]
    else:
        values = []
    return unique_strings([*base_terms, *values])


def html_for_job(job: Mapping[str, Any], *, timeout: int) -> str:
    html_path = text_from(job, "input_html", "html_path")
    if html_path:
        return Path(html_path).read_text(encoding="utf-8")
    url = text_from(job, "url", "discovery_url")
    if not url:
        raise SummaryLeadDiscoveryError(f"lead discovery job missing url: {job}")
    return fetch_url(url, timeout=timeout)


def discover_job(job: Mapping[str, Any], *, timeout: int, lead_terms: Sequence[str]) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    person_name = text_from(job, "person", "person_name", "name", "object_name")
    if not person_name:
        raise SummaryLeadDiscoveryError(f"lead discovery job missing person: {job}")
    url = text_from(job, "url", "discovery_url")
    if not url:
        raise SummaryLeadDiscoveryError(f"lead discovery job missing url: {job}")
    leads, report = discover_from_html(
        html_for_job(job, timeout=timeout),
        person_name=person_name,
        discovery_url=url,
        section_titles=job_sections(job),
        lead_terms=job_lead_terms(job, lead_terms),
    )
    seed = seed_patch_from_leads(person_name, leads)
    return leads, seed, report


def discover_jobs(jobs: Sequence[Mapping[str, Any]], *, timeout: int, lead_terms: Sequence[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    all_leads: list[dict[str, Any]] = []
    seeds: list[dict[str, Any]] = []
    reports: list[dict[str, Any]] = []
    for job in jobs:
        leads, seed, report = discover_job(job, timeout=timeout, lead_terms=lead_terms)
        all_leads.extend(leads)
        seeds.append(seed)
        reports.append(report)
    return all_leads, seeds, {
        "ok": True,
        "generated_by": "scripts/dev/retrieval_v2_summary_lead_discovery.py",
        "job_count": len(jobs),
        "lead_count": len(all_leads),
        "seed_count": len(seeds),
        "source_document_hint_count": sum(len(lead.get("source_document_hints") or []) for lead in all_leads),
        "resolvable_source_document_hint_count": sum(len(seed.get("source_document_hints") or []) for seed in seeds),
        "jobs": reports,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build lead-only source hints from summary pages such as Wikipedia.")
    parser.add_argument("--url", help="Summary page URL. Used as fetch target unless --input-html is set.")
    parser.add_argument("--input-html", type=Path, help="Read already-fetched HTML from this file instead of fetching --url.")
    parser.add_argument("--person", help="Person/object name for generated seed rows.")
    parser.add_argument("--section", action="append", default=[], help="Section title to mine. Repeat for multiple sections.")
    parser.add_argument("--input-jobs-jsonl", type=Path, help="Batch jobs JSONL with person/url/sections and optional input_html.")
    parser.add_argument("--lead-term", action="append", default=[], help="Additional lead trigger term to record when present.")
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--output-leads-jsonl", type=Path)
    parser.add_argument("--output-seeds-jsonl", type=Path)
    parser.add_argument("--output-report-json", type=Path)
    args = parser.parse_args(argv)

    lead_terms = unique_strings([*DEFAULT_LEAD_TERMS, *args.lead_term])
    if args.input_jobs_jsonl:
        leads, seeds, report = discover_jobs(read_jsonl(args.input_jobs_jsonl), timeout=args.timeout, lead_terms=lead_terms)
    else:
        if not args.url or not args.person or not args.section:
            raise SummaryLeadDiscoveryError("single-page mode requires --url, --person and at least one --section")
        html_text = args.input_html.read_text(encoding="utf-8") if args.input_html else fetch_url(args.url, timeout=args.timeout)
        leads, report = discover_from_html(
            html_text,
            person_name=args.person,
            discovery_url=args.url,
            section_titles=args.section,
            lead_terms=lead_terms,
        )
        seeds = [seed_patch_from_leads(args.person, leads)]
    if args.output_leads_jsonl:
        write_jsonl(args.output_leads_jsonl, leads)
    if args.output_seeds_jsonl:
        write_jsonl(args.output_seeds_jsonl, seeds)
    if args.output_report_json:
        write_json(args.output_report_json, report)
    print(pretty_json(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
