from pathlib import Path
import hashlib
import json
HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'pcie_retirement_contract'

def prepare():
    source=(OLD/'tests/tb_pcie_retirement.sv').read_bytes()
    s=source.decode('ascii')
    s=s[:s.index('    initial begin\n        trace=')]
    s=s.replace('tb_fpga_v8_pcie_retirement','tb_fpga_v8_h2f_transport')
    s=s.replace('`define FIFO_MODULE pcie_fifo','`define FIFO_MODULE fpga_v8_pcie_fifo_h2f')
    s=s.replace('wire release_b=b_age>=b_delay;',
                'wire release_b=b_age>=b_delay;\n    wire gate_w = w_gate && (!periodic_w || cycle%17>=7);')
    s=s.replace('route_aw && w_gate && !memory_mode','route_aw && gate_w && !memory_mode')
    s=s.replace('assign wready=route_aw && w_gate && (memory_mode ? mem_aw : ew_ready);',
                'assign wready=(pre_aw_ready && !route_aw) || (route_aw && gate_w && (memory_mode ? mem_aw : ew_ready));')
    s=s.replace("assign bresp=memory_mode ? 2'b00 : eb_resp;","assign bresp=memory_mode ? memory_resp : eb_resp;")
    s=s.replace('cycle>2500000','cycle>15000000')
    # FETCH reports the actual controller's length/64-bit address. Edge detect
    # the real MRD engine ACK, which can stay high for multiple clocks.
    s=s.replace('if(dut.pango_pcie_top.ack32 || dut.pango_pcie_top.ack64)',
                'if((dut.pango_pcie_top.ack32 || dut.pango_pcie_top.ack64) && !dut.pango_pcie_top.ack_seen)')
    tail=(HERE/'tests/tb_tail.svh').read_text(encoding='ascii')
    declarations="    reg pre_aw_ready=0,periodic_w=0;\n    reg [1:0] memory_resp=0;\n"
    assert declarations in tail
    tail=tail.replace(declarations,'',1)
    s=s.replace('    reg rst_n=0;',declarations+'    reg rst_n=0;',1)
    s+=tail
    (HERE/'artifacts/tb_transport.sv').write_text(s,encoding='ascii')
    manifest=dict(parent_tb_sha256=hashlib.sha256(source).hexdigest(),
        generated_tb_sha256=hashlib.sha256(s.encode()).hexdigest(),
        qualification='reuse immutable endpoint/control wiring and event monitor; add independent FIFO/AXI assertions and case suite')
    (HERE/'artifacts/tb_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')

if __name__=='__main__':prepare()
