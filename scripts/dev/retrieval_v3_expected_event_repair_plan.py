from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class ExpectedEventRepairPlanError(RuntimeError):
    pass


def text(value: Any) -> str:
    return str(value or "").strip()


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def stable_code(prefix: str, value: Any) -> str:
    digest = hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()[:20].upper()
    return f"{prefix}-{digest}"


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ExpectedEventRepairPlanError(f"{path}: expected JSON object")
    return payload


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ExpectedEventRepairPlanError(f"{path}:{line_no}: expected JSON object")
        rows.append(payload)
    return rows


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(stable_json(dict(row)) + "\n" for row in rows), encoding="utf-8", newline="\n")


def source_ref(row: Mapping[str, Any]) -> str:
    return text(row.get("slice_cache_code") or row.get("source_slice_ref"))


def document_code(row: Mapping[str, Any]) -> str:
    return text(row.get("document_cache_code") or row.get("document_code"))


def build_repair_plan(
    reconciliation_rows: Sequence[Mapping[str, Any]],
    *,
    source_documents: Sequence[Mapping[str, Any]],
    mention_slices: Sequence[Mapping[str, Any]],
    person_seeds: Sequence[Mapping[str, Any]],
    person_coverage: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    reextract = [dict(row) for row in reconciliation_rows if text(row.get("decision")) == "reextract_cached_source"]
    rebuild = [dict(row) for row in reconciliation_rows if text(row.get("decision")) == "rebuild_event_group"]
    requested_refs = {text(ref) for row in reextract for ref in row.get("source_slice_refs") or [] if text(ref)}
    slices_by_ref = {source_ref(row): dict(row) for row in mention_slices if source_ref(row)}
    missing_refs = sorted(requested_refs - set(slices_by_ref))
    if missing_refs:
        raise ExpectedEventRepairPlanError(f"reextract source refs missing from cache: {', '.join(missing_refs)}")
    target_slices = [slices_by_ref[ref] for ref in sorted(requested_refs)]
    target_document_codes = {document_code(row) for row in target_slices if document_code(row)}
    target_documents = [dict(row) for row in source_documents if document_code(row) in target_document_codes]
    missing_documents = sorted(target_document_codes - {document_code(row) for row in target_documents})
    if missing_documents:
        raise ExpectedEventRepairPlanError(f"target documents missing from cache: {', '.join(missing_documents)}")
    target_names = {text(row.get("object_name")) for row in reextract if text(row.get("object_name"))}
    target_seeds = [dict(row) for row in person_seeds if text(row.get("name") or row.get("person_name")) in target_names]
    target_coverage = [dict(row) for row in person_coverage if text(row.get("person_name")) in target_names]
    events_by_ref: dict[str, list[str]] = {}
    for row in reextract:
        for ref in row.get("source_slice_refs") or []:
            if text(ref):
                events_by_ref.setdefault(text(ref), []).append(text(row.get("event_inventory_code")))
    for row in target_slices:
        row["slice_kind"] = "expected_event_repair"
        row["expected_event_repair"] = {
            "event_inventory_codes": sorted(set(events_by_ref.get(source_ref(row), []))),
            "reconciliation_decision": "reextract_cached_source",
        }
    reextract_targets = [
        {
            "repair_code": stable_code("EERP", [row.get("event_inventory_code"), row.get("source_slice_refs")]),
            "event_inventory_code": text(row.get("event_inventory_code")),
            "emperor_name": text(row.get("emperor_name")),
            "object_id": row.get("object_id"),
            "object_name": text(row.get("object_name")),
            "event_label": text(row.get("event_label")),
            "importance": text(row.get("importance")),
            "source_slice_refs": sorted({text(ref) for ref in row.get("source_slice_refs") or [] if text(ref)}),
            "existing_claim_keys": sorted({text(key) for key in row.get("claim_keys") or [] if text(key)}),
            "existing_group_keys": sorted({text(key) for key in row.get("group_keys") or [] if text(key)}),
            "missing_facets": list(row.get("missing_facets") or []),
            "review_note": text(row.get("review_note")),
            "write_db": False,
            "scoring_allowed": False,
        }
        for row in reextract
    ]
    rebuild_targets = [
        {
            "repair_code": stable_code("EEGR", [row.get("event_inventory_code"), row.get("claim_keys")]),
            "event_inventory_code": text(row.get("event_inventory_code")),
            "emperor_name": text(row.get("emperor_name")),
            "object_id": row.get("object_id"),
            "object_name": text(row.get("object_name")),
            "event_label": text(row.get("event_label")),
            "claim_keys": sorted({text(key) for key in row.get("claim_keys") or [] if text(key)}),
            "source_group_keys": sorted({text(key) for key in row.get("group_keys") or [] if text(key)}),
            "proposed_group_key": stable_code("CEG-R3R", row.get("event_inventory_code")),
            "review_note": text(row.get("review_note")),
            "apply_allowed": False,
            "write_db": False,
            "scoring_allowed": False,
        }
        for row in rebuild
    ]
    return {
        "source_documents": target_documents,
        "mention_slices": target_slices,
        "person_seeds": target_seeds,
        "person_coverage": target_coverage,
        "reextract_targets": reextract_targets,
        "rebuild_targets": rebuild_targets,
        "report": {
            "ok": True,
            "generated_by": "scripts/dev/retrieval_v3_expected_event_repair_plan.py",
            "decision_counts": dict(sorted(Counter(text(row.get("decision")) for row in reconciliation_rows).items())),
            "reextract_event_count": len(reextract_targets),
            "rebuild_event_group_count": len(rebuild_targets),
            "target_slice_count": len(target_slices),
            "target_document_count": len(target_documents),
            "target_object_count": len(target_names),
            "write_db": False,
            "agent_invocation_enabled": False,
            "scoring_allowed": False,
            "new_source_fetch_allowed": False,
            "next_action": "run_narrow_claim_plan_then_review_event_group_rebuilds",
        },
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "# Expected-event existing-source repair plan",
            "",
            f"- reextract events: `{report.get('reextract_event_count', 0)}`",
            f"- rebuild event groups: `{report.get('rebuild_event_group_count', 0)}`",
            f"- target slices: `{report.get('target_slice_count', 0)}`",
            f"- target documents: `{report.get('target_document_count', 0)}`",
            f"- target objects: `{report.get('target_object_count', 0)}`",
            "- write_db: `false`",
            "- agent_invocation_enabled: `false`",
            "- scoring_allowed: `false`",
            "- new_source_fetch_allowed: `false`",
            "",
        ]
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a narrow existing-source repair plan from expected-event reconciliation.")
    parser.add_argument("--reconciliation-jsonl", type=Path, required=True)
    parser.add_argument("--reconciliation-report-json", type=Path, required=True)
    parser.add_argument("--source-cache-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    gate = read_json(args.reconciliation_report_json)
    if gate.get("progress_allowed") is not True:
        raise ExpectedEventRepairPlanError("reconciliation gate does not allow existing-source repair")
    plan = build_repair_plan(
        read_jsonl(args.reconciliation_jsonl),
        source_documents=read_jsonl(args.source_cache_root / "source_documents.jsonl"),
        mention_slices=read_jsonl(args.source_cache_root / "mention_slices.jsonl"),
        person_seeds=read_jsonl(args.source_cache_root / "person_seeds.jsonl"),
        person_coverage=read_jsonl(args.source_cache_root / "person_coverage.jsonl"),
    )
    cache_root = args.output_root / "reextract_cache"
    write_jsonl(cache_root / "source_documents.jsonl", plan["source_documents"])
    write_jsonl(cache_root / "mention_slices.jsonl", plan["mention_slices"])
    write_jsonl(cache_root / "person_seeds.jsonl", plan["person_seeds"])
    write_jsonl(cache_root / "person_coverage.jsonl", plan["person_coverage"])
    write_jsonl(args.output_root / "reextract_targets.jsonl", plan["reextract_targets"])
    write_jsonl(args.output_root / "event_group_rebuilds.jsonl", plan["rebuild_targets"])
    write_json(args.output_root / "report.json", plan["report"])
    (args.output_root / "report.md").write_text(render_markdown(plan["report"]), encoding="utf-8", newline="\n")
    print(json.dumps(plan["report"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
