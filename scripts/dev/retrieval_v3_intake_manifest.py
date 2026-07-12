from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class IntakeManifestError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise IntakeManifestError(f"{path}: expected JSON object")
    return payload


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def text(value: Any) -> str:
    return str(value or "").strip()


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def resolve_artifact(path_text: str, *, run_root: Path) -> Path:
    raw = Path(path_text)
    candidates = [raw]
    if not raw.is_absolute():
        candidates.extend([ROOT / raw, run_root / raw])
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return raw if raw.is_absolute() else ROOT / raw


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_record(kind: str, path: Path) -> dict[str, Any]:
    exists = path.exists()
    return {
        "kind": kind,
        "path": repo_relative(path),
        "exists": exists,
        "sha256": sha256_file(path) if exists and path.is_file() else "",
    }


def sanitize_code_part(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9]+", "-", value.strip().upper()).strip("-")
    return clean or "UNKNOWN"


def source_pack_code(*, target_code: str, rule_code: str, run_root: Path, judge_path: Path) -> str:
    seed = "|".join([target_code, rule_code, repo_relative(run_root), repo_relative(judge_path)])
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:10].upper()
    target_part = sanitize_code_part(target_code.removeprefix("TGT-"))
    rule_part = sanitize_code_part(rule_code)
    return f"SPK-{target_part}-{rule_part}-{digest}"


def count_rows(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    return len(value) if isinstance(value, list) else 0


def mapping_rows(payload: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    value = payload.get(key)
    return [row for row in value if isinstance(row, Mapping)] if isinstance(value, list) else []


def context_from_task_person(task: Mapping[str, Any], person: Mapping[str, Any]) -> dict[str, str]:
    return {
        "target_code": text(task.get("target_code") or person.get("target_code")),
        "emperor_name": text(task.get("emperor_name") or person.get("name")),
        "item_code": text(task.get("item_code") or person.get("item_code") or "I5B"),
        "rule_code": text(task.get("rule_code") or person.get("rule_code") or "appointment_delegation"),
    }


def gate_issues(
    *,
    context: Mapping[str, str],
    person: Mapping[str, Any],
    artifacts: Sequence[Mapping[str, Any]],
    judge: Mapping[str, Any],
) -> list[str]:
    issues: list[str] = []
    missing = [row["kind"] for row in artifacts if not row.get("exists")]
    if missing:
        issues.append("missing_artifacts:" + ",".join(missing))
    if text(judge.get("status") or person.get("judge_status")) != "succeeded":
        issues.append("judge_status_not_succeeded")
    if person.get("judge_anomaly_block_count") != 0:
        issues.append("judge_anomaly_block_count_not_zero")
    if not context.get("target_code"):
        issues.append("target_code_missing")
    if not context.get("emperor_name"):
        issues.append("emperor_name_missing")
    if not context.get("item_code"):
        issues.append("item_code_missing")
    if not context.get("rule_code"):
        issues.append("rule_code_missing")
    return issues


def package_from_person(summary_path: Path, person: Mapping[str, Any]) -> dict[str, Any]:
    run_root = summary_path.parent
    files = person.get("files") if isinstance(person.get("files"), Mapping) else {}
    task_path = (
        resolve_artifact(text(files.get("final_task")), run_root=run_root)
        if files.get("final_task")
        else run_root / "__missing_task.final.json"
    )
    candidates_path = (
        resolve_artifact(text(files.get("final_candidates")), run_root=run_root)
        if files.get("final_candidates")
        else run_root / "__missing_candidates.final.json"
    )
    judge_path = (
        resolve_artifact(text(files.get("final_judge_result")), run_root=run_root)
        if files.get("final_judge_result")
        else run_root / "__missing_judge_result.final.json"
    )

    task = load_json(task_path) if task_path.exists() and task_path.is_file() else {}
    candidates = load_json(candidates_path) if candidates_path.exists() and candidates_path.is_file() else {}
    judge = load_json(judge_path) if judge_path.exists() and judge_path.is_file() else {}
    context = context_from_task_person(task, person)
    artifacts = [
        artifact_record("summary", summary_path),
        artifact_record("task", task_path),
        artifact_record("candidates", candidates_path),
        artifact_record("judge", judge_path),
    ]
    issues = gate_issues(context=context, person=person, artifacts=artifacts, judge=judge)
    pack_code = source_pack_code(
        target_code=context["target_code"] or "UNKNOWN",
        rule_code=context["rule_code"] or "UNKNOWN",
        run_root=run_root,
        judge_path=judge_path,
    )
    coverage = candidates.get("coverage") if isinstance(candidates.get("coverage"), Mapping) else {}
    package = {
        "acceptance_status": "accepted" if not issues else "rejected",
        "acceptance_issues": issues,
        "source_pack_code": pack_code,
        "target_code": context["target_code"],
        "emperor_name": context["emperor_name"],
        "item_code": context["item_code"],
        "rule_code": context["rule_code"],
        "run_root": repo_relative(run_root),
        "run_dir": text(person.get("run_dir")) or repo_relative(judge_path.parent),
        "artifacts": artifacts,
        "gate": {
            "judge_status": text(judge.get("status") or person.get("judge_status")),
            "judge_anomaly_block_count": person.get("judge_anomaly_block_count"),
            "final_judge_exists": judge_path.exists(),
        },
        "counts": {
            "source_documents": count_rows(judge, "documents"),
            "source_passages": count_rows(judge, "passages"),
            "claims": count_rows(judge, "claims"),
            "primary_bindings": count_rows(judge, "primary_bindings"),
            "secondary_binding_candidates": count_rows(judge, "secondary_binding_candidates"),
            "candidate_slices": person.get("candidate_slices"),
            "candidate_coverage_gaps": count_rows(candidates, "coverage_gaps"),
            "judge_coverage_gaps": count_rows(judge, "coverage_gaps"),
            "fetch_errors": count_rows(candidates, "fetch_errors"),
        },
        "objects_without_slices": list(coverage.get("objects_without_slices") or person.get("objects_without_slices") or []),
        "claim_objects": sorted({text(row.get("object_name")) for row in mapping_rows(judge, "claims") if text(row.get("object_name"))}),
    }
    return package


def iter_summary_people(summary_path: Path, emperors: set[str]) -> Iterable[dict[str, Any]]:
    summary = load_json(summary_path)
    for person in summary.get("people") or []:
        if not isinstance(person, Mapping):
            continue
        name = text(person.get("name"))
        if emperors and name not in emperors:
            continue
        yield package_from_person(summary_path, person)


def build_manifest(*, summary_paths: Sequence[Path], emperors: set[str] | None = None) -> dict[str, Any]:
    selected_emperors = emperors or set()
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for summary_path in summary_paths:
        for package in iter_summary_people(summary_path, selected_emperors):
            if package["acceptance_status"] == "accepted":
                accepted.append(package)
            else:
                rejected.append(package)

    seen: dict[tuple[str, str, str], str] = {}
    for package in accepted:
        key = (package["emperor_name"], package["item_code"], package["rule_code"])
        if key in seen:
            raise IntakeManifestError(
                f"duplicate accepted package for {key}: {seen[key]} and {package['source_pack_code']}"
            )
        seen[key] = package["source_pack_code"]

    return {
        "generated_by": "scripts/dev/retrieval_v3_intake_manifest.py",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "acceptance_policy": {
            "judge_status": "succeeded",
            "judge_anomaly_block_count": 0,
            "required_artifacts": ["summary", "task", "candidates", "judge"],
        },
        "summary_paths": [repo_relative(path) for path in summary_paths],
        "packages": sorted(accepted, key=lambda row: (row["emperor_name"], row["source_pack_code"])),
        "rejected_packages": sorted(rejected, key=lambda row: (row["emperor_name"], row["source_pack_code"])),
        "totals": {
            "accepted": len(accepted),
            "rejected": len(rejected),
            "claims": sum(int(row["counts"]["claims"] or 0) for row in accepted),
            "primary_bindings": sum(int(row["counts"]["primary_bindings"] or 0) for row in accepted),
            "secondary_binding_candidates": sum(
                int(row["counts"]["secondary_binding_candidates"] or 0) for row in accepted
            ),
            "judge_coverage_gaps": sum(int(row["counts"]["judge_coverage_gaps"] or 0) for row in accepted),
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a retrieval_v3 accepted-run intake manifest.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="Build intake_manifest.json from clean runner summary files.")
    build.add_argument("--summary", type=Path, action="append", required=True)
    build.add_argument("--emperor", action="append", default=[])
    build.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "build":
        raise IntakeManifestError(f"unsupported command: {args.command}")
    manifest = build_manifest(summary_paths=args.summary, emperors=set(args.emperor or []))
    write_json(args.output, manifest)
    print(
        json.dumps(
            {"output": str(args.output), "totals": manifest["totals"]},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
