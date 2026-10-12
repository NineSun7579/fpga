"""Identity-bound optimized viewer comparison; restores current viewer afterward."""
import base64
import json
import os
from pathlib import Path
import struct
import sys
import time
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'fpga'))
import verify_rollback_current as verify
rollback = verify.rollback
deploy, board, motion = rollback.deploy, rollback.board, rollback.motion
EXE = '/userdata/linaro/100h_performance/build_e896c57888522673/build/detview'
HASH = 'bcd9650360c7a5f4902722a5612e91b8c63b30315d6b95739ccdd51cfd2d2f60'
EXTRA = r'''
prior_optimized_action = action
def action(request, emit):
    if request['action'] != 'prepare_optimized':
        return prior_optimized_action(request, emit)
    require(sha(request['snapshot']) == request['snapshot_sha256'], 'Snapshot changed')
    saved = private_read(request['snapshot'])
    require(saved['operation'] == request['start_operation'] and saved['boot_id'] == boot(), 'Operation or boot changed')
    require(not owners(), 'New DMA owner appeared')
    require(process(saved['baseline']['pid']) is None, 'Original PID exists')
    require(sha(request['exe']) == request['exe_sha256'], 'Optimized binary hash changed')
    verify_files(saved['config'], saved['baseline'])
    config = dict(saved['config'])
    config.update(exe=request['exe'], argv=[request['exe']] + config['argv'][1:], log=request['log'])
    env = dict(config['env'])
    env.update(DET_BENCH='1', DETVIEW_GPU_HUD='1', DETVIEW_HUD_BATCH='1', DETVIEW_TEXTURE_RING='1',
        DETVIEW_CAPTURE_MAX_FPS='0', DETVIEW_CAPTURE_FPS_BY_CAMERA='40,40,30,30,40,40')
    config['env'] = env
    baseline = dict(saved['baseline'], exe=config['exe'], exe_sha256=request['exe_sha256'],
        argv=config['argv'], environment=env, files=dict(saved['baseline']['files']))
    baseline['files'][config['exe']] = request['exe_sha256']
    root = Path(request['exe']).parents[1] / 'src'
    for p in root.rglob('*'):
        if p.is_file():
            baseline['files'][str(p)] = sha(p)
    verify_files(config, baseline)
    private_write(request['new_snapshot'], dict(saved, operation=request['operation'], config=config, baseline=baseline, target=None))
    emit('snapshot_saved', snapshot=request['new_snapshot'], snapshot_sha256=sha(request['new_snapshot']),
        preserved_argv=config['argv'], files=baseline['files'])
'''
motion.REMOTE_SOURCE = (motion.REMOTE_SOURCE.split("if __name__ == '__main__':",1)[0] + EXTRA +
    motion.REMOTE_EXTENSION[motion.REMOTE_EXTENSION.index("if __name__ == '__main__':"):])

def main():
    token = uuid.uuid4().hex
    directory = rollback.LOG / ('pll56_optimized_' + token)
    directory.mkdir()
    receipt = dict(operation=token, status='running', stages=[], note='Frozen motion SRAM; optimized binary preserves calibration argv including trial-meters flag, whose semantics are absent in optimized source.')
    lock = rollback.LOG/'board_session.lock'
    client = None
    held = False
    recovery = None
    current = None
    def stage(name, **details):
        stamp = time.strftime('%Y-%m-%d %H:%M:%S')
        receipt['stages'].append(dict(stage=name, time=stamp, **details))
        motion.viewer.atomic_json(directory/'receipt.json', receipt)
        print(stamp + ' ' + name, flush=True)
    def action(request, name):
        result = dict(schema=1, operation=token, action=request['action'], host=deploy.board_host(), status='running', events=[])
        def emit(value):
            result['events'].append(value)
            motion.viewer.atomic_json(directory/(name+'.json'), result)
            if value['state'] != 'log_chunk':
                print(time.strftime('%Y-%m-%d %H:%M:%S') + ' ' + name + ': ' + value['state'], flush=True)
        try:
            motion.remote_run(client, request, emit)
            result['status'] = 'success'
        except BaseException as exc:
            result.update(status='failed', error=str(exc))
            raise
        finally:
            motion.viewer.atomic_json(directory/(name+'.json'), result)
        return result
    def common(snapshot, target):
        return dict(snapshot=snapshot['snapshot'], snapshot_sha256=snapshot['snapshot_sha256'], start_operation=token, target=target)
    def resume(snapshot, label):
        return action(dict(action='resume_candidate', operation=token, timeout=100,
            snapshot=snapshot['snapshot'], snapshot_sha256=snapshot['snapshot_sha256'], start_operation=token),label)['events'][-1]
    def observe(request, label):
        stage('observe_120_seconds', label=label)
        result = action(dict(request, action='observe', operation=token, seconds=120, timeout=180), label+'_observe')
        text = ''.join(e['text'] for e in result['events'] if e['state']=='log_chunk')
        (directory/(label+'_observation.log')).write_text(text,encoding='utf-8')
        health = verify.health_summary(text,result['events'][-1])
        motion.viewer.atomic_json(directory/(label+'_health.json'),health)
        shot = action(dict(request, action='rollback_screenshot', timeout=60),label+'_screenshot')
        raw = base64.b64decode(next(e for e in shot['events'] if e['state']=='screenshot')['xwd'])
        (directory/(label+'_screen.xwd')).write_bytes(raw)
        f = struct.unpack('>25I',raw[:100])
        if (f[1],f[11],f[7],*f[14:17]) != (7,32,0,0xff0000,0xff00,0xff):
            raise RuntimeError('Unexpected screenshot format')
        verify.Image.frombytes('RGB',(f[4],f[5]),raw[f[0]+f[19]*12:],'raw','BGRX',f[12],1).save(directory/(label+'_screen.png'))
        stage('measurement_saved',label=label,health=health)
    try:
        with lock.open('x') as stream:
            json.dump(dict(operation=token,pid=os.getpid(),action='pll56_optimized_trial'),stream)
        held = True
        client = deploy.ssh_connect(timeout=8)
        identity = board.load(rollback.LOG/'board_identity.json')
        identity['driver'] = board.MODULE
        if not board.endpoint(board.Remote(client),identity):
            raise RuntimeError('Fresh endpoint mismatch')
        captured = action(dict(action='identity_snapshot',operation=token,timeout=100,
            snapshot='/userdata/linaro/100h_performance/motion_viewer_'+token+'.snapshot.json',
            log='/userdata/linaro/100h_performance/pll56_optimized_'+token+'_capture.log',model=motion.MODEL),'capture')
        captured['action'] = 'start'
        pause = action(dict(deploy.source_request(captured), action='pause_candidate',operation=token,timeout=100,
            new_snapshot='/userdata/linaro/100h_performance/motion_viewer_'+token+'_recovery.snapshot.json',
            log='/userdata/linaro/100h_performance/pll56_optimized_'+token+'_recovery.log'),'pause_current')
        if pause['events'][-1]['state'] != 'stopped':
            raise RuntimeError('Current viewer normal stop unverified')
        recovery = next(e for e in pause['events'] if e['state']=='snapshot_saved')
        stage('exact_current_config_saved_and_normal_close_verified')
        prep = action(dict(action='prepare_optimized',operation=token,timeout=100,
            snapshot=recovery['snapshot'],snapshot_sha256=recovery['snapshot_sha256'],start_operation=token,
            exe=EXE,exe_sha256=HASH,new_snapshot='/userdata/linaro/100h_performance/motion_viewer_'+token+'_optimized.snapshot.json',
            log='/userdata/linaro/100h_performance/pll56_optimized_'+token+'_trial.log'),'prepare')
        saved = prep['events'][-1]
        current = common(saved,resume(saved,'optimized_resume'))
        observe(current,'optimized')
        receipt['status'] = 'measured_target_unmet'
    except BaseException as exc:
        receipt.update(status='blocked',error=str(exc))
        stage('trial_error')
    finally:
        if client and recovery:
            try:
                if current:
                    action(dict(current,action='pause_candidate',operation=token,timeout=100,
                        new_snapshot='/userdata/linaro/100h_performance/motion_viewer_'+token+'_optimized_stopped.snapshot.json',
                        log='/userdata/linaro/100h_performance/pll56_optimized_'+token+'_stopped.log'),'optimized_stop')
                restored = common(recovery,resume(recovery,'current_restore'))
                observe(restored,'restored_current')
                stage('exact_current_viewer_restored')
            except BaseException as exc:
                receipt.update(status='recovery_blocked',recovery_error=str(exc))
                stage('recovery_blocked')
        motion.viewer.atomic_json(directory/'receipt.json',receipt)
        print('Receipt: '+str(directory/'receipt.json'),flush=True)
        if client:
            client.close()
        if held and board.load(lock).get('operation') == token:
            lock.unlink()

if __name__ == '__main__':
    main()
