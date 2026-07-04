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

from scripts.build.i5b_item_result_calculator import (  # noqa: E402
    DEFAULT_CLUSTER_FORMULA,
    DEFAULT_ITEM_CODE,
)
from scripts.dev.evidence_cluster_workbench import (  # noqa: E402
    DEFAULT_DSN_ENV,
    fetch_cluster_calc_detail_rows,
    fetch_materials,
    resolve_dsn,
)
from scripts.dev.i5b_rule_evidence_unit_candidate_builder import (  # noqa: E402
    build_candidate_payload,
)


SOURCE_METHOD = "candidate_from_calc_detail"
REVIEW_STATUS = "needs_review"
SCORE_MODE = "shadow"
LEGACY_CANDIDATE_REVIEW_NOTES = {
    "候选来自当前 calc_detail.materials；因果链默认按 obj_src 分开，需人工合并同链。",
    "候选来自当前 calc_detail.materials；需人工复核。",
}


class RuleEvidenceUnitDbSyncError(ValueError):
    pass


@dataclass(frozen=True)
class SyncStats:
    emperor: str
    units_seen: int = 0
    units_inserted: int = 0
    units_updated: int = 0
    units_retired: int = 0
    members_seen: int = 0
    members_inserted: int = 0
    members_updated: int = 0
    members_retired: int = 0
    supporting_unattached: int = 0
    preview_issues: int = 0
    preview_blocking: bool = False


def _text(value: object) -> str:
    return str(value or "").strip()


def _int_or_none(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _scored_obj(unit: Mapping[str, object]) -> Mapping[str, object]:
    value = unit.get("scored_obj")
    return value if isinstance(value, Mapping) else {}


def _iter_units(payload: Mapping[str, object]) -> list[Mapping[str, object]]:
    units = payload.get("units")
    if not isinstance(units, list):
        return []
    return [unit for unit in units if isinstance(unit, Mapping)]


def _iter_members(unit: Mapping[str, object]) -> list[Mapping[str, object]]:
    members = unit.get("members")
    if not isinstance(members, list):
        return []
    return [member for member in members if isinstance(member, Mapping)]


def _supporting_count(payload: Mapping[str, object]) -> int:
    members = payload.get("supporting_materials")
    return len(members) if isinstance(members, list) else 0


def _preview_stats(payload: Mapping[str, object]) -> tuple[int, bool]:
    preview = payload.get("preview")
    if not isinstance(preview, Mapping):
        return 0, False
    return _int_or_none(preview.get("issue_count")) or 0, bool(preview.get("has_blocking_issue"))


def fetch_emperors_with_calc_details(
    *,
    dsn: str,
    item_code: str = DEFAULT_ITEM_CODE,
    cluster_formula: str = DEFAULT_CLUSTER_FORMULA,
    rule_codes: Sequence[str] = (),
) -> tuple[str, ...]:
    clauses = ["i.item_code = %s", "c.formula_code = %s", "d.formula_code = %s"]
    params: list[Any] = [item_code, cluster_formula, cluster_formula]
    rule_filter = {rule_code for rule_code in rule_codes if rule_code}
    if rule_filter:
        clauses.append("r.rule_code = any(%s)")
        params.append(sorted(rule_filter))
    where_sql = " and ".join(clauses)
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                select distinct e.id, e.name
                  from evd_clusters c
                  join evd_cluster_calc_details d on d.cluster_id = c.id
                  join emps e on e.id = c.emp_id
                  join eval_items i on i.id = c.item_id
                  join eval_rules r on r.id = c.rule_id
                 where {where_sql}
                 order by e.id
                """,
                tuple(params),
            )
            return tuple(str(row[1]) for row in cur.fetchall())


def build_payloads(
    *,
    dsn: str,
    emperors: Sequence[str],
    item_code: str = DEFAULT_ITEM_CODE,
    cluster_formula: str = DEFAULT_CLUSTER_FORMULA,
    rule_codes: Sequence[str] = (),
) -> list[dict[str, object]]:
    emperor_filter = tuple(dict.fromkeys(emperor for emperor in emperors if emperor))
    if not emperor_filter:
        raise RuleEvidenceUnitDbSyncError("no emperors selected")
    rules = tuple(rule_code for rule_code in rule_codes if rule_code)
    cluster_rows = fetch_cluster_calc_detail_rows(
        dsn=dsn,
        item_code=item_code,
        formula_code=cluster_formula,
        emperors=emperor_filter,
        rule_codes=rules,
    )
    payloads: list[dict[str, object]] = []
    for emperor in emperor_filter:
        materials_report = fetch_materials(
            dsn=dsn,
            emperor=emperor,
            item_code=item_code,
            rule_code=None,
        )
        payloads.append(
            build_candidate_payload(
                emperor=emperor,
                item_code=item_code,
                cluster_formula=cluster_formula,
                cluster_rows=cluster_rows,
                materials_report=materials_report,
                rule_codes=rules,
            )
        )
    return payloads


def _fetch_one_id(cur: psycopg.Cursor, sql: str, params: tuple[object, ...], missing_message: str) -> int:
    cur.execute(sql, params)
    row = cur.fetchone()
    if row is None:
        raise RuleEvidenceUnitDbSyncError(missing_message)
    return int(row[0])


def _resolve_ids(
    cur: psycopg.Cursor,
    *,
    emperor: str,
    item_code: str,
    rule_codes: Sequence[str],
) -> tuple[int, int, dict[str, int]]:
    emp_id = _fetch_one_id(cur, "select id from emps where name = %s", (emperor,), f"emps missing: {emperor}")
    item_id = _fetch_one_id(
        cur,
        "select id from eval_items where item_code = %s",
        (item_code,),
        f"eval_items missing item_code: {item_code}",
    )
    rule_filter = tuple(sorted({rule_code for rule_code in rule_codes if rule_code}))
    if not rule_filter:
        return emp_id, item_id, {}
    cur.execute(
        "select rule_code, id from eval_rules where item_id = %s and rule_code = any(%s)",
        (item_id, list(rule_filter)),
    )
    rule_ids = {str(rule_code): int(rule_id) for rule_code, rule_id in cur.fetchall()}
    missing = sorted(set(rule_filter) - set(rule_ids))
    if missing:
        raise RuleEvidenceUnitDbSyncError(f"eval_rules missing rule_code(s): {', '.join(missing)}")
    return emp_id, item_id, rule_ids


def unit_db_values(
    *,
    unit: Mapping[str, object],
    emp_id: int,
    item_id: int,
    rule_id: int,
    item_code: str,
) -> dict[str, object]:
    scored_obj = _scored_obj(unit)
    scoring_role = _text(unit.get("scoring_role"))
    rule_code = _text(unit.get("rule_code"))
    source_method = _text(unit.get("source_method")) or SOURCE_METHOD
    review_status = _text(unit.get("review_status")) or REVIEW_STATUS
    review_note = _text(unit.get("review_note"))
    note = _text(unit.get("note"))
    if source_method == SOURCE_METHOD and review_status == REVIEW_STATUS:
        if review_note in LEGACY_CANDIDATE_REVIEW_NOTES:
            review_note = ""
        if note.startswith("候选承载对象："):
            note = ""
    return {
        "emp_id": emp_id,
        "item_id": item_id,
        "item_code": item_code,
        "rule_id": rule_id,
        "rule_code": rule_code,
        "causal_chain_key": _text(unit.get("causal_chain_key")),
        "scored_obj_id": _int_or_none(scored_obj.get("obj_id")),
        "scored_obj_src_id": _int_or_none(scored_obj.get("obj_src_id")),
        "scoring_role": scoring_role,
        "direction": _text(unit.get("direction")) or "mixed",
        "score_mode": _text(unit.get("score_mode")) or SCORE_MODE,
        "source_method": source_method,
        "review_status": review_status,
        "review_note": review_note,
        "note": note,
        "status": "active",
    }


def member_db_values(*, member: Mapping[str, object], unit_id: int) -> dict[str, object]:
    member_role = _text(member.get("role") or member.get("member_role") or "source_context")
    source_method = _text(member.get("source_method")) or SOURCE_METHOD
    review_status = _text(member.get("review_status")) or REVIEW_STATUS
    review_note = _text(member.get("review_note"))
    note = _text(member.get("note"))
    if source_method == SOURCE_METHOD and review_status == REVIEW_STATUS:
        if review_note in LEGACY_CANDIDATE_REVIEW_NOTES:
            review_note = ""
        if note.startswith("候选上下文成员："):
            note = ""
    return {
        "unit_id": unit_id,
        "obj_id": _int_or_none(member.get("obj_id")),
        "obj_src_id": _int_or_none(member.get("obj_src_id")),
        "relation_id": _int_or_none(member.get("relation_id")),
        "member_role": member_role,
        "source_method": source_method,
        "review_status": review_status,
        "review_note": review_note,
        "note": note,
        "status": "active",
    }


def _find_unit(cur: psycopg.Cursor, values: Mapping[str, object]) -> int | None:
    cur.execute(
        """
        select id
          from rule_evidence_units
         where status = 'active'
           and emp_id = %s
           and item_id = %s
           and rule_id = %s
           and causal_chain_key = %s
           and scoring_role = %s
           and coalesce(scored_obj_id, 0) = coalesce(%s, 0)
           and coalesce(scored_obj_src_id, 0) = coalesce(%s, 0)
         order by id
         limit 1
        """,
        (
            values["emp_id"],
            values["item_id"],
            values["rule_id"],
            values["causal_chain_key"],
            values["scoring_role"],
            values["scored_obj_id"],
            values["scored_obj_src_id"],
        ),
    )
    row = cur.fetchone()
    return int(row[0]) if row else None


def _insert_unit(cur: psycopg.Cursor, values: Mapping[str, object]) -> int:
    columns = tuple(values)
    placeholders = ", ".join(["%s"] * len(columns))
    cur.execute(
        f"""
        insert into rule_evidence_units ({", ".join(columns)})
        values ({placeholders})
        returning id
        """,
        tuple(values[column] for column in columns),
    )
    row = cur.fetchone()
    if row is None:
        raise RuleEvidenceUnitDbSyncError("failed to insert rule_evidence_units row")
    return int(row[0])


def _update_unit(cur: psycopg.Cursor, unit_id: int, values: Mapping[str, object]) -> None:
    cur.execute(
        """
        update rule_evidence_units
           set item_code = %s,
               rule_code = %s,
               direction = %s,
               score_mode = case
                   when source_method = %s::public.eval_source_method
                    and review_status = %s::public.eval_review_status
                    and score_mode = %s::public.rule_evidence_score_mode
                   then %s::public.rule_evidence_score_mode
                   else score_mode
               end,
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
            values["direction"],
            SOURCE_METHOD,
            REVIEW_STATUS,
            SCORE_MODE,
            values["score_mode"],
            SOURCE_METHOD,
            REVIEW_STATUS,
            values["source_method"],
            SOURCE_METHOD,
            REVIEW_STATUS,
            values["review_status"],
            unit_id,
        ),
    )


def _find_member(cur: psycopg.Cursor, values: Mapping[str, object]) -> int | None:
    cur.execute(
        """
        select id
          from rule_evidence_unit_members
         where status = 'active'
           and unit_id = %s
           and member_role = %s
           and coalesce(obj_id, 0) = coalesce(%s, 0)
           and coalesce(obj_src_id, 0) = coalesce(%s, 0)
           and coalesce(relation_id, 0) = coalesce(%s, 0)
         order by id
         limit 1
        """,
        (
            values["unit_id"],
            values["member_role"],
            values["obj_id"],
            values["obj_src_id"],
            values["relation_id"],
        ),
    )
    row = cur.fetchone()
    return int(row[0]) if row else None


def _insert_member(cur: psycopg.Cursor, values: Mapping[str, object]) -> int:
    columns = tuple(values)
    placeholders = ", ".join(["%s"] * len(columns))
    cur.execute(
        f"""
        insert into rule_evidence_unit_members ({", ".join(columns)})
        values ({placeholders})
        returning id
        """,
        tuple(values[column] for column in columns),
    )
    row = cur.fetchone()
    if row is None:
        raise RuleEvidenceUnitDbSyncError("failed to insert rule_evidence_unit_members row")
    return int(row[0])


def _update_member(cur: psycopg.Cursor, member_id: int, values: Mapping[str, object]) -> None:
    cur.execute(
        """
        update rule_evidence_unit_members
           set source_method = case
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
            SOURCE_METHOD,
            REVIEW_STATUS,
            values["source_method"],
            SOURCE_METHOD,
            REVIEW_STATUS,
            values["review_status"],
            member_id,
        ),
    )


def _retire_stale_candidate_units(
    cur: psycopg.Cursor,
    *,
    emp_id: int,
    item_id: int,
    rule_ids: Mapping[str, int],
    active_unit_ids: Sequence[int],
) -> tuple[int, int]:
    if not rule_ids:
        return 0, 0
    cur.execute(
        """
        update rule_evidence_units
           set status = 'retired',
               updated_at = now()
         where status = 'active'
           and source_method = %s::public.eval_source_method
           and review_status = %s::public.eval_review_status
           and emp_id = %s
           and item_id = %s
           and rule_id = any(%s)
           and not (id = any(%s))
        returning id
        """,
        (SOURCE_METHOD, REVIEW_STATUS, emp_id, item_id, list(rule_ids.values()), list(active_unit_ids)),
    )
    retired_unit_ids = [int(row[0]) for row in cur.fetchall()]
    if not retired_unit_ids:
        return 0, 0
    cur.execute(
        """
        update rule_evidence_unit_members
           set status = 'retired',
               updated_at = now()
         where status = 'active'
           and source_method = %s::public.eval_source_method
           and review_status = %s::public.eval_review_status
           and unit_id = any(%s)
        returning id
        """,
        (SOURCE_METHOD, REVIEW_STATUS, retired_unit_ids),
    )
    retired_member_count = len(cur.fetchall())
    return len(retired_unit_ids), retired_member_count


def sync_payload(
    *,
    cur: psycopg.Cursor,
    payload: Mapping[str, object],
    dry_run: bool = False,
) -> SyncStats:
    emperor = _text(payload.get("emperor"))
    item_code = _text(payload.get("item_code")) or DEFAULT_ITEM_CODE
    units = _iter_units(payload)
    rule_codes = tuple(_text(unit.get("rule_code")) for unit in units if _text(unit.get("rule_code")))
    preview_issues, preview_blocking = _preview_stats(payload)

    if dry_run:
        return SyncStats(
            emperor=emperor,
            units_seen=len(units),
            members_seen=sum(len(_iter_members(unit)) for unit in units),
            supporting_unattached=_supporting_count(payload),
            preview_issues=preview_issues,
            preview_blocking=preview_blocking,
        )

    emp_id, item_id, rule_ids = _resolve_ids(cur, emperor=emperor, item_code=item_code, rule_codes=rule_codes)
    inserted_units = updated_units = inserted_members = updated_members = 0
    members_seen = 0
    active_unit_ids: list[int] = []
    for unit in units:
        rule_code = _text(unit.get("rule_code"))
        values = unit_db_values(
            unit=unit,
            emp_id=emp_id,
            item_id=item_id,
            rule_id=rule_ids[rule_code],
            item_code=item_code,
        )
        unit_id = _find_unit(cur, values)
        if unit_id is None:
            unit_id = _insert_unit(cur, values)
            inserted_units += 1
        else:
            _update_unit(cur, unit_id, values)
            updated_units += 1
        active_unit_ids.append(unit_id)

        for member in _iter_members(unit):
            members_seen += 1
            member_values = member_db_values(member=member, unit_id=unit_id)
            member_id = _find_member(cur, member_values)
            if member_id is None:
                _insert_member(cur, member_values)
                inserted_members += 1
            else:
                _update_member(cur, member_id, member_values)
                updated_members += 1
    retired_units, retired_members = _retire_stale_candidate_units(
        cur,
        emp_id=emp_id,
        item_id=item_id,
        rule_ids=rule_ids,
        active_unit_ids=active_unit_ids,
    )

    return SyncStats(
        emperor=emperor,
        units_seen=len(units),
        units_inserted=inserted_units,
        units_updated=updated_units,
        units_retired=retired_units,
        members_seen=members_seen,
        members_inserted=inserted_members,
        members_updated=updated_members,
        members_retired=retired_members,
        supporting_unattached=_supporting_count(payload),
        preview_issues=preview_issues,
        preview_blocking=preview_blocking,
    )


def sync_payloads(*, dsn: str, payloads: Sequence[Mapping[str, object]], dry_run: bool = False) -> list[SyncStats]:
    if dry_run:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                return [sync_payload(cur=cur, payload=payload, dry_run=True) for payload in payloads]
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            stats = [sync_payload(cur=cur, payload=payload, dry_run=False) for payload in payloads]
        conn.commit()
    return stats


def render_markdown(stats: Sequence[SyncStats], *, dry_run: bool) -> str:
    lines = [
        "# I5B 规则证据单元影子表同步",
        "",
        f"- generated_at: `{datetime.now().astimezone().isoformat(timespec='seconds')}`",
        f"- dry_run: `{str(dry_run).lower()}`",
        "",
        "| 皇帝 | units | unit新增 | unit更新 | unit退役 | members | member新增 | member更新 | member退役 | 未挂支撑 | 预览问题 | 阻塞 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in stats:
        lines.append(
            "| "
            + " | ".join(
                [
                    row.emperor,
                    str(row.units_seen),
                    str(row.units_inserted),
                    str(row.units_updated),
                    str(row.units_retired),
                    str(row.members_seen),
                    str(row.members_inserted),
                    str(row.members_updated),
                    str(row.members_retired),
                    str(row.supporting_unattached),
                    str(row.preview_issues),
                    "是" if row.preview_blocking else "否",
                ]
            )
            + " |"
        )
    totals = {
        "units_seen": sum(row.units_seen for row in stats),
        "units_inserted": sum(row.units_inserted for row in stats),
        "units_updated": sum(row.units_updated for row in stats),
        "units_retired": sum(row.units_retired for row in stats),
        "members_seen": sum(row.members_seen for row in stats),
        "members_inserted": sum(row.members_inserted for row in stats),
        "members_updated": sum(row.members_updated for row in stats),
        "members_retired": sum(row.members_retired for row in stats),
        "supporting_unattached": sum(row.supporting_unattached for row in stats),
        "preview_issues": sum(row.preview_issues for row in stats),
        "preview_blocking": sum(1 for row in stats if row.preview_blocking),
    }
    lines.extend(
        [
            "",
            "## 汇总",
            "",
            f"- units_seen: `{totals['units_seen']}`",
            f"- units_inserted: `{totals['units_inserted']}`",
            f"- units_updated: `{totals['units_updated']}`",
            f"- units_retired: `{totals['units_retired']}`",
            f"- members_seen: `{totals['members_seen']}`",
            f"- members_inserted: `{totals['members_inserted']}`",
            f"- members_updated: `{totals['members_updated']}`",
            f"- members_retired: `{totals['members_retired']}`",
            f"- supporting_unattached: `{totals['supporting_unattached']}`",
            f"- preview_issues: `{totals['preview_issues']}`",
            f"- preview_blocking_emperors: `{totals['preview_blocking']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def _json_stats(stats: Sequence[SyncStats], *, dry_run: bool) -> dict[str, object]:
    rows = [asdict(row) for row in stats]
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "dry_run": dry_run,
        "stats": rows,
        "totals": {
            "units_seen": sum(row.units_seen for row in stats),
            "units_inserted": sum(row.units_inserted for row in stats),
            "units_updated": sum(row.units_updated for row in stats),
            "units_retired": sum(row.units_retired for row in stats),
            "members_seen": sum(row.members_seen for row in stats),
            "members_inserted": sum(row.members_inserted for row in stats),
            "members_updated": sum(row.members_updated for row in stats),
            "members_retired": sum(row.members_retired for row in stats),
            "supporting_unattached": sum(row.supporting_unattached for row in stats),
            "preview_issues": sum(row.preview_issues for row in stats),
            "preview_blocking_emperors": sum(1 for row in stats if row.preview_blocking),
        },
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync I5B rule evidence unit candidates into shadow PostgreSQL tables.")
    parser.add_argument("--emperor", action="append", default=[], help="Emperor name; repeatable.")
    parser.add_argument("--all-emperors", action="store_true", help="Sync all emperors with current I5B calc details.")
    parser.add_argument("--rule-code", action="append", default=[], help="Limit to one I5B rule_code; repeatable.")
    parser.add_argument("--item-code", default=DEFAULT_ITEM_CODE)
    parser.add_argument("--cluster-formula", default=DEFAULT_CLUSTER_FORMULA)
    parser.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    parser.add_argument("--dsn", help="PostgreSQL DSN; overrides --dsn-env.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    dsn = args.dsn or resolve_dsn(args.dsn_env)
    if args.all_emperors:
        emperors = fetch_emperors_with_calc_details(
            dsn=dsn,
            item_code=args.item_code,
            cluster_formula=args.cluster_formula,
            rule_codes=tuple(args.rule_code),
        )
    else:
        emperors = tuple(dict.fromkeys(args.emperor))
    payloads = build_payloads(
        dsn=dsn,
        emperors=emperors,
        item_code=args.item_code,
        cluster_formula=args.cluster_formula,
        rule_codes=tuple(args.rule_code),
    )
    stats = sync_payloads(dsn=dsn, payloads=payloads, dry_run=args.dry_run)
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
