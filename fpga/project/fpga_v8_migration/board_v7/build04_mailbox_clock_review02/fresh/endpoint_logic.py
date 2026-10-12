"""Conservative bit evaluation of actual exported combinational cones."""
import itertools,re
def evaluate(g,net,parameters,roots=None,seen=None):
    roots={} if roots is None else roots
    seen=set() if seen is None else set(seen)
    if net is None or net in seen:return None
    seen.add(net)
    aliases=g['net_aliases'].get(net,[])
    rootvalues={v for name,v in roots.items() if any(a in {'/@'+name,'/'+name,name} for a in aliases)}
    if len(rootvalues)==1:return next(iter(rootvalues))
    for bit in [0,1]:
        if any(a.endswith('/@$constant_'+str(bit)) for a in aliases):return bit
    drivers=[p for p in g['netpins'].get(net,[]) if g['primitives'][p.rsplit('/',1)[0]]['ports'][p.rsplit('/',1)[1]]['direction']=='OUTPUT']
    if len(drivers)!=1:return None
    cell,port=drivers[0].rsplit('/',1);rec=g['primitives'][cell];typ=rec['type'];params=parameters(rec)
    if typ in {'GTP_GND','GND'}:return 0
    if typ in {'GTP_VCC','VCC'}:return 1
    if typ=='GTP_CONSTANT':return int(params['VALUE']) if params.get('VALUE') in {'0','1'} else None
    inputs=[p for p,r in rec['ports'].items() if r['direction']=='INPUT' and cell+'/'+p in g['pin_net']]
    def val(p):return evaluate(g,g['pin_net'].get(cell+'/'+p),parameters,roots,seen)
    if 'BUF' in typ.upper():
        index=re.search(r'\[\d+\]$',port)
        if index:inputs=[p for p in inputs if p.endswith(index[0])]
        if len(inputs)==1:return val(inputs[0])
    if typ=='bmsREDOR':
        vals=[val(p) for p in inputs]
        if 1 in vals:return 1
        return 0 if vals and all(v==0 for v in vals) else None
    if (typ.startswith('GTP_LUT') and port=='Z') or (typ.startswith('gopLUT') and port=='L6'):
        lutpins=[p for p in rec['ports'] if re.fullmatch(r'I\d+',p)]
        lutpins.sort(key=lambda p:int(p[1:]))
        bits=params.get('INIT','')
        if not re.fullmatch('[01]+',bits) or len(bits)!=2**len(lutpins):return None
        vals=[val(p) for p in lutpins];unknown=[i for i,v in enumerate(vals) if v is None]
        outputs=set()
        for assignment in itertools.product([0,1],repeat=len(unknown)):
            trial=list(vals)
            for i,v in zip(unknown,assignment):trial[i]=v
            index=sum(v<<i for i,v in enumerate(trial));outputs.add(int(bits[-1-index]))
        return next(iter(outputs)) if len(outputs)==1 else None
    return None
