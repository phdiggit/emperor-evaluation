from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path

import config_loaders
from export_i5b_auto_adjudication import export_auto_adjudication
from export_i5b_expanded_batch1 import (
    export_expanded_i5b_batch1_cluster_adjudication,
    export_expanded_i5b_batch1_post_supplement_adjudication,
    export_expanded_i5b_batch1_review,
    export_expanded_i5b_batch1_targeted_supplement,
)
from export_i5b_net_evidence import (
    I5B_NET_EVIDENCE_TARGETS,
    export_i5b_evidence_cards_index,
    export_i5b_evidence_clusters_index,
    export_i5b_net_evidence_pool,
    export_i5b_review_profile_views,
    export_i5b_search_package_index,
)
from export_i5b_views import (
    export_expanded_i5b_batch1_human_review_package,
    export_expanded_i5b_batch1_readiness_audit,
    export_expanded_i5b_batch1_readiness_followup,
    export_expanded_i5b_batch1_relative_band_preparation,
)
from export_project_doc_views import (
    export_expanded_i5b_candidate_pool_docs,
    export_global_scale_decision_brief_docs,
)
from export_md_scaffold import (
    ExportStep,
    escape_cell,
    export_db_table_markdown,
    join_list_cell,
    read_jsonl,
    run_export_steps,
    summarize_unique_values,
)


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "evidence_cache.sqlite"
EXPORT_PATH = ROOT / "exports" / "markdown_views" / "史料证据卡索引.md"
SEARCH_LOGS_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "第五项B三人试点检索线索.md"
EVIDENCE_CLUSTERS_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "证据组裁量索引.md"
THEMATIC_ANCHORS_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "专题锚点索引.md"
QUERY_PROFILES_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "项目检索包索引.md"
YONGZHENG_RULE_BOUNDARY_BATCH_PATH = ROOT / "data" / "rule_boundary_batches" / "i5b_yongzheng_rule_boundary_review_20260619.jsonl"
ZHUYUANZHANG_MICRO_SUPPLEMENT_SOURCE_BATCH_PATH = ROOT / "data" / "source_batches" / "i5b_zhu_yuanzhang_micro_supplement_20260619.jsonl"
ZHUYUANZHANG_MICRO_SUPPLEMENT_EVIDENCE_BATCH_PATH = ROOT / "data" / "evidence_card_batches" / "i5b_zhu_yuanzhang_micro_supplement_20260619.jsonl"



HEADERS = [
    "evidence_id",
    "person",
    "subitem",
    "human_level",
    "source_id",
    "quote_short",
    "object_anchor",
    "evidence_role",
    "mitigation_flag",
    "upper_bound_flag",
    "cluster_role",
    "verification_status",
    "case_classification",
    "risk_status",
    "mitigating_factors",
    "aggravating_factors",
    "reversal_or_rehabilitation",
    "adjudication_status",
]
SEARCH_LOG_HEADERS = [
    "search_id",
    "person",
    "subitem",
    "polarity",
    "trigger_family",
    "query_terms",
    "result_status",
    "result_summary",
    "linked_evidence_id",
    "note",
]
EVIDENCE_CLUSTER_HEADERS = [
    "cluster_id",
    "person",
    "subitem",
    "cluster_type",
    "polarity",
    "linked_evidence_ids",
    "linked_object_anchors",
    "linked_evidence_roles",
    "candidate_strength",
    "upper_probe",
    "adjudication_status",
    "summary",
]
THEMATIC_ANCHOR_HEADERS = [
    "anchor_id",
    "theme",
    "subitem",
    "persons",
    "linked_evidence_ids",
    "linked_cluster_ids",
    "comparative_value",
    "anchor_summary",
]
QUERY_PROFILE_HEADERS = [
    "query_profile_id",
    "item",
    "subitem",
    "search_modes",
    "positive_terms",
    "negative_terms",
    "reversal_terms",
    "source_scopes",
    "thematic_anchor_targets",
]


def load_i5b_trial_targets() -> list[str]:
    return config_loaders.get_i5b_trial_targets()


I5B_TRIAL_TARGETS = load_i5b_trial_targets()
I5B_SUBITEM = "第五项B"


def export_markdown() -> Path:
    EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    if DB_PATH.exists():
        with sqlite3.connect(DB_PATH) as connection:
            connection.row_factory = sqlite3.Row
            rows = list(
                connection.execute(
                    """
                    SELECT evidence_id, person, subitem, human_level, source_id,
                           quote_short, verification_status, raw_json
                    FROM evidence_cards
                    ORDER BY evidence_id
                    """
                )
            )

    lines = [
        "# 史料证据卡索引",
        "",
        "| " + " | ".join(HEADERS) + " |",
        "| " + " | ".join("---" for _ in HEADERS) + " |",
    ]

    for row in rows:
        raw_json = json.loads(row["raw_json"])
        values = {header: raw_json.get(header, row[header] if header in row.keys() else "") for header in HEADERS}
        lines.append("| " + " | ".join(escape_cell(values[header]) for header in HEADERS) + " |")

    EXPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return EXPORT_PATH


def export_search_logs_markdown() -> Path:
    SEARCH_LOGS_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    if DB_PATH.exists():
        placeholders = ", ".join("?" for _ in I5B_TRIAL_TARGETS)
        with sqlite3.connect(DB_PATH) as connection:
            connection.row_factory = sqlite3.Row
            rows = list(
                connection.execute(
                    f"""
                    SELECT search_id, person, subitem, polarity, trigger_family,
                           query_terms, result_status, result_summary,
                           linked_evidence_id, note
                    FROM search_logs
                    WHERE subitem = ?
                      AND person IN ({placeholders})
                    ORDER BY person, polarity, trigger_family, search_id
                    """,
                    [I5B_SUBITEM, *I5B_TRIAL_TARGETS],
                )
            )

    lines = [
        "# 第五项B三人试点检索线索",
        "",
        "本文件导出待回源检索线索；未回源材料不得入分。",
        "",
        "| " + " | ".join(SEARCH_LOG_HEADERS) + " |",
        "| " + " | ".join("---" for _ in SEARCH_LOG_HEADERS) + " |",
    ]

    for row in rows:
        lines.append("| " + " | ".join(escape_cell(row[header]) for header in SEARCH_LOG_HEADERS) + " |")

    SEARCH_LOGS_EXPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return SEARCH_LOGS_EXPORT_PATH


def export_generic_markdown(
    export_path: Path,
    title: str,
    table: str,
    headers: list[str],
    order_by: str,
) -> Path:
    return export_db_table_markdown(DB_PATH, export_path, title, table, headers, order_by)




def export_evidence_clusters_markdown() -> Path:
    EVIDENCE_CLUSTERS_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    cluster_rows = []
    evidence_lookup: dict[str, dict[str, object]] = {}
    if DB_PATH.exists():
        with sqlite3.connect(DB_PATH) as connection:
            connection.row_factory = sqlite3.Row
            evidence_rows = list(
                connection.execute(
                    """
                    SELECT evidence_id, raw_json
                    FROM evidence_cards
                    """
                )
            )
            for row in evidence_rows:
                evidence_lookup[row["evidence_id"]] = json.loads(row["raw_json"])

            cluster_rows = list(
                connection.execute(
                    """
                    SELECT raw_json
                    FROM evidence_clusters
                    ORDER BY cluster_id
                    """
                )
            )

    lines = [
        "# 证据组裁量索引",
        "",
        "| " + " | ".join(EVIDENCE_CLUSTER_HEADERS) + " |",
        "| " + " | ".join("---" for _ in EVIDENCE_CLUSTER_HEADERS) + " |",
    ]

    for row in cluster_rows:
        raw_json = json.loads(row["raw_json"])
        linked_evidence_ids = raw_json.get("linked_evidence_ids") or []
        linked_rows = [evidence_lookup[evidence_id] for evidence_id in linked_evidence_ids if evidence_id in evidence_lookup]
        raw_json["linked_object_anchors"] = summarize_unique_values(linked_rows, "object_anchor")
        raw_json["linked_evidence_roles"] = summarize_unique_values(linked_rows, "evidence_role")
        lines.append("| " + " | ".join(escape_cell(raw_json.get(header)) for header in EVIDENCE_CLUSTER_HEADERS) + " |")

    EVIDENCE_CLUSTERS_EXPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return EVIDENCE_CLUSTERS_EXPORT_PATH


def main() -> int:
    steps = [
        ExportStep("evidence_index", export_markdown),
        ExportStep("search_logs", export_search_logs_markdown),
        ExportStep("evidence_clusters", export_evidence_clusters_markdown),
        ExportStep(
            "thematic_anchors",
            lambda: export_generic_markdown(
                THEMATIC_ANCHORS_EXPORT_PATH,
                "专题锚点索引",
                "thematic_anchors",
                THEMATIC_ANCHOR_HEADERS,
                "anchor_id",
            ),
        ),
        ExportStep(
            "query_profiles",
            lambda: export_generic_markdown(
                QUERY_PROFILES_EXPORT_PATH,
                "项目检索包索引",
                "query_profiles",
                QUERY_PROFILE_HEADERS,
                "query_profile_id",
            ),
        ),
        *[
            ExportStep(
                f"net_evidence_{person}",
                lambda person=person, net_evidence_path=net_evidence_path: export_i5b_net_evidence_pool(
                    person, net_evidence_path
                ),
            )
            for person, net_evidence_path in I5B_NET_EVIDENCE_TARGETS
        ],
        ExportStep("i5b_evidence_cards_index", export_i5b_evidence_cards_index),
        ExportStep("i5b_evidence_clusters_index", export_i5b_evidence_clusters_index),
        ExportStep("i5b_search_package_index", export_i5b_search_package_index),
        ExportStep("i5b_review_profile_views", export_i5b_review_profile_views),
        ExportStep("expanded_batch1_review", export_expanded_i5b_batch1_review),
        ExportStep("expanded_batch1_cluster_adjudication", export_expanded_i5b_batch1_cluster_adjudication),
        ExportStep("expanded_batch1_targeted_supplement", export_expanded_i5b_batch1_targeted_supplement),
        ExportStep("expanded_batch1_post_supplement_adjudication", export_expanded_i5b_batch1_post_supplement_adjudication),
        ExportStep("expanded_batch1_readiness_audit", export_expanded_i5b_batch1_readiness_audit),
        ExportStep("expanded_batch1_readiness_followup", export_expanded_i5b_batch1_readiness_followup),
        ExportStep("expanded_batch1_human_review_package", export_expanded_i5b_batch1_human_review_package),
        ExportStep("expanded_batch1_relative_band_preparation", export_expanded_i5b_batch1_relative_band_preparation),
        ExportStep("global_scale_decision_brief", export_global_scale_decision_brief_docs),
        ExportStep("expanded_i5b_candidate_pool", export_expanded_i5b_candidate_pool_docs),
        ExportStep("auto_adjudication", export_auto_adjudication),
    ]
    run_export_steps(steps)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
