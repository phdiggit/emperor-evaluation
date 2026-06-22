import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = (
    ROOT
    / "exports"
    / "markdown_views"
    / "第五项B"
    / "人工审核"
    / "自动裁判链"
    / "自动结算草案"
    / "第五项B三人试点正负证矩阵.md"
)
SEARCH_LOGS_PATH = ROOT / "data" / "search_logs.jsonl"


def test_run_matrix_exports_i5b_trial_matrix_without_touching_search_logs() -> None:
    before_search_logs = SEARCH_LOGS_PATH.read_text(encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_matrix.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert OUTPUT_PATH.exists()
    assert SEARCH_LOGS_PATH.read_text(encoding="utf-8") == before_search_logs

    content = OUTPUT_PATH.read_text(encoding="utf-8")
    assert "李世民" in content
    assert "刘秀" in content
    assert "刘庄" in content
    assert "\u6b63\u5411" in content
    assert "\u8d1f\u5411" in content
    assert "识人拔擢" in content
    assert "廷杖刑辱" in content
    assert "分数" not in content
    assert "总榜" not in content
    assert "排名" not in content
