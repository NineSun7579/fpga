"""真实 ADIF CDB 全部364时钟对及逐物理 CLK 的 compile补集继承。"""
import json,re
import generate_exact11 as gen
def parse_cdb(path):
    raw=path.read_bytes();pos=raw.find(b'(CDB ')
    assert pos>=0,('无实际 CDB',str(path))
    stack=[];root=None
    for m in re.finditer(r'"(?:[^"\\]|\\.)*"|\\[^\s]+|[()]|[^\s()]+',raw[pos:].decode('ascii',errors='backslashreplace')):
        t=m[0]
        if t=='(':stack.append([])
        elif t==')':
            n=stack.pop()
            if stack:stack[-1].append(n)
            else:root=n;break
        else:stack[-1].append(t)
    assert root and root[0]=='CDB'
    return root
def field(e,key,default=None):
    a=next((x for x in e[1:] if isinstance(x,list) and x[0]==key),None)
    return a[1] if a and len(a)>1 else default
def prove(stage,dump,graph=None):
    cdb=parse_cdb(dump);off=json.loads((gen.OUT/'coverageproof_offline.json').read_bytes())
    expected={tuple(p) for p in off['retained_clock_pairs']};pairs=[];maxdelay=[];errors=[]
    for e in cdb[1:]:
        if not isinstance(e,list):continue
        if e[0]=='FP' and field(e,'FCK') is not None and field(e,'TCK') is not None:
            a=field(e,'FCK').strip('"');b=field(e,'TCK').strip('"')
            pairs.append({'pair':[a,b],'setup':field(e,'SU'),'hold':field(e,'HD'),'line':field(e,'LN'),'cdbid':field(e,'CDBID')})
            if field(e,'SU')!='1' or field(e,'HD')!='1':errors.append({'wrong_setup_hold':e})
        if e[0]=='MMD':
            maxdelay.append({'delay_ps':field(e,'DELAY'),'datapath_only':field(e,'DATAPATH_ONLY'),'line':field(e,'LN'),'cdbid':field(e,'CDBID')})
    actual={tuple(e['pair']) for e in pairs}
    if actual!=expected:errors.append({'missing_clockpairs':sorted(expected-actual),'unexpected_clockpairs':sorted(actual-expected)})
    if len(pairs)!=364:errors.append({'clockpair_record_count':len(pairs)})
    if len(maxdelay)!=4 or any(e['delay_ps']!='15238' or e['datapath_only']!='1' for e in maxdelay):errors.append({'bad_mailbox_maxdelay':maxdelay})
    inheritance=[]
    if graph is not None:
        synth=json.loads((gen.OUT/'coverageproof_synthesis.json').read_bytes())
        binding={}
        eliminated=set()
        if stage=='routed':
            routed_proof=json.loads((gen.OUT/'coverageproof_routed.json').read_bytes())
            binding={b['logical']:b['physical'] for b in routed_proof['bindings']}
            eliminated={e['logical'] for e in routed_proof.get('eliminated_sinkless_registers',[])}
        lines=(gen.NEW/'physical_constraints_exact_11/clock.fdc').read_text().splitlines()
        for camera in synth['cameras']:
            i=camera['camera'];mailbox={p[0] for p in off['cameras'][i]['physical_pairs']}
            compile_comp=set(off['cameras'][i]['compile_complement'])
            for pin in camera['actual']['leaves']:
                if pin in mailbox:continue
                if stage=='routed' and pin in eliminated:
                    inheritance.append({'camera':i,'logical_synthesis_pin':pin,'map_eliminated_closed_sinkless_cone':True});continue
                physical=binding.get(pin,pin) if stage=='routed' else pin
                cell,port=physical.rsplit('/',1);entries=[]
                if cell not in graph['primitives']:
                    errors.append({'missing_physical_binding':pin});continue
                for e in graph['primitives'][cell].get('cdb_entries',[]):
                    if field(e,'PINNAME')!=port:continue
                    name=field(e,'FILENAME','').strip('"')
                    if name!=(gen.NEW/'physical_constraints_exact_11/clock.fdc').as_posix():continue
                    ln=int(field(e,'LINENUM'));text=lines[ln-1]
                    if not text.startswith('set_false_path -from ') or not text.endswith('-to [get_clocks {ddrphy_sysclk}]'):continue
                    origin=field(e,'HIER')+'/'+port
                    if origin in compile_comp:entries.append({'cdbid':field(e,'CDBID'),'line':ln,'compile_pin':origin})
                if not entries:errors.append({'missing_compile_complement_inheritance':pin})
                inheritance.append({'camera':i,'logical_synthesis_pin':pin,'physical_pin':physical,'compile_entries':entries})
    result={'stage':stage,'passed':not errors,'dump_path':str(dump),'dump_sha256':gen.cf.sha(dump),
            'clockpair_count':len(pairs),'clockpair_records':pairs,'mailbox_maxdelay_records':maxdelay,
            'compile_complement_inheritance':inheritance,'errors':errors}
    gen.write_json(gen.OUT/('actual_cdb_'+stage+'_proof.json'),result)
    return result
def main():
    graph=json.loads((gen.OUT/'actual/analysis/graph.json').read_bytes())
    results=[prove('synthesis',gen.OUT/'actual/synthesis_export/synthesis_dump.txt',graph)]
    routed=gen.OUT/'routed/synthesis_export/synthesis_dump.txt'
    if routed.exists():
        rg=json.loads((gen.OUT/'routed/analysis/graph.json').read_bytes())
        results.append(prove('routed',routed,rg))
    return results
if __name__=='__main__':
    print([(r['stage'],r['passed'],r['clockpair_count'],len(r['errors'])) for r in main()])
