#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p local_build
python3 local_camera_diag_check.py
g++ -std=c++17 -O2 -Wall -Wextra -Werror camera_diag_selftest.cpp -o local_build/camera_diag_selftest
./local_build/camera_diag_selftest
python3 local_protocol_check.py
g++ -std=c++17 -O2 -fPIC -pthread -I. local_build/protocol.cpp -o local_build/protocol_test \
    $(pkg-config --cflags --libs Qt5Core Qt5Gui) \
    -Wl,--wrap=open,--wrap=close,--wrap=raise,--wrap=mmap,--wrap=munmap,--wrap=ioctl
DETVIEW_DIAG_SELFTEST=1 ./local_build/protocol_test
DETVIEW_DIAG_SELFTEST=1 DETVIEW_CAMERA_DIAG=1 ./local_build/protocol_test
DETVIEW_DIAG_SELFTEST=1 DETVIEW_FPGA_INFER_RGB=1 DETVIEW_CAMERA_DIAG=1 ./local_build/protocol_test
echo 'CAMERA_DIAG_LOCAL_CHECK_PASS (host fixtures; no board access)'
