#!/bin/bash
set -euo pipefail
export DISPLAY=${DISPLAY:-:0}
export XAUTHORITY=${XAUTHORITY:-/var/run/lightdm/root/:0}
export QT_QPA_PLATFORM=${QT_QPA_PLATFORM:-xcb}
export QT_XCB_GL_INTEGRATION=${QT_XCB_GL_INTEGRATION:-xcb_egl}
# Capture ownership is checked without touching the driver's open operation.
if fuser /dev/pango_pci_driver >/dev/null 2>&1; then
    echo '请先退出当前 detview/camview，再启动环视工具。' >&2
    exit 1
fi
exec /userdata/surround360/surround360 --config /userdata/surround360/calibration.json --fullscreen "$@"
