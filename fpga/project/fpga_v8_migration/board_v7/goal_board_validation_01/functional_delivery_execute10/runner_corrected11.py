"""Preserved runner10 with fresh post-reboot BME masking and broader vendor idle."""
import importlib.util, sys, os, json, subprocess, traceback
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('delivery10_preserved',HERE/'runner.py')
r=importlib.util.module_from_spec(s);s.loader.exec_module(r)
original_reboot=r.reboot
original_remote=r.remote
original_idle=r.vendor.idle
def reboot():
    original_reboot()
    state=r.snapshot('fresh_post_reboot_before_sram')
    def named_remote(name,*args,**kwargs):
        if name=='bme_clear_before_reboot':name='bme_clear_after_reboot'
        return original_remote(name,*args,**kwargs)
    r.remote=named_remote
    try:r.clear_bme(state)
    finally:r.remote=original_remote
def idle():
    query="Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {$_.Name -match 'pds|programmer|^ta\\.exe$|^pnr\\.exe$|^synplify|^ads\\.exe$|^cfg|^pgm|^cdt_(cfg|js)|^(bitgen|pne|ppc|ppp|synth)\\.exe$'} | Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    def local(_):
        p=subprocess.run(['powershell','-NoProfile','-Command',query],capture_output=True,timeout=30)
        return p.returncode,p.stdout,p.stderr
    assert not r.c.record(HERE,'expanded_global_tool_idle',query,local).strip(), 'Whole-machine vendor tools busy'
    original_idle()
r.reboot=reboot
r.vendor.idle=idle
def main():
    assert not (HERE/'execution_started11.json').exists(), 'Never repeat corrected actual execution'
    r.save('execution_started11.json',{'utc':r.c.utc(),'pid':os.getpid(),'runner_sha256':r.c.sha(__file__),'preserved_runner_sha256':r.c.sha(HERE/'runner.py'),'goal_complete':False})
    r.wait_controller()
    handoff=r.checker.check(r.BUILD/'BIT_MANIFEST.json');r.save('checked_bit_handoff.json',handoff)
    bit=Path(handoff['bit']);digest=handoff['bit_sha256']
    print(r.c.utc(),'Actual new bit qualified',digest,flush=True)
    k,h=r.c.tool_lease(HERE)
    try:
        r.vendor.idle();r.reboot();r.snapshot('before_sram')
        directory=HERE/'sram_program';directory.mkdir()
        receipt={'status':'blocked','target':'PG2L100H','mode':'sram','bit':str(bit),'bit_sha256':digest,'stages':{},'stage_errors':[],'boot_id':r.BOOT,'handoff_sha256':r.c.sha(HERE/'checked_bit_handoff.json'),'started_utc':r.c.utc()}
        try:r.vendor.run(r.SimpleNamespace(mode='sram',timeout=300),receipt,directory,bit,digest)
        finally:
            receipt['ended_utc']=r.c.utc();r.c.save(directory/'receipt.json',receipt)
        assert receipt['status']=='success' and all(receipt['stages'].values())
        r.link_driver()
        for mode in ['six-camera','driving']:r.viewer(mode,bit,directory/'receipt.json')
        r.snapshot('final_state')
        r.save('RESULT.json',{'status':'ACTUAL_NEW_SRAM_TWO_MODES_CAPTURED_REQUIRES_VISUAL_REVIEW','utc':r.c.utc(),'boot_id':r.BOOT,'bit':str(bit),'bit_sha256':digest,'vendor_receipt':str(directory/'receipt.json'),'vendor_receipt_sha256':r.c.sha(directory/'receipt.json'),'goal_complete':False,'functional_pass':False,'admission_mode':'0o644','ledger_retained':True})
    finally:k.ReleaseMutex(h);k.CloseHandle(h)
if __name__=='__main__':
    try:main()
    except Exception as e:
        if r.BOOT:
            try:r.ledger_mode('failure_admission_rehold',0o644)
            except Exception as cleanup:r.save('failure_admission_rehold_error.json',{'utc':r.c.utc(),'error':repr(cleanup)})
        r.save('FAIL.json',{'utc':r.c.utc(),'error':repr(e),'traceback':traceback.format_exc(),'goal_complete':False,'functional_pass':False,'old_bit_fallback':False})
        traceback.print_exc();sys.exit(1)
