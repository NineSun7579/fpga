from pathlib import Path
import json,collections,re,hashlib
HERE=Path(__file__).resolve().parent
def descendants(n,k):
    if isinstance(n,list):
        if n and n[0]==k:yield n
        for x in n:
            if isinstance(x,list):yield from descendants(x,k)
def main():
    g=json.loads((HERE/'graph.json').read_bytes());o=json.loads((HERE/'objects.json').read_bytes())
    prim=g['primitives'];pn=g['pin_net'];np=g['netpins'];aliases=g['net_aliases']
    aliasnet={a:n for n,aa in aliases.items() for a in aa}
    drivers={n:[p for p in pp if prim[p.rsplit('/',1)[0]]['ports'][p.rsplit('/',1)[1]]['direction']=='OUTPUT'] for n,pp in np.items()}
    shared_output_proofs=[]
    def lut_signature(pin):
        ip,port=pin.rsplit('/',1);r=prim[ip]
        assert r['type'].startswith('GTP_LUT'),r['type']
        init=next(p for p in (r['parameters'] or r['default_parameters']) if p[1]=='INIT')
        literal=next(descendants(init,'B'));v=int(literal[2].strip('"'),2)
        inputs=sorted((p for p,a in r['ports'].items() if a['direction']=='INPUT'),key=lambda p:int(p[1:]))
        if port=='Z5':inputs=[p for p in inputs if p!='I5']
        table=[(v>>mask)&1 for mask in range(1<<len(inputs))]
        used=[i for i in range(len(inputs)) if any(table[m]!=table[m^(1<<i)] for m in range(len(table)))]
        reduced=[table[sum(((mask>>j)&1)<<i for j,i in enumerate(used))] for mask in range(1<<len(used))]
        return ([pn[ip+'/'+inputs[i]] for i in used],reduced)
    for n,outs in drivers.items():
        if len(outs)>1 and n.startswith('source_diagnostics/') and all(prim[p.rsplit('/',1)[0]]['type'].startswith('GTP_LUT') for p in outs):
            sigs=[lut_signature(p) for p in outs]
            assert all(s==sigs[0] for s in sigs),('non-equivalent shared outputs',n,outs)
            shared_output_proofs.append({'net':n,'drivers':outs,'support_nets':sigs[0][0],'truth_table':sigs[0][1]})
    def clock_trace(pin,seen=None):
        seen=seen or set();net=pn[pin]
        if net in seen:raise ValueError('clock cycle')
        aa=aliases[net];outs=drivers.get(net,[]);ports=[a for a in aa if '/' not in a]
        step={'sink':pin,'aliases':[a for a in aa if '/@' in a and any(k in a for k in ['axi_clk','nt_cmos','gpll_clkout0','clkout0'])],'drivers':outs,'top_ports':ports}
        trace=[step]
        for p in outs:
            ip,port=p.rsplit('/',1);t=prim[ip]['type']
            if t.startswith('GTP_CLKBUF'):trace+=clock_trace(ip+'/CLKIN',seen|{net})
            elif t.startswith('GTP_INBUF'):trace+=clock_trace(ip+'/I',seen|{net})
        return trace
    provenance=[]
    for cam in range(4):
        r=o['bundles'][cam*512]
        provenance.append({'camera':cam,'launch':clock_trace(r['launch']['pins']['CLK']), 'capture':clock_trace(r['capture']['pins']['CLK'])})
    # Evaluate actual optimized LUT cones for read words. Each truth-table result is
    # an integer bitset over ALL 2**support assignments, not random vectors.
    # Word select, read_strobe and snapshot_valid are fixed to the RTL read contract.
    def symbolic(net,overrides,memo,active):
        if net in overrides:return overrides[net]
        if net in memo:return memo[net]
        const=[int(a[-1]) for a in aliases[net] if '/@$constant_' in a]
        if const:assert len(set(const))==1;return ('const',const[0])
        if net in active:raise ValueError('combinational cycle')
        outs=drivers.get(net,[])
        if len(outs)>1:
            assert all(p.rsplit('/',1)[0] in prim and prim[p.rsplit('/',1)[0]]['type'].startswith('GTP_LUT') for p in outs),outs
            # Shared equivalent outputs are checked separately; prefer current camera.
            outs=[next((p for p in outs if prefix in p),outs[0])]
        if len(outs)!=1:raise ValueError(('drivers',net,outs))
        ip,port=outs[0].rsplit('/',1);r=prim[ip];t=r['type']
        if t.startswith('GTP_DFF'):result=('var',outs[0])
        elif t in ['GTP_GND','GND']:result=('const',0)
        elif t in ['GTP_VCC','VCC']:result=('const',1)
        elif t.startswith('GTP_LUT'):
            params=r['parameters'] or r['default_parameters']
            init=next(p for p in params if p[1]=='INIT');literal=next(descendants(init,'B'))
            v=int(literal[2].strip('"'),2)
            inputs=sorted((p for p,a in r['ports'].items() if a['direction']=='INPUT'),key=lambda p:int(p[1:]))
            if port=='Z5':inputs=[p for p in inputs if p!='I5']
            args=[symbolic(pn[ip+'/'+p],overrides,memo,active|{net}) if ip+'/'+p in pn else ('var','UNCONNECTED/'+ip+'/'+p) for p in inputs]
            remaining=[a for a in args if a[0]!='const']
            table=[]
            for mask in range(1<<len(remaining)):
                pos=0;index=0
                for j,a in enumerate(args):
                    if a[0]=='const':x=a[1]
                    else:x=(mask>>pos)&1;pos+=1
                    index|=x<<j
                table.append((v>>index)&1)
            used=[j for j in range(len(remaining)) if any(table[m]!=table[m^(1<<j)] for m in range(len(table)))]
            if len(used)!=len(remaining):
                table=[table[sum(((mask>>i)&1)<<j for i,j in enumerate(used))] for mask in range(1<<len(used))]
                remaining=[remaining[j] for j in used]
            if len(set(table))==1:result=('const',table[0])
            else:
                result=('lut',sum(x<<j for j,x in enumerate(table)),remaining)
                for j,a in enumerate(remaining):
                    if all(x==((m>>j)&1) for m,x in enumerate(table)):result=a;break
        elif t.startswith('GTP_MUX'):
            args={p:symbolic(pn[ip+'/'+p],overrides,memo,active|{net}) for p,a in r['ports'].items() if a['direction']=='INPUT'}
            result=('mux',args)
        else:raise ValueError(('unsupported logic',ip,t))
        memo[net]=result;return result
    def support(expr):
        if expr[0]=='var':return {expr[1]}
        if expr[0]=='const':return set()
        if expr[0]=='lut':return set().union(*(support(x) for x in expr[2]))
        if expr[0]=='mux':return set().union(*(support(x) for x in expr[1].values()))
    def evaluate(e,env):
        if e[0]=='const':return e[1]
        if e[0]=='var':return env[e[1]]
        if e[0]=='lut':return (e[1]>>sum(evaluate(x,env)<<i for i,x in enumerate(e[2])))&1
        if e[0]=='mux':
            a=e[1];return evaluate(a['I1'] if evaluate(a['S'],env) else a['I0'],env)
    resolved=[];checks=[];errors=[]
    for cam in range(4):
        prefix=f'source_diagnostics/cameras[{cam}].source/'
        common={aliasnet[prefix+'@read_strobe']:('const',1),aliasnet[prefix+'@snapshot_valid']:('const',1)}
        for word in range(16):
            ov=dict(common)
            for j in range(4):ov[aliasnet[prefix+f'@read_word[{j}]']]=('const',(word>>j)&1)
            memo={}
            for bit in range(32):
                logical=word*32+bit;rec=o['bundles'][cam*512+logical]
                try:
                    e=symbolic(pn[prefix+f'read_data[{bit}]/D'],ov,memo,set())
                    ss=sorted(support(e));assert len(ss)<=12,(logical,ss)
                    values=[evaluate(e,{s:(mask>>i)&1 for i,s in enumerate(ss)}) for mask in range(1<<len(ss))]
                    mapping=None
                    if all(v==0 for v in values):mapping={'kind':'constant_zero','value':0}
                    else:
                        for i,s in enumerate(ss):
                            if all(v==((mask>>i)&1) for mask,v in enumerate(values)):
                                mapping={'kind':'register','capture_q':s};break
                    assert mapping is not None,('not identity',ss,values)
                    if mapping['kind']=='register':
                        capture=mapping['capture_q'].rsplit('/',1)[0];dnet=pn[capture+'/D'];qs=drivers[dnet]
                        assert len(qs)==1 and '/mailbox[' in qs[0],qs
                        launch=qs[0].rsplit('/',1)[0]
                        mapping.update({'launch_cell':launch,'capture_cell':capture,'launch_CLK':launch+'/CLK','launch_Q':launch+'/Q','capture_D':capture+'/D',
                                        'merged':capture!=prefix+f'host_bank[{logical}]','q_fanout':np[pn[launch+'/Q']]})
                        if rec['capture']:assert capture==rec['capture']['cell']
                    else:assert rec['capture'] is None,logical
                    resolved.append({'camera':cam,'logical_bit':logical,'word':word,'bit':bit,'mapping':mapping})
                    checks.append({'camera':cam,'logical_bit':logical,'support':ss,'exhaustive_assignments':len(values),'result':mapping['kind']})
                except Exception as exc:errors.append({'camera':cam,'logical_bit':logical,'error':str(exc)})
    result={'source_dump_sha256':o['dump_sha256'],'resolved':resolved,'errors':errors,'clock_provenance':provenance,'shared_output_proofs':shared_output_proofs,'proof':'Exhaustive actual LUT cone evaluation at snapshot_valid=1,read_strobe=1,word=0..15','checks':checks}
    (HERE/'manifest.json').write_text(json.dumps(result,indent=2))
    print('resolved',len(resolved),'errors',len(errors),'kinds',dict(collections.Counter(r['mapping']['kind'] for r in resolved)),'merged',sum(r['mapping'].get('merged',False) for r in resolved))
    print(errors[:5])
if __name__=='__main__':main()
