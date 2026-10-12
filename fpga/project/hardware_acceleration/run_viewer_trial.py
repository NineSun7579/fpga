"""Run one identity-bound six-camera legacy/native trial and restore HDMI."""
import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'project/tools'))


def diagnostic_helpers():
    spec = importlib.util.spec_from_file_location('acceleration_diagnostic', ROOT/'project/per_camera_fps/host_stall/run_diagnostic.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def native_binding(proof_path, source_hashes, viewer_proof, diag, sdk_sha256):
    report = diag.read_json(proof_path)
    parent_receipt = proof_path.resolve().parents[2] / 'receipt.json'
    experiment = diag.read_json(parent_receipt)
    if experiment.get('status') != 'success' or experiment.get('backend') != 'rknn' or experiment.get('phase') != 'experiment':
        raise ValueError('A successful RKNN experiment must bind the native report')
    pinned = experiment['source_sha256']
    for viewer_name, probe_name in [('native_adapter.h', 'native_adapter.h')]:
        if source_hashes.get(viewer_name) != pinned.get(probe_name):
            raise ValueError('Native parity proof uses a different ' + viewer_name)
    if sdk_sha256 != pinned.get('prepared/sdk/rknn_api.h'):
        raise ValueError('Native parity proof uses a different SDK header')
    summary = report.get('candidate_summaries', {}).get('native_io', {})
    if report.get('status') != 'isolated_hardware_comparison_complete' or not summary.get('parity_certified') or report.get('dequant_scale') != 'fp16':
        raise ValueError('Native I/O has not passed all FP16-scale hardware parity gates')
    certifications = report.get('certifications', [])
    if len(certifications) != 4 or not all(c.get('certified') and c.get('exact_tuples') and
            c.get('all_float_arrays_within_epsilon') and c.get('atol') == 1e-6 and
            c.get('rtol') <= 1e-6 and c.get('arrays') and
            all(a.get('bitwise_equal') and a.get('max_abs') == 0 for a in c['arrays']) for c in certifications):
        raise ValueError('Four fixtures with unchanged strict parity rules required')
    names = {'native_io_' + name + '_cert_candidate' for name in
             ('bright_baseline_cam1', 'candidate_cam1', 'live_cam1_bank0_0', 'live_cam2_bank0_0')}
    if {c.get('candidate') for c in certifications} != names:
        raise ValueError('Native certificate does not cover the four frozen fixtures')
    starts = [e for e in experiment['events'] if e['state'] == 'probe_started']
    command = starts[-1]['command']
    if command[command.index('--native-query') + 1] != '9':
        raise ValueError('Viewer requires native output query9 certification')
    target = report['target']
    if target.get('model_sha256') != '21451a51f680ececd9ee75bcbb4db3e4ccee05d210ef9ffef2f1b99da61a8b31' or target.get('library_sha256') != viewer_proof['runtime_sha256']:
        raise ValueError('Native parity model/runtime differ from viewer build')
    return dict(report_sha256=diag.sha_file(proof_path), experiment_receipt_sha256=diag.sha_file(parent_receipt),
                experiment_host=experiment['host'], target=target, source_sha256=pinned)


EXTRA = r'''
previous_trial_action = action

def selected_io_entries(lines, mode):
    entries = [line for line in lines if line.startswith('[rknn-io]')]
    selected = next((i for i, line in enumerate(entries) if
                     'sha256=21451a51f680ececd9ee75bcbb4db3e4ccee05d210ef9ffef2f1b99da61a8b31 ' in line), None)
    if selected is None:
        return []
    active = entries[selected:]
    require(all(' actual=' + mode + ' ' in line for line in active), 'Selected RKNN I/O changed or became unavailable')
    require(all('model=/root/npu/whiteboard_3cls/det-yolov8n-3cls-wb_v4_combo-rk3568-raw-dfl6-int8.rknn ' in line or
                'model=wb_v4_combo ' in line for line in active), 'Selected inference model changed')
    return active

def check_build(build):
    require(sha(build['binary']) == build['binary_sha256'], 'Immutable viewer executable changed')
    require(os.path.realpath(build['binary']) == build['binary'], 'Viewer executable path contains a symlink')
    for name, digest in build['source_sha256'].items():
        require(sha(build['remote_directory'] + '/src/' + name) == digest, 'Viewer source changed: ' + name)
    for path, digest in build['dependencies'].items():
        require(sha(path) == digest, 'Compiled dependency changed: ' + path)

def no_dma_tests(request, candidate_config, emit):
    proof = request['build']['proof']
    require(proof['status'] == 'target_build_selftests_passed' and
            proof['executable_sha256'] == request['build']['binary_sha256'], 'Viewer selftest binding differs')
    require({v['option'] for v in proof['tests']} ==
            {'--vision-selftest', '--camera-dma-selftest', '--dfl-selftest'} and
            all(v['exit_code'] == 0 for v in proof['tests']), 'Required target viewer selftests missing')
    emit('selftests_verified', binary_sha256=proof['executable_sha256'],
         test_options=[v['option'] for v in proof['tests']], reused_immutable_build=True)

def comparison_configuration(saved, emit):
    compare_environment = {k:v for k,v in saved['candidate']['environment'].items() if k != 'DETVIEW_RKNN_IO'}
    comparison = dict(argv=saved['candidate']['argv'], cwd=saved['candidate']['cwd'],
                      uid=saved['candidate']['uid'], gid=saved['candidate']['gid'], groups=saved['candidate']['groups'],
                      environment_sha256=hashlib.sha256(json.dumps(compare_environment, sort_keys=True).encode()).hexdigest(),
                       files_sha256=saved['candidate']['files'], boot_id=saved['boot_id'])
    stereo_environment = {k:v for k,v in saved['candidate']['environment'].items() if k != 'DETVIEW_STEREO_ASYNC'}
    stereo_compare = dict(comparison, environment_sha256=hashlib.sha256(
        json.dumps(stereo_environment, sort_keys=True).encode()).hexdigest())
    emit('comparison_configuration', configuration=comparison,
          sha256=hashlib.sha256(json.dumps(comparison, sort_keys=True).encode()).hexdigest(),
          stereo_worker_configuration_sha256=hashlib.sha256(json.dumps(stereo_compare, sort_keys=True).encode()).hexdigest(),
          stereo_worker=saved['candidate']['environment'].get('DETVIEW_STEREO_ASYNC', '0'),
          stereo_configuration=stereo_configuration(saved),
         safe_environment={k:v for k,v in compare_environment.items() if k.startswith(('DETVIEW_', 'QT_QPA_UPDATE_')) or
                           k in {'DET_BENCH', 'DET_INT8_IN'}})

def stereo_configuration(saved):
    candidate = saved['candidate']
    argv = candidate['argv']
    require('--stereo-config' in argv, 'Pinned stereo configuration required')
    path = argv[argv.index('--stereo-config') + 1]
    require(sha(path) == candidate['files'][path], 'Pinned stereo configuration changed')
    pairs = [[int(row['left']), int(row['right'])] for row in json.loads(Path(path).read_text())['pairs']]
    require(1 <= len(pairs) <= 2 and all(1 <= v <= 6 for pair in pairs for v in pair) and
            len(set(v for pair in pairs for v in pair)) == 2 * len(pairs), 'Invalid configured stereo pairs')
    return dict(path=path, sha256=candidate['files'][path], pairs=pairs)

def observe_trial(request, saved, target, emit):
    common = dict(config=saved['candidate_config'], baseline=saved['candidate'], target=target)
    identity_pin = pin_sample_identity(common)
    global_observation_guard(target)
    log = Path(saved['candidate_config']['log'])
    require(log.stat().st_size <= MAX_LOG, 'Trial log too large')
    mode = request['mode']
    comparison_configuration(saved, emit)
    def workload_log():
        require(log.stat().st_size <= MAX_LOG, 'Trial log exceeds retained bound')
        content = log.read_text(errors='replace')
        lines = content.splitlines()
        io = selected_io_entries(lines, mode)
        counters = [json.loads(line.split('[acceptance] ',1)[1]) for line in lines if line.startswith('[acceptance] ')]
        ready = (bool(io) and any('sha256=21451a51f680ececd9ee75bcbb4db3e4ccee05d210ef9ffef2f1b99da61a8b31' in line for line in io) and
                 any('[panes] mode=6 ' in line and ' have=111111 ' in line for line in lines) and
                 bool(counters) and int(counters[-1]['completed']) > 0 and
                 all(int(v) > 0 for v in counters[-1]['delivered']) and
                 any(int(v) > 0 for v in re.findall(r'pair_compute_ok=([0-9]+)', content)))
        return content, counters, ready
    readiness_deadline = time.monotonic() + 45
    while True:
        sample_identity(common, identity_pin)
        text, counters, ready = workload_log()
        if ready:
            break
        require(time.monotonic() < readiness_deadline, 'Complete capture/inference/stereo workload did not become ready')
        time.sleep(.25)
    mapped = set()
    for line in Path('/proc', str(target['pid']), 'maps').read_text().splitlines():
        columns = line.split(None, 5)
        if len(columns) == 6 and columns[5].endswith('/librknnrt.so'):
            mapped.add(str(Path(columns[5]).resolve()))
    require(mapped == {request['build']['proof']['runtime']}, 'Candidate maps a different RKNN runtime')
    check_build(request['build'])
    begin = paired_time()
    emit('measurement_started', clocks=begin, seconds_limit=request['seconds'],
         mode=mode, observer_policy='identity10s/global30s; exact boundaries; no thread sampler or trace')
    deadline = begin['monotonic_ns'] + int(request['seconds'] * 1e9)
    sample_due = begin['monotonic_ns']
    global_due = begin['monotonic_ns']
    progress_due = begin['monotonic_ns']
    while time.monotonic_ns() < deadline:
        now = time.monotonic_ns()
        if now >= sample_due:
            sample_identity(common, identity_pin)
            sample_due = now + 10000000000
        if now >= global_due:
            global_observation_guard(target)
            global_due = now + 30000000000
        if now >= progress_due:
            text, _, _ = workload_log()
            stats = [line for line in text.splitlines() if line.startswith(('[infer-perf]', '[stats]', '[acceptance]'))]
            emit('measurement_progress', mode=mode, elapsed_seconds=(now-begin['monotonic_ns'])/1e9,
                 latest=stats[-1][:1600] if stats else 'waiting for cumulative counters')
            progress_due = now + 10000000000
        time.sleep(min(.25, max(0, (deadline-time.monotonic_ns())/1e9)))
    end = paired_time()
    emit('measurement_endpoint', clocks=end, elapsed_seconds=(end['monotonic_ns']-begin['monotonic_ns'])/1e9,
         observer_thread_cpu_seconds=(end['sampler_cpu_ns']-begin['sampler_cpu_ns'])/1e9)
    sample_identity(common, identity_pin)
    exact(common)
    verify_files(saved['candidate_config'], saved['candidate'])
    global_observation_guard(target)
    check_build(request['build'])
    final_log, counters, ready = workload_log()
    require(ready, 'Complete workload disappeared at the endpoint')
    stereo = stereo_configuration(saved)
    stereo_endpoint = latest_stereo_endpoint(final_log, stereo['pairs'])
    bounded = [row for row in counters if int(row['sample_begin_ns']) >= begin['monotonic_ns'] + 10000000000 and
               int(row['sample_end_ns']) <= min(end['monotonic_ns'], stereo_endpoint)]
    require(len(bounded) >= 2, 'No bounded post-warmup cumulative endpoints')
    measured_window = observed_window(bounded[0], bounded[-1], 120)
    measured_window['stereo'] = validate_stereo(final_log, stereo['pairs'],
        int(bounded[0]['sample_begin_ns']), int(bounded[-1]['sample_end_ns']))
    delta = measured_window['delta']
    require(delta['completed'] > 0 and delta['failed'] == 0 and
            all(int(v) > 0 for v in delta['delivered']) and measured_window['all_six_cameras_painted'],
            'Accepted interval lacks complete six-camera paints/delivery or successful inference')
    emit('acceptance_window', result=measured_window)
    emit('measured', clocks=end, elapsed_seconds=(end['monotonic_ns']-begin['monotonic_ns'])/1e9, mode=mode)

def action(request, emit):
    if request['action'] == 'configuration':
        require(re.fullmatch('/userdata/linaro/100h_performance/host_stall_[0-9a-f]{32}/original.snapshot.json', request['snapshot']),
                'Invalid retained trial snapshot path')
        require(sha(request['snapshot']) == request['snapshot_sha256'], 'Retained trial snapshot changed')
        saved = private_read(request['snapshot'])
        require(saved['boot_id'] == boot(), 'Board rebooted after trial')
        comparison_configuration(saved, emit)
        return
    if request['action'] == 'diagnostic':
        return run_trial(request, emit)
    return previous_trial_action(request, emit)
'''


def enrich_configuration(receipt_path):
    diag = diagnostic_helpers()
    receipt = diag.read_json(receipt_path)
    existing = [e for e in receipt['events'] if e['state'] == 'comparison_configuration']
    if existing and existing[0].get('stereo_configuration'):
        return
    if receipt.get('status') != 'success' or not receipt.get('restoration_verified'):
        raise ValueError('Only a successfully restored trial can be enriched')
    snap = next(e for e in receipt['events'] if e['state'] == 'snapshot_saved')
    motion = diag.load_helpers()
    motion.REMOTE_SOURCE = motion.REMOTE_SOURCE.split("if __name__ == '__main__':",1)[0] + diag.REMOTE_AGENT + EXTRA + diag.REMOTE_MAIN
    from board_host import ssh_connect
    client = ssh_connect()
    result = []
    try:
        motion.remote_run(client, dict(action='configuration', snapshot=snap['snapshot'],
                                      snapshot_sha256=snap['snapshot_sha256'], timeout=90), result.append)
    finally:
        client.close()
    if len(result) != 1 or result[0]['state'] != 'comparison_configuration':
        raise RuntimeError('No retained comparison configuration evidence')
    if existing:
        if result[0]['sha256'] != existing[0]['sha256']:
            raise ValueError('Retained comparison configuration changed')
        receipt['events'].remove(existing[0])
    receipt['events'].append(dict(result[0], provenance='verified_private_start_snapshot_after_restoration'))
    motion.viewer.atomic_json(receipt_path, receipt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-receipt', type=Path, required=True)
    parser.add_argument('--current-receipt', type=Path, required=True)
    parser.add_argument('--calibration-receipt', type=Path)
    parser.add_argument('--mode', choices=('legacy', 'native'), required=True)
    parser.add_argument('--stereo-worker', choices=('sync', 'async'),
                        help='Opt-in candidate comparison; hold RKNN I/O mode fixed between stereo trials')
    parser.add_argument('--native-proof', type=Path, help='Successful multi-fixture hardware comparison report')
    parser.add_argument('--helper-proof', type=Path, help='Successful hardware proof of the exact frozen viewer helper')
    parser.add_argument('--seconds', type=int, default=150)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.seconds < 150:
        parser.error('At least150s is required to select post-warmup endpoints spanning120s')
    diag = diagnostic_helpers()
    motion = diag.load_helpers()
    calibration = args.calibration_receipt or diag.CAL_CAPTURE
    cal = diag.calibration_request(calibration, motion)
    outer = diag.read_json(args.build_receipt)
    if outer.get('status') != 'success' or outer.get('backend') != 'viewer':
        raise ValueError('Successful immutable viewer build receipt required')
    proof = outer['build_proof']
    source_hashes = {name[4:]: digest for name,digest in outer['source_sha256'].items() if name.startswith('src/')}
    if not source_hashes or proof['source_sha256'] != source_hashes:
        raise ValueError('Viewer source receipt mismatch')
    deps = dict(proof['compiler_dependency_sha256'], **proof['linked_library_sha256'])
    for name, digest in [('src/hardware_inference.h', source_hashes['hardware_inference.h']),
                         ('src/native_adapter.h', source_hashes['native_adapter.h']),
                         ('sdk/rknn_api.h', outer['source_sha256']['sdk/rknn_api.h'])]:
        if deps.get(outer['package'] + '/' + name) != digest:
            raise ValueError('Viewer compiler dependency differs: ' + name)
    build = dict(binary=outer['binary'], binary_sha256=outer['binary_sha256'],
                 remote_directory=outer['package'], source_sha256=source_hashes, dependencies=deps, proof=proof)
    current_receipt = diag.read_json(args.current_receipt)
    events = [e for e in current_receipt['events'] if e['state'] in ('restored', 'viewer_preserved')]
    if not events:
        raise ValueError('Current viewer requires a verified identity receipt')
    current = dict(diag.HDMI, pid=events[-1]['pid'], starttime=events[-1]['starttime'])
    if args.mode == 'native':
        if not args.native_proof or not args.helper_proof:
            parser.error('Native trial requires --native-proof and --helper-proof')
        native = native_binding(args.native_proof, source_hashes, proof, diag, outer['source_sha256']['sdk/rknn_api.h'])
        if native['experiment_host'] != outer['host']:
            raise ValueError('Native experiment and viewer build target different boards')
        helper = diag.read_json(args.helper_proof)
        if helper.get('status') != 'success' or helper.get('backend') != 'viewer_parity' or helper['host'] != outer['host']:
            raise ValueError('Successful same-board viewer helper proof required')
        evidence = helper['helper_proof']
        identity = evidence['identity']
        if not evidence.get('hardware_parity_complete') or evidence['status'] != 'actual_helper_array_parity_passed':
            raise ValueError('Frozen viewer helper parity failed')
        for key, digest in [('helper_sha256', source_hashes['hardware_inference.h']),
                            ('adapter_sha256', source_hashes['native_adapter.h']),
                            ('sdk_sha256', outer['source_sha256']['sdk/rknn_api.h']),
                            ('runtime_sha256', proof['runtime_sha256']),
                            ('model_sha256', native['target']['model_sha256'])]:
            if identity[key] != digest:
                raise ValueError('Viewer helper proof differs: ' + key)
    source = motion.REMOTE_SOURCE.split("if __name__ == '__main__':",1)[0] + diag.REMOTE_AGENT
    anchor = "    candidate_config = config_for(candidate, str(directory / 'candidate.log'))"
    if source.count(anchor) != 1:
        raise ValueError('Trial environment patch anchor changed')
    source = source.replace(anchor,
        "    candidate['environment'] = dict(candidate['environment'], DETVIEW_RKNN_IO=request['mode'], DETVIEW_ACCEPTANCE='1')\n" + anchor)
    if args.stereo_worker is not None:
        source = source.replace(anchor,
            "    candidate['environment']['DETVIEW_STEREO_ASYNC'] = request['stereo_worker']\n" + anchor)
    acceptance = (TASK/'viewer/acceptance_summary.py').read_text().split('def main():',1)[0]
    stereo_code = (TASK/'viewer/stereo_summary.py').read_text()
    source += acceptance + stereo_code + EXTRA + diag.REMOTE_MAIN
    if args.check:
        compile(source, '<viewer trial>', 'exec')
        print(json.dumps(dict(valid=True, ssh=False, binary=build['binary'], mode=args.mode,
                               stereo_worker=args.stereo_worker,
                               restore_always=True, measured_seconds=args.seconds)))
        return 0
    from board_host import board_host, ssh_connect
    if cal['host'] != board_host() or outer['host'] != board_host():
        raise ValueError('Build/calibration/board identity mismatch')
    token = uuid.uuid4().hex
    directory = TASK/'runs'/('viewer_' + args.mode + '_' + token)
    directory.mkdir(parents=True)
    remote = '/userdata/linaro/100h_performance/host_stall_' + token
    receipt_path = directory/'receipt.json'
    receipt = dict(status='running', operation=token, mode=args.mode, host=board_host(),
                   binary_sha256=build['binary_sha256'], events=[], remote_directory=remote,
                   build_receipt_sha256=diag.sha_file(args.build_receipt), seconds_limit=args.seconds,
                   native_proof_sha256=diag.sha_file(args.native_proof) if args.native_proof else None)
    receipt['helper_proof_sha256'] = diag.sha_file(args.helper_proof) if args.helper_proof else None
    request = dict(action='diagnostic', operation=token, timeout=args.seconds+400, directory=remote,
                   current=current, original_binary=diag.ORIGINAL_BINARY, calibration=cal, build=build,
                    seconds=args.seconds, mode=args.mode, test_options=[], selftest_proof={}, tracefs=False)
    if args.stereo_worker is not None:
        receipt['stereo_worker'] = args.stereo_worker
        request['stereo_worker'] = '1' if args.stereo_worker == 'async' else '0'
    lock = ROOT/'log/100h_motion/board_session.lock'
    held = sent = False
    client = None
    motion.REMOTE_SOURCE = source
    receipt['supervisor_source_sha256'] = hashlib.sha256(source.encode()).hexdigest()
    def event(value):
        receipt['events'].append(dict(value, local_monotonic_ns=time.monotonic_ns()))
        motion.viewer.atomic_json(receipt_path, receipt)
        detail = ''
        if value['state'] == 'measurement_progress':
            detail = value.get('latest', '')
            if detail.startswith('[acceptance] '):
                row = json.loads(detail.split('[acceptance] ', 1)[1])
                detail = ('cumulative completed=' + row['completed'] + ' failed=' + row['failed'] +
                          ' fresh_swaps=' + '/'.join(row['per_camera_paints']) +
                          ' requested_pixels_MiB=' + format(sum(int(v) for v in row['dma_payload_request_bytes']) / 1048576, '.1f'))
        elif value['state'] == 'acceptance_window':
            summary = value['result']
            detail = ('seconds=' + format(summary['seconds_bounds'][0], '.3f') +
                      ' completed_fps=' + format(summary['completed_fps_bounds']['minimum_fps'], '.4f') +
                      ' fresh_fps=' + '/'.join(format(v['minimum_fps'], '.2f') for v in summary['per_camera_paint_fps_bounds']))
        print('Viewer ' + args.mode + ': ' + value['state'] + (' ' + detail if detail else ''), flush=True)
    try:
        with lock.open('x') as stream:
            json.dump(dict(operation=token, pid=os.getpid(), action='native_viewer_trial'), stream)
        held=True
        client=ssh_connect()
        sent=True
        motion.remote_run(client, request, event)
        receipt['status']='observed_awaiting_verified_artifacts'
    except BaseException as exc:
        receipt.update(status='failed', error=type(exc).__name__+': '+str(exc))
    finally:
        if client:
            try:
                bundles = [e for e in receipt['events'] if e['state'] == 'artifacts']
                artifact = next(v for v in bundles[-1]['files'] if v['name'] == 'candidate.redacted.log')
                log = directory/'candidate.redacted.log'
                with log.open('xb') as stream:
                    def downloaded(value):
                        if value['state'] == 'artifact_chunk':
                            stream.write(base64.b64decode(value['base64'], validate=True))
                        elif value['state'] != 'downloaded':
                            event(value)
                    motion.remote_run(client, dict(action='download', artifact=artifact, timeout=90), downloaded)
                if diag.sha_file(log) != artifact['sha256'] or log.stat().st_size != artifact['bytes']:
                    raise RuntimeError('Downloaded trial log size/hash mismatch')
                receipt['log_sha256']=artifact['sha256']
                windows = [e['result'] for e in receipt['events'] if e['state'] == 'acceptance_window']
                if not windows:
                    raise RuntimeError('No verified cumulative acceptance window')
                motion.viewer.atomic_json(directory/'analysis.json', windows[-1])
                receipt['analysis_sha256']=diag.sha_file(directory/'analysis.json')
                if receipt['status'] == 'observed_awaiting_verified_artifacts':
                    receipt['status']='success'
            except Exception as exc:
                receipt['download_error']=str(exc)
                receipt['status']='failed'
            client.close()
        restored=any(e['state']=='restored' for e in receipt['events'])
        receipt['restoration_verified']=restored
        receipt['board_lock_retained']=held and sent and not restored
        motion.viewer.atomic_json(receipt_path,receipt)
        if held and (not sent or restored):
            lock.unlink()
        print('Receipt: '+str(receipt_path),flush=True)
    return 0 if receipt['status']=='success' else 1


if __name__=='__main__':
    sys.exit(main())
