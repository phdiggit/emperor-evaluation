import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
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


def run_script(script_name: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script_name)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_export_md_generates_expanded_candidate_pool_design() -> None:
    build_result = run_script("build_db.py")
    assert build_result.returncode == 0, build_result.stdout + build_result.stderr

    export_result = run_script("export_md.py")
    assert export_result.returncode == 0, export_result.stdout + export_result.stderr
    assert CANDIDATE_POOL_DOC_PATH.exists()
    assert CANDIDATE_POOL_EXPORT_PATH.exists()

    doc_content = CANDIDATE_POOL_DOC_PATH.read_text(encoding="utf-8")
    export_content = CANDIDATE_POOL_EXPORT_PATH.read_text(encoding="utf-8")

    for content in (doc_content, export_content):
        assert "第五项B扩展试点候选池设计" in content
        assert "候选池按类型抽样，不按名气或预期高低抽样" in content
        assert "recommended_priority" in content
        assert "不作定档结论" in content
        assert "不生成正式分" in content
        assert "不排名" in content
        assert "不生成阶段总榜或总榜" in content
        assert "刘邦" in content
        assert "雍正" in content
        assert "朱元璋" in content
        assert "赵匡胤" in content
        assert "嬴政" in content
        assert "刘彻" in content
        assert "武则天" in content
        assert "强正但负证较少" in content
        assert "用人强但有明显反向事件" in content
        assert "行政强但授权偏弱" in content
        assert "证据印象强但证据簇不足" in content
        assert "负证主导、正证不足" in content
        assert "非军事/非开国光环型" in content
        assert "边界争议型" in content

