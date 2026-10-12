"""Independent byte ADIF connectivity reader; no import of production parser.

Uses canonical qualified byte names and symmetric equivalence classes, then checks
ALL primitive pin memberships against the supplied full graph. Root strings and
parser aliases do not establish physical identity by themselves.
"""
from pathlib import Path
import collections,json,re,sys
sys.dont_write_bytecode=True
from setup_review import HERE,B04,sha,save
def kids(n,key):return [v for v in n[1:] if isinstance(v,list) and v and v[0]==key]
def one(n,key):return next(iter(kids(n,key)),[])
def find(n,key):
    if isinstance(n,list):
        if n and n[0]==key:yield n
        for v in n:yield from find(v,key)
def label(x):
    if isinstance(x,bytes):return x.lstrip(b'\\').strip(b'"').decode('ascii')
    if x[0]==b'BIT':return '$constant_'+x[1][2].strip(b'"').decode('ascii')
    if x[0]==b'INDEXED':return label(x[1])+'['+x[2].decode('ascii')+']'
    if x[0]==b'ARRAY':return label(x[1])
    raise RuntimeError('Unsupported raw name '+repr(x))
def read_cells(raw):
    cells={};stack=[]
    for m in re.finditer(rb'"(?:[^"\\]|\\.)*"|\\[^\s]+|[()]|[^\s()]+',raw):
        t=m.group()
        if t==b'(':stack.append([])
        elif t==b')':
            n=stack.pop()
            if n and n[0]==b'CELL':
                for view in kids(n,b'VIEW'):
                    ports=[];instances=[];nets=[]
                    for p in kids(one(view,b'INTERFACE'),b'PORT'):
                        names=[label(p[1])]
                        if isinstance(p[1],list) and p[1][0]==b'ARRAY':names=[label(p[1])+f'[{i}]' for i in range(int(p[1][3]),int(p[1][2])+1)]
                        ports.extend(names)
                    contents=one(view,b'CONTENTS')
                    for inst in kids(contents,b'INSTANCE'):
                        instances.append((label(inst[1]),label(next(find(inst,b'CELLREF'))[1]),label(next(find(inst,b'VIEWREF'))[1])))
                    for net in kids(contents,b'NET'):
                        for connection in kids(net,b'CONNECT'):
                            nr=one(connection,b'NETREF');name=label(nr[1]) if nr else label(net[1]);endpoints=[]
                            for p in kids(connection,b'PORTREF'):
                                ir=one(p,b'INSTREF');endpoints.append((label(ir[1]) if ir else '',label(p[1])))
                            nets.append((name,endpoints))
                    for connection in kids(contents,b'CONNECT'):
                        name=label(one(connection,b'NETREF')[1]);endpoints=[]
                        for p in kids(connection,b'PORTREF'):
                            ir=one(p,b'INSTREF');endpoints.append((label(ir[1]) if ir else '',label(p[1])))
                        nets.append((name,endpoints))
                    key=(label(n[1]),label(view[1]));assert key not in cells
                    cells[key]=(ports,instances,nets)
                n=[b'CONSUMED_CELL']
            if stack:stack[-1].append(n)
        else:stack[-1].append(t)
    assert not stack
    return cells
def check(stage):
    root=B04/'evidence/runtime'/stage;dump=root/'synthesis_export/synthesis_dump.txt';graph=root/'analysis/graph.json'
    cells=read_cells(dump.read_bytes());parent={};rank={};leaf_ports={}
    def rootof(v):
        if v not in parent:parent[v]=v;rank[v]=0
        if parent[v]!=v:parent[v]=rootof(parent[v])
        return parent[v]
    def connect(a,b):
        a,b=rootof(a),rootof(b)
        if a==b:return
        if rank[a]<rank[b]:a,b=b,a
        parent[b]=a
        if rank[a]==rank[b]:rank[a]+=1
    def pathcat(a,b):return a+'/'+b if a and b else (a or b)
    def flatten(key,path):
        ports,insts,nets=cells[key]
        for name,ends in nets:
            # A NETREF or PORTREF can contain a qualified hierarchical alias.
            # Canonicalize the complete qualified spelling, not tuple boundaries.
            net=('pin',path+'/@'+name)
            for inst,p in ends:connect(net,('pin',pathcat(pathcat(path,inst),p).lstrip('/')))
        for inst,typ,view in insts:
            childpath=pathcat(path,inst);childkey=(typ,view)
            if cells[childkey][1]:flatten(childkey,childpath)
            else:leaf_ports[childpath]=(typ,cells[childkey][0])
    top=[k for k in cells if k[0]=='v7_sdt_top'];assert len(top)==1
    flatten(top[0],'');del cells
    groups=collections.defaultdict(set);pinclasses={}
    for cell,(typ,ports) in leaf_ports.items():
        for p in ports:
            vertex=('pin',cell+'/'+p)
            if vertex in parent:
                pin=cell+'/'+p;cl=rootof(vertex);groups[cl].add(pin);pinclasses[pin]=cl
    g=json.loads(graph.read_bytes());assert set(leaf_ports)==set(g['primitives'])
    assert set(pinclasses)==set(g['pin_net'])
    errors=[];checked=0
    for pin,cl in pinclasses.items():
        if groups[cl]!=set(g['netpins'][g['pin_net'][pin]]):
            errors.append({'pin':pin,'raw':sorted(groups[cl]),'graph':g['netpins'][g['pin_net'][pin]]})
        checked+=1
    assert not errors,[(r['pin'],len(r['raw']),len(r['graph'])) for r in errors[:3]]
    witnesses=[]
    for cam in range(4):
        cell=f'source_diagnostics/cameras[{cam}].source/';suffix='/opit_0' if stage=='mapping60_01/mapping' else ''
        q=cell+'mailbox[240]'+suffix+'/Q';d=cell+'host_bank[240]'+suffix+'/D'
        if stage!='compile':
            assert groups[pinclasses[q]]=={q,d}
            assert not any(k==cell+f'{bank}[{480+i}]' or k.startswith(cell+f'{bank}[{480+i}]/') for k in leaf_ports for bank in ['mailbox','host_bank'] for i in range(32) if (0x53464401>>i)&1)
            witnesses.append({'camera':cam,'raw_equivalence_class':sorted(groups[pinclasses[q]]),'duplicate_cells_absent':True})
    result={'status':'PASS_OFFLINE_RAW_CONNECTIVITY_ONLY','stage':stage,'dump_sha256':sha(dump),'graph_sha256':sha(graph),'all_primitive_cells':len(leaf_ports),'all_connected_primitive_pins':checked,'all_pin_equivalence_classes':len(groups),'errors':errors,'camera_shared_pair_witnesses':witnesses,'mapped_storage_semantics_approved':False}
    save('independent_raw_'+stage.replace('/','_')+'.json',result)
    print(stage,'all primitive/pin memberships verified',checked,flush=True)
if __name__=='__main__':
    for stage in sys.argv[1:] or ['actual','mapping60_01/mapping','compile']:check(stage)
