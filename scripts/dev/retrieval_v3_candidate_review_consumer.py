from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v2_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v2_import_plan import json_param  # noqa: E402
from scripts.dev.retrieval_v2_pg_schema import DEFAULT_PG_SCHEMA, DEFAULT_V3_DSN_ENV, schema_cursor  # noqa: E402
from scripts.dev.retrieval_v3_candidate_review_worklist import stable_code, stable_json, text  # noqa: E402


PROFILE = "retrieval_v3_material_candidate_plan"
ALLOWED_VERDICTS = {"accepted_candidate", "supporting_only", "rejected", "needs_context"}
ALLOWED_ROLES = {
    "",
    "appointed_actor",
    "entrusted_actor",
    "delegated_actor",
    "strategic_advisor",
    "military_commander",
    "civil_official",
    "misappointed_actor",
    "misdelegated_actor",
    "misentrusted_actor",
    "authority_revoked_target",
}


class CandidateReviewConsumerError(ValueError):
    pass


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, Mapping):
            raise CandidateReviewConsumerError(f"{path}:{line_no}: expected object")
        rows.append(dict(payload))
    return rows


def review_status_for_verdict(verdict: str) -> str:
    if verdict == "accepted_candidate":
        return "accepted"
    if verdict == "rejected":
        return "rejected"
    return "needs_review"


def review_route_for_verdict(verdict: str) -> str:
    """Separate terminal support from work that actually needs context expansion."""
    if verdict == "accepted_candidate":
        return "identity_gate"
    if verdict == "rejected":
        return "terminal_rejected"
    if verdict == "supporting_only":
        return "terminal_supporting_only"
    return "needs_context_expansion"


def validate_patch(row: Mapping[str, Any]) -> dict[str, Any]:
    code = text(row.get("review_code"))
    verdict = text(row.get("review_verdict"))
    if not code:
        raise CandidateReviewConsumerError("review_code is required")
    if verdict not in ALLOWED_VERDICTS:
        raise CandidateReviewConsumerError(f"{code}: unsupported review_verdict={verdict!r}")
    role = text(row.get("candidate_role"))
    if role not in ALLOWED_ROLES:
        raise CandidateReviewConsumerError(f"{code}: unsupported candidate_role={role!r}")
    direction = text(row.get("direction"))
    if direction not in {"positive", "negative"}:
        raise CandidateReviewConsumerError(f"{code}: direction must be positive or negative")
    facts = row.get("required_facts")
    if not isinstance(facts, Mapping):
        raise CandidateReviewConsumerError(f"{code}: required_facts must be an object")
    fact_keys = (
        "has_appointment_or_authorization",
        "has_named_actor",
        "has_task_or_responsibility",
        "has_result_or_feedback",
        "has_continuity_or_reuse",
    )
    if any(not isinstance(facts.get(key), bool) for key in fact_keys):
        raise CandidateReviewConsumerError(f"{code}: required_facts must use booleans")
    scoring = row.get("scoring_candidate") is True
    protocol_ok = bool(
        facts["has_appointment_or_authorization"]
        and facts["has_named_actor"]
        and facts["has_task_or_responsibility"]
        and (facts["has_result_or_feedback"] or facts["has_continuity_or_reuse"])
    )
    if scoring and (not protocol_ok or row.get("usable_for_scoring_cluster") is not True):
        raise CandidateReviewConsumerError(f"{code}: scoring candidate violates appointment_delegation protocol")
    return {
        "review_code": code,
        "review_verdict": verdict,
        "review_status": review_status_for_verdict(verdict),
        "review_route": review_route_for_verdict(verdict),
        "second_review_required": verdict == "needs_context",
        "review_note": text(row.get("review_note")),
        "candidate_role": role,
        "direction": direction,
        "required_facts": dict(facts),
        "scoring_candidate": scoring,
        "usable_for_scoring_cluster": row.get("usable_for_scoring_cluster") is True,
        "identity_gate": text(row.get("identity_gate")),
        "evidence_passage_codes": [text(value) for value in row.get("evidence_passage_codes") or [] if text(value)],
    }


def candidate_lookup(cur: Any) -> dict[str, dict[str, Any]]:
    cur.execute(
        """
        select id, candidate_code, candidate_payload, candidate_direction::text as candidate_direction,
               candidate_object_role, review_status::text as review_status
          from retrieval_v3.claim_rule_binding_candidates
         where routed_by_profile = %s and candidate_rule_code = %s
        """,
        (PROFILE, "appointment_delegation"),
    )
    rows = {}
    for row in cur.fetchall():
        item = dict(row)
        item["review_code"] = stable_code(text(item["candidate_code"]))
        rows[item["review_code"]] = item
    return rows


def run_consumer(*, patch_rows: Sequence[Mapping[str, Any]], dsn: str, schema_name: str, execute: bool) -> dict[str, Any]:
    patches = [validate_patch(row) for row in patch_rows]
    psycopg, dict_row = import_psycopg()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            lookup = candidate_lookup(cur)
            missing = sorted(set(row["review_code"] for row in patches) - set(lookup))
            if missing:
                raise CandidateReviewConsumerError(f"review candidates not found: {missing[:5]}")
            counts: Counter[str] = Counter()
            route_counts: Counter[str] = Counter()
            for patch in patches:
                current = lookup[patch["review_code"]]
                current_payload = current.get("candidate_payload") if isinstance(current.get("candidate_payload"), Mapping) else {}
                review_payload = {
                    "review_verdict": patch["review_verdict"],
                    "review_route": patch["review_route"],
                    "second_review_required": patch["second_review_required"],
                    "review_note": patch["review_note"],
                    "required_facts": patch["required_facts"],
                    "candidate_role": patch["candidate_role"],
                    "direction": patch["direction"],
                    "scoring_candidate": patch["scoring_candidate"],
                    "usable_for_scoring_cluster": patch["usable_for_scoring_cluster"],
                    "identity_gate": patch["identity_gate"],
                    "evidence_passage_codes": patch["evidence_passage_codes"],
                    "formal_binding_allowed": False,
                    "source": "retrieval_v3_candidate_review_consumer",
                }
                payload = {**dict(current_payload), "candidate_review": review_payload, "formal_binding_allowed": False}
                if execute:
                    cur.execute(
                        """
                        update retrieval_v3.claim_rule_binding_candidates
                           set review_status = %s::retrieval_v3.rv3_review_status,
                               candidate_direction = %s::retrieval_v3.rv3_claim_direction,
                               candidate_object_role = %s,
                               required_facts_present = %s::jsonb,
                               candidate_payload = %s::jsonb,
                               updated_at = now()
                         where id = %s
                        """,
                        (
                            patch["review_status"],
                            patch["direction"],
                            patch["candidate_role"],
                            json_param(patch["required_facts"]),
                            json_param(payload),
                            current["id"],
                        ),
                    )
                counts[patch["review_status"]] += 1
                route_counts[patch["review_route"]] += 1
        if execute:
            conn.commit()
        else:
            conn.rollback()
    return {
        "ok": True,
        "write_db": execute,
        "executed": execute,
        "input_rows": len(patches),
        "counts_by_review_status": dict(sorted(counts.items())),
        "counts_by_review_route": dict(sorted(route_counts.items())),
        "formal_binding_created": 0,
        "identity_rows_changed": 0,
        "legacy_data_reads": False,
        "legacy_data_migrated": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply validated v3 candidate review patches; dry-run unless --execute.")
    parser.add_argument("--input-jsonl", type=Path, required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default=DEFAULT_V3_DSN_ENV)
    parser.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.env_file:
        load_env_file(args.env_file)
    payload = run_consumer(
        patch_rows=read_jsonl(args.input_jsonl),
        dsn=resolve_dsn(args.dsn_env),
        schema_name=args.pg_schema,
        execute=args.execute,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
