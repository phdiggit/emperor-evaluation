from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
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
    NEUTRAL_EXTRACTION_POLICY_VERSION,
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
from emperor_v4.runtime.emperor_outcome_projection import (
    PROJECTION_POLICY_VERSION,
    build_outcome_transport_schema,
    project_current_outcomes,
)
from emperor_v4.runtime.deterministic_campaign_extraction import (
    discover_deterministic_backbone_campaigns,
)
from emperor_v4.runtime.structured_codex_runner import (
    ModelBatchAnomalyError,
    StructuredCodexRunner,
)


SCHEMA_VERSION = "emperor-rebuild-v1"
STAGE_MANIFEST_SCHEMA_VERSION = "emperor-stage-manifest-v1"
STAGE_CONTRACTS = {
    "source_inventory": "source-inventory-stage-v1",
    "neutral_materials": "shared-directed-neutral-stage-v1",
    "outcome_projection": "current-outcome-projection-stage-v2",
    "current_projection": "registry-profile-i5b-stage-v1",
}


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


def _file_digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _contract_files_fingerprint(root: Path, relative_paths: Sequence[str]) -> str:
    return _digest(
        {
            relative: _file_digest(root / relative)
            for relative in sorted(str(value) for value in relative_paths)
        }
    )


def _stage_manifest_path(stage_cache_root: Path, stage: str) -> Path:
    return stage_cache_root.resolve() / stage / "current.json"


def _restore_stage_artifacts(
    *,
    stage_cache_root: Path | None,
    stage: str,
    input_fingerprint: str,
    producer_contract_fingerprint: str,
    targets: Mapping[str, Path],
) -> dict[str, Any] | None:
    if stage_cache_root is None:
        return None
    manifest_path = _stage_manifest_path(stage_cache_root, stage)
    if not manifest_path.is_file():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("schema_version") != STAGE_MANIFEST_SCHEMA_VERSION
        or manifest.get("stage") != stage
        or manifest.get("status") != "quality_accepted"
        or manifest.get("input_fingerprint") != input_fingerprint
        or manifest.get("producer_contract_fingerprint")
        != producer_contract_fingerprint
    ):
        return None
    artifacts = manifest.get("artifacts") or {}
    if set(artifacts) != set(targets):
        return None
    sources: dict[str, Path] = {}
    for name, target in targets.items():
        row = artifacts.get(name) or {}
        source = manifest_path.parent / str(row.get("file") or "")
        if (
            not source.is_file()
            or _file_digest(source) != str(row.get("sha256") or "")
        ):
            return None
        sources[name] = source
    for name, target in targets.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
        shutil.copy2(sources[name], temporary)
        os.replace(temporary, target)
    return manifest


def _accept_stage(
    *,
    runtime_root: Path,
    stage_cache_root: Path | None,
    stage: str,
    input_fingerprint: str,
    producer_contract_fingerprint: str,
    quality_checks: Mapping[str, Any],
    artifacts: Mapping[str, Path],
) -> dict[str, Any]:
    manifest = {
        "schema_version": STAGE_MANIFEST_SCHEMA_VERSION,
        "stage": stage,
        "status": "quality_accepted",
        "input_fingerprint": input_fingerprint,
        "producer_contract_fingerprint": producer_contract_fingerprint,
        "quality_checks": dict(quality_checks),
        "artifacts": {},
    }
    roots = [runtime_root.resolve() / "stages"]
    if stage_cache_root is not None:
        roots.append(stage_cache_root.resolve())
    for root in roots:
        stage_root = root / stage
        stage_root.mkdir(parents=True, exist_ok=True)
        rows = {}
        for name, source in artifacts.items():
            if not source.is_file():
                raise ValueError(f"阶段产物不存在: {stage}/{name}")
            artifact_name = f"{name}.json"
            target = stage_root / artifact_name
            temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
            shutil.copy2(source, temporary)
            os.replace(temporary, target)
            rows[name] = {
                "file": artifact_name,
                "sha256": _file_digest(target),
            }
        payload = {**manifest, "artifacts": rows}
        _atomic_text(
            stage_root / "current.json",
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
        manifest = payload
    return manifest


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


def _shared_backbone_contract(
    *,
    project: Mapping[str, Any],
    ruler: str,
) -> dict[str, Any] | None:
    """Resolve and validate the repository-wide chronicle range ownership."""

    rulers = (project.get("i5b_current_value") or {}).get("rulers") or {}
    configured = rulers.get(ruler)
    if not isinstance(configured, Mapping):
        raise ValueError(f"皇帝尚未进入当前链路: {ruler}")
    shared_catalog = (
        (project.get("neutral_material_reuse") or {}).get(
            "shared_chronicle_materials"
        )
        or {}
    )
    if not isinstance(shared_catalog, Mapping):
        raise ValueError("共享编年材料中央目录必须是对象")

    range_owners: list[tuple[str, str, int, int]] = []
    for catalog_token, catalog_config in shared_catalog.items():
        token_name = str(catalog_token)
        if not isinstance(catalog_config, Mapping):
            raise ValueError(f"共享编年 token 合同必须是对象: {token_name}")
        referenced_owners = {
            str(name)
            for name, value in rulers.items()
            if isinstance(value, Mapping)
            and str(value.get("neutral_scan_backbone_material_token") or "")
            == token_name
        }
        subjects = {str(value) for value in catalog_config.get("subjects") or ()}
        if subjects != referenced_owners:
            raise ValueError(
                f"共享编年 token 主体闭包与引用皇帝不一致: {token_name}"
            )
        if not str(catalog_config.get("extraction_contract") or ""):
            raise ValueError(f"共享编年 token 缺少抽取合同版本: {token_name}")
        works = {str(value) for value in catalog_config.get("works") or ()}
        page_ranges = catalog_config.get("page_ranges") or {}
        if not works or not isinstance(page_ranges, Mapping):
            raise ValueError(f"共享编年 token 缺少史书或连续范围: {token_name}")
        if works != {str(value) for value in page_ranges}:
            raise ValueError(f"共享编年 token 的史书与连续范围不一致: {token_name}")
        for work, bounds in page_ranges.items():
            if (
                not isinstance(bounds, Sequence)
                or isinstance(bounds, (str, bytes))
                or len(bounds) != 2
            ):
                raise ValueError(f"共享编年连续范围必须是起止页: {token_name}/{work}")
            start, end = (int(value) for value in bounds)
            if start > end:
                raise ValueError(f"共享编年连续范围起止颠倒: {token_name}/{work}")
            range_owners.append((f"token:{token_name}", str(work), start, end))

    forbidden_inline_fields = (
        "neutral_scan_backbone_works",
        "neutral_scan_backbone_page_ranges",
        "neutral_scan_shared_subjects",
    )
    for owner, owner_config in rulers.items():
        if not isinstance(owner_config, Mapping):
            continue
        owner_token = str(
            owner_config.get("neutral_scan_backbone_material_token") or ""
        )
        if owner_token:
            if owner_token not in shared_catalog:
                raise ValueError(f"共享编年 token 未在中央目录登记: {owner_token}/{owner}")
            duplicated = [
                field for field in forbidden_inline_fields if field in owner_config
            ]
            if duplicated:
                raise ValueError(
                    f"共享编年范围只能在中央目录定义: {owner_token}/{owner}/"
                    f"{','.join(duplicated)}"
                )
            continue
        page_ranges = owner_config.get("neutral_scan_backbone_page_ranges") or {}
        if not isinstance(page_ranges, Mapping):
            raise ValueError(f"皇帝编年连续范围必须是对象: {owner}")
        for work, bounds in page_ranges.items():
            if (
                not isinstance(bounds, Sequence)
                or isinstance(bounds, (str, bytes))
                or len(bounds) != 2
            ):
                raise ValueError(f"皇帝编年连续范围必须是起止页: {owner}/{work}")
            start, end = (int(value) for value in bounds)
            if start > end:
                raise ValueError(f"皇帝编年连续范围起止颠倒: {owner}/{work}")
            range_owners.append((f"ruler:{owner}", str(work), start, end))

    for index, left in enumerate(range_owners):
        for right in range_owners[index + 1 :]:
            left_owner, left_work, left_start, left_end = left
            right_owner, right_work, right_start, right_end = right
            if (
                left_owner != right_owner
                and left_work == right_work
                and max(left_start, right_start) <= min(left_end, right_end)
            ):
                raise ValueError(
                    "编年连续范围重叠但未复用同一中央 token: "
                    f"{left_owner}/{right_owner}/{left_work}/"
                    f"{max(left_start, right_start)}-{min(left_end, right_end)}"
                )

    token = str(configured.get("neutral_scan_backbone_material_token") or "")
    if not token:
        return None
    owners = {
        str(name)
        for name, value in rulers.items()
        if isinstance(value, Mapping)
        and str(value.get("neutral_scan_backbone_material_token") or "") == token
    }
    catalog_config = shared_catalog[token]
    works = sorted(str(value) for value in catalog_config["works"])
    ranges = {
        str(work): [int(value) for value in bounds]
        for work, bounds in sorted(catalog_config["page_ranges"].items())
    }
    extraction_contract = str(catalog_config.get("extraction_contract") or "")
    if not extraction_contract:
        raise ValueError(f"共享编年 token 缺少抽取合同版本: {token}")
    return {
        "material_token": token,
        "owners": sorted(owners),
        "works": works,
        "page_ranges": ranges,
        "extraction_contract": extraction_contract,
    }


def _merge_neutral_currents(
    currents: Sequence[Mapping[str, Any] | None],
) -> dict[str, Any]:
    batch_results = []
    batch_fingerprints: dict[str, Any] = {}
    conflicting_fingerprint_keys: set[str] = set()
    seen_results: set[str] = set()
    for current in currents:
        if not current:
            continue
        for result in current.get("batch_results") or ():
            identity = _digest(result)
            if identity in seen_results:
                continue
            seen_results.add(identity)
            batch_results.append(result)
        for key, value in (current.get("batch_fingerprints") or {}).items():
            key = str(key)
            if key in conflicting_fingerprint_keys:
                continue
            previous = batch_fingerprints.get(key)
            if previous is not None and previous != value:
                # Batch identities may legitimately be reused at segment level
                # after a plan change.  Dropping the conflicting whole-batch
                # fingerprint forces the stricter segment validation path.
                batch_fingerprints.pop(key, None)
                conflicting_fingerprint_keys.add(key)
                continue
            batch_fingerprints[key] = value
    return {
        "batch_results": batch_results,
        "batch_fingerprints": batch_fingerprints,
    }


def _shared_backbone_identity(
    plan: Mapping[str, Any],
    *,
    extraction_contract: str = "",
) -> str:
    """Identify shared atoms without the current ruler's projection flag."""

    return _digest(
        {
            "source_index_identity": plan["source_index_identity"],
            "extraction_contract": extraction_contract,
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
                for batch in plan["page_batches"]
            ],
        }
    )


def _shared_subject_coverage(
    *,
    plan: Mapping[str, Any],
    materials: Mapping[str, Any],
    owner_refs: Mapping[str, str],
    deterministic_empty_segment_refs: Sequence[str] = (),
) -> dict[str, Any]:
    """Prove that every shared ruler's eligible chronicle units were resolved."""

    segments = [
        segment
        for batch in plan.get("page_batches") or ()
        for segment in batch.get("segments") or ()
    ]
    reviewed_segment_refs = {
        str(review["segment_ref"])
        for result in materials.get("batch_results") or ()
        for review in result.get("segment_reviews") or ()
        if review.get("segment_ref")
    }
    deterministic_empty_refs = {
        str(value)
        for value in deterministic_empty_segment_refs
    }
    resolved_segment_refs = reviewed_segment_refs | deterministic_empty_refs
    facts = list((materials.get("fanout") or {}).get("facts") or ())
    subjects = []
    for canonical_name, subject_ref in sorted(owner_refs.items()):
        subject_ref = str(subject_ref)
        eligible_refs = {
            str(segment["segment_ref"])
            for segment in segments
            if subject_ref
            in {
                str(value) for value in segment.get("subject_refs") or ()
            }
        }
        window_refs = {
            str(segment["segment_ref"])
            for segment in segments
            if str(segment.get("chronicle_ruler_ref") or "") == subject_ref
        }
        missing_refs = sorted(eligible_refs - resolved_segment_refs)
        fact_refs = sorted(
            {
                str(fact["fact_ref"])
                for fact in facts
                if fact.get("fact_ref")
                and any(
                    str(actor.get("subject_ref") or "") == subject_ref
                    and actor.get("role") != "mentioned_only"
                    for actor in fact.get("actors") or ()
                )
            }
        )
        coverage_complete = bool(eligible_refs) and bool(window_refs) and not missing_refs
        subjects.append(
            {
                "canonical_name": str(canonical_name),
                "subject_ref": subject_ref,
                "eligible_segment_count": len(eligible_refs),
                "window_segment_count": len(window_refs),
                "resolved_segment_count": len(eligible_refs & resolved_segment_refs),
                "neutral_fact_count": len(fact_refs),
                "neutral_fact_refs": fact_refs,
                "missing_segment_refs": missing_refs,
                "coverage_complete": coverage_complete,
            }
        )
    return {
        "schema_version": "shared-chronicle-subject-coverage-v1",
        "coverage_complete": bool(subjects)
        and all(row["coverage_complete"] for row in subjects),
        "subjects": subjects,
    }


def _shared_current_has_complete_subject_coverage(
    *,
    candidate: Mapping[str, Any],
    expected_backbone_identity: str,
    recomputed_coverage: Mapping[str, Any],
) -> bool:
    return bool(
        candidate.get("backbone_identity") == expected_backbone_identity
        and candidate.get("subject_coverage") == recomputed_coverage
        and recomputed_coverage.get("coverage_complete")
    )


def _project_event_signatures_for_ruler(
    *,
    plan: Mapping[str, Any],
    signatures: Sequence[Mapping[str, Any]],
    ruler_ref: str,
) -> list[Mapping[str, Any]]:
    """Keep own actions and minister actions inside the current ruler window."""

    chronicle_ruler_by_segment = {
        str(segment["segment_ref"]): str(segment["chronicle_ruler_ref"])
        for batch in plan.get("page_batches") or ()
        for segment in batch.get("segments") or ()
        if segment.get("chronicle_ruler_ref")
    }
    return [
        signature
        for signature in signatures
        if ruler_ref
        in {
            str(row.get("subject_ref") or "")
            for row in signature.get("subject_bindings") or ()
        }
        or any(
            chronicle_ruler_by_segment.get(str(row.get("segment_ref") or ""))
            == ruler_ref
            for row in signature.get("backbone_quotes") or ()
        )
    ]


def _ruler_backbone_fact_refs(
    *,
    plan: Mapping[str, Any],
    neutral_materials: Mapping[str, Any],
    ruler_ref: str,
) -> list[str]:
    segment_ruler_refs = {
        str(segment["segment_ref"]): str(segment.get("chronicle_ruler_ref") or "")
        for batch in plan.get("page_batches") or ()
        for segment in batch.get("segments") or ()
    }
    return sorted(
        str(fact["fact_ref"])
        for fact in (neutral_materials.get("fanout") or {}).get("facts") or ()
        if str(fact.get("segment_ref") or "") in segment_ruler_refs
        and (
            segment_ruler_refs[str(fact["segment_ref"])] == ruler_ref
            or any(
                str(actor.get("subject_ref") or "") == ruler_ref
                for actor in fact.get("actors") or ()
            )
        )
    )


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
    stage_cache_root: Path | None = None,
    runtime_root: Path,
    limits: RebuildLimits = RebuildLimits(),
    stage_callback: Callable[[str, str, Mapping[str, Any]], None] | None = None,
    stop_after_stage: str | None = None,
) -> dict[str, Any]:
    """Restart the current deterministic chain and atomically publish its outputs.

    Stage checkpoints live only below ``runtime_root``. A successful run removes
    them; a failure leaves the latest completed stage for a zero-model-call retry.
    """

    workspace_root = workspace_root.resolve()
    runtime_root = runtime_root.resolve()
    checkpoint_dir = runtime_root / "checkpoint"
    deadline = _Deadline(limits.wall_clock_seconds)
    stage_results: list[dict[str, Any]] = []

    def notify_stage(
        stage: str, status: str, details: Mapping[str, Any] | None = None
    ) -> None:
        payload = {
            **dict(details or {}),
            "stage": stage,
            "status": status,
        }
        if status in {"quality_accepted", "reused"}:
            stage_results.append(payload)
        if stage_callback is not None:
            stage_callback(stage, status, payload)

    source_pack, configured = _load_current_config(workspace_root, ruler)
    project = yaml.safe_load(
        (workspace_root / "config/project.yml").read_text(encoding="utf-8")
    )
    shared_contract = _shared_backbone_contract(project=project, ruler=ruler)
    identity_resolver = HistoricalEntityResolver.load(
        workspace_root / "config/historical-entity-identities.yml",
        source_pack=source_pack,
    )
    shared_owner_names = (
        list(shared_contract["owners"]) if shared_contract is not None else []
    )
    shared_owner_refs = {
        str(name): identity_resolver.entity_for_name(str(name)).person_ref
        for name in shared_owner_names
    }
    shared_subject_refs = {
        name: subject_ref
        for name, subject_ref in shared_owner_refs.items()
        if str(name) != ruler
    }
    shared_backbone_token = str(
        (shared_contract or {}).get("material_token") or ""
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
    backbone_works = (
        [str(work) for work in shared_contract["works"]]
        if shared_contract is not None
        else [
            str(work)
            for work in configured.get("neutral_scan_backbone_works") or ()
        ]
    )
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
    backbone_page_ranges = (
        {
            str(work): [int(value) for value in bounds]
            for work, bounds in shared_contract["page_ranges"].items()
        }
        if shared_contract is not None
        else {
            str(work): [int(value) for value in bounds]
            for work, bounds in (
                configured.get("neutral_scan_backbone_page_ranges") or {}
            ).items()
        }
    )
    input_fingerprint = _digest(
        {
            "ruler": ruler,
            "source_pack_sha256": source_pack["source_pack_sha256"],
            "source_index_identity": source_index.identity,
            # Concurrency, timeout and export settings may change while
            # supervising a retry; they do not change historical content.
            "inventory_limits": {
                "max_pages_per_subject": limits.max_pages_per_subject,
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
    inventory_contract_fingerprint = _digest(
        {
            "contract": STAGE_CONTRACTS["source_inventory"],
            "identity_config": _contract_files_fingerprint(
                workspace_root,
                ["config/historical-entity-identities.yml"],
            ),
        }
    )
    marker = checkpoint_dir / "source_inventory.json"
    notify_stage("source_inventory", "running")
    restored_inventory = _restore_stage_artifacts(
        stage_cache_root=stage_cache_root,
        stage="source_inventory",
        input_fingerprint=input_fingerprint,
        producer_contract_fingerprint=inventory_contract_fingerprint,
        targets={"inventory": marker},
    )
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
    inventory_stage = _accept_stage(
        runtime_root=runtime_root,
        stage_cache_root=stage_cache_root,
        stage="source_inventory",
        input_fingerprint=input_fingerprint,
        producer_contract_fingerprint=inventory_contract_fingerprint,
        quality_checks={
            "candidate_page_count": int(inventory["candidate_page_count"]),
            "missing_works": list(inventory["missing_works"]),
            "source_index_identity": source_index.identity,
        },
        artifacts={"inventory": marker},
    )
    notify_stage(
        "source_inventory",
        "reused" if restored_inventory is not None else "quality_accepted",
        inventory_stage,
    )
    deadline.check("neutral_extraction")
    neutral_path = workspace_root / str(configured["neutral_materials"])
    neutral_stage_input_fingerprint = _digest(
        {
            "inventory_input_fingerprint": input_fingerprint,
            "shared_contract": shared_contract,
            "dynasty_governance_current": (
                {
                    "input_fingerprint": dynasty_governance_current.get(
                        "input_fingerprint"
                    ),
                    "source_index_identity": dynasty_governance_current.get(
                        "source_index_identity"
                    ),
                }
                if dynasty_governance_current is not None
                else None
            ),
        }
    )
    neutral_stage_contract_fingerprint = _digest(
        {
            "contract": STAGE_CONTRACTS["neutral_materials"],
            "neutral_policy": NEUTRAL_EXTRACTION_POLICY_VERSION,
            "files": _contract_files_fingerprint(
                workspace_root,
                [
                    "config/historical-entity-identities.yml",
                    "config/model-policy.yml",
                    "config/shared-neutral-extraction-output.schema.json",
                ],
            ),
        }
    )
    notify_stage("neutral_materials", "running")
    restored_neutral_stage = _restore_stage_artifacts(
        stage_cache_root=stage_cache_root,
        stage="neutral_materials",
        input_fingerprint=neutral_stage_input_fingerprint,
        producer_contract_fingerprint=neutral_stage_contract_fingerprint,
        targets={"neutral_materials": neutral_path},
    )
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
    # A shared token is extracted from one stable subject closure. Team members
    # belong to later ruler/profile projections and must not change the shared
    # chronicle plan or force another model extraction.
    backbone_source_pack = {
        "ruler": source_pack["ruler"],
        "ruler_ref": source_pack["ruler_ref"],
        "members": [],
    }
    backbone_plan = build_ruler_neutral_plan(
        source_pack=backbone_source_pack,
        source_index=source_index,
        inventory=inventory,
        identity_resolver=identity_resolver,
        allowed_works=backbone_works or configured_scan_works,
        allowed_page_ranges=backbone_page_ranges,
        shared_subjects=shared_subject_refs,
    )
    shared_backbone_extraction_contract = str(
        (shared_contract or {}).get("extraction_contract") or ""
    )
    shared_backbone_identity = _shared_backbone_identity(
        backbone_plan,
        extraction_contract=shared_backbone_extraction_contract,
    )
    expected_backbone_routing = build_deterministic_fact_resolution_plan(
        backbone_plan
    )["deterministic_routing"]
    shared_backbone_path = None
    if shared_backbone_root is not None and shared_backbone_token:
        resolved_shared_root = shared_backbone_root.resolve()
        shared_backbone_path = (
            resolved_shared_root / shared_backbone_token / "current.json"
        ).resolve()
        if resolved_shared_root not in shared_backbone_path.parents:
            raise ValueError("共享主干材料路径越界")
    shared_backbone_current: Mapping[str, Any] | None = None
    shared_backbone_seed: Mapping[str, Any] | None = None
    shared_backbone_previous_identity: str | None = None
    if shared_backbone_path is not None and shared_backbone_path.is_file():
        candidate = json.loads(shared_backbone_path.read_text(encoding="utf-8"))
        if (
            candidate.get("schema_version") == "shared-chronicle-current-v1"
            and candidate.get("status") == "quality_contract_valid_shadow"
            and candidate.get("material_token") == shared_backbone_token
            and candidate.get("source_index_identity") == source_index.identity
            and candidate.get("extraction_contract")
            == shared_backbone_extraction_contract
        ):
            shared_backbone_seed = candidate.get("materials")
            candidate_subject_coverage = _shared_subject_coverage(
                plan=backbone_plan,
                materials=candidate.get("materials") or {},
                owner_refs=shared_owner_refs,
                deterministic_empty_segment_refs=expected_backbone_routing[
                    "deterministic_empty_segment_refs"
                ],
            )
            if _shared_current_has_complete_subject_coverage(
                candidate=candidate,
                expected_backbone_identity=shared_backbone_identity,
                recomputed_coverage=candidate_subject_coverage,
            ):
                shared_backbone_current = candidate.get("materials")
            # Exact batch/segment fingerprints inside the material remain safe
            # seeds when a shared range expands. The extractor will call the
            # model only for genuinely missing or contract-changed atoms, then
            # replace the current with the new complete identity.
            shared_backbone_previous_identity = str(
                candidate.get("backbone_identity") or ""
            )
    combined_backbone_current = _merge_neutral_currents(
        [shared_backbone_seed, current_neutral]
    )
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
    backbone_subject_ref_by_name = shared_owner_refs or {
        str(source_pack["ruler"]): str(source_pack["ruler_ref"])
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
            subject_ref_by_name=backbone_subject_ref_by_name,
            identity_resolver=identity_resolver,
            supplemental_facts_by_segment=deterministic_campaign_facts_by_segment,
        ),
        initial_batch_size=12,
        maximum_recoveries=2,
    )
    backbone_model_call_count = int(backbone_materials.pop("model_call_count"))
    backbone_materials["deterministic_routing"] = routed_backbone_plan[
        "deterministic_routing"
    ]
    backbone_materials["chronicle_role_projections"] = (
        build_chronicle_role_projections(
            plan=routed_backbone_plan,
            neutral_materials=backbone_materials,
        )
    )
    shared_subject_coverage = (
        _shared_subject_coverage(
            plan=backbone_plan,
            materials=backbone_materials,
            owner_refs=backbone_subject_ref_by_name,
            deterministic_empty_segment_refs=routed_backbone_plan[
                "deterministic_routing"
            ]["deterministic_empty_segment_refs"],
        )
        if shared_backbone_token
        else None
    )
    if shared_subject_coverage is not None and not shared_subject_coverage[
        "coverage_complete"
    ]:
        incomplete = [
            str(row["canonical_name"])
            for row in shared_subject_coverage["subjects"]
            if not row["coverage_complete"]
        ]
        raise ValueError(
            "共享编年主体中性抽取覆盖不完整: " + ",".join(incomplete)
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
                    "extraction_contract": shared_backbone_extraction_contract,
                    "subject_coverage": shared_subject_coverage,
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
    current_event_signatures = _project_event_signatures_for_ruler(
        plan=routed_backbone_plan,
        signatures=accepted_event_signatures,
        ruler_ref=str(source_pack["ruler_ref"]),
    )
    if backbone_works and (backsource_works or directed_supplement_works):
        neutral_plan = build_event_directed_neutral_plan(
            backbone_plan=routed_backbone_plan,
            event_signatures=current_event_signatures,
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
        directed_current = _merge_neutral_currents(
            [current_neutral, backbone_materials]
        )
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
            maximum_recoveries=2,
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
    neutral_materials["ruler_neutral_projection"] = {
        "ruler_ref": str(source_pack["ruler_ref"]),
        "backbone_fact_refs": _ruler_backbone_fact_refs(
            plan=routed_backbone_plan,
            neutral_materials=neutral_materials,
            ruler_ref=str(source_pack["ruler_ref"]),
        ),
    }
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
    neutral_stage = _accept_stage(
        runtime_root=runtime_root,
        stage_cache_root=stage_cache_root,
        stage="neutral_materials",
        input_fingerprint=neutral_stage_input_fingerprint,
        producer_contract_fingerprint=neutral_stage_contract_fingerprint,
        quality_checks={
            "neutral_fact_count": int(neutral_materials["fanout"]["fact_count"]),
            "shared_subject_coverage": shared_subject_coverage,
            "backbone_model_call_count": backbone_model_call_count,
            "backsource_model_call_count": backsource_model_call_count,
            "database_write_count": 0,
            "formal_score_write_count": 0,
        },
        artifacts={"neutral_materials": neutral_path},
    )
    notify_stage(
        "neutral_materials",
        "reused"
        if restored_neutral_stage is not None and neutral_model_call_count == 0
        else "quality_accepted",
        neutral_stage,
    )
    deadline.check("outcome_projection")
    source_pack_path = workspace_root / str(configured["source_pack"])
    outcome_route = resolve_agent_route(
        model_policy,
        stage_code="episode_candidate_normalization",
        escalation_reasons=(),
    )
    outcome_schema_path = workspace_root / "config/current-outcome-candidate-output.schema.json"
    outcome_transport_schema_path = checkpoint_dir / "current-outcome-transport.schema.json"
    _atomic_text(
        outcome_transport_schema_path,
        json.dumps(
            build_outcome_transport_schema(outcome_schema_path),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    outcome_stage_input_fingerprint = _digest(
        {
            "neutral_materials": {
                key: value
                for key, value in neutral_materials.items()
                if key != "outcome_projection"
            },
            "source_pack_sha256": source_pack["source_pack_sha256"],
            "source_index_identity": source_index.identity,
        }
    )
    outcome_stage_contract_fingerprint = _digest(
        {
            "contract": STAGE_CONTRACTS["outcome_projection"],
            "projection_policy": PROJECTION_POLICY_VERSION,
            "files": _contract_files_fingerprint(
                workspace_root,
                [
                    "config/current-outcome-candidate-output.schema.json",
                    "config/model-policy.yml",
                ],
            ),
        }
    )
    notify_stage("outcome_projection", "running")
    restored_outcome_stage = _restore_stage_artifacts(
        stage_cache_root=stage_cache_root,
        stage="outcome_projection",
        input_fingerprint=outcome_stage_input_fingerprint,
        producer_contract_fingerprint=outcome_stage_contract_fingerprint,
        targets={
            "neutral_materials": neutral_path,
            "source_pack": source_pack_path,
        },
    )

    def outcome_runner_factory() -> StructuredCodexRunner:
        return StructuredCodexRunner(
            codex_bin="codex",
            model=str(outcome_route["model"]),
            reasoning_effort=str(outcome_route["reasoning_effort"]),
            output_schema_path=outcome_transport_schema_path,
            timeout_seconds=limits.model_timeout_seconds,
            cwd=workspace_root,
            deadline_monotonic=deadline.deadline,
        )

    if restored_outcome_stage is not None:
        neutral_materials = json.loads(neutral_path.read_text(encoding="utf-8"))
        restored_quality = restored_outcome_stage.get("quality_checks") or {}
        restored_projection = neutral_materials.get("outcome_projection") or {}
        outcome_projection = {
            "policy_fingerprint": restored_projection.get("policy_fingerprint"),
            "dispositions": list(restored_projection.get("dispositions") or ()),
            "candidate_count": int(
                restored_quality.get("outcome_candidate_count") or 0
            ),
            "model_call_count": 0,
            "source_pack_changed": False,
        }
        outcome_recovery_count = 0
        outcome_final_facts_per_call = int(
            restored_quality.get("final_facts_per_call") or 16
        )
    else:
        (
            outcome_projection,
            outcome_recovery_count,
            outcome_final_facts_per_call,
        ) = _run_with_model_anomaly_recovery(
            runner_factory=outcome_runner_factory,
            operation=lambda runner, facts_per_call: project_current_outcomes(
                source_pack_path=source_pack_path,
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
            maximum_recoveries=2,
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
    outcome_stage = _accept_stage(
        runtime_root=runtime_root,
        stage_cache_root=stage_cache_root,
        stage="outcome_projection",
        input_fingerprint=outcome_stage_input_fingerprint,
        producer_contract_fingerprint=outcome_stage_contract_fingerprint,
        quality_checks={
            "outcome_candidate_count": int(outcome_projection["candidate_count"]),
            "disposition_count": len(outcome_projection["dispositions"]),
            "model_call_count": int(outcome_projection["model_call_count"]),
            "recovery_count": outcome_recovery_count,
            "final_facts_per_call": outcome_final_facts_per_call,
            "database_write_count": 0,
            "formal_score_write_count": 0,
        },
        artifacts={
            "neutral_materials": neutral_path,
            "source_pack": source_pack_path,
        },
    )
    notify_stage(
        "outcome_projection",
        "reused" if restored_outcome_stage is not None else "quality_accepted",
        outcome_stage,
    )
    if stop_after_stage == "outcome_projection":
        projected_source_pack = json.loads(
            source_pack_path.read_text(encoding="utf-8")
        )
        projected_outcomes = (
            (projected_source_pack.get("outcome_registry") or {}).get("clusters")
            or ()
        )
        return {
            "schema_version": "emperor-rebuild-review-v1",
            "status": "awaiting_review",
            "ruler": ruler,
            "review_stage": "outcome_projection",
            "source_pack": str(source_pack_path),
            "neutral_materials": str(neutral_path),
            "outcome_count": len(projected_outcomes),
            "stage_results": stage_results,
            "database_write_count": 0,
            "formal_score_write_count": 0,
        }
    deadline.check("current_projection")
    current_stage_input_fingerprint = _digest(
        {
            "source_pack_sha256": _file_digest(source_pack_path),
            "neutral_materials_sha256": _file_digest(neutral_path),
        }
    )
    current_stage_contract_fingerprint = _digest(
        {
            "contract": STAGE_CONTRACTS["current_projection"],
            "files": _contract_files_fingerprint(
                workspace_root,
                [
                    "config/i5b-scoring-policy.yml",
                    "config/project.yml",
                    "config/talent-grade-v11-domain-equivalent-historic.yml",
                ],
            ),
        }
    )
    notify_stage("current_projection", "running")
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
    current_stage = _accept_stage(
        runtime_root=runtime_root,
        stage_cache_root=None,
        stage="current_projection",
        input_fingerprint=current_stage_input_fingerprint,
        producer_contract_fingerprint=current_stage_contract_fingerprint,
        quality_checks={
            "ruler": ruler,
            "registry_fingerprint": outcome_layers["registry"][
                "registry_fingerprint"
            ],
            "sampled_person_exports": samples,
            "net_signal": report["net_signal"],
            "database_write_count": 0,
            "formal_score_write_count": 0,
        },
        artifacts={"result": result_path},
    )
    notify_stage("current_projection", "quality_accepted", current_stage)
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
        "shared_backbone_material_token": shared_backbone_token or None,
        "shared_backbone_identity": shared_backbone_identity,
        "shared_backbone_previous_identity": shared_backbone_previous_identity,
        "shared_backbone_zero_model_reuse": (
            shared_backbone_current is not None
            and backbone_model_call_count == 0
        ),
        "shared_backbone_event_signature_count": len(
            accepted_event_signatures
        ),
        "shared_backbone_subject_coverage": shared_subject_coverage,
        "ruler_event_signature_count": len(current_event_signatures),
        "ruler_backbone_fact_count": len(
            (
                neutral_materials.get("ruler_neutral_projection") or {}
            ).get("backbone_fact_refs")
            or ()
        ),
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
        "stage_results": stage_results,
    }
