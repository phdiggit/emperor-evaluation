from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
    read_jsonl,
)
from scripts.dev.source_excerpt_pool_lib.profile import (  # noqa: E402
    derive_primary_search_terms,
    fallback_source_titles,
    object_search_terms,
    ExcerptPoolError,
    profile_matches_workflow,
)


DEFAULT_TARGET_STATUSES = ("fetched_needs_profile_work",)
REVIEW_REQUIRED_NOTE = "候选只用于人工审查；脚本不直接改 query profile、不投抓包队列。"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return read_jsonl(path)


def _add_unique(values: list[str], value: str) -> None:
    cleaned = " ".join(str(value).split())
    if cleaned and cleaned not in values:
        values.append(cleaned)


def load_profile_rows(path: Path, *, workflow_code: str = DEFAULT_WORKFLOW_CODE) -> dict[str, dict[str, Any]]:
    workflow_code = normalize_workflow_code(workflow_code)
    profiles: dict[str, dict[str, Any]] = {}
    for row in _read_jsonl(path):
        if not profile_matches_workflow(row, workflow_code):
            continue
        person = str(row.get("person") or "").strip()
        if person:
            if person in profiles:
                raise ExcerptPoolError(f"multiple profiles found for person: {person} workflow_code={workflow_code}")
            profiles[person] = row
    return profiles


def load_status_rows(
    *,
    status_report: Path | None,
    profile_path: Path,
    source_pack_root: Path,
    all_list: Path,
    jobs_dir: Path,
    logs_dir: Path,
    workflow_code: str = DEFAULT_WORKFLOW_CODE,
) -> list[dict[str, Any]]:
    workflow_code = normalize_workflow_code(workflow_code)
    if status_report is not None:
        payload = _read_json(status_report)
        report_workflow_code = str(payload.get("workflow_code") or "").strip()
        if report_workflow_code and normalize_workflow_code(report_workflow_code) != workflow_code:
            raise ExcerptPoolError(
                f"status report workflow_code mismatch: expected {workflow_code}, got {normalize_workflow_code(report_workflow_code)}"
            )
        rows = payload.get("rows")
        if not isinstance(rows, list):
            return []
        return [row for row in rows if isinstance(row, dict) and _status_row_matches_workflow(row, workflow_code)]
    report = build_status_report(
        persons=load_persons(all_list) if all_list.exists() else [],
        profiles=load_profiles(profile_path, workflow_code=workflow_code) if profile_path.exists() else {},
        jobs=load_jobs(jobs_dir, logs_dir),
        packs=load_packs(source_pack_root),
        workflow_code=workflow_code,
    )
    return [row for row in report["rows"] if isinstance(row, dict)]


def _status_row_matches_workflow(row: Mapping[str, Any], workflow_code: str) -> bool:
    row_codes = [
        str(row.get(key) or "").strip()
        for key in ("profile_workflow_code", "job_workflow_code", "pack_workflow_code")
        if str(row.get(key) or "").strip()
    ]
    return not row_codes or all(normalize_workflow_code(code) == workflow_code for code in row_codes)


def _object_layer(profile: Mapping[str, Any], object_name: str) -> str:
    layers = profile.get("object_layers")
    if not isinstance(layers, Mapping):
        return ""
    for layer, names in layers.items():
        if isinstance(names, list) and object_name in names:
            return str(layer)
    return ""


def _existing_aliases(profile: Mapping[str, Any], object_name: str) -> list[str]:
    aliases = profile.get("object_search_aliases")
    if not isinstance(aliases, Mapping):
        return []
    raw = aliases.get(object_name)
    if isinstance(raw, str):
        return [raw.strip()] if raw.strip() else []
    if isinstance(raw, list):
        return [str(value).strip() for value in raw if str(value).strip()]
    return []


def _suggest_aliases(profile: Mapping[str, Any], object_name: str) -> list[str]:
    existing = set(_existing_aliases(profile, object_name))
    suggestions: list[str] = []
    for term in derive_primary_search_terms(object_name):
        if term != object_name and term not in existing:
            _add_unique(suggestions, term)
    return suggestions


def _layer_contexts(layer: str, gap_kind: str) -> tuple[str, ...]:
    if "negative" in layer:
        if gap_kind == "without_excerpts":
            return ("任用风险 人才安全", "诛 贬 罢", "近幸 宗亲 酷吏")
        return ("任用风险", "人才安全", "近幸 宗亲 酷吏")
    if "adjacent" in layer:
        return ("相邻项剥离", "边界 需复核")
    if "supplemental" in layer:
        return ("任用 信任", "举荐 授权", "容人 保全")
    return ("任用 信任", "识拔 举荐", "授权 容人")


def _known_query_texts(profile: Mapping[str, Any]) -> set[str]:
    raw = profile.get("query_bundles")
    return {str(value).strip() for value in raw if str(value).strip()} if isinstance(raw, list) else set()


def _suggest_queries(
    profile: dict[str, Any],
    *,
    object_name: str,
    layer: str,
    gap_kinds: Sequence[str],
    max_per_object: int,
) -> list[str]:
    person = str(profile.get("person") or "").strip()
    existing = _known_query_texts(profile)
    suggestions: list[str] = []
    try:
        terms = object_search_terms(profile, object_name)
    except Exception:
        terms = tuple(derive_primary_search_terms(object_name)) or (object_name,)
    primary_terms = [term for term in terms if len(term) >= 2][:2] or [object_name]
    sources = list(fallback_source_titles(profile))[:3]
    gap = "without_page_hits" if "without_page_hits" in gap_kinds else "without_excerpts"
    for primary in primary_terms:
        for source_title in sources:
            for context in _layer_contexts(layer, gap):
                query = f"{person} {primary} {source_title} {context}"
                if query not in existing:
                    _add_unique(suggestions, query)
                if len(suggestions) >= max_per_object:
                    return suggestions
    return suggestions


def _load_src_docs(pack_dir: Path) -> list[dict[str, Any]]:
    return _read_jsonl(pack_dir / "src_docs.jsonl")


def _source_targets_from_pack(pack_dir: Path, object_name: str) -> list[str]:
    targets: list[str] = []
    for row in _load_src_docs(pack_dir):
        names = row.get("object_names")
        if not isinstance(names, list) or object_name not in names:
            continue
        page_title = str(row.get("page_title") or "").strip()
        if page_title:
            _add_unique(targets, f"{page_title} 抓包命中页，需人工复核")
    return targets


def _gap_kinds(row: Mapping[str, Any], object_name: str) -> list[str]:
    kinds: list[str] = []
    if object_name in set(row.get("objects_without_page_hits") or []):
        kinds.append("without_page_hits")
    if object_name in set(row.get("objects_without_excerpts") or []):
        kinds.append("without_excerpts")
    return kinds


def _refine_object(
    profile: dict[str, Any],
    row: Mapping[str, Any],
    pack_dir: Path,
    object_name: str,
    *,
    max_queries_per_object: int,
) -> dict[str, Any]:
    layer = _object_layer(profile, object_name)
    gap_kinds = _gap_kinds(row, object_name)
    source_targets = _source_targets_from_pack(pack_dir, object_name) if pack_dir.exists() else []
    aliases = _suggest_aliases(profile, object_name)
    queries = _suggest_queries(
        profile,
        object_name=object_name,
        layer=layer,
        gap_kinds=gap_kinds,
        max_per_object=max_queries_per_object,
    )
    confidence = "high" if source_targets else ("medium" if aliases or queries else "low")
    return {
        "object_name": object_name,
        "layer": layer,
        "gap_kinds": gap_kinds,
        "suggested_aliases": aliases,
        "suggested_query_bundles": queries,
        "suggested_source_targets": source_targets,
        "confidence": confidence,
        "requires_review": True,
        "reason": "抓包覆盖缺口触发；按对象缺页/缺摘录生成检索补强候选。",
    }


def _build_patch(object_refinements: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    query_bundles: list[str] = []
    source_targets: list[str] = []
    alias_map: dict[str, list[str]] = {}
    for item in object_refinements:
        object_name = str(item.get("object_name") or "")
        aliases = [str(value) for value in item.get("suggested_aliases") or [] if str(value).strip()]
        if aliases:
            alias_map[object_name] = aliases
        for query in item.get("suggested_query_bundles") or []:
            _add_unique(query_bundles, str(query))
        for target in item.get("suggested_source_targets") or []:
            _add_unique(source_targets, str(target))
    return {
        "merge_object_search_aliases": alias_map,
        "append_query_bundles": query_bundles,
        "append_source_targets": source_targets,
    }


def refine_person(
    profile: dict[str, Any] | None,
    row: Mapping[str, Any],
    *,
    max_queries_per_object: int = 6,
    include_adjacent: bool = False,
) -> dict[str, Any]:
    person = str(row.get("person") or (profile or {}).get("person") or "").strip()
    action_status = str(row.get("action_status") or "")
    if profile is None:
        return {
            "person": person,
            "action_status": action_status,
            "status": "missing_profile",
            "requires_review": True,
            "note": "缺 query profile，不能自动补强。",
            "profile_patch_candidate": _build_patch([]),
            "object_refinements": [],
        }
    if action_status == "profile_needs_work":
        return {
            "person": person,
            "query_profile_id": profile.get("query_profile_id") or "",
            "action_status": action_status,
            "status": "needs_seed_profile",
            "requires_review": True,
            "note": "检索包仍是半成品；需要先补具体对象，再让抓包结果驱动二次补强。",
            "profile_patch_candidate": _build_patch([]),
            "object_refinements": [],
        }

    pack_dir = Path(str(row.get("pack_path") or ""))
    missing_objects = sorted(
        {
            *[str(value) for value in row.get("objects_without_page_hits") or [] if str(value).strip()],
            *[str(value) for value in row.get("objects_without_excerpts") or [] if str(value).strip()],
        }
    )
    object_refinements = []
    skipped_adjacent: list[str] = []
    for object_name in missing_objects:
        layer = _object_layer(profile, object_name)
        if layer == "adjacent_split_objects" and not include_adjacent:
            skipped_adjacent.append(object_name)
            continue
        object_refinements.append(
            _refine_object(profile, row, pack_dir, object_name, max_queries_per_object=max_queries_per_object)
        )
    return {
        "person": person,
        "query_profile_id": profile.get("query_profile_id") or "",
        "action_status": action_status,
        "status": "candidate_generated" if object_refinements else "no_gap_objects",
        "requires_review": True,
        "note": REVIEW_REQUIRED_NOTE,
        "pack_path": str(pack_dir) if str(pack_dir) else "",
        "skipped_adjacent_objects": skipped_adjacent,
        "profile_patch_candidate": _build_patch(object_refinements),
        "object_refinements": object_refinements,
    }


def build_refinement_report(
    *,
    profiles: Mapping[str, dict[str, Any]],
    status_rows: Sequence[Mapping[str, Any]],
    workflow_code: str = DEFAULT_WORKFLOW_CODE,
    persons: Sequence[str] = (),
    target_statuses: Sequence[str] = DEFAULT_TARGET_STATUSES,
    max_queries_per_object: int = 6,
    include_adjacent: bool = False,
) -> dict[str, Any]:
    normalized_workflow_code = normalize_workflow_code(workflow_code)
    person_filter = {person for person in persons if person}
    status_filter = set(target_statuses)
    selected_rows = [
        row
        for row in status_rows
        if (not person_filter or row.get("person") in person_filter)
        and (not status_filter or row.get("action_status") in status_filter)
    ]
    refinements = [
        refine_person(
            profiles.get(str(row.get("person") or "")),
            row,
            max_queries_per_object=max_queries_per_object,
            include_adjacent=include_adjacent,
        )
        for row in selected_rows
    ]
    patch_count = sum(
        len(item["profile_patch_candidate"]["append_query_bundles"])
        + len(item["profile_patch_candidate"]["append_source_targets"])
        + sum(len(values) for values in item["profile_patch_candidate"]["merge_object_search_aliases"].values())
        for item in refinements
    )
    return {
        "workflow_code": normalized_workflow_code,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "review_required": True,
        "target_statuses": list(target_statuses),
        "totals": {
            "persons": len(refinements),
            "object_refinements": sum(len(item["object_refinements"]) for item in refinements),
            "skipped_adjacent_objects": sum(len(item.get("skipped_adjacent_objects", [])) for item in refinements),
            "patch_suggestions": patch_count,
        },
        "refinements": refinements,
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    totals = report.get("totals") if isinstance(report.get("totals"), Mapping) else {}
    workflow_code = str(report.get("workflow_code") or DEFAULT_WORKFLOW_CODE)
    lines = [
        f"# {workflow_code} 检索包补强候选",
        "",
        f"- workflow_code: `{workflow_code}`",
        f"- generated_at: `{report.get('generated_at') or ''}`",
        f"- persons: `{totals.get('persons', 0)}`",
        f"- object_refinements: `{totals.get('object_refinements', 0)}`",
        f"- skipped_adjacent_objects: `{totals.get('skipped_adjacent_objects', 0)}`",
        f"- patch_suggestions: `{totals.get('patch_suggestions', 0)}`",
        "- review_required: `true`",
        "",
        "候选只用于审查，不会自动改 query profile，也不会投抓包队列。",
        "",
    ]
    for person in report.get("refinements") or []:
        if not isinstance(person, Mapping):
            continue
        lines.extend([f"## {person.get('person', '')}", ""])
        lines.append(f"- action_status: `{person.get('action_status', '')}`")
        lines.append(f"- status: `{person.get('status', '')}`")
        if person.get("note"):
            lines.append(f"- note: {person.get('note')}")
        patch = person.get("profile_patch_candidate") if isinstance(person.get("profile_patch_candidate"), Mapping) else {}
        aliases = patch.get("merge_object_search_aliases") if isinstance(patch.get("merge_object_search_aliases"), Mapping) else {}
        if aliases:
            lines.append("- suggested_aliases:")
            for object_name, values in aliases.items():
                lines.append(f"  - {object_name}: {'、'.join(values)}")
        if patch.get("append_source_targets"):
            lines.append("- append_source_targets:")
            for target in patch.get("append_source_targets") or []:
                lines.append(f"  - {target}")
        if patch.get("append_query_bundles"):
            lines.append("- append_query_bundles:")
            for query in patch.get("append_query_bundles") or []:
                lines.append(f"  - {query}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate review-only query-profile refinement candidates from source-pack gaps.")
    parser.add_argument("--profile", type=Path, default=None, help="Query-profile JSONL path.")
    parser.add_argument("--workflow-code", default=DEFAULT_WORKFLOW_CODE, help="Workflow/subitem code for report metadata.")
    parser.add_argument("--status-report", type=Path, default=None, help="Optional i5b_source_pack_status JSON report.")
    parser.add_argument("--source-pack-root", type=Path, default=None, help="Source-pack root when no status report is provided.")
    parser.add_argument("--all-list", type=Path, default=DEFAULT_ALL_LIST, help="YAML list used only when building status on the fly.")
    parser.add_argument("--jobs-dir", type=Path, default=None, help="Jobs directory used only when building status on the fly.")
    parser.add_argument("--logs-dir", type=Path, default=None, help="Logs directory used only when building status on the fly.")
    parser.add_argument("--person", action="append", default=[], help="Limit to one person; may be repeated.")
    parser.add_argument("--status", action="append", default=[], help="Limit action_status; defaults to fetched_needs_profile_work.")
    parser.add_argument("--max-queries-per-object", type=int, default=6)
    parser.add_argument("--include-adjacent", action="store_true", help="Also generate candidates for adjacent_split_objects.")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    workflow_code = normalize_workflow_code(args.workflow_code)
    source_paths = load_source_excerpt_pool_paths(workflow_code=workflow_code)
    profile_path = args.profile or source_paths.get("query_profile") or DEFAULT_PROFILE
    source_pack_root = args.source_pack_root or source_paths.get("source_pack_root") or _default_source_pack_root(workflow_code=workflow_code)
    jobs_dir = args.jobs_dir or source_paths.get("jobs_dir") or source_pack_root.parent / "jobs"
    logs_dir = args.logs_dir or source_paths.get("logs_dir") or source_pack_root.parent / "logs"
    profiles = load_profile_rows(profile_path, workflow_code=workflow_code) if profile_path.exists() else {}
    status_rows = load_status_rows(
        status_report=args.status_report,
        profile_path=profile_path,
        source_pack_root=source_pack_root,
        all_list=args.all_list,
        jobs_dir=jobs_dir,
        logs_dir=logs_dir,
        workflow_code=workflow_code,
    )
    report = build_refinement_report(
        profiles=profiles,
        status_rows=status_rows,
        workflow_code=workflow_code,
        persons=args.person,
        target_statuses=args.status or list(DEFAULT_TARGET_STATUSES),
        max_queries_per_object=args.max_queries_per_object,
        include_adjacent=args.include_adjacent,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n" if args.format == "json" else render_markdown(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
