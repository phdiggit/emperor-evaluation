from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any, Sequence


MIGRATION_KEY = "v4-schema-field-governance-v1"
IDENTITY_RESOLVER_VERSION = "role-aware-conservative-v3"
TARGET_SCHEMAS = (
    "public",
    "v4_source_cache",
    "v4_claim_extractor",
    "v4_person_profile",
    "v4_governance",
)
QUALITY_METRIC_SPECS = (
    (
        "reference_debt:episode_participants:noncanonical_person_ref",
        "public",
        "episode_participants",
        "person_ref",
        "noncanonical_reference",
        "person_ref !~ '^[A-Z][A-Z0-9]*(-[A-Z0-9]+)+$'",
    ),
    (
        "reference_debt:episode_participants:unresolved_person_ref:v2",
        "public",
        "episode_participants",
        "person_ref",
        "unresolved_reference",
        "NOT EXISTS (SELECT 1 FROM v4_governance.identity_reference_aliases r WHERE r.source_ref = episode_participants.person_ref AND r.active AND r.resolution_status IN ('canonical', 'alias'))",
    ),
    (
        "reference_debt:historical_episodes:noncanonical_evaluation_context",
        "public",
        "historical_episodes",
        "evaluation_context",
        "noncanonical_reference",
        "evaluation_context !~ '^[A-Z][A-Z0-9]*(-[A-Z0-9]+)+$'",
    ),
    (
        "mixed_text:person_profile_catalog:talent_grade_basis",
        "v4_person_profile",
        "person_profile_catalog",
        "talent_grade_basis",
        "mixed_han_latin",
        "talent_grade_basis ~ '[一-龥]' AND talent_grade_basis ~ '[A-Za-z]'",
    ),
    (
        "mixed_text:person_profile_catalog:negative_talent_basis",
        "v4_person_profile",
        "person_profile_catalog",
        "negative_talent_basis",
        "mixed_han_latin",
        "negative_talent_basis ~ '[一-龥]' AND negative_talent_basis ~ '[A-Za-z]'",
    ),
    (
        "mixed_text:talent_grade_calibrations:source_basis",
        "v4_person_profile",
        "talent_grade_calibrations",
        "source_basis",
        "mixed_han_latin",
        "source_basis ~ '[一-龥]' AND source_basis ~ '[A-Za-z]'",
    ),
    (
        "mixed_text:talent_grade_calibrations:review_basis",
        "v4_person_profile",
        "talent_grade_calibrations",
        "review_basis",
        "mixed_han_latin",
        "review_basis ~ '[一-龥]' AND review_basis ~ '[A-Za-z]'",
    ),
    (
        "mixed_text:episode_assertion_dispositions:reason",
        "public",
        "episode_assertion_dispositions",
        "reason",
        "mixed_han_latin",
        "reason ~ '[一-龥]' AND reason ~ '[A-Za-z]'",
    ),
    (
        "mixed_text:episode_assertion_dispositions:follow_up",
        "public",
        "episode_assertion_dispositions",
        "follow_up",
        "mixed_han_latin",
        "follow_up ~ '[一-龥]' AND follow_up ~ '[A-Za-z]'",
    ),
)


class SchemaQualityRegressionError(RuntimeError):
    pass


def migration_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "db"
        / "postgres"
        / "012_v4_schema_field_governance.sql"
    )


def _migration_sha256() -> str:
    payload = migration_path().read_bytes() + b"\0" + IDENTITY_RESOLVER_VERSION.encode()
    return sha256(payload).hexdigest()


def _inventory(cursor: Any) -> list[dict[str, str]]:
    cursor.execute(
        """
        SELECT n.nspname, c.relname, c.relkind, a.attname,
               pg_catalog.format_type(a.atttypid, a.atttypmod),
               CASE WHEN a.attnotnull THEN 'not_null' ELSE 'nullable' END
        FROM pg_catalog.pg_class AS c
        JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
        JOIN pg_catalog.pg_attribute AS a ON a.attrelid = c.oid
        WHERE n.nspname = ANY(%s)
          AND c.relkind IN ('r', 'p', 'v', 'm')
          AND c.relname NOT LIKE 'pg_%%'
          AND a.attnum > 0
          AND NOT a.attisdropped
        ORDER BY n.nspname, c.relname, a.attnum
        """,
        (list(TARGET_SCHEMAS),),
    )
    return [
        {
            "schema": str(row[0]),
            "relation": str(row[1]),
            "relation_kind": str(row[2]),
            "column": str(row[3]),
            "data_type": str(row[4]),
            "nullability": str(row[5]),
        }
        for row in cursor.fetchall()
    ]


def _inventory_sha256(inventory: Sequence[dict[str, str]]) -> str:
    payload = json.dumps(
        list(inventory), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def _comment_gaps(cursor: Any) -> list[dict[str, str]]:
    cursor.execute(
        """
        SELECT n.nspname, c.relname, '' AS column_name
        FROM pg_catalog.pg_class AS c
        JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = ANY(%s)
          AND c.relkind IN ('r', 'p', 'v', 'm')
          AND c.relname NOT LIKE 'pg_%%'
          AND NULLIF(btrim(COALESCE(obj_description(c.oid, 'pg_class'), '')), '') IS NULL
        UNION ALL
        SELECT n.nspname, c.relname, a.attname
        FROM pg_catalog.pg_class AS c
        JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
        JOIN pg_catalog.pg_attribute AS a ON a.attrelid = c.oid
        WHERE n.nspname = ANY(%s)
          AND c.relkind IN ('r', 'p', 'v', 'm')
          AND c.relname NOT LIKE 'pg_%%'
          AND a.attnum > 0
          AND NOT a.attisdropped
          AND NULLIF(btrim(COALESCE(col_description(c.oid, a.attnum), '')), '') IS NULL
        ORDER BY 1, 2, 3
        """,
        (list(TARGET_SCHEMAS), list(TARGET_SCHEMAS)),
    )
    return [
        {"schema": str(row[0]), "relation": str(row[1]), "column": str(row[2])}
        for row in cursor.fetchall()
    ]


def _state(cursor: Any) -> tuple[str, str] | None:
    cursor.execute("SELECT to_regclass('v4_governance.schema_migration_state')")
    if cursor.fetchone()[0] is None:
        return None
    cursor.execute(
        """
        SELECT migration_sha256, inventory_sha256
        FROM v4_governance.schema_migration_state
        WHERE migration_key = %s
        """,
        (MIGRATION_KEY,),
    )
    row = cursor.fetchone()
    return None if row is None else (str(row[0]), str(row[1]))


def _quality_metrics(cursor: Any) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    for (
        metric_key,
        schema_name,
        table_name,
        column_name,
        metric_kind,
        predicate,
    ) in QUALITY_METRIC_SPECS:
        cursor.execute("SELECT to_regclass(%s)", (f"{schema_name}.{table_name}",))
        if cursor.fetchone()[0] is None:
            continue
        if "v4_person_profile.person_identity_registry" in predicate:
            cursor.execute(
                "SELECT to_regclass('v4_person_profile.person_identity_registry')"
            )
            if cursor.fetchone()[0] is None:
                continue
        if "v4_governance.identity_reference_aliases" in predicate:
            cursor.execute(
                "SELECT to_regclass('v4_governance.identity_reference_aliases')"
            )
            if cursor.fetchone()[0] is None:
                continue
        cursor.execute(
            f'SELECT count(*) FROM "{schema_name}"."{table_name}" WHERE {predicate}'
        )
        metrics.append(
            {
                "metric_key": metric_key,
                "schema": schema_name,
                "table": table_name,
                "column": column_name,
                "metric_kind": metric_kind,
                "count": int(cursor.fetchone()[0]),
            }
        )
    return metrics


def _quality_baselines(cursor: Any) -> dict[str, int]:
    cursor.execute("SELECT to_regclass('v4_governance.field_quality_baselines')")
    if cursor.fetchone()[0] is None:
        return {}
    cursor.execute(
        "SELECT metric_key, baseline_count FROM v4_governance.field_quality_baselines"
    )
    return {str(row[0]): int(row[1]) for row in cursor.fetchall()}


def _upsert_quality_baselines(
    cursor: Any, metrics: Sequence[dict[str, Any]]
) -> None:
    for metric in metrics:
        cursor.execute(
            """
            INSERT INTO v4_governance.field_quality_baselines (
                metric_key, schema_name, table_name, column_name,
                metric_kind, baseline_count, measured_at
            ) VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (metric_key) DO UPDATE SET
                schema_name = EXCLUDED.schema_name,
                table_name = EXCLUDED.table_name,
                column_name = EXCLUDED.column_name,
                metric_kind = EXCLUDED.metric_kind,
                baseline_count = LEAST(
                    v4_governance.field_quality_baselines.baseline_count,
                    EXCLUDED.baseline_count
                ),
                measured_at = CASE
                    WHEN EXCLUDED.baseline_count <
                         v4_governance.field_quality_baselines.baseline_count
                    THEN EXCLUDED.measured_at
                    ELSE v4_governance.field_quality_baselines.measured_at
                END
            """,
            (
                metric["metric_key"],
                metric["schema"],
                metric["table"],
                metric["column"],
                metric["metric_kind"],
                metric["count"],
            ),
        )


def _refresh_identity_reference_aliases(cursor: Any) -> dict[str, int]:
    cursor.execute(
        "UPDATE v4_governance.identity_reference_aliases SET active = FALSE WHERE active"
    )
    rows: dict[str, dict[str, Any]] = {}

    cursor.execute("SELECT to_regclass('v4_person_profile.person_identity_registry')")
    profile_registry_exists = cursor.fetchone()[0] is not None
    if profile_registry_exists:
        cursor.execute(
            """
            SELECT person_ref, canonical_name
            FROM v4_person_profile.person_identity_registry
            WHERE identity_status = 'active'
            """
        )
        for person_ref, canonical_name in cursor.fetchall():
            rows[str(person_ref)] = {
                "reference_kind": "person_profile_identity",
                "resolution_status": "canonical",
                "canonical_ref": str(person_ref),
                "canonical_name": str(canonical_name),
                "basis_ref": "v4_person_profile.person_identity_registry",
                "source_priority": 100,
            }

    source_rows: dict[str, bool] = {}
    cursor.execute("SELECT to_regclass('public.episode_participants')")
    participants_exist = cursor.fetchone()[0] is not None
    if participants_exist:
        cursor.execute(
            """
            SELECT person_ref, bool_or(role_status = 'resolved')
            FROM public.episode_participants
            GROUP BY person_ref
            """
        )
        source_rows.update({str(row[0]): bool(row[1]) for row in cursor.fetchall()})
    cursor.execute("SELECT to_regclass('public.historical_episodes')")
    episodes_exist = cursor.fetchone()[0] is not None
    if episodes_exist:
        cursor.execute("SELECT DISTINCT evaluation_context FROM public.historical_episodes")
        for (source_ref,) in cursor.fetchall():
            source_rows.setdefault(str(source_ref), False)

    exact_name_matches: dict[str, tuple[str, str]] = {}
    if profile_registry_exists and source_rows:
        cursor.execute(
            """
            SELECT source.source_ref, min(r.person_ref), min(r.canonical_name)
            FROM unnest(%s::text[]) AS source(source_ref)
            JOIN v4_person_profile.person_identity_registry AS r
              ON r.canonical_name = source.source_ref
             AND r.identity_status = 'active'
            GROUP BY source.source_ref
            HAVING count(DISTINCT r.person_ref) = 1
            """,
            (list(source_rows),),
        )
        exact_name_matches = {
            str(row[0]): (str(row[1]), str(row[2])) for row in cursor.fetchall()
        }

    evidence_matches: dict[str, tuple[str, str, str]] = {}
    name_hints: dict[str, str] = {}
    if profile_registry_exists and participants_exist and episodes_exist:
        cursor.execute(
            """
            WITH linked AS (
                SELECT p.person_ref AS source_ref, p.role_code,
                       a.payload ->> 'subject' AS subject_name,
                       a.payload ->> 'object' AS object_name,
                       COALESCE(
                           a.payload #>> '{qualifiers,evaluation_context_name}',
                           a.payload #>> '{qualifiers,evaluation_context}'
                       ) AS ruler_name
                FROM public.episode_participants AS p
                JOIN public.historical_episodes AS e ON e.episode_id = p.episode_id
                JOIN public.episode_assertion_dispositions AS d
                  ON d.episode_id = e.episode_id
                 AND d.semantic_version = e.active_semantic_version
                 AND d.evidence_version = e.active_evidence_version
                JOIN public.assertions AS a ON a.assertion_id = d.assertion_id
            ), participant_candidates AS (
                SELECT DISTINCT linked.source_ref, r.person_ref, r.canonical_name,
                       CASE WHEN linked.role_code = 'ruler'
                            THEN 'assertion_evaluation_context_name'
                            ELSE 'assertion_subject_or_object_name' END AS basis_kind
                FROM linked
                JOIN v4_person_profile.person_identity_registry AS r
                  ON r.identity_status = 'active'
                 AND (
                     (linked.role_code = 'ruler' AND r.canonical_name = linked.ruler_name)
                     OR (
                         linked.role_code = 'actor'
                         AND r.canonical_name = linked.subject_name
                         AND r.canonical_name IS DISTINCT FROM linked.ruler_name
                     )
                     OR (
                         linked.role_code NOT IN ('ruler', 'actor')
                         AND r.canonical_name = linked.object_name
                         AND r.canonical_name IS DISTINCT FROM linked.ruler_name
                     )
                 )
            ), evaluation_context_candidates AS (
                SELECT DISTINCT e.evaluation_context AS source_ref,
                       r.person_ref, r.canonical_name,
                       'assertion_evaluation_context_name' AS basis_kind
                FROM public.historical_episodes AS e
                JOIN public.episode_assertion_dispositions AS d
                  ON d.episode_id = e.episode_id
                 AND d.semantic_version = e.active_semantic_version
                 AND d.evidence_version = e.active_evidence_version
                JOIN public.assertions AS a ON a.assertion_id = d.assertion_id
                JOIN v4_person_profile.person_identity_registry AS r
                  ON r.identity_status = 'active'
                 AND r.canonical_name = COALESCE(
                     a.payload #>> '{qualifiers,evaluation_context_name}',
                     a.payload #>> '{qualifiers,evaluation_context}'
                 )
            ), candidates AS (
                SELECT * FROM participant_candidates
                UNION
                SELECT * FROM evaluation_context_candidates
            )
            SELECT source_ref, min(person_ref), min(canonical_name), min(basis_kind)
            FROM candidates
            GROUP BY source_ref
            HAVING count(DISTINCT person_ref) = 1
            """
        )
        evidence_matches = {
            str(row[0]): (str(row[1]), str(row[2]), str(row[3]))
            for row in cursor.fetchall()
        }
        cursor.execute(
            """
            WITH hints AS (
                SELECT e.evaluation_context AS source_ref,
                       COALESCE(
                           a.payload #>> '{qualifiers,evaluation_context_name}',
                           a.payload #>> '{qualifiers,evaluation_context}'
                       ) AS name_hint
                FROM public.historical_episodes AS e
                JOIN public.episode_assertion_dispositions AS d
                  ON d.episode_id = e.episode_id
                 AND d.semantic_version = e.active_semantic_version
                 AND d.evidence_version = e.active_evidence_version
                JOIN public.assertions AS a ON a.assertion_id = d.assertion_id
            )
            SELECT source_ref, min(name_hint)
            FROM hints
            WHERE name_hint IS NOT NULL AND name_hint <> ''
            GROUP BY source_ref
            HAVING count(DISTINCT name_hint) = 1
            """
        )
        name_hints = {str(row[0]): str(row[1]) for row in cursor.fetchall()}

    canonical_pattern = re.compile(r"^[A-Z][A-Z0-9]*(-[A-Z0-9]+)+$")
    for source_ref, has_resolved_role in source_rows.items():
        if source_ref in rows:
            continue
        canonical_ref: str | None = None
        canonical_name: str | None = name_hints.get(source_ref)
        if "-GROUP-CANDIDATE-" in source_ref or source_ref.endswith("使者"):
            kind = "non_person_context"
            status = "non_person"
            basis_ref = "field-governance:non-person-participant-v1"
            priority = 70
        elif "-NAME-CANDIDATE-" in source_ref:
            kind = "name_candidate"
            status = "candidate"
            basis_ref = "field-governance:candidate-prefix-v1"
            priority = 50
        elif canonical_pattern.fullmatch(source_ref) and has_resolved_role:
            canonical_ref = source_ref
            kind = "episode_domain_identity"
            status = "canonical"
            basis_ref = "public.episode_participants:resolved-role"
            priority = 60
        elif source_ref in evidence_matches:
            canonical_ref, canonical_name, basis_kind = evidence_matches[source_ref]
            kind = "evidence_resolved_alias"
            status = "alias"
            basis_ref = f"field-governance:{basis_kind}:v1"
            priority = 90
        elif source_ref in exact_name_matches:
            canonical_ref, canonical_name = exact_name_matches[source_ref]
            kind = "canonical_name_alias"
            status = "alias"
            basis_ref = "field-governance:unique-canonical-name-match-v1"
            priority = 80
        else:
            kind = "legacy_or_display_value"
            status = "unresolved"
            basis_ref = "field-governance:requires-identity-review-v1"
            priority = 10
        rows[source_ref] = {
            "reference_kind": kind,
            "resolution_status": status,
            "canonical_ref": canonical_ref,
            "canonical_name": canonical_name,
            "basis_ref": basis_ref,
            "source_priority": priority,
        }

    for source_ref, row in rows.items():
        cursor.execute(
            """
            INSERT INTO v4_governance.identity_reference_aliases (
                source_ref, reference_kind, resolution_status, canonical_ref,
                canonical_name, basis_ref, source_priority, active, observed_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, CURRENT_TIMESTAMP)
            ON CONFLICT (source_ref) DO UPDATE SET
                reference_kind = EXCLUDED.reference_kind,
                resolution_status = EXCLUDED.resolution_status,
                canonical_ref = EXCLUDED.canonical_ref,
                canonical_name = EXCLUDED.canonical_name,
                basis_ref = EXCLUDED.basis_ref,
                source_priority = EXCLUDED.source_priority,
                active = TRUE,
                observed_at = EXCLUDED.observed_at
            """,
            (
                source_ref,
                row["reference_kind"],
                row["resolution_status"],
                row["canonical_ref"],
                row["canonical_name"],
                row["basis_ref"],
                row["source_priority"],
            ),
        )
    counts: dict[str, int] = {}
    for row in rows.values():
        status = str(row["resolution_status"])
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def _identity_alias_counts(cursor: Any) -> dict[str, int]:
    cursor.execute("SELECT to_regclass('v4_governance.identity_reference_aliases')")
    if cursor.fetchone()[0] is None:
        return {}
    cursor.execute(
        """
        SELECT resolution_status, count(*)
        FROM v4_governance.identity_reference_aliases
        WHERE active
        GROUP BY resolution_status
        ORDER BY resolution_status
        """
    )
    return {str(row[0]): int(row[1]) for row in cursor.fetchall()}


def _refresh_legacy_value_dispositions(cursor: Any) -> list[dict[str, Any]]:
    cursor.execute("UPDATE v4_governance.legacy_value_dispositions SET active = FALSE WHERE active")
    cursor.execute(
        """
        SELECT source_ref, resolution_status, canonical_ref, basis_ref
        FROM v4_governance.identity_reference_aliases
        WHERE active
        """
    )
    aliases = {
        str(row[0]): {
            "resolution_status": str(row[1]),
            "canonical_ref": None if row[2] is None else str(row[2]),
            "basis_ref": str(row[3]),
        }
        for row in cursor.fetchall()
    }
    probes = (
        (
            "noncanonical_participant_ref",
            """
            SELECT p.person_ref, count(*), match.person_ref
            FROM public.episode_participants AS p
            LEFT JOIN LATERAL (
                SELECT min(r.person_ref) AS person_ref
                FROM v4_person_profile.person_identity_registry AS r
                WHERE r.canonical_name = p.person_ref
                HAVING count(*) = 1
            ) AS match ON TRUE
            WHERE p.person_ref !~ '^[A-Z][A-Z0-9]*(-[A-Z0-9]+)+$'
            GROUP BY p.person_ref, match.person_ref
            """,
            "public",
            "episode_participants",
            "person_ref",
        ),
        (
            "cross_namespace_participant_ref",
            """
            SELECT p.person_ref, count(*), match.person_ref
            FROM public.episode_participants AS p
            LEFT JOIN LATERAL (
                SELECT min(r.person_ref) AS person_ref
                FROM v4_person_profile.person_identity_registry AS r
                WHERE r.canonical_name = p.person_ref
                HAVING count(*) = 1
            ) AS match ON TRUE
            WHERE NOT EXISTS (
                SELECT 1 FROM v4_person_profile.person_identity_registry AS registered
                WHERE registered.person_ref = p.person_ref
            )
            GROUP BY p.person_ref, match.person_ref
            """,
            "public",
            "episode_participants",
            "person_ref",
        ),
        (
            "noncanonical_evaluation_context",
            """
            SELECT e.evaluation_context, count(*), match.person_ref
            FROM public.historical_episodes AS e
            LEFT JOIN LATERAL (
                SELECT min(r.person_ref) AS person_ref
                FROM v4_person_profile.person_identity_registry AS r
                WHERE r.canonical_name = e.evaluation_context
                HAVING count(*) = 1
            ) AS match ON TRUE
            WHERE e.evaluation_context !~ '^[A-Z][A-Z0-9]*(-[A-Z0-9]+)+$'
            GROUP BY e.evaluation_context, match.person_ref
            """,
            "public",
            "historical_episodes",
            "evaluation_context",
        ),
    )
    summary: list[dict[str, Any]] = []
    for issue_code, query, schema_name, table_name, column_name in probes:
        cursor.execute("SELECT to_regclass(%s)", (f"{schema_name}.{table_name}",))
        if cursor.fetchone()[0] is None:
            continue
        if "v4_person_profile" in query:
            cursor.execute(
                "SELECT to_regclass('v4_person_profile.person_identity_registry')"
            )
            if cursor.fetchone()[0] is None:
                continue
        cursor.execute(query)
        rows = cursor.fetchall()
        for legacy_value, occurrence_count, canonical_value in rows:
            legacy_text = str(legacy_value)
            alias = aliases.get(legacy_text)
            classification = (
                str(alias["resolution_status"]) if alias else "unresolved"
            )
            resolved_target = (
                alias["canonical_ref"] if alias and alias["canonical_ref"] else canonical_value
            )
            disposition = "canonical_target" if resolved_target else "quarantined"
            basis = (
                f"跨域身份解析：{alias['basis_ref']}。"
                if alias
                else "未找到唯一规范身份；保留历史值并阻断新增写入。"
            )
            cursor.execute(
                """
                INSERT INTO v4_governance.legacy_value_dispositions (
                    issue_code, schema_name, table_name, column_name,
                    legacy_value_sha256, legacy_value, occurrence_count,
                    disposition, canonical_value, basis, classification,
                    active, observed_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, CURRENT_TIMESTAMP)
                ON CONFLICT (issue_code, legacy_value_sha256) DO UPDATE SET
                    occurrence_count = EXCLUDED.occurrence_count,
                    disposition = EXCLUDED.disposition,
                    canonical_value = EXCLUDED.canonical_value,
                    basis = EXCLUDED.basis,
                    classification = EXCLUDED.classification,
                    active = TRUE,
                    observed_at = EXCLUDED.observed_at
                """,
                (
                    issue_code,
                    schema_name,
                    table_name,
                    column_name,
                    sha256(legacy_text.encode("utf-8")).hexdigest(),
                    legacy_text,
                    int(occurrence_count),
                    disposition,
                    resolved_target,
                    basis,
                    classification,
                ),
            )
        summary.append(
            {
                "issue_code": issue_code,
                "distinct_value_count": len(rows),
                "canonical_target_count": sum(
                    1
                    for row in rows
                    if aliases.get(str(row[0]), {}).get("canonical_ref") or row[2]
                ),
                "quarantined_count": sum(
                    1
                    for row in rows
                    if not aliases.get(str(row[0]), {}).get("canonical_ref")
                    and not row[2]
                ),
            }
        )
    return summary


def ensure_schema_governance(cursor: Any) -> dict[str, Any]:
    migration_sha = _migration_sha256()
    before_inventory = _inventory(cursor)
    before_inventory_sha = _inventory_sha256(before_inventory)
    gaps_before = _comment_gaps(cursor)
    state = _state(cursor)
    quality_before = _quality_metrics(cursor)
    baselines = _quality_baselines(cursor)
    regressions = [
        {**metric, "baseline_count": baselines[metric["metric_key"]]}
        for metric in quality_before
        if metric["metric_key"] in baselines
        and metric["count"] > baselines[metric["metric_key"]]
    ]
    if regressions:
        raise SchemaQualityRegressionError(
            f"field quality baseline regression: {regressions}"
        )
    baseline_refresh = any(
        metric["metric_key"] not in baselines
        or metric["count"] < baselines[metric["metric_key"]]
        for metric in quality_before
    )
    if (
        state == (migration_sha, before_inventory_sha)
        and not gaps_before
        and not baseline_refresh
    ):
        return {
            "action": "reused",
            "database_write_count": 0,
            "migration_sha256": migration_sha,
            "inventory_sha256": before_inventory_sha,
            "relation_count": len(
                {(item["schema"], item["relation"]) for item in before_inventory}
            ),
            "column_count": len(before_inventory),
            "comment_gap_count": 0,
            "quality_metrics": quality_before,
            "identity_reference_aliases": _identity_alias_counts(cursor),
        }

    cursor.execute(migration_path().read_text(encoding="utf-8"))
    after_inventory = _inventory(cursor)
    after_inventory_sha = _inventory_sha256(after_inventory)
    gaps_after = _comment_gaps(cursor)
    identity_alias_summary = _refresh_identity_reference_aliases(cursor)
    quality_after = _quality_metrics(cursor)
    _upsert_quality_baselines(cursor, quality_after)
    disposition_summary = _refresh_legacy_value_dispositions(cursor)
    report = {
        "schema_version": MIGRATION_KEY,
        "migration_sha256": migration_sha,
        "inventory_sha256": after_inventory_sha,
        "relation_count": len(
            {(item["schema"], item["relation"]) for item in after_inventory}
        ),
        "column_count": len(after_inventory),
        "comment_gap_count": len(gaps_after),
        "quality_metrics": quality_after,
        "identity_reference_aliases": identity_alias_summary,
        "legacy_value_dispositions": disposition_summary,
    }
    cursor.execute(
        """
        INSERT INTO v4_governance.schema_migration_state (
            migration_key, migration_sha256, inventory_sha256, report, applied_at
        ) VALUES (%s, %s, %s, %s::jsonb, CURRENT_TIMESTAMP)
        ON CONFLICT (migration_key) DO UPDATE SET
            migration_sha256 = EXCLUDED.migration_sha256,
            inventory_sha256 = EXCLUDED.inventory_sha256,
            report = EXCLUDED.report,
            applied_at = EXCLUDED.applied_at
        """,
        (MIGRATION_KEY, migration_sha, after_inventory_sha, json.dumps(report)),
    )
    if gaps_after:
        raise RuntimeError(f"schema comments remain incomplete: {gaps_after[:5]}")
    return {"action": "applied", "database_write_count": 1, **report}


def _debt_counts(cursor: Any) -> list[dict[str, Any]]:
    probes = (
        (
            "noncanonical_participant_ref",
            "public",
            "episode_participants",
            "person_ref",
            "person_ref !~ '^[A-Z][A-Z0-9]*(-[A-Z0-9]+)+$'",
        ),
        (
            "unresolved_participant_ref",
            "public",
            "episode_participants",
            "person_ref",
            "NOT EXISTS (SELECT 1 FROM v4_governance.identity_reference_aliases r WHERE r.source_ref = episode_participants.person_ref AND r.active AND r.resolution_status IN ('canonical', 'alias'))",
        ),
        (
            "noncanonical_evaluation_context",
            "public",
            "historical_episodes",
            "evaluation_context",
            "evaluation_context !~ '^[A-Z][A-Z0-9]*(-[A-Z0-9]+)+$'",
        ),
    )
    result: list[dict[str, Any]] = []
    for issue_code, schema_name, table_name, column_name, predicate in probes:
        cursor.execute("SELECT to_regclass(%s)", (f"{schema_name}.{table_name}",))
        if cursor.fetchone()[0] is None:
            continue
        if issue_code == "unresolved_participant_ref":
            cursor.execute(
                "SELECT to_regclass('v4_governance.identity_reference_aliases')"
            )
            if cursor.fetchone()[0] is None:
                continue
        cursor.execute(
            f'SELECT count(*) FROM "{schema_name}"."{table_name}" WHERE {predicate}'
        )
        result.append(
            {
                "issue_code": issue_code,
                "schema": schema_name,
                "table": table_name,
                "column": column_name,
                "row_count": int(cursor.fetchone()[0]),
                "policy": "historical_debt_new_writes_blocked",
            }
        )
    return result


def run_schema_governance(dsn: str, *, dry_run: bool) -> dict[str, Any]:
    if not dsn.strip():
        raise ValueError("schema governance requires an explicit V4 DSN")
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("schema governance requires psycopg") from exc

    with psycopg.connect(dsn) as connection:
        with connection.cursor() as cursor:
            if dry_run:
                inventory = _inventory(cursor)
                migration_sha = _migration_sha256()
                inventory_sha = _inventory_sha256(inventory)
                gaps = _comment_gaps(cursor)
                state = _state(cursor)
                governance = {
                    "action": (
                        "reuse"
                        if state == (migration_sha, inventory_sha) and not gaps
                        else "would_apply"
                    ),
                    "database_write_count": 0,
                    "migration_sha256": migration_sha,
                    "inventory_sha256": inventory_sha,
                    "relation_count": len(
                        {(item["schema"], item["relation"]) for item in inventory}
                    ),
                    "column_count": len(inventory),
                    "comment_gap_count": len(gaps),
                    "quality_metrics": _quality_metrics(cursor),
                }
            else:
                governance = ensure_schema_governance(cursor)
            debt = _debt_counts(cursor)
    return {
        "schema_version": "v4-schema-field-governance-run-v1",
        "dry_run": dry_run,
        "governance": governance,
        "historical_debt": debt,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        from dotenv import load_dotenv
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("schema governance CLI requires python-dotenv") from exc
    load_dotenv(args.env_file)
    dsn = os.environ.get("EMPEROR_EVAL_V4_DSN", "")
    report = run_schema_governance(dsn, dry_run=not args.apply)
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
