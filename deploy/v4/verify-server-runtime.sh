#!/usr/bin/env bash
set -euo pipefail

release_root=/opt/emperor-evaluation-v4
state_root=/data1/emperor-evaluation/runtime/services/emperor-v4
disabled_units=(
  emperor-v4-source-cache-worker.timer
  emperor-v4-claim-extractor-worker.timer
  emperor-v4-emperor-rebuild-queue.timer
)
active_units=(emperor-v4-dynasty-governance-worker.timer)

[[ -d $state_root ]] || { echo "missing_state_root=$state_root" >&2; exit 2; }
state_owner=$(stat -c '%U:%G' "$state_root")
[[ $state_owner == emperor-v4:emperor-v4 ]] || { echo "invalid_state_owner=$state_owner" >&2; exit 2; }

for service in source-cache claim-extractor dynasty-governance emperor-rebuild; do
  current="$release_root/$service/current"
  [[ -L $current ]] || { echo "missing_current_symlink=$current" >&2; exit 2; }
  target=$(readlink "$current")
  [[ $target =~ ^releases/[0-9a-f]{40}$ ]] || { echo "invalid_release_target=$service:$target" >&2; exit 2; }
  [[ -f "$current/RELEASE.json" ]] || { echo "missing_release_json=$service" >&2; exit 2; }
  printf 'release_%s=%s\n' "$service" "${target#releases/}"
done

for unit in "${active_units[@]}"; do
  enabled=$(systemctl is-enabled "$unit")
  active=$(systemctl is-active "$unit")
  [[ $enabled == enabled && $active == active ]] || { echo "invalid_unit_state=$unit:$enabled/$active" >&2; exit 2; }
  printf 'unit_%s=%s/%s\n' "$unit" "$enabled" "$active"
done

for unit in "${disabled_units[@]}"; do
  enabled=$(systemctl is-enabled "$unit" || true)
  active=$(systemctl is-active "$unit" || true)
  [[ $enabled == disabled && $active == inactive ]] || { echo "invalid_unit_state=$unit:$enabled/$active" >&2; exit 2; }
  printf 'unit_%s=%s/%s\n' "$unit" "$enabled" "$active"
done

codex_bin="$release_root/bin/codex"
[[ -x $codex_bin ]] || { echo "missing_codex_bin=$codex_bin" >&2; exit 2; }
[[ -d $state_root/session-control ]] || { echo "missing_session_control_root=$state_root/session-control" >&2; exit 2; }
[[ -d $state_root/shared-neutral-backbones ]] || { echo "missing_shared_backbone_root=$state_root/shared-neutral-backbones" >&2; exit 2; }
printf 'codex_version=%s\n' "$($codex_bin --version)"
printf 'state_root=%s\n' "$state_root"
echo runtime_ready=true
