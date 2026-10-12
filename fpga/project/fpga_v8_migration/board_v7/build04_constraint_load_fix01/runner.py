from pathlib import Path
import sys,os,json,hashlib,subprocess,time,ctypes,re,traceback,shutil,tkinter
sys.dont_write_bytecode=True
E=Path(__file__).resolve().parent
BOARD=E.parent
B=BOARD/'source_diagnostics_timing_build_04'
F=BOARD/'build04_final_route_runtime01'
W=E/'candidate02'
PDS=Path('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')
ARCH='set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,o):
 p=E/n;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='ascii') as f:json.dump(o,f,ensure_ascii=True,indent=2)
def idle(label):
 ps=json.loads(subprocess.check_output(['powershell','-NoProfile','-Command','ConvertTo-Json -InputObject @(Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,CommandLine) -Compress']))
 busy=[p for p in ps if re.search(r'pds|programmer|^ta\.exe$|^pnr\.exe$|^synplify|^ads\.exe$|^cfg|^pgm|^cdt_(?:cfg|js)',p['Name'],re.I) or (p['ProcessId']!=os.getpid() and p['Name'].lower() in {'python.exe','pythonw.exe'} and re.search(r'run_trial\.py|programwrapper|run_mapping|controller04\.py',p.get('CommandLine') or '',re.I))]
 save(label+'_idle.json',{'time':time.time(),'processes':ps,'busy':busy})
 if busy:raise RuntimeError('Whole machine tools/controller busy')
 trial=BOARD/'goal_board_validation_01/reboot_then_program_pcie_trial07'
 receipt=json.loads((trial/'qualifiedV7_sram.receipt.json').read_bytes())
 raw=(trial/'qualifiedV7_sram.stdout.txt').read_bytes()
 if receipt['exit_code']!=0 or b'"device_done": true' not in raw or b'"program_success": true' not in raw:raise RuntimeError('V7 program has not completed')
def tool(label,text,cwd,project_stage=None):
 idle(label);cwd.mkdir(parents=True,exist_ok=True)
 script=E/(label+'.tcl');script.write_text(text,encoding='ascii')
 cmd=([str(PDS),'-project',str(cwd/'project.pds'),'-run',project_stage,'-work_dir',str(cwd)] if project_stage else [str(PDS),'-file',str(script),'-work_dir',str(cwd),'-project_name','v7_sdt_top'])
 save(label+'_command.json',{'argv':cmd,'script_sha256':sha(script),'tool_sha256':sha(PDS),'controller_sha256':sha(__file__),'project_sha256':sha(cwd/'project.pds') if (cwd/'project.pds').exists() else None,'cwd':str(cwd)})
 start=time.time();log=E/(label+'.log')
 print('真实工具启动 '+label,flush=True)
 with log.open('xb') as f:
  p=subprocess.Popen(cmd,cwd=cwd,stdout=f,stderr=subprocess.STDOUT)
  save(label+'_process.json',{'pid':p.pid,'controller_pid':os.getpid(),'start':start})
  rc=p.wait()
 raw=log.read_bytes()
 errors=[x.decode('ascii','backslashreplace') for x in raw.splitlines() if re.search(rb'^\s*(?:E:|ERROR|FATAL)|Timing-4006|STA-3016|unknown command|unrecognized option',x,re.I)]
 save(label+'_receipt.json',{'rc':rc,'start':start,'end':time.time(),'log_sha256':sha(log),'errors':errors})
 print('真实工具完成 '+label+' rc='+str(rc),flush=True)
 if rc or errors:raise RuntimeError('Actual tool failed '+label)
 return raw
def lock():
 idle('before_mutex_'+str(time.time_ns()))
 k=ctypes.WinDLL('kernel32',use_last_error=True)
 k.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p];k.CreateMutexW.restype=ctypes.c_void_p
 k.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong];k.ReleaseMutex.argtypes=[ctypes.c_void_p];k.CloseHandle.argtypes=[ctypes.c_void_p]
 h=k.CreateMutexW(None,False,'Global\\ov56401_PDS_single_instance');v=k.WaitForSingleObject(h,0)
 if v not in (0,128):raise RuntimeError('Global PDS mutex busy')
 return k,h
def prepare():
 if W.exists():raise RuntimeError('Candidate already exists')
 m=json.loads((B/'manifest.json').read_bytes())
 hashes=m['local_hashes'];assert len(hashes)==741 and len(m['registered_sources'])==186
 frozen={str(p):sha(p) for root in [B,F,BOARD/'build04_replacement_clock_route01',BOARD/'build04_timing_reload_probe01'] for p in root.rglob('*') if p.is_file()}
 if not (E/'frozen_before.json').exists():save('frozen_before.json',frozen)
 W.mkdir()
 for d in ['rtl','inputs']:shutil.copytree(B/d,W/d)
 for n,hv in hashes.items():assert sha(W/n)==hv==sha(B/n),(n,'source mismatch')
 if not (E/'sourcehash.json').exists():save('sourcehash.json',{'count':741,'registered':186,'hashes':hashes,'source_set_sha256':hashlib.sha256(json.dumps(hashes,sort_keys=True,separators=(',',':')).encode()).hexdigest()})
 shutil.copytree(F/'constraints',W/'constraints_live')
 shutil.copy2(BOARD/'production60_target_prepare01/production60_site_DRAFT.lcf',W/'constraints_live/production60.lcf')
 raw=(B/'project.pds').read_bytes()
 sources=[x.decode('ascii') for x in re.findall(rb'\(_file "([^"]+)"',raw) if x.startswith((b'inputs/',b'rtl/'))]
 assert sources==m['registered_sources']
 (W/'project.pds').write_bytes(raw)
 if not (E/'registration186.json').exists():save('registration186.json',sources)
 sys.path.insert(0,str(F/'runtime'))
 from graph_adapter import Resolver,classify
 from derive_new_constraints import coll
 cg=json.loads((B/'evidence/runtime/compile/analysis/graph.json').read_bytes())
 proof=json.loads((F/'coverageproof.json').read_bytes())
 assert proof['mailbox_budget_ns']==15.238 and len(proof['retained_clock_pairs'])==364
 text=(F/'constraints/clock.fdc').read_text(encoding='ascii')
 lines=[line for line in text.splitlines() if not ('get_pins -hierarchical' in line)]
 rows=[];cl=classify(cg)
 for cam in range(4):
  prefix=f'source_diagnostics/cameras[{cam}].source/'
  leaves=set(Resolver(cg).clock_leaves(cam)['leaves'])
  mb={k+'/'+p for k,r in cg['primitives'].items() if k.startswith(prefix+'mailbox[') for p,v in r['ports'].items() if v['clock']}
  host={k+'/'+p for k,r in cg['primitives'].items() if k.startswith(prefix+'host_bank[') for p,v in r['ports'].items() if p.startswith('D[') and v['direction']=='INPUT'}
  assert len(mb)==17 and len(host)==512 and mb<=leaves
  ack=cl['ack_first'][cam]
  lines+=['set_false_path -from '+coll(leaves-mb)+' -to [get_clocks {ddrphy_sysclk}]','set_max_delay -datapath_only 15.238 -from '+coll(mb)+' -to '+coll(host),'set_false_path -hold -from '+coll(mb)+' -to '+coll(host),'set_false_path -from '+coll({ack['launch_CLK']})+' -to '+coll({ack['capture_D']})]
  rows.append({'camera':cam,'mailbox':sorted(mb),'host':sorted(host),'complement':sorted(leaves-mb),'ack':ack})
 (W/'constraints_live/clock.fdc').write_text('\n'.join(lines)+'\n',encoding='ascii')
 save('compile02_constraint_derivation.json',{'graph_sha256':sha(B/'evidence/runtime/compile/analysis/graph.json'),'clock_sha256':sha(W/'constraints_live/clock.fdc'),'U364':proof['retained_clock_pairs'],'budget_ns':15.238,'rows':rows,'syntax':'get_pins -hierarchical dot hierarchy / port; LCF native slash instances'})
 print('隔离来源准备完成：741字节一致，186登记，U364，15.238，DDR131.25，production60',flush=True)
def constraints():return ''.join('add_constraint {'+(W/'constraints_live'/n).as_posix()+'}\n' for n in ['clock.fdc','cdc.fdc','ddr3.fdc','ov5640.fdc','pcie.fdc','sfp.fdc'])
def export(label,db):
 dest=E/label;ana=dest/'analysis';ana.mkdir(parents=True);dump=dest/'synthesis_export/synthesis_dump.txt';dump.parent.mkdir()
 tool(label+'_export',ARCH+'.switch_db -input {'+db.as_posix()+'} -output {'+dump.as_posix()+'}\n',dest)
 shutil.copy2(B/'runtime/analysis_tools/parse_objects.py',ana/'parse_objects.py')
 res=subprocess.run([sys.executable,'-B',str(ana/'parse_objects.py')],cwd=ana,capture_output=True)
 (ana/'parser.log').write_bytes(res.stdout+res.stderr)
 save(label+'_parser_receipt.json',{'rc':res.returncode,'dump_sha256':sha(dump),'adf_sha256':sha(db)})
 assert res.returncode==0
 return json.loads((ana/'graph.json').read_bytes())
def build():
 tool('compile02',ARCH+constraints()+'compile -force_to_run -top_module v7_sdt_top\n',W,'compile')
 cg=export('compile_native',W/'compile/v7_sdt_top_comp.adf')
 old=json.loads((B/'evidence/runtime/compile/analysis/graph.json').read_bytes())
 for key in ['primitives','pin_net','netpins','net_aliases']:
  if key=='primitives':assert {k:(r['type'],r['ports']) for k,r in cg[key].items()}=={k:(r['type'],r['ports']) for k,r in old[key].items()},'compile graph changed'
  else:assert cg[key]==old[key],('compile source graph mismatch',key)
 save('fresh_compile_graph_consistency.json',{'source_graph_equal':True,'graph_sha256':sha(E/'compile_native/analysis/graph.json')})
 tool('synthesize02',ARCH+constraints()+'synthesize -force_to_run -ads\n',W,'synthesize')
 sg=export('synthesis_native',W/'synthesize/v7_sdt_top_syn.adf')
 save('synthesis_ready.json',{'adf_sha256':sha(W/'synthesize/v7_sdt_top_syn.adf'),'graph_sha256':sha(E/'synthesis_native/analysis/graph.json')})
def guard():
 frozen=json.loads((E/'frozen_before.json').read_bytes())
 drift=[p for p,hv in frozen.items() if not Path(p).is_file() or sha(p)!=hv]
 save('frozen_after_'+str(time.time_ns())+'.json',{'files':len(frozen),'drift':drift})
 assert not drift,'Frozen artifact drift'
def mapping():
 from native_audit import cdb,pairs,sites
 sys.path.insert(0,str(F/'runtime'))
 from derive_new_constraints import coll
 from graph_adapter import Resolver,classify
 cg=json.loads((E/'compile_native/analysis/graph.json').read_bytes())
 sg=json.loads((E/'synthesis_native/analysis/graph.json').read_bytes())
 cc=cdb('compile_native');sc=cdb('synthesis_native')
 assert b'15238' in sc,'Fresh synthesis timing CDB did not receive replacement budget'
 assert b'(CLKGP ' not in cc and b'(CLKGP ' not in sc,'Old clock groups survived fresh build'
 syn_count=sum('/host_bank[' in cell and 'D' in rec['ports'] for cell,rec in sg['primitives'].items())
 assert syn_count in {1280,1284,1320},('Unsupported synthesis pair count',syn_count)
 rows=pairs(sg,expected=syn_count)
 save('synthesis_native_pairs'+str(syn_count)+'.json',{'rows':rows,'graph_sha256':sha(E/'synthesis_native/analysis/graph.json'),'signature_constant_pairs':syn_count-1280,'mapped_expected_unique':1280})
 cl=classify(sg);draft=W/'constraints_live/production60.lcf';t=tkinter.Tcl()
 targets=[t.splitlist(line)[1][2:] for line in draft.read_text(encoding='ascii').splitlines() if line.strip() and not line.lstrip().startswith('#')]
 assert len(targets)==60 and all(x in sg['primitives'] and sg['primitives'][x]['type'] in {'GTP_DFF_C','GTP_DFF_P'} for x in targets),'Production60 synthesis paths changed'
 # Re-derive phase-specific targets from fresh synthesis connectivity, with no old aliases.
 base=[x for x in (F/'constraints/clock.fdc').read_text(encoding='ascii').splitlines() if 'get_pins -hierarchical' not in x]
 fresh=[]
 for cam in range(4):
  rr=[r for r in rows if r['camera']==cam and (syn_count!=1284 or int(re.search(r'/host_bank\[(\d+)\]',r['capture_D'])[1])<480)];launch={r['launch_CLK'] for r in rr};capture={r['capture_D'] for r in rr}
  leaves=set(Resolver(sg).clock_leaves(cam)['leaves']);assert launch<=leaves
  signature_clocks={r['launch_CLK'] for r in rows if r['camera']==cam and syn_count==1284 and int(re.search(r'/host_bank\[(\d+)\]',r['capture_D'])[1])>=480}
  ack=cl['ack_first'][cam]
  fresh+=['set_false_path -from '+coll(leaves-launch-signature_clocks)+' -to [get_clocks {ddrphy_sysclk}]','set_max_delay -datapath_only 15.238 -from '+coll(launch)+' -to '+coll(capture),'set_false_path -hold -from '+coll(launch)+' -to '+coll(capture),'set_false_path -from '+coll({ack['launch_CLK']})+' -to '+coll({ack['capture_D']})]
 (W/'constraints_live/synthesis_exact_clock.fdc').write_text('\n'.join(base+fresh)+'\n',encoding='ascii')
 save('fresh_synthesis_constraint_binding.json',{'pairs':1280,'source':str(E/'synthesis_native/analysis/graph.json'),'derived_clock_sha256':sha(W/'constraints_live/synthesis_exact_clock.fdc'),'inherited_compile_CDB_sha256':sha(E/'synthesis_native_CDB_raw.txt'),'note':'Fresh compile CDB is inherited and transformed by synthesis; exact synthesis derivation checks its binding, not a claim that add_constraint overwrites an input DB.'})
 text=ARCH+'add_constraint {'+(W/'constraints_live/synthesis_exact_clock.fdc').as_posix()+'}\nadd_constraint {'+draft.as_posix()+'}\ndev_map -force_to_run -input_db_file {'+(W/'synthesize/v7_sdt_top_syn.adf').as_posix()+'} -override_pcf TRUE -devmap_remove_dups 0 -devmap_const_prop 0 -devmap_control_set_num 0\n'
 tool('mapping02',text,W)
 mg=export('mapping_native',W/'device_map/v7_sdt_top_map.adf');mc=cdb('mapping_native')
 mapped=pairs(mg);save('mapping_native_pairs1280.json',{'rows':mapped,'graph_sha256':sha(E/'mapping_native/analysis/graph.json')});sites(mg)
 assert b'15238' in mc and b'(CLKGP ' not in mc,'Mapping CDB replacement failed'
 assert str(B).replace('\\','/').encode() not in mc,'Native timing CDB still names frozen build04 constraints'
 def nativepins(pp):return '{'+' '.join('{'+p+'}' for p in sorted(set(pp)))+'}'
 targets=' -from '+nativepins(r['launch_CLK'] for r in mapped)+' -to '+nativepins(r['capture_D'] for r in mapped)
 tool('native_clock_exception',ARCH+'report_timing -force_to_run -input_db_file {'+(W/'device_map/v7_sdt_top_map.adf').as_posix()+'} -delay_type max -report_exception TRUE -input_pins TRUE -max_path 2560 -nworst 1'+targets+'\n',E/'reports')
 guard()
if __name__=='__main__':
 try:
  k,h=lock()
  try:
   if sys.argv[1]=='help':tool('official_entry_help',ARCH+''.join('help '+x+'\n' for x in ['add_constraint','compile','synthesize','dev_map','get_pins','set_max_delay']),E/'help')
   elif sys.argv[1]=='build':prepare();build();guard()
   elif sys.argv[1]=='map':mapping()
   else:raise RuntimeError('Unknown requested action')
  finally:k.ReleaseMutex(h);k.CloseHandle(h)
 except BaseException:
  save('failure_'+str(time.time_ns())+'.json',{'traceback':traceback.format_exc()})
  if (E/'frozen_before.json').exists():
   try:guard()
   except BaseException:save('guard_failure_'+str(time.time_ns())+'.json',{'traceback':traceback.format_exc()})
  raise
