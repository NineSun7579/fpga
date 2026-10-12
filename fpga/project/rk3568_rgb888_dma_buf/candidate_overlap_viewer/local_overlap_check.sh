#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
ulimit -c 0
bash local_fair_check.sh
python3 local_overlap_check.py
g++ -std=c++17 -O2 -pthread prefetch_selftest.cpp -o local_build/prefetch_selftest
./local_build/prefetch_selftest > local_build/prefetch.log
echo 'OVERLAP_LOCAL_CHECK_PASS (host fixtures only)'
