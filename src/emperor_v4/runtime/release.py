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
    "config/i5b-source-search-scope.yml",
    "config/project.yml",
    "config/workflow-source-cache.yml",
    "config/workflow-source-cache-request.schema.json",
    "config/dynasty-neutral-governance-output.schema.json",
    "config/dynasty-neutral-material-atomization-output.schema.json",
    "config/dynasty-neutral-source-increment-output.schema.json",
    "src/emperor_v4/__init__.py",
    "src/emperor_v4/adapters/dynasty_neutral_governance.py",
    "src/emperor_v4/adapters/dynasty_neutral_material_atomization.py",
    "src/emperor_v4/adapters/dynasty_neutral_material_settlement.py",
    "src/emperor_v4/adapters/dynasty_neutral_source_increment.py",
    "src/emperor_v4/adapters/source_cache_fixture.py",
    "src/emperor_v4/adapters/source_cache_plan.py",
    "src/emperor_v4/adapters/source_cache_wikisource.py",
    "src/emperor_v4/adapters/shidian.py",
    "src/emperor_v4/adapters/source_text_index.py",
    "src/emperor_v4/adapters/structured_output_contract.py",
    "src/emperor_v4/adapters/wikisource.py",
    "src/emperor_v4/application/source_cache_service.py",
    "src/emperor_v4/application/source_cache_worker.py",
    "src/emperor_v4/contracts/source.py",
    "src/emperor_v4/domain/source_segmentation.py",
    "src/emperor_v4/persistence/postgres_source_cache.py",
    "src/emperor_v4/persistence/canonical_refs.py",
    "src/emperor_v4/persistence/source_cache.py",
    "src/emperor_v4/persistence/source_cache_jobs.py",
    "src/emperor_v4/runtime/release.py",
    "src/emperor_v4/runtime/source_cache.py",
    "src/emperor_v4/runtime/source_cache_worker.py",
    "src/emperor_v4/runtime/workflow_source_cache.py",
    "src/emperor_v4/runtime/workflow_source_cache_import.py",
    "db/postgres/002_v4_source_cache_service.sql",
    "db/postgres/003_v4_source_cache_jobs.sql",
    "deploy/v4/emperor-v4-source-cache-worker.service",
    "deploy/v4/emperor-v4-source-cache-worker.timer",
    "deploy/v4/source-cache.env.example",
    "deploy/v4/provision-prerequisites.sh",
    "deploy/v4/verify-server-runtime.sh",
)
CLAIM_EXTRACTOR_RELEASE_PATHS = (
    "pyproject.toml",
    "config/claim-extraction-profiles.yml",
    "config/claim-extraction-output.schema.json",
    "src/emperor_v4/__init__.py",
    "src/emperor_v4/adapters/claim_extraction_profile.py",
    "src/emperor_v4/adapters/claim_extractor.py",
    "src/emperor_v4/adapters/claim_extractor_frozen.py",
    "src/emperor_v4/adapters/claim_extractor_codex.py",
    "src/emperor_v4/adapters/structured_output_contract.py",
    "src/emperor_v4/application/claim_extractor_service.py",
    "src/emperor_v4/application/source_cache_worker.py",
    "src/emperor_v4/contracts/assertion.py",
    "src/emperor_v4/contracts/extraction.py",
    "src/emperor_v4/persistence/claim_extractor.py",
    "src/emperor_v4/persistence/postgres_claim_extractor.py",
    "src/emperor_v4/persistence/source_cache_jobs.py",
    "src/emperor_v4/runtime/claim_extractor.py",
    "src/emperor_v4/runtime/claim_extractor_model_shadow.py",
    "src/emperor_v4/runtime/release.py",
    "db/postgres/004_v4_claim_extractor_service.sql",
    "deploy/v4/emperor-v4-claim-extractor-worker.service",
    "deploy/v4/emperor-v4-claim-extractor-worker.timer",
    "deploy/v4/claim-extractor.env.example",
    "deploy/v4/provision-prerequisites.sh",
    "deploy/v4/verify-server-runtime.sh",
)
EMPEROR_REBUILD_RELEASE_PATHS = (
    "AGENTS.md",
    "README.md",
    "pyproject.toml",
    "config",
    "db/postgres/007_v4_historical_outcome_clusters.sql",
    "docs/项目总纲/皇帝综合评价体系评分标准.md",
    "docs/项目总纲/总规则.md",
    "docs/证据规则/公共成果登记与人物画像规则.md",
    "docs/证据规则/单朝代治理会话工作流.md",
    "docs/证据规则/单皇帝主控会话工作流.md",
    "docs/分项规则/第五项统治者政治素质/B用人与授权.md",
    "eval/i5b_current_value",
    "src/emperor_v4",
    "deploy/v4/provision-prerequisites.sh",
    "deploy/v4/verify-server-runtime.sh",
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
            files.extend(
                item
                for item in path.rglob("*")
                if item.is_file() and "__pycache__" not in item.parts
            )
        else:
            raise FileNotFoundError(f"release allowlist 路径不存在: {name}")
    return tuple(
        sorted(
            set(files),
            key=lambda item: item.relative_to(repo_root).as_posix(),
        )
    )


def build_source_cache_release(
    *,
    repo_root: Path,
    output_dir: Path,
    commit_sha: str,
    require_clean: bool = True,
) -> dict[str, Any]:
    return _build_release(
        repo_root=repo_root,
        output_dir=output_dir,
        commit_sha=commit_sha,
        require_clean=require_clean,
        service="v4-source-cache",
        archive_prefix="v4-source-cache",
        paths=SOURCE_CACHE_RELEASE_PATHS,
    )


def build_claim_extractor_release(
    *,
    repo_root: Path,
    output_dir: Path,
    commit_sha: str,
    require_clean: bool = True,
) -> dict[str, Any]:
    return _build_release(
        repo_root=repo_root,
        output_dir=output_dir,
        commit_sha=commit_sha,
        require_clean=require_clean,
        service="v4-claim-extractor",
        archive_prefix="v4-claim-extractor",
        paths=CLAIM_EXTRACTOR_RELEASE_PATHS,
    )


def build_emperor_rebuild_release(
    *,
    repo_root: Path,
    output_dir: Path,
    commit_sha: str,
    require_clean: bool = True,
) -> dict[str, Any]:
    return _build_release(
        repo_root=repo_root,
        output_dir=output_dir,
        commit_sha=commit_sha,
        require_clean=require_clean,
        service="v4-emperor-rebuild",
        archive_prefix="v4-emperor-rebuild",
        paths=EMPEROR_REBUILD_RELEASE_PATHS,
    )


def _build_release(
    *,
    repo_root: Path,
    output_dir: Path,
    commit_sha: str,
    require_clean: bool,
    service: str,
    archive_prefix: str,
    paths: Iterable[str],
) -> dict[str, Any]:
    actual_sha = _git(repo_root, "rev-parse", "HEAD")
    if commit_sha != actual_sha or len(commit_sha) != 40:
        raise ValueError("release commit_sha 必须等于当前 HEAD")
    if require_clean and _git(repo_root, "status", "--short"):
        raise RuntimeError("不可变 release 只能从干净工作树构建")
    files = _files(repo_root, paths)
    entries = []
    for path in files:
        data = path.read_bytes()
        entries.append(
            {
                "path": path.relative_to(repo_root).as_posix(),
                "size": len(data),
                "sha256": _sha256(data),
            }
        )
    embedded = {
        "contract": RELEASE_CONTRACT,
        "service": service,
        "commit_sha": commit_sha,
        "files": entries,
    }
    release_json = (
        json.dumps(
            embedded,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / f"{archive_prefix}-{commit_sha}.tar"
    with tarfile.open(
        archive_path,
        "w",
        format=tarfile.PAX_FORMAT,
    ) as archive:
        for path in files:
            data = path.read_bytes()
            info = tarfile.TarInfo(
                path.relative_to(repo_root).as_posix()
            )
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
    manifest_path = output_dir / (
        f"{archive_prefix}-{commit_sha}.manifest.json"
    )
    manifest_path.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def verify_service_release(
    *,
    archive_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    manifest = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )
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


verify_source_cache_release = verify_service_release


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="构建或验证 V4 服务不可变发布包"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--repo-root", type=Path, default=Path.cwd())
    build.add_argument("--output-dir", type=Path, required=True)
    build.add_argument("--commit-sha", required=True)
    build.add_argument(
        "--service",
        choices=("source-cache", "claim-extractor", "emperor-rebuild"),
        default="source-cache",
    )
    verify = sub.add_parser("verify")
    verify.add_argument("--archive", type=Path, required=True)
    verify.add_argument("--manifest", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = (
        (
            {
                "source-cache": build_source_cache_release,
                "claim-extractor": build_claim_extractor_release,
                "emperor-rebuild": build_emperor_rebuild_release,
            }[args.service]
        )(
            repo_root=args.repo_root,
            output_dir=args.output_dir,
            commit_sha=args.commit_sha,
        )
        if args.command == "build"
        else verify_service_release(
            archive_path=args.archive,
            manifest_path=args.manifest,
        )
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
