from pathlib import Path
import subprocess,json,hashlib,sys
E=Path(__file__).resolve().parent;I=Path('C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/bsim');SIM=Path('C:/modeltech64_10.6e/win64');W=E/'lut_contract';W.mkdir()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
models=[I/n for n in ['INT_LUTMUX2_UDP.v','INT_LUTMUX4_UDP.v','V_LUT5.v','V_MUX2LUT6.v']]
commands=[[str(SIM/'vlib.exe'),'work'],[str(SIM/'vlog.exe'),'-work','work',*map(str,models),str(E/'lut_contract_tb.v')],[str(SIM/'vsim.exe'),'-c','-l','vsim.log','work.lut_contract_tb','-do','run -all; quit -f']]
receipts=[]
for n,cmd in enumerate(commands):
 p=subprocess.run(cmd,cwd=W,capture_output=True);(W/('step'+str(n)+'.log')).write_bytes(p.stdout+p.stderr);receipts.append({'command':cmd,'exit_code':p.returncode,'tool_sha256':sha(Path(cmd[0]))})
 if p.returncode:break
text=b'\n'.join(p.read_bytes() for p in W.glob('*.log'));ok=b'PASS_OFFICIAL_LUT6_COMPOSITION' in text and b'LUT_MISMATCH' not in text
(E/'official_lut_contract.json').write_text(json.dumps({'pass':ok,'receipts':receipts,'models':{str(p):sha(p) for p in models},'fixture_sha256':sha(E/'lut_contract_tb.v'),'scope':'Exhaustive binary LUT index and LUT5 pair/MUX2 LUT6 composition; actual routed INIT and input/half selection require separate binding.'},indent=2)+'\n')
print('OFFICIAL_LUT_CONTRACT_PASS',ok);sys.exit(0 if ok else 1)
