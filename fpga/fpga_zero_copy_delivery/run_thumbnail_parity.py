"""Actual frozen RAW versus FPGA thumbnail byte check; requires programmed image."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh

root=Path(__file__).resolve().parent
client=board_ssh.connect()
try:
    rc,out,err=board_ssh.run(client,'pkill -x detview-hdmiful; sleep 1; fuser /dev/pango_pci_driver',sudo=True)
    if out.strip() or 'pango_pci_driver:' in err:
        raise RuntimeError('Device still owned')
    remote='/userdata/linaro/fpga-zero-copy-host/thumbnail_parity'
    try:
        rc,out,err=board_ssh.run(client,remote+' >'+remote+'.jsonl 2>'+remote+'.stderr',sudo=True,timeout=60)
    finally:
        with client.open_sftp() as sftp:
            for suffix in ('.jsonl','.stderr'):
                sftp.get(remote+suffix,str(root/('thumbnail_parity'+suffix)))
    if rc:
        raise RuntimeError('Hardware thumbnail check failed; preserve uncertain owner: '+(root/'thumbnail_parity.stderr').read_text())
    rows=[json.loads(line) for line in (root/'thumbnail_parity.jsonl').read_text().splitlines()]
    if len(rows)!=10 or not all(row['pass'] and row['bytes_compared']==153600 for row in rows):
        raise RuntimeError('Missing pixel parity evidence')
    command=('cd /userdata/detview-hdmifull; setsid nohup env DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 '
        'QT_QPA_PLATFORM=xcb QT_XCB_GL_INTEGRATION=xcb_egl DET_BENCH=1 '
        './detview-hdmifull --model MVP_accuracy_round1 --fullscreen '
        '>/userdata/linaro/display-latency-delivery/final_acceptance.log 2>&1 </dev/null & echo $!')
    rc,out,err=board_ssh.run(client,command,sudo=True)
    if rc:
        raise RuntimeError(out+err)
    report={'frames':10,'bytes_compared':1536000,'all_pixels_equal':True,'restored_viewer_pid':out.strip(),
            'mean_thumbnail_delivery_ms':sum(row['thumbnail_delivery_ms'] for row in rows)/len(rows)}
    (root/'thumbnail_parity_summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
finally:
    client.close()
