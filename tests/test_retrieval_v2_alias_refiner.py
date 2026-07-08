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
    assert {"冯唐", "馮唐"} <= set(alias_script_variants("冯唐"))
    assert {"左僕射", "左仆射"} <= set(alias_script_variants("左僕射"))
    assert {"侍衛步軍指揮使", "侍卫步军指挥使"} <= set(alias_script_variants("侍衛步軍指揮使"))
    assert {"參知政事", "参知政事"} <= set(alias_script_variants("參知政事"))
    assert {"陳頊", "陈顼"} <= set(alias_script_variants("陳頊"))
    assert {"陳叔寶", "陈叔宝"} <= set(alias_script_variants("陳叔寶"))
    assert {"高歡", "高欢"} <= set(alias_script_variants("高歡"))
    assert {"高緯", "高纬"} <= set(alias_script_variants("高緯"))
    assert {"李顯", "李显"} <= set(alias_script_variants("李顯"))
    assert {"黃巢", "黄巢"} <= set(alias_script_variants("黃巢"))
    assert {"皇甫繼勳", "皇甫继勋"} <= set(alias_script_variants("皇甫继勋"))
    assert {"盧絳", "卢绛"} <= set(alias_script_variants("卢绛"))
    assert {"耶律賢", "耶律贤"} <= set(alias_script_variants("耶律贤"))
    assert {"塔不煙", "塔不烟"} <= set(alias_script_variants("塔不烟"))
    assert {"李諒祚", "李谅祚"} <= set(alias_script_variants("李谅祚"))
    assert {"李乾順", "李乾顺"} <= set(alias_script_variants("李乾顺"))
    assert {"完顏吳乞買", "完颜吴乞买"} <= set(alias_script_variants("完颜吴乞买"))
    assert {"鐵穆耳", "铁穆耳"} <= set(alias_script_variants("铁穆耳"))
    assert {"愛育黎拔力八達", "爱育黎拔力八达"} <= set(alias_script_variants("爱育黎拔力八达"))
    assert {"碩德八剌", "硕德八剌"} <= set(alias_script_variants("硕德八剌"))
    assert {"也孫鐵木兒", "也孙铁木儿"} <= set(alias_script_variants("也孙铁木儿"))
    assert {"圖帖睦爾", "图帖睦尔"} <= set(alias_script_variants("图帖睦尔"))
    assert {"妥歡帖睦爾", "妥欢帖睦尔"} <= set(alias_script_variants("妥欢帖睦尔"))
    assert {"朱高熾", "朱高炽"} <= set(alias_script_variants("朱高炽"))
    assert {"朱祁鈺", "朱祁钰"} <= set(alias_script_variants("朱祁钰"))
    assert {"朱見深", "朱见深"} <= set(alias_script_variants("朱见深"))
    assert {"載湉", "载湉"} <= set(alias_script_variants("载湉"))
    assert {"湯和", "汤和"} <= set(alias_script_variants("汤和"))
    assert {"鄧愈", "邓愈"} <= set(alias_script_variants("邓愈"))
    assert {"藍玉", "蓝玉"} <= set(alias_script_variants("蓝玉"))
    assert {"懷義", "怀义"} <= set(alias_script_variants("怀义"))
    assert {"劉蒼", "刘苍"} <= set(alias_script_variants("刘苍"))
    assert {"劉曄", "刘晔"} <= set(alias_script_variants("刘晔"))
    assert {"鍾離意", "钟离意"} <= set(alias_script_variants("钟离意"))
    assert {"婁圭", "娄圭"} <= set(alias_script_variants("娄圭"))
    assert {"狄仁傑", "狄仁杰"} <= set(alias_script_variants("狄仁杰"))


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
