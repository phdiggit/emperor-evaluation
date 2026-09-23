"""Publication gates for the settled M1 ledger and its reading view."""
from __future__ import annotations

import json
import re
from pathlib import Path

from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.profile_record_integrity import verify_current_records
from emperor_v4.evaluation.profile_markdown import render_profile_markdown
from emperor_v4.evaluation.profile_m1_evidence import verify_evidence_scope
from emperor_v4.evaluation.profile_registry import profile_axis_entry

ROOT = Path(__file__).resolve().parents[3]
PROFILE_ROOT = ROOT / "docs" / "评分结算" / "人物画像"
SETTLEMENT = PROFILE_ROOT / "M1" / "01-M1军事判断与统帅能力正式结算.json"
MARKDOWN = SETTLEMENT.with_suffix(".md")
FORBIDDEN_AGGREGATES = ("第三项A+B", "D线性Q", "总排名", "第三项总分")
MATERIAL_INTENSITIES = {"MI1_CASE", "MI2_LIFECYCLE", "MI3_SUSTAINED_SYSTEMIC", "MI4_CROSS_PHASE_SYSTEMIC"}
MATERIAL_INTENSITY_ORDER = {"MI1_CASE": 1, "MI2_LIFECYCLE": 2, "MI3_SUSTAINED_SYSTEMIC": 3, "MI4_CROSS_PHASE_SYSTEMIC": 4}


def verify() -> dict[str, int]:
    payload = load_json(SETTLEMENT)
    entry = profile_axis_entry("M1")
    assert payload["contract_version"] == entry["axis_contract_version"], "M1 contract version drift"
    rows = payload["records"]
    verify_current_records(payload)
    pool = load_json(ROOT / "config/common/canonical-ruler-pool.json")
    assert {r["ruler_id"] for r in rows} == {r["ruler_id"] for r in pool["records"] if r["pool_status"] == "INCLUDED"}
    for row in rows:
        verify_evidence_scope(row)
        assert row["evidence_scope"]["schema_version"] == entry["evidence_scope_schema_version"]
        assert all((ROOT / ref).is_file() for ref in row["evidence_scope"]["source_refs"]), "M1 source registry missing"
        text = "\n".join(str(row.get(key, "")) for key in ("grade_basis", "position_basis"))
        serialized = json.dumps(row, ensure_ascii=False)
        assert not any(token in serialized for token in FORBIDDEN_AGGREGATES), "third-item aggregate leaked into M1 record"
        claims = set(re.findall(r"(?:取|定|支持)(G[0-5])", text))
        assert claims <= {row["axis_grade"]}, "published grade conflicts with explanatory basis"
        context_intensities = []
        for context in row.get("representative_parent_contexts") or []:
            assert context.get("direction") != "UNRESOLVED", (
                f"{row['ruler_name']}: unresolved direction leaked into formal representative context"
            )
            intensity = context.get("material_intensity")
            if intensity:
                assert intensity in MATERIAL_INTENSITIES, f"{row['ruler_name']}: invalid material_intensity {intensity}"
                context_intensities.append(intensity)
        for intensity in row.get("grade_basis_claimed_material_intensities") or []:
            assert intensity in MATERIAL_INTENSITIES, f"{row['ruler_name']}: invalid claimed material intensity {intensity}"
        max_intensity = row.get("representative_context_max_material_intensity")
        if max_intensity:
            assert max_intensity in MATERIAL_INTENSITIES, f"{row['ruler_name']}: invalid max material intensity {max_intensity}"
        if context_intensities:
            expected_max = max(context_intensities, key=MATERIAL_INTENSITY_ORDER.__getitem__)
            assert max_intensity == expected_max, (
                f"{row['ruler_name']}: representative context max material intensity mismatch "
                f"{max_intensity} != {expected_max}"
            )
    markdown = MARKDOWN.read_text(encoding="utf-8")
    assert markdown == render_profile_markdown(payload), "M1 reading view differs from current formal records"
    assert "非前线指挥链" not in markdown or "前线−" not in markdown.split("非前线指挥链")[0][-80:], "operational design displayed as frontline"
    assert not any(token in markdown for token in FORBIDDEN_AGGREGATES), "third-item aggregate leaked into reading view"
    return {"records": len(rows), "aggregate_leaks": 0, "grade_conflicts": 0}
