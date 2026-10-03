"""Capture full raw frames/diagnostics with viewer paused; restore candidate."""
from pathlib import Path
import shlex
from board_host import ssh_connect

root = Path(__file__).resolve().parents[2]
out = root / 'log/camview_fps_audit_20261003/raw_recheck'
out.mkdir(exist_ok=True)
c = ssh_connect(timeout=8)
def run(command, timeout=30):
    s, o, e = c.exec_command('sudo -S sh -c ' + shlex.quote(command), timeout=timeout)
    s.write('123456\n'); s.flush()
    data, errors = o.read(), e.read()
    if o.channel.recv_exit_status():
        raise RuntimeError((data + errors).decode('utf8', 'replace'))
    return data
try:
    sf = c.open_sftp()
    sf.put(str(root / 'project/tools/accept_six_streams.py'), '/tmp/accept_six_streams.py')
    sf.close()
    run('pkill -x camview || true')
    data = run('timeout 45 python3 /tmp/accept_six_streams.py --seconds 20 --diagnostics '
               '--output /tmp/fps_raw_recheck', 50)
    (out / 'board.jsonl').write_bytes(data)
    sf = c.open_sftp()
    for name in sf.listdir('/tmp/fps_raw_recheck'):
        sf.get('/tmp/fps_raw_recheck/' + name, str(out / name))
    sf.close()
    print((out / 'report.json').read_text())
finally:
    run('cd /root/ov5640/camview_fps_candidate && '
        'DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 '
        'nohup ./camview > /root/ov5640/camview_fps_candidate.log 2>&1 < /dev/null &')
    c.close()
