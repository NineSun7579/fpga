from probe import E,sha,save
from pathlib import Path
import json,re
rows=[]
for d in sorted((E/'probes').iterdir()):
 if not d.is_dir():continue
 rec=d/'receipt.json';failure=d/'failure.json';log=d/'stdout.log'
 rows.append(dict(probe=d.name,receipt=json.loads(rec.read_bytes()) if rec.exists() else None,failure=json.loads(failure.read_bytes()) if failure.exists() else None,semantic_rejections=[line.decode('utf-8','backslashreplace') for line in log.read_bytes().splitlines() if re.search(rb'Timing-4006|STA-3016|Flow-0013|\b(?:unknown|unresolved|unsupported|fatal)\b|^\s*E:',line,re.I)] if log.exists() else [],physical_accepted=False))
save(E/'probe_failure_audit_final.json',rows)
summary=json.loads((E/'followup_summary.json').read_bytes())
assert len([x for x in summary['mapped_old_async_groups'] if x['name'] in ['cmos1_pclk','cmos2_pclk','cmos3_pclk','cmos4_pclk'] and x['async_value']])==4
g=json.loads((E/'timing_reload_gaps_final.json').read_bytes());assert len(g['coverage'])==9 and all(v['verified'] is False for v in g['coverage'].values())
for v in g['coverage'].values():
 for x in v['raw_files']:
  p=Path(x['path']);assert p.stat().st_size==x['bytes'] and sha(p)==x['sha256']
save(E/'evidence_hashes_final.json',[dict(path=str(p.resolve()),bytes=p.stat().st_size,sha256=sha(p)) for p in E.rglob('*') if p.is_file() and p.name!='evidence_hashes_final.json'])
print('Final evidence hashes validated; no accepted timing_reload claims')
