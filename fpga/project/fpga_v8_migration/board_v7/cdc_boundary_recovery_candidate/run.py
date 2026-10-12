from pathlib import Path
import subprocess,os,hashlib,sys
here=Path(__file__).resolve().parent
old=here.parent/'cdc_boundary_candidate'
base=here.parent/'capture_boundary_integration'
root=here.parents[1]/'whole_candidate_v7_route_01'
tools=Path(os.environ.get('MODELSIM_BIN','C:/modeltech64_10.6e/win64'))
vendor=Path('C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation')
protected=list(old.rglob('*'))+list(root.rglob('*'))+list(base.glob('*'))
protected=[p for p in protected if p.is_file() and p.suffix in ('.v','.vh','.sv','.py','.log','.md','.pds','.fdc')]
before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
subprocess.run([sys.executable,str(here/'generate.py')],check=True)
ddr=root/'inputs/source/ov5640/ov5640_ddr'
sources=[root/'rtl/ov5640_cdc_tc04.v',root/'rtl/ov5640_ddr_tc04.v',root/'inputs/source/ov5640/ov5640/cmos_capture.v',root/'inputs/source/ov5640/cam_fir3.v']
sources += [ddr/n for n in ('ov5640_ddr_w_en.v','ov5640_ddr_w.v','ov5640_ddr_w_ctrl.v')]
for name in ('ov5640_cdc_fifo','ov5640_ddr_fifo_DRM','ov5640_ddr_fifo'):
 d=root/'inputs/ipcore'/name;sources += [d/(name+'.v'),*sorted((d/'rtl').glob('*.v'))]
sources += [vendor/(n+'.v') for n in ('GTP_DRM18K_E1','GTP_DRM36K_E1','GTP_GRS')]
sources += [here/n for n in ('cdc_order_meta.v','cdc_recovery.v','ddr_recovery.v','ddr_ctrl_recovery.v')]
def run(build,exe,args,log):
 with (build/log).open('wb') as f:
  result=subprocess.run([str(tools/exe),*map(str,args)],cwd=build,stdout=f,stderr=subprocess.STDOUT)
 if result.returncode: raise RuntimeError((build/log).read_text(errors='replace')[-6000:])
def sim(mode,tb,top,chain=None,extra=()):
 build=here/mode;build.mkdir(exist_ok=True)
 (build/'tb.sv').write_bytes(tb)
 local=[build/'tb.sv']
 if chain is not None: (build/'chain.v').write_bytes(chain);local.insert(0,build/'chain.v')
 if not (build/'work').exists():run(build,'vlib.exe',['work'],'vlib.log')
 run(build,'vlog.exe',['-sv',*sources,*local],'compile.log')
 run(build,'vsim.exe',['-c','-voptargs=+acc',*extra,'work.'+top,'-do','onerror {quit -code 1}; run -all; quit -code 0'],'simulation.log')
 text=(build/'simulation.log').read_text(errors='replace')
 print(mode,'\n'.join(l for l in text.splitlines() if any(k in l for k in ('RESULT','DONE','FAIL','RECOVERY','CONTINUOUS','LONG_LEVEL'))),flush=True)
 assert 'errors=0' in text and 'FAIL' not in text
chain=(base/'frozen_capture_chain.v').read_bytes()
newchain=chain.replace(b'ov5640_cdc_tc04',b'cdc_recovery').replace(b'input ov_rst_n,cam_rst_n,video_clk,video_rst,',b'input system_reset,ov_rst_n,cam_rst_n,video_clk,video_rst,').replace(b'output [15:0] video_data',b'output boundary_fault,\noutput [15:0] video_data').replace(b'.cam_clk(cam_pclk),',b'.system_reset(system_reset),.boundary_fault(boundary_fault),\n    .cam_clk(cam_pclk),')
tb=(base/'tb_integration.sv').read_bytes().replace(b'\r\n',b'\n')
prefix=tb[:tb.index(b'initial begin\n if($test$plusargs')].replace(b'queue[0:700000]',b'queue[0:1000000]')
newprefix=prefix.replace(b'wire [15:0] pix,fpix;',b'wire boundary_fault; wire [15:0] pix,fpix;').replace(b'.ov_rst_n(!rst)',b'.system_reset(rst),.boundary_fault(boundary_fault),.ov_rst_n(!rst)').replace(b'.rst(rst),.in_valid',b'.rst(rst | boundary_fault),.in_valid').replace(b'ov5640_ddr_tc04 #',b'ddr_recovery #').replace(b'.dma_abort(1\'b0)',b'.transport_abort(boundary_fault),.dma_abort(1\'b0)')
if '--review' not in sys.argv and '--extended' not in sys.argv:
 for mode,pre,ch,case in [('baseline',prefix,chain,'cases.vh'),('candidate',newprefix,newchain,'cases.vh'),('extra',newprefix,newchain,'extra_cases.vh'),('long_baseline',prefix,chain,'long_cases.vh'),('long_candidate',newprefix,newchain,'long_cases.vh')]:
  if mode.startswith('long'):pre=pre.replace(b'idle(tail);marker(16);idle(32);',b'idle(tail);marker(pulse);idle(32);')
  tests=(old/case).read_bytes().replace(b'IS_CANDIDATE',b'0' if 'baseline' in mode else b'1')
  sim(mode,pre+tests,'tb_integration',ch)
if '--extended' in sys.argv:
 pre=newprefix.replace(b'reg cam=0,video=0,rst=1,vs=0,href=0;',b'reg cam=0,video=0,rst=1,vs=0,href=0; reg cam_request=0,video_request=0;').replace(b'.cam_rst_n(!rst)',b'.cam_rst_n(!(rst|cam_request))').replace(b'.video_rst(rst)',b'.video_rst(rst|video_request)')
 sim('binding_recovery',pre+(here/'binding_cases.vh').read_bytes(),'tb_integration',newchain)
sim('review',(here/'tb_recovery.sv').read_bytes(),'tb_recovery')
sim('review_board',(here/'tb_recovery.sv').read_bytes(),'tb_recovery',extra=('-gCAM_HALF=5.9525','-gVID_HALF=3.8095'))
contract=(old/'tb_contract.sv').read_bytes().replace(b'\r\n',b'\n')
contract=contract.replace(b'cdc_order_candidate #',b'cdc_recovery #').replace(b'dut(.cam_clk(cam)',b'dut(.system_reset(rst),.cam_clk(cam)')
contract=contract.replace(b'@(negedge cam);rst=0;',b'@(negedge cam);rst=0; repeat(20) tick(0,0,0);')
old_pixel_setup=b'reset_all();@(negedge vid);ven=0;\n  repeat(1100)'
assert old_pixel_setup in contract
contract=contract.replace(old_pixel_setup,b'reset_all();tick(1,0,0);tick(0,0,0);@(negedge vid);ven=0;\n  repeat(1100)')
sim('contract',contract,'tb_contract')
assert before=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
(here/'protected_hashes.txt').write_text('\n'.join(f'{v}  {k}' for k,v in before.items())+'\n')
print('PROTECTED_UNCHANGED',len(before))
