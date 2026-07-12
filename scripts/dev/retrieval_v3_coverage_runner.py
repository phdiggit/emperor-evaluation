from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v3_bootstrap import import_psycopg, load_env_file, resolve_dsn
from scripts.dev.retrieval_v3_pg_schema import DEFAULT_PG_SCHEMA, DEFAULT_V3_DSN_ENV, schema_cursor
from scripts.dev.retrieval_v3_coverage_controller import build_report, fetch_rows, render_markdown
from scripts.dev.retrieval_v3_coverage_convergence import (
    apply_convergence,
    build_consumer_handoffs,
    build_convergence_delta,
    build_repair_ledger,
)


def text(value: Any) -> str:
    return str(value or "").strip()


def read_jsonl(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, Mapping):
            raise ValueError(f"{path}:{line_no}: expected object")
        rows.append(dict(value))
    return rows


def fetch_coverage_contract(
    *, dsn: str, schema_name: str, emperors: Sequence[str] = (), items: Sequence[str] = (), rules: Sequence[str] = ()
) -> list[dict[str, Any]]:
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            cur.execute(
                """
                select rt.target_code, rt.emperor_name, rt.item_code, rc.contract_code,
                       rcr.rule_code, rcr.rule_label, rcr.rule_order, rcr.is_core_for_retrieval,
                       rcr.requirement_payload, rcr.source_fingerprint
                  from retrieval_v3.retrieval_targets rt
                  join retrieval_v3.rule_contracts rc on rc.id = rt.contract_id and rc.status = 'active'
                  join retrieval_v3.rule_contract_rules rcr on rcr.contract_id = rc.id
                 where rt.target_status = 'active'
                   and (coalesce(array_length(%s::text[], 1), 0) = 0 or rt.emperor_name = any(%s::text[]))
                   and (coalesce(array_length(%s::text[], 1), 0) = 0 or rt.item_code = any(%s::text[]))
                   and (coalesce(array_length(%s::text[], 1), 0) = 0 or rcr.rule_code = any(%s::text[]))
                 order by rt.item_code, rcr.rule_order, rcr.rule_code, rt.emperor_name
                """,
                (list(emperors), list(emperors), list(items), list(items), list(rules), list(rules)),
            )
            return [dict(row) for row in cur.fetchall()]


def group_contract(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (text(row.get("item_code")), text(row.get("rule_code")))
        scope = grouped.setdefault(key, {
            "item_code": key[0], "rule_code": key[1], "rule_label": text(row.get("rule_label")),
            "contract_codes": set(), "source_fingerprints": set(), "emperors": set(),
        })
        scope["contract_codes"].add(text(row.get("contract_code")))
        scope["source_fingerprints"].add(text(row.get("source_fingerprint")))
        scope["emperors"].add(text(row.get("emperor_name")))
    return [
        dict(scope) | {
            "contract_codes": sorted(scope["contract_codes"]),
            "source_fingerprints": sorted(scope["source_fingerprints"]),
            "emperors": sorted(scope["emperors"]),
            "emperor_count": len(scope["emperors"]),
        }
        for _, scope in sorted(grouped.items())
    ]


def scope_stem(item_code: str, rule_code: str) -> str:
    return f"{item_code}__{rule_code}"


def unique_contract_cells(rows: Sequence[Mapping[str, Any]]) -> set[tuple[str, str, str]]:
    return {(text(row.get("emperor_name")), text(row.get("item_code")), text(row.get("rule_code"))) for row in rows}


def build_contract_cell_assessments(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    objects_by_emperor: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in report.get("objects") or []:
        objects_by_emperor[text(row.get("emperor_name"))].append(row)
    cells: list[dict[str, Any]] = []
    for emperor in report.get("emperors") or []:
        objects = objects_by_emperor.get(text(emperor), [])
        mechanical = Counter(text(row.get("mechanical_coverage_status")) for row in objects)
        convergence = Counter(text(row.get("convergence_state")) for row in objects)
        cells.append({
            "emperor_name": text(emperor), "item_code": text(report.get("item_code")),
            "rule_code": text(report.get("rule_code")), "object_count": len(objects),
            "cell_status": "observed_objects" if objects else "empty_no_objects",
            "mechanical_coverage_counts": dict(sorted(mechanical.items())),
            "convergence_counts": dict(sorted(convergence.items())),
            "historically_assessed_object_count": sum(
                text(row.get("historical_event_coverage_status")) != "unassessed" for row in objects),
        })
    return cells


def build_full_report(contract_rows: Sequence[Mapping[str, Any]], scope_reports: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    convergence: Counter[str] = Counter()
    mechanical: Counter[str] = Counter()
    gap_counts: Counter[str] = Counter()
    delta_counts: Counter[str] = Counter(); handoff_counts: Counter[str] = Counter()
    cells = 0
    empty_cells = 0
    historical_assessed_cells = 0
    for report in scope_reports:
        convergence.update(report.get("convergence_counts") or {})
        mechanical.update(report.get("mechanical_coverage_counts") or {})
        gap_counts.update(report.get("gap_counts") or {})
        delta_counts.update(report.get("delta_counts") or {}); handoff_counts.update(report.get("handoff_counts") or {})
        cell_rows = report.get("contract_cell_assessments") or build_contract_cell_assessments(report)
        cells += len(cell_rows); empty_cells += sum(text(row.get("cell_status")) == "empty_no_objects" for row in cell_rows)
        historical_assessed_cells += sum(
            text(row.get("historical_event_coverage_status")) != "unassessed" for row in report.get("objects") or []
        )
    expected_cells = len(unique_contract_cells(contract_rows))
    run_complete = len(scope_reports) == len(group_contract(contract_rows))
    data_converged = run_complete and not gap_counts and set(convergence).issubset({"verified"})
    return {
        "ok": run_complete,
        "controller_status": "complete_read_only_control_plane" if run_complete else "incomplete_run",
        "data_converged": data_converged,
        "mode": "read_only_full_coverage_convergence",
        "write_job": False,
        "write_db": False,
        "contract_source": "retrieval_targets + rule_contracts + rule_contract_rules",
        "forbidden_contract_tables_used": False,
        "side_effects_authorized": False,
        "capabilities": {
            "full_contract": True, "unified_object_matrix": True, "repair_ledger": True,
            "report_only_consumer_handoff": True, "score_lineage_freshness": True,
            "full_runner": True, "convergence_delta": True,
        },
        "contract_cell_count": expected_cells,
        "contract_row_count": len(contract_rows),
        "duplicate_contract_row_count": len(contract_rows) - expected_cells,
        "covered_scope_count": len(scope_reports),
        "covered_emperor_rule_cell_count": cells,
        "empty_contract_cell_count": empty_cells,
        "historically_assessed_object_count": historical_assessed_cells,
        "mechanical_coverage_counts": dict(sorted(mechanical.items())),
        "convergence_counts": dict(sorted(convergence.items())),
        "gap_counts": dict(sorted(gap_counts.items())),
        "delta_counts": dict(sorted(delta_counts.items())),
        "handoff_counts": dict(sorted(handoff_counts.items())),
        "scopes": [{
            "item_code": report.get("item_code"), "rule_code": report.get("rule_code"),
            "emperors": report.get("emperors"), "counts": report.get("counts"),
            "convergence_counts": report.get("convergence_counts"),
            "expected_event_count": report.get("expected_event_count"),
        } for report in scope_reports],
    }


def render_full_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# retrieval_v3 全量 coverage convergence 报告", "",
        f"- contract rows: `{report.get('contract_row_count', 0)}`",
        f"- unique emperor/item/rule cells: `{report.get('contract_cell_count', 0)}`",
        f"- duplicate contract rows: `{report.get('duplicate_contract_row_count', 0)}`",
        f"- covered cells: `{report.get('covered_emperor_rule_cell_count', 0)}`",
        f"- mechanical: `{json.dumps(report.get('mechanical_coverage_counts') or {}, ensure_ascii=False, sort_keys=True)}`",
        f"- convergence: `{json.dumps(report.get('convergence_counts') or {}, ensure_ascii=False, sort_keys=True)}`",
        "- write_job/write_db: `false/false`", "", "## Scopes", "",
        "| item | rule | emperors | objects | expected events | convergence |", "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in report.get("scopes") or []:
        lines.append(
            f"| {text(row.get('item_code'))} | {text(row.get('rule_code'))} | {len(row.get('emperors') or [])} | "
            f"{(row.get('counts') or {}).get('objects', 0)} | {row.get('expected_event_count', 0)} | "
            f"{json.dumps(row.get('convergence_counts') or {}, ensure_ascii=False, sort_keys=True)} |")
    return "\n".join(lines) + "\n"


def run_contract(
    *, dsn: str, schema_name: str, contract_rows: Sequence[Mapping[str, Any]], output_root: Path,
    inputs_root: Path | None = None, previous_root: Path | None = None,
    scope_inputs: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    reports: list[dict[str, Any]] = []
    for scope in group_contract(contract_rows):
        item_code, rule_code = scope["item_code"], scope["rule_code"]
        stem = scope_stem(item_code, rule_code)
        scope_input = (scope_inputs or {}).get(stem) or {}
        claims, downstream, targets, sources = fetch_rows(
            dsn=dsn, schema_name=schema_name, item_code=item_code, rule_code=rule_code,
            emperors=scope["emperors"], source_pack_codes=scope_input.get("source_pack_codes") or [])
        expected_path = Path(text(scope_input.get("expected_events_jsonl"))) if text(scope_input.get("expected_events_jsonl")) else None
        expected = read_jsonl(expected_path or (inputs_root / f"{stem}.expected_events.jsonl" if inputs_root else None))
        reconciliation = []
        reconciliation_path = inputs_root / f"{stem}.reconciliation.json" if inputs_root else None
        if reconciliation_path and reconciliation_path.exists():
            value = json.loads(reconciliation_path.read_text(encoding="utf-8"))
            reconciliation = [dict(value)] if isinstance(value, Mapping) else []
        for report_path in scope_input.get("reconciliation_reports") or []:
            value = json.loads(Path(text(report_path)).read_text(encoding="utf-8"))
            if isinstance(value, Mapping):
                reconciliation.append(dict(value))
        report = build_report(
            claim_rows=claims, downstream_rows=downstream, target_rows=targets, source_rows=sources,
            schema_name=schema_name, item_code=item_code, rule_code=rule_code,
            emperors=scope["emperors"], expected_events=expected, reconciliation_reports=reconciliation,
        )
        previous = read_jsonl(previous_root / f"{stem}.repair_ledger.jsonl" if previous_root else None)
        ledger = build_repair_ledger(report, previous); apply_convergence(report, ledger)
        report["coverage_contract"] = scope
        report["source_pack_codes"] = list(scope_input.get("source_pack_codes") or [])
        report["contract_cell_assessments"] = build_contract_cell_assessments(report)
        delta = build_convergence_delta(ledger, previous)
        report["delta_counts"] = delta["counts"]
        (output_root / f"{stem}.delta.json").write_text(
            json.dumps(delta, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        handoff = build_consumer_handoffs(ledger)
        report["handoff_counts"] = handoff["counts"]
        (output_root / f"{stem}.handoff.json").write_text(
            json.dumps(handoff, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8", newline="\n")
        (output_root / f"{stem}.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8", newline="\n")
        (output_root / f"{stem}.md").write_text(render_markdown(report), encoding="utf-8", newline="\n")
        (output_root / f"{stem}.repair_ledger.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) + "\n" for row in ledger), encoding="utf-8", newline="\n")
        reports.append(report)
    full = build_full_report(contract_rows, reports)
    matrix_rows = [
        dict(row) | {"item_code": report.get("item_code"), "rule_code": report.get("rule_code")}
        for report in reports for row in report.get("objects") or []
    ]
    cell_rows = [row for report in reports for row in report.get("contract_cell_assessments") or []]
    full["object_matrix_row_count"] = len(matrix_rows)
    (output_root / "coverage_contract.json").write_text(
        json.dumps(list(contract_rows), ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8", newline="\n")
    (output_root / "contract_cells.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in cell_rows), encoding="utf-8", newline="\n")
    (output_root / "object_coverage_matrix.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) + "\n" for row in matrix_rows), encoding="utf-8", newline="\n")
    (output_root / "convergence_report.json").write_text(
        json.dumps(full, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (output_root / "convergence_report.md").write_text(render_full_markdown(full), encoding="utf-8", newline="\n")
    return full


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run read-only retrieval_v3 coverage controller for the active contract.")
    parser.add_argument("--env-file", type=Path); parser.add_argument("--dsn-env", default=DEFAULT_V3_DSN_ENV)
    parser.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA); parser.add_argument("--emperor", action="append", default=[])
    parser.add_argument("--item", action="append", default=[]); parser.add_argument("--rule", action="append", default=[])
    parser.add_argument("--inputs-root", type=Path); parser.add_argument("--previous-root", type=Path)
    parser.add_argument("--scope-input-manifest", type=Path)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.env_file:
        load_env_file(args.env_file)
    dsn = resolve_dsn(args.dsn_env)
    contract = fetch_coverage_contract(
        dsn=dsn, schema_name=args.pg_schema, emperors=args.emperor, items=args.item, rules=args.rule)
    if not contract:
        raise ValueError("active coverage contract is empty")
    scope_inputs: Mapping[str, Mapping[str, Any]] = {}
    if args.scope_input_manifest:
        value = json.loads(args.scope_input_manifest.read_text(encoding="utf-8"))
        scope_inputs = value.get("scopes") or {} if isinstance(value, Mapping) else {}
    report = run_contract(
        dsn=dsn, schema_name=args.pg_schema, contract_rows=contract, output_root=args.output_root,
        inputs_root=args.inputs_root, previous_root=args.previous_root, scope_inputs=scope_inputs)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
