"""Offline audit of immutable original map; never invokes PDS or modifies inputs."""
from pathlib import Path
import sys,json,hashlib,re,itertools,subprocess,shutil,collections,traceback,tkinter
sys.dont_write_bytecode=True
H=Path(__file__).resolve().parent
BOARD=H.parent; B=BOARD/'source_diagnostics_timing_build_04'
E=B/'evidence/runtime/mapping60_01'; PREP=BOARD/'production60_target_prepare01'
sys.path[:0]=[str(B/'runtime'),str(B/'runtime/libraries'),str(B/'runtime/analysis_tools')]
from graph_adapter import Resolver,canon,parameter
from endpoint_detail import parameters
import preflight
INSTALL=Path('C:/pango/PDS_2022.2-SP6.4')
def sha(p):return preflight.sha(p)
def load(p):return json.loads(Path(p).read_bytes())
def save(n,o):
 p=H/n;p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(o,indent=2,ensure_ascii=True)+'\n',encoding='ascii')
def require(v,m):
 if not v:raise RuntimeError(m)
def snapshot():
 roots=[B,BOARD/'source_diagnostics_timing_build_03',BOARD/'diagnostic_sync_register_map_01',BOARD/'diagnostic_sync_register_map02',PREP]
 out={str(p):sha(p) for root in roots for p in root.rglob('*') if p.is_file()}
 m=load(B/'manifest.json')
 for p in m['protected_hashes']:out[p]=sha(p)
 return out
def locs(rec):
 out=[]
 def visit(v):
  if not isinstance(v,list):return
  if len(v)==3 and v[:2]==['ATTRIBUTE','PAP_LOC']:
   require(isinstance(v[2],list) and v[2][0]=='STRING','Unsupported PAP_LOC')
   out.append({'value':v[2][1].strip('"'),'entry':v})
  for x in v:visit(x)
 visit(rec.get('attributes',[]));visit(rec.get('cdb_entries',[]));return out
def root(g,names):
 ns={n for n,aa in g['net_aliases'].items() if any(canon(a) in names for a in aa)}
 require(len(ns)==1,'Nonunique exact root '+repr(names));return next(iter(ns))

class Cone:
 """Exact primitive gates, evaluated exhaustively. Unknowns raise, never become true."""
 def __init__(self,g):self.g=g;self.r=Resolver(g);self.records={}
 def value(self,n,assignment,seen=None):
  if n in assignment:return assignment[n]
  seen=set() if seen is None else set(seen)
  require(n is not None and n not in seen,'Unconnected/cyclic cone '+str(n));seen.add(n)
  aa=self.g['net_aliases'].get(n,[])
  for v in [0,1]:
   if any(a.endswith('/@$constant_'+str(v)) for a in aa):return v
  if any(a.endswith('/@$constant_y') for a in aa):return None
  ds=self.r.drivers(n);require(len(ds)==1,'Nonunique cone driver '+str(n)+' '+repr(ds))
  pin=ds[0];c,port=pin.rsplit('/',1);rec=self.g['primitives'][c];typ=rec['type'];p=parameters(rec)
  self.records[c]={'type':typ,'parameters':p,'output':pin}
  def val(k):return self.value(self.g['pin_net'].get(c+'/'+k),assignment,seen)
  if typ in {'GTP_CONSTANT'}:require(p.get('VALUE') in {'0','1'},'Unknown constant');return int(p['VALUE'])
  if typ in {'GTP_GND','gopGND','GND'}:return 0
  if typ in {'GTP_VCC','gopVCC','VCC'}:return 1
  ip=self.r.identity_input(pin)
  if ip:return self.value(self.g['pin_net'][ip],assignment,seen)
  if typ in {'bmsINV','bmsWIDEINV','GTP_INV','gopINV'}:
   ins=[k for k,v in rec['ports'].items() if v['direction']=='INPUT' and c+'/'+k in self.g['pin_net']]
   require(len(ins)==1,'Unknown inverter interface');return 1-val(ins[0])
  if (re.fullmatch(r'GTP_LUT[1-6](?:_Cell_\d+)?',typ) and port=='Z') or (re.fullmatch(r'gopLUT6(?:_Cell_\d+)?',typ) and port=='L6'):
   ins=sorted([k for k in rec['ports'] if re.fullmatch(r'I\d+',k)],key=lambda k:int(k[1:]))
   bits=p.get('INIT','');require(re.fullmatch('[01]+',bits) and len(bits)==2**len(ins),'Invalid LUT truth table '+c)
   vals=[val(k) for k in ins];domains=[(0,1) if v is None else (v,) for v in vals]
   outputs={int(bits[-1-sum(v<<i for i,v in enumerate(trial))]) for trial in itertools.product(*domains)}
   self.records[c]['input_pins']={k:self.g['pin_net'].get(c+'/'+k) for k in ins}
   self.records[c]['complete_truth_table']=[{'inputs':[(i>>j)&1 for j in range(len(ins))],'output':int(bits[-1-i])} for i in range(2**len(ins))]
   require(len(outputs)==1,'LUT depends on unbound dont-care inputs '+c)
   return next(iter(outputs))
  raise RuntimeError('Unknown/unproved cone primitive '+typ+' '+pin)

def retained_output(g,original_cell,ports):
 candidates=[c+'/'+k for c,rec in g['primitives'].items() if c==original_cell or c.startswith(original_cell+'/') for k in ports if c+'/'+k in g['pin_net'] and rec['ports'][k]['direction']=='OUTPUT']
 require(len(candidates)==1,'Exact retained output ambiguous '+original_cell+' '+repr(candidates))
 return candidates[0]
def clock_path(g,pin,alias):
 r=Resolver(g);n=g['pin_net'][pin];seen=set();edges=[];binding=None
 if alias=='ddr3/u_ddrphy_top/ddrphy_sysclk' and g is not SYN_GRAPH:
  op=retained_output(g,'ddr3/u_ddrphy_top/u_sysclk_bufg',['CLKOUT']);end=g['pin_net'][op]
  rec=g['primitives'][op.rsplit('/',1)[0]]
  require(rec['type']=='gopCLKBUFG' and parameters(rec)=={'SOURCE_CLK':'CLK0'},'DDR root actual clock buffer parameters')
  binding={'synthesis_output':'ddr3/u_ddrphy_top/u_sysclk_bufg/CLKOUT','mapped_output':op,'type':rec['type'],'parameters':parameters(rec)}
 else:end=root(g,{alias})
 while n!=end:
  require(n not in seen,'Clock cycle');seen.add(n);ds=r.drivers(n);require(len(ds)==1,'Clock ambiguity')
  op=ds[0];c,port=op.rsplit('/',1);rec=g['primitives'][c];typ=rec['type'];p=parameters(rec)
  ip=r.identity_input(op)
  if ip is None:
   if typ in {'gopIBUF','gopIBUF_Cell_1','gopIBUF_Cell_2'}:
    require(port=='O' and p.get('CP_DYN_IN')=='OFF' and p.get('IOB_MODE','').startswith('IBUF'),'IBUF identity parameters');ip=c+'/I'
   elif typ=='gopCLKBUFG':require(port=='CLKOUT','CLKBUFG port');ip=c+'/CLK'
   elif typ=='gopHCKB':require(port=='CLKOUT' and p.get('CP_MODE_SEL')=='DISABLE','HCKB identity parameters');ip=c+'/CLKIN'
   elif typ=='gopIOL_Cell_9':
    checks={'BUF_MODE':'IBUF','CP_IDLY_EN':'FALSE','CP_IDYN_EN':'FALSE','CP_ZHOLD_EN':'FALSE','CP_DYN_CLKPOL':'FALSE','CP_IDFFEN':'FALSE','CP_ILTHEN':'FALSE','CP_DDRI_EN':'FALSE','CP_DES_DDREN':'FALSE','CP_DES_SDREN':'FALSE','CP_D_POL0':'FALSE','CP_D_SEL0':0,'CP_D_SEL1':0,'CP_D_SEL2':0,'CP_D_SEL3':0}
    require(port=='DI_TO_CLK' and all(parameter(rec,k)==v for k,v in checks.items()),'IOL identity parameters')
    require(not any(c+'/'+k in g['pin_net'] for k in ['ICLK','ICLKB','ICLKDIV','DYN_CLKPOL','IDLY_SEL']),'IOL active controls');ip=c+'/DI'
   else:raise RuntimeError('Unknown exact clock identity '+typ+' '+c)
  require(ip in g['pin_net'],'Missing clock identity input')
  edges.append({'net':n,'driver':op,'type':typ,'input':ip,'parameters':p});n=g['pin_net'][ip]
 return {'root_alias':alias,'root_net':n,'exact_retained_root_binding':binding,'edges':edges,'identity':True}

def reparsed():
 src=E/'mapping';dst=H/'native_reparse';ana=dst/'analysis';ana.mkdir(parents=True)
 (dst/'synthesis_export').mkdir()
 shutil.copy2(src/'analysis/parse_objects.py',ana/'parse_objects.py')
 shutil.copy2(src/'synthesis_export/synthesis_dump.txt',dst/'synthesis_export/synthesis_dump.txt')
 res=subprocess.run([sys.executable,'-B',str(ana/'parse_objects.py')],cwd=ana,capture_output=True)
 (ana/'parser.log').write_bytes(res.stdout+res.stderr)
 require(res.returncode==0,'Offline parser failed')
 require(sha(ana/'graph.json')==sha(src/'analysis/graph.json'),'Reparsed graph differs')
 return load(ana/'graph.json')

def main():
 global SYN_GRAPH
 require(not (H/'final_result.json').exists(),'Review already completed; refuse overwrite')
 print('HASH_SNAPSHOT_START',flush=True);before=snapshot();save('before_hashes.json',before)
 m=preflight.verify();print('PROTECTED_INPUTS_VERIFIED',flush=True)
 provenance={};checks={}
 for filename in ['mapping_artifact.json','mapping_input_hashes.json']:
  binding=load(E/filename);checks[filename]={p:Path(p).is_file() and sha(p)==v for p,v in binding.items()}
 gb=load(E/'graph_binding.json')
 paths={'adf':E/'isolated_mapping_work/device_map/v7_sdt_top_map.adf','dmr':E/'isolated_mapping_work/device_map/dmr.db','pcf':E/'isolated_mapping_work/device_map/v7_sdt_top.pcf','dump':E/'mapping/synthesis_export/synthesis_dump.txt','graph':E/'mapping/analysis/graph.json','parser':E/'mapping/analysis/parse_objects.py'}
 checks['graph_binding']={k:sha(p)==gb[k+'_sha256'] for k,p in paths.items()}
 fresh=load(E/'fresh60_binding.json');sgfile=B/'evidence/runtime/actual/analysis/graph.json';sg=load(sgfile);SYN_GRAPH=sg
 checks['fresh60']={'graph':sha(sgfile)==fresh['synthesis_graph_sha256'],'parser':sha(B/'runtime/analysis_tools/parse_objects.py')==fresh['parser_sha256']}
 for label in ['mapping','mapping_export']:
  rec=load(E/(label+'_receipt.json'));checks[label]={'exit':rec['exit_code']==0,'log':sha(E/(label+'.log'))==rec['log_sha256'],'errors':not rec['rejected_lines'] and not rec['native_errors']}
 require(all(all(v.values()) for v in checks.values()),'Original artifact binding drift')
 require(load(E/'final_result.json')['status']=='FAIL','Original FAIL changed')
 print('OFFLINE_NATIVE_PARSER_START',flush=True);g=reparsed();print('OFFLINE_NATIVE_PARSER_MATCH',flush=True)
 provenance['checks']=checks;provenance['original_result']=load(E/'final_result.json')
 provenance['actual_artifacts']={str(p):sha(p) for p in paths.values()}
 provenance['actual_logs']={str(p):sha(p) for p in [E/'mapping.log',E/'mapping_export.log',E/'mapping/analysis/parser.log',E/'isolated_mapping_work/device_map/run.log']}
 provenance['receipts']={label:load(E/(label+'_receipt.json')) for label in ['mapping','mapping_export']}
 provenance['fresh60_binding_sha256']=sha(E/'fresh60_binding.json')
 provenance['reparse']={str(p):sha(p) for p in (H/'native_reparse').rglob('*') if p.is_file()}
 modelpaths=[INSTALL/'arch/vendor/pango/logos2'/family/'valence/operator/gate/CLM'/name for family in ['common','pg2l100h'] for name in ['gopQ.eval','gopLUT6Q.eval','gopLUT6.eval','gopLUT6QQ.eval','gopCLKROUTE.eval']]
 rulepath=INSTALL/'arch/vendor/pango/logos2/common/packingrule/packingrules.txt'
 rules=rulepath.read_text();start=rules.index('rule gopL6Q\n');end=rules.index('rule gopL6QQ\n',start);rule=rules[start:end]
 require(all(s in rule for s in ['gopQ inst1 + gopLUT6 inst2 => gopLUT6Q','D of inst1 => NIL','Q of inst1 => L6Q','FF_RS        of inst1  => FF_RS','FF_INIT      of inst1  => FF_INIT']),'Official oneFF packing rule differs')
 readable={str(p):not p.read_bytes().startswith(b'\x01\x00PANG!') and b'module' in p.read_bytes() for p in modelpaths}
 model_semantics_available=all(readable.values())
 save('official_model_evidence.json',{'models':{str(p):{'sha256':sha(p),'header_hex':p.read_bytes()[:12].hex(),'readable_behavior':readable[str(p)]} for p in modelpaths},'packing_rule':rule,'packing_rule_path':str(rulepath),'packing_rule_sha256':sha(rulepath),'prior_decode_basis':{str(p):sha(p) for p in [B/'runtime/libraries/endpoint_detail.py',B/'runtime/libraries/endpoint_logic.py',BOARD/'diagnostic_sync_register_map02/audit_packed_pairs.py']},'official_GTP_models':{str(INSTALL/'arch/vendor/pango/verilog/simulation'/n):sha(INSTALL/'arch/vendor/pango/verilog/simulation'/n) for n in ['GTP_LUT1.v','GTP_LUT2.v','GTP_LUT3.v','GTP_LUT4.v','GTP_LUT5.v','GTP_LUT6.v','GTP_DFF_C.v','GTP_DFF_P.v']},'limitation':'Installed gop .eval files are PANG binary models. No readable behavioral implementation or existing model decoder was found. Parameter matches and textual packing rule are structural evidence; full model-semantic acceptance remains unproven.'})
 tcl=tkinter.Tcl();lcf=[];pcf=[]
 for line in (PREP/'production60_site_DRAFT.lcf').read_text().splitlines():
  if not line.strip() or line.lstrip().startswith('#'):continue
  pp=tcl.splitlist(line);require(len(pp)==4 and pp[0]=='define_attribute' and pp[2]=='PAP_LOC','LCF syntax');lcf.append((pp[1][2:],pp[3]))
 for line in paths['pcf'].read_text().splitlines():
  if not line.strip() or line.lstrip().startswith('#'):continue
  pp=tcl.splitlist(line)
  if pp[0]=='def_inst_site':
   require(len(pp) in {3,4},'PCF syntax');pcf.append({'cell':pp[1].lstrip('\\'),'site':pp[2],'implementation':pp[3] if len(pp)==4 else None,'line':line})
 require(len(lcf)==60 and dict(lcf)=={t['target']:t['site'] for t in fresh['rows']},'LCF/fresh60 mismatch')
 require(dict(lcf)=={t['target']:t['site'] for t in load(PREP/'site_candidate_plan.json')['rows']},'LCF/plan mismatch')
 sr=Resolver(sg);mr=Resolver(g);rows=[];lookup={}
 for t in fresh['rows']:
  s=t['synthesis_row'];target=t['target'];candidates=[c for c in g['primitives'] if c==target or c.startswith(target+'/')]
  row={'camera':s['camera'],'chain':s['chain'],'bit':s['bit'],'logical':s['logical'],'synthesis_target':target,'planned_site':t['site'],'candidates':candidates,'checks':{},'errors':[]}
  rows.append(row);lookup[(s['camera'],s['chain'],s['bit'])]=row
  try:
   require(len(candidates)==1,'Exact retained synthesis target does not bind one mapped primitive')
   c=candidates[0];rec=g['primitives'][c];p=parameters(rec);typ=rec['type'];integrated=typ=='gopLUT6Q_Cell_139'
   row.update({'cell':c,'type':typ,'parameters':p,'raw_record':rec})
   require(typ in {'gopQ','gopQ_Cell_1','gopLUT6Q_Cell_139'},'Unknown mapped storage type '+typ)
   q='L6Q' if integrated else 'Q';data=[f'I{i}' for i in range(6)] if integrated else ['D']
   expected_ports=set(data+['CLK','RS','CE','CECO','RSCO',q]+(['L6'] if integrated else []))
   row['checks']['exact_oneFF_interface']=set(rec['ports'])==expected_ports
   row.update({'Q':c+'/'+q,'D':None if integrated else c+'/D','storage_D_function':'LUT6(I0..I5)' if integrated else c+'/D','data_inputs':[c+'/'+k for k in data],'CLK':c+'/CLK','reset':c+'/RS','actual_pin_nets':{k:g['pin_net'].get(c+'/'+k) for k in rec['ports']}})
   row['checks']['ports_connected']=all(c+'/'+k in g['pin_net'] for k in data+['CLK','RS',q])
   row['checks']['directions']=all(rec['ports'][k]['direction']=='INPUT' for k in data+['CLK','RS']) and rec['ports'][q]['direction']=='OUTPUT'
   sync=s['chain'] in {'ack_sync','req_sync','overrun_sync'};expected={'FF_RS':'RESET' if sync else 'SET','FF_INIT':'0' if sync else '1','GRS_EN':'TRUE','RS_MODE':'ASYNC','LRS_POL':'FALSE','LRS_EN':'TRUE','LCE_POL':'FALSE','LCE_EN':'FALSE','CLK_POL':'FALSE','RSMUX_SEL':'LOCAL','CEMUX_SEL':'LOCAL','LATCH_EN':'FALSE','QMUX_SEL':'YX' if integrated else 'MX'}
   expected.update({'MODE':'LUT6'} if integrated else {'IMPL_MODE':'Q'})
   row['expected_parameters']=expected
   row['checks']['no_unknown_storage_parameters']=set(p)==set(expected)|({'INIT'} if integrated else set())
   for k,v in expected.items():row['checks']['parameter_'+k]=p.get(k)==v
   row['checks']['CE_unconnected_disabled']=c+'/CE' not in g['pin_net'] and p['LCE_EN']=='FALSE'
   row['checks']['Q_is_unique_actual_driver']=mr.drivers(g['pin_net'][row['Q']])==[row['Q']]
   row['checks']['no_extra_storage_parameters']=not any(k.startswith(('FFAPP','FF0','FF1','SRL')) for k in p)
   synrec=sg['primitives'][target];row['checks']['exact_original_GTP']=synrec['type']==('GTP_DFF_C' if sync else 'GTP_DFF_P') and set(synrec['ports'])=={'D','Q','CLK','C' if sync else 'P'}
   row['checks']['original_model_hash']=sha(t['no_CE_model'])==t['model_sha256']
   row['synthesis_record']=synrec
   actual=[x for x in pcf if x['cell']==c];entries=locs(rec)
   row.update({'actual_PCF':actual,'actual_PAP_LOC':entries})
   row['checks']['exact_site_binding']=bool(actual and entries) and {x['site'] for x in actual}=={t['site']} and {x['value'] for x in entries}=={t['site']}
   row['implementation_annotation_present']=bool(actual and actual[0]['implementation'])
   row['PAP_NOPRUNE_present']=['ATTRIBUTE','PAP_NOPRUNE',['BOOL','TRUE']] in rec.get('attributes',[])
   row['checks']['PCF_exact_command']=len(actual)==1 and actual[0]['implementation'] in {None,'impl_devCQ0'}
   alias=s['clock_root_expected'];alias=alias if alias!='ddrphy_sysclk' else 'ddr3/u_ddrphy_top/ddrphy_sysclk'
   try:
    row['clock_identity']=clock_path(g,row['CLK'],alias);row['synthesis_clock_identity']=clock_path(sg,s['CLK'],alias);row['checks']['exact_clock_identity']=True
   except Exception as ex:row['checks']['exact_clock_identity']=False;row['errors'].append(str(ex))
   if integrated:
    require(s['bit']==0 and not sync,'Integrated LUT unsupported stage')
    bits=p.get('INIT','');require(re.fullmatch('[01]{64}',bits),'Malformed integrated LUT INIT')
    truth=[{'I':[(i>>j)&1 for j in range(6)],'actual':int(bits[-1-i]),'expected_identity_I0':i&1} for i in range(64)]
    row['complete_LUT_truth_table']=truth;row['checks']['LUT_full_identity_I0']=all(x['actual']==x['expected_identity_I0'] for x in truth)
    cn=Cone(g);row['I0_constant_value']=cn.value(g['pin_net'][c+'/I0'],{});row['I0_cone']=cn.records
    row['checks']['I0_original_constant_zero']=row['I0_constant_value']==0 and Cone(sg).value(sg['pin_net'][s['D']],{})==0
    restricted=[x for x in truth if x['I'][0]==row['I0_constant_value']]
    row['reachable_truth_table']=restricted;row['checks']['D_function_original_zero']=len(restricted)==32 and all(x['actual']==0 for x in restricted)
   row['checks']['official_gop_behavior_decoded']=model_semantics_available
  except Exception as ex:row['errors'].append(str(ex))
 print('EXACT60_BINDING_ROWS_WRITTEN',len(rows),flush=True)
 # Each row is audited independently; a failure never suppresses remaining rows.
 pairs=[]
 for t,row in zip(fresh['rows'],rows):
  s=t['synthesis_row'];cam=s['camera'];chain=s['chain'];bit=s['bit'];sync=chain in {'ack_sync','req_sync','overrun_sync'}
  try:
   require('cell' in row and 'Q' in row,'Unbound row')
   if bit:
    prev=lookup[(cam,chain,bit-1)];pair={'previous_Q':prev['Q'],'capture_D':row['D'],'synthesis_Q':prev['synthesis_target']+'/Q','synthesis_D':s['D']}
    pair['actual_Q_D']=mr.equal(prev['Q'],row['D']);pair['synthesis_Q_D']=sr.equal(pair['synthesis_Q'],pair['synthesis_D']);pair['clock_same']=mr.equal(prev['CLK'],row['CLK']);pair['reset_same']=mr.equal(prev['reset'],row['reset']);pairs.append(pair)
    row['checks']['adjacent_Q_D_clock_reset']=all(pair[k] for k in ['actual_Q_D','synthesis_Q_D','clock_same','reset_same'])
   elif sync:
    signal={'ack_sync':'ack','req_sync':'request','overrun_sync':'sticky_overrun'}[chain];sq=sr.signal_q(cam,signal);anchor=sq.rsplit('/',1)[0]
    # Bind to the exact original source register path, then its unique registered output.
    candidates=[(c,k) for c,rec in g['primitives'].items() if c==anchor or c.startswith(anchor+'/') for k in ['Q','Q0','L5Q','L6Q'] if c+'/'+k in g['pin_net'] and rec['ports'][k]['direction']=='OUTPUT']
    require(len(candidates)==1,'Source Q binding ambiguity '+anchor)
    c,k=candidates[0];mq=c+'/'+k;row['first_stage_source_binding']={'synthesis_Q':sq,'actual_Q':mq,'actual_type':g['primitives'][c]['type']}
    row['checks']['D_original_source_Q']=sr.equal(sq,s['D']) and mr.equal(mq,row['D'])
   if sync:
    release=lookup[(cam,'cr' if chain=='ack_sync' else 'hr',1)]
    row['reset_release_binding']={'Q':release['Q'],'RS':row['reset']};row['checks']['reset_identity_exact_release_Q']=mr.equal(release['Q'],row['reset'])
   else:
    parent='ov5640_top' if cam==0 else f'cam{cam+1}_ov5640_top'
    names=[{'source_diagnostics/rst','axi_rst'},{f'nt_cmos{cam+1}_rst_n'},{'camera_ctrl_rst_n'},{parent+'/ov5640/ov5640_i2c_rgb565_cfg/init_done'}]
    sn=[root(sg,x) for x in names];mn=[]
    for x,a in zip(names,sn):
     try:mn.append(root(g,x))
     except RuntimeError:
      ds=sr.drivers(a);require(len(ds)==1 and ds[0].endswith('/Q'),'Missing root is not exact synthesis Q')
      op=retained_output(g,ds[0].rsplit('/',1)[0],['Q','Q0','L5Q','L6Q']);mn.append(g['pin_net'][op])
    row['reset_boundary_binding']=[{'names':sorted(x),'synthesis_net':a,'mapped_net':b,'synthesis_drivers':sr.drivers(a),'mapped_drivers':mr.drivers(b),'mapped_driver_records':{op.rsplit('/',1)[0]:g['primitives'][op.rsplit('/',1)[0]] for op in mr.drivers(b)}} for x,a,b in zip(names,sn,mn)]
    row['reset_boundary_semantic_limit']='Truth-table comparison cuts at exact retained source-register outputs. Source-register transformations (including inverted/packed LUT+FF drivers) still require decoded official gop behavior; this conditional cone comparison does not prove those boundary transformations.'
    st=Cone(sg);mt=Cone(g);table=[]
    for vals in itertools.product([0,1],repeat=4):
     sv=st.value(sg['pin_net'][s['reset']],dict(zip(sn,vals)));mv=mt.value(g['pin_net'][row['reset']],dict(zip(mn,vals)))
     x,cn,ctrl,init=vals;table.append({'inputs':list(vals),'synthesis':sv,'mapped':mv,'expected':x|(1-cn)|(1-(ctrl&init))})
    row['reset_complete_truth_table']=table;row['synthesis_reset_cone']=st.records;row['mapped_reset_cone']=mt.records
    row['checks']['reset_function_exact_original']=len(table)==16 and all(x['mapped']==x['synthesis']==x['expected'] for x in table)
  except Exception as ex:row['errors'].append(str(ex))
  row['passed']=bool(row['checks']) and all(row['checks'].values()) and not row['errors']
 distinct=len({x.get('cell') for x in rows if x.get('cell')})==60
 sites=len({x['planned_site'] for x in rows})==60
 qdistinct=len({g['pin_net'].get(x.get('Q')) for x in rows if x.get('Q')})==60
 save('rows60.json',{'rows':rows,'distinct_cells':distinct,'distinct_registered_Q_nets':qdistinct,'distinct_sites':sites,'types':dict(collections.Counter(x.get('type','UNBOUND') for x in rows))})
 save('adjacent_Q_D.json',{'rows':pairs,'count':len(pairs),'passed':len(pairs)==36 and all(all(x[k] for k in ['actual_Q_D','synthesis_Q_D','clock_same','reset_same']) for x in pairs)})
 save('artifact_provenance.json',provenance)
 after=snapshot();save('after_hashes.json',after);unchanged=before==after
 models=load(H/'official_model_evidence.json')['models'];model_after={p:sha(p) for p in models}
 save('official_models_after_hashes.json',{'after':model_after,'before':{p:v['sha256'] for p,v in models.items()},'unchanged':all(model_after[p]==v['sha256'] for p,v in models.items())})
 save('protection_comparison.json',{'passed':unchanged,'count':len(before),'changed':{p:{'before':before.get(p),'after':after.get(p)} for p in set(before)|set(after) if before.get(p)!=after.get(p)}})
 result={'status':'PASS_INDEPENDENT_MAPPED_ENDPOINT60_REVIEW' if unchanged and distinct and sites and all(x['passed'] for x in rows) else 'FAIL','rows':60,'distinct_storage_cells_observed':60 if distinct else None,'types':dict(collections.Counter(x.get('type','UNBOUND') for x in rows)),'functional_and_structural_checks_excluding_official_behavior_pass':all(not x['errors'] and all(v for k,v in x['checks'].items() if k!='official_gop_behavior_decoded') for x in rows),'failed_rows':[{'target':x['synthesis_target'],'failed_checks':[k for k,v in x['checks'].items() if not v],'errors':x['errors']} for x in rows if not x['passed']],'protection_unchanged':unchanged,'original_mapping60_status':load(E/'final_result.json')['status'],'consumer_needed_compatibility':['Bind fresh60 exact original GTP retained instance plus planned site, mapped PAP_LOC and native PCF actual cell; do not require lost logical alias.','Recognize only model-proven exact gopQ variants and oneFF gopLUT6Q variants; reject SRL/QQ/multistorage/unknown types.','Expose L6Q as registered Q; integrated D is the fully decoded LUT function, not a nonexistent external D port.','Use actual RS/CLK/CE endpoints and parameter proof; ordinary consumers must accept retained ff/site endpoints instead of cr[0] alias.'],'pnr':False,'bit':False,'program':False,'remote':False,'PDS_invoked':False}
 save('final_result.json',result)
 save('review_output_hashes.json',{str(p.relative_to(H)):sha(p) for p in H.rglob('*') if p.is_file() and p.name!='review_output_hashes.json'})
 print(json.dumps({k:result[k] for k in ['status','types','functional_and_structural_checks_excluding_official_behavior_pass','protection_unchanged']},indent=2),flush=True)
 print('NONMODEL_ERRORS',[(x['synthesis_target'],x['errors'],[k for k,v in x['checks'].items() if not v and k!='official_gop_behavior_decoded']) for x in rows if x['errors'] or any(not v for k,v in x['checks'].items() if k!='official_gop_behavior_decoded')],flush=True)
if __name__=='__main__':
 try:main()
 except Exception:
  save('actual_review_failure.json',{'status':'FAIL','traceback':traceback.format_exc()});print(traceback.format_exc(),flush=True);sys.exit(1)
