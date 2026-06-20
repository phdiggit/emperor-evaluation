from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import config_loaders
from export_md_scaffold import escape_cell


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "evidence_cache.sqlite"
I5B_SUBITEM = "第五项B"

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
    "object_anchor",
    "evidence_role",
    "mitigation_flag",
    "upper_bound_flag",
    "cluster_role",
    "cross_item_split",
    "scoring_effect",
    "adjudication_status",
]
def load_i5b_net_evidence_targets() -> list[tuple[str, Path]]:
    return config_loaders.get_i5b_net_evidence_targets()


I5B_NET_EVIDENCE_TARGETS = load_i5b_net_evidence_targets()


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
