import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def script_path(script_name: str) -> Path:
    routes = {
        "validate_evidence.py": Path("scripts/validate/validate_evidence.py"),
        "build_db.py": Path("scripts/build/build_db.py"),
        "export_md.py": Path("scripts/export/export_md.py"),
        "export_i5b_auto_adjudication.py": Path("scripts/export/export_i5b_auto_adjudication.py"),
    }
    return ROOT / routes.get(script_name, Path("scripts") / script_name)


RETIRED_CANDIDATE_POOL_DOC_PATH = ROOT / "docs" / "第五项B扩展试点候选池设计.md"
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


def run_script(script_name: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script_path(script_name)), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.export_full
@pytest.mark.integration
@pytest.mark.db
def test_export_md_generates_expanded_candidate_pool_design_export_only() -> None:
    build_result = run_script("build_db.py")
    assert build_result.returncode == 0, build_result.stdout + build_result.stderr

    export_result = run_script("export_md.py", "--profile", "project-docs")
    assert export_result.returncode == 0, export_result.stdout + export_result.stderr
    assert not RETIRED_CANDIDATE_POOL_DOC_PATH.exists()
    assert CANDIDATE_POOL_EXPORT_PATH.exists()

    content = CANDIDATE_POOL_EXPORT_PATH.read_text(encoding="utf-8")

    for needle in [
        "第五项B扩展试点候选池设计",
        "候选池按类型抽样，不按名气或预期高低抽样",
        "recommended_priority",
        "不作定档结论",
        "不生成正式分",
        "不排名",
        "不生成阶段总榜或总榜",
        "刘邦",
        "雍正",
        "朱元璋",
        "赵匡胤",
        "嬴政",
        "刘彻",
        "武则天",
        "强正但负证较少",
        "用人强但有明显反向事件",
        "行政强但授权偏弱",
        "证据印象强但证据簇不足",
        "负证主导、正证不足",
        "非军事/非开国光环型",
        "边界争议型",
    ]:
        assert needle in content
