"""Coverage is independent of ability shape, role certainty and grade."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from emperor_v4.evaluation.profile_m1_evidence import (
    ABILITY_LABELS, COVERAGE_LABEL, COVERAGE_STATUS, evidence_scope, verify_evidence_scope,
)
from emperor_v4.evaluation.profile_markdown import _overview_table

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("level,mode", [("E1", "EPISODE_TAG"), ("E2", "BOUNDED_PROFILE"), ("E3", "FULL_GRADE")])
def test_completed_registry_does_not_require_strong_personal_evidence(level, mode):
    record = {"ruler_name": "合成对象", "axis_evidence_level": level, "output_mode": mode,
              "score_status": "FINAL", "evidence_scope": evidence_scope(level, mode)}
    verify_evidence_scope(record)
    assert record["evidence_scope"]["material_coverage_status"] == COVERAGE_STATUS
    assert record["evidence_scope"]["ability_evidence_label"] == ABILITY_LABELS[level]


def test_evidence_scope_never_produces_grade_or_confidence():
    scope = evidence_scope("E1", "EPISODE_TAG")
    assert not {"axis_grade", "position", "radar_value", "score_100", "confidence"} & scope.keys()


def test_missing_or_conflicting_scope_fails_closed():
    record = {"ruler_name": "合成对象", "axis_evidence_level": "E1", "output_mode": "EPISODE_TAG", "score_status": "FINAL"}
    with pytest.raises(AssertionError, match="missing"):
        verify_evidence_scope(record)
    record["evidence_scope"] = evidence_scope("E1", "EPISODE_TAG")
    record["evidence_scope"]["material_coverage_status"] = "UNKNOWN"
    with pytest.raises(AssertionError, match="inconsistent"):
        verify_evidence_scope(record)


def test_retired_mapping_gate_cannot_override_current_scope():
    record = {"ruler_name": "合成对象", "axis_evidence_level": "E2", "output_mode": "BOUNDED_PROFILE",
              "score_status": "FINAL", "evidence_scope": evidence_scope("E2", "BOUNDED_PROFILE"),
              "normative_entry_gate_mode_adjustment": "obsolete"}
    with pytest.raises(AssertionError, match="retired entry gate"):
        verify_evidence_scope(record)


def test_m1_table_exposes_both_layers_without_regrading():
    record = {"ruler_name": "合成对象", "axis_grade": "G2", "position": "MID", "radar_value": 45,
              "confidence": "LOW", "typical_pattern": "共享权力下的有限本人行为。",
              "evidence_scope": evidence_scope("E1", "EPISODE_TAG")}
    before = copy.deepcopy(record)
    table = "\n".join(_overview_table("M1", [record], {}))
    assert COVERAGE_LABEL in table
    assert ABILITY_LABELS["E1"] in table
    assert "材料底池覆盖" in table and "本人能力证据" in table
    assert record == before


def test_reader_projects_formal_scope_verbatim():
    spec = importlib.util.spec_from_file_location("reader_scope_build", ROOT / "reader/build.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    scope = evidence_scope("E1", "EPISODE_TAG")
    projected = builder.axis_projection({"evidence_scope": scope}, ["evidence_scope"])
    assert projected["evidence_scope"] == scope


def test_person_and_compare_renderer_use_formal_scope_not_e_level_as_coverage():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js unavailable")
    template = (ROOT / "reader/index.template.html").read_text(encoding="utf-8")
    function = template.split("function axisEvidenceScope(a,c){", 1)[1].split("function axisEvidence(r,c,suffix=''){", 1)[0]
    script = (
        "const readerText=x=>x;const mode=x=>x;const axisProse=x=>'<p>'+x+'</p>';\n"
        "function axisEvidenceScope(a,c){" + function + "\n"
        "const a=" + json.dumps({"axis_evidence_level": "E1", "output_mode": "EPISODE_TAG",
                                "evidence_scope": evidence_scope("E1", "EPISODE_TAG")}, ensure_ascii=False) + ";\n"
        "console.log(JSON.stringify([axisEvidenceScope(a,'M1'),axisEvidenceScope({},'M1'),axisEvidenceScope(a,'C2')]));"
    )
    result = subprocess.run([node, "-"], input=script, capture_output=True, text=True, encoding="utf-8", check=True)
    full, missing, other = json.loads(result.stdout)
    assert full["coverage"] == COVERAGE_LABEL
    assert ABILITY_LABELS["E1"] in full["detail"]
    assert missing["coverage"] == ""
    assert other["coverage"] == "E1"
