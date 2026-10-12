#!/usr/bin/env python3
"""Local Linux tests only; no board, deployment, or X server."""
import os
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parents[1]
build = root / 'host_build'
build.mkdir(exist_ok=True)
cc = os.environ.get('CC', 'cc')
evidence = []
def compile_(args, fallback=False):
    subprocess.run([cc, '-std=c11', '-Wall', '-Wextra', '-Werror', '-O2',
                    *(['-DPROBE_NO_XCB_HEADERS'] if fallback else []), *args], cwd=root, check=True)
compile_(['-shared', '-fPIC', 'tests/stub.c', '-ldl', '-o', str(build/'libstub.so')])
compile_(['-shared', '-fPIC', '-DOMIT_OPTIONALS', 'tests/stub.c', '-ldl', '-o', str(build/'libminimal.so')])
for fallback in [False, True]:
    suffix = 'fallback' if fallback else 'official'
    compile_(['-shared', '-fPIC', '-DPROBE_TEST_CLOCK', 'xcb_request_probe.c', '-ldl', '-o', str(build/f'probe_{suffix}.so')], fallback)
    compile_(['tests/host.c', '-L'+str(build), '-lstub', '-ldl', '-pthread', '-rdynamic', '-Wl,-rpath,$ORIGIN', '-o', str(build/f'host_{suffix}')], fallback)
compile_(['-shared', '-fPIC', 'xcb_request_probe.c', '-ldl', '-o', str(build/'libxcb_request_probe.so')])

def run(exe, probe, case=None, enabled='1', extra=None):
    env = os.environ.copy()
    env.update(LD_PRELOAD=str(probe), DETVIEW_XCB_REQUEST_PROBE=enabled)
    if extra: env.update(extra)
    return subprocess.run([str(exe), *([case] if case else [])], env=env, text=True, capture_output=True)

unknown = {'collision', 'overwrite', 'thread', 'ambiguous', 'failed'}
cases = ['send32', 'send64', 'fds', 'fds64', 'wrap', 'core', 'flag4', 'flag0', 'nested', 'recheck', 'repeat', 'conn_pair', 'snapshot', 'windows', 'invalid', *sorted(unknown)]
for suffix in ['official', 'fallback']:
    for case in cases:
        r = run(build/f'host_{suffix}', build/f'probe_{suffix}.so', case)
        assert r.returncode == 0, (suffix, case, r.stdout, r.stderr)
        lines = r.stderr.splitlines()
        assert len(lines) == (2 if case in ['repeat', 'conn_pair', 'windows'] else 1), (case, lines)
        for i, line in enumerate(lines):
            fields = dict(re.findall(r'(\w+)=([^ ]+)', line))
            is_unknown = case in unknown or (case == 'repeat' and i == 1)
            assert fields['unknown'] == str(int(is_unknown)), (case, fields)
            expected_calls = '3' if case == 'windows' else '2' if case == 'invalid' else '1'
            assert fields['calls'] == expected_calls, fields
            assert fields['timed'] == ('1' if case == 'invalid' else expected_calls), fields
            assert fields['invalid_clock'] == ('1' if case == 'invalid' else '0'), fields
            assert fields['sum_ns'] == ('3000000000' if case == 'windows' else '6000000000'), fields
            assert fields['max_ns'] == ('1000000000' if case == 'windows' else '6000000000'), fields
            assert fields['slow_ge20ms'] == ('3' if case == 'windows' else '1'), fields
            assert fields['extension'] == ('unknown' if is_unknown else 'core' if case == 'core' else 'DRI3'), fields
            assert fields['opcode'] == ('unknown' if is_unknown else '9' if case == 'conn_pair' and i == 1 else '7'), fields
            assert fields['flags'] == ('unknown' if is_unknown else '4' if case == 'flag4' else '0' if case == 'flag0' else '1'), fields
            assert fields['checked'] == ('unknown' if is_unknown else '0' if case in ['flag4', 'flag0'] else '1'), fields
        evidence.append(f'PASS {suffix} {case}\n{r.stdout}{r.stderr}')
        print(f'PASS {suffix} {case}')
    for value in ['0', 'yes', '01']:
        r = run(build/f'host_{suffix}', build/f'probe_{suffix}.so', 'send64', value)
        assert r.returncode == 0 and not r.stderr, r.stderr
        evidence.append(f'PASS disabled {suffix} {value}')

# Optional originals absent: startup succeeds; an actual optional call rejects.
r = run('/bin/true', build/'libxcb_request_probe.so', extra={'LD_PRELOAD': f"{build/'libxcb_request_probe.so'}:{build/'libminimal.so'}"})
assert r.returncode == 0, r.stderr
# Use a separately linked minimal host for absence test.
compile_(['tests/optional.c', '-L'+str(build), '-lminimal', '-ldl', '-Wl,-rpath,$ORIGIN', '-o', str(build/'optional')])
r = run(build/'optional', build/'libxcb_request_probe.so')
assert r.returncode == 127 and 'cannot forward safely' in r.stderr, r.stderr
evidence.append('PASS missing optional: startup succeeds, invoked missing send64 exits 127')
for value in ['0', '1']:
    r = run('/bin/true', build/'libxcb_request_probe.so', enabled=value)
    assert r.returncode == 127, r.stderr
evidence.append('PASS missing mandatory originals exits 127 enabled/disabled')

compile_(['tests/real.c', '-lxcb', '-o', str(build/'real')])
for value in ['0', '1']:
    r = run(build/'real', build/'libxcb_request_probe.so', enabled=value)
    assert r.returncode == 0 and not r.stderr, (r.stdout, r.stderr)
    evidence.append(f'PASS real libxcb disconnected forwarding enabled={value}: {r.stdout.strip()}')
symbols = subprocess.check_output(['nm', '-D', str(build/'libxcb_request_probe.so')], text=True)
assert not any(x in symbols for x in [' U malloc', ' U calloc', ' U realloc', ' U free', ' U xcb_', '__tls_get_addr'])
evidence.append('PASS symbol audit: no allocation, XCB imports, or dynamic TLS\n'+symbols)
(build/'test_results.txt').write_text('\n'.join(evidence))
print('PASS optional/mandatory resolution, real libxcb, symbol audit; host-only evidence saved')
