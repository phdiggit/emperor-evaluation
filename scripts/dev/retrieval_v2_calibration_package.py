from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev import retrieval_v2_object_source_cache as object_source_cache  # noqa: E402
from scripts.dev import retrieval_v2_source_candidates as source_candidates  # noqa: E402
from scripts.dev.retrieval_v2_clean_runner import atomic_write_json  # noqa: E402


SCHEMA_VERSION = 1

PROFILE_HIGH_RISK_GRADES = {"sycophant", "major_sycophant", "historic_sycophant"}
PROFILE_IMPORTANT_GRADES = {"important_talent", "top_talent", "historic_talent"}
PROFILE_CORE_GRADES = {"top_talent", "historic_talent", "historic_sycophant"}

CLAIM_BUDGETS = {
    "ordinary_object": {"min": 1, "max": 2},
    "important_object": {"min": 3, "max": 5},
    "high_risk_object": {"min": 4, "max": 7},
    "core_political_object": {"min": 5, "max": 8},
}

SLOT_TERMS: dict[str, tuple[str, ...]] = {
    "entry_or_selection": (
        "荐",
        "薦",
        "举",
        "舉",
        "召",
        "征",
        "起",
        "拔",
        "擢",
        "用",
        "拜",
        "授",
        "任",
        "以为",
        "以爲",
    ),
    "role_or_authority": (
        "相",
        "丞相",
        "宰相",
        "参知政事",
        "參知政事",
        "大将军",
        "大將軍",
        "将军",
        "將軍",
        "都督",
        "总",
        "總",
        "统",
        "統",
        "督",
        "主",
        "掌",
        "权",
        "權",
    ),
    "action_or_task": (
        "命",
        "令",
        "遣",
        "使",
        "征",
        "讨",
        "討",
        "伐",
        "取",
        "守",
        "镇",
        "鎮",
        "平",
        "治",
        "谏",
        "諫",
        "上疏",
        "审",
        "審",
        "理",
        "抚",
        "撫",
    ),
    "outcome_or_feedback": (
        "功",
        "赏",
        "賞",
        "封",
        "赐",
        "賜",
        "迁",
        "遷",
        "克",
        "破",
        "定",
        "败",
        "敗",
        "罢",
        "罷",
        "贬",
        "貶",
        "诛",
        "誅",
        "杀",
        "殺",
        "伏诛",
        "伏誅",
        "坐",
        "罪",
    ),
    "risk_or_conflict": (
        "专擅",
        "專擅",
        "威福",
        "弄权",
        "弄權",
        "结党",
        "結黨",
        "朋党",
        "朋黨",
        "胡党",
        "胡黨",
        "蓝党",
        "藍黨",
        "坐党",
        "坐黨",
        "党诛",
        "黨誅",
        "谋反",
        "謀反",
        "构结祸乱",
        "搆結禍亂",
        "谗",
        "讒",
        "谮",
        "譖",
        "贪",
        "貪",
        "赃",
        "贓",
        "违法",
        "違法",
        "壅蔽",
        "伏诛",
        "伏誅",
    ),
    "institutional_effect": (
        "废丞相",
        "廢丞相",
        "罢中书",
        "罷中書",
        "中书",
        "中書",
        "改制",
        "更制",
        "制度",
        "法",
        "令",
        "官制",
        "胡党",
        "胡黨",
        "蓝党",
        "藍黨",
        "连坐",
        "連坐",
    ),
}


class CalibrationPackageError(RuntimeError):
    pass


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True, default=str) + "\n" for row in rows),
        encoding="utf-8",
    )


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CalibrationPackageError(f"{path} must contain a JSON object")
    return payload


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise CalibrationPackageError(f"{path}:{line_no}: expected JSON object")
        rows.append(payload)
    return rows


def compact(value: str, *, max_chars: int = 220) -> str:
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 1] + "…"


def object_name(seed: Mapping[str, Any]) -> str:
    return source_candidates.object_seed_name(seed)


def task_object_names(task: Mapping[str, Any]) -> list[str]:
    names: list[str] = []
    for seed in task.get("object_seeds") or []:
        if isinstance(seed, Mapping):
            name = object_name(seed)
            if name and name not in names:
                names.append(name)
    return names


def terms_in_text(text: str, terms: Sequence[str]) -> list[str]:
    return [term for term in terms if term and term in text]


def slots_for_slice(row: Mapping[str, Any]) -> dict[str, list[str]]:
    text = str(row.get("text") or "")
    return {
        slot: terms_in_text(text, terms)
        for slot, terms in SLOT_TERMS.items()
        if terms_in_text(text, terms)
    }


def load_profile_priors(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    priors: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(path):
        name = str(
            row.get("canonical_name")
            or row.get("person_name")
            or row.get("object_name")
            or row.get("name")
            or ""
        ).strip()
        if not name:
            continue
        priors[name] = {
            "person_name": name,
            "talent_grade": str(row.get("talent_grade") or row.get("profile_class") or "").strip(),
            "talent_quality_label": str(row.get("talent_quality_label") or "").strip(),
            "review_status": str(row.get("review_status") or "").strip(),
            "source": str(row.get("source") or row.get("generated_by") or "").strip(),
        }
    return priors


def cache_coverage_index(cache_root: Path | None) -> dict[str, dict[str, Any]]:
    if cache_root is None:
        return {}
    return {
        str(row.get("person_name") or ""): row
        for row in read_jsonl(cache_root / "person_coverage.jsonl")
        if row.get("person_name")
    }


def cache_document_index(cache_root: Path | None) -> dict[str, list[dict[str, Any]]]:
    if cache_root is None:
        return {}
    rows_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in read_jsonl(cache_root / "source_documents.jsonl"):
        name = str(row.get("person_name") or "").strip()
        if name:
            rows_by_name[name].append(row)
    return dict(rows_by_name)


def source_prior_for(name: str, coverage: Mapping[str, Any], documents: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    shapes = sorted({str(row.get("source_shape") or "") for row in documents if row.get("source_shape")})
    has_biography = bool(coverage.get("has_biography_source")) or any(
        shape in {
            "object_biography_candidate",
            "object_existing_source_candidate",
            "title_name_candidate",
            "object_biography_or_direct_mention_candidate",
        }
        for shape in shapes
    )
    return {
        "person_name": name,
        "has_source_document": bool(coverage.get("has_source_document")) or bool(documents),
        "has_biography_source": has_biography,
        "source_document_count": int(coverage.get("source_document_count") or len(documents)),
        "mention_slice_count": int(coverage.get("mention_slice_count") or sum(int(row.get("mention_slice_count") or 0) for row in documents)),
        "needs_agent_review": bool(coverage.get("needs_agent_review")),
        "agent_review_reason": str(coverage.get("agent_review_reason") or ""),
        "source_shapes": shapes or list(coverage.get("source_shapes") or []),
    }


def document_owner_index(task: Mapping[str, Any], cache_root: Path | None = None) -> dict[str, set[str]]:
    owners: dict[str, set[str]] = {}
    cache_owners_by_title: dict[str, set[str]] = defaultdict(set)
    if cache_root is not None:
        for row in read_jsonl(cache_root / "source_documents.jsonl"):
            person_name = str(row.get("person_name") or "").strip()
            title = str(row.get("wikisource_title") or row.get("source_title") or row.get("title") or "").strip()
            if person_name and title:
                cache_owners_by_title[title].add(person_name)
    for index, raw_doc in enumerate(task.get("source_documents") or task.get("documents") or [], start=1):
        if not isinstance(raw_doc, Mapping):
            continue
        code = source_candidates.document_code(raw_doc, index)
        title = str(raw_doc.get("wikisource_title") or raw_doc.get("title") or "").strip()
        if title and cache_owners_by_title.get(title):
            owners.setdefault(code, set()).update(cache_owners_by_title[title])
        cache_payload = raw_doc.get("object_source_cache")
        if not isinstance(cache_payload, Mapping):
            continue
        person_name = str(cache_payload.get("person_name") or "").strip()
        if person_name:
            owners.setdefault(code, set()).add(person_name)
    return owners


def budget_class_for(
    *,
    profile_prior: Mapping[str, Any],
    source_prior: Mapping[str, Any],
    slot_hits: Mapping[str, Sequence[str]],
    slice_count: int,
) -> str:
    grade = str(profile_prior.get("talent_grade") or "")
    has_profile_prior = bool(grade)
    has_source_prior = bool(source_prior.get("has_source_document"))
    has_risk = bool(slot_hits.get("risk_or_conflict"))
    has_institutional = bool(slot_hits.get("institutional_effect"))
    slot_count = len([slot for slot, hits in slot_hits.items() if hits])
    if grade in PROFILE_CORE_GRADES:
        return "core_political_object"
    if grade in PROFILE_HIGH_RISK_GRADES or (
        has_source_prior and has_risk and (slot_hits.get("outcome_or_feedback") or has_institutional)
    ):
        return "high_risk_object"
    if grade in PROFILE_IMPORTANT_GRADES:
        return "important_object"
    if not has_source_prior and not has_profile_prior:
        return "important_object" if slice_count >= 5 and slot_count >= 3 else "ordinary_object"
    if bool(source_prior.get("has_biography_source")) and slot_count >= 5 and slice_count >= 12:
        return "core_political_object"
    if slot_count >= 3 or bool(source_prior.get("has_biography_source")) and slice_count >= 3:
        return "important_object"
    return "ordinary_object"


def required_slots_for(budget_class: str, slot_hits: Mapping[str, Sequence[str]]) -> list[str]:
    if budget_class == "ordinary_object":
        return []
    if budget_class == "important_object":
        return ["role_or_authority", "action_or_task", "outcome_or_feedback"]
    if budget_class == "high_risk_object":
        return ["role_or_authority", "risk_or_conflict", "outcome_or_feedback"]
    if budget_class == "core_political_object":
        required = ["entry_or_selection", "role_or_authority", "action_or_task", "outcome_or_feedback"]
        if slot_hits.get("risk_or_conflict"):
            required.append("risk_or_conflict")
        return required
    return []


def suggested_action(
    *,
    source_prior: Mapping[str, Any],
    slice_count: int,
    owned_slice_count: int,
    missing_slots: Sequence[str],
    budget_class: str,
    claim_budget: Mapping[str, int],
) -> str:
    if not source_prior.get("has_source_document"):
        return "warm_object_source_cache"
    if source_prior.get("needs_agent_review"):
        return "review_object_source_cache_identity"
    if owned_slice_count == 0:
        return "ensure_object_owned_source_enters_candidates"
    if slice_count == 0:
        return "add_alias_or_source_hint_before_judge"
    if budget_class == "high_risk_object" and ("risk_or_conflict" in missing_slots or "outcome_or_feedback" in missing_slots):
        return "require_risk_and_feedback_windows_before_sample_judge"
    if missing_slots:
        return "improve_slot_coverage_before_sample_judge"
    if slice_count < int(claim_budget.get("min") or 0):
        return "raise_candidate_slice_budget_or_add_dense_source"
    return "sample_judge_ready"


def profile_signal_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "signal_code": "OPS-" + source_candidates.stable_fingerprint(
            [row.get("object_name"), row.get("object_budget_class"), row.get("slot_hits")]
        )[:16].upper(),
        "signal_type": "object_political_sufficiency",
        "object_name": row.get("object_name"),
        "profile_prior": row.get("profile_prior"),
        "source_prior": row.get("source_prior"),
        "object_budget_class_candidate": row.get("object_budget_class"),
        "claim_budget": row.get("claim_budget"),
        "candidate_slice_count": row.get("candidate_slice_count"),
        "owned_candidate_slice_count": row.get("owned_candidate_slice_count"),
        "analysis_slice_count": row.get("analysis_slice_count"),
        "slot_hits": row.get("slot_hits"),
        "missing_slots": row.get("missing_slots"),
        "suggested_action": row.get("suggested_action"),
        "review_status": "candidate",
        "write_db": False,
    }


def build_object_rows(
    *,
    task: Mapping[str, Any],
    candidates: Mapping[str, Any],
    cache_root: Path | None,
    profile_priors: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    coverage_index = cache_coverage_index(cache_root)
    documents_index = cache_document_index(cache_root)
    owner_by_document = document_owner_index(task, cache_root=cache_root)
    slices_by_object: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in candidates.get("candidate_slices") or []:
        if isinstance(row, Mapping):
            slices_by_object[str(row.get("object_name") or "")].append(row)

    rows: list[dict[str, Any]] = []
    for name in task_object_names(task):
        object_slices = sorted(
            slices_by_object.get(name, []),
            key=lambda row: (-int(row.get("score") or 0), str(row.get("document_code") or "")),
        )
        owned_slices = [
            row
            for row in object_slices
            if name in owner_by_document.get(str(row.get("document_code") or ""), set())
        ]
        analysis_slices = owned_slices or object_slices
        slot_terms: dict[str, list[str]] = {slot: [] for slot in SLOT_TERMS}
        for row in analysis_slices:
            for slot, terms in slots_for_slice(row).items():
                for term in terms:
                    if term not in slot_terms[slot]:
                        slot_terms[slot].append(term)
        slot_hits = {slot: terms for slot, terms in slot_terms.items() if terms}
        profile_prior = dict(profile_priors.get(name) or {})
        source_prior = source_prior_for(
            name,
            coverage_index.get(name) or {},
            documents_index.get(name) or [],
        )
        budget_class = budget_class_for(
            profile_prior=profile_prior,
            source_prior=source_prior,
            slot_hits=slot_hits,
            slice_count=len(analysis_slices),
        )
        claim_budget = CLAIM_BUDGETS[budget_class]
        required_slots = required_slots_for(budget_class, slot_hits)
        missing_slots = [slot for slot in required_slots if not slot_hits.get(slot)]
        top_windows = [
            {
                "slice_code": row.get("slice_code"),
                "document_code": row.get("document_code"),
                "score": row.get("score"),
                "slots": sorted(slots_for_slice(row)),
                "matched_rule_terms": row.get("matched_rule_terms") or [],
                "matched_outcome_terms": row.get("matched_outcome_terms") or [],
                "text_preview": compact(str(row.get("text") or "")),
            }
            for row in analysis_slices[:3]
        ]
        row = {
            "object_name": name,
            "object_budget_class": budget_class,
            "claim_budget": claim_budget,
            "profile_prior": profile_prior,
            "source_prior": source_prior,
            "candidate_slice_count": len(object_slices),
            "owned_candidate_slice_count": len(owned_slices),
            "analysis_slice_count": len(analysis_slices),
            "slot_hits": slot_hits,
            "slot_hit_count": len(slot_hits),
            "required_slots": required_slots,
            "missing_slots": missing_slots,
            "top_windows": top_windows,
        }
        row["suggested_action"] = suggested_action(
            source_prior=source_prior,
            slice_count=len(analysis_slices),
            owned_slice_count=len(owned_slices),
            missing_slots=missing_slots,
            budget_class=budget_class,
            claim_budget=claim_budget,
        )
        rows.append(row)
    return rows


def build_summary(
    *,
    task: Mapping[str, Any],
    overlay_stats: Mapping[str, Any] | None,
    candidates: Mapping[str, Any],
    object_rows: Sequence[Mapping[str, Any]],
    elapsed_seconds: float,
) -> dict[str, Any]:
    class_counts = Counter(str(row.get("object_budget_class") or "") for row in object_rows)
    action_counts = Counter(str(row.get("suggested_action") or "") for row in object_rows)
    missing_slot_counts: Counter[str] = Counter()
    for row in object_rows:
        missing_slot_counts.update(str(slot) for slot in row.get("missing_slots") or [])
    ready_rows = [row for row in object_rows if row.get("suggested_action") == "sample_judge_ready"]
    high_impact_rows = [
        row
        for row in object_rows
        if row.get("object_budget_class") in {"high_risk_object", "core_political_object"}
    ]
    return {
        "generated_by": "scripts/dev/retrieval_v2_calibration_package.py",
        "schema_version": SCHEMA_VERSION,
        "mode": "candidate_only_calibration",
        "write_db": False,
        "agent_invoked": False,
        "full_judge_invoked": False,
        "task_identity": {
            key: task.get(key)
            for key in ("job_code", "target_code", "emperor_name", "item_code", "rule_code", "capture_profile")
            if task.get(key)
        },
        "overlay_stats": dict(overlay_stats or {}),
        "candidate_stats": dict(candidates.get("stats") or {}),
        "coverage": dict(candidates.get("coverage") or {}),
        "totals": {
            "objects": len(object_rows),
            "sample_judge_ready_objects": len(ready_rows),
            "high_impact_objects": len(high_impact_rows),
            "objects_with_missing_slots": sum(1 for row in object_rows if row.get("missing_slots")),
            "objects_without_slices": len((candidates.get("coverage") or {}).get("objects_without_slices") or []),
            "candidate_slices": len(candidates.get("candidate_slices") or []),
            "source_documents": len(candidates.get("source_documents") or []),
            "elapsed_seconds": elapsed_seconds,
        },
        "object_budget_class_counts": dict(sorted(class_counts.items())),
        "suggested_action_counts": dict(sorted(action_counts.items())),
        "missing_slot_counts": dict(sorted(missing_slot_counts.items())),
    }


def render_markdown(summary: Mapping[str, Any], object_rows: Sequence[Mapping[str, Any]]) -> str:
    totals = summary.get("totals") or {}
    lines = [
        "# retrieval_v2 calibration package",
        "",
        f"- mode: `{summary.get('mode')}`",
        f"- emperor: `{(summary.get('task_identity') or {}).get('emperor_name', '')}`",
        f"- objects: `{totals.get('objects', 0)}`",
        f"- candidate_slices: `{totals.get('candidate_slices', 0)}`",
        f"- sample_judge_ready_objects: `{totals.get('sample_judge_ready_objects', 0)}`",
        f"- objects_with_missing_slots: `{totals.get('objects_with_missing_slots', 0)}`",
        f"- full_judge_invoked: `{summary.get('full_judge_invoked')}`",
        "",
        "## Object Budget",
        "",
        "| object | class | budget | slices | owned | slots | missing | action |",
        "| --- | --- | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in object_rows:
        budget = row.get("claim_budget") or {}
        lines.append(
            "| {object} | {klass} | {min}-{max} | {slices} | {owned} | {slots} | {missing} | {action} |".format(
                object=row.get("object_name") or "",
                klass=row.get("object_budget_class") or "",
                min=budget.get("min", ""),
                max=budget.get("max", ""),
                slices=row.get("candidate_slice_count", 0),
                owned=row.get("owned_candidate_slice_count", 0),
                slots=", ".join(row.get("slot_hits") or {}),
                missing=", ".join(row.get("missing_slots") or []),
                action=row.get("suggested_action") or "",
            )
        )
    lines.append("")
    lines.append("## High Impact Top Windows")
    lines.append("")
    for row in object_rows:
        if row.get("object_budget_class") not in {"high_risk_object", "core_political_object"}:
            continue
        lines.append(f"### {row.get('object_name')}")
        for window in row.get("top_windows") or []:
            lines.append(
                "- `{code}` score={score} slots={slots}: {text}".format(
                    code=window.get("slice_code") or "",
                    score=window.get("score") or 0,
                    slots=",".join(window.get("slots") or []),
                    text=window.get("text_preview") or "",
                )
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_calibration_package(
    *,
    task: Mapping[str, Any],
    output_root: Path,
    object_source_cache_root: Path | None,
    source_cache_root: Path,
    profile_priors_path: Path | None = None,
    context_chars: int = 260,
    max_slices_per_object: int = 12,
    candidate_timeout: int = 15,
    skip_fetch_errors: bool = True,
) -> dict[str, Any]:
    started = time.perf_counter()
    output_root.mkdir(parents=True, exist_ok=True)
    current_task = json.loads(stable_json(task))
    overlay_stats: dict[str, Any] | None = None
    if object_source_cache_root is not None:
        current_task, overlay_stats = object_source_cache.overlay_task_from_cache(
            current_task,
            cache_root=object_source_cache_root,
        )
    atomic_write_json(output_root / "task.overlaid.json", current_task)
    candidates = source_candidates.build_candidates(
        current_task,
        cache_dir=source_cache_root,
        timeout=candidate_timeout,
        context_chars=context_chars,
        max_slices_per_object=max_slices_per_object,
        skip_fetch_errors=skip_fetch_errors,
    )
    atomic_write_json(output_root / "candidates.candidate_only.json", candidates)
    profile_priors = load_profile_priors(profile_priors_path)
    object_rows = build_object_rows(
        task=current_task,
        candidates=candidates,
        cache_root=object_source_cache_root,
        profile_priors=profile_priors,
    )
    write_jsonl(output_root / "object_budget_candidates.jsonl", object_rows)
    signal_rows = [profile_signal_row(row) for row in object_rows]
    write_jsonl(output_root / "profile_signal_events.jsonl", signal_rows)
    elapsed = round(time.perf_counter() - started, 3)
    summary = build_summary(
        task=current_task,
        overlay_stats=overlay_stats,
        candidates=candidates,
        object_rows=object_rows,
        elapsed_seconds=elapsed,
    )
    atomic_write_json(output_root / "calibration_summary.json", summary)
    (output_root / "calibration_summary.md").write_text(render_markdown(summary, object_rows), encoding="utf-8")
    return {
        "summary": summary,
        "object_rows": object_rows,
        "output_root": str(output_root),
        "files": {
            "task": str(output_root / "task.overlaid.json"),
            "candidates": str(output_root / "candidates.candidate_only.json"),
            "object_budget_candidates": str(output_root / "object_budget_candidates.jsonl"),
            "profile_signal_events": str(output_root / "profile_signal_events.jsonl"),
            "summary_json": str(output_root / "calibration_summary.json"),
            "summary_md": str(output_root / "calibration_summary.md"),
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build candidate-only retrieval_v2 calibration package.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="Run object cache overlay and candidate-only object sufficiency audit.")
    build.add_argument("--task", type=Path, required=True)
    build.add_argument("--output-root", type=Path, required=True)
    build.add_argument("--object-source-cache-root", type=Path)
    build.add_argument("--source-cache-root", type=Path, default=source_candidates.DEFAULT_CACHE_DIR)
    build.add_argument("--profile-priors", type=Path)
    build.add_argument("--context-chars", type=int, default=260)
    build.add_argument("--max-slices-per-object", type=int, default=12)
    build.add_argument("--candidate-timeout", type=int, default=15)
    build.add_argument("--no-skip-fetch-errors", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "build":
        result = build_calibration_package(
            task=read_json(args.task),
            output_root=args.output_root,
            object_source_cache_root=args.object_source_cache_root,
            source_cache_root=args.source_cache_root,
            profile_priors_path=args.profile_priors,
            context_chars=args.context_chars,
            max_slices_per_object=args.max_slices_per_object,
            candidate_timeout=args.candidate_timeout,
            skip_fetch_errors=not args.no_skip_fetch_errors,
        )
        print(json.dumps({"ok": True, **result["files"], "totals": result["summary"]["totals"]}, ensure_ascii=False))
        return 0
    raise CalibrationPackageError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
