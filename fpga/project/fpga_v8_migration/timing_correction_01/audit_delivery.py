"""Verify final delivered sources match tested sources and protected evidence."""
from pathlib import Path
import hashlib,json,re
HERE=Path(__file__).resolve().parent
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
checks={}
reg=json.loads((HERE/'regression_result.json').read_text())
four=json.loads((HERE/'four_regression_result.json').read_text())
handoff=json.loads((HERE/'parent_handoff.json').read_text())
assert reg['status']==four['status']==handoff['four_regression_result']['status']=='PASS'
for p,h in reg['candidate_sources'].items(): assert sha(Path(p))==h
for p,h in reg['protected_sources'].items(): assert sha(Path(p))==h
for p,h in four['source_hashes'].items(): assert sha(Path(p))==h
assert four['candidate_sha256']==sha(HERE/'rtl/block_motion_detector_tc01.v')
for p,h in json.loads((HERE/'evidence/source_hashes.json').read_text()).items():
    assert sha(Path(p))==h,(p,'protected/candidate identity changed')
checks['tested_rtl_and_protected_sources_match']=True
checks['two_parent_bindings_with_unchanged_ports']=len(handoff['binding_replacements'])==2
assert checks['two_parent_bindings_with_unchanged_ports']
modules=[]
for p in sorted((HERE/'rtl').glob('*.v')):
    names=re.findall(rb'(?m)^module\s+(\w+)',p.read_bytes())
    assert len(names)==1
    modules.append(names[0].decode())
assert len(set(modules))==2
checks['unique_candidate_modules']=modules
checks['no_pds_or_ssh']=reg['pds_invoked']==four['pds_invoked']==False and reg['ssh_invoked']==False
checks['no_fdc_edits_or_timing_cuts']=handoff['fdc_edits']==handoff['new_false_paths']==handoff['new_hold_cuts']==[]
assert checks['no_pds_or_ssh'] and checks['no_fdc_edits_or_timing_cuts']
result={'status':'PASS','checks':checks,
        'source_hashes':{str(p.relative_to(HERE)):sha(p) for p in sorted(HERE.glob('*.py'))+sorted((HERE/'rtl').glob('*.v'))},
        'rtl_timing_status':'UNMEASURED; parent fresh whole route required',
        'parent_handoff_sha256':sha(HERE/'parent_handoff.json')}
(HERE/'delivery_audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
