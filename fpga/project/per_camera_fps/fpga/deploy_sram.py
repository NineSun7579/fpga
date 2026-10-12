"""Identity-pinned SRAM deployment; retains partial receipts and exact viewer config."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'project/tools'))
import motion_board_session as board
from board_host import board_host, ssh_connect

spec = importlib.util.spec_from_file_location('pinned_motion_viewer', ROOT / 'project/motion_scheduling/board_viewer.py')
motion = importlib.util.module_from_spec(spec)
spec.loader.exec_module(motion)
LOG = ROOT / 'log/100h_motion'
RUN = ROOT / 'project/per_camera_fps/fpga/deploy_evidence_c0l0p_o6'

EXTENSION = r'''
prior_action = action
def action(request, emit):
    if request['action'] not in ('pause_candidate', 'resume_candidate'):
        return prior_action(request, emit)
    path = request['snapshot']
    require(sha(path) == request['snapshot_sha256'], 'Snapshot hash mismatch')
    saved = private_read(path)
    require(saved['operation'] == request['start_operation'] and saved['boot_id'] == boot(), 'Snapshot operation/boot mismatch')
    if request['action'] == 'pause_candidate':
        target = private_read(path + '.candidate')
        require(target['operation'] == saved['operation'], 'Candidate sidecar operation mismatch')
        for key in ('pid', 'starttime', 'exe_sha256'):
            require(target[key] == request['target'][key], 'Candidate receipt mismatch: ' + key)
        verify_files(saved['config'], saved['baseline'])
        if process(target['pid']) is None:
            require(not owners(), 'Absent viewer but DMA owned')
            require(not same_exe_pids(saved['config']['exe']), 'Another same-exe viewer exists')
            require(target['exe_sha256'] == saved['baseline']['exe_sha256'], 'Exited executable hash mismatch')
            snap = dict(saved['baseline'], pid=target['pid'], starttime=target['starttime'],
                        environment=dict(saved['config']['env']))
            win = windows(target['pid'], snap['environment'])
            require(not win, 'Exited viewer still has windows')
            emit('already_exited_verified', pid=target['pid'], starttime=target['starttime'], device_unowned=True)
        else:
            snap = exact(dict(config=saved['config'], baseline=saved['baseline'], target=target))
            require(owners() == [snap['pid']], 'Expected sole DMA owner')
            win = windows(snap['pid'], snap['environment'])
            require(len(win) == 1 and win[0]['delete_supported'], 'Expected unique normal-close window')
        require(not snap['environment'].get('LD_PRELOAD'), 'Unexpected preload')
        snap.update(files=dict(saved['baseline']['files']), windows=win)
        config = config_for(snap, request['log'])
        replacement = dict(saved, operation=request['operation'], config=config, baseline=snap, target=None)
        private_write(request['new_snapshot'], replacement)
        emit('snapshot_saved', snapshot=request['new_snapshot'], snapshot_sha256=sha(request['new_snapshot']),
             preserved_exe=snap['exe'], preserved_argv=snap['argv'], files=snap['files'],
             settings={k:v for k,v in snap['environment'].items() if k.startswith(('DETVIEW_', 'QT_', 'DET_BENCH', 'LD_PRELOAD'))})
        close_exact(saved['config'], saved['baseline'], target, emit)
        return
    require(not Path(path + '.candidate').exists(), 'Resume identity already exists; inspect before retry')
    require(process(saved['baseline']['pid']) is None, 'Old PID still exists')
    require(not owners(), 'DMA already owned')
    verify_files(saved['config'], saved['baseline'])
    def started(state, **details):
        if state == 'candidate_identity':
            private_write(path + '.candidate', dict(operation=saved['operation'], **details))
        emit(state, **details)
    candidate_action(dict(action='start', config=saved['config'], baseline=saved['baseline'],
                          timeout=40, ready_seconds=5, log=saved['config']['log']), started)
'''
motion.REMOTE_SOURCE = (motion.REMOTE_SOURCE.split("if __name__ == '__main__':", 1)[0]
                        + EXTENSION + motion.REMOTE_EXTENSION[motion.REMOTE_EXTENSION.index("if __name__ == '__main__':"):])

def source_request(receipt):
    if receipt.get('schema') != 1 or receipt.get('action') != 'start' or receipt.get('status') != 'success':
        raise ValueError('Successful start receipt required')
    if receipt['host'] != board_host():
        raise ValueError('Board host mismatch')
    op = receipt['operation']
    if not motion.re.fullmatch('[0-9a-f]{32}', op):
        raise ValueError('Invalid operation')
    snapshots = [e for e in receipt['events'] if e['state'] == 'snapshot_saved']
    targets = [e for e in receipt['events'] if e['state'] == 'started']
    if len(snapshots) != 1 or len(targets) != 1:
        raise ValueError('Unique snapshot and started identity required')
    snapshot, target = snapshots[0], targets[0]
    if snapshot['snapshot'] != '/userdata/linaro/100h_performance/motion_viewer_' + op + '.snapshot.json':
        raise ValueError('Unexpected snapshot path')
    motion.valid_hash(snapshot['snapshot_sha256'])
    motion.valid_hash(target['exe_sha256'])
    return dict(snapshot=snapshot['snapshot'], snapshot_sha256=snapshot['snapshot_sha256'], start_operation=op, target=target)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start-receipt', type=Path, required=True)
    args = parser.parse_args()
    start = board.load(args.start_receipt)
    request = source_request(start)
    identity = board.load(LOG / 'board_identity.json')
    identity['driver'] = board.MODULE
    if identity != dict(bdf='0002:21:00.0', vendor='0x0755', device='0x0755', driver=board.MODULE,
                        device_node=board.DEVICE, device_number='511:0'):
        raise ValueError('Unexpected stored board identity')
    token = uuid.uuid4().hex
    path = LOG / ('sram_deploy_' + token + '.json')
    receipt = dict(schema=1, operation=token, status='running', host=board_host(), stages=[],
                   start_receipt=str(args.start_receipt), start_receipt_sha256=motion.sha_file(args.start_receipt))
    def stage(name, **details):
        receipt['stage'] = name
        receipt['stages'].append(dict(stage=name, time=time.strftime('%Y-%m-%d %H:%M:%S'), **details))
        motion.viewer.atomic_json(path, receipt)
        print('SRAM deploy: ' + name, flush=True)
    def remote_action(client, req, destination):
        result = dict(schema=1, action='start' if req['action']=='resume_candidate' else req['action'],
                      operation=token, host=board_host(), status='running', events=[])
        def event(value):
            result['events'].append(value)
            motion.viewer.atomic_json(destination, result)
            if value['state'] != 'log_chunk':
                print('Viewer: ' + value['state'], flush=True)
        try:
            motion.remote_run(client, req, event)
            result['status'] = 'success'
        except BaseException as exc:
            result.update(status='failed', error=str(exc))
            raise
        finally:
            motion.viewer.atomic_json(destination, result)
        return result
    def program(check):
        directory = RUN / ('checks' if check else 'program')
        before = set(directory.glob('run_*/receipt.json'))
        command = [sys.executable, '-B', str(ROOT/'project/tools/program_100h_motion.py'), '--mode', 'sram',
                   '--bit', str(RUN/'top.sbit'), '--build-status', str(RUN/'status.json'),
                   '--log-dir', str(RUN/('checks' if check else 'program'))]
        if check:
            command.append('--check')
        subprocess.run(command, check=True)
        fresh = set(directory.glob('run_*/receipt.json')) - before
        if len(fresh) != 1:
            raise RuntimeError('Expected one new programmer receipt')
        programmer_path = fresh.pop()
        outcome = board.load(programmer_path)
        if outcome.get('status') != ('validated_only' if check else 'success') or outcome.get('mode') != 'sram' or outcome.get('bit_sha256') != 'a323d6dfad78aff2a4da975bad7c317dc7f6755d56c6a667c08c694893222a3d':
            raise RuntimeError('Programmer receipt outcome/hash mismatch')
        if not check and not all(outcome.get('stages', {}).values()):
            raise RuntimeError('Programmer stages incomplete')
        receipt['check_receipt' if check else 'program_receipt'] = str(programmer_path)
        motion.viewer.atomic_json(path, receipt)
    client = None
    lock = LOG / 'board_session.lock'
    with lock.open('x') as stream:
        json.dump(dict(operation=token, pid=os.getpid(), action='deploy_sram'), stream)
    try:
        stage('immediate_program_check')
        program(True)
        client = ssh_connect(timeout=8)
        remote = board.Remote(client)
        if not board.endpoint(remote, identity):
            raise RuntimeError('Fresh endpoint binding failed before viewer close')
        stage('fresh_identity_verified', identity=identity)
        new_snapshot = '/userdata/linaro/100h_performance/motion_viewer_' + token + '.snapshot.json'
        log = '/userdata/linaro/100h_performance/motion_viewer_' + token + '.log'
        pause_path = LOG / ('sram_viewer_pause_' + token + '.json')
        stage('normal_viewer_close', pause_receipt=str(pause_path))
        paused = remote_action(client, dict(request, action='pause_candidate', operation=token, timeout=100,
                                            new_snapshot=new_snapshot, log=log), pause_path)
        if paused['events'][-1]['state'] != 'stopped':
            raise RuntimeError('No verified normal stop')
        # Normal WM_DELETE can briefly leave a child zombie before its parent reaps
        # it. Wait for all process names to disappear; never signal or ignore owners.
        deadline = time.monotonic() + 5
        while remote.owners() or remote.viewers() or remote.run('pgrep -x detview', allowed=(0,1))[0] == 0:
            if time.monotonic() >= deadline:
                raise RuntimeError('Owner/viewer present before quiescence')
            time.sleep(.2)
        if not board.endpoint(remote, identity):
            raise RuntimeError('Endpoint identity changed before quiescence')
        stage('module_unload')
        remote.text('rmmod ' + board.MODULE)
        remote.text('test ! -d /sys/module/' + board.MODULE)
        stage('endpoint_remove')
        remote.text('echo 1 > ' + board.PCI + '/remove')
        remote.text('test ! -d ' + board.PCI)
        stage('sram_program')
        program(False)
        stage('guarded_reconnect')
        class Adapter:
            def state(self, state, **details):
                stage(state, **details)
        reconnect = argparse.Namespace(action='reconnect', baseline=LOG/'viewer_launch_baseline.json',
            viewer_build=LOG/'viewer_build.json', identity_json=LOG/'board_identity.json', ready_timeout=30)
        board.execute(reconnect, Adapter())
        snapshot = [e for e in paused['events'] if e['state']=='snapshot_saved'][0]
        resume_path = LOG / ('sram_viewer_resume_' + token + '.json')
        stage('restore_exact_viewer', resume_receipt=str(resume_path))
        resumed = remote_action(client, dict(action='resume_candidate', operation=token, timeout=100,
            snapshot=new_snapshot, snapshot_sha256=snapshot['snapshot_sha256'], start_operation=token), resume_path)
        resumed['events'].insert(0, snapshot)
        motion.viewer.atomic_json(resume_path, resumed)
        if resumed['events'][-1]['state'] != 'started':
            raise RuntimeError('No verified viewer restart')
        receipt['resume_receipt'] = str(resume_path)
        stage('observe_120_seconds')
        observe_path = LOG / ('sram_viewer_observe_' + token + '.json')
        observed = remote_action(client, dict(source_request(resumed), action='observe', operation=token,
            timeout=180, seconds=120), observe_path)
        receipt['observation_receipt'] = str(observe_path)
        if observed['events'][-1]['state'] != 'observed':
            raise RuntimeError('No verified observation')
        receipt['status'] = 'success'
        stage('complete')
    except BaseException as exc:
        receipt.update(status='failed', error=str(exc))
        stage('failed_review_recovery_state')
        raise
    finally:
        motion.viewer.atomic_json(path, receipt)
        print('Deployment receipt: ' + str(path), flush=True)
        if client:
            client.close()
        if board.load(lock).get('operation') == token:
            lock.unlink()

if __name__ == '__main__':
    main()
