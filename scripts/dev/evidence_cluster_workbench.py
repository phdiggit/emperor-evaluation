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


def upsert_clusters(
    *,
    dsn: str,
    item_code: str,
    clusters: tuple[ClusterInput, ...],
    dry_run: bool = False,
    log_path: Path = DEFAULT_LOG_PATH,
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
                        "material_ids": list(cluster.material_ids),
                        "calc_note": cluster.calc_note,
                    }
                )

        if dry_run:
            conn.rollback()
        else:
            conn.commit()

    if not dry_run:
        append_calc_log(log_path, rows)

    return {"dry_run": dry_run, "item_code": item_code, "clusters": rows}


def append_calc_log(path: Path, rows: list[dict[str, Any]]) -> None:
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
                "formula_code": row["formula_code"],
                "material_ids": row["material_ids"],
                "calc_note": row["calc_note"],
            }
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


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
    upsert.add_argument("--log", type=Path, default=DEFAULT_LOG_PATH, help="JSONL calculation log path.")
    upsert.add_argument("--dry-run", action="store_true", help="Rollback database writes and skip log append.")

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
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    raise EvidenceClusterWorkbenchError(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
