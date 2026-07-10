from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path

import pytest

from scripts.dev import retrieval_v3_runtime_release as release


def write_archive(path: Path, names: list[str]) -> None:
    with tarfile.open(path, "w:gz") as archive:
        for name in names:
            payload = b"runtime\n"
            member = tarfile.TarInfo(name)
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))


def write_manifest(path: Path, archive: Path, required_paths: list[str]) -> None:
    path.write_text(
        json.dumps(
            {
                "schema": release.SCHEMA,
                "commit_sha": "a" * 40,
                "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                "required_paths": required_paths,
            }
        ),
        encoding="utf-8",
    )


def test_apply_plan_validates_archive_and_keeps_server_read_only(tmp_path: Path) -> None:
    archive = tmp_path / "release.tar.gz"
    manifest = tmp_path / "manifest.json"
    write_archive(archive, ["scripts/worker.py", "data/config.yml"])
    write_manifest(manifest, archive, ["scripts/worker.py", "data/config.yml"])

    plan = release.plan_apply(
        archive_path=archive,
        manifest_path=manifest,
        release_root=tmp_path / "server-runtime",
        services=["claim-worker.service", "source-cache@1.service"],
        systemctl_scope="user",
    )

    assert plan["write_server"] is False
    assert plan["commit_sha"] == "a" * 40
    assert plan["services"] == ["claim-worker.service", "source-cache@1.service"]
    assert plan["systemctl_scope"] == "user"
    assert release.systemctl_argv(plan, "restart", "claim-worker.service") == [
        "systemctl", "--user", "restart", "claim-worker.service"
    ]
    assert not (tmp_path / "server-runtime").exists()


def test_apply_plan_rejects_checksum_mismatch(tmp_path: Path) -> None:
    archive = tmp_path / "release.tar.gz"
    manifest = tmp_path / "manifest.json"
    write_archive(archive, ["scripts/worker.py"])
    write_manifest(manifest, archive, ["scripts/worker.py"])
    archive.write_bytes(archive.read_bytes() + b"tampered")

    with pytest.raises(release.RuntimeReleaseError, match="SHA256"):
        release.plan_apply(
            archive_path=archive,
            manifest_path=manifest,
            release_root=tmp_path / "server-runtime",
            services=[],
        )


def test_archive_inspection_rejects_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "release.tar.gz"
    write_archive(archive, ["../escape.py"])

    with pytest.raises(release.RuntimeReleaseError, match="unsafe archive member"):
        release.inspect_archive(archive)


def test_service_names_are_strict() -> None:
    with pytest.raises(release.RuntimeReleaseError, match="invalid systemd"):
        release.validate_services(["claim-worker.service; reboot"])


def test_server_runtime_scripts_are_release_relative_and_config_driven() -> None:
    root = Path(__file__).resolve().parents[1]
    claim_script = (root / "scripts/dev/server_runtime/retrieval_v3_claim_worker_loop.sh").read_text(encoding="utf-8")
    object_script = (root / "scripts/dev/server_runtime/retrieval_v3_object_source_cache_worker_loop.sh").read_text(encoding="utf-8")

    assert "object_cache_runner_" not in claim_script + object_script
    assert 'BASH_SOURCE[0]' in claim_script
    assert 'BASH_SOURCE[0]' in object_script
    assert "--judge-timeout" not in claim_script
    assert "--judge-shard-size" not in claim_script
    assert "--judge-shard-workers" not in claim_script
    assert "--env-file" not in claim_script + object_script
