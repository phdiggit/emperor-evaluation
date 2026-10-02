"""Shared Chinese labels for declared military responsibility codes."""
import re

RESULT_SCOPE_LABELS = {
    "unresolved_command_scope": "本人指挥范围尚未闭合",
    "actual_command_scope": "本人实际指挥范围",
    "operational_design_scope": "本人战区设计与统筹范围",
    "independent_direction_scope": "本人独立方向决策范围",
    "scoped_stage_scope": "本人可归责阶段范围",
}
FAULT_LABELS = {
    "COMMANDER_RESPONSIBILITY_AFTER_UNRESOLVED_SEARCH": "实际指挥责任成立，具体致败过错未定",
    "UNKNOWN": "具体致败责任未定",
    "PARTLY_UNKNOWN": "部分致败责任未定",
    "ATTRIBUTABLE_COMMAND_ERROR": "已证实本人指挥失误",
    "ATTRIBUTABLE_ROUTE_SELECTION": "可归责的路线选择失误",
    "SUPPORTED_DECISION_RESPONSIBILITY": "已有证据支持本人决策责任",
    "SUPPORTED_STAGE_CAUSATION": "已有证据支持本人阶段行动与败果的因果关系",
    "SUPPORTED_ACTUAL_COMMAND_RESPONSIBILITY": "已有证据支持本人实际指挥责任",
    "SUPPORTED_SHARED_COMMAND_RESPONSIBILITY": "已有证据支持共同指挥责任",
    "SUPPORTED_EXECUTION_RESPONSIBILITY": "已有证据支持本人执行责任",
    "SUPPORTED_COMMAND_ERROR_WITH_FORCED_OFFENSIVE_CONSTRAINT": "本人指挥失误有证据，同时存在强令进攻约束",
    "DIRECT_COMMAND_ABANDONMENT": "本人弃军离开指挥岗位",
    "DIRECT_COMMAND_NEGLECT": "本人指挥疏忽",
    "DIRECT_DEFECTION": "本人倒戈",
    "EXPLICIT_PREMATURE_WITHDRAWAL": "明确记载过早撤军",
    "EXPLICIT_FAILURE_TO_ADVANCE": "明确记载未进兵",
    "EXPLICIT_FIRST_FLIGHT": "明确记载本人先逃",
    "EXPLICIT_PREEMPTIVE_FLIGHT": "明确记载本人提前逃离",
    "EXPLICIT_WITHDRAWAL_UNDER_DIVERSION": "明确记载受牵制而撤军",
    "NO_ATTRIBUTABLE_FAILURE_ESTABLISHED": "尚未闭合可归责败绩",
    "NO_FAULT": "未发现本人致败过错",
    "NO_FAULT_MANDATORY_ORDER": "受强制军令约束，未归本人过错",
    "NO_FAULT_FORCED_ORDER_AND_WITHDRAWN_SUPPORT": "被强令作战且支援撤走，未归本人过错",
    "NO_FAULT_EXTERNAL_DISASTER": "外部灾害所致，未归本人过错",
    "FORCED_OFFENSIVE_AND_WEATHER_WITHOUT_INDIVIDUAL_FAULT_CLOSURE": "存在强令进攻及天气约束，本人过错尚未闭合",
    "PERSONAL_CAPABILITY_ATTRIBUTION_NOT_ESTABLISHED": "本人军事能力责任尚未闭合",
    "NOT_APPLICABLE": "不适用",
    "NOT_APPLICABLE_SOURCE_CONFLICT": "史源冲突，暂不裁定",
}


def registered_military_display(value: str) -> str:
    """Translate reading text only; unknown declared codes fail closed."""
    def translate(match: re.Match[str], labels: dict[str, str], title: str) -> str:
        code = match.group(1)
        if code not in labels:
            raise ValueError(f"军事阅读字段存在未翻译枚举：{code}")
        return f"{title}：{labels[code]}"

    value = re.sub(r"结果责任=([A-Za-z_]+)",
                   lambda match: translate(match, RESULT_SCOPE_LABELS, "本人结果责任"), value)
    value = re.sub(r"致败责任=([A-Za-z_]+)",
                   lambda match: translate(match, FAULT_LABELS, "致败归责"), value)
    for source, public in (
        ("positive人物成果", "正向个人成果"),
        ("negative人物成果", "负向个人结果"),
        ("mixed_review人物成果", "正反并存的个人成果"),
        ("当前只读终局卡表面动作而漏掉父群明确absorbed的三阶段", "原终局摘要漏记已并入父战役的三个阶段"),
        ("no_frontline_difficulty", "不继承前线难度"),
        ("war_conduct_negative", "战争行为负面"),
        ("attributable_failure", "可归责败绩"),
        ("command_adverse", "指挥负面"),
    ):
        value = value.replace(source, public)
    return value
