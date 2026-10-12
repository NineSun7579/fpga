#!/bin/sh
set -eu
export DISPLAY=:0
export XAUTHORITY=/var/run/lightdm/root/:0
export QT_QPA_PLATFORM=xcb
export QT_XCB_GL_INTEGRATION=xcb_egl
export TMPDIR=/userdata/linaro/ov56401-cam34-wire-trial/tmp
export DETVIEW_FPGA_INFER_RGB=0
if fuser /dev/pango_pci_driver >/dev/null 2>&1; then
 echo 'Quit the current viewer with Q before starting another camera owner.' >&2
 exit 1
fi
exec /userdata/linaro/ov56401-cam34-wire-viewer-build-1791637623370314600/detview_cam34_fpga_compressed --model MVP_accuracy_round1 --fullscreen --no-tracking --detect-interval-ms 50 --detect-min-ms 50 "$@"
