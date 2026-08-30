from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from emperor_v4.evaluation.profile_markdown import render_profile_markdown


ROOT = Path(__file__).resolve().parents[3]
PROFILE_ROOT = ROOT / "docs" / "评分结算" / "皇帝人物画像"
C5 = PROFILE_ROOT / "C5/02-C5权力运用风格与克制正式结算.json"
C5_MD = C5.with_suffix(".md")
C5_AUDIT = PROFILE_ROOT / "C5/04-C5主要入口单元处置审计.json"
C5_DENSITY = PROFILE_ROOT / "C5/05-C5高档材料密度复核.json"
C5_STRUCTURE = PROFILE_ROOT / "C5/07-C5高档与证据门结构复核.json"
C5_REMEDIATION = PROFILE_ROOT / "C5/08-C5聊天版全池二次校准整改复核.json"
JOINT = PROFILE_ROOT / "交叉轴复核/23-C2与C5同链边界及强度联合复核.json"
MANIFEST = PROFILE_ROOT / "00-已结算轴正式入口.json"
PROJECT = ROOT / "config" / "project.yml"

GRADE_POINTS = {
    "G0": {"LOW": 2, "MID": 7, "HIGH": 12},
    "G1": {"LOW": 18, "MID": 25, "HIGH": 31},
    "G2": {"LOW": 38, "MID": 45, "HIGH": 51},
    "G3": {"LOW": 58, "MID": 65, "HIGH": 71},
    "G4": {"LOW": 77, "MID": 82, "HIGH": 87},
    "G5": {"LOW": 91, "MID": 94, "HIGH": 97},
}
OUTPUT_BY_EVIDENCE = {
    "E1": ("EPISODE_TAG", "LOW", "EVIDENCE_LIMITED"),
    "E2": ("BOUNDED_PROFILE", "MEDIUM", "EVIDENCE_LIMITED"),
    "E3": ("FULL_GRADE", "HIGH", "FINAL"),
}


def _read(path: Path) -> bytes:
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), f"UTF-8 BOM is forbidden: {path}"
    raw.decode("utf-8")
    return raw


def _load(path: Path) -> dict:
    return json.loads(_read(path).decode("utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(_read(path)).hexdigest()


def _md_rows() -> list[tuple[int, str, str, str, str, str]]:
    rows = []
    for line in _read(C5_MD).decode("utf-8").splitlines():
        if line.startswith("| ") and not line.startswith("|---") and "展示序" not in line:
            cells = [cell.strip().replace("\\|", "|") for cell in line[1:-1].split("|")]
            rows.append((int(cells[5]), cells[3], cells[2], cells[6], cells[7], cells[8]))
    return rows


def verify() -> dict[str, object]:
    c5, audit, density, structure, remediation, joint = (
        _load(path) for path in (C5, C5_AUDIT, C5_DENSITY, C5_STRUCTURE, C5_REMEDIATION, JOINT)
    )
    assert _read(C5_MD).decode("utf-8") == render_profile_markdown(c5)
    c5_by_id = {row["ruler_id"]: row for row in c5["records"]}
    assert len(c5_by_id) == 184
    assert (
        c5["contract_sha256"]
        == density["contract_sha256"]
        == structure["contract_sha256"]
        == joint["contract_sha256"]
    )

    allowed_same_chain = {"NO_TRIGGER", "CONSTRUCT_SEPARATED"}
    c5_statuses = {row["same_chain_semantic_conflict_review_status"] for row in c5["records"]}
    assert c5_statuses == allowed_same_chain

    c5_parent_ids = set()
    for row in c5["records"]:
        assert row["grade_numeric"] == int(row["axis_grade"][1])
        assert row["radar_value"] == row["score_100"] == GRADE_POINTS[row["axis_grade"]][row["position"]]
        assert (row["output_mode"], row["confidence"], row["score_status"]) == OUTPUT_BY_EVIDENCE[
            row["axis_evidence_level"]
        ]
        parents = {parent["parent_id"]: parent for parent in row["parents"]}
        assert len(parents) == len(row["parents"])
        c5_parent_ids.update(parents)
        assert set(row["axis_relevance_check"]["scoring_parent_refs"]) == set(parents)
        for group in row["unit_groups"]:
            if group["status"] == "SCORING_PARENT":
                assert group["parent_id"] in parents
            else:
                assert "parent_id" not in group or group["parent_id"] is None
        directions = {parent["direction"] for parent in row["parents"]}
        if row["grade_numeric"] >= 3 and directions and directions <= {"NEGATIVE", "MIXED_NEGATIVE"}:
            assert row["review_status"] in {"RECALIBRATED", "VALIDATED"}
            assert row["public_evidence_points"] and row["source_refs"]
        assert not (row["grade_numeric"] == 0 and directions and directions <= {"POSITIVE", "MIXED_POSITIVE"})

    decisions = {row["ruler_id"]: row for row in remediation["decisions"]}
    assert remediation["decision_count"] == len(decisions) == 184
    assert set(decisions) == set(c5_by_id)
    for ruler_id, row in c5_by_id.items():
        decision = decisions[ruler_id]
        assert decision["after"] == (
            f"{row['axis_grade']}-{row['position']}/{row['score_100']}/{row['axis_evidence_level']}"
        )
        assert row["adjudication_ref"] == f"C5-CHAT-REVIEW-V2#{ruler_id}"
        assert row["public_evidence_points"] and row["source_refs"]
        assert row["source_quality"]["named_source_count"] >= 1
        assert row["source_quality"]["locator_count"] >= 1

    units = audit["units"]
    assert audit["unit_count"] == len(units) == 1680
    assert len({unit["unit_id"] for unit in units}) == len(units)
    assert set(audit["status_counts"]) == {
        "SCORING_PARENT", "BACKGROUND_VALIDATION", "AXIS_OUT_WITH_REASON"
    }, "all entries cannot receive one uniform disposition"
    assert sum(audit["status_counts"].values()) == len(units)
    assert {unit["scoring_parent_id"] for unit in units if unit["status"] == "SCORING_PARENT"} <= c5_parent_ids
    assert all((unit["status"] == "SCORING_PARENT") == bool(unit["scoring_parent_id"]) for unit in units)

    yang = c5_by_id["RULER-SHADOW-杨坚"]
    yang_groups = {token: group for group in yang["unit_groups"] for token in group["unit_ids"]}
    for material_id in ("LAW-16-005", "LAW-16-006", "LAW-16-007"):
        group = yang_groups[f"LOCAL_LEGAL_REGISTRY::{material_id}"]
        assert group["status"] == "SCORING_PARENT" and group["parent_id"] == "C5-P119-LATE-BREACH"
    early = yang_groups["LOCAL_LEGAL_REGISTRY::LAW-16-008"]
    assert early["status"] == "SCORING_PARENT" and early["parent_id"] == "C5-P119-EARLY-LAW"
    late = next(parent for parent in yang["parents"] if parent["parent_id"] == "C5-P119-LATE-BREACH")
    assert late["direction"] == "NEGATIVE" and late["intensity"] == "MI4_CROSS_PHASE_SYSTEMIC"

    liubang = c5_by_id["RULER-HAN-LIUBANG"]
    anger = next(group for group in liubang["unit_groups"] if "I2-WHAN-LB-MINISTER-ANGER-001" in group["unit_ids"])
    assert anger["status"] == "SCORING_PARENT" and anger["parent_id"] == "C5-P016-ANGER"
    advice = next(group for group in liubang["unit_groups"] if "I2-WHAN-LB-LUJIA-ADVICE-001" in group["unit_ids"])
    assert advice["status"] == "BACKGROUND_VALIDATION"
    assert (liubang["axis_grade"], liubang["position"]) == ("G3", "LOW")
    liuxiu = c5_by_id["RULER-HAN-LIUXIU"]
    assert (liuxiu["axis_grade"], liuxiu["position"]) == ("G4", "LOW")

    assert joint["same_chain_unresolved_count"] == 0
    assert joint["strong_suppression_crosscheck"]["unresolved_count"] == 0
    assert joint["strong_suppression_crosscheck"]["aligned_count"] == 11
    assert joint["policy"]["b2_channel_presence_is_not_c5_scoring"] is True
    assert joint["policy"]["general_judicial_governance_is_not_c5_high_strength"] is True

    assert _md_rows() == [
        (
            row["radar_value"], f"{row['axis_grade']}-{row['position']}", row["ruler_name"],
            row["axis_evidence_level"], row["confidence"], row["output_mode"],
        )
        for row in c5["records"]
    ]
    manifest = _load(MANIFEST)
    axis = next(item for item in manifest["axes"] if item["axis_code"] == "C5")
    assert axis["json_sha256"] == _sha(C5)
    assert JOINT.relative_to(MANIFEST.parent).as_posix() in axis["audit_jsons"]
    assert C5_REMEDIATION.relative_to(MANIFEST.parent).as_posix() in axis["audit_jsons"]
    project = yaml.safe_load(_read(PROJECT).decode("utf-8"))
    assert project["profile_assessment"]["settled_axes"]["C5"]["joint_boundary_review_json"].endswith(JOINT.name)

    hashes = {path.name: _sha(path) for path in (C5, C5_MD, C5_AUDIT, C5_REMEDIATION, JOINT)}
    return {
        "status": "PASS",
        "record_count": 184,
        "c5_parent_count": sum(len(row["parents"]) for row in c5["records"]),
        "c5_unit_count": len(units),
        "grade_distribution": c5["summary"]["grade_distribution"],
        "evidence_distribution": c5["summary"]["axis_evidence_distribution"],
        "hashes": hashes,
        "combined_sha256": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
    }


def main() -> None:
    print(json.dumps(verify(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
