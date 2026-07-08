from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if __name__ == "__main__":
    sys.modules.setdefault("scripts.dev.retrieval_v2_clean_runner", sys.modules[__name__])

from scripts.dev import retrieval_v2_alias_refiner as alias_refiner
from scripts.dev import retrieval_v2_candidate_source_refiner as candidate_source_refiner
from scripts.dev import retrieval_v2_candidate_prompt as candidate_prompt
from scripts.dev import retrieval_v2_claim_cache as claim_cache
from scripts.dev import retrieval_v2_judge_shards as judge_shards
from scripts.dev import retrieval_v2_object_source_cache as object_source_cache
from scripts.dev.retrieval_v2_clean_summary import build_batch_summary, sum_usage, summarize_person
from scripts.dev.retrieval_v2_run_events import RunEventLogger
from scripts.dev import retrieval_v2_source_candidates as source_candidates
from scripts.dev import retrieval_v2_task_skeleton as task_skeleton

DEFAULT_TARGET_DSN_ENV = "EMPEROR_EVAL_RETRIEVAL_V2_DSN"

class RetrievalV2CleanRunnerError(RuntimeError):
    pass

@dataclass(frozen=True)
class CodexInvocation:
    phase: str
    prompt: str
    cwd: Path
    last_message: Path
    event_log: Path
    search: bool
    timeout_seconds: int
    codex_bin: str

@dataclass(frozen=True)
class CodexResult:
    payload: dict[str, Any]
    elapsed_seconds: float
    usage: dict[str, Any]

CodexRunner = Callable[[CodexInvocation], CodexResult]

DEFAULT_CODEX_SANDBOX = "read-only"
CODEX_SANDBOX_ENV = "RETRIEVAL_V2_CODEX_SANDBOX"
CODEX_ADD_DIRS_ENV = "RETRIEVAL_V2_CODEX_ADD_DIRS"
CODEX_BIN_ENV = "CODEX_BIN"

def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"

def stable_fingerprint(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()

def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    atomic_write_text(path, pretty_json(dict(payload)))


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RetrievalV2CleanRunnerError(f"expected object JSON: {path}")
    return payload


def load_env_file(path: Path) -> list[str]:
    if not path.exists():
        raise RetrievalV2CleanRunnerError(f"env file missing: {path}")
    loaded: list[str] = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip('"').strip("'")
        loaded.append(key)
    return loaded


def resolve_dsn(env_name: str) -> str:
    value = os.environ.get(env_name)
    if not value:
        raise RetrievalV2CleanRunnerError(f"missing PostgreSQL DSN env var: {env_name}")
    return value


def import_psycopg():
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ModuleNotFoundError as exc:  # pragma: no cover - environment guard
        raise RetrievalV2CleanRunnerError("psycopg is required for live retrieval_v2 task generation") from exc
    return psycopg, dict_row


def sanitize_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return token or stable_fingerprint(value)[:12]


def target_dir_name(task: Mapping[str, Any]) -> str:
    target_code = str(task.get("target_code") or "").strip()
    emperor_name = str(task.get("emperor_name") or "").strip()
    rule_code = str(task.get("rule_code") or source_candidates.rule_code(task) or "rule").strip()
    base = target_code or f"target_{stable_fingerprint([emperor_name, rule_code])[:12]}"
    return sanitize_token(f"{base}_{rule_code}")


def extract_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        if start < 0:
            raise
        payload, _ = json.JSONDecoder().raw_decode(stripped[start:])
    if not isinstance(payload, dict):
        raise RetrievalV2CleanRunnerError("Codex output is not a JSON object")
    return payload


def usage_from_events(stdout_text: str) -> dict[str, Any]:
    usage: dict[str, Any] = {}
    for line in stdout_text.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            usage = dict(event["usage"])
    return usage

def _env_list(name: str) -> list[str]:
    raw = os.environ.get(name, "")
    if not raw.strip():
        return []
    values: list[str] = []
    for chunk in re.split(r"[;\n]", raw):
        chunk = chunk.strip()
        if chunk:
            values.append(chunk)
    return values

def _codex_bin(invocation: CodexInvocation) -> str:
    if invocation.codex_bin != "codex":
        return invocation.codex_bin
    return os.environ.get(CODEX_BIN_ENV) or invocation.codex_bin

def _codex_sandbox() -> str:
    value = os.environ.get(CODEX_SANDBOX_ENV, DEFAULT_CODEX_SANDBOX).strip()
    return value or DEFAULT_CODEX_SANDBOX

def _codex_add_dirs(cwd: Path) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for raw in [str(cwd), *_env_list(CODEX_ADD_DIRS_ENV)]:
        path = Path(raw).expanduser().resolve()
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def run_codex(invocation: CodexInvocation) -> CodexResult:
    cwd = invocation.cwd.resolve()
    last_message = invocation.last_message.resolve()
    event_log = invocation.event_log.resolve()
    cwd.mkdir(parents=True, exist_ok=True)
    cmd = [_codex_bin(invocation)]
    if invocation.search:
        cmd.append("--search")
    else:
        cmd.extend(["--disable", "standalone_web_search", "--disable", "browser_use", "--disable", "browser_use_external"])
    cmd.extend(["-a", "never", "-s", _codex_sandbox()])
    for add_dir in _codex_add_dirs(cwd):
        add_dir.mkdir(parents=True, exist_ok=True)
        cmd.extend(["--add-dir", str(add_dir)])
    cmd.extend(
        [
            "exec",
            "--ephemeral",
            "--skip-git-repo-check",
            "--ignore-user-config",
            "--ignore-rules",
            "-C",
            str(cwd),
            "--output-last-message",
            str(last_message),
            "--json",
            "-",
        ]
    )
    started = time.perf_counter()
    completed = subprocess.run(
        cmd,
        input=invocation.prompt,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=invocation.timeout_seconds,
        check=False,
    )
    elapsed = round(time.perf_counter() - started, 3)
    atomic_write_text(event_log, completed.stdout + "\n--- STDERR ---\n" + completed.stderr)
    if completed.returncode != 0:
        raise RetrievalV2CleanRunnerError(
            f"codex {invocation.phase} failed rc={completed.returncode}; see {event_log}"
        )
    return CodexResult(
        payload=extract_json(last_message.read_text(encoding="utf-8")),
        elapsed_seconds=elapsed,
        usage=usage_from_events(completed.stdout),
    )


def fetch_retrieval_contexts(
    *,
    target_dsn: str,
    emperor_names: Sequence[str],
    item_code: str,
    rule_code: str,
    contract_code: str | None,
) -> dict[str, dict[str, Any]]:
    psycopg, dict_row = import_psycopg()
    contract_filter = "and rc.contract_code = %s" if contract_code else ""
    params: list[Any] = [list(emperor_names), item_code, rule_code]
    if contract_code:
        params.append(contract_code)
    sql = f"""
        select
            t.target_code,
            t.emperor_name,
            t.item_code,
            rc.contract_code,
            ri.intent_code,
            crr.rule_code,
            crr.rule_label,
            crr.material_policy_payload,
            crr.predicate_policy_payload,
            crr.requirement_payload,
            ri.intent_payload,
            t.target_payload,
            coalesce((
                select jsonb_agg(
                    jsonb_build_object(
                        'alias', ta.alias,
                        'alias_type', ta.alias_type,
                        'source', ta.source,
                        'alias_payload', ta.alias_payload
                    )
                    order by ta.alias_type, ta.alias
                )
                  from retrieval_v2.target_aliases ta
                 where ta.target_id = t.id
                   and ta.status = 'active'
            ), '[]'::jsonb) as target_aliases
          from retrieval_v2.retrieval_targets t
          join retrieval_v2.rule_contracts rc on rc.id = t.contract_id
          join retrieval_v2.retrieval_intents ri on ri.target_id = t.id
          join retrieval_v2.rule_contract_rules crr on crr.id = ri.contract_rule_id
         where t.emperor_name = any(%s)
           and t.item_code = %s
           and crr.rule_code = %s
           {contract_filter}
         order by t.emperor_name
    """
    with psycopg.connect(target_dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    by_name = {str(row["emperor_name"]): dict(row) for row in rows}
    missing = [name for name in emperor_names if name not in by_name]
    if missing:
        raise RetrievalV2CleanRunnerError(f"missing retrieval_v2 targets for {rule_code}: {missing}")
    return by_name


def normalize_task_from_context(task: Mapping[str, Any], context: Mapping[str, Any]) -> dict[str, Any]:
    result = json.loads(stable_json(task))
    result.setdefault("job_code", f"JOB-{context['item_code']}-{context['target_code']}-{context['rule_code']}-CLEAN")
    result["target_code"] = context["target_code"]
    result["emperor_name"] = context["emperor_name"]
    result["item_code"] = context["item_code"]
    result["contract_code"] = context["contract_code"]
    result["rule_code"] = context["rule_code"]
    if isinstance(context.get("target_payload"), Mapping):
        result["target_payload"] = dict(context["target_payload"])
    requirement = context.get("requirement_payload") or {}
    if isinstance(requirement, Mapping):
        result.setdefault("coverage_matrix", requirement.get("coverage_matrix") or {})
    result.setdefault("rule", {})
    if isinstance(result["rule"], dict):
        result["rule"].setdefault("rule_code", context["rule_code"])
        result["rule"].setdefault("rule_label", context.get("rule_label") or "")
        result["rule"].setdefault("coverage_matrix", result.get("coverage_matrix") or {})
    return result


def _presearch_backed_discovery_source_documents(
    discovery: Mapping[str, Any],
    prompt_skeleton: Mapping[str, Any],
) -> list[dict[str, Any]]:
    search_plan = prompt_skeleton.get("search_plan")
    if not isinstance(search_plan, Mapping):
        return []
    allowed_titles: set[str] = set()
    allowed_urls: set[str] = set()
    for hit in search_plan.get("presearch_hits") or []:
        if not isinstance(hit, Mapping):
            continue
        title = str(hit.get("title") or hit.get("wikisource_title") or "").strip()
        url = str(hit.get("url") or "").strip()
        if title:
            allowed_titles.add(title)
        if url:
            allowed_urls.add(url)
    if not allowed_titles and not allowed_urls:
        return []

    referenced_codes = {
        str(code).strip()
        for obj in discovery.get("object_seeds") or []
        if isinstance(obj, Mapping)
        for code in obj.get("source_document_codes") or []
        if str(code).strip()
    }
    docs = discovery.get("source_documents") or discovery.get("documents") or []
    trusted: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for doc in docs:
        if not isinstance(doc, Mapping):
            continue
        document_code = str(doc.get("document_code") or "").strip()
        if referenced_codes and document_code and document_code not in referenced_codes:
            continue
        title = str(doc.get("title") or "").strip()
        wikisource_title = str(doc.get("wikisource_title") or "").strip()
        url = str(doc.get("url") or "").strip()
        if not (
            (title and title in allowed_titles)
            or (wikisource_title and wikisource_title in allowed_titles)
            or (url and url in allowed_urls)
        ):
            continue
        key = (document_code, title or wikisource_title, url)
        if key in seen:
            continue
        seen.add(key)
        trusted.append(dict(doc))
    return trusted


def run_taskgen(
    *,
    context: Mapping[str, Any],
    run_root: Path,
    codex_runner: CodexRunner,
    codex_bin: str,
    timeout_seconds: int,
    search: bool,
    discovery_profile: Mapping[str, Any] | None = None,
    preseed_discovery: Mapping[str, Any] | None = None,
    event_logger: RunEventLogger | None = None,
) -> dict[str, Any]:
    draft_identity = {
        "target_code": context["target_code"],
        "rule_code": context["rule_code"],
        "emperor_name": context["emperor_name"],
    }
    person_dir = run_root / target_dir_name(draft_identity)
    skeleton = task_skeleton.build_task_skeleton(context)
    atomic_write_json(person_dir / "task.skeleton.json", skeleton)
    if discovery_profile is not None:
        if event_logger is not None:
            event_logger.emit(
                "taskgen_start",
                emperor_name=str(context["emperor_name"]),
                target_code=str(context["target_code"]),
                rule_code=str(context["rule_code"]),
                mode="discovery_profile",
            )
        task = task_skeleton.merge_taskgen_discovery(skeleton, discovery_profile)
        task = normalize_task_from_context(task, context)
        issues = task_skeleton.validate_task_for_candidates(task)
        if issues:
            raise RetrievalV2CleanRunnerError(f"discovery profile produced invalid task: {issues}")
        atomic_write_json(person_dir / "task.generated.json", task)
        atomic_write_json(person_dir / "discovery_profile.used.json", dict(discovery_profile))
        atomic_write_json(person_dir / "discovery_profile.generated.json", task_skeleton.discovery_profile_from_task(task))
        if event_logger is not None:
            event_logger.emit(
                "taskgen_done",
                emperor_name=str(context["emperor_name"]),
                target_code=str(context["target_code"]),
                rule_code=str(context["rule_code"]),
                mode="discovery_profile",
                elapsed_seconds_stage=0.0,
                input_tokens=0,
                output_tokens=0,
            )
        return {
            "task": task,
            "taskgen": {
                "elapsed_seconds": 0.0,
                "usage": {},
                "mode": "discovery_profile",
                "files": {
                    "skeleton": str(person_dir / "task.skeleton.json"),
                    "profile": str(person_dir / "discovery_profile.used.json"),
                    "generated_profile": str(person_dir / "discovery_profile.generated.json"),
                },
            },
        }

    prompt_skeleton = skeleton
    preseed_file: Path | None = None
    if preseed_discovery is not None:
        prompt_skeleton = task_skeleton.merge_taskgen_discovery(skeleton, preseed_discovery)
        preseed_file = person_dir / "task.preseed.json"
        atomic_write_json(preseed_file, prompt_skeleton)
        if event_logger is not None:
            event_logger.emit(
                "taskgen_preseed_applied",
                emperor_name=str(context["emperor_name"]),
                target_code=str(context["target_code"]),
                rule_code=str(context["rule_code"]),
                source_document_count=len(prompt_skeleton.get("source_documents") or []),
                presearch_hit_count=(prompt_skeleton.get("clean_audit") or {}).get("presearch_hit_count"),
            )

    taskgen_mode = "preseeded_skeleton_discovery" if preseed_file is not None else "skeleton_discovery"
    prompt = task_skeleton.discovery_prompt(context, prompt_skeleton, allow_search=search)
    atomic_write_text(person_dir / "taskgen_prompt.md", prompt)
    if event_logger is not None:
        event_logger.emit(
            "taskgen_start",
            emperor_name=str(context["emperor_name"]),
            target_code=str(context["target_code"]),
            rule_code=str(context["rule_code"]),
            mode=taskgen_mode,
            search=search,
            prompt_chars=len(prompt),
        )
    result = codex_runner(
        CodexInvocation(
            phase="taskgen",
            prompt=prompt,
            cwd=(person_dir / "taskgen").resolve(),
            last_message=(person_dir / "taskgen_last_message.json").resolve(),
            event_log=(person_dir / "taskgen_events.jsonl").resolve(),
            search=search,
            timeout_seconds=timeout_seconds,
            codex_bin=codex_bin,
        )
    )
    discovery_payload = dict(result.payload)
    if preseed_file is not None and not search:
        trusted_documents = _presearch_backed_discovery_source_documents(discovery_payload, prompt_skeleton)
        discovery_payload.pop("documents", None)
        if trusted_documents:
            discovery_payload["source_documents"] = trusted_documents
        else:
            discovery_payload.pop("source_documents", None)
    task = task_skeleton.merge_taskgen_discovery(prompt_skeleton, discovery_payload)
    task = normalize_task_from_context(task, context)
    issues = task_skeleton.validate_task_for_candidates(task)
    if issues:
        raise RetrievalV2CleanRunnerError(f"taskgen discovery produced invalid task: {issues}")
    atomic_write_json(person_dir / "task.generated.json", task)
    atomic_write_json(person_dir / "discovery_profile.generated.json", task_skeleton.discovery_profile_from_task(task))
    if event_logger is not None:
        event_logger.emit(
            "taskgen_done",
            emperor_name=str(context["emperor_name"]),
            target_code=str(context["target_code"]),
            rule_code=str(context["rule_code"]),
            mode=taskgen_mode,
            elapsed_seconds_stage=result.elapsed_seconds,
            input_tokens=result.usage.get("input_tokens"),
            output_tokens=result.usage.get("output_tokens"),
            reasoning_output_tokens=result.usage.get("reasoning_output_tokens"),
        )
    return {
        "task": task,
        "taskgen": {
            "elapsed_seconds": result.elapsed_seconds,
            "usage": result.usage,
            "mode": taskgen_mode,
            "files": {
                "skeleton": str(person_dir / "task.skeleton.json"),
                "preseed": str(preseed_file) if preseed_file is not None else None,
                "prompt": str(person_dir / "taskgen_prompt.md"),
                "events": str(person_dir / "taskgen_events.jsonl"),
                "last_message": str(person_dir / "taskgen_last_message.json"),
                "generated_profile": str(person_dir / "discovery_profile.generated.json"),
            },
        },
    }


def build_candidate_round(
    *,
    task: Mapping[str, Any],
    person_dir: Path,
    round_index: int,
    timeout: int,
    context_chars: int,
    max_slices_per_object: int,
    skip_fetch_errors: bool,
    source_cache_root: Path | None,
) -> dict[str, Any]:
    started = time.perf_counter()
    cache_dir = source_cache_root or (person_dir / "source_cache")
    candidates = source_candidates.build_candidates(
        task,
        cache_dir=cache_dir,
        timeout=timeout,
        context_chars=context_chars,
        max_slices_per_object=max_slices_per_object,
        skip_fetch_errors=skip_fetch_errors,
    )
    elapsed = round(time.perf_counter() - started, 3)
    output_path = person_dir / f"candidates.round{round_index}.json"
    prompt_path = person_dir / f"judge_prompt.round{round_index}.md"
    atomic_write_json(output_path, candidates)
    atomic_write_text(prompt_path, candidate_prompt.build_prompt(candidates))
    return {
        "payload": candidates,
        "elapsed_seconds": elapsed,
        "output_path": output_path,
        "prompt_path": prompt_path,
    }


def apply_object_source_cache_overlay(
    task: Mapping[str, Any],
    *,
    cache_root: Path,
    person_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    overlaid, stats = object_source_cache.overlay_task_from_cache(task, cache_root=cache_root)
    atomic_write_json(person_dir / "object_source_cache_overlay.json", {"cache_root": str(cache_root), "stats": stats})
    atomic_write_json(person_dir / "task.object_source_cache_overlay.json", overlaid)
    return overlaid, stats


def apply_claim_cache_to_candidates(
    candidates: Mapping[str, Any],
    *,
    cache_root: Path,
    person_dir: Path,
    round_index: int,
) -> tuple[dict[str, Any], dict[str, Any], Path]:
    input_path = person_dir / f"candidates.round{round_index}.claim_cache_input.json"
    output_path = person_dir / f"candidates.round{round_index}.claim_cache_uncovered.json"
    atomic_write_json(input_path, candidates)
    report = claim_cache.plan_candidates(input_path, cache_root, output_path)
    filtered = load_json(output_path)
    stats = dict(filtered.get("stats") or {})
    stats["candidate_slices_before_claim_cache"] = report["candidate_slice_count"]
    stats["candidate_slices"] = report["uncovered_slice_count"]
    stats["claim_cache_cached_slice_count"] = report["cached_slice_count"]
    stats["claim_cache_cached_claim_key_count"] = report["cached_claim_key_count"]
    filtered["stats"] = stats
    filtered["claim_cache_plan"] = report
    atomic_write_json(output_path, filtered)
    return filtered, report, output_path


def compact_claim_cache_plan(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": report.get("schema_version"),
        "cache_root": report.get("cache_root"),
        "candidates_path": report.get("candidates_path"),
        "uncovered_candidates_path": report.get("uncovered_candidates_path"),
        "candidate_slice_count": report.get("candidate_slice_count"),
        "cached_slice_count": report.get("cached_slice_count"),
        "uncovered_slice_count": report.get("uncovered_slice_count"),
        "cached_claim_key_count": report.get("cached_claim_key_count"),
        "by_object": report.get("by_object") or {},
        "suggested_policy": report.get("suggested_policy"),
    }


def build_alias_refinement_round(
    *,
    task_path: Path,
    task: Mapping[str, Any],
    candidates: Mapping[str, Any],
    judge_result: Mapping[str, Any] | None,
    person_dir: Path,
    round_index: int,
    stage: str,
) -> dict[str, Any]:
    payload = alias_refiner.build_refinement_payload(
        task_path=task_path,
        task=task,
        candidates=candidates,
        judge_result=judge_result,
    )
    output_path = person_dir / f"alias_patch.{stage}.round{round_index}.json"
    atomic_write_json(output_path, payload)
    prompt_path: Path | None = None
    if payload["stats"]["cli_alias_refiner_count"]:
        prompt_path = person_dir / f"alias_refiner_prompt.{stage}.round{round_index}.md"
        atomic_write_text(prompt_path, alias_refiner.build_cli_prompt(task, payload["patches"]))
    return {"payload": payload, "output_path": output_path, "prompt_path": prompt_path}


def run_judge_round(
    *,
    prompt_path: Path,
    person_dir: Path,
    round_index: int,
    codex_runner: CodexRunner,
    codex_bin: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    result = codex_runner(
        CodexInvocation(
            phase="judge",
            prompt=prompt_path.read_text(encoding="utf-8"),
            cwd=(person_dir / f"judge.round{round_index}").resolve(),
            last_message=(person_dir / f"judge_last_message.round{round_index}.json").resolve(),
            event_log=(person_dir / f"judge_events.round{round_index}.jsonl").resolve(),
            search=False,
            timeout_seconds=timeout_seconds,
            codex_bin=codex_bin,
        )
    )
    output_path = person_dir / f"judge_result.round{round_index}.json"
    atomic_write_json(output_path, result.payload)
    return {
        "payload": result.payload,
        "elapsed_seconds": result.elapsed_seconds,
        "usage": result.usage,
        "output_path": output_path,
    }


def with_judge_mode(candidates: Mapping[str, Any], judge_mode: str | None) -> dict[str, Any]:
    result = json.loads(stable_json(candidates))
    if not judge_mode:
        return result
    task_identity = result.get("task_identity")
    if not isinstance(task_identity, dict):
        task_identity = {}
    task_identity["judge_mode"] = judge_mode
    result["task_identity"] = task_identity
    return result


def run_judge(
    *,
    candidates: Mapping[str, Any],
    prompt_path: Path,
    person_dir: Path,
    round_index: int,
    codex_runner: CodexRunner,
    codex_bin: str,
    timeout_seconds: int,
    judge_shard_size: int,
    judge_shard_workers: int,
    judge_mode: str | None = None,
) -> dict[str, Any]:
    candidates = with_judge_mode(candidates, judge_mode)
    atomic_write_text(prompt_path, candidate_prompt.build_prompt(candidates))
    shards = judge_shards.build_judge_shards(
        candidates,
        max_objects_per_shard=judge_shard_size,
        round_index=round_index,
    )
    if not shards:
        result = run_judge_round(
            prompt_path=prompt_path,
            person_dir=person_dir,
            round_index=round_index,
            codex_runner=codex_runner,
            codex_bin=codex_bin,
            timeout_seconds=timeout_seconds,
        )
        result["payload"] = judge_shards.enrich_judge_payload(candidates, result["payload"])
        enriched_output_path = person_dir / f"judge_result.round{round_index}.enriched.json"
        atomic_write_json(enriched_output_path, result["payload"])
        result["output_path"] = enriched_output_path
        result["sharded"] = False
        result["shard_count"] = 1
        return result

    started = time.perf_counter()
    for shard in shards:
        shard_code = str(shard["shard_code"])
        atomic_write_json(person_dir / f"candidates.round{round_index}.{shard_code}.json", shard["payload"])
        atomic_write_text(
            person_dir / f"judge_prompt.round{round_index}.{shard_code}.md",
            judge_shards.build_judge_shard_prompt(shard["payload"]),
        )

    def run_one(shard: Mapping[str, Any]) -> dict[str, Any]:
        shard_code = str(shard["shard_code"])
        result = codex_runner(
            CodexInvocation(
                phase="judge_shard",
                prompt=(person_dir / f"judge_prompt.round{round_index}.{shard_code}.md").read_text(encoding="utf-8"),
                cwd=(person_dir / f"judge.round{round_index}.{shard_code}").resolve(),
                last_message=(person_dir / f"judge_last_message.round{round_index}.{shard_code}.json").resolve(),
                event_log=(person_dir / f"judge_events.round{round_index}.{shard_code}.jsonl").resolve(),
                search=False,
                timeout_seconds=timeout_seconds,
                codex_bin=codex_bin,
            )
        )
        output_path = person_dir / f"judge_result.round{round_index}.{shard_code}.json"
        atomic_write_json(output_path, result.payload)
        return {
            "shard": {"shard_code": shard_code, "object_names": list(shard.get("object_names") or [])},
            "payload": result.payload,
            "elapsed_seconds": result.elapsed_seconds,
            "usage": result.usage,
            "output_path": str(output_path),
        }

    workers = max(1, min(judge_shard_workers, len(shards)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        shard_results = list(pool.map(run_one, shards))
    elapsed = round(time.perf_counter() - started, 3)
    usage = sum_usage(
        [
            {
                "judge_usage": row.get("usage") or {},
                "taskgen_usage": {},
            }
            for row in shard_results
        ]
    )
    merged = judge_shards.merge_judge_shard_results(
        candidates=candidates,
        shard_results=shard_results,
        elapsed_seconds=elapsed,
        usage=usage,
    )
    output_path = person_dir / f"judge_result.round{round_index}.merged.json"
    atomic_write_json(output_path, merged)
    return {
        "payload": merged,
        "elapsed_seconds": elapsed,
        "usage": usage,
        "output_path": output_path,
        "sharded": True,
        "shard_count": len(shards),
    }


def process_task(
    *,
    task: Mapping[str, Any],
    run_root: Path,
    codex_runner: CodexRunner,
    codex_bin: str,
    skip_judge: bool,
    max_alias_refine_rounds: int,
    candidate_source_refine_rounds: int,
    candidate_source_refine_max_objects: int,
    candidate_source_refine_pages_per_object: int,
    candidate_source_refine_source_hint_limit: int,
    candidate_timeout: int,
    context_chars: int,
    max_slices_per_object: int,
    skip_fetch_errors: bool,
    source_cache_root: Path | None,
    judge_timeout_seconds: int, judge_shard_size: int, judge_shard_workers: int,
    judge_mode: str | None = None,
    claim_cache_root: Path | None = None,
    claim_cache_skip_cached_slices: bool = False,
    claim_cache_min_uncovered_slices_for_judge: int = 1,
    object_source_cache_root: Path | None = None,
    taskgen: Mapping[str, Any] | None = None,
    event_logger: RunEventLogger | None = None, candidate_source_refine_objects: Sequence[str] = (),
) -> dict[str, Any]:
    person_dir = run_root / target_dir_name(task)
    person_dir.mkdir(parents=True, exist_ok=True)
    current_task = json.loads(stable_json(task))
    if object_source_cache_root is not None:
        current_task, overlay_stats = apply_object_source_cache_overlay(
            current_task,
            cache_root=object_source_cache_root,
            person_dir=person_dir,
        )
        if event_logger is not None:
            event_logger.emit(
                "object_source_cache_overlay_done",
                emperor_name=str(current_task.get("emperor_name") or ""),
                target_code=str(current_task.get("target_code") or ""),
                rule_code=str(current_task.get("rule_code") or source_candidates.rule_code(current_task)),
                cache_root=str(object_source_cache_root),
                added_source_document_count=overlay_stats.get("added_source_document_count"),
                source_document_count=overlay_stats.get("source_document_count"),
                matched_object_count=len(overlay_stats.get("matched_object_names") or []),
            )
    target_code = str(current_task.get("target_code") or "")
    emperor_name = str(current_task.get("emperor_name") or "")
    rule_code = str(current_task.get("rule_code") or source_candidates.rule_code(current_task))
    if event_logger is not None:
        event_logger.emit(
            "target_start",
            emperor_name=emperor_name,
            target_code=target_code,
            rule_code=rule_code,
            taskgen_mode=taskgen.get("mode") if taskgen else None,
        )
    task_path = person_dir / "task.round0.json"
    atomic_write_json(task_path, current_task)
    rounds: list[dict[str, Any]] = []
    final_candidates: dict[str, Any] | None = None
    final_judge: dict[str, Any] | None = None
    alias_round_limit_reached = external_source_refine_used = False
    alias_refine_count = source_refine_count = 0
    def apply_source_refine(stage: str, payload: Mapping[str, Any], object_names: Sequence[str], round_index: int):
        nonlocal current_task, task_path, source_refine_count
        refined_task, source_stats = candidate_source_refiner.refine_task_sources_for_candidate_gaps(
            current_task, payload, object_names=object_names, stage=stage, max_objects=candidate_source_refine_max_objects,
            pages_per_object=candidate_source_refine_pages_per_object, source_hint_limit=candidate_source_refine_source_hint_limit,
            timeout=candidate_timeout,
        )
        source_refine_path = person_dir / f"task.{stage}_source_refine.round{round_index}.json"
        atomic_write_json(source_refine_path, refined_task)
        if not source_stats["added_source_document_count"]:
            return source_stats, source_refine_path, False
        issues = task_skeleton.validate_task_for_candidates(refined_task)
        if issues:
            raise RetrievalV2CleanRunnerError(f"{stage} source refinement produced invalid task: {issues}")
        source_refine_count += 1
        current_task = refined_task
        task_path = person_dir / f"task.round{round_index + 1}.json"
        atomic_write_json(task_path, current_task)
        return source_stats, source_refine_path, True
    for round_index in range(max_alias_refine_rounds + candidate_source_refine_rounds + 1):
        if event_logger is not None:
            event_logger.emit(
                "candidate_start",
                emperor_name=emperor_name,
                target_code=target_code,
                rule_code=rule_code,
                round=round_index,
            )
        candidate_result = build_candidate_round(
            task=current_task,
            person_dir=person_dir,
            round_index=round_index,
            timeout=candidate_timeout,
            context_chars=context_chars,
            max_slices_per_object=max_slices_per_object,
            skip_fetch_errors=skip_fetch_errors,
            source_cache_root=source_cache_root,
        )
        final_candidates = dict(candidate_result["payload"])
        if event_logger is not None:
            event_logger.emit(
                "candidate_done",
                emperor_name=emperor_name,
                target_code=target_code,
                rule_code=rule_code,
                round=round_index,
                elapsed_seconds_stage=candidate_result["elapsed_seconds"],
                candidate_slices=final_candidates.get("stats", {}).get("candidate_slices"),
                coverage_gap_count=len(final_candidates.get("coverage_gaps") or []),
                fetch_error_count=len(final_candidates.get("fetch_errors") or []),
                fetch_errors=final_candidates.get("fetch_errors") or [],
            )
        candidate_refinement = build_alias_refinement_round(
            task_path=task_path,
            task=current_task,
            candidates=final_candidates,
            judge_result=None,
            person_dir=person_dir,
            round_index=round_index,
            stage="candidate",
        )
        candidate_patch_stats = candidate_refinement["payload"]["stats"]
        round_summary: dict[str, Any] = {
            "round": round_index,
            "candidate_elapsed_seconds": candidate_result["elapsed_seconds"],
            "candidate_slices": final_candidates.get("stats", {}).get("candidate_slices"),
            "candidate_coverage_gap_count": len(final_candidates.get("coverage_gaps") or []),
            "candidate_source_refine_stats": None,
            "candidate_source_refine_task": None,
            "candidate_alias_patch_stats": candidate_patch_stats,
            "candidate_alias_patch": str(candidate_refinement["output_path"]),
            "candidate_alias_prompt": str(candidate_refinement["prompt_path"])
            if candidate_refinement["prompt_path"]
            else None,
            "judge_elapsed_seconds": None,
            "judge_status": None,
            "judge_sharded": False,
            "judge_shard_count": 0,
            "judge_alias_patch_stats": None,
            "claim_cache_plan": None,
            "claim_cache_uncovered_candidates": None,
        }
        external_gap_names = list(candidate_source_refine_objects) if not external_source_refine_used else []
        gap_object_names = candidate_source_refiner.unique_strings(
            [*candidate_source_refiner.candidate_gap_object_names(final_candidates), *external_gap_names]
        )
        if gap_object_names and source_refine_count < candidate_source_refine_rounds:
            external_source_refine_used = external_source_refine_used or bool(external_gap_names)
            if event_logger is not None:
                event_logger.emit(
                    "candidate_source_refine_start", emperor_name=emperor_name, target_code=target_code,
                    rule_code=rule_code, round=round_index, gap_object_count=len(gap_object_names),
                    max_objects=candidate_source_refine_max_objects,
                    pages_per_object=candidate_source_refine_pages_per_object,
                    source_hint_limit=candidate_source_refine_source_hint_limit,
                )
            source_stats, source_refine_path, refined = apply_source_refine("candidate", final_candidates, external_gap_names, round_index)
            round_summary["candidate_source_refine_stats"] = source_stats
            round_summary["candidate_source_refine_task"] = str(source_refine_path)
            if event_logger is not None:
                event_logger.emit(
                    "candidate_source_refine_done", emperor_name=emperor_name, target_code=target_code,
                    rule_code=rule_code, round=round_index, gap_object_count=len(gap_object_names),
                    added_source_document_count=source_stats["added_source_document_count"],
                    source_document_count=source_stats["source_document_count"], hit_count=source_stats["hit_count"],
                    error_count=source_stats["error_count"],
                )
            if refined:
                rounds.append(round_summary)
                continue
        if candidate_patch_stats["apply_alias_patch_count"]:
            if alias_refine_count >= max_alias_refine_rounds:
                alias_round_limit_reached = True
            else:
                alias_refine_count += 1
                current_task = alias_refiner.apply_alias_patches(current_task, candidate_refinement["payload"]["patches"])
                task_path = person_dir / f"task.round{round_index + 1}.json"
                atomic_write_json(task_path, current_task)
                rounds.append(round_summary)
                continue

        if skip_judge:
            rounds.append(round_summary)
            break

        judge_candidates = final_candidates
        claim_cache_plan: dict[str, Any] | None = None
        if (
            claim_cache_root is not None
            and claim_cache_skip_cached_slices
            and judge_mode == candidate_prompt.CLAIM_EXTRACTION_ONLY_MODE
        ):
            judge_candidates, claim_cache_plan, uncovered_path = apply_claim_cache_to_candidates(
                final_candidates,
                cache_root=claim_cache_root,
                person_dir=person_dir,
                round_index=round_index,
            )
            round_summary["claim_cache_plan"] = compact_claim_cache_plan(claim_cache_plan)
            round_summary["claim_cache_uncovered_candidates"] = str(uncovered_path)
            if event_logger is not None:
                event_logger.emit(
                    "claim_cache_plan_done",
                    emperor_name=emperor_name,
                    target_code=target_code,
                    rule_code=rule_code,
                    round=round_index,
                    cache_root=str(claim_cache_root),
                    candidate_slice_count=claim_cache_plan["candidate_slice_count"],
                    cached_slice_count=claim_cache_plan["cached_slice_count"],
                    uncovered_slice_count=claim_cache_plan["uncovered_slice_count"],
                    cached_claim_key_count=claim_cache_plan["cached_claim_key_count"],
                )
            uncovered_count = len(judge_candidates.get("candidate_slices") or [])
            min_uncovered = max(1, int(claim_cache_min_uncovered_slices_for_judge))
            if uncovered_count < min_uncovered:
                all_cached = uncovered_count == 0
                final_judge = {
                    "job_code": f"JOB-{target_code}-{rule_code}-CLAIM-CACHE-HIT",
                    "status": "succeeded" if all_cached else "needs_refinement",
                    "documents": [],
                    "passages": [],
                    "claims": [],
                    "primary_bindings": [],
                    "secondary_binding_candidates": [],
                    "coverage_matrix": {"rule_code": rule_code, "role_families": []},
                    "coverage": {
                        "ready_for_object_pool": False,
                        "checked_objects": [],
                        "missing_core_objects": [],
                        "positive_claim_count": 0,
                        "negative_claim_count": 0,
                        "alias_coverage_note": "claim_cache_all_slices_cached",
                    },
                    "coverage_gaps": []
                    if all_cached
                    else [
                        {
                            "gap_type": "claim_cache_tail_uncovered",
                            "object_name": "",
                            "family_code": "",
                            "queue": "claim_cache_tail_review",
                            "diagnosis": f"{uncovered_count} uncovered candidate slices below claim_cache_min_uncovered_slices_for_judge={min_uncovered}",
                            "recommended_action": "batch_tail_claim_extraction_or_accept_cached_claim_set",
                            "do_not_add_recall_terms": True,
                        }
                    ],
                    "_elapsed_seconds": 0.0,
                    "_usage": {},
                    "_judge_mode": judge_mode or "",
                    "_claim_cache_plan": claim_cache_plan,
                }
                round_summary["judge_elapsed_seconds"] = 0.0
                round_summary["judge_status"] = final_judge["status"]
                if event_logger is not None:
                    event_logger.emit(
                        "judge_skipped_by_claim_cache",
                        emperor_name=emperor_name,
                        target_code=target_code,
                        rule_code=rule_code,
                        round=round_index,
                        cached_slice_count=claim_cache_plan["cached_slice_count"],
                        uncovered_slice_count=uncovered_count,
                        min_uncovered_slices_for_judge=min_uncovered,
                    )
                rounds.append(round_summary)
                break

        if event_logger is not None:
            event_logger.emit(
                "judge_start",
                emperor_name=emperor_name,
                target_code=target_code,
                rule_code=rule_code,
                round=round_index,
                judge_shard_size=judge_shard_size,
                judge_shard_workers=judge_shard_workers,
                judge_mode=judge_mode,
            )
        judge_result = run_judge(
            candidates=judge_candidates,
            prompt_path=candidate_result["prompt_path"],
            person_dir=person_dir,
            round_index=round_index,
            codex_runner=codex_runner,
            codex_bin=codex_bin,
            timeout_seconds=judge_timeout_seconds,
            judge_shard_size=judge_shard_size,
            judge_shard_workers=judge_shard_workers,
            judge_mode=judge_mode,
        )
        final_judge = dict(judge_result["payload"])
        final_judge["_elapsed_seconds"] = judge_result["elapsed_seconds"]
        final_judge["_usage"] = judge_result["usage"]
        final_judge["_judge_mode"] = judge_mode or ""
        if claim_cache_plan is not None:
            final_judge["_claim_cache_plan"] = claim_cache_plan
        round_summary["judge_elapsed_seconds"] = judge_result["elapsed_seconds"]
        round_summary["judge_status"] = final_judge.get("status")
        round_summary["judge_sharded"] = bool(judge_result.get("sharded"))
        round_summary["judge_shard_count"] = int(judge_result.get("shard_count") or 0)
        if event_logger is not None:
            event_logger.emit(
                "judge_done",
                emperor_name=emperor_name,
                target_code=target_code,
                rule_code=rule_code,
                round=round_index,
                elapsed_seconds_stage=judge_result["elapsed_seconds"],
                status=final_judge.get("status"),
                judge_sharded=bool(judge_result.get("sharded")),
                judge_shard_count=int(judge_result.get("shard_count") or 0),
                claim_count=len(final_judge.get("claims") or []),
                coverage_gap_count=len(final_judge.get("coverage_gaps") or []),
                input_tokens=judge_result["usage"].get("input_tokens"),
                output_tokens=judge_result["usage"].get("output_tokens"),
            )

        judge_refinement = build_alias_refinement_round(
            task_path=task_path,
            task=current_task,
            candidates=final_candidates,
            judge_result=final_judge,
            person_dir=person_dir,
            round_index=round_index,
            stage="judge",
        )
        judge_patch_stats = judge_refinement["payload"]["stats"]
        round_summary["judge_alias_patch_stats"] = judge_patch_stats
        round_summary["judge_alias_patch"] = str(judge_refinement["output_path"])
        round_summary["judge_alias_prompt"] = str(judge_refinement["prompt_path"]) if judge_refinement["prompt_path"] else None
        if judge_patch_stats["apply_alias_patch_count"]:
            if alias_refine_count >= max_alias_refine_rounds:
                alias_round_limit_reached = True
                rounds.append(round_summary)
                break
            alias_refine_count += 1
            current_task = alias_refiner.apply_alias_patches(current_task, judge_refinement["payload"]["patches"])
            task_path = person_dir / f"task.round{round_index + 1}.json"
            atomic_write_json(task_path, current_task)
            rounds.append(round_summary)
            continue
        judge_gap_names = candidate_source_refiner.judge_gap_object_names(final_judge)
        if final_judge.get("status") == "needs_refinement" and judge_gap_names and source_refine_count < candidate_source_refine_rounds:
            source_stats, source_refine_path, refined = apply_source_refine("judge", final_judge, judge_gap_names, round_index)
            round_summary["candidate_source_refine_stats"] = source_stats
            round_summary["candidate_source_refine_task"] = str(source_refine_path)
            if refined:
                rounds.append(round_summary)
                continue
        rounds.append(round_summary)
        break

    atomic_write_json(person_dir / "task.final.json", current_task)
    if final_candidates:
        atomic_write_json(person_dir / "candidates.final.json", final_candidates)
    if final_judge:
        atomic_write_json(person_dir / "judge_result.final.json", final_judge)
    person_summary = summarize_person(
        task=current_task,
        person_dir=person_dir,
        rounds=rounds,
        taskgen=taskgen,
        final_candidates=final_candidates,
        final_judge=final_judge,
        alias_round_limit_reached=alias_round_limit_reached,
    )
    if event_logger is not None:
        event_logger.emit(
            "target_done",
            emperor_name=emperor_name,
            target_code=target_code,
            rule_code=rule_code,
            candidate_slices=person_summary.get("candidate_slices"),
            claim_count=person_summary.get("claim_count"),
            judge_coverage_gap_count=person_summary.get("judge_coverage_gap_count"),
        )
    return person_summary


def run_clean_pipeline(
    *,
    tasks: Sequence[Mapping[str, Any]],
    run_root: Path,
    codex_runner: CodexRunner = run_codex,
    codex_bin: str = "codex",
    skip_judge: bool = False,
    max_alias_refine_rounds: int = 2,
    candidate_source_refine_rounds: int = 0,
    candidate_source_refine_max_objects: int = 8,
    candidate_source_refine_pages_per_object: int = 2,
    candidate_source_refine_source_hint_limit: int = 2,
    candidate_timeout: int = 15,
    context_chars: int = 260,
    max_slices_per_object: int = 8,
    skip_fetch_errors: bool = False,
    source_cache_root: Path | None = source_candidates.DEFAULT_CACHE_DIR,
    object_source_cache_root: Path | None = None,
    judge_timeout_seconds: int = 1800, judge_shard_size: int = 8, judge_shard_workers: int = 2,
    judge_mode: str | None = None,
    claim_cache_root: Path | None = None,
    claim_cache_skip_cached_slices: bool = False,
    claim_cache_min_uncovered_slices_for_judge: int = 1,
    claim_cache_import_final: bool = False,
    taskgen_by_target_code: Mapping[str, Mapping[str, Any]] | None = None,
    max_workers: int = 4, event_logger: RunEventLogger | None = None, candidate_source_refine_objects: Sequence[str] = (),
) -> dict[str, Any]:
    started = time.perf_counter()
    run_root.mkdir(parents=True, exist_ok=True)
    taskgen_by_target_code = taskgen_by_target_code or {}
    if event_logger is not None:
        event_logger.emit(
            "pipeline_start",
            target_count=len(tasks),
            max_workers=max_workers,
            mode="task_list",
        )

    def run_one(task: Mapping[str, Any]) -> dict[str, Any]:
        target_code = str(task.get("target_code") or "")
        return process_task(
            task=task,
            run_root=run_root,
            codex_runner=codex_runner,
            codex_bin=codex_bin,
            skip_judge=skip_judge,
            max_alias_refine_rounds=max_alias_refine_rounds,
            candidate_source_refine_rounds=candidate_source_refine_rounds,
            candidate_source_refine_max_objects=candidate_source_refine_max_objects,
            candidate_source_refine_pages_per_object=candidate_source_refine_pages_per_object,
            candidate_source_refine_source_hint_limit=candidate_source_refine_source_hint_limit,
            candidate_timeout=candidate_timeout,
            context_chars=context_chars,
            max_slices_per_object=max_slices_per_object,
            skip_fetch_errors=skip_fetch_errors,
            source_cache_root=source_cache_root,
            object_source_cache_root=object_source_cache_root,
            judge_timeout_seconds=judge_timeout_seconds,
            judge_shard_size=judge_shard_size,
            judge_shard_workers=judge_shard_workers,
            judge_mode=judge_mode,
            claim_cache_root=claim_cache_root,
            claim_cache_skip_cached_slices=claim_cache_skip_cached_slices,
            claim_cache_min_uncovered_slices_for_judge=claim_cache_min_uncovered_slices_for_judge,
            taskgen=taskgen_by_target_code.get(target_code),
            event_logger=event_logger,
            candidate_source_refine_objects=candidate_source_refine_objects,
        )

    workers = max(1, min(max_workers, len(tasks) or 1))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        people = list(pool.map(run_one, tasks))
    elapsed = round(time.perf_counter() - started, 3)
    summary = build_batch_summary(
        people=people,
        run_root=run_root,
        elapsed_seconds=elapsed,
        max_alias_refine_rounds=max_alias_refine_rounds,
        candidate_source_refine_rounds=candidate_source_refine_rounds,
        candidate_source_refine_max_objects=candidate_source_refine_max_objects,
        candidate_source_refine_pages_per_object=candidate_source_refine_pages_per_object,
        judge_shard_size=judge_shard_size,
        judge_shard_workers=judge_shard_workers,
        source_cache_root=source_cache_root,
        taskgen_streaming=False,
        taskgen_batch_size=1,
    )
    summary.setdefault("clean_policy", {})["judge_mode"] = judge_mode or "full"
    if claim_cache_root is not None:
        summary.setdefault("clean_policy", {})["claim_cache_root"] = str(claim_cache_root)
        summary.setdefault("clean_policy", {})["claim_cache_skip_cached_slices"] = bool(claim_cache_skip_cached_slices)
        summary.setdefault("clean_policy", {})["claim_cache_min_uncovered_slices_for_judge"] = int(claim_cache_min_uncovered_slices_for_judge)
        summary.setdefault("clean_policy", {})["claim_cache_import_final"] = bool(claim_cache_import_final)
    atomic_write_json(run_root / "summary.json", summary)
    if claim_cache_root is not None and claim_cache_import_final:
        import_report = claim_cache.import_run(run_root, claim_cache_root)
        summary["claim_cache_import"] = import_report
        atomic_write_json(run_root / "summary.json", summary)
    if event_logger is not None:
        event_logger.emit(
            "pipeline_done",
            target_count=len(people),
            elapsed_seconds_stage=elapsed,
            candidate_slices=summary["totals"]["candidate_slices"],
            claim_count=summary["totals"]["claim_count"],
            judge_coverage_gap_count=summary["totals"]["judge_coverage_gap_count"],
        )
    return summary


def run_streaming_taskgen_pipeline(**kwargs: Any) -> dict[str, Any]:
    from scripts.dev.retrieval_v2_clean_cli import run_streaming_taskgen_pipeline as cli_streaming
    return cli_streaming(**kwargs)


def main(argv: Sequence[str] | None = None) -> int:
    from scripts.dev.retrieval_v2_clean_cli import main as cli_main
    return cli_main(argv)


if __name__ == "__main__":  # pragma: no cover
    try:
        raise SystemExit(main())
    except RetrievalV2CleanRunnerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
