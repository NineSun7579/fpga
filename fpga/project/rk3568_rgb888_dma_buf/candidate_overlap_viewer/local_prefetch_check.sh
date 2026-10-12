#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p local_build
python3 local_prefetch_preservation.py
g++ -std=c++17 -O2 -pthread prefetch_selftest.cpp -o local_build/prefetch_selftest
./local_build/prefetch_selftest | tee local_build/prefetch.log
python3 - <<'PY'
import os, subprocess
for value, expected in [(None, 30), ('0', 0), ('30', 30), ('50', 50), ('120', 120),
                        ('-1', 0), ('121', 0), ('30 ', 0), ('9999999999999999999999999999', 0)]:
    env = dict(os.environ, DETVIEW_FPGA_INFER_RGB='1')
    env.pop('DETVIEW_FPGA_PREFETCH_LEAD_MS', None)
    if value is not None: env['DETVIEW_FPGA_PREFETCH_LEAD_MS'] = value
    p = subprocess.run(['./local_build/prefetch_selftest', '--config'], env=env,
                       capture_output=True, text=True, check=True)
    assert p.stdout.strip() == f'lead_ms={expected}'
    invalid = value in ('-1', '121', '30 ', '9999999999999999999999999999')
    assert p.stderr.count('[fpga-prefetch]') == int(invalid), p.stderr
env = dict(os.environ, DETVIEW_FPGA_INFER_RGB='0', DETVIEW_FPGA_PREFETCH_LEAD_MS='invalid',
           DETVIEW_FPGA_PREFETCH_TIMING='1')
p = subprocess.run(['./local_build/prefetch_selftest', '--config'], env=env,
                   capture_output=True, text=True, check=True)
assert p.stdout.strip() == 'RGB_OFF' and not p.stderr
print('PREFETCH_ENV_DEFAULT_FAIL_CLOSED_WARN_ONCE_OFF_PASS')
PY
bash local_fair_check.sh
