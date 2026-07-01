from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import psycopg


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DSN_ENV = "EMPEROR_EVAL_PG_DSN"
DEFAULT_LOG_PATH = ROOT / "logs" / "evidence_clusters" / "evidence_cluster_calc.jsonl"
ALLOWED_DIRECTIONS = {"positive", "negative", "mixed"}


class EvidenceClusterWorkbenchError(ValueError):
    pass


@dataclass(frozen=True)
class ClusterInput:
    emperor: str
    rule_code: str
    positive_signal: Decimal
    negative_signal: Decimal
    formula_code: str
    note: str
    material_ids: tuple[int, ...] = ()
    calc_note: str = ""
    calc_detail: dict[str, Any] | None = None


def load_env(path: Path = ROOT / ".env") -> dict[str, str]:
    if not path.exists():
        return {}
    env: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def resolve_dsn(env_name: str) -> str:
    if os.environ.get(env_name):
        return str(os.environ[env_name])
    env = load_env()
    if env_name not in env:
        raise EvidenceClusterWorkbenchError(f"missing PostgreSQL DSN env var {env_name}")
    return env[env_name]


def _require_text(row: dict[str, Any], key: str, path: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise EvidenceClusterWorkbenchError(f"{path}.{key}: expected non-empty string")
    return value.strip()


def _decimal(row: dict[str, Any], key: str, path: str) -> Decimal:
    value = row.get(key)
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise EvidenceClusterWorkbenchError(f"{path}.{key}: expected decimal") from exc
    if parsed < 0:
        raise EvidenceClusterWorkbenchError(f"{path}.{key}: expected non-negative decimal")
    return parsed


def _optional_int_tuple(row: dict[str, Any], key: str, path: str) -> tuple[int, ...]:
    value = row.get(key, [])
    if value is None:
        return ()
    if not isinstance(value, list):
        raise EvidenceClusterWorkbenchError(f"{path}.{key}: expected list")
    ids: list[int] = []
    for index, item in enumerate(value):
        if not isinstance(item, int):
            raise EvidenceClusterWorkbenchError(f"{path}.{key}[{index}]: expected integer")
        ids.append(item)
    return tuple(ids)


def direction_from_signals(positive_signal: Decimal, negative_signal: Decimal) -> str:
    net = positive_signal - negative_signal
    if net > 0:
        return "positive"
    if net < 0:
        return "negative"
    return "mixed"


def parse_cluster_payload(raw: dict[str, Any]) -> tuple[str, tuple[ClusterInput, ...]]:
    item_code = _require_text(raw, "item_code", "payload")
    default_formula_code = _require_text(raw, "formula_code", "payload")
    clusters_value = raw.get("clusters")
    if not isinstance(clusters_value, list) or not clusters_value:
        raise EvidenceClusterWorkbenchError("payload.clusters: expected non-empty list")

    clusters: list[ClusterInput] = []
    for index, item in enumerate(clusters_value):
        path = f"payload.clusters[{index}]"
        if not isinstance(item, dict):
            raise EvidenceClusterWorkbenchError(f"{path}: expected object")
        formula_code = item.get("formula_code")
        if formula_code is None:
            formula_code = default_formula_code
        if not isinstance(formula_code, str) or not formula_code.strip():
            raise EvidenceClusterWorkbenchError(f"{path}.formula_code: expected non-empty string")
        calc_note = item.get("calc_note", "")
        if calc_note is None:
            calc_note = ""
        if not isinstance(calc_note, str):
            raise EvidenceClusterWorkbenchError(f"{path}.calc_note: expected string")
        calc_detail = item.get("calc_detail")
        if calc_detail is not None and not isinstance(calc_detail, dict):
            raise EvidenceClusterWorkbenchError(f"{path}.calc_detail: expected object")
        clusters.append(
            ClusterInput(
                emperor=_require_text(item, "emperor", path),
                rule_code=_require_text(item, "rule_code", path),
                positive_signal=_decimal(item, "positive_signal", path),
                negative_signal=_decimal(item, "negative_signal", path),
                formula_code=formula_code.strip(),
                note=_require_text(item, "note", path),
                material_ids=_optional_int_tuple(item, "material_ids", path),
                calc_note=calc_note.strip(),
                calc_detail=calc_detail,
            )
        )
    return item_code, tuple(clusters)


def load_cluster_payload(path: Path) -> tuple[str, tuple[ClusterInput, ...]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise EvidenceClusterWorkbenchError("payload: expected object")
    return parse_cluster_payload(value)


def _cluster_lookup(cur: psycopg.Cursor, *, emperor: str, item_code: str, rule_code: str) -> tuple[int, int, int]:
    cur.execute("select id from emps where name = %s", (emperor,))
    emp_row = cur.fetchone()
    if emp_row is None:
        raise EvidenceClusterWorkbenchError(f"emps missing emperor: {emperor}")
    emp_id = int(emp_row[0])

    cur.execute("select id from eval_items where item_code = %s", (item_code,))
    item_row = cur.fetchone()
    if item_row is None:
        raise EvidenceClusterWorkbenchError(f"eval_items missing item_code: {item_code}")
    item_id = int(item_row[0])

    cur.execute("select id from eval_rules where item_id = %s and rule_code = %s", (item_id, rule_code))
    rule_row = cur.fetchone()
    if rule_row is None:
        raise EvidenceClusterWorkbenchError(f"eval_rules missing rule_code: {rule_code}")
    rule_id = int(rule_row[0])
    return emp_id, item_id, rule_id


def _expected_material_id_sets(
    cur: psycopg.Cursor,
    *,
    emp_id: int,
    item_id: int,
    rule_id: int,
) -> tuple[set[int], set[int]]:
    cur.execute(
        """
        select osrc.id, osrc.direction
        from obj_srcs osrc
        join emp_objs eo on eo.id = osrc.emp_obj_id
        where eo.emp_id = %s
          and osrc.item_id = %s
          and osrc.rule_id = %s
        order by osrc.id
        """,
        (emp_id, item_id, rule_id),
    )
    rows = cur.fetchall()
    all_ids = {int(row[0]) for row in rows}
    scoring_ids = {int(row[0]) for row in rows if len(row) < 2 or row[1] != "neutral"}
    return all_ids, scoring_ids


def _calc_detail_material_ids(cluster: ClusterInput) -> tuple[int, ...] | None:
    if cluster.calc_detail is None:
        return None
    materials = cluster.calc_detail.get("materials")
    if materials is None:
        return None
    if not isinstance(materials, list):
        raise EvidenceClusterWorkbenchError(f"{cluster.emperor}/{cluster.rule_code}: calc_detail.materials expected list")
    ids: list[int] = []
    for index, material in enumerate(materials):
        if not isinstance(material, dict):
            raise EvidenceClusterWorkbenchError(
                f"{cluster.emperor}/{cluster.rule_code}: calc_detail.materials[{index}] expected object"
            )
        value = material.get("obj_src_id")
        if value is None:
            continue
        if not isinstance(value, int):
            raise EvidenceClusterWorkbenchError(
                f"{cluster.emperor}/{cluster.rule_code}: calc_detail.materials[{index}].obj_src_id expected integer"
            )
        ids.append(value)
    return tuple(ids)


def _int_tuple_from_detail(detail: dict[str, Any] | None, key: str) -> tuple[int, ...]:
    if not isinstance(detail, dict):
        return ()
    value = detail.get(key)
    if not isinstance(value, list):
        return ()
    ids: list[int] = []
    for item in value:
        if isinstance(item, int):
            ids.append(item)
    return tuple(ids)


def _cluster_detail_arrays(cluster: ClusterInput) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    detail = cluster.calc_detail if isinstance(cluster.calc_detail, dict) else None
    covered = _int_tuple_from_detail(detail, "covered_material_ids") or cluster.material_ids
    scored = _int_tuple_from_detail(detail, "scored_material_ids") or (_calc_detail_material_ids(cluster) or ())
    supporting = _int_tuple_from_detail(detail, "supporting_material_ids")
    if not supporting:
        supporting = tuple(material_id for material_id in covered if material_id not in set(scored))
    return covered, scored, supporting


def _jsonb(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _upsert_cluster_calc_detail(
    cur: psycopg.Cursor,
    *,
    cluster_id: int,
    item_code: str,
    cluster: ClusterInput,
) -> None:
    covered_ids, scored_ids, supporting_ids = _cluster_detail_arrays(cluster)
    calc_detail = cluster.calc_detail or {}
    cur.execute(
        """
        insert into evd_cluster_calc_details (
            cluster_id, item_code, formula_code, calc_note,
            material_ids, covered_material_ids, scored_material_ids,
            supporting_material_ids, calc_detail
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        on conflict (cluster_id) do update set
            item_code = excluded.item_code,
            formula_code = excluded.formula_code,
            calc_note = excluded.calc_note,
            material_ids = excluded.material_ids,
            covered_material_ids = excluded.covered_material_ids,
            scored_material_ids = excluded.scored_material_ids,
            supporting_material_ids = excluded.supporting_material_ids,
            calc_detail = excluded.calc_detail,
            updated_at = now()
        """,
        (
            cluster_id,
            item_code,
            cluster.formula_code,
            cluster.calc_note,
            list(cluster.material_ids),
            list(covered_ids),
            list(scored_ids),
            list(supporting_ids),
            _jsonb(calc_detail),
        ),
    )


def _raise_material_coverage_error(
    *,
    cluster: ClusterInput,
    field_name: str,
    missing: list[int],
    extra: list[int],
) -> None:
    parts = []
    if missing:
        parts.append(f"missing obj_srcs={missing}")
    if extra:
        parts.append(f"extra obj_srcs={extra}")
    detail = "; ".join(parts)
    raise EvidenceClusterWorkbenchError(
        f"{cluster.emperor}/{cluster.rule_code}: {field_name} does not cover DB obj_srcs; {detail}"
    )


def _validate_material_coverage(
    cur: psycopg.Cursor,
    *,
    emp_id: int,
    item_id: int,
    rule_id: int,
    cluster: ClusterInput,
) -> None:
    expected, scoring_expected = _expected_material_id_sets(cur, emp_id=emp_id, item_id=item_id, rule_id=rule_id)
    material_ids = set(cluster.material_ids)
    missing = sorted(expected - material_ids)
    extra = sorted(material_ids - expected)
    if missing or extra:
        _raise_material_coverage_error(
            cluster=cluster,
            field_name="material_ids",
            missing=missing,
            extra=extra,
        )

    if cluster.rule_code == "team_building":
        return

    detail_ids = _calc_detail_material_ids(cluster)
    if detail_ids is None:
        return
    detail_set = set(detail_ids)
    detail_missing = sorted(scoring_expected - detail_set)
    detail_extra = sorted(detail_set - scoring_expected)
    if detail_missing or detail_extra:
        _raise_material_coverage_error(
            cluster=cluster,
            field_name="calc_detail.materials",
            missing=detail_missing,
            extra=detail_extra,
        )


def upsert_clusters(
    *,
    dsn: str,
    item_code: str,
    clusters: tuple[ClusterInput, ...],
    dry_run: bool = False,
    log_path: Path | None = None,
    require_full_material_coverage: bool = True,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            for cluster in clusters:
                emp_id, item_id, rule_id = _cluster_lookup(
                    cur,
                    emperor=cluster.emperor,
                    item_code=item_code,
                    rule_code=cluster.rule_code,
                )
                if require_full_material_coverage:
                    _validate_material_coverage(
                        cur,
                        emp_id=emp_id,
                        item_id=item_id,
                        rule_id=rule_id,
                        cluster=cluster,
                    )
                direction = direction_from_signals(cluster.positive_signal, cluster.negative_signal)
                cur.execute(
                    """
                    insert into evd_clusters (
                        emp_id, item_id, rule_id, cluster_direction,
                        positive_signal, negative_signal, formula_code, note
                    )
                    values (%s, %s, %s, %s, %s, %s, %s, %s)
                    on conflict (emp_id, item_id, rule_id) do update set
                        cluster_direction = excluded.cluster_direction,
                        positive_signal = excluded.positive_signal,
                        negative_signal = excluded.negative_signal,
                        formula_code = excluded.formula_code,
                        note = excluded.note,
                        updated_at = now()
                    returning id, net_signal, signal_intensity
                    """,
                    (
                        emp_id,
                        item_id,
                        rule_id,
                        direction,
                        cluster.positive_signal,
                        cluster.negative_signal,
                        cluster.formula_code,
                        cluster.note,
                    ),
                )
                cluster_id, net_signal, signal_intensity = cur.fetchone()
                _upsert_cluster_calc_detail(
                    cur,
                    cluster_id=int(cluster_id),
                    item_code=item_code,
                    cluster=cluster,
                )
                rows.append(
                    {
                        "id": int(cluster_id),
                        "emperor": cluster.emperor,
                        "rule_code": cluster.rule_code,
                        "cluster_direction": direction,
                        "positive_signal": str(cluster.positive_signal),
                        "negative_signal": str(cluster.negative_signal),
                        "net_signal": str(net_signal),
                        "signal_intensity": str(signal_intensity),
                        "formula_code": cluster.formula_code,
                        "note": cluster.note,
                        "material_ids": list(cluster.material_ids),
                        "calc_note": cluster.calc_note,
                        "calc_detail": cluster.calc_detail,
                    }
                )

        if dry_run:
            conn.rollback()
        else:
            conn.commit()

    return {"dry_run": dry_run, "item_code": item_code, "clusters": rows}


def append_calc_log(path: Path, rows: list[dict[str, Any]]) -> None:
    """Append legacy cluster calculation logs.

    Current I5B tooling writes calculation details to PostgreSQL tables instead
    of JSONL logs. This helper remains for historical log fixtures only.
    """
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            payload = {
                "generated_at": generated_at,
                "cluster_id": row["id"],
                "emperor": row["emperor"],
                "rule_code": row["rule_code"],
                "positive_signal": row["positive_signal"],
                "negative_signal": row["negative_signal"],
                "net_signal": row["net_signal"],
                "signal_intensity": row["signal_intensity"],
                "cluster_direction": row["cluster_direction"],
                "formula_code": row["formula_code"],
                "note": row["note"],
                "material_ids": row["material_ids"],
                "calc_note": row["calc_note"],
            }
            if row.get("calc_detail") is not None:
                payload["calc_detail"] = row["calc_detail"]
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _filters(values: tuple[str, ...]) -> set[str]:
    return {value for value in values if value}


def fetch_cluster_calc_detail_rows(
    *,
    dsn: str,
    item_code: str,
    formula_code: str,
    emperors: tuple[str, ...] = (),
    rule_codes: tuple[str, ...] = (),
) -> dict[tuple[str, str], dict[str, Any]]:
    emperor_filter = _filters(emperors)
    rule_filter = _filters(rule_codes)
    clauses = ["i.item_code = %s", "c.formula_code = %s", "d.formula_code = %s"]
    params: list[Any] = [item_code, formula_code, formula_code]
    if emperor_filter:
        clauses.append("e.name = any(%s)")
        params.append(sorted(emperor_filter))
    if rule_filter:
        clauses.append("r.rule_code = any(%s)")
        params.append(sorted(rule_filter))
    where_sql = " and ".join(clauses)

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                select
                    c.id as cluster_id,
                    e.name as emperor,
                    r.rule_code,
                    c.positive_signal,
                    c.negative_signal,
                    c.net_signal,
                    c.signal_intensity,
                    c.cluster_direction,
                    c.formula_code,
                    c.note,
                    d.material_ids,
                    d.calc_note,
                    d.calc_detail
                  from evd_clusters c
                  join evd_cluster_calc_details d on d.cluster_id = c.id
                  join emps e on e.id = c.emp_id
                  join eval_items i on i.id = c.item_id
                  join eval_rules r on r.id = c.rule_id
                 where {where_sql}
                 order by e.name, r.rule_code
                """,
                tuple(params),
            )
            columns = [desc.name for desc in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]

    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        emperor = str(row["emperor"])
        rule_code = str(row["rule_code"])
        row["positive_signal"] = str(row["positive_signal"])
        row["negative_signal"] = str(row["negative_signal"])
        row["net_signal"] = str(row["net_signal"])
        row["signal_intensity"] = str(row["signal_intensity"])
        row["material_ids"] = list(row.get("material_ids") or [])
        latest[(emperor, rule_code)] = row
    return latest


def fetch_materials(
    *,
    dsn: str,
    emperor: str,
    item_code: str,
    rule_code: str | None = None,
) -> dict[str, Any]:
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            params: list[Any] = [emperor, item_code]
            rule_filter = ""
            if rule_code:
                rule_filter = "and r.rule_code = %s"
                params.append(rule_code)
            cur.execute(
                f"""
                select
                    osrc.id as obj_src_id,
                    e.id as emp_id,
                    e.name as emperor,
                    i.item_code,
                    r.id as rule_id,
                    r.rule_code,
                    ro.id as obj_id,
                    ro.name as obj_name,
                    ro.obj_type,
                    eo.id as emp_obj_id,
                    sd.id as doc_id,
                    sd.src_key,
                    sd.title,
                    sd.volume,
                    sd.locator,
                    osrc.direction,
                    osrc.note as obj_src_note,
                    ro.note as obj_note,
                    coalesce(
                        jsonb_agg(
                            distinct jsonb_build_object(
                                'attr_code', oa.attr_code,
                                'value_text', oa.value_text,
                                'value_num', oa.value_num,
                                'confidence', oa.confidence,
                                'note', oa.note
                            )
                        ) filter (where oa.id is not null),
                        '[]'::jsonb
                    ) as attrs
                from obj_srcs osrc
                join emp_objs eo on eo.id = osrc.emp_obj_id
                join emps e on e.id = eo.emp_id
                join eval_items i on i.id = osrc.item_id
                join eval_rules r on r.id = osrc.rule_id
                join raw_objs ro on ro.id = osrc.obj_id
                join src_docs sd on sd.id = osrc.doc_id
                left join obj_attrs oa on oa.obj_id = ro.id
                where e.name = %s
                  and i.item_code = %s
                  {rule_filter}
                group by
                    osrc.id, e.id, e.name, i.item_code, r.id, r.rule_code,
                    ro.id, ro.name, ro.obj_type, eo.id, sd.id, sd.src_key,
                    sd.title, sd.volume, sd.locator, osrc.direction, osrc.note, ro.note
                order by r.rule_code, osrc.direction desc, osrc.id
                """,
                tuple(params),
            )
            rows = [dict(zip([desc.name for desc in cur.description], row)) for row in cur.fetchall()]

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        row["attrs"] = list(row["attrs"])
        grouped.setdefault(str(row["rule_code"]), []).append(row)

    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "emperor": emperor,
        "item_code": item_code,
        "rule_code": rule_code,
        "material_count": len(rows),
        "rules": grouped,
    }


def render_materials_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# {report['emperor']} 证据簇材料",
        "",
        f"- item_code: `{report['item_code']}`",
        f"- rule_code: `{report.get('rule_code') or 'ALL'}`",
        f"- material_count: `{report['material_count']}`",
        "",
    ]
    for rule_code, rows in report["rules"].items():
        lines.extend([f"## {rule_code}", ""])
        for row in rows:
            attrs = ", ".join(
                f"{attr.get('attr_code')}={attr.get('value_text') or attr.get('value_num')}"
                for attr in row.get("attrs", [])
                if attr.get("attr_code")
            )
            attrs_text = f"；attrs: {attrs}" if attrs else ""
            lines.append(
                f"- `{row['obj_src_id']}` `{row['direction']}` {row['obj_name']} "
                f"({row['src_key']}): {row['obj_src_note']}{attrs_text}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_materials_report(path: Path, report: dict[str, Any], *, output_format: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "json":
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return
    if output_format == "markdown":
        path.write_text(render_materials_markdown(report), encoding="utf-8")
        return
    raise EvidenceClusterWorkbenchError(f"unknown output format: {output_format}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evidence cluster material workbench for local PostgreSQL data.")
    parser.add_argument("--dsn-env", default=DEFAULT_DSN_ENV, help="Environment variable name for PostgreSQL DSN.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    materials = subparsers.add_parser("materials", help="Fetch obj_srcs grouped by rule.")
    materials.add_argument("--emperor", required=True, help="Emperor name.")
    materials.add_argument("--item-code", default="I5B", help="Evaluation item code.")
    materials.add_argument("--rule-code", default=None, help="Optional rule_code filter.")
    materials.add_argument("--output", type=Path, required=True, help="Output report path.")
    materials.add_argument("--format", choices=("json", "markdown"), default="markdown", help="Output format.")

    upsert = subparsers.add_parser("upsert", help="Upsert judged evidence cluster strengths.")
    upsert.add_argument("--input", type=Path, required=True, help="UTF-8 JSON cluster payload.")
    upsert.add_argument("--log", type=Path, default=None, help="Deprecated; calculation details are stored in DB.")
    upsert.add_argument("--dry-run", action="store_true", help="Rollback database writes.")
    upsert.add_argument(
        "--allow-partial-material-coverage",
        action="store_true",
        help="Allow cluster material_ids/calc_detail to omit DB obj_srcs for this emperor/rule.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    dsn = resolve_dsn(args.dsn_env)

    if args.command == "materials":
        report = fetch_materials(
            dsn=dsn,
            emperor=args.emperor,
            item_code=args.item_code,
            rule_code=args.rule_code,
        )
        write_materials_report(args.output, report, output_format=args.format)
        print(
            json.dumps(
                {
                    "output": str(args.output),
                    "emperor": report["emperor"],
                    "material_count": report["material_count"],
                    "rules": sorted(report["rules"]),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "upsert":
        item_code, clusters = load_cluster_payload(args.input)
        report = upsert_clusters(
            dsn=dsn,
            item_code=item_code,
            clusters=clusters,
            dry_run=args.dry_run,
            log_path=args.log,
            require_full_material_coverage=not args.allow_partial_material_coverage,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    raise EvidenceClusterWorkbenchError(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
