from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping


def _hash(value: object) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def build_candidate_refreeze(
    *, inventory: Mapping[str, Any], decisions: Mapping[str, Any]
) -> dict[str, Any]:
    if decisions.get("schema_version") != "i5b-candidate-refreeze-decisions-v1":
        raise ValueError("candidate refreeze decision schema mismatch")
    rows = deepcopy(list(inventory.get("candidate_inventory") or ()))
    pending = {
        str(row["event_group_key"])
        for row in rows
        if row.get("final_disposition") == "advance_to_source_rebind"
    }
    decision_rows = decisions.get("decisions") or ()
    by_key = {str(row.get("event_group_key")): row for row in decision_rows}
    if len(by_key) != len(decision_rows) or set(by_key) != pending:
        raise ValueError("candidate refreeze decisions do not close pending inventory")
    for row in rows:
        key = str(row.get("event_group_key"))
        if key not in by_key:
            continue
        decision = by_key[key]
        row["final_disposition"] = str(decision["final_disposition"])
        row["final_rationale"] = str(decision["judge_rationale"])
        row["source_rebind_v2"] = {
            "decision_ref": str(decisions["decision_ref"]),
            "source_passage_refs": list(decision.get("source_passage_refs") or ()),
            "formal_unit_ref": decision.get("formal_unit_ref"),
        }
    for row in decisions.get("new_recalled_candidates") or ():
        if str(row.get("event_group_key")) in {str(item.get("event_group_key")) for item in rows}:
            raise ValueError("new recalled candidate duplicates inventory")
        rows.append(deepcopy(dict(row)))
    unresolved = sum(row.get("final_disposition") == "advance_to_source_rebind" for row in rows)
    payload = deepcopy(dict(inventory))
    payload["schema_version"] = "i5b-appointment-delegation-candidate-inventory-v2"
    payload["status"] = "human_refrozen_after_source_recovery_and_judge"
    payload["candidate_inventory"] = rows
    payload["historical_coverage_complete"] = unresolved == 0
    payload["refreeze"] = {
        "decision_ref": decisions["decision_ref"],
        "prior_pending_source_rebind_count": len(pending),
        "judged_candidate_count": len(pending),
        "new_recalled_candidate_count": len(decisions.get("new_recalled_candidates") or ()),
        "unresolved_candidate_count": unresolved,
        "source_cache_output_fingerprints": list(decisions.get("source_cache_output_fingerprints") or ()),
        "human_freeze_accepted": True,
        "model_call_count": 0,
        "business_write_count": 0,
    }
    payload.pop("report_sha256", None)
    payload["report_sha256"] = _hash(payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply explicit human candidate refreeze decisions")
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build_candidate_refreeze(inventory=load(args.inventory), decisions=load(args.decisions))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
