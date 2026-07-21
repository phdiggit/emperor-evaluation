from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence
from uuid import uuid4

import yaml

from emperor_v4.adapters.source_text_index import LocalSourceTextIndex
from emperor_v4.runtime.dynasty_governance_rebuild import (
    DynastyGovernanceLimits,
    rebuild_dynasty_governance,
)


SCHEMA_VERSION = "dynasty-governance-worker-tick-v1"


def _atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def _configured_dynasties(workspace_root: Path) -> Mapping[str, Mapping[str, Any]]:
    project = yaml.safe_load(
        (workspace_root / "config/project.yml").read_text(encoding="utf-8")
    )
    rows = (project.get("dynasty_governance_scans") or {}).get("dynasties") or {}
    if not isinstance(rows, Mapping) or not rows:
        raise ValueError("未配置朝代政书扫描")
    return rows


def _configured_works(configured: Mapping[str, Any]) -> tuple[str, ...]:
    works = tuple(
        dict.fromkeys(
            str(row.get("work") or "").strip()
            for row in configured.get("source_works") or ()
            if isinstance(row, Mapping) and str(row.get("work") or "").strip()
        )
    )
    if not works:
        raise ValueError("朝代政书配置没有有效 work")
    return works


def discover_source_index(
    source_index_root: Path, *, works: Sequence[str]
) -> LocalSourceTextIndex | None:
    candidates: list[tuple[int, str, LocalSourceTextIndex]] = []
    for path in sorted(source_index_root.rglob("*.sqlite3")):
        try:
            index = LocalSourceTextIndex(path)
            counts = [sum(1 for _ in index.iter_pages(works=(work,))) for work in works]
        except (OSError, ValueError):
            continue
        if all(count > 0 for count in counts):
            candidates.append((sum(counts), str(path.resolve()), index))
    return max(candidates, key=lambda row: (row[0], row[1]))[2] if candidates else None


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[bool]:
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("a+b")
    locked = False
    try:
        if os.name == "nt":
            import msvcrt

            stream.seek(0)
            if stream.tell() == 0 and path.stat().st_size == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                locked = True
            except OSError:
                locked = False
        else:
            import fcntl

            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
            except BlockingIOError:
                locked = False
        yield locked
    finally:
        if locked:
            if os.name == "nt":
                import msvcrt

                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()


def run_worker_once(
    *,
    source_index_root: Path,
    runtime_root: Path,
    workspace_root: Path,
    codex_bin: str,
    limits: DynastyGovernanceLimits,
) -> dict[str, object]:
    workspace_root = workspace_root.resolve()
    rows = []
    failures = []
    for dynasty, configured in _configured_dynasties(workspace_root).items():
        token = str(configured.get("dynasty_token") or "").strip()
        if not token:
            failures.append({"dynasty": str(dynasty), "error": "缺少 dynasty_token"})
            continue
        works = _configured_works(configured)
        index = discover_source_index(source_index_root, works=works)
        if index is None:
            rows.append(
                {
                    "dynasty": str(dynasty),
                    "dynasty_token": token,
                    "status": "waiting_for_source_index",
                    "works": list(works),
                    "model_call_count": 0,
                    "business_write_count": 0,
                }
            )
            continue
        lock_path = runtime_root / ".locks" / f"{token}.lock"
        with _exclusive_lock(lock_path) as locked:
            if not locked:
                rows.append(
                    {
                        "dynasty": str(dynasty),
                        "dynasty_token": token,
                        "status": "already_running",
                        "model_call_count": 0,
                        "business_write_count": 0,
                    }
                )
                continue
            try:
                result = rebuild_dynasty_governance(
                    dynasty=str(dynasty),
                    source_index_path=index.path,
                    runtime_root=runtime_root,
                    workspace_root=workspace_root,
                    limits=limits,
                    codex_bin=codex_bin,
                )
            except Exception as exc:
                failures.append({"dynasty": str(dynasty), "error": str(exc)})
                continue
        rows.append(
            {
                "dynasty": str(dynasty),
                "dynasty_token": token,
                "status": "reused" if result.get("reused") else "quality_accepted",
                "source_index": str(index.path),
                "source_index_identity": index.identity,
                "model_call_count": int(result.get("model_call_count") or 0),
                "business_write_count": int(result.get("business_write_count") or 0),
                "chain_count": int((result.get("quality") or {}).get("chain_count") or 0),
            }
        )
    status = "failed_closed" if failures else (
        "noop" if all(row["model_call_count"] == 0 for row in rows) else "succeeded"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "dynasty_count": len(rows) + len(failures),
        "model_call_count": sum(int(row["model_call_count"]) for row in rows),
        "business_write_count": 0,
        "dynasties": rows,
        "failures": failures,
        "formal_writes": 0,
        "score_writes": 0,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="朝代政书中性材料后台单次 worker")
    parser.add_argument("--source-index-root", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--workspace-root", type=Path, default=Path.cwd())
    parser.add_argument("--codex-bin", required=True)
    parser.add_argument("--model-workers", type=int, default=4)
    parser.add_argument("--model-timeout-seconds", type=int, default=120)
    parser.add_argument("--target-chars", type=int, default=2_400)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = run_worker_once(
        source_index_root=args.source_index_root,
        runtime_root=args.runtime_root,
        workspace_root=args.workspace_root,
        codex_bin=args.codex_bin,
        limits=DynastyGovernanceLimits(
            model_workers=args.model_workers,
            model_timeout_seconds=args.model_timeout_seconds,
            target_chars=args.target_chars,
        ),
    )
    _atomic_json(args.output, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 1 if report["status"] == "failed_closed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
