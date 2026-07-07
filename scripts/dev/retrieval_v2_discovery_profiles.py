from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev import retrieval_v2_task_skeleton as task_skeleton


class RetrievalV2DiscoveryProfileError(RuntimeError):
    pass


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    atomic_write_text(path, pretty_json(dict(payload)))


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RetrievalV2DiscoveryProfileError(f"expected object JSON: {path}")
    return payload


def safe_slug(value: Any) -> str:
    text = re.sub(r"[^A-Za-z0-9_.\-\u4e00-\u9fff]+", "_", str(value or "")).strip("._")
    return text or "unknown"


def profile_from_task(task: Mapping[str, Any]) -> dict[str, Any]:
    return task_skeleton.discovery_profile_from_task(task)


def recall_terms_from_delta(delta: Mapping[str, Any]) -> list[str]:
    terms: list[Any] = []
    updates = delta.get("proposed_updates") if isinstance(delta.get("proposed_updates"), list) else []
    for update in updates:
        if not isinstance(update, Mapping):
            continue
        if update.get("target_location") != "source_discovery_profile":
            continue
        if update.get("target_field") != "rule_terms":
            continue
        if update.get("operation") != "append_unique":
            continue
        terms.extend(update.get("add_terms") or [])
    return task_skeleton.unique_strings(terms)


def conditional_terms_from_delta(delta: Mapping[str, Any]) -> list[dict[str, Any]]:
    terms: list[dict[str, Any]] = []
    updates = delta.get("proposed_updates") if isinstance(delta.get("proposed_updates"), list) else []
    for update in updates:
        if not isinstance(update, Mapping):
            continue
        if update.get("target_location") != "source_discovery_profile":
            continue
        if update.get("target_field") != "conditional_rule_terms":
            continue
        if update.get("operation") != "append_guarded_terms":
            continue
        for row in update.get("conditional_terms") or []:
            if isinstance(row, Mapping):
                terms.append(dict(row))
    return terms


def profile_recall_delta_preview(profile: Mapping[str, Any], delta: Mapping[str, Any]) -> dict[str, Any]:
    result = json.loads(pretty_json(profile))
    add_terms = recall_terms_from_delta(delta)
    conditional_terms = conditional_terms_from_delta(delta)
    result["rule_terms"] = task_skeleton.unique_strings([*(result.get("rule_terms") or []), *add_terms])
    result["recall_term_overlays"] = [
        *(result.get("recall_term_overlays") or []),
        {
            "source_delta_version": delta.get("version"),
            "source_report_type": delta.get("report_type"),
            "target_location": "source_discovery_profile",
            "target_field": "rule_terms",
            "operation": "append_unique",
            "add_terms": add_terms,
            "conditional_terms_not_injected": conditional_terms,
        },
    ]
    result["preview_metadata"] = {
        "generated_by": "scripts/dev/retrieval_v2_discovery_profiles.py",
        "preview_type": "recall_term_delta_preview",
        "writes_profile": False,
        "requires_regression_before_prompt_removal": True,
        "appended_rule_term_count": len(add_terms),
        "conditional_term_not_injected_count": len(conditional_terms),
        "preview_fingerprint": task_skeleton.stable_fingerprint(
            {
                "profile_fingerprint": profile.get("profile_fingerprint"),
                "rule_terms": result["rule_terms"],
                "delta_version": delta.get("version"),
            }
        ),
    }
    return result


def task_recall_delta_preview(task: Mapping[str, Any], delta: Mapping[str, Any]) -> dict[str, Any]:
    result = json.loads(pretty_json(task))
    add_terms = recall_terms_from_delta(delta)
    conditional_terms = conditional_terms_from_delta(delta)
    result["rule_terms"] = task_skeleton.unique_strings([*(result.get("rule_terms") or []), *add_terms])
    result["recall_term_overlays"] = [
        *(result.get("recall_term_overlays") or []),
        {
            "source_delta_version": delta.get("version"),
            "source_report_type": delta.get("report_type"),
            "target_location": "task.rule_terms",
            "operation": "append_unique",
            "add_terms": add_terms,
            "conditional_terms_not_injected": conditional_terms,
        },
    ]
    result["preview_metadata"] = {
        "generated_by": "scripts/dev/retrieval_v2_discovery_profiles.py",
        "preview_type": "recall_term_delta_task_preview",
        "writes_task": False,
        "writes_profile": False,
        "requires_regression_before_prompt_removal": True,
        "appended_rule_term_count": len(add_terms),
        "conditional_term_not_injected_count": len(conditional_terms),
        "preview_fingerprint": task_skeleton.stable_fingerprint(
            {
                "target_code": task.get("target_code"),
                "task_fingerprint": task.get("task_skeleton", {}).get("context_fingerprint")
                if isinstance(task.get("task_skeleton"), Mapping)
                else None,
                "rule_terms": result["rule_terms"],
                "delta_version": delta.get("version"),
            }
        ),
    }
    return result


def validate_profile(profile: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    if not str(profile.get("emperor_name") or "").strip():
        issues.append("emperor_name is empty")
    if not isinstance(profile.get("object_seeds"), list) or not profile.get("object_seeds"):
        issues.append("object_seeds is empty")
    if not isinstance(profile.get("source_documents"), list) or not profile.get("source_documents"):
        issues.append("source_documents is empty")
    return issues


def profile_matches_context(
    profile: Mapping[str, Any],
    context: Mapping[str, Any],
    *,
    allow_cross_rule: bool = False,
) -> bool:
    emperor_name = task_skeleton.text_from(profile, "emperor_name")
    if emperor_name and emperor_name != task_skeleton.text_from(context, "emperor_name"):
        return False
    item_code = task_skeleton.text_from(profile, "item_code")
    if item_code and item_code != task_skeleton.text_from(context, "item_code"):
        return False
    profile_rule = task_skeleton.text_from(profile, "rule_code")
    if allow_cross_rule:
        return True
    return not profile_rule or profile_rule == task_skeleton.text_from(context, "rule_code")


def profile_score(profile: Mapping[str, Any], context: Mapping[str, Any]) -> tuple[int, int, str]:
    score = 0
    if task_skeleton.text_from(profile, "rule_code") == task_skeleton.text_from(context, "rule_code"):
        score += 100
    if task_skeleton.text_from(profile, "item_code") == task_skeleton.text_from(context, "item_code"):
        score += 20
    score += min(len(profile.get("object_seeds") or []), 30)
    score += min(len(profile.get("source_documents") or []), 20)
    return (score, len(str(profile.get("profile_fingerprint") or "")), str(profile.get("_path") or ""))


def select_profile(
    profiles: Sequence[Mapping[str, Any]],
    context: Mapping[str, Any],
    *,
    allow_cross_rule: bool = False,
) -> Mapping[str, Any] | None:
    valid_profiles = [
        profile
        for profile in profiles
        if not validate_profile(profile) and profile_matches_context(profile, context, allow_cross_rule=allow_cross_rule)
    ]
    if not valid_profiles:
        return None
    return sorted(valid_profiles, key=lambda profile: profile_score(profile, context), reverse=True)[0]


def profile_output_path(profile: Mapping[str, Any], profile_root: Path) -> Path:
    item_code = safe_slug(profile.get("item_code") or "item")
    emperor = safe_slug(profile.get("emperor_name") or "target")
    rule = safe_slug(profile.get("rule_code") or "generic")
    fingerprint = str(profile.get("profile_fingerprint") or task_skeleton.stable_fingerprint(profile))[:12]
    return profile_root / item_code / emperor / f"{rule}.{fingerprint}.json"


def write_profile(profile: Mapping[str, Any], profile_root: Path) -> Path:
    issues = validate_profile(profile)
    if issues:
        raise RetrievalV2DiscoveryProfileError(f"invalid discovery profile: {issues}")
    output_path = profile_output_path(profile, profile_root)
    atomic_write_json(output_path, dict(profile))
    return output_path


def profile_summary(profile: Mapping[str, Any], *, path: Path | str | None = None) -> dict[str, Any]:
    return {
        "path": str(path if path is not None else profile.get("_path") or ""),
        "emperor_name": profile.get("emperor_name"),
        "item_code": profile.get("item_code"),
        "rule_code": profile.get("rule_code"),
        "object_seed_count": len(profile.get("object_seeds") or []),
        "source_document_count": len(profile.get("source_documents") or []),
        "profile_fingerprint": profile.get("profile_fingerprint"),
    }


def iter_profile_files(paths: Sequence[Path], roots: Sequence[Path]) -> list[Path]:
    result: list[Path] = []
    for path in paths:
        result.append(path)
    for root in roots:
        if root.is_file():
            result.append(root)
        elif root.exists():
            result.extend(sorted(path for path in root.rglob("*.json") if path.is_file()))
    deduped: dict[str, Path] = {}
    for path in result:
        deduped.setdefault(str(path.resolve()), path)
    return list(deduped.values())


def load_profiles(
    *,
    paths: Sequence[Path] = (),
    roots: Sequence[Path] = (),
    ignore_invalid_in_roots: bool = True,
) -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    explicit_paths = {str(path.resolve()) for path in paths}
    for path in iter_profile_files(paths, roots):
        try:
            payload = load_json(path)
        except Exception:
            if ignore_invalid_in_roots and str(path.resolve()) not in explicit_paths:
                continue
            raise
        issues = validate_profile(payload)
        if issues:
            if ignore_invalid_in_roots and str(path.resolve()) not in explicit_paths:
                continue
            raise RetrievalV2DiscoveryProfileError(f"invalid discovery profile {path}: {issues}")
        payload["_path"] = str(path)
        profiles.append(payload)
    return profiles


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage retrieval_v2 discovery profiles.")
    parser.add_argument("--from-task", type=Path, help="Build a discovery profile from a task JSON.")
    parser.add_argument("--output", type=Path, help="Write profile JSON to this path.")
    parser.add_argument("--profile-root", type=Path, help="Write profile under this root using a deterministic path.")
    parser.add_argument("--profile", type=Path, action="append", default=[], help="Profile JSON to inspect; repeatable.")
    parser.add_argument("--scan-root", type=Path, action="append", default=[], help="Profile root to scan; repeatable.")
    parser.add_argument("--recall-term-delta", type=Path, help="Read a recall term profile delta and build a preview.")
    parser.add_argument("--output-preview", type=Path, help="Write preview JSON without modifying the source profile.")
    parser.add_argument("--output-task-preview", type=Path, help="Write task preview JSON without modifying the source task.")
    parser.add_argument("--verbose", action="store_true", help="Print full profile JSON when writing from a task.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.recall_term_delta:
        if args.output_task_preview:
            if not args.from_task:
                raise RetrievalV2DiscoveryProfileError("--output-task-preview requires --from-task")
            preview = task_recall_delta_preview(load_json(args.from_task), load_json(args.recall_term_delta))
            atomic_write_json(args.output_task_preview, preview)
            sys.stdout.write(
                pretty_json(
                    {
                        "ok": True,
                        "output": str(args.output_task_preview),
                        "appended_rule_term_count": preview["preview_metadata"]["appended_rule_term_count"],
                        "conditional_term_not_injected_count": preview["preview_metadata"][
                            "conditional_term_not_injected_count"
                        ],
                        "writes_task": False,
                        "writes_profile": False,
                    }
                )
            )
            return 0
        if len(args.profile) != 1:
            raise RetrievalV2DiscoveryProfileError("--recall-term-delta requires exactly one --profile")
        profile = load_json(args.profile[0])
        issues = validate_profile(profile)
        if issues:
            raise RetrievalV2DiscoveryProfileError(f"invalid discovery profile {args.profile[0]}: {issues}")
        preview = profile_recall_delta_preview(profile, load_json(args.recall_term_delta))
        if args.output_preview:
            atomic_write_json(args.output_preview, preview)
            sys.stdout.write(
                pretty_json(
                    {
                        "ok": True,
                        "output": str(args.output_preview),
                        "appended_rule_term_count": preview["preview_metadata"]["appended_rule_term_count"],
                        "conditional_term_not_injected_count": preview["preview_metadata"][
                            "conditional_term_not_injected_count"
                        ],
                        "writes_profile": False,
                    }
                )
            )
        else:
            sys.stdout.write(pretty_json(preview))
        return 0
    if args.from_task:
        profile = profile_from_task(load_json(args.from_task))
        output_path: Path | None = None
        if args.profile_root:
            output_path = write_profile(profile, args.profile_root)
        if args.output:
            atomic_write_json(args.output, profile)
            output_path = args.output
        if output_path is None:
            sys.stdout.write(pretty_json(profile))
        else:
            payload: dict[str, Any] = {
                "ok": True,
                "output": str(output_path),
                "profile": profile_summary(profile, path=output_path),
            }
            if args.verbose:
                payload["full_profile"] = profile
            sys.stdout.write(pretty_json(payload))
        return 0
    profiles = load_profiles(paths=args.profile, roots=args.scan_root)
    sys.stdout.write(
        pretty_json(
            {
                "ok": True,
                "profile_count": len(profiles),
                "profiles": [profile_summary(profile) for profile in profiles],
            }
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    try:
        raise SystemExit(main())
    except RetrievalV2DiscoveryProfileError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
