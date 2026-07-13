from __future__ import annotations

import argparse
from hashlib import sha256
import io
import json
from pathlib import Path
import subprocess
import tarfile
from typing import Any, Iterable, Sequence


RELEASE_CONTRACT = "emperor-v4-service-release-v1"
SOURCE_CACHE_RELEASE_PATHS = (
    "pyproject.toml",
    "src/emperor_v4/__init__.py",
    "src/emperor_v4/adapters/source_cache_fixture.py",
    "src/emperor_v4/adapters/source_cache_plan.py",
    "src/emperor_v4/adapters/source_cache_wikisource.py",
    "src/emperor_v4/adapters/wikisource.py",
    "src/emperor_v4/application/source_cache_service.py",
    "src/emperor_v4/application/source_cache_worker.py",
    "src/emperor_v4/contracts/source.py",
    "src/emperor_v4/domain/source_segmentation.py",
    "src/emperor_v4/persistence/postgres_source_cache.py",
    "src/emperor_v4/persistence/source_cache.py",
    "src/emperor_v4/persistence/source_cache_jobs.py",
    "src/emperor_v4/runtime/release.py",
    "src/emperor_v4/runtime/source_cache.py",
    "src/emperor_v4/runtime/source_cache_worker.py",
    "db/postgres/002_v4_source_cache_service.sql",
    "db/postgres/003_v4_source_cache_jobs.sql",
    "deploy/v4",
)


def _sha256(data: bytes) -> str:
    return sha256(data).hexdigest()


def _git(repo_root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=repo_root, text=True, encoding="utf-8"
    ).strip()


def _files(repo_root: Path, paths: Iterable[str]) -> tuple[Path, ...]:
    files: list[Path] = []
    for name in paths:
        path = repo_root / name
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(item for item in path.rglob("*") if item.is_file() and "__pycache__" not in item.parts)
        else:
            raise FileNotFoundError(f"release allowlist 路径不存在: {name}")
    return tuple(sorted(set(files), key=lambda item: item.relative_to(repo_root).as_posix()))


def build_source_cache_release(
    *, repo_root: Path, output_dir: Path, commit_sha: str,
    require_clean: bool = True,
) -> dict[str, Any]:
    actual_sha = _git(repo_root, "rev-parse", "HEAD")
    if commit_sha != actual_sha or len(commit_sha) != 40:
        raise ValueError("release commit_sha 必须等于当前 HEAD")
    if require_clean and _git(repo_root, "status", "--short"):
        raise RuntimeError("不可变 release 只能从干净工作树构建")
    files = _files(repo_root, SOURCE_CACHE_RELEASE_PATHS)
    entries = []
    for path in files:
        data = path.read_bytes()
        entries.append({
            "path": path.relative_to(repo_root).as_posix(),
            "size": len(data), "sha256": _sha256(data),
        })
    embedded = {
        "contract": RELEASE_CONTRACT,
        "service": "v4-source-cache",
        "commit_sha": commit_sha,
        "files": entries,
    }
    release_json = (json.dumps(embedded, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / f"v4-source-cache-{commit_sha}.tar"
    with tarfile.open(archive_path, "w", format=tarfile.PAX_FORMAT) as archive:
        for path in files:
            data = path.read_bytes()
            info = tarfile.TarInfo(path.relative_to(repo_root).as_posix())
            info.size = len(data)
            info.mode = 0o755 if path.suffix in {".sh"} else 0o644
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            archive.addfile(info, io.BytesIO(data))
        info = tarfile.TarInfo("RELEASE.json")
        info.size = len(release_json)
        info.mode = 0o644
        info.mtime = 0
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        archive.addfile(info, io.BytesIO(release_json))
    manifest = dict(embedded)
    manifest["archive"] = archive_path.name
    manifest["archive_sha256"] = _sha256(archive_path.read_bytes())
    manifest_path = output_dir / f"v4-source-cache-{commit_sha}.manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    return manifest


def verify_source_cache_release(*, archive_path: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if _sha256(archive_path.read_bytes()) != manifest["archive_sha256"]:
        raise ValueError("release archive SHA-256 不匹配")
    expected = {item["path"]: item for item in manifest["files"]}
    with tarfile.open(archive_path, "r") as archive:
        names = {member.name for member in archive.getmembers()}
        if names != set(expected) | {"RELEASE.json"}:
            raise ValueError("release archive 文件集合越出 allowlist")
        for name, item in expected.items():
            stream = archive.extractfile(name)
            if stream is None or _sha256(stream.read()) != item["sha256"]:
                raise ValueError(f"release 文件 hash 不匹配: {name}")
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="构建或验证 V4 Source Cache 不可变发布包")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--repo-root", type=Path, default=Path.cwd())
    build.add_argument("--output-dir", type=Path, required=True)
    build.add_argument("--commit-sha", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--archive", type=Path, required=True)
    verify.add_argument("--manifest", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = (
        build_source_cache_release(
            repo_root=args.repo_root, output_dir=args.output_dir,
            commit_sha=args.commit_sha,
        )
        if args.command == "build"
        else verify_source_cache_release(archive_path=args.archive, manifest_path=args.manifest)
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
