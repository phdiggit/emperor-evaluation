from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import config_loaders
from shared.export_md_scaffold import escape_cell, join_list_cell, read_jsonl
from i5b_markdown_display import (
    AppendixEntry,
    display_field_label,
    display_value,
    human_review_table_fields,
    load_display_dictionary,
    render_appendix_page,
    render_markdown_kv,
    render_markdown_table,
)


ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "evidence_cache.sqlite"
I5B_SUBITEM = "第五项B"
MARKDOWN_VIEW_ROOT = ROOT / "exports" / "markdown_views"
I5B_EVIDENCE_CHAIN_ROOT = MARKDOWN_VIEW_ROOT / "第五项B" / "机器审计" / "证据链"
I5B_HUMAN_AUTO_CHAIN_ROOT = MARKDOWN_VIEW_ROOT / "第五项B" / "人工审核" / "自动裁判链"
I5B_EVIDENCE_CARD_DIR = I5B_EVIDENCE_CHAIN_ROOT / "证据卡"
I5B_EVIDENCE_CLUSTER_DIR = I5B_EVIDENCE_CHAIN_ROOT / "证据簇"
I5B_APPENDIX_DIR = I5B_EVIDENCE_CHAIN_ROOT / "附录"
EXPANDED_BATCH1_REVIEW_EXPORT_PATH = I5B_EVIDENCE_CARD_DIR / "第五项B扩展试点第一批证据卡与证据簇草案.md"
EXPANDED_BATCH1_CLUSTER_ADJUDICATION_BATCH_PATH = ROOT / "data" / "adjudication_batches" / "i5b_expanded_pilot_batch1_cluster_adjudication_20260619.jsonl"
EXPANDED_BATCH1_CLUSTER_ADJUDICATION_EXPORT_PATH = I5B_EVIDENCE_CLUSTER_DIR / "第五项B扩展试点第一批证据簇结算草案.md"
TARGETED_SUPPLEMENT_SOURCE_BATCH_PATH = ROOT / "data" / "source_batches" / "i5b_expanded_pilot_batch1_targeted_supplement_20260619.jsonl"
TARGETED_SUPPLEMENT_EVIDENCE_BATCH_PATH = ROOT / "data" / "evidence_card_batches" / "i5b_expanded_pilot_batch1_targeted_supplement_20260619.jsonl"
TARGETED_SUPPLEMENT_EXPORT_PATH = I5B_HUMAN_AUTO_CHAIN_ROOT / "试点闭环" / "第五项B扩展试点第一批定向补证.md"
TARGETED_SUPPLEMENT_ROLE_CLASS_SWEEP_BATCH_PATH = ROOT / "data" / "sweep_batches" / "i5b_yongzheng_role_class_sweep_20260619.jsonl"
POST_SUPPLEMENT_ADJUDICATION_BATCH_PATH = ROOT / "data" / "adjudication_batches" / "i5b_expanded_pilot_batch1_post_supplement_adjudication_20260619.jsonl"
POST_SUPPLEMENT_ADJUDICATION_EXPORT_PATH = I5B_HUMAN_AUTO_CHAIN_ROOT / "试点闭环" / "第五项B扩展试点第一批补证后结算更新草案.md"
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


def _human_display_config() -> dict[str, object]:
    config = dict(load_display_dictionary())
    config["keep_machine_field_name"] = False
    labels = dict(config.get("field_labels") or {})
    labels.update(
        {
            "evidence_id": "证据编号",
            "source_id": "来源编号",
            "cluster_id": "证据簇编号",
            "linked_evidence_ids": "关联证据编号",
        }
    )
    config["field_labels"] = labels
    return config


def _label(field: str, config: dict[str, object]) -> str:
    return display_field_label(field, config)


def _value(value: object, config: dict[str, object]) -> str:
    return display_value(value, config)


def _list_value(value: object, config: dict[str, object]) -> str:
    if isinstance(value, list):
        return "；".join(_value(item, config) for item in value)
    return _value(value, config)


def _table(headers: list[str], rows: list[dict[str, object]], config: dict[str, object]) -> list[str]:
    lines = [
        "| " + " | ".join(_label(header, config) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(escape_cell(_value(row.get(header), config)) for header in headers) + " |")
    return lines


def _human_table_fields(table_key: str, config: dict[str, object]) -> list[str]:
    return human_review_table_fields(table_key, config)


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
        "本文件为机器审计视图，用于代码审查、数据追踪和回源定位，不作为人工业务审核主入口。",
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
        "本文件为机器审计视图，用于代码审查、数据追踪和回源定位，不作为人工业务审核主入口。",
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
    display_config = _human_display_config()

    source_rows = read_jsonl(TARGETED_SUPPLEMENT_SOURCE_BATCH_PATH)
    evidence_rows = read_jsonl(TARGETED_SUPPLEMENT_EVIDENCE_BATCH_PATH)
    sweep_rows = read_jsonl(TARGETED_SUPPLEMENT_ROLE_CLASS_SWEEP_BATCH_PATH)
    person_counts = Counter(row.get("person") for row in evidence_rows)

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

    lines.extend(
        [
            "",
            "## 定向补证来源",
            "",
            *_table(_human_table_fields("targeted_supplement_sources", display_config), source_rows, display_config),
        ]
    )

    lines.extend(
        [
            "",
            "## 定向补证证据卡",
            "",
            *_table(_human_table_fields("targeted_supplement_evidence_cards", display_config), evidence_rows, display_config),
        ]
    )

    lines.extend([
        "",
        "## 雍正 role-class sweep / 防漏扫查",
        "",
        *_table(TARGETED_SUPPLEMENT_ROLE_CLASS_SWEEP_HEADERS, sweep_rows, display_config),
    ])

    lines.extend(["", "结语：不定档，不出分，不排名，不出总榜。", ""])

    TARGETED_SUPPLEMENT_EXPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return TARGETED_SUPPLEMENT_EXPORT_PATH


def export_expanded_i5b_batch1_post_supplement_adjudication() -> Path:
    POST_SUPPLEMENT_ADJUDICATION_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    display_config = _human_display_config()

    rows = read_jsonl(POST_SUPPLEMENT_ADJUDICATION_BATCH_PATH)

    lines = [
        "# 第五项B扩展试点第一批补证后结算更新草案",
        "",
        "本文仅供人工审核，汇总 #68 targeted supplement 之后对 #66 净裁量结构的更新草案；只作草案，不定档，不出分，不排名，不出总榜。",
        "",
        "## 总览",
        "",
        *_table(
            [
                "adjudication_id",
                "person",
                "pre_supplement_net_adjudication_summary",
                "post_supplement_negative_intercept_status",
                "status",
            ],
            rows,
            display_config,
        ),
    ]

    lines.extend(["", "## 逐人更新", ""])
    for row in rows:
        lines.extend(
            [
                f"### {row.get('person')}",
                "",
                f"- {_label('pre_supplement_net_adjudication_summary', display_config)}：{_value(row.get('pre_supplement_net_adjudication_summary'), display_config)}",
                f"- {_label('supplement_evidence_ids', display_config)}：{_list_value(row.get('supplement_evidence_ids'), display_config)}",
                f"- {_label('supplement_positive_effect_summary', display_config)}：{_value(row.get('supplement_positive_effect_summary'), display_config)}",
                f"- {_label('supplement_negative_effect_summary', display_config)}：{_value(row.get('supplement_negative_effect_summary'), display_config)}",
                f"- {_label('role_class_sweep_effect_summary', display_config)}：{_value(row.get('role_class_sweep_effect_summary'), display_config)}",
                f"- {_label('post_supplement_negative_intercept_status', display_config)}：{_value(row.get('post_supplement_negative_intercept_status'), display_config)}",
                f"- {_label('post_supplement_adjacent_item_split_summary', display_config)}：{_value(row.get('post_supplement_adjacent_item_split_summary'), display_config)}",
                f"- {_label('post_supplement_rule_pressure_summary', display_config)}：{_value(row.get('post_supplement_rule_pressure_summary'), display_config)}",
                f"- {_label('post_supplement_net_adjudication_draft', display_config)}：{_value(row.get('post_supplement_net_adjudication_draft'), display_config)}",
                f"- {_label('remaining_gap_list', display_config)}：{_list_value(row.get('remaining_gap_list'), display_config)}",
                f"- {_label('status', display_config)}：{_value(row.get('status'), display_config)}",
                "",
            ]
        )

    lines.extend(["## 关门声明", "", "不定档，不出分，不排名，不出总榜。"])

    POST_SUPPLEMENT_ADJUDICATION_EXPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return POST_SUPPLEMENT_ADJUDICATION_EXPORT_PATH
