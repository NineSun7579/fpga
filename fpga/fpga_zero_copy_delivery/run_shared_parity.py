from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import board_ssh

root = Path(__file__).resolve().parent
client = board_ssh.connect()
try:
    remote = '/tmp/fpga-zero-copy-probe'
    with client.open_sftp() as sftp:
        sftp.put(str(root / 'host/shared_input_parity.cpp'), remote + '/shared_input_parity.cpp')
    rc, out, err = board_ssh.run(client,
        'cd ' + remote + '; g++ -std=c++17 -O2 -Wall -Wextra shared_input_parity.cpp -lrknnrt -o shared_input_parity', timeout=60)
    (root / 'shared_parity_build.log').write_text(out + err, encoding='utf-8')
    if rc:
        raise RuntimeError(out + err)
    receipts = []
    for offset in (0, 2*1024*1024, 2*1024*1024 + 80*640*3):
        rc, out, err = board_ssh.run(client,
            remote + '/shared_input_parity /root/npu/whiteboard_3cls/det-yolov8n-3cls-wb_v8_w25_nop2c2f-rk3568-raw-dfl6-int8.rknn '
            '/userdata/linaro/fpga_accel_delivery/mismatch.cpu.rgb ' + str(offset), sudo=True, timeout=45)
        receipts.append(out + err)
        (root / 'shared_input_parity.log').write_text(''.join(receipts), encoding='utf-8')
        print('return_code=', rc)
        print(out + err)
        if rc:
            raise SystemExit(rc)
finally:
    client.close()
