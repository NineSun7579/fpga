from pathlib import Path
import hashlib,json,subprocess,time
E=Path(__file__).resolve().parent
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
before=json.loads((E/'protection_before.json').read_bytes());drift=[p for p,h in before.items() if not Path(p).is_file() or sha(p)!=h]
ps=json.loads(subprocess.check_output(['powershell','-NoProfile','-Command','ConvertTo-Json -InputObject @(Get-CimInstance Win32_Process | Select-Object ProcessId,Name,CommandLine) -Compress']))
busy=[p for p in ps if p['Name'].lower() in {'pds.exe','pds_shell.exe','ta.exe'}]
binding=json.loads((E/'official_model_binding60_refined.json').read_bytes())
audit={'time':time.time(),'protected_fixed_files':len(before),'protected_drift':drift,'machine_busy':busy,'routed_renamed_rows':sum(r['mapped_cell']!=r['routed_cell'] for r in binding['rows']),'RSMUX_LOCAL_to_CHAIN_rows':sum('RSMUX_SEL' in r['parameter_changes'] for r in binding['rows']),'review_status':'Diagnostic exports complete. Independent SR alias/boundary semantic review and STA/IO/timing/reload gates blocked.','earlier_seal_correction':'Only RESULT_ZH.md count corrected 8 to 11; original evidence hashes remain preserved; use evidence_hashes_final.json.'}
p=E/'final_audit.json'
if p.exists():raise RuntimeError('Refuse overwrite')
p.write_text(json.dumps(audit,indent=2)+'\n')
files={str(p):sha(p) for p in E.rglob('*') if p.is_file()}
(E/'evidence_hashes_final.json').write_text(json.dumps(files,indent=2)+'\n')
print('FINAL_FIXED_INPUT_DRIFT',drift,'BUSY',busy,'FILES',len(files),'RSMUX',audit['RSMUX_LOCAL_to_CHAIN_rows'])
if drift or busy:raise RuntimeError('Final audit blocked')
