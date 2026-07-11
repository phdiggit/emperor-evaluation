from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


ROOT = Path(__file__).resolve().parents[2]
PROJECT_CONFIG_PATH = ROOT / "data" / "configs" / "project_config.yml"

AGENT_STAGES = (
    "retrieval_taskgen",
    "retrieval_judge",
    "alias_refiner",
    "object_source_hint_review",
    "claim_extraction",
    "claim_passage_repair",
    "material_review",
    "identity_judgment",
    "factorization",
    "v3_candidate_review",
    "v3_context_review",
    "v3_unseeded_actor_review",
    "v3_negative_chain_review",
    "v3_expected_event_inventory",
)
MODEL_ENV = "EMPEROR_EVAL_AGENT_MODEL"
REASONING_EFFORT_ENV = "EMPEROR_EVAL_AGENT_REASONING_EFFORT"
LEGACY_MODEL_ENV = "RETRIEVAL_V2_CODEX_MODEL"
LEGACY_REASONING_EFFORT_ENV = "RETRIEVAL_V2_CODEX_REASONING_EFFORT"


class AgentRuntimeConfigError(ValueError):
    pass


def text(value: Any) -> str:
    return str(value or "").strip()


def stage_env_name(stage: str, field: str) -> str:
    return f"EMPEROR_EVAL_AGENT_{stage}_{field}".upper()


def load_agent_runtime_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or PROJECT_CONFIG_PATH
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise AgentRuntimeConfigError(f"{config_path}: project config must be a mapping")
    tooling = payload.get("tooling")
    if not isinstance(tooling, Mapping):
        raise AgentRuntimeConfigError(f"{config_path}: tooling must be a mapping")
    runtime = tooling.get("agent_runtime")
    if not isinstance(runtime, Mapping):
        raise AgentRuntimeConfigError(f"{config_path}: tooling.agent_runtime must be a mapping")
    defaults = runtime.get("defaults")
    stages = runtime.get("stages")
    if not isinstance(defaults, Mapping) or not isinstance(stages, Mapping):
        raise AgentRuntimeConfigError(f"{config_path}: agent_runtime defaults/stages must be mappings")
    return {"defaults": dict(defaults), "stages": {str(key): dict(value) for key, value in stages.items() if isinstance(value, Mapping)}}


def _positive_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool):
        raise AgentRuntimeConfigError(f"{label} must be a positive integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise AgentRuntimeConfigError(f"{label} must be a positive integer") from exc
    if parsed <= 0:
        raise AgentRuntimeConfigError(f"{label} must be a positive integer")
    return parsed


def resolve_agent_stage(
    stage: str,
    *,
    config_path: Path | None = None,
    environ: Mapping[str, str] | None = None,
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> dict[str, Any]:
    if stage not in AGENT_STAGES:
        raise AgentRuntimeConfigError(f"unsupported agent stage: {stage}")
    config = load_agent_runtime_config(config_path)
    stage_config = config["stages"].get(stage)
    if not isinstance(stage_config, Mapping):
        raise AgentRuntimeConfigError(f"agent stage is missing from project config: {stage}")
    resolved = {**config["defaults"], **dict(stage_config), "stage": stage}
    env = environ if environ is not None else os.environ
    resolved_model = (
        text(model)
        or text(env.get(stage_env_name(stage, "MODEL")))
        or text(env.get(MODEL_ENV))
        or text(env.get(LEGACY_MODEL_ENV))
        or text(resolved.get("model"))
    )
    resolved_effort = (
        text(reasoning_effort)
        or text(env.get(stage_env_name(stage, "REASONING_EFFORT")))
        or text(env.get(REASONING_EFFORT_ENV))
        or text(env.get(LEGACY_REASONING_EFFORT_ENV))
        or text(resolved.get("reasoning_effort"))
    )
    if not resolved_model or not resolved_effort:
        raise AgentRuntimeConfigError(f"agent stage {stage} must resolve model and reasoning_effort")
    resolved["model"] = resolved_model
    resolved["reasoning_effort"] = resolved_effort
    for field in ("max_workers", "timeout_seconds", "batch_size", "shard_size"):
        env_value = text(env.get(stage_env_name(stage, field)))
        if env_value:
            resolved[field] = _positive_int(env_value, label=f"{stage}.{field}")
        elif field in resolved:
            resolved[field] = _positive_int(resolved[field], label=f"{stage}.{field}")
    return resolved


def codex_task_argv(
    stage: str,
    *,
    codex_bin: str = "codex",
    config_path: Path | None = None,
    exec_args: Sequence[str] | None = None,
) -> list[str]:
    runtime = resolve_agent_stage(stage, config_path=config_path)
    return [
        codex_bin,
        "-m",
        runtime["model"],
        "-c",
        f'model_reasoning_effort="{runtime["reasoning_effort"]}"',
        "exec",
        *(list(exec_args) if exec_args is not None else ["-"]),
    ]
