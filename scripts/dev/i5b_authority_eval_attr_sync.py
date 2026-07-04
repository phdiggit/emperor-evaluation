from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

import psycopg

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.evidence_cluster_workbench import resolve_dsn
from scripts.dev.i5b_authority_eval_handoff import DEFAULT_WORK_ROOT, JsonlRow, load_batches
from scripts.dev.i5b_finite_values import (
    CANONICAL_TALENT_QUALITY_VALUES,
    NEGATIVE_TALENT_QUALITY_VALUES,
    TALENT_PROFILE_NOTE_ATTR,
    TALENT_QUALITY_ATTR,
    require_talent_quality,
    talent_quality_polarity,
    talent_quality_rank,
)


DEFAULT_OUTPUT = Path("tmp/i5b-authority-eval-work/review/authority_eval_attr_sync_report.json")
SYNC_ATTR_CODES = {TALENT_QUALITY_ATTR, TALENT_PROFILE_NOTE_ATTR}
TALENT_QUALITY_PROPOSAL_FIELD = f"{TALENT_QUALITY_ATTR}_proposal"
TALENT_QUALITY_BASIS_FIELD = f"{TALENT_QUALITY_ATTR}_basis"
CANONICAL_SYNC_TALENT_QUALITY_VALUES = set(CANONICAL_TALENT_QUALITY_VALUES)
CONFIDENCE_VALUES = {"high": 0.95, "medium": 0.82, "low": 0.68}


class AuthorityEvalAttrSyncError(ValueError):
    pass


def _text(value: object) -> str:
    return str(value or "").strip()


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def sync_talent_quality_rank(value: object) -> int | None:
    text = _text(value)
    rank = talent_quality_rank(text)
    if rank is not None:
        return rank
    if text in NEGATIVE_TALENT_QUALITY_VALUES:
        return -(NEGATIVE_TALENT_QUALITY_VALUES.index(text) + 1)
    return None


def require_sync_talent_quality_rank(value: object) -> int:
    rank = sync_talent_quality_rank(value)
    if rank is None:
        raise AuthorityEvalAttrSyncError(f"unsupported talent_quality_proposal: {_text(value)}")
    return rank


def is_canonical_sync_talent_quality(value: object) -> bool:
    text = _text(value)
    return text in CANONICAL_SYNC_TALENT_QUALITY_VALUES and sync_talent_quality_rank(text) is not None


def talent_quality_choice_key(value: object) -> tuple[int, int, int, str]:
    text = _text(value)
    rank = require_sync_talent_quality_rank(text)
    canonical_priority = 1 if text in CANONICAL_SYNC_TALENT_QUALITY_VALUES else 0
    return (abs(rank), canonical_priority, rank, text)


def stable_source_key(*, obj_id: int, source_ref: str) -> str:
    del obj_id
    digest = hashlib.sha1(source_ref.encode("utf-8")).hexdigest()[:12]
    return f"AUTH-EVAL-{digest}"


def source_row_for_candidate(candidate: Mapping[str, Any]) -> dict[str, str]:
    sources = [source for source in _list(candidate.get("authority_eval_sources")) if isinstance(source, Mapping)]
    if sources:
        source = sources[0]
        source_ref = _text(source.get("source_ref") or source.get("source_key") or "authority-eval")
        source_key = _text(source.get("source_key")) or stable_source_key(
            obj_id=int(candidate["obj_id"]),
            source_ref=source_ref,
        )
        note = _text(source.get("evaluation_note")) or "authority-eval talent-quality source"
    else:
        source_ref = "authority-eval"
        source_key = stable_source_key(obj_id=int(candidate["obj_id"]), source_ref=source_ref)
        note = "authority-eval talent-quality source"
    return {
        "src_key": source_key,
        "title": source_ref,
        "author": "",
        "dynasty": "",
        "volume": "",
        "locator": source_ref,
        "url": "",
        "note": note,
    }


def talent_quality_note(candidate: Mapping[str, Any]) -> str:
    summary = _text(candidate.get("authority_eval_summary"))
    limitations = _text(candidate.get("authority_eval_limitations") or candidate.get("limitations"))
    basis = _text(candidate.get(TALENT_QUALITY_BASIS_FIELD))
    parts = [part for part in (summary, limitations, f"basis={basis}" if basis else "") if part]
    return "；".join(parts)


def profile_note_attr_note(candidate: Mapping[str, Any]) -> str:
    return "复合人才画像提示；不直接入分，不改变 talent_quality_factor。"


def candidate_confidence(candidate: Mapping[str, Any]) -> float:
    return CONFIDENCE_VALUES.get(_text(candidate.get("confidence")), 0.82)


def load_sync_candidates(work_root: Path) -> list[JsonlRow]:
    rows = load_batches(work_root)
    return [
        row
        for row in rows
        if isinstance(row.row.get("obj_id"), int)
        and is_canonical_sync_talent_quality(row.row.get(TALENT_QUALITY_PROPOSAL_FIELD))
    ]


def choose_object_candidate(rows: list[JsonlRow]) -> dict[str, Any]:
    proposals = [_text(row.row.get(TALENT_QUALITY_PROPOSAL_FIELD)) for row in rows]
    unique = sorted(set(proposals), key=require_sync_talent_quality_rank)
    polarities = {talent_quality_polarity(value) for value in unique}
    if "unknown" in polarities:
        raise AuthorityEvalAttrSyncError(f"{rows[0].row.get('object_name')}: unsupported talent_quality_proposals: {unique}")
    if len(polarities) > 1:
        raise AuthorityEvalAttrSyncError(f"{rows[0].row.get('object_name')}: mixed positive/negative proposals: {unique}")
    chosen = max(unique, key=talent_quality_choice_key)
    chosen_rows = [row for row in rows if _text(row.row.get(TALENT_QUALITY_PROPOSAL_FIELD)) == chosen]
    chosen_rows.sort(key=lambda row: CONFIDENCE_VALUES.get(_text(row.row.get("confidence")), 0.0), reverse=True)
    candidate = dict(chosen_rows[0].row)
    candidate["_proposal_counts"] = dict(sorted(Counter(proposals).items()))
    candidate["_candidate_rows"] = [
        {
            "batch": row.batch,
            "line_no": row.line_no,
            "emperor": row.row.get("emperor"),
            "proposal": row.row.get(TALENT_QUALITY_PROPOSAL_FIELD),
            "confidence": row.row.get("confidence"),
        }
        for row in rows
    ]
    return candidate


def chosen_candidates(work_root: Path) -> list[dict[str, Any]]:
    grouped: dict[int, list[JsonlRow]] = defaultdict(list)
    for row in load_sync_candidates(work_root):
        grouped[int(row.row["obj_id"])].append(row)
    return [choose_object_candidate(rows) for _, rows in sorted(grouped.items())]


def fetch_raw_object(cur: psycopg.Cursor, obj_id: int) -> dict[str, Any]:
    cur.execute("select id, name, period from raw_objs where id = %s", (obj_id,))
    row = cur.fetchone()
    if row is None:
        raise AuthorityEvalAttrSyncError(f"raw_objs missing id={obj_id}")
    return {"id": int(row[0]), "name": row[1], "period": row[2]}


def upsert_source(cur: psycopg.Cursor, row: Mapping[str, str]) -> int:
    cur.execute(
        """
        select id
          from src_docs
         where title = %s
           and coalesce(volume, '') = %s
           and coalesce(locator, '') = %s
           and coalesce(url, '') = %s
         order by id
         limit 1
        """,
        (row["title"], row["volume"], row["locator"], row["url"]),
    )
    natural = cur.fetchone()
    if natural is not None:
        cur.execute(
            """
            update src_docs
               set note = %s,
                   updated_at = now()
             where id = %s
            returning id
            """,
            (row["note"], int(natural[0])),
        )
        return int(cur.fetchone()[0])
    cur.execute("select id from src_docs where src_key = %s", (row["src_key"],))
    existing = cur.fetchone()
    if existing is not None:
        cur.execute(
            """
            update src_docs
               set note = %s,
                   updated_at = now()
             where id = %s
            returning id
            """,
            (row["note"], int(existing[0])),
        )
        return int(cur.fetchone()[0])
    cur.execute(
        """
        insert into src_docs (src_key, title, author, dynasty, volume, locator, url, note)
        values (%s, %s, %s, %s, %s, %s, %s, %s)
        on conflict (src_key) do update set
            note = excluded.note,
            updated_at = now()
        returning id
        """,
        (
            row["src_key"],
            row["title"],
            row["author"],
            row["dynasty"],
            row["volume"],
            row["locator"],
            row["url"],
            row["note"],
        ),
    )
    return int(cur.fetchone()[0])


def latest_attr(cur: psycopg.Cursor, *, obj_id: int, attr_code: str) -> dict[str, Any] | None:
    cur.execute(
        """
        select id, value_text, confidence
          from obj_attrs
         where obj_id = %s
           and attr_code = %s
         order by updated_at desc, id desc
         limit 1
        """,
        (obj_id, attr_code),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return {"id": int(row[0]), "value_text": row[1], "confidence": float(row[2] or 0)}


def upsert_attr(
    cur: psycopg.Cursor,
    *,
    raw_object: Mapping[str, Any],
    attr_code: str,
    value_text: str,
    doc_id: int,
    confidence: float,
    note: str,
) -> dict[str, Any]:
    obj_id = int(raw_object["id"])
    existing = latest_attr(cur, obj_id=obj_id, attr_code=attr_code)
    if existing is None:
        cur.execute(
            """
            insert into obj_attrs (
                obj_id, attr_code, value_text, value_num, value_unit,
                period_start, period_end, region, doc_id, obj_src_id,
                confidence, note, obj_name
            )
            values (%s, %s, %s, null, '', null, null, %s, %s, null, %s, %s, %s)
            returning id
            """,
            (
                obj_id,
                attr_code,
                value_text,
                raw_object["period"],
                doc_id,
                confidence,
                note,
                raw_object["name"],
            ),
        )
        return {"action": "inserted", "attr_id": int(cur.fetchone()[0]), "old_value": ""}
    if _text(existing.get("value_text")) == value_text:
        return {"action": "unchanged", "attr_id": existing["id"], "old_value": existing.get("value_text") or ""}
    cur.execute(
        """
        update obj_attrs
           set value_text = %s,
               value_num = null,
               value_unit = '',
               region = %s,
               doc_id = %s,
               obj_src_id = null,
               confidence = %s,
               note = %s,
               obj_name = %s,
               updated_at = now()
         where id = %s
        returning id
        """,
        (
            value_text,
            raw_object["period"],
            doc_id,
            confidence,
            note,
            raw_object["name"],
            existing["id"],
        ),
    )
    return {"action": "updated", "attr_id": int(cur.fetchone()[0]), "old_value": existing.get("value_text") or ""}


def sync_candidate(cur: psycopg.Cursor, candidate: Mapping[str, Any]) -> dict[str, Any]:
    raw_object = fetch_raw_object(cur, int(candidate["obj_id"]))
    source_row = source_row_for_candidate(candidate)
    doc_id = upsert_source(cur, source_row)
    talent_quality = require_talent_quality(candidate.get(TALENT_QUALITY_PROPOSAL_FIELD), field_name=TALENT_QUALITY_PROPOSAL_FIELD)
    tq_result = upsert_attr(
        cur,
        raw_object=raw_object,
        attr_code=TALENT_QUALITY_ATTR,
        value_text=talent_quality,
        doc_id=doc_id,
        confidence=candidate_confidence(candidate),
        note=talent_quality_note(candidate),
    )
    profile_note = _text(candidate.get(TALENT_PROFILE_NOTE_ATTR))
    profile_result: dict[str, Any] | None = None
    if profile_note:
        profile_result = upsert_attr(
            cur,
            raw_object=raw_object,
            attr_code=TALENT_PROFILE_NOTE_ATTR,
            value_text=profile_note,
            doc_id=doc_id,
            confidence=candidate_confidence(candidate),
            note=profile_note_attr_note(candidate),
        )
    return {
        "obj_id": raw_object["id"],
        "object_name": raw_object["name"],
        "src_key": source_row["src_key"],
        TALENT_QUALITY_ATTR: talent_quality,
        "proposal_counts": candidate.get("_proposal_counts") or {},
        "talent_quality_result": tq_result,
        "talent_profile_note_result": profile_result,
    }


def sync_attrs(
    *,
    dsn: str,
    work_root: Path,
    dry_run: bool,
) -> dict[str, Any]:
    candidates = chosen_candidates(work_root)
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            rows = [sync_candidate(cur, candidate) for candidate in candidates]
        if dry_run:
            conn.rollback()
        else:
            conn.commit()
    return {
        "dry_run": dry_run,
        "candidate_obj_count": len(candidates),
        "talent_quality_actions": dict(sorted(Counter(row["talent_quality_result"]["action"] for row in rows).items())),
        "talent_quality_counts": dict(sorted(Counter(row[TALENT_QUALITY_ATTR] for row in rows).items())),
        "talent_profile_note_actions": dict(
            sorted(Counter((row["talent_profile_note_result"] or {"action": "none"})["action"] for row in rows).items())
        ),
        "rows": rows,
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# I5B authority-eval attr sync",
        "",
        f"- dry_run: {report['dry_run']}",
        f"- candidate_obj_count: {report['candidate_obj_count']}",
        f"- talent_quality_actions: {json.dumps(report['talent_quality_actions'], ensure_ascii=False, sort_keys=True)}",
        f"- talent_profile_note_actions: {json.dumps(report['talent_profile_note_actions'], ensure_ascii=False, sort_keys=True)}",
        "",
        "| action | object | old | new | profile_note |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in report["rows"]:
        tq = row["talent_quality_result"]
        note_action = (row["talent_profile_note_result"] or {"action": ""})["action"]
        if tq["action"] == "unchanged" and not note_action:
            continue
        lines.append(
            f"| `{tq['action']}` | {row['object_name']}({row['obj_id']}) | "
            f"{tq.get('old_value') or ''} | {row[TALENT_QUALITY_ATTR]} | {note_action} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_outputs(report: Mapping[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync reviewed I5B authority-eval talent attributes into obj_attrs.")
    parser.add_argument("--work-root", type=Path, default=DEFAULT_WORK_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dsn-env", default="EMPEROR_EVAL_PG_DSN")
    parser.add_argument("--write", action="store_true", help="Commit obj_attrs/src_docs changes. Default is dry-run rollback.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    dry_run = not args.write
    if args.write and os.environ.get("I5B_OBJECT_POOL_IMPORT_UNFREEZE") != "1":
        parser.error("attr sync frozen; set I5B_OBJECT_POOL_IMPORT_UNFREEZE=1 to write")
    report = sync_attrs(dsn=resolve_dsn(args.dsn_env), work_root=args.work_root, dry_run=dry_run)
    write_outputs(report, args.output)
    print(json.dumps({key: report[key] for key in report if key != "rows"}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
