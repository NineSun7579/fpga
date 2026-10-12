#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
candidate="$PWD"
mkdir -p localbuild/async localbuild/vision localchecksreceipt
export LD_LIBRARY_PATH="$candidate/localbuild/deps/usr/lib/x86_64-linux-gnu:$candidate/localbuild/deps/usr/lib/x86_64-linux-gnu/blas:$candidate/localbuild/deps/usr/lib/x86_64-linux-gnu/lapack:${LD_LIBRARY_PATH:-}"
export LIBRARY_PATH="$LD_LIBRARY_PATH"
unset DETVIEW_STEREO_ASYNC
(
  cd localbuild/async
  qmake ../../src/stereo_async_selftest.pro
  make -j4
) > localchecksreceipt/async_build.log 2>&1
(
  cd localbuild/vision
  qmake ../../src/vision_local_selftest.pro
  make -j4
) > localchecksreceipt/vision_build.log 2>&1
localbuild/async/stereo_async_selftest > localchecksreceipt/async_selftest.stdout 2> localchecksreceipt/async_selftest.stderr
localbuild/vision/vision_local_selftest > localchecksreceipt/vision_sync.stdout 2> localchecksreceipt/vision_sync.stderr
DETVIEW_STEREO_ASYNC=1 localbuild/vision/vision_local_selftest > localchecksreceipt/vision_async.stdout 2> localchecksreceipt/vision_async.stderr
localbuild/async/stereo_async_selftest --metrics > localchecksreceipt/metrics.stdout 2> localchecksreceipt/metrics.stderr
python3 local_audit.py > localchecksreceipt/audit.stdout
printf 'LOCAL_CHECKS_PASS\n'
