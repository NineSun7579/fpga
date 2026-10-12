"""Capture live baseline without opening or stopping the PCIe driver."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import board_ssh

root = Path(__file__).resolve().parent
client = board_ssh.connect()
try:
    rc, out, err = board_ssh.run(client, 'pgrep -x detview-hdmiful', sudo=True)
    if rc or len(out.split()) != 1:
        raise RuntimeError('Expected one running full viewer: ' + out + err)
    pid = int(out.strip())
    with client.open_sftp() as sftp:
        sftp.put(str(root / 'sample_host.py'), '/tmp/fpga_offload_sample_host.py')
    rc, out, err = board_ssh.run(client,
        'python3 /tmp/fpga_offload_sample_host.py --pid ' + str(pid) + ' --seconds 60', sudo=True, timeout=90)
    if rc:
        raise RuntimeError(out + err)
    (root / 'host_baseline.json').write_text(out, encoding='utf-8')
    rc, out, err = board_ssh.run(client,
        'tail -n 350 /userdata/linaro/display-latency-delivery/final_acceptance.log', sudo=True)
    (root / 'host_baseline_viewer.log').write_text(out, encoding='utf-8')
    print('Baseline captured for PID ' + str(pid) + '; full viewer/NPU left running.')
finally:
    client.close()
