from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from emperor_v4.evaluation.battle_registry_store import load_battle_registry


BATTLE_REGISTRY_PATH = Path("docs/公共成果/军事/01-战役登记.json")
SUPPORTED_PARTITIONS = ("south_song", "yuan", "ming")


def build_post_tang_third_item_readiness(
    workspace_root: Path,
    *,
    partitions: Iterable[str] = SUPPORTED_PARTITIONS,
) -> dict[str, Any]:
    """Audit whether public battle records are ready for Third Item scoring.

    This consumer deliberately has no chronicle-card path.  It can only see
    records that have already passed through the public battle registry.
    """
    requested = tuple(dict.fromkeys(str(value) for value in partitions))
    payload = load_battle_registry(
        workspace_root / BATTLE_REGISTRY_PATH,
        partitions=requested,
    )
    records = list(payload.get("records") or ())
    summaries: list[dict[str, Any]] = []
    for partition in requested:
        rows = [
            row for row in records if str(row.get("dynasty_partition")) == partition
        ]
        public_rows = [row for row in rows if row.get("public_outcome_registered")]
        phase_containers = [
            row for row in rows if row.get("third_item_phase_container")
        ]
        subject_phases = [
            phase
            for row in phase_containers
            for phase in row.get("subject_phase_views") or ()
        ]
        binding_status_counts = Counter(
            str((phase.get("ruler_binding") or {}).get("status") or "UNKNOWN")
            for phase in subject_phases
        )
        bound_phases = [
            phase
            for phase in subject_phases
            if (phase.get("ruler_binding") or {}).get("status")
            == "BOUND_EXCLUSIVE_GOVERNING_WINDOW"
        ]
        member_rows = [row for row in public_rows if row.get("members")]
        ruler_bound_rows = [
            row
            for row in public_rows
            if row.get("subject_phase_views")
            or str(row.get("ruler_role_status") or "") != "unresolved"
        ]
        ab_axis_rows = [
            row
            for row in public_rows
            if row.get("security_grade") is not None
            or row.get("wc_grade") is not None
        ]
        d_axis_rows = [
            row
            for row in public_rows
            if row.get("parent_cost_axes") or row.get("parent_benefit_axes")
        ]
        summaries.append(
            {
                "partition": partition,
                "registered_record_count": len(rows),
                "public_outcome_count": len(public_rows),
                "resolved_member_outcome_count": len(member_rows),
                "person_result_count": sum(
                    len(row.get("members") or ()) for row in public_rows
                ),
                "canonical_phase_container_count": len(phase_containers),
                "canonical_subject_phase_count": len(subject_phases),
                "canonical_bound_phase_count": len(bound_phases),
                "canonical_binding_status_counts": dict(
                    sorted(binding_status_counts.items())
                ),
                "canonical_bound_ab_axis_count": sum(
                    "strategic_security" in phase and bool(phase.get("border_control"))
                    for phase in bound_phases
                ),
                "canonical_bound_d_raw_axis_count": sum(
                    bool(phase.get("cost_axes")) for phase in bound_phases
                ),
                "ruler_window_bound_record_count": len(ruler_bound_rows),
                "third_ab_axis_ready_record_count": len(ab_axis_rows),
                "third_d_axis_ready_record_count": len(d_axis_rows),
                "command_status_counts": dict(
                    sorted(
                        Counter(
                            str(row.get("command_status") or "UNKNOWN")
                            for row in rows
                        ).items()
                    )
                ),
                "public_registration_ready": bool(rows and public_rows),
                "canonical_phase_registration_ready": bool(phase_containers),
                "ruler_window_binding_ready": bool(bound_phases)
                and not binding_status_counts.get("UNRESOLVED_WINDOW_OVERLAP")
                and not binding_status_counts.get("UNRESOLVED_YEAR"),
                "third_ab_axes_ready": bool(public_rows)
                and len(ab_axis_rows) == len(public_rows),
                "third_d_axes_ready": bool(public_rows)
                and len(d_axis_rows) == len(public_rows),
            }
        )

    score_ready = all(
        summary["canonical_phase_registration_ready"]
        and summary["ruler_window_binding_ready"]
        and summary["third_ab_axes_ready"]
        and summary["third_d_axes_ready"]
        for summary in summaries
    )
    return {
        "schema_version": "post-tang-third-item-readiness-v1",
        "source_registry": str(BATTLE_REGISTRY_PATH).replace("\\", "/"),
        "source_loader": (
            "emperor_v4.evaluation.battle_registry_store.load_battle_registry"
        ),
        "direct_chronicle_card_consumption_allowed": False,
        "partitions": summaries,
        "registered_record_count": sum(
            summary["registered_record_count"] for summary in summaries
        ),
        "public_outcome_count": sum(
            summary["public_outcome_count"] for summary in summaries
        ),
        "person_result_count": sum(
            summary["person_result_count"] for summary in summaries
        ),
        "canonical_phase_container_count": sum(
            summary["canonical_phase_container_count"] for summary in summaries
        ),
        "canonical_subject_phase_count": sum(
            summary["canonical_subject_phase_count"] for summary in summaries
        ),
        "canonical_bound_phase_count": sum(
            summary["canonical_bound_phase_count"] for summary in summaries
        ),
        "score_ready": score_ready,
        "readiness_status": (
            "PUBLIC_REGISTERED_AND_SCORE_READY"
            if score_ready
            else "PUBLIC_REGISTERED_NOT_SCORE_READY"
        ),
        "next_required_contracts": []
        if score_ready
        else [
            "resolve_year_only_accession_boundary_and_yearless_phase_bindings",
            "consume_bound_phase_security_and_control_axes_into_third_item_ab",
            "aggregate_bound_phases_into_third_item_d_ruler_window_parent_cycles",
        ],
    }
