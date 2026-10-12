from pathlib import Path
import sys,json,re,collections,itertools,hashlib
sys.dont_write_bytecode=True
E=Path(__file__).resolve().parent;B=E.parent/'source_diagnostics_timing_build_04'
sys.path[:0]=[str(B/'runtime'),str(B/'runtime/libraries'),str(B/'runtime/analysis_tools')]
from endpoint_detail import parameters
from graph_adapter import Resolver,canon
def load(p):return json.loads(p.read_bytes())
def save(n,x):
 p=E/n
 if p.exists():raise RuntimeError('Refuse overwrite '+str(p))
 p.write_text(json.dumps(x,indent=2,ensure_ascii=True)+'\n',encoding='ascii')
def norm(s):return re.sub(r'\s+','',s.replace('\\','').replace('/@','/').lstrip('/'))
def const(s):
 s=norm(s).lower().replace('_','');m=re.fullmatch(r"(\d+)'([bhd])([0-9a-f]+)",s)
 if m:return int(m[3],{'b':2,'h':16,'d':10}[m[2]])
 if s in {'0','1'}:return int(s)
 return None
def locs(rec):
 found=[]
 def walk(v):
  if isinstance(v,list):
   if len(v)==3 and v[:2]==['ATTRIBUTE','PAP_LOC']:found.append(v[2][1].strip('"'))
   for child in v:walk(child)
 walk(rec.get('attributes',[]));walk(rec.get('cdb_entries',[]));return sorted(set(found))
class Netlist:
 def __init__(self,cells):
  self.cells=cells;self.drivers=collections.defaultdict(list)
  for n,c in cells.items():
   outs={'V_FFASYN':['Q'],'V_FFSYN':['Q'],'V_BUF':['Z'],'V_INV':['Z'],'V_LUT6CARRY':['Z','Z5','COUT'],'V_MUX2':['Z'],'V_LUT5':['Y'],'V_MUX2LUT6':['Z']}.get(c['type'],[])
   for port in outs:
    v=c['ports'].get(port,'')
    if v:self.drivers[norm(v)].append((n,port))
 def value(self,net,assign,records,seen=None):
  n=norm(net)
  if n in assign:return assign[n]
  k=const(n)
  if k is not None:return k
  if not n:return None
  seen=set() if seen is None else set(seen)
  if n in seen:raise RuntimeError('Cycle '+n)
  seen.add(n);ds=self.drivers.get(n,[])
  if len(ds)!=1:raise RuntimeError('Unresolved/nonunique V driver '+n+' '+repr(ds))
  name,port=ds[0];c=self.cells[name];records[name]=c;t=c['type'];p=c['ports'];pa=c['parameters']
  def v(k):return self.value(p.get(k,''),assign,records,seen)
  if t=='V_BUF':return v('I')
  if t=='V_INV':
   x=v('I');return None if x is None else 1-x
  if t=='V_LUT6CARRY':
   init=const(pa.get('INIT',''))
   if init is None:raise RuntimeError('Unknown LUT INIT')
   if port not in {'Z','Z5'}:raise RuntimeError('Unsupported carry cone output')
   keys=['I'+str(i) for i in range(5)]+(['I5' if pa.get('I5_TO_LUT')=='"TRUE"' else 'CIN'] if port=='Z' else [])
   values={};pending=[]
   for bit,key in enumerate(keys):
    expr=p.get(key,'');nn=norm(expr);cv=const(expr)
    if nn in assign:values[bit]=assign[nn]
    elif cv is not None:values[bit]=cv
    else:pending.append((bit,key))
   def indices():return [i for i in range(1<<len(keys)) if all(((i>>bit)&1)==val for bit,val in values.items())]
   for bit,key in pending:
    ii=indices();support=any(((init>>i)&1)!=((init>>(i^(1<<bit)))&1) for i in ii)
    if not support:continue
    x=v(key)
    if x is not None:values[bit]=x
   outs={(init>>i)&1 for i in indices()}
   if len(outs)!=1:raise RuntimeError('LUT depends on unconnected input '+name)
   return next(iter(outs))
  raise RuntimeError('Unknown/unproved V cone '+t+' '+name+'/'+port)
def main():
 rg=load(E/'routed/analysis/graph.json');mg=load(B/'evidence/runtime/mapping60_01/mapping/analysis/graph.json');rows=load(E.parent/'build04_mapped_endpoint_review02/rows60.json')['rows'];inv=load(E/'functional_instance_inventory.json');cells=inv['cells'];nl=Netlist(cells);r=Resolver(rg)
 aliasindex=collections.defaultdict(set)
 for net,aa in rg['net_aliases'].items():
  for a in aa:aliasindex[norm(a)].add(net)
 def portcheck(pin,vnet):
  rn=rg['pin_net'].get(pin);candidates=sorted(aliasindex.get(norm(vnet),[]));return {'routed_pin':pin,'routed_net':rn,'V_net':vnet,'V_net_graph_candidates':candidates,'exact_alias_net_equal':rn in candidates if rn else False}
 result=[]
 for old in rows:
  mapped=old['cell'];rcandidates=[c for c in [mapped,mapped+'_perm'] if c in rg['primitives']]
  row={'logical':old['logical'],'mapped_cell':mapped,'mapped_site':old['planned_site'],'mapped_parameters':old['parameters'],'mapped_type':old['type'],'routed_candidates':rcandidates,'checks':{},'errors':[]};result.append(row)
  try:
   if len(rcandidates)!=1:raise RuntimeError('Exact original or explicit _L6Q_perm identity ambiguous')
   c=rcandidates[0];rec=rg['primitives'][c];p=parameters(rec);site=locs(rec)
   matches={n:v for n,v in cells.items() if v.get('logical_origin')==c+'/FF0/FF' and v['type']=='V_FFASYN'}
   if len(matches)!=1:raise RuntimeError('Exact exported /FF0/FF origin missing/ambiguous')
   vn,v=next(iter(matches.items()));row.update(routed_cell=c,routed_type=rec['type'],routed_parameters=p,routed_sites=site,V_instance=vn,V_record=v,parameter_changes={k:{'mapped':old['parameters'].get(k),'routed':p.get(k)} for k in old['parameters'].keys()|p.keys() if old['parameters'].get(k)!=p.get(k)})
   checks=row['checks'];sync=old['chain'] in {'ack_sync','req_sync','overrun_sync'}
   checks['exact_site']=site==[old['planned_site']] and vn.split('/')[0]==old['planned_site']
   checks['FF_V_parameters']=v['parameters']=={'GRS_EN':'"TRUE"','SET_RESET':'"RESET"' if sync else '"SET"','LRS_EN':'"TRUE"','INIT':"1'b0" if sync else "1'b1"}
   expected={'FF_RS':'RESET' if sync else 'SET','FF_INIT':'0' if sync else '1','RS_MODE':'ASYNC','LRS_POL':'FALSE','LRS_EN':'TRUE','LCE_POL':'FALSE','LCE_EN':'FALSE','CLK_POL':'FALSE','GRS_EN':'TRUE','LATCH_EN':'FALSE','CEMUX_SEL':'LOCAL'}
   checks['actual_storage_parameters']=all(p.get(k)==val for k,val in expected.items()) and p.get('RSMUX_SEL') in {'LOCAL','CHAIN'}
   checks['V_CE_exact_one']=const(v['ports'].get('CE',''))==1
   outputs=[k for k in ['Q','L6Q'] if c+'/'+k in rg['pin_net'] and rec['ports'][k]['direction']=='OUTPUT']
   checks['one_registered_output']=len(outputs)==1
   q=c+'/'+outputs[0];checks['Q_unique_driver']=r.drivers(rg['pin_net'][q])==[q]
   row['port_binding']={k:portcheck(pin,v['ports'].get(k,'')) for k,pin in [('Q',q),('CK',c+'/CLK'),('SR',c+'/RS')]}
   checks['V_Q_CK_SR_exact_graph_nets']=all(x['exact_alias_net_equal'] for x in row['port_binding'].values())
   if c+'/D' in rg['pin_net']:
    row['port_binding']['D']=portcheck(c+'/D',v['ports']['D']);checks['V_D_exact_graph_net']=row['port_binding']['D']['exact_alias_net_equal']
   else:
    records={};value=nl.value(v['ports']['D'],{},records)
    row['actual_D_cone']=records;row['constant_D_value']=value;checks['integrated_D_original_zero']=value==0 and old.get('I0_constant_value')==0
    luts=[x for x in records.values() if x['type']=='V_LUT6CARRY'];checks['integrated_LUT_INIT_binding']=len(luts)==1 and const(luts[0]['parameters']['INIT'])==int(p['INIT'],2) and luts[0]['parameters'].get('I5_TO_LUT')=='"TRUE"'
   row['GTP_contract']={'model':'GTP_DFF_C' if sync else 'GTP_DFF_P','logical_D':old['synthesis_target']+'/D','Q':q,'clock':c+'/CLK','local_reset':c+'/RS','INIT':0 if sync else 1,'GRS':'active-low global reset to INIT, then active-high local C/P, then positive edge D','V_model':'V_FFASYN','CE':1,'event_simulation_receipt':'official_cp_contract.json'}
  except Exception as ex:row['errors'].append(str(ex))
 # Reset boundary model binding includes the actual L5Q/L6Q and inverted paths,
 # retaining complete V driver cones up to registered boundaries, never naming an unknown as identity.
 boundaries=[]
 for cam in range(4):
  parent='ov5640_top' if cam==0 else f'cam{cam+1}_ov5640_top'
  nets=['axi_rst',f'nt_cmos{cam+1}_rst_n','camera_ctrl_rst_n',parent+'/ov5640/cam_init_done']
  for net in nets:
   seen=set();stack=[norm(net)];records={};unresolved=[];registered=[]
   while stack:
    n=stack.pop()
    if n in seen or const(n) is not None or not n:continue
    seen.add(n);ds=nl.drivers.get(n,[])
    if len(ds)!=1:unresolved.append({'net':n,'drivers':ds});continue
    name,port=ds[0];v=cells[name];records[name]=v
    if v['type'] in {'V_FFASYN','V_FFSYN'}:registered.append({'net':n,'instance':name,'output':port,'parameters':v['parameters'],'ports':v['ports'],'logical_origin':v['logical_origin']});continue
    if v['type'] in {'V_BUF','V_INV'}:stack.append(norm(v['ports']['I']))
    elif v['type']=='V_LUT6CARRY':stack.extend(norm(v['ports'].get(k,'')) for k in ['I0','I1','I2','I3','I4','I5','CIN'])
    else:unresolved.append({'net':n,'type':v['type'],'instance':name})
   boundaries.append({'camera':cam,'logical_boundary':net,'driver_cone':records,'registered_boundaries':registered,'unresolved':unresolved,'acceptance':'Exact exported model parameters/connections captured. Upstream GTP-to-packed boundary transformation remains an independent review gate.'})
 # Evaluate actual exported reset cones under each of the 16 boundary assignments.
 resets=[]
 for row,old in zip(result,rows):
  if old['chain'] in {'ack_sync','req_sync','overrun_sync'} or 'V_record' not in row:continue
  cam=old['camera'];parent='ov5640_top' if cam==0 else f'cam{cam+1}_ov5640_top';nets=['axi_rst',f'nt_cmos{cam+1}_rst_n','camera_ctrl_rst_n',parent+'/ov5640/cam_init_done'];table=[];records={};error=None
  try:
   for vals in itertools.product([0,1],repeat=4):
    actual=nl.value(row['V_record']['ports']['SR'],dict(zip(map(norm,nets),vals)),records);x,cn,ctrl,init=vals;table.append({'inputs':vals,'actual':actual,'expected':x|(1-cn)|(1-(ctrl&init))})
  except Exception as ex:error=str(ex)
  resets.append({'logical':row['logical'],'V_SR':row['V_record']['ports']['SR'],'boundary_nets':nets,'table':table,'cone':records,'error':error,'passed':len(table)==16 and all(x['actual']==x['expected'] for x in table)})
 issues=[{'logical':x['logical'],'errors':x['errors'],'failed_checks':[k for k,v in x['checks'].items() if not v]} for x in result if x['errors'] or not all(x['checks'].values())]
 save('official_model_binding60_refined.json',{'rows':result,'count':len(result),'distinct_storage':len({x.get('routed_cell') for x in result if x.get('routed_cell')}),'distinct_sites':len({s for x in result for s in x.get('routed_sites',[])}),'distinct_V_FFASYN':len({x.get('V_instance') for x in result if x.get('V_instance')}),'issues':issues,'reset_boundary_models':boundaries,'reset_cone_contracts':resets,'mapped_to_routed_graph_identity':False,'alias_changes_require_independent_review':True,'full_semantic_acceptance':False,'initial_analysis_retained':'official_model_binding60.json','refinement':'Correct exact renamed original _L6Q + _perm; check full cell/D key; evaluate only LUT support under bound selector/constants, never accept unresolved supported inputs.'})
 print('EXACT60',len(result),'ISSUES',len(issues),'RESET_CONE_PASS',sum(x['passed'] for x in resets),'/',len(resets))
if __name__=='__main__':main()
