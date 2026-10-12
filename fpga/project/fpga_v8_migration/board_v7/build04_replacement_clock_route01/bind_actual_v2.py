from pathlib import Path
import json,re,hashlib,sys
sys.dont_write_bytecode=True
E=Path(__file__).resolve().parent;BOARD=E.parent
sys.path.insert(0,str(BOARD/'build04_final_route_runtime01/runtime'))
from graph_adapter import Resolver
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,o):
 with (E/n).open('x',encoding='ascii') as f:json.dump(o,f,indent=2,ensure_ascii=True)
def main():
 gp=E/'routed02/analysis/graph.json';g=json.loads(gp.read_bytes());rr=Resolver(g);pr=g['primitives'];pn=g['pin_net'];np=g['netpins']
 an={a:n for n,aa in g['net_aliases'].items() for a in aa}
 def output(logical):
  n=an.get('/@'+logical)
  if n is None:raise RuntimeError('Missing native alias '+logical)
  q,trace=rr.trace_driver(n);return q,n,trace
 targets=json.loads((BOARD/'build04_final_route_runtime01/physical_targets2560.json').read_bytes());seen=set();pairs=[];errors=[]
 for row in targets:
  key=(row['start'],row['end'])
  if key in seen:continue
  seen.add(key)
  try:
   cq,cn,ct=output(row['end'].rsplit('/',1)[0]);cc=cq.rsplit('/',1)[0];d=cc+'/D'
   q,trace=rr.trace_driver(pn[d]);lc=q.rsplit('/',1)[0];clk=lc+'/CLK'
   lq,ln,lt=output(row['start'].rsplit('/',1)[0])
   if q!=lq or clk not in pn:raise RuntimeError('Fresh source alias/CLK mismatch')
   pairs.append({'logical_start':row['start'],'logical_end':row['end'],'start':clk,'end':d,'launch_Q':q,'capture_Q':cq,'launch_type':pr[lc]['type'],'capture_type':pr[cc]['type'],'logical_members':row['logical_members'],'actual_trace':trace})
  except Exception as ex:errors.append({'target':row,'error':str(ex)})
 if not (E/'fresh_mailbox_pairs_v2.json').exists():save('fresh_mailbox_pairs_v2.json',{'graph_sha256':sha(gp),'pairs':pairs,'errors':errors,'resolved':len(pairs),'unique_actual':len({(x['start'],x['end']) for x in pairs}),'corner_targets':len(pairs)*2,'logical_contract_count':2048,'timing_coverage_measured':False,'supersedes':'fresh_mailbox_pairs.json; five native identity CLKROUTE buffers traced to actual source Q'})
 pcf=E/'work/device_map/v7_sdt_top.pcf';sitecmd={m[1].decode():m[2].decode() for m in re.finditer(rb'def_inst_site\s+\{([^}]+)\}\s+([^\s]+)',pcf.read_bytes())}
 raw=(E/'routed_dump.txt').read_bytes();placements={}
 pattern=rb'\(INSTANNOTATE\s+\(INSTREF\s+([^\s)]+)\s*\)\s+\(PLACE\s+([^\s]+)\s+\(DEVINSTREF\s+([^\s]+)\s+\(SITEREF\s+(\d+)\s+(\d+)\)'
 for m in re.finditer(pattern,raw):placements.setdefault(m[1].decode().lstrip('\\'),[]).append(m[3].decode()+'_'+m[4].decode()+'_'+m[5].decode())
 rows=json.loads((BOARD/'build04_mapped_endpoint_review02/rows60.json').read_bytes())['rows'];bound=[]
 for row in rows:
  anchor=row['synthesis_target'];wanted=[(c,s) for c,s in sitecmd.items() if c.startswith(anchor+'/')]
  cand=[c for c,r in pr.items() if c.startswith(anchor+'/') and c+'/CLK' in pn and any(c+'/'+p in pn for p in ['Q','L6Q','L5Q'])]
  item={'logical':row['logical'],'native_PCF_targets':wanted,'actual_candidates':cand}
  if len(cand)==1 and len(wanted)==1:
   c=cand[0];site=placements.get(c,[]);item.update(actual_cell=c,type=pr[c]['type'],D=c+'/D' if c+'/D' in pn else None,CLK=c+'/CLK',actual_sites=site,expected_native_PCF_site=wanted[0][1],site_matches=site==[wanted[0][1]],Q_outputs=[c+'/'+p for p in ['Q','L6Q','L5Q'] if c+'/'+p in pn])
  else:item['error']='Nonunique actual storage or native PCF target'
  bound.append(item)
 save('fresh_distinct60_sites_v3.json',{'native_PCF_sha256':sha(pcf),'graph_sha256':sha(gp),'rows':bound,'distinct_cells':len({r['actual_cell'] for r in bound if 'actual_cell' in r}),'distinct_sites':len({s for r in bound for s in r.get('actual_sites',[])}),'site_match_rows':sum(r.get('site_matches',False) for r in bound),'scope':'Basic actual storage/clock/site correspondence; native escaped identifiers and optional whitespace decoded; no new primitive formal gate'})
 mgp=BOARD/'source_diagnostics_timing_build_04/evidence/runtime/mapping60_01/mapping/analysis/graph.json';mg=json.loads(mgp.read_bytes())
 def params(r):
  out={}
  def walk(x):
   if isinstance(x,list):
    if x and x[0]=='PARAMETER':out[x[1]]=x[2:]
    else:
     for s in x:walk(s)
  walk(r.get('default_parameters',[]));walk(r.get('parameters',[]));return out
 motion=[];hsst=[]
 for c,mr in mg['primitives'].items():
  if 'u_motion_tap/u_detector/history_' in c and mr['type'].startswith('gopDRM'):
   ar=pr.get(c);motion.append({'cell':c,'fresh_type':ar['type'] if ar else None,'mapped_parameters':params(mr),'fresh_parameters':params(ar) if ar else None,'parameters_equal':bool(ar and params(ar)==params(mr)),'ports_equal':bool(ar and ar['ports']==mr['ports']),'native_sites':placements.get(c,[])})
  if c.endswith('/gophsst'):
   ar=pr.get(c);hsst.append({'cell':c,'parameters_equal':bool(ar and params(ar)==params(mr)),'native_sites':placements.get(c,[]),'expected_PCF_site':sitecmd.get(c)})
 save('HSST_motion_native_retention_v3.json',{'mapped_graph_sha256':sha(mgp),'fresh_graph_sha256':sha(gp),'motion_count':len(motion),'motion_rows':motion,'HSST_rows':hsst})
 print('FRESH PAIRS',len(pairs),'ERRORS',len(errors),'60 DISTINCT',len({r['actual_cell'] for r in bound if 'actual_cell' in r}),'60 SITE MATCH',sum(r.get('site_matches',False) for r in bound),'MOTION',len(motion))
if __name__=='__main__':main()
