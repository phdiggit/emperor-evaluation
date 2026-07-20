from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest
import yaml

from emperor_v4.adapters.claim_extraction_profile import (
    ClaimExtractionProfile,
)
from emperor_v4.adapters.claim_extractor_codex import (
    CodexCliClaimExtractionProvider,
    _codex_subprocess_environment,
    parse_codex_claim_output,
)
from emperor_v4.adapters.structured_output_contract import (
    build_canary_acceptance_report,
    build_preflight_report,
    validate_payload_against_schema,
    validate_codex_output_schema,
    validate_codex_task_plan,
)
from emperor_v4.adapters.dynasty_neutral_governance import (
    audit_scan,
    build_dynasty_neutral_governance_prompt,
    prepare_scan,
)
from emperor_v4.adapters.dynasty_neutral_source_increment import (
    audit_comparison,
    prepare_comparison,
)
from emperor_v4.adapters.dynasty_neutral_material_settlement import (
    settle_neutral_materials,
)
from emperor_v4.adapters.source_cache_wikisource import (
    WikisourceSourceMaterialProvider,
)
from emperor_v4.adapters.wikisource import WikisourcePageSnapshot
from emperor_v4.application.claim_extractor_service import (
    ClaimExtractionBatch,
    claim_extraction_input_fingerprint,
    ensure_claim_extraction,
)
from emperor_v4.contracts.extraction import ClaimExtractionRequest
from emperor_v4.contracts.source import SourceCacheRequest, SourceCacheSubject
from emperor_v4.persistence.claim_extractor import (
    InMemoryClaimExtractionRepository,
)
from emperor_v4.runtime.claim_extractor import (
    claim_worker_lease_seconds,
    request_profile_from_mapping,
)
from emperor_v4.runtime.source_cache import run_wikisource_ensure
from emperor_v4.runtime.release import (
    CLAIM_EXTRACTOR_RELEASE_PATHS,
    SOURCE_CACHE_RELEASE_PATHS,
)


ROOT = Path(__file__).parents[1]
PROFILES = ROOT / "config" / "claim-extraction-profiles.yml"
OUTPUT_SCHEMA = ROOT / "config" / "claim-extraction-output.schema.json"


def test_service_releases_include_runtime_verification_and_data1_state() -> None:
    verifier = "deploy/v4/verify-server-runtime.sh"
    assert verifier in SOURCE_CACHE_RELEASE_PATHS
    assert verifier in CLAIM_EXTRACTOR_RELEASE_PATHS
    claim_unit = (
        ROOT / "deploy/v4/emperor-v4-claim-extractor-worker.service"
    ).read_text(encoding="utf-8")
    provisioner = (ROOT / "deploy/v4/provision-prerequisites.sh").read_text(
        encoding="utf-8"
    )
    state_root = "/data1/emperor-evaluation/runtime/services/emperor-v4"
    assert f"Environment=CODEX_HOME={state_root}/claim-extractor/codex" in claim_unit
    assert f"ReadWritePaths={state_root}" in claim_unit
    assert f"EMPEROR_EVAL_V4_STATE_ROOT:-{state_root}" in provisioner
    assert {
        "config/dynasty-neutral-governance-output.schema.json",
        "config/dynasty-neutral-source-increment-output.schema.json",
        "src/emperor_v4/adapters/dynasty_neutral_governance.py",
        "src/emperor_v4/adapters/dynasty_neutral_material_settlement.py",
        "src/emperor_v4/adapters/dynasty_neutral_source_increment.py",
        "src/emperor_v4/adapters/structured_output_contract.py",
    } <= set(SOURCE_CACHE_RELEASE_PATHS)


def _claim_payload() -> dict:
    return {
        "assertions": [
            {
                "assertion_code": "A-LOCAL-1",
                "source_passage_ref": "SP-1",
                "assertion_type": "event_fact",
                "subject": "太宗",
                "predicate": "召见",
                "object": "魏徵",
                "time_expression": None,
                "location_expression": None,
                "qualifiers": {
                    "responsibility_family": "talent_discovery"
                },
                "polarity": "asserted",
                "source_attribution": {},
                "confidence": 0.9,
                "ambiguity_flags": [],
                "passage_support": {
                    "support_mode": "single_passage",
                    "assertion_semantic_key": "太宗-召见-魏徵",
                    "supported_fields": ["identity", "action"],
                },
            }
        ],
        "coverage_gaps": ["缺少后续任用结果"],
    }


def _request(profile_code: str = "political_action_atomic_v1"):
    return ClaimExtractionRequest(
        request_id="CER-SCALE-1",
        idempotency_key="claim-scale-contract:1",
        profile_code=profile_code,
        subject={
            "person_ref": "PER-WEIZHENG",
            "ruler": "李世民",
            "aliases": ["魏徵"],
        },
        passages=(
            {
                "passage_id": "SP-1",
                "raw_text": "太宗召徵。",
            },
        ),
        requested_at="2026-07-14T00:00:00+08:00",
    )


def _profile(code: str = "political_action_atomic_v1"):
    return ClaimExtractionProfile(
        code=code,
        output_contract="assertion-extraction-contract-v2",
        purpose="抽取测试事实",
        required_chains=(),
        prohibitions=("不做评分",),
    )


def _saturated_claim_payload(*, declare_limit: bool) -> dict:
    template = _claim_payload()["assertions"][0]
    assertions = []
    for index in range(64):
        row = deepcopy(template)
        row["assertion_code"] = f"A-LIMIT-{index:02d}"
        row["predicate"] = f"事实动作{index:02d}"
        row["object"] = f"事实对象{index:02d}"
        row["passage_support"]["assertion_semantic_key"] = (
            f"limit-semantic-{index:02d}"
        )
        assertions.append(row)
    return {
        "assertions": assertions,
        "coverage_gaps": ["output_limit_reached"] if declare_limit else [],
    }


class _PolicyPayloadProvider:
    def __init__(self, payload: dict, policy_fingerprint: str) -> None:
        self.payload = payload
        self.policy_fingerprint = policy_fingerprint
        self.calls = 0

    def extract(self, request_payload):
        self.calls += 1
        return parse_codex_claim_output(
            self.payload,
            provider_code="codex:test",
            provider_metadata={
                "provider_policy_fingerprint": self.policy_fingerprint,
            },
        )


def test_claim_worker_selects_profile_from_each_job_payload() -> None:
    payload = {
        "request_id": "CER-PROFILE-1",
        "idempotency_key": "claim-profile:1",
        "profile_code": "talent_discovery_chain_v1",
        "subject": {"person_ref": "PER-WEIZHENG"},
        "passages": [{"passage_id": "SP-1", "raw_text": "太宗召徵。"}],
        "requested_at": "2026-07-14T00:00:00+08:00",
    }

    request, profile = request_profile_from_mapping(PROFILES, payload)

    assert request.profile_code == "talent_discovery_chain_v1"
    assert profile.code == request.profile_code
    assert profile.required_chains


def test_claim_worker_lease_must_cover_model_timeout() -> None:
    assert claim_worker_lease_seconds(timeout_seconds=600) == 720
    assert claim_worker_lease_seconds(
        timeout_seconds=600,
        configured_lease_seconds=900,
    ) == 900
    with pytest.raises(ValueError, match="覆盖 provider timeout"):
        claim_worker_lease_seconds(
            timeout_seconds=600,
            configured_lease_seconds=600,
        )


def test_claim_service_accepts_explicit_empty_result_without_retry_loop() -> None:
    class EmptyProvider:
        calls = 0

        def extract(self, request_payload):
            self.calls += 1
            return ClaimExtractionBatch(
                assertions=(),
                provider_code="empty-fixture:v1",
                coverage_gaps=("no_relevant_fact_in_requested_profile",),
            )

    provider = EmptyProvider()
    repository = InMemoryClaimExtractionRepository()
    first = ensure_claim_extraction(
        _request(),
        profile=_profile(),
        provider=provider,
        repository=repository,
        service_release_sha="a" * 40,
    )
    second = ensure_claim_extraction(
        _request(),
        profile=_profile(),
        provider=provider,
        repository=repository,
        service_release_sha="a" * 40,
    )

    assert first.response["status"] == "succeeded_no_relevant_facts"
    assert first.response["assertions"] == []
    assert first.response["coverage_gaps"] == [
        "no_relevant_fact_in_requested_profile"
    ]
    assert second.cache_hit is True
    assert provider.calls == 1


def test_claim_service_rejects_silent_empty_result() -> None:
    class SilentProvider:
        def extract(self, request_payload):
            return ClaimExtractionBatch((), "silent-fixture:v1")

    with pytest.raises(ValueError, match="空结果必须声明"):
        ensure_claim_extraction(
            _request(),
            profile=_profile(),
            provider=SilentProvider(),
            repository=InMemoryClaimExtractionRepository(),
            service_release_sha="a" * 40,
        )


def test_codex_parser_preserves_gaps_and_runtime_audit() -> None:
    batch = parse_codex_claim_output(
        _claim_payload(),
        provider_code="codex:test",
        provider_metadata={"elapsed_seconds": 1.25, "prompt_chars": 300},
    )

    assert batch.coverage_gaps == ("缺少后续任用结果",)
    assert batch.provider_metadata["elapsed_seconds"] == 1.25
    assert batch.assertions[0].qualifiers["responsibility_family"] == (
        "talent_discovery"
    )


def test_claim_service_replaces_provider_ids_and_adds_trusted_routing() -> None:
    class PayloadProvider:
        def __init__(self, payload: dict) -> None:
            self.payload = payload

        def extract(self, request_payload):
            return parse_codex_claim_output(
                self.payload,
                provider_code="codex:test",
            )

    first_payload = _claim_payload()
    second_payload = deepcopy(first_payload)
    second_payload["assertions"][0]["assertion_code"] = "MODEL-RANDOM-2"
    second_payload["assertions"][0]["passage_support"][
        "assertion_semantic_key"
    ] = "模型另一种措辞"
    second_payload["assertions"][0]["confidence"] = 0.72
    third_payload = deepcopy(first_payload)
    third_payload["assertions"][0].pop("assertion_code")

    first = ensure_claim_extraction(
        _request(),
        profile=_profile(),
        provider=PayloadProvider(first_payload),
        repository=InMemoryClaimExtractionRepository(),
        service_release_sha="a" * 40,
    ).response["assertions"][0]
    second = ensure_claim_extraction(
        _request(),
        profile=_profile(),
        provider=PayloadProvider(second_payload),
        repository=InMemoryClaimExtractionRepository(),
        service_release_sha="a" * 40,
    ).response["assertions"][0]
    third = ensure_claim_extraction(
        _request("talent_discovery_chain_v1"),
        profile=_profile("talent_discovery_chain_v1"),
        provider=PayloadProvider(third_payload),
        repository=InMemoryClaimExtractionRepository(),
        service_release_sha="a" * 40,
    ).response["assertions"][0]

    assert first["assertion_code"] == second["assertion_code"]
    assert first["assertion_code"] == third["assertion_code"]
    assert first["assertion_code"].startswith("ASTD-")
    assert (
        first["passage_support"]["assertion_semantic_key"]
        == second["passage_support"]["assertion_semantic_key"]
        == third["passage_support"]["assertion_semantic_key"]
    )
    assert first["extraction_provenance"]["provider_assertion_code"] == (
        "A-LOCAL-1"
    )
    assert second["extraction_provenance"]["provider_assertion_code"] == (
        "MODEL-RANDOM-2"
    )
    assert third["extraction_provenance"]["provider_assertion_code"] == (
        "provider-row-0001"
    )
    assert third["qualifiers"]["evaluation_context"] == "李世民"
    assert third["qualifiers"]["focal_person_ref"] == "PER-WEIZHENG"
    assert third["qualifiers"]["candidate_participant_roles"] == (
        ("李世民", "ruler"),
        ("PER-WEIZHENG", "focal_person"),
    )


def test_claim_cache_identity_includes_provider_policy() -> None:
    first = claim_extraction_input_fingerprint(
        _request(),
        _profile(),
        provider_policy_fingerprint="a" * 64,
    )
    second = claim_extraction_input_fingerprint(
        _request(),
        _profile(),
        provider_policy_fingerprint="b" * 64,
    )

    assert first != second


def test_claim_cache_rejects_silent_reuse_after_provider_policy_change() -> None:
    repository = InMemoryClaimExtractionRepository()
    first_provider = _PolicyPayloadProvider(_claim_payload(), "a" * 64)
    second_provider = _PolicyPayloadProvider(_claim_payload(), "b" * 64)

    ensure_claim_extraction(
        _request(),
        profile=_profile(),
        provider=first_provider,
        repository=repository,
        service_release_sha="a" * 40,
    )
    with pytest.raises(ValueError, match="provider policy"):
        ensure_claim_extraction(
            _request(),
            profile=_profile(),
            provider=second_provider,
            repository=repository,
            service_release_sha="a" * 40,
        )

    assert first_provider.calls == 1
    assert second_provider.calls == 0


def test_claim_service_rejects_saturated_output_without_explicit_gap() -> None:
    provider = _PolicyPayloadProvider(
        _saturated_claim_payload(declare_limit=False),
        "a" * 64,
    )

    with pytest.raises(ValueError, match="output_limit_reached"):
        ensure_claim_extraction(
            _request(),
            profile=_profile(),
            provider=provider,
            repository=InMemoryClaimExtractionRepository(),
            service_release_sha="a" * 40,
        )


def test_claim_service_accepts_saturated_output_with_explicit_gap() -> None:
    provider = _PolicyPayloadProvider(
        _saturated_claim_payload(declare_limit=True),
        "a" * 64,
    )

    run = ensure_claim_extraction(
        _request(),
        profile=_profile(),
        provider=provider,
        repository=InMemoryClaimExtractionRepository(),
        service_release_sha="a" * 40,
    )

    assert run.response["status"] == "succeeded_with_gaps"
    assert len(run.response["assertions"]) == 64
    assert run.response["coverage_gaps"] == ["output_limit_reached"]


def test_codex_provider_rejects_oversized_prompt_before_process_start() -> None:
    provider = CodexCliClaimExtractionProvider(
        codex_bin="never-executed",
        model="fixture-model",
        reasoning_effort="medium",
        output_schema_path=OUTPUT_SCHEMA,
        max_prompt_chars=32,
    )

    with pytest.raises(ValueError, match="prompt 超限"):
        provider.extract(
            {
                "profile_code": "political_action_atomic_v1",
                "passages": [
                    {"passage_id": "SP-1", "raw_text": "原文" * 100}
                ],
            }
        )


def test_structured_output_preflight_rejects_contract_drift_before_model_call(
    tmp_path: Path,
) -> None:
    valid = {
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "items"],
        "properties": {
            "schema_version": {"type": "string", "const": "fixture-v1"},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["name", "note"],
                    "properties": {
                        "name": {"type": "string"},
                        "note": {"type": ["string", "null"]},
                    },
                },
            },
        },
    }
    report = validate_codex_output_schema(valid)
    assert report["contract_version"] == "codex-structured-output-contract-v1"
    assert len(report["schema_sha256"]) == 64

    missing_type = deepcopy(valid)
    del missing_type["properties"]["schema_version"]["type"]
    with pytest.raises(ValueError, match="缺少显式 type"):
        validate_codex_output_schema(missing_type)

    unsupported = deepcopy(valid)
    unsupported["properties"]["items"]["uniqueItems"] = True
    with pytest.raises(ValueError, match="uniqueItems"):
        validate_codex_output_schema(unsupported)

    optional_drift = deepcopy(valid)
    optional_drift["properties"]["items"]["items"]["required"] = ["name"]
    with pytest.raises(ValueError, match="可空字段也必须 required"):
        validate_codex_output_schema(optional_drift)


@pytest.mark.parametrize(
    "schema_path",
    sorted((ROOT / "config").glob("*output.schema.json")),
    ids=lambda path: path.name,
)
def test_all_model_output_schemas_pass_zero_call_provider_preflight(
    schema_path: Path,
) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    report = validate_codex_output_schema(
        schema,
        require_all_properties=(
            schema_path.name
            in {
                "shared-neutral-extraction-output.schema.json",
                "dynasty-neutral-governance-output.schema.json",
                "dynasty-neutral-source-increment-output.schema.json",
            }
        ),
    )
    assert len(report["schema_sha256"]) == 64


def test_structured_output_task_preflight_requires_effective_schema_and_isolation(
    tmp_path: Path,
) -> None:
    schema_path = tmp_path / "output.schema.json"
    schema_path.write_text(
        json.dumps(
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["value"],
                "properties": {"value": {"type": "string"}},
            }
        ),
        encoding="utf-8",
    )
    prompt_path = tmp_path / "prompt.md"
    prompt_path.write_text(
        "\n".join(
            (
                "EXECUTION_MODE: STRUCTURED_OUTPUT_NO_TOOLS",
                "TOOLS: FORBIDDEN",
                "REPOSITORY_READ: FORBIDDEN",
                "OUTPUT: JSON_ONLY",
            )
        ),
        encoding="utf-8",
    )
    task = {
        "task_code": "CANARY-1",
        "prompt_path": str(prompt_path),
        "argv": ["codex", "exec", "--output-schema", str(schema_path), "-"],
    }
    report = validate_codex_task_plan([task], output_schema_path=schema_path)
    assert report["requires_respect_task_argv"] is True
    assert report["execution_mode"] == "structured_output_no_tools"

    ignored = task | {"output_schema_path": str(schema_path)}
    with pytest.raises(ValueError, match="禁止静默字段 output_schema_path"):
        validate_codex_task_plan([ignored], output_schema_path=schema_path)

    wrong = deepcopy(task)
    wrong["argv"][3] = str(tmp_path / "wrong.schema.json")
    with pytest.raises(ValueError, match="与预检 schema 不一致"):
        validate_codex_task_plan([wrong], output_schema_path=schema_path)

    tasks_path = tmp_path / "tasks.jsonl"
    tasks_path.write_text(json.dumps(task) + "\n", encoding="utf-8")
    preflight = build_preflight_report(
        schema_path=schema_path,
        tasks_path=tasks_path,
    )
    assert preflight["status"] == "ready_for_single_canary"
    assert preflight["model_calls"] == 0


def test_canary_acceptance_closes_events_usage_and_payload(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.json"
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["value"],
        "properties": {"value": {"type": "string", "minLength": 1}},
    }
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    status_path = tmp_path / "status.json"
    status_path.write_text(
        json.dumps(
            {
                "status": "succeeded",
                "tasks": [
                    {
                        "task_code": "CANARY-1",
                        "status": "succeeded",
                        "returncode": 0,
                        "duration_sec": 3.5,
                        "command_info": {"respect_task_argv": True},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    events_path = tmp_path / "events.jsonl"
    events_path.write_text(
        "\n".join(
            (
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {"type": "agent_message"},
                    }
                ),
                json.dumps(
                    {
                        "type": "turn.completed",
                        "usage": {"input_tokens": 100, "output_tokens": 20},
                    }
                ),
            )
        )
        + "\n",
        encoding="utf-8",
    )
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps({"value": "ok"}), encoding="utf-8")

    validate_payload_against_schema({"value": "ok"}, schema)
    report = build_canary_acceptance_report(
        schema_path=schema_path,
        status_path=status_path,
        event_log_path=events_path,
        result_path=result_path,
        task_code="CANARY-1",
        max_input_tokens=200,
        max_output_tokens=50,
    )
    assert report["status"] == "ready_for_batch_fanout"
    assert report["tool_event_count"] == 0

    result_path.write_text(json.dumps({"value": "ok", "extra": 1}), encoding="utf-8")
    with pytest.raises(ValueError, match="存在额外字段"):
        build_canary_acceptance_report(
            schema_path=schema_path,
            status_path=status_path,
            event_log_path=events_path,
            result_path=result_path,
            task_code="CANARY-1",
            max_input_tokens=200,
            max_output_tokens=50,
        )

    result_path.write_text(json.dumps({"value": "ok"}), encoding="utf-8")
    events_path.write_text(
        json.dumps(
            {
                "type": "item.completed",
                "item": {"type": "command_execution"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="工具或非输出事件"):
        build_canary_acceptance_report(
            schema_path=schema_path,
            status_path=status_path,
            event_log_path=events_path,
            result_path=result_path,
            task_code="CANARY-1",
            max_input_tokens=200,
            max_output_tokens=50,
        )


def test_dynasty_neutral_governance_prepare_and_audit_stay_rule_neutral(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "han.txt"
    source_text = "文帝除肉刑，[12]丞相张苍议定律令，\n诏从其议。"
    source_path.write_text(source_text, encoding="utf-8")
    schema_path = ROOT / "config" / "dynasty-neutral-governance-output.schema.json"
    output_root = tmp_path / "scan"
    preparation = prepare_scan(
        {
            "pages": [
                {
                    "dynasty": "han",
                    "source_genre": "cross_dynastic_institutional_compendium",
                    "source_work": "测试政书",
                    "target_scope": "只抽取汉代实际发生的事实",
                    "page_title": "汉书/卷023",
                    "revision_ref": "23",
                    "text_path": str(source_path),
                }
            ]
        },
        output_root=output_root,
        output_schema_path=schema_path,
    )
    task = preparation["tasks"][0]
    prompt = Path(output_root / "prompts" / f"{task['task_code']}.md").read_text(
        encoding="utf-8"
    )
    assert "EXECUTION_MODE: STRUCTURED_OUTPUT_NO_TOOLS" in prompt
    assert "规则复用建议" in prompt
    assert "跨朝代政书中的前代制度" in prompt
    assert "不得自行补右引号" in prompt
    assert "不得删除中间内容后拼接" in prompt
    assert "只抽取汉代实际发生的事实" in prompt
    assert "reuse_candidates" not in prompt

    payload = {
        "schema_version": "dynasty-neutral-governance-output-v1",
        "task_code": task["task_code"],
        "dynasty": "han",
        "source_chars": len(source_text),
        "chains": [
            {
                "chain_key": "han-wendi-corporal-punishment",
                "title": "文帝废除肉刑并议定替代律令",
                "domain": "law_and_adjudication",
                "period": "文帝时",
                "action": "文帝下令废除肉刑。",
                "implementation": "张苍议定律令，皇帝批准。",
                "observable_result": "原文未载进一步运行结果。",
                "cost_or_burden": "原文未载。",
                "affected_groups": ["受刑者"],
                "operation_status": "enacted",
                "temporal_scope": "single_event",
                "geographic_scope": "national",
                "actors": [
                    {
                        "name": "文帝",
                        "responsibility_role": "lead",
                        "contribution_phases": ["initiated", "authorized"],
                        "role_basis": "原文明示下令并批准。",
                        "quote_refs": ["q1"],
                    },
                    {
                        "name": "张苍",
                        "responsibility_role": "participant",
                        "contribution_phases": ["designed"],
                        "role_basis": "原文明示参与议定律令。",
                        "quote_refs": ["q1"],
                    },
                ],
                "evidence": [
                    {
                        "quote_ref": "q1",
                        "page_title": "汉书/卷023",
                        "revision_ref": "23",
                        "exact_quote": "文帝除肉刑，丞相张苍议定律令，诏从其议。",
                    }
                ],
                "uncertainty": "替代刑罚具体内容未载。",
            }
        ],
        "limitations": [],
    }
    (output_root / "results").mkdir(parents=True, exist_ok=True)
    (output_root / "results" / f"{task['task_code']}.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    audit = audit_scan(
        preparation,
        results_dir=output_root / "results",
        output_schema_path=schema_path,
    )
    assert audit["status"] == "accepted_shadow"
    assert audit["chain_count"] == 1
    assert audit["formal_writes"] == audit["score_writes"] == 0

    payload["chains"].append(
        {
            **payload["chains"][0],
            "chain_key": "han-wendi-invalid-quote",
            "evidence": [
                {
                    **payload["chains"][0]["evidence"][0],
                    "exact_quote": "原文中不存在的引文",
                }
            ],
        }
    )
    (output_root / "results" / f"{task['task_code']}.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    failed_audit = audit_scan(
        preparation,
        results_dir=output_root / "results",
        output_schema_path=schema_path,
    )
    assert failed_audit["status"] == "failed_closed"
    assert failed_audit["accepted_task_count"] == 0
    assert failed_audit["chain_count"] == failed_audit["quote_count"] == 0


def test_dynasty_neutral_source_increment_closes_candidate_coverage(
    tmp_path: Path,
) -> None:
    schema_path = ROOT / "config" / "dynasty-neutral-source-increment-output.schema.json"
    baseline = {
        "status": "accepted_shadow",
        "failures": [],
        "chains": [
            {
                "chain_key": "base-canal",
                "title": "分段漕运",
                "domain": "military_logistics",
                "period": "开元",
                "action": "设置仓储分段漕运",
                "implementation": "设置河阴仓",
                "observable_result": "原文未载",
                "cost_or_burden": "原文未载",
                "affected_groups": ["漕户"],
                "operation_status": "implemented",
                "temporal_scope": "long_term_pattern",
                "geographic_scope": "multi_region",
                "actors": [{"name": "裴耀卿"}],
            }
        ],
    }
    candidate = {
        "status": "accepted_shadow",
        "failures": [],
        "chains": [
            {
                **baseline["chains"][0],
                "chain_key": "candidate-canal",
                "observable_result": "三年运七百万石",
            }
        ],
    }
    preparation = prepare_comparison(
        baseline,
        candidate,
        output_root=tmp_path / "comparison",
        output_schema_path=schema_path,
    )
    assert preparation["baseline_count"] == preparation["candidate_count"] == 1
    prompt = (tmp_path / "comparison" / "prompt.md").read_text(encoding="utf-8")
    assert "same_fact_enrichment" in prompt
    payload = {
        "schema_version": "dynasty-neutral-source-increment-output-v1",
        "task_code": preparation["task_code"],
        "baseline_count": 1,
        "candidate_count": 1,
        "comparisons": [
            {
                "candidate_chain_key": "candidate-canal",
                "classification": "same_fact_enrichment",
                "baseline_chain_keys": ["base-canal"],
                "added_dimensions": ["observable_result"],
                "rationale": "补充运量。",
                "confidence": "high",
            }
        ],
        "limitations": [],
    }
    audit = audit_comparison(
        preparation,
        payload,
        output_schema_path=schema_path,
    )
    assert audit["status"] == "accepted_shadow"
    assert audit["classification_counts"] == {"same_fact_enrichment": 1}
    assert audit["formal_writes"] == audit["score_writes"] == 0

    invalid = deepcopy(payload)
    invalid["comparisons"][0]["added_dimensions"] = [
        "independent_source_attestation"
    ]
    with pytest.raises(ValueError, match="缺少实质新增维度"):
        audit_comparison(preparation, invalid, output_schema_path=schema_path)


def test_dynasty_neutral_material_settlement_coalesces_same_fact_components() -> None:
    def chain(key: str, result: str, quote: str) -> dict:
        return {
            "chain_key": key,
            "title": "分段漕运",
            "domain": "military_logistics",
            "period": "开元",
            "action": "设置仓储分段漕运",
            "implementation": "设置河阴仓",
            "observable_result": result,
            "cost_or_burden": "原文未载",
            "operation_status": "implemented",
            "temporal_scope": "long_term_pattern",
            "geographic_scope": "multi_region",
            "actors": [{"name": "裴耀卿"}],
            "evidence": [
                {
                    "page_title": key,
                    "revision_ref": "1",
                    "exact_quote": quote,
                }
            ],
        }

    baseline = {
        "status": "accepted_shadow",
        "failures": [],
        "chains": [chain("base-canal", "原文未载", "置河阴仓")],
    }
    candidate = {
        "status": "accepted_shadow",
        "failures": [],
        "chains": [
            chain("candidate-canal-a", "三年运七百万石", "三岁漕七百万石"),
            chain("candidate-canal-b", "省陆运佣钱", "省佣钱三十万缗"),
            chain("candidate-new", "渠成", "新开一渠"),
        ],
    }
    increment = {
        "status": "accepted_shadow",
        "baseline_count": 1,
        "candidate_count": 3,
        "comparisons": [
            {
                "candidate_chain_key": "candidate-canal-a",
                "classification": "same_fact_enrichment",
                "baseline_chain_keys": ["base-canal"],
                "rationale": "补运量",
                "confidence": "high",
            },
            {
                "candidate_chain_key": "candidate-canal-b",
                "classification": "same_fact_enrichment",
                "baseline_chain_keys": ["base-canal"],
                "rationale": "补成本",
                "confidence": "high",
            },
            {
                "candidate_chain_key": "candidate-new",
                "classification": "new_fact",
                "baseline_chain_keys": [],
                "rationale": "独立工程",
                "confidence": "high",
            },
        ],
    }

    report = settle_neutral_materials(baseline, candidate, increment)

    assert report["status"] == "accepted_shadow"
    assert report["settled_material_count"] == 2
    canal = next(
        row for row in report["materials"] if row["baseline_chain_keys"]
    )
    assert canal["candidate_chain_keys"] == [
        "candidate-canal-a",
        "candidate-canal-b",
    ]
    assert len(canal["fact_variants"]) == 3
    assert len(canal["evidence"]) == 3
    assert canal["episode_projection_status"] == "pending_atomization_review"
    assert report["indexes"]["by_actor"]["裴耀卿"]
    assert report["historical_episode_writes"] == report["score_writes"] == 0


def test_dynasty_neutral_material_settlement_queues_mixed_partial_overlap() -> None:
    def chain(key: str, operation_status: str) -> dict:
        return {
            "chain_key": key,
            "title": key,
            "domain": "fiscal_taxation",
            "period": "唐",
            "action": key,
            "implementation": "已执行",
            "observable_result": "原文未载",
            "cost_or_burden": "原文未载",
            "operation_status": operation_status,
            "temporal_scope": "repeated_pattern",
            "geographic_scope": "multi_region",
            "actors": [],
            "evidence": [
                {
                    "page_title": key,
                    "revision_ref": "1",
                    "exact_quote": key,
                }
            ],
        }

    baseline = {
        "status": "accepted_shadow",
        "failures": [],
        "chains": [chain("tea-tax", "implemented")],
    }
    candidate = {
        "status": "accepted_shadow",
        "failures": [],
        "chains": [chain("three-unrelated-taxes", "mixed_chain")],
    }
    increment = {
        "status": "accepted_shadow",
        "baseline_count": 1,
        "candidate_count": 1,
        "comparisons": [
            {
                "candidate_chain_key": "three-unrelated-taxes",
                "classification": "same_fact_enrichment",
                "baseline_chain_keys": ["tea-tax"],
                "rationale": "只有茶税部分重合",
                "confidence": "medium",
            }
        ],
    }

    report = settle_neutral_materials(baseline, candidate, increment)

    assert report["settled_material_count"] == 1
    assert report["review_queue_count"] == 1
    assert report["review_queue"] == [
        {
            "candidate_chain_key": "three-unrelated-taxes",
            "possible_baseline_chain_keys": ["tea-tax"],
            "rationale": "只有茶税部分重合",
            "confidence": "medium",
            "review_reason": "mixed_chain_partial_overlap_requires_atomization",
        }
    ]

def test_codex_provider_keeps_windows_runtime_identity_without_business_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("USERPROFILE", r"C:\Users\tester")
    monkeypatch.setenv("APPDATA", r"C:\Users\tester\AppData\Roaming")
    monkeypatch.setenv("SYSTEMROOT", r"C:\Windows")
    monkeypatch.setenv("COMSPEC", r"C:\Windows\System32\cmd.exe")
    monkeypatch.setenv("EMPEROR_EVAL_V4_DSN", "postgresql://secret")

    environment = _codex_subprocess_environment()

    assert environment["USERPROFILE"] == r"C:\Users\tester"
    assert environment["APPDATA"].endswith("Roaming")
    assert environment["SYSTEMROOT"] == r"C:\Windows"
    assert environment["COMSPEC"].endswith("cmd.exe")
    assert "EMPEROR_EVAL_V4_DSN" not in environment


def test_claim_output_schema_supports_structured_qualifiers_and_empty_set() -> None:
    schema = json.loads(OUTPUT_SCHEMA.read_text(encoding="utf-8"))
    assertions = schema["properties"]["assertions"]
    item_schema = assertions["items"]
    qualifiers = item_schema["properties"]["qualifiers"]["properties"]

    assert "minItems" not in assertions
    assert assertions["maxItems"] == 64
    assert "assertion_code" not in item_schema["required"]
    assert {
        "responsibility_family",
        "office_or_domain",
        "outcome",
        "normalized_time",
    } <= set(qualifiers)


def test_wikisource_provider_selects_subject_plan_and_fetches_page_once(
    tmp_path: Path,
) -> None:
    sections = []
    for section_id in ("任命", "结果"):
        sections.append(
            {
                "page_code": "history-001",
                "page_title": "测试史书/卷一",
                "expected_revision_id": 7,
                "work_identity": "测试史书",
                "edition_identity": "测试版本",
                "source_role": "primary",
                "license_or_access_note": "test",
                "section_id": section_id,
                "section_heading": section_id,
                "passages": [
                    {
                        "seed_code": section_id,
                        "anchor_start": "甲",
                        "anchor_end": "。",
                        "passage_kind": "atomic",
                        "selection_reason": [section_id],
                    }
                ],
                "window_policy": {
                    "version": "test-window-v1",
                    "sentence_radius_before": 0,
                    "sentence_radius_after": 0,
                    "context_chars_before": 0,
                    "context_chars_after": 0,
                },
            }
        )
    plan = {
        "schema_version": 1,
        "provider": "wikisource_revision_plan",
        "subject_ref": "PER-A",
        "sections": sections,
    }
    (tmp_path / "a.yml").write_text(
        yaml.safe_dump(plan, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    (tmp_path / "b.yml").write_text(
        yaml.safe_dump(
            {**plan, "subject_ref": "PER-B"},
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    calls = []
    raw_text = "甲。"

    def fetch(**kwargs):
        calls.append(kwargs)
        return WikisourcePageSnapshot(
            page_code="history-001",
            requested_title="测试史书/卷一",
            canonical_title="测试史书/卷一",
            canonical_url="https://example.invalid/history-001",
            revision_id=7,
            revision_timestamp="2026-07-14T00:00:00Z",
            retrieved_at="2026-07-14T00:00:01Z",
            raw_text=raw_text,
            content_hash=sha256(raw_text.encode("utf-8")).hexdigest(),
        )

    request = SourceCacheRequest(
        request_id="SRC-PLAN-1",
        idempotency_key="source-plan:1",
        subject=SourceCacheSubject("PER-A", "甲", ()),
        evaluation_context={"purpose": "test"},
        source_hints=("测试史书/卷一",),
        required_source_families=("primary_text",),
        mode="ensure",
        source_policy_version="test-source-policy-v1",
        requested_at="2026-07-14T00:00:00+08:00",
    )

    batch = WikisourceSourceMaterialProvider(
        plan_path=tmp_path,
        fetch=fetch,
    ).load(request)

    assert len(batch.sections) == 2
    assert batch.network_request_count == 1
    assert len(calls) == 1


def test_wikisource_ensure_uses_network_once_then_replays_cache(
    tmp_path: Path,
) -> None:
    request = {
        "request_id": "SRC-ONLINE-1",
        "idempotency_key": "source-online:1",
        "subject": {
            "person_or_ruler_ref": "PER-A",
            "canonical_name": "甲",
            "aliases": [],
        },
        "evaluation_context": {"purpose": "test"},
        "source_hints": ["测试史书/卷一"],
        "required_source_families": ["primary"],
        "mode": "ensure",
        "source_policy_version": "test-source-policy-v1",
        "requested_at": "2026-07-14T00:00:00+08:00",
    }
    plan = {
        "schema_version": 1,
        "provider": "wikisource_revision_plan",
        "subject_ref": "PER-A",
        "sections": [
            {
                "page_code": "history-001",
                "page_title": "测试史书/卷一",
                "expected_revision_id": 7,
                "work_identity": "测试史书",
                "edition_identity": "测试版本",
                "source_role": "primary",
                "license_or_access_note": "test",
                "section_id": "任命",
                "section_heading": "任命",
                "passages": [
                    {
                        "seed_code": "任命",
                        "anchor_start": "甲",
                        "anchor_end": "。",
                        "passage_kind": "atomic",
                        "selection_reason": ["任命"],
                    }
                ],
                "window_policy": {
                    "version": "test-window-v1",
                    "sentence_radius_before": 0,
                    "sentence_radius_after": 0,
                    "context_chars_before": 0,
                    "context_chars_after": 0,
                },
            }
        ],
    }
    request_path = tmp_path / "request.yml"
    plan_path = tmp_path / "plan.yml"
    state_path = tmp_path / "state.json"
    request_path.write_text(
        yaml.safe_dump(request, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    plan_path.write_text(
        yaml.safe_dump(plan, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    calls = []
    raw_text = "甲。"

    def fetch(**kwargs):
        calls.append(kwargs)
        return WikisourcePageSnapshot(
            page_code="history-001",
            requested_title="测试史书/卷一",
            canonical_title="测试史书/卷一",
            canonical_url="https://example.invalid/history-001",
            revision_id=7,
            revision_timestamp="2026-07-14T00:00:00Z",
            retrieved_at="2026-07-14T00:00:01Z",
            raw_text=raw_text,
            content_hash=sha256(raw_text.encode("utf-8")).hexdigest(),
        )

    first = run_wikisource_ensure(
        request_path=request_path,
        source_plan_path=plan_path,
        state_path=state_path,
        service_release_sha="a" * 40,
        fetch=fetch,
    )
    second = run_wikisource_ensure(
        request_path=request_path,
        source_plan_path=plan_path,
        state_path=state_path,
        service_release_sha="a" * 40,
        fetch=fetch,
    )

    assert first["runtime_audit"]["network_request_count"] == 1
    assert first["runtime_audit"]["cache_hit"] is False
    assert second["runtime_audit"]["network_request_count"] == 0
    assert second["runtime_audit"]["cache_hit"] is True
    assert len(calls) == 1
