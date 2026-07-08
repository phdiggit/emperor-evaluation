from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev import retrieval_v2_claim_cache as fs_cache  # noqa: E402
from scripts.dev import retrieval_v2_claim_cache_pg as pg_cache  # noqa: E402
from scripts.dev import retrieval_v2_claim_quality as claim_quality  # noqa: E402
from scripts.dev.retrieval_v2_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v2_pg_schema import DEFAULT_PG_SCHEMA, DEFAULT_V3_DSN_ENV, schema_cursor  # noqa: E402


DEFAULT_DSN_ENV = DEFAULT_V3_DSN_ENV
PATCH_TYPES = {"claim_update", "evidence_drop"}
CLAIM_FIELD_PATCH_KEYS = {
    "claim_summary",
    "direction",
    "action_type",
    "event_scope",
    "office_or_domain",
    "time_context",
    "outcome",
    "status",
    "confidence",
}


class ClaimCacheReviewPatchError(RuntimeError):
    pass


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ClaimCacheReviewPatchError(f"{path}:{line_no}: expected JSON object")
        row.setdefault("_patch_source", str(path))
        row.setdefault("_patch_line", line_no)
        rows.append(row)
    return rows


def write_json(path: Path | None, payload: Mapping[str, Any]) -> None:
    if path is None:
        print(pretty_json(payload), end="")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pretty_json(payload), encoding="utf-8", newline="\n")


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(stable_json(row) + "\n" for row in rows), encoding="utf-8", newline="\n")


def text(value: Any) -> str:
    return str(value or "").strip()


def validate_patch_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for row in rows:
        patch_type = text(row.get("patch_type"))
        if patch_type not in PATCH_TYPES:
            issues.append(issue(row, "unsupported_patch_type", f"unsupported patch_type: {patch_type}"))
            continue
        if patch_type == "claim_update":
            if not text(row.get("claim_key")):
                issues.append(issue(row, "missing_claim_key", "claim_update requires claim_key"))
            if not any(key in row for key in CLAIM_FIELD_PATCH_KEYS) and not isinstance(row.get("fact_payload_patch"), Mapping):
                issues.append(issue(row, "empty_claim_update", "claim_update has no supported field updates"))
        if patch_type == "evidence_drop":
            if not text(row.get("evidence_key")) and not (text(row.get("claim_key")) and text(row.get("source_slice_ref"))):
                issues.append(issue(row, "missing_evidence_selector", "evidence_drop requires evidence_key or claim_key + source_slice_ref"))
    return issues


def issue(row: Mapping[str, Any], code: str, message: str) -> dict[str, Any]:
    return {
        "issue_code": code,
        "message": message,
        "patch_source": row.get("_patch_source", ""),
        "patch_line": row.get("_patch_line", ""),
        "claim_key": row.get("claim_key", ""),
        "evidence_key": row.get("evidence_key", ""),
    }


def load_cache(cache_root: Path) -> dict[str, list[dict[str, Any]]]:
    paths = fs_cache.cache_paths(cache_root)
    return {
        "claims": fs_cache.read_jsonl(paths["claims"]),
        "evidence": fs_cache.read_jsonl(paths["evidence"]),
        "source_slices": fs_cache.read_jsonl(paths["slices"]),
        "runs": fs_cache.read_jsonl(paths["runs"]),
    }


def backup_cache_files(cache_root: Path, patch_code: str) -> str:
    paths = fs_cache.cache_paths(cache_root)
    backup_dir = paths["reports"] / f"{patch_code}_backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for path in (paths["claims"], paths["evidence"], paths["slices"], paths["runs"]):
        if path.exists():
            shutil.copy2(path, backup_dir / path.name)
    return str(backup_dir)


def review_entry(row: Mapping[str, Any], *, patch_code: str) -> dict[str, Any]:
    return {
        "patch_code": patch_code,
        "review_note": text(row.get("review_note") or row.get("reason")),
        "scope_role": text(row.get("scope_role")),
        "patch_source": row.get("_patch_source", ""),
        "patch_line": row.get("_patch_line", ""),
    }


def apply_claim_update(claim: Mapping[str, Any], patch: Mapping[str, Any], *, patch_code: str) -> tuple[dict[str, Any], dict[str, Any]]:
    updated = dict(claim)
    before = {
        "claim_summary": claim.get("claim_summary"),
        "direction": claim.get("direction"),
        "action_type": claim.get("action_type"),
        "event_scope": claim.get("event_scope"),
        "office_or_domain": claim.get("office_or_domain"),
        "time_context": claim.get("time_context"),
        "outcome": claim.get("outcome"),
        "status": claim.get("status"),
        "confidence": claim.get("confidence"),
        "fact_payload": claim.get("fact_payload"),
        "canonical_event_key": claim.get("canonical_event_key"),
    }
    for key in CLAIM_FIELD_PATCH_KEYS:
        if key in patch:
            updated[key] = patch[key]
    fact_payload = dict(updated.get("fact_payload") or {})
    if isinstance(patch.get("fact_payload_patch"), Mapping):
        fact_payload.update(dict(patch["fact_payload_patch"]))
    for key in ("direction", "action_type", "event_scope", "office_or_domain", "time_context", "outcome"):
        if key in patch:
            fact_payload[key] = patch[key]
    manual_reviews = list(fact_payload.get("manual_reviews") or [])
    manual_reviews.append(review_entry(patch, patch_code=patch_code))
    fact_payload["manual_reviews"] = manual_reviews
    updated["fact_payload"] = fact_payload
    updated.update(claim_quality.claim_quality_payload(updated))
    after = {
        "claim_summary": updated.get("claim_summary"),
        "direction": updated.get("direction"),
        "action_type": updated.get("action_type"),
        "event_scope": updated.get("event_scope"),
        "office_or_domain": updated.get("office_or_domain"),
        "time_context": updated.get("time_context"),
        "outcome": updated.get("outcome"),
        "status": updated.get("status"),
        "confidence": updated.get("confidence"),
        "fact_payload": updated.get("fact_payload"),
        "canonical_event_key": updated.get("canonical_event_key"),
    }
    return updated, {"before": before, "after": after}


def evidence_matches(row: Mapping[str, Any], patch: Mapping[str, Any]) -> bool:
    evidence_key = text(patch.get("evidence_key"))
    if evidence_key:
        return text(row.get("evidence_key")) == evidence_key
    return text(row.get("claim_key")) == text(patch.get("claim_key")) and text(row.get("source_slice_ref")) == text(patch.get("source_slice_ref"))


def apply_patch_to_cache(cache_root: Path, rows: Sequence[Mapping[str, Any]], *, patch_code: str, execute: bool) -> dict[str, Any]:
    cache = load_cache(cache_root)
    claims_by_key = {text(row.get("claim_key")): row for row in cache["claims"]}
    evidence_rows = list(cache["evidence"])
    source_slices = list(cache["source_slices"])
    applied: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []

    for patch in rows:
        patch_type = text(patch.get("patch_type"))
        if patch_type == "claim_update":
            claim_key = text(patch.get("claim_key"))
            claim = claims_by_key.get(claim_key)
            if not claim:
                issues.append(issue(patch, "claim_not_found", f"claim not found: {claim_key}"))
                continue
            updated, delta = apply_claim_update(claim, patch, patch_code=patch_code)
            claims_by_key[claim_key] = updated
            applied.append(
                {
                    "patch_type": patch_type,
                    "claim_key": claim_key,
                    "delta": delta,
                    "review_note": text(patch.get("review_note") or patch.get("reason")),
                }
            )
        elif patch_type == "evidence_drop":
            matched = [row for row in evidence_rows if evidence_matches(row, patch)]
            if not matched:
                issues.append(issue(patch, "evidence_not_found", "no evidence rows matched selector"))
                continue
            matched_keys = {text(row.get("evidence_key")) for row in matched}
            evidence_rows = [row for row in evidence_rows if text(row.get("evidence_key")) not in matched_keys]
            applied.append(
                {
                    "patch_type": patch_type,
                    "claim_key": text(patch.get("claim_key")),
                    "evidence_keys": sorted(matched_keys),
                    "source_slice_refs": sorted({text(row.get("source_slice_ref")) for row in matched}),
                    "reason": text(patch.get("review_note") or patch.get("reason")),
                }
            )

    referenced_slice_hashes = {text(row.get("slice_hash")) for row in evidence_rows}
    pruned_source_slices = [row for row in source_slices if text(row.get("slice_hash")) in referenced_slice_hashes]
    paths = fs_cache.cache_paths(cache_root)
    backup_dir = ""
    if execute and not issues:
        backup_dir = backup_cache_files(cache_root, patch_code)
        write_jsonl(paths["claims"], sorted(claims_by_key.values(), key=lambda row: text(row.get("claim_key"))))
        write_jsonl(paths["evidence"], sorted(evidence_rows, key=lambda row: text(row.get("evidence_key"))))
        write_jsonl(paths["slices"], sorted(pruned_source_slices, key=lambda row: text(row.get("slice_hash"))))

    return {
        "cache_root": str(cache_root),
        "write_files": execute and not issues,
        "backup_dir": backup_dir,
        "issues": issues,
        "applied": applied,
        "counts_before": {
            "claims": len(cache["claims"]),
            "evidence": len(cache["evidence"]),
            "source_slices": len(source_slices),
        },
        "counts_after": {
            "claims": len(claims_by_key),
            "evidence": len(evidence_rows),
            "source_slices": len(pruned_source_slices),
        },
    }


def sync_pg_deletes(*, dsn: str, dropped_evidence_keys: Sequence[str], execute: bool, schema_name: str) -> dict[str, Any]:
    if not dropped_evidence_keys:
        return {"planned_delete_count": 0, "deleted": [], "existing_before": []}
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            cur.execute(
                "select evidence_key, claim_key, source_slice_ref from retrieval_v2.claim_evidence where evidence_key = any(%s)",
                (list(dropped_evidence_keys),),
            )
            existing = [dict(row) for row in cur.fetchall()]
            deleted: list[str] = []
            if execute:
                cur.execute(
                    "delete from retrieval_v2.claim_evidence where evidence_key = any(%s) returning evidence_key",
                    (list(dropped_evidence_keys),),
                )
                deleted = [row["evidence_key"] for row in cur.fetchall()]
        if execute:
            conn.commit()
        else:
            conn.rollback()
    return {
        "planned_delete_count": len(dropped_evidence_keys),
        "existing_before": existing,
        "deleted": deleted,
    }


def apply_review_patch(
    *,
    cache_root: Path,
    patch_rows: Sequence[Mapping[str, Any]],
    patch_code: str,
    execute: bool,
    sync_pg: bool,
    env_file: Path | None,
    dsn_env: str,
    schema_name: str = DEFAULT_PG_SCHEMA,
) -> dict[str, Any]:
    validation_issues = validate_patch_rows(patch_rows)
    report: dict[str, Any] = {
        "ok": not validation_issues,
        "generated_by": "scripts/dev/retrieval_v2_claim_cache_review_patch.py",
        "patch_code": patch_code,
        "mode": "execute" if execute else "dry_run",
        "write_files": False,
        "sync_pg": sync_pg,
        "patch_row_count": len(patch_rows),
        "validation_issues": validation_issues,
        "cache_report": {},
        "pg_apply_report": {},
        "pg_evidence_delete_report": {},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if validation_issues:
        return report
    cache_report = apply_patch_to_cache(cache_root, patch_rows, patch_code=patch_code, execute=execute)
    report["cache_report"] = cache_report
    report["write_files"] = bool(cache_report.get("write_files"))
    report["ok"] = not cache_report.get("issues")
    if not report["ok"] or not sync_pg:
        return report
    if env_file is not None:
        load_env_file(env_file)
    pg_apply_report = pg_cache.apply_cache_to_pg(
        cache_root=cache_root,
        env_file=None,
        dsn_env=dsn_env,
        schema_name=schema_name,
        execute=execute,
    )
    report["pg_apply_report"] = pg_apply_report
    dropped_keys: list[str] = []
    for item in cache_report.get("applied") or []:
        if item.get("patch_type") == "evidence_drop":
            dropped_keys.extend(str(key) for key in item.get("evidence_keys") or [])
    report["pg_evidence_delete_report"] = sync_pg_deletes(
        dsn=resolve_dsn(dsn_env),
        dropped_evidence_keys=sorted(set(dropped_keys)),
        execute=execute,
        schema_name=schema_name,
    )
    report["ok"] = bool(report["ok"] and pg_apply_report.get("ok"))
    return report


def markdown_report(payload: Mapping[str, Any]) -> str:
    lines = [
        "# retrieval_v2 claim cache review patch",
        "",
        f"- ok: `{str(payload.get('ok')).lower()}`",
        f"- mode: `{payload.get('mode')}`",
        f"- patch_code: `{payload.get('patch_code')}`",
        f"- sync_pg: `{str(payload.get('sync_pg')).lower()}`",
        "",
    ]
    cache_report = payload.get("cache_report") if isinstance(payload.get("cache_report"), Mapping) else {}
    if cache_report:
        lines.extend(["## Cache", ""])
        lines.append(f"- cache_root: `{cache_report.get('cache_root')}`")
        lines.append(f"- write_files: `{str(cache_report.get('write_files')).lower()}`")
        lines.append(f"- backup_dir: `{cache_report.get('backup_dir', '')}`")
        lines.append(f"- counts_before: `{cache_report.get('counts_before')}`")
        lines.append(f"- counts_after: `{cache_report.get('counts_after')}`")
        lines.append("")
    applied = cache_report.get("applied") if isinstance(cache_report, Mapping) else []
    if isinstance(applied, list) and applied:
        lines.extend(["## Applied", ""])
        for item in applied:
            label = item.get("claim_key") or ",".join(item.get("evidence_keys") or [])
            lines.append(f"- `{item.get('patch_type')}` `{label}`")
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Apply reviewed JSONL patches to a filesystem retrieval_v2 claim cache; dry-run by default.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    apply = subparsers.add_parser("apply-patch", help="Apply claim_update/evidence_drop patch JSONL rows.")
    apply.add_argument("--cache-root", type=Path, required=True)
    apply.add_argument("--patch-jsonl", type=Path, action="append", required=True)
    apply.add_argument("--patch-code", required=True)
    apply.add_argument("--execute", action="store_true")
    apply.add_argument("--sync-pg", action="store_true")
    apply.add_argument("--env-file", type=Path)
    apply.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    apply.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    apply.add_argument("--output-json", type=Path, required=True)
    apply.add_argument("--output-md", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "apply-patch":
        patch_rows = [row for path in args.patch_jsonl for row in read_jsonl(path)]
        payload = apply_review_patch(
            cache_root=args.cache_root,
            patch_rows=patch_rows,
            patch_code=args.patch_code,
            execute=args.execute,
            sync_pg=args.sync_pg,
            env_file=args.env_file,
            dsn_env=args.dsn_env,
            schema_name=args.pg_schema,
        )
        write_json(args.output_json, payload)
        if args.output_md is not None:
            args.output_md.parent.mkdir(parents=True, exist_ok=True)
            args.output_md.write_text(markdown_report(payload), encoding="utf-8", newline="\n")
        print(
            json.dumps(
                {
                    "ok": payload["ok"],
                    "mode": payload["mode"],
                    "patch_code": payload["patch_code"],
                    "output_json": str(args.output_json),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0 if payload["ok"] else 1
    raise ClaimCacheReviewPatchError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
