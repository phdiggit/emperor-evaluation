from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v2_contracts import alias_script_variants  # noqa: E402
from scripts.dev.retrieval_v2_intake_manifest import repo_relative, text  # noqa: E402
from scripts.dev.retrieval_v2_intake_rows import stable_json  # noqa: E402
from scripts.dev.retrieval_v2_review_worklists import read_jsonl  # noqa: E402


class IdempotencyReportError(RuntimeError):
    pass


def stable_hash(value: Any, *, length: int = 16) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()[:length].upper()


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def row_file(normalized_root: Path, name: str) -> Path:
    return normalized_root / f"{name}.jsonl"


def load_rows(normalized_root: Path) -> dict[str, list[dict[str, Any]]]:
    names = [
        "source_packs",
        "source_pack_artifacts",
        "source_documents",
        "source_passages",
        "material_claims",
        "primary_claim_rule_bindings",
        "claim_rule_binding_candidates",
        "secondary_binding_candidates",
        "coverage_gap_events",
    ]
    return {name: read_jsonl(row_file(normalized_root, name)) for name in names}


def duplicate_values(rows: Sequence[Mapping[str, Any]], key_fn: Callable[[Mapping[str, Any]], str]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    samples: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        key = key_fn(row)
        if not key:
            continue
        counts[key] += 1
        samples.setdefault(key, row)
    return [
        {"key": key, "count": count, "sample": dict(samples[key])}
        for key, count in sorted(counts.items())
        if count > 1
    ]


def exact_duplicate_count(rows: Sequence[Mapping[str, Any]]) -> int:
    counts = Counter(stable_json(row) for row in rows)
    return sum(count - 1 for count in counts.values() if count > 1)


def key_join(*values: Any) -> str:
    return "|".join(text(value) for value in values)


def natural_key_functions() -> dict[str, dict[str, Callable[[Mapping[str, Any]], str]]]:
    return {
        "source_packs": {
            "source_pack_code": lambda row: text(row.get("source_pack_code")),
        },
        "source_pack_artifacts": {
            "pack_kind_path": lambda row: key_join(row.get("source_pack_code"), row.get("kind"), row.get("path")),
        },
        "source_documents": {
            "document_code": lambda row: text(row.get("document_code")),
            "pack_raw_document_code": lambda row: key_join(row.get("source_pack_code"), row.get("raw_document_code")),
        },
        "source_passages": {
            "passage_code": lambda row: text(row.get("passage_code")),
            "pack_raw_passage_code": lambda row: key_join(row.get("source_pack_code"), row.get("raw_passage_code")),
            "document_locator_quote_hash": lambda row: key_join(
                row.get("document_code"),
                row.get("locator"),
                row.get("quote_hash"),
            ),
        },
        "material_claims": {
            "claim_code": lambda row: text(row.get("claim_code")),
            "pack_raw_claim_code": lambda row: key_join(row.get("source_pack_code"), row.get("raw_claim_code")),
            "semantic_candidate": lambda row: key_join(
                row.get("emperor_name"),
                object_group_key(text(row.get("object_name"))),
                text(row.get("direction")),
                stable_hash(text(row.get("claim_summary")), length=12),
            ),
        },
        "primary_claim_rule_bindings": {
            "binding_code": lambda row: text(row.get("binding_code")),
            "claim_rule_predicate_direction_role": lambda row: key_join(
                row.get("claim_code"),
                row.get("rule_code"),
                row.get("predicate"),
                row.get("direction"),
                row.get("object_role"),
            ),
        },
        "claim_rule_binding_candidates": {
            "candidate_code": lambda row: text(row.get("candidate_code")),
            "claim_source_candidate_reason": lambda row: key_join(
                row.get("claim_code"),
                row.get("source_rule_code"),
                row.get("candidate_item_code"),
                row.get("candidate_rule_code"),
                stable_hash(text(row.get("reason")), length=12),
            ),
        },
        "coverage_gap_events": {
            "idem_key": lambda row: text(row.get("idem_key")),
        },
    }


def name_variants(name: str) -> set[str]:
    variants = {text(name)}
    variants.update(text(value) for value in alias_script_variants(name) if text(value))
    return {value for value in variants if value}


def object_group_key(name: str) -> str:
    variants = sorted(name_variants(name))
    return variants[0] if variants else text(name)


def alias_duplicate_groups(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for row in rows:
        emperor_name = text(row.get("emperor_name"))
        item_code = text(row.get("item_code") or "I5B")
        object_name = text(row.get("object_name"))
        if object_name:
            grouped[(emperor_name, item_code, object_group_key(object_name))].add(object_name)
    out: list[dict[str, Any]] = []
    for (emperor_name, item_code, group_key), names in sorted(grouped.items()):
        if len(names) > 1:
            out.append(
                {
                    "emperor_name": emperor_name,
                    "item_code": item_code,
                    "object_group_key": group_key,
                    "observed_names": sorted(names),
                    "script_variant_candidates": sorted({variant for name in names for variant in name_variants(name)}),
                }
            )
    return out


def build_report(*, normalized_root: Path, review_root: Path | None = None) -> dict[str, Any]:
    rows_by_name = load_rows(normalized_root)
    key_fns = natural_key_functions()
    table_reports: dict[str, Any] = {}
    blocks: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for name, rows in rows_by_name.items():
        exact_dups = exact_duplicate_count(rows)
        table_report = {
            "row_count": len(rows),
            "exact_duplicate_rows": exact_dups,
            "duplicate_natural_keys": {},
        }
        if exact_dups:
            blocks.append({"table": name, "code": "exact_duplicate_rows", "count": exact_dups})
        for key_name, key_fn in key_fns.get(name, {}).items():
            dups = duplicate_values(rows, key_fn)
            table_report["duplicate_natural_keys"][key_name] = {"count": len(dups), "duplicates": dups[:20]}
            if dups:
                severity = "warning" if key_name in {"semantic_candidate", "document_locator_quote_hash"} else "block"
                issue = {"table": name, "code": f"duplicate_{key_name}", "count": len(dups)}
                (warnings if severity == "warning" else blocks).append(issue)
        table_reports[name] = table_report

    alias_groups = alias_duplicate_groups(rows_by_name.get("material_claims", []))
    if alias_groups:
        warnings.append({"table": "material_claims", "code": "alias_variant_groups", "count": len(alias_groups)})

    review_summary: dict[str, Any] = {}
    if review_root is not None:
        summary_path = review_root / "worklist_summary.json"
        if summary_path.exists():
            review_summary = json.loads(summary_path.read_text(encoding="utf-8"))

    return {
        "generated_by": "scripts/dev/retrieval_v2_idempotency_report.py",
        "normalized_root": repo_relative(normalized_root),
        "review_root": repo_relative(review_root) if review_root else "",
        "ok": not blocks,
        "tables": table_reports,
        "alias_variant_groups": alias_groups[:50],
        "review_summary": review_summary,
        "blocks": blocks,
        "warnings": warnings,
        "totals": {
            "tables_checked": len(table_reports),
            "blocks": len(blocks),
            "warnings": len(warnings),
            "alias_variant_groups": len(alias_groups),
        },
    }


SCHEMA_DRAFT = """# retrieval_v2 消费层 schema 草案

本文是离线草案，不执行迁移。目标是把 clean 包消费为可幂等重放、可跨规则复用、可人工复核的 retrieval_v2 长期层。

## 设计原则

1. 旧对象池只作为历史参考，不做 FK，不复用旧 ID，不同步写入。
2. claim 是跨规则材料事实，不属于 I5B；rule binding 是后续规则解释。
3. 每张消费表必须有自然幂等键和唯一约束；重复导入只能 update，不得 insert 第二份。
4. 对象身份层独立于 claim 和 rule binding，繁简、异名、同名冲突必须先进入 review，不自动造重复对象。
5. secondary binding 必须进入长期候选池，未来新 item / rule contract 上线后从候选池解析为正式 binding。
6. 正式迁移建表时，所有表和字段必须写数据库注释；没有注释的 DDL 不进入合并。
7. 带说明性质的字段使用中文内容，不用英文 `note` 式占位；字段名可以保持英文，字段值面向人工阅读时必须中文优先。
8. 说明字段只保存信息熵高的具体判断、来源、原因或处置意见；模板句、套话和大段低信息文本宁可留空。
9. 取值有限的字段优先使用 PostgreSQL enum type；不要用裸 `text` 承载状态机、方向、名称类型和队列状态。

## DDL 注释与说明字段

- 表注释必须说明该表消费哪类 clean 产物、是否可重放、主要人工复核边界。
- 字段注释必须说明字段语义、来源和是否参与幂等键；外键字段还要写清楚引用层级。
- 说明类字段建议命名为 `description`、`diagnosis`、`review_note`、`curator_note`、`resolution_note` 等具体用途，不新增泛化 `note` 字段。
- 说明类字段入库前做空值优先策略：如果只有模板文本、重复字段名解释或“用于记录相关说明”这类低信息文本，就写空字符串 / NULL。
- 自动生成说明时要保留可验证事实，例如具体对象、史源定位、冲突原因、复核结论；不要写“本条记录用于补充说明该对象相关情况”这类无法消费的文字。

## 枚举类型

- `rv2_claim_direction`：`positive`, `negative`, `neutral`, `mixed`。
- `rv2_review_status`：`pending`, `accepted`, `rejected`, `needs_review`, `resolved`, `retired`。
- `rv2_object_identity_status`：`draft`, `active`, `needs_review`, `merged`, `rejected`, `retired`。
- `rv2_queue_status`：`ready`, `running`, `resolved`, `needs_review`, `blocked`, `cancelled`。
- `rv2_object_type`：`person`, `institution`, `place`, `event`, `text`, `other`。
- `rv2_object_name_kind`：`canonical`, `alias`, `script_variant`, `courtesy_name`, `posthumous_name`, `temple_name`, `reign_title`, `other`。
- `rv2_target_object_scope`：`item`, `rule`, `source_pack`, `manual`。
- `rv2_claim_passage_relation_kind`：`supporting_quote`, `context_quote`, `source_pointer`。

## 建议表

### source_packs
- 用途：accepted clean run 的包身份。
- 唯一键：`source_pack_code`。
- 备用自然键：`target_code, rule_code, accepted_run_fingerprint`。
- 冲突策略：更新 manifest、artifact hash、coverage 状态，不新增重复包。

### source_documents
- 用途：包内史源文档。
- 唯一键：`source_pack_code, raw_document_code`。
- 跨包去重候选：`canon_url_hash` 或 `source_title, title, locator`。
- 冲突策略：同包 raw code 更新元数据；跨包相同 URL 只作为共用文档候选，不自动合并。

### source_passages
- 用途：可定位原文片段。
- 唯一键：`source_pack_code, raw_passage_code`。
- 文本重复候选：`document_id, locator, quote_hash`。
- 冲突策略：同包 raw code 更新 passage payload；文本重复进入 warning。

### material_claims
- 用途：跨规则材料事实。
- 唯一键：`source_pack_code, raw_claim_code`。
- 语义重复候选：`target_code, normalized_object_name, direction, claim_summary_hash`。
- 冲突策略：同包 raw claim 更新；语义重复进入人工合并候选，不自动删除。

### claim_rule_bindings
- 用途：已确认 rule 解释。
- 唯一键：`claim_id, rule_contract_id, predicate, direction, object_role`。
- 冲突策略：更新 confidence、usable flags、review_status，不插重复 binding。

### claim_rule_binding_candidates
- 用途：跨规则长期候选池。
- 唯一键：`claim_id, source_rule_code, candidate_item_code, candidate_rule_code, reason_hash`，或稳定 `candidate_code`。
- 字段：`source_item_code, source_rule_code, candidate_item_code, candidate_rule_code, candidate_predicate, candidate_object_role, reason, confidence, review_status, resolved_binding_id`。
- 冲突策略：更新 confidence / reason / review_status；解析成功后写 `resolved_binding_id`。

### objects
- 用途：canonical object 身份。
- 唯一键：稳定 `object_identity_key`。
- 注意：不得仅按展示名插入；对象由 identity review 产生。

### object_names
- 用途：对象名、别名、繁简异名。
- 唯一键：`object_id, normalized_name, name_kind`。
- 冲突检测：同一 target scope 下同一个 `normalized_name` 指向多个 object 时进入 conflict review。

### target_objects
- 用途：某皇帝 / item scope 下对象出现。
- 唯一键：`target_id, object_id, scope_code`。
- 冲突策略：更新 review_status 和来源，不重复挂载。

### material_object_links
- 用途：claim 与 object 的角色关系。
- 唯一键：`claim_id, object_id, role`。
- 冲突策略：更新 confidence 和 review_status。

### material_review_queue
- 用途：材料复核工作队列。
- 唯一键：`claim_id, binding_id, review_kind`。
- 冲突策略：保持 running / resolved 状态，不重置为 ready。

### coverage_gap_events
- 用途：补抓 / 补判 / 消费侧缺口。
- 唯一键：`idem_key`。
- 冲突策略：重复 emit 不得把 `queued`, `running`, `retry_wait`, `resolved`, `blocked`, `cancelled` 打回 `ready`。

## 入库顺序

1. `source_packs`
2. `source_documents`
3. `source_passages`
4. `material_claims`
5. `claim_rule_bindings`
6. `claim_rule_binding_candidates`
7. `coverage_gap_events`
8. `object_resolution_worklist` 审过后再写对象身份层
9. `material_review_worklist` 审过后再写 material object links / scoring candidates
"""


def markdown_report(payload: Mapping[str, Any]) -> str:
    lines = [
        "# retrieval_v2 idempotency report",
        "",
        f"- ok: `{str(payload.get('ok')).lower()}`",
        f"- normalized_root: `{payload.get('normalized_root')}`",
        f"- blocks: `{len(payload.get('blocks') or [])}`",
        f"- warnings: `{len(payload.get('warnings') or [])}`",
        "",
        "| table | rows | exact duplicates | duplicate natural keys |",
        "| --- | ---: | ---: | ---: |",
    ]
    for name, table in sorted((payload.get("tables") or {}).items()):
        duplicate_key_count = sum(int(value.get("count") or 0) for value in (table.get("duplicate_natural_keys") or {}).values())
        lines.append(
            f"| {name} | {table.get('row_count')} | {table.get('exact_duplicate_rows')} | {duplicate_key_count} |"
        )
    if payload.get("blocks"):
        lines.extend(["", "## Blocks", ""])
        for issue in payload.get("blocks") or []:
            lines.append(f"- `{issue.get('table')}` `{issue.get('code')}` count={issue.get('count')}")
    if payload.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        for issue in payload.get("warnings") or []:
            lines.append(f"- `{issue.get('table')}` `{issue.get('code')}` count={issue.get('count')}")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Report idempotency risks for retrieval_v2 normalized rows.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    report = subparsers.add_parser("report", help="Build idempotency report and schema draft.")
    report.add_argument("--normalized-root", type=Path, required=True)
    report.add_argument("--review-root", type=Path)
    report.add_argument("--output-json", type=Path, required=True)
    report.add_argument("--output-md", type=Path, required=True)
    report.add_argument("--schema-draft", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "report":
        raise IdempotencyReportError(f"unsupported command: {args.command}")
    payload = build_report(normalized_root=args.normalized_root, review_root=args.review_root)
    write_json(args.output_json, payload)
    write_text(args.output_md, markdown_report(payload))
    write_text(args.schema_draft, SCHEMA_DRAFT)
    print(json.dumps({"ok": payload["ok"], "totals": payload["totals"]}, ensure_ascii=False, sort_keys=True))
    return 1 if not payload["ok"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
