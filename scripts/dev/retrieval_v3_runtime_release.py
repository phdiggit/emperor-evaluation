from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "emperor-evaluation-runtime-release/v1"
REQUIRED_RUNTIME_PATHS = (
    "data/configs/project_config.yml",
    "scripts/shared/agent_runtime_config.py",
    "scripts/dev/retrieval_v2_clean_runner.py",
    "scripts/dev/retrieval_v2_object_source_cache_worker.py",
    "scripts/dev/retrieval_v2_claim_extraction_worker.py",
    "scripts/dev/retrieval_v3_runtime_release.py",
    "scripts/dev/server_runtime/retrieval_v3_claim_worker_loop.sh",
    "scripts/dev/server_runtime/retrieval_v3_object_source_cache_worker_loop.sh",
    "scripts/dev/server_runtime/emperor-retrieval-v3-claim-worker.service",
    "scripts/dev/server_runtime/emperor-retrieval-v3-object-source-cache-worker.service",
)
SERVICE_RE = re.compile(r"^[A-Za-z0-9_.@-]+$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


class RuntimeReleaseError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_checked(argv: Sequence[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv),
        cwd=cwd,
        check=True,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def git_text(repo_root: Path, *args: str) -> str:
    return run_checked(["git", *args], cwd=repo_root).stdout.strip()


def assert_clean_worktree(repo_root: Path) -> None:
    status = git_text(repo_root, "status", "--porcelain", "--untracked-files=all")
    if status:
        raise RuntimeReleaseError("package requires a clean worktree so the archive exactly matches one commit")


def package_release(
    *,
    repo_root: Path,
    archive_path: Path,
    manifest_path: Path,
    ref: str = "HEAD",
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    assert_clean_worktree(repo_root)
    commit_sha = git_text(repo_root, "rev-parse", f"{ref}^{{commit}}")
    if not COMMIT_RE.fullmatch(commit_sha):
        raise RuntimeReleaseError(f"invalid commit SHA resolved from {ref}: {commit_sha}")
    for required_path in REQUIRED_RUNTIME_PATHS:
        run_checked(["git", "cat-file", "-e", f"{commit_sha}:{required_path}"], cwd=repo_root)
    archive_path = archive_path.resolve()
    manifest_path = manifest_path.resolve()
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    run_checked(
        ["git", "archive", "--format=tar.gz", f"--output={archive_path}", commit_sha],
        cwd=repo_root,
    )
    manifest = {
        "schema": SCHEMA,
        "generated_by": "scripts/dev/retrieval_v3_runtime_release.py",
        "commit_sha": commit_sha,
        "ref": ref,
        "branch": git_text(repo_root, "branch", "--show-current"),
        "archive_filename": archive_path.name,
        "archive_sha256": sha256_file(archive_path),
        "required_paths": list(REQUIRED_RUNTIME_PATHS),
        "agent_runtime_config": "data/configs/project_config.yml",
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def read_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise RuntimeReleaseError(f"{path}: manifest must be a JSON object")
    manifest = dict(payload)
    if manifest.get("schema") != SCHEMA:
        raise RuntimeReleaseError(f"{path}: unsupported release schema")
    commit_sha = str(manifest.get("commit_sha") or "")
    if not COMMIT_RE.fullmatch(commit_sha):
        raise RuntimeReleaseError(f"{path}: invalid commit_sha")
    required_paths = manifest.get("required_paths")
    if not isinstance(required_paths, list) or not required_paths:
        raise RuntimeReleaseError(f"{path}: required_paths must be a non-empty list")
    return manifest


def safe_member_path(member: tarfile.TarInfo) -> str:
    path = PurePosixPath(member.name)
    if path.is_absolute() or not member.name or ".." in path.parts:
        raise RuntimeReleaseError(f"unsafe archive member: {member.name}")
    if member.issym() or member.islnk():
        target = PurePosixPath(member.linkname)
        if target.is_absolute() or ".." in target.parts:
            raise RuntimeReleaseError(f"unsafe archive link: {member.name} -> {member.linkname}")
    return path.as_posix().rstrip("/")


def inspect_archive(archive_path: Path) -> set[str]:
    names: set[str] = set()
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive.getmembers():
            names.add(safe_member_path(member))
    return names


def validate_services(services: Sequence[str]) -> list[str]:
    clean = list(dict.fromkeys(str(service).strip() for service in services if str(service).strip()))
    invalid = [service for service in clean if not SERVICE_RE.fullmatch(service)]
    if invalid:
        raise RuntimeReleaseError(f"invalid systemd service names: {', '.join(invalid)}")
    return clean


def plan_apply(
    *,
    archive_path: Path,
    manifest_path: Path,
    release_root: Path,
    services: Sequence[str],
    systemctl_scope: str = "system",
) -> dict[str, Any]:
    archive_path = archive_path.resolve()
    manifest = read_manifest(manifest_path.resolve())
    actual_sha = sha256_file(archive_path)
    if actual_sha != manifest.get("archive_sha256"):
        raise RuntimeReleaseError("archive SHA256 does not match manifest")
    names = inspect_archive(archive_path)
    missing = [str(path) for path in manifest["required_paths"] if str(path) not in names]
    if missing:
        raise RuntimeReleaseError(f"archive is missing required runtime paths: {', '.join(missing)}")
    service_names = validate_services(services)
    if systemctl_scope not in {"system", "user"}:
        raise RuntimeReleaseError("systemctl_scope must be system or user")
    release_root = release_root.resolve()
    commit_sha = str(manifest["commit_sha"])
    return {
        "ok": True,
        "write_server": False,
        "commit_sha": commit_sha,
        "archive_sha256": actual_sha,
        "release_root": str(release_root),
        "release_path": str(release_root / "releases" / commit_sha),
        "current_path": str(release_root / "current"),
        "services": service_names,
        "systemctl_scope": systemctl_scope,
        "required_paths": list(manifest["required_paths"]),
    }


def _within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _switch_symlink(current_path: Path, target: Path) -> None:
    link_path = current_path.with_name(f".{current_path.name}.{os.getpid()}.new")
    if link_path.exists() or link_path.is_symlink():
        link_path.unlink()
    os.symlink(target, link_path, target_is_directory=True)
    os.replace(link_path, current_path)


def systemctl_argv(plan: Mapping[str, Any], action: str, service: str) -> list[str]:
    argv = ["systemctl"]
    if plan.get("systemctl_scope") == "user":
        argv.append("--user")
    return [*argv, action, service]


def current_path_for_apply(plan: Mapping[str, Any]) -> Path:
    """Return an absolute current-link path without dereferencing the link."""
    return Path(os.path.abspath(str(plan["current_path"])))


def execute_apply(plan: Mapping[str, Any], *, archive_path: Path) -> dict[str, Any]:
    if os.name != "posix":
        raise RuntimeReleaseError("--execute is supported only on the Linux server")
    services = validate_services(plan.get("services") or [])
    if not services:
        raise RuntimeReleaseError("--execute requires at least one --service")
    release_root = Path(str(plan["release_root"])).resolve()
    releases_root = (release_root / "releases").resolve()
    release_path = Path(str(plan["release_path"])).resolve()
    current_path = current_path_for_apply(plan)
    if (
        not _within(releases_root, release_root)
        or not _within(release_path, releases_root)
        or not _within(current_path.parent, release_root)
    ):
        raise RuntimeReleaseError("resolved release paths escape release_root")
    releases_root.mkdir(parents=True, exist_ok=True)
    previous_target = current_path.resolve() if current_path.is_symlink() else None
    created_release = False
    if not release_path.exists():
        staging = Path(tempfile.mkdtemp(prefix=f".{plan['commit_sha']}.", dir=releases_root))
        if not _within(staging, releases_root):
            raise RuntimeReleaseError("staging path escapes releases directory")
        try:
            with tarfile.open(archive_path.resolve(), "r:gz") as archive:
                members = archive.getmembers()
                for member in members:
                    safe_member_path(member)
                archive.extractall(staging, members=members, filter="data")
            for required_path in plan["required_paths"]:
                if not (staging / str(required_path)).exists():
                    raise RuntimeReleaseError(f"extracted release is missing {required_path}")
            os.replace(staging, release_path)
            created_release = True
        finally:
            if staging.exists() and _within(staging, releases_root):
                shutil.rmtree(staging)
    _switch_symlink(current_path, release_path)
    try:
        for service in services:
            run_checked(systemctl_argv(plan, "restart", service))
        for service in services:
            run_checked([*systemctl_argv(plan, "is-active", service)[:-1], "--quiet", service])
    except Exception:
        if previous_target is not None:
            _switch_symlink(current_path, previous_target)
            for service in services:
                subprocess.run(systemctl_argv(plan, "restart", service), check=False)
        elif current_path.is_symlink():
            current_path.unlink()
        raise
    return {**dict(plan), "write_server": True, "created_release": created_release, "active": True}


def write_output(path: Path | None, payload: Mapping[str, Any]) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8", newline="\n")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Package and atomically apply commit-pinned server runtime releases.")
    sub = parser.add_subparsers(dest="command", required=True)
    package = sub.add_parser("package", help="Create a git-archive release and SHA256 manifest from a clean commit.")
    package.add_argument("--repo-root", type=Path, default=ROOT)
    package.add_argument("--ref", default="HEAD")
    package.add_argument("--archive", type=Path, required=True)
    package.add_argument("--manifest", type=Path, required=True)
    package.add_argument("--output-json", type=Path)
    apply = sub.add_parser("apply", help="Validate or atomically activate a release on the Linux server.")
    apply.add_argument("--archive", type=Path, required=True)
    apply.add_argument("--manifest", type=Path, required=True)
    apply.add_argument("--release-root", type=Path, required=True)
    apply.add_argument("--service", action="append", default=[])
    apply.add_argument("--systemctl-scope", choices=("system", "user"), default="system")
    apply.add_argument("--execute", action="store_true")
    apply.add_argument("--output-json", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "package":
        payload = package_release(
            repo_root=args.repo_root,
            archive_path=args.archive,
            manifest_path=args.manifest,
            ref=args.ref,
        )
    else:
        payload = plan_apply(
            archive_path=args.archive,
            manifest_path=args.manifest,
            release_root=args.release_root,
            services=args.service,
            systemctl_scope=args.systemctl_scope,
        )
        if args.execute:
            payload = execute_apply(payload, archive_path=args.archive)
    write_output(args.output_json, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
