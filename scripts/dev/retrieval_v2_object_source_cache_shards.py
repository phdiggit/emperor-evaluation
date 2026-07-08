from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


RunFn = Callable[..., subprocess.CompletedProcess[str]]


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    write_text(path, json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, indent=2, default=str) + "\n")


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    write_text(path, "".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True, default=str) + "\n" for row in rows))


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected JSON object")
    return payload


def read_jsonl_if_exists(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def shard_ranges(total: int, shard_size: int, *, max_shards: int = 0) -> list[tuple[int, int, int]]:
    if shard_size <= 0:
        raise ValueError("shard_size must be positive")
    ranges: list[tuple[int, int, int]] = []
    index = 1
    for start in range(0, total, shard_size):
        if max_shards > 0 and len(ranges) >= max_shards:
            break
        end = min(start + shard_size, total)
        ranges.append((index, start, end))
        index += 1
    return ranges


def shard_name(index: int, start: int, end: int) -> str:
    return f"shard_{index:04d}_{start + 1:05d}_{end:05d}"


def parse_manifest_from_stdout(stdout: str) -> dict[str, Any]:
    for line in reversed(stdout.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, Mapping) and isinstance(payload.get("manifest"), Mapping):
            return dict(payload["manifest"])
    return {}


def load_shard_manifest(shard_root: Path, stdout: str = "") -> dict[str, Any]:
    manifest_path = shard_root / "manifest.json"
    if manifest_path.exists():
        return read_json(manifest_path)
    return parse_manifest_from_stdout(stdout)


def merge_shard_jsonl(shard_rows: Sequence[Mapping[str, Any]], *, file_name: str, output_path: Path) -> int:
    rows: list[dict[str, Any]] = []
    for shard in shard_rows:
        if shard.get("status") not in {"completed", "skipped_completed"}:
            continue
        shard_root = Path(str(shard.get("output_root") or ""))
        if not shard_root:
            continue
        rows.extend(read_jsonl_if_exists(shard_root / file_name))
    write_jsonl(output_path, rows)
    return len(rows)


def render_shard_report(summary: Mapping[str, Any]) -> str:
    totals = summary.get("totals") if isinstance(summary.get("totals"), Mapping) else {}
    lines = [
        "# retrieval_v2 object source cache shard build",
        "",
        "## Summary",
        "",
        f"- seed_rows: `{totals.get('seed_rows', 0)}`",
        f"- shard_count: `{totals.get('shard_count', 0)}`",
        f"- completed: `{totals.get('completed', 0)}`",
        f"- skipped_completed: `{totals.get('skipped_completed', 0)}`",
        f"- failed: `{totals.get('failed', 0)}`",
        f"- timed_out: `{totals.get('timed_out', 0)}`",
        f"- persons: `{totals.get('persons', 0)}`",
        f"- source_documents: `{totals.get('source_documents', 0)}`",
        f"- mention_slices: `{totals.get('mention_slices', 0)}`",
        f"- coverage_needs_agent_review: `{totals.get('coverage_needs_agent_review', 0)}`",
        f"- fetch_errors: `{totals.get('fetch_errors', 0)}`",
        f"- elapsed_seconds: `{totals.get('elapsed_seconds', 0)}`",
        "",
        "## Shards",
        "",
        "| shard | status | rows | elapsed | notes |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for shard in summary.get("shards") or []:
        if not isinstance(shard, Mapping):
            continue
        notes = shard.get("error") or shard.get("stderr_tail") or ""
        lines.append(
            f"| {shard.get('shard')} | {shard.get('status')} | {shard.get('seed_rows', 0)} | "
            f"{shard.get('elapsed_seconds', 0)} | {str(notes).replace('|', '/')} |"
        )
    return "\n".join(lines) + "\n"


def write_progress(output_root: Path, shard_rows: Sequence[Mapping[str, Any]]) -> None:
    write_json(output_root / "shard_progress.json", {"shards": list(shard_rows)})
    write_jsonl(output_root / "shard_progress.jsonl", shard_rows)


def run_build_shards(
    seeds: Sequence[Mapping[str, Any]],
    *,
    output_root: Path,
    cache_dir: Path,
    build_cli_args: Sequence[str],
    shard_size: int = 20,
    shard_timeout: float = 120.0,
    max_shards: int = 0,
    skip_completed: bool = True,
    python_executable: str | None = None,
    script_path: Path | None = None,
    run_fn: RunFn = subprocess.run,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    seed_root = output_root / "seeds"
    shard_root = output_root / "shards"
    seed_root.mkdir(parents=True, exist_ok=True)
    shard_root.mkdir(parents=True, exist_ok=True)
    py = python_executable or sys.executable
    script = script_path or Path(__file__).with_name("retrieval_v2_object_source_cache.py")
    shard_rows: list[dict[str, Any]] = []

    for index, start, end in shard_ranges(len(seeds), shard_size, max_shards=max_shards):
        name = shard_name(index, start, end)
        shard_seeds = [dict(row) for row in seeds[start:end]]
        shard_seed_path = seed_root / f"{name}.jsonl"
        current_output_root = shard_root / name
        write_jsonl(shard_seed_path, shard_seeds)
        manifest_path = current_output_root / "manifest.json"
        if skip_completed and manifest_path.exists():
            manifest = read_json(manifest_path)
            shard_rows.append(
                {
                    "shard": name,
                    "status": "skipped_completed",
                    "seed_rows": len(shard_seeds),
                    "seed_jsonl": str(shard_seed_path),
                    "output_root": str(current_output_root),
                    "manifest": manifest,
                    "elapsed_seconds": manifest.get("totals", {}).get("elapsed_seconds", 0),
                }
            )
            write_progress(output_root, shard_rows)
            continue
        cmd = [
            py,
            str(script),
            "build",
            "--seed-jsonl",
            str(shard_seed_path),
            "--output-root",
            str(current_output_root),
            "--cache-dir",
            str(cache_dir),
            *build_cli_args,
        ]
        try:
            completed = run_fn(cmd, text=True, capture_output=True, check=False, timeout=shard_timeout)
        except subprocess.TimeoutExpired as exc:
            shard_rows.append(
                {
                    "shard": name,
                    "status": "timed_out",
                    "seed_rows": len(shard_seeds),
                    "seed_jsonl": str(shard_seed_path),
                    "output_root": str(current_output_root),
                    "timeout_seconds": shard_timeout,
                    "stdout_tail": (exc.stdout or "")[-2000:] if isinstance(exc.stdout, str) else "",
                    "stderr_tail": (exc.stderr or "")[-2000:] if isinstance(exc.stderr, str) else "",
                }
            )
            write_progress(output_root, shard_rows)
            continue
        manifest = load_shard_manifest(current_output_root, completed.stdout or "")
        status = "completed" if completed.returncode == 0 else "failed"
        shard_rows.append(
            {
                "shard": name,
                "status": status,
                "seed_rows": len(shard_seeds),
                "seed_jsonl": str(shard_seed_path),
                "output_root": str(current_output_root),
                "returncode": completed.returncode,
                "manifest": manifest,
                "elapsed_seconds": manifest.get("totals", {}).get("elapsed_seconds", 0) if manifest else 0,
                "stdout_tail": "" if status == "completed" else (completed.stdout or "")[-2000:],
                "stderr_tail": "" if status == "completed" else (completed.stderr or "")[-2000:],
            }
        )
        write_progress(output_root, shard_rows)

    totals = {
        "seed_rows": sum(int(row.get("seed_rows") or 0) for row in shard_rows),
        "shard_count": len(shard_rows),
        "completed": sum(1 for row in shard_rows if row.get("status") == "completed"),
        "skipped_completed": sum(1 for row in shard_rows if row.get("status") == "skipped_completed"),
        "failed": sum(1 for row in shard_rows if row.get("status") == "failed"),
        "timed_out": sum(1 for row in shard_rows if row.get("status") == "timed_out"),
        "persons": 0,
        "source_documents": 0,
        "mention_slices": 0,
        "coverage_needs_agent_review": 0,
        "search_hits": 0,
        "fetch_errors": 0,
        "elapsed_seconds": 0.0,
    }
    for row in shard_rows:
        manifest = row.get("manifest") if isinstance(row.get("manifest"), Mapping) else {}
        manifest_totals = manifest.get("totals") if isinstance(manifest.get("totals"), Mapping) else {}
        for key in ("persons", "source_documents", "mention_slices", "coverage_needs_agent_review", "search_hits", "fetch_errors"):
            totals[key] += int(manifest_totals.get(key) or 0)
        totals["elapsed_seconds"] = round(float(totals["elapsed_seconds"]) + float(manifest_totals.get("elapsed_seconds") or 0), 3)

    artifacts = {
        "summary_json": output_root / "shard_summary.json",
        "summary_jsonl": output_root / "shard_summary.jsonl",
        "report": output_root / "shard_report.md",
        "person_coverage": output_root / "person_coverage.jsonl",
        "source_documents": output_root / "source_documents.jsonl",
        "mention_slices": output_root / "mention_slices.jsonl",
        "agent_review_queue": output_root / "agent_review_queue.jsonl",
        "fetch_errors": output_root / "fetch_errors.jsonl",
    }
    merged_counts = {
        "person_coverage": merge_shard_jsonl(shard_rows, file_name="person_coverage.jsonl", output_path=artifacts["person_coverage"]),
        "source_documents": merge_shard_jsonl(shard_rows, file_name="source_documents.jsonl", output_path=artifacts["source_documents"]),
        "mention_slices": merge_shard_jsonl(shard_rows, file_name="mention_slices.jsonl", output_path=artifacts["mention_slices"]),
        "agent_review_queue": merge_shard_jsonl(shard_rows, file_name="agent_review_queue.jsonl", output_path=artifacts["agent_review_queue"]),
        "fetch_errors": merge_shard_jsonl(shard_rows, file_name="fetch_errors.jsonl", output_path=artifacts["fetch_errors"]),
    }
    summary = {
        "generated_by": "scripts/dev/retrieval_v2_object_source_cache_shards.py",
        "mode": "offline_no_agent_sharded",
        "write_db": False,
        "agent_invocation_enabled": False,
        "output_root": str(output_root),
        "cache_dir": str(cache_dir),
        "shard_size": shard_size,
        "shard_timeout_seconds": shard_timeout,
        "max_shards": max_shards,
        "skip_completed": skip_completed,
        "build_cli_args": list(build_cli_args),
        "totals": totals,
        "merged_counts": merged_counts,
        "artifacts": {key: str(path) for key, path in artifacts.items()},
        "shards": shard_rows,
    }
    write_json(artifacts["summary_json"], summary)
    write_jsonl(artifacts["summary_jsonl"], shard_rows)
    write_text(artifacts["report"], render_shard_report(summary))
    return summary
