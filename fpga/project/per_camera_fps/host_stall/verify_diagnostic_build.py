import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import sys
import subprocess
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'project/tools'))
from board_host import ssh_connect

REMOTE = r'''
import hashlib, json, pathlib, subprocess, sys
request = json.loads(sys.argv[1])
binary = pathlib.Path(request['binary'])
root = pathlib.Path(request['remote_directory'])
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
if sha(binary) != request['binary_sha256']: raise RuntimeError('Built executable hash changed')
for name, expected in request['source_sha256'].items():
    if sha(root/'src'/name) != expected: raise RuntimeError('Frozen source mismatch: '+name)
records = []
for option in (() if request.get('skip_viewer_tests') else ('--vision-selftest','--camera-dma-selftest','--dfl-selftest')):
    result = subprocess.run(['env','QT_QPA_PLATFORM=offscreen',str(binary),option],
                            capture_output=True,text=True,timeout=45,cwd=root/'build')
    records.append({'option':option,'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
    if result.returncode: break
files = {}
for name in ('Makefile','main.o','vision_pipeline.o','moc_predefs.h'):
    path = root/'build'/name
    if path.is_file(): files[name] = {'sha256':sha(path),'size':path.stat().st_size}
sdk = pathlib.Path('/userdata/linaro/detview-todo-work/sdk/rknn_api.h')
if sdk.is_file(): files[str(sdk)] = {'sha256':sha(sdk),'size':sdk.stat().st_size}
commands = {}
for name, argv in (('qmake',['qmake','-v']),('compiler',['g++','--version']),
                   ('opencv',['pkg-config','--modversion','opencv4'])):
    result = subprocess.run(argv,capture_output=True,text=True,timeout=10)
    commands[name] = {'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr}
print(json.dumps({'tests':records,'files':files,'tools':commands,
                  'binary_sha256_after':sha(binary),'source_sha256_after':{name:sha(root/'src'/name) for name in request['source_sha256']}}))
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build-receipt', type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('diagnostic_build_validation', ROOT / 'project/motion_scheduling/board_viewer.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    build = module.validate_build(json.loads(args.build_receipt.read_text(encoding='utf-8')))
    path = args.build_receipt.with_name('diagnostic_verification.json')
    previous = json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
    if (previous and previous.get('status') == 'verified' and
            previous.get('binary_sha256_after') == build['binary_sha256'] and
            previous.get('source_sha256_after') == build['source_sha256'] and
            len(previous.get('tests', [])) == 3 and
            all(test['exit_code'] == 0 for test in previous['tests'])):
        build['skip_viewer_tests'] = True
    client = ssh_connect()
    try:
        command = 'python3 -c ' + shlex.quote(REMOTE) + ' ' + shlex.quote(json.dumps(build))
        _, stdout, stderr = client.exec_command(command, timeout=110)
        result = json.loads(stdout.read())
        if build.get('skip_viewer_tests'):
            result['tests'] = previous['tests']
            result['reused_verified_selftests'] = True
        code = stdout.channel.recv_exit_status()
        result['ssh_exit_code'] = code
        result['ssh_stderr'] = stderr.read().decode(errors='replace')
        result['build_receipt'] = str(args.build_receipt.resolve())
        result['captured_unix_s'] = time.time()
        success = (code == 0 and len(result['tests']) == 3 and
                   all(test['exit_code'] == 0 for test in result['tests']) and
                   result['binary_sha256_after'] == build['binary_sha256'] and
                   result['source_sha256_after'] == build['source_sha256'])
        result['status'] = 'verified' if success else 'verification_failed'
        path.write_text(json.dumps(result,indent=2), encoding='utf-8')
        print(json.dumps({'status':result['status'],'record':str(path),
                          'tests':[{key:test[key] for key in ('option','exit_code')} for test in result['tests']]},indent=2))
        if not success: raise RuntimeError('Diagnostic executable verification failed')
        source = ROOT / 'project/per_camera_fps/host_stall/diagnostic/stall_timing_selftest.cpp'
        test_suffix = str(time.time_ns())
        remote_test = build['remote_directory'] + '/build/stall_timing_selftest_' + test_suffix + '.cpp'
        with client.open_sftp() as transfer:
            with transfer.open(remote_test, 'wx') as stream:
                stream.write(source.read_bytes())
        test_binary = build['remote_directory'] + '/build/stall_timing_selftest_' + test_suffix
        compile_command = ('g++ -std=c++17 -O2 -pthread -I' + shlex.quote(build['remote_directory'] + '/src') +
                           ' ' + shlex.quote(remote_test) + ' -o ' + shlex.quote(test_binary))
        _, stdout, stderr = client.exec_command(compile_command, timeout=30)
        compile_output = stdout.read() + stderr.read()
        if stdout.channel.recv_exit_status():
            raise RuntimeError('Target timing test compile failed: ' + compile_output.decode(errors='replace'))
        _, stdout, stderr = client.exec_command(shlex.quote(test_binary), timeout=30)
        test_output = stdout.read() + stderr.read()
        test_exit = stdout.channel.recv_exit_status()
        _, stdout, stderr = client.exec_command('sha256sum ' + shlex.quote(test_binary), timeout=10)
        test_binary_hash = stdout.read().decode().split()[0]
        if stdout.channel.recv_exit_status(): raise RuntimeError('Timing executable hash failed')
        if test_exit or b'STALL_TIMING_SELFTEST_PASS' not in test_output:
            raise RuntimeError('Target timing test failed: ' + test_output.decode(errors='replace'))
        proof = {'binary_sha256':build['binary_sha256'],
                 'tests':[{'option':test['option'], 'exit_code':test['exit_code'],
                           'output_sha256':hashlib.sha256((test['stdout'] + test['stderr']).encode()).hexdigest()}
                          for test in result['tests'] if test['option'] != '--dfl-selftest'],
                 'timing':{'exit_code':test_exit, 'output_sha256':hashlib.sha256(test_output).hexdigest(),
                           'binary_sha256':test_binary_hash, 'source_sha256':{
                               'stall_timing.h':build['source_sha256']['stall_timing.h'],
                               'stall_timing_selftest.cpp':hashlib.sha256(source.read_bytes()).hexdigest()},
                           'machine':'aarch64', 'compile_command':compile_command,
                           'compile_output_sha256':hashlib.sha256(compile_output).hexdigest(),
                           'output':test_output.decode(errors='replace')}}
        proof_path = args.build_receipt.with_name('diagnostic_selftest_proof.json')
        proof_path.write_text(json.dumps(proof,indent=2),encoding='utf-8')
        print('Target timing and viewer self-test proof: ' + str(proof_path),flush=True)
    finally:
        client.close()


if __name__ == '__main__':
    main()
