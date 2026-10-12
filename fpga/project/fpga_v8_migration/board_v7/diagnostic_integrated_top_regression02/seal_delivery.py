"""Seal after redirected execution logs close; verify all prior artifacts."""
from pathlib import Path
import hashlib,json
P=Path(__file__).resolve().parent
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def main():
    prior=json.loads((P/'hashlog.json').read_text())
    differences=[n for n,h in prior.items() if sha(P/n)!=h]
    assert set(differences)<= {'audit_run.log'},differences
    frozen=json.loads((P/'frozen_before.json').read_text())
    assert frozen==json.loads((P/'frozen_after.json').read_text())
    assert all(sha(f)==h for f,h in frozen.items())
    assert json.loads((P/'audit.json').read_text())['status']=='PASS'
    hashes={str(f.relative_to(P)):sha(f) for f in P.rglob('*') if f.is_file() and not any(x in f.parts for x in ['work','__pycache__']) and f.name!='hashlog.json'}
    (P/'hashlog.json').write_text(json.dumps(hashes,indent=2),encoding='utf8')
    assert all(sha(P/n)==h for n,h in hashes.items())
    print('DELIVERY_HASH_SEAL_PASS files=%d protected=%d closed_log_updates=%s'%(len(hashes),len(frozen),differences))
if __name__=='__main__':main()
