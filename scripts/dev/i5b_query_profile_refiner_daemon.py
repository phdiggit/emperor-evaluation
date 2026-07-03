from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.i5b_query_profile_refiner import (  # noqa: E402
    DEFAULT_TARGET_STATUSES,
    build_refinement_report,
    load_profile_rows,
    render_markdown as render_refinements_markdown,
)
from scripts.dev.i5b_source_pack_status import (  # noqa: E402
    DEFAULT_ALL_LIST,
    build_status_report,
    load_jobs,
    load_packs,
    load_persons,
    load_profiles,
    render_markdown as render_status_markdown,
    _default_source_pack_root,
)
from scripts.dev.source_excerpt_pool_lib.common import (  # noqa: E402
    DEFAULT_PROFILE,
    DEFAULT_WORKFLOW_CODE,
    load_source_excerpt_pool_paths,
    normalize_workflow_code,
    workflow_slug,
)


def iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def log(message: str) -> None:
    print(f"{iso_now()} {message}", flush=True)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(path)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)


def source_pack_status_stem(workflow_code: str | None) -> str:
    return f"{workflow_slug(workflow_code)}_source_pack_status"


def refinement_stem(workflow_code: str | None) -> str:
    return f"{workflow_slug(workflow_code)}_query_profile_refinements"


def daemon_status_name(workflow_code: str | None) -> str:
    return f"{workflow_slug(workflow_code)}_query_profile_refiner_daemon.status.json"


def run_once(
    *,
    profile_path: Path,
    all_list: Path,
    source_pack_root: Path,
    jobs_dir: Path,
    logs_dir: Path,
    output_dir: Path,
    target_statuses: list[str],
    max_queries_per_object: int,
    include_adjacent: bool = False,
    workflow_code: str = DEFAULT_WORKFLOW_CODE,
) -> dict[str, Any]:
    started = time.monotonic()
    normalized_workflow_code = normalize_workflow_code(workflow_code)
    profiles_for_status = load_profiles(profile_path, workflow_code=normalized_workflow_code) if profile_path.exists() else {}
    status_report = build_status_report(
        persons=load_persons(all_list) if all_list.exists() else [],
        profiles=profiles_for_status,
        jobs=load_jobs(jobs_dir, logs_dir),
        packs=load_packs(source_pack_root),
        workflow_code=normalized_workflow_code,
    )
    profiles = load_profile_rows(profile_path, workflow_code=normalized_workflow_code) if profile_path.exists() else {}
    refinement_report = build_refinement_report(
        profiles=profiles,
        status_rows=status_report["rows"],
        workflow_code=normalized_workflow_code,
        target_statuses=target_statuses,
        max_queries_per_object=max_queries_per_object,
        include_adjacent=include_adjacent,
    )
    status_stem = source_pack_status_stem(normalized_workflow_code)
    refinements_stem = refinement_stem(normalized_workflow_code)
    write_json(output_dir / f"{status_stem}.json", status_report)
    write_text(output_dir / f"{status_stem}.md", render_status_markdown(status_report))
    write_json(output_dir / f"{refinements_stem}.json", refinement_report)
    write_text(output_dir / f"{refinements_stem}.md", render_refinements_markdown(refinement_report))
    daemon_status = {
        "status": "ok",
        "workflow_code": normalized_workflow_code,
        "generated_at": iso_now(),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "profile_path": str(profile_path),
        "source_pack_root": str(source_pack_root),
        "jobs_dir": str(jobs_dir),
        "logs_dir": str(logs_dir),
        "output_dir": str(output_dir),
        "status_totals": status_report.get("totals", {}),
        "refinement_totals": refinement_report.get("totals", {}),
    }
    write_json(output_dir / daemon_status_name(normalized_workflow_code), daemon_status)
    return daemon_status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Periodically refresh I5B source-pack status and query-profile refinement reports.")
    parser.add_argument("--profile", type=Path, default=None)
    parser.add_argument("--workflow-code", default=DEFAULT_WORKFLOW_CODE, help="Workflow/subitem code for report metadata and output file stems.")
    parser.add_argument("--all-list", type=Path, default=DEFAULT_ALL_LIST)
    parser.add_argument("--source-pack-root", type=Path, default=None)
    parser.add_argument("--jobs-dir", type=Path, default=None)
    parser.add_argument("--logs-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--status", action="append", default=[], help="Refiner action_status; defaults to fetched_needs_profile_work.")
    parser.add_argument("--max-queries-per-object", type=int, default=6)
    parser.add_argument("--include-adjacent", action="store_true")
    parser.add_argument("--interval-seconds", type=float, default=900)
    parser.add_argument("--once", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.interval_seconds <= 0:
        raise SystemExit("--interval-seconds must be > 0")
    workflow_code = normalize_workflow_code(args.workflow_code)
    source_paths = load_source_excerpt_pool_paths(workflow_code=workflow_code)
    profile_path = args.profile or source_paths.get("query_profile") or DEFAULT_PROFILE
    source_pack_root = args.source_pack_root or source_paths.get("source_pack_root") or _default_source_pack_root(workflow_code=workflow_code)
    jobs_dir = args.jobs_dir or source_paths.get("jobs_dir") or source_pack_root.parent / "jobs"
    logs_dir = args.logs_dir or source_paths.get("logs_dir") or source_pack_root.parent / "logs"
    target_statuses = args.status or list(DEFAULT_TARGET_STATUSES)
    log(f"refiner daemon started workflow={workflow_code} output={args.output_dir} interval={args.interval_seconds}")
    while True:
        try:
            status = run_once(
                profile_path=profile_path,
                all_list=args.all_list,
                source_pack_root=source_pack_root,
                jobs_dir=jobs_dir,
                logs_dir=logs_dir,
                output_dir=args.output_dir,
                workflow_code=workflow_code,
                target_statuses=target_statuses,
                max_queries_per_object=args.max_queries_per_object,
                include_adjacent=args.include_adjacent,
            )
            log(
                "refiner refreshed "
                f"status={status['status']} "
                f"persons={status['refinement_totals'].get('persons', 0)} "
                f"suggestions={status['refinement_totals'].get('patch_suggestions', 0)}"
            )
        except Exception as exc:
            error_status = {"status": "error", "workflow_code": workflow_code, "generated_at": iso_now(), "error": repr(exc)}
            write_json(args.output_dir / daemon_status_name(workflow_code), error_status)
            log(f"refiner error={exc!r}")
            if args.once:
                return 1
        if args.once:
            return 0
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
