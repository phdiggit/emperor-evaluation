"""Source collection contracts, using synthetic records rather than ruler snapshots."""
import pytest
from emperor_v4.evaluation.historical_impact import _source_records


def test_default_records_and_explicit_scores_are_distinct():
    payload = {
        "records": [{"ruler_id": "synthetic", "basis": "profile evidence"}],
        "scores": [{"ruler_id": "synthetic", "state_anchors": {"S_end": "synthetic-state"}}],
    }
    assert _source_records(payload, {})["synthetic"] is payload["records"][0]
    assert _source_records(payload, {"collection": "scores"})["synthetic"] is payload["scores"][0]


@pytest.mark.parametrize("payload,source", [
    ({"scores": []}, {}),  # Do not infer a missing collection.
    ({"records": []}, {"collection": "scores"}),
    ({"records": {}}, {}),
    ({"records": [None]}, {}),
    ({"records": [{"basis": "no identity"}]}, {}),
    ({"records": [{"ruler_id": "duplicate"}, {"ruler_id": "duplicate"}]}, {}),
    ({"records": []}, {"collection": "supplementary_records"}),
    ({"records": []}, {"collection": []}),
    ({"records": []}, {"collection": None}),
])
def test_invalid_or_ambiguous_source_collections_fail(payload, source):
    with pytest.raises(ValueError):
        _source_records(payload, source)
