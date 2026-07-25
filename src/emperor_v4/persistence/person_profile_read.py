from __future__ import annotations

from typing import Any, Iterable


PROFILE_COLUMNS = (
    "person_ref",
    "canonical_name",
    "historical_context",
    "talent_grade",
    "talent_grade_basis",
    "talent_grade_confidence",
    "talent_authority_consensus",
    "talent_performance_support",
    "talent_evidence_coverage",
    "negative_risk_status",
    "negative_talent_class",
    "negative_talent_severity",
    "negative_talent_basis",
    "negative_talent_confidence",
    "negative_authority_consensus",
    "negative_fact_support",
    "negative_evidence_coverage",
    "capability_domains",
    "profile_ref",
    "source_profile_ref",
    "review_status",
    "source_created_at",
)


def _profile_from_row(row: tuple[Any, ...]) -> dict[str, Any]:
    if len(row) != len(PROFILE_COLUMNS):
        raise ValueError("person_profiles 查询列与读取合同不一致")
    return dict(zip(PROFILE_COLUMNS, row, strict=True))


def read_current_person_profiles(
    dsn: str,
    *,
    person_refs: Iterable[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Read the one current V4 person profile table in a read-only transaction."""

    if not dsn.strip():
        raise ValueError("读取唯一人物画像表需要显式 V4 DSN")
    requested = sorted({str(value) for value in person_refs or () if str(value)})
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("读取唯一人物画像表需要 psycopg") from exc

    query = (
        "SELECT "
        + ", ".join(PROFILE_COLUMNS)
        + " FROM v4_person_profile.person_profiles"
    )
    params: tuple[object, ...] = ()
    if requested:
        query += " WHERE person_ref = ANY(%s)"
        params = (requested,)
    query += " ORDER BY person_ref"
    with psycopg.connect(dsn) as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            rows = [_profile_from_row(tuple(row)) for row in cursor.fetchall()]

    profiles = {str(row["person_ref"]): row for row in rows}
    if len(profiles) != len(rows):
        raise ValueError("唯一人物画像表返回重复 person_ref")
    missing = sorted(set(requested) - set(profiles))
    if missing:
        raise ValueError(f"唯一人物画像表缺少人物: {missing}")
    return profiles
