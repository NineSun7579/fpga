from pathlib import Path
import subprocess,json,hashlib,sys
E=Path(__file__).resolve().parent
I=Path('C:/pango/PDS_2022.2-SP6.4');SIM=Path('C:/modeltech64_10.6e/win64')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
W=E/'model_contract';W.mkdir()
models=[I/'arch/vendor/pango/verilog/simulation'/n for n in ['GTP_GRS.v','GTP_DFF_C.v','GTP_DFF_P.v']]+[I/'arch/vendor/pango/verilog/bsim/V_FFASYN.v']
commands=[[str(SIM/'vlib.exe'),'work'],[str(SIM/'vlog.exe'),'-work','work',*map(str,models),str(E/'contract_tb.v')],[str(SIM/'vsim.exe'),'-c','-l','vsim.log','work.contract_tb','-do','run -all; quit -f']]
receipts=[]
for n,cmd in enumerate(commands):
 p=subprocess.run(cmd,cwd=W,capture_output=True);raw=p.stdout+p.stderr;(W/('step'+str(n)+'.log')).write_bytes(raw)
 receipts.append({'command':cmd,'exit_code':p.returncode,'tool_sha256':sha(Path(cmd[0]))})
 if p.returncode:break
text=b'\n'.join(p.read_bytes() for p in W.glob('*.log'))
result={'pass':b'PASS_OFFICIAL_GTP_CP_V_FFASYN' in text and b'MISMATCH' not in text,'receipts':receipts,'models':{str(p):sha(p) for p in models},'fixture_sha256':sha(E/'contract_tb.v'),'scope':'Binary event contract for exact active-high asynchronous C/P, positive CK, CE tied 1, GRS and INIT precedence. Does not establish routed connectivity or final timing.'}
(E/'official_cp_contract.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2));sys.exit(0 if result['pass'] else 1)
