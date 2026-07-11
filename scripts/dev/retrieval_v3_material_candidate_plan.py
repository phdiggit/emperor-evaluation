from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v3_cross_rule_router import route_claim  # noqa: E402


RULE_CODE = "appointment_delegation"
ITEM_CODE = "I5B"


class MaterialCandidatePlanError(RuntimeError):
    pass


def text(value: Any) -> str:
    return str(value or "").strip()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise MaterialCandidatePlanError(f"invalid JSONL at {path}:{line_number}") from exc
        if not isinstance(row, Mapping):
            raise MaterialCandidatePlanError(f"expected object at {path}:{line_number}")
        rows.append(dict(row))
    return rows


def candidate_from_route(row: Mapping[str, Any], route: Any) -> dict[str, Any]:
    claim_code = text(row.get("claim_code"))
    candidate_code = f"{claim_code}::CANDIDATE::{RULE_CODE}" if claim_code else ""
    candidate_lane = f"{ITEM_CODE}.{RULE_CODE}"
    return {
        "candidate_code": candidate_code,
        "source_material_claim_code": claim_code,
        "source_pack_code": text(row.get("source_pack_code")),
        "emperor_name": text(row.get("emperor_name")),
        "object_name": text(row.get("object_name")),
        "claim_summary": text(row.get("claim_summary")),
        "candidate_item_code": ITEM_CODE,
        "candidate_rule_code": RULE_CODE,
        "candidate_lane": candidate_lane,
        "hint_status": "current_rule_candidate",
        "formal_binding_allowed": False,
        "candidate_reason": route.reason,
        "matched_signals": list(route.signals),
        "matched_terms": list(route.terms),
        "candidate_payload": {
            "created_from": "retrieval_v3_material_candidate_plan",
            "material_scope": "rule_neutral",
            "source_material_claim_code": claim_code,
            "candidate_lane": candidate_lane,
            "hint_status": "current_rule_candidate",
            "formal_binding_allowed": False,
            "object_identity_gate": "required_before_formal_binding",
            "matched_signals": list(route.signals),
            "matched_terms": list(route.terms),
            "source_binding_required": True,
        },
    }


def build_plan(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    unrouted: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        routes = [route for route in route_claim(row) if route.rule_code == RULE_CODE]
        if not routes:
            unrouted.append(
                {
                    "claim_code": text(row.get("claim_code")),
                    "emperor_name": text(row.get("emperor_name")),
                    "object_name": text(row.get("object_name")),
                    "claim_summary": text(row.get("claim_summary")),
                }
            )
            continue
        for route in routes:
            candidate = candidate_from_route(row, route)
            if not candidate["candidate_code"] or candidate["candidate_code"] in seen:
                continue
            seen.add(candidate["candidate_code"])
            candidates.append(candidate)
    return {
        "ok": True,
        "generated_by": "scripts/dev/retrieval_v3_material_candidate_plan.py",
        "item_code": ITEM_CODE,
        "rule_code": RULE_CODE,
        "material_scope": "rule_neutral",
        "write_db": False,
        "input_material_claims": len(rows),
        "candidate_count": len(candidates),
        "unrouted_count": len(unrouted),
        "candidate_rule_counts": dict(Counter(row["candidate_rule_code"] for row in candidates)),
        "candidates": candidates,
        "unrouted": unrouted,
    }


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build rule candidates from rule-neutral material claims.")
    parser.add_argument("--input-jsonl", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_plan(read_jsonl(args.input_jsonl))
    write_json(args.output_json, payload)
    print(json.dumps({key: payload[key] for key in ("ok", "input_material_claims", "candidate_count", "unrouted_count", "write_db")}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
