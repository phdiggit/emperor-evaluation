from __future__ import annotations

from typing import Any, Mapping

from scripts.dev.retrieval_v3_diagnostics_lib.common import DEFAULT_RULE_CODE, text

def next_command_for(code: str, *, item_code: str, rule_code: str, formula_code: str, scope: str) -> str:
    output_root = f"tmp/retrieval_v3_consumption/diagnostics_next_{item_code}_{rule_code or 'all'}"
    if code == "material_review_pending":
        return (
            "python scripts/dev/retrieval_v3_material_review_consumer.py worklist "
            f"--env-file .env --item-code {item_code} --scope {scope} "
            f"--output-json {output_root}/material_review_worklist.json --output-md {output_root}/material_review_worklist.md"
        )
    if code == "factorization_required":
        return (
            "python scripts/dev/retrieval_v3_factorization_worklists.py worklist "
            f"--env-file .env --item-code {item_code} --rule-code {rule_code or DEFAULT_RULE_CODE} "
            f"--formula-code {formula_code} --scope {scope} "
            f"--output-json {output_root}/factorization_worklist.json "
            f"--output-md {output_root}/factorization_worklist.md "
            f"--batch-output-dir {output_root}/factorization_batches"
        )
    if code in {"material_score_required", "rule_score_required", "rule_score_stale"}:
        return (
            "python scripts/dev/retrieval_v3_rule_scorer.py apply "
            f"--env-file .env --item-code {item_code} --rule-code {rule_code or DEFAULT_RULE_CODE} "
            f"--formula-code {formula_code} --output-json {output_root}/rule_scorer.json "
            f"--output-md {output_root}/rule_scorer.md --execute"
        )
    if code == "role_matched_object_link_missing":
        return (
            "python scripts/dev/retrieval_v3_object_consumer.py apply "
            f"--env-file .env --output-json {output_root}/object_consumer.json "
            f"--output-md {output_root}/object_consumer.md --execute"
        )
    return ""

def build_next_actions(
    *,
    readiness: Mapping[str, Any] | None,
    coverage: Mapping[str, Any] | None,
    duplicates: Mapping[str, Any] | None,
    item_code: str,
    rule_code: str,
    formula_code: str,
    scope: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    sources = [readiness or {}, coverage or {}, duplicates or {}]
    for source in sources:
        checks = list(source.get("checks") or [])
        checks.extend(source.get("blockers") or [])
        checks.extend(source.get("warnings") or [])
        checks.extend(source.get("downstream_required") or [])
        for check in checks:
            code = text(check.get("code"))
            count = int(check.get("count") or 0)
            if not code or count <= 0 or code in seen:
                continue
            seen.add(code)
            command = text(check.get("next_command")) or next_command_for(
                code,
                item_code=item_code,
                rule_code=rule_code,
                formula_code=formula_code,
                scope=scope,
            )
            rows.append(
                {
                    "code": code,
                    "count": count,
                    "severity": text(check.get("severity")) or text(check.get("status")) or "warning",
                    "owner": text(check.get("owner")) or "human",
                    "description": text(check.get("description")),
                    "next_command": command,
                }
            )
    return rows

