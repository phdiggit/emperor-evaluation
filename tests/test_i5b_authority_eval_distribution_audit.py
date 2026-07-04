from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "scripts" / "dev" / "i5b_authority_eval_distribution_audit.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("i5b_authority_eval_distribution_audit_under_test", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_distribution_audit_flags_generic_top_grade(tmp_path: Path) -> None:
    tool = load_tool()
    batch = tmp_path / "batch-demo"
    write_jsonl(
        batch / "authority_eval_attrs.jsonl",
        [
            {
                "emperor": "赵祯",
                "object_name": "甲",
                "authority_eval_summary": "正史有传，历任中枢重臣，评价较高。",
                "authority_eval_sources": [
                    {
                        "source_type": "official_history",
                        "source_ref": "宋史 某传",
                        "evaluation_note": "列传记其任职。",
                    }
                ],
                "talent_quality_proposal": "顶级人才",
                "talent_quality_basis": "authority_consensus",
                "confidence": "high",
            }
        ],
    )

    report, findings = tool.build_report(tmp_path)

    assert report["review_candidate_count"] == 1
    assert findings[0]["recommended_action"] == "review_top_to_important_or_keep"
    assert findings[0]["review_codes"] == ["top_grade_single_source", "top_grade_needs_outcome_basis"]


def test_distribution_audit_flags_important_grade_for_ordinary_check(tmp_path: Path) -> None:
    tool = load_tool()
    batch = tmp_path / "batch-demo"
    write_jsonl(
        batch / "authority_eval_attrs.jsonl",
        [
            {
                "emperor": "刘恒",
                "object_name": "乙",
                "authority_eval_summary": "历任地方官员，参与政务执行。",
                "authority_eval_sources": [
                    {
                        "source_type": "official_history",
                        "source_ref": "汉书 某传",
                        "evaluation_note": "列其任官。",
                    }
                ],
                "talent_quality_proposal": "重要人才",
                "talent_quality_basis": "authority_consensus",
                "confidence": "high",
            }
        ],
    )

    report, findings = tool.build_report(tmp_path)

    assert report["review_action_counts"] == {"review_important_to_ordinary_or_keep": 1}
    assert findings[0]["review_codes"] == ["important_grade_needs_ordinary_check"]


def test_distribution_audit_does_not_flag_strong_multisource_historical_candidate(tmp_path: Path) -> None:
    tool = load_tool()
    batch = tmp_path / "batch-demo"
    write_jsonl(
        batch / "authority_eval_attrs.jsonl",
        [
            {
                "emperor": "刘邦",
                "object_name": "韩信",
                "authority_eval_summary": "正史与编年均突出其统帅战役、战略平定和楚汉战争格局塑造。",
                "authority_eval_sources": [
                    {
                        "source_type": "official_history",
                        "source_ref": "史记 淮阴侯列传",
                        "evaluation_note": "本传记其统兵战绩。",
                    },
                    {
                        "source_type": "chronicle",
                        "source_ref": "资治通鉴 汉纪",
                        "evaluation_note": "编年叙其方面军作用。",
                    },
                ],
                "talent_quality_proposal": "历史级人才",
                "talent_quality_basis": "authority_consensus",
                "confidence": "high",
            }
        ],
    )

    report, findings = tool.build_report(tmp_path)

    assert report["review_candidate_count"] == 0
    assert findings == []


def test_distribution_audit_skips_reviewed_keep_rows(tmp_path: Path) -> None:
    tool = load_tool()
    batch = tmp_path / "batch-demo"
    write_jsonl(
        batch / "authority_eval_attrs.jsonl",
        [
            {
                "emperor": "赵祯",
                "object_name": "甲",
                "authority_eval_summary": "正史有传，历任中枢重臣，评价较高。",
                "authority_eval_sources": [
                    {
                        "source_type": "official_history",
                        "source_ref": "宋史 某传",
                        "evaluation_note": "列传记其任职。",
                    }
                ],
                "talent_quality_proposal": "顶级人才",
                "talent_quality_basis": "authority_consensus",
                "confidence": "high",
                "distribution_review_status": "keep_top",
                "distribution_review_note": "人工复核认为仍应保留顶级。",
            }
        ],
    )

    report, findings = tool.build_report(tmp_path)

    assert report["review_candidate_count"] == 0
    assert findings == []


def test_distribution_audit_flags_mixed_profile_negative_followup(tmp_path: Path) -> None:
    tool = load_tool()
    batch = tmp_path / "batch-demo"
    write_jsonl(
        batch / "authority_eval_attrs.jsonl",
        [
            {
                "emperor": "刘秀",
                "object_name": "吴汉",
                "authority_eval_summary": "正史评价其为东汉开国核心统帅，战役和平定割据功绩突出。",
                "authority_eval_sources": [
                    {
                        "source_type": "official_history",
                        "source_ref": "后汉书 吴汉传",
                        "evaluation_note": "本传记其统兵功绩。",
                    },
                    {
                        "source_type": "chronicle",
                        "source_ref": "资治通鉴 汉纪",
                        "evaluation_note": "编年叙其军事行动。",
                    },
                ],
                "talent_quality_proposal": "历史级人才",
                "talent_quality_basis": "mixed",
                "confidence": "high",
                "talent_profile_note": "军事才能可列历史级，但用兵严酷、屠掠和治理伤害风险明显。",
            }
        ],
    )

    report, findings = tool.build_report(tmp_path)

    assert report["review_action_counts"] == {"review_mixed_profile_negative_followup": 1}
    assert findings[0]["review_codes"] == ["positive_talent_with_negative_profile_note"]
    assert findings[0]["talent_profile_note"].startswith("军事才能可列历史级")


def test_distribution_audit_skips_reviewed_mixed_profile_note(tmp_path: Path) -> None:
    tool = load_tool()
    batch = tmp_path / "batch-demo"
    write_jsonl(
        batch / "authority_eval_attrs.jsonl",
        [
            {
                "emperor": "刘秀",
                "object_name": "吴汉",
                "authority_eval_summary": "正史评价其为东汉开国核心统帅，战役和平定割据功绩突出。",
                "authority_eval_sources": [
                    {
                        "source_type": "official_history",
                        "source_ref": "后汉书 吴汉传",
                        "evaluation_note": "本传记其统兵功绩。",
                    },
                    {
                        "source_type": "chronicle",
                        "source_ref": "资治通鉴 汉纪",
                        "evaluation_note": "编年叙其军事行动。",
                    },
                ],
                "talent_quality_proposal": "历史级人才",
                "talent_quality_basis": "mixed",
                "confidence": "high",
                "talent_profile_note": "军事才能可列历史级，但用兵严酷、屠掠和治理伤害风险明显。",
                "mixed_profile_review_status": "negative_followup_recorded",
            }
        ],
    )

    report, findings = tool.build_report(tmp_path)

    assert report["review_candidate_count"] == 0
    assert findings == []


def test_distribution_audit_writes_action_worklists(tmp_path: Path) -> None:
    tool = load_tool()
    batch = tmp_path / "batch-demo"
    output_dir = tmp_path / "review"
    write_jsonl(
        batch / "authority_eval_attrs.jsonl",
        [
            {
                "emperor": "赵祯",
                "object_name": "甲",
                "authority_eval_summary": "正史有传，历任中枢重臣，评价较高。",
                "authority_eval_sources": [
                    {
                        "source_type": "official_history",
                        "source_ref": "宋史 某传",
                        "evaluation_note": "列传记其任职。",
                    }
                ],
                "talent_quality_proposal": "顶级人才",
                "talent_quality_basis": "authority_consensus",
                "confidence": "high",
            }
        ],
    )

    report, findings = tool.build_report(tmp_path)
    tool.write_outputs(report, findings, output_dir)

    worklist = (output_dir / "authority_eval_review_top_to_important_or_keep.jsonl").read_text(encoding="utf-8")
    assert "赵祯" in worklist
    assert "甲" in worklist
