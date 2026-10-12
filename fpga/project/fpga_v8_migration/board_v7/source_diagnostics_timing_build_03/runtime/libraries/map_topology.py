import collections, re
from preflight import save


def audit(label,g,reference=None):
    # Resolve kept logical Q net names through actual graph aliases, then physical drivers.
    rows=[];pins=g['pin_net'];prims=g['primitives'];aliases=g['net_aliases'];netpins=g['netpins']
    def transparent(n):
        seen=set()
        while n not in seen:
            seen.add(n)
            drivers=[p for p in netpins.get(n,[]) if prims[p.rsplit('/',1)[0]]['ports'][p.rsplit('/',1)[1]]['direction']=='OUTPUT']
            if len(drivers)!=1:return n,drivers
            cell=drivers[0].rsplit('/',1)[0];rec=prims[cell]
            if 'KEEPBUF' not in rec['type'].upper() and rec['type'].lower() not in {'syn_keepbuf','keepbuf'}:return n,drivers
            inputs=[cell+'/'+p for p,v in rec['ports'].items() if v['direction']=='INPUT']
            output_port=drivers[0].rsplit('/',1)[1]
            index=re.search(r'\[\d+\]$',output_port)
            if index:inputs=[p for p in inputs if p.endswith(index[0])]
            if len(inputs)!=1:return n,drivers
            n=pins.get(inputs[0],n)
        return n,[]
    for cam in range(4):
        prefix=f'source_diagnostics/cameras[{cam}].'
        for chain,count in [('ack_sync',2),('req_sync',3),('overrun_sync',2),('cr',2),('hr',2),('reset_pipe',4)]:
            parent=prefix+('source/' if chain!='reset_pipe' else '')
            for bit in range(count):
                logical=parent+f'{chain}[{bit}]';instance=parent+f'{chain}_ff{bit}'
                netalias=(parent.rstrip('/')+'/@'+f'{chain}[{bit}]') if chain!='reset_pipe' else f'source_diagnostics/@cameras[{cam}].reset_pipe[{bit}]'
                matches=[n for n,a in aliases.items() if netalias in a]
                for direct in [instance+'/Q',logical+'/Q']:
                    if direct in pins:matches.append(pins[direct])
                matches=sorted(set(matches))
                drivers=[]
                for n in matches:drivers.extend(transparent(n)[1])
                drivers=sorted(set(drivers));cells=sorted({p.rsplit('/',1)[0] for p in drivers})
                binding_method='actual_Q_alias_or_primitive_Q_pin'
                if not cells:
                    candidates=[c for c,r in prims.items() if (c.startswith(instance+'/') or c.startswith(logical+'/')) and ('RS' in r['ports'] or 'CLK' in r['ports'])]
                    if len(candidates)==1:
                        cells=candidates;binding_method='actual_physical_cell_under_logical_instance'
                        c=cells[0]
                        drivers=[c+'/'+p for p,v in prims[c]['ports'].items() if v['direction']=='OUTPUT' and p in {'Q','Q0'} and c+'/'+p in pins]
                        matches=sorted({pins[p] for p in drivers})
                packed_from=None
                if not cells and bit and reference and rows:
                    prev=rows[-1]
                    if prev['camera']==cam and prev['chain']==chain and len(prev['cells'])==1 and 'SRL2' in prims[prev['cells'][0]]['type'].upper():
                        rp=reference['pin_net']
                        for before,after in [(parent+f'{chain}_ff{bit-1}',instance),(parent+f'{chain}[{bit-1}]',logical)]:
                            if before+'/Q' in rp and after+'/D' in rp and rp[before+'/Q']==rp[after+'/D'] and rp.get(before+'/CLK')==rp.get(after+'/CLK'):
                                cells=prev['cells'];c=cells[0];packed_from=prev['logical'];binding_method='verified_synthesis_adjacent_Q_to_D_inside_SRL2'
                                drivers=[c+'/Q0'] if c+'/Q0' in pins else []
                                matches=[pins[p] for p in drivers];break
                rec={'camera':cam,'chain':chain,'bit':bit,'logical':logical,'expected_instance':instance,'q_alias':netalias,'matching_nets':matches,'drivers':drivers,'cells':cells,'records':{c:prims[c] for c in cells},'pins':{c:{p:pins.get(c+'/'+p) for p in prims[c]['ports']} for c in cells}}
                rec['binding_method']=binding_method
                rec['packed_from']=packed_from
                # Compiler primitive cell names, synthesis GTP and physical DFF all require real D/clock/reset ports.
                independent=len(cells)==1 and len(drivers)==1
                if independent:
                    c=cells[0];r=prims[c];portset=set(r['ports']);clock=[p for p,v in r['ports'].items() if v['clock']]
                    if not clock and 'CLK' in portset and r['type'].startswith(('GTP_DFF','gopQ','gopSRL')):clock=['CLK']
                    reset=[p for p in portset if p in {'C','P','RS','CLR','PRE'}]
                    independent='D' in portset and bool(clock) and bool(reset) and not any(t in r['type'].upper() for t in ['SRL','DRM','RAM','LUT6QQ'])
                    rec.update({'D':c+'/D' if 'D' in portset else None,'clock_endpoints':[c+'/'+p for p in clock],'reset_endpoints':[c+'/'+p for p in reset]})
                rec['independent_endpoint_passed']=independent;rows.append(rec)
    allcells=[r['cells'][0] for r in rows if r['independent_endpoint_passed']]
    result={'stage':label,'status':'PASS' if len(allcells)==60 and len(set(allcells))==60 else 'FAIL','expected':60,'independent_registers':len(set(allcells)),'independent_sync':sum(r['independent_endpoint_passed'] for r in rows if r['chain'] in {'ack_sync','req_sync','overrun_sync'}),'independent_reset':sum(r['independent_endpoint_passed'] for r in rows if r['chain'] in {'cr','hr','reset_pipe'}),'physical_types':dict(collections.Counter(v['type'] for v in prims.values())),'rows':rows,'boundary':'Independent real storage cells and endpoints only. Functional regression remains original candidate evidence; this is not routed STA signoff.'}
    save(label+'_topology.json',result);return result

