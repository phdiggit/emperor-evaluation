from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_RUNTIME_PATHS_CONFIG = Path(
    r"\\192.168.1.37\data1\emperor-evaluation\runtime\handoff\latest\runtime_paths.json"
)
ENV_RUNTIME_PATHS_JSON = "EMPEROR_EVAL_RUNTIME_PATHS_JSON"
ENV_ACTIVE_ROOT = "EMPEROR_EVAL_RUNTIME_ACTIVE_ROOT"
ENV_ARCHIVE_ROOT = "EMPEROR_EVAL_RUNTIME_ARCHIVE_ROOT"


class RuntimePathError(RuntimeError):
    pass


def _clean_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _path_from(value: Any) -> Path | None:
    text = _clean_text(value)
    return Path(text) if text else None


def _local_paths() -> dict[str, Any]:
    active_root = ROOT / "tmp"
    return {
        "uses_runtime_config": False,
        "config_source": "local_fallback",
        "active_root": active_root,
        "archive_root": ROOT / ".tmp" / "runtime-archive",
        "retrieval_v2_clean_runs": active_root / "retrieval_v2_clean_runs",
        "retrieval_v2_consumption": active_root / "retrieval_v2_consumption",
        "retrieval_v2_feedback": active_root / "retrieval_v2_feedback",
        "retrieval_v2_reports": active_root / "retrieval_v2_reports",
        "source_cache": active_root / "retrieval_v2_source_cache",
    }


def _paths_from_config(payload: Mapping[str, Any], *, config_source: str) -> dict[str, Any]:
    active_root = _path_from(payload.get("active_root_smb") or payload.get("active_root"))
    if active_root is None:
        raise RuntimePathError(f"{config_source}: missing active_root_smb or active_root")
    archive_root = _path_from(payload.get("archive_root_smb") or payload.get("archive_root")) or active_root / "archive"
    return {
        "uses_runtime_config": True,
        "config_source": config_source,
        "active_root": active_root,
        "archive_root": archive_root,
        "retrieval_v2_clean_runs": _path_from(payload.get("retrieval_v2_clean_runs"))
        or active_root
        / "retrieval_v2_clean_runs",
        "retrieval_v2_consumption": _path_from(payload.get("retrieval_v2_consumption"))
        or active_root
        / "retrieval_v2_consumption",
        "retrieval_v2_feedback": _path_from(payload.get("retrieval_v2_feedback")) or active_root / "retrieval_v2_feedback",
        "retrieval_v2_reports": _path_from(payload.get("retrieval_v2_reports")) or active_root / "retrieval_v2_reports",
        "source_cache": _path_from(payload.get("source_cache")) or active_root / "source_cache",
    }


def load_runtime_paths(
    *,
    config_path: Path | None = None,
    use_local: bool = False,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if use_local:
        return _local_paths()
    environ = os.environ if env is None else env
    if config_path is not None and not config_path.exists():
        raise RuntimePathError(f"{config_path}: runtime paths config does not exist")
    env_config = _path_from(environ.get(ENV_RUNTIME_PATHS_JSON))
    candidates = [path for path in [config_path, env_config, DEFAULT_RUNTIME_PATHS_CONFIG] if path is not None]
    for path in candidates:
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, Mapping):
                raise RuntimePathError(f"{path}: expected JSON object")
            return _paths_from_config(payload, config_source=str(path))
    active_root = _path_from(environ.get(ENV_ACTIVE_ROOT))
    if active_root is not None:
        archive_root = _path_from(environ.get(ENV_ARCHIVE_ROOT)) or active_root / "archive"
        return _paths_from_config(
            {"active_root": str(active_root), "archive_root": str(archive_root)},
            config_source=f"env:{ENV_ACTIVE_ROOT}",
        )
    return _local_paths()


def sanitize_run_name(name: str) -> str:
    safe = re.sub(r"[^0-9A-Za-z._-]+", "_", name.strip())
    safe = safe.strip("._-")
    if not safe:
        raise RuntimePathError("run name must contain at least one safe character")
    return safe[:120]


def default_run_root(name: str, paths: Mapping[str, Any] | None = None) -> Path:
    resolved = load_runtime_paths() if paths is None else paths
    return Path(resolved["retrieval_v2_clean_runs"]) / sanitize_run_name(name)


def default_consumption_root(name: str, paths: Mapping[str, Any] | None = None) -> Path:
    resolved = load_runtime_paths() if paths is None else paths
    return Path(resolved["retrieval_v2_consumption"]) / sanitize_run_name(name)


def default_source_cache_root(paths: Mapping[str, Any] | None = None) -> Path:
    resolved = load_runtime_paths() if paths is None else paths
    return Path(resolved["source_cache"])


def report_payload(name: str, paths: Mapping[str, Any]) -> dict[str, str | bool]:
    safe_name = sanitize_run_name(name)
    return {
        "name": safe_name,
        "uses_runtime_config": bool(paths["uses_runtime_config"]),
        "config_source": str(paths["config_source"]),
        "active_root": str(paths["active_root"]),
        "archive_root": str(paths["archive_root"]),
        "run_root": str(default_run_root(safe_name, paths)),
        "output_root": str(default_consumption_root(safe_name, paths)),
        "source_cache_root": str(default_source_cache_root(paths)),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve retrieval_v2 runtime asset paths.")
    parser.add_argument("--config", type=Path, help="runtime_paths.json override.")
    parser.add_argument("--use-local-runtime", action="store_true", help="Force repo-local tmp/.tmp fallback paths.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    new_run = subparsers.add_parser("new-run", help="Print standard paths for a new retrieval_v2 run.")
    new_run.add_argument("name", help="Run or package name.")
    new_run.add_argument("--json", action="store_true", help="Print JSON instead of key=value lines.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = load_runtime_paths(config_path=args.config, use_local=args.use_local_runtime)
    if args.command == "new-run":
        payload = report_payload(args.name, paths)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            for key in sorted(payload):
                print(f"{key}={payload[key]}")
        return 0
    raise RuntimePathError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
