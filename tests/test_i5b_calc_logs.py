from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "scripts" / "dev" / "i5b_calc_logs.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("i5b_calc_logs_under_test", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_latest_cluster_log_rows_filters_and_keeps_latest_replayable_row(tmp_path: Path) -> None:
    tool = load_tool()
    log = tmp_path / "clusters.jsonl"
    write_jsonl(
        log,
        [
            {
                "emperor": "测试帝",
                "rule_code": "talent_discovery",
                "formula_code": "formula_a",
                "positive_signal": "1.000",
                "calc_detail": {"materials": [{"obj_name": "甲"}]},
            },
            {
                "emperor": "测试帝",
                "rule_code": "delegation",
                "formula_code": "formula_a",
                "positive_signal": "9.999",
            },
            {
                "emperor": "测试帝",
                "rule_code": "talent_discovery",
                "formula_code": "formula_a",
                "positive_signal": "2.000",
                "calc_detail": {"materials": [{"obj_name": "乙"}]},
            },
            {
                "emperor": "测试帝",
                "rule_code": "talent_discovery",
                "formula_code": "formula_a",
                "positive_signal": "4.000",
                "calc_detail": None,
            },
            {
                "emperor": "测试帝",
                "rule_code": "talent_discovery",
                "formula_code": "formula_b",
                "positive_signal": "3.000",
                "calc_detail": {"materials": [{"obj_name": "丙"}]},
            },
        ],
    )

    rows = tool.latest_cluster_log_rows(
        log,
        formula_code="formula_a",
        emperors=("测试帝",),
        require_calc_detail=True,
    )

    assert set(rows) == {("测试帝", "talent_discovery")}
    assert rows[("测试帝", "talent_discovery")]["positive_signal"] == "2.000"
    assert rows[("测试帝", "talent_discovery")]["calc_detail"]["materials"][0]["obj_name"] == "乙"


def test_latest_item_result_log_rows_filters_by_formula_and_emperor(tmp_path: Path) -> None:
    tool = load_tool()
    log = tmp_path / "results.jsonl"
    write_jsonl(
        log,
        [
            {"emperor": "测试帝", "formula_code": "result_a", "score": "10.000"},
            {"emperor": "旁观帝", "formula_code": "result_a", "score": "20.000"},
            {"emperor": "测试帝", "formula_code": "result_a", "score": "30.000"},
            {"emperor": "测试帝", "formula_code": "result_b", "score": "40.000"},
        ],
    )

    rows = tool.latest_item_result_log_rows(log, formula_code="result_a", emperors=("测试帝",))

    assert set(rows) == {"测试帝"}
    assert rows["测试帝"]["score"] == "30.000"
