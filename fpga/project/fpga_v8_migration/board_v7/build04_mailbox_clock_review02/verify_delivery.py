"""Final standalone audit of review02 delivery and untouched review01 seals."""
from pathlib import Path
import hashlib,json
P=Path(__file__).resolve().parent;R=P.parent/'build04_mailbox_clock_review01'
def load(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for n,h in load(P/'review02_hashes.json').items():assert sha(P/n)==h,n
for n,h in load(R/'final_bundle_hashes.json').items():assert sha(R/n)==h,n
c=load(P/'candidate_specific_expectation_contract.json');d=load(P/'decision_ZH.json')
assert d['contract_sha256']==sha(P/'candidate_specific_expectation_contract.json')
assert c['expected']=={'logical2048':2048,'registerLogical1320':1320,'uniquePhysical1280':1280,'zero728':728,'alias40':40,'per_camera':{'logical':512,'registerLogical':330,'uniquePhysical':320,'zero':182,'alias':10},'corners':['Slow','Fast'],'exact_scored_pair_corner_records2560':2560}
partition=c['semantic_partition'];pp=partition['synthesis_physical_pairs'];z={tuple(x) for x in partition['zero_keys']}
regs=[tuple(k) for p in pp for k in p['logical_members']]
assert len(pp)==len({(p['Q'],p['D']) for p in pp})==1280
assert len(regs)==len(set(regs))==1320 and not set(regs)&z
assert len(z)==728 and set(regs)|z=={tuple(x) for x in partition['logical_keys']}
assert sum(len(p['logical_members'])-1 for p in pp)==40
for n,h in c['independent_review_evidence'].items():assert sha(P/n)==h,n
assert c['sharedlaneRTL']['sha256']==sha(P/c['sharedlaneRTL']['path'])
pc=c['exact_pair_corner_expectation'];assert pc['sha256']==sha(P/pc['path'])
records=load(P/pc['path'])['records'];assert len(records)==2560
actual={(r['synthesis_launch_Q'],r['synthesis_capture_D'],r['corner']) for r in records}
assert actual=={(p['Q'],p['D'],corner) for p in pp for corner in ['Slow','Fast']}
assert all(r['required_datapath_only_ns']==15.238 and r['score_required'] and r['fresh_route_actual_Q_CLK_D_binding_required'] for r in records)
assert c['timing']['set_max_delay_datapath_only_ns']==15.238 and not c['runtime_STA_passed'] and not c['constraints_qualified']
print('PASS final delivery hashes, exact candidate identity/semantic partition and untouched old58; contract',d['contract_sha256'])
