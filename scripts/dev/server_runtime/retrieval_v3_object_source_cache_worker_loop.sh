#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
LOG_ROOT="${RETRIEVAL_V3_OBJECT_SOURCE_WORKER_LOG_ROOT:-/data1/emperor-evaluation/runtime/active/retrieval_v3_object_source_cache_worker_logs}"
mkdir -p "${LOG_ROOT}"
cd "${ROOT}"

echo "retrieval_v3 object source cache worker started at $(date -Is)"
echo "runner=${ROOT}"

claim_bridge_args=(
  --dsn-env "${RETRIEVAL_V3_OBJECT_SOURCE_DSN_ENV:-EMPEROR_EVAL_RETRIEVAL_V3_DSN}"
  --pg-schema "${RETRIEVAL_V3_OBJECT_SOURCE_PG_SCHEMA:-retrieval_v3}"
  --claim-cache-root "${RETRIEVAL_V3_CLAIM_CACHE_ROOT:-/data1/emperor-evaluation/runtime/active/retrieval_v3_quality_pilot/claim_cache}"
  --claim-run-root "${RETRIEVAL_V3_CLAIM_RUN_ROOT:-/data1/emperor-evaluation/runtime/active/retrieval_v3_quality_pilot/claim_runs}"
  --claim-plan-output-root "${RETRIEVAL_V3_CLAIM_PLAN_OUTPUT_ROOT:-/data1/emperor-evaluation/runtime/active/retrieval_v3_quality_pilot/object_source_claim_plans}"
  --claim-max-slices-per-person "${RETRIEVAL_V3_CLAIM_PLAN_MAX_SLICES_PER_PERSON:-12}"
  --claim-max-total-slices "${RETRIEVAL_V3_CLAIM_PLAN_MAX_TOTAL_SLICES:-0}"
  --claim-selection-profile "${RETRIEVAL_V3_CLAIM_PLAN_SELECTION_PROFILE:-all}"
)

while true; do
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  out="${LOG_ROOT}/object_source_cache_worker_once_${stamp}.json"
  if python3 scripts/dev/retrieval_v3_object_source_cache_worker.py once \
      --execute \
      "${claim_bridge_args[@]}" \
      --worker-id retrieval_v3_object_source_cache_worker_service \
      --max-docs-per-person "${RETRIEVAL_V3_OBJECT_SOURCE_MAX_DOCS_PER_PERSON:-8}" \
      --auto-enqueue-claim-job \
      --output-json "${out}"; then
    python3 - "${out}" <<'PY' || true
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
job = payload.get("job") or {}
result = payload.get("result") or {}
summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
totals = summary.get("totals") if isinstance(summary.get("totals"), dict) else {}
bridge = result.get("claim_bridge_result") if isinstance(result.get("claim_bridge_result"), dict) else {}
claim_job = bridge.get("claim_job") if isinstance(bridge.get("claim_job"), dict) else {}
print(
    "object_source_cache_worker_once",
    "status=" + str(payload.get("status")),
    "job=" + str(job.get("job_code")),
    "seed_count=" + str(job.get("seed_count")),
    "completed=" + str(totals.get("completed")),
    "timed_out=" + str(totals.get("timed_out")),
    "source_documents=" + str(totals.get("source_documents")),
    "mention_slices=" + str(totals.get("mention_slices")),
    "claim_bridge_status=" + str(bridge.get("status")),
    "uncovered_claim_slices=" + str(bridge.get("uncovered_slice_count")),
    "claim_job=" + str(claim_job.get("job_code")),
)
PY
  else
    rc=$?
    echo "object_source_cache_worker_once_failed rc=${rc} output=${out}" >&2
  fi

  bridge_out="${LOG_ROOT}/object_source_cache_bridge_succeeded_${stamp}.json"
  if python3 scripts/dev/retrieval_v3_object_source_cache_worker.py bridge-succeeded \
      "${claim_bridge_args[@]}" \
      --bridge-min-created-at "${RETRIEVAL_V3_OBJECT_SOURCE_BRIDGE_MIN_CREATED_AT:-2026-07-09T13:00:00Z}" \
      --output-json "${bridge_out}"; then
    python3 - "${bridge_out}" <<'PY' || true
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
job = payload.get("job") or {}
result = payload.get("result") or {}
claim_job = result.get("claim_job") if isinstance(result.get("claim_job"), dict) else {}
print(
    "object_source_cache_bridge_succeeded",
    "status=" + str(payload.get("status")),
    "job=" + str(job.get("job_code")),
    "bridge_status=" + str(result.get("status")),
    "uncovered_claim_slices=" + str(result.get("uncovered_slice_count")),
    "claim_job=" + str(claim_job.get("job_code")),
)
PY
  else
    rc=$?
    echo "object_source_cache_bridge_succeeded_failed rc=${rc} output=${bridge_out}" >&2
  fi

  sleep "${RETRIEVAL_V3_OBJECT_SOURCE_WORKER_SLEEP:-30}"
done
