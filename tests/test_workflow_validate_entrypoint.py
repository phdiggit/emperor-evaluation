from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "validate.yml"


def test_validate_workflow_installs_repo_requirements_before_unified_entrypoint() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["validate"]["steps"]
    step_names = [step["name"] for step in steps]

    dependency_step = steps[step_names.index("Install validation dependencies")]
    validate_step_index = step_names.index("Run unified validation entrypoint")
    focused_step_index = step_names.index("Run focused validation tests")

    assert step_names.index("Install validation dependencies") < validate_step_index
    assert validate_step_index < focused_step_index
    assert "python -m pip install --upgrade pip" in dependency_step["run"]
    assert "python -m pip install -r requirements.txt pytest" in dependency_step["run"]


def test_validate_workflow_keeps_focused_tests_after_unified_validation() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["validate"]["steps"]
    focused_step = next(step for step in steps if step["name"] == "Run focused validation tests")

    assert "tests/test_validate_all.py tests/test_scripts_directory_layout.py" in focused_step["run"]
    assert "always()" not in focused_step["run"]


def test_workflow_root_cause_is_locked_to_missing_runtime_dependencies() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "Install pytest" not in text
    assert "requirements.txt" in text
    assert "Run unified validation entrypoint" in text
    assert "Run focused validation tests" in text
