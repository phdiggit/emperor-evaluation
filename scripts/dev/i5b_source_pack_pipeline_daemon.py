from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.i5b_query_profile_refiner import (  # noqa: E402
    DEFAULT_TARGET_STATUSES,
    build_refinement_report,
    load_profile_rows,
)
from scripts.dev.i5b_source_pack_status import (  # noqa: E402
    DEFAULT_ALL_LIST,
    build_status_report,
    load_jobs,
    load_packs,
    load_persons,
    load_profiles,
    _default_source_pack_root,
)
from scripts.dev.source_excerpt_pool_lib.common import (  # noqa: E402
    DEFAULT_PROFILE,
    DEFAULT_WORKFLOW_CODE,
    load_source_excerpt_pool_paths,
    normalize_workflow_code,
    workflow_slug,
)


STATE_SCHEMA_VERSION = 1


def iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def log(message: str) -> None:
    print(f"{iso_now()} {message}", flush=True)


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z_.\-\u4e00-\u9fff]+", "_", value).strip("._-")
    return cleaned or "i5b_source_pack"


def workflow_file_stem(workflow_code: str) -> str:
    return f"{workflow_slug(workflow_code)}_source_pack"


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    lines = [json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows]
    _atomic_write_text(path, "\n".join(lines).rstrip() + ("\n" if lines else ""))


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": STATE_SCHEMA_VERSION, "submissions": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {"schema_version": STATE_SCHEMA_VERSION, "submissions": []}
    submissions = payload.get("submissions")
    if not isinstance(submissions, list):
        payload["submissions"] = []
    payload["schema_version"] = STATE_SCHEMA_VERSION
    return payload


def save_state(path: Path, state: Mapping[str, Any]) -> None:
    write_json(path, state)


def _add_unique(values: list[str], value: Any) -> bool:
    cleaned = " ".join(str(value).split())
    if cleaned and cleaned not in values:
        values.append(cleaned)
        return True
    return False


def patch_has_work(patch: Mapping[str, Any]) -> bool:
    aliases = patch.get("merge_object_search_aliases")
    return bool(
        patch.get("append_query_bundles")
        or patch.get("append_source_targets")
        or (isinstance(aliases, Mapping) and any(aliases.values()))
    )


def apply_profile_patch(profile: Mapping[str, Any], patch: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    updated = json.loads(json.dumps(profile, ensure_ascii=False))
    stats = {"query_bundles": 0, "source_targets": 0, "object_search_aliases": 0}

    query_bundles = updated.setdefault("query_bundles", [])
    if not isinstance(query_bundles, list):
        query_bundles = []
        updated["query_bundles"] = query_bundles
    for query in patch.get("append_query_bundles") or []:
        if _add_unique(query_bundles, query):
            stats["query_bundles"] += 1

    source_targets = updated.setdefault("source_targets", [])
    if not isinstance(source_targets, list):
        source_targets = []
        updated["source_targets"] = source_targets
    for target in patch.get("append_source_targets") or []:
        if _add_unique(source_targets, target):
            stats["source_targets"] += 1

    alias_map = updated.setdefault("object_search_aliases", {})
    if not isinstance(alias_map, dict):
        alias_map = {}
        updated["object_search_aliases"] = alias_map
    raw_aliases = patch.get("merge_object_search_aliases")
    if isinstance(raw_aliases, Mapping):
        for object_name, aliases in raw_aliases.items():
            key = str(object_name).strip()
            if not key:
                continue
            current = alias_map.get(key, [])
            if isinstance(current, str):
                current_values = [current]
            elif isinstance(current, list):
                current_values = [str(value) for value in current if str(value).strip()]
            else:
                current_values = []
            for alias in aliases or []:
                if _add_unique(current_values, alias):
                    stats["object_search_aliases"] += 1
            if current_values:
                alias_map[key] = current_values

    return updated, stats


def patch_fingerprint(person: str, patch: Mapping[str, Any]) -> str:
    payload = {"person": person, "patch": patch}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:12]


def state_submitted_fingerprints(
    state: Mapping[str, Any],
    *,
    workflow_code: str = DEFAULT_WORKFLOW_CODE,
) -> set[tuple[str, str, str, str]]:
    workflow_code = normalize_workflow_code(workflow_code)
    submitted: set[tuple[str, str, str, str]] = set()
    for item in state.get("submissions") or []:
        if not isinstance(item, Mapping):
            continue
        item_workflow_code = normalize_workflow_code(item.get("workflow_code") or DEFAULT_WORKFLOW_CODE)
        if item_workflow_code != workflow_code:
            continue
        person = str(item.get("person") or "")
        kind = str(item.get("kind") or "")
        fingerprint = str(item.get("fingerprint") or "")
        if person and kind and fingerprint:
            submitted.add((workflow_code, person, kind, fingerprint))
    return submitted


def state_submission_counts(
    state: Mapping[str, Any],
    *,
    kind: str,
    workflow_code: str = DEFAULT_WORKFLOW_CODE,
) -> dict[str, int]:
    workflow_code = normalize_workflow_code(workflow_code)
    counts: dict[str, int] = {}
    for item in state.get("submissions") or []:
        if not isinstance(item, Mapping) or item.get("kind") != kind:
            continue
        if normalize_workflow_code(item.get("workflow_code") or DEFAULT_WORKFLOW_CODE) != workflow_code:
            continue
        person = str(item.get("person") or "").strip()
        if person:
            counts[person] = counts.get(person, 0) + 1
    return counts


def latest_profile_overrides(
    state: Mapping[str, Any],
    *,
    workflow_code: str = DEFAULT_WORKFLOW_CODE,
) -> dict[str, Path]:
    workflow_code = normalize_workflow_code(workflow_code)
    overrides: dict[str, Path] = {}
    for item in state.get("submissions") or []:
        if not isinstance(item, Mapping):
            continue
        if normalize_workflow_code(item.get("workflow_code") or DEFAULT_WORKFLOW_CODE) != workflow_code:
            continue
        person = str(item.get("person") or "").strip()
        profile_path = str(item.get("profile_path") or "").strip()
        if person and profile_path and Path(profile_path).exists():
            overrides[person] = Path(profile_path)
    return overrides


def load_effective_profiles(
    base_profile_path: Path,
    state: Mapping[str, Any],
    *,
    workflow_code: str = DEFAULT_WORKFLOW_CODE,
) -> dict[str, dict[str, Any]]:
    workflow_code = normalize_workflow_code(workflow_code)
    profiles = load_profile_rows(base_profile_path, workflow_code=workflow_code) if base_profile_path.exists() else {}
    for person, profile_path in latest_profile_overrides(state, workflow_code=workflow_code).items():
        try:
            override = load_profile_rows(profile_path, workflow_code=workflow_code).get(person)
        except Exception:
            override = None
        if override:
            profiles[person] = override
    return profiles


def _existing_output_names(jobs_dir: Path, source_pack_root: Path) -> set[str]:
    names: set[str] = set()
    if jobs_dir.exists():
        for path in jobs_dir.iterdir():
            if not path.is_file():
                continue
            name = path.name
            for suffix in (".json.running", ".json.failed", ".json.done", ".json"):
                if name.endswith(suffix):
                    names.add(name[: -len(suffix)])
                    break
    if source_pack_root.exists():
        names.update(path.name for path in source_pack_root.iterdir() if path.is_dir())
    return names


def next_output_name(
    person: str,
    kind: str,
    fingerprint: str,
    existing_names: set[str],
    *,
    workflow_code: str = DEFAULT_WORKFLOW_CODE,
) -> str:
    workflow_prefix = workflow_slug(workflow_code)
    base = safe_name(f"{workflow_prefix}_pipeline_{kind}_{datetime.now().astimezone():%Y%m%d}_{person}_{fingerprint}")
    output_name = base
    index = 2
    while output_name in existing_names:
        output_name = f"{base}_{index}"
        index += 1
    existing_names.add(output_name)
    return output_name


def submit_job(
    *,
    jobs_dir: Path,
    output_name: str,
    person: str,
    profile_path: Path,
    workflow_code: str,
    include_adjacent: bool,
    fetch_defaults: Mapping[str, Any],
    pipeline: Mapping[str, Any],
) -> Path:
    payload = {
        "person": person,
        "profile": str(profile_path),
        "output_name": output_name,
        "workflow_code": normalize_workflow_code(workflow_code),
        "include_adjacent": include_adjacent,
        **dict(fetch_defaults),
        "pipeline": dict(pipeline),
    }
    job_path = jobs_dir / f"{output_name}.json"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    temp_path = job_path.with_name(job_path.name + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(job_path)
    return job_path


def _row_by_person(status_report: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in status_report.get("rows") or []:
        if isinstance(row, dict) and row.get("person"):
            rows[str(row["person"])] = row
    return rows


def _build_status(
    *,
    profile_path: Path,
    all_list: Path,
    source_pack_root: Path,
    jobs_dir: Path,
    logs_dir: Path,
    workflow_code: str = DEFAULT_WORKFLOW_CODE,
) -> dict[str, Any]:
    return build_status_report(
        persons=load_persons(all_list) if all_list.exists() else [],
        profiles=load_profiles(profile_path, workflow_code=workflow_code) if profile_path.exists() else {},
        jobs=load_jobs(jobs_dir, logs_dir),
        packs=load_packs(source_pack_root),
        workflow_code=workflow_code,
    )


def _fetch_defaults(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "pages_per_query": args.pages_per_query,
        "context_chars": args.context_chars,
        "max_passages_per_page": args.max_passages_per_page,
        "request_delay": args.request_delay,
        "max_retries": args.max_retries,
        "retry_backoff": args.retry_backoff,
        "max_retry_wait": args.max_retry_wait,
        "max_consecutive_errors": args.max_consecutive_errors,
        "max_wall_seconds": args.max_wall_seconds,
        "max_queries_per_object": args.fetch_max_queries_per_object,
        "no_cache": args.no_cache,
    }


def _append_submission(state: dict[str, Any], submission: Mapping[str, Any]) -> None:
    submissions = state.setdefault("submissions", [])
    if isinstance(submissions, list):
        submissions.append(dict(submission))


def summarize_actions(actions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    action_counts: Counter[str] = Counter()
    people_by_status: dict[str, list[str]] = {}
    people_by_kind: dict[str, list[str]] = {}
    for action in actions:
        status = str(action.get("status") or "").strip()
        kind = str(action.get("kind") or "").strip()
        person = str(action.get("person") or "").strip()
        if status:
            action_counts[status] += 1
        if person and status:
            people_by_status.setdefault(status, []).append(person)
        if person and kind:
            people_by_kind.setdefault(kind, []).append(person)
    return {
        "action_counts": dict(sorted(action_counts.items())),
        "people_by_status": {key: sorted(set(values)) for key, values in sorted(people_by_status.items())},
        "people_by_kind": {key: sorted(set(values)) for key, values in sorted(people_by_kind.items())},
        "submitted_people": sorted(set(people_by_status.get("submitted", []))),
        "round_capped_people": sorted(set(people_by_status.get("skip_round_cap", []))),
        "duplicate_people": sorted(set(people_by_status.get("skip_duplicate", []))),
        "no_effect_people": sorted(set(people_by_status.get("skip_no_effect", []))),
    }


def run_once(args: argparse.Namespace) -> dict[str, Any]:
    workflow_code = normalize_workflow_code(getattr(args, "workflow_code", DEFAULT_WORKFLOW_CODE))
    source_paths = load_source_excerpt_pool_paths(workflow_code=workflow_code)
    profile_path = args.profile or source_paths.get("query_profile") or DEFAULT_PROFILE
    source_pack_root = args.source_pack_root or source_paths.get("source_pack_root") or _default_source_pack_root(workflow_code=workflow_code)
    jobs_dir = args.jobs_dir or source_paths.get("jobs_dir") or source_pack_root.parent / "jobs"
    logs_dir = args.logs_dir or source_paths.get("logs_dir") or source_pack_root.parent / "logs"
    output_dir = args.output_dir
    derived_dir = args.derived_profile_dir or output_dir / "derived-profiles"
    file_stem = workflow_file_stem(workflow_code)
    state_path = args.state_file or output_dir / f"{file_stem}_pipeline_state.json"
    report_path = output_dir / f"{file_stem}_pipeline_report.json"

    started = time.monotonic()
    state = load_state(state_path)
    submitted = state_submitted_fingerprints(state, workflow_code=workflow_code)
    existing_names = _existing_output_names(jobs_dir, source_pack_root)
    fetch_defaults = _fetch_defaults(args)

    status_report = _build_status(
        profile_path=profile_path,
        all_list=args.all_list,
        source_pack_root=source_pack_root,
        jobs_dir=jobs_dir,
        logs_dir=logs_dir,
        workflow_code=workflow_code,
    )
    effective_profiles = load_effective_profiles(profile_path, state, workflow_code=workflow_code)
    refinement_report = build_refinement_report(
        profiles=effective_profiles,
        status_rows=status_report["rows"],
        workflow_code=workflow_code,
        target_statuses=args.status or list(DEFAULT_TARGET_STATUSES),
        max_queries_per_object=args.refine_max_queries_per_object,
        include_adjacent=args.include_adjacent,
    )
    status_rows = _row_by_person(status_report)
    actions: list[dict[str, Any]] = []
    submitted_count = 0

    def can_submit() -> bool:
        return args.max_jobs_per_run <= 0 or submitted_count < args.max_jobs_per_run

    if args.submit_prepared:
        base_profiles = load_profile_rows(profile_path, workflow_code=workflow_code) if profile_path.exists() else {}
        for person, row in status_rows.items():
            if not can_submit():
                break
            if row.get("action_status") != "prepared_not_submitted":
                continue
            profile = base_profiles.get(person)
            if not profile:
                continue
            fingerprint = patch_fingerprint(person, {"prepared_not_submitted": profile.get("query_profile_id")})
            key = (workflow_code, person, "initial", fingerprint)
            if key in submitted:
                actions.append({"person": person, "kind": "initial", "status": "skip_duplicate", "fingerprint": fingerprint})
                continue
            output_name = next_output_name(person, "initial", fingerprint, existing_names, workflow_code=workflow_code)
            job_path = submit_job(
                jobs_dir=jobs_dir,
                output_name=output_name,
                person=person,
                profile_path=profile_path,
                workflow_code=workflow_code,
                include_adjacent=args.include_adjacent,
                fetch_defaults=fetch_defaults,
                pipeline={"kind": "initial", "fingerprint": fingerprint, "submitted_at": iso_now()},
            )
            submission = {
                "person": person,
                "workflow_code": workflow_code,
                "kind": "initial",
                "fingerprint": fingerprint,
                "profile_path": str(profile_path),
                "output_name": output_name,
                "job_path": str(job_path),
                "submitted_at": iso_now(),
            }
            _append_submission(state, submission)
            submitted.add(key)
            submitted_count += 1
            actions.append({**submission, "status": "submitted"})

    if args.submit_refinements:
        refine_counts = state_submission_counts(state, kind="refine", workflow_code=workflow_code)
        for refinement in refinement_report.get("refinements") or []:
            if not can_submit():
                break
            if not isinstance(refinement, Mapping):
                continue
            person = str(refinement.get("person") or "").strip()
            if person and refine_counts.get(person, 0) >= args.max_refine_rounds_per_person:
                actions.append(
                    {
                        "person": person,
                        "kind": "refine",
                        "status": "skip_round_cap",
                        "submitted_rounds": refine_counts.get(person, 0),
                        "max_refine_rounds_per_person": args.max_refine_rounds_per_person,
                    }
                )
                continue
            profile = effective_profiles.get(person)
            patch = refinement.get("profile_patch_candidate")
            if not person or not profile or not isinstance(patch, Mapping) or not patch_has_work(patch):
                continue
            fingerprint = patch_fingerprint(person, patch)
            key = (workflow_code, person, "refine", fingerprint)
            if key in submitted:
                actions.append({"person": person, "kind": "refine", "status": "skip_duplicate", "fingerprint": fingerprint})
                continue
            patched_profile, stats = apply_profile_patch(profile, patch)
            if not any(stats.values()):
                actions.append({"person": person, "kind": "refine", "status": "skip_no_effect", "fingerprint": fingerprint})
                continue
            output_name = next_output_name(person, "refine", fingerprint, existing_names, workflow_code=workflow_code)
            derived_profile_path = derived_dir / f"{output_name}.jsonl"
            patched_profile["note"] = "采集层自动派生 profile；仅供下一轮 source pack 抓取，不写回 canonical query profile。"
            write_jsonl(derived_profile_path, [patched_profile])
            job_path = submit_job(
                jobs_dir=jobs_dir,
                output_name=output_name,
                person=person,
                profile_path=derived_profile_path,
                workflow_code=workflow_code,
                include_adjacent=args.include_adjacent,
                fetch_defaults=fetch_defaults,
                pipeline={
                    "kind": "refine",
                    "fingerprint": fingerprint,
                    "source_pack": status_rows.get(person, {}).get("pack_output_name", ""),
                    "submitted_at": iso_now(),
                },
            )
            submission = {
                "person": person,
                "workflow_code": workflow_code,
                "kind": "refine",
                "fingerprint": fingerprint,
                "profile_path": str(derived_profile_path),
                "output_name": output_name,
                "job_path": str(job_path),
                "patch_stats": stats,
                "submitted_at": iso_now(),
            }
            _append_submission(state, submission)
            submitted.add(key)
            refine_counts[person] = refine_counts.get(person, 0) + 1
            submitted_count += 1
            actions.append({**submission, "status": "submitted"})

    save_state(state_path, state)
    report = {
        "schema_version": STATE_SCHEMA_VERSION,
        "generated_at": iso_now(),
        "workflow_code": workflow_code,
        "status": "ok",
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "profile_path": str(profile_path),
        "source_pack_root": str(source_pack_root),
        "jobs_dir": str(jobs_dir),
        "logs_dir": str(logs_dir),
        "state_file": str(state_path),
        "derived_profile_dir": str(derived_dir),
        "submitted_jobs": submitted_count,
        "status_totals": status_report.get("totals", {}),
        "status_control_summary": status_report.get("control_summary", {}),
        "refinement_totals": refinement_report.get("totals", {}),
        "control_summary": summarize_actions(actions),
        "actions": actions,
    }
    write_json(report_path, report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Continuously submit source-pack jobs from status and refinement reports.")
    parser.add_argument("--workflow-code", default=DEFAULT_WORKFLOW_CODE, help="Workflow/subitem code for job, state, and report metadata.")
    parser.add_argument("--profile", type=Path, default=None)
    parser.add_argument("--all-list", type=Path, default=DEFAULT_ALL_LIST)
    parser.add_argument("--source-pack-root", type=Path, default=None)
    parser.add_argument("--jobs-dir", type=Path, default=None)
    parser.add_argument("--logs-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--state-file", type=Path, default=None)
    parser.add_argument("--derived-profile-dir", type=Path, default=None)
    parser.add_argument("--status", action="append", default=[], help="Refiner action_status; defaults to fetched_needs_profile_work.")
    parser.add_argument("--submit-prepared", action="store_true", help="Submit jobs for prepared_not_submitted profiles.")
    parser.add_argument("--submit-refinements", action="store_true", help="Apply mechanical refinement patches to derived profiles and submit jobs.")
    parser.add_argument("--max-jobs-per-run", type=int, default=0, help="0 means no per-cycle cap.")
    parser.add_argument("--max-refine-rounds-per-person", type=int, default=2)
    parser.add_argument("--include-adjacent", action="store_true")
    parser.add_argument("--refine-max-queries-per-object", type=int, default=6)
    parser.add_argument("--fetch-max-queries-per-object", type=int, default=4)
    parser.add_argument("--pages-per-query", type=int, default=6)
    parser.add_argument("--context-chars", type=int, default=420)
    parser.add_argument("--max-passages-per-page", type=int, default=4)
    parser.add_argument("--request-delay", type=float, default=1.0)
    parser.add_argument("--max-retries", type=int, default=4)
    parser.add_argument("--retry-backoff", type=float, default=3.0)
    parser.add_argument("--max-retry-wait", type=float, default=30)
    parser.add_argument("--max-consecutive-errors", type=int, default=8)
    parser.add_argument("--max-wall-seconds", type=float, default=3600)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--interval-seconds", type=float, default=900)
    parser.add_argument("--once", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.workflow_code = normalize_workflow_code(args.workflow_code)
    if not args.submit_prepared and not args.submit_refinements:
        raise SystemExit("enable at least one of --submit-prepared or --submit-refinements")
    if args.interval_seconds <= 0:
        raise SystemExit("--interval-seconds must be > 0")
    log(f"pipeline daemon started workflow={args.workflow_code} output={args.output_dir} interval={args.interval_seconds}")
    while True:
        try:
            report = run_once(args)
            log(
                "pipeline refreshed "
                f"submitted={report['submitted_jobs']} "
                f"actions={len(report['actions'])} "
                f"queued={report['status_totals'].get('by_action_status', {}).get('fetch_queued', 0)} "
                f"running={report['status_totals'].get('by_action_status', {}).get('fetch_running', 0)}"
            )
        except Exception as exc:
            args.output_dir.mkdir(parents=True, exist_ok=True)
            write_json(
                args.output_dir / f"{workflow_file_stem(args.workflow_code)}_pipeline_report.json",
                {"status": "error", "generated_at": iso_now(), "workflow_code": args.workflow_code, "error": repr(exc)},
            )
            log(f"pipeline error={exc!r}")
            if args.once:
                return 1
        if args.once:
            return 0
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
