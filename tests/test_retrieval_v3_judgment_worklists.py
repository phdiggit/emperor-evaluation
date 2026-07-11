from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.dev import retrieval_v3_judgment_worklists as tool


def test_target_period_item_contains_patch_template() -> None:
    item = tool.target_period_item(
        {
            "target_id": 1,
            "target_code": "TGT-1",
            "emperor_name": "司马炎",
            "item_code": "I5B",
            "object_id": 10,
            "object_code": "OBJ-10",
            "role_title": "",
            "talent_grade_basis": "司马炎，当前评价项目标皇帝。",
        }
    )

    assert item["task_kind"] == "target_emperor_period"
    assert item["required_patch"]["dynasty_label"] == ""
    assert item["required_patch"]["emperor_name"] == "司马炎"
    assert "西晋" in item["context"]["allowed_dynasty_labels"]


def test_role_item_does_not_guess_from_failed_delegate() -> None:
    item = tool.role_item(
        {
            "object_id": 20,
            "object_code": "OBJ-20",
            "canonical_name": "王德用",
            "normalized_name": "王德用",
            "target_code": "TGT-SR",
            "emperor_name": "赵祯",
            "item_code": "I5B",
            "material_roles": ["revoked_or_failed_delegate"],
            "known_dynasties": ["北宋"],
        }
    )

    assert item["required_patch"]["role_kind"] == ""
    assert item["context"]["material_roles"] == ["revoked_or_failed_delegate"]
    assert "general" in item["context"]["allowed_role_kinds"]


def test_profile_basis_item_only_requests_intro_patch() -> None:
    item = tool.profile_basis_item(
        {
            "object_id": 30,
            "object_code": "OBJ-30",
            "canonical_name": "张良",
            "normalized_name": "张良",
            "talent_grade": "historic_talent",
            "talent_grade_basis": "",
            "target_emperors": ["刘邦"],
            "known_dynasties": ["西汉"],
            "role_kinds": ["minister"],
            "known_names": ["canonical:张良", "style:子房"],
        }
    )

    assert item["task_kind"] == "person_profile_basis"
    assert item["required_patch"] == {
        "task_kind": "person_profile_basis",
        "workitem_code": item["workitem_code"],
        "object_id": 30,
        "talent_grade_basis": "张良，",
    }
    assert item["context"]["current_talent_grade"] == "historic_talent"
    assert "style:子房" in item["context"]["known_names"]


def test_talent_item_uses_authority_consensus_v2_contract() -> None:
    item = tool.talent_item(
        {
            "object_id": 31,
            "canonical_name": "马周",
            "authority_evaluations": [{"source_titles": ["旧唐书"], "basis": "史臣称许其识度。"}],
            "evidence_claims": [{"claim_summary": "上疏论刺史县令选任。"}],
        }
    )

    assert item["context"]["rubric_version"] == "talent-grade-v3"
    assert item["context"]["authority_evaluations"]
    assert any("不能据此排除 top_talent" in rule for rule in item["context"]["grade_boundary_rules"])
    assert any("不得按朝代分配档位人数" in rule for rule in item["context"]["grade_boundary_rules"])
    assert any("三个独立重要战役" in rule for rule in item["context"]["grade_boundary_rules"])
    assert any("公认治世" in rule for rule in item["context"]["grade_boundary_rules"])
    assert any("独立成就簇" in rule for rule in item["context"]["grade_boundary_rules"])
    assert any("人才发现与组织使用" in rule for rule in item["context"]["grade_boundary_rules"])
    assert item["required_patch"]["achievement_clusters"] == []
    assert "时代塑造级" in item["context"]["rubric"]["historic_talent"]
    assert item["required_patch"]["talent_grade_confidence"] is None


def test_blind_talent_refresh_omits_previous_profile_basis() -> None:
    item = tool.talent_item(
        {
            "object_id": 32,
            "canonical_name": "长孙无忌",
            "talent_grade_basis": "长孙无忌，上一轮评价结论。",
            "authority_evaluations": [],
            "evidence_claims": [],
        },
        include_current_profile_basis=False,
    )

    assert "current_profile_basis" not in item["context"]
    assert item["required_patch"]["talent_authority_consensus"] == ""
    assert item["required_patch"]["authority_sources"] == []
    assert "材料不足" in tool.prompt_for_task(
        task={"task_kind": tool.PERSON_TALENT_KIND},
        workitems=[item],
        patch_path=Path("tmp/talent.jsonl"),
    )


def test_negative_talent_item_keeps_type_and_severity_separate() -> None:
    item = tool.negative_talent_item(
        {
            "object_id": 32,
            "canonical_name": "某臣",
            "authority_evaluations": [],
            "evidence_claims": [],
        }
    )

    assert item["context"]["rubric_version"] == "negative-talent-v1"
    assert "power_abuser" in item["context"]["allowed_negative_talent_classes"]
    assert item["required_patch"]["has_negative_talent_class"] is None
    assert item["required_patch"]["negative_talent_severity"] == ""


def test_negative_talent_worklist_covers_every_active_profile() -> None:
    class Cursor:
        def __init__(self) -> None:
            self.sql = ""
            self.params = ()

        def execute(self, sql: str, params: tuple[str, ...]) -> None:
            self.sql = sql
            self.params = params

        def fetchall(self) -> list[dict]:
            return []

    cur = Cursor()
    assert tool.fetch_pending_negative_talent(cur, item_code="I5B") == []
    assert "o.identity_status = 'active'" in cur.sql
    assert "join retrieval_v3.target_objects" not in cur.sql
    assert "pp.talent_grade is not null" not in cur.sql
    assert cur.params == (False, tool.NEGATIVE_TALENT_VERSION)

    tool.fetch_pending_negative_talent(cur, item_code="I5B", include_existing=True)
    assert cur.params == (True, tool.NEGATIVE_TALENT_VERSION)


def test_negative_prompt_distinguishes_actual_rebellion_from_accusation() -> None:
    prompt = tool.prompt_for_task(
        task={"task_code": "T", "task_kind": tool.PERSON_NEGATIVE_TALENT_KIND},
        workitems=[],
        patch_path=Path("tmp/negative.jsonl"),
    )

    assert "实际举兵反叛" in prompt
    assert "谋反指控、诬告、未证实嫌疑" in prompt


def test_v2_profile_value_validators_reject_invalid_values() -> None:
    assert tool.require_confidence("0.75", "confidence") == 0.75
    assert tool.require_choice("strong", tool.AUTHORITY_CONSENSUS_VALUES, "consensus") == "strong"
    with pytest.raises(tool.JudgmentWorklistError, match="unsupported confidence"):
        tool.require_confidence(1.1, "confidence")
    with pytest.raises(tool.JudgmentWorklistError, match="unsupported consensus"):
        tool.require_choice("unanimous", tool.AUTHORITY_CONSENSUS_VALUES, "consensus")


def test_authority_sources_require_durable_source_identity() -> None:
    rows = tool.require_authority_sources(
        [
            {
                "source_title": "旧唐书",
                "source_locator": "卷七十四 马周传 史臣曰",
                "source_url": "https://example.test/old-tang-74",
                "evaluation_summary": "史臣肯定马周识度与辅政能力。",
            }
        ]
    )

    assert rows[0]["source_title"] == "旧唐书"
    assert rows[0]["source_locator"].startswith("卷七十四")
    with pytest.raises(tool.JudgmentWorklistError, match="requires source_title"):
        tool.require_authority_sources([{"source_title": "旧唐书", "evaluation_summary": "缺定位。"}])


def test_authority_sources_accept_persisted_claim_reference() -> None:
    assert tool.require_authority_sources(["PCA-EXISTING"]) == [{"claim_key": "PCA-EXISTING"}]
    assert tool.require_authority_sources([{"claim_key": "PCA-EXISTING"}]) == [{"claim_key": "PCA-EXISTING"}]
    with pytest.raises(tool.JudgmentWorklistError, match="must start with PCA-"):
        tool.require_authority_sources([{"claim_key": "CLMK-WRONG-LANE"}])


class _RecordingCursor:
    def __init__(self) -> None:
        self.sql = ""
        self.params: tuple[object, ...] = ()

    def execute(self, sql: str, params: tuple[object, ...]) -> None:
        self.sql = sql
        self.params = params

    def fetchall(self) -> list[dict[str, object]]:
        return []


def test_fetch_missing_talent_includes_name_matched_claim_cache_and_refresh_flag() -> None:
    cursor = _RecordingCursor()

    assert tool.fetch_missing_talent(cursor, item_code="I5B", include_existing=True) == []

    assert "cc.object_name in (o.canonical_name, o.normalized_name)" in cursor.sql
    assert "cc.claim_key like 'CLMK-%%'" in cursor.sql
    assert cursor.params == ("I5B", "I5B", True, tool.TALENT_GRADE_VERSION)


def test_write_worklist_outputs_builds_codex_prompts(tmp_path: Path) -> None:
    workitems = [
        tool.target_period_item(
            {
                "target_id": 1,
                "target_code": "TGT-1",
                "emperor_name": "司马炎",
                "item_code": "I5B",
                "object_id": 10,
                "object_code": "OBJ-10",
            }
        ),
        tool.talent_item(
            {
                "object_id": 2,
                "object_code": "OBJ-2",
                "canonical_name": "傅友德",
                "normalized_name": "傅友德",
                "target_emperors": ["朱元璋"],
                "known_dynasties": ["明"],
                "role_kinds": ["general"],
            }
        ),
    ]

    summary = tool.write_worklist_outputs(output_root=tmp_path, workitems=workitems, batch_size=1)

    assert summary["totals"] == {"codex_tasks": 2, "workitems": 2}
    assert (tmp_path / "judgment_workitems.jsonl").exists()
    assert (tmp_path / "codex_tasks.jsonl").exists()
    tasks = [json.loads(line) for line in (tmp_path / "codex_tasks.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(tasks) == 2
    assert all(Path(task["prompt_path"]).name.endswith(".md") for task in tasks)
    assert "--ask-for-approval" not in tasks[0]["argv"]
    assert "--dangerously-bypass-approvals-and-sandbox" in tasks[0]["argv"]
    assert tasks[0]["argv"][-1] == "-"
    assert tasks[0]["expected_outputs"][0]["kind"] == "jsonl_patch"
    assert tasks[0]["expected_outputs"][0]["begin"] == "PATCH_JSONL_BEGIN"
    prompt_text = (Path.cwd() / tasks[0]["prompt_path"]).read_text(encoding="utf-8")
    assert "唯一允许写入的是指定 JSONL patch 文件" in prompt_text
    basis_prompt = tool.prompt_for_task(
        task={"task_kind": "person_profile_basis"},
        workitems=[tool.profile_basis_item({"object_id": 1, "canonical_name": "张良"})],
        patch_path=tmp_path / "basis.jsonl",
    )
    assert "不修改 talent_grade" in basis_prompt


def test_run_codex_tasks_dry_run_delegates_to_codex_win(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tasks = [
        {
            "task_code": "CJT-1",
            "task_kind": "target_emperor_period",
            "prompt_path": "tmp/no-such-prompt.md",
            "patch_path": "tmp/no-such-patch.jsonl",
            "log_path": "tmp/no-such-log.jsonl",
            "argv": ["codex", "exec", "-"],
        },
        {
            "task_code": "CJT-2",
            "task_kind": "person_profile_basis",
            "prompt_path": "tmp/no-such-prompt-2.md",
            "patch_path": "tmp/no-such-patch-2.jsonl",
            "log_path": "tmp/no-such-log-2.jsonl",
            "argv": ["codex", "exec", "-"],
        },
    ]
    tasks_path = tmp_path / "tasks.jsonl"
    tool.write_jsonl(tasks_path, tasks)
    calls: list[list[str]] = []

    def fake_run(argv: list[str], **kwargs: object) -> object:
        calls.append(argv)

        class Completed:
            returncode = 0
            stdout = json.dumps(
                {
                    "status": "planned",
                    "tasks": [{"task_code": "CJT-1", "status": "planned"}],
                    "totals": {"planned": 1},
                },
                ensure_ascii=False,
            )
            stderr = ""

        return Completed()

    monkeypatch.setattr(tool.subprocess, "run", fake_run)

    agent_root = tmp_path / "agent"
    payload = tool.run_codex_tasks(
        tasks_path=tasks_path,
        execute=False,
        background=False,
        limit=1,
        output=None,
        agent_output_root=agent_root,
        codex_win_bin="codex-win-test",
        max_workers=2,
        timeout_seconds=60,
    )

    assert payload["totals"] == {"planned": 1}
    assert payload["runner"] == "codex-win agent run-plan"
    assert payload["results"] == [{"task_code": "CJT-1", "status": "planned"}]
    assert calls
    argv = calls[0]
    assert argv[:3] == ["codex-win-test", "agent", "run-plan"]
    assert "--dry-run" in argv
    assert "--background" not in argv
    assert argv[argv.index("--max-workers") + 1] == "2"
    assert argv[argv.index("--timeout-seconds") + 1] == "60"
    assert argv[argv.index("--sandbox-profile") + 1] == "local-write"
    limited_rows = [
        json.loads(line)
        for line in (agent_root / "limited_tasks.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [row["task_code"] for row in limited_rows] == ["CJT-1"]


def test_apply_patch_rows_rejects_unknown_values() -> None:
    with pytest.raises(tool.JudgmentWorklistError, match="unsupported dynasty_label"):
        tool.require_period("Neo-Qing")
    with pytest.raises(tool.JudgmentWorklistError, match="unsupported role_kind"):
        tool.require_role("wizard")
    with pytest.raises(tool.JudgmentWorklistError, match="unsupported talent_grade"):
        tool.require_grade("巨佬")
