#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "run as root" >&2
  exit 2
fi
if [[ $# -ne 4 ]]; then
  echo "usage: $0 RELEASE_SHA UPLOAD_ROOT CODEX_SOURCE SOURCE_PLAN_OR_DIR" >&2
  exit 2
fi

release_sha=$1
upload_root=$2
codex_source=$3
source_plan_input=$4
root=/opt/emperor-evaluation-v4
etc_root=/etc/emperor-evaluation-v4
state_root=${EMPEROR_EVAL_V4_STATE_ROOT:-/data1/emperor-evaluation/runtime/services/emperor-v4}
source_plan_root=$etc_root/source-cache-plans

[[ $release_sha =~ ^[0-9a-f]{40}$ ]] || { echo "invalid release sha" >&2; exit 2; }
[[ -x $codex_source ]] || { echo "codex source is not executable" >&2; exit 2; }
[[ -f $source_plan_input || -d $source_plan_input ]] || { echo "source plan input is missing" >&2; exit 2; }

getent group emperor-v4 >/dev/null || groupadd --system emperor-v4
id emperor-v4 >/dev/null 2>&1 || useradd --system --gid emperor-v4 --home-dir "$state_root" --create-home --shell /usr/sbin/nologin emperor-v4

install -d -o root -g root -m 0755 "$root" "$root/bin"
install -d -o root -g emperor-v4 -m 0750 "$etc_root" "$source_plan_root"
install -d -o emperor-v4 -g emperor-v4 -m 0750 "$state_root" "$state_root/claim-extractor" "$state_root/claim-extractor/codex" "$state_root/neutral-material-batches" "$state_root/emperor-rebuild" "$state_root/emperor-rebuild/requests" "$state_root/emperor-rebuild/jobs" "/data1/emperor-evaluation/runtime/active/dynasty_neutral_materials"
install -o root -g root -m 0755 "$codex_source" "$root/bin/codex"

for service in source-cache claim-extractor dynasty-governance emperor-rebuild; do
  archive="$upload_root/v4-${service}-${release_sha}.tar"
  manifest="$upload_root/v4-${service}-${release_sha}.manifest.json"
  service_root="$root/$service"
  release_root="$service_root/releases/$release_sha"
  stage_root="$service_root/releases/.${release_sha}.stage"
  [[ -f $archive && -f $manifest ]] || { echo "release input missing: $service" >&2; exit 2; }
  install -d -o root -g root -m 0755 "$service_root" "$service_root/releases"
  rm -rf "$stage_root"
  install -d -o root -g root -m 0755 "$stage_root"
  tar -xf "$archive" -C "$stage_root"
  PYTHONPATH="$stage_root/src" python3 -m emperor_v4.runtime.release verify --archive "$archive" --manifest "$manifest" >/dev/null
  if [[ -e $release_root ]]; then
    diff -qr "$stage_root" "$release_root" >/dev/null || { echo "existing release differs: $service" >&2; exit 2; }
    rm -rf "$stage_root"
  else
    mv "$stage_root" "$release_root"
  fi
  chown -R root:root "$release_root"
  chmod -R a-w "$release_root"
  ln -sfn "releases/$release_sha" "$service_root/current.next"
  mv -Tf "$service_root/current.next" "$service_root/current"
  if [[ ! -x $service_root/venv/bin/python ]] || ! "$service_root/venv/bin/python" -m pip --version >/dev/null 2>&1; then
    rm -rf "$service_root/venv"
    python3 -m venv "$service_root/venv"
  fi
  "$service_root/venv/bin/python" -m pip install --disable-pip-version-check --quiet "PyYAML>=6.0" "opencc-python-reimplemented>=0.1.7" "psycopg[binary]>=3.2"
done

stage_plan_root=$(mktemp -d "$etc_root/.source-cache-plans.XXXXXX")
trap 'rm -rf "$stage_plan_root"' EXIT
if [[ -f $source_plan_input ]]; then
  install -o root -g emperor-v4 -m 0640 "$source_plan_input" "$stage_plan_root/default.yml"
else
  plan_count=0
  while IFS= read -r -d '' plan; do
    install -o root -g emperor-v4 -m 0640 "$plan" "$stage_plan_root/$(basename "$plan")"
    plan_count=$((plan_count + 1))
  done < <(find "$source_plan_input" -maxdepth 1 -type f \( -name '*.yml' -o -name '*.yaml' \) -print0 | sort -z)
  [[ $plan_count -gt 0 ]] || { echo "source plan directory contains no YAML plans" >&2; exit 2; }
fi
find "$stage_plan_root" -maxdepth 1 -type f -print0 | xargs -0 -r chmod 0640
chown -R root:emperor-v4 "$stage_plan_root"
rm -rf "$source_plan_root.next"
mv "$stage_plan_root" "$source_plan_root.next"
trap - EXIT
rm -rf "$source_plan_root"
mv "$source_plan_root.next" "$source_plan_root"

install -o root -g emperor-v4 -m 0640 "$root/source-cache/current/deploy/v4/source-cache.env.example" "$etc_root/source-cache.env.example"
install -o root -g emperor-v4 -m 0640 "$root/claim-extractor/current/deploy/v4/claim-extractor.env.example" "$etc_root/claim-extractor.env.example"
install -o root -g emperor-v4 -m 0640 "$root/dynasty-governance/current/deploy/v4/dynasty-governance.env.example" "$etc_root/dynasty-governance.env.example"
install -o root -g emperor-v4 -m 0640 "$root/emperor-rebuild/current/deploy/v4/emperor-rebuild.env.example" "$etc_root/emperor-rebuild.env.example"

echo "provisioned_without_database_credentials_or_unit_enablement"
