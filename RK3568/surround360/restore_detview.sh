#!/bin/bash
set -euo pipefail
export DISPLAY=${DISPLAY:-:0}
export XAUTHORITY=${XAUTHORITY:-/var/run/lightdm/root/:0}
export QT_QPA_PLATFORM=${QT_QPA_PLATFORM:-xcb}
export QT_XCB_GL_INTEGRATION=${QT_XCB_GL_INTEGRATION:-xcb_egl}
if fuser /dev/pango_pci_driver >/dev/null 2>&1; then
    echo '采集设备仍被占用，请先正常退出环视工具。' >&2
    exit 1
fi
previous=/userdata/surround360/evidence/previous_cmdline.bin
if [[ -f "$previous" ]]; then
    mapfile -d '' -t args < "$previous"
    [[ ${#args[@]} -gt 0 ]] || exit 1
    # Original relative executable names are normalized for reliable restart.
    args[0]=/userdata/detview-hdmifull/detview-hdmifull
else
    args=(/userdata/detview-hdmifull/detview-hdmifull --model MVP_accuracy_round1 --fullscreen)
fi
exec "${args[@]}"
