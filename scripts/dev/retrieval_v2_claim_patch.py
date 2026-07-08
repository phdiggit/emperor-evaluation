from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v2_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v2_pg_schema import DEFAULT_V3_DSN_ENV, schema_cursor  # noqa: E402


DEFAULT_DSN_ENV = DEFAULT_V3_DSN_ENV
ALLOWED_DIRECTIONS = {"positive", "negative", "neutral", "mixed"}
ALLOWED_STATUSES = {"active", "superseded", "needs_review", "rejected"}
PATCHABLE_FIELDS = ("emperor_name", "direction", "action_type", "status")


class ClaimPatchError(RuntimeError):
    pass


@dataclass(frozen=True)
class ClaimPatch:
    claim_key: str
    set_values: dict[str, str]
    expected: dict[str, str]
    reason: str
    source: str
    note: str


def text(value: Any) -> str:
    return str(value or "").strip()


def as_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def read_patch_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise ClaimPatchError(f"patch file missing: {path}")
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        rows: list[dict[str, Any]] = []
        for line_no, line in enumerate(raw.splitlines(), start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, Mapping):
                raise ClaimPatchError(f"{path}:{line_no}: expected JSON object")
            rows.append(dict(payload))
        return rows
    payload = json.loads(raw)
    if isinstance(payload, Mapping) and isinstance(payload.get("patches"), list):
        payload = payload["patches"]
    if not isinstance(payload, list):
        raise ClaimPatchError(f"{path}: expected JSON array, JSONL, or object with patches[]")
    rows = []
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, Mapping):
            raise ClaimPatchError(f"{path}: patches[{index}] must be an object")
        rows.append(dict(item))
    return rows


def parse_patch_row(row: Mapping[str, Any]) -> ClaimPatch:
    claim_key = text(row.get("claim_key"))
    if not claim_key:
        raise ClaimPatchError("patch row missing claim_key")
    set_payload = as_mapping(row.get("set"))
    set_values = {
        field: text(set_payload.get(field) if field in set_payload else row.get(field))
        for field in PATCHABLE_FIELDS
        if text(set_payload.get(field) if field in set_payload else row.get(field))
    }
    if not set_values:
        raise ClaimPatchError(f"{claim_key}: patch must set at least one of {', '.join(PATCHABLE_FIELDS)}")
    direction = set_values.get("direction")
    if direction and direction not in ALLOWED_DIRECTIONS:
        raise ClaimPatchError(f"{claim_key}: invalid direction {direction!r}")
    status = set_values.get("status")
    if status and status not in ALLOWED_STATUSES:
        raise ClaimPatchError(f"{claim_key}: invalid status {status!r}")
    unknown = sorted(set(set_payload) - set(PATCHABLE_FIELDS))
    if unknown:
        raise ClaimPatchError(f"{claim_key}: unsupported set fields: {', '.join(unknown)}")
    return ClaimPatch(
        claim_key=claim_key,
        set_values=set_values,
        expected={key: text(value) for key, value in as_mapping(row.get("expected")).items() if text(value)},
        reason=text(row.get("reason")),
        source=text(row.get("source")) or "manual_claim_patch",
        note=text(row.get("note")),
    )


def load_patches(path: Path) -> list[ClaimPatch]:
    patches = [parse_patch_row(row) for row in read_patch_rows(path)]
    seen: set[str] = set()
    duplicates: list[str] = []
    for patch in patches:
        if patch.claim_key in seen:
            duplicates.append(patch.claim_key)
        seen.add(patch.claim_key)
    if duplicates:
        raise ClaimPatchError(f"duplicate claim_key in patch file: {', '.join(sorted(set(duplicates)))}")
    return patches


def fetch_claims(cur: Any, claim_keys: Sequence[str]) -> dict[str, dict[str, Any]]:
    keys = [text(key) for key in claim_keys if text(key)]
    if not keys:
        return {}
    cur.execute(
        """
        select
            claim_key,
            emperor_name,
            direction::text as direction,
            action_type,
            status::text as status,
            fact_payload,
            claim_summary,
            object_name,
            time_context
          from retrieval_v2.claim_cache
         where claim_key = any(%s)
         order by claim_key
        """,
        (keys,),
    )
    return {text(row["claim_key"]): dict(row) for row in cur.fetchall()}


def expected_mismatches(patch: ClaimPatch, current: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    mismatches: dict[str, dict[str, str]] = {}
    for field, expected in patch.expected.items():
        actual = text(current.get(field))
        if actual != expected:
            mismatches[field] = {"expected": expected, "actual": actual}
    return mismatches


def patch_preview(patch: ClaimPatch, current: Mapping[str, Any] | None) -> dict[str, Any]:
    if current is None:
        return {
            "claim_key": patch.claim_key,
            "status": "missing",
            "changes": {},
            "expected_mismatches": {},
            "reason": patch.reason,
            "note": patch.note,
        }
    mismatches = expected_mismatches(patch, current)
    changes = {
        field: {"from": text(current.get(field)), "to": value}
        for field, value in patch.set_values.items()
        if text(current.get(field)) != value
    }
    status = "blocked_expected_mismatch" if mismatches else ("changed" if changes else "noop")
    return {
        "claim_key": patch.claim_key,
        "status": status,
        "changes": changes,
        "expected_mismatches": mismatches,
        "reason": patch.reason,
        "source": patch.source,
        "note": patch.note,
        "current": {
            "emperor_name": text(current.get("emperor_name")),
            "object_name": text(current.get("object_name")),
            "direction": text(current.get("direction")),
            "action_type": text(current.get("action_type")),
            "status": text(current.get("status")),
            "time_context": text(current.get("time_context")),
            "claim_summary": text(current.get("claim_summary")),
        },
    }


def build_patch_report(patches: Sequence[ClaimPatch], current_rows: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    rows = [patch_preview(patch, current_rows.get(patch.claim_key)) for patch in patches]
    counts: dict[str, int] = {}
    for row in rows:
        status = text(row.get("status"))
        counts[status] = counts.get(status, 0) + 1
    return {
        "ok": not any(row["status"] in {"missing", "blocked_expected_mismatch"} for row in rows),
        "totals": {
            "patches": len(rows),
            "changed": counts.get("changed", 0),
            "noop": counts.get("noop", 0),
            "missing": counts.get("missing", 0),
            "blocked_expected_mismatch": counts.get("blocked_expected_mismatch", 0),
        },
        "patches": rows,
    }


def repair_payload(patch: ClaimPatch, current: Mapping[str, Any], changes: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source": patch.source,
        "reason": patch.reason,
        "note": patch.note,
        "claim_key": patch.claim_key,
        "changes": changes,
        "previous": {
            "emperor_name": text(current.get("emperor_name")),
            "direction": text(current.get("direction")),
            "action_type": text(current.get("action_type")),
            "status": text(current.get("status")),
        },
    }


def apply_patch(cur: Any, patch: ClaimPatch, current: Mapping[str, Any]) -> int:
    preview = patch_preview(patch, current)
    if preview["status"] != "changed":
        return 0
    changes = preview["changes"]
    set_values = {field: patch.set_values[field] for field in changes}
    fact_merge: dict[str, Any] = {}
    if "action_type" in set_values:
        fact_merge["action_type"] = set_values["action_type"]
    repair = repair_payload(patch, current, changes)
    fact_merge["claim_repair_payload"] = repair
    history_item = [repair]
    cur.execute(
        """
        update retrieval_v2.claim_cache
           set emperor_name = coalesce(%s, emperor_name),
               direction = coalesce(%s::retrieval_v2.rv2_claim_direction, direction),
               action_type = coalesce(%s, action_type),
               status = coalesce(%s::retrieval_v2.rv2_claim_cache_status, status),
               fact_payload = jsonb_set(
                   fact_payload || %s::jsonb,
                   '{claim_repair_history}',
                   coalesce(fact_payload->'claim_repair_history', '[]'::jsonb) || %s::jsonb,
                   true
               ),
               updated_at = now()
         where claim_key = %s
        """,
        (
            set_values.get("emperor_name"),
            set_values.get("direction"),
            set_values.get("action_type"),
            set_values.get("status"),
            stable_json(fact_merge),
            stable_json(history_item),
            patch.claim_key,
        ),
    )
    return int(getattr(cur, "rowcount", 0) or 0)


def apply_patches(cur: Any, patches: Sequence[ClaimPatch], current_rows: Mapping[str, Mapping[str, Any]]) -> int:
    updated = 0
    for patch in patches:
        current = current_rows.get(patch.claim_key)
        if current is None:
            continue
        preview = patch_preview(patch, current)
        if preview["status"] == "blocked_expected_mismatch":
            continue
        updated += apply_patch(cur, patch, current)
    return updated


def run_claim_patch(
    *,
    patch_file: Path,
    env_file: Path | None,
    dsn_env: str,
    schema_name: str,
    execute: bool,
) -> dict[str, Any]:
    if env_file is not None:
        load_env_file(env_file)
    patches = load_patches(patch_file)
    psycopg, dict_row = import_psycopg()
    updated = 0
    with psycopg.connect(resolve_dsn(dsn_env), row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            current_rows = fetch_claims(cur, [patch.claim_key for patch in patches])
            report = build_patch_report(patches, current_rows)
            if execute:
                if not report["ok"]:
                    conn.rollback()
                    raise ClaimPatchError("patch report has missing rows or expected mismatches; refusing --execute")
                updated = apply_patches(cur, patches, current_rows)
                conn.commit()
            else:
                conn.rollback()
    report.update(
        {
            "generated_by": "scripts/dev/retrieval_v2_claim_patch.py",
            "mode": "execute" if execute else "dry_run",
            "write_db": execute,
            "schema_name": schema_name,
            "patch_file": str(patch_file),
            "executed_counts": {"claim_cache_updated": updated} if execute else {},
        }
    )
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Apply reviewed, explicit claim_cache corrections. Defaults to dry-run.")
    parser.add_argument("--patch-file", type=Path, required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    parser.add_argument("--pg-schema", default="retrieval_v3")
    parser.add_argument("--execute", action="store_true", help="Write accepted patches to PostgreSQL.")
    parser.add_argument("--output-json", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_claim_patch(
        patch_file=args.patch_file,
        env_file=args.env_file,
        dsn_env=args.dsn_env,
        schema_name=args.pg_schema,
        execute=bool(args.execute),
    )
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(pretty_json(report), encoding="utf-8", newline="\n")
    print(json.dumps({"ok": report["ok"], "mode": report["mode"], "totals": report["totals"]}, ensure_ascii=False, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ClaimPatchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
