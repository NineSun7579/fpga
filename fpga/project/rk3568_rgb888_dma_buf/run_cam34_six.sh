#!/bin/sh
set -eu
export DISPLAY=:0
export XAUTHORITY=/var/run/lightdm/root/:0
export QT_QPA_PLATFORM=xcb
export QT_XCB_GL_INTEGRATION=xcb_egl
export TMPDIR=/userdata/linaro/ov56401-cam34-six-shared-20261010/tmp
if fuser /dev/pango_pci_driver >/dev/null 2>&1; then
 echo 'Quit the current camera viewer with Q before launching another.' >&2
 exit 1
fi
exec /userdata/linaro/ov56401-cam34-six-320x240-build-1791630965350164900/detview_cam34_six --model MVP_accuracy_round1 --fullscreen --no-tracking --detect-interval-ms 50 --detect-min-ms 50 "$@"
