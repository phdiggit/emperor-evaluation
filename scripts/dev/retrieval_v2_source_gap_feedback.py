from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev import retrieval_v2_candidate_prompt as candidate_prompt
from scripts.dev import retrieval_v2_candidate_source_refiner as source_refiner
from scripts.dev import retrieval_v2_source_candidates as source_candidates
from scripts.dev.retrieval_v2_recall_feedback import (
    load_jsonl,
    source_gap_feedback_rows,
)


REPORT_VERSION = "source_gap_feedback_bridge_v0_2"
SOURCE_REFINER_ACTION = "run_object_source_refiner"
OBJECT_BIOGRAPHY_QUERY_SUFFIXES = ("奸臣", "列传", "列傳")
CHRONICLE_QUERY_SUFFIXES = ("纪事本末", "紀事本末")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return dict(payload)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def stable_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def load_source_gap_rows(paths: Sequence[Path]) -> list[dict[str, Any]]:
    rows = [row for path in paths for row in load_jsonl(path)]
    return source_gap_feedback_rows(rows)


def object_names_for_refiner(gap_rows: Sequence[Mapping[str, Any]]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for row in gap_rows:
        if str(row.get("recommended_action") or "") != SOURCE_REFINER_ACTION:
            continue
        name = str(row.get("object_name") or "").strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def source_gap_query_suffixes(row: Mapping[str, Any]) -> list[str]:
    source_types = {str(value or "").strip() for value in row.get("required_source_type") or []}
    suffixes: list[str] = []
    if "object_biography" in source_types:
        suffixes.extend(OBJECT_BIOGRAPHY_QUERY_SUFFIXES)
    if "chronicle_cross_check" in source_types:
        suffixes.extend(CHRONICLE_QUERY_SUFFIXES)
    return list(dict.fromkeys(suffix for suffix in suffixes if suffix))


def source_gap_search_fn(
    gap_rows: Sequence[Mapping[str, Any]],
    *,
    base_search: source_refiner.SearchFn | None = None,
) -> source_refiner.SearchFn | None:
    suffixes_by_object = {
        str(row.get("object_name") or "").strip(): source_gap_query_suffixes(row)
        for row in gap_rows
        if str(row.get("recommended_action") or "") == SOURCE_REFINER_ACTION
    }
    suffixes_by_object = {name: suffixes for name, suffixes in suffixes_by_object.items() if name and suffixes}
    if not suffixes_by_object and base_search is None:
        return None
    search = base_search or source_refiner.search_wikisource

    def wrapped_search(query: str, *, limit: int, timeout: int) -> list[dict[str, Any]]:
        suffixes: list[str] = []
        for object_name, object_suffixes in suffixes_by_object.items():
            if object_name and object_name in query:
                suffixes.extend(object_suffixes)
        queries = [f"{query} {suffix}".strip() for suffix in dict.fromkeys(suffixes)]
        queries.append(query)
        pages: list[dict[str, Any]] = []
        seen_titles: set[str] = set()
        for expanded_query in queries:
            for page in search(expanded_query, limit=limit, timeout=timeout):
                title = str(page.get("title") or "")
                key = title or json.dumps(page, ensure_ascii=False, sort_keys=True, default=str)
                if key in seen_titles:
                    continue
                seen_titles.add(key)
                row = dict(page)
                if expanded_query != query:
                    row["source_gap_expanded_query"] = expanded_query
                pages.append(row)
                if len(pages) >= limit:
                    return pages
        return pages

    return wrapped_search


def refine_task_from_source_gap_feedback(
    task: Mapping[str, Any],
    gap_rows: Sequence[Mapping[str, Any]],
    *,
    stage: str = "judge",
    max_objects: int = 8,
    pages_per_object: int = 4,
    timeout: int = 20,
    source_hint_limit: int = 2,
    search_fn: source_refiner.SearchFn | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    object_names = object_names_for_refiner(gap_rows)
    if not object_names:
        result = json.loads(json.dumps(dict(task), ensure_ascii=False, default=str))
        stats = {
            "stage": "judge" if stage == "judge" else "candidate",
            "gap_object_names": [],
            "searched_object_names": [],
            "source_hints": [],
            "hit_count": 0,
            "error_count": 0,
            "added_source_document_count": 0,
            "source_document_count": len(result.get("source_documents") or result.get("documents") or []),
        }
        return result, stats
    effective_search_fn = source_gap_search_fn(gap_rows, base_search=search_fn)
    return source_refiner.refine_task_sources_for_candidate_gaps(
        task,
        {"coverage": {"objects_without_slices": []}, "coverage_gaps": []},
        object_names=object_names,
        stage=stage,
        max_objects=max_objects,
        pages_per_object=pages_per_object,
        timeout=timeout,
        source_hint_limit=source_hint_limit,
        search_fn=effective_search_fn,
    )


def build_bridge_report(
    *,
    feedback_paths: Sequence[Path],
    task_path: Path,
    output_task: Path,
    gap_rows: Sequence[Mapping[str, Any]],
    refiner_stats: Mapping[str, Any],
    candidates_path: Path | None = None,
    focused_candidates_path: Path | None = None,
) -> dict[str, Any]:
    return {
        "generated_by": "scripts/dev/retrieval_v2_source_gap_feedback.py",
        "version": REPORT_VERSION,
        "report_type": "source_gap_feedback_bridge_report",
        "inputs": {
            "feedback_paths": [str(path) for path in feedback_paths],
            "task_path": str(task_path),
            "source_gap_row_count": len(gap_rows),
            "source_refinement_row_count": len(gap_rows),
            "object_names": object_names_for_refiner(gap_rows),
        },
        "refiner_stats": dict(refiner_stats),
        "outputs": {
            "refined_task": str(output_task),
            "candidates": str(candidates_path) if candidates_path is not None else "",
            "focused_candidates": str(focused_candidates_path) if focused_candidates_path is not None else "",
        },
        "source_gap_feedback": {
            "rows": list(gap_rows),
            "excluded_from_recall_overlay": True,
        },
        "safety": {
            "writes_task": False,
            "writes_profile": False,
            "writes_prompt": False,
            "writes_db": False,
            "requires_shadow_review_before_profile_update": True,
        },
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    inputs = report.get("inputs") if isinstance(report.get("inputs"), Mapping) else {}
    stats = report.get("refiner_stats") if isinstance(report.get("refiner_stats"), Mapping) else {}
    outputs = report.get("outputs") if isinstance(report.get("outputs"), Mapping) else {}
    lines = [
        "# retrieval_v2 source gap feedback bridge report",
        "",
        f"- version: `{report.get('version')}`",
        f"- source_gap_row_count: `{inputs.get('source_gap_row_count')}`",
        f"- source_refinement_row_count: `{inputs.get('source_refinement_row_count')}`",
        f"- object_names: `{json.dumps(inputs.get('object_names') or [], ensure_ascii=False)}`",
        f"- added_source_document_count: `{stats.get('added_source_document_count')}`",
        f"- hit_count: `{stats.get('hit_count')}`",
        f"- error_count: `{stats.get('error_count')}`",
        f"- refined_task: `{outputs.get('refined_task')}`",
        f"- candidates: `{outputs.get('candidates')}`",
        f"- focused_candidates: `{outputs.get('focused_candidates')}`",
        "",
        "## source_gap_feedback",
        "",
        "| emperor | object | lane | gap_type | reason | missing_material | action |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    source_gap = report.get("source_gap_feedback") if isinstance(report.get("source_gap_feedback"), Mapping) else {}
    for row in source_gap.get("rows") or []:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            "| {emperor} | {object} | {lane} | {gap_type} | {reason} | {missing} | {action} |".format(
                emperor=row.get("emperor_name"),
                object=row.get("object_name"),
                lane=row.get("candidate_lane"),
                gap_type=row.get("gap_type"),
                reason=row.get("gap_reason"),
                missing=json.dumps(row.get("missing_material") or [], ensure_ascii=False).replace("|", "｜"),
                action=row.get("recommended_action"),
            )
        )
    lines.append("")
    return "\n".join(lines)


def focused_candidates(
    candidates: Mapping[str, Any],
    *,
    object_names: Sequence[str],
) -> dict[str, Any]:
    wanted = {str(name or "").strip() for name in object_names if str(name or "").strip()}
    rows = [
        dict(row)
        for row in candidates.get("candidate_slices") or []
        if isinstance(row, Mapping) and str(row.get("object_name") or "").strip() in wanted
    ]
    document_codes = {str(row.get("document_code") or "") for row in rows if row.get("document_code")}
    result = json.loads(json.dumps(dict(candidates), ensure_ascii=False, default=str))
    result["candidate_slices"] = rows
    result["source_documents"] = [
        dict(row)
        for row in candidates.get("source_documents") or []
        if isinstance(row, Mapping) and str(row.get("document_code") or "") in document_codes
    ]
    result["object_seeds"] = [
        dict(row)
        for row in candidates.get("object_seeds") or []
        if isinstance(row, Mapping) and str(row.get("name") or "").strip() in wanted
    ]
    result["coverage"] = {
        "object_slice_counts": {name: len([row for row in rows if row.get("object_name") == name]) for name in sorted(wanted)},
        "objects_without_slices": sorted(name for name in wanted if not any(row.get("object_name") == name for row in rows)),
        "ready_for_judgement": bool(rows) and all(any(row.get("object_name") == name for row in rows) for name in wanted),
        "focused_from": "source_gap_feedback_bridge",
    }
    result["coverage_gaps"] = []
    stats = dict(result.get("stats") or {})
    stats["focused_candidate_slices"] = len(rows)
    result["stats"] = stats
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bridge consumer source/refinement feedback into retrieval_v2 source refiner shadow tasks.")
    parser.add_argument("--task", type=Path, required=True, help="Base retrieval_v2 task JSON.")
    parser.add_argument("--feedback-jsonl", type=Path, action="append", required=True, help="Consumer source gap feedback JSONL.")
    parser.add_argument("--output-task", type=Path, required=True, help="Shadow refined task JSON output.")
    parser.add_argument("--output-report-json", type=Path)
    parser.add_argument("--output-report-md", type=Path)
    parser.add_argument("--stage", choices=("candidate", "judge"), default="judge")
    parser.add_argument("--max-objects", type=int, default=8)
    parser.add_argument("--pages-per-object", type=int, default=4)
    parser.add_argument("--search-timeout", type=int, default=20)
    parser.add_argument("--source-hint-limit", type=int, default=2)
    parser.add_argument("--output-candidates", type=Path)
    parser.add_argument("--prompt-output", type=Path)
    parser.add_argument("--focused-output-candidates", type=Path)
    parser.add_argument("--focused-prompt-output", type=Path)
    parser.add_argument("--cache-dir", type=Path, default=source_candidates.DEFAULT_CACHE_DIR)
    parser.add_argument("--fetch-timeout", type=int, default=20)
    parser.add_argument("--context-chars", type=int, default=180)
    parser.add_argument("--max-slices-per-object", type=int, default=6)
    parser.add_argument("--skip-fetch-errors", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    task = load_json(args.task)
    gap_rows = load_source_gap_rows(args.feedback_jsonl)
    refined_task, refiner_stats = refine_task_from_source_gap_feedback(
        task,
        gap_rows,
        stage=args.stage,
        max_objects=args.max_objects,
        pages_per_object=args.pages_per_object,
        timeout=args.search_timeout,
        source_hint_limit=args.source_hint_limit,
    )
    write_json(args.output_task, refined_task)

    candidates_path: Path | None = None
    focused_path: Path | None = None
    candidates_payload: dict[str, Any] | None = None
    if args.output_candidates is not None or args.prompt_output is not None or args.focused_output_candidates is not None:
        candidates_payload = source_candidates.build_candidates(
            refined_task,
            cache_dir=args.cache_dir,
            timeout=args.fetch_timeout,
            context_chars=args.context_chars,
            max_slices_per_object=args.max_slices_per_object,
            skip_fetch_errors=args.skip_fetch_errors,
        )
        if args.output_candidates is not None:
            write_json(args.output_candidates, candidates_payload)
            candidates_path = args.output_candidates
        if args.prompt_output is not None:
            write_text(args.prompt_output, candidate_prompt.build_prompt(candidates_payload))
        if args.focused_output_candidates is not None:
            focused_payload = focused_candidates(candidates_payload, object_names=object_names_for_refiner(gap_rows))
            write_json(args.focused_output_candidates, focused_payload)
            focused_path = args.focused_output_candidates
            if args.focused_prompt_output is not None:
                write_text(args.focused_prompt_output, candidate_prompt.build_prompt(focused_payload))

    report = build_bridge_report(
        feedback_paths=args.feedback_jsonl,
        task_path=args.task,
        output_task=args.output_task,
        gap_rows=gap_rows,
        refiner_stats=refiner_stats,
        candidates_path=candidates_path,
        focused_candidates_path=focused_path,
    )
    if args.output_report_json is not None:
        write_json(args.output_report_json, report)
    if args.output_report_md is not None:
        write_text(args.output_report_md, render_markdown(report))

    print(stable_json({"ok": True, "summary": report["inputs"], "refiner_stats": report["refiner_stats"]}))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
