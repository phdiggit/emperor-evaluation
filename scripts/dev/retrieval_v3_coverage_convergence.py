from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any, Mapping, Sequence


def text(value: Any) -> str:
    return str(value or "").strip()


def as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def list_texts(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [text(item) for item in value if text(item)]


def stable_key(prefix: str, *parts: Any) -> str:
    payload = "\x1f".join(text(part) for part in parts)
    return f"{prefix}-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:20].upper()}"


def identity_key(row: Mapping[str, Any]) -> str:
    return f"id:{as_int(row.get('object_id'))}" if as_int(row.get("object_id")) else f"name:{text(row.get('object_name'))}"


def build_gap_routes(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []
    terminal_actions = {"identity_review", "expected_event_inventory_review"}
    for row in report.get("objects") or []:
        base = {
            "emperor_name": text(row.get("emperor_name")),
            "object_id": row.get("object_id"),
            "object_name": text(row.get("object_name")),
            "write_job": False,
            "write_db": False,
        }
        for item in row.get("gaps") or []:
            action = text(item.get("next_action")) or "manual_review"
            terminal = action in terminal_actions
            routes.append(base | {
                "idempotency_key": stable_key("CGR", report.get("item_code"), report.get("rule_code"),
                                              row.get("emperor_name"), identity_key(row), item.get("gap_type"), action),
                "gap_type": text(item.get("gap_type")),
                "current_decision": text(item.get("gap_type")),
                "terminal": terminal,
                "retryable": not terminal,
                "next_action": action,
            })
        for event in row.get("expected_event_assessments") or []:
            decision = text(event.get("reconciliation_decision"))
            action = text(event.get("repair_next_action"))
            if not decision or action == "none":
                continue
            routes.append(base | {
                "idempotency_key": stable_key("CGR", report.get("item_code"), report.get("rule_code"),
                                              event.get("event_inventory_code"), action),
                "event_inventory_code": text(event.get("event_inventory_code")),
                "gap_type": "historical_event_reconciliation",
                "source_attempt_count": as_int(event.get("reconciliation_attempt_count")),
                "current_decision": decision,
                "terminal": bool(event.get("repair_terminal")),
                "retryable": bool(event.get("repair_retryable")),
                "next_action": action,
            })
    return sorted(routes, key=lambda row: (text(row.get("emperor_name")), text(row.get("object_name")),
                                           text(row.get("idempotency_key"))))


def build_repair_ledger(
    report: Mapping[str, Any], previous_rows: Sequence[Mapping[str, Any]] = ()
) -> list[dict[str, Any]]:
    previous = {text(row.get("idempotency_key")): row for row in previous_rows if text(row.get("idempotency_key"))}
    ledger: list[dict[str, Any]] = []
    for route in build_gap_routes(report):
        row = dict(route)
        old = previous.get(text(row.get("idempotency_key")))
        old_decision = text(old.get("current_decision")) if old else ""
        old_action = text(old.get("next_action")) if old else ""
        unchanged = bool(old) and old_decision == text(row.get("current_decision")) and old_action == text(row.get("next_action"))
        row["attempt_count"] = as_int(old.get("attempt_count")) + 1 if old else 1
        row["previous_decision"] = old_decision
        row["decision_changed"] = bool(old) and not unchanged
        row["progress_observed"] = bool(old) and not unchanged
        row["convergence_state"] = (
            "terminal_review" if row.get("terminal") else
            "blocked" if not row.get("retryable") else
            "no_progress" if unchanged else
            "repair_in_progress" if old else
            "repairable"
        )
        ledger.append(row)
    return ledger


def build_consumer_handoffs(ledger: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    stage_aliases = {
        "claim_extraction_coverage_review": "claim_extraction",
        "promote_claim_cache_to_material": "material_promotion",
        "route_material_candidates": "candidate_routing",
        "candidate_review_and_binding": "candidate_binding",
        "rebuild_event_groups": "event_group_rebuild",
    }
    rows: list[dict[str, Any]] = []
    for raw in ledger:
        row = dict(raw)
        state = text(row.get("convergence_state"))
        if row.get("terminal"):
            dispatch_state = "terminal_manual_review"
        elif state == "no_progress":
            dispatch_state = "held_no_progress"
        elif row.get("retryable"):
            dispatch_state = "ready_report_only"
        else:
            dispatch_state = "blocked"
        action = text(row.get("next_action"))
        row.update({
            "consumer_stage": stage_aliases.get(action, action),
            "dispatch_state": dispatch_state,
            "dispatch_allowed": dispatch_state == "ready_report_only",
            "write_job": False,
            "write_db": False,
        })
        rows.append(row)
    counts = Counter(text(row.get("dispatch_state")) for row in rows)
    stage_counts = Counter(text(row.get("consumer_stage")) for row in rows)
    return {
        "ok": True,
        "mode": "report_only_consumer_handoff",
        "write_job": False,
        "write_db": False,
        "counts": dict(sorted(counts.items())),
        "stage_counts": dict(sorted(stage_counts.items())),
        "handoffs": rows,
    }


def build_convergence_delta(
    current_rows: Sequence[Mapping[str, Any]], previous_rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    current = {text(row.get("idempotency_key")): row for row in current_rows}
    previous = {text(row.get("idempotency_key")): row for row in previous_rows}
    changes: list[dict[str, Any]] = []
    for key in sorted(set(current) | set(previous)):
        now, old = current.get(key), previous.get(key)
        if now is None:
            kind = "resolved_gap"
        elif old is None:
            kind = "new_gap"
        elif bool(now.get("terminal")) and not bool(old.get("terminal")):
            kind = "regressed_to_terminal"
        elif text(now.get("current_decision")) != text(old.get("current_decision")) or text(now.get("next_action")) != text(old.get("next_action")):
            kind = "decision_changed"
        elif text(now.get("convergence_state")) == "no_progress":
            kind = "stalled"
        else:
            kind = "unchanged"
        source = now or old or {}
        changes.append({
            "idempotency_key": key,
            "change_type": kind,
            "emperor_name": text(source.get("emperor_name")),
            "object_id": source.get("object_id"),
            "object_name": text(source.get("object_name")),
            "previous_decision": text(old.get("current_decision")) if old else "",
            "current_decision": text(now.get("current_decision")) if now else "",
            "previous_action": text(old.get("next_action")) if old else "",
            "current_action": text(now.get("next_action")) if now else "",
        })
    counts = Counter(text(row.get("change_type")) for row in changes)
    return {
        "ok": True,
        "mode": "read_only_convergence_delta",
        "write_job": False,
        "write_db": False,
        "counts": dict(sorted(counts.items())),
        "changes": changes,
    }


def apply_convergence(report: dict[str, Any], ledger: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    routes_by_object: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for route in ledger:
        key = (text(route.get("emperor_name")), identity_key(route))
        routes_by_object.setdefault(key, []).append(route)
    mechanical_counts: Counter[str] = Counter()
    convergence_counts: Counter[str] = Counter()
    for row in report.get("objects") or []:
        mechanical = text(row.get("mechanical_coverage_status")) or text(row.get("coverage_status"))
        mechanical_counts[mechanical] += 1
        events = row.get("expected_event_assessments") or []
        routes = routes_by_object.get((text(row.get("emperor_name")), identity_key(row)), [])
        historical = text(row.get("historical_event_coverage_status"))
        if any(text(route.get("convergence_state")) == "terminal_review" for route in routes):
            state = "terminal_review"
        elif historical == "unassessed":
            state = "unassessed"
        elif historical == "assessed_no_relevant_events":
            state = "verified"
        elif events and all(text(event.get("coverage_status")) == "covered" for event in events):
            state = "verified"
        elif any(text(route.get("convergence_state")) == "no_progress" for route in routes):
            state = "no_progress"
        elif routes:
            state = "repair_in_progress" if any(as_int(route.get("attempt_count")) > 1 for route in routes) else "repairable"
        else:
            state = "blocked"
        row["convergence_state"] = state
        convergence_counts[state] += 1
    report["mechanical_coverage_counts"] = dict(sorted(mechanical_counts.items()))
    report["convergence_counts"] = dict(sorted(convergence_counts.items()))
    report["repair_ledger_count"] = len(ledger)
    report["repair_ledger_write_job"] = False
    report["repair_ledger_write_db"] = False
    return report
