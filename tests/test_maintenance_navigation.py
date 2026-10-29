from pathlib import Path

from emperor_v4.evaluation.maintenance import inspect


def test_b2_navigation_reads_current_related_material_dispositions():
    root = Path(__file__).resolve().parents[1]
    report = inspect(root, ['I2.B2'], [], [])
    assert report['scope']['components'] == ['I2.B2']
    assert 'profile.C2' in report['semantic_review_consumers']
    assert isinstance(report['current_link_gaps'], list)
