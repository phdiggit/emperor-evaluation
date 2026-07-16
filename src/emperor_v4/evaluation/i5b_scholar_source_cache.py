from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import unquote, urlparse

import yaml

from emperor_v4.adapters.source_cache_wikisource import (
    WikisourceSourceMaterialProvider,
)
from emperor_v4.adapters.wikisource import (
    WikisourcePageSnapshot,
    fetch_wikisource_plaintext,
    write_wikisource_snapshot,
)
from emperor_v4.application.source_cache_service import ensure_source_cache
from emperor_v4.persistence.source_cache import InMemorySourceCacheRepository
from emperor_v4.runtime.source_cache import source_cache_request_from_mapping


FetchWikisource = Callable[..., WikisourcePageSnapshot]
BUILDER_VERSION = "i5b-scholar-source-cache-builder-v2-task-bound"


def _page_title(canonical_url: str) -> str:
    parsed = urlparse(canonical_url)
    if parsed.netloc != "zh.wikisource.org" or not parsed.path.startswith("/wiki/"):
        raise ValueError(f"非 Wikisource 原始史料定位: {canonical_url}")
    title = unquote(parsed.path.removeprefix("/wiki/")).replace("_", " ").strip()
    if not title:
        raise ValueError("Wikisource 原始史料定位缺少页面标题")
    return title


class MemoizingWikisourceFetcher:
    def __init__(self, fetch: FetchWikisource = fetch_wikisource_plaintext) -> None:
        self.fetch = fetch
        self.network_request_count = 0
        self.snapshots: dict[str, WikisourcePageSnapshot] = {}

    def __call__(
        self,
        *,
        page_code: str,
        page_title: str,
        expected_revision_id: int | None = None,
    ) -> WikisourcePageSnapshot:
        cached = self.snapshots.get(page_title)
        if cached is not None:
            if expected_revision_id is not None and cached.revision_id != expected_revision_id:
                raise ValueError(f"缓存 revision 与 plan 不一致: {page_title}")
            return cached
        snapshot = self.fetch(
            page_code=page_code,
            page_title=page_title,
            expected_revision_id=expected_revision_id,
        )
        self.snapshots[page_title] = snapshot
        self.network_request_count += 1
        return snapshot


def _plan_for_task(task: Mapping[str, Any]) -> dict[str, Any] | None:
    sections = []
    for index, locator in enumerate(task.get("primary_source_locators") or (), start=1):
        passages = locator.get("source_cache_passages") or ()
        if not passages:
            continue
        title = _page_title(str(locator["canonical_url"]))
        page_code = "wikisource-" + sha256(title.encode("utf-8")).hexdigest()[:16]
        sections.append(
            {
                "page_code": page_code,
                "page_title": title,
                "work_identity": str(locator["work"]),
                "edition_identity": "Wikisource MediaWiki API plaintext; live revision captured in Source Cache",
                "source_role": "primary_text",
                "license_or_access_note": (
                    "public-domain text; transcription quality remains review-visible"
                ),
                "section_id": f"{task['case_ref'].lower()}-{index}",
                "section_heading": str(locator["section"]),
                "document_span_start": 0,
                "window_policy": {
                    "version": "v4-scholar-guided-exact-anchor-v1",
                    "sentence_radius_before": 0,
                    "sentence_radius_after": 0,
                    "context_chars_before": 0,
                    "context_chars_after": 0,
                },
                "passages": [dict(passage) for passage in passages],
            }
        )
    if not sections:
        return None
    return {
        "schema_version": 1,
        "provider": "wikisource_revision_plan",
        "subject_ref": task["subject_ref"],
        "sections": sections,
    }


def run_scholar_source_cache_shadow(
    *,
    report: Mapping[str, Any],
    output_dir: Path,
    service_release_sha: str,
    fetch: FetchWikisource = fetch_wikisource_plaintext,
) -> dict[str, Any]:
    if report.get("schema_version") != "i5b-scholar-guided-retrieval-report-v1":
        raise ValueError("Source Cache shadow 只能消费学术引导检索报告")
    output_path = output_dir / "source-cache-shadow.json"
    if output_path.is_file():
        cached = json.loads(output_path.read_text(encoding="utf-8"))
        if (
            cached.get("source_report_sha256") == report.get("report_sha256")
            and cached.get("builder_version") == BUILDER_VERSION
            and cached.get("service_release_sha") == service_release_sha
        ):
            cached["current_run_audit"] = {
                "exact_response_reused": True,
                "network_request_count": 0,
                "shadow_state_write_count": 0,
                "database_write_count": 0,
                "model_call_count": 0,
            }
            return cached
    plans_dir = output_dir / "plans"
    snapshots_dir = output_dir / "snapshots"
    plans_dir.mkdir(parents=True, exist_ok=True)
    memoized_fetch = MemoizingWikisourceFetcher(fetch)
    repository = InMemorySourceCacheRepository()
    task_runs = []
    documents: dict[str, dict[str, Any]] = {}
    passages: dict[str, dict[str, Any]] = {}
    unresolved = []
    provider_call_count = 0
    shadow_state_write_count = 0

    for task in report.get("source_cache_tasks") or ():
        plan = _plan_for_task(task)
        if plan is None:
            unresolved.append(
                {
                    "case_ref": task["case_ref"],
                    "subject_ref": task["subject_ref"],
                    "reason": "missing_exact_source_cache_passage_locator",
                }
            )
            continue
        plan_path = plans_dir / f"{task['case_ref'].lower()}.yml"
        plan_path.write_text(
            yaml.safe_dump(plan, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
            newline="\n",
        )
        run = ensure_source_cache(
            source_cache_request_from_mapping(task["source_cache_request"]),
            provider=WikisourceSourceMaterialProvider(
                plan_path=plan_path, fetch=memoized_fetch
            ),
            repository=repository,
            service_release_sha=service_release_sha,
        )
        provider_call_count += run.provider_call_count
        shadow_state_write_count += run.repository_write_count
        for document in run.response["documents"]:
            documents.setdefault(document["document_cache_id"], dict(document))
        for passage in run.response["passages"]:
            passage_with_task = {
                **passage,
                "source_cache_task_code": task["task_code"],
            }
            passages.setdefault(passage["passage_id"], passage_with_task)
        task_runs.append(
            {
                "case_ref": task["case_ref"],
                "request_id": run.response["request_id"],
                "status": run.response["status"],
                "document_count": len(run.response["documents"]),
                "passage_count": len(run.response["passages"]),
                "network_request_count": run.network_request_count,
            }
        )

    for title, snapshot in memoized_fetch.snapshots.items():
        snapshot_name = sha256(title.encode("utf-8")).hexdigest()[:16] + ".json"
        write_wikisource_snapshot(snapshot, snapshots_dir / snapshot_name)

    response = {
        "contract": "v4.source_cache.response.v2",
        "status": "succeeded_with_explicit_locator_gaps" if unresolved else "succeeded",
        "documents": sorted(documents.values(), key=lambda row: row["document_cache_id"]),
        "passages": sorted(passages.values(), key=lambda row: row["passage_id"]),
        "unresolved_tasks": unresolved,
    }
    result = {
        "schema_version": "i5b-scholar-source-cache-shadow-v1",
        "builder_version": BUILDER_VERSION,
        "service_release_sha": service_release_sha,
        "status": response["status"],
        "source_report_sha256": report["report_sha256"],
        "response": response,
        "task_runs": task_runs,
        "runtime_audit": {
            "planned_task_count": len(task_runs),
            "unresolved_task_count": len(unresolved),
            "unique_page_count": len(memoized_fetch.snapshots),
            "provider_call_count": provider_call_count,
            "network_request_count": memoized_fetch.network_request_count,
            "shadow_state_write_count": shadow_state_write_count,
            "database_write_count": 0,
            "model_call_count": 0,
            "formal_acceptance_performed": False,
        },
        "snapshots": [
            {
                "page_title": title,
                "revision_id": snapshot.revision_id,
                "revision_timestamp": snapshot.revision_timestamp,
                "content_hash": snapshot.content_hash,
            }
            for title, snapshot in sorted(memoized_fetch.snapshots.items())
        ],
        "current_run_audit": {
            "exact_response_reused": False,
            "network_request_count": memoized_fetch.network_request_count,
            "shadow_state_write_count": shadow_state_write_count,
            "database_write_count": 0,
            "model_call_count": 0,
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result
