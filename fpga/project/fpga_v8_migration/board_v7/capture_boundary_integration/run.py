"""Read-only frozen V7 integration; real generated FIFOs + PDS primitives."""
from pathlib import Path
import os, subprocess, hashlib,sys
here=Path(__file__).resolve().parent
root=here.parents[1]/'whole_candidate_v7_route_01'
tools=Path(os.environ.get('MODELSIM_BIN','C:/modeltech64_10.6e/win64'))
vendor=Path('C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation')
mode=sys.argv[1] if len(sys.argv)>1 else ''
assert mode in ('','--smoke','--repro')
build=here/('modelsim'+('_'+mode[2:] if mode else '')); build.mkdir(exist_ok=True)
binding=root/'rtl/ov5640_tc03_binding.v'
parent=root/'rtl/parent_tc04_c40cee500c37.v'
parent_bytes=parent.read_bytes()
for connection in (
 b'assign sh_video_valid = video_valid;', b'assign sh_video_vsync = video_vsync;',
 b'assign kf_video_valid = fir_video_valid;', b'assign kf_video_vsync = fir_video_vsync;',
 b'.in_valid  (sh_video_valid )', b'.in_vsync  (sh_video_vsync )',
 b'.out_valid (fir_video_valid)', b'.out_vsync (fir_video_vsync)',
 b'.s_data_valid   (kf_video_valid)', b'.s_vsync        (kf_video_vsync)'):
 assert connection in parent_bytes, f'Frozen connection changed: {connection!r}'
body=binding.read_bytes().split(b'cmos_capture #(',1)[1].rsplit(b'endmodule',1)[0]
# Exact capture / negedge / CDC instance text, extracted without changing behavior.
header=b'''module frozen_capture_chain(input cam_pclk,cam_vsync,cam_href,input [7:0] cam_data,
input ov_rst_n,cam_rst_n,video_clk,video_rst,
output [15:0] video_data,output video_valid,video_hsync,video_vsync,
output [31:0] dbg_cdc_input,dbg_cdc_output,dbg_cdc_drop,dbg_cdc_seq);
parameter DATA_WIDTH=16; parameter DEVICE="PG";
wire capture_vsync=cam_vsync;
wire cmos_frame_vsync,cmos_frame_href,cmos_frame_valid;
wire [15:0] cmos_frame_data;
cmos_capture #('''
(here/'frozen_capture_chain.v').write_bytes(header+body+b'endmodule\n')
ddr=root/'inputs/source/ov5640/ov5640_ddr'
sources=[root/'rtl/ov5640_cdc_tc04.v', root/'rtl/ov5640_ddr_tc04.v',
 root/'inputs/source/ov5640/ov5640/cmos_capture.v',root/'inputs/source/ov5640/cam_fir3.v']
sources += [ddr/n for n in ('ov5640_ddr_w_en.v','ov5640_ddr_w.v','ov5640_ddr_w_ctrl.v')]
for name in ('ov5640_cdc_fifo','ov5640_ddr_fifo_DRM','ov5640_ddr_fifo'):
 d=root/'inputs/ipcore'/name
 sources += [d/(name+'.v'),*sorted((d/'rtl').glob('*.v'))]
sources += [vendor/(n+'.v') for n in ('GTP_DRM18K_E1','GTP_DRM36K_E1','GTP_GRS')]
hashed=sources+[binding,parent]
before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in hashed}
def run(exe,args,log):
 cmd=[str(tools/exe),*map(str,args)]
 print(subprocess.list2cmdline(cmd),flush=True)
 with (build/log).open('wb') as f:
  result=subprocess.run(cmd,cwd=build,stdout=f,stderr=subprocess.STDOUT)
 if result.returncode:
  print((build/log).read_text(errors='replace')[-12000:]); raise SystemExit(result.returncode)
if not (build/'work').exists(): run('vlib.exe',['work'],'vlib.log')
run('vlog.exe',['-sv',*sources,here/'frozen_capture_chain.v',here/'tb_integration.sv'],'compile.log')
simulation_log='simulation'+('_'+mode[2:] if mode else '')+'.log'
extra=['+'+mode[2:].upper()] if mode else []
run('vsim.exe',['-c','-voptargs=+acc','work.tb_integration',*extra,'-do','onerror {quit -code 1}; run -all; quit -code 0'],simulation_log)
log=(build/simulation_log).read_text(errors='replace')
print('\n'.join(x for x in log.splitlines() if 'RESULT' in x or 'DONE' in x or 'FAIL' in x))
assert 'INTEGRATION_DONE' in log and 'errors=0' in log and 'FAIL' not in log
assert before=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in hashed}
(here/'source_hashes.txt').write_text('\n'.join(f'{h}  {p}' for p,h in before.items())+'\n')
