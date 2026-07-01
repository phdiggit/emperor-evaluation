from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "scripts" / "dev" / "i5b_talent_discovery_audit.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("i5b_talent_discovery_audit_under_test", TOOL_PATH)
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


def test_expected_talent_names_parses_profile_lane() -> None:
    tool = load_tool()

    names = tool.expected_talent_names(
        {
            "expected_lane_outcomes": [
                "POS-TALENT-RECOGNITION: 萧何 / 张良 / 刘大夏（需回源确认具体发现链）",
                "POS-TEAM-STRUCTURE: 萧何 / 张良",
            ]
        }
    )

    assert names == ("萧何", "张良", "刘大夏")


def test_audit_report_flags_expected_talents_missing_from_cluster(tmp_path: Path) -> None:
    tool = load_tool()
    profile = tmp_path / "profiles.jsonl"
    cluster_log = tmp_path / "clusters.jsonl"
    result_log = tmp_path / "results.jsonl"
    write_jsonl(
        profile,
        [
            {
                "person": "测试帝",
                "query_profile_id": "QRY-1",
                "expected_lane_outcomes": ["POS-TALENT-RECOGNITION: 甲 / 乙 / 丙"],
            }
        ],
    )
    write_jsonl(
        cluster_log,
        [
            {
                "emperor": "测试帝",
                "rule_code": "talent_discovery",
                "formula_code": "cluster_formula_test",
                "calc_detail": {
                    "materials": [
                        {"obj_name": "甲", "side": "positive"},
                        {"obj_name": "丁", "side": "positive"},
                        {"obj_name": "戊", "side": "negative"},
                    ]
                },
            }
        ],
    )
    write_jsonl(result_log, [{"emperor": "测试帝", "formula_code": "result_formula_test"}])

    report = tool.build_audit_report(
        profile_path=profile,
        cluster_log=cluster_log,
        result_log=result_log,
        cluster_formula="cluster_formula_test",
        result_formula="result_formula_test",
    )
    markdown = tool.render_markdown(report)

    assert report["ok"] is False
    assert report["rows"][0]["missing"] == ["乙", "丙"]
    assert report["rows"][0]["extra"] == ["丁"]
    assert "| 测试帝 | 3：甲、乙、丙 | 2：甲、丁 | 乙、丙 | 丁 |" in markdown
