"""User-authorized single reboot then qualifiedV7 SRAM PCIe trial."""
import sys, importlib.util, json, time, subprocess, ctypes, os, hashlib
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('actual06',HERE.parent/'recovery_execution_actual06/controller.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
def capture(name):
    client=c.connect()
    try:
        cmd="sudo -n python3 - <<'TRIAL07_READONLY'\n"+(HERE/'capture_remote.py').read_text()+"\nTRIAL07_READONLY\n"
        raw=c.record(HERE,name,cmd,c.transport(client))
        obj=json.loads(raw)
        assert obj['admission_mode']=='0o644' and obj['admission_sha256']=='72cd352aba95fce2a9897fb3fefe7214940b080d3937a2c8bad8afa72f25a703'
        assert not obj['holders'] and not obj['scan_errors']
        assert not any(p['exe']=='/userdata/detview-driving-demo/detview-driving-demo' for p in obj['processes'])
        return obj
    finally:client.close()
QUERY="Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {$_.Name -match '^(pds|pds_shell|pnr|ta|bitgen|pne|ppc|ppp|synth|cdt_js|cdt_cfg|cdt_cfg_shell|programmer)\\.exe$'} | Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress"
def toolscan(name):
    def run(_):
        p=subprocess.run(['powershell.exe','-NoProfile','-Command',QUERY],capture_output=True,timeout=30)
        return p.returncode,p.stdout,p.stderr
    return c.record(HERE,name,QUERY,run).strip()
def lease():
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p];k.CreateMutexW.restype=ctypes.c_void_p
    k.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong];k.WaitForSingleObject.restype=ctypes.c_ulong
    k.ReleaseMutex.argtypes=[ctypes.c_void_p];k.CloseHandle.argtypes=[ctypes.c_void_p]
    h=k.CreateMutexW(None,False,'Global\\ov56401_PDS_single_instance')
    if not h:raise RuntimeError('CreateMutex failed')
    n=0
    while True:
        # Do not hold the mutex while the other agent is building.
        busy=toolscan('tools_wait_%03d'%n)
        acquired=False;result=None
        if not busy:
            result=k.WaitForSingleObject(h,0)
            acquired=result in (0,128)
            if acquired and toolscan('tools_under_mutex_%03d'%n):
                k.ReleaseMutex(h);acquired=False
        c.save(HERE/('mutex_wait_%03d.json'%n),dict(utc=c.utc(),pid=os.getpid(),name='Global\\ov56401_PDS_single_instance',wait_result=result,acquired=acquired,vendor_busy=bool(busy)))
        if acquired:return k,h
        print('PDS/mutex busy; released or unowned; retaining fresh SSH window',flush=True)
        capture('waiting_readonly_%03d'%n)
        n+=1
        time.sleep(20)
def main():
    assert not (HERE/'reboot.receipt.json').exists(),'Never repeat this reboot trial'
    assert c.sha(c.BIT)==c.EXPECTED_BIT
    c.save(HERE/'provenance.json',dict(utc=c.utc(),user_order='sudo -n reboot -> qualifiedV7 SRAM -> natural PCIe -> optional one actual-parent rescan',actual06_controller_sha256=c.sha(HERE.parent/'recovery_execution_actual06/controller.py'),ssh_helper_sha256=c.sha(c.TOOLS/'board_host.py'),program_board_sha256=c.sha(c.M/'timing_correction_05/program_board.py'),verify_delivery_sha256=c.sha(c.M/'timing_correction_05/verify_delivery.py'),bit_sha256=c.sha(c.BIT),admission_release=False,flash=False,gpio144=False,heldSBR=False,viewer=False,goal_complete=False))
    before=capture('before_reboot_fresh')
    assert before['boot_id']=='c1500212-6832-4215-a2b2-76b60c8c3858'
    assert not before['pci'],'Expected no PCI EP/root at initial failed host state'
    client=c.connect()
    try:
        # A disconnect rc is retained; real boot change is the success criterion.
        try:c.record(HERE,'reboot','sudo -n reboot\n',c.transport(client))
        except Exception as e:c.save(HERE/'reboot_transport.json',dict(utc=c.utc(),error=str(e),boot_change_required=True))
    finally:client.close()
    print('sudo -n reboot sent; reconnecting to prove new boot',flush=True)
    after=None
    for n in range(90):
        try:
            obj=capture('reconnect_%03d'%n)
            if obj['boot_id']!=before['boot_id']:after=obj;break
        except Exception as e:c.save(HERE/('reconnect_error_%03d.json'%n),dict(utc=c.utc(),error=str(e)))
        time.sleep(5)
    if after is None:raise RuntimeError('New boot not confirmed; do not program')
    boot=after['boot_id']
    c.save(HERE/'boot_binding.json',dict(utc=c.utc(),before=before['boot_id'],after=boot,real_new_boot=True))
    print('Confirmed new boot '+boot,flush=True)
    k,h=lease()
    try:
        pre=capture('before_sram')
        assert pre['boot_id']==boot and not pre['pci'],'PCI state changed; review before programming'
        c.v7_program(HERE,'qualifiedV7_sram',boot)
        natural=capture('post_sram_natural_immediate')
    finally:k.ReleaseMutex(h);k.CloseHandle(h)
    assert natural['boot_id']==boot
    time.sleep(10)
    later=capture('post_sram_natural_10s')
    roots=[p for p in later['pci'] if p['attributes']['class'].startswith('0x0604')]
    endpoints=[p for p in later['pci'] if p['attributes']['vendor']=='0x0755' and p['attributes']['device']=='0x0755']
    rescan=dict(executed=False,reason='No actual PCI root/rootport: host probe failed, rescan cannot revive a missing host')
    if not endpoints and len(roots)==1:
        parent=roots[0]['bdf'];client=c.connect()
        try:
            cmd="sudo -n python3 - <<'TRIAL07_RESCAN'\nfrom pathlib import Path\np=Path('/sys/bus/pci/devices/"+parent+"/rescan')\nassert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=="+repr(boot)+"\nassert p.exists()\np.write_text('1\\n')\nprint('actual parent rescan: "+parent+"')\nTRIAL07_RESCAN\n"
            c.record(HERE,'single_parent_rescan',cmd,c.transport(client))
            rescan=dict(executed=True,parent=parent)
        finally:client.close()
        later=capture('post_single_rescan')
    c.save(HERE/'result.json',dict(utc=c.utc(),boot_before=before['boot_id'],boot_after=boot,bit_sha256=c.EXPECTED_BIT,sram_done=True,natural_pci=natural['pci'],final_pci=later['pci'],driver_nodes=later['driver_nodes'],rescan=rescan,admission_mode=later['admission_mode'],goal_complete=False,accepted=False))
    print(json.dumps(json.loads((HERE/'result.json').read_text()),indent=2),flush=True)
if __name__=='__main__':
    try:main()
    except Exception as e:
        c.save(HERE/'failure.json',dict(utc=c.utc(),error=repr(e),goal_complete=False))
        raise
