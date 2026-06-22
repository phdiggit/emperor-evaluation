from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path

import config_loaders
from i5b_markdown_display import (
    AppendixEntry,
    display_field_label,
    display_value,
    load_display_dictionary,
    render_appendix_page,
    render_markdown_table,
)


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "evidence_cache.sqlite"
I5B_SUBITEM = "第五项B"
MARKDOWN_VIEW_ROOT = ROOT / "exports" / "markdown_views"
I5B_HUMAN_REVIEW_ROOT = MARKDOWN_VIEW_ROOT / "第五项B" / "人工审核"
I5B_MACHINE_AUDIT_ROOT = MARKDOWN_VIEW_ROOT / "第五项B" / "机器审计"
I5B_EVIDENCE_CHAIN_ROOT = I5B_MACHINE_AUDIT_ROOT / "证据链"
I5B_HUMAN_EVIDENCE_CHAIN_ROOT = I5B_HUMAN_REVIEW_ROOT / "证据链"
NET_EVIDENCE_DIR = I5B_EVIDENCE_CHAIN_ROOT / "净证据池"
EVIDENCE_CARD_DIR = I5B_EVIDENCE_CHAIN_ROOT / "证据卡"
EVIDENCE_CLUSTER_DIR = I5B_EVIDENCE_CHAIN_ROOT / "证据簇"
SEARCH_PACKAGE_DIR = I5B_EVIDENCE_CHAIN_ROOT / "检索包"
APPENDIX_DIR = I5B_EVIDENCE_CHAIN_ROOT / "附录"
HUMAN_NET_EVIDENCE_DIR = I5B_HUMAN_EVIDENCE_CHAIN_ROOT / "净证据池"
HUMAN_EVIDENCE_CARD_DIR = I5B_HUMAN_EVIDENCE_CHAIN_ROOT / "证据卡"
HUMAN_EVIDENCE_CLUSTER_DIR = I5B_HUMAN_EVIDENCE_CHAIN_ROOT / "证据簇"
HUMAN_APPENDIX_DIR = I5B_HUMAN_EVIDENCE_CHAIN_ROOT / "附录"
MACHINE_NET_EVIDENCE_DIR = I5B_EVIDENCE_CHAIN_ROOT / "净证据池"
MACHINE_EVIDENCE_CARD_DIR = I5B_EVIDENCE_CHAIN_ROOT / "证据卡"
MACHINE_EVIDENCE_CLUSTER_DIR = I5B_EVIDENCE_CHAIN_ROOT / "证据簇"
MACHINE_SEARCH_PACKAGE_DIR = I5B_EVIDENCE_CHAIN_ROOT / "检索包"
MACHINE_APPENDIX_DIR = I5B_EVIDENCE_CHAIN_ROOT / "附录"
HUMAN_REVIEW_DECLARATION = "本文件为人工审核视图，隐藏机器追踪字段，只保留业务判断所需信息。"
MACHINE_AUDIT_DECLARATION = "本文件为机器审计视图，用于代码审查、数据追踪和回源定位，不作为人工业务审核主入口。"
CONTEXT_REQUIRED_STABLE_STATUSES = {"supplied", "source_verified"}
CONTEXT_REQUIRED_FIELDS = [
    "quote_context",
    "context_summary",
    "context_scope",
    "context_effect",
    "adjudication_bridge",
]
I5B_EVIDENCE_CONTEXT_HEADERS = [
    "quote_context",
    "context_summary",
    "context_scope",
    "context_required",
    "context_status",
    "context_effect",
    "source_locator",
    "adjudication_bridge",
    "context_review_queue",
]
MACHINE_LOCATOR_FIELDS = [
    "evidence_id",
    "source_id",
    "cluster_id",
    "linked_evidence_ids",
    "query_profile_id",
    "search_id",
]
HUMAN_DETAIL_FIELDS = [
    "quote_short",
    "quote_context",
    "context_summary",
    "summary",
    "source_locator",
    "adjudication_bridge",
    "cross_item_split",
]
HUMAN_LINK_FIELD_SOURCES = {
    "source_detail_link": ["quote_short", "source_locator"],
    "context_detail_link": ["quote_context", "context_summary", "context_scope"],
    "adjudication_bridge_detail_link": ["adjudication_bridge"],
    "cross_item_split_detail_link": ["cross_item_split"],
    "summary_detail_link": ["summary"],
}
HUMAN_LINK_TEXT = {
    "source_detail_link": "查看史料详情",
    "context_detail_link": "查看上下文",
    "adjudication_bridge_detail_link": "查看裁判桥接",
    "cross_item_split_detail_link": "查看剥离说明",
    "summary_detail_link": "查看摘要",
}

NET_EVIDENCE_CLUSTER_HEADERS = [
    "cluster_id",
    "person",
    "polarity",
    "cluster_type",
    "linked_evidence_ids",
    "candidate_strength",
    "upper_probe",
    "adjudication_status",
    "summary",
    "cross_item_split",
]
NET_EVIDENCE_CARD_HEADERS = [
    "evidence_id",
    "person",
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
HUMAN_NET_EVIDENCE_CLUSTER_HEADERS = [
    "person",
    "polarity",
    "candidate_strength",
    "adjudication_status",
    "summary_detail_link",
    "cross_item_split_detail_link",
]
HUMAN_NET_EVIDENCE_CARD_HEADERS = [
    "person",
    "polarity",
    "human_level",
    "trigger_family",
    "object_anchor",
    "evidence_role",
    "source_detail_link",
    "context_detail_link",
    "context_status",
    "context_effect",
    "context_review_queue",
    "adjudication_bridge_detail_link",
    "cross_item_split_detail_link",
    "scoring_effect",
    "adjudication_status",
]
I5B_EVIDENCE_CARD_HEADERS = [
    "evidence_id",
    "person",
    "item",
    "subitem",
    "polarity",
    "strength",
    "human_level",
    "source_id",
    "quote_short",
    "object_anchor",
    "evidence_role",
    "trigger_family",
    "mitigation_flag",
    "upper_bound_flag",
    "cluster_role",
    "cross_item_split",
    "scoring_effect",
    "verification_status",
    "adjudication_status",
]
HUMAN_EVIDENCE_CARD_HEADERS = [
    "person",
    "polarity",
    "strength",
    "human_level",
    "trigger_family",
    "object_anchor",
    "evidence_role",
    "source_detail_link",
    "context_detail_link",
    "context_status",
    "context_effect",
    "context_review_queue",
    "adjudication_bridge_detail_link",
    "cross_item_split_detail_link",
    "scoring_effect",
    "verification_status",
    "adjudication_status",
]
I5B_EVIDENCE_CLUSTER_HEADERS = [
    "cluster_id",
    "person",
    "item",
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
    "cross_item_split",
]
HUMAN_EVIDENCE_CLUSTER_HEADERS = [
    "person",
    "polarity",
    "candidate_strength",
    "adjudication_status",
    "summary_detail_link",
    "cross_item_split_detail_link",
]
I5B_SEARCH_LOG_HEADERS = [
    "search_id",
    "person",
    "item",
    "subitem",
    "polarity",
    "trigger_family",
    "query_terms",
    "result_status",
    "result_summary",
    "linked_evidence_id",
    "note",
]
I5B_QUERY_PROFILE_HEADERS = [
    "query_profile_id",
    "item",
    "subitem",
    "search_modes",
    "positive_terms",
    "negative_terms",
    "reversal_terms",
    "source_scopes",
    "thematic_anchor_targets",
    "cross_item_split_notes",
    "note",
]


def load_i5b_net_evidence_targets() -> list[tuple[str, Path]]:
    return config_loaders.get_i5b_net_evidence_targets()


I5B_NET_EVIDENCE_TARGETS = load_i5b_net_evidence_targets()


def _raw_rows(table: str, where_sql: str, params: list[object], order_by: str) -> list[dict[str, object]]:
    if not DB_PATH.exists():
        return []
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = list(
            connection.execute(
                f"""
                SELECT raw_json
                FROM {table}
                WHERE {where_sql}
                ORDER BY {order_by}
                """,
                params,
            )
        )
    return [json.loads(row["raw_json"]) for row in rows]


def _i5b_evidence_rows(person: str | None = None) -> list[dict[str, object]]:
    where = "subitem = ?"
    params: list[object] = [I5B_SUBITEM]
    if person is not None:
        where += " AND person = ?"
        params.append(person)
    return _raw_rows("evidence_cards", where, params, "person, polarity DESC, strength DESC, evidence_id")


def _i5b_cluster_rows(person: str | None = None) -> list[dict[str, object]]:
    where = "subitem = ?"
    params: list[object] = [I5B_SUBITEM]
    if person is not None:
        where += " AND person = ?"
        params.append(person)
    return _raw_rows("evidence_clusters", where, params, "person, polarity DESC, candidate_strength DESC, cluster_id")


def _i5b_search_rows() -> list[dict[str, object]]:
    return _raw_rows("search_logs", "subitem = ?", [I5B_SUBITEM], "person, polarity DESC, trigger_family, search_id")


def _i5b_query_profile_rows() -> list[dict[str, object]]:
    return _raw_rows("query_profiles", "subitem = ?", [I5B_SUBITEM], "query_profile_id")


def _add_cluster_linked_fields(cluster_rows: list[dict[str, object]], evidence_rows: list[dict[str, object]]) -> None:
    evidence_lookup = {str(row.get("evidence_id")): row for row in evidence_rows if row.get("evidence_id")}
    for cluster in cluster_rows:
        linked_ids = cluster.get("linked_evidence_ids") or []
        if isinstance(linked_ids, str):
            try:
                linked_ids = json.loads(linked_ids)
            except json.JSONDecodeError:
                linked_ids = [linked_ids]
        linked_rows = [evidence_lookup[str(evidence_id)] for evidence_id in linked_ids if str(evidence_id) in evidence_lookup]
        cluster["linked_object_anchors"] = _unique_join(linked_rows, "object_anchor")
        cluster["linked_evidence_roles"] = _unique_join(linked_rows, "evidence_role")


def _unique_join(rows: list[dict[str, object]], field: str) -> list[str]:
    values: list[str] = []
    for row in rows:
        value = row.get(field)
        if not isinstance(value, str):
            continue
        cleaned = value.strip()
        if cleaned and cleaned not in values:
            values.append(cleaned)
    return values


def _is_filled(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _is_context_required(row: dict[str, object]) -> bool:
    value = row.get("context_required")
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return False


def _add_context_review_queue(rows: list[dict[str, object]]) -> None:
    for row in rows:
        if not _is_context_required(row):
            continue
        context_status = str(row.get("context_status") or "").strip()
        missing_required_field = any(not _is_filled(row.get(field)) for field in CONTEXT_REQUIRED_FIELDS)
        if context_status not in CONTEXT_REQUIRED_STABLE_STATUSES or missing_required_field:
            row["context_review_queue"] = "needs_context_source_review"


def _headers_with_context(base_headers: list[str], rows: list[dict[str, object]]) -> list[str]:
    if not any(any(_is_filled(row.get(field)) for field in I5B_EVIDENCE_CONTEXT_HEADERS) for row in rows):
        return base_headers
    return base_headers + [field for field in I5B_EVIDENCE_CONTEXT_HEADERS if field not in base_headers]


def _slug(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "-", value.strip().lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "appendix"


def _escape_table_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _row_anchor(row: dict[str, object], row_id_fields: tuple[str, ...], index: int) -> str:
    for field in row_id_fields:
        if row.get(field):
            return _slug(str(row[field]))
    for field in MACHINE_LOCATOR_FIELDS:
        if row.get(field):
            return _slug(str(row[field]))
    return f"row-{index}"


def _machine_locator_text(row: dict[str, object]) -> str:
    lines: list[str] = []
    for field in MACHINE_LOCATOR_FIELDS:
        value = row.get(field)
        if _is_filled(value):
            if isinstance(value, (list, dict)):
                rendered = json.dumps(value, ensure_ascii=False)
            else:
                rendered = str(value)
            lines.append(f"{field}: {rendered}")
    return "\n".join(lines) if lines else "无机器定位字段。"


def _human_link_cell(
    row: dict[str, object],
    *,
    virtual_field: str,
    row_anchor: str,
    appendix_relative_path: str,
) -> str:
    source_fields = HUMAN_LINK_FIELD_SOURCES[virtual_field]
    if not any(_is_filled(row.get(field)) for field in source_fields):
        return ""
    text = HUMAN_LINK_TEXT[virtual_field]
    return f"[{text}]({appendix_relative_path}#{row_anchor})"


def _render_human_table(
    rows: list[dict[str, object]],
    headers: list[str],
    *,
    row_id_fields: tuple[str, ...],
    appendix_relative_path: str,
    config: dict[str, object],
) -> list[str]:
    labels = [display_field_label(header, config) for header in headers]
    lines = [
        "| " + " | ".join(labels) + " |",
        "| " + " | ".join("---" for _ in labels) + " |",
    ]
    for index, row in enumerate(rows, start=1):
        row_anchor = _row_anchor(row, row_id_fields, index)
        cells: list[str] = []
        for header in headers:
            if header in HUMAN_LINK_FIELD_SOURCES:
                cells.append(_human_link_cell(row, virtual_field=header, row_anchor=row_anchor, appendix_relative_path=appendix_relative_path))
            else:
                cells.append(_escape_table_cell(display_value(row.get(header), config)))
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def _appendix_section(lines: list[str], heading: str, value: object) -> None:
    if not _is_filled(value):
        return
    if isinstance(value, (list, dict)):
        rendered = json.dumps(value, ensure_ascii=False, indent=2)
    else:
        rendered = str(value)
    lines.extend(["", f"### {heading}", "", "```text", rendered, "```"])


def _human_row_title(row: dict[str, object], fallback: str) -> str:
    parts = [
        str(row.get("person") or "").strip(),
        str(row.get("trigger_family") or row.get("cluster_type") or "").strip(),
        str(row.get("object_anchor") or "").strip(),
    ]
    title = " / ".join(part for part in parts if part)
    return title or fallback


def _render_human_appendix_page(
    title: str,
    row_groups: list[tuple[str, list[dict[str, object]], tuple[str, ...]]],
) -> str:
    lines = [f"# {title}", ""]
    has_entries = False
    for section_name, rows, row_id_fields in row_groups:
        for index, row in enumerate(rows, start=1):
            has_entries = True
            anchor = _row_anchor(row, row_id_fields, index)
            lines.extend(["", f"## {anchor}", "", f"史料详情：{_human_row_title(row, section_name)}"])
            _appendix_section(lines, "短摘", row.get("quote_short"))
            _appendix_section(lines, "上下文摘录", row.get("quote_context"))
            _appendix_section(lines, "上下文摘要", row.get("context_summary"))
            _appendix_section(lines, "摘要", row.get("summary"))
            _appendix_section(lines, "来源定位", row.get("source_locator"))
            _appendix_section(lines, "裁判桥接说明", row.get("adjudication_bridge"))
            _appendix_section(lines, "相邻项剥离说明", row.get("cross_item_split"))
            _appendix_section(lines, "机器定位信息", _machine_locator_text(row))
            lines.append("")
    if not has_entries:
        lines.extend(["无人工审核附录。", ""])
    return "\n".join(lines).rstrip() + "\n"


def _relative_appendix_path(export_path: Path, appendix_path: Path) -> str:
    return Path(os.path.relpath(appendix_path, export_path.parent)).as_posix()


def _write_appendix(path: Path, title: str, entries: list[AppendixEntry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_appendix_page(title, entries).rstrip() + "\n", encoding="utf-8")


def _write_table_export(
    export_path: Path,
    appendix_path: Path,
    *,
    title: str,
    intro: str,
    sections: list[tuple[str, list[str], list[dict[str, object]], tuple[str, ...]]],
) -> Path:
    export_path.parent.mkdir(parents=True, exist_ok=True)
    config = load_display_dictionary()
    appendix_entries: list[AppendixEntry] = []
    appendix_relative_path = _relative_appendix_path(export_path, appendix_path)
    lines = [f"# {title}", "", intro, ""]
    for heading, headers, rows, row_id_fields in sections:
        lines.extend(
            [
                f"## {heading}",
                "",
                *render_markdown_table(
                    rows,
                    headers,
                    row_id_fields=row_id_fields,
                    appendix_relative_path=appendix_relative_path,
                    appendix_entries=appendix_entries,
                    config=config,
                ),
                "",
            ]
        )
    export_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    _write_appendix(appendix_path, f"{title}长字段附录", appendix_entries)
    return export_path


def _write_human_review_export(
    export_path: Path,
    appendix_path: Path,
    *,
    title: str,
    intro: str,
    sections: list[tuple[str, list[str], list[dict[str, object]], tuple[str, ...]]],
) -> Path:
    export_path.parent.mkdir(parents=True, exist_ok=True)
    config = load_display_dictionary()
    appendix_relative_path = _relative_appendix_path(export_path, appendix_path)
    lines = [f"# {title}", "", HUMAN_REVIEW_DECLARATION, "", intro, ""]
    appendix_groups: list[tuple[str, list[dict[str, object]], tuple[str, ...]]] = []
    for heading, headers, rows, row_id_fields in sections:
        appendix_groups.append((heading, rows, row_id_fields))
        lines.extend(
            [
                f"## {heading}",
                "",
                *_render_human_table(
                    rows,
                    headers,
                    row_id_fields=row_id_fields,
                    appendix_relative_path=appendix_relative_path,
                    config=config,
                ),
                "",
            ]
        )
    export_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    appendix_path.parent.mkdir(parents=True, exist_ok=True)
    appendix_path.write_text(_render_human_appendix_page(f"{title}史料详情附录", appendix_groups), encoding="utf-8")
    return export_path


def _remove_legacy_net_evidence_export(person: str, export_path: Path) -> None:
    legacy_path = MARKDOWN_VIEW_ROOT / f"第五项B_{person}净证据池.md"
    if legacy_path != export_path and legacy_path.exists():
        legacy_path.unlink()


def export_i5b_net_evidence_pool(person: str, export_path: Path) -> Path:
    cluster_rows = _i5b_cluster_rows(person)
    evidence_rows = _i5b_evidence_rows(person)
    _add_context_review_queue(evidence_rows)
    _add_cluster_linked_fields(cluster_rows, evidence_rows)
    appendix_path = APPENDIX_DIR / f"{person}_净证据池长字段附录.md"
    result = _write_table_export(
        export_path,
        appendix_path,
        title=f"第五项B_{person}净证据池",
        intro=(
            f"{MACHINE_AUDIT_DECLARATION}\n\n"
            "本文件为定档前净证据池视图；本机器审计全字段版本只汇总已回源原子证据与证据组裁量候选，"
            "不代表最终档位、得分或排名。"
        ),
        sections=[
            ("证据组裁量结论", NET_EVIDENCE_CLUSTER_HEADERS, cluster_rows, ("cluster_id",)),
            ("原子证据卡", _headers_with_context(NET_EVIDENCE_CARD_HEADERS, evidence_rows), evidence_rows, ("evidence_id",)),
        ],
    )
    _remove_legacy_net_evidence_export(person, export_path)
    return result


def export_i5b_human_review_net_evidence_pool(person: str) -> Path:
    cluster_rows = _i5b_cluster_rows(person)
    evidence_rows = _i5b_evidence_rows(person)
    _add_context_review_queue(evidence_rows)
    _add_cluster_linked_fields(cluster_rows, evidence_rows)
    export_path = HUMAN_NET_EVIDENCE_DIR / f"第五项B_{person}人工审核净证据池.md"
    appendix_path = HUMAN_APPENDIX_DIR / f"{person}_人工审核史料详情附录.md"
    return _write_human_review_export(
        export_path,
        appendix_path,
        title=f"第五项B_{person}人工审核净证据池",
        intro="本文件是定档前人工业务审核主表；机器定位字段隐藏在主表外，可从附录“机器定位信息”或机器审计视图追溯。",
        sections=[
            ("证据组裁量结论", HUMAN_NET_EVIDENCE_CLUSTER_HEADERS, cluster_rows, ("cluster_id",)),
            ("原子证据卡", HUMAN_NET_EVIDENCE_CARD_HEADERS, evidence_rows, ("evidence_id",)),
        ],
    )


def export_i5b_machine_audit_net_evidence_pool(person: str) -> Path:
    cluster_rows = _i5b_cluster_rows(person)
    evidence_rows = _i5b_evidence_rows(person)
    _add_context_review_queue(evidence_rows)
    _add_cluster_linked_fields(cluster_rows, evidence_rows)
    export_path = MACHINE_NET_EVIDENCE_DIR / f"第五项B_{person}机器审计净证据池.md"
    appendix_path = MACHINE_APPENDIX_DIR / f"{person}_机器审计净证据池长字段附录.md"
    return _write_table_export(
        export_path,
        appendix_path,
        title=f"第五项B_{person}机器审计净证据池",
        intro=MACHINE_AUDIT_DECLARATION,
        sections=[
            ("证据组裁量结论", NET_EVIDENCE_CLUSTER_HEADERS, cluster_rows, ("cluster_id",)),
            ("原子证据卡", _headers_with_context(NET_EVIDENCE_CARD_HEADERS, evidence_rows), evidence_rows, ("evidence_id",)),
        ],
    )


def export_i5b_evidence_cards_index() -> Path:
    export_path = EVIDENCE_CARD_DIR / "第五项B证据卡索引.md"
    appendix_path = APPENDIX_DIR / "第五项B证据卡长字段附录.md"
    rows = _i5b_evidence_rows()
    _add_context_review_queue(rows)
    return _write_table_export(
        export_path,
        appendix_path,
        title="第五项B证据卡索引",
        intro=f"{MACHINE_AUDIT_DECLARATION}\n\n本文件只展示第五项B证据卡，不改变原始证据数据、评分或裁判语义。",
        sections=[("证据卡", _headers_with_context(I5B_EVIDENCE_CARD_HEADERS, rows), rows, ("evidence_id",))],
    )


def export_i5b_human_review_evidence_cards_index() -> Path:
    export_path = HUMAN_EVIDENCE_CARD_DIR / "第五项B人工审核证据卡索引.md"
    appendix_path = HUMAN_APPENDIX_DIR / "第五项B人工审核证据卡史料详情附录.md"
    rows = _i5b_evidence_rows()
    _add_context_review_queue(rows)
    return _write_human_review_export(
        export_path,
        appendix_path,
        title="第五项B人工审核证据卡索引",
        intro="本文件是证据卡人工业务审核主表；机器定位字段隐藏在主表外，可从附录“机器定位信息”或机器审计视图追溯。",
        sections=[("证据卡", HUMAN_EVIDENCE_CARD_HEADERS, rows, ("evidence_id",))],
    )


def export_i5b_machine_audit_evidence_cards_index() -> Path:
    export_path = MACHINE_EVIDENCE_CARD_DIR / "第五项B机器审计证据卡索引.md"
    appendix_path = MACHINE_APPENDIX_DIR / "第五项B机器审计证据卡长字段附录.md"
    rows = _i5b_evidence_rows()
    _add_context_review_queue(rows)
    return _write_table_export(
        export_path,
        appendix_path,
        title="第五项B机器审计证据卡索引",
        intro=MACHINE_AUDIT_DECLARATION,
        sections=[("证据卡", _headers_with_context(I5B_EVIDENCE_CARD_HEADERS, rows), rows, ("evidence_id",))],
    )


def export_i5b_evidence_clusters_index() -> Path:
    export_path = EVIDENCE_CLUSTER_DIR / "第五项B证据簇索引.md"
    appendix_path = APPENDIX_DIR / "第五项B证据簇长字段附录.md"
    evidence_rows = _i5b_evidence_rows()
    cluster_rows = _i5b_cluster_rows()
    _add_cluster_linked_fields(cluster_rows, evidence_rows)
    return _write_table_export(
        export_path,
        appendix_path,
        title="第五项B证据簇索引",
        intro=f"{MACHINE_AUDIT_DECLARATION}\n\n本文件只展示第五项B证据簇与关联证据摘要，不改变证据簇裁判结论。",
        sections=[("证据簇", I5B_EVIDENCE_CLUSTER_HEADERS, cluster_rows, ("cluster_id",))],
    )


def export_i5b_human_review_evidence_clusters_index() -> Path:
    export_path = HUMAN_EVIDENCE_CLUSTER_DIR / "第五项B人工审核证据簇索引.md"
    appendix_path = HUMAN_APPENDIX_DIR / "第五项B人工审核证据簇史料详情附录.md"
    evidence_rows = _i5b_evidence_rows()
    cluster_rows = _i5b_cluster_rows()
    _add_cluster_linked_fields(cluster_rows, evidence_rows)
    return _write_human_review_export(
        export_path,
        appendix_path,
        title="第五项B人工审核证据簇索引",
        intro="本文件是证据簇人工业务审核主表；机器定位字段隐藏在主表外，可从附录“机器定位信息”或机器审计视图追溯。",
        sections=[("证据簇", HUMAN_EVIDENCE_CLUSTER_HEADERS, cluster_rows, ("cluster_id",))],
    )


def export_i5b_machine_audit_evidence_clusters_index() -> Path:
    export_path = MACHINE_EVIDENCE_CLUSTER_DIR / "第五项B机器审计证据簇索引.md"
    appendix_path = MACHINE_APPENDIX_DIR / "第五项B机器审计证据簇长字段附录.md"
    evidence_rows = _i5b_evidence_rows()
    cluster_rows = _i5b_cluster_rows()
    _add_cluster_linked_fields(cluster_rows, evidence_rows)
    return _write_table_export(
        export_path,
        appendix_path,
        title="第五项B机器审计证据簇索引",
        intro=MACHINE_AUDIT_DECLARATION,
        sections=[("证据簇", I5B_EVIDENCE_CLUSTER_HEADERS, cluster_rows, ("cluster_id",))],
    )


def export_i5b_search_package_index() -> tuple[Path, Path]:
    query_profile_path = SEARCH_PACKAGE_DIR / "第五项B检索包索引.md"
    query_profile_appendix_path = APPENDIX_DIR / "第五项B检索包长字段附录.md"
    search_log_path = SEARCH_PACKAGE_DIR / "第五项B检索线索索引.md"
    search_log_appendix_path = APPENDIX_DIR / "第五项B检索线索长字段附录.md"
    _write_table_export(
        query_profile_path,
        query_profile_appendix_path,
        title="第五项B检索包索引",
        intro=f"{MACHINE_AUDIT_DECLARATION}\n\n本文件展示第五项B检索包配置全字段视图，仅用于回源定位与检索复核。",
        sections=[("检索包", I5B_QUERY_PROFILE_HEADERS, _i5b_query_profile_rows(), ("query_profile_id",))],
    )
    _write_table_export(
        search_log_path,
        search_log_appendix_path,
        title="第五项B检索线索索引",
        intro=f"{MACHINE_AUDIT_DECLARATION}\n\n本文件展示第五项B检索线索及回源状态；未回源材料不得入分。",
        sections=[("检索线索", I5B_SEARCH_LOG_HEADERS, _i5b_search_rows(), ("search_id",))],
    )
    legacy_search_log_path = MARKDOWN_VIEW_ROOT / "第五项B三人试点检索线索.md"
    if legacy_search_log_path.exists():
        legacy_search_log_path.unlink()
    return query_profile_path, search_log_path


def export_i5b_machine_audit_search_package_index() -> tuple[Path, Path]:
    query_profile_path = MACHINE_SEARCH_PACKAGE_DIR / "第五项B机器审计检索包索引.md"
    query_profile_appendix_path = MACHINE_APPENDIX_DIR / "第五项B机器审计检索包长字段附录.md"
    search_log_path = MACHINE_SEARCH_PACKAGE_DIR / "第五项B机器审计检索线索索引.md"
    search_log_appendix_path = MACHINE_APPENDIX_DIR / "第五项B机器审计检索线索长字段附录.md"
    _write_table_export(
        query_profile_path,
        query_profile_appendix_path,
        title="第五项B机器审计检索包索引",
        intro=MACHINE_AUDIT_DECLARATION,
        sections=[("检索包", I5B_QUERY_PROFILE_HEADERS, _i5b_query_profile_rows(), ("query_profile_id",))],
    )
    _write_table_export(
        search_log_path,
        search_log_appendix_path,
        title="第五项B机器审计检索线索索引",
        intro=MACHINE_AUDIT_DECLARATION,
        sections=[("检索线索", I5B_SEARCH_LOG_HEADERS, _i5b_search_rows(), ("search_id",))],
    )
    return query_profile_path, search_log_path


def export_i5b_review_profile_views() -> list[Path]:
    paths: list[Path] = []
    for person, _ in I5B_NET_EVIDENCE_TARGETS:
        paths.append(export_i5b_human_review_net_evidence_pool(person))
        paths.append(export_i5b_machine_audit_net_evidence_pool(person))
    paths.append(export_i5b_human_review_evidence_cards_index())
    paths.append(export_i5b_human_review_evidence_clusters_index())
    paths.append(export_i5b_machine_audit_evidence_cards_index())
    paths.append(export_i5b_machine_audit_evidence_clusters_index())
    paths.extend(export_i5b_machine_audit_search_package_index())
    return paths
