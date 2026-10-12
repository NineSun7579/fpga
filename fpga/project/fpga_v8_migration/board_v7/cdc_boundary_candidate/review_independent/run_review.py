from pathlib import Path
import os, subprocess, hashlib
here=Path(__file__).resolve().parent
candidate=here.parent
root=candidate.parents[1]/'whole_candidate_v7_route_01'
tools=Path(os.environ.get('MODELSIM_BIN','C:/modeltech64_10.6e/win64'))
vendor=Path('C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation')
ip=root/'inputs/ipcore/ov5640_cdc_fifo'
sources=[ip/'ov5640_cdc_fifo.v',*sorted((ip/'rtl').glob('*.v')),vendor/'GTP_DRM18K_E1.v',vendor/'GTP_GRS.v',candidate/'cdc_order_meta.v',candidate/'cdc_order_candidate.v',here/'tb_review.sv']
before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
def run(exe,args,log):
 with (here/log).open('wb') as f:
  result=subprocess.run([str(tools/exe),*map(str,args)],cwd=here,stdout=f,stderr=subprocess.STDOUT)
 if result.returncode: raise RuntimeError((here/log).read_text(errors='replace'))
if not (here/'work').exists():run('vlib.exe',['work'],'vlib.log')
run('vlog.exe',['-sv',*sources],'compile.log')
for name,params in [('simulation',[]),('board_clocks',['-gCAM_HALF=5.9525','-gVID_HALF=3.8095'])]:
 run('vsim.exe',['-c','-voptargs=+acc','work.tb_review',*params,'-do','onerror {quit -code 1}; run -all; quit -code 0'],name+'.log')
 text=(here/(name+'.log')).read_text(errors='replace')
 print(name, '\n'.join(l for l in text.splitlines() if 'REVIEW' in l or 'FAIL' in l))
 assert 'REVIEW_DONE errors=0' in text and 'FAIL' not in text
assert before=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
(here/'input_hashes.txt').write_text('\n'.join(f'{v}  {k}' for k,v in before.items())+'\n')
