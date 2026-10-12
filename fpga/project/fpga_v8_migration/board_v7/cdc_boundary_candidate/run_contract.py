from pathlib import Path
import subprocess,os
here=Path(__file__).resolve().parent
root=here.parents[1]/'whole_candidate_v7_route_01'
tools=Path(os.environ.get('MODELSIM_BIN','C:/modeltech64_10.6e/win64'))
vendor=Path('C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation')
build=here/'contract';build.mkdir(exist_ok=True)
ip=root/'inputs/ipcore/ov5640_cdc_fifo'
sources=[ip/'ov5640_cdc_fifo.v',*sorted((ip/'rtl').glob('*.v')),vendor/'GTP_DRM18K_E1.v',vendor/'GTP_GRS.v',here/'cdc_order_meta.v',here/'cdc_order_candidate.v',here/'tb_contract.sv']
def run(exe,args,log):
 with (build/log).open('wb') as f:
  r=subprocess.run([str(tools/exe),*map(str,args)],cwd=build,stdout=f,stderr=subprocess.STDOUT)
 if r.returncode:raise RuntimeError((build/log).read_text(errors='replace')[-8000:])
if not (build/'work').exists():run('vlib.exe',['work'],'vlib.log')
run('vlog.exe',['-sv',*sources],'compile.log')
run('vsim.exe',['-c','-voptargs=+acc','work.tb_contract','-do','onerror {quit -code 1}; run -all; quit -code 0'],'simulation.log')
text=(build/'simulation.log').read_text(errors='replace')
print(text)
assert 'CONTRACT_DONE errors=0' in text and 'FAIL' not in text
