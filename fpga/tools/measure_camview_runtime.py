"""Measure existing viewer without rebuilding or changing desktop settings."""
from pathlib import Path
import re
import shlex
import sys
import time
from board_host import ssh_connect

label = sys.argv[1]
assert label.isalnum()
root = Path(__file__).resolve().parents[2]
out = root / 'log/camview_fps_audit_20261003'
c = ssh_connect(timeout=8)
def run(command):
    s,o,e=c.exec_command('sudo -S sh -c '+shlex.quote(command),timeout=20)
    s.write('123456\n');s.flush()
    data,err=o.read(),e.read()
    if o.channel.recv_exit_status(): raise RuntimeError(err.decode(errors='replace'))
    return data
try:
    count=int(run('wc -l < /root/ov5640/camview_fps_candidate.log'))
    time.sleep(35)
    data=run('tail -n +%d /root/ov5640/camview_fps_candidate.log' % (count+1))
    (out / (label+'_runtime.txt')).write_bytes(data)
    text=data.decode(errors='replace')
    uploads=[float(x) for x in re.findall(r'uploaded_fps=([\d.]+)',text)]
    if not uploads or max(uploads)<=0:
        raise RuntimeError('Invalid measurement: no active viewer upload windows; check DMA ownership and viewer lifetime')
    for pattern in ['uploaded_fps=([\\d.]+)','paint_ms=([\\d.]+)','camera_upload_ms=([\\d.]+)',
                    'camera_draw_ms=([\\d.]+)','setup_ms=([\\d.]+)','hud_ms=([\\d.]+)']:
        values=[float(x) for x in re.findall(pattern,text)]
        print(pattern, sum(values)/len(values) if values else None)
finally:
    c.close()
