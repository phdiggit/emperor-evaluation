from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import psycopg


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build.i5b_item_result_calculator import DEFAULT_ITEM_CODE  # noqa: E402
from scripts.dev.evidence_cluster_workbench import DEFAULT_DSN_ENV, resolve_dsn  # noqa: E402


DEFAULT_RULE_CODES = ("anti_nepotism", "tolerate_talent")
SOURCE_METHOD = "candidate_from_calc_detail"
REVIEW_STATUS = "needs_review"


class FactRelationCandidateSyncError(ValueError):
    pass


@dataclass(frozen=True)
class RelationOption:
    rule_code: str
    scoring_role: str
    predicate: str
    relation_role: str
    subject_obj_type: str
    object_obj_type: str
    direction: str
    description: str


@dataclass(frozen=True)
class RelationSyncStats:
    emperor: str
    rule_code: str
    units_seen: int = 0
    person_units: int = 0
    relation_candidates: int = 0
    inserted: int = 0
    updated: int = 0
    skipped_non_person: int = 0
    skipped_missing_object: int = 0
    skipped_no_catalog: int = 0
    skipped_direction_mismatch: int = 0
    units_with_relation: int = 0
    units_without_relation: int = 0


def _text(value: object) -> str:
    return str(value or "").strip()


def _int_or_none(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def resolve_rule_codes(args: argparse.Namespace) -> tuple[str, ...]:
    if args.rule_code:
        return tuple(dict.fromkeys(rule for rule in args.rule_code if rule))
    if args.all_rules:
        return ()
    return DEFAULT_RULE_CODES


def fetch_emperors_with_units(
    *,
    dsn: str,
    item_code: str = DEFAULT_ITEM_CODE,
    rule_codes: Sequence[str] = (),
) -> tuple[str, ...]:
    clauses = ["reu.item_code = %s", "reu.status = 'active'"]
    params: list[Any] = [item_code]
    if rule_codes:
        clauses.append("reu.rule_code = any(%s)")
        params.append(list(rule_codes))
    where_sql = " and ".join(clauses)
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                select distinct e.id, e.name
                  from rule_evidence_units reu
                  join emps e on e.id = reu.emp_id
                 where {where_sql}
                 order by e.id
                """,
                tuple(params),
            )
            return tuple(str(row[1]) for row in cur.fetchall())


def fetch_relation_options(
    *,
    cur: psycopg.Cursor,
    item_code: str,
    rule_codes: Sequence[str] = (),
) -> dict[tuple[str, str, str], RelationOption]:
    clauses = ["item_code = %s", "status = 'active'"]
    params: list[Any] = [item_code]
    if rule_codes:
        clauses.append("rule_code = any(%s)")
        params.append(list(rule_codes))
    cur.execute(
        f"""
        select
            rule_code,
            scoring_role,
            predicate,
            relation_role,
            subject_obj_type,
            object_obj_type,
            direction,
            description
          from fact_relation_predicate_options
         where {" and ".join(clauses)}
         order by rule_code, scoring_role, predicate
        """,
        tuple(params),
    )
    options: dict[tuple[str, str, str], RelationOption] = {}
    for row in cur.fetchall():
        option = RelationOption(
            rule_code=str(row[0]),
            scoring_role=str(row[1]),
            predicate=str(row[2]),
            relation_role=str(row[3]),
            subject_obj_type=str(row[4]),
            object_obj_type=str(row[5] or ""),
            direction=str(row[6]),
            description=str(row[7] or ""),
        )
        options[(option.rule_code, option.scoring_role, option.subject_obj_type)] = option
    return options


def fetch_unit_rows(
    *,
    cur: psycopg.Cursor,
    item_code: str,
    emperors: Sequence[str],
    rule_codes: Sequence[str] = (),
) -> list[dict[str, object]]:
    clauses = ["reu.item_code = %s", "reu.status = 'active'", "reu.score_mode <> 'rejected'"]
    params: list[Any] = [item_code]
    if emperors:
        clauses.append("e.name = any(%s)")
        params.append(list(emperors))
    if rule_codes:
        clauses.append("reu.rule_code = any(%s)")
        params.append(list(rule_codes))
    cur.execute(
        f"""
        select
            reu.id as unit_id,
            reu.emp_id,
            e.name as emperor,
            reu.item_id,
            reu.item_code,
            reu.rule_id,
            reu.rule_code,
            reu.causal_chain_key,
            reu.scored_obj_id,
            ro.name as scored_obj_name,
            ro.obj_type as scored_obj_type,
            reu.scored_obj_src_id,
            osrc.doc_id,
            reu.scoring_role,
            reu.direction
          from rule_evidence_units reu
          join emps e on e.id = reu.emp_id
          left join raw_objs ro on ro.id = reu.scored_obj_id
          left join obj_srcs osrc on osrc.id = reu.scored_obj_src_id
         where {" and ".join(clauses)}
         order by e.id, reu.rule_code, reu.id
        """,
        tuple(params),
    )
    columns = [desc.name for desc in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def relation_values(row: Mapping[str, object], option: RelationOption) -> dict[str, object]:
    rule_code = _text(row.get("rule_code"))
    return {
        "emp_id": int(row["emp_id"]),
        "item_id": _int_or_none(row.get("item_id")),
        "item_code": _text(row.get("item_code")) or DEFAULT_ITEM_CODE,
        "rule_id": _int_or_none(row.get("rule_id")),
        "rule_code": rule_code,
        "subject_obj_id": int(row["scored_obj_id"]),
        "predicate": option.predicate,
        "object_obj_id": None,
        "doc_id": _int_or_none(row.get("doc_id")),
        "obj_src_id": _int_or_none(row.get("scored_obj_src_id")),
        "causal_chain_key": _text(row.get("causal_chain_key")),
        "relation_role": option.relation_role,
        "confidence": "0.7000",
        "source_method": SOURCE_METHOD,
        "review_status": REVIEW_STATUS,
        "review_note": "",
        "note": "",
        "status": "active",
    }


def relation_candidate(row: Mapping[str, object], options: Mapping[tuple[str, str, str], RelationOption]) -> tuple[dict[str, object] | None, str]:
    obj_id = _int_or_none(row.get("scored_obj_id"))
    if obj_id is None:
        return None, "missing_object"
    obj_type = _text(row.get("scored_obj_type"))
    if obj_type != "person":
        return None, "non_person"
    key = (_text(row.get("rule_code")), _text(row.get("scoring_role")), obj_type)
    option = options.get(key)
    if option is None:
        return None, "no_catalog"
    direction = _text(row.get("direction"))
    if direction and direction != option.direction:
        return None, "direction_mismatch"
    return relation_values(row, option), ""


def _find_relation(cur: psycopg.Cursor, values: Mapping[str, object]) -> int | None:
    cur.execute(
        """
        select id
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
         order by id
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
    row = cur.fetchone()
    return int(row[0]) if row else None


def _insert_relation(cur: psycopg.Cursor, values: Mapping[str, object]) -> int:
    columns = tuple(values)
    placeholders = ", ".join(["%s"] * len(columns))
    cur.execute(
        f"""
        insert into fact_relations ({", ".join(columns)})
        values ({placeholders})
        returning id
        """,
        tuple(values[column] for column in columns),
    )
    row = cur.fetchone()
    if row is None:
        raise FactRelationCandidateSyncError("failed to insert fact_relations row")
    return int(row[0])


def _update_relation(cur: psycopg.Cursor, relation_id: int, values: Mapping[str, object]) -> None:
    cur.execute(
        """
        update fact_relations
           set item_code = %s,
               rule_code = %s,
               doc_id = %s,
               relation_role = %s,
               confidence = %s,
               source_method = case
                   when source_method = %s::public.eval_source_method
                    and review_status = %s::public.eval_review_status
                   then %s::public.eval_source_method
                   else source_method
               end,
               review_status = case
                   when source_method = %s::public.eval_source_method
                    and review_status = %s::public.eval_review_status
                   then %s::public.eval_review_status
                   else review_status
               end,
               updated_at = now()
         where id = %s
        """,
        (
            values["item_code"],
            values["rule_code"],
            values["doc_id"],
            values["relation_role"],
            values["confidence"],
            SOURCE_METHOD,
            REVIEW_STATUS,
            values["source_method"],
            SOURCE_METHOD,
            REVIEW_STATUS,
            values["review_status"],
            relation_id,
        ),
    )


def _bump(stats: dict[tuple[str, str], dict[str, int]], row: Mapping[str, object], key: str) -> None:
    bucket = stats.setdefault((_text(row.get("emperor")), _text(row.get("rule_code"))), {})
    bucket[key] = bucket.get(key, 0) + 1


def _stats_rows(stats: Mapping[tuple[str, str], Mapping[str, int]]) -> list[RelationSyncStats]:
    rows: list[RelationSyncStats] = []
    for (emperor, rule_code), values in sorted(stats.items()):
        rows.append(
            RelationSyncStats(
                emperor=emperor,
                rule_code=rule_code,
                units_seen=values.get("units_seen", 0),
                person_units=values.get("person_units", 0),
                relation_candidates=values.get("relation_candidates", 0),
                inserted=values.get("inserted", 0),
                updated=values.get("updated", 0),
                skipped_non_person=values.get("skipped_non_person", 0),
                skipped_missing_object=values.get("skipped_missing_object", 0),
                skipped_no_catalog=values.get("skipped_no_catalog", 0),
                skipped_direction_mismatch=values.get("skipped_direction_mismatch", 0),
                units_with_relation=values.get("units_with_relation", 0),
                units_without_relation=values.get("units_without_relation", 0),
            )
        )
    return rows


def audit_units_with_relations(
    *,
    cur: psycopg.Cursor,
    item_code: str,
    emperors: Sequence[str],
    rule_codes: Sequence[str],
) -> dict[tuple[str, str], dict[str, int]]:
    rows = fetch_unit_rows(cur=cur, item_code=item_code, emperors=emperors, rule_codes=rule_codes)
    options = fetch_relation_options(cur=cur, item_code=item_code, rule_codes=rule_codes)
    stats: dict[tuple[str, str], dict[str, int]] = {}
    for row in rows:
        candidate, reason = relation_candidate(row, options)
        if candidate is None:
            continue
        relation_id = _find_relation(cur, candidate)
        _bump(stats, row, "units_with_relation" if relation_id is not None else "units_without_relation")
    return stats


def sync_candidates(
    *,
    dsn: str,
    item_code: str,
    emperors: Sequence[str],
    rule_codes: Sequence[str],
    dry_run: bool = False,
) -> list[RelationSyncStats]:
    if not emperors:
        raise FactRelationCandidateSyncError("no emperors selected")
    stats: dict[tuple[str, str], dict[str, int]] = {}
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            options = fetch_relation_options(cur=cur, item_code=item_code, rule_codes=rule_codes)
            rows = fetch_unit_rows(cur=cur, item_code=item_code, emperors=emperors, rule_codes=rule_codes)
            for row in rows:
                _bump(stats, row, "units_seen")
                obj_type = _text(row.get("scored_obj_type"))
                if obj_type == "person":
                    _bump(stats, row, "person_units")
                candidate, reason = relation_candidate(row, options)
                if candidate is None:
                    _bump(stats, row, f"skipped_{reason}")
                    continue
                _bump(stats, row, "relation_candidates")
                if dry_run:
                    continue
                relation_id = _find_relation(cur, candidate)
                if relation_id is None:
                    _insert_relation(cur, candidate)
                    _bump(stats, row, "inserted")
                else:
                    _update_relation(cur, relation_id, candidate)
                    _bump(stats, row, "updated")
            if not dry_run:
                audit = audit_units_with_relations(cur=cur, item_code=item_code, emperors=emperors, rule_codes=rule_codes)
                for key, values in audit.items():
                    for field, value in values.items():
                        stats.setdefault(key, {})[field] = value
        if dry_run:
            conn.rollback()
        else:
            conn.commit()
    return _stats_rows(stats)


def render_markdown(stats: Sequence[RelationSyncStats], *, dry_run: bool) -> str:
    lines = [
        "# I5B 事实关系候选同步",
        "",
        f"- generated_at: `{datetime.now().astimezone().isoformat(timespec='seconds')}`",
        f"- dry_run: `{str(dry_run).lower()}`",
        "",
        "| 皇帝 | rule | units | person | candidates | 新增 | 更新 | 非人物跳过 | 无对象 | 无词表 | 方向不符 | 有关系 | 缺关系 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in stats:
        lines.append(
            "| "
            + " | ".join(
                [
                    row.emperor,
                    row.rule_code,
                    str(row.units_seen),
                    str(row.person_units),
                    str(row.relation_candidates),
                    str(row.inserted),
                    str(row.updated),
                    str(row.skipped_non_person),
                    str(row.skipped_missing_object),
                    str(row.skipped_no_catalog),
                    str(row.skipped_direction_mismatch),
                    str(row.units_with_relation),
                    str(row.units_without_relation),
                ]
            )
            + " |"
        )
    totals = {
        "units_seen": sum(row.units_seen for row in stats),
        "person_units": sum(row.person_units for row in stats),
        "relation_candidates": sum(row.relation_candidates for row in stats),
        "inserted": sum(row.inserted for row in stats),
        "updated": sum(row.updated for row in stats),
        "skipped_non_person": sum(row.skipped_non_person for row in stats),
        "skipped_missing_object": sum(row.skipped_missing_object for row in stats),
        "skipped_no_catalog": sum(row.skipped_no_catalog for row in stats),
        "skipped_direction_mismatch": sum(row.skipped_direction_mismatch for row in stats),
        "units_with_relation": sum(row.units_with_relation for row in stats),
        "units_without_relation": sum(row.units_without_relation for row in stats),
    }
    lines.extend(["", "## 汇总", ""])
    for key, value in totals.items():
        lines.append(f"- {key}: `{value}`")
    return "\n".join(lines) + "\n"


def _json_stats(stats: Sequence[RelationSyncStats], *, dry_run: bool) -> dict[str, object]:
    rows = [asdict(row) for row in stats]
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "dry_run": dry_run,
        "stats": rows,
        "totals": {
            "units_seen": sum(row.units_seen for row in stats),
            "person_units": sum(row.person_units for row in stats),
            "relation_candidates": sum(row.relation_candidates for row in stats),
            "inserted": sum(row.inserted for row in stats),
            "updated": sum(row.updated for row in stats),
            "skipped_non_person": sum(row.skipped_non_person for row in stats),
            "skipped_missing_object": sum(row.skipped_missing_object for row in stats),
            "skipped_no_catalog": sum(row.skipped_no_catalog for row in stats),
            "skipped_direction_mismatch": sum(row.skipped_direction_mismatch for row in stats),
            "units_with_relation": sum(row.units_with_relation for row in stats),
            "units_without_relation": sum(row.units_without_relation for row in stats),
        },
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync I5B fact relation candidates from rule evidence units.")
    parser.add_argument("--emperor", action="append", default=[], help="Emperor name; repeatable.")
    parser.add_argument("--all-emperors", action="store_true", help="Sync all emperors with selected rule evidence units.")
    parser.add_argument("--rule-code", action="append", default=[], help="Limit to one I5B rule_code; repeatable.")
    parser.add_argument("--all-rules", action="store_true", help="Use all active I5B predicate options instead of default high-risk rules.")
    parser.add_argument("--item-code", default=DEFAULT_ITEM_CODE)
    parser.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    parser.add_argument("--dsn", help="PostgreSQL DSN; overrides --dsn-env.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    dsn = args.dsn or resolve_dsn(args.dsn_env)
    rule_codes = resolve_rule_codes(args)
    if args.all_emperors:
        emperors = fetch_emperors_with_units(dsn=dsn, item_code=args.item_code, rule_codes=rule_codes)
    else:
        emperors = tuple(dict.fromkeys(args.emperor))
    stats = sync_candidates(
        dsn=dsn,
        item_code=args.item_code,
        emperors=emperors,
        rule_codes=rule_codes,
        dry_run=args.dry_run,
    )
    if args.format == "markdown":
        text = render_markdown(stats, dry_run=args.dry_run)
    else:
        text = json.dumps(_json_stats(stats, dry_run=args.dry_run), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
