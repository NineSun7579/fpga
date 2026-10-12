"""Preserve the live display30 baseline identity before further paired trials."""
import json,time,subprocess,sys
from pathlib import Path
import deploy_candidate as d
old=json.loads((d.ROOT/'deploy_1791608274721868300/receipt.json').read_text())
runtime=json.loads((d.ROOT/'display30_reboot_recovery/runtime_receipt.json').read_text())
folder=d.ROOT/('display30_baseline_'+str(time.time_ns()));folder.mkdir()
session=d.Session(folder,old)
try:
    assert session.rpc('hash',path=session.helper)['sha256']==old['artifacts']['helper_sha256']
    baseline=session.rpc('snapshot',pid=runtime['pid'],active_sha=d.ACTIVE)
    assert baseline['boot_id']==runtime['boot_id']
    assert baseline['env']['QT_QPA_PLATFORM']=='xcb'
    assert baseline['env']['QT_XCB_GL_INTEGRATION']=='xcb_egl'
    baseline['log']=runtime['remote']+'/original.log'
    (folder/'baseline.json').write_text(json.dumps(baseline,indent=2),encoding='utf-8')
    (folder/'artifacts.json').write_text(json.dumps({'viewer_sha256':d.ACTIVE,'sram_sha256':d.ROLLBACK,'driver_sha256':runtime['module_sha256'],'sram_program_evidence':str(d.ROOT/'display30_reboot_recovery/restore.jtag.log')},indent=2))
    print(str(folder),flush=True)
    subprocess.run([sys.executable,str(d.ROOT/'sample_runtime.py'),str(runtime['pid']),folder.name,baseline['log']],check=True)
finally:session.client.close()
