from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def git_output_lines(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=ROOT,
        capture_output=True,
        text=False,
        check=True,
    )
    return result.stdout.decode("utf-8").splitlines()


def normalize_repo_path(path: str) -> str:
    return path.strip().replace("\\", "/")


def git_changed_files(*args: str, ignore_prefixes: tuple[str, ...] = (".tmp/",)) -> set[str]:
    paths = {
        normalize_repo_path(line)
        for line in git_output_lines(*args)
        if line.strip()
    }
    return {
        path
        for path in paths
        if not any(path.startswith(prefix) for prefix in ignore_prefixes)
    }


def changed_files_against_base(base: str = "origin/GPT...HEAD") -> set[str]:
    return git_changed_files("diff", "--name-only", base)

