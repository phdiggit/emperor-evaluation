from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import config_loaders
from shared.export_md_scaffold import escape_cell
from i5b_markdown_display import display_field_label, display_value, load_display_dictionary


ROOT = Path(__file__).resolve().parents[2]
GLOBAL_SCALE_BRIEF_DOC_PATH = ROOT / "docs" / "全局总标尺决策简报_讨论版.md"
GLOBAL_SCALE_BRIEF_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "综合汇总" / "全局总标尺决策简报_讨论版.md"
CANDIDATE_POOL_DOC_PATH = ROOT / "docs" / "第五项B扩展试点候选池设计.md"
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


def export_global_scale_decision_brief_docs() -> tuple[Path, Path]:
    GLOBAL_SCALE_BRIEF_DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    GLOBAL_SCALE_BRIEF_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    brief_content = render_global_scale_decision_brief()
    GLOBAL_SCALE_BRIEF_DOC_PATH.write_text(brief_content, encoding="utf-8")
    GLOBAL_SCALE_BRIEF_EXPORT_PATH.write_text(brief_content, encoding="utf-8")
    return GLOBAL_SCALE_BRIEF_DOC_PATH, GLOBAL_SCALE_BRIEF_EXPORT_PATH


def export_expanded_i5b_candidate_pool_docs() -> tuple[Path, Path]:
    CANDIDATE_POOL_DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATE_POOL_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    candidate_pool_content = render_expanded_i5b_candidate_pool()
    CANDIDATE_POOL_DOC_PATH.write_text(candidate_pool_content, encoding="utf-8")
    CANDIDATE_POOL_EXPORT_PATH.write_text(candidate_pool_content, encoding="utf-8")
    return CANDIDATE_POOL_DOC_PATH, CANDIDATE_POOL_EXPORT_PATH


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
