from probe import E,sha,save
import re,json
rows=[]
for d in sorted((E/'probes').iterdir()):
 if not d.is_dir():continue
 r=d/'receipt.json';f=d/'failure.json';log=d/'stdout.log'
 row=dict(probe=d.name,receipt=json.loads(r.read_bytes()) if r.exists() else None,failure=json.loads(f.read_bytes()) if f.exists() else None)
 if log.exists():
  raw=log.read_bytes();row['semantic_rejections']=[s.decode('utf-8','backslashreplace') for s in raw.splitlines() if re.search(rb'Timing-4006|STA-3016|Flow-0013|\b(?:unknown|unresolved|unsupported|fatal)\b|^\s*E:',s,re.I)]
  row['stdout_sha256']=sha(log)
  row['accepted_physical_evidence']=False
 rows.append(row)
save(E/'probe_failure_audit.json',rows)
print('No rc=0/registration-only/unknown target auto acceptance')
