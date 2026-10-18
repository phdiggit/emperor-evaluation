from pathlib import Path

import pytest

from emperor_v4.evaluation.first_item_markdown_settlement import (
    COMPONENT_SETTLEMENTS, TOTAL_SETTLEMENT, _validate_b2_text_consistency,
)


def fixture(root: Path):
    target = root / COMPONENT_SETTLEMENTS[2]
    target.parent.mkdir(parents=True)
    (target.parent / "source.md").write_text("合成材料", encoding="utf-8")
    reasons = "\n".join([
        "- **评价窗口**：合成建基阶段。",
        "- **本人控制链**：本人授予基础任务与专业权限。",
        "- **公开阅读问题**：合成任务怎样分工？",
        "- **公开阅读正文**：一位助手与一个专业中心分担任务。",
        "- **并行执行**：L1。一个助手处理分派的基础任务。",
        "- **团队能力覆盖与组织杠杆**：L2。一个专业中心完成独立任务。",
        "- **异质整合**：L1。外围集团只形成短期依附。",
        "- **材料来源**：[合成来源](source.md)。",
    ])
    target.write_text("| 1 | 合成人物 | L1 | 2 | L2 | 4 | L1 | 2 | **8** |\n\n### 1. 合成人物\n\n- **B2结算**：**8/30**\n" + reasons + "\n", encoding="utf-8")
    (root / TOTAL_SETTLEMENT).write_text("### 1. 合成人物\n\n**B2｜组织：8/30**\n" + reasons + "\n", encoding="utf-8")
    return {"合成人物": {"b2": 8}}


def test_b2_current_material_views_are_equal(tmp_path):
    totals = fixture(tmp_path)
    assert _validate_b2_text_consistency(tmp_path, totals) == len(totals)


@pytest.mark.parametrize("kind", ["reason", "score", "source", "window", "story", "control"])
def test_b2_rejects_material_or_value_drift(tmp_path, kind):
    totals = fixture(tmp_path)
    path = tmp_path / TOTAL_SETTLEMENT
    if kind == "reason":
        path.write_text(path.read_text(encoding="utf-8").replace("一个助手", "两个助手"), encoding="utf-8")
    elif kind == "score":
        totals["合成人物"]["b2"] = 10
    elif kind == "source":
        (path.parent / "source.md").unlink()
    else:
        before, after = {"window": ("合成建基阶段", "另外阶段"),
                         "story": ("分担任务", "未分担任务"),
                         "control": ("授予基础任务", "没有授予任务")}[kind]
        path.write_text(path.read_text(encoding="utf-8").replace(before, after), encoding="utf-8")
    with pytest.raises(ValueError):
        _validate_b2_text_consistency(tmp_path, totals)
