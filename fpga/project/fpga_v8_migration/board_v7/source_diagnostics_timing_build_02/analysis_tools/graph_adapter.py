"""Strict actual-graph resolver for cr_ff versus cr[] and KEEPBUFFER nets.

Logical aliases and connected Q drivers determine identity. Names only provide
an additional verified anchor; no whitelist or old-name assertion is deleted.
"""
import re

def require(ok, message):
    if not ok: raise RuntimeError(message)

def transparent(record, clock=False):
    typ=record['type']
    keep='KEEPBUF' in typ.upper() or typ.lower() in {'syn_keepbuf','keepbuf'}
    if keep: return True
    base={'bmsWIDEBUF','bmsBUF','GTP_INBUF','GTP_CLKBUFG','GTP_CLKBUF','GTP_CLKBUFH'}
    return typ in base or (clock and typ in {'bmsWIDEINV','bmsINV','GTP_INV'})

class Resolver:
    def __init__(self,g):
        self.g=g;self.pr=g['primitives'];self.pn=g['pin_net'];self.np=g['netpins'];self.alias=g['net_aliases']
    def drivers(self,n):
        return [p for p in self.np.get(n,[]) if self.pr[p.rsplit('/',1)[0]]['ports'][p.rsplit('/',1)[1]]['direction']=='OUTPUT']
    def strip(self,n):
        seen=set()
        while True:
            require(n not in seen,'Transparent data buffer cycle');seen.add(n)
            ds=self.drivers(n)
            if len(ds)!=1:return n
            cell=ds[0].rsplit('/',1)[0];r=self.pr[cell]
            if not transparent(r):return n
            ins=[cell+'/'+p for p,v in r['ports'].items() if v['direction']=='INPUT']
            outs=[p for p,v in r['ports'].items() if v['direction']=='OUTPUT']
            require(len(ins)==len(outs)==1 and ins[0] in self.pn,'Not a unit buffer: '+cell)
            n=self.pn[ins[0]]
    def equal(self,a,b): return self.strip(self.pn[a])==self.strip(self.pn[b])
    def bind(self,cam,chain,bit):
        prefix=f'source_diagnostics/cameras[{cam}].'
        parent=prefix+('source/' if chain!='reset_pipe' else '')
        logical=parent+f'{chain}[{bit}]';explicit=parent+f'{chain}_ff{bit}'
        alias=(parent.rstrip('/')+'/@'+f'{chain}[{bit}]') if chain!='reset_pipe' else f'source_diagnostics/@cameras[{cam}].reset_pipe[{bit}]'
        nets={n for n,aa in self.alias.items() if alias in aa}
        for anchor in [explicit,logical]:
            for cell,r in self.pr.items():
                if cell==anchor or cell.startswith(anchor+'/'):
                    for p in ['Q','Q0']:
                        if cell+'/'+p in self.pn:nets.add(self.pn[cell+'/'+p])
        ds={p for n in nets for p in self.drivers(self.strip(n))}
        require(len(ds)==1,f'Unique actual Q driver required: {logical}: {ds}')
        q=next(iter(ds));cell=q.rsplit('/',1)[0];r=self.pr[cell];ports=r['ports']
        require(not any(t in r['type'].upper() for t in ['SRL','RAM','DRM']), 'Packed storage rejected: '+cell)
        clocks=[p for p,v in ports.items() if v['clock']]
        if not clocks and 'CLK' in ports and r['type'].startswith(('GTP_DFF','gopQ')):clocks=['CLK']
        resets=[p for p in ports if p in {'P','C','RS','CLR','PRE','R','S'}]
        require('D' in ports and len(clocks)==len(resets)==1,'Distinct D/clock/reset endpoint required: '+cell)
        require(all(cell+'/'+p in self.pn for p in ['D',clocks[0],resets[0]]),'Unconnected endpoint: '+cell)
        return {'camera':cam,'chain':chain,'bit':bit,'logical':logical,'cell':cell,'type':r['type'],
                'Q':q,'D':cell+'/D','CLK':cell+'/'+clocks[0],'reset':cell+'/'+resets[0],
                'alias':alias,'matching_nets':sorted(nets),'cdb_entries':r.get('cdb_entries',[])}
    def constant(self,pin,value):
        n=self.strip(self.pn[pin]);ds=self.drivers(n)
        aliases=self.alias.get(n,[])
        if any(a.endswith('/@$constant_'+str(value)) for a in aliases):return True
        return len(ds)==1 and self.pr[ds[0].rsplit('/',1)[0]]['type'] in ({'GTP_GND','GND'} if value==0 else {'GTP_VCC','VCC'})
    def signal_q(self,cam,signal):
        parent=f'source_diagnostics/cameras[{cam}].source'
        nets=[n for n,aa in self.alias.items() if parent+'/@'+signal in aa]
        direct=parent+'/'+signal+'/Q'
        if direct in self.pn:nets.append(self.pn[direct])
        ds={p for n in nets for p in self.drivers(self.strip(n))}
        require(len(ds)==1,'Unique source signal Q missing: '+signal)
        return next(iter(ds))
    def clock_leaves(self,cam):
        name=f'cmos{cam+1}_pclk'
        roots={n for n,aa in self.alias.items() if name in aa or '/@'+name in aa}
        require(len(roots)==1,'Actual camera root not unique: '+name)
        queue=list(roots);seen=set();leaves=set();edges={};unknown=[]
        while queue:
            net=queue.pop()
            if net in seen:continue
            seen.add(net)
            for pin in self.np[net]:
                cell,port=pin.rsplit('/',1);r=self.pr[cell];v=r['ports'][port]
                if transparent(r,clock=True):
                    ins=[p for p,x in r['ports'].items() if x['direction']=='INPUT']
                    outs=[p for p,x in r['ports'].items() if x['direction']=='OUTPUT']
                    require(len(ins)==len(outs)==1,'Clock gate is not transparent: '+cell)
                    linked=[cell+'/'+p for p in ins+outs]
                    require(all(p in self.pn for p in linked),'Unconnected clock buffer: '+cell)
                    edges[cell]={'cell':cell,'type':r['type'],'pins':linked}
                    queue.extend(self.pn[p] for p in linked)
                elif v['direction']=='INPUT':
                    allowed=r['type'].startswith(('bmsWIDEDFF','GTP_DFF','GTP_DRM','gopQ'))
                    isclock=v['clock'] or (port=='CLK' and r['type'].startswith(('GTP_DFF','gopQ')))
                    if isclock and allowed:leaves.add(pin)
                    else:unknown.append({'pin':pin,'type':r['type'],'clock':v['clock']})
        require(not unknown,'Unknown camera clock sink: '+repr(unknown))
        require(leaves,'Empty camera leaves')
        return {'clock':name,'roots':sorted(roots),'nets':sorted(seen),'leaves':sorted(leaves),
                'transparent':list(edges.values()),'unknown':unknown}

def classify(g):
    r=Resolver(g); rows=[]; lookup={};chains=[];resets=[];ordinary=[]
    for cam in range(4):
        for chain,width in [('cr',2),('hr',2),('reset_pipe',4),('ack_sync',2),('req_sync',3),('overrun_sync',2)]:
            for bit in range(width):
                row=r.bind(cam,chain,bit);rows.append(row);lookup[(cam,chain,bit)]=row
                if bit:
                    prev=lookup[(cam,chain,bit-1)]
                    require(r.equal(prev['Q'],row['D']),'Previous Q to D changed: '+row['logical'])
                    require(r.equal(prev['CLK'],row['CLK']),'Chain clock changed: '+row['logical'])
                if chain in {'cr','hr','reset_pipe'}:
                    if not bit:require(r.constant(row['D'],0),'Reset release D0 not zero')
                    resets.append({'camera':cam,'logical':f'{chain}[{bit}]','actual_Q':[row['Q']],
                                   'D':row['D'],'CLK':row['CLK'],'reset':row['reset'],'merged':False})
                else:
                    if not bit:
                        q=r.signal_q(cam,{'ack_sync':'ack','req_sync':'request','overrun_sync':'sticky_overrun'}[chain])
                        require(r.equal(q,row['D']),'First-stage D source changed')
                    release=lookup[(cam,'cr' if chain=='ack_sync' else 'hr',1)]
                    require(r.equal(release['Q'],row['reset']),'Wrong reset release source')
                    chains.append({**row,'signal':chain,'stage':bit,'classification':'cdc_first' if bit==0 else 'sync_later'})
                    if bit:ordinary.append({'launch_CLK':prev['CLK'],'capture_D':row['D'],'classification':'sync_later'})
    require(len(rows)==len({x['cell'] for x in rows})==60,'60 independent actual storage cells required')
    require(len(chains)==28 and len(resets)==32 and len(ordinary)==16,'Chain/reset/stage counts changed')
    # Cross-domain ACK first stage remains exempt; later same-domain checks above remain mandatory.
    ack=[]
    for cam in range(4):
        q=r.signal_q(cam,'ack');cell=q.rsplit('/',1)[0]
        cp=[p for p,v in r.pr[cell]['ports'].items() if v['clock']]
        require(len(cp)==1,'ACK launch clock ambiguous')
        launch=cell+'/'+cp[0];first=lookup[(cam,'ack_sync',0)]
        require(not r.equal(launch,first['CLK']),'ACK first stage is not cross-domain')
        ack.append({'camera':cam,'launch_CLK':launch,'capture_D':first['D']})
    return {'status':'PASS','rows':rows,'chains':chains,'reset':resets,'ordinary_pairs':ordinary,
            'ack_first':ack,'independent_registers':60,'independent_sync':28,'independent_reset':32,
            'limits':['Structural new-graph binding only; INIT/GRS/async polarity and clock roots need endpoint audit',
                      'Recovery/removal/MPW/setup/hold and routed independence need actual two-corner STA']}
