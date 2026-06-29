from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from export.export_i5b_auto_adjudication import export_auto_adjudication
from export.export_i5b_net_evidence import (
    I5B_NET_EVIDENCE_TARGETS,
    export_i5b_evidence_cards_index,
    export_i5b_evidence_clusters_index,
    export_i5b_net_evidence_pool,
    export_i5b_review_profile_views,
    export_i5b_search_package_index,
)
from export.export_project_doc_views import (
    export_expanded_i5b_candidate_pool,
    export_global_scale_decision_brief,
)
from shared import config_loaders
from shared.export_md_scaffold import (
    ExportStep,
    escape_cell,
    export_db_table_markdown,
    join_list_cell,
    read_jsonl,
    run_export_steps,
    summarize_unique_values,
)


ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "evidence_cache.sqlite"
MARKDOWN_VIEW_ROOT = ROOT / "exports" / "markdown_views"
SUMMARY_EXPORT_ROOT = MARKDOWN_VIEW_ROOT / "综合汇总"
I5B_MACHINE_SEARCH_PACKAGE_ROOT = MARKDOWN_VIEW_ROOT / "第五项B" / "机器审计" / "证据链" / "检索包"
EXPORT_PATH = SUMMARY_EXPORT_ROOT / "史料证据卡索引.md"
SEARCH_LOGS_EXPORT_PATH = I5B_MACHINE_SEARCH_PACKAGE_ROOT / "第五项B当前人物组检索线索.md"
DEFAULT_SEARCH_LOGS_EXPORT_PATH = SEARCH_LOGS_EXPORT_PATH
EVIDENCE_CLUSTERS_EXPORT_PATH = SUMMARY_EXPORT_ROOT / "证据组裁量索引.md"
THEMATIC_ANCHORS_EXPORT_PATH = SUMMARY_EXPORT_ROOT / "专题锚点索引.md"
QUERY_PROFILES_EXPORT_PATH = SUMMARY_EXPORT_ROOT / "项目检索包索引.md"
@dataclass(frozen=True)
class ExportProfile:
    description: str
    steps: tuple[str, ...]


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


def load_i5b_active_targets() -> list[str]:
    return config_loaders.get_i5b_active_person_targets()


def load_i5b_trial_targets() -> list[str]:
    return config_loaders.get_i5b_trial_targets()


I5B_ACTIVE_TARGETS = load_i5b_active_targets()
I5B_SUBITEM = "第五项B"


def safe_filename_part(value: object) -> str:
    return str(value).replace("/", "_").replace("\\", "_").strip()


def active_search_logs_export_path(workflow_config: dict[str, object]) -> Path:
    if SEARCH_LOGS_EXPORT_PATH != DEFAULT_SEARCH_LOGS_EXPORT_PATH:
        return SEARCH_LOGS_EXPORT_PATH
    subitem = safe_filename_part(workflow_config.get("subitem") or I5B_SUBITEM)
    group_label = safe_filename_part(workflow_config.get("group_label") or workflow_config.get("group") or "当前人物组")
    return DEFAULT_SEARCH_LOGS_EXPORT_PATH.parent / f"{subitem}{group_label}检索线索.md"


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
    workflow_config = config_loaders.get_i5b_active_workflow_config()
    targets = list(workflow_config.get("targets") or [])
    group_label = str(workflow_config.get("group_label") or workflow_config.get("group") or "当前人物组")
    export_path = active_search_logs_export_path(workflow_config)
    export_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    if DB_PATH.exists() and targets:
        placeholders = ", ".join("?" for _ in targets)
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
                    [I5B_SUBITEM, *targets],
                )
            )

    lines = [
        f"# {I5B_SUBITEM}{group_label}检索线索",
        "",
        "本文件为机器审计视图，用于代码审查、数据追踪和回源定位，不作为人工业务审核主入口。",
        "",
        "本文件导出待回源检索线索；未回源材料不得入分。",
        "",
        f"- **活动人物组**：{group_label}",
        f"- **覆盖人物**：{'、'.join(str(person) for person in targets)}",
        "",
        "| " + " | ".join(SEARCH_LOG_HEADERS) + " |",
        "| " + " | ".join("---" for _ in SEARCH_LOG_HEADERS) + " |",
    ]

    for row in rows:
        lines.append("| " + " | ".join(escape_cell(row[header]) for header in SEARCH_LOG_HEADERS) + " |")

    export_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return export_path


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


def build_all_export_steps() -> dict[str, ExportStep]:
    return {
        "evidence_index": ExportStep("evidence_index", export_markdown),
        "search_logs": ExportStep("search_logs", export_search_logs_markdown),
        "evidence_clusters": ExportStep("evidence_clusters", export_evidence_clusters_markdown),
        "thematic_anchors": ExportStep(
            "thematic_anchors",
            lambda: export_generic_markdown(
                THEMATIC_ANCHORS_EXPORT_PATH,
                "专题锚点索引",
                "thematic_anchors",
                THEMATIC_ANCHOR_HEADERS,
                "anchor_id",
            ),
        ),
        "query_profiles": ExportStep(
            "query_profiles",
            lambda: export_generic_markdown(
                QUERY_PROFILES_EXPORT_PATH,
                "项目检索包索引",
                "query_profiles",
                QUERY_PROFILE_HEADERS,
                "query_profile_id",
            ),
        ),
        **{
            f"net_evidence_{person}": ExportStep(
                f"net_evidence_{person}",
                lambda person=person, net_evidence_path=net_evidence_path: export_i5b_net_evidence_pool(
                    person, net_evidence_path
                ),
            )
            for person, net_evidence_path in I5B_NET_EVIDENCE_TARGETS
        },
        "i5b_evidence_cards_index": ExportStep("i5b_evidence_cards_index", export_i5b_evidence_cards_index),
        "i5b_evidence_clusters_index": ExportStep("i5b_evidence_clusters_index", export_i5b_evidence_clusters_index),
        "i5b_search_package_index": ExportStep("i5b_search_package_index", export_i5b_search_package_index),
        "i5b_review_profile_views": ExportStep("i5b_review_profile_views", export_i5b_review_profile_views),
        "global_scale_decision_brief": ExportStep("global_scale_decision_brief", export_global_scale_decision_brief),
        "expanded_i5b_candidate_pool": ExportStep("expanded_i5b_candidate_pool", export_expanded_i5b_candidate_pool),
        "auto_adjudication": ExportStep("auto_adjudication", export_auto_adjudication),
    }


ALL_EXPORT_STEPS = build_all_export_steps()
I5B_CORE_STEPS = (
    "search_logs",
    *(f"net_evidence_{person}" for person, _net_evidence_path in I5B_NET_EVIDENCE_TARGETS),
    "i5b_evidence_cards_index",
    "i5b_evidence_clusters_index",
    "i5b_search_package_index",
    "i5b_review_profile_views",
)

EXPORT_PROFILES: dict[str, ExportProfile] = {
    "main": ExportProfile(
        "综合入口和全局索引，默认运行。",
        ("evidence_index", "evidence_clusters", "thematic_anchors", "query_profiles"),
    ),
    "i5b-core": ExportProfile(
        "第五项B常规证据链和人工审核细节导出。",
        I5B_CORE_STEPS,
    ),
    "i5b-auto": ExportProfile(
        "第五项B自动结算导出。",
        ("auto_adjudication",),
    ),
    "project-docs": ExportProfile(
        "项目级文档导出。",
        ("global_scale_decision_brief", "expanded_i5b_candidate_pool"),
    ),
    "all": ExportProfile(
        "显式全量导出，保留旧行为。",
        ("*",),
    ),
}


def step_names_for_profile(profile_name: str) -> list[str]:
    profile = EXPORT_PROFILES[profile_name]
    if profile.steps == ("*",):
        return list(ALL_EXPORT_STEPS)
    return list(profile.steps)


def steps_for_profile(profile_name: str) -> list[ExportStep]:
    return [ALL_EXPORT_STEPS[name] for name in step_names_for_profile(profile_name)]


def print_profiles() -> None:
    for profile_name, profile in EXPORT_PROFILES.items():
        steps = ", ".join(step_names_for_profile(profile_name))
        print(f"{profile_name}: {profile.description}")
        print(f"  steps: {steps}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--profile",
        choices=tuple(EXPORT_PROFILES),
        default="main",
        help="export profile to run; defaults to main",
    )
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="list available export profiles without writing files",
    )
    args = parser.parse_args(argv)

    if args.list_profiles:
        print_profiles()
        return 0

    run_export_steps(steps_for_profile(args.profile))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
