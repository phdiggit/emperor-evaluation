import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIEF_DOC_PATH = ROOT / "docs" / "全局总标尺决策简报_讨论版.md"
BRIEF_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "全局总标尺决策简报_讨论版.md"


def test_export_md_generates_global_scale_decision_brief() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "export_md.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert BRIEF_DOC_PATH.exists()
    assert BRIEF_EXPORT_PATH.exists()

    doc_content = BRIEF_DOC_PATH.read_text(encoding="utf-8")
    export_content = BRIEF_EXPORT_PATH.read_text(encoding="utf-8")

    for content in (doc_content, export_content):
        assert "全局总标尺决策简报" in content
        assert "方案 C 已规则级确认" in content
        assert "不正式出分" in content
        assert "方案A：全体系 100 分总标尺，大项权重固定" in content
        assert "方案B：各大项先独立 100 分，最终再统一归一化" in content
        assert "方案C：阶段性总标尺口径（已采纳）" in content
        assert "推荐的下一步规则确认顺序" in content

