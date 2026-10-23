from copy import deepcopy

import pytest

from emperor_v4.evaluation import maintenance, profile_markdown


@pytest.fixture
def verify_synthetic(tmp_path, monkeypatch):
    path = tmp_path / "axis.json"
    path.with_suffix(".md").write_text("synthetic reading", encoding="utf-8")
    monkeypatch.setattr(maintenance, "current_entries", lambda root: {"profile.C4": path})
    monkeypatch.setattr(maintenance, "load_json", lambda path: {
        "records": [{"ruler_id": "SYNTHETIC", "pool_status": "INCLUDED"}]
    })
    monkeypatch.setattr(profile_markdown, "render_profile_markdown", lambda payload: "synthetic reading")

    def verify(row):
        return maintenance.verify_profile_current(tmp_path, "C4", payload={"records": [deepcopy(row)]})

    return verify


def not_applicable():
    return {
        "ruler_id": "SYNTHETIC",
        "applicability": {"status": "NOT_APPLICABLE", "basis": "合成对象没有实际制度选择机会"},
        "axis_grade": None, "position": None, "score_100": None, "radar_value": None,
        "formal_status": "FORMAL_CURRENT",
    }


def test_not_applicable_remains_null_and_checks_reading(verify_synthetic):
    assert verify_synthetic(not_applicable())["status"] == "PASS"


@pytest.mark.parametrize("key,value", [
    ("axis_grade", "G0"), ("position", "LOW"), ("score_100", 0), ("radar_value", 0),
])
def test_not_applicable_rejects_grade_or_zero_projection(verify_synthetic, key, value):
    row = not_applicable()
    row[key] = value
    with pytest.raises(ValueError, match="不适用不得给档或投零分"):
        verify_synthetic(row)


@pytest.mark.parametrize("key", ["axis_grade", "position", "score_100", "radar_value"])
def test_not_applicable_requires_explicit_null_fields(verify_synthetic, key):
    row = not_applicable()
    del row[key]
    with pytest.raises(ValueError, match="不适用不得给档或投零分"):
        verify_synthetic(row)


@pytest.mark.parametrize("basis,status", [("", "FORMAL_CURRENT"), ("  ", "FORMAL_CURRENT"), ("范围理由", "DRAFT")])
def test_not_applicable_requires_explicit_basis_and_current_status(verify_synthetic, basis, status):
    row = not_applicable()
    row["applicability"]["basis"] = basis
    row["formal_status"] = status
    with pytest.raises(ValueError, match="缺少依据或正式状态"):
        verify_synthetic(row)


def test_not_applicable_still_requires_reading_parity(verify_synthetic, monkeypatch):
    monkeypatch.setattr(profile_markdown, "render_profile_markdown", lambda payload: "different reading")
    with pytest.raises(ValueError, match="reading view differs"):
        verify_synthetic(not_applicable())


def test_applicable_still_checks_grade_projection(verify_synthetic):
    row = not_applicable()
    row.update(applicability={"status": "APPLICABLE", "basis": "合成制度选择"},
               axis_grade="G3", position="MID", score_100=65, radar_value=65,
               grade_basis="合成机制正常运行", position_basis="合成档内定位")
    assert verify_synthetic(row)["status"] == "PASS"
    row["radar_value"] = 0
    with pytest.raises(ValueError, match="projection mismatch"):
        verify_synthetic(row)
