from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev import i5b_factor_table_sync as factor_sync


DEFAULT_RULE_DOCS = {
    "I5B": factor_sync.I5B_RULE_DOC,
}
DEFAULT_DSN_ENV = "EMPEROR_EVAL_RETRIEVAL_V2_DSN"
DEFAULT_WEIGHT_VERSION = "v1"
WEIGHT_COMPARISON_KEYS = (
    "item_code",
    "rule_code",
    "rule_label",
    "formula_code",
    "weight_version",
    "weight_num",
    "weight_order",
)


@dataclass(frozen=True)
class RuleScoreWeight:
    item_code: str
    rule_code: str
    rule_label: str
    formula_code: str
    weight_version: str
    weight_num: Decimal
    weight_order: int
    weight_basis: str
    source_doc: str
    source_line: int

    def to_dict(self) -> dict[str, object]:
        return {
            "item_code": self.item_code,
            "rule_code": self.rule_code,
            "rule_label": self.rule_label,
            "formula_code": self.formula_code,
            "weight_version": self.weight_version,
            "weight_num": factor_sync.format_decimal(self.weight_num),
            "weight_order": self.weight_order,
            "weight_basis": self.weight_basis,
            "source_doc": self.source_doc,
            "source_line": self.source_line,
        }


def default_rule_doc(item_code: str) -> Path:
    try:
        return DEFAULT_RULE_DOCS[item_code]
    except KeyError as exc:
        raise SystemExit(f"--rule-doc is required for item_code {item_code}") from exc


def rule_labels_from_doc(text: str) -> dict[str, str]:
    labels: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"^#{2,3}\s+(?:[一二三四五六七八九十]+、)?`([^`]+)`\s*(.*?)\s*$", line)
        if not match:
            continue
        code = match.group(1).strip()
        label = match.group(2).strip()
        if code and label:
            labels[code] = label
    return labels


def extract_rule_score_weights(
    rule_doc: Path,
    *,
    item_code: str,
    weight_version: str = DEFAULT_WEIGHT_VERSION,
) -> list[RuleScoreWeight]:
    text = rule_doc.read_text(encoding="utf-8")
    source_doc = factor_sync.repo_relative(rule_doc)
    formula_code = factor_sync.extract_formula_code(text)
    labels = rule_labels_from_doc(text)
    rows: list[RuleScoreWeight] = []

    for line_no, line in enumerate(text.splitlines(), start=1):
        match = re.match(
            r"^\s*\+?\s*([+-]?\d+(?:\.\d+)?)\s*\*\s*([a-z][a-z0-9_]*)\.(?:rule_net_effect|rule_net_signal|rule_raw_net)\s*$",
            line,
        )
        if not match:
            continue
        weight_num = Decimal(match.group(1))
        rule_code = match.group(2)
        rule_label = labels.get(rule_code, "")
        order = (len(rows) + 1) * 10
        basis_label = rule_label or rule_code
        rows.append(
            RuleScoreWeight(
                item_code=item_code,
                rule_code=rule_code,
                rule_label=rule_label,
                formula_code=formula_code,
                weight_version=weight_version,
                weight_num=weight_num,
                weight_order=order,
                weight_basis=f"{item_code} 总分权重：{basis_label} 在 {formula_code} 总分公式中的线性权重。",
                source_doc=source_doc,
                source_line=line_no,
            )
        )
    return rows


def extract_snapshot(
    *,
    item_code: str,
    rule_doc: Path,
    default_factor_doc: Path,
    include_defaults: bool,
    scope: str,
) -> dict[str, list[dict[str, object]]]:
    payload: dict[str, list[dict[str, object]]] = {}
    if scope in {"all", "factors"}:
        factor_rows = factor_sync.extract_factor_options(
            rule_doc=rule_doc,
            default_doc=default_factor_doc,
            include_defaults=include_defaults,
            item_code=item_code,
            allowed_rule_codes=None,
        )
        payload["factor_options"] = [row.to_dict() for row in factor_rows]
    if scope in {"all", "weights"}:
        payload["rule_score_weights"] = [row.to_dict() for row in extract_rule_score_weights(rule_doc, item_code=item_code)]
    return payload


def normalize_weight_row(row: dict[str, object]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key in WEIGHT_COMPARISON_KEYS:
        value = row.get(key, "")
        if key == "weight_num":
            normalized[key] = factor_sync.format_decimal(Decimal(str(value)))
        elif key == "weight_order":
            normalized[key] = str(int(value))
        else:
            normalized[key] = str(value)
    return normalized


def compare_weight_rows(
    expected: Iterable[dict[str, object]],
    actual: Iterable[RuleScoreWeight],
) -> dict[str, list[dict[str, str]]]:
    expected_rows = [normalize_weight_row(row) for row in expected]
    actual_rows = [normalize_weight_row(row.to_dict()) for row in actual]
    expected_keys = {tuple(row[key] for key in WEIGHT_COMPARISON_KEYS): row for row in expected_rows}
    actual_keys = {tuple(row[key] for key in WEIGHT_COMPARISON_KEYS): row for row in actual_rows}
    return {
        "missing": [expected_keys[key] for key in sorted(expected_keys.keys() - actual_keys.keys())],
        "extra": [actual_keys[key] for key in sorted(actual_keys.keys() - expected_keys.keys())],
    }


def dump_retrieval_v2_factor_options(
    dsn: str,
    *,
    item_code: str,
    formula_code: str | None = None,
) -> list[dict[str, object]]:
    import psycopg

    params: list[object] = [item_code]
    formula_clause = ""
    if formula_code:
        formula_clause = "and f.formula_code = %s"
        params.append(formula_code)

    sql = f"""
        select
            o.id as factor_option_id,
            f.item_code,
            f.rule_code,
            f.formula_code,
            f.factor_name,
            f.factor_scope,
            o.label,
            o.value_num,
            o.sort_no,
            o.source_doc,
            f.source_heading,
            o.source_line,
            o.option_note as note
        from retrieval_v2.eval_rule_factors f
        join retrieval_v2.eval_rule_factor_options o on o.factor_id = f.id
        where f.item_code = %s
          and f.factor_status = 'active'
          and o.option_status = 'active'
          {formula_clause}
        order by f.rule_code, f.factor_name, o.sort_no, o.id
    """
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            columns = [desc.name for desc in cur.description]
            rows = []
            for values in cur.fetchall():
                row = dict(zip(columns, values))
                row["value_num"] = factor_sync.format_decimal(Decimal(str(row["value_num"])))
                rows.append(row)
            return rows


def dump_rule_score_weights(
    dsn: str,
    *,
    item_code: str,
    formula_code: str | None = None,
) -> list[dict[str, object]]:
    import psycopg

    params: list[object] = [item_code]
    formula_clause = ""
    if formula_code:
        formula_clause = "and formula_code = %s"
        params.append(formula_code)
    sql = f"""
        select
            item_code,
            rule_code,
            rule_label,
            formula_code,
            weight_version,
            weight_num,
            weight_order,
            weight_basis,
            source_doc,
            source_line
        from retrieval_v2.item_rule_score_weights
        where item_code = %s
          and weight_status = 'active'
          {formula_clause}
        order by weight_order, rule_code
    """
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            columns = [desc.name for desc in cur.description]
            rows = []
            for values in cur.fetchall():
                row = dict(zip(columns, values))
                row["weight_num"] = factor_sync.format_decimal(Decimal(str(row["weight_num"])))
                rows.append(row)
            return rows


def compare_db_sync(
    dsn: str,
    *,
    item_code: str,
    rule_doc: Path,
    default_factor_doc: Path,
    include_defaults: bool,
    scope: str,
) -> dict[str, object]:
    doc_factors = factor_sync.extract_factor_options(
        rule_doc=rule_doc,
        default_doc=default_factor_doc,
        include_defaults=include_defaults,
        item_code=item_code,
        allowed_rule_codes=None,
    )
    doc_weights = extract_rule_score_weights(rule_doc, item_code=item_code)
    formula_code = factor_sync.extract_formula_code(rule_doc.read_text(encoding="utf-8"))
    payload: dict[str, object] = {}
    if scope in {"all", "factors"}:
        db_factors = dump_retrieval_v2_factor_options(dsn, item_code=item_code, formula_code=formula_code)
        diff = factor_sync.compare_rows(db_factors, doc_factors)
        payload["factor_options"] = {"table_only": diff["missing"], "doc_only": diff["extra"]}
    if scope in {"all", "weights"}:
        db_weights = dump_rule_score_weights(dsn, item_code=item_code, formula_code=formula_code)
        diff = compare_weight_rows(db_weights, doc_weights)
        payload["rule_score_weights"] = {"table_only": diff["missing"], "doc_only": diff["extra"]}
    return payload


def audit_factor_judgments(
    dsn: str,
    *,
    item_code: str,
    formula_code: str,
    rule_codes: Sequence[str] = (),
    target_codes: Sequence[str] = (),
) -> dict[str, object]:
    import psycopg

    clauses = ["j.item_code = %s", "j.formula_code = %s"]
    params: list[object] = [item_code, formula_code]
    if rule_codes:
        clauses.append("j.rule_code = any(%s)")
        params.append(list(rule_codes))
    if target_codes:
        clauses.append("rt.target_code = any(%s)")
        params.append(list(target_codes))
    where_sql = " and ".join(clauses)
    sql = f"""
        select
            j.id as factor_judgment_id,
            rt.emperor_name,
            rt.target_code,
            j.rule_code,
            j.target_action::text as target_action,
            j.side::text as side,
            b.binding_code,
            c.factor_name,
            c.option_label,
            c.value_num::text as judgment_value,
            active.factor_rule_code,
            active.factor_option_id,
            active.active_value::text as active_value
        from retrieval_v2.claim_rule_binding_factor_judgments j
        join retrieval_v2.retrieval_targets rt on rt.id = j.target_id
        join retrieval_v2.claim_rule_bindings b on b.id = j.binding_id
        left join retrieval_v2.claim_rule_binding_factor_choices c on c.factor_judgment_id = j.id
        left join lateral (
            select
                f.rule_code as factor_rule_code,
                o.id as factor_option_id,
                o.value_num as active_value
            from retrieval_v2.eval_rule_factors f
            join retrieval_v2.eval_rule_factor_options o on o.factor_id = f.id
            where f.item_code = j.item_code
              and f.formula_code = j.formula_code
              and f.factor_name = c.factor_name
              and f.factor_status = 'active'
              and f.rule_code in (j.rule_code, '')
              and o.option_status = 'active'
              and o.label = c.option_label
            order by case when f.rule_code = j.rule_code then 0 else 1 end, o.id
            limit 1
        ) active on true
        where {where_sql}
        order by rt.emperor_name, j.rule_code, j.id, c.factor_name
    """
    rows: list[dict[str, object]] = []
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            columns = [desc.name for desc in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]

    issues: list[dict[str, object]] = []
    checked = 0
    for row in rows:
        factor_name = str(row.get("factor_name") or "")
        if not factor_name:
            if row.get("target_action") == "score":
                issues.append({**row, "severity": "error", "status": "missing_factor_choice"})
            continue
        checked += 1
        if not row.get("factor_option_id"):
            issues.append({**row, "severity": "error", "status": "stale_or_unknown_factor_option"})
            continue
        judgment_value = factor_sync.format_decimal(Decimal(str(row.get("judgment_value"))))
        active_value = factor_sync.format_decimal(Decimal(str(row.get("active_value"))))
        if judgment_value != active_value:
            issues.append(
                {
                    **row,
                    "severity": "error",
                    "status": "factor_value_mismatch",
                    "judgment_value": judgment_value,
                    "active_value": active_value,
                }
            )
    error_count = sum(1 for issue in issues if issue.get("severity") == "error")
    return {
        "ok": error_count == 0,
        "checked_factor_choices": checked,
        "judgment_rows": len({row.get("factor_judgment_id") for row in rows}),
        "error_count": error_count,
        "issues": issues,
    }


def weight_source_fingerprint(row: RuleScoreWeight) -> str:
    import hashlib

    source = "|".join(
        [
            row.item_code,
            row.rule_code,
            row.formula_code,
            row.weight_version,
            factor_sync.format_decimal(row.weight_num),
            f"{row.source_doc}:{row.source_line}",
        ]
    )
    return hashlib.md5(source.encode("utf-8")).hexdigest()


def render_weight_upsert_sql(rows: Sequence[RuleScoreWeight]) -> str:
    if not rows:
        return ""
    values = ",\n".join(
        "    ("
        + ", ".join(
            [
                factor_sync.sql_literal(row.item_code),
                factor_sync.sql_literal(row.rule_code),
                factor_sync.sql_literal(row.rule_label),
                factor_sync.sql_literal(row.formula_code),
                factor_sync.sql_literal(row.weight_version),
                factor_sync.format_decimal(row.weight_num),
                str(row.weight_order),
                factor_sync.sql_literal(row.weight_basis),
                factor_sync.sql_literal(row.source_doc),
                str(row.source_line),
                factor_sync.sql_literal(weight_source_fingerprint(row)),
            ]
        )
        + ")"
        for row in rows
    )
    return f"""with doc_weights(
    item_code,
    rule_code,
    rule_label,
    formula_code,
    weight_version,
    weight_num,
    weight_order,
    weight_basis,
    source_doc,
    source_line,
    source_fingerprint
) as (
    values
{values}
),
resolved as (
    select
        ei.id as item_id,
        er.id as rule_id,
        doc_weights.*
    from doc_weights
    left join retrieval_v2.eval_items ei on ei.item_code = doc_weights.item_code
    left join retrieval_v2.eval_rules er on er.item_id = ei.id and er.rule_code = doc_weights.rule_code
)
insert into retrieval_v2.item_rule_score_weights (
    item_id,
    rule_id,
    item_code,
    rule_code,
    rule_label,
    formula_code,
    weight_version,
    weight_num,
    weight_order,
    weight_status,
    weight_basis,
    source_doc,
    source_line,
    source_fingerprint,
    weight_payload
)
select
    item_id,
    rule_id,
    item_code,
    rule_code,
    rule_label,
    formula_code,
    weight_version,
    weight_num,
    weight_order,
    'active'::retrieval_v2.rv2_rule_weight_status,
    weight_basis,
    source_doc,
    source_line,
    source_fingerprint,
    jsonb_build_object('source', 'scoring_rule_table_sync', 'scope', 'item_rule_total_weight')
from resolved
on conflict on constraint rv2_item_rule_score_weights_item_rule_formula_version_uk do update
set
    item_id = coalesce(excluded.item_id, retrieval_v2.item_rule_score_weights.item_id),
    rule_id = coalesce(excluded.rule_id, retrieval_v2.item_rule_score_weights.rule_id),
    rule_label = excluded.rule_label,
    weight_num = excluded.weight_num,
    weight_order = excluded.weight_order,
    weight_status = excluded.weight_status,
    weight_basis = excluded.weight_basis,
    source_doc = excluded.source_doc,
    source_line = excluded.source_line,
    source_fingerprint = excluded.source_fingerprint,
    weight_payload = retrieval_v2.item_rule_score_weights.weight_payload || excluded.weight_payload,
    updated_at = now();
"""


def render_markdown(payload: dict[str, list[dict[str, object]]]) -> str:
    lines: list[str] = []
    if "factor_options" in payload:
        lines.extend(["## factor_options", "", factor_sync.render_markdown([]).rstrip()])
        for row in payload["factor_options"]:
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(row["item_code"]),
                        str(row["rule_code"]),
                        str(row["factor_name"]),
                        str(row["factor_scope"]),
                        str(row["label"]),
                        str(row["value_num"]),
                        str(row["source_line"]),
                    ]
                )
                + " |"
            )
        lines.append("")
    if "rule_score_weights" in payload:
        lines.extend(
            [
                "## rule_score_weights",
                "",
                "| item_code | rule_code | rule_label | formula_code | weight_num | weight_order | source_line |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for row in payload["rule_score_weights"]:
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(row["item_code"]),
                        str(row["rule_code"]),
                        str(row["rule_label"]),
                        str(row["formula_code"]),
                        str(row["weight_num"]),
                        str(row["weight_order"]),
                        str(row["source_line"]),
                    ]
                )
                + " |"
            )
    return "\n".join(lines).rstrip() + "\n"


def has_diff(payload: dict[str, object]) -> bool:
    for value in payload.values():
        if not isinstance(value, dict):
            continue
        if value.get("table_only") or value.get("doc_only"):
            return True
    return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync structured scoring rule docs with rule tables.")
    parser.add_argument("--item-code", default="I5B")
    parser.add_argument("--rule-doc", type=Path)
    parser.add_argument("--default-factor-doc", type=Path, default=factor_sync.DEFAULT_FACTOR_DOC)
    parser.add_argument("--no-defaults", action="store_true", help="Do not include shared default factor options.")
    parser.add_argument("--scope", choices=("all", "factors", "weights"), default="all")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--render-upsert-sql", action="store_true", help="Render supported factor and weight upsert SQL for the selected scope.")
    parser.add_argument("--render-weight-upsert-sql", action="store_true", help="Render retrieval_v2.item_rule_score_weights upsert SQL.")
    parser.add_argument("--dump-db-json", action="store_true", help="Dump active retrieval_v2 rule-table snapshot.")
    parser.add_argument("--check-db-sync", action="store_true", help="Compare Markdown extraction with retrieval_v2 tables.")
    parser.add_argument("--audit-factor-judgments", action="store_true", help="Audit retrieval_v2 factor judgments against active factor option tables.")
    parser.add_argument("--rule-code", action="append", default=None, help="Optional rule_code filter for factor judgment audit; repeatable.")
    parser.add_argument("--target-code", action="append", default=None, help="Optional target_code filter for factor judgment audit; repeatable.")
    parser.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    parser.add_argument("--fail-on-diff", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rule_doc = args.rule_doc or default_rule_doc(args.item_code)
    include_defaults = not args.no_defaults

    if args.render_upsert_sql or args.render_weight_upsert_sql:
        chunks: list[str] = []
        if args.render_upsert_sql and args.scope in {"all", "factors"}:
            factor_rows = factor_sync.extract_factor_options(
                rule_doc=rule_doc,
                default_doc=args.default_factor_doc,
                include_defaults=include_defaults,
                item_code=args.item_code,
                allowed_rule_codes=None,
            )
            chunks.append("-- factor options -> retrieval_v2.eval_rule_factors / retrieval_v2.eval_rule_factor_options\n")
            chunks.append(factor_sync.render_upsert_sql(factor_rows).rstrip() + "\n")
        if args.scope in {"all", "weights"}:
            weight_rows = extract_rule_score_weights(rule_doc, item_code=args.item_code)
            chunks.append("-- rule score weights -> retrieval_v2.item_rule_score_weights\n")
            chunks.append(render_weight_upsert_sql(weight_rows).rstrip() + "\n")
        factor_sync.write_output("\n".join(chunks), args.output)
        return 0

    if args.audit_factor_judgments:
        dsn = factor_sync.resolve_dsn(args.dsn_env)
        formula_code = factor_sync.extract_formula_code(rule_doc.read_text(encoding="utf-8"))
        payload = audit_factor_judgments(
            dsn,
            item_code=args.item_code,
            formula_code=formula_code,
            rule_codes=tuple(args.rule_code or ()),
            target_codes=tuple(args.target_code or ()),
        )
        factor_sync.write_output(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", args.output)
        return 1 if args.fail_on_diff and not payload["ok"] else 0

    if args.dump_db_json or args.check_db_sync:
        dsn = factor_sync.resolve_dsn(args.dsn_env)
        if args.check_db_sync:
            payload = compare_db_sync(
                dsn,
                item_code=args.item_code,
                rule_doc=rule_doc,
                default_factor_doc=args.default_factor_doc,
                include_defaults=include_defaults,
                scope=args.scope,
            )
            factor_sync.write_output(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", args.output)
            return 1 if args.fail_on_diff and has_diff(payload) else 0

        formula_code = factor_sync.extract_formula_code(rule_doc.read_text(encoding="utf-8"))
        payload: dict[str, object] = {}
        if args.scope in {"all", "factors"}:
            payload["factor_options"] = dump_retrieval_v2_factor_options(
                dsn,
                item_code=args.item_code,
                formula_code=formula_code,
            )
        if args.scope in {"all", "weights"}:
            payload["rule_score_weights"] = dump_rule_score_weights(
                dsn,
                item_code=args.item_code,
                formula_code=formula_code,
            )
        factor_sync.write_output(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", args.output)
        return 0

    payload = extract_snapshot(
        item_code=args.item_code,
        rule_doc=rule_doc,
        default_factor_doc=args.default_factor_doc,
        include_defaults=include_defaults,
        scope=args.scope,
    )
    if args.format == "markdown":
        text = render_markdown(payload)
    else:
        text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    factor_sync.write_output(text, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
