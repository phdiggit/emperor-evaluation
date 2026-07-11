from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v2_contracts import alias_script_variants, unique_strings  # noqa: E402
from scripts.dev.retrieval_v2_object_source_cache_seed import normalize_seed  # noqa: E402


FETCH_DECISION = "fetch_missing_source"


class ExpectedEventSourceRefinementError(RuntimeError):
    pass


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def stable_code(prefix: str, value: Any, *, length: int = 20) -> str:
    digest = hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()[:length].upper()
    return f"{prefix}-{digest}"


def text(value: Any) -> str:
    return str(value or "").strip()


def strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if text(value) else []
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [text(item) for item in value if text(item)]
    return []


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ExpectedEventSourceRefinementError(f"{path}: expected JSON object")
    return payload


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ExpectedEventSourceRefinementError(f"{path}:{line_no}: expected JSON object")
        rows.append(payload)
    return rows


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(stable_json(dict(row)) + "\n" for row in rows), encoding="utf-8", newline="\n")


def object_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return text(row.get("emperor_name")), text(row.get("object_id")), text(row.get("object_name"))


def dedupe_source_leads(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for lead in rows:
        key = text(lead.get("source_title")), text(lead.get("locator_hint"))
        if not any(key):
            continue
        current = by_key.setdefault(key, {"source_title": key[0], "locator_hint": key[1], "query_terms": []})
        current["query_terms"] = unique_strings([*current["query_terms"], *strings(lead.get("query_terms"))])
    return sorted(by_key.values(), key=lambda row: (row["source_title"], row["locator_hint"]))


def source_titles_from_lead(lead: Mapping[str, Any]) -> list[str]:
    combined = " ".join([text(lead.get("source_title")), text(lead.get("locator_hint"))])
    marked = re.findall(r"《([^》]+)》", combined)
    return unique_strings(title.split("·", 1)[0] for title in (marked or [text(lead.get("source_title"))]) if title)


def source_document_hints(source_leads: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    hints: dict[tuple[str, str], dict[str, Any]] = {}
    for lead in source_leads:
        combined = " ".join([text(lead.get("source_title")), text(lead.get("locator_hint"))])
        title_marks = list(re.finditer(r"《([^》]+)》", combined))
        for index, title_match in enumerate(title_marks):
            segment_end = title_marks[index + 1].start() if index + 1 < len(title_marks) else len(combined)
            segment = combined[title_match.end() : segment_end]
            volumes = unique_strings(re.findall(r"卷[零〇一二两兩三四五六七八九十百\d]{1,6}[上下]?", segment))
            for volume in volumes:
                key = title_match.group(1), volume
                hints.setdefault(
                    key,
                    {
                        "source_title": title_match.group(1),
                        "title": title_match.group(1),
                        "volume": volume,
                        "locator": text(lead.get("locator_hint")),
                        "query_terms": strings(lead.get("query_terms")),
                        "source_kind": "expected_event_authoritative_lead",
                    },
                )
    return list(hints.values())


def aliases_for_object(object_name: str, inventory_rows: Sequence[Mapping[str, Any]]) -> list[str]:
    explicit: list[str] = []
    for row in inventory_rows:
        explicit.extend(strings(row.get("aliases") or row.get("object_aliases")))
    return unique_strings([object_name, *explicit, *alias_script_variants(object_name)])


def priority_for_events(events: Sequence[Mapping[str, Any]]) -> int:
    if any(text(row.get("importance")) == "major" for row in events):
        return 10
    if any(text(row.get("importance")) == "secondary" for row in events):
        return 30
    return 50


def object_source_cache_query_rows(seed: Mapping[str, Any]) -> list[dict[str, str]]:
    refinement = seed.get("expected_event_refinement")
    if not isinstance(refinement, Mapping):
        return []
    rows: list[dict[str, str]] = []
    for raw in refinement.get("search_queries") or []:
        if not isinstance(raw, Mapping):
            continue
        query = text(raw.get("query"))
        if not query:
            continue
        rows.append(
            {
                "query": query,
                "base_query": query,
                "query_name": text(seed.get("name") or seed.get("person_name")),
                "search_name": text(seed.get("name") or seed.get("person_name")),
                "source_hint": text(raw.get("source_hint")),
                "event_inventory_code": text(raw.get("event_inventory_code")),
                "query_kind": "expected_event_refinement",
            }
        )
    return rows


def refinement_queries(pairs: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for event, _result in pairs:
        leads = [lead for lead in (event.get("source_leads") or []) if isinstance(lead, Mapping)]
        lead = leads[0] if leads else {}
        terms = strings(lead.get("query_terms")) or unique_strings(
            [
                text(event.get("object_name")),
                *strings(event.get("event_anchor_terms")),
                *strings(event.get("duty_anchor_terms")),
                *strings(event.get("outcome_anchor_terms")),
            ]
        )
        query = " ".join(terms[:5])
        source_titles = source_titles_from_lead(lead) if lead else []
        source_hint = source_titles[0] if source_titles else ""
        key = query, source_hint
        if not query or key in seen:
            continue
        rows.append(
            {
                "event_inventory_code": text(event.get("event_inventory_code")),
                "query": query,
                "source_hint": source_hint,
            }
        )
        seen.add(key)
    return rows


def build_refinement_packages(
    inventory_rows: Sequence[Mapping[str, Any]], reconciliation_rows: Sequence[Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    inventory_by_code = {
        text(row.get("event_inventory_code")): dict(row)
        for row in inventory_rows
        if text(row.get("record_type")) == "expected_event" and text(row.get("event_inventory_code"))
    }
    fetch_rows = [row for row in reconciliation_rows if text(row.get("decision")) == FETCH_DECISION]
    grouped: dict[tuple[str, str, str], list[tuple[dict[str, Any], Mapping[str, Any]]]] = {}
    for result in fetch_rows:
        event_code = text(result.get("event_inventory_code"))
        inventory = inventory_by_code.get(event_code)
        if inventory is None:
            raise ExpectedEventSourceRefinementError(f"reconciliation event missing from inventory: {event_code}")
        if object_key(result) != object_key(inventory):
            raise ExpectedEventSourceRefinementError(f"event identity mismatch: {event_code}")
        grouped.setdefault(object_key(inventory), []).append((inventory, result))

    packages: list[dict[str, Any]] = []
    seeds: list[dict[str, Any]] = []
    for (emperor_name, object_id, object_name), pairs in sorted(grouped.items()):
        events = [pair[0] for pair in pairs]
        results = [pair[1] for pair in pairs]
        leads = dedupe_source_leads(
            lead for event in events for lead in (event.get("source_leads") or []) if isinstance(lead, Mapping)
        )
        aliases = aliases_for_object(object_name, events)
        event_rows = [
            {
                "event_inventory_code": text(event.get("event_inventory_code")),
                "event_label": text(event.get("event_label")),
                "direction": text(event.get("direction")),
                "importance": text(event.get("importance")),
                "domain": text(event.get("domain")),
                "event_anchor_terms": strings(event.get("event_anchor_terms")),
                "duty_anchor_terms": strings(event.get("duty_anchor_terms")),
                "outcome_anchor_terms": strings(event.get("outcome_anchor_terms")),
                "missing_facets": strings(result.get("missing_facets")),
            }
            for event, result in pairs
        ]
        query_terms = unique_strings(
            [
                object_name,
                *aliases,
                *(term for lead in leads for term in strings(lead.get("query_terms"))),
                *(term for event in events for key in ("event_anchor_terms", "duty_anchor_terms", "outcome_anchor_terms") for term in strings(event.get(key))),
            ]
        )
        search_queries = refinement_queries(pairs)
        package_code = stable_code("EESR", [emperor_name, object_id, object_name, [row["event_inventory_code"] for row in event_rows]])
        package = {
            "refinement_code": package_code,
            "workflow_code": "retrieval_v3_expected_event_source_refinement",
            "item_code": "I5B",
            "rule_code": "appointment_delegation",
            "emperor_name": emperor_name,
            "object_id": int(object_id) if object_id.isdigit() else object_id,
            "object_name": object_name,
            "aliases": aliases,
            "priority": priority_for_events(events),
            "missing_event_count": len(event_rows),
            "missing_events": event_rows,
            "source_leads": leads,
            "query_terms": query_terms,
            "refinement_queries": search_queries,
            "already_checked": {
                "claim_keys": unique_strings(key for row in results for key in strings(row.get("claim_keys"))),
                "group_keys": unique_strings(key for row in results for key in strings(row.get("group_keys"))),
                "source_slice_refs": unique_strings(key for row in results for key in strings(row.get("source_slice_refs"))),
            },
            "write_db": False,
            "enqueue_allowed": False,
            "scoring_allowed": False,
            "next_stage": "retrieval_v2_object_source_cache",
        }
        packages.append(package)
        seeds.append(
            normalize_seed(
                {
                    "object_code": f"v3-object-{object_id}" if object_id else "",
                    "person_name": object_name,
                    "target_emperor": emperor_name,
                    "aliases": aliases,
                    "priority": package["priority"],
                    "capture_profile": "expected_event_source_refinement",
                    "source_hints": unique_strings(title for lead in leads for title in source_titles_from_lead(lead)),
                    "source_document_hints": source_document_hints(leads),
                    "query_terms": query_terms,
                    "expected_event_refinement": {
                        "refinement_code": package_code,
                        "event_inventory_codes": [row["event_inventory_code"] for row in event_rows],
                        "already_checked": package["already_checked"],
                        "search_queries": search_queries,
                    },
                },
                seed_source="retrieval_v3_expected_event_source_refinement",
            )
        )

    report = {
        "ok": True,
        "generated_by": "scripts/dev/retrieval_v3_expected_event_source_refinement.py",
        "input_reconciliation_rows": len(reconciliation_rows),
        "fetch_event_requests": len(fetch_rows),
        "object_refinement_packages": len(packages),
        "requests_avoided_by_coalescing": max(0, len(fetch_rows) - len(packages)),
        "event_direction_counts": dict(
            sorted(Counter(text(inventory_by_code[text(row.get("event_inventory_code"))].get("direction")) for row in fetch_rows).items())
        ),
        "write_db": False,
        "enqueue_allowed": False,
        "scoring_allowed": False,
        "progress_allowed": False,
        "next_action": "review_object_packages_then_run_object_source_cache",
    }
    return packages, seeds, report


def render_markdown(report: Mapping[str, Any], packages: Sequence[Mapping[str, Any]]) -> str:
    lines = [
        "# Expected-event object source refinement",
        "",
        f"- fetch event requests: `{report.get('fetch_event_requests', 0)}`",
        f"- object refinement packages: `{report.get('object_refinement_packages', 0)}`",
        f"- requests avoided: `{report.get('requests_avoided_by_coalescing', 0)}`",
        "- write_db: `false`",
        "- enqueue_allowed: `false`",
        "- scoring_allowed: `false`",
        "",
        "| emperor | object | events | priority | source leads |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for row in packages:
        lines.append(
            f"| {row.get('emperor_name', '')} | {row.get('object_name', '')} | {row.get('missing_event_count', 0)} | "
            f"{row.get('priority', 0)} | {len(row.get('source_leads') or [])} |"
        )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Coalesce missing expected events into object-level source refinement seeds.")
    parser.add_argument("--inventory-jsonl", type=Path, required=True)
    parser.add_argument("--reconciliation-jsonl", type=Path, required=True)
    parser.add_argument("--reconciliation-report-json", type=Path)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.reconciliation_report_json is not None:
        reconciliation_report = read_json(args.reconciliation_report_json)
        if reconciliation_report.get("progress_allowed") is True:
            raise ExpectedEventSourceRefinementError("reconciliation gate already allows progress; source refinement is not the gate bypass")
    inventory_rows = read_jsonl(args.inventory_jsonl)
    reconciliation_rows = read_jsonl(args.reconciliation_jsonl)
    packages, seeds, report = build_refinement_packages(inventory_rows, reconciliation_rows)
    event_selection = [row for row in reconciliation_rows if text(row.get("decision")) == FETCH_DECISION]
    write_jsonl(args.output_root / "source_refinement_packages.jsonl", packages)
    write_jsonl(args.output_root / "object_source_cache_seeds.jsonl", seeds)
    write_jsonl(args.output_root / "event_selection.jsonl", event_selection)
    write_json(args.output_root / "report.json", report)
    (args.output_root / "report.md").write_text(render_markdown(report, packages), encoding="utf-8", newline="\n")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
