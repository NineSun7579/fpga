"""Authorized one-off calibration-to-camview switch with private restoration snapshot."""
import json
from pathlib import Path
import shlex
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'project/tools'))
from board_host import ssh_connect
from current_viewer_session import REMOTE_SOURCE

token = uuid.uuid4().hex
extension = r'''
pid = 48587
snap = process(pid)
require(snap is not None and snap['exe'] == '/userdata/linaro/detview-calibration-work/build/detview', 'Calibration identity changed')
require('--calibration-capture' in snap['argv'], 'Unexpected viewer configuration')
require(owners() == [pid], 'Expected calibration as sole DMA owner')
exe = '/userdata/linaro/100h_motion/viewer_eaf579139acf/camview'
require(sha(exe) == 'dc9ca56440e3b10e2241ef52ad99e1e8fd8e692d0bebda27b9e20fcf88d2e5e9', 'Camview binary differs')
saved = '/userdata/linaro/100h_performance/calibration_before_camview_' + TOKEN + '.json'
descriptor = os.open(saved, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
with os.fdopen(descriptor, 'w') as stream:
    json.dump(snap, stream)
win = windows(pid, snap['environment'])
require(len(win) == 1 and win[0]['delete_supported'], 'Expected unique closeable calibration window')
require(process(pid)['starttime'] == snap['starttime'], 'PID changed before close')
close_window(win[0]['id'], snap['environment'])
deadline = time.monotonic() + 30
while time.monotonic() < deadline:
    try:
        current = process(pid)
    except (FileNotFoundError, ProcessLookupError):
        require(not Path('/proc', str(pid)).exists(), 'Proc identity read failed')
        current = None
    require(current is None or current['starttime'] == snap['starttime'], 'PID reused')
    require(not any(owner != pid for owner in owners()), 'Another DMA owner appeared')
    if current is None and not owners():
        break
    time.sleep(.2)
else:
    raise RuntimeError('Calibration graceful close timed out')
env = dict(snap['environment'], CAMVIEW_MOTION='1', DISPLAY=':0', XAUTHORITY='/var/run/lightdm/root/:0')
log = '/userdata/linaro/100h_performance/camview_' + TOKEN + '.log'
with open(log, 'xb') as output:
    child = subprocess.Popen([exe], cwd=str(Path(exe).parent), env=env,
        stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
time.sleep(5)
require(child.poll() is None, 'Camview exited; inspect ' + log)
shown = process(child.pid)
require(shown['exe_sha256'] == sha(exe), 'Camview running identity differs')
require(owners() == [child.pid], 'Camview not sole DMA owner')
require(windows(child.pid, env), 'Camview visible window missing')
print(json.dumps({'status':'shown', 'pid':child.pid, 'starttime':shown['starttime'],
    'exe':exe, 'sha256':shown['exe_sha256'], 'log':log, 'calibration_snapshot':saved,
    'calibration_pid':pid, 'calibration_starttime':snap['starttime']}), flush=True)
'''
script = REMOTE_SOURCE.split("if __name__ == '__main__':", 1)[0] + '\nTOKEN = ' + repr(token) + '\n' + extension
client = ssh_connect()
try:
    inp, out, err = client.exec_command("sudo -S -p '' python3 -c " + shlex.quote(script), timeout=60)
    inp.write('123456\n'); inp.flush(); inp.channel.shutdown_write()
    text = out.read().decode(errors='replace')
    error = err.read().decode(errors='replace')
    code = out.channel.recv_exit_status()
    receipt = {'output': text, 'error': error, 'exit_code': code}
    path = ROOT / 'log/100h_motion' / ('show_camview_' + token + '.json')
    path.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(text); print('Receipt:', path)
    if code:
        raise RuntimeError(error)
finally:
    client.close()
