from pathlib import Path
import json,re,sys,tkinter,xml.etree.ElementTree as ET
from runner import E,W,B,F,sha,save
sys.path.insert(0,str(F/'runtime'))
from graph_adapter import Resolver,parameter
def cdb(label):
 dump=E/label/'synthesis_export/synthesis_dump.txt';raw=dump.read_bytes();start=raw.find(b'(CDB ');depth=0;stop=None
 assert start>=0,'Missing native CDB'
 for m in re.finditer(rb'"(?:[^"\\]|\\.)*"|[()]',raw[start:]):
  if m[0]==b'(':depth+=1
  elif m[0]==b')':
   depth-=1
   if depth==0:stop=start+m.end();break
 assert stop is not None
 c=raw[start:stop];p=E/(label+'_CDB_raw.txt')
 if p.exists():
  assert p.read_bytes()==c,'Previous native CDB differs'
  return c
 p.write_bytes(c)
 save(label+'_CDB_binding.json',{'dump_sha256':sha(dump),'CDB_sha256':sha(p),'start':start,'end':stop,'contains_15238':b'15238' in c,'clockgroup_count':len(re.findall(rb'\(CLOCKGROUP\b',c))})
 return c
def pairs(g,expected=1280):
 r=Resolver(g);rows=[]
 for cell,rec in g['primitives'].items():
  match=re.match(r'source_diagnostics/cameras\[(\d)\]\.source/host_bank\[',cell)
  if not match:continue
  for port,desc in rec['ports'].items():
   if port!='D' or desc['direction']!='INPUT' or cell+'/D' not in g['pin_net']:continue
   q,trace=r.trace_driver(g['pin_net'][cell+'/D']);launch=q.rsplit('/',1)[0]
   assert '/mailbox[' in launch and q.rsplit('/',1)[1] in {'Q','Q0','L6Q','L5Q'},('Unexpected host driver',cell,q)
   assert len(r.clock_ports(launch))==1
   rows.append({'camera':int(match[1]),'launch_Q':q,'launch_CLK':launch+'/'+r.clock_ports(launch)[0],'capture_D':cell+'/D','capture_CLK':cell+'/'+r.clock_ports(cell)[0],'trace':trace})
 assert len(rows)==expected and len({(x['launch_CLK'],x['capture_D']) for x in rows})==expected,('New physical pair count',len(rows),expected)
 assert all(sum(x['camera']==cam for x in rows)==expected//4 for cam in range(4))
 if expected in {1320,1284}:
  constants=[x for x in rows if int(re.search(r'/host_bank\[(\d+)\]',x['capture_D'])[1])>=480]
  assert len(constants)==expected-1280
  assert all(g['pin_net'].get(x['launch_CLK'].rsplit('/',1)[0]+'/D','').endswith('/@$constant_1') for x in constants),'Signature register must have native constant-one D'
  if expected==1284:
   assert all(not g['primitives'][x['launch_CLK'].rsplit('/',1)[0]]['cdb_entries'] and not g['primitives'][x['capture_D'].rsplit('/',1)[0]]['cdb_entries'] for x in constants),'Residual signature must be unannotated'
 return rows
def sites(g):
 t=tkinter.Tcl();draft=W/'constraints_live/production60.lcf';pcf=W/'device_map/v7_sdt_top.pcf'
 targets=[t.splitlist(line) for line in draft.read_text(encoding='ascii').splitlines() if line.strip() and not line.lstrip().startswith('#')]
 actual=[t.splitlist(line) for line in pcf.read_text(encoding='ascii').splitlines() if line.startswith('def_inst_site ')]
 rows=[]
 for cmd in targets:
  assert len(cmd)==4 and cmd[0]=='define_attribute' and cmd[2]=='PAP_LOC'
  source=cmd[1][2:];site=cmd[3]
  cells=[c for c in g['primitives'] if c==source or c.startswith(source+'/')]
  storage=[c for c in cells if g['primitives'][c]['type']=='gopQ']
  assert len(storage)==1,(source,storage)
  cell=storage[0];entries=[x for x in actual if x[1].lstrip('\\')==cell]
  assert len(entries)==1 and entries[0][2]==site,(source,site,entries)
  rows.append({'source':source,'cell':cell,'site':site,'pcf':entries[0]})
 assert len(rows)==len({x['cell'] for x in rows})==len({x['site'] for x in rows})==60
 save('native60_site_binding.json',{'rows':rows,'passed':True,'draft_sha256':sha(draft),'pcf_sha256':sha(pcf)})
def messages():
 rows=[]
 for stage,filename in [('compile','cmr.db'),('synthesize','snr.db'),('device_map','dmr.db')]:
  p=W/stage/filename;tables=list(ET.parse(p).getroot().iter('table'));errors=[]
  for table in tables:
   if 'message' not in table.get('id','').lower():continue
   for row in table.findall('row'):
    values=[v.text or '' for v in row.findall('data')]
    if any(v.strip().lower() in {'error','fatal'} for v in values):errors.append(values)
  rows.append({'stage':stage,'file':str(p),'sha256':sha(p),'native_errors':errors})
  assert not errors,('Native errors',stage,errors)
 save('native_stage_message_audit.json',rows)
def exact_cdb(label):
 raw=cdb(label);stack=[];root=None
 for match in re.finditer(rb'"(?:[^"\\]|\\.)*"|\\[^\s]+|[()]|[^\s()]+',raw):
  token=match[0]
  if token==b'(':stack.append([])
  elif token==b')':
   item=stack.pop()
   if stack:stack[-1].append(item)
   else:root=item
  else:stack[-1].append(token.decode('ascii','backslashreplace'))
 assert root and root[0]=='CDB'
 counts={};maxentries=[];falseentries=[]
 for item in root[1:]:
  if not isinstance(item,list) or not item:continue
  counts[item[0]]=counts.get(item[0],0)+1
  if any(isinstance(x,str) and '15238' in x for x in item):maxentries.append(item)
  if item[0]=='CLKGP':raise RuntimeError('Native CDB retains clock group')
 save(label+'_CDB_structure.json',{'counts':counts,'budget_entries':maxentries,'CDB_sha256':sha(E/(label+'_CDB_raw.txt'))})
 assert len(maxentries)==4,('Native exact maxdelay record count',len(maxentries))
 return root,maxentries
if __name__=='__main__':
 label=sys.argv[1];cdb(label)
 if label!='compile_native':
  g=json.loads((E/label/'analysis/graph.json').read_bytes());rows=pairs(g)
  save(label+'_pairs1280.json',{'rows':rows,'graph_sha256':sha(E/label/'analysis/graph.json')})
  if label=='mapping_native':sites(g)
