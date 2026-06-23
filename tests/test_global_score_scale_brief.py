import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIEF_DOC_PATH = ROOT / "docs" / "全局总标尺决策简报_讨论版.md"
BRIEF_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "综合汇总" / "全局总标尺决策简报_讨论版.md"


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
        "1440",
        "历史负债",
        "第五项B",
        "45",
        "当前阶段不发布人物正式分",
        "方案 C",
        "内部100制相对试算指数",
    ]:
        assert needle in content
    for forbidden in [
        "未发现正式全局分值上限",
        "全局满分或总分基准缺失",
        "是否采用单一全局总分",
    ]:
        assert forbidden not in content
