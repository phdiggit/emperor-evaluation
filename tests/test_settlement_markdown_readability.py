from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SETTLEMENT_ROOT = ROOT / "docs/评分结算"
SECOND_ITEM = SETTLEMENT_ROOT / "第二项治国净收益"
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
    assert len(paths) == 47
    assert SETTLEMENT_ROOT / "皇帝人物画像/雷达图小样/00-雷达图小样说明.md" in paths
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

    assert all(len(table) == 187 for table in (c1, c2, c3, c4))
    assert "全任曲线 S0→S_main→S_end" in c1[0]
    assert "全任曲线 S0→S_main→S_end" in c2[0]
    assert "K稳定性（诊断）" in c3[0]
    assert "阶段峰值" not in c1[0] and "阶段峰值" not in c2[0]
    assert any("赵恒" in line and "（峰值：C1-5）" in line for line in c1)
    assert any("弘历" in line and "（峰值：C2-5）" in line for line in c2)
    assert "净恢复 + K稳定承压 - 恶化 - DA" in c4[0]
    assert any("杨广" in line and "恶化归责=FULL" in line and "DA4放大" in line for line in c4)


def test_second_item_direction_views_keep_institution_and_m_chain_combinations() -> None:
    institution = SECOND_ITEM / "制度行政"
    a = (institution / "01-A制度建设与实际运行方向卡.md").read_text(encoding="utf-8")
    b1 = (institution / "02-B1官僚治理与行政执行方向卡.md").read_text(encoding="utf-8")
    b2 = (institution / "03-B2反馈纠错与权力约束方向卡.md").read_text(encoding="utf-8")
    method = _first_table(institution / "04-治理手段165分正式结算.md")

    assert "| 重大制度组合（按S角色） | 有效M链组合（正/混/负） |" in a
    assert "李嗣源" in a and "三司使统合中央财赋接口〔正M3〕" in a
    assert "设置端明殿学士顾问接口〔正M2〕" in a
    zhu_line = next(line for line in a.splitlines() if "| 朱元璋 |" in line)
    assert "S+骨架：《大明律》统一公开法源并获后世遵行〔S+〕" in zhu_line
    assert "S−/逆转：拒绝因律例冲突调整定律〔S-1〕" in zhu_line
    assert zhu_line.count("科举、都察院、殿阁大学士与三法司复核接口〔混M2〕") == 1
    assert "黄册十年大造与里甲编役〔正M3/混M3〕" in zhu_line
    assert "| M链组合 | 裁决摘要 |" in b1
    assert "| M链组合 | 裁决摘要 |" in b2
    assert "任圜任内府库军民与朝纲改善〔正M3〕" in b1
    assert "诬告安重诲案经担保与复奏后纠正〔正M2〕" in b2
    assert "A/B1方向指数" in method[0] and "B2方向指数→/45" in method[0]


def test_second_item_rollups_keep_components_and_sparse_caps_inline() -> None:
    handoff = _first_table(SECOND_ITEM / "政权交接稳定" / "03-交接质量20分正式结算.md")
    total = _first_table(SECOND_ITEM / "01-第二项治国净收益405分正式结算.md")

    assert len(handoff) == 187 and len(total) == 187
    assert "低侧封顶" not in handoff[0]
    assert any("王建" in line and "（低侧封顶12.0）" in line for line in handoff)
    assert all(label in total[0] for label in ("C1/80", "C2/35", "C3/60", "C4/-45—45"))


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
