from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import psycopg


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build.i5b_item_result_calculator import DEFAULT_ITEM_CODE  # noqa: E402
from scripts.dev.evidence_cluster_workbench import DEFAULT_DSN_ENV, resolve_dsn  # noqa: E402
from scripts.dev.i5b_fact_relation_candidate_sync import (  # noqa: E402
    fetch_emperors_with_units,
    fetch_relation_options,
    fetch_unit_rows,
    relation_candidate,
    resolve_rule_codes,
)


RelationExists = Callable[[Mapping[str, object]], bool]


class FactRelationGapSummaryError(ValueError):
    pass


@dataclass(frozen=True)
class FactRelationGap:
    emperor: str
    rule_code: str
    code: str
    object_name: str
    object_type: str
    obj_src_id: int | None
    scoring_role: str
    direction: str
    causal_chain_key: str
    message: str


def _text(value: object) -> str:
    return str(value or "").strip()


def _int_or_none(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _gap(row: Mapping[str, object], code: str, message: str) -> FactRelationGap:
    return FactRelationGap(
        emperor=_text(row.get("emperor")),
        rule_code=_text(row.get("rule_code")),
        code=code,
        object_name=_text(row.get("scored_obj_name")),
        object_type=_text(row.get("scored_obj_type")),
        obj_src_id=_int_or_none(row.get("scored_obj_src_id")),
        scoring_role=_text(row.get("scoring_role")),
        direction=_text(row.get("direction")),
        causal_chain_key=_text(row.get("causal_chain_key")),
        message=message,
    )


def _gap_message(reason: str) -> str:
    messages = {
        "missing_object": "承载单元缺少 subject object，无法生成事实关系候选。",
        "non_person": "事实关系候选要求具体 person，当前承载对象不是 person。",
        "no_catalog": "当前 rule/scoring_role/object_type 没有 predicate catalog 映射。",
        "direction_mismatch": "承载方向与 predicate catalog 方向不匹配。",
        "missing_relation": "可生成事实关系候选，但 fact_relations 尚无对应 active 记录。",
    }
    return messages.get(reason, "无法生成事实关系候选。")


def collect_gaps(
    rows: Sequence[Mapping[str, object]],
    options: Mapping[tuple[str, str, str], object],
    *,
    relation_exists: RelationExists | None = None,
) -> list[FactRelationGap]:
    gaps: list[FactRelationGap] = []
    for row in rows:
        candidate, reason = relation_candidate(row, options)
        if candidate is None:
            gaps.append(_gap(row, reason, _gap_message(reason)))
            continue
        if relation_exists is not None and not relation_exists(candidate):
            gaps.append(_gap(row, "missing_relation", _gap_message("missing_relation")))
    return gaps


def build_gap_summary(gaps: Sequence[FactRelationGap]) -> dict[str, object]:
    gap_rows = [asdict(gap) for gap in gaps]
    totals: dict[str, int] = {
        "total": len(gaps),
        "non_person": 0,
        "direction_mismatch": 0,
        "missing_object": 0,
        "no_catalog": 0,
        "missing_relation": 0,
    }
    for gap in gaps:
        totals[gap.code] = totals.get(gap.code, 0) + 1
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "totals": totals,
        "gaps": gap_rows,
    }


def relation_exists_in_db(cur: psycopg.Cursor, values: Mapping[str, object]) -> bool:
    cur.execute(
        """
        select 1
          from fact_relations
         where status = 'active'
           and emp_id = %s
           and coalesce(item_id, 0) = coalesce(%s, 0)
           and coalesce(rule_id, 0) = coalesce(%s, 0)
           and subject_obj_id = %s
           and predicate = %s
           and coalesce(object_obj_id, 0) = coalesce(%s, 0)
           and coalesce(obj_src_id, 0) = coalesce(%s, 0)
           and causal_chain_key = %s
         limit 1
        """,
        (
            values["emp_id"],
            values["item_id"],
            values["rule_id"],
            values["subject_obj_id"],
            values["predicate"],
            values["object_obj_id"],
            values["obj_src_id"],
            values["causal_chain_key"],
        ),
    )
    return cur.fetchone() is not None


def build_gap_summary_from_db(
    *,
    dsn: str,
    item_code: str,
    emperors: Sequence[str],
    rule_codes: Sequence[str],
) -> dict[str, object]:
    if not emperors:
        raise FactRelationGapSummaryError("no emperors selected")
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            rows = fetch_unit_rows(cur=cur, item_code=item_code, emperors=emperors, rule_codes=rule_codes)
            options = fetch_relation_options(cur=cur, item_code=item_code, rule_codes=rule_codes)
            gaps = collect_gaps(rows, options, relation_exists=lambda values: relation_exists_in_db(cur, values))
    return build_gap_summary(gaps)


def render_markdown(summary: Mapping[str, object]) -> str:
    totals = summary.get("totals") if isinstance(summary.get("totals"), Mapping) else {}
    gaps = summary.get("gaps") if isinstance(summary.get("gaps"), list) else []
    lines = [
        "# I5B fact relation gap summary",
        "",
        f"- generated_at: `{summary.get('generated_at') or ''}`",
        f"- total: `{totals.get('total', 0)}`",
        f"- non_person: `{totals.get('non_person', 0)}`",
        f"- direction_mismatch: `{totals.get('direction_mismatch', 0)}`",
        f"- missing_object: `{totals.get('missing_object', 0)}`",
        f"- no_catalog: `{totals.get('no_catalog', 0)}`",
        f"- missing_relation: `{totals.get('missing_relation', 0)}`",
        "",
        "## Gap 明细",
        "",
    ]
    if not gaps:
        lines.append("无。")
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            "| 皇帝 | rule | code | object | type | obj_src | role | direction | chain | message |",
            "| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- |",
        ]
    )
    for gap in gaps:
        if not isinstance(gap, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _text(gap.get("emperor")),
                    _text(gap.get("rule_code")),
                    _text(gap.get("code")),
                    _text(gap.get("object_name")),
                    _text(gap.get("object_type")),
                    str(gap.get("obj_src_id") or ""),
                    _text(gap.get("scoring_role")),
                    _text(gap.get("direction")),
                    _text(gap.get("causal_chain_key")),
                    _text(gap.get("message")),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_output(text: str, output: Path | None) -> None:
    if output is None:
        sys.stdout.write(text)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize I5B fact relation gaps from rule evidence units.")
    parser.add_argument("--emperor", action="append", default=[], help="Emperor name; repeatable.")
    parser.add_argument("--all-emperors", action="store_true", help="Summarize all emperors with selected units.")
    parser.add_argument("--rule-code", action="append", default=[], help="Limit to one I5B rule_code; repeatable.")
    parser.add_argument("--all-rules", action="store_true", help="Use all active I5B predicate options.")
    parser.add_argument("--item-code", default=DEFAULT_ITEM_CODE)
    parser.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    parser.add_argument("--dsn", help="PostgreSQL DSN; overrides --dsn-env.")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fail-on-gap", action="store_true")
    return parser.parse_args(argv)


def selected_emperors(args: argparse.Namespace, *, dsn: str, rule_codes: Sequence[str]) -> tuple[str, ...]:
    if args.all_emperors:
        return fetch_emperors_with_units(dsn=dsn, item_code=args.item_code, rule_codes=rule_codes)
    emperors = tuple(dict.fromkeys(args.emperor))
    if not emperors:
        raise FactRelationGapSummaryError("no emperors selected; use --emperor or --all-emperors")
    return emperors


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    dsn = args.dsn or resolve_dsn(args.dsn_env)
    rule_codes = resolve_rule_codes(args)
    emperors = selected_emperors(args, dsn=dsn, rule_codes=rule_codes)
    summary = build_gap_summary_from_db(
        dsn=dsn,
        item_code=args.item_code,
        emperors=emperors,
        rule_codes=rule_codes,
    )
    if args.format == "json":
        text = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    else:
        text = render_markdown(summary)
    write_output(text, args.output)
    totals = summary["totals"]
    gap_count = int(totals["total"]) if isinstance(totals, Mapping) else 0
    return 1 if args.fail_on_gap and gap_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
