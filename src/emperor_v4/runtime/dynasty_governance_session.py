from __future__ import annotations

import json
import os
from pathlib import Path
from hashlib import sha256
from typing import Any, Mapping, Sequence
from uuid import uuid4

from emperor_v4.adapters.historical_entity_identity import HistoricalEntityResolver
from emperor_v4.adapters.source_text_index import LocalSourceTextIndex
from emperor_v4.evaluation.historical_outcome_registry import (
    write_dynasty_outcome_partition,
)
from emperor_v4.persistence.canonical_refs import canonical_hashed_ref
from emperor_v4.runtime.dynasty_governance_rebuild import (
    DynastyGovernanceLimits,
    load_dynasty_governance_catalog_entry,
    rebuild_dynasty_governance,
)
from emperor_v4.runtime.emperor_neutral_scan import merge_dynasty_governance_current
from emperor_v4.runtime.emperor_outcome_projection import project_current_outcomes


SCHEMA_VERSION = "dynasty-governance-session-v1"
OUTCOME_PACK_SCHEMA_VERSION = "dynasty-governance-outcome-pack-v1"


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def _discover_source_index(
    source_index_root: Path, *, works: Sequence[str]
) -> LocalSourceTextIndex:
    candidates: list[tuple[int, str, LocalSourceTextIndex]] = []
    for path in sorted(source_index_root.rglob("*.sqlite3")):
        try:
            index = LocalSourceTextIndex(path)
            counts = [sum(1 for _ in index.iter_pages(works=(work,))) for work in works]
        except (OSError, ValueError):
            continue
        if all(count > 0 for count in counts):
            candidates.append((sum(counts), str(path.resolve()), index))
    if not candidates:
        raise ValueError("没有覆盖朝代政书目录的固定史源索引")
    return max(candidates, key=lambda row: (row[0], row[1]))[2]


def _empty_outcome_pack(*, dynasty: str, dynasty_token: str) -> dict[str, Any]:
    ruler = f"{dynasty}治理底账"
    pack = {
        "schema_version": OUTCOME_PACK_SCHEMA_VERSION,
        "pack_scope": "dynasty_governance",
        "dynasty": dynasty,
        "dynasty_token": dynasty_token,
        "ruler": ruler,
        "ruler_ref": canonical_hashed_ref("DYNASTY", dynasty_token, length=12),
        "window": "全朝",
        "members": [],
        "facts": [],
        "outcome_registry": {
            "schema_version": "historical-outcome-cluster-registry-v1",
            "status": "shadow",
            "clusters": [],
        },
        "three_channel_disposition": {},
        "profile_projection_gate": {
            "status": "not_applicable_for_dynasty_baseline",
            "material_coverage_complete": False,
            "freeze_allowed": False,
        },
    }
    pack["source_pack_sha256"] = sha256(
        json.dumps(
            pack,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return pack


def run_dynasty_governance_session(
    *,
    workspace_root: Path,
    source_index_root: Path,
    runtime_root: Path,
    dynasty: str,
    outcome_review_path: Path | None = None,
    codex_bin: str = "codex",
    model_workers: int = 4,
    model_timeout_seconds: int = 120,
    target_chars: int = 2_400,
) -> dict[str, Any]:
    """Build one dynasty governance baseline without claiming a ruler."""

    workspace_root = workspace_root.resolve()
    runtime_root = runtime_root.resolve()
    canonical_dynasty, configured = load_dynasty_governance_catalog_entry(
        workspace_root, dynasty
    )
    token = str(configured["dynasty_token"])
    works = tuple(
        str(row.get("work") or "").strip()
        for row in configured.get("source_works") or ()
        if isinstance(row, Mapping) and str(row.get("work") or "").strip()
    )
    source_index = _discover_source_index(source_index_root.resolve(), works=works)
    rebuild = rebuild_dynasty_governance(
        dynasty=canonical_dynasty,
        source_index_path=source_index.path,
        runtime_root=runtime_root,
        workspace_root=workspace_root,
        limits=DynastyGovernanceLimits(
            model_workers=model_workers,
            model_timeout_seconds=model_timeout_seconds,
            target_chars=target_chars,
        ),
        codex_bin=codex_bin,
    )
    current_path = runtime_root / token / "current.json"
    current = json.loads(current_path.read_text(encoding="utf-8"))
    resolver = HistoricalEntityResolver.load(
        workspace_root / "config/historical-entity-identities.yml"
    )
    neutral_materials = merge_dynasty_governance_current(
        neutral_materials={
            "fanout": {
                "facts": [],
                "person_fanout": [],
                "event_groups": [],
            }
        },
        current=current,
        expected_dynasty_token=token,
        expected_source_index_identity=source_index.identity,
        period_terms=(),
        identity_resolver=resolver,
        subject_ref_by_name={},
        ruler_ref="",
        event_signatures=(),
        include_all_dynasty_chains=True,
    )
    pack_path = runtime_root / token / "outcome-pack.json"
    if not pack_path.is_file():
        _atomic_json(
            pack_path,
            _empty_outcome_pack(
                dynasty=canonical_dynasty,
                dynasty_token=token,
            ),
        )
    reviewed_payload = None
    if outcome_review_path is not None:
        reviewed_payload = json.loads(
            outcome_review_path.resolve().read_text(encoding="utf-8")
        )
    projection = project_current_outcomes(
        source_pack_path=pack_path,
        neutral_materials=neutral_materials,
        source_index=source_index,
        schema_path=workspace_root
        / "config/current-outcome-candidate-output.schema.json",
        runner=None,
        checkpoint_dir=runtime_root / token / ".review-checkpoint",
        workspace_root=workspace_root,
        max_workers=1,
        reviewed_payload=reviewed_payload,
        included_source_roles=("dynasty_governance",),
    )
    if projection.get("status") == "awaiting_main_session_review":
        worklist_path = runtime_root / token / "review" / "outcome-worklist.json"
        _atomic_json(worklist_path, projection["review_worklist"])
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "awaiting_review",
            "dynasty": canonical_dynasty,
            "dynasty_token": token,
            "source_index": str(source_index.path),
            "source_index_identity": source_index.identity,
            "governance_current": str(current_path),
            "outcome_worklist": str(worklist_path),
            "model_call_count": int(rebuild.get("model_call_count") or 0),
            "database_write_count": 0,
            "formal_score_write_count": 0,
        }
    outcome_pack = json.loads(pack_path.read_text(encoding="utf-8"))
    partition = write_dynasty_outcome_partition(
        outcome_pack=outcome_pack,
        dynasty_token=token,
        output_root=runtime_root / "historical_outcome_registry",
    )
    handoff = {
        "schema_version": "dynasty-governance-handoff-v1",
        "status": "quality_accepted_shadow",
        "dynasty": canonical_dynasty,
        "dynasty_token": token,
        "governance_current": str(current_path),
        "governance_input_fingerprint": str(current["input_fingerprint"]),
        "source_index_identity": source_index.identity,
        "outcome_pack": str(pack_path),
        "outcome_pack_sha256": str(outcome_pack["source_pack_sha256"]),
        "outcome_registry_current": partition["current_json"],
        "outcome_registry_fingerprint": partition["registry"][
            "registry_fingerprint"
        ],
        "outcome_count": int(
            partition["registry"]["declarations"]["outcome_count"]
        ),
        "formal_write_count": 0,
    }
    handoff_path = runtime_root / token / "handoff.json"
    _atomic_json(handoff_path, handoff)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "quality_accepted",
        "dynasty": canonical_dynasty,
        "dynasty_token": token,
        "handoff": str(handoff_path),
        "outcome_registry_current": partition["current_json"],
        "outcome_registry_markdown": partition["current_markdown"],
        "outcome_count": handoff["outcome_count"],
        "model_call_count": int(rebuild.get("model_call_count") or 0),
        "database_write_count": 0,
        "formal_score_write_count": 0,
    }
