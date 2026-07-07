from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.parse
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v2_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v2_import_plan import json_param, write_json  # noqa: E402
from scripts.dev.retrieval_v2_intake_manifest import text  # noqa: E402

DEFAULT_DSN_ENV = "EMPEROR_EVAL_RETRIEVAL_V2_DSN"
DEFAULT_ITEM_CODE = "I5B"
DEFAULT_SOURCE_CACHE_ROOT = ROOT / "tmp" / "retrieval_v2_source_cache"


class PassageFulltextBackfillError(RuntimeError):
    pass


def quote_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest() if value else ""


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PassageFulltextBackfillError(f"{path}: expected JSON object")
    return payload


def resolve_repo_path(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def candidate_slices_by_code(path: Path) -> dict[str, dict[str, Any]]:
    payload = read_json(path)
    rows: dict[str, dict[str, Any]] = {}
    for row in payload.get("candidate_slices") or []:
        if isinstance(row, Mapping) and text(row.get("slice_code")):
            rows.setdefault(text(row.get("slice_code")), dict(row))
    return rows


def fallback_candidate_paths(target_code: str) -> list[Path]:
    if not target_code:
        return []
    run_root = ROOT / "tmp" / "retrieval_v2_clean_runs"
    pattern = f"*/{target_code}_appointment_delegation/candidates.final.json"
    return sorted(
        run_root.glob(pattern),
        key=lambda path: path.stat().st_mtime if path.exists() else 0,
        reverse=True,
    )


def source_cache_paths(cache_dir: Path, source_key: str) -> tuple[Path, Path]:
    stem = hashlib.sha256(source_key.encode("utf-8")).hexdigest()
    return cache_dir / f"{stem}.txt", cache_dir / f"{stem}.meta.json"


def read_source_cache_text(cache_dir: Path, source_key: str) -> str:
    text_path, _meta_path = source_cache_paths(cache_dir, source_key)
    if not text_path.exists():
        return ""
    return text_path.read_text(encoding="utf-8")


def source_keys_for_row(row: Mapping[str, Any]) -> list[str]:
    payload = row.get("document_payload") if isinstance(row.get("document_payload"), Mapping) else {}
    titles = [
        payload.get("wikisource_title"),
        payload.get("title"),
        row.get("document_title"),
        row.get("source_title"),
    ]
    keys: list[str] = []
    seen: set[str] = set()
    for raw_title in titles:
        title = text(raw_title)
        if not title:
            continue
        key = f"wikisource:{title}"
        if key not in seen:
            seen.add(key)
            keys.append(key)
    url = text(row.get("canon_url") or payload.get("url"))
    if url:
        title_from_url = wikisource_title_from_url(url)
        if title_from_url:
            key = f"wikisource:{title_from_url}"
            if key not in seen:
                seen.add(key)
                keys.append(key)
        key = f"url:{url}"
        if key not in seen:
            keys.append(key)
    return keys


def wikisource_title_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if not parsed.netloc.endswith("wikisource.org"):
        return ""
    path = urllib.parse.unquote(parsed.path).strip("/")
    for prefix in ("wiki/", "zh-hans/", "zh/", "zh-hant/"):
        if path.startswith(prefix):
            return path[len(prefix) :].strip()
    return ""


def char_ranges_from_locator(locator: str) -> list[tuple[int, int]]:
    match = re.search(r"chars:(\d+)-(\d+)", locator)
    if not match:
        return []
    start, end = int(match.group(1)), int(match.group(2))
    if end <= start:
        return []
    return [(start, end), (start, end + 1)]


def full_text_from_document_cache(
    row: Mapping[str, Any],
    *,
    source_cache_root: Path,
) -> tuple[str, str]:
    current_raw_text = text(row.get("raw_text"))
    best_snippet = ""
    best_source_key = ""
    for source_key in source_keys_for_row(row):
        page_text = read_source_cache_text(source_cache_root, source_key)
        if not page_text:
            continue
        for start, end in char_ranges_from_locator(text(row.get("locator"))):
            snippet = page_text[start:end].strip()
            if current_text_is_prefix(current_raw_text, snippet) and len(snippet) > len(best_snippet):
                best_snippet = snippet
                best_source_key = source_key
    return best_snippet, best_source_key


def load_candidate_cache(paths: Sequence[str]) -> dict[str, dict[str, dict[str, Any]]]:
    cache: dict[str, dict[str, dict[str, Any]]] = {}
    for path_text in sorted({text(path) for path in paths if text(path)}):
        path = resolve_repo_path(path_text)
        if path.exists():
            cache[path_text] = candidate_slices_by_code(path)
    return cache


def candidate_sources_for_row(
    row: Mapping[str, Any],
    cache: Mapping[str, dict[str, dict[str, Any]]],
) -> list[tuple[str, dict[str, dict[str, Any]]]]:
    sources: list[tuple[str, dict[str, dict[str, Any]]]] = []
    primary = text(row.get("candidates_path"))
    if primary in cache:
        sources.append((primary, cache[primary]))
    for path in fallback_candidate_paths(text(row.get("target_code"))):
        path_text = str(path)
        if path_text in cache and path_text != primary:
            sources.append((path_text, cache[path_text]))
    return sources


def passage_slice_code(row: Mapping[str, Any]) -> str:
    payload = row.get("passage_payload") if isinstance(row.get("passage_payload"), Mapping) else {}
    return text(payload.get("slice_code"))


def current_text_is_prefix(current: str, full_text: str) -> bool:
    current = current.strip()
    full_text = full_text.strip()
    if not current or not full_text or len(full_text) <= len(current):
        return False
    return full_text.startswith(current)


def build_backfill_plan(
    rows: Sequence[Mapping[str, Any]],
    *,
    source_cache_root: Path = DEFAULT_SOURCE_CACHE_ROOT,
) -> dict[str, Any]:
    candidate_paths = [text(row.get("candidates_path")) for row in rows]
    for row in rows:
        candidate_paths.extend(str(path) for path in fallback_candidate_paths(text(row.get("target_code"))))
    candidate_cache = load_candidate_cache(candidate_paths)
    planned: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()
    for row in rows:
        slice_code = passage_slice_code(row)
        if not slice_code:
            skipped["missing_slice_code"] += 1
            continue
        sources = candidate_sources_for_row(row, candidate_cache)
        if not sources:
            full_text, document_source_key = full_text_from_document_cache(row, source_cache_root=source_cache_root)
            if not full_text:
                skipped["missing_candidates_artifact"] += 1
                continue
            candidates_path = f"source_cache:{document_source_key}"
            candidate_slice = {"locator": row.get("locator"), "text": full_text}
        else:
            candidates_path = ""
            candidate_slice = None
            for source_path, slices in sources:
                if slice_code in slices:
                    candidates_path = source_path
                    candidate_slice = slices[slice_code]
                    break
            if not candidate_slice:
                full_text, document_source_key = full_text_from_document_cache(row, source_cache_root=source_cache_root)
                if full_text:
                    candidates_path = f"source_cache:{document_source_key}"
                    candidate_slice = {"locator": row.get("locator"), "text": full_text}
                else:
                    skipped["missing_candidate_slice"] += 1
                    continue
        full_text = text(candidate_slice.get("text"))
        current_raw_text = text(row.get("raw_text"))
        if not current_text_is_prefix(current_raw_text, full_text):
            skipped["not_prefix_or_not_longer"] += 1
            continue
        payload = dict(row.get("passage_payload") or {})
        payload.update(
            {
                "quote": full_text,
                "raw_text": full_text,
                "fulltext_backfill": {
                    "source": "retrieval_v2_passage_fulltext_backfill",
                    "source_slice_code": slice_code,
                    "source_artifact": candidates_path,
                    "previous_raw_text_chars": len(current_raw_text),
                    "new_raw_text_chars": len(full_text),
                },
            }
        )
        planned.append(
            {
                "passage_id": int(row["passage_id"]),
                "emperor_name": text(row.get("emperor_name")),
                "source_pack_code": text(row.get("source_pack_code")),
                "passage_code": text(row.get("passage_code")),
                "raw_passage_code": text(row.get("raw_passage_code")),
                "document_code": text(row.get("document_code")),
                "source_slice_code": slice_code,
                "candidates_path": candidates_path,
                "old_chars": len(current_raw_text),
                "new_chars": len(full_text),
                "locator": text(candidate_slice.get("locator") or row.get("locator")),
                "raw_text": full_text,
                "quote_hash": quote_hash(full_text),
                "passage_payload": payload,
            }
        )
    return {
        "planned": planned,
        "skipped_counts": dict(sorted(skipped.items())),
        "candidate_artifacts_loaded": len(candidate_cache),
    }


def fetch_candidate_rows(
    cur: Any,
    *,
    item_code: str,
    target_names: Sequence[str],
    target_codes: Sequence[str],
    pack_codes: Sequence[str],
    limit: int,
) -> list[dict[str, Any]]:
    cur.execute(
        """
        with artifact_agg as (
            select
                source_pack_id,
                max(artifact_path) filter (where artifact_kind = 'candidates') as candidates_path
              from retrieval_v2.source_pack_artifacts
             group by source_pack_id
        )
        select
            rt.emperor_name,
            rt.target_code,
            sp.pack_code as source_pack_code,
            aa.candidates_path,
            spg.id as passage_id,
            spg.passage_code,
            spg.raw_passage_code,
            spg.locator,
            spg.raw_text,
            spg.passage_payload,
            sd.document_code,
            sd.title as document_title,
            sd.source_title,
            sd.canon_url,
            sd.document_payload
          from retrieval_v2.source_passages spg
          join retrieval_v2.source_documents sd on sd.id = spg.source_document_id
          join retrieval_v2.source_packs sp on sp.id = sd.source_pack_id
          join retrieval_v2.retrieval_targets rt on rt.id = sp.target_id
          left join artifact_agg aa on aa.source_pack_id = sp.id
         where sp.status = 'accepted'
           and (%s = '' or rt.item_code = %s)
           and (coalesce(array_length(%s::text[], 1), 0) = 0 or rt.emperor_name = any(%s::text[]))
           and (coalesce(array_length(%s::text[], 1), 0) = 0 or rt.target_code = any(%s::text[]))
           and (coalesce(array_length(%s::text[], 1), 0) = 0 or sp.pack_code = any(%s::text[]))
           and coalesce(spg.passage_payload->>'slice_code', '') <> ''
           and spg.raw_passage_code not like 'RPR-%%'
         order by rt.emperor_name, sp.pack_code, spg.id
         limit case when %s > 0 then %s else 2147483647 end
        """,
        (
            item_code,
            item_code,
            list(target_names),
            list(target_names),
            list(target_codes),
            list(target_codes),
            list(pack_codes),
            list(pack_codes),
            limit,
            limit,
        ),
    )
    return [dict(row) for row in cur.fetchall()]


def apply_updates(cur: Any, planned: Sequence[Mapping[str, Any]]) -> int:
    count = 0
    for row in planned:
        cur.execute(
            """
            update retrieval_v2.source_passages
               set raw_text = %s,
                   quote_hash = %s,
                   locator = %s,
                   passage_payload = passage_payload || %s::jsonb
             where id = %s
            """,
            (
                text(row.get("raw_text")),
                text(row.get("quote_hash")),
                text(row.get("locator")),
                json_param(row.get("passage_payload") or {}),
                int(row["passage_id"]),
            ),
        )
        count += int(getattr(cur, "rowcount", 0) or 0)
    return count


def run_backfill(
    *,
    env_file: Path | None,
    dsn_env: str,
    item_code: str,
    target_names: Sequence[str],
    target_codes: Sequence[str],
    pack_codes: Sequence[str],
    limit: int,
    execute: bool,
) -> dict[str, Any]:
    if env_file is not None:
        load_env_file(env_file)
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(resolve_dsn(dsn_env), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            rows = fetch_candidate_rows(
                cur,
                item_code=item_code,
                target_names=target_names,
                target_codes=target_codes,
                pack_codes=pack_codes,
                limit=limit,
            )
            plan = build_backfill_plan(rows)
            updated = apply_updates(cur, plan["planned"]) if execute else 0
        if execute:
            conn.commit()
        else:
            conn.rollback()
    counts_by_target = Counter(text(row.get("emperor_name")) for row in plan["planned"])
    counts_by_pack = Counter(text(row.get("source_pack_code")) for row in plan["planned"])
    return {
        "generated_by": "scripts/dev/retrieval_v2_passage_fulltext_backfill.py",
        "write_db": execute,
        "executed": execute,
        "ok": True,
        "scanned": len(rows),
        "planned_count": len(plan["planned"]),
        "updated_count": updated,
        "candidate_artifacts_loaded": plan["candidate_artifacts_loaded"],
        "counts_by_target": dict(sorted(counts_by_target.items())),
        "counts_by_pack": dict(sorted(counts_by_pack.items())),
        "skipped_counts": plan["skipped_counts"],
        "planned": [
            {key: value for key, value in row.items() if key not in {"raw_text", "passage_payload"}}
            for row in plan["planned"]
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill full candidate slice text into retrieval_v2 source_passages.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    parser.add_argument("--item-code", default=DEFAULT_ITEM_CODE)
    parser.add_argument("--target-name", action="append", default=[])
    parser.add_argument("--target-code", action="append", default=[])
    parser.add_argument("--pack-code", action="append", default=[])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--output-json", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run_backfill(
        env_file=args.env_file,
        dsn_env=args.dsn_env,
        item_code=args.item_code,
        target_names=args.target_name,
        target_codes=args.target_code,
        pack_codes=args.pack_code,
        limit=max(0, args.limit),
        execute=args.execute,
    )
    if args.output_json is not None:
        write_json(args.output_json, payload)
    print(
        json.dumps(
            {
                "ok": payload["ok"],
                "executed": payload["executed"],
                "scanned": payload["scanned"],
                "planned_count": payload["planned_count"],
                "updated_count": payload["updated_count"],
                "counts_by_target": payload["counts_by_target"],
                "skipped_counts": payload["skipped_counts"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
