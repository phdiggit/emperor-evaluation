from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse
from uuid import uuid4

import yaml
from opencc import OpenCC

from emperor_v4.adapters.source_text_index import LocalSourceTextIndex


WORKLIST_SCHEMA_VERSION = "discovery-source-backfill-worklist-v1"
RESULT_SCHEMA_VERSION = "google-ai-browser-result-v1"
I5B_SOURCE_SCOPE_SCHEMA_VERSION = "i5b-source-search-scope-v3"
DEFAULT_I5B_SOURCE_SCOPE_PATH = (
    Path(__file__).parents[3] / "config/i5b-source-search-scope.yml"
)
DEFAULT_I5B_WORK_BUDGET_PATH = (
    Path(__file__).parents[3] / "config/i5b-historical-work-budget.yml"
)
HANCHI_BATCH_PLAN_SCHEMA_VERSION = "hanchi-locator-batch-plan-v1"
HANCHI_BATCH_RESULT_SCHEMA_VERSION = "hanchi-locator-batch-result-v1"
HANCHI_POLICY_LINEAGE_SCHEMA_VERSION = "i5b-hanchi-policy-lineage-v1"
HANCHI_POLICY_JUDGE_WORKLIST_SCHEMA_VERSION = "i5b-hanchi-policy-judge-worklist-v1"
HANCHI_POLICY_REVIEW_PACK_SCHEMA_VERSION = "i5b-hanchi-policy-review-pack-v1"
_HANCHI_T2S = OpenCC("t2s")

_LEAD_BLOCK = re.compile(
    r"(?ms)^LEAD (?P<lead_code>L\d+)\s*$"
    r"(?P<body>.*?)"
    r"(?=^LEAD L\d+\s*$|^OMISSIONS\s*$)"
)
_SOURCE_HINT = re.compile(
    r"(?ms)^\s*(?:-\s*)?source_work:\s*(?P<work>.+?)\s*$"
    r".*?^\s*volume_or_section:\s*(?P<section>.+?)\s*$"
    r".*?^\s*source_url:\s*(?P<url>.+?)\s*$"
)
_OMISSIONS_BLOCK = re.compile(r"(?ms)^OMISSIONS\s*$\s*(?P<body>.*)$")


def _required_text(payload: Mapping[str, Any], field: str) -> str:
    value = str(payload.get(field) or "").strip()
    if not value:
        raise ValueError(f"discovery artifact 缺少 {field}")
    return value


def load_i5b_person_retrieval_limit(
    path: Path = DEFAULT_I5B_WORK_BUDGET_PATH,
) -> int:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    per_ruler = (payload or {}).get("per_ruler_run") or {}
    limit = int(per_ruler.get("max_person_retrieval_entries") or 0)
    if limit <= 0:
        raise ValueError("I5B 单皇帝人物检索入口上限必须为正数")
    if per_ruler.get("policy_entries_count_against_person_limit") is not False:
        raise ValueError("I5B 皇帝政策入口不得占用人物检索名额")
    return limit


def _block_field(body: str, field: str) -> str:
    match = re.search(
        rf"(?ms)^{re.escape(field)}:\s*(?P<value>.*?)(?=^[a-z_]+:\s*|\Z)",
        body,
    )
    value = match.group("value").strip() if match else ""
    if not value:
        raise ValueError(f"discovery lead 缺少 {field}")
    return value


def _optional_block_field(body: str, field: str, *, default: str) -> str:
    try:
        return _block_field(body, field)
    except ValueError:
        return default


def _locator_status(section: str, url: str) -> str:
    section_located = section not in {"未核", "不确定"} and "未核" not in section
    direct_url = _is_direct_document_url(url)
    if section_located and direct_url:
        return "work_section_and_url"
    if section_located:
        return "work_section_only"
    if direct_url:
        return "work_and_url"
    return "work_only"


def _is_direct_document_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    path = parsed.path.rstrip("/")
    if not path:
        return False
    if path.lower() in {"/zh", "/zh-hans", "/zh-hant", "/search"}:
        return False
    return True


def _projection_targets(lead_type: str) -> tuple[str, ...]:
    targets = ["historical_episode_candidate"]
    if lead_type in {"achievement", "authority_evaluation"}:
        targets.append("talent_profile_candidate")
    if lead_type == "risk":
        targets.append("political_risk_profile_candidate")
    return tuple(targets)


def load_i5b_source_search_scope(
    path: Path, *, dynasty: str
) -> tuple[str, dict[str, tuple[str, ...]]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("I5B 本地史料检索范围必须是 object")
    if payload.get("schema_version") != I5B_SOURCE_SCOPE_SCHEMA_VERSION:
        raise ValueError("I5B 本地史料检索范围版本不支持")
    raw_dynasties = payload.get("dynasties")
    if not isinstance(raw_dynasties, Mapping) or not raw_dynasties:
        raise ValueError("I5B 本地史料检索范围缺少 dynasties")
    requested_dynasty = _required_text({"dynasty": dynasty}, "dynasty")
    matches = []
    for canonical, raw in raw_dynasties.items():
        aliases = tuple(str(item) for item in (raw or {}).get("aliases") or ())
        if requested_dynasty == str(canonical) or requested_dynasty in aliases:
            matches.append((str(canonical), raw))
    if len(matches) != 1:
        raise ValueError(f"I5B 朝代必须唯一命中书目路由: {requested_dynasty}")
    canonical_dynasty, dynasty_policy = matches[0]
    raw_scopes = dynasty_policy.get("scopes") if isinstance(dynasty_policy, Mapping) else None
    if not isinstance(raw_scopes, Mapping):
        raise ValueError(f"I5B {canonical_dynasty} 书目路由缺少 scopes")
    required = {"civil_governance_discovery", "ruler_policy_discovery"}
    if set(raw_scopes) != required:
        raise ValueError("I5B 本地史料检索范围 purpose 不完整")
    scopes = {}
    for purpose, raw in raw_scopes.items():
        raw_works = raw.get("works") if isinstance(raw, Mapping) else raw
        works = tuple(
            dict.fromkeys(str(item).strip() for item in raw_works or ())
        )
        if not works or any(not work for work in works):
            raise ValueError(f"I5B 本地史料检索范围 {purpose} 缺少 works")
        scopes[str(purpose)] = works
    return canonical_dynasty, scopes


def load_i5b_source_page_ranges(
    path: Path, *, dynasty: str
) -> dict[str, tuple[int, int]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw_dynasties = payload.get("dynasties") if isinstance(payload, Mapping) else None
    if not isinstance(raw_dynasties, Mapping):
        raise ValueError("I5B 本地史料检索范围缺少 dynasties")
    matches = []
    for canonical, raw in raw_dynasties.items():
        aliases = tuple(str(item) for item in (raw or {}).get("aliases") or ())
        if dynasty == str(canonical) or dynasty in aliases:
            matches.append(raw)
    if len(matches) != 1:
        raise ValueError(f"I5B 朝代必须唯一命中页面范围: {dynasty}")
    raw_ranges = matches[0].get("page_ranges") or {}
    ranges = {}
    for work, bounds in raw_ranges.items():
        if not isinstance(bounds, Sequence) or isinstance(bounds, str) or len(bounds) != 2:
            raise ValueError(f"I5B {work} 页面范围必须是起止卷次")
        start, end = (int(bounds[0]), int(bounds[1]))
        if start <= 0 or end < start:
            raise ValueError(f"I5B {work} 页面范围无效")
        ranges[str(work)] = (start, end)
    return ranges


def _route_i5b_tasks_to_local_scope(
    tasks: Sequence[Mapping[str, Any]],
    scopes: Mapping[str, Sequence[str]],
) -> list[dict[str, Any]]:
    routed = []
    for raw in tasks:
        task = dict(raw)
        purpose = str(task["purpose_code"])
        works = tuple(scopes.get(purpose) or ())
        if not works:
            raise ValueError(f"I5B 本地史料检索没有配置 {purpose}")
        task["discovery_locators"] = list(task.get("locators") or ())
        task["locators"] = [
            {
                "source_work": work,
                "volume_or_section": "全书索引待定位",
                "source_url": "未核",
                "locator_status": "work_section_only",
            }
            for work in works
        ]
        task["source_route"] = "curated_local_text_index"
        routed.append(task)
    return routed


def _merge_i5b_scope_batches(
    batches: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for batch in batches:
        key = (str(batch["subject_ref"]), str(batch["subject_name"]))
        row = grouped.setdefault(
            key,
            {
                **batch,
                "source_url": "local-source-index:",
                "source_works": [],
                "requested_sections": ["全书索引待定位"],
                "lead_refs": [],
                "leads": [],
                "projection_targets": [],
            },
        )
        for field in ("source_works", "lead_refs", "projection_targets"):
            row[field].extend(batch.get(field) or ())
        row["leads"].extend(batch.get("leads") or ())
    merged = []
    for (subject_ref, _), row in sorted(grouped.items()):
        for field in ("source_works", "lead_refs", "projection_targets"):
            row[field] = list(dict.fromkeys(row[field]))
        row["leads"] = list(
            {str(lead["lead_ref"]): lead for lead in row["leads"]}.values()
        )
        row["source_batch_code"] = "I5BSCOPE-" + sha256(
            (subject_ref + "\n" + "\n".join(row["source_works"])).encode("utf-8")
        ).hexdigest()[:16].upper()
        merged.append(row)
    return merged


def _source_batches(tasks: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    unresolved = []
    for task in tasks:
        task_has_direct_locator = any(
            _is_direct_document_url(str(row["source_url"]))
            for row in task["locators"]
        )
        for locator in task["locators"]:
            url = str(locator["source_url"])
            lead_ref = f"{task['discovery_task_code']}:{task['lead_code']}"
            has_direct_url = _is_direct_document_url(url)
            has_local_index_locator = (
                locator["locator_status"] in {"work_section_only", "work_only"}
                and not task_has_direct_locator
            )
            if not has_direct_url and not has_local_index_locator:
                unresolved.append(
                    {
                        "lead_ref": lead_ref,
                        "source_work": locator["source_work"],
                        "volume_or_section": locator["volume_or_section"],
                        "source_url": url,
                        "reason": "local_source_index_or_direct_document_required",
                    }
                )
                continue
            batch_locator = (
                url
                if has_direct_url
                else "work-index:"
                + str(locator["source_work"])
                + ":"
                + str(locator["volume_or_section"])
            )
            key = (str(task["subject_ref"]), batch_locator)
            row = grouped.setdefault(
                key,
                {
                    "subject_ref": task["subject_ref"],
                    "subject_name": task["subject_name"],
                    "source_url": url,
                    "source_works": [],
                    "requested_sections": [],
                    "lead_refs": [],
                    "leads": [],
                    "projection_targets": [],
                    "usage": "source_backfill_candidate_only",
                },
            )
            row["source_works"].append(locator["source_work"])
            row["requested_sections"].append(locator["volume_or_section"])
            row["lead_refs"].append(lead_ref)
            row["leads"].append(
                {
                    "lead_ref": lead_ref,
                    "lead_type": task["lead_type"],
                    "lead": task["lead"],
                    "period_or_ruler_context": task["period_or_ruler_context"],
                    "subject_action": task["subject_action"],
                    "responsibility": task["responsibility"],
                    "observable_result": task["observable_result"],
                    "project_relevance": task["project_relevance"],
                    "uncertainty": task["uncertainty"],
                    **(
                        {"source_recall_terms": list(task["source_recall_terms"])}
                        if task.get("source_recall_terms")
                        else {}
                    ),
                    "projection_targets": list(
                        _projection_targets(str(task["lead_type"]))
                    ),
                    **(
                        {"hanchi_lineage": dict(task["hanchi_lineage"])}
                        if isinstance(task.get("hanchi_lineage"), Mapping)
                        else {}
                    ),
                }
            )
            row["projection_targets"].extend(_projection_targets(str(task["lead_type"])))
    batches = []
    for (subject_ref, url), row in sorted(grouped.items()):
        for field in (
            "source_works",
            "requested_sections",
            "lead_refs",
            "projection_targets",
        ):
            row[field] = list(dict.fromkeys(row[field]))
        row["leads"] = list(
            {
                lead["lead_ref"]: lead
                for lead in row["leads"]
            }.values()
        )
        row["source_batch_code"] = "SRCBACK-" + sha256(
            f"{subject_ref}\n{url}".encode("utf-8")
        ).hexdigest()[:16].upper()
        batches.append(row)
    resolved_lead_refs = {
        lead_ref
        for batch in batches
        for lead_ref in batch["lead_refs"]
    }
    return batches, [
        row for row in unresolved if row["lead_ref"] not in resolved_lead_refs
    ]


def artifact_to_backfill_tasks(
    artifact: Mapping[str, Any], *, artifact_name: str
) -> list[dict[str, Any]]:
    if artifact.get("schema_version") != RESULT_SCHEMA_VERSION:
        raise ValueError("discovery artifact 版本不支持")
    if (artifact.get("quality") or {}).get("status") != "passed":
        raise ValueError("只有质量门槛通过的 discovery artifact 才能生成回源待办")
    if (artifact.get("provenance") or {}).get("usage") != "discovery_lead_only":
        raise ValueError("discovery artifact usage 边界非法")

    discovery_task_code = _required_text(artifact, "task_code")
    discovery_input_version = _required_text(artifact, "input_version")
    discovery_input_fingerprint = _required_text(artifact, "input_fingerprint")
    subject_ref = _required_text(artifact, "subject_ref")
    subject_name = _required_text(artifact, "subject_name")
    purpose_code = _required_text(artifact, "purpose_code")
    answer = _required_text(artifact, "answer_text")
    blocks = list(_LEAD_BLOCK.finditer(answer))
    if not blocks:
        raise ValueError("discovery artifact 没有结构化 LEAD")

    tasks = []
    for match in blocks:
        lead_code = match.group("lead_code")
        body = match.group("body")
        locators = []
        for hint in _SOURCE_HINT.finditer(body):
            work = hint.group("work").strip()
            section = hint.group("section").strip()
            url = hint.group("url").strip()
            locators.append(
                {
                    "source_work": work,
                    "volume_or_section": section,
                    "source_url": url,
                    "locator_status": _locator_status(section, url),
                }
            )
        if not locators:
            raise ValueError(f"discovery lead {lead_code} 缺少 source_hints")
        lead = _block_field(body, "lead")
        tasks.append(
            {
                "task_code": f"{discovery_task_code}-{lead_code}-BACKFILL",
                "discovery_task_code": discovery_task_code,
                "discovery_input_version": discovery_input_version,
                "discovery_input_fingerprint": discovery_input_fingerprint,
                "discovery_captured_at": _required_text(artifact, "captured_at"),
                "discovery_artifact": artifact_name,
                "lead_code": lead_code,
                "subject_ref": subject_ref,
                "subject_name": subject_name,
                "purpose_code": purpose_code,
                "lead_type": _block_field(body, "lead_type"),
                "lead": lead,
                "period_or_ruler_context": _block_field(
                    body, "period_or_ruler_context"
                ),
                "subject_action": _block_field(body, "subject_action"),
                "responsibility": _block_field(body, "responsibility"),
                "observable_result": _block_field(body, "observable_result"),
                "project_relevance": _block_field(body, "project_relevance"),
                "locators": locators,
                "verification_query": " ".join(
                    dict.fromkeys(
                        [subject_name, lead, *(row["source_work"] for row in locators)]
                    )
                ),
                "uncertainty": _optional_block_field(
                    body,
                    "uncertainty",
                    default="模型未说明，待回源核验",
                ),
                "usage": "source_backfill_candidate_only",
                "source_passage_required": True,
            }
        )
    return tasks


def artifact_omission_gap(
    artifact: Mapping[str, Any], *, artifact_name: str
) -> dict[str, Any] | None:
    answer = _required_text(artifact, "answer_text")
    match = _OMISSIONS_BLOCK.search(answer)
    if not match:
        return None
    body = match.group("body")
    omitted = _block_field(body, "omitted_leads")
    if omitted in {"无", "none", "None"}:
        return None
    try:
        omission_reason = _block_field(body, "omission_reason")
    except ValueError:
        omission_reason = "模型未说明，待回源补充"
    return {
        "discovery_task_code": _required_text(artifact, "task_code"),
        "discovery_artifact": artifact_name,
        "purpose_code": _required_text(artifact, "purpose_code"),
        "omitted_leads": omitted,
        "omission_reason": omission_reason,
        "blocks_profile_review": (
            _required_text(artifact, "purpose_code")
            in {"person_rebuild_discovery", "authority_evaluation_discovery"}
        ),
    }


def build_backfill_worklist(result_paths: Sequence[Path]) -> dict[str, Any]:
    paths = sorted((Path(path) for path in result_paths), key=lambda path: path.name)
    if not paths:
        raise ValueError("没有 discovery result artifact")
    tasks = []
    discovery_omissions = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError(f"discovery artifact 必须是 object: {path}")
        tasks.extend(artifact_to_backfill_tasks(payload, artifact_name=path.name))
        omission = artifact_omission_gap(payload, artifact_name=path.name)
        if omission is not None:
            discovery_omissions.append(omission)
    return _build_backfill_worklist_from_tasks(
        tasks,
        input_artifacts=[path.name for path in paths],
        discovery_omissions=discovery_omissions,
    )


def _build_backfill_worklist_from_tasks(
    tasks: Sequence[Mapping[str, Any]],
    *,
    input_artifacts: Sequence[str],
    discovery_omissions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build the common source-cache worklist after a consumer has selected leads."""
    normalized_tasks = [dict(task) for task in tasks]
    task_codes = [row["task_code"] for row in normalized_tasks]
    if len(task_codes) != len(set(task_codes)):
        raise ValueError("回源待办 task_code 重复")
    source_batches, unresolved_locators = _source_batches(normalized_tasks)
    return {
        "schema_version": WORKLIST_SCHEMA_VERSION,
        "input_artifacts": list(input_artifacts),
        "tasks": normalized_tasks,
        "source_batches": source_batches,
        "unresolved_locators": unresolved_locators,
        "discovery_omissions": [dict(row) for row in discovery_omissions],
        "projection_policy": {
            "source_passage_required": True,
            "claim_extraction_required": True,
            "formal_write_allowed": False,
            "database_write_allowed": False,
            "profile_and_episode_share_verified_assertions": True,
        },
    }


def build_hanchi_policy_backfill_worklist(
    *,
    hanchi_plan: Mapping[str, Any],
    hanchi_result: Mapping[str, Any],
    ruler_ref: str,
    ruler_name: str,
) -> dict[str, Any]:
    """Convert candidate-specific Hanchi results into the common exact-source worklist."""
    if hanchi_plan.get("schema_version") != HANCHI_BATCH_PLAN_SCHEMA_VERSION:
        raise ValueError("汉籍政策回源只接受 batch plan v1")
    if hanchi_result.get("schema_version") != HANCHI_BATCH_RESULT_SCHEMA_VERSION:
        raise ValueError("汉籍政策回源只接受 batch result v1")
    ruler_ref = _required_text({"ruler_ref": ruler_ref}, "ruler_ref")
    ruler_name = _required_text({"ruler_name": ruler_name}, "ruler_name")
    if (
        str(hanchi_plan.get("ruler") or "") != str(hanchi_result.get("ruler") or "")
        or str(hanchi_plan.get("dynasty_scope") or "")
        != str(hanchi_result.get("dynasty_scope") or "")
    ):
        raise ValueError("汉籍政策 plan 与 result 的皇帝或朝代不一致")
    declarations = hanchi_result.get("transport_declarations") or {}
    if (
        declarations.get("official_retrieval_route") != "hanchi_post"
        or declarations.get("google_used_for_retrieval") is not False
    ):
        raise ValueError("汉籍政策正式检索链声明不完整")

    result_entries = {
        str(row.get("entry_ref") or ""): row
        for row in hanchi_result.get("entry_results") or ()
        if row.get("entry_kind") == "policy"
    }
    tasks: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    candidate_refs: set[str] = set()
    for entry in hanchi_plan.get("entries") or ():
        if entry.get("entry_kind") != "policy":
            continue
        entry_ref = str(entry.get("entry_ref") or "").strip()
        candidate_ref = str(entry.get("candidate_ref") or "").strip()
        candidate_summary = str(entry.get("candidate_summary") or "").strip()
        search_subject_name = str(entry.get("subject_name") or "").strip()
        source_recall_terms = [
            str(value).strip()
            for value in entry.get("source_recall_terms") or ()
            if str(value).strip()
        ]
        allowed_books = [str(value) for value in entry.get("allowed_books") or ()]
        if (
            not entry_ref
            or not candidate_ref
            or not candidate_summary
            or not allowed_books
            or candidate_ref in candidate_refs
        ):
            raise ValueError("汉籍政策候选缺少稳定身份、事项或书目范围")
        candidate_refs.add(candidate_ref)
        result_entry = result_entries.get(entry_ref)
        if not isinstance(result_entry, Mapping):
            raise ValueError(f"汉籍政策候选 {candidate_ref} 缺少执行结果")
        if str(result_entry.get("candidate_ref") or "") != candidate_ref:
            raise ValueError(f"汉籍政策候选 {candidate_ref} 结果身份漂移")
        query_lineage = list(result_entry.get("query_lineage") or ())
        if not search_subject_name:
            search_subject_name = next(
                (
                    str(row.get("subject_term") or "").strip()
                    for row in query_lineage
                    if isinstance(row, Mapping)
                    and str(row.get("subject_term") or "").strip()
                ),
                "",
            )
        if not any(
            row.get("mode") in {"advanced", "professional"}
            and str(row.get("topic_term") or "").strip()
            for row in query_lineage
            if isinstance(row, Mapping)
        ):
            raise ValueError(f"汉籍政策候选 {candidate_ref} 未执行候选特定查询")

        locators = []
        locator_keys = []
        for hit in result_entry.get("locator_hits") or ():
            locator = hit.get("locator") or {}
            source_work = str(locator.get("source_work") or "").strip()
            locator_key = str(hit.get("locator_key") or "").strip()
            if not source_work or source_work not in allowed_books or not locator_key:
                continue
            locator_keys.append(locator_key)
            locators.append(
                {
                    "source_work": source_work,
                    "volume_or_section": str(locator.get("title") or "汉籍命中书目"),
                    "source_url": "未核",
                    "locator_status": "work_section_only",
                }
            )
        status = (
            "ready_for_exact_source_backfill"
            if locators
            else "insufficient_no_filtered_hanchi_locator"
        )
        candidate_rows.append(
            {
                "candidate_ref": candidate_ref,
                "candidate_summary": candidate_summary,
                "entry_ref": entry_ref,
                "target_rule_hints": list(entry.get("target_rule_hints") or ()),
                "allowed_books": allowed_books,
                "hanchi_locator_keys": locator_keys,
                "status": status,
            }
        )
        if not locators:
            continue
        discovery_fingerprint = sha256(
            json.dumps(
                {
                    "candidate_ref": candidate_ref,
                    "candidate_summary": candidate_summary,
                    "query_lineage": query_lineage,
                    "locator_keys": locator_keys,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        ruler_context = str(entry.get("period_or_ruler_context") or ruler_name)
        if search_subject_name and search_subject_name not in ruler_context:
            ruler_context = f"{ruler_context}（{search_subject_name}）"
        tasks.append(
            {
                "task_code": f"{candidate_ref}-HANCHI-BACKFILL",
                "discovery_task_code": candidate_ref,
                "discovery_input_version": HANCHI_BATCH_RESULT_SCHEMA_VERSION,
                "discovery_input_fingerprint": discovery_fingerprint,
                "discovery_captured_at": "not_recorded:hanchi_post_batch",
                "discovery_artifact": f"hanchi-result:{entry_ref}",
                "lead_code": "H1",
                "subject_ref": ruler_ref,
                "subject_name": ruler_name,
                "purpose_code": "ruler_policy_discovery",
                "lead_type": "policy",
                "lead": candidate_summary,
                "source_recall_terms": source_recall_terms,
                "period_or_ruler_context": ruler_context,
                "subject_action": str(entry.get("subject_action") or candidate_summary),
                "responsibility": str(entry.get("responsibility") or "ruler_policy_candidate"),
                "observable_result": str(
                    entry.get("observable_result") or "待精确回源核验"
                ),
                "project_relevance": "historical_episode_candidate",
                "locators": locators,
                "verification_query": " ".join(
                    [
                        ruler_name,
                        *(
                            [search_subject_name]
                            if search_subject_name and search_subject_name != ruler_name
                            else []
                        ),
                        candidate_summary,
                        *allowed_books,
                    ]
                ),
                "uncertainty": str(entry.get("uncertainty") or "待精确回源核验"),
                "usage": "source_backfill_candidate_only",
                "source_passage_required": True,
                "hanchi_lineage": {
                    "schema_version": HANCHI_POLICY_LINEAGE_SCHEMA_VERSION,
                    "candidate_ref": candidate_ref,
                    "entry_ref": entry_ref,
                    "locator_keys": locator_keys,
                    "query_lineage": query_lineage,
                    "retrieval_route": "hanchi_post",
                    "google_used_for_retrieval": False,
                },
            }
        )

    if not candidate_rows:
        raise ValueError("汉籍批次没有候选级政策入口")
    if set(result_entries) != {row["entry_ref"] for row in candidate_rows}:
        raise ValueError("汉籍政策结果含未知或遗漏候选入口")
    payload = _build_backfill_worklist_from_tasks(
        tasks,
        input_artifacts=["hanchi-plan", "hanchi-result"],
        discovery_omissions=[],
    )
    # Keep the candidate-specific Hanchi path directly consumable by the
    # established I5B Source Cache runtime.  This selection block is routing
    # metadata, not a second policy limit: policy candidates remain uncapped.
    payload["i5b_selection"] = {
        "ruler_ref": ruler_ref,
        "ruler_name": ruler_name,
        "civil_discovery_lead_limit": 0,
        "ruler_policy_lead_limit": None,
        "policy_stop_condition": "candidate_disposition_closed",
        "deferred_discovery_leads": [],
        "formal_write_allowed": False,
        "database_write_allowed": False,
    }
    payload["hanchi_policy_lineage"] = {
        "schema_version": HANCHI_POLICY_LINEAGE_SCHEMA_VERSION,
        "ruler_ref": ruler_ref,
        "ruler_name": ruler_name,
        "candidate_count": len(candidate_rows),
        "candidates": candidate_rows,
        "candidate_disposition_closed": True,
        "retrieval_route": "hanchi_post_then_independent_exact_source_backfill",
        "google_used_for_retrieval": False,
    }
    return payload


def build_hanchi_policy_judge_worklist(
    backfill_worklist: Mapping[str, Any],
    *,
    source_reports: Sequence[Mapping[str, Any]],
    max_concurrency: int = 3,
) -> dict[str, Any]:
    """Group exact passages by Hanchi candidate into independent parallel Judge tasks."""
    if backfill_worklist.get("schema_version") != WORKLIST_SCHEMA_VERSION:
        raise ValueError("汉籍政策 Judge 只接受通用回源待办 v1")
    lineage = backfill_worklist.get("hanchi_policy_lineage") or {}
    if lineage.get("schema_version") != HANCHI_POLICY_LINEAGE_SCHEMA_VERSION:
        raise ValueError("汉籍政策 Judge 缺少候选 lineage")
    if max_concurrency <= 0:
        raise ValueError("汉籍政策 Judge 并发数必须为正数")
    passages = [
        dict(passage)
        for report in source_reports
        for passage in (report.get("response") or {}).get("passages") or ()
        if isinstance(passage, Mapping)
    ]
    tasks = []
    gaps = []
    for candidate in lineage.get("candidates") or ():
        candidate_ref = str(candidate["candidate_ref"])
        lead_ref = f"{candidate_ref}:H1"
        matched = [
            passage
            for passage in passages
            if lead_ref in (passage.get("selection_reason") or ())
        ]
        if candidate.get("status") != "ready_for_exact_source_backfill" or not matched:
            gaps.append(
                {
                    "candidate_ref": candidate_ref,
                    "disposition": "insufficient",
                    "reason": (
                        "no_filtered_hanchi_locator"
                        if candidate.get("status") != "ready_for_exact_source_backfill"
                        else "exact_source_passage_not_found"
                    ),
                }
            )
            continue
        tasks.append(
            {
                "schema_version": "i5b-hanchi-policy-judge-task-v1",
                "task_code": f"{candidate_ref}-JUDGE",
                "candidate_ref": candidate_ref,
                "candidate_summary": str(candidate["candidate_summary"]),
                "target_rule_hints": list(candidate.get("target_rule_hints") or ()),
                "source_passages": matched,
                "output_contract": {
                    "schema_version": "i5b-hanchi-policy-judge-result-v1",
                    "required_disposition": [
                        "counted",
                        "supporting",
                        "excluded",
                        "insufficient",
                    ],
                    "numeric_factor_values_forbidden": True,
                    "counted_requires_atomic_episode": True,
                },
            }
        )
    return {
        "schema_version": HANCHI_POLICY_JUDGE_WORKLIST_SCHEMA_VERSION,
        "ruler_ref": lineage["ruler_ref"],
        "ruler_name": lineage["ruler_name"],
        "candidate_count": int(lineage["candidate_count"]),
        "tasks": tasks,
        "automatic_gaps": gaps,
        "execution_policy": {
            "parallelizable": True,
            "max_concurrency": max_concurrency,
            "task_independence_key": "candidate_ref",
            "main_session_semantic_rejudge_required": False,
            "formal_write_allowed": False,
            "database_write_allowed": False,
        },
    }


def build_hanchi_policy_local_source_report(
    backfill_worklist: Mapping[str, Any],
    *,
    local_source_index_path: Path,
    max_passages_per_candidate: int = 2,
) -> dict[str, Any]:
    """Resolve Hanchi policy leads against immutable local revision text.

    Policy leads use ruler-title proximity plus explicit source recall terms;
    they must not reuse the person-biography locator's generic n-grams.
    """
    if backfill_worklist.get("schema_version") != WORKLIST_SCHEMA_VERSION:
        raise ValueError("汉籍政策本地回源只接受通用回源待办 v1")
    if max_passages_per_candidate <= 0:
        raise ValueError("汉籍政策每候选 passage 上限必须为正数")
    index = LocalSourceTextIndex(local_source_index_path)
    candidate_rows = {
        str(row["candidate_ref"]): row
        for row in (backfill_worklist.get("hanchi_policy_lineage") or {}).get(
            "candidates"
        )
        or ()
    }
    passages = []
    gaps = []
    for task in backfill_worklist.get("tasks") or ():
        lineage = task.get("hanchi_lineage") or {}
        candidate_ref = str(lineage.get("candidate_ref") or "")
        candidate = candidate_rows.get(candidate_ref) or {}
        terms = tuple(
            dict.fromkeys(
                _HANCHI_T2S.convert(str(term).strip())
                for term in task.get("source_recall_terms") or ()
                if str(term).strip()
            )
        )
        works = tuple(str(work) for work in candidate.get("allowed_books") or ())
        context = _HANCHI_T2S.convert(str(task.get("period_or_ruler_context") or ""))
        aliases = tuple(
            title
            for title in ("高祖", "太宗", "高宗", "中宗", "睿宗", "玄宗")
            if title in context
        )
        ranked = []
        for page in index.iter_pages(works=works):
            normalized = _HANCHI_T2S.convert(page.raw_text)
            for term in terms:
                start_at = 0
                while (position := normalized.find(term, start_at)) >= 0:
                    window_start = max(0, position - 440)
                    window_end = min(len(normalized), position + len(term) + 440)
                    window = normalized[window_start:window_end]
                    matched = tuple(value for value in terms if value in window)
                    actor_present = any(alias in window for alias in aliases)
                    strong = tuple(value for value in matched if len(value) >= 3)
                    if actor_present and (strong or len(matched) >= 2):
                        paragraph_start = page.raw_text.rfind("\n", window_start, position) + 1
                        paragraph_end = page.raw_text.find("\n", position, window_end)
                        if paragraph_end < 0:
                            paragraph_end = window_end
                        if paragraph_end - paragraph_start > 900:
                            paragraph_start = max(0, position - 360)
                            paragraph_end = min(len(page.raw_text), position + len(term) + 360)
                        raw_text = page.raw_text[paragraph_start:paragraph_end].strip()
                        if raw_text:
                            ranked.append(
                                (
                                    -len(matched),
                                    -sum(len(value) ** 2 for value in matched),
                                    page.page_title,
                                    paragraph_start,
                                    page,
                                    raw_text,
                                    matched,
                                )
                            )
                    start_at = position + 1
        selected = []
        seen_pages = set()
        for row in sorted(ranked):
            page = row[4]
            if page.page_title in seen_pages:
                continue
            seen_pages.add(page.page_title)
            selected.append(row)
            if len(selected) >= max_passages_per_candidate:
                break
        if not selected:
            gaps.append({"candidate_ref": candidate_ref, "reason": "strong_local_anchor_not_found"})
            continue
        for row in selected:
            page, raw_text, matched = row[4], row[5], row[6]
            passage_ref = "HANCHIPASSAGE-" + sha256(
                f"{candidate_ref}\n{page.page_title}\n{raw_text}".encode("utf-8")
            ).hexdigest()[:20].upper()
            passages.append(
                {
                    "passage_id": passage_ref,
                    "passage_ref": passage_ref,
                    "raw_text": raw_text,
                    "content_hash": sha256(raw_text.encode("utf-8")).hexdigest(),
                    "source_url": page.source_url,
                    "page_title": page.page_title,
                    "revision_ref": page.revision_ref,
                    "lineage_status": "exact_local_revision_text_match",
                    "selection_reason": [
                        "hanchi_policy_local_source_backfill",
                        f"{candidate_ref}:H1",
                        *(f"matched:{term}" for term in matched),
                    ],
                }
            )
    return {
        "schema_version": "i5b-hanchi-policy-local-source-report-v1",
        "source_index_identity": index.identity,
        "candidate_count": len(candidate_rows),
        "passage_count": len(passages),
        "gaps": gaps,
        "response": {"passages": passages, "errors": gaps},
        "formal_writes": 0,
        "database_writes": 0,
        "model_calls": 0,
    }


def merge_hanchi_policy_judge_results(
    worklist: Mapping[str, Any],
    results: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Fail closed unless every candidate has one acceptance-ready shadow disposition."""
    if worklist.get("schema_version") != HANCHI_POLICY_JUDGE_WORKLIST_SCHEMA_VERSION:
        raise ValueError("汉籍政策 Judge 合并输入版本不支持")
    task_by_ref = {str(row["candidate_ref"]): row for row in worklist.get("tasks") or ()}
    result_by_ref: dict[str, Mapping[str, Any]] = {}
    for result in results:
        candidate_ref = str(result.get("candidate_ref") or "")
        if (
            result.get("schema_version") != "i5b-hanchi-policy-judge-result-v1"
            or candidate_ref not in task_by_ref
            or candidate_ref in result_by_ref
            or str(result.get("task_code") or "") != task_by_ref[candidate_ref]["task_code"]
        ):
            raise ValueError("汉籍政策 Judge 结果版本、身份或唯一性非法")
        result_by_ref[candidate_ref] = result
    if set(result_by_ref) != set(task_by_ref):
        raise ValueError("汉籍政策 Judge 结果未覆盖全部可审候选")

    reviews = list(worklist.get("automatic_gaps") or ())
    allowed_rules = {
        "talent_discovery",
        "appointment_delegation",
        "tolerate_talent",
        "anti_nepotism",
    }
    for candidate_ref, task in task_by_ref.items():
        result = result_by_ref[candidate_ref]
        disposition = str(result.get("disposition") or "")
        reason = str(result.get("judge_reason") or "").strip()
        refs = [str(value) for value in result.get("passage_refs") or ()]
        available_refs = {
            str(row.get("passage_id") or row.get("passage_ref") or "")
            for row in task.get("source_passages") or ()
        }
        if (
            disposition not in {"counted", "supporting", "excluded", "insufficient"}
            or not reason
            or not set(refs) <= available_refs
            or any(key in result for key in ("factor_values", "material_magnitude", "score"))
        ):
            raise ValueError(f"汉籍政策候选 {candidate_ref} Judge 处置非法")
        normalized = {
            "candidate_ref": candidate_ref,
            "disposition": disposition,
            "judge_reason": reason,
            "passage_refs": refs,
        }
        if disposition == "counted":
            target_rule = str(result.get("target_rule") or "")
            episode = result.get("episode")
            factor_codes = result.get("factor_option_codes")
            if (
                target_rule not in allowed_rules
                or not refs
                or not isinstance(episode, Mapping)
                or not isinstance(factor_codes, Mapping)
                or not factor_codes
                or any(
                    not str(episode.get(field) or "").strip()
                    for field in (
                        "time_boundary",
                        "ruler_attribution",
                        "action_boundary",
                        "result_boundary",
                    )
                )
                or any(isinstance(value, (int, float)) for value in factor_codes.values())
            ):
                raise ValueError(f"汉籍政策候选 {candidate_ref} counted 输出不完整")
            normalized.update(
                {
                    "target_rule": target_rule,
                    "episode": dict(episode),
                    "factor_option_codes": {
                        str(key): str(value) for key, value in factor_codes.items()
                    },
                }
            )
        reviews.append(normalized)
    if len(reviews) != int(worklist["candidate_count"]):
        raise ValueError("汉籍政策候选处置未闭合")
    return {
        "schema_version": HANCHI_POLICY_REVIEW_PACK_SCHEMA_VERSION,
        "status": "acceptance_ready_shadow_policy_review",
        "ruler_ref": worklist["ruler_ref"],
        "ruler_name": worklist["ruler_name"],
        "candidate_reviews": sorted(reviews, key=lambda row: row["candidate_ref"]),
        "declarations": {
            "hanchi_retrieval_required": True,
            "google_used_for_retrieval": False,
            "candidate_disposition_closed": True,
            "main_session_semantic_rejudge_required": False,
            "numeric_factor_values_derived_later": True,
            "formal_write_allowed": False,
            "database_write_allowed": False,
        },
    }


def _artifact_downstream_context(artifact: Mapping[str, Any]) -> Mapping[str, Any]:
    provenance = artifact.get("provenance") or {}
    context = provenance.get("downstream_context") or {}
    if not isinstance(context, Mapping):
        raise ValueError("discovery artifact downstream_context 必须是 object")
    return context


def _civil_lead_priority(task: Mapping[str, Any]) -> tuple[int, int, str, str]:
    """Prefer directly locatable, result-bearing and stable independent civil leads."""
    direct_locator = any(
        _is_direct_document_url(str(row.get("source_url") or ""))
        for row in task.get("locators") or ()
    )
    lead_type = str(task.get("lead_type") or "")
    return (
        0 if direct_locator else 1,
        0 if lead_type == "achievement" else 1,
        str(task.get("lead") or ""),
        str(task.get("task_code") or ""),
    )


def build_i5b_ready_worklist(
    result_paths: Sequence[Path],
    *,
    ruler_ref: str,
    ruler_name: str,
    ruler_dynasty: str,
    max_civil_leads_per_person: int = 3,
    max_person_retrieval_entries: int | None = None,
    source_search_scopes: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, Any]:
    """Select source-backfill work for one ruler without limiting discovery itself.

    Civil discovery is a supplement to biography discovery, so only the three
    best independently locatable leads for each civil official enter the first
    source-backfill pass.  Ruler policy discovery has no lead-count cap: its
    natural bound is the caller's wall-clock budget during source backfill.
    """
    ruler_ref = _required_text({"ruler_ref": ruler_ref}, "ruler_ref")
    ruler_name = _required_text({"ruler_name": ruler_name}, "ruler_name")
    if max_civil_leads_per_person <= 0:
        raise ValueError("文臣首轮回源线索数必须为正数")
    configured_person_limit = load_i5b_person_retrieval_limit()
    person_limit = (
        configured_person_limit
        if max_person_retrieval_entries is None
        else int(max_person_retrieval_entries)
    )
    if person_limit <= 0:
        raise ValueError("I5B 单皇帝人物检索入口上限必须为正数")
    if person_limit > configured_person_limit:
        raise ValueError("I5B 人物检索入口不得超过配置的单皇帝硬上限")

    civil_by_person: dict[str, list[dict[str, Any]]] = {}
    civil_priority_by_person: dict[str, int] = {}
    policy_tasks: list[dict[str, Any]] = []
    artifacts: list[str] = []
    omissions: list[dict[str, Any]] = []
    for path in sorted((Path(item) for item in result_paths), key=lambda item: item.name):
        artifact = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(artifact, Mapping):
            raise ValueError(f"discovery artifact 必须是 object: {path}")
        purpose_code = _required_text(artifact, "purpose_code")
        if purpose_code not in {"civil_governance_discovery", "ruler_policy_discovery"}:
            continue
        context = _artifact_downstream_context(artifact)
        if (
            str(context.get("ruler_ref") or "") != ruler_ref
            or str(context.get("ruler_name") or "") != ruler_name
        ):
            raise ValueError("I5B discovery artifact 的皇帝上下文不匹配")
        artifact_dynasty = str(context.get("ruler_dynasty") or "")
        if artifact_dynasty and artifact_dynasty != ruler_dynasty:
            raise ValueError("I5B discovery artifact 的朝代上下文不匹配")
        tasks = artifact_to_backfill_tasks(artifact, artifact_name=path.name)
        artifacts.append(path.name)
        omission = artifact_omission_gap(artifact, artifact_name=path.name)
        if omission is not None:
            omissions.append(omission)
        if purpose_code == "civil_governance_discovery":
            person_ref = _required_text(artifact, "subject_ref")
            civil_by_person.setdefault(person_ref, []).extend(tasks)
            raw_priority = context.get("person_retrieval_priority")
            priority = int(raw_priority) if raw_priority is not None else 1_000_000
            civil_priority_by_person[person_ref] = min(
                priority,
                civil_priority_by_person.get(person_ref, priority),
            )
        else:
            policy_tasks.extend(tasks)

    if not artifacts:
        raise ValueError("没有该皇帝的 I5B 文臣治理或政策 discovery artifact")

    selected: list[dict[str, Any]] = []
    deferred: list[dict[str, str]] = []
    ordered_people = sorted(
        civil_by_person,
        key=lambda person_ref: (civil_priority_by_person[person_ref], person_ref),
    )
    selected_people = set(ordered_people[:person_limit])
    for person_ref in ordered_people:
        tasks = civil_by_person[person_ref]
        unique: dict[tuple[str, str], dict[str, Any]] = {}
        for task in tasks:
            key = (str(task["lead"]), str(task["subject_action"]))
            unique.setdefault(key, task)
        ranked = sorted(unique.values(), key=_civil_lead_priority)
        if person_ref not in selected_people:
            deferred.extend(
                {
                    "task_code": str(task["task_code"]),
                    "subject_ref": person_ref,
                    "reason": "deferred_boundary_candidate",
                }
                for task in ranked
            )
            continue
        selected.extend(ranked[:max_civil_leads_per_person])
        deferred.extend(
            {
                "task_code": str(task["task_code"]),
                "subject_ref": person_ref,
                "reason": "civil_first_pass_lead_limit",
            }
            for task in ranked[max_civil_leads_per_person:]
        )
    selected.extend(sorted(policy_tasks, key=_civil_lead_priority))
    if source_search_scopes is None:
        canonical_dynasty, loaded_scopes = load_i5b_source_search_scope(
            DEFAULT_I5B_SOURCE_SCOPE_PATH,
            dynasty=ruler_dynasty,
        )
        scopes = dict(loaded_scopes)
        page_ranges = load_i5b_source_page_ranges(
            DEFAULT_I5B_SOURCE_SCOPE_PATH,
            dynasty=ruler_dynasty,
        )
    else:
        canonical_dynasty = _required_text(
            {"ruler_dynasty": ruler_dynasty}, "ruler_dynasty"
        )
        scopes = dict(source_search_scopes)
        page_ranges = {}
    selected = _route_i5b_tasks_to_local_scope(selected, scopes)
    payload = _build_backfill_worklist_from_tasks(
        selected,
        input_artifacts=artifacts,
        discovery_omissions=omissions,
    )
    payload["source_batches"] = _merge_i5b_scope_batches(payload["source_batches"])
    payload["i5b_selection"] = {
        "ruler_ref": ruler_ref,
        "ruler_name": ruler_name,
        "ruler_dynasty": canonical_dynasty,
        "civil_discovery_lead_limit": max_civil_leads_per_person,
        "max_person_retrieval_entries": person_limit,
        "selected_person_count": len(selected_people),
        "selected_person_refs": [
            person_ref for person_ref in ordered_people if person_ref in selected_people
        ],
        "policy_entry_counts_against_person_limit": False,
        "ruler_policy_lead_limit": None,
        "policy_stop_condition": "wall_clock_budget_only",
        "source_route": "curated_local_text_index_then_revision_fetch",
        "google_locator_usage": "audit_only_not_executable_route",
        "source_search_scopes": {
            purpose: list(works) for purpose, works in sorted(scopes.items())
        },
        "source_page_ranges": {
            work: list(bounds) for work, bounds in sorted(page_ranges.items())
        },
        "deferred_discovery_leads": deferred,
        "formal_write_allowed": False,
        "database_write_allowed": False,
    }
    return payload


def build_ready_person_worklists(
    result_paths: Sequence[Path],
) -> dict[str, dict[str, Any]]:
    required_purposes = {
        "person_rebuild_discovery",
        "authority_evaluation_discovery",
        "political_risk_discovery",
    }
    grouped: dict[str, list[Path]] = {}
    purposes: dict[str, set[str]] = {}
    for path in sorted((Path(item) for item in result_paths), key=lambda item: item.name):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError(f"discovery artifact 必须是 object: {path}")
        subject_ref = _required_text(payload, "subject_ref")
        purpose_code = _required_text(payload, "purpose_code")
        if purpose_code not in required_purposes:
            continue
        grouped.setdefault(subject_ref, []).append(path)
        purposes.setdefault(subject_ref, set()).add(purpose_code)
    ready = {}
    for subject_ref, paths in sorted(grouped.items()):
        if purposes[subject_ref] != required_purposes:
            continue
        ready[subject_ref] = build_backfill_worklist(paths)
    return ready


def write_ready_person_worklists(
    directory: Path,
    payloads: Mapping[str, Mapping[str, Any]],
) -> dict[str, bool]:
    results = {}
    for subject_ref, payload in sorted(payloads.items()):
        code = "PERSONBACK-" + sha256(subject_ref.encode("utf-8")).hexdigest()[:16].upper()
        results[subject_ref] = write_backfill_worklist(
            directory / f"{code}.json",
            payload,
        )
    return results


def write_backfill_worklist(path: Path, payload: Mapping[str, Any]) -> bool:
    encoded = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    if path.is_file() and path.read_bytes() == encoded:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_bytes(encoded)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return True


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="将 discovery artifact 转为待回源定位清单")
    parser.add_argument("--results-dir", type=Path, required=True)
    outputs = parser.add_mutually_exclusive_group(required=True)
    outputs.add_argument("--output", type=Path)
    outputs.add_argument("--ready-dir", type=Path)
    parser.add_argument("--i5b-ruler-ref")
    parser.add_argument("--i5b-ruler-name")
    parser.add_argument("--i5b-ruler-dynasty")
    parser.add_argument("--max-civil-leads-per-person", type=int, default=3)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    paths = tuple(args.results_dir.glob("*.json"))
    i5b_identity = (
        bool(args.i5b_ruler_ref),
        bool(args.i5b_ruler_name),
        bool(args.i5b_ruler_dynasty),
    )
    if len(set(i5b_identity)) != 1:
        raise ValueError("I5B 回源必须同时提供皇帝 ref、皇帝名和朝代")
    if args.ready_dir:
        if args.i5b_ruler_ref:
            raise ValueError("I5B 回源使用 --output，不使用 --ready-dir")
        payloads = build_ready_person_worklists(paths)
        changes = write_ready_person_worklists(args.ready_dir, payloads)
        print(
            json.dumps(
                {
                    "ready_people": len(payloads),
                    "changed_people": sum(changes.values()),
                    "output": str(args.ready_dir),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    payload = (
        build_i5b_ready_worklist(
            paths,
            ruler_ref=args.i5b_ruler_ref,
            ruler_name=args.i5b_ruler_name,
            ruler_dynasty=args.i5b_ruler_dynasty,
            max_civil_leads_per_person=args.max_civil_leads_per_person,
        )
        if args.i5b_ruler_ref
        else build_backfill_worklist(paths)
    )
    changed = write_backfill_worklist(args.output, payload)
    print(
        json.dumps(
            {"changed": changed, "output": str(args.output), "tasks": len(payload["tasks"])},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
