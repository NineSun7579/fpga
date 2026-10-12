from pathlib import Path
import sys,json,hashlib,importlib.util,itertools,traceback,collections
sys.dont_write_bytecode=True
E=Path(__file__).resolve().parent;BOARD=E.parent;B=BOARD/'source_diagnostics_timing_build_04'
sys.path[:0]=[str(B/'runtime/libraries'),str(B/'runtime/analysis_tools'),str(B/'runtime')]
from endpoint_detail import parameters
from graph_adapter import Resolver
spec=importlib.util.spec_from_file_location('original_review',BOARD/'build04_mapped_endpoint_review02/review.py');rv=importlib.util.module_from_spec(spec);spec.loader.exec_module(rv)
def load(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,x):
 p=E/n
 if p.exists():raise RuntimeError('Refuse overwrite '+str(p))
 p.write_text(json.dumps(x,indent=2,ensure_ascii=True)+'\n',encoding='ascii')
def peers(g,n):return sorted(p for p,v in g['pin_net'].items() if v==n)
def main():
 gp=B/'evidence/runtime/mapping60_01/mapping/analysis/graph.json';rp=E/'routed/analysis/graph.json'
 mg=load(gp);rg=load(rp);sg=load(B/'evidence/runtime/actual/analysis/graph.json');rv.SYN_GRAPH=sg
 rows=load(BOARD/'build04_mapped_endpoint_review02/rows60.json')['rows'];rr=Resolver(rg)
 relevant=set();bridges=[];issues=[]
 for row in rows:
  c=row['cell'];relevant.add(c)
  for k in ['mapped_reset_cone','I0_cone']:relevant.update(row.get(k,{}))
  for bound in row.get('reset_boundary_binding',[]):relevant.update(bound.get('mapped_driver_records',{}))
  for edge in row.get('clock_identity',{}).get('edges',[]):relevant.add(edge['driver'].rsplit('/',1)[0])
  if row.get('first_stage_source_binding'):relevant.add(row['first_stage_source_binding']['actual_Q'].rsplit('/',1)[0])
  r={'logical':row['logical'],'mapped_cell':c,'mapped_type':row['type'],'mapped_site':row['planned_site'],'mapped_Q':row['Q'],'errors':[]}
  bridges.append(r)
  if c not in rg['primitives']:
   r['errors'].append('Exact mapped cell absent; independent identity review required');continue
  rec=rg['primitives'][c];p=parameters(rec);r.update(routed_cell=c,routed_type=rec['type'],routed_parameters=p,routed_record=rec,routed_PAP_LOC=rv.locs(rec))
  r['checks']={'same_type':rec['type']==row['type'],'same_parameters':p==row['parameters'],'exact_site':{x['value'] for x in rv.locs(rec)}=={row['planned_site']},'same_ports':rec['ports']==mg['primitives'][c]['ports']}
  q=row['Q'];r['checks']['unique_Q_driver']=q in rg['pin_net'] and rr.drivers(rg['pin_net'][q])==[q]
  r['pin_bridge']={}
  for port in mg['primitives'][c]['ports']:
   pin=c+'/'+port;mn=mg['pin_net'].get(pin);rn=rg['pin_net'].get(pin)
   before=peers(mg,mn) if mn else [];after=peers(rg,rn) if rn else []
   r['pin_bridge'][port]={'mapped_net':mn,'routed_net':rn,'mapped_aliases':mg['net_aliases'].get(mn,[]),'routed_aliases':rg['net_aliases'].get(rn,[]),'mapped_endpoints':before,'routed_endpoints':after,'lost_endpoints':sorted(set(before)-set(after)),'new_endpoints':sorted(set(after)-set(before))}
  try:r['routed_clock_identity']=rv.clock_path(rg,c+'/CLK',row['clock_identity']['root_alias']);r['checks']['routed_clock_proved']=True
  except Exception as ex:r['errors'].append('Clock: '+str(ex));r['checks']['routed_clock_proved']=False
  if row.get('reset_boundary_binding'):
   try:
    nets=[];boundaries=[]
    for bb in row['reset_boundary_binding']:
     ds=bb['mapped_drivers']
     if len(ds)!=1 or ds[0] not in rg['pin_net']:raise RuntimeError('Boundary exact driver absent/ambiguous '+repr(ds))
     pin=ds[0];nets.append(rg['pin_net'][pin]);boundaries.append({'exact_retained_driver':pin,'mapped_net':bb['mapped_net'],'routed_net':nets[-1],'routed_record':rg['primitives'][pin.rsplit('/',1)[0]]})
    cn=rv.Cone(rg);table=[]
    for vals in itertools.product([0,1],repeat=4):
     actual=cn.value(rg['pin_net'][c+'/RS'],dict(zip(nets,vals)));x,cam,ctrl,init=vals;table.append({'inputs':vals,'routed':actual,'expected':x|(1-cam)|(1-(ctrl&init))})
    r['routed_reset_boundaries']=boundaries;r['routed_reset_cone']=cn.records;r['routed_reset_truth_table']=table;r['checks']['reset_truth_table']=all(x['routed']==x['expected'] for x in table)
   except Exception as ex:r['errors'].append('Reset cone: '+str(ex));r['checks']['reset_truth_table']=False
  if 'INIT' in p:
   r['LUT_INIT_changed']=p['INIT']!=row['parameters'].get('INIT')
  if any(v['lost_endpoints'] or v['new_endpoints'] or v['mapped_aliases']!=v['routed_aliases'] for v in r['pin_bridge'].values()):r['independent_alias_endpoint_review_required']=True
 changes=[]
 for c in sorted(relevant):
  a=mg['primitives'].get(c);b=rg['primitives'].get(c)
  changes.append({'cell':c,'mapped_record':a,'routed_record':b,'same_type':bool(a and b and a['type']==b['type']),'mapped_parameters':parameters(a) if a else None,'routed_parameters':parameters(b) if b else None,'mapped_PAP_LOC':rv.locs(a) if a else [],'routed_PAP_LOC':rv.locs(b) if b else [],'record_changed':a!=b})
 pairs=[];index={(x['camera'],x['chain'],x['bit']):x for x in rows}
 for row in rows:
  if row['bit']:
   prev=index[row['camera'],row['chain'],row['bit']-1];d=row['D'];q=prev['Q']
   pairs.append({'Q':q,'D':d,'routed_equal':bool(d and q in rg['pin_net'] and d in rg['pin_net'] and rr.equal(q,d)),'same_clock':row['CLK'] in rg['pin_net'] and prev['CLK'] in rg['pin_net'] and rr.equal(row['CLK'],prev['CLK']),'same_reset':row['reset'] in rg['pin_net'] and prev['reset'] in rg['pin_net'] and rr.equal(row['reset'],prev['reset'])})
 for r in bridges:
  if r['errors'] or not all(r.get('checks',{}).values()):issues.append({'logical':r['logical'],'errors':r['errors'],'failed_checks':[k for k,v in r.get('checks',{}).items() if not v]})
 full={'removed_cells':sorted(set(mg['primitives'])-set(rg['primitives'])),'added_cells':sorted(set(rg['primitives'])-set(mg['primitives'])),'changed_common_cell_records':[c for c in mg['primitives'].keys()&rg['primitives'].keys() if mg['primitives'][c]!=rg['primitives'][c]]}
 save('mapped_routed_identity_bridge.json',{'mapped_graph_sha256':sha(gp),'routed_graph_sha256':sha(rp),'rows':bridges,'rows60':len(bridges),'distinct_routed_storage':len({r.get('routed_cell') for r in bridges if r.get('routed_cell')}),'distinct_routed_sites':len({x['value'] for r in bridges for x in r.get('routed_PAP_LOC',[])}),'issues':issues,'adjacent_stage_contracts':pairs,'independent_alias_review_rows':[r['logical'] for r in bridges if r.get('independent_alias_endpoint_review_required')],'same_graph_claim':False})
 save('relevant_parameter_and_boundary_changes.json',changes);save('full_graph_change_inventory.json',full)
 print('BRIDGE rows=',len(bridges),'issues=',len(issues),'alias_review=',sum(bool(r.get('independent_alias_endpoint_review_required')) for r in bridges))
if __name__=='__main__':main()
