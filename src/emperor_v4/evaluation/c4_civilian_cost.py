"""Read-only checks for explicit civilian-cost adjudications, not a grader.

Historical attribution and the independence of consequences require semantic
review. These checks prevent inconsistent projections and inferred high grades.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

from emperor_v4.evaluation.formal_json_store import load_json
from .civilian_harm import legacy_c4_score, validate_formal, is_adopted

VERSION = "C4-CIVILIAN-COST-V1"
ROOT_PATH = Path("docs/评分结算/净收益/第二项治国净收益/财政民生")
AUDIT_PATH = ROOT_PATH / "06-主动民力成本去重审计.json"


def validate_record(row: Mapping[str, Any]) -> None:
    if 'civilian_harm_adjudication' in row:
        validate_formal(row)
        if is_adopted(row):
            return
    name = row.get("ruler_id", "synthetic")
    grade = row.get("destructive_amplification_grade", "")
    if not isinstance(grade, str) or not re.fullmatch(r"DA[0-6]", grade):
        raise ValueError(f"C4 invalid DA grade: {name}")
    tier = int(grade[-1])
    review = row.get("active_civilian_cost_review") or {}
    if review.get("version") != VERSION or review.get("status") != "REVIEWED":
        raise ValueError(f"C4 missing civilian-cost review: {name}")
    mode = review.get("evidence_mode")
    if mode not in {"DIRECT", "INFERRED", "NONE"}:
        raise ValueError(f"C4 invalid civilian evidence mode: {name}")
    if (mode == "NONE") != (tier == 0):
        raise ValueError(f"C4 residual admission disagrees with DA: {name}")
    if mode == "INFERRED" and tier != 1:
        raise ValueError(f"C4 inference exceeds the conservative floor: {name}")
    if review.get("military_input_double_charge") is not False:
        raise ValueError(f"C4 military input double charge: {name}")
    for field in ("choice_and_civilian_basis", "absorbed_and_excluded_basis"):
        if not isinstance(review.get(field), str) or not review[field].strip():
            raise ValueError(f"C4 missing {field}: {name}")
    penalty = 4.5 * tier
    if row.get("destructive_amplification_penalty") != penalty:
        raise ValueError(f"C4 DA penalty mismatch: {name}")
    expected = legacy_c4_score(row['positive_score_retained'], row['deterioration_penalty'], penalty)
    if row.get("score") != expected or row.get("raw_score") != expected:
        raise ValueError(f"C4 signed score mismatch: {name}")


def verify_snapshot(workspace_root: Path) -> dict[str, Any]:
    source = load_json(workspace_root / ROOT_PATH / "04-C4正式结算.json")
    audit = load_json(workspace_root / AUDIT_PATH)
    rows = source["scores"]
    from .civilian_harm_handoffs import verify_handoffs
    verify_handoffs(workspace_root, rows)
    mechanism = source.get('civilian_harm_mechanism')
    if mechanism:
        from .civilian_harm import FORMAL_VERSION
        if mechanism.get('version') != FORMAL_VERSION:
            raise ValueError('Unknown civilian-harm mechanism')
        pool = load_json(workspace_root/'config/common/canonical-ruler-pool.json')['records']
        included = {r['ruler_id'] for r in pool if r['pool_status']=='INCLUDED'}
        ready = {r['ruler_id'] for r in pool if r['settlement_readiness']=='COMPOSITE_READY'}
        for row in rows:
            status = row.get('civilian_harm_adjudication',{}).get('status')
            rid=row['ruler_id']
            if ((rid not in included and status != 'OUTSIDE_POOL') or
                (rid in included-ready and status != 'NOT_READY') or
                (rid in ready and status not in {'ADOPTED','BASELINE_RETAINED','UNRESOLVED'})):
                raise ValueError(f'Civilian-harm readiness drift: {rid}')
    indexed = {row["ruler_id"]: row for row in rows}
    reviewed = {row["ruler_id"]: row for row in audit["records"]}
    if len(indexed) != len(rows) or len(reviewed) != len(audit["records"]) or set(indexed) != set(reviewed):
        raise ValueError("C4 civilian audit coverage mismatch")
    if audit["record_count"] != len(rows) or audit.get("contract_version") != VERSION:
        raise ValueError("C4 civilian audit metadata mismatch")
    scores = sorted((row["score"] for row in rows), reverse=True)
    from .second_item_c_public import render_complete_markdown
    from .reading_layout import check_reading
    # Compare every current index/person page to JSON, including the complete
    # technical verdict and public evidence; do not infer a roster from headings.
    check_reading(workspace_root, ROOT_PATH / '04-C4正式结算.md', render_complete_markdown(source))
    for row in rows:
        validate_record(row)
        if 'civilian_harm_adjudication' in row:
            validate_formal(row, workspace_root)
        review = row["active_civilian_cost_review"]
        entry = reviewed[row["ruler_id"]]
        if entry["final_grade"] != row["destructive_amplification_grade"] or entry["final_penalty"] != row["destructive_amplification_penalty"]:
            raise ValueError(f"C4 civilian audit verdict mismatch: {row['ruler_id']}")
        for field in ("evidence_mode", "choice_and_civilian_basis", "absorbed_and_excluded_basis"):
            if entry[field] != review[field]:
                raise ValueError(f"C4 civilian audit basis mismatch: {row['ruler_id']}")
        if row["rank"] != scores.index(row["score"]) + 1 or row["main_band"] != "C4":
            raise ValueError(f"C4 score presentation mismatch: {row['ruler_id']}")
    return {"status": "PASS", "record_count": len(rows), "scope": "STRUCTURE_AND_PROJECTIONS_NOT_SEMANTIC_REGRADING"}
