from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any, Sequence
import unicodedata


MIGRATION_KEY = "v4-schema-field-governance-v1"
IDENTITY_RESOLVER_VERSION = "physical-event-identity-backfill-v5"
FIELD_NORMALIZATION_VERSION = "full-physical-field-normalization-v1"
_TEXT_REPLACEMENTS = {
    "allowed_talent_grades": "允许的人才等级",
    "authority_evaluations": "权威评价",
    "performance_support": "绩效支持",
    "field_representative": "领域代表成果",
    "evidence_claims": "证据断言",
    "evidence_claim": "证据断言",
    "important_talent": "重要人才",
    "ordinary_talent": "普通人才",
    "historic_talent": "历史级人才",
    "usable_talent": "可用人才",
    "talent-grade-v5": "人才等级第五版",
    "source_snapshot": "来源快照",
    "top_talent": "顶级人才",
    "comprehensive": "全面",
    "substantial": "充分",
    "workitem": "工作项",
    "promotion": "晋级",
    "important": "重要人才",
    "historic": "历史级人才",
    "ordinary": "普通人才",
    "coverage": "覆盖度",
    "confidence": "置信度",
    "consensus": "共识",
    "authority": "权威评价",
    "evidence": "证据",
    "disputed": "有争议",
    "moderate": "中等",
    "partial": "部分",
    "usable": "可用人才",
    "rubric": "规则标尺",
    "claims": "证据断言",
    "claim": "证据断言",
    "primary": "主要",
    "path": "路径",
    "weak": "较弱",
    "top": "顶级人才",
    "V9": "第九版",
    "V8": "第八版",
    "V7": "第七版",
    "V6": "第六版",
    "v5": "第五版",
}
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
        "NOT EXISTS (SELECT 1 FROM v4_person_profile.person_identity_registry p WHERE p.person_ref = episode_participants.person_ref) AND NOT EXISTS (SELECT 1 FROM v4_governance.identity_reference_aliases r WHERE r.source_ref = episode_participants.person_ref AND r.active AND r.resolution_status IN ('canonical', 'alias'))",
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


def canonical_hashed_ref(prefix: str, value: object, *, length: int = 16) -> str:
    rendered = unicodedata.normalize("NFKC", str(value).strip())
    if not rendered:
        raise ValueError(f"{prefix} canonical reference requires a source value")
    canonical_pattern = re.compile(
        rf"^{re.escape(prefix)}-[0-9A-F]{{{length}}}$"
    )
    if canonical_pattern.fullmatch(rendered):
        return rendered
    digest = sha256(rendered.encode("utf-8")).hexdigest()[:length].upper()
    return f"{prefix}-{digest}"


def canonical_assertion_id(value: object) -> str:
    return canonical_hashed_ref("AST-V4", value, length=20)


def canonical_section_id(value: object) -> str:
    return canonical_hashed_ref("SEC-V4", value)


def canonical_import_batch_id(value: object) -> str:
    return canonical_hashed_ref("V4PP-BATCH", value)


def canonical_freeze_ref(value: object) -> str:
    return canonical_hashed_ref("FRZ-V4", value)


def canonical_source_profile_ref(value: object) -> str:
    return canonical_hashed_ref("SPR-V4", value)


def canonical_person_ref(value: object) -> str:
    rendered = str(value).strip()
    candidate = re.fullmatch(r"RULER-NAME-CANDIDATE-([0-9A-F]{12})", rendered)
    if candidate:
        return f"PER-V4-{candidate.group(1)}"
    fixed = {
        "PER-LI-SHIMIN": "PER-V4-737E2C4D60AC",
        "PER-V4-78F48EBC67F8": "PER-V4-737E2C4D60AC",
        "per-4eb7ac987fecc59f": "PER-V4-4EB7AC987FEC",
        "per-e15c1b65f12f0ae6": "PER-V4-E15C1B65F12F",
        "杨广": "PER-V4-C93016BB741A",
        "胡亥": "PER-V4-75EF40579300",
        "PER-FANG-XUANLING": "PER-V4-C37ED24688F5",
        "PER-V4-1EA22CE7B00F": "PER-V4-8DE3F5E45B1D",
        "PER-V4-DDEC62284B91": "PER-V4-620AF1EC07C0",
        "PER-V4-19A7D9A17D2F": "PER-V4-B0E10D8903E7",
        "PER-V4-7CF98C73F205": "PER-V4-89C0D231C76C",
        "PER-NAME-CANDIDATE-CHANGSUN-WUJI": "PER-V4-839C5A8CB43C",
        "PER-NAME-CANDIDATE-FANG-YIAI": "PER-V4-B3237391DC6C",
        "PER-NAME-CANDIDATE-HOU-JUNJI": "PER-V4-BBB439491EC7",
        "PER-NAME-CANDIDATE-LI-DAOYU": "PER-V4-D1A161DEDA40",
        "PER-NAME-CANDIDATE-LI-YOULIANG": "PER-V4-7B0F18DD6A7E",
        "PER-NAME-CANDIDATE-WANG-GUI": "PER-V4-6CAF227D2D39",
        "PER-NAME-CANDIDATE-ZHANG-XUANSU": "PER-V4-429CE79493C8",
        "PER-GROUP-CANDIDATE-LI-ROYAL-KIN": "GRP-V4-6D9014C97B41",
        "PER-GROUP-CANDIDATE-QINFU-OLD-FOLLOWERS": "GRP-V4-68FC831D2408",
        "obj-2b89622cefdec6e3": "PER-V4-6B644ADA6B87",
        "obj-485798d73c4c10dd": "PER-V4-B248DFDEACE7",
        "obj-a4785b7cc76ec776": "PER-V4-D7FBC6D47CAE",
        "per-90d341e561ef23dd": "PER-V4-E15C1B65F12F",
        "per-d7a0d148728a2905": "PER-V4-D7A0D148728A",
        "二世": "PER-V4-75EF40579300",
        "二世使者": "GRP-V4-3169839A92A8",
        "叔孙通": "PER-V4-6F877F064B0B",
        "屈突通": "PER-V4-C1923EA6B469",
        "李斯": "PER-V4-A18E9558AE21",
        "炀帝": "PER-V4-C93016BB741A",
        "胡亥使者": "GRP-V4-CBD654AFB735",
        "萧瑀": "PER-V4-B817E6DF722E",
        "隋炀帝": "PER-V4-C93016BB741A",
    }
    return fixed.get(rendered, rendered)


def normalize_chinese_explanatory_text(value: object) -> str:
    rendered = str(value).strip()
    for source, target in sorted(
        _TEXT_REPLACEMENTS.items(), key=lambda item: len(item[0]), reverse=True
    ):
        rendered = re.sub(
            rf"(?<![A-Za-z0-9_]){re.escape(source)}(?![A-Za-z0-9_])",
            target,
            rendered,
        )
    if re.search(r"[一-龥]", rendered) and re.search(r"[A-Za-z]", rendered):
        tokens = sorted(set(re.findall(r"[A-Za-z][A-Za-z0-9_-]*", rendered)))
        raise ValueError(f"说明文本仍含未治理英文锚点: {tokens}")
    return rendered


def _migration_sha256() -> str:
    payload = (
        migration_path().read_bytes()
        + b"\0"
        + IDENTITY_RESOLVER_VERSION.encode()
        + b"\0"
        + FIELD_NORMALIZATION_VERSION.encode()
    )
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


def _apply_physical_identity_backfill(cursor: Any) -> dict[str, int]:
    cursor.execute(
        """
        SELECT target_ref, min(canonical_name),
               jsonb_agg(DISTINCT basis_ref ORDER BY basis_ref)
        FROM v4_governance.identity_reference_backfill_map
        WHERE active AND participant_kind = 'person'
        GROUP BY target_ref
        ORDER BY target_ref
        """
    )
    inserted_identities = 0
    for target_ref, canonical_name, basis_refs in cursor.fetchall():
        fingerprint = sha256(
            f"field-governance-identity-v1|{target_ref}|{canonical_name}".encode(
                "utf-8"
            )
        ).hexdigest()
        cursor.execute(
            """
            INSERT INTO v4_person_profile.person_identity_registry (
                person_ref, canonical_name, historical_context,
                identity_fingerprint, identity_status, semantic_version,
                supersedes_person_ref, idempotency_key, import_batch_id,
                payload, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, 'active', 1, NULL, %s, NULL,
                jsonb_build_object(
                    'source', 'v4-schema-field-governance',
                    'basis_refs', %s::jsonb,
                    'physical_backfill', TRUE
                ),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            ON CONFLICT (person_ref) DO NOTHING
            """,
            (
                target_ref,
                canonical_name,
                "公共事件域身份引用物理归一化",
                fingerprint,
                f"field-governance-identity-v1:{target_ref}",
                json.dumps(basis_refs, ensure_ascii=False),
            ),
        )
        inserted_identities += max(int(cursor.rowcount), 0)

    cursor.execute(
        """
        UPDATE v4_governance.identity_reference_backfill_map AS m
        SET source_row_count = source.count,
            applied_row_count = source.count,
            duplicate_row_count = 0,
            applied_at = CURRENT_TIMESTAMP
        FROM (
            SELECT m2.source_ref, count(e.episode_id)::integer AS count
            FROM v4_governance.identity_reference_backfill_map AS m2
            LEFT JOIN public.historical_episodes AS e
              ON e.evaluation_context = m2.source_ref
            WHERE m2.active AND m2.reference_domain = 'evaluation_context'
            GROUP BY m2.source_ref
        ) AS source
        WHERE m.reference_domain = 'evaluation_context'
          AND m.source_ref = source.source_ref
        """
    )
    cursor.execute(
        """
        UPDATE public.historical_episodes AS e
        SET evaluation_context = m.target_ref,
            updated_at = CURRENT_TIMESTAMP
        FROM v4_governance.identity_reference_backfill_map AS m
        WHERE m.active
          AND m.reference_domain = 'evaluation_context'
          AND e.evaluation_context = m.source_ref
          AND e.evaluation_context IS DISTINCT FROM m.target_ref
        """
    )
    episode_rows_updated = max(int(cursor.rowcount), 0)

    cursor.execute(
        """
        CREATE TEMP TABLE governance_participant_projection
        ON COMMIT DROP AS
        SELECT p.ctid AS row_id, p.episode_id, p.semantic_version,
               p.person_ref AS source_ref, p.role_code,
               COALESCE(m.target_ref, p.person_ref) AS target_ref,
               row_number() OVER (
                   PARTITION BY p.episode_id, p.semantic_version,
                                COALESCE(m.target_ref, p.person_ref), p.role_code
                   ORDER BY (m.target_ref IS NULL), p.person_ref, p.ctid
               ) AS duplicate_rank
        FROM public.episode_participants AS p
        LEFT JOIN v4_governance.identity_reference_backfill_map AS m
          ON m.active
         AND m.reference_domain = 'participant_ref'
         AND m.source_ref = p.person_ref
        """
    )
    cursor.execute(
        """
        UPDATE v4_governance.identity_reference_backfill_map AS m
        SET source_row_count = source.source_count,
            applied_row_count = source.source_count - source.duplicate_count,
            duplicate_row_count = source.duplicate_count,
            applied_at = CURRENT_TIMESTAMP
        FROM (
            SELECT source_ref, count(*)::integer AS source_count,
                   count(*) FILTER (WHERE duplicate_rank > 1)::integer
                       AS duplicate_count
            FROM governance_participant_projection
            WHERE source_ref IS DISTINCT FROM target_ref
            GROUP BY source_ref
        ) AS source
        WHERE m.active
          AND m.reference_domain = 'participant_ref'
          AND m.source_ref = source.source_ref
        """
    )
    cursor.execute(
        """
        DELETE FROM public.episode_participants AS p
        USING governance_participant_projection AS projected
        WHERE p.ctid = projected.row_id
          AND projected.duplicate_rank > 1
        """
    )
    duplicate_rows_removed = max(int(cursor.rowcount), 0)
    cursor.execute(
        """
        UPDATE public.episode_participants AS p
        SET person_ref = m.target_ref,
            role_status = 'resolved'
        FROM v4_governance.identity_reference_backfill_map AS m
        WHERE m.active
          AND m.reference_domain = 'participant_ref'
          AND p.person_ref = m.source_ref
          AND p.person_ref IS DISTINCT FROM m.target_ref
        """
    )
    participant_rows_updated = max(int(cursor.rowcount), 0)

    cursor.execute(
        """
        ALTER TABLE public.episode_participants
            VALIDATE CONSTRAINT episode_participants_canonical_person_ref_check;
        ALTER TABLE public.episode_participants
            VALIDATE CONSTRAINT episode_participants_no_candidate_ref_check;
        ALTER TABLE public.historical_episodes
            VALIDATE CONSTRAINT historical_episodes_canonical_evaluation_context_check;
        """
    )
    return {
        "canonical_identities_inserted": inserted_identities,
        "historical_episode_rows_updated": episode_rows_updated,
        "episode_participant_rows_updated": participant_rows_updated,
        "duplicate_participant_rows_removed": duplicate_rows_removed,
    }


def _stable_json_hash(value: object) -> str:
    rendered = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(rendered.encode("utf-8")).hexdigest()


def _record_field_backfill(
    cursor: Any,
    *,
    schema_name: str,
    table_name: str,
    column_name: str,
    source_value: str,
    target_value: str,
    normalization_kind: str,
    source_row_count: int,
    applied_row_count: int,
) -> None:
    cursor.execute(
        """
        INSERT INTO v4_governance.field_value_backfill_map (
            schema_name, table_name, column_name, source_value_sha256,
            source_value, target_value, normalization_kind,
            normalization_version, source_row_count, applied_row_count,
            applied_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (schema_name, table_name, column_name, source_value_sha256)
        DO UPDATE SET
            target_value = EXCLUDED.target_value,
            normalization_kind = EXCLUDED.normalization_kind,
            normalization_version = EXCLUDED.normalization_version,
            source_row_count = EXCLUDED.source_row_count,
            applied_row_count = EXCLUDED.applied_row_count,
            applied_at = EXCLUDED.applied_at
        """,
        (
            schema_name,
            table_name,
            column_name,
            sha256(source_value.encode("utf-8")).hexdigest(),
            source_value,
            target_value,
            normalization_kind,
            FIELD_NORMALIZATION_VERSION,
            source_row_count,
            applied_row_count,
        ),
    )


def _normalize_reference_column(
    cursor: Any,
    *,
    schema_name: str,
    table_name: str,
    column_name: str,
    canonicalizer: Any,
    normalization_kind: str,
) -> int:
    cursor.execute(
        f'SELECT "{column_name}", count(*) FROM "{schema_name}"."{table_name}" '
        f'WHERE "{column_name}" IS NOT NULL GROUP BY "{column_name}"'
    )
    values = [(str(value), int(count)) for value, count in cursor.fetchall()]
    writes = 0
    for source_value, source_count in values:
        target_value = str(canonicalizer(source_value))
        if source_value == target_value:
            continue
        cursor.execute(
            f'UPDATE "{schema_name}"."{table_name}" '
            f'SET "{column_name}" = %s WHERE "{column_name}" = %s',
            (target_value, source_value),
        )
        applied = max(int(cursor.rowcount), 0)
        writes += applied
        _record_field_backfill(
            cursor,
            schema_name=schema_name,
            table_name=table_name,
            column_name=column_name,
            source_value=source_value,
            target_value=target_value,
            normalization_kind=normalization_kind,
            source_row_count=source_count,
            applied_row_count=applied,
        )
    return writes


def _normalize_assertion_ids(cursor: Any) -> int:
    cursor.execute(
        """
        SELECT assertion_id, source_passage_id, assertion_type,
               assertion_semantic_key, payload, created_at
        FROM public.assertions
        ORDER BY assertion_id
        """
    )
    rows = cursor.fetchall()
    writes = 0
    for source_id, passage_id, assertion_type, semantic_key, payload, created_at in rows:
        source_text = str(source_id)
        target_id = canonical_assertion_id(source_text)
        if source_text == target_id:
            continue
        cursor.execute(
            """
            INSERT INTO public.assertions (
                assertion_id, source_passage_id, assertion_type,
                assertion_semantic_key, payload, created_at
            ) VALUES (%s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (assertion_id) DO NOTHING
            """,
            (
                target_id,
                passage_id,
                assertion_type,
                semantic_key,
                json.dumps(payload, ensure_ascii=False),
                created_at,
            ),
        )
        cursor.execute(
            """
            UPDATE public.episode_assertion_dispositions
            SET assertion_id = %s
            WHERE assertion_id = %s
            """,
            (target_id, source_text),
        )
        cursor.execute(
            "DELETE FROM public.assertions WHERE assertion_id = %s",
            (source_text,),
        )
        writes += 1
        _record_field_backfill(
            cursor,
            schema_name="public",
            table_name="assertions",
            column_name="assertion_id",
            source_value=source_text,
            target_value=target_id,
            normalization_kind="canonical_assertion_id",
            source_row_count=1,
            applied_row_count=1,
        )
    return writes


def _normalize_import_batches(cursor: Any) -> tuple[int, int]:
    cursor.execute(
        """
        SELECT import_batch_id, idempotency_key, source_system,
               source_freeze_ref, source_package_fingerprint,
               contract_version, status, legacy_numeric_id_reused,
               database_write_mode, payload, created_at
        FROM v4_person_profile.import_batches
        ORDER BY import_batch_id
        """
    )
    rows = cursor.fetchall()
    batch_writes = 0
    freeze_writes = 0
    child_tables = (
        "person_identity_registry",
        "person_legacy_refs",
        "person_profile_snapshots",
        "person_profile_catalog",
        "ruler_team_window_snapshots",
        "talent_grade_calibrations",
    )
    for row in rows:
        source_id = str(row[0])
        target_id = canonical_import_batch_id(source_id)
        source_freeze = str(row[3])
        target_freeze = canonical_freeze_ref(source_freeze)
        if source_id == target_id and source_freeze == target_freeze:
            continue
        payload = dict(row[9])
        if "import_batch_id" in payload:
            payload["import_batch_id"] = target_id
        if "source_freeze_ref" in payload:
            payload["source_freeze_ref"] = target_freeze
        cursor.execute(
            """
            INSERT INTO v4_person_profile.import_batches (
                import_batch_id, idempotency_key, source_system,
                source_freeze_ref, source_package_fingerprint,
                contract_version, status, legacy_numeric_id_reused,
                database_write_mode, payload, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (import_batch_id) DO NOTHING
            """,
            (
                target_id,
                f"field-normalized:{target_id}",
                row[2],
                target_freeze,
                row[4],
                row[5],
                row[6],
                row[7],
                row[8],
                json.dumps(payload, ensure_ascii=False),
                row[10],
            ),
        )
        for table_name in child_tables:
            cursor.execute(
                f'UPDATE v4_person_profile."{table_name}" '
                'SET import_batch_id = %s WHERE import_batch_id = %s',
                (target_id, source_id),
            )
        cursor.execute(
            "DELETE FROM v4_person_profile.import_batches WHERE import_batch_id = %s",
            (source_id,),
        )
        batch_writes += 1
        freeze_writes += int(source_freeze != target_freeze)
        _record_field_backfill(
            cursor,
            schema_name="v4_person_profile",
            table_name="import_batches",
            column_name="import_batch_id",
            source_value=source_id,
            target_value=target_id,
            normalization_kind="canonical_import_batch_id",
            source_row_count=1,
            applied_row_count=1,
        )
        _record_field_backfill(
            cursor,
            schema_name="v4_person_profile",
            table_name="import_batches",
            column_name="source_freeze_ref",
            source_value=source_freeze,
            target_value=target_freeze,
            normalization_kind="canonical_freeze_ref",
            source_row_count=1,
            applied_row_count=int(source_freeze != target_freeze),
        )
    return batch_writes, freeze_writes


def _normalize_candidate_identities(cursor: Any) -> int:
    cursor.execute(
        """
        SELECT person_ref, canonical_name, historical_context,
               identity_fingerprint, identity_status, semantic_version,
               supersedes_person_ref, idempotency_key, import_batch_id,
               payload, created_at, updated_at
        FROM v4_person_profile.person_identity_registry
        WHERE person_ref LIKE '%CANDIDATE%' OR person_ref = 'PER-LI-SHIMIN'
        ORDER BY person_ref
        """
    )
    rows = cursor.fetchall()
    writes = 0
    for row in rows:
        source_ref = str(row[0])
        target_ref = canonical_person_ref(source_ref)
        if target_ref == source_ref:
            continue
        fingerprint = sha256(
            f"field-normalized-person-v1|{target_ref}|{row[1]}|{row[2]}".encode(
                "utf-8"
            )
        ).hexdigest()
        payload = dict(row[9])
        for key in ("person_ref", "canonical_person_ref", "ruler_ref"):
            if payload.get(key) == source_ref:
                payload[key] = target_ref
        cursor.execute(
            """
            INSERT INTO v4_person_profile.person_identity_registry (
                person_ref, canonical_name, historical_context,
                identity_fingerprint, identity_status, semantic_version,
                supersedes_person_ref, idempotency_key, import_batch_id,
                payload, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, 'active', %s, NULL, %s, %s, %s, %s, %s)
            ON CONFLICT (person_ref) DO NOTHING
            """,
            (
                target_ref,
                row[1],
                row[2],
                fingerprint,
                row[5],
                f"field-normalized-person-v1:{target_ref}",
                row[8],
                json.dumps(payload, ensure_ascii=False),
                row[10],
                row[11],
            ),
        )
        cursor.execute(
            """
            SELECT window_ref, window_policy_version, payload
            FROM v4_person_profile.ruler_team_window_snapshots
            WHERE ruler_ref = %s
            """,
            (source_ref,),
        )
        for window_ref, policy_version, window_payload in cursor.fetchall():
            normalized_payload = dict(window_payload)
            normalized_payload["ruler_ref"] = target_ref
            cursor.execute(
                """
                UPDATE v4_person_profile.ruler_team_window_snapshots
                SET ruler_ref = %s, payload = %s::jsonb,
                    semantic_fingerprint = %s
                WHERE window_ref = %s AND window_policy_version = %s
                """,
                (
                    target_ref,
                    json.dumps(normalized_payload, ensure_ascii=False),
                    _stable_json_hash(normalized_payload),
                    window_ref,
                    policy_version,
                ),
            )
        cursor.execute(
            "DELETE FROM v4_person_profile.person_identity_registry WHERE person_ref = %s",
            (source_ref,),
        )
        writes += 1
        _record_field_backfill(
            cursor,
            schema_name="v4_person_profile",
            table_name="person_identity_registry",
            column_name="person_ref",
            source_value=source_ref,
            target_value=target_ref,
            normalization_kind="canonical_person_ref",
            source_row_count=1,
            applied_row_count=1,
        )
    return writes


def _normalize_source_profile_refs(cursor: Any) -> int:
    cursor.execute(
        """
        SELECT DISTINCT source_profile_ref
        FROM v4_person_profile.person_profile_snapshots
        UNION
        SELECT DISTINCT source_profile_ref
        FROM v4_person_profile.person_profile_catalog
        ORDER BY 1
        """
    )
    sources = [str(row[0]) for row in cursor.fetchall()]
    writes = 0
    for source_ref in sources:
        target_ref = canonical_source_profile_ref(source_ref)
        if source_ref == target_ref:
            continue
        cursor.execute(
            """
            SELECT profile_ref, snapshot_version, payload
            FROM v4_person_profile.person_profile_snapshots
            WHERE source_profile_ref = %s
            """,
            (source_ref,),
        )
        snapshot_rows = cursor.fetchall()
        for profile_ref, snapshot_version, payload in snapshot_rows:
            normalized_payload = dict(payload)
            normalized_payload["source_profile_ref"] = target_ref
            fingerprint_payload = dict(normalized_payload)
            fingerprint_payload.pop("semantic_fingerprint", None)
            fingerprint = _stable_json_hash(fingerprint_payload)
            if "semantic_fingerprint" in normalized_payload:
                normalized_payload["semantic_fingerprint"] = fingerprint
            cursor.execute(
                """
                UPDATE v4_person_profile.person_profile_snapshots
                SET source_profile_ref = %s, payload = %s::jsonb,
                    semantic_fingerprint = %s
                WHERE profile_ref = %s AND snapshot_version = %s
                """,
                (
                    target_ref,
                    json.dumps(normalized_payload, ensure_ascii=False),
                    fingerprint,
                    profile_ref,
                    snapshot_version,
                ),
            )
        cursor.execute(
            """
            UPDATE v4_person_profile.person_profile_catalog
            SET source_profile_ref = %s,
                payload = jsonb_set(payload, '{source_profile_ref}', to_jsonb(%s::text), TRUE)
            WHERE source_profile_ref = %s
            """,
            (target_ref, target_ref, source_ref),
        )
        applied = len(snapshot_rows) + max(int(cursor.rowcount), 0)
        writes += applied
        _record_field_backfill(
            cursor,
            schema_name="v4_person_profile",
            table_name="person_profile_snapshots/person_profile_catalog",
            column_name="source_profile_ref",
            source_value=source_ref,
            target_value=target_ref,
            normalization_kind="canonical_source_profile_ref",
            source_row_count=applied,
            applied_row_count=applied,
        )
    return writes


def _normalize_explanatory_columns(cursor: Any) -> int:
    specifications = (
        ("person_profile_catalog", "profile_ref", "snapshot_version", "talent_grade_basis"),
        ("person_profile_catalog", "profile_ref", "snapshot_version", "negative_talent_basis"),
        ("talent_grade_calibrations", "calibration_ref", None, "source_basis"),
        ("talent_grade_calibrations", "calibration_ref", None, "review_basis"),
    )
    writes = 0
    for table_name, key_column, second_key, column_name in specifications:
        key_select = f", {second_key}" if second_key else ""
        cursor.execute(
            f"SELECT {key_column}{key_select}, {column_name} "
            f"FROM v4_person_profile.{table_name} ORDER BY {key_column}"
        )
        rows = cursor.fetchall()
        before_sha = _stable_json_hash([str(row[-1]) for row in rows])
        source_count = 0
        applied_count = 0
        for row in rows:
            source_text = str(row[-1])
            target_text = normalize_chinese_explanatory_text(source_text)
            if source_text == target_text:
                continue
            source_count += 1
            if second_key:
                cursor.execute(
                    f"""
                    UPDATE v4_person_profile.{table_name}
                    SET {column_name} = %s,
                        payload = jsonb_set(payload, %s::text[], to_jsonb(%s::text), TRUE)
                    WHERE {key_column} = %s AND {second_key} = %s
                    """,
                    (target_text, [column_name], target_text, row[0], row[1]),
                )
            else:
                cursor.execute(
                    f"SELECT payload FROM v4_person_profile.{table_name} "
                    f"WHERE {key_column} = %s",
                    (row[0],),
                )
                payload = dict(cursor.fetchone()[0])
                payload[column_name] = target_text
                fingerprint_payload = dict(payload)
                fingerprint_payload.pop("semantic_fingerprint", None)
                fingerprint = _stable_json_hash(fingerprint_payload)
                if "semantic_fingerprint" in payload:
                    payload["semantic_fingerprint"] = fingerprint
                cursor.execute(
                    f"""
                    UPDATE v4_person_profile.{table_name}
                    SET {column_name} = %s, payload = %s::jsonb,
                        semantic_fingerprint = %s
                    WHERE {key_column} = %s
                    """,
                    (
                        target_text,
                        json.dumps(payload, ensure_ascii=False),
                        fingerprint,
                        row[0],
                    ),
                )
            applied_count += max(int(cursor.rowcount), 0)
        cursor.execute(
            f"SELECT {column_name} FROM v4_person_profile.{table_name} "
            f"ORDER BY {key_column}"
        )
        after_values = [str(row[0]) for row in cursor.fetchall()]
        remaining = sum(
            bool(re.search(r"[一-龥]", value) and re.search(r"[A-Za-z]", value))
            for value in after_values
        )
        cursor.execute(
            """
            INSERT INTO v4_governance.text_normalization_runs (
                schema_name, table_name, column_name, normalization_version,
                source_row_count, applied_row_count, remaining_mixed_row_count,
                before_sha256, after_sha256, applied_at
            ) VALUES (
                'v4_person_profile', %s, %s, %s, %s, %s, %s, %s, %s,
                CURRENT_TIMESTAMP
            )
            ON CONFLICT (schema_name, table_name, column_name, normalization_version)
            DO UPDATE SET
                source_row_count = EXCLUDED.source_row_count,
                applied_row_count = EXCLUDED.applied_row_count,
                remaining_mixed_row_count = EXCLUDED.remaining_mixed_row_count,
                before_sha256 = EXCLUDED.before_sha256,
                after_sha256 = EXCLUDED.after_sha256,
                applied_at = EXCLUDED.applied_at
            """,
            (
                table_name,
                column_name,
                FIELD_NORMALIZATION_VERSION,
                source_count,
                applied_count,
                remaining,
                before_sha,
                _stable_json_hash(after_values),
            ),
        )
        if remaining:
            raise RuntimeError(
                f"{table_name}.{column_name} still has {remaining} mixed-language rows"
            )
        writes += applied_count
    return writes


def _apply_full_field_normalization(cursor: Any) -> dict[str, int]:
    normalization_constraints = (
        ("public.assertions", "assertions_assertion_id_family_check", "assertion_id ~ '^AST-V4-[0-9A-F]{20}$'"),
        ("public.source_passages", "source_passages_section_id_family_check", "section_id ~ '^SEC-V4-[0-9A-F]{16}$'"),
        ("v4_source_cache.passages", "source_cache_passages_section_id_family_check", "section_id ~ '^SEC-V4-[0-9A-F]{16}$'"),
        ("v4_person_profile.person_identity_registry", "person_identity_registry_canonical_ref_check", "person_ref ~ '^PER-V4-[0-9A-F]{12}$'"),
        ("v4_person_profile.ruler_team_window_snapshots", "ruler_team_window_snapshots_canonical_ruler_ref_check", "ruler_ref ~ '^PER-V4-[0-9A-F]{12}$'"),
        ("v4_person_profile.person_profile_snapshots", "person_profile_snapshots_source_profile_ref_check", "source_profile_ref ~ '^SPR-V4-[0-9A-F]{16}$'"),
        ("v4_person_profile.person_profile_catalog", "person_profile_catalog_source_profile_ref_check", "source_profile_ref ~ '^SPR-V4-[0-9A-F]{16}$'"),
        (
            "v4_person_profile.person_profile_catalog",
            "person_profile_catalog_chinese_basis_check",
            "NOT (talent_grade_basis ~ '[一-龥]' AND talent_grade_basis ~ '[A-Za-z]') AND NOT (negative_talent_basis ~ '[一-龥]' AND negative_talent_basis ~ '[A-Za-z]')",
        ),
        (
            "v4_person_profile.talent_grade_calibrations",
            "talent_grade_calibrations_chinese_basis_check",
            "NOT (source_basis ~ '[一-龥]' AND source_basis ~ '[A-Za-z]') AND NOT (review_basis ~ '[一-龥]' AND review_basis ~ '[A-Za-z]')",
        ),
        ("v4_person_profile.import_batches", "import_batches_id_family_check", "import_batch_id ~ '^V4PP-BATCH-[0-9A-F]{16}$'"),
        ("v4_person_profile.import_batches", "import_batches_source_freeze_ref_type_check", "source_freeze_ref ~ '^FRZ-V4-[0-9A-F]{16}$'"),
    )
    for table_name, constraint_name, _ in normalization_constraints:
        cursor.execute(
            f'ALTER TABLE {table_name} DROP CONSTRAINT IF EXISTS "{constraint_name}"'
        )
    immutable_triggers = (
        ("person_profile_snapshots", "person_profile_snapshots_immutable"),
        ("person_profile_catalog", "person_profile_catalog_immutable"),
        ("ruler_team_window_snapshots", "ruler_team_window_snapshots_immutable"),
        ("ruler_team_window_members", "ruler_team_window_members_immutable"),
        ("talent_grade_calibrations", "talent_grade_calibrations_immutable"),
    )
    for table_name, trigger_name in immutable_triggers:
        cursor.execute(
            f'ALTER TABLE v4_person_profile."{table_name}" '
            f'DISABLE TRIGGER "{trigger_name}"'
        )
    try:
        assertion_writes = _normalize_assertion_ids(cursor)
        public_section_writes = _normalize_reference_column(
            cursor,
            schema_name="public",
            table_name="source_passages",
            column_name="section_id",
            canonicalizer=canonical_section_id,
            normalization_kind="canonical_section_id",
        )
        source_cache_section_writes = _normalize_reference_column(
            cursor,
            schema_name="v4_source_cache",
            table_name="passages",
            column_name="section_id",
            canonicalizer=canonical_section_id,
            normalization_kind="canonical_section_id",
        )
        explanatory_writes = _normalize_explanatory_columns(cursor)
        candidate_identity_writes = _normalize_candidate_identities(cursor)
        source_profile_writes = _normalize_source_profile_refs(cursor)
        batch_writes, freeze_writes = _normalize_import_batches(cursor)
    finally:
        for table_name, trigger_name in immutable_triggers:
            cursor.execute(
                f'ALTER TABLE v4_person_profile."{table_name}" '
                f'ENABLE TRIGGER "{trigger_name}"'
            )

    for table_name, constraint_name, expression in normalization_constraints:
        cursor.execute(
            f'ALTER TABLE {table_name} ADD CONSTRAINT "{constraint_name}" '
            f'CHECK ({expression}) NOT VALID'
        )

    cursor.execute(
        """
        ALTER TABLE public.assertions
            VALIDATE CONSTRAINT assertions_assertion_id_family_check;
        ALTER TABLE public.source_passages
            VALIDATE CONSTRAINT source_passages_section_id_family_check;
        ALTER TABLE v4_source_cache.passages
            VALIDATE CONSTRAINT source_cache_passages_section_id_family_check;
        ALTER TABLE public.episode_participants
            VALIDATE CONSTRAINT episode_participants_canonical_person_ref_check;
        ALTER TABLE public.historical_episodes
            VALIDATE CONSTRAINT historical_episodes_canonical_evaluation_context_check;
        ALTER TABLE v4_person_profile.person_identity_registry
            VALIDATE CONSTRAINT person_identity_registry_canonical_ref_check;
        ALTER TABLE v4_person_profile.ruler_team_window_snapshots
            VALIDATE CONSTRAINT ruler_team_window_snapshots_canonical_ruler_ref_check;
        ALTER TABLE v4_person_profile.person_profile_snapshots
            VALIDATE CONSTRAINT person_profile_snapshots_source_profile_ref_check;
        ALTER TABLE v4_person_profile.person_profile_catalog
            VALIDATE CONSTRAINT person_profile_catalog_source_profile_ref_check;
        ALTER TABLE v4_person_profile.person_profile_catalog
            VALIDATE CONSTRAINT person_profile_catalog_chinese_basis_check;
        ALTER TABLE v4_person_profile.talent_grade_calibrations
            VALIDATE CONSTRAINT talent_grade_calibrations_chinese_basis_check;
        ALTER TABLE v4_person_profile.import_batches
            VALIDATE CONSTRAINT import_batches_id_family_check;
        ALTER TABLE v4_person_profile.import_batches
            VALIDATE CONSTRAINT import_batches_source_freeze_ref_type_check;
        """
    )
    return {
        "assertion_id_rows_updated": assertion_writes,
        "public_section_id_rows_updated": public_section_writes,
        "source_cache_section_id_rows_updated": source_cache_section_writes,
        "candidate_identity_rows_updated": candidate_identity_writes,
        "source_profile_ref_rows_updated": source_profile_writes,
        "import_batch_rows_updated": batch_writes,
        "source_freeze_rows_updated": freeze_writes,
        "explanatory_text_rows_updated": explanatory_writes,
    }


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
    baseline_refresh = any(
        metric["metric_key"] not in baselines
        or metric["count"] < baselines[metric["metric_key"]]
        for metric in quality_before
    )
    if (
        state == (migration_sha, before_inventory_sha)
        and not gaps_before
        and not baseline_refresh
        and not regressions
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
    physical_backfill_summary = _apply_physical_identity_backfill(cursor)
    full_field_normalization = _apply_full_field_normalization(cursor)
    identity_alias_summary = _refresh_identity_reference_aliases(cursor)
    quality_after = _quality_metrics(cursor)
    remaining_regressions = [
        {**metric, "baseline_count": baselines[metric["metric_key"]]}
        for metric in quality_after
        if metric["metric_key"] in baselines
        and metric["count"] > baselines[metric["metric_key"]]
    ]
    if remaining_regressions:
        raise SchemaQualityRegressionError(
            f"field quality baseline regression: {remaining_regressions}"
        )
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
        "physical_identity_backfill": physical_backfill_summary,
        "full_field_normalization": full_field_normalization,
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
