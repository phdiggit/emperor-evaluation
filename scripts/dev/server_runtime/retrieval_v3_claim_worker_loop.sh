#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
LOG_ROOT="${RETRIEVAL_V3_CLAIM_WORKER_LOG_ROOT:-/data1/emperor-evaluation/runtime/active/retrieval_v2_claim_worker_logs}"
mkdir -p "${LOG_ROOT}"
cd "${ROOT}"

echo "retrieval_v3 claim worker started at $(date -Is)"
echo "runner=${ROOT}"
echo "codex=$(${CODEX_BIN:-codex} --version 2>&1 || true)"

while true; do
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  out="${LOG_ROOT}/claim_worker_once_${stamp}.json"
  if python3 scripts/dev/retrieval_v2_claim_extraction_worker.py once \
      --execute \
      --worker-id retrieval_v3_claim_worker_service \
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
  else
    rc=$?
    echo "claim_worker_once_failed rc=${rc} output=${out}" >&2
  fi
  sleep "${RETRIEVAL_V3_CLAIM_WORKER_SLEEP:-20}"
done
