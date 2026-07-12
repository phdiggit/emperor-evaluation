from pathlib import Path

from scripts.dev import retrieval_v3_identity_gate_consumer as tool


def test_identity_gate_query_ignores_merged_audit_shells() -> None:
    source = Path(tool.__file__).read_text(encoding="utf-8")

    assert "o.identity_status::text = 'active'" in source


def row(**overrides):
    value = {
        "object_id": 10,
        "identity_status": "active",
        "target_object_id": 20,
        "target_object_status": "pending",
    }
    value.update(overrides)
    return value


def test_classify_group_exact_active_pending_is_eligible() -> None:
    decision, ids = tool.classify_group([row()])
    assert decision == "identity_ready_for_accept"
    assert ids == {"object_id": 10, "target_object_id": 20}


def test_classify_group_blocks_missing_and_ambiguous_identity() -> None:
    assert tool.classify_group([{"target_object_id": 20, "target_object_status": "pending"}])[0] == "identity_missing"
    assert tool.classify_group([row(), row(object_id=11)])[0] == "identity_ambiguous"


def test_classify_group_blocks_non_active_object() -> None:
    assert tool.classify_group([row(identity_status="needs_review")])[0] == "object_not_active"


def test_identity_ready_still_synchronizes_candidate_gate() -> None:
    decision, _ = tool.classify_group([row(target_object_status="accepted")])
    assert decision == "identity_ready"
    assert tool.syncs_candidate_identity_gate(decision) is True
    assert tool.syncs_candidate_identity_gate("identity_missing") is False


def test_unique_existing_object_without_target_attachment_is_attachable() -> None:
    groups = {
        1: [row(target_id=220, target_object_id=None, object_identity_key="target|old|person|李绩")],
        2: [row(target_id=220, target_object_id=None, object_identity_key="target|old|person|李绩")],
        3: [row(target_id=220, object_id=11, target_object_id=None)],
    }

    candidates = tool.target_object_attachment_candidates(groups)

    assert [(item["target_id"], item["object_id"]) for item in candidates] == [(220, 10), (220, 11)]


def test_ambiguous_identity_is_not_attachable() -> None:
    groups = {1: [row(target_id=220, target_object_id=None), row(target_id=220, object_id=11, target_object_id=None)]}

    assert tool.target_object_attachment_candidates(groups) == []


def test_identity_gate_resolves_accepted_alias_names() -> None:
    source = Path(tool.__file__).read_text(encoding="utf-8")

    assert "from retrieval_v3.object_names onm" in source
    assert "lower(onm.normalized_name) = lower(mc.object_name)" in source


def test_identity_gate_supports_narrow_source_pack_filter() -> None:
    source = Path(tool.__file__).read_text(encoding="utf-8")

    assert "sp.pack_code = any(%s::text[])" in source
    assert 'parser.add_argument("--source-pack-code", action="append", default=[])' in source
    assert '"--attach-missing-target-objects"' in source
