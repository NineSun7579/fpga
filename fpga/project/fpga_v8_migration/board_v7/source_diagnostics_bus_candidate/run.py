"""Local ModelSim only. Generate mechanical TB wiring; hash frozen inputs."""
from pathlib import Path
import hashlib, os, subprocess, re
P=Path(__file__).resolve().parent
F=P.parents[1]/'whole_candidate_v7_route_01'
S=P.parent/'source_frame_diagnostics_candidate'
inputs=[F/'inputs/source/ov5640/axi_to_axi_lite.v',F/'rtl/ovreg_axil_decode_tc01.v',S/'v7_sfd_candidate.v',F/'inputs/source/ov5640/ov5640/cmos_capture.v',F/'rtl/ov5640_tc03_binding.v']
inputs.append(F/'inputs/source/pcie_dma/pcie_fifo.v')
def hashes(): return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
before=hashes()
expected=['96f932e5e8f61683b0b8f2f57581b0ea90c32b4cf288f3e1886e19a7d98050b3',
 '8e77852f4e969984ad7e333445acc067c7cac0714f6b5adaf8156a4a4fbd5c5e',
 'e417f08619c0b7a4e66bab41bcd8fc747a0239ef59ab34b85f24d50f3e776c93',
 'bf59cfe4da8564a036c5033a5cb4995180049f812ae7eca6011881d9963ffb61',
 '63c7b8b48410cf8cb05115a425a209f42652dfdd5248961bf2132bcff4b25a1d',
 'c6bcf1f48328ff250e097ad1bbe0e49e8e52001138fe15f9db697da1ddf62027']
assert list(before.values())==expected,'Frozen dependency changed: review before updating binding'
conflicts=[]
for root in [P.parents[2]/'source',P.parent,F/'rtl',F/'inputs/source']:
 for p in root.rglob('*'):
  if p.suffix.lower() not in ('.v','.sv') or P in p.parents: continue
  if re.search(rb'\bmodule\s+(v7_sdb|sdb_legacy_slave|tb_v7_sdb)\b',p.read_bytes()): conflicts.append(str(p))
assert not conflicts,conflicts
print('BYTE_MODULE_SCAN conflicts=0')
evidence=[]
for p in [inputs[0],inputs[1],inputs[4],inputs[5]]:
 keys=[b'm_axil_awaddr',b'm_axil_araddr',b'm_axil_wdata',b's_axi_rdata',b'motion_aw',b'cdc_read',b'aw_saved',b'cur_addr',b'AXI_DATA_SIZE',b'cmos_frame_valid_r',b'cmos_frame_vsync_r',b'.cam_rst']
 for n,line in enumerate(p.read_bytes().splitlines(),1):
  if any(k in line for k in keys): evidence.append(f'{p.relative_to(F)}:{n}: '+line.decode('gbk',errors='replace'))
(P/'address_evidence.txt').write_text('\n'.join(evidence),encoding='utf-8')
ports={'awvalid':1,'awready':1,'awaddr':32,'wvalid':1,'wready':1,'wdata':32,'wstrb':4,'bvalid':1,'bready':1,'bresp':2,'arvalid':1,'arready':1,'araddr':32,'rvalid':1,'rready':1,'rdata':32,'rresp':2}
lines=[]
for prefix in ['s','m']+[f'q{i}' for i in range(5)]:
 for n,w in ports.items(): lines.append(f'wire {"" if w==1 else f"[{w-1}:0] "}{prefix}_{n};')
lines.append('v7_sdb dut (.clk(clk),.rst(rst),.cam_clk({4{camclk}}),.cam_reset(cr),.raw_vsync(rawvs),.raw_href(href),.raw_byte_accept(href),.capture_vsync(capvs),.capture_valid(capvalid),'+','.join(f'.{p}_{n}({p}_{n})' for p in ['s','m'] for n in ports)+');')
bridge=['.axi_clk(clk)','.axi_rst(rst)']
for ch in ['aw','w','b','ar','r']:
 for n in ports:
  if n.startswith(ch) and not (ch=='r' and n.startswith('ar')):
   bridge.append(f'.m_axil_{n}(s_{n})')
   bridge.append(f'.s_axi_{n}({"dma_wdata" if n=="wdata" else "dma_wstrb" if n=="wstrb" else "dma_rdata" if n=="rdata" else "u_"+n})')
for ch in ['aw','ar']:
 for n,w in [('id',4),('len',8),('size',3),('burst',2),('lock',2),('cache',4),('prot',3),('qos',4),('region',4)]:
  bridge.append(f'.s_axi_{ch}{n}({w}\'d{4 if n=="size" else 1 if n=="burst" else 0})')
bridge+=['.s_axi_wlast(1\'b1)','.s_axi_bid()','.s_axi_rid()','.s_axi_rlast()']
lines.append('axi_to_axi_lite bridge ('+','.join(bridge)+');')
lines.append('ovreg_axil_decode_tc01 legacy (.clk(clk),.rst(rst),'+','.join(f'.s_{n}(m_{n})' for n in ports)+','+','.join(f'.m{i}_{n}(q{i}_{n})' for i in range(5) for n in ports)+');')
for i in range(5):
 lines.append(f'sdb_legacy_slave #(.TAG({i})) slave{i} (.clk(clk),.rst(rst),'+','.join(f'.{n}(q{i}_{n})' for n in ports)+');')
# Four real frozen captures and the binding's negedge observation registers.
for i in range(4):
 lines.append(f'''wire cv{i}, vs{i};
 cmos_capture #(.DATA_WIDTH(16),.DELAY(2)) cap{i} (.cam_pclk(camclk),.rst_n(!cr[{i}] && !rst),.cam_vsync(rawvs[{i}]),.cam_href(href[{i}]),.cam_data(8'h55),.cmos_frame_vsync(vs{i}),.cmos_frame_href(),.cmos_frame_valid(cv{i}),.cmos_frame_data());
 always @(negedge camclk) begin capvs[{i}]<=vs{i}; capvalid[{i}]<=cv{i}; end''')
(P/'fixture.vh').write_text('\n'.join(lines),encoding='ascii')
bin=Path(os.environ.get('MODELSIM_BIN',r'C:\modeltech64_10.6e\win64'))
def run(exe,args,log):
 r=subprocess.run([str(bin/exe),*map(str,args)],cwd=P,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 text=r.stdout.decode('utf-8',errors='replace'); (P/log).write_text(text,encoding='utf-8')
 print(text[-3500:]); assert r.returncode==0,(exe,r.returncode)
 return text
if not (P/'work').exists(): run('vlib.exe',['work'],'vlib.log')
run('vlog.exe',['-sv',*inputs[:4],P/'v7_sdb.v',P/'tb.sv'],'compile.log')
t=run('vsim.exe',['-c','-novopt','work.tb_v7_sdb','-do','onerror {quit -code 1}; run -all; quit -f'],'simulation.log')
assert 'SDB_ALL_PASS' in t and 'FAIL' not in t
# Re-run unchanged original source scoreboard in THIS directory's library.
run('vlog.exe',['-sv',S/'tb_v7_sfd_candidate.sv'],'source_compile.log')
t=run('vsim.exe',['-c','-novopt','work.tb_v7_sfd_candidate','-do','onerror {quit -code 1}; run -all; quit -f'],'source_simulation.log')
assert 'SFD_ALL_PASS' in t and 'FAIL' not in t
assert before==hashes()
(P/'source_hashes.txt').write_text('\n'.join(f'{v}  {k}' for k,v in before.items()),encoding='utf-8')
print('FROZEN_HASHES_UNCHANGED')
