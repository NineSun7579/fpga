"""Exclusive, identity-bound PLL56 SRAM trial with exact-current-config recovery."""
import argparse
import base64
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'fpga'))
import verify_rollback_current as verify
import summarize_observation as metrics
rollback = verify.rollback
deploy, board, motion = rollback.deploy, rollback.board, rollback.motion
ROOT, LOG = rollback.ROOT, rollback.LOG
READY = HERE / 'readiness_evidence_ox3p7nss'
HASH = 'bc40afff4210bee0333feff7754d8fd5fd45207b1a04a301cdf8add54d7465b0'
ABSENT_RESTORE = r'''
prior_absent_action = action
def action(request, emit):
    if request['action'] != 'restore_absent_current':
        return prior_absent_action(request, emit)
    require(not owners(), 'DMA owner appeared during absent restore')
    require(not subprocess.run(['pgrep','-x','detview'], stdout=subprocess.PIPE).stdout.strip(), 'Viewer appeared during absent restore')
    require(sha(request['source_snapshot']) == request['source_sha256'], 'Saved successful snapshot changed')
    saved = private_read(request['source_snapshot'])
    require(saved['boot_id'] == boot(), 'Saved configuration boot mismatch')
    require(process(saved['baseline']['pid']) is None, 'Old viewer PID exists')
    # Preserve other workers' current files. Bind restoration to fresh hashes,
    # retaining the historical manifest separately rather than replacing files.
    baseline = dict(saved['baseline'])
    baseline['files'] = {p: sha(p) for p in saved['baseline']['files']}
    baseline['exe_sha256'] = sha(baseline['exe'])
    require(baseline['exe'] == '/userdata/linaro/detview-calibration-work/build/detview', 'Unexpected saved executable')
    verify_files(saved['config'], baseline)
    replacement = dict(saved, operation=request['operation'], target=None, baseline=baseline,
        historical_files=saved['baseline']['files'])
    replacement['config'] = dict(saved['config'], log=request['log'])
    private_write(request['snapshot'], replacement)
    emit('snapshot_saved', snapshot=request['snapshot'], snapshot_sha256=sha(request['snapshot']),
         files=baseline['files'], historical_files=saved['baseline']['files'],
         exe_sha256=baseline['exe_sha256'], preserved_argv=baseline['argv'])
    previous_current_action(dict(action='resume_candidate', snapshot=request['snapshot'],
        snapshot_sha256=sha(request['snapshot']), start_operation=request['operation']), emit)
'''
motion.REMOTE_SOURCE = (motion.REMOTE_SOURCE.split("if __name__ == '__main__':", 1)[0] + ABSENT_RESTORE +
    motion.REMOTE_EXTENSION[motion.REMOTE_EXTENSION.index("if __name__ == '__main__':"):])

def main():
    token = uuid.uuid4().hex
    directory = LOG / ('pll56_deploy_' + token)
    directory.mkdir()
    receipt = dict(operation=token, status='running', host=deploy.board_host(), mode='sram', stages=[])
    path = directory / 'receipt.json'
    client = None
    held = False
    lock = LOG / 'board_session.lock'
    def stage(name, **details):
        stamp = time.strftime('%Y-%m-%d %H:%M:%S')
        receipt.update(stage=name)
        receipt['stages'].append(dict(stage=name, time=stamp, **details))
        motion.viewer.atomic_json(path, receipt)
        print(stamp + ' ' + name, flush=True)
    def action(req, name):
        result = dict(schema=1, action='start', operation=token, host=deploy.board_host(), status='running', events=[])
        dest = directory / (name + '.json')
        def event(value):
            result['events'].append(value)
            motion.viewer.atomic_json(dest, result)
            if value['state'] != 'log_chunk':
                print(time.strftime('%Y-%m-%d %H:%M:%S') + ' ' + name + ': ' + value['state'], flush=True)
        try:
            motion.remote_run(client, req, event)
            result['status'] = 'success'
        except BaseException as exc:
            result.update(status='failed', error=str(exc))
            raise
        finally:
            motion.viewer.atomic_json(dest, result)
        return result
    oldstatus = directory / 'frozen_motion_status.json'
    oldstatus.write_bytes((ROOT / 'project/motion_100h/status.json').read_bytes())
    old = board.load(oldstatus)
    if old.get('status') != 'complete' or old.get('bit_sha256') != rollback.OLD_HASH or motion.sha_file(old['bit']) != rollback.OLD_HASH:
        raise RuntimeError('Frozen recovery evidence mismatch')
    def program(candidate, check):
        bit = READY / 'top.sbit' if candidate else Path(old['bit'])
        status = READY / 'status.json' if candidate else oldstatus
        expected = HASH if candidate else rollback.OLD_HASH
        if motion.sha_file(bit) != expected:
            raise RuntimeError('Actual bit hash changed before programmer invocation')
        dest = directory / (('candidate' if candidate else 'recovery') + ('_check' if check else '_program'))
        command = [sys.executable, '-B', str(ROOT/'project/tools/program_100h_motion.py'), '--mode', 'sram',
                   '--bit', str(bit), '--build-status', str(status), '--log-dir', str(dest)]
        if candidate:
            command += ['--manifest', str(status)]
        if check:
            command += ['--check']
        stage('programmer_invocation', candidate=candidate, check=check, command=command, bit_sha256=expected)
        subprocess.run(command, check=True)
        outcomes = list(dest.glob('run_*/receipt.json'))
        if len(outcomes) != 1:
            raise RuntimeError('Unique programmer receipt required')
        outcome = board.load(outcomes[0])
        if outcome.get('status') != ('validated_only' if check else 'success') or outcome.get('bit_sha256') != expected or outcome.get('mode') != 'sram':
            raise RuntimeError('Programmer outcome mismatch')
        if not check and not all(outcome.get('stages', {}).values()):
            raise RuntimeError('Incomplete programmer stages')
        stage('program_check' if check else 'program_done', candidate=candidate, receipt=str(outcomes[0]))
    identity = board.load(LOG / 'board_identity.json')
    identity['driver'] = board.MODULE
    if identity != dict(bdf='0002:21:00.0', vendor='0x0755', device='0x0755', driver=board.MODULE,
                        device_node=board.DEVICE, device_number='511:0'):
        raise RuntimeError('Stored board identity mismatch')
    def exchange(source, candidate, label, pinned_request=None):
        remote = board.Remote(client)
        if not board.endpoint(remote, identity):
            raise RuntimeError('Fresh endpoint mismatch before close')
        snapshot = '/userdata/linaro/100h_performance/motion_viewer_' + token + '_' + label + '.snapshot.json'
        paused = action(dict(pinned_request or deploy.source_request(source), action='pause_candidate', operation=token, timeout=100,
            new_snapshot=snapshot, log='/userdata/linaro/100h_performance/pll56_' + token + '_' + label + '.log'), label+'_pause')
        if paused['events'][-1]['state'] != 'stopped':
            raise RuntimeError('Unverified normal close')
        stage('normal_close_verified', label=label)
        deadline = time.monotonic() + 10
        while remote.owners() or remote.viewers() or remote.run('pgrep -x detview', allowed=(0,1))[0] == 0:
            if time.monotonic() >= deadline:
                raise RuntimeError('DMA owner/viewer remains; no force action')
            time.sleep(.2)
        if not board.endpoint(remote, identity):
            raise RuntimeError('Endpoint changed before quiescence')
        stage('dma_free_quiesce', label=label)
        remote.text('rmmod ' + board.MODULE)
        remote.text('test ! -d /sys/module/' + board.MODULE)
        remote.text('echo 1 > ' + board.PCI + '/remove')
        remote.text('test ! -d ' + board.PCI)
        program(candidate, False)
        class Adapter:
            def state(self, state, **details):
                stage(state, **details)
        board.execute(argparse.Namespace(action='reconnect', baseline=LOG/'viewer_launch_baseline.json',
            viewer_build=LOG/'viewer_build.json', identity_json=LOG/'board_identity.json', ready_timeout=30), Adapter())
        saved = next(e for e in paused['events'] if e['state'] == 'snapshot_saved')
        resumed = action(dict(action='resume_candidate', operation=token, timeout=100, snapshot=snapshot,
            snapshot_sha256=saved['snapshot_sha256'], start_operation=token), label+'_resume')
        resumed['events'].insert(0, saved)
        motion.viewer.atomic_json(directory/(label+'_resume.json'), resumed)
        # source_request intentionally accepts only canonical snapshot names; this local request uses the saved, hash-bound path.
        common = dict(snapshot=snapshot, snapshot_sha256=saved['snapshot_sha256'], start_operation=token, target=resumed['events'][-1])
        return resumed, common
    def observe(common, label, seconds=120):
        stage('observe_seconds', label=label, seconds=seconds)
        observed = action(dict(common, action='observe', operation=token, timeout=seconds+60, seconds=seconds), label+'_observe')
        text = ''.join(e['text'] for e in observed['events'] if e['state'] == 'log_chunk')
        (directory/(label+'_observation.log')).write_text(text, encoding='utf-8')
        end = observed['events'][-1]
        if end['state'] != 'observed':
            raise RuntimeError('Incomplete observation')
        summary = metrics.summarize(observed)
        summary['health'] = verify.health_summary(text, end)
        summary['viewer_metrics'] = motion.candidate.summarize(text)
        motion.viewer.atomic_json(directory/(label+'_metrics.json'), summary)
        shot = action(dict(common, action='rollback_screenshot', timeout=60), label+'_screenshot')
        value = next(e for e in shot['events'] if e['state'] == 'screenshot')
        raw = base64.b64decode(value['xwd'])
        (directory/(label+'_screen.xwd')).write_bytes(raw)
        fields = struct.unpack('>25I', raw[:100])
        if (fields[1], fields[11], fields[7], *fields[14:17]) != (7,32,0,0xff0000,0xff00,0xff):
            raise RuntimeError('Unexpected XWD pixel format')
        verify.Image.frombytes('RGB', (fields[4],fields[5]), raw[fields[0]+fields[19]*12:], 'raw', 'BGRX', fields[12], 1).save(directory/(label+'_screen.png'))
        stage('measurement_saved', label=label, health=summary['health'])
        return summary
    try:
        with lock.open('x') as stream:
            json.dump(dict(operation=token, pid=os.getpid(), action='pll56_deployment'), stream)
        held = True
        stage('exclusive_board_lock_acquired')
        program(True, True)
        program(False, True)
        client = deploy.ssh_connect(timeout=8)
        if not board.endpoint(board.Remote(client), identity):
            raise RuntimeError('Initial endpoint mismatch')
        remote = board.Remote(client)
        if not remote.owners() and not remote.viewers() and remote.run('pgrep -x detview', allowed=(0,1))[0] == 1:
            prior = board.load(LOG/'rollback_current_3fb258dc1b1a492a97df74118ca68ff6/resume.json')
            saved = prior['events'][0]
            stage('restore_absent_viewer_from_successful_full_snapshot')
            action(dict(action='restore_absent_current', operation=token, timeout=100,
                source_snapshot=saved['snapshot'], source_sha256=saved['snapshot_sha256'],
                snapshot='/userdata/linaro/100h_performance/motion_viewer_' + token + '_absent.snapshot.json',
                log='/userdata/linaro/100h_performance/pll56_' + token + '_absent.log'), 'absent_restore')
        captured = action(dict(action='identity_snapshot', operation=token, timeout=100,
            snapshot='/userdata/linaro/100h_performance/motion_viewer_' + token + '.snapshot.json',
            log='/userdata/linaro/100h_performance/pll56_' + token + '_capture.log', model=motion.MODEL), 'capture')
        stage('fresh_full_configuration_saved', viewer=captured['events'][-1])
        resumed, common = exchange(captured, True, 'candidate')
        early = observe(common, 'candidate_early', seconds=10)
        health = early['health']
        early_bad = (set(health['cameras']) != set('123456') or
            any(v['min_delivered_fps'] <= 0 or v['max_unstable'] > 0 for v in health['cameras'].values()) or
            bool(health['error_lines']) or health['stereo_failures'] > 0)
        summary = early if early_bad else observe(common, 'candidate')
        receipt['candidate_metrics'] = str(directory/'candidate_metrics.json')
        if not summary['health']['recovery_healthy']:
            stage('candidate_unhealthy_restore_frozen_motion')
            # Re-use the same exact identity and saved configuration; no fresh unverified close.
            recovered, recovery_common = exchange(resumed, False, 'recovery', pinned_request=common)
            baseline = observe(recovery_common, 'recovery')
            receipt['recovery_metrics'] = str(directory/'recovery_metrics.json')
            receipt['status'] = 'recovered_target_unmet' if baseline['health']['recovery_healthy'] else 'recovery_unhealthy'
        else:
            receipt['status'] = 'candidate_healthy_target_unmet'
        stage('complete')
    except BaseException as exc:
        receipt.update(status='blocked', error=str(exc))
        stage('blocked_retained_state')
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
