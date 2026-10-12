"""Preserve viewer memory while stopping user submissions before full recovery."""
from pathlib import Path
import sys,json,hashlib
from datetime import datetime,timezone
H=Path(__file__).resolve().parent
sys.path.insert(0,str(H.parents[3]/'tools'))
from board_host import ssh_connect,board_host
REMOTE=r'''sudo -n python3 - <<'PY'
import os,signal,json,hashlib,subprocess,time
from pathlib import Path
from datetime import datetime,timezone
def utc():return datetime.now(timezone.utc).isoformat()
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert boot=='dd39b8d1-cf2d-404e-914d-45eb87278794','Unexpected boot; stop before process control'
pid=14889;p=Path('/proc')/str(pid)
argv=(p/'cmdline').read_bytes().split(b'\0');argv=[v.decode('utf8') for v in argv if v]
expected=['/userdata/detview-driving-demo/detview-driving-demo','--driving-demo','--fullscreen','--no-tracking','--rotate-model','trafficlight-16cls,wb_v4_combo']
assert argv==expected,('Unexpected viewer argv',pid)
exe=os.readlink(p/'exe')
assert exe==expected[0]
assert hashlib.sha256(Path(exe).read_bytes()).hexdigest()=='72cd352aba95fce2a9897fb3fefe7214940b080d3937a2c8bad8afa72f25a703'
before=(p/'stat').read_text()
starttime=before.rsplit(')',1)[1].split()[19]
def pci_read():
 r=subprocess.run(['setpci','-s','0002:21:00.0','COMMAND'],capture_output=True,text=True,timeout=10)
 assert r.returncode==0 and len(r.stdout.strip())==4 and int(r.stdout.strip(),16)&4==0,'BME must remain disabled'
 return {'stdout':r.stdout,'stderr':r.stderr,'returncode':r.returncode}
command_before=pci_read()
# SIGSTOP preserves descriptors and mappings; no release/idle assertion.
started=utc();os.kill(pid,signal.SIGSTOP)
for attempt in range(100):
 state=(p/'stat').read_text();parts=state.rsplit(')',1)[1].split()
 assert parts[19]==starttime,'PID identity changed'
 if parts[0] in {'T','t'}:break
 time.sleep(.02)
else:raise RuntimeError('Viewer did not enter stopped state')
command_after=pci_read()
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==boot
print(json.dumps({'status':'VIEWER_STOPPED_MEMORY_PRESERVED','boot_id':boot,'pid':pid,'argv':argv,'exe':exe,
 'starttime_ticks':starttime,'started_utc':started,'ended_utc':utc(),'before_stat':before,'after_stat':state,
 'command_before':command_before,'command_after':command_after,'signal':'SIGSTOP',
 'scope':'Freeze this exact viewer process until full SRAM recovery/session rebuild; BME disabled at both boundaries',
 'dma_opened':False,'dma_submitted':False,'pci_config_written':False,'reset_executed':False,
 'dma_idle_proven':False,'global_admission_STOP_proven':False,'accepted':False},indent=2))
PY
'''
def main():
    assert board_host()=='192.168.10.203'
    assert not (H/'action.receipt.json').exists()
    (H/'action.command.txt').write_text(REMOTE,encoding='utf8')
    started=datetime.now(timezone.utc).isoformat();client=ssh_connect()
    try:
        _,out,err=client.exec_command(REMOTE,timeout=30)
        raw=out.read();error=err.read();rc=out.channel.recv_exit_status()
    finally:client.close()
    (H/'action.stdout.json').write_bytes(raw);(H/'action.stderr.txt').write_bytes(error)
    receipt={'started_utc':started,'ended_utc':datetime.now(timezone.utc).isoformat(),'exit_code':rc,
             'command_sha256':hashlib.sha256(REMOTE.encode()).hexdigest(),
             'stdout_sha256':hashlib.sha256(raw).hexdigest(),'stderr_sha256':hashlib.sha256(error).hexdigest(),
             'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'accepted':False}
    (H/'action.receipt.json').write_text(json.dumps(receipt,indent=2),encoding='ascii')
    assert rc==0,error.decode('utf8',errors='replace')
    result=json.loads(raw);assert result['status']=='VIEWER_STOPPED_MEMORY_PRESERVED'
    print(json.dumps({'status':result['status'],'pid':result['pid'],'boot_id':result['boot_id'],'accepted':False}))
if __name__=='__main__':main()
