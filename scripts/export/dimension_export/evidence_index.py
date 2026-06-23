from __future__ import annotations

from typing import Any

from shared.i5b_cluster_warning_display import (
    match_display_only_cluster_warnings,
    render_display_only_cluster_warning_section,
)


def unique_values(values: list[object]) -> list[str]:
    results: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            cleaned = value.strip()
        else:
            cleaned = str(value).strip()
        if cleaned and cleaned not in results:
            results.append(cleaned)
    return results


def linked_cards_for_cluster(
    cluster: dict[str, Any],
    evidence_lookup: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    linked_evidence_ids = list(cluster.get("linked_evidence_ids") or [])
    return [evidence_lookup[evidence_id] for evidence_id in linked_evidence_ids if evidence_id in evidence_lookup]


def render_display_warning_section_for_clusters(
    cluster_rows: list[dict[str, Any]],
    evidence_lookup: dict[str, dict[str, Any]],
    warning_rules: list[dict[str, Any]],
) -> str:
    warnings: list[dict[str, Any]] = []
    for cluster in cluster_rows:
        linked_cards = linked_cards_for_cluster(cluster, evidence_lookup)
        warnings.extend(match_display_only_cluster_warnings(cluster, linked_cards, warning_rules))

    return render_display_only_cluster_warning_section(warnings).rstrip()


def collect_display_warnings_for_clusters(
    cluster_rows: list[dict[str, Any]],
    evidence_lookup: dict[str, dict[str, Any]],
    warning_rules: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    for cluster in cluster_rows:
        linked_cards = linked_cards_for_cluster(cluster, evidence_lookup)
        warnings.extend(match_display_only_cluster_warnings(cluster, linked_cards, warning_rules))
    return warnings


def person_clusters_for_report(
    report: dict[str, Any],
    cluster_lookup: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    person_cluster_ids = report["positive_cluster_ids"] + report["negative_cluster_ids"]
    return [cluster_lookup[cluster_id] for cluster_id in person_cluster_ids if cluster_id in cluster_lookup]
