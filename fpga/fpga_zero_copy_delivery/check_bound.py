from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import board_ssh

root = Path(__file__).resolve().parent
client = board_ssh.connect()
try:
    rc, out, err = board_ssh.run(client, 'mkdir -p /tmp/fpga-zero-copy-probe/cooperative_linux_transport')
    if rc:
        raise RuntimeError(out + err)
    with client.open_sftp() as sftp:
        for name in ('bound_rknn.hpp', 'pcie_session.hpp', 'check_bound.cpp'):
            sftp.put(str(root / 'host' / name), '/tmp/fpga-zero-copy-probe/' + name)
        sftp.put('D:/race/ov56401/project/fpga_v8_migration/cooperative_linux_transport/driver_abi.hpp',
                 '/tmp/fpga-zero-copy-probe/cooperative_linux_transport/driver_abi.hpp')
    rc, out, err = board_ssh.run(client,
        'cd /tmp/fpga-zero-copy-probe; g++ -std=c++17 -Wall -Wextra -fsyntax-only check_bound.cpp', timeout=30)
    (root / 'bound_runner_compile.log').write_text(out + err, encoding='utf-8')
    print('return_code', rc, out, err)
    if rc:
        raise SystemExit(rc)
finally:
    client.close()
