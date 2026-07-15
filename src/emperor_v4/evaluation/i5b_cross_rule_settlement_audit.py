from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "i5b-cross-rule-settlement-audit-v1"


def _hash(value: object) -> str:
    return sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _normalized_consumptions(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    rule_code = str(payload.get("rule_code") or "").strip()
    if not rule_code:
        raise ValueError("cross-rule settlement input requires rule_code")

    if "units" in payload:
        source_rows = [
            (row, str(row.get("status") or ""))
            for row in payload.get("units") or ()
        ]
    else:
        source_rows = [
            (row, "numerically_projected")
            for row in payload.get("materials") or ()
        ] + [
            (row, "insufficient_projection")
            for row in payload.get("insufficient_projections") or ()
        ]

    consumptions: list[dict[str, str]] = []
    for row, disposition in source_rows:
        event_group = str(row.get("canonical_event_group") or "").strip()
        side = str(row.get("side") or "").strip()
        object_ref = str(row.get("object_ref") or "").strip()
        unit_ref = str(row.get("unit_ref") or "").strip()
        if not all((event_group, side, unit_ref)):
            raise ValueError("cross-rule settlement material identity is incomplete")
        if not object_ref and disposition == "insufficient_projection":
            object_ref = f"UNRESOLVED:{unit_ref}"
        if not object_ref:
            raise ValueError("numerically projected settlement requires object_ref")
        if disposition == "projected":
            disposition = "numerically_projected"
        if disposition not in {"numerically_projected", "insufficient_projection"}:
            raise ValueError(f"unsupported settlement disposition: {disposition}")
        primary_by_group = payload.get("primary_settlement_rules") or {}
        consumptions.append(
            {
                "canonical_event_group": event_group,
                "disposition": disposition,
                "object_ref": object_ref,
                "primary_settlement_rule": str(
                    row.get("primary_settlement_rule")
                    or primary_by_group.get(event_group)
                    or ""
                ).strip(),
                "rule_code": rule_code,
                "side": side,
                "unit_ref": unit_ref,
            }
        )
    return consumptions


def build_i5b_cross_rule_settlement_audit(
    *, projection_reports: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    consumptions = [
        row
        for payload in projection_reports
        for row in _normalized_consumptions(payload)
    ]
    consumptions.sort(
        key=lambda row: (
            row["canonical_event_group"],
            row["rule_code"],
            row["unit_ref"],
            row["disposition"],
        )
    )

    seen_rule_groups: set[tuple[str, str]] = set()
    for row in consumptions:
        key = (row["rule_code"], row["canonical_event_group"])
        if key in seen_rule_groups:
            raise ValueError(
                "duplicate canonical_event_group consumption within one rule: "
                f"{row['rule_code']}:{row['canonical_event_group']}"
            )
        seen_rule_groups.add(key)

    groups: dict[str, list[dict[str, str]]] = {}
    for row in consumptions:
        groups.setdefault(row["canonical_event_group"], []).append(row)

    conflicts: list[dict[str, Any]] = []
    reconciliation: list[dict[str, Any]] = []
    for event_group, rows in sorted(groups.items()):
        projected_rules = sorted(
            {
                row["rule_code"]
                for row in rows
                if row["disposition"] == "numerically_projected"
            }
        )
        declared_primary_rules = sorted(
            {
                row["primary_settlement_rule"]
                for row in rows
                if row["primary_settlement_rule"]
            }
        )
        conflict_code = None
        if len(declared_primary_rules) > 1:
            conflict_code = "conflicting_primary_settlement_rule_declarations"
        elif (
            declared_primary_rules
            and declared_primary_rules[0] not in projected_rules
        ):
            conflict_code = "primary_settlement_rule_is_not_projected_consumer"
        elif len(projected_rules) > 1 and len(declared_primary_rules) != 1:
            conflict_code = "cross_rule_projection_requires_unique_primary"

        row_summary = {
            "canonical_event_group": event_group,
            "consumer_count": len(rows),
            "consumer_rules": sorted({row["rule_code"] for row in rows}),
            "declared_primary_settlement_rules": declared_primary_rules,
            "numerically_projected_rules": projected_rules,
            "status": "conflict" if conflict_code else "reconciled",
        }
        reconciliation.append(row_summary)
        if conflict_code:
            conflicts.append({"code": conflict_code, **row_summary})

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": (
            "cross_rule_settlement_audit_blocked"
            if conflicts
            else "cross_rule_settlement_audit_reconciled"
        ),
        "summary": {
            "canonical_event_group_count": len(groups),
            "conflict_count": len(conflicts),
            "consumption_count": len(consumptions),
            "insufficient_projection_count": sum(
                row["disposition"] == "insufficient_projection"
                for row in consumptions
            ),
            "model_call_count": 0,
            "numerically_projected_count": sum(
                row["disposition"] == "numerically_projected"
                for row in consumptions
            ),
            "rule_count": len({row["rule_code"] for row in consumptions}),
            "database_write_count": 0,
        },
        "consumptions": consumptions,
        "reconciliation": reconciliation,
        "conflicts": conflicts,
        "declarations": {
            "formal_scoring_allowed": False,
            "score_or_ranking_write": False,
            "zero_fill_used": False,
        },
    }
    report["report_sha256"] = _hash(report)
    return report
