from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Mapping, Sequence
from uuid import uuid4


SETTLEMENT_SCHEMA_VERSION = "dynasty-neutral-material-settlement-v1"
_FACT_FIELDS = (
    "title",
    "domain",
    "period",
    "action",
    "implementation",
    "observable_result",
    "cost_or_burden",
    "operation_status",
    "temporal_scope",
    "geographic_scope",
)


def _atomic_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def _accepted_chains(audit: Mapping[str, object], label: str) -> dict[str, dict]:
    if audit.get("status") != "accepted_shadow" or audit.get("failures"):
        raise ValueError(f"{label} audit 未达到 accepted_shadow")
    rows = [dict(row) for row in audit.get("chains") or () if isinstance(row, Mapping)]
    keys = [str(row.get("chain_key") or "") for row in rows]
    if not rows or any(not key for key in keys) or len(keys) != len(set(keys)):
        raise ValueError(f"{label} chain_key 缺失或重复")
    return dict(zip(keys, rows, strict=True))


def _evidence_identity(row: Mapping[str, object]) -> tuple[str, str, str]:
    return (
        str(row.get("page_title") or ""),
        str(row.get("revision_ref") or ""),
        str(row.get("exact_quote") or ""),
    )


def _actor_names(chain: Mapping[str, object]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            str(row.get("name") or "")
            for row in chain.get("actors") or ()
            if isinstance(row, Mapping) and str(row.get("name") or "")
        )
    )


def _richness(chain: Mapping[str, object]) -> tuple[int, int, int, str]:
    populated = sum(
        bool(str(chain.get(field) or "").strip())
        and "原文未载" not in str(chain.get(field) or "")
        for field in _FACT_FIELDS
    )
    return (
        populated,
        len(chain.get("evidence") or ()),
        len(chain.get("actors") or ()),
        str(chain.get("chain_key") or ""),
    )


def _requires_atomization_review(
    chain: Mapping[str, object],
    classification: str,
    baseline_keys: Sequence[str],
) -> bool:
    return (
        bool(baseline_keys)
        and classification in {"same_fact_enrichment", "same_fact_restatement"}
        and str(chain.get("operation_status") or "") == "mixed_chain"
    )


class _Components:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def add(self, value: str) -> None:
        self.parent.setdefault(value, value)

    def find(self, value: str) -> str:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            keep, merge = sorted((left_root, right_root))
            self.parent[merge] = keep

    def groups(self) -> tuple[tuple[str, ...], ...]:
        grouped: dict[str, list[str]] = {}
        for value in self.parent:
            grouped.setdefault(self.find(value), []).append(value)
        return tuple(
            sorted(tuple(sorted(values)) for values in grouped.values())
        )


def settle_neutral_materials(
    baseline_audit: Mapping[str, object],
    candidate_audit: Mapping[str, object],
    increment_audit: Mapping[str, object],
) -> dict[str, object]:
    baseline = _accepted_chains(baseline_audit, "baseline")
    candidate = _accepted_chains(candidate_audit, "candidate")
    if increment_audit.get("status") != "accepted_shadow":
        raise ValueError("increment audit 未达到 accepted_shadow")
    if increment_audit.get("baseline_count") != len(baseline):
        raise ValueError("increment baseline_count 不匹配")
    if increment_audit.get("candidate_count") != len(candidate):
        raise ValueError("increment candidate_count 不匹配")
    comparisons = increment_audit.get("comparisons") or ()
    comparison_by_candidate = {
        str(row.get("candidate_chain_key") or ""): row
        for row in comparisons
        if isinstance(row, Mapping)
    }
    if set(comparison_by_candidate) != set(candidate):
        raise ValueError("increment candidate 覆盖不完整")

    components = _Components()
    review_queue = []
    classifications = Counter()
    for candidate_key, row in comparison_by_candidate.items():
        classification = str(row.get("classification") or "")
        classifications[classification] += 1
        baseline_keys = tuple(str(key) for key in row.get("baseline_chain_keys") or ())
        if not set(baseline_keys) <= set(baseline):
            raise ValueError("increment 引用了未知 baseline chain")
        candidate_ref = f"candidate:{candidate_key}"
        if classification == "uncertain":
            review_queue.append(
                {
                    "candidate_chain_key": candidate_key,
                    "possible_baseline_chain_keys": list(baseline_keys),
                    "rationale": str(row.get("rationale") or ""),
                    "confidence": str(row.get("confidence") or ""),
                }
            )
            continue
        if _requires_atomization_review(
            candidate[candidate_key], classification, baseline_keys
        ):
            review_queue.append(
                {
                    "candidate_chain_key": candidate_key,
                    "possible_baseline_chain_keys": list(baseline_keys),
                    "rationale": str(row.get("rationale") or ""),
                    "confidence": str(row.get("confidence") or ""),
                    "review_reason": "mixed_chain_partial_overlap_requires_atomization",
                }
            )
        components.add(candidate_ref)
        for baseline_key in baseline_keys:
            baseline_ref = f"baseline:{baseline_key}"
            components.add(baseline_ref)
            components.union(candidate_ref, baseline_ref)

    materials = []
    actor_index: dict[str, list[str]] = {}
    domain_index: dict[str, list[str]] = {}
    for members in components.groups():
        variants = []
        candidate_classifications = set()
        for member in members:
            source_kind, chain_key = member.split(":", 1)
            chain = baseline[chain_key] if source_kind == "baseline" else candidate[chain_key]
            variants.append(
                {
                    "source_kind": source_kind,
                    "chain_key": chain_key,
                    "chain": chain,
                }
            )
            if source_kind == "candidate":
                candidate_classifications.add(
                    str(comparison_by_candidate[chain_key]["classification"])
                )
        preferred = max(variants, key=lambda row: _richness(row["chain"]))
        baseline_keys = sorted(
            row["chain_key"] for row in variants if row["source_kind"] == "baseline"
        )
        candidate_keys = sorted(
            row["chain_key"] for row in variants if row["source_kind"] == "candidate"
        )
        identity_seed = baseline_keys[0] if baseline_keys else f"candidate:{candidate_keys[0]}"
        material_ref = "DNMAT-" + sha256(identity_seed.encode("utf-8")).hexdigest()[:20].upper()
        evidence_by_identity = {}
        actors = []
        domains = []
        periods = []
        for variant in variants:
            chain = variant["chain"]
            for evidence in chain.get("evidence") or ():
                if isinstance(evidence, Mapping):
                    evidence_by_identity.setdefault(_evidence_identity(evidence), dict(evidence))
            actors.extend(_actor_names(chain))
            if str(chain.get("domain") or ""):
                domains.append(str(chain["domain"]))
            if str(chain.get("period") or ""):
                periods.append(str(chain["period"]))
        actor_names = sorted(set(actors))
        domain_names = sorted(set(domains))
        material = {
            "material_ref": material_ref,
            "settlement_status": (
                "new_candidate" if not baseline_keys else "same_fact_component"
            ),
            "candidate_classifications": sorted(candidate_classifications),
            "baseline_chain_keys": baseline_keys,
            "candidate_chain_keys": candidate_keys,
            "preferred_variant": {
                "source_kind": preferred["source_kind"],
                "chain_key": preferred["chain_key"],
            },
            "fact_variants": variants,
            "evidence": [
                evidence_by_identity[key] for key in sorted(evidence_by_identity)
            ],
            "actor_names": actor_names,
            "domains": domain_names,
            "periods": sorted(set(periods)),
            "episode_projection_status": "pending_atomization_review",
        }
        materials.append(material)
        for actor in actor_names:
            actor_index.setdefault(actor, []).append(material_ref)
        for domain in domain_names:
            domain_index.setdefault(domain, []).append(material_ref)
    materials.sort(key=lambda row: row["material_ref"])
    return {
        "schema_version": SETTLEMENT_SCHEMA_VERSION,
        "status": "accepted_shadow",
        "baseline_count": len(baseline),
        "candidate_count": len(candidate),
        "classification_counts": dict(sorted(classifications.items())),
        "settled_material_count": len(materials),
        "review_queue_count": len(review_queue),
        "materials": materials,
        "review_queue": sorted(
            review_queue, key=lambda row: row["candidate_chain_key"]
        ),
        "indexes": {
            "by_actor": {key: sorted(value) for key, value in sorted(actor_index.items())},
            "by_domain": {key: sorted(value) for key, value in sorted(domain_index.items())},
        },
        "historical_episode_writes": 0,
        "rule_evidence_unit_writes": 0,
        "score_writes": 0,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="朝代制度史中性材料确定性结算")
    parser.add_argument("--baseline-audit", type=Path, required=True)
    parser.add_argument("--candidate-audit", type=Path, required=True)
    parser.add_argument("--increment-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = settle_neutral_materials(
        json.loads(args.baseline_audit.read_text(encoding="utf-8")),
        json.loads(args.candidate_audit.read_text(encoding="utf-8")),
        json.loads(args.increment_audit.read_text(encoding="utf-8")),
    )
    _atomic_json(args.output, report)
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "status",
                    "settled_material_count",
                    "review_queue_count",
                    "historical_episode_writes",
                    "score_writes",
                )
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
