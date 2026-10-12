"""Pause viewer for a single-owner DMA audit, then restore tested candidate."""
from pathlib import Path
import shlex
import sys
from board_host import ssh_connect

root = Path(__file__).resolve().parents[2]
c = ssh_connect(timeout=8)
def run(command, timeout=30):
    s, o, e = c.exec_command('sudo -S sh -c ' + shlex.quote(command), timeout=timeout)
    s.write('123456\n'); s.flush()
    data, error = o.read(), e.read()
    if o.channel.recv_exit_status():
        raise RuntimeError((data + error).decode('utf8', 'replace'))
    return data
try:
    sf = c.open_sftp()
    for name in ['cam3_i2c_pt.py', 'benchmark_dma_capacity_board.py']:
        sf.put(str(root / 'project/tools' / name), '/tmp/' + name)
    if len(sys.argv) > 1 and sys.argv[1] == 'copy':
        for name in ['benchmark_dma_copy.cpp', 'dma_copy.h']:
            sf.put(str(root / 'project/host/camview' / name), '/tmp/' + name)
    sf.close()
    run('pkill -x camview || true')
    copy_test = len(sys.argv) > 1 and sys.argv[1] == 'copy'
    data = run('g++ -O2 -std=c++11 /tmp/benchmark_dma_copy.cpp -o /tmp/benchmark_dma_copy && '
               'timeout 20 /tmp/benchmark_dma_copy' if copy_test else
               'python3 /tmp/benchmark_dma_capacity_board.py', 45)
    (root / ('log/camview_fps_audit_20261003/dma_copy.txt' if copy_test else
             'log/camview_fps_audit_20261003/dma_capacity.json')).write_bytes(data)
    print(data.decode())
finally:
    run('cd /root/ov5640/camview_fps_candidate && '
        'DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 '
        'nohup ./camview > /root/ov5640/camview_fps_candidate.log 2>&1 < /dev/null &')
    c.close()
