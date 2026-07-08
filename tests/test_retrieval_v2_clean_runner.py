from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.dev import retrieval_v2_clean_cli
from scripts.dev import retrieval_v2_clean_runner as tool
from scripts.dev import retrieval_v2_discovery_profiles
from scripts.dev import retrieval_v2_source_candidates


def task_with_alias_gap() -> dict:
    return {
        "job_code": "JOB-I5B-ZKY-APPOINTMENT-DELEGATION",
        "target_code": "TGT-I5B-ZKY",
        "emperor_name": "赵匡胤",
        "item_code": "I5B",
        "contract_code": "I5B-RETRIEVAL-V2-20260704",
        "rule_code": "appointment_delegation",
        "target_profile": {"primary_name": "赵匡胤", "aliases": ["赵匡胤", "太祖"]},
        "rule": {
            "rule_code": "appointment_delegation",
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
        "job_code": "JOB-I5B-CC-APPOINTMENT-DELEGATION",
        "target_code": "TGT-I5B-CC",
        "emperor_name": "曹操",
        "item_code": "I5B",
        "contract_code": "I5B-RETRIEVAL-V2-20260704",
        "rule_code": "appointment_delegation",
        "target_profile": {"primary_name": "曹操", "aliases": ["曹操", "太祖"]},
        "rule": {"rule_code": "appointment_delegation", "keywords": ["命", "委"]},
        "coverage_matrix": {
            "rule_code": "appointment_delegation",
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


def task_with_external_source_refine_object() -> dict:
    task = task_without_alias_gap()
    task["coverage_matrix"] = {
        "rule_code": "appointment_delegation",
        "role_families": [
            {"family_code": "civil_delegate", "target_min_claims": 1, "required_directions": ["positive"]}
        ],
    }
    task["source_documents"] = [
        {
            "document_code": "DOC-SH-001",
            "title": "宋史/fixture",
            "source_kind": "primary_source",
            "text": "太祖命吕余庆参知政事，委以政务。",
        }
    ]
    return task


def test_extract_json_accepts_trailing_text() -> None:
    payload = tool.extract_json('{"ok": true, "value": 1}\n补充说明：这里不应影响解析。')

    assert payload == {"ok": True, "value": 1}


def sample_context() -> dict:
    return {
        "target_code": "TGT-I5B-ZKY",
        "emperor_name": "赵匡胤",
        "item_code": "I5B",
        "contract_code": "I5B-RETRIEVAL-V2-20260704",
        "intent_code": "INT-I5B-ZKY-APPOINTMENT-DELEGATION",
        "rule_code": "appointment_delegation",
        "rule_label": "任用授权质量",
        "target_aliases": [{"alias": "赵匡胤", "alias_type": "name", "source": "seed"}],
        "material_policy_payload": [{"policy_code": "person_authority_claim"}],
        "predicate_policy_payload": [{"predicate": "delegated_civil_authority"}],
        "requirement_payload": {
            "coverage_matrix": {
                "rule_code": "appointment_delegation",
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
        "job_code": "JOB-I5B-ZKY-APPOINTMENT-DELEGATION",
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
                "rule_code": "appointment_delegation",
                "predicate": "delegated_civil_authority",
                "direction": "positive",
                "object_role": "civil_delegate",
                "usable_for_object_payload": True,
                "usable_for_scoring_cluster": True,
                "confidence": 0.85,
            }
        ],
        "secondary_binding_candidates": [],
        "coverage_matrix": {"rule_code": "appointment_delegation", "role_families": []},
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
        "job_code": "JOB-I5B-ZKY-APPOINTMENT-DELEGATION",
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
                "rule_code": "appointment_delegation",
                "predicate": "delegated_civil_authority",
                "direction": "positive",
                "object_role": "civil_delegate",
                "usable_for_object_payload": True,
                "usable_for_scoring_cluster": True,
                "confidence": 0.8,
            }
        ],
        "secondary_binding_candidates": [],
        "coverage_matrix": {"rule_code": "appointment_delegation", "role_families": []},
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
    assert task["rule_code"] == "appointment_delegation"
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


def test_run_codex_uses_server_env_bin_sandbox_and_add_dirs(tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, list[str]] = {}
    extra_dir = tmp_path / "runtime"

    def fake_run(cmd: list[str], **kwargs) -> SimpleNamespace:
        captured["cmd"] = cmd
        last_message = Path(cmd[cmd.index("--output-last-message") + 1])
        last_message.parent.mkdir(parents=True, exist_ok=True)
        last_message.write_text('{"ok": true}', encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setenv(tool.CODEX_BIN_ENV, "/home/penghao/.local/bin/codex")
    monkeypatch.setenv(tool.CODEX_SANDBOX_ENV, "workspace-write")
    monkeypatch.setenv(tool.CODEX_ADD_DIRS_ENV, str(extra_dir))
    monkeypatch.setattr(tool.subprocess, "run", fake_run)

    tool.run_codex(
        tool.CodexInvocation(
            phase="judge",
            prompt="{}",
            cwd=tmp_path / "cwd",
            last_message=tmp_path / "last.json",
            event_log=tmp_path / "events.jsonl",
            search=False,
            timeout_seconds=30,
            codex_bin="codex",
        )
    )

    assert captured["cmd"][0] == "/home/penghao/.local/bin/codex"
    assert captured["cmd"][captured["cmd"].index("-s") + 1] == "workspace-write"
    add_dirs = [
        Path(captured["cmd"][index + 1])
        for index, value in enumerate(captured["cmd"])
        if value == "--add-dir"
    ]
    assert (tmp_path / "cwd").resolve() in add_dirs
    assert extra_dir.resolve() in add_dirs


def test_codex_bin_keeps_explicit_binary(monkeypatch) -> None:
    monkeypatch.setenv(tool.CODEX_BIN_ENV, "/home/penghao/.local/bin/codex")
    invocation = tool.CodexInvocation(
        phase="judge",
        prompt="{}",
        cwd=Path("."),
        last_message=Path("last.json"),
        event_log=Path("events.jsonl"),
        search=False,
        timeout_seconds=30,
        codex_bin="/opt/codex/bin/codex",
    )

    assert tool._codex_bin(invocation) == "/opt/codex/bin/codex"


def test_codex_bin_resolves_from_path_when_default(monkeypatch) -> None:
    monkeypatch.delenv(tool.CODEX_BIN_ENV, raising=False)
    monkeypatch.setattr(tool.shutil, "which", lambda name: "/usr/local/bin/codex" if name == "codex" else None)
    invocation = tool.CodexInvocation(
        phase="judge",
        prompt="{}",
        cwd=Path("."),
        last_message=Path("last.json"),
        event_log=Path("events.jsonl"),
        search=False,
        timeout_seconds=30,
        codex_bin="codex",
    )

    assert tool._codex_bin(invocation) == "/usr/local/bin/codex"


def test_codex_bin_falls_back_to_user_local_bin(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv(tool.CODEX_BIN_ENV, raising=False)
    monkeypatch.setattr(tool.shutil, "which", lambda name: None)
    monkeypatch.setattr(tool.Path, "home", staticmethod(lambda: tmp_path))
    codex_bin = tmp_path / ".local" / "bin" / "codex"
    codex_bin.parent.mkdir(parents=True)
    codex_bin.write_text("#!/usr/bin/env node\n", encoding="utf-8")
    invocation = tool.CodexInvocation(
        phase="judge",
        prompt="{}",
        cwd=Path("."),
        last_message=Path("last.json"),
        event_log=Path("events.jsonl"),
        search=False,
        timeout_seconds=30,
        codex_bin="codex",
    )

    assert tool._codex_bin(invocation) == str(codex_bin)


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


def test_run_taskgen_accepts_presearch_backed_taskgen_documents_when_preseed_empty(tmp_path: Path) -> None:
    def fake_taskgen_with_presearch_doc(invocation: tool.CodexInvocation) -> tool.CodexResult:
        payload = {
            "target_profile": {"aliases": ["后唐明宗"]},
            "object_seeds": [
                {
                    "name": "安重诲",
                    "source_document_codes": ["SD-ZZTJ-274"],
                }
            ],
            "source_documents": [
                {
                    "document_code": "SD-ZZTJ-274",
                    "title": "資治通鑑(四部叢刊本)/卷第二百七十四",
                    "wikisource_title": "資治通鑑(四部叢刊本)/卷第二百七十四",
                    "url": "https://zh.wikisource.org/zh-hans/%E8%B3%87%E6%B2%BB%E9%80%9A%E9%91%91/%E5%8D%B7274",
                },
                {"document_code": "DOC-BAD", "title": "bad", "url": "https://example.test/bad"},
            ],
        }
        invocation.last_message.parent.mkdir(parents=True, exist_ok=True)
        invocation.last_message.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        invocation.event_log.write_text(
            '{"type":"turn.completed","usage":{"input_tokens":12,"output_tokens":4}}\n',
            encoding="utf-8",
        )
        return tool.CodexResult(payload=payload, elapsed_seconds=0.5, usage={"input_tokens": 12, "output_tokens": 4})

    preseed = {
        "source_documents": [],
        "search_plan": {
            "presearch_hits": [
                {
                    "query": "李嗣源 資治通鑑",
                    "title": "資治通鑑(四部叢刊本)/卷第二百七十四",
                    "url": "https://zh.wikisource.org/zh-hans/%E8%B3%87%E6%B2%BB%E9%80%9A%E9%91%91/%E5%8D%B7274",
                    "rejected_reason": "source_root_mismatch",
                }
            ]
        },
        "clean_audit": {"taskgen_presearch": True, "presearch_hit_count": 1},
    }
    context = context_for("李嗣源", "TGT-I5B-LSY")

    result = tool.run_taskgen(
        context=context,
        run_root=tmp_path,
        codex_runner=fake_taskgen_with_presearch_doc,
        codex_bin="codex",
        timeout_seconds=30,
        search=False,
        preseed_discovery=preseed,
    )

    assert [row["document_code"] for row in result["task"]["source_documents"]] == ["SD-ZZTJ-274"]


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


def test_cli_loads_query_profile_metadata_for_missing_public_emp() -> None:
    metadata = retrieval_v2_clean_cli._load_query_profile_metadata(["刘娥"])

    assert "宋史 本纪与列传" in metadata["刘娥"]["source_targets"]
    assert metadata["刘娥"]["retrieval_profile_source_group"] == "all_monarch_backfill"


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
        "rule_code": "appointment_delegation",
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


def test_clean_pipeline_judges_when_candidate_alias_budget_is_zero(tmp_path: Path, monkeypatch) -> None:
    def fake_alias_round(**kwargs) -> dict:
        stage = kwargs["stage"]
        stats = {
            "gap_count": 1,
            "patch_count": 1 if stage == "candidate" else 0,
            "apply_alias_patch_count": 1 if stage == "candidate" else 0,
            "added_alias_count": 1 if stage == "candidate" else 0,
            "cli_alias_refiner_count": 0,
        }
        return {
            "payload": {"stats": stats, "patches": [{"object_name": "吕余庆", "aliases": ["吕余庆"]}]},
            "output_path": tmp_path / f"alias_patch.{stage}.json",
            "prompt_path": None,
        }

    monkeypatch.setattr(tool, "build_alias_refinement_round", fake_alias_round)
    summary = tool.run_clean_pipeline(
        tasks=[task_without_alias_gap()],
        run_root=tmp_path,
        codex_runner=fake_judge,
        skip_judge=False,
        max_alias_refine_rounds=0,
        max_workers=1,
    )

    person = summary["people"][0]
    assert person["alias_round_limit_reached"] is True
    assert person["round_count"] == 1
    assert person["judge_status"] == "succeeded"
    assert person["rounds"][0]["candidate_alias_patch_stats"]["apply_alias_patch_count"] == 1


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


def test_clean_pipeline_overlays_object_source_cache_before_candidates(tmp_path: Path) -> None:
    cache_root = tmp_path / "object_cache"
    cache_root.mkdir()
    (cache_root / "source_documents.jsonl").write_text(
        json.dumps(
            {
                "document_cache_code": "OSD-LYQ",
                "person_cache_code": "PSC-LYQ",
                "person_name": "吕余庆",
                "source_title": "宋史/卷999",
                "wikisource_title": "宋史/卷999",
                "source_kind": "wikisource_page",
                "source_role": "object_biography_or_mentions",
                "source_shape": "object_biography_candidate",
                "mention_slice_count": 1,
                "text_chars": 120,
                "source_key": "wikisource:宋史/卷999",
                "shared_cache_text_path": str(tmp_path / "source_cache" / "dummy.txt"),
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    source_cache = tmp_path / "source_cache"
    retrieval_v2_source_candidates.write_cached_text(
        source_cache,
        "wikisource:宋史/卷999",
        "太祖命吕余庆参知政事，委以政务。吕余庆传。",
        {"cache_status": "test", "source_kind": "wikisource", "source_key": "wikisource:宋史/卷999"},
    )

    summary = tool.run_clean_pipeline(
        tasks=[task_without_alias_gap()],
        run_root=tmp_path / "run",
        skip_judge=True,
        max_alias_refine_rounds=0,
        source_cache_root=source_cache,
        object_source_cache_root=cache_root,
        max_workers=1,
    )

    person = summary["people"][0]
    final_task = json.loads(Path(person["files"]["final_task"]).read_text(encoding="utf-8"))
    final_candidates = json.loads(Path(person["files"]["final_candidates"]).read_text(encoding="utf-8"))
    overlay = json.loads((Path(person["run_dir"]) / "object_source_cache_overlay.json").read_text(encoding="utf-8"))

    assert overlay["stats"]["added_source_document_count"] == 1
    assert any(row["title"] == "宋史/卷999" for row in final_task["source_documents"])
    assert any(row["title"] == "宋史/卷999" for row in final_candidates["source_documents"])
    assert person["objects_without_slices"] == []


def test_clean_pipeline_refines_external_source_gap_objects(tmp_path: Path, monkeypatch) -> None:
    queries: list[str] = []

    def fake_search(query: str, *, limit: int, timeout: int) -> list[dict]:
        queries.append(query)
        return [
            {
                "title": "宋史/卷十",
                "url": "https://example.test/sh10",
                "snippet": "吕余庆",
                "text": "太祖命吕余庆参知政事，委以政务。",
            }
        ]

    monkeypatch.setattr(tool.candidate_source_refiner, "search_wikisource", fake_search)
    summary = tool.run_clean_pipeline(
        tasks=[task_with_external_source_refine_object()],
        run_root=tmp_path,
        skip_judge=True,
        max_alias_refine_rounds=0,
        candidate_source_refine_rounds=1,
        candidate_source_refine_max_objects=4,
        candidate_source_refine_pages_per_object=1,
        candidate_source_refine_objects=["吕余庆"],
        max_workers=1,
    )

    person = summary["people"][0]
    assert "吕余庆 宋史" in queries
    assert all(query.endswith(" 宋史") for query in queries)
    assert person["round_count"] == 2
    assert person["rounds"][0]["candidate_coverage_gap_count"] == 0
    assert person["rounds"][0]["candidate_source_refine_stats"]["gap_object_names"] == ["吕余庆"]
    assert person["rounds"][0]["candidate_source_refine_stats"]["added_source_document_count"] == 1


def test_clean_pipeline_refines_judge_source_gap_objects(tmp_path: Path, monkeypatch) -> None:
    queries: list[str] = []
    judge_calls: list[str] = []

    def fake_search(query: str, *, limit: int, timeout: int) -> list[dict]:
        queries.append(query)
        return [
            {
                "title": "宋史/卷十",
                "url": "https://example.test/sh10",
                "snippet": "吕余庆",
                "text": "太祖命吕余庆参知政事，委以政务。",
            }
        ]

    def judge_needs_refine_once(invocation: tool.CodexInvocation) -> tool.CodexResult:
        judge_calls.append(invocation.phase)
        needs_refine = len(judge_calls) == 1
        payload = {
            "job_code": "JOB-I5B-ZKY-APPOINTMENT-DELEGATION",
            "status": "needs_refinement" if needs_refine else "succeeded",
            "documents": [],
            "passages": [],
            "claims": [],
            "primary_bindings": [],
            "secondary_binding_candidates": [],
            "coverage_matrix": {"rule_code": "appointment_delegation", "role_families": []},
            "coverage": {"ready_for_object_pool": not needs_refine, "checked_objects": ["吕余庆"]},
            "coverage_gaps": [
                {"gap_type": "predicate_missing", "object_name": "吕余庆", "family_code": "civil_delegate"}
            ]
            if needs_refine
            else [],
        }
        invocation.last_message.parent.mkdir(parents=True, exist_ok=True)
        invocation.last_message.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        invocation.event_log.write_text('{"type":"turn.completed","usage":{"input_tokens":9}}\n', encoding="utf-8")
        return tool.CodexResult(payload=payload, elapsed_seconds=1.0, usage={"input_tokens": 9})

    monkeypatch.setattr(tool.candidate_source_refiner, "search_wikisource", fake_search)
    summary = tool.run_clean_pipeline(
        tasks=[task_with_external_source_refine_object()],
        run_root=tmp_path,
        codex_runner=judge_needs_refine_once,
        skip_judge=False,
        max_alias_refine_rounds=0,
        candidate_source_refine_rounds=1,
        candidate_source_refine_pages_per_object=1,
        max_workers=1,
    )

    person = summary["people"][0]
    final_task = json.loads(Path(person["files"]["final_task"]).read_text(encoding="utf-8"))
    assert judge_calls == ["judge", "judge"]
    assert "吕余庆 宋史" in queries
    assert person["round_count"] == 2
    assert person["judge_status"] == "succeeded"
    assert person["rounds"][0]["candidate_source_refine_stats"]["stage"] == "judge"
    assert "task.judge_source_refine.round0.json" in person["rounds"][0]["candidate_source_refine_task"]
    assert final_task["search_plan"]["judge_gap_source_presearch"]["gap_object_names"] == ["吕余庆"]


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


def test_clean_pipeline_can_run_claim_only_judge_mode(tmp_path: Path) -> None:
    def fake_claim_only_judge(invocation: tool.CodexInvocation) -> tool.CodexResult:
        assert invocation.phase == "judge"
        assert "本轮只抽取 claim" in invocation.prompt
        assert "不要输出 primary_bindings" in invocation.prompt
        assert '"secondary_binding_candidates": []' in invocation.prompt
        assert "appointment_delegation scoring candidate 硬协议" not in invocation.prompt
        payload = {
            "job_code": "JOB-I5B-ZKY-CLAIM-ONLY",
            "status": "succeeded",
            "documents": [],
            "passages": [],
            "claims": [
                {
                    "claim_code": "CLM-001",
                    "emperor_name": "赵匡胤",
                    "object_name": "吕余庆",
                    "object_type": "person",
                    "claim_kind": "material_claim",
                    "claim_summary": "赵匡胤任吕余庆参知政事。",
                    "direction": "positive",
                    "confidence": 0.8,
                    "source_slice_refs": ["SLI-001"],
                }
            ],
            "primary_bindings": [],
            "secondary_binding_candidates": [],
            "coverage_matrix": {"rule_code": "appointment_delegation", "role_families": []},
            "coverage": {
                "ready_for_object_pool": False,
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
            '{"type":"turn.completed","usage":{"input_tokens":8,"output_tokens":3}}\n',
            encoding="utf-8",
        )
        return tool.CodexResult(payload=payload, elapsed_seconds=0.5, usage={"input_tokens": 8, "output_tokens": 3})

    summary = tool.run_clean_pipeline(
        tasks=[task_without_alias_gap()],
        run_root=tmp_path,
        codex_runner=fake_claim_only_judge,
        skip_judge=False,
        max_alias_refine_rounds=0,
        judge_shard_size=0,
        judge_mode=tool.candidate_prompt.CLAIM_EXTRACTION_ONLY_MODE,
        max_workers=1,
    )

    person = summary["people"][0]
    result = json.loads(Path(person["files"]["final_judge_result"]).read_text(encoding="utf-8"))
    assert summary["clean_policy"]["judge_mode"] == "claim_extraction_only"
    assert result["_judge_mode"] == "claim_extraction_only"
    assert result["claims"]
    assert result["primary_bindings"] == []
    assert result["secondary_binding_candidates"] == []


def test_clean_pipeline_can_skip_cached_claim_slices_and_import_new_claims(tmp_path: Path, monkeypatch) -> None:
    cached_slice = {
        "slice_code": "SLI-CACHED",
        "document_code": "DOC-001",
        "object_name": "汤和",
        "text": "帝命汤和守常州，常州安辑。",
    }
    new_slice = {
        "slice_code": "SLI-NEW",
        "document_code": "DOC-001",
        "object_name": "常遇春",
        "text": "帝命常遇春进兵，克敌。",
    }
    cache_root = tmp_path / "claim_cache"
    cached_hash = tool.claim_cache.slice_hash_from_row(cached_slice)
    tool.claim_cache.write_jsonl(
        cache_root / "claim_evidence.jsonl",
        [{"evidence_key": "EVD-CACHED", "claim_key": "CLMK-CACHED", "slice_hash": cached_hash}],
    )
    tool.claim_cache.write_jsonl(
        cache_root / "claims.jsonl",
        [
            {
                "claim_key": "CLMK-CACHED",
                "emperor_name": "朱元璋",
                "object_name": "汤和",
                "object_type": "person",
                "claim_kind": "material_claim",
                "claim_summary": "朱元璋命汤和镇守常州。",
                "direction": "positive",
                "action_type": "授权",
                "fact_payload": {
                    "actor": "朱元璋",
                    "object": "汤和",
                    "action_type": "授权",
                    "event_scope": "军事",
                    "office_or_domain": "常州镇守",
                    "outcome": "常州安辑",
                },
                "seen_count": 1,
            }
        ],
    )
    tool.claim_cache.write_jsonl(
        cache_root / "source_slices.jsonl",
        [{"slice_hash": cached_hash, "object_name": "汤和", "seen_count": 1}],
    )

    def fake_candidate_round(**kwargs) -> dict:
        person_dir = kwargs["person_dir"]
        prompt_path = person_dir / "judge_prompt.round0.md"
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text("placeholder", encoding="utf-8")
        return {
            "payload": {
                "task_identity": {"emperor_name": "朱元璋", "rule_code": "i5b_item_wide"},
                "target_profile": {"primary_name": "朱元璋"},
                "rule": {"rule_code": "i5b_item_wide"},
                "object_seeds": [{"name": "汤和"}, {"name": "常遇春"}],
                "source_documents": [{"document_code": "DOC-001", "title": "fixture"}],
                "candidate_slices": [cached_slice, new_slice],
                "coverage_gaps": [],
                "fetch_errors": [],
                "stats": {"candidate_slices": 2},
            },
            "elapsed_seconds": 0.01,
            "output_path": person_dir / "candidates.round0.json",
            "prompt_path": prompt_path,
        }

    def fake_claim_only_judge(invocation: tool.CodexInvocation) -> tool.CodexResult:
        assert "SLI-NEW" in invocation.prompt
        assert "SLI-CACHED" not in invocation.prompt
        payload = {
            "job_code": "JOB-CLAIM-CACHE",
            "status": "succeeded",
            "documents": [],
            "passages": [],
            "claims": [
                {
                    "claim_code": "CLM-NEW",
                    "emperor_name": "朱元璋",
                    "object_name": "常遇春",
                    "object_type": "person",
                    "claim_kind": "material_claim",
                    "claim_summary": "朱元璋命常遇春进兵并克敌。",
                    "direction": "positive",
                    "confidence": 0.9,
                    "source_slice_refs": ["SLI-NEW"],
                    "fact_payload": {
                        "fact_schema": "political_action_v1",
                        "actor": "朱元璋",
                        "object": "常遇春",
                        "action_type": "授权",
                        "event_scope": "军事",
                        "office_or_domain": "进兵",
                        "outcome": "克敌",
                        "time_context": "",
                        "source_span_refs": ["SLI-NEW"],
                        "confidence": 0.9,
                        "completeness": {"has_actor": True, "has_object": True, "has_action": True},
                    },
                    "evidence_spans": [
                        {"span_type": "action", "source_slice_ref": "SLI-NEW", "text": "命常遇春进兵"},
                        {"span_type": "outcome", "source_slice_ref": "SLI-NEW", "text": "克敌"},
                    ],
                }
            ],
            "primary_bindings": [],
            "secondary_binding_candidates": [],
            "coverage_matrix": {"rule_code": "i5b_item_wide", "role_families": []},
            "coverage": {},
            "coverage_gaps": [],
        }
        invocation.last_message.parent.mkdir(parents=True, exist_ok=True)
        invocation.last_message.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        invocation.event_log.write_text(
            '{"type":"turn.completed","usage":{"input_tokens":5,"output_tokens":3}}\n',
            encoding="utf-8",
        )
        return tool.CodexResult(payload=payload, elapsed_seconds=0.2, usage={"input_tokens": 5, "output_tokens": 3})

    monkeypatch.setattr(tool, "build_candidate_round", fake_candidate_round)
    summary = tool.run_clean_pipeline(
        tasks=[task_without_alias_gap()],
        run_root=tmp_path / "run",
        codex_runner=fake_claim_only_judge,
        skip_judge=False,
        max_alias_refine_rounds=0,
        judge_shard_size=0,
        judge_mode=tool.candidate_prompt.CLAIM_EXTRACTION_ONLY_MODE,
        claim_cache_root=cache_root,
        claim_cache_skip_cached_slices=True,
        claim_cache_import_final=True,
        max_workers=1,
    )

    round_summary = summary["people"][0]["rounds"][0]
    assert round_summary["claim_cache_plan"]["cached_slice_count"] == 1
    assert round_summary["claim_cache_plan"]["uncovered_slice_count"] == 1
    assert round_summary["claim_cache_hydrated_claim_count"] == 1
    assert summary["claim_cache_import"]["stats"]["new_claim_count"] == 1
    assert summary["claim_cache_import"]["stats"]["duplicate_claim_count"] == 1
    assert summary["people"][0]["claim_count"] == 2
    cached_claims = tool.claim_cache.read_jsonl(cache_root / "claims.jsonl")
    assert {row["object_name"] for row in cached_claims} == {"汤和", "常遇春"}


def test_clean_pipeline_can_skip_small_claim_cache_tail_without_judge(tmp_path: Path, monkeypatch) -> None:
    cached_slice = {
        "slice_code": "SLI-CACHED",
        "document_code": "DOC-001",
        "object_name": "汤和",
        "text": "帝命汤和守常州，常州安辑。",
    }
    new_slice = {
        "slice_code": "SLI-TAIL",
        "document_code": "DOC-001",
        "object_name": "常遇春",
        "text": "帝命常遇春进兵。",
    }
    cache_root = tmp_path / "claim_cache"
    cached_hash = tool.claim_cache.slice_hash_from_row(cached_slice)
    tool.claim_cache.write_jsonl(
        cache_root / "claim_evidence.jsonl",
        [{"evidence_key": "EVD-CACHED", "claim_key": "CLMK-CACHED", "slice_hash": cached_hash}],
    )
    tool.claim_cache.write_jsonl(
        cache_root / "claims.jsonl",
        [
            {
                "claim_key": "CLMK-CACHED",
                "emperor_name": "朱元璋",
                "object_name": "汤和",
                "object_type": "person",
                "claim_kind": "material_claim",
                "claim_summary": "朱元璋命汤和镇守常州。",
                "direction": "positive",
                "action_type": "授权",
                "fact_payload": {"actor": "朱元璋", "object": "汤和", "action_type": "授权"},
                "seen_count": 1,
            }
        ],
    )

    def fake_candidate_round(**kwargs) -> dict:
        person_dir = kwargs["person_dir"]
        prompt_path = person_dir / "judge_prompt.round0.md"
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text("placeholder", encoding="utf-8")
        return {
            "payload": {
                "task_identity": {"emperor_name": "朱元璋", "rule_code": "i5b_item_wide"},
                "target_profile": {"primary_name": "朱元璋"},
                "rule": {"rule_code": "i5b_item_wide"},
                "candidate_slices": [cached_slice, new_slice],
                "coverage_gaps": [],
                "fetch_errors": [],
                "stats": {"candidate_slices": 2},
            },
            "elapsed_seconds": 0.01,
            "output_path": person_dir / "candidates.round0.json",
            "prompt_path": prompt_path,
        }

    def fail_judge(invocation: tool.CodexInvocation) -> tool.CodexResult:
        raise AssertionError("judge should be skipped for small claim-cache tail")

    monkeypatch.setattr(tool, "build_candidate_round", fake_candidate_round)
    summary = tool.run_clean_pipeline(
        tasks=[task_without_alias_gap()],
        run_root=tmp_path / "run",
        codex_runner=fail_judge,
        skip_judge=False,
        max_alias_refine_rounds=0,
        judge_shard_size=0,
        judge_mode=tool.candidate_prompt.CLAIM_EXTRACTION_ONLY_MODE,
        claim_cache_root=cache_root,
        claim_cache_skip_cached_slices=True,
        claim_cache_min_uncovered_slices_for_judge=2,
        max_workers=1,
    )

    person = summary["people"][0]
    result = json.loads(Path(person["files"]["final_judge_result"]).read_text(encoding="utf-8"))
    assert person["judge_status"] == "needs_refinement"
    assert person["judge_elapsed_seconds"] == 0.0
    assert person["claim_count"] == 1
    assert result["claims"][0]["cached_claim_key"] == "CLMK-CACHED"
    assert result["claims"][0]["source_slice_refs"] == ["SLI-CACHED"]
    assert result["coverage_gaps"][0]["gap_type"] == "claim_cache_tail_uncovered"
    assert result["_claim_cache_plan"]["uncovered_slice_count"] == 1
    assert result["_claim_cache_hydrated"]["merged_cached_claim_count"] == 1


def test_clean_pipeline_can_skip_low_claim_cache_hit_ratio_without_judge(tmp_path: Path, monkeypatch) -> None:
    cached_slice = {
        "slice_code": "SLI-CACHED",
        "document_code": "DOC-001",
        "object_name": "汤和",
        "text": "帝命汤和守常州，常州安辑。",
    }
    drifted_slices = [
        {
            "slice_code": f"SLI-DRIFT-{index}",
            "document_code": "DOC-001",
            "object_name": "常遇春",
            "text": f"帝命常遇春进兵，片段{index}。",
        }
        for index in range(3)
    ]
    cache_root = tmp_path / "claim_cache"
    cached_hash = tool.claim_cache.slice_hash_from_row(cached_slice)
    tool.claim_cache.write_jsonl(
        cache_root / "claim_evidence.jsonl",
        [{"evidence_key": "EVD-CACHED", "claim_key": "CLMK-CACHED", "slice_hash": cached_hash}],
    )
    tool.claim_cache.write_jsonl(
        cache_root / "claims.jsonl",
        [
            {
                "claim_key": "CLMK-CACHED",
                "emperor_name": "朱元璋",
                "object_name": "汤和",
                "object_type": "person",
                "claim_kind": "material_claim",
                "claim_summary": "朱元璋命汤和镇守常州。",
                "direction": "positive",
                "action_type": "授权",
                "fact_payload": {"actor": "朱元璋", "object": "汤和", "action_type": "授权"},
                "seen_count": 1,
            }
        ],
    )

    def fake_candidate_round(**kwargs) -> dict:
        person_dir = kwargs["person_dir"]
        prompt_path = person_dir / "judge_prompt.round0.md"
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text("placeholder", encoding="utf-8")
        return {
            "payload": {
                "task_identity": {"emperor_name": "朱元璋", "rule_code": "i5b_item_wide"},
                "target_profile": {"primary_name": "朱元璋"},
                "rule": {"rule_code": "i5b_item_wide"},
                "candidate_slices": [cached_slice, *drifted_slices],
                "coverage_gaps": [],
                "fetch_errors": [],
                "stats": {"candidate_slices": 4},
            },
            "elapsed_seconds": 0.01,
            "output_path": person_dir / "candidates.round0.json",
            "prompt_path": prompt_path,
        }

    def fail_judge(invocation: tool.CodexInvocation) -> tool.CodexResult:
        raise AssertionError("judge should be skipped when claim-cache hit ratio is too low")

    monkeypatch.setattr(tool, "build_candidate_round", fake_candidate_round)
    summary = tool.run_clean_pipeline(
        tasks=[task_without_alias_gap()],
        run_root=tmp_path / "run",
        codex_runner=fail_judge,
        skip_judge=False,
        max_alias_refine_rounds=0,
        judge_shard_size=0,
        judge_mode=tool.candidate_prompt.CLAIM_EXTRACTION_ONLY_MODE,
        claim_cache_root=cache_root,
        claim_cache_skip_cached_slices=True,
        claim_cache_min_uncovered_slices_for_judge=1,
        claim_cache_min_hit_ratio_for_judge=0.8,
        max_workers=1,
    )

    person = summary["people"][0]
    result = json.loads(Path(person["files"]["final_judge_result"]).read_text(encoding="utf-8"))
    assert person["judge_status"] == "needs_refinement"
    assert person["judge_elapsed_seconds"] == 0.0
    assert person["claim_count"] == 1
    assert result["coverage_gaps"][0]["gap_type"] == "claim_cache_low_hit_ratio"
    assert "hit ratio 0.250" in result["coverage_gaps"][0]["diagnosis"]
    assert result["_claim_cache_plan"]["cached_slice_count"] == 1
    assert result["_claim_cache_plan"]["uncovered_slice_count"] == 3
    assert summary["clean_policy"]["claim_cache_min_hit_ratio_for_judge"] == 0.8


def test_judge_payload_normalizes_candidate_profiles_for_consumption() -> None:
    payload = {
        "claims": [],
        "secondary_binding_candidates": [
            {
                "claim_code": "CLM-001",
                "rule_code": "team_building",
                "candidate_item_code": "I5B",
                "candidate_payload": {
                    "personnel_profile": {"person": "萧何", "person_role": "丞相", "talent_quality": ""},
                    "power_control_profile": {"power_holder": "萧何"},
                    "appointment_delegation_factor_hints": {"importance_hint": "real_duty"},
                    "profile_policy": "do not persist",
                },
            },
            {
                "claim_code": "CLM-002",
                "rule_code": "central_military_power_control",
                "candidate_item_code": "I5C",
                "candidate_payload": {
                    "personnel_profile": {"person": "韩信"},
                    "power_control_profile": {"power_holder": "韩信", "risk_type": ""},
                    "appointment_delegation_factor_hints": {"importance_hint": "key_military_political"},
                    "profile_policy": "do not persist",
                },
            },
            {
                "claim_code": "CLM-003",
                "rule_code": "military_frontier_result",
                "candidate_item_code": "I3",
                "candidate_payload": {
                    "personnel_profile": {"person": "韩信"},
                    "power_control_profile": {"power_holder": "韩信"},
                    "appointment_delegation_factor_hints": {"importance_hint": "key_military_political"},
                    "profile_policy": "do not persist",
                },
            },
            {
                "claim_code": "CLM-004",
                "rule_code": "appointment_delegation",
                "candidate_item_code": "I5B",
                "candidate_lane": "I5B.appointment_delegation",
                "direction": "positive",
                "candidate_payload": {
                    "scoring_candidate": True,
                    "usable_for_scoring_cluster": True,
                    "appointment_delegation_factor_hints": {
                        "importance_hint": "key_military_political",
                        "effect_hint": "strong_success",
                        "continuity_hint": "stable",
                        "hint_confidence": {"importance": "high", "effect": "medium", "continuity": "medium"},
                        "uncertainty_flags": [],
                    },
                },
            },
        ],
    }

    normalized = tool.judge_shards.normalize_candidate_payload_profiles(payload)
    rows = normalized["secondary_binding_candidates"]

    assert rows[0]["candidate_payload"] == {
        "personnel_profile": {"person": "萧何", "person_role": "丞相"},
    }
    assert rows[1]["candidate_payload"] == {
        "power_control_profile": {"power_holder": "韩信"},
    }
    assert rows[2]["candidate_payload"] == {}
    assert rows[3]["candidate_payload"]["appointment_delegation_factor_hints"] == {
        "importance_hint": "key_military_political",
        "effect_hint": "strong_success",
        "continuity_hint": "stable",
        "hint_confidence": {"importance": "high", "effect": "medium", "continuity": "medium"},
        "uncertainty_flags": [],
    }


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


def test_cli_defaults_run_root_from_runtime_config(tmp_path: Path, capsys) -> None:
    task_path = tmp_path / "task.json"
    task_path.write_text(json.dumps(task_without_alias_gap(), ensure_ascii=False), encoding="utf-8")
    config = tmp_path / "runtime_paths.json"
    clean_runs_root = tmp_path / "active" / "clean_runs"
    source_cache_root = tmp_path / "active" / "source_cache"
    config.write_text(
        json.dumps(
            {
                "active_root_smb": str(tmp_path / "active"),
                "archive_root_smb": str(tmp_path / "archive"),
                "retrieval_v2_clean_runs": str(clean_runs_root),
                "source_cache": str(source_cache_root),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    assert tool.main(["--task", str(task_path), "--runtime-paths-config", str(config), "--skip-judge"]) == 0

    payload = json.loads(capsys.readouterr().out)
    run_root = Path(payload["event_log"]).parent
    assert run_root.parent == clean_runs_root
    assert payload["runtime_paths"]["uses_runtime_config"] is True
    assert payload["runtime_paths"]["source_cache_root"] == str(source_cache_root)
    assert (run_root / "summary.json").exists()


def test_cli_claim_cache_stable_rerun_preset_applies_safe_defaults(tmp_path: Path, capsys) -> None:
    task_path = tmp_path / "task.json"
    run_root = tmp_path / "run"
    cache_root = tmp_path / "claim_cache"
    source_cache_root = tmp_path / "source_cache"
    task_path.write_text(json.dumps(task_without_alias_gap(), ensure_ascii=False), encoding="utf-8")

    assert tool.main(
        [
            "--task",
            str(task_path),
            "--run-root",
            str(run_root),
            "--source-cache-root",
            str(source_cache_root),
            "--claim-cache-root",
            str(cache_root),
            "--claim-cache-stable-rerun-preset",
            "--skip-judge",
        ]
    ) == 0

    payload = json.loads(capsys.readouterr().out)
    policy = payload["clean_policy"]
    assert policy["claim_cache_stable_rerun_preset"] is True
    assert policy["judge_mode"] == "claim_extraction_only"
    assert policy["claim_cache_skip_cached_slices"] is True
    assert policy["claim_cache_min_uncovered_slices_for_judge"] == 8
    assert policy["claim_cache_min_hit_ratio_for_judge"] == 0.8
    assert policy["context_chars"] == 180
    assert policy["max_slices_per_object"] == 12
    assert policy["max_alias_refine_rounds"] == 0
    assert policy["candidate_source_refine_rounds"] == 0
    assert policy["judge_shard_size"] == 4
    assert policy["judge_shard_workers"] == 4
    assert payload["runtime_paths"]["source_cache_root"] == str(source_cache_root)


def test_cli_claim_cache_stable_rerun_preset_rejects_local_source_cache_fallback(tmp_path: Path) -> None:
    task_path = tmp_path / "task.json"
    task_path.write_text(json.dumps(task_without_alias_gap(), ensure_ascii=False), encoding="utf-8")

    with pytest.raises(tool.RetrievalV2CleanRunnerError, match="requires --source-cache-root"):
        tool.main(
            [
                "--task",
                str(task_path),
                "--run-root",
                str(tmp_path / "run"),
                "--use-local-runtime",
                "--claim-cache-root",
                str(tmp_path / "claim_cache"),
                "--claim-cache-stable-rerun-preset",
                "--skip-judge",
            ]
        )


def test_cli_i5b_wide_shadow_pilot_marks_outputs_not_formal_consumption(tmp_path: Path, capsys) -> None:
    task_path = tmp_path / "task.json"
    run_root = tmp_path / "run"
    task_path.write_text(json.dumps(task_without_alias_gap(), ensure_ascii=False), encoding="utf-8")

    assert tool.main([
        "--task",
        str(task_path),
        "--run-root",
        str(run_root),
        "--skip-judge",
        "--i5b-wide-shadow-pilot",
    ]) == 0

    payload = json.loads(capsys.readouterr().out)
    person = payload["people"][0]
    candidates = json.loads(Path(person["files"]["final_candidates"]).read_text(encoding="utf-8"))
    final_task = json.loads(Path(person["files"]["final_task"]).read_text(encoding="utf-8"))

    assert payload["capture_mode"] == "i5b_wide_shadow"
    assert payload["formal_consumption_source"] is False
    assert payload["clean_policy"]["shadow_pilot"] is True
    assert person["capture_mode"] == "i5b_wide_shadow"
    assert person["formal_consumption_source"] is False
    assert final_task["capture_mode"] == "i5b_wide_shadow"
    assert candidates["task_identity"]["capture_mode"] == "i5b_wide_shadow"


def test_cli_i5b_item_wide_shadow_pilot_uses_item_wide_package_shape(tmp_path: Path, capsys) -> None:
    task_path = tmp_path / "task.json"
    run_root = tmp_path / "run"
    task_path.write_text(json.dumps(task_without_alias_gap(), ensure_ascii=False), encoding="utf-8")

    assert tool.main(
        [
            "--task",
            str(task_path),
            "--run-root",
            str(run_root),
            "--skip-judge",
            "--i5b-item-wide-shadow-pilot",
        ]
    ) == 0

    payload = json.loads(capsys.readouterr().out)
    person = payload["people"][0]
    candidates = json.loads(Path(person["files"]["final_candidates"]).read_text(encoding="utf-8"))
    final_task = json.loads(Path(person["files"]["final_task"]).read_text(encoding="utf-8"))

    assert payload["capture_mode"] == "i5b_item_wide_shadow"
    assert payload["formal_consumption_source"] is False
    assert payload["clean_policy"]["shadow_pilot"] is True
    assert person["capture_mode"] == "i5b_item_wide_shadow"
    assert person["rule_code"] == "i5b_item_wide"
    assert final_task["rule_code"] == "i5b_item_wide"
    assert final_task["rule"]["rule_code"] == "i5b_item_wide"
    assert final_task["coverage_matrix"]["rule_code"] == "i5b_item_wide"
    assert final_task["target_payload"]["capture_profile"] == "i5b_item_wide"
    assert candidates["task_identity"]["capture_mode"] == "i5b_item_wide_shadow"
    assert candidates["task_identity"]["rule_code"] == "i5b_item_wide"
    assert candidates["task_identity"]["capture_profile"] == "i5b_item_wide"


def test_cli_personnel_political_wide_shadow_pilot_uses_generic_fact_contract(tmp_path: Path, capsys) -> None:
    task_path = tmp_path / "task.json"
    run_root = tmp_path / "run"
    task_path.write_text(json.dumps(task_without_alias_gap(), ensure_ascii=False), encoding="utf-8")

    assert tool.main(
        [
            "--task",
            str(task_path),
            "--run-root",
            str(run_root),
            "--skip-judge",
            "--personnel-political-wide-shadow-pilot",
        ]
    ) == 0

    payload = json.loads(capsys.readouterr().out)
    person = payload["people"][0]
    candidates = json.loads(Path(person["files"]["final_candidates"]).read_text(encoding="utf-8"))
    final_task = json.loads(Path(person["files"]["final_task"]).read_text(encoding="utf-8"))

    assert payload["capture_mode"] == "personnel_political_wide_shadow"
    assert payload["capture_profile"] == "personnel_political_wide"
    assert payload["formal_consumption_source"] is False
    assert payload["clean_policy"]["shadow_pilot"] is True
    assert payload["clean_policy"]["capture_profile"] == "personnel_political_wide"
    assert person["capture_mode"] == "personnel_political_wide_shadow"
    assert person["rule_code"] == "i5b_item_wide"
    assert final_task["rule_code"] == "i5b_item_wide"
    assert final_task["coverage_matrix"]["rule_code"] == "i5b_item_wide"
    family_codes = {row["family_code"] for row in final_task["coverage_matrix"]["role_families"]}
    candidate_rules = {row["rule_code"] for row in final_task["secondary_rule_candidates"]}
    candidate_lanes = {row.get("candidate_lane") for row in final_task["secondary_rule_candidates"]}
    assert "appointment_delegation_material" in family_codes
    assert "appointment_trust_material" not in family_codes
    assert "appointment_delegation" in candidate_rules
    assert "appointment_trust" not in candidate_rules
    assert "delegation" not in candidate_rules
    assert "power_control" not in candidate_rules
    assert "central_military_power_control" in candidate_rules
    assert "regional_clan_power_control" in candidate_rules
    assert "inner_favorite_power_control" in candidate_rules
    assert "institutional_constraint_correction" in candidate_rules
    assert "I5B.appointment_delegation" in candidate_lanes
    assert "power_control" not in candidate_lanes
    assert "central_military_power_control" in candidate_lanes
    assert "regional_clan_power_control" in candidate_lanes
    assert "inner_favorite_power_control" in candidate_lanes
    assert "institutional_constraint_correction" in candidate_lanes
    final_task_text = json.dumps(final_task, ensure_ascii=False)
    assert "appointment_trust" not in final_task_text
    assert "I5B.delegation" not in final_task_text
    assert final_task["target_payload"]["capture_profile"] == "personnel_political_wide"
    assert final_task["target_payload"]["fact_schema"] == "political_action_v1"
    assert final_task["target_payload"]["candidate_route_table_version"] == "personnel_political_v0_2"
    assert candidates["task_identity"]["capture_mode"] == "personnel_political_wide_shadow"
    assert candidates["task_identity"]["capture_profile"] == "personnel_political_wide"
    assert candidates["task_identity"]["fact_schema"] == "political_action_v1"
    assert candidates["task_identity"]["candidate_route_table_version"] == "personnel_political_v0_2"
    assert candidates["task_identity"]["rule_code"] == "i5b_item_wide"


def test_cli_judge_shard_workers_defaults_to_four_for_item_wide_shadow() -> None:
    args = SimpleNamespace(
        judge_shard_workers=None,
        personnel_political_wide_shadow_pilot=True,
        i5b_item_wide_shadow_pilot=False,
        i5b_wide_shadow_pilot=False,
    )

    assert retrieval_v2_clean_cli._effective_judge_shard_workers(args) == 4


def test_cli_judge_shard_workers_keeps_non_shadow_default_and_explicit_value() -> None:
    normal_args = SimpleNamespace(
        judge_shard_workers=None,
        personnel_political_wide_shadow_pilot=False,
        i5b_item_wide_shadow_pilot=False,
        i5b_wide_shadow_pilot=False,
    )
    explicit_args = SimpleNamespace(
        judge_shard_workers=3,
        personnel_political_wide_shadow_pilot=True,
        i5b_item_wide_shadow_pilot=False,
        i5b_wide_shadow_pilot=False,
    )

    assert retrieval_v2_clean_cli._effective_judge_shard_workers(normal_args) == 2
    assert retrieval_v2_clean_cli._effective_judge_shard_workers(explicit_args) == 3


def test_i5b_item_wide_shadow_context_is_rewritten_before_taskgen() -> None:
    args = SimpleNamespace(i5b_item_wide_shadow_pilot=True, i5b_wide_shadow_pilot=False)

    context = retrieval_v2_clean_cli._with_shadow_context(task_with_candidate_source_gap(), args)
    skeleton = retrieval_v2_clean_cli.task_skeleton.build_task_skeleton(context)
    family_codes = {row["family_code"] for row in skeleton["coverage_matrix"]["role_families"]}

    assert context["rule_code"] == "i5b_item_wide"
    assert context["target_payload"]["capture_mode"] == "i5b_item_wide_shadow"
    assert skeleton["rule_code"] == "i5b_item_wide"
    assert "appointment_delegation_material" in family_codes
    assert "anti_nepotism_material" in family_codes
    assert "military_delegate" not in family_codes


def test_personnel_political_wide_shadow_context_reuses_item_wide_shell() -> None:
    args = SimpleNamespace(
        personnel_political_wide_shadow_pilot=True,
        i5b_item_wide_shadow_pilot=False,
        i5b_wide_shadow_pilot=False,
    )

    context = retrieval_v2_clean_cli._with_shadow_context(task_with_candidate_source_gap(), args)
    skeleton = retrieval_v2_clean_cli.task_skeleton.build_task_skeleton(context)
    family_codes = {row["family_code"] for row in skeleton["coverage_matrix"]["role_families"]}

    assert context["rule_code"] == "i5b_item_wide"
    assert context["target_payload"]["capture_mode"] == "personnel_political_wide_shadow"
    assert context["target_payload"]["capture_profile"] == "personnel_political_wide"
    assert context["target_payload"]["fact_schema"] == "political_action_v1"
    assert context["target_payload"]["candidate_route_table_version"] == "personnel_political_v0_2"
    assert skeleton["rule_code"] == "i5b_item_wide"
    assert "appointment_delegation_material" in family_codes
    assert "future_power_character_hint" in family_codes
