#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
LOG_ROOT="${RETRIEVAL_V3_PERSON_PROFILE_LOG_ROOT:-/data1/emperor-evaluation/runtime/active/retrieval_v3_person_profile_worker_logs}"
RUN_ROOT="${RETRIEVAL_V3_PERSON_PROFILE_RUN_ROOT:-/data1/emperor-evaluation/runtime/active/retrieval_v3_person_profile_runs}"
mkdir -p "${LOG_ROOT}" "${RUN_ROOT}"
cd "${ROOT}"

while true; do
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  python3 scripts/dev/retrieval_v3_person_profile_worker.py \
    --worker-id retrieval_v3_person_profile_worker_service \
    --output-root "${RUN_ROOT}" \
    --output-json "${LOG_ROOT}/person_profile_once_${stamp}.json" || true
  sleep "${RETRIEVAL_V3_PERSON_PROFILE_WORKER_SLEEP:-30}"
done
