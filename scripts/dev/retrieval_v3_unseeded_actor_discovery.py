from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.object_pool_aliases import normalize_object_alias  # noqa: E402
from scripts.dev.retrieval_v2_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v2_contracts import source_hints_for_period  # noqa: E402
from scripts.dev.retrieval_v2_pg_schema import DEFAULT_PG_SCHEMA, DEFAULT_V3_DSN_ENV, schema_cursor  # noqa: E402


DEFAULT_CONTRACT_CODE = "I5B-CLAIM-CACHE-V3-NATIVE-20260710"
DEFAULT_EMPERORS = ("刘邦", "朱元璋", "李世民")
DEFAULT_MIN_CONFIDENCE = 0.7
MAX_EVIDENCE_WINDOWS = 3
MAX_WINDOW_CHARS = 520

APPOINTMENT_TERMS = (
    "所任",
    "任用",
    "任命",
    "委任",
    "授任",
    "拜为",
    "以为",
    "命",
    "令",
    "使",
    "擢",
    "授",
    "领",
    "掌",
    "典",
    "留",
    "亲信",
    "倚之",
    "宠任",
)
HARM_TERMS = (
    "失守",
    "大败",
    "败绩",
    "专擅",
    "擅权",
    "专权",
    "贪污",
    "贪纵",
    "酷虐",
    "暴虐",
    "枉法",
    "诬陷",
    "构陷",
    "谮害",
    "卖官",
    "扰民",
    "纵兵",
    "结党",
    "乱政",
    "害民",
    "失职",
    "误国",
)
DISPOSITION_TERMS = (
    "皆获罪",
    "俱获罪",
    "并获罪",
    "获罪",
    "伏诛",
    "被诛",
    "赐死",
    "下狱",
    "削权",
    "夺职",
    "罢免",
    "免官",
    "谋反",
)
WARNING_TERMS = ("劾", "谏", "言其不可", "不听", "仍用", "益信", "庇护", "复任")
CLAIM_ACTOR_ADVERSE_ACTION_TYPES = {"处置", "失职", "构陷", "滥权", "结党", "拒谏", "制度高压"}
CLAIM_ACTOR_ADVERSE_TERMS = ("告", "劾", "谮", "诬", "陷", "害", "杀", "鞫", "毒", "专擅", "擅权", "谋反")

SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？；])|[\r\n]+")
CJK_NAME = r"[\u3400-\u9fff\U00020000-\U0002fa1f]{2,4}"
ENUMERATION_RE = re.compile(
    rf"(?P<body>[\u3400-\u9fff\U00020000-\U0002fa1f、，,]{{4,72}})"
    r"(?P<outcome>皆获罪|俱获罪|并获罪|皆伏诛|俱伏诛|并伏诛)"
)
DIRECT_NEGATIVE_RE = re.compile(
    rf"(?P<name>{CJK_NAME})(?P<outcome>获罪|伏诛|赐死|下狱|罢免|免官|谋反|专擅|擅权|专权|酷虐|暴虐|枉法|诬陷|构陷|谮害|卖官|扰民|纵兵|乱政|害民|失职|误国)"
)

PREFIX_CUES = ("所任", "任用", "任命", "委任", "授任", "拜", "以", "命", "令", "使", "擢", "授", "留")
NAME_STOPWORDS = {
    "太祖",
    "太宗",
    "高祖",
    "世宗",
    "圣祖",
    "皇帝",
    "陛下",
    "诸将",
    "将吏",
    "功臣",
    "百官",
    "群臣",
    "左右",
    "丞相",
    "中书",
    "列传",
    "本纪",
    "编辑",
    "数据项",
    "获罪",
    "伏诛",
}
NAME_BAD_FRAGMENTS = ("太祖", "太宗", "高祖", "皇帝", "陛下", "列传", "本纪", "编辑", "数据")


def text(value: Any) -> str:
    return str(value or "").strip()


def stable_code(prefix: str, *parts: Any) -> str:
    payload = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return prefix + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20].upper()


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def write_text(path: Path | None, payload: str) -> None:
    if path is None:
        print(payload, end="")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8", newline="\n")


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    payload = "".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True, default=str) + "\n" for row in rows)
    write_text(path, payload)


def signal_terms(value: str, terms: Sequence[str]) -> list[str]:
    return [term for term in terms if term in value]


def passage_windows(raw_text: str) -> list[dict[str, str]]:
    parts = [part.strip() for part in SENTENCE_SPLIT_RE.split(raw_text) if part and part.strip()]
    windows: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, part in enumerate(parts):
        negative = signal_terms(part, HARM_TERMS) or signal_terms(part, DISPOSITION_TERMS)
        if not negative:
            continue
        previous = parts[index - 1] if index > 0 and len(parts[index - 1]) <= 180 else ""
        following = parts[index + 1] if index + 1 < len(parts) and len(parts[index + 1]) <= 180 else ""
        window = "".join(segment for segment in (previous, part, following) if segment)
        if len(window) > MAX_WINDOW_CHARS:
            window = part[:MAX_WINDOW_CHARS]
        if window and window not in seen:
            seen.add(window)
            windows.append({"focus_text": part, "window": window})
    return windows


def valid_candidate_name(value: str) -> bool:
    name = normalize_object_alias(value)
    if not re.fullmatch(CJK_NAME, name):
        return False
    if name in NAME_STOPWORDS:
        return False
    return not any(fragment in name for fragment in NAME_BAD_FRAGMENTS)


def strip_enumeration_prefix(value: str) -> str:
    body = value
    best_end = -1
    for cue in PREFIX_CUES:
        index = body.rfind(cue)
        if index >= 0:
            best_end = max(best_end, index + len(cue))
    if best_end >= 0:
        body = body[best_end:]
    return body.strip("，,、：:。；; ")


def pattern_name_candidates(window: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for match in ENUMERATION_RE.finditer(window):
        body = strip_enumeration_prefix(match.group("body"))
        names = [normalize_object_alias(part) for part in re.split(r"[、，,]", body)]
        for name in names:
            if valid_candidate_name(name):
                candidates.append(
                    {
                        "observed_name": name,
                        "extraction_method": "negative_enumeration",
                        "extraction_confidence": 0.82,
                        "matched_outcome": match.group("outcome"),
                    }
                )
    for match in DIRECT_NEGATIVE_RE.finditer(window):
        name = normalize_object_alias(match.group("name"))
        if valid_candidate_name(name):
            candidates.append(
                {
                    "observed_name": name,
                    "extraction_method": "direct_negative_predicate",
                    "extraction_confidence": 0.58,
                    "matched_outcome": match.group("outcome"),
                }
            )
    return candidates


def build_name_index(name_rows: Sequence[Mapping[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], list[tuple[str, dict[str, Any]]]]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    scan_names: list[tuple[str, dict[str, Any]]] = []
    seen_scan: set[tuple[str, int]] = set()
    for row in name_rows:
        object_id = int(row["object_id"])
        canonical_name = text(row.get("canonical_name"))
        names = [canonical_name, *[text(value) for value in row.get("names") or []]]
        object_row = {
            "object_id": object_id,
            "canonical_name": canonical_name,
            "identity_status": text(row.get("identity_status")),
        }
        for raw_name in names:
            normalized = normalize_object_alias(raw_name)
            if len(normalized) < 2:
                continue
            if all(int(item["object_id"]) != object_id for item in index[normalized]):
                index[normalized].append(object_row)
            scan_key = (normalized, object_id)
            if scan_key not in seen_scan:
                seen_scan.add(scan_key)
                scan_names.append((normalized, object_row))
    scan_names.sort(key=lambda item: (-len(item[0]), item[0], int(item[1]["object_id"])))
    return dict(index), scan_names


def known_name_candidates(
    window: str,
    name_index: Mapping[str, Sequence[Mapping[str, Any]]],
    scan_names: Sequence[tuple[str, Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for observed_name in dict.fromkeys(name for name, _object_row in scan_names):
        if observed_name not in window or not valid_candidate_name(observed_name):
            continue
        matches = list(name_index.get(observed_name, ()))
        candidate = {
            "observed_name": observed_name,
            "extraction_method": "accepted_object_name",
            "extraction_confidence": 0.95,
            "matched_outcome": "",
        }
        if len(matches) == 1:
            candidate.update(
                {
                    "resolved_object_id": int(matches[0]["object_id"]),
                    "resolved_canonical_name": text(matches[0].get("canonical_name")),
                    "identity_status": text(matches[0].get("identity_status")),
                }
            )
        elif len(matches) > 1:
            candidate["extraction_method"] = "accepted_object_name_ambiguous"
            candidate["identity_ambiguous"] = True
            candidate["matching_object_ids"] = sorted(int(row["object_id"]) for row in matches)
        result.append(candidate)
    return result


def normalized_owner_keys(owner_names: Sequence[Any], name_index: Mapping[str, Sequence[Mapping[str, Any]]]) -> tuple[set[str], set[int]]:
    names = {normalize_object_alias(value) for value in owner_names if normalize_object_alias(value)}
    object_ids = {
        int(row["object_id"])
        for name in names
        for row in name_index.get(name, ())
        if row.get("object_id") is not None
    }
    return names, object_ids


def lead_stage(*, harm_signals: Sequence[str], disposition_signals: Sequence[str], appointment_signals: Sequence[str]) -> str:
    if harm_signals and appointment_signals:
        return "appointment_harm_lead"
    if harm_signals:
        return "harm_lead_without_appointment"
    if disposition_signals and appointment_signals:
        return "appointment_disposition_lead"
    return "disposition_lead_only"


def discover_candidates_from_rows(
    passage_rows: Sequence[Mapping[str, Any]],
    name_rows: Sequence[Mapping[str, Any]],
    target_rows: Sequence[Mapping[str, Any]],
    *,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> dict[str, Any]:
    name_index, scan_names = build_name_index(name_rows)
    target_object_ids: dict[str, set[int]] = defaultdict(set)
    target_period_candidates: dict[str, set[str]] = defaultdict(set)
    for row in target_rows:
        emperor_name = text(row.get("emperor_name"))
        if row.get("object_id") is not None:
            target_object_ids[emperor_name].add(int(row["object_id"]))
        for period in row.get("dynasty_labels") or []:
            if text(period):
                target_period_candidates[emperor_name].add(text(period))
    names_by_object: dict[int, set[str]] = defaultdict(set)
    for name, matches in name_index.items():
        for match in matches:
            names_by_object[int(match["object_id"])].add(name)
    target_name_keys: dict[str, set[str]] = defaultdict(set)
    for emperor_name, object_ids in target_object_ids.items():
        for object_id in object_ids:
            target_name_keys[emperor_name].update(names_by_object.get(object_id, set()))

    grouped: dict[tuple[str, str, int | None], dict[str, Any]] = {}
    stats = Counter()
    by_emperor = Counter()
    for passage in passage_rows:
        emperor = text(passage.get("emperor_name"))
        owners = [text(value) for value in passage.get("owner_names") or [] if text(value)]
        owner_names, owner_ids = normalized_owner_keys(owners, name_index)
        for passage_window in passage_windows(text(passage.get("raw_text"))):
            focus_text = passage_window["focus_text"]
            window = passage_window["window"]
            stats["negative_windows"] += 1
            appointment_signals = signal_terms(focus_text, APPOINTMENT_TERMS)
            harm_signals = signal_terms(focus_text, HARM_TERMS)
            disposition_signals = signal_terms(focus_text, DISPOSITION_TERMS)
            warning_signals = signal_terms(focus_text, WARNING_TERMS)
            extracted = [*known_name_candidates(window, name_index, scan_names), *pattern_name_candidates(focus_text)]
            seen_window_names: set[tuple[str, int | None]] = set()
            for item in extracted:
                observed_name = normalize_object_alias(item.get("observed_name"))
                resolved_id = item.get("resolved_object_id")
                if resolved_id is None:
                    matches = name_index.get(observed_name, ())
                    if len(matches) == 1:
                        resolved_id = int(matches[0]["object_id"])
                        item = {
                            **item,
                            "resolved_object_id": resolved_id,
                            "resolved_canonical_name": text(matches[0].get("canonical_name")),
                            "identity_status": text(matches[0].get("identity_status")),
                        }
                identity_key = int(resolved_id) if resolved_id is not None else None
                dedupe_key = (observed_name, identity_key)
                if dedupe_key in seen_window_names:
                    continue
                seen_window_names.add(dedupe_key)
                if float(item.get("extraction_confidence") or 0) < float(min_confidence):
                    stats["below_confidence"] += 1
                    continue
                if observed_name in owner_names or (identity_key is not None and identity_key in owner_ids):
                    stats["owner_mentions"] += 1
                    continue
                if observed_name == normalize_object_alias(emperor):
                    stats["emperor_mentions"] += 1
                    continue
                if observed_name in target_name_keys.get(emperor, set()) or (
                    identity_key is not None and identity_key in target_object_ids.get(emperor, set())
                ):
                    stats["existing_target_object_mentions"] += 1
                    continue

                if item.get("identity_ambiguous"):
                    status = "ambiguous_known_name_not_attached"
                else:
                    status = "known_object_not_attached" if identity_key is not None else "unresolved_name_candidate"
                group_key = (emperor, observed_name, identity_key)
                period_candidates = sorted(target_period_candidates.get(emperor, set()))
                target_period = period_candidates[0] if len(period_candidates) == 1 else ""
                evidence = {
                    "passage_code": text(passage.get("passage_code")),
                    "document_code": text(passage.get("document_code")),
                    "source_title": text(passage.get("source_title")) or text(passage.get("title")),
                    "locator": text(passage.get("locator")),
                    "source_pack_code": text(passage.get("source_pack_code")),
                    "owner_names": owners,
                    "focus_text": focus_text,
                    "window": window,
                    "appointment_signals": appointment_signals,
                    "harm_signals": harm_signals,
                    "disposition_signals": disposition_signals,
                    "warning_signals": warning_signals,
                    "window_hash": stable_code("UAW-", emperor, text(passage.get("passage_code")), window),
                }
                if group_key not in grouped:
                    grouped[group_key] = {
                        "candidate_code": stable_code("UAC-", emperor, observed_name, identity_key),
                        "emperor_name": emperor,
                        "target_period": target_period,
                        "target_period_candidates": period_candidates,
                        "source_hints": source_hints_for_period(target_period) if target_period else [],
                        "observed_name": observed_name,
                        "normalized_name": observed_name,
                        "resolved_object_id": identity_key,
                        "resolved_canonical_name": text(item.get("resolved_canonical_name")),
                        "identity_status": text(item.get("identity_status")),
                        "discovery_status": status,
                        "extraction_methods": [],
                        "max_extraction_confidence": 0.0,
                        "lead_stages": [],
                        "appointment_signals": [],
                        "harm_signals": [],
                        "disposition_signals": [],
                        "warning_signals": [],
                        "evidence_windows": [],
                        "judge_required": True,
                        "scoring_allowed": False,
                        "negative_chain_level": None,
                        "next_action": "run_object_source_refiner_then_negative_chain_review",
                    }
                candidate = grouped[group_key]
                candidate["extraction_methods"] = sorted(set(candidate["extraction_methods"]) | {text(item.get("extraction_method"))})
                candidate["max_extraction_confidence"] = max(
                    float(candidate["max_extraction_confidence"]),
                    float(item.get("extraction_confidence") or 0),
                )
                candidate["lead_stages"] = sorted(
                    set(candidate["lead_stages"])
                    | {lead_stage(harm_signals=harm_signals, disposition_signals=disposition_signals, appointment_signals=appointment_signals)}
                )
                for key, values in (
                    ("appointment_signals", appointment_signals),
                    ("harm_signals", harm_signals),
                    ("disposition_signals", disposition_signals),
                    ("warning_signals", warning_signals),
                ):
                    candidate[key] = sorted(set(candidate[key]) | set(values))
                if evidence["window_hash"] not in {row["window_hash"] for row in candidate["evidence_windows"]}:
                    candidate["evidence_windows"].append(evidence)
                    candidate["evidence_windows"] = candidate["evidence_windows"][:MAX_EVIDENCE_WINDOWS]

    candidates = sorted(
        grouped.values(),
        key=lambda row: (
            text(row.get("emperor_name")),
            -float(row.get("max_extraction_confidence") or 0),
            text(row.get("observed_name")),
        ),
    )
    for candidate in candidates:
        stats["unseeded_actor_candidates"] += 1
        stats[text(candidate.get("discovery_status"))] += 1
        by_emperor[text(candidate.get("emperor_name"))] += 1
    return {
        "candidates": candidates,
        "counts": dict(sorted(stats.items())),
        "candidate_counts_by_emperor": dict(sorted(by_emperor.items())),
    }


def discover_candidates_from_claim_actors(
    claim_rows: Sequence[Mapping[str, Any]],
    name_rows: Sequence[Mapping[str, Any]],
    target_rows: Sequence[Mapping[str, Any]],
    *,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> dict[str, Any]:
    name_index, _scan_names = build_name_index(name_rows)
    target_object_ids: dict[str, set[int]] = defaultdict(set)
    target_period_candidates: dict[str, set[str]] = defaultdict(set)
    for row in target_rows:
        emperor = text(row.get("emperor_name"))
        if row.get("object_id") is not None:
            target_object_ids[emperor].add(int(row["object_id"]))
        target_period_candidates[emperor].update(text(value) for value in row.get("dynasty_labels") or [] if text(value))

    candidates: list[dict[str, Any]] = []
    stats = Counter()
    for row in claim_rows:
        fact = row.get("fact_payload") if isinstance(row.get("fact_payload"), Mapping) else {}
        emperor = text(row.get("emperor_name"))
        focal_object = normalize_object_alias(row.get("object_name"))
        actor = normalize_object_alias(fact.get("actor"))
        action_type = text(fact.get("action_type"))
        relation_text = " ".join(
            text(value)
            for value in (
                row.get("claim_summary"),
                fact.get("outcome"),
                fact.get("cost_or_damage"),
                fact.get("office_or_domain"),
            )
        )
        stats["claim_actor_rows_checked"] += 1
        if not valid_candidate_name(actor) or actor in {normalize_object_alias(emperor), focal_object}:
            stats["claim_actor_not_candidate"] += 1
            continue
        adverse_terms = signal_terms(relation_text, CLAIM_ACTOR_ADVERSE_TERMS)
        if action_type not in CLAIM_ACTOR_ADVERSE_ACTION_TYPES and not adverse_terms:
            stats["claim_actor_non_adverse_relation"] += 1
            continue
        confidence = float(row.get("confidence") or 0)
        if confidence < float(min_confidence):
            stats["claim_actor_below_confidence"] += 1
            continue
        matches = list(name_index.get(actor, ()))
        resolved_id = int(matches[0]["object_id"]) if len(matches) == 1 else None
        if resolved_id is not None and resolved_id in target_object_ids.get(emperor, set()):
            stats["existing_target_object_mentions"] += 1
            continue
        if len(matches) > 1:
            discovery_status = "ambiguous_known_name_not_attached"
        else:
            discovery_status = "known_object_not_attached" if resolved_id is not None else "unresolved_name_candidate"
        period_candidates = sorted(target_period_candidates.get(emperor, set()))
        target_period = period_candidates[0] if len(period_candidates) == 1 else ""
        evidence_windows = []
        for evidence in row.get("evidence") or []:
            if not isinstance(evidence, Mapping):
                continue
            source_ref = text(evidence.get("source_slice_ref"))
            window = text(evidence.get("slice_text_preview"))
            evidence_windows.append(
                {
                    "passage_code": "",
                    "document_code": text(evidence.get("document_code")),
                    "source_title": text(evidence.get("source_title")),
                    "locator": source_ref,
                    "source_pack_code": "",
                    "owner_names": [focal_object] if focal_object else [],
                    "focus_text": text(row.get("claim_summary")),
                    "window": window,
                    "appointment_signals": [],
                    "harm_signals": ["structured_adverse_actor_relation"],
                    "disposition_signals": [action_type] if action_type == "处置" else [],
                    "warning_signals": adverse_terms,
                    "claim_key": text(row.get("claim_key")),
                    "claim_actor": actor,
                    "claim_object": focal_object,
                    "claim_action_type": action_type,
                    "window_hash": stable_code("UAW-", emperor, text(row.get("claim_key")), source_ref, actor),
                }
            )
        candidate = {
            "candidate_code": stable_code("UAC-", emperor, actor, resolved_id),
            "emperor_name": emperor,
            "target_period": target_period,
            "target_period_candidates": period_candidates,
            "source_hints": source_hints_for_period(target_period) if target_period else [],
            "observed_name": actor,
            "normalized_name": actor,
            "resolved_object_id": resolved_id,
            "resolved_canonical_name": text(matches[0].get("canonical_name")) if len(matches) == 1 else "",
            "identity_status": text(matches[0].get("identity_status")) if len(matches) == 1 else "",
            "discovery_status": discovery_status,
            "extraction_methods": ["claim_fact_actor"],
            "max_extraction_confidence": min(confidence, 0.95),
            "lead_stages": ["claim_actor_adverse_relation_lead"],
            "appointment_signals": [],
            "harm_signals": ["structured_adverse_actor_relation"],
            "disposition_signals": [action_type] if action_type == "处置" else [],
            "warning_signals": adverse_terms,
            "evidence_windows": evidence_windows[:MAX_EVIDENCE_WINDOWS],
            "judge_required": True,
            "scoring_allowed": False,
            "negative_chain_level": None,
            "next_action": "run_object_source_refiner_then_negative_chain_review",
        }
        if len(matches) > 1:
            candidate["identity_ambiguous"] = True
            candidate["matching_object_ids"] = sorted(int(match["object_id"]) for match in matches)
        candidates.append(candidate)
        stats["claim_actor_candidates"] += 1
    return {"candidates": candidates, "counts": dict(sorted(stats.items()))}


def merge_discoveries(*discoveries: Mapping[str, Any]) -> dict[str, Any]:
    merged: dict[str, dict[str, Any]] = {}
    counts = Counter()
    for discovery in discoveries:
        counts.update(discovery.get("counts") or {})
        for source in discovery.get("candidates") or []:
            row = dict(source)
            code = text(row.get("candidate_code"))
            current = merged.get(code)
            if current is None:
                merged[code] = row
                continue
            for key in (
                "extraction_methods", "lead_stages", "appointment_signals", "harm_signals",
                "disposition_signals", "warning_signals",
            ):
                current[key] = sorted(set(current.get(key) or []) | set(row.get(key) or []))
            current["max_extraction_confidence"] = max(
                float(current.get("max_extraction_confidence") or 0),
                float(row.get("max_extraction_confidence") or 0),
            )
            existing_hashes = {text(item.get("window_hash")) for item in current.get("evidence_windows") or []}
            for evidence in row.get("evidence_windows") or []:
                if text(evidence.get("window_hash")) not in existing_hashes:
                    current.setdefault("evidence_windows", []).append(evidence)
            current["evidence_windows"] = current.get("evidence_windows", [])[:MAX_EVIDENCE_WINDOWS]
    candidates = sorted(
        merged.values(),
        key=lambda row: (text(row.get("emperor_name")), -float(row.get("max_extraction_confidence") or 0), text(row.get("observed_name"))),
    )
    for key in ("unseeded_actor_candidates", "unresolved_name_candidate", "known_object_not_attached", "ambiguous_known_name_not_attached"):
        counts.pop(key, None)
    by_emperor = Counter()
    for row in candidates:
        counts["unseeded_actor_candidates"] += 1
        counts[text(row.get("discovery_status"))] += 1
        by_emperor[text(row.get("emperor_name"))] += 1
    return {
        "candidates": candidates,
        "counts": dict(sorted(counts.items())),
        "candidate_counts_by_emperor": dict(sorted(by_emperor.items())),
    }


def fetch_discovery_rows(
    *,
    dsn: str,
    schema_name: str,
    contract_code: str,
    emperors: Sequence[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    psycopg, dict_row = import_psycopg()
    emperor_names = [text(name) for name in emperors if text(name)]
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            cur.execute(
                """
                select rt.emperor_name, rt.target_code, sp.pack_code as source_pack_code,
                       sd.document_code, sd.source_title, sd.title,
                       spg.passage_code, coalesce(nullif(spg.locator, ''), sd.locator) as locator,
                       spg.raw_text,
                       coalesce(jsonb_agg(distinct mc.object_name) filter (where mc.object_name is not null), '[]'::jsonb) as owner_names
                  from retrieval_v3.rule_contracts rc
                  join retrieval_v3.retrieval_targets rt on rt.contract_id = rc.id
                  join retrieval_v3.source_packs sp on sp.target_id = rt.id and sp.contract_id = rc.id
                  join retrieval_v3.source_documents sd on sd.source_pack_id = sp.id
                  join retrieval_v3.source_passages spg on spg.source_document_id = sd.id
                  left join retrieval_v3.claim_source_passages csp on csp.source_passage_id = spg.id
                  left join retrieval_v3.material_claims mc on mc.id = csp.claim_id
                 where rc.contract_code = %s
                   and sp.status = 'accepted'
                   and (coalesce(array_length(%s::text[], 1), 0) = 0 or rt.emperor_name = any(%s::text[]))
                 group by rt.emperor_name, rt.target_code, sp.pack_code,
                          sd.document_code, sd.source_title, sd.title,
                          spg.passage_code, spg.locator, sd.locator, spg.raw_text
                 order by rt.emperor_name, sp.pack_code, sd.document_code, spg.passage_code
                """,
                (contract_code, emperor_names, emperor_names),
            )
            passage_rows = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """
                select o.id as object_id, o.canonical_name, o.identity_status::text as identity_status,
                       coalesce(jsonb_agg(distinct onm.name_text) filter (
                           where onm.id is not null and onm.review_status::text = 'accepted'
                       ), '[]'::jsonb) as names
                  from retrieval_v3.objects o
                  left join retrieval_v3.object_names onm on onm.object_id = o.id
                 where o.identity_status::text not in ('rejected', 'retired')
                 group by o.id, o.canonical_name, o.identity_status
                 order by o.id
                """
            )
            name_rows = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """
                select rt.emperor_name, tob.object_id,
                       coalesce(jsonb_agg(distinct pa.dynasty_label) filter (
                           where pa.id is not null
                             and pa.review_status::text not in ('rejected', 'retired')
                             and btrim(pa.dynasty_label) <> ''
                       ), '[]'::jsonb) as dynasty_labels
                  from retrieval_v3.rule_contracts rc
                  join retrieval_v3.retrieval_targets rt on rt.contract_id = rc.id
                  join retrieval_v3.target_objects tob on tob.target_id = rt.id
                  left join retrieval_v3.person_affiliations pa on pa.object_id = tob.object_id
                 where rc.contract_code = %s
                   and tob.review_status::text not in ('rejected', 'retired')
                   and (coalesce(array_length(%s::text[], 1), 0) = 0 or rt.emperor_name = any(%s::text[]))
                 group by rt.emperor_name, tob.object_id
                 order by rt.emperor_name, tob.object_id
                """,
                (contract_code, emperor_names, emperor_names),
            )
            target_rows = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """
                select c.claim_key, c.emperor_name, c.object_name, c.claim_summary,
                       c.confidence, c.fact_payload,
                       coalesce(jsonb_agg(distinct jsonb_build_object(
                           'document_code', s.document_code,
                           'source_title', s.source_title,
                           'source_url', s.source_url,
                           'source_slice_ref', s.source_slice_ref,
                           'slice_text_preview', s.slice_text_preview
                       )) filter (where s.slice_hash is not null), '[]'::jsonb) as evidence
                  from retrieval_v3.claim_cache c
                  left join retrieval_v3.claim_evidence e on e.claim_key = c.claim_key
                  left join retrieval_v3.claim_source_slices s on s.slice_hash = e.slice_hash
                 where c.status::text = 'active'
                   and (coalesce(array_length(%s::text[], 1), 0) = 0 or c.emperor_name = any(%s::text[]))
                 group by c.claim_key, c.emperor_name, c.object_name, c.claim_summary,
                          c.confidence, c.fact_payload
                 order by c.emperor_name, c.claim_key
                """,
                (emperor_names, emperor_names),
            )
            claim_rows = [dict(row) for row in cur.fetchall()]
    return passage_rows, name_rows, target_rows, claim_rows


def build_report(
    *,
    passage_rows: Sequence[Mapping[str, Any]],
    name_rows: Sequence[Mapping[str, Any]],
    target_rows: Sequence[Mapping[str, Any]],
    schema_name: str,
    contract_code: str,
    emperors: Sequence[str],
    min_confidence: float,
    claim_rows: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    discovery = merge_discoveries(
        discover_candidates_from_rows(
            passage_rows,
            name_rows,
            target_rows,
            min_confidence=min_confidence,
        ),
        discover_candidates_from_claim_actors(
            claim_rows,
            name_rows,
            target_rows,
            min_confidence=min_confidence,
        ),
    )
    return {
        "ok": True,
        "generated_by": "scripts/dev/retrieval_v3_unseeded_actor_discovery.py",
        "mode": "read_only_unseeded_actor_discovery",
        "write_db": False,
        "schema_name": schema_name,
        "contract_code": contract_code,
        "emperors": [text(name) for name in emperors if text(name)],
        "min_confidence": float(min_confidence),
        "source_passage_count": len(passage_rows),
        "claim_actor_source_count": len(claim_rows),
        "known_object_count": len(name_rows),
        "target_object_link_count": len(target_rows),
        "counts": discovery["counts"],
        "candidate_counts_by_emperor": discovery["candidate_counts_by_emperor"],
        "candidates": discovery["candidates"],
        "execute_effect": "read-only report and judge worklist generation; no object creation, no claim creation, no scoring",
    }


def markdown_cell(value: Any, *, limit: int = 180) -> str:
    result = text(value).replace("\r", " ").replace("\n", " ").replace("|", "\\|")
    return result if len(result) <= limit else result[: limit - 1] + "…"


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# retrieval_v3 未种子对象发现报告",
        "",
        f"- schema: `{report.get('schema_name')}`",
        f"- contract: `{report.get('contract_code')}`",
        f"- write_db: `{str(bool(report.get('write_db'))).lower()}`",
        f"- source passages: `{report.get('source_passage_count', 0)}`",
        f"- negative windows: `{report.get('counts', {}).get('negative_windows', 0)}`",
        f"- unseeded actor candidates: `{report.get('counts', {}).get('unseeded_actor_candidates', 0)}`",
        "",
        "> 本报告只发现待调查对象；处置、获罪或伏诛只能触发补抓，不能直接形成负向分。",
        "",
        "## 按皇帝统计",
        "",
        "| 皇帝 | 候选数 |",
        "| --- | ---: |",
    ]
    for emperor, count in (report.get("candidate_counts_by_emperor") or {}).items():
        lines.append(f"| {markdown_cell(emperor)} | {count} |")
    lines.extend(
        [
            "",
            "## 候选",
            "",
            "| 皇帝 | 观察名 | 状态 | 线索阶段 | 置信度 | 原文窗口 |",
            "| --- | --- | --- | --- | ---: | --- |",
        ]
    )
    for row in report.get("candidates") or []:
        evidence = (row.get("evidence_windows") or [{}])[0]
        lines.append(
            "| {emperor} | {name} | {status} | {stage} | {confidence:.2f} | {window} |".format(
                emperor=markdown_cell(row.get("emperor_name")),
                name=markdown_cell(row.get("observed_name")),
                status=markdown_cell(row.get("discovery_status")),
                stage=markdown_cell(", ".join(row.get("lead_stages") or [])),
                confidence=float(row.get("max_extraction_confidence") or 0),
                window=markdown_cell(evidence.get("window")),
            )
        )
    return "\n".join(lines) + "\n"


def build_judge_worklist(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "task_code": stable_code("UAWL-", row.get("candidate_code")),
            "candidate_code": row.get("candidate_code"),
            "emperor_name": row.get("emperor_name"),
            "target_period": row.get("target_period"),
            "target_period_candidates": row.get("target_period_candidates"),
            "source_hints": row.get("source_hints"),
            "observed_name": row.get("observed_name"),
            "resolved_object_id": row.get("resolved_object_id"),
            "resolved_canonical_name": row.get("resolved_canonical_name"),
            "discovery_status": row.get("discovery_status"),
            "lead_stages": row.get("lead_stages"),
            "evidence_windows": row.get("evidence_windows"),
            "required_review": {
                "is_person_name": None,
                "is_same_reign_actor": None,
                "has_appointment_or_authorization": None,
                "has_harm_or_failure": None,
                "has_disposition_only": None,
                "recommended_action": "run_object_source_refiner | reject_name | needs_context",
            },
            "scoring_allowed": False,
        }
        for row in report.get("candidates") or []
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only v3 source-driven discovery of unseeded named actors.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default=DEFAULT_V3_DSN_ENV)
    parser.add_argument("--pg-schema", default=DEFAULT_PG_SCHEMA)
    parser.add_argument("--contract-code", default=DEFAULT_CONTRACT_CODE)
    parser.add_argument("--emperor", action="append", default=[])
    parser.add_argument("--min-confidence", type=float, default=DEFAULT_MIN_CONFIDENCE)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--output-worklist", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.env_file is not None:
        load_env_file(args.env_file)
    emperors = args.emperor or list(DEFAULT_EMPERORS)
    passage_rows, name_rows, target_rows, claim_rows = fetch_discovery_rows(
        dsn=resolve_dsn(args.dsn_env),
        schema_name=args.pg_schema,
        contract_code=args.contract_code,
        emperors=emperors,
    )
    report = build_report(
        passage_rows=passage_rows,
        name_rows=name_rows,
        target_rows=target_rows,
        schema_name=args.pg_schema,
        contract_code=args.contract_code,
        emperors=emperors,
        min_confidence=args.min_confidence,
        claim_rows=claim_rows,
    )
    if args.output_json is not None:
        write_text(args.output_json, pretty_json(report))
    elif args.output_md is None:
        write_text(None, pretty_json(report))
    if args.output_md is not None:
        write_text(args.output_md, render_markdown(report))
    if args.output_worklist is not None:
        write_jsonl(args.output_worklist, build_judge_worklist(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
