from pathlib import Path
import sys,json,re,hashlib,time,collections
sys.dont_write_bytecode=True
E=Path(__file__).resolve().parent;B=E.parent/'source_diagnostics_timing_build_04'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for part in iter(lambda:f.read(4*1024*1024),b''):h.update(part)
 return h.hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def save(n,x):
 p=E/n
 if p.exists():raise RuntimeError('Refuse overwrite '+str(p))
 p.write_text(json.dumps(x,indent=2,ensure_ascii=True)+'\n',encoding='ascii')
guard=load(E/'protection_before.json');after={p:sha(p) if Path(p).is_file() else None for p in guard};drift=[p for p in guard if after[p]!=guard[p]]
save('protection_after_all.json',{'hashes':after,'fixed_file_count':len(guard),'drift':drift,'new_concurrent_files_excluded':True})
copies=load(E/'copyhash.json');copy_after=[]
for row in copies:
 p=Path(row['copy']);h=sha(p) if p.is_file() else None;copy_after.append({**row,'after_sha256':h,'unchanged':h==row['copy_sha256']})
save('copyhash_after.json',copy_after)
binding=load(E/'official_model_binding60_refined.json');mg=load(B/'evidence/runtime/mapping60_01/mapping/analysis/graph.json');rg=load(E/'routed/analysis/graph.json');old=load(E.parent/'build04_mapped_endpoint_review02/rows60.json')['rows'];delta=[]
for a,s in zip(binding['rows'],old):
 mc=s['cell'];rc=a['routed_cell'];ports=[]
 for pinrole,mp,rp in [('Q',s['Q'],rc+('/L6Q' if rc+'/L6Q' in rg['pin_net'] else '/Q')),('CLK',mc+'/CLK',rc+'/CLK'),('RS',mc+'/RS',rc+'/RS')]+[('D' if k=='D' else k,mc+'/'+k,rc+'/'+k) for k,v in mg['primitives'][mc]['ports'].items() if v['direction']=='INPUT' and k not in {'CLK','RS','CE'}]:
  mn=mg['pin_net'].get(mp);rn=rg['pin_net'].get(rp);aa=mg['net_aliases'].get(mn,[]);bb=rg['net_aliases'].get(rn,[])
  ports.append({'role':pinrole,'mapped_pin':mp,'routed_pin':rp,'mapped_net':mn,'routed_net':rn,'mapped_endpoints':mg['netpins'].get(mn,[]),'routed_endpoints':rg['netpins'].get(rn,[]),'mapped_aliases':aa,'routed_aliases':bb,'alias_set_changed':set(aa)!=set(bb)})
 delta.append({'logical':s['logical'],'mapped_cell':mc,'routed_cell':rc,'site':s['planned_site'],'V_instance':a['V_instance'],'parameter_changes':a['parameter_changes'],'ports':ports})
save('mapped_routed_endpoint_delta60.json',{'rows':delta,'same_graph':False,'review_policy':'Every alias/endpoint delta is preserved. Exact site and V-origin binding plus separate data/reset/clock contracts do not imply unchanged MAP graph.'})
pending=[{'logical':r['logical'],'mapped_cell':r['mapped_cell'],'routed_cell':r['routed_cell'],'site':r['mapped_site'],'V_instance':r['V_instance'],'unresolved_port_bindings':{k:v for k,v in r['port_binding'].items() if not v['exact_alias_net_equal']},'proven_conditional_reset_truth_table':True,'state':'PENDING_INDEPENDENT_REVIEW_NO_AUTO_ACCEPT'} for r in binding['rows'] if any(not v['exact_alias_net_equal'] for v in r['port_binding'].values())]
save('independent_review_handoff.json',{'SR_alias_rows19':pending,'all_endpoint_delta_file':'mapped_routed_endpoint_delta60.json','upstream_boundary_transform_records':'stage_and_boundary_contract_evidence.json','boundary_transform_acceptance':False,'unknown_acceptance':False,'original_attempt_failure_preserved':'failure.json','continuation_explanation':'Controller initially counted PLC and PNR ADF together. Official PNR exited 0 and done; only gen_netlist and switch_db continuation ran, no repeated PNR.'})
models=load(E/'official_library_binding.json');model_after={entry['path']:{'expected':entry['sha256'],'actual':sha(entry['path'])} for entries in models['closure'].values() for entry in entries}
save('official_library_hashes_after.json',model_after)
submitted={str(p):sha(p) for p in E.glob('*.tcl')};forbidden={str(p):[x for x in p.read_text().splitlines() if re.match(r'\s*(?:compile|synthesize|syn|dev_map|gen_bit_stream|bit)\b',x)] for p in E.glob('*.tcl')}
save('toolhash_and_command_audit.json',{'submitted_tool_scripts':submitted,'forbidden_command_lines':forbidden,'pds_shell':{'path':'C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe','sha256':sha('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')},'producer_analysis_scripts':{str(p):sha(p) for p in E.glob('*.py')},'watcher_scripts':{str(p):sha(p) for p in E.glob('*.ps1')},'parser':{str(E/'routed/analysis/parse_objects.py'):sha(E/'routed/analysis/parse_objects.py')}})
native=load(E/'native_route_diagnostics.json');stage=load(E/'stage_and_boundary_contract_evidence.json');artifact=load(E/'actual_final_route_binding.json');functional=E/'functional/generate_netlist/v7_sdt_top_sim.v'
receipts={label:load(E/(label+'_receipt.json')) for label in ['pnr','functional','graph']}
result={'status':'DIAGNOSTIC_PNR_FUNCTIONAL_EXPORT_COMPLETE_REVIEW_BLOCKED','actual_pids':{n:load(E/(n+'_process.json'))['pid'] for n in ['help','pnr','functional','graph']},'stage_exit_codes':{n:r['exit_code'] for n,r in receipts.items()},'official_pnr_done':native['official_pnr_done'],'routed_adf':artifact,'functional_netlist':{'path':str(functional),'size':functional.stat().st_size,'sha256':sha(functional)},'full_functional_compile':load(E/'functional_compile_receipt.json')['passed'],'actual_V_instances':len(load(E/'functional_instance_inventory.json')['cells']),'storage60':binding['distinct_storage'],'site60':binding['distinct_sites'],'V_FFASYN60':binding['distinct_V_FFASYN'],'clock_identity_pass':stage['clock_identity_pass'],'stage_contract_issues':stage['unresolved'],'reset32_truth_tables_pass':sum(x['passed'] for x in binding['reset_cone_contracts']),'raw_pnr_errors':native['raw_errors'],'native_pnr_errors':native['native_errors'],'fixed_input_drift':drift,'copy_drift':[r for r in copy_after if not r['unchanged']],'model_drift':[p for p,v in model_after.items() if v['expected']!=v['actual']],'source741':len(load(E/'sourcehash.json')),'registered186':len(load(E/'registration186.json')),'full_source_copy_files':len(load(E/'full_sourcehash.json')),'blockers':['19 SR physical-net/graph-alias identities require independent review. Actual reset V truth tables passed conditionally; no alias auto-accept.','Upstream reset boundary GTP-to-packed L5Q/L6Q/inverted transformations require independent semantic review; original GTP and actual V parameters/connections captured.','STA contains negative setup/hold/removal slack; native summary and hold-fix log independently preserved without replacing either.','IO final bank/electrical review and timing/reload acceptance remain pending. Native IO report has 112 rows; no final acceptance inferred.'],'timing_acceptance':False,'reload_acceptance':False,'IO_final_acceptance':False,'bit':False,'remote':False,'flash':False,'initial_controller_artifact_count_failure_preserved':True,'PNR_rerun':False,'time':time.time()}
save('final_result.json',result)
report='''# Diagnostic PNR / official behavior export 结果

仅新建 build04_diagnostic_behavior_route01。PNR / gen_netlist / switch_db 均实际退出 0；官方 PNR 和 Generate Netlist 均 done。原 build04/03/02、review02、export01 固定输入保护检查见 protection_after_all.json；新增并发文件不参与假冲突判定。

实际 PNR PID 60168；功能导出 PID 40812；图导出 PID 65580。最终 route 为 work/place_route/v7_sdt_top_pnr.adf，原生 prr.db / .prr / logs 和 PLC ADF 全部保留。官方功能网表 functional/generate_netlist/v7_sdt_top_sim.v 为真实 V_* 网表，完整官方模型库编译通过。全部模型及 UDP 依赖 hashes、选择记录和 ModelSim 契约见 official_library_binding.json、official_library_hashes_after.json 与 *_contract.json。

60 storage / 60 site / 60 V_FFASYN 精确绑定见 official_model_binding60_refined.json。32 个 reset storage 的 SR 锥均通过 16 组合边界真值表。60 clock identity、逐级 D/reset-release 契约见 stage_and_boundary_contract_evidence.json。PNR 改动包含 12 个 _L6Q_perm 重命名与 INIT 输入位重排、8 个 RSMUX_SEL LOCAL→CHAIN；完整 mapped→routed cell+site / endpoint / alias 差异见 mapped_routed_endpoint_delta60.json。不能把 route 冒称 MAP 同图。

仍阻断：19 行 SR 物理网与 graph alias 的独立确认；上游 reset 边界 GTP→packed L5Q/L6Q/inv 变换语义审查；STA 的 setup/hold/removal 负 slack；IO 最终 bank/electrical 与 timing/reload 验收。逐条交接见 independent_review_handoff.json。原始 STA 摘要和 hold-fix 日志数值可能不同，均原样保存，不以较好值覆盖。工具 raw/native PNR fatal/unknown/unresolved/Timing-4006/STA-3016 检出为 0。

首次控制器把 PLC 与 PNR ADF 同计为两个候选而误停；failure.json 原样保留。continue_export.py 只选择明确最终 _pnr.adf 并执行 gen_netlist / switch_db，无 PNR 或 compile/synth/dev_map 重跑。初轮分析的严格同名拒绝及后续精确修正证据均保留。

source741 / registration186 / full copy ledger / copyhash before+after / submitted tool script hashes / protection after / raw logs / native receipts 齐全。本结果仅模型诊断，不作最终 timing/reload 验收；未执行 bit、remote 或 Flash。
'''
(E/'RESULT_ZH.md').write_text(report,encoding='utf-8')
save('evidence_hashes.json',{str(p):sha(p) for p in E.rglob('*') if p.is_file()})
print(json.dumps({k:result[k] for k in ['status','stage_exit_codes','storage60','site60','V_FFASYN60','clock_identity_pass','reset32_truth_tables_pass','fixed_input_drift','copy_drift','model_drift']},indent=2))
