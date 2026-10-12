"""Strict actual-graph resolver for cr_ff versus cr[] and KEEPBUFFER nets.

Logical aliases and connected Q drivers determine identity. Names only provide
an additional verified anchor; no whitelist or old-name assertion is deleted.
"""
import re

def canon(alias):return alias.replace('/@','/').lstrip('/')

def parameter(record,key):
    found={}
    def walk(value):
        if isinstance(value,list):
            if value and value[0]=='PARAMETER':found[value[1]]=value
            for child in value:walk(child)
    walk(record.get('default_parameters',[]));walk(record.get('parameters',[]))
    require(key in found,'Missing actual parameter '+key)
    def values(value):
        if isinstance(value,list):
            if value and value[0]=='B':yield int(value[2].strip('"'),2)
            if value and value[0]=='STRING':yield value[1].strip('"')
            for child in value:yield from values(child)
    result=list(values(found[key]));require(len(result)==1,'Ambiguous actual parameter '+key)
    return result[0]

def require(ok, message):
    if not ok: raise RuntimeError(message)

def transparent(record, clock=False):
    typ=record['type']
    keep=typ in {'KEEPBUFFER','KEEPBUF','syn_keepbuf','keepbuf'}
    if keep: return True
    base={'bmsWIDEBUF','bmsBUF','GTP_INBUF','GTP_CLKBUFG','GTP_CLKBUF','GTP_CLKBUFH'}
    return typ in base or (clock and typ in {'bmsWIDEINV','bmsINV','GTP_INV'})

KEEPBUF_WIDTHS={'bmsKEEPBUF':32,'bmsKEEPBUF_Cell_1':1,'bmsKEEPBUF_Cell_2':3,
    'bmsKEEPBUF_Cell_3':2,'bmsKEEPBUF_Cell_4':17,'bmsKEEPBUF_Cell_5':128,
    'bmsKEEPBUF_Cell_6':16,'bmsKEEPBUF_Cell_7':8,'bmsKEEPBUF_Cell_8':4,
    'bmsKEEPBUF_Cell_9':5,'bmsKEEPBUF_Cell_10':10,'bmsKEEPBUF_Cell_11':12,
    'bmsKEEPBUF_Cell_12':7,'bmsKEEPBUF_Cell_13':28}
def strict_keepbuf(record):
    # Exact observed specialization, not a prefix whitelist. Official bmsPrim.v:
    # WIDTH vector I -> Z via assign Z=I; no state, enable, inversion or clock.
    require(record['type'] in KEEPBUF_WIDTHS,'Unknown KEEPBUF specialization')
    width=KEEPBUF_WIDTHS[record['type']]
    params={}
    def walk(v):
        if isinstance(v,list):
            if v and v[0]=='PARAMETER':
                require(v[1]=='WIDTH','Unknown KEEPBUF parameter')
                require(v[2]==['DATATYPE','INTEGER'] and v[3]==['INTEGER',str(width)] and len(v)==4,'Nonidentity KEEPBUF WIDTH')
                params[v[1]]=width
            elif v and v[0]=='PARAMETERMAP':
                for x in v[1:]:walk(x)
            else:
                for x in v:walk(x)
    walk(record.get('default_parameters',[]));walk(record.get('parameters',[]))
    require(params=={'WIDTH':width},'Missing KEEPBUF WIDTH')
    schema={f'{p}[{i}]':{'direction':d,'clock':False} for i in range(width) for p,d in [('I','INPUT'),('Z','OUTPUT')]}
    require(record['ports']==schema,'Nonidentity KEEPBUF schema')
    return True

class Resolver:
    def __init__(self,g):
        self.g=g;self.pr=g['primitives'];self.pn=g['pin_net'];self.np=g['netpins'];self.alias=g['net_aliases']
    def drivers(self,n):
        return [p for p in self.np.get(n,[]) if self.pr[p.rsplit('/',1)[0]]['ports'][p.rsplit('/',1)[1]]['direction']=='OUTPUT']
    def identity_input(self,output,clock=False):
        cell,port=output.rsplit('/',1);r=self.pr[cell]
        if r['type'] in KEEPBUF_WIDTHS:
            strict_keepbuf(r)
            match=re.fullmatch(r'Z\[(\d+)\]',port)
            require(match is not None,'Unsupported vector KEEPBUF output: '+output)
            index=match[1];pin=cell+'/I['+index+']'
            ins={p for p,v in r['ports'].items() if v['direction']=='INPUT'}
            outs={p for p,v in r['ports'].items() if v['direction']=='OUTPUT'}
            require(ins and outs=={p.replace('I[','Z[',1) for p in ins} and all(re.fullmatch(r'I\[\d+\]',p) for p in ins),'Nonidentity vector KEEPBUF interface: '+cell)
            require(pin in self.pn and r['ports'][port]['direction']=='OUTPUT','Unconnected vector KEEPBUF lane')
            return pin
        if r['type']=='gopCLKROUTE':
            require(port=='CR' and r['ports'][port]['direction']=='OUTPUT','Unsupported clock route output')
            require([parameter(r,'INIT'+k) for k in 'ABCD']==[0,(1<<64)-1,0,(1<<64)-1],'Nonidentity CLKROUTE: '+cell)
            require(r['ports']['M']['direction']=='INPUT' and cell+'/M' in self.pn,'Unconnected CLKROUTE M')
            return cell+'/M'
        if not transparent(r,clock):return None
        ins=[cell+'/'+p for p,v in r['ports'].items() if v['direction']=='INPUT']
        outs=[cell+'/'+p for p,v in r['ports'].items() if v['direction']=='OUTPUT']
        require(len(ins)==len(outs)==1 and outs[0]==output and ins[0] in self.pn,'Not a proven unit buffer: '+cell)
        return ins[0]
    def trace_driver(self,n):
        seen=set();trace=[]
        while True:
            require(n not in seen,'Identity data path cycle');seen.add(n)
            ds=self.drivers(n);require(len(ds)==1,'Unique identity-path net driver required: '+n)
            output=ds[0];cell=output.rsplit('/',1)[0];pin=self.identity_input(output)
            trace.append({'net':n,'driver':output,'type':self.pr[cell]['type'],'identity_input':pin,
                          'identity_parameters':{k:parameter(self.pr[cell],k) for k in ['INITA','INITB','INITC','INITD']} if self.pr[cell]['type']=='gopCLKROUTE' else {}})
            if pin is None:return output,trace
            n=self.pn[pin]
    def strip(self,n):
        seen=set()
        while True:
            require(n not in seen,'Transparent data buffer cycle');seen.add(n)
            ds=self.drivers(n)
            if len(ds)!=1:return n
            cell=ds[0].rsplit('/',1)[0];r=self.pr[cell]
            pin=self.identity_input(ds[0])
            if pin is None:return n
            n=self.pn[pin]
    def equal(self,a,b): return self.strip(self.pn[a])==self.strip(self.pn[b])
    def clock_ports(self,cell):
        record=self.pr[cell];ports=record['ports']
        clocks=[p for p,v in ports.items() if v['clock'] and v['direction']=='INPUT']
        if not clocks and record['type'].startswith(('GTP_DFF','gopQ','gopSRL2','gopLUT5','gopLUT6','gopLUT7','gopLUT8')) and 'CLK' in ports:
            require(ports['CLK']['direction']=='INPUT' and cell+'/CLK' in self.pn,'Unconnected/noninput storage CLK: '+cell)
            clocks=['CLK']
        if not clocks and record['type'].startswith(('gopDRM18K','gopDRM36K')):
            clocks=[p for p in ['CLKA','CLKB'] if p in ports and ports[p]['direction']=='INPUT' and cell+'/'+p in self.pn]
        return clocks
    def bind(self,cam,chain,bit):
        prefix=f'source_diagnostics/cameras[{cam}].'
        parent=prefix+('source/' if chain!='reset_pipe' else '')
        logical=parent+f'{chain}[{bit}]';explicit=parent+f'{chain}_ff{bit}'
        alias=(parent.rstrip('/')+'/@'+f'{chain}[{bit}]') if chain!='reset_pipe' else f'source_diagnostics/@cameras[{cam}].reset_pipe[{bit}]'
        nets={n for n,aa in self.alias.items() if any(canon(a) in {canon(alias),canon(logical)} for a in aa)}
        for anchor in [explicit,logical]:
            for cell,r in self.pr.items():
                if cell==anchor or cell.startswith(anchor+'/'):
                    require(not any(t in r['type'].upper() for t in ['SRL','RAM','DRM']),'Packed storage rejected by independent60 gate: '+cell)
                    for p in ['Q','Q0']:
                        if cell+'/'+p in self.pn:nets.add(self.pn[cell+'/'+p])
        ds={p for n in nets for p in self.drivers(self.strip(n))}
        require(len(ds)==1,f'Unique actual Q driver required: {logical}: {ds}')
        q=next(iter(ds));cell=q.rsplit('/',1)[0];r=self.pr[cell];ports=r['ports']
        require(not any(t in r['type'].upper() for t in ['SRL','RAM','DRM']), 'Packed storage rejected: '+cell)
        require(q.rsplit('/',1)[1] in {'Q','Q0'},'Logical stage resolved to non-Q driver: '+q)
        clocks=self.clock_ports(cell)
        resets=[p for p in ports if p in {'P','C','RS','CLR','PRE','R','S'}]
        require('D' in ports and len(clocks)==len(resets)==1,'Distinct D/clock/reset endpoint required: '+cell)
        require(all(ports[p]['direction']=='INPUT' for p in ['D',clocks[0],resets[0]]),'Storage endpoint direction changed: '+cell)
        require(all(cell+'/'+p in self.pn for p in ['D',clocks[0],resets[0]]),'Unconnected endpoint: '+cell)
        return {'camera':cam,'chain':chain,'bit':bit,'logical':logical,'cell':cell,'type':r['type'],
                'Q':q,'D':cell+'/D','CLK':cell+'/'+clocks[0],'reset':cell+'/'+resets[0],
                'alias':alias,'matching_nets':sorted(nets),'cdb_entries':r.get('cdb_entries',[])}
    def constant(self,pin,value):
        n=self.strip(self.pn[pin]);ds=self.drivers(n)
        aliases=self.alias.get(n,[])
        if any(a.rsplit('$constant_',1)[-1]==str(value) for a in aliases if '$constant_' in a):return True
        if len(ds)==1 and self.pr[ds[0].rsplit('/',1)[0]]['type']=='GTP_CONSTANT':
            from endpoint_detail import parameters
            return parameters(self.pr[ds[0].rsplit('/',1)[0]]).get('VALUE')==str(value)
        if len(ds)==1 and self.pr[ds[0].rsplit('/',1)[0]]['type'] in ({'GTP_GND','GND','gopGND'} if value==0 else {'GTP_VCC','VCC','gopVCC'}):return True
        from endpoint_logic import evaluate
        from endpoint_detail import parameters
        return evaluate(self.g,n,parameters)==value
    def signal_q(self,cam,signal):
        parent=f'source_diagnostics/cameras[{cam}].source'
        nets=[n for n,aa in self.alias.items() if any(canon(a)==parent+'/'+signal for a in aa)]
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
                if v['direction']=='OUTPUT':continue
                if r['type'] in {'gopIBUF','gopIBUF_Cell_1','gopIBUF_Cell_2'}:
                    require(port=='I' and parameter(r,'CP_DYN_IN')=='OFF' and parameter(r,'IOB_MODE').startswith('IBUF'),'Unproved clock input buffer mode: '+cell)
                    output=cell+'/O';require(output in self.pn and r['ports']['O']['direction']=='OUTPUT','Unconnected IBUF output')
                    edges[cell]={'cell':cell,'type':r['type'],'pins':[pin,output],'polarity':'identity','CP_DYN_IN':'OFF'}
                    queue.append(self.pn[output])
                elif r['type']=='gopIOL_Cell_9':
                    checks={'BUF_MODE':'IBUF','CP_IDLY_EN':'FALSE','CP_IDYN_EN':'FALSE','CP_ZHOLD_EN':'FALSE',
                            'CP_DYN_CLKPOL':'FALSE','CP_IDFFEN':'FALSE','CP_ILTHEN':'FALSE','CP_DDRI_EN':'FALSE',
                            'CP_DES_DDREN':'FALSE','CP_DES_SDREN':'FALSE','CP_D_POL0':'FALSE','CP_D_SEL0':0,
                            'CP_D_SEL1':0,'CP_D_SEL2':0,'CP_D_SEL3':0}
                    require(port=='DI' and all(parameter(r,k)==v for k,v in checks.items()),'Unproved input clock IOL identity mode: '+cell)
                    output=cell+'/DI_TO_CLK';require(output in self.pn,'Unconnected IOL clock output')
                    require(not any(cell+'/'+p in self.pn for p in ['ICLK','ICLKB','ICLKDIV','DYN_CLKPOL','IDLY_SEL']),'Active IOL state/control in clock identity route')
                    edges[cell]={'cell':cell,'type':r['type'],'pins':[pin,output],'polarity':'identity','parameters':checks}
                    queue.append(self.pn[output])
                elif r['type']=='gopHCKB':
                    require(port=='CLKIN' and parameter(r,'CP_MODE_SEL')=='DISABLE' and cell+'/CLKOUT' in self.pn,'Unproved HCKB clock buffer mode: '+cell)
                    edges[cell]={'cell':cell,'type':r['type'],'pins':[pin,cell+'/CLKOUT'],'polarity':'identity','CP_MODE_SEL':'DISABLE'}
                    queue.append(self.pn[cell+'/CLKOUT'])
                elif r['type']=='gopCLKBUFG':
                    require(port=='CLK' and cell+'/CLKOUT' in self.pn,'Unconnected CLKBUFG')
                    edges[cell]={'cell':cell,'type':r['type'],'pins':[pin,cell+'/CLKOUT'],'polarity':'identity'}
                    queue.append(self.pn[cell+'/CLKOUT'])
                elif r['type']=='gopCLKROUTE':
                    output=cell+'/CR';inputpin=self.identity_input(output,clock=True)
                    require(pin==inputpin,'Camera clock connected to nonidentity clock-route control: '+pin)
                    require(output in self.pn,'Unconnected clock route output')
                    edges[cell]={'cell':cell,'type':r['type'],'pins':[inputpin,output],'polarity':'identity'}
                    queue.append(self.pn[output])
                elif r['type']=='bmsKEEPBUF_Cell_1':
                    strict_keepbuf(r)
                    output=cell+'/Z[0]';inputpin=self.identity_input(output,clock=True)
                    require(pin==inputpin,'Clock on wrong KEEPBUF lane: '+pin)
                    connected=output in self.pn
                    if connected:require(self.drivers(self.pn[output])==[output],'KEEPBUF output has additional driver')
                    else:require(not any(output in pp for pp in self.np.values()),'Inconsistent unconnected KEEPBUF output')
                    edges[cell]={'cell':cell,'type':r['type'],'pins':[inputpin,output],'polarity':'identity','WIDTH':1,'official_model':'bmsPrim.v: assign Z = I','output_connected':connected,'disposition':'identity_forward' if connected else 'identity_terminal_no_output_net_no_storage'}
                    if connected:queue.append(self.pn[output])
                elif transparent(r,clock=True):
                    ins=[p for p,x in r['ports'].items() if x['direction']=='INPUT']
                    outs=[p for p,x in r['ports'].items() if x['direction']=='OUTPUT']
                    require(len(ins)==len(outs)==1,'Clock gate is not transparent: '+cell)
                    linked=[cell+'/'+p for p in ins+outs]
                    require(all(p in self.pn for p in linked),'Unconnected clock buffer: '+cell)
                    edges[cell]={'cell':cell,'type':r['type'],'pins':linked,'polarity':'inverted' if r['type'] in {'bmsWIDEINV','bmsINV','GTP_INV'} else 'identity'}
                    queue.extend(self.pn[p] for p in linked)
                elif v['direction']=='INPUT':
                    allowed=r['type'].startswith(('bmsWIDEDFF','GTP_DFF','GTP_DRM','gopQ','gopSRL2','gopLUT5','gopLUT6','gopLUT7','gopLUT8','gopDRM18K','gopDRM36K'))
                    isclock=port in self.clock_ports(cell)
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
        cp=r.clock_ports(cell)
        require(len(cp)==1,'ACK launch clock ambiguous')
        launch=cell+'/'+cp[0];first=lookup[(cam,'ack_sync',0)]
        require(not r.equal(launch,first['CLK']),'ACK first stage is not cross-domain')
        ack.append({'camera':cam,'launch_CLK':launch,'capture_D':first['D']})
    return {'status':'PASS','rows':rows,'chains':chains,'reset':resets,'ordinary_pairs':ordinary,
            'ack_first':ack,'independent_registers':60,'independent_sync':28,'independent_reset':32,
            'limits':['Structural new-graph binding only; INIT/GRS/async polarity and clock roots need endpoint audit',
                      'Recovery/removal/MPW/setup/hold and routed independence need actual two-corner STA']}
