from __future__ import annotations

import json
from pathlib import Path

from emperor_v4.evaluation.profile_markdown import AXIS_FILES, PROFILE_ROOT, render_profile_markdown


def test_completed_c_axes_use_deterministic_reading_views() -> None:
    for axis, filename in AXIS_FILES.items():
        json_path = PROFILE_ROOT / filename
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        markdown = json_path.with_suffix(".md").read_text(encoding="utf-8")
        assert markdown == render_profile_markdown(payload)
        assert markdown.count("\n### ") >= 184
        assert "## 阅读说明" in markdown
        assert "## 全池结算表" in markdown
        assert "## 逐人裁决依据" in markdown
        assert markdown.count("**主模式**") == 184
        assert markdown.count("**裁档理由**") == 184
        assert markdown.count("**限制**") == 184


def test_shared_limitations_are_defined_once_and_referenced() -> None:
    payload = json.loads((PROFILE_ROOT / AXIS_FILES["C3"]).read_text(encoding="utf-8"))
    markdown = render_profile_markdown(payload)
    repeated = "主要任务类型或主要掌权阶段仍有未暴露窗口；新增连续君主中心正文可能改变档位。"
    assert markdown.count(repeated) == 1
    assert "### 共用限制说明" in markdown
    assert "`L1`" in markdown
