"""Publication gates for the settled M1 ledger and its reading view."""
from __future__ import annotations

from pathlib import Path

from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.profile_record_integrity import verify_current_records
from emperor_v4.evaluation.maintenance import verify_profile_current
from emperor_v4.evaluation.profile_m1_evidence import verify_evidence_scope
from emperor_v4.evaluation.profile_m1_public import validate_public_reading
from emperor_v4.evaluation.profile_m1_public import archive_projection
from emperor_v4.evaluation.profile_m1_public import load_archive_context
from emperor_v4.evaluation.profile_m1_stability import verify_stability_review, verify_failure_aliases
from emperor_v4.evaluation.talent_registry_store import load_talent_registry
from emperor_v4.evaluation.profile_registry import profile_axis_entry

ROOT = Path(__file__).resolve().parents[3]
PROFILE_ROOT = ROOT / "docs" / "评分结算" / "人物画像"
SETTLEMENT = PROFILE_ROOT / "M1" / "01-M1军事判断与统帅能力正式结算.json"
MARKDOWN = SETTLEMENT.with_suffix(".md")
MATERIAL_INTENSITIES = {"MI1_CASE", "MI2_LIFECYCLE", "MI3_SUSTAINED_SYSTEMIC", "MI4_CROSS_PHASE_SYSTEMIC"}
MATERIAL_INTENSITY_ORDER = {"MI1_CASE": 1, "MI2_LIFECYCLE": 2, "MI3_SUSTAINED_SYSTEMIC": 3, "MI4_CROSS_PHASE_SYSTEMIC": 4}


def verify() -> dict[str, int]:
    payload = load_json(SETTLEMENT)
    entry = profile_axis_entry("M1")
    assert payload["contract_version"] == entry["axis_contract_version"], "M1 contract version drift"
    rows = payload["records"]
    assert payload["record_order_policy"] == "RADAR_VALUE_DESC_THEN_RULER_ID_ASC"
    assert rows == sorted(rows, key=lambda row: (-row["radar_value"], row["ruler_id"])), (
        "M1 display order differs from the declared policy"
    )
    talent = load_talent_registry(ROOT / "docs/公共成果/军事/02-武将人才等级.json")
    for profile in talent["profiles"]:
        if any(item.get("source_alias_refs") for item in profile.get("failure_accountability", [])):
            verify_failure_aliases(profile["failure_accountability"])
    verify_current_records(payload)
    verify_profile_current(ROOT, "M1", payload=payload)
    archive_context = load_archive_context(ROOT)
    for row in rows:
        from emperor_v4.evaluation.profile_m1_projection import registry_projection
        registry_projection(row['military_talent_registry_projection'])
        assert row.get('public_reading'), 'M1正式对象缺少直接维护的公开正文'
        comparisons = row['public_reading'].get('comparisons', [])
        assert len(comparisons) == 2, 'M1须提供两个有具体依据的同轴参照'
        roles = {item.get('comparison_role') for item in comparisons}
        assert roles in ({'SAME_POSITION','POSITION_CONTRAST'}, {'NO_SAME_POSITION_PEER','POSITION_CONTRAST'}), 'M1参照须同档同位加异位，或明确的无同位例外'
        validate_public_reading(row)
        if row.get('public_reading', {}).get('career_review') or row.get('public_reading', {}).get('comparisons'):
            archive_projection(row, ROOT, archive_context)
        verify_stability_review(row)
        verify_evidence_scope(row)
        assert row["evidence_scope"]["schema_version"] == entry["evidence_scope_schema_version"]
        assert all((ROOT / ref).is_file() for ref in row["evidence_scope"]["source_refs"]), "M1 source registry missing"
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
    return {"records": len(rows)}
