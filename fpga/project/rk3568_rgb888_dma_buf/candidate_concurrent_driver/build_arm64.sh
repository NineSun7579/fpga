#!/bin/sh
# Local Linux/WSL cross-build only; does not contact or install to a board.
set -eu
: "${KDIR:?Set KDIR to the prepared RK3568 kernel build tree}"
export ARCH=arm64
export CROSS_COMPILE="${CROSS_COMPILE:-aarch64-linux-gnu-}"
command -v "${CROSS_COMPILE}gcc" >/dev/null
test -f "$KDIR/Makefile"
test -f "$KDIR/include/generated/autoconf.h"
test -f "$KDIR/Module.symvers"
driver_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec make -C "$KDIR" M="$driver_dir" ARCH="$ARCH" CROSS_COMPILE="$CROSS_COMPILE" modules
