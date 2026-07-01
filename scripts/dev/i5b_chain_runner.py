from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.build.i5b_item_result_calculator import (  # noqa: E402
    DEFAULT_CLUSTER_FORMULA,
    DEFAULT_FORMULA_CODE,
    DEFAULT_ITEM_CODE,
    DEFAULT_LOG_PATH as DEFAULT_RESULT_LOG_PATH,
    calculate_item_results,
)
from scripts.dev.evidence_cluster_workbench import (  # noqa: E402
    DEFAULT_LOG_PATH as DEFAULT_CLUSTER_LOG_PATH,
    load_cluster_payload,
    upsert_clusters,
)
from scripts.dev.object_pool_importer import (  # noqa: E402
    RAW_NOTE_FORBIDDEN_TERMS,
    import_payloads,
    load_payloads,
    resolve_dsn,
)


DEFAULT_REPORT_PATH = ROOT / ".tmp" / "i5b" / "i5b_chain_report.json"


class I5BChainRunnerError(ValueError):
    pass


@dataclass(frozen=True)
class ChainInputs:
    emperors: tuple[str, ...]
    object_payloads: tuple[Any, ...]
    cluster_item_code: str | None
    clusters: tuple[Any, ...]


def json_default(value: Any) -> str:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    return str(value)


def rows_as_dicts(cur: Any) -> list[dict[str, Any]]:
    columns = [desc.name for desc in cur.description]
    rows: list[dict[str, Any]] = []
    for raw in cur.fetchall():
        row: dict[str, Any] = {}
        for column, value in zip(columns, raw):
            row[column] = str(value) if isinstance(value, Decimal) else value
        rows.append(row)
    return rows


def ordered_unique(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)


def load_chain_inputs(
    *,
    object_payload_path: Path | None,
    cluster_payload_path: Path | None,
    emperors: tuple[str, ...],
) -> ChainInputs:
    object_payloads = load_payloads(object_payload_path) if object_payload_path else ()
    cluster_item_code: str | None = None
    clusters: tuple[Any, ...] = ()
    if cluster_payload_path:
        cluster_item_code, clusters = load_cluster_payload(cluster_payload_path)

    derived = list(emperors)
    if not derived:
        derived.extend(payload.emperor.name for payload in object_payloads)
        derived.extend(cluster.emperor for cluster in clusters)
    names = ordered_unique(derived)
    if not names:
        raise I5BChainRunnerError("at least one emperor is required")
    return ChainInputs(names, object_payloads, cluster_item_code, clusters)


def _material_counts_from_payload(cluster_payload_path: Path | None) -> dict[tuple[str, str], int]:
    if cluster_payload_path is None:
        return {}
    raw = json.loads(cluster_payload_path.read_text(encoding="utf-8"))
    return {
        (str(cluster["emperor"]), str(cluster["rule_code"])): len(cluster.get("material_ids", []))
        for cluster in raw.get("clusters", [])
    }


def validate_chain(
    *,
    dsn: str,
    emperors: tuple[str, ...],
    item_code: str = DEFAULT_ITEM_CODE,
    result_formula: str = DEFAULT_FORMULA_CODE,
    cluster_formula: str = DEFAULT_CLUSTER_FORMULA,
    cluster_payload_path: Path | None = None,
) -> dict[str, Any]:
    names = list(emperors)
    material_counts = _material_counts_from_payload(cluster_payload_path)
    with psycopg.connect(dsn) as conn:
        results = rows_as_dicts(
            conn.execute(
                """
                select r.emp_name as emperor,
                       r.item_code,
                       r.formula_code,
                       r.score,
                       r.score_rate,
                       r.tier,
                       r.tier_band,
                       r.updated_at
                  from v_emp_item_results_by_id r
                 where r.emp_name = any(%s)
                   and r.item_code = %s
                   and r.formula_code = %s
                 order by array_position(%s::text[], r.emp_name)
                """,
                (names, item_code, result_formula, names),
            )
        )
        chain_counts = rows_as_dicts(
            conn.execute(
                """
                select e.name as emperor,
                       count(distinct sd.id) as src_docs,
                       count(distinct eo.id) as emp_objs,
                       count(os.id) as obj_srcs,
                       count(distinct oa.id) as obj_attrs
                  from emps e
                  left join emp_objs eo on eo.emp_id = e.id
                  left join obj_srcs os on os.emp_obj_id = eo.id
                  left join src_docs sd on sd.id = os.doc_id
                  left join obj_attrs oa on oa.obj_id = eo.obj_id
                 where e.name = any(%s)
                 group by e.name
                 order by array_position(%s::text[], e.name)
                """,
                (names, names),
            )
        )
        cluster_rows = rows_as_dicts(
            conn.execute(
                """
                select e.name as emperor,
                       r.rule_code,
                       c.positive_signal,
                       c.negative_signal,
                       c.cluster_direction
                  from evd_clusters c
                  join emps e on e.id = c.emp_id
                  join eval_items i on i.id = c.item_id
                  join eval_rules r on r.id = c.rule_id
                 where e.name = any(%s)
                   and i.item_code = %s
                   and c.formula_code = %s
                 order by array_position(%s::text[], e.name), r.rule_code
                """,
                (names, item_code, cluster_formula, names),
            )
        )
        unsourced = rows_as_dicts(
            conn.execute(
                """
                select e.name as emperor,
                       ro.name as raw_object
                  from emps e
                  join emp_objs eo on eo.emp_id = e.id
                  join raw_objs ro on ro.id = eo.obj_id
                  left join obj_srcs os on os.emp_obj_id = eo.id
                 where e.name = any(%s)
                 group by e.name, ro.name, eo.id
                having count(os.id) = 0
                 order by e.name, ro.name
                """,
                (names,),
            )
        )
        attr_doc_unlinked = rows_as_dicts(
            conn.execute(
                """
                select e.name as emperor,
                       ro.name as raw_object,
                       oa.attr_code,
                       oa.doc_id
                  from emps e
                  join emp_objs eo on eo.emp_id = e.id
                  join raw_objs ro on ro.id = eo.obj_id
                  join obj_attrs oa on oa.obj_id = eo.obj_id
                 where e.name = any(%s)
                   and not exists (
                       select 1
                         from obj_srcs os
                        where os.emp_obj_id = eo.id
                          and os.doc_id = oa.doc_id
                   )
                 order by e.name, ro.name, oa.attr_code
                """,
                (names,),
            )
        )
        raw_notes = rows_as_dicts(
            conn.execute(
                """
                select distinct e.name as emperor,
                       ro.name as raw_object,
                       ro.note
                  from emps e
                  join emp_objs eo on eo.emp_id = e.id
                  join raw_objs ro on ro.id = eo.obj_id
                 where e.name = any(%s)
                 order by e.name, ro.name
                """,
                (names,),
            )
        )

    raw_note_violations = []
    for row in raw_notes:
        terms = [term for term in RAW_NOTE_FORBIDDEN_TERMS if term and term in str(row["note"])]
        if terms:
            raw_note_violations.append(
                {
                    "emperor": row["emperor"],
                    "raw_object": row["raw_object"],
                    "terms": terms,
                }
            )

    cluster_count_by_emperor = Counter(str(row["emperor"]) for row in cluster_rows)
    clusters_by_emperor: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in cluster_rows:
        emperor = str(row.pop("emperor"))
        row["material_count"] = material_counts.get((emperor, str(row["rule_code"])), 0)
        clusters_by_emperor[emperor].append(row)

    result_names = {str(row["emperor"]) for row in results}
    missing_results = [name for name in names if name not in result_names]
    cluster_payload_keys = set(material_counts)
    cluster_db_keys = {(emperor, str(row["rule_code"])) for emperor, rows in clusters_by_emperor.items() for row in rows}
    missing_clusters_from_payload = [
        {"emperor": emperor, "rule_code": rule}
        for emperor, rule in sorted(cluster_payload_keys - cluster_db_keys)
    ]

    issue_counts = {
        "missing_results": len(missing_results),
        "missing_clusters_from_payload": len(missing_clusters_from_payload),
        "unsourced": len(unsourced),
        "attr_doc_unlinked": len(attr_doc_unlinked),
        "raw_note_violations": len(raw_note_violations),
    }
    return {
        "ok": all(count == 0 for count in issue_counts.values()),
        "item_code": item_code,
        "result_formula": result_formula,
        "cluster_formula": cluster_formula,
        "results": results,
        "chain_counts": chain_counts,
        "clusters": dict(clusters_by_emperor),
        "cluster_count": len(cluster_rows),
        "cluster_count_by_emperor": dict(cluster_count_by_emperor),
        "issues": {
            "counts": issue_counts,
            "missing_results": missing_results,
            "missing_clusters_from_payload": missing_clusters_from_payload,
            "unsourced": unsourced,
            "attr_doc_unlinked": attr_doc_unlinked,
            "raw_note_violations": raw_note_violations,
        },
    }


def run_chain(
    *,
    dsn: str,
    object_payload_path: Path | None,
    cluster_payload_path: Path | None,
    emperors: tuple[str, ...],
    item_code: str,
    cluster_formula: str,
    result_formula: str,
    cluster_log_path: Path,
    result_log_path: Path,
    dry_run: bool,
    skip_object_import: bool,
    skip_cluster_upsert: bool,
    skip_results: bool,
    skip_validation: bool,
) -> dict[str, Any]:
    inputs = load_chain_inputs(
        object_payload_path=object_payload_path,
        cluster_payload_path=cluster_payload_path,
        emperors=emperors,
    )
    stages: list[dict[str, Any]] = []

    if object_payload_path and not skip_object_import:
        dry_report = import_payloads(inputs.object_payloads, dsn, dry_run=True)
        stages.append({"stage": "object_import_dry_run", "report": dry_report})
        if not dry_run:
            stages.append({"stage": "object_import", "report": import_payloads(inputs.object_payloads, dsn, dry_run=False)})

    if cluster_payload_path and not skip_cluster_upsert:
        payload_item_code = inputs.cluster_item_code or item_code
        if payload_item_code != item_code:
            raise I5BChainRunnerError(f"cluster payload item_code {payload_item_code} != requested {item_code}")
        dry_report = upsert_clusters(
            dsn=dsn,
            item_code=item_code,
            clusters=inputs.clusters,
            dry_run=True,
            log_path=cluster_log_path,
        )
        stages.append({"stage": "cluster_upsert_dry_run", "report": dry_report})
        if not dry_run:
            stages.append(
                {
                    "stage": "cluster_upsert",
                    "report": upsert_clusters(
                        dsn=dsn,
                        item_code=item_code,
                        clusters=inputs.clusters,
                        dry_run=False,
                        log_path=cluster_log_path,
                    ),
                }
            )

    if not skip_results:
        dry_report = calculate_item_results(
            dsn=dsn,
            emperors=inputs.emperors,
            item_code=item_code,
            cluster_formula=cluster_formula,
            formula_code=result_formula,
            dry_run=True,
            log_path=result_log_path,
        )
        stages.append({"stage": "item_results_dry_run", "report": dry_report})
        if not dry_run:
            stages.append(
                {
                    "stage": "item_results",
                    "report": calculate_item_results(
                        dsn=dsn,
                        emperors=inputs.emperors,
                        item_code=item_code,
                        cluster_formula=cluster_formula,
                        formula_code=result_formula,
                        dry_run=False,
                        log_path=result_log_path,
                    ),
                }
            )

    validation = None
    if not dry_run and not skip_validation:
        validation = validate_chain(
            dsn=dsn,
            emperors=inputs.emperors,
            item_code=item_code,
            result_formula=result_formula,
            cluster_formula=cluster_formula,
            cluster_payload_path=cluster_payload_path,
        )

    return {
        "dry_run": dry_run,
        "emperors": list(inputs.emperors),
        "object_payload": str(object_payload_path) if object_payload_path else None,
        "cluster_payload": str(cluster_payload_path) if cluster_payload_path else None,
        "stages": stages,
        "validation": validation,
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=json_default) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the sourced-object -> cluster -> I5B result chain.")
    parser.add_argument("--dsn-env", default="EMPEROR_EVAL_PG_DSN", help="Environment variable name for PostgreSQL DSN.")
    parser.add_argument("--object-payload", type=Path, default=None, help="UTF-8 object payload JSON.")
    parser.add_argument("--cluster-payload", type=Path, default=None, help="UTF-8 evidence cluster payload JSON.")
    parser.add_argument("--emperor", action="append", default=[], help="Emperor name; repeat to override payload-derived names.")
    parser.add_argument("--item-code", default=DEFAULT_ITEM_CODE, help="Evaluation item code.")
    parser.add_argument("--cluster-formula", default=DEFAULT_CLUSTER_FORMULA, help="Required evd_clusters formula_code.")
    parser.add_argument("--result-formula", default=DEFAULT_FORMULA_CODE, help="emp_item_results formula_code to write.")
    parser.add_argument("--cluster-log", type=Path, default=DEFAULT_CLUSTER_LOG_PATH, help="Evidence cluster JSONL log path.")
    parser.add_argument("--result-log", type=Path, default=DEFAULT_RESULT_LOG_PATH, help="Item result JSONL log path.")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH, help="UTF-8 JSON run report path.")
    parser.add_argument("--dry-run", action="store_true", help="Run all dry-run stages and skip database writes/log appends.")
    parser.add_argument("--skip-object-import", action="store_true", help="Skip object payload import stages.")
    parser.add_argument("--skip-cluster-upsert", action="store_true", help="Skip evidence cluster upsert stages.")
    parser.add_argument("--skip-results", action="store_true", help="Skip emp_item_results calculation stages.")
    parser.add_argument("--skip-validation", action="store_true", help="Skip post-write database validation summary.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    report = run_chain(
        dsn=resolve_dsn(args.dsn_env),
        object_payload_path=args.object_payload,
        cluster_payload_path=args.cluster_payload,
        emperors=tuple(args.emperor),
        item_code=args.item_code,
        cluster_formula=args.cluster_formula,
        result_formula=args.result_formula,
        cluster_log_path=args.cluster_log,
        result_log_path=args.result_log,
        dry_run=args.dry_run,
        skip_object_import=args.skip_object_import,
        skip_cluster_upsert=args.skip_cluster_upsert,
        skip_results=args.skip_results,
        skip_validation=args.skip_validation,
    )
    write_report(args.report, report)
    print(json.dumps({"report": str(args.report), "ok": None if report["validation"] is None else report["validation"]["ok"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
