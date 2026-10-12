"""Parse only successful export_02 ADIF; retain actual cells/pins and connectivity."""
from pathlib import Path
import re,json,hashlib,collections,csv
HERE=Path(__file__).resolve().parent
BUILD=HERE.parent
def children(n,k):return [x for x in n if isinstance(x,list) and x and x[0]==k]
def child(n,k):return next(iter(children(n,k)),[])
def descend(n,k):
    if isinstance(n,list):
        if n and n[0]==k:yield n
        for x in n:
            if isinstance(x,list):yield from descend(x,k)
def name(x):
    if isinstance(x,list):
        if x[0]=='BIT':return '$constant_'+x[1][2].strip('"')
        if x[0]=='INDEXED':return name(x[1])+'['+x[2]+']'
        if x[0]=='ARRAY':return name(x[1])
    return x.lstrip('\\').strip('"')
def cell_record(n,v):
    iface=child(v,'INTERFACE'); cont=child(v,'CONTENTS')
    ports={}
    for p in children(iface,'PORT'):
        direction=child(p,'DIRECTION')[1]
        clock=any(a[1]=='PAP_IS_CLOCK_PIN' for a in children(p,'ATTRIBUTE'))
        names=[name(p[1])]
        if isinstance(p[1],list):names=[name(p[1])+f'[{i}]' for i in range(int(p[1][3]),int(p[1][2])+1)]
        for pn in names:ports[pn]={'direction':direction,'clock':clock}
    inst={}
    for i in children(cont,'INSTANCE'):
        ref=next(descend(i,'CELLREF'))
        view=next(descend(i,'VIEWREF'))
        inst[name(i[1])]={'type':name(ref[1]),'view':name(view[1]),'attributes':[a for a in children(i,'ATTRIBUTE')],
                          'parameters':children(i,'PARAMETERMAP') or children(i,'PARAMETER')}
    nets=[]
    for netnode in children(cont,'NET'):
        for j,c in enumerate(children(netnode,'CONNECT')):
            nr=child(c,'NETREF');nn=name(nr[1]) if nr else name(netnode[1])
            ep=[]
            for p in children(c,'PORTREF'):
                ir=child(p,'INSTREF');ep.append((name(ir[1]) if ir else '',name(p[1])))
            nets.append((nn,ep))
    for c in children(cont,'CONNECT'):
        nr=child(c,'NETREF');nn=name(nr[1]);ep=[]
        for p in children(c,'PORTREF'):
            ir=child(p,'INSTREF');ep.append((name(ir[1]) if ir else '',name(p[1])))
        nets.append((nn,ep))
    return {'ports':ports,'instances':inst,'nets':nets,'parameters':children(n,'PARAMETER')}
def main():
    raw=(BUILD/'synthesis_export_02/synthesis_dump.txt').read_bytes()
    cells={};stack=[]
    for match in re.finditer(r'"(?:[^"\\]|\\.)*"|\\[^\s]+|[()]|[^\s()]+',raw.decode('utf8',errors='replace')):
        t=match.group()
        if t=='(':stack.append([])
        elif t==')':
            n=stack.pop()
            if n and n[0]=='CELL':
                ct=name(n[1])
                for v in children(n,'VIEW'):
                    key=(ct,name(v[1]));assert key not in cells,key
                    cells[key]=cell_record(n,v)
                n=['PARSED_CELL',ct]
            if stack:stack[-1].append(n)
        else:stack[-1].append(t)
    parent={};primitives={};pin_net={};net_names={}
    def root(a):
        parent.setdefault(a,a)
        while parent[a]!=a:parent[a]=parent[parent[a]];a=parent[a]
        return a
    def union(a,b):parent[root(a)]=root(b)
    def walk(ct,view,path):
        c=cells[(ct,view)]
        for nn,eps in c['nets']:
            net=path+'/@'+nn;root(net)
            for ins,p in eps:
                pin=((path+'/'+ins if ins else path)+'/'+p).lstrip('/');union(pin,net)
        for ins,rec in c['instances'].items():
            ip=(path+'/'+ins).lstrip('/')
            definition=cells[(rec['type'],rec['view'])]
            if definition['instances']:walk(rec['type'],rec['view'],ip)
            else:primitives[ip]={**rec,'ports':definition['ports'],'default_parameters':definition['parameters']}
    topviews=[view for ct,view in cells if ct=='v7_sdt_top'];assert len(topviews)==1,topviews
    walk('v7_sdt_top',topviews[0],'')
    groups=collections.defaultdict(list)
    for a in parent:groups[root(a)].append(a)
    for ip,r in primitives.items():
        for pn in r['ports']:
            pin=ip+'/'+pn
            if pin in parent:pin_net[pin]=root(pin)
    netpins=collections.defaultdict(list)
    for p,n in pin_net.items():netpins[n].append(p)
    def reg(ip):
        r=primitives[ip]; cp=[p for p,a in r['ports'].items() if a['clock']]
        return {'cell':ip,'type':r['type'],'pins':{p:ip+'/'+p for p in r['ports']},
                'clock_pins':cp,'clock_nets':{p:[a for a in groups.get(pin_net.get(ip+'/'+p,''),[]) if '/@' in a or '/' not in a] for p in cp},
                'attributes':r['attributes'],'parameters':r['parameters']}
    bundles=[];unresolved=[]
    for cam in range(4):
        prefix=f'source_diagnostics/cameras[{cam}].source/'
        for bit in range(512):
            m=prefix+f'mailbox[{bit}]';h=prefix+f'host_bank[{bit}]'
            rec={'camera':cam,'logical_bit':bit,'launch':reg(m) if m in primitives else None,
                 'capture':reg(h) if h in primitives else None}
            # No inference for missing optimized bits: all aliases are resolved by actual nets below.
            qnet=pin_net.get(m+'/Q');dnet=pin_net.get(h+'/D')
            rec['direct_q_to_d']=bool(qnet and qnet==dnet)
            rec['q_fanout']=netpins.get(qnet,[])
            if not rec['direct_q_to_d']:unresolved.append([cam,bit])
            bundles.append(rec)
    selected={}
    for ip,r in primitives.items():
        if not r['type'].startswith('GTP_DFF'):continue
        cl=None
        if ip.startswith('source_diagnostics/'):
            leaf=ip.split('/')[-1]
            if re.match(r'(req_sync|ack_sync|overrun_sync)\[0\]',leaf):cl='cdc_first'
            elif re.match(r'(req_sync|ack_sync|overrun_sync)\[[12]\]',leaf):cl='sync_later'
            elif re.match(r'(cr|hr)\[',leaf) or 'reset_pipe[' in leaf:cl='reset_chain'
            elif 'mailbox[' in leaf:cl='mailbox'
            elif 'host_bank[' in leaf:cl='host_bank'
            else:cl='ordinary_diagnostic'
        elif ip.endswith(('cmos_frame_valid_r','cmos_frame_vsync_r')):cl='negedge_binding'
        if cl:selected[ip]={'classification':cl,**reg(ip)}
    (HERE/'objects.json').write_text(json.dumps({'dump_sha256':hashlib.sha256(raw).hexdigest(),
        'bundles':bundles,'classified_registers':selected,'unresolved_direct_bits':unresolved},indent=2))
    (HERE/'graph.json').write_text(json.dumps({'primitives':primitives,'pin_net':pin_net,'netpins':netpins,'net_aliases':groups}))
    summary={'cells':len({ct for ct,view in cells}),'cell_views':len(cells),'primitives':len(primitives),'bundle_logical_bits':len(bundles),
        'actual_mailbox':sum(r['launch'] is not None for r in bundles),'actual_host_bank':sum(r['capture'] is not None for r in bundles),
        'direct_bits':sum(r['direct_q_to_d'] for r in bundles),'unresolved_direct_bits':unresolved,
        'class_counts':dict(collections.Counter(r['classification'] for r in selected.values()))}
    (HERE/'object_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps({k:v for k,v in summary.items() if k!='unresolved_direct_bits'},indent=2))
if __name__=='__main__':main()
