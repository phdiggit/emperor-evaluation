from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v3_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v3_import_plan import ImportPlanError, json_param, stable_hash, write_json  # noqa: E402
from scripts.dev.retrieval_v3_intake_manifest import text  # noqa: E402


SOURCE = "retrieval_v3_person_profile_consumer"

GRADE_LABEL_TO_ENUM = {
    "历史级人才": "historic_talent",
    "顶级人才": "top_talent",
    "重要人才": "important_talent",
    "普通人才": "ordinary_talent",
    "佞臣": "sycophant",
    "大佞臣": "major_sycophant",
    "历史级佞臣": "historic_sycophant",
}
GRADE_ENUM_TO_LABEL = {value: key for key, value in GRADE_LABEL_TO_ENUM.items()}
TECHNICAL_EVALUATION_RE = re.compile(r"[A-Za-z0-9_#=]")
PROCESS_EVALUATION_MARKERS = (
    "旧库",
    "导入",
    "回填",
    "重复对象行",
    "审计",
    "候选",
    "本轮",
    "编码",
    "事实链",
    "只证明",
    "只确认",
    "只评价",
    "不替代",
    "不把",
    "不直接",
    "暂不",
    "另证",
    "另行",
    "另归",
    "需另",
    "需各自",
    "需拆分",
    "需补",
    "按具体事实",
    "提交",
)

NEW_PERSON_SQL = """
select
    id as object_id,
    object_code,
    object_identity_key,
    canonical_name,
    normalized_name,
    identity_status::text as identity_status
from retrieval_v3.objects
where object_type = 'person'
  and not exists (
      select 1
        from retrieval_v3.target_objects tob
       where tob.object_id = retrieval_v3.objects.id
         and tob.object_role = 'target_emperor'
  )
order by canonical_name, id
"""

OLD_TALENT_SQL = """
select
    ro.id as old_obj_id,
    ro.name as old_name,
    ro.obj_type as old_obj_type,
    oa.id as old_attr_id,
    oa.value_text as talent_quality_label,
    oa.note as old_attr_note,
    oa.confidence as old_confidence,
    a.alias_text,
    a.normalized_alias,
    a.alias_kind
from public.raw_objs ro
join public.obj_attrs oa on oa.obj_id = ro.id and oa.attr_code = 'talent_quality'
left join public.raw_obj_aliases a on a.obj_id = ro.id and coalesce(a.active, true)
where ro.obj_type = 'person'
order by ro.name, oa.confidence desc nulls last, oa.id
"""


def fetch_one_id(cur: Any) -> int:
    row = cur.fetchone()
    if not row or row.get("id") is None:
        raise ImportPlanError("expected statement to return id")
    return int(row["id"])


def profile_code(person: Mapping[str, Any]) -> str:
    return "PRF-" + stable_hash(["person_profile", text(person.get("object_code")) or person.get("object_id")], length=16)


def row_confidence(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def old_match_keys(row: Mapping[str, Any]) -> list[str]:
    keys: list[str] = []
    for key in [row.get("old_name"), row.get("alias_text"), row.get("normalized_alias")]:
        value = text(key)
        if value and value not in keys:
            keys.append(value)
    return keys


def build_old_talent_index(old_rows: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    for row in old_rows:
        grade = GRADE_LABEL_TO_ENUM.get(text(row.get("talent_quality_label")))
        normalized = {
            "old_obj_id": row.get("old_obj_id"),
            "old_name": text(row.get("old_name")),
            "old_attr_id": row.get("old_attr_id"),
            "talent_quality_label": text(row.get("talent_quality_label")),
            "talent_grade": grade,
            "old_attr_note": text(row.get("old_attr_note")),
            "old_confidence": row_confidence(row.get("old_confidence")),
            "alias_text": text(row.get("alias_text")),
            "normalized_alias": text(row.get("normalized_alias")),
            "alias_kind": text(row.get("alias_kind")),
        }
        for key in old_match_keys(row):
            index.setdefault(key, []).append(normalized)
    return index


def unique_matches(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, Any]] = set()
    unique: list[dict[str, Any]] = []
    for row in rows:
        key = (row.get("old_obj_id"), row.get("old_attr_id"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(dict(row))
    return unique


def person_match_keys(person: Mapping[str, Any]) -> list[str]:
    keys: list[str] = []
    for value in [person.get("canonical_name"), person.get("normalized_name")]:
        key = text(value)
        if key and key not in keys:
            keys.append(key)
    return keys


def match_old_talent(person: Mapping[str, Any], old_index: Mapping[str, Sequence[Mapping[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for key in person_match_keys(person):
        rows.extend(old_index.get(key, []))
    return unique_matches(rows)


def basis_for_match(person: Mapping[str, Any], grade: str, matches: Sequence[Mapping[str, Any]]) -> str:
    del grade
    notes = [
        clean_person_evaluation(text(match.get("old_attr_note")))
        for match in matches
        if text(match.get("old_attr_note"))
    ]
    evaluation = "；".join(note for note in dict.fromkeys(notes) if note)
    if not evaluation:
        return ""
    name = text(person.get("canonical_name")) or text(person.get("normalized_name"))
    if not name:
        return evaluation
    if evaluation.startswith(name):
        evaluation = evaluation[len(name):].lstrip("，,、：: ")
    return f"{name}，{evaluation}" if evaluation else f"{name}，"


def clean_person_evaluation(value: str) -> str:
    segments: list[str] = []
    for raw_segment in re.split(r"[。；;\n]+", value):
        segment = text(raw_segment).strip("。；; ")
        if not segment:
            continue
        if TECHNICAL_EVALUATION_RE.search(segment):
            continue
        if not re.search(r"[\u4e00-\u9fff]", segment):
            continue
        if any(marker in segment for marker in PROCESS_EVALUATION_MARKERS):
            continue
        segments.append(segment)
    return "；".join(dict.fromkeys(segments))


def payload_for(person: Mapping[str, Any], status: str, matches: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "source": SOURCE,
        "match_status": status,
        "match_keys": person_match_keys(person),
        "old_source": "public.raw_objs + public.obj_attrs(attr_code=talent_quality)",
        "old_matches": [
            {
                "old_obj_id": match.get("old_obj_id"),
                "old_name": match.get("old_name"),
                "old_attr_id": match.get("old_attr_id"),
                "talent_quality_label": match.get("talent_quality_label"),
                "talent_grade": match.get("talent_grade"),
                "old_confidence": match.get("old_confidence"),
                "alias_text": match.get("alias_text"),
                "normalized_alias": match.get("normalized_alias"),
                "alias_kind": match.get("alias_kind"),
            }
            for match in matches[:10]
        ],
    }


def profile_row_for(person: Mapping[str, Any], matches: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    grades = sorted({text(match.get("talent_grade")) for match in matches if text(match.get("talent_grade"))})
    unsupported = sorted(
        {
            text(match.get("talent_quality_label"))
            for match in matches
            if text(match.get("talent_quality_label")) and not text(match.get("talent_grade"))
        }
    )
    if not matches:
        status = "missing_old_talent_quality"
        grade = None
        review_status = "needs_review"
        basis = ""
    elif len(grades) == 1 and not unsupported:
        status = "matched_old_talent_quality"
        grade = grades[0]
        review_status = "accepted"
        basis = basis_for_match(person, grade, matches)
    elif unsupported:
        status = "unsupported_old_talent_quality"
        grade = None
        review_status = "needs_review"
        basis = ""
    else:
        status = "conflicting_old_talent_quality"
        grade = None
        review_status = "needs_review"
        basis = ""

    return {
        "person_profile_code": profile_code(person),
        "object_id": int(person.get("object_id")),
        "object_code": text(person.get("object_code")),
        "canonical_name": text(person.get("canonical_name")),
        "normalized_name": text(person.get("normalized_name")),
        "talent_grade": grade,
        "talent_quality_label": GRADE_ENUM_TO_LABEL.get(grade or "", ""),
        "talent_grade_basis": basis,
        "review_status": review_status,
        "match_status": status,
        "profile_payload": payload_for(person, status, matches),
    }


def build_profile_plan(person_rows: Sequence[Mapping[str, Any]], old_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    old_index = build_old_talent_index(old_rows)
    profile_rows = [profile_row_for(person, match_old_talent(person, old_index)) for person in person_rows]
    status_counts = Counter(row["match_status"] for row in profile_rows)
    review_counts = Counter(row["review_status"] for row in profile_rows)
    grade_counts = Counter(row["talent_grade"] or "ungraded" for row in profile_rows)
    return {
        "generated_by": "scripts/dev/retrieval_v3_person_profile_consumer.py",
        "mode": "dry_run_person_profile_consumer",
        "write_db": False,
        "executed": False,
        "ok": True,
        "totals": {
            "person_objects": len(person_rows),
            "profile_rows": len(profile_rows),
            "matched_old_talent_quality": status_counts.get("matched_old_talent_quality", 0),
            "missing_old_talent_quality": status_counts.get("missing_old_talent_quality", 0),
            "conflicting_old_talent_quality": status_counts.get("conflicting_old_talent_quality", 0),
            "unsupported_old_talent_quality": status_counts.get("unsupported_old_talent_quality", 0),
        },
        "status_counts": dict(sorted(status_counts.items())),
        "review_status_counts": dict(sorted(review_counts.items())),
        "talent_grade_counts": dict(sorted(grade_counts.items())),
        "operation_counts": {"retrieval_v3.person_profiles": len(profile_rows)},
        "review_needed": [
            {
                "object_id": row["object_id"],
                "canonical_name": row["canonical_name"],
                "normalized_name": row["normalized_name"],
                "match_status": row["match_status"],
            }
            for row in profile_rows
            if row["review_status"] == "needs_review"
        ],
        "profile_rows": profile_rows,
        "executed_counts": {},
    }


def fetch_new_person_rows(cur: Any) -> list[dict[str, Any]]:
    cur.execute(NEW_PERSON_SQL)
    return [dict(row) for row in cur.fetchall()]


def fetch_old_talent_rows(cur: Any) -> list[dict[str, Any]]:
    cur.execute(OLD_TALENT_SQL)
    return [dict(row) for row in cur.fetchall()]


def upsert_person_profile(cur: Any, row: Mapping[str, Any]) -> int:
    cur.execute(
        """
        insert into retrieval_v3.person_profiles (
            person_profile_code, object_id, talent_grade, talent_grade_basis,
            review_status, profile_payload
        )
        values (
            %s, %s, %s::retrieval_v3.rv3_person_talent_grade, %s,
            %s::retrieval_v3.rv3_review_status, %s::jsonb
        )
        on conflict on constraint rv3_person_profiles_object_uk do update set
            person_profile_code = excluded.person_profile_code,
            talent_grade = case
                when retrieval_v3.person_profiles.review_status = 'accepted'
                 and coalesce(retrieval_v3.person_profiles.profile_payload->>'source', '') <> %s
                 and retrieval_v3.person_profiles.talent_grade is not null
                    then retrieval_v3.person_profiles.talent_grade
                when excluded.talent_grade is null and retrieval_v3.person_profiles.talent_grade is not null
                    then retrieval_v3.person_profiles.talent_grade
                else excluded.talent_grade
            end,
            talent_grade_basis = case
                when retrieval_v3.person_profiles.review_status = 'accepted'
                 and coalesce(retrieval_v3.person_profiles.profile_payload->>'source', '') <> %s
                 and retrieval_v3.person_profiles.talent_grade is not null
                    then retrieval_v3.person_profiles.talent_grade_basis
                else excluded.talent_grade_basis
            end,
            review_status = case
                when retrieval_v3.person_profiles.review_status in ('rejected', 'retired')
                    then retrieval_v3.person_profiles.review_status
                when retrieval_v3.person_profiles.review_status = 'accepted'
                 and coalesce(retrieval_v3.person_profiles.profile_payload->>'source', '') <> %s
                 and retrieval_v3.person_profiles.talent_grade is not null
                    then retrieval_v3.person_profiles.review_status
                else excluded.review_status
            end,
            profile_payload = excluded.profile_payload,
            updated_at = now()
        returning id
        """,
        (
            text(row.get("person_profile_code")),
            int(row.get("object_id")),
            row.get("talent_grade"),
            text(row.get("talent_grade_basis")),
            text(row.get("review_status")),
            json_param(row.get("profile_payload") or {}),
            SOURCE,
            SOURCE,
            SOURCE,
        ),
    )
    return fetch_one_id(cur)


def execute_upserts(cur: Any, profile_rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in profile_rows:
        upsert_person_profile(cur, row)
        counts["retrieval_v3.person_profiles"] += 1
    return dict(sorted(counts.items()))


def execute_person_profile_consumer(
    *,
    env_file: Path | None,
    dsn_env: str,
    reference_dsn_env: str,
    execute: bool,
) -> dict[str, Any]:
    if env_file is not None:
        load_env_file(env_file)
    psycopg, dict_row = import_psycopg()
    new_dsn = resolve_dsn(dsn_env)
    reference_dsn = resolve_dsn(reference_dsn_env)

    with psycopg.connect(reference_dsn, row_factory=dict_row) as reference_conn:
        with reference_conn.cursor() as old_cur:
            old_rows = fetch_old_talent_rows(old_cur)

    with psycopg.connect(new_dsn, row_factory=dict_row) as new_conn:
        with new_conn.cursor() as new_cur:
            person_rows = fetch_new_person_rows(new_cur)
            report = build_profile_plan(person_rows, old_rows)
            report["mode"] = "execute" if execute else "dry_run_person_profile_consumer"
            report["write_db"] = execute
            if not execute:
                new_conn.rollback()
                return report
            report["executed_counts"] = execute_upserts(new_cur, report["profile_rows"])
            report["executed"] = True
        new_conn.commit()
    return report


def markdown_report(payload: Mapping[str, Any]) -> str:
    totals = payload.get("totals") or {}
    lines = [
        "# retrieval_v3 person profile consumer report",
        "",
        f"- ok: `{str(payload.get('ok')).lower()}`",
        f"- write_db: `{str(payload.get('write_db')).lower()}`",
        f"- executed: `{str(payload.get('executed')).lower()}`",
        f"- person_objects: `{totals.get('person_objects', 0)}`",
        f"- matched_old_talent_quality: `{totals.get('matched_old_talent_quality', 0)}`",
        f"- missing_old_talent_quality: `{totals.get('missing_old_talent_quality', 0)}`",
        f"- conflicting_old_talent_quality: `{totals.get('conflicting_old_talent_quality', 0)}`",
        f"- unsupported_old_talent_quality: `{totals.get('unsupported_old_talent_quality', 0)}`",
        "",
        "## Talent Grade Counts",
        "",
        "| talent_grade | rows |",
        "| --- | ---: |",
    ]
    for grade, count in (payload.get("talent_grade_counts") or {}).items():
        lines.append(f"| {grade} | {count} |")
    if payload.get("executed_counts"):
        lines.extend(["", "## Executed", "", "| table | rows |", "| --- | ---: |"])
        for table, count in (payload.get("executed_counts") or {}).items():
            lines.append(f"| {table} | {count} |")
    review_needed = list(payload.get("review_needed") or [])
    if review_needed:
        lines.extend(["", "## Review Needed", "", "| object_id | name | reason |", "| ---: | --- | --- |"])
        for row in review_needed[:80]:
            lines.append(f"| {row.get('object_id')} | {row.get('canonical_name')} | {row.get('match_status')} |")
        if len(review_needed) > 80:
            lines.append(f"|  |  | ... {len(review_needed) - 80} more |")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Populate retrieval_v3.person_profiles from current person objects and old talent_quality reference data.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    apply = subparsers.add_parser("apply", help="Upsert one person profile per retrieval_v3 person object.")
    apply.add_argument("--output-json", type=Path, required=True)
    apply.add_argument("--output-md", type=Path, required=True)
    apply.add_argument("--env-file", type=Path)
    apply.add_argument("--dsn-env", default="EMPEROR_EVAL_RETRIEVAL_V3_DSN")
    apply.add_argument("--reference-dsn-env", default="EMPEROR_EVAL_RETRIEVAL_V3_DSN")
    apply.add_argument("--execute", action="store_true", help="Actually write person_profiles. Omit for dry-run.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "apply":
        raise ImportPlanError(f"unsupported command: {args.command}")
    payload = execute_person_profile_consumer(
        env_file=args.env_file,
        dsn_env=args.dsn_env,
        reference_dsn_env=args.reference_dsn_env,
        execute=args.execute,
    )
    write_json(args.output_json, payload)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(markdown_report(payload), encoding="utf-8")
    print(json.dumps({"ok": payload["ok"], "totals": payload["totals"]}, ensure_ascii=False, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
