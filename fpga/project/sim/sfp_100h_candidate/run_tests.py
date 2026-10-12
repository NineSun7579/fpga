from pathlib import Path
import subprocess,json,hashlib
R=Path(__file__).resolve().parent;B=Path('C:/modeltech64_10.6e/win64');A=R.parent/'sfp_align';C=R/'candidate'
def run(args,name):
 p=subprocess.run([str(x) for x in args],cwd=R,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 text=p.stdout.decode(errors='replace');(R/name).write_text(text)
 if p.returncode:raise RuntimeError(name)
 return text
def main():
 # Insert 120 actual control prefixes immediately before B words.
 words=[tuple(int(x,16) for x in l.split()) for l in (R.parent/'sfp_payload_probe/actual.vec').read_text().splitlines()]
 payload=0;targets=set()
 for i,(d,k) in enumerate(words):
  if k==0:
   if payload%1280==640 and payload//1280%4==0:targets.add(i-1)
   payload+=2
 syms=[]
 for i,(d,k) in enumerate(words):
  if i in targets:syms.extend([(0xbc,1),(0x28,0)])
  syms.extend(((d>>(8*j))&255,(k>>j)&1) for j in range(4))
 with (R/'insert_full.vec').open('w') as f:
  for i in range(0,len(syms),4):
   ch=syms[i:i+4];f.write(f'{sum(b<<(8*j) for j,(b,k) in enumerate(ch)):08x} {sum(k<<j for j,(b,k) in enumerate(ch)):x}\n')
 run([B/'vlib.exe','e2ework'],'e2e_vlib.log')
 # Compile the exact top-level OLD/NEW generate branch in an isolated shell.
 top=(C/'top.v').read_bytes();start=top.index(b'generate if (SFP_NEW_PARSER)');end=top.index(b'end endgenerate',start)+len(b'end endgenerate')
 shell=b'''module sfp_decode_select #(parameter SFP_NEW_PARSER=0)(
 input sfp_rx_clk,sfp_rx_rst_n,sfp_rx_en,sfp_raw_en,
 input [31:0] sfp_rxd,sfp_raw_d,input [3:0] sfp_rxk,sfp_raw_k,
 output sfp_vs,sfp_hs,sfp_de,output [15:0] sfp_pix,
 output sfp_parser_overflow,sfp_malformed);
'''+top[start:end]+b'\nendmodule\n'
 (R/'sfp_decode_select.sv').write_bytes(shell)
 tb=(R/'tb_end_to_end.sv').read_bytes()
 begin=tb.index(b' rx_symbol_candidate parser(');finish=tb.index(b';',begin)+1
 tb=tb[:begin]+b''' sfp_decode_select #(.SFP_NEW_PARSER(1)) selected(
 .sfp_rx_clk(clk),.sfp_rx_rst_n(rst_n),.sfp_rx_en(en),.sfp_raw_en(raw_en),
 .sfp_rxd(d),.sfp_rxk(k),.sfp_raw_d(raw_d),.sfp_raw_k(raw_k),
 .sfp_vs(vs),.sfp_hs(hs),.sfp_de(de),.sfp_pix(pix),
 .sfp_parser_overflow(overflow),.sfp_malformed(malformed));'''+tb[finish:]
 (R/'tb_integrated.sv').write_bytes(tb)
 old=tb.replace(b'module tb_end_to_end;',b'module tb_old_default;').replace(b'#(.SFP_NEW_PARSER(1)) selected',b'selected')
 cut=old.index(b'  replay("../sfp_payload_probe/delete_BC28_before_B.vec");')
 old=old[:cut]+b'''  if(n5!=307200 || n6!=307200 || s5!=1 || s6!=1 || malformed)$fatal(1,"old default baseline");
  $display("PASS OLD default parser CAM5/CAM6 exact 307200");$finish;
 end
 initial begin #50000000;$fatal(1,"timeout");end
endmodule
'''
 (R/'tb_old_default.sv').write_bytes(old)
 run([B/'vlog.exe','-sv','-work','e2ework',A/'hsst_sfp_stub.v',C/'sfp/sfp_rx_link.v',C/'sfp/rx_symbol_candidate.sv',C/'sfp/sfp_video_rx.v',C/'sfp/sfp_rx_cam_if.v',C/'sfp/video_async_fifo.v','sfp_decode_select.sv','tb_integrated.sv','tb_old_default.sv',C/'sfp/sfp_rx_diagnostics.sv',C/'preprocess/prep_regs.v'],'e2e_compile.log')
 text=run([B/'vsim.exe','-c','-voptargs=+acc','e2ework.tb_end_to_end','-do','onbreak {quit -code 1 -force}; onerror {quit -code 1 -force}; run -all; quit -code 0 -force'],'e2e.log')
 assert 'PASS E2E' in text
 oldlog=run([B/'vsim.exe','-c','e2ework.tb_old_default','-do','onbreak {quit -code 1 -force}; onerror {quit -code 1 -force}; run -all; quit -code 0 -force'],'old_default.log')
 assert 'PASS OLD' in oldlog
 for row in json.loads((R/'manifest.json').read_text()).values():assert hashlib.sha256(Path(row['source']).read_bytes()).hexdigest()==row['sha256']
 print('PASS E2E and production/IP hashes unchanged')
if __name__=='__main__':main()
