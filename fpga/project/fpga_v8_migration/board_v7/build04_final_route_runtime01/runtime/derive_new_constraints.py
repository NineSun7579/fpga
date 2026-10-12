"""Pure offline derivation from supplied NEW compile/synthesis graphs; no tool calls."""
from pathlib import Path
import argparse, hashlib, json, re
from graph_adapter import Resolver, classify, require
from contract import validate_mapping, CONTRACT

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def coll(pins):
    require(bool(pins),'Empty exact constraint collection')
    return '[get_pins -hierarchical {'+' '.join(c.replace('/','.')+'/'+p for c,p in
           (x.rsplit('/',1) for x in sorted(set(pins))))+'}]'
def derive(compile_graph,synthesis_graph,mapping_manifest,frozen_clock):
    cg=json.loads(Path(compile_graph).read_bytes());sg=json.loads(Path(synthesis_graph).read_bytes())
    m=json.loads(Path(mapping_manifest).read_bytes());raw=Path(frozen_clock).read_bytes()
    require(not m['errors'] and len(m['resolved'])==2048,'New exhaustive mailbox resolution incomplete')
    validate_mapping(m,sg); classify(cg);classified=classify(sg)
    clocks=set();groups=[]
    for line in raw.decode('ascii').splitlines():
        line=line.lstrip()
        if line.lstrip().startswith('#'):continue
        if line.startswith(('create_clock ','create_generated_clock ')):clocks.add(re.search(r'-name\s+\{([^}]+)\}',line)[1])
        if line.startswith('set_clock_groups '):
            require('-asynchronous' in line,'Unknown frozen clock group')
            gs=re.findall(r'-group\s+\[get_clocks\s+\{?(\w+)\}?\]',line)
            require(len(gs)==1,'Unknown frozen group syntax');groups.extend(gs)
    u={(a,b) for a in clocks for b in clocks if a!=b and (a in groups or b in groups)}
    carved={(f'cmos{i+1}_pclk','ddrphy_sysclk') for i in range(4)}
    require(len(u)==368 and carved<=u and len(u-carved)==364,'Complete frozen U changed')
    lines=['# Derived from supplied new graph hashes; qualification and runtime proof pending.']
    for a,b in sorted(u-carved):lines.append(f'set_false_path -from [get_clocks {{{a}}}] -to [get_clocks {{{b}}}]')
    rows=[];allpairs=set()
    for cam in range(4):
        cr=Resolver(cg);sr=Resolver(sg);cp=cr.clock_leaves(cam);sp=sr.clock_leaves(cam)
        pre=f'source_diagnostics/cameras[{cam}].source/'
        mb={k+'/'+p for k,r in cg['primitives'].items() if k.startswith(pre+'mailbox[') for p,v in r['ports'].items() if v['clock']}
        host={k+'/'+p for k,r in cg['primitives'].items() if k.startswith(pre+'host_bank[') for p,v in r['ports'].items() if p.startswith('D[') and v['direction']=='INPUT'}
        require(len(mb)==17 and len(host)==512 and mb<=set(cp['leaves']),'New compile mailbox contract failed')
        mapped=[x['mapping'] for x in m['resolved'] if x['camera']==cam and x['mapping']['kind']=='register']
        pairs={(x['launch_CLK'],x['capture_D']) for x in mapped}
        require(len(pairs)==CONTRACT['expected']['per_camera']['uniquePhysical'],'Exact candidate per-camera physical contract failed')
        launches={a for a,b in pairs};captures={b for a,b in pairs}
        require(launches<=set(sp['leaves']),'Clock traversal omitted mailbox leaves')
        for a,b in pairs:
            q=a.rsplit('/',1)[0]+'/Q'
            require(sg['pin_net'][q]==sg['pin_net'][b] and set(sg['netpins'][sg['pin_net'][q]])=={q,b},'Mailbox path is not exclusive Q-D')
        complement=(set(cp['leaves'])-mb)|(set(sp['leaves'])-launches)
        lines += ['set_false_path -from '+coll(complement)+' -to [get_clocks {ddrphy_sysclk}]',
                  'set_max_delay -datapath_only 15.238 -from '+coll(mb|launches)+' -to '+coll(host|captures),
                  'set_false_path -hold -from '+coll(mb|launches)+' -to '+coll(host|captures)]
        ack=classified['ack_first'][cam]
        lines.append('set_false_path -from '+coll({ack['launch_CLK']})+' -to '+coll({ack['capture_D']}))
        rows.append({'camera':cam,'compile':cp,'synthesis':sp,'compile_mailbox':sorted(mb),
                     'physical_pairs':sorted(pairs),'complement':sorted(complement),'ack_first':ack})
        allpairs |= pairs
    require(len(allpairs)==CONTRACT['expected']['uniquePhysical1280'],'Exact candidate physical contract failed')
    base=b'\n'.join(x for x in raw.splitlines() if not x.lstrip().startswith(b'set_clock_groups '))+b'\n'
    result=base+'\n'.join(lines).encode('ascii')+b'\n'
    proof={'structural_pass':True,'runtime_proven':False,'constraints_qualified':False,'physical_pairs':CONTRACT['expected']['uniquePhysical1280'],
           'candidate_specific_contract':True,'U':sorted(u),'retained_clock_pairs':sorted(u-carved),
           'carved_camera_to_ddr':sorted(carved),'same_domain_exemptions':[], 'mailbox_budget_ns':15.238,
           'cameras':rows,'compile_graph_sha256':sha(compile_graph),'synthesis_graph_sha256':sha(synthesis_graph),
           'mapping_manifest_sha256':sha(mapping_manifest),'frozen_clock_sha256':sha(frozen_clock),
           'constraint_sha256':hashlib.sha256(result).hexdigest()}
    return result,proof
if __name__=='__main__':
    ap=argparse.ArgumentParser()
    for name in ['compile_graph','synthesis_graph','mapping_manifest','frozen_clock','output']:ap.add_argument('--'+name.replace('_','-'),required=True)
    a=ap.parse_args();dest=Path(a.output)
    require(not dest.exists(),'Refuse existing derived output');raw,proof=derive(a.compile_graph,a.synthesis_graph,a.mapping_manifest,a.frozen_clock)
    dest.mkdir(parents=True);(dest/'clock.fdc').write_bytes(raw)
    (dest/'coverageproof_new_graph.json').write_bytes((json.dumps(proof,indent=2)+'\n').encode('ascii'))
