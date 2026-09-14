from emperor_v4.evaluation.profile_c1_verifier import _source_path


def test_archive_source_locator_resolves_as_evidence(tmp_path):
    target = tmp_path / "archive" / "retired" / "evidence.md"
    target.parent.mkdir(parents=True)
    target.write_text("Synthetic source evidence", encoding="utf-8")
    assert _source_path(tmp_path, "archive/retired/evidence.md#episode") == target
