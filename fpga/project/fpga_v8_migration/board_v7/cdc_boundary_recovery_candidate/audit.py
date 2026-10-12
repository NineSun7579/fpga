from pathlib import Path
import hashlib,json
here=Path(__file__).resolve().parent
modes=['baseline','candidate','extra','long_baseline','long_candidate','review','review_board','contract','binding_recovery']
summary={}
for mode in modes:
 p=here/mode/'simulation.log';text=p.read_text(errors='replace')
 lines=[s for s in text.splitlines() if 'DONE' in s or 'CONTINUOUS' in s or 'RECOVERY' in s]
 assert any('DONE' in s and 'errors=0' in s for s in lines),mode
 assert 'FAIL' not in text,mode
 summary[mode]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'summary':lines}
for line in (here/'protected_hashes.txt').read_text().splitlines():
 digest,path=line.split('  ',1)
 assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest,path
(here/'evidence_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
files=sorted(p for p in here.glob('*') if p.suffix in ('.py','.v','.vh','.sv','.md','.diff','.json'))
(here/'candidate_hashes.txt').write_text('\n'.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}' for p in files)+'\n')
print('AUDIT_PASS logs=9 protected=605 candidate_files='+str(len(files)))
