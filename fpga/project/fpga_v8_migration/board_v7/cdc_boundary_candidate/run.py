"""Generate reviewable isolated derivatives; compile actual frozen/vendor inputs."""
from pathlib import Path
import subprocess, hashlib, os, sys
here=Path(__file__).resolve().parent
base=here.parent/'capture_boundary_integration'
root=here.parents[1]/'whole_candidate_v7_route_01'
tools=Path(os.environ.get('MODELSIM_BIN','C:/modeltech64_10.6e/win64'))
vendor=Path('C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation')
ddr=root/'inputs/source/ov5640/ov5640_ddr'
sources=[root/'rtl/ov5640_cdc_tc04.v',root/'rtl/ov5640_ddr_tc04.v',root/'inputs/source/ov5640/ov5640/cmos_capture.v',root/'inputs/source/ov5640/cam_fir3.v']
sources += [ddr/n for n in ('ov5640_ddr_w_en.v','ov5640_ddr_w.v','ov5640_ddr_w_ctrl.v')]
for name in ('ov5640_cdc_fifo','ov5640_ddr_fifo_DRM','ov5640_ddr_fifo'):
 d=root/'inputs/ipcore'/name
 sources += [d/(name+'.v'),*sorted((d/'rtl').glob('*.v'))]
sources += [vendor/(n+'.v') for n in ('GTP_DRM18K_E1','GTP_DRM36K_E1','GTP_GRS')]
protected=sources+list(base.glob('*.sv'))+[base/'frozen_capture_chain.v']
before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
orig=sources[0].read_bytes()
new=orig[:orig.index(b'    reg [1:0] vsync_sync')]+(here/'transport.vh').read_bytes()+orig[orig.index(b'    reg src_vs_q'):]
new=new.replace(b'module ov5640_cdc_tc04',b'module cdc_order_candidate')
new=new.replace(b'    input cam_clk, cam_rst,',b'    output boundary_fault,\n    input cam_clk, cam_rst,')
new=new.replace(b'    assign video_data=dout;',b'    assign boundary_fault=fault_sync[1];\n    assign video_data=dout;')
new=new.replace(b'                dbg_cdc_output <= out_snapshot;',b'')
new=new.replace(b'            out_vs_q <= video_vsync;',b'            dbg_cdc_output <= out_snapshot;\n            out_vs_q <= video_vsync;')
(here/'cdc_order_candidate.v').write_bytes(new)
chain=(base/'frozen_capture_chain.v').read_bytes()
tb=(base/'tb_integration.sv').read_bytes().replace(b'\r\n',b'\n')
# Reuse all stimulus/checker/DDR endpoint tasks, replace only test selection.
prefix=tb[:tb.index(b'initial begin\n if($test$plusargs')]
prefix=prefix.replace(b'queue[0:700000]',b'queue[0:1000000]')
assert sys.argv[1:] in ([],['--candidate'],['--extra'],['--long'])
extra=sys.argv[1:]==['--extra']
long_mode=sys.argv[1:]==['--long']
tests=(here/('long_cases.vh' if long_mode else ('extra_cases.vh' if extra else 'cases.vh'))).read_bytes()
if long_mode:
 prefix=prefix.replace(b'idle(tail);marker(16);idle(32);',b'idle(tail);marker(pulse);idle(32);')
for mode in (('long_baseline','long_candidate') if long_mode else (('extra',) if extra else (('candidate',) if sys.argv[1:] else ('baseline','candidate')))):
 build=here/mode;build.mkdir(exist_ok=True)
 is_baseline=mode in ('baseline','long_baseline')
 (build/'chain.v').write_bytes(chain if is_baseline else chain.replace(b'ov5640_cdc_tc04',b'cdc_order_candidate'))
 (build/'tb.sv').write_bytes(prefix+tests.replace(b'IS_CANDIDATE',b'0' if is_baseline else b'1'))
 def run(exe,args,log):
  with (build/log).open('wb') as f:
   r=subprocess.run([str(tools/exe),*map(str,args)],cwd=build,stdout=f,stderr=subprocess.STDOUT)
  if r.returncode: raise RuntimeError((build/log).read_text(errors='replace')[-12000:])
 if not (build/'work').exists():run('vlib.exe',['work'],'vlib.log')
 run('vlog.exe',['-sv',*sources,here/'cdc_order_meta.v',here/'cdc_order_candidate.v',build/'chain.v',build/'tb.sv'],'compile.log')
 run('vsim.exe',['-c','-voptargs=+acc','work.tb_integration','-do','onerror {quit -code 1}; run -all; quit -code 0'],'simulation.log')
 text=(build/'simulation.log').read_text(errors='replace')
 print(mode, '\n'.join(l for l in text.splitlines() if any(s in l for s in ('RESULT','DONE','FAIL','CONTINUOUS','LONG_LEVEL'))),flush=True)
 assert 'CANDIDATE_DONE' in text and 'errors=0' in text and 'FAIL' not in text
assert before=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
(here/'source_hashes.txt').write_text('\n'.join(f'{v}  {k}' for k,v in before.items())+'\n')
