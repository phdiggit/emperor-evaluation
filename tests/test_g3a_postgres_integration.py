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
