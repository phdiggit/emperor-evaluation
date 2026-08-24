from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SETTLEMENT_ROOT = ROOT / "docs/评分结算"
BANNED_READER_NOISE = re.compile(
    r"机器读取|机器事实源|机器可读|同名JSON|正式JSON|"
    r"数据库(?:未写入|写入|关闭)|canonical状态|结算状态|覆盖状态|节点状态|"
    r"晋升门|覆盖门|为什么是这档|定档理由|合成说明|结果结构|档位路径|"
    r"任务结果剖面|材料角色|结果闭合：|档内净余|补充核验|"
    r"FORMAL_CURRENT|CURRENT_ACCEPTED|CALIBRATED_CURRENT|"
    r"REVIEWED_NO_THRESHOLD_ERROR|NOT_APPLICABLE_NO_SYSTEM_STRESS|`UNRESOLVED`"
)


def _reader_views() -> list[Path]:
    return sorted(
        path
        for path in SETTLEMENT_ROOT.rglob("*.md")
        if path.name != "README.md" and "分析" not in path.name
    )


def test_settlement_reader_views_exclude_machine_audit_and_template_noise() -> None:
    paths = _reader_views()
    assert len(paths) == 29
    for path in paths:
        raw = path.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), path
        for line_number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
            assert not BANNED_READER_NOISE.search(line), f"{path}:{line_number}:{line}"


def test_settlement_reader_view_tables_have_stable_column_counts() -> None:
    for path in _reader_views():
        expected: int | None = None
        for line in path.read_text(encoding="utf-8").splitlines() + [""]:
            if line.startswith("|") and line.endswith("|"):
                column_count = len(line[1:-1].split("|"))
                if expected is None:
                    expected = column_count
                else:
                    assert column_count == expected, f"{path}:{line}"
            else:
                expected = None
