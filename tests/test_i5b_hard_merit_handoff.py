from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "scripts" / "dev" / "i5b_hard_merit_handoff.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("i5b_hard_merit_handoff_under_test", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_handoff_maps_ready_i5b_catalog_candidate(tmp_path: Path) -> None:
    tool = load_tool()
    batch = tmp_path / "batch-demo"
    write_jsonl(
        batch / "hard_merit_attrs.jsonl",
        [
            {
                "emperor": "李世民",
                "object_name": "李靖",
                "career_track": "military",
                "hard_merit_tags": ["military_campaign"],
                "hard_merit_summary": "受命统军。",
                "hard_merit_scope_hint": "dynasty_core",
                "source_refs": ["旧唐书 卷..."],
            }
        ],
    )
    write_jsonl(
        batch / "fact_relation_hints.jsonl",
        [
            {
                "emperor": "李世民",
                "subject_name": "李靖",
                "subject_obj_id": 60,
                "predicate_hint": "delegated_military_command",
                "relation_role_hint": "cross_item_candidate",
                "target_items_hint": ["I5B.appointment_delegation", "国防安全"],
                "fact_summary": "受命统军攻灭东突厥。",
                "source_refs": ["旧唐书 卷..."],
            }
        ],
    )

    report, candidates = tool.build_report(tmp_path)

    assert report["blocks"] == 0
    assert report["mapping_status_counts"] == {"cross_item_pending": 1, "ready_i5b_catalog": 1}
    ready = [row for row in candidates if row["mapping_status"] == "ready_i5b_catalog"][0]
    assert ready["rule_code"] == "appointment_delegation"
    assert ready["formal_predicate"] == "appointed_or_delegated_authority"


def test_negative_attr_row_may_have_no_hard_merit_tags(tmp_path: Path) -> None:
    tool = load_tool()
    batch = tmp_path / "batch-demo"
    write_jsonl(
        batch / "hard_merit_attrs.jsonl",
        [
            {
                "emperor": "弘历",
                "object_name": "和珅",
                "career_track": "negative",
                "hard_merit_summary": "乾隆晚年权臣风险链。",
                "hard_merit_scope_hint": "dynasty_core",
                "source_refs": ["清史稿 卷..."],
                "limitations": "负向对象无正向硬通货标签。",
            }
        ],
    )

    report, _ = tool.build_report(tmp_path)

    assert report["blocks"] == 0
