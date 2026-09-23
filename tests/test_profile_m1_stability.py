"""Synthetic failure-gate invariants; no historical score snapshots."""
from copy import deepcopy
import pytest

from emperor_v4.evaluation.profile_m1_stability import verify_stability_review, verify_failure_aliases


def sample():
    case = dict(cycle_ref="cycle", alias_refs=["parent"], label="独立周期", negative_tier="A",
                tier_basis="PERSON_NEGATIVE_RESULT", source_refs=["source"], effect="POSITION_LIMIT")
    case.update({k: "已明确记录。" for k in ("consequence", "attribution", "feedback", "recovery", "residual_loss", "decision_basis")})
    return dict(ruler_id="synthetic", axis_grade="G5", position="LOW", m1_stability_review=dict(
        schema_version="m1-stability-review-v1", reviewed_under_contract="FORMAL-V1.3",
        published_grade="G5", published_position="LOW", decision="PASS", basis="重组有效但损失保留。",
        cases=[case], source_refs=["source"]))


def test_single_major_failure_with_recovery_is_not_an_automatic_cap():
    verify_stability_review(sample())


def test_parent_and_person_failure_cannot_be_two_cycles():
    row = sample()
    duplicate = deepcopy(row["m1_stability_review"]["cases"][0])
    duplicate.update(cycle_ref="parent", alias_refs=[])
    row["m1_stability_review"]["cases"].append(duplicate)
    with pytest.raises(AssertionError, match="duplicate"):
        verify_stability_review(row)


def test_mixed_parent_cannot_supply_a_pure_negative_grade():
    row = sample()
    row["m1_stability_review"]["cases"][0].update(tier_basis="UNSPLIT_MIXED", negative_tier="S-")
    with pytest.raises(AssertionError, match="mixed parent"):
        verify_stability_review(row)


def test_unsplit_damage_is_reviewable_without_inventing_a_negative_grade():
    row = sample()
    row["m1_stability_review"]["cases"][0].update(tier_basis="UNSPLIT_MIXED", negative_tier=None)
    verify_stability_review(row)


def test_explicit_blocker_cannot_coexist_with_g5():
    row = sample()
    row["m1_stability_review"]["decision"] = "BLOCK_G5"
    row["m1_stability_review"]["cases"][0].update(effect="BLOCK_G5", pattern_changing_basis="核心能力持续失能，未重建。")
    with pytest.raises(AssertionError, match="G5 with"):
        verify_stability_review(row)


def test_changed_grade_requires_synchronized_review():
    row = sample()
    row.update(axis_grade="G4", position="HIGH")
    with pytest.raises(AssertionError, match="stale"):
        verify_stability_review(row)
    row["m1_stability_review"].update(published_grade="G4", published_position="HIGH")
    verify_stability_review(row)


def test_no_failures_does_not_raise_a_grade():
    row = sample()
    row.update(axis_grade="G4", position="HIGH")
    row["m1_stability_review"].update(published_grade="G4", published_position="HIGH", cases=[])
    verify_stability_review(row)
    assert row["axis_grade"] == "G4"


def test_high_grade_requires_review():
    row = sample()
    row.pop("m1_stability_review")
    with pytest.raises(AssertionError, match="missing"):
        verify_stability_review(row)


def test_shared_source_cannot_reintroduce_an_explicitly_merged_failure():
    failures = [{"campaign_ref": "person-phase", "source_alias_refs": ["parent"]}]
    verify_failure_aliases(failures)
    with pytest.raises(AssertionError, match="duplicate source"):
        verify_failure_aliases(failures + [{"campaign_ref": "parent"}])


def test_failure_reader_displays_complete_source_fields(tmp_path):
    from pathlib import Path
    import shutil
    import subprocess
    import json

    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for reader behavior")
    template = (Path(__file__).resolve().parents[1] / "reader/index.template.html").read_text(encoding="utf-8")
    function = template.split("function m1FailureReview(a){", 1)[1].split("function axisEvidenceScope", 1)[0]
    row = sample()
    case = row["m1_stability_review"]["cases"][0]
    case.update(label="合成<战役>", recovery="前段恢复；后段未恢复，不能删去。", residual_loss="损失仍然存在。")
    script = tmp_path / "reader.cjs"
    script.write_text("const assert=require('node:assert/strict');const esc=s=>String(s).replace(/</g,'&lt;').replace(/>/g,'&gt;');const axisProse=s=>'<p>'+esc(s)+'</p>';function m1FailureReview(a){" + function +
        "const text=m1FailureReview(" + json.dumps(row, ensure_ascii=False) + ");assert(text.includes('合成&lt;战役&gt;'));assert(text.includes('前段恢复；后段未恢复，不能删去。'));assert(text.includes('损失仍然存在。'));assert.equal(m1FailureReview({}),'');", encoding="utf-8")
    subprocess.run([node, str(script)], check=True, capture_output=True, text=True)
