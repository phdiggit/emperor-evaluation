"""Build and verify the formal public projection for Second Item B2."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from emperor_v4.evaluation.governance_quality import is_direct

from emperor_v4.evaluation.formal_json_store import (
    load_json,
    load_ruler_polities,
    write_json,
)


B2_PATH = Path(
    "docs/评分结算/净收益/第二项治国净收益/制度行政/"
    "03-B2反馈纠错与权力约束方向卡.json"
)
CONTRACT_PATH = Path("docs/分项规则/第二项治国净收益/制度行政/00-规则与计分合同.md")
PUBLIC_PROJECTION_SCHEMA = "second-item-b2-authored-public-v2"
PROFILE_KEYS = ("M_positive_profile", "M_mixed_profile", "M_negative_profile")
PUBLIC_EVIDENCE_FIELDS = (
    "id",
    "public_label",
    "public_direction",
    "public_tags",
    "public_basis",
    "public_boundary",
    "source_refs",
)

PUBLIC_DIRECTIONS = {"正向", "负向", "正向主导", "负向主导", "正负并存"}
PUBLIC_FORBIDDEN_RE = re.compile(
    r"(?:"
    r"(?<![A-Za-z0-9])(?:B1|B2|C[1-4]|D[13]|M[0-3]|M|G[0-5]|R[0-4])(?![A-Za-z0-9])|"
    r"S(?:\+\+|\+|−|-)\s*\d*|"
    r"\b(?:position|lifecycle|canonical|observed_or_repeated|"
    r"repeated_or_stage|sustained_or_systemic|institution_lifecycle_adjudicated|"
    r"context_only|external_constraint|information_ingress|"
    r"sovereign_self_correction|ignored_high_stakes_feedback)\b|"
    r"[A-Za-z]+(?:_[A-Za-z0-9]+)+|"
    r"生命周期|门禁|主档|消费|净余量|计权|闭合|本轮|重审|重裁|恢复原|版本史|错绑|现撤回|已吸收|形成完整链条|反馈反馈链"
    r")",
    flags=re.IGNORECASE,
)


def _number(value: object) -> float:
    if isinstance(value, bool) or value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _profile_rows(row: dict[str, Any]):
    for profile_key in PROFILE_KEYS:
        for index, profile in enumerate(row.get(profile_key) or []):
            if isinstance(profile, dict):
                yield profile_key, index, profile


def _group_key(profile: dict[str, Any], index: int) -> str:
    for key in ("lifecycle_group_key", "absorbed_into_lifecycle_key", "lifecycle_key", "material_id"):
        value = str(profile.get(key) or "").strip()
        if value:
            return value
    material_ids = profile.get("material_ids") or []
    if isinstance(material_ids, list):
        for value in material_ids:
            if str(value).strip():
                return str(value).strip()
    return f"profile-{index}"


def _group_profiles(row: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for _, index, profile in _profile_rows(row):
        groups.setdefault(_group_key(profile, index), []).append(profile)
    return groups


def _stable_id(row: dict[str, Any], group_key: str) -> str:
    raw = f"{row.get('ruler_id', '')}|{group_key}".encode("utf-8")
    return "B2-PUBLIC-" + hashlib.sha256(raw).hexdigest()[:16].upper()


def _public_direction(profiles: list[dict[str, Any]]) -> str:
    effective = [p for p in profiles if is_direct(p)]
    profiles = effective or profiles
    authored = {p["lifecycle_direction"] for p in profiles if p.get("lifecycle_direction")}
    if len(authored) > 1:
        raise ValueError("B2同一反馈过程的总体方向不一致")
    if authored:
        value = authored.pop()
        if value not in PUBLIC_DIRECTIONS:
            raise ValueError("B2同一反馈过程的总体方向非法")
        return value
    directions = {str(profile.get("direction") or "") for profile in profiles}
    if "positive" in directions and "negative" in directions:
        return "正负并存"
    if "mixed_positive" in directions:
        return "正向主导"
    if "mixed_negative" in directions:
        return "负向主导"
    if "positive" in directions:
        return "正向"
    if "negative" in directions:
        return "负向"
    return "正负并存"


def _public_evidence_items(row: dict[str, Any]) -> list[dict[str, Any]]:
    items = row.get("public_evidence_items")
    if not isinstance(items, list) or (not items and row.get("grade_origin") != "MISSING_EVIDENCE_DEFAULT"):
        raise ValueError(f"B2缺少直接维护的逐条公开正文：{row.get('ruler_name')}")
    return copy.deepcopy(items)


def _public_summary(row: dict[str, Any]) -> str:
    text = row.get("public_adjudication_summary")
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"B2缺少直接维护的公开定档理由：{row.get('ruler_name')}")
    return text


def _source_material_ids(profiles: list[dict[str, Any]]) -> set[str]:
    return {
        str(value) for profile in profiles
        for value in [profile.get("material_id"), *(profile.get("material_ids") or []),
                      *(profile.get("merged_source_material_ids") or [])]
        if value
    }


def _verify_sources(root: Path, item: dict[str, Any], profiles: list[dict[str, Any]], cache: dict) -> None:
    refs = item.get("source_refs")
    if not isinstance(refs, list) or not refs:
        raise ValueError(f"B2公开材料缺少来源：{item.get('id')}")
    expected = _source_material_ids(profiles)
    if {ref.get("material_id") for ref in refs} != expected:
        raise ValueError(f"B2公开来源与正式材料身份不一致：{item.get('id')}")
    for ref in refs:
        relative = Path(str(ref.get("path") or ""))
        path = (root / relative).resolve()
        allowed = (root / "docs/公共成果/制度行政/01-制度行政计分材料登记").resolve()
        if relative.is_absolute() or not path.is_relative_to(allowed) or not path.is_file():
            raise ValueError(f"B2公开来源不在有效材料登记中：{relative}")
        if path not in cache:
            cache[path] = {m["material_id"]: m for m in load_json(path).get("records", [])}
        material = cache[path].get(ref["material_id"])
        if material is None:
            raise ValueError(f"B2公开来源缺少对应材料：{ref['material_id']}")
        candidates = []
        for evidence in material.get("evidence") or []:
            if not isinstance(evidence, dict):
                continue
            candidates.append({
                "path": relative.as_posix(), "material_id": material["material_id"],
                "source_title": evidence.get("source_title") or evidence.get("source_locator") or "所引史料",
                "source_locator": evidence.get("source_locator") or "",
                "source_url": evidence.get("source_url") or "",
                "exact_quote": evidence.get("exact_quote") or "",
            })
        if not candidates:
            candidates.append({"path": relative.as_posix(), "material_id": material["material_id"],
                               "source_title": "正式材料登记", "source_locator": "",
                               "source_url": "", "exact_quote": ""})
        if ref not in candidates:
            raise ValueError(f"B2公开史源不与登记逐字同值：{ref['material_id']}")


def _scoring_signature(payload: dict[str, Any]) -> str:
    snapshot = copy.deepcopy(payload.get("records") or [])
    for row in snapshot:
        for key in ("public_adjudication_summary", "public_evidence_items"):
            row.pop(key, None)
    return json.dumps(
        sorted(snapshot, key=lambda item: str(item.get("ruler_id"))),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _refresh_payload(payload: dict[str, Any]) -> dict[str, Any]:
    before_signature = _scoring_signature(payload)
    profile_count = 0
    evidence_count = 0
    merged_count = 0
    zero_weight_count = 0
    for row in payload.get("records") or []:
        profiles = list(_profile_rows(row))
        profile_count += len(profiles)
        groups = _group_profiles(row)
        items = _public_evidence_items(row)
        row["public_adjudication_summary"] = _public_summary(row)
        row["public_evidence_items"] = items
        evidence_count += len(items)
        merged_count += sum(1 for group in groups.values() if len(group) > 1)
        zero_weight_count += sum(
            1 for _, _, profile in profiles if not is_direct(profile)
        )
    if _scoring_signature(payload) != before_signature:
        raise ValueError("第二项B2公开字段迁移意外改变了正式评分字段")
    payload["public_projection_schema_version"] = PUBLIC_PROJECTION_SCHEMA
    payload["public_projection_status"] = "FORMAL_UPSTREAM_SOURCE"
    payload["public_projection_record_count"] = len(payload.get("records") or [])
    payload["public_projection_profile_count"] = profile_count
    payload["public_projection_evidence_item_count"] = evidence_count
    payload["public_projection_merged_group_count"] = merged_count
    payload["public_projection_zero_weight_profile_count"] = zero_weight_count
    payload["public_projection_source"] = {
        "formal_contract": CONTRACT_PATH.as_posix(),
        "identity": "人物ID加lifecycle_key、absorbed_into_lifecycle_key或材料ID生成稳定公开条目ID",
        "reader_policy": "公开正文直接维护于正式记录；命令只校验机制身份、方向、阶段边界及逐字史源，不从内部判词生成历史解释",
    }
    return payload


def refresh_public_projection(workspace_root: Path) -> dict[str, Any]:
    return _refresh_payload(load_json(workspace_root / B2_PATH))


def verify_public_projection(
    workspace_root: Path,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if payload is None:
        payload = load_json(workspace_root / B2_PATH)
    if payload.get("public_projection_schema_version") != PUBLIC_PROJECTION_SCHEMA:
        raise ValueError("第二项B2缺少正式公开投影schema标记")
    if payload.get("public_projection_status") != "FORMAL_UPSTREAM_SOURCE":
        raise ValueError("第二项B2公开投影不是正式上游真源")
    records = payload.get("records") or []
    if payload.get("public_projection_record_count") != len(records):
        raise ValueError("第二项B2公开投影人物计数不一致")

    expected_profile_count = 0
    expected_evidence_count = 0
    expected_merged_count = 0
    expected_zero_weight_count = 0
    all_ids: set[str] = set()
    source_cache: dict = {}
    for row in records:
        name = str(row.get("ruler_name"))
        profiles = list(_profile_rows(row))
        groups = _group_profiles(row)
        expected_profile_count += len(profiles)
        expected_evidence_count += len(groups)
        expected_merged_count += sum(1 for group in groups.values() if len(group) > 1)
        expected_zero_weight_count += sum(
            1 for _, _, profile in profiles if not is_direct(profile)
        )
        actual_items = row.get("public_evidence_items")
        if not isinstance(actual_items, list) or (not actual_items and row.get("grade_origin") != "MISSING_EVIDENCE_DEFAULT"):
            raise ValueError(f"第二项B2缺少逐人公开材料列表：{name}")
        ids = [str(item.get("id") or "") for item in actual_items if isinstance(item, dict)]
        if len(ids) != len(actual_items) or len(ids) != len(set(ids)) or any(not value for value in ids):
            raise ValueError(f"第二项B2公开材料ID不唯一或缺失：{name}")
        if all_ids & set(ids):
            raise ValueError(f"第二项B2公开材料ID跨人物重复：{name}")
        all_ids.update(ids)
        for item in actual_items:
            if set(item) != set(PUBLIC_EVIDENCE_FIELDS):
                raise ValueError(f"第二项B2公开材料字段不完整：{name} / {item.get('id')}")
            if not str(item.get("id") or "").startswith("B2-PUBLIC-"):
                raise ValueError(f"第二项B2公开材料ID不稳定：{name} / {item.get('id')}")
            if item.get("public_direction") not in PUBLIC_DIRECTIONS:
                raise ValueError(f"第二项B2公开方向非法：{name} / {item.get('id')}")
            if not isinstance(item.get("public_tags"), list) or not item["public_tags"]:
                raise ValueError(f"第二项B2公开标签缺失：{name} / {item.get('id')}")
            for tag in item["public_tags"]:
                if not isinstance(tag, str) or not tag.strip() or PUBLIC_FORBIDDEN_RE.search(tag):
                    raise ValueError(f"第二项B2公开标签含空值或内部术语：{name} / {item.get('id')}")
            for field in ("public_label", "public_basis", "public_boundary"):
                value = item.get(field)
                if not isinstance(value, str) or not value.strip() or PUBLIC_FORBIDDEN_RE.search(value):
                    raise ValueError(f"第二项B2公开字段含空值或内部术语：{name} / {item.get('id')} / {field}")
        expected_ids = [_stable_id(row, key) for key in groups]
        if ids != expected_ids:
            raise ValueError(f"第二项B2公开材料与正式机制身份或顺序不一致：{name}")
        for item, group in zip(actual_items, groups.values()):
            if item["public_direction"] != _public_direction(group):
                raise ValueError(f"第二项B2公开方向与正式方向不一致：{name}")
            effective = [p for p in group if is_direct(p)]
            if ("背景材料" in item["public_tags"]) != (not effective):
                raise ValueError(f"第二项B2整条背景标记与有效阶段不一致：{name}")
            partial = bool(effective) and len(effective) < len(group)
            if ("部分阶段不另计" in item["public_tags"]) != partial:
                raise ValueError(f"第二项B2合并阶段标记不一致：{name}")
            if effective and "这条材料仅" in item["public_boundary"]:
                raise ValueError(f"第二项B2有效机制被整条写成背景：{name}")
            if item["public_basis"].rstrip("。") == item["public_label"].rstrip("。"):
                raise ValueError(f"第二项B2正文仅重复标题：{name}")
            _verify_sources(workspace_root, item, group, source_cache)
        summary = row.get("public_adjudication_summary")
        if not isinstance(summary, str) or not summary.strip() or PUBLIC_FORBIDDEN_RE.search(summary):
            raise ValueError(f"第二项B2人物级公开总结缺失或含内部术语：{name}")
        if summary != _public_summary(row):
            raise ValueError(f"第二项B2人物级公开总结不是当前正式裁决的确定性投影：{name}")

    if payload.get("public_projection_profile_count") != expected_profile_count:
        raise ValueError("第二项B2公开投影profile计数不一致")
    if payload.get("public_projection_evidence_item_count") != expected_evidence_count:
        raise ValueError("第二项B2公开材料计数不一致")
    if payload.get("public_projection_merged_group_count") != expected_merged_count:
        raise ValueError("第二项B2公开合并组计数不一致")
    if payload.get("public_projection_zero_weight_profile_count") != expected_zero_weight_count:
        raise ValueError("第二项B2背景profile计数不一致")
    return {
        "status": "PASS",
        "record_count": len(records),
        "profile_count": expected_profile_count,
        "public_evidence_item_count": expected_evidence_count,
        "merged_group_count": expected_merged_count,
        "zero_weight_profile_count": expected_zero_weight_count,
        "schema_version": PUBLIC_PROJECTION_SCHEMA,
    }


def render_public_markdown(markdown: str, payload: dict[str, Any]) -> str:
    records = {row['ruler_name']: row for row in payload['records']}
    parts = re.split(r'(?=^### )', markdown, flags=re.MULTILINE)
    seen = set()
    for index, part in enumerate(parts):
        match = re.match(r'### ([^（\n]+)（[^\n]+\n', part)
        if not match or match[1] not in records:
            continue
        row = records[match[1]]
        seen.add(match[1])
        position = {'lower':'下位','lower-middle':'中下位','middle':'中位','middle-upper':'中上位','upper':'上位'}[row['position']]
        confidence = {'LOW':'低','MEDIUM':'中','HIGH':'高'}[row['confidence']]
        lines = [f"- 档位：{row['grade']}（{position}）", f"- 内部指数：{row['direction_index']:.1f}/80", f"- 置信度：{confidence}"]
        if row.get('grade_origin') == 'MISSING_EVIDENCE_DEFAULT':
            lines.append('- 证据状态：缺证默认；不代表已证良好表现。')
        lines += ['', row['public_adjudication_summary'], '', '- 结算依据：']
        lines += [f"  - {line.rstrip('。')}。" for line in row['settlement_basis']]
        lines += ['', '- 材料依据：']
        lines += [f"  - {line.rstrip('。')}。" for line in row['material_basis']]
        lines.append('')
        for item in row['public_evidence_items']:
            lines += [f"- **{item['public_label']}**（{item['public_direction']}；{'、'.join(item['public_tags'])}）",
                      f"  - 事实与判断：{item['public_basis']}", f"  - 适用边界：{item['public_boundary']}"]
            for ref in item['source_refs']:
                target = '../../../../公共成果/制度行政/01-制度行政计分材料登记/' + Path(ref['path']).name
                lines.append(f"  - 来源：{ref['source_title']} {ref['source_locator']}；[材料登记]({target})")
        parts[index] = f"### {row['ruler_name']}（{row['polity']}，分项第{row['rank']}名）\n\n" + '\n'.join(lines) + '\n\n'
    if seen != set(records):
        raise ValueError('B2 Markdown人物块与正式记录不一致')
    all_names = set(re.findall(r'^### ([^（\n]+)（', markdown, flags=re.MULTILINE))
    if all_names == set(records):
        lines = ['# B2反馈纠错与权力约束方向卡', '', '按实际反馈质量、表达保护、范围归责及反证恢复维护当前裁决。内部指数使用80刻度，按正式总则合成。', '', '缺证对象明确标为低置信度默认结算，不以缺少记载推定良好表现。', '', '## 逐人裁决与材料依据', '']
        parts[0] = '\n'.join(lines) + '\n'
    return ''.join(parts).rstrip() + '\n'


def run(workspace_root: Path, *, write: bool = False) -> dict[str, Any]:
    path = workspace_root / B2_PATH
    current = load_json(path)
    projected = _refresh_payload(copy.deepcopy(current))
    verify_public_projection(workspace_root, projected)
    markdown_path = path.with_suffix('.md')
    current_markdown = markdown_path.read_text(encoding='utf-8')
    projected_markdown = render_public_markdown(current_markdown, projected)
    if write:
        write_json(path, projected, ruler_polities=load_ruler_polities(workspace_root))
        markdown_path.write_text(projected_markdown, encoding='utf-8')
        report = verify_public_projection(workspace_root)
        report["status"] = "WRITTEN"
        return report
    if projected != current or projected_markdown != current_markdown:
        raise ValueError("第二项B2正式公开投影未同步；请运行second-item-b2-public --write")
    return verify_public_projection(workspace_root)
