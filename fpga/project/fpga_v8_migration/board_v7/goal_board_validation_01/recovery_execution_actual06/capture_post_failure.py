"""One read-only diagnostic of actual post-reboot failure; no recovery writes."""
import controller as c
import json
root=c.HERE/'execution_7cf8fef0e319'
d=root/'post_failure_readonly'; d.mkdir(exist_ok=False)
command="""sudo -n python3 - <<'POST_FAILURE'
import json,hashlib,stat,subprocess
from pathlib import Path
p=Path('/var/lib/fpga-recovery-actual06/admission.json')
rows=json.loads(p.read_text())
out={'boot':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'ledger_raw':p.read_text(),'ledger_uid':p.stat().st_uid,'ledger_mode':oct(stat.S_IMODE(p.stat().st_mode)),'inventory':[],'device_exists':Path('/dev/pango_pci_driver').exists(),'module_exists':Path('/sys/module/pango_pci_driver').exists(),'commands':[]}
for r in rows:
 f=Path(r['path']); h=hashlib.sha256(f.read_bytes()).hexdigest(); mode=stat.S_IMODE(f.stat().st_mode)
 out['inventory'].append(dict(r,current_sha256=h,current_mode=oct(mode),hash_matches=h==r['sha256'],execute_bits_clear=not bool(mode&0o111)))
for argv in (['lspci','-Dnn'],['cat','/proc/modules'],['dmesg']):
 q=subprocess.run(argv,capture_output=True,text=True);out['commands'].append(dict(argv=argv,returncode=q.returncode,stdout=q.stdout,stderr=q.stderr))
out['pci_sysfs']=[dict(bdf=f.name,vendor=(f/'vendor').read_text().strip(),device=(f/'device').read_text().strip(),class_code=(f/'class').read_text().strip()) for f in Path('/sys/bus/pci/devices').iterdir()]
print(json.dumps(out,indent=2))
POST_FAILURE
"""
client=c.connect()
try:
 raw=c.record(d,'current_state',command,c.transport(client)); out=json.loads(raw)
 assert out['boot']!='dd39b8d1-cf2d-404e-914d-45eb87278794'
 assert out['ledger_uid']==0 and out['ledger_mode']=='0o600'
 assert all(r['hash_matches'] and r['execute_bits_clear'] for r in out['inventory'])
 c.save(d/'reconstruction_failure.json',dict(boot_before='dd39b8d1-cf2d-404e-914d-45eb87278794',boot_after=out['boot'],admission_persistent_verified=True,device_exists=out['device_exists'],module_exists=out['module_exists'],actual_endpoint_bdfs=[r['bdf'] for r in out['pci_sysfs'] if r['vendor']=='0x0755' and r['device']=='0x0755'],status='new_boot_confirmed_driver_endpoint_reconstruction_failed',accepted=False,goal_complete=False))
 print((d/'reconstruction_failure.json').read_text())
finally: client.close()
