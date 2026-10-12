from pathlib import Path
import json,hashlib,re
E=Path(__file__).resolve().parent;B=E.parents[2]
m=json.loads((B/'manifest.json').read_bytes());old=Path(m['baseline_root'])
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows={n:sha(B/n)==v and (B/n).read_bytes()==(old/n).read_bytes() for n,v in m['local_hashes'].items()}
refs=[x.decode('ascii') for x in re.findall(rb'\(_file "([^"]+)"',(B/'project.pds').read_bytes()) if x.startswith((b'rtl/',b'inputs/'))]
passed=len(rows)==741 and all(rows.values()) and refs==m['registered_sources'] and len(refs)==186
result={'status':'PASS' if passed else 'FAIL','source_byte_equality_build03':rows,'actual_registered_sources':refs,'manifest_sha256':sha(B/'manifest.json'),'original_project_sha256':sha(B/'project.pds')}
out=E/'independent_source741_registration186_review.json'
assert not out.exists();out.write_text(json.dumps(result,indent=2)+'\n',encoding='ascii')
print(result['status'],len(rows),len(refs));assert passed
