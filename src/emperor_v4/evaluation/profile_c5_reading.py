"""Shared C5 positioning guidance for the reading views."""

from .profile_m1_public import public_grade

POSITION_GUIDE = "权力运用的档内位置看已核案件覆盖、同类做法是否复发、程序能否约束权力，以及明确反馈后处分怎样收束或扩大。"
_POSITION_TEMPLATE = "按逐案覆盖、复发强度、程序与反馈后收束综合定位为{letter}档{position}位。"
COMMON_CONFLICT_FINDING = "未在C5、第五项C、M4及主要政治安全入口命中需重开的强触发；未来新增上游事实仍可重开。"
CONFLICT_REVIEW_GUIDE = (
    "政治斗争复核交叉查看本轴、归档的权力行为材料、内部联盟与主要政治安全记录。"
    "新增事实可能改变案件归责或处分边界时，可重开复核。"
)
EXPANSION_LABELS = {
    "R0_NO_EXPANSION": "未见处分扩大",
    "R1_LIMITED": "扩大至少数邻接对象",
    "R2_BOUNDED": "限于同案家庭或小群体",
    "R3_BROAD": "扩大至有明确边界的较广群体",
    "R4_SYSTEMIC_EXTREME": "波及无关群体或形成系统性清洗",
}


def uses_shared_position_guide(row: dict) -> bool:
    """Recognize the complete stock text only when its grade and position agree."""
    basis = row.get("position_basis")
    positions = {"LOW": "低", "MID": "中", "HIGH": "高"}
    if not basis or row.get("position") not in positions or row.get("axis_grade") not in {
        "G0", "G1", "G2", "G3", "G4", "G5",
    }:
        return False
    return basis == _POSITION_TEMPLATE.format(letter=public_grade(row)[0], position=positions[row["position"]])
