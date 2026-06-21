from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import config_loaders
from i5b_markdown_display import (
    AppendixEntry,
    load_display_dictionary,
    render_appendix_page,
    render_markdown_table,
)


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "evidence_cache.sqlite"
I5B_SUBITEM = "第五项B"
MARKDOWN_VIEW_ROOT = ROOT / "exports" / "markdown_views"
I5B_EVIDENCE_CHAIN_ROOT = MARKDOWN_VIEW_ROOT / "第五项B" / "证据链"
NET_EVIDENCE_DIR = I5B_EVIDENCE_CHAIN_ROOT / "净证据池"
EVIDENCE_CARD_DIR = I5B_EVIDENCE_CHAIN_ROOT / "证据卡"
EVIDENCE_CLUSTER_DIR = I5B_EVIDENCE_CHAIN_ROOT / "证据簇"
SEARCH_PACKAGE_DIR = I5B_EVIDENCE_CHAIN_ROOT / "检索包"
APPENDIX_DIR = I5B_EVIDENCE_CHAIN_ROOT / "附录"

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


def _remove_legacy_net_evidence_export(person: str, export_path: Path) -> None:
    legacy_path = MARKDOWN_VIEW_ROOT / f"第五项B_{person}净证据池.md"
    if legacy_path != export_path and legacy_path.exists():
        legacy_path.unlink()


def export_i5b_net_evidence_pool(person: str, export_path: Path) -> Path:
    cluster_rows = _i5b_cluster_rows(person)
    evidence_rows = _i5b_evidence_rows(person)
    _add_cluster_linked_fields(cluster_rows, evidence_rows)
    appendix_path = APPENDIX_DIR / f"{person}_净证据池长字段附录.md"
    result = _write_table_export(
        export_path,
        appendix_path,
        title=f"第五项B_{person}净证据池",
        intro="本文件为定档前净证据池视图；只汇总已回源原子证据与证据组裁量候选，不代表最终档位、得分或排名。",
        sections=[
            ("证据组裁量结论", NET_EVIDENCE_CLUSTER_HEADERS, cluster_rows, ("cluster_id",)),
            ("原子证据卡", NET_EVIDENCE_CARD_HEADERS, evidence_rows, ("evidence_id",)),
        ],
    )
    _remove_legacy_net_evidence_export(person, export_path)
    return result


def export_i5b_evidence_cards_index() -> Path:
    export_path = EVIDENCE_CARD_DIR / "第五项B证据卡索引.md"
    appendix_path = APPENDIX_DIR / "第五项B证据卡长字段附录.md"
    rows = _i5b_evidence_rows()
    return _write_table_export(
        export_path,
        appendix_path,
        title="第五项B证据卡索引",
        intro="本文件只展示第五项B证据卡，不改变原始证据数据、评分或裁判语义。",
        sections=[("证据卡", I5B_EVIDENCE_CARD_HEADERS, rows, ("evidence_id",))],
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
        intro="本文件只展示第五项B证据簇与关联证据摘要，不改变证据簇裁判结论。",
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
        intro="本文件展示第五项B检索包配置视图，仅用于人工回源与检索复核。",
        sections=[("检索包", I5B_QUERY_PROFILE_HEADERS, _i5b_query_profile_rows(), ("query_profile_id",))],
    )
    _write_table_export(
        search_log_path,
        search_log_appendix_path,
        title="第五项B检索线索索引",
        intro="本文件展示第五项B检索线索及回源状态；未回源材料不得入分。",
        sections=[("检索线索", I5B_SEARCH_LOG_HEADERS, _i5b_search_rows(), ("search_id",))],
    )
    legacy_search_log_path = MARKDOWN_VIEW_ROOT / "第五项B三人试点检索线索.md"
    if legacy_search_log_path.exists():
        legacy_search_log_path.unlink()
    return query_profile_path, search_log_path
