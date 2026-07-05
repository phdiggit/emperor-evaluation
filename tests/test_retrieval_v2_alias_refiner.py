from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v2_alias_refiner as tool
from scripts.dev.retrieval_v2_contracts import alias_script_variants


def sample_task() -> dict:
    return {
        "job_code": "JOB-I5B-ZKY-DELEGATION",
        "target_code": "TGT-I5B-2E7B9861051F",
        "emperor_name": "赵匡胤",
        "item_code": "I5B",
        "contract_code": "I5B-RETRIEVAL-V2-20260704",
        "rule_code": "delegation",
        "object_seeds": [
            {"aliases": [{"text": "党進", "strength": "strong"}, {"text": "侍衛步軍指揮使", "strength": "medium"}]},
            {"aliases": [{"text": "呂餘慶", "strength": "strong"}, {"text": "參知政事", "strength": "medium"}]},
            {"name": "威侯", "aliases": [{"alias": "威侯", "strength": "weak"}]},
        ],
    }


def sample_judge_result() -> dict:
    return {
        "coverage_gaps": [
            {
                "gap_type": "alias_missing",
                "object_name": "党進",
                "family_code": "military_delegate",
                "diagnosis": "coverage 中该对象无直接命中。",
                "recommended_action": "补充强别名“党进”，并用既有潘美/北汉方向源页重跑切片。",
            },
            {
                "gap_type": "alias_missing",
                "object_name": "呂餘慶",
                "family_code": "civil_delegate",
                "diagnosis": "coverage 中该对象无直接命中。",
                "recommended_action": "补充“吕馀庆”“吕余庆”“呂余慶”等异体/简繁别名后重跑切片。",
            },
            {
                "gap_type": "weak_alias_noise",
                "object_name": "威侯",
                "family_code": "military_delegate",
                "diagnosis": "all candidate slices rely only on weak aliases",
                "recommended_action": "require target-era context co-occurrence or add stronger aliases before judging",
            },
        ]
    }


def test_alias_script_variants_cover_common_simplified_traditional_forms() -> None:
    assert {"党進", "党进", "黨進", "黨进"} <= set(alias_script_variants("党進"))
    variants = set(alias_script_variants("呂餘慶"))
    assert {"呂餘慶", "吕余庆", "吕馀庆", "呂余慶"} <= variants
    assert {"張亮", "张亮"} <= set(alias_script_variants("張亮"))
    assert {"房玄齡", "房玄龄"} <= set(alias_script_variants("房玄齡"))
    assert {"長孫無忌", "长孙无忌"} <= set(alias_script_variants("長孫無忌"))
    assert {"程知節", "程知节"} <= set(alias_script_variants("程知節"))
    assert {"薛萬徹", "薛万彻"} <= set(alias_script_variants("薛萬徹"))
    assert {"左僕射", "左仆射"} <= set(alias_script_variants("左僕射"))
    assert {"侍衛步軍指揮使", "侍卫步军指挥使"} <= set(alias_script_variants("侍衛步軍指揮使"))
    assert {"參知政事", "参知政事"} <= set(alias_script_variants("參知政事"))


def test_build_alias_patches_splits_mechanical_and_cli_work() -> None:
    patches = tool.build_alias_patches(sample_task(), sample_judge_result())

    by_object = {patch["object_name"]: patch for patch in patches}

    assert by_object["党進"]["target_action"] == "apply_aliases"
    assert "党进" in {row["alias"] for row in by_object["党進"]["added_aliases"]}
    assert by_object["呂餘慶"]["target_action"] == "apply_aliases"
    assert {"吕余庆", "吕馀庆"} <= {row["alias"] for row in by_object["呂餘慶"]["added_aliases"]}
    assert by_object["威侯"]["target_action"] == "needs_cli_alias_refiner"


def test_apply_alias_patches_updates_existing_seeds_without_duplicate() -> None:
    patches = tool.build_alias_patches(sample_task(), sample_judge_result())

    updated = tool.apply_alias_patches(sample_task(), patches)

    first_aliases = updated["object_seeds"][0]["aliases"]
    second_aliases = updated["object_seeds"][1]["aliases"]
    assert any(row.get("alias") == "党进" for row in first_aliases)
    assert any(row.get("alias") == "吕余庆" for row in second_aliases)
    assert updated["alias_refinement"]["patch_count"] == 3


def test_cli_writes_patch_task_and_prompt(tmp_path: Path) -> None:
    task_path = tmp_path / "task.json"
    judge_path = tmp_path / "judge.json"
    patch_path = tmp_path / "alias_patch.json"
    output_task_path = tmp_path / "task.alias_refined.json"
    prompt_path = tmp_path / "alias_refiner_prompt.md"
    task_path.write_text(json.dumps(sample_task(), ensure_ascii=False), encoding="utf-8")
    judge_path.write_text(json.dumps(sample_judge_result(), ensure_ascii=False), encoding="utf-8")

    assert tool.main(
        [
            "--task",
            str(task_path),
            "--judge-result",
            str(judge_path),
            "--output-patch",
            str(patch_path),
            "--output-task",
            str(output_task_path),
            "--prompt-output",
            str(prompt_path),
        ]
    ) == 0

    patch = json.loads(patch_path.read_text(encoding="utf-8"))
    refined_task = json.loads(output_task_path.read_text(encoding="utf-8"))
    prompt = prompt_path.read_text(encoding="utf-8")
    assert patch["stats"]["apply_alias_patch_count"] == 2
    assert patch["stats"]["cli_alias_refiner_count"] == 1
    assert any(row.get("alias") == "党进" for row in refined_task["object_seeds"][0]["aliases"])
    assert "alias-refiner worker" in prompt
    assert "威侯" in prompt
