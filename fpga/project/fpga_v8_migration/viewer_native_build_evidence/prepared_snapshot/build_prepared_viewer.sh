#!/bin/sh
# Build-only handoff. Run locally in an isolated Linux/RK3568 staging directory.
# This script performs no SSH, deployment, GUI or inference execution.
set -eu
candidate_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
native_build_dir=${NATIVE_VIEWER_BUILD_DIR:-"$candidate_root/artifacts/viewer_build"}
case "$native_build_dir" in
  "$candidate_root"/*) ;;
  *) printf '%s\n' 'NATIVE_VIEWER_BUILD_DIR must stay under the staged candidate directory' >&2; exit 1 ;;
esac
mkdir -p "$native_build_dir"
cd "$native_build_dir"
# Inherited detview.pro retains c++17/opencv4 and the original RKNN/RGA link flags.
"${QMAKE:-qmake}" "$candidate_root/src/detview.pro" "TARGET=detview-native-candidate"
"${MAKE:-make}" -j"${NATIVE_BUILD_JOBS:-2}"
sha256sum "$native_build_dir/detview-native-candidate"
