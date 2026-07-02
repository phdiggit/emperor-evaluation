from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from subprocess import CompletedProcess


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

VALIDATE_ALL_SPEC = importlib.util.spec_from_file_location(
    "validate.validate_all",
    ROOT / "scripts" / "validate" / "validate_all.py",
)
assert VALIDATE_ALL_SPEC is not None
validate_all = importlib.util.module_from_spec(VALIDATE_ALL_SPEC)
sys.modules[VALIDATE_ALL_SPEC.name] = validate_all
assert VALIDATE_ALL_SPEC.loader is not None
VALIDATE_ALL_SPEC.loader.exec_module(validate_all)

def test_validate_all_root_still_points_to_repo_root() -> None:
    assert validate_all.ROOT.resolve() == ROOT.resolve()


def test_retired_validate_all_wrapper_path_is_absent() -> None:
    assert not (ROOT / "scripts" / "validate_all.py").exists()


def test_validate_all_cli_passes_on_repo_data() -> None:
    result = validate_all.subprocess.run(
        [validate_all.sys.executable, str(ROOT / "scripts" / "validate" / "validate_all.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "[validate_all] all validation steps passed" in result.stdout


def test_validate_all_runs_steps_in_order(monkeypatch) -> None:
    called: list[tuple[str, Path]] = []

    def fake_run_step(name: str, script_path: Path) -> CompletedProcess[str]:
        called.append((name, script_path))
        return CompletedProcess(args=[name], returncode=0, stdout=f"{name} ok\n", stderr="")

    monkeypatch.setattr(validate_all, "run_step", fake_run_step)

    result = validate_all.main()

    assert result == 0
    assert called == validate_all.VALIDATION_STEPS


def test_validate_all_includes_config_readability_step() -> None:
    assert (
        "validate_config_readability",
        ROOT / "scripts" / "validate" / "validate_config_readability.py",
    ) in validate_all.VALIDATION_STEPS


def test_validate_all_includes_project_config_step() -> None:
    assert (
        "validate_project_config",
        ROOT / "scripts" / "validate" / "validate_project_config.py",
    ) in validate_all.VALIDATION_STEPS


def test_validate_all_includes_chinese_view_config_step() -> None:
    assert (
        "validate_chinese_view_configs",
        ROOT / "scripts" / "validate" / "validate_chinese_view_configs.py",
    ) in validate_all.VALIDATION_STEPS


def test_validate_all_includes_review_config_step() -> None:
    assert (
        "validate_review_configs",
        ROOT / "scripts" / "validate" / "validate_review_configs.py",
    ) in validate_all.VALIDATION_STEPS


def test_validate_all_includes_i5b_cluster_adjudication_config_step() -> None:
    assert (
        "validate_i5b_cluster_adjudication_configs",
        ROOT / "scripts" / "validate" / "validate_i5b_cluster_adjudication_configs.py",
    ) in validate_all.VALIDATION_STEPS


def test_validate_all_excludes_script_lifecycle_registry_step() -> None:
    step_names = {name for name, _path in validate_all.VALIDATION_STEPS}

    assert "validate_script_lifecycle_registry" not in step_names


def test_validate_all_excludes_retired_source_review_jsonl_steps() -> None:
    step_names = {name for name, _path in validate_all.VALIDATION_STEPS}

    assert "validate_evidence" not in step_names
    assert "validate_canonical_data_integrity" not in step_names
    assert "validate_source_evidence_canonical_stores" not in step_names


def test_validate_all_stops_after_first_failure(monkeypatch) -> None:
    called: list[str] = []

    def fake_run_step(name: str, script_path: Path) -> CompletedProcess[str]:
        called.append(name)
        if name == "validate_project_config":
            return CompletedProcess(args=[name], returncode=1, stdout="", stderr="failed\n")
        return CompletedProcess(args=[name], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(validate_all, "run_step", fake_run_step)

    result = validate_all.main()

    assert result == 1
    assert called == ["validate_project_config"]
