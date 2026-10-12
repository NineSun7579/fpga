#!/bin/bash
set -eu
stage_root=$(pwd -P)
case "$stage_root" in
  /userdata/linaro/fpga_v8_viewer_native_build_20261005*) ;;
  *) printf '%s\n' 'Unexpected isolated build directory' >&2; exit 98 ;;
esac
if [ -e attempt1 ] || [ -e artifacts/viewer_build_attempt1 ]; then
  printf '%s\n' 'Refusing to overwrite previous attempt' >&2
  exit 97
fi
mkdir attempt1
mv artifacts/viewer_build artifacts/viewer_build_attempt1
for file in compile_link.log commands.txt build_return_code.txt build_start_epoch.txt build_end_epoch.txt; do
  mv "$file" attempt1/
done
printf '%s\n' "QMAKE=$stage_root/qmake_evidence.sh MAKE=$stage_root/make_evidence.sh NATIVE_BUILD_JOBS=2 sh build_prepared_viewer.sh" > commands.txt
date -u +%s > build_start_epoch.txt
set +e
QMAKE="$stage_root/qmake_evidence.sh" MAKE="$stage_root/make_evidence.sh" NATIVE_BUILD_JOBS=2 \
  sh build_prepared_viewer.sh > compile_link.log 2>&1
rc=$?
set -e
date -u +%s > build_end_epoch.txt
printf '%s\n' "$rc" > build_return_code.txt
printf '{"build_return_code":%s}\n' "$rc"
exit 0
