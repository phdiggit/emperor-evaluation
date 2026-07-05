from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v2_contracts import alias_script_variants


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected object JSON: {path}")
    return payload


def pretty_json(value: Mapping[str, Any]) -> str:
    return json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def resolve_run_path(path: str | Path, *, run_root: Path) -> Path:
    candidate = Path(path)
    if candidate.exists():
        return candidate
    return run_root / candidate


def text(value: Any) -> str:
    return str(value or "").strip()


def object_name_variants(value: str) -> set[str]:
    return set(alias_script_variants(value)) or {value}


def object_sets_match(left: str, right: str) -> bool:
    return bool(object_name_variants(left) & object_name_variants(right))


def unmatched_objects(source: set[str], target: set[str]) -> list[str]:
    return sorted(name for name in source if not any(object_sets_match(name, other) for other in target))


def coverage_pair_matches(left: Sequence[Any], right: Sequence[Any]) -> bool:
    if len(left) < 2 or len(right) < 2:
        return False
    return str(left[1]) == str(right[1]) and object_sets_match(str(left[0]), str(right[0]))


def unmatched_coverage_pairs(source: set[tuple[str, str]], target: set[tuple[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for pair in sorted(source):
        if not any(coverage_pair_matches(pair, other) for other in target):
            rows.append({"object_name": pair[0], "direction": pair[1]})
    return rows


def person_name_from_payloads(
    *,
    summary_person: Mapping[str, Any] | None,
    candidates: Mapping[str, Any] | None,
    judge: Mapping[str, Any] | None,
    fallback: str,
) -> str:
    if summary_person and text(summary_person.get("name")):
        return text(summary_person.get("name"))
    for payload in (candidates, judge):
        if not isinstance(payload, Mapping):
            continue
        identity = payload.get("task_identity") if isinstance(payload.get("task_identity"), Mapping) else {}
        for key in ("emperor_name", "name"):
            if text(identity.get(key)):
                return text(identity.get(key))
            if text(payload.get(key)):
                return text(payload.get(key))
    return fallback


def metric_from_summary(summary_person: Mapping[str, Any] | None, key: str, fallback: int) -> int:
    if not summary_person:
        return fallback
    value = summary_person.get(key)
    return int(value) if isinstance(value, int) else fallback


def summarize_person_run(
    *,
    name: str,
    summary_person: Mapping[str, Any] | None,
    candidates: Mapping[str, Any] | None,
    judge: Mapping[str, Any] | None,
    run_dir: Path,
) -> dict[str, Any]:
    claims = [row for row in (judge or {}).get("claims") or [] if isinstance(row, Mapping)]
    claims_by_code = {text(row.get("claim_code")): row for row in claims if text(row.get("claim_code"))}
    primary_bindings = [
        row
        for row in ((judge or {}).get("primary_bindings") or (judge or {}).get("bindings") or [])
        if isinstance(row, Mapping)
    ]
    scoring_bindings = [
        row
        for row in primary_bindings
        if row.get("usable_for_scoring_cluster", True) is not False
        and text(row.get("claim_code")) in claims_by_code
    ]
    candidate_gaps = [row for row in (candidates or {}).get("coverage_gaps") or [] if isinstance(row, Mapping)]
    judge_gaps = [row for row in (judge or {}).get("coverage_gaps") or [] if isinstance(row, Mapping)]
    coverage = candidates.get("coverage") if isinstance((candidates or {}).get("coverage"), Mapping) else {}
    objects = {text(row.get("object_name")) for row in claims if text(row.get("object_name"))}
    object_direction_coverage = sorted(
        {
            (
                text(claims_by_code[text(row.get("claim_code"))].get("object_name")),
                text(row.get("direction")),
            )
            for row in scoring_bindings
            if text(claims_by_code[text(row.get("claim_code"))].get("object_name"))
            and text(row.get("direction"))
        }
    )
    return {
        "name": name,
        "run_dir": str(run_dir),
        "status": (judge or {}).get("status") or (summary_person or {}).get("judge_status"),
        "object_names": sorted(objects),
        "object_count": len(objects),
        "object_direction_coverage": [
            {"object_name": object_name, "direction": direction}
            for object_name, direction in object_direction_coverage
        ],
        "object_direction_count": len(object_direction_coverage),
        "claim_count": len(claims) if judge else metric_from_summary(summary_person, "claim_count", 0),
        "primary_binding_count": len(primary_bindings)
        if judge
        else metric_from_summary(summary_person, "primary_binding_count", 0),
        "scoring_binding_count": len(scoring_bindings),
        "candidate_slices": (candidates.get("stats") or {}).get("candidate_slices")
        if candidates
        else (summary_person or {}).get("candidate_slices"),
        "candidate_gap_count": len(candidate_gaps)
        if candidates
        else metric_from_summary(summary_person, "candidate_coverage_gaps", 0),
        "judge_gap_count": len(judge_gaps)
        if judge
        else metric_from_summary(summary_person, "judge_coverage_gap_count", 0),
        "objects_without_slices": list(coverage.get("objects_without_slices") or []),
        "directions": dict(Counter(text(row.get("direction")) for row in claims if text(row.get("direction")))),
        "judge_gap_keys": [
            {
                "gap_type": gap.get("gap_type"),
                "object_name": gap.get("object_name"),
                "family_code": gap.get("family_code"),
            }
            for gap in judge_gaps
        ],
    }


def collect_new_style_people(run_root: Path, summary: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    people: dict[str, dict[str, Any]] = {}
    for raw_person in summary.get("people") or []:
        if not isinstance(raw_person, Mapping):
            continue
        files = raw_person.get("files") if isinstance(raw_person.get("files"), Mapping) else {}
        judge_path = files.get("final_judge_result")
        candidates_path = files.get("final_candidates")
        if not judge_path:
            continue
        judge_file = resolve_run_path(str(judge_path), run_root=run_root)
        candidates_file = resolve_run_path(str(candidates_path), run_root=run_root) if candidates_path else None
        if not judge_file.exists():
            continue
        judge = load_json(judge_file)
        candidates = load_json(candidates_file) if candidates_file and candidates_file.exists() else None
        name = person_name_from_payloads(
            summary_person=raw_person,
            candidates=candidates,
            judge=judge,
            fallback=judge_file.parent.name,
        )
        people[name] = summarize_person_run(
            name=name,
            summary_person=raw_person,
            candidates=candidates,
            judge=judge,
            run_dir=judge_file.parent,
        )
    return people


def collect_legacy_people(run_root: Path, summary: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    summary_by_name = {
        text(row.get("name")): row for row in summary.get("people") or [] if isinstance(row, Mapping) and text(row.get("name"))
    }
    people: dict[str, dict[str, Any]] = {}
    for subdir in sorted(path for path in run_root.iterdir() if path.is_dir()):
        judge_file = subdir / "judge_result.json"
        candidates_file = subdir / "candidates.json"
        if not judge_file.exists():
            continue
        judge = load_json(judge_file)
        candidates = load_json(candidates_file) if candidates_file.exists() else None
        name = person_name_from_payloads(
            summary_person=None,
            candidates=candidates,
            judge=judge,
            fallback=subdir.name,
        )
        people[name] = summarize_person_run(
            name=name,
            summary_person=summary_by_name.get(name),
            candidates=candidates,
            judge=judge,
            run_dir=subdir,
        )
    return people


def collect_run_people(run_root: Path) -> dict[str, dict[str, Any]]:
    summary_path = run_root / "summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"missing summary.json under {run_root}")
    summary = load_json(summary_path)
    people = collect_new_style_people(run_root, summary)
    if people:
        return people
    return collect_legacy_people(run_root, summary)


def ratio_below(candidate: int, baseline: int, minimum_ratio: float) -> bool:
    if baseline <= 0:
        return False
    return candidate < baseline * minimum_ratio


def compare_person(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    min_claim_ratio: float,
    min_primary_ratio: float,
    max_lost_objects: int,
) -> dict[str, Any]:
    baseline_objects = set(str(value) for value in baseline.get("object_names") or [])
    candidate_objects = set(str(value) for value in candidate.get("object_names") or [])
    lost = unmatched_objects(baseline_objects, candidate_objects)
    gained = unmatched_objects(candidate_objects, baseline_objects)
    baseline_object_directions = {
        (str(row.get("object_name") or ""), str(row.get("direction") or ""))
        for row in baseline.get("object_direction_coverage") or []
        if isinstance(row, Mapping) and row.get("object_name") and row.get("direction")
    }
    candidate_object_directions = {
        (str(row.get("object_name") or ""), str(row.get("direction") or ""))
        for row in candidate.get("object_direction_coverage") or []
        if isinstance(row, Mapping) and row.get("object_name") and row.get("direction")
    }
    lost_object_directions = unmatched_coverage_pairs(baseline_object_directions, candidate_object_directions)
    blocks: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if len(lost) > max_lost_objects:
        blocks.append(
            {
                "code": "object_coverage_regressed",
                "message": f"lost {len(lost)} baseline objects",
                "objects": lost,
            }
        )
    if lost_object_directions:
        blocks.append(
            {
                "code": "object_direction_coverage_regressed",
                "message": f"lost {len(lost_object_directions)} baseline object-direction pairs",
                "pairs": lost_object_directions,
            }
        )
    if baseline.get("status") == "succeeded" and candidate.get("status") != "succeeded":
        blocks.append(
            {
                "code": "status_regressed",
                "message": f"baseline succeeded but candidate status is {candidate.get('status')}",
            }
        )
    if candidate.get("objects_without_slices"):
        blocks.append(
            {
                "code": "objects_without_slices",
                "message": "candidate has object seeds without slices",
                "objects": candidate.get("objects_without_slices"),
            }
        )
    if ratio_below(int(candidate.get("claim_count") or 0), int(baseline.get("claim_count") or 0), min_claim_ratio):
        blocks.append(
            {
                "code": "claim_count_regressed",
                "message": f"candidate claims {candidate.get('claim_count')} below baseline {baseline.get('claim_count')}",
            }
        )
    if ratio_below(
        int(candidate.get("primary_binding_count") or 0),
        int(baseline.get("primary_binding_count") or 0),
        min_primary_ratio,
    ):
        warnings.append(
            {
                "code": "primary_binding_count_regressed",
                "message": "candidate primary bindings below baseline threshold",
            }
        )
    if int(candidate.get("judge_gap_count") or 0) > int(baseline.get("judge_gap_count") or 0):
        warnings.append(
            {
                "code": "judge_gap_count_increased",
                "message": f"candidate judge gaps {candidate.get('judge_gap_count')} > baseline {baseline.get('judge_gap_count')}",
                "gaps": candidate.get("judge_gap_keys") or [],
            }
        )
    return {
        "name": baseline.get("name") or candidate.get("name"),
        "ok": not blocks,
        "baseline": {
            "status": baseline.get("status"),
            "object_count": baseline.get("object_count"),
            "claim_count": baseline.get("claim_count"),
            "primary_binding_count": baseline.get("primary_binding_count"),
            "scoring_binding_count": baseline.get("scoring_binding_count"),
            "object_direction_count": baseline.get("object_direction_count"),
            "judge_gap_count": baseline.get("judge_gap_count"),
        },
        "candidate": {
            "status": candidate.get("status"),
            "object_count": candidate.get("object_count"),
            "claim_count": candidate.get("claim_count"),
            "primary_binding_count": candidate.get("primary_binding_count"),
            "scoring_binding_count": candidate.get("scoring_binding_count"),
            "object_direction_count": candidate.get("object_direction_count"),
            "judge_gap_count": candidate.get("judge_gap_count"),
            "objects_without_slices": candidate.get("objects_without_slices"),
        },
        "lost_objects": lost,
        "gained_objects": gained,
        "blocks": blocks,
        "warnings": warnings,
    }


def compare_runs(
    *,
    baseline_run_root: Path,
    candidate_run_root: Path,
    min_claim_ratio: float = 0.9,
    min_primary_ratio: float = 0.9,
    max_lost_objects: int = 0,
) -> dict[str, Any]:
    baseline_people = collect_run_people(baseline_run_root)
    candidate_people = collect_run_people(candidate_run_root)
    people: list[dict[str, Any]] = []
    blocks: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for name in sorted(set(baseline_people) | set(candidate_people)):
        if name not in baseline_people:
            warning = {"code": "new_person_only", "name": name}
            warnings.append(warning)
            continue
        if name not in candidate_people:
            block = {"code": "missing_candidate_person", "name": name}
            blocks.append(block)
            continue
        row = compare_person(
            baseline_people[name],
            candidate_people[name],
            min_claim_ratio=min_claim_ratio,
            min_primary_ratio=min_primary_ratio,
            max_lost_objects=max_lost_objects,
        )
        people.append(row)
        for issue in row["blocks"]:
            blocks.append({"name": name, **issue})
        for issue in row["warnings"]:
            warnings.append({"name": name, **issue})

    return {
        "ok": not blocks,
        "baseline_run_root": str(baseline_run_root),
        "candidate_run_root": str(candidate_run_root),
        "thresholds": {
            "min_claim_ratio": min_claim_ratio,
            "min_primary_ratio": min_primary_ratio,
            "max_lost_objects": max_lost_objects,
        },
        "people": people,
        "blocks": blocks,
        "warnings": warnings,
        "totals": {
            "people_compared": len(people),
            "blocks": len(blocks),
            "warnings": len(warnings),
        },
    }


def markdown_report(payload: Mapping[str, Any]) -> str:
    lines = [
        "# retrieval_v2 quality gate",
        "",
        f"- ok: `{str(payload.get('ok')).lower()}`",
        f"- baseline: `{payload.get('baseline_run_root')}`",
        f"- candidate: `{payload.get('candidate_run_root')}`",
        f"- blocks: `{len(payload.get('blocks') or [])}`",
        f"- warnings: `{len(payload.get('warnings') or [])}`",
        "",
        "| person | ok | objects baseline -> candidate | claims baseline -> candidate | primary baseline -> candidate | scoring baseline -> candidate | lost | warnings |",
        "|---|---:|---:|---:|---:|---:|---|---:|",
    ]
    for row in payload.get("people") or []:
        baseline = row.get("baseline") or {}
        candidate = row.get("candidate") or {}
        lost = ", ".join(row.get("lost_objects") or [])
        lines.append(
            " | ".join(
                [
                    str(row.get("name") or ""),
                    "`yes`" if row.get("ok") else "`no`",
                    f"{baseline.get('object_count')} -> {candidate.get('object_count')}",
                    f"{baseline.get('claim_count')} -> {candidate.get('claim_count')}",
                    f"{baseline.get('primary_binding_count')} -> {candidate.get('primary_binding_count')}",
                    f"{baseline.get('scoring_binding_count')} -> {candidate.get('scoring_binding_count')}",
                    lost or "-",
                    str(len(row.get("warnings") or [])),
                ]
            )
        )
    if payload.get("blocks"):
        lines.extend(["", "## Blocks", ""])
        for issue in payload.get("blocks") or []:
            lines.append(f"- `{issue.get('code')}` {issue.get('name', '')}: {issue.get('message', '')}")
    return "\n".join(lines) + "\n"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare retrieval_v2 clean runs against a quality baseline.")
    parser.add_argument("--baseline-run-root", type=Path, required=True)
    parser.add_argument("--candidate-run-root", type=Path, required=True)
    parser.add_argument("--min-claim-ratio", type=float, default=0.9)
    parser.add_argument("--min-primary-ratio", type=float, default=0.9)
    parser.add_argument("--max-lost-objects", type=int, default=0)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--fail-on-block", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    payload = compare_runs(
        baseline_run_root=args.baseline_run_root,
        candidate_run_root=args.candidate_run_root,
        min_claim_ratio=args.min_claim_ratio,
        min_primary_ratio=args.min_primary_ratio,
        max_lost_objects=args.max_lost_objects,
    )
    if args.format == "markdown":
        print(markdown_report(payload), end="")
    else:
        print(pretty_json(payload), end="")
    return 1 if args.fail_on_block and not payload["ok"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
