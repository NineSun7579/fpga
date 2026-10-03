"""Build and measure a reversible RK3568 viewer candidate, one DMA owner."""
import shlex
import time
import sys
import re
from pathlib import Path
from board_host import ssh_connect

root = Path(__file__).resolve().parents[2]
out = root / 'log/camview_fps_audit_20261003'
out.mkdir(exist_ok=True)
c = ssh_connect(timeout=8)
suffix = sys.argv[1] if len(sys.argv) > 1 else 'candidate'
if not suffix.isalnum():
    raise ValueError('invalid label')
def run(command, timeout=30):
    stdin, stdout, stderr = c.exec_command('sudo -S sh -c ' + shlex.quote(command), timeout=timeout)
    stdin.write('123456\n'); stdin.flush()
    data, error = stdout.read(), stderr.read()
    status = stdout.channel.recv_exit_status()
    if status:
        raise RuntimeError((data + error).decode('utf8', 'replace'))
    return data

compositor_command = None
compositor_original = None

try:
    if suffix in ('compositor', 'direct'):
        code = ("from pathlib import Path; import subprocess; "
                "pid=subprocess.check_output(['pgrep','-u','linaro','-x','xfwm4']).decode().strip(); "
                "print(next(x.split(b'=',1)[1].decode() for x in Path('/proc/'+pid+'/environ').read_bytes().split(bytes([0])) "
                "if x.startswith(b'DBUS_SESSION_BUS_ADDRESS=')))")
        bus = run('python3 -c ' + shlex.quote(code)).decode().strip()
        compositor_command = ('sudo -u linaro env DBUS_SESSION_BUS_ADDRESS=' + shlex.quote(bus) +
                              ' xfconf-query -c xfwm4 -p /general/use_compositing')
        compositor_original = run(compositor_command).decode().strip()
        if compositor_original not in ('true', 'false'):
            raise RuntimeError('unknown compositor setting')
        (out / 'compositor_original.txt').write_text(compositor_original)
        run(compositor_command + ' -s false')
    if not (out / 'baseline_runtime.txt').exists():
        (out / 'baseline_runtime.txt').write_bytes(run(
            'tail -60 /root/ov5640/camview_final.log; ps -eo pid,pcpu,args | grep "[.]/camview"'))
    sftp = c.open_sftp()
    sftp.put(str(root / 'project/host/camview/main.cpp'), '/tmp/camview_fps_candidate.cpp')
    sftp.put(str(root / 'project/host/camview/dma_copy.h'), '/tmp/camview_dma_copy.h')
    sftp.close()
    (out / (suffix + '_build.log')).write_bytes(run(
        'mkdir -p /root/ov5640/camview_fps_candidate; '
        'cp /root/ov5640/camview/camview.pro /root/ov5640/camview_fps_candidate/; '
        'cp /tmp/camview_fps_candidate.cpp /root/ov5640/camview_fps_candidate/main.cpp; '
        'cp /tmp/camview_dma_copy.h /root/ov5640/camview_fps_candidate/dma_copy.h; '
        'cd /root/ov5640/camview_fps_candidate && qmake && make -j4', 60))
    run('pkill -f "^/bin/bash /root/ov5640/run_camview.sh" || true; pkill -x camview || true')
    run('nohup sh -c ' + shlex.quote('cd /root/ov5640/camview_fps_candidate && '
        'DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 '
        + ('CAMVIEW_NOHUD=1 ' if suffix == 'nohud' else
           'CAMVIEW_SWAP_INTERVAL=0 CAMVIEW_MIN_MS=16 ' if suffix in ('noswap', 'direct') else
           'QT_QPA_UPDATE_IDLE_TIME=0 CAMVIEW_MIN_MS=16 ' if suffix in ('pipeline', 'bypass') else '') +
        'exec ./camview') + ' > /root/ov5640/camview_fps_candidate.log 2>&1 < /dev/null &')
    if suffix == 'bypass':
        time.sleep(2)
        tree = run('DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 xwininfo -root -tree').decode()
        match = re.search(r'(0x[0-9a-f]+) "camview  QUAD THREAD VIEW"', tree)
        if not match:
            raise RuntimeError('viewer window not found')
        run('DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 xprop -id ' + match.group(1) +
            ' -f _NET_WM_BYPASS_COMPOSITOR 32c -set _NET_WM_BYPASS_COMPOSITOR 1')
    time.sleep(35)
    data = run('cat /root/ov5640/camview_fps_candidate.log; '
               'ps -eo pid,pcpu,args | grep "[.]/camview"')
    (out / (suffix + '_runtime.txt')).write_bytes(data)
    print(data.decode('utf8', 'replace')[-16000:])
except Exception:
    run('pkill -x camview || true; nohup /bin/bash /root/ov5640/run_camview.sh '
        '> /root/ov5640/camview_final.log 2>&1 < /dev/null &')
    raise
finally:
    if compositor_command and compositor_original in ('true', 'false'):
        run(compositor_command + ' -s ' + compositor_original)
    c.close()
