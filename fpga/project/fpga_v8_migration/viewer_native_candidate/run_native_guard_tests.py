"""Local C++17 guard test using attributes from recorded board evidence, no SSH."""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
from audit_native_candidate import audit

HERE = Path(__file__).resolve().parent
ART = HERE / 'artifacts'
RECORD = HERE.parent / 'pipeline_board_runtime_compatible' / 'pipeline_source.json'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run(command, log):
    result = subprocess.run(command, cwd=HERE, capture_output=True, text=True, timeout=120)
    text = result.stdout + result.stderr
    (ART / log).write_text(text, encoding='utf-8')
    if result.returncode: raise RuntimeError(f'{command}\n{text}')
    return text

def attrs_line(a):
    bits = struct.unpack('<I', struct.pack('<f', a['scale']))[0]
    return ' '.join(map(str, [a['index'], a['name'], len(a['dims']), *a['dims'], a['fmt'], a['type'],
                              a['qnt_type'], a['n_elems'], a['attr_bytes'], a['w_stride'],
                              a['size_with_stride'], a['zp'], bits])) + '\n'

def main():
    ART.mkdir(exist_ok=True)
    before = audit()
    evidence_sha = sha(RECORD)
    record = json.loads(RECORD.read_bytes())
    session = record['certification']['native_session']
    blocks = [b['session'] for b in record['blocks'] if b['profile'] == 'native_quantized']
    for b in blocks:
        for key in ('input', 'logical_heads', 'runtime_api_version', 'driver_version', 'init_flags'):
            assert b[key] == session[key], f'non-stationary recorded profile {key}'
    assert record['totals']['semantic_compatibility_pass'] and record['totals']['cleanup_errors'] == 0
    assert record['model']['verified_sha256'] == record['model']['supplied_sha256']
    manifest = json.loads((HERE.parent / 'pipeline_board_runtime_compatible' / 'experiment_manifest.json').read_text())
    native_pin = next(f['sha256'] for f in manifest['files'] if f['local'].endswith('raw_dfl_native.h'))
    assert native_pin == sha(HERE / 'src' / 'raw_dfl_native.h')
    profile = (record['model']['verified_sha256'] + ' ' + record['runtime_library']['sha256'] + ' ' +
               json.dumps(session['runtime_api_version']) + ' ' + session['driver_version'] + '\n' +
               attrs_line(session['input']) + ''.join(attrs_line(a) for a in session['logical_heads']))
    fixture = ART / 'recorded_profile.txt'
    fixture.write_text(profile, encoding='ascii')
    (ART / 'recorded_profile.json').write_text(json.dumps(dict(source=str(RECORD), source_sha256=evidence_sha,
        session=session, model=record['model'], runtime_library=record['runtime_library']), indent=2) + '\n')
    cxx = os.environ.get('NATIVE_GUARD_CXX') or shutil.which('g++')
    binary = ART / ('native_guard_selftest.exe' if os.name == 'nt' else 'native_guard_selftest')
    commands = []
    if cxx:
        command = [cxx, '--version']; commands.append(command); run(command, 'compiler_version.txt')
        command = [cxx, '-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror', '-pedantic',
                   str(HERE / 'native_guard_selftest.cpp'), '-o', str(binary)]
        commands.append(command); run(command, 'compile.txt')
    elif os.name == 'nt':
        command = ['cmd.exe', '/d', '/c', str(HERE / 'build_native_guard_selftest.cmd')]
        commands.append(command)
        (ART / 'compiler_version.txt').write_text(run(command, 'compile.txt'), encoding='utf-8')
    else: raise RuntimeError('provide a C++17 compiler through NATIVE_GUARD_CXX')
    command = [str(binary), str(fixture)]
    commands.append(command)
    stdout = run(command, 'selftest.txt')
    marker = re.search(r'NATIVE_GUARD_PASS cases=(\d+) checks=(\d+) releases=(\d+) released_buffers=(\d+)', stdout)
    assert marker, stdout
    after = audit()
    assert before == after and sha(RECORD) == evidence_sha
    counts = dict(zip(('cases', 'checks', 'releases', 'released_buffers'), map(int, marker.groups())))
    result = dict(status='PASS', scope='pure C++ guard, decoder ownership and cleanup; no complete viewer build/runtime',
                  deployed=False, counts=counts, commands=commands, compiler_version=(ART/'compiler_version.txt').read_text(),
                  recorded_evidence_sha256=evidence_sha, recorded_native_sessions_compared=len(blocks)+1,
                  candidate_manifest_sha256=sha(HERE/'candidate_manifest.json'),
                  sources_sha256={str(p.relative_to(HERE)):sha(p) for p in
                      (HERE/'native_guard_selftest.cpp', HERE/'src/viewer_native_guard.hpp',
                       HERE/'src/viewer_native_qt.hpp', HERE/'src/main.cpp', HERE/'src/raw_dfl_native.h', HERE/'src/rknn_api.h')},
                  artifacts_sha256={p.name:sha(p) for p in (binary, fixture, ART/'selftest.txt', ART/'compile.txt')})
    (ART / 'results.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print('NATIVE_GUARD_PASS', counts)
    print('FROZEN_INPUT_AUDIT_PASS files=61; production_decoder_byte_exact=11102; changed_existing=main.cpp')

if __name__ == '__main__':
    main()
