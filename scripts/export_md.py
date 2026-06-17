from __future__ import annotations

import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "evidence_cache.sqlite"
EXPORT_PATH = ROOT / "exports" / "markdown_views" / "史料证据卡索引.md"
SEARCH_LOGS_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "第五项B三人试点检索线索.md"
EVIDENCE_CLUSTERS_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "证据组裁量索引.md"
THEMATIC_ANCHORS_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "专题锚点索引.md"
QUERY_PROFILES_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "项目检索包索引.md"

HEADERS = [
    "evidence_id",
    "person",
    "subitem",
    "human_level",
    "source_id",
    "quote_short",
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
NET_EVIDENCE_CLUSTER_HEADERS = [
    "cluster_id",
    "polarity",
    "cluster_type",
    "linked_evidence_ids",
    "candidate_strength",
    "upper_probe",
    "adjudication_status",
    "summary",
]
NET_EVIDENCE_CARD_HEADERS = [
    "evidence_id",
    "polarity",
    "human_level",
    "trigger_family",
    "source_id",
    "quote_short",
    "cross_item_split",
    "scoring_effect",
    "adjudication_status",
]
I5B_TRIAL_TARGETS = ["李世民", "刘秀", "刘庄"]
I5B_NET_EVIDENCE_TARGETS = [
    ("李世民", ROOT / "exports" / "markdown_views" / "第五项B_李世民净证据池.md"),
    ("刘秀", ROOT / "exports" / "markdown_views" / "第五项B_刘秀净证据池.md"),
]
I5B_SUBITEM = "第五项B"


def escape_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).replace("|", "\\|").replace("\n", " ")


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
    export_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    if DB_PATH.exists():
        with sqlite3.connect(DB_PATH) as connection:
            connection.row_factory = sqlite3.Row
            rows = list(connection.execute(f"SELECT raw_json FROM {table} ORDER BY {order_by}"))

    lines = [
        f"# {title}",
        "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]

    for row in rows:
        raw_json = json.loads(row["raw_json"])
        lines.append("| " + " | ".join(escape_cell(raw_json.get(header)) for header in headers) + " |")

    export_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return export_path


def export_i5b_net_evidence_pool(person: str, export_path: Path) -> Path:
    export_path.parent.mkdir(parents=True, exist_ok=True)

    cluster_rows = []
    evidence_rows = []
    if DB_PATH.exists():
        with sqlite3.connect(DB_PATH) as connection:
            connection.row_factory = sqlite3.Row
            cluster_rows = list(
                connection.execute(
                    """
                    SELECT raw_json
                    FROM evidence_clusters
                    WHERE person = ? AND subitem = ?
                    ORDER BY polarity DESC, candidate_strength DESC, cluster_id
                    """,
                    [person, I5B_SUBITEM],
                )
            )
            evidence_rows = list(
                connection.execute(
                    """
                    SELECT raw_json
                    FROM evidence_cards
                    WHERE person = ? AND subitem = ?
                    ORDER BY polarity DESC, strength DESC, evidence_id
                    """,
                    [person, I5B_SUBITEM],
                )
            )

    lines = [
        f"# 第五项B_{person}净证据池",
        "",
        "本文件为定档前净证据池视图；只汇总已回源原子证据与证据组裁量候选，不代表最终档位、得分或排名。",
        "",
        "## 证据组裁量结论",
        "",
        "| " + " | ".join(NET_EVIDENCE_CLUSTER_HEADERS) + " |",
        "| " + " | ".join("---" for _ in NET_EVIDENCE_CLUSTER_HEADERS) + " |",
    ]

    for row in cluster_rows:
        raw_json = json.loads(row["raw_json"])
        lines.append(
            "| " + " | ".join(escape_cell(raw_json.get(header)) for header in NET_EVIDENCE_CLUSTER_HEADERS) + " |"
        )

    lines.extend(
        [
            "",
            "## 原子证据卡",
            "",
            "| " + " | ".join(NET_EVIDENCE_CARD_HEADERS) + " |",
            "| " + " | ".join("---" for _ in NET_EVIDENCE_CARD_HEADERS) + " |",
        ]
    )

    for row in evidence_rows:
        raw_json = json.loads(row["raw_json"])
        lines.append("| " + " | ".join(escape_cell(raw_json.get(header)) for header in NET_EVIDENCE_CARD_HEADERS) + " |")

    export_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return export_path


def main() -> int:
    export_path = export_markdown()
    print(f"exported {export_path}")
    search_logs_export_path = export_search_logs_markdown()
    print(f"exported {search_logs_export_path}")
    evidence_clusters_export_path = export_generic_markdown(
        EVIDENCE_CLUSTERS_EXPORT_PATH,
        "证据组裁量索引",
        "evidence_clusters",
        EVIDENCE_CLUSTER_HEADERS,
        "cluster_id",
    )
    print(f"exported {evidence_clusters_export_path}")
    thematic_anchors_export_path = export_generic_markdown(
        THEMATIC_ANCHORS_EXPORT_PATH,
        "专题锚点索引",
        "thematic_anchors",
        THEMATIC_ANCHOR_HEADERS,
        "anchor_id",
    )
    print(f"exported {thematic_anchors_export_path}")
    query_profiles_export_path = export_generic_markdown(
        QUERY_PROFILES_EXPORT_PATH,
        "项目检索包索引",
        "query_profiles",
        QUERY_PROFILE_HEADERS,
        "query_profile_id",
    )
    print(f"exported {query_profiles_export_path}")
    for person, net_evidence_path in I5B_NET_EVIDENCE_TARGETS:
        exported_net_evidence_path = export_i5b_net_evidence_pool(person, net_evidence_path)
        print(f"exported {exported_net_evidence_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
