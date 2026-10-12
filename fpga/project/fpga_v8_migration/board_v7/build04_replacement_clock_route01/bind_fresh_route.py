from pathlib import Path
import json,re,hashlib,sys,importlib.util,shutil,collections
sys.dont_write_bytecode=True
E=Path(__file__).resolve().parent;BOARD=E.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):
 with (E/n).open('x',encoding='ascii') as f:json.dump(x,f,indent=2,ensure_ascii=True)
def main():
 src=BOARD/'source_diagnostics_timing_build_04/runtime/analysis_tools/parse_objects.py'
 if not (E/'native_graph_rawreceipt.json').is_file():raise RuntimeError('Require completed official graph export receipt before consuming dump')
 dest=E/'routed02/analysis';dest.mkdir(parents=True);exp=E/'routed02/synthesis_export';exp.mkdir()
 shutil.copy2(E/'routed_dump.txt',exp/'synthesis_dump.txt');shutil.copy2(src,dest/'parse_objects.py')
 spec=importlib.util.spec_from_file_location('fresh_parser',dest/'parse_objects.py');parser=importlib.util.module_from_spec(spec);spec.loader.exec_module(parser);parser.main()
 g=json.loads((dest/'graph.json').read_bytes());pr=g['primitives'];pn=g['pin_net'];np=g['netpins'];aliases=g['net_aliases']
 ds={n:[p for p in pins if pr[p.rsplit('/',1)[0]]['ports'][p.rsplit('/',1)[1]]['direction']=='OUTPUT'] for n,pins in np.items()}
 aliasnet={s:n for n,aa in aliases.items() for s in aa}
 def output(logical):
  n=aliasnet.get('/@'+logical)
  if n is None:n=aliasnet.get(logical.replace('/source/','/source/@'))
  if n is None:raise RuntimeError('Alias not found '+logical)
  driver=ds.get(n,[])
  if len(driver)!=1:raise RuntimeError('Nonunique driver '+logical+': '+str(driver))
  return driver[0],n
 targets=json.loads((BOARD/'build04_final_route_runtime01/physical_targets2560.json').read_bytes())
 seen=set();pairs=[];issues=[]
 for row in targets:
  key=(row['start'],row['end'])
  if key in seen:continue
  seen.add(key)
  try:
   logical_end=row['end'].rsplit('/',1)[0];cq,cn=output(logical_end);cc=cq.rsplit('/',1)[0]
   d=cc+'/D';dn=pn[d];driver=ds[dn]
   if len(driver)!=1:raise RuntimeError('Nonunique fresh source '+repr(driver))
   q=driver[0];lc=q.rsplit('/',1)[0];clk=lc+'/CLK'
   if clk not in pn:raise RuntimeError('No launch CLK')
   logical_start=row['start'].rsplit('/',1)[0];expectedq,expectedn=output(logical_start)
   if expectedq!=q:raise RuntimeError('Actual fresh Q/D differs from logical source alias')
   pairs.append({'logical_start':row['start'],'logical_end':row['end'],'start':clk,'end':d,'launch_Q':q,'capture_Q':cq,'launch_type':pr[lc]['type'],'capture_type':pr[cc]['type'],'logical_members':row['logical_members'],'direct_net':dn})
  except Exception as ex:issues.append({'target':row,'error':str(ex)})
 save('fresh_mailbox_pairs.json',{'graph_sha256':sha(dest/'graph.json'),'dump_sha256':sha(E/'routed_dump.txt'),'unique_expected':1280,'resolved':len(pairs),'unique_actual':len({(r['start'],r['end']) for r in pairs}),'pairs':pairs,'issues':issues,'timing_coverage_measured':False})
 rows=json.loads((BOARD/'build04_mapped_endpoint_review02/rows60.json').read_bytes())['rows'];bound=[]
 for row in rows:
  try:
   q,n=output(row['logical']);c=q.rsplit('/',1)[0];r=pr[c]
   sites=[x[2][1].strip('"') for x in r['attributes'] if x[1] in {'PAP_LOC','.SITE_NAME'}]
   sites=sorted(set(sites));bound.append({'logical':row['logical'],'actual_cell':c,'Q':q,'D':c+'/D','CLK':c+'/CLK','type':r['type'],'native_sites':sites,'expected_site':row['planned_site'],'same_site':sites==[row['planned_site']],'connected_D_CLK':c+'/D' in pn and c+'/CLK' in pn})
  except Exception as ex:bound.append({'logical':row['logical'],'error':str(ex)})
 save('fresh_distinct60_sites.json',{'rows':bound,'distinct_cells':len({r['actual_cell'] for r in bound if 'actual_cell' in r}),'distinct_sites':len({s for r in bound for s in r.get('native_sites',[])}),'exact_site_rows':sum(r.get('same_site',False) for r in bound)})
 mgp=BOARD/'source_diagnostics_timing_build_04/evidence/runtime/mapping60_01/mapping/analysis/graph.json'
 mg=json.loads(mgp.read_bytes());motion=[];hsst=[]
 def params(r):
  pp={}
  def walk(x):
   if isinstance(x,list):
    if x and x[0]=='PARAMETER':pp[x[1]]=x[2:]
    else:
     for s in x:walk(s)
  walk(r.get('default_parameters',[]));walk(r.get('parameters',[]));return pp
 for c,mr in mg['primitives'].items():
  if 'u_motion_tap/u_detector/history_' in c and 'DRM36' in mr['type']:
   rr=pr.get(c);motion.append({'cell':c,'mapped_type':mr['type'],'fresh_type':rr['type'] if rr else None,'parameters_equal':bool(rr and params(rr)==params(mr)),'mapped_parameters':params(mr),'fresh_parameters':params(rr) if rr else None,'ports_equal':bool(rr and rr['ports']==mr['ports'])})
  if c.endswith('/gophsst'):
   rr=pr.get(c);hsst.append({'cell':c,'mapped_type':mr['type'],'fresh_type':rr['type'] if rr else None,'parameters_equal':bool(rr and params(rr)==params(mr)),'fresh_attributes':rr['attributes'] if rr else None})
 raw=(E/'routed_dump.txt').read_bytes()
 for row in hsst:
  c=row['cell'].encode();pattern=rb'\(INSTANNOTATE\s+\(INSTREF\s+'+re.escape(c)+rb'\)\s+\(PLACE\s+([^\s]+)\s+\(DEVINSTREF\s+([^\s]+)\s+\(SITEREF\s+(\d+)\s+(\d+)\)'
  row['actual_native_places']=[{'impl':m[1].decode(),'site':m[2].decode()+'_'+m[3].decode()+'_'+m[4].decode()} for m in re.finditer(pattern,raw)]
 save('HSST_motion_native_retention.json',{'mapped_graph_sha256':sha(mgp),'fresh_graph_sha256':sha(dest/'graph.json'),'motion_rows':motion,'motion_count':len(motion),'motion_parameters_retained':len(motion)==32 and all(r['parameters_equal'] and r['ports_equal'] for r in motion),'HSST_rows':hsst})
 print('FRESH pairs',len(pairs),'issues',len(issues),'storage60',len({r['actual_cell'] for r in bound if 'actual_cell' in r}))
if __name__=='__main__':main()
