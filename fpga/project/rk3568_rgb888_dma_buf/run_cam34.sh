#!/bin/sh
set -eu
export DISPLAY=:0
export XAUTHORITY=/var/run/lightdm/root/:0
export QT_QPA_PLATFORM=xcb
export QT_XCB_GL_INTEGRATION=xcb_egl
export TMPDIR=/userdata/linaro/ov56401-cam34-shared-20261010/tmp
if fuser /dev/pango_pci_driver >/dev/null 2>&1; then
 echo 'Camera device is already in use. Quit the current viewer with Q first.' >&2
 exit 1
fi
exec /userdata/linaro/ov56401-rgb888-viewer_build_1791627094983637700/detview_cam34_composite --model MVP_accuracy_round1 --fullscreen --no-tracking --detect-interval-ms 50 --detect-min-ms 50 "$@"
