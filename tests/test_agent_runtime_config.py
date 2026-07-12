from __future__ import annotations

from scripts.shared import agent_runtime_config as tool


def test_repo_agent_runtime_lists_every_known_stage() -> None:
    config = tool.load_agent_runtime_config()

    assert set(config["stages"]) == set(tool.AGENT_STAGES)
    assert config["defaults"]["model"] == "gpt-5.6-luna"
    assert config["stages"]["claim_extraction"]["shard_size"] == 1


def test_stage_resolution_uses_project_defaults_and_stage_concurrency() -> None:
    runtime = tool.resolve_agent_stage("claim_extraction", environ={})

    assert runtime["model"] == "gpt-5.6-luna"
    assert runtime["reasoning_effort"] == "medium"
    assert runtime["max_workers"] == 4
    assert runtime["shard_size"] == 1
    assert runtime["timeout_seconds"] == 1800


def test_review_and_factorization_defaults_use_high_throughput_batches() -> None:
    factorization = tool.resolve_agent_stage("factorization", environ={})
    candidate_review = tool.resolve_agent_stage("v3_candidate_review", environ={})

    assert (factorization["batch_size"], factorization["max_workers"]) == (16, 8)
    assert (candidate_review["batch_size"], candidate_review["max_workers"]) == (16, 8)


def test_stage_specific_environment_has_highest_runtime_precedence() -> None:
    runtime = tool.resolve_agent_stage(
        "claim_extraction",
        environ={
            "EMPEROR_EVAL_AGENT_MODEL": "generic-model",
            "EMPEROR_EVAL_AGENT_CLAIM_EXTRACTION_MODEL": "stage-model",
            "EMPEROR_EVAL_AGENT_CLAIM_EXTRACTION_MAX_WORKERS": "7",
        },
    )

    assert runtime["model"] == "stage-model"
    assert runtime["max_workers"] == 7


def test_codex_task_argv_is_built_from_project_config() -> None:
    argv = tool.codex_task_argv("v3_candidate_review")

    assert argv == [
        "codex",
        "-m",
        "gpt-5.6-luna",
        "-c",
        'model_reasoning_effort="medium"',
        "exec",
        "-",
    ]
