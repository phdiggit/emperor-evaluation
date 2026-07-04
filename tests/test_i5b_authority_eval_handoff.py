from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "scripts" / "dev" / "i5b_authority_eval_handoff.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("i5b_authority_eval_handoff_under_test", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_authority_eval_handoff_accepts_high_confidence_candidate(tmp_path: Path) -> None:
    tool = load_tool()
    batch = tmp_path / "batch-demo"
    write_jsonl(
        batch / "authority_eval_attrs.jsonl",
        [
            {
                "emperor": "李世民",
                "object_name": "李靖",
                "career_track": "military",
                "authority_eval_summary": "正史与后世编年材料均将李靖列为唐初核心军事人才。",
                "authority_eval_sources": [
                    {
                        "source_type": "official_history",
                        "source_ref": "旧唐书 卷六十七 李靖传",
                        "evaluation_note": "本传集中记其军事功绩与朝廷任用。",
                    },
                    {
                        "source_type": "chronicle",
                        "source_ref": "资治通鉴 唐纪",
                        "evaluation_note": "编年叙事中反复作为唐初军事授权核心出现。",
                    },
                ],
                "talent_quality_proposal": "历史级人才",
                "talent_quality_basis": "authority_consensus",
                "confidence": "high",
                "authority_eval_limitations": "仍需与李世民发现链条分开入分。",
                "talent_profile_note": "军事才能历史级；本字段只说明能力，不抵消负向事实。",
            }
        ],
    )

    report, candidates = tool.build_report(tmp_path)

    assert report["blocks"] == 0
    assert report["warnings"] == 0
    assert report["candidate_status_counts"] == {"ready_high_confidence": 1}
    assert candidates[0]["talent_quality_proposal"] == "历史级人才"
    assert candidates[0]["source_type_counts"] == {"chronicle": 1, "official_history": 1}
    assert candidates[0]["talent_profile_note"] == "军事才能历史级；本字段只说明能力，不抵消负向事实。"


def test_authority_eval_handoff_writes_priority_markdown(tmp_path: Path) -> None:
    tool = load_tool()
    batch = tmp_path / "batch-demo"
    output_dir = tmp_path / "review"
    write_jsonl(
        batch / "authority_eval_attrs.jsonl",
        [
            {
                "emperor": "李世民",
                "object_name": "魏徵",
                "career_track": "civil",
                "authority_eval_summary": "正史与编年材料均把魏徵列为唐初核心谏臣。",
                "authority_eval_sources": [
                    {
                        "source_type": "official_history",
                        "source_ref": "旧唐书 卷七十一 魏徵传",
                        "evaluation_note": "本传以谏诤和朝廷信用为主线。",
                    }
                ],
                "talent_quality_proposal": "顶级人才",
                "talent_quality_basis": "authority_consensus",
                "confidence": "high",
                "talent_profile_note": "顶级谏臣，但具体入分仍需事实链。",
            }
        ],
    )

    report, candidates = tool.build_report(tmp_path)
    tool.write_outputs(report, candidates, output_dir)

    priority = (output_dir / "talent_quality_priority_candidates.md").read_text(encoding="utf-8")
    assert "魏徵" in priority
    assert "顶级人才" in priority
    assert "profile_note" in priority


def test_authority_eval_handoff_warns_on_weak_sources_for_high_proposal(tmp_path: Path) -> None:
    tool = load_tool()
    batch = tmp_path / "batch-demo"
    write_jsonl(
        batch / "authority_eval_attrs.jsonl",
        [
            {
                "emperor": "刘邦",
                "object_name": "某人",
                "authority_eval_summary": "只见传说性评价。",
                "authority_eval_sources": [
                    {
                        "source_type": "literary_tradition",
                        "source_ref": "后世演义",
                        "evaluation_note": "文学化称誉。",
                    }
                ],
                "talent_quality_proposal": "历史级人才",
                "talent_quality_basis": "authority_consensus",
                "confidence": "medium",
            }
        ],
    )

    report, candidates = tool.build_report(tmp_path)

    assert report["blocks"] == 0
    assert report["warnings"] == 1
    assert report["candidate_status_counts"] == {"needs_review": 1}
    assert candidates[0]["issue_codes"] == ["weak_sources_for_high_proposal"]


def test_authority_eval_handoff_blocks_invalid_source_type(tmp_path: Path) -> None:
    tool = load_tool()
    batch = tmp_path / "batch-demo"
    write_jsonl(
        batch / "authority_eval_attrs.jsonl",
        [
            {
                "emperor": "赵祯",
                "object_name": "范仲淹",
                "authority_eval_summary": "评价摘要。",
                "authority_eval_sources": [
                    {
                        "source_type": "blog",
                        "source_ref": "unknown",
                        "evaluation_note": "非权威来源。",
                    }
                ],
                "talent_quality_proposal": "顶级人才",
                "talent_quality_basis": "authority_consensus",
                "confidence": "medium",
            }
        ],
    )

    report, candidates = tool.build_report(tmp_path)

    assert report["blocks"] == 1
    assert candidates[0]["candidate_status"] == "blocked"
