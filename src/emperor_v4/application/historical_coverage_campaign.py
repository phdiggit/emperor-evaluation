from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from threading import RLock
from typing import Any, Callable, Mapping, Sequence


CAMPAIGN_SCHEMA_VERSION = "i5b-historical-coverage-campaign-v1"
CHECKPOINT_SCHEMA_VERSION = "i5b-historical-coverage-checkpoint-v2"
SUMMARY_SCHEMA_VERSION = "i5b-historical-coverage-summary-v1"
WORK_PACKAGE_SCHEMA_VERSION = "i5b-historical-coverage-work-package-v2"
EXECUTION_REPORT_SCHEMA_VERSION = "i5b-historical-coverage-execution-report-v1"
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


class CampaignBudgetExhausted(RuntimeError):
    """The ruler-level hard deadline was reached during cooperative work."""


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
    deadline_at: datetime | None = None


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
    ruler_started_at: dict[str, datetime] = field(default_factory=dict)
    ruler_deadlines: dict[str, datetime] = field(default_factory=dict)
    exhausted_ruler_codes: set[str] = field(default_factory=set)
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
                "wall_clock_budget": {
                    "ruler_started_at": {
                        code: timestamp(value)
                        for code, value in sorted(self.ruler_started_at.items())
                    },
                    "ruler_deadlines": {
                        code: timestamp(value)
                        for code, value in sorted(self.ruler_deadlines.items())
                    },
                    "exhausted_ruler_codes": sorted(self.exhausted_ruler_codes),
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
        wall_clock_budget = payload.get("wall_clock_budget") or {}
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
            ruler_started_at={
                str(code): timestamp(value)
                for code, value in (wall_clock_budget.get("ruler_started_at") or {}).items()
            },
            ruler_deadlines={
                str(code): timestamp(value)
                for code, value in (wall_clock_budget.get("ruler_deadlines") or {}).items()
            },
            exhausted_ruler_codes={
                str(code)
                for code in wall_clock_budget.get("exhausted_ruler_codes") or ()
            },
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
    max_wall_clock_minutes = int(runtime.get("max_wall_clock_minutes") or 0)
    completion_reserve_seconds = int(
        runtime.get("completion_reserve_seconds", 90)
    )
    if max_concurrency <= 0 or max_attempts <= 0 or lease_seconds <= 0:
        raise CampaignContractError("runtime 并发、重试和 lease 参数必须为正数")
    if max_wall_clock_minutes <= 0:
        raise CampaignContractError("runtime.max_wall_clock_minutes 必须为正数")
    if not 0 <= completion_reserve_seconds < max_wall_clock_minutes * 60:
        raise CampaignContractError(
            "runtime.completion_reserve_seconds 必须非负且小于 wall-clock 预算"
        )
    if lease_seconds <= max_wall_clock_minutes * 60:
        raise CampaignContractError("runtime.lease_seconds 必须长于皇帝级 wall-clock 预算")
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
    if not artifact_root.startswith("tmp/"):
        raise CampaignContractError("campaign phase artifact 必须写入 Git 忽略的 tmp/**")
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
        ruler_wall_clock_minutes: float | None = None,
        ruler_wall_clock_seconds: float | None = None,
        completion_reserve_seconds: float = 0,
    ) -> None:
        missing = set(PHASE_CODES) - set(handlers)
        if missing:
            raise CampaignContractError(f"缺少 phase handler: {sorted(missing)}")
        self.state = state
        self.handlers = dict(handlers)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        if (
            ruler_wall_clock_minutes is not None
            and ruler_wall_clock_seconds is not None
        ):
            raise CampaignContractError("皇帝级 wall-clock 预算只能使用一种单位")
        if ruler_wall_clock_minutes is not None and ruler_wall_clock_minutes <= 0:
            raise CampaignContractError("皇帝级 wall-clock 预算必须为正数")
        if ruler_wall_clock_seconds is not None and ruler_wall_clock_seconds <= 0:
            raise CampaignContractError("皇帝级 wall-clock 预算必须为正数")
        if completion_reserve_seconds < 0:
            raise CampaignContractError("完成收尾预留时间不得为负数")
        budget_seconds = ruler_wall_clock_seconds
        if budget_seconds is None and ruler_wall_clock_minutes is not None:
            budget_seconds = ruler_wall_clock_minutes * 60
        if (
            budget_seconds is not None
            and completion_reserve_seconds >= budget_seconds
        ):
            raise CampaignContractError("完成收尾预留时间必须小于 wall-clock 预算")
        self.ruler_wall_clock_seconds = budget_seconds
        self.completion_reserve_seconds = completion_reserve_seconds
        self.ruler_deadlines = self.state.ruler_deadlines
        self.exhausted_ruler_codes = self.state.exhausted_ruler_codes
        self.budget_exhausted = bool(self.exhausted_ruler_codes)

    def _ruler_budget_exhausted(self, ruler_code: str, now: datetime) -> bool:
        if self.ruler_wall_clock_seconds is None:
            return False
        self.state.ruler_started_at.setdefault(ruler_code, now)
        deadline = self.ruler_deadlines.setdefault(
            ruler_code, now + timedelta(seconds=self.ruler_wall_clock_seconds)
        )
        exhausted = now >= deadline - timedelta(seconds=self.completion_reserve_seconds)
        if exhausted:
            self.budget_exhausted = True
            self.exhausted_ruler_codes.add(ruler_code)
        return exhausted

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
            pool = ThreadPoolExecutor(max_workers=limit)
            pending: dict[Future[None], ClaimedPhase] = {
                pool.submit(self._execute, claim): claim for claim in claims
            }
            try:
                while pending:
                    now = self.clock()
                    expired = [
                        future
                        for future, claim in pending.items()
                        if claim.deadline_at is not None and now >= claim.deadline_at
                    ]
                    for future in expired:
                        claim = pending.pop(future)
                        future.cancel()
                        self._defer_at_budget_boundary(
                            claim, "hard_deadline_reached_while_handler_running"
                        )
                    if not pending:
                        break
                    deadlines = [
                        claim.deadline_at
                        for claim in pending.values()
                        if claim.deadline_at is not None
                    ]
                    timeout = (
                        None
                        if not deadlines
                        else max(
                            0.0,
                            (min(deadlines) - self.clock()).total_seconds(),
                        )
                    )
                    done, _ = wait(
                        pending,
                        timeout=timeout,
                        return_when=FIRST_COMPLETED,
                    )
                    for future in done:
                        pending.pop(future, None)
                        future.result()
            finally:
                pool.shutdown(wait=False, cancel_futures=True)
            completed += sum(
                self.state.tasks[claim.task_code].phases[claim.phase_code].status
                == "succeeded"
                for claim in claims
            )

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
                now = self.clock()
                if self._ruler_budget_exhausted(task.spec.ruler_code, now):
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
                        deadline_at=self.ruler_deadlines.get(task.spec.ruler_code),
                    )
                )
                if len(claimed) >= limit:
                    break
        return claimed

    def _execute(self, claim: ClaimedPhase) -> None:
        if claim.deadline_at is not None and self.clock() >= claim.deadline_at:
            self._defer_at_budget_boundary(claim, "deadline_reached_before_handler")
            return
        try:
            result = self.handlers[claim.phase_code](claim)
            if claim.deadline_at is not None and self.clock() >= claim.deadline_at:
                self._defer_at_budget_boundary(claim, "late_handler_result_discarded")
                return
            self._succeed(claim, result)
        except CampaignBudgetExhausted:
            self._defer_at_budget_boundary(claim, "deadline_reached_inside_handler")
        except Exception as error:
            self._fail(claim, error)

    def _defer_at_budget_boundary(self, claim: ClaimedPhase, reason: str) -> None:
        with self.state._lock:
            task = self.state.tasks[claim.task_code]
            phase = task.phases[claim.phase_code]
            if (
                phase.status != "running"
                or phase.active_run_id != claim.run_id
                or phase.lease_owner is None
            ):
                return
            phase.status = "ready"
            phase.next_attempt_at = None
            phase.lease_owner = None
            phase.lease_expires_at = None
            phase.active_run_id = None
            phase.last_error = f"wall_clock_budget_exhausted:{reason}"
            self.budget_exhausted = True
            self.exhausted_ruler_codes.add(claim.ruler_code)

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
            task = self.state.tasks[claim.task_code]
            phase = task.phases[claim.phase_code]
            if (
                phase.status != "running"
                or phase.active_run_id != claim.run_id
                or phase.lease_owner is None
            ):
                return
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


class WorkspaceCampaignHandlers:
    """Read versioned, report-only work packages through the common five-phase contract."""

    def __init__(
        self,
        state: CampaignState,
        *,
        workspace_root: Path,
        input_root: Path,
    ) -> None:
        self.state = state
        self.workspace_root = workspace_root.resolve()
        self.input_root = input_root.resolve()
        if not self.input_root.is_relative_to(self.workspace_root):
            raise CampaignContractError("input_root 必须位于 workspace_root 内")

    def handlers(
        self,
    ) -> Mapping[str, Callable[[ClaimedPhase], PhaseExecutionResult]]:
        return {code: self._handle for code in PHASE_CODES}

    def _handle(self, claim: ClaimedPhase) -> PhaseExecutionResult:
        self._require_time_remaining(claim)
        package = self._load_package(claim)
        raw = package.get("phases", {}).get(claim.phase_code)
        if not isinstance(raw, dict):
            raise CampaignContractError(
                f"work package 缺少 phase 输入: {claim.phase_code}"
            )
        payload = _json_copy(raw)
        if claim.phase_code == "candidate_freeze":
            from emperor_v4.evaluation.i5b_candidate_retrieval_gate import (
                validate_candidate_retrieval_gate,
            )

            self._run_candidate_preprocessors(claim, payload)
            if payload.get("adapter") == "scholar_guided_retrieval_v1":
                self._run_scholar_guided_retrieval(claim, payload)
            gate = payload.get("retrieval_gate")
            if not isinstance(gate, dict):
                raise CampaignContractError("candidate_freeze 缺少 retrieval_gate")
            try:
                payload.update(
                    validate_candidate_retrieval_gate(
                        gate, rule_code=claim.rule_code
                    )
                )
            except ValueError as error:
                raise CampaignContractError(str(error)) from error
        if claim.phase_code == "source_recovery" and payload.get("adapter") == (
            "source_cache_fixture_ensure_v1"
        ):
            self._run_source_cache(claim, payload)
        if claim.phase_code == "shadow_projection" and payload.get("adapter") == (
            "deterministic_scored_shadow_v1"
        ):
            self._run_scored_shadow(claim, payload)
        self._validate_phase_payload(claim.phase_code, payload)
        referenced = payload.pop("referenced_artifacts", [])
        verified = [self._verify_reference(value) for value in referenced]
        task = self.state.tasks[claim.task_code]
        phase_index = PHASE_CODES.index(claim.phase_code)
        upstream = [
            task.phases[code].artifact_fingerprint
            for code in PHASE_CODES[:phase_index]
        ]
        payload.update(
            {
                "artifact_type": claim.phase_code,
                "handler": "workspace_common_contract_v1",
                "verified_artifacts": verified,
                "upstream_artifact_fingerprints": upstream,
                "model_call_count": 0,
                "business_write_count": 0,
            }
        )
        return PhaseExecutionResult(payload=payload)

    @staticmethod
    def _require_time_remaining(claim: ClaimedPhase) -> None:
        if (
            claim.deadline_at is not None
            and datetime.now(timezone.utc) >= claim.deadline_at
        ):
            raise CampaignBudgetExhausted

    def _run_candidate_preprocessors(
        self, claim: ClaimedPhase, payload: dict[str, Any]
    ) -> None:
        preprocessors = payload.get("candidate_preprocessors") or []
        if not isinstance(preprocessors, list):
            raise CampaignContractError("candidate_preprocessors 必须是列表")
        audits = []
        for row in preprocessors:
            self._require_time_remaining(claim)
            if not isinstance(row, dict):
                raise CampaignContractError("candidate preprocessor 必须是对象")
            adapter = str(row.get("adapter") or "")
            if adapter == "talent_discovery_scope_refreeze_v1":
                frozen_inventory_ref = row.get("frozen_inventory_ref")
                if frozen_inventory_ref:
                    report = json.loads(
                        self._reference_path(frozen_inventory_ref).read_text(
                            encoding="utf-8"
                        )
                    )
                    summary = report.get("candidate_summary") or {}
                    human_freeze = report.get("human_freeze") or {}
                    if (
                        report.get("schema_version")
                        != "i5b-talent-discovery-candidate-inventory-v7"
                        or report.get("historical_coverage_complete") is not True
                        or report.get("formal_fact_acceptance_ready") is not True
                        or summary.get("unresolved_candidate_count") != 0
                        or summary.get("within_work_budget") is not True
                        or human_freeze.get("accepted") is not True
                        or not str(human_freeze.get("decision_ref") or "")
                    ):
                        raise CampaignContractError(
                            "发现人才冻结 inventory 未通过完整性与人工接受校验"
                        )
                else:
                    from emperor_v4.evaluation.i5b_talent_discovery_scope import (
                        build_talent_discovery_scope_refreeze,
                    )

                    report = build_talent_discovery_scope_refreeze(
                        self._reference_path(row.get("contract_ref"))
                    )
                audits.append(
                    {
                        "adapter": adapter,
                        "report_sha256": report["report_sha256"],
                        "within_work_budget": report["candidate_summary"][
                            "within_work_budget"
                        ],
                        "unresolved_candidate_count": report["candidate_summary"][
                            "unresolved_candidate_count"
                        ],
                    }
                )
                if report["historical_coverage_complete"] is not True:
                    raise CampaignContractError(
                        "发现人才有界重冻批次已执行，仍有候选或deferred backlog待处理"
                    )
            elif adapter == "delegated_harm_audit_v1":
                from emperor_v4.evaluation.i5b_delegated_harm_audit import (
                    build_delegated_harm_audit,
                )

                report = build_delegated_harm_audit(
                    contract_path=self._reference_path(row.get("contract_ref")),
                    incidents_path=self._reference_path(row.get("incidents_ref")),
                )
                summary = report["summary"]
                gate = payload.get("retrieval_gate")
                if not isinstance(gate, dict):
                    raise CampaignContractError("委托损害审计缺少 retrieval_gate")
                gate["delegated_harm_audit"] = {
                    "status": report["status"],
                    "report_sha256": report["report_sha256"],
                    "reviewed_incident_count": summary["reviewed_incident_count"],
                    "unresolved_incident_count": summary["unresolved_incident_count"],
                    "cross_rule_duplicate_count": summary[
                        "cross_rule_duplicate_count"
                    ],
                }
                audits.append(
                    {
                        "adapter": adapter,
                        "report_sha256": report["report_sha256"],
                        "status": report["status"],
                    }
                )
            else:
                raise CampaignContractError(
                    f"未知 candidate preprocessor: {adapter or 'missing'}"
                )
        payload["candidate_preprocessor_audits"] = audits

    def _run_scholar_guided_retrieval(
        self, claim: ClaimedPhase, payload: dict[str, Any]
    ) -> None:
        self._require_time_remaining(claim)
        from emperor_v4.evaluation.i5b_scholar_guided_retrieval import (
            build_scholar_guided_retrieval_report,
        )

        report = build_scholar_guided_retrieval_report(
            mechanism_contract_path=self._reference_path(
                payload.get("scholar_guided_mechanism_ref")
            ),
            task_contract_path=self._reference_path(
                payload.get("scholar_guided_task_ref")
            ),
        )
        expected = json.loads(
            self._reference_path(payload.get("scholar_guided_report_ref")).read_text(
                encoding="utf-8"
            )
        )
        if report.get("report_sha256") != expected.get("report_sha256"):
            raise CampaignContractError("学术引导检索输出与冻结报告不一致")

        rule = claim.rule_code.lower()
        rule_tasks = [
            row
            for row in report.get("source_cache_tasks") or ()
            if rule in row.get("target_rules", ())
        ]
        judge_intake = json.loads(
            self._reference_path(payload.get("scholar_guided_judge_intake_ref")).read_text(
                encoding="utf-8"
            )
        )
        bound_codes = {
            str(row.get("source_cache_task_code") or "")
            for row in judge_intake.get("items") or ()
            if str(row.get("rule_code") or "").lower() == rule
            and row.get("status") in {"ready_for_candidate_judge", "judged"}
        }
        task_codes = {str(row["task_code"]) for row in rule_tasks}
        if not task_codes or not task_codes <= bound_codes:
            raise CampaignContractError("学术引导候选尚未全部绑定到 Judge intake")
        gate = payload.get("retrieval_gate")
        if not isinstance(gate, dict):
            raise CampaignContractError("candidate_freeze 缺少 retrieval_gate")
        gate["scholar_guided_retrieval"] = {
            "status": "complete",
            "report_sha256": report["report_sha256"],
            "task_count": len(rule_tasks),
            "source_cache_routed_task_count": len(rule_tasks),
            "judge_bound_task_count": len(task_codes & bound_codes),
        }

    def _run_source_cache(self, claim: ClaimedPhase, payload: dict[str, Any]) -> None:
        from emperor_v4.runtime.source_cache import run_fixture_ensure
        import yaml

        jobs = payload.get("source_cache_jobs")
        if jobs is None:
            jobs = [{
                "source_request_ref": payload.get("source_request_ref"),
                "source_plan_ref": payload.get("source_plan_ref"),
                "response_ref": next(
                    (
                        value
                        for value in payload.get("referenced_artifacts") or ()
                        if str(value).endswith("_response.json")
                    ),
                    None,
                ),
            }]
        if not isinstance(jobs, list) or not jobs:
            raise CampaignContractError("source_recovery 必须声明非空 Source Cache jobs")
        responses: list[Mapping[str, Any]] = []
        audits: list[Mapping[str, Any]] = []
        for job_index, job in enumerate(jobs):
            self._require_time_remaining(claim)
            if not isinstance(job, dict):
                raise CampaignContractError("Source Cache job 必须是对象")
            response, audit = self._run_source_cache_job(
                claim, job, job_index=job_index
            )
            responses.append(response)
            audits.append(audit)
        payload.update(
            {
                "source_cache_complete": all(
                    response.get("status") in {"complete", "succeeded"}
                    for response in responses
                ),
                "document_count": sum(len(response.get("documents") or ()) for response in responses),
                "passage_count": sum(len(response.get("passages") or ()) for response in responses),
                "source_cache_output_fingerprints": [
                    response.get("output_fingerprint") for response in responses
                ],
                "source_cache_audits": audits,
                "source_cache_audit": {
                    "job_count": len(audits),
                    "network_request_count": sum(int(row.get("network_request_count", 0)) for row in audits),
                    "model_call_count": sum(int(row.get("model_call_count", 0)) for row in audits),
                    "business_write_count": 0,
                },
            }
        )
        if payload["source_cache_audit"]["network_request_count"] != 0 or payload["source_cache_audit"]["model_call_count"] != 0:
            raise CampaignContractError("campaign Source Cache 必须保持离线零模型")

    def _run_source_cache_job(
        self,
        claim: ClaimedPhase,
        job: Mapping[str, Any],
        *,
        job_index: int,
    ) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
        from emperor_v4.runtime.source_cache import run_fixture_ensure
        import yaml

        request_path = self._reference_path(job.get("source_request_ref"))
        plan_path = self._reference_path(job.get("source_plan_ref"))
        plan = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
        sections = plan.get("sections") or () if isinstance(plan, dict) else ()
        if sections and all(section.get("snapshot") for section in sections):
            state_path = _workspace_path(
                self.workspace_root,
                f"{claim.allowed_write_prefix}source_cache_state_{job_index + 1}.json",
            )
            report = run_fixture_ensure(
                request_path=request_path,
                fixture_plan_path=plan_path,
                state_path=state_path,
                service_release_sha=claim.input_fingerprint[:40],
                repo_root=self.workspace_root,
            )
            response = report["response"]
            audit = report["runtime_audit"]
        else:
            response_ref = job.get("response_ref")
            if not response_ref:
                raise CampaignContractError(
                    "无本地 snapshot 的 Source plan 必须绑定一个冻结 response"
                )
            frozen = json.loads(
                self._reference_path(response_ref).read_text(encoding="utf-8")
            )
            response = frozen.get("response") or frozen
            provenance = response.get("provenance") or {}
            audit = {
                "cache_hit": True,
                "exact_response_reused": True,
                "provider_call_count": 0,
                "shadow_state_write_count": 0,
                "network_request_count": 0,
                "database_write_count": 0,
                "model_call_count": 0,
                "replayed_frozen_response": True,
                "source_network_request_count": provenance.get(
                    "network_request_count", 0
                ),
            }
        if audit.get("network_request_count") != 0 or audit.get("model_call_count") != 0:
            raise CampaignContractError("campaign Source Cache 必须保持离线零模型")
        return response, audit

    def _run_scored_shadow(self, claim: ClaimedPhase, payload: dict[str, Any]) -> None:
        from emperor_v4.evaluation.i5b_appointment_delegation_historical_scored_shadow import (
            build_appointment_historical_scored_shadow,
        )
        from emperor_v4.evaluation.i5b_joint_projection_scored_shadow import (
            build_i5b_joint_projection_scored_shadow,
        )
        from emperor_v4.evaluation.i5b_team_building_historical_scored_shadow import (
            build_team_building_historical_scored_shadow,
        )

        def load(reference: Any) -> Mapping[str, Any]:
            path = self._reference_path(reference)
            if path.suffix.lower() in {".yml", ".yaml"}:
                import yaml

                value = yaml.safe_load(path.read_text(encoding="utf-8"))
            else:
                value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise CampaignContractError(f"scorer 输入顶层必须是对象: {reference}")
            return value

        rule_code = claim.rule_code.lower()
        formal = load(payload.get("formal_acceptance_ref"))
        if rule_code == "appointment_delegation":
            report = build_appointment_historical_scored_shadow(
                projection_payload=load(payload.get("projection_input_ref")),
                formal_acceptance=formal,
            )
        elif rule_code == "team_building":
            report = build_team_building_historical_scored_shadow(
                roster_payload=load(payload.get("roster_ref")),
                formal_acceptance=formal,
                scoring_policy=load(payload.get("scoring_policy_ref")),
                authorized_promotion=load(payload.get("authorized_promotion_ref")),
                supplemental_promotion=load(payload.get("supplemental_promotion_ref")),
                calibrations=[
                    load(reference)
                    for reference in payload.get("calibration_refs") or ()
                ],
            )
        elif rule_code in {"talent_discovery", "tolerate_talent", "anti_nepotism"}:
            report = build_i5b_joint_projection_scored_shadow(
                rule_code=rule_code,
                projection_payload=load(payload.get("projection_input_ref")),
                scoring_policy=load(payload.get("scoring_policy_ref")),
                assertion_payload=formal,
            )
        else:  # pragma: no cover - manifest rule registry is finite in production
            raise CampaignContractError(f"没有 scored shadow adapter: {claim.rule_code}")
        expected = load(payload.get("expected_report_ref"))
        if report.get("report_sha256") != expected.get("report_sha256"):
            raise CampaignContractError("deterministic scored shadow 与冻结报告不一致")
        payload.update(
            {
                "historical_coverage_status": "coverage_complete",
                "formal_score": None,
                "tier": None,
                "ranking": None,
                "computed_report_sha256": report.get("report_sha256"),
                "result_summary": _json_copy(report.get("summary") or {}),
                "score_contributions": _json_copy(
                    report.get("score_contributions")
                    or ([report["score_contribution"]] if report.get("score_contribution") else [])
                ),
            }
        )

    def _load_package(self, claim: ClaimedPhase) -> Mapping[str, Any]:
        path = (
            self.input_root / claim.ruler_code / f"{claim.rule_code}.json"
        ).resolve()
        if not path.is_relative_to(self.input_root) or not path.is_file():
            raise CampaignContractError(f"work package 不存在: {claim.ruler_code}/{claim.rule_code}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise CampaignContractError("work package 顶层必须是对象")
        expected = {
            "schema_version": WORK_PACKAGE_SCHEMA_VERSION,
            "ruler_code": claim.ruler_code,
            "rule_code": claim.rule_code,
            "input_version": claim.input_version,
        }
        if any(payload.get(key) != value for key, value in expected.items()):
            raise CampaignContractError("work package 身份或输入版本不匹配")
        if set(payload) != {*expected, "phases"} or not isinstance(
            payload.get("phases"), dict
        ):
            raise CampaignContractError("work package envelope 合同非法")
        if set(payload["phases"]) != set(PHASE_CODES):
            raise CampaignContractError("work package 必须提供固定五阶段输入")
        return payload

    def _verify_reference(self, value: Any) -> Mapping[str, str]:
        relative = _required_text(value, "referenced_artifact").replace("\\", "/")
        path = self._reference_path(relative)
        return {
            "path": relative,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    def _reference_path(self, value: Any) -> Path:
        relative = _required_text(value, "referenced_artifact").replace("\\", "/")
        path_value = PurePosixPath(relative)
        if path_value.is_absolute() or ".." in path_value.parts:
            raise CampaignContractError("referenced_artifact 必须是仓库内相对路径")
        path = (self.workspace_root / Path(*path_value.parts)).resolve()
        if not path.is_relative_to(self.workspace_root) or not path.is_file():
            raise CampaignContractError(f"referenced_artifact 不存在: {relative}")
        return path

    @staticmethod
    def _validate_phase_payload(phase_code: str, payload: Mapping[str, Any]) -> None:
        refs = payload.get("referenced_artifacts")
        if not isinstance(refs, list) or not refs:
            raise CampaignContractError("phase 必须声明非空 referenced_artifacts")
        if payload.get("model_call_count", 0) != 0 or payload.get(
            "business_write_count", 0
        ) != 0:
            raise CampaignContractError("workspace handler 只允许零模型、零业务写入输入")

        required_by_phase = {
            "candidate_freeze": (
                "candidate_count",
                "candidate_universe_frozen",
                "retrieval_gate_complete",
                "retrieval_gate_fingerprint",
                "unresolved_cross_rule_orphan_count",
                "unresolved_candidate_count",
            ),
            "source_recovery": (
                "document_count",
                "passage_count",
                "assertion_draft_count",
                "source_cache_complete",
            ),
            "acceptance": (
                "accepted_unit_count",
                "accepted_assertion_count",
                "pending_blocking_review_unit_count",
            ),
            "persistence": (
                "persistence_status",
                "idempotent_rerun_business_write_count",
                "formal_score_write",
            ),
            "shadow_projection": (
                "historical_coverage_status",
                "formal_score",
                "tier",
                "ranking",
            ),
        }
        missing = [key for key in required_by_phase[phase_code] if key not in payload]
        if missing:
            raise CampaignContractError(f"{phase_code} 缺少字段: {missing}")
        count_fields = {
            "candidate_count",
            "document_count",
            "passage_count",
            "assertion_draft_count",
            "accepted_unit_count",
            "accepted_assertion_count",
            "pending_blocking_review_unit_count",
            "idempotent_rerun_business_write_count",
        }
        for field in count_fields & set(payload):
            if not isinstance(payload[field], int) or payload[field] < 0:
                raise CampaignContractError(f"{phase_code}.{field} 必须是非负整数")
        if phase_code == "candidate_freeze" and payload[
            "candidate_universe_frozen"
        ] is not True:
            raise CampaignContractError("candidate universe 必须冻结")
        if phase_code == "candidate_freeze" and (
            payload["retrieval_gate_complete"] is not True
            or payload["unresolved_cross_rule_orphan_count"] != 0
            or payload["unresolved_candidate_count"] != 0
        ):
            raise CampaignContractError("candidate universe 检索门禁未闭合")
        if phase_code == "source_recovery" and (
            payload["source_cache_complete"] is not True
            or payload["document_count"] <= 0
            or payload["passage_count"] <= 0
            or payload["assertion_draft_count"] <= 0
        ):
            raise CampaignContractError("source recovery 必须消费非空且完成的 Source Cache")
        if phase_code == "acceptance" and payload[
            "pending_blocking_review_unit_count"
        ] != 0:
            raise CampaignContractError("acceptance 仍有 blocking review unit")
        if phase_code == "persistence" and (
            payload["idempotent_rerun_business_write_count"] != 0
            or payload["formal_score_write"] is not False
            or payload["persistence_status"]
            not in {"verified_idempotent", "plan_only_report_only"}
        ):
            raise CampaignContractError("persistence 必须是幂等核验或 report-only 计划")
        if phase_code == "shadow_projection" and (
            payload["historical_coverage_status"] != "coverage_complete"
            or any(payload[field] is not None for field in ("formal_score", "tier", "ranking"))
        ):
            raise CampaignContractError("shadow projection 禁止正式分数、档位或排名")


def _workspace_path(workspace_root: Path, relative: str) -> Path:
    normalized = _relative_prefix(relative).rstrip("/")
    path = (workspace_root.resolve() / Path(*PurePosixPath(normalized).parts)).resolve()
    if not path.is_relative_to(workspace_root.resolve()):
        raise CampaignContractError("artifact 路径超出 workspace_root")
    return path


def _flush_campaign_artifacts(state: CampaignState, workspace_root: Path) -> None:
    for relative, payload in state.artifacts.items():
        write_json_artifact(_workspace_path(workspace_root, relative), payload)


def _verify_disk_artifacts(state: CampaignState, workspace_root: Path) -> None:
    for relative, expected in state.artifacts.items():
        path = _workspace_path(workspace_root, relative)
        if not path.is_file():
            raise CampaignContractError(f"checkpoint artifact 缺失: {relative}")
        actual = json.loads(path.read_text(encoding="utf-8"))
        if actual != expected or _fingerprint(actual) != _fingerprint(expected):
            raise CampaignContractError(f"checkpoint artifact 被篡改: {relative}")


def _cleanup_successful_campaign_runtime(
    state: CampaignState, workspace_root: Path, checkpoint_path: Path
) -> None:
    workspace = workspace_root.resolve()
    tmp_root = (workspace / "tmp").resolve()
    checkpoint = checkpoint_path.resolve()
    if not checkpoint.is_relative_to(tmp_root):
        raise CampaignContractError("成功清理要求 checkpoint 位于 Git 忽略的 tmp/**")
    for relative in sorted(state.artifacts, reverse=True):
        path = _workspace_path(workspace, relative)
        if not path.is_relative_to(tmp_root):
            raise CampaignContractError("成功清理拒绝删除 tmp/** 之外的 phase artifact")
        if path.is_file():
            path.unlink()
        parent = path.parent
        while parent != tmp_root and parent.is_relative_to(tmp_root):
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
    if checkpoint.is_file():
        checkpoint.unlink()


def run_workspace_campaign(
    *,
    manifest: Mapping[str, Any],
    workspace_root: Path,
    input_root: Path,
    checkpoint_path: Path,
    summary_path: Path,
    worker_id: str,
    resume: bool = False,
    phase_code: str | None = None,
    cleanup_on_success: bool = False,
) -> Mapping[str, Any]:
    fresh = build_campaign_state(manifest)
    if resume:
        if not checkpoint_path.is_file():
            raise CampaignContractError("resume 要求 checkpoint 已存在")
        state = CampaignState.from_checkpoint(
            json.loads(checkpoint_path.read_text(encoding="utf-8"))
        )
        if (
            state.manifest_fingerprint != fresh.manifest_fingerprint
            or state.campaign_code != fresh.campaign_code
        ):
            raise CampaignContractError("checkpoint 与 manifest 不匹配")
        _verify_disk_artifacts(state, workspace_root)
    else:
        if checkpoint_path.exists():
            raise CampaignContractError("checkpoint 已存在；请使用 resume")
        state = fresh

    handler_set = WorkspaceCampaignHandlers(
        state, workspace_root=workspace_root, input_root=input_root
    )
    runtime = dict(manifest.get("runtime") or {})
    max_wall_clock_minutes = int(runtime.get("max_wall_clock_minutes") or 0)
    completion_reserve_seconds = int(
        runtime.get("completion_reserve_seconds", 90)
    )
    if max_wall_clock_minutes <= 0:
        raise CampaignContractError("runtime.max_wall_clock_minutes 必须为正数")
    runner = CampaignRunner(
        state,
        handlers=handler_set.handlers(),
        ruler_wall_clock_minutes=max_wall_clock_minutes,
        completion_reserve_seconds=completion_reserve_seconds,
    )
    phase_codes = (phase_code,) if phase_code else PHASE_CODES
    completed = 0
    for code in phase_codes:
        if code not in PHASE_CODES:
            raise CampaignContractError("phase_code 不受支持")
        completed += runner.run_phase(code, worker_id=worker_id)
        _flush_campaign_artifacts(state, workspace_root)
        write_json_artifact(checkpoint_path, state.checkpoint())

    summary = build_campaign_summary(state)
    write_json_artifact(summary_path, summary)
    runtime_artifacts_cleaned = False
    if cleanup_on_success and not phase_code and summary["gate"]["status"] == "passed":
        _cleanup_successful_campaign_runtime(state, workspace_root, checkpoint_path)
        runtime_artifacts_cleaned = True
    now = runner.clock()
    elapsed_by_ruler = {
        code: max(0.0, (now - started_at).total_seconds())
        for code, started_at in sorted(state.ruler_started_at.items())
    }
    return {
        "schema_version": EXECUTION_REPORT_SCHEMA_VERSION,
        "campaign_code": state.campaign_code,
        "manifest_fingerprint": state.manifest_fingerprint,
        "completed_phase_count": completed,
        "task_count": len(state.tasks),
        "model_call_count": state.model_call_count,
        "business_write_count": state.business_write_count,
        "max_wall_clock_minutes": max_wall_clock_minutes,
        "completion_reserve_seconds": completion_reserve_seconds,
        "wall_clock_budget_exhausted": runner.budget_exhausted,
        "wall_clock_budget_exhausted_ruler_codes": sorted(
            runner.exhausted_ruler_codes
        ),
        "hard_deadline_enforced": True,
        "late_handler_results_accepted": False,
        "elapsed_wall_clock_seconds_by_ruler": elapsed_by_ruler,
        "runtime_artifacts_cleaned": runtime_artifacts_cleaned,
        "summary_gate_status": summary["gate"]["status"],
        "checkpoint": checkpoint_path.as_posix(),
        "summary": summary_path.as_posix(),
    }


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
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--resume", action="store_true")
    parser.add_argument("--workspace-root", type=Path, default=Path("."))
    parser.add_argument("--input-root", type=Path)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--worker-id", default="campaign-worker")
    parser.add_argument("--phase", choices=PHASE_CODES)
    parser.add_argument(
        "--keep-runtime-artifacts",
        action="store_true",
        help="成功后保留 tmp checkpoint 和逐 phase artifact；仅用于本地诊断",
    )
    args = parser.parse_args(argv)
    manifest = load_manifest(args.manifest)
    if not args.run and not args.resume:
        state = build_campaign_state(manifest)
        write_json_artifact(args.output, plan_report(state))
        return 0
    if not args.input_root or not args.checkpoint or not args.summary:
        parser.error("--run/--resume 要求 --input-root、--checkpoint 和 --summary")
    workspace_root = args.workspace_root.resolve()
    execution = run_workspace_campaign(
        manifest=manifest,
        workspace_root=workspace_root,
        input_root=(
            args.input_root.resolve()
            if args.input_root.is_absolute()
            else (workspace_root / args.input_root).resolve()
        ),
        checkpoint_path=(
            args.checkpoint.resolve()
            if args.checkpoint.is_absolute()
            else (workspace_root / args.checkpoint).resolve()
        ),
        summary_path=(
            args.summary.resolve()
            if args.summary.is_absolute()
            else (workspace_root / args.summary).resolve()
        ),
        worker_id=args.worker_id,
        resume=args.resume,
        phase_code=args.phase,
        cleanup_on_success=not args.keep_runtime_artifacts,
    )
    write_json_artifact(args.output, execution)
    if args.phase:
        return 0
    return 0 if execution["summary_gate_status"] == "passed" else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
