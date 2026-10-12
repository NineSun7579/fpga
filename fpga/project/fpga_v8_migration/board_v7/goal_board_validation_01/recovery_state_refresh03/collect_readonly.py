"""SSH-only state refresh; no device opens, config writes, DMA or process control."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[3] / 'tools'
sys.path.insert(0, str(TOOLS))
from board_host import ssh_connect, board_host

def utc():
    return datetime.now(timezone.utc).isoformat()

def digest(data):
    return hashlib.sha256(data).hexdigest()

COMMANDS = {
'identity': """cat /proc/sys/kernel/random/boot_id
date -u +%Y-%m-%dT%H:%M:%SZ
uname -r
cat /proc/uptime
cat /proc/modules
cat /sys/module/pango_pci_driver/initstate
sha256sum /userdata/linaro/projects/fpga/RK3568/driver/pango_pci_driver_fixed_20260926.ko
od -An -tx1 /sys/module/pango_pci_driver/notes/.note.gnu.build-id
readelf -n /userdata/linaro/projects/fpga/RK3568/driver/pango_pci_driver_fixed_20260926.ko
""",
'pci': r"""python3 - <<'PY'
from pathlib import Path
import subprocess,json,datetime
root=Path('/sys/bus/pci/devices'); eps=[]
for dev in root.iterdir():
 try:
  if dev.joinpath('vendor').read_text().strip()=='0x0755' and dev.joinpath('device').read_text().strip()=='0x0755':eps.append(dev)
 except OSError:pass
result={'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'endpoints':[]}
for dev in eps:
 real=dev.resolve();parent=real.parent;bdf=parent.name
 rec={'endpoint':dev.name,'sysfs_realpath':str(real),'parent_bdf':bdf,'driver':str((dev/'driver').resolve()),'commands':{}}
 for key,args in [('parent_lspci',['sudo','-n','lspci','-s',bdf,'-nnvv']),('endpoint_lspci',['sudo','-n','lspci','-s',dev.name,'-nnvv']),('bridge_control',['sudo','-n','setpci','-s',bdf,'BRIDGE_CONTROL']),('parent_command',['sudo','-n','setpci','-s',bdf,'COMMAND']),('endpoint_command',['sudo','-n','setpci','-s',dev.name,'COMMAND'])]:
  start=datetime.datetime.now(datetime.timezone.utc).isoformat()
  proc=subprocess.run(args,capture_output=True,text=True,timeout=20)
  rec['commands'][key]={'argv':args,'started_utc':start,'ended_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'stdout':proc.stdout,'stderr':proc.stderr,'returncode':proc.returncode}
 result['endpoints'].append(rec)
print(json.dumps(result,indent=2))
PY
""",
'owners': r"""sudo -n python3 - <<'PY'
import os,stat,json,datetime
from pathlib import Path
device='/dev/pango_pci_driver'; errors=[]; owners=[]; viewers=[]
try: target=os.stat(device).st_rdev
except OSError as e: target=None;errors.append({'path':device,'error':type(e).__name__})
for proc in Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try:
  comm=(proc/'comm').read_text().strip()
  if any(s in comm.lower() for s in ('detview','camview','viewer')):
   viewers.append({'pid':int(proc.name),'comm':comm,'exe':os.readlink(proc/'exe'),'stat':(proc/'stat').read_text().strip()})
  for fd in (proc/'fd').iterdir():
   try:
    info=fd.stat()
    if target is not None and stat.S_ISCHR(info.st_mode) and info.st_rdev==target:
     owners.append({'pid':int(proc.name),'comm':comm,'fd':fd.name,'link':os.readlink(fd),'stat':(proc/'stat').read_text().strip()})
   except FileNotFoundError:pass
   except OSError as e:errors.append({'path':str(fd),'error':type(e).__name__})
 except FileNotFoundError:pass
 except OSError as e:errors.append({'path':str(proc),'error':type(e).__name__})
print(json.dumps({'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'captured_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'owners':owners,'viewers':viewers,'scan_errors':errors,'device_opened':False,'dma_idle_proven':False},indent=2))
PY
""",
'kernel_log': 'sudo -n dmesg\n',
'boot_after': 'cat /proc/sys/kernel/random/boot_id\ncat /proc/uptime\n',
}

def main():
    if any((HERE/(name+'.receipt.json')).exists() for name in COMMANDS):
        raise RuntimeError('Refusing to overwrite prior receipts')
    receipts=[]
    client=None
    start=utc()
    try:
        if board_host() != '192.168.10.203':
            raise RuntimeError('Existing host resolution does not match requested address')
        client=ssh_connect()
        for name, command in COMMANDS.items():
            raw_command=command.encode('utf-8')
            (HERE/(name+'.command.txt')).write_bytes(raw_command)
            begun=utc()
            _,out,err=client.exec_command(command,timeout=90)
            stdout=out.read();stderr=err.read();code=out.channel.recv_exit_status()
            (HERE/(name+'.stdout.txt')).write_bytes(stdout)
            (HERE/(name+'.stderr.txt')).write_bytes(stderr)
            receipt={'contract':'readonlySSHRefresh/v1','host':'192.168.10.203','started_utc':begun,'ended_utc':utc(),'exit_code':code,'command_sha256':digest(raw_command),'stdout_sha256':digest(stdout),'stderr_sha256':digest(stderr),'collector_sha256':digest(Path(__file__).read_bytes()),'device_opened':False,'dma_submitted':False,'pci_config_written':False,'sysfs_written':False,'gpio_written':False,'process_control':False,'reset_executed':False,'reboot_executed':False,'programming_executed':False,'pds_started':False,'dma_idle_proven':False,'accepted':False}
            (HERE/(name+'.receipt.json')).write_text(json.dumps(receipt,indent=2),encoding='utf-8')
            receipts.append(receipt)
        result={'status':'captured_pending_review','started_utc':start,'ended_utc':utc(),'commands_completed':len(receipts),'accepted':False,'dma_idle_proven':False}
    except Exception as e:
        result={'status':'blocked_or_partial','started_utc':start,'ended_utc':utc(),'commands_completed':len(receipts),'blocker_type':type(e).__name__,'accepted':False,'dma_idle_proven':False}
    finally:
        if client is not None:client.close()
    (HERE/'session.receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__':main()
