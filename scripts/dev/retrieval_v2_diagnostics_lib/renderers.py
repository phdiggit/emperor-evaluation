from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from scripts.dev.retrieval_v2_import_plan import write_json
from scripts.dev.retrieval_v2_diagnostics_lib.common import short_text, text

def render_markdown(payload: Mapping[str, Any]) -> str:
    if payload.get("command") == "score-chain":
        return render_score_chain_markdown(payload)
    lines = [
        "# retrieval_v2 diagnostics",
        "",
        f"- command: `{payload.get('command', '')}`",
        f"- ok: `{str(payload.get('ok')).lower()}`",
    ]
    scope = payload.get("scope")
    if isinstance(scope, Mapping):
        lines.append(
            f"- scope: `{scope.get('scope')}` / `{scope.get('item_code')}` / `{scope.get('rule_code')}` / `{scope.get('formula_code')}`"
        )
    lines.append("")
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else payload
    totals = summary.get("totals") if isinstance(summary, Mapping) else None
    if isinstance(totals, Mapping):
        lines.extend(["## Summary", "", "| key | value |", "| --- | ---: |"])
        for key, value in totals.items():
            lines.append(f"| {key} | {value} |")
        lines.append("")
    checks: list[Mapping[str, Any]] = []
    for key in ("checks", "next_actions"):
        if isinstance(payload.get(key), list):
            checks.extend(payload.get(key) or [])
    for group_key in ("readiness", "coverage", "duplicates"):
        group = payload.get(group_key)
        if isinstance(group, Mapping):
            checks.extend(group.get("checks") or [])
            checks.extend(group.get("blockers") or [])
            checks.extend(group.get("warnings") or [])
            checks.extend(group.get("downstream_required") or [])
    active_checks = [row for row in checks if int(row.get("count") or 0) > 0]
    if active_checks:
        lines.extend(["## Active Checks", "", "| code | severity | count | owner | next |", "| --- | --- | ---: | --- | --- |"])
        seen: set[str] = set()
        for row in active_checks:
            code = text(row.get("code"))
            if code in seen:
                continue
            seen.add(code)
            lines.append(
                f"| `{code}` | `{row.get('severity') or row.get('status')}` | {row.get('count')} | "
                f"`{row.get('owner', '')}` | `{row.get('next_command', '')}` |"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"

def factor_summary(material: Mapping[str, Any]) -> str:
    choices = material.get("factor_choices")
    if not isinstance(choices, list):
        return ""
    parts = []
    for choice in choices:
        if not isinstance(choice, Mapping):
            continue
        label = text(choice.get("option_label")) or text(choice.get("option_code"))
        parts.append(f"{choice.get('factor_name')}={label}({choice.get('value_num')})")
    return "; ".join(parts)

def render_score_chain_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# retrieval_v2 score chain",
        "",
        f"- command: `{payload.get('command', '')}`",
        f"- ok: `{str(payload.get('ok')).lower()}`",
    ]
    scope = payload.get("scope")
    if isinstance(scope, Mapping):
        target_parts: list[str] = []
        if scope.get("target_code"):
            target_parts.append(text(scope.get("target_code")))
        target_parts.extend(text(value) for value in scope.get("target_codes") or [] if text(value))
        emperor_parts = [text(value) for value in scope.get("emperors") or [] if text(value)]
        target_part = f" / target=`{', '.join(target_parts)}`" if target_parts else ""
        emperor_part = f" / emperor=`{', '.join(emperor_parts)}`" if emperor_parts else ""
        lines.append(
            f"- scope: `{scope.get('scope')}` / `{scope.get('item_code')}` / `{scope.get('rule_code')}` / `{scope.get('formula_code')}`{target_part}{emperor_part}"
        )
    formula_params = payload.get("formula_params")
    if isinstance(formula_params, Mapping) and formula_params:
        lines.append(
            "- formula: "
            + ", ".join(f"`{key}={value}`" for key, value in formula_params.items() if key != "coverage")
        )
    lines.append("")
    totals = payload.get("totals")
    if isinstance(totals, Mapping):
        lines.extend(["## Summary", "", "| key | value |", "| --- | ---: |"])
        for key, value in totals.items():
            lines.append(f"| {key} | {value} |")
        lines.append("")
    observations = payload.get("observations")
    active_observations = [
        row for row in observations or [] if isinstance(row, Mapping) and int(row.get("count") or 0) > 0
    ]
    if active_observations:
        lines.extend(["## Observations", "", "| code | severity | count | description |", "| --- | --- | ---: | --- |"])
        for row in active_observations:
            lines.append(
                f"| `{row.get('code')}` | `{row.get('severity')}` | {row.get('count')} | {text(row.get('description'))} |"
            )
        lines.append("")
        for row in active_observations:
            examples = row.get("examples")
            if not isinstance(examples, list) or not examples:
                continue
            lines.extend([f"### {row.get('code')}", "", "| target | object | side | detail |", "| --- | --- | --- | --- |"])
            for example in examples[:5]:
                if not isinstance(example, Mapping):
                    continue
                detail = text(example.get("claim_summary")) or (
                    f"positive={example.get('positive_signal')} negative={example.get('negative_signal')}"
                )
                lines.append(
                    f"| {example.get('emperor_name')} | {example.get('object_name', '')} | "
                    f"`{example.get('side', '')}` | {short_text(detail, max_chars=110)} |"
                )
            lines.append("")
    targets = payload.get("targets")
    if isinstance(targets, list) and targets:
        lines.extend(
            [
                "## Target Signals",
                "",
                "| target | emperor | positive | negative | scored | supporting | excluded | materials |",
                "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for target in targets:
            if not isinstance(target, Mapping):
                continue
            lines.append(
                f"| `{target.get('target_code')}` | {target.get('emperor_name')} | "
                f"{target.get('positive_signal')} | {target.get('negative_signal')} | "
                f"{target.get('scored_judgment_count')} | {target.get('supporting_judgment_count')} | "
                f"{target.get('excluded_judgment_count')} | {len(target.get('materials') or [])} |"
            )
        lines.append("")
        for target in targets:
            if not isinstance(target, Mapping):
                continue
            lines.extend([f"## {target.get('emperor_name')} `{target.get('target_code')}`", ""])
            object_scores = target.get("object_side_scores")
            if isinstance(object_scores, Mapping):
                lines.extend(["### Object Side Scores", "", "| side | object | score | materials |", "| --- | --- | ---: | ---: |"])
                for side in ("positive", "negative"):
                    for row in object_scores.get(side) or []:
                        if not isinstance(row, Mapping):
                            continue
                        object_label = text(row.get("object_name")) or text(row.get("object_id"))
                        lines.append(f"| `{side}` | {object_label} | {row.get('score')} | {row.get('material_count')} |")
                lines.append("")
            top_rows = target.get("top_materials")
            if isinstance(top_rows, list) and top_rows:
                lines.extend(["### Top Materials", "", "| side | object | abs | raw | factors | claim |", "| --- | --- | ---: | ---: | --- | --- |"])
                for material in top_rows:
                    if not isinstance(material, Mapping):
                        continue
                    lines.append(
                        f"| `{material.get('side')}` | {material.get('object_name')} | {material.get('abs_score')} | "
                        f"{material.get('raw_score')} | {short_text(factor_summary(material), max_chars=90)} | "
                        f"{short_text(material.get('claim_summary'), max_chars=90)} |"
                    )
                lines.append("")
    return "\n".join(lines).rstrip() + "\n"

def write_report(output_json: Path, output_md: Path | None, payload: Mapping[str, Any]) -> None:
    write_json(output_json, payload)
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_markdown(payload), encoding="utf-8")

