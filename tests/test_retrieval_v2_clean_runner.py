from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from scripts.dev import retrieval_v2_clean_cli
from scripts.dev import retrieval_v2_clean_runner as tool
from scripts.dev import retrieval_v2_discovery_profiles


def task_with_alias_gap() -> dict:
    return {
        "job_code": "JOB-I5B-ZKY-DELEGATION",
        "target_code": "TGT-I5B-ZKY",
        "emperor_name": "赵匡胤",
        "item_code": "I5B",
        "contract_code": "I5B-RETRIEVAL-V2-20260704",
        "rule_code": "delegation",
        "target_profile": {"primary_name": "赵匡胤", "aliases": ["赵匡胤", "太祖"]},
        "rule": {
            "rule_code": "delegation",
            "keywords": ["命", "参知政事", "委"],
        },
        "object_seeds": [
            {"aliases": [{"text": "呂餘慶", "strength": "strong"}, {"text": "參知政事", "strength": "medium"}]},
        ],
        "source_documents": [
            {
                "document_code": "DOC-SH-001",
                "title": "宋史/fixture",
                "source_kind": "primary_source",
                "text": "太祖命吕余庆参知政事，委以政务。",
            }
        ],
    }


def task_without_alias_gap() -> dict:
    task = task_with_alias_gap()
    task["target_code"] = "TGT-I5B-ZKY-NOGAP"
    task["object_seeds"] = [{"name": "吕余庆", "aliases": [{"alias": "吕余庆", "strength": "strong"}]}]
    return task


def task_for_sharded_judge() -> dict:
    task = task_without_alias_gap()
    task["target_code"] = "TGT-I5B-ZKY-SHARDED"
    task["object_seeds"] = [
        {"name": "吕余庆", "aliases": [{"alias": "吕余庆", "strength": "strong"}]},
        {"name": "赵普", "aliases": [{"alias": "赵普", "strength": "strong"}]},
    ]
    task["source_documents"] = [
        {
            "document_code": "DOC-SH-001",
            "title": "宋史/fixture",
            "source_kind": "primary_source",
            "text": "太祖命吕余庆参知政事，委以政务。太祖命赵普为相，委决国政。",
        }
    ]
    return task


def task_with_candidate_source_gap() -> dict:
    return {
        "job_code": "JOB-I5B-CC-DELEGATION",
        "target_code": "TGT-I5B-CC",
        "emperor_name": "曹操",
        "item_code": "I5B",
        "contract_code": "I5B-RETRIEVAL-V2-20260704",
        "rule_code": "delegation",
        "target_profile": {"primary_name": "曹操", "aliases": ["曹操", "太祖"]},
        "rule": {"rule_code": "delegation", "keywords": ["命", "委"]},
        "coverage_matrix": {
            "rule_code": "delegation",
            "role_families": [
                {"family_code": "strategic_delegate", "target_min_claims": 1, "required_directions": ["positive"]}
            ],
        },
        "object_seeds": [{"name": "荀彧"}],
        "source_documents": [
            {
                "document_code": "DOC-SGZ-001",
                "title": "三國志/卷一",
                "source_kind": "primary_source",
                "text": "太祖起兵。",
            }
        ],
    }


def test_extract_json_accepts_trailing_text() -> None:
    payload = tool.extract_json('{"ok": true, "value": 1}\n补充说明：这里不应影响解析。')

    assert payload == {"ok": True, "value": 1}


def sample_context() -> dict:
    return {
        "target_code": "TGT-I5B-ZKY",
        "emperor_name": "赵匡胤",
        "item_code": "I5B",
        "contract_code": "I5B-RETRIEVAL-V2-20260704",
        "intent_code": "INT-I5B-ZKY-DELEGATION",
        "rule_code": "delegation",
        "rule_label": "合理授权",
        "target_aliases": [{"alias": "赵匡胤", "alias_type": "name", "source": "seed"}],
        "material_policy_payload": [{"policy_code": "person_authority_claim"}],
        "predicate_policy_payload": [{"predicate": "delegated_civil_authority"}],
        "requirement_payload": {
            "coverage_matrix": {
                "rule_code": "delegation",
                "role_families": [
                    {"family_code": "civil_delegate", "target_min_claims": 1, "required_directions": ["positive"]}
                ],
                "secondary_rule_hints": [{"rule_code": "team_building", "reason": "reuse"}],
            }
        },
        "intent_payload": {},
    }


def context_for(name: str, target_code: str) -> dict:
    context = sample_context()
    context["emperor_name"] = name
    context["target_code"] = target_code
    context["intent_code"] = f"INT-{target_code}"
    context["target_aliases"] = [{"alias": name, "alias_type": "name", "source": "seed"}]
    return context


def fake_taskgen(invocation: tool.CodexInvocation) -> tool.CodexResult:
    assert invocation.phase == "taskgen"
    assert invocation.search is True
    assert "task skeleton" in invocation.prompt
    payload = {
        "target_code": "BAD",
        "rule_code": "BAD",
        "target_profile": {"aliases": ["宋太祖"]},
        "rule": {"keywords": ["命", "参知政事"]},
        "object_seeds": [{"name": "吕余庆", "aliases": [{"alias": "呂餘慶", "strength": "strong"}]}],
        "source_documents": [
            {
                "document_code": "DOC-SH-001",
                "title": "宋史/fixture",
                "source_kind": "primary_source",
                "text": "太祖命吕余庆参知政事。",
            }
        ],
        "generation_notes": ["discovered"],
    }
    invocation.last_message.parent.mkdir(parents=True, exist_ok=True)
    invocation.last_message.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    invocation.event_log.write_text(
        '{"type":"turn.completed","usage":{"input_tokens":20,"output_tokens":8}}\n',
        encoding="utf-8",
    )
    return tool.CodexResult(payload=payload, elapsed_seconds=2.0, usage={"input_tokens": 20, "output_tokens": 8})


def fake_batch_taskgen(invocation: tool.CodexInvocation) -> tool.CodexResult:
    assert invocation.phase == "taskgen_batch"
    assert invocation.search is True
    assert "targets" in invocation.prompt
    payload = {
        "targets": [
            {
                "target_code": "TGT-I5B-ZKY",
                "emperor_name": "赵匡胤",
                "target_profile": {"aliases": ["宋太祖"]},
                "rule": {"keywords": ["命", "参知政事"]},
                "object_seeds": [{"name": "吕余庆", "aliases": [{"alias": "吕余庆", "strength": "strong"}]}],
                "source_documents": [
                    {"document_code": "DOC-SH-001", "title": "宋史/fixture", "text": "太祖命吕余庆参知政事。"}
                ],
            },
            {
                "target_code": "TGT-I5B-LB",
                "emperor_name": "刘邦",
                "target_profile": {"aliases": ["汉高祖"]},
                "rule": {"keywords": ["命", "相国"]},
                "object_seeds": [{"name": "萧何", "aliases": [{"alias": "萧何", "strength": "strong"}]}],
                "source_documents": [
                    {"document_code": "DOC-SJ-001", "title": "史记/fixture", "text": "高祖命萧何为相国。"}
                ],
            },
        ]
    }
    invocation.last_message.parent.mkdir(parents=True, exist_ok=True)
    invocation.last_message.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    invocation.event_log.write_text(
        '{"type":"turn.completed","usage":{"input_tokens":30,"output_tokens":12}}\n',
        encoding="utf-8",
    )
    return tool.CodexResult(payload=payload, elapsed_seconds=3.0, usage={"input_tokens": 30, "output_tokens": 12})


def fake_preseeded_taskgen(invocation: tool.CodexInvocation) -> tool.CodexResult:
    assert invocation.phase == "taskgen"
    assert invocation.search is False
    assert "presearch_hits" in invocation.prompt
    payload = {
        "target_profile": {"aliases": ["宋太祖"]},
        "object_seeds": [{"name": "吕余庆", "aliases": [{"alias": "吕余庆", "strength": "strong"}]}],
        "source_documents": [{"document_code": "DOC-BAD", "title": "bad", "text": "bad"}],
        "generation_notes": ["used presearch source documents"],
    }
    invocation.last_message.parent.mkdir(parents=True, exist_ok=True)
    invocation.last_message.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    invocation.event_log.write_text(
        '{"type":"turn.completed","usage":{"input_tokens":12,"output_tokens":4}}\n',
        encoding="utf-8",
    )
    return tool.CodexResult(payload=payload, elapsed_seconds=0.5, usage={"input_tokens": 12, "output_tokens": 4})


def fake_judge(invocation: tool.CodexInvocation) -> tool.CodexResult:
    assert invocation.phase == "judge"
    assert invocation.search is False
    assert invocation.cwd.is_absolute()
    assert invocation.last_message.is_absolute()
    assert invocation.event_log.is_absolute()
    payload = {
        "job_code": "JOB-I5B-ZKY-DELEGATION",
        "status": "succeeded",
        "documents": [{"document_code": "DOC-SH-001", "title": "宋史/fixture", "source_kind": "primary_source"}],
        "passages": [
            {
                "passage_code": "PAS-001",
                "document_code": "DOC-SH-001",
                "slice_code": "SLI-001",
                "locator": "chars:0-20",
                "quote": "太祖命吕余庆参知政事",
                "summary": "赵匡胤任用吕余庆参知政事。",
                "matched_aliases": ["吕余庆"],
            }
        ],
        "claims": [
            {
                "claim_code": "CLM-001",
                "emperor_name": "赵匡胤",
                "object_name": "吕余庆",
                "object_type": "person",
                "claim_kind": "material_claim",
                "claim_summary": "赵匡胤授权吕余庆参与政务。",
                "direction": "positive",
                "confidence": 0.85,
                "source_passage_refs": ["PAS-001"],
                "source_slice_refs": ["SLI-001"],
            }
        ],
        "primary_bindings": [
            {
                "claim_code": "CLM-001",
                "rule_code": "delegation",
                "predicate": "delegated_civil_authority",
                "direction": "positive",
                "object_role": "civil_delegate",
                "usable_for_object_payload": True,
                "usable_for_scoring_cluster": True,
                "confidence": 0.85,
            }
        ],
        "secondary_binding_candidates": [],
        "coverage_matrix": {"rule_code": "delegation", "role_families": []},
        "coverage": {
            "ready_for_object_pool": True,
            "checked_objects": ["吕余庆"],
            "missing_core_objects": [],
            "positive_claim_count": 1,
            "negative_claim_count": 0,
        },
        "coverage_gaps": [],
    }
    invocation.last_message.parent.mkdir(parents=True, exist_ok=True)
    invocation.last_message.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    invocation.event_log.write_text(
        '{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":5}}\n',
        encoding="utf-8",
    )
    return tool.CodexResult(payload=payload, elapsed_seconds=1.25, usage={"input_tokens": 10, "output_tokens": 5})


def fake_shard_judge(invocation: tool.CodexInvocation) -> tool.CodexResult:
    assert invocation.phase == "judge_shard"
    assert invocation.search is False
    prompt = invocation.prompt
    if "吕余庆" in prompt:
        object_name = "吕余庆"
    elif "赵普" in prompt:
        object_name = "赵普"
    else:  # pragma: no cover
        raise AssertionError("shard prompt missing expected object")
    payload = {
        "job_code": "JOB-I5B-ZKY-DELEGATION",
        "status": "succeeded",
        "documents": [{"document_code": "DOC-SH-001", "title": "宋史/fixture", "source_kind": "primary_source"}],
        "passages": [
            {
                "passage_code": "PAS-001",
                "document_code": "DOC-SH-001",
                "slice_code": f"SLI-{object_name}",
                "locator": "chars:0-20",
                "quote": f"太祖命{object_name}",
                "summary": f"赵匡胤任用{object_name}。",
                "matched_aliases": [object_name],
            }
        ],
        "claims": [
            {
                "claim_code": "CLM-001",
                "emperor_name": "赵匡胤",
                "object_name": object_name,
                "object_type": "person",
                "claim_kind": "material_claim",
                "claim_summary": f"赵匡胤授权{object_name}处理政务。",
                "direction": "positive",
                "confidence": 0.8,
                "source_passage_refs": ["PAS-001"],
                "source_slice_refs": [f"SLI-{object_name}"],
            }
        ],
        "primary_bindings": [
            {
                "claim_code": "CLM-001",
                "rule_code": "delegation",
                "predicate": "delegated_civil_authority",
                "direction": "positive",
                "object_role": "civil_delegate",
                "usable_for_object_payload": True,
                "usable_for_scoring_cluster": True,
                "confidence": 0.8,
            }
        ],
        "secondary_binding_candidates": [],
        "coverage_matrix": {"rule_code": "delegation", "role_families": []},
        "coverage": {
            "ready_for_object_pool": True,
            "checked_objects": [object_name],
            "missing_core_objects": [],
            "positive_claim_count": 1,
            "negative_claim_count": 0,
        },
        "coverage_gaps": [],
    }
    invocation.last_message.parent.mkdir(parents=True, exist_ok=True)
    invocation.last_message.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    invocation.event_log.write_text(
        '{"type":"turn.completed","usage":{"input_tokens":11,"output_tokens":7}}\n',
        encoding="utf-8",
    )
    return tool.CodexResult(payload=payload, elapsed_seconds=1.0, usage={"input_tokens": 11, "output_tokens": 7})


def test_run_taskgen_uses_script_skeleton_and_merges_discovery(tmp_path: Path) -> None:
    result = tool.run_taskgen(
        context=sample_context(),
        run_root=tmp_path,
        codex_runner=fake_taskgen,
        codex_bin="codex",
        timeout_seconds=30,
        search=True,
    )

    task = result["task"]
    assert task["target_code"] == "TGT-I5B-ZKY"
    assert task["rule_code"] == "delegation"
    assert task["object_seeds"][0]["name"] == "吕余庆"
    assert "宋太祖" in task["target_profile"]["aliases"]
    assert result["taskgen"]["mode"] == "skeleton_discovery"
    assert Path(result["taskgen"]["files"]["skeleton"]).exists()
    assert Path(result["taskgen"]["files"]["generated_profile"]).exists()


def test_run_codex_ignores_user_config_and_rules_by_default(tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_run(cmd: list[str], **kwargs) -> SimpleNamespace:
        captured["cmd"] = cmd
        last_message = Path(cmd[cmd.index("--output-last-message") + 1])
        last_message.parent.mkdir(parents=True, exist_ok=True)
        last_message.write_text('{"ok": true}', encoding="utf-8")
        return SimpleNamespace(
            returncode=0,
            stdout='{"type":"turn.completed","usage":{"input_tokens":1}}\n',
            stderr="",
        )

    monkeypatch.setattr(tool.subprocess, "run", fake_run)
    result = tool.run_codex(
        tool.CodexInvocation(
            phase="taskgen",
            prompt="{}",
            cwd=tmp_path / "cwd",
            last_message=tmp_path / "last.json",
            event_log=tmp_path / "events.jsonl",
            search=False,
            timeout_seconds=30,
            codex_bin="codex",
        )
    )

    assert result.payload == {"ok": True}
    assert "--ignore-user-config" in captured["cmd"]
    assert "--ignore-rules" in captured["cmd"]
    assert "--search" not in captured["cmd"]
    assert "standalone_web_search" in captured["cmd"]
    assert "browser_use" in captured["cmd"]


def test_run_taskgen_can_preseed_search_documents_before_codex(tmp_path: Path) -> None:
    preseed = {
        "source_documents": [
            {
                "document_code": "DOC-PRE-TGT-I5B-ZKY-01",
                "title": "宋史/fixture",
                "source_kind": "primary_source",
                "text": "太祖命吕余庆参知政事。",
            }
        ],
        "search_plan": {"presearch_hits": [{"query": "宋太祖 宋史", "title": "宋史/fixture"}]},
        "clean_audit": {"taskgen_presearch": True, "presearch_hit_count": 1},
    }

    result = tool.run_taskgen(
        context=sample_context(),
        run_root=tmp_path,
        codex_runner=fake_preseeded_taskgen,
        codex_bin="codex",
        timeout_seconds=30,
        search=False,
        preseed_discovery=preseed,
    )

    assert result["taskgen"]["mode"] == "preseeded_skeleton_discovery"
    assert result["task"]["source_documents"][0]["document_code"] == "DOC-PRE-TGT-I5B-ZKY-01"
    assert all(row.get("document_code") != "DOC-BAD" for row in result["task"]["source_documents"])
    assert Path(result["taskgen"]["files"]["preseed"]).exists()


def test_cli_merges_public_emp_metadata_into_task_target_payload() -> None:
    task = {"target_code": "TGT-I5B-CC", "target_payload": {"seed_source": "retrieval_v2_bootstrap"}}
    result = retrieval_v2_clean_cli._with_emp_metadata_target_payload(
        task,
        {"period": "三國", "title": "魏武帝", "ignored": "x"},
    )

    assert result["target_payload"] == {
        "seed_source": "retrieval_v2_bootstrap",
        "period": "三國",
        "title": "魏武帝",
    }
    assert "ignored" not in result["target_payload"]


def test_cli_object_source_presearch_keeps_emp_metadata_after_normalize(tmp_path: Path, monkeypatch) -> None:
    context = sample_context()
    task = tool.normalize_task_from_context(task_without_alias_gap(), context)
    args = SimpleNamespace(
        taskgen_presearch=True,
        no_taskgen_object_source_presearch=False,
        taskgen_object_source_max_objects=2,
        taskgen_object_source_pages_per_object=1,
        taskgen_presearch_timeout=3,
    )

    monkeypatch.setattr(
        retrieval_v2_clean_cli.taskgen_preseed,
        "expand_task_sources_for_objects",
        lambda task, context, **_: dict(task),
    )
    result = retrieval_v2_clean_cli._expand_object_sources_after_taskgen(
        args=args,
        row={"task": task, "taskgen": {"files": {}}},
        context=context,
        emp_metadata_by_name={"赵匡胤": {"period": "北宋", "title": "宋太祖"}},
        run_root=tmp_path,
        taskgen_search=False,
    )

    assert result["task"]["target_payload"]["period"] == "北宋"
    assert result["task"]["target_payload"]["title"] == "宋太祖"


def test_run_taskgen_can_reuse_discovery_profile_without_codex(tmp_path: Path) -> None:
    def fail_codex(invocation: tool.CodexInvocation) -> tool.CodexResult:
        raise AssertionError("codex should not run when a matching discovery profile is provided")

    profile = {
        "emperor_name": "赵匡胤",
        "rule_code": "delegation",
        "object_seeds": [{"name": "吕余庆", "aliases": [{"alias": "呂餘慶", "strength": "strong"}]}],
        "source_documents": [{"document_code": "DOC-SH-001", "title": "宋史/fixture", "text": "太祖命吕余庆。"}],
    }

    result = tool.run_taskgen(
        context=sample_context(),
        run_root=tmp_path,
        codex_runner=fail_codex,
        codex_bin="codex",
        timeout_seconds=30,
        search=True,
        discovery_profile=profile,
    )

    assert result["taskgen"]["mode"] == "discovery_profile"
    assert result["taskgen"]["elapsed_seconds"] == 0.0
    assert result["task"]["target_code"] == "TGT-I5B-ZKY"


def test_cli_can_reuse_discovery_profile_root(tmp_path: Path, capsys, monkeypatch) -> None:
    profile_root = tmp_path / "profiles"
    run_root = tmp_path / "run"
    profile = retrieval_v2_discovery_profiles.profile_from_task(task_without_alias_gap())
    retrieval_v2_discovery_profiles.write_profile(profile, profile_root)

    monkeypatch.setenv("TEST_RETRIEVAL_V2_DSN", "postgresql://example")
    monkeypatch.setattr(
        tool,
        "fetch_retrieval_contexts",
        lambda **_: {"赵匡胤": sample_context()},
    )

    assert tool.main(
        [
            "--emperor",
            "赵匡胤",
            "--target-dsn-env",
            "TEST_RETRIEVAL_V2_DSN",
            "--discovery-profile-root",
            str(profile_root),
            "--run-root",
            str(run_root),
            "--skip-judge",
        ]
    ) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["people"][0]["taskgen_mode"] == "discovery_profile"
    assert payload["people"][0]["taskgen_elapsed_seconds"] == 0.0
    assert payload["people"][0]["candidate_slices"] == 1


def test_streaming_taskgen_pipeline_writes_events_and_preserves_order(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    event_logger = tool.RunEventLogger(run_root / "run_events.jsonl")
    contexts = {
        "赵匡胤": context_for("赵匡胤", "TGT-I5B-ZKY"),
        "刘邦": context_for("刘邦", "TGT-I5B-LB"),
    }

    summary = tool.run_streaming_taskgen_pipeline(
        contexts=contexts,
        emperor_names=["赵匡胤", "刘邦"],
        loaded_profiles=[],
        allow_cross_rule_discovery_profile=False,
        profile_roots=[],
        run_root=run_root,
        codex_runner=fake_taskgen,
        skip_judge=True,
        max_workers=2,
        event_logger=event_logger,
    )

    assert summary["clean_policy"]["taskgen_streaming"] is True
    assert summary["targets"] == ["赵匡胤", "刘邦"]
    events = [
        json.loads(line)
        for line in (run_root / "run_events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    event_names = [row["event"] for row in events]
    assert event_names.count("taskgen_start") == 2
    assert event_names.count("target_done") == 2
    assert event_names[-1] == "pipeline_done"


def test_streaming_taskgen_pipeline_can_batch_no_profile_targets(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    event_logger = tool.RunEventLogger(run_root / "run_events.jsonl")
    contexts = {
        "赵匡胤": context_for("赵匡胤", "TGT-I5B-ZKY"),
        "刘邦": context_for("刘邦", "TGT-I5B-LB"),
    }

    summary = tool.run_streaming_taskgen_pipeline(
        contexts=contexts,
        emperor_names=["赵匡胤", "刘邦"],
        loaded_profiles=[],
        allow_cross_rule_discovery_profile=False,
        profile_roots=[],
        run_root=run_root,
        codex_runner=fake_batch_taskgen,
        skip_judge=True,
        max_workers=2,
        taskgen_batch_size=2,
        event_logger=event_logger,
    )

    assert summary["clean_policy"]["taskgen_batch_size"] == 2
    assert [row["taskgen_mode"] for row in summary["people"]] == [
        "batch_skeleton_discovery",
        "batch_skeleton_discovery",
    ]
    assert summary["totals"]["usage"] == {"input_tokens": 30, "output_tokens": 12}
    events = [
        json.loads(line)
        for line in (run_root / "run_events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [row["event"] for row in events].count("taskgen_batch_start") == 1
    assert [row["event"] for row in events].count("taskgen_start") == 0


def test_streaming_taskgen_pipeline_uses_presearch_before_batching(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    event_logger = tool.RunEventLogger(run_root / "run_events.jsonl")
    contexts = {
        "赵匡胤": context_for("赵匡胤", "TGT-I5B-ZKY"),
        "刘邦": context_for("刘邦", "TGT-I5B-LB"),
    }
    preseeds = {
        name: {
            "source_documents": [
                {
                    "document_code": f"DOC-PRE-{context['target_code']}-01",
                    "title": "宋史/fixture",
                    "source_kind": "primary_source",
                    "text": "太祖命吕余庆参知政事。",
                }
            ],
            "search_plan": {"presearch_hits": [{"query": f"{name} 宋史", "title": "宋史/fixture"}]},
            "clean_audit": {"taskgen_presearch": True, "presearch_hit_count": 1},
        }
        for name, context in contexts.items()
    }

    summary = tool.run_streaming_taskgen_pipeline(
        contexts=contexts,
        emperor_names=["赵匡胤", "刘邦"],
        loaded_profiles=[],
        allow_cross_rule_discovery_profile=False,
        profile_roots=[],
        run_root=run_root,
        codex_runner=fake_preseeded_taskgen,
        skip_judge=True,
        max_workers=2,
        taskgen_batch_size=2,
        taskgen_search=False,
        taskgen_preseeds=preseeds,
        event_logger=event_logger,
    )

    assert summary["clean_policy"]["taskgen_presearch"] is True
    assert summary["clean_policy"]["taskgen_search_enabled"] is False
    assert [row["taskgen_mode"] for row in summary["people"]] == [
        "preseeded_skeleton_discovery",
        "preseeded_skeleton_discovery",
    ]
    events = [
        json.loads(line)
        for line in (run_root / "run_events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [row["event"] for row in events].count("taskgen_preseed_applied") == 2
    assert [row["event"] for row in events].count("taskgen_batch_start") == 0


def test_streaming_taskgen_pipeline_isolates_single_target_failure(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    event_logger = tool.RunEventLogger(run_root / "run_events.jsonl")
    contexts = {
        "赵匡胤": context_for("赵匡胤", "TGT-I5B-ZKY"),
        "刘邦": context_for("刘邦", "TGT-I5B-LB"),
    }

    def flaky_taskgen(invocation: tool.CodexInvocation) -> tool.CodexResult:
        if "刘邦" in invocation.prompt:
            raise tool.RetrievalV2CleanRunnerError("boom")
        return fake_taskgen(invocation)

    summary = tool.run_streaming_taskgen_pipeline(
        contexts=contexts,
        emperor_names=["赵匡胤", "刘邦"],
        loaded_profiles=[],
        allow_cross_rule_discovery_profile=False,
        profile_roots=[],
        run_root=run_root,
        codex_runner=flaky_taskgen,
        skip_judge=True,
        max_workers=2,
        event_logger=event_logger,
    )

    assert summary["people"][0]["name"] == "赵匡胤"
    assert summary["people"][0]["candidate_slices"] == 1
    assert summary["people"][1]["name"] == "刘邦"
    assert summary["people"][1]["status"] == "failed"
    assert summary["people"][1]["failed_stage"] == "taskgen"
    events = [
        json.loads(line)
        for line in (run_root / "run_events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert any(row["event"] == "target_failed" and row["emperor_name"] == "刘邦" for row in events)


def test_clean_pipeline_matches_script_variant_before_judge(tmp_path: Path) -> None:
    summary = tool.run_clean_pipeline(
        tasks=[task_with_alias_gap()],
        run_root=tmp_path,
        codex_runner=fake_judge,
        skip_judge=False,
        max_alias_refine_rounds=2,
        max_workers=1,
    )

    person = summary["people"][0]
    assert person["round_count"] == 1
    assert person["rounds"][0]["candidate_alias_patch_stats"]["apply_alias_patch_count"] == 0
    assert person["objects_without_slices"] == []
    assert person["judge_status"] == "succeeded"
    assert person["claim_count"] == 1
    assert summary["totals"]["usage"] == {"input_tokens": 10, "output_tokens": 5}
    final_candidates = json.loads(Path(person["files"]["final_candidates"]).read_text(encoding="utf-8"))
    assert "吕余庆" in final_candidates["candidate_slices"][0]["matched_aliases"]


def test_clean_pipeline_auto_refines_candidate_source_gaps(tmp_path: Path, monkeypatch) -> None:
    queries: list[str] = []

    def fake_search(query: str, *, limit: int, timeout: int) -> list[dict]:
        queries.append(query)
        assert limit == 1
        return [
            {
                "title": "三國志/卷十",
                "url": "https://example.test/sgz10",
                "snippet": "荀彧",
                "text": "太祖命荀彧为司马，委以军国之事。",
            }
        ]

    monkeypatch.setattr(tool.candidate_source_refiner, "search_wikisource", fake_search)
    summary = tool.run_clean_pipeline(
        tasks=[task_with_candidate_source_gap()],
        run_root=tmp_path,
        skip_judge=True,
        max_alias_refine_rounds=0,
        candidate_source_refine_rounds=1,
        candidate_source_refine_max_objects=4,
        candidate_source_refine_pages_per_object=1,
        max_workers=1,
    )

    person = summary["people"][0]
    assert queries == ["荀彧 三國志"]
    assert person["round_count"] == 2
    assert person["rounds"][0]["candidate_source_refine_stats"]["added_source_document_count"] == 1
    assert person["candidate_slices"] == 1
    assert person["objects_without_slices"] == []
    assert summary["clean_policy"]["candidate_source_refine_rounds"] == 1


def test_clean_pipeline_can_judge_object_shards_and_merge_ids(tmp_path: Path) -> None:
    summary = tool.run_clean_pipeline(
        tasks=[task_for_sharded_judge()],
        run_root=tmp_path,
        codex_runner=fake_shard_judge,
        skip_judge=False,
        max_alias_refine_rounds=0,
        max_slices_per_object=1,
        judge_shard_size=1,
        judge_shard_workers=2,
        max_workers=1,
    )

    person = summary["people"][0]
    result = json.loads(Path(person["files"]["final_judge_result"]).read_text(encoding="utf-8"))
    claim_codes = [row["claim_code"] for row in result["claims"]]
    passage_codes = [row["passage_code"] for row in result["passages"]]
    assert person["judge_sharded"] is True
    assert person["judge_shard_count"] == 2
    assert person["claim_count"] == 2
    assert len(set(claim_codes)) == 2
    assert len(set(passage_codes)) == 2
    assert all(code.startswith("JSH-R00-") for code in claim_codes)
    assert all(binding["claim_code"] in claim_codes for binding in result["primary_bindings"])
    assert summary["totals"]["usage"] == {"input_tokens": 22, "output_tokens": 14}


def test_cli_skip_judge_runs_candidate_and_summary(tmp_path: Path, capsys) -> None:
    task_path = tmp_path / "task.json"
    run_root = tmp_path / "run"
    task_path.write_text(json.dumps(task_without_alias_gap(), ensure_ascii=False), encoding="utf-8")

    assert tool.main(["--task", str(task_path), "--run-root", str(run_root), "--skip-judge"]) == 0

    out = capsys.readouterr().out
    payload = json.loads(out)
    summary_path = run_root / "summary.json"
    assert summary_path.exists()
    assert payload["ok"] is True
    assert payload["cli_elapsed_seconds"] >= payload["elapsed_seconds"]
    assert payload["people"][0]["judge_status"] is None
    assert payload["people"][0]["candidate_slices"] == 1
    assert payload["clean_policy"]["candidate_alias_missing_auto_patch"] is True
