from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import socket
import stat
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
from emperor_v4.runtime.emperor_rebuild import (
    RebuildLimits,
    _resolve_source_index,
    _shared_backbone_contract,
    rebuild_emperor,
)
from emperor_v4.runtime.dynasty_governance_rebuild import (
    DynastyGovernanceLimits,
    validate_dynasty_governance_current_catalog,
    load_dynasty_governance_catalog_entry,
    rebuild_dynasty_governance,
)
from emperor_v4.runtime.dynasty_governance_worker import _exclusive_lock


LEASE_SCHEMA_VERSION = "emperor-session-lease-v1"
STATUS_SCHEMA_VERSION = "emperor-session-control-status-v1"
PUBLISH_SCHEMA_VERSION = "emperor-session-publish-v1"
BOOTSTRAP_SCHEMA_VERSION = "emperor-session-bootstrap-v1"
BOOTSTRAP_REPORT_SCHEMA_VERSION = "emperor-session-bootstrap-report-v1"
RELEASE_UPGRADE_SCHEMA_VERSION = "emperor-session-release-upgrade-v1"
SESSION_DYNASTY_GOVERNANCE_SCHEMA_VERSION = (
    "emperor-session-dynasty-governance-v1"
)
GLOBAL_MODEL_SLOT_COUNT = 4
REQUIRED_REBUILD_STAGES = (
    "source_inventory",
    "neutral_materials",
    "outcome_projection",
    "current_projection",
)
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


_WORK_NAME_TRANSLATION = str.maketrans(
    {
        "實": "实",
        "錄": "录",
        "舊": "旧",
        "書": "书",
        "紀": "纪",
        "傳": "传",
        "資": "资",
        "鑑": "鉴",
        "續": "续",
        "國": "国",
    }
)


def _normalized_work_name(value: object) -> str:
    return (
        str(value)
        .translate(_WORK_NAME_TRANSLATION)
        .replace("对应皇帝", "")
        .replace(" ", "")
        .strip()
    )


def _neutral_material_strategy(
    workspace_root: Path, dynasty: str
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    path = workspace_root / "config/i5b-source-search-scope.yml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    defaults = payload.get("neutral_material_defaults") or {}
    for canonical, row in (payload.get("dynasties") or {}).items():
        if dynasty == str(canonical) or dynasty in {
            str(alias) for alias in row.get("aliases") or ()
        }:
            strategy = row.get("neutral_material_strategy") or {}
            if not isinstance(strategy, Mapping):
                break
            return defaults, strategy
    raise SessionControlError(f"统一中性史源目录未覆盖朝代: {dynasty}")


def _validate_bootstrap_source_scope(
    *,
    workspace_root: Path,
    dynasty: str,
    configured: Mapping[str, Any],
) -> None:
    if configured.get("neutral_scan_backbone_material_token"):
        return
    defaults, strategy = _neutral_material_strategy(workspace_root, dynasty)
    backbone_works = [
        str(work) for work in configured.get("neutral_scan_backbone_works") or ()
    ]
    normalized_backbones = {
        _normalized_work_name(work) for work in backbone_works
    }
    forbidden_fragments = {
        _normalized_work_name(fragment)
        for fragment in strategy.get("forbidden_backbone_name_fragments") or ()
    }
    for work in normalized_backbones:
        if any(fragment and fragment in work for fragment in forbidden_fragments):
            raise SessionControlError(
                f"bootstrap 连续主干禁止整套扫描高体量史书: {work}"
            )
    allowed_backbones = {
        _normalized_work_name(work)
        for work in strategy.get("ruler_chronicles") or ()
    }
    if allowed_backbones and not normalized_backbones <= allowed_backbones:
        raise SessionControlError(
            "bootstrap 连续主干不符合朝代统一书目: "
            f"{sorted(normalized_backbones)} not in {sorted(allowed_backbones)}"
        )
    backsource_works = {
        _normalized_work_name(work)
        for work in configured.get("neutral_scan_backsource_works") or ()
    }
    allowed_backsources = {
        _normalized_work_name(work)
        for work in strategy.get("event_backsource") or ()
    }
    if not backsource_works <= allowed_backsources:
        raise SessionControlError(
            "bootstrap 事件回源不符合朝代统一书目: "
            f"{sorted(backsource_works)} not in {sorted(allowed_backsources)}"
        )
    page_ranges = configured.get("neutral_scan_backbone_page_ranges") or {}
    total_pages = 0
    for work in backbone_works:
        value = page_ranges.get(work)
        if (
            not isinstance(value, Sequence)
            or isinstance(value, (str, bytes))
            or len(value) != 2
        ):
            raise SessionControlError(f"bootstrap 连续主干缺少有效页范围: {work}")
        start, end = int(value[0]), int(value[1])
        if start <= 0 or end < start:
            raise SessionControlError(f"bootstrap 连续主干页范围无效: {work}")
        total_pages += end - start + 1
    maximum = int(
        strategy.get("max_backbone_pages_per_ruler")
        or defaults.get("max_backbone_pages_per_ruler")
        or 64
    )
    if total_pages > maximum:
        raise SessionControlError(
            f"bootstrap 连续主干超过统一页数上限: {total_pages} > {maximum}"
        )


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


def _bootstrap_static_contract_fingerprint(root: Path) -> str:
    excluded = {
        "config/project.yml",
        "config/historical-entity-identities.yml",
    }
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
            relative = path.relative_to(root).as_posix()
            if relative in excluded:
                continue
            entries.append({"path": relative, "sha256": _file_sha256(path)})
    for relative_path in SESSION_RULE_DOCUMENTS:
        path = root / relative_path
        if not path.is_file():
            raise SessionControlError(f"release 缺少当前规则文档: {relative_path}")
        entries.append({"path": relative_path, "sha256": _file_sha256(path)})
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


def _provisional_ruler_ref(ruler: str) -> str:
    return f"RULER-BOOTSTRAP-{_digest({'ruler': ruler})[:16].upper()}"


def _canonical_paths(
    root: Path, configured: Mapping[str, object]
) -> dict[str, Path]:
    result = root / str(configured["result"])
    project = yaml.safe_load(
        (root / "config/project.yml").read_text(encoding="utf-8")
    )
    registry = project.get("historical_outcome_registry") or {}
    profiles = project.get("historical_person_profile_registry") or {}
    paths = {
        "source_pack": root / str(configured["source_pack"]),
        "neutral_materials": root / str(configured["neutral_materials"]),
        "result_json": result,
        "result_markdown": result.with_suffix(".md"),
        "outcome_binding": root / str(configured["outcome_binding"]),
        "outcome_registry_json": root / str(registry["current_json"]),
        "outcome_registry_markdown": root / str(registry["current_markdown"]),
        "person_profile_registry_json": root / str(profiles["current_json"]),
        "person_profile_registry_markdown": root
        / str(profiles["current_markdown"]),
    }
    current_binding = paths["outcome_binding"].resolve()
    rulers = ((project.get("i5b_current_value") or {}).get("rulers") or {})
    for ruler_name, ruler_config in rulers.items():
        if not isinstance(ruler_config, Mapping) or not ruler_config.get(
            "outcome_binding"
        ):
            continue
        binding = (root / str(ruler_config["outcome_binding"])).resolve()
        if binding != current_binding:
            paths[f"outcome_binding_{ruler_name}"] = binding
    return paths


def _is_shared_migratable_canonical(key: str) -> bool:
    """Return whether a release may refresh this shared derived baseline."""

    return key in {
        "outcome_registry_json",
        "outcome_registry_markdown",
        "person_profile_registry_json",
        "person_profile_registry_markdown",
    } or key.startswith("outcome_binding_")


def _is_empty_outcome_registry_schema_migration(
    current_path: Path, target_path: Path
) -> bool:
    """Allow only v2→v3 metadata adoption before a ruler has any outcomes."""

    if not current_path.is_file() or not target_path.is_file():
        return False
    current = _read_json(current_path)
    target = _read_json(target_path)
    for payload in (current, target):
        declared = str(payload.get("source_pack_sha256") or "")
        unsigned = dict(payload)
        unsigned.pop("source_pack_sha256", None)
        if not declared or _digest(unsigned) != declared:
            return False
        registry = payload.get("outcome_registry")
        if not isinstance(registry, Mapping) or registry.get("clusters") != []:
            return False
    current_registry = current["outcome_registry"]
    target_registry = target["outcome_registry"]
    if current_registry.get("schema_version") != "historical-outcome-cluster-registry-v2":
        return False
    if target_registry.get("schema_version") != "historical-outcome-cluster-registry-v3":
        return False
    normalized_current = json.loads(json.dumps(current, ensure_ascii=False))
    normalized_target = json.loads(json.dumps(target, ensure_ascii=False))
    for payload in (normalized_current, normalized_target):
        payload.pop("source_pack_sha256", None)
        payload["outcome_registry"].pop("schema_version", None)
    return normalized_current == normalized_target


def _prepare_outcome_review_contract_reset(
    workspace_path: Path,
    *,
    ruler: str,
    ruler_ref: str,
) -> tuple[dict[str, Any], int, int] | None:
    """Keep verified facts but invalidate v2 reviewed outcomes for a v3 replay."""

    if not workspace_path.is_file():
        return None
    payload = _read_json(workspace_path)
    declared = str(payload.get("source_pack_sha256") or "")
    unsigned = dict(payload)
    unsigned.pop("source_pack_sha256", None)
    if not declared or _digest(unsigned) != declared:
        return None
    if payload.get("ruler") != ruler or payload.get("ruler_ref") != ruler_ref:
        return None
    registry = payload.get("outcome_registry")
    if not isinstance(registry, Mapping):
        return None
    clusters = list(registry.get("clusters") or ())
    if (
        registry.get("schema_version")
        != "historical-outcome-cluster-registry-v2"
        or not clusters
        or any(not str(row.get("outcome_ref") or "") for row in clusters)
    ):
        return None
    facts = list(payload.get("facts") or ())
    if any(
        not str(row.get("record_ref") or "").startswith("PFACT-")
        or not row.get("assertions")
        for row in facts
    ):
        return None
    migrated = json.loads(json.dumps(payload, ensure_ascii=False))
    migrated["outcome_registry"] = {
        **migrated["outcome_registry"],
        "schema_version": "historical-outcome-cluster-registry-v3",
        "clusters": [],
    }
    migrated.pop("three_channel_disposition", None)
    migrated.pop("source_pack_sha256", None)
    migrated["source_pack_sha256"] = _digest(migrated)
    return migrated, len(clusters), len(facts)


def _is_session_owned_outcome_review_pack(
    workspace_path: Path,
    target_path: Path,
    *,
    ruler: str,
    ruler_ref: str,
    allow_missing_target: bool = False,
) -> bool:
    """Recognize a reset v3 fact set without equating it to a release seed."""

    if not workspace_path.is_file():
        return False
    workspace = _read_json(workspace_path)
    payloads = [workspace]
    if target_path.is_file():
        payloads.append(_read_json(target_path))
    elif not allow_missing_target:
        return False
    for payload in payloads:
        declared = str(payload.get("source_pack_sha256") or "")
        unsigned = dict(payload)
        unsigned.pop("source_pack_sha256", None)
        if (
            not declared
            or _digest(unsigned) != declared
            or payload.get("ruler") != ruler
            or payload.get("ruler_ref") != ruler_ref
            or (payload.get("outcome_registry") or {}).get("schema_version")
            != "historical-outcome-cluster-registry-v3"
            or (payload.get("outcome_registry") or {}).get("clusters")
        ):
            return False
    facts = list(workspace.get("facts") or ())
    return bool(facts) and all(
        str(row.get("record_ref") or "").startswith("PFACT-")
        and row.get("assertions")
        for row in facts
    )


def _refresh_other_ruler_source_packs(
    *,
    release_root: Path,
    workspace_root: Path,
    rulers: Mapping[str, object],
    current_ruler: str,
) -> list[str]:
    """Refresh read-only source-pack baselines owned by other ruler chains."""

    refreshed = []
    for ruler_name, ruler_config in sorted(rulers.items()):
        if ruler_name == current_ruler or not isinstance(ruler_config, Mapping):
            continue
        relative = Path(str(ruler_config["source_pack"]))
        source = release_root / relative
        if not source.is_file():
            continue
        target = workspace_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file() and _file_sha256(target) == _file_sha256(source):
            continue
        shutil.copy2(source, target)
        refreshed.append(relative.as_posix())
    return refreshed


def _control_root(state_root: Path) -> Path:
    return state_root.resolve() / "session-control"


def _session_path(state_root: Path, session_id: str) -> Path:
    return _control_root(state_root) / "sessions" / session_id / "current.json"


def _owned_resource(path: Path, session_id: str) -> bool:
    return path.is_file() and _read_json(path).get("session_id") == session_id


def _release_resources(state_root: Path, lease: Mapping[str, object]) -> None:
    session_id = str(lease["session_id"])
    control = _control_root(state_root)
    resource_ruler_ref = str(
        lease.get("resource_ruler_ref") or lease["ruler_ref"]
    )
    resource_paths = [
        control / "rulers" / f"{resource_ruler_ref}.json",
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


def _make_workspace_owner_writable(root: Path) -> None:
    """Undo read-only release modes only inside a session-owned workspace."""
    if not root.exists():
        return
    for path in (root, *root.rglob("*")):
        try:
            additions = stat.S_IWUSR
            if path.is_dir():
                additions |= stat.S_IXUSR
            path.chmod(path.stat().st_mode | additions)
        except FileNotFoundError:
            continue


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
    # The public outcome and person-profile registries are rebuilt from every
    # configured source pack,
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
    _make_workspace_owner_writable(workspace_root)


def _prepare_bootstrap_workspace(
    *,
    release_root: Path,
    workspace_root: Path,
) -> None:
    workspace_root.mkdir(parents=True, exist_ok=False)
    shutil.copytree(release_root / "config", workspace_root / "config")
    project = yaml.safe_load(
        (release_root / "config/project.yml").read_text(encoding="utf-8")
    )
    rulers = (project.get("i5b_current_value") or {}).get("rulers") or {}
    for configured in rulers.values():
        if not isinstance(configured, Mapping):
            continue
        source = release_root / str(configured.get("source_pack") or "")
        if not source.is_file():
            raise SessionControlError(f"release 缺少公共成果登记输入: {source}")
        target = workspace_root / source.relative_to(release_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    for section, fields in (
        (
            "historical_outcome_registry",
            ("current_json", "current_markdown"),
        ),
        (
            "historical_person_profile_registry",
            ("current_json", "current_markdown"),
        ),
    ):
        configured = project.get(section) or {}
        for field in fields:
            source = release_root / str(configured.get(field) or "")
            if not source.is_file():
                continue
            target = workspace_root / source.relative_to(release_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    _make_workspace_owner_writable(workspace_root)


def _bootstrap_report(
    *,
    lease: Mapping[str, object],
    missing: Sequence[str],
    spec_path: Path | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": BOOTSTRAP_REPORT_SCHEMA_VERSION,
        "status": "awaiting_bootstrap" if missing else "bootstrap_ready",
        "session_id": lease["session_id"],
        "ruler": lease["ruler"],
        "stage": lease["stage"],
        "workspace_root": lease["workspace_root"],
        "bootstrap_spec": str(spec_path) if spec_path else None,
        "missing": list(missing),
        "result_persisted": False,
        "runtime_model_call_count": 0,
        "database_write_count": 0,
        "formal_score_write_count": 0,
    }


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
    project = yaml.safe_load(
        (release_root / "config/project.yml").read_text(encoding="utf-8")
    )
    candidates = [ruler] if ruler else configured_order
    release_contract_fingerprint = _contract_fingerprint(release_root)
    candidate_specs = []
    invalid_candidates: list[str] = []
    for candidate in candidates:
        if candidate not in rulers:
            if not ruler:
                invalid_candidates.append(str(candidate))
                continue
            candidate_specs.append(
                (
                    str(candidate),
                    None,
                    _provisional_ruler_ref(str(candidate)),
                    [],
                    True,
                )
            )
            continue
        try:
            configured = rulers[candidate]
            _shared_backbone_contract(project=project, ruler=candidate)
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
                (candidate, configured, ruler_ref, shared_tokens, False)
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
    for (
        candidate,
        configured,
        ruler_ref,
        shared_tokens,
        bootstrap_required,
    ) in candidate_specs:
        base_payload = {
            "schema_version": LEASE_SCHEMA_VERSION,
            "session_id": session_id,
            "ruler": candidate,
            "ruler_ref": ruler_ref,
            "resource_ruler_ref": ruler_ref,
            "release_sha": release_sha,
            "release_contract_fingerprint": release_contract_fingerprint,
            "bootstrap_static_contract_fingerprint": (
                _bootstrap_static_contract_fingerprint(release_root)
                if bootstrap_required
                else None
            ),
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
            if bootstrap_required:
                _prepare_bootstrap_workspace(
                    release_root=release_root,
                    workspace_root=workspace_root,
                )
                canonical: dict[str, Path] = {}
            else:
                assert configured is not None
                _prepare_workspace(
                    release_root=release_root,
                    workspace_root=workspace_root,
                    ruler=candidate,
                    configured=configured,
                )
                canonical = _canonical_paths(release_root, configured)
            lease = {
                **base_payload,
                "stage": (
                    "bootstrap_required" if bootstrap_required else "claimed"
                ),
                "bootstrap_required": bootstrap_required,
                "model_slots": claimed_slots,
                "shared_tokens": claimed_shared,
                "workspace_root": str(workspace_root),
                "runtime_root": str(session_root / "runtime"),
                "shared_backbone_root": str(state_root / "shared-neutral-backbones"),
                "stage_cache_root": str(
                    state_root / "stage-cache" / ruler_ref
                ),
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
            if bootstrap_required:
                bootstrap_path = session_root / "runtime" / "bootstrap" / "current.json"
                bootstrap = _bootstrap_report(
                    lease=lease,
                    missing=[
                        "ruler_identity",
                        "ruler_window",
                        "chronicle_range",
                        "fixed_source_index",
                        "dynasty_governance_current",
                        "bootstrap_members",
                    ],
                )
                _atomic_json(bootstrap_path, bootstrap)
                lease["bootstrap_report"] = str(bootstrap_path)
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
                _make_workspace_owner_writable(session_root)
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
                _make_workspace_owner_writable(session_root)
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


def build_session_dynasty_governance(
    *,
    state_root: Path,
    session_id: str,
    release_root: Path,
    source_index_root: Path,
    dynasty_governance_root: Path,
    dynasty: str,
    codex_bin: str = "codex",
    model_timeout_seconds: int = 120,
    target_chars: int = 2_400,
) -> dict[str, Any]:
    session_id = _safe_token(session_id, field="session_id")
    path = _session_path(state_root, session_id)
    if not path.is_file():
        raise SessionControlError("会话租约不存在")
    lease = _read_json(path)
    release_root = release_root.resolve()
    if _release_identity(release_root) != lease.get("release_sha"):
        raise SessionControlError("政书构建 release 与认领 release 不一致")
    if _contract_fingerprint(release_root) != lease.get(
        "release_contract_fingerprint"
    ):
        raise SessionControlError("政书构建 release 合同在认领后发生变化")
    workspace_root = Path(str(lease["workspace_root"])).resolve()
    dynasty_governance_root = dynasty_governance_root.resolve()
    if dynasty_governance_root == workspace_root or workspace_root in (
        dynasty_governance_root,
        *dynasty_governance_root.parents,
    ):
        raise SessionControlError("朝代政书 current 根不得位于皇帝 workspace")
    canonical_dynasty, configured = load_dynasty_governance_catalog_entry(
        workspace_root, dynasty
    )
    token = _safe_token(
        configured.get("dynasty_token"), field="dynasty_governance_token"
    )
    project = yaml.safe_load(
        (workspace_root / "config/project.yml").read_text(encoding="utf-8")
    )
    ruler_config = (
        (project.get("i5b_current_value") or {}).get("rulers") or {}
    ).get(str(lease["ruler"])) or {}
    expected_token = str(
        ruler_config.get("dynasty_governance_material_token") or ""
    )
    if expected_token != token:
        raise SessionControlError(
            "当前皇帝的朝代治理 token 与请求目录不匹配: "
            f"{expected_token or '<missing>'} != {token}"
        )
    works = tuple(
        str(row.get("work") or "").strip()
        for row in configured.get("source_works") or ()
        if isinstance(row, Mapping) and str(row.get("work") or "").strip()
    )
    if not works:
        raise SessionControlError(f"{canonical_dynasty}: 政书目录没有有效书目")
    try:
        source_index = _resolve_source_index(
            # A dynasty-governance index is selected only for the catalogued
            # specialist works.  Ruler source-pack facts belong to the later
            # chronicle/person stages and must not widen this shared index.
            source_pack={"facts": []},
            source_index_path=None,
            source_index_root=source_index_root,
            required_works=works,
        )
    except (OSError, ValueError) as exc:
        return {
            "schema_version": SESSION_DYNASTY_GOVERNANCE_SCHEMA_VERSION,
            "status": "awaiting_governance_source_assets",
            "session_id": session_id,
            "ruler": lease["ruler"],
            "dynasty": canonical_dynasty,
            "dynasty_token": token,
            "required_source_works": list(works),
            "source_catalog": configured,
            "missing": [f"fixed_governance_source_index: {exc}"],
            "shared_current_path": str(
                dynasty_governance_root / token / "current.json"
            ),
            "runtime_model_call_count": 0,
            "database_write_count": 0,
            "formal_score_write_count": 0,
        }
    required_page_titles = sorted(
        {
            str(page_title)
            for source in configured.get("source_works") or ()
            if isinstance(source, Mapping)
            for page_title in source.get("page_titles") or ()
            if str(page_title).strip()
        }
    )
    if required_page_titles:
        available_page_titles = {
            str(page.page_title)
            for page in source_index.iter_pages(works=works)
        }
        missing_page_titles = sorted(
            set(required_page_titles) - available_page_titles
        )
        if missing_page_titles:
            return {
                "schema_version": SESSION_DYNASTY_GOVERNANCE_SCHEMA_VERSION,
                "status": "awaiting_governance_source_assets",
                "session_id": session_id,
                "ruler": lease["ruler"],
                "dynasty": canonical_dynasty,
                "dynasty_token": token,
                "required_source_works": list(works),
                "required_page_titles": required_page_titles,
                "missing": [
                    "fixed_governance_source_pages: "
                    + ", ".join(missing_page_titles)
                ],
                "source_catalog": configured,
                "shared_current_path": str(
                    dynasty_governance_root / token / "current.json"
                ),
                "runtime_model_call_count": 0,
                "database_write_count": 0,
                "formal_score_write_count": 0,
            }
    lock_path = dynasty_governance_root / ".locks" / f"{token}.lock"
    with _exclusive_lock(lock_path) as locked:
        if not locked:
            return {
                "schema_version": SESSION_DYNASTY_GOVERNANCE_SCHEMA_VERSION,
                "status": "already_running",
                "session_id": session_id,
                "ruler": lease["ruler"],
                "dynasty": canonical_dynasty,
                "dynasty_token": token,
                "runtime_model_call_count": 0,
                "database_write_count": 0,
                "formal_score_write_count": 0,
            }
        result = rebuild_dynasty_governance(
            dynasty=canonical_dynasty,
            source_index_path=source_index.path,
            runtime_root=dynasty_governance_root,
            workspace_root=workspace_root,
            limits=DynastyGovernanceLimits(
                model_workers=len(lease.get("model_slots") or ()),
                model_timeout_seconds=model_timeout_seconds,
                target_chars=target_chars,
            ),
            codex_bin=codex_bin,
            use_catalog=True,
        )
    lease["updated_at"] = _now()
    _atomic_json(path, lease)
    return {
        "schema_version": SESSION_DYNASTY_GOVERNANCE_SCHEMA_VERSION,
        "status": "reused" if result.get("reused") else "quality_accepted",
        "session_id": session_id,
        "ruler": lease["ruler"],
        "dynasty": canonical_dynasty,
        "dynasty_token": token,
        "source_index": str(source_index.path),
        "source_index_identity": source_index.identity,
        "shared_current_path": str(
            dynasty_governance_root / token / "current.json"
        ),
        "runtime_model_call_count": int(result.get("model_call_count") or 0),
        "database_write_count": 0,
        "formal_score_write_count": 0,
        "quality": result.get("quality"),
    }


def complete_session_bootstrap(
    *,
    state_root: Path,
    session_id: str,
    bootstrap_spec_path: Path,
    source_index_root: Path,
    dynasty_governance_root: Path,
) -> dict[str, Any]:
    session_id = _safe_token(session_id, field="session_id")
    path = _session_path(state_root, session_id)
    if not path.is_file():
        raise SessionControlError("会话租约不存在")
    lease = _read_json(path)
    revising_failed_source_scope = bool(
        lease.get("bootstrap_scope_revision")
    ) or (
        lease.get("bootstrap_required") is not True
        and bool(lease.get("bootstrap_spec"))
        and lease.get("stage") == "failed_reusable"
    )
    if (
        lease.get("bootstrap_required") is not True
        and not revising_failed_source_scope
    ):
        raise SessionControlError("该会话不处于首次 bootstrap 阶段")
    spec = _read_json(bootstrap_spec_path.resolve())
    if spec.get("schema_version") != BOOTSTRAP_SCHEMA_VERSION:
        raise SessionControlError("bootstrap spec 版本不支持")
    ruler = str(lease["ruler"])
    if str(spec.get("ruler") or "") != ruler:
        raise SessionControlError("bootstrap spec 皇帝与租约不匹配")
    if revising_failed_source_scope:
        previous_spec = _read_json(Path(str(lease["bootstrap_spec"])))
        immutable_fields = (
            "ruler",
            "ruler_ref",
            "dynasty",
            "window",
            "members",
            "identity_entries",
        )
        if any(
            previous_spec.get(field) != spec.get(field)
            for field in immutable_fields
        ):
            raise SessionControlError(
                "failed_reusable 只允许修订 bootstrap 史源范围"
            )
    ruler_ref = _safe_token(spec.get("ruler_ref"), field="ruler_ref")
    dynasty = str(spec.get("dynasty") or "").strip()
    window = str(spec.get("window") or "").strip()
    configured = spec.get("ruler_config")
    members = spec.get("members") or []
    identities = spec.get("identity_entries") or []
    if not dynasty or not window:
        raise SessionControlError("bootstrap spec 缺少 dynasty 或 window")
    if not isinstance(configured, Mapping):
        raise SessionControlError("bootstrap spec ruler_config 必须是 object")
    if not isinstance(members, list) or not isinstance(identities, list):
        raise SessionControlError("bootstrap spec members/identity_entries 必须是数组")
    expected_paths = {
        "source_pack": f"eval/i5b_current_value/{ruler}/source-pack.json",
        "neutral_materials": f"eval/i5b_current_value/{ruler}/neutral-materials.json",
        "result": f"eval/i5b_current_value/{ruler}/result.json",
        "outcome_binding": f"eval/historical_outcome_bindings/{ruler}.json",
    }
    for field, expected in expected_paths.items():
        if str(configured.get(field) or "") != expected:
            raise SessionControlError(
                f"bootstrap ruler_config {field} 必须为 {expected}"
            )
    if not configured.get("dynasty_governance_material_token"):
        raise SessionControlError("bootstrap ruler_config 缺少朝代治理 token")
    catalog_dynasty, governance_catalog = (
        load_dynasty_governance_catalog_entry(
            Path(str(lease["workspace_root"])), dynasty
        )
    )
    governance_token = str(
        configured["dynasty_governance_material_token"]
    )
    catalog_token = str(governance_catalog.get("dynasty_token") or "")
    if governance_token != catalog_token:
        raise SessionControlError(
            "bootstrap 朝代治理 token 与统一政书目录不匹配: "
            f"{governance_token} != {catalog_token}"
        )
    if not configured.get("neutral_scan_backbone_material_token") and (
        not configured.get("neutral_scan_backbone_works")
        or not configured.get("neutral_scan_backbone_page_ranges")
    ):
        raise SessionControlError("bootstrap ruler_config 缺少编年主干及连续范围")
    configured = dict(configured)
    _validate_bootstrap_source_scope(
        workspace_root=Path(str(lease["workspace_root"])),
        dynasty=dynasty,
        configured=configured,
    )
    if not configured.get("neutral_scan_backbone_material_token"):
        ruler_heading_terms = list(
            configured.get("neutral_scan_ruler_heading_terms")
            or configured.get("dynasty_governance_period_terms")
            or ()
        )
        if not ruler_heading_terms:
            raise SessionControlError("bootstrap 独占编年主干缺少皇帝标题词")
        configured["neutral_scan_ruler_heading_terms"] = ruler_heading_terms
    spec = {**spec, "ruler_config": configured}

    member_rows = []
    for member in members:
        if not isinstance(member, Mapping):
            raise SessionControlError("bootstrap member 必须是 object")
        person = str(member.get("person") or "").strip()
        person_ref = _safe_token(member.get("person_ref"), field="person_ref")
        if not person:
            raise SessionControlError("bootstrap member 缺少 person")
        member_rows.append({"person": person, "person_ref": person_ref})
    expected_identities = {
        ruler: ruler_ref,
        **{row["person"]: row["person_ref"] for row in member_rows},
    }
    supplied_identities = {}
    for identity in identities:
        if not isinstance(identity, Mapping):
            raise SessionControlError("bootstrap identity entry 必须是 object")
        name = str(identity.get("canonical_name") or "").strip()
        person_ref = _safe_token(identity.get("person_ref"), field="person_ref")
        if not name or str(identity.get("dynasty") or "") != dynasty:
            raise SessionControlError("bootstrap identity 缺少姓名或朝代不匹配")
        supplied_identities[name] = person_ref
    if any(
        supplied_identities.get(name) != person_ref
        for name, person_ref in expected_identities.items()
    ):
        raise SessionControlError("bootstrap identity 未覆盖皇帝及全部候选成员")

    workspace_root = Path(str(lease["workspace_root"]))
    project_path = workspace_root / "config/project.yml"
    project = yaml.safe_load(project_path.read_text(encoding="utf-8"))
    project.setdefault("i5b_current_value", {}).setdefault("rulers", {})[
        ruler
    ] = dict(configured)
    _shared_backbone_contract(project=project, ruler=ruler)
    project_path.write_text(
        yaml.safe_dump(project, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
        newline="\n",
    )

    identity_path = workspace_root / "config/historical-entity-identities.yml"
    identity_catalog = yaml.safe_load(identity_path.read_text(encoding="utf-8"))
    existing_by_name = {
        str(row["canonical_name"]): row
        for row in identity_catalog.get("entities") or ()
    }
    for identity in identities:
        row = dict(identity)
        name = str(row["canonical_name"])
        existing = existing_by_name.get(name)
        if existing is not None and str(existing.get("person_ref")) != str(
            row["person_ref"]
        ):
            raise SessionControlError(f"bootstrap identity 与现有身份冲突: {name}")
        if existing is None:
            identity_catalog.setdefault("entities", []).append(row)
    identity_path.write_text(
        yaml.safe_dump(identity_catalog, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
        newline="\n",
    )

    source_pack = {
        "schema_version": "i5b-current-value-source-pack-v5",
        "status": "bootstrap_ready_for_first_session",
        "ruler": ruler,
        "ruler_ref": ruler_ref,
        "window": window,
        "members": member_rows,
        "facts": [],
        "materials": [],
        "ruler_context_materials": [],
        "excluded_units": [],
        "outcome_registry": {
            "schema_version": "historical-outcome-cluster-registry-v3",
            "status": "shadow",
            "clusters": [],
        },
        "profile_projection_gate": {
            "status": "material_coverage_open",
            "material_coverage_complete": False,
            "freeze_allowed": False,
            "candidate_roster_review": {
                "status": "bootstrap_open",
                "coverage": [
                    "ruler_window_appointments",
                    "outcome_participants",
                    "potential_top_full_career",
                ],
            },
        },
        "declarations": {
            "shadow_only": True,
            "formal_write": False,
            "model_call_count": 0,
            "database_write_count": 0,
            "formal_score_write_count": 0,
        },
    }
    source_pack["source_pack_sha256"] = _digest(source_pack)
    source_pack_path = workspace_root / expected_paths["source_pack"]
    _atomic_json(source_pack_path, source_pack)

    runtime_spec_path = (
        Path(str(lease["runtime_root"])) / "bootstrap" / "spec.json"
    )
    _atomic_json(runtime_spec_path, spec)
    missing: list[str] = []
    shared_contract = _shared_backbone_contract(project=project, ruler=ruler)
    backbone_works = (
        list(shared_contract["works"])
        if shared_contract is not None
        else list(configured.get("neutral_scan_backbone_works") or ())
    )
    required_works = [
        *backbone_works,
        *list(configured.get("neutral_scan_backsource_works") or ()),
    ]
    source_index = None
    try:
        source_index = _resolve_source_index(
            source_pack=source_pack,
            source_index_path=None,
            source_index_root=source_index_root,
            required_works=required_works,
        )
    except (OSError, ValueError) as exc:
        missing.append(f"fixed_source_index: {exc}")
    governance_path = dynasty_governance_root / governance_token / "current.json"
    if source_index is None:
        missing.append("dynasty_governance_current: 等待固定索引")
    elif not governance_path.is_file():
        missing.append(f"dynasty_governance_current: {governance_path}")
    else:
        governance = _read_json(governance_path)
        invalid_governance = (
            governance.get("schema_version") != "dynasty-governance-current-v2"
            or governance.get("status") != "quality_accepted_shadow"
            or str(governance.get("dynasty_token") or "") != governance_token
            or not str(governance.get("source_index_identity") or "")
        )
        try:
            validate_dynasty_governance_current_catalog(
                governance, governance_catalog
            )
        except ValueError:
            invalid_governance = True
        if invalid_governance:
            missing.append("dynasty_governance_current: 头部合同不匹配")

    shared_tokens = []
    token = str(configured.get("neutral_scan_backbone_material_token") or "")
    if not missing and token:
        token_path = _control_root(state_root) / "shared-writers" / f"{token}.json"
        if not _claim_json(token_path, lease):
            missing.append(f"shared_chronicle_writer: {token}")
        else:
            shared_tokens.append(token)
    if missing:
        lease["bootstrap_required"] = True
        if revising_failed_source_scope:
            lease["bootstrap_scope_revision"] = True
        lease["stage"] = "bootstrap_assets_required"
        lease["bootstrap_spec"] = str(runtime_spec_path)
        lease["updated_at"] = _now()
        report = _bootstrap_report(
            lease=lease,
            missing=missing,
            spec_path=runtime_spec_path,
        )
        report["dynasty_governance_assets"] = {
            "dynasty": catalog_dynasty,
            "dynasty_token": governance_token,
            "source_catalog": governance_catalog,
            "shared_current_path": str(governance_path),
            "ownership": "dynasty_shared_not_ruler_workspace",
            "build_command": "emperor-session-dynasty-governance",
        }
        _atomic_json(Path(str(lease["bootstrap_report"])), report)
        _atomic_json(path, lease)
        return report

    canonical = _canonical_paths(workspace_root, configured)
    lease.update(
        {
            "ruler_ref": ruler_ref,
            "bootstrap_required": False,
            "bootstrap_spec": str(runtime_spec_path),
            "stage": "claimed",
            "shared_tokens": shared_tokens,
            "stage_cache_root": str(
                state_root.resolve() / "stage-cache" / ruler_ref
            ),
            "canonical_expected_sha256": {
                key: None
                if key in {"source_pack", "neutral_materials", "result_json",
                           "result_markdown", "outcome_binding"}
                else _file_sha256(
                    Path(str(lease["workspace_root"])).resolve()
                    / target.relative_to(workspace_root)
                )
                for key, target in canonical.items()
            },
            "input_fingerprint": _digest(
                {
                    "release_sha": lease["release_sha"],
                    "ruler": ruler,
                    "bootstrap_spec": spec,
                    "source_index_identity": source_index.identity,
                }
            ),
            "updated_at": _now(),
        }
    )
    lease.pop("bootstrap_scope_revision", None)
    report = _bootstrap_report(
        lease=lease,
        missing=[],
        spec_path=runtime_spec_path,
    )
    _atomic_json(Path(str(lease["bootstrap_report"])), report)
    _atomic_json(path, lease)
    return report


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
    stop_after_stage: str | None = None,
    outcome_review_path: Path | None = None,
    allow_outcome_model_draft: bool = False,
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
    if lease.get("bootstrap_required") is True:
        report_path = Path(str(lease["bootstrap_report"]))
        report = _read_json(report_path)
        return {**report, "reused": True}
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

    def update_stage(
        stage: str, status: str, details: Mapping[str, Any]
    ) -> None:
        lease["stage"] = str(stage)
        lease["stage_status"] = str(status)
        lease["stage_input_fingerprint"] = details.get("input_fingerprint")
        lease["stage_producer_contract_fingerprint"] = details.get(
            "producer_contract_fingerprint"
        )
        lease["updated_at"] = _now()
        _atomic_json(path, lease)

    try:
        report = rebuild_emperor(
            workspace_root=Path(str(lease["workspace_root"])),
            ruler=str(lease["ruler"]),
            source_index_path=None,
            source_index_root=source_index_root,
            dynasty_governance_root=dynasty_governance_root,
            shared_backbone_root=Path(str(lease["shared_backbone_root"])),
            stage_cache_root=Path(str(lease["stage_cache_root"])),
            runtime_root=Path(str(lease["runtime_root"])),
            limits=limits,
            stage_callback=update_stage,
            stop_after_stage=stop_after_stage,
            outcome_review_path=outcome_review_path,
            allow_outcome_model_draft=allow_outcome_model_draft,
        )
        stage_results = list(report.get("stage_results") or ())
        observed_stages = [str(row.get("stage") or "") for row in stage_results]
        if report.get("status") == "awaiting_review":
            review_stage = str(report.get("review_stage") or "")
            if review_stage not in REQUIRED_REBUILD_STAGES:
                raise SessionControlError("人工审阅阶段不属于受监督职责链")
            expected_stages = list(REQUIRED_REBUILD_STAGES)[
                : list(REQUIRED_REBUILD_STAGES).index(review_stage) + 1
            ]
            if observed_stages != expected_stages or any(
                row.get("status") not in {"quality_accepted", "reused"}
                or not row.get("input_fingerprint")
                or not row.get("producer_contract_fingerprint")
                for row in stage_results
            ):
                raise SessionControlError("人工审阅前的阶段监督清单不完整")
            review = {
                **report,
                "session_id": session_id,
                "release_sha": lease["release_sha"],
                "input_fingerprint": lease["input_fingerprint"],
                "limits": asdict(limits),
                "reused": False,
            }
            _atomic_json(
                Path(str(lease["runtime_root"])) / "review.json",
                review,
            )
            lease["stage"] = "awaiting_review"
            lease["review_stage"] = review_stage
            lease["updated_at"] = _now()
            _atomic_json(path, lease)
            return review
        if observed_stages != list(REQUIRED_REBUILD_STAGES) or any(
            row.get("status") not in {"quality_accepted", "reused"}
            or not row.get("input_fingerprint")
            or not row.get("producer_contract_fingerprint")
            for row in stage_results
        ):
            raise SessionControlError("阶段监督清单不完整，禁止进入发布状态")
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
    lease.pop("stage_status", None)
    lease.pop("stage_input_fingerprint", None)
    lease.pop("stage_producer_contract_fingerprint", None)
    _atomic_json(path, lease)
    return completed


def upgrade_failed_session_release(
    *,
    state_root: Path,
    session_id: str,
    release_root: Path,
) -> dict[str, Any]:
    """Adopt a repaired immutable release without discarding checkpoints."""

    session_id = _safe_token(session_id, field="session_id")
    path = _session_path(state_root, session_id)
    if not path.is_file():
        raise SessionControlError("会话租约不存在")
    lease = _read_json(path)
    stage = str(lease.get("stage") or "")
    bootstrap_session = bool(lease.get("bootstrap_spec"))
    allowed_stages = {"failed_reusable", "awaiting_review"}
    if bootstrap_session:
        allowed_stages.add("bootstrap_assets_required")
    if stage not in allowed_stages:
        raise SessionControlError(
            "只有 failed_reusable、awaiting_review，或等待资产的 bootstrap "
            "会话可以升级 release"
        )
    control = _control_root(state_root)
    resource_ruler_ref = str(
        lease.get("resource_ruler_ref") or lease["ruler_ref"]
    )
    owned_resources = [
        control / "rulers" / f"{resource_ruler_ref}.json",
        *(
            control / "model-slots" / f"{int(slot)}.json"
            for slot in lease.get("model_slots") or ()
        ),
    ]
    if not all(_owned_resource(resource, session_id) for resource in owned_resources):
        raise SessionControlError("会话资源租约不完整，拒绝升级 release")

    release_root = release_root.resolve()
    target_release_sha = _release_identity(release_root)
    target_contract_fingerprint = _contract_fingerprint(release_root)
    rulers, _ = _project_rulers(release_root)
    configured = rulers.get(str(lease["ruler"]))
    workspace_root = Path(str(lease["workspace_root"]))
    workspace_project_path = workspace_root / "config/project.yml"
    workspace_project = yaml.safe_load(
        workspace_project_path.read_text(encoding="utf-8")
    )
    if not isinstance(configured, Mapping) and bootstrap_session:
        configured = (
            (workspace_project.get("i5b_current_value") or {}).get("rulers")
            or {}
        ).get(str(lease["ruler"]))
    if not isinstance(configured, Mapping):
        raise SessionControlError("目标 release 已移除当前皇帝")
    expected = dict(lease.get("canonical_expected_sha256") or {})
    target_canonical = _canonical_paths(release_root, configured)
    changed_inputs = [
        key
        for key, target in target_canonical.items()
        if expected.get(key) is not None
        and _file_sha256(target) != expected.get(key)
    ]
    workspace_source_pack = workspace_root / str(configured["source_pack"])
    outcome_review_contract_reset = None
    if stage == "awaiting_review" and lease.get("review_stage") == (
        "outcome_projection"
    ):
        outcome_review_contract_reset = _prepare_outcome_review_contract_reset(
            workspace_source_pack,
            ruler=str(lease["ruler"]),
            ruler_ref=str(lease["ruler_ref"]),
        )
    if expected.get("source_pack") is not None:
        if _file_sha256(workspace_source_pack) != expected.get("source_pack"):
            if outcome_review_contract_reset is None:
                raise SessionControlError("会话 workspace source-pack 已偏离认领输入")
    current_ruler_source_pack_schema_migration = (
        "source_pack" in changed_inputs
        and expected.get("source_pack") is not None
        and _is_empty_outcome_registry_schema_migration(
            workspace_source_pack, target_canonical["source_pack"]
        )
    )
    session_owned_outcome_review_pack = (
        "source_pack" in changed_inputs
        and expected.get("source_pack") is not None
        and _file_sha256(workspace_source_pack) == expected.get("source_pack")
        and _is_session_owned_outcome_review_pack(
            workspace_source_pack,
            target_canonical["source_pack"],
            ruler=str(lease["ruler"]),
            ruler_ref=str(lease["ruler_ref"]),
            allow_missing_target=bootstrap_session,
        )
    )
    protected_changes = [
        key
        for key in changed_inputs
        if not _is_shared_migratable_canonical(key)
        and not (
            key == "source_pack" and current_ruler_source_pack_schema_migration
        )
        and not (key == "source_pack" and outcome_review_contract_reset is not None)
        and not (key == "source_pack" and session_owned_outcome_review_pack)
    ]
    if protected_changes:
        raise SessionControlError(
            "目标 release 改变了会话已认领的 canonical 输入: "
            + ", ".join(protected_changes)
        )
    shared_canonical_migrations = [
        key for key in changed_inputs if _is_shared_migratable_canonical(key)
    ]
    if expected.get("source_pack") is None:
        source_pack = _read_json(workspace_source_pack)
        source_pack_digest = str(source_pack.pop("source_pack_sha256", ""))
        if (
            source_pack.get("ruler") != lease["ruler"]
            or source_pack.get("ruler_ref") != lease["ruler_ref"]
            or _digest(source_pack) != source_pack_digest
        ):
            raise SessionControlError("bootstrap workspace source-pack 身份或摘要无效")
    preserved_bootstrap_ruler_config = None
    preserved_bootstrap_identities = []
    if bootstrap_session:
        preserved_bootstrap_ruler_config = dict(
            (
                (workspace_project.get("i5b_current_value") or {}).get(
                    "rulers"
                )
                or {}
            ).get(str(lease["ruler"]))
            or {}
        )
        workspace_identity_path = (
            workspace_root / "config/historical-entity-identities.yml"
        )
        if workspace_identity_path.is_file():
            workspace_identities = yaml.safe_load(
                workspace_identity_path.read_text(encoding="utf-8")
            )
            preserved_bootstrap_identities = list(
                workspace_identities.get("entities") or ()
            )
    release_config_root = release_root / "config"
    workspace_config_root = workspace_root / "config"
    for source in sorted(
        value for value in release_config_root.rglob("*") if value.is_file()
    ):
        target = workspace_config_root / source.relative_to(release_config_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    workspace_project = yaml.safe_load(
        workspace_project_path.read_text(encoding="utf-8")
    )
    if bootstrap_session:
        if not preserved_bootstrap_ruler_config:
            raise SessionControlError("bootstrap workspace 皇帝配置缺失")
        workspace_project.setdefault("i5b_current_value", {}).setdefault(
            "rulers", {}
        )[str(lease["ruler"])] = preserved_bootstrap_ruler_config
        workspace_identity_path = (
            workspace_root / "config/historical-entity-identities.yml"
        )
        refreshed_identities = yaml.safe_load(
            workspace_identity_path.read_text(encoding="utf-8")
        )
        refreshed_by_name = {
            str(row.get("canonical_name") or ""): row
            for row in refreshed_identities.get("entities") or ()
        }
        for row in preserved_bootstrap_identities:
            name = str(row.get("canonical_name") or "")
            existing = refreshed_by_name.get(name)
            if existing is not None and str(existing.get("person_ref") or "") != str(
                row.get("person_ref") or ""
            ):
                raise SessionControlError(
                    f"目标 release 与 bootstrap 身份冲突: {name}"
                )
            if existing is None:
                refreshed_identities.setdefault("entities", []).append(row)
                refreshed_by_name[name] = row
        workspace_identity_path.write_text(
            yaml.safe_dump(
                refreshed_identities, allow_unicode=True, sort_keys=False
            ),
            encoding="utf-8",
            newline="\n",
        )
        configured = dict(configured)
        if (
            not configured.get("neutral_scan_backbone_material_token")
            and not configured.get("neutral_scan_ruler_heading_terms")
        ):
            heading_terms = list(
                configured.get("dynasty_governance_period_terms") or ()
            )
            if not heading_terms:
                raise SessionControlError("bootstrap workspace 缺少皇帝编年标题词")
            configured["neutral_scan_ruler_heading_terms"] = heading_terms
            workspace_project["i5b_current_value"]["rulers"][
                str(lease["ruler"])
            ] = configured
    workspace_project_path.write_text(
        yaml.safe_dump(
            workspace_project, allow_unicode=True, sort_keys=False
        ),
        encoding="utf-8",
        newline="\n",
    )
    if outcome_review_contract_reset is not None:
        _atomic_json(workspace_source_pack, outcome_review_contract_reset[0])
    elif current_ruler_source_pack_schema_migration:
        shutil.copy2(target_canonical["source_pack"], workspace_source_pack)
    other_ruler_canonical_refreshes = _refresh_other_ruler_source_packs(
        release_root=release_root,
        workspace_root=workspace_root,
        rulers=rulers,
        current_ruler=str(lease["ruler"]),
    )

    previous_release_sha = str(lease["release_sha"])
    lease["release_sha"] = target_release_sha
    lease["release_contract_fingerprint"] = target_contract_fingerprint
    for key in shared_canonical_migrations:
        lease.setdefault("canonical_expected_sha256", {})[key] = _file_sha256(
            target_canonical[key]
        )
    if (
        current_ruler_source_pack_schema_migration
        or outcome_review_contract_reset is not None
    ):
        lease.setdefault("canonical_expected_sha256", {})["source_pack"] = (
            _file_sha256(workspace_source_pack)
        )
    if bootstrap_session:
        lease["bootstrap_static_contract_fingerprint"] = (
            _bootstrap_static_contract_fingerprint(release_root)
        )
    lease["updated_at"] = _now()
    _atomic_json(path, lease)
    return {
        "schema_version": RELEASE_UPGRADE_SCHEMA_VERSION,
        "status": "failed_session_release_upgraded",
        "session_id": session_id,
        "ruler": lease["ruler"],
        "from_release_sha": previous_release_sha,
        "release_sha": target_release_sha,
        "checkpoint_preserved": True,
        "workspace_preserved": True,
        "shared_canonical_migrations": shared_canonical_migrations,
        "current_ruler_source_pack_schema_migration": (
            "empty_outcome_registry_v2_to_v3"
            if current_ruler_source_pack_schema_migration
            else None
        ),
        "outcome_review_contract_reset": (
            {
                "invalidated_outcome_count": outcome_review_contract_reset[1],
                "preserved_fact_count": outcome_review_contract_reset[2],
                "review_payload_reuse_allowed": False,
            }
            if outcome_review_contract_reset is not None
            else None
        ),
        "session_owned_outcome_review_pack_preserved": (
            session_owned_outcome_review_pack
        ),
        "other_ruler_canonical_refreshes": other_ruler_canonical_refreshes,
        "database_write_count": 0,
        "formal_score_write_count": 0,
    }


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
    person_profiles = _read_json(paths["person_profile_registry_json"])
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
    if (
        (person_profiles.get("declarations") or {}).get(
            "outcome_registry_fingerprint"
        )
        != outcome_registry.get("registry_fingerprint")
        or report.get("person_profile_registry_fingerprint")
        != person_profiles.get("registry_fingerprint")
        or not report.get("person_profile_registry_ref")
        or (
            workspace_root / str(report["person_profile_registry_ref"])
        ).resolve()
        != paths["person_profile_registry_json"].resolve()
    ):
        raise SessionControlError("共享人物画像与成果总登记或皇帝结果不一致")
    project = yaml.safe_load(
        (workspace_root / "config/project.yml").read_text(encoding="utf-8")
    )
    rulers = ((project.get("i5b_current_value") or {}).get("rulers") or {})
    for ruler_name, ruler_config in rulers.items():
        if not isinstance(ruler_config, Mapping):
            continue
        other_source_pack = _read_json(
            workspace_root / str(ruler_config["source_pack"])
        )
        other_binding = _read_json(
            workspace_root / str(ruler_config["outcome_binding"])
        )
        materialized = materialize_ruler_outcome_registry(
            outcome_registry, other_binding
        )
        direct_outcome_refs = {
            str(row["outcome_ref"])
            for row in other_binding["bindings"]
            if not row.get("context_only_ancestor")
        }
        direct_materialized = {
            **materialized,
            "clusters": [
                cluster
                for cluster in materialized["clusters"]
                if str(cluster["outcome_ref"]) in direct_outcome_refs
            ],
        }
        if direct_materialized != other_source_pack.get("outcome_registry"):
            raise SessionControlError(
                f"{ruler_name} 成果绑定无法无损还原 source-pack"
            )
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


def _merge_bootstrap_project(
    *,
    canonical_path: Path,
    workspace_path: Path,
    ruler: str,
) -> str:
    canonical = yaml.safe_load(canonical_path.read_text(encoding="utf-8"))
    workspace = yaml.safe_load(workspace_path.read_text(encoding="utf-8"))
    canonical_rulers = canonical.setdefault("i5b_current_value", {}).setdefault(
        "rulers", {}
    )
    workspace_configured = (
        (workspace.get("i5b_current_value") or {}).get("rulers") or {}
    ).get(ruler)
    if not isinstance(workspace_configured, Mapping):
        raise SessionControlError("bootstrap workspace 缺少目标皇帝配置")
    existing = canonical_rulers.get(ruler)
    if existing is not None and dict(existing) != dict(workspace_configured):
        raise SessionControlError("canonical 已存在不同的目标皇帝配置")
    if existing is not None:
        return canonical_path.read_text(encoding="utf-8")
    canonical_rulers[ruler] = dict(workspace_configured)
    _shared_backbone_contract(project=canonical, ruler=ruler)
    text = canonical_path.read_text(encoding="utf-8")
    marker = "  settlement_mode:"
    if text.count(marker) != 1:
        raise SessionControlError("config/project.yml 皇帝配置插入锚点不唯一")
    rendered = yaml.safe_dump(
        {ruler: dict(workspace_configured)},
        allow_unicode=True,
        sort_keys=False,
    ).rstrip()
    block = "\n".join(f"    {line}" for line in rendered.splitlines()) + "\n"
    return text.replace(marker, block + marker, 1)


def _merge_bootstrap_identities(
    *,
    canonical_path: Path,
    workspace_path: Path,
    ruler: str,
) -> str:
    canonical = yaml.safe_load(canonical_path.read_text(encoding="utf-8"))
    workspace = yaml.safe_load(workspace_path.read_text(encoding="utf-8"))
    canonical_by_name = {
        str(row["canonical_name"]): row
        for row in canonical.get("entities") or ()
    }
    workspace_by_name = {
        str(row["canonical_name"]): row
        for row in workspace.get("entities") or ()
    }
    if ruler not in workspace_by_name:
        raise SessionControlError("bootstrap workspace 身份目录缺少目标皇帝")
    additions = []
    for name, row in workspace_by_name.items():
        existing = canonical_by_name.get(name)
        if existing is not None:
            if str(existing.get("person_ref")) != str(row.get("person_ref")):
                raise SessionControlError(f"canonical 身份冲突: {name}")
            continue
        additions.append(row)
    if not additions:
        return canonical_path.read_text(encoding="utf-8")
    rendered = yaml.safe_dump(
        additions,
        allow_unicode=True,
        sort_keys=False,
    ).rstrip()
    block = "\n".join(f"  {line}" for line in rendered.splitlines()) + "\n"
    text = canonical_path.read_text(encoding="utf-8")
    return text.rstrip() + "\n" + block


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
    bootstrap_session = bool(lease.get("bootstrap_spec"))
    if bootstrap_session:
        if _bootstrap_static_contract_fingerprint(canonical_root) != lease.get(
            "bootstrap_static_contract_fingerprint"
        ):
            raise SessionControlError("canonical 通用代码或规则在会话运行期间已变化")
    elif _contract_fingerprint(canonical_root) != lease.get(
        "release_contract_fingerprint"
    ):
        raise SessionControlError("canonical 代码或配置在会话运行期间已变化")
    rulers, _ = _project_rulers(canonical_root)
    configured = rulers.get(str(lease["ruler"]))
    if not isinstance(configured, Mapping) and bootstrap_session:
        workspace_project = yaml.safe_load(
            (
                Path(str(lease["workspace_root"])) / "config/project.yml"
            ).read_text(encoding="utf-8")
        )
        configured = (
            (workspace_project.get("i5b_current_value") or {}).get("rulers")
            or {}
        ).get(str(lease["ruler"]))
    if not isinstance(configured, Mapping):
        raise SessionControlError("canonical 已移除目标皇帝配置")
    source_paths = _validate_publish_payload(
        workspace_root=Path(str(lease["workspace_root"])),
        configured=configured,
        ruler=str(lease["ruler"]),
    )
    target_paths = _canonical_paths(canonical_root, configured)
    generated_root = path.parent / "publish-generated"
    if bootstrap_session:
        generated_root.mkdir(parents=True, exist_ok=True)
        project_source = generated_root / "project.yml"
        project_source.write_text(
            _merge_bootstrap_project(
                canonical_path=canonical_root / "config/project.yml",
                workspace_path=Path(str(lease["workspace_root"]))
                / "config/project.yml",
                ruler=str(lease["ruler"]),
            ),
            encoding="utf-8",
            newline="\n",
        )
        identity_source = generated_root / "historical-entity-identities.yml"
        identity_source.write_text(
            _merge_bootstrap_identities(
                canonical_path=canonical_root
                / "config/historical-entity-identities.yml",
                workspace_path=Path(str(lease["workspace_root"]))
                / "config/historical-entity-identities.yml",
                ruler=str(lease["ruler"]),
            ),
            encoding="utf-8",
            newline="\n",
        )
        source_paths = {
            **source_paths,
            "bootstrap_project": project_source,
            "bootstrap_identities": identity_source,
        }
        target_paths = {
            **target_paths,
            "bootstrap_project": canonical_root / "config/project.yml",
            "bootstrap_identities": canonical_root
            / "config/historical-entity-identities.yml",
        }
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
            if not key.startswith("bootstrap_")
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
    if lease.get("stage_cache_root"):
        stage_cache_root = Path(str(lease["stage_cache_root"])).resolve()
        expected_stage_cache_parent = state_root.resolve() / "stage-cache"
        if (
            expected_stage_cache_parent in stage_cache_root.parents
            and stage_cache_root.exists()
        ):
            shutil.rmtree(stage_cache_root)
    _make_workspace_owner_writable(path.parent)
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
    _make_workspace_owner_writable(path.parent)
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
