#!/bin/bash
set -u
stage_root=$(pwd -P)
case "$stage_root" in
  /userdata/linaro/fpga_v8_viewer_native_build_20261005*) ;;
  *) printf '%s\n' 'Unexpected isolated build directory' >&2; exit 98 ;;
esac
if [ -e artifacts/viewer_build ] || [ -e build_return_code.txt ]; then
  printf '%s\n' 'Refusing to reuse existing build products' >&2
  exit 97
fi
printf '%s\n' "QMAKE=/usr/lib/qt5/bin/qmake MAKE=$stage_root/make_evidence.sh NATIVE_BUILD_JOBS=2 sh build_prepared_viewer.sh" > commands.txt
date -u +%s > build_start_epoch.txt
QMAKE=/usr/lib/qt5/bin/qmake MAKE="$stage_root/make_evidence.sh" NATIVE_BUILD_JOBS=2 \
  sh build_prepared_viewer.sh > compile_link.log 2>&1
rc=$?
date -u +%s > build_end_epoch.txt
printf '%s\n' "$rc" > build_return_code.txt
printf '{"build_return_code":%s}\n' "$rc"
exit 0
