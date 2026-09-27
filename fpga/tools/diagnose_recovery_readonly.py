"""Read-only FPGA register survey; no programming or SCCB transactions."""
import json, shlex, sys
from pathlib import Path
import paramiko

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tp/recovery_readonly_diag'
OUT.mkdir(parents=True, exist_ok=True)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.10.241', username='linaro', password='123456', allow_agent=False, look_for_keys=False, timeout=15)
def sh(cmd):
    i,o,e = c.exec_command('sudo -S -p "" bash -c '+shlex.quote(cmd), timeout=90)
    i.write('123456\n'); i.flush()
    text = o.read().decode(errors='replace') + e.read().decode(errors='replace')
    with (OUT/'session.log').open('a',encoding='utf-8') as f: f.write(cmd+'\n'+text+'\n')
    print(text, flush=True)
    if o.channel.recv_exit_status(): raise RuntimeError(cmd)
probe = '''import sys,time,json
sys.path.insert(0,'/tmp')
from cam3_i2c_pt import PciDriver
d=PciDriver()
rows=[]
try:
 for n in range(21):
  row={'t':time.monotonic(),'cams':[]}
  for base in (0x20000000,0x20000200,0x20000400):
   row['cams'].append({hex(x):d.read32(base+x) for x in range(0,256,16)})
  rows.append(row)
  time.sleep(0.25)
finally:d.close()
open('/tmp/recovery_readonly.json','w').write(json.dumps(rows,indent=2))
print(json.dumps(rows))
'''
try:
    sh('pkill -9 -x run_camview.sh || true')
    sh('pkill -9 -x camview || true')
    sh('rmmod pango_pci_driver; insmod /root/ov5640/pango_pci_driver.ko')
    s=c.open_sftp()
    s.put(str(ROOT/'tools/cam3_i2c_pt.py'),'/tmp/cam3_i2c_pt.py')
    with s.open('/tmp/recovery_readonly_probe.py','w') as f: f.write(probe)
    sh('python3 -u /tmp/recovery_readonly_probe.py')
    s.get('/tmp/recovery_readonly.json',str(OUT/'registers.json'))
    s.close()
finally:
    try:
        sh('rmmod pango_pci_driver; insmod /root/ov5640/pango_pci_driver.ko; test -L /sys/bus/pci/devices/0002:21:00.0/driver')
        sh('rm -f /tmp/camview.lock; setsid nohup /root/ov5640/run_camview.sh > /tmp/camview.log 2>&1 < /dev/null &')
        sh('sleep 10; pgrep -a -x camview; pgrep -a -x run_camview.sh')
    finally: c.close()
