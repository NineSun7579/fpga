"""Candidate-specific exact semantics. No any-count acceptance."""
from pathlib import Path
import collections,hashlib,json,re
HERE=Path(__file__).resolve().parent.parent
BOARD=HERE.parent
SOURCE=BOARD/'source_diagnostics_timing_build_04'
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4194304),b''):h.update(b)
    return h.hexdigest()
def require(ok,msg):
    if not ok:raise RuntimeError(msg)
CONTRACT=load(HERE/'candidate_specific_expectation_contract.json') if (HERE/'candidate_specific_expectation_contract.json').exists() else None
def verify_inputs():
    c=CONTRACT;s=c['source_candidate04'];review=BOARD/'build04_mailbox_clock_review02'
    require(sha(HERE/'candidate_specific_expectation_contract.json')==sha(review/'candidate_specific_expectation_contract.json'),'Contract identity drift')
    require(s['root']==str(SOURCE) and c['candidate_id']==SOURCE.name,'Candidate identity drift')
    for name,key in [('manifest.json','manifest_sha256'),('source04hash.json','source04hash_sha256')]:require(sha(SOURCE/name)==s[key],name+' drift')
    require(len(s['local_hashes741'])==741 and len(s['registered_sources186'])==len(set(s['registered_sources186']))==186,'741/186 mismatch')
    actual={p.relative_to(SOURCE).as_posix() for folder in ['rtl','inputs'] for p in (SOURCE/folder).rglob('*') if p.is_file()}
    require(actual==set(s['full_source_copy_hashes742']) and len(actual)==742,'Complete source inventory changed')
    for n,h in s['full_source_copy_hashes742'].items():require(sha(SOURCE/n)==h,'Source drift '+n)
    for n,h in s['local_hashes741'].items():require(sha(SOURCE/n)==h,'Local source drift '+n)
    manifest=load(SOURCE/'manifest.json')
    require(manifest['registered_sources']==s['registered_sources186'],'Registered source identity drift')
    registrations=[x.decode('ascii') for x in re.findall(rb'\(_file "([^"]+)"',(SOURCE/'project.pds').read_bytes())]
    require([n for n in registrations if n.startswith(('rtl/','inputs/'))]==s['registered_sources186'],'Actual project registration drift')
    for n,h in s['graph_and_raw_hashes'].items():require(sha(SOURCE/n)==h,'Graph/raw drift '+n)
    for n,h in c['independent_review_evidence'].items():require(sha(review/n)==h,'Review evidence drift '+n)
    return c
def validate_mapping(m,g,routed=False):
    require(not m['errors'],'Mailbox resolve errors')
    part=CONTRACT['semantic_partition'];groups=collections.defaultdict(set);zeros=set();keys=set();registers=0
    for r in m['resolved']:
        k=(r['camera'],r['logical_bit']);require(k not in keys,'Duplicate logical row');keys.add(k)
        require(r['word']*32+r['bit']==r['logical_bit'],'Word/bit identity mismatch')
        mp=r['mapping']
        if mp['kind']=='constant_zero':
            require(mp=={'kind':'constant_zero','value':0},'Nonzero constant');zeros.add(k);continue
        require(mp['kind']=='register','Unknown mapping kind');registers+=1
        q,d=mp['launch_Q'],mp['capture_D'];prefix=f'source_diagnostics/cameras[{k[0]}].source/'
        require(q.startswith(prefix) and d.startswith(prefix),'Cross-camera mapping')
        require(g['pin_net'][q]==g['pin_net'][d] and set(g['netpins'][g['pin_net'][q]])=={q,d},'Nonexclusive physical Q-D')
        require(mp['launch_CLK']==q.rsplit('/',1)[0]+'/CLK','Wrong launch clock')
        if not routed:
            require(all(g['primitives'][p.rsplit('/',1)[0]]['type']=='GTP_DFF_CE' for p in [q,d]),'Unknown mailbox primitive')
        groups[(q,d)].add(k)
    require(keys=={tuple(k) for k in part['logical_keys']} and zeros=={tuple(k) for k in part['zero_keys']},'Exact logical/zero sets mismatch')
    expected={(p['Q'],p['D']):{tuple(k) for k in p['logical_members']} for p in part['synthesis_physical_pairs']}
    require(len(groups)==1280 and registers==1320,'Exact physical/register counts mismatch')
    if routed:
        require({frozenset(v) for v in groups.values()}=={frozenset(v) for v in expected.values()},'Routed reverse alias partition mismatch')
    else:require(dict(groups)==expected,'Exact physical reverse membership mismatch')
    require(all(sum(next(iter(v))[0]==cam for v in groups.values())==320 for cam in range(4)),'Per-camera physical mismatch')
    return [{'Q':q,'D':d,'CLK':q.rsplit('/',1)[0]+'/CLK','logical_members':sorted(v)} for (q,d),v in sorted(groups.items())]
def validate_records(rows,pairs):
    expected={(p['CLK'],p['D'],c) for p in pairs for c in ['Slow','Fast']};actual=[]
    require(len(expected)==2560,'Physical target identity/duplicates mismatch')
    for r in rows:
        key=(r['start'],r['end'],r['corner']);actual.append(key)
        require(key in expected,'Cross-pair or wrong corner record')
        require(r.get('exception')=='MaxDelay Path 15.238','Wrong timing budget exception')
        require(isinstance(r.get('slack'),(float,int)) and r['slack']>=0,'Unscored/negative slack')
    require(len(actual)==len(set(actual))==2560 and set(actual)==expected,'Missing/duplicate/extra pair-corner')
    return True
