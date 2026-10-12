#!/bin/bash
set -euo pipefail
printf 'Compiler: '; g++ --version | head -n 1
printf 'Qt: '; qmake -query QT_VERSION
printf 'Existing runtime libraries:\n'
ldconfig -p | grep -E 'opencv|tbb|lapack|blas' || true
printf 'OpenCV dependencies:\n'
apt-cache depends libopencv-calib3d406t64 libopencv-core406t64 libopencv-imgproc406t64 libopencv-features2d406t64 libopencv-flann406t64 libopencv-calib3d-dev
