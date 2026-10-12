from pathlib import Path
import subprocess
R=Path(__file__).resolve().parent;P=R.parents[1];B=Path('C:/modeltech64_10.6e/win64')
def run(args,name,marker=None):
 p=subprocess.run([str(x) for x in args],cwd=R,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 t=p.stdout.decode(errors='replace');(R/name).write_text(t)
 if p.returncode or (marker and marker not in t):raise RuntimeError(name)
 return t
# Existing ABI regression plus independent AW/W capture and frozen bank reads.
tb=(R.parent/'sfp_diag/tb_sfp_diag.v').read_bytes()
tb=tb.replace(b'reg [31:0] captured;',b'reg [31:0] captured; reg [511:0] bank; integer ix;')
tb=tb.replace(b'.sfp_diag_rejects(32\'h91800007)',b'.sfp_rx_diag_bank(bank), .sfp_diag_rejects(32\'h91800007)')
tb=tb.replace(b'repeat (4) @(negedge clk);',b'for(ix=0;ix<16;ix=ix+1)bank[ix*32 +:32]=32\'hface0000+ix;\n        repeat (4) @(negedge clk);',1)
insert=b'''read_check(32'h200001f0,0,0);
        write_reg(32'h200001d0,32'h100,4'hf);
        read_check(32'h200001f0,0,1);
        bank=0;
        for(ix=0;ix<16;ix=ix+1)begin
            write_reg(32'h200001d0,ix,4'hf);
            read_check(32'h200001e0,0,32'hface0000+ix);
        end
        // Bit 8 without byte1 strobe must not capture a new bank.
        write_reg(32'h200001d0,32'h100,4'h1);
        read_check(32'h200001f0,0,1);
        read_check(32'h200001e0,0,32'hface0000);
        write_reg(32'h200001d0,32'h100,4'hf);
        read_check(32'h200001f0,0,2);
        read_check(32'h200001e0,0,0);'''
tb=tb.replace(b"read_check(32'h200001f0, 0, 0);",insert)
(R/'tb_registers.v').write_bytes(tb)
# Exact production ingress alignment + bridge + decode: preserve existing
# camera CDC and PREP routing, additionally check new slots and all aliases.
host=(R.parent/'cdc_pixel_repro/tb_cdc_host_map.sv').read_bytes()
extra=b''
for off in [0x1d0,0x1e0,0x1f0]:
 for lane in range(16):extra+=f" check(32'h{0x20000000+off+lane:08x},32'hfacefeed);\n".encode()
host=host.replace(b'  $display("PASS HOST MAP',extra+b'  $display("PASS HOST MAP')
(R/'tb_host_route.sv').write_bytes(host)
run([B/'vlib.exe','regwork'],'reg_vlib.log')
run([B/'vlog.exe','-sv','-work','regwork',R/'candidate/preprocess/prep_regs.v','tb_registers.v',P/'source/ov5640/axi_to_axi_lite.v',P/'source/ov5640/ovreg_axil_decode.v',P/'source/ov5640/ov5640_reg.v','tb_host_route.sv','sfp_rx_diagnostics.sv','tb_diagnostics.sv'],'reg_compile.log')
for tb,marker in [('tb_sfp_diag','SFP_DIAG_PASS'),('tb_cdc_host_map','PASS HOST MAP'),('tb_diagnostics','PASS DIAGNOSTICS')]:
 run([B/'vsim.exe','-c','regwork.'+tb,'-do','onbreak {quit -code 1 -force}; onerror {quit -code 1 -force}; run -all; quit -code 0 -force'],tb+'.log',marker)
print('PASS legacy ABI, frozen bank, independent AW/W, host aliases/routing, diagnostics counters/CDC')
