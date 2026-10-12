"""Authorized serial actual functional delivery. No V7 fallback, flash, or GPIO."""
import sys, os, json, time, ctypes, subprocess, importlib.util, shlex, traceback
from pathlib import Path
from types import SimpleNamespace
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
BUILD = GOAL.parent / 'build04_functional_route04'
TOOLS = GOAL.parents[2] / 'tools'
def module(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
c = module('actual06_delivery10', GOAL / 'recovery_execution_actual06/controller.py')
checker = module('check09_delivery10', GOAL / 'check_functional_bit09.py')
vendor = module('vendor_delivery10', TOOLS / 'program_100h_motion.py')
summary = module('summary09_delivery10', GOAL / 'summarize_camera_log09.py')
ELF = '/userdata/detview-driving-demo/detview-driving-demo'
ELFSHA = '72cd352aba95fce2a9897fb3fefe7214940b080d3937a2c8bad8afa72f25a703'
SNAP = (GOAL / 'reboot_then_program_pcie_trial07/capture_remote.py').read_text()
BOOT = None
def save(name, value): c.save(HERE / name, value)
def remote(name, source, boot=True):
    prefix = 'from pathlib import Path\n'
    if boot and BOOT:
        prefix += 'assert Path("/proc/sys/kernel/random/boot_id").read_text().strip() == ' + repr(BOOT) + '\n'
    cmd = "sudo -n python3 -u - <<'DELIVERY10'\n" + prefix + source + '\nDELIVERY10\n'
    cli = c.connect()
    try: return c.record(HERE, name, cmd, c.transport(cli))
    finally: cli.close()
def snapshot(name):
    obj = json.loads(remote(name, SNAP))
    assert obj['admission_sha256'] == ELFSHA
    assert not obj['scan_errors'] and not obj['holders'], 'Actual device owners or incomplete scan'
    assert not any(p['exe'] == ELF for p in obj['processes']), 'Unexpected producer; no signals'
    return obj
def wait_controller():
    query = 'Get-CimInstance Win32_Process -Filter "ProcessId=44500" | Select-Object ProcessId,ParentProcessId,ExecutablePath,CommandLine,CreationDate | ConvertTo-Json -Compress'
    p = subprocess.run(['powershell', '-NoProfile', '-Command', query], capture_output=True, check=True)
    (HERE / 'controller_identity.stdout.json').write_bytes(p.stdout)
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_bool, ctypes.c_ulong]; k.OpenProcess.restype = ctypes.c_void_p
    k.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]; k.WaitForSingleObject.restype = ctypes.c_ulong
    k.CloseHandle.argtypes = [ctypes.c_void_p]
    k.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    if not p.stdout.strip():
        assert (BUILD / 'BIT_MANIFEST.json').exists(), 'Controller exited without new bit manifest'
        save('controller_wait.json', {'utc': c.utc(), 'already_exited': True}); return
    ident = json.loads(p.stdout)
    expected = str(BUILD / 'controller.py')
    assert expected.lower() in ident['CommandLine'].lower() and ident['CommandLine'].rstrip().endswith('diagnostic02')
    assert Path(ident['ExecutablePath']).resolve() == Path(sys.executable).resolve()
    h = k.OpenProcess(0x100000 | 0x1000, False, 44500)
    assert h, 'Exact controller process handle unavailable'
    # Reconfirm creation identity after opening the handle to exclude PID recycling.
    p2 = subprocess.run(['powershell', '-NoProfile', '-Command', query], capture_output=True, check=True)
    assert json.loads(p2.stdout) == ident, 'Controller identity changed while acquiring handle'
    start = c.utc()
    try:
        while True:
            rc = k.WaitForSingleObject(h, 60000)
            if rc == 0: break
            assert rc == 258, 'Controller handle wait failed'
            print(c.utc(), 'Waiting on exact controller process handle; no build polling', flush=True)
        code = ctypes.c_ulong(); assert k.GetExitCodeProcess(h, ctypes.byref(code))
        save('controller_wait.json', {'started_utc': start, 'ended_utc': c.utc(), 'identity': ident, 'exit_code': code.value})
        assert code.value == 0, 'Actual controller failed; no SRAM fallback'
    finally: k.CloseHandle(h)
def ledger_mode(name, mode):
    return remote(name, '''import os,stat,hashlib,json
p=Path(%r); ledger=Path('/var/lib/fpga-recovery-actual06/admission.json')
assert ledger.stat().st_uid==0 and not ledger.stat().st_mode & 0o077
rows=json.loads(ledger.read_text()); assert len(rows)==1
r=rows[0]; assert r['path']==str(p) and r['sha256']==%r and r['original_mode']==0o755
assert not p.is_symlink() and hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256']
os.chmod(p,%d)
assert stat.S_IMODE(p.stat().st_mode)==%d
print(json.dumps(dict(mode=oct(%d),ledger=rows,sha256=r['sha256'],ledger_retained=True)))
''' % (ELF, ELFSHA, mode, mode, mode))
def clear_bme(state):
    eps = [p for p in state['pci'] if p['attributes']['vendor']=='0x0755' and p['attributes']['device']=='0x0755']
    assert len(eps) <= 1
    if eps:
        remote('bme_clear_before_reboot', '''import subprocess,json
bdf=%r
def rd():
 r=subprocess.run(['setpci','-s',bdf,'COMMAND'],capture_output=True,text=True);print(r.returncode,r.stdout,r.stderr,flush=True);assert r.returncode==0 and len(r.stdout.strip())==4;v=int(r.stdout.strip(),16);assert v!=65535;return v
old=rd();subprocess.run(['setpci','-s',bdf,'COMMAND=0000:0004'],check=True);new=rd()
assert not new & 4 and old & ~4 == new & ~4
print(json.dumps(dict(before=old,after=new)))
''' % eps[0]['bdf'])
def reboot():
    global BOOT
    before=snapshot('before_reboot'); assert before['admission_mode']=='0o644'
    BOOT=before['boot_id'];clear_bme(before)
    cli=c.connect()
    try:
        try: c.record(HERE,'reboot','sudo -n reboot\n',c.transport(cli))
        except Exception as e: save('reboot_transport.json',{'utc':c.utc(),'error':str(e),'boot_change_required':True})
    finally:cli.close()
    for n in range(90):
        time.sleep(5)
        try:
            raw=remote('reconnect_%03d'%n, SNAP, boot=False); obj=json.loads(raw)
            if obj['boot_id']==BOOT: continue
            assert obj['admission_mode']=='0o644' and obj['admission_sha256']==ELFSHA
            assert not obj['holders'] and not obj['scan_errors']
            old=BOOT;BOOT=obj['boot_id'];save('boot_binding.json',{'utc':c.utc(),'before':old,'after':BOOT,'real_boot_changed':True});return
        except Exception as e:save('reconnect_error_%03d.json'%n,{'utc':c.utc(),'error':str(e)})
    raise RuntimeError('Actual new boot not confirmed')
def link_driver():
    state=snapshot('post_sram_natural')
    roots=[p for p in state['pci'] if p['attributes']['class'].startswith('0x0604')]
    if not roots and not state['pci']:
        src=(GOAL/'pcie_host_reprobe08/bind_once.command.txt').read_text()
        src=src.split("<<'PY'\n",1)[1].rsplit('\nPY',1)[0]
        src=src.replace('925a0f3d-b23b-46e5-b02b-b387a380402e',BOOT)
        remote('host_bind_once',src)
        state=snapshot('post_bind')
    eps=[p for p in state['pci'] if p['attributes']['vendor']=='0x0755' and p['attributes']['device']=='0x0755']
    assert len(eps)==1, 'New SRAM did not enumerate exact endpoint; no reset or fallback'
    ep=eps[0];assert ep['bdf']=='0002:21:00.0'
    assert ep['attributes']['current_link_width']=='2' and ep['attributes']['current_link_speed'].startswith('5.0'), 'PCIe is not Gen2 x2'
    if ep['driver'] is None:
        src=(GOAL/'pcie_host_reprobe08/insmod_once.command.txt').read_text().split("<<'PY'\n",1)[1].rsplit('\nPY',1)[0]
        remote('insmod_once',src.replace('925a0f3d-b23b-46e5-b02b-b387a380402e',BOOT))
    final=snapshot('driver_ready')
    ep=next(p for p in final['pci'] if p['bdf']=='0002:21:00.0')
    assert ep['driver'] and 'pango' in ep['driver'] and final['driver_nodes']
    remote('bar_command_verify', '''import subprocess,json
p=Path('/sys/bus/pci/devices/0002:21:00.0')
r=subprocess.run(['setpci','-s',p.name,'COMMAND'],capture_output=True,text=True);print(r.returncode,r.stdout,r.stderr);assert r.returncode==0 and int(r.stdout.strip(),16)!=65535
resources=(p/'resource').read_text();print(resources);assert any(int(line.split()[0],16)>0 for line in resources.splitlines())
''')
def viewer(mode, bit, receipt):
    snapshot(mode+'_before')
    ledger_mode(mode+'_admission_restore',0o755)
    remote_dir='/userdata/driving_demo_evidence/functional_delivery10_'+str(int(time.time()))+'_'+mode
    args=[ELF,'--fullscreen','--no-tracking']
    if mode=='six-camera':args+=['--prefer-hdmifull','off']
    else:args+=['--driving-demo','--rotate-model','trafficlight-16cls,wb_v4_combo']
    args+=['--duration','120']
    source='''import subprocess,os,json,hashlib,time
root=Path(%r);root.mkdir(mode=0o700,parents=True,exist_ok=False)
app=%r; assert hashlib.sha256(Path(app).read_bytes()).hexdigest()==%r
launcher=Path('/userdata/detview-driving-demo/run_driving_demo.sh').read_text();print('LAUNCHER_SHA256',hashlib.sha256(launcher.encode()).hexdigest())
assert 'LD_LIBRARY_PATH' not in launcher, 'Launcher has a library setting: review before direct exec'
r=subprocess.run(['ldd',app],capture_output=True);print(r.stdout.decode(),r.stderr.decode());assert r.returncode==0 and b'not found' not in r.stdout
env=os.environ.copy();env.update(DISPLAY=':0',XAUTHORITY='/home/linaro/.Xauthority',QT_X11_NO_MITSHM='1',QT_QPA_PLATFORM='xcb',QT_XCB_GL_INTEGRATION='xcb_egl')
# Supervisor preserves exact child exit status and never relaunches it.
supervisor="import subprocess,json,os;from pathlib import Path;p=Path("+repr(str(root))+");f=(p/'viewer.log').open('wb');v=subprocess.Popen("+repr(%r)+",cwd='/userdata/detview-driving-demo',env="+repr(env)+",stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT);(p/'pid').write_text(str(v.pid));rc=v.wait();f.close();(p/'exit.json').write_text(json.dumps(dict(pid=v.pid,rc=rc)))"
s=subprocess.Popen(['python3','-u','-c',supervisor],stdin=subprocess.DEVNULL,stdout=(root/'supervisor.log').open('wb'),stderr=subprocess.STDOUT,start_new_session=True)
for n in range(50):
 if (root/'pid').exists():break
 time.sleep(.1)
pid=int((root/'pid').read_text());p=Path('/proc')/str(pid)
print(json.dumps(dict(pid=pid,supervisor_pid=s.pid,root=str(root),log=str(root/'viewer.log'),exe=os.readlink(p/'exe'),argv=(p/'cmdline').read_bytes().split(b'\\0'),starttime=(p/'stat').read_text().rsplit(')',1)[1].split()[19]),default=lambda b:b.decode()))
'''%(remote_dir,ELF,ELFSHA,args)
    raw=remote(mode+'_launch',source)
    ident=json.loads(raw.decode().splitlines()[-1]);save(mode+'_viewer_identity.json',ident)
    assert ident['exe']==ELF and ident['argv'][:-1]==args
    try:
        time.sleep(12)
        cmd=[sys.executable,'-B',str(GOAL/'capture_camera_session09.py'),'--mode',mode,'--pid',str(ident['pid']),'--bit',str(bit),'--program-receipt',str(receipt),'--viewer-log',ident['log'],'--output',str(HERE/(mode+'_capture'))]
        def local(_):
            p=subprocess.run(cmd,capture_output=True,timeout=100);return p.returncode,p.stdout,p.stderr
        c.record(HERE,mode+'_capture',subprocess.list2cmdline(cmd),local)
    finally:
        # Wait for the owned duration exit. If necessary only signal the exact owned identity.
        remote(mode+'_wait_exit', '''import time,os,json,signal
root=Path(%r);pid=%d;expected=%r
for n in range(140):
 if (root/'exit.json').exists():break
 time.sleep(1)
else:
 p=Path('/proc')/str(pid)
 assert os.readlink(p/'exe')==%r and (p/'stat').read_text().rsplit(')',1)[1].split()[19]==expected
 os.kill(pid,signal.SIGTERM)
 for n in range(10):
  if (root/'exit.json').exists():break
  time.sleep(1)
 assert (root/'exit.json').exists(), 'Owned viewer did not exit; admission remains held'
print((root/'exit.json').read_text())
'''%(remote_dir,ident['pid'],ident['starttime'],ELF))
        full=remote(mode+'_full_log', 'print(Path(%r).read_text(),end="")'%ident['log'])
        result=summary.summarize(full);save(mode+'_log_summary.json',result)
        snapshot(mode+'_released')
        ledger_mode(mode+'_admission_rehold',0o644)
    exitdoc=json.loads((HERE/(mode+'_wait_exit.stdout.txt')).read_bytes());assert exitdoc['rc']==0, 'Actual viewer failed'
    result=json.loads((HERE/(mode+'_log_summary.json')).read_bytes())
    assert not result['video_log_present'] and not result['inference_failure_observed']
    if mode=='six-camera':assert result['positive_capture_rates_all_six'], 'Six-camera frames missing/stalled'
    else:
        assert all(str(cam) in result['latest_per_camera'] and result['latest_per_camera'][str(cam)]['tag_advance_rate']>0 for cam in [5,6]), 'Driving C5/C6 stalled'
        assert result['inference_completion_observed'], 'No actual completed model inference'
    assert not result['error_candidates'], 'Actual viewer has errors; retain raw logs for review'
def main():
    assert not (HERE/'execution_started.json').exists(), 'Never repeat delivery execution'
    save('execution_started.json',{'utc':c.utc(),'pid':os.getpid(),'runner_sha256':c.sha(__file__),'goal_complete':False})
    wait_controller()
    handoff=checker.check(BUILD/'BIT_MANIFEST.json');save('checked_bit_handoff.json',handoff)
    bit=Path(handoff['bit']);digest=handoff['bit_sha256']
    print(c.utc(),'Actual new bit qualified',digest,flush=True)
    k,h=c.tool_lease(HERE)
    try:
        vendor.idle();reboot();snapshot('before_sram')
        directory=HERE/'sram_program';directory.mkdir()
        receipt={'status':'blocked','target':'PG2L100H','mode':'sram','bit':str(bit),'bit_sha256':digest,'stages':{},'stage_errors':[],'boot_id':BOOT,'handoff_sha256':c.sha(HERE/'checked_bit_handoff.json'),'started_utc':c.utc()}
        try:vendor.run(SimpleNamespace(mode='sram',timeout=300),receipt,directory,bit,digest)
        finally:
            receipt['ended_utc']=c.utc();c.save(directory/'receipt.json',receipt)
        assert receipt['status']=='success' and all(receipt['stages'].values())
        link_driver()
        for mode in ['six-camera','driving']:viewer(mode,bit,directory/'receipt.json')
        snapshot('final_state')
        save('RESULT.json',{'status':'ACTUAL_NEW_SRAM_TWO_MODES_CAPTURED_REQUIRES_VISUAL_REVIEW','utc':c.utc(),'boot_id':BOOT,'bit':str(bit),'bit_sha256':digest,'vendor_receipt':str(directory/'receipt.json'),'vendor_receipt_sha256':c.sha(directory/'receipt.json'),'goal_complete':False,'functional_pass':False,'admission_mode':'0o644','ledger_retained':True})
    finally:k.ReleaseMutex(h);k.CloseHandle(h)
if __name__=='__main__':
    try:main()
    except Exception as e:
        if BOOT:
            try: ledger_mode('failure_admission_rehold',0o644)
            except Exception as cleanup: save('failure_admission_rehold_error.json',{'utc':c.utc(),'error':repr(cleanup)})
        save('FAIL.json',{'utc':c.utc(),'error':repr(e),'traceback':traceback.format_exc(),'goal_complete':False,'functional_pass':False,'old_bit_fallback':False})
        traceback.print_exc();sys.exit(1)
