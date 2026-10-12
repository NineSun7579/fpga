from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import board_ssh

root = Path(__file__).resolve().parent
client = board_ssh.connect()
try:
    remote = '/tmp/fpga-zero-copy-probe'
    rc, out, err = board_ssh.run(client, 'mkdir -p ' + remote)
    if rc:
        raise RuntimeError(out + err)
    with client.open_sftp() as sftp:
        sftp.put(str(root / 'host/probe_shared_input.cpp'), remote + '/probe.cpp')
        sftp.put(str(root.parent / 'display_latency_delivery/src/rknn_api.h'), remote + '/rknn_api.h')
    rc, out, err = board_ssh.run(client,
        'cd ' + remote + '; g++ -std=c++17 -O2 -Wall -Wextra probe.cpp -lrknnrt -o probe', timeout=60)
    (root / 'probe_build.log').write_text(out + err, encoding='utf-8')
    if rc:
        raise RuntimeError(out + err)
    rc, out, err = board_ssh.run(client,
        remote + '/probe /root/npu/whiteboard_3cls/det-yolov8n-3cls-wb_v8_w25_nop2c2f-rk3568-raw-dfl6-int8.rknn',
        sudo=True, timeout=30)
    (root / 'probe_shared_input.log').write_text(out + err, encoding='utf-8')
    print('return_code=', rc)
    print(out + err)
finally:
    client.close()
