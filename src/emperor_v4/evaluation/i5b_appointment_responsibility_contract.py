from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


ROOT = Path(__file__).resolve().parents[3]
SCHEMA_VERSION = "i5b-appointment-responsibility-contract-v1"
REPORT_SCHEMA_VERSION = "i5b-appointment-responsibility-projection-v1"
Q = Decimal("0.000001")
SUBJECT_KINDS = {"person", "institution", "responsibility_group"}
AUTHORITY_SCOPES = {
    "nominal": "nominal_or_light",
    "local_bounded": "real_bounded",
    "major_affairs": "major_affairs",
    "national_or_systemic": "critical_national_or_long_term",
}
OUTCOME_OPTIONS = {
    "normal_success",
    "major_success",
    "exceptional_success",
    "bounded_control_failure",
    "limited_direct_damage",
    "major_direct_damage",
    "structural_continuing_damage",
}


def _load(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _resolve(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _hash(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _rounded(value: Decimal) -> str:
    return format(value.quantize(Q), "f")


def _accepted_assertions(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(assertion["assertion_code"]): assertion
        for unit in payload.get("units") or ()
        for assertion in unit.get("assertion_drafts") or ()
        if assertion.get("formal_acceptance_disposition") == "accept"
    }


def _assert_refs(
    refs: Sequence[object], *, accepted: Mapping[str, Any], label: str
) -> list[str]:
    values = [str(ref) for ref in refs]
    if not values or len(values) != len(set(values)):
        raise ValueError(f"{label} Assertion refs 必须非空且唯一")
    unknown = sorted(set(values) - set(accepted))
    if unknown:
        raise ValueError(f"{label} 引用了未接受 Assertion: {unknown}")
    return values


def _source_refs(
    assertion_refs: Sequence[str], accepted: Mapping[str, Mapping[str, Any]]
) -> list[str]:
    return sorted(
        {
            str(accepted[ref]["source_passage_ref"])
            for ref in assertion_refs
            if accepted[ref].get("source_passage_ref")
        }
    )


def _factor_values(
    policy: Mapping[str, Any], options: Mapping[str, str]
) -> tuple[dict[str, str], Decimal]:
    appointment = policy["rules"]["appointment_delegation"]
    evidence = policy["evidence_factor"]
    values: dict[str, Decimal] = {
        "appointment_importance": Decimal(
            str(appointment["appointment_importance"][options["appointment_importance"]])
        ),
        "appointment_effect": Decimal(
            str(appointment["appointment_effect"][options["appointment_effect"]])
        ),
        "continuity_factor": Decimal(
            str(appointment["continuity_factor"][options["continuity_factor"]])
        ),
        "attribution_factor": Decimal(
            str(evidence["attribution_factor"][options["attribution_factor"]])
        ),
        "source_factor": Decimal(
            str(evidence["source_factor"][options["source_factor"]])
        ),
        "context_factor": Decimal(
            str(evidence["context_factor"][options["context_factor"]])
        ),
    }
    evidence_value = max(
        Decimal(str(evidence["minimum"])),
        min(
            values["attribution_factor"]
            * values["source_factor"]
            * values["context_factor"],
            Decimal(str(evidence["maximum"])),
        ),
    )
    magnitude = (
        abs(values["appointment_importance"])
        * abs(values["appointment_effect"])
        * abs(values["continuity_factor"])
        * evidence_value
    )
    magnitude = min(magnitude, Decimal("4"))
    values["evidence_factor"] = evidence_value
    return {key: _rounded(value) for key, value in values.items()}, magnitude


def _continuity_option(unit: Mapping[str, Any]) -> str:
    authorization_count = int(unit["distinct_authorization_count"])
    observation_count = len(unit["operation_observations"])
    if authorization_count >= 2:
        return "long_term_multi_stage"
    if observation_count >= 2:
        return "stable"
    return "short_or_one_off"


def build_appointment_responsibility_projection(manifest_path: Path) -> dict[str, Any]:
    manifest_path = _resolve(str(manifest_path))
    manifest = _load(manifest_path)
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("任用责任链合同 schema_version 不匹配")
    acceptance_path = _resolve(str(manifest["formal_acceptance_source"]))
    policy_path = _resolve(str(manifest["policy"]))
    acceptance = _load(acceptance_path)
    policy = _load(policy_path)
    accepted = _accepted_assertions(acceptance)
    materials: list[dict[str, Any]] = []
    insufficient: list[dict[str, Any]] = []
    seen_material_ids: set[str] = set()

    for unit in manifest.get("units") or ():
        material_id = str(unit["material_id"])
        if material_id in seen_material_ids:
            raise ValueError(f"责任链 material_id 重复: {material_id}")
        seen_material_ids.add(material_id)
        subject = unit.get("responsibility_subject") or {}
        if subject.get("kind") not in SUBJECT_KINDS:
            raise ValueError(f"{material_id} responsibility_subject.kind 非法")
        if not str(subject.get("ref") or "") or not str(subject.get("label") or ""):
            raise ValueError(f"{material_id} 责任主体缺失")
        attribution_refs = _assert_refs(
            unit.get("ruler_attribution_assertion_refs") or (),
            accepted=accepted,
            label=f"{material_id}.ruler_attribution",
        )
        boundary = unit.get("authority_boundary") or {}
        scope = str(boundary.get("scope") or "")
        if scope not in AUTHORITY_SCOPES:
            raise ValueError(f"{material_id} authority_boundary.scope 非法")
        boundary_refs = _assert_refs(
            boundary.get("assertion_refs") or (),
            accepted=accepted,
            label=f"{material_id}.authority_boundary",
        )
        observations = list(unit.get("operation_observations") or ())
        if not observations:
            insufficient.append(
                {
                    "material_id": material_id,
                    "subject": str(subject["label"]),
                    "rule_evidence_unit_ref": str(unit["unit_ref"]),
                    "missing_inputs": ["actual_operation_observation"],
                    "judge_reason": "已确认责任主体和权限边界，但没有实际运行观察，不进入数值候选集。",
                }
            )
            continue
        observation_refs: list[str] = []
        for index, observation in enumerate(observations, start=1):
            observation_refs.extend(
                _assert_refs(
                    observation.get("assertion_refs") or (),
                    accepted=accepted,
                    label=f"{material_id}.operation_observation[{index}]",
                )
            )
        effect = str(unit.get("outcome_assessment") or "")
        if effect not in OUTCOME_OPTIONS:
            raise ValueError(f"{material_id} outcome_assessment 非法")
        side = "negative" if effect in {
            "bounded_control_failure",
            "limited_direct_damage",
            "major_direct_damage",
            "structural_continuing_damage",
        } else "positive"
        option_codes = {
            "appointment_importance": AUTHORITY_SCOPES[scope],
            "appointment_effect": effect,
            "continuity_factor": _continuity_option(unit),
            "attribution_factor": "direct",
            "source_factor": "complete_direct_chain",
            "context_factor": "core_mechanism_direct",
        }
        values, magnitude = _factor_values(policy, option_codes)
        all_refs = sorted(set(attribution_refs + boundary_refs + observation_refs))
        materials.append(
            {
                "material_id": material_id,
                "side": side,
                "subject": str(subject["label"]),
                "subject_kind": str(subject["kind"]),
                "object_ref": str(subject["ref"]),
                "rule_evidence_unit_ref": str(unit["unit_ref"]),
                "factor_option_codes": option_codes,
                "factor_values": values,
                "material_magnitude": _rounded(magnitude),
                "fact": str(unit["fact_summary"]),
                "assertion_refs": all_refs,
                "source_refs": _source_refs(all_refs, accepted),
                "duplicate_boundary": str(unit["duplicate_boundary"]),
            }
        )

    report: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "appointment_responsibility_projection_complete",
        "task_code": str(manifest["task_code"]),
        "ruler": str(manifest["ruler"]),
        "ruler_ref": str(manifest["ruler_ref"]),
        "window": str(manifest["window"]),
        "contract_ref": (
            str(manifest_path.relative_to(ROOT))
            if manifest_path.is_relative_to(ROOT)
            else manifest_path.as_posix()
        ),
        "contract_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "policy_ref": str(manifest["policy"]),
        "policy_sha256": hashlib.sha256(policy_path.read_bytes()).hexdigest(),
        "formal_acceptance_ref": str(manifest["formal_acceptance_source"]),
        "formal_acceptance_sha256": hashlib.sha256(
            acceptance_path.read_bytes()
        ).hexdigest(),
        "materials": materials,
        "insufficient_units": insufficient,
        "summary": {
            "unit_count": len(manifest.get("units") or ()),
            "eligible_material_count": len(materials),
            "insufficient_unit_count": len(insufficient),
        },
        "declarations": {
            "person_only_contract": False,
            "institution_or_group_subject_supported": True,
            "actual_operation_observation_required": True,
            "specific_appointee_required": False,
            "model_call_count": 0,
            "database_write_count": 0,
            "formal_score": None,
            "tier": None,
            "ranking": None,
        },
    }
    report["report_sha256"] = _hash(report)
    return report


def render_appointment_responsibility_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        f"# {report['ruler']}任用责任链证据合同投影",
        "",
        "| 状态 | 数量 |",
        "|---|---:|",
        f"| 合格责任链材料 | {report['summary']['eligible_material_count']} |",
        f"| 证据不足责任链 | {report['summary']['insufficient_unit_count']} |",
        "",
        "## 合格材料",
        "",
        "| 责任主体 | 主体类型 | 方向 | 材料分 | 计分事实 |",
        "|---|---|---|---:|---|",
    ]
    for row in report["materials"]:
        lines.append(
            f"| {row['subject']} | {row['subject_kind']} | {row['side']} | "
            f"{row['material_magnitude']} | {row['fact']} |"
        )
    lines.extend(["", "## 证据不足", "", "| 责任主体 | 缺口 | Judge理由 |", "|---|---|---|"])
    for row in report["insufficient_units"]:
        lines.append(
            f"| {row['subject']} | {'、'.join(row['missing_inputs'])} | {row['judge_reason']} |"
        )
    lines.extend(["", "本报告不生成45分、tier或排名。", ""])
    return "\n".join(lines)


def write_appointment_responsibility_projection(
    *, manifest_path: Path, output_json: Path, output_markdown: Path
) -> dict[str, Any]:
    report = build_appointment_responsibility_projection(manifest_path)
    output_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    output_markdown.write_text(
        render_appointment_responsibility_markdown(report), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    args = parser.parse_args()
    write_appointment_responsibility_projection(
        manifest_path=args.manifest,
        output_json=args.output_json,
        output_markdown=args.output_md,
    )


if __name__ == "__main__":
    main()
