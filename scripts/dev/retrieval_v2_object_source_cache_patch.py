from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v2_object_source_cache_audit import read_jsonl
from scripts.dev.retrieval_v2_object_source_cache_seed import seed_aliases
from scripts.dev.retrieval_v2_contracts import unique_strings


class ObjectSourceCachePatchError(RuntimeError):
    pass


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


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def stable_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def unique_hint_rows(rows: Sequence[Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        item = {str(key): value for key, value in row.items() if value not in (None, "", [])}
        if not item:
            continue
        key = stable_key(item)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def patch_has_payload(patch: Mapping[str, Any]) -> bool:
    return any(
        patch.get(key)
        for key in (
            "new_aliases",
            "add_aliases",
            "replace_source_document_hints",
            "add_source_document_hints",
            "source_document_hints",
            "add_source_hints",
            "source_hints",
        )
    )


def iter_patch_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(row) for row in payload if isinstance(row, Mapping)]
    if not isinstance(payload, Mapping):
        return []
    if isinstance(payload.get("patches"), list):
        return [dict(row) for row in payload["patches"] if isinstance(row, Mapping)]
    rows: list[dict[str, Any]] = []
    for item in payload.get("workitems") or []:
        if not isinstance(item, Mapping):
            continue
        suggested = item.get("suggested_patch")
        if not isinstance(suggested, Mapping):
            continue
        patch = dict(suggested)
        patch.setdefault("person_name", text_from(item, "person_name"))
        patch.setdefault("person_cache_code", text_from(item, "person_cache_code"))
        rows.append(patch)
    return rows


def load_patch_rows(patch_json: Path) -> list[dict[str, Any]]:
    return iter_patch_rows(json.loads(patch_json.read_text(encoding="utf-8")))


def apply_patch_to_seed(seed: Mapping[str, Any], patches: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], dict[str, int]]:
    row = dict(seed)
    counts = {
        "alias_added_count": 0,
        "source_hint_added_count": 0,
        "source_document_hint_added_count": 0,
        "source_document_hint_replaced_count": 0,
    }
    for patch in patches:
        aliases_before = list(row.get("aliases") or [])
        alias_additions = unique_strings([*(patch.get("new_aliases") or []), *(patch.get("add_aliases") or [])])
        if alias_additions:
            row["aliases"] = unique_strings([*aliases_before, *alias_additions])
            counts["alias_added_count"] += max(0, len(row["aliases"]) - len(aliases_before))

        source_hints_before = list(row.get("source_hints") or [])
        source_hint_additions = unique_strings([*(patch.get("add_source_hints") or []), *(patch.get("source_hints") or [])])
        if source_hint_additions:
            row["source_hints"] = unique_strings([*source_hints_before, *source_hint_additions])
            counts["source_hint_added_count"] += max(0, len(row["source_hints"]) - len(source_hints_before))

        replace_hints = unique_hint_rows(patch.get("replace_source_document_hints") or [])
        if replace_hints:
            row["source_document_hints"] = replace_hints
            counts["source_document_hint_replaced_count"] += len(replace_hints)
        else:
            current_hints = unique_hint_rows(row.get("source_document_hints") or [])
            add_hints = unique_hint_rows([*(patch.get("add_source_document_hints") or []), *(patch.get("source_document_hints") or [])])
            if add_hints:
                merged_hints = unique_hint_rows([*current_hints, *add_hints])
                row["source_document_hints"] = merged_hints
                counts["source_document_hint_added_count"] += max(0, len(merged_hints) - len(current_hints))

    row["aliases"] = seed_aliases(row, include_script_variants=False)
    row["expanded_aliases"] = seed_aliases(row)
    row["seed_sources"] = unique_strings([*(row.get("seed_sources") or []), "object_source_cache_patch"])
    return row, counts


def apply_seed_patches(
    seeds: Sequence[Mapping[str, Any]],
    patch_rows: Sequence[Mapping[str, Any]],
    *,
    allow_missing_person: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    patches_by_name: dict[str, list[dict[str, Any]]] = {}
    invalid_patch_rows: list[dict[str, Any]] = []
    noop_patch_rows: list[dict[str, Any]] = []
    for index, patch in enumerate(patch_rows, start=1):
        name = text_from(patch, "person_name", "name")
        if not name:
            invalid_patch_rows.append({"row_number": index, "issue_code": "missing_person_name"})
            continue
        if not patch_has_payload(patch):
            noop_patch_rows.append({"row_number": index, "person_name": name, "issue_code": "empty_patch_payload"})
            continue
        patches_by_name.setdefault(name, []).append(dict(patch))

    seen_names = {text_from(seed, "name", "person_name") for seed in seeds}
    missing_people = [name for name in patches_by_name if name not in seen_names]
    if invalid_patch_rows:
        raise ObjectSourceCachePatchError(f"invalid patch rows: {len(invalid_patch_rows)}")
    if missing_people and not allow_missing_person:
        raise ObjectSourceCachePatchError(f"patch people missing from seed: {', '.join(missing_people)}")

    totals = {
        "input_seeds": len(seeds),
        "output_seeds": 0,
        "patch_rows": len(patch_rows),
        "payload_patch_rows": sum(len(rows) for rows in patches_by_name.values()),
        "noop_patch_rows": len(noop_patch_rows),
        "applied_people": 0,
        "missing_people": len(missing_people),
        "alias_added_count": 0,
        "source_hint_added_count": 0,
        "source_document_hint_added_count": 0,
        "source_document_hint_replaced_count": 0,
    }
    output: list[dict[str, Any]] = []
    applied_people: list[str] = []
    for seed in seeds:
        name = text_from(seed, "name", "person_name")
        patches = patches_by_name.get(name)
        if not patches:
            output.append(dict(seed))
            continue
        updated, counts = apply_patch_to_seed(seed, patches)
        output.append(updated)
        applied_people.append(name)
        for key, value in counts.items():
            totals[key] += value

    totals["output_seeds"] = len(output)
    totals["applied_people"] = len(applied_people)
    report = {
        "generated_by": "scripts/dev/retrieval_v2_object_source_cache_patch.py",
        "totals": totals,
        "applied_people": applied_people,
        "missing_people": missing_people,
        "noop_patch_rows": noop_patch_rows,
        "invalid_patch_rows": invalid_patch_rows,
    }
    return output, report


def render_patch_report_markdown(report: Mapping[str, Any]) -> str:
    totals = report.get("totals") if isinstance(report.get("totals"), Mapping) else {}
    lines = [
        "# retrieval_v2 object source cache seed patch report",
        "",
        "## Totals",
        "",
    ]
    for key, value in totals.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Applied People", ""])
    for name in report.get("applied_people") or []:
        lines.append(f"- {name}")
    if report.get("missing_people"):
        lines.extend(["", "## Missing People", ""])
        for name in report.get("missing_people") or []:
            lines.append(f"- {name}")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Apply reviewed object source cache worklist patches to a seed JSONL file.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    apply_cmd = subparsers.add_parser("apply", help="Apply alias/source-hint patches to a seed JSONL file.")
    apply_cmd.add_argument("--seed-jsonl", type=Path, required=True)
    apply_cmd.add_argument("--patch-json", type=Path, required=True)
    apply_cmd.add_argument("--output-jsonl", type=Path, required=True)
    apply_cmd.add_argument("--report-json", type=Path, required=True)
    apply_cmd.add_argument("--report-md", type=Path, required=True)
    apply_cmd.add_argument("--allow-missing-person", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "apply":
        try:
            output_rows, report = apply_seed_patches(
                read_jsonl(args.seed_jsonl),
                load_patch_rows(args.patch_json),
                allow_missing_person=args.allow_missing_person,
            )
        except ObjectSourceCachePatchError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        write_jsonl(args.output_jsonl, output_rows)
        write_json(args.report_json, report)
        args.report_md.parent.mkdir(parents=True, exist_ok=True)
        args.report_md.write_text(render_patch_report_markdown(report), encoding="utf-8")
        print(
            json.dumps(
                {
                    "ok": True,
                    "output_jsonl": str(args.output_jsonl),
                    "report_json": str(args.report_json),
                    "report_md": str(args.report_md),
                    "totals": report["totals"],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
