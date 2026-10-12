"""New candidate-specific expectation after review02 evidence passes; no legacy edits."""
from pathlib import Path
import hashlib,itertools,json,re,sys
sys.dont_write_bytecode=True
P=Path(__file__).resolve().parent;B=P.parent;S=B/'source_diagnostics_timing_build_04';R=B/'build04_mailbox_clock_review01'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def save(n,v):(P/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def main():
 source=S/'rtl/v7_sfd_candidate.v';raw=source.read_bytes();old=(B/'source_diagnostics_timing_build_01/rtl/v7_sfd_candidate.v').read_bytes();orig=(B/'source_frame_diagnostics_candidate/v7_sfd_candidate.v').read_bytes()
 def assigns(b):return [re.sub(rb'\s+',b'',m.group()) for m in re.finditer(rb'mailbox\[[^;]+;',b)]
 assert len(assigns(raw))==16 and assigns(raw)==assigns(old)==assigns(orig)
 assert raw.count(b'mailbox<=0;')==1 and raw.count(b'host_bank<=0;')==1 and raw.count(b'host_bank<=mailbox;')==1
 assert b'if(edge_vs)' in raw and b'if(armed)' in raw and b'if(busy)' in raw
 assert re.search(rb'if\(busy\)\s*sticky_overrun<=1;\s*else begin\s*request<=~request;\s*mailbox\[',raw)
 assert b'if(snapshot_available && acquire_strobe)' in raw
 alias=[240]+[480+b for b in range(32) if (0x53464401>>b)&1]
 widths=[32,24,16,16,24,24,24,24,24,24,24,16,8,16,24]
 zero=sorted({w*32+b for w,width in enumerate(widths) for b in range(width,32)}|{480+b for b in range(32) if not(0x53464401>>b)&1})
 mailbox=[];host=[]
 # Full one-step inductive cases tied to actual nested RTL control, reset priority.
 for prev,rst,edge,armed,busy in itertools.product(range(2),repeat=5):
  wr=edge and armed and not busy;v=0 if rst else 1 if wr else prev
  mailbox.append({'previous':prev,'rst_c':rst,'edge_vs':edge,'armed':armed,'busy':busy,'write':bool(wr),'next11':[v]*11})
 for prev,rst,valid,req,ack,acquire,src in itertools.product(range(2),repeat=7):
  en=not rst and not valid and req!=ack and acquire;v=0 if rst else src if en else prev
  host.append({'previous':prev,'rst_h':rst,'snapshot_valid':valid,'req_sync2':req,'ack':ack,'acquire_strobe':acquire,'source':src,'capture_enable':bool(en),'next11':[v]*11})
 induction={'source_path':str(source),'source_sha256':sha(source),'old_and_original_exact_payload_assignments':True,'payload_assignments':[x.decode() for x in assigns(raw)],'logical_bits_per_camera':512,'word7_bit16':240,'magic_word15':'53464401','alias_group_per_camera':alias,'zero_per_camera':zero,'mailbox_next':'rst_c ? 0 : (edge_vs && armed && !busy ? 1 : previous)','host_next':'rst_h ? 0 : (!snapshot_valid && req_sync[2]!=ack && acquire_strobe ? equal_mailbox_value : previous)','mailbox_induction32_cases':mailbox,'host_induction128_cases':host,'initial_state':'reset=0; equality preserved on every camera/host event, including asynchronous assertion','all2048_coverage':'each camera512 =330 registerLogical +182zero; 330=319 singleton +11 equal lane group; physical320=319 singleton+1 representative','zero_induction':'all182 zero lanes are reset0, every successful write0, hold0, host reset0/capture0/hold0','scope':'offline original/build01/current RTL equivalence, actual graph connectivity and read cones; mapped60 official behavior remains external'}
 save('sharedlaneRTL_contract.json',induction)
 # Extract real KEEPBUF specialization CELL bytes independently, preserving offset.
 dump=S/'evidence/runtime/compile/synthesis_export/synthesis_dump.txt';data=dump.read_bytes();schemas=[]
 for match in re.finditer(rb'\(CELL\s+(bmsKEEPBUF(?:_Cell_\d+)?)\s',data):
  stack=[];node=None;end=None
  for t in re.finditer(rb'"(?:[^"\\]|\\.)*"|\\[^\s]+|[()]|[^\s()]+',data[match.start():]):
   v=t.group()
   if v==b'(':stack.append([])
   elif v==b')':
    x=stack.pop()
    if not stack:node=x;end=match.start()+t.end();break
    stack[-1].append(x)
   else:stack[-1].append(v)
  def nodes(n,key):
   if isinstance(n,list):
    if n and n[0]==key:yield n
    for x in n:yield from nodes(x,key)
  params=list(nodes(node,b'PARAMETER'));ports=list(nodes(node,b'PORT'))
  assert len(params)==1 and params[0][1:3]==[b'WIDTH',[b'DATATYPE',b'INTEGER']]
  width=int(params[0][3][1]);assert len(ports)==2
  schema={p[1][1].decode():{'range':[int(p[1][2]),int(p[1][3])],'direction':next(nodes(p,b'DIRECTION'))[1].decode()} for p in ports}
  assert schema=={'I':{'range':[width-1,0],'direction':'INPUT'},'Z':{'range':[width-1,0],'direction':'OUTPUT'}}
  assert not list(nodes(node,b'CLOCK')) and not list(nodes(node,b'CONTENTS'))
  schemas.append({'type':match[1].decode(),'WIDTH':width,'schema':schema,'byte_start':match.start(),'byte_end':end,'cell_bytes_sha256':hashlib.sha256(data[match.start():end]).hexdigest(),'raw_cell':data[match.start():end].decode('ascii')})
 assert len(schemas)==14 and {x['type']:x['WIDTH'] for x in schemas}=={'bmsKEEPBUF':32,'bmsKEEPBUF_Cell_1':1,'bmsKEEPBUF_Cell_2':3,'bmsKEEPBUF_Cell_3':2,'bmsKEEPBUF_Cell_4':17,'bmsKEEPBUF_Cell_5':128,'bmsKEEPBUF_Cell_6':16,'bmsKEEPBUF_Cell_7':8,'bmsKEEPBUF_Cell_8':4,'bmsKEEPBUF_Cell_9':5,'bmsKEEPBUF_Cell_10':10,'bmsKEEPBUF_Cell_11':12,'bmsKEEPBUF_Cell_12':7,'bmsKEEPBUF_Cell_13':28}
 save('independent_KEEPBUF_raw_schema.json',{'source':str(dump),'dump_sha256':sha(dump),'cells':schemas,'model_snippet_sha256':sha(P/'official_KEEPBUF_exact.v'),'clock_traversal_allowed_specialization':'bmsKEEPBUF_Cell_1 WIDTH=1 only'})
 manifest=load(S/'manifest.json');sets=load(P/'fresh_exact_sets.json')
 cmr=S/'compile/v7_sdt_top.cmr';cmrbytes=cmr.read_bytes();input_section=cmrbytes[:cmrbytes.index(b'| Output')]
 rootprefix=S.resolve().as_posix()+'/'
 inputpaths=[x.decode().strip()[len(rootprefix):] for x in re.findall(rb'C:/[^\r\n|]*',input_section) if x.decode().strip().startswith(rootprefix)]
 sources=[x for x in inputpaths if not x.endswith('.idf')]
 assert len(sources)==186 and sources==manifest['registered_sources']
 projectbindings={}
 for name in ['project.pds','project_template.pds']:
  project=S/name;pr=project.read_bytes()
  reg=[x.decode() for x in re.findall(rb'\(_file "([^"]+)"\s*\(_format (?:verilog|system_verilog|vhdl)\)',pr)]
  assert len(reg)==186 and set(reg)==(set(sources)-{'rtl/v7_sdt_top.v'})|{'compile/v7_sdt_top.cmr'}
  projectbindings[name]=sha(project)
 save('registered186_actual_CMR_binding.json',{'compile_report_sha256':sha(cmr),'input_source_paths_exact_manifest_order':sources,'IP_IDF_input_count':len(inputpaths)-len(sources),'project_hashes':projectbindings,'compiled_project_top_substitution':{'source_top':'rtl/v7_sdt_top.v','postcompile_entry':'compile/v7_sdt_top.cmr','verified':'CMR input section contains all186 exact manifest source paths, including original source top; PDS has185 source entries plusCMR. This is recorded separately from manifest registered_sources count.'}})
 if '--proof-only' in sys.argv:
  print('independent RTL induction,14 rawKEEPBUF schemas and186 actualCMR registrations passed',flush=True);return
 assert load(P/'recompute_result.json')['status']=='PASS_INDEPENDENT_OFFLINE_RECOMPUTATION'
 assert load(P/'cycle_result.json')['status']=='PASS_FRESH_RTL_CYCLE_MITER'
 assert load(P/'boolean_exhaustive_result.json')['status']=='PASS_FRESH_EXHAUSTIVE_BOOLEAN_EQUIVALENCE'
 rawtypes=load(P/'independent_raw_type_schema_results.json')
 assert len(rawtypes)==4 and all(x['status']=='PASS_RAW_ADIF_TYPES_PORT_NAMES' for x in rawtypes)
 for n,h in load(R/'output_hashes.json').items():assert sha(R/n)==h,n
 for p,h in load(R/'input_binding.json').items():assert sha(Path(p))==h,p
 for n,h in manifest['local_hashes'].items():assert sha(S/n)==h,n
 save('final_source_and_ledger_no_drift.json',{'review01_final_bundle_58_entries':58,'review01_intermediate_ledger55_entries':len(load(R/'output_hashes.json')),'final_ledger_sha256':sha(R/'final_bundle_hashes.json'),'intermediate_ledger_sha256':sha(R/'output_hashes.json'),'final_source741_and_input775_reverified':True,'drift':[]})
 graphs={}
 for stage in ['compile','actual','mapping60_01/mapping']:
  root=S/'evidence/runtime'/stage
  for n in ['analysis/graph.json','synthesis_export/synthesis_dump.txt','synthesis_export/synthesis_dump.v']:graphs[str((root/n).relative_to(S))]=sha(root/n)
 evidence={n:sha(P/n) for n in ['artifact58_rehash.json','source741_registered186_rehash.json','registered186_actual_CMR_binding.json','fresh_exact_sets.json','independent_raw_actual.json','independent_raw_compile.json','independent_raw_mapping60_01_mapping.json','independent_build01_raw_and_trajectory.json','independent_raw_type_schema_results.json','fresh_keepbuf_counterexamples8.json','fresh_clock_exact_audit.json','recompute_result.json','cycle_result.json','cycle_simulation.log','sharedlaneRTL_contract.json','independent_KEEPBUF_raw_schema.json','frozen1320_gate_reject.log','final_source_and_ledger_no_drift.json']}
 contract={'schema':'candidate-specific-mailbox-expectation/v1','candidate_id':manifest['candidate_id'],'decision':'仅此source_candidate04及绑定graph的独立离线证明通过；新producer/consumer须显式绑定本合同','source_candidate04':{'root':str(S),'manifest_sha256':sha(S/'manifest.json'),'source04hash_sha256':sha(S/'source04hash.json'),'local_hashes741':manifest['local_hashes'],'registered_sources186':manifest['registered_sources'],'graph_and_raw_hashes':graphs,'candidate_RTL_sha256':sha(source)},'expected':{'logical2048':2048,'registerLogical1320':1320,'uniquePhysical1280':1280,'zero728':728,'alias40':40,'per_camera':{'logical':512,'registerLogical':330,'uniquePhysical':320,'zero':182,'alias':10},'corners':['Slow','Fast'],'exact_scored_pair_corner_records2560':2560},'semantic_partition':{'logical_keys':sets['logical2048'],'zero_keys':sets['zero728'],'alias_group_each_camera':alias,'synthesis_physical_pairs':sets['physical1280'],'fresh_sets_sha256':sha(P/'fresh_exact_sets.json')},'sharedlaneRTL':{'path':'sharedlaneRTL_contract.json','sha256':sha(P/'sharedlaneRTL_contract.json')},'timing':{'set_max_delay_datapath_only_ns':15.238,'U':368,'carved_camera_to_DDR':4,'retained_exact_clock_relations':364,'DDR_MHz':131.25,'constraint_draft_sha256':sha(R/'diagnostic_constraint_DRAFT/clock.fdc'),'clock_audit_sha256':sha(P/'fresh_clock_exact_audit.json'),'preserve_original_createclock_uncertainty_DDR_multicycle_bytes':True,'new_same_domain_falsepaths_allowed':False,'exact_hold_and_ACK_first_exceptions_only':True},'producer_consumer_binding':{'must_bind_contract_sha256':True,'must_rehash_all_source_and_registered_inputs':True,'fresh_route_rebuild_required':True,'must_independently_rederive_all2048_semantics_from_raw_routed_graph':True,'must_match_exact_zero_set_alias_partition_and_actual_count':True,'physical_names':'rederive actual routed Q/CLK/D; do not inherit synthesis endpoint names blindly','report_set':'exact independently reconstructed1280 actual CLK-to-D pairs ×Slow/Fast;2560 unique scored records with actual MaxDelay Path15.238 exception and corner','reject':['any source/graph/hash binding mismatch','actual count other than1280 or per-camera count other than320','different logical/zero/alias semantic sets even when total count equals1280','duplicate/missing/extra pair-corner records','cross-camera or nonexclusive pair','from/to Cartesian product reports','logical alias duplicate counted as physical report','old1320 reports or inherited old gate PASS','unscored record, wrong corner, missing/wrong15.238 exception','new same-domain falsepath'],'old_gate_policy':'旧1320 producer/consumer保持原样；旧1320报告不能继承；必须新建并显式绑定producer/consumer','acceptance_policy':'only_exact_bound_candidate_identity_and_exact_semantic_sets; no any_count policy'},'independent_review_evidence':evidence,'constraints_qualified':False,'runtime_STA_passed':False,'pds_started':False,'board_actions':False,'remaining_external_gates':['mapped60官方行为及完整endpoint签核由另一agent独立完成','fresh route原始图和精确2560有分数双corner报告','vendor timing reload replacement/no-remap证据','IO/full STA/板级独立gates']}
 contract['source_candidate04']['full_source_copy_hashes742']=manifest['full_source_copy_hashes']
 contract['source_candidate04']['registered186_actual_CMR_binding_sha256']=sha(P/'registered186_actual_CMR_binding.json')
 expected_records=[{'semantic_pair_logical_members':p['logical_members'],'synthesis_launch_Q':p['Q'],'synthesis_launch_CLK':p['Q'].rsplit('/',1)[0]+'/CLK','synthesis_capture_D':p['D'],'corner':corner,'required_actual_exception':'MaxDelay Path','required_datapath_only_ns':15.238,'fresh_route_actual_Q_CLK_D_binding_required':True,'score_required':True} for p in sets['physical1280'] for corner in ['Slow','Fast']]
 assert len(expected_records)==2560 and len({(r['synthesis_launch_CLK'],r['synthesis_capture_D'],r['corner']) for r in expected_records})==2560
 save('expected_pair_corner2560.json',{'identity':'exact semantic pair membership from independently verified candidate04; actual routed endpoints must be freshly bound','records':expected_records})
 contract['exact_pair_corner_expectation']={'path':'expected_pair_corner2560.json','sha256':sha(P/'expected_pair_corner2560.json'),'records':2560,'actual_report_requirement':'each fresh routed actual pair binds exactly one semantic membership key; exactly Slow+Fast scored records per key; reject missing/extra/duplicate/mismatch'}
 evidence['expected_pair_corner2560.json']=sha(P/'expected_pair_corner2560.json')
 evidence.update({n:sha(P/n) for n in ['boolean_exhaustive_result.json','boolean_exhaustive.log','tb_boolean_exhaustive.sv']})
 storage=load(P/'actual1280_storage_control_identity.json')
 assert len(storage['cameras'])==4 and all(x['physical_records']==320 and x['all_storage_GTP_DFF_CE_INIT0_GRS_TRUE_no_override'] for x in storage['cameras'])
 evidence['actual1280_storage_control_identity.json']=sha(P/'actual1280_storage_control_identity.json')
 save('candidate_specific_expectation_contract.json',contract)
 save('decision_ZH.json',{'decision':'接受此候选1280物理pair的离线身份与等值共享证明，生成新candidate-specific expectation；不继承旧gate/1320报告','scope_pass':list(evidence),'logical':2048,'registerLogical':1320,'uniquePhysical':1280,'zero':728,'alias':40,'contract_sha256':sha(P/'candidate_specific_expectation_contract.json'),'all_required_offline_checks_passed':True,'runtime_STA_passed':False,'constraints_qualified':False,'remaining_external_gates':contract['remaining_external_gates']})
 text='''# build04 mailbox / clock 独立审阅02

结论：本候选离线核验全部通过，接受绑定 source_candidate04 原始字节与实际图的 1280 唯一物理 pair 身份，交付新的 candidate-specific expectation contract。旧 1320 gate 未修改，实际重跑仍拒绝1280；旧1320报告不可继承。未启动PDS、PnR或板操作。mapped60官方行为由另一agent负责，本报告不重复签核。

58个封存产物逐文件重算SHA256（目录共60文件，另2个是封存账本）；中间账本55项也全部复验。原manifest的741 local hashes、186注册source、742 full-source-copy项、775 input bindings和prepare fresh图绑定逐项核对。实际CMR的186 source输入与manifest路径及顺序完全相等，另含15个IP IDF；编译后PDS实际为185个source加1个CMR入口替换顶层RTL，已单独核对封存，不将其混报成186 RTL直接入口。证据见 artifact58_rehash.json、source741_registered186_rehash.json、registered186_actual_CMR_binding.json。结束再次核对旧58文件及741/775输入未变。

fresh resolve重新穷举2048个read cone并与原manifest逐字段相等。独立集合计算确认2048=1320逻辑寄存器记录+728精确零；1320=1280唯一物理pair+40共享alias；每camera320。所有实际source Q网完整pin集合恰为{Q,D}，无跨camera。四个11位组精确为240及magic 53464401的10个置1位；240是word7 bit16。没有把这些顺序状态当恒1。

共享轨迹证明绑定实际RTL全文哈希与原始/build01完全相同的16条mailbox字段赋值。32个完整mailbox控制组合及128个host控制组合做单步归纳：共同reset0、成功snapshot写1、否则hold；host同reset/acquire采样。182零/camera亦reset0/write0/hold0。新增仿真用官方GTP模型，四camera各40000周期，246899次观察，逐次比较实际build04、build01及原始模型的全部512 mailbox、512 host位和总线输出，均一致；见 cycle_simulation.log、sharedlaneRTL_contract.json。另重跑实际build01/build04计数器524288、gap1048576个完整16bit状态/控制转移，含prefix/next_q检查均通过，见 boolean_exhaustive.log。仿真是有限轨迹，共享/零覆盖另由归纳和fresh read-cone穷举证明。

原始ADIF字节reader独立于生产graph parser，重新展开compile/synthesis/mapped全部primitive连接类，逐pin与完整图比较。额外对build01原始ADIF全部连接类复验；四阶段另外逐cell核对原始leaf type与完整port name集合，防止连接相同但类型错误。旧11条独立mailbox有同D=1、CLK/C/CE/default参数，host同控制并各自连接旧Q，精确40旧pair消失且没有新增pair。见 independent_raw_*.json、independent_build01_raw_and_trajectory.json；mapped仅复验连接，不作官方storage模型签核。

KEEPBUF核对安装官方模型原字节assign Z=I，无storage；另从原compile ADIF提取14个实际specialization完整CELL字节、offset、hash与WIDTH/I/Z精确schema，Cell编号不视为WIDTH。fresh adapter保留严格vector数据支持，clock新增仅Cell_1/WIDTH1。8个恶意类型/schema/control/unknown-sink反例重新执行全部拒绝。所有无输出终点在pin_net及完整netpins确无Z连接，明确记录no-storage终点，不删除未知sink。见 independent_KEEPBUF_raw_schema.json、fresh_keepbuf_counterexamples8.json。

fresh compile/synthesis clock traversal与原coverageproof完整相等；独立重建实际补集，camera0/1=836、camera2/3=844，预算launch不在补集中。原368有向关系仅刻4条camera→DDR，保留364；新增380条命令逐条精确相等，15.238ns/DDR131.25MHz固定；原create_clock/create_generated_clock/uncertainty/DDR multicycle32条保持字节。无新增同域falsepath。见 fresh_clock_exact_audit.json。

candidate_specific_expectation_contract.json绑定本真实source/graph和独立证明hash，要求后续新producer/consumer显式绑定合同hash；fresh route必须从原始图独立重建相同2048语义集合、728零集合、四共享组、实际1280及320/camera，否则拒绝。要求独立routed1280 pair×Slow/Fast精确2560条有分数记录，每pair为真实MaxDelay Path15.238；拒绝缺失、多余、重复、笛卡尔积、hash/count/semantic mismatch及旧1320报告。保留原预算及精确hold/ACK例外，不提供any_count策略。

这是新候选身份限定的物理期望合同，不是旧条件修改。constraints_qualified=false、runtime_STA_passed=false。实际route、vendor timing replacement/no-remap、mapped60官方行为、IO/full STA仍需各自证据；本离线通过不解除它们。新合同SHA256及证据hash见decision_ZH.json和review02_hashes.json。
'''
 (P/'REPORT_ZH.md').write_text(text,encoding='utf8')
 for n,h in load(R/'final_bundle_hashes.json').items():assert sha(R/n)==h,n
 save('review02_hashes.json',{str(p.relative_to(P)):sha(p) for p in P.rglob('*') if p.is_file() and p.name!='review02_hashes.json' and '__pycache__' not in p.parts})
 print('sealed new candidate contract',sha(P/'candidate_specific_expectation_contract.json'),flush=True)
if __name__=='__main__':main()
