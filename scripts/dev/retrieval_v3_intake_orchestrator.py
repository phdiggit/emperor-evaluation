from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.dev.retrieval_v3_bootstrap import load_env_file, resolve_dsn
from scripts.dev import retrieval_v3_object_source_cache_seed as seed_tool
from scripts.dev import retrieval_v3_object_source_cache_worker as worker


class IntakeOrchestratorError(RuntimeError):
    pass


INTAKE_MODES = ("ensure", "supplement", "refresh")


def text(value: Any) -> str:
    return str(value or "").strip()


def name_keys(seed: Mapping[str, Any]) -> set[str]:
    values = [seed.get("name"), seed.get("normalized_name"), *(seed.get("aliases") or [])]
    return {seed_tool.normalized_name(value) for value in values if text(value)}


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


def select_intake_seeds(
    seeds: Sequence[Mapping[str, Any]], *, object_names: Sequence[str], emperor_names: Sequence[str]
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
            if target_keys & emperor_owner_keys:
                matched_emperors.update(requested_emperors.keys())
            selected[text(seed.get("object_code")) or text(seed.get("name"))] = seed

    missing_objects = sorted(requested_objects[key] for key in requested_objects.keys() - matched_objects)
    missing_emperors = sorted(requested_emperors[key] for key in requested_emperors.keys() - matched_emperors)
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create one idempotent retrieval_v3 intake job for objects or emperors.")
    parser.add_argument("--object", action="append", default=[])
    parser.add_argument("--emperor", action="append", default=[])
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    seeds = seed_tool.rows_from_db(
        env_file=args.env_file,
        dsn_env=args.dsn_env,
        include_object_pool_aliases=True,
        source="retrieval-v3",
    )
    selected, report = select_intake_seeds(seeds, object_names=args.object, emperor_names=args.emperor)
    write_jsonl(args.seed_jsonl, selected)
    build_options, request_key = intake_build_options(mode=args.mode, request_key=args.request_key)
    job = worker.job_from_seed(
        seed_jsonl=args.seed_jsonl,
        output_root=args.output_root,
        page_cache_root=args.page_cache_root,
        priority=args.priority,
        build_options=build_options,
    )
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
        if args.env_file is not None:
            load_env_file(args.env_file)
        report["enqueue"] = worker.enqueue_job(
            dsn=resolve_dsn(args.dsn_env), job=job, schema_name=args.pg_schema
        )
    write_json(args.output_json, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
