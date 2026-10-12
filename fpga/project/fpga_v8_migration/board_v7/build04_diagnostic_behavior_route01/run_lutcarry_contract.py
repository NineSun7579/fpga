from pathlib import Path
import subprocess,json,hashlib,sys
E=Path(__file__).resolve().parent;I=Path('C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/bsim');SIM=Path('C:/modeltech64_10.6e/win64');W=E/'lutcarry_contract';W.mkdir()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
models=[I/n for n in ['INT_LUTMUX2_UDP.v','INT_LUTMUX4_UDP.v','V_LUT6CARRY.v']]
commands=[[str(SIM/'vlib.exe'),'work'],[str(SIM/'vlog.exe'),'-work','work',*map(str,models),str(E/'lutcarry_contract_tb.v')],[str(SIM/'vsim.exe'),'-c','-l','vsim.log','work.lutcarry_contract_tb','-do','run -all; quit -f']]
receipts=[]
for n,cmd in enumerate(commands):
 p=subprocess.run(cmd,cwd=W,capture_output=True);(W/('step'+str(n)+'.log')).write_bytes(p.stdout+p.stderr);receipts.append({'command':cmd,'exit_code':p.returncode,'tool_sha256':sha(Path(cmd[0]))})
 if p.returncode:break
text=b'\n'.join(p.read_bytes() for p in W.glob('*.log'));ok=b'PASS_OFFICIAL_LUT6CARRY' in text and b'LUTCARRY_MISMATCH' not in text
(E/'official_lutcarry_contract.json').write_text(json.dumps({'pass':ok,'receipts':receipts,'models':{str(p):sha(p) for p in models},'fixture_sha256':sha(E/'lutcarry_contract_tb.v'),'scope':'Exact exported I5_TO_LUT TRUE, I5_TO_CARRY TRUE, Z output contract; binary LUT index, actual INIT/input binding remains independently checked.'},indent=2)+'\n')
print('OFFICIAL_LUTCARRY_CONTRACT_PASS',ok);sys.exit(0 if ok else 1)
