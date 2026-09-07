from __future__ import annotations


import copy

from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.profile_markdown import (
    AXIS_FILES,
    C2_DISPLAY_REF_LIMIT,
    PROFILE_ROOT,
    render_profile_markdown,
)
from emperor_v4.evaluation.profile_parent_schema import parent_chains


def test_completed_c_axes_use_deterministic_reading_views() -> None:
    for axis, filename in AXIS_FILES.items():
        json_path = PROFILE_ROOT / filename
        payload = load_json(json_path)
        markdown = json_path.with_suffix(".md").read_text(encoding="utf-8")
        assert markdown == render_profile_markdown(payload)
        assert markdown.count("\n### ") >= len(payload["records"])
        assert "## 阅读说明" in markdown
        assert "## 全池结算表" in markdown
        assert "## 逐人裁决依据" in markdown
        if axis == "M3":
            for label in ("接手局面", "建设与维持", "成本与后果", "关键行为链", "交班局面", "落档理由"):
                assert markdown.count(f"**{label}**") == len(payload["records"])
        elif axis == "C2":
            assert markdown.count("**核心依据**") == len(payload["records"])
            assert markdown.count("**档内定位**") == len(payload["records"])
            assert "**主模式**" not in markdown
            assert "**裁档理由**" not in markdown
        elif axis == "C5":
            assert "| 展示序 | 池序 | 人物 | 档位 | 雷达值 | 证据 | 置信度 | 输出模式 | 人物类型 |" in markdown
            assert "| 展示序 | 池序 | 人物 | 档位 | 潜在高档假设 |" not in markdown
            assert markdown.count("**政治斗争复核**") == len(payload["records"])
        else:
            assert markdown.count("**主模式**") == len(payload["records"])
            assert markdown.count("**裁档理由**") == len(payload["records"])
        assert markdown.count("**限制**") == len(payload["records"])


def test_shared_limitations_are_defined_once_and_referenced() -> None:
    payload = load_json(PROFILE_ROOT / AXIS_FILES["C3"])
    markdown = render_profile_markdown(payload)
    repeated = "主要任务类型或主要掌权阶段仍有未暴露窗口；新增连续君主中心正文可能改变档位。"
    assert markdown.count(repeated) == 1
    assert "### 共用限制说明" in markdown
    assert "`L1`" in markdown


def test_c2_reader_view_uses_representatives_and_compacts_source_display() -> None:
    payload = load_json(PROFILE_ROOT / AXIS_FILES["C2"])
    markdown = render_profile_markdown(payload)

    assert "完整来源集合与关联父链保留在正式JSON" in markdown
    assert "  - 来源：" not in markdown
    for line in markdown.splitlines():
        if "直接定位" not in line:
            continue
        shown = line.split("：", 1)[1].split("；其余", 1)[0]
        assert len(shown.split("；")) <= C2_DISPLAY_REF_LIMIT

    source_row = next(row for row in payload["records"] if len(parent_chains(row)) >= 2)
    narrowed = copy.deepcopy(payload)
    narrowed["records"] = [copy.deepcopy(source_row)]
    first_id = source_row["parent_chains"][0]["parent_id"]
    second_id = source_row["parent_chains"][1]["parent_id"]
    narrowed["records"][0]["representative_parent_ids"] = [first_id]
    narrowed_markdown = render_profile_markdown(narrowed)
    assert f"`{first_id}`" in narrowed_markdown
    assert f"`{second_id}`" not in narrowed_markdown
