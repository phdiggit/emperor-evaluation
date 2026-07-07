from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


REPORT_VERSION = "recall_term_sampler_v0_1"
PROFILE_PATCH_VERSION = "recall_term_profile_patch_v0_1"
PROFILE_DELTA_VERSION = "recall_term_profile_delta_v0_1"
SOURCE_AB_VERSION = "recall_term_source_ab_v0_1"
CASE_TERM_BLOCKLIST = {"刘基", "劉基", "总中书政", "總中書政"}
BOILERPLATE_TERMS = {"编辑", "編輯", "本纪", "本紀", "列传", "列傳"}
OFFICE_TITLE_TERMS = {"将军", "將軍", "大将", "大將", "都督", "总兵", "總兵", "丞相", "御史", "大夫", "太子", "尚书", "尚書", "中书", "中書"}
OFFICE_TITLE_SUBSTRINGS = ("将军", "將軍", "宗正", "御史")
STOP_CHARS = set("年月日之其以为而于與与及并並或后後又乃所者也矣焉的了在是將将使令拜任")
MECHANISM_NGRAM_CHARS = set("擅权權威福宠寵任信谏諫疏言赦保疑忌杀殺诛誅族连連坐狱獄贿賄党黨谮譖谗讒荐薦举舉拔擢兵军軍藩宗宦戚屯边邊寇屠坑弊监察監察反")
PUNCT_RE = re.compile(r"[^\u4e00-\u9fff]+")
CJK_RE = re.compile(r"^[\u4e00-\u9fff]{2,6}$")
CALENDAR_RE = re.compile(r"^[元一二三四五六七八九十百千甲乙丙丁戊己庚辛壬癸春夏秋冬正年月日朔望]+$")
GRAMMAR_FRAGMENT_RE = re.compile(r"(^为|曰$|为$|于$|之$|者$)")
PROFILE_PATCH_NOISE_RE = re.compile(r"(信|福建|上党|宗庙|赦天|人言|有言|兵三|军士|公反|士缚|缚信)")
PROFILE_CANDIDATE_RE = re.compile(r"(谋反|将兵|发兵|引兵|举兵|起兵|兵反|兵攻|欲反|伏诛|下狱|三族|皆诛|诛灭|其党|功臣|宗室|连坐)")
PROFILE_CONTEXT_RE = re.compile(r"(自杀|杀人|大赦|赦罪|其言|兵与|反耳|诛秦|连兵)")
APPOINTMENT_DELEGATION_LONG_TERMS = {
    "任用",
    "起用",
    "擢用",
    "拜授",
    "授职",
    "授官",
    "授任",
    "委任",
    "委寄",
    "托付",
    "付托",
    "倚任",
    "倚重",
    "信任",
    "亲信",
    "親信",
    "信幸",
    "亲任",
    "親任",
    "宠任",
    "寵任",
    "腹心",
    "心腹",
    "主事",
    "任事",
    "典兵",
    "典军",
    "典軍",
    "掌兵",
    "留守",
    "镇守",
    "鎮守",
    "统领",
    "統領",
    "总领",
    "總領",
    "从其计",
    "從其計",
    "用其策",
    "采纳",
    "採納",
}
POWER_ABUSE_LONG_TERMS = {
    "专擅",
    "專擅",
    "擅权",
    "擅權",
    "专权",
    "專權",
    "擅政",
    "专政",
    "專政",
    "威福",
    "封事",
    "不奏",
    "径行",
    "徑行",
    "壅蔽",
    "匿奏",
    "匿闻",
    "匿聞",
    "不报",
    "不報",
    "黜陟",
    "奔竞",
    "奔競",
    "趋附",
    "趨附",
    "趋门",
    "趨門",
}
TALENT_DISCOVERY_LONG_TERMS = {
    "荐举",
    "薦舉",
    "推荐",
    "薦任",
    "荐任",
    "举荐",
    "舉薦",
    "辟召",
    "拔擢",
    "擢用",
    "识拔",
    "識拔",
    "访贤",
    "訪賢",
    "求贤",
    "求賢",
    "征辟",
    "征召",
    "举贤",
    "舉賢",
    "察举",
    "察舉",
}
TOLERATE_TALENT_LONG_TERMS = {
    "纳谏",
    "納諫",
    "直言",
    "进谏",
    "進諫",
    "从谏",
    "從諫",
    "容谏",
    "容諫",
    "听谏",
    "聽諫",
    "言事",
    "实封",
    "實封",
    "保全",
    "宽宥",
    "寬宥",
    "赦免",
    "宽赦",
    "寬赦",
    "复用",
    "復用",
}
ANTI_NEPOTISM_LONG_TERMS = {
    "谮害",
    "譖害",
    "谗害",
    "讒害",
    "朋党",
    "朋黨",
    "结党",
    "結黨",
    "党附",
    "黨附",
    "党援",
    "黨援",
    "阿附",
    "请托",
    "請托",
    "请谒",
    "請謁",
    "奔竞",
    "奔競",
    "纳贿",
    "納賄",
    "受赂",
    "受賂",
    "贿赂",
    "賄賂",
}
POWER_CONTROL_LONG_TERMS = {
    "收兵权",
    "收兵權",
    "释兵权",
    "釋兵權",
    "削藩",
    "裁抑",
    "夺权",
    "奪權",
    "夺兵",
    "奪兵",
    "罢相",
    "罷相",
    "废相",
    "廢相",
    "废丞相",
    "廢丞相",
    "罢中书",
    "罷中書",
    "分权",
    "分權",
    "制衡",
    "禁军",
    "禁軍",
    "宿卫",
    "宿衛",
}
LONG_TERM_TERM_GROUPS = (
    ("appointment_delegation", APPOINTMENT_DELEGATION_LONG_TERMS),
    ("power_abuse_mechanism", POWER_ABUSE_LONG_TERMS),
    ("talent_discovery", TALENT_DISCOVERY_LONG_TERMS),
    ("tolerate_talent", TOLERATE_TALENT_LONG_TERMS),
    ("anti_nepotism", ANTI_NEPOTISM_LONG_TERMS),
    ("power_control", POWER_CONTROL_LONG_TERMS),
)
LONG_TERM_MECHANISM_TERMS = set().union(*(terms for _, terms in LONG_TERM_TERM_GROUPS))
MILITARY_AUTHORITY_TERMS = {
    "将兵",
    "发兵",
    "引兵",
    "举兵",
    "起兵",
    "领兵",
    "領兵",
    "统兵",
    "統兵",
    "督兵",
    "欲发兵",
    "兵攻",
}
DISPOSITION_RISK_TERMS = {
    "谋反",
    "欲反",
    "兵反",
    "发兵反",
    "其党",
    "伏诛",
    "下狱",
    "族诛",
    "族誅",
    "三族",
    "皆诛",
    "皆誅",
    "连坐",
    "連坐",
    "赐死",
    "賜死",
    "诛灭",
    "誅滅",
    "族灭",
    "族滅",
    "废黜",
    "廢黜",
    "罢免",
    "罷免",
    "削爵",
    "夺爵",
    "奪爵",
    "弃市",
    "棄市",
}
POWER_BASE_CONTEXT_TERMS = {"权臣", "權臣", "宗室", "外戚", "宦官", "近幸", "近臣", "藩王", "诸王", "諸王", "功臣"}
MILITARY_AUTHORITY_GUARD_TERMS = ["命", "遣", "使", "将", "军", "兵", "征", "讨", "击", "守", "都督", "大将军"]
DISPOSITION_RISK_GUARD_TERMS = ["宠任", "丞相", "中书", "专擅", "威福", "封事", "其党", "党", "相位", "独相"]
POWER_BASE_CONTEXT_GUARD_TERMS = ["专擅", "擅权", "兵权", "军权", "收兵权", "削藩", "禁军", "宗室", "外戚", "宦官", "裁抑"]
CONTEXT_ONLY_TERMS = {
    "自杀",
    "自殺",
    "杀人",
    "殺人",
    "大赦",
    "大赦天下",
    "赦天下",
    "赦罪",
    "其言",
    "汉军",
    "漢軍",
    "精兵",
    "兵至",
    "兵出",
    "元兵",
    "军士",
    "軍士",
    "军国",
    "軍國",
}
FRAGMENT_NOISE_TERMS = {
    "王信",
    "信欲",
    "信欲反",
    "信国",
    "信国公",
    "赦天",
    "大赦天",
    "人言",
    "有言",
    "告信",
    "告信欲",
    "告信欲反",
    "士缚信",
    "武士缚信",
    "缚信",
    "上党",
    "福建",
    "公反",
    "楚王信",
    "之宗",
    "宗庙",
    "兵三",
}
SENTENCE_FRAGMENT_END_CHARS = ("乎", "也")
MILITARY_CONTEXT_NGRAM_TERMS = {
    "分兵",
    "屯田",
    "兵会",
    "兵出入",
    "陈兵",
    "陈兵出",
    "陈兵出入",
    "练兵",
    "诸军",
    "其军",
    "议军",
    "议军国",
    "中兵",
    "军中",
}
REJECT_RECALL_TERMS = CASE_TERM_BLOCKLIST | BOILERPLATE_TERMS


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=str) + "\n"


def text(value: Any) -> str:
    return str(value or "").strip()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def candidate_paths_from_run_root(run_root: Path) -> list[Path]:
    return sorted(run_root.rglob("candidates.final.json"))


def unique_strings(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    rows: list[str] = []
    for value in values:
        item = text(value)
        if item and item not in seen:
            seen.add(item)
            rows.append(item)
    return rows


def recall_term_policy(term: str) -> dict[str, Any]:
    value = text(term)
    if value in REJECT_RECALL_TERMS:
        return {
            "term": value,
            "profile_action": "reject_term",
            "policy_group": "case_or_boilerplate",
            "risk_level": "block",
            "guard": {},
        }
    if value in CONTEXT_ONLY_TERMS:
        return {
            "term": value,
            "profile_action": "context_only",
            "policy_group": "context_or_noise",
            "risk_level": "block",
            "guard": {},
        }
    if PROFILE_CONTEXT_RE.search(value):
        return {
            "term": value,
            "profile_action": "context_only",
            "policy_group": "context_or_noise",
            "risk_level": "block",
            "guard": {},
        }
    if value in FRAGMENT_NOISE_TERMS:
        return {
            "term": value,
            "profile_action": "reject_term",
            "policy_group": "fragment_noise",
            "risk_level": "block",
            "guard": {},
        }
    if value.startswith("反") and value not in DISPOSITION_RISK_TERMS:
        return {
            "term": value,
            "profile_action": "reject_term",
            "policy_group": "fragment_noise",
            "risk_level": "block",
            "guard": {},
        }
    for group_name, group_terms in LONG_TERM_TERM_GROUPS:
        if value in group_terms:
            return {
                "term": value,
                "profile_action": "append_rule_term",
                "policy_group": group_name,
                "risk_level": "low",
                "guard": {},
            }
    if "信" in value:
        return {
            "term": value,
            "profile_action": "reject_term",
            "policy_group": "fragment_noise",
            "risk_level": "block",
            "guard": {},
        }
    if value in MILITARY_AUTHORITY_TERMS:
        return {
            "term": value,
            "profile_action": "conditional_term",
            "policy_group": "military_authority",
            "risk_level": "medium",
            "guard": {
                "requires_near_any": MILITARY_AUTHORITY_GUARD_TERMS,
                "reason": "avoid treating generic troop movement as appointment_delegation evidence without authority context",
            },
        }
    if value in DISPOSITION_RISK_TERMS:
        return {
            "term": value,
            "profile_action": "conditional_term",
            "policy_group": "disposition_risk",
            "risk_level": "high",
            "guard": {
                "requires_near_any": DISPOSITION_RISK_GUARD_TERMS,
                "reason": "avoid treating punishment/rebellion context as AD negative unless appointment or power-abuse context is nearby",
            },
        }
    if value in POWER_BASE_CONTEXT_TERMS:
        return {
            "term": value,
            "profile_action": "conditional_term",
            "policy_group": "power_base_context",
            "risk_level": "medium",
            "guard": {
                "requires_near_any": POWER_BASE_CONTEXT_GUARD_TERMS,
                "reason": "avoid treating broad actor classes as power-control evidence without control or abuse context",
            },
        }
    if looks_like_context_only_ngram(value):
        return {
            "term": value,
            "profile_action": "context_only",
            "policy_group": "context_or_noise",
            "risk_level": "block",
            "guard": {},
        }
    if looks_like_sentence_fragment_ngram(value):
        return {
            "term": value,
            "profile_action": "reject_term",
            "policy_group": "fragment_noise",
            "risk_level": "block",
            "guard": {},
        }
    return {
        "term": value,
        "profile_action": "needs_taxonomy_review",
        "policy_group": "unclassified_candidate",
        "risk_level": "review",
        "guard": {},
    }


def cjk_ngrams(value: str, *, min_chars: int, max_chars: int) -> set[str]:
    terms: set[str] = set()
    for segment in PUNCT_RE.split(value):
        segment = segment.strip()
        if not segment:
            continue
        for size in range(min_chars, max_chars + 1):
            if len(segment) < size:
                continue
            for index in range(0, len(segment) - size + 1):
                term = segment[index : index + size]
                if is_candidate_term(term):
                    terms.add(term)
    return terms


def is_candidate_term(term: str) -> bool:
    if not CJK_RE.fullmatch(term):
        return False
    if all(char in STOP_CHARS for char in term):
        return False
    if term in CASE_TERM_BLOCKLIST:
        return True
    return any(char not in STOP_CHARS for char in term)


def looks_like_mechanism_ngram(term: str) -> bool:
    if term in CASE_TERM_BLOCKLIST:
        return True
    if term in BOILERPLATE_TERMS or term in OFFICE_TITLE_TERMS or CALENDAR_RE.fullmatch(term):
        return False
    return any(char in MECHANISM_NGRAM_CHARS for char in term)


def looks_like_sentence_fragment_ngram(term: str) -> bool:
    value = text(term)
    if not value:
        return False
    if value.endswith(SENTENCE_FRAGMENT_END_CHARS):
        return True
    if "乃疑" in value or "何言" in value or "党不" in value:
        return True
    if len(value) <= 3 and value.endswith("反") and value not in DISPOSITION_RISK_TERMS:
        return True
    if len(value) <= 3 and value.startswith(("杀", "殺")):
        return True
    if value.endswith("赦") and value not in LONG_TERM_MECHANISM_TERMS:
        return True
    if "与言" in value or value.endswith("有言"):
        return True
    if value in {"人言公", "公言", "言公"}:
        return True
    if value.startswith(("可与", "子可", "与子")) and "言" in value:
        return True
    if value.startswith("言") and value not in TOLERATE_TALENT_LONG_TERMS:
        return True
    if "公" in value:
        return True
    if "精兵处" in value or value in {"兵处", "天下精兵", "下精兵", "兵大"}:
        return True
    if value.startswith("下") and any(fragment in value for fragment in ("乃疑", "精兵")):
        return True
    return False


def looks_like_context_only_ngram(term: str) -> bool:
    value = text(term)
    if value in MILITARY_CONTEXT_NGRAM_TERMS:
        return True
    if value.endswith("军") and value not in LONG_TERM_MECHANISM_TERMS and value not in MILITARY_AUTHORITY_TERMS:
        return True
    return False


def load_candidate_slices(path: Path) -> list[dict[str, Any]]:
    payload = load_json(path)
    if not isinstance(payload, Mapping):
        return []
    task_identity = payload.get("task_identity") if isinstance(payload.get("task_identity"), Mapping) else {}
    target_profile = payload.get("target_profile") if isinstance(payload.get("target_profile"), Mapping) else {}
    target_name = text(task_identity.get("emperor_name") or target_profile.get("primary_name") or target_profile.get("name"))
    rows: list[dict[str, Any]] = []
    for raw in payload.get("candidate_slices") or []:
        if not isinstance(raw, Mapping):
            continue
        rows.append(
            {
                "source_path": repo_relative(path),
                "target_name": target_name,
                "slice_code": text(raw.get("slice_code")),
                "document_code": text(raw.get("document_code")),
                "object_name": text(raw.get("object_name")),
                "text": text(raw.get("text")),
                "matched_rule_terms": unique_strings(raw.get("matched_rule_terms") or []),
                "matched_role_families": unique_strings(raw.get("matched_role_families") or []),
            }
        )
    return rows


def slice_signature(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (text(row.get("object_name")), text(row.get("document_code")), text(row.get("text")))


def compact_slice(row: Mapping[str, Any], *, accepted_terms: set[str]) -> dict[str, Any]:
    matched_terms = unique_strings(row.get("matched_rule_terms") or [])
    return {
        "object_name": text(row.get("object_name")),
        "document_code": text(row.get("document_code")),
        "slice_code": text(row.get("slice_code")),
        "matched_rule_terms": matched_terms,
        "accepted_term_hits": sorted(term for term in matched_terms if term in accepted_terms),
        "text_sample": text(row.get("text"))[:160],
    }


def build_source_ab_report(
    *,
    base_candidates_path: Path,
    overlay_candidates_path: Path,
    accepted_terms: Sequence[str] = (),
    max_examples: int = 50,
) -> dict[str, Any]:
    accepted_term_set = set(unique_strings(accepted_terms))
    base_rows = load_candidate_slices(base_candidates_path)
    overlay_rows = load_candidate_slices(overlay_candidates_path)
    base_by_sig = {slice_signature(row): row for row in base_rows}
    overlay_by_sig = {slice_signature(row): row for row in overlay_rows}
    added_sigs = sorted(overlay_by_sig.keys() - base_by_sig.keys())
    removed_sigs = sorted(base_by_sig.keys() - overlay_by_sig.keys())

    changed_terms: list[dict[str, Any]] = []
    new_term_counter: Counter[str] = Counter()
    overlay_hit_counter: Counter[str] = Counter()
    for row in overlay_rows:
        for term in row.get("matched_rule_terms") or []:
            if term in accepted_term_set:
                overlay_hit_counter[term] += 1

    for sig in sorted(overlay_by_sig.keys() & base_by_sig.keys()):
        base_terms = set(base_by_sig[sig].get("matched_rule_terms") or [])
        overlay_terms = set(overlay_by_sig[sig].get("matched_rule_terms") or [])
        added_terms = sorted(overlay_terms - base_terms)
        removed_terms = sorted(base_terms - overlay_terms)
        if not added_terms and not removed_terms:
            continue
        for term in added_terms:
            if term in accepted_term_set:
                new_term_counter[term] += 1
        changed_terms.append(
            {
                "object_name": sig[0],
                "document_code": sig[1],
                "added_terms": added_terms,
                "removed_terms": removed_terms,
                "accepted_added_terms": [term for term in added_terms if term in accepted_term_set],
                "text_sample": sig[2][:160],
            }
        )
    for sig in added_sigs:
        for term in overlay_by_sig[sig].get("matched_rule_terms") or []:
            if term in accepted_term_set:
                new_term_counter[term] += 1

    object_delta: dict[str, dict[str, int]] = {}
    for row in base_rows:
        object_delta.setdefault(text(row.get("object_name")), {"base": 0, "overlay": 0})["base"] += 1
    for row in overlay_rows:
        object_delta.setdefault(text(row.get("object_name")), {"base": 0, "overlay": 0})["overlay"] += 1

    return {
        "generated_by": "scripts/dev/retrieval_v2_recall_term_sampler.py",
        "version": SOURCE_AB_VERSION,
        "report_type": "recall_term_source_ab_report",
        "inputs": {
            "base_candidates_path": repo_relative(base_candidates_path),
            "overlay_candidates_path": repo_relative(overlay_candidates_path),
            "accepted_terms": sorted(accepted_term_set),
        },
        "safety": {
            "source_only": True,
            "writes_candidates": False,
            "writes_profile": False,
            "writes_db": False,
        },
        "summary": {
            "base_slice_count": len(base_rows),
            "overlay_slice_count": len(overlay_rows),
            "slice_count_delta": len(overlay_rows) - len(base_rows),
            "added_slice_count": len(added_sigs),
            "removed_slice_count": len(removed_sigs),
            "changed_term_slice_count": len(changed_terms),
            "overlay_accepted_term_hits": dict(sorted(overlay_hit_counter.items())),
            "new_accepted_term_hits": dict(sorted(new_term_counter.items())),
            "object_slice_delta": {
                key: {"base": value["base"], "overlay": value["overlay"], "delta": value["overlay"] - value["base"]}
                for key, value in sorted(object_delta.items())
            },
        },
        "term_policy_recommendations": [recall_term_policy(term) for term in sorted(accepted_term_set)],
        "added_slices": [compact_slice(overlay_by_sig[sig], accepted_terms=accepted_term_set) for sig in added_sigs[:max_examples]],
        "removed_slices": [compact_slice(base_by_sig[sig], accepted_terms=accepted_term_set) for sig in removed_sigs[:max_examples]],
        "changed_term_slices": changed_terms[:max_examples],
    }


def names_for_slice(row: Mapping[str, Any]) -> set[str]:
    return {value for value in (text(row.get("target_name")), text(row.get("object_name"))) if value}


def term_rejection_reasons(term: str, rows: Sequence[Mapping[str, Any]]) -> list[str]:
    reasons: list[str] = []
    if term in CASE_TERM_BLOCKLIST:
        reasons.append("case_term_blocklist")
    if term in BOILERPLATE_TERMS or CALENDAR_RE.fullmatch(term):
        reasons.append("boilerplate_or_calendar_term")
    if term in OFFICE_TITLE_TERMS or any(title in term for title in OFFICE_TITLE_SUBSTRINGS):
        reasons.append("office_title_not_long_term_profile_term")
    if GRAMMAR_FRAGMENT_RE.search(term):
        reasons.append("grammar_fragment_not_profile_term")
    for row in rows:
        for name in names_for_slice(row):
            if term == name or (len(term) >= 2 and term in name):
                reasons.append("matches_target_or_object_name")
                return unique_strings(reasons)
    return unique_strings(reasons)


def term_tier(*, support_count: int, target_count: int, object_count: int, document_count: int, rejection_reasons: Sequence[str]) -> str:
    if rejection_reasons:
        return "reject_term"
    if support_count >= 3 and target_count >= 3 and object_count >= 3:
        return "core_term"
    if support_count >= 3 and (target_count >= 2 or object_count >= 2) and document_count >= 2:
        return "conditional_term"
    return "case_term"


def score_term(*, support_count: int, target_count: int, object_count: int, document_count: int, tier: str) -> float:
    tier_bonus = {"core_term": 8.0, "conditional_term": 4.0, "case_term": 0.0, "reject_term": -100.0}.get(tier, 0.0)
    return round(tier_bonus + math.log1p(support_count) + target_count * 1.5 + object_count + document_count * 0.5, 3)


def candidate_ab_rows(terms: Sequence[Mapping[str, Any]], rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for term_row in terms:
        term = text(term_row.get("term"))
        if not term:
            continue
        text_hit_rows = [row for row in rows if term in text(row.get("text"))]
        already_matched_rows = [
            row
            for row in text_hit_rows
            if term in {text(value) for value in row.get("matched_rule_terms") or []}
        ]
        new_hit_rows = [row for row in text_hit_rows if row not in already_matched_rows]
        role_counts: Counter[str] = Counter()
        for row in text_hit_rows:
            for family in row.get("matched_role_families") or []:
                role_counts[text(family)] += 1
        result.append(
            {
                "term": term,
                "tier": text(term_row.get("tier")),
                "text_hit_count": len(text_hit_rows),
                "already_matched_count": len(already_matched_rows),
                "new_text_hit_count": len(new_hit_rows),
                "hit_object_diversity": len({text(row.get("object_name")) for row in text_hit_rows if text(row.get("object_name"))}),
                "hit_target_diversity": len({text(row.get("target_name")) for row in text_hit_rows if text(row.get("target_name"))}),
                "hit_role_family_counts": dict(sorted(role_counts.items())),
                "rejection_reasons": list(term_row.get("rejection_reasons") or []),
                "new_hit_examples": [
                    {
                        "source_path": text(row.get("source_path")),
                        "target_name": text(row.get("target_name")),
                        "object_name": text(row.get("object_name")),
                        "slice_code": text(row.get("slice_code")),
                        "text_sample": text(row.get("text"))[:120],
                    }
                    for row in new_hit_rows[:3]
                ],
            }
        )
    return sorted(result, key=lambda row: (-int(row["new_text_hit_count"]), -int(row["hit_object_diversity"]), str(row["term"])))


def profile_patch_template(
    report: Mapping[str, Any],
    *,
    min_new_hits: int,
    min_object_diversity: int,
    max_terms: int,
    accepted_terms: Sequence[str] = (),
) -> dict[str, Any]:
    candidate_ab = report.get("candidate_ab") if isinstance(report.get("candidate_ab"), Mapping) else {}
    ab_terms = candidate_ab.get("terms") if isinstance(candidate_ab.get("terms"), list) else []
    accepted_tiers = {"core_term", "conditional_term"}
    accepted_term_set = set(unique_strings(accepted_terms))
    rows: list[dict[str, Any]] = []
    raw_by_term: dict[str, Mapping[str, Any]] = {}

    def make_patch_row(raw: Mapping[str, Any], *, accepted: bool) -> dict[str, Any]:
        term = text(raw.get("term"))
        suggestion, flags = profile_review_suggestion(term)
        return {
            "term": term,
            "proposed_location": "source_discovery_profile",
            "profile_scope": "personnel_political_wide",
            "review_status": "accepted" if accepted else "pending",
            "accepted_for_profile": accepted,
            "review_suggestion": suggestion,
            "review_flags": [*flags, *(["accepted_by_explicit_term_list"] if accepted else [])],
            "tier": text(raw.get("tier")),
            "evidence": {
                "new_text_hit_count": int(raw.get("new_text_hit_count") or 0),
                "text_hit_count": int(raw.get("text_hit_count") or 0),
                "already_matched_count": int(raw.get("already_matched_count") or 0),
                "hit_object_diversity": int(raw.get("hit_object_diversity") or 0),
                "hit_target_diversity": int(raw.get("hit_target_diversity") or 0),
                "hit_role_family_counts": dict(raw.get("hit_role_family_counts") or {}),
            },
            "rationale": "candidate-only A/B found reviewable new text hits; requires human review before profile use",
            "new_hit_examples": list(raw.get("new_hit_examples") or []),
        }

    for raw in ab_terms:
        if not isinstance(raw, Mapping):
            continue
        term = text(raw.get("term"))
        if term:
            raw_by_term[term] = raw
        tier = text(raw.get("tier"))
        rejection_reasons = list(raw.get("rejection_reasons") or [])
        new_hits = int(raw.get("new_text_hit_count") or 0)
        object_diversity = int(raw.get("hit_object_diversity") or 0)
        if tier not in accepted_tiers or rejection_reasons:
            continue
        if PROFILE_PATCH_NOISE_RE.search(text(raw.get("term"))):
            continue
        if new_hits < min_new_hits or object_diversity < min_object_diversity:
            continue
        rows.append(make_patch_row(raw, accepted=term in accepted_term_set))
    existing_terms = {row["term"] for row in rows}
    for term in sorted(accepted_term_set - existing_terms):
        raw = raw_by_term.get(term)
        if raw is not None:
            rows.append(make_patch_row(raw, accepted=True))
    if max_terms > 0:
        rows = sorted(rows, key=lambda row: (row["accepted_for_profile"] is not True, row["term"]))[:max_terms]
    return {
        "generated_by": "scripts/dev/retrieval_v2_recall_term_sampler.py",
        "version": PROFILE_PATCH_VERSION,
        "report_type": "recall_term_profile_patch_template",
        "source_report_version": report.get("version"),
        "safety": {
            "writes_profile": False,
            "requires_human_review": True,
            "default_accepted_for_profile": False,
        },
        "selection": {
            "min_new_hits": min_new_hits,
            "min_object_diversity": min_object_diversity,
            "max_terms": max_terms,
            "accepted_tiers": sorted(accepted_tiers),
            "explicit_accepted_terms": sorted(accepted_term_set),
        },
        "summary": {
            "candidate_term_count": len(rows),
            "accepted_term_count": sum(1 for row in rows if row["accepted_for_profile"] is True),
            "review_suggestion_counts": dict(sorted(Counter(row["review_suggestion"] for row in rows).items())),
        },
        "terms": rows,
    }


def profile_delta_from_patch(profile_patch: Mapping[str, Any]) -> dict[str, Any]:
    terms = profile_patch.get("terms") if isinstance(profile_patch.get("terms"), list) else []
    accepted_terms = unique_strings(
        row.get("term")
        for row in terms
        if isinstance(row, Mapping) and row.get("accepted_for_profile") is True
    )
    policies = [recall_term_policy(term) for term in accepted_terms]
    append_terms = [row["term"] for row in policies if row["profile_action"] == "append_rule_term"]
    conditional_terms = [row for row in policies if row["profile_action"] == "conditional_term"]
    rejected_terms = [row for row in policies if row["profile_action"] == "reject_term"]
    context_only_terms = [row for row in policies if row["profile_action"] == "context_only"]
    taxonomy_review_terms = [row for row in policies if row["profile_action"] == "needs_taxonomy_review"]
    proposed_updates = []
    if append_terms:
        proposed_updates.append(
            {
                "profile_scope": "personnel_political_wide",
                "target_location": "source_discovery_profile",
                "target_field": "rule_terms",
                "operation": "append_unique",
                "add_terms": append_terms,
            }
        )
    if conditional_terms:
        proposed_updates.append(
            {
                "profile_scope": "personnel_political_wide",
                "target_location": "source_discovery_profile",
                "target_field": "conditional_rule_terms",
                "operation": "append_guarded_terms",
                "conditional_terms": conditional_terms,
            }
        )
    return {
        "generated_by": "scripts/dev/retrieval_v2_recall_term_sampler.py",
        "version": PROFILE_DELTA_VERSION,
        "report_type": "recall_term_profile_delta",
        "source_patch_version": profile_patch.get("version"),
        "safety": {
            "writes_profile": False,
            "requires_human_review": True,
            "requires_regression_before_prompt_removal": True,
        },
        "summary": {
            "accepted_term_count": len(accepted_terms),
            "append_rule_term_count": len(append_terms),
            "conditional_term_count": len(conditional_terms),
            "rejected_term_count": len(rejected_terms),
            "context_only_term_count": len(context_only_terms),
            "taxonomy_review_term_count": len(taxonomy_review_terms),
            "proposed_update_count": len(proposed_updates),
        },
        "term_policy_recommendations": policies,
        "proposed_updates": proposed_updates,
    }


def profile_review_suggestion(term: str) -> tuple[str, list[str]]:
    flags: list[str] = []
    if PROFILE_CANDIDATE_RE.search(term):
        flags.append("mechanism_like_profile_term")
        return "profile_candidate_review", flags
    if PROFILE_CONTEXT_RE.search(term):
        flags.append("context_or_noise_risk")
        return "context_or_noise_review", flags
    flags.append("manual_review_required")
    return "needs_human_review", flags


def collect_term_stats(
    rows: Sequence[Mapping[str, Any]],
    *,
    min_chars: int,
    max_chars: int,
    include_text_ngrams: bool,
) -> list[dict[str, Any]]:
    support_rows: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    matched_rule_term_counts: Counter[str] = Counter()
    text_ngram_counts: Counter[str] = Counter()
    role_family_counts: dict[str, Counter[str]] = defaultdict(Counter)

    for row in rows:
        row_text = text(row.get("text"))
        text_terms = cjk_ngrams(row_text, min_chars=min_chars, max_chars=max_chars) if include_text_ngrams else set()
        text_terms = {term for term in text_terms if looks_like_mechanism_ngram(term)}
        text_terms.update(term for term in CASE_TERM_BLOCKLIST if term in row_text)
        matched_terms = {term for term in row.get("matched_rule_terms") or [] if is_candidate_term(text(term))}
        for term in sorted(text_terms | matched_terms):
            support_rows[term].append(row)
            if term in matched_terms:
                matched_rule_term_counts[term] += 1
            if term in text_terms:
                text_ngram_counts[term] += 1
            for family in row.get("matched_role_families") or []:
                role_family_counts[term][text(family)] += 1

    result: list[dict[str, Any]] = []
    for term, term_rows in support_rows.items():
        target_names = {text(row.get("target_name")) for row in term_rows if text(row.get("target_name"))}
        object_names = {text(row.get("object_name")) for row in term_rows if text(row.get("object_name"))}
        document_codes = {text(row.get("document_code")) for row in term_rows if text(row.get("document_code"))}
        source_paths = {text(row.get("source_path")) for row in term_rows if text(row.get("source_path"))}
        rejection_reasons = term_rejection_reasons(term, term_rows)
        tier = term_tier(
            support_count=len(term_rows),
            target_count=len(target_names),
            object_count=len(object_names),
            document_count=len(document_codes),
            rejection_reasons=rejection_reasons,
        )
        result.append(
            {
                "term": term,
                "tier": tier,
                "score": score_term(
                    support_count=len(term_rows),
                    target_count=len(target_names),
                    object_count=len(object_names),
                    document_count=len(document_codes),
                    tier=tier,
                ),
                "support_count": len(term_rows),
                "target_diversity": len(target_names),
                "object_diversity": len(object_names),
                "document_diversity": len(document_codes),
                "source_file_diversity": len(source_paths),
                "matched_rule_term_count": matched_rule_term_counts[term],
                "text_ngram_count": text_ngram_counts[term],
                "role_family_counts": dict(sorted(role_family_counts[term].items())),
                "rejection_reasons": rejection_reasons,
                "examples": [
                    {
                        "source_path": text(row.get("source_path")),
                        "target_name": text(row.get("target_name")),
                        "object_name": text(row.get("object_name")),
                        "slice_code": text(row.get("slice_code")),
                        "text_sample": text(row.get("text"))[:120],
                    }
                    for row in term_rows[:3]
                ],
            }
        )
    return sorted(result, key=lambda row: (-float(row["score"]), str(row["tier"]), str(row["term"])))


def filtered_terms(terms: Sequence[Mapping[str, Any]], *, min_support: int, include_case_terms: bool, top: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for term in terms:
        tier = text(term.get("tier"))
        support = int(term.get("support_count") or 0)
        if support < min_support and tier not in {"reject_term"}:
            continue
        if not include_case_terms and tier == "case_term":
            continue
        rows.append(dict(term))
    return rows[:top] if top > 0 else rows


def enrich_terms_with_policy(terms: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in terms:
        term = text(row.get("term"))
        result.append({**dict(row), "policy": recall_term_policy(term)})
    return result


def taxonomy_validation_summary(terms: Sequence[Mapping[str, Any]], *, max_unknown_terms: int = 30) -> dict[str, Any]:
    action_counts: Counter[str] = Counter()
    group_counts: Counter[str] = Counter()
    unknown_terms: list[dict[str, Any]] = []
    for row in terms:
        policy = row.get("policy") if isinstance(row.get("policy"), Mapping) else recall_term_policy(text(row.get("term")))
        action = text(policy.get("profile_action"))
        group = text(policy.get("policy_group"))
        action_counts[action] += 1
        group_counts[group] += 1
        if action == "needs_taxonomy_review":
            unknown_terms.append(
                {
                    "term": row.get("term"),
                    "tier": row.get("tier"),
                    "support_count": int(row.get("support_count") or 0),
                    "target_diversity": int(row.get("target_diversity") or 0),
                    "object_diversity": int(row.get("object_diversity") or 0),
                    "matched_rule_term_count": int(row.get("matched_rule_term_count") or 0),
                    "text_ngram_count": int(row.get("text_ngram_count") or 0),
                    "examples": list(row.get("examples") or [])[:2],
                }
            )
    unknown_terms.sort(
        key=lambda row: (
            -int(row["support_count"]),
            -int(row["object_diversity"]),
            -int(row["target_diversity"]),
            str(row["term"]),
        )
    )
    return {
        "policy_action_counts": dict(sorted(action_counts.items())),
        "policy_group_counts": dict(sorted(group_counts.items())),
        "needs_taxonomy_review_count": action_counts.get("needs_taxonomy_review", 0),
        "top_needs_taxonomy_review_terms": unknown_terms[:max_unknown_terms],
    }


def build_report(
    *,
    candidates_paths: Sequence[Path],
    min_chars: int,
    max_chars: int,
    include_text_ngrams: bool,
    include_candidate_ab: bool,
    min_support: int,
    include_case_terms: bool,
    top: int,
) -> dict[str, Any]:
    slice_rows = [row for path in candidates_paths for row in load_candidate_slices(path)]
    all_terms = collect_term_stats(slice_rows, min_chars=min_chars, max_chars=max_chars, include_text_ngrams=include_text_ngrams)
    terms = enrich_terms_with_policy(filtered_terms(all_terms, min_support=min_support, include_case_terms=include_case_terms, top=top))
    tier_counts = Counter(text(row.get("tier")) for row in all_terms)
    report = {
        "generated_by": "scripts/dev/retrieval_v2_recall_term_sampler.py",
        "version": REPORT_VERSION,
        "report_type": "recall_term_sampling_report",
        "inputs": {
            "candidates_paths": [repo_relative(path) for path in candidates_paths],
            "candidate_file_count": len(candidates_paths),
            "candidate_slice_count": len(slice_rows),
            "min_chars": min_chars,
            "max_chars": max_chars,
            "include_text_ngrams": include_text_ngrams,
            "include_candidate_ab": include_candidate_ab,
            "min_support": min_support,
            "include_case_terms": include_case_terms,
            "top": top,
        },
        "summary": {
            "raw_term_count": len(all_terms),
            "reported_term_count": len(terms),
            "tier_counts": dict(sorted(tier_counts.items())),
        },
        "taxonomy_validation": taxonomy_validation_summary(terms),
        "terms": terms,
    }
    if include_candidate_ab:
        ab_terms = candidate_ab_rows(terms, slice_rows)
        report["candidate_ab"] = {
            "summary": {
                "term_count": len(ab_terms),
                "terms_with_new_text_hits": sum(1 for row in ab_terms if int(row["new_text_hit_count"]) > 0),
            },
            "terms": ab_terms,
        }
    return report


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), Mapping) else {}
    inputs = report.get("inputs") if isinstance(report.get("inputs"), Mapping) else {}
    taxonomy = report.get("taxonomy_validation") if isinstance(report.get("taxonomy_validation"), Mapping) else {}
    lines = [
        "# retrieval_v2 recall term sampling report",
        "",
        f"- version: `{report.get('version')}`",
        f"- candidate_file_count: `{inputs.get('candidate_file_count')}`",
        f"- candidate_slice_count: `{inputs.get('candidate_slice_count')}`",
        f"- raw_term_count: `{summary.get('raw_term_count')}`",
        f"- reported_term_count: `{summary.get('reported_term_count')}`",
        f"- tier_counts: `{json.dumps(summary.get('tier_counts') or {}, ensure_ascii=False, sort_keys=True)}`",
        f"- policy_action_counts: `{json.dumps(taxonomy.get('policy_action_counts') or {}, ensure_ascii=False, sort_keys=True)}`",
        f"- needs_taxonomy_review_count: `{taxonomy.get('needs_taxonomy_review_count')}`",
        "",
        "| term | tier | policy | group | support | target_diversity | object_diversity | matched_rule | score |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in report.get("terms") or []:
        if not isinstance(row, Mapping):
            continue
        policy = row.get("policy") if isinstance(row.get("policy"), Mapping) else {}
        lines.append(
            "| {term} | {tier} | {policy} | {group} | {support} | {target} | {obj} | {matched} | {score} |".format(
                term=row.get("term"),
                tier=row.get("tier"),
                policy=policy.get("profile_action"),
                group=policy.get("policy_group"),
                support=row.get("support_count"),
                target=row.get("target_diversity"),
                obj=row.get("object_diversity"),
                matched=row.get("matched_rule_term_count"),
                score=row.get("score"),
            )
        )
    unknown_terms = taxonomy.get("top_needs_taxonomy_review_terms") if isinstance(taxonomy.get("top_needs_taxonomy_review_terms"), list) else []
    if unknown_terms:
        lines.extend(
            [
                "",
                "## needs taxonomy review",
                "",
                "| term | tier | support | objects | targets | matched_rule | text_ngram |",
                "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in unknown_terms[:30]:
            if not isinstance(row, Mapping):
                continue
            lines.append(
                "| {term} | {tier} | {support} | {objects} | {targets} | {matched} | {ngram} |".format(
                    term=row.get("term"),
                    tier=row.get("tier"),
                    support=row.get("support_count"),
                    objects=row.get("object_diversity"),
                    targets=row.get("target_diversity"),
                    matched=row.get("matched_rule_term_count"),
                    ngram=row.get("text_ngram_count"),
                )
            )
    if isinstance(report.get("candidate_ab"), Mapping):
        ab_terms = report["candidate_ab"].get("terms") if isinstance(report["candidate_ab"].get("terms"), list) else []
        lines.extend(
            [
                "",
                "## candidate-only A/B",
                "",
                "| term | tier | text_hit | already_matched | new_text_hit | objects |",
                "| --- | --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in ab_terms[:50]:
            if not isinstance(row, Mapping):
                continue
            lines.append(
                "| {term} | {tier} | {text_hit} | {matched} | {new_hit} | {objects} |".format(
                    term=row.get("term"),
                    tier=row.get("tier"),
                    text_hit=row.get("text_hit_count"),
                    matched=row.get("already_matched_count"),
                    new_hit=row.get("new_text_hit_count"),
                    objects=row.get("hit_object_diversity"),
                )
            )
    return "\n".join(lines) + "\n"


def render_source_ab_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), Mapping) else {}
    inputs = report.get("inputs") if isinstance(report.get("inputs"), Mapping) else {}
    lines = [
        "# retrieval_v2 recall term source A/B report",
        "",
        f"- version: `{report.get('version')}`",
        f"- base: `{inputs.get('base_candidates_path')}`",
        f"- overlay: `{inputs.get('overlay_candidates_path')}`",
        f"- accepted_terms: `{json.dumps(inputs.get('accepted_terms') or [], ensure_ascii=False)}`",
        f"- base_slice_count: `{summary.get('base_slice_count')}`",
        f"- overlay_slice_count: `{summary.get('overlay_slice_count')}`",
        f"- slice_count_delta: `{summary.get('slice_count_delta')}`",
        f"- added_slice_count: `{summary.get('added_slice_count')}`",
        f"- removed_slice_count: `{summary.get('removed_slice_count')}`",
        f"- changed_term_slice_count: `{summary.get('changed_term_slice_count')}`",
        f"- overlay_accepted_term_hits: `{json.dumps(summary.get('overlay_accepted_term_hits') or {}, ensure_ascii=False, sort_keys=True)}`",
        f"- new_accepted_term_hits: `{json.dumps(summary.get('new_accepted_term_hits') or {}, ensure_ascii=False, sort_keys=True)}`",
        "",
        "## term policy recommendations",
        "",
        "| term | action | group | risk | guard_any |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in report.get("term_policy_recommendations") or []:
        if not isinstance(row, Mapping):
            continue
        guard = row.get("guard") if isinstance(row.get("guard"), Mapping) else {}
        lines.append(
            "| {term} | {action} | {group} | {risk} | {guard} |".format(
                term=row.get("term"),
                action=row.get("profile_action"),
                group=row.get("policy_group"),
                risk=row.get("risk_level"),
                guard=json.dumps(guard.get("requires_near_any") or [], ensure_ascii=False),
            )
        )
    lines.extend(
        [
            "",
            "## changed term slices",
            "",
            "| object | document | added_terms | removed_terms | text_sample |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in report.get("changed_term_slices") or []:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            "| {object} | {document} | {added} | {removed} | {sample} |".format(
                object=row.get("object_name"),
                document=row.get("document_code"),
                added=json.dumps(row.get("added_terms") or [], ensure_ascii=False),
                removed=json.dumps(row.get("removed_terms") or [], ensure_ascii=False),
                sample=text(row.get("text_sample")).replace("|", "｜"),
            )
        )
    lines.extend(["", "## added slices", "", "| object | document | accepted_hits | text_sample |", "| --- | --- | --- | --- |"])
    for row in report.get("added_slices") or []:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            "| {object} | {document} | {hits} | {sample} |".format(
                object=row.get("object_name"),
                document=row.get("document_code"),
                hits=json.dumps(row.get("accepted_term_hits") or [], ensure_ascii=False),
                sample=text(row.get("text_sample")).replace("|", "｜"),
            )
        )
    return "\n".join(lines) + "\n"


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) + "\n" for row in rows), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sample and classify retrieval_v2 recall terms from local candidate slices.")
    parser.add_argument("--source-ab-base", type=Path)
    parser.add_argument("--source-ab-overlay", type=Path)
    parser.add_argument("--source-ab-accepted-term", action="append", default=[])
    parser.add_argument("--source-ab-max-examples", type=int, default=50)
    parser.add_argument("--output-source-ab-json", type=Path)
    parser.add_argument("--output-source-ab-md", type=Path)
    parser.add_argument("--candidates", type=Path, action="append", default=[])
    parser.add_argument("--run-root", type=Path, action="append", default=[])
    parser.add_argument("--min-chars", type=int, default=2)
    parser.add_argument("--max-chars", type=int, default=4)
    parser.add_argument("--include-text-ngrams", action="store_true")
    parser.add_argument("--include-candidate-ab", action="store_true")
    parser.add_argument("--min-support", type=int, default=2)
    parser.add_argument("--include-case-terms", action="store_true")
    parser.add_argument("--top", type=int, default=200)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--output-jsonl", type=Path)
    parser.add_argument("--output-profile-patch", type=Path)
    parser.add_argument("--output-profile-delta", type=Path)
    parser.add_argument("--profile-min-new-hits", type=int, default=6)
    parser.add_argument("--profile-min-object-diversity", type=int, default=3)
    parser.add_argument("--profile-max-terms", type=int, default=50)
    parser.add_argument("--accept-term", action="append", default=[])
    return parser


def candidate_paths_from_args(args: argparse.Namespace) -> list[Path]:
    paths = [path for path in args.candidates if path.exists()]
    for run_root in args.run_root:
        paths.extend(candidate_paths_from_run_root(run_root))
    deduped: dict[str, Path] = {}
    for path in paths:
        deduped[str(path.resolve())] = path
    return sorted(deduped.values(), key=lambda path: str(path))


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.source_ab_base or args.source_ab_overlay:
        if not args.source_ab_base or not args.source_ab_overlay:
            parser.error("--source-ab-base and --source-ab-overlay must be provided together")
        source_ab_report = build_source_ab_report(
            base_candidates_path=args.source_ab_base,
            overlay_candidates_path=args.source_ab_overlay,
            accepted_terms=args.source_ab_accepted_term,
            max_examples=args.source_ab_max_examples,
        )
        if args.output_source_ab_json is not None:
            write_json(args.output_source_ab_json, source_ab_report)
        if args.output_source_ab_md is not None:
            args.output_source_ab_md.parent.mkdir(parents=True, exist_ok=True)
            args.output_source_ab_md.write_text(render_source_ab_markdown(source_ab_report), encoding="utf-8")
        print(
            stable_json(
                {
                    "ok": True,
                    "summary": source_ab_report["summary"],
                    "output_source_ab_json": str(args.output_source_ab_json) if args.output_source_ab_json else None,
                    "output_source_ab_md": str(args.output_source_ab_md) if args.output_source_ab_md else None,
                }
            )
        )
        return 0
    candidates_paths = candidate_paths_from_args(args)
    if not candidates_paths:
        parser.error("provide --candidates or --run-root with candidates.final.json files")
    include_candidate_ab = args.include_candidate_ab or args.output_profile_patch is not None or args.output_profile_delta is not None
    report = build_report(
        candidates_paths=candidates_paths,
        min_chars=args.min_chars,
        max_chars=args.max_chars,
        include_text_ngrams=args.include_text_ngrams,
        include_candidate_ab=include_candidate_ab,
        min_support=args.min_support,
        include_case_terms=args.include_case_terms,
        top=args.top,
    )
    if args.output_json is not None:
        write_json(args.output_json, report)
    if args.output_md is not None:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(render_markdown(report), encoding="utf-8")
    if args.output_jsonl is not None:
        write_jsonl(args.output_jsonl, report.get("terms") or [])
    profile_patch = None
    profile_delta = None
    if args.output_profile_patch is not None or args.output_profile_delta is not None:
        profile_patch = profile_patch_template(
            report,
            min_new_hits=args.profile_min_new_hits,
            min_object_diversity=args.profile_min_object_diversity,
            max_terms=args.profile_max_terms,
            accepted_terms=args.accept_term,
        )
    if args.output_profile_patch is not None and profile_patch is not None:
        write_json(args.output_profile_patch, profile_patch)
    if args.output_profile_delta is not None and profile_patch is not None:
        profile_delta = profile_delta_from_patch(profile_patch)
        write_json(args.output_profile_delta, profile_delta)
    print(
        stable_json(
            {
                "ok": True,
                "summary": report["summary"],
                "inputs": report["inputs"],
                "profile_patch_terms": (profile_patch or {}).get("summary", {}).get("candidate_term_count"),
                "profile_delta_terms": (profile_delta or {}).get("summary", {}).get("accepted_term_count"),
            }
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
