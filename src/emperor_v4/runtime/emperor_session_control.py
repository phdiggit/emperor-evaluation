from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
from typing import Any, Mapping, Sequence
from uuid import uuid4

import yaml

from emperor_v4.evaluation.i5b_current_value_runner import (
    render_scoring_detail_markdown,
)
from emperor_v4.evaluation.historical_outcome_registry import (
    materialize_ruler_outcome_registry,
)
from emperor_v4.runtime.emperor_rebuild import RebuildLimits, rebuild_emperor


LEASE_SCHEMA_VERSION = "emperor-session-lease-v1"
STATUS_SCHEMA_VERSION = "emperor-session-control-status-v1"
PUBLISH_SCHEMA_VERSION = "emperor-session-publish-v1"
GLOBAL_MODEL_SLOT_COUNT = 4
SESSION_RULE_DOCUMENTS = (
    "AGENTS.md",
    "README.md",
    "docs/项目总纲/皇帝综合评价体系评分标准.md",
    "docs/项目总纲/总规则.md",
    "docs/证据规则/公共成果登记与人物画像规则.md",
    "docs/证据规则/单皇帝主控会话工作流.md",
    "docs/分项规则/第五项统治者政治素质/B用人与授权.md",
)


class SessionControlError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digest(value: object) -> str:
    return sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _file_sha256(path: Path) -> str | None:
    return sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def _contract_fingerprint(root: Path) -> str:
    entries = []
    for relative_root, suffixes in (
        ("config", {".json", ".yml", ".yaml"}),
        ("src/emperor_v4", {".py"}),
    ):
        base = root / relative_root
        if not base.is_dir():
            raise SessionControlError(f"release 缺少合同目录: {relative_root}")
        for path in sorted(
            value
            for value in base.rglob("*")
            if value.is_file() and value.suffix.lower() in suffixes
        ):
            entries.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "sha256": _file_sha256(path),
                }
            )
    for relative_path in SESSION_RULE_DOCUMENTS:
        path = root / relative_path
        if not path.is_file():
            raise SessionControlError(f"release 缺少当前规则文档: {relative_path}")
        entries.append(
            {"path": relative_path, "sha256": _file_sha256(path)}
        )
    return _digest(entries)


def _safe_token(value: object, *, field: str) -> str:
    token = str(value or "").strip()
    if not token or any(part in token for part in ("/", "\\", "..")):
        raise ValueError(f"{field} 含非法路径字符")
    return token


def _atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def _claim_json(path: Path, payload: Mapping[str, object]) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return False
    try:
        data = (
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        os.write(descriptor, data)
    finally:
        os.close(descriptor)
    return True


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SessionControlError(f"运行时合同不是 object: {path}")
    return payload


def _release_identity(release_root: Path) -> str:
    release_manifest = release_root / "RELEASE.json"
    if release_manifest.is_file():
        payload = _read_json(release_manifest)
        commit_sha = str(payload.get("commit_sha") or "")
        if len(commit_sha) != 40:
            raise SessionControlError("RELEASE.json 缺少40位 commit_sha")
        return commit_sha
    try:
        commit_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=release_root,
            text=True,
            encoding="utf-8",
        ).strip()
        dirty = subprocess.check_output(
            ["git", "status", "--short"],
            cwd=release_root,
            text=True,
            encoding="utf-8",
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SessionControlError("会话只能从干净 Git checkout 或不可变 release 启动") from exc
    if len(commit_sha) != 40 or dirty:
        raise SessionControlError("会话只能从干净且固定的 release 启动")
    return commit_sha


def _project_rulers(release_root: Path) -> tuple[dict[str, Any], list[str]]:
    project_path = release_root / "config/project.yml"
    project = yaml.safe_load(project_path.read_text(encoding="utf-8"))
    rulers = ((project.get("i5b_current_value") or {}).get("rulers") or {})
    if not isinstance(rulers, dict) or not rulers:
        raise SessionControlError("config/project.yml 没有可运行皇帝")
    return rulers, [str(value) for value in rulers]


def _canonical_paths(
    root: Path, configured: Mapping[str, object]
) -> dict[str, Path]:
    result = root / str(configured["result"])
    project = yaml.safe_load(
        (root / "config/project.yml").read_text(encoding="utf-8")
    )
    registry = project.get("historical_outcome_registry") or {}
    return {
        "source_pack": root / str(configured["source_pack"]),
        "neutral_materials": root / str(configured["neutral_materials"]),
        "result_json": result,
        "result_markdown": result.with_suffix(".md"),
        "outcome_binding": root / str(configured["outcome_binding"]),
        "outcome_registry_json": root / str(registry["current_json"]),
        "outcome_registry_markdown": root / str(registry["current_markdown"]),
    }


def _control_root(state_root: Path) -> Path:
    return state_root.resolve() / "session-control"


def _session_path(state_root: Path, session_id: str) -> Path:
    return _control_root(state_root) / "sessions" / session_id / "current.json"


def _owned_resource(path: Path, session_id: str) -> bool:
    return path.is_file() and _read_json(path).get("session_id") == session_id


def _release_resources(state_root: Path, lease: Mapping[str, object]) -> None:
    session_id = str(lease["session_id"])
    control = _control_root(state_root)
    resource_paths = [
        control / "rulers" / f"{lease['ruler_ref']}.json",
        *(
            control / "model-slots" / f"{int(slot)}.json"
            for slot in lease.get("model_slots") or ()
        ),
        *(
            control / "shared-writers" / f"{token}.json"
            for token in lease.get("shared_tokens") or ()
        ),
    ]
    for path in resource_paths:
        if _owned_resource(path, session_id):
            path.unlink()


def _release_session_guard(state_root: Path, session_id: str) -> None:
    guard = _control_root(state_root) / "session-ids" / f"{session_id}.json"
    if _owned_resource(guard, session_id):
        guard.unlink()


def _prepare_workspace(
    *,
    release_root: Path,
    workspace_root: Path,
    ruler: str,
    configured: Mapping[str, object],
) -> None:
    workspace_root.mkdir(parents=True, exist_ok=False)
    shutil.copytree(release_root / "config", workspace_root / "config")
    project = yaml.safe_load(
        (release_root / "config/project.yml").read_text(encoding="utf-8")
    )
    ruler_configs = (project.get("i5b_current_value") or {}).get("rulers") or {}
    source = release_root / "eval/i5b_current_value" / ruler
    if not (source / "source-pack.json").is_file():
        raise SessionControlError(f"release 不含皇帝 source-pack: {ruler}")
    shutil.copytree(source, workspace_root / "eval/i5b_current_value" / ruler)
    # The public outcome registry is rebuilt from every configured source pack,
    # even though this session may mutate only its claimed ruler. Copy the
    # other packs as immutable inputs. Shared neutral atoms live under the
    # session controller's token store; another ruler's derived neutral view is
    # never copied or merged into this workspace.
    for other_ruler, other_config in ruler_configs.items():
        if not isinstance(other_config, Mapping):
            continue
        if str(other_ruler) != ruler:
            other_source = release_root / str(other_config.get("source_pack") or "")
            if not other_source.is_file():
                raise SessionControlError(
                    f"release 缺少公共成果登记输入: {other_ruler}"
                )
            other_target = workspace_root / other_source.relative_to(release_root)
            other_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(other_source, other_target)
    for path in _canonical_paths(release_root, configured).values():
        if not path.is_file():
            # A ruler's first run has only the immutable bootstrap source pack.
            # The session owns generation of neutral materials, bindings and
            # result views, so those outputs are intentionally absent before
            # the first claim.
            continue
        relative = path.relative_to(release_root)
        target = workspace_root / relative
        if target.is_file():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def claim_session(
    *,
    state_root: Path,
    release_root: Path,
    session_id: str,
    ruler: str | None = None,
    model_slot_count: int = 2,
) -> dict[str, Any]:
    session_id = _safe_token(session_id, field="session_id")
    if not 1 <= model_slot_count <= GLOBAL_MODEL_SLOT_COUNT:
        raise ValueError("model_slot_count 必须介于1到4")
    state_root = state_root.resolve()
    release_root = release_root.resolve()
    current_path = _session_path(state_root, session_id)
    if current_path.is_file():
        current = _read_json(current_path)
        if current.get("schema_version") != LEASE_SCHEMA_VERSION:
            raise SessionControlError("已有会话租约版本不受支持")
        return {**current, "reused": True}

    release_sha = _release_identity(release_root)
    rulers, configured_order = _project_rulers(release_root)
    candidates = [ruler] if ruler else configured_order
    if ruler and ruler not in rulers:
        raise SessionControlError(f"皇帝尚未进入当前链路: {ruler}")
    release_contract_fingerprint = _contract_fingerprint(release_root)
    candidate_specs = []
    invalid_candidates: list[str] = []
    for candidate in candidates:
        try:
            configured = rulers[candidate]
            for field in ("source_pack", "neutral_materials", "result"):
                if not configured.get(field):
                    raise SessionControlError(f"缺少 {field}")
            source_pack_path = release_root / str(configured["source_pack"])
            source_pack = _read_json(source_pack_path)
            ruler_ref = _safe_token(source_pack.get("ruler_ref"), field="ruler_ref")
            shared_tokens = [
                _safe_token(value, field="shared material token")
                for value in [configured.get("neutral_scan_backbone_material_token")]
                if value
            ]
            candidate_specs.append(
                (candidate, configured, ruler_ref, shared_tokens)
            )
        except (KeyError, OSError, ValueError, SessionControlError) as exc:
            if ruler:
                raise SessionControlError(
                    f"目标皇帝配置不完整: {candidate}: {exc}"
                ) from exc
            invalid_candidates.append(candidate)
    control = _control_root(state_root)
    control.mkdir(parents=True, exist_ok=True)
    session_guard = control / "session-ids" / f"{session_id}.json"
    if not _claim_json(
        session_guard,
        {
            "schema_version": LEASE_SCHEMA_VERSION,
            "session_id": session_id,
            "release_sha": release_sha,
        },
    ):
        if current_path.is_file():
            return {**_read_json(current_path), "reused": True}
        raise SessionControlError("session_id 正在被另一个认领过程使用")
    busy: list[str] = []
    for candidate, configured, ruler_ref, shared_tokens in candidate_specs:
        base_payload = {
            "schema_version": LEASE_SCHEMA_VERSION,
            "session_id": session_id,
            "ruler": candidate,
            "ruler_ref": ruler_ref,
            "release_sha": release_sha,
            "release_contract_fingerprint": release_contract_fingerprint,
            "host": socket.gethostname(),
            "started_at": _now(),
            "updated_at": _now(),
        }
        ruler_path = control / "rulers" / f"{ruler_ref}.json"
        if not _claim_json(ruler_path, base_payload):
            busy.append(candidate)
            continue
        claimed_slots: list[int] = []
        claimed_shared: list[str] = []
        try:
            for slot in range(GLOBAL_MODEL_SLOT_COUNT):
                slot_path = control / "model-slots" / f"{slot}.json"
                if _claim_json(slot_path, base_payload):
                    claimed_slots.append(slot)
                    if len(claimed_slots) == model_slot_count:
                        break
            if len(claimed_slots) != model_slot_count:
                raise SessionControlError("全局模型槽位不足")
            for token in shared_tokens:
                token_path = control / "shared-writers" / f"{token}.json"
                if not _claim_json(token_path, base_payload):
                    raise SessionControlError(f"共享编年材料已有写者: {token}")
                claimed_shared.append(token)
            session_root = control / "sessions" / session_id
            workspace_root = session_root / "workspace"
            _prepare_workspace(
                release_root=release_root,
                workspace_root=workspace_root,
                ruler=candidate,
                configured=configured,
            )
            canonical = _canonical_paths(release_root, configured)
            lease = {
                **base_payload,
                "stage": "claimed",
                "model_slots": claimed_slots,
                "shared_tokens": claimed_shared,
                "workspace_root": str(workspace_root),
                "runtime_root": str(session_root / "runtime"),
                "shared_backbone_root": str(state_root / "shared-neutral-backbones"),
                "canonical_expected_sha256": {
                    key: _file_sha256(path) for key, path in canonical.items()
                },
                "input_fingerprint": _digest(
                    {
                        "release_sha": release_sha,
                        "ruler": candidate,
                        "canonical": {
                            key: _file_sha256(path) for key, path in canonical.items()
                        },
                    }
                ),
            }
            _atomic_json(current_path, lease)
            return {**lease, "reused": False}
        except SessionControlError:
            rollback = {
                **base_payload,
                "model_slots": claimed_slots,
                "shared_tokens": claimed_shared,
            }
            _release_resources(state_root, rollback)
            session_root = control / "sessions" / session_id
            if session_root.exists():
                shutil.rmtree(session_root)
            if ruler:
                _release_session_guard(state_root, session_id)
                raise
            busy.append(candidate)
        except Exception:
            rollback = {
                **base_payload,
                "model_slots": claimed_slots,
                "shared_tokens": claimed_shared,
            }
            _release_resources(state_root, rollback)
            session_root = control / "sessions" / session_id
            if session_root.exists():
                shutil.rmtree(session_root)
            _release_session_guard(state_root, session_id)
            raise
    _release_session_guard(state_root, session_id)
    raise SessionControlError(
        "没有可认领皇帝"
        + (f"；占用: {', '.join(busy)}" if busy else "")
        + (f"；配置无效: {', '.join(invalid_candidates)}" if invalid_candidates else "")
    )


def heartbeat_session(
    *, state_root: Path, session_id: str, stage: str
) -> dict[str, Any]:
    session_id = _safe_token(session_id, field="session_id")
    stage = _safe_token(stage, field="stage")
    if stage in {"claimed", "running", "ready_to_publish", "failed_reusable"}:
        raise SessionControlError("该阶段只能由会话控制入口设置")
    path = _session_path(state_root, session_id)
    if not path.is_file():
        raise SessionControlError("会话租约不存在")
    lease = _read_json(path)
    lease["stage"] = stage
    lease["updated_at"] = _now()
    _atomic_json(path, lease)
    return lease


def run_claimed_session(
    *,
    state_root: Path,
    session_id: str,
    release_root: Path,
    source_index_root: Path,
    dynasty_governance_root: Path,
    wall_clock_seconds: int | None = None,
    source_workers: int = 8,
    export_workers: int = 4,
    max_pages_per_subject: int = 32,
    model_timeout_seconds: int = 120,
) -> dict[str, Any]:
    path = _session_path(state_root, _safe_token(session_id, field="session_id"))
    if not path.is_file():
        raise SessionControlError("会话租约不存在")
    lease = _read_json(path)
    if _release_identity(release_root.resolve()) != lease.get("release_sha"):
        raise SessionControlError("运行 release 与认领 release 不一致")
    if _contract_fingerprint(release_root.resolve()) != lease.get(
        "release_contract_fingerprint"
    ):
        raise SessionControlError("运行 release 合同在认领后发生变化")
    if lease.get("stage") == "ready_to_publish":
        completed_path = Path(str(lease["runtime_root"])) / "completed.json"
        if completed_path.is_file():
            return {**_read_json(completed_path), "reused": True}
    lease["stage"] = "running"
    lease["updated_at"] = _now()
    _atomic_json(path, lease)
    limits = RebuildLimits(
        wall_clock_seconds=wall_clock_seconds,
        source_workers=source_workers,
        export_workers=export_workers,
        max_pages_per_subject=max_pages_per_subject,
        model_workers=len(lease["model_slots"]),
        model_timeout_seconds=model_timeout_seconds,
    )
    try:
        report = rebuild_emperor(
            workspace_root=Path(str(lease["workspace_root"])),
            ruler=str(lease["ruler"]),
            source_index_path=None,
            source_index_root=source_index_root,
            dynasty_governance_root=dynasty_governance_root,
            shared_backbone_root=Path(str(lease["shared_backbone_root"])),
            runtime_root=Path(str(lease["runtime_root"])),
            limits=limits,
        )
    except Exception:
        lease["stage"] = "failed_reusable"
        lease["updated_at"] = _now()
        _atomic_json(path, lease)
        raise
    completed = {
        **report,
        "session_id": session_id,
        "release_sha": lease["release_sha"],
        "input_fingerprint": lease["input_fingerprint"],
        "limits": asdict(limits),
        "reused": False,
    }
    _atomic_json(Path(str(lease["runtime_root"])) / "completed.json", completed)
    lease["stage"] = "ready_to_publish"
    lease["updated_at"] = _now()
    for token in list(lease.get("shared_tokens") or ()):
        token_path = _control_root(state_root) / "shared-writers" / f"{token}.json"
        if _owned_resource(token_path, session_id):
            token_path.unlink()
    lease["shared_tokens"] = []
    _atomic_json(path, lease)
    return completed


def _validate_publish_payload(
    *, workspace_root: Path, configured: Mapping[str, object], ruler: str
) -> dict[str, Path]:
    paths = _canonical_paths(workspace_root, configured)
    missing = [key for key, path in paths.items() if not path.is_file()]
    if missing:
        raise SessionControlError(f"会话输出不完整: {', '.join(missing)}")
    source_pack = _read_json(paths["source_pack"])
    binding = _read_json(paths["outcome_binding"])
    outcome_registry = _read_json(paths["outcome_registry_json"])
    neutral = _read_json(paths["neutral_materials"])
    report = _read_json(paths["result_json"])
    markdown = paths["result_markdown"].read_text(encoding="utf-8")
    if source_pack.get("ruler") != ruler or report.get("ruler") != ruler:
        raise SessionControlError("会话输出皇帝不匹配")
    if report.get("source_pack_sha256") != source_pack.get("source_pack_sha256"):
        raise SessionControlError("结果与 source-pack 当前值不匹配")
    if materialize_ruler_outcome_registry(outcome_registry, binding) != source_pack.get(
        "outcome_registry"
    ):
        raise SessionControlError("成果总登记与皇帝窗口绑定无法还原 source-pack")
    if not isinstance((neutral.get("fanout") or {}).get("facts"), list):
        raise SessionControlError("中性材料缺少 fanout facts")
    if "## 战役登记" not in markdown or "## 治理成果登记" not in markdown:
        raise SessionControlError("皇帝详情导出不完整")
    for member in source_pack.get("members") or ():
        person = str(member["person"])
        rendered = render_scoring_detail_markdown(report, person=person)
        if "## 当前人物画像" not in rendered:
            raise SessionControlError(f"臣子详情导出失败: {person}")
    return paths


def publish_session(
    *, state_root: Path, session_id: str, canonical_root: Path
) -> dict[str, Any]:
    session_id = _safe_token(session_id, field="session_id")
    path = _session_path(state_root, session_id)
    if not path.is_file():
        raise SessionControlError("会话租约不存在")
    lease = _read_json(path)
    if lease.get("stage") != "ready_to_publish":
        raise SessionControlError("会话尚未完成重建与质量验证")
    canonical_root = canonical_root.resolve()
    if _contract_fingerprint(canonical_root) != lease.get(
        "release_contract_fingerprint"
    ):
        raise SessionControlError("canonical 代码或配置在会话运行期间已变化")
    rulers, _ = _project_rulers(canonical_root)
    configured = rulers.get(str(lease["ruler"]))
    if not isinstance(configured, Mapping):
        raise SessionControlError("canonical 已移除目标皇帝配置")
    source_paths = _validate_publish_payload(
        workspace_root=Path(str(lease["workspace_root"])),
        configured=configured,
        ruler=str(lease["ruler"]),
    )
    target_paths = _canonical_paths(canonical_root, configured)
    control = _control_root(state_root)
    global_publish_lock = control / "publish" / "historical-outcome-registry.json"
    if not _claim_json(global_publish_lock, {"session_id": session_id}):
        raise SessionControlError("成果总登记已有发布者")
    publish_lock = control / "publish" / f"{lease['ruler_ref']}.json"
    if not _claim_json(publish_lock, {"session_id": session_id}):
        global_publish_lock.unlink(missing_ok=True)
        raise SessionControlError("目标皇帝已有发布者")
    rollback_root = path.parent / "publish-rollback"
    replaced: list[str] = []
    try:
        expected = dict(lease["canonical_expected_sha256"])
        changed_targets = [
            key
            for key, target in target_paths.items()
            if _file_sha256(target) != expected.get(key)
        ]
        if changed_targets:
            raise SessionControlError(
                "canonical 在会话运行期间已变化: " + ", ".join(changed_targets)
            )
        rollback_root.mkdir(parents=True, exist_ok=False)
        for key, target in target_paths.items():
            if target.is_file():
                shutil.copy2(target, rollback_root / key)
        for key, target in target_paths.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
            shutil.copy2(source_paths[key], temporary)
            os.replace(temporary, target)
            replaced.append(key)
    except Exception:
        for key in replaced:
            backup = rollback_root / key
            target = target_paths[key]
            if backup.is_file():
                os.replace(backup, target)
            elif target.exists():
                target.unlink()
        raise
    finally:
        if rollback_root.exists():
            shutil.rmtree(rollback_root)
        publish_lock.unlink(missing_ok=True)
        global_publish_lock.unlink(missing_ok=True)
    result = {
        "schema_version": PUBLISH_SCHEMA_VERSION,
        "status": "published_current",
        "session_id": session_id,
        "ruler": lease["ruler"],
        "release_sha": lease["release_sha"],
        "published_sha256": {
            key: _file_sha256(path) for key, path in target_paths.items()
        },
        "database_write_count": 0,
        "formal_score_write_count": 0,
    }
    _release_resources(state_root, lease)
    _release_session_guard(state_root, session_id)
    shutil.rmtree(path.parent)
    return result


def abandon_session(*, state_root: Path, session_id: str) -> dict[str, Any]:
    session_id = _safe_token(session_id, field="session_id")
    path = _session_path(state_root, session_id)
    if not path.is_file():
        raise SessionControlError("会话租约不存在")
    lease = _read_json(path)
    _release_resources(state_root, lease)
    _release_session_guard(state_root, session_id)
    shutil.rmtree(path.parent)
    return {
        "schema_version": LEASE_SCHEMA_VERSION,
        "status": "abandoned",
        "session_id": session_id,
        "ruler": lease["ruler"],
    }


def session_status(*, state_root: Path) -> dict[str, Any]:
    control = _control_root(state_root)
    sessions = []
    for path in sorted((control / "sessions").glob("*/current.json")):
        sessions.append(_read_json(path))
    occupied_slots = sorted(
        int(path.stem) for path in (control / "model-slots").glob("*.json")
    )
    return {
        "schema_version": STATUS_SCHEMA_VERSION,
        "status": "ready",
        "global_model_slot_count": GLOBAL_MODEL_SLOT_COUNT,
        "occupied_model_slots": occupied_slots,
        "available_model_slot_count": GLOBAL_MODEL_SLOT_COUNT - len(occupied_slots),
        "sessions": sessions,
    }
