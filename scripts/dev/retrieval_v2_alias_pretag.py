from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]

from scripts.dev.retrieval_v2_target_alias_backfill import (  # noqa: E402
    DEFAULT_ALIAS_FILE,
    DEFAULT_EMPEROR_LIST,
    alias_payload,
    alias_rows_for_emperors,
    load_alias_seed,
    load_emperor_names,
)
from scripts.dev.retrieval_v2_intake_manifest import text  # noqa: E402


RULER_ACTION_TYPES = {"任命", "授权", "处置", "收权", "制度高压", "纳谏", "拒谏", "战役", "其他"}
BARE_TITLE_TYPES = {"temple_name", "posthumous_name"}
CONTEXT_ONLY_OWNER_RELATION_TERMS = ("亲礼", "所亲", "亲待", "礼遇")
TITLE_ALIAS_TYPES = {"title"}
TITLE_ALIAS_BOUNDARY_FOLLOWERS = set("曰云言谓謂问問命诏詔使遣以为為用处處即及与與从從在于於之所将將率领領召征徵至入出拜授封立废廢薨崩卒死杀殺诛誅罢罷怒喜")
COMMON_CJK_SURNAME_CHARS = set(
    "赵錢钱孙孫李周吴吳郑鄭王冯馮陈陳褚卫衛蒋蔣沈韩韓杨楊朱秦尤许許何吕呂施张張孔曹严嚴华華金魏陶姜戚谢謝邹鄒喻柏水窦竇章云雲苏蘇潘葛奚范彭郎鲁魯韦韋昌马馬苗凤鳳花方俞任袁柳鲍鮑史唐费費廉岑薛雷贺賀倪汤湯滕殷罗羅毕畢郝邬鄔安常乐樂于於时時傅皮卞齐齊康伍余元卜顾顧孟平黄黃和穆萧蕭尹姚邵湛汪祁毛禹狄米贝貝明臧计計伏成戴宋茅庞龐熊纪紀舒屈项項祝董梁杜阮蓝藍闵閔席季麻强強贾賈路娄婁危江童颜顏郭梅盛林刁钟鍾徐邱骆駱高夏蔡田胡凌霍虞万萬支柯昝管卢盧莫经經房裘缪繆干解应應宗丁宣邓鄧郁单單杭洪包诸諸左石崔吉龚龔程邢裴陆陸荣榮翁荀羊甄曲家封芮羿储儲靳汲邴糜松井段富巫乌烏焦巴弓牧隗山谷车車侯宓蓬全郗班仰秋仲伊宫宮宁甯仇栾欒暴甘斜厉厲戎祖武符刘劉景詹束龙龍叶葉幸司韶郜黎蓟薊薄印宿白怀懷蒲台臺从從鄂索咸籍赖賴卓蔺藺屠蒙池乔喬阴陰胥能苍蒼双雙闻聞莘党黨翟谭譚贡貢劳勞逄姬申扶堵冉宰郦酈雍璩桑桂濮牛寿壽通边邊扈燕冀郏郟浦尚农農温别別庄莊晏柴瞿阎閻充慕连連茹习習宦艾鱼魚容向古易慎戈廖庾终終暨居衡步都耿满滿弘匡国國文寇广廣禄祿阙闕东東殴歐殳沃利蔚越夔隆师師巩鞏厍厙聂聶晁勾敖融冷訾辛阚闞那简簡饶饒空曾毋沙乜养養鞠须須丰豐巢关關蒯相查后荆荊红紅游竺权權逯盖蓋益桓公"
)
SHORT_ALIAS_BOUNDARY_PRECEDERS = set("向问問谓謂白告奏诏詔命令使遣从從随隨及与與为為以于於至入出拜授封立废廢诛誅杀殺罢罷")
SOURCE_TITLE_DYNASTY_MARKERS = (
    ("旧唐书", "唐"),
    ("舊唐書", "唐"),
    ("新唐书", "唐"),
    ("新唐書", "唐"),
    ("唐书", "唐"),
    ("唐書", "唐"),
    ("宋史", "宋"),
    ("明史", "明"),
    ("清史稿", "清"),
    ("隋书", "隋"),
    ("隋書", "隋"),
    ("汉书", "汉"),
    ("漢書", "汉"),
    ("后汉书", "汉"),
    ("後漢書", "汉"),
)


@dataclass(frozen=True)
class AliasEntry:
    owner_name: str
    alias: str
    alias_type: str
    scopes: tuple[str, ...]


@dataclass(frozen=True)
class AliasResolver:
    entries: tuple[AliasEntry, ...]
    source: str


def unique_texts(values: Sequence[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        item = text(value)
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def alias_resolver_from_rows(rows: Sequence[Mapping[str, Any]], *, source: str) -> AliasResolver:
    entries: list[AliasEntry] = []
    seen: set[tuple[str, str, str, tuple[str, ...]]] = set()
    for row in rows:
        owner_name = text(row.get("emperor_name"))
        alias = text(row.get("alias"))
        alias_type = text(row.get("alias_type")) or "alias"
        payload = row.get("alias_payload") if isinstance(row.get("alias_payload"), Mapping) else {}
        scopes = payload.get("scopes") if isinstance(payload, Mapping) else []
        if isinstance(scopes, str):
            scopes = [scopes]
        clean_scopes = tuple(unique_texts(scopes if isinstance(scopes, list) else []))
        if not owner_name or not alias:
            continue
        key = (owner_name, alias, alias_type, clean_scopes)
        if key in seen:
            continue
        seen.add(key)
        entries.append(AliasEntry(owner_name=owner_name, alias=alias, alias_type=alias_type, scopes=clean_scopes))
    entries.sort(key=lambda item: (-len(item.alias), item.alias, item.owner_name))
    return AliasResolver(entries=tuple(entries), source=source)


def load_alias_resolver(
    *,
    emperor_list: Path = DEFAULT_EMPEROR_LIST,
    alias_file: Path = DEFAULT_ALIAS_FILE,
) -> AliasResolver:
    emperor_names = load_emperor_names(emperor_list)
    alias_seed = load_alias_seed(alias_file)
    rows = [
        {**row, "alias_payload": alias_payload(row)}
        for row in alias_rows_for_emperors(emperor_names, alias_seed)
    ]
    return alias_resolver_from_rows(rows, source=str(alias_file))


def canonical_owner_name(value: str, *, resolver: AliasResolver | None = None) -> str:
    resolver = resolver or load_alias_resolver()
    name = text(value)
    if not name:
        return ""
    if any(entry.owner_name == name for entry in resolver.entries):
        return name
    matches = [
        entry
        for entry in resolver.entries
        if entry.alias == name and (not entry.scopes or len(entry.alias) > 2)
    ]
    owners = sorted({entry.owner_name for entry in matches})
    return owners[0] if len(owners) == 1 else name


def candidate_requested_owner(candidates: Mapping[str, Any]) -> str:
    task_identity = candidates.get("task_identity") if isinstance(candidates.get("task_identity"), Mapping) else {}
    target_profile = candidates.get("target_profile") if isinstance(candidates.get("target_profile"), Mapping) else {}
    return text(task_identity.get("emperor_name")) or text(target_profile.get("primary_name"))


def active_entries_for_alias(
    resolver: AliasResolver,
    alias: str,
    *,
    requested_owner_name: str,
    source_dynasty_prefixes: Sequence[str] = (),
) -> list[AliasEntry]:
    requested = text(requested_owner_name)
    dynasty_matched_owners = owners_for_dynasty_bare_alias(
        resolver,
        alias,
        source_dynasty_prefixes=source_dynasty_prefixes,
    )
    rows = [
        entry
        for entry in resolver.entries
        if entry.alias == alias
        and (
            not entry.scopes
            or requested in entry.scopes
            or entry.owner_name in dynasty_matched_owners
        )
    ]
    return sorted(rows, key=lambda item: (item.owner_name, item.alias_type))


def source_dynasty_prefixes_from_title(source_title: str) -> list[str]:
    title = text(source_title)
    return unique_texts([prefix for marker, prefix in SOURCE_TITLE_DYNASTY_MARKERS if marker in title])


def owners_for_dynasty_bare_alias(
    resolver: AliasResolver,
    alias: str,
    *,
    source_dynasty_prefixes: Sequence[str],
) -> set[str]:
    alias_text = text(alias)
    if len(alias_text) > 2 or not source_dynasty_prefixes:
        return set()
    full_aliases = {f"{prefix}{alias_text}" for prefix in source_dynasty_prefixes if prefix}
    return {entry.owner_name for entry in resolver.entries if entry.alias in full_aliases}


def resolution_rule(
    entry: AliasEntry,
    *,
    requested_owner_name: str,
    source_dynasty_prefixes: Sequence[str] = (),
    source_dynasty_owner_match: bool = False,
) -> str:
    if entry.alias_type == "name":
        return "canonical_name"
    if source_dynasty_prefixes and source_dynasty_owner_match:
        return "source_title_dynasty_bare_title"
    if entry.scopes and entry.alias_type in BARE_TITLE_TYPES and len(entry.alias) <= 2:
        return "same_dynasty_bare_title_scope"
    if entry.scopes:
        return "scoped_alias_by_requested_owner"
    return "unique_global_alias"


def iter_alias_positions(text_value: str, aliases: Sequence[str]) -> list[tuple[str, int, int]]:
    positions: list[tuple[str, int, int]] = []
    for alias in sorted(unique_texts(aliases), key=lambda item: (-len(item), item)):
        start = 0
        while alias:
            index = text_value.find(alias, start)
            if index < 0:
                break
            positions.append((alias, index, index + len(alias)))
            start = index + max(1, len(alias))
    positions.sort(key=lambda row: (row[1], -(row[2] - row[1]), row[0]))
    return positions


def overlap(span: tuple[int, int], used: Sequence[tuple[int, int]]) -> bool:
    start, end = span
    return any(start < used_end and end > used_start for used_start, used_end in used)


def is_cjk_char(value: str) -> bool:
    return len(value) == 1 and "\u4e00" <= value <= "\u9fff"


def title_alias_followed_by_non_owner_name(text_value: str, alias_end: int, entries: Sequence[AliasEntry]) -> bool:
    if not any(entry.alias_type in TITLE_ALIAS_TYPES for entry in entries):
        return False
    suffix = text_value[alias_end : alias_end + 4]
    if not suffix or not is_cjk_char(suffix[0]) or suffix[0] in TITLE_ALIAS_BOUNDARY_FOLLOWERS:
        return False
    for entry in entries:
        if entry.alias_type not in TITLE_ALIAS_TYPES:
            continue
        owner = text(entry.owner_name)
        owner_given = owner[1:] if len(owner) >= 2 else owner
        if owner and suffix.startswith(owner):
            return False
        if owner_given and suffix.startswith(owner_given):
            return False
    return True


def alias_inside_book_title(text_value: str, alias_start: int, alias_end: int) -> bool:
    left = text_value.rfind("《", 0, alias_start + 1)
    right = text_value.find("》", alias_end)
    if left < 0 or right < 0:
        return False
    close_before = text_value.rfind("》", 0, alias_start + 1)
    open_after = text_value.find("《", alias_start + 1, right + 1)
    return close_before < left and open_after < 0


def short_alias_embedded_after_surname(text_value: str, alias_start: int, alias: str) -> bool:
    if len(alias) > 2 or alias_start <= 0:
        return False
    previous = text_value[alias_start - 1]
    if previous in SHORT_ALIAS_BOUNDARY_PRECEDERS:
        return False
    return is_cjk_char(previous) and previous in COMMON_CJK_SURNAME_CHARS


def alias_suppression_reason(
    text_value: str,
    *,
    alias: str,
    start: int,
    end: int,
    active_entries: Sequence[AliasEntry],
) -> str:
    if alias_inside_book_title(text_value, start, end):
        return "alias_inside_book_title"
    if short_alias_embedded_after_surname(text_value, start, alias):
        return "short_alias_embedded_after_surname"
    if title_alias_followed_by_non_owner_name(text_value, end, active_entries):
        return "title_alias_followed_by_non_owner_name"
    return ""


def alias_risk_flags(
    *,
    alias: str,
    entries: Sequence[AliasEntry],
    source_dynasty_prefixes: Sequence[str],
    suppression_reason: str = "",
) -> list[str]:
    flags: list[str] = []
    alias_types = {entry.alias_type for entry in entries}
    if suppression_reason:
        flags.append(suppression_reason)
    if len(alias) <= 2:
        flags.append("short_alias")
    if alias_types & BARE_TITLE_TYPES:
        flags.append("bare_title_alias")
        if not source_dynasty_prefixes:
            flags.append("bare_title_without_source_title_dynasty")
    if alias_types & TITLE_ALIAS_TYPES:
        flags.append("title_alias")
    return unique_texts(flags)


def resolved_alias_mention(
    *,
    text_value: str,
    alias: str,
    start: int,
    end: int,
    entry: AliasEntry,
    requested_owner_name: str,
    source_dynasty_prefixes: Sequence[str],
    dynasty_owners: set[str],
    suppression_reason: str = "",
) -> dict[str, Any]:
    suppressed = bool(suppression_reason)
    return {
        "alias": alias,
        "matched_text": text_value[start:end],
        "resolved_owner_name": entry.owner_name,
        "resolution_status": "suppressed" if suppressed else "resolved",
        "resolution_rule": resolution_rule(
            entry,
            requested_owner_name=requested_owner_name,
            source_dynasty_prefixes=source_dynasty_prefixes,
            source_dynasty_owner_match=entry.owner_name in dynasty_owners,
        ),
        "confidence": "not_owner_anchor" if suppressed else "deterministic",
        "alias_type": entry.alias_type,
        "start": start,
        "end": end,
        "owner_relation_to_requested": "target_owner" if entry.owner_name == requested_owner_name else "other_owner",
        "scopes": list(entry.scopes),
        "source_dynasty_prefixes": list(source_dynasty_prefixes),
        "owner_anchor_eligible": not suppressed,
        "mention_role": "suppressed_owner_alias" if suppressed else "owner_anchor",
        "suppression_reason": suppression_reason,
        "risk_flags": alias_risk_flags(
            alias=alias,
            entries=[entry],
            source_dynasty_prefixes=source_dynasty_prefixes,
            suppression_reason=suppression_reason,
        ),
    }


def ambiguous_alias_mention(
    *,
    text_value: str,
    alias: str,
    start: int,
    end: int,
    active_entries: Sequence[AliasEntry],
    source_dynasty_prefixes: Sequence[str],
    suppression_reason: str = "",
) -> dict[str, Any]:
    owners = sorted({entry.owner_name for entry in active_entries})
    suppressed = bool(suppression_reason)
    return {
        "alias": alias,
        "matched_text": text_value[start:end],
        "resolved_owner_name": "",
        "candidate_owner_names": owners,
        "resolution_status": "suppressed" if suppressed else "ambiguous",
        "resolution_rule": "suppressed_ambiguous_alias" if suppressed else "ambiguous_alias",
        "confidence": "not_owner_anchor" if suppressed else "review",
        "start": start,
        "end": end,
        "owner_relation_to_requested": "ambiguous",
        "scopes": sorted({scope for entry in active_entries for scope in entry.scopes}),
        "source_dynasty_prefixes": list(source_dynasty_prefixes),
        "owner_anchor_eligible": False,
        "mention_role": "suppressed_owner_alias" if suppressed else "ambiguous_owner_alias",
        "suppression_reason": suppression_reason,
        "risk_flags": alias_risk_flags(
            alias=alias,
            entries=active_entries,
            source_dynasty_prefixes=source_dynasty_prefixes,
            suppression_reason=suppression_reason,
        ),
    }


def alias_mentions_in_text(
    text_value: str,
    *,
    requested_owner_name: str,
    source_title: str = "",
    resolver: AliasResolver | None = None,
    include_suppressed: bool = False,
) -> list[dict[str, Any]]:
    resolver = resolver or load_alias_resolver()
    requested = text(requested_owner_name)
    source_dynasty_prefixes = source_dynasty_prefixes_from_title(source_title)
    aliases = [entry.alias for entry in resolver.entries if entry.alias]
    mentions: list[dict[str, Any]] = []
    used_spans: list[tuple[int, int]] = []
    for alias, start, end in iter_alias_positions(text_value, aliases):
        if overlap((start, end), used_spans):
            continue
        active = active_entries_for_alias(
            resolver,
            alias,
            requested_owner_name=requested,
            source_dynasty_prefixes=source_dynasty_prefixes,
        )
        if not active:
            continue
        suppression_reason = alias_suppression_reason(
            text_value,
            alias=alias,
            start=start,
            end=end,
            active_entries=active,
        )
        if suppression_reason and not include_suppressed:
            continue
        dynasty_owners = owners_for_dynasty_bare_alias(
            resolver,
            alias,
            source_dynasty_prefixes=source_dynasty_prefixes,
        )
        owners = sorted({entry.owner_name for entry in active})
        if len(owners) == 1:
            entry = active[0]
            mentions.append(
                resolved_alias_mention(
                    text_value=text_value,
                    alias=alias,
                    start=start,
                    end=end,
                    entry=entry,
                    requested_owner_name=requested,
                    source_dynasty_prefixes=source_dynasty_prefixes,
                    dynasty_owners=dynasty_owners,
                    suppression_reason=suppression_reason,
                )
            )
        else:
            mentions.append(
                ambiguous_alias_mention(
                    text_value=text_value,
                    alias=alias,
                    start=start,
                    end=end,
                    active_entries=active,
                    source_dynasty_prefixes=source_dynasty_prefixes,
                    suppression_reason=suppression_reason,
                )
            )
        used_spans.append((start, end))
    return mentions


def slice_alias_mentions(
    row: Mapping[str, Any],
    *,
    requested_owner_name: str,
    resolver: AliasResolver | None = None,
    only_prompt_relevant: bool = False,
) -> list[dict[str, Any]]:
    mentions = alias_mentions_in_text(
        str(row.get("text") or row.get("raw_text") or ""),
        requested_owner_name=requested_owner_name,
        source_title=text(row.get("source_title") or row.get("title")),
        resolver=resolver,
    )
    if not only_prompt_relevant:
        return mentions
    return [
        mention
        for mention in mentions
        if mention.get("resolution_status") != "resolved"
        or text(mention.get("resolved_owner_name")) != text(requested_owner_name)
    ]


def alias_owner_index_for_slices(
    slices: Mapping[str, Mapping[str, Any]],
    *,
    requested_owner_name: str,
    resolver: AliasResolver | None = None,
) -> dict[str, list[dict[str, Any]]]:
    resolver = resolver or load_alias_resolver()
    return {
        source_ref: slice_alias_mentions(row, requested_owner_name=requested_owner_name, resolver=resolver)
        for source_ref, row in sorted(slices.items())
    }


def claim_actor_text(claim: Mapping[str, Any]) -> str:
    payload = claim.get("fact_payload") if isinstance(claim.get("fact_payload"), Mapping) else {}
    return text(payload.get("actor"))


def claim_action_type(claim: Mapping[str, Any]) -> str:
    payload = claim.get("fact_payload") if isinstance(claim.get("fact_payload"), Mapping) else {}
    return text(claim.get("action_type")) or text(payload.get("action_type"))


def claim_search_text(claim: Mapping[str, Any]) -> str:
    payload = claim.get("fact_payload") if isinstance(claim.get("fact_payload"), Mapping) else {}
    parts = [
        text(claim.get("claim_summary") or claim.get("summary")),
        text(claim.get("outcome")),
        text(payload.get("actor")),
        text(payload.get("object")),
        text(payload.get("outcome")),
    ]
    return " ".join(part for part in parts if part)


def owner_mentions_from_refs(
    *,
    source_refs: Sequence[str],
    alias_mentions_by_ref: Mapping[str, Sequence[Mapping[str, Any]]],
    current_owner: str,
) -> list[dict[str, Any]]:
    mentions: list[dict[str, Any]] = []
    for source_ref in source_refs:
        for mention in alias_mentions_by_ref.get(source_ref) or []:
            if text(mention.get("resolution_status")) != "resolved":
                continue
            if mention.get("owner_anchor_eligible") is False:
                continue
            owner = text(mention.get("resolved_owner_name"))
            alias = text(mention.get("alias"))
            if not owner or not alias:
                continue
            row = dict(mention)
            row["source_slice_ref"] = source_ref
            row["owner_relation_to_current"] = "current_owner" if owner == current_owner else "other_owner"
            mentions.append(row)
    return mentions


def owner_aliases_in_claim_text(claim_text: str, mentions: Sequence[Mapping[str, Any]], owner_name: str) -> list[str]:
    return unique_texts(
        [
            mention.get("alias")
            for mention in mentions
            if text(mention.get("resolved_owner_name")) == text(owner_name)
            and text(mention.get("alias"))
            and text(mention.get("alias")) in claim_text
        ]
    )


def resolved_owner_mentions_in_claim_text(
    claim_text: str,
    *,
    current_owner: str,
    resolver: AliasResolver | None = None,
) -> list[dict[str, Any]]:
    return [
        mention
        for mention in alias_mentions_in_text(
            claim_text,
            requested_owner_name=current_owner,
            resolver=resolver,
        )
        if text(mention.get("resolution_status")) == "resolved"
    ]


def owner_aliases_from_mentions(mentions: Sequence[Mapping[str, Any]], owner_name: str) -> list[str]:
    return unique_texts(
        [
            mention.get("alias")
            for mention in mentions
            if text(mention.get("resolved_owner_name")) == text(owner_name)
            and text(mention.get("alias"))
        ]
    )


def source_owner_anchor_mentions(mentions: Sequence[Mapping[str, Any]], *, max_start: int = 220) -> list[dict[str, Any]]:
    return [
        dict(mention)
        for mention in mentions
        if text(mention.get("resolution_rule"))
        in {"same_dynasty_bare_title_scope", "source_title_dynasty_bare_title"}
        and int(mention.get("start") or 0) <= max_start
    ]


def requested_owner_context_only(claim_text: str, requested_aliases: Sequence[str]) -> bool:
    for alias in requested_aliases:
        for relation in CONTEXT_ONLY_OWNER_RELATION_TERMS:
            if f"受{alias}{relation}" in claim_text or f"为{alias}{relation}" in claim_text or f"为{alias}所{relation}" in claim_text:
                return True
    return False


def rebind_payload_from_mentions(
    *,
    claim: Mapping[str, Any],
    mentions: Sequence[Mapping[str, Any]],
    from_owner: str,
    to_owner: str,
    matched_aliases: Sequence[str],
    reason: str,
) -> dict[str, Any]:
    evidence = [
        {
            "source_slice_ref": text(mention.get("source_slice_ref")),
            "alias": text(mention.get("alias")),
            "from_emperor_name": from_owner,
            "to_emperor_name": to_owner,
            "resolution_rule": text(mention.get("resolution_rule")),
            "confidence": text(mention.get("confidence")) or "deterministic",
        }
        for mention in mentions
        if text(mention.get("resolved_owner_name")) == to_owner
        and text(mention.get("alias")) in set(matched_aliases)
    ]
    return {
        "from_emperor_name": from_owner,
        "to_emperor_name": to_owner,
        "reason": reason,
        "matched_aliases": unique_texts(matched_aliases),
        "source_slice_refs": unique_texts([row["source_slice_ref"] for row in evidence]),
        "resolution_rules": unique_texts([row["resolution_rule"] for row in evidence]),
        "evidence": evidence,
    }


def claim_owner_rebind_from_alias_mentions(
    claim: Mapping[str, Any],
    *,
    source_refs: Sequence[str],
    alias_mentions_by_ref: Mapping[str, Sequence[Mapping[str, Any]]],
    resolver: AliasResolver | None = None,
) -> dict[str, Any]:
    current_owner = text(claim.get("emperor_name"))
    actor = claim_actor_text(claim)
    action_type = claim_action_type(claim)
    if action_type not in RULER_ACTION_TYPES:
        return {}
    mentions = owner_mentions_from_refs(
        source_refs=source_refs,
        alias_mentions_by_ref=alias_mentions_by_ref,
        current_owner=current_owner,
    )
    if not mentions:
        return {}
    other_mentions = [mention for mention in mentions if text(mention.get("resolved_owner_name")) != current_owner]
    source_anchor_mentions = source_owner_anchor_mentions(other_mentions)
    source_anchor_owner_names = unique_texts([mention.get("resolved_owner_name") for mention in source_anchor_mentions])
    claim_text = claim_search_text(claim)
    claim_mentions = resolved_owner_mentions_in_claim_text(claim_text, current_owner=current_owner, resolver=resolver)
    claim_current_aliases = owner_aliases_from_mentions(claim_mentions, current_owner)
    source_current_aliases = owner_aliases_from_mentions(mentions, current_owner)
    if len(source_anchor_owner_names) == 1:
        source_anchor_owner = source_anchor_owner_names[0]
        claim_anchor_owner_aliases = owner_aliases_from_mentions(claim_mentions, source_anchor_owner)
        source_anchor_aliases = owner_aliases_from_mentions(source_anchor_mentions, source_anchor_owner)
        if source_anchor_aliases and claim_current_aliases and not source_current_aliases and not claim_anchor_owner_aliases:
            payload = rebind_payload_from_mentions(
                claim=claim,
                mentions=source_anchor_mentions,
                from_owner=current_owner,
                to_owner=source_anchor_owner,
                matched_aliases=source_anchor_aliases,
                reason="source_unique_owner_anchor_rejects_unsupported_requested_owner_alias",
            )
            payload["reject_claim"] = True
            payload["unsupported_requested_owner_aliases"] = claim_current_aliases
            return payload
        if source_anchor_aliases and not claim_current_aliases and not claim_anchor_owner_aliases:
            return rebind_payload_from_mentions(
                claim=claim,
                mentions=source_anchor_mentions,
                from_owner=current_owner,
                to_owner=source_anchor_owner,
                matched_aliases=source_anchor_aliases,
                reason="source_unique_owner_anchor_without_requested_owner_in_claim",
            )

    other_owner_names = unique_texts([mention.get("resolved_owner_name") for mention in other_mentions])
    if len(other_owner_names) != 1:
        return {}
    to_owner = other_owner_names[0]
    claim_other_aliases = owner_aliases_from_mentions(claim_mentions, to_owner)

    actor_aliases = owner_aliases_in_claim_text(actor, other_mentions, to_owner)
    if actor_aliases:
        return rebind_payload_from_mentions(
            claim=claim,
            mentions=other_mentions,
            from_owner=current_owner,
            to_owner=to_owner,
            matched_aliases=actor_aliases,
            reason="claim_actor_matches_resolved_owner_alias",
        )

    payload = claim.get("fact_payload") if isinstance(claim.get("fact_payload"), Mapping) else {}
    fact_object_aliases = owner_aliases_in_claim_text(text(payload.get("object")), other_mentions, to_owner)
    if fact_object_aliases:
        return rebind_payload_from_mentions(
            claim=claim,
            mentions=other_mentions,
            from_owner=current_owner,
            to_owner=to_owner,
            matched_aliases=fact_object_aliases,
            reason="claim_fact_object_matches_resolved_owner_alias",
        )

    other_aliases_in_claim = owner_aliases_in_claim_text(claim_text, other_mentions, to_owner)
    if not other_aliases_in_claim:
        return {}
    current_aliases_in_claim = owner_aliases_in_claim_text(claim_text, mentions, current_owner)
    current_context_only = bool(current_aliases_in_claim) and requested_owner_context_only(claim_text, current_aliases_in_claim)
    if current_aliases_in_claim and not current_context_only:
        return {}
    return rebind_payload_from_mentions(
        claim=claim,
        mentions=other_mentions,
        from_owner=current_owner,
        to_owner=to_owner,
        matched_aliases=other_aliases_in_claim,
        reason=(
            "claim_context_unique_resolved_owner_with_requested_owner_context_only"
            if current_context_only
            else "claim_context_unique_resolved_owner_without_requested_owner"
        ),
    )


def apply_claim_owner_rebind(claim: Mapping[str, Any], rebind: Mapping[str, Any]) -> dict[str, Any]:
    to_owner = text(rebind.get("to_emperor_name"))
    if not to_owner:
        return dict(claim)
    result = dict(claim)
    result["emperor_name"] = to_owner
    payload = result.get("fact_payload") if isinstance(result.get("fact_payload"), Mapping) else {}
    result["fact_payload"] = dict(payload)
    result["owner_rebind_payload"] = dict(rebind)
    return result
