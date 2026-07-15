from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from threading import RLock
from typing import Any, Callable, Mapping, Sequence


CAMPAIGN_SCHEMA_VERSION = "i5b-historical-coverage-campaign-v1"
CHECKPOINT_SCHEMA_VERSION = "i5b-historical-coverage-checkpoint-v1"
SUMMARY_SCHEMA_VERSION = "i5b-historical-coverage-summary-v1"
PHASE_CODES = (
    "candidate_freeze",
    "source_recovery",
    "acceptance",
    "persistence",
    "shadow_projection",
)
ARTIFACT_ENVELOPE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "task_code",
        "ruler_code",
        "rule_code",
        "phase_code",
        "input_version",
        "input_fingerprint",
        "status",
        "payload",
    ],
    "properties": {
        "schema_version": {"type": "string", "minLength": 1},
        "task_code": {"type": "string", "minLength": 1},
        "ruler_code": {"type": "string", "minLength": 1},
        "rule_code": {"type": "string", "minLength": 1},
        "phase_code": {"enum": list(PHASE_CODES)},
        "input_version": {"type": "string", "minLength": 1},
        "input_fingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "status": {"const": "succeeded"},
        "payload": {"type": "object"},
    },
}
_CODE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,63}$")
_TERMINAL = frozenset({"succeeded", "failed", "blocked_upstream_failed"})
_RUNNABLE = frozenset({"ready", "retry_wait"})


class CampaignContractError(ValueError):
    """A deterministic manifest or artifact contract failure."""


def _canonical(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _json_copy(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _required_text(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise CampaignContractError(f"{label} 不能为空")
    return text


def _required_code(value: Any, label: str) -> str:
    code = _required_text(value, label)
    if not _CODE.fullmatch(code):
        raise CampaignContractError(f"{label} 必须是稳定的大写机器标识")
    return code


def _relative_prefix(value: Any) -> str:
    text = _required_text(value, "artifact_root").replace("\\", "/").rstrip("/")
    path = PurePosixPath(text)
    if path.is_absolute() or ".." in path.parts:
        raise CampaignContractError("artifact_root 必须是仓库内相对路径")
    return f"{path.as_posix()}/"


@dataclass(frozen=True, slots=True)
class PhaseSpec:
    code: str
    output_schema_version: str
    max_concurrency: int


@dataclass(frozen=True, slots=True)
class CampaignTaskSpec:
    task_code: str
    ruler_code: str
    rule_code: str
    input_version: str
    input_fingerprint: str
    allowed_write_prefix: str
    output_schemas: Mapping[str, str]
    max_attempts: int
    lease_seconds: int
    retry_delay_seconds: int


@dataclass(slots=True)
class PhaseState:
    status: str = "blocked"
    attempt_count: int = 0
    next_attempt_at: datetime | None = None
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    active_run_id: str | None = None
    input_fingerprint: str | None = None
    artifact_path: str | None = None
    artifact_fingerprint: str | None = None
    last_error: str | None = None


@dataclass(slots=True)
class CampaignTaskState:
    spec: CampaignTaskSpec
    phases: dict[str, PhaseState]

    @property
    def status(self) -> str:
        statuses = {state.status for state in self.phases.values()}
        if statuses == {"succeeded"}:
            return "succeeded"
        if "failed" in statuses:
            return "failed_closed"
        if statuses <= _TERMINAL:
            return "blocked"
        if "running" in statuses:
            return "running"
        return "pending"


@dataclass(frozen=True, slots=True)
class PhaseExecutionResult:
    payload: Mapping[str, Any]
    model_calls: int = 0
    business_writes: int = 0


@dataclass(frozen=True, slots=True)
class ClaimedPhase:
    task_code: str
    ruler_code: str
    rule_code: str
    phase_code: str
    run_id: str
    attempt_number: int
    input_version: str
    input_fingerprint: str
    allowed_write_prefix: str
    output_schema_version: str


@dataclass(slots=True)
class CampaignState:
    campaign_code: str
    manifest_fingerprint: str
    phases: tuple[PhaseSpec, ...]
    tasks: dict[str, CampaignTaskState]
    max_concurrency: int
    safety: Mapping[str, bool]
    artifacts: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    model_call_count: int = 0
    business_write_count: int = 0
    _lock: RLock = field(default_factory=RLock, repr=False)

    def checkpoint(self) -> Mapping[str, Any]:
        def timestamp(value: datetime | None) -> str | None:
            return value.isoformat() if value else None

        with self._lock:
            return {
                "schema_version": CHECKPOINT_SCHEMA_VERSION,
                "campaign_code": self.campaign_code,
                "manifest_fingerprint": self.manifest_fingerprint,
                "max_concurrency": self.max_concurrency,
                "safety": dict(self.safety),
                "phases": [
                    {
                        "code": phase.code,
                        "output_schema_version": phase.output_schema_version,
                        "max_concurrency": phase.max_concurrency,
                    }
                    for phase in self.phases
                ],
                "tasks": [
                    {
                        "spec": {
                            "task_code": task.spec.task_code,
                            "ruler_code": task.spec.ruler_code,
                            "rule_code": task.spec.rule_code,
                            "input_version": task.spec.input_version,
                            "input_fingerprint": task.spec.input_fingerprint,
                            "allowed_write_prefix": task.spec.allowed_write_prefix,
                            "output_schemas": dict(task.spec.output_schemas),
                            "max_attempts": task.spec.max_attempts,
                            "lease_seconds": task.spec.lease_seconds,
                            "retry_delay_seconds": task.spec.retry_delay_seconds,
                        },
                        "phases": {
                            code: {
                                "status": phase.status,
                                "attempt_count": phase.attempt_count,
                                "next_attempt_at": timestamp(phase.next_attempt_at),
                                "lease_owner": phase.lease_owner,
                                "lease_expires_at": timestamp(phase.lease_expires_at),
                                "active_run_id": phase.active_run_id,
                                "input_fingerprint": phase.input_fingerprint,
                                "artifact_path": phase.artifact_path,
                                "artifact_fingerprint": phase.artifact_fingerprint,
                                "last_error": phase.last_error,
                            }
                            for code, phase in task.phases.items()
                        },
                    }
                    for task in sorted(self.tasks.values(), key=lambda row: row.spec.task_code)
                ],
                "artifacts": _json_copy(self.artifacts),
                "metrics": {
                    "model_call_count": self.model_call_count,
                    "business_write_count": self.business_write_count,
                },
            }

    @classmethod
    def from_checkpoint(cls, payload: Mapping[str, Any]) -> CampaignState:
        if payload.get("schema_version") != CHECKPOINT_SCHEMA_VERSION:
            raise CampaignContractError("checkpoint schema_version 不受支持")

        def timestamp(value: Any) -> datetime | None:
            return datetime.fromisoformat(str(value)) if value else None

        phases = tuple(PhaseSpec(**row) for row in payload.get("phases") or ())
        tasks: dict[str, CampaignTaskState] = {}
        for row in payload.get("tasks") or ():
            spec = CampaignTaskSpec(**row["spec"])
            states = {
                code: PhaseState(
                    status=value["status"],
                    attempt_count=int(value["attempt_count"]),
                    next_attempt_at=timestamp(value.get("next_attempt_at")),
                    lease_owner=value.get("lease_owner"),
                    lease_expires_at=timestamp(value.get("lease_expires_at")),
                    active_run_id=value.get("active_run_id"),
                    input_fingerprint=value.get("input_fingerprint"),
                    artifact_path=value.get("artifact_path"),
                    artifact_fingerprint=value.get("artifact_fingerprint"),
                    last_error=value.get("last_error"),
                )
                for code, value in row["phases"].items()
            }
            tasks[spec.task_code] = CampaignTaskState(spec=spec, phases=states)
        metrics = payload.get("metrics") or {}
        return cls(
            campaign_code=_required_code(payload.get("campaign_code"), "campaign_code"),
            manifest_fingerprint=_required_text(
                payload.get("manifest_fingerprint"), "manifest_fingerprint"
            ),
            phases=phases,
            tasks=tasks,
            max_concurrency=int(payload.get("max_concurrency") or 0),
            safety=dict(payload.get("safety") or {}),
            artifacts=_json_copy(payload.get("artifacts") or {}),
            model_call_count=int(metrics.get("model_call_count") or 0),
            business_write_count=int(metrics.get("business_write_count") or 0),
        )


def build_campaign_state(manifest: Mapping[str, Any]) -> CampaignState:
    if manifest.get("schema_version") != CAMPAIGN_SCHEMA_VERSION:
        raise CampaignContractError("campaign schema_version 不受支持")
    campaign_code = _required_code(manifest.get("campaign_code"), "campaign_code")
    campaign_input_version = _required_text(
        manifest.get("input_version"), "input_version"
    )
    safety = dict(manifest.get("safety") or {})
    required_safety = {
        "offline": True,
        "report_only": True,
        "shadow_first": True,
        "formal_scoring": False,
        "ranking": False,
        "production_deployment": False,
    }
    if safety != required_safety:
        raise CampaignContractError("campaign safety 必须保持 offline/report-only/shadow-first")

    runtime = dict(manifest.get("runtime") or {})
    max_concurrency = int(runtime.get("max_concurrency") or 0)
    max_attempts = int(runtime.get("max_attempts") or 0)
    lease_seconds = int(runtime.get("lease_seconds") or 0)
    retry_delay_seconds = int(runtime.get("retry_delay_seconds") or 0)
    if max_concurrency <= 0 or max_attempts <= 0 or lease_seconds <= 0:
        raise CampaignContractError("runtime 并发、重试和 lease 参数必须为正数")
    if retry_delay_seconds < 0 or runtime.get("failure_policy") != "fail_closed":
        raise CampaignContractError("runtime 必须使用非负重试间隔和 fail_closed")

    raw_phases = tuple(manifest.get("phases") or ())
    if tuple(row.get("code") for row in raw_phases) != PHASE_CODES:
        raise CampaignContractError("campaign 必须按固定五阶段合同声明 phases")
    phases = tuple(
        PhaseSpec(
            code=str(row["code"]),
            output_schema_version=_required_text(
                row.get("output_schema_version"),
                f"{row.get('code')} output_schema_version",
            ),
            max_concurrency=int(row.get("max_concurrency") or max_concurrency),
        )
        for row in raw_phases
    )
    if any(phase.max_concurrency <= 0 for phase in phases):
        raise CampaignContractError("phase max_concurrency 必须为正数")

    rulers = tuple(manifest.get("rulers") or ())
    rules = tuple(manifest.get("rules") or ())
    expected = int(manifest.get("expected_ruler_count") or 0)
    if expected <= 0 or len(rulers) != expected:
        raise CampaignContractError("rulers 数量必须等于 expected_ruler_count")
    ruler_codes = [_required_code(row.get("ruler_code"), "ruler_code") for row in rulers]
    rule_codes = [_required_code(row.get("rule_code"), "rule_code") for row in rules]
    if len(set(ruler_codes)) != len(ruler_codes) or len(set(rule_codes)) != len(rule_codes):
        raise CampaignContractError("ruler_code 和 rule_code 不得重复")
    if not rules:
        raise CampaignContractError("rules 不能为空")

    artifact_root = _relative_prefix(manifest.get("artifact_root"))
    manifest_fingerprint = _fingerprint(manifest)
    tasks: dict[str, CampaignTaskState] = {}
    for ruler, ruler_code in zip(rulers, ruler_codes, strict=True):
        ruler_input_version = _required_text(
            ruler.get("input_version"), f"{ruler_code} input_version"
        )
        for rule, rule_code in zip(rules, rule_codes, strict=True):
            rule_version = _required_text(rule.get("rule_version"), f"{rule_code} rule_version")
            identity = {
                "campaign_code": campaign_code,
                "ruler_code": ruler_code,
                "rule_code": rule_code,
            }
            task_code = f"HC-{campaign_code}-{ruler_code}-{rule_code}-{_fingerprint(identity)[:12].upper()}"
            input_version = ":".join(
                (campaign_input_version, ruler_input_version, rule_version)
            )
            input_fingerprint = _fingerprint(
                {**identity, "input_version": input_version}
            )
            allowed_prefix = f"{artifact_root}{task_code}/"
            output_schemas = {
                phase.code: phase.output_schema_version for phase in phases
            }
            spec = CampaignTaskSpec(
                task_code=task_code,
                ruler_code=ruler_code,
                rule_code=rule_code,
                input_version=input_version,
                input_fingerprint=input_fingerprint,
                allowed_write_prefix=allowed_prefix,
                output_schemas=output_schemas,
                max_attempts=max_attempts,
                lease_seconds=lease_seconds,
                retry_delay_seconds=retry_delay_seconds,
            )
            states = {phase.code: PhaseState() for phase in phases}
            states[PHASE_CODES[0]].status = "ready"
            tasks[task_code] = CampaignTaskState(spec=spec, phases=states)
    return CampaignState(
        campaign_code=campaign_code,
        manifest_fingerprint=manifest_fingerprint,
        phases=phases,
        tasks=tasks,
        max_concurrency=max_concurrency,
        safety=safety,
    )


class CampaignRunner:
    def __init__(
        self,
        state: CampaignState,
        *,
        handlers: Mapping[str, Callable[[ClaimedPhase], PhaseExecutionResult]],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        missing = set(PHASE_CODES) - set(handlers)
        if missing:
            raise CampaignContractError(f"缺少 phase handler: {sorted(missing)}")
        self.state = state
        self.handlers = dict(handlers)
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def recover_expired_leases(self) -> int:
        now = self.clock()
        recovered = 0
        with self.state._lock:
            for task in self.state.tasks.values():
                for phase_code, phase in task.phases.items():
                    if (
                        phase.status != "running"
                        or phase.lease_expires_at is None
                        or phase.lease_expires_at > now
                    ):
                        continue
                    phase.lease_owner = None
                    phase.lease_expires_at = None
                    phase.active_run_id = None
                    if phase.attempt_count >= task.spec.max_attempts:
                        phase.status = "failed"
                        phase.last_error = "lease_expired_at_max_attempts"
                        self._block_downstream(task, phase_code)
                    else:
                        phase.status = "retry_wait"
                        phase.next_attempt_at = now
                        phase.last_error = "lease_expired_recovered"
                    recovered += 1
        return recovered

    def run_phase(self, phase_code: str, *, worker_id: str) -> int:
        if phase_code not in PHASE_CODES or not worker_id.strip():
            raise CampaignContractError("phase_code 或 worker_id 非法")
        self.recover_expired_leases()
        phase_spec = next(row for row in self.state.phases if row.code == phase_code)
        limit = min(self.state.max_concurrency, phase_spec.max_concurrency)
        completed = 0
        while True:
            claims = self._claim_batch(phase_code, worker_id, limit)
            if not claims:
                return completed
            with ThreadPoolExecutor(max_workers=limit) as pool:
                list(pool.map(self._execute, claims))
            completed += len(claims)

    def run_to_quiescence(self, *, worker_id: str) -> int:
        completed = 0
        for phase_code in PHASE_CODES:
            completed += self.run_phase(phase_code, worker_id=worker_id)
        return completed

    def _claim_batch(
        self, phase_code: str, worker_id: str, limit: int
    ) -> list[ClaimedPhase]:
        now = self.clock()
        claimed: list[ClaimedPhase] = []
        with self.state._lock:
            for task in sorted(self.state.tasks.values(), key=lambda row: row.spec.task_code):
                phase = task.phases[phase_code]
                if phase.status not in _RUNNABLE:
                    continue
                if phase.next_attempt_at and phase.next_attempt_at > now:
                    continue
                input_fingerprint = self._phase_input_fingerprint(task, phase_code)
                phase.status = "running"
                phase.attempt_count += 1
                phase.lease_owner = worker_id
                phase.lease_expires_at = now + timedelta(seconds=task.spec.lease_seconds)
                phase.active_run_id = (
                    f"{task.spec.task_code}:{phase_code}:{phase.attempt_count}"
                )
                phase.input_fingerprint = input_fingerprint
                claimed.append(
                    ClaimedPhase(
                        task_code=task.spec.task_code,
                        ruler_code=task.spec.ruler_code,
                        rule_code=task.spec.rule_code,
                        phase_code=phase_code,
                        run_id=phase.active_run_id,
                        attempt_number=phase.attempt_count,
                        input_version=task.spec.input_version,
                        input_fingerprint=input_fingerprint,
                        allowed_write_prefix=task.spec.allowed_write_prefix,
                        output_schema_version=task.spec.output_schemas[phase_code],
                    )
                )
                if len(claimed) >= limit:
                    break
        return claimed

    def _execute(self, claim: ClaimedPhase) -> None:
        try:
            result = self.handlers[claim.phase_code](claim)
            self._succeed(claim, result)
        except Exception as error:
            self._fail(claim, error)

    def _owned(self, claim: ClaimedPhase) -> tuple[CampaignTaskState, PhaseState]:
        task = self.state.tasks[claim.task_code]
        phase = task.phases[claim.phase_code]
        if (
            phase.status != "running"
            or phase.active_run_id != claim.run_id
            or phase.lease_owner is None
        ):
            raise RuntimeError("campaign phase lease 已失效")
        if phase.lease_expires_at is None or phase.lease_expires_at <= self.clock():
            raise RuntimeError("campaign phase lease 已过期")
        return task, phase

    def _succeed(self, claim: ClaimedPhase, result: PhaseExecutionResult) -> None:
        if not isinstance(result, PhaseExecutionResult):
            raise CampaignContractError("phase handler 必须返回 PhaseExecutionResult")
        if result.model_calls < 0 or result.business_writes < 0:
            raise CampaignContractError("handler 计数不得为负数")
        if result.business_writes != 0:
            raise CampaignContractError("report-only campaign 禁止业务写入")
        payload = dict(result.payload)
        if payload.get("artifact_type") != claim.phase_code:
            raise CampaignContractError("artifact payload 类型与 phase 不一致")
        artifact_path = f"{claim.allowed_write_prefix}{claim.phase_code}.json"
        if not artifact_path.startswith(claim.allowed_write_prefix):
            raise CampaignContractError("artifact 写入超出 task 允许范围")
        artifact = {
            "schema_version": claim.output_schema_version,
            "task_code": claim.task_code,
            "ruler_code": claim.ruler_code,
            "rule_code": claim.rule_code,
            "phase_code": claim.phase_code,
            "input_version": claim.input_version,
            "input_fingerprint": claim.input_fingerprint,
            "status": "succeeded",
            "payload": _json_copy(payload),
        }
        self._validate_artifact(artifact, claim)
        artifact_fingerprint = _fingerprint(artifact)
        with self.state._lock:
            task, phase = self._owned(claim)
            existing = self.state.artifacts.get(artifact_path)
            if existing is not None and _fingerprint(existing) != artifact_fingerprint:
                raise CampaignContractError("同一 artifact 路径已绑定不同结果")
            self.state.artifacts.setdefault(artifact_path, artifact)
            phase.status = "succeeded"
            phase.artifact_path = artifact_path
            phase.artifact_fingerprint = artifact_fingerprint
            phase.lease_owner = None
            phase.lease_expires_at = None
            phase.active_run_id = None
            phase.next_attempt_at = None
            phase.last_error = None
            self.state.model_call_count += result.model_calls
            self.state.business_write_count += result.business_writes
            phase_index = PHASE_CODES.index(claim.phase_code)
            if phase_index + 1 < len(PHASE_CODES):
                next_phase = task.phases[PHASE_CODES[phase_index + 1]]
                if next_phase.status == "blocked":
                    next_phase.status = "ready"

    def _fail(self, claim: ClaimedPhase, error: Exception) -> None:
        with self.state._lock:
            task, phase = self._owned(claim)
            deterministic = isinstance(
                error, (CampaignContractError, ValueError, TypeError, KeyError, AssertionError)
            )
            terminal = deterministic or phase.attempt_count >= task.spec.max_attempts
            phase.status = "failed" if terminal else "retry_wait"
            phase.next_attempt_at = (
                None
                if terminal
                else self.clock() + timedelta(seconds=task.spec.retry_delay_seconds)
            )
            phase.lease_owner = None
            phase.lease_expires_at = None
            phase.active_run_id = None
            phase.last_error = f"{type(error).__name__}: {error}"
            if terminal:
                self._block_downstream(task, claim.phase_code)

    @staticmethod
    def _block_downstream(task: CampaignTaskState, phase_code: str) -> None:
        start = PHASE_CODES.index(phase_code) + 1
        for downstream in PHASE_CODES[start:]:
            state = task.phases[downstream]
            if state.status not in _TERMINAL:
                state.status = "blocked_upstream_failed"
                state.last_error = f"upstream_failed:{phase_code}"

    @staticmethod
    def _validate_artifact(
        artifact: Mapping[str, Any], claim: ClaimedPhase | None = None
    ) -> None:
        required = {
            "schema_version",
            "task_code",
            "ruler_code",
            "rule_code",
            "phase_code",
            "input_version",
            "input_fingerprint",
            "status",
            "payload",
        }
        if set(artifact) != required or artifact.get("status") != "succeeded":
            raise CampaignContractError("artifact envelope 合同非法")
        text_fields = (
            "schema_version",
            "task_code",
            "ruler_code",
            "rule_code",
            "input_version",
        )
        if any(
            not isinstance(artifact.get(field), str) or not artifact[field]
            for field in text_fields
        ):
            raise CampaignContractError("artifact identity 字段非法")
        if (
            artifact.get("phase_code") not in PHASE_CODES
            or not isinstance(artifact.get("payload"), dict)
            or not re.fullmatch(
                r"[0-9a-f]{64}",
                str(artifact.get("input_fingerprint") or ""),
            )
        ):
            raise CampaignContractError("artifact phase 或 payload 非法")
        if artifact["payload"].get("artifact_type") != artifact["phase_code"]:
            raise CampaignContractError("artifact payload 类型非法")
        if claim and any(
            (
                artifact["schema_version"] != claim.output_schema_version,
                artifact["task_code"] != claim.task_code,
                artifact["phase_code"] != claim.phase_code,
                artifact["input_fingerprint"] != claim.input_fingerprint,
            )
        ):
            raise CampaignContractError("artifact 与 lease 输入不一致")

    @staticmethod
    def _phase_input_fingerprint(task: CampaignTaskState, phase_code: str) -> str:
        index = PHASE_CODES.index(phase_code)
        upstream = [
            task.phases[code].artifact_fingerprint for code in PHASE_CODES[:index]
        ]
        if any(not value for value in upstream):
            raise CampaignContractError("phase 缺少成功的上游 artifact")
        return _fingerprint(
            {
                "task_input_fingerprint": task.spec.input_fingerprint,
                "phase_code": phase_code,
                "output_schema_version": task.spec.output_schemas[phase_code],
                "upstream_artifact_fingerprints": upstream,
            }
        )


def build_campaign_summary(state: CampaignState) -> Mapping[str, Any]:
    consumed: list[Mapping[str, Any]] = []
    rejected: list[Mapping[str, str]] = []
    counts = {status: 0 for status in ("succeeded", "failed_closed", "blocked", "running", "pending")}
    for task in sorted(state.tasks.values(), key=lambda row: row.spec.task_code):
        counts[task.status] += 1
        phase = task.phases["shadow_projection"]
        if phase.status != "succeeded" or not phase.artifact_path:
            rejected.append(
                {"task_code": task.spec.task_code, "reason": "task_not_successful"}
            )
            continue
        artifact = state.artifacts.get(phase.artifact_path)
        try:
            if artifact is None:
                raise CampaignContractError("artifact_missing")
            CampaignRunner._validate_artifact(artifact)
            if (
                artifact.get("task_code") != task.spec.task_code
                or artifact.get("ruler_code") != task.spec.ruler_code
                or artifact.get("rule_code") != task.spec.rule_code
                or artifact.get("input_version") != task.spec.input_version
                or artifact.get("input_fingerprint") != phase.input_fingerprint
                or artifact.get("schema_version")
                != task.spec.output_schemas["shadow_projection"]
                or not phase.artifact_path.startswith(task.spec.allowed_write_prefix)
                or _fingerprint(artifact) != phase.artifact_fingerprint
            ):
                raise CampaignContractError("artifact_state_mismatch")
        except CampaignContractError as error:
            rejected.append(
                {"task_code": task.spec.task_code, "reason": str(error)}
            )
            continue
        consumed.append(
            {
                "task_code": task.spec.task_code,
                "ruler_code": task.spec.ruler_code,
                "rule_code": task.spec.rule_code,
                "artifact_path": phase.artifact_path,
                "artifact_fingerprint": phase.artifact_fingerprint,
            }
        )
    gate_passed = len(consumed) == len(state.tasks) and not rejected
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "campaign_code": state.campaign_code,
        "manifest_fingerprint": state.manifest_fingerprint,
        "safety": dict(state.safety),
        "task_count": len(state.tasks),
        "task_status_counts": counts,
        "consumed_successful_results": consumed,
        "rejected_results": rejected,
        "gate": {
            "status": "passed" if gate_passed else "failed_closed",
            "formal_scoring_open": False,
            "ranking_open": False,
            "production_deployment_open": False,
        },
    }


def write_json_artifact(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def load_manifest(path: Path) -> Mapping[str, Any]:
    import yaml

    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CampaignContractError("campaign manifest 顶层必须是对象")
    return payload


def plan_report(state: CampaignState) -> Mapping[str, Any]:
    return {
        "schema_version": "i5b-historical-coverage-plan-report-v1",
        "campaign_code": state.campaign_code,
        "manifest_fingerprint": state.manifest_fingerprint,
        "task_count": len(state.tasks),
        "phase_work_item_count": len(state.tasks) * len(state.phases),
        "max_concurrency": state.max_concurrency,
        "safety": dict(state.safety),
        "artifact_envelope_schema": _json_copy(ARTIFACT_ENVELOPE_SCHEMA),
        "tasks": [
            {
                "task_code": task.spec.task_code,
                "ruler_code": task.spec.ruler_code,
                "rule_code": task.spec.rule_code,
                "input_version": task.spec.input_version,
                "input_fingerprint": task.spec.input_fingerprint,
                "allowed_write_prefix": task.spec.allowed_write_prefix,
                "output_schemas": dict(task.spec.output_schemas),
                "status": task.status,
                "failure_recovery": {
                    "max_attempts": task.spec.max_attempts,
                    "lease_seconds": task.spec.lease_seconds,
                    "retry_delay_seconds": task.spec.retry_delay_seconds,
                    "failure_policy": "fail_closed",
                    "checkpoint_resume": True,
                },
            }
            for task in sorted(state.tasks.values(), key=lambda row: row.spec.task_code)
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="I5B historical coverage campaign planner")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    state = build_campaign_state(load_manifest(args.manifest))
    write_json_artifact(args.output, plan_report(state))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
