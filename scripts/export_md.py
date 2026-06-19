from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from collections import Counter

from export_i5b_auto_adjudication import export_auto_adjudication


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "evidence_cache.sqlite"
EXPORT_PATH = ROOT / "exports" / "markdown_views" / "史料证据卡索引.md"
SEARCH_LOGS_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "第五项B三人试点检索线索.md"
EVIDENCE_CLUSTERS_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "证据组裁量索引.md"
THEMATIC_ANCHORS_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "专题锚点索引.md"
QUERY_PROFILES_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "项目检索包索引.md"
EXPANDED_BATCH1_REVIEW_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "第五项B扩展试点第一批证据卡与证据簇草案.md"
EXPANDED_BATCH1_CLUSTER_ADJUDICATION_BATCH_PATH = ROOT / "data" / "adjudication_batches" / "i5b_expanded_pilot_batch1_cluster_adjudication_20260619.jsonl"
EXPANDED_BATCH1_CLUSTER_ADJUDICATION_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "第五项B扩展试点第一批证据簇结算草案.md"
TARGETED_SUPPLEMENT_SOURCE_BATCH_PATH = ROOT / "data" / "source_batches" / "i5b_expanded_pilot_batch1_targeted_supplement_20260619.jsonl"
TARGETED_SUPPLEMENT_EVIDENCE_BATCH_PATH = ROOT / "data" / "evidence_card_batches" / "i5b_expanded_pilot_batch1_targeted_supplement_20260619.jsonl"
TARGETED_SUPPLEMENT_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "第五项B扩展试点第一批定向补证.md"
GLOBAL_SCALE_BRIEF_DOC_PATH = ROOT / "docs" / "全局总标尺决策简报_讨论版.md"
GLOBAL_SCALE_BRIEF_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "全局总标尺决策简报_讨论版.md"
CANDIDATE_POOL_DOC_PATH = ROOT / "docs" / "第五项B扩展试点候选池设计.md"
CANDIDATE_POOL_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "第五项B扩展试点候选池设计.md"
EXPANDED_BATCH1_PERSONS = ["刘邦", "雍正", "朱元璋"]
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

I5B_EXPANDED_CANDIDATE_POOL_ROWS = [
    {
        "person": "刘邦",
        "candidate_type": "用人强但有明显反向事件",
        "why_selected": "兼具高强度用人、早期创业授权和显著反向事件，适合压测正负并存时的边界处理。",
        "expected_rule_pressure": "检验强正与负证共存时，是否会把用人能力误判为无压制高分。",
        "required_evidence_focus": "早期任用、分封/统军、纳谏、功臣与异姓王处置、反向事件原文。",
        "adjacent_item_risk": "军功、开国叙事和统一结果回填到第五项B。",
        "negative_scan_focus": "功臣清洗、异姓王处置、身后评价反转、寒蝉式负证。",
        "recommended_priority": "P1",
    },
    {
        "person": "雍正",
        "candidate_type": "行政强但授权偏弱",
        "why_selected": "适合检查高行政强度与低授权弹性并存时，是否被误抬成强正。",
        "expected_rule_pressure": "压测授权偏弱下的中正/强正封顶与强负压制。",
        "required_evidence_focus": "中枢批示、制度执行、用人与授权边界、近臣/督抚关系。",
        "adjacent_item_risk": "政务整顿、财政整饬和后续治绩回填。",
        "negative_scan_focus": "严控、猜忌、近臣高压、表达入口受损。",
        "recommended_priority": "P2",
    },
    {
        "person": "朱元璋",
        "candidate_type": "负证主导、正证不足",
        "why_selected": "用于检验强负主导样本的负证拦截和相邻项切分是否足够坚实。",
        "expected_rule_pressure": "压测强负核心、极负边界和负证主导样本是否会误入强正通道。",
        "required_evidence_focus": "功臣处置、容谏、制度控制、正证与负证厚度对比。",
        "adjacent_item_risk": "开国秩序、行政整肃和历史评价被回填到第五项B。",
        "negative_scan_focus": "大清洗、文臣寒蝉、严刑、猜忌、权力收束。",
        "recommended_priority": "P3",
    },
    {
        "person": "赵匡胤",
        "candidate_type": "强正但负证较少",
        "why_selected": "适合做相对干净的强正样本，检验强正封顶和轻负稀薄场景。",
        "expected_rule_pressure": "压测强正是否会因负证稀少而被误抬到极正。",
        "required_evidence_focus": "授权用人、文武平衡、功臣安全、容谏入口。",
        "adjacent_item_risk": "统一、开国、政权稳定和军功回填。",
        "negative_scan_focus": "杯酒释兵权、功臣边界、中央集权、后续控制。",
        "recommended_priority": "P4",
    },
    {
        "person": "嬴政",
        "candidate_type": "边界争议型",
        "why_selected": "统一、法制与高压并存，适合测相邻项剥离和边界争议处理。",
        "expected_rule_pressure": "压测 C/D/E 项切分、极强正与极强负并存时的分案规则。",
        "required_evidence_focus": "统一、法令、任用、徙民、表达安全、严刑。",
        "adjacent_item_risk": "统一战争、制度创设和法令执行被回填到第五项B。",
        "negative_scan_focus": "焚书、坑儒、徙民、严刑、集权与表达安全受损。",
        "recommended_priority": "P5",
    },
    {
        "person": "刘彻",
        "candidate_type": "证据印象强但证据簇不足",
        "why_selected": "名声与印象很强，但需要检查是否真有足够成簇证据支撑。",
        "expected_rule_pressure": "压测证据簇厚度、代表性覆盖和印象替代证据的风险。",
        "required_evidence_focus": "用人、授权、纳谏、后期反向事件、可成簇证据。",
        "adjacent_item_risk": "盛世叙事、对外扩张和制度成效回填。",
        "negative_scan_focus": "巫蛊、严刑、征战损耗、后期反转。",
        "recommended_priority": "P6",
    },
    {
        "person": "武则天",
        "candidate_type": "非军事/非开国光环型",
        "why_selected": "适合去光环，检验非军事/非开国叙事下的证据厚度。",
        "expected_rule_pressure": "压测去光环、性别偏置和非军事统治样本的用人/授权证据。",
        "required_evidence_focus": "任用、纳谏、官僚整合、制度运行、光环剥离。",
        "adjacent_item_risk": "后世褒贬、宗教与宫廷叙事回填。",
        "negative_scan_focus": "酷吏、告密、宗室/储位、称帝叙事、寒蝉。",
        "recommended_priority": "P7",
    },
]


def read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


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

    lines = [
        "# 第五项B扩展试点第一批证据卡与证据簇草案",
        "",
        "本文件汇总刘邦、雍正、朱元璋的回源证据卡与证据簇草案，仅供审阅，不生成正式分，不排名，不出总榜。",
        "",
        "## 证据卡",
        "",
        "| " + " | ".join(EXPANDED_BATCH1_EVIDENCE_HEADERS) + " |",
        "| " + " | ".join("---" for _ in EXPANDED_BATCH1_EVIDENCE_HEADERS) + " |",
    ]

    for row in evidence_rows:
        raw_json = json.loads(row["raw_json"])
        lines.append(
            "| " + " | ".join(escape_cell(raw_json.get(header)) for header in EXPANDED_BATCH1_EVIDENCE_HEADERS) + " |"
        )

    lines.extend(
        [
            "",
            "## 证据簇",
            "",
            "| " + " | ".join(EXPANDED_BATCH1_CLUSTER_HEADERS) + " |",
            "| " + " | ".join("---" for _ in EXPANDED_BATCH1_CLUSTER_HEADERS) + " |",
        ]
    )

    for row in cluster_rows:
        raw_json = json.loads(row["raw_json"])
        lines.append(
            "| " + " | ".join(escape_cell(raw_json.get(header)) for header in EXPANDED_BATCH1_CLUSTER_HEADERS) + " |"
        )

    EXPANDED_BATCH1_REVIEW_EXPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return EXPANDED_BATCH1_REVIEW_EXPORT_PATH

def export_expanded_i5b_batch1_cluster_adjudication() -> Path:
    EXPANDED_BATCH1_CLUSTER_ADJUDICATION_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    rows = read_jsonl(EXPANDED_BATCH1_CLUSTER_ADJUDICATION_BATCH_PATH)

    lines = [
        "# 第五项B扩展试点第一批证据簇结算草案",
        "",
        "本文件仅供人工审阅，汇总刘邦、雍正、朱元璋的证据簇结算草案；只作草案，不输出终局结果。",
        "",
        "## 结算总览",
        "",
        "| " + " | ".join(EXPANDED_BATCH1_CLUSTER_ADJUDICATION_HEADERS) + " |",
        "| " + " | ".join("---" for _ in EXPANDED_BATCH1_CLUSTER_ADJUDICATION_HEADERS) + " |",
    ]

    for row in rows:
        lines.append("| " + " | ".join(escape_cell(row.get(header)) for header in EXPANDED_BATCH1_CLUSTER_ADJUDICATION_HEADERS) + " |")

    lines.extend(["", "## 逐人结算", ""])
    for row in rows:
        lines.extend(
            [
                f"### {row.get('person')}",
                "",
                f"- 正向证据簇：{escape_cell(row.get('positive_cluster_ids'))}",
                f"- 负向证据簇：{escape_cell(row.get('negative_cluster_ids'))}",
                f"- 正向核心：{row.get('positive_core_summary') or ''}",
                f"- 负向核心：{row.get('negative_core_summary') or ''}",
                f"- 相邻项切分：{row.get('adjacent_item_split_summary') or ''}",
                f"- 负证拦截：{row.get('negative_intercept_status') or ''} / {row.get('adjacent_item_split_status') or ''}",
                f"- 规则敏感点：{row.get('rule_pressure_summary') or ''}",
                f"- 净裁量草案：{row.get('net_adjudication_draft') or ''}",
                f"- 补证缺口：{escape_cell(row.get('supplement_gap_list'))}",
                "",
            ]
        )

    lines.extend(["## 规则敏感点清单", ""])
    for row in rows:
        lines.append(f"- {row.get('person')}：{row.get('rule_pressure_summary') or ''}")

    lines.extend(["", "## 后续 targeted supplement 缺口清单", ""])
    for row in rows:
        lines.append(f"- {row.get('person')}：{escape_cell(row.get('supplement_gap_list'))}")

    lines.extend(
        [
            "",
            "本文件不输出终局结果。",
        ]
    )

    EXPANDED_BATCH1_CLUSTER_ADJUDICATION_EXPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return EXPANDED_BATCH1_CLUSTER_ADJUDICATION_EXPORT_PATH


def export_expanded_i5b_batch1_targeted_supplement() -> Path:
    TARGETED_SUPPLEMENT_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    source_rows = read_jsonl(TARGETED_SUPPLEMENT_SOURCE_BATCH_PATH)
    evidence_rows = read_jsonl(TARGETED_SUPPLEMENT_EVIDENCE_BATCH_PATH)
    source_rows = sorted(source_rows, key=lambda row: str(row.get("source_id") or ""))
    evidence_rows = sorted(
        evidence_rows,
        key=lambda row: (str(row.get("person") or ""), str(row.get("polarity") or ""), str(row.get("evidence_id") or "")),
    )

    counts = Counter(str(row.get("person") or "") for row in evidence_rows)

    lines = [
        "# 第五项B扩展试点第一批定向补证",
        "",
        "本文件只汇总刘邦、雍正、朱元璋的 targeted supplement 补证材料；只做补证，不定档，不出分，不排名，不出总榜。",
        "",
        "## 人数与补证数量",
        "",
    ]
    for person in ["刘邦", "雍正", "朱元璋"]:
        lines.append(f"- {person}：{counts.get(person, 0)} 条")

    lines.extend(
        [
            "",
            "## 来源",
            "",
            "| " + " | ".join(TARGETED_SUPPLEMENT_SOURCE_HEADERS) + " |",
            "| " + " | ".join("---" for _ in TARGETED_SUPPLEMENT_SOURCE_HEADERS) + " |",
        ]
    )
    for row in source_rows:
        lines.append("| " + " | ".join(escape_cell(row.get(header)) for header in TARGETED_SUPPLEMENT_SOURCE_HEADERS) + " |")

    lines.extend(
        [
            "",
            "## 证据卡",
            "",
            "| " + " | ".join(TARGETED_SUPPLEMENT_EVIDENCE_HEADERS) + " |",
            "| " + " | ".join("---" for _ in TARGETED_SUPPLEMENT_EVIDENCE_HEADERS) + " |",
        ]
    )
    for row in evidence_rows:
        lines.append("| " + " | ".join(escape_cell(row.get(header)) for header in TARGETED_SUPPLEMENT_EVIDENCE_HEADERS) + " |")

    lines.extend(
        [
            "",
            "## 结语",
            "",
            "本批仅补 source-backed targeted supplement evidence cards；不定档、不出分、不排名、不出总榜。",
        ]
    )

    TARGETED_SUPPLEMENT_EXPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return TARGETED_SUPPLEMENT_EXPORT_PATH


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


def render_expanded_i5b_candidate_pool() -> str:
    coverage_rows = [
        {
            "required_type": "强正但负证较少",
            "representative_person": "赵匡胤",
            "coverage_note": "用于检验强正封顶在轻负稀薄场景下是否仍能稳住，不把低噪负证误抬为高压制。",
        },
        {
            "required_type": "用人强但有明显反向事件",
            "representative_person": "刘邦",
            "coverage_note": "用于压测用人能力与反向事件并存时的边界，避免把强用人误读为无负证样本。",
        },
        {
            "required_type": "行政强但授权偏弱",
            "representative_person": "雍正",
            "coverage_note": "用于检验高行政强度与低授权弹性并存时，是否会被误抬为强正上探。",
        },
        {
            "required_type": "证据印象强但证据簇不足",
            "representative_person": "刘彻",
            "coverage_note": "用于检验印象强度是否会替代成簇证据厚度，防止名声压过证据结构。",
        },
        {
            "required_type": "负证主导、正证不足",
            "representative_person": "朱元璋",
            "coverage_note": "用于压测强负主导样本的拦截、切分与极负边界，避免负证样本误入强正通道。",
        },
        {
            "required_type": "非军事/非开国光环型",
            "representative_person": "武则天",
            "coverage_note": "用于去光环，确认非军事、非开国叙事下仍能回到用人、授权和纳谏证据。",
        },
        {
            "required_type": "边界争议型",
            "representative_person": "嬴政",
            "coverage_note": "用于测相邻项剥离和边界争议，特别是统一、法令、严刑与表达安全的切分。",
        },
    ]

    lines = [
        "# 第五项B扩展试点候选池设计",
        "",
        "状态：候选池设计 / 试点样本规划 / 不出分",
        "",
        "本文件只设计第五项B扩展试点候选池，不作定档结论，不生成正式分，不排名，不生成阶段总榜或总榜。",
        "",
        "候选池按类型抽样，不按名气或预期高低抽样；`recommended_priority` 只是建议采样顺序，不是人物高低排序。",
        "",
        "## 一、覆盖检查",
        "",
        "| required_type | representative_person | coverage_note |",
        "| --- | --- | --- |",
    ]

    for row in coverage_rows:
        lines.append(
            "| "
            + " | ".join(
                escape_cell(row[field])
                for field in ["required_type", "representative_person", "coverage_note"]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## 二、候选池明细",
            "",
            "| person | candidate_type | why_selected | expected_rule_pressure | required_evidence_focus | adjacent_item_risk | negative_scan_focus | recommended_priority |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )

    for row in I5B_EXPANDED_CANDIDATE_POOL_ROWS:
        lines.append(
            "| "
            + " | ".join(
                escape_cell(row[field])
                for field in [
                    "person",
                    "candidate_type",
                    "why_selected",
                    "expected_rule_pressure",
                    "required_evidence_focus",
                    "adjacent_item_risk",
                    "negative_scan_focus",
                    "recommended_priority",
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## 三、设计说明",
            "",
            "1. 本候选池只用于扩展试点样本设计，不代表任何最终定档或分数结论。",
            "2. 候选选择重点在规则压力覆盖，而不是历史名气、综合高低或名望大小。",
            "3. 后续真正进入扩展试点时，应优先补齐原子证据卡、证据簇、相邻项切分与负证拦截，再谈任何定档。",
            "4. 本文件不要求机械全收候选参考名单；未纳入者可作为后续扩容备选。",
            "",
        ]
    )

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
    expanded_batch1_review_export_path = export_expanded_i5b_batch1_review()
    print(f"exported {expanded_batch1_review_export_path}")
    expanded_batch1_cluster_adjudication_export_path = export_expanded_i5b_batch1_cluster_adjudication()
    print(f"exported {expanded_batch1_cluster_adjudication_export_path}")
    targeted_supplement_export_path = export_expanded_i5b_batch1_targeted_supplement()
    print(f"exported {targeted_supplement_export_path}")
    GLOBAL_SCALE_BRIEF_DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    GLOBAL_SCALE_BRIEF_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    brief_content = render_global_scale_decision_brief()
    GLOBAL_SCALE_BRIEF_DOC_PATH.write_text(brief_content, encoding="utf-8")
    GLOBAL_SCALE_BRIEF_EXPORT_PATH.write_text(brief_content, encoding="utf-8")
    print(f"exported {GLOBAL_SCALE_BRIEF_DOC_PATH}")
    print(f"exported {GLOBAL_SCALE_BRIEF_EXPORT_PATH}")
    CANDIDATE_POOL_DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATE_POOL_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    candidate_pool_content = render_expanded_i5b_candidate_pool()
    CANDIDATE_POOL_DOC_PATH.write_text(candidate_pool_content, encoding="utf-8")
    CANDIDATE_POOL_EXPORT_PATH.write_text(candidate_pool_content, encoding="utf-8")
    print(f"exported {CANDIDATE_POOL_DOC_PATH}")
    print(f"exported {CANDIDATE_POOL_EXPORT_PATH}")
    auto_adjudication_export_path, auto_rules_export_path, formal_landing_export_path, closure_export_path = export_auto_adjudication()
    print(f"exported {auto_adjudication_export_path}")
    print(f"exported {auto_rules_export_path}")
    print(f"exported {formal_landing_export_path}")
    print(f"exported {closure_export_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
