from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping, Sequence


SCHEMA_CONTRACT_VERSION = "codex-structured-output-contract-v1"
_FORBIDDEN_SCHEMA_KEYWORDS = {"uniqueItems"}
_IGNORED_TASK_FIELDS = {"output_schema_path"}
_TOOL_FREE_PROMPT_MARKERS = (
    "EXECUTION_MODE: STRUCTURED_OUTPUT_NO_TOOLS",
    "TOOLS: FORBIDDEN",
    "REPOSITORY_READ: FORBIDDEN",
    "OUTPUT: JSON_ONLY",
)


def _type_names(value: object) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return set(value)
    return set()


def _value_matches_types(value: object, types: set[str]) -> bool:
    if value is None:
        return "null" in types
    if isinstance(value, bool):
        return "boolean" in types
    if isinstance(value, int):
        return "integer" in types or "number" in types
    if isinstance(value, float):
        return "number" in types
    if isinstance(value, str):
        return "string" in types
    if isinstance(value, list):
        return "array" in types
    if isinstance(value, Mapping):
        return "object" in types
    return False


def validate_codex_output_schema(
    schema: Mapping[str, object],
    *,
    require_all_properties: bool = True,
) -> dict[str, object]:
    """Validate the strict schema subset before any billable model call."""

    errors: list[str] = []

    def walk(node: object, path: str) -> None:
        if not isinstance(node, Mapping):
            errors.append(f"{path}: schema node 必须是 object")
            return
        forbidden = sorted(_FORBIDDEN_SCHEMA_KEYWORDS & set(node))
        if forbidden:
            errors.append(f"{path}: 不支持字段 {', '.join(forbidden)}")

        types = _type_names(node.get("type"))
        if not types:
            errors.append(f"{path}: 缺少显式 type")
        if "properties" in node:
            if "object" not in types:
                errors.append(f"{path}: properties 要求 type=object")
            properties = node.get("properties")
            if not isinstance(properties, Mapping):
                errors.append(f"{path}.properties: 必须是 object")
            else:
                required = node.get("required")
                if not isinstance(required, list) or not all(
                    isinstance(item, str) for item in required
                ):
                    errors.append(f"{path}.required: 必须显式列出字段")
                    required_names: set[str] = set()
                else:
                    required_names = set(required)
                    if len(required_names) != len(required):
                        errors.append(f"{path}.required: 不得重复")
                property_names = set(str(item) for item in properties)
                unknown_required = required_names - property_names
                if unknown_required:
                    errors.append(
                        f"{path}.required: 未定义字段 {sorted(unknown_required)}"
                    )
                if require_all_properties and required_names != property_names:
                    missing = sorted(property_names - required_names)
                    errors.append(
                        f"{path}.required: 严格合同缺少 {missing}; "
                        "可空字段也必须 required，并用 null 表示"
                    )
                if node.get("additionalProperties") is not False:
                    errors.append(f"{path}: additionalProperties 必须为 false")
                for name, child in properties.items():
                    walk(child, f"{path}.properties.{name}")
        if "items" in node:
            if "array" not in types:
                errors.append(f"{path}: items 要求 type=array")
            walk(node.get("items"), f"{path}.items")
        if "array" in types and "items" not in node:
            errors.append(f"{path}: array 必须显式定义 items")

        if "const" in node and not _value_matches_types(node["const"], types):
            errors.append(f"{path}.const: 值与 type 不一致")
        enum = node.get("enum")
        if enum is not None:
            if not isinstance(enum, list) or not enum:
                errors.append(f"{path}.enum: 必须是非空数组")
            elif any(not _value_matches_types(item, types) for item in enum):
                errors.append(f"{path}.enum: 存在与 type 不一致的值")

    walk(schema, "$")
    if errors:
        raise ValueError("结构化输出 Schema 预检失败:\n- " + "\n- ".join(errors))
    serialized = json.dumps(
        schema,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "contract_version": SCHEMA_CONTRACT_VERSION,
        "schema_sha256": sha256(serialized).hexdigest(),
        "strict_required_properties": require_all_properties,
    }


def validate_codex_task_plan(
    tasks: Sequence[Mapping[str, object]],
    *,
    output_schema_path: Path,
    require_tool_free_prompt: bool = True,
) -> dict[str, object]:
    """Validate effective argv and prompt isolation before run-plan."""

    expected_schema = output_schema_path.resolve()
    if not expected_schema.is_file():
        raise ValueError("任务计划引用的 output schema 不存在")
    errors: list[str] = []
    task_codes: set[str] = set()
    for index, task in enumerate(tasks, start=1):
        label = str(task.get("task_code") or f"row-{index}")
        if not task.get("task_code") or label in task_codes:
            errors.append(f"{label}: task_code 缺失或重复")
        task_codes.add(label)
        ignored = sorted(_IGNORED_TASK_FIELDS & set(task))
        if ignored:
            errors.append(f"{label}: 禁止静默字段 {', '.join(ignored)}")
        argv = task.get("argv")
        if not isinstance(argv, list) or not all(isinstance(x, str) for x in argv):
            errors.append(f"{label}: argv 必须是字符串数组")
            continue
        if "exec" not in argv or argv[-1:] != ["-"]:
            errors.append(f"{label}: argv 必须使用 codex exec 并从 stdin 读取")
        positions = [i for i, item in enumerate(argv) if item == "--output-schema"]
        if len(positions) != 1 or positions[0] + 1 >= len(argv):
            errors.append(f"{label}: 必须且只能传递一次 --output-schema")
        else:
            actual = Path(argv[positions[0] + 1]).resolve()
            if actual != expected_schema:
                errors.append(f"{label}: --output-schema 与预检 schema 不一致")

        prompt_path = Path(str(task.get("prompt_path") or ""))
        if not prompt_path.is_file():
            errors.append(f"{label}: prompt_path 不存在")
        elif require_tool_free_prompt:
            prompt = prompt_path.read_text(encoding="utf-8")
            missing = [item for item in _TOOL_FREE_PROMPT_MARKERS if item not in prompt]
            if missing:
                errors.append(f"{label}: 缺少无工具执行标记 {missing}")
    if errors:
        raise ValueError("Codex 任务计划预检失败:\n- " + "\n- ".join(errors))
    return {
        "contract_version": SCHEMA_CONTRACT_VERSION,
        "task_count": len(tasks),
        "task_codes": sorted(task_codes),
        "output_schema_path": str(expected_schema),
        "requires_respect_task_argv": True,
        "execution_mode": "structured_output_no_tools",
    }


def validate_payload_against_schema(
    payload: object,
    schema: Mapping[str, object],
) -> None:
    """Validate the deterministic subset used by repository output schemas."""

    errors: list[str] = []

    def walk(value: object, node: Mapping[str, object], path: str) -> None:
        types = _type_names(node.get("type"))
        if not _value_matches_types(value, types):
            errors.append(f"{path}: 值不符合 type {sorted(types)}")
            return
        if "const" in node and value != node["const"]:
            errors.append(f"{path}: 值不符合 const")
        if "enum" in node and value not in node["enum"]:
            errors.append(f"{path}: 值不在 enum")
        if isinstance(value, str) and len(value) < int(node.get("minLength", 0)):
            errors.append(f"{path}: 字符串短于 minLength")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in node and value < node["minimum"]:
                errors.append(f"{path}: 数值小于 minimum")
        if isinstance(value, list):
            if len(value) < int(node.get("minItems", 0)):
                errors.append(f"{path}: 数组短于 minItems")
            if "maxItems" in node and len(value) > int(node["maxItems"]):
                errors.append(f"{path}: 数组长于 maxItems")
            item_schema = node.get("items")
            if isinstance(item_schema, Mapping):
                for index, item in enumerate(value):
                    walk(item, item_schema, f"{path}[{index}]")
        if isinstance(value, Mapping):
            properties = node.get("properties")
            if not isinstance(properties, Mapping):
                return
            required = set(node.get("required") or ())
            missing = required - set(value)
            if missing:
                errors.append(f"{path}: 缺少 required {sorted(missing)}")
            if node.get("additionalProperties") is False:
                extra = set(value) - set(properties)
                if extra:
                    errors.append(f"{path}: 存在额外字段 {sorted(extra)}")
            for name, child_schema in properties.items():
                if name in value and isinstance(child_schema, Mapping):
                    walk(value[name], child_schema, f"{path}.{name}")

    walk(payload, schema, "$")
    if errors:
        raise ValueError("结构化输出结果验收失败:\n- " + "\n- ".join(errors))


def build_canary_acceptance_report(
    *,
    schema_path: Path,
    status_path: Path,
    event_log_path: Path,
    result_path: Path,
    task_code: str,
    max_input_tokens: int,
    max_output_tokens: int,
) -> dict[str, object]:
    """Accept one canary only after command, events, usage and payload close."""

    if max_input_tokens <= 0 or max_output_tokens <= 0:
        raise ValueError("canary token 上限必须为正数")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    status = json.loads(status_path.read_text(encoding="utf-8"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    tasks = status.get("tasks") or ()
    matching = [task for task in tasks if task.get("task_code") == task_code]
    if len(matching) != 1:
        raise ValueError("canary status 未唯一覆盖 task_code")
    task = matching[0]
    command_info = task.get("command_info") or {}
    if (
        status.get("status") != "succeeded"
        or task.get("status") != "succeeded"
        or task.get("returncode") != 0
    ):
        raise ValueError("canary 进程未成功")
    if command_info.get("respect_task_argv") is not True:
        raise ValueError("canary 未实际启用 respect_task_argv")

    input_tokens = None
    output_tokens = None
    tool_events: list[str] = []
    for line_number, line in enumerate(
        event_log_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("type") == "item.completed":
            item_type = str((event.get("item") or {}).get("type") or "")
            if item_type not in {"agent_message", "reasoning"}:
                tool_events.append(f"line={line_number},type={item_type}")
        if event.get("type") == "turn.completed":
            usage = event.get("usage") or {}
            input_tokens = usage.get("input_tokens")
            output_tokens = usage.get("output_tokens")
    if tool_events:
        raise ValueError(f"canary 出现工具或非输出事件: {tool_events}")
    if not isinstance(input_tokens, int) or not isinstance(output_tokens, int):
        raise ValueError("canary 缺少 token usage")
    if input_tokens > max_input_tokens or output_tokens > max_output_tokens:
        raise ValueError(
            "canary token 超限: "
            f"input={input_tokens}/{max_input_tokens}, "
            f"output={output_tokens}/{max_output_tokens}"
        )
    validate_payload_against_schema(result, schema)
    return {
        "contract_version": SCHEMA_CONTRACT_VERSION,
        "status": "ready_for_batch_fanout",
        "task_code": task_code,
        "duration_sec": task.get("duration_sec"),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "tool_event_count": 0,
        "payload_schema_valid": True,
    }


def _load_jsonl(path: Path) -> list[Mapping[str, object]]:
    rows: list[Mapping[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, Mapping):
            raise ValueError(f"{path}:{line_number}: task 必须是 object")
        rows.append(row)
    if not rows:
        raise ValueError("任务计划不得为空")
    return rows


def build_preflight_report(
    *,
    schema_path: Path,
    tasks_path: Path | None = None,
    require_all_properties: bool = True,
    require_tool_free_prompt: bool = True,
) -> dict[str, object]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if not isinstance(schema, Mapping):
        raise ValueError("output schema 必须是 JSON object")
    schema_report = validate_codex_output_schema(
        schema,
        require_all_properties=require_all_properties,
    )
    task_report = None
    if tasks_path is not None:
        task_report = validate_codex_task_plan(
            _load_jsonl(tasks_path),
            output_schema_path=schema_path,
            require_tool_free_prompt=require_tool_free_prompt,
        )
    return {
        "contract_version": SCHEMA_CONTRACT_VERSION,
        "status": "ready_for_single_canary",
        "schema": schema_report,
        "tasks": task_report,
        "model_calls": 0,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="模型结构化输出合同的零调用预检")
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--tasks-jsonl", type=Path)
    parser.add_argument("--allow-optional-properties", action="store_true")
    parser.add_argument("--allow-agent-tools", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--canary-status", type=Path)
    parser.add_argument("--canary-events", type=Path)
    parser.add_argument("--canary-result", type=Path)
    parser.add_argument("--canary-task-code")
    parser.add_argument("--max-input-tokens", type=int, default=30_000)
    parser.add_argument("--max-output-tokens", type=int, default=2_000)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = build_preflight_report(
        schema_path=args.schema,
        tasks_path=args.tasks_jsonl,
        require_all_properties=not args.allow_optional_properties,
        require_tool_free_prompt=not args.allow_agent_tools,
    )
    canary_values = (
        args.canary_status,
        args.canary_events,
        args.canary_result,
        args.canary_task_code,
    )
    if any(canary_values) and not all(canary_values):
        raise SystemExit("canary 验收参数必须完整提供")
    if all(canary_values):
        report["canary"] = build_canary_acceptance_report(
            schema_path=args.schema,
            status_path=args.canary_status,
            event_log_path=args.canary_events,
            result_path=args.canary_result,
            task_code=args.canary_task_code,
            max_input_tokens=args.max_input_tokens,
            max_output_tokens=args.max_output_tokens,
        )
        report["status"] = "ready_for_batch_fanout"
    serialized = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8", newline="\n")
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
