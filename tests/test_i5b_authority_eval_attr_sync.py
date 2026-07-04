from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "scripts" / "dev" / "i5b_authority_eval_attr_sync.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("i5b_authority_eval_attr_sync_under_test", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_stable_source_key_is_deterministic() -> None:
    tool = load_tool()

    first = tool.stable_source_key(obj_id=123, source_ref="后汉书 吴汉传")
    second = tool.stable_source_key(obj_id=123, source_ref="后汉书 吴汉传")

    assert first == second
    assert first.startswith("AUTH-EVAL-")


def test_choose_object_candidate_uses_strongest_same_polarity() -> None:
    tool = load_tool()
    rows = [
        tool.JsonlRow(
            batch="batch-a",
            path=Path("a.jsonl"),
            line_no=1,
            row={
                "obj_id": 1,
                "object_name": "苏威",
                "talent_quality_proposal": "重要人才",
                "confidence": "high",
            },
        ),
        tool.JsonlRow(
            batch="batch-b",
            path=Path("b.jsonl"),
            line_no=2,
            row={
                "obj_id": 1,
                "object_name": "苏威",
                "talent_quality_proposal": "顶级人才",
                "confidence": "medium",
            },
        ),
    ]

    candidate = tool.choose_object_candidate(rows)

    assert candidate["talent_quality_proposal"] == "顶级人才"
    assert candidate["_proposal_counts"] == {"重要人才": 1, "顶级人才": 1}


def test_choose_object_candidate_keeps_legacy_high_quality_rank() -> None:
    tool = load_tool()
    rows = [
        tool.JsonlRow(
            batch="batch-a",
            path=Path("a.jsonl"),
            line_no=1,
            row={
                "obj_id": 1,
                "object_name": "旧标签人才",
                "talent_quality_proposal": "重要人才",
                "confidence": "high",
            },
        ),
        tool.JsonlRow(
            batch="batch-b",
            path=Path("b.jsonl"),
            line_no=2,
            row={
                "obj_id": 1,
                "object_name": "旧标签人才",
                "talent_quality_proposal": "高质量人才",
                "confidence": "medium",
            },
        ),
    ]

    candidate = tool.choose_object_candidate(rows)

    assert candidate["talent_quality_proposal"] == "高质量人才"
    assert tool.sync_talent_quality_rank("高质量人才") == 3
    assert tool.talent_quality_choice_key("顶级人才") > tool.talent_quality_choice_key("高质量人才")


def test_choose_object_candidate_rejects_polarity_conflict() -> None:
    tool = load_tool()
    rows = [
        tool.JsonlRow(
            batch="batch-a",
            path=Path("a.jsonl"),
            line_no=1,
            row={
                "obj_id": 1,
                "object_name": "某人",
                "talent_quality_proposal": "重要人才",
                "confidence": "high",
            },
        ),
        tool.JsonlRow(
            batch="batch-b",
            path=Path("b.jsonl"),
            line_no=2,
            row={
                "obj_id": 1,
                "object_name": "某人",
                "talent_quality_proposal": "佞臣",
                "confidence": "medium",
            },
        ),
    ]

    try:
        tool.choose_object_candidate(rows)
    except tool.AuthorityEvalAttrSyncError as exc:
        assert "mixed positive/negative proposals" in str(exc)
    else:
        raise AssertionError("expected polarity conflict")


def test_source_row_uses_existing_source_key_when_present() -> None:
    tool = load_tool()

    source = tool.source_row_for_candidate(
        {
            "obj_id": 1,
            "authority_eval_sources": [
                {
                    "source_key": "SRC-EXISTING",
                    "source_ref": "汉书 某传",
                    "evaluation_note": "本传评价。",
                }
            ],
        }
    )

    assert source["src_key"] == "SRC-EXISTING"
    assert source["title"] == "汉书 某传"


def test_load_sync_candidates_only_allows_canonical_talent_quality(tmp_path: Path) -> None:
    tool = load_tool()
    batch = tmp_path / "batch-demo"
    write_jsonl(
        batch / "authority_eval_attrs.jsonl",
        [
            {
                "obj_id": 1,
                "object_name": "旧标签人才",
                "talent_quality_proposal": "高质量人才",
                "confidence": "high",
            },
            {
                "obj_id": 2,
                "object_name": "新标签人才",
                "talent_quality_proposal": "顶级人才",
                "confidence": "medium",
            },
        ],
    )

    rows = tool.load_sync_candidates(tmp_path)

    assert [row.row["talent_quality_proposal"] for row in rows] == ["顶级人才"]
