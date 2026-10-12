#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p local_build
python3 local_prefetch_preservation.py
g++ -std=c++17 -O2 -pthread prefetch_selftest.cpp -o local_build/prefetch_selftest
./local_build/prefetch_selftest | tee local_build/prefetch.log
bash local_fair_check.sh
