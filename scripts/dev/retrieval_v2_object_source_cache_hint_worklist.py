from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v2_object_source_cache_audit import build_review_audit, read_jsonl


def text_from(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None:
            text = str(value).strip()
            if text:
                return text
    return ""


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def compact(value: Any, *, limit: int = 180) -> str:
    text = " ".join(str(value or "").split())
    return text[: limit - 1] + "…" if len(text) > limit else text


def load_seed_hints(seed_jsonl: Path | None) -> dict[str, dict[str, Any]]:
    if seed_jsonl is None:
        return {}
    rows = read_jsonl(seed_jsonl)
    return {text_from(row, "name", "person_name"): row for row in rows if text_from(row, "name", "person_name")}


def classify_next_action(row: Mapping[str, Any]) -> str:
    classification = text_from(row, "classification")
    risk = text_from(row, "claim_closure_risk")
    tags = set(row.get("issue_tags") or [])
    if classification == "nonempty_no_alias_hit":
        return "alias_or_title_review"
    if classification == "empty_text_candidate":
        return "source_hint_replacement_or_rescue_search"
    if "subpath_locator_collapsed" in tags or "fourku_locator_collapsed" in tags:
        return "source_hint_replacement"
    if risk == "mentions_without_biography_source":
        return "biography_source_discovery"
    return "agent_source_hint_review"


def reason_for_action(row: Mapping[str, Any]) -> str:
    action = classify_next_action(row)
    if action == "alias_or_title_review":
        return "Current source text is non-empty but none of the known aliases matched; review title/courtesy/posthumous/name variants before replacing source."
    if action == "source_hint_replacement_or_rescue_search":
        return "Some current source candidates are empty or unrelated; review whether a known biography page should replace the current hint."
    if action == "source_hint_replacement":
        return "Current source hint points through a collapsed or likely wrong source route; find the actual biography/claim page rather than widening default search."
    if action == "biography_source_discovery":
        return "Existing pages contain mentions but no biography-shaped source; discover or confirm a stronger biography source."
    return "Review source hints and aliases manually or with an agent before changing seeds."


def row_document_summary(doc: Mapping[str, Any]) -> dict[str, Any]:
    hint = doc.get("source_document_hint") if isinstance(doc.get("source_document_hint"), Mapping) else {}
    return {
        "title": text_from(doc, "wikisource_title", "source_title", "title"),
        "source_shape": text_from(doc, "source_shape"),
        "text_chars": int(doc.get("text_chars") or 0),
        "mention_slice_count": int(doc.get("mention_slice_count") or 0),
        "why_selected": compact(doc.get("why_selected")),
        "search_query": compact(doc.get("search_query")),
        "hint_locator": compact(text_from(hint, "locator")),
        "hint_title": compact(text_from(hint, "title")),
    }


def build_source_hint_worklist(
    cache_root: Path,
    *,
    seed_jsonl: Path | None = None,
    max_documents_per_person: int = 5,
) -> dict[str, Any]:
    audit = build_review_audit(cache_root, max_docs_per_person=max_documents_per_person)
    seeds_by_name = load_seed_hints(seed_jsonl)
    docs_by_person: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for doc in read_jsonl(cache_root / "source_documents.jsonl"):
        docs_by_person[text_from(doc, "person_name")].append(doc)

    workitems: list[dict[str, Any]] = []
    for row in audit.get("review_rows") or []:
        person_name = text_from(row, "person_name")
        seed = seeds_by_name.get(person_name, {})
        action = classify_next_action(row)
        workitems.append(
            {
                "person_name": person_name,
                "person_cache_code": text_from(row, "person_cache_code"),
                "claim_closure_risk": text_from(row, "claim_closure_risk"),
                "classification": text_from(row, "classification"),
                "issue_tags": row.get("issue_tags") or [],
                "recommended_action": action,
                "action_reason": reason_for_action(row),
                "current_aliases": seed.get("aliases") or [],
                "current_source_document_hints": seed.get("source_document_hints") or [],
                "documents": [row_document_summary(doc) for doc in docs_by_person.get(person_name, [])[:max_documents_per_person]],
                "suggested_patch": {
                    "action": "review_required",
                    "new_aliases": [],
                    "add_source_hints": [],
                    "replace_source_document_hints": [],
                    "add_source_document_hints": [],
                    "notes": "",
                },
            }
        )

    action_counts: dict[str, int] = {}
    for item in workitems:
        action = text_from(item, "recommended_action")
        action_counts[action] = action_counts.get(action, 0) + 1
    return {
        "generated_by": "scripts/dev/retrieval_v2_object_source_cache_hint_worklist.py",
        "cache_root": str(cache_root),
        "seed_jsonl": str(seed_jsonl) if seed_jsonl is not None else "",
        "totals": {
            "workitems": len(workitems),
            "review_rows": len(audit.get("review_rows") or []),
        },
        "action_counts": dict(sorted(action_counts.items())),
        "classification_counts": audit.get("classification_counts") or {},
        "workitems": workitems,
    }


def render_source_hint_worklist_markdown(worklist: Mapping[str, Any]) -> str:
    totals = worklist.get("totals") if isinstance(worklist.get("totals"), Mapping) else {}
    lines = [
        "# retrieval_v2 object source hint correction worklist",
        "",
        f"- cache_root: `{worklist.get('cache_root', '')}`",
        f"- seed_jsonl: `{worklist.get('seed_jsonl', '')}`",
        f"- workitems: `{totals.get('workitems', 0)}`",
        "",
        "## Actions",
        "",
    ]
    for action, count in (worklist.get("action_counts") or {}).items():
        lines.append(f"- {action}: `{count}`")
    lines.extend(["", "## Workitems", ""])
    for item in worklist.get("workitems") or []:
        lines.extend(
            [
                f"### {item.get('person_name')}",
                "",
                f"- risk: `{item.get('claim_closure_risk')}`",
                f"- class: `{item.get('classification')}`",
                f"- action: `{item.get('recommended_action')}`",
                f"- reason: {item.get('action_reason')}",
                f"- aliases: `{', '.join(item.get('current_aliases') or [])}`",
                "",
                "| title | shape | chars | slices | query | hint |",
                "| --- | --- | ---: | ---: | --- | --- |",
            ]
        )
        for doc in item.get("documents") or []:
            lines.append(
                f"| {doc.get('title')} | {doc.get('source_shape')} | {doc.get('text_chars')} | {doc.get('mention_slice_count')} | {doc.get('search_query')} | {doc.get('hint_locator')} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate source hint correction worklist from object source cache review rows.")
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--seed-jsonl", type=Path)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    parser.add_argument("--max-documents-per-person", type=int, default=5)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    worklist = build_source_hint_worklist(
        args.cache_root,
        seed_jsonl=args.seed_jsonl,
        max_documents_per_person=args.max_documents_per_person,
    )
    write_json(args.output_json, worklist)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(render_source_hint_worklist_markdown(worklist), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": True,
                "output_json": str(args.output_json),
                "output_md": str(args.output_md),
                "totals": worklist.get("totals", {}),
                "action_counts": worklist.get("action_counts", {}),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
