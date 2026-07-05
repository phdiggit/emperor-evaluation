from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v2_quality_gate as tool


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def judge_payload(
    *,
    status: str = "succeeded",
    objects: list[str],
    claim_count: int | None = None,
    primary_binding_count: int | None = None,
) -> dict:
    claims = []
    for index in range(claim_count or len(objects)):
        object_name = objects[index % len(objects)]
        claims.append(
            {
                "claim_code": f"CLM-{index + 1:03d}",
                "object_name": object_name,
                "direction": "positive",
            }
        )
    return {
        "status": status,
        "claims": claims,
        "primary_bindings": [
            {
                "claim_code": claims[index % len(claims)]["claim_code"],
                "direction": "positive",
                "rule_code": "delegation",
                "object_role": "civil_delegate",
                "usable_for_scoring_cluster": True,
            }
            for index in range(primary_binding_count if primary_binding_count is not None else len(claims))
        ],
        "coverage_gaps": [],
    }


def candidates_payload(*, name: str, objects_without_slices: list[str] | None = None) -> dict:
    return {
        "task_identity": {"emperor_name": name, "rule_code": "delegation"},
        "stats": {"candidate_slices": 10},
        "coverage": {"objects_without_slices": objects_without_slices or []},
        "coverage_gaps": [],
    }


def write_legacy_run(root: Path, *, name: str, dirname: str, objects: list[str], claim_count: int | None = None) -> None:
    write_json(root / "summary.json", {"ok": True, "people": [{"name": name, "judge_status": "succeeded"}]})
    write_json(root / dirname / "judge_result.json", judge_payload(objects=objects, claim_count=claim_count))
    write_json(root / dirname / "candidates.json", candidates_payload(name=name))


def write_new_run(
    root: Path,
    *,
    name: str,
    target_dir: str,
    objects: list[str],
    claim_count: int | None = None,
    primary_binding_count: int | None = None,
    status: str = "succeeded",
    objects_without_slices: list[str] | None = None,
) -> None:
    person_dir = root / target_dir
    judge_path = person_dir / "judge_result.final.json"
    candidates_path = person_dir / "candidates.final.json"
    write_json(
        judge_path,
        judge_payload(
            status=status,
            objects=objects,
            claim_count=claim_count,
            primary_binding_count=primary_binding_count,
        ),
    )
    write_json(candidates_path, candidates_payload(name=name, objects_without_slices=objects_without_slices))
    write_json(
        root / "summary.json",
        {
            "ok": True,
            "people": [
                {
                    "name": name,
                    "judge_status": status,
                    "files": {
                        "final_judge_result": str(judge_path),
                        "final_candidates": str(candidates_path),
                    },
                }
            ],
        },
    )


def test_compare_runs_accepts_equal_coverage_and_more_claims(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    write_legacy_run(
        baseline,
        name="李世民",
        dirname="lishimin",
        objects=["张公谨", "李靖"],
        claim_count=2,
    )
    write_new_run(
        candidate,
        name="李世民",
        target_dir="TGT-LSM",
        objects=["張公謹", "李靖"],
        claim_count=4,
    )

    result = tool.compare_runs(baseline_run_root=baseline, candidate_run_root=candidate)

    assert result["ok"] is True
    assert result["people"][0]["lost_objects"] == []
    assert result["people"][0]["candidate"]["claim_count"] == 4


def test_compare_runs_blocks_object_coverage_regression(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    write_legacy_run(
        baseline,
        name="曹操",
        dirname="caocao",
        objects=["荀攸", "郭嘉", "张辽"],
        claim_count=3,
    )
    write_new_run(
        candidate,
        name="曹操",
        target_dir="TGT-CC",
        objects=["郭嘉"],
        claim_count=1,
        objects_without_slices=["张辽"],
    )

    result = tool.compare_runs(baseline_run_root=baseline, candidate_run_root=candidate)

    assert result["ok"] is False
    block_codes = {row["code"] for row in result["blocks"]}
    assert "object_coverage_regressed" in block_codes
    assert "objects_without_slices" in block_codes
    assert "claim_count_regressed" in block_codes


def test_compare_runs_warns_for_primary_count_regression_when_direction_coverage_is_equal(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    write_legacy_run(
        baseline,
        name="赵匡胤",
        dirname="zhaokuangyin",
        objects=["石守信", "薛居正"],
        claim_count=4,
    )
    write_new_run(
        candidate,
        name="赵匡胤",
        target_dir="TGT-ZKY",
        objects=["石守信", "薛居正"],
        claim_count=4,
        primary_binding_count=2,
    )

    result = tool.compare_runs(baseline_run_root=baseline, candidate_run_root=candidate)

    assert result["ok"] is True
    assert result["blocks"] == []
    assert {row["code"] for row in result["warnings"]} == {"primary_binding_count_regressed"}


def test_compare_runs_ignores_non_scoring_direction_regression(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    write_legacy_run(
        baseline,
        name="曹操",
        dirname="caocao",
        objects=["贾诩"],
        claim_count=1,
    )
    baseline_judge = json.loads((baseline / "caocao" / "judge_result.json").read_text(encoding="utf-8"))
    baseline_judge["claims"].append(
        {
            "claim_code": "CLM-NONSCORING",
            "object_name": "贾诩",
            "direction": "negative",
        }
    )
    baseline_judge["primary_bindings"].append(
        {
            "claim_code": "CLM-NONSCORING",
            "direction": "negative",
            "rule_code": "delegation",
            "object_role": "misdelegated_actor",
            "usable_for_scoring_cluster": False,
        }
    )
    write_json(baseline / "caocao" / "judge_result.json", baseline_judge)
    write_new_run(
        candidate,
        name="曹操",
        target_dir="TGT-CC",
        objects=["贾诩"],
        claim_count=2,
    )

    result = tool.compare_runs(baseline_run_root=baseline, candidate_run_root=candidate)

    assert result["ok"] is True
    assert result["blocks"] == []


def test_compare_runs_blocks_scoring_direction_regression(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    write_legacy_run(
        baseline,
        name="李世民",
        dirname="lishimin",
        objects=["薛万彻"],
        claim_count=1,
    )
    baseline_judge = json.loads((baseline / "lishimin" / "judge_result.json").read_text(encoding="utf-8"))
    baseline_judge["claims"].append(
        {
            "claim_code": "CLM-NEGATIVE",
            "object_name": "薛万彻",
            "direction": "negative",
        }
    )
    baseline_judge["primary_bindings"].append(
        {
            "claim_code": "CLM-NEGATIVE",
            "direction": "negative",
            "rule_code": "delegation",
            "object_role": "authority_revoked_target",
            "usable_for_scoring_cluster": True,
        }
    )
    write_json(baseline / "lishimin" / "judge_result.json", baseline_judge)
    write_new_run(
        candidate,
        name="李世民",
        target_dir="TGT-LSM",
        objects=["薛万彻"],
        claim_count=2,
    )

    result = tool.compare_runs(baseline_run_root=baseline, candidate_run_root=candidate)

    assert result["ok"] is False
    assert {row["code"] for row in result["blocks"]} == {"object_direction_coverage_regressed"}
