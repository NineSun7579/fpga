#!/bin/bash
set -euo pipefail
[[ $(id -u) -eq 0 ]] || { echo 'Run with sudo'; exit 1; }
release=$(cd -- "$(dirname -- "$0")" && pwd)
repo=$(cd -- "$release/../../.." && pwd)
model="$repo/RK3568/models/detview/mvp_accuracy_round1"
binary="$release/bin/detview-hdmifull"
model_file=MVP_accuracy_round1_rk3568_int8.rknn
[[ $(sha256sum "$binary" | cut -d ' ' -f1) == 3d315e77913fb651b884b817480284d1ad17ad5e794866f4db5c7c50db69cf0b ]]
[[ $(sha256sum "$model/$model_file" | cut -d ' ' -f1) == 6cdfe6c8d834e2b99994633b483e048819a79c440562a2ea1ccbc55947be03e2 ]]
for proc in /proc/[0-9]*/exe; do
    executable=$(readlink "$proc" 2>/dev/null || true)
    case "$executable" in */detview|*/detview-hdmifull|*/camview) echo "Close active viewer first: $executable"; exit 1;; esac
done
backup=$(mktemp -d /userdata/model_imports/detview_temporal_backup_XXXXXXXX)
mkdir -p /userdata/detview-hdmifull /root/npu/mvp
for relative in userdata/detview-hdmifull/detview-hdmifull "root/npu/mvp/$model_file" "root/npu/mvp/$model_file.names.json" "root/npu/mvp/$model_file.deployment.json"; do
    mkdir -p "$backup/$(dirname "$relative")"
    if [[ -e "/$relative" || -L "/$relative" ]]; then
        cp -a "/$relative" "$backup/$relative"
        printf '%s\n' "$relative" >> "$backup/existing_files.txt"
    else printf '%s\n' "$relative" >> "$backup/new_files.txt"; fi
done
install -m 755 "$binary" /userdata/detview-hdmifull/detview-hdmifull.new
mv -f /userdata/detview-hdmifull/detview-hdmifull.new /userdata/detview-hdmifull/detview-hdmifull
for name in "$model_file" "$model_file.names.json" "$model_file.deployment.json"; do
    # Replace symlinks themselves, preserving their previous target in backup.
    install -m 644 "$model/$name" "/root/npu/mvp/$name.new"
    mv -f "/root/npu/mvp/$name.new" "/root/npu/mvp/$name"
done
echo "Installed verified files. Backup: $backup"
