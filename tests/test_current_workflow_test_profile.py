from __future__ import annotations

from pathlib import Path

from conftest import CURRENT_WORKFLOW_TESTS, current_workflow_test_names


ROOT = Path(__file__).resolve().parents[1]


def test_current_workflow_manifest_is_unique_and_resolves_to_tests() -> None:
    rows = [
        line.strip()
        for line in CURRENT_WORKFLOW_TESTS.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    assert len(rows) == len(set(rows))
    assert all((ROOT / "tests" / name).is_file() for name in rows)


def test_current_workflow_manifest_keeps_native_chain_and_excludes_legacy_examples() -> None:
    names = current_workflow_test_names()

    assert "test_retrieval_v3_claim_extraction_worker.py" in names
    assert "test_retrieval_v3_candidate_binding_consumer.py" in names
    assert "test_retrieval_v3_factorization_consumer.py" in names
    assert "test_retrieval_v3_rule_scorer.py" in names
    assert "test_retrieval_v3_runtime_release.py" in names
    assert "test_export_md_trial_targets.py" not in names
    assert "test_i5b_typical_batch_a.py" not in names
    assert "test_object_pool_importer.py" not in names
