from __future__ import annotations

from pathlib import Path

import pytest

from scripts.dev import retrieval_v3_post_claim_orchestrator as tool


def succeeded_payload() -> dict:
    return {
        "status": "succeeded",
        "job": {"job_code": "CLAIM-LSM-1", "emperor_name": "李世民"},
        "result": {"claim_count": 12},
    }


def test_success_plan_rebuilds_event_groups_before_discovery(tmp_path: Path) -> None:
    plan = tool.build_post_claim_plan(succeeded_payload(), output_root=tmp_path)
    assert [row["stage"] for row in plan["commands"]] == [
        "semantic_identity",
        "event_group_target",
        "related_object_discovery",
    ]
    event_argv = plan["commands"][1]["argv"]
    assert "--execute" in event_argv
    assert "--replace-existing" in event_argv
    discovery_argv = plan["commands"][2]["argv"]
    assert discovery_argv[discovery_argv.index("--emperor") + 1] == "李世民"
    assert plan["identity_gate"]["automatic_canonical_person_creation"] is False


def test_non_success_claim_job_is_skipped(tmp_path: Path) -> None:
    plan = tool.build_post_claim_plan({"status": "idle"}, output_root=tmp_path)
    assert plan == {"status": "skipped", "reason": "claim_job_not_succeeded", "commands": []}


def test_succeeded_job_requires_emperor(tmp_path: Path) -> None:
    with pytest.raises(tool.PostClaimOrchestratorError, match="missing emperor_name"):
        tool.build_post_claim_plan({"status": "succeeded", "job": {}, "result": {}}, output_root=tmp_path)


def test_execute_plan_provides_release_root_pythonpath(monkeypatch, tmp_path: Path) -> None:
    seen = {}

    def fake_run(argv, **kwargs):
        seen["env"] = kwargs["env"]
        return type("Done", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(tool.subprocess, "run", fake_run)
    result = tool.execute_plan(
        {"status": "ready", "output_root": str(tmp_path), "commands": [{"stage": "x", "argv": ["python", "x.py"]}]}
    )

    assert result["status"] == "succeeded"
    assert str(tool.ROOT) in seen["env"]["PYTHONPATH"]
