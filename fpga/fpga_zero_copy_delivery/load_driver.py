"""Controlled driver swap; no FPGA reprogramming. Keep a matching rollback file."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh

root=Path(__file__).resolve().parent
manifest=json.loads((root/'driver_build_manifest.json').read_text())
expected=manifest['modules']['pango_zc.ko']
original='/userdata/linaro/projects/fpga/RK3568/driver/pango_pci_driver_fixed_20260926.ko'
candidate='/userdata/linaro/fpga-zero-copy-driver-stage/pango_zc.ko'
client=board_ssh.connect()
receipt=[]
def run(command):
    rc,out,err=board_ssh.run(client,command,sudo=True,timeout=30)
    receipt.append({'command':command,'rc':rc,'out':out,'err':err})
    (root/'driver_swap.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    return rc,out,err
try:
    rc,out,err=run('sha256sum '+original+' '+candidate)
    if rc or expected not in out or '0244c739f9758e0ab3296d14b72befbcf23050c7c02a97299531dfa514ce2861' not in out:
        raise RuntimeError('Driver identity mismatch')
    rc,out,err=run('pkill -x detview-hdmiful; sleep 1; fuser /dev/pango_pci_driver')
    if out.strip() or 'pango_pci_driver:' in err:
        raise RuntimeError('Driver still owned')
    rc,out,err=run('rmmod pango_pci_driver')
    if rc:
        raise RuntimeError('Old driver could not unload: '+out+err)
    rc,out,err=run('insmod '+candidate)
    if rc:
        rollback_rc,rollback_out,rollback_err=run('insmod '+original)
        raise RuntimeError('Candidate load failed; rollback rc='+str(rollback_rc)+': '+out+err+rollback_out+rollback_err)
    rc,out,err=run('readlink /sys/bus/pci/devices/0002:21:00.0/driver; ls -l /dev/pango_pci_driver; cat /proc/modules; dmesg | tail -n 15')
    print(out+err)
    if rc or '/pango_zc' not in out:
        raise RuntimeError('Candidate module did not bind')
    print('Shared driver bound. Viewer stopped for exclusive smoke test.')
finally:
    client.close()
