"""Fresh identity-pinned current calibration SRAM rollback; never writes Flash."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
import deploy_sram as deploy

board, motion = deploy.board, deploy.motion
ROOT, LOG = deploy.ROOT, deploy.LOG
OLD_HASH = 'e3da6e1fbc7d0bb2abcc2ee57342906e395fb74cecd1f3163e9ada33e89e96f7'
EXTRA = r'''
previous_current_action = action
def action(request, emit):
    if request['action'] != 'identity_snapshot':
        return previous_current_action(request, emit)
    own = owners()
    require(len(own) == 1, 'Expected sole current DMA owner')
    snap = process(own[0])
    require(snap is not None, 'Current owner exited; capture again')
    exe = snap['exe']
    require(exe == '/userdata/linaro/detview-calibration-work/build/detview' or
            re.fullmatch('/userdata/linaro/100h_performance/build_[0-9a-f]{16}/build/detview', exe),
            'Current viewer outside authorized whitelist')
    require(snap['argv'][0] == exe and snap['uid'] == 0, 'Unexpected current viewer identity')
    require(not snap['environment'].get('LD_PRELOAD'), 'Unexpected preload')
    if request.get('expected_hash'):
        require(snap['exe_sha256'] == request['expected_hash'], 'Fresh expected executable hash mismatch')
    config = config_for(snap, request['log'])
    snap['files'] = files(config)
    snap['files'][exe] = sha(exe)
    snap['files'][request['model']] = sha(request['model'])
    # Preserve every current calibration/config file, including referenced maps.
    for root in ['/userdata/linaro/detview-calibration-session',
                 '/userdata/linaro/detview-calibration-work/src']:
        if Path(root).is_dir():
            for p in Path(root).rglob('*'):
                if p.is_file() and p.suffix.lower() in {'.json','.yaml','.yml','.xml','.ini','.cfg','.npz','.npy'}:
                    snap['files'][str(p)] = sha(p)
    for arg in snap['argv'][1:]:
        if arg.startswith('/') and Path(arg).is_file():
            snap['files'][arg] = sha(arg)
    verify_files(config, snap)
    exact(dict(config=config, baseline=snap, target=snap))
    require(owners() == [snap['pid']], 'Owner changed during capture')
    win = windows(snap['pid'], snap['environment'])
    require(len(win) == 1 and win[0]['delete_supported'], 'Unique normal-close window required')
    snap['windows'] = win
    saved = dict(operation=request['operation'], boot_id=boot(), config=config, baseline=snap, target=None)
    private_write(request['snapshot'], saved)
    private_write(request['snapshot'] + '.candidate', dict(operation=request['operation'],
        pid=snap['pid'], starttime=snap['starttime'], exe_sha256=snap['exe_sha256']))
    emit('snapshot_saved', snapshot=request['snapshot'], snapshot_sha256=sha(request['snapshot']),
         files=snap['files'], preserved_argv=snap['argv'])
    emit('started', pid=snap['pid'], starttime=snap['starttime'], exe_sha256=snap['exe_sha256'],
         window=win[0]['id'], captured_existing=True)
'''
motion.REMOTE_SOURCE = (motion.REMOTE_SOURCE.split("if __name__ == '__main__':",1)[0] + EXTRA +
    motion.REMOTE_EXTENSION[motion.REMOTE_EXTENSION.index("if __name__ == '__main__':"):])

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--expected-hash')
    args = parser.parse_args()
    if args.execute:
        motion.valid_hash(args.expected_hash)
    token = uuid.uuid4().hex
    directory = LOG / ('rollback_current_' + token)
    directory.mkdir()
    path = directory / 'receipt.json'
    receipt = dict(operation=token, host=deploy.board_host(), status='running', stages=[], mode='sram')
    def stage(name, **details):
        receipt['stages'].append(dict(stage=name, time=time.strftime('%Y-%m-%d %H:%M:%S'), **details))
        motion.viewer.atomic_json(path, receipt)
        print(name, flush=True)
    def remote_action(client, req, name):
        destination = directory / (name + '.json')
        result = dict(schema=1, action='start', operation=token, host=deploy.board_host(), status='running', events=[])
        def event(value):
            result['events'].append(value)
            motion.viewer.atomic_json(destination, result)
            if value['state'] != 'log_chunk':
                print(name + ': ' + value['state'], flush=True)
        try:
            motion.remote_run(client, req, event)
            result['status'] = 'success'
        finally:
            motion.viewer.atomic_json(destination, result)
        return result
    status = ROOT / 'project/motion_100h/status.json'
    frozen = directory / 'build_status.json'
    frozen.write_bytes(status.read_bytes())
    build = board.load(frozen)
    if build.get('status') != 'complete' or build.get('bit_sha256') != OLD_HASH or motion.sha_file(build['bit']) != OLD_HASH:
        raise RuntimeError('Old motion build evidence mismatch')
    def program(check):
        dest = directory / ('check' if check else 'program')
        command = [sys.executable, '-B', str(ROOT / 'project/tools/program_100h_motion.py'),
            '--mode', 'sram', '--bit', build['bit'], '--build-status', str(frozen), '--log-dir', str(dest)]
        if check:
            command.append('--check')
        subprocess.run(command, check=True)
        outcomes = list(dest.glob('run_*/receipt.json'))
        if len(outcomes) != 1:
            raise RuntimeError('Unique programmer receipt required')
        outcome = board.load(outcomes[0])
        if outcome.get('status') != ('validated_only' if check else 'success') or outcome.get('bit_sha256') != OLD_HASH:
            raise RuntimeError('Program outcome mismatch')
        if not check and not all(outcome.get('stages', {}).values()):
            raise RuntimeError('Incomplete programmer stages')
        stage('program_check' if check else 'program_done', receipt=str(outcomes[0]))
    client = None
    lock = LOG / 'board_session.lock'
    held = False
    try:
        with lock.open('x') as stream:
            json.dump(dict(operation=token, pid=os.getpid(), action='rollback_current'), stream)
        held = True
        program(True)
        client = deploy.ssh_connect(timeout=8)
        remote = board.Remote(client)
        identity = board.load(LOG / 'board_identity.json')
        identity['driver'] = board.MODULE
        if not board.endpoint(remote, identity):
            raise RuntimeError('Current PCI endpoint mismatch')
        capture = remote_action(client, dict(action='identity_snapshot', operation=token, timeout=100,
            snapshot='/userdata/linaro/100h_performance/motion_viewer_' + token + '.snapshot.json',
            log='/userdata/linaro/100h_performance/rollback_current_' + token + '.log',
            model=motion.MODEL, expected_hash=args.expected_hash), 'capture')
        target = capture['events'][-1]
        stage('fresh_capture', pid=target['pid'], starttime=target['starttime'], exe_sha256=target['exe_sha256'])
        if not args.execute:
            receipt['status'] = 'captured_only'
            return
        request = deploy.source_request(capture)
        new_snapshot = '/userdata/linaro/100h_performance/motion_viewer_' + token + '_restore.snapshot.json'
        paused = remote_action(client, dict(request, action='pause_candidate', operation=token, timeout=100,
            new_snapshot=new_snapshot, log='/userdata/linaro/100h_performance/rollback_restored_' + token + '.log'), 'pause')
        if paused['events'][-1]['state'] != 'stopped':
            raise RuntimeError('Normal stop unverified')
        deadline = time.monotonic() + 10
        while remote.owners() or remote.viewers() or remote.run('pgrep -x detview', allowed=(0,1))[0] == 0:
            if time.monotonic() > deadline:
                raise RuntimeError('Owner remains; no force action')
            time.sleep(.2)
        if not board.endpoint(remote, identity):
            raise RuntimeError('Endpoint changed before quiesce')
        stage('quiesce')
        remote.text('rmmod ' + board.MODULE)
        remote.text('test ! -d /sys/module/' + board.MODULE)
        remote.text('echo 1 > ' + board.PCI + '/remove')
        remote.text('test ! -d ' + board.PCI)
        program(False)
        class Adapter:
            def state(self, state, **details):
                stage(state, **details)
        board.execute(argparse.Namespace(action='reconnect', baseline=LOG/'viewer_launch_baseline.json',
            viewer_build=LOG/'viewer_build.json', identity_json=LOG/'board_identity.json', ready_timeout=30), Adapter())
        snapshot = next(e for e in paused['events'] if e['state'] == 'snapshot_saved')
        resumed = remote_action(client, dict(action='resume_candidate', operation=token, timeout=100,
            snapshot=new_snapshot, snapshot_sha256=snapshot['snapshot_sha256'], start_operation=token), 'resume')
        resumed['events'].insert(0, snapshot)
        motion.viewer.atomic_json(directory/'resume.json', resumed)
        common = dict(snapshot=new_snapshot, snapshot_sha256=snapshot['snapshot_sha256'], start_operation=token,
            target=resumed['events'][-1])
        observed = remote_action(client, dict(common, action='observe', operation=token, timeout=180, seconds=120), 'observe')
        if observed['events'][-1]['state'] != 'observed':
            raise RuntimeError('Observation incomplete')
        text = ''.join(e['text'] for e in observed['events'] if e['state'] == 'log_chunk')
        (directory/'observation.log').write_text(text, encoding='utf-8')
        receipt['viewer'] = resumed['events'][-1]
        receipt['status'] = 'success'
        stage('complete')
    except BaseException as exc:
        receipt.update(status='failed', error=str(exc))
        stage('failed_retained_state')
        raise
    finally:
        motion.viewer.atomic_json(path, receipt)
        print('Receipt: ' + str(path), flush=True)
        if client:
            client.close()
        if held and board.load(lock).get('operation') == token:
            lock.unlink()

if __name__ == '__main__':
    main()
