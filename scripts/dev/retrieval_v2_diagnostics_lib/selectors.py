from __future__ import annotations

from typing import Any, Sequence

from scripts.dev.retrieval_v2_diagnostics_lib.common import RetrievalV2DiagnosticsError, text

SUPPORTED_SELECTOR_TYPES = {"person"}
SUPPORTED_PERSON_ROLES = {"emperor"}

def normalized_list(values: Sequence[str] | None) -> list[str]:
    return [text(value) for value in values or [] if text(value)]

def build_score_chain_selectors(
    *,
    target_code: str = "",
    target_codes: Sequence[str] | None = None,
    emperors: Sequence[str] | None = None,
    selector_type: str = "",
    selector_role: str = "",
    names: Sequence[str] | None = None,
) -> dict[str, Any]:
    code_values = normalized_list(target_codes)
    if text(target_code):
        code_values.append(text(target_code))
    emperor_values = normalized_list(emperors)
    selector_names = normalized_list(names)
    selectors: list[dict[str, Any]] = []
    if emperor_values:
        selectors.append({"type": "person", "role": "emperor", "names": sorted(set(emperor_values)), "source": "--emperor"})
    if selector_names:
        normalized_type = text(selector_type) or "person"
        normalized_role = text(selector_role) or "emperor"
        if normalized_type not in SUPPORTED_SELECTOR_TYPES:
            raise RetrievalV2DiagnosticsError(f"unsupported selector type for score-chain: {normalized_type}")
        if normalized_type == "person" and normalized_role not in SUPPORTED_PERSON_ROLES:
            raise RetrievalV2DiagnosticsError(f"unsupported person selector role for score-chain: {normalized_role}")
        if normalized_type == "person" and normalized_role == "emperor":
            emperor_values.extend(selector_names)
        selectors.append({"type": normalized_type, "role": normalized_role, "names": sorted(set(selector_names)), "source": "--type/--role/--name"})
    return {
        "target_codes": sorted(set(code_values)),
        "emperors": sorted(set(emperor_values)),
        "selectors": selectors,
    }

def score_chain_filter_values(
    *,
    target_code: str = "",
    target_codes: Sequence[str] | None = None,
    emperors: Sequence[str] | None = None,
    selector_type: str = "",
    selector_role: str = "",
    names: Sequence[str] | None = None,
) -> tuple[list[str], list[str]]:
    selector_payload = build_score_chain_selectors(
        target_code=target_code,
        target_codes=target_codes,
        emperors=emperors,
        selector_type=selector_type,
        selector_role=selector_role,
        names=names,
    )
    return selector_payload["target_codes"], selector_payload["emperors"]

def score_chain_params(
    item_code: str,
    rule_code: str,
    formula_code: str,
    target_codes: Sequence[str],
    emperors: Sequence[str],
) -> tuple[Any, ...]:
    return (
        item_code,
        item_code,
        item_code,
        rule_code,
        rule_code,
        formula_code,
        list(target_codes),
        list(target_codes),
        list(emperors),
        list(emperors),
    )
