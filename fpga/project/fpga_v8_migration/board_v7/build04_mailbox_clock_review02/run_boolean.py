from pathlib import Path
import hashlib,json,re,subprocess
P=Path(__file__).resolve().parent;D=P/'cycle';SIM=Path('C:/modeltech64_10.6e/win64')
def run(exe,args,name):
 r=subprocess.run([str(SIM/exe),*map(str,args)],cwd=D,capture_output=True);text=(r.stdout+r.stderr).decode('utf8','replace');(P/name).write_text(text,encoding='utf8');print(text[-1000:],flush=True)
 assert r.returncode==0 and not re.search(r'\*\* (Error|Fatal)',text),name
 return text
run('vlog.exe',['-sv',P/'tb_boolean_exhaustive.sv'],'boolean_compile.log')
text=run('vsim.exe',['-c','-voptargs=+acc','work.tb_boolean_exhaustive','-do','run -all; quit -code 0'],'boolean_exhaustive.log')
assert 'PASS build01/build04 counter exhaustive524288' in text and 'PASS build01/build04 gap exhaustive1048576' in text
(P/'boolean_exhaustive_result.json').write_text(json.dumps({'status':'PASS_FRESH_EXHAUSTIVE_BOOLEAN_EQUIVALENCE','counter_state_control_transitions':524288,'gap_state_control_transitions':1048576,'includes_prefix_and_next_q':True,'compiled_actual_sources_binding':'cycle_result.json','tb_sha256':hashlib.sha256((P/'tb_boolean_exhaustive.sv').read_bytes()).hexdigest()},indent=2)+'\n',encoding='utf8')
