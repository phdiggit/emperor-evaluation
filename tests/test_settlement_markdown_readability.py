from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SETTLEMENT_ROOT = ROOT / "docs/评分结算"
SECOND_ITEM = SETTLEMENT_ROOT / "第二项治国净收益"


def _reader_views() -> list[Path]:
    return sorted(
        path
        for path in SETTLEMENT_ROOT.rglob("*.md")
        if path.name != "README.md" and "分析" not in path.name
    )


def test_settlement_reader_views_are_utf8_without_bom() -> None:
    paths = _reader_views()
    assert SETTLEMENT_ROOT / "皇帝人物画像/雷达图小样/00-雷达图小样说明.md" in paths
    assert SETTLEMENT_ROOT / "皇帝人物画像/视频文字小样/00-视频人物画像文字小样.md" in paths
    for path in paths:
        raw = path.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), path
        raw.decode("utf-8")


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


def _first_table(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next(index for index, line in enumerate(lines) if line.startswith("| "))
    table: list[str] = []
    for line in lines[start:]:
        if not (line.startswith("|") and line.endswith("|")):
            break
        table.append(line)
    return table


def test_second_item_finance_views_keep_curves_k_and_merge_sparse_notes() -> None:
    finance = SECOND_ITEM / "财政民生"
    c1 = _first_table(finance / "01-C1正式结算.md")
    c2 = _first_table(finance / "02-C2正式结算.md")
    c3 = _first_table(finance / "03-C3正式结算.md")
    c4 = _first_table(finance / "04-C4正式结算.md")

    assert "全任曲线 S0→S_main→S_end" in c1[0]
    assert "全任曲线 S0→S_main→S_end" in c2[0]
    assert "K折损" in c3[0]
    assert "阶段峰值" not in c1[0] and "阶段峰值" not in c2[0]
    assert "恢复 - 可归责恶化 - DA" in c4[0]


def test_second_item_direction_views_keep_institution_and_m_chain_combinations() -> None:
    institution = SECOND_ITEM / "制度行政"
    a = (institution / "01-A制度建设与实际运行方向卡.md").read_text(encoding="utf-8")
    b1 = (institution / "02-B1官僚治理与行政执行方向卡.md").read_text(encoding="utf-8")
    method = _first_table(institution / "04-治理手段165分正式结算.md")

    assert "| 重大制度组合（按S角色） | 有效M链组合（正/混/负） |" in a
    assert "| 运行摘要 | 内部指数/100 |" in b1
    assert "## 五、逐人裁决与材料依据" in b1
    assert "- 结算依据：\n  - **裁决说明**：" in b1
    assert not re.search(
        r"(?<![A-Za-z])(?:distributed|central|support|core|personnel|capture|major-stage|mixed|N3-)",
        b1,
    )
    assert "A/B1方向指数" in method[0] and "B2方向指数→/45" in method[0]


def test_second_item_rollups_keep_components_and_sparse_caps_inline() -> None:
    handoff = _first_table(SECOND_ITEM / "政权交接稳定" / "03-交接质量20分正式结算.md")

    assert "低侧封顶" not in handoff[0]


def test_recent_second_item_batches_have_one_current_detail_block_each() -> None:
    names = {
        "刘崇", "孟知祥", "李克用", "杨行密", "钱镠", "马殷", "高季兴",
        "耶律阿保机", "耶律德光", "耶律阮", "耶律贤", "萧绰", "耶律隆绪", "耶律宗真", "耶律洪基", "耶律延禧", "耶律大石",
        "完颜阿骨打", "完颜晟", "完颜亶", "完颜亮", "完颜雍", "完颜璟", "完颜永济", "完颜珣", "完颜守绪",
    }
    paths = [
        SECOND_ITEM / "制度行政/01-A制度建设与实际运行方向卡.md",
        SECOND_ITEM / "制度行政/02-B1官僚治理与行政执行方向卡.md",
        SECOND_ITEM / "制度行政/03-B2反馈纠错与权力约束方向卡.md",
        SECOND_ITEM / "政权交接稳定/01-D1继任行政连续性方向卡.md",
        SECOND_ITEM / "政权交接稳定/02-D3政权交接稳定方向卡.md",
        SECOND_ITEM / "财政民生/01-C1正式结算.md",
        SECOND_ITEM / "财政民生/02-C2正式结算.md",
        SECOND_ITEM / "财政民生/03-C3正式结算.md",
        SECOND_ITEM / "财政民生/04-C4正式结算.md",
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for name in names:
            assert text.count(f"### {name}（") == 1, (path, name)
