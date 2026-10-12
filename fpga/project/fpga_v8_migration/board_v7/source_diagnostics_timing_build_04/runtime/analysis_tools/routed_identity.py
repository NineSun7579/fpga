"""Fresh routed truth-table and identity-path proof; never consumes review.json."""
import ast
import collections
import hashlib
from pathlib import Path
from graph_adapter import Resolver, require, canon, parameter

REFERENCE_SHA='35c420048f567d0b33b04444f4744f55def87d1accc352c813c8ddf93438f3ae'
def truth_proof(g,sg,m,reference):
    source=Path(reference).read_bytes()
    require(hashlib.sha256(source).hexdigest()==REFERENCE_SHA,'Reviewed truth-function source changed; re-review required')
    tree=ast.parse(source)
    names={'descendants','canon','net_for','param','lut_expr','output_expr','symbolic','support','evaluate','trace_driver'}
    functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    require(len(functions)==len(names),'Truth proof function inventory changed')
    pr,pn,aliases=g['primitives'],g['pin_net'],g['net_aliases']
    drivers={n:[p for p in pp if pr[p.rsplit('/',1)[0]]['ports'][p.rsplit('/',1)[1]]['direction']=='OUTPUT'] for n,pp in g['netpins'].items()}
    an=collections.defaultdict(set)
    for n,aa in aliases.items():
        for a in aa:an[canon(a)].add(n)
    scope={'g':g,'sg':sg,'m':m,'pr':pr,'pn':pn,'aliases':aliases,'drivers':drivers,'an':an,'visited':set()}
    exec(compile(ast.Module(body=functions,type_ignores=[]),str(reference),'exec'),scope)
    original=scope['output_expr']
    def output(p,ov,memo,active,combinational=False):
        cell,port=p.rsplit('/',1)
        if port not in {'Q','Q0','CR0','L5Q','L6Q','L8Q'}:
            pin=Resolver(g).identity_input(p)
            if pin is not None:return scope['symbolic'](pn[pin],ov,memo,active)
        return original(p,ov,memo,active,combinational)
    scope['output_expr']=output
    scope['trace_driver']=Resolver(g).trace_driver
    require(len(m['resolved'])==2048 and all(row['camera']==i//512 and row['logical_bit']==i%512 for i,row in enumerate(m['resolved'])),
            'Manifest logical ordering/count changed')
    # Only the reviewed exhaustive 4*16*32 data loop; no global disk reads/writes.
    loop=next(n for n in tree.body if isinstance(n,ast.For) and isinstance(n.target,ast.Name) and n.target.id=='cam')
    scope.update(rows=[],errors=[],pairs={})
    exec(compile(ast.Module(body=[loop],type_ignores=[]),str(reference),'exec'),scope)
    rows,errors=scope['rows'],scope['errors']
    counts=dict(collections.Counter(r['kind'] for r in rows))
    pairs=[]
    for row in rows:
        if row['kind']!='register':continue
        launch,capture=row['launch_CLK'],row['capture_D'];r=Resolver(g)
        require(r.clock_ports(launch.rsplit('/',1)[0])==['CLK'],'Actual mailbox launch CLK schema changed')
        q,trace=r.trace_driver(pn[capture]);require(q==row['launch_Q'],'Independent identity trace disagrees with LUT proof')
        pairs.append({'logical':[m['resolved'][row['camera']*512+row['logical_bit']]['mapping']['launch_CLK'],
                                 m['resolved'][row['camera']*512+row['logical_bit']]['mapping']['capture_D']],
                      'physical':[launch,capture],'launch_Q':q,'capture_Q':row['capture_Q'],
                      'direct_Q_to_D':pn[q]==pn[capture],'connection_semantics':'identity_path',
                      'driver_trace':trace,'camera':row['camera'],'logical_bit':row['logical_bit']})
    unique={tuple(p['physical']) for p in pairs}
    percam={cam:dict(collections.Counter(r['kind'] for r in rows if r['camera']==cam)) for cam in range(4)}
    passed=not errors and len(rows)==2048 and counts=={'register':1320,'constant_zero':728} and len(unique)==1320 and all(v=={'register':330,'constant_zero':182} for v in percam.values())
    return {'passed':passed,'resolved':rows,'errors':errors,'kind_counts':counts,'per_camera':percam,
            'pairs':pairs,'physical_pair_count':len(unique),'reference_sha256':REFERENCE_SHA,
            'visited_outputs':sorted(scope['visited']),'proof':'fresh actual routed read LUT truth tables for all 2048 bits; unknown constants remain free variables'}

def bind_clock_leaf(g,logical,logs):
    """Exact storage clones or explicit tool cleanup; no missing-name waiver."""
    cell,port=logical.rsplit('/',1);r=Resolver(g)
    candidates=[k+'/'+port for k in r.pr if (k==cell or k.startswith(cell+'/')) and port in r.pr[k]['ports'] and k+'/'+port in r.pn]
    for pin in candidates:
        require(port in r.clock_ports(pin.rsplit('/',1)[0]),'Leaf is not a schema storage clock: '+pin)
    if not candidates:
        evidence=[]
        for path in logs:
            raw=Path(path).read_bytes()
            for i,line in enumerate(raw.splitlines(),1):
                if b'Public-4008' in line and b'dangling and will be cleaned' in line and (b"Instance '"+cell.encode('ascii')+b"'") in line:
                    evidence.append({'path':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'line':i,'text':line.decode('gbk',errors='replace')})
        require(evidence,'Missing surviving clock leaf without actual cleanup evidence: '+logical)
        require(not any(k==cell or k.startswith(cell+'/') for k in r.pr),'Cleanup warning but physical leaf survives: '+logical)
        return {'logical':logical,'physical':[],'status':'tool_cleanup','cleanup_evidence':evidence}
    if len(candidates)>1:
        cells=[p.rsplit('/',1)[0] for p in candidates]
        records=[]
        for k in cells:
            rec=r.pr[k];require(rec['type'].startswith(('gopQ','GTP_DFF')),'Unsupported clone storage schema: '+k)
            records.append({'type':rec['type'],'nets':{p:r.pn.get(k+'/'+p) for p in ['D','CLK','RS','P','C','CE']},
                            'parameters':{key:parameter(rec,key) for key in set(parameter_keys(rec))},
                            'cell':k,'output_fanout':{p:r.np.get(r.pn.get(k+'/'+p),[]) for p,v in rec['ports'].items() if v['direction']=='OUTPUT'}})
        first=records[0]
        require(all(x['type']==first['type'] and x['nets']==first['nets'] and x['parameters']==first['parameters'] for x in records),'Non-equivalent storage clones: '+logical)
        require(all(x['nets']['D'] is not None and x['nets']['CLK'] is not None and x['output_fanout'] for x in records),'Unconnected clones')
        return {'logical':logical,'physical':sorted(candidates),'status':'equivalent_fanout_copies','clone_evidence':records}
    return {'logical':logical,'physical':candidates,'status':'unique_storage_clock'}

def parameter_keys(record):
    def walk(value):
        if isinstance(value,list):
            if value and value[0]=='PARAMETER':yield value[1]
            for child in value:yield from walk(child)
    return list(walk(record.get('default_parameters',[])))+list(walk(record.get('parameters',[])))
