"""Stage and build real RK3568 comparison tools; no PCIe device open."""
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import board_ssh

root=Path(__file__).resolve().parent
remote='/userdata/linaro/fpga-zero-copy-host'
client=board_ssh.connect()
try:
    rc,out,err=board_ssh.run(client,'mkdir -p '+remote+'/cooperative_linux_transport')
    if rc:
        raise RuntimeError(out+err)
    with client.open_sftp() as sftp:
        for source in (root/'host').iterdir():
            if source.suffix in ('.cpp','.hpp'):
                sftp.put(str(source),remote+'/'+source.name)
        sftp.put(str(root.parent/'display_latency_delivery/src/rknn_api.h'),remote+'/rknn_api.h')
        sftp.put(str(root/'driver/pango_zc_uapi.h'),remote+'/pango_zc_uapi.h')
        sftp.put('D:/race/ov56401/project/fpga_v8_migration/cooperative_linux_transport/driver_abi.hpp',
                 remote+'/cooperative_linux_transport/driver_abi.hpp')
    rc,out,err=board_ssh.run(client,'cd '+remote+'; g++ -std=c++17 -O2 -Wall -Wextra -Werror paired_pointer.cpp -lrknnrt -pthread -o paired_pointer',timeout=90)
    (root/'host_build.log').write_text(out+err,encoding='utf-8')
    print('return_code',rc,out,err)
    if rc:
        raise SystemExit(rc)
    rc,out,err=board_ssh.run(client,'cd '+remote+'; g++ -std=c++17 -O2 -Wall -Wextra -Werror thumbnail_parity.cpp -lrknnrt -pthread -o thumbnail_parity',timeout=90)
    (root/'thumbnail_host_build.log').write_text(out+err,encoding='utf-8')
    print('thumbnail_return_code',rc,out,err)
    if rc:
        raise SystemExit(rc)
    rc,out,err=board_ssh.run(client,'cd '+remote+'; g++ -std=c++17 -O2 -Wall -Wextra -Werror -DOFFLOAD_SHARED_INPUT paired_pointer.cpp -lrknnrt -pthread -o paired_shared',timeout=90)
    (root/'shared_host_build.log').write_text(out+err,encoding='utf-8')
    print('shared_return_code',rc,out,err)
    if rc:
        raise SystemExit(rc)
finally:
    client.close()
