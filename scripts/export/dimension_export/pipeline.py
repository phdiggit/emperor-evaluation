from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from export.dimension_export.data_loading import read_jsonl


PersonEvaluator = Callable[[str, list[dict[str, Any]], dict[str, dict[str, Any]]], dict[str, Any]]


def build_dimension_context(
    *,
    targets: list[str],
    data_dir: Path,
    evaluate_person: PersonEvaluator,
) -> dict[str, Any]:
    evidence_cards = read_jsonl(data_dir / "evidence_cards.jsonl")
    evidence_clusters = read_jsonl(data_dir / "evidence_clusters.jsonl")
    evidence_lookup = {row["evidence_id"]: row for row in evidence_cards if row.get("evidence_id")}
    cluster_lookup = {row["cluster_id"]: row for row in evidence_clusters if row.get("cluster_id")}
    person_reports = [evaluate_person(person, evidence_clusters, evidence_lookup) for person in targets]
    return {
        "targets": targets,
        "evidence_lookup": evidence_lookup,
        "cluster_lookup": cluster_lookup,
        "person_reports": person_reports,
    }
