from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Sequence


ROOT = Path(__file__).resolve().parents[2]
I5B_RULE_DOC = (
    ROOT
    / "docs"
    / "\u5206\u9879\u89c4\u5219"
    / "\u7b2c\u4e94\u9879\u7edf\u6cbb\u8005\u653f\u6cbb\u7d20\u8d28"
    / "B\u7528\u4eba\u4e0e\u6388\u6743.md"
)
DEFAULT_FACTOR_DOC = ROOT / "docs" / "\u8bc1\u636e\u89c4\u5219" / "\u8bc1\u636e\u7c07\u8ba1\u7b97\u516c\u5f0f.md"

ITEM_CODE = "I5B"
DEFAULT_DSN_ENV = "EMPEROR_EVAL_RETRIEVAL_V2_DSN"
DEFAULT_FORMULA_CODE = "evidence_cluster_signal_v3"
DEFAULT_FACTOR_NAMES = {
    "attribution_factor",
    "source_factor",
    "context_factor",
}
KNOWN_I5B_RULE_CODES = {
    "talent_discovery",
    "appointment_delegation",
    "team_building",
    "tolerate_talent",
    "anti_nepotism",
}
RETIRED_FACTOR_NAMES = {
    "founder_pressure",
    "retention_signal",
    "certainty_factor",
    "spillover_factor",
    "disposition_severity",
}
COMPARISON_KEYS = (
    "item_code",
    "rule_code",
    "formula_code",
    "factor_name",
    "factor_scope",
    "label",
    "value_num",
)


@dataclass(frozen=True)
class FactorOption:
    item_code: str
    rule_code: str
    formula_code: str
    factor_name: str
    factor_scope: str
    label: str
    value_num: Decimal
    sort_no: int
    source_doc: str
    source_heading: str
    source_line: int
    description: str = ""
    note: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "item_code": self.item_code,
            "rule_code": self.rule_code,
            "formula_code": self.formula_code,
            "factor_name": self.factor_name,
            "factor_scope": self.factor_scope,
            "label": self.label,
            "value_num": format_decimal(self.value_num),
            "sort_no": self.sort_no,
            "source_doc": self.source_doc,
            "source_heading": self.source_heading,
            "source_line": self.source_line,
            "description": self.description,
            "note": self.note,
        }


def format_decimal(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text == "-0":
        return "0"
    return text


def repo_relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def clean_cell(value: str) -> str:
    text = value.strip().replace("<br>", " ").replace("<br/>", " ")
    if len(text) >= 2 and text.startswith("`") and text.endswith("`"):
        text = text[1:-1]
    return text.strip()


def split_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return []
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def is_separator_row(cells: Sequence[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells)


def parse_decimal_cell(value: str) -> Decimal | None:
    text = clean_cell(value)
    if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text):
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def rule_code_from_heading(heading: str, allowed_rule_codes: set[str] | None = None) -> str:
    match = re.search(r"`([^`]+)`", heading)
    if not match:
        return ""
    code = match.group(1).strip()
    if allowed_rule_codes is not None:
        return code if code in allowed_rule_codes else ""
    if re.fullmatch(r"[a-z][a-z0-9_]*", code):
        return code
    return ""


def normalized_factor_name(raw_factor_name: str) -> str:
    factor_name = clean_cell(raw_factor_name)
    if "->" not in factor_name:
        return factor_name
    return clean_cell(factor_name.rsplit("->", 1)[1])


def factor_scope_for(rule_code: str, factor_name: str, raw_factor_name: str = "") -> str:
    source_name = clean_cell(raw_factor_name or factor_name)
    if source_name.startswith("obj_attrs.") or re.match(r"^obj_attrs\.[^`]+->", source_name):
        return "attribute_mapping"
    if rule_code == "talent_discovery" and factor_name == "talent_quality_factor":
        return "attribute_mapping"
    if rule_code == "team_building":
        return "team"
    if rule_code:
        return "rule"
    return "shared"


def extract_formula_code(text: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if "\u5f53\u524d\u8bc1\u636e\u7c07\u516c\u5f0f\u7248\u672c" not in line:
            continue
        for candidate in lines[index + 1 : index + 10]:
            cleaned = candidate.strip().strip("`").strip()
            if cleaned.startswith("evidence_cluster"):
                return cleaned
    return DEFAULT_FORMULA_CODE


def option_from_cells(cells: Sequence[str]) -> tuple[str, Decimal, str] | None:
    if len(cells) < 2:
        return None

    first_value = parse_decimal_cell(cells[0])
    if first_value is not None:
        label = clean_cell(cells[1])
        note = option_note(label, clean_cell(cells[2]) if len(cells) >= 3 else "")
        return label, first_value, note

    second_value = parse_decimal_cell(cells[1])
    if second_value is not None:
        label = clean_cell(cells[0])
        note = option_note(label, clean_cell(cells[2]) if len(cells) >= 3 else "")
        return label, second_value, note

    return None


def option_note(label: str, note: str) -> str:
    cleaned = clean_cell(note)
    label_norm = clean_cell(label).strip("。；;")
    note_norm = cleaned.strip("。；;")
    if not cleaned or note_norm == label_norm:
        return ""
    return cleaned


def parse_i5b_rule_doc(
    path: Path = I5B_RULE_DOC,
    *,
    item_code: str = ITEM_CODE,
    allowed_rule_codes: set[str] | None = KNOWN_I5B_RULE_CODES,
) -> list[FactorOption]:
    text = path.read_text(encoding="utf-8")
    formula_code = extract_formula_code(text)
    source_doc = repo_relative(path)
    rows: list[FactorOption] = []
    sort_counters: defaultdict[tuple[str, str], int] = defaultdict(int)

    current_heading = ""
    current_rule_code = ""
    current_factor = ""
    current_factor_raw = ""
    table_header: list[str] | None = None
    in_evidence_factor_section = False

    for line_no, line in enumerate(text.splitlines(), start=1):
        h2_match = re.match(r"^##\s+(.+?)\s*$", line)
        if h2_match:
            current_heading = h2_match.group(1).strip()
            current_rule_code = rule_code_from_heading(current_heading, allowed_rule_codes)
            in_evidence_factor_section = "证据修正因子" in current_heading
            current_factor = ""
            current_factor_raw = ""
            table_header = None
            continue

        heading_match = re.match(r"^###\s+(.+?)\s*$", line)
        if heading_match:
            current_heading = heading_match.group(1).strip()
            current_factor = ""
            current_factor_raw = ""
            table_header = None
            factor_heading_match = re.fullmatch(r"`([^`]+)`", current_heading)
            if factor_heading_match:
                current_factor_raw = factor_heading_match.group(1).strip()
                current_factor = normalized_factor_name(current_factor_raw)
                if in_evidence_factor_section:
                    current_rule_code = ""
                continue
            heading_rule_code = rule_code_from_heading(current_heading, allowed_rule_codes)
            if heading_rule_code:
                current_rule_code = heading_rule_code
            continue

        factor_match = re.match(r"^`([^`]+)`.*[\uff1a:]\s*$", line.strip())
        if factor_match:
            current_factor_raw = factor_match.group(1).strip()
            current_factor = normalized_factor_name(current_factor_raw)
            if in_evidence_factor_section:
                current_rule_code = ""
            table_header = None
            continue

        cells = split_table_row(line)
        if not cells or not current_factor:
            continue
        if is_separator_row(cells):
            continue
        if table_header is None:
            table_header = [clean_cell(cell) for cell in cells]
            continue

        option = option_from_cells(cells)
        if option is None:
            continue
        label, value_num, note = option
        if not label:
            continue

        key = (current_rule_code, current_factor)
        sort_counters[key] += 1
        rows.append(
            FactorOption(
                item_code=item_code,
                rule_code=current_rule_code,
                formula_code=formula_code,
                factor_name=current_factor,
                factor_scope=factor_scope_for(current_rule_code, current_factor, current_factor_raw),
                label=label,
                value_num=value_num,
                sort_no=sort_counters[key],
                    source_doc=source_doc,
                    source_heading=current_heading,
                    source_line=line_no,
                    note=note,
            )
        )

    return rows


def parse_default_factor_doc(path: Path = DEFAULT_FACTOR_DOC, *, item_code: str = ITEM_CODE) -> list[FactorOption]:
    text = path.read_text(encoding="utf-8")
    source_doc = repo_relative(path)
    rows: list[FactorOption] = []
    sort_counters: defaultdict[str, int] = defaultdict(int)

    for line_no, line in enumerate(text.splitlines(), start=1):
        cells = split_table_row(line)
        if len(cells) < 2 or is_separator_row(cells):
            continue
        factor_name = clean_cell(cells[0])
        if factor_name not in DEFAULT_FACTOR_NAMES:
            continue
        prose = clean_cell(cells[1])
        for match in re.finditer(r"([^，。；]+?)\s*`([+-]?\d+(?:\.\d+)?)`", prose):
            label = match.group(1).strip(" ，。；")
            if not label:
                continue
            sort_counters[factor_name] += 1
            rows.append(
                FactorOption(
                    item_code=item_code,
                    rule_code="",
                    formula_code=DEFAULT_FORMULA_CODE,
                    factor_name=factor_name,
                    factor_scope="default",
                    label=label,
                    value_num=Decimal(match.group(2)),
                    sort_no=sort_counters[factor_name],
                    source_doc=source_doc,
                    source_heading="\u5355\u6761\u6750\u6599",
                    source_line=line_no,
                    description=prose,
                    note="",
                )
            )

    return rows


def extract_factor_options(
    rule_doc: Path = I5B_RULE_DOC,
    default_doc: Path = DEFAULT_FACTOR_DOC,
    include_defaults: bool = True,
    item_code: str = ITEM_CODE,
    allowed_rule_codes: set[str] | None = KNOWN_I5B_RULE_CODES,
) -> list[FactorOption]:
    rows: list[FactorOption] = parse_i5b_rule_doc(rule_doc, item_code=item_code, allowed_rule_codes=allowed_rule_codes)
    if include_defaults:
        provided_defaults = {row.factor_name for row in rows if row.rule_code == ""}
        rows.extend(
            row
            for row in parse_default_factor_doc(default_doc, item_code=item_code)
            if row.factor_name not in provided_defaults
        )
    return rows


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def option_code_for(row: FactorOption) -> str:
    return f"opt_{row.sort_no:03d}"


def stable_source_id(namespace: str, parts: Sequence[object]) -> int:
    payload = namespace + "|" + "|".join(str(part) for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return 6_000_000_000_000_000_000 + (int(digest[:15], 16) % 1_000_000_000_000_000_000)


def jsonb_literal(payload: dict[str, object]) -> str:
    return sql_literal(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))) + "::jsonb"


def source_fingerprint(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def factor_group_key(row: FactorOption) -> tuple[str, str, str, str, str, str, str]:
    return (
        row.item_code,
        row.rule_code,
        row.formula_code,
        row.factor_name,
        row.factor_scope,
        row.source_doc,
        row.source_heading,
    )


def render_group_upsert_statement(rows: Sequence[FactorOption]) -> str:
    if not rows:
        return ""
    row = rows[0]
    item_code = sql_literal(row.item_code)
    rule_code = sql_literal(row.rule_code)
    formula_code = sql_literal(row.formula_code)
    factor_name = sql_literal(row.factor_name)
    factor_scope = sql_literal(row.factor_scope)
    source_doc = sql_literal(row.source_doc)
    source_heading = sql_literal(row.source_heading)
    description = sql_literal(row.description)
    factor_payload = {
        "source": "i5b_factor_table_sync",
        "item_code": row.item_code,
        "rule_code": row.rule_code,
        "formula_code": row.formula_code,
        "factor_name": row.factor_name,
        "factor_scope": row.factor_scope,
        "value_source": "markdown",
        "source_doc": row.source_doc,
        "source_heading": row.source_heading,
        "description": row.description,
    }
    source_factor_id = str(
        stable_source_id(
            "eval_rule_factors",
            [row.item_code, row.rule_code, row.formula_code, row.factor_name],
        )
    )
    factor_source_row = jsonb_literal(factor_payload)
    factor_source_fingerprint = sql_literal(source_fingerprint(factor_payload))
    option_values = ",\n".join(
        "    ("
        + ", ".join(
            [
                str(
                    stable_source_id(
                        "eval_rule_factor_options",
                        [
                            option.item_code,
                            option.rule_code,
                            option.formula_code,
                            option.factor_name,
                            option.label,
                        ],
                    )
                ),
                sql_literal(option_code_for(option)),
                sql_literal(option.label),
                format_decimal(option.value_num),
                str(option.sort_no),
                sql_literal(option.note),
                sql_literal(option.source_doc),
                str(option.source_line),
                jsonb_literal(
                    {
                        "source": "i5b_factor_table_sync",
                        "item_code": option.item_code,
                        "rule_code": option.rule_code,
                        "formula_code": option.formula_code,
                        "factor_name": option.factor_name,
                        "option_code": option_code_for(option),
                        "label": option.label,
                        "value_num": format_decimal(option.value_num),
                        "sort_no": option.sort_no,
                        "note": option.note,
                        "source_doc": option.source_doc,
                        "source_line": option.source_line,
                    }
                ),
                sql_literal(
                    source_fingerprint(
                        {
                            "source": "i5b_factor_table_sync",
                            "item_code": option.item_code,
                            "rule_code": option.rule_code,
                            "formula_code": option.formula_code,
                            "factor_name": option.factor_name,
                            "option_code": option_code_for(option),
                            "label": option.label,
                            "value_num": format_decimal(option.value_num),
                            "sort_no": option.sort_no,
                            "note": option.note,
                            "source_doc": option.source_doc,
                            "source_line": option.source_line,
                        }
                    )
                ),
            ]
        )
        + ")"
        for option in rows
    )

    if row.rule_code:
        rule_row = f"""
rule_row as (
    select r.id
    from retrieval_v2.eval_rules r
    join item_row i on i.id = r.item_id
    where r.rule_code = {rule_code}
)"""
    else:
        rule_row = """
rule_row as (
    select null::bigint as id
)"""

    return f"""with item_row as (
    select id
    from retrieval_v2.eval_items
    where item_code = {item_code}
),
{rule_row},
factor_row as (
    insert into retrieval_v2.eval_rule_factors (
        item_id,
        source_factor_id,
        item_code,
        rule_id,
        rule_code,
        formula_code,
        factor_name,
        factor_scope,
        value_source,
        source_doc,
        source_heading,
        description,
        factor_status,
        source_row,
        source_fingerprint
    )
    select
        item_row.id,
        {source_factor_id},
        {item_code},
        rule_row.id,
        {rule_code},
        {formula_code},
        {factor_name},
        {factor_scope},
        'markdown',
        {source_doc},
        {source_heading},
        {description},
        'active',
        {factor_source_row},
        {factor_source_fingerprint}
    from item_row
    cross join rule_row
    on conflict on constraint rv2_eval_rule_factors_code_uk do update set
        item_id = excluded.item_id,
        rule_id = excluded.rule_id,
        factor_scope = excluded.factor_scope,
        value_source = excluded.value_source,
        source_doc = excluded.source_doc,
        source_heading = excluded.source_heading,
        description = excluded.description,
        factor_status = excluded.factor_status,
        source_row = excluded.source_row,
        source_fingerprint = excluded.source_fingerprint,
        copied_at = now()
    returning id
),
option_rows(source_option_id, option_code, label, value_num, sort_no, option_note, source_doc, source_line, source_row, source_fingerprint) as (
    values
{option_values}
)
insert into retrieval_v2.eval_rule_factor_options (
    factor_id,
    source_option_id,
    option_code,
    label,
    value_num,
    sort_no,
    option_note,
    source_doc,
    source_line,
    option_status,
    source_row,
    source_fingerprint
)
select
    factor_row.id,
    option_rows.source_option_id,
    option_rows.option_code,
    option_rows.label,
    option_rows.value_num,
    option_rows.sort_no,
    option_rows.option_note,
    option_rows.source_doc,
    option_rows.source_line,
    'active',
    option_rows.source_row,
    option_rows.source_fingerprint
from factor_row
cross join option_rows
on conflict on constraint rv2_eval_rule_factor_options_factor_label_uk do update set
    option_code = excluded.option_code,
    value_num = excluded.value_num,
    sort_no = excluded.sort_no,
    option_note = excluded.option_note,
    source_doc = excluded.source_doc,
    source_line = excluded.source_line,
    option_status = excluded.option_status,
    source_row = excluded.source_row,
    source_fingerprint = excluded.source_fingerprint,
    copied_at = now();"""


def render_retire_stale_sql(rows: Sequence[FactorOption]) -> str:
    option_keys = sorted(
        {
            (
                row.item_code,
                row.rule_code,
                row.formula_code,
                row.factor_name,
                row.label,
            )
            for row in rows
        }
    )
    factor_keys = sorted(
        {
            (
                row.item_code,
                row.rule_code,
                row.formula_code,
                row.factor_name,
            )
            for row in rows
        }
    )
    item_codes = sorted({row.item_code for row in rows})
    formula_codes = sorted({row.formula_code for row in rows})
    if not option_keys:
        return ""

    option_values = ",\n".join(
        "    (" + ", ".join(sql_literal(value) for value in key) + ")" for key in option_keys
    )
    factor_values = ",\n".join(
        "    (" + ", ".join(sql_literal(value) for value in key) + ")" for key in factor_keys
    )
    item_code_list = ", ".join(sql_literal(value) for value in item_codes)
    formula_code_list = ", ".join(sql_literal(value) for value in formula_codes)

    return f"""with doc_options(item_code, rule_code, formula_code, factor_name, label) as (
    values
{option_values}
)
update retrieval_v2.eval_rule_factor_options erfo
set
    option_status = 'inactive',
    copied_at = now()
from retrieval_v2.eval_rule_factors erf
where erf.id = erfo.factor_id
  and erf.value_source = 'markdown'
  and erf.item_code in ({item_code_list})
  and erf.formula_code in ({formula_code_list})
  and erfo.option_status = 'active'
  and not exists (
      select 1
      from doc_options d
      where d.item_code = erf.item_code
        and d.rule_code = erf.rule_code
        and d.formula_code = erf.formula_code
        and d.factor_name = erf.factor_name
        and d.label = erfo.label
  );

with doc_factors(item_code, rule_code, formula_code, factor_name) as (
    values
{factor_values}
)
update retrieval_v2.eval_rule_factors erf
set
    factor_status = 'inactive',
    copied_at = now()
where erf.value_source = 'markdown'
  and erf.item_code in ({item_code_list})
  and erf.formula_code in ({formula_code_list})
  and erf.factor_status = 'active'
  and not exists (
      select 1
      from doc_factors d
      where d.item_code = erf.item_code
        and d.rule_code = erf.rule_code
        and d.formula_code = erf.formula_code
        and d.factor_name = erf.factor_name
  );"""


def render_upsert_sql(rows: Sequence[FactorOption]) -> str:
    groups: dict[tuple[str, str, str, str, str, str, str], list[FactorOption]] = {}
    for row in rows:
        groups.setdefault(factor_group_key(row), []).append(row)

    statements = ["begin;"]
    statements.extend(render_group_upsert_statement(group) for _, group in sorted(groups.items()))
    stale_sql = render_retire_stale_sql(rows)
    if stale_sql:
        statements.append(stale_sql)
    statements.append("commit;")
    return "\n\n".join(statements) + "\n"


def render_markdown(rows: Sequence[FactorOption]) -> str:
    lines = [
        "| item_code | rule_code | factor_name | scope | label | value_num | source_line |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row.item_code,
                    row.rule_code,
                    row.factor_name,
                    row.factor_scope,
                    row.label,
                    format_decimal(row.value_num),
                    str(row.source_line),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def normalize_row_dict(row: dict[str, object]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key in COMPARISON_KEYS:
        value = row.get(key, "")
        if key == "value_num":
            normalized[key] = format_decimal(Decimal(str(value)))
        else:
            normalized[key] = str(value)
    return normalized


def compare_rows(expected: Iterable[dict[str, object]], actual: Iterable[FactorOption]) -> dict[str, list[dict[str, str]]]:
    expected_rows = [normalize_row_dict(row) for row in expected]
    actual_rows = [normalize_row_dict(row.to_dict()) for row in actual]
    expected_keys = {tuple(row[key] for key in COMPARISON_KEYS): row for row in expected_rows}
    actual_keys = {tuple(row[key] for key in COMPARISON_KEYS): row for row in actual_rows}
    missing = [expected_keys[key] for key in sorted(expected_keys.keys() - actual_keys.keys())]
    extra = [actual_keys[key] for key in sorted(actual_keys.keys() - expected_keys.keys())]
    return {"missing": missing, "extra": extra}


def normalize_label(value: str) -> str:
    return re.sub(r"\s+", "", value.strip().strip("\u3002\uff1b;"))


def factor_name_candidates(catalog: dict[str, list[dict[str, object]]], factor_name: str) -> tuple[str, ...]:
    names = [factor_name]
    suffix = f"-> {factor_name}"
    for name in catalog:
        if name not in names and name.endswith(suffix):
            names.append(name)
    return tuple(names)


def _decimal_text(value: object) -> str | None:
    try:
        return format_decimal(Decimal(str(value)))
    except (InvalidOperation, TypeError):
        return None


def match_factor_option(
    catalog: dict[str, list[dict[str, object]]],
    *,
    rule_code: str,
    factor_name: str,
    label: str,
) -> tuple[str, list[dict[str, object]]]:
    candidates: list[dict[str, object]] = []
    for name in factor_name_candidates(catalog, factor_name):
        candidates.extend(catalog.get(name, ()))
    if not candidates:
        return "missing_factor", []

    rule_candidates = [row for row in candidates if str(row.get("rule_code") or "") == rule_code]
    shared_candidates = [row for row in candidates if not str(row.get("rule_code") or "")]
    scoped = rule_candidates or shared_candidates
    if not scoped:
        return "missing_rule_scope", []

    wanted = normalize_label(label)
    exact = [row for row in scoped if normalize_label(str(row.get("label") or "")) == wanted]
    if exact:
        return ("matched", exact) if len({_decimal_text(row.get("value_num")) for row in exact}) <= 1 else ("ambiguous", exact)

    fuzzy = [
        row
        for row in scoped
        if wanted in normalize_label(str(row.get("label") or ""))
        or normalize_label(str(row.get("label") or "")) in wanted
    ]
    if fuzzy:
        return ("fuzzy_matched", fuzzy) if len({_decimal_text(row.get("value_num")) for row in fuzzy}) <= 1 else ("ambiguous", fuzzy)
    return "missing_option", []


def iter_calc_factor_refs(calc_row: dict[str, object]) -> Iterable[dict[str, object]]:
    calc_detail = calc_row.get("calc_detail")
    if not isinstance(calc_detail, dict):
        return
    rule_code = str(calc_row.get("rule_code") or "")
    emperor = str(calc_row.get("emperor") or "")
    cluster_id = calc_row.get("cluster_id")

    materials = calc_detail.get("materials")
    if isinstance(materials, list):
        for index, material in enumerate(materials):
            if not isinstance(material, dict):
                continue
            refs = material.get("factor_refs")
            if not isinstance(refs, dict):
                continue
            values = material.get("factor_values")
            values = values if isinstance(values, dict) else {}
            for factor_name, ref in refs.items():
                yield {
                    "cluster_id": cluster_id,
                    "emperor": emperor,
                    "rule_code": rule_code,
                    "path": f"materials[{index}].factor_refs.{factor_name}",
                    "obj_src_id": material.get("obj_src_id"),
                    "obj_name": material.get("obj_name"),
                    "factor_name": str(factor_name),
                    "ref": ref,
                    "snapshot_value": values.get(factor_name),
                }

    team_factors = calc_detail.get("team_factors")
    if isinstance(team_factors, dict):
        refs = team_factors.get("factor_refs")
        values = team_factors.get("factor_values")
        values = values if isinstance(values, dict) else {}
        if isinstance(refs, dict):
            for factor_name, ref in refs.items():
                yield {
                    "cluster_id": cluster_id,
                    "emperor": emperor,
                    "rule_code": rule_code,
                    "path": f"team_factors.factor_refs.{factor_name}",
                    "obj_src_id": None,
                    "obj_name": "",
                    "factor_name": str(factor_name),
                    "ref": ref,
                    "snapshot_value": values.get(factor_name),
                }


def factor_rows_catalog(rows: Iterable[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    catalog: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        catalog[str(row.get("factor_name") or "")].append(row)
    return dict(catalog)


def audit_calc_detail_factor_refs(
    calc_rows: Iterable[dict[str, object]],
    factor_rows: Iterable[dict[str, object]],
) -> dict[str, object]:
    catalog = factor_rows_catalog(factor_rows)
    issues: list[dict[str, object]] = []
    checked = 0
    matched = 0

    for item in calc_rows:
        for ref_row in iter_calc_factor_refs(item):
            checked += 1
            factor_name = str(ref_row["factor_name"])
            ref = ref_row["ref"]
            base_issue = {
                key: ref_row.get(key)
                for key in ("cluster_id", "emperor", "rule_code", "path", "obj_src_id", "obj_name", "factor_name")
            }
            if factor_name in RETIRED_FACTOR_NAMES:
                issues.append({**base_issue, "severity": "error", "status": "retired_factor"})
                continue
            if factor_name == "team_quality_excluded":
                continue
            if not isinstance(ref, dict):
                severity = "error" if str(base_issue.get("path") or "").startswith("team_factors.") else "warning"
                issues.append({**base_issue, "severity": severity, "status": "literal_factor_ref", "ref": ref})
                continue
            if "value" in ref and "label" not in ref:
                severity = "error" if str(base_issue.get("path") or "").startswith("team_factors.") else "warning"
                issues.append({**base_issue, "severity": severity, "status": "literal_factor_value", "ref": ref})
                continue
            label = ref.get("label")
            if not isinstance(label, str) or not label.strip():
                issues.append({**base_issue, "severity": "error", "status": "missing_label", "ref": ref})
                continue
            ref_factor_name = str(ref.get("factor") or factor_name)
            status, matches = match_factor_option(
                catalog,
                rule_code=str(ref_row.get("rule_code") or ""),
                factor_name=ref_factor_name,
                label=label,
            )
            if status not in {"matched", "fuzzy_matched"}:
                issues.append({**base_issue, "severity": "error", "status": status, "label": label})
                continue
            selected = matches[0]
            selected_value = _decimal_text(selected.get("value_num"))
            snapshot_value = _decimal_text(ref_row.get("snapshot_value"))
            if selected_value is not None and snapshot_value is not None and selected_value != snapshot_value:
                issues.append(
                    {
                        **base_issue,
                        "severity": "error",
                        "status": "value_mismatch",
                        "label": label,
                        "snapshot_value": snapshot_value,
                        "catalog_value": selected_value,
                        "factor_option_id": selected.get("factor_option_id"),
                    }
                )
                continue
            if status == "fuzzy_matched":
                issues.append(
                    {
                        **base_issue,
                        "severity": "warning",
                        "status": status,
                        "label": label,
                        "matched_label": selected.get("label"),
                        "factor_option_id": selected.get("factor_option_id"),
                    }
                )
            matched += 1

    error_count = sum(1 for issue in issues if issue["severity"] == "error")
    warning_count = sum(1 for issue in issues if issue["severity"] == "warning")
    return {
        "ok": error_count == 0,
        "checked_factor_refs": checked,
        "matched_factor_refs": matched,
        "error_count": error_count,
        "warning_count": warning_count,
        "issues": issues,
    }


def write_output(text: str, output_path: Path | None) -> None:
    if output_path is None:
        sys.stdout.write(text)
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")


def load_env(path: Path = ROOT / ".env") -> dict[str, str]:
    if not path.exists():
        return {}
    env: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def resolve_dsn(env_name: str) -> str:
    if os.environ.get(env_name):
        return str(os.environ[env_name])
    env = load_env()
    if env_name not in env:
        raise RuntimeError(f"missing PostgreSQL DSN env var {env_name}")
    return env[env_name]


def dump_db_factor_options(dsn: str, *, item_code: str = ITEM_CODE, formula_code: str | None = None) -> list[dict[str, object]]:
    import psycopg

    params: list[object] = [item_code]
    formula_clause = ""
    if formula_code:
        formula_clause = "and erf.formula_code = %s"
        params.append(formula_code)

    sql = f"""
        select
            erfo.id as factor_option_id,
            erf.item_code,
            erf.rule_code,
            erf.formula_code,
            erf.factor_name,
            erf.factor_scope,
            erfo.label,
            erfo.value_num,
            erfo.sort_no,
            erfo.source_doc,
            erf.source_heading,
            erfo.source_line,
            erfo.option_note as note
        from retrieval_v2.eval_rule_factors erf
        join retrieval_v2.eval_rule_factor_options erfo on erfo.factor_id = erf.id
        where erf.item_code = %s
          and erf.factor_status = 'active'
          and erfo.option_status = 'active'
          {formula_clause}
        order by erf.rule_code, erf.factor_name, erfo.sort_no, erfo.id
    """
    columns = [
        "factor_option_id",
        "item_code",
        "rule_code",
        "formula_code",
        "factor_name",
        "factor_scope",
        "label",
        "value_num",
        "sort_no",
        "source_doc",
        "source_heading",
        "source_line",
        "note",
    ]
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = []
            for values in cur.fetchall():
                row = dict(zip(columns, values))
                row["value_num"] = format_decimal(Decimal(str(row["value_num"])))
                rows.append(row)
            return rows


def fetch_calc_detail_rows(
    dsn: str,
    *,
    item_code: str,
    formula_code: str,
    emperors: Sequence[str] = (),
    rule_codes: Sequence[str] = (),
) -> list[dict[str, object]]:
    import psycopg

    clauses = ["i.item_code = %s", "d.item_code = %s", "d.formula_code = %s"]
    params: list[object] = [item_code, item_code, formula_code]
    if emperors:
        clauses.append("e.name = any(%s)")
        params.append(list(emperors))
    if rule_codes:
        clauses.append("r.rule_code = any(%s)")
        params.append(list(rule_codes))
    where_sql = " and ".join(clauses)
    sql = f"""
        select
            c.id as cluster_id,
            e.name as emperor,
            r.rule_code,
            d.formula_code,
            d.calc_detail
        from public.evd_cluster_calc_details d
        join public.evd_clusters c on c.id = d.cluster_id
        join public.emps e on e.id = c.emp_id
        join public.eval_items i on i.id = c.item_id
        join public.eval_rules r on r.id = c.rule_id
        where {where_sql}
        order by e.name, r.rule_code, c.id
    """
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            columns = [desc.name for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]


def audit_db_calc_details(
    dsn: str,
    *,
    item_code: str,
    formula_code: str,
    emperors: Sequence[str] = (),
    rule_codes: Sequence[str] = (),
) -> dict[str, object]:
    factor_rows = dump_db_factor_options(dsn, item_code=item_code, formula_code=formula_code)
    calc_rows = fetch_calc_detail_rows(
        dsn,
        item_code=item_code,
        formula_code=formula_code,
        emperors=emperors,
        rule_codes=rule_codes,
    )
    report = audit_calc_detail_factor_refs(calc_rows, factor_rows)
    report["cluster_rows"] = len(calc_rows)
    report["factor_options"] = len(factor_rows)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract I5B factor options from Markdown rule docs.")
    parser.add_argument("--rule-doc", type=Path, default=I5B_RULE_DOC)
    parser.add_argument("--default-factor-doc", type=Path, default=DEFAULT_FACTOR_DOC)
    parser.add_argument("--no-defaults", action="store_true", help="Only extract I5B-specific rule tables.")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--render-upsert-sql", action="store_true", help="Render PostgreSQL upsert SQL instead of JSON/Markdown.")
    parser.add_argument("--expected-json", type=Path, help="Compare extracted rows with an exported table snapshot.")
    parser.add_argument("--dump-db-json", action="store_true", help="Dump active factor options from PostgreSQL as JSON.")
    parser.add_argument("--check-db-sync", action="store_true", help="Compare Markdown extraction with active PostgreSQL factor options.")
    parser.add_argument("--audit-calc-details", action="store_true", help="Audit evd_cluster_calc_details factor_refs against factor option table.")
    parser.add_argument("--item-code", default=ITEM_CODE, help="Evaluation item code for DB operations.")
    parser.add_argument("--cluster-formula", default=DEFAULT_FORMULA_CODE, help="Evidence cluster formula_code for calc detail audit.")
    parser.add_argument("--emperor", action="append", default=None, help="Optional emperor filter for calc detail audit; repeatable.")
    parser.add_argument("--rule-code", action="append", default=None, help="Optional rule_code filter for calc detail audit; repeatable.")
    parser.add_argument("--dsn-env", default=DEFAULT_DSN_ENV, help="Environment variable name for PostgreSQL DSN.")
    parser.add_argument("--fail-on-diff", action="store_true", help="Exit with code 1 when --expected-json differs.")
    parser.add_argument("--output", type=Path, help="Write output to a UTF-8 file instead of stdout.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rows = extract_factor_options(
        rule_doc=args.rule_doc,
        default_doc=args.default_factor_doc,
        include_defaults=not args.no_defaults,
    )

    if args.dump_db_json or args.check_db_sync:
        db_rows = dump_db_factor_options(resolve_dsn(args.dsn_env), item_code=args.item_code, formula_code=DEFAULT_FORMULA_CODE)
        if args.dump_db_json:
            text = json.dumps(db_rows, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            write_output(text, args.output)
            return 0
        diff = compare_rows(db_rows, rows)
        payload = {"table_only": diff["missing"], "doc_only": diff["extra"]}
        text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        write_output(text, args.output)
        if args.fail_on_diff and (payload["table_only"] or payload["doc_only"]):
            return 1
        return 0

    if args.audit_calc_details:
        report = audit_db_calc_details(
            resolve_dsn(args.dsn_env),
            item_code=args.item_code,
            formula_code=args.cluster_formula,
            emperors=tuple(args.emperor or ()),
            rule_codes=tuple(args.rule_code or ()),
        )
        write_output(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", args.output)
        if args.fail_on_diff and not report["ok"]:
            return 1
        return 0

    if args.expected_json:
        expected = json.loads(args.expected_json.read_text(encoding="utf-8"))
        if not isinstance(expected, list):
            raise SystemExit("--expected-json must contain a JSON array")
        diff = compare_rows(expected, rows)
        text = json.dumps(diff, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        write_output(text, args.output)
        if args.fail_on_diff and (diff["missing"] or diff["extra"]):
            return 1
        return 0

    if args.render_upsert_sql:
        write_output(render_upsert_sql(rows), args.output)
    elif args.format == "markdown":
        write_output(render_markdown(rows), args.output)
    else:
        payload = [row.to_dict() for row in rows]
        write_output(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
