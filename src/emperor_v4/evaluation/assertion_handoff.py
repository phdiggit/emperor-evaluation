from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from emperor_v4.adapters import adapt_claim_extractor_snapshot


def build_assertion_candidate_payloads(
    source_fixture_path: Path,
    handoff_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    source_bytes = source_fixture_path.read_bytes()
    source = json.loads(source_bytes.decode("utf-8"))
    handoff = yaml.safe_load(handoff_path.read_text(encoding="utf-8"))
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    if source_hash != handoff.get("source_fixture_sha256"):
        raise ValueError("assertion handoff source fixture hash 不一致")
    if handoff.get("execution_authorized") is not True:
        raise ValueError("assertion extraction execution 未授权")
    if handoff.get("production_write_authorized") is not False:
        raise ValueError("assertion extraction production write 必须禁用")
    if handoff.get("database_import_authorized") is not False:
        raise ValueError("assertion extraction database import 必须禁用")

    documents = {
        item["document_cache_id"]: item for item in source.get("documents", [])
    }
    focus_by_episode = handoff.get("episode_focus_person") or {}
    task_by_ruler = {item["ruler"]: item for item in handoff.get("tasks", [])}
    passages_by_ruler: dict[str, list[dict[str, Any]]] = {
        ruler: [] for ruler in task_by_ruler
    }
    for passage in source.get("passages", []):
        ruler = passage.get("ruler")
        episode_code = passage.get("episode_code")
        if ruler not in passages_by_ruler:
            raise ValueError(f"source passage ruler 不在 handoff task: {ruler}")
        if episode_code not in focus_by_episode:
            raise ValueError(f"source passage episode 无 focus person: {episode_code}")
        passages_by_ruler[ruler].append(passage)

    output_root.mkdir(parents=True, exist_ok=True)
    outputs: list[dict[str, Any]] = []
    seen_passages: set[str] = set()
    for ruler, task in task_by_ruler.items():
        passages = passages_by_ruler[ruler]
        referenced_document_ids = {item["document_cache_id"] for item in passages}
        object_names = sorted({focus_by_episode[item["episode_code"]] for item in passages})
        payload = {
            "schema_version": 1,
            "generated_by": "emperor_v4.evaluation.assertion_handoff",
            "task_identity": {
                "capture_profile": handoff["extraction_profile"],
                "capture_mode": "v4_episode_pilot_shadow",
                "emperor_name": ruler,
                "judge_mode": "claim_extraction_only",
                "rule_code": "i5b_item_wide",
                "target_code": task["target_code"],
            },
            "target_profile": {"primary_name": ruler},
            "rule": {"rule_code": "i5b_item_wide"},
            "object_seeds": [{"name": name} for name in object_names],
            "source_documents": [
                {
                    "document_code": document_id,
                    "source_kind": "wikisource_page",
                    "source_role": documents[document_id].get("source_role")
                    or "primary_source",
                    "title": documents[document_id]["title"],
                    "url": documents[document_id]["url"],
                }
                for document_id in sorted(referenced_document_ids)
            ],
            "candidate_slices": [],
            "coverage": {
                "checked_objects": object_names,
                "claim_count": 0,
                "alias_coverage_note": "v4_episode_pilot_shadow",
            },
            "coverage_gaps": [],
        }
        for passage in passages:
            passage_id = passage["passage_cache_id"]
            if passage_id in seen_passages:
                raise ValueError(f"source passage 重复进入 task: {passage_id}")
            seen_passages.add(passage_id)
            focus = focus_by_episode[passage["episode_code"]]
            payload["candidate_slices"].append(
                {
                    "slice_code": passage_id,
                    "document_code": passage["document_cache_id"],
                    "source_title": documents[passage["document_cache_id"]]["title"],
                    "locator": passage["locator"],
                    "text": passage["raw_text"],
                    "object_name": focus,
                    "matched_aliases": [focus],
                    "expected_event_repair": {
                        "event_inventory_codes": [passage["episode_code"]],
                        "related_window": passage.get("related_window") is True,
                    },
                }
            )

        output_path = output_root / Path(task["candidates_path"]).name
        rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        output_path.write_text(rendered, encoding="utf-8")
        outputs.append(
            {
                "task_code": task["task_code"],
                "ruler": ruler,
                "path": str(output_path),
                "sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
                "candidate_slice_count": len(passages),
                "object_count": len(object_names),
            }
        )

    expected_passages = {item["passage_cache_id"] for item in source.get("passages", [])}
    if seen_passages != expected_passages:
        raise ValueError("assertion handoff 未一一覆盖 source passages")
    return {
        "status": "passed",
        "source_fixture_sha256": source_hash,
        "input_passage_count": len(expected_passages),
        "task_count": len(outputs),
        "outputs": outputs,
    }


def _canonical_json_hash(payload: Any) -> str:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _all_strings(value: Any):
    if isinstance(value, dict):
        for item in value.values():
            yield from _all_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _all_strings(item)
    elif isinstance(value, str):
        yield value


def check_assertion_extraction_response(
    handoff_path: Path,
    execution_path: Path,
    response_path: Path,
) -> dict[str, Any]:
    handoff = yaml.safe_load(handoff_path.read_text(encoding="utf-8"))
    execution = yaml.safe_load(execution_path.read_text(encoding="utf-8"))
    response_bytes = response_path.read_bytes()
    response = json.loads(response_bytes.decode("utf-8"))
    errors: list[str] = []
    warnings: list[str] = []

    task_by_ruler = {item["ruler"]: item for item in handoff.get("tasks", [])}
    execution_by_ruler = {item["ruler"]: item for item in execution.get("tasks", [])}
    input_slices: dict[str, dict[str, Any]] = {}
    for ruler, task in task_by_ruler.items():
        candidate_path = Path(task["candidates_path"])
        candidates = json.loads(candidate_path.read_text(encoding="utf-8"))
        canonical_hash = _canonical_json_hash(candidates)
        if canonical_hash != execution_by_ruler[ruler]["canonical_candidate_sha256"]:
            errors.append(f"candidate canonical hash 不一致: {ruler}")
        for item in candidates.get("candidate_slices", []):
            slice_code = item["slice_code"]
            if slice_code in input_slices:
                errors.append(f"candidate slice 重复: {slice_code}")
            input_slices[slice_code] = {
                "ruler": ruler,
                "episode_code": (
                    item.get("expected_event_repair", {}).get("event_inventory_codes")
                    or [None]
                )[0],
            }

    used_slices: set[str] = set()
    claim_count = 0
    target_rejected = 0
    object_rejected = 0
    task_statuses: dict[str, str] = {}
    for person in response.get("people", []):
        ruler = person.get("ruler")
        payload = person.get("payload") or {}
        task_statuses[ruler] = str(payload.get("status"))
        for claim in payload.get("claims", []):
            claim_count += 1
            if claim.get("emperor_name") != ruler:
                errors.append(f"claim 跨皇帝污染: {claim.get('claim_code')}")
            refs = set(claim.get("source_slice_refs") or ())
            if not refs:
                errors.append(f"claim 缺少 source_slice_refs: {claim.get('claim_code')}")
            unknown = refs - set(input_slices)
            if unknown:
                errors.append(f"claim 引用未知 source slice: {sorted(unknown)}")
            used_slices.update(refs)
        target_rejected += int(
            payload.get("_target_emperor_gate", {}).get("rejected_claim_count") or 0
        )
        object_rejected += int(
            payload.get("_candidate_object_gate", {}).get("rejected_claim_count") or 0
        )

    if target_rejected:
        errors.append("target emperor gate 拒绝了 claim")
    if object_rejected:
        errors.append("candidate object gate 拒绝了 claim")
    if response.get("model_call_count", 0) > handoff.get("model_call_budget", 0):
        errors.append("模型调用超过预算")
    if response.get("production_write_performed") is not False:
        errors.append("发生了生产写入")
    if response.get("database_import_performed") is not False:
        errors.append("发生了数据库导入")

    response_hash = hashlib.sha256(response_bytes).hexdigest()
    if response_hash != execution.get("initial_run", {}).get("response_sha256"):
        errors.append("response hash 与 execution record 不一致")
    if execution.get("idempotency_check", {}).get("model_call_count") != 0:
        errors.append("幂等重跑不是零模型调用")

    adapted_count = 0
    try:
        adapted_count = len(adapt_claim_extractor_snapshot(response))
    except ValueError as exc:
        errors.append(f"AssertionDraft adapter 拒绝 response: {exc}")

    missing_slices = sorted(set(input_slices) - used_slices)
    if missing_slices:
        warnings.append(f"{len(missing_slices)} 个输入 passage 未产出 accepted claim")
    refinement_tasks = sorted(
        ruler for ruler, status in task_statuses.items() if status != "succeeded"
    )
    if refinement_tasks:
        warnings.append(f"任务需要 refinement: {', '.join(refinement_tasks)}")

    forbidden_values = [
        value
        for value in _all_strings(response)
        if value.startswith(("/data1/", "/home/", "/tmp/")) or "192.168." in value
    ]
    if forbidden_values:
        errors.append("response 包含运行环境路径或内网地址")

    status = "failed" if errors else (
        "passed_with_review_required" if warnings else "passed"
    )
    return {
        "report_schema_version": 1,
        "check": "assertion_extraction_response",
        "status": status,
        "response_sha256": response_hash,
        "input_passage_count": len(input_slices),
        "used_passage_count": len(used_slices),
        "unconsumed_passages": [
            {"passage_ref": ref, **input_slices[ref]} for ref in missing_slices
        ],
        "claim_count": claim_count,
        "assertion_draft_count": adapted_count,
        "model_call_count": response.get("model_call_count"),
        "idempotent_rerun_model_call_count": execution.get(
            "idempotency_check", {}
        ).get("model_call_count"),
        "target_gate_rejected_claim_count": target_rejected,
        "object_gate_rejected_claim_count": object_rejected,
        "task_statuses": task_statuses,
        "warnings": warnings,
        "errors": errors,
    }


def build_assertion_repair_payloads(
    handoff_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    handoff = yaml.safe_load(handoff_path.read_text(encoding="utf-8"))
    if handoff.get("execution_authorized") is not True:
        raise ValueError("assertion repair execution 未授权")
    if handoff.get("production_write_authorized") is not False:
        raise ValueError("assertion repair production write 必须禁用")
    if handoff.get("database_import_authorized") is not False:
        raise ValueError("assertion repair database import 必须禁用")

    source_fixtures = [
        handoff["source_fixture"],
        handoff["segmentation_repair_fixture"],
        *(handoff.get("additional_source_fixtures") or []),
    ]
    source_payloads = [
        json.loads(Path(path).read_text(encoding="utf-8"))
        for path in source_fixtures
    ]
    documents = {
        item["document_cache_id"]: item
        for payload in reversed(source_payloads)
        for item in payload.get("documents", [])
    }
    passages = {
        item["passage_cache_id"]: item
        for payload in source_payloads
        for item in payload.get("passages", [])
    }
    focus_by_episode = handoff.get("episode_focus_person") or {}
    participants_by_episode = handoff.get("episode_participants") or {}
    expected_assertions_by_episode = handoff.get("episode_expected_assertions") or {}
    aliases_by_ruler = handoff.get("ruler_aliases") or {}
    output_root.mkdir(parents=True, exist_ok=True)
    seen_passages: set[str] = set()
    outputs: list[dict[str, Any]] = []

    for task in handoff.get("tasks", []):
        ruler = task["ruler"]
        selected = [passages[ref] for ref in task.get("passage_refs", [])]
        referenced_document_ids = {item["document_cache_id"] for item in selected}
        object_names = sorted(
            {
                name
                for item in selected
                for name in (
                    participants_by_episode.get(item["episode_code"])
                    or [focus_by_episode[item["episode_code"]]]
                )
                if name != ruler
            }
        )
        payload = {
            "schema_version": 1,
            "generated_by": "emperor_v4.evaluation.assertion_handoff.repair",
            "task_identity": {
                "capture_profile": "i5b_item_wide",
                "capture_mode": "v4_episode_pilot_shadow_repair",
                "emperor_name": ruler,
                "judge_mode": "claim_extraction_only",
                "rule_code": "i5b_item_wide",
                "target_code": task["target_code"],
            },
            "target_profile": {
                "primary_name": ruler,
                "aliases": aliases_by_ruler.get(ruler, []),
            },
            "rule": {"rule_code": "i5b_item_wide"},
            "object_seeds": [{"name": name} for name in object_names],
            "source_documents": [
                {
                    "document_code": document_id,
                    "source_kind": "wikisource_page",
                    "source_role": documents[document_id].get("source_role")
                    or "primary_source",
                    "title": documents[document_id]["title"],
                    "url": documents[document_id]["url"],
                }
                for document_id in sorted(referenced_document_ids)
            ],
            "candidate_slices": [],
            "coverage": {
                "checked_objects": object_names,
                "claim_count": 0,
                "alias_coverage_note": "v4_episode_pilot_shadow_repair",
            },
            "coverage_gaps": [],
        }
        for passage in selected:
            passage_id = passage["passage_cache_id"]
            if passage_id in seen_passages:
                raise ValueError(f"repair passage 重复进入 task: {passage_id}")
            seen_passages.add(passage_id)
            focus = focus_by_episode[passage["episode_code"]]
            matched_aliases = [focus]
            if focus == ruler:
                matched_aliases.extend(aliases_by_ruler.get(ruler, []))
            payload["candidate_slices"].append(
                {
                    "slice_code": passage_id,
                    "document_code": passage["document_cache_id"],
                    "source_title": documents[passage["document_cache_id"]]["title"],
                    "locator": passage["locator"],
                    "text": passage["raw_text"],
                    "object_name": focus,
                    "matched_aliases": matched_aliases,
                    "expected_event_repair": {
                        "event_inventory_codes": [passage["episode_code"]],
                        "related_window": passage.get("related_window") is True,
                        "required_participants": participants_by_episode.get(
                            passage["episode_code"], []
                        ),
                        "expected_assertions": expected_assertions_by_episode.get(
                            passage["episode_code"], []
                        ),
                    },
                }
            )

        output_path = output_root / Path(task["candidates_path"]).name
        rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        output_path.write_bytes(rendered.encode("utf-8"))
        outputs.append(
            {
                "task_code": task["task_code"],
                "ruler": ruler,
                "path": str(output_path),
                "sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
                "candidate_slice_count": len(selected),
            }
        )

    expected = {ref for task in handoff.get("tasks", []) for ref in task.get("passage_refs", [])}
    if seen_passages != expected:
        raise ValueError("assertion repair 未一一覆盖 repair passages")
    return {
        "status": "passed",
        "input_passage_count": len(seen_passages),
        "task_count": len(outputs),
        "outputs": outputs,
    }


def check_assertion_repair_response(
    handoff_path: Path,
    execution_path: Path,
    response_path: Path,
) -> dict[str, Any]:
    handoff = yaml.safe_load(handoff_path.read_text(encoding="utf-8"))
    execution = yaml.safe_load(execution_path.read_text(encoding="utf-8"))
    response_bytes = response_path.read_bytes()
    response = json.loads(response_bytes.decode("utf-8"))
    errors: list[str] = []

    execution_tasks = {item["ruler"]: item for item in execution.get("tasks", [])}
    input_slices: set[str] = set()
    for task in handoff.get("tasks", []):
        candidates = json.loads(Path(task["candidates_path"]).read_text(encoding="utf-8"))
        canonical_hash = _canonical_json_hash(candidates)
        if canonical_hash != execution_tasks[task["ruler"]]["candidate_sha256"]:
            errors.append(f"repair candidate hash 不一致: {task['ruler']}")
        input_slices.update(
            item["slice_code"] for item in candidates.get("candidate_slices", [])
        )

    used_slices: set[str] = set()
    claim_count = 0
    gate_rejections = 0
    for person in response.get("people", []):
        ruler = person.get("ruler")
        payload = person.get("payload") or {}
        if payload.get("status") != "succeeded":
            errors.append(f"repair task 未成功: {ruler}")
        gate_rejections += int(
            payload.get("_target_emperor_gate", {}).get("rejected_claim_count") or 0
        )
        gate_rejections += int(
            payload.get("_candidate_object_gate", {}).get("rejected_claim_count") or 0
        )
        for claim in payload.get("claims", []):
            claim_count += 1
            if claim.get("emperor_name") != ruler:
                errors.append(f"repair claim 跨皇帝污染: {claim.get('claim_code')}")
            refs = set(claim.get("source_slice_refs") or ())
            if not refs or refs - input_slices:
                errors.append(f"repair claim source refs 非闭合: {claim.get('claim_code')}")
            used_slices.update(refs)
    if gate_rejections:
        errors.append("repair gate 拒绝了 claim")
    if used_slices != input_slices:
        errors.append("repair 未消费全部输入 passage")
    if response.get("model_call_count", 0) > handoff.get("model_call_budget", 0):
        errors.append("repair 模型调用超过预算")
    if response.get("database_import_performed") is not False:
        errors.append("repair 发生数据库导入")
    if response.get("production_write_performed") is not False:
        errors.append("repair 发生生产写入")

    response_hash = hashlib.sha256(response_bytes).hexdigest()
    if execution.get("response_sha256") != response_hash:
        errors.append("repair execution response hash 不一致")
    if execution.get("idempotency_check", {}).get("model_call_count") != 0:
        errors.append("repair 幂等重跑不是零模型调用")
    try:
        assertion_count = len(adapt_claim_extractor_snapshot(response))
    except ValueError as exc:
        assertion_count = 0
        errors.append(f"repair AssertionDraft adapter 拒绝: {exc}")

    return {
        "report_schema_version": 1,
        "check": "assertion_repair_response",
        "status": "passed" if not errors else "failed",
        "response_sha256": response_hash,
        "input_passage_count": len(input_slices),
        "used_passage_count": len(used_slices),
        "claim_count": claim_count,
        "assertion_draft_count": assertion_count,
        "model_call_count": response.get("model_call_count"),
        "idempotent_rerun_model_call_count": execution.get(
            "idempotency_check", {}
        ).get("model_call_count"),
        "gate_rejected_claim_count": gate_rejections,
        "errors": errors,
    }


def check_assertion_gap_repair_chain(
    handoff_paths: tuple[Path, ...],
    execution_paths: tuple[Path, ...],
    response_paths: tuple[Path, ...],
) -> dict[str, Any]:
    if not (
        len(handoff_paths) == len(execution_paths) == len(response_paths) == 2
    ):
        raise ValueError("gap repair chain 必须包含初次修复和一次 refinement")

    errors: list[str] = []
    expected_slices: set[str] = set()
    used_slices: set[str] = set()
    model_call_count = 0
    assertion_count = 0
    refinement_statuses: list[str] = []
    response_hashes: list[str] = []

    for handoff_path, execution_path, response_path in zip(
        handoff_paths, execution_paths, response_paths, strict=True
    ):
        handoff = yaml.safe_load(handoff_path.read_text(encoding="utf-8"))
        execution = yaml.safe_load(execution_path.read_text(encoding="utf-8"))
        response_bytes = response_path.read_bytes()
        response = json.loads(response_bytes.decode("utf-8"))
        response_hash = hashlib.sha256(response_bytes).hexdigest()
        response_hashes.append(response_hash)
        if execution.get("response_sha256") != response_hash:
            errors.append(f"gap repair response hash 不一致: {response_path.name}")
        if execution.get("idempotency_check", {}).get("model_call_count") != 0:
            errors.append(f"gap repair 幂等重跑非零调用: {response_path.name}")
        if response.get("database_import_performed") is not False:
            errors.append(f"gap repair 发生数据库导入: {response_path.name}")
        if response.get("production_write_performed") is not False:
            errors.append(f"gap repair 发生生产写入: {response_path.name}")

        current_calls = int(response.get("model_call_count") or 0)
        model_call_count += current_calls
        if current_calls > int(handoff.get("model_call_budget") or 0):
            errors.append(f"gap repair 超出单批预算: {response_path.name}")

        for task in handoff.get("tasks", []):
            candidates = json.loads(
                Path(task["candidates_path"]).read_text(encoding="utf-8")
            )
            expected_slices.update(
                item["slice_code"] for item in candidates.get("candidate_slices", [])
            )
        for person in response.get("people", []):
            payload = person.get("payload") or {}
            refinement_statuses.append(str(payload.get("status")))
            for gate_name in ("_target_emperor_gate", "_candidate_object_gate"):
                if int(payload.get(gate_name, {}).get("rejected_claim_count") or 0):
                    errors.append(
                        f"gap repair gate 拒绝 claim: {response_path.name}:{gate_name}"
                    )
            for claim in payload.get("claims", []):
                used_slices.update(claim.get("source_slice_refs") or ())
        try:
            assertion_count += len(adapt_claim_extractor_snapshot(response))
        except ValueError as exc:
            errors.append(f"gap repair AssertionDraft adapter 拒绝: {exc}")

    if used_slices != expected_slices:
        errors.append("gap repair chain 未合并消费全部输入 passage")
    if "needs_refinement" not in refinement_statuses:
        errors.append("gap repair chain 未保留首轮 refinement 状态")
    if refinement_statuses[-1] != "succeeded":
        errors.append("gap repair refinement 未成功")

    return {
        "report_schema_version": 1,
        "check": "assertion_gap_repair_chain",
        "status": "passed_with_recorded_refinement" if not errors else "failed",
        "input_passage_count": len(expected_slices),
        "used_passage_count": len(used_slices),
        "assertion_draft_count": assertion_count,
        "model_call_count": model_call_count,
        "idempotent_rerun_model_call_count": 0,
        "refinement_statuses": refinement_statuses,
        "response_sha256": response_hashes,
        "errors": errors,
    }
