from __future__ import annotations

from scripts.dev import retrieval_v3_scoring_runner as tool


def manifest() -> dict:
    return {
        "item_code": "I5B",
        "rule_code": "appointment_delegation",
        "formula_code": "evidence_cluster_signal_v3",
        "targets": [{
            "emperor_name": "甲",
            "target_code": "TGT-A",
            "source_pack_codes": ["SPK-BASE", "SPK-CACHE", "SPK-BASE"],
        }],
    }


def test_validate_manifest_deduplicates_pack_codes() -> None:
    result = tool.validate_manifest(manifest())

    assert result["scope_code"] == "I5B__appointment_delegation"
    assert result["targets"][0]["source_pack_codes"] == ["SPK-BASE", "SPK-CACHE"]


def test_validate_manifest_rejects_duplicate_emperor() -> None:
    value = manifest()
    value["targets"].append({
        "emperor_name": "甲", "target_code": "TGT-B", "source_pack_codes": ["SPK-B"]})

    try:
        tool.validate_manifest(value)
    except tool.ScoringRunnerError as exc:
        assert "duplicate emperor or target" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected duplicate target rejection")


def test_score_summary_requires_exact_target() -> None:
    payload = {"clusters": [{"target_code": "TGT-A", "positive_signal": "1.000"}]}

    assert tool.score_summary(payload, "TGT-A")["positive_signal"] == "1.000"


def test_parser_is_read_only_by_default() -> None:
    args = tool.build_parser().parse_args([
        "--manifest", "manifest.json", "--output-root", "tmp/run"])

    assert args.execute_scorer is False


def test_read_only_unchanged_contract_uses_input_fingerprint(monkeypatch, tmp_path) -> None:
    current = tool.validate_manifest(manifest())
    fingerprint = "A" * 64
    previous = {
        "manifest_fingerprint": tool.stable_hash(current, length=64),
        "targets": [{
            "target_code": "TGT-A",
            "input_fingerprint": fingerprint,
            "score": {"target_code": "TGT-A", "positive_signal": "1.000"},
        }],
    }
    previous_root = tmp_path / "previous"
    previous_root.mkdir()
    previous_report = previous_root / "report.json"
    previous_report.write_text(tool.json.dumps(previous), encoding="utf-8")
    (previous_root / "score_details.json").write_text(tool.json.dumps({
        "TGT-A": {
            "emperor_name": "甲",
            "calc_detail": {
                "materials": [{
                    "claim_key": "CLM-A", "event_group_keys": ["EG-A"],
                    "source_document_codes": ["DOC-A"],
                }],
                "object_side_scores": {"positive": {"1": {}}, "negative": {}},
            },
        },
    }), encoding="utf-8")
    monkeypatch.setattr(tool, "input_snapshot", lambda **kwargs: {
        "input_fingerprint": fingerprint,
        "judgment_count": 1,
        "score_judgment_count": 1,
        "supporting_judgment_count": 0,
        "exclude_judgment_count": 0,
    })
    monkeypatch.setattr(tool, "apply_rule_scores", lambda **kwargs: (_ for _ in ()).throw(AssertionError("scorer called")))
    monkeypatch.setattr(tool, "fetch_coverage_contract", lambda **kwargs: [{}])
    def fake_run_contract(**kwargs):
        scope = kwargs["output_root"] / "I5B__appointment_delegation.json"
        scope.parent.mkdir(parents=True, exist_ok=True)
        scope.write_text('{"objects": []}', encoding="utf-8")
        return {"ok": True}

    monkeypatch.setattr(tool, "run_contract", fake_run_contract)

    report = tool.run(
        dsn="postgresql://unused",
        schema_name="retrieval_v3",
        manifest=current,
        output_root=tmp_path / "current",
        previous_report_path=previous_report,
    )

    assert report["dirty_target_count"] == 0
    assert report["skipped_target_count"] == 1
    assert report["targets"][0]["status"] == "skipped_unchanged"
    assert report["operational_score_ready"] is True
