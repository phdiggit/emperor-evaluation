from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path

import config_loaders
from export_md_scaffold import escape_cell, join_list_cell, read_jsonl
from i5b_markdown_display import AppendixEntry, load_display_dictionary, render_appendix_page, render_markdown_kv, render_markdown_table


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "evidence_cache.sqlite"
I5B_SUBITEM = "第五项B"
MARKDOWN_VIEW_ROOT = ROOT / "exports" / "markdown_views"
I5B_EVIDENCE_CHAIN_ROOT = MARKDOWN_VIEW_ROOT / "第五项B" / "证据链"
I5B_EVIDENCE_CARD_DIR = I5B_EVIDENCE_CHAIN_ROOT / "证据卡"
I5B_EVIDENCE_CLUSTER_DIR = I5B_EVIDENCE_CHAIN_ROOT / "证据簇"
I5B_APPENDIX_DIR = I5B_EVIDENCE_CHAIN_ROOT / "附录"
EXPANDED_BATCH1_REVIEW_EXPORT_PATH = I5B_EVIDENCE_CARD_DIR / "第五项B扩展试点第一批证据卡与证据簇草案.md"
EXPANDED_BATCH1_CLUSTER_ADJUDICATION_BATCH_PATH = ROOT / "data" / "adjudication_batches" / "i5b_expanded_pilot_batch1_cluster_adjudication_20260619.jsonl"
EXPANDED_BATCH1_CLUSTER_ADJUDICATION_EXPORT_PATH = I5B_EVIDENCE_CLUSTER_DIR / "第五项B扩展试点第一批证据簇结算草案.md"
TARGETED_SUPPLEMENT_SOURCE_BATCH_PATH = ROOT / "data" / "source_batches" / "i5b_expanded_pilot_batch1_targeted_supplement_20260619.jsonl"
TARGETED_SUPPLEMENT_EVIDENCE_BATCH_PATH = ROOT / "data" / "evidence_card_batches" / "i5b_expanded_pilot_batch1_targeted_supplement_20260619.jsonl"
TARGETED_SUPPLEMENT_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "第五项B扩展试点第一批定向补证.md"
TARGETED_SUPPLEMENT_ROLE_CLASS_SWEEP_BATCH_PATH = ROOT / "data" / "sweep_batches" / "i5b_yongzheng_role_class_sweep_20260619.jsonl"
POST_SUPPLEMENT_ADJUDICATION_BATCH_PATH = ROOT / "data" / "adjudication_batches" / "i5b_expanded_pilot_batch1_post_supplement_adjudication_20260619.jsonl"
POST_SUPPLEMENT_ADJUDICATION_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "第五项B扩展试点第一批补证后结算更新草案.md"
EXPANDED_BATCH1_EVIDENCE_BATCH_PATH = ROOT / "data" / "evidence_card_batches" / "i5b_expanded_pilot_batch1_20260619.jsonl"
EXPANDED_BATCH1_CLUSTER_BATCH_PATH = ROOT / "data" / "evidence_cluster_batches" / "i5b_expanded_pilot_batch1_20260619.jsonl"


def load_expanded_batch1_persons() -> list[str]:
    return config_loaders.get_i5b_expanded_batch1_targets()


EXPANDED_BATCH1_PERSONS = load_expanded_batch1_persons()
EXPANDED_BATCH1_EVIDENCE_HEADERS = [
    "evidence_id",
    "person",
    "polarity",
    "strength",
    "human_level",
    "source_id",
    "quote_short",
    "object_anchor",
    "evidence_role",
    "cluster_candidate_id",
    "cross_item_split",
    "scoring_effect",
    "verification_status",
    "adjudication_status",
]
EXPANDED_BATCH1_CLUSTER_HEADERS = [
    "cluster_id",
    "person",
    "polarity",
    "linked_evidence_ids",
    "summary",
    "five_axis_assessment",
    "candidate_strength",
    "upper_probe",
    "cross_item_split",
    "adjudication_status",
    "status",
]
EXPANDED_BATCH1_CLUSTER_ADJUDICATION_HEADERS = [
    "adjudication_id",
    "person",
    "item",
    "subitem",
    "positive_cluster_ids",
    "negative_cluster_ids",
    "positive_core_summary",
    "negative_core_summary",
    "adjacent_item_split_summary",
    "negative_intercept_status",
    "adjacent_item_split_status",
    "rule_pressure_summary",
    "net_adjudication_draft",
    "supplement_gap_list",
    "status",
]
TARGETED_SUPPLEMENT_SOURCE_HEADERS = [
    "source_id",
    "title",
    "author",
    "dynasty",
    "volume",
    "location",
    "url",
    "note",
]
TARGETED_SUPPLEMENT_EVIDENCE_HEADERS = [
    "evidence_id",
    "person",
    "polarity",
    "strength",
    "human_level",
    "source_id",
    "quote_short",
    "object_anchor",
    "evidence_role",
    "cluster_candidate_id",
    "supplement_gap_addressed",
    "supplement_for_adjudication_id",
    "verification_status",
    "adjudication_status",
]
TARGETED_SUPPLEMENT_ROLE_CLASS_SWEEP_HEADERS = [
    "sweep_id",
    "item",
    "subitem",
    "role_class",
    "candidate_people",
    "carded_people",
    "linked_evidence_ids",
    "not_carded_people",
    "not_carded_reason",
    "source_status",
    "fifth_b_relevance",
    "adjacent_item_risk",
    "status",
]


def _relative_appendix_path(export_path: Path, appendix_path: Path) -> str:
    import os

    return Path(os.path.relpath(appendix_path, export_path.parent)).as_posix()


def _write_appendix(path: Path, title: str, entries: list[AppendixEntry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_appendix_page(title, entries).rstrip() + "\n", encoding="utf-8")


def _remove_legacy_export(filename: str, export_path: Path) -> None:
    legacy_path = MARKDOWN_VIEW_ROOT / filename
    if legacy_path != export_path and legacy_path.exists():
        legacy_path.unlink()


def export_expanded_i5b_batch1_review() -> Path:
    EXPANDED_BATCH1_REVIEW_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    evidence_rows = []
    cluster_rows = []
    if DB_PATH.exists():
        placeholders = ", ".join("?" for _ in EXPANDED_BATCH1_PERSONS)
        with sqlite3.connect(DB_PATH) as connection:
            connection.row_factory = sqlite3.Row
            evidence_rows = list(
                connection.execute(
                    f"""
                    SELECT raw_json
                    FROM evidence_cards
                    WHERE subitem = ?
                      AND person IN ({placeholders})
                    ORDER BY person, polarity DESC, strength DESC, evidence_id
                    """,
                    [I5B_SUBITEM, *EXPANDED_BATCH1_PERSONS],
                )
            )
            cluster_rows = list(
                connection.execute(
                    f"""
                    SELECT raw_json
                    FROM evidence_clusters
                    WHERE subitem = ?
                      AND person IN ({placeholders})
                    ORDER BY person, polarity DESC, candidate_strength DESC, cluster_id
                    """,
                    [I5B_SUBITEM, *EXPANDED_BATCH1_PERSONS],
                )
            )

    if not evidence_rows:
        evidence_rows = [
            {"raw_json": json.dumps(row, ensure_ascii=False)}
            for row in read_jsonl(EXPANDED_BATCH1_EVIDENCE_BATCH_PATH)
            if row.get("subitem") == I5B_SUBITEM and row.get("person") in EXPANDED_BATCH1_PERSONS
        ]
        evidence_rows.sort(
            key=lambda row: (
                json.loads(row["raw_json"]).get("person", ""),
                0 if json.loads(row["raw_json"]).get("polarity") == "positive" else 1,
                -int(json.loads(row["raw_json"]).get("strength", 0) or 0),
                json.loads(row["raw_json"]).get("evidence_id", ""),
            )
        )
    if not cluster_rows:
        cluster_rows = [
            {"raw_json": json.dumps(row, ensure_ascii=False)}
            for row in read_jsonl(EXPANDED_BATCH1_CLUSTER_BATCH_PATH)
            if row.get("subitem") == I5B_SUBITEM and row.get("person") in EXPANDED_BATCH1_PERSONS
        ]
        cluster_rows.sort(
            key=lambda row: (
                json.loads(row["raw_json"]).get("person", ""),
                0 if json.loads(row["raw_json"]).get("polarity") == "positive" else 1,
                -int(json.loads(row["raw_json"]).get("candidate_strength", 0) or 0),
                json.loads(row["raw_json"]).get("cluster_id", ""),
            )
        )
    evidence_payloads = [json.loads(row["raw_json"]) for row in evidence_rows]
    cluster_payloads = [json.loads(row["raw_json"]) for row in cluster_rows]
    appendix_path = I5B_APPENDIX_DIR / "第五项B扩展试点第一批证据卡与证据簇长字段附录.md"
    appendix_entries: list[AppendixEntry] = []
    display_config = load_display_dictionary()
    appendix_relative_path = _relative_appendix_path(EXPANDED_BATCH1_REVIEW_EXPORT_PATH, appendix_path)
    lines = [
        "# 第五项B扩展试点第一批证据卡与证据簇草案",
        "",
        f"本文件汇总{'、'.join(EXPANDED_BATCH1_PERSONS)}的回源证据卡与证据簇草案，仅供审阅，不生成正式分，不排名，不出总榜。",
        "",
        "## 证据卡",
        "",
        *render_markdown_table(
            evidence_payloads,
            EXPANDED_BATCH1_EVIDENCE_HEADERS,
            row_id_fields=("evidence_id",),
            appendix_relative_path=appendix_relative_path,
            appendix_entries=appendix_entries,
            config=display_config,
        ),
    ]

    lines.extend(
        [
            "",
            "## 证据簇",
            "",
            *render_markdown_table(
                cluster_payloads,
                EXPANDED_BATCH1_CLUSTER_HEADERS,
                row_id_fields=("cluster_id",),
                appendix_relative_path=appendix_relative_path,
                appendix_entries=appendix_entries,
                config=display_config,
            ),
        ]
    )

    EXPANDED_BATCH1_REVIEW_EXPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _write_appendix(appendix_path, "第五项B扩展试点第一批证据卡与证据簇长字段附录", appendix_entries)
    _remove_legacy_export("第五项B扩展试点第一批证据卡与证据簇草案.md", EXPANDED_BATCH1_REVIEW_EXPORT_PATH)
    return EXPANDED_BATCH1_REVIEW_EXPORT_PATH


def export_expanded_i5b_batch1_cluster_adjudication() -> Path:
    EXPANDED_BATCH1_CLUSTER_ADJUDICATION_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    rows = read_jsonl(EXPANDED_BATCH1_CLUSTER_ADJUDICATION_BATCH_PATH)

    appendix_path = I5B_APPENDIX_DIR / "第五项B扩展试点第一批证据簇结算长字段附录.md"
    appendix_entries: list[AppendixEntry] = []
    display_config = load_display_dictionary()
    appendix_relative_path = _relative_appendix_path(EXPANDED_BATCH1_CLUSTER_ADJUDICATION_EXPORT_PATH, appendix_path)
    lines = [
        "# 第五项B扩展试点第一批证据簇结算草案",
        "",
        f"本文件仅供人工审阅，汇总{'、'.join(EXPANDED_BATCH1_PERSONS)}的证据簇结算草案；只作草案，不输出终局结果。",
        "",
        "## 结算总览",
        "",
        *render_markdown_table(
            rows,
            EXPANDED_BATCH1_CLUSTER_ADJUDICATION_HEADERS,
            row_id_fields=("adjudication_id",),
            appendix_relative_path=appendix_relative_path,
            appendix_entries=appendix_entries,
            config=display_config,
        ),
    ]

    lines.extend(["", "## 逐人结算", ""])
    for row in rows:
        lines.extend(
            [
                f"### {row.get('person')}",
                "",
            ]
        )
        for field in [
            "positive_cluster_ids",
            "negative_cluster_ids",
            "positive_core_summary",
            "negative_core_summary",
            "adjacent_item_split_summary",
            "negative_intercept_status",
            "adjacent_item_split_status",
            "rule_pressure_summary",
            "net_adjudication_draft",
            "supplement_gap_list",
            "status",
        ]:
            lines.extend(render_markdown_kv(field, row.get(field), display_config))
        lines.append("")

    lines.extend(["## 规则敏感点清单", ""])
    for row in rows:
        lines.append(f"- **{row.get('person')}**：{row.get('rule_pressure_summary') or ''}")

    lines.extend(["", "## 后续 targeted supplement 缺口清单", ""])
    for row in rows:
        lines.append(f"- **{row.get('person')}**：{escape_cell(row.get('supplement_gap_list'))}")

    lines.extend(
        [
            "",
            "本文件不输出终局结果。",
        ]
    )

    EXPANDED_BATCH1_CLUSTER_ADJUDICATION_EXPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _write_appendix(appendix_path, "第五项B扩展试点第一批证据簇结算长字段附录", appendix_entries)
    _remove_legacy_export("第五项B扩展试点第一批证据簇结算草案.md", EXPANDED_BATCH1_CLUSTER_ADJUDICATION_EXPORT_PATH)
    return EXPANDED_BATCH1_CLUSTER_ADJUDICATION_EXPORT_PATH


def export_expanded_i5b_batch1_targeted_supplement() -> Path:
    TARGETED_SUPPLEMENT_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    source_rows = read_jsonl(TARGETED_SUPPLEMENT_SOURCE_BATCH_PATH)
    evidence_rows = read_jsonl(TARGETED_SUPPLEMENT_EVIDENCE_BATCH_PATH)
    sweep_rows = read_jsonl(TARGETED_SUPPLEMENT_ROLE_CLASS_SWEEP_BATCH_PATH)
    person_counts = Counter(row.get("person") for row in evidence_rows)

    def render_sweep_cell(value: object) -> str:
        if isinstance(value, list):
            return escape_cell("、".join(str(item) for item in value))
        return escape_cell(value)

    lines = [
        "# 第五项B扩展试点第一批定向补证",
        "",
        "本文仅汇总定向补证材料，不定档，不出分，不排名，不出总榜。",
        "",
        "## 人数与补证数量",
        "",
        "| 人物 | 证据卡数 |",
        "| --- | ---: |",
    ]
    for person in EXPANDED_BATCH1_PERSONS:
        lines.append(f"| {person} | {person_counts.get(person, 0)} |")

    lines.extend(["", "## 来源", "", "| " + " | ".join(TARGETED_SUPPLEMENT_SOURCE_HEADERS) + " |", "| " + " | ".join("---" for _ in TARGETED_SUPPLEMENT_SOURCE_HEADERS) + " |",])
    for row in source_rows:
        lines.append("| " + " | ".join(escape_cell(row.get(header)) for header in TARGETED_SUPPLEMENT_SOURCE_HEADERS) + " |")

    lines.extend(["", "## 证据卡", "", "| " + " | ".join(TARGETED_SUPPLEMENT_EVIDENCE_HEADERS) + " |", "| " + " | ".join("---" for _ in TARGETED_SUPPLEMENT_EVIDENCE_HEADERS) + " |",])
    for row in evidence_rows:
        lines.append("| " + " | ".join(escape_cell(row.get(header)) for header in TARGETED_SUPPLEMENT_EVIDENCE_HEADERS) + " |")

    lines.extend([
        "",
        "## 雍正 role-class sweep / 防漏扫查",
        "",
        "| " + " | ".join(TARGETED_SUPPLEMENT_ROLE_CLASS_SWEEP_HEADERS) + " |",
        "| " + " | ".join("---" for _ in TARGETED_SUPPLEMENT_ROLE_CLASS_SWEEP_HEADERS) + " |",
    ])
    for row in sweep_rows:
        lines.append(
            "| "
            + " | ".join(render_sweep_cell(row.get(header)) for header in TARGETED_SUPPLEMENT_ROLE_CLASS_SWEEP_HEADERS)
            + " |"
        )

    lines.extend(["", "结语：不定档，不出分，不排名，不出总榜。", ""])

    TARGETED_SUPPLEMENT_EXPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return TARGETED_SUPPLEMENT_EXPORT_PATH


def export_expanded_i5b_batch1_post_supplement_adjudication() -> Path:
    POST_SUPPLEMENT_ADJUDICATION_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    rows = read_jsonl(POST_SUPPLEMENT_ADJUDICATION_BATCH_PATH)

    lines = [
        "# 第五项B扩展试点第一批补证后结算更新草案",
        "",
        "本文仅供人工审核，汇总 #68 targeted supplement 之后对 #66 净裁量结构的更新草案；只作草案，不定档，不出分，不排名，不出总榜。",
        "",
        "## 总览",
        "",
        "| adjudication_id | person | pre_supplement_net_adjudication_summary | post_supplement_negative_intercept_status | status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    escape_cell(row.get("adjudication_id")),
                    escape_cell(row.get("person")),
                    escape_cell(row.get("pre_supplement_net_adjudication_summary")),
                    escape_cell(row.get("post_supplement_negative_intercept_status")),
                    escape_cell(row.get("status")),
                ]
            )
            + " |"
        )

    lines.extend(["", "## 逐人更新", ""])
    for row in rows:
        lines.extend(
            [
                f"### {row.get('person')}",
                "",
                f"- 预补证净裁量摘要：{row.get('pre_supplement_net_adjudication_summary') or ''}",
                f"- 补证证据ID：{join_list_cell(row.get('supplement_evidence_ids'))}",
                f"- 补证正向效应：{row.get('supplement_positive_effect_summary') or ''}",
                f"- 补证负向效应：{row.get('supplement_negative_effect_summary') or ''}",
                f"- role-class sweep 效应：{row.get('role_class_sweep_effect_summary') or ''}",
                f"- 负拦截状态：{row.get('post_supplement_negative_intercept_status') or ''}",
                f"- 相邻项切分摘要：{row.get('post_supplement_adjacent_item_split_summary') or ''}",
                f"- 规则压力摘要：{row.get('post_supplement_rule_pressure_summary') or ''}",
                f"- 补证后净裁量草案：{row.get('post_supplement_net_adjudication_draft') or ''}",
                f"- remaining gaps：{join_list_cell(row.get('remaining_gap_list'))}",
                f"- 状态：{row.get('status') or ''}",
                "",
            ]
        )

    lines.extend(["## 关门声明", "", "不定档，不出分，不排名，不出总榜。"])

    POST_SUPPLEMENT_ADJUDICATION_EXPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return POST_SUPPLEMENT_ADJUDICATION_EXPORT_PATH
