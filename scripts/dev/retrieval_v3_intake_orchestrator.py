from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from scripts.dev.retrieval_v3_bootstrap import import_psycopg, load_env_file, resolve_dsn
from scripts.dev.retrieval_v3_pg_schema import schema_cursor
from scripts.dev import retrieval_v3_object_source_cache_seed as seed_tool
from scripts.dev import retrieval_v3_object_source_cache as source_cache
from scripts.dev import retrieval_v3_object_source_cache_worker as worker


class IntakeOrchestratorError(RuntimeError):
    pass


ROOT = Path(__file__).resolve().parents[2]
INTAKE_MODES = ("ensure", "supplement", "refresh")
DEFAULT_QUERY_PROFILE_JSONL = ROOT / "data" / "query_profile_batches" / "i5b_layered_retrieval_profiles_20260630.jsonl"
WIKIPEDIA_SUMMARY_ENDPOINT = (
    "https://zh.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&redirects=1"
    "&format=json&formatversion=2&titles={title}"
)


def text(value: Any) -> str:
    return str(value or "").strip()


def name_keys(seed: Mapping[str, Any]) -> set[str]:
    values = [seed.get("name"), seed.get("normalized_name"), *(seed.get("aliases") or [])]
    return {seed_tool.normalized_name(value) for value in values if text(value)}


def new_person_seed(name: str, *, target_emperors: Sequence[str], is_emperor: bool = False) -> dict[str, Any]:
    canonical_name = text(name)
    normalized = seed_tool.normalized_name(canonical_name)
    if not normalized:
        raise IntakeOrchestratorError("new person name must not be blank")
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16].upper()
    owners = [text(value) for value in target_emperors if text(value)]
    if is_emperor and canonical_name not in owners:
        owners.append(canonical_name)
    return {
        "object_code": f"OBJ-INTAKE-{digest}",
        "name": canonical_name,
        "normalized_name": normalized,
        "object_type": "person",
        "aliases": [],
        "is_emperor": is_emperor,
        "target_emperors": sorted(set(owners)),
        "source_hints": [],
        "source_document_hints": [],
        "intake_source": "retrieval_v3_intake_orchestrator",
    }


def fetch_wikipedia_summary(name: str, *, timeout_seconds: int = 15) -> dict[str, Any]:
    url = WIKIPEDIA_SUMMARY_ENDPOINT.format(title=quote(text(name), safe=""))
    request = Request(url, headers={"User-Agent": "emperor-evaluation-retrieval-v3/1.0"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - fixed HTTPS endpoint
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"status": "unavailable", "url": url, "error": type(exc).__name__}
    pages = ((payload.get("query") or {}).get("pages") or []) if isinstance(payload, Mapping) else []
    page = pages[0] if pages and isinstance(pages[0], Mapping) else {}
    extract = text(page.get("extract"))
    canonical_title = text(page.get("title")) or text(name)
    return {
        "status": "found" if extract else "empty",
        "url": "https://zh.wikipedia.org/wiki/" + quote(canonical_title.replace(" ", "_"), safe="_"),
        "title": canonical_title,
        "extract": extract,
    }


def enrich_wikipedia_summary_leads(
    seeds: Sequence[Mapping[str, Any]], *, fetcher: Any = fetch_wikipedia_summary
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    by_status: dict[str, int] = {}
    with_terminal_leads: list[str] = []
    for raw in seeds:
        row = dict(raw)
        result = dict(fetcher(text(row.get("name"))))
        status = text(result.get("status")) or "unknown"
        by_status[status] = by_status.get(status, 0) + 1
        discovery_title = text(result.get("title"))
        if discovery_title and seed_tool.normalized_name(discovery_title) != seed_tool.normalized_name(row.get("name")):
            row["aliases"] = seed_tool.unique_strings([*(row.get("aliases") or []), discovery_title])
            row["expanded_aliases"] = seed_tool.unique_strings([*(row.get("expanded_aliases") or []), discovery_title])
        terms = source_cache.terminal_outcome_terms_from_text(result.get("extract"))
        if terms:
            row["summary_leads"] = [{
                "lead_terms": terms,
                "source_kind": "wikipedia_discovery_summary",
                "source_url": text(result.get("url")),
                "evidence_allowed": False,
            }]
            with_terminal_leads.append(text(row.get("name")))
        row["wikipedia_discovery"] = {
            "status": status,
            "title": discovery_title,
            "url": text(result.get("url")),
            "terminal_lead_count": len(terms),
            "evidence_allowed": False,
        }
        enriched.append(row)
    return enriched, {
        "enabled": True,
        "by_status": dict(sorted(by_status.items())),
        "objects_with_terminal_leads": sorted(with_terminal_leads),
    }


def intake_build_options(*, mode: str, request_key: str = "") -> tuple[dict[str, Any], str]:
    if mode not in INTAKE_MODES:
        raise IntakeOrchestratorError(f"unsupported intake mode: {mode}")
    if mode == "ensure":
        return {"intake_mode": mode, "cache_refresh": False}, ""
    effective_request_key = text(request_key) or uuid.uuid4().hex
    return {
        "intake_mode": mode,
        "intake_request_key": effective_request_key,
        "cache_refresh": mode == "refresh",
    }, effective_request_key


def apply_worker_runtime_root(job: Mapping[str, Any], *, runtime_root: str) -> dict[str, Any]:
    root = text(runtime_root).rstrip("/\\")
    if not root:
        return dict(job)
    normalized = dict(job)
    job_code = text(normalized.get("job_code")).lower()
    normalized["output_root"] = f"{root}/object_source_runs/{job_code}"
    normalized["page_cache_root"] = f"{root}/source_pages"
    normalized["seed_jsonl_path"] = f"{root}/embedded_seeds/{job_code}.jsonl"
    return normalized


def merge_query_profile_source_hints(
    seeds: Sequence[Mapping[str, Any]], *, profile_path: Path | None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if profile_path is None or not profile_path.exists():
        return [dict(row) for row in seeds], {"enabled": False, "matched_objects": []}
    by_name: dict[str, dict[str, Any]] = {}
    emperors = sorted({text(owner) for row in seeds for owner in row.get("target_emperors") or [] if text(owner)})
    for emperor in emperors:
        for profile_seed in worker.profile_seed_rows(profile_path=profile_path, emperor_name=emperor):
            by_name[seed_tool.normalized_name(profile_seed.get("name") or profile_seed.get("person_name"))] = profile_seed
    merged: list[dict[str, Any]] = []
    matched: list[str] = []
    for raw in seeds:
        row = dict(raw)
        profile_seed = by_name.get(seed_tool.normalized_name(row.get("name")))
        if profile_seed:
            row["source_hints"] = seed_tool.unique_strings([*(row.get("source_hints") or []), *(profile_seed.get("source_hints") or [])])
            row["source_target_refs"] = seed_tool.unique_strings([*(row.get("source_target_refs") or []), *(profile_seed.get("source_target_refs") or [])])
            row["query_profile_id"] = text(profile_seed.get("query_profile_id"))
            matched.append(text(row.get("name")))
        merged.append(row)
    return merged, {"enabled": True, "matched_objects": sorted(matched), "profile_path": str(profile_path)}


def select_intake_seeds(
    seeds: Sequence[Mapping[str, Any]], *, object_names: Sequence[str], emperor_names: Sequence[str],
    allow_new: bool = False, target_emperors: Sequence[str] = (),
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    requested_objects = {seed_tool.normalized_name(value): text(value) for value in object_names if text(value)}
    requested_emperors = {seed_tool.normalized_name(value): text(value) for value in emperor_names if text(value)}
    if not requested_objects and not requested_emperors:
        raise IntakeOrchestratorError("at least one --object or --emperor is required")

    selected: dict[str, dict[str, Any]] = {}
    matched_objects: set[str] = set()
    matched_emperors: set[str] = set()
    emperor_owner_keys = set(requested_emperors)
    for raw in seeds:
        if bool(raw.get("is_emperor")) and name_keys(raw) & requested_emperors.keys():
            emperor_owner_keys.add(seed_tool.normalized_name(raw.get("name")))
    for raw in seeds:
        seed = dict(raw)
        keys = name_keys(seed)
        object_matches = keys & requested_objects.keys()
        if object_matches:
            matched_objects.update(object_matches)
            selected[text(seed.get("object_code")) or text(seed.get("name"))] = seed

        target_keys = {seed_tool.normalized_name(value) for value in seed.get("target_emperors") or [] if text(value)}
        emperor_matches = target_keys & emperor_owner_keys
        if bool(seed.get("is_emperor")):
            emperor_matches |= keys & requested_emperors.keys()
        if emperor_matches:
            matched_emperors.update(keys & requested_emperors.keys())
            selected[text(seed.get("object_code")) or text(seed.get("name"))] = seed

    missing_objects = sorted(requested_objects[key] for key in requested_objects.keys() - matched_objects)
    missing_emperors = sorted(requested_emperors[key] for key in requested_emperors.keys() - matched_emperors)
    if allow_new:
        for name in missing_objects:
            seed = new_person_seed(name, target_emperors=target_emperors)
            selected[seed["object_code"]] = seed
        for name in missing_emperors:
            seed = new_person_seed(name, target_emperors=[name], is_emperor=True)
            selected[seed["object_code"]] = seed
        matched_objects.update(requested_objects.keys())
        matched_emperors.update(requested_emperors.keys())
        missing_objects = []
        missing_emperors = []
    if missing_objects or missing_emperors:
        raise IntakeOrchestratorError(
            "unresolved intake names: "
            + json.dumps({"objects": missing_objects, "emperors": missing_emperors}, ensure_ascii=False)
        )

    rows = seed_tool.dedupe_seeds(selected.values())
    report = {
        "schema": "retrieval_v3_intake_orchestrator_v1",
        "requested_objects": sorted(requested_objects.values()),
        "requested_emperors": sorted(requested_emperors.values()),
        "selected_seed_count": len(rows),
        "selected_objects": [text(row.get("name")) for row in rows],
        "requires_related_object_discovery": bool(requested_emperors),
        "next_stages": [
            "object_source_cache",
            "claim_plan",
            "atomic_claim_extraction",
            "pg_claim_cache",
            "event_group",
            *( ["related_object_discovery", "identity_review", "enqueue_discovered_objects"] if requested_emperors else [] ),
        ],
    }
    return rows, report


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def write_json(path: Path | None, payload: Mapping[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def ensure_canonical_people(*, dsn: str, seeds: Sequence[Mapping[str, Any]], schema_name: str) -> dict[str, int]:
    psycopg, dict_row = import_psycopg()
    counts = {"objects": 0, "object_names": 0, "target_objects": 0}
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw:
            cur = schema_cursor(raw, schema_name=schema_name)
            cur.execute("set local retrieval_v3.rebuild_bypass='on'")
            for seed in seeds:
                if text(seed.get("intake_source")) != "retrieval_v3_intake_orchestrator":
                    continue
                name = text(seed.get("name"))
                normalized = seed_tool.normalized_name(name)
                identity_key = f"intake|type|person|name|{normalized}"
                cur.execute(
                    "select id from retrieval_v3.objects where object_type='person' and identity_status='active' and normalized_name=%s order by id limit 1",
                    (normalized,),
                )
                existing = cur.fetchone()
                if existing:
                    object_id = int(existing["id"])
                else:
                    cur.execute(
                        """
                        insert into retrieval_v3.objects (
                            object_code, object_identity_key, canonical_name, normalized_name,
                            object_type, identity_status, identity_payload
                        ) values (%s,%s,%s,%s,'person','active',%s::jsonb)
                        on conflict (object_identity_key) do update set identity_status='active', updated_at=now()
                        returning id
                        """,
                        (
                            "OBJ-INTAKE-" + seed_tool.stable_hash(identity_key, length=16), identity_key,
                            name, normalized, json.dumps({"source": "retrieval_v3_intake_orchestrator"}, ensure_ascii=False),
                        ),
                    )
                    object_id = int(cur.fetchone()["id"])
                    counts["objects"] += 1
                cur.execute(
                    """
                    insert into retrieval_v3.object_names (
                        object_name_code, object_id, name_text, normalized_name, name_kind,
                        source, review_status, name_payload
                    ) values (%s,%s,%s,%s,'canonical','retrieval_v3_intake_orchestrator','accepted','{}'::jsonb)
                    on conflict on constraint rv3_object_names_name_uk do update set review_status='accepted'
                    """,
                    ("ONM-INTAKE-" + seed_tool.stable_hash([identity_key, normalized], length=16), object_id, name, normalized),
                )
                counts["object_names"] += 1
                for emperor in seed.get("target_emperors") or []:
                    cur.execute(
                        "select id,target_code from retrieval_v3.retrieval_targets where item_code='I5B' and target_status='active' and emperor_name=%s order by id desc limit 1",
                        (text(emperor),),
                    )
                    target = cur.fetchone()
                    if not target:
                        continue
                    cur.execute(
                        """
                        insert into retrieval_v3.target_objects (
                            target_object_code,target_id,object_id,scope_code,object_role,review_status,target_object_payload
                        ) values (%s,%s,%s,'item','','accepted',%s::jsonb)
                        on conflict on constraint rv3_target_objects_scope_uk do update set review_status='accepted',updated_at=now()
                        """,
                        (
                            "TOB-INTAKE-" + seed_tool.stable_hash([target["target_code"], identity_key], length=16),
                            int(target["id"]), object_id,
                            json.dumps({"source": "retrieval_v3_intake_orchestrator"}, ensure_ascii=False),
                        ),
                    )
                    counts["target_objects"] += 1
        conn.commit()
    return counts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create one idempotent retrieval_v3 intake job for objects or emperors.")
    parser.add_argument("--object", action="append", default=[])
    parser.add_argument("--emperor", action="append", default=[])
    parser.add_argument("--target-emperor", action="append", default=[], help="Associate newly introduced people with these emperor targets.")
    parser.add_argument("--seed-jsonl", type=Path, required=True)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--page-cache-root", type=Path, default=worker.DEFAULT_PAGE_CACHE_ROOT)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--priority", type=int, default=50)
    parser.add_argument("--mode", choices=INTAKE_MODES, default="ensure")
    parser.add_argument(
        "--request-key",
        default="",
        help="Idempotency key for supplement/refresh retries; generated when omitted.",
    )
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default="EMPEROR_EVAL_RETRIEVAL_V3_DSN")
    parser.add_argument("--pg-schema", default="retrieval_v3")
    parser.add_argument("--execute", action="store_true", help="Enqueue the object-source job; otherwise only write the plan.")
    parser.add_argument("--no-wikipedia-summary-leads", action="store_true")
    parser.add_argument("--query-profile-jsonl", type=Path, default=DEFAULT_QUERY_PROFILE_JSONL)
    parser.add_argument(
        "--worker-runtime-root",
        default="",
        help="Persist worker-native paths while retaining embedded seed rows.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.env_file is not None:
        load_env_file(args.env_file)
    worker_runtime_root = args.worker_runtime_root or os.environ.get("EMPEROR_EVAL_RETRIEVAL_V3_WORKER_RUNTIME_ROOT", "")
    seeds = seed_tool.rows_from_db(
        env_file=args.env_file,
        dsn_env=args.dsn_env,
        include_object_pool_aliases=True,
        source="retrieval-v3",
    )
    selected, report = select_intake_seeds(
        seeds, object_names=args.object, emperor_names=args.emperor,
        allow_new=True, target_emperors=args.target_emperor,
    )
    selected, report["query_profile_sources"] = merge_query_profile_source_hints(
        selected, profile_path=args.query_profile_jsonl
    )
    if not args.no_wikipedia_summary_leads:
        selected, report["wikipedia_discovery"] = enrich_wikipedia_summary_leads(selected)
    else:
        report["wikipedia_discovery"] = {"enabled": False}
    write_jsonl(args.seed_jsonl, selected)
    build_options, request_key = intake_build_options(mode=args.mode, request_key=args.request_key)
    job = worker.job_from_seed(
        seed_jsonl=args.seed_jsonl,
        output_root=args.output_root,
        page_cache_root=args.page_cache_root,
        priority=args.priority,
        build_options=build_options,
    )
    job = apply_worker_runtime_root(job, runtime_root=worker_runtime_root)
    report["intake_mode"] = args.mode
    report["request_key"] = request_key
    report["mode_effect"] = {
        "ensure": "Reuse the stable idempotent job when the selected seeds and options are unchanged.",
        "supplement": "Create one auditable uncovered-material pass without forcing cached pages to refresh.",
        "refresh": "Create one auditable pass and force source page cache refresh.",
    }[args.mode]
    report["job"] = job
    report["execute"] = bool(args.execute)
    if args.execute:
        report["enqueue"] = worker.enqueue_job(
            dsn=resolve_dsn(args.dsn_env), job=job, schema_name=args.pg_schema
        )
        report["canonical_people"] = ensure_canonical_people(
            dsn=resolve_dsn(args.dsn_env), seeds=selected, schema_name=args.pg_schema
        )
    write_json(args.output_json, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
