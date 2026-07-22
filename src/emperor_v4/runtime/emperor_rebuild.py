from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import time
from typing import Any, Callable, Mapping, Sequence
from uuid import uuid4

import yaml

from emperor_v4.adapters.historical_entity_identity import HistoricalEntityResolver
from emperor_v4.adapters.source_text_index import LocalSourceTextIndex
from emperor_v4.evaluation.model_policy import resolve_agent_route
from emperor_v4.evaluation.i5b_current_value_runner import (
    build_i5b_current_value,
    render_scoring_detail_markdown,
)
from emperor_v4.evaluation.historical_outcome_registry import (
    write_current_outcome_layers,
)
from emperor_v4.runtime.emperor_neutral_scan import (
    build_backbone_event_signatures,
    build_compact_multi_output_schema,
    build_chronicle_role_projections,
    build_deterministic_fact_resolution_plan,
    build_event_directed_neutral_plan,
    build_ruler_neutral_plan,
    extract_current_neutral_materials,
    merge_dynasty_governance_current,
    seed_deterministic_campaign_facts,
)
from emperor_v4.runtime.emperor_outcome_projection import project_current_outcomes
from emperor_v4.runtime.deterministic_campaign_extraction import (
    discover_deterministic_backbone_campaigns,
)
from emperor_v4.runtime.structured_codex_runner import (
    ModelBatchAnomalyError,
    StructuredCodexRunner,
)


SCHEMA_VERSION = "emperor-rebuild-v1"


def _digest(value: object) -> str:
    return sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


@dataclass(frozen=True, slots=True)
class RebuildLimits:
    wall_clock_seconds: int | None = None
    source_workers: int = 8
    export_workers: int = 4
    max_pages_per_subject: int = 32
    model_workers: int = 4
    model_timeout_seconds: int = 120

    def __post_init__(self) -> None:
        if self.wall_clock_seconds is not None and self.wall_clock_seconds <= 0:
            raise ValueError("墙钟预算启用时必须为正数")
        if not 1 <= self.source_workers <= 16:
            raise ValueError("史料召回并发必须在 1..16")
        if not 1 <= self.export_workers <= 8:
            raise ValueError("导出并发必须在 1..8")
        if self.max_pages_per_subject <= 0:
            raise ValueError("每主体页面上限必须为正数")
        if not 1 <= self.model_workers <= 8:
            raise ValueError("模型并发必须在 1..8")
        if not 15 <= self.model_timeout_seconds <= 180:
            raise ValueError("单批模型超时必须在 15..180 秒")


class _Deadline:
    def __init__(self, seconds: int | None) -> None:
        self.started = time.monotonic()
        self.deadline = self.started + seconds if seconds is not None else None

    def check(self, stage: str) -> None:
        if self.deadline is not None and time.monotonic() >= self.deadline:
            raise TimeoutError(f"皇帝链路超过硬墙钟预算: {stage}")

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.started


def _run_with_model_anomaly_recovery(
    *,
    runner_factory: Callable[[], StructuredCodexRunner],
    operation: Callable[[StructuredCodexRunner, int], Any],
    initial_batch_size: int,
    maximum_recoveries: int = 2,
) -> tuple[Any, int, int]:
    """Resume checkpoints with a fresh runner and smaller batches after anomaly.

    StructuredCodexRunner intentionally cancels every peer after one abnormal
    subprocess.  The emperor job, however, owns the durable checkpoint boundary:
    it can recreate the runner and continue the unfinished work without granting
    a new wall-clock budget or repeating successful model calls.
    """

    batch_size = max(1, initial_batch_size)
    recovery_count = 0
    while True:
        runner = runner_factory()
        try:
            return operation(runner, batch_size), recovery_count, batch_size
        except ModelBatchAnomalyError:
            if recovery_count >= maximum_recoveries:
                raise
            recovery_count += 1
            batch_size = max(1, batch_size // 2)


def _load_current_config(workspace_root: Path, ruler: str) -> tuple[dict[str, Any], Mapping[str, Any]]:
    project = yaml.safe_load((workspace_root / "config/project.yml").read_text(encoding="utf-8"))
    configured = ((project.get("i5b_current_value") or {}).get("rulers") or {}).get(ruler)
    if not isinstance(configured, Mapping):
        raise ValueError(f"皇帝尚未进入当前链路: {ruler}")
    source_pack = json.loads(
        (workspace_root / str(configured["source_pack"])).read_text(encoding="utf-8")
    )
    return source_pack, configured


def _resolve_source_index(
    *,
    source_pack: Mapping[str, Any],
    source_index_path: Path | None,
    source_index_root: Path | None,
    required_works: Sequence[str] = (),
    preextracted_works: Sequence[str] = (),
) -> LocalSourceTextIndex:
    if source_index_path is not None:
        return LocalSourceTextIndex(source_index_path)
    configured_root = source_index_root or (
        Path(os.environ["EMPEROR_SOURCE_INDEX_ROOT"])
        if os.environ.get("EMPEROR_SOURCE_INDEX_ROOT")
        else None
    )
    if configured_root is None or not configured_root.is_dir():
        raise ValueError(
            "未提供可用史料索引；请设置 EMPEROR_SOURCE_INDEX_ROOT 或传 --source-index-root"
        )
    works = ({
        str(row["source_page"]).split("/", 1)[0]
        for row in source_pack.get("facts") or ()
        if row.get("source_page")
    } - {str(work) for work in preextracted_works}) | {
        str(work) for work in required_works
    }
    candidates = []
    for path in configured_root.rglob("*.sqlite3"):
        try:
            index = LocalSourceTextIndex(path)
            pages = list(index.iter_pages(works=sorted(works)))
            covers_every_work = all(
                next(index.iter_pages(works=[work]), None) is not None
                for work in works
            )
        except (OSError, ValueError):
            continue
        if pages and covers_every_work:
            candidates.append((len(pages), str(path), index))
    if not candidates:
        raise ValueError(f"史料索引根没有覆盖当前作品集: {sorted(works)}")
    return max(candidates, key=lambda row: (row[0], row[1]))[2]


def _resolve_dynasty_governance_root(
    *,
    source_index: LocalSourceTextIndex,
    configured_root: Path | None,
) -> Path:
    if configured_root is not None:
        return configured_root.resolve()
    for parent in source_index.path.resolve().parents:
        if parent.name == "source_text_indexes":
            return parent.parent / "dynasty_neutral_materials"
    raise ValueError("无法从史料索引推导朝代政书 current 根；请显式传入路径")


def _source_inventory(
    *,
    source_pack: Mapping[str, Any],
    source_index: LocalSourceTextIndex,
    works: Sequence[str],
    limits: RebuildLimits,
    deadline: _Deadline,
    aliases_by_subject: Mapping[str, Sequence[str]],
    known_pages_by_subject: Mapping[str, Sequence[str]],
    page_ranges: Mapping[str, Sequence[int]] | None = None,
) -> dict[str, Any]:
    subjects = [str(source_pack["ruler"]), *[str(row["person"]) for row in source_pack["members"]]]

    def recall(subject: str) -> dict[str, Any]:
        deadline.check("source_inventory")
        hits = source_index.recall(
            works=works,
            recall_terms=(subject, *aliases_by_subject.get(subject, ())),
            priority_terms=(
                "任命", "授任", "制度", "法令", "选举", "赋税", "治理",
                "攻破", "平定", "灭国", "诛灭", "战胜",
            ),
            page_ranges=page_ranges,
        )
        discovered = [hit.page_title for hit in hits[: limits.max_pages_per_subject]]
        pages = list(
            dict.fromkeys(
                [*known_pages_by_subject.get(subject, ()), *discovered]
            )
        )
        return {
            "subject": subject,
            "pages": pages,
        }

    with ThreadPoolExecutor(max_workers=min(limits.source_workers, len(subjects))) as pool:
        rows = list(pool.map(recall, subjects))
    indexed_works = {
        work
        for work in works
        if next(source_index.iter_pages(works=[work]), None) is not None
    }
    return {
        "source_index_identity": source_index.identity,
        "subject_count": len(rows),
        "candidate_page_count": len({page for row in rows for page in row["pages"]}),
        "subjects": rows,
        "missing_works": sorted(set(works) - indexed_works),
    }


def _self_review_samples(report: Mapping[str, Any], *, limit: int = 4) -> list[str]:
    profiles = list(report.get("profile_projection_review") or ())
    outcome_kind = {
        str(row["outcome_ref"]): str(row["outcome_kind"])
        for row in report.get("historical_outcome_clusters") or ()
    }
    risk_rank = {None: 0, "material": 1, "serious": 2, "critical": 3}
    grade_rank = {"import": 0, "important": 1, "top": 2, "historic": 3}
    selected = []

    def add(row: Mapping[str, Any] | None) -> None:
        if row is not None and str(row["person"]) not in selected:
            selected.append(str(row["person"]))

    add(
        max(
            profiles,
            key=lambda row: (
                risk_rank.get(row.get("candidate_negative_talent_severity"), 0),
                str(row["person"]),
            ),
            default=None,
        )
    )
    for kind in ("campaign", "governance"):
        add(
            max(
                (
                    row
                    for row in profiles
                    if any(
                        outcome_kind.get(str(ref)) == kind
                        for ref in row.get("outcome_refs") or ()
                    )
                ),
                key=lambda row: (
                    grade_rank.get(str(row.get("candidate_talent_grade")), -1),
                    len(row.get("outcome_refs") or ()),
                    str(row["person"]),
                ),
                default=None,
            )
        )
    for row in sorted(
        profiles,
        key=lambda value: (
            -grade_rank.get(str(value.get("candidate_talent_grade")), -1),
            str(value["person"]),
        ),
    ):
        add(row)
        if len(selected) >= limit:
            break
    return selected[:limit]


def rebuild_emperor(
    *,
    workspace_root: Path,
    ruler: str,
    source_index_path: Path | None,
    source_index_root: Path | None = None,
    dynasty_governance_root: Path | None = None,
    shared_backbone_root: Path | None = None,
    runtime_root: Path,
    limits: RebuildLimits = RebuildLimits(),
) -> dict[str, Any]:
    """Restart the current deterministic chain and atomically publish its outputs.

    Stage checkpoints live only below ``runtime_root``. A successful run removes
    them; a failure leaves the latest completed stage for a zero-model-call retry.
    """

    workspace_root = workspace_root.resolve()
    runtime_root = runtime_root.resolve()
    checkpoint_dir = runtime_root / "checkpoint"
    deadline = _Deadline(limits.wall_clock_seconds)
    source_pack, configured = _load_current_config(workspace_root, ruler)
    identity_resolver = HistoricalEntityResolver.load(
        workspace_root / "config/historical-entity-identities.yml",
        source_pack=source_pack,
    )
    shared_subject_refs = {
        str(name): identity_resolver.entity_for_name(str(name)).person_ref
        for name in configured.get("neutral_scan_shared_subjects") or ()
    }
    shared_backbone_token = str(
        configured.get("neutral_scan_backbone_material_token") or ""
    )
    if shared_subject_refs and not shared_backbone_token:
        raise ValueError("配置共享篇章主体时必须声明主干材料 token")
    if shared_backbone_token and any(
        value in shared_backbone_token for value in ("/", "\\", "..")
    ):
        raise ValueError("主干材料 token 含非法路径字符")
    aliases_by_subject = {
        name: identity_resolver.recall_terms(name)[1:]
        for name in (
            str(source_pack["ruler"]),
            *(str(row["person"]) for row in source_pack.get("members") or ()),
            *sorted(shared_subject_refs),
        )
    }
    known_pages_by_subject: dict[str, list[str]] = {ruler: []}
    for member in source_pack.get("members") or ():
        person = str(member["person"])
        biography = ((member.get("profile_review") or {}).get("full_lifecycle_biography") or {})
        known_pages_by_subject[person] = (
            [str(biography["source_page"])] if biography.get("source_page") else []
        )
    for fact in source_pack.get("facts") or ():
        if str(fact.get("record_ref") or "").startswith("PFACT-AUTO-"):
            continue
        name = str(fact.get("canonical_name") or "")
        if name in known_pages_by_subject and fact.get("source_page"):
            known_pages_by_subject[name].append(str(fact["source_page"]))
    backbone_works = [
        str(work) for work in configured.get("neutral_scan_backbone_works") or ()
    ]
    backsource_works = [
        str(work) for work in configured.get("neutral_scan_backsource_works") or ()
    ]
    supplement_works = [
        str(work) for work in configured.get("neutral_scan_supplement_works") or ()
    ]
    configured_scan_works = list(
        dict.fromkeys([*backbone_works, *backsource_works, *supplement_works])
    )
    dynasty_governance_token = str(
        configured.get("dynasty_governance_material_token") or ""
    )
    source_index = _resolve_source_index(
        source_pack=source_pack,
        source_index_path=source_index_path,
        source_index_root=source_index_root,
        required_works=(
            [*backbone_works, *backsource_works]
            if dynasty_governance_token
            else configured_scan_works
        ),
        preextracted_works=(
            sorted(
                {
                    str(row["source_page"]).split("/", 1)[0]
                    for row in source_pack.get("facts") or ()
                    if row.get("source_page")
                }
                - set(backbone_works)
                - set(backsource_works)
            )
            if dynasty_governance_token
            else ()
        ),
    )
    dynasty_governance_current: Mapping[str, Any] | None = None
    if dynasty_governance_token:
        governance_root = _resolve_dynasty_governance_root(
            source_index=source_index,
            configured_root=dynasty_governance_root,
        )
        governance_path = governance_root / dynasty_governance_token / "current.json"
        if not governance_path.is_file():
            raise ValueError(f"朝代政书 current 不存在: {governance_path}")
        dynasty_governance_current = json.loads(
            governance_path.read_text(encoding="utf-8")
        )
        if (
            dynasty_governance_current.get("schema_version")
            != "dynasty-governance-current-v1"
            or dynasty_governance_current.get("status")
            != "quality_accepted_shadow"
            or str(dynasty_governance_current.get("dynasty_token") or "")
            != dynasty_governance_token
            or str(dynasty_governance_current.get("source_index_identity") or "")
            != source_index.identity
        ):
            raise ValueError("朝代政书 current 头部合同与皇帝链路不匹配")
    works = sorted(
        set(configured_scan_works)
        | {
            str(row["source_page"]).split("/", 1)[0]
            for row in source_pack.get("facts") or ()
            if row.get("source_page")
        }
    )
    backbone_page_ranges = {
        str(work): [int(value) for value in bounds]
        for work, bounds in (
            configured.get("neutral_scan_backbone_page_ranges") or {}
        ).items()
    }
    input_fingerprint = _digest(
        {
            "ruler": ruler,
            "source_pack_sha256": source_pack["source_pack_sha256"],
            "source_index_identity": source_index.identity,
            "execution_limits": {
                key: value
                for key, value in asdict(limits).items()
                if key != "wall_clock_seconds"
            },
            "aliases_by_subject": aliases_by_subject,
            "identity_bindings": identity_resolver.bindings(
                [
                    str(source_pack["ruler_ref"]),
                    *(str(row["person_ref"]) for row in source_pack.get("members") or ()),
                    *shared_subject_refs.values(),
                ]
            ),
            "known_pages_by_subject": known_pages_by_subject,
            "backbone_page_ranges": backbone_page_ranges,
            "configured_scan_works": configured_scan_works,
        }
    )
    marker = checkpoint_dir / "source_inventory.json"
    if marker.is_file():
        saved = json.loads(marker.read_text(encoding="utf-8"))
        inventory = saved["output"] if saved.get("input_fingerprint") == input_fingerprint else None
    else:
        inventory = None
    if inventory is None:
        inventory = _source_inventory(
            source_pack=source_pack,
            source_index=source_index,
            works=works,
            limits=limits,
            deadline=deadline,
            aliases_by_subject=aliases_by_subject,
            known_pages_by_subject=known_pages_by_subject,
            page_ranges=backbone_page_ranges,
        )
        _atomic_text(
            marker,
            json.dumps(
                {"input_fingerprint": input_fingerprint, "output": inventory},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
    deadline.check("neutral_extraction")
    neutral_path = workspace_root / str(configured["neutral_materials"])
    current_neutral = (
        json.loads(neutral_path.read_text(encoding="utf-8"))
        if neutral_path.is_file()
        else None
    )
    # A quality-accepted dynasty current is the one-time neutral extraction for
    # specialist governance works.  The ruler chain consumes it; it must not
    # rescan the same books per emperor.
    directed_supplement_works = (
        [] if dynasty_governance_current is not None else supplement_works
    )
    backbone_plan = build_ruler_neutral_plan(
        source_pack=source_pack,
        source_index=source_index,
        inventory=inventory,
        identity_resolver=identity_resolver,
        allowed_works=backbone_works or configured_scan_works,
        allowed_page_ranges=backbone_page_ranges,
        shared_subjects=shared_subject_refs,
    )
    shared_backbone_identity = _digest(
        {
            "source_index_identity": backbone_plan["source_index_identity"],
            "page_batches": [
                {
                    **dict(batch),
                    "segments": [
                        {
                            key: value
                            for key, value in segment.items()
                            if key != "chronicle_ruler_active"
                        }
                        for segment in batch["segments"]
                    ],
                }
                for batch in backbone_plan["page_batches"]
            ],
        }
    )
    shared_backbone_path = None
    if shared_backbone_root is not None and shared_backbone_token:
        resolved_shared_root = shared_backbone_root.resolve()
        shared_backbone_path = (
            resolved_shared_root / shared_backbone_token / "current.json"
        ).resolve()
        if resolved_shared_root not in shared_backbone_path.parents:
            raise ValueError("共享主干材料路径越界")
    shared_backbone_current: Mapping[str, Any] | None = None
    if shared_backbone_path is not None and shared_backbone_path.is_file():
        candidate = json.loads(shared_backbone_path.read_text(encoding="utf-8"))
        if (
            candidate.get("schema_version") == "shared-chronicle-current-v1"
            and candidate.get("status") == "quality_contract_valid_shadow"
            and candidate.get("material_token") == shared_backbone_token
            and candidate.get("backbone_identity") == shared_backbone_identity
        ):
            shared_backbone_current = candidate.get("materials")
    combined_backbone_current = {
        "batch_results": [
            *((shared_backbone_current or {}).get("batch_results") or ()),
            *((current_neutral or {}).get("batch_results") or ()),
        ],
        "batch_fingerprints": {
            **dict((shared_backbone_current or {}).get("batch_fingerprints") or {}),
            **dict((current_neutral or {}).get("batch_fingerprints") or {}),
        },
    }
    model_policy = yaml.safe_load(
        (workspace_root / "config/model-policy.yml").read_text(encoding="utf-8")
    )
    route = resolve_agent_route(
        model_policy,
        stage_code="person_rebuild_minimum_claim",
        escalation_reasons=(),
    )
    multi_schema_path = checkpoint_dir / "multi-page-neutral-output.schema.json"
    _atomic_text(
        multi_schema_path,
        json.dumps(
            build_compact_multi_output_schema(
                workspace_root / "config/shared-neutral-extraction-output.schema.json"
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    def neutral_runner_factory() -> StructuredCodexRunner:
        return StructuredCodexRunner(
            codex_bin="codex",
            model=str(route["model"]),
            reasoning_effort=str(route["reasoning_effort"]),
            output_schema_path=multi_schema_path,
            timeout_seconds=limits.model_timeout_seconds,
            cwd=workspace_root,
            deadline_monotonic=deadline.deadline,
        )

    subject_ref_by_name = {
        str(source_pack["ruler"]): str(source_pack["ruler_ref"]),
        **{
            str(row["person"]): str(row["person_ref"])
            for row in source_pack.get("members") or ()
        },
    }
    deterministic_campaigns = discover_deterministic_backbone_campaigns(
        backbone_plan=backbone_plan,
        ruler_name=str(source_pack["ruler"]),
        ruler_ref=str(source_pack["ruler_ref"]),
        identity_resolver=identity_resolver,
    )
    routed_backbone_plan = build_deterministic_fact_resolution_plan(
        backbone_plan,
        dense_segment_refs=[
            str(row["segment_ref"])
            for row in deterministic_campaigns.get("events") or ()
        ],
    )
    deterministic_campaign_seed = seed_deterministic_campaign_facts(
        plan=routed_backbone_plan,
        current=combined_backbone_current,
        discovery=deterministic_campaigns,
    )
    deterministic_campaign_facts_by_segment: dict[str, list[Mapping[str, Any]]] = {}
    for event in deterministic_campaigns.get("events") or ():
        deterministic_campaign_facts_by_segment.setdefault(
            str(event["segment_ref"]), []
        ).append(event["neutral_fact"])
    if not routed_backbone_plan["page_batches"]:
        raise ValueError("确定性扫描未发现需要事实裁决的编年主干事件单元")
    (
        backbone_materials,
        backbone_recovery_count,
        backbone_final_pages_per_call,
    ) = _run_with_model_anomaly_recovery(
        runner_factory=neutral_runner_factory,
        operation=lambda runner, pages_per_call: extract_current_neutral_materials(
            plan=routed_backbone_plan,
            current=deterministic_campaign_seed["current"],
            runner=runner,
            max_workers=limits.model_workers,
            checkpoint_dir=checkpoint_dir / "neutral_extraction" / "backbone",
            pages_per_call=pages_per_call,
            subject_ref_by_name=subject_ref_by_name,
            identity_resolver=identity_resolver,
            supplemental_facts_by_segment=deterministic_campaign_facts_by_segment,
        ),
        initial_batch_size=12,
        maximum_recoveries=0,
    )
    backbone_model_call_count = int(backbone_materials.pop("model_call_count"))
    backbone_materials["chronicle_role_projections"] = (
        build_chronicle_role_projections(
            plan=routed_backbone_plan,
            neutral_materials=backbone_materials,
        )
    )
    if shared_backbone_path is not None:
        _atomic_text(
            shared_backbone_path,
            json.dumps(
                {
                    "schema_version": "shared-chronicle-current-v1",
                    "status": "quality_contract_valid_shadow",
                    "material_token": shared_backbone_token,
                    "backbone_identity": shared_backbone_identity,
                    "source_index_identity": source_index.identity,
                    "materials": backbone_materials,
                    "formal_write": False,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
    accepted_event_signatures = build_backbone_event_signatures(
        backbone_plan=routed_backbone_plan,
        backbone_materials=backbone_materials,
        identity_resolver=identity_resolver,
    )
    if backbone_works and (backsource_works or directed_supplement_works):
        neutral_plan = build_event_directed_neutral_plan(
            backbone_plan=routed_backbone_plan,
            event_signatures=accepted_event_signatures,
            source_index=source_index,
            identity_resolver=identity_resolver,
            backsource_works=backsource_works,
            supplement_works=directed_supplement_works,
        )
        if not neutral_plan["event_signatures"]:
            raise ValueError("编年主干未形成可定向回源的中性事件签名")
        target_roles = {
            str(segment.get("source_role") or "")
            for batch in neutral_plan["page_batches"]
            for segment in batch["segments"]
        }
        required_roles = {
            role
            for role, values in (
                ("backsource", backsource_works),
                ("supplement", directed_supplement_works),
            )
            if values
        }
        if not required_roles <= target_roles:
            missing = ", ".join(sorted(required_roles - target_roles))
            raise ValueError(f"事件级定向回源未命中配置史源层: {missing}")
    else:
        neutral_plan = routed_backbone_plan
    model_plan = build_deterministic_fact_resolution_plan(neutral_plan)
    target_segments = [
        segment
        for batch in model_plan["page_batches"]
        for segment in batch["segments"]
        if segment.get("source_role") in {"backsource", "supplement"}
    ]
    if target_segments:
        directed_current = {
            "batch_results": [
                *((current_neutral or {}).get("batch_results") or ()),
                *(backbone_materials.get("batch_results") or ()),
            ],
            "batch_fingerprints": {
                **dict((current_neutral or {}).get("batch_fingerprints") or {}),
                **dict(backbone_materials.get("batch_fingerprints") or {}),
            },
        }
        (
            neutral_materials,
            directed_recovery_count,
            neutral_final_pages_per_call,
        ) = _run_with_model_anomaly_recovery(
            runner_factory=neutral_runner_factory,
            operation=lambda runner, pages_per_call: extract_current_neutral_materials(
                plan=model_plan,
                current=directed_current,
                runner=runner,
                max_workers=limits.model_workers,
                checkpoint_dir=checkpoint_dir / "neutral_extraction" / "backsource",
                pages_per_call=pages_per_call,
                subject_ref_by_name=subject_ref_by_name,
                identity_resolver=identity_resolver,
            ),
            initial_batch_size=12,
            maximum_recoveries=0,
        )
        backsource_model_call_count = int(
            neutral_materials.pop("model_call_count")
        )
    else:
        neutral_materials = backbone_materials
        directed_recovery_count = 0
        neutral_final_pages_per_call = backbone_final_pages_per_call
        backsource_model_call_count = 0
    neutral_recovery_count = backbone_recovery_count + directed_recovery_count
    neutral_model_call_count = (
        backbone_model_call_count + backsource_model_call_count
    )
    neutral_materials["deterministic_routing"] = model_plan[
        "deterministic_routing"
    ]
    neutral_materials["deterministic_campaign_discovery"] = deterministic_campaigns
    neutral_materials["deterministic_campaign_seed"] = {
        key: value
        for key, value in deterministic_campaign_seed.items()
        if key != "current"
    }
    neutral_materials["chronicle_role_projections"] = build_chronicle_role_projections(
        plan=model_plan,
        neutral_materials=neutral_materials,
    )
    if dynasty_governance_current is not None:
        neutral_materials = merge_dynasty_governance_current(
            neutral_materials=neutral_materials,
            current=dynasty_governance_current,
            expected_dynasty_token=dynasty_governance_token,
            expected_source_index_identity=source_index.identity,
            period_terms=[
                str(value)
                for value in configured.get("dynasty_governance_period_terms") or ()
            ],
            identity_resolver=identity_resolver,
            ruler_ref=str(source_pack["ruler_ref"]),
            subject_ref_by_name={
                str(source_pack["ruler"]): str(source_pack["ruler_ref"]),
                **{
                    str(row["person"]): str(row["person_ref"])
                    for row in source_pack.get("members") or ()
                },
            },
            event_signatures=model_plan.get("event_signatures") or (),
        )
    if current_neutral and current_neutral.get("outcome_projection"):
        neutral_materials["outcome_projection"] = current_neutral[
            "outcome_projection"
        ]
    _atomic_text(
        neutral_path,
        json.dumps(neutral_materials, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
    )
    deadline.check("outcome_projection")
    outcome_route = resolve_agent_route(
        model_policy,
        stage_code="episode_candidate_normalization",
        escalation_reasons=(),
    )
    outcome_schema_path = workspace_root / "config/current-outcome-candidate-output.schema.json"
    def outcome_runner_factory() -> StructuredCodexRunner:
        return StructuredCodexRunner(
            codex_bin="codex",
            model=str(outcome_route["model"]),
            reasoning_effort=str(outcome_route["reasoning_effort"]),
            output_schema_path=outcome_schema_path,
            timeout_seconds=limits.model_timeout_seconds,
            cwd=workspace_root,
            deadline_monotonic=deadline.deadline,
        )

    (
        outcome_projection,
        outcome_recovery_count,
        outcome_final_facts_per_call,
    ) = _run_with_model_anomaly_recovery(
        runner_factory=outcome_runner_factory,
        operation=lambda runner, facts_per_call: project_current_outcomes(
            source_pack_path=workspace_root / str(configured["source_pack"]),
            neutral_materials=neutral_materials,
            source_index=source_index,
            schema_path=outcome_schema_path,
            runner=runner,
            checkpoint_dir=checkpoint_dir / "outcome_projection",
            workspace_root=workspace_root,
            max_workers=min(limits.model_workers, 4),
            facts_per_call=facts_per_call,
        ),
        initial_batch_size=16,
        maximum_recoveries=0,
    )
    neutral_materials["outcome_projection"] = {
        "schema_version": "current-outcome-disposition-v1",
        "policy_fingerprint": outcome_projection["policy_fingerprint"],
        "dispositions": outcome_projection["dispositions"],
    }
    _atomic_text(
        neutral_path,
        json.dumps(neutral_materials, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
    )
    deadline.check("current_projection")
    source_pack_path = workspace_root / str(configured["source_pack"])
    outcome_layers = write_current_outcome_layers(workspace_root)
    report = build_i5b_current_value(source_pack_path, workspace_root=workspace_root)
    if report["ruler"] != ruler:
        raise ValueError("链路结果皇帝不匹配")

    deadline.check("self_review")
    samples = _self_review_samples(report)
    with ThreadPoolExecutor(max_workers=min(limits.export_workers, max(1, len(samples)))) as pool:
        person_exports = list(
            pool.map(lambda person: render_scoring_detail_markdown(report, person=person), samples)
        )
    if any("## 当前人物画像" not in rendered for rendered in person_exports):
        raise ValueError("臣子导出自审失败")
    ruler_markdown = render_scoring_detail_markdown(report)
    if "## 治理成果登记" not in ruler_markdown or "## 战役登记" not in ruler_markdown:
        raise ValueError("皇帝导出自审失败")

    deadline.check("publish")
    result_path = workspace_root / str(configured["result"])
    _atomic_text(
        result_path,
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    _atomic_text(result_path.with_suffix(".md"), ruler_markdown)
    if checkpoint_dir.exists():
        shutil.rmtree(checkpoint_dir)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "rebuilt_before_database_write",
        "ruler": ruler,
        "source_index_identity": source_index.identity,
        "candidate_page_count": inventory["candidate_page_count"],
        "source_index_missing_works": inventory["missing_works"],
        "neutral_fact_count": neutral_materials["fanout"]["fact_count"],
        "neutral_model_call_count": neutral_model_call_count,
        "neutral_backbone_model_call_count": backbone_model_call_count,
        "neutral_backsource_model_call_count": backsource_model_call_count,
        "neutral_model_anomaly_recovery_count": neutral_recovery_count,
        "neutral_final_pages_per_call": neutral_final_pages_per_call,
        "neutral_deterministic_routing": {
            key: value
            for key, value in model_plan["deterministic_routing"].items()
            if key != "deterministic_empty_segment_refs"
        },
        "neutral_deterministic_campaign_seed": {
            key: value
            for key, value in deterministic_campaign_seed.items()
            if key != "current" and key != "seeded_segment_refs"
        },
        "dynasty_governance_fact_count": int(
            (neutral_materials.get("dynasty_governance_current") or {}).get(
                "fact_count"
            )
            or 0
        ),
        "outcome_candidate_count": outcome_projection["candidate_count"],
        "outcome_model_call_count": outcome_projection["model_call_count"],
        "outcome_model_anomaly_recovery_count": outcome_recovery_count,
        "outcome_final_facts_per_call": outcome_final_facts_per_call,
        "source_pack_changed": outcome_projection["source_pack_changed"],
        "historical_outcome_registry_fingerprint": outcome_layers["registry"][
            "registry_fingerprint"
        ],
        "sampled_person_exports": samples,
        "net_signal": report["net_signal"],
        "elapsed_seconds": round(deadline.elapsed, 3),
        "database_write_count": 0,
        "formal_score_write_count": 0,
        "result": str(result_path),
    }
