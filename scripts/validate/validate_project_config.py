from __future__ import annotations

import sys
import re
from pathlib import Path
from typing import Any

import yaml
from yaml.tokens import AliasToken, AnchorToken, DocumentStartToken, TagToken


ROOT = Path(__file__).resolve().parents[2]
PROJECT_CONFIG_PATH = ROOT / "data" / "configs" / "project_config.yml"
ALLOWED_TOP_LEVEL_KEYS = {
    "version",
    "timezone",
    "active_subitem",
    "default_person_group",
    "person_groups",
    "outputs",
    "tooling",
}
ALLOWED_TIMEZONES = {"Asia/Shanghai"}
ALLOWED_GROUP_KEYS = {"label", "persons", "persons_ref"}
PERSON_SOURCE_KEYS = {"persons", "persons_ref"}
ALLOWED_OUTPUT_KEYS = {
    "matrix",
    "review_entry",
    "subitem_details",
    "evidence_indexes",
}
ALLOWED_OUTPUT_DETAIL_KEYS = {"enabled", "person_group_override"}
ALLOWED_TOOLING_KEYS = {"agent_runtime", "source_excerpt_pool"}
ALLOWED_AGENT_RUNTIME_KEYS = {"defaults", "stages"}
ALLOWED_AGENT_DEFAULT_KEYS = {"model", "reasoning_effort", "max_workers", "timeout_seconds"}
ALLOWED_AGENT_STAGE_KEYS = ALLOWED_AGENT_DEFAULT_KEYS | {"batch_size", "shard_size"}
ALLOWED_REASONING_EFFORTS = {"low", "medium", "high"}
REQUIRED_AGENT_STAGES = {
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
    "v3_expected_event_reconciliation",
}
ALLOWED_SOURCE_EXCERPT_POOL_KEYS = {"cache", "default_workflow_code", "paths", "workflows"}
ALLOWED_SOURCE_EXCERPT_CACHE_KEYS = {"enabled", "backend", "directory", "dsn_env", "schema"}
ALLOWED_SOURCE_EXCERPT_PATH_KEYS = {
    "query_profile",
    "query_profile_shared_copy",
    "source_pack_root",
    "jobs_dir",
    "logs_dir",
    "handoff_root",
}
ALLOWED_SOURCE_EXCERPT_WORKFLOW_KEYS = {"adapter", "source_scope", "paths"}
ALLOWED_NAMED_EXTERNAL_PATH_KEYS = {"server", "windows"}
FORBIDDEN_KEYS = {
    "i5b",
    "subitems",
    "groups",
    "defaults",
    "trial_group",
    "expanded_group",
    "persons_from_group",
    "candidate_pool",
    "review_warning_rules",
    "candidate_type",
    "why_selected",
    "expected_rule_pressure",
    "required_evidence_focus",
    "adjacent_item_risk",
    "negative_scan_focus",
    "trigger_terms",
    "warning_message",
    "evidence_strength_scope",
    "polarity_scope",
    "path_template",
    "subitem",
    "note",
    "group_type",
}


def is_non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_non_empty_string_list(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(is_non_empty_string(item) for item in value)


def validate_yaml_surface(path: Path, raw_text: str) -> list[str]:
    errors: list[str] = []
    try:
        tokens = yaml.scan(raw_text)
        for token in tokens:
            line = token.start_mark.line + 1
            if isinstance(token, AnchorToken):
                errors.append(f"{path}: line {line}: YAML anchors are not allowed")
            elif isinstance(token, AliasToken):
                errors.append(f"{path}: line {line}: YAML aliases are not allowed")
            elif isinstance(token, TagToken):
                errors.append(f"{path}: line {line}: custom YAML tags are not allowed")
            elif isinstance(token, DocumentStartToken):
                errors.append(f"{path}: line {line}: explicit document markers are not allowed")
    except yaml.YAMLError as exc:
        errors.append(f"{path}: invalid YAML ({exc})")
    return errors


def validate_basic_subset(path: Path, value: object, label: str = "$") -> list[str]:
    errors: list[str] = []
    if value is None or isinstance(value, (str, int, float, bool)):
        return errors
    if isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(validate_basic_subset(path, item, f"{label}[{index}]"))
        return errors
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                errors.append(f"{path}: {label}: mapping keys must be strings")
                continue
            errors.extend(validate_basic_subset(path, item, f"{label}.{key}"))
        return errors
    errors.append(f"{path}: {label}: unsupported YAML value type {type(value).__name__}")
    return errors


def find_forbidden_keys(path: Path, value: object, label: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child_label = f"{label}.{key}" if label != "$" else str(key)
            allowed_agent_defaults = child_label == "tooling.agent_runtime.defaults"
            if isinstance(key, str) and key in FORBIDDEN_KEYS and not allowed_agent_defaults:
                errors.append(f"{path}: {child_label}: {key} is not allowed in project_config.yml")
            errors.extend(find_forbidden_keys(path, item, child_label))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(find_forbidden_keys(path, item, f"{label}[{index}]"))
    return errors


def validate_persons_ref(path: Path, persons_ref: str, label: str) -> list[str]:
    errors: list[str] = []
    ref_path = Path(persons_ref)
    allowed_root = Path("data") / "configs" / "lists"
    if ref_path.is_absolute() or ".." in ref_path.parts or not ref_path.as_posix().startswith(
        allowed_root.as_posix() + "/"
    ):
        errors.append(f"{path}: {label}.persons_ref must stay under data/configs/lists/")
        return errors
    if not (ROOT / ref_path).exists():
        errors.append(f"{path}: {label}.persons_ref target does not exist: {persons_ref}")
    return errors


def validate_group(path: Path, groups: dict[str, Any], group_key: str, row: object) -> list[str]:
    _ = groups
    label = f"person_groups.{group_key}"
    errors: list[str] = []
    if not isinstance(row, dict):
        return [f"{path}: {label} must be a mapping"]
    extra_keys = sorted(set(row) - ALLOWED_GROUP_KEYS)
    if extra_keys:
        errors.append(f"{path}: {label}: person_groups only allow label/persons/persons_ref")
        for key in extra_keys:
            errors.append(f"{path}: {label}.{key}: group field is not allowed")
    if not is_non_empty_string(row.get("label")):
        errors.append(f"{path}: {label}.label must be a non-empty string")

    source_keys = [key for key in PERSON_SOURCE_KEYS if key in row]
    if len(source_keys) != 1:
        errors.append(f"{path}: {label}: provide exactly one of persons or persons_ref")
        return errors

    if "persons" in row and not is_non_empty_string_list(row["persons"]):
        errors.append(f"{path}: {label}.persons must be a non-empty list of non-empty strings")
    if "persons_ref" in row:
        persons_ref = row["persons_ref"]
        if not is_non_empty_string(persons_ref):
            errors.append(f"{path}: {label}.persons_ref must be a non-empty string")
        else:
            errors.extend(validate_persons_ref(path, str(persons_ref), label))
    return errors


def validate_outputs(path: Path, outputs: object, groups: dict[str, Any]) -> list[str]:
    label = "outputs"
    errors: list[str] = []
    if not isinstance(outputs, dict):
        return [f"{path}: {label} must be a mapping"]
    extra_keys = sorted(set(outputs) - ALLOWED_OUTPUT_KEYS)
    for key in extra_keys:
        errors.append(f"{path}: {label}.{key}: outputs only allow known product output switches")
    for key in sorted(ALLOWED_OUTPUT_KEYS):
        if key not in outputs:
            errors.append(f"{path}: {label}.{key} must be declared")
            continue
        value = outputs[key]
        if isinstance(value, bool):
            continue
        if not isinstance(value, dict):
            errors.append(f"{path}: {label}.{key} must be a boolean or output switch mapping")
            continue
        errors.append(f"{path}: {label}.{key}: output switches no longer accept mapping values")
        extra_detail_keys = sorted(set(value) - ALLOWED_OUTPUT_DETAIL_KEYS)
        for detail_key in extra_detail_keys:
            errors.append(f"{path}: {label}.{key}.{detail_key}: output switch field is not allowed")
        if "enabled" in value and not isinstance(value["enabled"], bool):
            errors.append(f"{path}: {label}.{key}.enabled must be a boolean")
        override = value.get("person_group_override")
        if override is not None:
            if not is_non_empty_string(override):
                errors.append(f"{path}: {label}.{key}.person_group_override must be null or a non-empty group key")
            elif override not in groups:
                errors.append(f"{path}: {label}.{key}.person_group_override references missing group {override!r}")
    return errors


def validate_person_groups(path: Path, groups: object) -> list[str]:
    label = "person_groups"
    errors: list[str] = []
    if not isinstance(groups, dict) or not groups:
        return [f"{path}: {label} must be a non-empty mapping"]
    for group_key, row in groups.items():
        if not is_non_empty_string(group_key):
            errors.append(f"{path}: {label}: group keys must be non-empty strings")
            continue
        errors.extend(validate_group(path, groups, str(group_key), row))
    return errors


def validate_cache_directory(path: Path, directory: object, label: str) -> list[str]:
    if not is_non_empty_string(directory):
        return [f"{path}: {label} must be a non-empty string"]
    cache_path = Path(str(directory))
    if cache_path.is_absolute() or ".." in cache_path.parts:
        return [f"{path}: {label} must be a repo-relative path without '..'"]
    if not cache_path.as_posix().startswith(".cache/"):
        return [f"{path}: {label} must stay under .cache/"]
    return []


def path_has_parent_ref(value: str) -> bool:
    normalized = value.replace("\\", "/")
    return any(part == ".." for part in normalized.split("/"))


def validate_query_profile_path(path: Path, value: object, label: str) -> list[str]:
    if not is_non_empty_string(value):
        return [f"{path}: {label} must be a non-empty string"]
    profile_path = Path(str(value))
    allowed_root = Path("data") / "query_profile_batches"
    if profile_path.is_absolute() or path_has_parent_ref(str(value)) or not profile_path.as_posix().startswith(
        allowed_root.as_posix() + "/"
    ):
        return [f"{path}: {label} must stay under data/query_profile_batches/"]
    if not (ROOT / profile_path).exists():
        return [f"{path}: {label} target does not exist: {value}"]
    return []


def validate_named_external_paths(path: Path, value: object, label: str) -> list[str]:
    if not isinstance(value, dict) or not value:
        return [f"{path}: {label} must be a non-empty mapping"]
    errors: list[str] = []
    extra_keys = sorted(set(value) - ALLOWED_NAMED_EXTERNAL_PATH_KEYS)
    for key in extra_keys:
        errors.append(f"{path}: {label}.{key}: path target must be one of {sorted(ALLOWED_NAMED_EXTERNAL_PATH_KEYS)}")
    for key in sorted(set(value) & ALLOWED_NAMED_EXTERNAL_PATH_KEYS):
        path_value = value[key]
        if not is_non_empty_string(path_value):
            errors.append(f"{path}: {label}.{key} must be a non-empty string")
        elif path_has_parent_ref(str(path_value)):
            errors.append(f"{path}: {label}.{key} must not contain '..'")
    return errors


def validate_source_excerpt_paths(path: Path, paths: object, label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(paths, dict):
        return [f"{path}: {label} must be a mapping"]
    extra_path_keys = sorted(set(paths) - ALLOWED_SOURCE_EXCERPT_PATH_KEYS)
    for key in extra_path_keys:
        errors.append(f"{path}: {label}.{key}: paths field is not allowed")
    if "query_profile" in paths:
        errors.extend(validate_query_profile_path(path, paths["query_profile"], f"{label}.query_profile"))
    for key in ("query_profile_shared_copy", "source_pack_root", "jobs_dir", "logs_dir", "handoff_root"):
        if key in paths:
            errors.extend(validate_named_external_paths(path, paths[key], f"{label}.{key}"))
    return errors


def validate_pg_identifier(path: Path, value: object, label: str) -> list[str]:
    if not is_non_empty_string(value):
        return [f"{path}: {label} must be a non-empty string"]
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(value)):
        return [f"{path}: {label} must be a PostgreSQL identifier"]
    return []


def validate_positive_int(path: Path, value: object, label: str) -> list[str]:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return [f"{path}: {label} must be a positive integer"]
    return []


def validate_agent_runtime(path: Path, runtime: object) -> list[str]:
    label = "tooling.agent_runtime"
    if not isinstance(runtime, dict):
        return [f"{path}: {label} must be a mapping"]
    errors: list[str] = []
    for key in sorted(set(runtime) - ALLOWED_AGENT_RUNTIME_KEYS):
        errors.append(f"{path}: {label}.{key}: agent_runtime field is not allowed")
    defaults = runtime.get("defaults")
    if not isinstance(defaults, dict):
        errors.append(f"{path}: {label}.defaults must be a mapping")
    else:
        for key in sorted(set(defaults) - ALLOWED_AGENT_DEFAULT_KEYS):
            errors.append(f"{path}: {label}.defaults.{key}: default field is not allowed")
        if not is_non_empty_string(defaults.get("model")):
            errors.append(f"{path}: {label}.defaults.model must be a non-empty string")
        if defaults.get("reasoning_effort") not in ALLOWED_REASONING_EFFORTS:
            errors.append(f"{path}: {label}.defaults.reasoning_effort must be one of {sorted(ALLOWED_REASONING_EFFORTS)}")
        for key in ("max_workers", "timeout_seconds"):
            errors.extend(validate_positive_int(path, defaults.get(key), f"{label}.defaults.{key}"))
    stages = runtime.get("stages")
    if not isinstance(stages, dict):
        errors.append(f"{path}: {label}.stages must be a mapping")
        return errors
    missing = sorted(REQUIRED_AGENT_STAGES - set(stages))
    extra = sorted(set(stages) - REQUIRED_AGENT_STAGES)
    for stage in missing:
        errors.append(f"{path}: {label}.stages.{stage}: required agent stage is missing")
    for stage in extra:
        errors.append(f"{path}: {label}.stages.{stage}: unknown agent stage")
    for stage, row in stages.items():
        stage_label = f"{label}.stages.{stage}"
        if not isinstance(row, dict):
            errors.append(f"{path}: {stage_label} must be a mapping")
            continue
        for key in sorted(set(row) - ALLOWED_AGENT_STAGE_KEYS):
            errors.append(f"{path}: {stage_label}.{key}: stage field is not allowed")
        if "model" in row and not is_non_empty_string(row["model"]):
            errors.append(f"{path}: {stage_label}.model must be a non-empty string")
        if "reasoning_effort" in row and row["reasoning_effort"] not in ALLOWED_REASONING_EFFORTS:
            errors.append(f"{path}: {stage_label}.reasoning_effort must be one of {sorted(ALLOWED_REASONING_EFFORTS)}")
        for key in ("max_workers", "timeout_seconds", "batch_size", "shard_size"):
            if key in row:
                errors.extend(validate_positive_int(path, row[key], f"{stage_label}.{key}"))
    return errors


def validate_tooling(path: Path, tooling: object) -> list[str]:
    if tooling is None:
        return []
    label = "tooling"
    errors: list[str] = []
    if not isinstance(tooling, dict):
        return [f"{path}: {label} must be a mapping"]
    extra_keys = sorted(set(tooling) - ALLOWED_TOOLING_KEYS)
    for key in extra_keys:
        errors.append(f"{path}: {label}.{key}: tooling only allows known local tool sections")

    agent_runtime = tooling.get("agent_runtime")
    if agent_runtime is not None:
        errors.extend(validate_agent_runtime(path, agent_runtime))

    source_excerpt_pool = tooling.get("source_excerpt_pool")
    if source_excerpt_pool is None:
        return errors
    if not isinstance(source_excerpt_pool, dict):
        return [*errors, f"{path}: {label}.source_excerpt_pool must be a mapping"]
    extra_pool_keys = sorted(set(source_excerpt_pool) - ALLOWED_SOURCE_EXCERPT_POOL_KEYS)
    for key in extra_pool_keys:
        errors.append(f"{path}: {label}.source_excerpt_pool.{key}: source_excerpt_pool field is not allowed")
    if "default_workflow_code" in source_excerpt_pool and not is_non_empty_string(source_excerpt_pool["default_workflow_code"]):
        errors.append(f"{path}: {label}.source_excerpt_pool.default_workflow_code must be a non-empty string")

    paths = source_excerpt_pool.get("paths")
    if paths is not None:
        errors.extend(validate_source_excerpt_paths(path, paths, f"{label}.source_excerpt_pool.paths"))

    workflows = source_excerpt_pool.get("workflows")
    if workflows is not None:
        if not isinstance(workflows, dict):
            errors.append(f"{path}: {label}.source_excerpt_pool.workflows must be a mapping")
        else:
            for workflow_code, workflow_row in workflows.items():
                workflow_label = f"{label}.source_excerpt_pool.workflows.{workflow_code}"
                if not is_non_empty_string(workflow_code):
                    errors.append(f"{path}: {label}.source_excerpt_pool.workflows: workflow codes must be non-empty strings")
                    continue
                if not isinstance(workflow_row, dict):
                    errors.append(f"{path}: {workflow_label} must be a mapping")
                    continue
                extra_workflow_keys = sorted(set(workflow_row) - ALLOWED_SOURCE_EXCERPT_WORKFLOW_KEYS)
                for key in extra_workflow_keys:
                    errors.append(f"{path}: {workflow_label}.{key}: workflow field is not allowed")
                if "adapter" in workflow_row and not is_non_empty_string(workflow_row["adapter"]):
                    errors.append(f"{path}: {workflow_label}.adapter must be a non-empty string")
                if "source_scope" in workflow_row and not is_non_empty_string(workflow_row["source_scope"]):
                    errors.append(f"{path}: {workflow_label}.source_scope must be a non-empty string")
                if "paths" in workflow_row:
                    errors.extend(validate_source_excerpt_paths(path, workflow_row["paths"], f"{workflow_label}.paths"))

    cache = source_excerpt_pool.get("cache")
    if cache is None:
        return errors
    if not isinstance(cache, dict):
        return [*errors, f"{path}: {label}.source_excerpt_pool.cache must be a mapping"]
    extra_cache_keys = sorted(set(cache) - ALLOWED_SOURCE_EXCERPT_CACHE_KEYS)
    for key in extra_cache_keys:
        errors.append(f"{path}: {label}.source_excerpt_pool.cache.{key}: cache field is not allowed")
    if "enabled" in cache and not isinstance(cache["enabled"], bool):
        errors.append(f"{path}: {label}.source_excerpt_pool.cache.enabled must be a boolean")
    backend = cache.get("backend")
    if backend is not None and backend not in {"filesystem", "postgres"}:
        errors.append(f"{path}: {label}.source_excerpt_pool.cache.backend must be filesystem or postgres")
    if backend == "postgres" and "directory" in cache:
        errors.append(f"{path}: {label}.source_excerpt_pool.cache.directory is only allowed for filesystem backend")
    if "directory" in cache:
        errors.extend(validate_cache_directory(path, cache["directory"], f"{label}.source_excerpt_pool.cache.directory"))
    if "dsn_env" in cache and not is_non_empty_string(cache["dsn_env"]):
        errors.append(f"{path}: {label}.source_excerpt_pool.cache.dsn_env must be a non-empty string")
    if "schema" in cache:
        errors.extend(validate_pg_identifier(path, cache["schema"], f"{label}.source_excerpt_pool.cache.schema"))
    return errors


def validate_timezone(path: Path, value: object) -> list[str]:
    if not is_non_empty_string(value):
        return [f"{path}: timezone must be a non-empty IANA timezone string"]
    if value not in ALLOWED_TIMEZONES:
        return [f"{path}: timezone must be one of {sorted(ALLOWED_TIMEZONES)}"]
    return []


def validate(path: Path = PROJECT_CONFIG_PATH) -> list[str]:
    if not path.exists():
        return [f"{path}: file does not exist"]

    raw_text = path.read_text(encoding="utf-8")
    errors = validate_yaml_surface(path, raw_text)
    if any("invalid YAML" in error for error in errors):
        return errors
    try:
        payload = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        return [*errors, f"{path}: invalid YAML ({exc})"]

    if not isinstance(payload, dict):
        return [*errors, f"{path}: top-level value must be a mapping"]
    errors.extend(validate_basic_subset(path, payload))
    errors.extend(find_forbidden_keys(path, payload))

    extra_top_level = sorted(set(payload) - ALLOWED_TOP_LEVEL_KEYS)
    for key in extra_top_level:
        errors.append(
            f"{path}: {key}: top-level config only allows "
            "version/timezone/active_subitem/default_person_group/person_groups/outputs/tooling"
        )
    if payload.get("version") != 2:
        errors.append(f"{path}: version must be 2")
    errors.extend(validate_timezone(path, payload.get("timezone")))
    active_subitem = payload.get("active_subitem")
    if not is_non_empty_string(active_subitem):
        errors.append(f"{path}: active_subitem must be a non-empty string")

    groups = payload.get("person_groups")
    errors.extend(validate_person_groups(path, groups))
    if isinstance(groups, dict):
        default_person_group = payload.get("default_person_group")
        if not is_non_empty_string(default_person_group):
            errors.append(f"{path}: default_person_group must be a non-empty group key")
        elif default_person_group not in groups:
            errors.append(f"{path}: default_person_group references missing group {default_person_group!r}")
        errors.extend(validate_outputs(path, payload.get("outputs"), groups))
    else:
        errors.append(f"{path}: outputs cannot be validated without person_groups")
    errors.extend(validate_tooling(path, payload.get("tooling")))
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(error)
        return 1

    print("Project config validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
