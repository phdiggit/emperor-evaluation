from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v2_intake_manifest import text


REQUIRED_KEYS = (
    "claim_id",
    "contract_rule_id",
    "rule_code",
    "predicate",
    "direction",
    "object_role",
    "object_id",
    "target_object_id",
    "binding_note",
)


class DirectBindingPlanError(ValueError):
    pass


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, Mapping):
            raise DirectBindingPlanError(f"{path}:{line_no}: expected JSON object")
        rows.append({**payload, "_line_no": line_no})
    return rows


def validate_direct_assessment(row: Mapping[str, Any]) -> dict[str, Any]:
    line_no = row.get("_line_no", "?")
    missing = [key for key in REQUIRED_KEYS if row.get(key) in (None, "")]
    if missing:
        raise DirectBindingPlanError(f"line {line_no}: missing direct-binding fields: {', '.join(missing)}")
    if text(row.get("direction")) not in {"positive", "negative"}:
        raise DirectBindingPlanError(f"line {line_no}: direction must be positive or negative")
    if len(text(row.get("binding_note"))) < 24:
        raise DirectBindingPlanError(f"line {line_no}: binding_note must be high-information")
    try:
        identifiers = {key: int(row[key]) for key in ("claim_id", "contract_rule_id", "object_id", "target_object_id")}
    except (TypeError, ValueError) as exc:
        raise DirectBindingPlanError(f"line {line_no}: direct-binding identifiers must be integers") from exc
    if any(value <= 0 for value in identifiers.values()):
        raise DirectBindingPlanError(f"line {line_no}: direct-binding identifiers must be positive")
    return {
        **identifiers,
        "rule_code": text(row.get("rule_code")),
        "predicate": text(row.get("predicate")),
        "direction": text(row.get("direction")),
        "object_role": text(row.get("object_role")),
        "confidence": row.get("confidence"),
        "binding_note": text(row.get("binding_note")),
        "assessment_lane": "normal_direct",
        "candidate_required": False,
    }


def build_plan(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    assessments = [validate_direct_assessment(row) for row in rows]
    return {
        "ok": True,
        "generated_by": "scripts/dev/retrieval_v3_direct_binding_plan.py",
        "write_db": False,
        "assessment_lane": "normal_direct",
        "candidate_required": False,
        "next_step": "direct_binding_consumer_execute",
        "assessments": assessments,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate direct formal-binding assessments without creating candidates.")
    parser.add_argument("--input-jsonl", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args(argv)
    payload = build_plan(read_jsonl(args.input_jsonl))
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "assessments": len(payload["assessments"]), "write_db": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
