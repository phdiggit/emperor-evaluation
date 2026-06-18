from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from export_i5b_auto_adjudication import export_auto_adjudication


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "evidence_cache.sqlite"
EXPORT_PATH = ROOT / "exports" / "markdown_views" / "史料证据卡索引.md"
SEARCH_LOGS_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "第五项B三人试点检索线索.md"
EVIDENCE_CLUSTERS_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "证据组裁量索引.md"
THEMATIC_ANCHORS_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "专题锚点索引.md"
QUERY_PROFILES_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "项目检索包索引.md"
GLOBAL_SCALE_BRIEF_DOC_PATH = ROOT / "docs" / "全局总标尺决策简报_讨论版.md"
GLOBAL_SCALE_BRIEF_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "全局总标尺决策简报_讨论版.md"

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
I5B_TRIAL_TARGETS = ["李世民", "刘秀", "刘庄"]
I5B_NET_EVIDENCE_TARGETS = [
    ("李世民", ROOT / "exports" / "markdown_views" / "第五项B_李世民净证据池.md"),
    ("刘秀", ROOT / "exports" / "markdown_views" / "第五项B_刘秀净证据池.md"),
    ("刘庄", ROOT / "exports" / "markdown_views" / "第五项B_刘庄净证据池.md"),
]
I5B_SUBITEM = "第五项B"


def escape_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).replace("|", "\\|").replace("\n", " ")


def summarize_unique_values(rows: list[dict[str, object]], field: str) -> str:
    values = []
    for row in rows:
        value = row.get(field)
        if value is None:
            continue
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned and cleaned not in values:
                values.append(cleaned)
    return "；".join(values)


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


def render_global_scale_decision_brief() -> str:
    lines = [
        "# 全局总标尺决策简报",
        "",
        "状态：方案 C 已规则级确认 / 阶段性总标尺口径 / 不正式出分",
        "",
        "## 一、简报目的",
        "",
        "本简报用于把当前评分体系的“全局总标尺缺口”整理成可供确认的选项。",
        "",
        "它只讨论规则结构，不生成任何人物正式分数，不排名，不生成阶段总榜或总榜。",
        "",
        "其中方案 C 已被规则级确认，并作为当前阶段的全局总标尺口径。",
        "",
        "## 二、当前已存在的全局规则类型",
        "",
        "仓库里已经存在的全局规则，主要是“如何把史料变成净证据”的中间层，而不是全局总分：",
        "",
        "1. `docs/总规则.md` 给出先规则、后证据、再评分的总顺序。",
        "2. `docs/证据裁量总则_讨论版.md` 给出原子证据卡、五轴裁量、相邻项剥离、自动结算边界和人工裁判边界。",
        "3. `docs/证据强度四级与五轴量化规则_讨论版.md` 给出四级证据强度与五轴裁量口径。",
        "4. `docs/第五项B自动结算规则.md` 给出第五项B的带位方向、规则敏感点和高档位拦截。",
        "5. `docs/第五项B正式工作流模板.md` 给出自动结算草案、正式定档落地表与正式出分任务的流程边界。",
        "6. `docs/第五项B评分映射总标尺对齐审计.md` 给出当前未发现正式全局分值上限或第五项B专属封顶的审计结论。",
        "",
        "## 三、当前缺失的规则类型",
        "",
        "从 #53 的审计结论看，仓库当前还缺少这些“正式总标尺”层内容：",
        "",
        "1. 全局满分或总分基准。",
        "2. 各大项权重。",
        "3. 各子项分值上限。",
        "4. 跨项统一归一化规则。",
        "5. 档位到正式分值的统一映射。",
        "",
        "## 四、为什么第五项B不能直接正式出分",
        "",
        "第五项B目前只有相对区间草案，没有正式全局总标尺对齐结果。",
        "",
        "因此它只能继续停在“待总标尺确认”：",
        "",
        "1. 没有明确的全局总分上限，就无法知道相对区间最终应落在哪个绝对分值区间。",
        "2. 没有大项权重，就无法判断第五项B在总体系中的相对占比。",
        "3. 没有子项分值上限，就无法把第五项B的强弱档位正式压到统一刻度。",
        "4. 没有统一映射，就不能把第五项B相对区间自动转成正式分数。",
        "",
        "## 五、后续正式出分需要用户确认的事项",
        "",
        "若要进入正式出分任务，建议先由用户规则级确认以下内容：",
        "",
        "1. 是否采用单一全局总分。",
        "2. 是否给每个大项设置固定权重。",
        "3. 是否给每个子项设置分值上限。",
        "4. 是否允许先按各子项独立评分，再做统一归一化。",
        "5. 是否允许保留相对档位，但延后到全体系完成后统一映射。",
        "",
        "## 六、全局总标尺设计方案",
        "",
        "### 方案A：全体系 100 分总标尺，大项权重固定",
        "",
        "做法：",
        "",
        "- 先定义全局 100 分总标尺；",
        "- 各大项预先分配固定权重；",
        "- 各子项在大项权重内再落分。",
        "",
        "优点：",
        "",
        "- 结构清晰；",
        "- 便于横向比较；",
        "- 便于后续统一展示。",
        "",
        "风险：",
        "",
        "- 需要先把所有大项的权重都定死；",
        "- 早期子项容易被过早数值化；",
        "- 第五项B若缺少正式上限，容易被迫硬套。",
        "",
        "对既有工作的影响：",
        "",
        "- 第一、第二、第三、第五项都要提前对齐权重；",
        "- 第五项B的相对区间必须尽快换成正式值；",
        "- 会显著提高全体系一次性定标成本。",
        "",
        "### 方案B：各大项先独立 100 分，最终再统一归一化",
        "",
        "做法：",
        "",
        "- 每个大项先各自形成独立评分尺度；",
        "- 各项内部先完成定档；",
        "- 后续再统一归一化到全局尺度。",
        "",
        "优点：",
        "",
        "- 每个大项可以先独立成熟；",
        "- 对单项试点更友好；",
        "- 可以延后跨项权重争议。",
        "",
        "风险：",
        "",
        "- 后期归一化会引入额外换算复杂度；",
        "- 可能出现“大项之间可比性”争议；",
        "- 若归一化规则不清，会拖慢最终定分。",
        "",
        "对既有工作的影响：",
        "",
        "- 第一、第二、第三、第五项可先各自收口；",
        "- 第五项B可先保留相对区间；",
        "- 需要在后续明确跨项换算公式。",
        "",
        "### 方案C：阶段性总标尺口径（已采纳）",
        "",
        "做法：",
        "",
        "- 先只做相对档位与相对区间；",
        "- 不进入跨项数值总分；",
        "- 等主要项目都完成后，再统一定总标尺。",
        "",
        "优点：",
        "",
        "- 最符合当前仓库的现状；",
        "- 对第五项B现有工作最少扰动；",
        "- 能先把规则成熟度做出来，再讨论数值化。",
        "",
        "风险：",
        "",
        "- 短期内无法产出正式总分；",
        "- 阶段成果更偏规则成果而非数值成果；",
        "- 如果用户急需总分，会觉得进度慢。",
        "",
        "对既有工作的影响：",
        "",
        "- 第一、第二、第三、第五项都可以继续按规则层推进；",
        "- 第五项B相对区间继续保留“待总标尺确认”；",
        "- 最适合当前“先稳规则、后定总分”的阶段。",
        "",
        "## 七、推荐的下一步规则确认顺序",
        "",
        "建议按以下顺序确认：",
        "",
        "1. 先确认是否需要单一全局总分。",
        "2. 再确认是否存在各大项权重。",
        "3. 再确认第五项B等单项是否有上限。",
        "4. 再确认是否采用独立评分后统一归一化。",
        "5. 最后再决定第五项B相对区间如何转成正式分值。",
        "",
        "## 八、结论",
        "",
        "目前最稳妥的状态仍然是：",
        "",
        "1. 保留第五项 B 相对档位草案；",
        "2. 将方案 C 作为当前阶段的全局总标尺口径；",
        "3. 保留当前全局总标尺缺口的审计结论，直到后续正式出分再补齐；",
        "4. 不进入正式出分、不排名、不生成总榜。",
    ]
    return "\n".join(lines) + "\n"


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
    export_path = export_markdown()
    print(f"exported {export_path}")
    search_logs_export_path = export_search_logs_markdown()
    print(f"exported {search_logs_export_path}")
    evidence_clusters_export_path = export_evidence_clusters_markdown()
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
    GLOBAL_SCALE_BRIEF_DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    GLOBAL_SCALE_BRIEF_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    brief_content = render_global_scale_decision_brief()
    GLOBAL_SCALE_BRIEF_DOC_PATH.write_text(brief_content, encoding="utf-8")
    GLOBAL_SCALE_BRIEF_EXPORT_PATH.write_text(brief_content, encoding="utf-8")
    print(f"exported {GLOBAL_SCALE_BRIEF_DOC_PATH}")
    print(f"exported {GLOBAL_SCALE_BRIEF_EXPORT_PATH}")
    auto_adjudication_export_path, auto_rules_export_path, formal_landing_export_path, closure_export_path = export_auto_adjudication()
    print(f"exported {auto_adjudication_export_path}")
    print(f"exported {auto_rules_export_path}")
    print(f"exported {formal_landing_export_path}")
    print(f"exported {closure_export_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
