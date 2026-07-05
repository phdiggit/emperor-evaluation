from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.dev import retrieval_v2_factorization_worklists as tool


def material_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "target_code": "TGT-I5B-LB",
        "emperor_name": "刘邦",
        "item_code": "I5B",
        "source_pack_code": "SPK-I5B-LB",
        "claim_id": 10,
        "claim_code": "CLM-001",
        "raw_claim_code": "RAW-CLM-001",
        "claim_object_name": "萧何",
        "claim_object_type": "person",
        "claim_direction": "positive",
        "claim_summary": "刘邦委任萧何镇守关中并主持后方供给。",
        "binding_id": 20,
        "binding_code": "BND-001",
        "raw_binding_code": "RAW-BND-001",
        "rule_code": "delegation",
        "predicate": "delegated_authority",
        "direction": "positive",
        "object_role": "civil_delegate",
        "binding_confidence": "0.9200",
        "binding_review_status": "pending",
        "material_object_link_id": 30,
        "link_code": "MOL-001",
        "material_role": "civil_delegate",
        "object_link_confidence": "0.9200",
        "target_object_id": 40,
        "target_object_code": "TOB-001",
        "object_id": 50,
        "object_code": "OBJ-001",
        "canonical_name": "萧何",
        "normalized_name": "萧何",
        "object_type": "person",
        "talent_grade": "historic_talent",
        "talent_grade_basis": "萧何，汉初重臣。",
        "person_roles": [{"role_kind": "minister", "dynasty_label": "西汉"}],
        "person_affiliations": [{"affiliation_kind": "dynasty", "dynasty_label": "西汉"}],
        "source_passages": [{"source_title": "史记", "title": "萧相国世家", "quote": "镇国家，抚百姓。"}],
    }
    row.update(overrides)
    return row


def factor_rows() -> list[dict[str, object]]:
    return [
        {
            "rule_code": "",
            "factor_name": "source_factor",
            "factor_option_id": 1,
            "label": "基础史源",
            "value_num": "1.0000",
        },
        {
            "rule_code": "delegation",
            "factor_name": "authorization_intensity",
            "factor_option_id": 2,
            "label": "有明确授权",
            "value_num": "1.2000",
        },
        {
            "rule_code": "delegation",
            "factor_name": "person_post_fit",
            "factor_option_id": 3,
            "label": "人岗高度匹配",
            "value_num": "1.1000",
        },
        {
            "rule_code": "delegation",
            "factor_name": "result_feedback",
            "factor_option_id": 4,
            "label": "结果明确正向",
            "value_num": "1.1000",
        },
        {
            "rule_code": "delegation",
            "factor_name": "result_feedback",
            "factor_option_id": 7,
            "label": "效果较差",
            "value_num": "-0.7000",
        },
        {
            "rule_code": "",
            "factor_name": "attribution_factor",
            "factor_option_id": 5,
            "label": "可归因于皇帝授权",
            "value_num": "1.0000",
        },
        {
            "rule_code": "",
            "factor_name": "context_factor",
            "factor_option_id": 6,
            "label": "语境清楚",
            "value_num": "1.0000",
        },
    ]


def test_delegation_factor_keys_match_pending_material_contract() -> None:
    assert tool.factor_keys_for_material("delegation", "positive") == (
        "authorization_intensity",
        "person_post_fit",
        "result_feedback",
        "attribution_factor",
        "source_factor",
        "context_factor",
    )
    assert tool.factor_keys_for_material("team_building", "positive") == ()


def test_accepted_pack_scope_uses_latest_passed_pack_per_target_contract() -> None:
    predicate = tool.scope_predicate("accepted-packs")

    assert "distinct on (sp2.target_id, sp2.contract_id)" in predicate
    assert "sp2.status = 'accepted'" in predicate
    assert "sp2.coverage_status = 'passed'" in predicate
    assert "sp2.updated_at desc" in predicate


def test_factor_patch_template_merges_generic_and_rule_options() -> None:
    catalog = tool.build_factor_option_catalog(factor_rows())
    item = tool.material_item(material_row(), catalog)
    template = item["factor_patch_template"]

    assert template["target_action"] == "review"
    assert template["side"] == "positive"
    assert template["factor_refs"]["authorization_intensity"] == {"label": ""}
    assert template["factor_option_candidates"]["authorization_intensity"][0]["label"] == "有明确授权"
    assert template["factor_option_candidates"]["source_factor"][0]["label"] == "基础史源"
    assert item["object"]["talent_grade"] == "historic_talent"
    assert item["claim"]["source_passages"][0]["source_title"] == "史记"


def test_build_worklist_groups_materials_and_suggests_batches() -> None:
    payload = tool.build_worklist_from_rows(
        [
            material_row(binding_code="BND-001"),
            material_row(binding_code="BND-002", emperor_name="朱元璋", target_code="TGT-I5B-ZYZ", direction="negative"),
        ],
        factor_rows(),
        item_code="I5B",
        rule_code="delegation",
        formula_code="evidence_cluster_signal_v3",
        scope="accepted-packs",
        batch_size=1,
    )

    assert payload["totals"]["materials"] == 2
    assert payload["totals"]["groups"] == 2
    assert payload["direction_counts"] == {"negative": 1, "positive": 1}
    assert [batch["material_count"] for batch in payload["suggested_batches"]] == [1, 1]


def test_filter_material_rows_restricts_by_target_name_or_code() -> None:
    rows = [
        material_row(binding_code="BND-001", emperor_name="刘邦", target_code="TGT-I5B-LB"),
        material_row(binding_code="BND-002", emperor_name="朱元璋", target_code="TGT-I5B-ZYZ"),
    ]

    by_name = tool.filter_material_rows(rows, target_names=["朱元璋"])
    by_code = tool.filter_material_rows(rows, target_codes=["TGT-I5B-LB"])

    assert [row["binding_code"] for row in by_name] == ["BND-002"]
    assert [row["binding_code"] for row in by_code] == ["BND-001"]


def test_patch_template_and_validation_require_complete_coverage() -> None:
    payload = tool.build_worklist_from_rows(
        [material_row()],
        factor_rows(),
        item_code="I5B",
        rule_code="delegation",
        formula_code="evidence_cluster_signal_v3",
        scope="accepted-packs",
        batch_size=40,
    )
    batch = payload["suggested_batches"][0]
    template_rows = tool.patch_template_rows(batch)

    assert template_rows == [
        {
            "binding_code": "BND-001",
            "target_action": "review",
            "side": "positive",
            "factor_refs": {
                "authorization_intensity": {"label": ""},
                "person_post_fit": {"label": ""},
                "result_feedback": {"label": ""},
                "attribution_factor": {"label": ""},
                "source_factor": {"label": ""},
                "context_factor": {"label": ""},
            },
            "patch_note": "",
        }
    ]

    patch_row = {
        "binding_code": "BND-001",
        "target_action": "score",
        "side": "positive",
        "factor_refs": {
            "authorization_intensity": {"label": "有明确授权"},
            "person_post_fit": {"label": "人岗高度匹配"},
            "result_feedback": {"label": "结果明确正向"},
            "attribution_factor": {"label": "可归因于皇帝授权"},
            "source_factor": {"label": "基础史源"},
            "context_factor": {"label": "语境清楚"},
        },
        "patch_note": "萧何材料直接说明后方委任与供给成效，可作为正向授权材料。",
    }

    report = tool.validate_patch(batch, [patch_row])

    assert report["ok"] is True
    assert report["action_counts"] == {"score": 1}


def test_validation_flags_unknown_labels_and_missing_rows() -> None:
    payload = tool.build_worklist_from_rows(
        [material_row(binding_code="BND-001"), material_row(binding_code="BND-002")],
        factor_rows(),
        item_code="I5B",
        rule_code="delegation",
        formula_code="evidence_cluster_signal_v3",
        scope="accepted-packs",
        batch_size=40,
    )
    batch = payload["suggested_batches"][0]
    patch_row = {
        "binding_code": "BND-001",
        "target_action": "score",
        "side": "positive",
        "factor_refs": {
            "authorization_intensity": {"label": "不存在的标签"},
            "person_post_fit": {"label": "人岗高度匹配"},
            "result_feedback": {"label": "结果明确正向"},
            "attribution_factor": {"label": "可归因于皇帝授权"},
            "source_factor": {"label": "基础史源"},
            "context_factor": {"label": "语境清楚"},
        },
        "patch_note": "萧何材料直接说明后方委任与供给成效，可作为正向授权材料。",
    }

    report = tool.validate_patch(batch, [patch_row])

    assert report["ok"] is False
    statuses = {issue["status"] for issue in report["issues"]}
    assert {"unknown_factor_label", "missing_patch_row"} <= statuses


def test_validation_rejects_delegation_side_result_feedback_sign_mismatch() -> None:
    payload = tool.build_worklist_from_rows(
        [material_row()],
        factor_rows(),
        item_code="I5B",
        rule_code="delegation",
        formula_code="evidence_cluster_signal_v3",
        scope="accepted-packs",
        batch_size=40,
    )
    batch = payload["suggested_batches"][0]
    patch_row = {
        "binding_code": "BND-001",
        "target_action": "score",
        "side": "positive",
        "factor_refs": {
            "authorization_intensity": {"label": "有明确授权"},
            "person_post_fit": {"label": "人岗高度匹配"},
            "result_feedback": {"label": "效果较差"},
            "attribution_factor": {"label": "可归因于皇帝授权"},
            "source_factor": {"label": "基础史源"},
            "context_factor": {"label": "语境清楚"},
        },
        "patch_note": "萧何材料是正向任用事实，不能在正向行里选择负值结果反馈。",
    }

    report = tool.validate_patch(batch, [patch_row])

    assert report["ok"] is False
    assert any(issue["status"] == "side_result_feedback_sign_mismatch" for issue in report["issues"])


def test_cli_writes_worklist_outputs(tmp_path: Path, monkeypatch) -> None:
    payload = tool.build_worklist_from_rows(
        [material_row()],
        factor_rows(),
        item_code="I5B",
        rule_code="delegation",
        formula_code="evidence_cluster_signal_v3",
        scope="accepted-packs",
        batch_size=40,
    )
    monkeypatch.setattr(tool, "build_worklist", lambda **_: payload)
    output_json = tmp_path / "worklist.json"
    output_md = tmp_path / "worklist.md"
    batch_dir = tmp_path / "batches"

    assert tool.main([
        "worklist",
        "--output-json",
        str(output_json),
        "--output-md",
        str(output_md),
        "--batch-output-dir",
        str(batch_dir),
    ]) == 0

    assert json.loads(output_json.read_text(encoding="utf-8"))["totals"]["materials"] == 1
    assert "retrieval_v2 factorization worklist" in output_md.read_text(encoding="utf-8")
    assert (batch_dir / "rv2_factor_batch_01.json").exists()


def test_cli_template_and_validate_patch(tmp_path: Path) -> None:
    payload = tool.build_worklist_from_rows(
        [material_row()],
        factor_rows(),
        item_code="I5B",
        rule_code="delegation",
        formula_code="evidence_cluster_signal_v3",
        scope="accepted-packs",
        batch_size=40,
    )
    batch_json = tmp_path / "batch.json"
    tool.write_json(batch_json, payload["suggested_batches"][0])
    patch_jsonl = tmp_path / "patch.jsonl"

    assert tool.main(["template", "--batch-json", str(batch_json), "--output-jsonl", str(patch_jsonl)]) == 0
    assert len(patch_jsonl.read_text(encoding="utf-8").splitlines()) == 1

    output_json = tmp_path / "validation.json"
    output_md = tmp_path / "validation.md"
    assert tool.main([
        "validate-patch",
        "--batch-json",
        str(batch_json),
        "--patch-jsonl",
        str(patch_jsonl),
        "--output-json",
        str(output_json),
        "--output-md",
        str(output_md),
    ]) == 0
    assert json.loads(output_json.read_text(encoding="utf-8"))["ok"] is False
    assert "retrieval_v2 factorization patch validation" in output_md.read_text(encoding="utf-8")


def test_build_codex_tasks_writes_slim_prompt_and_task_jsonl(tmp_path: Path) -> None:
    payload = tool.build_worklist_from_rows(
        [material_row()],
        factor_rows(),
        item_code="I5B",
        rule_code="delegation",
        formula_code="evidence_cluster_signal_v3",
        scope="accepted-packs",
        batch_size=40,
    )
    batch_path = tmp_path / "rv2_factor_batch_01.json"
    tool.write_json(batch_path, payload["suggested_batches"][0])

    summary = tool.write_task_outputs(batch_paths=[batch_path], output_root=tmp_path / "tasks")

    assert summary["totals"] == {"materials": 1, "tasks": 1}
    tasks = tool.read_jsonl(tmp_path / "tasks" / "factorization_tasks.jsonl")
    assert tasks[0]["task_kind"] == "retrieval_v2_factorization"
    assert "--dangerously-bypass-approvals-and-sandbox" in tasks[0]["argv"]
    assert (tmp_path / "tasks" / "patches").exists()
    assert (tmp_path / "tasks" / "logs").exists()
    prompt_text = (Path.cwd() / tasks[0]["prompt_path"]).read_text(encoding="utf-8")
    assert "factor_options_by_factor" in prompt_text
    assert "唯一允许写入的是指定 JSONL patch 文件" in prompt_text
    assert "$i5b-delegation-factorization" not in prompt_text
    assert "delegation 轻量校准" in prompt_text
    assert "包内 direction 就是本轮 side，不重新判断正负" in prompt_text
    assert "positive 行不得选择负值 `result_feedback`" in prompt_text
    assert "重新全量裁判正负" not in prompt_text
    assert "刘邦委任萧何镇守关中" in prompt_text


def test_recover_patches_from_last_message(tmp_path: Path) -> None:
    tasks_path = tmp_path / "tasks.jsonl"
    last_message_path = tmp_path / "logs" / "RV2F-1.last.md"
    patch_path = tmp_path / "patches" / "RV2F-1.jsonl"
    last_message_path.parent.mkdir(parents=True)
    last_message_path.write_text(
        "\n".join(
            [
                '{"binding_code":"BND-001","target_action":"score","side":"positive","factor_refs":{},"patch_note":"材料明确呈现授权与结果反馈，可作为委任因子化测试。"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    tool.write_jsonl(
        tasks_path,
        [
            {
                "task_code": "RV2F-1",
                "batch_id": "rv2_factor_batch_01",
                "material_count": 1,
                "patch_path": str(patch_path),
                "last_message_path": str(last_message_path),
                "log_path": str(tmp_path / "logs" / "RV2F-1.jsonl"),
            }
        ],
    )
    output_json = tmp_path / "recovery.json"
    output_md = tmp_path / "recovery.md"

    payload = tool.recover_task_patches(tasks_path=tasks_path, output_json=output_json, output_md=output_md)

    assert payload["ok"] is True
    assert payload["totals"] == {"complete": 1}
    assert json.loads(patch_path.read_text(encoding="utf-8").splitlines()[0])["binding_code"] == "BND-001"
    assert "retrieval_v2 factorization patch recovery" in output_md.read_text(encoding="utf-8")


def test_recover_patches_preserves_existing_complete_patch(tmp_path: Path) -> None:
    tasks_path = tmp_path / "tasks.jsonl"
    last_message_path = tmp_path / "logs" / "RV2F-1.last.md"
    patch_path = tmp_path / "patches" / "RV2F-1.jsonl"
    last_message_path.parent.mkdir(parents=True)
    complete_rows = [
        {"binding_code": "BND-001", "target_action": "score", "side": "positive", "factor_refs": {}, "patch_note": "既有完整补丁第一行。"},
        {"binding_code": "BND-002", "target_action": "score", "side": "positive", "factor_refs": {}, "patch_note": "既有完整补丁第二行。"},
    ]
    partial_rows = [
        {"binding_code": "BND-001", "target_action": "score", "side": "positive", "factor_refs": {}, "patch_note": "日志只恢复出一行。"}
    ]
    tool.write_jsonl(patch_path, complete_rows)
    last_message_path.write_text(json.dumps(partial_rows[0], ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    tool.write_jsonl(
        tasks_path,
        [
            {
                "task_code": "RV2F-1",
                "batch_id": "rv2_factor_batch_01",
                "material_count": 2,
                "patch_path": str(patch_path),
                "last_message_path": str(last_message_path),
                "log_path": str(tmp_path / "logs" / "RV2F-1.jsonl"),
            }
        ],
    )

    payload = tool.recover_task_patches(tasks_path=tasks_path, output_json=None, output_md=None)

    assert payload["ok"] is True
    assert payload["tasks"][0]["source_mode"] == "existing_preserved"
    assert payload["tasks"][0]["written"] is False
    assert [row["binding_code"] for row in tool.read_jsonl(patch_path)] == ["BND-001", "BND-002"]


def test_run_plan_dry_run_delegates_to_codex_win(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tasks_path = tmp_path / "tasks.jsonl"
    tool.write_jsonl(
        tasks_path,
        [
            {
                "task_code": "RV2F-1",
                "task_kind": "retrieval_v2_factorization",
                "prompt_path": "tmp/no-such-prompt.md",
                "patch_path": "tmp/no-such-patch.jsonl",
                "argv": ["codex", "exec", "-"],
            }
        ],
    )
    calls: list[list[str]] = []

    def fake_run(argv: list[str], **kwargs: object) -> object:
        calls.append(argv)

        class Completed:
            returncode = 0
            stdout = json.dumps({"tasks": [{"task_code": "RV2F-1", "status": "planned"}], "totals": {"planned": 1}}, ensure_ascii=False)
            stderr = ""

        return Completed()

    monkeypatch.setattr(tool.subprocess, "run", fake_run)

    payload = tool.run_codex_tasks(
        tasks_path=tasks_path,
        execute=False,
        background=False,
        limit=1,
        output=None,
        agent_output_root=tmp_path / "agent",
        codex_win_bin="codex-win-test",
        max_workers=2,
        timeout_seconds=60,
    )

    assert payload["totals"] == {"planned": 1}
    assert payload["runner"] == "codex-win agent run-plan"
    argv = calls[0]
    assert argv[:3] == ["codex-win-test", "agent", "run-plan"]
    assert "--dry-run" in argv
    assert argv[argv.index("--max-workers") + 1] == "2"
    assert argv[argv.index("--sandbox-profile") + 1] == "local-write"
