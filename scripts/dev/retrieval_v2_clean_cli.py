from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.dev import retrieval_v2_discovery_profiles as discovery_profiles
from scripts.dev import retrieval_v2_batch_taskgen as batch_taskgen
from scripts.dev import retrieval_v2_contracts as contracts
from scripts.dev import retrieval_v2_runtime_paths as runtime_paths
from scripts.dev import retrieval_v2_source_candidates as source_candidates
from scripts.dev import retrieval_v2_task_skeleton as task_skeleton
from scripts.dev import retrieval_v2_taskgen_preseed as taskgen_preseed
from scripts.dev import retrieval_v2_clean_runner as runner
from scripts.dev.retrieval_v2_run_events import RunEventLogger


TARGET_METADATA_KEYS = (
    "period",
    "title",
    "temple_name",
    "posthumous_name",
    "source_targets",
    "query_bundles",
    "object_search_aliases",
    "expected_lane_outcomes",
    "retrieval_profile_id",
    "retrieval_profile_source_group",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run retrieval_v2 clean taskgen/candidate/alias/judge pipeline.")
    parser.add_argument("--task", type=Path, action="append", default=[], help="Existing task envelope JSON; repeatable.")
    parser.add_argument("--emperor", action="append", default=[], help="Emperor name for live DB-driven taskgen; repeatable.")
    parser.add_argument("--item-code", default="I5B")
    parser.add_argument("--rule-code", default="appointment_delegation")
    parser.add_argument("--contract-code", default=None)
    parser.add_argument("--env-file", type=Path)
    shadow_group = parser.add_mutually_exclusive_group()
    shadow_group.add_argument(
        "--i5b-wide-shadow-pilot",
        action="store_true",
        help="Mark this run as an I5B-wide shadow pilot. Output stays in its run_root and must not be used as a formal consumption source.",
    )
    shadow_group.add_argument(
        "--i5b-item-wide-shadow-pilot",
        action="store_true",
        help=(
            "Mark this run as an I5B item-wide shadow pilot. The judge should build a broad "
            "I5B material pool rather than a single-rule primary package; output stays in run_root."
        ),
    )
    shadow_group.add_argument(
        "--personnel-political-wide-shadow-pilot",
        action="store_true",
        help=(
            "Mark this run as a personnel_political_wide shadow pilot. It reuses the I5B item-wide "
            "package shell while emitting political_action_v1 facts and cross-item future hints."
        ),
    )
    parser.add_argument(
        "--discovery-profile",
        type=Path,
        action="append",
        default=[],
        help="Reusable retrieval_v2 discovery profile JSON; repeatable. Matching profiles skip Codex taskgen.",
    )
    parser.add_argument(
        "--discovery-profile-root",
        type=Path,
        action="append",
        default=[],
        help="Directory to read/write reusable discovery profiles; repeatable.",
    )
    parser.add_argument(
        "--allow-cross-rule-discovery-profile",
        action="store_true",
        help="Allow profile reuse across rules for the same target after applying the current rule skeleton.",
    )
    parser.add_argument("--target-dsn-env", default=runner.DEFAULT_TARGET_DSN_ENV)
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--runtime-paths-config", type=Path, help="Optional runtime_paths.json for run/cache defaults.")
    parser.add_argument(
        "--use-local-runtime",
        action="store_true",
        help="Force repo-local tmp/.tmp runtime defaults instead of NAS/env runtime config.",
    )
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--taskgen-timeout", type=int, default=1800)
    parser.add_argument(
        "--taskgen-batch-size",
        type=int,
        default=1,
        help="Batch live skeleton discovery for this many no-profile emperor targets per Codex taskgen call; 1 keeps fastest per-target parallelism.",
    )
    parser.add_argument(
        "--taskgen-presearch",
        action="store_true",
        help="Pre-search public Wikisource pages by script and feed them into taskgen; keeps old source packs/object pool forbidden.",
    )
    parser.add_argument(
        "--taskgen-presearch-with-codex-search",
        action="store_true",
        help="Keep Codex web search enabled after script presearch; default presearch mode disables Codex search to reduce wall time.",
    )
    parser.add_argument("--taskgen-presearch-queries", type=int, default=4)
    parser.add_argument("--taskgen-presearch-pages-per-query", type=int, default=3)
    parser.add_argument("--taskgen-presearch-timeout", type=int, default=8)
    parser.add_argument(
        "--no-taskgen-object-source-presearch",
        action="store_true",
        help="Disable script object-name source expansion after presearch taskgen.",
    )
    parser.add_argument("--taskgen-object-source-max-objects", type=int, default=12)
    parser.add_argument("--taskgen-object-source-pages-per-object", type=int, default=2)
    parser.add_argument("--taskgen-object-source-hint-limit", type=int, default=2)
    parser.add_argument(
        "--emp-metadata-dsn-env",
        default="EMPEROR_EVAL_PG_DSN",
        help="Optional source DB env var for public.emps title/period hints used only by --taskgen-presearch.",
    )
    parser.add_argument("--judge-timeout", type=int, default=1800)
    parser.add_argument("--candidate-timeout", type=int, default=15)
    parser.add_argument(
        "--source-cache-root",
        type=Path,
        default=None,
        help="Shared raw source page cache; defaults to runtime path config unless --run-local-source-cache is set.",
    )
    parser.add_argument(
        "--run-local-source-cache",
        action="store_true",
        help="Use the run directory source_cache instead of the shared raw source page cache.",
    )
    parser.add_argument("--context-chars", type=int, default=260)
    parser.add_argument("--max-slices-per-object", type=int, default=8)
    parser.add_argument("--max-alias-refine-rounds", type=int, default=2)
    parser.add_argument(
        "--candidate-source-refine-rounds",
        type=int,
        default=None,
        help="Auto-search source pages for candidate objects without slices; default is 1 in --taskgen-presearch mode, otherwise 0.",
    )
    parser.add_argument("--candidate-source-refine-max-objects", type=int, default=8)
    parser.add_argument("--candidate-source-refine-pages-per-object", type=int, default=2)
    parser.add_argument("--candidate-source-refine-source-hint-limit", type=int, default=2)
    parser.add_argument(
        "--candidate-source-refine-object",
        action="append",
        default=[],
        help="Force candidate source refinement to search this object name even when candidate coverage has no gap; repeatable.",
    )
    parser.add_argument(
        "--judge-shard-size",
        type=int,
        default=8,
        help="Maximum objects per judge shard; use 0 to force a single judge call.",
    )
    parser.add_argument(
        "--judge-shard-workers",
        type=int,
        default=None,
        help=(
            "Maximum parallel Codex judge shard workers per target. "
            "Defaults to 4 for item-wide/personnel-political shadow packages, otherwise 2."
        ),
    )
    parser.add_argument("--skip-fetch-errors", action="store_true")
    parser.add_argument("--skip-judge", action="store_true", help="Stop after candidates and alias refinement.")
    parser.add_argument("--no-taskgen-search", action="store_true", help="Disable web search in live taskgen.")
    parser.add_argument(
        "--no-stream-taskgen",
        action="store_true",
        help="Use the old staged mode: finish all taskgen calls before candidate/judge.",
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        help="Echo run_events.jsonl stage updates to stderr while preserving final JSON on stdout.",
    )
    return parser


def _source_cache_root(args: argparse.Namespace) -> Path | None:
    return None if args.run_local_source_cache else args.source_cache_root


def _candidate_source_refine_rounds(args: argparse.Namespace) -> int:
    if args.candidate_source_refine_rounds is not None:
        return max(0, int(args.candidate_source_refine_rounds))
    if args.taskgen_presearch and not args.no_taskgen_object_source_presearch:
        return 1
    return 0


def _effective_judge_shard_workers(args: argparse.Namespace) -> int:
    if getattr(args, "judge_shard_workers", None) is not None:
        return max(1, int(args.judge_shard_workers))
    if _is_item_wide_shadow_mode(_shadow_capture_mode(args)):
        return 4
    return 2


def _shadow_capture_mode(args: argparse.Namespace | None) -> str:
    if args is None:
        return ""
    if bool(getattr(args, "personnel_political_wide_shadow_pilot", False)):
        return contracts.PERSONNEL_POLITICAL_WIDE_CAPTURE_MODE
    if bool(getattr(args, "i5b_item_wide_shadow_pilot", False)):
        return "i5b_item_wide_shadow"
    if bool(getattr(args, "i5b_wide_shadow_pilot", False)):
        return "i5b_wide_shadow"
    return ""


def _is_item_wide_shadow_mode(mode: str) -> bool:
    return mode in {"i5b_item_wide_shadow", contracts.PERSONNEL_POLITICAL_WIDE_CAPTURE_MODE}


def _shadow_capture_profile(mode: str) -> str:
    if mode == contracts.PERSONNEL_POLITICAL_WIDE_CAPTURE_MODE:
        return contracts.PERSONNEL_POLITICAL_WIDE_PROFILE
    if mode == "i5b_item_wide_shadow":
        return "i5b_item_wide"
    if mode == "i5b_wide_shadow":
        return "i5b_wide"
    return ""


def _apply_shadow_target_contract(target_payload: dict[str, Any], mode: str) -> None:
    target_payload["capture_mode"] = mode
    target_payload["shadow_pilot"] = True
    target_payload["formal_consumption_source"] = False
    profile = _shadow_capture_profile(mode)
    if profile:
        target_payload["capture_profile"] = profile
    if mode == contracts.PERSONNEL_POLITICAL_WIDE_CAPTURE_MODE:
        target_payload["fact_schema"] = contracts.POLITICAL_ACTION_FACT_SCHEMA
        target_payload["candidate_route_table_version"] = contracts.CANDIDATE_ROUTE_TABLE_VERSION


def _sanitize_item_wide_shadow_contract(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _sanitize_item_wide_shadow_contract(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_item_wide_shadow_contract(item) for item in value]
    if isinstance(value, str):
        mapped = (
            value.replace("I5B.appointment_trust", "I5B.appointment_delegation")
            .replace("I5B.delegation", "I5B.appointment_delegation")
            .replace("appointment_trust_material", "appointment_delegation_material")
        )
        if mapped == "appointment_trust" or mapped == "delegation":
            return "appointment_delegation"
        return mapped
    return value


def _with_shadow_capture_mode(task: Mapping[str, Any], args: argparse.Namespace | None) -> dict[str, Any]:
    result = dict(_sanitize_item_wide_shadow_contract(task))
    mode = _shadow_capture_mode(args)
    if not mode:
        return dict(task)
    result["capture_mode"] = mode
    target_payload = dict(result.get("target_payload") or {})
    _apply_shadow_target_contract(target_payload, mode)
    result["target_payload"] = target_payload
    generation_notes = [str(value) for value in result.get("generation_notes") or [] if str(value).strip()]
    if _is_item_wide_shadow_mode(mode):
        result["rule_code"] = "i5b_item_wide"
        result["job_code"] = str(result.get("job_code") or "").replace("-delegation-", "-i5b_item_wide-")
        rule_payload = dict(result.get("rule") or {})
        rule_payload["rule_code"] = "i5b_item_wide"
        rule_payload["rule_label"] = "I5B item-wide material pool"
        result["rule"] = rule_payload
        result["coverage_matrix"] = contracts.coverage_matrix_template("i5b_item_wide")
        result["secondary_rule_candidates"] = contracts.secondary_rule_hints("i5b_item_wide")
    note = (
        "I5B item-wide shadow pilot: build broad I5B material pool; not a formal consumption source."
        if mode == "i5b_item_wide_shadow"
        else (
            "personnel_political_wide shadow pilot: emit political_action_v1 facts and cross-item future hints; not a formal consumption source."
            if mode == contracts.PERSONNEL_POLITICAL_WIDE_CAPTURE_MODE
            else "I5B-wide shadow pilot: evaluate broad claim capture and secondary candidates; not a formal consumption source."
        )
    )
    if note not in generation_notes:
        generation_notes.append(note)
    result["generation_notes"] = generation_notes
    clean_audit = dict(result.get("clean_audit") or {})
    clean_audit["capture_mode"] = mode
    clean_audit["capture_profile"] = _shadow_capture_profile(mode)
    clean_audit["formal_consumption_source"] = False
    result["clean_audit"] = clean_audit
    return result


def _with_shadow_context(context: Mapping[str, Any], args: argparse.Namespace | None) -> dict[str, Any]:
    result = dict(context)
    mode = _shadow_capture_mode(args)
    if not _is_item_wide_shadow_mode(mode):
        return result
    result["rule_code"] = "i5b_item_wide"
    result["rule_label"] = "I5B item-wide material pool"
    intent_code = str(result.get("intent_code") or "")
    if intent_code:
        result["intent_code"] = intent_code.replace("-delegation", "-i5b_item_wide").replace("-DELEGATION", "-I5B_ITEM_WIDE")
    target_payload = dict(result.get("target_payload") or {})
    _apply_shadow_target_contract(target_payload, mode)
    result["target_payload"] = target_payload
    requirement = dict(result.get("requirement_payload") or {})
    requirement["coverage_matrix"] = contracts.coverage_matrix_template("i5b_item_wide")
    result["requirement_payload"] = requirement
    return result


def _mark_shadow_summary(summary: dict[str, Any], args: argparse.Namespace | None) -> dict[str, Any]:
    mode = _shadow_capture_mode(args)
    if not mode:
        return summary
    summary.setdefault("clean_policy", {})["capture_mode"] = mode
    summary.setdefault("clean_policy", {})["capture_profile"] = _shadow_capture_profile(mode)
    summary.setdefault("clean_policy", {})["shadow_pilot"] = True
    summary.setdefault("clean_policy", {})["formal_consumption_source"] = False
    summary["capture_mode"] = mode
    summary["capture_profile"] = _shadow_capture_profile(mode)
    if mode == contracts.PERSONNEL_POLITICAL_WIDE_CAPTURE_MODE:
        summary.setdefault("clean_policy", {})["fact_schema"] = contracts.POLITICAL_ACTION_FACT_SCHEMA
        summary.setdefault("clean_policy", {})["candidate_route_table_version"] = contracts.CANDIDATE_ROUTE_TABLE_VERSION
        summary["fact_schema"] = contracts.POLITICAL_ACTION_FACT_SCHEMA
        summary["candidate_route_table_version"] = contracts.CANDIDATE_ROUTE_TABLE_VERSION
    summary["formal_consumption_source"] = False
    return summary


def _with_emp_metadata_target_payload(
    task: Mapping[str, Any],
    emp_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    result = dict(task)
    target_payload = dict(result.get("target_payload") or {})
    for key in TARGET_METADATA_KEYS:
        value = emp_metadata.get(key)
        if value not in (None, "", {}, []):
            target_payload.setdefault(key, value)
    if target_payload:
        result["target_payload"] = target_payload
    return result


def _run_staged_emperors(
    *,
    args: argparse.Namespace,
    contexts: Mapping[str, Mapping[str, Any]],
    loaded_profiles: Sequence[Mapping[str, Any]],
    run_root: Path,
    event_logger: RunEventLogger,
    taskgen_preseeds: Mapping[str, Mapping[str, Any]],
    emp_metadata_by_name: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    taskgen_results: list[dict[str, Any]]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(args.max_workers, len(args.emperor)))) as pool:
        taskgen_results = list(
            pool.map(
                lambda name: _run_single_taskgen(
                    name=name,
                    context=contexts[name],
                    loaded_profiles=loaded_profiles,
                    allow_cross_rule_discovery_profile=args.allow_cross_rule_discovery_profile,
                    run_root=run_root,
                    codex_runner=runner.run_codex,
                    codex_bin=args.codex_bin,
                    taskgen_timeout_seconds=args.taskgen_timeout,
                    taskgen_search=_effective_taskgen_search(args),
                    taskgen_preseed_discovery=taskgen_preseeds.get(name),
                    emp_metadata_by_name=emp_metadata_by_name,
                    args=args,
                    event_logger=event_logger,
                )[0],
                args.emperor,
            )
        )
    tasks = [row["task"] for row in taskgen_results]
    tasks = [_with_shadow_capture_mode(task, args) for task in tasks]
    taskgen_by_target_code = {
        str(row["task"].get("target_code") or ""): row["taskgen"] for row in taskgen_results
    }
    for profile_root in args.discovery_profile_root:
        for task in tasks:
            discovery_profiles.write_profile(discovery_profiles.profile_from_task(task), profile_root)
    summary = runner.run_clean_pipeline(
        tasks=tasks,
        run_root=run_root,
        codex_runner=runner.run_codex,
        codex_bin=args.codex_bin,
        skip_judge=args.skip_judge,
        max_alias_refine_rounds=args.max_alias_refine_rounds,
        candidate_source_refine_rounds=_candidate_source_refine_rounds(args),
        candidate_source_refine_max_objects=args.candidate_source_refine_max_objects,
        candidate_source_refine_pages_per_object=args.candidate_source_refine_pages_per_object,
        candidate_source_refine_source_hint_limit=args.candidate_source_refine_source_hint_limit,
        candidate_source_refine_objects=args.candidate_source_refine_object,
        candidate_timeout=args.candidate_timeout,
        context_chars=args.context_chars,
        max_slices_per_object=args.max_slices_per_object,
        skip_fetch_errors=args.skip_fetch_errors,
        source_cache_root=_source_cache_root(args),
        judge_timeout_seconds=args.judge_timeout,
        judge_shard_size=args.judge_shard_size,
        judge_shard_workers=_effective_judge_shard_workers(args),
        taskgen_by_target_code=taskgen_by_target_code,
        max_workers=args.max_workers,
        event_logger=event_logger,
    )
    summary.setdefault("clean_policy", {})["taskgen_presearch"] = bool(args.taskgen_presearch)
    summary.setdefault("clean_policy", {})["taskgen_search_enabled"] = _effective_taskgen_search(args)
    _mark_shadow_summary(summary, args)
    runner.atomic_write_json(run_root / "summary.json", summary)
    return summary


def _run_task_files(args: argparse.Namespace, *, run_root: Path, event_logger: RunEventLogger) -> dict[str, Any]:
    tasks = [_with_shadow_capture_mode(runner.load_json(path), args) for path in args.task]
    summary = runner.run_clean_pipeline(
        tasks=tasks,
        run_root=run_root,
        codex_runner=runner.run_codex,
        codex_bin=args.codex_bin,
        skip_judge=args.skip_judge,
        max_alias_refine_rounds=args.max_alias_refine_rounds,
        candidate_source_refine_rounds=_candidate_source_refine_rounds(args),
        candidate_source_refine_max_objects=args.candidate_source_refine_max_objects,
        candidate_source_refine_pages_per_object=args.candidate_source_refine_pages_per_object,
        candidate_source_refine_source_hint_limit=args.candidate_source_refine_source_hint_limit,
        candidate_source_refine_objects=args.candidate_source_refine_object,
        candidate_timeout=args.candidate_timeout,
        context_chars=args.context_chars,
        max_slices_per_object=args.max_slices_per_object,
        skip_fetch_errors=args.skip_fetch_errors,
        source_cache_root=_source_cache_root(args),
        judge_timeout_seconds=args.judge_timeout,
        judge_shard_size=args.judge_shard_size,
        judge_shard_workers=_effective_judge_shard_workers(args),
        taskgen_by_target_code={},
        max_workers=args.max_workers,
        event_logger=event_logger,
    )
    return _mark_shadow_summary(summary, args)


def _chunks(values: Sequence[str], size: int) -> list[list[str]]:
    chunk_size = max(1, size)
    return [list(values[index : index + chunk_size]) for index in range(0, len(values), chunk_size)]


def _fetch_public_emp_metadata(dsn: str, names: Sequence[str]) -> dict[str, dict[str, Any]]:
    psycopg, dict_row = runner.import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("select to_regclass('public.emps') is not null as exists")
            if not bool(cur.fetchone()["exists"]):
                return {}
            cur.execute(
                """
                select to_jsonb(e) as row
                  from public.emps e
                 where e.name = any(%s)
                 order by e.sort_no nulls last, e.id
                """,
                (list(names),),
            )
            rows = cur.fetchall()
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        payload = row["row"]
        if isinstance(payload, dict) and payload.get("name"):
            result[str(payload["name"])] = payload
    return result


def _load_query_profile_metadata(names: Sequence[str]) -> dict[str, dict[str, Any]]:
    wanted = set(names)
    if not wanted:
        return {}
    path = Path("data/query_profile_batches/i5b_layered_retrieval_profiles_20260630.jsonl")
    if not path.exists():
        return {}
    result: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            person = str(payload.get("person") or "").strip()
            if person not in wanted:
                continue
            metadata = {
                "source_targets": payload.get("source_targets") or [],
                "query_bundles": payload.get("query_bundles") or [],
                "object_search_aliases": payload.get("object_search_aliases") or {},
                "expected_lane_outcomes": payload.get("expected_lane_outcomes") or [],
                "retrieval_profile_id": payload.get("query_profile_id") or "",
                "retrieval_profile_source_group": payload.get("source_group") or "",
            }
            result.setdefault(person, {key: value for key, value in metadata.items() if value not in ("", [], {})})
    return result


def _load_emp_metadata(args: argparse.Namespace, names: Sequence[str]) -> dict[str, dict[str, Any]]:
    if not args.taskgen_presearch:
        return {}
    profile_metadata = _load_query_profile_metadata(names)
    dsn = os.environ.get(args.emp_metadata_dsn_env or "")
    if not dsn:
        return profile_metadata
    public_metadata = _fetch_public_emp_metadata(dsn, names)
    result: dict[str, dict[str, Any]] = {}
    for name in names:
        merged = dict(profile_metadata.get(name) or {})
        merged.update(public_metadata.get(name) or {})
        if merged:
            result[name] = merged
    return result


def _build_taskgen_preseed(
    args: argparse.Namespace,
    context: Mapping[str, Any],
    emp_metadata_by_name: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any] | None:
    if not args.taskgen_presearch:
        return None
    emperor_name = str(context.get("emperor_name") or "")
    return taskgen_preseed.build_taskgen_preseed(
        context,
        emp_metadata=emp_metadata_by_name.get(emperor_name) or {},
        max_queries=args.taskgen_presearch_queries,
        pages_per_query=args.taskgen_presearch_pages_per_query,
        timeout=args.taskgen_presearch_timeout,
    )


def _build_taskgen_preseeds(
    args: argparse.Namespace,
    contexts: Mapping[str, Mapping[str, Any]],
    names: Sequence[str],
    emp_metadata_by_name: Mapping[str, Mapping[str, Any]],
    loaded_profiles: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    if not args.taskgen_presearch:
        return {}

    def build_one(name: str) -> tuple[str, dict[str, Any] | None]:
        profile = discovery_profiles.select_profile(
            loaded_profiles,
            contexts[name],
            allow_cross_rule=args.allow_cross_rule_discovery_profile,
        )
        if profile is not None:
            return name, None
        return name, _build_taskgen_preseed(args, contexts[name], emp_metadata_by_name)

    workers = max(1, min(args.max_workers, len(names) or 1))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(build_one, names))
    return {name: preseed for name, preseed in rows if preseed is not None}


def _effective_taskgen_search(args: argparse.Namespace) -> bool:
    if args.no_taskgen_search:
        return False
    if args.taskgen_presearch and not args.taskgen_presearch_with_codex_search:
        return False
    return True


def _expand_object_sources_after_taskgen(
    *,
    args: argparse.Namespace,
    row: Mapping[str, Any],
    context: Mapping[str, Any],
    emp_metadata_by_name: Mapping[str, Mapping[str, Any]],
    run_root: Path,
    taskgen_search: bool,
    event_logger: RunEventLogger | None = None,
) -> dict[str, Any]:
    emperor_name = str(context.get("emperor_name") or "")
    task = _with_emp_metadata_target_payload(
        row["task"],
        emp_metadata_by_name.get(emperor_name) or {},
    )
    row = {**dict(row), "task": task}
    if not args.taskgen_presearch or args.no_taskgen_object_source_presearch or taskgen_search:
        return row
    started = time.perf_counter()
    if event_logger is not None:
        event_logger.emit(
            "taskgen_object_source_presearch_start",
            emperor_name=emperor_name,
            target_code=str(context.get("target_code") or ""),
            rule_code=str(context.get("rule_code") or ""),
            max_objects=args.taskgen_object_source_max_objects,
            pages_per_object=args.taskgen_object_source_pages_per_object,
        )
    expanded_task = taskgen_preseed.expand_task_sources_for_objects(
        task,
        context,
        emp_metadata=emp_metadata_by_name.get(emperor_name) or {},
        max_objects=args.taskgen_object_source_max_objects,
        pages_per_object=args.taskgen_object_source_pages_per_object,
        timeout=args.taskgen_presearch_timeout,
        source_hint_limit=getattr(args, "taskgen_object_source_hint_limit", 2),
    )
    expanded_task = runner.normalize_task_from_context(expanded_task, context)
    expanded_task = _with_emp_metadata_target_payload(
        expanded_task,
        emp_metadata_by_name.get(emperor_name) or {},
    )
    issues = task_skeleton.validate_task_for_candidates(expanded_task)
    if issues:
        raise runner.RetrievalV2CleanRunnerError(f"object source presearch produced invalid task: {issues}")
    person_dir = run_root / runner.target_dir_name(expanded_task)
    runner.atomic_write_json(person_dir / "task.object_source_preseed.json", expanded_task)
    runner.atomic_write_json(person_dir / "task.generated.json", expanded_task)
    runner.atomic_write_json(
        person_dir / "discovery_profile.generated.json",
        task_skeleton.discovery_profile_from_task(expanded_task),
    )
    result = dict(row)
    result["task"] = expanded_task
    taskgen = dict(result.get("taskgen") or {})
    files = dict(taskgen.get("files") or {})
    files["object_source_preseed"] = str(person_dir / "task.object_source_preseed.json")
    taskgen["files"] = files
    taskgen["object_source_presearch"] = True
    result["taskgen"] = taskgen
    if event_logger is not None:
        clean_audit = expanded_task.get("clean_audit") or {}
        event_logger.emit(
            "taskgen_object_source_presearch_done",
            emperor_name=emperor_name,
            target_code=str(context.get("target_code") or ""),
            rule_code=str(context.get("rule_code") or ""),
            elapsed_seconds_stage=round(time.perf_counter() - started, 3),
            source_document_count=len(expanded_task.get("source_documents") or []),
            hit_count=clean_audit.get("object_source_presearch_hit_count"),
        )
    return result


def _run_single_taskgen(
    *,
    name: str,
    context: Mapping[str, Any],
    loaded_profiles: Sequence[Mapping[str, Any]],
    allow_cross_rule_discovery_profile: bool,
    run_root: Path,
    codex_runner: runner.CodexRunner,
    codex_bin: str,
    taskgen_timeout_seconds: int,
    taskgen_search: bool,
    taskgen_preseed_discovery: Mapping[str, Any] | None,
    emp_metadata_by_name: Mapping[str, Mapping[str, Any]],
    args: argparse.Namespace | None,
    event_logger: RunEventLogger | None,
) -> list[dict[str, Any]]:
    effective_context = _with_emp_metadata_target_payload(
        context,
        emp_metadata_by_name.get(name) or {},
    )
    row = runner.run_taskgen(
        context=effective_context,
        run_root=run_root,
        codex_runner=codex_runner,
        codex_bin=codex_bin,
        timeout_seconds=taskgen_timeout_seconds,
        search=taskgen_search,
        discovery_profile=discovery_profiles.select_profile(
            loaded_profiles,
            effective_context,
            allow_cross_rule=allow_cross_rule_discovery_profile,
        ),
        preseed_discovery=taskgen_preseed_discovery,
        event_logger=event_logger,
    )
    if args is not None:
        row = _expand_object_sources_after_taskgen(
            args=args,
            row=row,
            context=effective_context,
            emp_metadata_by_name=emp_metadata_by_name,
            run_root=run_root,
            taskgen_search=taskgen_search,
            event_logger=event_logger,
        )
    return [row]


def _run_batch_taskgen(
    *,
    names: Sequence[str],
    contexts: Mapping[str, Mapping[str, Any]],
    run_root: Path,
    codex_runner: runner.CodexRunner,
    codex_bin: str,
    taskgen_timeout_seconds: int,
    taskgen_search: bool,
    event_logger: RunEventLogger | None,
) -> list[dict[str, Any]]:
    batch_contexts = [contexts[name] for name in names]
    skeletons = {name: task_skeleton.build_task_skeleton(contexts[name]) for name in names}
    batch_code = "BTG-" + runner.stable_fingerprint(
        [context.get("target_code") for context in batch_contexts]
    )[:12].upper()
    batch_dir = run_root / "taskgen_batches" / batch_code
    batch_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        person_dir = run_root / runner.target_dir_name(
            {
                "target_code": contexts[name]["target_code"],
                "rule_code": contexts[name]["rule_code"],
                "emperor_name": contexts[name]["emperor_name"],
            }
        )
        runner.atomic_write_json(person_dir / "task.skeleton.json", skeletons[name])
    prompt = batch_taskgen.build_batch_discovery_prompt(
        [(contexts[name], skeletons[name]) for name in names],
        allow_search=taskgen_search,
    )
    runner.atomic_write_text(batch_dir / "taskgen_batch_prompt.md", prompt)
    if event_logger is not None:
        event_logger.emit(
            "taskgen_batch_start",
            batch_code=batch_code,
            target_count=len(names),
            targets=list(names),
            mode="batch_skeleton_discovery",
            prompt_chars=len(prompt),
            search=taskgen_search,
        )
    result = codex_runner(
        runner.CodexInvocation(
            phase="taskgen_batch",
            prompt=prompt,
            cwd=batch_dir.resolve(),
            last_message=(batch_dir / "taskgen_batch_last_message.json").resolve(),
            event_log=(batch_dir / "taskgen_batch_events.jsonl").resolve(),
            search=taskgen_search,
            timeout_seconds=taskgen_timeout_seconds,
            codex_bin=codex_bin,
        )
    )
    discoveries = batch_taskgen.target_discoveries_from_payload(result.payload, expected_targets=batch_contexts)
    rows: list[dict[str, Any]] = []
    for index, name in enumerate(names):
        context = contexts[name]
        skeleton = skeletons[name]
        target_code = str(context["target_code"])
        person_dir = run_root / runner.target_dir_name(skeleton)
        task = task_skeleton.merge_taskgen_discovery(skeleton, discoveries[target_code])
        task = runner.normalize_task_from_context(task, context)
        issues = task_skeleton.validate_task_for_candidates(task)
        if issues:
            raise runner.RetrievalV2CleanRunnerError(f"batch taskgen discovery produced invalid task: {issues}")
        runner.atomic_write_json(person_dir / "task.generated.json", task)
        runner.atomic_write_json(person_dir / "discovery_profile.generated.json", task_skeleton.discovery_profile_from_task(task))
        rows.append(
            {
                "task": task,
                "taskgen": {
                    "elapsed_seconds": round(result.elapsed_seconds / max(1, len(names)), 3),
                    "usage": batch_taskgen.split_usage(result.usage, count=len(names), index=index),
                    "mode": "batch_skeleton_discovery",
                    "batch_code": batch_code,
                    "batch_size": len(names),
                    "batch_elapsed_seconds": result.elapsed_seconds,
                    "files": {
                        "skeleton": str(person_dir / "task.skeleton.json"),
                        "prompt": str(batch_dir / "taskgen_batch_prompt.md"),
                        "events": str(batch_dir / "taskgen_batch_events.jsonl"),
                        "last_message": str(batch_dir / "taskgen_batch_last_message.json"),
                        "generated_profile": str(person_dir / "discovery_profile.generated.json"),
                    },
                },
            }
        )
    if event_logger is not None:
        event_logger.emit(
            "taskgen_batch_done",
            batch_code=batch_code,
            target_count=len(names),
            targets=list(names),
            elapsed_seconds_stage=result.elapsed_seconds,
            input_tokens=result.usage.get("input_tokens"),
            output_tokens=result.usage.get("output_tokens"),
            reasoning_output_tokens=result.usage.get("reasoning_output_tokens"),
        )
    return rows


def _failed_person(
    *,
    context: Mapping[str, Any],
    run_root: Path,
    stage: str,
    exc: BaseException,
) -> dict[str, Any]:
    task = {
        "target_code": context.get("target_code") or "",
        "emperor_name": context.get("emperor_name") or "",
        "rule_code": context.get("rule_code") or "",
    }
    person_dir = run_root / runner.target_dir_name(task)
    person_dir.mkdir(parents=True, exist_ok=True)
    error_payload = {
        "name": task["emperor_name"],
        "target_code": task["target_code"],
        "rule_code": task["rule_code"],
        "failed_stage": stage,
        "error": repr(exc),
    }
    runner.atomic_write_json(person_dir / f"{stage}.error.json", error_payload)
    return {
        **error_payload,
        "status": "failed",
        "run_dir": str(person_dir),
        "taskgen_elapsed_seconds": None,
        "taskgen_usage": {},
        "taskgen_mode": None,
        "taskgen_object_source_presearch": False,
        "round_count": 0,
        "alias_round_limit_reached": False,
        "object_seed_count": 0,
        "source_document_count": 0,
        "candidate_slices": 0,
        "fetch_error_count": 0,
        "fetch_errors": [],
        "candidate_coverage_gap_count": 0,
        "objects_without_slices": [],
        "judge_status": None,
        "judge_elapsed_seconds": None,
        "judge_usage": {},
        "judge_sharded": False,
        "judge_shard_count": 0,
        "claim_count": 0,
        "primary_binding_count": 0,
        "secondary_binding_count": 0,
        "judge_coverage_gap_count": 0,
        "rounds": [],
        "files": {"error": str(person_dir / f"{stage}.error.json")},
    }


def run_streaming_taskgen_pipeline(
    *,
    contexts: Mapping[str, Mapping[str, Any]],
    emperor_names: Sequence[str],
    loaded_profiles: Sequence[Mapping[str, Any]],
    allow_cross_rule_discovery_profile: bool,
    profile_roots: Sequence[Path],
    run_root: Path,
    codex_runner: runner.CodexRunner = runner.run_codex,
    codex_bin: str = "codex",
    taskgen_timeout_seconds: int = 1800,
    taskgen_search: bool = True,
    skip_judge: bool = False,
    max_alias_refine_rounds: int = 2,
    candidate_source_refine_rounds: int = 0,
    candidate_source_refine_max_objects: int = 8,
    candidate_source_refine_pages_per_object: int = 2,
    candidate_source_refine_source_hint_limit: int = 2,
    candidate_source_refine_objects: Sequence[str] = (),
    candidate_timeout: int = 15,
    context_chars: int = 260,
    max_slices_per_object: int = 8,
    skip_fetch_errors: bool = False,
    source_cache_root: Path | None = source_candidates.DEFAULT_CACHE_DIR,
    judge_timeout_seconds: int = 1800,
    judge_shard_size: int = 8,
    judge_shard_workers: int = 2,
    max_workers: int = 4,
    taskgen_batch_size: int = 1,
    taskgen_preseeds: Mapping[str, Mapping[str, Any]] | None = None,
    emp_metadata_by_name: Mapping[str, Mapping[str, Any]] | None = None,
    args: argparse.Namespace | None = None,
    event_logger: RunEventLogger | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    taskgen_preseeds = taskgen_preseeds or {}
    emp_metadata_by_name = emp_metadata_by_name or {}
    run_root.mkdir(parents=True, exist_ok=True)
    if event_logger is not None:
        event_logger.emit(
            "pipeline_start",
            target_count=len(emperor_names),
            max_workers=max_workers,
            mode="streaming_taskgen",
            capture_mode=_shadow_capture_mode(args) or None,
            taskgen_batch_size=taskgen_batch_size,
            taskgen_presearch=bool(taskgen_preseeds),
        )

    def process_taskgen_result(taskgen_result: Mapping[str, Any]) -> dict[str, Any]:
        task = _with_shadow_capture_mode(taskgen_result["task"], args)
        taskgen_result = {**dict(taskgen_result), "task": task}
        for profile_root in profile_roots:
            discovery_profiles.write_profile(discovery_profiles.profile_from_task(task), profile_root)
        return runner.process_task(
            task=task,
            run_root=run_root,
            codex_runner=codex_runner,
            codex_bin=codex_bin,
            skip_judge=skip_judge,
            max_alias_refine_rounds=max_alias_refine_rounds,
            candidate_source_refine_rounds=candidate_source_refine_rounds,
            candidate_source_refine_max_objects=candidate_source_refine_max_objects,
            candidate_source_refine_pages_per_object=candidate_source_refine_pages_per_object,
            candidate_source_refine_source_hint_limit=candidate_source_refine_source_hint_limit,
            candidate_source_refine_objects=candidate_source_refine_objects,
            candidate_timeout=candidate_timeout,
            context_chars=context_chars,
            max_slices_per_object=max_slices_per_object,
            skip_fetch_errors=skip_fetch_errors,
            source_cache_root=source_cache_root,
            judge_timeout_seconds=judge_timeout_seconds,
            judge_shard_size=judge_shard_size,
            judge_shard_workers=judge_shard_workers,
            taskgen=taskgen_result["taskgen"],
            event_logger=event_logger,
        )

    profile_names: list[str] = []
    batch_names: list[str] = []
    for name in emperor_names:
        profile = discovery_profiles.select_profile(
            loaded_profiles,
            contexts[name],
            allow_cross_rule=allow_cross_rule_discovery_profile,
        )
        if profile is not None or taskgen_preseeds.get(name) is not None or taskgen_batch_size <= 1:
            profile_names.append(name)
        else:
            batch_names.append(name)

    taskgen_jobs: list[tuple[str, list[str]]] = [("single", [name]) for name in profile_names]
    taskgen_jobs.extend(("batch", chunk) for chunk in _chunks(batch_names, taskgen_batch_size))
    workers = max(1, min(max_workers, len(taskgen_jobs) or 1))
    people_by_index: dict[int, dict[str, Any]] = {}
    name_to_index = {name: index for index, name in enumerate(emperor_names)}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as taskgen_pool:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(emperor_names) or 1))) as process_pool:
            taskgen_futures = {}
            for kind, names in taskgen_jobs:
                if kind == "single":
                    name = names[0]
                    taskgen_futures[
                        taskgen_pool.submit(
                            _run_single_taskgen,
                            name=name,
                            context=contexts[name],
                            loaded_profiles=loaded_profiles,
                            allow_cross_rule_discovery_profile=allow_cross_rule_discovery_profile,
                            run_root=run_root,
                            codex_runner=codex_runner,
                            codex_bin=codex_bin,
                            taskgen_timeout_seconds=taskgen_timeout_seconds,
                            taskgen_search=taskgen_search,
                            taskgen_preseed_discovery=taskgen_preseeds.get(name),
                            emp_metadata_by_name=emp_metadata_by_name,
                            args=args,
                            event_logger=event_logger,
                        )
                    ] = names
                else:
                    taskgen_futures[
                        taskgen_pool.submit(
                            _run_batch_taskgen,
                            names=names,
                            contexts=contexts,
                            run_root=run_root,
                            codex_runner=codex_runner,
                            codex_bin=codex_bin,
                            taskgen_timeout_seconds=taskgen_timeout_seconds,
                            taskgen_search=taskgen_search,
                            event_logger=event_logger,
                        )
                    ] = names
            process_futures = {}
            for future in concurrent.futures.as_completed(taskgen_futures):
                try:
                    taskgen_results = future.result()
                except Exception as exc:
                    for name in taskgen_futures[future]:
                        index = name_to_index[name]
                        people_by_index[index] = _failed_person(
                            context=contexts[name],
                            run_root=run_root,
                            stage="taskgen",
                            exc=exc,
                        )
                        if event_logger is not None:
                            event_logger.emit(
                                "target_failed",
                                emperor_name=name,
                                target_code=str(contexts[name].get("target_code") or ""),
                                rule_code=str(contexts[name].get("rule_code") or ""),
                                failed_stage="taskgen",
                                error=repr(exc),
                            )
                    continue
                for taskgen_result in taskgen_results:
                    task = taskgen_result["task"]
                    index = name_to_index[str(task.get("emperor_name") or "")]
                    process_futures[process_pool.submit(process_taskgen_result, taskgen_result)] = index
            for future in concurrent.futures.as_completed(process_futures):
                index = process_futures[future]
                try:
                    people_by_index[index] = future.result()
                except Exception as exc:
                    name = emperor_names[index]
                    people_by_index[index] = _failed_person(
                        context=contexts[name],
                        run_root=run_root,
                        stage="target_process",
                        exc=exc,
                    )
                    if event_logger is not None:
                        event_logger.emit(
                            "target_failed",
                            emperor_name=name,
                            target_code=str(contexts[name].get("target_code") or ""),
                            rule_code=str(contexts[name].get("rule_code") or ""),
                            failed_stage="target_process",
                            error=repr(exc),
                        )

    people = [people_by_index[index] for index in range(len(emperor_names))]
    elapsed = round(time.perf_counter() - started, 3)
    summary = runner.build_batch_summary(
        people=people,
        run_root=run_root,
        elapsed_seconds=elapsed,
        max_alias_refine_rounds=max_alias_refine_rounds,
        candidate_source_refine_rounds=candidate_source_refine_rounds,
        candidate_source_refine_max_objects=candidate_source_refine_max_objects,
        candidate_source_refine_pages_per_object=candidate_source_refine_pages_per_object,
        judge_shard_size=judge_shard_size,
        judge_shard_workers=judge_shard_workers,
        source_cache_root=source_cache_root,
        taskgen_streaming=True,
        taskgen_batch_size=max(1, taskgen_batch_size),
        taskgen_presearch=bool(taskgen_preseeds),
        taskgen_search_enabled=taskgen_search,
    )
    _mark_shadow_summary(summary, args)
    runner.atomic_write_json(run_root / "summary.json", summary)
    if event_logger is not None:
        event_logger.emit(
            "pipeline_done",
            target_count=len(people),
            elapsed_seconds_stage=elapsed,
            candidate_slices=summary["totals"]["candidate_slices"],
            claim_count=summary["totals"]["claim_count"],
            judge_coverage_gap_count=summary["totals"]["judge_coverage_gap_count"],
        )
    return summary


def _run_emperors(
    args: argparse.Namespace,
    *,
    loaded_profiles: Sequence[Mapping[str, Any]],
    run_root: Path,
    event_logger: RunEventLogger,
) -> dict[str, Any]:
    contexts = runner.fetch_retrieval_contexts(
        target_dsn=runner.resolve_dsn(args.target_dsn_env),
        emperor_names=args.emperor,
        item_code=args.item_code,
        rule_code=args.rule_code,
        contract_code=args.contract_code,
    )
    contexts = {name: _with_shadow_context(context, args) for name, context in contexts.items()}
    emp_metadata_by_name = _load_emp_metadata(args, args.emperor)
    taskgen_preseeds = _build_taskgen_preseeds(
        args,
        contexts,
        args.emperor,
        emp_metadata_by_name,
        loaded_profiles,
    )
    if args.no_stream_taskgen:
        return _run_staged_emperors(
            args=args,
            contexts=contexts,
            loaded_profiles=loaded_profiles,
            run_root=run_root,
            event_logger=event_logger,
            taskgen_preseeds=taskgen_preseeds,
            emp_metadata_by_name=emp_metadata_by_name,
        )
    return run_streaming_taskgen_pipeline(
        contexts=contexts,
        emperor_names=args.emperor,
        loaded_profiles=loaded_profiles,
        allow_cross_rule_discovery_profile=args.allow_cross_rule_discovery_profile,
        profile_roots=args.discovery_profile_root,
        run_root=run_root,
        codex_runner=runner.run_codex,
        codex_bin=args.codex_bin,
        taskgen_timeout_seconds=args.taskgen_timeout,
        taskgen_search=_effective_taskgen_search(args),
        skip_judge=args.skip_judge,
        max_alias_refine_rounds=args.max_alias_refine_rounds,
        candidate_source_refine_rounds=_candidate_source_refine_rounds(args),
        candidate_source_refine_max_objects=args.candidate_source_refine_max_objects,
        candidate_source_refine_pages_per_object=args.candidate_source_refine_pages_per_object,
        candidate_source_refine_source_hint_limit=args.candidate_source_refine_source_hint_limit,
        candidate_source_refine_objects=args.candidate_source_refine_object,
        candidate_timeout=args.candidate_timeout,
        context_chars=args.context_chars,
        max_slices_per_object=args.max_slices_per_object,
        skip_fetch_errors=args.skip_fetch_errors,
        source_cache_root=_source_cache_root(args),
        judge_timeout_seconds=args.judge_timeout,
        judge_shard_size=args.judge_shard_size,
        judge_shard_workers=_effective_judge_shard_workers(args),
        max_workers=args.max_workers,
        taskgen_batch_size=args.taskgen_batch_size,
        taskgen_preseeds=taskgen_preseeds,
        emp_metadata_by_name=emp_metadata_by_name,
        args=args,
        event_logger=event_logger,
    )


def main(argv: Sequence[str] | None = None) -> int:
    cli_started = time.perf_counter()
    args = build_parser().parse_args(argv)
    loaded_env_keys: list[str] = []
    if args.env_file is not None:
        loaded_env_keys = runner.load_env_file(args.env_file)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.personnel_political_wide_shadow_pilot:
        default_run_name = f"personnel_political_wide_shadow_{timestamp}"
    elif args.i5b_item_wide_shadow_pilot:
        default_run_name = f"i5b_item_wide_shadow_{timestamp}"
    elif args.i5b_wide_shadow_pilot:
        default_run_name = f"i5b_wide_shadow_{timestamp}"
    else:
        default_run_name = f"clean_pipeline_{timestamp}"
    runtime = runtime_paths.load_runtime_paths(
        config_path=args.runtime_paths_config,
        use_local=args.use_local_runtime,
    )
    if args.source_cache_root is None:
        args.source_cache_root = runtime_paths.default_source_cache_root(runtime)
    run_root = args.run_root or runtime_paths.default_run_root(default_run_name, runtime)
    event_logger = RunEventLogger(run_root / "run_events.jsonl", echo=args.progress)

    loaded_profiles = discovery_profiles.load_profiles(
        paths=args.discovery_profile,
        roots=args.discovery_profile_root,
    )
    if args.task:
        summary = _run_task_files(args, run_root=run_root, event_logger=event_logger)
    elif args.emperor:
        summary = _run_emperors(args, loaded_profiles=loaded_profiles, run_root=run_root, event_logger=event_logger)
    else:
        raise runner.RetrievalV2CleanRunnerError("provide --task or at least one --emperor")

    summary["cli_elapsed_seconds"] = round(time.perf_counter() - cli_started, 3)
    summary["total_elapsed_seconds"] = summary["cli_elapsed_seconds"]
    summary["event_log"] = str(run_root / "run_events.jsonl")
    summary["loaded_env_keys"] = loaded_env_keys
    summary["runtime_paths"] = {
        "uses_runtime_config": bool(runtime["uses_runtime_config"]),
        "config_source": str(runtime["config_source"]),
        "active_root": str(runtime["active_root"]),
        "run_root": str(run_root),
        "source_cache_root": str(args.source_cache_root),
    }
    _mark_shadow_summary(summary, args)
    runner.atomic_write_json(run_root / "summary.json", summary)
    sys.stdout.write(runner.pretty_json(summary))
    return 0
