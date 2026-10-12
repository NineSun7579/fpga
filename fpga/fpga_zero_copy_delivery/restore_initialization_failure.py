"""Recover this proven pre-DMA failure only; not a generic timeout recovery."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh
client=board_ssh.connect()
root=Path(__file__).resolve().parent
try:
    rc,out,err=board_ssh.run(client,'cat /proc/7004/maps',sudo=True)
    if rc or '/dev/pango' in out:
        raise RuntimeError('Pre-DMA recovery proof no longer holds')
    command=('kill -KILL 7004; sleep 1; rmmod pango_zc && '
        'insmod /userdata/linaro/projects/fpga/RK3568/driver/pango_pci_driver_fixed_20260926.ko && '
        'cd /userdata/detview-hdmifull && setsid nohup env DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 '
        'QT_QPA_PLATFORM=xcb QT_XCB_GL_INTEGRATION=xcb_egl DET_BENCH=1 '
        './detview-hdmifull --model MVP_accuracy_round1 --fullscreen '
        '>/userdata/linaro/display-latency-delivery/final_acceptance.log 2>&1 </dev/null &')
    rc,out,err=board_ssh.run(client,command,sudo=True,timeout=20)
    (root/'initialization_recovery.log').write_text(out+err,encoding='utf-8')
    print(rc,out,err)
finally:
    client.close()
