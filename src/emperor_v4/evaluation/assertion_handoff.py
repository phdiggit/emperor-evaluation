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
                    "source_role": documents[document_id]["source_role"],
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
