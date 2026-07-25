from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
from time import monotonic
from typing import Any, Mapping, Protocol, Sequence
from uuid import uuid4

from emperor_v4.adapters.claim_extraction_profile import load_claim_extraction_profile
from emperor_v4.adapters.claim_extractor_codex import CodexCliClaimExtractionProvider
from emperor_v4.adapters.source_cache_discovery import (
    DiscoverySourceMaterialProvider,
    wikisource_title_candidates,
)
from emperor_v4.adapters.source_text_index import LocalSourceTextIndex
from emperor_v4.application.claim_extractor_service import ensure_claim_extraction
from emperor_v4.application.discovery_source_backfill import (
    build_ready_person_worklists,
    write_ready_person_worklists,
)
from emperor_v4.application.source_cache_service import ensure_source_cache
from emperor_v4.contracts.extraction import ClaimExtractionRequest
from emperor_v4.contracts.source import SourceCacheRequest, SourceCacheSubject
from emperor_v4.persistence.claim_extractor import ShadowJsonClaimExtractionRepository
from emperor_v4.persistence.source_cache import ShadowJsonSourceCacheRepository


PIPELINE_SCHEMA_VERSION = "person-rebuild-shadow-v1"
CLAIM_PROFILE_CODE = "person_rebuild_atomic_v1"
SOURCE_POLICY_VERSION = "person-rebuild-discovery-source-v23"
CLAIM_SELECTION_VERSION = "person-rebuild-claim-selection-v3"
_DISPUTED_OR_EXCULPATORY_TERMS = (
    "譖",
    "谮",
    "讒",
    "谗",
    "誣",
    "诬",
    "無狀",
    "无状",
    "意已悟",
    "勿以為懷",
    "勿以为怀",
)
_NON_EPISODE_ASSERTION_TYPES = {"historiographical_evaluation"}
_DISPUTED_POLARITIES = {"disputed", "negated"}
_TALENT_ACHIEVEMENT_RESPONSIBILITY_FAMILIES = {
    "军事行动",
    "军事谋划",
    "军事任用",
}


class ClaimProvider(Protocol):
    def extract(self, request_payload: Mapping[str, Any]): ...


def _stable(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _hash(value: Any) -> str:
    return sha256(_stable(value).encode("utf-8")).hexdigest()


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> bool:
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if path.is_file() and path.read_bytes() == encoded:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_bytes(encoded)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return True


def dispatch_ready_people(results_dir: Path, ready_dir: Path) -> dict[str, Any]:
    payloads = build_ready_person_worklists(tuple(results_dir.glob("*.json")))
    changes = write_ready_person_worklists(ready_dir, payloads)
    return {
        "stage": "dispatch",
        "ready_people": len(payloads),
        "changed_people": sum(changes.values()),
        "waiting_artifacts": len(tuple(results_dir.glob("*.json"))),
    }


def _worklist_identity(worklist: Mapping[str, Any]) -> tuple[str, str, str]:
    tasks = tuple(worklist.get("tasks") or ())
    if not tasks:
        raise ValueError("person worklist 缺少 tasks")
    people = {(str(row["subject_ref"]), str(row["subject_name"])) for row in tasks}
    if len(people) != 1:
        raise ValueError("person worklist 必须只包含一个人物")
    person_ref, person_name = next(iter(people))
    captured = max(str(row["discovery_captured_at"]) for row in tasks)
    return person_ref, person_name, captured


def _compact_source_batches(
    worklist: Mapping[str, Any],
    *,
    max_source_documents: int | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Merge same-document leads and keep the first-pass source set minimal."""
    if max_source_documents is not None and max_source_documents <= 0:
        raise ValueError("每人首轮回源文献数必须为正数")
    grouped: dict[str, dict[str, Any]] = {}
    for raw in worklist.get("source_batches") or ():
        batch = dict(raw)
        candidates = wikisource_title_candidates(batch)
        key = candidates[0] if candidates else str(batch.get("source_url") or "")
        merged = grouped.setdefault(key, {**batch, "leads": []})
        for field in ("source_works", "requested_sections", "lead_refs", "projection_targets"):
            merged[field] = list(
                dict.fromkeys(
                    [*(merged.get(field) or ()), *(batch.get(field) or ())]
                )
            )
        merged["leads"] = list(
            {
                str(lead.get("lead_ref") or index): lead
                for index, lead in enumerate(
                    [*(merged.get("leads") or ()), *(batch.get("leads") or ())]
                )
            }.values()
        )
        if "wikisource.org" in str(batch.get("source_url") or ""):
            merged["source_url"] = batch["source_url"]

    def priority(batch: Mapping[str, Any]) -> tuple[int, int, int, str]:
        works = " ".join(str(item) for item in batch.get("source_works") or ())
        official_history = any(
            marker in works for marker in ("旧唐书", "新唐书", "资治通鉴", "宋史", "明史")
        )
        has_risk = any(
            str(lead.get("lead_type") or "") == "risk"
            for lead in batch.get("leads") or ()
        )
        return (
            0 if official_history else 1,
            0 if has_risk else 1,
            -len(batch.get("leads") or ()),
            str(batch.get("source_batch_code") or ""),
        )

    ordered = sorted(grouped.values(), key=priority)
    if max_source_documents is None:
        return ordered, []
    return ordered[:max_source_documents], ordered[max_source_documents:]


def backfill_person_worklist(
    worklist_path: Path,
    *,
    state_dir: Path,
    output_dir: Path,
    service_release_sha: str,
    fetch: Any | None = None,
    max_source_documents: int | None = None,
    local_source_index_path: Path | None = None,
) -> dict[str, Any]:
    worklist = json.loads(worklist_path.read_text(encoding="utf-8"))
    person_ref, person_name, captured_at = _worklist_identity(worklist)
    source_batches, deferred_source_batches = _compact_source_batches(
        worklist,
        max_source_documents=max_source_documents,
    )
    selected_worklist = {**worklist, "source_batches": source_batches}
    local_index = (
        LocalSourceTextIndex(local_source_index_path)
        if local_source_index_path is not None
        else None
    )
    input_fingerprint = _hash(
        {
            "worklist": selected_worklist,
            "local_source_index_identity": local_index.identity if local_index else None,
        }
    )
    source_hints = tuple(
        dict.fromkeys(
            title
            for batch in selected_worklist.get("source_batches") or ()
            for title in wikisource_title_candidates(batch)
        )
    )
    request = SourceCacheRequest(
        request_id=f"SRC-{input_fingerprint[:20].upper()}",
        idempotency_key=(
            f"person-rebuild-source:{SOURCE_POLICY_VERSION}:"
            f"{person_ref}:{input_fingerprint}"
        ),
        subject=SourceCacheSubject(person_ref, person_name, ()),
        evaluation_context={
            "mode": "person_rebuild_shadow",
            "worklist_fingerprint": input_fingerprint,
            "local_source_index_identity": local_index.identity if local_index else None,
        },
        source_hints=source_hints,
        required_source_families=("official_history",),
        mode="ensure",
        source_policy_version=SOURCE_POLICY_VERSION,
        requested_at=captured_at,
    )
    provider_options = {"fetch": fetch} if fetch is not None else {}
    run = ensure_source_cache(
        request,
        provider=DiscoverySourceMaterialProvider(
            worklist=selected_worklist,
            local_index=local_index,
            **provider_options,
        ),
        repository=ShadowJsonSourceCacheRepository(
            state_dir / f"{worklist_path.stem}.json"
        ),
        service_release_sha=service_release_sha,
    )
    resolved_omission_tasks = {
        str(reason).removeprefix("discovery_omission:")
        for passage in run.response.get("passages") or ()
        for reason in passage.get("selection_reason") or ()
        if str(reason).startswith("discovery_omission:")
    }
    discovery_omissions = [
        {
            **row,
            "source_backfill_status": (
                "resolved_source_passage"
                if str(row.get("discovery_task_code")) in resolved_omission_tasks
                else "unresolved"
            ),
        }
        for row in worklist.get("discovery_omissions") or ()
    ]
    report = {
        "schema_version": PIPELINE_SCHEMA_VERSION,
        "stage": "source_backfill",
        "person_ref": person_ref,
        "person_name": person_name,
        "worklist_fingerprint": input_fingerprint,
        "source_policy_version": SOURCE_POLICY_VERSION,
        "source_selection": {
            "max_source_documents": max_source_documents,
            "selected_source_batch_codes": [
                str(batch.get("source_batch_code") or "")
                for batch in source_batches
            ],
            "deferred_source_batch_codes": [
                str(batch.get("source_batch_code") or "")
                for batch in deferred_source_batches
            ],
        },
        "discovery_unresolved_locators": list(
            worklist.get("unresolved_locators") or ()
        ),
        "discovery_omissions": discovery_omissions,
        "request": asdict(request),
        "response": run.response,
        "runtime_audit": {
            "cache_hit": run.cache_hit,
            "provider_call_count": run.provider_call_count,
            "network_request_count": run.network_request_count,
            "state_write_count": run.repository_write_count,
            "database_write_count": 0,
            "model_call_count": 0,
        },
    }
    _atomic_json(output_dir / f"{worklist_path.stem}.json", report)
    return report


def run_backfill_once(
    ready_dir: Path,
    *,
    state_dir: Path,
    output_dir: Path,
    service_release_sha: str,
) -> dict[str, Any]:
    for path in sorted(ready_dir.glob("*.json")):
        output = output_dir / path.name
        if output.is_file():
            existing = json.loads(output.read_text(encoding="utf-8"))
            worklist = json.loads(path.read_text(encoding="utf-8"))
            if (
                existing.get("worklist_fingerprint") == _hash(worklist)
                and existing.get("source_policy_version")
                == SOURCE_POLICY_VERSION
            ):
                continue
        return backfill_person_worklist(
            path,
            state_dir=state_dir,
            output_dir=output_dir,
            service_release_sha=service_release_sha,
        )
    return {"stage": "source_backfill", "status": "idle"}


def backfill_ready_people(
    ready_dir: Path,
    *,
    state_dir: Path,
    output_dir: Path,
    service_release_sha: str,
    max_workers: int,
    max_source_documents: int | None = None,
) -> dict[str, Any]:
    """Backfill every ready person concurrently; the cache keeps replays zero-network."""
    if max_workers <= 0:
        raise ValueError("source backfill 并发必须为正数")
    paths = sorted(ready_dir.glob("*.json"))
    completed: list[str] = []
    unchanged: list[str] = []
    failed: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        active = {
            executor.submit(
                backfill_person_worklist,
                path,
                state_dir=state_dir,
                output_dir=output_dir,
                service_release_sha=service_release_sha,
                max_source_documents=max_source_documents,
            ): path
            for path in paths
        }
        for future, path in active.items():
            try:
                report = future.result()
            except Exception as exc:  # noqa: BLE001 - batch must continue per person
                failed[path.name] = str(exc)
                continue
            target = unchanged if report["runtime_audit"]["cache_hit"] else completed
            target.append(path.name)
    return {
        "stage": "source_backfill_batch",
        "completed": completed,
        "unchanged": unchanged,
        "failed": failed,
        "max_workers": max_workers,
        "max_source_documents": max_source_documents,
        "formal_writes": 0,
    }


def backfill_i5b_worklist(
    worklist_path: Path,
    *,
    state_dir: Path,
    output_dir: Path,
    service_release_sha: str,
    max_workers: int,
    local_source_index_path: Path | None = None,
) -> dict[str, Any]:
    """Run one I5B discovery worklist through Source Cache, per subject only.

    The input is already lead-limited for civil officials and intentionally
    uncapped for the ruler-policy subject.  This stage does no Claim extraction.
    """
    if max_workers <= 0:
        raise ValueError("I5B source backfill 并发必须为正数")
    worklist = json.loads(worklist_path.read_text(encoding="utf-8"))
    selection = worklist.get("i5b_selection") or {}
    ruler_ref = str(selection.get("ruler_ref") or "")
    if not ruler_ref:
        raise ValueError("I5B worklist 缺少 i5b_selection.ruler_ref")
    by_subject: dict[tuple[str, str], dict[str, Any]] = {}
    for task in worklist.get("tasks") or ():
        key = (str(task["subject_ref"]), str(task["subject_name"]))
        row = by_subject.setdefault(key, {**worklist, "tasks": [], "source_batches": []})
        row["tasks"].append(task)
    for batch in worklist.get("source_batches") or ():
        key = (str(batch["subject_ref"]), str(batch["subject_name"]))
        if key in by_subject:
            by_subject[key]["source_batches"].append(batch)
    input_dir = state_dir / "i5b-worklists"
    input_dir.mkdir(parents=True, exist_ok=True)
    materialized: list[Path] = []
    for (subject_ref, _), payload in sorted(by_subject.items()):
        code = "I5BSRC-" + _hash([ruler_ref, subject_ref])[:16].upper()
        path = input_dir / f"{code}.json"
        _atomic_json(path, payload)
        materialized.append(path)
    reports: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        active = {
            executor.submit(
                backfill_person_worklist,
                path,
                state_dir=state_dir,
                output_dir=output_dir,
                service_release_sha=service_release_sha,
                max_source_documents=None,
                local_source_index_path=local_source_index_path,
            ): path
            for path in materialized
        }
        for future, path in active.items():
            reports[path.stem] = future.result()
    return {
        "stage": "i5b_source_backfill",
        "ruler_ref": ruler_ref,
        "subject_count": len(reports),
        "reports": reports,
        "formal_writes": 0,
        "database_writes": 0,
        "model_calls": 0,
    }


def claim_person_sources(
    source_report_path: Path,
    *,
    profiles_path: Path,
    state_dir: Path,
    output_dir: Path,
    provider: ClaimProvider,
    service_release_sha: str,
    deadline_at: float | None = None,
) -> dict[str, Any]:
    source_report = json.loads(source_report_path.read_text(encoding="utf-8"))
    response = source_report.get("response") or {}
    selected_passages = _deduplicate_passages(
        tuple(response.get("passages") or ())
    )
    if not selected_passages:
        raise ValueError("人物回源没有可供 Claim Extractor 使用的 passages")
    passage_projection_map = {
        passage_ref: sorted(targets)
        for passage_ref, targets in _passage_projection_map(
            selected_passages
        ).items()
    }
    passages = tuple(
        {
            "passage_id": str(row["passage_id"]),
            "raw_text": str(row["raw_text"]),
            "context_before": str(row.get("context_before") or ""),
            "context_after": str(row.get("context_after") or ""),
        }
        for row in selected_passages
    )
    person_ref = str(source_report["person_ref"])
    person_name = str(source_report["person_name"])
    source_output_fingerprint = str(response["output_fingerprint"])
    source_fingerprint = _hash(
        {
            "selection_version": CLAIM_SELECTION_VERSION,
            "passages": passages,
        }
    )
    profile = load_claim_extraction_profile(profiles_path, CLAIM_PROFILE_CODE)
    profile_fingerprint = _hash(asdict(profile))
    provider_policy_fingerprint = str(
        getattr(provider, "policy_fingerprint", "unversioned-provider")
    )
    output_path = output_dir / f"{source_report_path.stem}.json"
    if output_path.is_file():
        existing = json.loads(output_path.read_text(encoding="utf-8"))
        existing_provenance = (existing.get("response") or {}).get("provenance") or {}
        if (
            existing.get("source_output_fingerprint") == source_fingerprint
            and existing.get("claim_selection_version") == CLAIM_SELECTION_VERSION
            and existing.get("claim_profile_fingerprint")
            == profile_fingerprint
            and existing_provenance.get("provider_policy_fingerprint")
            == provider_policy_fingerprint
        ):
            replay = dict(existing)
            replay["runtime_audit"] = {
                "cache_hit": True,
                "provider_call_count": 0,
                "model_call_count": 0,
                "state_write_count": 0,
                "database_write_count": 0,
                "formal_assertion_write_count": 0,
            }
            return replay
    claim_identity = _hash(
        {
            "source_fingerprint": source_fingerprint,
            "profile_fingerprint": profile_fingerprint,
            "provider_policy_fingerprint": provider_policy_fingerprint,
        }
    )
    request = ClaimExtractionRequest(
        request_id=f"CLM-{claim_identity[:20].upper()}",
        idempotency_key=f"person-rebuild-claim:{person_ref}:{claim_identity}",
        profile_code=CLAIM_PROFILE_CODE,
        subject={
            "person_ref": person_ref,
            "person_or_ruler_ref": person_ref,
            "person_name": person_name,
            "evaluation_context": person_ref,
        },
        passages=passages,
        requested_at=str(source_report["request"]["requested_at"]),
    )
    run = ensure_claim_extraction(
        request,
        profile=profile,
        provider=provider,
        repository=ShadowJsonClaimExtractionRepository(
            state_dir / f"{source_report_path.stem}.json"
        ),
        service_release_sha=service_release_sha,
    )
    report = {
        "schema_version": PIPELINE_SCHEMA_VERSION,
        "stage": "claim_extraction",
        "person_ref": person_ref,
        "person_name": person_name,
        "source_output_fingerprint": source_fingerprint,
        "source_cache_output_fingerprint": source_output_fingerprint,
        "claim_selection_version": CLAIM_SELECTION_VERSION,
        "claim_profile_fingerprint": profile_fingerprint,
        "provider_policy_fingerprint": provider_policy_fingerprint,
        "passage_projection_map": passage_projection_map,
        "request": asdict(request),
        "response": run.response,
        "runtime_audit": {
            "cache_hit": run.cache_hit,
            "provider_call_count": run.provider_call_count,
            "model_call_count": run.model_call_count,
            "state_write_count": run.repository_write_count,
            "database_write_count": 0,
            "formal_assertion_write_count": 0,
        },
    }
    if deadline_at is not None and monotonic() >= deadline_at:
        report["stage"] = "claim_extraction_discarded_after_deadline"
        report["discarded_after_deadline"] = True
        return report
    _atomic_json(output_path, report)
    return report


def claim_ready_sources(
    source_report_dir: Path,
    *,
    profiles_path: Path,
    state_dir: Path,
    output_dir: Path,
    provider_factory: Any,
    service_release_sha: str,
    max_workers: int,
    deadline_seconds: int,
    max_attempts_per_source: int = 2,
) -> dict[str, Any]:
    if max_workers <= 0 or deadline_seconds <= 0 or max_attempts_per_source <= 0:
        raise ValueError("claim batch 并发和截止时间及尝试次数必须为正数")
    paths = iter(sorted(source_report_dir.glob("*.json")))
    deadline_at = monotonic() + deadline_seconds
    completed = []
    discarded = []
    failed: dict[str, str] = {}
    attempts: dict[str, int] = {}

    def submit_one(executor: ThreadPoolExecutor, path: Path):
        attempts[path.name] = attempts.get(path.name, 0) + 1
        remaining_seconds = max(1, int(deadline_at - monotonic()))
        return executor.submit(
            claim_person_sources,
            path,
            profiles_path=profiles_path,
            state_dir=state_dir,
            output_dir=output_dir,
            provider=provider_factory(remaining_seconds),
            service_release_sha=service_release_sha,
            deadline_at=deadline_at,
        )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        active = {}
        while len(active) < max_workers and monotonic() < deadline_at:
            try:
                path = next(paths)
            except StopIteration:
                break
            active[submit_one(executor, path)] = path
        while active:
            remaining = deadline_at - monotonic()
            done, _pending = wait(
                active,
                timeout=max(0.0, remaining),
                return_when=FIRST_COMPLETED,
            )
            if not done:
                done = set(active)
            for future in done:
                path = active.pop(future)
                try:
                    report = future.result()
                except Exception as exc:  # noqa: BLE001 - one Claim cannot stop the batch
                    if (
                        attempts[path.name] < max_attempts_per_source
                        and monotonic() < deadline_at
                    ):
                        active[submit_one(executor, path)] = path
                    else:
                        failed[path.name] = str(exc)
                    continue
                target = discarded if report.get("discarded_after_deadline") else completed
                target.append(path.name)
                if monotonic() < deadline_at:
                    try:
                        next_path = next(paths)
                    except StopIteration:
                        continue
                    active[submit_one(executor, next_path)] = next_path
    not_started = [path.name for path in paths]
    return {
        "stage": "claim_batch",
        "completed": completed,
        "discarded_after_deadline": discarded,
        "failed": failed,
        "attempts": attempts,
        "not_started": not_started,
        "max_workers": max_workers,
        "deadline_seconds": deadline_seconds,
    }


def _deduplicate_passages(
    passages: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    grouped: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for passage in passages:
        key = (
            str(passage.get("document_id") or ""),
            str(passage.get("raw_text") or ""),
            str(passage.get("context_before") or ""),
            str(passage.get("context_after") or ""),
        )
        existing = grouped.get(key)
        if existing is None:
            grouped[key] = dict(passage)
            continue
        existing["selection_reason"] = list(
            dict.fromkeys(
                [
                    *(existing.get("selection_reason") or ()),
                    *(passage.get("selection_reason") or ()),
                ]
            )
        )
        existing["linked_passages"] = list(
            dict.fromkeys(
                [
                    *(existing.get("linked_passages") or ()),
                    str(passage.get("passage_id") or ""),
                    *(passage.get("linked_passages") or ()),
                ]
            )
        )
    return tuple(grouped.values())


def _passage_projection_map(
    passages: Sequence[Mapping[str, Any]],
) -> dict[str, set[str]]:
    return {
        str(row["passage_id"]): {
            reason.removeprefix("projection:")
            for reason in row.get("selection_reason") or ()
            if str(reason).startswith("projection:")
        }
        for row in passages
    }


def build_person_shadow_candidate(
    source_report: Mapping[str, Any],
    claim_report: Mapping[str, Any],
) -> dict[str, Any]:
    if source_report["person_ref"] != claim_report["person_ref"]:
        raise ValueError("source/claim 人物不一致")
    source_passages = _deduplicate_passages(
        tuple((source_report.get("response") or {}).get("passages") or ())
    )
    expected_claim_source_fingerprint = _hash(
        {
            "selection_version": CLAIM_SELECTION_VERSION,
            "passages": tuple(
                {
                    "passage_id": str(row["passage_id"]),
                    "raw_text": str(row["raw_text"]),
                    "context_before": str(row.get("context_before") or ""),
                    "context_after": str(row.get("context_after") or ""),
                }
                for row in source_passages
            ),
        }
    )
    if claim_report.get("source_output_fingerprint") and (
        claim_report["source_output_fingerprint"]
        != expected_claim_source_fingerprint
    ):
        raise ValueError("claim report 不属于当前 source passages")
    assertions = tuple((claim_report.get("response") or {}).get("assertions") or ())
    by_passage: dict[str, list[Mapping[str, Any]]] = {}
    for assertion in assertions:
        by_passage.setdefault(str(assertion["source_passage_ref"]), []).append(assertion)
    evidence_passages = tuple(
        (claim_report.get("request") or {}).get("passages")
        or (source_report.get("response") or {}).get("passages")
        or ()
    )
    passages = {
        str(row["passage_id"]): row
        for row in evidence_passages
    }
    projection_map = {
        str(passage_ref): {str(target) for target in targets}
        for passage_ref, targets in (
            claim_report.get("passage_projection_map") or {}
        ).items()
    } or _passage_projection_map(evidence_passages)
    episodes = []
    excluded_episode_assertions = []
    talent_refs = []
    talent_achievement_refs = []
    talent_authority_refs = []
    talent_ambiguity_refs = []
    risk_refs = []
    counterevidence_refs = []
    counterevidence_passage_refs = []
    risk_excluded_refs = []
    risk_dispositions = []
    for passage_ref, rows in sorted(by_passage.items()):
        assertion_refs = [str(row["assertion_code"]) for row in rows]
        disputed_refs = [
            str(row["assertion_code"])
            for row in rows
            if str(row.get("polarity")) in _DISPUTED_POLARITIES
        ]
        non_episode_refs = [
            str(row["assertion_code"])
            for row in rows
            if str(row.get("assertion_type")) in _NON_EPISODE_ASSERTION_TYPES
        ]
        non_focal_subject_refs = [
            str(row["assertion_code"])
            for row in rows
            if str(row.get("subject") or "")
            and str(row.get("subject")) != str(source_report["person_name"])
            and str(row["assertion_code"])
            not in {*disputed_refs, *non_episode_refs}
        ]
        episode_rows = [
            row
            for row in rows
            if str(row["assertion_code"])
            not in {*disputed_refs, *non_episode_refs, *non_focal_subject_refs}
        ]
        if episode_rows:
            episode_assertion_refs = [str(row["assertion_code"]) for row in episode_rows]
            identity = _hash(
                {
                    "person_ref": source_report["person_ref"],
                    "passage_ref": passage_ref,
                    "assertion_refs": episode_assertion_refs,
                }
            )
            episodes.append(
                {
                    "episode_ref": f"EPDRAFT-{identity[:20].upper()}",
                    "status": "proposed",
                    "source_passage_ref": passage_ref,
                    "assertion_refs": episode_assertion_refs,
                    "actions": list(
                        dict.fromkeys(str(row["predicate"]) for row in episode_rows)
                    ),
                    "outcomes": list(
                        dict.fromkeys(str(row["object"]) for row in episode_rows)
                    ),
                    "formal_acceptance": False,
                }
            )
        excluded_episode_assertions.extend(
            {
                "assertion_ref": ref,
                "reason": reason,
                "source_passage_ref": passage_ref,
            }
            for refs, reason in (
                (disputed_refs, "disputed_or_negated"),
                (non_episode_refs, "historiographical_evaluation_not_episode"),
                (non_focal_subject_refs, "subject_is_not_focal_person"),
            )
            for ref in refs
        )
        targets = projection_map.get(passage_ref, set())
        if "talent_profile_candidate" in targets:
            talent_refs.extend(assertion_refs)
            talent_achievement_refs.extend(
                str(row["assertion_code"])
                for row in rows
                if str(row.get("assertion_type"))
                != "historiographical_evaluation"
                and str(row.get("polarity")) not in _DISPUTED_POLARITIES
            )
            talent_authority_refs.extend(non_episode_refs)
            talent_ambiguity_refs.extend(
                str(row["assertion_code"])
                for row in rows
                if row.get("ambiguity_flags")
            )
        talent_achievement_refs.extend(
            str(row["assertion_code"])
            for row in rows
            if str(row.get("subject") or "") == str(source_report["person_name"])
            and str(row.get("assertion_type")) == "event_fact"
            and str(row.get("polarity")) not in _DISPUTED_POLARITIES
            and str((row.get("qualifiers") or {}).get("responsibility_family") or "")
            in _TALENT_ACHIEVEMENT_RESPONSIBILITY_FAMILIES
        )
        if "political_risk_profile_candidate" in targets:
            passage = passages.get(passage_ref) or {}
            passage_text = "\n".join(
                str(passage.get(field) or "")
                for field in ("context_before", "raw_text", "context_after")
            )
            risk_rows = [
                row
                for row in rows
                if str((row.get("qualifiers") or {}).get("event_scope") or "")
                in {"风险事件", "政治风险事件"}
                and str(row.get("subject") or "") == str(source_report["person_name"])
            ]
            non_risk_refs = {
                str(row["assertion_code"])
                for row in rows
                if row not in risk_rows
            }
            if non_risk_refs:
                risk_excluded_refs.extend(sorted(non_risk_refs))
                risk_dispositions.extend(
                    {
                        "assertion_ref": ref,
                        "disposition": "excluded",
                        "reason": "not_explicit_personal_risk_event",
                    }
                    for ref in sorted(non_risk_refs)
                )
            is_disputed_or_exculpatory = any(
                term in passage_text for term in _DISPUTED_OR_EXCULPATORY_TERMS
            ) or any(
                str(row.get("polarity") or "") in _DISPUTED_POLARITIES
                for row in risk_rows
            )
            risk_assertion_refs = [
                str(row["assertion_code"])
                for row in risk_rows
            ]
            if is_disputed_or_exculpatory and risk_assertion_refs:
                risk_excluded_refs.extend(risk_assertion_refs)
                if any(
                    term in passage_text
                    for term in ("意已悟", "勿以為懷", "勿以为怀", "誣", "诬")
                ):
                    counterevidence_passage_refs.append(passage_ref)
                risk_dispositions.extend(
                    {
                        "assertion_ref": ref,
                        "disposition": "excluded",
                        "reason": "accusation_disputed_or_exculpatory_context",
                    }
                    for ref in risk_assertion_refs
                )
            elif risk_assertion_refs:
                risk_refs.extend(risk_assertion_refs)
                risk_dispositions.extend(
                    {
                        "assertion_ref": ref,
                        "disposition": "needs_human_judgment",
                        "reason": "direct_risk_candidate",
                    }
                    for ref in risk_assertion_refs
                )
    payload = {
        "schema_version": PIPELINE_SCHEMA_VERSION,
        "stage": "person_shadow_candidate",
        "person_ref": source_report["person_ref"],
        "person_name": source_report["person_name"],
        "historical_episode_candidates": episodes,
        "historical_episode_exclusions": excluded_episode_assertions,
        "profile_candidate": {
            "talent_grade_status": "needs_human_judgment",
            "talent_grade": None,
            "talent_assertion_refs": list(dict.fromkeys(talent_refs)),
            "talent_achievement_assertion_refs": list(
                dict.fromkeys(talent_achievement_refs)
            ),
            "talent_authority_assertion_refs": list(
                dict.fromkeys(talent_authority_refs)
            ),
            "talent_ambiguity_assertion_refs": list(
                dict.fromkeys(talent_ambiguity_refs)
            ),
            "talent_evidence_coverage": "partial",
            "political_risk_status": (
                "needs_human_judgment" if risk_refs else "insufficient_evidence"
            ),
            "political_risk_severity": None,
            "political_risk_assertion_refs": list(dict.fromkeys(risk_refs)),
            "political_risk_excluded_assertion_refs": list(
                dict.fromkeys(risk_excluded_refs)
            ),
            "political_risk_counterevidence_refs": list(
                dict.fromkeys(counterevidence_refs)
            ),
            "political_risk_counterevidence_passage_refs": list(
                dict.fromkeys(counterevidence_passage_refs)
            ),
            "political_risk_dispositions": risk_dispositions,
        },
        "unresolved": [
            *list(source_report.get("discovery_unresolved_locators") or ()),
            *[
                row
                for row in source_report.get("discovery_omissions") or ()
                if row.get("blocks_profile_review") is True
                and row.get("source_backfill_status") != "resolved_source_passage"
            ],
            *list((source_report.get("response") or {}).get("errors") or ()),
            *list((claim_report.get("response") or {}).get("coverage_gaps") or ()),
        ],
        "lineage": {
            "source_output_fingerprint": (source_report.get("response") or {}).get(
                "output_fingerprint"
            ),
            "claim_output_fingerprint": (claim_report.get("response") or {}).get(
                "output_fingerprint"
            ),
        },
        "formal_writes": {
            "database": 0,
            "assertion": 0,
            "historical_episode": 0,
            "person_profile": 0,
            "score": 0,
            "ranking": 0,
        },
    }
    payload["output_fingerprint"] = _hash(payload)
    return payload


def assemble_ready_people(
    source_report_dir: Path,
    claim_report_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    claims_by_person: dict[str, Mapping[str, Any]] = {}
    for path in sorted(claim_report_dir.glob("*.json")):
        claim = json.loads(path.read_text(encoding="utf-8"))
        person_ref = str(claim.get("person_ref") or "")
        if person_ref:
            claims_by_person[person_ref] = claim
    assembled = []
    unchanged = []
    waiting_for_claim = []
    for path in sorted(source_report_dir.glob("*.json")):
        source = json.loads(path.read_text(encoding="utf-8"))
        person_ref = str(source.get("person_ref") or "")
        claim = claims_by_person.get(person_ref)
        if claim is None:
            waiting_for_claim.append(person_ref or path.stem)
            continue
        candidate = build_person_shadow_candidate(source, claim)
        changed = _atomic_json(output_dir / f"{person_ref}.json", candidate)
        (assembled if changed else unchanged).append(person_ref)
    return {
        "stage": "assemble_ready",
        "assembled": assembled,
        "unchanged": unchanged,
        "waiting_for_claim": waiting_for_claim,
        "formal_writes": 0,
    }


def run_ready_pipeline(
    ready_dir: Path,
    *,
    source_state_dir: Path,
    source_report_dir: Path,
    claim_state_dir: Path,
    claim_report_dir: Path,
    shadow_output_dir: Path,
    profiles_path: Path,
    output_schema_path: Path,
    codex_bin: str,
    model: str,
    reasoning_effort: str,
    per_claim_timeout_seconds: int,
    service_release_sha: str,
    source_max_workers: int,
    max_source_documents_per_person: int,
    claim_max_workers: int,
    claim_max_attempts_per_source: int,
    wall_clock_budget_seconds: int,
) -> dict[str, Any]:
    """Run the non-browser I5B shadow chain under one wall-clock envelope."""
    if (
        wall_clock_budget_seconds <= 0
        or per_claim_timeout_seconds <= 0
        or max_source_documents_per_person <= 0
        or claim_max_attempts_per_source <= 0
    ):
        raise ValueError("I5B 墙钟预算、单次 Claim 超时、首轮文献数和尝试次数必须为正数")
    started_at = monotonic()
    source = backfill_ready_people(
        ready_dir,
        state_dir=source_state_dir,
        output_dir=source_report_dir,
        service_release_sha=service_release_sha,
        max_workers=source_max_workers,
        max_source_documents=max_source_documents_per_person,
    )
    elapsed_after_source = monotonic() - started_at
    remaining_seconds = max(0, wall_clock_budget_seconds - int(elapsed_after_source))
    if remaining_seconds:
        claims = claim_ready_sources(
            source_report_dir,
            profiles_path=profiles_path,
            state_dir=claim_state_dir,
            output_dir=claim_report_dir,
            provider_factory=lambda remaining: CodexCliClaimExtractionProvider(
                codex_bin=codex_bin,
                model=model,
                reasoning_effort=reasoning_effort,
                output_schema_path=output_schema_path,
                timeout_seconds=min(per_claim_timeout_seconds, remaining),
            ),
            service_release_sha=service_release_sha,
            max_workers=claim_max_workers,
            deadline_seconds=remaining_seconds,
            max_attempts_per_source=claim_max_attempts_per_source,
        )
    else:
        claims = {
            "stage": "claim_batch",
            "completed": [],
            "discarded_after_deadline": [],
            "not_started": [path.name for path in source_report_dir.glob("*.json")],
            "max_workers": claim_max_workers,
            "attempts": {},
            "deadline_seconds": 0,
            "status": "skipped_budget_exhausted",
        }
    assembled = assemble_ready_people(
        source_report_dir,
        claim_report_dir,
        shadow_output_dir,
    )
    elapsed_seconds = monotonic() - started_at
    return {
        "stage": "person_rebuild_ready_pipeline",
        "wall_clock_budget_seconds": wall_clock_budget_seconds,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "remaining_seconds": max(0, round(wall_clock_budget_seconds - elapsed_seconds, 3)),
        "within_budget": elapsed_seconds <= wall_clock_budget_seconds,
        "source_backfill": source,
        "claim_extraction": claims,
        "assembly": assembled,
        "formal_writes": 0,
    }


def run_discovery_ready_pipeline(
    results_dir: Path,
    ready_dir: Path,
    **pipeline_kwargs: Any,
) -> dict[str, Any]:
    """Consume completed browser artifacts without another manual dispatch step."""
    dispatch = dispatch_ready_people(results_dir, ready_dir)
    pipeline = run_ready_pipeline(ready_dir, **pipeline_kwargs)
    return {
        "stage": "person_rebuild_discovery_ready_pipeline",
        "dispatch": dispatch,
        "pipeline": pipeline,
        "formal_writes": 0,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="人物宽搜异步回源与 shadow 重建流水线")
    sub = parser.add_subparsers(dest="command", required=True)
    dispatch = sub.add_parser("dispatch")
    dispatch.add_argument("--results-dir", type=Path, required=True)
    dispatch.add_argument("--ready-dir", type=Path, required=True)
    backfill = sub.add_parser("backfill-once")
    backfill.add_argument("--ready-dir", type=Path, required=True)
    backfill.add_argument("--state-dir", type=Path, required=True)
    backfill.add_argument("--output-dir", type=Path, required=True)
    backfill.add_argument("--service-release-sha", required=True)
    i5b_backfill = sub.add_parser("i5b-backfill")
    i5b_backfill.add_argument("--worklist", type=Path, required=True)
    i5b_backfill.add_argument("--state-dir", type=Path, required=True)
    i5b_backfill.add_argument("--output-dir", type=Path, required=True)
    i5b_backfill.add_argument("--service-release-sha", required=True)
    i5b_backfill.add_argument("--max-workers", type=int, default=6)
    i5b_backfill.add_argument("--local-source-index", type=Path)
    claim = sub.add_parser("claim")
    claim.add_argument("--source-report", type=Path, required=True)
    claim.add_argument("--profiles", type=Path, required=True)
    claim.add_argument("--state-dir", type=Path, required=True)
    claim.add_argument("--output-dir", type=Path, required=True)
    claim.add_argument("--output-schema", type=Path, required=True)
    claim.add_argument("--codex-bin", required=True)
    claim.add_argument("--model", required=True)
    claim.add_argument("--reasoning-effort", required=True)
    claim.add_argument("--timeout-seconds", type=int, default=600)
    claim.add_argument("--service-release-sha", required=True)
    claim_batch = sub.add_parser("claim-ready")
    claim_batch.add_argument("--source-report-dir", type=Path, required=True)
    claim_batch.add_argument("--profiles", type=Path, required=True)
    claim_batch.add_argument("--state-dir", type=Path, required=True)
    claim_batch.add_argument("--output-dir", type=Path, required=True)
    claim_batch.add_argument("--output-schema", type=Path, required=True)
    claim_batch.add_argument("--codex-bin", required=True)
    claim_batch.add_argument("--model", required=True)
    claim_batch.add_argument("--reasoning-effort", required=True)
    claim_batch.add_argument("--timeout-seconds", type=int, default=300)
    claim_batch.add_argument("--service-release-sha", required=True)
    claim_batch.add_argument("--max-workers", type=int, default=6)
    claim_batch.add_argument("--deadline-seconds", type=int, required=True)
    claim_batch.add_argument("--max-attempts-per-source", type=int, default=2)
    run_ready = sub.add_parser("run-ready")
    run_ready.add_argument("--results-dir", type=Path)
    run_ready.add_argument("--ready-dir", type=Path, required=True)
    run_ready.add_argument("--source-state-dir", type=Path, required=True)
    run_ready.add_argument("--source-report-dir", type=Path, required=True)
    run_ready.add_argument("--claim-state-dir", type=Path, required=True)
    run_ready.add_argument("--claim-report-dir", type=Path, required=True)
    run_ready.add_argument("--shadow-output-dir", type=Path, required=True)
    run_ready.add_argument("--profiles", type=Path, required=True)
    run_ready.add_argument("--output-schema", type=Path, required=True)
    run_ready.add_argument("--codex-bin", required=True)
    run_ready.add_argument("--model", required=True)
    run_ready.add_argument("--reasoning-effort", required=True)
    run_ready.add_argument("--per-claim-timeout-seconds", type=int, default=180)
    run_ready.add_argument("--service-release-sha", required=True)
    run_ready.add_argument("--source-max-workers", type=int, default=6)
    run_ready.add_argument("--max-source-documents-per-person", type=int, default=2)
    run_ready.add_argument("--claim-max-workers", type=int, default=6)
    run_ready.add_argument("--claim-max-attempts-per-source", type=int, default=2)
    run_ready.add_argument("--wall-clock-budget-seconds", type=int, default=900)
    assemble = sub.add_parser("assemble")
    assemble.add_argument("--source-report", type=Path, required=True)
    assemble.add_argument("--claim-report", type=Path, required=True)
    assemble.add_argument("--output", type=Path, required=True)
    assemble_ready = sub.add_parser("assemble-ready")
    assemble_ready.add_argument("--source-report-dir", type=Path, required=True)
    assemble_ready.add_argument("--claim-report-dir", type=Path, required=True)
    assemble_ready.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "dispatch":
        report = dispatch_ready_people(args.results_dir, args.ready_dir)
    elif args.command == "backfill-once":
        report = run_backfill_once(
            args.ready_dir,
            state_dir=args.state_dir,
            output_dir=args.output_dir,
            service_release_sha=args.service_release_sha,
        )
    elif args.command == "i5b-backfill":
        report = backfill_i5b_worklist(
            args.worklist,
            state_dir=args.state_dir,
            output_dir=args.output_dir,
            service_release_sha=args.service_release_sha,
            max_workers=args.max_workers,
            local_source_index_path=args.local_source_index,
        )
    elif args.command == "claim":
        report = claim_person_sources(
            args.source_report,
            profiles_path=args.profiles,
            state_dir=args.state_dir,
            output_dir=args.output_dir,
            provider=CodexCliClaimExtractionProvider(
                codex_bin=args.codex_bin,
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                output_schema_path=args.output_schema,
                timeout_seconds=args.timeout_seconds,
            ),
            service_release_sha=args.service_release_sha,
        )
    elif args.command == "claim-ready":
        report = claim_ready_sources(
            args.source_report_dir,
            profiles_path=args.profiles,
            state_dir=args.state_dir,
            output_dir=args.output_dir,
            provider_factory=lambda remaining: CodexCliClaimExtractionProvider(
                codex_bin=args.codex_bin,
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                output_schema_path=args.output_schema,
                timeout_seconds=min(args.timeout_seconds, remaining),
            ),
            service_release_sha=args.service_release_sha,
            max_workers=args.max_workers,
            deadline_seconds=args.deadline_seconds,
            max_attempts_per_source=args.max_attempts_per_source,
        )
    elif args.command == "run-ready":
        pipeline_kwargs = {
            "source_state_dir": args.source_state_dir,
            "source_report_dir": args.source_report_dir,
            "claim_state_dir": args.claim_state_dir,
            "claim_report_dir": args.claim_report_dir,
            "shadow_output_dir": args.shadow_output_dir,
            "profiles_path": args.profiles,
            "output_schema_path": args.output_schema,
            "codex_bin": args.codex_bin,
            "model": args.model,
            "reasoning_effort": args.reasoning_effort,
            "per_claim_timeout_seconds": args.per_claim_timeout_seconds,
            "service_release_sha": args.service_release_sha,
            "source_max_workers": args.source_max_workers,
            "max_source_documents_per_person": args.max_source_documents_per_person,
            "claim_max_workers": args.claim_max_workers,
            "claim_max_attempts_per_source": args.claim_max_attempts_per_source,
            "wall_clock_budget_seconds": args.wall_clock_budget_seconds,
        }
        report = (
            run_discovery_ready_pipeline(
                args.results_dir,
                args.ready_dir,
                **pipeline_kwargs,
            )
            if args.results_dir is not None
            else run_ready_pipeline(args.ready_dir, **pipeline_kwargs)
        )
    elif args.command == "assemble":
        source_report = json.loads(args.source_report.read_text(encoding="utf-8"))
        claim_report = json.loads(args.claim_report.read_text(encoding="utf-8"))
        report = build_person_shadow_candidate(source_report, claim_report)
        _atomic_json(args.output, report)
    else:
        report = assemble_ready_people(
            args.source_report_dir,
            args.claim_report_dir,
            args.output_dir,
        )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
