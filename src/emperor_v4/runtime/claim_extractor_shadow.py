from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from typing import Sequence

from emperor_v4.adapters.claim_extraction_profile import (
    load_claim_extraction_profile,
    render_claim_extraction_request,
)
from emperor_v4.adapters.claim_extractor import adapt_claim_extractor_snapshot


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="V4 Claim Extractor profile/frozen-response shadow")
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    person = snapshot["people"][0]
    payload = person["payload"]
    profile = load_claim_extraction_profile(args.profiles, args.profile)
    request = render_claim_extraction_request(
        profile=profile,
        subject={"ruler": person.get("ruler"), "claim_run": person.get("claim_run")},
        passages=tuple(payload.get("passages") or ()),
    )
    assertions = adapt_claim_extractor_snapshot(snapshot)
    report = {
        "schema_version": 1,
        "status": "claim_extractor_profile_frozen_shadow_complete",
        "profile_code": profile.code,
        "output_contract": profile.output_contract,
        "input_fingerprint": request["input_fingerprint"],
        "frozen_release": snapshot.get("captured_from_release"),
        "frozen_extractor_version": snapshot.get("extractor_version"),
        "claim_count": sum(len(row["payload"].get("claims") or ()) for row in snapshot["people"]),
        "assertion_count": len(assertions),
        "assertions": [asdict(item) for item in assertions],
        "runtime_audit": {"model_call_count": 0, "database_write_count": 0, "server_unit_change_count": 0},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
