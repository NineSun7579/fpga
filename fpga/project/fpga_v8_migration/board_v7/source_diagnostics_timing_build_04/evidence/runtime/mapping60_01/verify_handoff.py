from pathlib import Path
import json,hashlib,sys,subprocess
sys.dont_write_bytecode=True
E=Path(__file__).resolve().parent;B=E.parents[2]
sys.path.insert(0,str(B/'runtime'))
import preflight
def load(n):return json.loads((E/n).read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=preflight.verify();checks={}
for ledger in ['final_evidence_hashes.json','failure_diagnosis_hashes.json']:
    for n,h in load(ledger).items():checks[ledger+':'+n]=sha(E/n)==h
assert all(checks.values())
ps=json.loads(subprocess.check_output(['powershell','-NoProfile','-Command','ConvertTo-Json -InputObject @(Get-CimInstance Win32_Process | Select-Object ProcessId,Name) -Compress']))
busy=[p for p in ps if p['Name'].lower() in {'pds.exe','pds_shell.exe','ta.exe'}]
assert not busy
inv=load('failed_attempt_exact60_inventory.json');assert inv['counts']['targets']==60
save={'status':'PASS_EVIDENCE_INTEGRITY_PRODUCTION60_FAIL_RETAINED','evidence_hash_checks':checks,'all_tool_processes_exited':not busy,'source_files':len(m['local_hashes']),'registered_sources':len(m['registered_sources']),'build03_frozen_files':len(m['build03_full_hashes']),'protected_hashes':len(m['protected_hashes']),'actual_counts':inv['counts'],'actual_map_exit':load('mapping_receipt.json')['exit_code'],'actual_export_exit':load('mapping_export_receipt.json')['exit_code'],'production60_status':'FAIL','pnr':False,'bit':False,'remote':False,'program':False}
p=E/'handoff_integrity_review.json';assert not p.exists();p.write_text(json.dumps(save,indent=2)+'\n',encoding='ascii')
print(save['status'],len(checks),'hash checks')
