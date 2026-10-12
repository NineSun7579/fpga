#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p local_build
python3 local_protocol_check.py
python3 local_syntax_check.py
python3 local_native_verify_check.py
g++ -std=c++17 -O2 -pthread fair_dma_selftest.cpp -o local_build/fair_dma_selftest
./local_build/fair_dma_selftest > local_build/fair_dma.log
g++ -std=c++17 -O2 -fPIC -pthread -I. local_build/protocol.cpp -o local_build/protocol_test \
    $(pkg-config --cflags --libs Qt5Core Qt5Gui) \
    -Wl,--wrap=open,--wrap=close,--wrap=raise,--wrap=mmap,--wrap=munmap,--wrap=ioctl
./local_build/protocol_test > local_build/protocol_off.log 2>&1
DETVIEW_FPGA_INFER_RGB=1 ./local_build/protocol_test > local_build/protocol_on.log 2>&1
DETVIEW_FPGA_INFER_RGB=1 DETVIEW_FPGA_INFER_VERIFY=1 ./local_build/protocol_test > local_build/protocol_verify.log 2>&1
g++ -std=c++17 -fPIC -pthread -I. -fsyntax-only local_build/main_classes.cpp \
    $(pkg-config --cflags Qt5Core Qt5Gui Qt5Widgets Qt5OpenGL) > local_build/syntax.log 2>&1
g++ -std=c++17 -O2 -I. local_build/native_verify.cpp -o local_build/native_verify
./local_build/native_verify > local_build/native_verify.log
echo 'FAIR_LOCAL_CHECK_PASS (host fixtures; no board access)'
