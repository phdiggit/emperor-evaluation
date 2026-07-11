#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
LOG_ROOT="${RETRIEVAL_V3_CLAIM_WORKER_LOG_ROOT:-/data1/emperor-evaluation/runtime/active/retrieval_v3_claim_worker_logs}"
mkdir -p "${LOG_ROOT}"
cd "${ROOT}"

echo "retrieval_v3 claim worker started at $(date -Is)"
echo "runner=${ROOT}"
echo "codex=$(${CODEX_BIN:-codex} --version 2>&1 || true)"

worker_count="${RETRIEVAL_V3_CLAIM_JOB_WORKERS:-2}"
if [[ ! "${worker_count}" =~ ^[1-4]$ ]]; then
  echo "invalid RETRIEVAL_V3_CLAIM_JOB_WORKERS=${worker_count}; expected 1..4" >&2
  exit 2
fi
echo "claim_job_workers=${worker_count}"

run_claim_worker() {
  local slot="$1"
  local stamp="$2"
  local out="${LOG_ROOT}/claim_worker_once_${stamp}_w${slot}.json"
  if python3 scripts/dev/retrieval_v3_claim_extraction_worker.py once \
      --execute \
      --worker-id "retrieval_v3_claim_worker_service_${slot}" \
      --output-json "${out}"; then
    python3 - "${out}" <<'PY' || true
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
job = payload.get("job") or {}
result = payload.get("result") or {}
print(
    "claim_worker_once",
    "status=" + str(payload.get("status")),
    "job=" + str(job.get("job_code")),
    "claim_count=" + str(result.get("claim_count")),
)
PY
    local post_out="${LOG_ROOT}/post_claim_${stamp}_w${slot}.json"
    python3 scripts/dev/retrieval_v3_post_claim_orchestrator.py \
      --claim-worker-output "${out}" \
      --output-root "${RETRIEVAL_V3_POST_CLAIM_ROOT:-/data1/emperor-evaluation/runtime/active/retrieval_v3_post_claim}" \
      --output-json "${post_out}" \
      --execute || echo "post_claim_orchestrator_failed output=${post_out}" >&2
  else
    local rc=$?
    echo "claim_worker_once_failed slot=${slot} rc=${rc} output=${out}" >&2
  fi
}

while true; do
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  pids=()
  for slot in $(seq 1 "${worker_count}"); do
    run_claim_worker "${slot}" "${stamp}" &
    pids+=("$!")
  done
  for pid in "${pids[@]}"; do
    wait "${pid}" || true
  done
  sleep "${RETRIEVAL_V3_CLAIM_WORKER_SLEEP:-20}"
done
