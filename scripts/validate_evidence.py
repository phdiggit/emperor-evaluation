from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

JSONL_FILES = [
    DATA_DIR / "evidence_cards.jsonl",
    DATA_DIR / "sources.jsonl",
    DATA_DIR / "events.jsonl",
    DATA_DIR / "trigger_terms.jsonl",
    DATA_DIR / "search_logs.jsonl",
]

VALID_POLARITIES = {"positive", "negative"}
VALID_TIERS = {"core", "extended"}
VALID_SEARCH_RESULT_STATUSES = {
    "checked_no_hard_evidence",
    "evidence_found_card_created",
    "lead_needs_source_review",
    "routed_to_adjacent_item",
}

REQUIRED_EVIDENCE_FIELDS = [
    "evidence_id",
    "person",
    "item",
    "subitem",
    "polarity",
    "strength",
    "human_level",
    "source_id",
    "quote_short",
    "interpretation",
    "trigger_family",
    "trigger_terms",
    "cross_item_split",
    "scoring_effect",
    "verification_status",
]


def read_jsonl(path: Path, errors: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        errors.append(f"{path}: file does not exist")
        return rows

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError as exc:
                errors.append(f"{path}: line {line_number}: invalid JSON: {exc.msg}")
                continue
            if not isinstance(value, dict):
                errors.append(f"{path}: line {line_number}: JSONL row must be an object")
                continue
            rows.append(value)
    return rows


def is_filled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def validate_evidence_card(row: dict[str, Any], line_label: str, source_ids: set[str], errors: list[str]) -> None:
    for field in REQUIRED_EVIDENCE_FIELDS:
        if field not in row:
            errors.append(f"{line_label}: missing required field: {field}")

    polarity = row.get("polarity")
    if polarity not in VALID_POLARITIES:
        errors.append(f"{line_label}: polarity must be positive or negative")

    strength = row.get("strength")
    if strength not in {1, 2, 3, 4}:
        errors.append(f"{line_label}: strength must be one of 1, 2, 3, 4")

    human_level = row.get("human_level")
    if strength == 4 and polarity == "positive" and human_level != "极正":
        errors.append(f"{line_label}: strength=4 and polarity=positive requires human_level=极正")
    if strength == 4 and polarity == "negative" and human_level != "极负":
        errors.append(f"{line_label}: strength=4 and polarity=negative requires human_level=极负")

    if polarity == "negative" and human_level in {"强负", "极负"}:
        if not (is_filled(row.get("cross_item_split")) or is_filled(row.get("scoring_effect"))):
            errors.append(f"{line_label}: 强负 or 极负 evidence requires cross_item_split or scoring_effect")

    source_id = row.get("source_id")
    if source_id and source_id not in source_ids:
        errors.append(f"{line_label}: source_id not found in sources.jsonl: {source_id}")


def validate_trigger_term(
    row: dict[str, Any],
    line_label: str,
    seen_term_ids: set[str],
    errors: list[str],
) -> None:
    polarity = row.get("polarity")
    if polarity is not None and polarity not in VALID_POLARITIES:
        errors.append(f"{line_label}: polarity must be positive or negative")

    tier = row.get("tier")
    if tier is not None and tier not in VALID_TIERS:
        errors.append(f"{line_label}: tier must be core or extended")

    term_id = row.get("term_id")
    if is_filled(term_id):
        if term_id in seen_term_ids:
            errors.append(f"{line_label}: duplicate term_id: {term_id}")
        seen_term_ids.add(term_id)


def validate_search_log(row: dict[str, Any], line_label: str, errors: list[str]) -> None:
    polarity = row.get("polarity")
    if polarity is not None and polarity not in VALID_POLARITIES:
        errors.append(f"{line_label}: polarity must be positive or negative")

    result_status = row.get("result_status")
    if result_status is not None and result_status not in VALID_SEARCH_RESULT_STATUSES:
        errors.append(f"{line_label}: result_status is not a suggested value: {result_status}")


def nonblank_line_numbers(path: Path) -> list[int]:
    with path.open("r", encoding="utf-8") as handle:
        return [number for number, line in enumerate(handle, start=1) if line.strip()]


def validate() -> list[str]:
    errors: list[str] = []
    parsed = {path: read_jsonl(path, errors) for path in JSONL_FILES}

    sources = parsed[DATA_DIR / "sources.jsonl"]
    source_ids = {row.get("source_id") for row in sources if is_filled(row.get("source_id"))}

    evidence_path = DATA_DIR / "evidence_cards.jsonl"
    evidence_line_numbers = nonblank_line_numbers(evidence_path)

    for row, line_number in zip(parsed[evidence_path], evidence_line_numbers):
        validate_evidence_card(row, f"{evidence_path}: line {line_number}", source_ids, errors)

    trigger_terms_path = DATA_DIR / "trigger_terms.jsonl"
    trigger_term_line_numbers = nonblank_line_numbers(trigger_terms_path)
    seen_term_ids: set[str] = set()
    for row, line_number in zip(parsed[trigger_terms_path], trigger_term_line_numbers):
        validate_trigger_term(row, f"{trigger_terms_path}: line {line_number}", seen_term_ids, errors)

    search_logs_path = DATA_DIR / "search_logs.jsonl"
    search_log_line_numbers = nonblank_line_numbers(search_logs_path)
    for row, line_number in zip(parsed[search_logs_path], search_log_line_numbers):
        validate_search_log(row, f"{search_logs_path}: line {line_number}", errors)

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
