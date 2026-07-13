from __future__ import annotations

from dataclasses import replace
import os
import uuid

import pytest

from emperor_v4.application.core_shadow_runner import run_core_shadow_sync
from emperor_v4.contracts.episode import AssertionLink
from emperor_v4.domain.versioning import apply_episode_revision
from emperor_v4.persistence import (
    CoreRegistryBatch,
    EpisodeDispositionRecord,
    PostgresCoreRegistry,
    bootstrap_g3a_schema,
)
from test_g3a_core_registry import _assertion, _initial_batch, _passage


pytestmark = pytest.mark.db


def _integration_dsn() -> str:
    dsn = os.environ.get("EMPEROR_EVAL_V4_DSN")
    if not dsn:
        pytest.skip("EMPEROR_EVAL_V4_DSN 未显式注入测试进程")
    return dsn


def _source_cache_isolated_dsn() -> str:
    dsn = os.environ.get("EMPEROR_EVAL_V4_SOURCE_CACHE_ISOLATED_DSN")
    if not dsn:
        pytest.skip("未显式注入 Source Cache 独立临时数据库 DSN")
    return dsn


def _claim_extractor_isolated_dsn() -> str:
    dsn = os.environ.get("EMPEROR_EVAL_V4_CLAIM_EXTRACTOR_ISOLATED_DSN")
    if not dsn:
        pytest.skip("未显式注入 Claim Extractor 独立临时数据库 DSN")
    return dsn


def test_real_postgres_claim_extractor_job_lease_contract() -> None:
    from dataclasses import asdict
    import json
    from pathlib import Path

    import psycopg

    from emperor_v4.adapters.claim_extraction_profile import load_claim_extraction_profile
    from emperor_v4.adapters.claim_extractor_frozen import FrozenClaimExtractionProvider
    from emperor_v4.application.claim_extractor_service import (
        claim_extraction_input_fingerprint,
        ensure_claim_extraction,
    )
    from emperor_v4.application.source_cache_worker import run_source_cache_worker_once
    from emperor_v4.persistence.postgres_claim_extractor import (
        PostgresClaimExtractionRepository,
        bootstrap_claim_extractor_schema,
    )
    from emperor_v4.persistence.source_cache_jobs import PostgresSourceCacheJobRepository
    from emperor_v4.runtime.claim_extractor import request_from_frozen_snapshot, request_from_mapping

    dsn = _claim_extractor_isolated_dsn()
    root = Path(__file__).parents[1]
    snapshot_path = root / "tests/fixtures/episode_pilot_v1/claim-extractor-talent-discovery-response.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    profile = load_claim_extraction_profile(root / "config/claim-extraction-profiles.yml", "talent_discovery_chain_v1")
    request = request_from_frozen_snapshot(snapshot, profile_code=profile.code, request_id="CLX-PG-1", idempotency_key="claim:v4:pg:1", requested_at="2026-07-14T20:00:00+08:00")
    with psycopg.connect(dsn, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("DROP SCHEMA IF EXISTS v4_claim_extractor CASCADE")
    try:
        assert bootstrap_claim_extractor_schema(dsn).action == "applied"
        assert bootstrap_claim_extractor_schema(dsn).database_write_count == 0
        jobs = PostgresSourceCacheJobRepository(dsn, schema="v4_claim_extractor")
        payload = asdict(request)
        fingerprint = claim_extraction_input_fingerprint(request, profile)
        assert jobs.enqueue(job_id="CLXJ-PG-1", idempotency_key="claim-job:pg:1", input_fingerprint=fingerprint, policy_version=profile.code, request_payload=payload) == 1
        assert jobs.enqueue(job_id="CLXJ-PG-DUP", idempotency_key="claim-job:pg:1", input_fingerprint=fingerprint, policy_version=profile.code, request_payload=payload) == 0
        provider = FrozenClaimExtractionProvider(snapshot_path)
        repository = PostgresClaimExtractionRepository(dsn)

        def handler(value):
            return ensure_claim_extraction(request_from_mapping(value), profile=profile, provider=provider, repository=repository, service_release_sha="c" * 40).response

        assert run_source_cache_worker_once(jobs, worker_id="claim-worker", handler=handler).status == "succeeded"
        assert run_source_cache_worker_once(jobs, worker_id="claim-worker", handler=handler).status == "idle"
        with psycopg.connect(dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM v4_claim_extractor.assertion_drafts")
                assert cursor.fetchone()[0] == 4
                cursor.execute("SELECT status, attempt_count FROM v4_claim_extractor.jobs")
                assert cursor.fetchone() == ("succeeded", 1)
    finally:
        with psycopg.connect(dsn, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("DROP SCHEMA IF EXISTS v4_claim_extractor CASCADE")


def test_real_postgres_source_cache_job_lease_contract() -> None:
    from dataclasses import asdict
    from pathlib import Path

    import psycopg

    from emperor_v4.adapters.source_cache_fixture import FrozenSourceMaterialProvider
    from emperor_v4.application.source_cache_service import (
        ensure_source_cache,
        source_cache_input_fingerprint,
    )
    from emperor_v4.application.source_cache_worker import run_source_cache_worker_once
    from emperor_v4.persistence.postgres_source_cache import (
        PostgresSourceCacheRepository,
        bootstrap_source_cache_schema,
    )
    from emperor_v4.persistence.source_cache_jobs import PostgresSourceCacheJobRepository
    from emperor_v4.runtime.source_cache import (
        load_source_cache_request,
        source_cache_request_from_mapping,
    )

    dsn = _source_cache_isolated_dsn()
    repo_root = Path(__file__).parents[1]
    with psycopg.connect(dsn, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("DROP SCHEMA IF EXISTS v4_source_cache CASCADE")
    try:
        first_bootstrap = bootstrap_source_cache_schema(dsn)
        second_bootstrap = bootstrap_source_cache_schema(dsn)
        assert first_bootstrap.action == "applied"
        assert second_bootstrap.action == "reused"
        assert second_bootstrap.database_write_count == 0

        request = load_source_cache_request(repo_root / "eval/source_cache_v4_demo/request.yml")
        payload = asdict(request)
        jobs = PostgresSourceCacheJobRepository(dsn)
        assert jobs.enqueue(
            job_id="SCJ-PG-1", idempotency_key="source-cache-job:pg:1",
            input_fingerprint=source_cache_input_fingerprint(request),
            policy_version=request.source_policy_version,
            request_payload=payload,
        ) == 1
        assert jobs.enqueue(
            job_id="SCJ-PG-DUP", idempotency_key="source-cache-job:pg:1",
            input_fingerprint=source_cache_input_fingerprint(request),
            policy_version=request.source_policy_version,
            request_payload=payload,
        ) == 0
        cache = PostgresSourceCacheRepository(dsn)
        provider = FrozenSourceMaterialProvider(
            plan_path=repo_root / "eval/source_cache_v4_demo/fixture_plan.yml",
            repo_root=repo_root,
        )

        def handler(value):
            return ensure_source_cache(
                source_cache_request_from_mapping(value), provider=provider,
                repository=cache, service_release_sha="a" * 40,
            ).response

        first = run_source_cache_worker_once(jobs, worker_id="pg-worker", handler=handler)
        idle = run_source_cache_worker_once(jobs, worker_id="pg-worker", handler=handler)
        assert first.status == "succeeded"
        assert idle.status == "idle"

        payload2 = dict(payload)
        payload2["request_id"] = "SRC-V4-PG-LEASE-2"
        payload2["idempotency_key"] = "source-cache:v4:pg:lease:2"
        request2 = source_cache_request_from_mapping(payload2)
        jobs.enqueue(
            job_id="SCJ-PG-LEASE", idempotency_key="source-cache-job:pg:lease",
            input_fingerprint=source_cache_input_fingerprint(request2),
            policy_version=request2.source_policy_version,
            request_payload=payload2,
        )
        claimed = jobs.claim(worker_id="expired-worker", lease_seconds=300)
        assert claimed is not None
        with psycopg.connect(dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE v4_source_cache.jobs
                    SET lease_expires_at = CURRENT_TIMESTAMP - INTERVAL '1 second'
                    WHERE job_id = 'SCJ-PG-LEASE'
                    """
                )
        recovered = run_source_cache_worker_once(
            jobs, worker_id="recovery-worker", handler=handler,
        )
        assert recovered.status == "succeeded"
        assert recovered.recovered_lease_count == 1
        with psycopg.connect(dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT status, attempt_count FROM v4_source_cache.jobs ORDER BY job_id"
                )
                assert cursor.fetchall() == [("succeeded", 1), ("succeeded", 2)]
                cursor.execute(
                    "SELECT status FROM v4_source_cache.job_runs ORDER BY job_id, attempt_number"
                )
                assert [row[0] for row in cursor.fetchall()] == [
                    "succeeded", "lease_expired", "succeeded"
                ]
    finally:
        with psycopg.connect(dsn, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("DROP SCHEMA IF EXISTS v4_source_cache CASCADE")


def _table_counts(dsn: str) -> dict[str, int]:
    import psycopg

    tables = (
        "source_documents",
        "source_passages",
        "assertions",
        "historical_episodes",
        "historical_episode_versions",
        "episode_participants",
        "episode_assertion_dispositions",
        "review_artifacts",
        "boundary_review_cache",
    )
    with psycopg.connect(dsn) as connection:
        with connection.cursor() as cursor:
            result = {}
            for table in tables:
                cursor.execute(f"SELECT count(*) FROM {table}")
                result[table] = int(cursor.fetchone()[0])
            return result


def test_real_postgres_core_registry_contract() -> None:
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    base_dsn = _integration_dsn()
    schema = f"g3a_it_{uuid.uuid4().hex[:12]}"
    params = conninfo_to_dict(base_dsn)
    existing_options = params.get("options", "").strip()
    params["options"] = f"{existing_options} -csearch_path={schema}".strip()
    schema_dsn = make_conninfo(**params)

    with psycopg.connect(base_dsn, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    try:
        first_bootstrap = bootstrap_g3a_schema(schema_dsn)
        second_bootstrap = bootstrap_g3a_schema(schema_dsn)
        assert first_bootstrap.action == "applied"
        assert second_bootstrap.action == "reused"
        assert second_bootstrap.database_write_count == 0

        registry = PostgresCoreRegistry(schema_dsn)
        initial = _initial_batch()
        first = registry.apply(initial)
        unchanged = registry.apply(initial)
        assert first.business_write_count > 0
        assert unchanged.business_write_count == 0
        assert unchanged.model_call_count == 0
        active = registry.active_packets_by_identity(("EP-1", "missing-anchor"))
        assert active["EP-1"] == initial.episodes[0]
        assert "missing-anchor" not in active

        current = initial.episodes[0]
        passage = _passage("SP-2", "又命某仍掌军务", 20)
        assertion = _assertion("A-2", passage.passage_cache_id)
        observed = replace(
            current,
            assertion_links=current.assertion_links
            + (
                AssertionLink(
                    assertion_ref="A-2",
                    source_passage_ref="SP-2",
                    relation="supports",
                    supported_fields=("identity", "action", "responsibility"),
                ),
            ),
        )
        evidence_revision = apply_episode_revision(current, observed).packet
        evidence_result = registry.apply(
            CoreRegistryBatch(
                source_passages=(passage,),
                assertions=(assertion,),
                episodes=(evidence_revision,),
                episode_dispositions=(
                    EpisodeDispositionRecord(
                        episode_id="EP-1",
                        semantic_version=1,
                        evidence_version=2,
                        assertion_ref="A-2",
                        disposition="core_of_episode",
                        reason="新增同义证据",
                    ),
                ),
            )
        )
        assert evidence_result.table_writes["historical_episode_versions"] == 1
        assert evidence_result.table_writes["episode_participants"] == 0

        semantic_observed = replace(evidence_revision, responsibility="财政")
        semantic_revision = apply_episode_revision(
            evidence_revision, semantic_observed
        ).packet
        semantic_result = registry.apply(CoreRegistryBatch(episodes=(semantic_revision,)))
        assert semantic_result.table_writes["historical_episode_versions"] == 1
        assert semantic_result.table_writes["episode_participants"] == 2

        runner_unchanged = run_core_shadow_sync(
            registry,
            CoreRegistryBatch(
                episodes=(semantic_revision,),
                episode_identity_anchors={semantic_revision.episode_id: "EP-1"},
            ),
        )
        assert runner_unchanged.business_write_count == 0
        runner_observed = replace(
            semantic_revision,
            episode_id="EP-OBSERVED-CHANGED-ID",
            consequence=("制度后果",),
            semantic_fingerprint="semantic-runner-v3",
        )
        runner_changed = run_core_shadow_sync(
            registry,
            CoreRegistryBatch(
                episodes=(runner_observed,),
                episode_identity_anchors={runner_observed.episode_id: "EP-1"},
            ),
        )
        assert runner_changed.semantic_revision_anchors == ("EP-1",)
        assert runner_changed.write_result.table_writes[
            "historical_episode_versions"
        ] == 1
        assert registry.active_packets_by_identity(("EP-1",))["EP-1"].semantic_version == 3

        before_failure = _table_counts(schema_dsn)
        bad_episode = replace(
            runner_observed,
            episode_id="EP-BAD",
            semantic_version=1,
            evidence_version=1,
            assertion_links=(
                AssertionLink(
                    assertion_ref="A-MISSING",
                    source_passage_ref="SP-MISSING",
                    relation="supports",
                    supported_fields=("identity", "action"),
                ),
            ),
        )
        with pytest.raises(ValueError, match="lineage"):
            registry.apply(CoreRegistryBatch(episodes=(bad_episode,)))
        assert _table_counts(schema_dsn) == before_failure

        with psycopg.connect(schema_dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT tablename FROM pg_catalog.pg_tables
                    WHERE schemaname = current_schema()
                      AND tablename IN (
                        'episode_relations', 'rule_evidence_units', 'rule_projections',
                        'judgments', 'score_contributions', 'outbox', 'workers'
                      )
                    """
                )
                assert cursor.fetchall() == []
    finally:
        with psycopg.connect(base_dsn, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
                )
