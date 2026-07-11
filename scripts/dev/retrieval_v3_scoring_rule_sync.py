from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v3_bootstrap import import_psycopg, load_env_file, resolve_dsn


RULE_DOC = ROOT / "docs" / "分项规则" / "第五项统治者政治素质" / "B用人与授权.md"
SOURCE_DOC = "docs/分项规则/第五项统治者政治素质/B用人与授权.md"
ITEM_CODE = "I5B"
FORMULA_CODE = "evidence_cluster_signal_v3"
RULE_CODES = {
    "talent_discovery",
    "appointment_delegation",
    "team_building",
    "tolerate_talent",
    "anti_nepotism",
}
RULE_LABELS = {
    "talent_discovery": "发现人才",
    "appointment_delegation": "任用授权质量",
    "team_building": "建立团队",
    "tolerate_talent": "容人保全",
    "anti_nepotism": "避免任人唯亲",
}


@dataclass(frozen=True)
class FactorOption:
    rule_code: str
    factor_name: str
    factor_scope: str
    label: str
    value_num: Decimal
    sort_no: int
    source_heading: str
    source_line: int

    @property
    def key(self) -> tuple[str, str, str]:
        return self.rule_code, self.factor_name, self.label


@dataclass(frozen=True)
class RuleWeight:
    rule_code: str
    rule_label: str
    value_num: Decimal
    weight_order: int
    source_line: int


def decimal_text(value: Decimal) -> str:
    return format(value.normalize(), "f")


def fingerprint(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def synthetic_source_id(*parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return -(int.from_bytes(digest[:8], "big") % (2**62 - 1) + 1)


def table_cells(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return []
    return [cell.strip().strip("`").strip() for cell in stripped.strip("|").split("|")]


def numeric(value: str) -> Decimal | None:
    cleaned = value.strip().strip("`").lstrip("+")
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", cleaned):
        return None
    return Decimal(cleaned)


def factor_scope(rule_code: str, factor_name: str) -> str:
    if not rule_code:
        return "default"
    if rule_code == "team_building":
        return "team"
    if rule_code == "talent_discovery" and factor_name == "talent_quality_factor":
        return "attribute_mapping"
    return "rule"


def parse_rule_doc(path: Path = RULE_DOC) -> tuple[list[FactorOption], list[RuleWeight]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    factors: list[FactorOption] = []
    weights: list[RuleWeight] = []
    rule_code = ""
    rule_label = ""
    factor_name = ""
    factor_heading = ""
    table_header: list[str] | None = None
    sort_no = 0

    for line_no, line in enumerate(lines, start=1):
        h2 = re.match(r"^##\s+.+?`([a-z][a-z0-9_]*)`\s*(.*?)\s*$", line)
        if h2:
            candidate = h2.group(1)
            rule_code = candidate if candidate in RULE_CODES else ""
            rule_label = h2.group(2).strip()
            factor_name = ""
            table_header = None
            continue
        h3 = re.match(r"^###\s+`([a-z][a-z0-9_]*)`\s*$", line)
        if h3:
            factor_name = h3.group(1)
            factor_heading = factor_name
            table_header = None
            sort_no = 0
            continue
        if line.startswith("## ") or line.startswith("### "):
            factor_name = ""
            table_header = None
            continue
        cells = table_cells(line)
        if factor_name and cells:
            if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                continue
            if table_header is None:
                table_header = cells
                continue
            first = numeric(cells[0]) if cells else None
            second = numeric(cells[1]) if len(cells) > 1 else None
            if first is None and second is None:
                continue
            sort_no += 1
            if first is not None:
                value, label = first, cells[1]
            else:
                value, label = second, cells[0]
            factors.append(
                FactorOption(
                    rule_code=rule_code,
                    factor_name=factor_name,
                    factor_scope=factor_scope(rule_code, factor_name),
                    label=label,
                    value_num=value,
                    sort_no=sort_no,
                    source_heading=factor_heading,
                    source_line=line_no,
                )
            )

        weight = re.match(
            r"^\s*\+?\s*(\d+(?:\.\d+)?)\s*\*\s*([a-z][a-z0-9_]*)\.rule_raw_net\s*$",
            line,
        )
        if weight and weight.group(2) in RULE_CODES:
            code = weight.group(2)
            weights.append(RuleWeight(code, RULE_LABELS[code], Decimal(weight.group(1)), len(weights) * 10 + 10, line_no))

    duplicates = [key for key in {row.key for row in factors} if sum(row.key == key for row in factors) > 1]
    if duplicates:
        raise ValueError(f"duplicate factor options in rule doc: {duplicates}")
    if {row.rule_code for row in weights} != RULE_CODES:
        raise ValueError("rule weight formula does not cover every I5B rule")
    return factors, weights


def db_snapshot(cur: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cur.execute(
        """
        select f.rule_code, f.factor_name, f.factor_scope, o.label, o.value_num::text,
               o.sort_no, o.source_doc, o.source_line
          from retrieval_v3.eval_rule_factors f
          join retrieval_v3.eval_rule_factor_options o on o.factor_id = f.id
         where f.item_code = %s and f.formula_code = %s
           and f.factor_status = 'active' and o.option_status = 'active'
         order by f.rule_code, f.factor_name, o.sort_no, o.id
        """,
        (ITEM_CODE, FORMULA_CODE),
    )
    factor_rows = [dict(row) for row in cur.fetchall()]
    cur.execute(
        """
        select rule_code, rule_label, weight_num::text as value_num, weight_order, source_doc, source_line
          from retrieval_v3.item_rule_score_weights
         where item_code = %s and formula_code = %s and weight_status = 'active'
         order by weight_order, rule_code
        """,
        (ITEM_CODE, FORMULA_CODE),
    )
    weight_rows = [dict(row) for row in cur.fetchall()]
    return factor_rows, weight_rows


def normalized_doc_factors(rows: list[FactorOption]) -> dict[tuple[str, str, str], dict[str, Any]]:
    return {
        row.key: {
            "rule_code": row.rule_code,
            "factor_name": row.factor_name,
            "factor_scope": row.factor_scope,
            "label": row.label,
            "value_num": decimal_text(row.value_num),
            "sort_no": row.sort_no,
            "source_doc": SOURCE_DOC,
            "source_line": row.source_line,
        }
        for row in rows
    }


def normalized_db_factors(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    result = {}
    for row in rows:
        normalized = dict(row)
        normalized["value_num"] = decimal_text(Decimal(row["value_num"]))
        key = row["rule_code"], row["factor_name"], row["label"]
        result[key] = normalized
    return result


def diff_maps(expected: dict[Any, dict[str, Any]], actual: dict[Any, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    added = [expected[key] for key in sorted(expected.keys() - actual.keys())]
    retired = [actual[key] for key in sorted(actual.keys() - expected.keys())]
    changed = []
    for key in sorted(expected.keys() & actual.keys()):
        fields = {name: {"db": actual[key].get(name), "doc": expected[key].get(name)} for name in expected[key] if actual[key].get(name) != expected[key].get(name)}
        if fields:
            changed.append({"key": list(key) if isinstance(key, tuple) else key, "fields": fields})
    return {"added": added, "changed": changed, "retired": retired}


def audit(cur: Any, factors: list[FactorOption], weights: list[RuleWeight]) -> dict[str, Any]:
    db_factors, db_weights = db_snapshot(cur)
    expected_weights = {
        row.rule_code: {
            "rule_code": row.rule_code,
            "rule_label": row.rule_label,
            "value_num": decimal_text(row.value_num),
            "weight_order": row.weight_order,
            "source_doc": SOURCE_DOC,
            "source_line": row.source_line,
        }
        for row in weights
    }
    actual_weights = {row["rule_code"]: {**row, "value_num": decimal_text(Decimal(row["value_num"]))} for row in db_weights}
    factor_diff = diff_maps(normalized_doc_factors(factors), normalized_db_factors(db_factors))
    weight_diff = diff_maps(expected_weights, actual_weights)
    cur.execute(
        "select rule_code, rule_label from retrieval_v3.eval_rules where item_code=%s and rule_status='active' order by rule_code",
        (ITEM_CODE,),
    )
    actual_rules = {row["rule_code"]: {"rule_code": row["rule_code"], "rule_label": row["rule_label"]} for row in cur.fetchall()}
    expected_rules = {code: {"rule_code": code, "rule_label": label} for code, label in RULE_LABELS.items()}
    rule_diff = diff_maps(expected_rules, actual_rules)
    cur.execute(
        """
        select count(*)::int as count
          from retrieval_v3.claim_rule_binding_factor_choices c
          join retrieval_v3.claim_rule_binding_factor_judgments j on j.id = c.factor_judgment_id
         where j.item_code = %s
           and not exists (
               select 1
                 from retrieval_v3.eval_rule_factors f
                 join retrieval_v3.eval_rule_factor_options o on o.factor_id = f.id
                where f.item_code = j.item_code and f.formula_code = j.formula_code
                  and f.factor_name = c.factor_name and f.rule_code in (j.rule_code, '')
                  and f.factor_status = 'active' and o.option_status = 'active'
                  and trim(trailing '。' from o.label) = trim(trailing '。' from c.option_label)
           )
        """,
        (ITEM_CODE,),
    )
    invalid_choice_count = cur.fetchone()["count"]
    cur.execute(
        """
        select count(*)::int as count
          from retrieval_v3.claim_rule_binding_factor_choices c
          join retrieval_v3.claim_rule_binding_factor_judgments j on j.id = c.factor_judgment_id
          join lateral (
              select o.value_num
                from retrieval_v3.eval_rule_factors f
                join retrieval_v3.eval_rule_factor_options o on o.factor_id = f.id
               where f.item_code = j.item_code and f.formula_code = j.formula_code
                 and f.factor_name = c.factor_name and f.rule_code in (j.rule_code, '')
                 and f.factor_status = 'active' and o.option_status = 'active'
                 and trim(trailing '。' from o.label) = trim(trailing '。' from c.option_label)
               order by case when f.rule_code = j.rule_code then 0 else 1 end
               limit 1
          ) active on true
         where j.item_code = %s and c.value_num is distinct from active.value_num
        """,
        (ITEM_CODE,),
    )
    stale_choice_value_count = cur.fetchone()["count"]
    return {
        "item_code": ITEM_CODE,
        "formula_code": FORMULA_CODE,
        "doc_factor_option_count": len(factors),
        "doc_weight_count": len(weights),
        "factor_diff": factor_diff,
        "weight_diff": weight_diff,
        "rule_diff": rule_diff,
        "invalid_factor_choice_count": invalid_choice_count,
        "stale_factor_choice_value_count": stale_choice_value_count,
        "in_sync": not any(factor_diff.values()) and not any(weight_diff.values()) and not any(rule_diff.values()) and invalid_choice_count == 0,
    }


def apply_sync(cur: Any, factors: list[FactorOption], weights: list[RuleWeight]) -> None:
    for code, label in RULE_LABELS.items():
        cur.execute(
            "update retrieval_v3.eval_rules set rule_label=%s, rule_status='active', copied_at=now() where item_code=%s and rule_code=%s",
            (label, ITEM_CODE, code),
        )
        if cur.rowcount != 1:
            raise ValueError(f"missing canonical eval_rules row for {code}")
    cur.execute(
        "update retrieval_v3.eval_rules set rule_status='retired', copied_at=now() where item_code=%s and rule_code <> all(%s) and rule_status='active'",
        (ITEM_CODE, list(RULE_CODES)),
    )
    factor_keys: list[tuple[str, str]] = []
    for row in factors:
        factor_key = (row.rule_code, row.factor_name)
        if factor_key not in factor_keys:
            factor_keys.append(factor_key)
            cur.execute(
                """
                insert into retrieval_v3.eval_rule_factors (
                    item_id, source_factor_id, item_code, rule_id, rule_code, formula_code, factor_name, factor_scope,
                    value_source, source_doc, source_heading, description, factor_status, source_row, source_fingerprint
                )
                select i.id, %s, %s, r.id, %s, %s, %s, %s, 'markdown', %s, %s, '', 'active', %s::jsonb, %s
                  from retrieval_v3.eval_items i
                  left join retrieval_v3.eval_rules r on r.item_id = i.id and r.rule_code = %s
                 where i.item_code = %s
                on conflict on constraint rv3_eval_rule_factors_code_uk do update set
                    factor_scope=excluded.factor_scope, value_source='markdown', source_doc=excluded.source_doc,
                    source_heading=excluded.source_heading, factor_status='active', source_row=excluded.source_row,
                    source_fingerprint=excluded.source_fingerprint, copied_at=now()
                """,
                (
                    synthetic_source_id(ITEM_CODE, row.rule_code, FORMULA_CODE, row.factor_name),
                    ITEM_CODE, row.rule_code, FORMULA_CODE, row.factor_name, row.factor_scope, SOURCE_DOC,
                    row.source_heading, json.dumps({"source": "retrieval_v3_scoring_rule_sync"}),
                    fingerprint([ITEM_CODE, row.rule_code, row.factor_name, row.factor_scope]), row.rule_code,
                    ITEM_CODE,
                ),
            )
        cur.execute(
            """
            select id from retrieval_v3.eval_rule_factors
             where item_code=%s and rule_code=%s and formula_code=%s and factor_name=%s
            """,
            (ITEM_CODE, row.rule_code, FORMULA_CODE, row.factor_name),
        )
        factor_id = cur.fetchone()["id"]
        cur.execute(
            """
            insert into retrieval_v3.eval_rule_factor_options (
                factor_id, source_option_id, option_code, label, value_num, sort_no, option_note, source_doc,
                source_line, option_status, source_row, source_fingerprint
            ) values (%s,%s,%s,%s,%s,%s,'',%s,%s,'active',%s::jsonb,%s)
            on conflict on constraint rv3_eval_rule_factor_options_factor_label_uk do update set
                option_code=excluded.option_code, value_num=excluded.value_num, sort_no=excluded.sort_no,
                source_doc=excluded.source_doc, source_line=excluded.source_line, option_status='active',
                source_row=excluded.source_row, source_fingerprint=excluded.source_fingerprint, copied_at=now()
            """,
            (
                factor_id, synthetic_source_id(ITEM_CODE, row.rule_code, row.factor_name, row.label),
                f"opt_{row.sort_no:03d}", row.label, row.value_num, row.sort_no, SOURCE_DOC,
                row.source_line, json.dumps({"source": "retrieval_v3_scoring_rule_sync"}),
                fingerprint([ITEM_CODE, row.rule_code, row.factor_name, row.label, decimal_text(row.value_num)]),
            ),
        )

    expected_keys = {(row.rule_code, row.factor_name, row.label) for row in factors}
    expected_factor_keys = {(row.rule_code, row.factor_name) for row in factors}
    cur.execute(
        """
        select f.rule_code, f.factor_name, o.label, o.id
          from retrieval_v3.eval_rule_factors f
          join retrieval_v3.eval_rule_factor_options o on o.factor_id=f.id
         where f.item_code=%s and f.formula_code=%s and f.factor_status='active' and o.option_status='active'
        """,
        (ITEM_CODE, FORMULA_CODE),
    )
    for db_row in cur.fetchall():
        if (db_row["rule_code"], db_row["factor_name"], db_row["label"]) not in expected_keys:
            cur.execute("update retrieval_v3.eval_rule_factor_options set option_status='inactive', copied_at=now() where id=%s", (db_row["id"],))
    cur.execute(
        """
        select id, rule_code, factor_name
          from retrieval_v3.eval_rule_factors
         where item_code=%s and formula_code=%s and factor_status='active'
        """,
        (ITEM_CODE, FORMULA_CODE),
    )
    for db_row in cur.fetchall():
        if (db_row["rule_code"], db_row["factor_name"]) not in expected_factor_keys:
            cur.execute(
                "update retrieval_v3.eval_rule_factors set factor_status='retired', factor_scope='retired', copied_at=now() where id=%s",
                (db_row["id"],),
            )

    for row in weights:
        payload = {"source": "retrieval_v3_scoring_rule_sync", "scope": "item_rule_total_weight"}
        cur.execute(
            """
            insert into retrieval_v3.item_rule_score_weights (
                item_id, rule_id, item_code, rule_code, rule_label, formula_code, weight_version,
                weight_num, weight_order, weight_status, weight_basis, source_doc, source_line,
                source_fingerprint, weight_payload
            )
            select i.id, r.id, %s,%s,%s,%s,'v1',%s,%s,'active',%s,%s,%s,%s,%s::jsonb
              from retrieval_v3.eval_items i
              left join retrieval_v3.eval_rules r on r.item_id=i.id and r.rule_code=%s
             where i.item_code=%s
            on conflict on constraint rv3_item_rule_score_weights_item_rule_formula_version_uk do update set
                item_id=excluded.item_id, rule_id=excluded.rule_id, rule_label=excluded.rule_label,
                weight_num=excluded.weight_num, weight_order=excluded.weight_order, weight_status='active',
                weight_basis=excluded.weight_basis, source_doc=excluded.source_doc,
                source_line=excluded.source_line, source_fingerprint=excluded.source_fingerprint,
                weight_payload=excluded.weight_payload, updated_at=now()
            """,
            (
                ITEM_CODE, row.rule_code, row.rule_label, FORMULA_CODE, row.value_num, row.weight_order,
                f"I5B 总分权重：{row.rule_label}。", SOURCE_DOC, row.source_line,
                fingerprint([ITEM_CODE, row.rule_code, decimal_text(row.value_num)]), json.dumps(payload),
                row.rule_code, ITEM_CODE,
            ),
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit and synchronize all I5B scoring factors and rule weights.")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--dsn-env", default="EMPEROR_EVAL_RETRIEVAL_V3_DSN")
    parser.add_argument("--rule-doc", type=Path, default=RULE_DOC)
    parser.add_argument("--execute", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    load_env_file(args.env_file)
    psycopg, dict_row = import_psycopg()
    factors, weights = parse_rule_doc(args.rule_doc)
    with psycopg.connect(resolve_dsn(args.dsn_env), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            before = audit(cur, factors, weights)
            if args.execute:
                apply_sync(cur, factors, weights)
                after = audit(cur, factors, weights)
                conn.commit()
            else:
                after = before
                conn.rollback()
    print(json.dumps({"execute": args.execute, "before": before, "after": after}, ensure_ascii=False, indent=2))
    return 0 if after["in_sync"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
