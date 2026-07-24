from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path

from emperor_v4.adapters.source_text_index import (
    LocalSourceTextIndex,
    build_local_source_index,
)
from emperor_v4.adapters.wikisource import WikisourcePageSnapshot
from emperor_v4.runtime.workflow_source_cache import run_workflow_source_cache_once
from emperor_v4.runtime.workflow_source_cache import import_source_cache_snapshots
from emperor_v4.runtime.workflow_source_cache import submit_source_cache_request


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def test_workflow_source_cache_discovers_caches_and_stops_on_carrier_gap(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _write(repo / "config/project.yml", "dynasty_governance_catalog: {dynasties: {}}\n")
    _write(repo / "config/scope.yml", "dynasties: {}\n")
    _write(
        repo / "config/catalog.yml",
        """
schema_version: workflow-source-cache-catalog-v1
source_catalogs:
  search_scope: config/scope.yml
  project: config/project.yml
  derive_neutral_material_works: false
  derive_dynasty_governance_works: false
provider:
  max_pages_per_tick: 5
  transient_retry_after_seconds: 1800
  rate_limit_retry_after_seconds: 21600
pinned_collections:
  - collection_id: TEST
    purpose: test
    works:
      - work_title: 測試書
        root_title: 測試書
        required_page_titles: [測試書/卷1, 測試書/卷3]
""".lstrip(),
    )
    calls = {"list": 0, "fetch": 0}

    def list_pages(*, root_title: str) -> tuple[str, ...]:
        calls["list"] += 1
        assert root_title == "測試書"
        return ("測試書/卷1", "測試書/卷2")

    def fetch_pages(*, page_titles: list[str]) -> dict[str, WikisourcePageSnapshot]:
        calls["fetch"] += 1
        result = {}
        for title in page_titles:
            text = f"{title}正文"
            result[title] = WikisourcePageSnapshot(
                page_code="PAGE-" + sha256(title.encode()).hexdigest()[:8],
                requested_title=title,
                canonical_title=title,
                canonical_url=f"https://example.test/{title}",
                revision_id=100 + len(result),
                revision_timestamp="2026-07-24T00:00:00Z",
                retrieved_at=datetime.now(UTC).isoformat(),
                raw_text=text,
                content_hash=sha256(text.encode()).hexdigest(),
            )
        return result

    arguments = {
        "catalog_path": repo / "config/catalog.yml",
        "repo_root": repo,
        "state_root": tmp_path / "state",
        "request_root": tmp_path / "requests",
        "index_root": tmp_path / "indexes",
        "list_pages": list_pages,
        "fetch_pages": fetch_pages,
    }
    first = run_workflow_source_cache_once(**arguments)
    assert first["action"] == "inventory_discovered"
    assert calls == {"list": 1, "fetch": 0}

    second = run_workflow_source_cache_once(**arguments)
    assert second["action"] == "pages_cached"
    assert calls == {"list": 1, "fetch": 1}

    third = run_workflow_source_cache_once(**arguments)
    assert third["action"] == "idle"
    assert calls == {"list": 1, "fetch": 1}
    current = json.loads(
        (tmp_path / "indexes/workflow-test-current/CURRENT.json").read_text(
            encoding="utf-8"
        )
    )
    assert current["cached_required_page_count"] == 1
    assert current["carrier_missing_page_titles"] == ["測試書/卷3"]
    assert current["pending_page_count"] == 0
    index = LocalSourceTextIndex(
        tmp_path / "indexes/workflow-test-current/workflow-test.sqlite3"
    )
    assert [page.page_title for page in index.iter_pages(works=("測試書",))] == [
        "測試書/卷1",
    ]
    assert current["database_write_count"] == 0
    assert current["formal_score_write_count"] == 0
    assert current["model_call_count"] == 0


def test_source_cache_request_submission_is_idempotent_and_conflicts_fail(
    tmp_path: Path,
) -> None:
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "schema_version": "workflow-source-cache-request-v1",
                "request_id": "session-ruler",
                "collection_id": "RULER",
                "works": [
                    {
                        "work_title": "史書",
                        "required_page_titles": ["史書/卷1"],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    request_root = tmp_path / "requests"
    assert submit_source_cache_request(
        request_path=request, request_root=request_root
    )["status"] == "submitted"
    assert submit_source_cache_request(
        request_path=request, request_root=request_root
    )["status"] == "reused"

    payload = json.loads(request.read_text(encoding="utf-8"))
    payload["works"][0]["required_page_titles"] = ["史書/卷2"]
    request.write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    try:
        submit_source_cache_request(request_path=request, request_root=request_root)
    except ValueError as exc:
        assert "request_id 冲突" in str(exc)
    else:
        raise AssertionError("same request_id with changed content must fail")


def test_existing_local_index_is_a_zero_download_seed(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo / "config/project.yml", "dynasty_governance_catalog: {dynasties: {}}\n")
    _write(repo / "config/scope.yml", "dynasties: {}\n")
    _write(
        repo / "config/catalog.yml",
        """
schema_version: workflow-source-cache-catalog-v1
source_catalogs:
  search_scope: config/scope.yml
  project: config/project.yml
  derive_neutral_material_works: false
  derive_dynasty_governance_works: false
provider: {max_pages_per_tick: 5}
pinned_collections:
  - collection_id: SEEDED
    purpose: test
    works:
      - work_title: 種子書
        root_title: 種子書
        required_page_titles: [種子書/卷1]
""".lstrip(),
    )
    index_root = tmp_path / "indexes"
    build_local_source_index(
        [
            {
                "page_title": "種子書/卷1",
                "work_title": "種子書",
                "source_url": "https://example.test/seed",
                "revision_ref": "1",
                "raw_text": "既有正文",
            }
        ],
        index_root / "existing/current.sqlite3",
    )
    fetch_count = 0

    def forbidden_fetch(*, page_titles: list[str]) -> dict[str, WikisourcePageSnapshot]:
        nonlocal fetch_count
        fetch_count += 1
        raise AssertionError(page_titles)

    result = run_workflow_source_cache_once(
        catalog_path=repo / "config/catalog.yml",
        repo_root=repo,
        state_root=tmp_path / "state",
        request_root=tmp_path / "requests",
        index_root=index_root,
        list_pages=lambda **_: ("種子書/卷1",),
        fetch_pages=forbidden_fetch,
    )
    assert result["action"] == "inventory_discovered"
    assert fetch_count == 0
    current = json.loads(
        (index_root / "workflow-seeded-current/CURRENT.json").read_text(
            encoding="utf-8"
        )
    )
    assert current["cached_required_page_count"] == 1


def test_fixed_snapshot_import_is_validated_and_idempotent(tmp_path: Path) -> None:
    raw_text = "固定版本正文"
    payload = {
        "schema_version": "workflow-source-cache-import-v1",
        "snapshots": [
            {
                "page_title": "實錄/卷001",
                "work_title": "實錄",
                "source_url": "https://example.test/fixed",
                "revision_ref": "archive:v1",
                "raw_text": raw_text,
                "content_hash": sha256(raw_text.encode()).hexdigest(),
                "carrier_id": "approved-archive",
            }
        ],
    }
    source = tmp_path / "import.json"
    source.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    first = import_source_cache_snapshots(
        import_path=source, state_root=tmp_path / "state"
    )
    second = import_source_cache_snapshots(
        import_path=source, state_root=tmp_path / "state"
    )
    assert first["accepted_page_count"] == 1
    assert second["status"] == "reused"
    assert second["reused_page_count"] == 1

    payload["snapshots"][0]["raw_text"] = "被替换正文"
    payload["snapshots"][0]["content_hash"] = sha256(
        "被替换正文".encode()
    ).hexdigest()
    source.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    try:
        import_source_cache_snapshots(
            import_path=source, state_root=tmp_path / "state"
        )
    except ValueError as exc:
        assert "页面身份冲突" in str(exc)
    else:
        raise AssertionError("same page identity must not be overwritten")


def test_incomplete_primary_carrier_falls_back_to_secondary(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo / "config/project.yml", "dynasty_governance_catalog: {dynasties: {}}\n")
    _write(repo / "config/scope.yml", "dynasties: {}\n")
    _write(
        repo / "config/catalog.yml",
        """
schema_version: workflow-source-cache-catalog-v1
source_catalogs:
  search_scope: config/scope.yml
  project: config/project.yml
  derive_neutral_material_works: false
  derive_dynasty_governance_works: false
provider: {max_pages_per_tick: 5}
carriers:
  defaults:
    - {carrier_id: primary, provider_code: wikisource, root_title: 主载体}
    - {carrier_id: secondary, provider_code: wikisource, root_title: 备用载体}
pinned_collections:
  - collection_id: FALLBACK
    purpose: test
    works:
      - work_title: 合辑
        root_title: 合辑
        required_page_titles: [合辑/卷1, 合辑/卷2]
""".lstrip(),
    )
    calls = []

    def list_pages(*, root_title: str) -> tuple[str, ...]:
        calls.append(root_title)
        return ("合辑/卷1",) if root_title == "主载体" else ("合辑/卷2",)

    arguments = {
        "catalog_path": repo / "config/catalog.yml",
        "repo_root": repo,
        "state_root": tmp_path / "state",
        "request_root": tmp_path / "requests",
        "index_root": tmp_path / "indexes",
        "list_pages": list_pages,
        "fetch_pages": lambda **_: {},
    }
    assert run_workflow_source_cache_once(**arguments)["action"] == "inventory_discovered"
    assert run_workflow_source_cache_once(**arguments)["action"] == "inventory_discovered"
    assert calls == ["主载体", "备用载体"]
    current = json.loads(
        (tmp_path / "indexes/workflow-fallback-current/CURRENT.json").read_text(
            encoding="utf-8"
        )
    )
    assert current["inventory_complete"] is True
    assert current["carrier_missing_page_titles"] == []
    assert current["carrier_status"][0]["carriers_used"] == ["primary", "secondary"]
