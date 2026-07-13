from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping

from emperor_v4.adapters.claim_extractor import adapt_claim_extractor_snapshot
from emperor_v4.application.claim_extractor_service import ClaimExtractionBatch


class FrozenClaimExtractionProvider:
    def __init__(self, snapshot_path: Path) -> None:
        self.snapshot_path = snapshot_path

    def extract(self, request_payload: Mapping[str, Any]) -> ClaimExtractionBatch:
        snapshot = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
        migrated = deepcopy(snapshot)
        migrated["adapter_target_contract"] = "assertion-extraction-contract-v2"
        requested_refs = {
            str(row.get("passage_id") or row.get("passage_code") or "")
            for row in request_payload.get("passages") or ()
        }
        frozen_refs: set[str] = set()
        for person in migrated.get("people") or ():
            payload = person.get("payload") or {}
            frozen_refs.update(str(row.get("passage_code") or "") for row in payload.get("passages") or ())
            for claim in payload.get("claims") or ():
                bindings = []
                fact = claim.get("fact_payload") or {}
                fields = ["identity", "action"]
                if fact.get("outcome"):
                    fields.append("outcome")
                for ref in claim.get("source_passage_refs") or ():
                    bindings.append({
                        "source_passage_ref": ref,
                        "support_mode": "single_passage",
                        "assertion_semantic_key": str(claim.get("claim_code") or ""),
                        "supported_fields": fields,
                    })
                claim["passage_support_bindings"] = bindings
        if requested_refs != frozen_refs:
            raise ValueError("冻结 Claim provider passages 与请求不一致")
        return ClaimExtractionBatch(
            assertions=adapt_claim_extractor_snapshot(migrated),
            provider_code="frozen_claim_snapshot_v2_compat:v1",
            model_call_count=0,
        )
