from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from shared import config_loaders
from shared.export_md_scaffold import escape_cell
from shared.i5b_markdown_display import display_field_label, display_value, load_display_dictionary


ROOT = Path(__file__).resolve().parents[2]
GLOBAL_SCALE_BRIEF_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "综合汇总" / "全局总标尺决策简报_讨论版.md"
CANDIDATE_POOL_EXPORT_PATH = (
    ROOT
    / "exports"
    / "markdown_views"
    / "第五项B"
    / "人工审核"
    / "自动裁判链"
    / "试点闭环"
    / "第五项B扩展试点候选池设计.md"
)
def load_expanded_i5b_candidate_pool_rows() -> list[dict[str, str]]:
    return config_loaders.get_i5b_expanded_candidate_pool_rows()


def _display_table(headers: list[str], rows: list[dict[str, str]]) -> list[str]:
    display_config = dict(load_display_dictionary())
    display_config["keep_machine_field_name"] = False
    lines = [
        "| " + " | ".join(display_field_label(field, display_config) for field in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(escape_cell(display_value(row.get(field, ""), display_config)) for field in headers) + " |")
    return lines


def export_global_scale_decision_brief() -> Path:
    GLOBAL_SCALE_BRIEF_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    brief_content = render_global_scale_decision_brief()
    GLOBAL_SCALE_BRIEF_EXPORT_PATH.write_text(brief_content, encoding="utf-8")
    return GLOBAL_SCALE_BRIEF_EXPORT_PATH


def export_expanded_i5b_candidate_pool() -> Path:
    CANDIDATE_POOL_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    candidate_pool_content = render_expanded_i5b_candidate_pool()
    CANDIDATE_POOL_EXPORT_PATH.write_text(candidate_pool_content, encoding="utf-8")
    return CANDIDATE_POOL_EXPORT_PATH


def render_global_scale_decision_brief() -> str:
    lines = [
        "# 全局总标尺执行简报",
        "",
        "状态：V3.2 上位标尺已确认 / 当前阶段不发布人物正式分",
        "",
        "## 一、上位标准",
        "",
        "1. 最终得分采用 `正收益总分 - 历史负债`。",
        "2. 正收益总盘上限为 1440 分。",
        "3. 历史负债为第七项，按 0—300 扣分处理。",
        "4. 七大项及权重已经由 V3.2 driver 定义。",
        "5. 第五项B《用人与授权》的正式上限为 45 分。",
        "",
        "## 二、当前仍未完成的不是“总标尺”",
        "",
        "V3.2 已定义正式目标标尺；当前仍未完成的是人物级发布前的执行门槛：",
        "",
        "1. 各子项证据、锚点、负证拦截和相邻项剥离完整性。",
        "2. V3.2 正式档位到子项绝对分的映射规则。",
        "3. 压制、封顶、负证拦截的分值规则。",
        "4. 人工确认与正式发布门槛。",
        "",
        "## 三、方案 C 的当前含义",
        "",
        "方案 C 只作为实施和发布门槛，而不再表示总分结构未知。",
        "",
        "在证据、锚点、子项档位映射和人工确认未完成前，现有试点只保留相对档位和内部诊断指数；不发布人物正式分数、排名、阶段总榜或总榜。",
        "",
        "## 四、第五项B",
        "",
        "1. 第五项B正式上限 45 分已经明确。",
        "2. 当前 `relative_score_range_draft` 和 trial value 是内部100制相对试算指数。",
        "3. 该指数不能解释为 V3.2 正式得分率，不能按 `45 × index / 100` 机械换算，也不构成人物正式分。",
        "4. 正式 45 分映射必须另开专门 PR，明确 band、比例、压制、封顶和人审边界。",
        "",
        "## 五、结论",
        "",
        "1. V3.2 的 1440 正收益总盘、0—300 历史负债和第五项B 45 分上限已经确认。",
        "2. 本阶段继续执行禁正式出分、禁排名、禁阶段总榜和禁总榜。",
        "3. 方案 C 是发布门槛和实施顺序，不是总标尺缺失结论。",
        "4. 第五项B现有内部100制相对试算指数保持不变，不在本 PR 转换为45分正式映射。",
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
    ]

    lines.extend(_display_table(["required_type", "representative_person", "coverage_note"], coverage_rows))

    lines.extend(
        [
            "",
            "## 二、候选池明细",
            "",
        ]
    )

    lines.extend(
        _display_table(
            [
                "person",
                "candidate_type",
                "why_selected",
                "expected_rule_pressure",
                "required_evidence_focus",
                "adjacent_item_risk",
                "negative_scan_focus",
                "recommended_priority",
            ],
            load_expanded_i5b_candidate_pool_rows(),
        )
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
