#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p localbuild/debs localbuild/deps
cd localbuild/debs
# Download and extract only within this candidate. No apt installation, sudo,
# system library change or dependency edits in the frozen/active source.
apt-get download libopencv-core-dev libopencv-imgproc-dev libopencv-calib3d-dev \
  libopencv-features2d-dev libopencv-flann-dev libopencv-core406t64 \
  libopencv-imgproc406t64 libopencv-calib3d406t64 libopencv-features2d406t64 \
  libopencv-flann406t64 libblas3 liblapack3 libgfortran5 libquadmath0 \
  libtbb12 libtbbmalloc2 libtbbbind-2-5
for archive in *.deb; do dpkg-deb -x "$archive" ../deps; done
