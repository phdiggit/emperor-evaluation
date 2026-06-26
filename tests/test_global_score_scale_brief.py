import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BRIEF_DOC_PATH = ROOT / "docs" / "全局总标尺决策简报_讨论版.md"
BRIEF_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "综合汇总" / "全局总标尺决策简报_讨论版.md"


@pytest.mark.export_full
@pytest.mark.integration
def test_export_md_generates_global_scale_decision_brief_export_only() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "export" / "export_md.py"), "--profile", "project-docs"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert not BRIEF_DOC_PATH.exists()
    assert BRIEF_EXPORT_PATH.exists()

    content = BRIEF_EXPORT_PATH.read_text(encoding="utf-8")
    for needle in [
        "全局总标尺执行简报",
        "V3.2",
        "1500",
        "历史负债",
        "第五项B",
        "45",
        "G9 已批准第五项B正式分值与子项排名发布",
        "方案 C",
        "G8 正式算法已释放",
        "本阶段发布第五项B正式分值和子项排名",
    ]:
        assert needle in content
    for forbidden in [
        "未发现正式全局分值上限",
        "全局满分或总分基准缺失",
        "是否采用单一全局总分",
        "1440",
        "本阶段按1440分执行",
        "人物级正式值和排名仍等 G9",
    ]:
        assert forbidden not in content
