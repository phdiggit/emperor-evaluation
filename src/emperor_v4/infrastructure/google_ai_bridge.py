from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import threading
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse
from uuid import uuid4
import webbrowser


TASK_SCHEMA_VERSION = "google-ai-browser-task-v1"
RESULT_SCHEMA_VERSION = "google-ai-browser-result-v1"
STATE_SCHEMA_VERSION = "google-ai-browser-queue-v1"
TERMINAL_STATES = frozenset({"succeeded", "failed_closed"})
FAIL_CLOSED_REASONS = frozenset(
    {"captcha", "rate_limited"}
)


class GoogleAiBridgeError(ValueError):
    pass


_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime | None) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value else None


def _worker_bootstrap_url(bridge_session: str) -> str:
    return (
        "https://www.google.com/search?q=emperor_v4_worker_bootstrap"
        f"&gai_bridge=1&gai_session={bridge_session}"
    )


def _parse_timestamp(value: object) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _fingerprint(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def normalize_task(task: Mapping[str, Any]) -> dict[str, Any]:
    required = (
        "task_code",
        "input_version",
        "purpose_code",
        "subject_ref",
        "subject_name",
        "query",
    )
    normalized = {name: str(task.get(name) or "").strip() for name in required}
    missing = [name for name, value in normalized.items() if not value]
    if missing:
        raise GoogleAiBridgeError(f"Google AI 任务缺少字段: {', '.join(missing)}")
    if not _CODE_RE.fullmatch(normalized["purpose_code"]):
        raise GoogleAiBridgeError("Google AI purpose_code 必须是稳定英文代码")
    if len(normalized["query"]) > 4000:
        raise GoogleAiBridgeError("Google AI query 超过 4000 字符")
    response_mode = str(task.get("response_mode") or "structured_discovery").strip()
    if response_mode not in {"structured_discovery", "free_text"}:
        raise GoogleAiBridgeError("Google AI response_mode 不受支持")
    requested_outputs = task.get("requested_outputs") or ()
    if (
        not isinstance(requested_outputs, (list, tuple))
        or not requested_outputs
        or any(not _CODE_RE.fullmatch(str(value)) for value in requested_outputs)
    ):
        raise GoogleAiBridgeError("Google AI requested_outputs 必须是非空稳定代码数组")
    if len(requested_outputs) != len(set(requested_outputs)):
        raise GoogleAiBridgeError("Google AI requested_outputs 不得重复")
    max_attempts = int(task.get("max_attempts") or 2)
    lease_seconds = int(task.get("lease_seconds") or 120)
    response_timeout_seconds = int(task.get("response_timeout_seconds") or 10)
    if (
        max_attempts < 1
        or max_attempts > 5
        or lease_seconds < 30
        or response_timeout_seconds < 5
        or response_timeout_seconds > 300
        or lease_seconds <= response_timeout_seconds
    ):
        raise GoogleAiBridgeError("Google AI 重试或 lease 参数非法")
    downstream_context = task.get("downstream_context") or {}
    if not isinstance(downstream_context, Mapping):
        raise GoogleAiBridgeError("Google AI downstream_context 必须是 object")
    quality = task.get("quality_requirements") or {}
    if not isinstance(quality, Mapping):
        raise GoogleAiBridgeError("Google AI quality_requirements 必须是 object")
    min_answer_characters = int(quality.get("min_answer_characters") or 120)
    min_source_links = int(quality.get("min_source_links") or 0)
    require_subject_mention = bool(quality.get("require_subject_mention", True))
    require_locator_hints = bool(quality.get("require_locator_hints", False))
    raw_aliases = task.get("subject_aliases") or ()
    if not isinstance(raw_aliases, (list, tuple)):
        raise GoogleAiBridgeError("Google AI subject_aliases 必须是 array")
    subject_aliases = [str(value).strip() for value in raw_aliases if str(value).strip()]
    if len(subject_aliases) != len(set(subject_aliases)):
        raise GoogleAiBridgeError("Google AI subject_aliases 不得重复")
    acceptable_subject_mentions = list(
        dict.fromkeys([normalized["subject_name"], *subject_aliases])
    )
    if not 120 <= min_answer_characters <= 10000 or not 0 <= min_source_links <= 20:
        raise GoogleAiBridgeError("Google AI quality_requirements 数值非法")
    body = {
        "schema_version": TASK_SCHEMA_VERSION,
        **normalized,
        "response_mode": response_mode,
        "subject_aliases": subject_aliases,
        "requested_outputs": [str(value) for value in requested_outputs],
        "max_attempts": max_attempts,
        "lease_seconds": lease_seconds,
        "response_timeout_seconds": response_timeout_seconds,
        "quality_requirements": {
            "min_answer_characters": min_answer_characters,
            "min_source_links": min_source_links,
            "require_subject_mention": require_subject_mention,
            "require_locator_hints": require_locator_hints,
            "acceptable_subject_mentions": acceptable_subject_mentions,
        },
        "downstream_context": dict(downstream_context),
        "query_strategy": "single_google_ai_mode_query",
        "allowed_write_scope": "queue_result_only",
        "output_schema": RESULT_SCHEMA_VERSION,
    }
    body["input_fingerprint"] = _fingerprint(body)
    return body


def validate_result(task: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]:
    if result.get("schema_version") != RESULT_SCHEMA_VERSION:
        raise GoogleAiBridgeError("Google AI result schema_version 不受支持")
    if result.get("task_code") != task["task_code"]:
        raise GoogleAiBridgeError("Google AI result task_code 不匹配")
    if result.get("input_fingerprint") != task["input_fingerprint"]:
        raise GoogleAiBridgeError("Google AI result input_fingerprint 不匹配")
    answer = str(result.get("answer_text") or "").strip()
    page_title = str(result.get("page_title") or "").strip()
    page_url = str(result.get("page_url") or "").strip()
    quality_requirements = task["quality_requirements"]
    if len(answer) < quality_requirements["min_answer_characters"]:
        raise GoogleAiBridgeError("Google AI answer_text 过短")
    response_mode = task.get("response_mode", "structured_discovery")
    if response_mode not in {"structured_discovery", "free_text"}:
        raise GoogleAiBridgeError("Google AI response_mode 不受支持")
    if task["query"] in answer or "您说：" in answer:
        raise GoogleAiBridgeError("Google AI answer_text 混入查询 prompt 或模板")
    if response_mode == "free_text":
        return _validate_free_text_result(task, result, answer=answer)
    required_structure = (
        "\nsearched_categories:",
        "\nuncovered_categories:",
        "\nstop_reason:",
        "\nLEAD L1\n",
        "\nOMISSIONS\n",
        "\nomitted_leads:",
        "\nomission_reason:",
    )
    if not answer.startswith("DISCOVERY_SUMMARY") or any(
        marker not in answer for marker in required_structure
    ):
        raise GoogleAiBridgeError("Google AI answer_text 缺少回答结构")
    prompt_markers = (
        "您说：",
        "searched_categories: <",
        "LEAD <L1...>",
        "lead_type: <",
    )
    if any(marker in answer for marker in prompt_markers):
        raise GoogleAiBridgeError("Google AI answer_text 混入查询 prompt 或模板")
    expected_lead_types = {
        "person_rebuild_discovery": {"event", "achievement"},
        "talent_achievement_discovery": {"achievement"},
        "authority_evaluation_discovery": {"authority_evaluation"},
        "political_risk_discovery": {"risk"},
        "civil_governance_discovery": {"policy", "achievement"},
        "ruler_policy_discovery": {"policy"},
    }
    allowed_lead_types = expected_lead_types.get(task["purpose_code"])
    ignored_off_focus_lead_count = 0
    if allowed_lead_types:
        blocks = list(
            re.finditer(
                r"(?ms)^LEAD L\d+\n(?P<body>.*?)(?=^LEAD L\d+\n|^OMISSIONS\n)",
                answer,
            )
        )
        focused_bodies = []
        for block in blocks:
            lead_type = re.search(r"(?m)^lead_type:\s*(\S+)\s*$", block.group("body"))
            if lead_type and lead_type.group(1) in allowed_lead_types:
                focused_bodies.append(block.group("body"))
            else:
                ignored_off_focus_lead_count += 1
        if ignored_off_focus_lead_count:
            if not focused_bodies:
                raise GoogleAiBridgeError("Google AI answer_text 不含任务焦点 lead")
            prefix, omissions = answer.split("OMISSIONS\n", 1)
            summary = prefix.split("LEAD L1\n", 1)[0]
            answer = summary + "".join(
                f"LEAD L{index}\n{body}"
                for index, body in enumerate(focused_bodies, start=1)
            ) + "OMISSIONS\n" + omissions
    if any(marker in answer for marker in ("“", "”", '"')):
        raise GoogleAiBridgeError("Google AI answer_text 包含引文或仿写原文")
    if quality_requirements.get("require_locator_hints"):
        allowed_source_types = {
            "biography",
            "chronicle",
            "annals",
            "law_code",
            "institutional_treatise",
            "edict_collection",
            "political_compendium",
            "historiography",
            "epitaph",
            "other",
        }
        lead_bodies = re.findall(
            r"(?ms)^LEAD L\d+\n(.*?)(?=^LEAD L\d+\n|^OMISSIONS\n)", answer
        )
        for lead_body in lead_bodies:
            fields = {
                name: re.findall(
                    rf"(?m)^\s*(?:-\s*)?{name}:\s*(\S.*?)\s*$", lead_body
                )
                for name in (
                    "source_type",
                    "source_work",
                    "volume_or_section",
                    "locator_anchor",
                    "locator_confidence",
                    "locator_uncertainty",
                    "source_url",
                )
            }
            hint_count = len(fields["source_work"])
            if not 1 <= hint_count <= 3 or any(
                len(values) != hint_count for values in fields.values()
            ):
                raise GoogleAiBridgeError(
                    "Google AI 每条 lead 必须有 1 至 3 组完整史源定位"
                )
            if any(value not in allowed_source_types for value in fields["source_type"]):
                raise GoogleAiBridgeError("Google AI source_type 非法")
            if any(
                value not in {"exact", "probable", "work_only"}
                for value in fields["locator_confidence"]
            ):
                raise GoogleAiBridgeError("Google AI locator_confidence 非法")
            if any(value != "未核" for value in fields["source_url"]):
                raise GoogleAiBridgeError("Google AI 宽搜不得输出 source_url")
    bare_source_urls = [
        value
        for value in re.findall(r"(?m)^\s*source_url:\s*(\S+)\s*$", answer)
        if value != "未核"
        and (
            not value.startswith(("http://", "https://"))
            or not urlparse(value).path.rstrip("/")
        )
    ]
    if bare_source_urls:
        raise GoogleAiBridgeError("Google AI answer_text 含裸域名或站点首页 source_url")
    searched_match = re.search(
        r"(?ms)^searched_categories:\s*(.*?)(?=^uncovered_categories:)", answer
    )
    uncovered_match = re.search(
        r"(?ms)^uncovered_categories:\s*(.*?)(?=^stop_reason:)", answer
    )
    if searched_match and uncovered_match:
        searched = set(re.findall(r"(?m)^\s*-\s*(.+?)\s*$", searched_match.group(1)))
        uncovered = set(re.findall(r"(?m)^\s*-\s*(.+?)\s*$", uncovered_match.group(1)))
        if searched & uncovered:
            raise GoogleAiBridgeError("Google AI 已检索与未覆盖类别自相矛盾")
    actual_lead_types = set(re.findall(r"(?m)^lead_type:\s*(\S+)\s*$", answer))
    if allowed_lead_types and (
        not actual_lead_types or not actual_lead_types <= allowed_lead_types
        or (
            len(allowed_lead_types) == 1
            and len(actual_lead_types) != 1
        )
    ):
        raise GoogleAiBridgeError("Google AI answer_text lead_type 与任务焦点不一致")
    if task["purpose_code"] == "authority_evaluation_discovery":
        authority_leads = re.findall(r"(?m)^lead:\s*(.+)\s*$", answer)
        if not authority_leads or any(
            lead.count("｜") != 2 or len(lead) > 120 for lead in authority_leads
        ):
            raise GoogleAiBridgeError("Google AI 权威评价 lead 未保持纯定位格式")
    stop_reasons = re.findall(r"(?m)^stop_reason:\s*(\S+)\s*$", answer)
    allowed_stop_reasons = {
        "exhausted_categories",
        "no_more_independent_leads",
        "source_link_unavailable",
        "time_or_search_limit",
    }
    if len(stop_reasons) != 1 or stop_reasons[0] not in allowed_stop_reasons:
        raise GoogleAiBridgeError("Google AI answer_text stop_reason 非法")
    matched_subject_mentions = [
        value
        for value in quality_requirements["acceptable_subject_mentions"]
        if value in answer
    ]
    if quality_requirements["require_subject_mention"] and not matched_subject_mentions:
        raise GoogleAiBridgeError("Google AI answer_text 未命中任务主体")
    parsed = urlparse(page_url)
    if parsed.scheme != "https" or parsed.netloc not in {
        "google.com",
        "www.google.com",
    }:
        raise GoogleAiBridgeError("Google AI page_url 非预期 Google 页面")
    raw_links = result.get("source_links") or ()
    if not isinstance(raw_links, (list, tuple)):
        raise GoogleAiBridgeError("Google AI source_links 必须是 array")
    links: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for row in raw_links:
        if not isinstance(row, Mapping):
            continue
        url = str(row.get("url") or "").strip()
        title = str(row.get("title") or "").strip()
        hostname = (urlparse(url).hostname or "").casefold()
        is_google = bool(re.search(r"(^|\.)google\.[a-z.]+$", hostname)) or hostname.endswith(
            ".googleusercontent.com"
        )
        if (
            url.startswith(("http://", "https://"))
            and not is_google
            and bool(urlparse(url).path.rstrip("/"))
            and url not in seen_urls
        ):
            seen_urls.add(url)
            links.append({"title": title, "url": url})
    if len(links) < quality_requirements["min_source_links"]:
        raise GoogleAiBridgeError("Google AI source_links 少于任务质量要求")
    blocked_markers = (
        "检测到异常流量",
        "稍后重试",
        "无法生成回答",
        "rate limit",
        "unusual traffic",
        "captcha",
    )
    if any(marker.casefold() in answer.casefold() for marker in blocked_markers):
        raise GoogleAiBridgeError("Google AI 页面显示限流或生成失败")
    attempt_started_at = str(result.get("attempt_started_at") or "").strip()
    answer_ready_at = str(result.get("answer_ready_at") or "").strip()
    discovery_duration_seconds = float(result.get("discovery_duration_seconds") or 0)
    if not attempt_started_at or not answer_ready_at or not 0 < discovery_duration_seconds <= 300:
        raise GoogleAiBridgeError("Google AI result 检索计时非法")
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "task_code": task["task_code"],
        "input_version": task["input_version"],
        "input_fingerprint": task["input_fingerprint"],
        "purpose_code": task["purpose_code"],
        "subject_ref": task["subject_ref"],
        "subject_name": task["subject_name"],
        "query": task["query"],
        "requested_outputs": list(task["requested_outputs"]),
        "answer_text": answer,
        "source_links": links,
        "page_title": page_title,
        "page_url": page_url,
        "captured_at": str(result.get("captured_at") or _timestamp(_now())),
        "timing": {
            "attempt_started_at": attempt_started_at,
            "answer_ready_at": answer_ready_at,
            "discovery_duration_seconds": round(discovery_duration_seconds, 3),
        },
        "quality": {
            "status": "passed",
            "subject_mentioned": bool(matched_subject_mentions),
            "matched_subject_mentions": matched_subject_mentions,
            "answer_characters": len(answer),
            "source_link_count": len(links),
            "ignored_off_focus_lead_count": ignored_off_focus_lead_count,
        },
        "provenance": {
            "collector": "chrome_extension",
            "usage": "discovery_lead_only",
            "direct_assertion_write_allowed": False,
            "source_passage_required_before_claim_extraction": True,
            "downstream_context": dict(task["downstream_context"]),
        },
    }


def _validate_free_text_result(
    task: Mapping[str, Any], result: Mapping[str, Any], *, answer: str
) -> dict[str, Any]:
    """Validate transport provenance without interpreting a prompt-specific contract."""
    quality = task["quality_requirements"]
    matched_subject_mentions = [
        value for value in quality["acceptable_subject_mentions"] if value in answer
    ]
    if quality["require_subject_mention"] and not matched_subject_mentions:
        raise GoogleAiBridgeError("Google AI answer_text 未命中任务主体")
    blocked_markers = (
        "检测到异常流量",
        "稍后重试",
        "无法生成回答",
        "rate limit",
        "unusual traffic",
        "captcha",
    )
    if any(marker.casefold() in answer.casefold() for marker in blocked_markers):
        raise GoogleAiBridgeError("Google AI 页面显示限流或生成失败")
    page_url = str(result.get("page_url") or "").strip()
    parsed = urlparse(page_url)
    if parsed.scheme != "https" or parsed.netloc not in {"google.com", "www.google.com"}:
        raise GoogleAiBridgeError("Google AI page_url 非预期 Google 页面")
    raw_links = result.get("source_links") or ()
    if not isinstance(raw_links, (list, tuple)):
        raise GoogleAiBridgeError("Google AI source_links 必须是 array")
    links: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for row in raw_links:
        if not isinstance(row, Mapping):
            continue
        url = str(row.get("url") or "").strip()
        title = str(row.get("title") or "").strip()
        hostname = (urlparse(url).hostname or "").casefold()
        is_google = bool(re.search(r"(^|\.)google\.[a-z.]+$", hostname)) or hostname.endswith(
            ".googleusercontent.com"
        )
        if (
            url.startswith(("http://", "https://"))
            and not is_google
            and bool(urlparse(url).path.rstrip("/"))
            and url not in seen_urls
        ):
            seen_urls.add(url)
            links.append({"title": title, "url": url})
    if len(links) < quality["min_source_links"]:
        raise GoogleAiBridgeError("Google AI source_links 少于任务质量要求")
    attempt_started_at = str(result.get("attempt_started_at") or "").strip()
    answer_ready_at = str(result.get("answer_ready_at") or "").strip()
    discovery_duration_seconds = float(result.get("discovery_duration_seconds") or 0)
    if not attempt_started_at or not answer_ready_at or not 0 < discovery_duration_seconds <= 300:
        raise GoogleAiBridgeError("Google AI result 检索计时非法")
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "task_code": task["task_code"],
        "input_version": task["input_version"],
        "input_fingerprint": task["input_fingerprint"],
        "purpose_code": task["purpose_code"],
        "subject_ref": task["subject_ref"],
        "subject_name": task["subject_name"],
        "query": task["query"],
        "requested_outputs": list(task["requested_outputs"]),
        "answer_text": answer,
        "source_links": links,
        "page_title": str(result.get("page_title") or "").strip(),
        "page_url": page_url,
        "captured_at": str(result.get("captured_at") or _timestamp(_now())),
        "timing": {
            "attempt_started_at": attempt_started_at,
            "answer_ready_at": answer_ready_at,
            "discovery_duration_seconds": round(discovery_duration_seconds, 3),
        },
        "quality": {
            "status": "passed",
            "subject_mentioned": bool(matched_subject_mentions),
            "matched_subject_mentions": matched_subject_mentions,
            "answer_characters": len(answer),
            "source_link_count": len(links),
            "ignored_off_focus_lead_count": 0,
        },
        "provenance": {
            "collector": "chrome_extension",
            "usage": "discovery_lead_only",
            "direct_assertion_write_allowed": False,
            "source_passage_required_before_claim_extraction": True,
            "downstream_context": dict(task["downstream_context"]),
        },
    }


@dataclass(slots=True)
class QueueStatus:
    pending: int
    leased: int
    succeeded: int
    retryable: int
    failed_closed: int
    paused: bool


class GoogleAiTaskQueue:
    def __init__(self, root: Path, *, clock: Any = _now) -> None:
        self.root = Path(root)
        self.clock = clock
        self.state_path = self.root / "state.json"
        self.results_dir = self.root / "results"
        self.rejected_dir = self.root / "rejected"
        self._lock = threading.RLock()

    def _empty(self) -> dict[str, Any]:
        return {
            "schema_version": STATE_SCHEMA_VERSION,
            "paused": False,
            "pause_reason": None,
            "tasks": [],
        }

    def _load(self) -> dict[str, Any]:
        if not self.state_path.is_file():
            return self._empty()
        payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != STATE_SCHEMA_VERSION:
            raise GoogleAiBridgeError("Google AI queue state 版本不受支持")
        if not isinstance(payload.get("tasks"), list):
            raise GoogleAiBridgeError("Google AI queue tasks 必须是 array")
        return payload

    def _save(self, state: Mapping[str, Any]) -> None:
        _atomic_json(self.state_path, state)

    def enqueue(self, tasks: Sequence[Mapping[str, Any]]) -> int:
        normalized = [normalize_task(row) for row in tasks]
        codes = [row["task_code"] for row in normalized]
        if len(codes) != len(set(codes)):
            raise GoogleAiBridgeError("manifest 内 task_code 不得重复")
        with self._lock:
            state = self._load()
            existing = {row["task"]["task_code"]: row for row in state["tasks"]}
            added = 0
            for task in normalized:
                current = existing.get(task["task_code"])
                if current is not None:
                    if current["task"]["input_fingerprint"] != task["input_fingerprint"]:
                        raise GoogleAiBridgeError("task_code 已存在但输入发生变化")
                    continue
                state["tasks"].append(
                    {
                        "task": task,
                        "status": "pending",
                        "attempts": 0,
                        "lease_owner": None,
                        "lease_token": None,
                        "lease_expires_at": None,
                        "last_error": None,
                    }
                )
                added += 1
            if added:
                self._save(state)
            return added

    def _recover_expired(self, state: dict[str, Any]) -> int:
        now = self.clock()
        recovered = 0
        for row in state["tasks"]:
            expiry = _parse_timestamp(row.get("lease_expires_at"))
            if row["status"] != "leased" or expiry is None or expiry > now:
                continue
            task = row["task"]
            row["status"] = (
                "retryable" if row["attempts"] < task["max_attempts"] else "failed_closed"
            )
            row["last_error"] = "lease_expired"
            row["lease_owner"] = None
            row["lease_token"] = None
            row["lease_expires_at"] = None
            recovered += 1
        return recovered

    def recover_interrupted_leases(self) -> int:
        with self._lock:
            state = self._load()
            recovered = 0
            for row in state["tasks"]:
                if row["status"] == "leased":
                    row["status"] = (
                        "retryable"
                        if row["attempts"] < row["task"]["max_attempts"]
                        else "failed_closed"
                    )
                    row["last_error"] = "bridge_restarted"
                    row["lease_owner"] = None
                    row["lease_token"] = None
                    row["lease_expires_at"] = None
                    recovered += 1
            if recovered:
                self._save(state)
            return recovered

    def claim(self, worker_id: str) -> dict[str, Any] | None:
        if not worker_id.strip():
            raise GoogleAiBridgeError("worker_id 不得为空")
        with self._lock:
            state = self._load()
            changed = bool(self._recover_expired(state))
            if state["paused"]:
                if changed:
                    self._save(state)
                return None
            for row in state["tasks"]:
                if row["status"] == "leased" and row["lease_owner"] == worker_id:
                    if changed:
                        self._save(state)
                    return dict(row["task"]) | {"lease_token": row["lease_token"]}
            if any(row["status"] == "leased" for row in state["tasks"]):
                if changed:
                    self._save(state)
                return None
            row = next(
                (row for row in state["tasks"] if row["status"] in {"pending", "retryable"}),
                None,
            )
            if row is None:
                if changed:
                    self._save(state)
                return None
            row["status"] = "leased"
            row["attempts"] += 1
            row["lease_owner"] = worker_id
            row["lease_token"] = uuid4().hex
            row["lease_expires_at"] = _timestamp(
                self.clock() + timedelta(seconds=row["task"]["lease_seconds"])
            )
            self._save(state)
            return dict(row["task"]) | {"lease_token": row["lease_token"]}

    def heartbeat(self, worker_id: str, lease_token: str) -> bool:
        with self._lock:
            state = self._load()
            for row in state["tasks"]:
                if (
                    row["status"] == "leased"
                    and row["lease_owner"] == worker_id
                    and row["lease_token"] == lease_token
                ):
                    row["lease_expires_at"] = _timestamp(
                        self.clock()
                        + timedelta(seconds=row["task"]["lease_seconds"])
                    )
                    self._save(state)
                    return True
            return False

    def _leased_row(
        self, state: Mapping[str, Any], worker_id: str, lease_token: str
    ) -> dict[str, Any]:
        row = next(
            (
                row
                for row in state["tasks"]
                if row["status"] == "leased"
                and row["lease_owner"] == worker_id
                and row["lease_token"] == lease_token
            ),
            None,
        )
        if row is None:
            raise GoogleAiBridgeError("lease 不存在或已失效")
        return row

    def complete(
        self, worker_id: str, lease_token: str, result: Mapping[str, Any]
    ) -> Path:
        with self._lock:
            state = self._load()
            row = self._leased_row(state, worker_id, lease_token)
            try:
                normalized = validate_result(row["task"], result)
            except GoogleAiBridgeError as exc:
                rejected_path = self.rejected_dir / (
                    f"{row['task']['task_code']}-attempt-{row['attempts']}.json"
                )
                rejected_payload = {
                    "schema_version": "google-ai-browser-rejected-v1",
                    "task_code": row["task"]["task_code"],
                    "input_fingerprint": row["task"]["input_fingerprint"],
                    "discovery_attempt": row["attempts"],
                    "error": str(exc),
                    "result": dict(result),
                    "rejected_at": _timestamp(self.clock()),
                }
                if not rejected_path.is_file():
                    _atomic_json(rejected_path, rejected_payload)
                row["status"] = "failed_closed"
                row["last_error"] = f"contract_invalid: {exc}"
                row["lease_owner"] = None
                row["lease_token"] = None
                row["lease_expires_at"] = None
                self._save(state)
                raise
            path = self.results_dir / f"{row['task']['task_code']}.json"
            if path.is_file():
                existing = json.loads(path.read_text(encoding="utf-8"))
                if existing != normalized:
                    raise GoogleAiBridgeError("成功 artifact 已存在但内容冲突")
            else:
                _atomic_json(path, normalized)
            row["status"] = "succeeded"
            row["lease_owner"] = None
            row["lease_token"] = None
            row["lease_expires_at"] = None
            row["last_error"] = None
            self._save(state)
            return path

    def fail(
        self,
        worker_id: str,
        lease_token: str,
        reason: str,
        detail: str = "",
        page_url: str = "",
        diagnostic_result: Mapping[str, Any] | None = None,
    ) -> None:
        reason = reason.strip()
        if not reason:
            raise GoogleAiBridgeError("失败 reason 不得为空")
        with self._lock:
            state = self._load()
            row = self._leased_row(state, worker_id, lease_token)
            row["last_error"] = f"{reason}: {detail}".strip(": ")
            if diagnostic_result:
                rejected_path = self.rejected_dir / (
                    f"{row['task']['task_code']}-attempt-{row['attempts']}.json"
                )
                rejected_payload = {
                    "schema_version": "google-ai-browser-rejected-v1",
                    "task_code": row["task"]["task_code"],
                    "input_fingerprint": row["task"]["input_fingerprint"],
                    "discovery_attempt": row["attempts"],
                    "error": row["last_error"],
                    "result": dict(diagnostic_result),
                    "rejected_at": _timestamp(self.clock()),
                }
                if not rejected_path.is_file():
                    _atomic_json(rejected_path, rejected_payload)
            row["lease_owner"] = None
            row["lease_token"] = None
            row["lease_expires_at"] = None
            if reason in FAIL_CLOSED_REASONS:
                row["status"] = "failed_closed"
                state["paused"] = True
                state["pause_reason"] = row["last_error"]
            elif reason == "invalid_contract":
                row["status"] = "failed_closed"
            elif row["attempts"] < row["task"]["max_attempts"]:
                row["status"] = "retryable"
            else:
                row["status"] = "failed_closed"
            self._save(state)

    def revalidate_failed_closed(self) -> dict[str, int]:
        """Re-check saved contract failures after a validator-only upgrade.

        This never opens Chrome, reissues a query, or changes the task input.
        """
        with self._lock:
            state = self._load()
            revalidated = 0
            still_closed = 0
            for row in state["tasks"]:
                if row["status"] != "failed_closed":
                    continue
                task = row["task"]
                rejected_path = self.rejected_dir / (
                    f"{task['task_code']}-attempt-{row['attempts']}.json"
                )
                if not rejected_path.is_file():
                    still_closed += 1
                    continue
                rejected = json.loads(rejected_path.read_text(encoding="utf-8"))
                if (
                    rejected.get("input_fingerprint") != task["input_fingerprint"]
                    or not isinstance(rejected.get("result"), Mapping)
                ):
                    still_closed += 1
                    continue
                try:
                    normalized = validate_result(task, rejected["result"])
                except GoogleAiBridgeError:
                    still_closed += 1
                    continue
                path = self.results_dir / f"{task['task_code']}.json"
                if path.is_file():
                    existing = json.loads(path.read_text(encoding="utf-8"))
                    if existing != normalized:
                        raise GoogleAiBridgeError("重验成功 artifact 与既有结果冲突")
                else:
                    _atomic_json(path, normalized)
                row["status"] = "succeeded"
                row["last_error"] = None
                row["lease_owner"] = None
                row["lease_token"] = None
                row["lease_expires_at"] = None
                revalidated += 1
            if revalidated:
                self._save(state)
            return {"revalidated": revalidated, "still_closed": still_closed}

    def status(self) -> QueueStatus:
        with self._lock:
            state = self._load()
            counts = {
                name: sum(row["status"] == name for row in state["tasks"])
                for name in (
                    "pending",
                    "leased",
                    "succeeded",
                    "retryable",
                    "failed_closed",
                )
            }
            return QueueStatus(**counts, paused=bool(state["paused"]))


class _BridgeHandler(BaseHTTPRequestHandler):
    queue: GoogleAiTaskQueue
    bridge_session: str

    def log_message(self, format: str, *args: object) -> None:
        return

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin") or ""
        return (
            not origin
            or origin == "https://www.google.com"
            or origin.startswith("chrome-extension://")
        )

    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        origin = self.headers.get("Origin")
        if origin and self._origin_allowed():
            self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        if not self._origin_allowed():
            self._json(403, {"error": "origin_forbidden"})
            return
        self._json(204, {})

    def do_GET(self) -> None:  # noqa: N802
        if not self._origin_allowed():
            self._json(403, {"error": "origin_forbidden"})
            return
        if self.path != "/health":
            self._json(404, {"error": "not_found"})
            return
        status = self.queue.status()
        self._json(200, {"status": "ok", **asdict(status)})

    def do_POST(self) -> None:  # noqa: N802
        if not self._origin_allowed():
            self._json(403, {"error": "origin_forbidden"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length) or b"{}")
            if payload.get("bridge_session") != self.bridge_session:
                self._json(409, {"error": "bridge_session_stale"})
                return
            worker_id = str(payload.get("worker_id") or "")
            if self.path == "/lease":
                task = self.queue.claim(worker_id)
                self._json(
                    200,
                    {
                        "status": "leased" if task else "idle",
                        "task": task,
                    },
                )
            elif self.path == "/heartbeat":
                ok = self.queue.heartbeat(worker_id, str(payload.get("lease_token") or ""))
                self._json(200 if ok else 409, {"status": "ok" if ok else "stale"})
            elif self.path == "/complete":
                path = self.queue.complete(
                    worker_id,
                    str(payload.get("lease_token") or ""),
                    payload.get("result") or {},
                )
                self._json(200, {"status": "succeeded", "artifact": path.name})
            elif self.path == "/fail":
                self.queue.fail(
                    worker_id,
                    str(payload.get("lease_token") or ""),
                    str(payload.get("reason") or ""),
                    str(payload.get("detail") or ""),
                    str(payload.get("page_url") or ""),
                    payload.get("diagnostic_result") or None,
                )
                self._json(200, {"status": "recorded"})
            else:
                self._json(404, {"error": "not_found"})
        except (GoogleAiBridgeError, json.JSONDecodeError) as exc:
            self._json(409, {"error": str(exc)})


def _read_manifest(path: Path) -> list[Mapping[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "google-ai-browser-manifest-v1":
        raise GoogleAiBridgeError("Google AI manifest 版本不受支持")
    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        raise GoogleAiBridgeError("Google AI manifest tasks 必须是 array")
    return tasks


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Google AI Chrome 串行任务桥接")
    parser.add_argument("--queue", type=Path, default=Path("tmp/google_ai_bridge"))
    sub = parser.add_subparsers(dest="command", required=True)
    enqueue = sub.add_parser("enqueue")
    enqueue.add_argument("--manifest", type=Path, required=True)
    sub.add_parser("status")
    sub.add_parser("revalidate-closed")
    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--open-worker", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    queue = GoogleAiTaskQueue(args.queue)
    if args.command == "enqueue":
        print(json.dumps({"added": queue.enqueue(_read_manifest(args.manifest))}))
        return 0
    if args.command == "status":
        print(json.dumps(asdict(queue.status()), ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "revalidate-closed":
        print(json.dumps(queue.revalidate_failed_closed(), ensure_ascii=False, sort_keys=True))
        return 0
    queue.recover_interrupted_leases()
    bridge_session = uuid4().hex
    handler = type(
        "BridgeHandler",
        (_BridgeHandler,),
        {"queue": queue, "bridge_session": bridge_session},
    )
    server = ThreadingHTTPServer((args.host, args.port), handler)
    if args.open_worker:
        webbrowser.open(_worker_bootstrap_url(bridge_session))
    print(f"Google AI bridge listening on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
