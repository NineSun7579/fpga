"""Read actual exported CDB and primitive annotations; no DB mutation."""
import json,re,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
from runner import E,sha
from native_audit import pairs
def sexpr(raw):
 stack=[];root=None
 for m in re.finditer(rb'"(?:[^"\\]|\\.)*"|[()]|[^\s()]+',raw):
  tok=m[0]
  if tok==b'(':stack.append([])
  elif tok==b')':
   node=stack.pop()
   if stack:stack[-1].append(node)
   else:root=node
  else:stack[-1].append(tok.decode('ascii','backslashreplace'))
 return root
def fields(node):return {v[0]:v[1:] for v in node[1:] if isinstance(v,list) and v}
def review(graphfile,cdbfile,expected,out):
 g=json.loads(Path(graphfile).read_bytes());raw=Path(cdbfile).read_bytes();root=sexpr(raw)
 assert root[0]=='CDB' and not re.search(rb'\(CLKGP\b',raw)
 mm={}
 for n in root[1:]:
  if isinstance(n,list) and n and n[0]=='MMD':
   f=fields(n)
   if f.get('DELAY')==['15238']:
    assert f.get('DATAPATH_ONLY')==['1'];mm[f['CDBID'][0]]=f
 assert len(mm)==4,('Expected four native 15238 MMD entries',mm)
 rows=[];ids_by_cam={i:set() for i in range(4)}
 for p in pairs(g,expected):
  def matches(pin,typ):
   cell,port=pin.rsplit('/',1);out=[]
   for n in g['primitives'][cell]['cdb_entries']:
    f=fields(n)
    if f.get('CDBID',[''])[0] in mm and f.get('PINNAME')==[port] and f.get('TYPE')==[typ]:out.append(f['CDBID'][0])
   return set(out)
  common=matches(p['launch_CLK'],'1')&matches(p['capture_D'],'3')
  assert len(common)==1,('Actual native exception binding absent/ambiguous',p,common)
  ident=next(iter(common));ids_by_cam[p['camera']].add(ident)
  rows.append({**p,'MMD_CDBID':ident,'delay_ps':15238,'datapath_only':True})
 assert all(len(v)==1 for v in ids_by_cam.values()) and len(set.union(*ids_by_cam.values()))==4
 result={'passed':True,'pairs':len(rows),'budget_entries':mm,'camera_CDBIDs':{str(k):sorted(v) for k,v in ids_by_cam.items()},'rows':rows,'graph_sha256':sha(graphfile),'CDB_sha256':sha(cdbfile)}
 with Path(out).open('x',encoding='ascii') as f:json.dump(result,f,indent=2)
 print('Native exact budget binding PASS:',len(rows),flush=True)
 return result
if __name__=='__main__':
 label=sys.argv[1];count=1320 if label=='synthesis_native' else 1280
 review(E/label/'analysis/graph.json',E/(label+'_CDB_raw.txt'),count,E/(label+'_exact_pair_binding_'+str(time.time_ns())+'.json'))
