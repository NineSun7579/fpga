from pathlib import Path
import json,subprocess,hashlib,time,sys
E=Path(__file__).resolve().parent;W=E/'functional_compile';W.mkdir();SIM=Path('C:/modeltech64_10.6e/win64')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
binding=json.loads((E/'official_library_binding.json').read_bytes());selected={}
for typ,candidates in binding['closure'].items():
 if not candidates:raise RuntimeError('Missing model '+typ)
 preferred=sorted(candidates,key=lambda c:('bsim' not in Path(c['path']).parts,c['path']))[0]
 selected[typ]=preferred
models=sorted({c['path'] for c in selected.values()});netlist=E/'functional/generate_netlist/v7_sdt_top_sim.v'
commands=[[str(SIM/'vlib.exe'),'work'],[str(SIM/'vlog.exe'),'-work','work',*models],[str(SIM/'vlog.exe'),'-work','work',str(netlist)]];receipts=[]
for n,cmd in enumerate(commands):
 with (W/('step'+str(n)+'.log')).open('xb') as f:
  p=subprocess.Popen(cmd,cwd=W,stdout=f,stderr=subprocess.STDOUT)
  (W/('step'+str(n)+'_process.json')).write_text(json.dumps({'pid':p.pid,'command':cmd,'tool_sha256':sha(Path(cmd[0])),'time':time.time()},indent=2)+'\n');code=p.wait()
 receipts.append({'command':cmd,'exit_code':code,'log_sha256':sha(W/('step'+str(n)+'.log'))})
 if code:break
result={'passed':len(receipts)==3 and all(r['exit_code']==0 for r in receipts),'receipts':receipts,'selected_official_models':selected,'netlist_sha256':sha(netlist),'scope':'Compile actual full exported netlist against official library closure. Compilation alone does not prove whole-design functional equivalence or hardware timing.'}
(E/'functional_compile_receipt.json').write_text(json.dumps(result,indent=2)+'\n');print('FULL_FUNCTIONAL_COMPILE',result['passed']);sys.exit(0 if result['passed'] else 1)
